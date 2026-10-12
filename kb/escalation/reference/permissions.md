# Who can do what: L1, L2, L3 and engineering

**For people.** The theme-6a judge does not read the `reference/` folder. Issue files and `_principles.md` carry the rules the judge uses; this page is the background they rest on.

**Sources.**
- The 51-row permission table in `data/kb_research/notion_process_permissions.md` (Notion, read 2026-10-09). Row numbers below (N1–N51) are that table's.
- Corrections from what the eight case analyses observed in real escalations (`data/kb_research/cases_*.md`, sections D). Rows added from the cases are numbered C1, C2, …

**Read this first.**
- **A Trinity support level is not a capability tier.** Several reviewers are recorded as L2 in Trinity but hold L3 tooling. They run edge-config PATCHes, pod exec, credential rotation and production database writes. "An L2-level account did it" does not mean front-line L2 can.
- Most Notion pages are marked "unverified". Several of the richest are personal working copies, not policy.
- No Notion page maps the backend allow-lists (`SUPPORT_ADMIN_USER_IDS`, `JOB_DELETE_ADMIN_USER_IDS`, `SUPER_ADMIN_USER_IDS`, `REFUND_APPROVER_USER_IDS`) onto tiers.
- L1 capabilities are almost undocumented. They are implied only by playbooks labelled L1.

**How to read the table.**

| Value | Meaning |
|---|---|
| Yes | This tier does it. |
| Go-ahead | This tier does it, but the playbook says "Needs explicit go-ahead". |
| Guide | This tier tells the customer how to do it themselves. |
| No | This tier cannot. |
| ? | Notion does not say. |
| — | Not applicable. |

- **L3 / eng** covers both groups: support engineers at L3 with elevated tooling, and the owning engineering team's on-call.
- **Nobody in support** = Yes when no support tier, L3 included, can do it. Only a named non-support group can (platform engineering, billing-eng, an approver, legal, domains-ops), or no tool exists.
- **⚠** marks a row where practice in the cases differs from Notion.

---

## Databases and data recovery

