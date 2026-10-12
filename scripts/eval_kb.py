"""Test the rule-6 KB and the rule-7 note check on held-out escalations the KB was never built from.

    python scripts/eval_kb.py                   # theme 6, both checks (6a and 6b), all labelled holdout cases
    python scripts/eval_kb.py --theme 6a --limit 20

Inputs (git-ignored): data/escalations/tickets/*.json (corpus), data/escalations/holdout/labels_set_*.jsonl
(independent labels: verdict and note grade per case, made without seeing the KB).

For each case the checker gets only what it would have had live: the conversation and the escalating
engineer's notes up to 15 minutes after the move to L3. Labels were made with hindsight (what L3 actually
did), so this measures whether the KB predicts the outcome from escalation-time information.

Note: like production, this sends each case's conversation to Jev (Emergent's LiteLLM).
Writes data/escalations/holdout/eval_report.md and eval_cases.jsonl.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dotenv import load_dotenv  # noqa: E402

from notifier.config import load_rules_config  # noqa: E402
from notifier.detectors import CONTEXT_CHARS_PER_MESSAGE, CONTEXT_MESSAGES, NOTE_AFTER, NOTE_BEFORE, NOTE_TOO_SHORT  # noqa: E402
from notifier.kb import JevEscalationJudge, load_kb_files  # noqa: E402
from notifier.rca import JevRcaJudge  # noqa: E402

ROOT = Path("data/escalations")
NOT_NEEDED = {"L2_COULD_RESOLVE", "NO_FAULT_OR_USER_ERROR", "PREMATURE"}
FLAG_GRADES = {"MISSING", "VAGUE", "UNSUPPORTED"}


def escalation(tk: dict) -> dict | None:
    for a in tk["audit"]:
        if a["by"] != "System" and ((a["action"] == "level_changed" and a["new"] == "L3")
                                     or (a["action"] == "tag_added" and a["new"] in ("l3_needs_review", "real_l3"))):
            return a
    return None


def context_at_escalation(tk: dict, esc: dict) -> tuple[str, str, list[str]]:
    """(conversation context as the live detector builds it, the escalator's joined notes, tags at escalation)."""
    t0 = datetime.fromisoformat(esc["at"])
    horizon = t0 + NOTE_AFTER
    lines = []
    rows = [e for e in tk["timeline"] if datetime.fromisoformat(e["at"]) <= horizon and (
        e["kind"] in ("customer", "agent_reply", "overwatch_auto") or (e["kind"] == "internal_note" and e["by"] == esc["by"]))]
    for e in rows[-CONTEXT_MESSAGES:]:
        who = {"customer": "CUSTOMER", "internal_note": "ENGINEER INTERNAL NOTE", "overwatch_auto": "OVERWATCH (AI) REPLY"}.get(
            e["kind"], "SUPPORT REPLY")
        lines.append(f"[{e['at'][:16]} UTC] {who}:\n{(e.get('text') or '')[:CONTEXT_CHARS_PER_MESSAGE]}")
    notes = [n["text"].strip() for n in tk["internal_notes"] if n["by"] == esc["by"]
             and t0 - NOTE_BEFORE <= datetime.fromisoformat(n["at"]) <= horizon and n["text"].strip()]
    tags = [a["new"] for a in tk["audit"] if a["action"] == "tag_added" and datetime.fromisoformat(a["at"]) <= horizon]
    return "\n\n".join(lines), "\n\n".join(notes), [t for t in tags if t]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", choices=["6a", "6b", "both"], default="both",
                    help="6a = did the escalation need L3 (KB); 6b = escalation note (RCA)")
    ap.add_argument("--rule", choices=["6", "7"], help=argparse.SUPPRESS)  # old name: 6 = 6a, 7 = 6b
    ap.add_argument("--limit", type=int)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--set", choices=["holdout", "train"], default="holdout",
                    help="train = the analysts' verdicts on training cases (for tuning); holdout = the final test")
    ap.add_argument("--sample", type=int, help="train only: this many cases, half genuine and half not")
    args = ap.parse_args()
    if args.rule:
        args.theme = {"6": "6a", "7": "6b"}[args.rule]
    load_dotenv()
    rc = load_rules_config()
    key = os.environ["JEV_API_KEY"]
    labels = {}
    sources = sorted((ROOT / "holdout").glob("labels_set_*.jsonl")) if args.set == "holdout" else [ROOT / "train_labels.jsonl"]
    for f in sources:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                labels[int(row["num"])] = row
    files = load_kb_files(rc.L3_ESCALATION["kb_dir"])
    judge6 = JevEscalationJudge(files, rc.JEV_URL, rc.L3_ESCALATION["judge_model"], key, fallback=None)
    judge7 = JevRcaJudge(rc.JEV_URL, rc.L3_ESCALATION["judge_model"], key, fallback=None)
    nums = sorted(labels)[: args.limit] if args.limit else sorted(labels)
    if args.set == "train" and args.sample:
        import random
        rnd = random.Random(5)
        gen = [n for n in nums if labels[n]["verdict"] == "GENUINE_L3"]
        neg = [n for n in nums if labels[n]["verdict"] in NOT_NEEDED]
        rnd.shuffle(gen); rnd.shuffle(neg)
        nums = sorted(gen[: args.sample // 2] + neg[: args.sample // 2])
    sem = asyncio.Semaphore(args.concurrency)
    results = []

    async def one(num: int) -> None:
        path = ROOT / "tickets" / f"{num}.json"
        if not path.exists():
            return
        tk = json.loads(path.read_text(encoding="utf-8"))
        esc = escalation(tk)
        if not esc:
            return
        context, note, tags = context_at_escalation(tk, esc)
        row = {"num": num, "label": labels[num]["verdict"],
               "label_note": (labels[num].get("note_grade") or "UNKNOWN").split(" ")[0].upper()}
        async with sem:
            if args.theme in ("6a", "both"):
                v = await judge6.judge(tk["subject"] or "", context, tags)
                row.update(r6_needs_l3=v.needs_l3, r6_confidence=v.confidence, r6_ref=v.kb_reference, r6_p=v.probability,
                           r6_scores=v.scores,
                           r6_error=v.error, r6_alert=(not v.error and not v.needs_l3 and v.confidence in ("medium", "high")),
                           r6_reason=v.reason)
            if args.theme in ("6b", "both"):
                if not note:
                    row.update(r7="MISSING")
                elif len(note) < NOTE_TOO_SHORT:
                    row.update(r7="VAGUE")
                else:
                    rv = await judge7.judge(note)
                    row.update(r7=rv.verdict, r7_failed=rv.failed, r7_error=rv.error)
        results.append(row)
        print(f"#{num} label={row['label']}/{row['label_note']} r6={'alert' if row.get('r6_alert') else 'ok'} "
              f"r7={row.get('r7')}", file=sys.stderr)

    await asyncio.gather(*(one(n) for n in nums))
    tag = "" if args.set == "holdout" else "_train"
    (ROOT / "holdout" / f"eval_cases{tag}.jsonl").write_text("\n".join(json.dumps(r) for r in results) + "\n",
                                                           encoding="utf-8")
    report(results, tag)


def pct(a: int, b: int) -> str:
    return f"{a}/{b} ({a / b:.0%})" if b else "0/0"


def grid(rs: list[dict]) -> list[str]:
    """Precision / recall of the match rule over thresholds, from the raw scores (no new Jev calls)."""
    scored = [r for r in rs if r.get("r6_scores") and "l3_match" in r["r6_scores"] and r["label"] != "UNCLEAR"]
    neg = [r for r in scored if r["label"] in NOT_NEEDED]
    out = ["", f"Match rule over thresholds ({len(scored)} cases with scores, {len(neg)} not needing L3):", "",
           "| alert when L2/not-a-fault match ≥ | and L3 match ≤ | alerts | right | precision | recall |", "|---|---|---|---|---|---|"]
    for amin in (0.5, 0.6, 0.7, 0.8, 0.9):
        for l3max in (0.1, 0.2, 0.3, 0.4):
            al = [r for r in scored if max(r["r6_scores"]["l2_match"], r["r6_scores"]["nofault_match"]) >= amin
                  and r["r6_scores"]["l3_match"] <= l3max]
            ok = [r for r in al if r["label"] in NOT_NEEDED]
            out.append(f"| {amin:.1f} | {l3max:.1f} | {len(al)} | {len(ok)} | {pct(len(ok), len(al))} | {pct(len(ok), len(neg))} |")
    return out


def report(rs: list[dict], tag: str = "") -> None:
    out = ["# KB evaluation on held-out escalations", ""]
    r6 = [r for r in rs if "r6_alert" in r and r["label"] != "UNCLEAR"]
    if r6:
        judged = [r for r in r6 if not r.get("r6_error")]
        alerts = [r for r in judged if r["r6_alert"]]
        not_needed = [r for r in judged if r["label"] in NOT_NEEDED]
        correct_alerts = [r for r in alerts if r["label"] in NOT_NEEDED]
        uncovered = [r for r in judged if "doesn't cover" in (r.get("r6_reason") or "")]
        out += ["## Theme 6a: did the escalation need L3?", "",
                f"- cases with a clear label: {len(r6)} (UNCLEAR labels left out)",
                f"- judged by Jev (not unsure/failed): {pct(len(judged), len(r6))}; KB said 'not covered': {len(uncovered)}",
                f"- **alerts that were right (precision): {pct(len(correct_alerts), len(alerts))}**",
                f"- wrong escalations caught (recall): {pct(len(correct_alerts), len(not_needed))}",
                f"- genuine escalations wrongly alerted: {pct(len(alerts) - len(correct_alerts), len([r for r in judged if r['label'] == 'GENUINE_L3']))}",
                "", "| label | alert | no alert |", "|---|---|---|"]
        for lab in ("GENUINE_L3", "L2_COULD_RESOLVE", "NO_FAULT_OR_USER_ERROR", "PREMATURE"):
            sub = [r for r in judged if r["label"] == lab]
            out.append(f"| {lab} | {sum(r['r6_alert'] for r in sub)} | {sum(not r['r6_alert'] for r in sub)} |")
        out += ["", "Alert threshold (Jev's P(needed L3) at or below):", "", "| threshold | alerts | right | precision | recall |",
                "|---|---|---|---|---|"]
        for th in (0.10, 0.15, 0.20, 0.30, 0.40):
            al = [r for r in judged if r.get("r6_p") is not None and r["r6_p"] <= th]
            ok = [r for r in al if r["label"] in NOT_NEEDED]
            out.append(f"| {th:.2f} | {len(al)} | {len(ok)} | {pct(len(ok), len(al))} | {pct(len(ok), len(not_needed))} |")
        out += grid(rs)
        out.append("")
    r7 = [r for r in rs if "r7" in r and r["r7"] != "UNKNOWN"]
    if r7:
        flag = [r for r in r7 if r["r7"] in FLAG_GRADES]
        should = [r for r in r7 if r["label_note"] in FLAG_GRADES]
        right = [r for r in flag if r["label_note"] in FLAG_GRADES]
        out += ["## Theme 6b: missing or vague escalation note", "",
                f"- cases judged: {len(r7)} (UNKNOWN = Jev unsure with no fallback: {sum(r['r7'] == 'UNKNOWN' for r in rs if 'r7' in r)})",
                f"- **flags that were right (precision): {pct(len(right), len(flag))}**",
                f"- bad notes caught (recall): {pct(len(right), len(should))}",
                f"- MISSING agreement: {pct(sum(r['r7'] == 'MISSING' and r['label_note'] == 'MISSING' for r in r7), sum(r['label_note'] == 'MISSING' for r in r7))}",
                "", "| label grade | flagged | not flagged |", "|---|---|---|"]
        for g in ("MISSING", "VAGUE", "UNSUPPORTED", "PARTIAL", "COMPLETE"):
            sub = [r for r in r7 if r["label_note"] == g]
            out.append(f"| {g} | {sum(r['r7'] in FLAG_GRADES for r in sub)} | {sum(r['r7'] not in FLAG_GRADES for r in sub)} |")
    text = "\n".join(out) + "\n"
    (ROOT / "holdout" / f"eval_report{tag}.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    asyncio.run(main())
