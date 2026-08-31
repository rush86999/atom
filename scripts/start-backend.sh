#!/usr/bin/env bash
# Start the Atom backend with stale-instance guards.
#
# Guards against the two ways a backend silently serves stale state:
#   1. An instance already listening on the port (e.g. an orphaned
#      `uvicorn --reload` worker whose watcher died) keeps serving its old
#      in-memory state — keys, tenants, caches — no matter what's on disk.
#   2. Starting on a port the frontend doesn't proxy to. The frontend's
#      target is NEXT_PUBLIC_API_URL in frontend-nextjs/.env.local
#      (default http://localhost:8001), applied to every /api rewrite in
#      next.config.js. This script starts on THAT port by default.
#
# Usage:
#   scripts/start-backend.sh [--port N] [--force] [--reload] [--daemon]
#
#   --port N   Override the port (default: frontend's NEXT_PUBLIC_API_URL).
#   --force    Kill whatever holds the port (and any other atom backend on
#              8000/8001) instead of refusing to start.
#   --reload   Pass --reload to uvicorn (dev auto-reload).
#   --daemon   Run in the background, logging to backend/logs/.

set -euo pipefail

PORT="" FORCE=0 RELOAD=0 DAEMON=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="${2:-}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    --reload) RELOAD=1; shift ;;
    --daemon) DAEMON=1; shift ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_LOCAL="$ROOT/frontend-nextjs/.env.local"

if [[ -z "$PORT" ]]; then
  # Single source of truth for "which backend does the UI talk to".
  PORT="$(grep -E '^NEXT_PUBLIC_API_URL=' "$ENV_LOCAL" 2>/dev/null | head -1 \
    | sed -E 's|^[^=]*=||; s|/*$||; s|.*:||')"
  PORT="${PORT:-8001}"
fi

port_pids() { lsof -nP -iTCP:"$1" -sTCP:LISTEN -t 2>/dev/null | sort -u || true; }
describe_pid() { ps -p "$1" -o pid=,lstart=,command= 2>/dev/null | cut -c1-150; }

# Guard 1: the port is already taken.
PIDS="$(port_pids "$PORT")"
if [[ -n "$PIDS" ]]; then
  echo "❌ Port $PORT already in use:"
  for p in $PIDS; do echo "   $(describe_pid "$p")"; done
  if [[ "$FORCE" == 1 ]]; then
    echo "   --force: replacing it"
    kill $PIDS 2>/dev/null || true; sleep 2
    kill -9 $PIDS 2>/dev/null || true
  else
    echo "   A stale instance keeps serving old in-memory state (keys, tenants,"
    echo "   caches) even after fixes on disk. Restart it, or rerun with --force."
    exit 1
  fi
fi

# Guard 2: another atom backend on the sibling port (split-brain state).
OTHER=8000; [[ "$PORT" == "8000" ]] && OTHER=8001
OTHER_PIDS="$(port_pids "$OTHER")"
if [[ -n "$OTHER_PIDS" ]]; then
  echo "⚠️  Another backend is listening on :$OTHER (the UI talks to :$PORT):"
  for p in $OTHER_PIDS; do echo "   $(describe_pid "$p")"; done
  if [[ "$FORCE" == 1 ]]; then
    kill $OTHER_PIDS 2>/dev/null || true; sleep 1
    kill -9 $OTHER_PIDS 2>/dev/null || true
  else
    echo "   Two instances = two divergent in-memory states. Kill it or use --force."
  fi
fi

cd "$ROOT/backend"
[[ -d venv ]] && source venv/bin/activate
export PYTHONPATH="$ROOT:$ROOT/backend"
export BYPASS_RATE_LIMIT="${BYPASS_RATE_LIMIT:-1}"
export ATOM_BACKEND_PORT="$PORT"

ARGS=(python -m uvicorn main_api_app:app --host 0.0.0.0 --port "$PORT")
[[ "$RELOAD" == 1 ]] && ARGS+=(--reload)

if [[ "$DAEMON" == 1 ]]; then
  mkdir -p logs
  LOG="logs/uvicorn_${PORT}_$(date +%Y%m%d).log"
  nohup "${ARGS[@]}" >> "$LOG" 2>&1 &
  echo "✅ Backend starting on :$PORT (pid $!)"
  echo "   Logs:   backend/$LOG"
  echo "   Health: http://127.0.0.1:$PORT/health — check identity.started_at"
else
  exec "${ARGS[@]}"
fi
