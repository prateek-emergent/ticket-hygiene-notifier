"""Release 2 (PRD_shift_guardian.md P1): CSV export, "Mark actioned", week grid and per-associate cards."""

import asyncio
import csv
import io
import json
from datetime import timedelta

import pytest
from aiohttp.test_utils import TestClient, TestServer

from dashboard.__main__ import build
from dashboard.app import Settings
from notifier.detectors import Rule
from notifier.store import Store

from .test_shiftviews import (A, B, BACKENDS, EXPO, LEAD, NAMES, TEAMS, URL, H, SimpleRC, _alert, _now,
                              _roster_grid, _shifts_file, make)


def _rows(text):
    return list(csv.reader(io.StringIO(text)))


@pytest.mark.parametrize("backend", BACKENDS)
def test_mark_actioned_is_recorded_in_our_app_and_shown_on_the_row(tmp_path, backend):
    now = _now()
    store, data, views = make(tmp_path, backend, now)
    store.put_open_tickets(A, [{"ticket_id": "t1", "num": 11, "subject": "One", "level": "L2"}])
    assert views.shifts(now)["off_shift_with_tickets"][0]["action"] is None

    a = data.add_action(A, "off_shift", [{"ticket_id": "t1", "num": 11}], "  reassigned to Bala  ", LEAD)
    assert a["note"] == "reassigned to Bala" and a["by"] == LEAD and a["tickets"] == [{"ticket_id": "t1", "num": 11}]
    page = views.shifts(now)
    assert page["off_shift_with_tickets"][0]["action"]["id"] == a["id"]
    assert [x["engineer"] for x in page["actions"]] == [A]

    with pytest.raises(ValueError):  # Expo (roster-only) and unknown people can't be actioned
        data.add_action(EXPO, "off_shift", [], "x", LEAD)
    with pytest.raises(ValueError):
        data.add_action(A, "reassign_in_trinity", [], "x", LEAD)


@pytest.mark.parametrize("backend", BACKENDS)
def test_an_action_from_before_the_shift_ended_does_not_count(tmp_path, backend):
    now = _now()
    store, data, views = make(tmp_path, backend, now)
    data.add_action(A, "still_online", [], "told them", LEAD)
    end = (now + timedelta(minutes=1)).isoformat()  # a later shift end than the action
    store.add_shift_record({"key": f"{A}|{end}", "email": A, "shift_start": now.isoformat(), "shift_end": end,
                            "status_at_end": "ONLINE", "outcome": "open", "offline_at": None, "online_minutes": None})
    assert views.shifts(now + timedelta(minutes=5))["still_online"][0]["action"] is None


@pytest.mark.parametrize("backend", BACKENDS)
def test_team_cards_count_who_is_on_shift_and_not_online(tmp_path, backend):
    now = _now()
    store, _, views = make(tmp_path, backend, now)
    store.put_presences({A: "ONLINE", B: "OFFLINE"})  # B is on shift (see _shifts_file) but Offline
    store.put_open_tickets(A, [{"ticket_id": "t1", "num": 11}])
    _alert(store, Rule.NO_REPLY.value, "nr", B, {"details": {}})
    (card,) = views.shifts(now)["teams"]
    assert card["engineers"] == 2 and card["on_shift"] == 1 and card["online"] == 1
    assert [p["email"] for p in card["on_shift_not_online"]] == [B]
    assert card["off_shift_with_tickets"] == 1 and card["open_tickets"] == 1 and card["alerts_today"] == 1


@pytest.mark.parametrize("backend", BACKENDS)
def test_week_grid_shows_the_roster_as_written(tmp_path, backend):
    now = _now()
    _, _, views = make(tmp_path, backend, now)
    week = views.week(now, "L2 Expo", start=(now - timedelta(days=1)).date())
    assert week["name"] == "L2 Expo" and len(week["days"]) == 7 and week["roster_only"]
    (p,) = week["people"]
    assert p["email"] == EXPO and [c["code"] for c in p["cells"][:2]] == ["Off", "6A-3P"]
    assert p["cells"][2]["kind"] == "none"  # beyond the file: not on the roster


