#!/usr/bin/env bash
# Stop Atom backend instances, including orphaned `uvicorn --reload` workers
# whose reloader parent died (they hold stale in-memory state forever).
#
# Usage:
#   scripts/stop-backend.sh [PORT ...]   # default: 8001 (frontend target) + 8000

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_LOCAL="$ROOT/frontend-nextjs/.env.local"

if [[ $# -gt 0 ]]; then
  PORTS=("$@")
else
  UI_PORT="$(grep -E '^NEXT_PUBLIC_API_URL=' "$ENV_LOCAL" 2>/dev/null | head -1 \
    | sed -E 's|^[^=]*=||; s|/*$||; s|.*:||')"
  UI_PORT="${UI_PORT:-8001}"
  PORTS=("$UI_PORT" 8000)
fi

STOPPED=0
for PORT in "${PORTS[@]}"; do
  PIDS="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | sort -u || true)"
  [[ -z "$PIDS" ]] && { echo ":$PORT — nothing listening"; continue; }
  for p in $PIDS; do
    ps -p "$p" -o pid=,lstart=,command= 2>/dev/null | cut -c1-150 || true
  done
  kill $PIDS 2>/dev/null || true
  sleep 2
  REMAIN="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | sort -u || true)"
  if [[ -n "$REMAIN" ]]; then
    kill -9 $REMAIN 2>/dev/null || true
  fi
  echo ":$PORT — stopped"
  STOPPED=1
done

[[ "$STOPPED" == 1 ]] || echo "No backend instances were running."
