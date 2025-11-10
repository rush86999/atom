#!/bin/bash

# ATOM Backend Keep-Alive Script
# Simple script to ensure backend stays running

set -e

# Configuration
BACKEND_PORT=8001
HEALTH_URL="http://localhost:$BACKEND_PORT/health"
LOG_FILE="logs/keep_alive.log"
PID_FILE=".keep_alive.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    log "${GREEN}✅ $1${NC}"
}

warning() {
    log "${YELLOW}⚠️  $1${NC}"
}

error() {
    log "${RED}❌ $1${NC}"
}

# Check if backend is healthy
check_health() {
    if curl -s --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Get backend PID
get_backend_pid() {
    lsof -ti:$BACKEND_PORT 2>/dev/null || echo ""
}

# Kill backend processes
kill_backend() {
    local pids=$(get_backend_pid)
    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null || true
        sleep 2
        # Force kill if still running
        local remaining=$(get_backend_pid)
        if [ -n "$remaining" ]; then
            kill -9 $remaining 2>/dev/null || true
        fi
    fi
}

# Start backend
start_backend() {
    log "Starting backend..."

    # Try different backend files
    if [ -f "backend/fixed_main_api_app.py" ]; then
        python backend/fixed_main_api_app.py &
    elif [ -f "robust_backend.py" ]; then
        python robust_backend.py &
    elif [ -f "start_simple_backend.py" ]; then
        python start_simple_backend.py &
    else
        error "No backend file found"
        return 1
    fi

    local backend_pid=$!
    echo $backend_pid > .backend.pid
    log "Backend started with PID: $backend_pid"

    # Wait for health
    local attempts=0
    while [ $attempts -lt 30 ]; do
        if check_health; then
            success "Backend is healthy"
            return 0
        fi

        if ! ps -p $backend_pid > /dev/null 2>&1; then
            error "Backend process died"
            return 1
        fi

        sleep 2
        ((attempts++))
    done

    error "Backend failed to start"
    kill $backend_pid 2>/dev/null || true
    return 1
}

# Main loop
main() {
    log "🚀 Starting ATOM Backend Keep-Alive"

    # Setup
    mkdir -p logs
    echo $$ > "$PID_FILE"

    # Cleanup handler
    trap 'log "Shutting down..."; kill_backend; rm -f "$PID_FILE" .backend.pid; exit 0' SIGINT SIGTERM

    # Initial cleanup
    kill_backend

    # Initial start
    if start_backend; then
        success "Initial backend start successful"
    else
        error "Initial backend start failed"
        exit 1
    fi

    # Monitoring loop
    local restart_count=0
    while true; do
        if check_health; then
            # Healthy - log every 5 minutes
            if [ $(( $(date +%s) % 300 )) -eq 0 ]; then
                log "Backend running normally"
            fi
        else
            # Unhealthy - restart
            warning "Backend unhealthy, restarting..."
            kill_backend
            sleep 3

            if start_backend; then
                ((restart_count++))
                success "Backend restarted (count: $restart_count)"
            else
                error "Backend restart failed"
            fi
        fi

        sleep 10
    done
}

# Handle arguments
case "${1:-}" in
    status)
        if check_health; then
            echo "HEALTHY"
        else
            echo "UNHEALTHY"
        fi
        ;;
    stop)
        if [ -f "$PID_FILE" ]; then
            local pid=$(cat "$PID_FILE")
            kill $pid 2>/dev/null && echo "Stopped" || echo "Not running"
        else
            echo "Not running"
        fi
        ;;
    restart)
        if [ -f "$PID_FILE" ]; then
            local pid=$(cat "$PID_FILE")
            kill $pid 2>/dev/null && sleep 2
        fi
        exec "$0"
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    *)
        main
        ;;
esac
