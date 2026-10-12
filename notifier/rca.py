"""Rule 7: is an escalation note a usable RCA? Six yes/no questions, then a fixed scoring rule.

The standard comes from Notion's Escalation Matrix ("Internal note must include: Job ID, User ID, App,
Root Cause, and either Fix Applied or precisely what eng must do"), refined on 2,527 real escalations;
the questions and the rule were validated by hand on 40 classified notes (data/kb_research/rca_standard.md,
section 3; the KB copy is kb/escalation/reference/rca-standard.md).

MISSING and too-short notes are decided by code (detectors.evaluate_escalation_note); this module judges
the rest. Jev answers the six questions in one call; Claude takes over when Jev is unsure on the hard
questions (cause, evidence, own hand-off), when the note is very long, or when Jev fails.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field

import aiohttp
import anthropic

from .classifier import claude_key_rejected

log = logging.getLogger(__name__)

QUESTIONS: dict[str, dict] = {
    "identifier": {
        "instructions": "Does the note contain at least one identifier of the affected thing?",
        "criteria": {
            "true": "A job ID, user ID, account email, app name or slug, app URL or domain, deployment, run, "
                    "workflow or org ID appears anywhere in the note.",
            "false": "The note names the customer only by first name or 'the user', or names no object at all.",
        },
    },
    "own_check": {
        "instructions": "Does the note report at least one check that the support engineer ran, together with its result?",
        "criteria": {
            "true": "A sentence says something was verified, queried, curled, reproduced, read in logs or code, or "
                    "looked up in a tool, and gives the result.",
            "false": "Every factual sentence describes what the customer said, saw or wants, or what another system "
                     "(Overwatch, an AI) said.",
        },
    },
    "cause": {
        "instructions": "Does the note state a specific cause, or a specific reason support cannot do it, or say "
                        "plainly that the cause is not known and list what was checked?",
        "criteria": {
            "true": "It names the component, record, setting, code location, platform limit or mechanism that "
                    "produces the problem; or, for a request, the specific reason support cannot do it (no "
                    "permission, no tool, no endpoint); or says the cause is not confirmed and lists something "
                    "checked or ruled out.",
            "false": "It only describes the symptom (e.g. preview not loading, 502, build failed, user cannot log "
                     "in), repeats an error message without saying what causes it, or asks someone else to find out why.",
        },
    },
    "evidence": {
        "instructions": "Does the note quote or describe at least one specific observation that could be re-checked?",
        "criteria": {
            "true": "An exact error or log text, a database or query result, an HTTP status with the URL or endpoint, "
                    "a reproduction result, a code file or line, a config or flag value, a timestamped event, or a "
                    "specific screenshot or attachment.",
            "false": "Only conclusions or opinions (likely, seems, the platform is broken) or general descriptions.",
        },
    },
    "ask": {
        "instructions": "Does the note say exactly what L3 or engineering must do, or what fix was already applied?",
        "criteria": {
            "true": "An action on a named object (terminate run X, delete key Y, re-own job Z, add the listed DNS "
                    "records, restore the snapshot before a time into a named database), or a fix already applied.",
            "false": "The only request is please check, look into this, investigate, review, kindly assist, L3 review "
                     "required, or assign back; or there is no request at all.",
        },
    },
    "own_handoff": {
        "instructions": "Is the note written as the engineer's own hand-off, rather than mainly a pasted customer "
                        "reply, a forwarded customer message, or AI output?",
        "criteria": {
            "true": "Most of the text is the engineer's own description, findings or requests.",
            "false": "More than half of the text is a customer-facing reply, a copy of the customer's message, or "
                     "text from Overwatch or another AI, with no verification by the engineer after it.",
        },
    },
}
HARD = ("cause", "evidence", "own_handoff")  # the hardest calls in validation: Claude decides when Jev is unsure
LONG_NOTE = 4000

MISSING_TEXT = {
    "identifier": "no job, user or app identifier",
    "own_check": "no check the engineer ran, with its result",
    "cause": "no root cause (only the symptom)",
    "evidence": "no evidence that can be re-checked",
    "ask": "no exact action for L3 (only 'please check')",
    "own_handoff": "mostly pasted customer or AI text",
}


@dataclass
class RcaVerdict:
    verdict: str  # COMPLETE | PARTIAL | VAGUE | UNSUPPORTED | UNKNOWN
    answers: dict[str, bool] = field(default_factory=dict)
    probabilities: dict[str, float] = field(default_factory=dict)
    judged_by: str = ""
    error: str | None = None

    @property
    def failed(self) -> list[str]:
        return [q for q in QUESTIONS if self.answers.get(q) is False]

    @property
    def flagged(self) -> bool:
        return self.verdict in ("VAGUE", "UNSUPPORTED")

    def reason(self) -> str:
        gaps = "; ".join(MISSING_TEXT[q] for q in self.failed)
        if self.verdict == "VAGUE":
            return f"Escalation note is vague: {gaps}."
        if self.verdict == "UNSUPPORTED":
            return f"Escalation note states a cause without evidence: {gaps}."
        return f"Escalation note {self.verdict.lower()}" + (f": {gaps}." if gaps else ".")


def score(a: dict[str, bool]) -> str:
    """The rule validated on 40 hand-classified notes (97.5% agreement on the flag)."""
    if a["own_handoff"] is False or (a["cause"] is False and a["ask"] is False):
        return "VAGUE"
    if a["cause"] and a["evidence"] is False:
        return "UNSUPPORTED"
    if all(a.values()):
        return "COMPLETE"
    return "PARTIAL"


class ClaudeRcaJudge:
    def __init__(self, model: str, use_fallbacks: bool = True):
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.use_fallbacks = use_fallbacks
        self.disabled: str | None = None  # set when Claude rejects the API key: no more calls this run

    async def judge(self, note: str) -> RcaVerdict:
        rules = "\n".join(f"- {k}: {q['instructions']} TRUE when: {q['criteria']['true']} FALSE when: {q['criteria']['false']}"
                          for k, q in QUESTIONS.items())
        schema = {"type": "object", "additionalProperties": False, "required": list(QUESTIONS),
                  "properties": {k: {"type": "boolean"} for k in QUESTIONS}}
        kwargs = dict(
            model=self.model, max_tokens=1000,
            system="You check support engineers' escalation notes against a written standard. Answer each "
                   "question from the note text alone, literally, by its TRUE/FALSE criteria.\n" + rules,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": f"<note>\n{note[:20000]}\n</note>"}],
        )
        try:
            if self.use_fallbacks:
                resp = await self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                              fallbacks="default", **kwargs)
            else:
                resp = await self.client.messages.create(**kwargs)
            text = next((b.text for b in resp.content if b.type == "text"), "")
            answers = {k: bool(v) for k, v in json.loads(text).items() if k in QUESTIONS}
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            self.disabled = claude_key_rejected(e, self.model)
            return RcaVerdict("UNKNOWN", judged_by=self.model, error=self.disabled)
        except Exception as e:  # never alert on a failed check
            log.warning("RCA check (Claude) failed: %s", e)
            return RcaVerdict("UNKNOWN", judged_by=self.model, error=str(e))
        return RcaVerdict(score(answers), answers, judged_by=self.model)


class JevRcaJudge:
    def __init__(self, base_url: str, model: str, api_key: str | None, fallback: ClaudeRcaJudge | None = None,
                 low: float = 0.35, high: float = 0.65, timeout_seconds: float = 60):
        self.url = base_url.rstrip("/") + "/v1/systemone"
        self.model = model
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.fallback = fallback
        self.low, self.high = low, high
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def _ask(self, note: str) -> dict[str, float]:
        body = {"model": self.model, "state": f"ESCALATION NOTE\n{note}",
                "questions": {k: {"type": "noul", **q} for k, q in QUESTIONS.items()}}
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as s:
            async with s.post(self.url, json=body) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
        answers = json.loads(text)["answers"]
        return {k: float(answers[k]["noul"]) for k in QUESTIONS}

    async def judge(self, note: str) -> RcaVerdict:
        if len(note) > LONG_NOTE and self.fallback is not None and not getattr(self.fallback, "disabled", None):
            return await self._fall_back(note, "note longer than 4,000 characters")
        try:
            p = await self._ask(note)
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, KeyError, ValueError) as e:
            return await self._fall_back(note, f"Jev failed: {type(e).__name__}: {e}")
        unsure = [q for q in HARD if self.low <= p[q] < self.high]
        if unsure:
            return await self._fall_back(note, f"Jev unsure on {', '.join(unsure)}", p)
        answers = {k: v >= 0.5 for k, v in p.items()}
        return RcaVerdict(score(answers), answers, p, judged_by=self.model)

    async def _fall_back(self, note: str, why: str, p: dict[str, float] | None = None) -> RcaVerdict:
        if self.fallback is None or getattr(self.fallback, "disabled", None):
            off = "no fallback configured" if self.fallback is None else "Claude fallback off (API key rejected)"
            log.warning("RCA check: %s; %s, not judged", why, off)
            return RcaVerdict("UNKNOWN", probabilities=p or {}, judged_by=self.model, error=why)
        v = await self.fallback.judge(note)  # never raises: a failure comes back as UNKNOWN (no alert)
        v.probabilities = p or {}
        v.judged_by = f"{self.fallback.model} (fallback: {why})"
        return v
