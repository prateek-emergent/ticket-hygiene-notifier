# PRD: bringing shift-guardian into the ticket-hygiene app

**Status:** draft for discussion (2026-10-15). Nothing here is built yet.
**Goal:** one app. Add what shift-guardian does that this app doesn't, so shift-guardian can be retired.

| | This app (ticket hygiene) | shift-guardian |
|---|---|---|
| Emergent app | `alert-dedupe-mongo`, job `7424298f-737e-49ab-86b4-c017c973d255` | `shift-guardian-2`, job `f6ae616a-89ae-497a-84cc-6592b85503b5` |
| Purpose | Alert on 6 themes of bad ticket practice; coach engineers | Manage shifts, online status and ticket assignment; act on off-shift engineers |
| Trinity | Strictly read-only | Reads, and **un-assigns tickets** |
| Notifies | Slack channel (associate tagged) and Slack DM | In-app alerts; email to the engineer (still a stub) |
| Judgment | Rules plus AI (Jev) for replies and escalation notes | Rules only |

Source: shift-guardian's `memory/PRD.md` and code (`server.py`, `shifts.py`, `reports.py`, `trinity.py`, `hold_alerts.py`, `held_now.py`), read on 2026-10-15.

---

## 1. Where the two apps overlap today

| Our theme | Overlap | In shift-guardian |
|---|---|---|
| 1 · Pending, no question | None | — |
| 2 · Taken from a colleague | None (adjacent) | Flags the opposite: holding a ticket 30+ min, then self-un-assigning without escalating |
| 3 · Grabbed during Overwatch | None | — |
| **4 · Status vs shift** | **Partial: the shift-end half** | "Off shift but still Online" |
| **5 · Held while off shift** | **Partial** | "Off shift with assigned tickets"; "Still assigned 60+ min, no reply" |
| 6a · L3 escalation needed? | None | Escalation is only a reason *not* to flag |
| 6b · Escalation note (RCA) | Loosely adjacent | Counts un-assignments without an internal note |

### Theme 4 compared
| | Ours | shift-guardian |
|---|---|---|
| When checked | 45 min after a shift ends | The moment a shift ends (within 60 s), no grace |
| Shift start ("still Offline") | Checked | Not checked |
| Action | Slack alert to the associate, plus a DM to the engineer | Pending approval → manager approves → open tickets un-assigned in Trinity, email to the engineer |
| Follow-through | One alert per shift boundary | Tracks how long they stayed Online; scores and ranks (3+ violations = "Needs attention") |
| After downtime | Missed boundaries are skipped (fixed 2026-10-14) | Judges the latest missed shift end by the status *now* (the flaw we fixed; one per person) |
| Teams | L2 Full Stack | L2 Full Stack and L2 Expo (12 engineers under Nikhita) |

### Theme 5 compared
| | Ours | shift-guardian |
|---|---|---|
| Trigger | OPEN ticket, assignee off shift, customer waiting 3+ h (from the later of their message and the shift end) | Any open assigned ticket of an off-shift agent, listed at once; separately, any assignee with no reply 60+ min after assignment |
| Action | Slack alert so the associate can reassign | A list plus a manual Un-assign button (writes to Trinity) |

---

## 2. Feature list

Size: **S** = hours, **M** = about a day, **L** = several days. ⚠️ = needs a decision first (section 3).

### A. New monitoring rules
| # | Feature | From shift-guardian | Size |
|---|---|---|---|
| A1 | **"Online right at shift end"**: flag the moment a shift ends while the person is still Online, as an earlier stage of theme 4 (today we wait 45 min) ⚠️ | "Off shift but still Online" | S |
| A2 | **How long they stayed Online after the shift**: per shift, record status at the end and when they went offline; outcome *offline on time / went offline late / online until next shift* | Shift records | M |
| A3 | **Theme 7: "Held 30+ min, then self-un-assigned without escalating"**, noting whether a handover note was left. Skips tickets moved to L1/L3 or tagged `l3_needs_review` from assignment until 5 min after the un-assign | Hold alerts | M |
| A4 | **Theme 8: "Still assigned 60+ min with no reply to the customer"**, any assignee. The timer restarts on every reassignment; internal notes, AI drafts and System messages don't count as a reply | Still assigned | M |
| A5 | **Off-shift agents with any open tickets**: an instant dashboard list, next to the theme 5 alert (which waits for 3+ h of customer waiting) | Off shift with assigned tickets | S |

