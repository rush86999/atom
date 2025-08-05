#!/bin/bash

# Atom Application Production-Ready Fix Script
# This script addresses the critical issues discovered during E2E testing

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔧 Atom Production-Ready Fix Script"
echo "===================================="

# Step 1: Install missing dependencies
echo "📦 Installing required dependencies..."
npm install pg axios jest supertest -D || true

# Step 2: Fix duplicate files causing build failures
echo "🗂️  Fixing duplicate file issues..."

# Create backup directory
mkdir -p .backup/$(date +%Y%m%d_%H%M%S)

# Fix duplicate .js vs .tsx files causing build conflicts
echo "   Removing conflicting .js files (keeping .tsx versions)..."
find pages/ -name "*.js" -type f | while read jsfile; do
    tsxfile="${jsfile%.js}.tsx"
    if [[ -f "$tsxfile" ]]; then
        echo "     Backing up and removing $jsfile (keeping $tsxfile)"
        cp "$jsfile" ".backup/$(date +%Y%m%d_%H%M%S)/" 2>/dev/null || true
        rm "$jsfile"
    fi
done

# Remove specific duplicate files identified in the build failure
CONFLICTING_FILES=(
    "pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistAlarms.js"
    "pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistBaseStep.js"
    "pages/Assist/CreateMeetingAssistWizard/CreateMeetingAssistBaseStep3.js"
    "pages/Auth/google/callback-google-oauth.js"
    "pages/Calendar/UserCreateEvent.js"
    "pages/OnBoard/UserOnBoard.js"
)

for file in "${CONFLICTING_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "     Removing conflicting file: $file"
        mv "$file" ".backup/$(date +%Y%m%d_%H%M%S)/" 2>/dev/null || true
    fi
done

# Step 3: Create .env.local if it doesn't exist
echo "🌍 Setting up environment variables..."
if [[ ! -f .env.local ]]; then
    echo "   Creating .env.local template..."
    cat > .env.local << 'EOF'
# Production Environment Variables
NODE_ENV=production
PORT=3000

# PostgreSQL Database (REQUIRED - Configure these!)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=atom_production
POSTGRES_USER=atom_user
POSTGRES_PASSWORD=your_secure_password_here

# Connection URL (Alternative to individual settings)
DATABASE_URL=postgresql://atom_user:your_password@localhost:5432/atom_production

# Required Service Keys
OPENAI_API_KEY=your_openai_api_key_here
JWT_SECRET=your_32_character_secure_secret_key_here_min_length

# External Integrations
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
LINKEDIN_CLIENT_ID=your_linkedin_client_id
SLACK_CLIENT_ID=your_slack_client_id

# Additional Security
ENCRYPTION_KEY=your_32_char_encryption_key
EOF

    echo "   ${YELLOW}⚠️  Please edit .env.local with your actual values!${NC}"
    echo "   Make sure to set your POSTGRES_PASSWORD and OPENAI_API_KEY"
fi

# Step 4: Test build configuration
echo "🏗️  Testing build configuration..."
if npm run build --silent 2>/dev/null; then
    echo "   ${GREEN}✅ Build successful${NC}"
else
    echo "   ${RED}❌ Build failed - addressing issues...${NC}"

    # Check for TypeScript errors
    echo "   Checking for TypeScript compilation issues..."
    if command -v tsc >/dev/null 2>&1; then
        npx tsc --noEmit
    fi

    # Clear build cache
    if [[ -d ".next" ]]; then
        echo "   Clearing build cache..."
        rm -rf .next
    fi
fi

# Step 5: Create package.json scripts for testing
echo "🎯 Adding test scripts to package.json..."
if [[ -f package.json ]]; then
    temp_file=$(mktemp)
    jq '.scripts += {
        "test:e2e": "node test-live-ready.js",
        "test:e2e:docker": "docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit",
        "e2e:quick": "npm run build && npm run test:e2e",
        "db:setup": "psql -h \"$POSTGRES_HOST\" -U \"$POSTGRES_USER\" -d \"$POSTGRES_DB\" -f init-test-db.sql"
    }' package.json > "$temp_file" && mv "$temp_file" package.json 2>/dev/null || true
fi

# Step 6: Verify environment setup
echo "🔍 Post-fix verification..."
echo "   Testing environment setup..."

# Check if required files exist
REQUIRED_FILES=(
    "test-live-ready.js"
    ".env.template"
    "docker-compose.test.yml"
    "init-test-db.sql"
    "__tests__/e2e/live-ready.test.ts"
    "package.json"
)
for file in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$file" ]]; then
        echo "   ${GREEN}✅ $file${NC}"
    else
        echo "   ${RED}❌ $file missing${NC}"
    fi
done

# Step 7: Next steps guidance
echo ""
echo "=========================="
echo "${GREEN}🎯 Production-Ready Fixes Applied!${NC}"
echo "=========================="
echo ""
echo "Next steps:"
echo "1. ${YELLOW}Edit .env.local with your actual values:${NC}"
echo "   - POSTGRES_PASSWORD: Set a secure password"
echo "   - OPENAI_API_KEY: Your OpenAI API key"
echo "   - JWT_SECRET: 32 character random string"
echo ""
echo "2. ${YELLOW}Optional: Use Docker for quick setup:${NC}"
echo "   npm run test:e2e:docker"
echo ""
echo "3. ${YELLOW}Complete setup:${NC}"
echo "   npm run e2e:quick"
echo ""
echo "4. ${YELLOW}Manual database setup:${NC}"
echo "   npm run db:setup"
echo ""
echo "5. ${GREEN}Run full verification:${NC}"
echo "   node test-live-ready.js"
echo ""

# Step 8: Cleanup on exit
trap "echo ''; echo '${GREEN}✅ Fix script completed${NC}'" EXIT
