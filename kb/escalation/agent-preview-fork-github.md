# Agent, preview workspace, fork, GitHub, VS Code, job and Wingman issues

## Covers
- Agent hung or not responding: "Agent is running" or "waiting…" for hours, stuck on "Thinking…", "There has been an error" or "Internal server error" on every message, agent will not stop or pause, chat input missing, heartbeat stuck, every tool call fails, tool server port 8010 down
- Preview not loading or agent not waking: Bad Gateway, 502, 520, "could not wake up environment", 409 "Another operation is in progress", wake 404, "empty IP", white screen, preview keeps restarting or timing out
- Preview workspace storage: DATA_LOST, "No PVC or snapshot found", "No fresh backups available", PVC Pending, snapshot stuck deleting, disk attached to another node, workspace disk full, stuck lock, workspace empty or back on old code, restore from S3, restic or snapshot
- Agent quality and doom loops: agent says "fixed" but it is not, agent broke working code, agent looping, credits burned in a loop, wrong model ran, poisoned chat history
- Fork stuck: "Finalizing environment", fork button does nothing, fork fails, forked job broken
- GitHub: Save to GitHub fails or says success but GitHub is not updated, "Failed to push to git:", "not a git repository", GitHub connect or authorization, private repo not visible, branch missing from the branch picker, pull from GitHub, saving from the wrong fork, GitHub App repository access
- VS Code will not open: "Password incorrect", 502, code-server not started
- Job deleted, archived or unarchived; job or project delete requests, "Job delete privileges required"
- Rollback of the job or conversation; agent built on the wrong branch
- Job or project transfer between accounts or into a project; "Unauthorized access" after a move
- Wingman: Wingman not responding, Gmail or Google permission, WhatsApp or channel linking, Wingman video or scenes stuck, Wingman memory or context

