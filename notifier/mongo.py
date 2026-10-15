"""MongoDB wiring, shared by the notifier's Store and the dashboard's Data.

Storage moves to MongoDB when MONGO_URL is set (the deployed app); without it the code keeps using SQLite,
so local runs and the tests are unchanged. Connection details live in the environment, never in code:

    MONGO_URL   the app's MongoDB (e.g. mongodb://localhost:27017)
    DB_NAME     the database name (defaults to "ticket_hygiene")

Timestamps stay ISO-8601 UTC strings, exactly as in SQLite, so they remain comparable and the dashboard and
watchdog can still parse them with datetime.fromisoformat (EMERGENT_DEPLOY.md section 4, rule 5).
"""

from __future__ import annotations

import os

from pymongo import ASCENDING, MongoClient, ReturnDocument  # noqa: F401  (re-exported for the backends)
from pymongo.errors import DuplicateKeyError  # noqa: F401

_client: MongoClient | None = None


def mongo_enabled() -> bool:
    """True when storage should use MongoDB (MONGO_URL is set)."""
    return bool(os.environ.get("MONGO_URL", "").strip())


def get_db():
    """The shared database handle, built from MONGO_URL / DB_NAME. One client per process."""
    global _client
    if _client is None:
        _client = MongoClient(os.environ["MONGO_URL"])
    return _client[os.environ.get("DB_NAME") or "ticket_hygiene"]


def ensure_indexes(db) -> None:
    """Create the collections' indexes. Idempotent, so both the Store and the Data may call it.

    The unique indexes are what make the duplicate-alert rules hold: a second row for the same
    (rule, trigger_event_id) is rejected, and alert_claims is the atomic 'post at most once' lock.
    """
    db.activity.create_index("at")
    db.activity.create_index("ticket_id")
    db.activity.create_index([("rule", ASCENDING), ("trigger_event_id", ASCENDING)])
    db.activity.create_index("id", unique=True)

    db.kv.create_index("key", unique=True)
    db.ticket_progress.create_index("ticket_id", unique=True)
    db.checks.create_index([("rule", ASCENDING), ("trigger_event_id", ASCENDING)], unique=True)

    db.alerts.create_index([("rule", ASCENDING), ("trigger_event_id", ASCENDING)], unique=True)
    db.alerts.create_index("id", unique=True)
    db.alerts.create_index("sent_at")
    db.alerts.create_index("ticket_id")

    db.alert_claims.create_index([("rule", ASCENDING), ("trigger_event_id", ASCENDING)], unique=True)

    db.feedback.create_index([("rule", ASCENDING), ("trigger_event_id", ASCENDING)])
    db.feedback.create_index("id", unique=True)

    db.dashboard_sessions.create_index("token_hash", unique=True)
    db.actions.create_index("at")
    db.actions.create_index("id", unique=True)
    db.open_tickets.create_index("assignee")
    db.shift_records.create_index("shift_end")
    db.shift_records.create_index("outcome")

    # Raise each id counter to at least the highest id in use, so a lost or stale _counters document can't
    # hand out an id that already exists.
    for name in ("alerts", "activity", "feedback", "actions"):
        top = db[name].find_one({"id": {"$ne": None}}, sort=[("id", -1)], projection={"id": 1})
        if top is not None:
            db["_counters"].update_one({"_id": name}, {"$max": {"seq": top["id"]}}, upsert=True)


def next_id(db, name: str) -> int:
    """A per-collection auto-incrementing integer, standing in for SQLite's AUTOINCREMENT rowids."""
    doc = db["_counters"].find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return doc["seq"]
