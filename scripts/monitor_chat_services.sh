#!/bin/bash

# ATOM Chat Services Monitoring Script
# Monitors chat interface and WebSocket services for health and performance

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR"
LOG_DIR="$PROJECT_ROOT/logs"
CONFIG_DIR="$PROJECT_ROOT/config"
ALERT_THRESHOLD=3  # Number of consecutive failures before alert

# Service endpoints
CHAT_API_URL="http://localhost:8000"
WEBSOCKET_URL="ws://localhost:5060"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Monitoring state
failure_count_chat_api=0
failure_count_websocket=0
failure_count_websocket_conn=0
failure_count_chat_message=0
failure_count_cpu=0
failure_count_memory=0
failure_count_disk=0
failure_count_logs=0
last_alert_time_chat_api=0
last_alert_time_websocket=0
last_alert_time_websocket_conn=0
last_alert_time_chat_message=0
last_alert_time_cpu=0
last_alert_time_memory=0
last_alert_time_disk=0
last_alert_time_logs=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Check if service is running by PID
check_service_pid() {
    local service_name=$1
    local pid_file="$LOG_DIR/${service_name}.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
            return 1
        fi
    else
        return 1
    fi
}

# Check chat API health
check_chat_api_health() {
    local response
    response=$(curl -s -w "%{http_code}" -o /dev/null "$CHAT_API_URL/health" --connect-timeout 5 --max-time 10)

    if [ "$response" -eq 200 ]; then
        log_success "Chat API Health Check: HTTP 200"
        failure_count_chat_api=0
        return 0
    else
        log_error "Chat API Health Check: HTTP $response"
        failure_count_chat_api=$((failure_count_chat_api + 1))
        return 1
    fi
}

# Check WebSocket server health
check_websocket_health() {
    local response
    response=$(curl -s -w "%{http_code}" -o /dev/null "http://localhost:5060/health" --connect-timeout 5 --max-time 10)

    if [ "$response" -eq 200 ]; then
        log_success "WebSocket Health Check: HTTP 200"
        failure_count_websocket=0
        return 0
    else
        log_error "WebSocket Health Check: HTTP $response"
        failure_count_websocket=$((failure_count_websocket + 1))
        return 1
    fi
}

# Test WebSocket connection
test_websocket_connection() {
    if python3 -c "
import websocket
import json
import sys
try:
    ws = websocket.create_connection('$WEBSOCKET_URL/ws/monitor_user', timeout=5)
    ws.send(json.dumps({'type': 'ping'}))
    response = ws.recv()
    ws.close()
    if 'pong' in response:
        sys.exit(0)
    else:
        sys.exit(1)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; then
        log_success "WebSocket Connection Test: Connected successfully"
        failure_count_websocket_conn=0
        return 0
    else
        log_error "WebSocket Connection Test: Connection failed"
        failure_count_websocket_conn=$((failure_count_websocket_conn + 1))
        return 1
    fi
}

# Test chat message processing
test_chat_message() {
    local response
    response=$(curl -s -w "%{http_code}" -o /dev/null \
        -X POST "$CHAT_API_URL/api/v1/chat/message" \
        -H "Content-Type: application/json" \
        -d '{"message": "monitoring test", "user_id": "monitor_user"}' \
        --connect-timeout 5 --max-time 10)

    if [ "$response" -eq 200 ]; then
        log_success "Chat Message Test: Message processed successfully"
        failure_count_chat_message=0
        return 0
    else
        log_error "Chat Message Test: HTTP $response"
        failure_count_chat_message=$((failure_count_chat_message + 1))
        return 1
    fi
}

# Check system resources
check_system_resources() {
    local cpu_usage
    local memory_usage
    local disk_usage

    # CPU usage (average over 1 minute)
    cpu_usage=$(uptime | awk -F'load average:' '{print $2}' | cut -d, -f1 | tr -d ' ')

    # Memory usage
    memory_usage=$(free | awk 'NR==2{printf "%.2f", $3*100/$2}')

    # Disk usage for project directory
    disk_usage=$(df "$PROJECT_ROOT" | awk 'NR==2{printf "%.2f", $5}' | tr -d '%')

    log_info "System Resources - CPU: $cpu_usage, Memory: ${memory_usage}%, Disk: ${disk_usage}%"

    # Check thresholds
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        log_warning "High CPU usage: $cpu_usage"
        failure_count_cpu=$((failure_count_cpu + 1))
    else
        failure_count_cpu=0
    fi

    if (( $(echo "$memory_usage > 85" | bc -l) )); then
        log_warning "High Memory usage: ${memory_usage}%"
        failure_count_memory=$((failure_count_memory + 1))
    else
        failure_count_memory=0
    fi

    if (( $(echo "$disk_usage > 90" | bc -l) )); then
        log_warning "High Disk usage: ${disk_usage}%"
        failure_count_disk=$((failure_count_disk + 1))
    else
        failure_count_disk=0
    fi
}

# Check log files for errors
check_logs() {
    local log_files=("chat_interface.log" "websocket_server.log")
    local error_count=0

    for log_file in "${log_files[@]}"; do
        local full_path="$LOG_DIR/$log_file"
        if [ -f "$full_path" ]; then
            local recent_errors=$(tail -100 "$full_path" | grep -i "error\|exception\|failed" | wc -l)
            if [ "$recent_errors" -gt 0 ]; then
                log_warning "Found $recent_errors errors in $log_file"
                error_count=$((error_count + recent_errors))
            fi
        fi
    done

    if [ "$error_count" -gt 0 ]; then
        failure_count_logs=$((failure_count_logs + 1))
    else
        failure_count_logs=0
    fi
}

