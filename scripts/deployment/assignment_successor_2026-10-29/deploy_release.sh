#!/usr/bin/env bash
# One reversible deployment transaction for the assignment successor.
#
# Preconditions:
#   - the release is already prepared with prepare_release.py
#   - root/config/APPROVED exists (or REHEARSAL_APPROVED for --rehearsal)
#   - a password file is supplied for the normal login-form smoke
#
# The transaction backs up first, stops only this release's PIDs, starts the
# release, runs normal-auth + representative-assignment checks, restarts and
# compares. Any failure after the start flips back to the previous release.
# It never restores the database automatically.
set -euo pipefail

ROOT="${RELEASE_ROOT:-}"
MODE="production"
if [[ "${1:-}" == "--rehearsal" ]]; then MODE="rehearsal"; shift; fi
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
RECEIPT="$ROOT/run/deployment_receipt.json"
mkdir -p "$ROOT/run" "$ROOT/logs"

if [[ "$MODE" == "production" && ! -f "$ROOT/config/APPROVED" ]]; then
  echo "REFUSED: config/APPROVED is missing; deployment is not authorized" >&2
  exit 2
fi
if [[ ! -f "$PASSWORD_FILE" ]]; then
  echo "REFUSED: normal-login smoke password file missing: $PASSWORD_FILE" >&2
  exit 2
fi

rollback_on_error() {
  rc=$?
  echo "DEPLOYMENT FAILED rc=$rc; attempting code rollback (data untouched)" >&2
  if [[ -L "$ROOT/previous" ]]; then
    "$PY" "$KIT/release_tool.py" --root "$ROOT" rollback > "$ROOT/logs/rollback.log" 2>&1 || true
  else
    "$PY" "$KIT/release_tool.py" --root "$ROOT" stop > "$ROOT/logs/rollback-stop.log" 2>&1 || true
  fi
  exit "$rc"
}

"$PY" "$KIT/release_tool.py" --root "$ROOT" preflight \
  --rehearsal $([[ "$MODE" == "rehearsal" ]] && echo --rehearsal) \
  --ignore-running-ports
"$PY" "$KIT/release_tool.py" --root "$ROOT" backup --label "predeploy-${MODE}"
"$PY" "$KIT/release_tool.py" --root "$ROOT" stop

trap rollback_on_error ERR
"$PY" "$KIT/release_tool.py" --root "$ROOT" preflight \
  --rehearsal $([[ "$MODE" == "rehearsal" ]] && echo --rehearsal)
"$PY" "$KIT/release_tool.py" --root "$ROOT" start \
  --rehearsal $([[ "$MODE" == "rehearsal" ]] && echo --rehearsal)

"$PY" "$KIT/smoke_auth.py" \
  --frontend "$FE_BASE" --api-base "$API_BASE" \
  --email "$EMAIL" --password-file "$PASSWORD_FILE" \
  --objective "$OBJECTIVE" --artifact-sha256 "$ARTIFACT_SHA" \
  --out-dir "$ROOT/run/auth-smoke"

"$PY" "$KIT/smoke_assignment.py" \
  --api-base "$API_BASE" --email "$EMAIL" --password-file "$PASSWORD_FILE" \
  --objective "$OBJECTIVE" --expected-sum "$EXPECTED_SUM" \
  --out "$ROOT/run/before-restart.json"

"$PY" "$KIT/release_tool.py" --root "$ROOT" stop
"$PY" "$KIT/release_tool.py" --root "$ROOT" start \
  --rehearsal $([[ "$MODE" == "rehearsal" ]] && echo --rehearsal)

"$PY" "$KIT/smoke_assignment.py" \
  --api-base "$API_BASE" --email "$EMAIL" --password-file "$PASSWORD_FILE" \
  --objective "$OBJECTIVE" --expected-sum "$EXPECTED_SUM" \
  --out "$ROOT/run/after-restart.json" --compare-to "$ROOT/run/before-restart.json"

"$PY" "$KIT/release_tool.py" --root "$ROOT" status > "$ROOT/run/final-status.json"

trap - ERR
python3 - "$ROOT" "$MODE" <<'PY'
import json, sys, datetime
from pathlib import Path
root = Path(sys.argv[1]); mode = sys.argv[2]
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
    "rollback_available": (root / "previous").is_symlink(),
    "database_restored": False,
    "user_data_preserved": True,
}
(root / "run" / "deployment_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps({"ok": True, "receipt": str(root / "run" / "deployment_receipt.json")}, indent=2))
PY

echo "DEPLOYMENT PASSED: $ROOT"
