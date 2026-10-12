"""Verify the Slack setup before going live.

    python scripts/check_slack.py              # token works, every associate resolves to a Slack user
    python scripts/check_slack.py --post-test  # also posts one test message to SLACK_CHANNEL
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv  # noqa: E402
from slack_sdk.errors import SlackApiError  # noqa: E402
from slack_sdk.web.async_client import AsyncWebClient  # noqa: E402

from notifier.teams import Directory  # noqa: E402


async def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--post-test", action="store_true")
    args = ap.parse_args()

    token = os.getenv("SLACK_BOT_TOKEN")
    channel = os.getenv("SLACK_CHANNEL", "#ticket-hygiene")
    if not token:
        sys.exit("SLACK_BOT_TOKEN is not set in .env")
    api_url = os.getenv("SLACK_API_URL")
    client = AsyncWebClient(token=token, **({"base_url": api_url} if api_url else {}))
    ok = True

    try:
        auth = await client.auth_test()
        print(f"token OK: bot '{auth['user']}' in workspace '{auth['team']}'")
    except SlackApiError as e:
        sys.exit(f"token rejected: {e.response.get('error')}")

    directory = Directory.load(os.getenv("TEAMS_FILE", "config/teams.yaml"))
    for team in directory.teams:
        for email in team.associates:
            try:
                user = (await client.users_lookupByEmail(email=email))["user"]
                print(f"associate OK: {email} -> <@{user['id']}> ({user.get('real_name')})")
            except SlackApiError as e:
                ok = False
                print(f"associate NOT FOUND: {email} ({e.response.get('error')}). "
                      f"Add their Slack ID under slack_ids: in teams.yaml")

    if args.post_test:
        try:
            await client.chat_postMessage(
                channel=channel,
                text=":white_check_mark: Ticket Hygiene Bot is connected. Alerts will appear in this channel.",
            )
            print(f"test message posted to {channel}")
        except SlackApiError as e:
            ok = False
            err = e.response.get("error")
            hint = " (invite the bot: /invite @Ticket Hygiene Bot)" if err in ("not_in_channel", "channel_not_found") else ""
            print(f"posting to {channel} failed: {err}{hint}")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
