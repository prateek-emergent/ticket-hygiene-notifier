"""Replay real Trinity tickets through the notifier on a simulated clock.

    python scripts/simulate.py --from-backtest backtest.txt --sample 50
    python scripts/simulate.py --tickets 6ac5e9f2... 6ac0baf5...   [--pace 0.3]

What it does:
  1. Downloads the full timelines of the chosen tickets from Trinity (read-only).
  2. Replays them on a simulated clock: an event only becomes visible to the notifier once the clock
     passes the time it really happened.
  3. Runs the REAL notifier loop against that replay, one poll every simulated minute: the same intake,
     grace periods, reply window, classifier (local Ollaya) and Slack formatting as production.
  4. Posts alerts to Slack through the real Slack client. Point --slack-url at scripts/fake_slack.py
     (default) to test without the real workspace.
  5. Reports, per alert, when the event happened, when the alert was posted (simulated time, i.e. the
     delay production would show) and how long the check took on this machine (wall time), and writes
     a Slack-like page: simulation/slack_channel.html.

Simulated time only advances between poll cycles, so classifier speed on this laptop does not distort
the delays: they show what the design produces. Wall times are reported separately.
"""

from __future__ import annotations

import argparse
import asyncio
import html
import logging
import re
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from notifier import service as service_mod  # noqa: E402
from notifier.__main__ import build_monitor  # noqa: E402
from notifier.config import Config  # noqa: E402
from notifier.detectors import RULE_TITLES, Rule, find_triggers  # noqa: E402
from notifier.models import Event, Ticket  # noqa: E402
from notifier.trinity import connect  # noqa: E402

POLL = timedelta(seconds=60)


@dataclass
class Clock:
    now: datetime


class ReplayTrinity:
    """Serves real timelines, but only the events that have 'happened' by the simulated clock."""

    def __init__(self, timelines: dict[str, list[Event]], tickets: dict[str, Ticket], clock: Clock):
        self.timelines, self.tickets, self.clock = timelines, tickets, clock

    def _visible(self, tid: str) -> list[Event]:
        return [e for e in self.timelines[tid] if e.created_at <= self.clock.now]

    async def tickets_updated_since(self, since: datetime) -> list[Ticket]:
        out = []
        for tid in self.timelines:
            vis = self._visible(tid)
            if vis and vis[-1].created_at >= since:
                out.append(Ticket.from_api({**self.tickets[tid].raw, "updated_at": vis[-1].created_at.isoformat()}))
        return out

    async def events_after(self, tid: str, after_seq: int) -> list[Event]:
        return [e for e in self._visible(tid) if e.seq > after_seq]

    async def all_events(self, tid: str) -> list[Event]:
        return self._visible(tid)

    async def get_ticket(self, tid: str) -> Ticket:
        return self.tickets[tid]


@dataclass
class AlertRecord:
    ticket: Ticket
    rule: Rule
    engineer: str
    event_at: datetime
    posted_at: datetime
    check_ms: float
    text: str
    blocks: list = field(default_factory=list)

    @property
    def delay(self) -> timedelta:
        return self.posted_at - self.event_at


def pick_from_backtest(path: Path, n: int) -> list[str]:
    """Spread the sample across rules: every Overwatch alert, then reassignments and Pending alerts."""
    by_rule: dict[str, list[str]] = {}
    for m in re.finditer(r"(?:Theme|Rule) `(\w+)` · Trinity ticket `([0-9a-f]{24})`", path.read_text(encoding="utf-8")):
        lst = by_rule.setdefault(m.group(1), [])
        if m.group(2) not in lst:
            lst.append(m.group(2))
    picked: list[str] = []
    order = ["picked_up_during_overwatch_run", "reassigned_from_colleague", "pending_without_open_question"]
    while len(picked) < n and any(by_rule.get(r) for r in order):
        for r in order:
            if by_rule.get(r) and len(picked) < n:
                tid = by_rule[r].pop(0)
                if tid not in picked:
                    picked.append(tid)
    return picked


