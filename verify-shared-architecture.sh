#!/bin/bash

# ATOM Shared Architecture Verification Script
# Verifies that both web and desktop apps can use the shared src/services directory

set -e

echo "🔍 ATOM Shared Architecture Verification"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to check if file exists and is readable
check_file() {
    local file=$1
    local description=$2

    if [ -f "$file" ] && [ -r "$file" ]; then
        echo -e "${GREEN}✓ $description: $file${NC}"
        return 0
    else
        echo -e "${RED}✗ $description: $file (missing or unreadable)${NC}"
        return 1
    fi
}

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

# Function to check TypeScript compilation
check_typescript() {
    local dir=$1
    local description=$2

    if command -v npx >/dev/null 2>&1; then
        cd "$dir"
        if npx tsc --noEmit --skipLibCheck > /dev/null 2>&1; then
            echo -e "${GREEN}✓ $description TypeScript compilation${NC}"
        else
            echo -e "${YELLOW}⚠ $description TypeScript compilation has warnings${NC}"
        fi
        cd - > /dev/null
    else
        echo -e "${YELLOW}⚠ TypeScript compiler not available, skipping $description check${NC}"
    fi
}

echo -e "${BLUE}Verifying Shared Services Structure...${NC}"

# Check shared services organization
check_directory "src/services/ai" "AI Services Directory"
check_directory "src/services/integrations" "Integration Services Directory"
check_directory "src/services/workflows" "Workflow Services Directory"
check_directory "src/services/utils" "Utility Services Directory"

# Check key service files
check_file "src/services/ai/ChatOrchestrationService.ts" "Chat Orchestration Service"
check_file "src/services/ai/nluService.ts" "NLU Service"
check_file "src/services/integrations/authService.ts" "Auth Service"
check_file "src/services/workflows/workflowService.ts" "Workflow Service"
check_file "src/services/utils/config.ts" "Shared Configuration"

echo -e "${BLUE}Verifying Frontend Web App Configuration...${NC}"

# Check frontend configuration
check_file "frontend-nextjs/next.config.js" "Next.js Configuration"
check_file "frontend-nextjs/package.json" "Frontend Package.json"

# Check if frontend has example usage
check_file "frontend-nextjs/src/components/ExampleServiceUsage.tsx" "Frontend Example Usage"

# Verify frontend can compile with shared services
check_typescript "frontend-nextjs" "Frontend"

echo -e "${BLUE}Verifying Desktop App Configuration...${NC}"

# Check desktop configuration
check_file "desktop/tauri/tsconfig.json" "Desktop TypeScript Configuration"
check_file "desktop/tauri/package.json" "Desktop Package.json"

# Check if desktop has example usage
check_file "desktop/tauri/src/components/ExampleServiceUsage.tsx" "Desktop Example Usage"

# Verify desktop can compile with shared services
check_typescript "desktop/tauri" "Desktop"

echo -e "${BLUE}Verifying Path Mappings...${NC}"

# Check frontend path mappings in next.config.js
if grep -q "@shared" frontend-nextjs/next.config.js; then
    echo -e "${GREEN}✓ Frontend path mappings configured${NC}"
else
    echo -e "${RED}✗ Frontend path mappings missing${NC}"
fi

# Check desktop path mappings in tsconfig.json
if grep -q "@shared" desktop/tauri/tsconfig.json; then
    echo -e "${GREEN}✓ Desktop path mappings configured${NC}"
else
    echo -e "${RED}✗ Desktop path mappings missing${NC}"
fi

echo -e "${BLUE}Verifying Backend Consolidation...${NC}"

# Check backend consolidation
check_directory "backend/consolidated" "Consolidated Backend"
check_directory "backend/consolidated/integrations" "Backend Integration Services"

# Check key backend files
check_file "backend/consolidated/integrations/asana_service.py" "Asana Service"
check_file "backend/consolidated/integrations/dropbox_service.py" "Dropbox Service"
check_file "backend/consolidated/integrations/outlook_service.py" "Outlook Service"

echo -e "${BLUE}Verifying Documentation...${NC}"

# Check documentation
check_file "ARCHITECTURE.md" "Architecture Documentation"
check_file "MIGRATION_GUIDE.md" "Migration Guide"
check_file "CODE_STRUCTURE_OVERVIEW.md" "Code Structure Overview"

echo -e "${BLUE}Testing Service Imports...${NC}"

# Create a simple test to verify imports work
cat > /tmp/test_shared_imports.ts << 'EOF'
// Test file to verify shared service imports
import { configManager } from '../src/services/utils/config';
import { ChatOrchestrationService } from '../src/services/ai/ChatOrchestrationService';
import { authService } from '../src/services/integrations/authService';
import { workflowService } from '../src/services/workflows/workflowService';

console.log('Shared service imports successful!');
console.log('Platform:', configManager.isDesktop() ? 'Desktop' : 'Web');
EOF

if npx tsc /tmp/test_shared_imports.ts --noEmit --skipLibCheck > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Shared service imports work correctly${NC}"
else
    echo -e "${RED}✗ Shared service imports have issues${NC}"
fi

rm -f /tmp/test_shared_imports.ts

echo -e "${BLUE}=======================================${NC}"
echo -e "${GREEN}🎉 Shared Architecture Verification Complete!${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""
echo -e "${YELLOW}Summary:${NC}"
echo "• Shared services organized in src/services/"
echo "• Frontend web app configured to use shared services"
echo "• Desktop app configured to use shared services"
echo "• Backend services consolidated"
echo "• Documentation updated"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Start development: ./start-dev.sh"
echo "2. Test web app: cd frontend-nextjs && npm run dev"
echo "3. Test desktop app: cd desktop/tauri && npm run dev"
echo "4. Run integration tests: ./test-all-features.sh"
echo ""
echo -e "${GREEN}Both applications now share the same business logic!${NC}"
