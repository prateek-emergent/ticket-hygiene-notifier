"""End-to-end: poll loop against a fake Trinity, fake classifier, capturing Slack output."""

import asyncio
from datetime import datetime, timedelta, timezone

from notifier.classifier import Verdict
from notifier.config import Config
from notifier.detectors import Rule
from notifier.models import Event, Ticket
from notifier.service import Monitor
from notifier.slack import SlackNotifier
from notifier.store import Store
from notifier.teams import Directory, Team

from .factory import Timeline

KRISHNA = "krishna@emergent.sh"
RENUKA = "renuka@emergent.sh"
LEAD = "lead@emergent.sh"


class FakeTrinity:
    def __init__(self, timelines: dict[str, Timeline]):
        self.timelines = timelines

    async def tickets_updated_since(self, since):
        return [self._ticket(tid) for tid in self.timelines]

    async def events_after(self, tid, after_seq):
        return [e for e in self.timelines[tid].events() if e.seq > after_seq]

    async def all_events(self, tid):
        return self.timelines[tid].events()

    async def get_ticket(self, tid):
        return self._ticket(tid)

    def _ticket(self, tid):
        return Ticket.from_api({"id": tid, "num": 42, "subject": "App won't deploy", "status": "PENDING",
                                "assigned_to": KRISHNA, "updated_at": datetime.now(timezone.utc).isoformat()})


class FakeClassifier:
    def __init__(self, awaiting: bool):
        self.awaiting = awaiting
        self.calls = 0

    async def classify(self, reply_text, customer_text, subject):
        self.calls += 1
        return Verdict(self.awaiting, "Can you share the job id?" if self.awaiting else "",
                       "Reply answers the question and asks nothing of the customer.", "high")


class CapturingNotifier(SlackNotifier):
    def __init__(self):
        super().__init__(None, "#hygiene", True, {LEAD: "U_LEAD"})
        self.posts = []

    async def post(self, text, blocks):
        self.posts.append((text, blocks))


def make_monitor(tmp_path, classifier):
    cfg = Config(
        trinity_url="x", trinity_headers={}, ticket_url_template="https://trinity/tickets/{id}",
        slack_token=None, slack_channel="#hygiene", dry_run=True, classifier_model="m",
        classifier_effort="low", classifier_fallbacks=False, teams_file=tmp_path / "t.yaml",
        state_db=tmp_path / "s.db", poll_seconds=60, initial_lookback=timedelta(days=3650),
        grace={r: timedelta(minutes=5) for r in Rule}, human_domains=("@emergent.sh",),
    )
    directory = Directory([Team("A", [LEAD], [KRISHNA, RENUKA])])
    notifier = CapturingNotifier()
    return Monitor(cfg, directory, classifier, notifier, Store(cfg.state_db)), notifier


def run(coro):
    return asyncio.run(coro)


def test_pending_without_question_alerts_associate_once(tmp_path):
    tl = (
        Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA)
        .reply(2, KRISHNA, "<p>Your deploy is fixed. Feel free to reach out.</p>")
        .status(2.1, "OPEN", "PENDING", KRISHNA)
    )
    clf = FakeClassifier(awaiting=False)
    monitor, notifier = make_monitor(tmp_path, clf)
    trinity = FakeTrinity({"tk": tl})

    run(monitor.discover(trinity))
    run(monitor.run_due(trinity))
    run(monitor.discover(trinity))  # second cycle must not re-alert
    run(monitor.run_due(trinity))

    assert clf.calls == 1
    assert len(notifier.posts) == 1
    body = "\n".join(b["text"]["text"] for b in notifier.posts[0][1] if b["type"] == "section")
    assert "<@U_LEAD>" in body
    assert "https://trinity/tickets/tk" in body
    assert "krishna@emergent.sh" in body
    assert "Your deploy is fixed" in body


def test_activity_trace_records_the_whole_check(tmp_path):
    import json

    tl = (
        Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA)
        .reply(2, KRISHNA, "<p>Your deploy is fixed.</p>")
        .status(2.1, "OPEN", "PENDING", KRISHNA)
    )
    monitor, _ = make_monitor(tmp_path, FakeClassifier(awaiting=False))
    trinity = FakeTrinity({"tk": tl})
    monitor.announce("test")
    run(monitor.discover(trinity))
    run(monitor.run_due(trinity))

    db = monitor.store.db
    kinds = [r[0] for r in db.execute("SELECT kind FROM activity WHERE rule='pending_without_open_question' ORDER BY id")]
    assert kinds == ["scheduled", "model", "alert", "check"]
    assert db.execute("SELECT outcome FROM activity WHERE kind='check' AND rule='pending_without_open_question'").fetchone()[0] == "flagged"
    assert {r[0] for r in db.execute("SELECT kind FROM activity")} >= {"start", "cycle"}
    num, subject, associates, url, dry = db.execute(
        "SELECT ticket_num, subject, associates, url, dry_run FROM alerts").fetchone()
    assert json.loads(associates) == ["lead@emergent.sh"] and url == "https://trinity/tickets/tk" and dry == 1
    assert monitor.store.get("heartbeat") and json.loads(monitor.store.get("notifier_info"))["mode"] == "test"
    engineer, finished = db.execute("SELECT engineer, finished_at FROM checks WHERE rule='pending_without_open_question'").fetchone()
    assert engineer == KRISHNA and finished


