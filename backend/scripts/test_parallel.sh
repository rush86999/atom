#!/bin/bash
# Test suite stability verification script
#
# Purpose: Compare sequential vs parallel test execution to verify performance
#          and detect flaky tests through randomization.
#
# Usage:
#   ./scripts/test_parallel.sh                    # Run all comparisons
#   SEQUENTIAL_ONLY=1 ./scripts/test_parallel.sh  # Run sequential only
#   PARALLEL_ONLY=1 ./scripts/test_parallel.sh    # Run parallel only
#   RANDOM_ONLY=1 ./scripts/test_parallel.sh      # Run random order only
#
# Expected Results:
#   - Sequential: Baseline timing (slowest)
#   - Parallel: 2-4x faster (depends on CPU cores)
#   - Random Order: Same pass/fail as sequential (no hidden dependencies)

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test selection (can be overridden via environment variables)
TEST_PATH="${TEST_PATH:-tests}"
VERBOSE="${VERBOSE:- -v}"

echo "=========================================="
echo "Test Suite Stability Verification"
echo "=========================================="
echo ""

# Sequential Baseline
if [[ -z "$SEQUENTIAL_ONLY" && -z "$PARALLEL_ONLY" && -z "$RANDOM_ONLY" || -n "$SEQUENTIAL_ONLY" ]]; then
    echo -e "${YELLOW}=== Sequential Baseline ===${NC}"
    echo "Running tests sequentially to establish baseline timing..."
    echo "Command: pytest ${TEST_PATH} ${VERBOSE}"
    echo ""

    time pytest "${TEST_PATH}" ${VERBOSE}

    echo ""
    echo -e "${GREEN}✓ Sequential baseline complete${NC}"
    echo ""
fi

# Parallel Execution
if [[ -z "$SEQUENTIAL_ONLY" && -z "$PARALLEL_ONLY" && -z "$RANDOM_ONLY" || -n "$PARALLEL_ONLY" ]]; then
    echo -e "${YELLOW}=== Parallel Execution ===${NC}"
    echo "Running tests in parallel using pytest-xdist..."
    echo "Configuration: -n auto --dist=loadscope"
    echo "  -n auto: Auto-detect CPU cores"
    echo "  --dist=loadscope: Group tests by module (better for shared fixtures)"
    echo "Command: pytest -n auto --dist=loadscope ${TEST_PATH} ${VERBOSE}"
    echo ""

    time pytest -n auto --dist=loadscope "${TEST_PATH}" ${VERBOSE}

    echo ""
    echo -e "${GREEN}✓ Parallel execution complete${NC}"
    echo ""
    echo "Performance Comparison:"
    echo "  - Parallel should be 2-4x faster than sequential"
    echo "  - Worker IDs (gw0, gw1, etc.) should appear in output"
    echo "  - Test results should match sequential (no isolation issues)"
    echo ""
fi

# Random Order (Flaky Detection)
if [[ -z "$SEQUENTIAL_ONLY" && -z "$PARALLEL_ONLY" && -z "$RANDOM_ONLY" || -n "$RANDOM_ONLY" ]]; then
    echo -e "${YELLOW}=== Random Order (Flaky Detection) ===${NC}"
    echo "Running tests in random order to detect hidden dependencies..."
    echo "Configuration: --random-order"
    echo "  --random-order: Randomize test execution order"
    echo "Purpose: Reveal tests that depend on execution order (anti-pattern)"
    echo "Command: pytest --random-order ${TEST_PATH} ${VERBOSE}"
    echo ""

    time pytest --random-order "${TEST_PATH}" ${VERBOSE}

    echo ""
    echo -e "${GREEN}✓ Random order execution complete${NC}"
    echo ""
    echo "Flaky Test Detection:"
    echo "  - If tests fail in random order but pass sequentially → hidden dependency"
    echo "  - Common causes: shared state, hardcoded IDs, improper cleanup"
    echo "  - Fix: Use unique_resource_name fixture and db_session for isolation"
    echo ""
fi

echo "=========================================="
echo "All stability checks complete!"
echo "=========================================="
echo ""
echo "Next Steps:"
echo "  1. Compare timing between sequential and parallel runs"
echo "  2. Verify test results are consistent across all modes"
echo "  3. Investigate any failures in random-order mode (isolation issues)"
echo "  4. Run parallel execution in CI/CD for faster feedback"
echo ""
echo "Documentation:"
echo "  - Test Isolation Patterns: backend/tests/docs/TEST_ISOLATION_PATTERNS.md"
echo "  - Flaky Test Guide: backend/tests/docs/FLAKY_TEST_GUIDE.md"
echo ""
