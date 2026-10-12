# Emergent accounts, login, deletion, security and legal requests

## Covers
- Cannot log in or sign up to Emergent: "Invalid payload sent to hook", "invalid auth code", password reset not arriving, blank page after login, "Unable to exchange external code" / server_error on Sign in with Apple, Google sign-in loop
- OTP or email codes not received, email verification link fails, phone login "too many verification code requests"
- Google or Apple sign-in account sent through "Forgot password" or password reset
- Account or app blocked: phishing flag, "Under review", redeploy blocked, app moved to emergentagent.host, is_phishing, AI assistant refuses content (policy), feature gated (e.g. Video not available)
- One person with two accounts or two Apple IDs, empty account after login, "it's my account" but the email does not match, enterprise SSO "account migration in progress" / 409, identity merge
- Change login email, release the email of a deleted account so it can sign up again
- Projects missing from Home, project switcher fails, "Unauthorized access" on publish after moving an app into a project
- Delete my account, GDPR Art. 17 erasure, immediate deletion, "Job delete privileges required" 403, "Please contact support to delete your project", super admin, delete a project or org, restore a deleted or archived job
- GDPR / DPA / sub-processor / cookie questions, PostHog or analytics data deletion, session-recording retention, `__emg_vid` / `__emg_sid` cookies
- Hard-delete files (secrets, payslips, PII) from the public customer-assets CDN, chat uploads or Trinity attachment links
- Platform private-access wall (Auth Wall) on: white screen or private login page for every visitor, teammates blocked by the allow-list
- Security reports and vulnerabilities, bug bounty, missing security headers, `.env` in the production image, leaked managed email key (`ek_`, EMERGENT_EMAIL_KEY), Emergent staff sent data to the wrong customer
- Legal tickets: police report, solicitor, regulator, formal notice, Real-Legal / `real_legal_escalation`
- Compliance questionnaires, signed security attestations, encryption-at-rest letters

## Needs L3 when
- The same Apple, Google or SSO sign-in error is reported by more than one user, or matches an open platform-bug thread — the fix is in Supabase or provider configuration (platform auth on-call).
- A password-reset or verification email is broken for every user, or a one-time link was consumed by a mail scanner and support must mark the email verified — platform code fix or a user-record write.
- Every login and every sign-up for one email returns "Invalid payload sent to hook" and the email belongs to a deleted account — no support tool releases a deleted account's identity.
- An enterprise SSO user is locked out and ds 10 shows an old non-SSO user row plus a new SSO row for the same email — the Supabase identity merge is "Always → platform/enterprise-auth eng".
- Phone OTP login returns "too many codes requested" before any code is delivered, on repeated tries — rate limits are platform configuration.
- Project loading or project switching returns a server error for several users at once — platform code bug.
- A phishing flag is still on after a LEGITIMATE (CLEAN) review and after the review window, or the app is a false positive — phishing verdicts are T&S or engineering only; clearing needs a DB or KV write.
- A gated product feature must be enabled for one account — no support tool for feature gating.
- A customer wants an immediate hard deletion of their account (waiving the grace period) or files a formal GDPR / CCPA erasure request — hard delete is an L3 go-ahead action, and formal requests go to Legal/privacy.
- A project or org must be deleted, or the support tool returns 403 "Job delete privileges required" or asks for super admin — needs the job-delete or super-admin allow-list.
- A deleted or archived job must be restored — there is no unarchive endpoint (engineering DB update).
- A file with secrets or personal data is still served from the customer-assets CDN, a chat upload or a Trinity attachment link, or a deleted project's preview is still public — support holds read-only storage access and the product delete is soft-only; removal needs a storage delete plus CDN invalidation.
- Files must be removed inside a customer workspace, or workspace git history must be rewritten — needs pod access.
- Data must be deleted from Emergent's own PostHog project, or the customer needs written answers about retention of data in Emergent's own analytics — no support tier has access or authority.
- A managed key (EMERGENT_EMAIL_KEY, `ek_`) leaked and must be revoked and reissued — support has no rotation path.
- A security header, CSP or CORS header is dropped or overwritten by the Emergent edge or preview worker while the app's own config is correct, `.env` files ship inside production images, or a platform tag loads a third-party script — platform source change.
- A security researcher reports a concrete vulnerability in Emergent itself (signup bypass, credit bypass, preview wrapper finding) — validation needs security engineering.
- A security incident in a customer app needs platform-side evidence preservation — support has no tool for this.
- Emergent staff sent one customer's data to another customer — needs security and privacy owners.
- The ticket contains police, solicitor, regulator, formal-notice or press-threat language — Legal owns the reply; keep it at L3 with the Real-Legal tag so it does not auto-close.
- The customer asks for signed security-control attestations or a bespoke security questionnaire — L2 cannot sign or commit for the platform.
- The customer needs the `__emg_*` platform cookies turned off on their site — only engineering can apply the hosting-layer opt-out.
- The private-access wall must keep working but its login does not complete, or the Manage → Security allow-list panel is missing — platform code or feature-flag fix.

