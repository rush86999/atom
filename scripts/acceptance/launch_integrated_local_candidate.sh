#!/usr/bin/env bash
# Launch one isolated integrated local candidate. Never touches the existing
# service on :8001. Requires a built frontend (.next/BUILD_ID) and the main
# repo's Python 3.11 venv.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORLD="${WORLD:?set WORLD to an isolated data root}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:?set ADMIN_PASSWORD for the isolated admin}"
BACKEND_PORT="${BACKEND_PORT:-8071}"
FRONTEND_PORT="${FRONTEND_PORT:-3130}"
PYTHON="${PYTHON:-/Users/rushiparikh/projects/atom/backend/venv/bin/python}"

if [[ ! -f "$ROOT/frontend-nextjs/.next/BUILD_ID" ]]; then
  echo "frontend is not built: run the build command in docs/acceptance/INTEGRATED_LOCAL_CANDIDATE_2026-10-31.md" >&2
  exit 2
fi

mkdir -p "$WORLD/data" "$WORLD/evidence" "$WORLD/data/office" \
  "$WORLD/data/assignments" "$WORLD/data/task_locks" \
  "$WORLD/data/email_attachments"

export DATABASE_URL="sqlite:///$WORLD/atom.db"
export ATOM_DATA_DIR="$WORLD/data"
export LANCEDB_URI="$WORLD/data/atom_memory"
export ATOM_OFFICE_DIR="$WORLD/data/office"
export ATOM_ASSIGNMENT_OUTPUT_DIR="$WORLD/data/assignments"
export ATOM_TASK_LOCK_DIR="$WORLD/data/task_locks"
export ATOM_EMAIL_ATTACHMENT_DIR="$WORLD/data/email_attachments"
export SECRET_KEY="${SECRET_KEY:-integrated-local-candidate}"
export ADMIN_PASSWORD
export ATOM_PRODUCT_PROFILE=core
export ENABLE_SCHEDULER=false
export ENABLE_INGESTION_SYNC=false
export ATOM_LOCAL_ONLY=true
export ATOM_TURN_DECISION_ROUTING=0
export ATOM_TASK_LIFECYCLE_ENABLED=1
export ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1
export ATOM_ASSIGNMENT_OUTBOX="$WORLD/controlled-outbox.jsonl"
export ADDITIONAL_ALLOWED_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"
export ALLOWED_HOSTS="localhost,127.0.0.1,localhost:${BACKEND_PORT},127.0.0.1:${BACKEND_PORT},localhost:${FRONTEND_PORT},127.0.0.1:${FRONTEND_PORT},testserver"

cd "$ROOT/backend"
nohup "$PYTHON" -m uvicorn main_api_app:app \
  --host 127.0.0.1 --port "$BACKEND_PORT" --timeout-keep-alive 75 \
  > "$WORLD/backend.log" 2>&1 &
echo $! > "$WORLD/backend.pid"

for _ in $(seq 1 90); do
  if curl -sS -m 2 "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
if ! curl -sS -m 2 "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1; then
  echo "backend did not become healthy; see $WORLD/backend.log" >&2
  exit 1
fi

cd "$ROOT/frontend-nextjs"
NEXT_PUBLIC_API_URL="http://127.0.0.1:${BACKEND_PORT}" \
NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
NEXT_PUBLIC_ASSIGNMENT_TRANSPORT=controlled \
nohup ./node_modules/.bin/next start -p "$FRONTEND_PORT" -H 127.0.0.1 \
  > "$WORLD/frontend.log" 2>&1 &
echo $! > "$WORLD/frontend.pid"

for _ in $(seq 1 60); do
  if curl -sS -m 2 "http://127.0.0.1:${FRONTEND_PORT}/login" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "world=$WORLD"
echo "backend=http://127.0.0.1:${BACKEND_PORT} pid=$(cat "$WORLD/backend.pid")"
echo "frontend=http://127.0.0.1:${FRONTEND_PORT} pid=$(cat "$WORLD/frontend.pid")"
echo "stop: kill -INT $(cat "$WORLD/backend.pid") $(cat "$WORLD/frontend.pid")"
