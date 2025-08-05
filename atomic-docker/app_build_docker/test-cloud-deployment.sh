#!/bin/bash

# Cloud-Hosted Integration Test Script
# Validates Atom application is production-ready for cloud deployments
# Handles both local cloud simulation and actual cloud environments

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_RESULTS_DIR="$SCRIPT_DIR/test-results"
TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
REPORT_FILE="$TEST_RESULTS_DIR/cloud-test-${TIMESTAMP}.json"

mkdir -p "$TEST_RESULTS_DIR"

# Cloud platform detection
detect_platform() {
  case true in
    [[ -n "${FLY_APP_NAME:-}" ]] && echo "fly.io" ;;
    [[ -n "${RAILWAY_PROJECT_ID:-}" ]] && echo "railway" ;;
    [[ -n "${VERCEL_URL:-}" ]] && echo "vercel" ;;
    [[ -n "${RENDER_SERVICE_ID:-}" ]] && echo "render" ;;
    [[ -n "${AWS_LAMBDA_FUNCTION_NAME:-}" ]] && echo "aws-lambda" ;;
    *) echo "local-cloud" ;;
  esac
}

# Enhanced logging
log() {
  echo -e "${BLUE}[CLOUD]${NC} $(date -u '+%Y-%m-%d %H:%M:%S') - $1"
}

success() {
  echo -e "${GREEN}[PASS]${NC} $1"
}

warning() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
  echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Test configuration loading
load_config() {
  local platform=$1

  # Load platform-specific env
  case "$platform" in
    "fly.io")
      export CLOUD_PLATFORM="fly"
      export CLOUD_URL="https://${FLY_APP_NAME}.fly.dev"
      export DATABASE_URL="${DATABASE_URL:-}"
      ;;
    "railway")
      export CLOUD_PLATFORM="railway"
      export CLOUD_URL="${RAILWAY_STATIC_URL}"
      export DATABASE_URL="${DATABASE_URL:-}"
      ;;
    "vercel")
      export CLOUD_PLATFORM="vercel"
      export CLOUD_URL="https://${VERCEL_URL}"
      export DATABASE_URL="${DATABASE_URL:-}"
      ;;
    "local-cloud")
      export CLOUD_PLATFORM="local"
      export CLOUD_URL="${CLOUD_TEST_URL:-http://localhost:3000}"
      export DATABASE_URL="${DATABASE_URL:-postgresql://localhost:5432/atom_test}"
      ;;
  esac

  log "Testing platform: $platform at $CLOUD_URL"
}

# Cloud database testing with proper PostgreSQL ENV handling
test_database_connection() {
  log "Testing cloud PostgreSQL connection..."

  if [[ -z "${DATABASE_URL:-}" ]]; then
    error "DATABASE_URL environment variable not set"
    return 1
  fi

  # Extract PostgreSQL credentials from DATABASE_URL
  local pg_user=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
  local pg_pass=$(echo "$DATABASE_URL" | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
  local pg_host=$(echo "$DATABASE_URL" | sed -n 's/.*@\(.*\):[0-9]\+.*/\1/p')
+  local pg_port=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:]*\):\([0-9]\+\).*/\2/p')
+  local pg_db=$(echo "$DATABASE_URL" | sed -n 's/.*\/\([^?]*\).*/\1/p')
+
+  log "PostgreSQL Config:"
+  log "  Host: $pg_host:$pg_port"
+  log "  Database: $pg_db"
+  log "  User: $pg_user"
+  log "  Password: [HIDDEN]"
+
+  # Create test script
+  cat > "$TEST_RESULTS_DIR/test-pg.js" << EOF
+const { Client } = require('pg');
+
+async function testConnection() {
+  try {
+    const client = new Client({
+      connectionString: process.env.DATABASE_URL,
+      ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
+    });
+
+    await client.connect();
+
+    const result = await client.query(`
+      SELECT
+        current_database() as db_name,
+        current_user as user,
+        version() as version,
+        NOW() as current_time
+    `);
+
+    console.log("✅ TEST PASSED")
+    console.log(`Database: ${result.rows[0].db_name}`);
+    console.log(`User: ${result.rows[0].user}`);
+    console.log(`Time: ${result.rows[0].current_time}`);
+
+    await client.end();
+    process.exit(0);
+  } catch (err) {
+    console.error("✅ TEST FAILED");
+    console.error(err.message);
+    process.exit(1);
+  }
+}
+
+testConnection();
+EOF
+
+  # Test database connection
+  NODE_ENV=production node "$TEST_RESULTS_DIR/test-pg.js" || {
+    error "Database connection failed"
+    return 1
+  }
+
+  success "Database connection successful"
+}

