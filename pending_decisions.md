# Pending decisions

Open questions about the notifier and its dashboard, parked for later. Each entry records:
- what is being decided;
- what is known so far;
- the options;
- the current behaviour until someone decides.

When a decision is made, move it to "Decided" with the date and the choice.

## Index

| ID | Topic | Status | Who decides |
|---|---|---|---|
| D1 | Theme 1: uncertain replies get no alert | **Decided 2026-10-12**: resolved by switching to Jev (see Decided) | n/a |
| D2 | Several alerts for the same ticket on the same day | Open | User / associates |
| D3 | Theme 2: the user's alternative approach | Open, waiting on the user | User |
| D4 | Theme 3: the "no own reply" guard | Open | User |
| D5 | Theme 6a knowledge base | **Decided 2026-10-09**: KB built (see Decided) | n/a |
| D6 | Keeping the shift roster current | Open | User / roster owner |
| D7 | Theme 5: exact definition | Open (theme is on) | User |
| D8 | People on Doom-Loop Calls and Evals duty | Open | User |
| D9 | Theme 1 model: option A or B | **Decided 2026-10-12**: option B, Jev (see Decided) | n/a |
| D10 | Dashboard: Google sign-in origin and https address | Open (client created) | User / admin |
| D11 | Dashboard: Nikhita's team | Open, waiting on the user | User |
| D12 | Where the data lives once deployed on Emergent | Open | User / platform |
| D13 | Theme 6a: go live, and how | Open (6a off) | User |
| D14 | KB contradictions between Notion and practice | Open | Support lead |
| D15 | Theme 6b: what to notify | Open (6b on) | User |
| D16 | Secrets found in ticket notes and replies | Open, needs action | Security / support lead |
| D17 | Rotate the API keys shared in chat | Open, needs action | User |
| D18 | Data-handling sign-off for sending ticket text to Jev and Claude | Open; **blocks go-live** | User / security owner |
| D19 | Alert when the notifier itself stops | **Decided 2026-10-12**: watchdog DMs the owner only (see Decided) | n/a |
| D20 | Go-live plan: dry-run review period and telling engineers the themes | Open | User / associates |
| D21 | Owner and refresh cadence for the escalation KB | Open | User / support lead |

---

## Open

### D2. Several alerts for the same ticket on the same day
*Raised 2026-10-07, from the 50-ticket simulation.*

**Situation.** Each Pending change is judged separately, so one ticket can produce several alerts in a day. Example: #273283, 3 Pending alerts in 40 minutes. Every alert is accurate, but associates may find it noisy.

**Options.**
1. One alert per action (current).
2. Group alerts per ticket, for example one message per ticket every few hours listing each occurrence.
3. A daily digest per engineer.

**Current behaviour:** one alert per action.

### D3. Theme 2 (reassignment): a different approach the user will propose
*Raised 2026-10-07.*

The user confirmed: flag any engineer taking a colleague's ticket, whatever the hold time; only associates may reassign. The user has another idea for this theme and will share it later.

**Current behaviour:** every self-reassignment from a colleague is flagged; associates are exempt.

### D4. Theme 3 (Overwatch pickup): the "no own reply" guard
*Raised 2026-10-07.*

Theme 3 also skips engineers who sent a reply of their own after picking the ticket up, including replies sent from Overwatch's draft. This guard was added to avoid unfair flags and was never explicitly confirmed. The alternative is to flag every pickup during an Overwatch run that ends in a System close.

**Current behaviour:** guard on.

### D6. Keeping the shift roster current
*Raised 2026-10-07; the roster was provided the same day.*

Themes 4 and 5 read the real roster, `data/Roster_L1_L2_2026_Schedule - L2 FS Team (Mid Oct - Dec).csv`:
- It covers **9 Oct to 15 Dec 2026**.
- The notifier warns a week before it runs out, and themes 4–5 go idle once it has.
- The file is git-ignored, because it holds staff names, emails and shifts.

**Still to decide:**
- **How the next roster arrives:** export the sheet to the same path each time (current approach), or have the notifier read the Google Sheet directly.
- **Timezone:** shift times are assumed to be IST (`Asia/Kolkata`). Confirm.
- **Swap cells:** "swap(12th)" and "swap(17th)" (15 and 22 Oct) don't say which shift was worked, so no checks run for those person-days. Should the roster use a shift code instead?

