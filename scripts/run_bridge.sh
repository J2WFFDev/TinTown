#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (scripts/..)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

# Ensure logs; in service mode assume venv is already provisioned
mkdir -p logs
if [[ -d .venv ]]; then
	source .venv/bin/activate || true
fi

# Environment
export PYTHONPATH=src
export SESSION_ID=${SESSION_ID:-$(uuidgen 2>/dev/null | cut -c1-12 || echo $RANDOM$RANDOM)}

# Decide if running under systemd (journald available)
UNDER_SYSTEMD=0
if [[ -n "${BRIDGE_AS_SERVICE:-}" || -n "${INVOCATION_ID:-}" || -n "${JOURNAL_STREAM:-}" ]]; then
	UNDER_SYSTEMD=1
fi

CONF_PATH=${BRIDGE_CONFIG:-config.yaml}

if [[ "$UNDER_SYSTEMD" -eq 1 ]]; then
	# Foreground execution so systemd tracks the process; journal captures stdout
	echo "SESSION_ID=$SESSION_ID"
	exec python -m scripts.run_bridge --config "$CONF_PATH"
else
	# Background mode for manual use; manage pidfile and simple stdout file
	PIDFILE="logs/bridge.pid"
	if [[ -f "$PIDFILE" ]]; then
		if ps -p "$(cat "$PIDFILE" 2>/dev/null)" >/dev/null 2>&1; then
			echo "Bridge already running with PID: $(cat "$PIDFILE")"
			exit 0
		else
			rm -f "$PIDFILE" 2>/dev/null || true
		fi
	fi
	echo "SESSION_ID=$SESSION_ID" > logs/bridge_run.out
	nohup python -m scripts.run_bridge --config "$CONF_PATH" >> logs/bridge_run.out 2>&1 &
	PID=$!
	echo "$PID" > "$PIDFILE"
	echo PID:$PID
fi
