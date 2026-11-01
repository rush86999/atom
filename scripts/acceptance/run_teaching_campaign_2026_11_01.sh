#!/usr/bin/env bash
# Campaign A: two-domain complex teaching/transfer/correction on the final
# candidate. Every restart is a real process restart against the same world.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORLD="${WORLD:?set WORLD to the long-run world}"
PASSWORD_FILE="${PASSWORD_FILE:?set PASSWORD_FILE}"
OUT="${OUT:?set OUT to a campaign evidence directory}"
PYTHON="${PYTHON:-$ROOT/backend/venv/bin/python}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:?set ADMIN_PASSWORD}"
BACKEND_PORT="${BACKEND_PORT:-8071}"
FRONTEND_PORT="${FRONTEND_PORT:-3130}"
FRONTEND="http://127.0.0.1:${FRONTEND_PORT}"

mkdir -p "$OUT"
log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT/runner.log"; }

stop_app() {
  local label="$1"
  for role in frontend backend; do
    local pidfile="$WORLD/${role}.pid"
    [ -f "$pidfile" ] || continue
    local pid
    pid="$(cat "$pidfile")"
    if kill -0 "$pid" 2>/dev/null; then
      log "stopping $label $role pid=$pid"
      kill -INT "$pid" 2>/dev/null || true
    fi
  done
  for _ in $(seq 1 30); do
    local alive=0
    for role in frontend backend; do
      local pidfile="$WORLD/${role}.pid"
      [ -f "$pidfile" ] || continue
      kill -0 "$(cat "$pidfile")" 2>/dev/null && alive=1
    done
    [ "$alive" -eq 0 ] && return 0
    sleep 1
  done
  for role in frontend backend; do
    local pidfile="$WORLD/${role}.pid"
    [ -f "$pidfile" ] || continue
    kill -9 "$(cat "$pidfile")" 2>/dev/null || true
  done
}

launch_app() {
  local label="$1"
  stop_app "$label"
  log "launching $label"
  (
    cd "$ROOT"
    env WORLD="$WORLD" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
      BACKEND_PORT="$BACKEND_PORT" FRONTEND_PORT="$FRONTEND_PORT" \
      PYTHON="$PYTHON" \
      bash scripts/acceptance/launch_integrated_local_candidate.sh
  ) > "$OUT/launch-${label}.log" 2>&1
  log "launched $label backend=$(cat "$WORLD/backend.pid") frontend=$(cat "$WORLD/frontend.pid")"
  curl -fsS "http://127.0.0.1:${BACKEND_PORT}/health" > "$OUT/health-${label}.json"
}

run_part1() {
  local domain="$1" csv="$2" objective="$3" correlation="$4" measure="$5"
  local context="$6" qualification="$7" candidate="$8" label="$9"
  log "part1 $domain"
  "$PYTHON" "$ROOT/scripts/acceptance/composite_long_running_part1.py" \
    --frontend "$FRONTEND" --password-file "$PASSWORD_FILE" \
    --csv "$csv" --out-dir "$OUT/$domain/part1" \
    --objective "$objective" --correlation "$correlation" \
    --measure "$measure" --context "$context" \
    --qualification "$qualification" --mapping-candidate "$candidate" \
    --domain-label "$label" \
    --agent-goal "Prepare $label documents from uploaded sheets, calculate totals, and explain missing context." \
    >> "$OUT/${domain}-part1.log" 2>&1
}

run_upload() {
  local domain="$1" file="$2"
  log "upload revised $domain source"
  "$PYTHON" "$ROOT/scripts/acceptance/campaign_upload.py" \
    --frontend "$FRONTEND" --password-file "$PASSWORD_FILE" \
    --file "$file" --out "$OUT/$domain/revised-source.json" \
    >> "$OUT/${domain}-upload.log" 2>&1
}

