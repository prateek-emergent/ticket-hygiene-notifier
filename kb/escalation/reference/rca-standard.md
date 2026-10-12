# Escalation note (RCA) standard

**For people and for theme 6b.** This standard defines a usable escalation note. The theme-6b check asks the six questions in "How the checker decides"; they are coded in `notifier/rca.py`, and this page is their readable version. The theme-6a judge does not read this page, because a thin note does not make an escalation wrong.

## Scope

1. This standard applies to every move of a Trinity ticket to L3 by an L1 or L2 support agent. A move to L3 is any of these:
   - setting the level to L3;
   - adding the tag `l3_needs_review`;
   - adding the tag `real_l3`.
2. The escalation note is the internal note written by the agent who makes the move.
3. If that agent writes several internal notes between 6 hours before and 15 minutes after the move, all of them together are the escalation note.

## Missing

4. The escalation note is MISSING when the escalating agent wrote no internal note between 6 hours before the move and 15 minutes after it.
5. A note written by another person does not count.
6. A note written by Overwatch, Oracle or any other System author does not count.
7. A note that is empty after removing spaces does not count.
8. The checker decides MISSING 15 minutes after the move.

## Too short

9. An escalation note shorter than 80 characters is VAGUE. Examples: "escalated to L3", "in L3", "looking.", "@name", "<name> is checking".

## Required content

10. The note must name the affected thing: the job ID, the user ID (or account email), and the app name, app URL or domain. Add a deployment, run, workflow or org ID when one is involved.
11. The note must describe the problem in the agent's own words, with the exact error text and when it started (UTC).
12. The note must state the root cause. The root cause is the mechanism that produces the problem: a named component, record, setting, code location or platform limit.
13. A restated symptom is not a root cause. "Preview not loading", "502", "build failed" and "user cannot log in" are symptoms.
14. A component that is "down", "broken" or "degraded", with no reason given, is not a root cause.
15. If the root cause is not known, the note must say "cause not confirmed" and list what was checked and ruled out.
16. If the escalation asks for an action that support cannot perform, the note must say why support cannot perform it: no permission, no tool, no endpoint, or a code change is needed.
17. The note must give at least one piece of evidence for the root cause.
18. The note must list what the agent already checked or ruled out, with the result of each check.
19. The note must state exactly what L3 or engineering must do, as an action on a named object. Alternatively, it must state the fix already applied and how it was verified.
20. These are not actions: "please check", "please look into this", "investigate", "review", "kindly assist", "L3 review required".
21. The note should link the matching Notion playbook or RCA page, or say "no matching playbook". A missing link is a soft gap.

## Evidence

22. Evidence is a specific observation that someone else can re-check.
23. These count as evidence:
    - an exact log line or error text, with its source;
    - a Redash or database query, with the value found;
    - an HTTP or curl result, with the URL and status;
    - a reproduction and its result;
    - a code file and line;
    - a config, flag or key value, with where it was read;
    - a tool output, with the tool name;
    - a reference to a specific screenshot or attachment.
24. These are not evidence on their own:
    - an Overwatch, Oracle or AI conclusion;
    - a green status;
    - the customer's own diagnosis.
25. A cause written as "likely", "might", "seems" or "appears", with no evidence, is an unsupported cause.

## Optional content

26. The note may add any of these:
    - impact: who is blocked, prod down, data at risk;
    - customer plan or LTV;
    - severity: P1 data-loss, P2 prod-down, P3 degraded, P4 cosmetic;
    - deadlines;
    - the Slack thread link;
    - the owner team;
    - actions L3 must not take;
    - what the customer has already been told.

## Not allowed in the note

27. The note must not consist mainly of a customer-facing reply, a copy of the customer's message, or pasted AI output.
28. If AI output is included, the note must say what the agent verified independently.

## How the checker decides

29. MISSING (rules 4–8) and too short (rule 9) are decided by code, without a judge.
30. For every other note, the checker asks six yes/no questions:
    - **Q1 Identifier.** Does the note contain an identifier: a job ID, user ID, account email, app name or slug, app URL or domain, or a deployment, run, workflow or org ID?
    - **Q2 Own check.** Does the note report a check the agent ran, together with its result?
    - **Q3 Cause.** Does the note state a specific root cause, or the specific reason support cannot do it, or say the cause is not confirmed and list what was ruled out?
    - **Q4 Evidence.** Does the note quote or describe at least one specific, re-checkable observation?
    - **Q5 Ask.** Does the note state an exact action for L3 or engineering on a named object, or a fix already applied?
    - **Q6 Own hand-off.** Is the note mainly the agent's own hand-off, rather than a pasted reply, a forwarded customer message or AI output?
31. The note is **VAGUE** when Q6 is no, or when both Q3 and Q5 are no.
32. The note is **UNSUPPORTED** when it is not VAGUE, Q3 is yes, and Q4 is no.
33. The note is **COMPLETE** when all six answers are yes.
34. In every other case the note is **PARTIAL**, and the checker lists the questions answered no.
35. MISSING, VAGUE and UNSUPPORTED notes are flagged.

## Why these numbers

