#!/bin/bash
# Stop E2E UI test environment and clean up volumes
# Usage: ./scripts/stop-e2e-env.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "Stopping E2E UI test environment..."
echo ""

# Stop and remove containers, networks, and volumes
docker-compose -f docker-compose-e2e-ui.yml down -v

echo ""
echo "✓ E2E test environment stopped and volumes cleaned."
echo ""
echo "Containers removed:"
echo "  - atom-postgres-e2e"
echo "  - atom-backend-e2e"
echo "  - atom-frontend-e2e"
echo ""
echo "Network removed:"
echo "  - e2e_test_network"
echo ""
echo "Volumes removed:"
echo "  - postgres_data_e2e"
echo ""
