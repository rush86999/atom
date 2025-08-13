#!/bin/bash
set -e

# This script is designed to be run from the `atomic-docker` directory.
# Example: ./python-api/ingestion_pipeline/run_ingestion_tests.sh

# The python executable to use
PYTHON_EXEC="/home/jules/.pyenv/shims/python"

# The requirements file relative to the execution directory (`atomic-docker`)
REQUIREMENTS_FILE="./python-api/ingestion_pipeline/requirements.txt"

# The test directory relative to the execution directory (`atomic-docker`)
TEST_DIR="./python-api/ingestion_pipeline/"

echo "--- Installing dependencies ---"
"$PYTHON_EXEC" -m pip install -r "$REQUIREMENTS_FILE"

echo "--- Installing test dependencies ---"
"$PYTHON_EXEC" -m pip install pytest pytest-asyncio

echo "--- Running tests ---"
"$PYTHON_EXEC" -m pytest "$TEST_DIR"
