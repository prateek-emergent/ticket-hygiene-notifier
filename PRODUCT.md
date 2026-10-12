# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

- **UI:** React + Vite (TypeScript), built to static files in `dashboard/static/`.
- **Server:** Python aiohttp (`python -m dashboard`), which serves the built UI, a JSON API, and a server-sent-events stream.
- **Data:** the notifier's SQLite `state.db`.
- **Deploy:** runs on one laptop for now; it will later deploy on Emergent's platform.

## Users

Associates (team leads) of Emergent's L2 support engineers: five today, about 34 engineers across their teams. Each associate is responsible for their own team's ticket hygiene and is @-mentioned in Slack when one of their engineers is flagged.

They open the dashboard in four situations. All four are confirmed and equally real:
1. **From a Slack alert:** to see one alert's full story and mark it right or wrong.
2. **Reviewing their team:** a daily or weekly look at who is flagged, for what, trends, and unreviewed alerts.
3. **Watching it live:** kept open during a shift as a monitor of checks, alerts, and notifier health.
4. **Auditing the system:** model accuracy, errors, and what was skipped and why.

## Product Purpose

**Ticket Hygiene** watches Trinity, Emergent's support-ticket platform, and flags practices that game support metrics or take credit for others' work. It alerts in Slack. The 6 themes (theme 6, L3 escalations, has two checks: 6a and 6b):
1. Moving a ticket to PENDING with no open question for the customer.
2. Taking a colleague's ticket.
3. Grabbing a ticket while the Overwatch AI agent works it.
4. Trinity status not matching the shift.
5. Holding tickets while off shift.
6. L3 escalations the knowledge base says L2 could handle.

The dashboard is its observability and traceability surface. It answers why each alert fired and why each non-alert didn't, shows whether the notifier is healthy right now, and collects associates' right/wrong verdicts on alerts.

Success means:
- An associate can trust an alert, or dispute it, within a minute of opening it.
- Their verdicts become the labelled data used to measure and tune the models (pending decisions D1 and D9).

## Positioning

It shows the notifier's own trace for every decision: the event that triggered a check, the grace period, the exact reply text judged, the model and its probability, the fallback taken, the Slack message sent, and the outcome. This is evidence, not a summary, and no general BI tool over Trinity data could show it.

## Operating Context

- Associates arrive from Slack links. Alerts carry the ticket link; Trinity tickets live at `https://trinity-base.internal.emergent.host/tickets/<id>`.
- Sign-in is Google, limited to an allow-list of associate emails (`config/dashboard_users.yaml`).
- Every associate sees every team, with their own team selected by default.
- Times are UTC in the data. Shifts and people are in IST (Asia/Kolkata).
- Theme names, models (`von`, `decider:4b`, Jev, Claude) and outcomes (clean, ok, flagged, skipped, uncertain) are the team's working vocabulary.

## Capabilities and Constraints

- **Read-only on Trinity and the notifier.** The only writes are feedback on alerts (correct or false alarm, plus an optional note, with who and when) and sign-in sessions.
- **Real-time:** new activity streams to the browser about once a second.
- **Full visibility:** every check is visible, not only alerts. That includes clean ones, skipped ones, the reasons for skipping, model calls with latency, and errors.
- **Undecided:**
  - The final allow-list of emails.
  - The Google OAuth client id.
  - The storage backend for the Emergent deployment.

## Brand Commitments

Visual constraints the user made binding:
- minimal;
- glass-like, with blur;
- dark mode, with a visible switch to toggle it;
- a sign-in gate in front of everything.

The product name is "Ticket Hygiene", the same name the Slack bot uses ("Ticket Hygiene Bot", #ticket-hygiene).

## Evidence on Hand

- Real data comes from running the notifier: `state.db` holds the activity trace, alerts and checks.
- There are no customer logos, testimonials, or marketing claims, and none should be invented.
- Customer reply text appears only inside traces, for people on the allow-list.

## Product Principles

1. **Every verdict is explainable.** An alert or a non-alert can always be traced to the theme, the event, and the model's score.
2. **The associate's own team comes first, with nothing hidden.** Default to their team, and keep everything one click away.
3. **The present matters most.** Live state and unreviewed alerts lead. History is there to answer questions.
4. **Disagreement is data.** Marking an alert wrong should be as easy as confirming it, and is never punished.
5. **Quiet when healthy, loud when broken.** Notifier health is ambient until it fails.
