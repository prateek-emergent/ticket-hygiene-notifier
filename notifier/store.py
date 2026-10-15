"""Notifier state: per-ticket progress, scheduled checks, sent alerts (for de-duplication), and the activity
trace the dashboard reads (every cycle, check, model call, alert and error, append-only).

Two backends, chosen by the environment and sharing one interface (same method names, same return shapes, so
the rest of the notifier and the dashboard don't change):

- SQLite (default): a single state.db file. The dashboard opens it read-mostly; WAL lets it read while the
  notifier writes. Used for local runs and the tests.
- MongoDB (when MONGO_URL is set): the deployed app's database. Timestamps stay ISO-8601 UTC strings, so they
  remain comparable and parseable with datetime.fromisoformat, exactly as in SQLite.

`Store(path)` returns whichever backend is configured. The duplicate-alert rules (claim_alert, record_alert)
are implemented the same way in both: an atomic claim and an insert-or-ignore, never find-then-insert.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .mongo import DuplicateKeyError, ensure_indexes, get_db, mongo_enabled, next_id

log = logging.getLogger(__name__)

# Columns added after the first release; created on open when missing.
MIGRATIONS = {
    "checks": {"engineer": "TEXT", "created_at": "TEXT", "finished_at": "TEXT"},
    "alerts": {
        "ticket_num": "INTEGER", "subject": "TEXT", "engineer_name": "TEXT", "associates": "TEXT",
        "reason": "TEXT", "url": "TEXT", "dry_run": "INTEGER",
    },
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    kind TEXT NOT NULL,          -- cycle | scheduled | recheck | check | model | alert | status | sweep | error | start
    rule TEXT,
    trigger_event_id TEXT,
    ticket_id TEXT,
    ticket_num INTEGER,
    engineer TEXT,
    outcome TEXT,                -- clean | ok | flagged | skipped | duplicate | error | waiting
    summary TEXT NOT NULL,       -- one line a person can read
    data TEXT                    -- JSON details
);
CREATE INDEX IF NOT EXISTS activity_at ON activity (at);
CREATE INDEX IF NOT EXISTS activity_ticket ON activity (ticket_id);
CREATE INDEX IF NOT EXISTS activity_check ON activity (rule, trigger_event_id);
"""

BASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ticket_progress (ticket_id TEXT PRIMARY KEY, last_seq INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS checks (
    rule TEXT NOT NULL,
    trigger_event_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    due_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    done INTEGER NOT NULL DEFAULT 0,
    outcome TEXT,
    PRIMARY KEY (rule, trigger_event_id)
);
CREATE TABLE IF NOT EXISTS alerts (
    rule TEXT NOT NULL,
    trigger_event_id TEXT NOT NULL,
    ticket_id TEXT NOT NULL,
    engineer TEXT NOT NULL,
    payload TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    PRIMARY KEY (rule, trigger_event_id)
);
-- One row per alert a notifier has reserved the right to post (see Store.claim_alert). The primary key is
-- what makes "post at most once" hold even with two notifier copies on the same database.
CREATE TABLE IF NOT EXISTS alert_claims (
    rule TEXT NOT NULL,
    trigger_event_id TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    PRIMARY KEY (rule, trigger_event_id)
);
-- A copy of Trinity data, refreshed by notifier/sync.py, so dashboard views don't have to ask Trinity.
CREATE TABLE IF NOT EXISTS presence (
    email TEXT PRIMARY KEY,
    presence TEXT,               -- ONLINE | OFFLINE | ... (NULL: Trinity doesn't know them)
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS open_tickets (
    ticket_id TEXT PRIMARY KEY,
    num INTEGER,
    subject TEXT,
    level TEXT,
    assignee TEXT NOT NULL,
    synced_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS open_tickets_assignee ON open_tickets (assignee);
-- R1: what happened at each shift end (notifier/shift_checks.py, track_shift_ends).
CREATE TABLE IF NOT EXISTS shift_records (
    key TEXT PRIMARY KEY,        -- email|shift end (ISO)
    email TEXT NOT NULL,
    shift_start TEXT NOT NULL,
    shift_end TEXT NOT NULL,
    status_at_end TEXT,          -- ONLINE | OFFLINE | ... | NULL (not observed)
    outcome TEXT NOT NULL,       -- open | offline_on_time | went_offline_late | online_until_next_shift | not_observed
    offline_at TEXT,
    online_minutes INTEGER,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS shift_records_end ON shift_records (shift_end);
-- Who may run a singleton job (the notifier) when several copies of the app run: see Store.take_lease.
CREATE TABLE IF NOT EXISTS leases (
    name TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def outcome_kind(outcome: str) -> str:
    """'skipped: uncertain: ...' -> 'skipped'; 'flagged-unclassified' -> 'flagged'."""
    head = outcome.split(":", 1)[0].strip().lower()
    return "flagged" if head.startswith("flagged") else head


def open_db(path: str | Path) -> sqlite3.Connection:
    db = sqlite3.connect(str(path), timeout=10)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=10000")
    db.executescript(BASE_SCHEMA + SCHEMA)
    for table, cols in MIGRATIONS.items():
        have = {r[1] for r in db.execute(f"PRAGMA table_info({table})")}
        for col, typ in cols.items():
            if col not in have:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    db.commit()
    return db


# What a "start fresh" reset clears (Store.reset_trial_data): alerts, reviews, the activity trace and the
# in-flight checks. Kept: ticket_progress (so old events are not re-alerted), kv, leases, sessions, counters.
RESET_TABLES = ("alerts", "alert_claims", "feedback", "activity", "checks")


def Store(path: str | Path):
    """The configured state store: MongoDB when MONGO_URL is set, otherwise SQLite at `path`."""
    if mongo_enabled():
        return MongoStore()
    return SqliteStore(path)


class SqliteStore:
    def __init__(self, path: str | Path):
        self.db = open_db(path)

    # --- activity trace (read by the dashboard) -----------------------------------------------

    def log(self, kind: str, summary: str, *, rule: str | None = None, trigger_event_id: str | None = None,
            ticket_id: str | None = None, ticket_num: int | None = None, engineer: str | None = None,
            outcome: str | None = None, data: dict | None = None) -> None:
        self.db.execute(
            "INSERT INTO activity (at, kind, rule, trigger_event_id, ticket_id, ticket_num, engineer, outcome, "
            "summary, data) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (_now(), kind, rule, trigger_event_id, ticket_id or None, ticket_num, engineer, outcome, summary[:1000],
             json.dumps(data, default=str) if data else None),
        )
        self.db.commit()

    def get(self, key: str) -> str | None:
        row = self.db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def put(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (key, value))
        self.db.commit()

    def last_seq(self, ticket_id: str) -> int | None:
        row = self.db.execute("SELECT last_seq FROM ticket_progress WHERE ticket_id=?", (ticket_id,)).fetchone()
        return row[0] if row else None

    def set_last_seq(self, ticket_id: str, seq: int) -> None:
        self.db.execute("INSERT OR REPLACE INTO ticket_progress VALUES (?,?)", (ticket_id, seq))
        self.db.commit()

    def schedule(self, rule: str, trigger_event_id: str, ticket_id: str, due_at: datetime,
                 engineer: str | None = None) -> bool:
        """True when the check is new (not scheduled before)."""
        cur = self.db.execute(
            "INSERT OR IGNORE INTO checks (rule, trigger_event_id, ticket_id, due_at, engineer, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (rule, trigger_event_id, ticket_id, due_at.isoformat(), engineer, _now()),
        )
        self.db.commit()
        return cur.rowcount > 0

    def due_checks(self, now: datetime, max_attempts: int = 5) -> list[tuple[str, str, str]]:
        return self.db.execute(
            "SELECT rule, trigger_event_id, ticket_id FROM checks "
            "WHERE done=0 AND due_at<=? AND attempts<? ORDER BY due_at",
            (now.isoformat(), max_attempts),
        ).fetchall()

    def reschedule(self, rule: str, trigger_event_id: str, due_at: datetime) -> None:
        self.db.execute(
            "UPDATE checks SET due_at=?, outcome='waiting for reply' WHERE rule=? AND trigger_event_id=?",
            (due_at.isoformat(), rule, trigger_event_id),
        )
        self.db.commit()

    def finish_check(self, rule: str, trigger_event_id: str, outcome: str) -> None:
        self.db.execute(
            "UPDATE checks SET done=1, outcome=?, finished_at=? WHERE rule=? AND trigger_event_id=?",
            (outcome, _now(), rule, trigger_event_id),
        )
        self.db.commit()

    def fail_check(self, rule: str, trigger_event_id: str, error: str) -> None:
        self.db.execute(
            "UPDATE checks SET attempts=attempts+1, outcome=? WHERE rule=? AND trigger_event_id=?",
            (f"error: {error}"[:500], rule, trigger_event_id),
        )
        self.db.commit()

    def already_alerted(self, rule: str, trigger_event_id: str) -> bool:
        return (
            self.db.execute(
                "SELECT 1 FROM alerts WHERE rule=? AND trigger_event_id=?", (rule, trigger_event_id)
            ).fetchone()
            is not None
        )

    def count_alerts(self, rule: str) -> int:
        """How many alerts have been recorded for a rule (used by the off-shift sweep trace)."""
        return self.db.execute("SELECT COUNT(*) FROM alerts WHERE rule=?", (rule,)).fetchone()[0]

    # --- copy of Trinity data (notifier/sync.py) -------------------------------------------------

    def put_presences(self, presences: dict[str, str | None]) -> None:
        at = _now()
        self.db.executemany("INSERT OR REPLACE INTO presence (email, presence, updated_at) VALUES (?,?,?)",
                            [(e.lower(), p, at) for e, p in presences.items()])
        self.db.commit()

    def presences(self) -> dict[str, tuple[str | None, str]]:
        """{email: (presence, updated_at)}"""
        return {r[0]: (r[1], r[2]) for r in self.db.execute("SELECT email, presence, updated_at FROM presence")}

    def put_open_tickets(self, assignee: str, tickets: list[dict]) -> None:
        """Replace one engineer's open tickets with `tickets` ({ticket_id, num, subject, level})."""
        at, assignee = _now(), assignee.lower()
        self.db.execute("DELETE FROM open_tickets WHERE assignee=?", (assignee,))
        self.db.executemany(
            "INSERT OR REPLACE INTO open_tickets (ticket_id, num, subject, level, assignee, synced_at) VALUES (?,?,?,?,?,?)",
            [(x["ticket_id"], x.get("num"), x.get("subject"), x.get("level"), assignee, at) for x in tickets])
        self.db.commit()

    def open_tickets(self, assignee: str | None = None) -> list[dict]:
        sql, args = "SELECT ticket_id, num, subject, level, assignee, synced_at FROM open_tickets", ()
        if assignee:
            sql, args = sql + " WHERE assignee=?", (assignee.lower(),)
        cols = ("ticket_id", "num", "subject", "level", "assignee", "synced_at")
        return [dict(zip(cols, r)) for r in self.db.execute(sql + " ORDER BY assignee, num", args)]

    # --- R1: shift-end records -------------------------------------------------------------------

    SHIFT_COLS = ("key", "email", "shift_start", "shift_end", "status_at_end", "outcome", "offline_at",
                  "online_minutes", "updated_at")

    def add_shift_record(self, rec: dict) -> bool:
        """Insert once per (email, shift end); False if it already exists."""
        rec = {**rec, "updated_at": _now()}
        cur = self.db.execute(
            f"INSERT OR IGNORE INTO shift_records ({','.join(self.SHIFT_COLS)}) VALUES ({','.join('?' * len(self.SHIFT_COLS))})",
            tuple(rec.get(c) for c in self.SHIFT_COLS))
        self.db.commit()
        return cur.rowcount == 1

    def close_shift_record(self, key: str, outcome: str, offline_at: str | None, online_minutes: int) -> None:
        self.db.execute("UPDATE shift_records SET outcome=?, offline_at=?, online_minutes=?, updated_at=? "
                        "WHERE key=? AND outcome='open'", (outcome, offline_at, online_minutes, _now(), key))
        self.db.commit()

    def shift_records(self, since: str | None = None, until: str | None = None, outcome: str | None = None) -> list[dict]:
        sql, args = "SELECT * FROM shift_records WHERE 1=1", []
        if since:
            sql, args = sql + " AND shift_end >= ?", args + [since]
        if until:
            sql, args = sql + " AND shift_end < ?", args + [until]
        if outcome:
            sql, args = sql + " AND outcome = ?", args + [outcome]
        cur = self.db.execute(sql + " ORDER BY shift_end", args)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in cur]

    def take_lease(self, name: str, owner: str, ttl_seconds: float) -> bool:
        """Take or renew the lease `name` for `owner` until now + ttl. True when `owner` holds it afterwards:
        it was free, expired, or already theirs. Atomic across processes sharing the database, so of several
        copies of the app exactly one holds it at a time."""
        now = datetime.now(timezone.utc)
        until = (now + timedelta(seconds=ttl_seconds)).isoformat()
        cur = self.db.execute("UPDATE leases SET owner=?, expires_at=? WHERE name=? AND (owner=? OR expires_at<?)",
                              (owner, until, name, owner, now.isoformat()))
        if cur.rowcount == 0:
            cur = self.db.execute("INSERT OR IGNORE INTO leases (name, owner, expires_at) VALUES (?,?,?)",
                                  (name, owner, until))
        self.db.commit()
        return cur.rowcount == 1

    def reset_trial_data(self, label: str) -> dict[str, int] | None:
        """Clear the trial data once per `label`: copy each RESET_TABLES table to <table>_bak_<label>, then empty
        it. Returns the counts cleared, or None when this label was already done."""
        done_key = f"reset_done:{label}"
        if self.get(done_key):
            return None
        suffix = "".join(c if c.isalnum() else "_" for c in label)
        have = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        counts = {}
        for name in RESET_TABLES:
            if name not in have:
                continue
            counts[name] = self.db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            self.db.execute(f"DROP TABLE IF EXISTS {name}_bak_{suffix}")
            self.db.execute(f"CREATE TABLE {name}_bak_{suffix} AS SELECT * FROM {name}")
            self.db.execute(f"DELETE FROM {name}")
        self.db.commit()
        self.put(done_key, _now())
        return counts

    def release_lease(self, name: str, owner: str) -> None:
        """Give the lease up (on shutdown), so another copy can take over at once instead of after the TTL."""
        self.db.execute("DELETE FROM leases WHERE name=? AND owner=?", (name, owner))
        self.db.commit()

    def claim_alert(self, rule: str, trigger_event_id: str) -> bool:
        """Reserve the right to post this alert, right before posting it. Atomic: when several notifier copies
        race for the same alert, exactly one gets True. Call release_alert() if the post then fails, so it
        can be retried. A crash between claim and post loses that alert rather than risking a duplicate."""
        if self.already_alerted(rule, trigger_event_id):
            return False
        cur = self.db.execute("INSERT OR IGNORE INTO alert_claims (rule, trigger_event_id, claimed_at) VALUES (?,?,?)",
                              (rule, trigger_event_id, _now()))
        self.db.commit()
        return cur.rowcount == 1

    def release_alert(self, rule: str, trigger_event_id: str) -> None:
        """The post failed: give the claim back so a later attempt can post it."""
        self.db.execute("DELETE FROM alert_claims WHERE rule=? AND trigger_event_id=?", (rule, trigger_event_id))
        self.db.commit()

    def record_alert(self, rule: str, trigger_event_id: str, ticket_id: str, engineer: str, payload: dict,
                     *, ticket_num: int | None = None, subject: str | None = None, engineer_name: str | None = None,
                     associates: list[str] | None = None, reason: str | None = None, url: str | None = None,
                     dry_run: bool | None = None) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO alerts (rule, trigger_event_id, ticket_id, engineer, payload, sent_at, ticket_num, "
            "subject, engineer_name, associates, reason, url, dry_run) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rule, trigger_event_id, ticket_id, engineer, json.dumps(payload, default=str), _now(), ticket_num,
             subject, engineer_name, json.dumps(associates) if associates is not None else None, reason, url,
             None if dry_run is None else int(dry_run)),
        )
        self.db.commit()


class MongoStore:
    """MongoDB-backed Store. Same methods and return shapes as SqliteStore.

    Collections mirror the SQLite tables (EMERGENT_DEPLOY.md section 4). activity and alerts carry an integer
    `id` (SQLite's AUTOINCREMENT rowid) the dashboard orders and paginates by. All timestamps are ISO strings.
    """

    def __init__(self, db=None):
        self.db = db if db is not None else get_db()
        ensure_indexes(self.db)

    # --- activity trace (read by the dashboard) -----------------------------------------------

    def log(self, kind: str, summary: str, *, rule: str | None = None, trigger_event_id: str | None = None,
            ticket_id: str | None = None, ticket_num: int | None = None, engineer: str | None = None,
            outcome: str | None = None, data: dict | None = None) -> None:
        self.db.activity.insert_one({
            "id": next_id(self.db, "activity"), "at": _now(), "kind": kind, "rule": rule,
            "trigger_event_id": trigger_event_id, "ticket_id": ticket_id or None, "ticket_num": ticket_num,
            "engineer": engineer, "outcome": outcome, "summary": summary[:1000],
            "data": json.dumps(data, default=str) if data else None,
        })

    def get(self, key: str) -> str | None:
        doc = self.db.kv.find_one({"key": key})
        return doc["value"] if doc else None

    def put(self, key: str, value: str) -> None:
        self.db.kv.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)

    def last_seq(self, ticket_id: str) -> int | None:
        doc = self.db.ticket_progress.find_one({"ticket_id": ticket_id})
        return doc["last_seq"] if doc else None

    def set_last_seq(self, ticket_id: str, seq: int) -> None:
        self.db.ticket_progress.update_one({"ticket_id": ticket_id}, {"$set": {"last_seq": seq}}, upsert=True)

    def schedule(self, rule: str, trigger_event_id: str, ticket_id: str, due_at: datetime,
                 engineer: str | None = None) -> bool:
        """True when the check is new. The unique (rule, trigger_event_id) index makes this insert-or-ignore."""
        try:
            self.db.checks.insert_one({
                "rule": rule, "trigger_event_id": trigger_event_id, "ticket_id": ticket_id,
                "due_at": due_at.isoformat(), "attempts": 0, "done": 0, "outcome": None,
                "engineer": engineer, "created_at": _now(), "finished_at": None,
            })
            return True
        except DuplicateKeyError:
            return False

    def due_checks(self, now: datetime, max_attempts: int = 5) -> list[tuple[str, str, str]]:
        cur = self.db.checks.find(
            {"done": 0, "due_at": {"$lte": now.isoformat()}, "attempts": {"$lt": max_attempts}}).sort("due_at", 1)
        return [(d["rule"], d["trigger_event_id"], d["ticket_id"]) for d in cur]

    def reschedule(self, rule: str, trigger_event_id: str, due_at: datetime) -> None:
        self.db.checks.update_one(
            {"rule": rule, "trigger_event_id": trigger_event_id},
            {"$set": {"due_at": due_at.isoformat(), "outcome": "waiting for reply"}})

    def finish_check(self, rule: str, trigger_event_id: str, outcome: str) -> None:
        self.db.checks.update_one(
            {"rule": rule, "trigger_event_id": trigger_event_id},
            {"$set": {"done": 1, "outcome": outcome, "finished_at": _now()}})

    def fail_check(self, rule: str, trigger_event_id: str, error: str) -> None:
        self.db.checks.update_one(
            {"rule": rule, "trigger_event_id": trigger_event_id},
            {"$inc": {"attempts": 1}, "$set": {"outcome": f"error: {error}"[:500]}})

    def already_alerted(self, rule: str, trigger_event_id: str) -> bool:
        return self.db.alerts.find_one({"rule": rule, "trigger_event_id": trigger_event_id}) is not None

    def count_alerts(self, rule: str) -> int:
        return self.db.alerts.count_documents({"rule": rule})

    # --- copy of Trinity data (notifier/sync.py) -------------------------------------------------

    def put_presences(self, presences: dict[str, str | None]) -> None:
        at = _now()
        for e, p in presences.items():
            self.db.presence.update_one({"_id": e.lower()}, {"$set": {"presence": p, "updated_at": at}}, upsert=True)

    def presences(self) -> dict[str, tuple[str | None, str]]:
        return {d["_id"]: (d.get("presence"), d["updated_at"]) for d in self.db.presence.find({})}

    def put_open_tickets(self, assignee: str, tickets: list[dict]) -> None:
        at, assignee = _now(), assignee.lower()
        self.db.open_tickets.delete_many({"assignee": assignee})
        for x in tickets:
            self.db.open_tickets.replace_one({"_id": x["ticket_id"]}, {
                "_id": x["ticket_id"], "num": x.get("num"), "subject": x.get("subject"), "level": x.get("level"),
                "assignee": assignee, "synced_at": at}, upsert=True)

    def open_tickets(self, assignee: str | None = None) -> list[dict]:
        q = {"assignee": assignee.lower()} if assignee else {}
        docs = self.db.open_tickets.find(q).sort([("assignee", 1), ("num", 1)])
        return [{"ticket_id": d["_id"], "num": d.get("num"), "subject": d.get("subject"), "level": d.get("level"),
                 "assignee": d["assignee"], "synced_at": d["synced_at"]} for d in docs]

    # --- R1: shift-end records -------------------------------------------------------------------

    def add_shift_record(self, rec: dict) -> bool:
        try:
            self.db.shift_records.insert_one({**rec, "_id": rec["key"], "updated_at": _now()})
            return True
        except DuplicateKeyError:
            return False

    def close_shift_record(self, key: str, outcome: str, offline_at: str | None, online_minutes: int) -> None:
        self.db.shift_records.update_one({"_id": key, "outcome": "open"}, {"$set": {
            "outcome": outcome, "offline_at": offline_at, "online_minutes": online_minutes, "updated_at": _now()}})

    def shift_records(self, since: str | None = None, until: str | None = None, outcome: str | None = None) -> list[dict]:
        q: dict = {}
        if since or until:
            q["shift_end"] = {**({"$gte": since} if since else {}), **({"$lt": until} if until else {})}
        if outcome:
            q["outcome"] = outcome
        return [{k: v for k, v in d.items() if k != "_id"} for d in self.db.shift_records.find(q).sort("shift_end", 1)]

    def take_lease(self, name: str, owner: str, ttl_seconds: float) -> bool:
        """Same contract as SqliteStore.take_lease. One upsert on the lease's _id: it matches when the lease is
        ours or expired; when it is held by someone else the upsert collides with the existing _id
        (DuplicateKeyError), so exactly one racer wins."""
        now = datetime.now(timezone.utc)
        until = (now + timedelta(seconds=ttl_seconds)).isoformat()
        try:
            self.db.leases.update_one(
                {"_id": name, "$or": [{"owner": owner}, {"expires_at": {"$lt": now.isoformat()}}]},
                {"$set": {"owner": owner, "expires_at": until}}, upsert=True)
            return True
        except DuplicateKeyError:
            return False

    def reset_trial_data(self, label: str) -> dict[str, int] | None:
        """Same contract as SqliteStore.reset_trial_data. Copies each collection to <name>_bak_<label> with $out,
        then deletes its documents (the collection and its unique indexes stay, so duplicate protection holds)."""
        done_key = f"reset_done:{label}"
        if self.get(done_key):
            return None
        suffix = "".join(c if c.isalnum() else "_" for c in label)
        counts = {}
        for name in RESET_TABLES:
            counts[name] = self.db[name].count_documents({})
            if counts[name]:
                self.db[name].aggregate([{"$match": {}}, {"$out": f"{name}_bak_{suffix}"}])
            self.db[name].delete_many({})
        self.put(done_key, _now())
        return counts

    def release_lease(self, name: str, owner: str) -> None:
        self.db.leases.delete_one({"_id": name, "owner": owner})

    def claim_alert(self, rule: str, trigger_event_id: str) -> bool:
        """Atomic reservation. An alerts row already existing means it was posted: never claim again. Otherwise
        the claim is a single insert into alert_claims; its unique index lets exactly one racer win."""
        if self.already_alerted(rule, trigger_event_id):
            return False
        try:
            self.db.alert_claims.insert_one(
                {"rule": rule, "trigger_event_id": trigger_event_id, "claimed_at": _now()})
            return True
        except DuplicateKeyError:
            return False

    def release_alert(self, rule: str, trigger_event_id: str) -> None:
        self.db.alert_claims.delete_one({"rule": rule, "trigger_event_id": trigger_event_id})

    def record_alert(self, rule: str, trigger_event_id: str, ticket_id: str, engineer: str, payload: dict,
                     *, ticket_num: int | None = None, subject: str | None = None, engineer_name: str | None = None,
                     associates: list[str] | None = None, reason: str | None = None, url: str | None = None,
                     dry_run: bool | None = None) -> None:
        """Insert-or-ignore: never a second row for the same (rule, trigger_event_id), like SQLite's INSERT OR
        IGNORE. An upsert keyed on that pair; a DuplicateKeyError is ignored only when that pair's row now exists
        (two upserts raced). Any other collision (the integer `id`) is logged and retried with a fresh id, so
        the row is never silently lost."""
        key = {"rule": rule, "trigger_event_id": trigger_event_id}
        for attempt in range(3):
            try:
                self.db.alerts.update_one(key, {"$setOnInsert": {
                    "id": next_id(self.db, "alerts"), "rule": rule, "trigger_event_id": trigger_event_id,
                    "ticket_id": ticket_id, "engineer": engineer, "payload": json.dumps(payload, default=str),
                    "sent_at": _now(), "ticket_num": ticket_num, "subject": subject, "engineer_name": engineer_name,
                    "associates": json.dumps(associates) if associates is not None else None, "reason": reason,
                    "url": url, "dry_run": None if dry_run is None else int(dry_run),
                }}, upsert=True)
                return
            except DuplicateKeyError as e:
                if self.already_alerted(rule, trigger_event_id):
                    return  # another copy recorded the same alert first
                log.error("record_alert %s %s: duplicate key other than (rule, trigger_event_id), attempt %d: %s",
                          rule, trigger_event_id, attempt + 1, e)
        raise RuntimeError(f"could not record alert {rule} {trigger_event_id}: alert id collisions")
