"""Rule 6: judge an L2->L3 escalation against the escalation knowledge base.

The knowledge base is every .md file in L3_ESCALATION["kb_dir"] (config.py). It describes which
problems genuinely need L3 (access or authority L2 lacks) and what L2 must try first. The judge reads
the KB plus the ticket conversation and decides whether L3 was needed. With no KB files the rule does
not run (pending decision D5).

Two judges:
  * JevEscalationJudge (default): Jev, a decision model, in two calls. 1) Which KB file is this ticket's
    issue about (whole KB + ticket)? 2) Against that file only: did it need L3, and if not, why? Jev
    can't write text, so the Slack alert quotes the matching KB section instead of an explanation.
  * EscalationJudge: Claude, used as Jev's fallback when Jev is unsure, fails, or the KB plus the
    ticket is too long for it. Claude writes its own explanation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp
import anthropic

from .classifier import claude_key_rejected

log = logging.getLogger(__name__)

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

SYSTEM_PROMPT = """You review escalations in Emergent's customer-support desk. L2 engineers escalate a
ticket to L3 when they believe it needs access or authority L2 does not have. Many escalations turn
out to be solvable by L2, which wastes L3's time.

Decide whether THIS escalation genuinely needed L3, using ONLY the knowledge base below as the
standard. If the knowledge base says L2 can resolve this kind of issue, or lists steps L2 must try
first that the conversation shows were not tried, the escalation was not needed. If the issue matches
something the knowledge base reserves for L3, it was needed. If the knowledge base does not cover the
issue, say so and use confidence "low".

Name the knowledge-base file and section your decision rests on.

<knowledge_base>
{kb}
</knowledge_base>"""

SCHEMA = {
    "type": "object",
    "properties": {
        "needs_l3": {"type": "boolean", "description": "True if the escalation genuinely needed L3."},
        "kb_reference": {"type": "string", "description": "KB file and section the decision rests on."},
        "reason": {"type": "string", "description": "One or two sentences a team lead can read in Slack."},
        "what_l2_should_try": {"type": "string", "description": "If not needed: what L2 should do instead."},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["needs_l3", "kb_reference", "reason", "what_l2_should_try", "confidence"],
    "additionalProperties": False,
}


def load_kb_files(kb_dir: str | Path) -> dict[str, str]:
    """{file name: text} for the KB the judge reads: every .md in kb_dir except README.md and the
    reference/ folder (background for people: full permission table, RCA standard, sources).
    Files whose name starts with "_" are shared principles, read alongside whichever issue file applies."""
    root = Path(kb_dir)
    files = sorted(root.glob("**/*.md")) if root.is_dir() else []
    return {f.relative_to(root).as_posix(): f.read_text(encoding="utf-8") for f in files
            if f.name.lower() != "readme.md" and "reference" not in f.relative_to(root).parts[:-1]}


def is_shared(name: str) -> bool:
    return Path(name).name.startswith("_")


def kb_covers(text: str) -> str:
    """A file's "## Covers" section (the issues it is about), used to choose the file."""
    m = re.search(r"^##\s+Covers\s*$(.*?)(?=^#{1,2}\s|\Z)", text, re.M | re.S)
    return " ".join(m.group(1).split())[:3000] if m else ""


def kb_text(files: dict[str, str]) -> str | None:
    """The KB as one text, each file under its name; None when there are no files."""
    if not files:
        return None
    return "\n\n".join(f"### FILE: {name}\n{text}" for name, text in files.items())


def load_kb(kb_dir: str | Path) -> str | None:
    return kb_text(load_kb_files(kb_dir))


@dataclass
class EscalationVerdict:
    needs_l3: bool
    kb_reference: str
    reason: str
    what_l2_should_try: str
    confidence: str
    error: str | None = None
    judged_by: str = ""
    probability: float | None = None  # Jev: P(an L3 bullet matches), when Jev decided
    scores: dict = field(default_factory=dict)  # Jev's raw answers, for evaluation and tuning


