"""Typed view over Trinity timeline events.

Trinity returns each ticket's timeline as a list of event dicts. The fields we rely on:

  type        "message" | "audit" | "note" | "ai_draft"
  action      for audits: "status_changed" | "assigned" | "ai_triggered" | "ai_completed" |
              "ai_draft_discarded" | "tag_added" | ...
  author_email  None for System (Overwatch / automation), an @emergent.sh address for humans
  old_value / new_value  status or assignee transitions
  metadata.origin == "overwatch_auto_send"  on messages Overwatch sent without a human
  metadata.overwatch_run_id  ties ai_triggered / drafts / auto-sends to one Overwatch run
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_RE = re.compile(r"</?(p|br|li|ul|ol|div|h\d|blockquote|pre|tr)[^>]*>", re.I)


def html_to_text(body: str | None) -> str:
    if not body:
        return ""
    text = _BLOCK_RE.sub("\n", body)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


@dataclass(frozen=True)
class Event:
    id: str
    ticket_id: str
    seq: int
    type: str
    action: str | None
    visibility: str | None
    direction: str | None
    author: str | None
    author_email: str | None
    old_value: str | None
    new_value: str | None
    body: str | None
    metadata: dict[str, Any]
    created_at: datetime

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "Event":
        return cls(
            id=raw["id"],
            ticket_id=raw["ticket_id"],
            seq=int(raw["seq"]),
            type=raw.get("type") or "",
            action=raw.get("action"),
            visibility=raw.get("visibility"),
            direction=raw.get("direction"),
            author=raw.get("author"),
            author_email=(raw.get("author_email") or None),
            old_value=raw.get("old_value"),
            new_value=raw.get("new_value"),
            body=raw.get("body"),
            metadata=raw.get("metadata") or {},
            created_at=parse_ts(raw["created_at"]),
        )

    @property
    def is_customer_message(self) -> bool:
        return self.type == "message" and self.direction == "inbound"

    @property
    def is_outbound_message(self) -> bool:
        return self.type == "message" and self.direction == "outbound" and self.visibility != "internal"

    @property
    def is_overwatch_auto_send(self) -> bool:
        return self.is_outbound_message and self.metadata.get("origin") == "overwatch_auto_send"

    @property
    def is_system_notice(self) -> bool:
        """Canned system mail (e.g. 'assigned to our senior team'), not a real reply."""
        return self.is_outbound_message and self.metadata.get("origin") == "spam_fallback"

    @property
    def text(self) -> str:
        return html_to_text(self.body)


@dataclass
class Ticket:
    id: str
    num: int | None
    subject: str
    status: str
    assigned_to: str | None
    level: str | None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> "Ticket":
        return cls(
            id=raw["id"],
            num=raw.get("num"),
            subject=raw.get("subject") or "(no subject)",
            status=raw.get("status") or "",
            assigned_to=raw.get("assigned_to"),
            level=raw.get("level"),
            raw=raw,
        )

    @property
    def updated_at(self) -> datetime | None:
        return parse_ts(self.raw.get("updated_at"))
