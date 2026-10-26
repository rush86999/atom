#!/usr/bin/env bash
# Narrow, fail-closed cutover runbook for release candidate ae0c2fda3.
#
# Read-only preflight (default):
#   ./scripts/deploy_release_candidate_ae0c2fda3.sh --preflight
#
# Apply (requires explicit approval token):
#   ATOM_DEPLOY_APPROVED=ae0c2fda3 \
#     ./scripts/deploy_release_candidate_ae0c2fda3.sh --apply
#
# Invariants:
#   - only the recorded pilot PID (33426) on port 8001 is stopped; no pkill;
#   - the live DB is snapshotted before the pilot is stopped, and any backup
#     failure aborts before the stop;
#   - the candidate is launched from its own versioned directory;
#   - c912375de is never overwritten or used as the candidate source;
#   - both data and config are candidate-local: data is a link to the verified
#     live data path, config is copied from the pilot release so writes cannot
#     mutate the rollback release.

set -euo pipefail

CANDIDATE_DIR="/Users/rushiparikh/projects/atom-releases/ae0c2fda3"
ROLLBACK_DIR="/Users/rushiparikh/projects/atom-releases/c912375de"
CANDIDATE_COMMIT="ae0c2fda340e9a85e840e310d84d4d0da4fedab8"
ROLLBACK_COMMIT="c912375de81b55465e61fe468bf0bc2b405fd206"
CANDIDATE_ARCHIVE="$CANDIDATE_DIR/evidence/archive/atom-ae0c2fda3-backend.tar"
CANDIDATE_ARCHIVE_SHA="33a317c2b981f5947f854056aad8b11ffce4ac8c0a6b908e96f998d5dca4f526"
APPROVAL_TOKEN="ae0c2fda3"

PILOT_PID="33426"
PORT="8001"
LIVE_DATA="/Users/rushiparikh/projects/atom/backend/data"
LIVE_ENV="/Users/rushiparikh/projects/atom/backend/.env"
LIVE_VENV="/Users/rushiparikh/projects/atom/backend/venv314"
DB_PATH="$LIVE_DATA/atom.db"
BACKUP_DIR="$LIVE_DATA/backups"
CUTOVER_DIR="$CANDIDATE_DIR/evidence/cutover"

PREFERRED_PROVIDER="opencode-go"
PREFERRED_MODEL="deepseek-v4.1-flash"
PROVIDER_POLICY='{"mode":"automatic","allowed_providers":["opencode-go"],"preferred":{"provider":"opencode-go","model":"deepseek-v4.1-flash"}}'

MODE="${1:---preflight}"
RUN_TS=""
CANDIDATE_STATE=""

fail() { printf 'FAILED: %s\n' "$*" >&2; exit 1; }
say() { printf '==> %s\n' "$*"; }

need_file() { [ -f "$1" ] || fail "missing file: $1"; }
need_dir() { [ -d "$1" ] || fail "missing directory: $1"; }
need_exec() { [ -x "$1" ] || fail "not executable: $1"; }

json_get() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

try:
    with open(sys.argv[1]) as fh:
        data = json.load(fh)
except Exception:
    sys.exit(2)

value = data
for part in sys.argv[2].split('.'):
    if not isinstance(value, dict):
        sys.exit(3)
    value = value.get(part)
print("" if value is None else value)
PY
}

health_json() {
  curl -sf -m 5 "http://127.0.0.1:$PORT/api/health"
}

health_identity_ok() {
  local want_cwd="$1" want_pid="$2" want_db="$3" payload="$4"
  printf '%s' "$payload" | python3 -c '
import json
import sys

d = json.load(sys.stdin)
identity = d.get("identity") or {}
assert d.get("status") == "healthy", d.get("status")
assert d.get("database") == "operational", d.get("database")
assert str(identity.get("pid")) == sys.argv[2], identity.get("pid")
assert identity.get("cwd") == sys.argv[1], identity.get("cwd")
assert identity.get("database") == sys.argv[3], identity.get("database")
' "$want_cwd" "$want_pid" "$want_db" 2>/dev/null
}

pilot_cwd() {
  lsof -a -p "$PILOT_PID" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' | head -1
}

