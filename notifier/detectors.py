"""Hygiene rules, as pure functions over a ticket's ordered event list.

Each rule has two halves:
  * a trigger predicate: which single audit event makes the rule worth checking
  * an evaluator: run after a grace period, with the full timeline, decides whether to flag

The grace period exists because the timeline is not atomic: engineers routinely set a ticket to
PENDING a few seconds *before* the reply that justifies it lands, and reassignments are sometimes
undone within seconds (a mis-click). Evaluating late lets those settle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from typing import Callable, Iterable

from .models import Event

IsHuman = Callable[[str | None], bool]


class Rule(str, Enum):
    PENDING_NO_QUESTION = "pending_without_open_question"
    SELF_REASSIGN = "reassigned_from_colleague"
    OVERWATCH_CLOSE = "picked_up_during_overwatch_run"
    STATUS_SHIFT = "status_not_matching_shift"
    OFF_SHIFT_HOLD = "ticket_held_off_shift"
    L3_ESCALATION = "l3_escalation_check"
    ESCALATION_NOTE = "escalation_note_quality"


RULE_TITLES = {
    Rule.PENDING_NO_QUESTION: "Moved to Pending with no open question for the customer",
    Rule.SELF_REASSIGN: "Ticket reassigned from a colleague",
    Rule.OVERWATCH_CLOSE: "Picked up while Overwatch was running, then closed by System",
    Rule.STATUS_SHIFT: "Trinity status doesn't match shift",
    Rule.OFF_SHIFT_HOLD: "Customer waiting on a ticket held by an off-shift engineer",
    Rule.L3_ESCALATION: "L3 escalation the knowledge base says L2 could handle",
    Rule.ESCALATION_NOTE: "L3 escalation with a missing or vague RCA note",
}

# Rules triggered by a ticket timeline event. Rules 4-5 run on a schedule instead (notifier/shift_checks.py).
EVENT_RULES = {Rule.PENDING_NO_QUESTION, Rule.SELF_REASSIGN, Rule.OVERWATCH_CLOSE, Rule.L3_ESCALATION,
               Rule.ESCALATION_NOTE}

# One escalation is often several audit events in the same minute (level -> L3, tag l3_needs_review, unassign).
# Events by the same engineer within this window are one escalation.
ESCALATION_DEDUPE = timedelta(minutes=30)
ESCALATION_TAGS = ("l3_needs_review", "real_l3")


@dataclass
class Trigger:
    rule: Rule
    event: Event


@dataclass
class Finding:
    rule: Rule
    ticket_id: str
    trigger_event_id: str
    engineer_email: str
    engineer_name: str | None
    reason: str
    details: dict = field(default_factory=dict)
    # Rule 1 only: the reply the classifier must read before we know whether to flag.
    needs_classification: bool = False
    # Rule 6 only: the escalation must be judged against the knowledge base (details["context"]).
    needs_kb_check: bool = False
    # Rule 7 only: the escalation note must be judged against the RCA standard (details["note"]).
    needs_rca_check: bool = False
    reply: Event | None = None
    customer_message: Event | None = None


def _same(a: str | None, b: str | None) -> bool:
    return bool(a) and bool(b) and a.strip().lower() == b.strip().lower()


def is_escalation(e: Event) -> bool:
    """A move to L3: level set to L3 (from L1/L2), or tag l3_needs_review / real_l3 added."""
    if e.type != "audit":
        return False
    if e.action == "level_changed":
        return e.new_value == "L3" and e.old_value in ("L1", "L2")
    return e.action == "tag_added" and e.new_value in ESCALATION_TAGS


def first_of_escalation(events: Iterable[Event], e: Event) -> bool:
    """True when no earlier move to L3 by the same person happened within ESCALATION_DEDUPE before `e`."""
    return not any(
        o.seq < e.seq and is_escalation(o) and _same(o.author_email, e.author_email)
        and e.created_at - o.created_at <= ESCALATION_DEDUPE
        for o in events
    )


def find_triggers(events: Iterable[Event], is_human: IsHuman) -> list[Trigger]:
    events = list(events)
    triggers: list[Trigger] = []
    for e in events:
        if is_escalation(e) and is_human(e.author_email) and first_of_escalation(events, e):
            # An engineer moving a ticket to L3: judged against the KB (rule 6), note checked (rule 7).
            triggers.append(Trigger(Rule.L3_ESCALATION, e))
            triggers.append(Trigger(Rule.ESCALATION_NOTE, e))
            continue
        if e.type != "audit":
            continue
        if e.action == "status_changed":
            if e.new_value == "PENDING" and e.old_value != "PENDING" and is_human(e.author_email):
                # System-driven OPEN->PENDING (Overwatch auto-send) is excluded on purpose.
                triggers.append(Trigger(Rule.PENDING_NO_QUESTION, e))
            elif e.new_value == "CLOSED" and e.old_value != "CLOSED" and not is_human(e.author_email):
                # Only System closes (Overwatch resolution or inactivity auto-close) are credited
                # to the assignee without them acting; engineer closes are their own call.
                triggers.append(Trigger(Rule.OVERWATCH_CLOSE, e))
        elif e.action == "assigned":
            if (
                is_human(e.old_value)
                and _same(e.author_email, e.new_value)
                and not _same(e.old_value, e.new_value)
            ):
                triggers.append(Trigger(Rule.SELF_REASSIGN, e))
    return triggers


# --- Rule 1: Pending without an open question ------------------------------------------------


def evaluate_pending(events: list[Event], trigger: Event, window: timedelta, is_human: IsHuman) -> Finding | None:
    """`window`: how long after the PENDING change a reply still counts as the one that justifies it.
    Engineers often set PENDING first and send the reply minutes later (ticket 271615: 7 minutes)."""
    horizon = trigger.created_at + window

    # Engineer changed their mind inside the window (e.g. closed it instead): not this rule.
    for e in events:
        if (
            e.seq > trigger.seq
            and e.created_at <= horizon
            and e.type == "audit"
            and e.action == "status_changed"
            and e.new_value != "PENDING"
            and is_human(e.author_email)
        ):
            return None

    last_inbound = None
    for e in events:
        if e.seq < trigger.seq and e.is_customer_message:
            last_inbound = e
    # A customer message after the trigger ends the window: replies after it answer something else.
    next_inbound_seq = next((e.seq for e in events if e.seq > trigger.seq and e.is_customer_message), None)

    reply = None
    for e in events:
        if not e.is_outbound_message or e.is_system_notice:
            continue
        if last_inbound is not None and e.seq < last_inbound.seq:
            continue
        if next_inbound_seq is not None and e.seq > next_inbound_seq:
            continue
        if e.created_at > horizon:
            continue
        reply = e

    base = dict(
        rule=Rule.PENDING_NO_QUESTION,
        ticket_id=trigger.ticket_id,
        trigger_event_id=trigger.id,
        engineer_email=trigger.author_email or "",
        engineer_name=trigger.author,
        customer_message=last_inbound,
    )
    if reply is None:
        return Finding(
            **base,
            reason="No reply was sent after the customer's latest message, so nothing is awaiting the customer.",
            details={"pending_at": trigger.created_at.isoformat(), "no_reply": True},
        )
    return Finding(
        **base,
        reason="",  # filled in by the classifier
        needs_classification=True,
        reply=reply,
        details={
            "pending_at": trigger.created_at.isoformat(),
            "reply_by_overwatch": reply.is_overwatch_auto_send or reply.author_email is None,
            "reply_author": reply.author or "System",
        },
    )


# --- Rule 2: Reassigned from a colleague -----------------------------------------------------


def evaluate_reassign(
    events: list[Event],
    trigger: Event,
    grace: timedelta,
    exempt: set[str],
    min_hold: timedelta = timedelta(minutes=2),
) -> Finding | None:
    if (trigger.author_email or "").lower() in exempt:
        return None

    # Claim races: when a ticket is freed, several engineers often click "take" within the same second
    # (ticket 272874: four assignments in 0.4 s). Taking a ticket someone held for less than `min_hold`
    # is that race, not taking over a colleague's work.
    held_since = None
    for e in events:
        if e.seq >= trigger.seq:
            break
        if e.type == "audit" and e.action == "assigned" and _same(e.new_value, trigger.old_value):
            held_since = e.created_at
    if held_since is not None and trigger.created_at - held_since < min_hold:
        return None

    horizon = trigger.created_at + grace
    for e in events:
        if (
            e.seq > trigger.seq
            and e.created_at <= horizon
            and e.type == "audit"
            and e.action == "assigned"
            and _same(e.new_value, trigger.old_value)
        ):
            return None  # handed straight back: a mis-click, not a grab
    return Finding(
        rule=Rule.SELF_REASSIGN,
        ticket_id=trigger.ticket_id,
        trigger_event_id=trigger.id,
        engineer_email=trigger.author_email or "",
        engineer_name=trigger.author,
        reason=f"Took the ticket from {trigger.old_value} and assigned it to themselves.",
        details={
            "previous_assignee": trigger.old_value,
            "reassigned_at": trigger.created_at.isoformat(),
            "previous_held_for_minutes": (
                round((trigger.created_at - held_since).total_seconds() / 60) if held_since else None
            ),
        },
    )


# --- Rule 3: Picked up while Overwatch was running, then closed by System ---------------------


def _run_active_at(events: list[Event], seq: int) -> Event | None:
    """The ai_triggered event of an Overwatch run that had started but produced nothing yet at `seq`
    (Trinity's "agent running" state). A run ends at its first output: auto-send, draft/escalation,
    completion or discard."""
    active = None
    for e in events:
        if e.seq >= seq:
            break
        if e.type == "audit" and e.action == "ai_triggered":
            run_id = e.metadata.get("overwatch_run_id")
            ended = any(
                x.seq < seq and x.metadata.get("overwatch_run_id") == run_id and x.action != "ai_triggered"
                for x in events
                if x.seq > e.seq
            )
            if not ended:
                active = e
    return active


def _assignee_at(events: list[Event], seq: int) -> str | None:
    owner = None
    for e in events:
        if e.seq >= seq:
            break
        if e.type == "audit" and e.action == "assigned":
            owner = e.new_value
        elif e.type == "audit" and e.action == "unassigned":
            owner = None
    return owner


def _close_reason(events: list[Event], close: Event) -> str:
    if close.metadata.get("reason") == "auto_close_inactivity":
        hours = close.metadata.get("idle_threshold_hours")
        return f"System auto-close after {hours}h of inactivity" if hours else "System auto-close (inactivity)"
    prior = [e for e in events if e.seq < close.seq and e.is_outbound_message]
    if prior and prior[-1].is_overwatch_auto_send:
        return "System, right after Overwatch's reply"
    return "System"


def evaluate_overwatch_close(events: list[Event], trigger: Event, is_human: IsHuman) -> Finding | None:
    """Flag only when ALL hold:
      * the ticket was closed by System (enforced by the trigger),
      * the assignee at close assigned it to themselves,
      * they did so while an Overwatch run was in progress,
      * it was not already theirs when that run started (e.g. engineer solved + closed it, customer
        replied "thank you", Overwatch answered and System closed: not flagged),
      * they sent no reply of their own after picking it up.
    """
    assign = None
    for e in events:
        if e.seq < trigger.seq and e.type == "audit" and e.action in ("assigned", "unassigned"):
            assign = e
    # Unassigned before the close (ticket 270370): nobody is credited with it, so nothing to flag.
    if assign is None or assign.action == "unassigned":
        return None
    if not is_human(assign.new_value) or not _same(assign.author_email, assign.new_value):
        return None
    assignee = assign.new_value

    run = _run_active_at(events, assign.seq)
    if run is None:
        return None
    if _same(_assignee_at(events, run.seq), assignee):
        return None

    if any(
        assign.seq < e.seq < trigger.seq and e.is_outbound_message and _same(e.author_email, assignee)
        for e in events
    ):
        return None

    closed_by = _close_reason(events, trigger)
    return Finding(
        rule=Rule.OVERWATCH_CLOSE,
        ticket_id=trigger.ticket_id,
        trigger_event_id=trigger.id,
        engineer_email=assignee,
        engineer_name=assign.author,
        reason=(
            "Assigned the ticket to themselves while Overwatch was running on it, sent no reply of their own, "
            f"and the ticket was then closed by {closed_by[0].lower() + closed_by[1:]}, credited to them."
        ),
        details={
            "assigned_at": assign.created_at.isoformat(),
            "overwatch_started_at": run.created_at.isoformat(),
            "closed_by": closed_by,
        },
    )


# --- Rule 6: L2 -> L3 escalation, judged against the escalation knowledge base ----------------

CONTEXT_MESSAGES = 8
CONTEXT_CHARS_PER_MESSAGE = 1500


def evaluate_escalation(events: list[Event], trigger: Event, grace: timedelta) -> Finding | None:
    """Collect what the knowledge-base judge needs: the conversation so far and the engineer's own
    reasoning (replies and internal notes around the escalation). The judging happens later."""
    horizon = trigger.created_at + grace
    if not first_of_escalation(events, trigger):
        return None
    for e in events:
        # Escalated and taken back by the same engineer within the grace period: changed their mind.
        if (
            trigger.seq < e.seq
            and e.created_at <= horizon
            and e.type == "audit"
            and e.action == "level_changed"
            and e.old_value == "L3"
            and _same(e.author_email, trigger.author_email)
        ):
            return None

    lines = []
    relevant = [
        e
        for e in events
        if e.created_at <= horizon
        and (e.type == "message" or (e.type == "note" and _same(e.author_email, trigger.author_email)))
        and not e.is_system_notice
        and e.text
    ]
    for e in relevant[-CONTEXT_MESSAGES:]:
        if e.is_customer_message:
            who = "CUSTOMER"
        elif e.type == "note":
            who = "ENGINEER INTERNAL NOTE"
        elif e.is_overwatch_auto_send or e.author_email is None:
            who = "OVERWATCH (AI) REPLY"
        else:
            who = f"SUPPORT REPLY ({e.author})"
        lines.append(f"[{e.created_at:%Y-%m-%d %H:%M} UTC] {who}:\n{e.text[:CONTEXT_CHARS_PER_MESSAGE]}")
    tags = [e.new_value for e in events if e.type == "audit" and e.action == "tag_added" and e.created_at <= horizon]
    return Finding(
        rule=Rule.L3_ESCALATION,
        ticket_id=trigger.ticket_id,
        trigger_event_id=trigger.id,
        engineer_email=trigger.author_email or "",
        engineer_name=trigger.author,
        reason="",  # filled in by the knowledge-base judge
        needs_kb_check=True,
        details={
            "escalated_at": trigger.created_at.isoformat(),
            "from_level": trigger.old_value,
            "tags": [t for t in tags if t],
            "context": "\n\n".join(lines),
        },
    )


# --- Rule 7: escalation note (RCA) quality -----------------------------------------------------

# From the corpus (data/kb_research/rca_standard.md): 98.9% of escalation notes written before the move fall
# within 6 h of it, and 93% of those written after it within 15 min.
NOTE_BEFORE = timedelta(hours=6)
NOTE_AFTER = timedelta(minutes=15)
NOTE_TOO_SHORT = 80  # characters; every sampled note under 100 was vague ("in L3", "escalated to L3")


def evaluate_escalation_note(events: list[Event], trigger: Event) -> Finding | None:
    """The escalating engineer's own internal notes from 6 h before to 15 min after the move.
    None = taken back within the window (changed their mind). Otherwise a Finding: MISSING and
    too-short notes are decided here; anything else goes to the RCA judge (needs_rca_check)."""
    if not first_of_escalation(events, trigger):
        return None
    horizon = trigger.created_at + NOTE_AFTER
    for e in events:
        if (trigger.seq < e.seq and e.created_at <= horizon and e.type == "audit" and e.action == "level_changed"
                and e.old_value == "L3" and _same(e.author_email, trigger.author_email)):
            return None
    notes = [e for e in events if e.type == "note" and _same(e.author_email, trigger.author_email)
             and trigger.created_at - NOTE_BEFORE <= e.created_at <= horizon and (e.text or "").strip()]
    text = "\n\n".join(e.text.strip() for e in notes)
    others = sorted({e.author or e.author_email for e in events if e.type == "note" and e.author_email
                     and not _same(e.author_email, trigger.author_email)
                     and trigger.created_at - NOTE_BEFORE <= e.created_at <= horizon})
    base = dict(rule=Rule.ESCALATION_NOTE, ticket_id=trigger.ticket_id, trigger_event_id=trigger.id,
                engineer_email=trigger.author_email or "", engineer_name=trigger.author)
    details = {"escalated_at": trigger.created_at.isoformat(), "note_chars": len(text), "note_count": len(notes)}
    if not notes:
        reason = "Escalated to L3 with no internal note: no root cause, evidence or ask for L3."
        if others:
            reason += f" (A note by {', '.join(others)} is in the window; the escalator wrote none.)"
        return Finding(reason=reason, details={**details, "verdict": "MISSING", "notes_by_others": others}, **base)
    if len(text) < NOTE_TOO_SHORT:
        return Finding(reason=f"Escalation note too short to carry the required fields: \"{text[:79]}\"",
                       details={**details, "verdict": "VAGUE", "note": text}, **base)
    return Finding(reason="", needs_rca_check=True, details={**details, "note": text}, **base)
