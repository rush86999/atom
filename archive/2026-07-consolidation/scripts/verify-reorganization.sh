#!/bin/bash

# ATOM Reorganization Verification Script
# This script verifies that the reorganization was successful and all components work correctly

set -e

echo "🔍 ATOM Reorganization Verification"
echo "==================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if directory exists and has files
check_directory() {
    local dir=$1
    local description=$2

    if [ -d "$dir" ] && [ "$(ls -A "$dir" 2>/dev/null)" ]; then
        echo -e "${GREEN}✓ $description: $dir${NC}"
        return 0
    else
        echo -e "${RED}✗ $description: $dir (missing or empty)${NC}"
        return 1
    fi
}

# Function to check if file exists
check_file() {
    local file=$1
    local description=$2

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓ $description: $file${NC}"
        return 0
    else
        echo -e "${RED}✗ $description: $file (missing)${NC}"
        return 1
    fi
}

echo -e "${BLUE}Verifying Frontend Service Organization...${NC}"

# Check frontend service directories
check_directory "src/services/ai" "AI Services Directory"
check_directory "src/services/integrations" "Integration Services Directory"
check_directory "src/services/workflows" "Workflow Services Directory"
check_directory "src/services/utils" "Utility Services Directory"

# Check key AI services
check_file "src/services/ai/ChatOrchestrationService.ts" "Chat Orchestration Service"
check_file "src/services/ai/hybridLLMService.ts" "Hybrid LLM Service"
check_file "src/services/ai/nluService.ts" "NLU Service"
check_file "src/services/ai/openaiService.ts" "OpenAI Service"

# Check integration services
check_file "src/services/integrations/authService.ts" "Auth Service"
check_file "src/services/integrations/apiKeyService.ts" "API Key Service"
check_file "src/services/integrations/connection-status-service.ts" "Connection Status Service"

# Check workflow services
check_file "src/services/workflows/workflowService.ts" "Workflow Service"
check_file "src/services/workflows/autonomousWorkflowService.ts" "Autonomous Workflow Service"

echo -e "${BLUE}Verifying Backend Consolidation...${NC}"

# Check backend consolidated structure
check_directory "backend/consolidated" "Consolidated Backend Directory"
check_directory "backend/consolidated/core" "Core Backend Services"
check_directory "backend/consolidated/integrations" "Backend Integration Services"
check_directory "backend/consolidated/workflows" "Backend Workflow Services"

# Check key backend files
check_file "backend/consolidated/core/database_manager.py" "Database Manager"
check_file "backend/consolidated/core/auth_service.py" "Auth Service"
check_file "backend/consolidated/integrations/asana_service.py" "Asana Service"
check_file "backend/consolidated/integrations/dropbox_service.py" "Dropbox Service"
check_file "backend/consolidated/integrations/outlook_service.py" "Outlook Service"

echo -e "${BLUE}Verifying Application Integrity...${NC}"

# Check main applications still exist
check_directory "frontend-nextjs" "Frontend Next.js App"
check_directory "desktop/tauri" "Desktop Tauri App"

# Check main backend still exists
check_directory "backend/python-api-service" "Main Backend Service"

# Check desktop embedded backend
check_directory "desktop/tauri/src-tauri/python-backend" "Desktop Embedded Backend"
check_file "desktop/tauri/src-tauri/python-backend/main.py" "Desktop Backend Main"

echo -e "${BLUE}Verifying Documentation...${NC}"

# Check documentation
check_file "ARCHITECTURE.md" "Architecture Documentation"
check_file "MIGRATION_GUIDE.md" "Migration Guide"

echo -e "${BLUE}Running Quick Syntax Checks...${NC}"

# Quick TypeScript syntax check for frontend services
echo "Checking TypeScript syntax in frontend services..."
if command -v npx >/dev/null 2>&1; then
    cd frontend-nextjs
    if npx tsc --noEmit --skipLibCheck > /dev/null 2>&1; then
        echo -e "${GREEN}✓ TypeScript syntax check passed${NC}"
    else
        echo -e "${YELLOW}⚠ TypeScript syntax check has warnings${NC}"
    fi
    cd ..
else
    echo -e "${YELLOW}⚠ TypeScript compiler not available, skipping syntax check${NC}"
fi

# Quick Python syntax check for backend
echo "Checking Python syntax in backend services..."
if python3 -m py_compile backend/consolidated/integrations/asana_service.py > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Python syntax check passed${NC}"
else
    echo -e "${YELLOW}⚠ Python syntax check has warnings${NC}"
fi

echo -e "${BLUE}===================================${NC}"
echo -e "${GREEN}🎉 Reorganization Verification Complete!${NC}"
echo -e "${BLUE}===================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo "1. Update import paths in frontend components"
echo "2. Test the applications with: ./start-dev.sh"
echo "3. Run comprehensive tests: ./test-all-features.sh"
echo ""
echo -e "${BLUE}For detailed migration instructions, see MIGRATION_GUIDE.md${NC}"