candidate_state() {
  local env_link=0 venv_link=0 data_link=0 config_dir=0
  local unexpected=""

  if [ -L "$CANDIDATE_DIR/backend/.env" ]; then
    env_link=1
  elif [ -e "$CANDIDATE_DIR/backend/.env" ]; then
    fail "candidate backend/.env exists but is not a link"
  fi

  if [ -L "$CANDIDATE_DIR/backend/venv314" ]; then
    venv_link=1
  elif [ -e "$CANDIDATE_DIR/backend/venv314" ]; then
    fail "candidate backend/venv314 exists but is not a link"
  fi

  if [ -L "$CANDIDATE_DIR/backend/data" ]; then
    data_link=1
  elif [ -d "$CANDIDATE_DIR/backend/data" ]; then
    unexpected="$(find "$CANDIDATE_DIR/backend/data" -mindepth 1 -maxdepth 1 \
      ! -name acceptance_results -print -quit)"
    [ -z "$unexpected" ] || fail \
      "candidate backend/data has unexpected source entries: $unexpected"
  elif [ -e "$CANDIDATE_DIR/backend/data" ]; then
    fail "candidate backend/data exists but is neither a directory nor a link"
  fi

  if [ -L "$CANDIDATE_DIR/config" ]; then
    fail "candidate config is a link; it must be a candidate-local copy"
  elif [ -d "$CANDIDATE_DIR/config" ]; then
    config_dir=1
  elif [ -e "$CANDIDATE_DIR/config" ]; then
    fail "candidate config exists but is not a directory"
  fi

  case "${env_link}${venv_link}${data_link}${config_dir}" in
    0000) CANDIDATE_STATE="source-only" ;;
    1111) CANDIDATE_STATE="prepared" ;;
    *) fail "candidate is partially prepared (env=$env_link venv=$venv_link data=$data_link config=$config_dir); inspect before retrying" ;;
  esac
}

verify_candidate_source() {
  local tmp diff_out
  [ "$CANDIDATE_STATE" = "source-only" ] || return 0
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/atom-candidate-source.XXXXXX")"
  tar -xf "$CANDIDATE_ARCHIVE" -C "$tmp" \
    || { rm -rf "$tmp"; fail "could not extract canonical candidate archive"; }
  diff_out="$(diff -rq "$tmp/backend" "$CANDIDATE_DIR/backend" 2>&1 || true)"
  if [ -n "$diff_out" ]; then
    printf '%s\n' "$diff_out" | head -20 >&2
    rm -rf "$tmp"
    fail "candidate source differs from the canonical archive"
  fi
  rm -rf "$tmp"
  say "candidate source matches the canonical archive (0 differences)"
}

verify_prepared_candidate() {
  local config_file
  [ "$(readlink "$CANDIDATE_DIR/backend/data")" = "$LIVE_DATA" ] \
    || fail "prepared candidate backend/data does not point at $LIVE_DATA"
  [ "$(readlink "$CANDIDATE_DIR/backend/.env")" = "$LIVE_ENV" ] \
    || fail "prepared candidate backend/.env does not point at $LIVE_ENV"
  [ "$(readlink "$CANDIDATE_DIR/backend/venv314")" = "$LIVE_VENV" ] \
    || fail "prepared candidate backend/venv314 does not point at $LIVE_VENV"

  for config_file in byok_config.release.json byok_keys.json byok_encryption_key; do
    need_file "$CANDIDATE_DIR/config/$config_file"
    need_file "$ROLLBACK_DIR/config/$config_file"
    [ "$(shasum -a 256 "$CANDIDATE_DIR/config/$config_file" | awk '{print $1}')" \
      = "$(shasum -a 256 "$ROLLBACK_DIR/config/$config_file" | awk '{print $1}')" ] \
      || fail "candidate config/$config_file differs from the pilot copy; inspect before retrying"
  done
}