The limits were measured on 2,527 human escalations in the train split of the corpus (`data/kb_research/rca_standard.md`, section 1). Of the notes written before an escalation, 98.9% fall within 6 hours; most agents write the note and change the level within seconds. Of the notes written after it, 93% land within 15 minutes. With these limits, 255 of 2,054 L1 and L2 escalations (12.4%) have no note. Every sampled note under 100 characters was VAGUE, and a job ID alone is 36 characters; 4.6% of L1 and L2 escalations fall under the 80-character limit. Only 3.1% of notes carry all five Escalation Matrix fields, and only 19% give a user ID, so PARTIAL is common and is not flagged. Applied by hand to 40 classified notes, the six questions matched the flag / no-flag judgement on 39 of them; one rater did this, and it is not yet a Jev run.

## Template

```
ESCALATION — #<ticket> → <owner team>
Job: <job id> | User: <user id / account email> | App: <slug> (<app URL or domain>)
Other ids: <deployment / run / workflow / org id>
Severity: <P1|P2|P3|P4> | Plan/LTV: <...> | Blocked: <yes/no, deadline>
PROBLEM: <what fails, exact error text, since when (UTC)>
ROOT CAUSE: <mechanism>   [CONFIRMED | NOT CONFIRMED]
EVIDENCE: - <tool/source>: <exact observation>
CHECKED / RULED OUT: - <thing> → <result>
ASK (L3/eng): <one action on a named object>   VERIFY BY: <check>
(or) FIX APPLIED: <change> — verified by <observation>
WHY NOT L2: <missing permission / tool / endpoint / code change>
RUNBOOK: <Notion link | no matching playbook>
```

## Examples

Placeholders replace identifiers. "…" marks trimmed text. The wording is otherwise the original.

### Good: confirmed cause, live evidence, ruled-out list, one action (#206875)

```
Job ID: <JOB_ID>
Issue: Live site on <DOMAIN> returns 500 on Admin, Booking, and Team. Preview works fine.
Root cause [CONFIRMED]: The production database password is being rejected — MongoServerError: Authentication failed, code 18 —
on every DB call. … Verified live: <DOMAIN>/api/admin = 500, /api/team = 500, pod logs looping code 18 right now.
Why republishing didn't help: MONGO_URL is platform-injected + encrypted. Each redeploy re-applies the same bad credential …
Not the cause (ruled out): App code is correct; NEXT_PUBLIC_BASE_URL is unused (the earlier reply's claim to change it is
wrong — ignore it); DNS/SSL/domain fine.
Fix (internal only): Reset/re-provision the Atlas credential behind MONGO_URL for this app → redeploy once → verify
admin/team return 200.
```

Why it is good: Q1–Q6 are all yes. It quotes the exact error, says how it was checked, rules out other causes, corrects an earlier wrong reply, and asks for one action with a verification step.

### Good: honest "cause not confirmed", with the next check (#271545)

```
RCA: The root job has no environments row and no volume_snapshots row. restart-environment-by-env-id on the root job returns
404 No environment found. So there is no sleeping pod to wake … The builder child has a running pod (POD_RUNNING …).
That was the pod Overwatch's "restarted code-server" finding applied to, not the root job's. …
Not confirmed: why the root has no environment. Either it never had one (lazy provisioning …) or the row was deleted later.
Most orchestrator roots do have a row (28,015 of 30,343 since June), so this is unusual.
Next step for L3: check envcore lazy_env_metadata for the slug and the creation-day EA logs.
```

Why it is good: it does not invent a cause (rule 15). It reports what was checked, corrects Overwatch, and names the next check for L3.

### Bad: restates the customer and asks L3 to investigate (#21274) → VAGUE

```
Customer provided screenshots showing that the account verification process completes successfully, but an error message
appears immediately afterward. The customer has confirmed that they prefer to log in using their email and password
combination. Please review the attached screenshots and investigate the cause of the verification success followed by the
login error. L3 review required
```

Why it fails: Q1, Q2, Q3 and Q5 are no. Every fact comes from the customer, no identifier is given, and the only ask is "investigate".

### Bad: confident mechanism with no observation (#225218) → UNSUPPORTED

```
RCA: Deploy <hash> regenerated all secrets to v1, resetting the migration idempotency guard, letting migrate.go run a
destructive restore over prod. If confirmed, this is a recurring platform risk …
```

Why it fails: Q3 is yes and Q4 is no. The note names a precise mechanism but cites no log, query or run that shows it, and says itself that the mechanism is unconfirmed.

## Sources

- Required fields: [Escalation Matrix](https://app.notion.com/p/37c3b3a7b061816788cdcd01c1b345e3): "Internal note must include: Job ID, User ID, App, Root Cause, and either Fix Applied or precisely what eng must do."
- Evidence and reproduction: [Support Guide](https://app.notion.com/p/22e3b3a7b061809890b2d140cd01e33b): "Steps to Reproduce · Logs and error traces · User ID and job ID · Impact assessment."
- "The mechanism, not the symptom": [Playbook Entry Template](https://app.notion.com/p/37c3b3a7b06181d18a1bfcf88bd7af89).
- Unsupported causes: [Deployer-Agent Debug/RCA Quality Audit](https://app.notion.com/p/39e3b3a7b06181b6a7c2feb71df6390b): "An RCA that can only say 'symptom X observed, cause not confirmed' is safer than an invented cause."
- Measurements, the 40-note validation and open decisions: `data/kb_research/rca_standard.md`.
