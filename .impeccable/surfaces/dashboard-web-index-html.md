---
version: 1
slug: "dashboard-web-index-html"
primary_target: "dashboard/web/index.html"
related_targets: ["dashboard/web/src"]
---

# Ticket Hygiene dashboard

**Scope:** the whole signed-in app and its sign-in gate. Routes:
- `/` Live
- `/alerts`, `/alerts/:id`
- `/review`
- `/team`
- `/tickets/:ref`
- `/system`

**Visitor mode:** Operate.

**Audience and jobs:** associates (team leads). They arrive from a Slack alert to verify one alert, review their team, keep it open as a live monitor during a shift, or audit the system itself.

**Constraints the brief pins:**
- minimal;
- glass with blur;
- dark mode with a visible switch;
- a sign-in gate;
- the own team selected first, with everything visible.

**Memorable moment:** the live river. The notifier's real traffic drifts behind frosted glass as light.

## Direction contract

**THESIS.** You watch the notifier's real traffic through frosted glass: every check is a passing light, and every alert is a red tail-light. This refuses the category default of KPI tiles over decorative gradient blobs. The glass is there because something real moves behind it.

**OWN-WORLD.**
- **Night.** Blue-black ground #0B1020, glass panes rgba(26,34,54,.42) with 26px backdrop blur, hairline edges at 9% white.
- **Day haze.** Ground #EEF1F6, ink #121826.
- **Lights mean states.** Headlight white means clean, teal #3DD6C3 means ok or live, sodium amber #F2A541 means waiting or uncertain, and tail-light red #FF4D5E means alert. Red is reserved for alerts alone.
- **Type.** One family, Red Hat Text, with its mono cut Red Hat Mono used only for ticket numbers, IDs and times. Chosen over Geist, which the detector flags as overused.

**STORY.** The associate sees at once whether the notifier is alive and what it is doing. They work their team's unreviewed alerts, open one to see its full trace (event, grace, reply, model score, Slack message), and mark it correct or a false alarm.

**FIRST VIEWPORT.**
- A 76px glass rail on the left: Live, Alerts, Review, Team, Tickets, System.
- A 64px header: product name, team selector (own team), time window, live state, theme switch.
- A 236px live river across the full width: real checks from the last hour placed by time, with alerts as red streaks.
- Below it, three panes: unreviewed alerts for your team (the primary action is "Review"), the six rules with hourly counts, and notifier health.

**FORM.** Long Exposure: night-shift city light trails seen through frosted glass. Position 3 on the ordered list. Seed key 83e2aab8.

**Raises carried from the declined challengers:**
- Red only for alerts.
- One family, with mono only for data.
- Guide-span head on the feed.
- The next unreviewed alert one keypress away.
- Verdicts stamp on and stay.

**FINISH.** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Google OAuth client id.
- The final allow-list.
- The storage backend on Emergent.
