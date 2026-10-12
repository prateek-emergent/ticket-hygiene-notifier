"""Event-driven mode: Trinity tells us when a ticket changes; we no longer discover changes by polling.

  POST /trinity/events      one change, a list of changes, or a GCP Pub/Sub push envelope
  GET  /healthz

Payloads only need to identify the ticket. Accepted shapes (first match wins):
  {"ticket_id": "..."}                                  e.g. a raw timeline event
  {"id": "...", "changedFields": {"status": ...}}       Trinity's planned `ticket.updated` event
  {"event": "ticket.updated", "data": {...}}            Pusher-style wrapper
  {"events": [...]} or [...]                            batches
  {"message": {"data": "<base64 json>"}}                Pub/Sub push subscription

If `changedFields` is present and touches neither status nor assignee, the event is ignored without
calling Trinity. Everything else is resolved by reading the ticket's new timeline events, so the
payload never has to be trusted for what actually happened.

Delivery is assumed to be at-least-once and lossy, so a slow reconciliation sweep (the old poll,
every RECONCILE_MINUTES) still runs as a safety net. Duplicates are harmless.
"""

from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
from datetime import datetime, timezone
from typing import Any, Iterable

from aiohttp import web

from .service import Monitor
from .trinity import connect

log = logging.getLogger(__name__)

RELEVANT_FIELDS = {"status", "assignedTo", "assigned_to", "assignee", "assigned_agent_id"}
BATCH_WINDOW_SECONDS = 2.0


def _unwrap(payload: Any) -> Iterable[dict]:
    if isinstance(payload, list):
        for item in payload:
            yield from _unwrap(item)
        return
    if not isinstance(payload, dict):
        return
    message = payload.get("message")
    if isinstance(message, dict) and "data" in message:  # Pub/Sub push
        try:
            yield from _unwrap(json.loads(base64.b64decode(message["data"])))
        except (ValueError, TypeError):
            log.warning("undecodable Pub/Sub message %s", message.get("messageId"))
        return
    if isinstance(payload.get("events"), list):
        yield from _unwrap(payload["events"])
        return
    if isinstance(payload.get("data"), dict) and "event" in payload:  # Pusher-style
        yield payload["data"]
        return
    yield payload


def extract_ticket_ids(payload: Any) -> list[str]:
    ids: list[str] = []
    for ev in _unwrap(payload):
        tid = ev.get("ticket_id") or ev.get("ticketId") or ev.get("id")
        if not isinstance(tid, str) or not tid:
            continue
        changed = ev.get("changedFields", ev.get("changed_fields"))
        if isinstance(changed, dict) and not RELEVANT_FIELDS & changed.keys():
            continue
        if tid not in ids:
            ids.append(tid)
    return ids


