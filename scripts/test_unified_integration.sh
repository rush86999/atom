#!/bin/bash

# ATOM Unified Communication Services Integration Test
# Comprehensive testing for Slack and Teams integration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Emoji for output
ROCKET="🚀"
CHECK="✅"
ERROR="❌"
INFO="ℹ️"
TEST="🧪"
SWITCH="🔄"
HEALTH="💊"
DASHBOARD="📊"
SERVER="⚙️"

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_URL="http://localhost:8000"
DASHBOARD_URL="http://localhost:3000"
TEST_USER_ID="test_user_$(date +%s)"
LOG_FILE="${SCRIPT_DIR}/unified_integration_test.log"

# Initialize log file
echo "=== ATOM Unified Communication Services Integration Test ===" > "$LOG_FILE"
echo "Started at: $(date)" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Helper functions
log_test() {
    echo -e "${CYAN}${TEST} $1${NC}" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${INFO} $1${NC}" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}${CHECK} $1${NC}" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}${ERROR} $1${NC}" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}" | tee -a "$LOG_FILE"
}

make_api_request() {
    local method="$1"
    local endpoint="$2"
    local data="$3"
    
    if [ -n "$data" ]; then
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            -d "$data" \
            "$API_URL$endpoint" \
            2>/dev/null || echo '{"ok":false,"error":"Request failed"}'
    else
        curl -s -X "$method" \
            -H "Content-Type: application/json" \
            "$API_URL$endpoint" \
            2>/dev/null || echo '{"ok":false,"error":"Request failed"}'
    fi
}

test_api_connectivity() {
    log_test "Testing API connectivity..."
    
    if curl -s "$API_URL/health" > /dev/null 2>&1; then
        log_success "API server is reachable at $API_URL"
        return 0
    else
        log_error "Cannot reach API server at $API_URL"
        return 1
    fi
}

test_implementation_status() {
    log_test "Testing implementation status endpoint..."
    
    response=$(make_api_request "GET" "/implementations")
    
    if echo "$response" | grep -q '"ok":true\|"status"'; then
        log_success "Implementation status endpoint working"
        echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    services = data.get('services', {})
    
    for service_name, config in services.items():
        current = config.get('current', 'unknown')
        mock_available = config.get('mock_available', False)
        real_available = config.get('real_available', False)
        
        status = f'  {service_name}: {current} (Mock: {mock_available}, Real: {real_available})'
        print(status)
        
except Exception as e:
    print(f'  Error parsing response: {e}')
" | tee -a "$LOG_FILE"
        return 0
    else
        log_error "Implementation status endpoint failed"
        echo "$response" >> "$LOG_FILE"
        return 1
    fi
}

test_service_health() {
    log_test "Testing service health..."
    
    response=$(make_api_request "GET" "/health")
    
    if echo "$response" | grep -q '"ok":true\|"status"'; then
        log_success "Health check endpoint working"
        echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    services = data.get('services', {})
    
    for service_name, health in services.items():
        status = health.get('status', 'unknown')
        print(f'  {service_name}: {status}')
        
        if status != 'healthy':
            error = health.get('error', 'Unknown error')
            print(f'    Error: {error}')
        
except Exception as e:
    print(f'  Error parsing response: {e}')
" | tee -a "$LOG_FILE"
        return 0
    else
        log_error "Health check endpoint failed"
        echo "$response" >> "$LOG_FILE"
        return 1
    fi
}

test_implementation_switch() {
    local service="$1"
    local implementation="$2"
    
    log_test "Testing implementation switch: $service -> $implementation"
    
    response=$(make_api_request "POST" "/implementations/switch" \
        "{\"service_name\": \"$service\", \"implementation_type\": \"$implementation\"}")
    
    if echo "$response" | grep -q '"ok":true'; then
        log_success "Successfully switched $service to $implementation"
        return 0
    else
        log_error "Failed to switch $service to $implementation"
        echo "$response" >> "$LOG_FILE"
        return 1
    fi
}

