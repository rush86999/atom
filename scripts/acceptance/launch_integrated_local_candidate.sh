#!/usr/bin/env bash
# Launch one isolated integrated local candidate. Never touches the existing
# service on :8001. Refuses protected/ambiguous worlds, occupied ports and
# low disk before writing; verifies the exact serving process and database.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORLD="${WORLD:?set WORLD to an isolated data root}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:?set ADMIN_PASSWORD for the isolated admin}"
BACKEND_PORT="${BACKEND_PORT:-8071}"
FRONTEND_PORT="${FRONTEND_PORT:-3130}"
PYTHON="${PYTHON:-/Users/rushiparikh/projects/atom/backend/venv/bin/python}"
MIN_FREE_MB="${MIN_FREE_MB:-1024}"

MARKER="$WORLD/.atom-integrated-world.json"
SECRET_FILE="$WORLD/.atom-secret"
BACKEND_PID=""
FRONTEND_PID=""
SUCCESS=0

stop_started() {
  local pid="$1" label="$2" pattern="$3"
  [ -n "$pid" ] || return 0
  kill -0 "$pid" 2>/dev/null || return 0
  local cmd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  case "$cmd" in
    *"$pattern"*) ;;
    *) echo "not stopping $label pid $pid (unexpected command: $cmd)" >&2; return 0 ;;
  esac
  echo "stopping $label pid $pid" >&2
  kill -INT "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 1
  done
  kill -9 "$pid" 2>/dev/null || true
}

cleanup() {
  local rc=$?
  if [ "$SUCCESS" -ne 1 ]; then
    if [ -n "$BACKEND_PID$FRONTEND_PID" ]; then
      echo "startup failed; cleaning up only this invocation's processes" >&2
    fi
    stop_started "$FRONTEND_PID" frontend "next"
    stop_started "$BACKEND_PID" backend "uvicorn main_api_app:app"
  fi
  exit "$rc"
}
trap cleanup EXIT

if [[ ! -f "$ROOT/frontend-nextjs/.next/BUILD_ID" ]]; then
  echo "frontend is not built: run the build command in docs/acceptance/INTEGRATED_LOCAL_CANDIDATE_2026-10-31.md" >&2
  exit 2
fi
if ! "$PYTHON" -c "import uvicorn" >/dev/null 2>&1; then
  echo "FAILED: $PYTHON cannot import uvicorn" >&2
  exit 2
fi

# 1. Read-only path/port/space validation. No directory is created yet.
VALIDATION="$("$PYTHON" "$ROOT/scripts/acceptance/validate_local_world.py" \
  --world "$WORLD" --repo "$ROOT" \
  --backend-port "$BACKEND_PORT" --frontend-port "$FRONTEND_PORT" \
  --min-free-mb "$MIN_FREE_MB")"
echo "$VALIDATION" | "$PYTHON" -m json.tool >/dev/null
WORLD_REAL="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["world"])' <<<"$VALIDATION")"
DB_PATH="$("$PYTHON" -c 'import json,sys; print(json.load(sys.stdin)["database"])' <<<"$VALIDATION")"

# 2. Existing storage guards. A fresh checkout has no gitignored worlds
# root; for a LOCAL layout only, create the configured root after the path/
# port/space validation above. Drive-backed layouts still refuse a missing
# volume and are never created here.
CONFIG="$ROOT/backend/config/world_storage.json"
if [[ -f "$CONFIG" ]]; then
  IFS=$'\t' read -r LAYOUT WORLDS_ROOT < <(
    "$PYTHON" - "$CONFIG" "$ROOT/backend" <<'PY'
import json, sys
from pathlib import Path
config = json.loads(Path(sys.argv[1]).read_text())
backend = Path(sys.argv[2])
root = ((config.get("worlds") or {}).get("root")
        or "data/acceptance_worlds")
root_path = Path(root)
if not root_path.is_absolute():
    root_path = backend / root_path
layout = (config.get("layout")
          or (config.get("worlds") or {}).get("layout") or "local")
print(f"{layout}\t{root_path}")
PY
  )
  if [[ "$LAYOUT" == "local" && ! -e "$WORLDS_ROOT" ]]; then
    mkdir -p "$WORLDS_ROOT"
    echo "created configured local worlds root: $WORLDS_ROOT"
  fi
