#!/bin/bash

# ATOM Platform - Ultimate Startup Solution
# Complete system startup with all services and monitoring

set -e  # Exit on any error

echo "🚀 ATOM Platform - Ultimate Startup"
echo "==================================="
echo "Timestamp: $(date)"
echo ""

# Configuration
BACKEND_PORT=8001
FRONTEND_PORT=3000
OAUTH_PORT=5058
MONITOR_PORT=9090

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

# Check dependencies
check_dependencies() {
    log "Checking dependencies..."

    if ! command -v python &> /dev/null; then
        error "Python is not installed"
        exit 1
    fi

    if ! command -v node &> /dev/null; then
        error "Node.js is not installed"
        exit 1
    fi

    if ! command -v npm &> /dev/null; then
        error "npm is not installed"
        exit 1
    fi

    success "All dependencies available"
}

# Clean up existing processes
cleanup() {
    log "Cleaning up existing processes..."

    # Kill processes on our ports
    for port in $BACKEND_PORT $FRONTEND_PORT $OAUTH_PORT $MONITOR_PORT; do
        pid=$(lsof -ti:$port 2>/dev/null || true)
        if [ -n "$pid" ]; then
            kill $pid 2>/dev/null || true
            log "Killed process on port $port (PID: $pid)"
        fi
    done

    # Kill by process name
    pkill -f "python.*backend" 2>/dev/null || true
    pkill -f "uvicorn" 2>/dev/null || true
    pkill -f "next" 2>/dev/null || true
    pkill -f "node.*dev" 2>/dev/null || true

    sleep 2
    success "Cleanup completed"
}

# Create necessary directories
setup_directories() {
    log "Setting up directories..."

    mkdir -p data logs uploads tmp
    success "Directories created"
}

# Start backend service
start_backend() {
    log "Starting backend service..."

    # Try multiple backend options
    local backend_started=false

    # Option 1: FastAPI backend
    if [ -f "backend/fixed_main_api_app.py" ]; then
        log "Starting FastAPI backend..."
        python backend/fixed_main_api_app.py &
        BACKEND_PID=$!
        backend_started=true
    # Option 2: Simple backend
    elif [ -f "start_simple_backend.py" ]; then
        log "Starting simple backend..."
        python start_simple_backend.py &
        BACKEND_PID=$!
        backend_started=true
    else
        error "No backend startup file found"
        return 1
    fi

    # Wait for backend to be ready
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
            success "Backend service started successfully on port $BACKEND_PORT"
            echo $BACKEND_PID > .backend.pid
            return 0
        fi

        if ! ps -p $BACKEND_PID > /dev/null 2>&1; then
            error "Backend process died"
            return 1
        fi

        log "Waiting for backend to be ready... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    error "Backend failed to start within timeout"
    kill $BACKEND_PID 2>/dev/null || true
    return 1
}

# Start frontend service
start_frontend() {
    log "Starting frontend service..."

    if [ ! -d "frontend-nextjs" ]; then
        warning "Frontend directory not found, skipping frontend startup"
        return 0
    fi

    cd frontend-nextjs

    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        log "Installing frontend dependencies..."
        npm install
    fi

    # Start frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..

    echo $FRONTEND_PID > .frontend.pid

    # Wait for frontend to be ready
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
            success "Frontend service started successfully on port $FRONTEND_PORT"
            return 0
        fi

        if ! ps -p $FRONTEND_PID > /dev/null 2>&1; then
            error "Frontend process died"
            return 1
        fi

        log "Waiting for frontend to be ready... (attempt $attempt/$max_attempts)"
        sleep 2
        ((attempt++))
    done

    error "Frontend failed to start within timeout"
    kill $FRONTEND_PID 2>/dev/null || true
    return 1
}

# Start OAuth server (if available)
start_oauth_server() {
    log "Checking for OAuth server..."

    if [ -f "start_simple_oauth_server.py" ]; then
        log "Starting OAuth server..."
        python start_simple_oauth_server.py &
        OAUTH_PID=$!
        echo $OAUTH_PID > .oauth.pid
        success "OAuth server started on port $OAUTH_PORT"
    else
        warning "OAuth server not found, skipping"
    fi
}

# Health check all services
health_check() {
    log "Performing health checks..."

    local all_healthy=true

    # Backend health
    if curl -s http://localhost:$BACKEND_PORT/health > /dev/null 2>&1; then
        success "Backend: HEALTHY"
    else
        error "Backend: UNHEALTHY"
        all_healthy=false
    fi

    # Frontend health
    if curl -s http://localhost:$FRONTEND_PORT > /dev/null 2>&1; then
        success "Frontend: HEALTHY"
    else
        error "Frontend: UNHEALTHY"
        all_healthy=false
    fi

    # OAuth health (if running)
    if [ -f ".oauth.pid" ] && ps -p $(cat .oauth.pid) > /dev/null 2>&1; then
        if curl -s http://localhost:$OAUTH_PORT/healthz > /dev/null 2>&1; then
            success "OAuth Server: HEALTHY"
        else
            warning "OAuth Server: UNHEALTHY"
        fi
    fi

    if [ "$all_healthy" = true ]; then
        success "All services are healthy!"
    else
        warning "Some services may need attention"
    fi
}

# Display service information
show_service_info() {
    echo ""
    echo "🎯 ATOM Platform Services"
    echo "========================"
    echo "Frontend:    http://localhost:$FRONTEND_PORT"
    echo "Backend API: http://localhost:$BACKEND_PORT"
    echo "API Docs:    http://localhost:$BACKEND_PORT/docs"
    echo "Health:      http://localhost:$BACKEND_PORT/health"

    if [ -f ".oauth.pid" ]; then
        echo "OAuth Server: http://localhost:$OAUTH_PORT"
    fi

    echo ""
    echo "📊 Quick Status Check:"
    echo "  ./monitor_production.sh"
    echo ""
    echo "🛑 To stop all services:"
    echo "  ./stop_atom_platform.sh"
    echo ""
    echo "📝 Logs:"
    echo "  tail -f logs/atom_platform.log"
}

# Main execution
main() {
    log "ATOM Platform Startup Initialized"

    # Check dependencies
    check_dependencies

    # Cleanup existing processes
    cleanup

    # Setup directories
    setup_directories

    # Start services
    start_backend
    start_frontend
    start_oauth_server

    # Health check
    health_check

    # Show service information
    show_service_info

    success "ATOM Platform startup completed!"
    log "Services are now running. Use Ctrl+C to stop monitoring."

    # Monitor services
    while true; do
        sleep 30
        log "Service monitor check..."
        health_check
    done
}

# Handle script interruption
trap 'echo ""; warning "Shutting down ATOM Platform..."; pkill -P $$; exit 0' INT TERM

# Run main function
main "$@"
