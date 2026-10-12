"""Run the dashboard:  python -m dashboard  (settings: config.py DASHBOARD, .env GOOGLE_CLIENT_ID)."""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

import yaml
from aiohttp import web
from dotenv import load_dotenv

from notifier.config import load_rules_config

from .app import Dashboard, Settings
from .auth import AllowList, is_loopback
from .queries import Data


def build(state_db: str | Path, teams_file: str | Path, users_file: str | Path, settings: Settings) -> web.Application:
    doc = yaml.safe_load(Path(teams_file).read_text(encoding="utf-8")) if Path(teams_file).exists() else {}
    doc = doc or {}
    data = Data(state_db, doc.get("teams") or [], doc.get("names") or {})
    return Dashboard(data, AllowList(users_file), settings).app()


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