fi
(
  cd "$ROOT/backend"
  "$PYTHON" -m core.world_storage_guard check
)
(
  cd "$ROOT/backend"
  "$PYTHON" -m scripts.orchestration_acceptance.storage_policy space \
    --world "$WORLD_REAL" --no-build-cache >/dev/null
)

# 3. Compute the exact source identity the serving process must report.
EXPECTED_SOURCE="$(
  cd "$ROOT/backend"
  "$PYTHON" -c 'from core.runtime_identity import capture_runtime_identity; print(capture_runtime_identity().source_id)'
)"

# 4. First write happens only after every refusal above.
umask 077
mkdir -p "$WORLD_REAL/data" "$WORLD_REAL/evidence" \
  "$WORLD_REAL/data/office" "$WORLD_REAL/data/assignments" \
  "$WORLD_REAL/data/task_locks" "$WORLD_REAL/data/email_attachments"
if [[ ! -s "$SECRET_FILE" ]]; then
  "$PYTHON" -c 'import secrets; print(secrets.token_hex(32))' > "$SECRET_FILE"
fi
chmod 600 "$SECRET_FILE"
SECRET_VALUE="$(cat "$SECRET_FILE")"

"$PYTHON" - "$MARKER" "$WORLD_REAL" "$ROOT" "$DB_PATH" "$SECRET_FILE" \
  "$BACKEND_PORT" "$FRONTEND_PORT" <<'PY'
import json, os, sys
from datetime import datetime, timezone
marker, world, repo, database, secret, bport, fport = sys.argv[1:]
now = datetime.now(timezone.utc).isoformat()
payload = {}
if os.path.isfile(marker):
    with open(marker) as fh:
        payload = json.load(fh)
payload.update({
    "schema": "atom-integrated-local-world-1",
    "world": world,
    "repo": repo,
    "database": database,
    "secret_file": secret,
    "backend_port": int(bport),
    "frontend_port": int(fport),
    "last_launched_at": now,
})
payload.setdefault("created_at", now)
with open(marker, "w") as fh:
    json.dump(payload, fh, indent=2, sort_keys=True)
    fh.write("\n")
PY

export DATABASE_URL="sqlite:///$DB_PATH"
export ATOM_DATA_DIR="$WORLD_REAL/data"
export LANCEDB_URI="$WORLD_REAL/data/atom_memory"
export ATOM_OFFICE_DIR="$WORLD_REAL/data/office"
export ATOM_ASSIGNMENT_OUTPUT_DIR="$WORLD_REAL/data/assignments"
export ATOM_TASK_LOCK_DIR="$WORLD_REAL/data/task_locks"
export ATOM_EMAIL_ATTACHMENT_DIR="$WORLD_REAL/data/email_attachments"
export SECRET_KEY="$SECRET_VALUE"
export ADMIN_PASSWORD
export ATOM_PRODUCT_PROFILE=core
export ENABLE_SCHEDULER=false
export ENABLE_INGESTION_SYNC=false
export ATOM_LOCAL_ONLY=true
export ATOM_TURN_DECISION_ROUTING=0
export ATOM_TASK_LIFECYCLE_ENABLED=1
export ATOM_ASSIGNMENT_CONTROLLED_TRANSPORT=1
export ATOM_ASSIGNMENT_OUTBOX="$WORLD_REAL/controlled-outbox.jsonl"
export ADDITIONAL_ALLOWED_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"
export ALLOWED_HOSTS="localhost,127.0.0.1,localhost:${BACKEND_PORT},127.0.0.1:${BACKEND_PORT},localhost:${FRONTEND_PORT},127.0.0.1:${FRONTEND_PORT},testserver"

