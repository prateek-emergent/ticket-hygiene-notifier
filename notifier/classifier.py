"""Decides whether a reply leaves the ball in the customer's court (the only valid reason for PENDING)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import anthropic

log = logging.getLogger(__name__)


def claude_key_rejected(e: anthropic.APIStatusError, model: str) -> str:
    """Claude refused the API key (401/403). Logged once as an error; the caller stops calling Claude for the
    rest of the run, so a wrong or revoked key doesn't fail (and log) every check."""
    msg = f"Claude API key rejected (HTTP {e.status_code}); fallback {model} off until ANTHROPIC_API_KEY is fixed and the notifier restarted"
    log.error(msg)
    return msg

SYSTEM_PROMPT = """You audit customer-support tickets for Emergent, an AI app-building platform.

Support SOP: an engineer may set a ticket to PENDING only when we are waiting on the customer, i.e. our
latest reply asks the customer something they must answer before we can proceed or confirm resolution:
a clarifying question, a request for information (job ID, app URL, screenshot, logs, email), a request
to try a fix and report back, or an explicit choice we need them to make.

Not valid reasons for PENDING (the ticket should have been closed or kept open):
- The reply resolves or answers the issue and only ends with a courtesy line such as "let me know if you
  have any other questions", "feel free to reach out", "hope this helps", "reply here if anything else
  comes up".
- The reply says WE will do something next ("we're looking into it", "the team will update you", "the
  export is being prepared"). That is waiting on us, not the customer.
- The reply is purely informational, a refusal, or a policy statement with no ask.

A conditional ask counts as waiting on the customer only if the reply needs that answer to move forward
(e.g. "please confirm the job ID so we can restore it"). A generic "if it still doesn't work, let us know"
after a complete fix does not count.

Judge only the text you are given. Quote the exact sentence that asks the customer something, if any."""

SCHEMA = {
    "type": "object",
    "properties": {
        "awaiting_customer": {
            "type": "boolean",
            "description": "True if the reply asks the customer something we need answered.",
        },
        "question_quote": {
            "type": "string",
            "description": "Exact sentence from the reply that asks the customer something; empty if none.",
        },
        "reason": {
            "type": "string",
            "description": "One sentence a team lead can read in Slack explaining the verdict.",
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["awaiting_customer", "question_quote", "reason", "confidence"],
    "additionalProperties": False,
}

MAX_CHARS = 12_000


@dataclass
class Verdict:
    awaiting_customer: bool
    question_quote: str
    reason: str
    confidence: str
    error: str | None = None
    probability: float | None = None  # P(awaiting customer), for decision-model backends
    uncertain: bool = False  # the model could not decide; treated as awaiting (no alert) unless ALERT_UNCERTAIN
    model: str | None = None  # which model decided (for the trace / dashboard)
    language: str | None = None  # detected language of the reply, when the backend detects it


class PendingClassifier:
    def __init__(self, model: str, effort: str = "low", use_fallbacks: bool = True):
        self.client = anthropic.AsyncAnthropic()
        self.model = model
        self.effort = effort
        self.use_fallbacks = use_fallbacks
        self.disabled: str | None = None  # set when Claude rejects the API key: no more calls this run

    async def classify(self, reply_text: str, customer_text: str | None, subject: str) -> Verdict:
        prompt = (
            f"Ticket subject: {subject}\n\n"
            f"<customer_latest_message>\n{(customer_text or '(none)')[:MAX_CHARS]}\n</customer_latest_message>\n\n"
            f"<our_latest_reply>\n{reply_text[:MAX_CHARS]}\n</our_latest_reply>\n\n"
            "After this reply the engineer set the ticket to PENDING. Is our reply waiting on the customer?"
        )
        kwargs = dict(
            model=self.model,
            max_tokens=4000,
            system=SYSTEM_PROMPT,
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": SCHEMA}},
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
        except anthropic.RateLimitError as e:
            return self._failed(f"rate limited: {e.message}")
        except anthropic.APIStatusError as e:
            return self._failed(f"API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError as e:
            return self._failed(f"connection error: {e}")
        except Exception as e:  # e.g. no usable API key found by the SDK
            return self._failed(f"{type(e).__name__}: {e}")

        if resp.stop_reason == "refusal":
            return self._failed("model declined to classify")
        text = next((b.text for b in resp.content if b.type == "text"), None)
        if not text:
            return self._failed(f"empty response (stop_reason={resp.stop_reason})")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return self._failed("unparseable response")
        return Verdict(
            awaiting_customer=bool(data["awaiting_customer"]),
            question_quote=data.get("question_quote", ""),
            reason=data.get("reason", ""),
            confidence=data.get("confidence", "low"),
            model=self.model,
        )

    def _failed(self, msg: str) -> Verdict:
        log.warning("classifier failed: %s", msg)
        # Unknown => surface to a human rather than silently dropping the check.
        return Verdict(False, "", f"Automatic check failed ({msg}); please review manually.", "low", error=msg,
                       model=self.model)
