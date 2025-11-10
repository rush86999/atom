#!/bin/bash

# ATOM Backend - Guaranteed Startup Script
# Ensures backend stays running with multiple fallback mechanisms

set -e

# Configuration
BACKEND_PORT=8001
HEALTH_CHECK_URL="http://localhost:$BACKEND_PORT/health"
MAX_RESTARTS=100
RESTART_DELAY=3
LOG_FILE="logs/backend_guaranteed.log"
PID_FILE=".backend_guaranteed.pid"

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
    if curl -s --max-time 5 "$HEALTH_CHECK_URL" > /dev/null 2>&1; then
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
    log "Cleaning up existing backend processes..."

    # Kill by port
    local port_pids=$(lsof -ti:$BACKEND_PORT 2>/dev/null || true)
    if [ -n "$port_pids" ]; then
        kill $port_pids 2>/dev/null || true
        sleep 2
        # Force kill any remaining
        local remaining_pids=$(lsof -ti:$BACKEND_PORT 2>/dev/null || true)
        if [ -n "$remaining_pids" ]; then
            kill -9 $remaining_pids 2>/dev/null || true
        fi
    fi

    # Kill by process name patterns
    pkill -f "python.*backend" 2>/dev/null || true
    pkill -f "uvicorn" 2>/dev/null || true
    pkill -f "fixed_main_api_app" 2>/dev/null || true

    sleep 2
}

# Try different backend startup methods
start_backend_method() {
    local method="$1"
    local backend_pid=""

    case "$method" in
        "fixed")
            if [ -f "backend/fixed_main_api_app.py" ]; then
                log "Starting fixed FastAPI backend..."
                python backend/fixed_main_api_app.py &
                backend_pid=$!
            fi
            ;;
        "robust")
            if [ -f "robust_backend.py" ]; then
                log "Starting robust backend..."
                python robust_backend.py &
                backend_pid=$!
            fi
            ;;
        "production")
            if [ -f "production_backend.py" ]; then
                log "Starting production backend..."
                python production_backend.py &
                backend_pid=$!
            fi
            ;;
        "simple")
            if [ -f "start_simple_backend.py" ]; then
                log "Starting simple backend..."
                python start_simple_backend.py &
                backend_pid=$!
            fi
            ;;
    esac

    echo "$backend_pid"
}

# Start backend with fallback methods
start_backend() {
    local attempt=$1
    local backend_pid=""

    log "Starting backend (attempt $attempt)..."

    # Try methods in order of preference
    local methods=("fixed" "robust" "production" "simple")

    for method in "${methods[@]}"; do
        backend_pid=$(start_backend_method "$method")
        if [ -n "$backend_pid" ]; then
            log "Backend started with method '$method' (PID: $backend_pid)"
            break
        fi
    done

    if [ -z "$backend_pid" ]; then
        error "No backend startup method available"
        return 1
    fi

    echo "$backend_pid" > .backend.pid

    # Wait for backend to be ready
    local health_checks=0
    local max_health_checks=30

    while [ $health_checks -lt $max_health_checks ]; do
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
        ((health_checks++))
    done

    error "Backend failed to become healthy within timeout"
    kill $backend_pid 2>/dev/null || true
    return 1
}

# Monitor and maintain backend
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
                log "Backend running normally - uptime: $(($(date +%s) - $last_success_time))s"
            fi

        else
            # Backend is unhealthy
            ((consecutive_failures++))
            warning "Backend health check failed (consecutive: $consecutive_failures)"

            # Check if process exists but is unresponsive
            local backend_pid=$(get_backend_pid)
            if [ -n "$backend_pid" ]; then
                warning "Backend process $backend_pid exists but unresponsive"
            fi

            # Clean up and restart
            kill_backend_processes

            # Implement exponential backoff
            local backoff_delay=$((RESTART_DELAY * (2 ** (consecutive_failures - 1))))
            backoff_delay=$((backoff_delay > 60 ? 60 : backoff_delay)) # Cap at 60 seconds

            if [ $consecutive_failures -gt 1 ]; then
                warning "Implementing backoff: waiting ${backoff_delay}s"
                sleep $backoff_delay
            else
                sleep $RESTART_DELAY
            fi

            # Restart backend
            if start_backend $((restart_count + 1)); then
                ((restart_count++))
                consecutive_failures=0
                success "Backend restarted successfully (total restarts: $restart_count)"

                # Reset counter after prolonged stability
                if [ $restart_count -ge 10 ] && [ $(($(date +%s) - $last_success_time)) -gt 3600 ]; then
                    log "Resetting restart counter after prolonged stability"
                    restart_count=0
                fi
            else
                error "Backend restart failed"
            fi
        fi

        sleep 10  # Check every 10 seconds
    done

    error "Reached maximum restart limit ($MAX_RESTARTS)"
    return 1
}

# Display current status
show_status() {
    echo ""
    echo "🔍 ATOM Backend Status"
    echo "====================="
    echo "Manager PID: $$"
    echo "Backend Port: $BACKEND_PORT"
    echo "Health Check: $HEALTH_CHECK_URL"
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
    echo "📊 Recent Activity:"
    tail -5 "$LOG_FILE" 2>/dev/null | while read line; do
        echo "  $line"
    done
}

# Cleanup function
cleanup() {
    log "Shutting down guaranteed backend manager..."
    kill_backend_processes
    rm -f "$PID_FILE" .backend.pid
    success "Backend manager shutdown complete"
    exit 0
}

# Main execution
main() {
    log "🚀 Starting ATOM Backend - Guaranteed Startup"

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

    # Show status
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
    *)
        main
        ;;
esac
