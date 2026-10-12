"""Turn the escalation corpus into compact case digests, grouped by issue family, for the KB analysts.

    python scripts/escalation_digest.py --per-family 90

Reads data/escalations/tickets/*.json (from escalation_corpus.py); writes data/escalations/digests/<family>.md
(train split only: holdout cases are never shown to the people or agents who write the KB) and
data/escalations/stats.md (counts over the whole corpus, both splits).

A digest is what a reviewer needs to judge one escalation: the customer's ask, the escalation note,
every internal note, the escalation audit trail, and how the ticket ended (the last support reply).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path("data/escalations")

# Issue family by tag, first match wins (order matters: the more specific families come first).
FAMILIES = [
    ("mobile_builds", {"expo", "ios builds", "android build", "mobile app", "ios build"}),
    ("custom_domain", {"custom domain", "dns", "ssl", "seo", "domain"}),
    ("database", {"database", "data loss", "mongo", "mongodb", "backup", "restore"}),
    ("billing", {"refund", "billing", "cancel-subscription", "coupons", "referral", "paid support", "credits", "subscription"}),
    ("account_security", {"auth", "account access", "security and compliance", "legal-compliance", "user-blocking", "social", "real-legal"}),
    ("agent_platform", {"agent quality", "agent hung", "agent not waking", "fork", "vs-code", "github", "universal api key",
                        "wingman", "mono", "collab", "agent", "rollback"}),
    ("deployment", {"deployment", "deployment_failure", "nginx", "cors", "prod sos", "sos"}),
]


def family(tags: list[str]) -> str:
    low = {t.lower() for t in tags if t}
    for name, keys in FAMILIES:
        if low & keys:
            return name
    return "other"


def outcome(tk: dict) -> str:
    """Facts only, for stratified sampling. Whether the escalation was right is the analysts' call."""
    tags = {t for t in tk["tags_now"] if t}
    down = any(a["action"] == "level_changed" and a["old"] == "L3" and a["new"] in ("L2", "L1") for a in tk["audit"])
    if "real_l3" in tags:
        return "real_l3_now"
    if "l3_needs_review" in tags and tk["level_now"] in ("L2", "L1"):
        return "needs_review_back_at_l2"
    if "l3_needs_review" in tags:
        return "needs_review_still_l3"
    if down:
        return "moved_down_untagged"
    return "l3_untagged"


def clip(s: str | None, n: int) -> str:
    s = (s or "").strip().replace("\r", "")
    return s if len(s) <= n else s[:n] + " […]"


def digest(tk: dict) -> str:
    tl = tk["timeline"]
    first_customer = next((e for e in tl if e["kind"] == "customer"), None)
    replies = [e for e in tl if e["kind"] in ("agent_reply", "overwatch_auto")]
    last_reply = replies[-1] if replies else None
    lines = [
        f"### Case #{tk['num']} · {clip(tk['subject'], 90)}",
        f"- tags now: {', '.join(t for t in tk['tags_now'] if t)} · level now: {tk['level_now']} · status: {tk['status']}"
        f" · created {tk['created_at'][:10]} · outcome facts: {outcome(tk)}",
    ]
    if first_customer:
        lines.append(f"- customer asked: {clip(first_customer['text'], 700)}")
    trail = [a for a in tk["audit"] if a["action"] in ("level_changed", "tag_added", "tag_removed", "team_assigned",
                                                        "slack_link_updated", "status_changed")
             and (a["action"] != "tag_added" or a["new"] in ("l3_needs_review", "real_l3"))
             and (a["action"] != "tag_removed" or a["old"] in ("l3_needs_review", "real_l3"))]
    if trail:
        lines.append("- escalation trail:")
        for a in trail[:25]:
            by = f"{a['by'].split('@')[0]}({a['by_level'] or a.get('by_role') or '?'})"
            lines.append(f"  - {a['at'][:16]} {by} {a['action']} {a['old'] or ''}→{a['new'] or ''}")
    if tk["internal_notes"]:
        lines.append("- internal notes:")
        for n in tk["internal_notes"][:8]:
            lines.append(f"  - {n['at'][:16]} {n['by'].split('@')[0]}({n['by_level'] or n.get('by_role') or '?'}): "
                         f"{clip(n['text'], 1400)}".replace("\n", " ⏎ "))
    if last_reply:
        lines.append(f"- last reply to customer ({last_reply['by'].split('@')[0]}, {last_reply['kind']}): "
                     f"{clip(last_reply['text'], 600)}".replace("\n", " ⏎ "))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-family", type=int, default=90)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    tickets = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "tickets").glob("*.json"))]
    by_family: dict[str, list[dict]] = defaultdict(list)
    stats = Counter()
    fam_out = defaultdict(Counter)
    notes_present = Counter()
    for tk in tickets:
        f = family(tk["tags_now"])
        o = outcome(tk)
        stats[tk["split"]] += 1
        fam_out[f][o] += 1
        human_escalated = any(a["by"] != "System" and ((a["action"] == "level_changed" and a["new"] == "L3")
                                                       or (a["action"] == "tag_added" and a["new"] == "l3_needs_review"))
                              for a in tk["audit"])
        notes_present["with internal note" if tk["internal_notes"] else "no internal note at all"] += human_escalated
        if tk["split"] == "train":
            by_family[f].append(tk)

    out = ROOT / "digests"
    out.mkdir(exist_ok=True)
    rnd = random.Random(args.seed)
    for f, cases in by_family.items():
        # stratify: an equal share of each outcome where available, then fill
        groups = defaultdict(list)
        for tk in cases:
            groups[outcome(tk)].append(tk)
        for g in groups.values():
            rnd.shuffle(g)
        picked, share = [], max(1, args.per_family // max(1, len(groups)))
        for g in groups.values():
            picked += g[:share]
        rest = [tk for g in groups.values() for tk in g[share:]]
        rnd.shuffle(rest)
        picked += rest[: max(0, args.per_family - len(picked))]
        body = "\n\n".join(digest(tk) for tk in picked)
        (out / f"{f}.md").write_text(f"# {f}: {len(picked)} sampled train cases of {len(cases)}\n\n{body}\n", encoding="utf-8")

    lines = ["# Escalation corpus statistics", "", f"Tickets: {sum(stats.values())} ({dict(stats)})", "",
             "## Outcome facts by issue family (both splits)", "",
             "| family | " + " | ".join(sorted({o for c in fam_out.values() for o in c})) + " | total |",
             "|---|" + "---|" * (len({o for c in fam_out.values() for o in c}) + 1)]
    outs = sorted({o for c in fam_out.values() for o in c})
    for f, c in sorted(fam_out.items(), key=lambda x: -sum(x[1].values())):
        lines.append(f"| {f} | " + " | ".join(str(c[o]) for o in outs) + f" | {sum(c.values())} |")
    lines += ["", "## Human escalations with / without any internal note", "", str(dict(notes_present))]
    (ROOT / "stats.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
