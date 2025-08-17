#!/bin/bash
# Autonomous System Unified Startup Script
# Usage: ./start-autonomous.sh [user-id]

set -e

# Configuration
USER_ID=${1:-"autonomous-demo"}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[Autonomous]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Main startup function
start_autonomous_system() {
    log "🚀 Starting autonomous system for user: $USER_ID"

    # Ensure Python environment is ready
    if [ ! -f "$SCRIPT_DIR/atomic-docker/python-api/venv/bin/activate" ]; then
        log "📦 Setting up Python environment..."
        mkdir -p "$SCRIPT_DIR/atomic-docker/python-api/logs"

        cd "$SCRIPT_DIR/atomic-docker/python-api"
        if command -v python3 >/dev/null 2>&1; then
            python3 -m venv venv
            source venv/bin/activate
            pip install -r requirements.txt
            log "✅ Python environment ready"
        else
            error "Python 3 required"
            exit 1
        fi
    fi

    # Start Redis
    if command -v redis-cli >/dev/null 2>&1; then
        if ! redis-cli ping >/dev/null 2>&1; then
            log "🔧 Starting Redis server locally..."
            nohup redis-server --port 6379 > "$SCRIPT_DIR/atomic-docker/python-api/logs/redis.log" 2>&1 &
            sleep 3
        fi
    elif command -v docker >/dev/null 2>&1; then
        if ! docker ps | grep redis >/dev/null 2>&1; then
            log "🔧 Starting Redis container..."
            docker run -d --name autonomous-redis -p 6379:6379 redis:7-alpine >/dev/null 2>&1 || true
            sleep 3
        fi
    fi

    # Start Celery workers
    log "⚡ Starting Celery workers..."
    cd "$SCRIPT_DIR/atomic-docker/python-api"
    source venv/bin/activate

    # Kill existing workers
    pkill -f "celery -A workflows" || true
    sleep 2

    # Start fresh workers
    nohup celery -A workflows.celery_app worker --loglevel=info --autoscale=8,2 \
        > logs/worker.log 2>&1 &
    nohup celery -A workflows.celery_app beat --loglevel=info \
        > logs/beat.log 2>&1 &

    cd "$SCRIPT_DIR"

    # Start API server
    log "🌐 Starting autonomous API server..."
    cd "$SCRIPT_DIR/atomic-docker/python-api"
    source venv/bin/activate

    nohup python -m uvicorn main:app --host 0.0.0.0 --port 8004 \
        > logs/server.log 2>&1 &

    cd "$SCRIPT_DIR"
    sleep 3

    log "✅ Autonomous system started!"
    log "📊 Monitor logs: tail -f atomic-docker/python-api/logs/*.log"
    log "🔗 API available at: http://localhost:8004/docs"

    # Test system health
    if curl -s http://localhost:8004/health >/dev/null; then
        log "🎯 System health: READY"
    else
        warning "⚠️ API server may still be starting"
    fi
}

# Stop function
stop_autonomous_system() {
    log "🛑 Stopping autonomous system..."

    pkill -f "celery -A workflows" || true
    pkill -f "uvicorn main:app" || true
    pkill -f "redis-server" || true

    if command -v docker >/dev/null 2>&1; then
        docker stop autonomous-redis >/dev/null 2>&1 || true
    fi

    log "✅ System stopped"
}

# Main command handling
case "${1:-start}" in
    start)
        start_autonomous_system
        ;;
    stop)
        stop_autonomous_system
        ;;
    restart)
        stop_autonomous_system
        sleep 2
        start_autonomous_system
        ;;
    *)
        echo "Usage: $0 [start|stop|restart] [user-id]"
        exit 1
        ;;
esac

# Keep script running for demo
if [ "${1:-start}" = "start" ]; then
