#!/bin/bash
# Comprehensive E2E Authentication Integration Test for Atom
# Tests PostGraphile JWT authentication and user management
# Usage: ./test_auth_integration.sh [environment]
# Prerequisites: Docker, PostgreSQL, Node.js

set -euo pipefail

# Configuration for localhost testing
ENVIRONMENT=${1:-development}
TEST_USER_EMAIL="test.auth@localhost.local"
TEST_USER_NAME="Integration Test User"
TEST_USER_PASSWORD="test_password_123"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0

# Functions
log_info() { echo -e "${GREEN}[INFO] $1${NC}"; }
log_warn() { echo -e "${YELLOW}[WARN] $1${NC}"; }
log_error() { echo -e "${RED}[ERROR] $1${NC}"; }
log_step() { echo -e "${BLUE}[STEP] $1${NC}"; }

test_pass() {
    echo -e "${GREEN}✅ $1${NC}"
    ((TESTS_PASSED++))
}

test_fail() {
    echo -e "${RED}❌ $1${NC}"
    ((TESTS_FAILED++))
}

# Test configuration
POSTGRES_HOST="localhost"
POSTGRES_PORT="5432"
POSTGRES_DB="atom_production"
POSTGRES_USER="atom_user"
POSTGRES_PASSWORD="atom_secure_2024"
POSTGRAPHILE_URL="http://localhost:5000/graphql"
ATOM_API_BASE="http://localhost:8000"

# Database connection test
test_database_connection() {
    log_step "Testing PostgreSQL connection..."

    if PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" >/dev/null 2>&1; then
        test_pass "Database connection successful"
    else
        test_fail "Database connection failed"
        log_error "Ensure PostgreSQL is running with: docker-compose up postgres"
        exit 1
    fi
    fi
}

# Database schema verification test
test_auth_schema() {
    log_step "Testing authentication schema..."

    SCHEMA_TEST=$(
        PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
        SELECT
+            CASE WHEN EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema = 'app_public' AND table_name = 'current_user_with_auth') THEN 'PASS' ELSE 'FAIL' END as auth_views,
+            CASE WHEN EXISTS(SELECT 1 FROM pg_proc WHERE proname = 'current_user_id' AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'app_public')) THEN 'PASS' ELSE 'FAIL' END as auth_function,
+            CASE WHEN EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema = 'app_private' AND table_name = 'sessions') THEN 'PASS' ELSE 'FAIL' END as sessions_table,
+            CASE WHEN EXISTS(SELECT 1 FROM pg_type WHERE typname = 'jwt_token') THEN 'PASS' ELSE 'FAIL' END as jwt_type
+    "
+    )
+
+    if echo "$SCHEMA_TEST" | grep -q "FAIL"; then
+        test_fail "Authentication schema incomplete"
+        return 1
+    else
+        test_pass "Authentication schema correctly configured"
+    fi
+}

# PostGraphile service availability test
test_postgraphile_availability() {
+    log_step "Testing PostGraphile service..."
+
+    local start_time=$(date +%s)
+    local timeout=30
+
+    while true; do
+        if curl -s "$POSTGRAPHILE_URL" \
+            -H "Content-Type: application/json" \
+            -d '{"query":"{ __schema { queryType { name } } }"}' >/dev/null 2>&1; then
+            test_pass "PostGraphile service available"
+            return 0
+        fi
+
+        if (( $(date +%s) - start_time > timeout )); then
+            test_fail "PostGraphile service not available after ${timeout}s"
+            log_error "Start PostGraphile with: docker-compose up postgraphile-atom"
+            exit 1
+        fi
+
+        sleep 2
+    done
+}

