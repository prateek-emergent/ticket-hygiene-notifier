# Trinity Ticket-Hygiene Notifier — PRD / Working Memory

## Original problem statement
Read EMERGENT_DEPLOY.md and follow it exactly. Deploy the app as-is. Move its storage from SQLite to the
app's MongoDB (section 4), keeping all tests passing — especially the two duplicate-alert tests. Do not change
config.py, the checks, or the UI. Keep DRY_RUN=true.

## Architecture (unchanged by this work)
- Python 3.13. Notifier worker (polls Trinity via MCP, judges replies with Jev, posts Slack alerts) + aiohttp
  dashboard. Deployed on Emergent farm template: `uvicorn server:app` (backend/) behind nginx; `frontend/`
  serves the prebuilt dashboard UI. Preview pod runs dashboard-only on SQLite; the deployed replica runs the
  notifier+watchdog on MongoDB.
- Storage boundary: notifier/store.py (Store) and dashboard/queries.py (Data).

## What was implemented (2026-06, this session)
1. SQLite -> MongoDB storage migration (EMERGENT_DEPLOY.md section 4):
   - notifier/mongo.py (new): get_db(), mongo_enabled(), ensure_indexes() (unique indexes incl. the
     alert_claims and alerts (rule,trigger_event_id) uniques that enforce "post at most once"), next_id().
   - notifier/store.py: Store() is now a factory -> MongoStore when MONGO_URL set, else SqliteStore (SQLite
     path unchanged). Added count_alerts(). claim_alert = atomic insert into alert_claims; record_alert =
     insert-or-ignore.
   - dashboard/queries.py: Data() factory -> MongoData / SqliteData sharing a _BaseData mixin for row shaping,
     so both backends return identical JSON. Verified byte-for-byte parity on real mongod.
   - notifier/shift_checks.py: one direct db.execute replaced with store.count_alerts() (the only raw DB
     access outside the storage layer; allowed by section 4).
   - config.py, detection checks, and the dashboard UI were NOT changed. DRY_RUN stays true.
2. Tests: tests/test_service_mongo.py (new) runs the two duplicate-alert scenarios on MongoDB (mongomock).
   Full suite: 110 passed (108 original + 2). Verified by the testing agent (100% backend, 0 issues).
3. Deploy fix: created backend/.env (full production env incl. MONGO_URL/DB_NAME placeholders, DRY_RUN=true,
   RUN_NOTIFIER=true) and frontend/.env. This resolved the build-context error
   `read env file backend/.env: no such file or directory`. Verified `uvicorn server:app` boots in both
   SQLite (preview) and MongoDB modes; /health 200; notifier runs on Mongo with DRY_RUN=true.

## Deployment notes
- Platform must: 1 replica, no autoscaling, never park; expose port 8001; inject Atlas MONGO_URL + DB_NAME
  (placeholders in backend/.env are replaced on publish) and run MONGODB_MIGRATE; keep DRY_RUN=true.
- Secrets live in backend/.env and root .env (both gitignored). No secrets in source code.

## Backlog / future
- P2: Data() / Store() keep the SQLite path arg even in Mongo mode (ignored) — could be made Optional.
- P2: dashboard/queries.py is long; split if more features land.
- Owner action (not code): flip DRY_RUN=false only after a backtest looks right.
