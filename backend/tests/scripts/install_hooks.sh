#!/bin/bash
#
# Install script for pre-commit coverage enforcement hook
#
# This script installs the coverage enforcement pre-commit hook to .git/hooks/
# Run this script once to enable automatic coverage checking on commits.
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOKS_DIR="$BACKEND_DIR/.git/hooks"
HOOK_SOURCE="$HOOKS_DIR/pre-commit"

echo "🔧 Installing coverage enforcement pre-commit hook..."
echo ""

# Check if .git/hooks directory exists
if [ ! -d "$HOOKS_DIR" ]; then
    echo -e "${RED}Error: .git/hooks directory not found at $HOOKS_DIR${NC}"
    echo "Please run this script from within a git repository."
    exit 1
fi

# Check if pre-commit hook already exists
if [ -f "$HOOK_SOURCE" ]; then
    echo -e "${YELLOW}Warning: Pre-commit hook already exists at $HOOK_SOURCE${NC}"
    read -p "Overwrite existing hook? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
fi

# Check if hook is executable
if [ -f "$HOOK_SOURCE" ] && [ -x "$HOOK_SOURCE" ]; then
    echo "✅ Pre-commit hook is already installed and executable."
else
    echo "✅ Pre-commit hook installed."
fi

# Verify hook is working
echo ""
echo "🧪 Verifying hook installation..."

if [ -x "$HOOK_SOURCE" ]; then
    echo -e "${GREEN}✅ Hook is executable${NC}"
else
    echo -e "${RED}❌ Hook is not executable${NC}"
    echo "Run: chmod +x $HOOK_SOURCE"
    exit 1
fi

# Print usage information
echo ""
echo "📚 Usage Information:"
echo ""
echo "The coverage enforcement hook will now run before every commit."
echo "It enforces 80% minimum coverage on new Python code."
echo ""
echo "To test the hook:"
echo "  1. Modify a Python file"
echo "  2. Stage the change: git add <file>"
echo "  3. Attempt to commit: git commit -m 'test'"
echo "  4. Hook will run and block commit if coverage is insufficient"
echo ""
echo "To bypass the hook (not recommended):"
echo "  git commit --no-verify -m 'message'"
echo ""
echo "To uninstall:"
echo "  rm $HOOK_SOURCE"
echo ""
echo -e "${GREEN}✅ Installation complete!${NC}"
