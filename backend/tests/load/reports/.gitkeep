# Load Test Reports Directory

This directory stores load test results and baseline files for performance regression detection.

## Directory Structure

- `baseline.json` - Reference performance metrics for regression detection
- `load_test_*.json` - Historical Locust JSON results
- `load_test_*.html` - Historical HTML reports
- `load_test_*.log` - Historical test logs

## Updating Baseline

**Important:** Only update `baseline.json` on the main branch after verifying that performance improvements are legitimate.

To update the baseline:

```bash
# Run load tests
./backend/tests/scripts/run_load_tests.sh -u 200 -r 20 -t 10m

# Copy results to baseline
cp backend/tests/load/reports/load_test_<TIMESTAMP>.json backend/tests/load/reports/baseline.json

# Commit changes
git add backend/tests/load/reports/baseline.json
git commit -m "perf: update load test baseline to <TIMESTAMP>"
```

## Performance Regression Detection

Compare new results against baseline:

```bash
./backend/tests/scripts/compare_performance.py \
  backend/tests/load/reports/baseline.json \
  backend/tests/load/reports/load_test_<TIMESTAMP>.json
```

Exit code 1 indicates regression detected.

## Git Configuration

The `.gitignore` in this directory ignores all reports except `baseline.json` to keep repository size manageable.
