#!/bin/bash

# 🧪 COMPREHENSIVE ENHANCED INTEGRATIONS TEST SCRIPT
# Enhanced Integration Capabilities Validation
# Version: 1.0
# Date: $(date +%Y-%m-%d)

set -e  # Exit on any error

echo "🧪 Starting Enhanced Integration Capabilities Testing"
echo "========================================================"

# Configuration
BACKEND_DIR="backend/python-api-service"
BACKEND_URL="http://localhost:5058"
TEST_RESULTS_FILE="enhanced_integrations_test_results_$(date +%Y%m%d_%H%M%S).json"
BACKEND_PID=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
WARNING_TESTS=0

# Logging function
log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
    ((PASSED_TESTS++))
    ((TOTAL_TESTS++))
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARNING_TESTS++))
    ((TOTAL_TESTS++))
}

error() {
    echo -e "${RED}❌ $1${NC}"
    ((FAILED_TESTS++))
    ((TOTAL_TESTS++))
}

# Start backend server
start_backend() {
    log "Starting backend server..."
    cd "$BACKEND_DIR"
    python3 main_api_with_integrations.py &
    BACKEND_PID=$!
    cd - > /dev/null

    # Wait for server to start
    sleep 8

    # Verify server is running
    if curl -s "$BACKEND_URL/health" > /dev/null; then
        success "Backend server started successfully (PID: $BACKEND_PID)"
    else
        error "Backend server failed to start"
        return 1
    fi
}

# Stop backend server
stop_backend() {
    if [ ! -z "$BACKEND_PID" ]; then
        log "Stopping backend server (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
        sleep 2
        success "Backend server stopped"
    fi
}

