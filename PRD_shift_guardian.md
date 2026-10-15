# PRD: one app for ticket hygiene and shift monitoring

**Status:** spec agreed for release 1, 2026-10-15. Release 1 (R1–R10, E2) built, tested and deployed 2026-10-15. Release 2 (P1) built and deployed 2026-10-15.
**Owner:** Prateek M. **Apps:** this app (`alert-dedupe-mongo`) absorbs `shift-guardian-2`.
**Decisions taken:** section 9. **Background comparison of the two apps:** appendix A.

---

## 1. Problem statement

Associates watch engineer behaviour in two separate internal tools: this app (6 ticket-hygiene themes, Slack alerts) and shift-guardian (off-shift status, held tickets, reports). The two overlap on shift status and off-shift tickets and flag the same moment at different times. They disagree on whether to act in Trinity. Each covers ground the other doesn't: shift-guardian has the L2 Expo team and held-ticket checks; this app has themes 1–3 and 6. Associates have two dashboards to check, can get two signals for one event, and still have no single view of an engineer's behaviour.

## 2. Goals

1. **One place:** associates can see everything shift-guardian's read-only features showed, in this app: monitoring for L2 Full Stack, and roster and shift views for L2 Expo. All release 1 requirements (section 6) shipped.
2. **Accurate new alerts:** at least **80%** of theme 7 and theme 8 alerts are marked *correct* by associates in the dry-run trial (stretch: 90%).
3. **Engineers go offline on time:** median minutes Online after a shift ends falls by **50%** within 4 weeks of Slack go-live, against the baseline measured in the trial.
4. **Associates actually use it:** at least **5 of 6** associates open the dashboard every week during the trial.
5. **Expo visible:** all 12 Expo engineers appear in the roster and shift views with a current roster (not monitored).

## 3. Non-goals

| Not doing | Why |
|---|---|
| **Writing to Trinity** (un-assigning tickets, approvals that act) | Decided: the app stays read-only. No write key, no security sign-off needed. Associates act in Trinity from the links we give them |
| **"Mark Offline" for an engineer** | Not possible: Trinity has no tool to change someone's status |
| **Email to engineers** | Slack DM already does this; shift-guardian's email was never built |
| **Leave and comp-off tracking** | A separate initiative; shift-guardian only has the layout |
| **Replacing the roster sheet** | The roster sheet stays the source of truth for shifts; we only read it |
| **Deciding when shift-guardian is retired** | Its owner decides (section 9) |

## 4. Users

- **Associate:** leads a team of engineers; reviews alerts, follows up, reassigns tickets in Trinity. The primary user.
- **Senior:** oversees several teams; reads reports and the scorecard.
- **Engineer:** the person monitored; receives Slack DMs, and never sees the dashboard.

## 5. User stories (by priority)

**Associate**
1. I want to see, the minute a shift ends, which of my engineers are still Online and for how long, so I can nudge them before it becomes a habit.
2. I want a Slack alert, with direct links to their open tickets, if someone is still Online 45 minutes after their shift, so I can reassign the tickets in Trinity myself.
3. I want to know when an engineer held a ticket for 30+ minutes and then dropped it without escalating, and whether they left a note, so tickets aren't silently bounced.
4. I want to know when a ticket has sat with an engineer for 60+ minutes with no reply to the customer, so customers aren't left waiting.
5. I want a live list of off-shift engineers who still hold open tickets, so I can rebalance work at shift change.
6. I want to switch between L2 Full Stack and L2 Expo, so Nikhita and the Expo associates get the same tools.
7. I want each engineer's counts and a simple rating over a date range, built only from alerts we didn't mark as false alarms, so coaching conversations rest on accurate data.
8. I want a daily report of who didn't go offline, who stayed online late, and who dropped tickets without notes, so I can run a quick morning check.
9. I want a "Run check now" button, so I can refresh before a shift-change huddle.

**Senior**
10. I want the scorecard across all teams, so I can see where coaching is needed most.

**Edge cases**
11. If the app was down during a shift change, missed shift ends are shown as *not observed*, never judged from today's status.
12. Engineers without a roster entry, and associates, are never flagged.
13. If an engineer goes Offline before 45 minutes, the dashboard records *went offline late (N min)* and no Slack alert is sent.

## 6. Requirements

### P0: release 1 (all read-only)

**R1 · Shift-end tracking (A1, A2)**
At each shift end, record the engineer's status. Online engineers appear in a live **"Still Online after shift"** dashboard list with a running timer. **No Slack at this point.** The record is closed with one of: *offline on time*, *went offline late (N min)*, *online until next shift*, or *not observed* (the app was down). Theme 4's Slack alert and DM at 45 minutes, and its shift-start check, are unchanged.
- [ ] Given a shift ending at 18:00 and the engineer Online, at 18:01 they appear in the list with a timer, and no Slack is sent.
- [ ] Still Online at 18:45: the theme 4 alert and DM fire, as today.
- [ ] Offline at 18:20: the record reads *went offline late, 20 min*, they leave the list, and no Slack is sent.
- [ ] Back-to-back shifts, engineers without a roster entry, and associates are never listed.
- [ ] After downtime, missed shift ends are recorded as *not observed* and never judged by the current status (the 2026-10-14 rule).

