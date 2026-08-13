#!/bin/zsh
# RAM-controlled coverage baseline: serial chunks, one process at a time.
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"
export OPENCODE_API_KEY=""
export TURN_FACT_EXTRACTION_ENABLED=false
export ATOM_STAGE_ROUTING_ENABLED=false
export ATOM_OBJECTIVE_LOOP_ENABLED=false
mkdir -p cov_wave_baseline
: > cov_wave_baseline/durations.log

run_chunk() {
  local name=$1; shift
  echo "[$(date +%T)] chunk $name start"
  local t0=$(date +%s)
  COVERAGE_FILE="cov_wave_baseline/.coverage.$name" ./venv/bin/python -m coverage run --source=core,api,integrations -m pytest "$@" -q -p no:cacheprovider --no-header > "cov_wave_baseline/out_$name.log" 2>&1
  local rc=$?
  local t1=$(date +%s)
  echo "[$(date +%T)] chunk $name done rc=$rc in $((t1-t0))s: $(tail -1 cov_wave_baseline/out_$name.log)" | tee -a cov_wave_baseline/durations.log
}

run_chunk api tests/api || true
run_chunk core tests/core || true
run_chunk misc tests/boundary_conditions tests/cli tests/concurrent_operations tests/contract tests/critical_error_paths tests/error_paths tests/failure_modes tests/coverage_expansion tests/database || true
run_chunk top tests/test_*.py || true

echo "[$(date +%T)] combining"
cd cov_wave_baseline
../venv/bin/python -m coverage combine .coverage.*
../venv/bin/python -m coverage report --sort=cover > report_all.txt 2>&1
../venv/bin/python -m coverage report --sort=cover --skip-covered > report_gaps.txt 2>&1
../venv/bin/python -m coverage json > coverage.json 2>&1
echo "[$(date +%T)] BASELINE DONE"
