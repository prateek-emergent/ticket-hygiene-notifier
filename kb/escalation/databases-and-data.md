# Databases and app data: MongoDB data loss, PITR restore, dump export, credentials, dedicated database, repointing, storage buckets

## Covers
- Production data lost or deleted: "records missing", "data disappeared", "collection wiped", "database empty after deploy", content reset to seed or template text
- Restore requests: "restore my database to before X", point-in-time restore (PITR), restore preview, re_insert diff, restore API 409/422/500, data older than 7 days
- Database dump, export or backup: "full export of my database", mongodump, BSON archive, binary fields, GridFS, Viewer "Dump DB" JSON, leaving the platform
- Export refused or failed: too large, export size cap, verification failed, Authentication failed, app not found
- Exposed or leaked MongoDB password or MONGO_URL, credential rotation or revocation; MongoDB auth error code 18, code 13, "not authorized"
- Dedicated database add-on: purchase, upgrade, migration stuck or failed, mongosync, cutover, NamespaceConflict, downgrade, refund, paid but never applied
- Live app shows an empty or old database after Replace, fork, redeploy or switch; data on an old database binding; repoint MONGO_URL
- Data added in preview not showing on the published (live) app; preview vs production data
- Deleted app's database, mongo_db_archives
- Postgres: customer's own Postgres provider, DATABASE_URL, Postgres in preview
- Uploaded files or images missing in production, files in another storage bucket, copy between buckets
- Managed MongoDB cluster errors at runtime (no primary, write errors); customer's own Atlas blocking production
- Questions about backups, snapshot schedule, encryption at rest

