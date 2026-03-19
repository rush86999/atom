#!/bin/bash
################################################################################
# Load Test Execution Script
#
# This script executes Locust load tests with configurable parameters.
# It generates timestamped HTML and JSON reports for analysis.
#
# Usage:
#   ./run_load_tests.sh                    # Use defaults (100 users, 5m)
#   ./run_load_tests.sh -u 200 -r 20       # Custom users and spawn rate
#   ./run_load_tests.sh -t 10m -h http://localhost:8000
#
# Reference: Phase 209 Plan 05
################################################################################

set -e  # Exit on error

# Default parameters
USERS=${USERS:-100}
SPAWN_RATE=${SPAWN_RATE:-10}
DURATION=${DURATION:-5m}
HOST=${HOST:-http://localhost:8000}

# Parse command line arguments
while getopts "u:r:t:h:" opt; do
  case $opt in
    u) USERS="$OPTARG" ;;
    r) SPAWN_RATE="$OPTARG" ;;
    t) DURATION="$OPTARG" ;;
    h) HOST="$OPTARG" ;;
    \?)
      echo "Usage: $0 [-u USERS] [-r SPAWN_RATE] [-t DURATION] [-h HOST]"
      echo ""
      echo "Options:"
      echo "  -u USERS         Number of users (default: 100)"
      echo "  -r SPAWN_RATE    Users spawned per second (default: 10)"
      echo "  -t DURATION      Test duration (default: 5m, format: 1m, 1h, etc)"
      echo "  -h HOST          Target host (default: http://localhost:8000)"
      echo ""
      echo "Examples:"
      echo "  $0 -u 200 -r 20 -t 10m"
      echo "  $0 -u 50 -t 15m -h http://staging.example.com"
      exit 1
      ;;
  esac
done

# Navigate to backend directory
cd "$(dirname "$0")/.."

# Create reports directory if not exists
mkdir -p tests/load/reports

# Generate timestamp for report filenames
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
REPORT_BASE="tests/load/reports/load_test_${TIMESTAMP}"

echo "=========================================="
echo "Load Test Configuration"
echo "=========================================="
echo "Users:        $USERS"
echo "Spawn Rate:   $SPAWN_RATE users/sec"
echo "Duration:     $DURATION"
echo "Host:         $HOST"
echo "Report Base:  $REPORT_BASE"
echo "=========================================="
echo ""

# Run Locust with specified parameters
locust -f tests/load/locustfile.py \
  --headless \
  -u "$USERS" \
  -r "$SPAWN_RATE" \
  -t "$DURATION" \
  --host "$HOST" \
  --html "${REPORT_BASE}.html" \
  --json "${REPORT_BASE}.json" \
  --logfile "${REPORT_BASE}.log"

# Capture Locust exit code
EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
  echo "✅ Load test completed successfully"
  echo "📊 Report: ${REPORT_BASE}.html"
  echo "📊 Data:   ${REPORT_BASE}.json"
  echo "📋 Log:    ${REPORT_BASE}.log"
else
  echo "❌ Load test failed with exit code $EXIT_CODE"
fi
echo "=========================================="

exit $EXIT_CODE
