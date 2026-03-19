#!/bin/bash
################################################################################
# Soak Test Execution Script
#
# This script executes pytest-based soak tests with extended timeout control.
# Soak tests run for long durations to detect memory leaks and stability issues.
#
# Usage:
#   ./run_soak_tests.sh                    # Run all soak tests for 1 hour
#   ./run_soak_tests.sh -d 2h              # Run for 2 hours
#   ./run_soak_tests.sh -t test_file.py    # Run specific test file
#
# Reference: Phase 209 Plan 05
################################################################################

set -e  # Exit on error
trap 'echo "❌ Soak test interrupted"; exit 1' INT  # Trap Ctrl+C

# Default parameters
DURATION=${DURATION:-1h}
TESTS=${TESTS:-""}

# Parse command line arguments
while getopts "d:t:" opt; do
  case $opt in
    d) DURATION="$OPTARG" ;;
    t) TESTS="$OPTARG" ;;
    \?)
      echo "Usage: $0 [-d DURATION] [-t TEST_FILE]"
      echo ""
      echo "Options:"
      echo "  -d DURATION  Test duration (default: 1h, format: 30m, 2h, etc)"
      echo "  -t TEST_FILE Specific test file to run (default: all soak tests)"
      echo ""
      echo "Examples:"
      echo "  $0 -d 2h"
      echo "  $0 -t tests/soak/test_memory_stability.py::test_governance_cache_memory_stability_1hr"
      echo "  $0 -d 30m -t tests/soak/test_connection_pool.py"
      exit 1
      ;;
  esac
done

# Navigate to backend directory
cd "$(dirname "$0")/.."

# Create logs directory
mkdir -p tests/soak/logs

# Generate timestamp for log file
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="tests/soak/logs/soak_test_${TIMESTAMP}.log"

echo "=========================================="
echo "Soak Test Configuration"
echo "=========================================="
echo "Duration:     $DURATION"
echo "Tests:        ${TESTS:-All soak tests}"
echo "Log File:     $LOG_FILE"
echo "=========================================="
echo ""

# Build pytest command
PYTEST_CMD="pytest -m soak --timeout=$DURATION -v --tb=short --log-cli-level=INFO"

# Add specific test file if provided
if [ -n "$TESTS" ]; then
  PYTEST_CMD="$PYTEST_CMD $TESTS"
fi

# Run pytest with soak tests
echo "Starting soak tests..."
echo "Command: $PYTEST_CMD"
echo ""

$PYTEST_CMD 2>&1 | tee "$LOG_FILE"

# Capture pytest exit code
EXIT_CODE=${PIPESTATUS[0]}

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
  echo "✅ Soak test completed successfully"
  echo "📋 Log: $LOG_FILE"
else
  echo "❌ Soak test failed with exit code $EXIT_CODE"
  echo "📋 Log: $LOG_FILE"
fi
echo "=========================================="

exit $EXIT_CODE
