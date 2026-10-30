#!/usr/bin/env bash
# One reversible deployment transaction for the assignment successor.
#
# Recovery is armed BEFORE shutdown. Pre-shutdown failures leave the running
# service untouched. Failures after shutdown attempt a verified code rollback;
# rollback failure is reported explicitly, never hidden. The database is never
# restored automatically.
set -euo pipefail

ROOT="${RELEASE_ROOT:-}"
MODE="production"
PRINT_PLAN=0
for arg in "$@"; do
  case "$arg" in
    --rehearsal) MODE="rehearsal" ;;
    --print-plan) PRINT_PLAN=1 ;;
    *) echo "REFUSED: unknown argument: $arg" >&2; exit 2 ;;
  esac
done
if [[ -z "$ROOT" || ! -f "$ROOT/RELEASE_IDENTITY.json" ]]; then
  echo "REFUSED: set RELEASE_ROOT to a prepared release root" >&2
  exit 2
fi

KIT="$ROOT/current/scripts"
PY="${RELEASE_PYTHON:-$ROOT/.venv/bin/python}"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi
API_PORT="${API_PORT:-$(awk -F= '/^API_PORT=/{print $2}' "$ROOT/config/env.release" | tail -1)}"
FE_PORT="${FE_PORT:-$(awk -F= '/^FE_PORT=/{print $2}' "$ROOT/config/env.release" | tail -1)}"
API_BASE="http://127.0.0.1:${API_PORT}"
FE_BASE="http://127.0.0.1:${FE_PORT}"
EMAIL="${ATOM_PILOT_USER_EMAIL:-admin@example.com}"
PASSWORD_FILE="${ATOM_SMOKE_PASSWORD_FILE:-$ROOT/config/pilot_password}"
if [[ "$MODE" == "rehearsal" ]]; then
  PASSWORD_FILE="${ATOM_SMOKE_PASSWORD_FILE:-$ROOT/config/rehearsal_admin_password}"
fi
OBJECTIVE="${ATOM_SMOKE_OBJECTIVE:-Sum the price of the HARSLE press brake stock price list}"
EXPECTED_SUM="${ATOM_SMOKE_EXPECTED_SUM:-216700.00}"
ARTIFACT_SHA="${ATOM_SMOKE_ARTIFACT_SHA256:-}"
FRESH_DATASET="${ATOM_SMOKE_FRESH_DATASET:-outlook_harsle_press_brake_stock_price_list}"
FRESH_SOURCE="${ATOM_SMOKE_FRESH_SOURCE:-outlook}"
FRESH_EXTERNAL_ID="${ATOM_SMOKE_FRESH_EXTERNAL_ID:-}"
FRESH_VERSION="${ATOM_SMOKE_FRESH_VERSION:-e0a7fb8a1b4757b7f6bef882b19cc4588d66246e}"
FRESH_SHEET="${ATOM_SMOKE_FRESH_SHEET:-库存产品}"
FRESH_MEASURE="${ATOM_SMOKE_FRESH_MEASURE:-Price}"
RECEIPT="${DEPLOY_RECEIPT_PATH:-$ROOT/run/deployment_receipt.json}"
mkdir -p "$ROOT/run" "$ROOT/logs"

REHEARSAL_ARGS=()
if [[ "$MODE" == "rehearsal" ]]; then
  REHEARSAL_ARGS=(--rehearsal)
fi

release_tool=("$PY" "$KIT/release_tool.py" "--root" "$ROOT")
approval_cmd=("${release_tool[@]}" approval-check --mode "$MODE")
freshness_cmd=("$PY" "$KIT/check_freshness.py" --root "$ROOT")
preflight_running=("${release_tool[@]}" preflight "${REHEARSAL_ARGS[@]}" --ignore-running-ports)
preflight_stopped=("${release_tool[@]}" preflight "${REHEARSAL_ARGS[@]}")
start_cmd=("${release_tool[@]}" start "${REHEARSAL_ARGS[@]}")
stop_cmd=("${release_tool[@]}" stop)
backup_cmd=("${release_tool[@]}" backup --label "predeploy-${MODE}")
status_cmd=("${release_tool[@]}" status)
rollback_cmd=("${release_tool[@]}" rollback)

