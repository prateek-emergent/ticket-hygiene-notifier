"""Formats findings as Slack messages and posts them (or prints them in dry-run mode)."""

from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient

from .detectors import RULE_TITLES, Finding, Rule
from .models import Ticket

log = logging.getLogger(__name__)

RULE_EMOJI = {
    Rule.PENDING_NO_QUESTION: ":hourglass_flowing_sand:",
    Rule.SELF_REASSIGN: ":twisted_rightwards_arrows:",
    Rule.OVERWATCH_CLOSE: ":robot_face:",
    Rule.STATUS_SHIFT: ":large_yellow_circle:",
    Rule.OFF_SHIFT_HOLD: ":zzz:",
    Rule.L3_ESCALATION: ":arrow_double_up:",
    Rule.ESCALATION_NOTE: ":memo:",
    Rule.HELD_THEN_DROPPED: ":leftwards_arrow_with_hook:",
    Rule.NO_REPLY: ":speech_balloon:",
}

EXCERPT_CHARS = 600


def _quote(text: str, limit: int = EXCERPT_CHARS) -> str:
    """Quote the END of a reply: that is where an ask or a courtesy closing sits."""
    text = text.strip()
    if len(text) > limit:
        text = "… " + text[-limit:].split(" ", 1)[-1]
    return "\n".join("> " + line if line else ">" for line in text.splitlines())


def _duration(minutes: int | None) -> str:
    if minutes is None:
        return ""
    if minutes < 120:
        return f"{minutes} min"
    hours = minutes / 60
    return f"{hours:.0f} h" if hours < 48 else f"{hours / 24:.1f} days"


def build_message(
    finding: Finding, ticket: Ticket, ticket_url: str, associate_mentions: list[str]
) -> tuple[str, list[dict]]:
    title = RULE_TITLES[finding.rule]
    label = f"#{ticket.num}" if ticket.num else ticket.id
    engineer = finding.engineer_name or finding.engineer_email
    engineer_line = (
        f"{engineer} ({finding.engineer_email})" if finding.engineer_name else finding.engineer_email
    )
    mentions = " ".join(associate_mentions) or "_no associate listed for this engineer in teams.yaml_"

    fields = [
        f"*Ticket:* <{ticket_url}|{label} · {ticket.subject}>",
        f"*Engineer:* {engineer_line}",
        f"*Associate:* {mentions}",
    ]
    if finding.rule == Rule.SELF_REASSIGN:
        held = _duration(finding.details.get("previous_held_for_minutes"))
        fields.append(
            f"*Taken from:* {finding.details.get('previous_assignee')}" + (f" (they had it for {held})" if held else "")
        )
    if finding.rule == Rule.OVERWATCH_CLOSE:
        fields.append(f"*Closed by:* {finding.details.get('closed_by')}")
    if finding.rule == Rule.OFF_SHIFT_HOLD:
        fields.append(f"*Customer waiting since:* {finding.details.get('waiting_since_local')}")
        fields.append(f"*Engineer's shift ended:* {finding.details.get('shift_ended_local')}")
    if finding.rule == Rule.ESCALATION_NOTE:
        fields.append(f"*Note:* {finding.details.get('verdict', 'MISSING').title()}"
                      + (f" · judged by {finding.details['judged_by']}" if finding.details.get("judged_by") else ""))
    if finding.rule == Rule.HELD_THEN_DROPPED:
        fields.append(f"*Held for:* {_duration(finding.details.get('held_minutes'))} · "
                      f"*Note left:* {'yes' if finding.details.get('left_note') else 'no'}")
    if finding.rule == Rule.NO_REPLY:
        fields.append(f"*Customer waiting:* {_duration(finding.details.get('waited_minutes'))}")
    if finding.rule == Rule.L3_ESCALATION:
        fields.append(f"*Knowledge base:* {finding.details.get('kb_reference') or '-'}")
        if finding.details.get("judged_by"):
            fields.append(f"*Judged by:* {finding.details['judged_by']}")

    blocks: list[dict] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"{RULE_EMOJI[finding.rule]} *{title}*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(fields)}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Why flagged:* {finding.reason}"}},
    ]
    if finding.rule == Rule.PENDING_NO_QUESTION and finding.reply is not None:
        who = "Overwatch's reply" if finding.details.get("reply_by_overwatch") else "Reply"
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{who} that was judged (end of message):*\n{_quote(finding.reply.text)}"},
            }
        )
    if finding.rule == Rule.L3_ESCALATION and finding.details.get("what_l2_should_try"):
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*What L2 could have done:*\n{finding.details['what_l2_should_try']}"},
            }
        )
    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"Theme `{finding.rule.value}` · Trinity ticket `{ticket.id}`"}],
        }
    )
    fallback = f"{title}: {label} by {engineer}. {mentions}"
    return fallback, blocks


