"""The Shifts page, reports and scorecard (PRD_shift_guardian.md R1, R6-R9), and "Run check now" (E2).

Never calls Trinity. Everything here is read from what the notifier stores:
  * its copy of Trinity data (notifier/sync.py): presence and open tickets of monitored engineers;
  * its shift-end records (R1, notifier/shift_checks.py);
  * its alerts, with associates' reviews (an alert marked false alarm never counts in reports or the scorecard).
Rosters come from the roster files (config.py ROSTER_VIEWS). Teams there that the notifier doesn't monitor (L2 Expo)
are shown in the roster view only: they have no presence, tickets, alerts or score here.

The only write is "Run check now": a request in the kv table that the notifier picks up within seconds.
"""

from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from notifier.detectors import RULE_TITLES, Rule
from notifier.sync import RUN_DONE_KEY, RUN_REQUEST_KEY, RUN_RESULT_KEY
from notifier.shifts import ShiftCalendar, roster_day

log = logging.getLogger(__name__)

RECENT = timedelta(hours=24)  # shift ends shown on the Shifts page
STATUS_ALERT_AFTER = 45  # minutes; theme 4's Slack alert (config.py STATUS_CHECK)
RUN_COOLDOWN = timedelta(seconds=60)  # one "Run check now" a minute
REPORT_MAX_DAYS = 90
HEAVY_DAY = 3  # alerts for one engineer in one day
REPEATED_TICKET = 2  # alerts on one ticket
NEEDS_ATTENTION = 3  # offline violations, or un-assignments without a note
PATTERN_DAYS = 7  # the daily report's "repeated patterns" look back this far


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