preflight() {
  local state pilot_cmd pilot_cwd_value port_pids health free_gb

  say "preflight candidate $CANDIDATE_COMMIT"
  need_dir "$CANDIDATE_DIR"
  need_dir "$ROLLBACK_DIR"
  need_file "$CANDIDATE_DIR/RELEASE_IDENTITY.json"
  need_file "$ROLLBACK_DIR/RELEASE_IDENTITY.json"
  need_file "$CANDIDATE_ARCHIVE"
  need_file "$LIVE_ENV"
  need_dir "$LIVE_DATA"
  need_dir "$LIVE_VENV"
  need_exec "$LIVE_VENV/bin/python"
  need_file "$DB_PATH"
  need_file "$ROLLBACK_DIR/config/byok_config.release.json"
  need_file "$ROLLBACK_DIR/config/byok_keys.json"
  need_file "$ROLLBACK_DIR/config/byok_encryption_key"

  [ "$(json_get "$CANDIDATE_DIR/RELEASE_IDENTITY.json" commit)" = "$CANDIDATE_COMMIT" ] \
    || fail "candidate identity commit mismatch"
  [ "$(json_get "$ROLLBACK_DIR/RELEASE_IDENTITY.json" commit)" = "$ROLLBACK_COMMIT" ] \
    || fail "rollback identity commit mismatch"
  [ "$(shasum -a 256 "$CANDIDATE_ARCHIVE" | awk '{print $1}')" = "$CANDIDATE_ARCHIVE_SHA" ] \
    || fail "candidate archive checksum mismatch"

  [ "$(cd "$CANDIDATE_DIR" && pwd -P)" != "$(cd "$ROLLBACK_DIR" && pwd -P)" ] \
    || fail "candidate and rollback resolve to the same directory"

  candidate_state
  state="$CANDIDATE_STATE"
  say "candidate state: $state"
  if [ "$state" = "prepared" ]; then
    verify_prepared_candidate
  else
    verify_candidate_source
  fi

  say "pilot pid=$PILOT_PID port=$PORT"
  kill -0 "$PILOT_PID" 2>/dev/null \
    || fail "recorded pilot pid $PILOT_PID is not running"
  pilot_cmd="$(ps -p "$PILOT_PID" -o command= | sed 's/^[[:space:]]*//')"
  case "$pilot_cmd" in
    *"uvicorn main_api_app:app"*"--port $PORT"*) ;;
    *) fail "recorded pilot pid does not look like uvicorn on port $PORT: $pilot_cmd" ;;
  esac
  pilot_cwd_value="$(pilot_cwd)"
  [ "$pilot_cwd_value" = "$ROLLBACK_DIR/backend" ] \
    || fail "pilot cwd is '$pilot_cwd_value', expected '$ROLLBACK_DIR/backend'"

  port_pids="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null \
    | sort -u | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  [ "$port_pids" = "$PILOT_PID" ] \
    || fail "port $PORT is owned by '${port_pids:-none}', expected only pilot $PILOT_PID"

  health="$(health_json)" || fail "pilot health endpoint is not healthy"
  health_identity_ok \
    "$ROLLBACK_DIR/backend" "$PILOT_PID" \
    "$ROLLBACK_DIR/backend/data/atom.db" "$health" \
    || fail "pilot health identity does not match recorded pid/cwd/database"

  [ "$(readlink "$ROLLBACK_DIR/backend/data")" = "$LIVE_DATA" ] \
    || fail "pilot data link does not resolve to $LIVE_DATA"
  [ "$(readlink "$ROLLBACK_DIR/backend/.env")" = "$LIVE_ENV" ] \
    || fail "pilot env link does not resolve to $LIVE_ENV"
  [ "$(readlink "$ROLLBACK_DIR/backend/venv314")" = "$LIVE_VENV" ] \
    || fail "pilot venv link does not resolve to $LIVE_VENV"
  [ "$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' \
        "$ROLLBACK_DIR/backend/data/atom.db" 2>/dev/null)" \
    = "$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' \
        "$DB_PATH" 2>/dev/null)" ] \
    || fail "pilot database is not the verified live database"

  [ "$(sqlite3 "$DB_PATH" 'PRAGMA quick_check;' 2>/dev/null)" = "ok" ] \
    || fail "live DB quick_check failed"
  [ -d "$BACKUP_DIR" ] || fail "backup directory missing: $BACKUP_DIR"
  [ -w "$BACKUP_DIR" ] || fail "backup directory not writable: $BACKUP_DIR"
  free_gb="$(df -g "$LIVE_DATA" | awk 'NR==2 {print $4}')"
  case "$free_gb" in
    ''|*[!0-9]*) fail "could not determine free space for $LIVE_DATA" ;;
  esac
  [ "$free_gb" -ge 2 ] || fail "less than 2 GiB free for the DB snapshot: ${free_gb} GiB"

  for tool in sqlite3 gzip curl lsof tar diff shasum; do
    command -v "$tool" >/dev/null 2>&1 || fail "$tool is required"
  done

  say "preflight OK; no changes made"
  say "apply: ATOM_DEPLOY_APPROVED=$APPROVAL_TOKEN $0 --apply"
}

