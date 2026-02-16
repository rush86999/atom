#!/bin/bash

# Atom Personal Edition - Setup Verification Script
# Tests all components of the Personal Edition setup

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║  Atom Personal Edition - Setup Verification              ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0
SKIPPED=0

# Function to print test result
print_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $2"
        ((PASSED++))
    elif [ $1 -eq 1 ]; then
        echo -e "${YELLOW}⚠️  SKIP${NC}: $2"
        ((SKIPPED++))
    else
        echo -e "${RED}❌ FAIL${NC}: $2"
        ((FAILED++))
    fi
}

echo "📋 Prerequisites Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Docker
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    print_result 0 "Docker installed: $DOCKER_VERSION"
else
    print_result 2 "Docker not found - required for Docker installation"
fi

# Check Docker Compose
if command -v docker-compose &> /dev/null || docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker-compose --version 2>/dev/null || docker compose version)
    print_result 0 "Docker Compose installed: $COMPOSE_VERSION"
else
    print_result 2 "Docker Compose not found"
fi

# Check Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    print_result 0 "Python installed: $PYTHON_VERSION"
else
    print_result 2 "Python 3 not found - required for native installation"
fi

# Check Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    print_result 0 "Node.js installed: $NODE_VERSION"
else
    print_result 1 "Node.js not found - required for frontend"
fi

# Check Git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version)
    print_result 0 "Git installed: $GIT_VERSION"
else
    print_result 1 "Git not found"
fi

echo ""
echo "📁 File Structure Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check required files
FILES=(
    "docker-compose-personal.yml"
    ".env.personal"
    "docs/PERSONAL_EDITION.md"
    "docs/NATIVE_SETUP.md"
    "docs/VECTOR_EMBEDDINGS.md"
    "install-native.sh"
    "install-native.bat"
    "test-embeddings.py"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        print_result 0 "File exists: $file"
    else
        print_result 2 "File missing: $file"
    fi
done

echo ""
echo "⚙️  Configuration Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if .env exists
if [ -f ".env" ]; then
    print_result 0 ".env file exists"

    # Check for API keys
    if grep -q "^OPENAI_API_KEY=sk-" .env 2>/dev/null; then
        print_result 0 "OpenAI API key configured"
    elif grep -q "^# OPENAI_API_KEY=" .env 2>/dev/null; then
        print_result 1 "OpenAI API key not set (commented out)"
    else
        print_result 1 "OpenAI API key not found in .env"
    fi

    if grep -q "^ANTHROPIC_API_KEY=sk-ant-" .env 2>/dev/null; then
        print_result 0 "Anthropic API key configured"
    elif grep -q "^# ANTHROPIC_API_KEY=" .env 2>/dev/null; then
        print_result 1 "Anthropic API key not set (commented out)"
    else
        print_result 1 "Anthropic API key not found in .env"
    fi

    # Check for encryption keys
    if grep -q "^BYOK_ENCRYPTION_KEY=" .env 2>/dev/null && ! grep -q "change-this" .env 2>/dev/null; then
        print_result 0 "BYOK encryption key configured"
    else
        print_result 1 "BYOK encryption key not set properly"
    fi

    if grep -q "^JWT_SECRET_KEY=" .env 2>/dev/null && ! grep -q "change-this" .env 2>/dev/null; then
        print_result 0 "JWT secret key configured"
    else
        print_result 1 "JWT secret key not set properly"
    fi

    # Check for embedding configuration
    if grep -q "^EMBEDDING_PROVIDER=" .env 2>/dev/null; then
        print_result 0 "Embedding provider configured"
    else
        print_result 1 "Embedding provider not set (will use default)"
    fi

else
    print_result 1 ".env file does not exist - needs to be created from .env.personal"
fi

echo ""
echo "🐳 Docker Configuration Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check docker-compose-personal.yml
if [ -f "docker-compose-personal.yml" ]; then
    print_result 0 "Docker Compose personal file exists"

    # Check for SQLite configuration
    if grep -q "DATABASE_URL=sqlite" docker-compose-personal.yml; then
        print_result 0 "SQLite database configured (Personal Edition)"
    else
        print_result 2 "SQLite not configured in docker-compose-personal.yml"
    fi

    # Check for services
    if grep -q "atom-backend:" docker-compose-personal.yml; then
        print_result 0 "Backend service defined"
    fi

    if grep -q "atom-frontend:" docker-compose-personal.yml; then
        print_result 0 "Frontend service defined"
    fi

    if grep -q "browser-node:" docker-compose-personal.yml; then
        print_result 0 "Browser automation service (optional)"
    fi
else
    print_result 2 "docker-compose-personal.yml not found"
fi

echo ""
echo "📦 Backend Dependencies Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "backend/requirements.txt" ]; then
    print_result 0 "requirements.txt exists"

    # Check for key dependencies
    DEPS=(
        "fastembed"
        "lancedb"
        "fastapi"
        "sqlalchemy"
        "uvicorn"
    )

    for dep in "${DEPS[@]}"; do
        if grep -q "$dep" backend/requirements.txt; then
            print_result 0 "Dependency included: $dep"
        else
            print_result 2 "Dependency missing: $dep"
        fi
    done
else
    print_result 2 "backend/requirements.txt not found"
fi

echo ""
echo "🎨 Frontend Dependencies Check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "frontend-nextjs/package.json" ]; then
    print_result 0 "Frontend package.json exists"

    if [ -d "frontend-nextjs/node_modules" ]; then
        NODE_MODULES_COUNT=$(find frontend-nextjs/node_modules -maxdepth 1 -type d | wc -l)
        print_result 0 "node_modules installed ($((NODE_MODULES_COUNT - 1)) packages)"
    else
        print_result 1 "node_modules not installed (run: cd frontend-nextjs && npm install)"
    fi
else
    print_result 2 "frontend-nextjs/package.json not found"
fi

echo ""
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

TOTAL=$((PASSED + FAILED + SKIPPED))
echo "Total Tests: $TOTAL"
echo -e "  ${GREEN}Passed${NC}: $PASSED"
echo -e "  ${YELLOW}Skipped${NC}: $SKIPPED"
echo -e "  ${RED}Failed${NC}: $FAILED"

if [ $FAILED -eq 0 ]; then
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ Personal Edition Ready!                                  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "🚀 Quick Start Commands:"
    echo ""
    echo "1. Add your API keys to .env:"
    echo "   nano .env"
    echo ""
    echo "2. Start Atom (Docker):"
    echo "   docker-compose -f docker-compose-personal.yml up -d"
    echo ""
    echo "3. Access Atom:"
    echo "   http://localhost:3000"
    echo ""
    echo "📚 Documentation:"
    echo "   - docs/PERSONAL_EDITION.md (Docker setup)"
    echo "   - docs/NATIVE_SETUP.md (Native installation)"
    echo "   - docs/VECTOR_EMBEDDINGS.md (Embeddings guide)"
    echo ""
else
    echo ""
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ⚠️  Setup Incomplete - Fix Failed Items Above              ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "📖 Quick Fixes:"
    echo ""
    echo "1. Install Docker:"
    echo "   https://www.docker.com/products/docker-desktop/"
    echo ""
    echo "2. Create .env from template:"
    echo "   cp .env.personal .env"
    echo "   nano .env  # Add your API keys"
    echo ""
    echo "3. Install frontend dependencies:"
    echo "   cd frontend-nextjs && npm install"
    echo ""
fi

echo ""
exit $FAILED
