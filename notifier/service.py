"""Poll loop: discover new audit events, schedule rule checks after their grace period, evaluate, alert."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

from .classifier import PendingClassifier
from .config import Config
from .detectors import (
    Finding,
    Rule,
    evaluate_escalation,
    evaluate_escalation_note,
    evaluate_overwatch_close,
    evaluate_pending,
    evaluate_reassign,
    find_triggers,
)
from .kb import CONFIDENCE_ORDER, EscalationJudge, JevEscalationJudge
from .models import Event, Ticket
from .slack import SlackNotifier, build_message
from .store import Store, outcome_kind
from .teams import Directory
from .trinity import Trinity, connect

log = logging.getLogger(__name__)

# list_tickets is sorted by updated_at; re-scan a little behind the watermark so nothing slips
# between pages or across clock skew. Duplicates are harmless (checks are keyed by event id).
OVERLAP = timedelta(minutes=2)
# Rule 1 with no reply yet: how often to look again, until the reply window closes.
RECHECK_AFTER = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Monitor:
    def __init__(
        self,
        cfg: Config,
        directory: Directory,
        classifier: PendingClassifier | None,
        notifier: SlackNotifier,
        store: Store | None = None,
        escalation_judge: JevEscalationJudge | EscalationJudge | None = None,
        rca_judge=None,
    ):
        self.cfg = cfg
        self.directory = directory
        self.classifier = classifier
        self.notifier = notifier
        self.store = store
        self.escalation_judge = escalation_judge
        self.rca_judge = rca_judge  # rule 7 (notifier/rca.py)
        self.shift_checks = None  # rules 4-5; set by the CLI when enabled (notifier/shift_checks.py)
        self.sync = None  # copy of Trinity presence and open tickets (notifier/sync.py); set by the CLI

    def trace(self, kind: str, summary: str, **fields) -> None:
        """Append to the activity trace the dashboard shows. No-op without a store (backtest, check)."""
        if self.store is None:
            return
        try:
            self.store.log(kind, summary, **fields)
            # Any work is a sign of life: a long first cycle (a backlog of checks) must not look like a stop.
            now = _now()
            if now - getattr(self, "_last_beat", datetime.min.replace(tzinfo=timezone.utc)) > timedelta(seconds=15):
                self.heartbeat()
        except Exception:  # observability must never break the checks themselves
            log.exception("could not write the activity trace")

    def describe(self) -> dict:
        """What this notifier runs with, for the dashboard's system view."""
        cfg = self.cfg
        clf = self.classifier
        judge = self.escalation_judge
        return {
            "rules": sorted(r.value for r in cfg.enabled_rules),
            "dry_run": self.notifier.dry_run,
            "poll_seconds": cfg.poll_seconds,
            "pending_model": {
                "option": cfg.pending_model_option,
                "models": [m for m in (getattr(clf, "model", None), getattr(clf, "multilingual_model", None)) if m],
                "url": cfg.systemone_url if cfg.classifier_backend == "systemone" else "anthropic",
            },
            "l3_judge": {"model": getattr(judge, "model", None),
                         "fallback": getattr(getattr(judge, "fallback", None), "model", None)} if judge else None,
            "slack_channel": cfg.slack_channel,
            "shifts_file": str(cfg.shifts_file),
        }

    # --- evaluation (shared by live loop, backtest and single-ticket check) ----------------

    def evaluate(self, events: list[Event], trigger: Event, rule: Rule) -> Finding | None:
        if rule == Rule.PENDING_NO_QUESTION:
            finding = evaluate_pending(events, trigger, self.cfg.pending_reply_window, self.cfg.is_human)
        elif rule == Rule.SELF_REASSIGN:
            finding = evaluate_reassign(
                events, trigger, self.cfg.grace[rule], self.directory.reassign_exempt, self.cfg.reassign_min_hold
            )
        elif rule == Rule.OVERWATCH_CLOSE:
            finding = evaluate_overwatch_close(events, trigger, self.cfg.is_human)
        elif rule == Rule.L3_ESCALATION:
            finding = evaluate_escalation(events, trigger, self.cfg.grace[rule])
        elif rule == Rule.ESCALATION_NOTE:
            finding = evaluate_escalation_note(events, trigger)
        else:
            raise ValueError(rule)
        # Only engineers listed in teams.yaml are monitored. Checked here rather than earlier because
        # for rule 3 the engineer (the assignee) is only known once the timeline has been evaluated.
        if finding is not None and not self.directory.is_monitored(finding.engineer_email):
            return None
        return finding

    def awaiting_reply(self, finding: Finding, now: datetime) -> bool:
        """Rule 1 found no reply yet, but the engineer may still be writing it: check again later."""
        if not finding.details.get("no_reply"):
            return False
        pending_at = datetime.fromisoformat(finding.details["pending_at"])
        return now < pending_at + self.cfg.pending_reply_window

    async def resolve(self, finding: Finding, ticket: Ticket) -> tuple[bool, str]:
        """Run the classifier where needed. Returns (should_alert, outcome description)."""
        if finding.needs_kb_check:
            return await self.resolve_escalation(finding, ticket)
        if finding.needs_rca_check:
            return await self.resolve_rca(finding, ticket)
        if finding.rule == Rule.ESCALATION_NOTE:  # MISSING / too short: decided without a judge
            return True, f"flagged: {finding.details.get('verdict', 'MISSING').lower()}"
        if not finding.needs_classification:
            return True, "flagged"
        if self.classifier is None:
            finding.reason = "(classifier disabled: review the reply below)"
            return True, "flagged-unclassified"
        customer = finding.customer_message.text if finding.customer_message else None
        t0 = time.perf_counter()
        verdict = await self.classifier.classify(finding.reply.text, customer, ticket.subject)
        ms = round((time.perf_counter() - t0) * 1000)
        p = verdict.probability
        self.trace(
            "model", f"{verdict.model or 'model'}: " + (f"{p:.0%} that the reply asks the customer something"
                                                        if p is not None else verdict.reason),
            rule=finding.rule.value, trigger_event_id=finding.trigger_event_id, ticket_id=ticket.id,
            ticket_num=ticket.num, engineer=finding.engineer_email,
            outcome="error" if verdict.error else ("uncertain" if verdict.uncertain else
                                                   ("asks" if verdict.awaiting_customer else "no_ask")),
            data={"model": verdict.model, "language": verdict.language, "probability": p,
                  "confidence": verdict.confidence, "uncertain": verdict.uncertain, "error": verdict.error,
                  "reason": verdict.reason, "latency_ms": ms, "reply_tail": finding.reply.text[-600:]},
        )
        finding.details.update(model=verdict.model, probability=p, language=verdict.language)
        if verdict.uncertain and not self.cfg.alert_uncertain:
            # Benefit of the doubt: a wrong alert costs an associate's time and the alerts' credibility.
            return False, f"skipped: uncertain: {verdict.reason}"
        if verdict.awaiting_customer and verdict.error is None and not verdict.uncertain:
            return False, f"ok: awaiting customer ({verdict.confidence}): {verdict.question_quote[:200]}"
        finding.reason = verdict.reason
        if verdict.confidence == "low" and verdict.error is None:
            finding.reason += " _(low confidence, please double-check)_"
        finding.details["classifier_confidence"] = verdict.confidence
        return True, "flagged"

    async def resolve_escalation(self, finding: Finding, ticket: Ticket) -> tuple[bool, str]:
        if self.escalation_judge is None:
            return False, "skipped: no escalation knowledge base"
        t0 = time.perf_counter()
        v = await self.escalation_judge.judge(ticket.subject, finding.details["context"], finding.details["tags"])
        self.trace(
            "model", f"{v.judged_by or 'judge'}: " + ("needed L3" if v.needs_l3 else "L2 could have handled it")
            + f" ({v.confidence})",
            rule=finding.rule.value, trigger_event_id=finding.trigger_event_id, ticket_id=ticket.id,
            ticket_num=ticket.num, engineer=finding.engineer_email,
            outcome="error" if v.error else ("needs_l3" if v.needs_l3 else "l2_could"),
            data={"model": v.judged_by, "confidence": v.confidence, "kb_reference": v.kb_reference,
                  "reason": v.reason, "error": v.error,
                  "latency_ms": round((time.perf_counter() - t0) * 1000)},
        )
        by = f" [{v.judged_by}]" if v.judged_by else ""
        if v.error:
            return False, f"skipped: {v.reason}{by}"
        if v.needs_l3:
            return False, f"ok: L3 needed ({v.confidence}): {v.kb_reference or v.reason}{by}"
        if CONFIDENCE_ORDER.get(v.confidence, 0) < CONFIDENCE_ORDER.get(self.cfg.l3_min_confidence, 1):
            return False, f"skipped: uncertain ({v.confidence}): {v.reason}{by}"
        finding.reason = v.reason
        finding.details.update(kb_reference=v.kb_reference, what_l2_should_try=v.what_l2_should_try,
                               judge_confidence=v.confidence, judged_by=v.judged_by)
        finding.details.pop("context", None)  # keep the stored alert small
        return True, "flagged"

    async def resolve_rca(self, finding: Finding, ticket: Ticket) -> tuple[bool, str]:
        if self.rca_judge is None:
            return False, "skipped: no RCA judge configured"
        t0 = time.perf_counter()
        v = await self.rca_judge.judge(finding.details["note"])
        self.trace(
            "model", f"{v.judged_by or 'judge'}: escalation note {v.verdict.lower()}",
            rule=finding.rule.value, trigger_event_id=finding.trigger_event_id, ticket_id=ticket.id,
            ticket_num=ticket.num, engineer=finding.engineer_email,
            outcome="error" if v.error else ("flagged" if v.flagged else "ok"),
            data={"model": v.judged_by, "verdict": v.verdict, "answers": v.answers, "probabilities": v.probabilities,
                  "error": v.error, "latency_ms": round((time.perf_counter() - t0) * 1000),
                  "note_tail": finding.details["note"][-800:]},
        )
        if v.error:
            return False, f"skipped: RCA check failed ({v.error})"
        finding.details.update(verdict=v.verdict, failed_questions=v.failed, judged_by=v.judged_by)
        if not v.flagged:
            return False, f"ok: note {v.verdict.lower()}" + (f" (missing: {', '.join(v.failed)})" if v.failed else "")
        finding.reason = v.reason()
        return True, "flagged"

    async def alert(self, finding: Finding, ticket: Ticket) -> dict:
        """Post the alert. Returns what the alert record and the trace need."""
        associates = self.directory.associates_for(finding.engineer_email)
        mentions = [await self.notifier.mention(a) for a in associates]
        url = self.cfg.ticket_url(ticket.id, ticket.num)
        text, blocks = build_message(finding, ticket, url, mentions)
        await self.notifier.post(text, blocks)
        self.trace(
            "alert", f"Alerted {', '.join(associates) or 'the channel'}: {finding.reason}"[:600],
            rule=finding.rule.value, trigger_event_id=finding.trigger_event_id, ticket_id=ticket.id,
            ticket_num=ticket.num, engineer=finding.engineer_email, outcome="flagged",
            data={"associates": associates, "url": url, "dry_run": self.notifier.dry_run, "text": text},
        )
        return {"ticket_num": ticket.num, "subject": ticket.subject, "engineer_name": finding.engineer_name,
                "associates": associates, "reason": finding.reason, "url": url, "dry_run": self.notifier.dry_run}

    # --- live loop -------------------------------------------------------------------------

    async def discover(self, trinity: Trinity) -> None:
        assert self.store is not None
        cycle_start = _now()
        stored = self.store.get("watermark")
        since = datetime.fromisoformat(stored) if stored else self.started_at()
        tickets = await trinity.tickets_updated_since(since - OVERLAP)
        scheduled = 0
        for t in tickets:
            scheduled += await self.ingest_ticket(trinity, t.id, since)
        self.store.put("watermark", cycle_start.isoformat())
        log.info("scanned %d updated tickets, scheduled %d checks", len(tickets), scheduled)
        self.trace("cycle", f"Scanned {len(tickets)} updated tickets, scheduled {scheduled} checks",
                   data={"tickets": len(tickets), "scheduled": scheduled,
                         "ms": round((_now() - cycle_start).total_seconds() * 1000)})

    async def ingest_ticket(self, trinity: Trinity, ticket_id: str, since: datetime) -> int:
        """Read a ticket's events we haven't seen and schedule a check for each trigger.
        Shared by the push path (webhook) and the reconciliation sweep, so a ticket reported by both
        is processed once (progress is tracked by event seq, checks are keyed by event id)."""
        assert self.store is not None
        last = self.store.last_seq(ticket_id)
        events = await trinity.events_after(ticket_id, last or 0)
        if not events:
            return 0
        scheduled = 0
        for trig in find_triggers(events, self.cfg.is_human):
            if trig.rule not in self.cfg.enabled_rules:
                continue
            if last is None and trig.event.created_at < since:
                continue  # first time we see this ticket: ignore history before we started
            if trig.rule != Rule.OVERWATCH_CLOSE and not self.directory.is_monitored(trig.event.author_email):
                continue  # rules 1-2 are about whoever made the change; skip unlisted people up front
            due = trig.event.created_at + self.cfg.grace[trig.rule]
            if self.store.schedule(trig.rule.value, trig.event.id, ticket_id, due, trig.event.author_email):
                grace = int(self.cfg.grace[trig.rule].total_seconds() // 60)
                self.trace("scheduled", f"{trig.event.author or 'Someone'}: {_event_line(trig.event)}; checking after "
                           f"a {grace}-minute grace period", rule=trig.rule.value, trigger_event_id=trig.event.id,
                           ticket_id=ticket_id, engineer=trig.event.author_email,
                           data={"event_at": trig.event.created_at, "due_at": due})
            scheduled += 1
        self.store.set_last_seq(ticket_id, max(e.seq for e in events))
        return scheduled

    def started_at(self) -> datetime:
        """When monitoring began; history before this is never alerted on."""
        assert self.store is not None
        stored = self.store.get("started_at")
        if stored:
            return datetime.fromisoformat(stored)
        start = _now() - self.cfg.initial_lookback
        self.store.put("started_at", start.isoformat())
        return start

    async def run_due(self, trinity: Trinity) -> None:
        assert self.store is not None
        for rule_value, event_id, ticket_id in self.store.due_checks(_now()):
            rule = Rule(rule_value)
            ids = {"rule": rule_value, "trigger_event_id": event_id, "ticket_id": ticket_id}
            try:
                if self.store.already_alerted(rule_value, event_id):
                    self.store.finish_check(rule_value, event_id, "duplicate")
                    self.trace("check", "Already alerted", outcome="duplicate", **ids)
                    continue
                events = await trinity.all_events(ticket_id)
                trigger = next((e for e in events if e.id == event_id), None)
                finding = self.evaluate(events, trigger, rule) if trigger else None
                if finding is None:
                    self.store.finish_check(rule_value, event_id, "clean")
                    self.trace("check", "Clean: nothing to flag", outcome="clean",
                               engineer=trigger.author_email if trigger else None, **ids)
                    continue
                if self.awaiting_reply(finding, _now()):
                    self.store.reschedule(rule_value, event_id, _now() + RECHECK_AFTER)
                    log.info("%s %s ticket=%s -> no reply yet, rechecking", rule_value, event_id, ticket_id)
                    self.trace("recheck", f"No reply yet; looking again in {RECHECK_AFTER.seconds // 60} min",
                               outcome="waiting", engineer=finding.engineer_email, **ids)
                    continue
                ticket = await trinity.get_ticket(ticket_id)
                should_alert, outcome = await self.resolve(finding, ticket)
                if should_alert and not self.store.claim_alert(rule_value, event_id):
                    should_alert, outcome = False, "duplicate"  # another notifier copy is posting it
                if should_alert:
                    try:
                        info = await self.alert(finding, ticket)
                    except Exception:
                        self.store.release_alert(rule_value, event_id)
                        raise
                    self.store.record_alert(
                        rule_value, event_id, ticket_id, finding.engineer_email, _finding_payload(finding), **info
                    )
                self.store.finish_check(rule_value, event_id, outcome)
                self.trace("check", outcome, outcome=outcome_kind(outcome), ticket_num=ticket.num,
                           engineer=finding.engineer_email, data={"subject": ticket.subject}, **ids)
                log.info("%s %s ticket=%s -> %s", rule_value, event_id, ticket_id, outcome)
            except Exception as e:  # keep the loop alive; the check is retried next cycle
                log.exception("check %s %s failed", rule_value, event_id)
                self.store.fail_check(rule_value, event_id, str(e))
                self.trace("error", f"Check failed, will retry: {type(e).__name__}: {e}", outcome="error", **ids)

    async def run_forever(self) -> None:
        log.info(
            "monitoring Trinity every %ss; themes=%s; dry_run=%s",
            self.cfg.poll_seconds,
            sorted(r.value for r in self.cfg.enabled_rules),
            self.notifier.dry_run,
        )
        self.announce("run")
        while True:
            try:
                async with connect(self.cfg.trinity_url, self.cfg.trinity_headers) as trinity:
                    await self.discover(trinity)
                    await self.run_due(trinity)
                    if self.shift_checks is not None:
                        await self.shift_checks.run(trinity, _now())
                    await self.run_sync(trinity)
                self.cycle_ok()
            except Exception as e:
                self.cycle_failed(f"{type(e).__name__}: {e}")
                log.exception("poll cycle failed; retrying next interval")
                self.trace("error", f"Poll cycle failed, retrying in {self.cfg.poll_seconds}s: "
                           f"{type(e).__name__}: {e}"[:500], outcome="error")
            self.heartbeat()
            await asyncio.sleep(self.cfg.poll_seconds)

    async def run_sync(self, trinity, force: bool = False) -> None:
        """Refresh the copy of Trinity data. A failure here is logged but doesn't fail the cycle: the checks
        themselves already ran."""
        if self.sync is None:
            return
        try:
            await self.sync.run(trinity, _now(), force=force)
        except Exception as e:
            log.exception("Trinity data sync failed")
            self.trace("error", f"Trinity data sync failed: {type(e).__name__}: {e}"[:500], outcome="error")

    def announce(self, mode: str) -> None:
        """Record a (re)start and what this notifier runs with."""
        if self.store is None:
            return
        info = self.describe() | {"mode": mode, "started": _now().isoformat()}
        self.store.put("notifier_info", json.dumps(info))
        self.trace("start", f"Notifier started ({mode}); themes on: {', '.join(info['rules'])}; "
                   f"dry run: {info['dry_run']}", data=info)
        self.heartbeat()

    def heartbeat(self) -> None:
        """The dashboard shows the notifier as live while this is recent."""
        if self.store is not None:
            self._last_beat = _now()
            self.store.put("heartbeat", self._last_beat.isoformat())

    def cycle_ok(self) -> None:
        """A cycle reached Trinity and finished: ends a failing streak (watched by notifier/watchdog.py)."""
        try:
            if self.store is not None and self.store.get("failing_since"):
                self.store.put("failing_since", "")
        except Exception:  # observability must never break the checks themselves
            log.exception("could not record the cycle")

    def cycle_failed(self, error: str) -> None:
        """A whole cycle failed (Trinity unreachable, key rejected, ...). Starts or extends a failing streak."""
        try:
            if self.store is not None:
                if not self.store.get("failing_since"):
                    self.store.put("failing_since", _now().isoformat())
                self.store.put("last_cycle_error", error[:300])
        except Exception:
            log.exception("could not record the failed cycle")

    # --- offline tools ---------------------------------------------------------------------

    async def evaluate_ticket(
        self, trinity: Trinity, ticket: Ticket, since: datetime | None
    ) -> list[tuple[str, str, str, str]]:
        """Evaluate every settled trigger in one ticket and alert (dry-run notifier for backtests).
        Returns (rule, outcome kind, human-readable line, engineer) per trigger."""
        events = await trinity.all_events(ticket.id)
        lines = []
        for trig in find_triggers(events, self.cfg.is_human):
            if trig.rule not in self.cfg.enabled_rules:
                continue
            if since and trig.event.created_at < since:
                continue
            if trig.event.created_at + self.cfg.grace[trig.rule] > _now():
                lines.append((trig.rule.value, "in-grace", f"{trig.rule.value} @{trig.event.created_at:%H:%M}: still in grace period", trig.event.author_email or ""))
                continue
            finding = self.evaluate(events, trig.event, trig.rule)
            if finding is None:
                lines.append((trig.rule.value, "clean", f"{trig.rule.value} @{trig.event.created_at:%Y-%m-%d %H:%M} by {trig.event.author}: clean", trig.event.author_email or ""))
                continue
            if self.awaiting_reply(finding, _now()):
                lines.append((trig.rule.value, "in-grace", f"{trig.rule.value} @{trig.event.created_at:%H:%M}: no reply yet, still within the reply window", finding.engineer_email))
                continue
            should_alert, outcome = await self.resolve(finding, ticket)
            kind = "flagged" if should_alert else "ok"
            lines.append((trig.rule.value, kind, f"{trig.rule.value} @{trig.event.created_at:%Y-%m-%d %H:%M} by {trig.event.author}: {outcome}", finding.engineer_email))
            if should_alert:
                await self.alert(finding, ticket)
        return lines


def _event_line(e: Event) -> str:
    """'status OPEN -> PENDING', 'assigned to x@...' : one line for the trace."""
    what = (e.action or e.type or "event").replace("_", " ")
    if e.old_value or e.new_value:
        return f"{what} {e.old_value or '-'} -> {e.new_value or '-'}"
    return what


def _finding_payload(f: Finding) -> dict:
    d = asdict(f)
    d["rule"] = f.rule.value
    d["reply"] = f.reply.id if f.reply else None
    d["customer_message"] = f.customer_message.id if f.customer_message else None
    return d
