from datetime import timedelta

from notifier.detectors import (
    Rule,
    evaluate_overwatch_close,
    evaluate_pending,
    evaluate_reassign,
    find_triggers,
)

from .factory import Timeline, is_human

GRACE = timedelta(minutes=5)
ANISH = "anish@emergent.sh"
KRISHNA = "krishna@emergent.sh"
RENUKA = "renuka@emergent.sh"


def trig(events, rule):
    return [t.event for t in find_triggers(events, is_human) if t.rule == rule]


# --- triggers --------------------------------------------------------------------------------


def test_overwatch_auto_pending_is_not_a_trigger():
    tl = (
        Timeline().customer(0).ow_trigger(0.1).ow_autosend(3, "<p>Fixed. Let me know which menus you checked.</p>")
        .ow_completed(3.01).status(3.02, "OPEN", "PENDING")  # System, like ticket 273250 seq 6
    )
    assert trig(tl.events(), Rule.PENDING_NO_QUESTION) == []


def test_self_assign_from_unassigned_is_not_a_reassign():
    tl = Timeline().customer(0).assign(1, ANISH, None, ANISH)
    assert trig(tl.events(), Rule.SELF_REASSIGN) == []


def test_lead_assigning_someone_else_is_not_a_self_reassign_trigger():
    tl = Timeline().customer(0).assign(1, ANISH, None, ANISH).assign(2, "lead@emergent.sh", ANISH, KRISHNA)
    assert trig(tl.events(), Rule.SELF_REASSIGN) == []


# --- rule 1 ----------------------------------------------------------------------------------


def test_pending_uses_reply_sent_shortly_after_status_change():
    # Ticket 272717: Overwatch auto-sent, Anish took it, set PENDING, *then* sent his own reply 2 min later.
    tl = (
        Timeline().customer(0).ow_trigger(0.1)
        .ow_autosend(2, "<p>Your code is reza123. If it still doesn't appear, let me know which menus you checked.</p>")
        .assign(3, ANISH, None, ANISH)
        .status(3.05, "OPEN", "PENDING", ANISH)
        .reply(5.4, ANISH, "<p>Once you make a top-up purchase, referral will be available. Feel free to reach out.</p>")
    )
    events = tl.events()
    [t] = trig(events, Rule.PENDING_NO_QUESTION)
    f = evaluate_pending(events, t, GRACE, is_human)
    assert f.needs_classification
    assert "top-up purchase" in f.reply.text  # Anish's reply, not Overwatch's
    assert f.engineer_email == ANISH
    assert f.details["reply_by_overwatch"] is False


def test_pending_without_any_reply_after_customer_is_flagged_without_llm():
    tl = (
        Timeline().customer(0).reply(5, KRISHNA, "<p>Can you share the job id?</p>")
        .customer(30, "Here it is: abc")
        .status(31, "OPEN", "PENDING", KRISHNA)
    )
    events = tl.events()
    [t] = trig(events, Rule.PENDING_NO_QUESTION)
    f = evaluate_pending(events, t, GRACE, is_human)
    assert f is not None and not f.needs_classification
    assert "No reply" in f.reason


def test_pending_reverted_by_engineer_within_grace_is_dropped():
    tl = (
        Timeline().customer(0).reply(5, KRISHNA, "<p>Done.</p>")
        .status(6, "OPEN", "PENDING", KRISHNA).status(7, "PENDING", "CLOSED", KRISHNA)
    )
    events = tl.events()
    [t] = trig(events, Rule.PENDING_NO_QUESTION)
    assert evaluate_pending(events, t, GRACE, is_human) is None


def test_pending_ignores_replies_after_the_next_customer_message():
    tl = (
        Timeline().customer(0).reply(1, KRISHNA, "<p>Please share your job id.</p>")
        .status(1.1, "OPEN", "PENDING", KRISHNA)
        .customer(2, "abc-123").status(2.01, "PENDING", "OPEN", reason="customer_reply")
        .reply(3, KRISHNA, "<p>Restored, all done.</p>")
    )
    events = tl.events()
    [t] = trig(events, Rule.PENDING_NO_QUESTION)
    f = evaluate_pending(events, t, GRACE, is_human)
    assert "job id" in f.reply.text


# --- rule 2 ----------------------------------------------------------------------------------


def test_grab_and_immediate_handback_is_not_flagged():
    # Ticket 273250 seq 15-17: Renuka took it from Krishna and gave it back 8 seconds later.
    tl = (
        Timeline().customer(0).assign(10, KRISHNA, None, KRISHNA)
        .assign(10.03, RENUKA, KRISHNA, RENUKA).assign(10.16, RENUKA, RENUKA, KRISHNA)
    )
    events = tl.events()
    [t] = trig(events, Rule.SELF_REASSIGN)
    assert evaluate_reassign(events, t, GRACE, exempt=set()) is None


