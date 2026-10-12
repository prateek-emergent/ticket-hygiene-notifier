"""Down alert (notifier/watchdog.py): one DM to one person when the notifier stops or keeps failing."""

import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from notifier.service import Monitor
from notifier.store import Store
from notifier.watchdog import Watchdog

T0 = datetime(2026, 10, 12, 6, 0, tzinfo=timezone.utc)
DOWN = {"dm": "owner@emergent.sh", "after_minutes": 10, "remind_every_minutes": 60}


class FakeSlack:
    dry_run = False

    def __init__(self):
        self.dms, self.fail = [], False

    async def user_id(self, email):
        return "U_OWNER"

    async def dm(self, email, text, blocks):
        if self.fail:
            raise OSError("network down")
        self.dms.append((email, text))


def make(tmp_path, **down):
    store, slack = Store(tmp_path / "state.db"), FakeSlack()
    return store, slack, Watchdog(store, slack, DOWN | down, ZoneInfo("Asia/Kolkata"), started=T0)


def tick(w, minutes):
    return asyncio.run(w.tick(T0 + timedelta(minutes=minutes)))


def test_stopped_notifier_dms_the_owner_once_then_reminds_then_says_back(tmp_path):
    store, slack, w = make(tmp_path)
    store.put("heartbeat", T0.isoformat())
    assert tick(w, 5) is None  # within the grace period
    assert "is down" in tick(w, 11) and slack.dms[-1][0] == "owner@emergent.sh"
    assert tick(w, 30) is None  # no repeat before the reminder interval
    assert "Still down" in tick(w, 72)
    store.put("heartbeat", (T0 + timedelta(minutes=80)).isoformat())
    assert "is back" in tick(w, 81)
    assert tick(w, 82) is None and len(slack.dms) == 3  # only ever DMs, only the owner


def test_running_but_failing_every_cycle_is_reported(tmp_path):
    store, slack, w = make(tmp_path)
    m = Monitor.__new__(Monitor)
    m.store = store
    m.cycle_failed("ConnectError: Trinity unreachable")
    store.put("failing_since", T0.isoformat())
    store.put("heartbeat", (T0 + timedelta(minutes=12)).isoformat())  # alive, beating
    text = tick(w, 12)
    assert "every check is failing" in text and "Trinity unreachable" in text
    m.cycle_ok()  # one good cycle ends the streak
    assert "is back" in tick(w, 13)


def test_a_notifier_that_never_starts_is_reported(tmp_path):
    _, _, w = make(tmp_path)
    assert tick(w, 9) is None
    assert "has not started" in tick(w, 10)


def test_a_failed_dm_is_retried_next_tick_and_restarts_dont_repeat(tmp_path):
    store, slack, w = make(tmp_path, remind_every_minutes=0)
    store.put("heartbeat", T0.isoformat())
    slack.fail = True
    assert tick(w, 11) is None and not slack.dms
    slack.fail = False
    assert "is down" in tick(w, 12)
    w2 = Watchdog(store, slack, DOWN | {"remind_every_minutes": 0}, ZoneInfo("Asia/Kolkata"), started=T0)
    assert asyncio.run(w2.tick(T0 + timedelta(minutes=200))) is None  # same problem, already reported