### D7. Theme 5 (tickets held off shift): exact definition
*Raised 2026-10-07.*

The user proposed flagging tickets held for more than 3 hours by someone who is off shift. The built version flags a ticket when **all** of these hold:
- **It is OPEN:** the ball is in our court. PENDING and CLOSED tickets held overnight are fine, since we are waiting on the customer.
- **Its assignee is a monitored engineer who is currently off shift.**
- **A customer has waited at least 3 hours since the engineer's shift ended,** counted from the later of the customer's unanswered message and the shift end.

It alerts once per ticket per off-shift period, in the channel, tagging the associate so they can reassign.

**To confirm:** this definition, the 3-hour threshold, and whether the engineer should also get a DM.

**Current behaviour:** on, with this definition (`config.py`), since 9 Oct when the roster starts.

### D8. People on Doom-Loop Calls and Evals duty
*Raised 2026-10-07, from the roster.*

The roster has separate blocks for **Doom-Loop Calls** (4 people) and **Evals** (2 people). They are in `teams.yaml`, so all themes apply to them, including themes 4 and 5. If they don't work the ticket desk on those shifts, themes 4–5 (and possibly 1–3) may not make sense for them.

**Options.**
1. Treat them like everyone else (current).
2. Exclude them from themes 4–5.
3. Exclude them from all ticket themes while on that duty.

**Current behaviour:** treated like everyone else.

### D10. Dashboard: Google sign-in origin and the https address
*Raised 2026-10-09.*

**Done:**
- The user created the OAuth client (project "ticket-hygiene").
- `GOOGLE_CLIENT_ID` is set in `.env`.
- `http://localhost:8090` is entered under Authorized JavaScript origins.

**Open:**
- **Checked 2026-10-12:** Google now accepts `http://localhost:8090` (its sign-in page opens for it). Two causes of the failing button were found:
  1. *Fixed in code:* the dashboard sent `Referrer-Policy: same-origin`, so Google couldn't see which site the button was on and refused it (HTTP 400). It now sends `strict-origin-when-cross-origin`, the origin only.
  2. *Needs the user:* Google's button also needs **`http://localhost`** (without a port) under Authorized JavaScript origins for local use. It is not there yet, so the button still gets HTTP 403. Add it, save, and wait a few minutes.
  Once deployed, add the dashboard's https address too; no port entry is needed for https.
- *(Earlier note)* **The origin hadn't taken effect.** At the last check (about 30 minutes of retries), Google still answered "The given origin is not allowed for the given client ID". Confirm the client was **saved**: the Save button is at the bottom of the page. Google says changes can take minutes to hours.
- **Laptop limit.** Google only allows sign-in from `localhost` or **https** addresses, so until the dashboard is deployed, only someone on this laptop can use it.
- **The https address on Emergent,** once deployed. It must be added to the same client's origins.
- **Whether the notifier moves to Emergent together with the dashboard.**

**Current behaviour:** Google sign-in is configured. The local test sign-in is off (`DASHBOARD_DEV_LOGIN=false`).

### D11. Dashboard: Nikhita's team
*Raised 2026-10-09. The rest of the access list is decided (see Decided).*

Nikhita is on the access list as an associate but leads no team in `data/table.tsv`, so she opens on "All teams". The user says she is on Expo and will share her team later.

**Then:**
1. Add her team to the sheet, with her as associate.
2. Re-run `scripts/import_teams.py` with `--associate "<her name>=nikhita@emergent.sh"`.

### D12. Where the data lives once deployed on Emergent
*Raised 2026-10-09.*

Everything is in one SQLite file today (`state.db`): the notifier's state, the activity trace, alerts, feedback and sessions. That works on one machine with a persistent disk.

**Options on Emergent.**
1. Keep SQLite on a persistent volume, with the notifier and dashboard in the same app.
2. Move to the platform's database (e.g. MongoDB). Every dashboard query is in `dashboard/queries.py` and every notifier write is in `notifier/store.py`, so only those two files change.

**Prepared 2026-10-12:** the Docker image (see README, "Deploying with Docker") keeps `state.db` in a `/data` volume, which is option 1. Option 2 is only needed if the platform has no persistent volumes.

