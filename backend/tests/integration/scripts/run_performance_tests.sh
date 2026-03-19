#!/bin/bash
# Performance Benchmark Runner Script
# Runs performance benchmarks using pytest-benchmark

# Change to backend directory
cd "$(dirname "$0")/../../../" || exit 1

# Default values
HISTOGRAM=false
SAVE=false
COMPARE=""
TEST_PATH="tests/integration/performance/"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --histogram)
            HISTOGRAM=true
            shift
            ;;
        --save)
            SAVE=true
            shift
            ;;
        --compare=*)
            COMPARE="${1#*=}"
            shift
            ;;
        --compare)
            COMPARE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --histogram       Generate histogram output"
            echo "  --save            Save benchmark data for historical tracking"
            echo "  --compare=FILE    Compare to previous run"
            echo "  --help            Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                              # Run all benchmarks"
            echo "  $0 --histogram --save           # Run with histogram and save"
            echo "  $0 --compare=.benchmarks/001    # Compare to previous run"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest --benchmark-only -v $TEST_PATH"

# Add benchmark options
if [ "$SAVE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --benchmark-autosave"
fi

if [ "$HISTOGRAM" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --benchmark-histogram"
fi

if [ -n "$COMPARE" ]; then
    PYTEST_CMD="$PYTEST_CMD --benchmark-compare=$COMPARE"
fi

# Print command
echo "Running: $PYTEST_CMD"
echo ""
echo "Performance benchmarks measure API latency and database query performance"
echo ""

# Run pytest and capture exit code
eval "$PYTEST_CMD"
EXIT_CODE=$?

# Print summary
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Performance benchmarks completed"
    echo "  Review P50, P95, P99 metrics above"
else
    echo "✗ Performance benchmarks failed"
fi

exit $EXIT_CODE
