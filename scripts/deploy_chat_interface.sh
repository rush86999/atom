#!/bin/bash

# ATOM Chat Interface Deployment Script
# This script deploys the chat interface components for production

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
BACKEND_DIR="$PROJECT_ROOT/backend"
LOG_DIR="$PROJECT_ROOT/logs"
CONFIG_DIR="$PROJECT_ROOT/config"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        log_success "Python $PYTHON_VERSION found"
    else
        log_error "Python 3 is required but not installed"
        exit 1
    fi

    # Check pip
    if command -v pip3 &> /dev/null; then
        log_success "pip3 found"
    else
        log_error "pip3 is required but not installed"
        exit 1
    fi

    # Check if backend directory exists
    if [ ! -d "$BACKEND_DIR" ]; then
        log_error "Backend directory not found: $BACKEND_DIR"
        exit 1
    fi

    # Create log directory if it doesn't exist
    mkdir -p "$LOG_DIR"
    log_success "Log directory ready: $LOG_DIR"
}

# Install dependencies
install_dependencies() {
    log_info "Installing Python dependencies..."

    cd "$BACKEND_DIR"

    # Check if requirements.txt exists
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt
        if [ $? -eq 0 ]; then
            log_success "Dependencies installed successfully"
        else
            log_error "Failed to install dependencies"
            exit 1
        fi
    else
        log_warning "requirements.txt not found, installing common dependencies"
        pip3 install fastapi uvicorn websocket-client requests pydantic
        log_success "Common dependencies installed"
    fi

    # Install chat-specific dependencies
    pip3 install websockets python-socketio aiohttp
    log_success "Chat-specific dependencies installed"
}

# Start chat interface server
start_chat_interface() {
    log_info "Starting Chat Interface Server..."

    cd "$BACKEND_DIR"

    # Check if chat interface server exists
    if [ ! -f "chat_interface_server.py" ]; then
        log_error "chat_interface_server.py not found"
        exit 1
    fi

    # Start the server in background
    nohup python3 chat_interface_server.py > "$LOG_DIR/chat_interface.log" 2>&1 &
    CHAT_PID=$!
    echo $CHAT_PID > "$LOG_DIR/chat_interface.pid"

    # Wait a moment for server to start
    sleep 3

    # Check if server is running
    if ps -p $CHAT_PID > /dev/null; then
        log_success "Chat Interface Server started (PID: $CHAT_PID)"
        log_info "Logs: $LOG_DIR/chat_interface.log"
    else
        log_error "Failed to start Chat Interface Server"
        exit 1
    fi
}

# Start WebSocket server
start_websocket_server() {
    log_info "Starting WebSocket Server..."

    cd "$BACKEND_DIR"

    # Check if WebSocket server exists
    if [ ! -f "websocket_server.py" ]; then
        log_error "websocket_server.py not found"
        exit 1
    fi

    # Start the server in background
    nohup python3 websocket_server.py > "$LOG_DIR/websocket_server.log" 2>&1 &
    WS_PID=$!
    echo $WS_PID > "$LOG_DIR/websocket_server.pid"

    # Wait a moment for server to start
    sleep 3

    # Check if server is running
    if ps -p $WS_PID > /dev/null; then
        log_success "WebSocket Server started (PID: $WS_PID)"
        log_info "Logs: $LOG_DIR/websocket_server.log"
    else
        log_error "Failed to start WebSocket Server"
        exit 1
    fi
}

# Run health checks
run_health_checks() {
    log_info "Running health checks..."

    # Wait a bit for servers to fully initialize
    sleep 5

    local all_healthy=true

    # Check chat interface health
    if curl -s http://localhost:5059/health > /dev/null; then
        log_success "Chat Interface Server is healthy"
    else
        log_error "Chat Interface Server health check failed"
        all_healthy=false
    fi

    # Check WebSocket server health
    if curl -s http://localhost:5060/health > /dev/null; then
        log_success "WebSocket Server is healthy"
    else
        log_error "WebSocket Server health check failed"
        all_healthy=false
    fi

    # Test WebSocket connection
    if python3 -c "import websocket; ws = websocket.create_connection('ws://localhost:5060/ws/test_user'); print('WebSocket connected')" 2>/dev/null; then
        log_success "WebSocket connection test passed"
    else
        log_error "WebSocket connection test failed"
        all_healthy=false
    fi

    if [ "$all_healthy" = true ]; then
        log_success "All health checks passed!"
    else
        log_error "Some health checks failed"
        exit 1
    fi
}

# Run integration tests
run_integration_tests() {
    log_info "Running integration tests..."

    cd "$PROJECT_ROOT"

    if [ -f "test_chat_integration.py" ]; then
        python3 test_chat_integration.py
        if [ $? -eq 0 ]; then
            log_success "Integration tests completed successfully"
        else
            log_warning "Integration tests had some failures"
        fi
    else
        log_warning "Integration test script not found, skipping tests"
    fi
}

# Display deployment information
show_deployment_info() {
    log_success "🎉 Chat Interface Deployment Completed Successfully!"
    echo ""
    echo "📊 Deployment Summary:"
    echo "   Chat Interface Server: http://localhost:5059"
    echo "   WebSocket Server: ws://localhost:5060"
    echo "   Health Check: curl http://localhost:5059/health"
    echo ""
    echo "📝 Quick Test Commands:"
    echo "   Test Chat API: curl -X POST http://localhost:5059/api/v1/chat/message -H 'Content-Type: application/json' -d '{\"message\": \"Hello\", \"user_id\": \"test_user\"}'"
    echo "   Test WebSocket: python3 -c \"import websocket; ws = websocket.create_connection('ws://localhost:5060/ws/test_user'); ws.send('{\\\"type\\\": \\\"ping\\\"}'); print(ws.recv()); ws.close()\""
    echo ""
    echo "📋 Next Steps:"
    echo "   1. Configure your frontend to connect to these endpoints"
    echo "   2. Set up monitoring for the chat services"
    echo "   3. Configure load balancing if needed"
    echo "   4. Set up SSL/TLS certificates for production"
    echo ""
    echo "🛑 To stop services: ./stop_chat_interface.sh"
}

# Main deployment function
main() {
    log_info "🚀 Starting ATOM Chat Interface Deployment"
    log_info "Project Root: $PROJECT_ROOT"
    echo ""

    check_prerequisites
    echo ""

    install_dependencies
    echo ""

    start_chat_interface
    echo ""

    start_websocket_server
    echo ""

    run_health_checks
    echo ""

    run_integration_tests
    echo ""

    show_deployment_info
}

# Handle script interruption
cleanup() {
    log_info "Cleaning up..."
    # Kill background processes if they exist
    if [ -f "$LOG_DIR/chat_interface.pid" ]; then
        kill $(cat "$LOG_DIR/chat_interface.pid") 2>/dev/null || true
        rm -f "$LOG_DIR/chat_interface.pid"
    fi
    if [ -f "$LOG_DIR/websocket_server.pid" ]; then
        kill $(cat "$LOG_DIR/websocket_server.pid") 2>/dev/null || true
        rm -f "$LOG_DIR/websocket_server.pid"
    fi
}

# Set up cleanup on exit
trap cleanup EXIT INT TERM

# Run main function
main "$@"