snapshot() {
  local tmp snap sha size
  say "snapshotting the live DB before any stop"
  mkdir -p "$BACKUP_DIR" "$CUTOVER_DIR"
  tmp="$(mktemp "$BACKUP_DIR/.atom-pre-ae0c2fda3-$RUN_TS.XXXXXX.db")"
  snap="$BACKUP_DIR/atom-pre-ae0c2fda3-$RUN_TS.db.gz"
  rm -f "$snap"

  if ! sqlite3 "$DB_PATH" ".backup '$tmp'"; then
    rm -f "$tmp"
    fail "DB snapshot failed; pilot was not stopped"
  fi
  [ -s "$tmp" ] || { rm -f "$tmp"; fail "DB snapshot is empty; pilot was not stopped"; }
  [ "$(sqlite3 "$tmp" 'PRAGMA quick_check;' 2>/dev/null)" = "ok" ] \
    || { rm -f "$tmp"; fail "DB snapshot quick_check failed; pilot was not stopped"; }
  gzip -c "$tmp" > "$snap" \
    || { rm -f "$tmp" "$snap"; fail "DB snapshot gzip failed; pilot was not stopped"; }
  gzip -t "$snap" \
    || { rm -f "$tmp" "$snap"; fail "DB snapshot gzip verification failed; pilot was not stopped"; }
  [ -s "$snap" ] \
    || { rm -f "$tmp" "$snap"; fail "DB snapshot file is empty; pilot was not stopped"; }

  sha="$(shasum -a 256 "$snap" | awk '{print $1}')"
  size="$(wc -c < "$snap" | tr -d ' ')"
  rm -f "$tmp"
  python3 - "$CUTOVER_DIR/snapshot-$RUN_TS.json" <<PY
import json
import sys

json.dump({
    "snapshot": "$snap",
    "sha256": "$sha",
    "size": $size,
    "source_db": "$DB_PATH",
    "created_at": "$RUN_TS",
}, open(sys.argv[1], "w"), indent=2)
PY
  say "snapshot OK: $snap ($sha)"
}

prepare_candidate() {
  local source_data
  candidate_state
  if [ "$CANDIDATE_STATE" = "prepared" ]; then
    verify_prepared_candidate
    say "candidate links/config already prepared; verifying only"
    return 0
  fi
  [ "$CANDIDATE_STATE" = "source-only" ] \
    || fail "candidate is not in a preparable state"

  say "preparing candidate-local data/env/venv links and config copy"
  mkdir -p "$CUTOVER_DIR"

  source_data=""
  if [ -d "$CANDIDATE_DIR/backend/data" ]; then
    source_data="$CUTOVER_DIR/source-backend-data-$RUN_TS"
    mv "$CANDIDATE_DIR/backend/data" "$source_data" \
      || fail "could not preserve tracked backend/data"
  fi
  ln -s "$LIVE_DATA" "$CANDIDATE_DIR/backend/data" \
    || fail "could not link live data into candidate"
  ln -s "$LIVE_ENV" "$CANDIDATE_DIR/backend/.env" \
    || fail "could not link live env into candidate"
  ln -s "$LIVE_VENV" "$CANDIDATE_DIR/backend/venv314" \
    || fail "could not link live venv into candidate"

  mkdir -p "$CANDIDATE_DIR/config"
  chmod 700 "$CANDIDATE_DIR/config"
  cp -p "$ROLLBACK_DIR/config/byok_config.release.json" "$CANDIDATE_DIR/config/" \
    || fail "could not copy BYOK config into candidate"
  cp -p "$ROLLBACK_DIR/config/byok_keys.json" "$CANDIDATE_DIR/config/" \
    || fail "could not copy BYOK keys into candidate"
  cp -p "$ROLLBACK_DIR/config/byok_encryption_key" "$CANDIDATE_DIR/config/" \
    || fail "could not copy BYOK encryption key into candidate"
  chmod 600 "$CANDIDATE_DIR/config/"*

  verify_prepared_candidate
  python3 - "$CUTOVER_DIR/prepare-$RUN_TS.json" "$source_data" <<PY
import json
import sys

json.dump({
    "candidate": "$CANDIDATE_DIR",
    "live_data_link": "$LIVE_DATA",
    "live_env_link": "$LIVE_ENV",
    "live_venv_link": "$LIVE_VENV",
    "config_source": "$ROLLBACK_DIR/config",
    "preserved_source_data": sys.argv[2] or None,
    "created_at": "$RUN_TS",
}, open(sys.argv[1], "w"), indent=2)
PY
  say "candidate preparation OK"
}

