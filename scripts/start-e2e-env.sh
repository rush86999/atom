#!/bin/bash
# Start E2E UI test environment with Docker Compose
# Usage: ./scripts/start-e2e-env.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Starting E2E UI test environment..."
echo ""

# Start services in detached mode
docker-compose -f docker-compose-e2e-ui.yml up -d

echo "Docker Compose services started."
echo ""
echo "Waiting for services to be healthy..."
./scripts/wait-for-healthy.sh

echo ""
echo "E2E test environment ready!"
echo ""
echo "Access endpoints:"
echo "  Frontend:  http://localhost:3001"
echo "  Backend:   http://localhost:8001"
echo "  Database:  localhost:5434"
echo ""
echo "View logs:"
echo "  docker-compose -f docker-compose-e2e-ui.yml logs -f"
echo ""
echo "Stop environment:"
echo "  ./scripts/stop-e2e-env.sh"
echo ""
