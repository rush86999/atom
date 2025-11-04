#!/bin/bash

# ATOM Unified Services Implementation Switcher
# Tool to toggle between Mock and Real services

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
SWITCH="🔄"
CHECK="✅"
ERROR="❌"
INFO="ℹ️"
WARNING="⚠️"
GEAR="⚙️"
MOCK="🎭"
REAL="🌐"

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_URL="http://localhost:8000"
ENV_FILE="${SCRIPT_DIR}/.env"

echo -e "${BLUE}${ROCKET} ATOM Unified Services Implementation Switcher${NC}"
echo -e "${BLUE}=================================================${NC}"
echo

# Helper functions
print_service_status() {
    local service="$1"
    local implementation="$2"
    local available="$3"
    
    if [ "$available" = "true" ]; then
        echo -e "  ${service}:"
        echo -e "    Current: ${implementation}"
        echo -e "    Available: Mock ${CHECK} | Real ${CHECK}"
    else
        echo -e "  ${service}:"
        echo -e "    Current: ${implementation}"
        echo -e "    Available: ${ERROR} Implementation not loaded"
    fi
}

print_implementation_status() {
    echo -e "${CYAN}${GEAR} Current Implementation Status${NC}"
    echo "---------------------------------"
    
    # Get status from API
    if curl -s "${API_URL}/implementations" > /dev/null 2>&1; then
        echo -e "${INFO} Fetching current implementation status..."
        echo
        
        curl -s "${API_URL}/implementations" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    services = data.get('services', {})
    
    for service_name, config in services.items():
        current = config.get('current', 'unknown')
        mock_available = config.get('mock_available', False)
        real_available = config.get('real_available', False)
        
        print(f'  {service_name}:')
        print(f'    Current: {current}')
        print(f'    Mock Available: {\"✅\" if mock_available else \"❌\"}')
        print(f'    Real Available: {\"✅\" if real_available else \"❌\"}')
        print()
        
except Exception as e:
    print(f'Error parsing response: {e}')
    sys.exit(1)
"
    else
        echo -e "${ERROR} Cannot connect to API server at ${API_URL}"
        echo -e "${INFO} Make sure the API server is running:"
        echo -e "${INFO}   python unified_communication_api.py"
        echo
    fi
}

print_health_status() {
    echo -e "${CYAN}${CHECK} Service Health Status${NC}"
    echo "---------------------------"
    
    if curl -s "${API_URL}/health" > /dev/null 2>&1; then
        echo -e "${INFO} Checking service health..."
        echo
        
        curl -s "${API_URL}/health" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    services = data.get('services', {})
    
    overall_status = data.get('status', 'unknown')
    print(f'  Overall: {overall_status}')
    print()
    
    for service_name, health in services.items():
        status = health.get('status', 'unknown')
        print(f'  {service_name}: {status}')
        
        if status != 'healthy':
            error = health.get('error', 'Unknown error')
            print(f'    Error: {error}')
        
except Exception as e:
    print(f'Error parsing health response: {e}')
    sys.exit(1)
"
    else
        echo -e "${ERROR} Cannot connect to API server at ${API_URL}"
        echo -e "${INFO} Make sure the API server is running:"
        echo -e "${INFO}   python unified_communication_api.py"
        echo
    fi
}

