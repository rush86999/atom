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
# Interpreter resolution, most-specific first:
#   1. PYTHON_BIN env — explicit override.
#   2. This repo's known Homebrew 3.11 path (this dev machine).
#   3. python3 from PATH — fresh installs on any machine.
# A fresh installation must not require this exact Cellar path to exist.
PY="${PYTHON_BIN:-}"
if [ -z "$PY" ] && [ -x "/usr/local/Cellar/python@3.11/3.11.13/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python" ]; then
    PY="/usr/local/Cellar/python@3.11/3.11.13/Frameworks/Python.framework/Versions/3.11/Resources/Python.app/Contents/MacOS/Python"
fi
if [ -z "$PY" ]; then
    PY="$(command -v python3 || true)"
fi
if [ -z "$PY" ]; then
    echo "FAILED: no Python interpreter found (set PYTHON_BIN=/path/to/python)" >&2
    exit 1
fi
if ! "$PY" -c "import uvicorn" >/dev/null 2>&1; then
    echo "FAILED: $PY cannot import uvicorn — run 'pip install -r backend/requirements.txt' (or set PYTHON_BIN to the env that has it)." >&2
    exit 1
fi
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

        # Off-machine copy: the portable drive keeps every snapshot (no
        # 5-cap pruning) so backups survive internal-disk failure. The drive
        # is OPT-IN: point ATOM_EXTERNAL_DRIVE at a mounted volume (or
        # symlink the memory store onto one) to enable it. A fresh install
        # without either just keeps snapshots locally — no warning.
        EXT_DRIVE="${ATOM_EXTERNAL_DRIVE:-/Volumes/Seagate Portable Drive}"
        MEM_LINK="$BACKEND_DIR/data/atom_memory"
        DRIVE_CONFIGURED=$([ -n "${ATOM_EXTERNAL_DRIVE:-}" ] || [ -L "$MEM_LINK" ] && echo 1 || echo 0)
        if [ -d "$EXT_DRIVE" ]; then
            mkdir -p "$EXT_DRIVE/atom-backups"
            if cp "$SNAP.gz" "$EXT_DRIVE/atom-backups/" 2>/dev/null; then
                ls -t "$EXT_DRIVE"/atom-backups/atom-*.db.gz 2>/dev/null | tail -n +31 | xargs rm -f 2>/dev/null
                echo "==> Copied to external drive: $EXT_DRIVE/atom-backups/"
            else
                echo "!! WARNING: external backup copy failed (continuing)"
            fi
        elif [ "$DRIVE_CONFIGURED" = "1" ]; then
            echo "!! WARNING: configured external drive not mounted ($EXT_DRIVE) — snapshot kept locally only"
        fi
    else
        rm -f "$SNAP"
        echo "!! WARNING: DB snapshot failed (continuing) — is sqlite3 installed?"
    fi
fi

# External-store preflight: when the memory store is drive-hosted (symlink),
# booting with the drive absent means "healthy but memory-less" — warn
# loudly BEFORE starting. A fresh local install (plain directory, no
# symlink) needs no external drive and stays silent here.
MEM_LINK="$BACKEND_DIR/data/atom_memory"
if [ -L "$MEM_LINK" ] && [ ! -e "$MEM_LINK" ]; then
    echo "!! WARNING: external memory store not mounted ($MEM_LINK dangling)."
    echo "!!   The API will start, but memory/RAG features will error until"
    echo "!!   the drive is reconnected (recovery is automatic afterwards)."
    echo "!!   Diagnose with scripts/drive_status.sh"
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
