# Mobile app builds (Expo, iOS, Android, TestFlight, Play Store, App Store)

## Covers
- iOS build failing or Android build failing: "Run gradlew" failed, Gradle "unknown error", "Install pods" failed, "No lockfile found", build fails in seconds with no logs, "Failed to start Android build", ErrDeploymentNotFound, "bash: not found", "exec format error", EAS build credits used up
- "Entity not authorized: AppEntity" at eas project:init, stuck at "Initializing EAS project", or at the eas-update step
- Google Play rejects the AAB: versionCode already used or below the live version, "doesn't allow existing users to upgrade", "android.versionCode field in app config is ignored when version source is set to remote", EAS remote versioning, Expo Partner API, version counter
- Play "signed with the wrong key", upload key SHA-1 mismatch, upload key reset, request for the keystore, its fingerprint or the upload certificate (PEM)
- Build green but not in TestFlight or App Store Connect, "no space left on device" on the Mac VM, "Apple Transporter error", altool error, App Store Connect API key revoked, HTTP 401 from Apple
- Apple store rejection: ITMS-90035, ITMS-90034, invalid signature, missing Info.plist key, Development or Ad-Hoc profile
- Apple sign-in in the build wizard: 6-digit code never arrives, wrong Apple team, "App name already taken", "bundle ID already registered to a different team", distribution certificate revoked, clear-asc-credentials
- Bundle identifier invalid or greyed out, build lands in the wrong App Store app, package name wrong, google-services.json package mismatch
- Build or installed app missing the latest changes, old icon or old version, builds come from the last deployed snapshot, OTA / EAS Update not updating
- Deploy fails at the eas-update Cloud Build step, TerminalCloudBuildFailure, "No app.json, app.config.js, or app.config.ts found" after a mobile-to-web conversion
- Mobile preview or Expo Go not loading, QR code, tunnel, Metro "ENOSPC: System limit for number of file watchers"
- White screen or crash on the installed APK, AAB or IPA while it works in preview or Expo Go; Sign in with Apple error 1000; push notifications not delivered

## Needs L3 when
- The log shows "Entity not authorized" at eas project:init or eas-update, usually after an org or workspace move, an owner change, a fork, Replace or an Expo account migration — clearing or relinking the stored Expo project ID is an L3-only write.
- Play rejects the AAB because its versionCode is at or below the live versionCode, and the build log says the app config versionCode is ignored because the version source is remote — re-seeding the EAS remote counter is an Expo Partner API write; L2 partner tools are read-only.
- The versionCode counter differs between the pool and the partner Expo project after an account or project migration — only engineering can set the counter on the partner project.
- The deployer refuses the build before any pipeline run exists (no Cloud Build ID, ErrDeploymentNotFound) although the app has a green deploy — deployer DB linkage repair, a prod write.
- The mobile build config is still tied to an older or parent job after a migration, fork or Replace, so the build screen shows first-build defaults — prod DB re-key.
- The build runs on the wrong template or image ("bash: not found" at an early step), or an app converted from mobile to web still runs the eas-update step — the template field change is a prod DB write.
- The failure comes from the platform's own build pipeline: "exec format error" on Fork plus Replace, a build template that force-pins a dependency, an eas-update template bug, Emergent's shared EAS account out of build credits, or the same error across many unrelated apps in the same hour — platform code or config fix.
- A deploy fails at the eas-update Cloud Build step and the step's error text is not visible in the logs support can read — reading the raw Cloud Build log needs engineering access (the fix can still turn out to be customer-side).
- The customer wants Emergent to load their own keystore, or needs the fingerprint, upload certificate (PEM) or key history of the Emergent-held keystore for a Play upload-key reset, or the keystore must be repointed — keystore and KMS access are deployer-only.
- The stored package name or bundle ID is wrong in the build config and must be changed on the platform side, or every bundle ID is refused as "already registered to a different team" — DB write or Apple account-link repair.
- The raw TestFlight upload log shows a Mac VM error such as "no space left on device", or Apple's rejection reason exists only in the Mac VM upload log — the Mac VM is backend-team-only.
- The stored App Store Connect API key is revoked or Apple returns HTTP 401, or the stored submit credentials are stale and the upload must be re-run — credential-store write and TestFlight retry are L3-only.
- Apple rejects the binary with ITMS-90035 or ITMS-90034 again after a fresh Deploy and rebuild, or the stored profile is Development or Ad-Hoc — minting Distribution credentials and overwriting the stored set is a mobile-builds engineering action.
- The stored Apple credentials must be cleared or regenerated (clear-asc-credentials), for example after the customer revoked the distribution certificate — Notion lists this endpoint as an L3-only write that needs explicit go-ahead.
- The Apple 6-digit code still never arrives after the 15–30 minute wait and a single fresh sign-in, Apple shows no password error, and the same Apple account receives codes in Apple's own tools — known macrunner 2FA bug owned by Expo engineering.
- The Expo preview cannot start for a platform reason: storage stuck Pending, Metro "ENOSPC" file-watcher limit, restore says "No fresh backups available", or a 502 persists after the documented environment restart while Metro runs — kubectl, node or backup access.
- Config that is present in the deployed snapshot is missing from the built app — Expo Team (Notion playbook rule).