# Enhanced cloud endpoint testing
test_endpoints() {
+  local base_url="${CLOUD_URL:-http://localhost:3000}"
+  log "Testing cloud endpoints at $base_url..."
+
+  # Check if we have curl available
+  if ! command -v curl >/dev/null 2>&1; then
+    error "curl is required for endpoint testing"
+    return 1
+  fi
+
+  local endpoints=("/" "/health" "/api/health" "/api/status")
+  local failed=()
+
+  for endpoint in "${endpoints[@]}"; do
+    local full_url="$base_url$endpoint"
+    local http_code
+
+    # Use curl with retry and timeout
+    for attempt in {1..3}; do
+      http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 --retry 1 "$full_url" 2>/dev/null || echo "000")
+
+      if [[ "$http_code" != "000" ]]; then
+        break
+      fi
+
+      sleep 1
+    done
+
+    local test_result
+    if [[ "$http_code" =~ ^[23][0-9][0-9]$ ]]; then
+      test_result="PASS"
+      success "$endpoint ($http_code)"
+    else
+      test_result="FAIL"
+      failed+=("$endpoint ($http_code)")
+      error "$endpoint ($http_code)"
+    fi
+
+    # Record result
+    echo "{\"endpoint\":\"$endpoint\",\"url\":\"$full_url\",\"status\":\"$test_result\",\"http_code\":\"$http_code\",\"timestamp\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" >> "$TEST_RESULTS_DIR/endpoint-tests.jsonl"
+  done
+
+  [[ ${#failed[@]} -eq 0 ]]
+}

# Cloud build testing
test_build() {
+  log "Testing cloud build..."
+
+  # Clean environment
+  rm -f .env.local
+  rm -rf .next
+
+  # Create build test
+  if npm run build &>/dev/null; then
+    success "Cloud build successful"
+    return 0
+  else
+    error "Cloud build failed - see actual build logs from cloud provider"
+    return 1
+  fi
+}

# Security configuration testing
test_security() {
+  log "Testing cloud security configuration..."
+
+  # Test required environment variables for cloud
+  local required_vars=("DATABASE_URL" "JWT_SECRET" "OPENAI_API_KEY")
+  local missing_vars=()
+
+  for var in "${required_vars[@]}"; do
+    if [[ -z "${!var:-}" ]]; then
+      missing_vars+=("$var")
+    fi
+  done
+
+  if [[ ${#missing_vars[@]} -gt 0 ]]; then
+    error "Missing required cloud secrets: ${missing_vars[*]}"
+    return 1
+  fi
+
+  success "Cloud security configuration valid"
+}
+
# Cloud environment validation
test_cloud_environment() {
+  local platform=$1
+  log "Validating cloud environment for $platform..."
+
+  # Platform-specific checks
+  case "$platform" in
+    "fly.io")
+      [[ -n "${FLY_APP_NAME:-}" ]] || [[ "$CLOUD_MODE" == "local" ]] || {
+        error "Missing FLY_APP_NAME for Fly.io"
+        return 1
+      }
+      ;;
+    "railway")
+      [[ -n "${RAILWAY_STATIC_URL:-}" ]] || [[ -n "${DATABASE_URL:-}" ]] || {
+        error "Missing RAILWAY_STATIC_URL and DATABASE_URL for Railway"
+        return 1
+      }
+      ;;
+    "vercel")
+      [[ -n "${VERCEL_URL:-}" ]] || [[ -n "${DATABASE_URL:-}" ]] || {
+        error "Missing VERCEL_URL and DATABASE_URL for Vercel"
+        return 1
+      }
+      ;;