## L2 can resolve when
- The account was created with Google, Apple or phone and the customer is using "Forgot password" or a password reset — read the provider in user_metadata on ds 10 and tell them to sign in with that provider; phone accounts sign in from the emergent.sh landing page.
- The sign-in code is delivered but the customer cannot find it — wait 60 seconds, check spam and old email threads, request one new code, try a private window.
- The person has two accounts or two Apple IDs, or lands in an empty account — exact-match every user_id by email and phone, find the one that owns jobs and payments, and transfer jobs with go-ahead (support Job Transfer).
- Projects are missing from Home but exist — the customer switches project with the selector or uses Move to Project.
- Publishing gives "Unauthorized access", or a feature is missing, after an app was moved into a project or another account — re-run the support-tool Job Transfer (a job transfer left a piece on the old owner).
- The customer wants to change their login email — not possible; for a password login use Forgot password on the same email, otherwise create a new account and transfer verified jobs with go-ahead.
- The customer asks to delete their account — self-serve in Account Settings, erased after the grace period and revocable until then; for "was it deleted?" read account_deletion_requests on ds 10.
- The customer wants individual jobs removed — they delete the job from its ⋯ menu; only project or org removal needs L3.
- The platform private-access wall is on and the customer asks in writing for it off, or teammates are blocked by its allow-list — support turns the wall off with the internal auth-wall call and checks both URLs return 200.
- In-app password-reset or login emails from managed email fail with 422, a suppressed address or an auto-disabled app — run the email admin diagnose and clear the named gate with the support admin API.
- The customer asks what the analytics script, cookies or sub-processors do, or asks for the DPA or GDPR facts — answer from app.emergent.sh/dpa, /subprocessors and the Trust Center; PostHog in the app is removed by deleting posthog.init from index.html.
- The customer asks to turn off a platform-wide feature that has no per-app setting (e.g. the Cloudflare analytics beacon on the shared domain) — explain it, offer a custom domain where that removes it, and record the feature request.
- A person asks about a bug bounty before giving any finding — reply that there is no paid programme and ask for the finding.
- A scanner reports missing security headers on the customer's own app — the customer adds them in the app (`_headers.json` or nginx) and redeploys.
- A redeploy shows "Under review" (wait) or "Move available" (customer clicks Re-deploy).

## L2 must try first
1. Prove ownership with the Support code or verify-ownership/v1, never with the sender's email alone.
2. On ds 10, exact-match users by email and by phone; list every user_id and which one owns jobs, payments and credits.
3. Read user_metadata.provider, is_blocked and account_deletion_requests. Do not treat users.active=false as a block.
4. Get the exact error string, a screenshot, browser and device, and whether a private window works.
5. Search #build-success and #platform-bug for the same error string to see whether other users are affected.
6. For deletion, name exactly what is to be deleted (account, job, project or org), try the support-tool action, and record the exact error.
7. For an exposed file, HEAD the URL (200 means still live), name the store and exact object keys, record the exposure window and credential names (never values), and tell the customer to rotate the keys.
8. For a phishing block, read the latest deploy_runs_v3 phishing_class and the deploy latest endpoint, and record how long the flag has been on.
9. For an app showing a private login page, read auth_metadata on ds 5 and make one request without cookies.
10. For legal or regulator language, set the Real-Legal tag, take one owner, stop Overwatch auto-replies, keep the ticket open and preserve evidence.
11. For compliance questions, answer everything the DPA, sub-processors page and Trust Center cover, and list only what remains.