## L2 can resolve when
- The real error line points at the customer's project: google-services.json registered for another package, Reanimated or react-native-worklets mismatch, no lockfile, Firebase pods, lint "ExtraTranslation" on locale keys, the customer's own build script, or an app dependency — give the mobile playbook agent prompt, then Deploy, then rebuild.
- The bundle identifier or package name has invalid characters, or a checked-in ios/ folder or app.json still holds the old bundle ID so the build lands in the wrong app — playbook "Bundle ID greyed out": one value, letters and digits per segment, Deploy, then build.
- The build or installed app lacks the latest changes or shows the old icon — builds use the last deployed snapshot: Deploy, wait for green, Generate build, install the new build (JS-only changes: close and reopen the app).
- The build was reported failed or stuck but the artifact exists or the build is already in TestFlight — check the TestFlight status API, the build list and a customer App Store Connect screenshot, then tell the customer.
- The app was never deployed ("no successful deploy found") — tell the customer to Deploy, wait for green, then generate the build.
- Sign in with Apple fails with error 1000 — add usesAppleSignIn under expo.ios, Deploy, rebuild, test the new TestFlight build.
- Push notifications are not delivered — the customer uploads the iOS .p8 or Android FCM JSON in the build flow, Deploys and installs a new build.
- The installed app shows a white screen or crashes because of app code, a dependency, a missing Maps key or a backend URL not read from EXPO_PUBLIC_BACKEND_URL — agent prompt, Deploy, rebuild.
- Expo Go opens the device-auth page, the tunnel is stuck, or a preview config error stops the dev server — Expo Go playbook steps or one environment restart.
- The Apple version is rejected or an unneeded capability blocks signing — fix expo.version (at most three numbers) or remove the capability, Deploy, rebuild.
- The mobile build toggle or publishing screen is missing after a job transfer — re-run the support-tool Job Transfer.

## L2 must try first
1. Resolve the job ID and the build owner's user ID from the job, not from the ticket sender, and note the platform and the time of the attempt.
2. Read the real failing step and its exact error with get_eas_build_logs (owner user ID), fetch_pipeline_logs with step logs, fetch_cloudbuild_logs, or the iOS and Android logs API. EAS logs are readable with L2 tools.
3. Do not rely on green signals: ios_testflight success, the stored testflight_error ("Apple Transporter error" is a canned message), EAS exit code 0, or a certificate expiry date in the future.
4. Confirm that a green Deploy came after the customer's last change, and that the failing build used it.
5. Match the error to the mobile playbook and apply the L1 or L2 fix; if escalating anyway, say why that fix was not enough.
6. Retry once when the failure looks transient, and check whether the build already succeeded or reached TestFlight.
7. For a Play rejection, record Play's expected SHA-1 or highest live versionCode and the rejected AAB's value, and ask whether that AAB was built outside Emergent.
8. Run get_expo_partner_account and get_mobile_build_config, and record pool or partner account, both Expo project IDs and the version source.
9. Check for a recent fork, Replace, workspace or org move, account migration or job transfer.
10. For Apple sign-in problems, have the customer wait 15–30 minutes and request the code once, check whether Apple refused the password before 2FA, and ask about multiple Apple teams, deleted certificates and revoked API keys.
11. For a preview problem, wake or restart the environment once and read the Metro log before escalating.

## Not a fault
- The AAB that Play rejected was built outside Emergent (the customer's own EAS organisation or "Build from GitHub") and the Emergent-built AAB matches Play's key — tell the customer to upload the Emergent-built AAB or do a Play upload-key reset.
- Apple refuses the sign-in before 2FA because the Apple password is wrong or old — the customer signs in with the current primary Apple password.
- The Apple ID belongs to several teams and the wrong team was chosen — the customer selects the team that owns the app.
- The Gradle log shows the customer's own native module or locale files failing to compile — the customer or agent fixes the project code.
- The preview is sleeping or archived after idle time, or the sandbox is healthy — resume it; this is normal behaviour.
- The customer asks whether OTA updates, automated Play submission or a custom domain on an Expo app are supported — answer as a product question (custom domains apply to web deployments only).
- The build issue already cleared before the escalation, for example a stale web bundle that refreshed — tell the customer it is resolved.

## Changed over time
- June to August 2026: L2-labelled agents ran clear-asc-credentials themselves (#29083, #32211, #217435). The current Notion rule lists it as an L3-only write with explicit go-ahead; this file follows Notion.
- August 2026: a missing mobile build toggle after a job transfer was fixed by L3 correcting ownership records (#230629). The current casebook says support re-runs the support-tool Job Transfer.

## Examples
- Genuine L3: #32565: eas project:init failed with "Entity not authorized" on a stale stored Expo project ID; engineering cleared it.
- Genuine L3: #241391: Play rejected the AAB because the EAS remote versionCode counter was below the live value; the counter was re-seeded through the Partner account.
- Genuine L3: #255906: the versionCode counter split between pool and partner Expo projects after migration; engineering seeded the partner counter.
- Genuine L3: #27222: the TestFlight upload failed with "no space left on device" on the Mac VM.
- Genuine L3: #19488: the stored App Store Connect API key returned HTTP 401 and had to be rotated in the credential store.
- Genuine L3: #10341: Play upload-key mismatch; engineering exported the certificate of Emergent's current key for a Play upload-key reset.
- Genuine L3: #42246: the Android build config stayed tied to the parent job after a migration and needed a DB re-key.
- Genuine L3: #32211: the Apple code never arrived after a fresh sign-in; this matched the macrunner 2FA bug.
- Not L3: #22395: Gradle failed on a google-services.json registered for another package; EAS logs were readable with L2 tools.
- Not L3: #16592: redeploys failed on underscores and hyphens in the bundle identifier; an agent prompt fixed app.json.
- Not L3: #25510: the iOS build showed the old icon because the change was never deployed; builds use the last deployed snapshot.
- Not L3: #31638: the reported TestFlight upload timeout had already succeeded when an L2 checked.
- Not L3: #9223: the AAB Play rejected was built outside Emergent; the Emergent-built AAB already matched Play's key.
- Not L3: #222115: Apple refused the sign-in at password validation; the customer had used the wrong Apple password.
- Not L3: #26333: the preview was archived after idle time, which is normal behaviour.
