"""Every read and write the dashboard makes, in one place (the storage boundary).

The notifier writes state.db (notifier/store.py); the dashboard reads it and adds its own two tables:
feedback on alerts, and sign-in sessions. Moving to another database later means replacing this module.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from notifier.detectors import RULE_TITLES, Rule
from notifier.store import open_db

DASHBOARD_SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule TEXT NOT NULL,
    trigger_event_id TEXT NOT NULL,
    verdict TEXT NOT NULL,       -- correct | false_alarm
    note TEXT,
    by_email TEXT NOT NULL,
    at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS feedback_alert ON feedback (rule, trigger_event_id);
CREATE TABLE IF NOT EXISTS dashboard_sessions (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    name TEXT,
    picture TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""

VERDICTS = ("correct", "false_alarm")
LIVE_WITHIN = timedelta(minutes=3)  # notifier heartbeat older than this: shown as not running
RULE_ORDER = [r.value for r in Rule]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _json(text: str | None):
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


class Data:
    def __init__(self, db_path: str | Path, teams: list[dict], names: dict[str, str]):
        self.db = open_db(db_path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(DASHBOARD_SCHEMA)
        self.db.commit()
        self.teams = teams  # [{"name", "associates": [...], "engineers": [...]}]
        self.names = {k.lower(): v for k, v in names.items()}
        self.team_of = {e.lower(): t["name"] for t in teams for e in t["engineers"]}

    # --- people -------------------------------------------------------------------------------

    def name(self, email: str | None) -> str | None:
        if not email:
            return None
        return self.names.get(email.lower()) or email.split("@")[0].replace(".", " ").title()

    def teams_for_associate(self, email: str) -> list[str]:
        return [t["name"] for t in self.teams if email.lower() in [a.lower() for a in t["associates"]]]

    def team_members(self, team: str | None) -> set[str] | None:
        if not team:
            return None
        for t in self.teams:
            if t["name"] == team:
                return {e.lower() for e in t["engineers"]}
        return set()

    def people(self) -> dict:
        return {
            "teams": [
                {"name": t["name"],
                 "associates": [{"email": a, "name": self.name(a)} for a in t["associates"]],
                 "engineers": [{"email": e, "name": self.name(e)} for e in t["engineers"]]}
                for t in self.teams
            ],
            "rules": [{"id": r, "title": RULE_TITLES[Rule(r)]} for r in RULE_ORDER],
        }

    # --- notifier status ----------------------------------------------------------------------

    def kv(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def status(self) -> dict:
        beat = self.kv("heartbeat")
        live = bool(beat) and _now() - datetime.fromisoformat(beat) < LIVE_WITHIN
        last_error = self.db.execute(
            "SELECT at, summary FROM activity WHERE kind='error' ORDER BY id DESC LIMIT 1").fetchone()
        last_cycle = self.db.execute(
            "SELECT at, summary FROM activity WHERE kind='cycle' ORDER BY id DESC LIMIT 1").fetchone()
        pending = self.db.execute("SELECT COUNT(*) FROM checks WHERE done=0").fetchone()[0]
        return {
            "live": live,
            "heartbeat": beat,
            "info": _json(self.kv("notifier_info")),
            "last_error": dict(last_error) if last_error else None,
            "last_cycle": dict(last_cycle) if last_cycle else None,
            "checks_waiting": pending,
            "last_activity_id": self.last_activity_id(),
        }

    def last_activity_id(self) -> int:
        return self.db.execute("SELECT COALESCE(MAX(id), 0) FROM activity").fetchone()[0]

    # --- overview -----------------------------------------------------------------------------

    def overview(self, hours: float, team: str | None) -> dict:
        since = _iso(_now() - timedelta(hours=hours))
        members = self.team_members(team)

        def mine(engineer: str | None) -> bool:
            return members is None or (engineer or "").lower() in members

        alerts = [r for r in self.db.execute(
            "SELECT rule, trigger_event_id, engineer, sent_at FROM alerts WHERE sent_at>=?", (since,)) if mine(r["engineer"])]
        checks = [r for r in self.db.execute(
            "SELECT rule, outcome, engineer FROM activity WHERE kind='check' AND at>=?", (since,)) if mine(r["engineer"])]
        models = [r for r in self.db.execute(
            "SELECT outcome, data, engineer FROM activity WHERE kind='model' AND at>=?", (since,)) if mine(r["engineer"])]
        status_checks = [r for r in self.db.execute(
            "SELECT outcome, engineer FROM activity WHERE kind='status' AND at>=?", (since,)) if mine(r["engineer"])]

        fb = self._latest_feedback()
        reviewed = Counter(fb[(a["rule"], a["trigger_event_id"])]["verdict"]
                           for a in alerts if (a["rule"], a["trigger_event_id"]) in fb)

        # Hourly (or daily, for long windows) buckets of alerts and checks.
        step = timedelta(hours=1 if hours <= 48 else 24)
        start = _now() - timedelta(hours=hours)
        n = int(timedelta(hours=hours) / step) + 1
        buckets = [{"t": _iso(start + i * step), "alerts": 0, "checks": 0} for i in range(n)]

        def bucket(at: str) -> int:
            return min(n - 1, max(0, int((datetime.fromisoformat(at) - start) / step)))

        for a in alerts:
            buckets[bucket(a["sent_at"])]["alerts"] += 1
        for r in self.db.execute("SELECT at, engineer FROM activity WHERE kind='check' AND at>=?", (since,)):
            if mine(r["engineer"]):
                buckets[bucket(r["at"])]["checks"] += 1

        per_rule = []
        alert_by_rule = Counter(a["rule"] for a in alerts)
        check_by_rule = defaultdict(Counter)
        for c in checks:
            check_by_rule[c["rule"]][c["outcome"]] += 1
        for s in status_checks:
            check_by_rule[Rule.STATUS_SHIFT.value]["ok" if s["outcome"] == "ok" else s["outcome"]] += 1
        # The last 12 hours per rule, hour by hour: checks run and alerts sent.
        h12 = _now() - timedelta(hours=12)
        hourly = {r: {"checks": [0] * 12, "alerts": [0] * 12} for r in RULE_ORDER}

        def hour(at: str) -> int:
            return min(11, max(0, int((datetime.fromisoformat(at) - h12) / timedelta(hours=1))))

        for r in self.db.execute("SELECT rule, at, engineer FROM activity WHERE kind IN ('check','status') "
                                 "AND rule IS NOT NULL AND at>=?", (_iso(h12),)):
            if r["rule"] in hourly and mine(r["engineer"]):
                hourly[r["rule"]]["checks"][hour(r["at"])] += 1
        for r in self.db.execute("SELECT rule, sent_at, engineer FROM alerts WHERE sent_at>=?", (_iso(h12),)):
            if r["rule"] in hourly and mine(r["engineer"]):
                hourly[r["rule"]]["alerts"][hour(r["sent_at"])] += 1
        for rule in RULE_ORDER:
            per_rule.append({"rule": rule, "title": RULE_TITLES[Rule(rule)], "alerts": alert_by_rule[rule],
                             "outcomes": dict(check_by_rule[rule]), "last12h": hourly[rule]})

        latency = defaultdict(list)
        model_outcomes = Counter()
        for m in models:
            d = _json(m["data"]) or {}
            model_outcomes[m["outcome"]] += 1
            if d.get("latency_ms") is not None:
                latency[d.get("model") or "?"].append(d["latency_ms"])

        def pct(values: list[int], q: float) -> int | None:
            if not values:
                return None
            s = sorted(values)
            return s[min(len(s) - 1, int(q * (len(s) - 1) + 0.5))]

        top = Counter(a["engineer"] for a in alerts).most_common(6)
        return {
            "hours": hours,
            "team": team,
            "totals": {
                "alerts": len(alerts),
                "checks": len(checks) + len(status_checks),
                "outcomes": dict(Counter(c["outcome"] for c in checks)),
                "reviewed": dict(reviewed),
                "unreviewed": len(alerts) - sum(reviewed.values()),
            },
            "per_rule": per_rule,
            "timeline": {"step_hours": step.total_seconds() / 3600, "buckets": buckets},
            "models": {
                "calls": len(models),
                "outcomes": dict(model_outcomes),
                "latency": [{"model": k, "calls": len(v), "p50_ms": pct(v, 0.5), "p95_ms": pct(v, 0.95)}
                            for k, v in sorted(latency.items())],
            },
            "top_engineers": [{"email": e, "name": self.name(e), "team": self.team_of.get(e.lower()), "alerts": c}
                              for e, c in top],
        }

    # --- alerts -------------------------------------------------------------------------------

    def _latest_feedback(self) -> dict[tuple[str, str], dict]:
        out = {}
        for r in self.db.execute("SELECT * FROM feedback ORDER BY id"):
            out[(r["rule"], r["trigger_event_id"])] = dict(r)
        return out

    def _alert_row(self, r: sqlite3.Row, fb: dict) -> dict:
        key = (r["rule"], r["trigger_event_id"])
        review = fb.get(key)
        return {
            "id": r["rowid"],
            "rule": r["rule"],
            "rule_title": RULE_TITLES[Rule(r["rule"])],
            "ticket_id": r["ticket_id"] or None,
            "ticket_num": r["ticket_num"],
            "subject": r["subject"],
            "engineer": r["engineer"],
            # The team sheet's spelling wins over the display name Trinity recorded.
            "engineer_name": self.names.get((r["engineer"] or "").lower()) or r["engineer_name"]
            or self.name(r["engineer"]),
            "team": self.team_of.get((r["engineer"] or "").lower()),
            "associates": _json(r["associates"]) or [],
            "reason": r["reason"],
            "url": r["url"],
            "dry_run": None if r["dry_run"] is None else bool(r["dry_run"]),
            "sent_at": r["sent_at"],
            "review": {"verdict": review["verdict"], "by": review["by_email"], "by_name": self.name(review["by_email"]),
                       "at": review["at"], "note": review["note"]} if review else None,
        }

    def alerts(self, *, rule: str | None = None, team: str | None = None, engineer: str | None = None,
               review: str | None = None, q: str | None = None, hours: float | None = None,
               limit: int = 100, before_id: int | None = None) -> dict:
        sql = "SELECT rowid, * FROM alerts WHERE 1=1"
        args: list = []
        if rule:
            sql += " AND rule=?"
            args.append(rule)
        if engineer:
            sql += " AND lower(engineer)=?"
            args.append(engineer.lower())
        if hours:
            sql += " AND sent_at>=?"
            args.append(_iso(_now() - timedelta(hours=hours)))
        if before_id:
            sql += " AND rowid<?"
            args.append(before_id)
        sql += " ORDER BY sent_at DESC, rowid DESC"
        members = self.team_members(team)
        fb = self._latest_feedback()
        needle = (q or "").strip().lower().lstrip("#")
        items = []
        for r in self.db.execute(sql, args):
            if members is not None and (r["engineer"] or "").lower() not in members:
                continue
            row = self._alert_row(r, fb)
            if review == "unreviewed" and row["review"]:
                continue
            if review in VERDICTS and (not row["review"] or row["review"]["verdict"] != review):
                continue
            if needle and needle not in " ".join(str(x).lower() for x in (
                    row["ticket_num"], row["ticket_id"], row["engineer"], row["engineer_name"], row["subject"],
                    row["reason"])):
                continue
            items.append(row)
            if len(items) > limit:
                break
        more = len(items) > limit
        return {"items": items[:limit], "more": more}

    def alert(self, alert_id: int) -> dict | None:
        r = self.db.execute("SELECT rowid, * FROM alerts WHERE rowid=?", (alert_id,)).fetchone()
        if r is None:
            return None
        row = self._alert_row(r, self._latest_feedback())
        row["payload"] = _json(r["payload"])
        row["trace"] = self.activity_rows(
            "SELECT * FROM activity WHERE rule=? AND trigger_event_id=? ORDER BY id", (r["rule"], r["trigger_event_id"]))
        row["feedback_history"] = [
            {**dict(f), "by_name": self.name(f["by_email"])} for f in self.db.execute(
                "SELECT * FROM feedback WHERE rule=? AND trigger_event_id=? ORDER BY id DESC",
                (r["rule"], r["trigger_event_id"]))]
        return row

    def add_feedback(self, alert_id: int, verdict: str, note: str | None, by_email: str) -> dict | None:
        if verdict not in VERDICTS:
            raise ValueError("verdict must be 'correct' or 'false_alarm'")
        r = self.db.execute("SELECT rule, trigger_event_id FROM alerts WHERE rowid=?", (alert_id,)).fetchone()
        if r is None:
            return None
        self.db.execute(
            "INSERT INTO feedback (rule, trigger_event_id, verdict, note, by_email, at) VALUES (?,?,?,?,?,?)",
            (r["rule"], r["trigger_event_id"], verdict, (note or "").strip()[:2000] or None, by_email, _iso(_now())))
        self.db.commit()
        return self.alert(alert_id)

    # --- activity -----------------------------------------------------------------------------

    def _ticket_nums(self) -> dict[str, int]:
        """ticket id -> number, from any row that recorded it (clean checks never fetch the ticket).
        Cached for a few seconds: the live stream asks every second."""
        cached = getattr(self, "_nums_cache", None)
        if cached and (_now() - cached[0]).total_seconds() < 5:
            return cached[1]
        nums = {r[0]: r[1] for r in self.db.execute(
            "SELECT ticket_id, MAX(ticket_num) FROM activity WHERE ticket_num IS NOT NULL GROUP BY ticket_id "
            "UNION ALL SELECT ticket_id, MAX(ticket_num) FROM alerts WHERE ticket_num IS NOT NULL GROUP BY ticket_id")}
        self._nums_cache = (_now(), nums)
        return nums

    def _activity_row(self, r: sqlite3.Row, nums: dict[str, int] | None = None) -> dict:
        return {
            "id": r["id"], "at": r["at"], "kind": r["kind"], "rule": r["rule"],
            "trigger_event_id": r["trigger_event_id"], "ticket_id": r["ticket_id"],
            "ticket_num": r["ticket_num"] or (nums or {}).get(r["ticket_id"]),
            "engineer": r["engineer"], "engineer_name": self.name(r["engineer"]),
            "team": self.team_of.get((r["engineer"] or "").lower()),
            "outcome": r["outcome"], "summary": r["summary"], "data": _json(r["data"]),
        }

    def activity_rows(self, sql: str, args: tuple) -> list[dict]:
        nums = self._ticket_nums()
        return [self._activity_row(r, nums) for r in self.db.execute(sql, args)]

    def activity(self, *, after_id: int | None = None, before_id: int | None = None, kinds: list[str] | None = None,
                 rule: str | None = None, team: str | None = None, limit: int = 150) -> list[dict]:
        sql, args = "SELECT * FROM activity WHERE 1=1", []
        if after_id is not None:
            sql += " AND id>?"
            args.append(after_id)
        if before_id is not None:
            sql += " AND id<?"
            args.append(before_id)
        if kinds:
            sql += f" AND kind IN ({','.join('?' * len(kinds))})"
            args += kinds
        if rule:
            sql += " AND rule=?"
            args.append(rule)
        sql += " ORDER BY id ASC" if after_id is not None else " ORDER BY id DESC"
        members = self.team_members(team)
        nums = self._ticket_nums()
        out = []
        for r in self.db.execute(sql, args):
            # Team filter keeps rows about the team's engineers, plus system rows (no engineer).
            if members is not None and r["engineer"] and r["engineer"].lower() not in members:
                continue
            out.append(self._activity_row(r, nums))
            if len(out) >= limit:
                break
        return out

    # --- tickets ------------------------------------------------------------------------------

    def ticket(self, ticket_ref: str) -> dict | None:
        ref = ticket_ref.lstrip("#")
        ticket_id = ref
        if ref.isdigit():
            row = self.db.execute(
                "SELECT ticket_id FROM activity WHERE ticket_num=? AND ticket_id IS NOT NULL "
                "UNION SELECT ticket_id FROM alerts WHERE ticket_num=? LIMIT 1", (int(ref), int(ref))).fetchone()
            if row is None:
                return None
            ticket_id = row[0]
        trace = self.activity_rows("SELECT * FROM activity WHERE ticket_id=? ORDER BY id", (ticket_id,))
        checks = [dict(r) for r in self.db.execute(
            "SELECT rule, trigger_event_id, due_at, attempts, done, outcome, engineer, created_at, finished_at "
            "FROM checks WHERE ticket_id=? ORDER BY due_at", (ticket_id,))]
        fb = self._latest_feedback()
        alerts = [self._alert_row(r, fb) for r in self.db.execute(
            "SELECT rowid, * FROM alerts WHERE ticket_id=? ORDER BY sent_at", (ticket_id,))]
        if not trace and not checks and not alerts:
            return None
        num = next((x["ticket_num"] for x in trace + alerts if x.get("ticket_num")), None)
        subject = next((a["subject"] for a in alerts if a.get("subject")), None) or next(
            ((t["data"] or {}).get("subject") for t in trace if (t["data"] or {}).get("subject")), None)
        url = next((a["url"] for a in alerts if a.get("url")), None)
        return {"ticket_id": ticket_id, "ticket_num": num, "subject": subject, "url": url, "trace": trace,
                "checks": checks, "alerts": alerts}

    # --- engineers ----------------------------------------------------------------------------

    def engineers(self, hours: float, team: str | None) -> list[dict]:
        since = _iso(_now() - timedelta(hours=hours))
        fb = self._latest_feedback()
        alerts = defaultdict(Counter)
        false_alarms = Counter()
        for r in self.db.execute("SELECT rule, trigger_event_id, engineer FROM alerts WHERE sent_at>=?", (since,)):
            e = (r["engineer"] or "").lower()
            alerts[e][r["rule"]] += 1
            f = fb.get((r["rule"], r["trigger_event_id"]))
            if f and f["verdict"] == "false_alarm":
                false_alarms[e] += 1
        checks = Counter()
        last_seen = {}
        for r in self.db.execute(
                "SELECT engineer, MAX(at) AS last, COUNT(*) AS n FROM activity WHERE kind IN ('check','status') "
                "AND at>=? GROUP BY lower(engineer)", (since,)):
            e = (r["engineer"] or "").lower()
            checks[e] = r["n"]
            last_seen[e] = r["last"]
        out = []
        for t in self.teams:
            if team and t["name"] != team:
                continue
            for e in t["engineers"]:
                k = e.lower()
                out.append({"email": e, "name": self.name(e), "team": t["name"],
                            "associates": t["associates"], "alerts": sum(alerts[k].values()),
                            "by_rule": dict(alerts[k]), "checks": checks[k], "false_alarms": false_alarms[k],
                            "last_activity": last_seen.get(k)})
        out.sort(key=lambda x: (-x["alerts"], x["name"] or ""))
        return out

    # --- sessions -----------------------------------------------------------------------------

    def create_session(self, token_hash: str, email: str, name: str | None, picture: str | None, hours: float) -> None:
        now = _now()
        self.db.execute("DELETE FROM dashboard_sessions WHERE expires_at<?", (_iso(now),))
        self.db.execute("INSERT INTO dashboard_sessions VALUES (?,?,?,?,?,?)",
                        (token_hash, email, name, picture, _iso(now), _iso(now + timedelta(hours=hours))))
        self.db.commit()

    def session(self, token_hash: str) -> dict | None:
        r = self.db.execute("SELECT * FROM dashboard_sessions WHERE token_hash=? AND expires_at>?",
                            (token_hash, _iso(_now()))).fetchone()
        return dict(r) if r else None

    def end_session(self, token_hash: str) -> None:
        self.db.execute("DELETE FROM dashboard_sessions WHERE token_hash=?", (token_hash,))
        self.db.commit()
