"""A local stand-in for the Slack Web API, for end-to-end tests before the real Slack app is approved.

    python scripts/fake_slack.py --port 8765 --channel "#ticket-hygiene" --log fake_slack_posts.jsonl

Then run the notifier with:
    SLACK_API_URL=http://127.0.0.1:8765/api/   SLACK_BOT_TOKEN=xoxb-fake   DRY_RUN=false

It implements the methods the notifier uses (auth.test, users.lookupByEmail, conversations.open for DMs,
chat.postMessage) and
enforces the same rules real Slack does, so mistakes surface here rather than after go-live:
  * a bot token is required (invalid_auth otherwise)
  * posting only works in the channel the bot was "invited" to (not_in_channel otherwise)
  * text or blocks required, at most 50 blocks, section text at most 3000 chars, context at most 10 elements
  * users.lookupByEmail only knows the associates in teams.yaml (users_not_found otherwise)
Every accepted message is appended to --log as JSON and printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import yaml
from aiohttp import web

MAX_BLOCKS = 50
MAX_SECTION_TEXT = 3000
MAX_CONTEXT_ELEMENTS = 10


def user_id(email: str) -> str:
    return "U" + hashlib.sha1(email.lower().encode()).hexdigest()[:9].upper()


class FakeSlack:
    def __init__(self, channel: str, known_emails: set[str], log_path: Path):
        self.channel = channel
        self.known = {e.lower() for e in known_emails}
        self.log_path = log_path
        self.calls: dict[str, int] = {}

    async def params(self, request: web.Request) -> dict:
        data = dict(request.query)
        if request.can_read_body:
            if request.content_type == "application/json":
                data.update(await request.json())
            else:
                data.update(await request.post())
        return data

    async def handle(self, request: web.Request) -> web.Response:
        method = request.match_info["method"]
        self.calls[method] = self.calls.get(method, 0) + 1
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer xoxb-"):
            return web.json_response({"ok": False, "error": "invalid_auth"})
        p = await self.params(request)
        handler = getattr(self, "m_" + method.replace(".", "_"), None)
        if handler is None:
            return web.json_response({"ok": False, "error": "unknown_method"})
        return web.json_response(handler(p))

    def m_auth_test(self, p):
        return {"ok": True, "user": "ticket_hygiene_bot", "team": "Emergent (fake)", "user_id": "UBOT00001"}

    def m_users_lookupByEmail(self, p):
        email = (p.get("email") or "").lower()
        if email not in self.known:
            return {"ok": False, "error": "users_not_found"}
        return {"ok": True, "user": {"id": user_id(email), "real_name": email.split("@")[0], "profile": {"email": email}}}

    def m_conversations_open(self, p):
        users = (p.get("users") or "").strip()
        if not users or users not in {user_id(e) for e in self.known}:
            return {"ok": False, "error": "user_not_found"}
        return {"ok": True, "channel": {"id": "D" + users[1:]}}

    def m_chat_postMessage(self, p):
        channel = p.get("channel") or ""
        if channel != self.channel and not (channel.startswith("D") and "U" + channel[1:] in {user_id(e) for e in self.known}):
            return {"ok": False, "error": "not_in_channel"}
        blocks = p.get("blocks")
        if isinstance(blocks, str):
            blocks = json.loads(blocks)
        if not p.get("text") and not blocks:
            return {"ok": False, "error": "no_text"}
        if blocks:
            if len(blocks) > MAX_BLOCKS:
                return {"ok": False, "error": "invalid_blocks", "detail": f"{len(blocks)} blocks > {MAX_BLOCKS}"}
            for i, b in enumerate(blocks):
                if b.get("type") == "section" and len(b.get("text", {}).get("text", "")) > MAX_SECTION_TEXT:
                    return {"ok": False, "error": "invalid_blocks", "detail": f"block {i} text > {MAX_SECTION_TEXT}"}
                if b.get("type") == "context" and len(b.get("elements", [])) > MAX_CONTEXT_ELEMENTS:
                    return {"ok": False, "error": "invalid_blocks", "detail": f"block {i} too many elements"}
        ts = f"{time.time():.6f}"
        record = {"ts": ts, "channel": channel, "text": p.get("text"), "blocks": blocks}
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        where = f"DM {channel}" if channel.startswith("D") else channel
        print("\n" + "=" * 72 + f"\n[fake slack] {where}  ts={ts}\n{p.get('text')}", flush=True)
        return {"ok": True, "channel": channel, "ts": ts, "message": {"text": p.get("text")}}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--channel", default="#ticket-hygiene")
    ap.add_argument("--teams", default="config/teams.yaml")
    ap.add_argument("--log", type=Path, default=Path("fake_slack_posts.jsonl"))
    args = ap.parse_args()

    data = yaml.safe_load(Path(args.teams).read_text(encoding="utf-8")) or {}
    # Associates (for @mentions) and engineers (for rule-4 DMs) are the known Slack users.
    emails = {a for t in data.get("teams", []) for a in t.get("associates", []) + t.get("engineers", [])}
    fake = FakeSlack(args.channel, emails, args.log)
    app = web.Application()
    app.router.add_route("*", "/api/{method}", fake.handle)
    print(f"fake Slack on http://127.0.0.1:{args.port}/api/  channel={args.channel}  "
          f"known users={len(emails)}  log={args.log}", flush=True)
    web.run_app(app, host="127.0.0.1", port=args.port, print=None)


if __name__ == "__main__":
    main()