run_part2() {
  local domain="$1" part1="$2" objective="$3" source="$4" candidate="$5"
  local measure="$6" context="$7" qualification="$8" response="$9"
  log "part2 $domain"
  "$PYTHON" "$ROOT/scripts/acceptance/composite_long_running_part2.py" \
    --frontend "$FRONTEND" --password-file "$PASSWORD_FILE" \
    --out-dir "$OUT/$domain/part2" --part1 "$part1" \
    --second-objective "$objective" --second-source "$source" \
    --second-candidate "$candidate" --measure "$measure" \
    --context "$context" --qualification "$qualification" \
    --response "$response" --domain-label "$domain" \
    --outbox "$WORLD/controlled-outbox.jsonl" \
    >> "$OUT/${domain}-part2.log" 2>&1
}

# 1. Sales domain.
run_part1 sales /tmp/campaign1/campaign_sales_quote.csv \
  "Sum Price for the sales campaign quote" "sales-campaign-20261101" \
  Price sales licensed "Gross Amount" "sales quote"
run_upload sales /tmp/campaign1/campaign_sales_revised.csv
launch_app sales
run_part2 sales "$OUT/sales/part1/part1.json" \
  "Sum Price for the revised sales campaign sheet" \
  campaign_sales_revised.csv "Net Amount" Price sales licensed \
  "Delivery term: net 45 days from the invoice date."

# 2. Grants domain, different vocabulary and a 25-row source.
run_part1 grants /tmp/campaign1/campaign_grant_awards.csv \
  "Sum Award Amount for the grants campaign" "grants-campaign-20261101" \
  "Award Amount" grants authorized "Approved Amount" "grant award"
run_upload grants /tmp/campaign1/campaign_grant_revised.csv
launch_app grants
run_part2 grants "$OUT/grants/part1/part1.json" \
  "Sum Award Amount for the revised grants campaign" \
  campaign_grant_revised.csv "Awarded Value" "Award Amount" grants authorized \
  "Delivery term: within 30 days of award acceptance."

python3 - "$OUT" "$WORLD" "$(git -C "$ROOT" rev-parse HEAD)" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1]); world = pathlib.Path(sys.argv[2]); source = sys.argv[3]
summary = {"schema": "atom-teaching-campaign-2026-11-01", "source": source,
           "status": "passed", "domains": {}}
for domain, expected in (("sales", "550.00"), ("grants", "14687.50")):
    p1 = json.loads((out / domain / "part1" / "part1.json").read_text())
    p2 = json.loads((out / domain / "part2" / "part2.json").read_text())
    summary["domains"][domain] = {
        "part1_run_id": p1["run_id"],
        "part1_source_result": next(s.get("result_value") for s in p1["steps"] if s["step_id"] == "source-1"),
        "part1_expected_source_result": expected,
        "part1_teaching_revision": p1["teaching_revision"],
        "part2_teaching_revision_before": p2["teaching_revision_before"],
        "part2_teaching_revision_after_teach": p2["teaching_revision_after_teach"],
        "part2_status_after_restart": p2["status_after_restart"],
        "part2_status_after_completion": p2["status_after_completion"],
        "part2_artifact_sha256": p2["artifact"]["sha256"],
        "part2_artifact_font": p2["artifact"]["normal_font"],
        "part2_artifact_size": p2["artifact"]["normal_size"],
        "second_run_id": p2["second_run_id"],
        "second_teaching_revision": p2["second_teaching_revision"],
        "second_artifact_sha256": p2["second_artifact"]["sha256"],
        "second_artifact_font": p2["second_artifact"]["normal_font"],
        "second_artifact_size": p2["second_artifact"]["normal_size"],
        "outbox_lines_total": p2["outbox_lines"],
    }
    if summary["domains"][domain]["part1_source_result"] != expected:
        summary["status"] = "failed"
    if p2["status_after_completion"] != "completed":
        summary["status"] = "failed"
    if p2["teaching_revision_after_teach"] != p2["teaching_revision_before"]:
        summary["status"] = "failed"
    if p2["second_teaching_revision"] == p2["teaching_revision_before"]:
        summary["status"] = "failed"
summary["outbox_path"] = str(world / "controlled-outbox.jsonl")
summary["outbox_lines"] = len((world / "controlled-outbox.jsonl").read_text().splitlines()) if (world / "controlled-outbox.jsonl").exists() else 0
(out / "campaign.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
PY
log "campaign complete"
