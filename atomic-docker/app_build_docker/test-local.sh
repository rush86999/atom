#!/bin/bash

# Local Development Environment Test Script
# For running E2E tests in local development environment

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_COMPOSE_FILE="$SCRIPT_DIR/docker-compose.local.yml"
ENV_FILE="$SCRIPT_DIR/.env.local"

echo "🔧 Atom Local Development Test Suite"
echo "===================================="

# Function to check if Docker is running
check_docker() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        echo "${GREEN}✅ Docker is available${NC}"
        return 0
    else
        echo "${RED}❌ Docker is not running${NC}"
        return 1
    fi
}

# Function to setup local PostgreSQL with Docker
setup_local_postgres() {
    echo "🔄 Setting up local PostgreSQL..."

    if ! check_docker; then
        echo "${YELLOW}⚠️  Using local PostgreSQL installation instead${NC}"
        return 1
    fi

    if [[ ! -f "$DOCKER_COMPOSE_FILE" ]]; then
        cat > "$DOCKER_COMPOSE_FILE" << 'EOF'
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: atom_local
      POSTGRES_USER: local_user
      POSTGRES_PASSWORD: local_dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_local_data:/var/lib/postgresql/data
      - ./init-test-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U local_user -d atom_local"]
      interval: 5s
      timeout: 5s
      retries: 5
    profiles:
      - local

volumes:
  postgres_local_data:

networks:
  default:
    driver: bridge
EOF
    fi

    echo "${GREEN}✅ Local PostgreSQL configured${NC}"
    return 0
}

# Function to create local environment file
setup_local_env() {
    echo "🌍 Setting up local environment configuration..."

    if [[ ! -f "$ENV_FILE" ]]; then
        cat > "$ENV_FILE" << 'EOF'
# Local Development Environment Variables
NODE_ENV=development
PORT=3000

# Local PostgreSQL (Managed by Docker)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=atom_local
POSTGRES_USER=local_user
POSTGRES_PASSWORD=local_dev_password

# Local Database URL
DATABASE_URL=postgresql://local_user:local_dev_password@localhost:5432/atom_local

# Development Defaults
OPENAI_API_KEY=sk-dev-or-mock-key
JWT_SECRET=local-dev-secret-key-for-testing-32-chars

# Local Development
RESTRICT_CORS=false
ENABLE_DEBUG=true
LOG_LEVEL=debug
EOF
        echo "${GREEN}✅ Created .env.local with defaults${NC}"
    else
        echo "${GREEN}✅ Found existing .env.local${NC}"
    fi
}

# Function to check if local PostgreSQL is running
check_local_postgres() {
    echo "🔍 Checking local PostgreSQL..."

    if docker compose -f "$DOCKER_COMPOSE_FILE" ps postgres --services 2>/dev/null | grep -q postgres; then
        echo "${GREEN}✅ Local PostgreSQL running via Docker${NC}"
        return 0
    fi

    # Check if PostgreSQL is running locally
    if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        echo "${GREEN}✅ Local PostgreSQL running directly${NC}"
        return 0
    fi

    echo "${RED}❌ PostgreSQL is not running locally${NC}"
    return 1
}

# Function to start local services
start_local_services() {
    echo "🚀 Starting local development environment..."

    if setup_local_postgres; then
        echo "🔄 Starting local PostgreSQL via Docker..."
        docker compose -f "$DOCKER_COMPOSE_FILE" --profile local up -d postgres

        # Wait for PostgreSQL to be ready
        echo "⏳ Waiting for PostgreSQL to be ready..."
        timeout=30
        while [[ $timeout -gt 0 ]]; do
            if check_local_postgres; then
                echo "${GREEN}✅ PostgreSQL is ready${NC}"
                break
            fi
            sleep 2
            ((timeout--))
        done

        if [[ $timeout -eq 0 ]]; then
            echo "${RED}❌ PostgreSQL failed to start${NC}"
            return 1
        fi
    else
        echo "${YELLOW}⚠️  Please ensure PostgreSQL is running locally on port 5432${NC}"
+    fi

    return 0
}

# Function to stop local services
stop_local_services() {
    echo "🛑 Stopping local services..."

    if [[ -f "$DOCKER_COMPOSE_FILE" ]]; then
        docker compose -f "$DOCKER_COMPOSE_FILE" --profile local down -v
        echo "${GREEN}✅ Local services stopped${NC}"
    fi
}

# Function to run local tests
run_local_tests() {
    echo "🧪 Running local E2E tests..."

    # Install dependencies
    echo "📦 Installing test dependencies..."
+    npm install --save-dev pg supertest axios
+
    # Set environment
+    export NODE_ENV=development
+
    # Start server and run tests
+    echo "🖥️  Starting development server..."
+    npm run dev &
+    SERVER_PID=$!
+
+    # Wait for server
+    echo "⏳ Waiting for server to start..."
+    timeout=30
+    while [[ $timeout -gt 0 ]]; do
+        if curl -fs http://localhost:3000 >/dev/null 2>&1; then
+            echo "${GREEN}✅ Server is running${NC}"
+            break
+        fi
+        sleep 2
+        ((timeout--))
+    done

    if [[ $timeout -eq 0 ]]; then
+        echo "${RED}❌ Server failed to start${NC}"
+        kill $SERVER_PID 2>/dev/null || true
+        return 1
+    fi

    # Run tests
+    echo "🔍 Running local E2E validation..."
+    npm test __tests__/e2e/live-ready.test.ts || {
+        echo "${YELLOW}⚠️  Some tests failed - see output above${NC}"
+        return_code=1
+    }
+
    # Cleanup
+    kill $SERVER_PID 2>/dev/null || true
+    wait $SERVER_PID 2>/dev/null || true
+
    return ${return_code:-0}
+}

# Main execution
main() {
+    case "${1:-test}" in
+        setup)
+            echo "🔧 Setting up local development environment..."
+            setup_local_env
+            setup_local_postgres
+            start_local_services
+            echo "${GREEN}✅ Local environment ready${NC}"
+            echo "${YELLOW}Next: npm run dev${NC}"
+            ;;
+        test)
+            echo "🧪 Running complete local testing..."
+            setup_local_env
+            start_local_services
+            run_local_tests
+            stop_local_services
+            ;;
+        start)
+            echo "🚀 Starting local environment..."
+            setup_local_env
+            start_local_services
+            echo "${GREEN}✅ Ready to go! Run npm run dev${NC}"
+            ;;
+        stop)
+            stop_local_services
+            ;;
+        shell)
+            echo "🐚 Opening interactive shell with environment loaded..."
+            setup_local_env
+            source "$ENV_FILE"
+            exec bash -c "source '$ENV_FILE' && exec bash"
+            ;;
+        *)
+            echo "Usage: $0 {setup|test|start|stop|shell}"
+            echo ""
+            echo "Commands:"
+            echo "  setup  - Configure local environment and services"
+            echo "  test   - Run complete local E2E tests"
+            echo "  start  - Start local PostgreSQL and services"
+            echo "  stop   - Stop local services"
+            echo "  shell  - Interactive shell with environment loaded"
+            exit 1
+            ;;
+    esac
+}
+
+# Handle shutdown gracefully
+trap 'echo "${RED}🛑 Interrupted - cleaning up...${NC}"; stop_local_services; exit 130' INT TERM
+
+# Run main function
+main "$@"
