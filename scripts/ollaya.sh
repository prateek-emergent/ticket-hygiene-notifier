#!/usr/bin/env bash
# Start, stop or check Ollaya, the local model server that rule 1 (Pending check, model option A) uses.
# macOS / Linux counterpart of scripts/ollaya.ps1.
#
#     scripts/ollaya.sh status
#     scripts/ollaya.sh start
#     scripts/ollaya.sh stop
#
# Ollaya does not start by itself: start it before the notifier (`python -m notifier run`), and keep it running.
# It loads a model on its first request (decider:4b can take up to a minute) and unloads it after 5 idle
# minutes; that's normal. Binaries and models live in .tools/ (git-ignored); the server log goes to
# .tools/ollaya.log.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EXE="$ROOT/.tools/ollaya/bin/ollaya"
URL="http://127.0.0.1:11435/v1/models"
export OLLAYA_HOST="127.0.0.1:11435"
export OLLAYA_MODELS="$ROOT/.tools/models"
if [ -z "${OLLAYA_THREADS:-}" ]; then
  # Use the performance cores; using every core (incl. efficiency cores) is slower on Apple silicon.
  OLLAYA_THREADS="$(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null || getconf _NPROCESSORS_ONLN)"
fi
export OLLAYA_THREADS

[ -x "$EXE" ] || { echo "Ollaya not found at $EXE (see README: First-time setup)" >&2; exit 1; }

up() { curl -s -m 3 -o /dev/null -w '%{http_code}' "$URL" 2>/dev/null | grep -q '^200$'; }

case "${1:-status}" in
  status)
    if up; then
      echo "Ollaya is running at $URL"
      echo "Installed models: $(curl -s -m 3 "$URL" | python3 -c 'import json,sys; print(", ".join(m.get("name","") for m in json.load(sys.stdin).get("models",[])))')"
      "$EXE" ps || true
    else
      echo "Ollaya is NOT running. Start it with: scripts/ollaya.sh start"
    fi
    ;;
  start)
    if up; then echo "Ollaya is already running at $URL"; exit 0; fi
    nohup "$EXE" serve >> "$ROOT/.tools/ollaya.log" 2>&1 &
    for _ in $(seq 1 30); do
      sleep 0.5
      if up; then echo "Ollaya started at $URL (threads: $OLLAYA_THREADS, log: .tools/ollaya.log)"; exit 0; fi
    done
    echo "Ollaya did not come up within 15 s; see .tools/ollaya.log" >&2; exit 1
    ;;
  stop)
    if ! up; then echo "Ollaya is not running"; exit 0; fi
    "$EXE" stop || pkill -f "$EXE serve" || true
    ;;
  *)
    echo "usage: scripts/ollaya.sh start|stop|status" >&2; exit 2
    ;;
esac