switch_implementation() {
    local service="$1"
    local implementation="$2"
    
    echo -e "${YELLOW}${SWITCH} Switching ${service} to ${implementation} implementation...${NC}"
    
    response=$(curl -s -X POST "${API_URL}/implementations/switch" \
        -H "Content-Type: application/json" \
        -d "{\"service_name\": \"${service}\", \"implementation_type\": \"${implementation}\"}" \
        2>/dev/null)
    
    if echo "$response" | grep -q '"ok":true'; then
        echo -e "${GREEN}${CHECK} Successfully switched ${service} to ${implementation} implementation${NC}"
        
        # Extract additional info if available
        new_implementation=$(echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    if data.get('ok'):
        print(data.get('new_implementation', 'unknown'))
except:
    pass
" 2>/dev/null)
        
        echo -e "${INFO} Active implementation: ${new_implementation}"
    else
        echo -e "${RED}${ERROR} Failed to switch ${service} to ${implementation} implementation${NC}"
        
        # Extract error message
        error_msg=$(echo "$response" | python3 -c "
import json
import sys

try:
    data = json.load(sys.stdin)
    print(data.get('error', 'Unknown error'))
except:
    pass
" 2>/dev/null)
        
        echo -e "${ERROR} Details: ${error_msg}"
    fi
    
    echo
}

update_environment_file() {
    local service="$1"
    local implementation="$2"
    
    echo -e "${YELLOW}${GEAR} Updating environment file...${NC}"
    
    # Update environment variable
    env_var="${service^^}_USE_REAL"
    env_value="false"
    
    if [ "$implementation" = "real" ]; then
        env_value="true"
    fi
    
    # Create .env file if it doesn't exist
    if [ ! -f "$ENV_FILE" ]; then
        echo "# ATOM Unified Services Configuration" > "$ENV_FILE"
        echo "# Generated by implementation switcher" >> "$ENV_FILE"
        echo "" >> "$ENV_FILE"
    fi
    
    # Update or add the variable
    if grep -q "^${env_var}=" "$ENV_FILE"; then
        # Update existing variable
        sed -i.bak "s/^${env_var}=.*/${env_var}=${env_value}/" "$ENV_FILE"
        rm -f "${ENV_FILE}.bak"
    else
        # Add new variable
        echo "${env_var}=${env_value}" >> "$ENV_FILE"
    fi
    
    echo -e "${GREEN}${CHECK} Updated ${env_var}=${env_value} in ${ENV_FILE}${NC}"
    echo
}

start_api_server() {
    echo -e "${YELLOW}${GEAR} Starting API server...${NC}"
    
    # Check if server is already running
    if curl -s "${API_URL}/health" > /dev/null 2>&1; then
        echo -e "${INFO} API server is already running at ${API_URL}"
        return 0
    fi
    
    # Start server in background
    echo -e "${INFO} Starting server..."
    cd "${SCRIPT_DIR}/backend/python-api-service"
    python unified_communication_api.py > "${SCRIPT_DIR}/api.log" 2>&1 &
    API_PID=$!
    
    # Wait for server to start
    echo -e "${INFO} Waiting for server to start..."
    for i in {1..10}; do
        if curl -s "${API_URL}/health" > /dev/null 2>&1; then
            echo -e "${GREEN}${CHECK} API server started successfully (PID: ${API_PID})${NC}"
            echo -e "${INFO} Server running at: ${API_URL}"
            echo -e "${INFO} Logs: ${SCRIPT_DIR}/api.log"
            echo
            return 0
        fi
        sleep 1
        echo -n "."
    done
    
    echo
    echo -e "${RED}${ERROR} Failed to start API server${NC}"
    echo -e "${INFO} Check logs: ${SCRIPT_DIR}/api.log"
    kill $API_PID 2>/dev/null || true
    return 1
}

stop_api_server() {
    echo -e "${YELLOW}${GEAR} Stopping API server...${NC}"
    
    # Kill any running Python processes with the API script
    pkill -f "unified_communication_api.py" 2>/dev/null || true
    pkill -f "python.*8000" 2>/dev/null || true
    
    # Wait for server to stop
    sleep 2
    
    if ! curl -s "${API_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}${CHECK} API server stopped successfully${NC}"
    else
        echo -e "${WARNING} API server may still be running${NC}"
    fi
    
    echo
}

show_help() {
    echo -e "${CYAN}Usage:${NC}"
    echo "  $0 [command] [options]"
    echo
    echo -e "${CYAN}Commands:${NC}"
    echo "  status                          Show current implementation status"
    echo "  health                          Show service health status"
    echo "  switch <service> <implementation>   Switch service implementation"
    echo "  start                           Start API server"
    echo "  stop                            Stop API server"
    echo "  restart                         Restart API server"
    echo "  mock <service>                   Switch service to mock implementation"
    echo "  real <service>                   Switch service to real implementation"
    echo "  mock-all                        Switch all services to mock"
    echo "  real-all                        Switch all services to real"
    echo "  help                            Show this help message"
    echo
    echo -e "${CYAN}Services:${NC}"
    echo "  Slack, MicrosoftTeams"
    echo
    echo -e "${CYAN}Implementations:${NC}"
    echo "  mock, real"
    echo
    echo -e "${CYAN}Examples:${NC}"
    echo "  $0 status                                   # Show current status"
    echo "  $0 health                                   # Show health status"
    echo "  $0 switch Slack real                        # Switch Slack to real"
    echo "  $0 switch MicrosoftTeams mock               # Switch Teams to mock"
    echo "  $0 mock Slack                               # Switch Slack to mock"
    echo "  $0 real MicrosoftTeams                       # Switch Teams to real"
    echo "  $0 mock-all                                 # Switch all to mock"
    echo "  $0 real-all                                 # Switch all to real"
    echo "  $0 start                                   # Start API server"
    echo "  $0 stop                                    # Stop API server"
    echo
}

# Parse command line arguments
case "${1:-help}" in
    "status")
        print_implementation_status
        ;;
    "health")
        print_health_status
        ;;
    "switch")
        if [ $# -ne 3 ]; then
            echo -e "${ERROR} Usage: $0 switch <service> <implementation>"
            echo -e "${INFO} Available services: Slack, MicrosoftTeams"
            echo -e "${INFO} Available implementations: mock, real"
            exit 1
        fi
        
        service="$2"
        implementation="$3"
        
        # Validate service
        if [[ ! "$service" =~ ^(Slack|MicrosoftTeams)$ ]]; then
            echo -e "${ERROR} Invalid service: $service"
            echo -e "${INFO} Available services: Slack, MicrosoftTeams"
            exit 1
        fi
        
        # Validate implementation
        if [[ ! "$implementation" =~ ^(mock|real)$ ]]; then
            echo -e "${ERROR} Invalid implementation: $implementation"
            echo -e "${INFO} Available implementations: mock, real"
            exit 1
        fi
        
        # Ensure server is running
        if ! curl -s "${API_URL}/health" > /dev/null 2>&1; then
            start_api_server
        fi
        
        # Switch implementation
        switch_implementation "$service" "$implementation"
        
        # Update environment file
        update_environment_file "$service" "$implementation"
        
        # Show new status
        print_implementation_status
        ;;
    "mock")
        if [ $# -ne 2 ]; then
            echo -e "${ERROR} Usage: $0 mock <service>"
            exit 1
        fi
        "$0" switch "$2" "mock"
        ;;
    "real")
        if [ $# -ne 2 ]; then
            echo -e "${ERROR} Usage: $0 real <service>"
            exit 1
        fi
        "$0" switch "$2" "real"
        ;;
    "mock-all")
        echo -e "${YELLOW}${MOCK} Switching all services to mock implementation...${NC}"
        if ! curl -s "${API_URL}/health" > /dev/null 2>&1; then
            start_api_server
        fi
        
        switch_implementation "Slack" "mock"
        update_environment_file "Slack" "mock"
        
        switch_implementation "MicrosoftTeams" "mock"
        update_environment_file "MicrosoftTeams" "mock"
        
        print_implementation_status
        ;;
    "real-all")
        echo -e "${YELLOW}${REAL} Switching all services to real implementation...${NC}"
        if ! curl -s "${API_URL}/health" > /dev/null 2>&1; then
            start_api_server
        fi
        
        switch_implementation "Slack" "real"
        update_environment_file "Slack" "real"
        
        switch_implementation "MicrosoftTeams" "real"
        update_environment_file "MicrosoftTeams" "real"
        
        print_implementation_status
        ;;
    "start")
        start_api_server
        ;;
    "stop")
        stop_api_server
        ;;
    "restart")
        echo -e "${YELLOW}${GEAR} Restarting API server...${NC}"
        stop_api_server
        sleep 1
        start_api_server
        ;;
    "help"|"-h"|"--help")
        show_help
        ;;
    *)
        echo -e "${ERROR} Unknown command: $1"
        echo
        show_help
        exit 1
        ;;
esac

echo -e "${BLUE}${ROCKET} Implementation switcher complete!${NC}"
echo -e "${BLUE}===================================${NC}"