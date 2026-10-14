# Trinity ticket-hygiene notifier

Watches Trinity tickets and engineers and posts to a Slack channel, tagging the engineer's associate, when one of these practices shows up:

| # | Theme | Fires when | Not flagged |
|---|------|-----------|-------------|
| 1 | `pending_without_open_question` | An **engineer** moves a ticket to PENDING and their reply asks the customer nothing (judged by the model chosen in `config.py`: option A or B), or no reply was sent after the customer's latest message | Overwatch/System moving to PENDING after an auto-send; engineer changes status again within 30 min; replies the model can't judge confidently (pending decision D1) |
| 2 | `reassigned_from_colleague` | An engineer assigns themselves a ticket **that a colleague was holding** | Self-assigning unassigned tickets; handing it back within 5 min (mis-click); claim races (colleague held it < 2 min); associates (reassigning is their job) |
| 3 | `picked_up_during_overwatch_run` | **System** closes a ticket (right after an Overwatch reply, or the 48 h inactivity auto-close) and the assignee had **assigned it to themselves while an Overwatch run was in progress**, without sending a reply of their own | Ticket was already theirs when that run started (e.g. a "thank you" follow-up); picked up after Overwatch had answered or escalated; assigned by someone else; unassigned before the close; engineer closed it themselves; engineer replied after picking it up |
| 4 | `status_not_matching_shift` | 45 min after a shift starts/ends, the engineer's Trinity status is still Offline/Online. Posts in the channel **and DMs the engineer** | Back-to-back shifts; roster days that can't be read (e.g. swaps); people not in the roster |
| 5 | `ticket_held_off_shift` | A customer has waited 3+ h (counted from the later of their message and the assignee's shift end) on an **OPEN** ticket whose assignee is off shift | PENDING/CLOSED tickets; on-shift assignees |
| 6a | `l3_escalation_check` | An L2→L3 escalation that the escalation knowledge base (`kb/escalation/*.md`) says L2 could have handled | Escalations the KB says need L3; issues the KB doesn't cover; low-confidence judgements; no KB present |
| 6b | `escalation_note_quality` | An L2→L3 escalation whose internal note (the RCA) is missing, under 80 characters, vague (no cause and no exact ask, or pasted text), or states a cause with no evidence | Partial notes (e.g. no User ID): listed in the dashboard only; escalations by people outside the team list |

- **On/off and thresholds:** set in **[`config.py`](config.py)**. The notifier handles 6 themes; theme 6 (L3 escalations) has two checks, 6a and 6b. Today themes 1–5 and 6b are on. Theme 6a is built and tested but off (pending decision D13). Themes 4–5 use the shift roster in `data/`, which covers 9 Oct to 15 Dec 2026.
- **Which AI model each theme uses:** only theme 1 uses the switchable model, `PENDING_MODEL` in `config.py`:
  - **A:** `von` + `decider:4b`, local in Ollaya.
  - **B:** Jev, hosted.

  Theme 6 (6a and 6b) uses Jev, with Claude as the fallback when `ANTHROPIC_API_KEY` is set. Themes 2–5 use no model: they are plain logic on Trinity events and the roster. Details are in "Theme 1's model: option A or B" and "Theme 6: escalations to L3" below.
- **Who is monitored:** only the 34 engineers in `config/teams.yaml`, generated from `data/table.tsv`.
- **Open questions:** tracked in [`pending_decisions.md`](pending_decisions.md). How it all fits together, with diagrams: [`architecture.md`](architecture.md).

Each alert is posted once, with the theme, ticket link, engineer, associate @-mention, and why it was flagged. Theme 1 alerts also quote the end of the reply that was judged.

---

## Running it day to day (two terminals)

**Theme 1 uses option B (Jev) since 2026-10-12, so only the notifier needs to run: skip terminal 1.** Terminal 1 applies only if you switch `config.py` back to option A, which needs **two programs running**:

1. **Ollaya**, the local model server that theme 1 uses to read replies. It does **not** start by itself.
2. **The notifier**, which watches Trinity and sends the alerts.

Start them in this order, each in its own terminal, from the project folder. The commands below are for **PowerShell** on Windows. For **macOS**, see the next block.

With model **option B** (Jev), skip terminal 1: Ollaya isn't used, and only the notifier runs.

### On macOS (Terminal, zsh)

```bash
cd ~/Downloads/PRATEEK/Slack_Notifier

# Terminal 1: Ollaya (option A only). Runs in the background; log in .tools/ollaya.log
scripts/ollaya.sh start      # also: scripts/ollaya.sh status | scripts/ollaya.sh stop

# Terminal 2: the notifier
.venv/bin/python -m notifier run

# Optional, another terminal: the dashboard (http://localhost:8090)
.venv/bin/python -m dashboard
```

Or activate the venv once per terminal with `source .venv/bin/activate`, then use plain `python …`.

On a Mac:
- `.venv\Scripts\python.exe` in this README becomes `.venv/bin/python`.
- `scripts\ollaya.ps1` becomes `scripts/ollaya.sh`.
- Backslashes in paths become forward slashes.

**Trinity and Jev need the company VPN.** Their addresses resolve to private IPs, so without the VPN the notifier logs connection errors.

**8 GB Macs.** `decider:4b`, option A's model for non-English replies, needs about 8.4 GB of RAM, more than the whole machine. On such a Mac:
- `von` (English replies) works;
- non-English Pending checks will fail or swap badly. Failed checks are skipped and logged, never alerted.

Run production on a bigger machine, or use option B (pending decisions D9 and D18).

### Terminal 1: start Ollaya (option A only)

**Foreground (recommended while you're watching).** The log stays visible; press **Ctrl+C** to stop it.

```powershell
cd C:\Users\Lenovo\Downloads\PRATEEK\Slack_Notifier
$env:OLLAYA_HOST    = "127.0.0.1:11435"          # address the notifier talks to (option A's url in config.py)
$env:OLLAYA_MODELS  = "$PWD\.tools\models"       # where the downloaded models are; without this Ollaya can't find `von`
$env:OLLAYA_THREADS = "12"                       # CPU threads; ~3-5x faster than the default on this laptop
.\.tools\ollaya\bin\ollaya.exe serve
```

It's ready when it prints `Ollaya is running address=127.0.0.1:11435 ...`. Leave this terminal open.

**Background, using the helper script.** It does exactly the same as the foreground way, but hidden, and returns once Ollaya answers.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\ollaya.ps1 start     # start
powershell -ExecutionPolicy Bypass -File scripts\ollaya.ps1 status    # is it running? which models?
powershell -ExecutionPolicy Bypass -File scripts\ollaya.ps1 stop      # stop
```

The start logic lives in [`scripts/ollaya.ps1`](scripts/ollaya.ps1). It sets the three variables above and runs `.tools\ollaya\bin\ollaya.exe serve`. Use one way or the other, not both: they use the same port.

Ollaya loads a model on its first request, which takes a few seconds (`decider:4b` up to a minute), and unloads it after 5 idle minutes. That's normal.

### Terminal 2: start the notifier

```powershell
cd C:\Users\Lenovo\Downloads\PRATEEK\Slack_Notifier
.\.venv\Scripts\python.exe -m notifier run
```

Within a few seconds you should see these lines:

```
INFO notifier.__main__: theme 1 model ready: option A (von + decider:4b at http://127.0.0.1:11435)
INFO notifier.shift_checks: loaded shifts for 40 people from data\Roster_...csv
INFO notifier.service: monitoring Trinity every 60s; themes=[...]; dry_run=True
```

With option B, the first line reads `theme 1 model ready: option B (jev-latest at https://litellm.central-infra-apps.emergentagent.com/typesafe)`.

- **If you see `theme 1 model not ready ... Start Ollaya`,** terminal 1 isn't running (option A). The notifier keeps going, but Pending checks are skipped and logged, not alerted, until Ollaya is up. For option B, the message says whether the key or the network is the problem.
- **`dry_run=True`** means alerts are **printed in this terminal instead of posted to Slack**. Set `DRY_RUN=false` in `.env` to post for real, once the Slack app is approved.
- **To stop,** press **Ctrl+C**. Restarting is safe: it picks up where it left off and never sends an alert twice, because state is kept in `state.db`.

`python -m notifier serve` is the event-driven alternative to `run`. Use it once Trinity sends change events (see "How it works").

### Terminal 3 (testing only): the stand-in Slack

Until the real Slack app is approved, a local imitation of Slack's API (`scripts/fake_slack.py`) lets you see real posts and DMs end to end. It enforces the same rules Slack does: valid token, bot must be in the channel, message size limits, user lookup by email. **Production does not use it.**

```powershell
.\.venv\Scripts\python.exe scripts\fake_slack.py --port 8765 --channel "#ticket-hygiene"
```

Then point the notifier at it, either in `.env` (`SLACK_API_URL=http://127.0.0.1:8765/api/`, `SLACK_BOT_TOKEN=xoxb-test`, `DRY_RUN=false`) or for one run:

```powershell
$env:SLACK_API_URL = "http://127.0.0.1:8765/api/"; $env:SLACK_BOT_TOKEN = "xoxb-test"; $env:DRY_RUN = "false"
.\.venv\Scripts\python.exe -m notifier run
```

Every message appears in terminal 3 and is saved to `fake_slack_posts.jsonl`. Remove `SLACK_API_URL` to use real Slack.

### Another terminal: the dashboard

The dashboard is the observability UI for associates. It reads the notifier's `state.db`:
- every check, model call, alert and error, live;
- a trace of each alert;
- each team's numbers;
- the notifier's health.

Associates mark alerts correct or false alarm there. It never writes to Trinity.

```powershell
cd C:\Users\Lenovo\Downloads\PRATEEK\Slack_Notifier
.\.venv\Scripts\python.exe -m dashboard
```

Open <http://localhost:8090>. It runs alongside the notifier and can start or stop at any time. Sign-in:

- **Google** (normal): set `GOOGLE_CLIENT_ID` in `.env` (setup below).
- **Local test sign-in** (before the Google client exists): set `DASHBOARD_DEV_LOGIN=true` in `.env`. The sign-in page then accepts any allow-listed email, but only from this machine.

Only emails in `config/dashboard_users.yaml` can sign in, Google or not. The file starts with the five associates; edit it to the final list. Changes apply at once, no restart needed, and removing an email ends that person's session.

---

## Command reference

Run from the project folder. `py` below means `.\.venv\Scripts\python.exe` on Windows and `.venv/bin/python` on macOS; on a Mac, also write paths with `/`.

| What | Command |
|---|---|
| Start / check / stop Ollaya | Windows: `powershell -ExecutionPolicy Bypass -File scripts\ollaya.ps1 start\|status\|stop` · macOS: `scripts/ollaya.sh start\|status\|stop` |
| Run the notifier (polling Trinity every minute) | `py -m notifier run` |
| Run the notifier (event-driven, once Trinity pushes events) | `py -m notifier serve` |
| Replay the last N hours, print what would be alerted (never posts) | `py -m notifier backtest --hours 24` (add `--no-llm` to skip theme 1's model, `--max-tickets 50` to limit) |
| Explain every check on one ticket (when an alert is disputed) | `py -m notifier check <ticket_id>` |
| Replay real tickets on a simulated clock, through a Slack stand-in, and write a Slack-like page | `py scripts\simulate.py --from-backtest <backtest output> --sample 50` or `--tickets <id> <id>`; add `--pace 0.3` to watch it unfold; page: `simulation\slack_channel.html` |
| Accuracy of theme 1's model on the 100 labelled replies | `py scripts\eval_classifier.py --option A --set all` (or `--option B`; `--set english` / `--set multilingual` for part of the set) |
| Verify the Slack setup (token, associates resolve, test post) | `py scripts\check_slack.py --post-test` |
| Stand-in Slack for testing | `py scripts\fake_slack.py --port 8765 --channel "#ticket-hygiene"` |
| Rebuild `config/teams.yaml` after the team sheet changes | `py scripts\import_teams.py data\table.tsv --associate "Hridaya Madaan=hridaya@emergent.sh" --associate "Sutikshan Mahajan=sutikshan@emergent.sh" --associate "Shreyas Gowda=shreyas.g@emergent.sh" --associate "Subrahmanya KR=subrahmanya@emergent.sh" --associate "Prateek Maithil=prateek.m@emergent.sh"` |
| Dashboard (observability UI) | `py -m dashboard`, then <http://localhost:8090> |
| Rebuild the dashboard UI after changing `dashboard/web/src` | `cd dashboard\web; npm install; npm run build` (writes `dashboard/static`) |
| Work on the UI with live reload | `py -m dashboard` in one terminal, `cd dashboard\web; npm run dev` in another, open <http://localhost:5173> |
| Rebuild the escalation corpus from Trinity (read-only), for the KB | `py scripts\escalation_corpus.py --since 2026-05-18`, then `py scripts\escalation_digest.py --per-family 90` |
| Measure themes 6a and 6b on held-out escalations | `py scripts\eval_kb.py` (report in `data\escalations\holdout\eval_report.md`; `--set train --sample 260` to tune) |
| Tests (offline) | `py -m pytest` |

Add `-v` after `notifier` (e.g. `py -m notifier -v run`) for detailed logs.

---

## First-time setup (on a new machine)

1. **Python environment** (Python 3.12 or later; tested on 3.14 on Windows and 3.15 on macOS)
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
   ```
   macOS:
   ```bash
   python3 -m venv .venv
   .venv/bin/python -m pip install -r requirements-dev.txt
   ```
2. **Secrets and connections:** copy `.env.example` to `.env`, then fill in `TRINITY_MCP_URL` and `TRINITY_MCP_TOKEN` (a read-only key), and later `SLACK_BOT_TOKEN` and `SLACK_CHANNEL`. Keep `DRY_RUN=true` until you've reviewed a day of output.
3. **Inputs in `data/`** (see [`data/README.md`](data/README.md)):
   - the team sheet as `data\table.tsv`; then run the `import_teams.py` command above to create `config/teams.yaml`;
   - the shift roster CSV; then set its path in `config.py` under `SHIFTS["file"]`.
4. **Theme 1's model.**
   - For **option B (Jev)**, put the key in `.env` as `JEV_API_KEY` and skip the rest of this step. Theme 6 uses the same key, plus `ANTHROPIC_API_KEY` for its Claude fallback (optional: without it the fallback is off, with one warning at start).
   - For **option A**, install Ollaya and the models once (Windows, CPU build, kept inside the project: no PATH or system changes):
     - Download the build for your machine (`ollaya-windows-amd64.zip`, or `ollaya-darwin-arm64.tgz` on an Apple-silicon Mac) and `sha256sum.txt` from <https://github.com/ollaya-dev/ollaya/releases> (v0.12.0 is the tested version).
     - Check the zip's SHA-256 against `sha256sum.txt`, then unzip it to `.tools\ollaya` On a Mac: `shasum -a 256 ollaya-darwin-arm64.tgz`, then `mkdir -p .tools/ollaya && tar -xzf ollaya-darwin-arm64.tgz -C .tools/ollaya`. The models in `.tools/models` work on both systems.
     - Start Ollaya (terminal 1 above). Then, in another terminal, download the two models once: `von` for English replies (about 1.6 GB) and `decider:4b` for all other languages (about 8.4 GB):
       ```powershell
       $env:OLLAYA_HOST = "127.0.0.1:11435"; $env:OLLAYA_MODELS = "$PWD\.tools\models"
       .\.tools\ollaya\bin\ollaya.exe pull von
       .\.tools\ollaya\bin\ollaya.exe pull decider:4b
       ```
     - The machine needs **16 GB RAM or more**: `decider:4b` takes about 8.4 GB while loaded.
5. **Slack app:** create it at <https://api.slack.com/apps> → *Create New App* → *From a manifest*, pasting [`config/slack-app-manifest.yaml`](config/slack-app-manifest.yaml). Scopes: `chat:write`, `users:read`, `users:read.email`, and `im:write` for theme-4 DMs. Install it (a workspace admin may need to approve it), copy the `xoxb-` token into `.env`, invite the bot to the channel (`/invite @Ticket Hygiene Bot`), then run `py scripts\check_slack.py --post-test`.
6. **Dashboard:**
   - **Build the UI once.** Needs Node 20 or later: `cd dashboard\web; npm install; npm run build`.
   - **Google sign-in.** In Google Cloud console, go to *APIs & Services → Credentials → Create credentials → OAuth client ID*. Choose type *Web application*. Under *Authorized JavaScript origins*, add `http://localhost:8090` (plus the https address once deployed). Put the client ID in `.env` as `GOOGLE_CLIENT_ID`. No client secret is needed: the server verifies Google's signed ID token itself. A Workspace admin may need to create the client.
   - **Access list.** Who may sign in is `config/dashboard_users.yaml` (copy `config/dashboard_users.example.yaml`).
   - **Sharing beyond this laptop.** Google sign-in only works on `localhost` or over https. So associates use it once it is deployed (pending decision D10), not over the office network by IP.
7. **Check everything:** `py -m pytest`, then a `backtest`, then `py -m notifier run` with `DRY_RUN=true`.

**On the production machine,** use the container (next section). On the Emergent platform several copies may run (it runs two): only the copy holding the `notifier` lease in the database runs the notifier and watchdog; the others serve the dashboard and take over within about a minute if it stops. Outside the platform (`docker/start.sh`, `python -m notifier run`), run **one** notifier only.

### Deploying with Docker

One container runs three processes ([`docker/start.sh`](docker/start.sh)), each restarted 10 s after it stops:
- **notifier** (`NOTIFIER_MODE=run`, polling; `serve` once Trinity pushes events);
- **dashboard** on port 8090 (or `$PORT` if the platform sets one);
- **watchdog**: the down alert (below).

```bash
docker build -t ticket-hygiene .
docker run -d --name ticket-hygiene --env-file .env -v ticket-hygiene-data:/data -p 127.0.0.1:8090:8090 ticket-hygiene
# or, on a VM:  docker compose up -d --build
```

- **Secrets:** the image has no `.env`. Pass the same variables as `.env.example`, through the platform's secret settings or `--env-file .env`.
- **Data:** `state.db` (alert history, dashboard reviews) is in the `/data` volume; keep it on persistent storage.
- **What's in the image** is listed in [`.dockerignore`](.dockerignore): code, `config.py`, `config/` (team list and dashboard access list, which hold staff emails), `kb/`, the roster CSV and the built dashboard. Customer data, local models, research and secrets stay out. Keep the image in a private registry.
- **Network:** the host must reach Trinity and Jev, which are on private (VPN) addresses, and Slack.
- **Health:** `python -m notifier health` exits 1 when the heartbeat is older than 5 min; the image uses it as its `HEALTHCHECK`.
- After editing `config.py`, `config/` or the roster, rebuild and redeploy.

### Pausing it on the Emergent platform

`RUN_NOTIFIER` is the master switch. Set it to `false` in the deploy settings (`backend/.env` in the job's pod, which the platform reads at deploy time) and redeploy: the notifier and the watchdog stop, so nothing calls Trinity, Jev or Slack, and the dashboard stays up. Set it back to `true` and redeploy to resume. `DRY_RUN` only holds back Slack posts; the checks keep running.

### Starting fresh (clearing trial data)

Set **both** in the app's environment settings and redeploy: `RESET_TRIAL=true` (the safety catch) and `RESET_TRIAL_DATA=<label>`, e.g. `2026-11-01`. On startup the copy holding the notifier lease clears alerts, reviews, the activity trace and in-flight checks, once per label, after copying them to `<name>_bak_<label>` in the same database. Ticket progress is kept, so old events don't come back as alerts. With only one of the two set, nothing is cleared and the log says why. Afterwards set `RESET_TRIAL=false`.

### Down alert

`python -m notifier watchdog` (started by the container) sends a Slack **DM to one person**, `DOWN_ALERT["dm"]` in `config.py`, never the channel:
- **stopped:** no heartbeat for 10 min (crashed, hung, or never started, e.g. a missing setting);
- **failing:** running, but every cycle has failed for 10 min (VPN down, Trinity key revoked);
- a reminder every 60 min while it lasts, and a DM when it's back.

It reads only `state.db` and `SLACK_BOT_TOKEN`, so it still works when the notifier can't start. It sends even with `DRY_RUN=true` (`send_during_dry_run`).

### Going live checklist

1. Slack app approved, `check_slack.py --post-test` passes, associates resolve to @mentions.
2. A day of `DRY_RUN=true` output reviewed, especially themes 4–5 from 9 Oct, when the roster starts.
3. `DRY_RUN=false` in `.env`, then restart the notifier.
4. Before 15 Dec: put the next roster in `data/` and update `SHIFTS["file"]`. The notifier warns a week ahead.

---

## Where the code lives, and how changes flow

The code exists in four places. **Nothing syncs on its own.**

| Place | What it is | How code gets in |
|---|---|---|
| **Mac** (this folder) | Where code is written and tested | Development |
| **GitHub** `prateek-emergent/ticket-hygiene-notifier` (private) | The single source of truth for code | `git push` from the Mac |
| **Preview pod** (Emergent job `alert-dedupe-mongo`) | What gets deployed | `git pull` in the pod (its GitHub link can read, but not push) |
| **Deployed app** (`alert-dedupe-mongo.internal.aws.emergent.host`) | What runs | **Deploy** button: builds from the pod's files *at that moment*, not from GitHub |

```
   develop + test        push              pull into pod           Deploy button         verify
   ┌──────────┐ git push ┌──────────┐ git pull ┌─────────────┐  (Emergent UI)  ┌──────────┐  logs,
   │   Mac    │────────▶ │  GitHub  │────────▶ │ preview pod │───────────────▶ │ deployed │─▶ /health
   └──────────┘          └──────────┘          └─────────────┘                 └──────────┘
        ▲                                              │
        └──── pod → Mac copy (only if code was changed in the pod; see below) ┘
```

**Normal change:**
1. Change and test on the Mac (`python -m pytest`), commit, `git push`.
2. In the pod (through the envcore tools, or its terminal), `cd /app && git pull`.
3. Click **Deploy** in the Emergent job. Code changes rebuild (about 4 min); setting-only changes take about 1 min.
4. Check the deploy steps, the app logs and `/health`.

**Rules:**
- **One source of truth.** Don't edit the same files on the Mac and in the pod at the same time.
- **If code was changed in the pod** (by the Emergent agent, or by hand), bring it back to the Mac *before* changing anything else. "Save to GitHub" is not available for this repo in the Emergent UI (the selector is greyed out), and the pod's GitHub link can't push. So the pod's new commits are copied over as patches:
  1. in the pod: `git format-patch <last-synced-commit>..HEAD`;
  2. transfer through envcore, checking the archive's sha256;
  3. on the Mac: `git am --ignore-whitespace` on a `pod-sync` branch. The original upload has Windows line endings, so that flag is needed;
  4. check `git rev-parse 'pod-sync^{tree}'` equals the pod's `git rev-parse 'HEAD^{tree}'`. Equal tree hashes mean identical files;
  5. merge `pod-sync` into `main`, run the tests, push.
- **Settings are not code.** `.env` (preview pod) and `backend/.env` (what the deploy reads) hold the keys and switches (`RUN_NOTIFIER`, `DRY_RUN`). They are git-ignored, live only in the pod, and are changed there; a setting change needs a redeploy but no push or pull.

## Configuration: two places

| Where | What | Examples |
|---|---|---|
| **`config.py`** | Which themes run, their thresholds, theme 1's model, the dashboard | `THEMES` switches; `PENDING_MODEL` option A/B; 45 min status check; 3 h off-shift threshold; roster path and timezone; KB folder; `DASHBOARD` port and access-list file |
| **`.env`** | Secrets, connections, timings | Trinity URL and key, Slack token and channel, `DRY_RUN`, `JEV_API_KEY`, `GOOGLE_CLIENT_ID`, grace periods |

Every `.env` setting is listed and explained in [`.env.example`](.env.example). Restart the notifier after changing either file.

---

## How it works

```
run (polling, today)                              serve (event-driven, once Trinity sends events)
  every 60 s: list tickets updated since last        Trinity POSTs /trinity/events on a change
  scan, read their new timeline events                -> read that ticket's new timeline events
                     \_______ same intake _______/
  -> trigger found? schedule a check at event time + grace period
  -> when due: re-read the timeline -> theme check -> (theme 1) option A/B model / (theme 6) Jev judge -> Slack -> record
  + themes 4-5 run on the clock every cycle (shift starts/ends, off-shift sweep every 15 min)
  + serve mode: the polling sweep every 15 min as a safety net for lost events
```

- **Grace periods:** checks wait a few minutes because Trinity timelines are not atomic. Engineers set PENDING before the reply lands (#272717: 2 minutes), and claims race within a second (#272874). Theme 1 checks 5 min after PENDING; if no reply exists yet, it re-checks for up to 30 min before alerting "no reply".
- **Read-only on Trinity:** it only reads `list_tickets`, `get_ticket`, `get_ticket_messages` and `list_agents`. Use a read-only MCP key.
- **Human vs System:** decided by author email domain (`HUMAN_EMAIL_DOMAINS`). Overwatch acts as `System`.
- **When unsure, no alert:** replies the model can't judge confidently, and checks that fail because the model can't be reached (Ollaya down, or Jev unreachable), are logged as skipped instead of alerted (`ALERT_UNCERTAIN=true` to alert anyway). Trinity errors are retried up to 5 times.
- **De-duplicated** by (theme, triggering event) in `state.db`. Restarts are safe.

### What Trinity needs to send (for `serve`)

Trinity's real-time design ("Real time UI updates - Trinity", Phase 2) calls `publish_ticket_event(ticket, action, changed_fields)` next to every status/assign/reply write. Adding one more destination there is enough: POST the same `ticket.updated` payload to this service, directly or via a Pub/Sub push subscription.

```http
POST https://<this-service>/trinity/events
X-Webhook-Token: <WEBHOOK_TOKEN>
Content-Type: application/json

{"id": "<ticket id>", "num": 273247, "changedFields": {"status": "PENDING"}, "version": 12}
```

Also accepted: `{"ticket_id": ...}`, batches (`{"events": [...]}` or a JSON list), Pusher-style `{"event": ..., "data": {...}}`, and Pub/Sub push envelopes (token as `?token=`). The service answers 202 right away; anything lost is caught by the 15-minute sweep. `GET /healthz` reports liveness.

---

## Theme 1's model: option A or B

Theme 1 needs one yes/no judgement: "does this reply ask the customer something?" It is the **only theme that uses this model**. Theme 6 has its own judge (Jev, below); themes 2–5 are plain logic on Trinity events and the roster.

Choose the model in `config.py`, then restart the notifier:

```python
PENDING_MODEL = {
    "option": "B",   # or "A"
    ...
}
```

| | **Option A** | **Option B** (in use since 2026-10-12) |
|---|---|---|
| Models | `von` for English, `decider:4b` for other languages | `jev-latest` (Jev 1.13) for every language |
| Runs | On this machine, in Ollaya (terminal 1) | At Emergent's LiteLLM (`/typesafe` route) |
| Customer text | Stays on this machine | Is sent to that service |
| Needs | Ollaya running; 16 GB RAM | `JEV_API_KEY` in `.env`; network |
| Time per reply | ~1 s English, ~7–30 s other languages | ~1 s |
| 100 labelled replies | 95/97 decided correct, 2 wrong alerts, 3 uncertain | **100/100**, 0 uncertain |

Both use TypeSafe's `/v1/systemone` API, so the same client code (`notifier/systemone.py`) serves both. For one run, `PENDING_MODEL_OPTION=B` in the environment overrides `config.py`. The comparison and the decision still to make are in `pending_decisions.md` (D9). `research.md` covers the research behind the models.

How a reply is scored:
1. Remove quoted history and stock courtesy sentences ("any other questions?", "¿Hay algo más en lo que pueda ayudarte?", "Cordiali saluti", … in English, Italian, Spanish, Portuguese, French and German).
2. Score it:
   - **Option A, English (`von`):** score the end of the reply (last 1,000 characters), and each sentence that could be an ask ("?", please, could you, confirm, send, ...). P = the mean of the whole-reply score and the best sentence score.
   - **Option A, other languages (`decider:4b`):** one question about the end of the reply. The language is detected from common words, ignoring links, code and quoted passages.
   - **Option B:** one question about the end of the reply, whatever the language.
3. P ≥ 0.6: asks the customer, so no alert. P < 0.4: asks nothing, so alert. In between: uncertain, so no alert, logged as skipped (or sent to Claude with `SYSTEMONE_FALLBACK=claude`).

`CLASSIFIER_BACKEND=claude` in `.env` replaces both options with Claude for every reply.

## Theme 6: escalations to L3 (6a and 6b)

Both fire when a monitored engineer moves a ticket to L3: they set the level to L3, or add `l3_needs_review` or `real_l3`. Several such events within 30 minutes count as one escalation. Both wait 15 minutes for the escalation note, then use Jev (`JEV_API_KEY`), with Claude as the fallback when `ANTHROPIC_API_KEY` is set.

The fallback never stops the notifier:
- **No key:** the fallback is off, with one warning at start. Cases Jev can't settle are logged as not judged and never alerted.
- **Key rejected** (wrong or revoked): one error in the log, then the fallback is off until the notifier restarts. No failing call on every check.
- **A Claude call fails** (network, rate limit, bad response): that case is not judged, and no alert is sent.

### Theme 6a: did it need L3?

This check is judged against the knowledge base in `kb/escalation/`; its layout and upkeep are described in `kb/escalation/README.md`. The KB was built from three sources:
- Notion: the process, the permissions, 216 playbooks, and the Escalation Matrix;
- 704 real escalations, each judged by an analyst;
- the record of contradictions, kept in `data/kb_research/conflicts_*.md`.

How the check works:
1. **Choose a file.** Jev picks the issue file whose Title and Covers list match the ticket. If none matches, there is no alert.
2. **Match bullets.** Jev answers three match questions against that file plus `_principles.md`:
   - Does a "Needs L3 when" bullet describe this ticket?
   - Does an "L2 can resolve when" bullet describe it?
   - Does a "Not a fault" bullet describe it?
3. **Decide.**
   - **Alert** when an L2 or not-a-fault bullet matches clearly (at least 70%) and no L3 bullet does (30% or less). The alert quotes the matching KB section as "What L2 could have done".
   - **Unsure:** Claude decides (only with `ANTHROPIC_API_KEY`; otherwise not judged, no alert).
   - **Anything else:** no alert.

Measured on 146 held-out escalations the KB never saw:
- 3 of 3 alerts were right.
- 0 of 90 genuine escalations were wrongly flagged.
- Only 10% of wrong escalations were caught.

So it is safe but cautious (pending decision D13). **It is off in `config.py`.** To re-measure after changing the KB, run `python scripts/eval_kb.py`.

### Theme 6b: missing or vague escalation note (RCA)

The standard is in `kb/escalation/reference/rca-standard.md`. It comes from the Escalation Matrix ("Job ID, User ID, App, Root Cause, and either Fix Applied or precisely what eng must do"), refined on 2,527 real notes.

How a note is judged:
- **MISSING** (code): the escalating engineer wrote no internal note from 6 h before to 15 min after the move. Flagged at once.
- **Too short** (code): under 80 characters ("escalated to L3", "in L3"). Flagged as vague.
- **Otherwise, Jev:** six yes/no questions about the note: identifier, own check with its result, cause, re-checkable evidence, exact ask, and the engineer's own hand-off.
  - **VAGUE:** pasted text, or no cause and no ask. Flagged.
  - **UNSUPPORTED:** a cause with no evidence. Flagged.
  - **PARTIAL:** listed only, not flagged.

Measured on the same 146 held-out escalations:
- 36 of 38 flags were right.
- Missing notes agreed 19 of 20.
- 2 of 75 partial or complete notes were wrongly flagged.

**It is on.**

## Cost of the models

- Theme 1, option A: nothing per call. Option B: about $0.04 per million input tokens, so cents a month at this volume.
- With `SYSTEMONE_FALLBACK=claude`: only uncertain replies reach Claude.
- Theme 6: one or two Jev calls per escalation for each check (6a once it is on, 6b now), a fraction of a cent each. With `ANTHROPIC_API_KEY`, add one Claude call for each case Jev can't settle; Claude caches the knowledge base between calls.

---

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `theme 1 model not ready: option A ... cannot reach http://127.0.0.1:11435` | Ollaya isn't running. Start it (terminal 1). |
| `theme 1 model not ready: option A ... model 'von' is not installed (have: none)` | Ollaya was started without `OLLAYA_MODELS` pointing at `.tools\models`. Stop it and start it again with the three variables, or use `scripts\ollaya.ps1 start`. |
| `theme 1 model not ready: option A ... model 'decider:4b' is not installed` | Download it once: `.\.tools\ollaya\bin\ollaya.exe pull decider:4b` (with `OLLAYA_HOST` and `OLLAYA_MODELS` set). |
| `theme l3_escalation_check is on: it judges with Jev, which needs JEV_API_KEY in .env` | Put the Jev key in `.env`, or turn theme 6a off in `config.py`. |
| `theme 6: Claude fallback (claude-opus-5-5) is off because ANTHROPIC_API_KEY is not set in .env ...` | Expected without a Claude key: everything still runs on Jev. Add the key to `.env` to turn the fallback on, or set `fallback_model` to `None` in `config.py` to never use Claude. |
| `Claude API key rejected (HTTP 401); fallback ... off until ANTHROPIC_API_KEY is fixed ...` | The Claude key is wrong or revoked. Fix it in `.env` and restart. Until then those cases are not judged (no alert). |
| `config.py PENDING_MODEL option B needs JEV_API_KEY in .env` | Put the Jev key in `.env`, or switch back to option A. |
| `theme 1 model not ready: option B ... HTTP 401. Check the API key in .env` | The Jev key is wrong or revoked. Get a new one and update `JEV_API_KEY`. |
| `theme 1 model not ready: option B ... cannot reach ...` | Network or VPN problem. Pending checks are skipped until it's back; switch to option A if it lasts. |
| Non-English Pending checks slow (~10 s each) or timing out | Normal for `decider:4b` on a CPU. Make sure `OLLAYA_THREADS` is set; raise `SYSTEMONE_TIMEOUT_SECONDS` if the machine is busy. |
| Ollaya: address already in use | It's already running, e.g. started by the script. `scripts\ollaya.ps1 status` / `stop`. |
| `scripts\ollaya.ps1` won't run ("running scripts is disabled") | Use the full form: `powershell -ExecutionPolicy Bypass -File scripts\ollaya.ps1 start`. |
| `not in the shift roster, so themes 4-5 can't check them: ...` | That person has no roster row (e.g. Parasmani, by decision). Harmless. |
| `the shift roster runs out in N day(s)` | Put the next roster in `data/` and update `SHIFTS["file"]` in `config.py`. |
| `poll cycle failed; retrying next interval` with `ConnectError` | Network blip or VPN to Trinity. It retries every minute by itself. |
| Alerts appear only in the terminal | `DRY_RUN=true` in `.env`. |
| `not_in_channel` from Slack | Invite the bot to the channel: `/invite @Ticket Hygiene Bot`. |

---

## Layout

```
config.py            which of the 6 themes run, and their thresholds
.env                 secrets and connections (copy from .env.example; git-ignored)
data/                input files: team sheet (table.tsv) and shift roster (see data/README.md)
config/              teams.yaml (generated), slack-app-manifest.yaml, example files
notifier/
  detectors.py       themes 1-3 and 6a as functions over a ticket timeline (start here)
  service.py         intake, scheduling, evaluation, alerting; the polling loop
  webhook.py         event-driven mode: HTTP receiver and workers
  systemone.py       theme-1 model client (option A: Ollaya; option B: Jev; same /v1/systemone API)
  classifier.py      theme-1 Claude client (backend / fallback)
  shifts.py          shift roster loader (themes 4-5)
  shift_checks.py    themes 4-5: status vs shift, tickets held off shift
  kb.py              theme 6a: escalation knowledge base; Jev judge with Claude fallback
  trinity.py         read-only Trinity client
  slack.py           message formats, posting, DMs, dry-run
  teams.py, config.py   team mapping, .env + config.py loading
  store.py           SQLite state, plus the activity trace the dashboard reads
dashboard/
  app.py             dashboard server: JSON API, live stream, sign-in gate
  queries.py         every read/write the dashboard makes (the storage boundary)
  auth.py            Google ID-token check, access list, sessions
  web/               the UI source (React + Vite); `npm run build` writes static/
scripts/
  ollaya.ps1         start / stop / status for Ollaya (Windows)
  ollaya.sh          the same for macOS / Linux
  simulate.py        replay real tickets on a simulated clock
  fake_slack.py      stand-in Slack for testing
  check_slack.py     verify the real Slack setup
  eval_classifier.py theme-1 accuracy on labelled replies
  import_teams.py    build config/teams.yaml from the team sheet
kb/escalation/       knowledge base for theme 6a (README explains the format)
tests/               offline tests, with timelines modelled on real tickets
.tools/              Ollaya binaries and models (git-ignored)
architecture.md      how it works, with flowcharts
pending_decisions.md open questions parked for later
PRODUCT.md           product brief for the dashboard's design (Impeccable skill)
.claude/skills/impeccable/  the UI design skill used for the dashboard
research.md          research behind the theme-1 model choice
l3_kb_research.md    how the L3 escalation KB (theme 6) was researched, built and tested
```
