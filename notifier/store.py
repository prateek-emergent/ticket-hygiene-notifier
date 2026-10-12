"""SQLite state: per-ticket progress, scheduled checks, sent alerts (for de-duplication), and the activity
trace the dashboard reads (every cycle, check, model call, alert and error, append-only).

The dashboard (python -m dashboard) opens the same file read-mostly; WAL mode lets it read while the
notifier writes."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

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


class Store:
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
