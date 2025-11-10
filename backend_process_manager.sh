#!/bin/bash

# ATOM Backend Process Manager
# Ensures backend API stays running with auto-recovery and monitoring

set -e

# Configuration
BACKEND_PORT=8001
HEALTH_CHECK_INTERVAL=30
RESTART_DELAY=5
MAX_RESTARTS=10
LOG_FILE="logs/backend_manager.log"
PID_FILE=".backend_manager.pid"

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
setup_directories() {
    mkdir -p logs data tmp
    touch "$LOG_FILE"
    chmod 644 "$LOG_FILE"
}

# Check if backend is healthy
check_backend_health() {
    if curl -s --max-time 5 "http://localhost:$BACKEND_PORT/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Get backend process ID
get_backend_pid() {
    lsof -ti:$BACKEND_PORT 2>/dev/null || echo ""
}

# Kill backend processes
kill_backend_processes() {
    local pids=$(get_backend_pid)
    if [ -n "$pids" ]; then
        log "Stopping backend processes: $pids"
        kill $pids 2>/dev/null || true
        sleep 2

        # Force kill if still running
        local remaining_pids=$(get_backend_pid)
        if [ -n "$remaining_pids" ]; then
            log "Force stopping remaining backend processes"
            kill -9 $remaining_pids 2>/dev/null || true
        fi
    fi
}

# Start backend process
start_backend() {
    local attempt=$1
    local backend_pid=""

    log "Starting backend (attempt $attempt)..."

    # Try different backend startup methods in order of preference
    if [ -f "robust_backend.py" ]; then
        python robust_backend.py &
        backend_pid=$!
    elif [ -f "production_backend.py" ]; then
        python production_backend.py &
        backend_pid=$!
    elif [ -f "backend/fixed_main_api_app.py" ]; then
        python backend/fixed_main_api_app.py &
        backend_pid=$!
    elif [ -f "start_simple_backend.py" ]; then
        python start_simple_backend.py &
        backend_pid=$!
    else
        error "No backend startup file found"
        return 1
    fi

    echo $backend_pid > .backend.pid
    log "Backend started with PID: $backend_pid"

    # Wait for backend to be ready
    local health_check_attempts=0
    local max_health_checks=30

    while [ $health_check_attempts -lt $max_health_checks ]; do
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
        ((health_check_attempts++))
    done

    error "Backend failed to become healthy within timeout"
    kill $backend_pid 2>/dev/null || true
    return 1
}

# Monitor backend health
monitor_backend() {
    local restart_count=0
    local last_restart_time=0
    local consecutive_failures=0

    log "Starting backend monitoring..."

    while true; do
        if ! check_backend_health; then
            ((consecutive_failures++))
            warning "Backend health check failed (consecutive failures: $consecutive_failures)"

            # Check if backend process is still running but unresponsive
            local backend_pid=$(get_backend_pid)
            if [ -n "$backend_pid" ]; then
                warning "Backend process $backend_pid is running but unresponsive - restarting"
            else
                warning "Backend process not found - restarting"
            fi

            # Implement exponential backoff for restarts
            local current_time=$(date +%s)
            local time_since_last_restart=$((current_time - last_restart_time))

            if [ $restart_count -gt 0 ] && [ $time_since_last_restart -lt $((RESTART_DELAY * 2)) ]; then
                local backoff_delay=$((RESTART_DELAY * (2 ** (restart_count - 1))))
                backoff_delay=$((backoff_delay > 300 ? 300 : backoff_delay)) # Cap at 5 minutes
                warning "Implementing exponential backoff: waiting ${backoff_delay}s before restart"
                sleep $backoff_delay
            else
                sleep $RESTART_DELAY
            fi

            # Kill existing backend processes
            kill_backend_processes

            # Start backend
            if start_backend $((restart_count + 1)); then
                ((restart_count++))
                last_restart_time=$(date +%s)
                consecutive_failures=0
                success "Backend restarted successfully (total restarts: $restart_count)"

                # Reset restart count after successful operation for a while
                if [ $restart_count -ge $MAX_RESTARTS ]; then
                    warning "Reached maximum restart count ($MAX_RESTARTS), resetting counter"
                    restart_count=0
                fi
            else
                error "Backend restart failed"
                consecutive_failures=$((consecutive_failures + 1))
            fi
        else
            # Backend is healthy
            if [ $consecutive_failures -gt 0 ]; then
                success "Backend recovered after $consecutive_failures failures"
                consecutive_failures=0
            fi

            # Log periodic health status
            if [ $(( $(date +%s) % 300 )) -eq 0 ]; then # Every 5 minutes
                log "Backend health check passed - running normally"
            fi
        fi

        sleep $HEALTH_CHECK_INTERVAL
    done
}

# Display status information
show_status() {
    echo ""
    echo "🔍 ATOM Backend Process Manager Status"
    echo "======================================"
    echo "Manager PID: $$"
    echo "Backend Port: $BACKEND_PORT"
    echo "Health Check Interval: ${HEALTH_CHECK_INTERVAL}s"
    echo "Log File: $LOG_FILE"
    echo ""

    local backend_pid=$(get_backend_pid)
    if [ -n "$backend_pid" ]; then
        echo "Backend Process:"
        echo "  PID: $backend_pid"
        echo "  Status: $(ps -p $backend_pid -o state= 2>/dev/null || echo "not found")"

        if check_backend_health; then
            echo "  Health: ${GREEN}HEALTHY${NC}"
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
    log "Shutting down backend process manager..."
    kill_backend_processes
    rm -f "$PID_FILE" .backend.pid
    success "Backend process manager shutdown complete"
    exit 0
}

# Main function
main() {
    log "🚀 Starting ATOM Backend Process Manager"

    # Setup
    setup_directories

    # Check if already running
    if [ -f "$PID_FILE" ]; then
        local manager_pid=$(cat "$PID_FILE")
        if ps -p "$manager_pid" > /dev/null 2>&1; then
            error "Backend process manager is already running with PID: $manager_pid"
            exit 1
        else
            warning "Stale PID file found, removing..."
            rm -f "$PID_FILE"
        fi
    fi

    # Create PID file
    echo $$ > "$PID_FILE"

    # Register cleanup handler
    trap cleanup SIGINT SIGTERM

    # Initial backend start
    if ! start_backend 1; then
        error "Initial backend startup failed"
        exit 1
    fi

    # Show initial status
    show_status

    # Start monitoring
    log "Backend process manager is now monitoring the backend service"
    log "Press Ctrl+C to stop monitoring and shutdown all services"

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
            kill $manager_pid 2>/dev/null && success "Sent stop signal to process manager" || error "Failed to stop process manager"
        else
            error "Process manager not running"
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
    *)
        main
        ;;
esac