class EventService:
    def __init__(self, monitor: Monitor, token: str | None, reconcile_minutes: int, due_tick_seconds: int):
        self.monitor = monitor
        self.cfg = monitor.cfg
        self.token = token
        self.reconcile_seconds = reconcile_minutes * 60
        self.due_tick_seconds = due_tick_seconds
        self.queue: asyncio.Queue[str] = asyncio.Queue()

    # --- HTTP --------------------------------------------------------------------------------

    def _authorized(self, request: web.Request) -> bool:
        if not self.token:
            return True
        # Header for direct webhooks; query parameter for Pub/Sub push, which cannot set headers.
        supplied = request.headers.get("X-Webhook-Token") or request.query.get("token") or ""
        return hmac.compare_digest(supplied, self.token)

    async def handle_event(self, request: web.Request) -> web.Response:
        if not self._authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            payload = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "invalid json"}, status=400)
        ids = extract_ticket_ids(payload)
        for tid in ids:
            self.queue.put_nowait(tid)
        # 2xx even when nothing is relevant, so the sender does not retry.
        return web.json_response({"queued": ids}, status=202)

    async def handle_health(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "queued": self.queue.qsize()})

    def app(self) -> web.Application:
        app = web.Application(client_max_size=1024 * 1024)
        app.router.add_post("/trinity/events", self.handle_event)
        app.router.add_get("/healthz", self.handle_health)
        return app

    # --- workers ------------------------------------------------------------------------------

    async def ingest_worker(self) -> None:
        """Turns queued ticket ids into scheduled checks. Bursts are batched into one connection."""
        since = self.monitor.started_at()
        while True:
            batch = {await self.queue.get()}
            await asyncio.sleep(BATCH_WINDOW_SECONDS)
            while not self.queue.empty():
                batch.add(self.queue.get_nowait())
            try:
                async with connect(self.cfg.trinity_url, self.cfg.trinity_headers) as trinity:
                    for tid in batch:
                        n = await self.monitor.ingest_ticket(trinity, tid, since)
                        if n:
                            log.info("ticket %s: scheduled %d check(s) from push event", tid, n)
            except Exception:
                # The reconciliation sweep will pick these tickets up; no need to retry here.
                log.exception("ingest failed for %d ticket(s)", len(batch))

    async def due_worker(self) -> None:
        """Runs checks whose grace period has ended. Only touches Trinity when something is due."""
        store = self.monitor.store
        while True:
            if store.due_checks(datetime.now(timezone.utc)):
                try:
                    async with connect(self.cfg.trinity_url, self.cfg.trinity_headers) as trinity:
                        await self.monitor.run_due(trinity)
                    self.monitor.cycle_ok()
                except Exception as e:
                    self.monitor.cycle_failed(f"{type(e).__name__}: {e}")
                    log.exception("running due checks failed")
                    self.monitor.trace("error", f"Running due checks failed: {type(e).__name__}: {e}"[:500],
                                       outcome="error")
            self.monitor.heartbeat()  # this loop ticks every few seconds: the liveness signal in serve mode
            await asyncio.sleep(self.due_tick_seconds)

    async def reconcile_worker(self) -> None:
        """Safety net for lost or never-sent events: the original poll, run rarely."""
        while True:
            try:
                async with connect(self.cfg.trinity_url, self.cfg.trinity_headers) as trinity:
                    await self.monitor.discover(trinity)
                self.monitor.cycle_ok()
            except Exception as e:
                self.monitor.cycle_failed(f"{type(e).__name__}: {e}")
                log.exception("reconciliation sweep failed")
                self.monitor.trace("error", f"Reconciliation sweep failed: {type(e).__name__}: {e}"[:500],
                                   outcome="error")
            await asyncio.sleep(self.reconcile_seconds)

    async def shift_worker(self) -> None:
        """Rules 4-5 run on the clock, not on ticket events: once a minute."""
        if self.monitor.shift_checks is None:
            return
        while True:
            try:
                async with connect(self.cfg.trinity_url, self.cfg.trinity_headers) as trinity:
                    await self.monitor.shift_checks.run(trinity, datetime.now(timezone.utc))
                self.monitor.cycle_ok()
            except Exception as e:
                self.monitor.cycle_failed(f"{type(e).__name__}: {e}")
                log.exception("shift checks failed")
                self.monitor.trace("error", f"Shift checks failed: {type(e).__name__}: {e}"[:500], outcome="error")
            await asyncio.sleep(60)

    async def serve(self, host: str, port: int) -> None:
        runner = web.AppRunner(self.app())
        await runner.setup()
        await web.TCPSite(runner, host, port).start()
        log.info(
            "listening on http://%s:%d/trinity/events; reconciliation every %d min; dry_run=%s",
            host, port, self.reconcile_seconds // 60, self.monitor.notifier.dry_run,
        )
        if not self.token:
            log.warning("WEBHOOK_TOKEN is not set: the endpoint accepts unauthenticated requests")
        self.monitor.announce("serve")
        await asyncio.gather(self.ingest_worker(), self.due_worker(), self.reconcile_worker(), self.shift_worker())
