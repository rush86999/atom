#!/bin/bash

# 🚀 ATOM Platform - Production Validation Script
# Validates all systems for production readiness

set -e  # Exit on any error

echo "🔍 ATOM Platform - Production Validation"
echo "========================================"
echo "Validation started: $(date)"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to log with colors
log_info() { echo -e "${BLUE}ℹ️ $1${NC}"; }
log_success() { echo -e "${GREEN}✅ $1${NC}"; }
log_warning() { echo -e "${YELLOW}⚠️ $1${NC}"; }
log_error() { echo -e "${RED}❌ $1${NC}"; }

# Function to test endpoint
test_endpoint() {
    local url=$1
    local description=$2
    local expected_status=${3:-200}

    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "$expected_status"; then
        log_success "$description"
        return 0
    else
        log_error "$description"
        return 1
    fi
}

# Function to test API endpoint with JSON response
test_api_endpoint() {
    local url=$1
    local description=$2
    local check_field=$3

    response=$(curl -s "$url")
    if echo "$response" | jq -e '.success' >/dev/null 2>&1; then
        if [ -n "$check_field" ]; then
            field_value=$(echo "$response" | jq -r ".$check_field")
            log_success "$description - $check_field: $field_value"
        else
            log_success "$description"
        fi
        return 0
    else
        log_error "$description"
        return 1
    fi
}

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

echo "📊 VALIDATION STARTED"
echo "===================="

