# Custom domains, DNS, SSL, Emergent-bought domains, edge and SEO

## Covers
- Custom domain will not connect: "Linking is pending", stuck "Pending", verify fails, Cloudflare error 1014 or 1034, domain does not resolve
- "Domain already exists", "already connected", "belongs to another user"; orphaned domain rows after the app was deleted; domain stuck on an old app with no Unlink button; moving a domain to another app
- SSL not issuing: ERR_SSL_PROTOCOL_ERROR, "SSL initializing", no certificate, www certificate error, cf_ssl_status validation_timed_out or failed, SSL reconcile, missing Cloudflare custom hostname
- DNS records on an Emergent-bought (bought in-app) domain: TXT, MX, SPF, DKIM, DMARC, Google or Microsoft 365 verification, Resend records, CNAME, AAAA
- Registrar work on Emergent-bought domains: EPP or auth code, transfer-out, 409 transfer_blocked, 60-day lock, nameserver change, delete or release at the registrar, clientHold or NXDOMAIN, IONOS/Entri "Linking is pending"
- Edge config: path redirects (301/308), www-to-apex redirect, 404 mode and soft-404, literal 410, HTML cache routes, visitor geolocation headers
- Worker and Cloudflare zone settings: minimum TLS version, ciphers, PCI scan, WAF or bot blocks, "Attention Required" 403, CF 1010, browser cache TTL, Cloudflare-injected scripts
- Security and Cache-Control headers: CSP, HSTS, X-Frame-Options, `_headers.json`, COOP/COEP/CORP, CORS headers on the production domain
- SEO and crawlers: Googlebot sees an empty SPA shell, the crawling toggle, crawler_enabled, stale crawler cache, Search Console "server error" or noindex, AI crawlers blocked, crawler user-agent list, SEO audit tool failing
- 520 "App not available" or white screen because the app's hostnames were flagged as phishing