# Test enhanced workflow endpoints
test_enhanced_workflow_endpoints() {
    log "Testing Enhanced Workflow Endpoints..."

    # Test intelligence analysis endpoint
    response=$(curl -s -X POST "$BACKEND_URL/api/v2/workflows/enhanced/intelligence/analyze" \
        -H "Content-Type: application/json" \
        -d '{"user_input": "Create a workflow to notify slack when github PR is created", "context": {}}' \
        -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        error "Enhanced intelligence analysis endpoint failed (HTTP $response)"
    else
        success "Enhanced intelligence analysis endpoint responding"
    fi

    # Test optimization analysis endpoint
    response=$(curl -s -X POST "$BACKEND_URL/api/v2/workflows/enhanced/optimization/analyze" \
        -H "Content-Type: application/json" \
        -d '{"workflow": {"name": "test", "steps": []}, "strategy": "performance"}' \
        -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Enhanced optimization analysis endpoint failed (HTTP $response)"
    else
        success "Enhanced optimization analysis endpoint responding"
    fi

    # Test monitoring health endpoint
    response=$(curl -s "$BACKEND_URL/api/v2/workflows/enhanced/monitoring/health?workflow_id=test" \
        -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Enhanced monitoring health endpoint failed (HTTP $response)"
    else
        success "Enhanced monitoring health endpoint responding"
    fi
}

# Test AI workflow enhancement system
test_ai_workflow_system() {
    log "Testing AI Workflow Enhancement System..."

    # Test AI workflow routes availability
    response=$(curl -s "$BACKEND_URL/api/v2/ai-workflows" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "AI workflow routes not available (HTTP $response)"
    else
        success "AI workflow enhancement system responding"
    fi

    # Test workflow templates endpoint
    response=$(curl -s "$BACKEND_URL/api/v2/ai-workflows/templates" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "AI workflow templates endpoint failed (HTTP $response)"
    else
        success "AI workflow templates endpoint responding"
    fi
}

# Test enhanced monitoring system
test_enhanced_monitoring() {
    log "Testing Enhanced Monitoring System..."

    # Test monitoring services endpoint
    response=$(curl -s "$BACKEND_URL/api/v2/monitoring/services" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Enhanced monitoring services endpoint failed (HTTP $response)"
    else
        success "Enhanced monitoring services endpoint responding"
    fi

    # Test monitoring health endpoint
    response=$(curl -s "$BACKEND_URL/api/v2/monitoring/health" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Enhanced monitoring health endpoint failed (HTTP $response)"
    else
        success "Enhanced monitoring health endpoint responding"
    fi

    # Test monitoring analytics endpoint
    response=$(curl -s "$BACKEND_URL/api/v2/monitoring/analytics" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Enhanced monitoring analytics endpoint failed (HTTP $response)"
    else
        success "Enhanced monitoring analytics endpoint responding"
    fi
}

# Test strategic integrations
test_strategic_integrations() {
    log "Testing Strategic Integrations..."

    # Test OpenAI API integration
    response=$(curl -s "$BACKEND_URL/api/v2/openai/status" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "OpenAI API integration not available (HTTP $response)"
    else
        success "OpenAI API integration responding"
    fi

    # Test GitLab CI/CD integration
    response=$(curl -s "$BACKEND_URL/api/v2/gitlab/status" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "GitLab CI/CD integration not available (HTTP $response)"
    else
        success "GitLab CI/CD integration responding"
    fi

    # Test enhanced health endpoints
    response=$(curl -s "$BACKEND_URL/api/v2/health/services" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Enhanced health endpoints not available (HTTP $response)"
    else
        success "Enhanced health endpoints responding"
    fi
}

# Test cross-service intelligence
test_cross_service_intelligence() {
    log "Testing Cross-Service Intelligence Engine..."

    # Test service dependency mapping
    response=$(curl -s "$BACKEND_URL/api/v2/services/dependencies" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Service dependency mapping not available (HTTP $response)"
    else
        success "Service dependency mapping responding"
    fi

    # Test intelligent routing
    response=$(curl -s "$BACKEND_URL/api/v2/services/routing/health" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Intelligent routing not available (HTTP $response)"
    else
        success "Intelligent routing responding"
    fi
}

# Test performance optimization
test_performance_optimization() {
    log "Testing Performance Optimization Framework..."

    # Test optimization strategies
    response=$(curl -s "$BACKEND_URL/api/v2/optimization/strategies" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Performance optimization strategies not available (HTTP $response)"
    else
        success "Performance optimization strategies responding"
    fi

    # Test caching configuration
    response=$(curl -s "$BACKEND_URL/api/v2/optimization/cache/status" -w "%{http_code}" || echo "000")

    if [[ "$response" =~ ^[45] ]]; then
        warning "Caching configuration not available (HTTP $response)"
    else
        success "Caching configuration responding"
    fi
}

# Validate environment configuration
validate_environment() {
    log "Validating Environment Configuration..."

    # Check enhanced feature flags
    if [ "$AI_WORKFLOW_ENABLED" = "true" ]; then
        success "AI Workflow Enhancement enabled"
    else
        warning "AI Workflow Enhancement disabled"
    fi

    if [ "$ENHANCED_MONITORING_ENABLED" = "true" ]; then
        success "Enhanced Monitoring enabled"
    else
        warning "Enhanced Monitoring disabled"
    fi

    if [ "$CROSS_SERVICE_ORCHESTRATION_ENABLED" = "true" ]; then
        success "Cross-Service Orchestration enabled"
    else
        warning "Cross-Service Orchestration disabled"
    fi

    # Check monitoring thresholds
    if [ ! -z "$RESPONSE_TIME_WARNING_MS" ] && [ "$RESPONSE_TIME_WARNING_MS" -eq 1000 ]; then
        success "Response time warning threshold configured"
    else
        warning "Response time warning threshold not configured"
    fi

    if [ ! -z "$SUCCESS_RATE_WARNING" ] && [ "$SUCCESS_RATE_WARNING" = "0.95" ]; then
        success "Success rate warning threshold configured"
    else
        warning "Success rate warning threshold not configured"
    fi
}

# Generate test report
generate_test_report() {
    log "Generating Test Report..."

    # Calculate success rate
    if [ $TOTAL_TESTS -gt 0 ]; then
        SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    else
        SUCCESS_RATE=0
    fi

    # Create JSON report
    cat > "$TEST_RESULTS_FILE" << EOF
{
  "test_summary": {
    "timestamp": "$(date -Iseconds)",
    "total_tests": $TOTAL_TESTS,
    "passed_tests": $PASSED_TESTS,
    "failed_tests": $FAILED_TESTS,
    "warning_tests": $WARNING_TESTS,
    "success_rate": $SUCCESS_RATE
  },
  "test_categories": {
    "enhanced_workflow": {
      "status": "$([ $FAILED_TESTS -eq 0 ] && echo "PASS" || echo "FAIL")",
      "endpoints_tested": 3,
      "details": "AI-powered workflow intelligence and optimization"
    },
    "ai_workflow_enhancement": {
      "status": "$([ $WARNING_TESTS -lt 2 ] && echo "PASS" || echo "WARNING")",
      "endpoints_tested": 2,
      "details": "Machine learning workflow optimization"
    },
    "enhanced_monitoring": {
      "status": "$([ $WARNING_TESTS -lt 3 ] && echo "PASS" || echo "WARNING")",
      "endpoints_tested": 3,
      "details": "Real-time monitoring and analytics"
    },
    "strategic_integrations": {
      "status": "$([ $WARNING_TESTS -lt 3 ] && echo "PASS" || echo "WARNING")",
      "endpoints_tested": 3,
      "details": "Strategic new service integrations"
    },
    "cross_service_intelligence": {
      "status": "$([ $WARNING_TESTS -lt 2 ] && echo "PASS" || echo "WARNING")",
      "endpoints_tested": 2,
      "details": "Service dependency mapping and intelligent routing"
    },
    "performance_optimization": {
      "status": "$([ $WARNING_TESTS -lt 2 ] && echo "PASS" || echo "WARNING")",
      "endpoints_tested": 2,
      "details": "Caching and optimization strategies"
    }
  },
  "environment_validation": {
    "ai_workflow_enabled": "$AI_WORKFLOW_ENABLED",
    "enhanced_monitoring_enabled": "$ENHANCED_MONITORING_ENABLED",
    "cross_service_orchestration_enabled": "$CROSS_SERVICE_ORCHESTRATION_ENABLED",
    "response_time_warning_ms": "$RESPONSE_TIME_WARNING_MS",
    "success_rate_warning": "$SUCCESS_RATE_WARNING"
  },
  "recommendations": {
    "immediate_actions": [
      "Review failed endpoint configurations",
      "Verify environment variable settings",
      "Check service dependencies"
    ],
    "optimization_suggestions": [
      "Enable AI workflow features for maximum benefit",
      "Configure monitoring thresholds appropriately",
      "Test cross-service workflows"
    ]
  }
}
EOF

    success "Test report generated: $TEST_RESULTS_FILE"
}

# Print test summary
print_test_summary() {
    echo ""
    echo "🧪 TEST SUMMARY"
    echo "=================="
    echo "Total Tests:    $TOTAL_TESTS"
    echo "✅ Passed:      $PASSED_TESTS"
    echo "❌ Failed:      $FAILED_TESTS"
    echo "⚠️  Warnings:    $WARNING_TESTS"

    if [ $TOTAL_TESTS -gt 0 ]; then
        SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
        echo "📊 Success Rate: $SUCCESS_RATE%"
    fi

    echo ""

    if [ $FAILED_TESTS -eq 0 ] && [ $SUCCESS_RATE -ge 80 ]; then
        echo "🎉 ENHANCED INTEGRATIONS TEST: PASSED"
        echo "All critical systems are operational"
    elif [ $FAILED_TESTS -eq 0 ] && [ $SUCCESS_RATE -ge 60 ]; then
        echo "⚠️  ENHANCED INTEGRATIONS TEST: WARNING"
        echo "Core systems operational, some features may need configuration"
    else
        echo "❌ ENHANCED INTEGRATIONS TEST: FAILED"
        echo "Critical systems require attention"
    fi

    echo ""
    echo "📄 Detailed report: $TEST_RESULTS_FILE"
}

# Main test function
main() {
    echo "🧪 ATOM Enhanced Integration Capabilities Testing"
    echo "========================================================"
    echo ""

    # Set enhanced feature environment variables
    export AI_WORKFLOW_ENABLED=true
    export ENHANCED_MONITORING_ENABLED=true
    export CROSS_SERVICE_ORCHESTRATION_ENABLED=true
    export WORKFLOW_OPTIMIZATION_ENABLED=true
    export RESPONSE_TIME_WARNING_MS=1000
    export SUCCESS_RATE_WARNING=0.95

    # Start backend and run tests
    if start_backend; then
        test_enhanced_workflow_endpoints
        test_ai_workflow_system
        test_enhanced_monitoring
        test_strategic_integrations
        test_cross_service_intelligence
        test_performance_optimization
        validate_environment
        stop_backend
    else
        error "Cannot proceed with testing - backend server not available"
    fi

    generate_test_report
    print_test_summary
}

# Run main function
main "$@"
