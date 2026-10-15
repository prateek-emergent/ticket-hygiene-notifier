"""Themes 7-8 (from shift-guardian): held then dropped; customer waiting 60+ min with no reply."""

import asyncio
from datetime import timedelta

from notifier.detectors import Rule, evaluate_held_then_dropped, evaluate_no_reply, find_triggers

from .factory import T0, Timeline
from .test_service import KRISHNA, LEAD, RENUKA, FakeClassifier, FakeTrinity, make_monitor

HOLD = timedelta(minutes=30)
WAIT = timedelta(minutes=60)
human = lambda e: bool(e) and e.endswith("@emergent.sh")  # noqa: E731


def _trigger(tl, rule):
    events = tl.events()
    return events, next(t.event for t in find_triggers(events, human) if t.rule == rule)


# --- theme 7 --------------------------------------------------------------------------------

def _held(minutes, note=False):
    tl = Timeline().customer(0).assign(1, KRISHNA, None, KRISHNA)
    if note:
        tl.note(10, KRISHNA)
    return tl.unassign(1 + minutes, KRISHNA, KRISHNA)


def test_theme7_flags_a_long_hold_then_self_unassign_and_reports_the_note():
    events, trig = _trigger(_held(45), Rule.HELD_THEN_DROPPED)
    f = evaluate_held_then_dropped(events, trig, HOLD)
    assert f and f.details["held_minutes"] == 45 and f.details["left_note"] is False
    assert "left no internal note" in f.reason
    events, trig = _trigger(_held(45, note=True), Rule.HELD_THEN_DROPPED)
    f = evaluate_held_then_dropped(events, trig, HOLD)
    assert f.details["left_note"] is True and "no internal note" not in f.reason


def test_theme7_skips_short_holds_escalations_and_tickets_already_l3():
    events, trig = _trigger(_held(20), Rule.HELD_THEN_DROPPED)
    assert evaluate_held_then_dropped(events, trig, HOLD) is None
    tl = _held(45).level(49, "L2", "L3", KRISHNA)  # escalated 3 min after dropping it: counts
    events, trig = _trigger(tl, Rule.HELD_THEN_DROPPED)
    assert evaluate_held_then_dropped(events, trig, HOLD) is None
    tl = Timeline().level(0, None, "L3").assign(1, KRISHNA, None, KRISHNA).unassign(50, KRISHNA, KRISHNA)
    events, trig = _trigger(tl, Rule.HELD_THEN_DROPPED)
    assert evaluate_held_then_dropped(events, trig, HOLD) is None


def test_theme7_is_only_about_engineers_dropping_their_own_ticket():
    tl = Timeline().assign(1, KRISHNA, None, KRISHNA).unassign(50, LEAD, KRISHNA)  # the associate un-assigned it
    assert not [t for t in find_triggers(tl.events(), human) if t.rule == Rule.HELD_THEN_DROPPED]


# --- theme 8 --------------------------------------------------------------------------------

def test_theme8_flags_a_customer_waiting_60_min_and_rechecks_when_not_yet():
    tl = Timeline().customer(0).assign(1, LEAD, None, KRISHNA)  # assigned by the associate: about the assignee
    events, trig = _trigger(tl, Rule.NO_REPLY)
    f = evaluate_no_reply(events, trig, T0 + timedelta(minutes=62), WAIT, human)
    assert f and f.engineer_email == KRISHNA and f.details["waited_minutes"] == 61 and "recheck_at" not in f.details
    # the customer wrote again at 40 after a reply at 10: waiting only since 40, so look again at 100
    tl = Timeline().customer(0).assign(1, LEAD, None, KRISHNA).reply(10, KRISHNA, "<p>On it</p>").customer(40)
    events, trig = _trigger(tl, Rule.NO_REPLY)
    assert evaluate_no_reply(events, trig, T0 + timedelta(minutes=62), WAIT, human) is None  # a person replied


def test_theme8_waits_for_a_late_customer_message():
    tl = Timeline().reply(-5, RENUKA, "<p>Done</p>").assign(1, LEAD, None, KRISHNA).customer(40)
    events, trig = _trigger(tl, Rule.NO_REPLY)
    f = evaluate_no_reply(events, trig, T0 + timedelta(minutes=62), WAIT, human)
    assert f.details["recheck_at"] == (T0 + timedelta(minutes=100)).isoformat()


def test_theme8_skips_reassigned_pending_escalated_and_no_customer_waiting():
    base = lambda: Timeline().customer(0).assign(1, LEAD, None, KRISHNA)  # noqa: E731
    later = T0 + timedelta(minutes=90)
    for tl in (base().assign(20, LEAD, KRISHNA, RENUKA),           # reassigned: its own check
               base().status(20, "OPEN", "PENDING", KRISHNA),      # waiting on the customer now
               base().tag(20, "l3_needs_review", KRISHNA),         # escalated
               Timeline().customer(-10).reply(-5, RENUKA, "<p>Fixed</p>").assign(1, LEAD, None, KRISHNA)):  # not waiting
        events, trig = _trigger(tl, Rule.NO_REPLY)
        assert evaluate_no_reply(events, trig, later, WAIT, human) is None


# --- end to end through the monitor ------------------------------------------------------------

class OpenTickets(FakeTrinity):
    """Theme 8 confirms live that the ticket is still OPEN and still the engineer's before alerting."""

    def _ticket(self, tid):
        t = super()._ticket(tid)
        t.status = "OPEN"
        return t


def test_both_themes_alert_through_the_normal_pipeline(tmp_path):
    held = Timeline("t7").customer(0).assign(1, KRISHNA, None, KRISHNA).reply(2, KRISHNA, "<p>Looking</p>") \
        .unassign(50, KRISHNA, KRISHNA)
    waiting = Timeline("t8").customer(0).assign(1, LEAD, None, KRISHNA)
    monitor, notifier = make_monitor(tmp_path, FakeClassifier(awaiting=True))
    monitor.cfg.enabled_rules = {Rule.HELD_THEN_DROPPED, Rule.NO_REPLY}
    trinity = OpenTickets({"t7": held, "t8": waiting})
    asyncio.run(monitor.discover(trinity))
    asyncio.run(monitor.run_due(trinity))
    titles = {b[0]["text"]["text"] for _, b in notifier.posts}
    assert any("then un-assigned it without escalating" in x for x in titles)
    assert any("Customer waiting 60+ min" in x for x in titles)
    assert len(notifier.posts) == 2  # t7's assignment was answered (reply at 2): no theme 8 for it


def test_theme8_does_not_alert_when_the_ticket_is_no_longer_open(tmp_path):
    monitor, notifier = make_monitor(tmp_path, FakeClassifier(awaiting=True))
    monitor.cfg.enabled_rules = {Rule.NO_REPLY}
    trinity = FakeTrinity({"t8": Timeline("t8").customer(0).assign(1, LEAD, None, KRISHNA)})  # live status: PENDING
    asyncio.run(monitor.discover(trinity))
    asyncio.run(monitor.run_due(trinity))
    assert notifier.posts == []