## Needs L3 when
- An orphaned domain row blocks relinking ("domain already exists" or "already connected") because the app it maps to was deleted or shut down, or the domain is stuck on an old app with no Unlink button — removing the mapping or row is an operator write in an L3 playbook; Notion forbids hand-deleting domain rows (#40156, #2143, #209227, #229772, #40438).
- The platform moved the domain to the wrong app (for example a failed Replace that fell back to a fresh deploy), or a Switch reported success but the database mapping did not change — domain switch API and deployer fix (#47513).
- No Cloudflare custom hostname exists in the production or phishing zone after one reconcile was run while dig showed only 162.159.142.117 and 172.66.2.113 — deployer-eng fix (#50436).
- cf_ssl_status is failed, deleted or pending_deletion, SSL is still not active an hour after a reconcile with correct DNS, or the reconcile returns a Cloudflare 403 — deployer-eng, with the hostname id.
- A CNAME record (or any record other than TXT or MX) is needed on an Emergent-bought domain — the support DNS API accepts only TXT and MX; oncall writes CNAMEs from the prod deployer pod (#256207, #265757, #269203).
- Every DNS record write on an Emergent-bought domain returns 502 registrar_error — domains-ops.
- The customer still wants the nameservers of an Emergent-bought domain changed after being offered transfer-out, or a transfer needs a registrar-side nameserver change to finish — no support operation exists; domains-ops or oncall (#213149, #274601).
- An Emergent-bought domain must be deleted or released at the registrar — no support tool exists (#230400).
- The registry shows clientHold on a domain bought in-app, or an IONOS/Entri purchase is stuck "Linking is pending" — always domain-partner or domains-ops (#8063).
- Transfer-out returns order_id_mismatch, registrant_roles_partial, any *_unverified error, or registrar_error — domains-ops or deployments-oncall; do not retry.
- A path redirect, 404 mode, an HTML cache route or another edge-config flag (for example visitor geolocation) must be written to the deployment's edge config — the edge-config PATCH is an L3 in-runbook action that needs explicit go-ahead (#226155, #227287, #231309, #212277, #218283, #267964). If stored_config and materialized_config still disagree after the PATCH, deployer-eng.
- The worker serves the wrong file or status: a directory path serves the root page, a route's own index.html is never served, asset paths still return 200 after 404 mode is on, or a platform start-up page is cached under asset URLs — worker.js code change (#40143, #197575, #212277, #2485).
- The customer needs a literal HTTP 410 — deployer-eng feature request (#197043).
- A header outside the `_headers.json` allowlist is needed (Cache-Control on static assets, COOP, COEP, CORP, CSP-Report-Only), or the worker drops an allowed header on some responses such as crawler renders — worker or zone change (#28026, #240473, #207270, #223899).
- A Cloudflare zone setting must change: minimum TLS version or ciphers, browser cache TTL, or a WAF or bot rule that blocks a verified crawler or a server-to-server caller (CF 1010, "Attention Required" 403, block by IP or network) — Cloudflare zone admin only (#29108, #251468, #231780, #226072).
- A crawler user agent must be added to the global crawler list (`__seo_crawler_patterns__`) — oncall KV write (#256091, #208310).
- The crawler renderer misbehaves (path cut to its first segment, query string ignored, 200 served over a backend redirect) or the crawling toggle itself returns an error — worker or deployer bug (#217786, #239854, #42224).
- purge_crawler_cache returns dirty or incomplete_*, or bad crawler renders come back after the app is stable — deployer-eng (worker owners).
- The SEO audit tool itself fails or times out — platform tool defect (#36898, #40298, #39050).
- The app returns 520 "App not available" or its hostnames sit in the phishing zone and the customer says the app is legitimate — clearing a phishing verdict is a T&S or engineering action (#35860).

## L2 can resolve when
- Apex A records are not exactly 162.159.142.117 and 172.66.2.113, www is not a CNAME to the root domain, records are proxied (orange cloud), or parking nameservers are set — the customer fixes DNS per the Manual DNS guide, clicks verify once and waits 5 to 15 minutes.
- The Cloudflare hostname exists but SSL is not active (validation_timed_out, "SSL initializing") and dig shows only the two Emergent IPs — run the domain reconcile (go-ahead) from the ERR_SSL or www-certificate playbook, wait 15 minutes, then handshake-test apex and www (#31439).
- The customer wants a domain moved between their own live apps — unlink in Manage Publishes, Domain on the current app, then link on the new app; DNS does not change (#226223).
- Support tools say "never configured" but the audit tables show linked then unlinked — the customer re-links from the Domain tab.
- Every requested record on an Emergent-bought domain is TXT or MX (SPF, DKIM as TXT, DMARC, Google or Microsoft verification, MX) — write them with the support DNS API (POST …/domains/internal/<domain>/dns/records), delete an old SPF first, and read back with GET and a public dig (#224072, #198140, #79333).
- The owner wants the EPP or auth code, or to transfer an Emergent-bought domain out — run the transfer-out endpoint; support runs it, it is not an escalation (permission row 22).
- Transfer-out returns 409 transfer_blocked — give the unlock date from the response and stop (#229778).
- The customer wants crawler rendering turned on or off — the Domain tab toggle "Enable Search Engine Crawling and Optimisation" is that switch (#211029, #40683, #238919).
- Crawler snapshots are stale after the app's own problem was fixed — run purge_crawler_cache once (go-ahead); the customer then uses Search Console "Validate Fix" or "Request Indexing".
- AI bots get the SPA shell although their user agent is in the global list — turn on the crawling toggle; the customer removes bot blocks in robots.txt or middleware.
- Every requested security header is in the `_headers.json` allowlist (CSP, X-Frame-Options, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy, Reporting-Endpoints) — the customer adds frontend/public/_headers.json and republishes (#54636, #42699).
- The customer wants www and apex redirected to each other — Manage Publishes, Domain, Enable Root Domain Redirection (#226625).
- The app is unreachable only from Turkish networks on the shared emergent.host address — known ISP block; give the workaround (custom domain) or support re-pins the app to the Turkey domain set (#247291).
- Every visitor sees a white screen or a private login page — that is the platform private-access wall, not a domain or edge fault; support turns it off on the customer's written request (permission row 45; covered in the accounts file).

## L2 must try first
1. Read both the apex and the www rows in Redash ds 5 `domains` (verified, deleted, cf_custom_hostname_id, cf_ssl_status, user_id, created_at, updated_at), `domain_apps`, both custom_domain_audit tables, and whether the mapped app still exists (fetch_app_details).
2. Run dig A, CNAME, NS and CAA for apex and www on a public resolver at the time of the check, and query each authoritative nameserver separately.
3. Call fetch_domain_status with the app slug or job id, not the domain. A "Forbidden" reply is not evidence either way.
4. For an SSL problem with correct DNS, run one reconcile (go-ahead), wait 15 minutes, then re-check cf_ssl_status and custom_hostnames_list in the production and phishing zones.
5. For an Emergent-bought domain, read the domains_v2 row (source, status, order_id), check the nameservers are emergentlabs.*.orderbox-dns.com, confirm the requester owns it, and check the registry whois.
6. For record requests, write every TXT and MX record yourself and read them back; escalate only the records the API refuses, with exact host, value and TTL.
7. For an EPP or leave request, run transfer-out. For a nameserver request, offer transfer-out first.
8. For edge, SEO or header problems, check /api/health, then send GET (not HEAD) requests to the custom domain and the .emergent.host address with a browser user agent and a bot user agent on 3 or 4 real paths; record status, size, via, x-rendered-by, ETag, cache-control and cf-ray. Read crawler_enabled from ds 5 `deployments_v3`, not kv_get_value.
9. GET the edge config by deployment slug and compare stored_config with materialized_config. For a redirect or 404 ask, prepare the full merged rule list, because a PATCH replaces the whole section. Check each requested header against the `_headers.json` allowlist.
10. For a white screen, check for 520 "App not available", the phishing flag and the private-access wall flag first.

## Not a fault
- The customer's A records still point at an old or non-Emergent IP — give the exact records to set; "updated_at equals created_at" alone proves nothing (#261587).
- The customer's authoritative nameservers return different answers — the customer fixes the stale zone at their DNS host (#25391).
- A CAA record that does not allow the platform's certificate authority blocks SSL — the customer removes or edits the CAA record (#38613).
- The customer's own Cloudflare zone proxies the records (orange cloud; dig returns 104.x or 172.67.x) and causes 1034 or 502 — the customer sets the records to DNS only.
- Only one client program fails the TLS handshake (no SNI, old TLS stack, the customer's DNSSEC) while browsers work — client-side; explain (#52980).
- The domain is not Emergent's (no domains_v2 row, nameservers elsewhere) — the customer adds records at their own registrar or DNS host (#218004).
- The customer asks for AAAA or IPv6 records — custom domains are IPv4-only; explain (#205160).
- Internal rewrites from non-/api paths to /api, uploads over about 100 MB (413), long requests cut off (524) — product limits; give the documented workaround (#210997).
- Assets are stale for about 5 minutes after a deploy, the problem is gone on re-test, or an old bundle shows in one browser because of its service worker — explain; nothing to change (#25649, #18348).
- A bot gets 200 with no Cloudflare block ("please whitelist SemrushBot"), or OpenAI Ads says "Business website unavailable" — no crawler-list change; the customer re-runs the check.
- A webhook or bot is "blocked by Bot Fight Mode" but the app's own code returns the 401 or 403 — the customer fixes their auth check (#8102).
- The customer wants the Cloudflare analytics beacon removed from the shared emergent.host address — it is zone-wide; explain that a custom domain avoids it (#240674).
- The SEO Audit card is missing while the feature is still rolling out — explain the rollout (#234615).

## Changed over time
- Until early June 2026 the worker set no security headers on static HTML, so header requests needed a platform change. Since July 2026 the allowlisted headers are self-serve through `_headers.json`.
- Before mid-July 2026 there was no support API for DNS records on Emergent-bought domains. Since mid-July 2026 (Notion "L3 → 0" page, 11 Jul) TXT and MX records are support work; CNAMEs stayed with oncall.
- In July 2026 deleting crawler-cache entries needed jumpbox access. Since August 2026 support runs purge_crawler_cache.
- The older Escalation Matrix sent EPP and transfer-out to domains-ops ("no self-serve runbook"). The October 2026 casebook supersedes it: support runs transfer-out.

## Examples
- Genuine L3: #40156: an orphaned domain row from a deleted deployment blocked relinking with "domain already exists".
- Genuine L3: #50436: the domain row was verified but no Cloudflare custom hostname existed in either zone after relinking.
- Genuine L3: #256207: L2 wrote the TXT records itself and escalated only two CNAMEs, which oncall wrote.
- Genuine L3: #274601: a registrar nameserver change was needed to finish a transfer-out; oncall applied it.
- Genuine L3: #226155: path redirects needed an edge-config redirects PATCH.
- Genuine L3: #40143: the worker served the root page for a directory path (no directory-index logic).
- Genuine L3: #256091: AI crawler user agents were missing from the global crawler list.
- Genuine L3: #35860: a white screen came from a false phishing flag that put the hostnames in the phishing zone.
- Not L3: #261587: certificates never issued because the customer's A records still pointed at an old IP.
- Not L3: #38613: a leftover customer CAA record blocked certificate issuance.
- Not L3: #31439: cf_ssl_status was validation_timed_out with correct DNS; the L2 reconcile covered it.
- Not L3: #224072: only TXT and MX records were needed on an Emergent-bought domain.
- Not L3: #229778: transfer-out was blocked by the 60-day lock; the answer is the unlock date.
- Not L3: #211029: the customer needed crawler rendering on, which is the Domain tab crawling toggle.
- Not L3: #54636: every requested security header was in the `_headers.json` allowlist.
