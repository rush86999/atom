#!/bin/bash

# ATOM Platform - Stop Script
# Gracefully stops all ATOM platform services

set -e  # Exit on any error

echo "🛑 ATOM Platform - Stopping All Services"
echo "========================================"
echo "Timestamp: $(date)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Stop processes by PID file
stop_by_pid_file() {
    local service_name="$1"
    local pid_file="$2"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            log "Stopping $service_name (PID: $pid)..."
            kill "$pid" 2>/dev/null || true
            sleep 2

            # Force kill if still running
            if ps -p "$pid" > /dev/null 2>&1; then
                log "Force stopping $service_name..."
                kill -9 "$pid" 2>/dev/null || true
            fi

            rm -f "$pid_file"
            success "Stopped $service_name"
        else
            rm -f "$pid_file"
            warning "$service_name was not running"
        fi
    else
        warning "No PID file found for $service_name"
    fi
}

# Stop processes by port
stop_by_port() {
    local port="$1"
    local service_name="$2"

    local pids=$(lsof -ti:$port 2>/dev/null || true)
    if [ -n "$pids" ]; then
        log "Stopping $service_name on port $port..."
        for pid in $pids; do
            kill "$pid" 2>/dev/null || true
        done
        sleep 2

        # Force kill any remaining processes
        local remaining_pids=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$remaining_pids" ]; then
            log "Force stopping remaining $service_name processes..."
            for pid in $remaining_pids; do
                kill -9 "$pid" 2>/dev/null || true
            done
        fi

        success "Stopped $service_name on port $port"
    else
        warning "No $service_name found running on port $port"
    fi
}

# Stop processes by name pattern
stop_by_pattern() {
    local pattern="$1"
    local service_name="$2"

    local pids=$(pgrep -f "$pattern" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        log "Stopping $service_name processes..."
        for pid in $pids; do
            kill "$pid" 2>/dev/null || true
        done
        sleep 2

        # Force kill any remaining processes
        local remaining_pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        if [ -n "$remaining_pids" ]; then
            log "Force stopping remaining $service_name processes..."
            for pid in $remaining_pids; do
                kill -9 "$pid" 2>/dev/null || true
            done
        fi

        success "Stopped $service_name processes"
    else
        warning "No $service_name processes found"
    fi
}

# Clean up PID files
cleanup_pid_files() {
    log "Cleaning up PID files..."
    rm -f .backend.pid .frontend.pid .oauth.pid .monitor.pid
    success "PID files cleaned up"
}

# Verify all services are stopped
verify_stopped() {
    log "Verifying all services are stopped..."

    local all_stopped=true

    # Check ports
    local ports="8000 8001 3000 5058 9090"
    for port in $ports; do
        if lsof -ti:$port > /dev/null 2>&1; then
            error "Service still running on port $port"
            all_stopped=false
        fi
    done

    # Check process patterns
    local patterns=("python.*backend" "uvicorn" "next" "node.*dev")
    for pattern in "${patterns[@]}"; do
        if pgrep -f "$pattern" > /dev/null 2>&1; then
            error "Processes still matching pattern: $pattern"
            all_stopped=false
        fi
    done

    if [ "$all_stopped" = true ]; then
        success "All ATOM platform services have been stopped"
    else
        warning "Some services may still be running. Use 'ps aux | grep -E \"(python|node)\"' to check."
    fi
}

# Display cleanup summary
show_cleanup_summary() {
    echo ""
    echo "🧹 Cleanup Summary"
    echo "=================="
    echo "Stopped Services:"
    echo "  - Backend API (ports 8000, 8001)"
    echo "  - Frontend (port 3000)"
    echo "  - OAuth Server (port 5058)"
    echo "  - Monitoring services"
    echo ""
    echo "Cleaned Up:"
    echo "  - PID files"
    echo "  - Temporary process files"
    echo ""
    echo "To restart: ./start_atom_platform.sh"
    echo ""
}

# Main execution
main() {
    log "Starting ATOM Platform shutdown sequence..."

    # Stop services by PID files (preferred method)
    stop_by_pid_file "Backend API" ".backend.pid"
    stop_by_pid_file "Frontend" ".frontend.pid"
    stop_by_pid_file "OAuth Server" ".oauth.pid"
    stop_by_pid_file "Monitor" ".monitor.pid"

    # Stop services by port (fallback method)
    stop_by_port "8000" "Backend API"
    stop_by_port "8001" "Backend API"
    stop_by_port "3000" "Frontend"
    stop_by_port "5058" "OAuth Server"
    stop_by_port "9090" "Monitoring"

    # Stop services by pattern (catch-all method)
    stop_by_pattern "python.*backend" "Backend Python processes"
    stop_by_pattern "uvicorn" "Uvicorn servers"
    stop_by_pattern "next" "Next.js processes"
    stop_by_pattern "node.*dev" "Node.js development servers"

    # Cleanup PID files
    cleanup_pid_files

    # Verify everything is stopped
    verify_stopped

    # Show summary
    show_cleanup_summary

    success "ATOM Platform shutdown completed successfully!"
}

# Handle script interruption
trap 'echo ""; warning "Shutdown interrupted"; exit 1' INT TERM

# Run main function
main "$@"