def test_pending_with_question_is_quiet(tmp_path):
    tl = (
        Timeline("tk").customer(0).reply(2, KRISHNA, "<p>Can you share the job id?</p>")
        .status(2.1, "OPEN", "PENDING", KRISHNA)
    )
    monitor, notifier = make_monitor(tmp_path, FakeClassifier(awaiting=True))
    trinity = FakeTrinity({"tk": tl})
    run(monitor.discover(trinity))
    run(monitor.run_due(trinity))
    assert notifier.posts == []


def test_reassign_alert_names_previous_assignee(tmp_path):
    tl = Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA).assign(30, RENUKA, KRISHNA, RENUKA)
    monitor, notifier = make_monitor(tmp_path, FakeClassifier(awaiting=True))
    trinity = FakeTrinity({"tk": tl})
    run(monitor.discover(trinity))
    run(monitor.run_due(trinity))
    [(text, blocks)] = notifier.posts
    body = "\n".join(b["text"]["text"] for b in blocks if b["type"] == "section")
    assert "Taken from:* krishna@emergent.sh" in body
    assert "renuka@emergent.sh" in body


def test_check_not_due_until_grace_elapses(tmp_path):
    now = datetime.now(timezone.utc)
    tl = Timeline("tk")
    tl.customer(0).assign(1, KRISHNA, None, KRISHNA).assign(2, RENUKA, KRISHNA, RENUKA)
    # Move the timeline to "just now" so the 5-minute grace has not elapsed.
    from .factory import T0
    shift = now - (T0 + timedelta(minutes=2))
    for r in tl.raw:
        r["created_at"] = (datetime.fromisoformat(r["created_at"]) + shift).isoformat()
    monitor, notifier = make_monitor(tmp_path, FakeClassifier(awaiting=True))
    trinity = FakeTrinity({"tk": tl})
    run(monitor.discover(trinity))
    run(monitor.run_due(trinity))
    assert notifier.posts == []
    assert monitor.store.due_checks(now + timedelta(minutes=6))  # becomes due later


OUTSIDER = "someone.else@emergent.sh"  # a real engineer, but not in teams.yaml


def _run_all(tmp_path, tl, awaiting=False):
    monitor, notifier = make_monitor(tmp_path, FakeClassifier(awaiting=awaiting))
    trinity = FakeTrinity({"tk": tl})
    run(monitor.discover(trinity))
    run(monitor.run_due(trinity))
    return notifier.posts


def test_unlisted_engineer_is_never_flagged(tmp_path):
    pending = (
        Timeline("tk").customer(0).assign(1, OUTSIDER, None, OUTSIDER)
        .reply(2, OUTSIDER, "<p>Fixed. Feel free to reach out.</p>").status(2.1, "OPEN", "PENDING", OUTSIDER)
    )
    grab = Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA).assign(30, OUTSIDER, KRISHNA, OUTSIDER)
    overwatch = (
        Timeline("tk").customer(0).ow_trigger(0.1).assign(0.5, OUTSIDER, None, OUTSIDER)
        .ow_autosend(2, "<p>Done.</p>").ow_completed(2.01).status(2.02, "OPEN", "CLOSED")
    )
    for i, tl in enumerate((pending, grab, overwatch)):
        d = tmp_path / str(i)
        d.mkdir()
        assert _run_all(d, tl) == []


def test_listed_engineer_taking_from_unlisted_colleague_is_flagged(tmp_path):
    tl = Timeline("tk").customer(0).assign(1, OUTSIDER, None, OUTSIDER).assign(30, RENUKA, OUTSIDER, RENUKA)
    [(_, blocks)] = _run_all(tmp_path, tl)
    assert "Taken from:* someone.else@emergent.sh" in blocks[1]["text"]["text"]


