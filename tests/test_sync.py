"""notifier/sync.py: the copy of Trinity presence and open tickets, and Trinity.presences()."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from notifier.models import Ticket
from notifier.store import Store
from notifier.sync import TrinitySync
from notifier.teams import Directory, Team
from notifier.trinity import Trinity

T0 = datetime(2026, 10, 15, 6, 0, tzinfo=timezone.utc)
A, B = "a@emergent.sh", "b@emergent.sh"
EXPO = "zeel@emergent.sh"  # roster-only team: must never be synced


class FakeTrinity:
    def __init__(self):
        self.presence = {A: "ONLINE", B: "OFFLINE", EXPO: "ONLINE"}
        self.open = {A: [Ticket.from_api({"id": "t1", "num": 1, "subject": "One", "level": "L2"})], B: []}
        self.presence_calls = self.ticket_calls = 0

    async def presences(self, emails):
        self.presence_calls += 1
        return {e: self.presence.get(e) for e in emails}

    async def open_tickets(self, email):
        self.ticket_calls += 1
        return self.open.get(email, [])


def make(tmp_path, backend):
    if backend == "sqlite":
        store = Store(tmp_path / "s.db")
    else:
        import mongomock
        from notifier.store import MongoStore
        store = MongoStore(db=mongomock.MongoClient()["t"])
    monitor = SimpleNamespace(store=store, directory=Directory([Team("T", ["lead@emergent.sh"], [A, B])]))
    return store, TrinitySync(monitor)


@pytest.mark.parametrize("backend", ["sqlite", "mongo"])
def test_sync_refreshes_presence_each_cycle_and_tickets_every_5_min(tmp_path, backend):
    store, sync = make(tmp_path, backend)
    trinity = FakeTrinity()
    asyncio.run(sync.run(trinity, T0))
    assert store.presences()[A][0] == "ONLINE" and store.presences()[B][0] == "OFFLINE"
    assert [t["ticket_id"] for t in store.open_tickets(A)] == ["t1"]
    assert EXPO not in store.presences()  # Expo is roster-only: never synced
    asyncio.run(sync.run(trinity, T0 + timedelta(minutes=1)))
    assert trinity.presence_calls == 2 and trinity.ticket_calls == 2  # tickets not refreshed yet (2 engineers once)
    trinity.open[A] = []  # t1 closed or reassigned
    asyncio.run(sync.run(trinity, T0 + timedelta(minutes=5)))
    assert store.open_tickets(A) == []
    assert store.get("synced_open_tickets_at") and store.get("synced_presence_at")


def test_presences_uses_one_bulk_call_then_looks_up_only_the_missing(monkeypatch):
    calls = []

    class FakeSession:
        pass

    t = Trinity(FakeSession())

    async def fake_call(tool, args):
        calls.append(args)
        if "query" not in args:  # the bulk call (Trinity caps it at 200 agents)
            return [{"email": "A@emergent.sh", "presence": "online"}]
        return [{"email": args["query"], "presence": "OFFLINE", "first_name": "B"}]

    monkeypatch.setattr(t, "_call", fake_call)
    got = asyncio.run(t.presences([A, B]))
    assert got == {A: "ONLINE", B: "OFFLINE"}
    assert len(calls) == 2  # one bulk + one lookup for B
