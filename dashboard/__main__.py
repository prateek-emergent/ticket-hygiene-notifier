"""Run the dashboard:  python -m dashboard  (settings: config.py DASHBOARD, .env GOOGLE_CLIENT_ID)."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import yaml
from aiohttp import web
from dotenv import load_dotenv

from notifier.config import DEFAULT_TICKET_URL, load_rules_config
from notifier.store import Store

from .app import Dashboard, Settings
from .auth import AllowList, is_loopback
from .queries import Data
from .shiftviews import ShiftViews


def build(state_db: str | Path, teams_file: str | Path, users_file: str | Path, settings: Settings,
          rules_config=None) -> web.Application:
    doc = yaml.safe_load(Path(teams_file).read_text(encoding="utf-8")) if Path(teams_file).exists() else {}
    doc = doc or {}
    data = Data(state_db, doc.get("teams") or [], doc.get("names") or {})
    rc = rules_config or load_rules_config()
    views = ShiftViews(Store(state_db), data, shifts_file=rc.SHIFTS["file"], tz=rc.SHIFTS["timezone"],
                       roster_views=getattr(rc, "ROSTER_VIEWS", None) or [{"name": "Roster", "file": rc.SHIFTS["file"]}],
                       ticket_url=os.getenv("TICKET_URL_TEMPLATE", DEFAULT_TICKET_URL))
    return Dashboard(data, AllowList(users_file), settings, views).app()


def main() -> None:
    load_dotenv()
    rc = load_rules_config()
    d = rc.DASHBOARD
    ap = argparse.ArgumentParser(prog="python -m dashboard")
    ap.add_argument("--host", default=os.getenv("DASHBOARD_HOST") or d["host"])
    ap.add_argument("--port", type=int, default=int(os.getenv("PORT") or d["port"]))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("dashboard")

    client_id = os.getenv("GOOGLE_CLIENT_ID") or None
    dev = os.getenv("DASHBOARD_DEV_LOGIN", "").strip().lower() in {"1", "true", "yes", "on"}
    if dev and not is_loopback(args.host):
        log.warning("DASHBOARD_DEV_LOGIN ignored: only allowed while listening on this machine (127.0.0.1)")
    if not client_id:
        log.warning("GOOGLE_CLIENT_ID is not set: Google sign-in is unavailable%s",
                    " (dev sign-in is on for this machine)" if dev and is_loopback(args.host) else "")
    users = d["users_file"]
    if not Path(users).exists():
        log.warning("%s doesn't exist: nobody can sign in (see config/dashboard_users.example.yaml)", users)
    settings = Settings(client_id, dev, float(d["session_hours"]), args.host)
    app = build(os.getenv("STATE_DB", "state.db"), os.getenv("TEAMS_FILE", "config/teams.yaml"), users, settings)
    log.info("dashboard on http://%s:%d", "localhost" if is_loopback(args.host) else args.host, args.port)
    web.run_app(app, host=args.host, port=args.port, print=None, access_log=None)


if __name__ == "__main__":
    main()