class ShiftViews:
    def __init__(self, store, data, *, shifts_file: str | Path | None, tz: str, roster_views: list[dict],
                 ticket_url: str):
        self.store = store  # the notifier's Store (SQLite or MongoDB, same as the notifier's)
        self.data = data  # dashboard/queries.py Data: names, teams, alerts with reviews
        self.shifts_file = Path(shifts_file) if shifts_file else None
        self.tz = ZoneInfo(tz)
        self.tz_name = tz
        self.views = [v for v in roster_views if Path(v["file"]).exists()]
        self.ticket_url = ticket_url
        self._cal: ShiftCalendar | None = None
        self._cal_key = None

    # --- people -------------------------------------------------------------------------------

    @property
    def monitored(self) -> set[str]:
        return set(self.data.team_of)

    def _scope(self, team: str | None):
        members = self.data.team_members(team)
        return lambda e: e in self.data.team_of and (members is None or e in members)

    def _person(self, email: str) -> dict:
        return {"email": email, "name": self.data.name(email), "team": self.data.team_of.get(email)}

    def _link(self, t: dict) -> dict:
        return {"ticket_id": t["ticket_id"], "num": t.get("num"), "subject": t.get("subject"),
                "level": t.get("level"), "url": self.ticket_url.format(id=t["ticket_id"], num=t.get("num") or "")}

    def calendar(self, now: datetime) -> ShiftCalendar | None:
        """The notifier's roster (SHIFTS["file"]), re-read when the file changes or the day turns."""
        if not self.shifts_file or not self.shifts_file.exists():
            return None
        key = (self.shifts_file.stat().st_mtime, now.astimezone(self.tz).date())
        if key != self._cal_key:
            self._cal = ShiftCalendar.load(self.shifts_file, self.tz_name, now)
            self._cal_key = key
        return self._cal

    def _local_day(self, iso: str) -> date:
        return datetime.fromisoformat(iso).astimezone(self.tz).date()

    # --- Shifts page (R1, R6, R7) ---------------------------------------------------------------

    def shifts(self, now: datetime, team: str | None = None, roster: str | None = None,
               user: str | None = None) -> dict:
        keep = self._scope(team)
        presence = {e: p for e, (p, _) in self.store.presences().items()}
        open_by: dict[str, list[dict]] = defaultdict(list)
        for t in self.store.open_tickets():
            open_by[t["assignee"]].append(self._link(t))

        still_online, recent_ends = [], []
        for r in self.store.shift_records(since=(now - RECENT).isoformat()):
            e = r["email"]
            if not keep(e):
                continue
            end = datetime.fromisoformat(r["shift_end"])
            row = {**self._person(e), "shift_start": r["shift_start"], "shift_end": r["shift_end"],
                   "outcome": r["outcome"], "online_minutes": r["online_minutes"], "offline_at": r["offline_at"]}
            if r["outcome"] == "open":
                minutes = int((now - end).total_seconds() // 60)
                still_online.append(row | {"online_minutes": minutes, "presence": presence.get(e),
                                           "alerted": minutes >= STATUS_ALERT_AFTER, "open_tickets": open_by.get(e, [])})
            elif r["outcome"] in ("went_offline_late", "online_until_next_shift", "not_observed"):
                recent_ends.append(row)
        still_online.sort(key=lambda x: -x["online_minutes"])
        recent_ends.sort(key=lambda x: x["shift_end"], reverse=True)

        off_shift = []
        cal = self.calendar(now)
        if cal is not None:
            for e, tickets in open_by.items():
                # Unknown roster cells (a swap) or no roster entry: we don't know they're off shift, so not listed.
                if not keep(e) or not cal.has_schedule(e) or not cal.is_certain(e, now) or cal.on_shift(e, now):
                    continue
                ended = cal.last_end_before(e, now)
                nxt = min((s.start for s in cal.by_email.get(e, []) if s.start > now), default=None)
                off_shift.append({**self._person(e), "presence": presence.get(e), "tickets": tickets,
                                  "shift_ended": ended.isoformat() if ended else None,
                                  "next_shift": nxt.isoformat() if nxt else None})
        off_shift.sort(key=lambda x: (-len(x["tickets"]), x["name"] or ""))

        return {"now": now.isoformat(), "timezone": self.tz_name, "team": team,
                "still_online": still_online, "recent_ends": recent_ends, "off_shift_with_tickets": off_shift,
                "roster": self.roster(now, roster, user, presence),
                "synced": {"presence": self.store.get("synced_presence_at"),
                           "open_tickets": self.store.get("synced_open_tickets_at")},
                "run_check": self.run_state()}

    def roster(self, now: datetime, name: str | None, user: str | None, presence: dict) -> dict:
        """Today's roster for one team, as written in its file, with who is on shift right now (R7)."""
        names = [v["name"] for v in self.views]
        if not self.views:
            return {"views": [], "name": None, "people": []}
        view = next((v for v in self.views if v["name"] == name), None)
        if view is None and user:
            view = next((v for v in self.views if user.lower() in [a.lower() for a in v.get("associates", [])]), None)
        view = view or self.views[0]
        today = now.astimezone(self.tz).date()
        rows = {r["email"]: r for r in roster_day(view["file"], self.tz_name, today)}
        for r in roster_day(view["file"], self.tz_name, today - timedelta(days=1)):  # last night's shift, still on
            if r["end"] and r["start"] <= now < r["end"]:
                rows[r["email"]] = r
        people = []
        for r in rows.values():
            if r["start"] is None:
                state = r["kind"]  # off | unknown (e.g. "swap(12th)") | none (empty cell)
            elif now < r["start"]:
                state = "later"
            elif now < r["end"]:
                state = "on"
            else:
                state = "done"
            watched = r["email"] in self.monitored
            people.append({"email": r["email"], "name": r["name"], "role": r["role"], "block": r["block"],
                           "code": r["code"], "state": state,
                           "start": r["start"].isoformat() if r["start"] else None,
                           "end": r["end"].isoformat() if r["end"] else None,
                           # Only engineers the notifier monitors have a status here; other teams are roster only.
                           "monitored": watched, "presence": presence.get(r["email"]) if watched else None})
        order = {"on": 0, "later": 1, "done": 2, "unknown": 3, "off": 4, "none": 5}
        people.sort(key=lambda p: (order[p["state"]], p["start"] or "", p["name"]))
        return {"views": names, "name": view["name"], "day": today.isoformat(), "people": people,
                "roster_only": not any(p["monitored"] for p in people)}

    # --- Reports and scorecard (R8, R9) -----------------------------------------------------

    def _range(self, start: date, end: date) -> tuple[str, str]:
        lo = datetime.combine(start, time(0), self.tz).astimezone(timezone.utc)
        hi = datetime.combine(end + timedelta(days=1), time(0), self.tz).astimezone(timezone.utc)
        return lo.isoformat(), hi.isoformat()

    def _facts(self, start: date, end: date, keep) -> list[dict]:
        lo, hi = self._range(start, end)
        return [f for f in self.data.alert_facts(lo, hi) if keep(f["engineer"])]

    def _ticket(self, f: dict) -> dict:
        return {"ticket_id": f["ticket_id"], "num": f["ticket_num"], "subject": f["subject"],
                "url": f["url"] or (self.ticket_url.format(id=f["ticket_id"], num=f["ticket_num"] or "")
                                    if f["ticket_id"] else None)}

    @staticmethod
    def _offline_violation(f: dict) -> bool:
        return f["rule"] == Rule.STATUS_SHIFT.value and f["details"].get("kind") == "end"

    @staticmethod
    def _unassign(f: dict) -> bool | None:
        """True: un-assigned with a note; False: without; None: not a theme 7 alert."""
        if f["rule"] != Rule.HELD_THEN_DROPPED.value:
            return None
        return bool(f["details"].get("left_note"))

    def _patterns(self, counted: list[dict]) -> tuple[list[dict], list[dict]]:
        """(heavy days: 3+ alerts for one engineer in one day, repeated tickets: 2+ alerts on one ticket)."""
        by_day: dict[tuple[str, date], list[dict]] = defaultdict(list)
        by_ticket: dict[str, list[dict]] = defaultdict(list)
        for f in counted:
            by_day[(f["engineer"], self._local_day(f["sent_at"]))].append(f)
            if f["ticket_id"]:
                by_ticket[f["ticket_id"]].append(f)
        heavy = [{**self._person(e), "day": d.isoformat(), "count": len(fs),
                  "by_rule": dict(Counter(f["rule"] for f in fs))}
                 for (e, d), fs in by_day.items() if len(fs) >= HEAVY_DAY]
        heavy.sort(key=lambda x: (-x["count"], x["day"]))
        repeated = []
        for fs in by_ticket.values():
            if len(fs) >= REPEATED_TICKET:
                engineers = sorted({f["engineer"] for f in fs})
                repeated.append({**self._ticket(fs[0]), "count": len(fs), "rules": sorted({f["rule"] for f in fs}),
                                 "engineers": [self._person(e) for e in engineers],
                                 "last_at": max(f["sent_at"] for f in fs)})
        repeated.sort(key=lambda x: x["last_at"], reverse=True)
        repeated.sort(key=lambda x: -x["count"])
        return heavy, repeated

    def reports(self, now: datetime, start: date | None = None, end: date | None = None,
                day: date | None = None, team: str | None = None) -> dict:
        today = now.astimezone(self.tz).date()
        end = min(end or today, today)
        start = start or end - timedelta(days=6)
        start = max(start, end - timedelta(days=REPORT_MAX_DAYS - 1))
        if start > end:
            start = end
        keep = self._scope(team)
        facts = self._facts(start, end, keep)
        counted = [f for f in facts if not f["false_alarm"]]
        heavy, repeated = self._patterns(counted)

        per = {e: {**self._person(e), "by_rule": Counter(), "false_alarms": 0, "unassign_with_note": 0,
                   "unassign_without_note": 0, "offline_violations": 0}
               for t in self.data.teams for e in (x.lower() for x in t["engineers"]) if keep(e)}
        for f in facts:
            p = per.get(f["engineer"])
            if p is None:
                continue
            if f["false_alarm"]:
                p["false_alarms"] += 1
                continue
            p["by_rule"][f["rule"]] += 1
            note = self._unassign(f)
            if note is not None:
                p["unassign_with_note" if note else "unassign_without_note"] += 1
            if self._offline_violation(f):
                p["offline_violations"] += 1
        pattern_of: dict[str, list[str]] = defaultdict(list)
        for h in heavy:
            pattern_of[h["email"]].append(f"{h['count']} alerts on {h['day']}")
        for r in repeated:
            for e in r["engineers"]:
                if sum(1 for f in counted if f["ticket_id"] == r["ticket_id"] and f["engineer"] == e["email"]) >= 2:
                    pattern_of[e["email"]].append(f"#{r['num'] or r['ticket_id']} flagged {r['count']} times")

        engineers, scorecard = [], []
        for e, p in per.items():
            total = sum(p["by_rule"].values())
            engineers.append({**p, "by_rule": dict(p["by_rule"]), "alerts": total})
            with_note, without = p["unassign_with_note"], p["unassign_without_note"]
            offline, patterns = p["offline_violations"], pattern_of.get(e, [])
            score = offline * 3 + without * 2 + with_note + (5 if patterns else 0)
            if offline >= NEEDS_ATTENTION or without >= NEEDS_ATTENTION or patterns:
                rating = "needs_attention"
            elif score:
                rating = "watch"
            else:
                rating = "good"
            scorecard.append({**self._person(e), "score": score, "rating": rating, "offline_violations": offline,
                              "unassign_without_note": without, "unassign_with_note": with_note,
                              "patterns": patterns, "other_alerts": total - offline - with_note - without,
                              "false_alarms": p["false_alarms"]})
        engineers.sort(key=lambda x: (-x["alerts"], x["name"] or ""))
        scorecard.sort(key=lambda x: (-x["score"], x["name"] or ""))

        return {"from": start.isoformat(), "to": end.isoformat(), "timezone": self.tz_name, "team": team,
                "rules": [{"id": r.value, "title": RULE_TITLES[r]} for r in Rule],
                "engineers": engineers, "heavy_days": heavy, "repeated_tickets": repeated,
                "scorecard": scorecard, "daily": self.daily(now, day or end, keep)}

    def daily(self, now: datetime, day: date, keep) -> dict:
        """One day's four lists: didn't go offline, stayed online late, un-assigned without a note, patterns."""
        lo, hi = self._range(day, day)
        facts = [f for f in self._facts(day, day, keep) if not f["false_alarm"]]
        false_alarmed = {f["trigger_event_id"] for f in self._facts(day, day, keep) if f["false_alarm"]}

        didnt, late, seen = [], [], set()
        for r in self.store.shift_records(since=lo, until=hi):
            e = r["email"]
            if not keep(e) or f"{e}|end|{r['shift_end']}" in false_alarmed:
                continue
            row = {**self._person(e), "shift_end": r["shift_end"], "online_minutes": r["online_minutes"],
                   "outcome": r["outcome"]}
            if r["outcome"] in ("open", "online_until_next_shift"):
                if r["outcome"] == "open":
                    row["online_minutes"] = int((now - datetime.fromisoformat(r["shift_end"])).total_seconds() // 60)
                didnt.append(row)
                seen.add((e, r["shift_end"]))
            elif r["outcome"] == "went_offline_late":
                late.append(row)
                seen.add((e, r["shift_end"]))
        for f in facts:  # theme 4 alerts from before shift ends were recorded (R1)
            if self._offline_violation(f):
                end = f["trigger_event_id"].rsplit("|", 1)[-1]
                if (f["engineer"], end) not in seen:
                    didnt.append({**self._person(f["engineer"]), "shift_end": end, "online_minutes": None,
                                  "outcome": "alerted"})
        late.sort(key=lambda x: -(x["online_minutes"] or 0))

        without_note = [{**self._person(f["engineer"]), **self._ticket(f), "at": f["sent_at"],
                         "held_minutes": f["details"].get("held_minutes")}
                        for f in facts if self._unassign(f) is False]

        week = [f for f in self._facts(day - timedelta(days=PATTERN_DAYS - 1), day, keep) if not f["false_alarm"]]
        heavy, repeated = self._patterns(week)
        patterns = [{**{k: h[k] for k in ("email", "name", "team")}, "what": f"{h['count']} alerts on {h['day']}"}
                    for h in heavy]
        patterns += [{**e, "what": f"#{r['num'] or r['ticket_id']} flagged {r['count']} times", "url": r["url"]}
                     for r in repeated for e in r["engineers"]]
        return {"day": day.isoformat(), "didnt_go_offline": didnt, "stayed_online_late": late,
                "unassigned_without_note": without_note, "patterns": patterns, "pattern_days": PATTERN_DAYS}

    # --- Run check now (E2) ---------------------------------------------------------------------

    def run_state(self) -> dict:
        try:
            req = json.loads(self.store.get(RUN_REQUEST_KEY) or "null")
        except ValueError:
            req = None
        done = self.store.get(RUN_DONE_KEY) or None
        pending = bool(req) and (not done or done < req["at"])
        return {"requested_at": req and req["at"], "by": req and req.get("by"), "done_at": done,
                "result": self.store.get(RUN_RESULT_KEY) or None, "pending": pending}

    def request_run(self, email: str, now: datetime) -> tuple[dict, bool]:
        """Ask the notifier for a cycle now (checks, then a full refresh of the Trinity copy). False when one was
        asked for under a minute ago and hasn't run yet."""
        state = self.run_state()
        if state["pending"] and now - _dt(state["requested_at"]) < RUN_COOLDOWN:
            return state, False
        self.store.put(RUN_REQUEST_KEY, json.dumps({"at": now.isoformat(), "by": email.lower()}))
        log.info("run check requested by %s", email)
        return self.run_state(), True
