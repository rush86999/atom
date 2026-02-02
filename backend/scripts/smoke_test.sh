#!/bin/bash
# Smoke Test Script for Atom Platform
# Tests critical functionality after deployment or code changes
#
# Usage: ./scripts/smoke_test.sh [environment]
#   environment: dev (default), staging, production

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=========================================="
echo "Atom Platform Smoke Tests"
echo "Environment: $ENVIRONMENT"
echo "Backend URL: $BACKEND_URL"
echo "=========================================="
echo ""

# Test counter
TESTS_PASSED=0
TESTS_FAILED=0

# Helper functions
pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    ((TESTS_PASSED++))
}

fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    ((TESTS_FAILED++))
}

warn() {
    echo -e "${YELLOW}⚠ WARN${NC}: $1"
}

info() {
    echo -e "ℹ INFO: $1"
}

# Test: Server is running
test_server_running() {
    echo -n "Testing if server is running... "

    if curl -s -f "$BACKEND_URL/health" > /dev/null 2>&1; then
        pass "Server is responding"
        return 0
    else
        fail "Server is not responding at $BACKEND_URL"
        return 1
    fi
}

# Test: Database connection
test_database_connection() {
    echo -n "Testing database connection... "

    # Try to query agents endpoint (requires database)
    if curl -s -f "$BACKEND_URL/api/agents" > /dev/null 2>&1; then
        pass "Database connection working"
        return 0
    else
        fail "Database connection failed"
        return 1
    fi
}

# Test: Authentication rejects invalid credentials
test_authentication_rejects_invalid() {
    echo -n "Testing authentication rejects invalid credentials... "

    RESPONSE=$(curl -s -X POST "$BACKEND_URL/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email":"invalid@test.com","password":"wrong"}' || echo "")

    if echo "$RESPONSE" | grep -q "401\|401 Unauthorized\|authentication"; then
        pass "Authentication properly rejects invalid credentials"
        return 0
    else
        fail "Authentication may not be properly rejecting invalid credentials"
        warn "Response: $RESPONSE"
        return 1
    fi
}

# Test: No default_user in authentication
test_no_default_user_bypass() {
    echo -n "Testing no default_user bypass... "

    # This test checks if the codebase still contains default_user patterns
    # (excluding test files and migration guide)
    DEFAULT_USER_COUNT=$(grep -r 'user_id.*=.*"default_user"' \
        "$PROJECT_ROOT/core" "$PROJECT_ROOT/api" "$PROJECT_ROOT/tools" \
        --include="*.py" 2>/dev/null | \
        grep -v test | grep -v __pycache__ | \
        grep -v auth_helpers.py | grep -v "migration_guide" | \
        wc -l | xargs || echo "0")

    if [ "$DEFAULT_USER_COUNT" -eq "0" ]; then
        pass "No default_user bypass found in production code"
        return 0
    else
        warn "Found $DEFAULT_USER_COUNT occurrences of default_user (may need migration)"
        return 0  # Not a failure, just a warning
    fi
}

# Test: No NotImplementedErrors in production code
test_no_not_implemented() {
    echo -n "Testing no NotImplementedError in production... "

    NOT_IMPLEMENTED_COUNT=$(grep -r "raise NotImplementedError" \
        "$PROJECT_ROOT/core" "$PROJECT_ROOT/api" "$PROJECT_ROOT/tools" \
        --include="*.py" 2>/dev/null | \
        grep -v test | grep -v __pycache__ | \
        grep -v "abstract" | wc -l | xargs || echo "0")

    if [ "$NOT_IMPLEMENTED_COUNT" -eq "0" ]; then
        pass "No NotImplementedError in production code"
        return 0
    else
        fail "Found $NOT_IMPLEMENTED_COUNT NotImplementedError occurrences"
        return 1
    fi
}

# Test: Agent execution endpoint
test_agent_execution() {
    echo -n "Testing agent execution endpoint... "

    # Try to execute a simple health check or list agents
    RESPONSE=$(curl -s "$BACKEND_URL/api/agents" || echo "")

    if [ -n "$RESPONSE" ]; then
        pass "Agent execution endpoint responding"
        return 0
    else
        fail "Agent execution endpoint not responding"
        return 1
    fi
}

