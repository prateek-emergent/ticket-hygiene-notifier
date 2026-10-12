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
