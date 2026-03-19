#!/bin/bash
# Integration Test Runner Script
# Runs integration tests with optional coverage and filtering

# Change to backend directory
cd "$(dirname "$0")/../../../" || exit 1

# Default values
COVERAGE=false
VERBOSE=false
FILTER=""
TEST_PATH="tests/integration/workflows/"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --coverage)
            COVERAGE=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --filter=*)
            FILTER="${1#*=}"
            shift
            ;;
        --filter)
            FILTER="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --coverage       Enable coverage reporting"
            echo "  --verbose        Verbose output (-vv)"
            echo "  --filter=NAME    Run specific test file or pattern"
            echo "  --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                                    # Run all integration tests"
            echo "  $0 --coverage                        # Run with coverage"
            echo "  $0 --filter=test_workflow_engine_e2e # Run specific test"
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
PYTEST_CMD="pytest"

# Add coverage if requested
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=backend --cov-report=term-missing --cov-report=html"
fi

# Add verbose flag if requested
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -vv"
else
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add test path
if [ -n "$FILTER" ]; then
    PYTEST_CMD="$PYTEST_CMD $TEST_PATH$FILTER"
else
    PYTEST_CMD="$PYTEST_CMD $TEST_PATH"
fi

# Add pytest options
PYTEST_CMD="$PYTEST_CMD --tb=short --maxfail=5"

# Print command
echo "Running: $PYTEST_CMD"
echo ""

# Run pytest and capture exit code
eval "$PYTEST_CMD"
EXIT_CODE=$?

# Print summary
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Integration tests passed"
else
    echo "✗ Integration tests failed"
fi

exit $EXIT_CODE
