# Deploying and publishing apps: publish stuck, deploy failed, live app down, old code live, prod secrets, rollback

## Covers
- Publish stuck or blocked: "Publishing…" never ends, "A deployment is currently in progress", "Deployer agent is running", "Agent is fixing", a deploy run stuck "pending" or "Queued", Redeploy or Replace button missing, "Unauthorized access" or 403 on publish, "Agentic deployment is not enabled for this job"
- Deploy failed at build (Cloud Build): "TerminalCloudBuildFailure", "cloud build: build failed", empty or unrelated build error, "manifest invalid", "[R2_DOWNLOAD] Failed after N attempts", Node engine, yarn or pnpm errors, build timeout, auto-created DEPLOY_FAILURE ticket
- Deploy fails before build because the source workspace cannot be reached: wakeup_environment, pull_source or manage_secrets step fails, "container not found (\"agent-env\")", "ensure-environment … context deadline exceeded", PVC Pending
- Live app down after a deploy: 502, 503, 520, CrashLoopBackOff, health_check failed, readiness timeout, "exec format error", "command not found", ModuleNotFoundError, OOMKilled, white screen, blank page, "Welcome to nginx", "app was down at HH:MM"
- Live site serves old code: changes not showing after a successful deploy, old JS bundle, custom domain or the .emergent.host address serving an older copy of the app
- Secrets and environment variables in production: works in preview but not in prod, prod secret keeps an old value, Secrets panel locked, CORS_ORIGINS, REACT_APP_BACKEND_URL, NEXT_PUBLIC_* empty, .env
- Rollback of a deployment to the last working version
- System packages and custom build config: LibreOffice, Tesseract, fonts, Chromium or Playwright, ffmpeg, Node.js in production, apt packages, custom nginx.conf, Dockerfile, entrypoint.sh, dynamic_manifest, replica count, restart of the prod container
- Cluster and capacity errors: "failed to allocate a serviceIP: range is full", "no IP addresses available in range set", pods Unschedulable "Insufficient cpu/memory", DNS-1035 name rejected, "has no plane configured", Atlas "GROUP_USERS_LIMIT_EXCEEDED" on deploy
- Prod SOS tickets and production outages; a failed deploy that left a second copy running (duplicate emails or crons)

## Needs L3 when
- A deploy run is still pending or running more than 2 hours after it started and blocks new publishes, or a pending run locks the Secrets panel — clearing it is a deploy_runs_v3 database write with go-ahead; L2 has read-only Redash.
- The customer already sent the chat prompt "Redeploy this job using the deployer agent" and the panel still shows "Deployer agent is running" or "Agent is fixing" — platform state bug.
- Publish is refused with a platform error such as "Agentic deployment is not enabled for this job", or an internal_server_error with no run created and no billing, tier or phishing reason in the deployer log — platform code fix.
- The first real build error line is in a platform-owned file or step (Dockerfile.cloudbuild, entrypoint.sh, the build template, the base image), the app's stored template or architecture field is wrong, or the base image is too large or too old for the build — needs a manifest edit, a deployer database write or a code change.
- The build step error is empty and the deployer build-log tools return no error line — engineering reads the Cloud Build log.
- The same wakeup_environment, pull_source or manage_secrets error ("container not found", "ensure-environment … context deadline exceeded", PVC Pending, snapshot stuck deleting) appears on two or more consecutive runs — the repair needs kubectl or envcore write access.
- The live app crash-loops because of a platform file or field: "command not found" for a path the platform entrypoint rewrote, a console script such as uvicorn missing from a platform cache, or "exec format error" because the app record says arm64 — template fix or database write.
- Production needs a system package that is not in the base image (LibreOffice, Tesseract, fonts, Chromium or Playwright, a Node.js runtime), or a customer's own nginx.conf or Dockerfile is ignored because dynamic_manifest is off — the manifest write (update_deployment_manifest) and the dynamic-manifest flip are go-ahead operator actions.
- The latest run and its R2 build hold the new code but the custom domain or .emergent.host address serves an older copy, or every deploy reports success while shipping a frozen snapshot — KV pointer rewrite or deployer fix.
- A Live secret was saved and a successful run followed but the pod still has the old value, a platform-managed key (MONGO_URL, REACT_APP_BACKEND_URL) is wrong on the pod, or someone must read a secret's value — no support tier can read v3 secret values.
- The customer needs production put back on the last good image and the self-serve Deployment Rollback cannot do it — rollback-deploy is a go-ahead L3 action.
- The production container must be restarted without a republish, or a failed deploy left a second copy running — needs kubectl.
- The error names a cluster or quota resource: "range is full", "no IP addresses available in range set", Unschedulable "Insufficient cpu/memory", DNS-1035, "has no plane configured", "GROUP_USERS_LIMIT_EXCEEDED" — infra or DB-ops capacity action.
- The customer needs more than 2 replicas, a CPU or memory override, or replicas on a legacy (non-v3) app — not available in the L2 override API.

