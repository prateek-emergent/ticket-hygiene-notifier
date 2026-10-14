"""backend/server.py, the Emergent platform entry: where the notifier runs, and what /health says."""

import importlib.util
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def server(monkeypatch):
    cwd = os.getcwd()
    spec = importlib.util.spec_from_file_location("platform_server", ROOT / "backend" / "server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    yield mod
    os.chdir(cwd)


def test_notifier_runs_only_in_the_deployed_app(server, monkeypatch):
    monkeypatch.delenv("RUN_NOTIFIER", raising=False)
    monkeypatch.delenv("MONGO_URL", raising=False)
    assert not server.notifier_enabled()  # preview pod: dashboard only, never a second notifier
    monkeypatch.setenv("MONGO_URL", "mongodb://db")
    assert server.notifier_enabled()  # deployed
    monkeypatch.setenv("RUN_NOTIFIER", "false")
    assert not server.notifier_enabled()
    monkeypatch.delenv("MONGO_URL")
    monkeypatch.setenv("RUN_NOTIFIER", "true")
    assert server.notifier_enabled()


def test_dev_sign_in_is_always_off_behind_the_forwarder(server):
    assert os.environ["DASHBOARD_DEV_LOGIN"] == "false"


def test_health_restarts_only_a_stalled_notifier(server, monkeypatch):
    class Kv:
        def __init__(self, beat):
            self.beat = beat

        def get(self, key):
            return self.beat

    monkeypatch.setenv("RUN_NOTIFIER", "true")
    now = datetime.now(timezone.utc)
    server.State.leader = False
    assert b"standby" in server.health()[1]  # another copy runs the notifier: nothing to restart here
    server.State.leader = True
    server.State.started = time.monotonic()
    assert server.health()[0] == 200  # still starting
    server.State.started = time.monotonic() - 3600
    server.State.store = Kv((now - timedelta(minutes=2)).isoformat())
    assert server.health()[0] == 200
    server.State.store = Kv((now - timedelta(minutes=30)).isoformat())
    assert server.health()[0] == 503
    server.State.store = Kv(None)
    assert server.health()[0] == 503
    monkeypatch.setenv("RUN_NOTIFIER", "false")
    assert server.health()[0] == 200  # dashboard only: nothing to restart for


def test_two_copies_run_one_notifier_and_the_standby_takes_over(server, monkeypatch, tmp_path):
    """The platform runs two copies of the app: only the lease holder runs the notifier; when it stops,
    the other copy takes over."""
    import asyncio

    monkeypatch.setenv("STATE_DB", str(tmp_path / "s.db"))
    monkeypatch.setattr(server, "LEASE_SECONDS", 0.6)
    monkeypatch.setattr(server, "LEASE_RENEW_SECONDS", 0.1)
    running = set()

    async def fake_notifier():
        running.add(asyncio.current_task().get_name())
        try:
            await asyncio.sleep(3600)
        finally:
            running.discard(asyncio.current_task().get_name())

    async def scenario():
        monkeypatch.setattr(server, "keep_running", lambda label, start: fake_notifier()
                            if label == "notifier" else asyncio.sleep(3600))

        async def copy(name):
            await server.lead(me=name)  # each copy of the app has its own identity

        a = asyncio.create_task(copy("copy-a"), name="copy-a")
        await asyncio.sleep(0.05)
        b = asyncio.create_task(copy("copy-b"), name="copy-b")
        await asyncio.sleep(0.5)
        first = len(running)
        a.cancel()  # the leader stops (e.g. its pod is replaced): it releases the lease
        await asyncio.gather(a, return_exceptions=True)
        await asyncio.sleep(0.5)
        second = len(running)
        b.cancel()
        await asyncio.gather(b, return_exceptions=True)
        return first, second

    assert asyncio.run(scenario()) == (1, 1)  # one notifier at a time, and one again after the takeover


def test_trial_reset_needs_both_the_switch_and_the_label(server, monkeypatch, tmp_path):
    from notifier.store import Store
    store = Store(tmp_path / "s.db")
    store.record_alert("r", "k", "", "x@emergent.sh", {})
    monkeypatch.setenv("RESET_TRIAL_DATA", "2026-11-01")
    for switch in ("", "false", "no"):  # label alone: the safety catch holds
        monkeypatch.setenv("RESET_TRIAL", switch)
        server.reset_trial_data_once(store)
        assert store.count_alerts("r") == 1
    monkeypatch.delenv("RESET_TRIAL_DATA")
    monkeypatch.setenv("RESET_TRIAL", "true")  # switch alone: no label, nothing cleared
    server.reset_trial_data_once(store)
    assert store.count_alerts("r") == 1
    monkeypatch.setenv("RESET_TRIAL_DATA", "2026-11-01")  # both: cleared once
    server.reset_trial_data_once(store)
    assert store.count_alerts("r") == 0