**R2 · Theme 4 alert carries ticket links (decision 1)**
The 45-minute "still Online after shift" alert lists the engineer's open tickets as Trinity links, with "reassign in Trinity". The app makes no change in Trinity.
- [ ] The alert lists up to 10 open tickets with links, plus "and N more" beyond that.
- [ ] No Trinity write tool is ever called (enforced by the read-only key, plus a test).

**R3 · Theme 7: "held 30+ min, then self-un-assigned without escalating" (A3)**
Fires when a monitored engineer was assigned a ticket and later un-assigned **themselves**, more than **30 minutes** later, and the ticket stayed L2 with no `l3_needs_review` tag from assignment until 5 minutes after the un-assign. The alert states the hold time and whether the engineer left their own internal note in that window.
- [ ] Un-assigned by someone else: no alert.
- [ ] Moved to L1 or L3, or tagged `l3_needs_review`, in the window: no alert.
- [ ] Held 30 minutes or less: no alert.
- [ ] One alert per (ticket, engineer, un-assign); the duplicate protection applies.

**R4 · Theme 8: "still assigned 60+ min with no reply to the customer" (A4)**
Fires when an OPEN ticket assigned to a monitored engineer **who is on shift** has had no public reply from a person for **60 minutes** since its latest assignment to them (decision 9; off-shift cases belong to theme 5).
- [ ] Internal notes, AI drafts and System messages don't count as a reply.
- [ ] A reassignment restarts the timer.
- [ ] PENDING or CLOSED tickets, and tickets escalated to L1/L3 or tagged `l3_needs_review`, are skipped.
- [ ] One alert per (ticket, assignment).

**R5 · Themes 7 and 8 use the existing pipeline**
Alert record, dashboard review (correct / false alarm), and a Slack alert tagging the associate, held back by `DRY_RUN` like every theme. They appear in the Live river, the filters and the theme counts.

**R6 · Off-shift engineers with open tickets (A5)**
A live dashboard list: each off-shift engineer, their status, shift end, and open tickets as links. Scoped by team and associate. No alert (theme 5's 3-hour alert is unchanged).

**R7 · L2 Expo team: roster and views only (D1)**
Load the Expo roster (12 engineers, associate Nikhita; `data/Roster_L1_L2_2026_Schedule - L2 Expo Team (Mid Oct - Dec).csv`, 16 Oct–15 Dec) and show the team in the dashboard's roster and shift views, with a team switcher. **Expo engineers are excluded from the notifier:** no themes, checks, alerts, shift tracking or scorecard (decision 8). Settles open decision D11 (Nikhita's team).
- [ ] The switcher changes the roster and shift views; a person sees their own team first.
- [ ] No Expo engineer ever appears in an alert, a check, the activity trace or the scorecard.

**R8 · Reports: counts and daily report (C1, C3)**
For any date range up to 90 days:
- per-engineer counts by theme;
- self-un-assignments with and without a note;
- "heavy days" (3+ in a day) and repeated tickets.

Plus a **daily report** with four lists: didn't go offline, stayed online late, un-assigned without a note, repeated patterns.

**R9 · Scorecard (C2)**
Score = offline-after-shift violations ×3 + un-assignments without a note ×2 + other self-un-assignments, +5 for a repeated pattern. Rated **Needs attention** (3+ violations, 3+ without notes, or a pattern), **Watch** (any), or **Good**.
- [ ] Only alerts **not** marked *false alarm* count.
- [ ] Visible only to people on the dashboard access list (associates and seniors).

**R10 · Trinity data cache and "Run check now" (E1, E2)**
Read-only background sync: everyone's presence every 60 seconds, and open tickets for monitored engineers every 5 minutes, stored in our database for R1, R4 and R6. A "Run check now" button refreshes it on demand.
- [ ] Only the copy holding the notifier lease runs the sync, so there's one sync for any number of copies.

### P1: fast follows (release 2)
- **Export:** alerts, reviews and reports to CSV (the read-only part of C4).
- **"Mark actioned" with a note** on held or off-shift tickets, recorded in our app only (B3).
- **Live shift views:** a week grid of who's on and off shift, and per-associate cards (D3).

### P2: later, but design for it
- **Roster upload** in the dashboard (D2).
- **Access list and roles** managed in the dashboard (D5).
- **Leave calendar** (D4).
- **Approvals and un-assigning in Trinity** (B1, B2): only if decision 1 is ever revisited. Keep alert records able to carry an "action taken" field so this can be added without a migration.

## 7. Success metrics

