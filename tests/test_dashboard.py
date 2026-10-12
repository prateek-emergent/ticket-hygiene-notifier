"""Dashboard API: sign-in gate, allow-list, feedback, and the data views, on a state.db written by the monitor."""

import asyncio
import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from dashboard.__main__ import build
from dashboard.app import Settings
from dashboard.auth import GoogleVerifier

from .factory import Timeline
from .test_service import KRISHNA, LEAD, FakeClassifier, FakeTrinity, make_monitor

H = {"X-Requested-With": "dashboard"}


def _state(tmp_path):
    """A state.db holding one flagged PENDING check (with its trace)."""
    tl = (Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA)
          .reply(2, KRISHNA, "<p>Your deploy is fixed.</p>").status(2.1, "OPEN", "PENDING", KRISHNA))
    monitor, _ = make_monitor(tmp_path, FakeClassifier(awaiting=False))
    trinity = FakeTrinity({"tk": tl})
    monitor.announce("test")
    asyncio.run(monitor.discover(trinity))
    asyncio.run(monitor.run_due(trinity))
    return monitor.cfg.state_db


def _files(tmp_path, allowed=(LEAD,)):
    teams = tmp_path / "teams.yaml"
    teams.write_text(json.dumps({"teams": [{"name": "Lead's team", "associates": [LEAD], "engineers": [KRISHNA]}],
                                 "names": {KRISHNA: "Krishna R", LEAD: "Lead Person"}}), encoding="utf-8")
    users = tmp_path / "users.yaml"
    users.write_text(json.dumps({"allowed": list(allowed)}), encoding="utf-8")
    return teams, users


def run_client(tmp_path, scenario, *, dev=True, client_id=None, allowed=(LEAD,)):
    db = _state(tmp_path)
    teams, users = _files(tmp_path, allowed)
    app = build(db, teams, users, Settings(client_id, dev, 12, "127.0.0.1"))

    async def go():
        async with TestClient(TestServer(app)) as client:
            return await scenario(client, users)

    return asyncio.run(go())


async def _login(client, email=LEAD):
    return await client.post("/api/auth/dev", json={"email": email}, headers=H)


def test_everything_needs_sign_in_and_forged_posts_are_refused(tmp_path):
    async def scenario(client, _):
        assert (await client.get("/api/overview")).status == 401
        assert (await client.get("/api/alerts")).status == 401
        assert (await client.get("/api/stream")).status == 401
        assert (await client.post("/api/auth/dev", json={"email": LEAD})).status == 403  # no custom header
        public = await (await client.get("/api/public")).json()
        assert public == {"google_client_id": None, "dev_login": True}

    run_client(tmp_path, scenario)


def test_dev_sign_in_only_for_listed_emails_and_only_when_enabled(tmp_path):
    async def scenario(client, _):
        assert (await _login(client, "stranger@emergent.sh")).status == 403
        r = await _login(client)
        assert r.status == 200
        me = await r.json()
        assert me["email"] == LEAD and me["teams"] == ["Lead's team"] and me["name"] == "Lead Person"
        assert (await client.get("/api/me")).status == 200
        await client.post("/api/auth/logout", headers=H)
        assert (await client.get("/api/me")).status == 401

    run_client(tmp_path, scenario)

    async def disabled(client, _):
        assert (await _login(client)).status == 404

    (tmp_path / "off").mkdir()
    run_client(tmp_path / "off", disabled, dev=False)


def test_removing_someone_from_the_list_ends_their_session(tmp_path):
    async def scenario(client, users):
        await _login(client)
        assert (await client.get("/api/me")).status == 200
        import os
        import time
        users.write_text(json.dumps({"allowed": []}), encoding="utf-8")
        os.utime(users, (time.time() + 5, time.time() + 5))  # make sure the change is seen
        assert (await client.get("/api/me")).status == 401

    run_client(tmp_path, scenario)


def test_google_sign_in_checks_the_list(tmp_path, monkeypatch):
    async def fake_verify(self, credential):
        if credential == "bad":
            raise ValueError("bad signature")
        return {"iss": "accounts.google.com", "email": credential, "email_verified": True, "name": "G User"}

    monkeypatch.setattr(GoogleVerifier, "verify", fake_verify)

    async def scenario(client, _):
        assert (await client.post("/api/auth/google", json={"credential": "bad"}, headers=H)).status == 401
        r = await client.post("/api/auth/google", json={"credential": "stranger@gmail.com"}, headers=H)
        assert r.status == 403 and "access list" in (await r.json())["error"]
        r = await client.post("/api/auth/google", json={"credential": LEAD}, headers=H)
        assert r.status == 200 and (await r.json())["name"] == "G User"
        cookie = r.headers["Set-Cookie"]
        assert "HttpOnly" in cookie and "SameSite=Lax" in cookie

    run_client(tmp_path, scenario, dev=False, client_id="cid")


def test_views_feedback_and_ticket_trace(tmp_path):
    async def scenario(client, _):
        await _login(client)
        ov = await (await client.get("/api/overview?hours=24")).json()
        assert ov["totals"]["alerts"] == 1 and ov["totals"]["unreviewed"] == 1
        assert ov["models"]["calls"] == 1
        assert (await (await client.get("/api/overview?team=Other")).json())["totals"]["alerts"] == 0

        alerts = (await (await client.get("/api/alerts")).json())["items"]
        assert len(alerts) == 1 and alerts[0]["engineer_name"] == "Krishna R" and alerts[0]["team"] == "Lead's team"
        aid = alerts[0]["id"]
        detail = await (await client.get(f"/api/alerts/{aid}")).json()
        assert [t["kind"] for t in detail["trace"]] == ["scheduled", "model", "alert", "check"]

        r = await client.post(f"/api/alerts/{aid}/feedback", json={"verdict": "maybe"}, headers=H)
        assert r.status == 400
        r = await client.post(f"/api/alerts/{aid}/feedback", json={"verdict": "false_alarm", "note": "asked on call"},
                              headers=H)
        a = await r.json()
        assert a["review"]["verdict"] == "false_alarm" and a["review"]["by"] == LEAD
        assert (await (await client.get("/api/alerts?review=unreviewed")).json())["items"] == []
        assert (await (await client.get("/api/alerts?q=krishna")).json())["items"][0]["id"] == aid

        t = await (await client.get("/api/tickets/tk")).json()
        assert t["alerts"][0]["id"] == aid and t["checks"][0]["engineer"] == KRISHNA
        assert (await client.get("/api/tickets/nope")).status == 404

        eng = await (await client.get("/api/engineers")).json()
        assert eng[0]["email"] == KRISHNA and eng[0]["alerts"] == 1 and eng[0]["false_alarms"] == 1

        st = await (await client.get("/api/status")).json()
        assert st["live"] is True and st["info"]["mode"] == "test"

    run_client(tmp_path, scenario)


def test_stream_sends_status_then_new_activity(tmp_path):
    async def scenario(client, _):
        await _login(client)
        r = await client.get("/api/stream?after=0")
        assert r.headers["Content-Type"].startswith("text/event-stream")
        seen = ""
        while "event: activity" not in seen:
            seen += (await asyncio.wait_for(r.content.readany(), 5)).decode()
        assert seen.startswith("event: status")
        r.close()

    run_client(tmp_path, scenario)


@pytest.mark.parametrize("path", ["/", "/alerts/3", "/tickets/abc"])
def test_ui_routes_serve_the_app_or_a_build_hint(tmp_path, path):
    async def scenario(client, _):
        r = await client.get(path)
        assert r.status == 200 and "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]

    run_client(tmp_path, scenario)