if [[ "$PRINT_PLAN" == "1" ]]; then
  python3 - "$MODE" "${REHEARSAL_ARGS[*]:-}" "${approval_cmd[*]}" \
    "${preflight_running[*]}" "${backup_cmd[*]}" "${stop_cmd[*]}" \
    "${preflight_stopped[*]}" "${start_cmd[*]}" "${rollback_cmd[*]}" <<'PY'
import json, sys
mode, rehearsal, approval, pre, backup, stop, pre2, start, rollback = sys.argv[1:]
print(json.dumps({
    "mode": mode,
    "rehearsal_args": rehearsal.split(),
    "approval": approval.split(),
    "preflight_before_stop": pre.split(),
    "backup": backup.split(),
    "stop": stop.split(),
    "preflight_after_stop": pre2.split(),
    "start": start.split(),
    "rollback": rollback.split(),
}, indent=2))
PY
  exit 0
fi

state_shutdown_started=0
state_previous_stopped=0
state_candidate_started=0
state_committed=0
state_rollback_active=0

write_failure_receipt() {
  local rc="$1" rollback_rc="$2"
  python3 - "$ROOT" "$MODE" "$rc" "$rollback_rc" <<'PY' >/dev/null 2>&1 || true
import json, sys, datetime
from pathlib import Path
root = Path(sys.argv[1]); mode = sys.argv[2]
receipt = {
    "schema": "atom-assignment-release-failure-1",
    "failed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "mode": mode,
    "exit_status": int(sys.argv[3]),
    "rollback_start_rc": int(sys.argv[4]),
    "database_restored": False,
    "user_data_preserved": True,
}
(root / "run").mkdir(parents=True, exist_ok=True)
(root / "run" / "deployment_failure.json").write_text(json.dumps(receipt, indent=2) + "\n")
PY
}

recover_on_exit() {
  rc=$?
  if [[ "$state_rollback_active" == "1" ]]; then
    exit "$rc"
  fi
  if [[ "$state_committed" == "1" && "$rc" == "0" ]]; then
    exit 0
  fi
  if [[ "$state_shutdown_started" == "0" ]]; then
    # Nothing disruptive happened; leave the running service alone.
    exit "$rc"
  fi
  state_rollback_active=1
  set +e
  echo "DEPLOYMENT FAILED rc=$rc after shutdown; attempting verified code rollback (data untouched)" >&2
  "${rollback_cmd[@]}" > "$ROOT/logs/rollback.log" 2>&1
  rollback_rc=$?
  if [[ "$rollback_rc" -eq 0 ]]; then
    echo "ROLLBACK RECOVERED previous release after failure rc=$rc" >&2
  else
    echo "ROLLBACK FAILED rc=$rollback_rc after deployment failure rc=$rc" >&2
    write_failure_receipt "$rc" "$rollback_rc"
  fi
  set -e
  exit "$rc"
}
trap recover_on_exit EXIT

# Authorization and local preconditions: no backup, shutdown or service call.
"${approval_cmd[@]}"
"${freshness_cmd[@]}"
if [[ ! -f "$PASSWORD_FILE" ]]; then
  echo "REFUSED: normal-login smoke password file missing: $PASSWORD_FILE" >&2
  exit 2
fi

"${preflight_running[@]}"
"${backup_cmd[@]}"

state_shutdown_started=1
"${stop_cmd[@]}"
state_previous_stopped=1

"${preflight_stopped[@]}"
"${start_cmd[@]}"
state_candidate_started=1

"$PY" "$KIT/smoke_auth.py" \
  --frontend "$FE_BASE" --api-base "$API_BASE" \
  --email "$EMAIL" --password-file "$PASSWORD_FILE" \
  --objective "$OBJECTIVE" --artifact-sha256 "$ARTIFACT_SHA" \
  --out-dir "$ROOT/run/auth-smoke"