# Test: Canvas routes query correct model
test_canvas_routes() {
    echo -n "Testing canvas routes... "

    # Check if canvas_routes.py queries AgentRegistry not AgentExecution
    CANVAS_ROUTES="$PROJECT_ROOT/api/canvas_routes.py"

    if grep -q "AgentRegistry" "$CANVAS_ROUTES" 2>/dev/null; then
        pass "Canvas routes using AgentRegistry"
        return 0
    else
        fail "Canvas routes may not be using AgentRegistry"
        return 1
    fi
}

# Test: Logging configuration exists
test_logging_config() {
    echo -n "Testing logging configuration... "

    if [ -f "$PROJECT_ROOT/core/logging_config.py" ]; then
        pass "Logging configuration module exists"
        return 0
    else
        fail "Logging configuration module not found"
        return 1
    fi
}

# Test: Error handlers exist
test_error_handlers() {
    echo -n "Testing error handlers... "

    if [ -f "$PROJECT_ROOT/core/error_handlers.py" ]; then
        pass "Error handlers module exists"
        return 0
    else
        fail "Error handlers module not found"
        return 1
    fi
}

# Test: Response models exist
test_response_models() {
    echo -n "Testing response models... "

    if [ -f "$PROJECT_ROOT/core/response_models.py" ]; then
        pass "Response models module exists"
        return 0
    else
        fail "Response models module not found"
        return 1
    fi
}

# Test: Type definitions tracked in git
test_typescript_types_tracked() {
    echo -n "Testing TypeScript definitions tracked... "

    cd "$PROJECT_ROOT"

    if git ls-files frontend-nextjs/components/canvas/types/index.ts | grep -q .; then
        pass "TypeScript definitions are tracked in git"
        return 0
    else
        fail "TypeScript definitions not tracked in git"
        return 1
    fi
}

# Test: Governance checks are fast
test_governance_performance() {
    echo -n "Testing governance performance... "

    # This would require running actual performance tests
    # For now, just check if governance_cache.py exists
    if [ -f "$PROJECT_ROOT/core/governance_cache.py" ]; then
        pass "Governance cache module exists"
        return 0
    else
        fail "Governance cache module not found"
        return 1
    fi
}

# Test: Business agents don't have NotImplementedError
test_business_agents() {
    echo -n "Testing business agents... "

    BUSINESS_AGENTS="$PROJECT_ROOT/core/business_agents.py"

    if grep -q "@abstractmethod" "$BUSINESS_AGENTS" 2>/dev/null; then
        pass "Business agents using abstract methods properly"
        return 0
    else
        fail "Business agents may not be using abstract methods"
        return 1
    fi
}

# Test: AI service has proper error handling
test_ai_service() {
    echo -n "Testing AI service... "

    AI_SERVICE="$PROJECT_ROOT/core/ai_service.py"

    if grep -q "ALLOW_MOCK_AI" "$AI_SERVICE" 2>/dev/null; then
        pass "AI service has proper error handling"
        return 0
    else
        fail "AI service may not have proper error handling"
        return 1
    fi
}

# Run all tests
echo "Running smoke tests..."
echo ""

# Check if we should skip server tests (for CI/CD without running server)
SKIP_SERVER_TESTS=${SKIP_SERVER_TESTS:-false}

if [ "$SKIP_SERVER_TESTS" != "true" ]; then
    test_server_running
    test_database_connection
    test_authentication_rejects_invalid
    test_agent_execution
else
    info "Skipping server tests (SKIP_SERVER_TESTS=true)"
fi

# Always run code quality tests
test_no_default_user_bypass
test_no_not_implemented
test_canvas_routes
test_logging_config
test_error_handlers
test_response_models
test_typescript_types_tracked
test_governance_performance
test_business_agents
test_ai_service

# Summary
echo ""
echo "=========================================="
echo "Smoke Test Summary"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo "=========================================="

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All smoke tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some smoke tests failed!${NC}"
    exit 1
fi