def test_grab_is_flagged():
    tl = Timeline().customer(0).assign(10, KRISHNA, None, KRISHNA).assign(50, RENUKA, KRISHNA, RENUKA)
    events = tl.events()
    [t] = trig(events, Rule.SELF_REASSIGN)
    f = evaluate_reassign(events, t, GRACE, exempt=set())
    assert f.engineer_email == RENUKA
    assert f.details["previous_assignee"] == KRISHNA


def test_grab_by_associate_is_exempt():
    tl = Timeline().customer(0).assign(10, KRISHNA, None, KRISHNA).assign(50, RENUKA, KRISHNA, RENUKA)
    events = tl.events()
    [t] = trig(events, Rule.SELF_REASSIGN)
    assert evaluate_reassign(events, t, GRACE, exempt={RENUKA}) is None


# --- rule 3 ----------------------------------------------------------------------------------
ZEEL = "zeel@emergent.sh"


def test_picked_up_while_overwatch_running_then_system_auto_closed():
    tl = (
        Timeline().customer(0).ow_trigger(0.1)
        .assign(0.5, ANISH, None, ANISH)  # Overwatch still running: nothing produced yet
        .ow_autosend(3, "<p>Here's the fix.</p>").ow_completed(3.01).status(3.02, "OPEN", "PENDING")
        .status(60 * 48, "PENDING", "CLOSED", reason="auto_close_inactivity", idle_threshold_hours=48)
    )
    events = tl.events()
    [t] = trig(events, Rule.OVERWATCH_CLOSE)
    f = evaluate_overwatch_close(events, t, is_human)
    assert f.engineer_email == ANISH
    assert f.details["closed_by"] == "System auto-close after 48h of inactivity"


def test_system_close_right_after_overwatch_reply_is_flagged_when_grabbed_mid_run():
    tl = (
        Timeline().customer(0).ow_trigger(0.1).assign(1, ANISH, None, ANISH)
        .ow_autosend(2, "<p>Done.</p>").ow_completed(2.01).status(2.02, "OPEN", "CLOSED")
    )
    events = tl.events()
    [t] = trig(events, Rule.OVERWATCH_CLOSE)
    f = evaluate_overwatch_close(events, t, is_human)
    assert f is not None and f.details["closed_by"] == "System, right after Overwatch's reply"


def test_owner_before_run_thank_you_followup_is_skipped():
    # Ticket 270552: Zeel solved and closed it; customer replied, Overwatch answered, System closed.
    tl = (
        Timeline().customer(0).assign(1, ZEEL, None, ZEEL).reply(5, ZEEL, "<p>Fixed.</p>")
        .status(6, "OPEN", "CLOSED", ZEEL)
        .customer(600, "Thank you!").status(600.1, "CLOSED", "OPEN", reason="customer_reply")
        .ow_trigger(600.2).ow_autosend(601, "<p>Glad it's sorted!</p>").ow_completed(601.01)
        .status(601.02, "OPEN", "CLOSED")
    )
    events = tl.events()
    triggers = trig(events, Rule.OVERWATCH_CLOSE)
    assert len(triggers) == 1  # Zeel's own close is not a trigger
    assert evaluate_overwatch_close(events, triggers[0], is_human) is None


def test_owner_reassigning_to_self_mid_run_is_still_skipped():
    tl = (
        Timeline().customer(0).assign(1, ZEEL, None, ZEEL)
        .customer(60).ow_trigger(60.1).assign(60.5, ZEEL, ZEEL, ZEEL)
        .ow_autosend(62, "<p>x</p>").status(62.1, "OPEN", "CLOSED")
    )
    events = tl.events()
    [t] = trig(events, Rule.OVERWATCH_CLOSE)
    assert evaluate_overwatch_close(events, t, is_human) is None


def test_picked_up_after_overwatch_escalated_is_skipped():
    # Ticket 271501: Overwatch had already produced its escalation draft before Krishna took it.
    tl = (
        Timeline().customer(0).ow_trigger(0.1)
        ._add(1.5, type="ai_draft", visibility="internal", metadata={"overwatch_run_id": "r1"})
        .assign(1.7, KRISHNA, None, KRISHNA)
        .status(60 * 48, "PENDING", "CLOSED", reason="auto_close_inactivity")
    )
    events = tl.events()
    [t] = trig(events, Rule.OVERWATCH_CLOSE)
    assert evaluate_overwatch_close(events, t, is_human) is None