# Persistence check on the earlier completed assignment.
"$PY" "$KIT/smoke_assignment.py" \
  --api-base "$API_BASE" --email "$EMAIL" --password-file "$PASSWORD_FILE" \
  --objective "$OBJECTIVE" --expected-sum "$EXPECTED_SUM" \
  --out "$ROOT/run/before-restart.json"

# Fresh read-only execution through the public authenticated interface.
"$PY" "$KIT/smoke_fresh_assignment.py" \
  --api-base "$API_BASE" --email "$EMAIL" --password-file "$PASSWORD_FILE" \
  --dataset-name "$FRESH_DATASET" --source "$FRESH_SOURCE" \
  --external-id "$FRESH_EXTERNAL_ID" --source-version "$FRESH_VERSION" \
  --sheet "$FRESH_SHEET" --measure "$FRESH_MEASURE" \
  --expected-sum "$EXPECTED_SUM" \
  --out "$ROOT/run/fresh-before-restart.json"

"${stop_cmd[@]}"
"${start_cmd[@]}"

"$PY" "$KIT/smoke_assignment.py" \
  --api-base "$API_BASE" --email "$EMAIL" --password-file "$PASSWORD_FILE" \
  --objective "$OBJECTIVE" --expected-sum "$EXPECTED_SUM" \
  --out "$ROOT/run/after-restart.json" --compare-to "$ROOT/run/before-restart.json"
"$PY" "$KIT/smoke_fresh_assignment.py" \
  --api-base "$API_BASE" --email "$EMAIL" --password-file "$PASSWORD_FILE" \
  --dataset-name "$FRESH_DATASET" --source "$FRESH_SOURCE" \
  --external-id "$FRESH_EXTERNAL_ID" --source-version "$FRESH_VERSION" \
  --sheet "$FRESH_SHEET" --measure "$FRESH_MEASURE" \
  --expected-sum "$EXPECTED_SUM" \
  --verify-snapshot "$ROOT/run/fresh-before-restart.json" \
  --out "$ROOT/run/fresh-after-restart.json"

"${status_cmd[@]}" > "$ROOT/run/final-status.json"

# Atomic receipt publication is the commit point. Keep the guard armed until
# this succeeds and the final health checks above are recorded.
RECEIPT_TMP="${RECEIPT}.tmp"
python3 - "$ROOT" "$MODE" "$RECEIPT_TMP" <<'PY'
import json, sys, datetime
from pathlib import Path
root = Path(sys.argv[1]); mode = sys.argv[2]; target = Path(sys.argv[3])
identity = json.loads((root / "RELEASE_IDENTITY.json").read_text())
receipt = {
    "schema": "atom-assignment-release-deployment-1",
    "deployed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "mode": mode,
    "release_commit": identity["release_commit"],
    "release_tag": identity["release_tag"],
    "product_tree_sha256": identity["product_tree_sha256"],
    "tested_runtime_commit": identity["tested_runtime_commit"],
    "frontend_build_id": identity["frontend_build_id"],
    "outbound_scope": identity["outbound_scope"],
    "send_authorized": False,
    "topology": identity["topology"],
    "auth_smoke": json.loads((root / "run" / "auth-smoke" / "auth-smoke.json").read_text()),
    "assignment_before_restart": json.loads((root / "run" / "before-restart.json").read_text()),
    "assignment_after_restart": json.loads((root / "run" / "after-restart.json").read_text()),
    "fresh_before_restart": json.loads((root / "run" / "fresh-before-restart.json").read_text()),
    "fresh_after_restart": json.loads((root / "run" / "fresh-after-restart.json").read_text()),
    "rollback_available": (root / "previous").is_symlink(),
    "database_restored": False,
    "user_data_preserved": True,
}
target.write_text(json.dumps(receipt, indent=2) + "\n")
PY
mv "$RECEIPT_TMP" "$RECEIPT"
state_committed=1

echo "DEPLOYMENT PASSED: $ROOT"