stop_pilot() {
  local i stat port_pids
  say "stopping ONLY recorded pilot pid $PILOT_PID"
  kill -TERM "$PILOT_PID" \
    || fail "could not TERM pilot pid $PILOT_PID"
  for i in $(seq 1 30); do
    if ! kill -0 "$PILOT_PID" 2>/dev/null; then
      break
    fi
    stat="$(ps -p "$PILOT_PID" -o stat= 2>/dev/null | tr -d '[:space:]')"
    case "$stat" in Z*) break ;; esac
    sleep 1
  done
  if kill -0 "$PILOT_PID" 2>/dev/null; then
    stat="$(ps -p "$PILOT_PID" -o stat= 2>/dev/null | tr -d '[:space:]')"
    case "$stat" in
      Z*) ;;
      *) fail "pilot pid $PILOT_PID still alive after 30s; refusing to start a second instance" ;;
    esac
  fi
  port_pids="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null \
    | sort -u | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  [ -z "$port_pids" ] \
    || fail "port $PORT still has a listener after pilot stop: $port_pids"
  python3 - "$CUTOVER_DIR/stop-$RUN_TS.json" <<PY
import json
import sys

json.dump({
    "stopped_pid": $PILOT_PID,
    "port": $PORT,
    "at": "$RUN_TS",
}, open(sys.argv[1], "w"), indent=2)
PY
  say "pilot stopped; port $PORT free"
}

start_release() {
  local dir="$1" config_dir="$2" log="$3"
  mkdir -p "$(dirname "$log")"
  (
    cd "$dir/backend" || exit 1
    nohup env \
      PYTHONUNBUFFERED=1 \
      ATOM_PREFERRED_LLM_PROVIDER="$PREFERRED_PROVIDER" \
      ATOM_PREFERRED_LLM_MODEL="$PREFERRED_MODEL" \
      ATOM_LLM_PROVIDER_POLICY="$PROVIDER_POLICY" \
      BYOK_CONFIG_FILE="$config_dir/byok_config.release.json" \
      BYOK_KEYS_FILE="$config_dir/byok_keys.json" \
      BYOK_ENC_KEY_FILE="$config_dir/byok_encryption_key" \
      "$LIVE_VENV/bin/python" -m uvicorn main_api_app:app \
      --host 0.0.0.0 --port "$PORT" --timeout-keep-alive 75 \
      >> "$log" 2>&1 </dev/null &
    echo $!
  )
}

wait_health() {
  local want_cwd="$1" want_db="$2" pid="$3" log="$4"
  local i payload
  for i in $(seq 1 60); do
    if ! kill -0 "$pid" 2>/dev/null; then
      tail -40 "$log" >&2 || true
      return 1
    fi
    case "$(ps -p "$pid" -o stat= 2>/dev/null | tr -d '[:space:]')" in
      Z*) tail -40 "$log" >&2 || true; return 1 ;;
    esac
    if payload="$(curl -sf -m 3 "http://127.0.0.1:$PORT/api/health" 2>/dev/null)"; then
      if health_identity_ok "$want_cwd" "$pid" "$want_db" "$payload"; then
        return 0
      fi
    fi
    sleep 2
  done
  tail -80 "$log" >&2 || true
  return 1
}

