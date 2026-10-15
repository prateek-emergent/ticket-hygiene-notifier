"""Builds Trinity-shaped event dicts. Shapes mirror real timelines (tickets 272717, 273247, 273250)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from notifier.models import Event

T0 = datetime(2026, 10, 6, 14, 0, tzinfo=timezone.utc)


class Timeline:
    def __init__(self, ticket_id: str = "t1"):
        self.ticket_id = ticket_id
        self.raw: list[dict] = []

    def _add(self, minutes: float, **kw) -> "Timeline":
        base = dict(
            id=f"{self.ticket_id}-e{len(self.raw) + 1}",
            ticket_id=self.ticket_id,
            seq=len(self.raw) + 1,
            type="audit",
            visibility="public",
            direction=None,
            body=None,
            author="System",
            author_email=None,
            action=None,
            old_value=None,
            new_value=None,
            metadata={},
            created_at=(T0 + timedelta(minutes=minutes)).isoformat(),
        )
        base.update(kw)
        self.raw.append(base)
        return self

    def customer(self, m, body="Hi, I need help"):
        return self._add(m, type="message", direction="inbound", body=body, author="Cust", author_email="c@x.com")

    def reply(self, m, who, body):
        name = who.split("@")[0].title()
        return self._add(m, type="message", direction="outbound", body=body, author=name, author_email=who)

    def ow_trigger(self, m, run="r1"):
        return self._add(m, action="ai_triggered", metadata={"overwatch_run_id": run})

    def ow_autosend(self, m, body, run="r1"):
        return self._add(
            m, type="message", direction="outbound", body=body,
            metadata={"overwatch_run_id": run, "origin": "overwatch_auto_send"},
        )

    def ow_completed(self, m, run="r1"):
        return self._add(m, action="ai_completed", metadata={"overwatch_run_id": run, "outcome": "AUTO_SENT"})

    def status(self, m, old, new, who=None, **meta):
        name = who.split("@")[0].title() if who else "System"
        return self._add(m, action="status_changed", old_value=old, new_value=new, author=name,
                         author_email=who, metadata=meta)

    def assign(self, m, by, old, new):
        return self._add(m, action="assigned", old_value=old, new_value=new, author=by.split("@")[0].title(),
                         author_email=by)

    def unassign(self, m, by, old):
        return self._add(m, action="unassigned", old_value=old, new_value=None, author=by.split("@")[0].title(),
                         author_email=by)

    def note(self, m, who, body="Checked the logs; handing over."):
        return self._add(m, type="note", visibility="internal", body=body, author=who.split("@")[0].title(),
                         author_email=who)

    def level(self, m, old, new, who=None):
        return self._add(m, action="level_changed", old_value=old, new_value=new,
                         author=who.split("@")[0].title() if who else "System", author_email=who)

    def tag(self, m, tag, who):
        return self._add(m, action="tag_added", new_value=tag, author=who.split("@")[0].title(), author_email=who)

    def events(self) -> list[Event]:
        return [Event.from_api(r) for r in self.raw]


def is_human(email):
    return bool(email) and email.endswith("@emergent.sh")
