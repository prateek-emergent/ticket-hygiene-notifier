# Integrations in customer apps: Universal Key, wallets, storage, MCP connector, managed Stripe and email

## Covers
- Universal API Key / Universal LLM Key / EMERGENT_LLM_KEY: "No key available", "Failed to toggle key", key shows 0.00 or a negative balance, Add Balance fails, "Failed to increase budget", EMERGENT_KEY_FUNDING_CAP_REACHED on a discounted or intro plan
- Universal Key budget errors: "Budget has been exceeded", "Current cost > Max budget", LLM calls still fail after a top-up, auto-recharge / auto-topup, "Daily spend limit reached" (409), FREE_USER_EXTERNAL_ACCESS_DENIED (403), 401 "Invalid API key" after the key was regenerated
- Universal Key money: purchased credits landed in the key balance, request to move the key balance back to main credits, top-up charged but never reached the key, auto-recharge transfers
- Universal Key proxy: TypeError or crash on Claude calls, prompt caching shows zero cache tokens, 60-second timeout, public endpoint for outside calls
- Integration wallet and object storage (Tigris): uploads fail with 402 "Storage access suspended", grace period, images or files missing on the live app (storage 404/500), older files missing after a workspace move, storage limit, "storage keys never provisioned"
- Emergent MCP connector in ChatGPT, Claude, Codex or n8n: OAuth 400, invalid_redirect_uri, "Could not load connection request" after Allow, tools disappear after about an hour, jobs missing from list_jobs, "OIDC enabled"
- Managed Stripe in an app: stuck on test keys, "System Keys" read-only, cannot unlink or remove the Stripe sandbox, sandbox expired or claim link invalid, "Make payments live" blank page, live key expired, webhook signature failures, STRIPE_SECRET_KEY won't save, STRIPE_WEBHOOK_SECRET not editable
- Managed email (Resend) in an app: 422 "undeliverable recipient", address on the suppression list, no_mx, 401 "invalid X-Email-Key", email disabled after bounces, leaked email key
- Third-party APIs and dependencies in customer apps: third-party key works in preview but not live, BYO Google OAuth redirect_uri_mismatch, Supabase/Postgres in production, pip ResolutionImpossible on fastapi/starlette/litellm, platform-pinned package with a CVE, provider outage
- Feature and information requests: "please add / disable X", legal, privacy or hosting facts, bug bounty, "has X launched"

