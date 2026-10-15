"""dashboard/shiftviews.py: the Shifts page (R1, R6, R7), reports and scorecard (R8, R9), "Run check now" (E2)."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from aiohttp.test_utils import TestClient, TestServer

from dashboard.__main__ import build
from dashboard.app import Settings
from dashboard.queries import MongoData, SqliteData
from dashboard.shiftviews import ShiftViews
from notifier.detectors import Rule
from notifier.store import MongoStore, Store

A, B, LEAD = "a@emergent.sh", "b@emergent.sh", "lead@emergent.sh"
EXPO = "zeel@emergent.sh"  # roster-only team
TEAMS = [{"name": "Lead's team", "associates": [LEAD], "engineers": [A, B]}]
NAMES = {A: "Asha A", B: "Bala B"}
URL = "https://trinity.example/tickets/{id}"
H = {"X-Requested-With": "dashboard"}


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def _roster_grid(path, people, now):
    """A roster file in the team-sheet layout, with today's and yesterday's cells."""
    days = [now - timedelta(days=1), now]
    head = ["Agent", "Email", "Role", "Fixed Weekly Off"] + [f"{d.day}-{d:%b} : {d:%a}" for d in days]
    rows = [["6A-3P SHIFT (L2)"], head] + [[name, email, "Agent", "Sunday", *cells] for name, email, cells in people]
    path.write_text("\n".join(",".join(r) for r in rows), encoding="utf-8")
    return path


def _shifts_file(path, now):
    """Long format, UTC: A worked until 1 h ago (off shift now); B is on shift now."""
    today = now.date().isoformat()
    path.write_text("email,day,start,end\n"
                    f"{A},{today},{(now - timedelta(hours=9)):%H:%M},{(now - timedelta(hours=1)):%H:%M}\n"
                    f"{B},{today},{(now - timedelta(hours=2)):%H:%M},{(now + timedelta(hours=6)):%H:%M}\n",
                    encoding="utf-8")
    return path


def make(tmp_path, backend, now):
    if backend == "sqlite":
        store, data = Store(tmp_path / "s.db"), SqliteData(tmp_path / "s.db", TEAMS, NAMES)
    else:
        import mongomock
        db = mongomock.MongoClient()["t"]
        store, data = MongoStore(db=db), MongoData(TEAMS, NAMES, db=db)
    expo = _roster_grid(tmp_path / "expo.csv", [("Zeel B", EXPO, ["Off", "6A-3P"])], now)
    views = ShiftViews(store, data, shifts_file=_shifts_file(tmp_path / "shifts.csv", now), tz="UTC",
                       roster_views=[{"name": "L2 Full Stack", "file": str(expo), "associates": []},
                                     {"name": "L2 Expo", "file": str(expo), "associates": ["nikhita@emergent.sh"]}],
                       ticket_url=URL)
    return store, data, views


def _alert(store, rule, key, engineer, payload, ticket="t1", num=1):
    store.record_alert(rule, key, ticket, engineer, payload, ticket_num=num, subject="Deploy broken",
                       url=URL.format(id=ticket) if ticket else None)


BACKENDS = ["sqlite", "mongo"]


@pytest.mark.parametrize("backend", BACKENDS)
def test_shifts_page_lists_still_online_and_off_shift_engineers_with_their_tickets(tmp_path, backend):
    now = _now()
    store, _, views = make(tmp_path, backend, now)
    end = (now - timedelta(minutes=50)).isoformat()
    store.add_shift_record({"key": f"{A}|{end}", "email": A, "shift_start": (now - timedelta(hours=9)).isoformat(),
                            "shift_end": end, "status_at_end": "ONLINE", "outcome": "open", "offline_at": None,
                            "online_minutes": None})
    store.put_presences({A: "ONLINE", B: "ONLINE"})
    store.put_open_tickets(A, [{"ticket_id": "t1", "num": 11, "subject": "One", "level": "L2"}])
    store.put_open_tickets(B, [{"ticket_id": "t2", "num": 12, "subject": "Two", "level": "L2"}])

    page = views.shifts(now, user=LEAD)
    (row,) = page["still_online"]
    assert row["email"] == A and row["online_minutes"] == 50 and row["alerted"]
    assert row["open_tickets"][0]["url"] == URL.format(id="t1")
    # A is listed once, under still Online (with the ticket); B is on shift, so not listed.
    assert page["off_shift_with_tickets"] == []
    assert views.shifts(now, team="Someone else's team")["still_online"] == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_still_online_engineers_are_not_listed_again_as_off_shift_with_tickets(tmp_path, backend):
    now = _now()
    store, _, views = make(tmp_path, backend, now)
    end = (now - timedelta(minutes=50)).isoformat()
    store.add_shift_record({"key": f"{A}|{end}", "email": A, "shift_start": (now - timedelta(hours=9)).isoformat(),
                            "shift_end": end, "status_at_end": "ONLINE", "outcome": "open", "offline_at": None,
                            "online_minutes": None})
    store.put_open_tickets(A, [{"ticket_id": "t1", "num": 11, "subject": "One", "level": "L2"}])
    page = views.shifts(now)
    assert [r["email"] for r in page["still_online"]] == [A] and page["off_shift_with_tickets"] == []


@pytest.mark.parametrize("backend", BACKENDS)
def test_expo_roster_is_view_only_and_its_associate_sees_it_first(tmp_path, backend):
    now = _now()
    store, _, views = make(tmp_path, backend, now)
    store.put_presences({EXPO: "ONLINE"})  # even if present in the copy, never shown for a roster-only team
    roster = views.shifts(now, user="nikhita@emergent.sh")["roster"]
    assert roster["name"] == "L2 Expo" and roster["views"] == ["L2 Full Stack", "L2 Expo"] and roster["roster_only"]
    (p,) = roster["people"]
    assert p["email"] == EXPO and p["code"] == "6A-3P" and not p["monitored"] and p["presence"] is None
    assert views.shifts(now, user=LEAD)["roster"]["name"] == "L2 Full Stack"
    assert views.shifts(now, roster="L2 Expo", user=LEAD)["roster"]["name"] == "L2 Expo"


@pytest.mark.parametrize("backend", BACKENDS)
def test_reports_and_scorecard_count_only_alerts_not_marked_false_alarm(tmp_path, backend):
    now = _now()
    store, data, views = make(tmp_path, backend, now)
    end = (now - timedelta(hours=3)).isoformat()
    for i in range(3):  # three un-assignments without a note: needs attention, and a heavy day
        _alert(store, Rule.HELD_THEN_DROPPED.value, f"u{i}", A, {"details": {"left_note": False, "held_minutes": 40}},
               ticket=f"t{i}", num=i)
    _alert(store, Rule.HELD_THEN_DROPPED.value, "u-note", B, {"details": {"left_note": True}}, ticket="t9", num=9)
    _alert(store, Rule.STATUS_SHIFT.value, f"{B}|end|{end}", B, {"kind": "end", "presence": "ONLINE"}, ticket="")
    _alert(store, Rule.NO_REPLY.value, "nr", B, {"details": {}}, ticket="t9", num=9)  # t9 flagged twice
    _alert(store, Rule.NO_REPLY.value, "nr-fa", B, {"details": {}}, ticket="t8", num=8)
    fa = next(a["id"] for a in data.alerts(limit=50)["items"] if a["ticket_id"] == "t8")
    data.add_feedback(fa, "false_alarm", None, LEAD)

    rep = views.reports(now)
    eng = {e["email"]: e for e in rep["engineers"]}
    assert eng[A]["unassign_without_note"] == 3 and eng[A]["alerts"] == 3
    assert eng[B]["unassign_with_note"] == 1 and eng[B]["offline_violations"] == 1 and eng[B]["false_alarms"] == 1
    assert eng[B]["by_rule"].get(Rule.NO_REPLY.value) == 1  # the false alarm isn't counted
    assert {(h["email"], h["count"]) for h in rep["heavy_days"]} == {(A, 3), (B, 3)}  # B: 4 today, 1 false alarm
    assert [(r["ticket_id"], r["count"]) for r in rep["repeated_tickets"]] == [("t9", 2)]

    card = {c["email"]: c for c in rep["scorecard"]}
    assert card[A]["rating"] == "needs_attention" and card[A]["score"] == 3 * 2 + 5  # + pattern (heavy day)
    # B: offline x3 + with-note x1, and t9 flagged twice for B is a pattern (+5).
    assert card[B]["score"] == 3 + 1 + 5 and card[B]["rating"] == "needs_attention"

    daily = rep["daily"]
    assert [x["email"] for x in daily["unassigned_without_note"]] == [A, A, A]
    assert [x["email"] for x in daily["didnt_go_offline"]] == [B]  # from the theme 4 alert (no shift record)
    assert {p["email"] for p in daily["patterns"]} == {A, B}


@pytest.mark.parametrize("backend", BACKENDS)
def test_report_range_is_capped_at_90_days(tmp_path, backend):
    now = _now()
    _, _, views = make(tmp_path, backend, now)
    rep = views.reports(now, start=now.date() - timedelta(days=400))
    assert (datetime.fromisoformat(rep["to"]) - datetime.fromisoformat(rep["from"])).days == 89


@pytest.mark.parametrize("backend", BACKENDS)
def test_run_check_now_is_picked_up_by_the_notifier_once(tmp_path, backend):
    from types import SimpleNamespace

    from notifier.service import Monitor

    now = _now()
    store, _, views = make(tmp_path, backend, now)
    state, ok = views.request_run(LEAD, now)
    assert ok and state["pending"] and state["by"] == LEAD
    assert views.request_run(LEAD, now + timedelta(seconds=5))[1] is False  # once a minute

    monitor = SimpleNamespace(store=store, trace=lambda *a, **k: None)
    asked = Monitor.run_requested(monitor)
    assert asked["by"] == LEAD
    Monitor.run_finished(monitor, asked, "ok")
    assert Monitor.run_requested(monitor) is None
    after = views.run_state()
    assert not after["pending"] and after["result"] == "ok"


def test_api_shifts_reports_and_run_check(tmp_path):
    now = _now()
    db = tmp_path / "s.db"
    Store(db)
    teams = tmp_path / "teams.yaml"
    teams.write_text(json.dumps({"teams": TEAMS, "names": NAMES}), encoding="utf-8")
    users = tmp_path / "users.yaml"
    users.write_text(json.dumps({"allowed": [LEAD]}), encoding="utf-8")
    expo = _roster_grid(tmp_path / "expo.csv", [("Zeel B", EXPO, ["Off", "6A-3P"])], now)
    rc = SimpleRC(str(_shifts_file(tmp_path / "shifts.csv", now)), str(expo))
    app = build(db, teams, users, Settings(None, True, 12, "127.0.0.1"), rules_config=rc)

    async def go():
        async with TestClient(TestServer(app)) as client:
            assert (await client.get("/api/shifts")).status == 401
            assert (await client.post("/api/checks/run", headers=H)).status == 401
            await client.post("/api/auth/dev", json={"email": LEAD}, headers=H)
            page = await (await client.get("/api/shifts?roster=L2%20Expo")).json()
            assert page["roster"]["name"] == "L2 Expo" and page["run_check"]["pending"] is False
            rep = await (await client.get("/api/reports?from=2000-01-01&day=bad")).json()
            assert {e["email"] for e in rep["scorecard"]} == {A, B}
            assert (await client.post("/api/checks/run")).status == 403  # no custom header: forged post
            r = await client.post("/api/checks/run", headers=H)
            assert r.status == 202 and (await r.json())["pending"]
            assert (await client.post("/api/checks/run", headers=H)).status == 429

    asyncio.run(go())


class SimpleRC:
    def __init__(self, shifts, expo):
        self.SHIFTS = {"file": shifts, "timezone": "UTC"}
        self.ROSTER_VIEWS = [{"name": "L2 Full Stack", "file": shifts}, {"name": "L2 Expo", "file": expo}]
