"""Scheduled checks against the shift schedule (rules 4 and 5).

Unlike rules 1-3 and 6, these are not triggered by a ticket event: they run every poll cycle and
look at the clock.

Rule 4, status vs shift: 45 min (configurable) after an engineer's shift starts their Trinity status
should be Online, and 45 min after it ends it should be Offline. If not, post in the channel (tagging
the associate) and DM the engineer. One alert per shift boundary.

Rule 5, tickets held off shift: every 15 min, for each monitored engineer who is off shift, look at
their OPEN tickets. Alert when a customer has been waiting at least 3 h, counted from the later of the
customer's unanswered message and the end of the engineer's shift. One alert per ticket per off-shift
period. PENDING and CLOSED tickets are never flagged: those wait on the customer, not on us.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .detectors import Finding, Rule
from .shifts import ShiftCalendar
from .slack import build_status_messages
from .trinity import Trinity

# Theme 4 judges a shift boundary by the engineer's status *now*, so it can only judge boundaries whose check
# time has just passed. After a gap (notifier paused, down, redeploying) older boundaries are skipped: today's
# status says nothing about whether someone was online at a shift change two days ago.
STATUS_MAX_CATCHUP = timedelta(minutes=10)
PRESENCE_FRESH = timedelta(minutes=3)  # the copy of Trinity status is used when no older than this


def _record(email: str, shift, status: str | None, outcome: str) -> dict:
    return {"key": f"{email}|{shift.end.isoformat()}", "email": email, "shift_start": shift.start.isoformat(),
            "shift_end": shift.end.isoformat(), "status_at_end": status, "outcome": outcome,
            "offline_at": None, "online_minutes": 0 if outcome == "offline_on_time" else None}

log = logging.getLogger(__name__)


def _local(t: datetime, tz: str) -> str:
    return t.astimezone(ZoneInfo(tz)).strftime("%a %d %b, %H:%M")


def waiting_since(events) -> datetime | None:
    """When the customer started waiting on us: their first message after our last reply."""
    last_reply = None
    for e in events:
        if e.is_outbound_message and not e.is_system_notice:
            last_reply = e.seq
    first_unanswered = next(
        (e for e in events if e.is_customer_message and (last_reply is None or e.seq > last_reply)), None
    )
    return first_unanswered.created_at if first_unanswered else None


class ShiftChecks:
    def __init__(self, monitor):
        self.monitor = monitor
        self.cfg = monitor.cfg
        self._calendar: ShiftCalendar | None = None
        self._loaded_key = None
        self._warned = False

    @property
    def active(self) -> bool:
        return bool({Rule.STATUS_SHIFT, Rule.OFF_SHIFT_HOLD} & self.cfg.enabled_rules)

    def calendar(self, now: datetime) -> ShiftCalendar | None:
        path = Path(self.cfg.shifts_file)
        if not path.exists():
            if not self._warned:
                log.warning("shift checks are on but %s does not exist; skipping themes 4-5", path)
                self._warned = True
            return None
        key = (path.stat().st_mtime, now.astimezone(ZoneInfo(self.cfg.shifts_tz)).date())
        if key != self._loaded_key:  # file changed, or a new day: re-expand around today
            self._calendar = ShiftCalendar.load(path, self.cfg.shifts_tz, now)
            self._loaded_key = key
            log.info("loaded shifts for %d people from %s", len(self._calendar.people), path)
            self._warn_if_running_out(now)
        return self._calendar

    def _warn_if_running_out(self, now: datetime) -> None:
        """Rosters cover a few months (the current one ends mid-December). Warn a week ahead, then daily."""
        cal = self._calendar
        ends = [s.end for shifts in cal.by_email.values() for s in shifts]
        days_left = (max(ends) - now).days if ends else -1
        missing = sorted(e for t in self.monitor.directory.teams for e in t.engineers if not cal.has_schedule(e))
        if days_left < 0:
            log.warning("the shift roster has no shifts from today on: themes 4-5 are idle until it is updated (%s)",
                        self.cfg.shifts_file)
        elif days_left <= 7:
            log.warning("the shift roster runs out in %d day(s): update %s", days_left, self.cfg.shifts_file)
        if missing:
            log.warning("not in the shift roster, so themes 4-5 can't check them: %s", ", ".join(missing))

    async def run(self, trinity: Trinity, now: datetime) -> None:
        if not self.active:
            return
        cal = self.calendar(now)
        if cal is None:
            return
        if Rule.STATUS_SHIFT in self.cfg.enabled_rules:
            await self.track_shift_ends(trinity, cal, now)
            await self.check_status(trinity, cal, now)
        if Rule.OFF_SHIFT_HOLD in self.cfg.enabled_rules:
            await self.check_off_shift_tickets(trinity, cal, now)

    # --- rule 4 ------------------------------------------------------------------------------

    async def presences_now(self, trinity: Trinity, emails: list[str], now: datetime) -> dict[str, str | None]:
        """Status from the copy of Trinity data (notifier/sync.py) when it is under 3 min old, else asked live."""
        if not emails:
            return {}
        copy = self.monitor.store.presences()
        fresh = {e: copy[e][0] for e in emails
                 if e in copy and now - datetime.fromisoformat(copy[e][1]) <= PRESENCE_FRESH}
        missing = [e for e in emails if e not in fresh]
        return fresh | (await trinity.presences(missing) if missing else {})

    async def track_shift_ends(self, trinity: Trinity, cal: ShiftCalendar, now: datetime) -> None:
        """R1: at each shift end record the engineer's status; while they stay Online the record is "open",
        and it is closed as went_offline_late (when they go Offline) or online_until_next_shift. Shift ends
        missed while the notifier was off are recorded as not_observed, never judged by today's status."""
        store = self.monitor.store
        stored = store.get("shift_ends_tracked_until")
        since = datetime.fromisoformat(stored) if stored else now
        monitored = self.monitor.directory.is_monitored
        if now - since > STATUS_MAX_CATCHUP:
            for email, kind, shift in cal.boundaries(since, now - STATUS_MAX_CATCHUP):
                if kind == "end" and monitored(email):
                    store.add_shift_record(_record(email, shift, None, "not_observed"))
            since = now - STATUS_MAX_CATCHUP
        ends = [(e, s) for e, kind, s in cal.boundaries(since, now)
                if kind == "end" and monitored(e) and cal.is_certain(e, s.end) and not cal.on_shift(e, now)]
        opened = store.shift_records(outcome="open")
        presence = await self.presences_now(trinity, sorted({e for e, _ in ends} | {r["email"] for r in opened}), now)
        for email, shift in ends:
            status = presence.get(email)
            online = status == "ONLINE"
            if store.add_shift_record(_record(email, shift, status, "open" if online else "offline_on_time")) and online:
                self.monitor.trace("status", f"Shift ended {shift.end:%H:%M} UTC; still Online", engineer=email,
                                   rule=Rule.STATUS_SHIFT.value, outcome="waiting",
                                   data={"shift_end": shift.end, "presence": status})
        for rec in opened:
            email, end = rec["email"], datetime.fromisoformat(rec["shift_end"])
            minutes = int((now - end).total_seconds() // 60)
            if presence.get(email) not in ("ONLINE", None):
                store.close_shift_record(rec["key"], "went_offline_late", now.isoformat(), minutes)
                self.monitor.trace("status", f"Went Offline {minutes} min after shift end", engineer=email,
                                   rule=Rule.STATUS_SHIFT.value, outcome="ok", data={"online_minutes": minutes})
            elif cal.on_shift(email, now):
                store.close_shift_record(rec["key"], "online_until_next_shift", None, minutes)
        store.put("shift_ends_tracked_until", now.isoformat())

    async def check_status(self, trinity: Trinity, cal: ShiftCalendar, now: datetime) -> None:
        store, after = self.monitor.store, self.cfg.status_after
        stored = store.get("status_checked_until")
        checked_until = datetime.fromisoformat(stored) if stored else now
        if now - checked_until > STATUS_MAX_CATCHUP:
            skipped = sum(1 for _ in cal.boundaries(checked_until - after, now - STATUS_MAX_CATCHUP - after))
            log.warning("status checks: not running since %s; skipping %d missed shift starts/ends (status now "
                        "can't tell status then)", checked_until.isoformat(timespec="minutes"), skipped)
            self.monitor.trace("status", f"Skipped {skipped} shift starts/ends missed while the notifier was not "
                               f"running (since {checked_until.isoformat(timespec='minutes')})",
                               rule=Rule.STATUS_SHIFT.value, outcome="skipped")
            checked_until = now - STATUS_MAX_CATCHUP
        # Boundaries whose check time (boundary + 45 min) fell in (checked_until, now].
        for email, kind, shift in cal.boundaries(checked_until - after, now - after):
            if not self.monitor.directory.is_monitored(email):
                continue
            boundary = shift.start if kind == "start" else shift.end
            key = f"{email}|{kind}|{boundary.isoformat()}"
            if store.already_alerted(Rule.STATUS_SHIFT.value, key):
                continue
            if kind == "end" and cal.on_shift(email, now):
                continue  # back-to-back shifts: being Online is right
            if not cal.is_certain(email, now):
                continue  # roster cell unreadable (e.g. a swap): we don't know their real shift
            agent = await trinity.agent(email)
            presence = agent["presence"] if agent else None
            should_be_online = kind == "start"
            expected = "Online" if should_be_online else "Offline"
            if (presence == "ONLINE") == should_be_online:
                log.info("status ok: %s %s of shift, %s", email, kind, presence)
                self.monitor.trace("status", f"{expected} as expected, {int(after.total_seconds() // 60)} min "
                                   f"after shift {kind}", rule=Rule.STATUS_SHIFT.value, trigger_event_id=key,
                                   engineer=email, outcome="ok",
                                   data={"kind": kind, "presence": presence, "shift_start": shift.start,
                                         "shift_end": shift.end})
                continue
            if not store.claim_alert(Rule.STATUS_SHIFT.value, key):
                continue  # another notifier copy is posting it
            name = agent["name"] if agent else email
            mentions = [await self.monitor.notifier.mention(a) for a in self.monitor.directory.associates_for(email)]
            open_links: list[tuple[str, str]] = []
            if kind == "end":  # R2: give the associate the tickets to reassign (the app itself never writes)
                try:
                    open_links = [(f"#{t.num} · {t.subject}" if t.num else t.subject, self.cfg.ticket_url(t.id, t.num))
                                  for t in await trinity.open_tickets(email)]
                except Exception as e:
                    log.warning("could not list %s's open tickets: %s", email, e)
            (text, blocks), (dm_text, dm_blocks) = build_status_messages(
                name, email, kind, shift.start, shift.end, presence,
                int(after.total_seconds() // 60), self.cfg.shifts_tz, mentions, open_links,
            )
            try:
                if self.cfg.status_post_channel:
                    await self.monitor.notifier.post(text, blocks)
                if self.cfg.status_dm:
                    await self.monitor.notifier.dm(email, dm_text, dm_blocks)
            except Exception:
                store.release_alert(Rule.STATUS_SHIFT.value, key)
                raise
            associates = self.monitor.directory.associates_for(email)
            reason = f"Status was {(presence or 'unknown').title()}, expected {expected}, " \
                     f"{int(after.total_seconds() // 60)} min after shift {kind}."
            store.record_alert(Rule.STATUS_SHIFT.value, key, "", email,
                               {"kind": kind, "presence": presence, "shift_start": shift.start.isoformat(),
                                "open_tickets": [label for label, _ in open_links]},
                               engineer_name=name, associates=associates, reason=reason,
                               dry_run=self.monitor.notifier.dry_run)
            self.monitor.trace("alert", f"Alerted {', '.join(associates) or 'the channel'}: {reason}",
                               rule=Rule.STATUS_SHIFT.value, trigger_event_id=key, engineer=email,
                               outcome="flagged", data={"kind": kind, "presence": presence, "dm": self.cfg.status_dm,
                                                        "shift_start": shift.start, "shift_end": shift.end})
            log.info("%s %s -> flagged (%s at %s of shift)", Rule.STATUS_SHIFT.value, email, presence, kind)
        store.put("status_checked_until", now.isoformat())

    # --- rule 5 ------------------------------------------------------------------------------

    async def check_off_shift_tickets(self, trinity: Trinity, cal: ShiftCalendar, now: datetime) -> None:
        store = self.monitor.store
        last = store.get("offshift_last_sweep")
        if last and now - datetime.fromisoformat(last) < self.cfg.offshift_sweep:
            return
        store.put("offshift_last_sweep", now.isoformat())
        flagged_before = self._alert_count(Rule.OFF_SHIFT_HOLD)
        await self._sweep_off_shift(trinity, cal, now)
        flagged = self._alert_count(Rule.OFF_SHIFT_HOLD) - flagged_before
        self.monitor.trace("sweep", f"Off-shift sweep: {flagged} new alert(s)", rule=Rule.OFF_SHIFT_HOLD.value,
                           outcome="flagged" if flagged else "clean")

    def _alert_count(self, rule: Rule) -> int:
        return self.monitor.store.count_alerts(rule.value)

    async def _sweep_off_shift(self, trinity: Trinity, cal: ShiftCalendar, now: datetime) -> None:
        store = self.monitor.store
        tz = self.cfg.shifts_tz
        for team in self.monitor.directory.teams:
            for email in team.engineers:
                if not cal.has_schedule(email) or cal.on_shift(email, now) or not cal.is_certain(email, now):
                    continue
                off_since = cal.last_end_before(email, now)
                if off_since is None:
                    continue
                for ticket in await trinity.open_tickets(email):
                    key = f"{ticket.id}|{off_since.isoformat()}"
                    if store.already_alerted(Rule.OFF_SHIFT_HOLD.value, key):
                        continue
                    events = await trinity.all_events(ticket.id)
                    since = waiting_since(events)
                    if since is None:
                        continue
                    counted_from = max(since, off_since)
                    waited = now - counted_from
                    if waited < self.cfg.offshift_wait:
                        continue
                    hours = waited.total_seconds() / 3600
                    finding = Finding(
                        rule=Rule.OFF_SHIFT_HOLD,
                        ticket_id=ticket.id,
                        trigger_event_id=key,
                        engineer_email=email,
                        engineer_name=None,
                        reason=(
                            f"A customer has been waiting {hours:.1f} h on this OPEN ticket while its assignee "
                            "is off shift. Please reassign it to someone on shift."
                        ),
                        details={
                            "waiting_since_local": f"{_local(since, tz)} ({tz})",
                            "shift_ended_local": f"{_local(off_since, tz)} ({tz})",
                        },
                    )
                    if not store.claim_alert(Rule.OFF_SHIFT_HOLD.value, key):
                        continue  # another notifier copy is posting it
                    try:
                        info = await self.monitor.alert(finding, ticket)
                    except Exception:
                        store.release_alert(Rule.OFF_SHIFT_HOLD.value, key)
                        raise
                    if self.cfg.offshift_dm:
                        await self.monitor.notifier.dm(
                            email, f"Ticket #{ticket.num} is still assigned to you while you are off shift.", []
                        )
                    store.record_alert(Rule.OFF_SHIFT_HOLD.value, key, ticket.id, email,
                                       {"waiting_since": since.isoformat(), "off_since": off_since.isoformat()},
                                       **info)
                    log.info("%s ticket=%s %s -> flagged (%.1f h)", Rule.OFF_SHIFT_HOLD.value, ticket.id, email, hours)
