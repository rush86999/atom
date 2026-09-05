#!/usr/bin/env bash
# Restart the ATOM backend as ONE healthy instance.
#
# Why this exists (2026-09-02): the API server does NOT run --reload, so
# code changes stay inert until a manual restart; ad-hoc restarts also left
# behind zombie app processes (one ingesting data without listening, two
# instances fighting over :8001). This script is the one reliable path:
#   1. kill every uvicorn main_api_app process (stragglers included)
#   2. start exactly one instance with the documented args, from backend/
#   3. poll /api/health until it reports healthy (or fail loudly)
# Idempotent — safe to run repeatedly.

set -u

PORT="${PORT:-8001}"
PY="${PYTHON_BIN:-/usr/local/Cellar/python@3.11/3.11.13/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python}"
BACKEND_DIR="$(cd "$(dirname "$0")/../backend" && pwd)"
LOG_FILE="${LOG_FILE:-$BACKEND_DIR/logs/uvicorn_8001_restart.log}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-90}"

# Snapshot the dev DB BEFORE touching the server (incident 2026-09-04: a
# stray script emptied backend/data/atom.db and no fresh backup existed).
# WAL-safe via the sqlite3 backup command, then gzipped — this box is
# disk-constrained (sqlite text compresses ~4x). Keeps the last 5.
DB_PATH="$BACKEND_DIR/data/atom.db"
if [ -f "$DB_PATH" ]; then
    BACKUP_DIR="$BACKEND_DIR/data/backups"
    mkdir -p "$BACKUP_DIR"
    TS=$(date +%Y%m%d-%H%M%S)
    SNAP="$BACKUP_DIR/atom-pre-restart-$TS.db"
    if sqlite3 "$DB_PATH" ".backup '$SNAP'" 2>/dev/null && gzip -f "$SNAP" 2>/dev/null; then
        ls -t "$BACKUP_DIR"/atom-pre-restart-*.db.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
        echo "==> DB snapshot: $SNAP.gz"
    else
        rm -f "$SNAP"
        echo "!! WARNING: DB snapshot failed (continuing) — is sqlite3 installed?"
    fi
fi

echo "==> Stopping existing backend instance(s) on port $PORT"
pkill -f "uvicorn main_api_app:app" 2>/dev/null
sleep 2
# Escalate for anything still holding the port or the app module.
LEFTOVERS=$(pgrep -f "uvicorn main_api_app:app" 2>/dev/null)
if [ -n "$LEFTOVERS" ]; then
    echo "==> Force-killing leftovers: $LEFTOVERS"
    pkill -9 -f "uvicorn main_api_app:app" 2>/dev/null
    sleep 1
fi

echo "==> Starting backend from $BACKEND_DIR"
mkdir -p "$(dirname "$LOG_FILE")"
cd "$BACKEND_DIR" || exit 1
nohup "$PY" -m uvicorn main_api_app:app \
    --host 0.0.0.0 --port "$PORT" --timeout-keep-alive 75 \
    >> "$LOG_FILE" 2>&1 &
NEW_PID=$!
echo "==> Started pid $NEW_PID (log: $LOG_FILE)"

echo -n "==> Waiting for health"
ELAPSED=0
until curl -sf -m 3 "http://localhost:$PORT/api/health" >/dev/null 2>&1; do
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    echo -n "."
    if ! kill -0 "$NEW_PID" 2>/dev/null; then
        echo
        echo "FAILED: process $NEW_PID exited during startup — last log lines:"
        tail -15 "$LOG_FILE"
        exit 1
    fi
    if [ "$ELAPSED" -ge "$HEALTH_TIMEOUT" ]; then
        echo
        echo "FAILED: no healthy response within ${HEALTH_TIMEOUT}s"
        tail -15 "$LOG_FILE"
        exit 1
    fi
done
echo

echo "==> Healthy:"
curl -s -m 3 "http://localhost:$PORT/api/health" \
    | python3 -c "import json,sys; d=json.load(sys.stdin); i=d.get('identity',{}); print('    status:', d.get('status'), '| pid:', i.get('pid'), '| started:', i.get('started_at'))"

echo "==> Done. Code changes are now live."
