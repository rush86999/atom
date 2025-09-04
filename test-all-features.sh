#!/bin/bash
# Atom Comprehensive Feature Test Script
# Tests all major components and features of the Atom application

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Atom Comprehensive Feature Test${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# Function to test service
test_service() {
    local service_name=$1
    local url=$2
    local expected_status=${3:-200}

    echo -e "${BLUE}Testing $service_name...${NC}"
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected_status"; then
        echo -e "${GREEN}✅ $service_name is working${NC}"
        return 0
    else
        echo -e "${RED}❌ $service_name is not responding${NC}"
        return 1
    fi
}

# Function to test API endpoint
test_api_endpoint() {
    local endpoint_name=$1
    local url=$2
    local expected_field=$3

    echo -e "${BLUE}Testing $endpoint_name...${NC}"
    response=$(curl -s "$url")

    if [ $? -eq 0 ] && [ -n "$response" ]; then
        if [ -n "$expected_field" ] && echo "$response" | jq -e ".$expected_field" > /dev/null; then
            echo -e "${GREEN}✅ $endpoint_name is working${NC}"
            return 0
        elif [ -z "$expected_field" ]; then
            echo -e "${GREEN}✅ $endpoint_name is working${NC}"
            return 0
        else
            echo -e "${YELLOW}⚠️  $endpoint_name responded but missing expected field '$expected_field'${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ $endpoint_name failed${NC}"
        return 1
    fi
}

# Test Results tracking
# Use regular arrays instead of associative arrays for compatibility
test_results=()
test_names=()
tests_passed=0
tests_failed=0
test_index=0

echo -e "${BLUE}📋 Testing Core Services${NC}"
echo -e "${BLUE}=======================${NC}"

# Test Frontend
if test_service "Frontend (Port 3000)" "http://localhost:3000" "200"; then
    test_names[$test_index]="frontend"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="frontend"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

# Test Python API Service
if test_service "Python API (Port 5058)" "http://localhost:5058/healthz" "200"; then
    test_names[$test_index]="python_api"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="python_api"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

# Test Workflows Service
if test_service "Workflows API (Port 8003)" "http://localhost:8003/healthz" "200"; then
    test_names[$test_index]="workflows_api"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="workflows_api"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

echo ""
echo -e "${BLUE}📋 Testing API Endpoints${NC}"
echo -e "${BLUE}=======================${NC}"

# Test Dashboard API
if test_api_endpoint "Dashboard API" "http://localhost:3000/api/dashboard-dev" "stats"; then
    test_names[$test_index]="dashboard_api"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="dashboard_api"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

# Test Workflows List
if test_api_endpoint "Workflows List" "http://localhost:8003/workflows" "workflows"; then
    test_names[$test_index]="workflows_list"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="workflows_list"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

# Test Python API Root
if test_api_endpoint "Python API Root" "http://localhost:5058" "service"; then
    test_names[$test_index]="python_api_root"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="python_api_root"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

echo ""
echo -e "${BLUE}📋 Testing Development Pages${NC}"
echo -e "${BLUE}===========================${NC}"

# Test Development Dashboard
if test_service "Development Dashboard" "http://localhost:3000/index-dev" "200"; then
    test_names[$test_index]="dev_dashboard"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="dev_dashboard"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

# Test Login Page
if test_service "Login Page" "http://localhost:3000/User/Login/UserLogin" "200"; then
    test_names[$test_index]="login_page"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="login_page"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

# Test Automations Page
if test_service "Automations Page" "http://localhost:3000/Automations" "200"; then
    test_names[$test_index]="automations_page"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="automations_page"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

echo ""
echo -e "${BLUE}📋 Testing Data Endpoints${NC}"
echo -e "${BLUE}========================${NC}"

# Test Dashboard Data
echo -e "${BLUE}Testing Dashboard Data...${NC}"
dashboard_data=$(curl -s "http://localhost:3000/api/dashboard-dev")
if echo "$dashboard_data" | jq -e '.stats' > /dev/null; then
    echo -e "${GREEN}✅ Dashboard data structure is valid${NC}"
    test_names[$test_index]="dashboard_data"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="dashboard_data"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

# Test Workflows Data
echo -e "${BLUE}Testing Workflows Data...${NC}"
workflows_data=$(curl -s "http://localhost:8003/workflows")
if echo "$workflows_data" | jq -e '.workflows' > /dev/null; then
    echo -e "${GREEN}✅ Workflows data structure is valid${NC}"
    test_names[$test_index]="workflows_data"
    test_results[$test_index]="PASS"
    ((tests_passed++))
    ((test_index++))
else
    test_names[$test_index]="workflows_data"
    test_results[$test_index]="FAIL"
    ((tests_failed++))
    ((test_index++))
fi

echo ""
echo -e "${BLUE}📊 Test Results Summary${NC}"
echo -e "${BLUE}======================${NC}"

# Print individual test results
for i in "${!test_names[@]}"; do
    test_name="${test_names[$i]}"
    status="${test_results[$i]}"
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✅ $test_name: PASS${NC}"
    else
        echo -e "${RED}❌ $test_name: FAIL${NC}"
    fi
done

echo ""
echo -e "${BLUE}📈 Overall Results${NC}"
echo -e "${BLUE}=================${NC}"

echo -e "Total Tests: $((tests_passed + tests_failed))"
echo -e "${GREEN}Passed: $tests_passed${NC}"
echo -e "${RED}Failed: $tests_failed${NC}"

if [ $tests_failed -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! Atom is fully operational.${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed. Check the services and try again.${NC}"
fi

echo ""
echo -e "${BLUE}🌐 Access URLs${NC}"
echo -e "${BLUE}=============${NC}"
echo -e "Frontend:          ${GREEN}http://localhost:3000${NC}"
echo -e "Development Dashboard: ${GREEN}http://localhost:3000/index-dev${NC}"
echo -e "Login Page:        ${GREEN}http://localhost:3000/User/Login/UserLogin${NC}"
echo -e "Automations:       ${GREEN}http://localhost:3000/Automations${NC}"
echo -e "Python API:        ${GREEN}http://localhost:5058${NC}"
echo -e "Workflows API:     ${GREEN}http://localhost:8003${NC}"
echo -e "Dashboard API:     ${GREEN}http://localhost:3000/api/dashboard-dev${NC}"

echo ""
echo -e "${BLUE}🚀 Next Steps${NC}"
echo -e "${BLUE}=============${NC}"
echo "1. Configure authentication (SuperTokens)"
echo "2. Set up OAuth credentials for integrations"
echo "3. Connect real services (Google, Outlook, Slack, etc.)"
echo "4. Implement voice features and meeting transcription"
echo "5. Deploy to production environment"

exit $tests_failed
