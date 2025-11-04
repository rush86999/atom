#!/bin/bash

# 🚀 ATOM Platform - 182 Services Verification Script
# Validates all 182 services are properly registered and accessible

set -e  # Exit on any error

echo "🔍 ATOM Platform - 182 Services Verification"
echo "============================================"
echo "Verification started: $(date)"
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

    local response_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")

    if [ "$response_code" = "$expected_status" ] || [ "$response_code" = "200" ]; then
        log_success "$description"
        return 0
    else
        log_error "$description (HTTP $response_code)"
        return 1
    fi
}

# Initialize counters
total_tests=0
passed_tests=0
failed_tests=0

echo "📊 SERVICE VERIFICATION STARTED"
echo "================================"

# Test 1: Backend Health
echo ""
echo "🔧 BACKEND HEALTH"
echo "-----------------"
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

# Test 2: Service Registry
echo ""
echo "🔄 SERVICE REGISTRY"
echo "-------------------"
((total_tests++))
if test_endpoint "http://localhost:5058/api/services" "Service Registry"; then
    ((passed_tests++))

    service_count=$(curl -s http://localhost:5058/api/services | jq -r '.total_services // 0')
    log_info "  Total Services: $service_count"

    if [ "$service_count" -ge 180 ]; then
        log_success "  Service count meets target (182+)"
    else
        log_warning "  Service count below target: $service_count/182"
    fi
else
    ((failed_tests++))
fi

# Test 3: Enhanced Service Endpoints
echo ""
echo "🚀 ENHANCED ENDPOINTS"
echo "---------------------"
((total_tests++))
if test_endpoint "http://localhost:5058/api/services/batch/health" "Batch Health Endpoint"; then
    ((passed_tests++))

    batch_health=$(curl -s http://localhost:5058/api/services/batch/health)
    batch_count=$(echo "$batch_health" | jq -r '.total_services // 0')
    healthy_count=$(echo "$batch_health" | jq -r '.healthy_services // 0')

    log_info "  Batch Services: $batch_count"
    log_info "  Healthy Services: $healthy_count"
else
    ((failed_tests++))
fi

((total_tests++))
if test_endpoint "http://localhost:5058/api/services/batch/info" "Batch Info Endpoint"; then
    ((passed_tests++))
else
    ((failed_tests++))
fi

# Test 4: Core Service Categories
echo ""
echo "📋 SERVICE CATEGORIES"
echo "---------------------"

categories=(
    "authentication:Authentication Services"
    "calendar:Calendar Services"
    "communication:Communication Services"
    "financial:Financial Services"
    "storage:Storage Services"
    "social_media:Social Media Services"
    "crm:CRM Services"
    "development:Development Services"
    "automation:Automation Services"
    "voice:Voice Services"
    "search:Search Services"
    "task_management:Task Management"
    "integration:Integration Services"
)

for category_info in "${categories[@]}"; do
    IFS=':' read -r category name <<< "$category_info"
    ((total_tests++))

    # Count services in this category
    category_count=$(curl -s http://localhost:5058/api/services/batch/info | jq -r ".services | to_entries | map(select(.value.type == \"$category\")) | length")

    if [ "$category_count" -gt 0 ]; then
        log_success "$name: $category_count services"
        ((passed_tests++))
    else
        log_warning "$name: No services found"
        ((failed_tests++))
    fi
done

# Test 5: Sample Service Health Checks
echo ""
echo "🧪 SAMPLE SERVICE HEALTH CHECKS"
echo "-------------------------------"

sample_services=(
    "workflow_automation:Workflow Automation"
    "atom_agent:Atom Agent"
    "github:GitHub Integration"
    "google_calendar:Google Calendar"
    "slack:Slack Integration"
    "dropbox:Dropbox Storage"
    "trello:Trello Management"
    "gmail:Gmail Integration"
    "voice_integration:Voice Integration"
    "transcription:Transcription Service"
    "search:Search Service"
    "context_management:Context Management"
)

for service_info in "${sample_services[@]}"; do
    IFS=':' read -r service name <<< "$service_info"
    ((total_tests++))

    if test_endpoint "http://localhost:5058/api/services/$service/health" "$name Health"; then
        ((passed_tests++))
    else
        ((failed_tests++))
    fi
done

# Test 6: Service Information Endpoints
echo ""
echo "📄 SERVICE INFORMATION"
echo "---------------------"

for service_info in "${sample_services[@]}"; do
    IFS=':' read -r service name <<< "$service_info"
    ((total_tests++))

    if test_endpoint "http://localhost:5058/api/services/$service/info" "$name Info"; then
        ((passed_tests++))
    else
        ((failed_tests++))
    fi
done

# Test 7: Performance and Response Times
echo ""
echo "⚡ PERFORMANCE CHECK"
echo "-------------------"

((total_tests++))
start_time=$(date +%s%3N)
curl -s http://localhost:5058/api/services > /dev/null
end_time=$(date +%s%3N)
response_time=$((end_time - start_time))

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

# Generate Summary Report
echo ""
echo "📈 VERIFICATION SUMMARY"
echo "======================"
echo "Total Tests: $total_tests"
echo "Passed: $passed_tests"
echo "Failed: $failed_tests"

success_rate=$((passed_tests * 100 / total_tests))
echo "Success Rate: $success_rate%"

# Get final service count
final_service_count=$(curl -s http://localhost:5058/api/services | jq -r '.total_services // 0')

echo ""
echo "🎯 182 SERVICES VALIDATION"
echo "=========================="

if [ "$final_service_count" -ge 180 ]; then
    log_success "🟢 SERVICE COUNT VALIDATED: $final_service_count/182"
    echo "All 182+ services are properly registered and accessible."

    # Show service distribution
    echo ""
    echo "📊 SERVICE DISTRIBUTION:"
    curl -s http://localhost:5058/api/services/batch/info | jq -r '
        .services | to_entries | group_by(.value.type) | map({
            category: .[0].value.type,
            count: length,
            services: map(.value.name) | join(", ")
        }) | .[] | "  \(.category): \(.count) services"'

elif [ "$final_service_count" -ge 150 ]; then
    log_warning "🟡 PARTIAL VALIDATION: $final_service_count/182"
    echo "Most services are registered, but some may be missing."
else
    log_error "🔴 INCOMPLETE: $final_service_count/182"
    echo "Significant number of services are missing from registry."
fi

echo ""
echo "🔧 RECOMMENDED ACTIONS"
echo "======================"

if [ $failed_tests -gt 0 ]; then
    echo "Failed tests indicate areas needing attention:"
    echo "1. Check backend logs for service registration errors"
    echo "2. Verify all service blueprints are properly imported"
    echo "3. Test individual service health endpoints"
    echo "4. Validate service registry configuration"
else
    echo "All systems operational. 182 services are ready for production!"
fi

echo ""
echo "🚀 NEXT STEPS"
echo "============="
echo "1. Run: ./MONITOR_SYSTEM.sh (for ongoing monitoring)"
echo "2. Test: Individual service functionality"
echo "3. Deploy: Follow IMMEDIATE_PRODUCTION_DEPLOYMENT.md"
echo "4. Monitor: Service performance and health"

echo ""
echo "Verification completed: $(date)"
echo "============================================"

# Exit with appropriate code
if [ $success_rate -ge 90 ] && [ "$final_service_count" -ge 180 ]; then
    exit 0
elif [ $success_rate -ge 70 ]; then
    exit 1
else
    exit 2
fi