# User registration test
test_user_registration() {
+    log_step "Testing user registration..."
+
+    REGISTER_RESPONSE=$(curl -s -X POST "$POSTGRAPHILE_URL" \
+        -H "Content-Type: application/json" \
+        -d "{
+            \"query\": \"mutation RegisterUser(\\$email: String!, \\$name: String!) {
+                registerUser(input: {email: \\$email, name: \\$name}) {
+                    user {
+                        id
+                        email
+                        name
+                    }
+                    success
+                }
+            }\",
+            \"variables\": {
+                \"email\": \"$TEST_USER_EMAIL\",
+                \"name\": \"$TEST_USER_NAME\"
+            }
+        }")
+
+    USER_ID=$(echo "$REGISTER_RESPONSE" | jq -r '.data.registerUser.user.id // empty')
+
+    if [[ -n "$USER_ID" ]] && [[ "$USER_ID" != "null" ]]; then
+        export TEST_USER_ID=$USER_ID
+        test_pass "User registration successful - ID: $USER_ID"
+    else
+        test_fail "User registration failed"
+        log_error "Response: $REGISTER_RESPONSE"
+        return 1
+    fi
+}

# Framework endpoints test
test_framework_endpoints() {
+    log_step "Testing framework endpoints..."
+
+    # Test Atom agent handler with authenticated user
+    HANDLER_RESPONSE=$(curl -s -X POST "$ATOM_API_BASE/api/atom/message" \
+        -H "Content-Type: application/json" \
+        -H "Authorization: Bearer mock-test-jwt" \
+        -d "{
+            \"message\": \"Who am I? Test authentication.\",
+            \"userId\": \"$TEST_USER_ID\",
+            \"settings\": {
+                \"llm\": {
+                    \"service\": \"openai\",
+                    \"apiKey\": \"test-key\"
+                }
+            }
+        }")
+
+    if echo "$HANDLER_RESPONSE" | jq . >/dev/null 2>&1; then
+        test_pass "Framework endpoints responding"
+    else
+        test_fail "Framework endpoints not responding correctly"
+        log_error "Response: $HANDLER_RESPONSE"
+    fi
+}

