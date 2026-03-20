#!/bin/bash
# Quality Test Runner Script
# Runs quality tests for flakiness detection and collection stability

# Change to backend directory
cd "$(dirname "$0")/../../../" || exit 1

# Default values
REPEAT=""
RANDOM_SEED=""
TEST_PATH="tests/integration/quality/"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --repeat=*)
            REPEAT="${1#*=}"
            shift
            ;;
        --repeat)
            REPEAT="$2"
            shift 2
            ;;
        --random-seed=*)
            RANDOM_SEED="${1#*=}"
            shift
            ;;
        --random-seed)
            RANDOM_SEED="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --repeat=N        Number of repeats for flakiness detection"
            echo "  --random-seed=N   Specific random seed for reproducibility"
            echo "  --help            Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run all quality tests"
            echo "  $0 --repeat=5                        # Run tests 5 times"
            echo "  $0 --repeat=5 --random-seed=1234     # Run with specific seed"
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
PYTEST_CMD="pytest -v $TEST_PATH"

# Add random seed if specified
if [ -n "$RANDOM_SEED" ]; then
    PYTEST_CMD="$PYTEST_CMD --randomly-seed=$RANDOM_SEED"
fi

# Add repeat count if specified
if [ -n "$REPEAT" ]; then
    PYTEST_CMD="$PYTEST_CMD --count=$REPEAT"
fi

# Print command
echo "Running: $PYTEST_CMD"
echo ""
echo "Quality tests detect flakiness and collection stability issues"
echo ""

# Run pytest and capture exit code
eval "$PYTEST_CMD"
EXIT_CODE=$?

# Print summary
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Quality tests passed"
    if [ -n "$REPEAT" ]; then
        echo "  Flakiness rate: 0% (all $REPEAT repeats passed)"
    fi
else
    echo "✗ Quality tests failed"
    if [ -n "$REPEAT" ]; then
        echo "  Check for flaky tests that failed in some repeats"
    fi
fi

exit $EXIT_CODE
