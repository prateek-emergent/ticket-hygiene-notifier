"""Entry point on the Emergent platform.

The platform runs `uvicorn server:app --host 0.0.0.0 --port 8001` in backend/ and puts nginx in front:
/api and /health come here, everything else is the dashboard UI built from frontend/ (a copy of
dashboard/static). This one process runs the whole app as asyncio tasks on uvicorn's event loop:
  * the dashboard (aiohttp) on 127.0.0.1:8090 inside this process; every request is forwarded to it;
  * the notifier and the down-alert watchdog, only where they should run (notifier_enabled()).
When uvicorn stops or reloads, the tasks stop with the process, so a stray second notifier can't survive.
Elsewhere (a laptop, Docker) the app runs as before: docker/start.sh, python -m notifier / dashboard.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # config.py, config/, kb/ and data/ are found relative to the project root

import aiohttp  # noqa: E402
from aiohttp import web  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
# Behind this forwarder every request reaches the dashboard from 127.0.0.1, which is exactly what its
# "local sign-in" (no Google) trusts. Never allow it here.
os.environ["DASHBOARD_DEV_LOGIN"] = "false"

from dashboard.__main__ import build as build_dashboard  # noqa: E402
from dashboard.app import Settings  # noqa: E402
from notifier.__main__ import build_monitor, check_classifier  # noqa: E402
from notifier.config import Config, load_rules_config  # noqa: E402
from notifier.store import Store  # noqa: E402
from notifier.watchdog import build_watchdog  # noqa: E402

log = logging.getLogger("server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
for noisy in ("httpx", "httpx2", "mcp", "anthropic"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

DASHBOARD_PORT = int(os.getenv("INTERNAL_DASHBOARD_PORT", "8090"))
HEARTBEAT_STALE = timedelta(minutes=10)
STARTUP_GRACE = timedelta(minutes=15)
HOP_BY_HOP = {"connection", "keep-alive", "transfer-encoding", "upgrade", "proxy-connection", "te", "trailer"}


def notifier_enabled() -> bool:
    """Run the notifier only in the deployed app. The preview pod keeps running after a deploy; two notifiers
    on two different databases would post every alert twice. Deployed = MONGO_URL is set (the platform gives
    it on publish). RUN_NOTIFIER=true/false overrides, e.g. for a local test."""
    explicit = os.getenv("RUN_NOTIFIER", "").strip().lower()
    if explicit in {"1", "true", "yes", "on"}:
        return True
    if explicit in {"0", "false", "no", "off"}:
        return False
    return bool(os.getenv("MONGO_URL", "").strip())


class State:
    started = time.monotonic()
    runner: web.AppRunner | None = None
    session: aiohttp.ClientSession | None = None
    tasks: list[asyncio.Task] = []
    store = None


async def keep_running(name: str, start) -> None:
    """Run a long-lived part of the app; if it stops or fails, log it and start it again after 30 s."""
    while True:
        try:
            await start()
            log.error("%s stopped; restarting in 30 s", name)
        except asyncio.CancelledError:
            raise
        except BaseException:  # includes SystemExit from a missing setting: report it, keep the server up
            log.exception("%s failed; restarting in 30 s", name)
        await asyncio.sleep(30)


async def run_notifier() -> None:
    cfg = Config.from_env(str(ROOT / ".env"))
    monitor = build_monitor(cfg, dry_run=cfg.dry_run, use_llm=True, with_store=True)  # on this thread: SQLite
    await asyncio.to_thread(check_classifier, monitor)  # it uses asyncio.run, so give it its own thread
    await monitor.run_forever()


async def run_watchdog() -> None:
    await build_watchdog(load_rules_config()).run_forever()


async def startup() -> None:
    rc = load_rules_config()
    d = rc.DASHBOARD
    settings = Settings(os.getenv("GOOGLE_CLIENT_ID") or None, False, float(d["session_hours"]), "127.0.0.1")
    app = build_dashboard(os.getenv("STATE_DB", "state.db"), os.getenv("TEAMS_FILE", "config/teams.yaml"),
                          d["users_file"], settings)
    State.runner = web.AppRunner(app, access_log=None)
    await State.runner.setup()
    await web.TCPSite(State.runner, "127.0.0.1", DASHBOARD_PORT).start()
    State.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=None, sock_connect=5),
                                          auto_decompress=False)
    storage = "MongoDB" if os.getenv("MONGO_URL", "").strip() else f"SQLite ({os.getenv('STATE_DB', 'state.db')})"
    if notifier_enabled():
        State.tasks = [asyncio.create_task(keep_running("notifier", run_notifier)),
                       asyncio.create_task(keep_running("watchdog", run_watchdog))]
        log.info("started dashboard, notifier and watchdog; storage: %s", storage)
    else:
        log.warning("started the dashboard only: the notifier runs in the deployed app (MONGO_URL set) or with "
                    "RUN_NOTIFIER=true; storage: %s", storage)


async def shutdown() -> None:
    for t in State.tasks:
        t.cancel()
    await asyncio.gather(*State.tasks, return_exceptions=True)
    if State.session:
        await State.session.close()
    if State.runner:
        await State.runner.cleanup()


def health() -> tuple[int, bytes]:
    """200 while the notifier's heartbeat is fresh (or it isn't meant to run here, or it is still starting);
    503 when it has stopped beating, so the platform restarts the app."""
    if not notifier_enabled():
        return 200, b"ok: dashboard only\n"
    if time.monotonic() - State.started < STARTUP_GRACE.total_seconds():
        return 200, b"ok: starting\n"
    try:
        if State.store is None:
            State.store = Store(os.getenv("STATE_DB", "state.db"))
        beat = datetime.fromisoformat(State.store.get("heartbeat") or "")
    except Exception as e:
        log.warning("health: cannot read the heartbeat: %s", e)
        return 503, b"unhealthy: no heartbeat\n"
    if datetime.now(timezone.utc) - beat > HEARTBEAT_STALE:
        return 503, b"unhealthy: notifier heartbeat is stale\n"
    return 200, b"ok\n"


async def forward(scope, receive, send) -> None:
    """Pass one HTTP request to the in-process dashboard and stream its answer back (the live page uses a
    never-ending server-sent-events response)."""
    body = b""
    while True:
        msg = await receive()
        if msg["type"] == "http.disconnect":
            return
        body += msg.get("body", b"")
        if not msg.get("more_body"):
            break
    path = scope.get("raw_path") or scope["path"].encode()
    url = f"http://127.0.0.1:{DASHBOARD_PORT}{path.decode('latin-1')}"
    if scope.get("query_string"):
        url += "?" + scope["query_string"].decode("latin-1")
    headers = [(k.decode("latin-1"), v.decode("latin-1")) for k, v in scope["headers"]
               if k.decode("latin-1").lower() not in HOP_BY_HOP | {"content-length"}]
    started = False
    try:
        async with State.session.request(scope["method"], url, headers=headers, data=body or None,
                                         allow_redirects=False) as resp:
            out = [(k.lower(), v) for k, v in resp.raw_headers if k.decode("latin-1").lower() not in HOP_BY_HOP]
            streaming = resp.headers.get("Content-Type", "").startswith("text/event-stream")
            if streaming:
                out = [(k, v) for k, v in out if k not in (b"content-length", b"x-accel-buffering")]
                out.append((b"x-accel-buffering", b"no"))  # nginx must not hold back live events
            await send({"type": "http.response.start", "status": resp.status, "headers": out})
            started = True

            async def pump():
                async for chunk in resp.content.iter_any():
                    await send({"type": "http.response.body", "body": chunk, "more_body": True})

            async def disconnected():
                while (await receive())["type"] != "http.disconnect":
                    pass

            pumping, gone = asyncio.create_task(pump()), asyncio.create_task(disconnected())
            done, pending = await asyncio.wait({pumping, gone}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            if pumping in done:
                pumping.result()
                await send({"type": "http.response.body", "body": b"", "more_body": False})
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        log.warning("dashboard unreachable for %s: %s", scope["path"], e)
        if started:  # the answer had begun: just end it
            await send({"type": "http.response.body", "body": b"", "more_body": False})
            return
        await send({"type": "http.response.start", "status": 502, "headers": [(b"content-type", b"text/plain")]})
        await send({"type": "http.response.body", "body": b"dashboard not ready\n"})


async def app(scope, receive, send) -> None:
    if scope["type"] == "lifespan":
        while True:
            msg = await receive()
            if msg["type"] == "lifespan.startup":
                try:
                    await startup()
                except Exception as e:
                    log.exception("startup failed")
                    await send({"type": "lifespan.startup.failed", "message": str(e)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif msg["type"] == "lifespan.shutdown":
                await shutdown()
                await send({"type": "lifespan.shutdown.complete"})
                return
    elif scope["type"] == "http":
        if scope["path"] == "/health":
            status, text = health()
            await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"text/plain")]})
            await send({"type": "http.response.body", "body": text})
            return
        await forward(scope, receive, send)