## Needs L3 when
- The tool server (port 8010) refuses connections, or the environment has no pod ("empty IP"), and one wake or restart did not bring it back — the fix is a pod restart or terminating a wedged workflow (pod access, L3 in-runbook) (#223071, #224836, #201862, #26903, #201870).
- The chat still shows running, waiting or stopped after the customer sent a new message and hard-refreshed, and no workflow is running — the heartbeat reconcile and any status reset are L3 writes (#258560, #226016, #40586).
- The agent cannot be stopped from the chat stop button — stopping a run is an L3 action (#223836, #34997).
- Chat history is poisoned and the customer must keep the same chat, the session is over the message limit, or the agent has no fork or rollback — trajectory or conversation surgery is engineering-only (#262552, #19184, #20471).
- The same platform error hits every message (model configuration error, MCP setup failure, wrong model ran) — platform code or config fix (#27166, #205606, #55784).
- A degenerate no-op loop is confirmed (thousands of identical tool calls) — every confirmed case goes to Agent Engineering.
- A wake or restart returns DATA_LOST, "No PVC or snapshot found" or "No fresh backups available", or the workspace came back empty or on old code — restoring from S3, restic or a snapshot is L3-only, and L2 cannot verify backup contents (#214425, #222110, #220387, #245882, #212106).
- The pod never becomes ready because a PVC is Pending, a snapshot is stuck deleting, the disk is attached to another node, the restore snapshot is corrupted, or a storage incident is running — needs kubectl and PVC access (#206312, #208057, #264052, #227184, #210886).
- 409 "Another operation is in progress" returns on every wake or fork — clearing a stuck lock is L3 (#213151, #206535).
- The workspace disk is full and the pod cannot start — PVC-level cleanup (#253767).
- Supervisord, code-server or the VS Code proxy is not running in an awake pod, or a freshly recreated pod still rejects the VS Code password — in-pod or base-image fix (#2093, #266445, #232218, #221323, #230114).
- A fork fails because the parent environment cannot wake, the forked job's tool server is broken, or the fork's disk cannot attach — pod or storage access (#7637, #10800, #208963).
- Save to GitHub fails with "not a git repository", the workspace git folder is broken, or the git link must be rebuilt with a GitHub App token — in-pod repair (#2093, #205766, #274700).
- Save to GitHub reports success but GitHub gets an old commit because of the platform commit hook, or the same empty "Failed to push to git:" repeats after the customer retried on a loaded app — platform bug, GitHub integration engineering.
- A GitHub import fails while loading the agent, or a stale server-side GitHub connection record must be reset — platform fix (#252044, #237239).
- A deleted (archived) job must be restored — there is no unarchive endpoint; it is an engineering database update (#20943, #243356, #207034, #212092).
- A job or project must be deleted and the support tool returns 403 "Job delete privileges required" or "requires super admin" — only allow-list holders can delete.
- A job transfer returns TRANSFER_FAILED or a server error, or the workspace is empty after a transfer — platform engineering (#273895).
- A Wingman needs a backend change (model swap, context clear, channel or WhatsApp binding fix, stuck scene items) or a Wingman bug is confirmed — only the Wingman team has that access (#211436, #34439, #206205, #249623, #231454).

## L2 can resolve when
- The chat shows running or waiting, every workflow has finished and the pod answers — the customer sends one new message or hard-refreshes (03 Agent Hung, stale status) (#2396).
- Every message fails because the chosen model rejects a setting or the conversation is too large — the customer forks to another model, lowers effort, or uses Conversation Rollback to drop the bad messages (03 Agent Hung, LLM call fails) (#224850, #268134).
- Chat history is poisoned and the customer can move — start a brand-new chat in the same project, not a fork; the code is intact (03 Agent Hung, poisoned history).
- The agent paused because credits ran out — top up and send "continue" in the same chat (03 Agent Hung, credits pause).
- The stuck run has finished or recovered by the time L2 checks — tell the customer to resume (#202885, #47064, #21951).
- The preview restarts or times out under load while the pod is healthy — explain the fixed preview compute and have the agent stop extra background programs (01 Preview Pod, CPU recycle) (#229506, #47682).
- A fork is stuck on "Finalizing environment" and the parent timeline has ForkStarted but no ForkCompleted — replay ForkCompleted with POST /v1/events:batch: success if the child job exists, failed if it does not (permission row 40) (#274470).
- The fork button does nothing on a fork that never ran — fork the original parent job (#235380).
- Save to GitHub ran from an older fork — the customer saves from the job that holds the commits (#255567).
- A repository is not visible or not pushable — the customer grants the Emergent GitHub App access to that repository or reconnects; a revoked authorization can only be fixed by the customer's own approval (#213831, #208780).
- "Failed to push to git:" with an empty message, once — open the app, let it load, retry Save; "remote contains work" — use Create Branch and Push.
- Large or unwanted tracked files block the push — the customer has the agent untrack them with git rm --cached (#225362).
- VS Code says the environment does not exist on an orchestrator root job — send the VS Code link of the builder child environment (#271545); file watcher limit — exclude folders in .vscode/settings.json.
- The agent built on the wrong branch or broke working code — Conversation Rollback, Deployment Rollback, or have the agent switch branch and redeploy (07 Doom Loops, regression) (#13473).
- After a job or project move, publishing shows "Unauthorized access", Manage Publishing is blank or the app is missing — re-run the support-tool Job Transfer (#271851, #274635, #228994, #264955).
- The person has two accounts or Apple IDs — find the user_id that owns the jobs and transfer them with go-ahead (#207922).
- A credit for loop waste is within the support cap — size it from credit_ledger and grant it (07 Doom Loops, goodwill credit).
- A Wingman lost its Google or Gmail permission — the customer removes the old grant and reconnects with every scope selected (#253706).

## L2 must try first
1. Confirm the exact job the customer is using: the fork or child job, not the parent, and not a job ID quoted by Overwatch or another ticket.
2. Check whether the problem is still happening now; several escalations had already cleared.
3. Read the workflow list and the failure reason (cortex-debugger), plus the heartbeats and environments rows in Redash ds 10. Do not trust POD_RUNNING.
4. Have the environment woken once (customer Wake, then wait 5 minutes without clicking again, or restart-environment) and copy the exact response into the note.
5. Where L2 has envcore access, run execute_tool echo (not search_tools) and record "empty IP" or "connection refused".
6. For DATA_LOST or an empty workspace, check volume_snapshots and backup_mode, confirm the live app is unaffected, and never tell the customer the data is lost.
7. For a stuck fork, check whether the child job exists in ds 10 and whether the parent timeline has ForkStarted and ForkCompleted.
8. For GitHub, confirm which job Save was clicked from, compare the latest commit on GitHub with the workspace, read the raw push error, and check GitHub App access and the branch count.
9. For Wingman, get the Wingman ID, the exact error and a screenshot, and rule out Google or Gmail consent.
10. Give the matching self-serve step (new message, new chat, fork to another model, fork the parent, rollback, reconnect, retry Save) and record the result.
11. Do not escalate on an Overwatch "requires platform action" verdict alone; check it first.

## Not a fault
- The agent paused for insufficient credits — top up and send "continue".
- Agent replies do not show because Plan mode is on — turn Plan mode off (#269009).
- The broken behaviour is in the customer's own code or setup (intentional errors, an undeployed contract, app logic bugs) — give the customer agent prompts to fix it (#241870, #31603, #207625).
- Software the agent installed outside /app (for example Postgres) is gone after a wake or fork — only /app persists; have the agent set it up inside the supported stack (#261189, #33890).
- Preview compute is fixed and cannot be raised — stop unused dev servers or deploy always-on workloads (#47682).
- No origin remote in the workspace git config is by design — Save to GitHub adds it for each push.
- .env, lock files, yarn.lock, node_modules and build output are not pushed by design (#197567).
- The customer's own pre-commit or pre-push hook blocks the push — fix or bypass the hook, then save again (#258436).
- History diverged because the code was edited both on GitHub and in the workspace (#198169).
- The branch picker lists at most 100 branches — push to a sync branch and open a pull request on GitHub (#233626).
- There is no pull from GitHub into an existing workspace — a GitHub import starts a new job (#239626).
- Wingman memory rules are preferences, context compaction is expected, and each account has a Wingman limit — explain the product behaviour (#242505, #264423, #44937).
- A third-party outage or Google revoking a third-party grant broke a Wingman — reconnect once the provider is back (#207399, #26870).
- A refund or credit request on top of any of these issues does not by itself make the ticket L3.

## Changed over time
- June 2026: L3 found in source that the GitHub branch picker fetches only 100 branches (#27338, genuine then). Since then it is a known limit that L2 explains (#233626).
- Since 2026-10-06 the Ticket Casebook (272413) states that a fork stuck on "Finalizing environment" is in scope for L2: check the child job and the parent timeline before any escalation.

## Examples
- Genuine L3: #214425: restart-environment returned DATA_LOST; L3 restored the workspace from a verified S3 backup.
- Genuine L3: #206312: the PVC was Pending on a stale node annotation; removed with kubectl.
- Genuine L3: #264052: the disk was attached to another node; L3 unblocked the PVC and restored from restic.
- Genuine L3: #223071: ports 8010 and 8011 refused connections; pod restart and wedged workflow terminated.
- Genuine L3: #226016: the heartbeat was stuck at "stopped" and the heartbeat PUT was refused; fixed by a database update.
- Genuine L3: #2093: code-server was disabled in the pod and /app was not a git repository; repaired in the pod.
- Genuine L3: #262552: a content filter blocked every reply and the agent had no fork or rollback; L3 rolled back the conversation.
- Genuine L3: #243356: the customer archived jobs; there is no unarchive endpoint.
- Genuine L3: #211436: the Wingman team moved the Wingman to another model.
- Not L3: #274470: fork stuck with no child job; fixed by replaying ForkCompleted as failed.
- Not L3: #235380: the fork button was dead on a fork that never ran; the fix was forking the parent.
- Not L3: #2396: the stale "running" status cleared with a hard refresh and a new message.
- Not L3: #224850: the model rejected a setting; the fix was forking to another model.
- Not L3: #202885: escalated 22 minutes in with no live check; the operation completed by itself.
- Not L3: #255567: Save to GitHub ran from an older fork, so nothing new was pushed.
- Not L3: #239626: the customer wanted to pull GitHub changes into an existing workspace; that feature does not exist.
- Not L3: #271851: publish failed after a project move; re-running Job Transfer fixed it.
- Not L3: #253706: Gmail "missing scope"; the customer re-granted Google access with all scopes.
