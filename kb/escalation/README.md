# Escalation knowledge base (theme 6a)

Theme 6a asks, when a ticket moves from L2 to L3: did it genuinely need L3? This folder is the standard (`L3_ESCALATION["kb_dir"]` in `config.py`, loaded by `notifier/kb.py`).

## Layout

- **Issue files** (`<family>.md`): one issue family per file. Each uses these headings, in this order:
  - `# Title`: names the family;
  - `## Covers`: sub-issues in the words tickets use (symptoms, error strings, product terms);
  - `## Needs L3 when`: the access or authority L2 lacks;
  - `## L2 can resolve when`: the exact L2 tool or runbook;
  - `## L2 must try first`: checks L2 must do and record before escalating;
  - `## Not a fault`: the customer's own setup or expected behaviour, and what to tell the customer;
  - `## Changed over time`: dated rule changes;
  - `## Examples`: genuine and not-L3 ticket numbers.
- **`_principles.md`**: shared rules, read with every issue file (any file starting with `_` is shared).
- **`reference/`**: background for people. The judge does not read it.
  - `permissions.md`: who can do what, from Notion, corrected by the cases.
  - `rca-standard.md`: the escalation-note standard behind theme 6b.

## How the checker uses it

1. **Choose a file.** Jev, a decision model, picks one issue file by its Title and Covers list, or "none of these" (no alert).
2. **Judge.** Jev answers "did this need L3?" against the chosen file plus `_principles.md` only.
3. **Explain a no.** If the answer is no, Jev chooses why: "L2 can resolve", "steps not tried" or "not a fault". The Slack alert quotes the matching section ("L2 can resolve when", "L2 must try first" or "Not a fault") as "What L2 could have done", cut to 700 characters.
4. **Fallback.** When Jev is unsure (40–60%), fails, or the input is too long, Claude judges, reading every issue file and the principles (not `reference/`), and writes its own reason.

So:
- Covers lists must use ticket wording.
- The three quoted sections must read well on their own in Slack.
- Statements must be short and literal, with no arithmetic or date comparisons.
- Note quality is theme 6b (`notifier/rca.py`), not theme 6a. Keep it out of issue files.

## Maintaining it

1. **Refresh the corpus:** `python scripts/escalation_corpus.py --since <date>` (read-only on Trinity). 1 in 5 tickets goes to a fixed `holdout` split that KB writers never see.
2. **Make digests:** `python scripts/escalation_digest.py --per-family 90` writes train-split digests per family to `data/escalations/digests/`.
3. **Add cases.** Add new cases to the issue file whose Covers matches, citing ticket numbers:
   - put a changed rule under "Changed over time" with its date, and keep the current rule in the main sections;
   - include no personal data: no customer names, emails, app names, domains or IDs;
   - record any contradiction in `data/kb_research/conflicts_*.md`, not in the KB.
4. **Re-run the evaluation:** `python scripts/eval_kb.py --theme 6a`. It judges the labelled holdout cases from escalation-time information and writes `data/escalations/holdout/eval_report.md`. Compare it with the previous report before shipping a KB change.

Keep each issue file under about 2,300 words and `_principles.md` under 700, because Jev is distracted by long text.