| Metric | Type | Target | How measured | When |
|---|---|---|---|---|
| Theme 7 and 8 alerts marked *correct* | Leading | ≥80% (stretch 90%) | Dashboard reviews | End of the 2-week trial |
| Associates opening the dashboard weekly | Leading | ≥5 of 6 | Sign-in sessions | Weekly during the trial |
| Expo engineers in roster and shift views | Leading | 12 of 12 | Roster views | Release 1 |
| Median minutes Online after shift end | Lagging | −50% vs trial baseline | R1 shift records | 4 weeks after Slack go-live |
| Engineers rated *Needs attention* | Lagging | Falling month on month | R9 scorecard | Monthly |

## 8. Open questions

| # | Question | Who | Blocking? |
|---|---|---|---|
| Q1 | ~~Theme 8 vs theme 5~~ **Decided:** theme 8 applies only to engineers on shift (decision 9) | Product (Prateek) | Resolved |
| Q2 | Are **30 min** (theme 7) and **60 min** (theme 8) right for our teams? These are shift-guardian's values | Associates | No (configurable) |
| Q3 | ~~Expo roster~~ **Received 2026-10-15** (16 Oct–15 Dec). Who refreshes it after 15 Dec is still open | Roster owner / Nikhita | No |
| Q4 | Expo associate: Nikhita (from shift-guardian's mapping); confirm whether there are others | Nikhita | No |

## 9. Decisions (2026-10-15)

1. **Read-only:** the app never writes to Trinity. The 45-minute shift-end alert gives associates ticket links to act on themselves (R2).
2. **Shift-end timing, both:** at 0 minutes, a dashboard list and timer only (R1); at 45 minutes, the Slack alert and DM as today.
3. **Add the L2 Expo team** (R7).
4. **Release 1 = the read-only core:** R1–R10. Approvals, roster upload, leave calendar and user management come later.
5. **Themes 7 and 8 behave like the other themes:** alerts, reviews and Slack, under `DRY_RUN` (R5).
6. **Scorecard in release 1,** visible to associates and seniors, counting only alerts not marked false alarm (R9).
7. **shift-guardian's owner decides when it's retired.**
8. **Expo is roster and views only:** no themes, checks, alerts or scorecard for Expo engineers (R7).
9. **Theme 8 covers engineers on shift only;** off-shift cases stay with theme 5 (R4).

## 10. Timeline and phasing

- **Release 1:** R1–R10, built on the existing pipeline, dashboard, lease and dry-run. Rough size: about 8–10 working days. No hard deadline.
- **Trial:** dry-run review in the dashboard, as today, until the Slack bot is approved (D23).
- **Release 2:** the P1 items.

**Dependencies:**
- the Expo roster and associate list (Q3, Q4);
- the Slack bot approval, for alerts to reach Slack;
- a new L2 roster before 15 Dec.

**Ordering inside release 1:**
1. R10, the cache, which the rest needs;
2. R1, R2, R6, the shift views;
3. R3, R4, R5, the new themes;
4. R7, Expo;
5. R8, R9, the reports.

---

## Appendix A: how the two apps compare (2026-10-15)

| | This app (ticket hygiene) | shift-guardian |
|---|---|---|
| Emergent app | `alert-dedupe-mongo`, job `7424298f-737e-49ab-86b4-c017c973d255` | `shift-guardian-2`, job `f6ae616a-89ae-497a-84cc-6592b85503b5` |
| Purpose | Alert on bad ticket practice; coach engineers | Manage shifts, online status and ticket assignment; act on off-shift engineers |
| Trinity | Strictly read-only | Reads, and un-assigns tickets |
| Notifies | Slack channel (associate tagged) and Slack DM | In-app alerts; email to the engineer (a stub) |
| Judgment | Rules plus AI (Jev) for replies and escalation notes | Rules only |

**Theme overlap:** themes 4 and 5 overlap partially; 6b is loosely adjacent (un-assignments without a note); themes 1, 2, 3 and 6a have no counterpart.

**Theme 4:**
- **Timing:** ours checks at +45 min (start and end); theirs checks at shift end only, with no grace.
- **Action:** ours sends a Slack alert and DM; theirs creates an approval that leads to un-assigning tickets and an email.
- **Follow-through:** theirs also tracks how long people stay Online and ranks them.
- **After downtime:** theirs judges missed shift ends by the current status (the flaw we fixed on 2026-10-14).

**Theme 5:**
- **Trigger:** ours alerts after the customer has waited 3+ hours on an OPEN ticket held off shift. Theirs lists every off-shift engineer's open tickets at once, and separately any ticket with no reply 60+ min after assignment.
- **Action:** ours sends a Slack alert; theirs offers a manual Un-assign button.

**Feature inventory** (IDs used in this spec):
- **A1–A5:** rules;
- **B1–B4:** acting in Trinity;
- **C1–C4:** reports;
- **D1–D5:** people and rosters;
- **E1–E3:** plumbing.

Source: shift-guardian's `memory/PRD.md` and code (`server.py`, `shifts.py`, `reports.py`, `trinity.py`, `hold_alerts.py`, `held_now.py`), read on 2026-10-15.
