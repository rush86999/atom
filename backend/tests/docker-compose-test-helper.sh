#!/bin/bash
# Helper script to run tests with Docker Compose services (Valkey, etc.)
#
# Usage: ./tests/docker-compose-test-helper.sh [test_file]
#
# Examples:
#   ./tests/docker-compose-test-helper.sh test_agent_communication.py
#   ./tests/docker-compose-test-helper.sh  # Run all tests

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting Docker Compose services for testing...${NC}"

# Start Valkey service from Personal Edition
cd "$(dirname "$0")/.."
docker-compose -f docker-compose-personal.yml up -d valkey

# Wait for Valkey to be healthy
echo -e "${YELLOW}Waiting for Valkey to be healthy...${NC}"
timeout 30 bash -c 'until docker-compose -f docker-compose-personal.yml ps valkey | grep -q "healthy"; do sleep 1; done'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}Valkey is healthy!${NC}"
else
    echo -e "${RED}Valkey health check timed out${NC}"
    docker-compose -f docker-compose-personal.yml logs valkey
    exit 1
fi

# Run tests
echo -e "${YELLOW}Running tests...${NC}"
if [ -n "$1" ]; then
    pytest "tests/$1" -v
else
    pytest tests/ -v
fi

TEST_RESULT=$?

# Optionally: keep services running for debugging
echo -e "${YELLOW}Tests completed with exit code: $TEST_RESULT${NC}"
echo -e "${YELLOW}Docker Compose services still running. Stop with: docker-compose -f docker-compose-personal.yml down${NC}"

exit $TEST_RESULT
