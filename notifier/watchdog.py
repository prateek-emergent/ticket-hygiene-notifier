"""Down alert: a Slack DM to one person (config.py DOWN_ALERT["dm"]), never the channel.

Runs as its own process (python -m notifier watchdog) next to the notifier, reading the same state.db:
  * stopped: the notifier's heartbeat is older than DOWN_ALERT["after_minutes"] (crashed, hung, never started);
  * failing: it runs, but every cycle has failed for that long (VPN down, Trinity key revoked, ...).
One DM when a problem starts, a reminder every DOWN_ALERT["remind_every_minutes"] while it lasts, and one DM
when the notifier is back. It needs only SLACK_BOT_TOKEN and state.db, not the notifier's own config, so a
notifier that can't even start (bad .env, bad config.py) is still reported.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from slack_sdk.errors import SlackApiError

from .slack import SlackNotifier
from .store import Store

log = logging.getLogger(__name__)

TICK_SECONDS = 60


@dataclass
class Status:
    kind: str  # "up", "stopped" or "failing"
    since: datetime | None = None  # when the problem started (stopped: the last heartbeat)
    detail: str = ""


def _parse(value: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(value) if value else None
    except ValueError:
        return None


def assess(store: Store, now: datetime, after: timedelta, started: datetime) -> Status:
    """What state the notifier is in, from what it writes to state.db."""
    beat = _parse(store.get("heartbeat"))
    if beat is None:
        # Fresh database: give a starting notifier the same grace period, counted from the watchdog's start.
        return Status("stopped", started, "no heartbeat yet") if now - started >= after else Status("up")
    if now - beat >= after:
        return Status("stopped", beat)
    failing = _parse(store.get("failing_since"))
    if failing is not None and now - failing >= after:
        return Status("failing", failing, store.get("last_cycle_error") or "")
    return Status("up")


def message(status: Status, now: datetime, tz: ZoneInfo, reminder: bool) -> str:
    def at(t: datetime) -> str:
        return t.astimezone(tz).strftime("%d %b %H:%M %Z")

    minutes = int((now - status.since).total_seconds() // 60) if status.since else 0
    again = "Still down. " if reminder else ""
    if status.kind == "stopped":
        if status.detail == "no heartbeat yet":
            return (f":red_circle: {again}*Ticket-hygiene notifier has not started* ({minutes} min since the "
                    "watchdog started). Check the container logs: usually a missing setting in the environment.")
        return (f":red_circle: {again}*Ticket-hygiene notifier is down*: no heartbeat for {minutes} min "
                f"(last at {at(status.since)}). No tickets are being checked. Check the container logs and restart it.")
    return (f":large_orange_circle: {again}*Ticket-hygiene notifier is running but every check is failing* "
            f"for {minutes} min (since {at(status.since)}). Usually Trinity or the VPN is unreachable, or a key "
            f"was revoked. Last error: `{status.detail[:200] or 'unknown'}`")


class Watchdog:
    def __init__(self, store: Store, slack: SlackNotifier, rc_down: dict, tz: ZoneInfo,
                 started: datetime | None = None):
        self.store = store
        self.slack = slack
        self.to = rc_down["dm"]
        self.after = timedelta(minutes=float(rc_down.get("after_minutes", 10)))
        remind = float(rc_down.get("remind_every_minutes", 60) or 0)
        self.remind = timedelta(minutes=remind) if remind > 0 else None
        self.tz = tz
        self.started = started or datetime.now(timezone.utc)

    async def send(self, text: str) -> bool:
        try:
            if not self.slack.dry_run and await self.slack.user_id(self.to) is None:
                log.error("down alert: no Slack user for %s (config.py DOWN_ALERT['dm'])", self.to)
                return False
            await self.slack.dm(self.to, text, [{"type": "section", "text": {"type": "mrkdwn", "text": text}}])
            return True
        except SlackApiError as e:  # try again on the next tick
            log.error("down alert: could not DM %s: %s", self.to, e.response.get("error"))
        except (OSError, asyncio.TimeoutError) as e:
            log.error("down alert: could not DM %s: %s", self.to, e)
        return False

    async def tick(self, now: datetime | None = None) -> str | None:
        """One check. Returns the text sent, if any. What was last sent is kept in state.db, so a restarted
        watchdog doesn't repeat itself."""
        now = now or datetime.now(timezone.utc)
        status = assess(self.store, now, self.after, self.started)
        alerted = self.store.get("down_alert_kind") or ""  # the problem last reported, "" = none
        last_dm = _parse(self.store.get("down_alert_at"))
        text = None
        if status.kind == "up":
            if alerted:
                text = ":large_green_circle: *Ticket-hygiene notifier is back* and checking tickets again."
        elif status.kind != alerted:
            text = message(status, now, self.tz, reminder=False)
        elif self.remind and last_dm and now - last_dm >= self.remind:
            text = message(status, now, self.tz, reminder=True)
        if text is None:
            return None
        if not await self.send(text):
            return None
        self.store.put("down_alert_kind", "" if status.kind == "up" else status.kind)
        self.store.put("down_alert_at", now.isoformat())
        log.warning("down alert sent to %s: %s", self.to, status.kind)
        return text

    async def run_forever(self) -> None:
        log.info("watchdog: DMs %s if the notifier is stopped or failing for %s min", self.to,
                 int(self.after.total_seconds() // 60))
        while True:
            try:
                await self.tick()
            except Exception:  # the watchdog itself must keep going
                log.exception("watchdog check failed")
            await asyncio.sleep(TICK_SECONDS)


def build_watchdog(rc) -> Watchdog:
    """From config.py (DOWN_ALERT, SHIFTS timezone) and the environment (SLACK_BOT_TOKEN, STATE_DB, DRY_RUN)."""
    down = getattr(rc, "DOWN_ALERT", None) or {}
    if not down.get("dm"):
        raise SystemExit("config.py DOWN_ALERT['dm'] is not set: nobody to tell when the notifier is down")
    token = os.getenv("SLACK_BOT_TOKEN") or None
    dry_run = os.getenv("DRY_RUN", "true").strip().lower() in {"1", "true", "yes", "on"}
    if not down.get("send_during_dry_run", True) and dry_run:
        token = None
    if token is None:
        log.warning("watchdog: no SLACK_BOT_TOKEN (or dry run): down alerts are printed here, not sent")
    teams = Path(os.getenv("TEAMS_FILE", "config/teams.yaml"))
    overrides = ((yaml.safe_load(teams.read_text(encoding="utf-8")) or {}).get("slack_ids") or {}) if teams.exists() else {}
    slack = SlackNotifier(token, "", dry_run=token is None, slack_id_overrides=overrides,
                          api_url=os.getenv("SLACK_API_URL") or None)
    tz = ZoneInfo(getattr(rc, "SHIFTS", {}).get("timezone", "UTC"))
    return Watchdog(Store(os.getenv("STATE_DB", "state.db")), slack, down, tz)