**Also to decide:** how long to keep the activity trace. It grows by roughly 2–5k rows a day; nothing is deleted today.

### D13. Theme 6a (did the escalation need L3?): go live, and how
*Raised 2026-10-09, after the KB evaluation. Full method: `l3_kb_research.md`.*

**The KB is built** (see Decided).

**Held-out test.** 146 escalations from July to October, never used to build the KB, labelled independently:

| Judge design | Alerts that were right | Genuine escalations wrongly flagged | Wrong escalations caught |
|---|---|---|---|
| One holistic question (rejected) | 26 of 83 (31%) | 57 of 75 | 93% |
| **Three match questions (built)** | **3 of 3** | **0 of 90** | **10% (3 of 29)** |

**What this means.** The check is safe: no false alarms on 90 genuine escalations. But it catches only the clearest wrong escalations.

Caveats:
- 3 alerts is a small sample.
- The labels are by careful AI labellers, not a human review.
- Training-set scores are higher only because the KB describes those cases.

**Options.**
1. Turn theme 6a on as it is: rare alerts, so far all correct.
2. Add `ANTHROPIC_API_KEY`, so Claude judges the cases where Jev is unsure (about 12%), then re-run `python scripts/eval_kb.py`.
3. Run it visible only in the dashboard, with no Slack, until associates' verdicts confirm it.

In every option, feed associates' dashboard verdicts back into KB examples.

**Current behaviour:** theme 6a is off in `config.py`.

### D14. KB contradictions between Notion and real practice
*Raised 2026-10-09.*

The KB writers resolved about 120 contradictions conservatively: where uncertain, they kept the case as L3, which means no alert. Each one is recorded with case numbers and the choice made, in `data/kb_research/`:

| File | Contradictions |
|---|---|
| `conflicts_accounts-security-legal.md` | 13 |
| `conflicts_agent-preview-fork-github.md` | 16 |
| `conflicts_billing-credits-subscriptions.md` | 17 |
| `conflicts_databases-and-data.md` | 12 |
| `conflicts_deployment-and-publishing.md` | 11 |
| `conflicts_domains-dns-edge-seo.md` | 16 |
| `conflicts_integrations-keys-connectors.md` | 10 |
| `conflicts_mobile-builds.md` | 12 |
| `conflicts_principles.md` | 13 |

**The ones that change verdicts most:**
- **L3-only tools that L2-level accounts use routinely,** per Notion: edge-config PATCH, `clear-asc-credentials`, credential rotation, system packages.
- **Export size cap:** 1 GiB or 3 GiB.
- **Credit and refund limits,** which conflict across Notion pages.
- **Rule switch dates:** support clearing managed email itself, and the DNS API gaining TXT/MX.
- **Whether a self-applied `real_l3` should itself be flagged:** it was genuine 56% of the time, against 78% when a reviewer applied it. Seen, for example, on #272793, #272959 and #273017. This question was carried over from D5.
- **L1 skipping L2:** 28 such escalations in the accounts sample, 12 of them L2 work.

A support lead should go through these. Each decision is a one-line KB edit.

### D15. Theme 6b (escalation note): what to notify
*Raised 2026-10-09.*

**Built and on.** Held-out test on 146 escalations:
- flags right: 36 of 38 (95%);
- missing notes agree 19 of 20;
- bad notes caught: 69%;
- partial or complete notes wrongly flagged: 2 of 75.

Weak spot: "cause stated with no evidence" notes, only 1 of 12 caught.

**Open.**
1. **A colleague's note in the window** (45 of 322 missing cases). Today it's still flagged MISSING, with the colleague's name shown.
2. **PARTIAL notes** (missing the user ID or an exact ask): notify, or only list? Today they are only listed in the dashboard.
3. **L1 escalators:** should the check apply to them? Today it applies to everyone in `config/teams.yaml`.
4. **Without `ANTHROPIC_API_KEY`,** notes where Jev is unsure (about 13%) are not judged. The Claude fallback is built in and turns on once the key is added.

### D16. Secrets found in ticket notes and replies
*Raised 2026-10-09, found during the KB research.*