# Test 1: Backend Health
echo ""
echo "🔧 BACKEND HEALTH CHECKS"
echo "------------------------"
((total_tests++))
if test_endpoint "http://localhost:5058/healthz" "Backend API Health"; then
    ((passed_tests++))

    # Get detailed health info
    health_info=$(curl -s http://localhost:5058/healthz)
    blueprint_count=$(echo "$health_info" | jq -r '.total_blueprints // 0')
    service_status=$(echo "$health_info" | jq -r '.status')

    log_info "  Blueprints: $blueprint_count"
    log_info "  Status: $service_status"
else
    ((failed_tests++))
fi

# Test 2: Frontend Health
((total_tests++))
if test_endpoint "http://localhost:3000" "Frontend UI" "307"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi

# Test 3: Service Registry
echo ""
echo "🔄 SERVICE REGISTRY"
echo "------------------"
((total_tests++))
if test_api_endpoint "http://localhost:5058/api/services" "Service Registry" "total_services"; then
    ((passed_tests++))

    # List top services
    services=$(curl -s http://localhost:5058/api/services | jq -r '.services[0:5] | .[] | "  - \(.name) (\(.status))"')
    log_info "Top Services:"
    echo "$services"
else
    ((failed_tests++))
fi

# Test 4: Core API Endpoints
echo ""
echo "🎯 CORE API ENDPOINTS"
echo "---------------------"

core_endpoints=(
    "tasks:Task Management"
    "calendar/events:Calendar Integration"
    "messages:Message System"
    "workflows:Workflow Automation"
    "user-api-keys:BYOK System"
)

for endpoint_info in "${core_endpoints[@]}"; do
    IFS=':' read -r endpoint description <<< "$endpoint_info"
    ((total_tests++))
    if test_api_endpoint "http://localhost:5058/api/$endpoint" "$description"; then
        ((passed_tests++))
    else
        ((failed_tests++))
    fi
done

# Test 5: OAuth Services
echo ""
echo "🔐 OAUTH SERVICES"
echo "-----------------"

oauth_services=(
    "github:GitHub"
    "google:Google"
    "slack:Slack"
    "dropbox:Dropbox"
    "trello:Trello"
)

for service_info in "${oauth_services[@]}"; do
    IFS=':' read -r service name <<< "$service_info"
    ((total_tests++))
    if test_endpoint "http://localhost:5058/api/services/$service/health" "$name OAuth Health" "200\|404"; then
        ((passed_tests++))
    else
        ((failed_tests++))
    fi
done

# Test 6: Advanced Features
echo ""
echo "🚀 ADVANCED FEATURES"
echo "-------------------"

advanced_endpoints=(
    "voice_integration:Voice Integration"
    "transcription:Meeting Transcription"
    "search:Search System"
    "context_management:Context Management"
)

for endpoint_info in "${advanced_endpoints[@]}"; do
    IFS=':' read -r endpoint description <<< "$endpoint_info"
    ((total_tests++))
    if test_endpoint "http://localhost:5058/api/$endpoint" "$description" "200\|404"; then
        ((passed_tests++))
    else
        ((failed_tests++))
    fi
done

# Test 7: Database Connectivity
echo ""
echo "🗄️ DATABASE CONNECTIVITY"
echo "-----------------------"
((total_tests++))
if curl -s http://localhost:5058/healthz | jq -e '.database' >/dev/null 2>&1; then
    ((passed_tests++))
    db_info=$(curl -s http://localhost:5058/healthz | jq -r '.database | to_entries | .[] | "  - \(.key): \(.value)"')
    log_success "Database Systems"
    echo "$db_info"
else
    ((failed_tests++))
    log_error "Database connectivity check failed"
fi

# Test 8: Performance Check
echo ""
echo "⚡ PERFORMANCE CHECK"
echo "-------------------"
((total_tests++))
start_time=$(date +%s%3N)
curl -s http://localhost:5058/healthz > /dev/null
end_time=$(date +%s%3N)
response_time=$((end_time - start_time))

if [ "$response_time" -lt 1000 ]; then
    ((passed_tests++))
    log_success "Response Time: ${response_time}ms (Excellent)"
elif [ "$response_time" -lt 2000 ]; then
    ((passed_tests++))
    log_success "Response Time: ${response_time}ms (Good)"
else
    ((failed_tests++))
    log_warning "Response Time: ${response_time}ms (Slow)"
fi

# Generate Summary Report
echo ""
echo "📈 VALIDATION SUMMARY"
echo "===================="
echo "Total Tests: $total_tests"
echo "Passed: $passed_tests"
echo "Failed: $failed_tests"

success_rate=$((passed_tests * 100 / total_tests))
echo "Success Rate: $success_rate%"

echo ""
echo "🎯 PRODUCTION READINESS ASSESSMENT"
echo "=================================="

if [ $success_rate -ge 90 ]; then
    log_success "🟢 PRODUCTION READY - $success_rate% success rate"
    echo "The platform is ready for production deployment."
elif [ $success_rate -ge 70 ]; then
    log_warning "🟡 NEARLY READY - $success_rate% success rate"
    echo "Minor issues need addressing before production."
else
    log_error "🔴 NOT READY - $success_rate% success rate"
    echo "Significant issues need to be resolved."
fi

echo ""
echo "🔧 RECOMMENDED ACTIONS"
echo "======================"

if [ $failed_tests -gt 0 ]; then
    echo "Failed tests indicate areas needing attention:"
    echo "1. Check backend logs for errors"
    echo "2. Verify service configurations"
    echo "3. Test database connectivity"
    echo "4. Validate OAuth service credentials"
else
    echo "All systems operational. Ready for deployment!"
fi

echo ""
echo "📊 NEXT STEPS"
echo "============="
echo "1. Run: ./MONITOR_SYSTEM.sh (for ongoing monitoring)"
echo "2. Review: README_USER_JOURNEY_VALIDATION.md (for persona testing)"
echo "3. Deploy: Follow IMMEDIATE_PRODUCTION_DEPLOYMENT.md"
echo "4. Monitor: Check logs in backend_production.log and frontend_production.log"

echo ""
echo "Validation completed: $(date)"
echo "========================================"

# Exit with appropriate code
if [ $success_rate -ge 90 ]; then
    exit 0
elif [ $success_rate -ge 70 ]; then
    exit 1
else
    exit 2
fi
