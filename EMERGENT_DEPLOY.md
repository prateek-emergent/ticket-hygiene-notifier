# Deploying on the Emergent platform: brief for the Emergent agent

This repository is a finished, tested app: the **Trinity ticket-hygiene notifier** (Python, no web frontend to
build). It watches Trinity support tickets, judges them with Jev, and posts alerts to Slack. Your job is to
**run it as it is** and **move its storage from SQLite to the app's MongoDB**. Do not redesign or "improve" the
checks, prompts, thresholds or UI.

Background: `README.md` (how it works), `architecture.md` (design), `pending_decisions.md` (open questions).

## 1. What runs

One container, three long-running processes. See `Dockerfile` and `docker/start.sh`:

| Process | Command | Notes |
|---|---|---|
| notifier | `python -m notifier run` | Background worker, polls Trinity every 60 s. Not a web server. |
| dashboard | `python -m dashboard` | aiohttp web UI on `$PORT` (default 8090), host `0.0.0.0` via `DASHBOARD_HOST`. The built UI is in `dashboard/static/`. No npm build is needed. |
| watchdog | `python -m notifier watchdog` | Sends the owner a Slack DM if the notifier stops. |

- **Python:** 3.13. Dependencies are in `requirements.txt`.
- **Health check:** `python -m notifier health` (exit 0 = heartbeat under 5 min old).
- **Expose:** only the dashboard port.

## 2. Platform settings (required)

- **Any number of copies is fine** (the platform runs two). All copies serve the dashboard; only the copy holding
  the `notifier` lease in the database runs the notifier and watchdog (`backend/server.py`, `lead()`), and a
  standby copy takes over within about a minute if that copy stops.
- **Never park or scale to zero.** The notifier works with no web traffic. If parked, it stops checking tickets, and the watchdog stops with it.
- **Internal app.** It must reach Trinity's MCP endpoint and Emergent's LiteLLM (both internal addresses), plus `slack.com`.

## 3. Environment variables (platform secrets, never in code)

Names and meanings are in `.env.example`. Required:

| Variable | Notes |
|---|---|
| `TRINITY_MCP_URL`, `TRINITY_MCP_TOKEN` | Read-only Trinity key |
| `JEV_API_KEY` | Emergent LiteLLM key for Jev |
| `GOOGLE_CLIENT_ID` | Dashboard sign-in |
| `DRY_RUN=true` | **Keep `true`.** Only the owner switches it to `false`. |

Optional:

| Variable | Notes |
|---|---|
| `SLACK_BOT_TOKEN`, `SLACK_CHANNEL` | Once the Slack app is approved |
| `ANTHROPIC_API_KEY` | Claude fallback; without it, it is off with a warning |
| `MONGO_URL`, `DB_NAME` | The app's MongoDB, after section 4 |

## 4. Move storage from SQLite to MongoDB

All storage is in two files:
- `notifier/store.py`: the `Store` class, written by the notifier and the watchdog;
- `dashboard/queries.py`: the `Data` class, read by the dashboard, which also writes feedback and sessions.

`notifier/shift_checks.py` makes one direct `db.execute` call. Nothing else touches the database. Keep the same
method names and return shapes so the rest of the code doesn't change. Use MongoDB when `MONGO_URL` is set, and keep
SQLite when it isn't, for local runs and the tests.

| SQLite table | MongoDB collection | Unique key (create a unique index) |
|---|---|---|
| `activity` | `activity` | none. Index `at`, `ticket_id`, and `(rule, trigger_event_id)` |
| `kv` | `kv` | `key` |
| `ticket_progress` | `ticket_progress` | `ticket_id` |
| `checks` | `checks` | `(rule, trigger_event_id)` |
| `alerts` | `alerts` | `(rule, trigger_event_id)` |
| `alert_claims` | `alert_claims` | `(rule, trigger_event_id)` |
| `feedback` | `feedback` | none. Index `(rule, trigger_event_id)` |
| `dashboard_sessions` | `dashboard_sessions` | `token_hash`. Add a TTL index on `expires_at` if convenient |

### Duplicate-alert rules: must not break

These rules are what stop engineers from being tagged twice for the same thing:

1. **`Store.claim_alert(rule, trigger_event_id)` must be atomic.** It returns `True` to exactly one caller, even
   when two notifier processes call it at the same moment. In MongoDB, do an `insert_one` into `alert_claims`
   with the unique index on `(rule, trigger_event_id)`: return `True` on success and `False` on `DuplicateKeyError`.
   It must also return `False` when an `alerts` row already exists. **Do not** implement it as "find, then insert": that has a race window.
2. **`Store.release_alert` deletes the claim**, so a failed post can be retried.
3. **`Store.record_alert` must not create a second row** for the same `(rule, trigger_event_id)`. Use an upsert with
   `$setOnInsert`, or ignore `DuplicateKeyError`. The SQLite version uses `INSERT OR IGNORE`.
4. **`kv`, `ticket_progress` and `checks` are upserts by their keys**, as in SQLite.
5. **Timestamps** are stored as ISO-8601 UTC strings in SQLite. Keep them comparable. The dashboard and watchdog parse them with `datetime.fromisoformat`.

### Done means

- `python -m pytest` passes: 108 tests today. Do not delete or weaken any test. Two tests in particular must pass:
  - `tests/test_service.py::test_two_notifier_copies_on_one_database_post_each_alert_once`
  - `tests/test_service.py::test_a_failed_post_releases_the_claim_so_it_is_retried`
- Add a MongoDB run of those two tests, for example with `mongomock` or a test database, so the duplicate rules are proven on MongoDB too.
- After deploying: the dashboard's System page shows the notifier **running**, and checks appear on the Live page within 2–3 minutes.

## 5. Do not change

- **Trinity stays strictly read-only.** Never call a Trinity write tool.
- **`config.py`** (which themes are on, thresholds, models) and **`DRY_RUN`** are the owner's decisions.
- **No secrets in code or in the repo.** No customer ticket text in logs beyond what the code already writes.