## Not a fault
- users.active=false on the account — this is the email-confirm flag and is false for most users; it is not a block.
- The account deletion the customer asks about has already completed or is still scheduled — tell them the status from account_deletion_requests.
- Emails come from an "unknown copy" of the app that is really the customer's own old preview or fork — tell them which job it is and to rotate the credentials.
- The customer's own `.env` edit overwrote the managed email key — the app uses whatever key they set; restore the managed key or keep their own provider.
- The AI assistant refuses a request for policy reasons — this is the acceptable-use policy, not a stuck account flag; start a new chat for allowed work.
- Review confirmed the app is malicious and the block stands — this is policy; no engineering fix, and classifier details are not shared.
- Members cannot invite others to a project — role gating is by design; the Owner invites.
- Logouts in an app without the private-access wall — this is the app's own authentication, fixed in the app.

## Changed over time
- By 2026-08-22: engineering offered a hosting-layer opt-out for the `__emg_*` cookies. Before that (8 Aug) there was no per-app mechanism, and the right answer was an explanation and a feature request.
- 2026-09-25: support clears managed-email suppressions directly with the admin API, including Resend's list, and re-enables auto-disabled apps. Before that, deleting a suppression row or clearing an auto-disable needed L3 (August and early September tickets).

## Examples
- Genuine L3: #38337: Sign in with Apple "Unable to exchange external code" was a platform issue affecting all Apple logins.
- Genuine L3: #273371: every login and sign-up failed with "Invalid payload sent to hook" because the email was bound to a deleted account.
- Genuine L3: #44928: an enterprise SSO login was fixed only by an identity merge.
- Genuine L3: #54790: phone OTP hit a rate limit before any code was sent; engineering changed it.
- Genuine L3: #239239: a phishing flag stayed RISKY after a CLEAN re-classification; clearing it needed a DB write.
- Genuine L3: #39082: an immediate GDPR account erasure needed a hard delete.
- Genuine L3: #266603: project and org deletion returned 403 "Job delete privileges required".
- Genuine L3: #20943: a deleted job was restored; there is no unarchive endpoint.
- Genuine L3: #253202: payslip PDFs on the public assets CDN needed a hard delete and CDN invalidation.
- Genuine L3: #273612: deleting a site's data from Emergent's own PostHog project needed access no support tier has.
- Genuine L3: #271069: a leaked managed email key had to be revoked and reissued.
- Genuine L3: #257346: `.env` files shipped inside production image layers; deployer code change.
- Genuine L3: #202471: a police-report threat with the Real-Legal tag; Legal owns the reply.
- Genuine L3: #268147: the private-access wall login was not served on two clusters; fixed in a deployer release.
- Not L3: #41050: the account used Sign in with Apple, so password-reset emails could never work.
- Not L3: #238762: the sign-in code was delivered but threaded into an old email.
- Not L3: #208425: the customer had two Google accounts and was signing in to the empty one.
- Not L3: #271851: publishing failed after a project move; re-running Job Transfer fixes it.
- Not L3: #105025: ds 10 already showed the account deletion had completed.
- Not L3: #268882: the platform private-access wall was on; support turns it off directly.
- Not L3: #215701: GDPR questions about the analytics script were answerable from published documents.
- Not L3: #261802: the "unknown instance" sending emails was the customer's own old previews.
- Not L3: #52734: a bug-bounty enquiry with no finding attached.
