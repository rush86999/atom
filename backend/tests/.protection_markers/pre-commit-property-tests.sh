#!/bin/bash
# Pre-commit hook to verify property-based test integrity
#
# Installation:
#   cp .protection_markers/pre-commit-property-tests.sh .git/hooks/pre-commit-property-tests
#   chmod +x .git/hooks/pre-commit-property-tests
#
# Add to .git/hooks/pre-commit:
#   .git/hooks/pre-commit-property-tests

echo "Verifying property-based test integrity..."

PROTECTED_DIR="tests/property_tests"

# Check if protected files were modified
if git diff --cached --name-only | grep -q "^$PROTECTED_DIR/"; then
    echo ""
    echo "⚠️  WARNING: Property-based tests have been modified!"
    echo ""
    echo "The following protected files were modified:"
    git diff --cached --name-only | grep "^$PROTECTED_DIR/"
    echo ""
    echo "📋 These tests verify CRITICAL SYSTEM INVARIANTS."
    echo ""
    echo "Before proceeding, ensure:"
    echo "  1. You are fixing a TEST BUG (not an implementation bug)"
    echo "  2. You are ADDING new invariants"
    echo "  3. You have EXPLICIT APPROVAL from engineering lead"
    echo ""
    echo "📖 See: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md"
    echo ""
    read -p "Continue with commit? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Commit aborted."
        echo ""
        echo "💡 To bypass (not recommended): git commit --no-verify"
        exit 1
    fi
fi

exit 0