## L2 can resolve when
- The panel shows "Deployer agent is running" or "Agent is fixing" but every deploy run is finished — tell the customer to send the chat prompt "Redeploy this job using the deployer agent".
- Publish fails with "Unauthorized access" or 403 after an account transfer, an org change or a move into a project — re-run the support Job Transfer, including the hidden deployer helper job.
- The build log shows an error in the customer's code or dependencies (yarn engine check, a prebuild script calling python3, a missing package, a third-party library bug) — give the agent prompt to fix or pin it, then the customer publishes once.
- ModuleNotFoundError in production — the agent installs the module in the workspace so the workspace pip list has it, then the customer publishes once; editing requirements.txt alone does nothing.
- The crash traceback comes from the customer's code or a secret the customer set (malformed MONGO_URL, CORS_ORIGINS rejected at startup, load_dotenv with override=True) — agent prompt or corrected secret, then republish.
- Backend is OOMKilled on the Starter tier — the customer upgrades the tier and redeploys.
- Works in preview but not in prod because of a value — the customer sets the Live value in Publish → Secrets (not the workspace .env) and republishes; add both apex and www to CORS_ORIGINS; put NEXT_PUBLIC_* values in .env.production; set every backend URL variable to the live address.
- Changes are not live because no deploy run exists after the change (a chat "rebuild" does not publish) — give the Republish changes + Confirm steps.
- The customer wants an earlier version back — guide them to the self-serve Deployment Rollback.
- The customer wants 1 or 2 replicas (max_replicas up to 2) on a v3 app — use the L2 per-app k8s override API.
- A restart would fix it (for example an in-memory cache) and the customer can republish — a republish of the same code replaces the pods.
- The deployment was removed because credits went negative — the customer adds credit and republishes the original job with a normal Publish.

## L2 must try first
1. List the app's deploy runs (fetch_recent_deployments or Redash ds 5 deploy_runs_v3) and record the failing step, its error line, whether it repeats, whether a later run succeeded, and whether any run is still pending and since when.
2. Open the live URL from a clean client or private window and record what it serves. A failed or stuck new run leaves the previous version live.
3. Read the real error: the full build log through the deployer build-log tools, or the pod state and previous logs (describe_app_pod, fetch_app_logs). Do not copy the Overwatch or deployer auto-RCA without checking it.
4. Decide whether the failing file or command is in the customer's repo or in a platform file or step, and write which.
5. Try the matching self-serve fix (chat redeploy prompt, Job Transfer, Publish → Secrets and republish, tier upgrade, agent prompt, Deployment Rollback) and wait for one attempt.
6. For a run that is pending with no progress, wait until it is more than 2 hours old; the platform recovery sweep fails such runs.
7. For a package request, check whether the package is already in the production image.
8. For a cluster or capacity error, check whether other apps on the same cluster fail the same way, then escalate at once.

## Not a fault
- A short blip while a new version goes live — publish replaces the old pods without draining; expected behaviour.
- The UI shows "failed" or "Cleaning Up…" but the live URL serves the new version — reassure the customer; no redeploy needed.
- Only one browser sees the old version and a private window shows the new one — a service worker or browser cache; clear it.
- An OpenClaw app shows Redeploy disabled — this is by design.
- The build fails on the customer's own setup, such as ESLint warnings treated as errors (CI=true) or a .dockerignore rule removing needed files — the agent fixes the project.
- The stack is not supported for deploy (for example Express, Vite and Postgres) — port to FastAPI and MongoDB or host elsewhere.
- Requests are cut at about 30 seconds in production — a platform limit; move long work to a background job with polling.
- The error comes from the app's own code: its own auth returns 401, a single worker is blocked, a database index is missing, or a cron runs more often than every 15 minutes — give the agent prompt.
- The requested package is already in the production image — tell the customer how to use it.
- A brief pod restart with restart count 0 after a node reschedule — not a crash.
- The Prod SOS tag alone — it is added automatically and does not show a platform fault.

## Changed over time
- 2026-07-31: deployer v0.7.104 pushes image tags one after another. Before that date an intermittent Cloud Build "manifest invalid" was a known platform race needing engineering; after it, do not cite the race as the cause.

## Examples
- Genuine L3: #9029: a run stuck for six days held the publish slot ("A deployment is currently in progress"); the Deployment team cleared it with a database update.
- Genuine L3: #7627: the platform Dockerfile template deleted a line of the customer's App.js on every build; engineering edited the template.
- Genuine L3: #13787: nine runs failed with "container not found (\"agent-env\")"; engineering repaired the source environment.
- Genuine L3: #29777: the customer's nginx.conf was ignored because dynamic_manifest was off; needed a database write.
- Genuine L3: #38310: exec-format crash loop because the app record said arm64 while the build made amd64; architecture field rewritten.
- Genuine L3: #219816: the domain pointed at an older copy of the app; engineering rewrote the pointer.
- Genuine L3: #205200: "failed to allocate a serviceIP: range is full" on one cluster; infra capacity.
- Genuine L3: #268537: a pending run locked the Secrets panel; the customer had no UI path.
- Not L3: #208041: panel stuck on "Agent is fixing" with every run finished; the chat redeploy prompt fixed it.
- Not L3: #264955: "Unauthorized access" on publish after an account transfer; re-running the Job Transfer for the helper job fixed it.
- Not L3: #206553: escalated after a run sat pending for 14 minutes; a later run succeeded with no engineering action.
- Not L3: #231015: 520s from OOMKilled on the Starter tier; the customer upgrades the tier.
- Not L3: #42625: crash loop from a MONGO_URL the customer had overwritten; fix the secret and republish.
- Not L3: #202171: build failed on the customer's ESLint warnings; the claimed architecture mismatch was wrong.
- Not L3: #270795: short downtime at publish; expected behaviour.
- Not L3: #27716: request to add ffmpeg to production; it was already in the image.