@pytest.mark.parametrize("backend", BACKENDS)
def test_exports_alerts_with_reviews_report_and_actions(tmp_path, backend):
    now = _now()
    store, data, views = make(tmp_path, backend, now)
    _alert(store, Rule.HELD_THEN_DROPPED.value, "u1", A, {"details": {"left_note": False}}, ticket="t1", num=1)
    store.record_alert(Rule.NO_REPLY.value, "nr", "t2", B, {"details": {}}, ticket_num=2, subject="=HYPERLINK(1)")
    fa = next(a["id"] for a in data.alerts(limit=10)["items"] if a["ticket_id"] == "t2")
    data.add_feedback(fa, "false_alarm", "customer had replied by phone", LEAD)
    data.add_action(A, "off_shift", [{"ticket_id": "t1", "num": 1}], "reassigned", LEAD)

    name, text = views.export("alerts", now)
    assert name.startswith("ticket-hygiene_alerts_") and name.endswith(".csv")
    rows = _rows(text)
    assert rows[0][:3] == ["id", "sent_at", "theme"] and len(rows) == 3
    t2 = next(r for r in rows if r[3] == "2")
    assert t2[4] == "'=HYPERLINK(1)"  # a spreadsheet won't run it as a formula
    assert t2[-3:] == ["false_alarm", LEAD, "customer had replied by phone"]

    rev = _rows(views.export("reviews", now)[1])
    assert len(rev) == 2 and rev[1][1] == "false_alarm" and rev[1][8] == B

    rep = {r[1]: r for r in _rows(views.export("report", now)[1])[1:]}
    assert rep[A][6] == "1" and rep[A][3] == "watch"  # one un-assignment without a note
    assert rep[B][-1] == "1"  # B's only alert was a false alarm

    act = _rows(views.export("actions", now)[1])
    assert act[1][2] == A and act[1][5] == "#1" and act[1][6] == "reassigned"

    assert len(_rows(views.export("alerts", now, team="Someone else's team")[1])) == 1  # header only
    with pytest.raises(ValueError):
        views.export("sessions", now)


def test_api_actions_week_and_export(tmp_path):
    now = _now()
    db = tmp_path / "s.db"
    Store(db)
    teams = tmp_path / "teams.yaml"
    teams.write_text(json.dumps({"teams": TEAMS, "names": NAMES}), encoding="utf-8")
    users = tmp_path / "users.yaml"
    users.write_text(json.dumps({"allowed": [LEAD]}), encoding="utf-8")
    expo = _roster_grid(tmp_path / "expo.csv", [("Zeel B", EXPO, ["Off", "6A-3P"])], now)
    app = build(db, teams, users, Settings(None, True, 12, "127.0.0.1"),
                rules_config=SimpleRC(str(_shifts_file(tmp_path / "shifts.csv", now)), str(expo)))
    body = {"engineer": A, "context": "off_shift", "tickets": [{"ticket_id": "t1", "num": 1}], "note": "done"}

    async def go():
        async with TestClient(TestServer(app)) as client:
            assert (await client.get("/api/export/alerts.csv")).status == 401
            assert (await client.post("/api/actions", json=body, headers=H)).status == 401
            await client.post("/api/auth/dev", json={"email": LEAD}, headers=H)
            assert (await client.post("/api/actions", json=body)).status == 403  # forged post
            r = await client.post("/api/actions", json=body, headers=H)
            assert r.status == 200 and (await r.json())["by"] == LEAD
            assert (await client.post("/api/actions", json={**body, "engineer": EXPO}, headers=H)).status == 400
            week = await (await client.get("/api/roster/week?roster=L2%20Expo")).json()
            assert week["people"][0]["email"] == EXPO
            r = await client.get("/api/export/actions.csv")
            assert r.status == 200 and "attachment" in r.headers["Content-Disposition"]
            text = await r.text()
            assert text.lstrip("﻿").startswith("at,engineer") and "done" in text
            assert (await client.get("/api/export/nothing.csv")).status == 404

    asyncio.run(go())
