# L3 escalation knowledge base: how it was researched, built and tested

How the knowledge base (KB) behind the escalation checks was made, from research question to measured results. Written for the support leads and engineers who will review, use or extend it.

- **Built:** 9 October 2026.
- **The KB itself:** `kb/escalation/`.
- **The checks that use it:** themes 6a and 6b of the ticket-hygiene notifier.

---

## Contents

0. [Summary](#0-summary)
1. [Goal and requirements](#1-goal-and-requirements)
2. [Ground rules: data access, privacy, independence](#2-ground-rules-data-access-privacy-independence)
3. [Phase 1: Notion research](#3-phase-1-notion-research)
4. [Phase 2: the escalation corpus from Trinity](#4-phase-2-the-escalation-corpus-from-trinity)
5. [How escalations actually work (what the data showed)](#5-how-escalations-actually-work-what-the-data-showed)
6. [Phase 3: case analysis](#6-phase-3-case-analysis)
7. [The RCA (escalation-note) standard](#7-the-rca-escalation-note-standard)
8. [Phase 4: writing the KB](#8-phase-4-writing-the-kb)
9. [How the checks use the KB](#9-how-the-checks-use-the-kb)
10. [Phase 5: evaluation](#10-phase-5-evaluation)
11. [Limitations and threats to validity](#11-limitations-and-threats-to-validity)
12. [Open decisions and recommended next steps](#12-open-decisions-and-recommended-next-steps)
13. [How to maintain and reproduce](#13-how-to-maintain-and-reproduce)
14. [Index of artefacts](#14-index-of-artefacts)
- [Appendix A: verdict and grading rubrics](#appendix-a-verdict-and-grading-rubrics)
- [Appendix B: per-family analysis results](#appendix-b-per-family-analysis-results)
- [Appendix C: Jev constraints that shaped the design](#appendix-c-jev-constraints-that-shaped-the-design)

---

## 0. Summary

**What was built.** A knowledge base that tells an automated checker two things about every L2→L3 escalation in Trinity:
- **Did it genuinely need L3?** This is theme 6a, `l3_escalation_check`.
- **Is the escalation note a proper RCA?** This is theme 6b, `escalation_note_quality`, which flags missing, too-short, vague and unsupported notes.

**What it rests on:**
- **Notion.** The escalation process, a 51-row permissions table (L1 / L2 / L3 / nobody in support), the Escalation Matrix's note standard, and 216 support playbooks.
- **3,230 real escalations** pulled read-only from Trinity (May to October 2026).
  - 704 of them were judged case by case by analysts.
  - 2,527 escalation notes were measured to define the RCA standard.
  - 1 in 5 tickets was held out and never shown to anyone building the KB.

**What it looks like.** In `kb/escalation/`:
- 8 issue files: deployment, databases, domains/edge, mobile builds, billing, agent/preview/GitHub, accounts/security/legal, integrations;
- `_principles.md`, shared by every judgement;
- `reference/`, with the full permissions table and the RCA standard (for people; the judge does not read it).

**How well it works.** Measured on 146 held-out escalations, labelled independently:

| Check | Alerts that were right | Wrongly flagged | Bad cases caught | Status |
|---|---|---|---|---|
| Theme 6b: missing or vague note | **36 / 38 (95%)** | 2 of 75 adequate notes | 69% | **On** |
| Theme 6a: did it need L3? | **3 / 3** | **0 of 90 genuine escalations** | 10% | Off; decision D13 |

- **Theme 6b is ready.**
- **Theme 6a is safe but cautious.** It never cried wolf in testing, but it only catches the clearest wrong escalations. A first design of theme 6a was tried and rejected: only 31% of its alerts were right. Section 10 explains why.

---

## 1. Goal and requirements

### 1.1 The request

The user specified the KB in three parts (their words, lightly edited):

1. "The difference in permissions and accesses between the two" (L2 and L3).
2. "Review and understand the gaps from referring to old escalation cases. Some of them would be good examples: the L3 solved them, or failed where `l3_needs_review` sent it back to L2 with the internal note message. This would make us understand more about the right and wrong escalations and make cases out of it."
3. "Missing RCA should be flagged immediately, and we have to understand vague RCA as well: where the RCA is not clearly formatted or just not standard. We might get it from the escalation-cases research, to understand the standard RCA."

They also asked:
- to use the connected Notion;
- for "deep research, as the whole backbone is going to be the KB here, so make no mistakes";
- for any other way to make the KB stronger.

### 1.2 How the requirements were interpreted

| Requirement | Delivered as |
|---|---|
| Permissions difference | `kb/escalation/reference/permissions.md`: capability table by tier, from Notion and corrected by observed practice. The judge uses it through the issue files' "Needs L3 when" and "L2 can resolve when" sections. |
| Learn from old cases | 704 escalations judged one by one. Their patterns became the issue files, and their case numbers became the files' examples. |
| Missing or vague RCA | A measured RCA standard and **a separate check (theme 6b)**. A missing note is flagged by code the moment the 15-minute window closes. |
| "Make no mistakes" | A fixed held-out test set, independent labellers, and an honest evaluation before anything was switched on. |

### 1.3 Additions beyond the three points

- **Themes 6a and 6b were kept separate.** The data showed note quality does not predict whether L3 was needed: many thin notes were genuine L3s.
- **Dated rules.** Several L2/L3 boundaries changed during 2026, and the KB records when. Examples: when support could start clearing managed-email suppression, and when the DNS API gained TXT and MX records.
- **"Judge the action, not the actor."** Several reviewers labelled L2 in Trinity do L3-only work, so who fixed a ticket proves nothing about who could have.
- **Warning signs across families,** in `_principles.md`. The strongest is a confident root cause, with no evidence, that L3 later refuted.
- **A record of contradictions:** about 120 conflicts between Notion and practice, each resolved conservatively and listed for a human decision.

---

## 2. Ground rules: data access, privacy, independence

- **Read-only on every system.** Trinity was accessed with a read-only MCP key (`readOnlyKey: true`). Only `list_tickets`, `get_ticket_messages` and `list_agents` were used. Notion was only read: nothing was created, edited or commented on.
- **Customer data stays local.** The corpus, digests, analyses and labels live under `data/`, which is git-ignored. KB files contain only ticket numbers and technical facts, never customer names, emails, app names, domains, URLs or IDs. This was checked mechanically: no emails, non-Notion URLs or UUIDs anywhere in `kb/`.
- **What leaves the machine.** At run time, themes 6a and 6b send the escalated ticket's conversation and note to Jev (Emergent's LiteLLM), and to Claude when the fallback is configured (it needs `ANTHROPIC_API_KEY`). The held-out evaluation did the same for 146 tickets, exactly as production would.
- **Independence:**
  - A fixed 20% of tickets (chosen by a hash of the ticket ID) was held out.
  - Analysts and KB writers never saw those tickets.
  - The held-out answer key was produced by separate labellers who were forbidden to read the KB or the analyses.

---

## 3. Phase 1: Notion research

### 3.1 Method

Two research agents searched the Notion workspace broadly, following links into child pages. They had to cite every claim with its page, quote rule-defining passages verbatim, and mark interpretations as **INFERRED**.

| Track | Output | Size |
|---|---|---|
| Escalation process and L1/L2/L3 permissions | `data/kb_research/notion_process_permissions.md` | about 500 lines |
| RCA and note standards, plus runbooks per issue family | `data/kb_research/notion_rca_runbooks.md` | about 3,450 lines, about 1,770 citations |

### 3.2 Source quality

Most Notion pages are unverified. Several of the richest sources are **personal working copies** written by a support L3 engineer with AI assistance:
- the Ticket Casebook;
- the "Architecture & Support Playbooks" mirror;
- the CS-Playbook DB.

They are detailed and checked against code, but they are not official policy. The official or semi-official pages are:
- Support Guide (2026-03-11)
- L3 Primary OnCall - KT (2026-09-27)
- Deployments L3 Oncall Guide (2026-09-30)
- QA OnCall – Production Issue Tracking (2026-09-25)
- Retention on-call

Where sources disagreed, the KB took the conservative side (section 8.3).

### 3.3 Key findings

**What "L3" means.** It means two things in practice:
- **Officially, an engineering-level escalation:** "only after L1/L2 playbooks fail", closed within 24 hours. The L3 teams in Trinity are Deployment, Expo, Conversion, Retention and Wingman.
- **In practice, also a senior support tier.** Some support staff were moved from L2 to L3, and 216 playbooks label each symptom L1, L2, L3 or "Eng".

**Escalation mechanics.** No formal SOP exists. What exists:
- **When to escalate:** when a fix needs a production write that is not in a runbook, or when you are less than 90% sure of the root cause.
- **What the internal note must contain** (Escalation Matrix): "Job ID, User ID, App, Root Cause, and either Fix Applied or precisely what eng must do", plus the matching runbook link.
- **Customer wording:** escalation language may go to the customer only after the escalation is confirmed.

**The two tags.** Neither is formally defined. In practice:
- `real_l3` = "a human has judged this genuinely L3";
- `l3_needs_review` = "flagged for a second pair of eyes".

**What L2 can do itself,** so escalating these is likely wrong:
- Mongo point-in-time restore (up to 7 days, up to 2 GiB) and Mongo dump export;
- domain transfer-out / EPP;
- TXT and MX records on Emergent-bought domains;
- replaying a lost fork-completed event;
- clearing managed-email suppression (from a date in late September);
- turning off the private-access wall;
- SSL reconcile.

**What L2 cannot do:**
- pod exec / kubectl;
- S3 and snapshot restores;
- Postgres writes.

**What nobody in support can do:**
- subscription writes;
- credential rotation (the Deployment team does it);
- deleting jobs behind admin allow-lists;
- platform code changes.

**Money limits.** Credit grants are capped by the customer's LTV bracket, with an approver above that. Dollar refunds auto-approve below a default limit. The values conflict across pages.

**Metrics.** The Deployment team's own review of 51 real-L3 tickets found about a third had no platform fault. So `real_l3` is not ground truth.

**The RCA standard.** No QA rubric exists for human support notes. The only graded RCA rubric is for the deployer AI agent, and it names a failure mode, `HALLUCINATED_RCA`: a real symptom with an unproven cause attached. It was adapted for theme 6b.

---

## 4. Phase 2: the escalation corpus from Trinity

### 4.1 What Trinity can return

The Trinity MCP API was probed before any script was written:
- `list_tickets` filters by `level` and `tags`;
- `get_ticket_messages` returns the full timeline, internal notes included;
- `list_agents` returns each agent's `support_level`, but caps at 200 agents. Support levels were therefore looked up per email.

| Filter | Tickets | Created |
|---|---|---|
| tag `l3_needs_review` | 1,119 | 25 May to 9 Oct 2026 |
| tag `real_l3` | 1,951 | 18 May to 9 Oct 2026 |
| currently at level L3 | 4,750 | June 2025 to 9 Oct 2026 |

### 4.2 Selection and extraction

`scripts/escalation_corpus.py` collected:
- **The tickets:** the union of all three filters, restricted to tickets created on or after **2026-05-18**, when tagging began. That gave **3,230 tickets**, all pulled with 0 failures.
- **The full timeline of each ticket,** saved as compact JSON:
  - internal notes, up to 6,000 characters each;
  - customer and agent messages, up to 1,500 characters;
  - AI drafts, up to 300 characters;
  - the audit trail: level changes, tags added and removed, team assignment, Slack thread link, assignment and status.
- **Each actor's support level and role.**
- **A derived summary per ticket,** in `index.jsonl`:
  - who escalated, when, and how;
  - the escalator's note near the escalation;
  - who added or removed `l3_needs_review` and `real_l3`;
  - any moves back down from L3;
  - teams, the Slack thread, and the RCA note authors.

### 4.3 The split

Each ticket was assigned to `holdout` when `sha1(ticket_id) mod 5 == 0`, otherwise to `train`. That gave **687 holdout tickets and 2,543 train tickets**. The split is fixed: re-running the scripts reproduces it.

### 4.4 Corpus statistics

These outcome facts are raw tags and levels, not verdicts. They come from `data/escalations/stats.md`.

| Family (by tag) | real_l3 now | needs_review, still L3 | needs_review, back at L2 | Other | Total |
|---|---|---|---|---|---|
| custom_domain | 287 | 293 | 9 | 18 | 607 |
| database | 385 | 204 | 2 | 13 | 604 |
| mobile_builds | 405 | 135 | 11 | 49 | 600 |
| billing | 426 | 107 | 7 | 25 | 565 |
| deployment | 141 | 150 | 0 | 29 | 320 |
| agent_platform | 164 | 103 | 4 | 24 | 295 |
| account_security | 82 | 55 | 0 | 5 | 142 |
| other | 61 | 29 | 2 | 5 | 97 |

**Notes per escalation:** 3,022 human escalations had at least one internal note on the ticket; **188 had none at all.**

---

## 5. How escalations actually work (what the data showed)

Real timelines were read before any rubric was designed. They overturned several naive assumptions.

**The observed flow:**
1. The L2 engineer writes an internal note, for example "Job id … Issue … To reproduce …".
2. They unassign themselves, set the level L2→L3, and add `l3_needs_review`.
3. A **reviewer** may write an "RCA:" note, swap `l3_needs_review` for `real_l3`, assign an engineering team (e.g. Expo Team) and link a Slack thread.
4. An engineer outside support fixes the issue, often moves the level **L3→L2**, and writes a short note ("Fixed the preview").
5. Support replies to the customer and closes the ticket.

**Consequences for the research:**
- **"Moved back to L2" usually means fixed, not rejected.** It cannot serve as a label.
- **`real_l3` is a human judgement,** often applied by the escalating engineer themselves. Across the analyses:
  - a self-applied `real_l3` was genuine **56%** of the time (65 of 117);
  - when a reviewer applied it, **78%** (106 of 136).
- **Trinity's level label does not tell you what someone can do.** Several reviewers are labelled L2 but routinely do L3-only actions: edge-config PATCH, jumpbox, credential rotation, kubectl-level repairs. So every verdict was based on **the action the fix required**, not on who performed it.
- **Some May–June escalation notes were logged as System replies,** not internal notes. Theme 6b therefore only runs on today's ticket format, and the held-out set starts in July.
- **Tags mislead.** In every family, a large share of tickets were about something else. For example, 51 of 90 "billing" cases were really agent or preview tickets that only carried a refund tag. The KB is organised by the actual problem, and the checker chooses a KB file from the ticket's content, not its tags.

**Corrected picture.** The only reliable labels come from reading what happened: who fixed it, with which tool or authority, and whether there was a platform fault at all. That is why the case analysis (section 6) reads each case end to end.

---

## 6. Phase 3: case analysis

### 6.1 Digests and sampling

`scripts/escalation_digest.py` turned each **train** ticket into a 2–4 KB digest:
- the customer's first message;
- the escalation trail (level, tag, team, Slack and status changes, each with the actor and their level);
- every internal note, up to 1,400 characters each;
- the last reply to the customer, which usually says how it was resolved.

Tickets were grouped into eight families by tag. Each family was sampled to **90 cases**, stratified by outcome so that each outcome type was represented. The "other" family had 74.

### 6.2 Rubric

Eight analysts (one per family) judged every sampled case. A ninth analysed notes across all families (section 7).

**Verdicts:**
- **GENUINE_L3:** the fix needed access or authority L2 lacks, or a platform fix.
- **L2_COULD_RESOLVE:** L2 had the tool, runbook or permission; the analyst named it.
- **NO_FAULT_OR_USER_ERROR:** nothing to fix at L3; the customer's own setup, or expected behaviour.
- **PREMATURE:** L2 skipped required first steps.
- **UNCLEAR:** not enough evidence.

**Note grade** for the escalating engineer's own note, against the Escalation Matrix fields:
- COMPLETE
- PARTIAL (with the missing fields listed)
- VAGUE
- UNSUPPORTED
- MISSING

Full definitions are in Appendix A.

Each analyst also:
- synthesised the family's sub-issues, each with "Needs L3 when", "L2 can resolve when", "L2 must try first", typical wrong escalations (with case numbers), and the evidence that tells the two apart;
- counted verdicts and note grades;
- listed contradictions with Notion;
- drafted a KB file.

**Instructions given to every analyst:**
- Ground every claim in a case number or a Notion citation, and mark guesses as INFERRED.
- Open full timelines only for digest cases, never held-out tickets. Several analysts checked this with a script.
- Judge by the action required, and by the rules in force on the ticket's date.

### 6.3 Results

| Family | Cases | Genuine L3 | L2 could resolve | No fault / user error | Premature | Unclear |
|---|---|---|---|---|---|---|
| Deployment | 90 | 52 | 8 | 20 | 4 | 6 |
| Database | 90 | 57 | 18 | 11 | 0 | 4 |
| Custom domain | 90 | 55 | 16 | 16 | 1 | 2 |
| Mobile builds | 90 | 47 | 24 | 8 | 4 | 7 |
| Billing | 90 | 49 | 14 | 18 | 3 | 6 |
| Agent / platform | 90 | 53 | 14 | 14 | 3 | 6 |
| Accounts / security | 90 | 50 | 22 | 8 | 3 | 7 |
| Other | 74 | 37 | 12 | 14 | 2 | 9 |
| **Total labelled** | **704** | **400** | **128** | **109** | **20** | **47** |

Overall, **257 of 657 clearly labelled escalations (39%) did not need L3.** Appendix B gives the note grades and family-specific findings.

### 6.4 Findings across families

1. **The type of request decides genuineness; note quality does not.** For example, 21 billing cases with vague or missing notes were still genuine.
2. **A confident cause with no evidence, later refuted by L3, is the strongest single warning sign.** UNSUPPORTED notes were on not-genuine cases 46 of 67 times. The signal is weaker in database (3 of 7) and agent/platform (4 of 8).
3. **"No tool exists" claims are often false.** Examples:
   - 6 of 9 database-export escalations said no tool makes a BSON archive. Each was then delivered through the L2 Dump Export API.
   - EAS logs were wrongly believed unreadable by L2.
   - The crawler toggle was wrongly believed hidden.
4. **Some escalation notes contain the runbook fix itself.** An L2 engineer verified the private-access wall was on, wrote the exact internal call that turns it off, and still escalated.
5. **L1 skipping L2.** In accounts and security, 28 escalations went straight from L1 to L3; 12 were L2 work and 19 had vague notes. This signal is weak in other families.
6. **Fixer level misleads,** as described in section 5.
7. **Rules changed during 2026.** Examples:
   - managed-email suppression clearing moved to support around 25 September;
   - TXT and MX records via the DNS API arrived around mid-July;
   - export size caps and job-transfer fixes changed too.

   Verdicts must use the rule in force at the time, and the KB records the dates.
8. **Security finding (outside scope).** Customer secrets were pasted into notes or replies (#47773, #51408, #35025). These should be handled as security incidents.

---

## 7. The RCA (escalation-note) standard

A dedicated analyst measured the **train** corpus: 2,527 human escalations, of which 2,054 were by L1 or L2 agents. Output: `data/kb_research/rca_standard.md`.

### 7.1 Measurements

**Missing notes.** No note by the escalator from 6 h before to 1 h after the move: **12.7%** of escalations (12.4% for L1/L2 escalators).
- 142 tickets (5.6%) had no internal note at all.
- Mobile builds is the worst family, at 28.5%.
- The rate fell from 58% in May to about 10% from August.

**Timing.** When was the note written, relative to the move?
- 83% within 1 minute before it;
- 98.9% within 6 hours before it;
- of notes written after the move, 93% within 15 minutes.

**Length.**
- Median 738 characters (p25 295, p90 2,160).
- Every sampled note under 150 characters was vague.

**Required fields,** by regex heuristic:

| Field | Share of notes |
|---|---|
| Job ID | 64% |
| User ID or account email | 19% |
| App | 19% |
| Cause words | 54% |
| Ask words | 47% |
| Steps or reproduction | 21% |

- **Only 3.1%** have all five Escalation Matrix fields.
- 20% have no cause, ask or evidence words at all.

**Manual classification of 152 notes (19 per family):**

| Grade | Notes |
|---|---|
| Complete | 42 |
| Partial | 43 |
| Vague | 47 |
| Unsupported | 4 |
| Missing | 16 |

Projected over all train escalations: about 28% complete, 29% partial, 27% vague, 2% unsupported and 13% missing, each ±8 points.

### 7.2 Definitions used by theme 6b

- **MISSING (code).** No internal note by the escalating engineer between **6 hours before** and **15 minutes after** the move.
  - Notes by other people or by System/Overwatch don't count.
  - It is decided 15 minutes after the move.
- **Too short (code).** A joined note under **80 characters** counts as VAGUE without asking a model. Examples: "in L3", "escalated to L3", "looking.". This covers 4.6% of L1/L2 escalations.
- **Six yes/no questions for Jev,** each with literal TRUE and FALSE criteria:

| # | Question | Short name |
|---|---|---|
| 1 | Is there an identifier (job, user, app, deployment…)? | identifier |
| 2 | Did the engineer report a check they ran, with its result? | own check |
| 3 | Is there a specific cause, the specific reason support can't act, or "cause not confirmed" plus what was ruled out? | cause |
| 4 | Is there a re-checkable observation (log line, query result, HTTP status, repro, code line, config value…)? | evidence |
| 5 | Is there an exact action for L3 on a named object, or a fix already applied? | ask |
| 6 | Is it mainly the engineer's own hand-off, not pasted customer or AI text? | own hand-off |

**Scoring:**
- **VAGUE** when the note is mainly pasted text (Q6 no), or has neither a cause nor an ask (Q3 and Q5 both no).
- **UNSUPPORTED** when it is not vague, names a cause, and has no evidence (Q3 yes, Q4 no).
- **COMPLETE** when all six are yes.
- **PARTIAL** otherwise.
- VAGUE, UNSUPPORTED and MISSING are flagged. PARTIAL is listed in the dashboard only.

**Validation by the analyst:** 40 hand-classified notes. The rule matched the analyst's four-way grade 80% of the time and the flag/no-flag decision 97.5% of the time (12 of 12 bad notes caught, 1 false flag). Two of the eight disagreements were the analyst's own labelling errors.

The standard, a copy-paste template, and good and bad examples are in `kb/escalation/reference/rca-standard.md`.

---

## 8. Phase 4: writing the KB

### 8.1 The writers' brief

One shared brief (`data/kb_research/WRITER_BRIEF.md`) fixed the format and rules for all nine writers.

**Fixed headings, in order:**
- `# Title`
- `## Covers`
- `## Needs L3 when`
- `## L2 can resolve when`
- `## L2 must try first`
- `## Not a fault`
- `## Changed over time`
- `## Examples`

**Rules:**
1. State today's rule; older rules go under "Changed over time".
2. Judge by the action needed, not the fixer.
3. Ground every bullet in case numbers or a cited Notion rule. Where evidence is thin or conflicting, be conservative and log the conflict.
4. At most about 2,300 words per file and 700 for the principles, because Jev is distracted by long text.
5. No personal data.
6. No note-quality content, which is theme 6b.
7. **Use evidence from every analysis file,** because tags lie.

**Written for a literal reader.** Covers lists use the wording of real tickets (error strings, product terms). Limits are written in words ("a deleted record older than 7 days"), never as calculations.

### 8.2 The files

| File | Words | Main contents |
|---|---|---|
| `deployment-and-publishing.md` | ~2,000 | publish stuck, Cloud Build, source workspace, live app down, secrets, rollback, system packages, capacity, Prod SOS |
| `databases-and-data.md` | ~2,100 | PITR limits, dump export, export cap, credential rotation, dedicated DB, repointing, data after publish |
| `domains-dns-edge-seo.md` | ~2,350 | connect, SSL/reconcile, DNS records on bought domains, EPP/registrar, edge-config, worker/zone, headers, crawler/SEO |
| `mobile-builds.md` | ~2,200 | build failures, "Entity not authorized", versionCode / remote versioning, TestFlight, ITMS, credentials, store issues |
| `billing-credits-subscriptions.md` | ~2,380 | refunds, credit grants and approvers, credits missing, plans not provisioned, subscriptions, coupons, disputes |
| `agent-preview-fork-github.md` | ~2,370 | agent hung, preview/workspace storage, doom loops, fork replay, GitHub, VS Code, archive, rollback, transfer, Wingman |
| `accounts-security-legal.md` | ~2,330 | login/OTP, blocks and phishing flags, ownership, deletion, private-access wall, security reports, legal/compliance |
| `integrations-keys-connectors.md` | ~2,390 | Universal Key, wallets, MCP connector, managed Stripe/email/storage, third-party, feature requests |
| `_principles.md` | ~700 | the general test, what does not decide it, warning signs (with measured rates) |
| `reference/permissions.md` | n/a | 51 Notion rows plus 17 observed rows; about 30 marked where practice differs |
| `reference/rca-standard.md` | n/a | the theme-6b standard, template, examples |
| `README.md` | ~500 | layout, how the checker uses it, maintenance |

**Validation.** Every issue file has the three sections the alerts quote. Every Covers list parses: 1,500–2,250 characters of routing terms per file.

### 8.3 Conflicts and how they were resolved

The writers recorded about 120 contradictions between Notion and practice in `data/kb_research/conflicts_*.md`. Each has the case numbers on both sides and the choice made.

**Policy:** when uncertain, keep the case as **L3**. That leans towards no alert, because a wrong alert costs an engineer's trust and an associate's time.

**The conflicts that most affect verdicts:**
- **L3-only tools that L2 accounts use routinely:** edge-config PATCH, `clear-asc-credentials`, credential rotation, system packages.
- **Export size cap:** 1 GiB or 3 GiB.
- **Credit caps and refund limits**, which conflict across Notion pages.
- **Rule switch dates.**
- **Self-applied `real_l3`:** whether it should itself be flagged.
- **L1 escalations that skip L2.**

These are listed for decision in `pending_decisions.md` (D14).

---

## 9. How the checks use the KB

Both checks fire when a monitored engineer moves a ticket to L3: setting the level to L3, or adding `l3_needs_review` or `real_l3`. Several moves by the same engineer within 30 minutes count as one escalation. Both checks wait **15 minutes**, which covers 93% of notes written after the move. Neither fires if the same engineer takes the ticket back within that time.

### 9.1 Theme 6a (`notifier/kb.py`, `JevEscalationJudge`)

1. **Choose a file.** Jev answers one choice question.
   - The options are "none of these", listed first so that Jev's first-option bias leans towards no alert, followed by each issue file's Title and Covers list.
   - Only the ticket is in the request, so the whole KB never has to fit into Jev's ~32k-token limit.
   - "None of these" means no alert.
2. **Match bullets.** In one request, Jev reads the chosen file, `_principles.md` and the ticket, and gives three yes/no probabilities:
   - Does a "Needs L3 when" bullet describe this ticket?
   - Does an "L2 can resolve when" bullet describe it?
   - Does a "Not a fault" bullet describe it?
3. **Decide.**
   - **Alert** only when an L2 or not-a-fault bullet matches at **70% or more** and an L3 bullet matches at **30% or less**. The alert quotes the matching KB section as "What L2 could have done".
   - **No alert** when an L3 bullet matches at 60% or more, or when nothing on the L2 side matches above 40%.
   - **In between:** Claude decides, if `ANTHROPIC_API_KEY` is set. Claude reads the whole KB. Without the key, the case is logged as not judged and never alerted.
4. **Logging.** Every verdict records its raw scores for evaluation, and every alert says who judged it.

### 9.2 Theme 6b (`notifier/detectors.py`, `notifier/rca.py`)

1. The escalator's own notes from 6 h before to 15 min after the move are joined into one text.
2. **None:** MISSING, flagged immediately by code.
3. **Under 80 characters:** VAGUE, flagged by code.
4. **Otherwise:** Jev answers the six questions in one call.
   - Claude takes over if Jev is unsure (35–65%) on cause, evidence or own hand-off, or if the note is over 4,000 characters.
   - The fixed scoring rule then decides: VAGUE and UNSUPPORTED are flagged, and the alert names what is missing.

---

## 10. Phase 5: evaluation

### 10.1 The answer key

From the **holdout** split, every human escalation created **from July 2026** was taken: 520 tickets. July is when notes are reliably internal notes and today's rules apply. From those, **146 cases** were sampled, about 20 per family (only 6 existed in "other").

Two independent labellers each took half. They used the Notion research and the same verdict and grading rubric as the analysts. They were **not allowed to read the KB, the case analyses or the RCA standard file**, and they labelled with hindsight: what L3 actually did.

| Labels | Genuine L3 | L2 could resolve | No fault | Premature | Unclear |
|---|---|---|---|---|---|
| Set 1 (73) | 46 | 11 | 10 | 3 | 3 |
| Set 2 (73) | 53 | 3 | 9 | 0 | 8 |
| **Total (146)** | **99** | **14** | **19** | **3** | **11** |

| Note grades | Complete | Partial | Vague | Unsupported | Missing |
|---|---|---|---|---|---|
| Set 1 | 7 | 35 | 12 | 5 | 14 |
| Set 2 | 2 | 39 | 19 | 7 | 6 |

### 10.2 Method

`scripts/eval_kb.py` rebuilds, for each case, **only what the checker would have seen live**:
- the conversation;
- the escalator's notes up to 15 minutes after the move;
- the tags at that moment.

It then runs the real judges against Jev and compares them with the labels.

**Metrics:**
- **Precision** (the headline): of the alerts raised, how many were right.
- **Recall:** of the cases that should alert, how many did.
- **False alarms on genuine escalations.**
- **Coverage:** how many cases Jev decided, rather than being unsure.

UNCLEAR labels are left out.

### 10.3 Theme 6a, first design: rejected

The first judge asked one broad question: "Using only the KB file, did this escalation genuinely need L3?" Its TRUE criterion required both:
- the issue is reserved for L3;
- the conversation shows L2 tried the required first steps.

| Held-out result (135 clear labels) | Value |
|---|---|
| Decided by Jev | 103 (76%) |
| Alerts that were right | **26 of 83 (31%)** |
| Wrong escalations caught | 26 of 28 (93%) |
| Genuine escalations wrongly flagged | **57 of 75** |

**Diagnosis.** At escalation time the conversation rarely shows L2's steps, so the "both conditions" criterion pushed Jev to "no" almost every time. No threshold fixed it: at the strictest setting, 1 of 3 alerts was right.

### 10.4 Redesign and tuning, on train cases only

Jev's strength is literal matching, so the single judgement was replaced by **three match questions** (section 9.1).

The held-out results had now been seen, so tuning moved to **train cases**:
- 260 cases sampled from the analysts' 704 labels, half genuine and half not;
- 251 had full scores.

The raw scores were collected once and the thresholds were searched offline:

| Alert when L2 or not-a-fault match ≥ | and L3 match ≤ | Alerts | Precision (train) | Recall (train) |
|---|---|---|---|---|
| 0.5 | 0.4 | 37 | 86% | 26% |
| 0.6 | 0.3 | 25 | 88% | 18% |
| **0.7** | **0.3** | **21** | **95%** | **16%** |
| 0.8 | 0.3 | 15 | 93% | 11% |

The strict setting (0.7 / 0.3) was chosen, because a wrong alert costs more than a missed one.

**Leakage warning.** On the same train cases even the rejected first design scored 84–92% precision. The KB was written from these exact cases, so train scores are optimistic and cannot be used as accuracy. They were used only to choose the shape of the check.

### 10.5 Theme 6a, built design: final held-out result (run once)

| Held-out result (135 clear labels) | Value |
|---|---|
| Decided by Jev | 119 (88%) |
| KB "not covered" | 2 |
| **Alerts that were right** | **3 of 3** |
| **Genuine escalations wrongly flagged** | **0 of 90** |
| Wrong escalations caught | 3 of 29 (10%) |

| Label | Alert | No alert |
|---|---|---|
| Genuine L3 | 0 | 90 |
| L2 could resolve | 1 | 10 |
| No fault / user error | 1 | 14 |
| Premature | 1 | 2 |

**Interpretation.** The built design is **safe but cautious**. On unseen tickets the wording rarely matches a KB bullet confidently, so it speaks only on the clearest cases. With only 3 alerts, the precision figure has a wide margin of error.

### 10.6 Theme 6b: held-out result

| Result | Value |
|---|---|
| Judged | 127 (19 more where Jev was unsure and no fallback is set yet) |
| **Flags that were right** | **36 of 38 (95%)** |
| Bad notes caught | 36 of 52 (69%) |
| MISSING agreement | 19 of 20 |

| Label grade | Flagged | Not flagged |
|---|---|---|
| Missing | 19 | 1 |
| Vague | 16 | 4 |
| Unsupported | 1 | 11 |
| Partial | 1 | 65 |
| Complete | 1 | 8 |

**Weak spot:** UNSUPPORTED notes, a cause with no evidence. Jev tends to accept a confidently written cause as evidenced.

### 10.7 Smoke test

Before the evaluation, both judges were run against real Jev on 4 train cases to check the plumbing: file choice, section quoting and note grades.
- **3 of 4 routings and verdicts matched the analysts.**
- **The fourth, #273152 (credential rotation),** was judged "L2 can resolve". The KB says rotation is L3, so on the KB's own terms this is a false alarm. It is, however, the very case the database analyst flagged as a sign that support may now have a rotation tool (D14).

---

## 11. Limitations and threats to validity

- **Labels are model-made, not human.** The analysts and labellers worked carefully and cited evidence, but no support lead reviewed their verdicts. Hard cases are listed in the label files.
- **Small held-out negatives.** Only 36 held-out cases didn't need L3, and theme 6a alerted 3 times. Precision estimates for theme 6a are therefore uncertain.
- **Hindsight gap.** Labels use what happened later, while the checker sees only escalation-time information. Some wrong escalations cannot be recognised at the moment they happen.
- **Leakage on train.** The KB was written from the train cases, so train scores overstate accuracy. Only held-out numbers are reported as performance.
- **Source quality.** Several key Notion sources are personal working copies, and some Notion rules conflict with each other or with practice (about 120 recorded conflicts).
- **Date-dependence.** Rules changed during 2026. The KB states today's rules, so older cases may be judged against rules that were not yet in force.
- **Coverage without a fallback.** Without an `ANTHROPIC_API_KEY`, about 12% of theme-6a cases and 13% of theme-6b cases are not judged at all. They are never alerted.

---

## 12. Open decisions and recommended next steps

All of these are in `pending_decisions.md`.

| ID | Decision | Recommendation |
|---|---|---|
| **D13** | Turn theme 6a on as it is, add a Claude key and re-measure, or run it visible only in the dashboard first. | Add `ANTHROPIC_API_KEY`, re-run `python scripts/eval_kb.py`, then go live in the dashboard first. |
| **D14** | About 120 KB contradictions between Notion and practice. | A support lead reviews them; each decision is a one-line KB edit. |
| **D15** | Theme 6b: notify on PARTIAL notes? Accept a colleague's note? Apply to L1? | Notify only MISSING, VAGUE and UNSUPPORTED (current behaviour); show the colleague's name on MISSING. |

**Ways to make the KB stronger over time:**
1. **Feed associates' verdicts back in.** The dashboard records "correct" and "false alarm" on every alert. Add confirmed cases as KB examples monthly.
2. **Refresh the corpus monthly** and re-run the held-out evaluation before shipping any KB change.
3. **Have a support lead review the held-out labels.** That turns the answer key into human ground truth.
4. **Close the Notion gaps the research found:** tag definitions, the reviewer role, a reject or send-back policy, Prod SOS criteria, and the missing versionCode playbook.

---

## 13. How to maintain and reproduce

Run from the project folder; `py` is `.venv\Scripts\python.exe`.

| Step | Command |
|---|---|
| Rebuild the corpus (read-only on Trinity) | `py scripts\escalation_corpus.py --since 2026-05-18` |
| Make train digests per family | `py scripts\escalation_digest.py --per-family 90` |
| Measure themes 6a and 6b on held-out escalations | `py scripts\eval_kb.py` → `data\escalations\holdout\eval_report.md` |
| Tune on train cases (never the holdout) | `py scripts\eval_kb.py --set train --sample 260 --theme 6a` |
| Tests | `py -m pytest` |

**Editing the KB.** Follow `kb/escalation/README.md`:
- keep the headings;
- cite case numbers;
- put changed rules under "Changed over time";
- no personal data;
- keep files at or under about 2,300 words.

Re-run the held-out evaluation after any change, and compare against the previous report.

---

## 14. Index of artefacts

| Path | What | In git? |
|---|---|---|
| `kb/escalation/*.md`, `kb/escalation/reference/*.md` | The KB | yes |
| `notifier/kb.py` | Theme 6a judges (Jev match questions, Claude fallback), KB loader | yes |
| `notifier/rca.py`, `notifier/detectors.py` (theme 6b part) | Theme 6b | yes |
| `scripts/escalation_corpus.py`, `escalation_digest.py`, `eval_kb.py` | Corpus, digests, evaluation | yes |
| `data/kb_research/notion_process_permissions.md` | Notion research: process and permissions | no (local) |
| `data/kb_research/notion_rca_runbooks.md` | Notion research: RCA standards and runbooks | no |
| `data/kb_research/cases_<family>.md` | The 8 case analyses (verdict tables, patterns, counts, conflicts, drafts) | no |
| `data/kb_research/rca_standard.md` | RCA measurements and definitions | no |
| `data/kb_research/conflicts_*.md` | Contradictions per KB file | no |
| `data/kb_research/WRITER_BRIEF.md` | The brief the KB writers followed | no |
| `data/escalations/tickets/*.json`, `index.jsonl`, `stats.md` | The corpus (contains customer conversations) | **never** |
| `data/escalations/train_labels.jsonl` | Analysts' 704 train verdicts | no |
| `data/escalations/holdout/labels_set_*.{md,jsonl}` | Independent held-out labels | no |
| `data/escalations/holdout/eval_report*.md`, `eval_cases*.jsonl` | Evaluation reports and per-case results | no |

---

## Appendix A: verdict and grading rubrics

**Verdicts** (did the escalation need L3?):

| Verdict | Meaning |
|---|---|
| GENUINE_L3 | The fix needed access or authority L2 lacks, or a platform code or config fix. Approver, legal or security authority counts. |
| L2_COULD_RESOLVE | A documented L2 runbook, tool or permission would have fixed it. The analyst named which. |
| NO_FAULT_OR_USER_ERROR | Nothing to fix at L3: the customer's own code, config or account, or expected behaviour. |
| PREMATURE | Required first checks were skipped, for example the PITR preview, a fork-state check, or confirming no migration ran. |
| UNCLEAR | The ticket does not show what fixed it, or it resolved without action. |

**Rules applied with every verdict:**
- judge by the action the fix needed, not by who did it;
- use the rules in force on the ticket's date;
- `real_l3`, moving back to L2, and team routing are not evidence either way.

**Note grades** (the escalating engineer's own note, 6 h before to 15 min after the move):

| Grade | Meaning |
|---|---|
| COMPLETE | Has an identifier, a root cause (or the reason support can't act), evidence, and the exact ask or fix applied. |
| PARTIAL | Usable but missing fields, most often the User ID or an exact ask. |
| VAGUE | Symptom only, or no cause and no exact ask, or mainly pasted customer or AI text, or under 80 characters. |
| UNSUPPORTED | Asserts a cause with no re-checkable evidence. |
| MISSING | No note by the escalator in the window. |

---

## Appendix B: per-family analysis results

Every count is from the analysts' tables. `real_l3` genuineness means: of the cases ever tagged `real_l3`, how many the analyst judged genuine.

| Family | Note grades (C / P / V / U / M) | `real_l3` genuine | Notable patterns |
|---|---|---|---|
| Deployment | 7 / 58 / 11 / 6 / 8 | 27 of 38 | Source-workspace failures and capacity errors almost always genuine. App-side faults blamed on the platform: 0 of 8 genuine. Managed Stripe/email/storage mostly not L3. |
| Database | 10 / 51 / 13 / 7 / 9 | 36 of 44 | Credential rotation 6 of 6 genuine. Database exports the main invalid pattern (Dump Export API). All 7 unsupported notes refuted by L3. |
| Custom domain | 5 / 45 / 16 / 11 / 13 | 31 of 40 | L2 handles TXT/MX, EPP, reconcile and the crawler toggle. CNAME on bought domains, registrar work, edge-config and zone settings are L3. 24 genuine cases never got `real_l3`. |
| Mobile builds | 5 / 39 / 15 / 11 / 20 | 25 of 35 | "Entity not authorized", remote-versioning versionCode and TestFlight VM/key failures always genuine. Customer project config often wrongly escalated. No playbook exists for remote versioning. |
| Billing | 3 / 44 / 26 / 9 / 8 | 24 of 41 | Only 37 of 90 were true billing cases. Coupon attachment, provisioning, gateway moves and post-dispute unblock genuine. Misread plan terms and promo gates are L2. |
| Agent / platform | 2 / 38 / 32 / 8 / 10 | 29 of 43 | Preview/workspace storage 17 of 21 genuine. GitHub mostly not L3 (2 of 8). Fork-replay variant when no child job exists. |
| Accounts / security | 4 / 43 / 28 / 7 / 8 | 34 of 51 | Privileged deletes, SSO merge, OTP limits and legal genuine. Private-access wall, GDPR questions and "two accounts" are L2. 28 L1→L3 skips. |
| Other | 5 / 32 / 22 / 8 / 7 | 28 of 47 | Mostly a tag-mapping failure. Deletion requests 7 of 7 genuine. Universal Key mostly user error. A confident wrong root cause is the strongest "not genuine" signal. |

---

## Appendix C: Jev constraints that shaped the design

Jev (`jev-latest`, Jev 1.13, via Emergent's LiteLLM `/typesafe` route) is a decision model. These properties shaped the design:

| Property | How it shaped the design |
|---|---|
| Answers yes/no (`noul`) and choice questions; no free text | Alerts quote KB sections instead of generating explanations. |
| A choice question needs a `criteria` map from each option to its description | File choice uses each file's Title and Covers list as the option criteria. |
| About a 32k-token limit on the state (~110k characters fit; 200k returns `max_tokens_exceeded`) | The whole KB never goes in one request. The file is chosen first, then judged against that file. |
| Literal reading; weak at arithmetic and comparing numbers or dates | Limits are written in words. Date logic lives in code, not in the model. |
| Distracted by long, irrelevant text | The second call sees one file plus the principles. Files are capped at about 2,300 words. |
| First-option bias in choice questions | "None of these" is listed first, so the bias leans towards no alert. |
| Holistic judgements that need indirect evidence work poorly; literal matching works well | Theme 6a was redesigned into three match questions (section 10.4). |