Customer secrets were pasted in plain text:
- #47773: live database connection strings with passwords, in a reply sent to the customer;
- #51408 and #35025: customer credentials in escalation notes.

**To decide:**
- Who handles these as security incidents, and whether the affected credentials are rotated.
- Whether the notifier should flag secrets in notes and replies, as a possible new theme.

### D17. Rotate the API keys shared in chat
*Raised 2026-10-08.*

The Trinity MCP key and the Jev (LiteLLM) key were pasted into the Claude chat while setting things up. Both now live only in `.env`, which is git-ignored, but they should be rotated, and `.env` updated, before go-live.

### D18. Data-handling sign-off for sending ticket text to Jev and Claude
*Raised 2026-10-09, in the gap review.*

**What leaves the machine today, or would once switched on:**

| Theme | Sends | To | Status |
|---|---|---|---|
| Theme 6b | The escalating engineer's internal notes, which often contain customer emails, app names and error text | Jev (Emergent's LiteLLM); Claude if a key is added | **on** |
| Theme 6a | The escalated ticket's conversation (last 8 messages) and the escalation note | Jev; Claude as fallback | off |
| Theme 1 (option B) | Engineers' replies to customers | Jev | **on since 2026-10-12** |
| Theme 1 Claude fallback | Uncertain replies | Claude | off |

Only theme 1 had a sign-off question until now (D9).

**To decide:** whether sending this text to Jev (and Claude) is acceptable, under what terms (retention, region), and who signs off. Theme 6b is on, so this applies now, although nothing is posted while `DRY_RUN=true`.

**Option if sign-off is refused:** themes 6a and 6b can run on the local `decider:4b` model in Ollaya instead. This would need re-measuring with `scripts/eval_kb.py`, and is slower.

### D19. Alert when the notifier itself stops
*Raised 2026-10-09, in the gap review.*

If the notifier stops, the dashboard shows "Not running", but nobody is notified, so monitoring can go silent unnoticed.

**Option:** a small watchdog (or a check in the dashboard server) that DMs the owner in Slack when the heartbeat is older than 10 minutes, and again when it recovers.

**Decided 2026-10-12:** built as `python -m notifier watchdog`, DM to the user only (see Decided).

### D20. Go-live plan: dry-run review period, and telling engineers the themes
*Raised 2026-10-09, in the gap review.*

**Situation.** No theme has yet been measured against human judgement on real tickets:
- theme 1 was tested on hand-written cases and a replay spot check;
- themes 2–5 rest on their logic and a partly reviewed backtest;
- theme 6 were tested against AI-made labels;
- themes 4–5 started with the roster on 9 Oct.

Backtests suggest about 100 alerts a day from themes 1–3, plus about 8–9 from theme 6b.

**Proposal.**
1. **One to two weeks of dry run,** with the deployed dashboard. Associates mark every alert correct or false alarm.
2. **Measure each theme** from those verdicts. Settle alert volume and grouping (D2), theme 6a (D13) and theme 6b notifications (D15) from that data.
3. **Before alerts go to Slack,** publish to engineers:
   - what each theme flags;
   - the escalation-note template in `kb/escalation/reference/rca-standard.md`;
   - that associates review every alert.
4. **Switch to `DRY_RUN=false`** theme by theme, starting with the most accurate.

**To decide:** the length of the review period, who reviews, and the order in which themes go live.

### D21. Owner and refresh cadence for the escalation KB
*Raised 2026-10-09, in the gap review.*

L2/L3 boundaries changed several times in 2026, for example managed-email suppression, DNS TXT/MX records and export caps. A KB that isn't kept up to date will slowly produce wrong verdicts for themes 6a and 6b.

**Proposal.**
- A named owner (a support lead).
- A monthly refresh:
  1. Run `scripts/escalation_corpus.py --since <last refresh>`.
  2. Add the new cases, and the dashboard verdicts on theme 6a and 6b alerts, as KB examples.
  3. Apply any D14 decisions.
  4. Re-run `scripts/eval_kb.py`, and ship only if the held-out results don't get worse.

The steps are in `kb/escalation/README.md`.

**To decide:** who owns it, and how often it is refreshed.

---

## Decided