## Needs L3 when
- A Universal Key fix needs a write to the key, wallet, paid flag or LiteLLM budget: the key budget does not rise after a refill, the key has a lifetime budget that never resets, a paying customer still shows as unpaid after a build job ran, or budget writes error — L2 cannot write integration-proxy or LiteLLM data; integration-proxy owners or billing engineering (#229578, #45652).
- Money left the customer's main credits or card but never reached the Universal Key (a stranded top-up), or credits were deducted while the key was never created — engineering ledger fix and refund (#26236, #20964).
- No Universal Key exists even after the customer ran a build in that workspace, or a funded wallet has no key and Add Balance keeps failing after the self-serve steps — integration-proxy owners (#216017).
- A v3 redeploy still ships the old EMERGENT_LLM_KEY after the key was regenerated — deployer owners.
- The Universal Key proxy crashes on a valid, correctly shaped request — platform code fix (#258728).
- Uploads still return 402 "Storage access suspended" for a paid account with a funded wallet after a retry, or a paid account is treated as free — clearing the grace period and lock is an integration-proxy write (#270264, #222072, #9208, #29181).
- Object storage is down for many apps, a storage limit must be raised, files must be copied between buckets after a workspace move, or stored objects must be deleted or bulk-exported — support access to object storage is read-only (#5267, #222902).
- The MCP connector fails on a supported client (Claude, ChatGPT or a local loopback client) after the known client-side causes were ruled out — only connector-gateway logs or source show the cause, and L2 has no access to them (#240007, #252846).
- A managed Stripe sandbox must be unlinked and the owner cannot do it (the Payments tab Remove is not available, or the agent refuses to unlink) — the integration-proxy unlink is an engineering action (#219646, #255655).
- A managed Stripe live key must be reissued, a key mint is stuck, sandbox provisioning returns 500, or Emergent's own sandbox Stripe account needs a change (for example orphaned test webhooks) — payments / integration-proxy team (#228508, #252836).
- Managed email needs something the support email admin API cannot do: the address was suppressed after a spam complaint, the admin DELETE fails at the Resend step, the block returns after clearing, a gate or verifier bug blocks valid addresses, the app is disabled for phishing, or a leaked managed email key must be revoked and reissued — integration-proxy email owners / retention on-call; phishing goes to Trust & Safety (#229377, #271069).
- A customer's fix is blocked by a package that Emergent publishes or pins (the litellm or emergentintegrations wheels, an openai or litellm version conflict) — agent-reliability / app-builder owners (#19216).

## L2 can resolve when
- "No key available" or "Failed to toggle key" and no key exists yet — the key is created on first use: the customer starts a build in that workspace or asks the agent to use the Universal LLM Key (#26713, #28898, #26772).
- "Failed to increase budget" with EMERGENT_KEY_FUNDING_CAP_REACHED on a discounted or intro plan — the funding cap works as designed; a regular paid top-up or a renewal lifts it (#38816).
- Add Balance is blocked by another gate (expiring or daily credits cannot fund the key, a restricted free signup) — match the error string to the gate in the Universal Key playbook and explain it.
- "Budget has been exceeded" with auto-recharge off or an empty wallet — the customer turns auto-recharge on or adds balance, then retries.
- "Daily spend limit reached" (409) or runaway spend — list each key's limit and auto-recharge setting; the customer sets the daily limit per project.
- FREE_USER_EXTERNAL_ACCESS_DENIED — a free customer upgrades or calls the key only from Emergent-hosted apps; for a paying customer, running any build job in that workspace re-syncs the paid flag.
- A deployed app's AI stops after the key was regenerated while preview works — the customer redeploys once (#20964).
- A Claude call through the key fails with TypeError because the message content list holds a bare string — the customer sends plain text or a list of text objects.
- How-to questions: the key's public endpoint, the preview-only 60-second timeout (use async polling), or explaining auto-recharge transfers (#220247, #14260, #32785).
- MCP client-side causes: n8n Cloud or any client other than Claude, ChatGPT or loopback is not supported (#250596); Codex drops the tools after about an hour because of a Codex token-renewal bug (#209835); "Could not load connection request" right after Allow means the Emergent session expired, so sign out, sign in and retry (#234916); a job inside a Project is missing from list_jobs, so give the job id directly (#252846); "OIDC" ticked in ChatGPT, so untick it.
- Managed Stripe: the customer wants their own keys or the sandbox expired — the owner uses Manage → Payments tab → Stripe menu → Remove, or asks the agent to unlink the sandbox and use their own keys, then sets their STRIPE_* keys in Secrets and redeploys (#203831, #232014, #217763). Stuck on test keys: finish go-live from the claim link.
- Managed email 422 or 401 where the admin diagnose names a suppression, no_mx, a verifier block or a bounce-rate auto-disable — clear it with the support email admin API (delete suppression, verify-override, re-enable the app), then confirm a live send delivers (#274499, #254237).
- Storage 402 with an empty storage wallet or negative credits — the customer tops up and retries an upload (#25464). Files that were never stored are re-uploaded.
- A third-party key works in preview but not live — backend keys go in Manage → Secrets, frontend public keys in frontend/.env, then redeploy. BYO Google OAuth redirect_uri_mismatch — the customer adds the live and custom-domain callbacks in their Google console. Postgres or Supabase in production — point DATABASE_URL at an external database. A fastapi/starlette pip conflict — bump both together.

## L2 must try first
1. Record the exact error text, HTTP status, app, job and time.
2. Decide managed or bring-your-own with get_integration_status and Redash ds 18 (not ds 5); editing a managed key and redeploying does nothing.
3. Universal Key: find the identity that owns the key (user or org) and check every key row. Record whether a key exists, the paid flag, the wallet balance, any grace period, and the LiteLLM budget against spend. Keep main credits, key budget and wallet apart. Compare the deployed EMERGENT_LLM_KEY with the owner's current key.
4. Before claiming stranded money, find the debit in the main ledger and look for the matching credit on the key or wallet side.
5. Storage 402: check wallet balance, credit balance, paid flag and grace deadline, and have the customer retry once after topping up.
6. MCP connector: record the client name and version, the attempt time with timezone, and whether the job sits inside a Project; rule out the client-side causes; test only against the client's real callback URL.
7. Managed Stripe: record the lifecycle state, linked or not, payments live, and whether the owner tried Payments tab Remove or the agent unlink and what happened.
8. Managed email: run the admin diagnose, name the gate, run the matching admin API call, and check a live send. Escalate only with the gate and the call that failed.
9. Check any Overwatch or customer-agent claim ("we will transfer it manually", "keys were never provisioned") before repeating it.

## Not a fault
- The customer wants the Universal Key balance moved back to main credits — it only flows one way; explain the two balances and do not promise a manual transfer (#35213).
- "Failed to increase budget" on a discounted intro plan — the funding cap; explain how a regular top-up lifts it (#38816).
- The Universal Key buttons fail before any key exists — the key is created on first use (#26713).
- Prompt caching shows zero cache tokens — the prompt is below the provider's minimum cacheable size, or the customer's own client strips cache_control (#24538, #250231, #43563).
- Storage uploads return 402 because the storage wallet is empty, or the app was coded against storage keys that do not exist — top up, or use the managed storage through the Emergent proxy (#25464, #236487).
- MCP tools drop in Codex, n8n Cloud is refused, or the session expired at Allow — client-side; give the matching fix (#209835, #250596, #234916).
- Managed Stripe: Stripe business verification unfinished or country mismatch (#224509, #235621); the customer pasted Stripe's masked key (#246464); the managed webhook works and failures are old or from an endpoint the customer created (#230494, #264857, #272287) — the customer finishes the step at Stripe or re-enters the full key.
- Managed email stopped because the customer's own .env edit overwrote the managed email key (#210532).
- A third-party provider was down, a third-party key ran out of credit, or a third-party library in the app has a bug (#207399, #7963, #233392) — explain; the fix is with the provider or in the app.
- A system package the customer asks for is already in the base image (#27716).
- Feature requests: a platform-wide feature cannot be turned off per app (#222342, #240674), one exposed port per app (#261125), an account-wide spend cap, managed Postgres — explain current behaviour and record product feedback.
- Information requests: legal, privacy or hosting facts go to legal/privacy (#27125, #203554); there is no paid bug-bounty programme (#40484); "has X launched" goes to the product or business owner (#56254).

## Changed over time
- 2026-09-25 (integration-proxy v0.4.87): the support admin delete-suppression call also clears Resend's own list. Before that, an address suppressed at Resend needed retention on-call with the Resend account key (#262603 genuine on 2026-09-24; #274499 L2-resolvable on 2026-10-08).
- August to early September 2026: clearing a managed-email suppression row or an auto-disabled email app needed an engineering write (#222860, #229742, #248815). The support email admin API now does both.
- Older playbooks said only engineering can unlink a managed Stripe sandbox. The current playbook says the owner can use Payments tab Remove, and engineering unlinks only when Remove cannot be used.
- 2026-08-30: deploys before this date, or on non-v3 pipelines, did not refresh EMERGENT_LLM_KEY; a v3 redeploy now re-injects the owner's current key.

## Examples
- Genuine L3: #229578: the LiteLLM key had a lifetime budget; redeploy and credit did not help; engineering reset it.
- Genuine L3: #26236: the key was never created and top-up credits were deducted; engineering fixed the cause and refunded.
- Genuine L3: #270264: uploads returned 402 after the grace deadline; engineering cleared the grace period and credited the wallet.
- Genuine L3: #240007: MCP OAuth registration returned 400 that only connector-gateway logs showed.
- Genuine L3: #252846: list_jobs excludes jobs in a Project, found only in source.
- Genuine L3: #255655: an unclaimed managed Stripe sandbox overwrote the customer's webhook secret; no support or UI path removed it.
- Genuine L3: #228508: orphaned test webhooks on Emergent's sandbox Stripe account had to be deleted with Emergent's Stripe access.
- Genuine L3: #262603: the admin call cleared the suppression but Resend re-suppressed it within minutes (before 2026-09-25).
- Genuine L3: #271069: a leaked managed email key had to be revoked and reissued; support has no rotation path.
- Not L3: #38816: "failed to increase budget" was the discounted-plan funding cap.
- Not L3: #35213: the credits were in the Universal Key balance, which cannot move back.
- Not L3: #25464: storage 402 because the storage wallet was empty and credits were negative.
- Not L3: #250596: n8n Cloud is not an accepted MCP client; L2 answered within the hour.
- Not L3: #234916: the session expired at Allow; the tool list was populated.
- Not L3: #203831: an expired managed Stripe sandbox was fixed by unlinking it and linking a new one.
- Not L3: #246464: the customer pasted Stripe's masked key display.
- Not L3: #274499: the admin delete-suppression call clears the address, including at Resend.
- Not L3: #27125: a legal question about CDN terms needed no engineering fix.
