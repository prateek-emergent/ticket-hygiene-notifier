#!/bin/sh
# The container's three processes, each restarted 10 s after it stops:
#   notifier   checks Trinity and alerts in Slack (NOTIFIER_MODE: run = polling, serve = Trinity pushes)
#   dashboard  the web UI (port $PORT, default 8090)
#   watchdog   DMs config.py DOWN_ALERT["dm"] if the notifier stops or keeps failing
set -u

keep_running() {
    name=$1
    shift
    while true; do
        "$@"
        echo "[start.sh] $name exited with code $?; restarting in 10 s" >&2
        sleep 10
    done
}

keep_running notifier python -m notifier "${NOTIFIER_MODE:-run}" &
keep_running dashboard python -m dashboard &
keep_running watchdog python -m notifier watchdog &
wait
