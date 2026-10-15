"""CLI.

  python -m notifier serve                     # event-driven: Trinity pushes changes (recommended)
  python -m notifier run                       # polling only, for when push is not wired up yet
  python -m notifier backtest --hours 24       # replay recent activity, print alerts, never posts
  python -m notifier check <ticket_id>         # evaluate every trigger in one ticket, never posts
  python -m notifier watchdog                  # down alert: DMs config.py DOWN_ALERT["dm"] if the notifier stops
  python -m notifier health                    # exit 0 if the notifier's heartbeat is recent (container health check)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

import yaml
from dotenv import load_dotenv

from .classifier import PendingClassifier
from .config import Config, load_rules_config
from .detectors import Rule
from .kb import EscalationJudge, JevEscalationJudge, kb_text, load_kb_files
from .rca import ClaudeRcaJudge, JevRcaJudge
from .shift_checks import ShiftChecks
from .service import Monitor
from .slack import SlackNotifier
from .store import Store
from .sync import TrinitySync
from .systemone import SystemOneClassifier
from .teams import Directory
from .trinity import connect
from .watchdog import build_watchdog
from .webhook import EventService


def has_claude_key() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY", "").strip())


def claude_fallback(model: str | None, what: str) -> str | None:
    """The Claude fallback model to use, or None. A missing ANTHROPIC_API_KEY turns the fallback off with one
    warning, never an error: the checks still run on Jev, and what Jev can't settle is logged, not alerted."""
    if not model:
        return None
    if not has_claude_key():
        logging.getLogger(__name__).warning(
            "%s: Claude fallback (%s) is off because ANTHROPIC_API_KEY is not set in .env; cases Jev can't "
            "settle are logged as not judged (no alert). Add the key and restart to turn it on.", what, model)
        return None
    logging.getLogger(__name__).info("%s: Claude fallback ready (%s)", what, model)
    return model


def build_classifier(cfg: Config):
    claude = lambda: PendingClassifier(cfg.classifier_model, cfg.classifier_effort, cfg.classifier_fallbacks)  # noqa: E731
    if cfg.classifier_backend == "claude":
        if not has_claude_key():
            raise SystemExit("CLASSIFIER_BACKEND=claude needs ANTHROPIC_API_KEY in .env "
                             "(or set CLASSIFIER_BACKEND=systemone to use config.py PENDING_MODEL)")
        return claude()
    if cfg.classifier_backend == "systemone":
        use_claude = cfg.systemone_fallback == "claude" and claude_fallback(cfg.classifier_model, "theme 1")
        return SystemOneClassifier(
            cfg.systemone_url,
            cfg.systemone_model,
            api_key=cfg.systemone_api_key,
            low=cfg.systemone_low,
            high=cfg.systemone_high,
            fallback=claude() if use_claude else None,
            multilingual_model=cfg.systemone_multilingual_model,
            per_sentence=cfg.systemone_per_sentence,
            multilingual_per_sentence=cfg.systemone_multilingual_per_sentence,
            timeout_seconds=cfg.systemone_timeout,
        )
    raise SystemExit(f"CLASSIFIER_BACKEND must be 'systemone' or 'claude', not {cfg.classifier_backend!r}")


def build_monitor(cfg: Config, *, dry_run: bool, use_llm: bool, with_store: bool) -> Monitor:
    directory = Directory.load(cfg.teams_file)
    overrides = (yaml.safe_load(cfg.teams_file.read_text(encoding="utf-8")) or {}).get("slack_ids", {}) or {}
    notifier = SlackNotifier(cfg.slack_token, cfg.slack_channel, dry_run, overrides, cfg.slack_api_url)
    classifier = build_classifier(cfg) if use_llm else None
    store = Store(cfg.state_db) if with_store else None
    judge = None
    l3_on = {Rule.L3_ESCALATION, Rule.ESCALATION_NOTE} & cfg.enabled_rules
    fallback_model = claude_fallback(cfg.l3_fallback_model, "theme 6") if l3_on and use_llm else None
    if Rule.L3_ESCALATION in cfg.enabled_rules and use_llm:
        files = load_kb_files(cfg.l3_kb_dir)
        if files:
            fallback = EscalationJudge(kb_text(files), fallback_model, cfg.classifier_fallbacks) if fallback_model else None
            judge = JevEscalationJudge(files, cfg.l3_url, cfg.l3_model, cfg.l3_api_key, fallback)
        else:
            logging.getLogger(__name__).warning(
                "l3_escalation_check is on but %s has no knowledge-base files; escalations are not judged",
                cfg.l3_kb_dir,
            )
    rca = None
    if Rule.ESCALATION_NOTE in cfg.enabled_rules and use_llm:
        rca_fallback = ClaudeRcaJudge(fallback_model, cfg.classifier_fallbacks) if fallback_model else None
        rca = JevRcaJudge(cfg.l3_url, cfg.l3_model, cfg.l3_api_key, rca_fallback)
    monitor = Monitor(cfg, directory, classifier, notifier, store, escalation_judge=judge, rca_judge=rca)
    if with_store and {Rule.STATUS_SHIFT, Rule.OFF_SHIFT_HOLD} & cfg.enabled_rules:
        monitor.shift_checks = ShiftChecks(monitor)
    if with_store:
        monitor.sync = TrinitySync(monitor)
    return monitor


