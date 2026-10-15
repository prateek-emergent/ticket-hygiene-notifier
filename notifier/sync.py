"""A copy of Trinity data in our database, so dashboard views and checks don't have to ask Trinity each time.

Read-only on Trinity. Refreshed from the notifier's cycle (so, with the lease, by exactly one copy of the app):
  * presence: every monitored engineer's Trinity status, every PRESENCE_EVERY;
  * open tickets: every monitored engineer's OPEN tickets, every TICKETS_EVERY.
Only monitored engineers (config/teams.yaml) are synced; the L2 Expo team is roster-only and never included.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from .trinity import Trinity

log = logging.getLogger(__name__)

PRESENCE_EVERY = timedelta(seconds=55)  # just under the 60 s cycle, so it runs every cycle
TICKETS_EVERY = timedelta(minutes=5)
TICKET_CONCURRENCY = 6


class TrinitySync:
    def __init__(self, monitor):
        self.monitor = monitor
        self._presence_at: datetime | None = None
        self._tickets_at: datetime | None = None

    async def run(self, trinity: Trinity, now: datetime, force: bool = False) -> dict[str, int]:
        """Refresh whatever is due (everything when `force`). Returns what was refreshed, for logging."""
        store, engineers = self.monitor.store, self.monitor.directory.engineers
        done: dict[str, int] = {}
        if store is None or not engineers:
            return done
        if force or self._presence_at is None or now - self._presence_at >= PRESENCE_EVERY:
            presences = await trinity.presences(engineers)
            store.put_presences(presences)
            self._presence_at = now
            done["presence"] = len(presences)
        if force or self._tickets_at is None or now - self._tickets_at >= TICKETS_EVERY:
            sem = asyncio.Semaphore(TICKET_CONCURRENCY)

            async def one(email: str) -> int:
                async with sem:
                    tickets = await trinity.open_tickets(email)
                store.put_open_tickets(email, [{"ticket_id": t.id, "num": t.num, "subject": t.subject,
                                                "level": t.level} for t in tickets])
                return len(tickets)

            counts = await asyncio.gather(*(one(e) for e in engineers))
            self._tickets_at = now
            done["open_tickets"] = sum(counts)
            store.put("synced_open_tickets_at", now.isoformat())
            log.info("synced %d open tickets for %d engineers", sum(counts), len(engineers))
        if "presence" in done:
            store.put("synced_presence_at", now.isoformat())
        return done
