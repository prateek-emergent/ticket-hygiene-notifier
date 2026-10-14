"""The duplicate-alert rules, proven on MongoDB too (EMERGENT_DEPLOY.md section 4, "Done means").

Mirrors the two SQLite tests in test_service.py that must not break, but runs them against a MongoStore
backed by mongomock, so the atomic claim and insert-or-ignore are shown to hold on MongoDB as well:
  - test_service.py::test_two_notifier_copies_on_one_database_post_each_alert_once
  - test_service.py::test_a_failed_post_releases_the_claim_so_it_is_retried
"""

import asyncio
import multiprocessing
import os
import uuid
from datetime import timedelta

import mongomock
import pytest

from notifier.config import Config
from notifier.detectors import Rule
from notifier.service import Monitor
from notifier.store import MongoStore
from notifier.teams import Directory, Team

from .factory import Timeline
from .test_service import KRISHNA, LEAD, RENUKA, CapturingNotifier, FakeClassifier, FakeTrinity


def make_mongo_monitor(tmp_path, db, classifier):
    cfg = Config(
        trinity_url="x", trinity_headers={}, ticket_url_template="https://trinity/tickets/{id}",
        slack_token=None, slack_channel="#hygiene", dry_run=True, classifier_model="m",
        classifier_effort="low", classifier_fallbacks=False, teams_file=tmp_path / "t.yaml",
        state_db=tmp_path / "unused.db", poll_seconds=60, initial_lookback=timedelta(days=3650),
        grace={r: timedelta(minutes=5) for r in Rule}, human_domains=("@emergent.sh",),
    )
    directory = Directory([Team("A", [LEAD], [KRISHNA, RENUKA])])
    notifier = CapturingNotifier()
    return Monitor(cfg, directory, classifier, notifier, MongoStore(db=db)), notifier


def test_mongo_two_notifier_copies_on_one_database_post_each_alert_once(tmp_path):
    db = mongomock.MongoClient().state  # both copies share one MongoDB
    tl = (
        Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA)
        .reply(2, KRISHNA, "<p>Your deploy is fixed. Feel free to reach out.</p>")
        .status(2.1, "OPEN", "PENDING", KRISHNA)
    )

    class SlowClassifier(FakeClassifier):  # both copies are judging at the same time
        async def classify(self, *a, **kw):
            await asyncio.sleep(0.05)
            return await super().classify(*a, **kw)

    a, posts_a = make_mongo_monitor(tmp_path, db, SlowClassifier(awaiting=False))
    b, posts_b = make_mongo_monitor(tmp_path, db, SlowClassifier(awaiting=False))
    trinity = FakeTrinity({"tk": tl})

    async def both():
        await a.discover(trinity)
        await b.discover(trinity)
        await asyncio.gather(a.run_due(trinity), b.run_due(trinity))

    asyncio.run(both())
    assert len(posts_a.posts) + len(posts_b.posts) == 1
    assert db.alerts.count_documents({}) == 1  # and exactly one row was recorded


def test_mongo_a_failed_post_releases_the_claim_so_it_is_retried():
    store = MongoStore(db=mongomock.MongoClient().state)
    assert store.claim_alert("r", "e1") and not store.claim_alert("r", "e1")
    store.release_alert("r", "e1")
    assert store.claim_alert("r", "e1")
    store.record_alert("r", "e2", "t", "x@emergent.sh", {})
    assert not store.claim_alert("r", "e2")  # recorded before claims existed: still never re-posted


def test_mongo_record_alert_survives_a_lost_id_counter():
    db = mongomock.MongoClient().state
    store = MongoStore(db=db)
    store.record_alert("r", "e1", "t", "x@emergent.sh", {})
    db["_counters"].delete_one({"_id": "alerts"})  # e.g. a restore without _counters: next id would be 1 again
    store.record_alert("r", "e2", "t", "x@emergent.sh", {})
    store.record_alert("r", "e2", "t", "x@emergent.sh", {})  # and a repeat is still ignored
    assert sorted(d["trigger_event_id"] for d in db.alerts.find()) == ["e1", "e2"]
    assert len({d["id"] for d in db.alerts.find()}) == 2


def _claim_keys(args):
    url, db_name = args
    from pymongo import MongoClient

    store = MongoStore(db=MongoClient(url)[db_name])
    return sum(store.claim_alert("race", f"k{i}") for i in range(100))


@pytest.mark.skipif(not os.environ.get("MONGO_TEST_URL"), reason="MONGO_TEST_URL is not set (needs a real MongoDB)")
def test_real_mongo_claim_alert_has_exactly_one_winner_across_processes():
    from pymongo import MongoClient

    url, db_name = os.environ["MONGO_TEST_URL"], f"hygiene_race_{uuid.uuid4().hex[:8]}"
    try:
        MongoStore(db=MongoClient(url)[db_name])  # create the unique indexes before the race
        with multiprocessing.get_context("spawn").Pool(8) as pool:
            wins = pool.map(_claim_keys, [(url, db_name)] * 8)
        assert sum(wins) == 100
    finally:
        MongoClient(url).drop_database(db_name)