def check_classifier(monitor: Monitor) -> None:
    """At startup: say which model option rule 1 uses, and clearly if it is not reachable. The notifier still
    runs; PENDING checks are skipped (and logged) until it is."""
    clf = monitor.classifier
    if Rule.PENDING_NO_QUESTION not in monitor.cfg.enabled_rules or not isinstance(clf, SystemOneClassifier):
        return
    cfg = monitor.cfg
    models = " + ".join(dict.fromkeys(filter(None, [clf.model, clf.multilingual_model])))
    what = f"option {cfg.pending_model_option} ({models} at {cfg.systemone_url})"
    problem = asyncio.run(clf.health())
    log = logging.getLogger(__name__)
    if not problem:
        log.info("theme 1 model ready: %s", what)
        return
    if cfg.systemone_api_key:  # a hosted service (option B)
        hint = (
            "Check the API key in .env" if "401" in problem or "403" in problem
            else "Check the network/VPN, or switch config.py PENDING_MODEL to option A"
        )
    elif "not installed" in problem:
        hint = "Restart Ollaya with OLLAYA_MODELS set to .tools\\models (or use scripts\\ollaya.ps1 start)"
    else:
        hint = "Start Ollaya with: scripts\\ollaya.ps1 start (see README, 'Running it day to day')"
    log.error("theme 1 model not ready: %s: %s. %s", what, problem, hint)


BACKTEST_BATCH = 50
BACKTEST_CONCURRENCY = 4
BACKTEST_RETRY_WAITS = (10, 30, 60)  # seconds; network blips to Trinity do happen


