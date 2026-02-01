#!/bin/bash

# Atom Desktop App E2E Test Runner
# Comprehensive desktop application testing orchestrator
# Usage: ./desktop-test-runner.sh [options]

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Default configuration
HEADLESS=false
PERSONA="all"
REPORT="html"
TIMEOUT=60000

show_help() {
    cat << EOF
Atom Desktop E2E Test Runner

USAGE:
    ./desktop-test-runner.sh [OPTIONS]

OPTIONS:
    --persona=PERSONA    Run tests for specific persona (alex|maria|ben|all)
    --headless          Run tests in headless mode
    --report=TYPE       Report format (html|json|allure)
    --timeout=SECONDS   Test timeout (default: 60s)
    --setup             Install desktop dependencies
    --clean             Clean test artifacts
    --help              Show this help

EXAMPLES:
    ./desktop-test-runner.sh
    ./desktop-test-runner.sh --persona=alex --headless
    ./desktop-test-runner.sh --report=allure --timeout=120
    ./desktop-test-runner.sh --setup --clean
EOF
}

log() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%H:%M:%S')] ERROR: $1${NC}"
}

check_prerequisites() {
    log "🔍 Checking desktop prerequisites..."

    if ! command -v node &> /dev/null; then
        error "Node.js is not installed"
        exit 1
    fi

    if ! command -v npm &> /dev/null; then
        error "npm is not installed"
        exit 1
    fi

    # Check if Playwright is installed
    if ! npx playwright --version &> /dev/null; then
        log "📦 Installing Playwright..."
        npm install -g @playwright/test
    fi

    # Check for desktop app
    if [[ ! -f "atomic-desktop/package.json" ]]; then
        warn "Desktop app not found at atomic-desktop/"
        exit 1
    fi

    log "✅ Prerequisites verified"
}

setup_mocks() {
    log "🔗 Setting up mock services..."

    # Set environment variables for desktop testing
    export NODE_ENV=test
    export ELECTRON_ENABLE_LOGGING=1
    export MOCK_EXTERNAL_SERVICES=true
    export TEST_USER_ID=desktop-test-user
}

run_desktop_tests() {
    local test_pattern=""
    case "$PERSONA" in
        "alex")
            test_pattern="desktop-alex.*test.ts"
            ;;
        "maria")
            test_pattern="desktop-maria.*test.ts"
            ;;
        "ben")
            test_pattern="desktop-ben.*test.ts"
            ;;
        "all")
            test_pattern="desktop-*.test.ts"
            ;;
        *)
            error "Invalid persona: $PERSONA. Use alex|maria|ben|all"
            exit 1
            ;;
+    esac
+
+    log "🎯 Running $PERSONA desktop tests..."
+
+    local reporter_args=""
+    case "$REPORT" in
+        "html")
+            reporter_args="--reporter=html"
+            ;;
+        "json")
+            reporter_args="--reporter=json,./tests/results/desktop-results.json"
+            ;;
+        "allure")
+            reporter_args="--reporter=allure-playwright"
+            ;;
+        *)
+            reporter_args="--reporter=html"
+            ;;
+    esac
+
+    if [[ "$HEADLESS" == true ]]; then
+        export DISPLAY=:99
+    fi
+
+    # Run tests with specific configuration
+    npx playwright test tests/e2e/desktop-app \
+        --project=electron \
+        $reporter_args \
+        --test-timeout=$TIMEOUT \
+        --test-match=$test_pattern \
+        --output-dir=tests/results/desktop
+}
+
+clean_artifacts() {
+    log "🧹 Cleaning test artifacts..."
+    rm -rf tests/results/desktop
+    rm -rf playwright-report
+    rm -rf allure-results
+    log "✅ Cleanup complete"
+}
+
+main() {
+    echo -e "${BLUE}"
+    echo "╔═══════════════════════════════════════════════════════════════╗"
+    echo "║        ATOM DES
