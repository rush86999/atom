#!/bin/bash
# RQ Worker Startup Script for ATOM Platform
#
# This script starts RQ workers to process background tasks.
# Workers handle scheduled social media posts and other async jobs.
#
# Usage:
#   ./start_workers.sh [queue_names...]
#
# Examples:
#   ./start_workers.sh                    # Start default worker
#   ./start_workers.sh social_media        # Start social media worker
#   ./start_workers.sh social_media default workflows  # Start multiple workers

set -e

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default configuration
REDIS_URL=${REDIS_URL:-"redis://localhost:6379/0"}
WORKER_NAME=${WORKER_NAME:-"atom-worker"}
LOG_LEVEL=${LOG_LEVEL:-"INFO"}
LOG_FILE=${LOG_FILE:-"logs/rq-worker.log"}

# Create logs directory if it doesn't exist
mkdir -p logs

# Queue names (default to all queues if none specified)
QUEUES=${*:-"social_media workflows default"}

echo "=========================================="
echo "ATOM RQ Worker"
echo "=========================================="
echo "Redis URL: $REDIS_URL"
echo "Worker Name: $WORKER_NAME"
echo "Queues: $QUEUES"
echo "Log Level: $LOG_LEVEL"
echo "Log File: $LOG_FILE"
echo "=========================================="

# Check if rq is installed
if ! command -v rq &> /dev/null; then
    echo "Error: 'rq' command not found"
    echo "Install with: pip install rq"
    exit 1
fi

# Start the worker
echo "Starting worker..."
rq worker \
    $QUEUES \
    --url "$REDIS_URL" \
    --name "$WORKER_NAME" \
    --log-level "$LOG_LEVEL" \
    --logfile "$LOG_FILE" \
    --pidfile "tmp/rq-worker.pid" \
    --mkdir \
    --max-jobs 500 \
    --default-result-ttl 86400

echo "Worker stopped"