def fmt_delay(d: timedelta) -> str:
    s = int(d.total_seconds())
    return f"{s // 60}m {s % 60:02d}s"


def mrkdwn_to_html(text: str) -> str:
    out = []
    for line in html.escape(text, quote=False).split("\n"):
        quote = line.startswith("&gt;")
        if quote:
            line = line[4:].lstrip()
        line = re.sub(r"&lt;(https?://[^|&]+)\|([^&]+?)&gt;", r'<a href="\1">\2</a>', line)
        line = re.sub(r"&lt;@(\w+)&gt;", r'<span class="mention">@\1</span>', line)
        line = re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", line)
        line = re.sub(r"(?<![\w])_([^_\n]+)_(?![\w])", r"<i>\1</i>", line)
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        for code, emoji in ((":hourglass_flowing_sand:", "⏳"), (":twisted_rightwards_arrows:", "🔀"), (":robot_face:", "🤖")):
            line = line.replace(code, emoji)
        out.append(f'<div class="quote">{line}</div>' if quote else f"<div>{line}</div>")
    return "\n".join(out)


def write_channel_html(path: Path, alerts: list[AlertRecord], channel: str, window: tuple[datetime, datetime]) -> None:
    rows = []
    for a in sorted(alerts, key=lambda a: a.posted_at):
        body = []
        for b in a.blocks:
            if b["type"] == "section":
                body.append(mrkdwn_to_html(b["text"]["text"]))
            elif b["type"] == "context":
                body.append('<div class="ctx">' + mrkdwn_to_html(" ".join(e["text"] for e in b["elements"])) + "</div>")
        rows.append(
            f'<div class="msg"><div class="avatar">TH</div><div class="content">'
            f'<div class="head"><b>Ticket Hygiene Bot</b> <span class="app">APP</span> '
            f'<span class="ts">{a.posted_at:%b %d, %H:%M:%S} UTC</span>'
            f'<span class="delay">posted {fmt_delay(a.delay)} after the event ({a.event_at:%H:%M:%S})</span></div>'
            + "".join(body)
            + "</div></div>"
        )
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(channel)} (simulation)</title>
<style>
:root{{--bg:#fff;--fg:#1d1c1d;--muted:#616061;--line:#e8e8e8;--quote:#dddddd;--link:#1264a3;--mention-bg:#e8f5fa;--badge:#f4ede4}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1a1d21;--fg:#d1d2d3;--muted:#9a9b9c;--line:#2c2d30;--quote:#545454;--link:#1d9bd1;--mention-bg:#1d3a4a;--badge:#3a3226}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.46 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}}
header{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:12px 16px}}
header h1{{font-size:18px;margin:0}} header p{{margin:2px 0 0;color:var(--muted);font-size:13px}}
.msg{{display:flex;gap:10px;padding:10px 16px;border-bottom:1px solid var(--line)}}
.avatar{{flex:0 0 36px;height:36px;border-radius:6px;background:#4a154b;color:#fff;display:grid;place-items:center;font-weight:700;font-size:13px}}
.content{{min-width:0;flex:1}} .head{{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}}
.app{{font-size:10px;background:var(--line);padding:1px 4px;border-radius:3px;color:var(--muted)}}
.ts{{color:var(--muted);font-size:12px}} .delay{{font-size:12px;background:var(--badge);padding:1px 6px;border-radius:10px}}
.quote{{border-left:4px solid var(--quote);padding-left:10px;color:var(--fg);white-space:pre-wrap;overflow-wrap:anywhere}}
a{{color:var(--link);text-decoration:none;overflow-wrap:anywhere}} .mention{{background:var(--mention-bg);color:var(--link);border-radius:3px;padding:0 2px}}
.ctx{{color:var(--muted);font-size:12px;margin-top:4px}} code{{font-size:12px;background:var(--line);padding:0 3px;border-radius:3px}}
</style></head><body>
<header><h1>{html.escape(channel)}</h1>
<p>Simulation replay of {window[0]:%b %d %H:%M} to {window[1]:%b %d %H:%M} UTC · {len(alerts)} alerts · real tickets, simulated clock, stand-in Slack</p></header>
{''.join(rows) or '<p style="padding:16px">No alerts.</p>'}
</body></html>"""
    path.write_text(page, encoding="utf-8")


async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--from-backtest", type=Path, help="backtest output; tickets are taken from its alerts")
    src.add_argument("--tickets", nargs="+", help="explicit Trinity ticket ids")
    ap.add_argument("--sample", type=int, default=50)
    ap.add_argument("--hours", type=float, default=24, help="replay triggers from the last N hours")
    ap.add_argument("--slack-url", default="http://127.0.0.1:8765/api/", help="'' to use real Slack from .env")
    ap.add_argument("--channel", default=None)
    ap.add_argument("--pace", type=float, default=0.0, help="wall seconds to pause per simulated minute with activity")
    ap.add_argument("--out", type=Path, default=ROOT / "simulation")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    cfg = Config.from_env(str(ROOT / ".env"))
    args.out.mkdir(exist_ok=True)
    cfg.state_db = args.out / "sim_state.db"
    cfg.state_db.unlink(missing_ok=True)
    if args.slack_url:
        cfg.slack_api_url, cfg.slack_token = args.slack_url, "xoxb-simulation"
    if args.channel:
        cfg.slack_channel = args.channel
    cfg.dry_run = False

    ids = pick_from_backtest(args.from_backtest, args.sample) if args.from_backtest else args.tickets
    print(f"Downloading {len(ids)} ticket timelines from Trinity ...", flush=True)
    timelines, tickets = {}, {}
    async with connect(cfg.trinity_url, cfg.trinity_headers) as trinity:
        for tid in ids:
            tickets[tid] = await trinity.get_ticket(tid)
            timelines[tid] = await trinity.all_events(tid)

    # Replay window: from just before the first trigger to the last trigger + the longest wait.
    horizon = datetime.now(timezone.utc)
    earliest = horizon - timedelta(hours=args.hours)
    trig_times = [
        t.event.created_at
        for evs in timelines.values()
        for t in find_triggers(evs, cfg.is_human)
        if earliest <= t.event.created_at <= horizon
    ]
    if not trig_times:
        sys.exit("no triggers in the chosen window")
    start = min(trig_times).replace(second=0, microsecond=0) - timedelta(minutes=2)
    end = min(horizon, max(trig_times) + cfg.pending_reply_window + timedelta(minutes=10))
    clock = Clock(start)
    replay = ReplayTrinity(timelines, tickets, clock)

    service_mod._now = lambda: clock.now  # the notifier's clock is now the simulated one
    monitor = build_monitor(cfg, dry_run=False, use_llm=True, with_store=True)
    store = monitor.store
    store.put("started_at", start.isoformat())
    store.put("watermark", start.isoformat())

    by_event: dict[str, tuple[str, Event]] = {}
    for tid, evs in timelines.items():
        for e in evs:
            by_event[e.id] = (tid, e)
    alerts: list[AlertRecord] = []
    outcomes: Counter[str] = Counter()
    check_ms: dict[str, float] = {}
    activity = [False]

    def say(msg: str) -> None:
        activity[0] = True
        print(f"[{clock.now:%m-%d %H:%M}] {msg}", flush=True)

    def label(tid: str) -> str:
        t = tickets[tid]
        return f"#{t.num}" if t.num else tid[:8]

    orig_schedule = store.schedule

    def schedule(rule, event_id, ticket_id, due_at):
        _, e = by_event[event_id]
        say(f"TRIGGER  {label(ticket_id):8} {rule:31} by {e.author or 'System'} at {e.created_at:%H:%M:%S}"
            f" -> check due {due_at:%H:%M}")
        return orig_schedule(rule, event_id, ticket_id, due_at)

    orig_finish, orig_resched = store.finish_check, store.reschedule

    def finish(rule, event_id, outcome):
        tid, _ = by_event[event_id]
        kind = outcome.split(":")[0]
        outcomes[f"{rule}: {kind}"] += 1
        ms = check_ms.get(event_id)
        say(f"CHECK    {label(tid):8} {rule:31} -> {outcome[:90]}" + (f"   [{ms / 1000:.1f}s on this PC]" if ms else ""))
        return orig_finish(rule, event_id, outcome)

    def reschedule(rule, event_id, due_at):
        tid, _ = by_event[event_id]
        say(f"WAIT     {label(tid):8} {rule:31} -> no reply yet, re-check at {due_at:%H:%M}")
        return orig_resched(rule, event_id, due_at)

    store.schedule, store.finish_check, store.reschedule = schedule, finish, reschedule

    orig_resolve = monitor.resolve

    async def resolve(finding, ticket):
        t0 = time.perf_counter()
        result = await orig_resolve(finding, ticket)
        check_ms[finding.trigger_event_id] = (time.perf_counter() - t0) * 1000
        return result

    monitor.resolve = resolve

    last_post: list = [None]
    orig_post = monitor.notifier.post

    async def post(text, blocks):
        await orig_post(text, blocks)
        last_post[0] = (text, blocks)

    monitor.notifier.post = post
    orig_alert = monitor.alert

    async def alert(finding, ticket):
        await orig_alert(finding, ticket)
        _, e = by_event[finding.trigger_event_id]
        rec = AlertRecord(ticket, finding.rule, finding.engineer_email, e.created_at, clock.now,
                          check_ms.get(finding.trigger_event_id, 0.0), *last_post[0])
        alerts.append(rec)
        say(f"SLACK    {label(ticket.id):8} {finding.rule.value:31} posted to {cfg.slack_channel}, "
            f"{fmt_delay(rec.delay)} after the event")

    monitor.alert = alert

    print(f"Replaying {start:%m-%d %H:%M} to {end:%m-%d %H:%M} UTC, one poll per simulated minute ...\n", flush=True)
    wall0 = time.perf_counter()
    while clock.now <= end:
        activity[0] = False
        await monitor.discover(replay)
        await monitor.run_due(replay)
        if activity[0] and args.pace:
            await asyncio.sleep(args.pace)
        clock.now += POLL
    wall = time.perf_counter() - wall0

    # --- report ---------------------------------------------------------------------------
    print("\n" + "=" * 100)
    print(f"Simulated {(end - start).total_seconds() / 3600:.1f} h of activity on {len(ids)} tickets "
          f"in {wall / 60:.1f} min of wall time.\n")
    print("Check outcomes:")
    for k, v in sorted(outcomes.items()):
        print(f"  {v:4d}  {k}")
    print(f"\nAlerts posted: {len(alerts)}")
    print(f"  {'ticket':8} {'rule':31} {'engineer':28} {'event at':>9} {'posted at':>9} {'delay':>8} {'check':>7}")
    for a in sorted(alerts, key=lambda a: a.posted_at):
        print(f"  #{a.ticket.num!s:7} {a.rule.value:31} {a.engineer:28} {a.event_at:%H:%M:%S} "
              f"{a.posted_at:%H:%M:%S} {fmt_delay(a.delay):>8} {a.check_ms / 1000:6.1f}s")
    print("\nDelay from event to Slack post (simulated, what production would show):")
    for rule in Rule:
        ds = [a.delay.total_seconds() / 60 for a in alerts if a.rule == rule]
        if ds:
            print(f"  {RULE_TITLES[rule][:55]:55} n={len(ds):3d}  median {statistics.median(ds):5.1f} min  "
                  f"max {max(ds):5.1f} min")
    page = args.out / "slack_channel.html"
    write_channel_html(page, alerts, cfg.slack_channel, (start, end))
    print(f"\nSlack-like channel view: {page}")


if __name__ == "__main__":
    asyncio.run(main())