## Needs L3 when
- The data was lost or changed more than 7 days ago — outside the PITR window; only DB-infra can look for older snapshots (#249211, #220778).
- The data was overwritten in place (fields changed, balances reset, records re-created), not deleted; or the customer wants the restore into a separate or temporary cluster; or the database is larger than 2 GiB — this needs a PITR clone, which only L3/DB-infra runs (#222742, #24736).
- The L2 PITR preview or apply hit a runbook exit: a 422, 500 or 503 error, a truncated diff, a re_insert count that does not match the customer's count, a job stuck in applying or rolling_back, a 409 "registry disagrees with live MONGO_URL", or the customer used the app after an apply and wants it undone — written exits of the PITR L2 runbook (#272334).
- A platform deploy or platform process deleted production data — L3 restores it and engineering fixes the platform cause (#225218).
- The L2 export job failed with a pass-to-L3 state: over the export size cap, verification failed, Authentication failed, cluster mismatch, app not found or deleted, feature disabled, stuck more than 30 minutes, or a non-primary database is the larger one — the cap is a deployer config change and the rest need DB-infra (#261282, #228931).
- The customer needs object-storage files exported in bulk, the dump delivered into their own storage, or a coordinated cutover that stops the production app — outside the export runbook (#222902, #254522).
- The customer wants an exposed Emergent-managed MongoDB credential rotated or revoked — only the Deployment Team executes rotation; no support tier can (#243685, #32712, #242979, #271807).
- The good data is on an older database binding or in another of the customer's jobs, and the live app must be repointed, merged or switched back — deployments on-call (#47773, #42583, #211788, #209939, #259440).
- A dedicated-database move is stuck or failed with a platform error (mongosync "API did not become ready", NamespaceConflict, 409 at cutover), or shows migrated with no audit row while MONGO_URL still points at the shared cluster — deployer mongo owners (#42238, #49167, #248737).
- A dedicated-database fix needs a database or billing write: wrong entitlement or migration flag, cluster resold or double-booked, paid add-on never applied, purchase reversal and refund, or a migration that put the database in the wrong region — L2 has read-only Redash and no Postgres or deployer database write (#243175, #212142, #198257, #4842, #55400).
- Files must be copied between storage buckets (preview bucket to production bucket, or an old organisation's bucket to the current one) — support has read, not write, access to buckets (#260917, #247126, #244991).
- A managed shared MongoDB cluster still has no primary or still rejects writes when L2 re-tests now — platform infrastructure (#32647, #35212).
- The answer needs Atlas-admin data: backup schedule, last snapshot time, profiler output or index definitions — L2 has no Atlas admin access (#222620, #205536).

## L2 can resolve when
- Records were deleted (not overwritten) within the last 7 days, the database is 2 GiB or smaller, and the PITR preview re_insert count matches the customer's count — MongoDB PITR Restore L2 Runbook, additive mode, with the customer's written approval (#238337, #233339).
- The customer wants old data checked or a restore validated without touching production — PITR L2 Runbook steps 1 to 4 only (preview into a scratch copy and diff) (#246362).
- The app's own code (reset endpoint, seeder, bulk delete, import) deleted records within the last 7 days — the customer fixes and redeploys the code first, then L2 runs the PITR L2 Runbook.
- The customer wants a copy of their app's MongoDB database, including BSON, binary fields, GridFS inside the database, or more than one database — L2 Runbook: Mongo Dump Export, after the ownership check (#273603, #273153, #271139, #248215).
- The customer says the Viewer "Dump DB" export is JSON only or lost binary data — run the Dump Export runbook; this alone is not a reason to escalate (#243739).
- The export download link expired — repeat the download step of the Dump Export runbook; no new export is needed.
- A deleted app's database is listed in mongo_db_archives — tell the customer a republish of the same app restores it; the balance must be positive first (#262674).
- The data is safe on an older binding — L2 finds it in deploy_runs_v3 and tells the customer it is safe; only the repoint itself goes to L3.
- A dedicated-database upgrade failed because the app's own code crashed in the rollout log (for example a unique index conflict) and the customer has fixed it — the customer presses Retry (#272454).
- The dedicated-database status is already migrated and verified and the customer only wants an answer, or another ticket on the same app is already open — answer from Redash ds=5 or link the open ticket (#199610).
- The backend fails with code 13 because DB_NAME was changed, or MONGO_URL or DATABASE_URL was emptied by the customer's own secret edit — the customer restores the value in Secrets and republishes, or L2 uses the secret-redeploy playbook (#214023).
- A managed-database connection error has already recovered when L2 re-tests — reply with the incident explanation (#242264).
- The customer asks general backup facts (encryption at rest, backups, the 7-day PITR window) — answer from published facts (#229982).

## L2 must try first
1. Verify ownership: ticket sender email, then user id, then deployments_v3.user_id. List every job the customer owns that serves the same site.
2. Write down the incident time in UTC and whether it is within the last 7 days.
3. In Redash ds=5 list deploy_runs_v3 for the app (run type, mongo_cluster, DB_NAME per run). Note any binding change, first publish or Replace with new database.
4. Find where the good copy lives before planning a restore: live database, older binding, another job, mongo_db_archives, or the PITR window.
5. Check the app's logs and code for seeders, reset endpoints, imports or bulk deletes at the incident time, and decide whether records were deleted or overwritten.
6. For deleted records within 7 days, run the PITR preview and compare re_insert with the customer's count. Escalate only on a runbook exit and quote it.
7. For any dump, export or backup request, run the Dump Export runbook. Escalate only with the export job's failure state and error text.
8. For dedicated-database tickets, read mongosub_migrations, mongo_migration_audit_v3 and user_mongo_clusters, check the live MONGO_URL host, and read the failed run's rollout log.
9. For missing files, check storage_buckets (Redash ds=18) for both workspaces and the total stored bytes before calling it data loss.
10. For connection errors, re-test now and classify the error as code 18, code 13 or timeout.

## Not a fault
- Records added in preview after the first publish are missing on the live app — preview data is copied to production only at first publish or Replace with new database; plain redeploys never copy it. Tell the customer to re-enter or import the data, or use Replace with new database only if they accept production being replaced (#31757).
- Content keeps reverting to template text after restarts — the app's own boot seeder overwrites it. The customer has the agent make the seeder insert-only and redeploys; edits overwritten between restarts cannot be restored.
- Records remain after an additive restore — they were created after the restore point, and additive restore never deletes newer documents. The customer removes them (#233339).
- The app blocks a user with a lock or flag its own code wrote — the customer clears it with the app's override or the Database Manager (#237784).
- The customer's own (not Emergent-managed) database blocks production traffic — send the published egress IP list and ask the customer to allowlist all of it (#273982).
- A credential for the customer's own database provider was exposed — the customer rotates it with their provider.
- The app uses the customer's own Postgres and DATABASE_URL is empty or wrong after their own secret edits — the customer restores it in Secrets and republishes (#214023).
- Postgres is not a supported deploy stack, and Postgres the agent installed in preview outside /app is lost on fork or restart — explain the platform limit (#8098, #33890, #261189).
- The export says "No databases to export" — the app has no data to export.

## Changed over time
- Since about 2026-08-18: L2 runs additive PITR restores with the PITR L2 Runbook. Before that, every production restore went to L3 (#217088).
- Since early September 2026 (runbook last edited 2026-09-24): L2 runs dumps with the Dump Export runbook. Before that, dumps went to L3 (#206899). Since 2026-09-24, exports of apps with more than one database no longer need L3.
- Export size cap: 1 GiB in production on 2026-09-24 (#261282); the 2026-09-30 playbook says it was raised to 3 GiB. Under either cap, an export refused for size is L3.
- Since 2026-08-25: a backfill archived and dropped some deleted apps' databases. Check mongo_db_archives; do not assume a deleted app's database is still live (#262674).

## Examples
- Genuine L3: #249211: data overwritten about three weeks earlier, outside the 7-day PITR window; restored from an older backup.
- Genuine L3: #24736: the app's own endpoint wiped collections and reset balances to zero; needed a snapshot restore to a temporary cluster.
- Genuine L3: #272334: the PITR preview would re-insert far more documents than the customer reported; the runbook mismatch exit applies.
- Genuine L3: #261282: the L2 export was refused because the database was over the export size cap; L3 ran mongodump from the jumpbox.
- Genuine L3: #243685: exposed managed MongoDB credential; rotation executed by the Deployment Team.
- Genuine L3: #248737: dedicated migration marked migrated with no audit row and no cutover.
- Genuine L3: #47773: the real data stayed on the old database binding; L3 merged it into the live database.
- Genuine L3: #247126: an organisation move left uploads in the old bucket; objects had to be copied into the live bucket.
- Not L3: #273603: a BSON dump with binary fields was delivered through the L2 export runbook in 27 minutes.
- Not L3: #238337: seven records hard-deleted one day earlier; the additive PITR runbook flow restored them.
- Not L3: #246362: a restore validation the note called operator-gated ran first try with PITR runbook steps 1 to 4.
- Not L3: #31757: the missing records were added in preview after the first publish, so they never reached production.
- Not L3: #233339: records left after an additive restore were created by the app's own seed code after the restore point.
- Not L3: #273982: the production egress IPs were already on the published list; the customer's copy was outdated.
- Not L3: #214023: the outage was an empty DATABASE_URL from the customer's own secret edits on their own Postgres.
- Not L3: #272454: the dedicated migration failed on the app's own unique-index conflict; a retry after the customer's fix succeeded.