| Date | ID | Decision |
|---|---|---|
| 2026-10-07 | | Only the 34 engineers in `data/table.tsv` are monitored, via `config/teams.yaml`. |
| 2026-10-07 | | Theme 1 runs on a local model (Ollaya + `von`) instead of a paid API, so customer text stays on the machine. Option B (Jev) was added on 2026-10-08. |
| 2026-10-07 | | Theme 1 first check stays at 5 minutes after Pending. The 30-minute window applies only when no reply exists yet. |
| 2026-10-07 | | Theme 2 flags every reassignment from a colleague, however long the colleague had held it. Only associates may reassign. |
| 2026-10-07 | | Theme 3 flags only pickups made while Overwatch was running that System then closes, and never when the ticket was already the engineer's before that run. |
| 2026-10-07 | D6 | The shift source for themes 4–5 is the team roster export (`data/Roster_L1_L2_2026_Schedule - L2 FS Team (Mid Oct - Dec).csv`), read cell by cell: each day's shift code (e.g. `6A-3P`, `9P-6A`), with Off, EL and Comp Off as days off. |
| 2026-10-07 | | Themes 4 (status vs shift) and 5 (tickets held off shift) switched on. |
| 2026-10-07 | | Parasmani stays in the team list with no roster entry (probably no longer working). No action: themes 4–5 skip him; themes 1–3 still apply if he acts on tickets. |
| 2026-10-08 | D1 | Non-English replies must not be missed. They are detected by language and judged by the local multilingual model `decider:4b` (Qwen3.5-4B, Apache-2.0, via Ollaya), one call per reply. Result: 64 of 64 correct on hand-written Italian, Spanish, Portuguese, French, German and mixed cases. Courtesy phrases and ask words were added for those five languages. |
| 2026-10-08 | D9 | The theme 1 model is a `config.py` setting, `PENDING_MODEL`: **option A** (`von` + `decider:4b`, local) or **option B** (Jev, hosted). The user chose option A "as of now". The production choice stays open in D9. |
| 2026-10-09 | | Theme 6a judges with **Jev** (`jev-latest`), with **Claude** (`claude-opus-5-5`) as the fallback, as the user chose. The judging method was later redesigned (see the last rows). |
| 2026-10-09 | D10 | Dashboard sign-in is **Google sign-in**, limited to an access list. The dashboard runs on this laptop for now and will be deployed on Emergent later. |
| 2026-10-09 | | **Observability dashboard** (`python -m dashboard`):<br>• every run is stored persistently in the `state.db` activity trace;<br>• real-time UI via server-sent events;<br>• everyone sees all teams, with their own team selected by default;<br>• associates mark alerts correct or false alarm, with a note;<br>• React + Vite UI served by Python;<br>• visual direction "Long Exposure", chosen on the Impeccable decision page: minimal glass with blur, dark/light switch. |
| 2026-10-09 | D11 | **Dashboard access list** (`config/dashboard_users.yaml`), 10 people, all @emergent.sh.<br>• Associates: hridaya, subrahmanya, shreyas.g, sutikshan, nikhita, prateek.m.<br>• Seniors: udayagiri, vinish, soham, vibhor.<br>Associates open on their own team; seniors and anyone without a team open on "All teams". |
| 2026-10-09 | D5 | **Theme 6a KB built**, from three things:<br>• Notion: process, permissions, 216 playbooks, the Escalation Matrix;<br>• 3,230 real escalations, 704 of them judged by case analysts;<br>• 146 held out for testing.<br>Layout in `kb/escalation/`: 8 issue files, plus `_principles.md`, plus `reference/` (permissions table, RCA standard). Accuracy was measured on the held-out set, not on `real_l3` tags: `real_l3` turned out not to be ground truth. Full method in `l3_kb_research.md`. |
| 2026-10-09 | D13 | **Theme 6a judging redesigned.** Jev now:<br>1. picks the KB file by its Title and Covers list;<br>2. answers three match questions against that file plus `_principles.md`: does an L3, an L2-can-resolve, or a not-a-fault bullet describe the ticket?<br>It alerts only when an L2 or not-a-fault bullet matches at 70% or more and an L3 bullet at 30% or less. The first, holistic design was rejected: only 31% of its alerts were right on held-out cases. Whether to switch theme 6a on stays open in D13. |
| 2026-10-09 | D15 | **Theme 6b (escalation note quality) added and on**, at the user's request: "missing RCA should be flagged immediately".<br>• MISSING: no note by the escalator from 6 h before to 15 min after the move.<br>• VAGUE: a note under 80 characters.<br>• Otherwise: six yes/no questions go to Jev (Claude if unsure).<br>Standard: `kb/escalation/reference/rca-standard.md`. |
| 2026-10-12 | D9 | **Theme 1 switched to option B, Jev** (`jev-latest` for every language), at the user's request: "it was anyday better than the local models". On the 100-case test, Jev scored 100/100 against option A's 95/97 with 2 wrong alerts, at about 1 s per reply. Local models also can't run `decider:4b` on the 8 GB Mac. Set in `config.py` `PENDING_MODEL["option"] = "B"`. Ollaya is no longer needed. Theme 1 reply text now goes to Jev, so the data-handling sign-off in D18 covers theme 1 as well. |
| 2026-10-12 | D1 | Uncertain theme-1 replies: resolved by the switch to Jev, which left no reply uncertain on the 100-case test. Any Jev-uncertain reply still gets no alert (`ALERT_UNCERTAIN=false`). |
| 2026-10-12 | | **Naming: "themes", not "rules".** The notifier handles **6 themes**: themes 1–5 are the former rules 1–5, and theme 6 (L3 escalations) has two checks, **6a** `l3_escalation_check` (former rule 6) and **6b** `escalation_note_quality` (former rule 7). Docs, Slack alerts, logs, the dashboard and `config.py` (`THEMES`, formerly `RULES`, still accepted) use the new names; internal code identifiers (`Rule` enum, the `rule` database column) are unchanged. `scripts/eval_kb.py --theme 6a/6b/both` replaces `--rule 6/7`. |
| 2026-10-12 | D13, D15 | **Jev is the main model everywhere; Claude stays theme 6's fallback.** Theme 1 (option B) and theme 6 (6a and 6b) judge with Jev. Claude (`claude-opus-5-5`) decides the cases Jev can't settle, only when `ANTHROPIC_API_KEY` is in `.env`. Error handling:<br>• no key: one warning at start, no error; those cases are logged as not judged, never alerted;<br>• key rejected: one error, then the fallback is off until restart;<br>• a failed Claude call never alerts. |
| 2026-10-12 | D19 | **Down alert:** a watchdog process sends a Slack DM to the user only (`DOWN_ALERT["dm"]` in `config.py`), never the channel, when the notifier has no heartbeat for 10 min or every cycle has failed for 10 min, with a reminder every 60 min and a DM on recovery. It works during `DRY_RUN=true` and when the notifier can't start. |
| 2026-10-12 | D12 | **Container built** (`Dockerfile`, `docker/start.sh`, `docker-compose.yml`): notifier + dashboard + watchdog in one container, `state.db` in a `/data` volume, secrets from the environment. The image holds no customer data or secrets (`.dockerignore`). Tests pass on Python 3.13, the image's version. |
| 2026-10-12 | D12 | **Deploy on the Emergent platform as an internal app**: code pushed to a private GitHub repo, imported into an Emergent job and deployed from there. SQLite goes up as is; the Emergent agent moves storage to the app's MongoDB following `EMERGENT_DEPLOY.md`. Duplicate protection is built in first: an alert is claimed atomically (`alert_claims`) before it is posted, tested with two notifier copies racing on one database. The repo commits the roster, team list and dashboard access list (staff data only); chat exports stay out (they hold keys). Platform must run exactly one copy and never park it. |
| 2026-10-12 | D12 | **Deployed** as internal app `alert-dedupe-mongo` (one pod, MongoDB, `DRY_RUN=true`), reachable on the VPN at `https://alert-dedupe-mongo.internal.aws.emergent.host`. Dashboard works. **Blocked on network:** the app runs on the AWS internal cluster (10.241.x), which cannot reach Trinity (`trinity-base.internal.emergent.host`, 10.99.32.123) or Jev's LiteLLM (172.28.0.7); every poll cycle times out. Needs the platform team: open those routes, or host the app where they are reachable. The public URL `alert-dedupe-mongo.emergent.host` answers "Deployment not found" (deploy screen stuck at "reconcile domain"). |