def test_listed_engineer_overwatch_pickup_is_flagged(tmp_path):
    tl = (
        Timeline("tk").customer(0).ow_trigger(0.1).assign(0.5, KRISHNA, None, KRISHNA)
        .ow_autosend(2, "<p>Done.</p>").ow_completed(2.01).status(2.02, "OPEN", "CLOSED")
    )
    [(_, blocks)] = _run_all(tmp_path, tl)
    assert "<@U_LEAD>" in blocks[1]["text"]["text"]


def test_pending_with_no_reply_yet_waits_then_alerts(tmp_path):
    from datetime import datetime, timedelta, timezone
    from .factory import T0

    # PENDING set 6 minutes ago with no reply yet: inside the 30-minute reply window, so no alert yet.
    tl = Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA).status(2, "OPEN", "PENDING", KRISHNA)
    shift = datetime.now(timezone.utc) - timedelta(minutes=6) - (T0 + timedelta(minutes=2))
    for r in tl.raw:
        r["created_at"] = (datetime.fromisoformat(r["created_at"]) + shift).isoformat()
    monitor, notifier = make_monitor(tmp_path, FakeClassifier(awaiting=False))
    trinity = FakeTrinity({"tk": tl})
    run(monitor.discover(trinity))
    run(monitor.run_due(trinity))
    assert notifier.posts == []
    [(rule, _, _)] = monitor.store.due_checks(datetime.now(timezone.utc) + timedelta(minutes=10))
    assert rule == "pending_without_open_question"

    # Window closes with still no reply: now it alerts.
    monitor.cfg.pending_reply_window = timedelta(minutes=5)
    monitor.store.reschedule(rule, tl.raw[-1]["id"], datetime.now(timezone.utc))
    run(monitor.run_due(trinity))
    [(_, blocks)] = notifier.posts
    assert "No reply was sent" in blocks[2]["text"]["text"]


def test_long_reply_quote_shows_the_end():
    from notifier.slack import _quote

    text = "Background explanation. " * 60 + "Could you confirm the job ID?"
    q = _quote(text)
    assert q.startswith("> … ") and q.endswith("Could you confirm the job ID?") and len(q) < 700


class UncertainClassifier:
    async def classify(self, reply_text, customer_text, subject):
        return Verdict(True, "", "Unclear whether the reply asks the customer anything (von: 45%).", "low",
                       probability=0.45, uncertain=True)


def test_uncertain_verdict_skips_alert_unless_enabled(tmp_path):
    def timeline():
        return (
            Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA)
            .reply(2, KRISHNA, "<p>Please check and tell us if it still fails.</p>")
            .status(2.1, "OPEN", "PENDING", KRISHNA)
        )

    for alert_uncertain, expected_posts in ((False, 0), (True, 1)):
        d = tmp_path / str(alert_uncertain)
        d.mkdir()
        monitor, notifier = make_monitor(d, UncertainClassifier())
        monitor.cfg.alert_uncertain = alert_uncertain
        trinity = FakeTrinity({"tk": timeline()})
        run(monitor.discover(trinity))
        run(monitor.run_due(trinity))
        assert len(notifier.posts) == expected_posts
        if expected_posts:
            body = notifier.posts[0][1][2]["text"]["text"]
            assert "Unclear" in body and "low confidence" in body


def test_two_notifier_copies_on_one_database_post_each_alert_once(tmp_path):
    """If the platform ever runs two copies, each alert must still go out once (Store.claim_alert)."""
    tl = (
        Timeline("tk").customer(0).assign(1, KRISHNA, None, KRISHNA)
        .reply(2, KRISHNA, "<p>Your deploy is fixed. Feel free to reach out.</p>")
        .status(2.1, "OPEN", "PENDING", KRISHNA)
    )

    class SlowClassifier(FakeClassifier):  # both copies are judging at the same time
        async def classify(self, *a, **kw):
            await asyncio.sleep(0.05)
            return await super().classify(*a, **kw)

    a, posts_a = make_monitor(tmp_path, SlowClassifier(awaiting=False))
    b, posts_b = make_monitor(tmp_path, SlowClassifier(awaiting=False))  # same s.db
    trinity = FakeTrinity({"tk": tl})

    async def both():
        await a.discover(trinity)
        await b.discover(trinity)
        await asyncio.gather(a.run_due(trinity), b.run_due(trinity))

    run(both())
    assert len(posts_a.posts) + len(posts_b.posts) == 1


def test_a_failed_post_releases_the_claim_so_it_is_retried(tmp_path):
    store = Store(tmp_path / "s.db")
    assert store.claim_alert("r", "e1") and not store.claim_alert("r", "e1")
    store.release_alert("r", "e1")
    assert store.claim_alert("r", "e1")
    store.record_alert("r", "e2", "t", "x@emergent.sh", {})
    assert not store.claim_alert("r", "e2")  # recorded before claims existed: still never re-posted
