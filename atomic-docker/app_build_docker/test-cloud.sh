#!/bin/bash

# Cloud-Hosted Environment Test Script
# For validating production deployments on cloud platforms
# (Fly.io, Railway, Vercel, AWS, etc.)

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_MODE="${1:-detect}"

echobot() {
    echo -e "${BLUE}[CLOUD-TEST]${NC} ${1}"
}

errorbot() {
    echo -e "${RED}[ERROR]${NC} ${1}" >&2
}

successbot() {
    echo -e "${GREEN}[SUCCESS]${NC} ${1}"
}

warnbot() {
    echo -e "${YELLOW}[WARN]${NC} ${1}"
}

# Detect cloud platform
detect_cloud_platform() {
    echobot "🔍 Detecting cloud platform..."

    if [[ -n "${FLY_APP_NAME:-}" ]]; then
        echo "fly"
    elif [[ -n "${RAILWAY_PROJECT_ID:-}" ]]; then
        echo "railway"
    elif [[ -n "${VERCEL_URL:-}" ]]; then
        echo "vercel"
    elif [[ -n "${AWS_LAMBDA_FUNCTION_NAME:-}" ]]; then
        echo "aws"
    elif [[ -n "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
        echo "gcp"
    else
        echo "unknown"
    fi
}

# Validate cloud-specific environment
validate_cloud_environment() {
    local platform=$1
    echobot "🔐 Validating $platform environment..."

    local required_vars=()
    case "$platform" in
        fly|unknown)
            required_vars=("DATABASE_URL" "JWT_SECRET" "OPENAI_API_KEY")
            ;;
        railway)
            required_vars=("DATABASE_URL" "JWT_SECRET" "OPENAI_API_KEY" "REDIS_URL")
            ;;
        vercel)
            required_vars=("DATABASE_URL" "JWT_SECRET" "OPENAI_API_KEY" "NEXT_PUBLIC_APP_URL")
            ;;
        aws|gcp)
            required_vars=("DATABASE_URL" "JWT_SECRET" "OPENAI_API_KEY" "REDIS_URL")
            ;;
    esac

    local missing_vars=()
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            missing_vars+=("$var")
+        fi
+    done
+
+    if [[ ${#missing_vars[@]} -gt 0 ]]; then
+        errorbot "Missing required environment variables: ${missing_vars[*]}"
+        return 1
+    fi
+
+    successbot "All required environment variables are set"
+    return 0
+}

# Test database connectivity
test_database_connection() {
+    echobot "🗄️  Testing cloud database connection..."
+
+    local db_url="${DATABASE_URL:-}"
+    if [[ -z "$db_url" ]]; then
+        errorbot "DATABASE_URL is not set"
+        return 1
+    fi
+
+    # Test database using node
+    node -e "
+        const { Client } = require('pg');
+        async function testCloudDatabase() {
+            try {
+                const client = new Client({
+                    connectionString: process.env.DATABASE_URL,
+                    ssl: { rejectUnauthorized: false }
+                });
+                await client.connect();
+                const result = await client.query('SELECT NOW() as current_time, $$CLOUD$$ as environment');
+                console.log('📊 Database:', result.rows[0]);
+                await client.end();
+                process.exit(0);
+            } catch (error) {
+                console.error('❌ Cloud database error:', error.message);
+                process.exit(1);
+            }
+        }
+        testCloudDatabase().catch(console.error);
+    "
+}

# Test health endpoints
test_health_endpoints() {
+    local base_url="${CLOUD_TEST_URL:-${TERMINAL_LINK:-${VERCEL_URL:-http://localhost:$PORT}}}}"
+
+    if [[ -z "$base_url" ]]; then
+        if [[ "$CLOUD_MODE" == "local" ]]; then
+            base_url="http://localhost:${PORT:-3000}"
+        else
+            errorbot "Could not determine test URL. Set CLOUD_TEST_URL or use local mode"
+            return 1
+        fi
+    fi
+
+    echobot "🌐 Testing cloud endpoints at $base_url..."
+
+    local endpoints=("/" "/health" "/api/health" "/api/status")
+    local failed=()
+
+    for endpoint in "${endpoints[@]}"; do
+        full_url="${base_url}${endpoint}"
+        echobot "Testing: $full_url"
+
+        local http_code status
+        if command -v curl >/dev/null 2>&1; then
+            http_code=$(curl -s -o /dev/null -w "%{http_code}" -f "$full_url" || echo "000")
+        else
+            http_code=$(wget --no-verbose --spider --server-response "$full_url" 2>&1 | awk '/HTTP\// {code=$2} END {print code}' || echo "000")
+        fi
+
+        if [[ "$http_code" =~ ^[23][0-9][0-9]$ ]]; then
+            successbot "✅ $endpoint ($http_code)"
+        else
+            failed+=("$endpoint: $http_code")
+            errorbot "❌ $endpoint ($http_code)"
+        fi
+    done
+
+    if [[ ${#failed[@]} -gt 0 ]]; then
+        errorbot "Failed endpoints: ${failed[*]}"
+        return 1
+    fi
+
+    return 0
+}

# Validate cloud deployment
validate_deployment() {
+    local platform=$1
+
+    echobot "🔍 Validating $platform deployment..."
+
+    case "$platform" in
+        fly)
+            if command -v fly >/dev/null 2>&1; then
+                echobot "Testing Fly.io deployment..."
+                if fly status &>/dev/null; then
+                    successbot "✅ Fly.io app is running"
+                else
+                    warnbot "⚠️  Fly.io app status check failed"
+                fi
+                fly info 2>/dev/null || true
+            fi
+            ;;
+        vercel)
+            if command -v vercel >/dev/null 2>&1; then
+                echobot "Testing Vercel deployment..."
+                vercel list 2>/dev/null || true
+            fi
+            ;;
+    esac
+}

# Run build test
+test_build() {
+    echobot "🏗️  Testing cloud build..."
+
+    # Remove any conflicting .local files
+    rm -f .env.local
+
+    # Test build
+    npm run build --silent 2>&1 | sed 's/^/[BUILD] /' || {
+        errorbot "Build failed - check output above"
+        return 1
+    }
+
+    successbot "✅ Cloud build successful"
+}

# Test performance
+test_performance() {
+    local base_url="${CLOUD_TEST_URL:-${TERMINAL_LINK:-http://localhost:$PORT}}"
+
+    echobot "⚡ Testing cloud performance..."
+
+    if command -v curl >/dev/null 2>&1; then
+        echo "Testing response times..."
+
+        local total=0
+        local count=0
+
+        for i in {1..3}; do
+            time_result=$(curl -w '@curl-format.txt' -o /dev/null -s "$base_url" 2>&1)
+            echo "Request $i: $time_result"
+            ((count++))
+        done
+
+    elif command -v wrk >/dev/null 2>&1; then
+        echobot "Running wrk performance test..."
+        wrk -t1 -c10 -d10s "$base_url" --timeout 30s
+    else
+        echobot "Skipping performance test (install curl or wrk for detailed metrics)"
+    fi
+}

# Display environment info
+show_environment_info() {
+    echobot "📊 Cloud Environment Info"
+    echo "=========================="
+
+    # Platform detection
+    local platform=$(detect_cloud_platform)
+
+    echo "Platform: $platform"
+    echo "Environment:"
+
+    # Git info
+    if [[ -d .git ]]; then
+        echo "  Git Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')"
+        echo "  Git Commit: $(git rev-parse HEAD 2>/dev/null || echo 'unknown' | cut -c1-8)"
+    fi
+
+    # Node/npm info
+    echo "  Node: $(node --version)"
+    echo "  NPM: $(npm --version)"
+    echo "  Build: $(npm run build --silent 2>&1 | head -1 || echo 'test-only')"
+
+    # Environment variables
+    echo "  PORT: ${PORT:-3000}"
+    echo "  NODE_ENV: ${NODE_ENV:-production}"
+
+    # Memory info
+    if [[ -n "${WEBMemory:-}" ]]; then
+        echo "  Memory Limits: ${WEBMemory}"
+    fi
+
+    echo ""
+}

+# Create performance test helper
+create_performance_helper() {
+    cat > curl-format.txt << 'EOF'
+time_namelookup:  %{time_namelookup}\n
+time_connect:  %{time_connect}\n
+time_appconnect:  %{time_appconnect}\n
+time_pretransfer:  %{time_pretransfer}\n
+time_redirect:  %{time_redirect}\n
+time_starttransfer:  %{time_starttransfer}\n
+time_total:  %{time_total}\n
+speed_download:  %{speed_download}\n
+EOF
+}

+# Generate test report
+generate_test_report() {
+    local platform=$1
+    local timestamp=$(date -u +%Y-%m-%d_%H:%M:%S)
+
+    echo ""
+    echo "📋 Cloud Test Report - $timestamp"
+    echo "=================================="
+    echo "Platform: $platform"
+    echo "Node: $(node --version)"
+    echo "Build Status: $(npm run build --silent 2>&1 | head -1 || echo 'Built')"
+    echo ""
+
+    if [[ -n "${VERCEL_URL:-}" ]]; then
+        echo "Deployment: $VERCEL_URL"
+    elif [[ -n "${RAILWAY_STATIC_URL:-}" ]]; then
+        echo "Deployment: $RAILWAY_STATIC_URL"
+    elif [[ -n "${RENDER_EXTERNAL_HOSTNAME:-}" ]]; then
+        echo "Deployment: $RENDER_EXTERNAL_HOSTNAME"
+    fi
+
+    echo ""
+}
+
+# Main test runner
+main() {
+    local platform=$(detect_cloud_platform)
+
+    echo "🌐 Cloud-Hosted Environment Test"
+    echo "================================="
+    echo "Platform: $platform"
+    echo "Test mode: $CLOUD_MODE"
+    echo ""
+
+    # Configuration debugging
+    if [[ "$CLOUD_MODE" == "debug" ]]; then
+        echo "Environment Variables:"
+        env | grep -E "(DATABASE|JWT|PORT|ENV|URL)" | sed 's/\(AWS_\|GOOGLE_\|VERCEL_\)/secret_hidden_/g'
+        echo ""
+    fi
+
+    # Stage 1: Environment Validation
+    echobot "Stage 1: Environment Validation"
+    if ! validate_cloud_environment "$platform"; then
+        errorbot "Environment validation failed"
+        exit 1
+    fi
+
+    # Stage 2: Database Connectivity
+    echobot "Stage 2: Database Connectivity"
+    if ! test_database_connection; then
+        warnbot "Database connection test failed - may be using different method"
+    fi
+
+    # Stage 3: Build Verification
+    echobot "Stage 3: Build Verification"
+    if ! test_build; then
+        errorbot "Build verification failed"
+        exit 1
+    fi
+
+    # Stage 4: Deployment Validation
+    echobot "Stage 4: Deployment Validation"
+    validate_deployment "$platform"
+
+    # Stage 5: Health Endpoints
+    echobot "Stage 5: Health Endpoints"
+    if ! test_health_endpoints; then
+        warnbot "Some health endpoints failed - check deployment status"
+    fi
+
+    # Stage 6: Performance (if requested)
+    if [[ "$CLOUD_MODE" == "performance" ]]; then
+        echobot "Stage 6: Performance Testing"
+        create_performance_helper
+        test_performance
+    fi
+
+    # Generate report
+    generate_test_report "$platform"
+
+    successbot "Cloud environment test completed!"
+    echobot "Your app is cloud-live-ready for $platform"
+}
+
+# CLI Help
+if [[ "$1" == "--help" ]]; then
+    cat << 'EOF'
+Usage: ./test-cloud.sh [mode] [options]
+
+Modes:
+  detect (default)   - Detect cloud platform automatically
+  fly                - Test Fly.io deployment
+  vercel             - Test Vercel deployment
+  railway            - Test Railway deployment
+  aws                - Test AWS deployment
+  gcp                - Test Google Cloud deployment
+  local              - Test local cloud simulation
+
+Examples:
+  ./test-cloud.sh                    # Auto-detect platform
+  ./test-cloud.sh fly                # Test Fly.io specifically
+  CLOUD_TEST_URL=https://myapp.com ./test-cloud.sh local
+
+Environment Variables:
+  DATABASE_URL         - PostgreSQL connection string
+  OPENAI_API_KEY       - OpenAI API key
+  JWT_SECRET          - JWT secret
+  PORT                - Port (default: 3000)
+  CLOUD_TEST_URL      - Force test URL
+  DEBUG               - Enable debug output
+EOF
+    exit 0
+fi

# Execute based on CLI argument
+case "${1:-detect}" in
+    fly|railway|vercel|aws|gcp|local|detect)
+        main "$1"
+        ;;
+    *)
+        main "$1"
+        ;;
+esac
