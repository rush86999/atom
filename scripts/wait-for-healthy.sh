#!/bin/bash
# Wait for all services in docker-compose-e2e-ui.yml to be healthy
# Usage: ./scripts/wait-for-healthy.sh [timeout_seconds]
# Default timeout: 120 seconds

set -e

TIMEOUT=${1:-120}
ELAPSED=0
SLEEP_INTERVAL=2

echo "Waiting for services to be healthy (timeout: ${TIMEOUT}s)..."

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Check PostgreSQL health
    if docker ps --filter "name=atom-postgres-e2e" --filter "health=healthy" | grep -q atom-postgres-e2e; then
        POSTGRES_READY=true
    else
        POSTGRES_READY=false
    fi

    # Check Backend health
    if docker ps --filter "name=atom-backend-e2e" --filter "health=healthy" | grep -q atom-backend-e2e; then
        BACKEND_READY=true
    else
        BACKEND_READY=false
    fi

    # Check Frontend health
    if docker ps --filter "name=atom-frontend-e2e" --filter "health=healthy" | grep -q atom-frontend-e2e; then
        FRONTEND_READY=true
    else
        FRONTEND_READY=false
    fi

    # Print status
    echo "[$(date +%H:%M:%S)] PostgreSQL: $([ "$POSTGRES_READY" = true ] && echo '✓ Healthy' || echo '→ Waiting'), Backend: $([ "$BACKEND_READY" = true ] && echo '✓ Healthy' || echo '→ Waiting'), Frontend: $([ "$FRONTEND_READY" = true ] && echo '✓ Healthy' || echo '→ Waiting')"

    # Check if all services are healthy
    if [ "$POSTGRES_READY" = true ] && [ "$BACKEND_READY" = true ] && [ "$FRONTEND_READY" = true ]; then
        echo ""
        echo "✓ All services are healthy!"
        echo ""
        echo "Services:"
        echo "  - PostgreSQL: localhost:5434"
        echo "  - Backend:    http://localhost:8001"
        echo "  - Frontend:   http://localhost:3001"
        echo ""
        exit 0
    fi

    sleep $SLEEP_INTERVAL
    ELAPSED=$((ELAPSED + SLEEP_INTERVAL))
done

echo ""
echo "✗ Timeout waiting for services to be healthy"
echo ""
echo "Check service logs:"
echo "  docker logs atom-postgres-e2e"
echo "  docker logs atom-backend-e2e"
echo "  docker logs atom-frontend-e2e"
echo ""
exit 1