rollback_after_failure() {
  local reason="$1" failed_pid="$2" failed_log="$3"
  local rb_log rb_pid health i port_pids

  say "candidate cutover failed: $reason"
  say "rolling back to $ROLLBACK_DIR"
  if [ -n "$failed_pid" ] && kill -0 "$failed_pid" 2>/dev/null; then
    kill -TERM "$failed_pid" 2>/dev/null || true
    sleep 3
    kill -KILL "$failed_pid" 2>/dev/null || true
  fi
  for i in $(seq 1 10); do
    port_pids="$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null \
      | sort -u | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
    [ -z "$port_pids" ] && break
    sleep 1
  done
  [ -z "$port_pids" ] \
    || fail "port $PORT still has a listener after failed-candidate cleanup: $port_pids"
  [ -f "$failed_log" ] && cp "$failed_log" "$CUTOVER_DIR/candidate-failed-$RUN_TS.log" || true

  rb_log="$CUTOVER_DIR/uvicorn_8001_rollback-$RUN_TS.log"
  if ! rb_pid="$(start_release "$ROLLBACK_DIR" "$ROLLBACK_DIR/config" "$rb_log")"; then
    fail "ROLLBACK FAILED TO START — manual recovery required"
  fi
  [ -n "$rb_pid" ] || fail "ROLLBACK FAILED TO START — manual recovery required"
  if wait_health "$ROLLBACK_DIR/backend" \
      "$ROLLBACK_DIR/backend/data/atom.db" "$rb_pid" "$rb_log"; then
    health="$(health_json 2>/dev/null || true)"
    python3 - "$CUTOVER_DIR/failed-$RUN_TS.json" "$reason" "$rb_pid" <<PY
import json
import sys

json.dump({
    "reason": sys.argv[2],
    "rollback_pid": int(sys.argv[3]),
    "rollback_dir": "$ROLLBACK_DIR",
    "at": "$RUN_TS",
}, open(sys.argv[1], "w"), indent=2)
PY
    fail "$reason; rollback is healthy (pid $rb_pid), candidate NOT deployed"
  fi
  fail "ROLLBACK ALSO FAILED — manual recovery required"
}

apply_cutover() {
  local new_pid new_log health

  [ "${ATOM_DEPLOY_APPROVED:-}" = "$APPROVAL_TOKEN" ] \
    || fail "explicit approval missing: set ATOM_DEPLOY_APPROVED=$APPROVAL_TOKEN"
  RUN_TS="$(date -u +%Y%m%dT%H%M%SZ)"

  preflight
  mkdir -p "$CUTOVER_DIR"
  snapshot
  prepare_candidate
  stop_pilot

  new_log="$CUTOVER_DIR/uvicorn_8001_candidate-$RUN_TS.log"
  say "starting candidate from $CANDIDATE_DIR"
  if ! new_pid="$(start_release "$CANDIDATE_DIR" "$CANDIDATE_DIR/config" "$new_log")"; then
    rollback_after_failure "candidate failed to start" "" "$new_log"
  fi
  [ -n "$new_pid" ] \
    || rollback_after_failure "candidate returned no pid" "" "$new_log"

  if wait_health "$CANDIDATE_DIR/backend" \
      "$CANDIDATE_DIR/backend/data/atom.db" "$new_pid" "$new_log"; then
    health="$(health_json)"
    python3 - "$CUTOVER_DIR/deployed-$RUN_TS.json" "$new_pid" "$health" <<PY
import json
import sys

json.dump({
    "candidate": "$CANDIDATE_DIR",
    "commit": "$CANDIDATE_COMMIT",
    "pid": int(sys.argv[2]),
    "health": json.loads(sys.argv[3]),
    "snapshot_metadata": "$CUTOVER_DIR/snapshot-$RUN_TS.json",
    "at": "$RUN_TS",
}, open(sys.argv[1], "w"), indent=2)
PY
    say "candidate healthy: pid $new_pid, cwd $CANDIDATE_DIR/backend"
    say "post-deploy smoke is a separate approved step"
    return 0
  fi

  rollback_after_failure "candidate health check failed" "$new_pid" "$new_log"
}

case "$MODE" in
  --preflight) preflight ;;
  --apply) apply_cutover ;;
  *) fail "usage: $0 [--preflight|--apply]" ;;
esac
