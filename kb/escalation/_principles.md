# Principles for judging an L2→L3 escalation

These apply to every issue file. A more specific issue file overrides them.

## Genuine L3

- An escalation is genuine when the fix needs access or authority that L2 does not have.
- L2 does not have this access:
  - a write to a production database or production infrastructure that no L2 runbook covers;
  - kubectl, pod exec, jumpbox or any shell inside a pod;
  - a restore from S3, a PVC snapshot or restic, or a database restore outside the L2 PITR runbook;
  - rotating or revoking a managed credential (database password, managed email key, stored App Store Connect key);
  - changing edge config, the Cloudflare worker, a Cloudflare zone setting, or a nameserver change or deletion at the domain registrar;
  - deleting jobs, projects, object-storage files or integration-proxy rows, which sit behind admin allow-lists or read-only roles;
  - any change to platform code, base images, build templates or the deployer.
- L2 does not have this authority:
  - approving a credit or refund above the support cap;
  - a legal, privacy, security or trust-and-safety decision;
  - a commercial exception or compensation decision.
- It is also genuine when L2 ran the matching runbook and the runbook's "escalate when" condition was met.

## Not L3

- L2 has a tool or runbook that performs the fix.
- The cause is the customer's own setup, code or third-party provider, or the platform is behaving as designed. L2 explains it and gives the customer the steps.
- The issue file's "L2 must try first" checks were skipped, or the note does not record them.
- The problem had already cleared before the escalation.

## What does not decide it

- **The Trinity level of the person who fixed it.** Several reviewers are labelled L2 in Trinity but do L3-only work: edge-config PATCH, pod exec, credential rotation, production database writes. Judge the action the fix needs.
- **The `real_l3` tag.** It is an opinion, not proof.
  - When the escalator added `real_l3` themselves, in the same action as the escalation, only about half were genuine.
  - When a different person added it, about four in five were genuine.
  - A ticket without `real_l3` is not evidence of a wrong escalation.
- **The level moving back from L3 to L2.** This usually means L3 fixed it, not that it was rejected.
- **How good the escalation note is.** Note quality is theme 6b, judged separately. A thin note does not make an escalation wrong, and a complete note does not make it right.
- **Which L3 team it was routed to.** Routing does not follow one table.
- **The Prod SOS tag.** The system adds it automatically, including on tickets with no platform fault.

## Warning signs of a wrong escalation

Each sign makes a wrong escalation more likely. None decides it alone.

1. **A confident root cause with no evidence behind it.** This includes a cause copied from Overwatch or an AI draft without the engineer's own check. Strong signal: in the case analyses, about two in three such escalations were not needed, and L3 refuted the cause (#235621, #197547, #221651, #273982).
2. **The note itself contains the answer or the runbook fix.** Examples:
   - the note already held the full answer (#222342);
   - the note said no product feature supports the request (#239626);
   - the note said the problem had self-resolved (#48809);
   - the note asked L3 to add TXT and MX records, which L2's DNS API writes (#237350).
3. **L1 moved the ticket straight to L3, skipping L2.** Tickets should reach L3 only after the L1 and L2 playbooks fail. In account and security tickets, 12 of 28 such moves were L2 work.
4. **The note says "no tool exists", and a tool does exist.** Check the claim against the issue file's "L2 can resolve when". Examples of false claims:
   - the Dump Export API (#273153, #273603, #271139);
   - EAS build logs, which `get_eas_build_logs` reads (#22395);
   - the Domain-tab crawler toggle (#211029, #238919);
   - the `_headers.json` security headers (#54636).

   A true "no tool" claim, such as credential rotation or a registrar deletion, is what makes an escalation genuine.