# Send alert
send_alert() {
    local service=$1
    local message=$2
    local current_time=$(date +%s)
    local last_alert_var="last_alert_time_${service}"
    local last_alert=${!last_alert_var:-0}

    # Rate limiting: don't send alerts more than once every 5 minutes
    if [ $((current_time - last_alert)) -gt 300 ]; then
        log_error "ALERT: $service - $message"
        # Here you would integrate with your alerting system (email, Slack, etc.)
        # Example: send_slack_alert "$service alert: $message"
        eval "last_alert_time_${service}=$current_time"
    fi
}

# Check for critical failures
check_critical_failures() {
    for service in chat_api websocket websocket_conn chat_message cpu memory disk logs; do
        local count_var="failure_count_${service}"
        local count=${!count_var}
        if [ "$count" -ge "$ALERT_THRESHOLD" ]; then
            send_alert "$service" "Critical failure detected: $count consecutive failures"
        fi
    done
}

# Generate monitoring report
generate_report() {
    local report_file="$LOG_DIR/monitoring_report_$(date +%Y%m%d_%H%M%S).json"
    local timestamp=$(date -Iseconds)

    cat > "$report_file" << EOF
{
  "timestamp": "$timestamp",
  "services": {
    "chat_api": {
      "status": "$(check_chat_api_health > /dev/null && echo "healthy" || echo "unhealthy")",
      "failure_count": ${failure_count_chat_api:-0}
    },
    "websocket": {
      "status": "$(check_websocket_health > /dev/null && echo "healthy" || echo "unhealthy")",
      "failure_count": ${failure_count_websocket:-0}
    },
    "websocket_connection": {
      "status": "$(test_websocket_connection > /dev/null && echo "healthy" || echo "unhealthy")",
      "failure_count": ${failure_count_websocket_conn:-0}
    },
    "chat_message": {
      "status": "$(test_chat_message > /dev/null && echo "healthy" || echo "unhealthy")",
      "failure_count": ${failure_count_chat_message:-0}
    }
  },
  "system": {
    "cpu_usage": "$(uptime | awk -F'load average:' '{print $2}' | cut -d, -f1 | tr -d ' ')",
    "memory_usage": "$(free | awk 'NR==2{printf "%.2f", $3*100/$2}')%",
    "disk_usage": "$(df "$PROJECT_ROOT" | awk 'NR==2{printf "%.2f", $5}')%"
  }
}
EOF

    log_info "Monitoring report generated: $report_file"
}

# Main monitoring function
run_monitoring_cycle() {
    log_info "Starting monitoring cycle..."

    # Initialize failure counts if not set
    # Initialize failure counts if not set (already done at top)
    :

    # Run all checks
    check_chat_api_health
    check_websocket_health
    test_websocket_connection
    test_chat_message
    check_system_resources
    check_logs

    # Check for critical failures
    check_critical_failures

    # Generate report every 10 cycles
    local cycle_count=${cycle_count:-0}
    cycle_count=$((cycle_count + 1))
    if [ $((cycle_count % 10)) -eq 0 ]; then
        generate_report
    fi

    log_success "Monitoring cycle completed"
}

# Continuous monitoring mode
continuous_monitoring() {
    log_info "Starting continuous monitoring (interval: 60 seconds)"
    log_info "Press Ctrl+C to stop"

    while true; do
        run_monitoring_cycle
        echo "----------------------------------------"
        sleep 60
    done
}

# Single check mode
single_check() {
    log_info "Running single monitoring check"
    run_monitoring_cycle
}

# Show status
show_status() {
    log_info "Current Service Status:"

    echo "Chat Interface Server: $(check_service_pid "chat_interface" && echo -e "${GREEN}RUNNING${NC}" || echo -e "${RED}STOPPED${NC}")"
    echo "WebSocket Server: $(check_service_pid "websocket_server" && echo -e "${GREEN}RUNNING${NC}" || echo -e "${RED}STOPPED${NC}")"

    if check_chat_api_health > /dev/null; then
        echo "Chat API Health: $(echo -e "${GREEN}HEALTHY${NC}")"
    else
        echo "Chat API Health: $(echo -e "${RED}UNHEALTHY${NC}")"
    fi

    if check_websocket_health > /dev/null; then
        echo "WebSocket Health: $(echo -e "${GREEN}HEALTHY${NC}")"
    else
        echo "WebSocket Health: $(echo -e "${RED}UNHEALTHY${NC}")"
    fi
}

# Usage information
show_usage() {
    echo "ATOM Chat Services Monitoring Script"
    echo ""
    echo "Usage: $0 [option]"
    echo ""
    echo "Options:"
    echo "  -c, --continuous    Run continuous monitoring (default)"
    echo "  -s, --single        Run single monitoring check"
    echo "  -t, --status        Show current service status"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --continuous     # Run continuous monitoring"
    echo "  $0 --single         # Run single check"
    echo "  $0 --status         # Show current status"
}

# Main function
main() {
    local mode="continuous"

    # Parse command line arguments
    case "${1:-}" in
        -c|--continuous)
            mode="continuous"
            ;;
        -s|--single)
            mode="single"
            ;;
        -t|--status)
            mode="status"
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        "")
            mode="continuous"
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac

    # Ensure log directory exists
    mkdir -p "$LOG_DIR"

    # Run based on mode
    case "$mode" in
        continuous)
            continuous_monitoring
            ;;
        single)
            single_check
            ;;
        status)
            show_status
            ;;
    esac
}

# Handle script interruption
cleanup() {
    log_info "Monitoring stopped"
    exit 0
}

# Set up signal handlers
trap cleanup INT TERM

# Run main function
main "$@"