def test_picked_up_mid_run_but_replied_is_skipped():
    tl = (
        Timeline().customer(0).ow_trigger(0.1).assign(0.5, ANISH, None, ANISH)
        .reply(4, ANISH, "<p>I fixed it myself.</p>")
        .status(60 * 48, "PENDING", "CLOSED", reason="auto_close_inactivity")
    )
    events = tl.events()
    [t] = trig(events, Rule.OVERWATCH_CLOSE)
    assert evaluate_overwatch_close(events, t, is_human) is None


def test_assigned_mid_run_by_lead_is_skipped():
    tl = (
        Timeline().customer(0).ow_trigger(0.1).assign(0.5, "lead@emergent.sh", None, ANISH)
        .ow_autosend(2, "<p>x</p>").status(2.1, "OPEN", "CLOSED")
    )
    events = tl.events()
    [t] = trig(events, Rule.OVERWATCH_CLOSE)
    assert evaluate_overwatch_close(events, t, is_human) is None


def test_engineer_close_is_not_a_rule3_trigger():
    tl = (
        Timeline().customer(0).ow_trigger(0.1).assign(0.5, ANISH, None, ANISH)
        .ow_autosend(2, "<p>x</p>").status(9, "PENDING", "CLOSED", ANISH)
    )
    assert trig(tl.events(), Rule.OVERWATCH_CLOSE) == []


# --- rule 2: simultaneous-claim races --------------------------------------------------------
ADITYA, GOVIND, NANDIKA = "aditya@emergent.sh", "govind@emergent.sh", "nandika@emergent.sh"


def test_claim_race_is_not_flagged():
    # Ticket 272874: Aditya freed the ticket and four claims landed within 0.4 seconds.
    tl = (
        Timeline().customer(0).assign(1, ADITYA, None, ADITYA)
        .assign(60.000, GOVIND, None, GOVIND)
        .assign(60.004, NANDIKA, GOVIND, NANDIKA)
        .assign(60.006, GOVIND, NANDIKA, GOVIND)
        .assign(60.007, ADITYA, GOVIND, ADITYA)
    )
    events = tl.events()
    triggers = trig(events, Rule.SELF_REASSIGN)
    assert len(triggers) == 3
    assert [evaluate_reassign(events, t, GRACE, exempt=set()) for t in triggers] == [None, None, None]


def test_taking_a_ticket_held_for_hours_is_flagged():
    # Ticket 6ac0baf5: Arjya took Shashi's ticket after Shashi had held it for 36 hours.
    tl = Timeline().customer(0).assign(1, KRISHNA, None, KRISHNA).assign(60 * 36, RENUKA, KRISHNA, RENUKA)
    events = tl.events()
    [t] = trig(events, Rule.SELF_REASSIGN)
    f = evaluate_reassign(events, t, GRACE, exempt=set())
    assert f is not None and f.details["previous_held_for_minutes"] == 60 * 36 - 1


def test_reply_sent_minutes_after_pending_is_the_one_judged():
    # Ticket 271615: PENDING at 09:51, the reply (with an ask) went out at 09:58.
    tl = (
        Timeline().customer(0).assign(1, ANISH, None, ANISH).status(5, "OPEN", "PENDING", ANISH)
        .reply(12, ANISH, "<p>Please publish the translated version and confirm it looks right.</p>")
    )
    events = tl.events()
    [t] = trig(events, Rule.PENDING_NO_QUESTION)
    f = evaluate_pending(events, t, timedelta(minutes=30), is_human)
    assert f.needs_classification and "confirm it looks right" in f.reply.text


def test_unassigned_before_system_close_is_not_flagged():
    # Ticket 270370: picked up mid-run, then unassigned; System auto-closed it two days later, unowned.
    tl = (
        Timeline().customer(0).ow_trigger(0.1).assign(0.5, ANISH, None, ANISH)
        .ow_autosend(2, "<p>x</p>").ow_completed(2.01).status(2.02, "OPEN", "PENDING")
        .unassign(60, ANISH, ANISH)
        .status(60 * 48, "PENDING", "CLOSED", reason="auto_close_inactivity")
    )
    events = tl.events()
    [t] = trig(events, Rule.OVERWATCH_CLOSE)
    assert evaluate_overwatch_close(events, t, is_human) is None


def test_reassigned_after_unassign_mid_run_counts_as_new_owner():
    # Owner unassigned themselves; while the next Overwatch run was going, someone else took the ticket.
    tl = (
        Timeline().customer(0).assign(1, ZEEL, None, ZEEL).unassign(2, ZEEL, ZEEL)
        .customer(60).ow_trigger(60.1).assign(60.5, ANISH, None, ANISH)
        .ow_autosend(62, "<p>Done.</p>").ow_completed(62.01).status(62.02, "OPEN", "CLOSED")
    )
    events = tl.events()
    [t] = trig(events, Rule.OVERWATCH_CLOSE)
    f = evaluate_overwatch_close(events, t, is_human)
    assert f is not None and f.engineer_email == ANISH
