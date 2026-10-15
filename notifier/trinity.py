"""Read-only Trinity access over its MCP server (the same tools Claude uses: list_tickets, get_ticket,
get_ticket_messages). The service never writes to Trinity."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client

from .models import Event, Ticket

log = logging.getLogger(__name__)

PAGE_LIMIT = 200  # Trinity clamps get_ticket_messages to 1..200


class TrinityError(RuntimeError):
    pass


class Trinity:
    def __init__(self, session: ClientSession):
        self._session = session

    async def _call(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        result = await self._session.call_tool(tool, args)
        text = "".join(getattr(c, "text", "") for c in (result.content or []))
        if result.is_error:
            raise TrinityError(f"{tool} failed: {text[:500]}")
        if result.structured_content:
            sc = result.structured_content
            return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
        return json.loads(text)

    async def get_ticket(self, ticket_id: str) -> Ticket:
        return Ticket.from_api(await self._call("get_ticket", {"ticket_id": ticket_id}))

    async def tickets_updated_since(self, since: datetime, page_size: int = 100) -> list[Ticket]:
        """Tickets whose updated_at >= since, across all statuses (list is sorted updated_at desc)."""
        out: list[Ticket] = []
        cursor = None
        while True:
            args: dict[str, Any] = {"limit": page_size, "sort_key": "updated_at", "sort_dir": "desc"}
            if cursor:
                args["cursor"] = cursor
            page = await self._call("list_tickets", args)
            for raw in page.get("items", []):
                t = Ticket.from_api(raw)
                if t.updated_at and t.updated_at < since:
                    return out
                out.append(t)
            cursor = page.get("next_cursor")
            if not cursor:
                return out

    async def events_after(self, ticket_id: str, after_seq: int) -> list[Event]:
        """Events with seq > after_seq, oldest first. Walks back from the newest page."""
        collected: list[Event] = []
        cursor = None
        while True:
            args: dict[str, Any] = {"ticket_id": ticket_id, "limit": PAGE_LIMIT, "include_internal": True}
            if cursor:
                args["cursor"] = cursor
            page = await self._call("get_ticket_messages", args)
            events = [Event.from_api(r) for r in page.get("events", [])]
            collected.extend(e for e in events if e.seq > after_seq)
            cursor = page.get("next_cursor")
            if not cursor or not events or min(e.seq for e in events) <= after_seq:
                break
        collected.sort(key=lambda e: e.seq)
        return collected

    async def all_events(self, ticket_id: str) -> list[Event]:
        return await self.events_after(ticket_id, 0)

    async def agent(self, email: str) -> dict | None:
        """{"name", "presence"} for one agent; presence is Trinity's status ("ONLINE", "OFFLINE", ...)."""
        data = await self._call("list_agents", {"query": email, "limit": 10})
        agents = data.get("result", data) if isinstance(data, dict) else data
        for a in agents or []:
            if (a.get("email") or "").lower() == email.lower():
                name = " ".join(x for x in (a.get("first_name"), a.get("last_name")) if x) or email
                return {"name": name, "presence": (a.get("presence") or "").upper() or None}
        return None

    async def presences(self, emails: list[str], concurrency: int = 6) -> dict[str, str | None]:
        """Trinity status ("ONLINE", "OFFLINE", ...) for each email; None when Trinity doesn't know the person.
        One bulk call first (Trinity caps it at 200 agents), then a lookup each for those it left out."""
        wanted = {e.lower() for e in emails}
        data = await self._call("list_agents", {"limit": 200})
        agents = data.get("result", data) if isinstance(data, dict) else data
        found = {(a.get("email") or "").lower(): (a.get("presence") or "").upper() or None for a in agents or []}
        out = {e: found[e] for e in wanted if e in found}
        sem = asyncio.Semaphore(concurrency)

        async def one(email: str) -> None:
            async with sem:
                out[email] = await self.agent_presence(email)

        await asyncio.gather(*(one(e) for e in wanted - out.keys()))
        return out

    async def agent_presence(self, email: str) -> str | None:
        a = await self.agent(email)
        return a["presence"] if a else None

    async def open_tickets(self, assignee: str) -> list[Ticket]:
        out, cursor = [], None
        while True:
            args: dict[str, Any] = {"status": "OPEN", "assigned_to": assignee, "limit": 100}
            if cursor:
                args["cursor"] = cursor
            page = await self._call("list_tickets", args)
            out.extend(Ticket.from_api(r) for r in page.get("items", []))
            cursor = page.get("next_cursor")
            if not cursor:
                return out


@asynccontextmanager
async def connect(url: str, headers: dict[str, str]) -> AsyncIterator[Trinity]:
    async with create_mcp_http_client(headers=headers) as http:
        async with streamable_http_client(url, http_client=http) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield Trinity(session)