def _local(t: datetime, tz: str) -> str:
    return t.astimezone(ZoneInfo(tz)).strftime("%a %d %b, %H:%M")


def build_status_messages(
    engineer_name: str, engineer_email: str, boundary: str, shift_start: datetime, shift_end: datetime,
    presence: str | None, minutes_after: int, tz: str, associate_mentions: list[str],
) -> tuple[tuple[str, list[dict]], tuple[str, list[dict]]]:
    """Rule 4: (channel message, direct message to the engineer)."""
    shown = (presence or "unknown").capitalize()
    if boundary == "start":
        what = f"Shift started {_local(shift_start, tz)}, but their Trinity status is still *{shown}*"
        ask = "Your shift started {} min ago, but your Trinity status is still *{}*. Please set yourself *Online*."
    else:
        what = f"Shift ended {_local(shift_end, tz)}, but their Trinity status is still *{shown}*"
        ask = "Your shift ended {} min ago, but your Trinity status is still *{}*. Please set yourself *Offline*."
    title = RULE_TITLES[Rule.STATUS_SHIFT]
    mentions = " ".join(associate_mentions) or "_no associate listed in teams.yaml_"
    fields = "\n".join([
        f"*Engineer:* {engineer_name} ({engineer_email})",
        f"*Associate:* {mentions}",
        f"*Shift:* {_local(shift_start, tz)} to {_local(shift_end, tz)} ({tz})",
    ])
    channel_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"{RULE_EMOJI[Rule.STATUS_SHIFT]} *{title}*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": fields}},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*Why flagged:* {what}, {minutes_after} min later."}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Theme `{Rule.STATUS_SHIFT.value}` · engineer reminded by DM"}]},
    ]
    dm_text = ask.format(minutes_after, shown)
    dm_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f":wave: Hi {engineer_name.split()[0]}, a quick reminder. {dm_text}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Your shift: {_local(shift_start, tz)} to {_local(shift_end, tz)} ({tz})"}]},
    ]
    return (f"{title}: {engineer_name}. {mentions}", channel_blocks), (dm_text.replace("*", ""), dm_blocks)


class SlackNotifier:
    def __init__(
        self,
        token: str | None,
        channel: str,
        dry_run: bool,
        slack_id_overrides: dict[str, str],
        api_url: str | None = None,
    ):
        # api_url points the client at a stand-in Slack (scripts/fake_slack.py) for end-to-end tests.
        kwargs = {"base_url": api_url} if api_url else {}
        self.client = AsyncWebClient(token=token, **kwargs) if token else None
        self.channel = channel
        self.dry_run = dry_run or self.client is None
        self._ids = {k.lower(): v for k, v in slack_id_overrides.items()}

    async def user_id(self, email: str) -> str | None:
        email = email.lower()
        if email not in self._ids and self.client is not None:
            try:
                resp = await self.client.users_lookupByEmail(email=email)
                self._ids[email] = resp["user"]["id"]
            except SlackApiError as e:
                log.warning("Slack lookup failed for %s: %s", email, e.response.get("error"))
                self._ids[email] = ""
        return self._ids.get(email) or None

    async def mention(self, email: str) -> str:
        user_id = await self.user_id(email)
        return f"<@{user_id}>" if user_id else email

    async def dm(self, email: str, text: str, blocks: list[dict]) -> None:
        """Direct message to one person (needs the im:write scope)."""
        if self.dry_run:
            print("\n" + "-" * 72 + f"\n[DRY RUN DM -> {email}] {text}")
            return
        user_id = await self.user_id(email)
        if not user_id:
            log.warning("cannot DM %s: no Slack user found", email)
            return
        channel = (await self.client.conversations_open(users=user_id))["channel"]["id"]
        await self.client.chat_postMessage(channel=channel, text=text, blocks=blocks, unfurl_links=False)

    async def post(self, text: str, blocks: list[dict]) -> None:
        if self.dry_run:
            print("\n" + "=" * 72 + f"\n[DRY RUN -> {self.channel}] {text}")
            for b in blocks:
                if b["type"] == "section":
                    print(b["text"]["text"])
                elif b["type"] == "context":
                    print(" ".join(el["text"] for el in b["elements"]))
            return
        await self.client.chat_postMessage(channel=self.channel, text=text, blocks=blocks, unfurl_links=False)