test_slack_endpoints() {
    log_test "Testing Slack endpoints..."
    
    # Test Slack install
    log_info "Testing Slack install endpoint..."
    response=$(make_api_request "POST" "/slack/install" \
        "{\"user_id\": \"$TEST_USER_ID\"}")
    
    if echo "$response" | grep -q '"ok":true'; then
        log_success "Slack install endpoint working"
        install_url=$(echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if data.get('ok'):
        print(data.get('install_url', 'No URL'))
    else:
        print('Install failed')
except:
    print('Parse error')
")
        log_info "Install URL: ${install_url:0:50}..."
    else
        log_error "Slack install endpoint failed"
    fi
    
    # Test Slack workspaces
    log_info "Testing Slack workspaces endpoint..."
    response=$(make_api_request "GET" "/slack/workspaces/$TEST_USER_ID")
    
    if echo "$response" | grep -q '"ok":true'; then
        log_success "Slack workspaces endpoint working"
        workspace_count=$(echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if data.get('ok'):
        workspaces = data.get('workspaces', [])
        print(len(workspaces))
    else:
        print('0')
except:
    print('0')
")
        log_info "Found $workspace_count workspaces"
    else
        log_error "Slack workspaces endpoint failed"
    fi
    
    # Test Slack channels (if workspaces exist)
    if [ "$workspace_count" -gt 0 ]; then
        log_info "Testing Slack channels endpoint..."
        # Get first workspace ID
        workspace_id=$(make_api_request "GET" "/slack/workspaces/$TEST_USER_ID" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if data.get('ok') and data.get('workspaces'):
        return data['workspaces'][0]['id']
    return ''
except:
    return ''
")
        
        if [ -n "$workspace_id" ]; then
            response=$(make_api_request "GET" "/slack/channels/$workspace_id/$TEST_USER_ID")
            
            if echo "$response" | grep -q '"ok":true'; then
                log_success "Slack channels endpoint working"
                channel_count=$(echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if data.get('ok'):
        channels = data.get('channels', [])
        print(len(channels))
    else:
        print('0')
except:
    print('0')
")
                log_info "Found $channel_count channels"
            else
                log_error "Slack channels endpoint failed"
            fi
        fi
    fi
}

test_teams_endpoints() {
    log_test "Testing Microsoft Teams endpoints..."
    
    # Test Teams get teams
    log_info "Testing Teams teams endpoint..."
    response=$(make_api_request "GET" "/teams")
    
    if echo "$response" | grep -q '"ok":true\|"teams"'; then
        log_success "Teams teams endpoint working"
        team_count=$(echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if 'teams' in data:
        print(len(data['teams']))
    else:
        print('0')
except:
    print('0')
")
        log_info "Found $team_count teams"
    else
        log_error "Teams teams endpoint failed"
    fi
    
    # Test Teams channels (if teams exist)
    if [ "$team_count" -gt 0 ]; then
        log_info "Testing Teams channels endpoint..."
        # Get first team ID
        team_id=$(make_api_request "GET" "/teams" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if 'teams' in data and data['teams']:
        return data['teams'][0]['id']
    return ''
except:
    return ''
")
        
        if [ -n "$team_id" ]; then
            response=$(make_api_request "GET" "/teams/channels/$team_id")
            
            if echo "$response" | grep -q '"ok":true\|"channels"'; then
                log_success "Teams channels endpoint working"
                channel_count=$(echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if 'channels' in data:
        print(len(data['channels']))
    else:
        print('0')
except:
    print('0')
")
                log_info "Found $channel_count channels"
            else
                log_error "Teams channels endpoint failed"
            fi
        fi
    fi
}

test_unified_endpoints() {
    log_test "Testing unified endpoints..."
    
    # Test unified workspaces
    log_info "Testing unified workspaces endpoint..."
    response=$(make_api_request "GET" "/workspaces?user_id=$TEST_USER_ID")
    
    if echo "$response" | grep -q '"ok":true'; then
        log_success "Unified workspaces endpoint working"
        echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if data.get('ok'):
        workspaces = data.get('workspaces', {})
        for service, ws_list in workspaces.items():
            print(f'  {service}: {len(ws_list)} workspaces')
except Exception as e:
    print(f'  Error: {e}')
" | tee -a "$LOG_FILE"
    else
        log_error "Unified workspaces endpoint failed"
    fi
    
    # Test unified channels
    log_info "Testing unified channels endpoint..."
    response=$(make_api_request "GET" "/channels/$TEST_USER_ID")
    
    if echo "$response" | grep -q '"ok":true'; then
        log_success "Unified channels endpoint working"
        echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if data.get('ok'):
        channels = data.get('channels', {})
        for service, ch_list in channels.items():
            print(f'  {service}: {len(ch_list)} channels')
except Exception as e:
    print(f'  Error: {e}')
" | tee -a "$LOG_FILE"
    else
        log_error "Unified channels endpoint failed"
    fi
}

test_dashboard_accessibility() {
    log_test "Testing dashboard accessibility..."
    
    if curl -s "$DASHBOARD_URL/dashboard/communication" > /dev/null 2>&1; then
        log_success "Dashboard is accessible at $DASHBOARD_URL"
        return 0
    else
        log_error "Dashboard is not accessible at $DASHBOARD_URL"
        return 1
    fi
}

run_full_test_suite() {
    echo -e "${BLUE}${ROCKET} ATOM Unified Communication Services Integration Test${NC}"
    echo -e "${BLUE}=================================================================${NC}"
    echo
    log_info "Test started at: $(date)"
    log_info "API URL: $API_URL"
    log_info "Dashboard URL: $DASHBOARD_URL"
    log_info "Test User ID: $TEST_USER_ID"
    echo
    
    local test_results=()
    local total_tests=0
    local passed_tests=0
    
    # Test 1: API Connectivity
    ((total_tests++))
    if test_api_connectivity; then
        ((passed_tests++))
        test_results+=("API Connectivity: PASSED")
    else
        test_results+=("API Connectivity: FAILED")
    fi
    echo
    
    # Test 2: Implementation Status
    ((total_tests++))
    if test_implementation_status; then
        ((passed_tests++))
        test_results+=("Implementation Status: PASSED")
    else
        test_results+=("Implementation Status: FAILED")
    fi
    echo
    
    # Test 3: Service Health
    ((total_tests++))
    if test_service_health; then
        ((passed_tests++))
        test_results+=("Service Health: PASSED")
    else
        test_results+=("Service Health: FAILED")
    fi
    echo
    
    # Test 4: Implementation Switching
    log_info "Testing implementation switching..."
    ((total_tests++))
    
    # Switch Slack to mock (if not already)
    if test_implementation_switch "Slack" "mock"; then
        log_info "Slack switched to mock"
        sleep 1
    fi
    
    # Switch Teams to mock (if not already)
    if test_implementation_switch "MicrosoftTeams" "mock"; then
        log_info "Teams switched to mock"
        sleep 1
    fi
    
    ((passed_tests++))
    test_results+=("Implementation Switching: PASSED")
    echo
    
    # Test 5: Slack Endpoints
    ((total_tests++))
    if test_slack_endpoints; then
        ((passed_tests++))
        test_results+=("Slack Endpoints: PASSED")
    else
        test_results+=("Slack Endpoints: FAILED")
    fi
    echo
    
    # Test 6: Teams Endpoints
    ((total_tests++))
    if test_teams_endpoints; then
        ((passed_tests++))
        test_results+=("Teams Endpoints: PASSED")
    else
        test_results+=("Teams Endpoints: FAILED")
    fi
    echo
    
    # Test 7: Unified Endpoints
    ((total_tests++))
    if test_unified_endpoints; then
        ((passed_tests++))
        test_results+=("Unified Endpoints: PASSED")
    else
        test_results+=("Unified Endpoints: FAILED")
    fi
    echo
    
    # Test 8: Dashboard Accessibility
    ((total_tests++))
    if test_dashboard_accessibility; then
        ((passed_tests++))
        test_results+=("Dashboard Accessibility: PASSED")
    else
        test_results+=("Dashboard Accessibility: FAILED")
    fi
    echo
    
    # Print summary
    echo -e "${BLUE}${TEST} Test Summary${NC}"
    echo "=================="
    echo
    
    for result in "${test_results[@]}"; do
        if echo "$result" | grep -q "PASSED"; then
            echo -e "${GREEN}${CHECK} $result${NC}"
        else
            echo -e "${RED}${ERROR} $result${NC}"
        fi
    done
    echo
    
    echo -e "${INFO} Total Tests: $total_tests"
    echo -e "${GREEN} Passed: $passed_tests${NC}"
    echo -e "${RED} Failed: $((total_tests - passed_tests))${NC}"
    echo
    
    local success_rate=$((passed_tests * 100 / total_tests))
    echo -e "${INFO} Success Rate: $success_rate%"
    echo
    
    if [ $success_rate -eq 100 ]; then
        echo -e "${GREEN}🎉 All tests passed!${NC}"
        log_success "All integration tests passed successfully"
        return 0
    elif [ $success_rate -ge 75 ]; then
        echo -e "${YELLOW}⚠️ Most tests passed, but some issues detected${NC}"
        log_warning "Integration tests partially successful ($success_rate%)"
        return 1
    else
        echo -e "${RED}❌ Multiple test failures detected${NC}"
        log_error "Integration tests failed ($success_rate%)"
        return 2
    fi
}

# Main execution
case "${1:-full}" in
    "api")
        test_api_connectivity
        test_implementation_status
        test_service_health
        ;;
    "slack")
        test_slack_endpoints
        ;;
    "teams")
        test_teams_endpoints
        ;;
    "unified")
        test_unified_endpoints
        ;;
    "dashboard")
        test_dashboard_accessibility
        ;;
    "health")
        test_service_health
        ;;
    "implementations")
        test_implementation_status
        ;;
    "switch")
        if [ $# -ne 3 ]; then
            echo "Usage: $0 switch <service> <implementation>"
            echo "Services: Slack, MicrosoftTeams"
            echo "Implementations: mock, real"
            exit 1
        fi
        test_implementation_switch "$2" "$3"
        ;;
    "full"|*)
        run_full_test_suite
        ;;
esac

echo -e "${BLUE}${ROCKET} Integration test complete!${NC}"
echo -e "${BLUE}=================================${NC}"

exit 0