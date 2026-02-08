#!/bin/bash

# Verification script for incomplete implementation fixes
# This script verifies that the fixes are properly applied

echo "=========================================="
echo "Verifying Incomplete Implementation Fixes"
echo "=========================================="
echo ""

# Check document_ingestion_routes.py
echo "1. Checking document_ingestion_routes.py for authentication..."
if grep -q "from core.security_dependencies import get_current_user" /Users/rushiparikh/projects/atom/backend/api/document_ingestion_routes.py; then
    echo "   ✅ get_current_user imported"
else
    echo "   ❌ get_current_user NOT imported"
fi

if grep -q "current_user: User = Depends(get_current_user)" /Users/rushiparikh/projects/atom/backend/api/document_ingestion_routes.py; then
    echo "   ✅ Authentication parameters added to endpoints"
else
    echo "   ❌ Authentication parameters NOT added"
fi
echo ""

# Check document_routes.py
echo "2. Checking document_routes.py for authentication..."
if grep -q "from core.security_dependencies import get_current_user" /Users/rushiparikh/projects/atom/backend/api/document_routes.py; then
    echo "   ✅ get_current_user imported"
else
    echo "   ❌ get_current_user NOT imported"
fi

if grep -q "current_user: User = Depends(get_current_user)" /Users/rushiparikh/projects/atom/backend/api/document_routes.py; then
    echo "   ✅ Authentication parameters added to endpoints"
else
    echo "   ❌ Authentication parameters NOT added"
fi
echo ""

# Check byok_handler.py
echo "3. Checking byok_handler.py for logging..."
if grep -q 'logger.warning(f"Cost estimation failed for model' /Users/rushiparikh/projects/atom/backend/core/llm/byok_handler.py; then
    echo "   ✅ Cost estimation logging added"
else
    echo "   ❌ Cost estimation logging NOT added"
fi
echo ""

# Check browser_tool.py
echo "4. Checking browser_tool.py for logging..."
if grep -q 'logger.debug(f"Wait for selector' /Users/rushiparikh/projects/atom/backend/tools/browser_tool.py; then
    echo "   ✅ Wait for selector logging added"
else
    echo "   ❌ Wait for selector logging NOT added"
fi
echo ""

# Check satellite_routes.py
echo "5. Checking satellite_routes.py for logging..."
if grep -q 'logger.debug(f"Failed to close WebSocket' /Users/rushiparikh/projects/atom/backend/api/satellite_routes.py; then
    echo "   ✅ WebSocket close logging added"
else
    echo "   ❌ WebSocket close logging NOT added"
fi
echo ""

# Check deeplinks.py
echo "6. Checking deeplinks.py for exception enhancements..."
if grep -q "def __init__(self, message: str, url: str = \"\", details: dict = None):" /Users/rushiparikh/projects/atom/backend/core/deeplinks.py; then
    echo "   ✅ DeepLinkParseException has __init__ method"
else
    echo "   ❌ DeepLinkParseException missing __init__ method"
fi

if grep -q "def __str__(self):" /Users/rushiparikh/projects/atom/backend/core/deeplinks.py; then
    echo "   ✅ Exception classes have __str__ method"
else
    echo "   ❌ Exception classes missing __str__ method"
fi
echo ""

# Check custom_components_service.py
echo "7. Checking custom_components_service.py for exception enhancements..."
if grep -q "def __init__(self, message: str, component_name: str = \"\", validation_reason: str = \"\"):" /Users/rushiparikh/projects/atom/backend/core/custom_components_service.py; then
    echo "   ✅ ComponentSecurityError has __init__ method"
else
    echo "   ❌ ComponentSecurityError missing __init__ method"
fi
echo ""

# Check test file
echo "8. Checking test file..."
if [ -f /Users/rushiparikh/projects/atom/backend/tests/test_incomplete_implementations_fixes.py ]; then
    echo "   ✅ Test file created"
    TEST_COUNT=$(grep -c "def test_" /Users/rushiparikh/projects/atom/backend/tests/test_incomplete_implementations_fixes.py)
    echo "   ✅ $TEST_COUNT tests defined"
else
    echo "   ❌ Test file NOT created"
fi
echo ""

# Check summary document
echo "9. Checking summary document..."
if [ -f /Users/rushiparikh/projects/atom/backend/INCOMPLETE_IMPLEMENTATION_FIXES_SUMMARY.md ]; then
    echo "   ✅ Summary document created"
else
    echo "   ❌ Summary document NOT created"
fi
echo ""

echo "=========================================="
echo "Verification Complete!"
echo "=========================================="
