#!/bin/bash

# ATOM Backend - Final Startup Solution
# Production-ready script to start and maintain the backend API

set -e

# Configuration
BACKEND_PORT=8001
HEALTH_URL="http://localhost:$BACKEND_PORT/health"
LOG_FILE="logs/backend_final.log"
PID_FILE=".backend_final.pid"
MAX_RESTARTS=1000
CHECK_INTERVAL=10

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local message="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${BLUE}[${timestamp}]${NC} $message" | tee -a "$LOG_FILE"
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

# Create necessary directories
setup_environment() {
    mkdir -p logs data tmp
    touch "$LOG_FILE"
    chmod 644 "$LOG_FILE"
}

# Check if backend is healthy
check_backend_health() {
    if curl -s --max-time 5 "$HEALTH_URL" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Get backend process ID
get_backend_pid() {
    lsof -ti:$BACKEND_PORT 2>/dev/null || echo ""
}

# Kill all backend processes
kill_backend_processes() {
    local pids=$(get_backend_pid)
    if [ -n "$pids" ]; then
        log "Stopping backend processes: $pids"
        kill $pids 2>/dev/null || true
        sleep 2

        # Force kill any remaining processes
        local remaining_pids=$(get_backend_pid)
        if [ -n "$remaining_pids" ]; then
            log "Force stopping remaining processes"
            kill -9 $remaining_pids 2>/dev/null || true
        fi
    fi

    # Also kill by process name patterns
    pkill -f "python.*backend" 2>/dev/null || true
    pkill -f "uvicorn" 2>/dev/null || true
    pkill -f "fixed_main_api_app" 2>/dev/null || true

    sleep 2
}

# Start backend process
start_backend() {
    local attempt=$1
    local backend_pid=""

    log "Starting backend (attempt $attempt)..."

    # Try backend files in order of preference
    if [ -f "backend/fixed_main_api_app.py" ]; then
        log "Starting fixed FastAPI backend..."
        python backend/fixed_main_api_app.py &
        backend_pid=$!
    elif [ -f "robust_backend.py" ]; then
        log "Starting robust backend..."
        python robust_backend.py &
        backend_pid=$!
    elif [ -f "production_backend.py" ]; then
        log "Starting production backend..."
        python production_backend.py &
        backend_pid=$!
    elif [ -f "start_simple_backend.py" ]; then
        log "Starting simple backend..."
        python start_simple_backend.py &
        backend_pid=$!
    else
        error "No backend startup file found"
        return 1
    fi

    echo "$backend_pid" > .backend.pid
    log "Backend started with PID: $backend_pid"

    # Wait for backend to become healthy
    local health_attempts=0
    local max_health_attempts=30

    while [ $health_attempts -lt $max_health_attempts ]; do
        if check_backend_health; then
            success "Backend is healthy and responding on port $BACKEND_PORT"
            return 0
        fi

        # Check if process is still running
        if ! ps -p $backend_pid > /dev/null 2>&1; then
            error "Backend process died during startup"
            return 1
        fi

        sleep 2
        ((health_attempts++))
    done

    error "Backend failed to become healthy within timeout"
    kill $backend_pid 2>/dev/null || true
    return 1
}

# Monitor backend health and restart if needed
monitor_backend() {
    local restart_count=0
    local consecutive_failures=0
    local last_success_time=$(date +%s)

    log "Starting backend monitoring loop..."

    while [ $restart_count -lt $MAX_RESTARTS ]; do
        if check_backend_health; then
            # Backend is healthy
            if [ $consecutive_failures -gt 0 ]; then
                success "Backend recovered after $consecutive_failures failures"
                consecutive_failures=0
            fi

            last_success_time=$(date +%s)

            # Log periodic status (every 5 minutes)
            if [ $(( $(date +%s) % 300 )) -eq 0 ]; then
                local uptime=$(($(date +%s) - $last_success_time))
                log "Backend running normally - uptime: ${uptime}s, restarts: $restart_count"
            fi

        else
            # Backend is unhealthy
            ((consecutive_failures++))
            warning "Backend health check failed (consecutive failures: $consecutive_failures)"

            # Check if process exists but is unresponsive
            local backend_pid=$(get_backend_pid)
            if [ -n "$backend_pid" ]; then
                warning "Backend process $backend_pid exists but is unresponsive"
            fi

            # Clean up existing processes
            kill_backend_processes

            # Implement exponential backoff for restarts
            local backoff_delay=$((CHECK_INTERVAL * (2 ** (consecutive_failures - 1))))
            backoff_delay=$((backoff_delay > 60 ? 60 : backoff_delay)) # Cap at 60 seconds

            if [ $consecutive_failures -gt 1 ]; then
                warning "Implementing exponential backoff: waiting ${backoff_delay}s"
                sleep $backoff_delay
            else
                sleep 3
            fi

            # Restart backend
            if start_backend $((restart_count + 1)); then
                ((restart_count++))
                consecutive_failures=0
                success "Backend restarted successfully (total restarts: $restart_count)"

                # Reset counter after prolonged stability (1 hour)
                if [ $restart_count -ge 10 ] && [ $(($(date +%s) - $last_success_time)) -gt 3600 ]; then
                    log "Resetting restart counter after prolonged stability"
                    restart_count=0
                fi
            else
                error "Backend restart failed"
            fi
        fi

        sleep $CHECK_INTERVAL
    done

    error "Reached maximum restart limit ($MAX_RESTARTS)"
    return 1
}

# Display current status
show_status() {
    echo ""
    echo "🔍 ATOM Backend Final Status"
    echo "============================"
    echo "Manager PID: $$"
    echo "Backend Port: $BACKEND_PORT"
    echo "Health Check: $HEALTH_URL"
    echo "Log File: $LOG_FILE"
    echo ""

    local backend_pid=$(get_backend_pid)
    if [ -n "$backend_pid" ]; then
        echo "Backend Process:"
        echo "  PID: $backend_pid"
        echo "  Status: $(ps -p $backend_pid -o state= 2>/dev/null || echo "not found")"

        if check_backend_health; then
            echo "  Health: ${GREEN}HEALTHY${NC}"
            echo "  Response: $(curl -s $HEALTH_URL | head -c 100)"
        else
            echo "  Health: ${RED}UNHEALTHY${NC}"
        fi
    else
        echo "Backend Process: ${RED}NOT RUNNING${NC}"
    fi

    echo ""
    echo "📊 Recent Logs:"
    tail -5 "$LOG_FILE" 2>/dev/null | while read line; do
        echo "  $line"
    done
}

# Cleanup function
cleanup() {
    log "Shutting down backend manager..."
    kill_backend_processes
    rm -f "$PID_FILE" .backend.pid
    success "Backend manager shutdown complete"
    exit 0
}

# Main execution function
main() {
    log "🚀 Starting ATOM Backend - Final Solution"

    # Setup environment
    setup_environment

    # Check if already running
    if [ -f "$PID_FILE" ]; then
        local existing_pid=$(cat "$PID_FILE")
        if ps -p "$existing_pid" > /dev/null 2>&1; then
            error "Backend manager already running with PID: $existing_pid"
            echo "Use: $0 status to check status"
            echo "Use: $0 stop to stop existing instance"
            exit 1
        else
            warning "Stale PID file found, cleaning up..."
            rm -f "$PID_FILE"
        fi
    fi

    # Create PID file
    echo $$ > "$PID_FILE"

    # Register cleanup handler
    trap cleanup SIGINT SIGTERM

    # Initial cleanup
    kill_backend_processes

    # Initial startup
    if start_backend 1; then
        success "Initial backend startup successful"
    else
        error "Initial backend startup failed"
        exit 1
    fi

    # Show initial status
    show_status

    log "Backend manager is now monitoring and maintaining the backend service"
    log "Press Ctrl+C to stop monitoring and shutdown all services"

    # Start monitoring loop
    monitor_backend
}

# Handle command line arguments
case "${1:-}" in
    status)
        show_status
        ;;
    stop)
        if [ -f "$PID_FILE" ]; then
            local manager_pid=$(cat "$PID_FILE")
            kill $manager_pid 2>/dev/null && success "Stop signal sent" || error "Failed to stop"
        else
            error "Backend manager not running"
        fi
        ;;
    restart)
        if [ -f "$PID_FILE" ]; then
            local manager_pid=$(cat "$PID_FILE")
            kill $manager_pid 2>/dev/null && sleep 2
        fi
        exec "$0"
        ;;
    logs)
        tail -f "$LOG_FILE"
        ;;
    health)
        if check_backend_health; then
            echo "HEALTHY"
            exit 0
        else
            echo "UNHEALTHY"
            exit 1
        fi
        ;;
    start-only)
        # Just start backend once without monitoring
        kill_backend_processes
        start_backend 1
        ;;
    *)
        main
        ;;
esac
