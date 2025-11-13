#!/bin/bash

# ATOM Chat Interface - Phase 2 Monitoring Script
# Multi-modal chat, voice integration, and analytics monitoring

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
BACKEND_DIR="$PROJECT_ROOT/backend"

# Service URLs
CHAT_URL="http://localhost:5059"
WEBSOCKET_URL="http://localhost:5060"

# Check service health
check_service_health() {
    local name=$1
    local url=$2

    log_info "Checking $name..."

    if curl -s --max-time 5 "$url" > /dev/null; then
        log_success "$name: Healthy"
        return 0
    else
        log_error "$name: Unhealthy"
        return 1
    fi
}

# Check process status
check_process_status() {
    local name=$1
    local pattern=$2

    if pgrep -f "$pattern" > /dev/null; then
        log_success "$name: Running"
        return 0
    else
        log_error "$name: Not running"
        return 1
    fi
}

# Check disk usage
check_disk_usage() {
    local path=$1
    local threshold=$2

    if [ -d "$path" ]; then
        local usage=$(df "$path" | awk 'NR==2 {print $5}' | sed 's/%//')
        if [ "$usage" -gt "$threshold" ]; then
            log_warning "Disk usage for $path: ${usage}% (above ${threshold}%)"
            return 1
        else
            log_success "Disk usage for $path: ${usage}%"
            return 0
        fi
    else
        log_warning "Directory not found: $path"
        return 1
    fi
}

# Test multi-modal features
test_multimodal_features() {
    log_info "Testing multi-modal features..."

    python3 -c "
import requests
import json

# Test file upload endpoint
try:
    url = 'http://localhost:5059/api/v1/chat/upload'
    files = {'file': ('test_monitor.txt', b'Monitoring test content', 'text/plain')}
    data = {'user_id': 'monitor_user', 'file_type': 'document'}

    response = requests.post(url, files=files, data=data, timeout=10)
    if response.status_code == 200:
        print('✓ File upload: SUCCESS')
    else:
        print(f'✗ File upload: FAILED - {response.status_code}')
except Exception as e:
    print(f'✗ File upload: ERROR - {e}')
"
}

# Test voice features
test_voice_features() {
    log_info "Testing voice features..."

    python3 -c "
import requests
import json

# Test TTS endpoint
try:
    url = 'http://localhost:5059/api/v1/voice/tts'
    data = {
        'text': 'Phase 2 monitoring test successful.',
        'user_id': 'monitor_user',
        'voice_type': 'standard'
    }

    response = requests.post(url, json=data, timeout=10)
    if response.status_code == 200:
        result = response.json()
        if result.get('success'):
            print('✓ TTS: SUCCESS')
        else:
            print(f'✗ TTS: FAILED - {result.get(\"error\")}')
    else:
        print(f'✗ TTS: FAILED - {response.status_code}')
except Exception as e:
    print(f'✗ TTS: ERROR - {e}')
"
}

# Test analytics features
test_analytics_features() {
    log_info "Testing analytics features..."

    python3 -c "
import requests
import json

# Test analytics endpoints
endpoints = [
    '/api/v1/analytics/chat-metrics',
    '/api/v1/analytics/voice-metrics',
    '/api/v1/analytics/file-metrics'
]

for endpoint in endpoints:
    try:
        url = f'http://localhost:5059{endpoint}'
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f'✓ Analytics {endpoint}: SUCCESS')
        else:
            print(f'✗ Analytics {endpoint}: FAILED - {response.status_code}')
    except Exception as e:
        print(f'✗ Analytics {endpoint}: ERROR - {e}')
"
}

# Check log files
check_logs() {
    log_info "Checking log files..."

    local log_files=(
        "$LOG_DIR/chat_interface.log"
        "$LOG_DIR/websocket_server.log"
    )

    for log_file in "${log_files[@]}"; do
        if [ -f "$log_file" ]; then
            local size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null || echo "0")
            local lines=$(wc -l < "$log_file" 2>/dev/null || echo "0")

            if [ "$size" -gt 10485760 ]; then # 10MB
                log_warning "Log file large: $log_file (${size} bytes)"
            else
                log_success "Log file: $log_file (${lines} lines, ${size} bytes)"
            fi
        else
            log_warning "Log file missing: $log_file"
        fi
    done
}

# Display system information
show_system_info() {
    log_info "System Information:"

    # CPU usage
    local cpu_usage=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | sed 's/%//' | cut -d. -f1)
    echo "  CPU Usage: ${cpu_usage}%"

    # Memory usage
    local mem_info=$(vm_stat | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
    local total_mem=$(sysctl -n hw.memsize)
    local free_mem=$((mem_info * 4096))
    local used_mem=$((total_mem - free_mem))
    local mem_percent=$((used_mem * 100 / total_mem))
    echo "  Memory Usage: ${mem_percent}%"

    # Disk space
    local disk_usage=$(df -h . | awk 'NR==2 {print $5}')
    echo "  Disk Usage: $disk_usage"
}

# Main monitoring function
main() {
    echo ""
    echo "🔍 ATOM Chat Interface - Phase 2 Monitoring"
    echo "==========================================="
    echo ""

    # Service health checks
    log_info "Service Health Checks:"
    check_service_health "Chat Interface Server" "$CHAT_URL/health"
    check_service_health "WebSocket Server" "$WEBSOCKET_URL/health"
    check_service_health "Voice Integration" "$CHAT_URL/api/v1/voice/health"
    echo ""

    # Process checks
    log_info "Process Status:"
    check_process_status "Chat Interface" "chat_interface_server.py"
    check_process_status "WebSocket Server" "websocket_server.py"
    echo ""

    # Disk usage checks
    log_info "Disk Usage:"
    check_disk_usage "./uploads" 80
    check_disk_usage "./voice" 80
    check_disk_usage "./data/analytics" 80
    echo ""

    # Feature testing
    log_info "Feature Testing:"
    test_multimodal_features
    test_voice_features
    test_analytics_features
    echo ""

    # Log checks
    check_logs
    echo ""

    # System information
    show_system_info
    echo ""

    # Quick commands reference
    log_info "Quick Commands:"
    echo "  Test file upload:"
    echo "    curl -X POST $CHAT_URL/api/v1/chat/upload \\"
    echo "      -F 'file=@test.txt' -F 'user_id=test' -F 'file_type=document'"
    echo ""
    echo "  Test TTS:"
    echo "    curl -X POST $CHAT_URL/api/v1/voice/tts \\"
    echo "      -H 'Content-Type: application/json' \\"
    echo "      -d '{\"text\":\"Hello\",\"user_id\":\"test\",\"voice_type\":\"standard\"}'"
    echo ""
    echo "  Get metrics:"
    echo "    curl $CHAT_URL/api/v1/analytics/chat-metrics"
    echo ""

    log_success "Phase 2 monitoring completed successfully!"
    echo ""
}

# Run main function
main "$@"
