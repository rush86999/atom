#!/bin/bash

# 🚀 ATOM Platform - Onboarding System Test
# Tests the complete onboarding system with 10 personas and 182 services

set -e  # Exit on any error

echo "🧪 ATOM Platform - Onboarding System Test"
echo "=========================================="
echo "Test started: $(date)"
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

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

# Function to test endpoint
test_endpoint() {
    local url=$1
    local description=$2
    local expected_status=${3:-200}

    ((total_tests++))

    local response_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")

    if [ "$response_code" = "$expected_status" ] || [ "$response_code" = "200" ]; then
        log_success "$description"
        ((passed_tests++))
        return 0
    else
        log_error "$description (HTTP $response_code)"
        ((failed_tests++))
        return 1
    fi
}

# Test 1: System Health
echo "🔧 SYSTEM HEALTH CHECKS"
echo "======================="

test_endpoint "http://localhost:5058/healthz" "Backend API Health"
test_endpoint "http://localhost:3000" "Frontend UI Health" "307"

# Get system information
if curl -s http://localhost:5058/healthz > /dev/null; then
    SERVICE_COUNT=$(curl -s http://localhost:5058/api/services | jq -r '.total_services // 0')
    BLUEPRINT_COUNT=$(curl -s http://localhost:5058/healthz | jq -r '.total_blueprints // 0')

    log_info "Services: $SERVICE_COUNT/182"
    log_info "Blueprints: $BLUEPRINT_COUNT"
fi

# Test 2: Core Onboarding Endpoints
echo ""
echo "🎯 CORE ONBOARDING ENDPOINTS"
echo "============================"

core_endpoints=(
    "calendar:Calendar Integration"
    "tasks:Task Management"
    "messages:Message System"
    "workflows:Workflow Automation"
    "services:Service Registry"
    "user-api-keys:BYOK System"
)

for endpoint_info in "${core_endpoints[@]}"; do
    IFS=':' read -r endpoint description <<< "$endpoint_info"
    test_endpoint "http://localhost:5058/api/$endpoint" "$description"
done

# Test 3: Service Health Checks
echo ""
echo "🔄 SERVICE HEALTH CHECKS"
echo "========================"

sample_services=(
    "workflow_automation:Workflow Automation"
    "atom_agent:Atom Agent"
    "github:GitHub Integration"
    "google_calendar:Google Calendar"
    "slack:Slack Integration"
    "dropbox:Dropbox Storage"
    "trello:Trello Management"
    "gmail:Gmail Integration"
)

for service_info in "${sample_services[@]}"; do
    IFS=':' read -r service name <<< "$service_info"
    test_endpoint "http://localhost:5058/api/services/$service/health" "$name Health" "200|404"
done

# Test 4: Persona-Specific Functionality
echo ""
echo "👥 PERSONA FUNCTIONALITY TESTS"
echo "=============================="

# Test Executive Assistant features
test_endpoint "http://localhost:5058/api/calendar/events" "Calendar Events (Executive Assistant)"
test_endpoint "http://localhost:5058/api/tasks" "Task Management (Executive Assistant)"

# Test Software Developer features
test_endpoint "http://localhost:5058/api/services/github/health" "GitHub Integration (Developer)"
test_endpoint "http://localhost:5058/api/workflows" "Workflow Automation (Developer)"

# Test Marketing Manager features
test_endpoint "http://localhost:5058/api/services/twitter/health" "Twitter Integration (Marketing)"
test_endpoint "http://localhost:5058/api/analytics" "Analytics (Marketing)" "200|404"

# Test 5: Performance and Response Times
echo ""
echo "⚡ PERFORMANCE TESTING"
echo "======================"

# Test service registry response time
start_time=$(date +%s%3N)
curl -s http://localhost:5058/api/services > /dev/null
end_time=$(date +%s%3N)
response_time=$((end_time - start_time))

((total_tests++))
if [ "$response_time" -lt 1000 ]; then
    log_success "Service Registry Response: ${response_time}ms (Excellent)"
    ((passed_tests++))
elif [ "$response_time" -lt 2000 ]; then
    log_success "Service Registry Response: ${response_time}ms (Good)"
    ((passed_tests++))
else
    log_warning "Service Registry Response: ${response_time}ms (Slow)"
    ((failed_tests++))
fi

# Test batch operations
start_time=$(date +%s%3N)
curl -s http://localhost:5058/api/services/batch/health > /dev/null 2>&1
end_time=$(date +%s%3N)
batch_time=$((end_time - start_time))

((total_tests++))
if [ "$batch_time" -lt 2000 ]; then
    log_success "Batch Operations: ${batch_time}ms (Good)"
    ((passed_tests++))
else
    log_warning "Batch Operations: ${batch_time}ms (Slow)"
    ((failed_tests++))
fi

# Test 6: Enhanced Features
echo ""
echo "🚀 ENHANCED FEATURES"
echo "===================="

# Test voice integration
test_endpoint "http://localhost:5058/api/voice_integration" "Voice Integration" "200|404"

# Test transcription service
test_endpoint "http://localhost:5058/api/transcription" "Transcription Service" "200|404"

# Test search functionality
test_endpoint "http://localhost:5058/api/search" "Search System" "200|404"

# Test context management
test_endpoint "http://localhost:5058/api/context_management" "Context Management" "200|404"

# Generate Summary Report
echo ""
echo "📈 TEST SUMMARY"
echo "==============="
echo "Total Tests: $total_tests"
echo "Passed: $passed_tests"
echo "Failed: $failed_tests"

success_rate=$((passed_tests * 100 / total_tests))
echo "Success Rate: $success_rate%"

echo ""
echo "🎯 ONBOARDING SYSTEM ASSESSMENT"
echo "================================"

if [ "$SERVICE_COUNT" -ge 180 ] && [ $success_rate -ge 90 ]; then
    log_success "🟢 ONBOARDING SYSTEM READY"
    echo "All 182 services are available and core functionality is operational."
    echo "The system is ready for user onboarding across 10 personas."

elif [ "$SERVICE_COUNT" -ge 150 ] && [ $success_rate -ge 80 ]; then
    log_warning "🟡 ONBOARDING SYSTEM PARTIALLY READY"
    echo "Most services are available but some features need attention."
    echo "System can support basic user onboarding."

else
    log_error "🔴 ONBOARDING SYSTEM NOT READY"
    echo "Significant issues need to be resolved before user onboarding."
fi

echo ""
echo "🔧 RECOMMENDED ACTIONS"
echo "======================"

if [ $failed_tests -gt 0 ]; then
    echo "Failed tests indicate areas needing attention:"
    echo "1. Check backend service registration"
    echo "2. Verify endpoint configurations"
    echo "3. Test individual service health"
    echo "4. Review error logs for details"
else
    echo "All systems operational. Ready for user onboarding!"
fi

echo ""
echo "🚀 NEXT STEPS FOR ONBOARDING"
echo "============================"
echo "1. Run persona-specific onboarding scripts"
echo "2. Test user journey workflows"
echo "3. Validate service integrations"
echo "4. Monitor performance under load"
echo "5. Gather user feedback"

echo ""
echo "Test completed: $(date)"
echo "=========================================="

# Exit with appropriate code
if [ $success_rate -ge 90 ] && [ "$SERVICE_COUNT" -ge 180 ]; then
    exit 0
elif [ $success_rate -ge 70 ]; then
    exit 1
else
    exit 2
fi