| # | Capability | L1 | L2 | L3 / eng | Nobody in support | Practice vs Notion | Source |
|---|---|---|---|---|---|---|---|
| N1 | Production DB **read** via Redash (ds 10, ds 5) | ? | Yes | Yes | — | | [Support Guide](https://app.notion.com/p/22e3b3a7b061809890b2d140cd01e33b); [Deployments L3 Oncall Guide](https://app.notion.com/p/3de3b3a7b0618174abade1872c6afe54) |
| N2 | Production Postgres **write** | No | No | Eng, on request with justification | Yes | | [L3 KT](https://app.notion.com/p/35d3b3a7b06181199b2ef71c6818313f) |
| N3 | Write `user_subscriptions` / `users` rows (wrong plan, Pro row) | No | No | billing-eng only | Yes | ⚠ Support staff below L3 activated or granted Pro plans (#200309, #209314, #220287). A support API `/support/pro-plan/v1` exists, but no page says which tier may call it. | [11 · Credits, Billing](https://app.notion.com/p/3eb3b3a7b0618194ae29ee8fef7432c1) |
| N4 | Customer app Mongo **read** (deployer `run_mongo_query`) | ? | Yes (inferred) | Yes, read-only, with the customer's written consent | — | | [Deployments L3 Oncall Guide](https://app.notion.com/p/3de3b3a7b0618174abade1872c6afe54) |
| N5 | Any **write** to a customer's Mongo | No | Only through the runbooks in N6–N7 | Yes (on-call action) | — | ⚠ Repointing a live app to its old database binding is unsettled: Notion 08 says on-call; a customer can edit `MONGO_URL` under System keys (#251059); every repoint in the cases was done by L3 or a reviewer (#211788, #209939, #259440). | [Deployments L3 Oncall Guide](https://app.notion.com/p/3de3b3a7b0618174abade1872c6afe54) |
| N6 | **Mongo PITR restore**: additive, loss within 7 days, DB ≤ 2 GiB, ≤ 1M docs per collection | ? | Yes (L2 runbook) | Yes. Overwrites or > 2 GiB use a PITR clone to a temp cluster (go-ahead) | — | ⚠ Notion 08 labels PITR L3; the cases follow the L2 runbook (#233339, #238337). A preview diff that does not match the ticket goes straight to L3 (#272334). | [PITR L2 Runbook](https://app.notion.com/p/3be3b3a7b06181819be3e49d16e84607); [08 · Data Loss](https://app.notion.com/p/3eb3b3a7b06181068782d962b723a808) |
| N7 | **Mongo dump export** (signed link), multi-DB included | ? | Yes (L2 runbook) | Yes. Raising the size cap: deployer eng | — | ⚠ Seven escalations said no tool makes the archive; the fixer then used the same export API (#273153, #273603, #271139, #273152, #238782; #243739 and #206899 predate the runbook). Cap measured at 1 GiB on 2026-09-24 (#261282); the 08 page (2026-09-30) says 3 GiB. | [L2 Runbook: Mongo Dump Export](https://app.notion.com/p/3d03b3a7b061815da6a8daee70dc9dbb); [cap page](https://app.notion.com/p/3e73b3a7b06181b4b58add248854a3e2) |
| N8 | Managed Atlas **credential rotation** | No | No | Deployment Team executes | Yes | ⚠ A reviewer rotated one within minutes on 2026-10-07 (#273152); a tool may now exist. A deleted managed DB user (auth code 18) is different: support recreated it and redeployed (#242166, #206875). | [L3 Casebook](https://app.notion.com/p/3d13b3a7b061816e9ca6cba001948cdf) |
| N9 | Read v3 deployment **secret values** | No | No | No (KMS or eng) | Yes | | [L3 Casebook](https://app.notion.com/p/3d13b3a7b061816e9ca6cba001948cdf) |
| N11 | **Preview restore** from PVC snapshot, restic or S3 backup | No | No | Yes, in-runbook. Infra eng when the only snapshot is deleted | — | ⚠ `DATA_LOST` is not proof of loss: environments were recovered from S3 (#222110, #214425, #220387), and one was declared unrecoverable without an S3 check (#201750). | [231318](https://app.notion.com/p/3c23b3a7b061814daea4cbb097be5d96); [Escalation Matrix](https://app.notion.com/p/37c3b3a7b061816788cdcd01c1b345e3); [01 · Preview Pod](https://app.notion.com/p/3eb3b3a7b0618156a6b0e9a633305396) |
| C1 | Re-run a failed dedicated-DB migration | ? | No (Notion: "L2 does not start a second move") | Yes | — | ⚠ A reviewer re-ran `POST /api/v1/mongo/migration` (#272454); an L2 tried an undocumented manual-trigger runbook (#248737). No Notion page covers either. | `notion_rca_runbooks.md` §3.5 |

## Pods, agents and previews

| # | Capability | L1 | L2 | L3 / eng | Nobody in support | Practice vs Notion | Source |
|---|---|---|---|---|---|---|---|
| N12 | **Pod exec / kubectl** (agent and deployed pods) | No | No | Yes (go-ahead) | — | ⚠ Reviewers labelled L2 in Trinity edited files and ran commands inside pods (#230114, #255567). Treat as L3 work. | [Cookbook 225923](https://app.notion.com/p/3bc3b3a7b06181e29ed0d8a20dd0de87); [01 · Preview Pod](https://app.notion.com/p/3eb3b3a7b0618156a6b0e9a633305396) |
| N13 | Jumpbox SSH to production | No | No | On request with justification | — | Used by on-call for a registrar nameserver change (#274601) and, before the MCP tool existed, a crawler-cache purge (#57711). | [L3 KT](https://app.notion.com/p/35d3b3a7b06181199b2ef71c6818313f) |
| N14 | envcore `execute_tool` on customer pods | ? | ? | Yes (read-only exploration) | — | | [L3 KT](https://app.notion.com/p/35d3b3a7b06181199b2ef71c6818313f); [Toolbox & Access](https://app.notion.com/p/37c3b3a7b06181cd8a1ad9441a8a684f) |
| N15 | Wake a pod, clear a paused lock, terminate a ghost workflow | ? | ? | Yes, in-runbook. envcore/infra eng for PVC finalizers, VolumeBinding timeouts, genuine restic `DATA_LOST` | — | ⚠ Inconsistent: reviewers labelled L2 did these (#224836, #223071, #214425); an L2 cleared one preview within an hour (#31175); others needed L3 (#28440, #201870, #26903). | [Escalation Matrix](https://app.notion.com/p/37c3b3a7b061816788cdcd01c1b345e3) |
| C2 | Heartbeat PUT to reconcile a stale agent status | ? | ? (playbook, go-ahead) | Yes | — | ⚠ It returns 200 but does not move a job out of `stopped`; that case needed a production DB update (#226016). | [03 · Agent Hung](https://app.notion.com/p/3eb3b3a7b06181a298f2f22e0d918a13) |
| N16 | Preview machine-type increase | ? | ? | Yes (go-ahead) | — | | [01 · Preview Pod](https://app.notion.com/p/3eb3b3a7b0618156a6b0e9a633305396) |
| N38 | Agent and job internals: trajectory, sessions, cost, logs | ? | Yes | Yes | — | | [Support Guide](https://app.notion.com/p/22e3b3a7b061809890b2d140cd01e33b); [L3 KT](https://app.notion.com/p/35d3b3a7b06181199b2ef71c6818313f) |
| N39 | Stop a looping agent; goodwill credit for the loop | ? | Goodwill: Yes (L2 playbook) | Stop agent (go-ahead). Agent Engineering for every confirmed degenerate loop | — | | [07 · Doom Loops](https://app.notion.com/p/3eb3b3a7b061815590d9d92a75696ce5) |
| N40 | Replay a lost `ForkCompleted` event | ? | Yes | Yes | — | When no child job exists, send `fork_status: failed`, never success (#274470). | [272413](https://app.notion.com/p/3f13b3a7b061813b9b29ee55896ece70) |
| N36 | **GitHub**: pod git fixes, history rewrite | No | Push errors not explained by ignore rules | Yes (go-ahead pod git commands). GitHub integration eng for platform defects | — | ⚠ A missing `origin` remote is by design; one reviewer "restored" it (#233626), against Notion. Revoked authorization is not escalatable. | [09 · GitHub](https://app.notion.com/p/3eb3b3a7b06181b88167caf6b883d66b) |
| N37 | Retrieve the per-deploy source zip (read-only copy) | No | ? | Yes | — | Deployer eng if the zip is missing. | [09 · GitHub](https://app.notion.com/p/3eb3b3a7b06181b88167caf6b883d66b) |

## Deployment and production runtime

| # | Capability | L1 | L2 | L3 / eng | Nobody in support | Practice vs Notion | Source |
|---|---|---|---|---|---|---|---|
| N10 | Apply prod secrets without republish (`secret-redeploy`) | ? | Go-ahead (L2 playbook) | Yes | — | | [02 · Deployment Pod](https://app.notion.com/p/3eb3b3a7b06181de971fd4a2f0b4f609) |
| N17 | Redeploy with current template, `force_rebuild`, rollback to last-good image, KV pointer write + purge, dynamic-manifest fixes | No | Several L2 playbooks (go-ahead) | Yes, in-runbook. Deployer eng: base-image defects, CVE blocks, agentic-recovery deadlock | — | ⚠ `dynamic_manifest`: the Escalation Matrix calls it a deployer-eng trigger, yet support ran `dynamic_manifest_change` in 16 tickets, and reviewers labelled L2 flipped it (#241332, #52646). | [Escalation Matrix](https://app.notion.com/p/37c3b3a7b061816788cdcd01c1b345e3); [02 · Deployment Pod](https://app.notion.com/p/3eb3b3a7b06181de971fd4a2f0b4f609) |
| C3 | Set `replicas` (1–2) and `max_replicas` (≤ 2) on one v3 deployment | ? | Yes (k8s-override API) | Yes | — | ⚠ Changed over time: on 6 Jul this needed engineering (#47788). | [k8s-override page](https://app.notion.com/p/3c23b3a7b061819e9b27f0d511e1d617) |
| N18 | Customer self-serve deployment rollback and conversation rollback | Guide | Guide | Guide | — | | [07 · Doom Loops](https://app.notion.com/p/3eb3b3a7b061815590d9d92a75696ce5) |
| N19 | Mark a stuck deploy run failed (`deploy_runs_v3` DB update) | No | No | Go-ahead DB update | — | ⚠ The stale "Agent is fixing" panel was also cleared by the customer prompt "Redeploy this job using the deployer agent" (#208041, #208625). Not in Notion. | [02 · Deployment Pod](https://app.notion.com/p/3eb3b3a7b06181de971fd4a2f0b4f609) |
| C4 | Install a system package in production (`POST_INSTALL_COMMANDS`) | ? | Casebook: Yes for Chromium | Yes: GCS manifest edit plus `dynamic_manifest` flip | — | ⚠ The runbook labels it L3, while the casebook says support fixed Chromium directly. In the deployment sample a nodesource install through `POST_INSTALL_COMMANDS` silently failed (#207647), and every LibreOffice and Playwright fix needed L3 (#47031). | [272939 / 272832](https://app.notion.com/p/3f13b3a7b06181ff872fd17ce49c4691) |
| C5 | Read the Cloud Build log of a failed deploy | ? | Yes per runbook (`gcloud builds describe`) | Yes | — | ⚠ Support accounts were denied the deployer-build log, and the deployer can return an empty step error (#202838). | `notion_rca_runbooks.md` §3.1 |
| N50 | Internal → external app migration | ? | ? | Go-ahead (SOP) | — | | [L3 KT](https://app.notion.com/p/35d3b3a7b06181199b2ef71c6818313f) |
| N51 | Any **platform source-code change**: base image, Dockerfile template, `worker.js` cache logic, R2/KV publish steps | No | No | Platform eng only | Yes | | [Escalation Matrix](https://app.notion.com/p/37c3b3a7b061816788cdcd01c1b345e3) |

## Custom domains, DNS and edge

| # | Capability | L1 | L2 | L3 / eng | Nobody in support | Practice vs Notion | Source |
|---|---|---|---|---|---|---|---|
| N20 | Custom domain reconcile, verify, switch, delete orphan hostname, SSL reset | ? | Reconcile on the L2 SSL and www-cert playbooks (go-ahead) | Yes, in-runbook. Platform eng: worker caching, R2/KV publish gap, WAF/1010 bypass, zone upload cap, 1034 handshake | — | ⚠ The same reconcile sits on an L3-labelled playbook; the cases support L2 (#31439). An L2 ran the deployer domain switch, which the Matrix calls L3 (#229942). | [04 · Cloudflare](https://app.notion.com/p/3eb3b3a7b06181849d5bc6d7664e91f0); [Escalation Matrix](https://app.notion.com/p/37c3b3a7b061816788cdcd01c1b345e3) |
| C6 | **Edge-config PATCH**: path redirects, 404 mode, HTML cache, visitor geo headers | No | No | Yes, in-runbook (go-ahead) | — | ⚠ Run routinely by reviewers labelled L2 (#227287, #239570, #218283, #212277, #267964). Each section is replaced whole, not appended (#227287). | [05 · Edge & SEO](https://app.notion.com/p/3eb3b3a7b061811f8f17d2620c8e0a7e) |
| C7 | Security headers through the `_headers.json` allowlist | Guide | Guide | — | — | ⚠ Self-serve since about early July 2026 (#42699); notes claiming no self-serve path were refuted (#54636). COOP/COEP/CORP and removing a wildcard ACAO are outside the allowlist (product gap). In May and early June the worker had no header support (#8914, #6886). | [05 · Edge & SEO](https://app.notion.com/p/3eb3b3a7b061811f8f17d2620c8e0a7e) |
| C8 | Search-engine crawling on/off | Guide | Guide (Domain-tab toggle) | Yes (crawler PATCH) | — | ⚠ The PATCH is the same switch as the Domain-tab "Enable Search Engine Crawling and Optimisation"; L2 notes said it was not exposed (#211029, #238919). | [05 · Edge & SEO](https://app.notion.com/p/3eb3b3a7b061811f8f17d2620c8e0a7e) |
| C9 | Crawler-cache purge (`purge_crawler_cache`, go-ahead) | ? | Support purged in August (#223643, #224198) | Yes | — | ⚠ On 15 Jul no endpoint existed and the purge needed the jumpbox (#57711). | [05 · Edge & SEO](https://app.notion.com/p/3eb3b3a7b061811f8f17d2620c8e0a7e) |
| N49 | Add a bot token to the crawler KV list | No | No | On-call write | Yes | | [Deployments L3 Oncall Guide](https://app.notion.com/p/3de3b3a7b0618174abade1872c6afe54) |
| N21 | **TXT / MX records** on Emergent-bought domains (internal DNS API) | ? | Yes | Yes. CNAME add/delete: on-call from the prod deployer pod | — | ⚠ The date L2 gained TXT/MX is uncertain: the L3 → 0 page (11 Jul) says L2-enable; a note on 14 Jul said the API had no TXT/MX (#198140). From September TXT/MX writes work and CNAME is refused (#256207, #265757, #269203). | [Deployments L3 Oncall Guide](https://app.notion.com/p/3de3b3a7b0618174abade1872c6afe54); [06 · DNS](https://app.notion.com/p/3eb3b3a7b061816ea8e8ef0cb310d48c) |
| N22 | **Domain transfer-out** (EPP code + DNS snapshot) | ? | Yes, not an escalation | Yes. Escalate only `order_id_mismatch`, `transfer_unlock_unverified`, `registrar_error`; clientHold or IONOS orders go to domains-ops | — | ⚠ A Cloudflare Registrar transfer also needed a nameserver change, which the playbook does not cover (#274601). | [273752](https://app.notion.com/p/3f23b3a7b06181b8847fe726c0644af1); [06 · DNS](https://app.notion.com/p/3eb3b3a7b061816ea8e8ef0cb310d48c) |
| N23 | **Nameserver change** on an Emergent-bought domain | No | No | On-call, through the jumpbox, after approval | Yes (policy: domains-ops) | ⚠ Notion says no operation exists; on-call ran one (#274601). | [06 · DNS](https://app.notion.com/p/3eb3b3a7b061816ea8e8ef0cb310d48c) |
| C10 | Delete an Emergent-bought domain at the registrar | No | No | On-call with the registrar (#230400) | — | No Notion playbook. The domain record is not updated after the deletion. | — |
| C11 | Re-pin an app to the Turkey domain set | ? | Yes (support action) | Yes | — | | [268868](https://app.notion.com/p/3ed3b3a7b06181068a90d6544b5c3669) |

## Mobile builds

| # | Capability | L1 | L2 | L3 / eng | Nobody in support | Practice vs Notion | Source |
|---|---|---|---|---|---|---|---|
| N24 | Regenerate distribution credentials, redeploy-before-build, bundle-ID fixes, iOS identity and `clear-asc-credentials` calls | ? | Some L2 playbooks (lockfile, gradle, white screen, bundle ID greyed out) | Yes, in-runbook. Expo/mobile eng: Apple capability toggles on `app.emergent.*`, the macrunner 2FA bug, Mac VM access | — | ⚠ Notion makes `clear-asc-credentials` L3-only; L2 agents ran it (#32211, #217435, #29083). It can revoke the customer's distribution certificate (#217435). | [Escalation Matrix](https://app.notion.com/p/37c3b3a7b061816788cdcd01c1b345e3); [10 · Mobile](https://app.notion.com/p/3eb3b3a7b06181f2abeadcdb557b4e5d) |
| C12 | Read EAS and pipeline build logs (`get_eas_build_logs`, `fetch_pipeline_logs`) | ? | Yes (read-only) | Yes | — | ⚠ One escalation claimed only the Expo team can read EAS logs (#22395). | [10 · Mobile](https://app.notion.com/p/3eb3b3a7b06181f2abeadcdb557b4e5d) |
| C13 | Expo partner-account writes: provisioning, session refresh, the versionCode counter | No | No | Eng | Yes | L2 confirmed it has no partner-API write access (#235880). Counter divergence needed eng (#241391, #255906, #272013). | [10 · Mobile](https://app.notion.com/p/3eb3b3a7b06181f2abeadcdb557b4e5d) |
| N25 | Android keystore repoint (prod DB write) | No | No | Deployer eng | Yes | ⚠ In practice L3 exported the upload certificate of the current key and the customer reset the Play upload key (#10341, #3043, #7705). | [10 · Mobile](https://app.notion.com/p/3eb3b3a7b06181f2abeadcdb557b4e5d) |

## Accounts, security and legal

| # | Capability | L1 | L2 | L3 / eng | Nobody in support | Practice vs Notion | Source |
|---|---|---|---|---|---|---|---|
| N26 | Admin View (app.emergent.sh) | ? | Yes | Yes. Superadmin: senior on-call only | — | | [Support Guide](https://app.notion.com/p/22e3b3a7b061809890b2d140cd01e33b); [L3 KT](https://app.notion.com/p/35d3b3a7b06181199b2ef71c6818313f) |
| N30 | Job ownership transfer; re-run the support-tool Job Transfer for a leftover piece | ? | Go-ahead (L1/L2 playbooks) | Yes. Merging subscriptions, credits or orgs: platform/accounts eng | — | Changed over time: in August L3 corrected ownership records by hand (#230629). | [16 · Account](https://app.notion.com/p/3eb3b3a7b06181b9a868de37823124a2) |
| N31 | Account deletion | Guide | — | Hard delete (go-ahead, verified owner, written reason). Formal GDPR: legal/privacy | — | ⚠ Deleting PostHog analytics data has no owner (#273612). | [16 · Account](https://app.notion.com/p/3eb3b3a7b06181b9a868de37823124a2) |
| N32 | Login email change | Guide | — | Move jobs (go-ahead) | — | | [16 · Account](https://app.notion.com/p/3eb3b3a7b06181b9a868de37823124a2) |
| N33 | Enterprise SSO identity merge | No | No | Platform/enterprise-auth eng | Yes | Emergent does not merge other accounts (#44928 was the SSO case). | [16 · Account](https://app.notion.com/p/3eb3b3a7b06181b9a868de37823124a2) |
| N34 | Delete jobs or projects | No | No | Allow-list holders only (L3 support got 403) | Yes | | [266603](https://app.notion.com/p/3ea3b3a7b06181c7a622e4045994ecb0) |
| N35 | Unarchive a job | No | No | Engineering DB update | Yes | | [266603](https://app.notion.com/p/3ea3b3a7b06181c7a622e4045994ecb0) |
| C14 | Release a deleted account's email for re-registration | No | No | Conversion Team | Yes | No support tool (#273371). | — |
| C15 | Enable a gated feature for one account | No | No | Conversion Team | Yes | No support tool documented (#270401). | — |
| N45 | Turn off the platform private-access wall | ? | Yes, with the customer's written request | Yes | — | ⚠ Notes called it internal-only (#268882, #232672); L2-level accounts turned it off (#232672, #263590). If the wall itself is broken, a deployer release is needed (#268147). | [268882](https://app.notion.com/p/3ec3b3a7b06181d4be43f4a81cef4ab5) |
| N46 | Phishing verdict to clear a blocked redeploy | No | No | T&S or eng | Yes | ⚠ A LEGITIMATE re-classification did not clear the flag; a DB write was needed (#239239). | [17 · T&S](https://app.notion.com/p/3eb3b3a7b06181889352d15a7da7783a) |
| N47 | Takedown or unsuspend an app | No | No | Go-ahead (L3 playbook) | — | | [17 · T&S](https://app.notion.com/p/3eb3b3a7b06181889352d15a7da7783a) |
| N48 | DPA, SOC 2, security questionnaires | ? | L2 playbook: route bespoke items to privacy@ | — | Yes (legal/privacy) | ⚠ In Trinity these went to L3 engineering teams (#228598, #236546, #229982). Trinity has no privacy team. | [17 · T&S](https://app.notion.com/p/3eb3b3a7b06181889352d15a7da7783a) |

## Billing, credits and integrations

| # | Capability | L1 | L2 | L3 / eng | Nobody in support | Practice vs Notion | Source |
|---|---|---|---|---|---|---|---|
| N27 | Support ECU credit grant (`/support/credit/v1`) | ? | Go-ahead, within the LTV-band cap | Same | Above the cap: approver group | ⚠ Grants above the 500 ECU per-call limit and every band appear with no recorded approver (#266431, #200309, #235448). One grant was a direct balance update outside credit history (#220247). | [11 · Credits, Billing](https://app.notion.com/p/3eb3b3a7b0618194ae29ee8fef7432c1); [07 · Doom Loops](https://app.notion.com/p/3eb3b3a7b061815590d9d92a75696ce5) |
| N28 | Dollar refund (`/support/refund/request/v1`) | ? | Request; auto-approved below the threshold (default 201 USD-equivalent) | Same | Above the threshold: refund approver. FAILED refunds: billing-eng. Chargebacks: payments | | [11 · Credits, Billing](https://app.notion.com/p/3eb3b3a7b0618194ae29ee8fef7432c1) |
| N29 | Credit transfer between accounts | No | Support-admins only | Support-admins, by exception | — | | [11 · Credits, Billing](https://app.notion.com/p/3eb3b3a7b0618194ae29ee8fef7432c1) |
| C16 | Immediate cancel, or annual → monthly switch | No (#25933) | Playbook labelled L2 | Unlimited-access admins | — | ⚠ The playbook's level label conflicts with its own permission note. | [11 · Credits, Billing](https://app.notion.com/p/3eb3b3a7b0618194ae29ee8fef7432c1) |
| N41 | Universal Key: set `is_paid`, raise budget, clear deficit, grace reset, re-provision storage key | No | Two L2 playbooks (cannot add balance; daily spend limit) | Eng | Yes | ⚠ The lifetime-cap failure (`budget_duration` NULL) is not in Notion and needed an eng config fix (#229578, #45652). A Universal Key balance cannot be moved back into credits (#35213). | [13 · Universal Key](https://app.notion.com/p/3eb3b3a7b0618174acf8c9388645a884) |
| N42 | Object-storage delete, customers-code bucket write, customer-asset deletion | No | No | retention-, deployments- or sandbox-oncall | Yes | Routed inconsistently between teams (#57937, #222741, #253202). | [Ticket Casebook](https://app.notion.com/p/3bf3b3a7b061813c9da3e78f05bf415a); [17 · T&S](https://app.notion.com/p/3eb3b3a7b06181889352d15a7da7783a) |
| N43 | Integration-proxy DB row deletes | No | No | `@retention-oncall` | Yes | ⚠ A reviewer labelled L2 ran an integration-proxy DELETE (#255655). | [Ticket Casebook](https://app.notion.com/p/3bf3b3a7b061813c9da3e78f05bf415a) |
| N44 | Clear managed-email suppression (support admin API) | ? | Yes | Yes | — | ⚠ Changed over time: since 2026-09-25 the admin DELETE also clears the provider list (#274499, L2 work). Before that it needed L3 (#229742, #248815, #262603). Still escalate a complaint, a provider-step DELETE error, a record-deletion request, or `phishing_disabled` (T&S). | [Archetype — managed email 422](https://app.notion.com/p/3f33b3a7b0618185be64f593e5d8fee1) |
| C17 | Unlink a managed Stripe sandbox | ? | Guide (Payments tab Remove, newer playbook) | Integration-proxy operator action | — | ⚠ Unsettled: a customer unlink worked (#203831, #224509), but platform-side unlinks were needed in #228508 and #219646. | [14 · Integrations](https://app.notion.com/p/3eb3b3a7b0618101b0ccdbe08d8f28d9) |