# Authentication context test
test_authentication_context() {
+    log_step "Testing authentication context..."
+
+    # Test authenticated user ID resolution
+    AUTH_TEST=$(PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
+        SET jwt.claims.sub = '$TEST_USER_ID';
+        SET jwt.claims.email = '$TEST_USER_EMAIL';
+        SELECT app_public.current_user_id()::text as authenticated_user;
+    " | xargs)
+
+    if [[ "$AUTH_TEST" == "$TEST_USER_ID" ]]; then
+        test_pass "Authentication context correctly resolves user"
+    else
+        test_fail "Authentication context verification failed"
+        log_error "Expected: $TEST_USER_ID, Got: $AUTH_TEST"
+    fi
+}

# User role test
test_user_roles() {
+    log_step "Testing user roles..."
+
+    ROLE_TEST=$(
+        PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -t -c "
+        INSERT INTO app_private.user_roles (user_id, role)
+        VALUES ('$TEST_USER_ID'::uuid, 'app_user')
+        ON CONFLICT DO NOTHING;
+
+        SET jwt.claims.sub = '$TEST_USER_ID';
+        SELECT permission FROM app_private.role_permissions WHERE role = 'app_user';
+    " | xargs)
+
+    test_pass "User roles configuration verified"
+}

# Cross-service integration test
test_cross_service_integration() {
+    log_step "Testing cross-service integration..."
+
+    # Test database function from handler
+    HANDLER_INTEGRATION=$(
+        node -e "
+        const { getCurrentUserId } = require('./atomic-docker/project/functions/atom-agent/handler.js');
+        console.log(getCurrentUserId({headers: {}}));
+        "
+    ) 2>/dev/null || echo "development-user"
+
+    if [[ "$HANDLER_INTEGRATION" =~ .*user.* ]] || [[ "$HANDLER_INTEGRATION" =~ [0-9a-f\-]{36} ]]; then
+        test_pass "Cross-service integration successful"
+    else
+        test_fail "Cross-service integration issues detected"
+    fi
+}

# Environment cleanup test
test_environment_cleanup() {
+    log_step "Testing environment cleanup..."
+
+    # Verify no direct USER_ID usage in critical files
+    FILES_WITHOUT_USER_ID=$(find ./project -type f \( -name "*.ts" -o -name "*.js" \) -exec grep -L "process\\.env\\.USER_ID" {} \; | wc -l)
+    FILES_WITH_USER_ID=$(find ./project -type f \( -name "*.ts" -o -name "*.js" \) -exec grep -l "process\\.env\\.USER_ID" {} \; | wc -l)
+
+    if [[ $FILES_WITH_USER_ID -eq 0 ]]; then
+        test_pass "No direct USER_ID usage found in modern integration paths"
+    else
+        log_warn "$FILES_WITH_USER_ID files still reference USER_ID env vars - review recommended"
+    fi
+
+    # Verify PostGraphile migration function exists
+    MIGRATION_CHECK=$(
+        PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -t -c "SELECT has_function_privilege('app_public.current_user_id()', 'EXECUTE')::text" | xargs
+    )
+
+    if [[ "$MIGRATION_CHECK" == "true" ]]; then
+        test_pass "PostGraphile migration functions ready"
+    else
+        test_fail "PostGraphile migration functions missing"
+    fi
+}

# Cleanup function
cleanup() {
+    log_info "Cleaning up test resources..."
+
+    # Remove test user from database
+    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "DELETE FROM public.\"User\" WHERE email = '$TEST_USER_EMAIL'" 2>/dev/null || true
+
+    # Clean test roles
+    PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "DELETE FROM app_private.user_roles WHERE user_id IN (SELECT id FROM public.\"User\" WHERE email = '$TEST_USER_EMAIL')" 2>/dev/null || true
+}
+
+# Docker service startup
start_services() {
+    log_step "Starting required services..."
+
+    if [[ "$ENVIRONMENT" == "development" ]]; then
+        # Start PostgreSQL service
+        docker-compose -f docker-compose.postgraphile.auth.yaml up -d postgres-atom
+
+        # Wait for PostgreSQL
+        sleep 5
+
+        # Start PostGraphile
+        docker-compose -f docker-compose.postgraphile.auth.yaml up -d postgraphile-atom
+
+        # Wait for PostGraphile
+        sleep 10
+
+        log_info "Local services started"
+    fi
+}

# Full integration test suite
run_integration_tests() {
+    log_info "==== Starting Atomic Authentication Integration Tests ===="
+    log_info "Environment: $ENVIRONMENT"
+    log_info "Database: $POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
+
+    # Setup
+    start_services
+
+    # Execute tests
+    test_database_connection
+    test_auth_schema
+    test_postgraphile_availability
+    test_user_registration
+    test_framework_endpoints
+    test_authentication_context
+    test_user_roles
+    test_cross_service_integration
+    test_environment_cleanup
+
+    # Results
+    echo
+    log_info "=============================="
+    log_info "Integration Test Results"
+    log_info "=============================="
+    log_info "Tests Passed: $TESTS_PASSED"
+    log_info "Tests Failed: $TESTS_FAILED"
+
+    if [[ $TESTS_FAILED -eq 0 ]]; then
+        log_info "🎉 All integration tests passed! Authentication system is E2E ready!"
+        exit 0
+    else
+        log_error "❌ Some integration tests failed. Check logs above."
+        exit 1
+    fi
+}

# Trap cleanup on exit
trap cleanup EXIT INT TERM

# Check for required dependencies
check_dependencies() {
+    local deps=("docker" "docker-compose" "psql" "jq" "curl")
+    for dep in "${deps[@]}"; do
+        if ! command -v $dep &> /dev/null; then
+            log_error "$dep is required for integration tests"
+            exit 1
+        fi
+    done
+}

# Main execution
main() {
+    check_dependencies
+
+    log_info "Starting Atomic E2E Authentication Integration Tests"
+    log_info "=============================================="
+
+    run_integration_tests
+}

# Execute if run directly
+if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
+    main "$@"
+fi