### B. Taking action in Trinity ⚠️
This app is strictly read-only on Trinity today; shift-guardian un-assigns tickets.

| # | Feature | Size |
|---|---|---|
| B1 | **Approval workflow**: an "Online after shift" case creates a pending approval; an associate or manager approves or dismisses it | M |
| B2 | **Un-assign tickets in Trinity**: all of a person's open tickets after approval, or one ticket via "Take action", always with a confirmation step. Needs a Trinity key that can write, plus security sign-off | M |
| B3 | **"Mark actioned" with a note** on held tickets (no change in Trinity) | S |
| B4 | **Tell the engineer** by Slack DM (shift-guardian's email is a stub; we already have DMs) | S |
| — | "Mark Offline" for someone: **not possible**. Trinity has no tool to change a person's status; shift-guardian has it disabled too | — |

### C. Reports and accountability
| # | Feature | Size |
|---|---|---|
| C1 | **Un-assignment tracking**: per person and per day, with or without a note, repeated tickets, "heavy days" (3+ in a day) | M |
| C2 | **Scorecard and ranking**: score = offline violations ×3 + missing notes ×2 + un-assignments; rated Good / Watch / Needs attention; 14-day summary or a custom range (up to 90 days) | M |
| C3 | **Daily report**: four lists (didn't go offline, stayed online late, un-assigned without a note, repeated patterns) | S |
| C4 | **Audit log** of every action (approvals, un-assignments, dismissals) with CSV export | S |

### D. People, teams and rosters
| # | Feature | Size |
|---|---|---|
| D1 | **Second team: L2 Expo** (12 engineers under Nikhita) with a team switcher. Also settles open decision D11 (Nikhita has no team today) | M |
| D2 | **Roster upload in the dashboard** (Excel/CSV, with a template and checks), replacing "put the file in `data/` and redeploy" | M |
| D3 | **Live shift views**: a week grid of who's on or off shift; per-associate cards (on shift, off shift, still Online, no roster today) | M |
| D4 | **Leave management calendar**: month view of shifts and leave (layout only in shift-guardian; leave and comp-off tracking later) | M |
| D5 | **Access list managed in the dashboard** (Settings → Users) instead of a file, with **manager vs associate roles** (only managers approve) | M |

### E. Plumbing these need
| # | Feature | Size |
|---|---|---|
| E1 | **A copy of Trinity data in our database**: everyone's online status (every minute) and open tickets (every 5 min), so the new views load fast | M |
| E2 | **"Run check now"** button on the dashboard | S |
| E3 | **Optional: import shift-guardian's history** (shift records, approvals, audit log), so reports don't start from zero | S–M |

---

## 3. Decisions needed before building

1. **⚠️ Read-only, or act in Trinity (section B)?** This is the biggest change to our design: it needs a write-capable Trinity key and security sign-off. Options:
   - keep everything read-only: approvals only produce a Slack message to the associate, who acts in Trinity themselves;
   - build B behind its own on/off switch, off by default.
2. **Theme 4 timing:** alert at shift end (shift-guardian), at 45 min (ours), or both (heads-up at 0, alert at 45)?
3. **Teams:** add L2 Expo?
4. **First release scope.** Suggestion:
   - A1–A5 (rules);
   - C1–C4 (reports);
   - D1 (Expo team);
   - E1–E2 (plumbing).

   That's all read-only. B and D2–D5 come next.
5. **Retiring shift-guardian:** once there's parity, agree a cut-over date with its owner, and whether to import its history (E3).

---

## 4. Points to raise with shift-guardian's owner

- **Double flagging:** once both apps are live, the same "Online after shift" moment is flagged twice, at different times (0 vs 45 min) and with different actions. Until one app remains, agree which one owns theme 4.
- **Read-only vs acting:** one app un-assigns tickets, the other deliberately never writes. Align, so associates don't get conflicting signals.
- **The catch-up flaw:** shift-guardian judges a missed shift end by the status at restart. This is the same flaw we fixed on 2026-10-14 (see `notifier/shift_checks.py`, `STATUS_MAX_CATCHUP`).
- **Complementary coverage:** shift-guardian covers the Expo team; we cover themes 1, 2, 3, 6a and 6b, which it doesn't.
