"""Pull every L2->L3 escalation from Trinity into a local corpus, for building and testing the rule-6 KB.

    python scripts/escalation_corpus.py                      # since 2026-05-18 (when l3 tags began)
    python scripts/escalation_corpus.py --since 2026-08-01 --limit 200

Read-only on Trinity: list_tickets, get_ticket_messages, list_agents. Writes to data/escalations/
(git-ignored: tickets contain customer conversations and must never be committed):
  tickets/<num>.json   compact timeline: meta, audit trail, internal notes, conversation excerpts
  index.jsonl          one derived summary per ticket (escalator, RCA note, review outcome, timings)
  agents.json          email -> support level / role, for everyone who acted on these tickets
  README.txt           what the fields mean

Every ticket gets a fixed split: 'holdout' (1 in 5, by ticket id hash) is never shown to the people or
agents who write the KB; it is kept to measure the finished KB fairly. Everything else is 'train'.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from notifier.config import Config  # noqa: E402
from notifier.models import Event, parse_ts  # noqa: E402
from notifier.trinity import connect  # noqa: E402

OUT = Path("data/escalations")
ESCALATION_TAGS = {"l3_needs_review", "real_l3"}
AUDIT_KEPT = {"level_changed", "tag_added", "tag_removed", "team_assigned", "team_unassigned", "slack_link_updated",
              "assigned", "unassigned", "status_changed", "spam_fallback_sent"}
NOTE_CHARS, MESSAGE_CHARS, DRAFT_CHARS = 6000, 1500, 300


def split_of(ticket_id: str) -> str:
    return "holdout" if int(hashlib.sha1(ticket_id.encode()).hexdigest(), 16) % 5 == 0 else "train"


async def ticket_ids(t, since: datetime, limit: int | None) -> dict[str, dict]:
    """Union of tickets tagged l3_needs_review / real_l3 or currently at L3, created since `since`."""
    found: dict[str, dict] = {}
    for f in ({"tags": ["l3_needs_review"]}, {"tags": ["real_l3"]}, {"level": "L3"}):
        cursor = None
        while True:
            args = {"limit": 100, **f}
            if cursor:
                args["cursor"] = cursor
            page = await t._call("list_tickets", args)
            for it in page.get("items", []):
                created = parse_ts(it.get("created_at"))
                if created and created >= since:
                    found.setdefault(it["id"], it)
            cursor = page.get("next_cursor")
            if not cursor:
                break
        print(f"  {f}: {len(found)} tickets so far", file=sys.stderr)
    if limit:
        found = dict(list(found.items())[:limit])
    return found


async def all_events(t, ticket_id: str, tries: int = 4) -> list[Event]:
    for attempt in range(tries):
        try:
            return await t.all_events(ticket_id)
        except Exception as e:  # network blips: back off and retry
            if attempt == tries - 1:
                raise
            await asyncio.sleep(5 * (attempt + 1))
            print(f"  retry {ticket_id}: {type(e).__name__}", file=sys.stderr)
    return []


class Levels:
    """support_level / role per email, looked up once each (list_agents caps at 200, so query per email)."""

    def __init__(self, t):
        self.t, self.cache, self.lock = t, {}, asyncio.Lock()

    async def of(self, email: str | None) -> dict:
        if not email or "@" not in email:
            return {}
        e = email.lower()
        if e not in self.cache:
            async with self.lock:
                if e not in self.cache:
                    try:
                        rows = await self.t._call("list_agents", {"query": e, "limit": 5})
                        rows = rows if isinstance(rows, list) else rows.get("items", [])
                        hit = next((r for r in rows if r.get("email", "").lower() == e), None)
                    except Exception:
                        hit = None
                    self.cache[e] = ({"support_level": hit.get("support_level"), "role": hit.get("role"),
                                      "name": f"{hit.get('first_name') or ''} {hit.get('last_name') or ''}".strip()}
                                     if hit else {"support_level": None, "role": "customer_or_unknown"})
        return self.cache[e]


def _text(e: Event, n: int) -> str:
    s = (e.text or "").strip()
    return s if len(s) <= n else s[:n] + " […]"


async def compact(meta: dict, events: list[Event], levels: Levels) -> tuple[dict, dict]:
    tl, notes, audit = [], [], []
    for e in events:
        who = e.author_email or e.author or "System"
        lv = await levels.of(e.author_email)
        row = {"at": e.created_at.isoformat(), "by": who, "by_level": lv.get("support_level"), "by_role": lv.get("role")}
        if e.type == "note":
            notes.append({**row, "text": _text(e, NOTE_CHARS)})
            tl.append({**row, "kind": "internal_note", "text": _text(e, NOTE_CHARS)})
        elif e.type == "audit":
            if e.action in AUDIT_KEPT:
                a = {**row, "action": e.action, "old": e.old_value, "new": e.new_value,
                     **({"meta": {k: v for k, v in e.metadata.items() if k in ("origin", "reason")}} if e.metadata else {})}
                audit.append(a)
                tl.append({**row, "kind": "audit", **{k: a[k] for k in ("action", "old", "new")}})
        elif e.type == "message":
            origin = (e.metadata or {}).get("origin")
            kind = "customer" if e.is_customer_message else ("overwatch_auto" if origin else "agent_reply")
            tl.append({**row, "kind": kind, "text": _text(e, MESSAGE_CHARS), **({"origin": origin} if origin else {})})
        elif e.type == "ai_draft":
            tl.append({**row, "kind": "ai_draft", "text": _text(e, DRAFT_CHARS)})
    ticket = {
        "id": meta["id"], "num": meta.get("num"), "subject": meta.get("subject"), "status": meta.get("status"),
        "level_now": meta.get("level"), "tags_now": [x if isinstance(x, str) else x.get("label") for x in meta.get("tags") or []],
        "created_at": meta.get("created_at"), "split": split_of(meta["id"]),
        "audit": audit, "internal_notes": notes, "timeline": tl,
    }
    return ticket, summarize(ticket)


def summarize(tk: dict) -> dict:
    """The escalation story in a few fields. Interpretation is left to the analysts; this only records facts."""
    audit = tk["audit"]
    human = lambda a: a["by"] != "System"  # noqa: E731
    esc = next((a for a in audit if human(a) and ((a["action"] == "level_changed" and a["new"] == "L3")
                                                   or (a["action"] == "tag_added" and a["new"] in ESCALATION_TAGS))), None)
    first = lambda pred: next((a for a in audit if pred(a)), None)  # noqa: E731
    real = first(lambda a: a["action"] == "tag_added" and a["new"] == "real_l3")
    review_tag = first(lambda a: a["action"] == "tag_added" and a["new"] == "l3_needs_review")
    review_removed = first(lambda a: a["action"] == "tag_removed" and a["old"] == "l3_needs_review")
    down = [a for a in audit if a["action"] == "level_changed" and a["old"] == "L3" and a["new"] in ("L2", "L1")]
    teams = [a["new"] for a in audit if a["action"] == "team_assigned"]
    slack = any(a["action"] == "slack_link_updated" for a in audit)
    esc_note = None
    if esc:
        t0 = datetime.fromisoformat(esc["at"])
        near = [n for n in tk["internal_notes"] if n["by"] == esc["by"]
                and t0 - timedelta(hours=6) <= datetime.fromisoformat(n["at"]) <= t0 + timedelta(hours=1)]
        esc_note = near[-1] if near else None
    rca_notes = [n for n in tk["internal_notes"] if "rca" in n["text"].lower() or "root cause" in n["text"].lower()]
    return {
        "num": tk["num"], "id": tk["id"], "split": tk["split"], "subject": tk["subject"], "tags_now": tk["tags_now"],
        "level_now": tk["level_now"], "status": tk["status"], "created_at": tk["created_at"],
        "escalated_by": esc and esc["by"], "escalator_level": esc and esc["by_level"], "escalated_at": esc and esc["at"],
        "escalation_action": esc and f'{esc["action"]}:{esc["new"]}',
        "escalation_note": esc_note and esc_note["text"][:3000], "escalation_note_chars": len(esc_note["text"]) if esc_note else 0,
        "l3_needs_review_added_by": review_tag and review_tag["by"],
        "l3_needs_review_removed_by": review_removed and review_removed["by"],
        "real_l3_added_by": real and real["by"], "real_l3_added_by_level": real and real["by_level"],
        "real_l3_at": real and real["at"],
        "moved_down_from_l3": [{"by": a["by"], "by_level": a["by_level"], "at": a["at"], "to": a["new"]} for a in down],
        "teams_assigned": teams, "slack_thread": slack,
        "rca_note_authors": sorted({n["by"] for n in rca_notes}), "internal_note_count": len(tk["internal_notes"]),
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-05-18")
    ap.add_argument("--limit", type=int, help="only the first N tickets (for a trial run)")
    ap.add_argument("--concurrency", type=int, default=6)
    args = ap.parse_args()
    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    cfg = Config.from_env()
    (OUT / "tickets").mkdir(parents=True, exist_ok=True)
    async with connect(cfg.trinity_url, cfg.trinity_headers) as t:
        print(f"listing escalated tickets created since {since:%Y-%m-%d} ...", file=sys.stderr)
        tickets = await ticket_ids(t, since, args.limit)
        levels = Levels(t)
        sem = asyncio.Semaphore(args.concurrency)
        done = 0
        index = []

        async def one(meta: dict) -> None:
            nonlocal done
            async with sem:
                path = OUT / "tickets" / f"{meta.get('num') or meta['id']}.json"
                try:
                    events = await all_events(t, meta["id"])
                except Exception as e:
                    print(f"  FAILED {meta.get('num')}: {e}", file=sys.stderr)
                    return
                ticket, summary = await compact(meta, events, levels)
                path.write_text(json.dumps(ticket, ensure_ascii=False, indent=1), encoding="utf-8")
                index.append(summary)
                done += 1
                if done % 100 == 0:
                    print(f"  {done}/{len(tickets)} tickets", file=sys.stderr)

        await asyncio.gather(*(one(m) for m in tickets.values()))
        index.sort(key=lambda s: s["created_at"] or "")
        with (OUT / "index.jsonl").open("w", encoding="utf-8") as f:
            for s in index:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        (OUT / "agents.json").write_text(json.dumps(levels.cache, indent=1), encoding="utf-8")
    (OUT / "README.txt").write_text(__doc__ + "\nindex.jsonl fields: see summarize() in scripts/escalation_corpus.py\n",
                                    encoding="utf-8")
    hold = sum(s["split"] == "holdout" for s in index)
    print(f"wrote {len(index)} tickets ({hold} holdout) to {OUT}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