cd "$ROOT/backend"
nohup "$PYTHON" -m uvicorn main_api_app:app \
  --host 127.0.0.1 --port "$BACKEND_PORT" --timeout-keep-alive 75 \
  > "$WORLD_REAL/backend.log" 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$WORLD_REAL/backend.pid"

HEALTH_OK=0
for _ in $(seq 1 90); do
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "backend exited during startup" >&2
    tail -20 "$WORLD_REAL/backend.log" >&2 || true
    exit 1
  fi
  if BODY="$(curl -fsS -m 3 "http://127.0.0.1:${BACKEND_PORT}/health" 2>/dev/null)"; then
    if "$PYTHON" - "$BODY" "$BACKEND_PID" "$ROOT/backend" "$DB_PATH" \
        "$BACKEND_PORT" "$EXPECTED_SOURCE" <<'PY'
import json, os, sys
from pathlib import Path
body, pid, backend, database, port, source = sys.argv[1:]
data = json.loads(body)
identity = data.get("identity") or {}
checks = {
    "status": data.get("status") in ("healthy", "ok"),
    "pid": str(identity.get("pid")) == str(pid),
    "cwd": Path(str(identity.get("cwd") or "")).resolve() == Path(backend).resolve(),
    "database": Path(str(identity.get("database") or "")).resolve() == Path(database).resolve(),
    "port": str(identity.get("port")) == str(port),
    "source": str(identity.get("source_id")) == str(source),
    "instance": str(identity.get("instance_id") or "").startswith(
        f"{source}.{pid}."),
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    print(f"health identity mismatch: {failed}; identity={identity}", file=sys.stderr)
    raise SystemExit(1)
PY
    then
      HEALTH_OK=1
      break
    fi
  fi
  sleep 2
done
if [ "$HEALTH_OK" -ne 1 ]; then
  echo "backend did not report the exact expected identity" >&2
  exit 1
fi

cd "$ROOT/frontend-nextjs"
NEXT_PUBLIC_API_URL="http://127.0.0.1:${BACKEND_PORT}" \
NEXT_PUBLIC_ALLOW_LOOPBACK=1 \
NEXT_PUBLIC_ASSIGNMENT_TRANSPORT=controlled \
nohup ./node_modules/.bin/next start -p "$FRONTEND_PORT" -H 127.0.0.1 \
  > "$WORLD_REAL/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "$FRONTEND_PID" > "$WORLD_REAL/frontend.pid"

FRONTEND_OK=0
for _ in $(seq 1 60); do
  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "frontend exited during startup" >&2
    tail -20 "$WORLD_REAL/frontend.log" >&2 || true
    exit 1
  fi
  if BODY="$(curl -fsS -m 3 "http://127.0.0.1:${FRONTEND_PORT}/api/health" 2>/dev/null)"; then
    if "$PYTHON" - "$BODY" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
if data.get("service") != "atom-frontend" or data.get("status") not in ("healthy", "ok"):
    print(f"unexpected frontend health: {data}", file=sys.stderr)
    raise SystemExit(1)
PY
    then
      FRONTEND_OK=1
      break
    fi
  fi
  sleep 2
done
if [ "$FRONTEND_OK" -ne 1 ]; then
  echo "frontend did not report atom-frontend health" >&2
  exit 1
fi

SUCCESS=1
echo "world=$WORLD_REAL"
echo "database=$DB_PATH"
echo "backend=http://127.0.0.1:${BACKEND_PORT} pid=$BACKEND_PID source=$EXPECTED_SOURCE"
echo "frontend=http://127.0.0.1:${FRONTEND_PORT} pid=$FRONTEND_PID"
echo "stop: kill -INT $BACKEND_PID $FRONTEND_PID"
