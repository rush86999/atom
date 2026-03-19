#!/bin/bash
# Contract Test Runner Script
# Runs API contract tests using Schemathesis with endpoint filtering

# Change to backend directory
cd "$(dirname "$0")/../../../" || exit 1

# Default values
VERBOSE=false
ENDPOINT=""
TEST_PATH="tests/integration/contracts/"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE=true
            shift
            ;;
        --endpoint=*)
            ENDPOINT="${1#*=}"
            shift
            ;;
        --endpoint)
            ENDPOINT="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --verbose        Verbose output (-vv)"
            echo "  --endpoint=NAME  Run specific endpoint tests"
            echo "  --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                           # Run all contract tests"
            echo "  $0 --endpoint=agent          # Run agent endpoint tests"
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
PYTEST_CMD="pytest -m contract"

# Add verbose flag if requested
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -vv"
else
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Add test path
PYTEST_CMD="$PYTEST_CMD $TEST_PATH"

# Add endpoint filter if specified
if [ -n "$ENDPOINT" ]; then
    PYTEST_CMD="$PYTEST_CMD -k $ENDPOINT"
fi

# Add pytest options
PYTEST_CMD="$PYTEST_CMD --tb=short"

# Print command
echo "Running: $PYTEST_CMD"
echo ""
echo "Contract tests validate API schema compliance"
echo ""

# Run pytest and capture exit code
eval "$PYTEST_CMD"
EXIT_CODE=$?

# Print summary
echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ Contract tests passed - API schemas validated"
else
    echo "✗ Contract tests failed - Schema violations detected"
fi

exit $EXIT_CODE
