#!/bin/bash

# Atom Full E2E Test Suite
# Comprehensive user journey testing across all personas and integrations
# Usage: ./run-e2e-tests.sh [options]

set -e  # Exit on any error

# Default configuration
PERSONA="all"
ALLURE=false
HEADLESS=false
DEBUG=false
DOCKER=false
SETUP_ONLY=false
CLEANUP=false

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ERROR: $1${NC}"
}

header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}\n"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --persona=*)
            PERSONA="${1#*=}"
            shift
            ;;
        --persona)
            PERSONA="$2"
            shift 2
            ;;
        --allure)
            ALLURE=true
            shift
            ;;
        --headless)
            HEADLESS=true
            shift
            ;;
        --debug)
            DEBUG=true
            shift
            ;;
        --docker)
            DOCKER=true
            shift
            ;;
        --setup-only)
            SETUP_ONLY=true
            shift
            ;;
        --cleanup)
            CLEANUP=true
            shift
            ;;
        --help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --persona=<name>   Run tests for specific persona (alex|maria|ben|all)"
            echo "  --allure           Generate Allure test reports"
            echo "  --headless         Run tests in headless mode"
            echo "  --debug            Enable debug logging"
            echo "  --docker           Use Docker setup for testing"
            echo "  --setup-only       Only setup environment, don't run tests"
            echo "  --cleanup          Cleanup test environment"
            echo "  --help             Show this help"
            exit 0
            ;;
        *)
            echo "Error: Unknown option $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check prerequisites
check_prerequisites() {
    log "🔍 Checking prerequisites..."

    if ! command -v node &> /dev/null; then
        error "Node.js is not installed"
        exit 1
    fi

    if ! command -v npm &> /dev/null; then
        error "npm is not installed"
        exit 1
    fi

    if ! command -v docker &> /dev/null; then
        warn "Docker is not installed - some tests may be skipped"
    fi

    # Check if required environment variables are set
    if [[ -z "$PLAID_CLIENT_ID" || -z "$PLAID_SECRET" ]]; then
        warn "PLAID_CLIENT_ID and PLAID_SECRET not set - Finance tests may be skipped"
    fi

    if [[ -z "$NOTION_API_KEY" ]]; then
        warn "NOTION_API_KEY not set - Notion integration tests may be skipped"
    fi

    if [[ -z "$GOOGLE_OAUTH_CLIENT_ID" ]]; then
        warn "Google OAuth credentials not set - Calendar tests may be skipped"
    fi
}

# Setup test environment
setup_test_environment() {
    header "Setting up E2E Test Environment"

    log "📦 Installing test dependencies..."
    npm install --quiet

    log "🎭 Setting up Playwright browsers..."
    npx playwright install chromium --with-deps

    if [[ "$DOCKER" == true ]]; then
        log "🐳 Starting Docker environment..."
        docker-compose -f docker-compose.postgraphile.auth.yaml down --volumes 2>/dev/null || true
        docker-compose -f docker-compose.postgraphile.auth.yaml up -d
        log "⏳ Waiting for services to start..."
        sleep 30
    fi

    log "📊 Setting up test databases..."
    node tests/setup/setup-test-db.js 2>/dev/null || log "⚠️  Test DB setup script not found, continuing..."

    log "🎯 Test environment ready!"
}

# Run the actual tests
run_tests() {
    header "Running E2E Tests - Persona: $PERSONA"

    # Environment variables for test runs
    export NODE_ENV="test"
    export TEST_PERSONA="$PERSONA"
    export CI="${CI:-false}"

    if [[ "$HEADLESS" == true ]]; then
        export HEADLESS="true"
    fi

    if [[ "$DEBUG" == true ]]; then
        export DEBUG="e2e:*"
    fi

    local test_pattern=""
    case "$PERSONA" in
        "alex")
            test_pattern=".*\\.alex\\..*\\.test\\.ts$"
            ;;
        "maria")
            test_pattern=".*\\.maria\\..*\\.test\\.ts$"
            ;;
        "ben")
            test_pattern=".*\\.ben\\..*\\.test\\.ts$"
            ;;
        "all")
            test_pattern=".*\\.test\\.ts$"
            ;;
        *)
            error "Invalid persona: $PERSONA. Use alex|maria|ben|all"
            exit 1
            ;;
    esac

    log "🎭 Running ${PERSONA} persona tests..."

    local jest_args="--testTimeout=60000 --detectOpenHandles"

    if [[ "$ALLURE" == true ]]; then
        jest_args="$jest_args --reporters=default --reporters=jest-allure"
        log "📊 Generating Allure reports..."
    fi

    # Run tests with filtering
    log "🔍 Running tests matching pattern: $test_pattern"

    if npx jest --config jest.config.js \
                $jest_args \
                --testRegex="tests/e2e/.*\\.test\\.ts" \
                --testNamePattern="$test_pattern"; then
        log "🎉 All tests passed!"
        local exit_code=0
    else
        local exit_code=$?
        error "Some tests failed (exit code: $exit_code)"
    fi

    if [[ "$ALLURE" == true ]]; then
        log "📊 Generating Allure report..."
        npx allure generate tests/results/allure-results --clean -o tests/results/allure-report
        log "📊 View Allure report: npx allure serve tests/results/allure-report"
    fi

    return $exit_code
}

# Cleanup environment
cleanup_environment() {
    header "Cleaning up E2E Test Environment"

    if [[ "$DOCKER" == true ]]; then
        log "🐳 Stopping Docker environment..."
        docker-compose -f docker-compose.postgraphile.auth.yaml down --volumes 2>/dev/null || true
    fi

    log "📊 Cleaning up test data..."
    node tests/setup/cleanup-test-db.js 2>/dev/null || log "⚠️  Test DB cleanup script not found, continuing..."

    log "✅ Environment cleaned"
}

# Main execution flow
main() {
    header "Atom E2E Test Suite"

    if [[ "$CLEANUP" == true ]]; then
        cleanup_environment
        exit 0
    fi

    check_prerequisites
    setup_test_environment

    if [[ "$SETUP_ONLY" == true ]]; then
        log "✅ Setup complete. Exiting..."
        exit 0
    fi

    local start_time=$(date +%s)
    run_tests
    local exit_code=$?
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log "⏱️  Total test execution time: ${duration}s"

    if [[ "$ALLURE" == true ]]; then
        log "📊 View Allure report: npx allure serve tests/results/allure-results"
    fi

    exit $exit_code
}

# Make script executable and run
main "$@"