def _progress(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


async def _with_retries(label: str, fn):
    """Run fn() (which opens its own Trinity connection); retry on network errors."""
    for attempt, wait in enumerate((0, *BACKTEST_RETRY_WAITS)):
        if wait:
            _progress(f"  {label}: retrying in {wait}s (attempt {attempt + 1})")
            await asyncio.sleep(wait)
        try:
            return await fn()
        except Exception as e:  # includes the ExceptionGroup the MCP transport raises on connect errors
            _progress(f"  {label}: {type(e).__name__}: {str(e)[:150]}")
    return None


async def cmd_backtest(cfg: Config, hours: float, use_llm: bool, max_tickets: int | None) -> None:
    monitor = build_monitor(cfg, dry_run=True, use_llm=use_llm, with_store=False)
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    started = datetime.now(timezone.utc)

    async def list_tickets():
        async with connect(cfg.trinity_url, cfg.trinity_headers) as trinity:
            return await trinity.tickets_updated_since(since)

    tickets = await _with_retries("listing tickets", list_tickets)
    if tickets is None:
        sys.exit("could not list tickets from Trinity")
    if max_tickets:
        tickets = tickets[:max_tickets]
    print(f"Backtesting {len(tickets)} tickets updated in the last {hours}h ...", flush=True)

    tally: Counter[str] = Counter()
    per_engineer: Counter[tuple[str, str]] = Counter()
    done: set[str] = set()
    failed: list[str] = []

    async def run_batch(batch):
        sem = asyncio.Semaphore(BACKTEST_CONCURRENCY)
        async with connect(cfg.trinity_url, cfg.trinity_headers) as trinity:

            async def one(t):
                if t.id in done:
                    return
                async with sem:
                    results = await monitor.evaluate_ticket(trinity, t, since)
                for rule, kind, line, engineer in results:
                    tally[f"{rule}: {kind}"] += 1
                    if kind == "flagged":
                        per_engineer[(engineer, rule)] += 1
                    if kind != "clean":
                        print(f"  #{t.num} {line}", flush=True)
                done.add(t.id)

            await asyncio.gather(*(one(t) for t in batch))
        return True

    for i in range(0, len(tickets), BACKTEST_BATCH):
        batch = tickets[i : i + BACKTEST_BATCH]
        ok = await _with_retries(f"tickets {i + 1}-{i + len(batch)}", lambda: run_batch(batch))
        if ok is None:
            failed.extend(t.id for t in batch if t.id not in done)
        mins = (datetime.now(timezone.utc) - started).total_seconds() / 60
        flagged = sum(v for k, v in tally.items() if k.endswith(": flagged"))
        _progress(f"progress: {len(done)}/{len(tickets)} tickets, {flagged} flagged, "
                  f"{len(failed)} failed, {mins:.1f} min")

    print("\nSummary", flush=True)
    for k, v in sorted(tally.items()):
        print(f"  {v:5d}  {k}")
    if per_engineer:
        print("\nFlagged per engineer")
        for (engineer, rule), v in sorted(per_engineer.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {v:3d}  {engineer:32} {rule}")
    if failed:
        print(f"\n{len(failed)} tickets could not be read after retries: {', '.join(failed[:20])}")


async def cmd_check(cfg: Config, ticket_id: str, use_llm: bool) -> None:
    monitor = build_monitor(cfg, dry_run=True, use_llm=use_llm, with_store=False)
    async with connect(cfg.trinity_url, cfg.trinity_headers) as trinity:
        ticket = await trinity.get_ticket(ticket_id)
        for _, _, line, _ in await monitor.evaluate_ticket(trinity, ticket, None):
            print(line)


def cmd_health(max_age_minutes: float) -> int:
    """0 when the notifier's heartbeat in state.db is recent, else 1 (with the reason on stderr)."""
    db = os.getenv("STATE_DB", "state.db")
    if not os.getenv("MONGO_URL", "").strip() and not os.path.exists(db):  # with MongoDB there is no file
        print(f"unhealthy: {db} does not exist yet", file=sys.stderr)
        return 1
    beat = Store(db).get("heartbeat")
    try:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(beat or "")
    except ValueError:
        print("unhealthy: no heartbeat yet", file=sys.stderr)
        return 1
    if age > timedelta(minutes=max_age_minutes):
        print(f"unhealthy: last heartbeat {int(age.total_seconds() // 60)} min ago", file=sys.stderr)
        return 1
    return 0


def main() -> None:
    p = argparse.ArgumentParser(prog="notifier")
    p.add_argument("--env", default=".env")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve")
    sub.add_parser("run")
    b = sub.add_parser("backtest")
    b.add_argument("--hours", type=float, default=24)
    b.add_argument("--max-tickets", type=int)
    b.add_argument("--no-llm", action="store_true", help="skip the classifier (no Anthropic spend)")
    c = sub.add_parser("check")
    c.add_argument("ticket_id")
    c.add_argument("--no-llm", action="store_true")
    sub.add_parser("watchdog")
    h = sub.add_parser("health")
    h.add_argument("--max-age-minutes", type=float, default=5)
    args = p.parse_args()
    # Windows consoles default to cp1252; ticket text and Slack previews contain arbitrary Unicode.
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for noisy in ("httpx", "httpx2", "mcp", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # These two read only state.db (and Slack), never the notifier's config: they must work when it can't start.
    if args.cmd in ("watchdog", "health"):
        if os.path.exists(args.env):
            load_dotenv(args.env)
        if args.cmd == "health":
            sys.exit(cmd_health(args.max_age_minutes))
        asyncio.run(build_watchdog(load_rules_config()).run_forever())
        return

    cfg = Config.from_env(args.env)
    if args.cmd == "serve":
        monitor = build_monitor(cfg, dry_run=cfg.dry_run, use_llm=True, with_store=True)
        check_classifier(monitor)
        service = EventService(monitor, cfg.webhook_token, cfg.reconcile_minutes, cfg.due_tick_seconds)
        asyncio.run(service.serve(cfg.webhook_host, cfg.webhook_port))
    elif args.cmd == "run":
        monitor = build_monitor(cfg, dry_run=cfg.dry_run, use_llm=True, with_store=True)
        check_classifier(monitor)
        asyncio.run(monitor.run_forever())
    elif args.cmd == "backtest":
        asyncio.run(cmd_backtest(cfg, args.hours, not args.no_llm, args.max_tickets))
    elif args.cmd == "check":
        asyncio.run(cmd_check(cfg, args.ticket_id, not args.no_llm))


if __name__ == "__main__":
    main()