class EscalationJudge:
    def __init__(self, kb_text: str, model: str, use_fallbacks: bool = True):
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.use_fallbacks = use_fallbacks
        self.disabled: str | None = None  # set when Claude rejects the API key: no more calls this run
        # The KB is the same on every call: cache it.
        self.system = [{"type": "text", "text": SYSTEM_PROMPT.format(kb=kb_text), "cache_control": {"type": "ephemeral"}}]

    async def judge(self, subject: str, context: str, tags: list[str]) -> EscalationVerdict:
        prompt = (
            f"Ticket subject: {subject}\nTags at escalation: {', '.join(tags) or '(none)'}\n\n"
            f"<conversation>\n{context}\n</conversation>\n\n"
            "The L2 engineer escalated this ticket to L3. Did it genuinely need L3?"
        )
        kwargs = dict(
            model=self.model,
            max_tokens=4000,
            system=self.system,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            if self.use_fallbacks:
                resp = await self.client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                resp = await self.client.messages.create(**kwargs)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
            self.disabled = claude_key_rejected(e, self.model)
            return self._failed(self.disabled)
        except anthropic.APIStatusError as e:
            return self._failed(f"API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError as e:
            return self._failed(f"connection error: {e}")
        except Exception as e:  # e.g. no usable API key found by the SDK: never let the fallback crash a check
            return self._failed(f"{type(e).__name__}: {e}")
        if resp.stop_reason == "refusal":
            return self._failed("model declined")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        try:
            data = json.loads(text or "")
            return EscalationVerdict(
                needs_l3=bool(data["needs_l3"]),
                kb_reference=data.get("kb_reference", ""),
                reason=data.get("reason", ""),
                what_l2_should_try=data.get("what_l2_should_try", ""),
                confidence=data.get("confidence", "low"),
                judged_by=self.model,
            )
        except (json.JSONDecodeError, KeyError, TypeError, AttributeError):
            return self._failed("unparseable response")

    @staticmethod
    def _failed(msg: str) -> EscalationVerdict:
        log.warning("escalation judge failed: %s", msg)
        # Unknown: never alert on a failed check; the escalation goes to L3 as usual.
        return EscalationVerdict(True, "", f"Check failed ({msg}).", "", "low", error=msg)


# --- Jev ------------------------------------------------------------------------------------------

# Jev reads instructions literally; these follow the knowledge-base headings (kb/escalation/README.md).
NEEDS_L3_QUESTION = {
    "instructions": "Using only the knowledge-base file as the standard: did this L2 to L3 escalation genuinely need L3?",
    "criteria": {
        "true": "The issue is something the file reserves for L3 (access or authority L2 does not have), and any "
                "steps the file says L2 must try first were tried in the conversation.",
        "false": "The file says L2 can resolve this kind of issue, or the file lists steps L2 must try first and "
                 "the conversation shows they were not tried.",
    },
}
# The checker's decision rests on three literal MATCH questions against the chosen file, Jev's strength.
# (One holistic "did this need L3?" question was tried first; on 135 held-out escalations only 31% of its
#  alerts were right, because at escalation time the conversation rarely shows L2's steps being tried.)
MATCH_QUESTIONS = {
    "l3_match": {
        "instructions": "Does a bullet in the file's 'Needs L3 when' section describe this ticket's issue?",
        "criteria": {
            "true": "The ticket's issue is the situation one 'Needs L3 when' bullet describes: the same kind of "
                    "problem, needing the access or fix that bullet names.",
            "false": "No 'Needs L3 when' bullet describes this ticket's issue.",
        },
    },
    "l2_match": {
        "instructions": "Does a bullet in the file's 'L2 can resolve when' section describe this ticket's issue?",
        "criteria": {
            "true": "The ticket's issue is the situation one 'L2 can resolve when' bullet describes, so the L2 tool "
                    "or runbook that bullet names would fix it.",
            "false": "No 'L2 can resolve when' bullet describes this ticket's issue.",
        },
    },
    "nofault_match": {
        "instructions": "Does a bullet in the file's 'Not a fault' section describe this ticket's issue?",
        "criteria": {
            "true": "The ticket's issue is the situation one 'Not a fault' bullet describes: the customer's own setup "
                    "or expected behaviour.",
            "false": "No 'Not a fault' bullet describes this ticket's issue.",
        },
    },
}
WHY_NOT_QUESTION = {
    "instructions": "Why did this escalation not need L3, according to the knowledge-base file?",
    "criteria": {
        "l2_can_resolve": "The file says L2 can resolve this kind of issue.",
        "steps_not_tried": "The file lists steps L2 must try first, and the conversation shows they were not tried.",
        "not_a_fault": "The file says this is not a platform fault: the customer's own setup or expected behaviour.",
    },
}
WHY_NOT_TEXT = {
    "l2_can_resolve": "The knowledge base says L2 can resolve this kind of issue.",
    "steps_not_tried": "The knowledge base lists steps L2 must try first, and the conversation doesn't show them being tried.",
    "not_a_fault": "The knowledge base says this is not a platform fault (the customer's own setup or expected behaviour), "
                   "so L2 explains it to the customer.",
}
WHY_NOT_SECTION = {"l2_can_resolve": "l2 can resolve", "steps_not_tried": "must try first", "not_a_fault": "not a fault"}
NONE_OF_THESE = "none"
SECTION_CHARS = 700


def kb_title(text: str, name: str) -> str:
    """A file's first heading, which names its issue type."""
    m = re.search(r"^#\s+(.+)$", text, re.M)
    return m.group(1).strip() if m else name


def kb_section(text: str, heading_contains: str) -> tuple[str, str] | None:
    """(heading, body) of the first '##' section whose heading contains the words, if any."""
    for m in re.finditer(r"^##\s+(.+)$", text, re.M):
        if heading_contains in m.group(1).lower():
            rest = text[m.end():]
            nxt = re.search(r"^#{1,2}\s", rest, re.M)
            body = rest[: nxt.start() if nxt else len(rest)].strip()
            return m.group(1).strip(), body[:SECTION_CHARS] + ("…" if len(body) > SECTION_CHARS else "")
    return None


class TooLong(Exception):
    pass


class JevEscalationJudge:
    """Theme 6a on Jev, with an optional fallback judge (Claude) for the cases Jev can't settle."""

    def __init__(self, files: dict[str, str], base_url: str, model: str, api_key: str | None,
                 fallback: EscalationJudge | None = None, low: float = 0.4, high: float = 0.6,
                 timeout_seconds: float = 60, alert_min: float = 0.7, l3_max: float = 0.3):
        self.files = files
        self.url = base_url.rstrip("/") + "/v1/systemone"
        self.model = model
        self.headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.fallback = fallback
        self.low, self.high = low, high
        # Alert only when an L2 / not-a-fault bullet clearly matches AND no L3 bullet does (tuned on train cases).
        self.alert_min, self.l3_max = alert_min, l3_max
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        # "None of these" first: Jev leans toward the first option of a choice, and leaning toward
        # "not covered" is the safe side (no alert).
        self.shared = {n: t for n, t in files.items() if is_shared(n)}
        self.issue_files = {n: t for n, t in files.items() if not is_shared(n)}
        self.file_question = {
            "instructions": "Which knowledge-base file is about this ticket's issue?",
            "criteria": {NONE_OF_THESE: "None of these files is about this ticket's issue."}
            | {name: f"{kb_title(text, name)}. {kb_covers(text)}".strip() for name, text in self.issue_files.items()},
        }

    async def _ask(self, session: aiohttp.ClientSession, state: str, questions: dict) -> dict:
        body = {"model": self.model, "state": state, "questions": questions}
        async with session.post(self.url, json=body) as resp:
            text = await resp.text()
            if resp.status in (400, 413, 422) and "max_tokens" in text:
                raise TooLong()
            if resp.status != 200:
                raise RuntimeError(f"HTTP {resp.status}: {text[:200]}")
            return json.loads(text)["answers"]

    async def judge(self, subject: str, context: str, tags: list[str]) -> EscalationVerdict:
        ticket = (f"TICKET\nSubject: {subject}\nTags at escalation: {', '.join(tags) or '(none)'}\n"
                  f"Conversation:\n{context}")
        try:
            async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as s:
                # 1) Which KB file: chosen from each file's title and "Covers" list (the options), so the
                #    whole KB never has to fit in one request.
                a = await self._ask(s, ticket, {"file": {"type": "choice", **self.file_question}})
                name = a["file"]["choice"]
                if name == NONE_OF_THESE or name not in self.issue_files:
                    return EscalationVerdict(True, "", "The knowledge base doesn't cover this issue.", "", "low",
                                             judged_by=self.model)
                # 2) Judge against that file plus the shared principles only: less unrelated text for Jev.
                shared = "".join(f"KNOWLEDGE-BASE PRINCIPLES ({n})\n{t}\n\n" for n, t in self.shared.items())
                a = await self._ask(s, f"{shared}KNOWLEDGE-BASE FILE: {name}\n{self.files[name]}\n\n{ticket}", {
                    **{k: {"type": "noul", **q} for k, q in MATCH_QUESTIONS.items()},
                    "needs_l3": {"type": "noul", **NEEDS_L3_QUESTION},  # kept for comparison in evaluations only
                })
        except TooLong:
            return await self._fall_back("knowledge base plus ticket too long for Jev", subject, context, tags)
        except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError, KeyError, ValueError) as e:
            return await self._fall_back(f"Jev failed: {type(e).__name__}: {e}", subject, context, tags)

        scores = {k: float(a[k]["noul"]) for k in (*MATCH_QUESTIONS, "needs_l3")}
        l3, l2, nf = scores["l3_match"], scores["l2_match"], scores["nofault_match"]
        not_needed = max(l2, nf)
        if not_needed >= self.alert_min and l3 <= self.l3_max:
            why = "l2_can_resolve" if l2 >= nf else "not_a_fault"
            section = kb_section(self.files[name], WHY_NOT_SECTION[why])
            return EscalationVerdict(
                needs_l3=False,
                kb_reference=f"{name}: {section[0]}" if section else name,
                reason=f"{WHY_NOT_TEXT[why]} (Jev: {not_needed:.0%} that the KB's "
                       f"{'L2' if why == 'l2_can_resolve' else 'not-a-fault'} section describes it, "
                       f"{l3:.0%} that an L3 one does.)",
                what_l2_should_try=section[1] if section else "",
                confidence="high" if not_needed >= 0.85 and l3 <= 0.15 else "medium",
                judged_by=self.model, probability=l3, scores=scores,
            )
        if l3 >= self.high or not_needed < self.low:
            return EscalationVerdict(True, name, f"Jev: {l3:.0%} that an L3 bullet describes it; "
                                     f"{not_needed:.0%} that an L2 or not-a-fault one does.", "",
                                     "high" if l3 >= 0.85 else "medium", judged_by=self.model, probability=l3, scores=scores)
        return await self._fall_back(f"Jev unsure (L3 match {l3:.0%}, L2/not-a-fault match {not_needed:.0%})",
                                     subject, context, tags, scores)

    async def _fall_back(self, why: str, subject: str, context: str, tags: list[str],
                         scores: dict | None = None) -> EscalationVerdict:
        if self.fallback is None or getattr(self.fallback, "disabled", None):
            off = "no fallback configured" if self.fallback is None else "Claude fallback off (API key rejected)"
            log.warning("escalation check: %s; %s, not judged", why, off)
            return EscalationVerdict(True, "", f"Not judged ({why}).", "", "low", error=why, judged_by=self.model,
                                     scores=scores or {})
        log.info("escalation check: %s; asking %s", why, self.fallback.model)
        try:
            v = await self.fallback.judge(subject, context, tags)
        except Exception as e:  # a failing fallback never alerts: the escalation goes to L3 as usual
            v = self.fallback._failed(f"{type(e).__name__}: {e}")
        v.judged_by = f"{self.fallback.model} (fallback: {why})"
        v.scores = v.scores or scores or {}
        return v
