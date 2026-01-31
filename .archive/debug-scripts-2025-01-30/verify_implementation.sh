#!/bin/bash
# Quick verification script for the implementation

echo "======================================"
echo "Implementation Verification Script"
echo "======================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BACKEND_DIR="/Users/rushiparikh/projects/atom/backend"
FRONTEND_DIR="/Users/rushiparikh/projects/atom/frontend-nextjs"

# Test counter
PASS=0
FAIL=0

test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((PASS++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((FAIL++))
    fi
}

echo "=== Phase 1: LLM Token Streaming ==="
echo ""

# Test 1.1: Check byok_handler.py for streaming method
echo -n "Testing: BYOK streaming method exists... "
if grep -q "async def stream_completion" "$BACKEND_DIR/core/llm/byok_handler.py"; then
    test_result 0 "stream_completion() method found"
else
    test_result 1 "stream_completion() method NOT found"
fi

# Test 1.2: Check WebSocket streaming constants
echo -n "Testing: WebSocket streaming constants... "
if grep -q "STREAMING_UPDATE.*streaming:update" "$BACKEND_DIR/core/websockets.py"; then
    test_result 0 "Streaming constants defined"
else
    test_result 1 "Streaming constants NOT found"
fi

# Test 1.3: Check streaming endpoint
echo -n "Testing: Streaming chat endpoint... "
if grep -q '@router.post("/chat/stream")' "$BACKEND_DIR/core/atom_agent_endpoints.py"; then
    test_result 0 "Streaming endpoint exists"
else
    test_result 1 "Streaming endpoint NOT found"
fi

# Test 1.4: Check useWebSocket streaming state
echo -n "Testing: useWebSocket streaming state... "
if grep -q "streamingContent.*useState.*Map" "$FRONTEND_DIR/hooks/useWebSocket.ts"; then
    test_result 0 "streamingContent state found"
else
    test_result 1 "streamingContent state NOT found"
fi

# Test 1.5: Check ChatInterface streaming rendering
echo -n "Testing: ChatInterface streaming UI... "
if grep -q "currentStreamId.*streamingContent" "$FRONTEND_DIR/components/chat/ChatInterface.tsx"; then
    test_result 0 "Streaming rendering logic found"
else
    test_result 1 "Streaming rendering NOT found"
fi

echo ""
echo "=== Phase 2: Canvas Chart Components ==="
echo ""

# Test 2.1: Check LineChart component
echo -n "Testing: LineChart component... "
if [ -f "$FRONTEND_DIR/components/canvas/LineChart.tsx" ]; then
    if grep -q "LineChartCanvas" "$FRONTEND_DIR/components/canvas/LineChart.tsx"; then
        test_result 0 "LineChart component exists"
    else
        test_result 1 "LineChart component invalid"
    fi
else
    test_result 1 "LineChart component NOT found"
fi

# Test 2.2: Check BarChart component
echo -n "Testing: BarChart component... "
if [ -f "$FRONTEND_DIR/components/canvas/BarChart.tsx" ]; then
    if grep -q "BarChartCanvas" "$FRONTEND_DIR/components/canvas/BarChart.tsx"; then
        test_result 0 "BarChart component exists"
    else
        test_result 1 "BarChart component invalid"
    fi
else
    test_result 1 "BarChart component NOT found"
fi

# Test 2.3: Check PieChart component
echo -n "Testing: PieChart component... "
if [ -f "$FRONTEND_DIR/components/canvas/PieChart.tsx" ]; then
    if grep -q "PieChartCanvas" "$FRONTEND_DIR/components/canvas/PieChart.tsx"; then
        test_result 0 "PieChart component exists"
    else
        test_result 1 "PieChart component invalid"
    fi
else
    test_result 1 "PieChart component NOT found"
fi

# Test 2.4: Check canvas_tool.py
echo -n "Testing: Canvas tool backend... "
if [ -f "$BACKEND_DIR/tools/canvas_tool.py" ]; then
    if grep -q "async def present_chart" "$BACKEND_DIR/tools/canvas_tool.py"; then
        test_result 0 "canvas_tool.py with present_chart()"
    else
        test_result 1 "canvas_tool.py incomplete"
    fi
else
    test_result 1 "canvas_tool.py NOT found"
fi

# Test 2.5: Check CanvasHost chart integration
echo -n "Testing: CanvasHost chart integration... "
if grep -q "case \"line_chart\"" "$FRONTEND_DIR/components/chat/CanvasHost.tsx" && \
   grep -q "case \"bar_chart\"" "$FRONTEND_DIR/components/chat/CanvasHost.tsx" && \
   grep -q "case \"pie_chart\"" "$FRONTEND_DIR/components/chat/CanvasHost.tsx"; then
    test_result 0 "Chart cases in CanvasHost"
else
    test_result 1 "Chart cases NOT found"
fi

echo ""
echo "=== Phase 3: Interactive Form System ==="
echo ""

# Test 3.1: Check InteractiveForm component
echo -n "Testing: InteractiveForm component... "
if [ -f "$FRONTEND_DIR/components/canvas/InteractiveForm.tsx" ]; then
    if grep -q "const validateField" "$FRONTEND_DIR/components/canvas/InteractiveForm.tsx" && \
       grep -q "validation.*pattern" "$FRONTEND_DIR/components/canvas/InteractiveForm.tsx"; then
        test_result 0 "InteractiveForm with validation"
    else
        test_result 1 "InteractiveForm incomplete"
    fi
else
    test_result 1 "InteractiveForm NOT found"
fi

# Test 3.2: Check canvas_routes API
echo -n "Testing: Canvas API routes... "
if [ -f "$BACKEND_DIR/api/canvas_routes.py" ]; then
    if grep -q "@router.post.*submit" "$BACKEND_DIR/api/canvas_routes.py"; then
        test_result 0 "Canvas submission endpoint"
    else
        test_result 1 "Canvas routes incomplete"
    fi
else
    test_result 1 "canvas_routes.py NOT found"
fi

# Test 3.3: Check main_api_app includes canvas routes
echo -n "Testing: Canvas routes registered... "
if grep -q "from api.canvas_routes import" "$BACKEND_DIR/main_api_app.py"; then
    test_result 0 "Canvas routes registered"
else
    test_result 1 "Canvas routes NOT registered"
fi

# Test 3.4: Check CanvasHost uses InteractiveForm
echo -n "Testing: CanvasHost uses InteractiveForm... "
if grep -q "import.*InteractiveForm" "$FRONTEND_DIR/components/chat/CanvasHost.tsx"; then
    if grep -q "<InteractiveForm" "$FRONTEND_DIR/components/chat/CanvasHost.tsx" && \
       grep -q "canvasId={canvasId}" "$FRONTEND_DIR/components/chat/CanvasHost.tsx"; then
        test_result 0 "InteractiveForm integrated"
    else
        test_result 1 "InteractiveForm not used"
    fi
else
    test_result 1 "InteractiveForm not imported"
fi

echo ""
echo "=== Syntax Validation ==="
echo ""

# Test 4.1: Python syntax checks
echo -n "Testing: Python file syntax... "
SYNTAX_ERRORS=0
for file in \
    "$BACKEND_DIR/core/llm/byok_handler.py" \
    "$BACKEND_DIR/core/websockets.py" \
    "$BACKEND_DIR/core/atom_agent_endpoints.py" \
    "$BACKEND_DIR/api/canvas_routes.py" \
    "$BACKEND_DIR/tools/canvas_tool.py"
do
    if ! python3 -m py_compile "$file" 2>/dev/null; then
        ((SYNTAX_ERRORS++))
    fi
done

if [ $SYNTAX_ERRORS -eq 0 ]; then
    test_result 0 "All Python files syntax valid"
else
    test_result 1 "$SYNTAX_ERRORS Python file(s) have syntax errors"
fi

# Test 4.2: TypeScript type check
echo -n "Testing: TypeScript type checking (implementation files only)... "
cd "$FRONTEND_DIR"
TYPE_OUTPUT=$(npm run type-check 2>&1)
if echo "$TYPE_OUTPUT" | grep -E "(canvas|LineChart|BarChart|PieChart|InteractiveForm|useWebSocket).*error TS" > /dev/null; then
    test_result 1 "Implementation files have type errors"
else
    test_result 0 "Implementation files type-safe"
fi

echo ""
echo "=== Dependency Verification ==="
echo ""

# Test 5.1: Check Recharts dependency
echo -n "Testing: Recharts dependency... "
if grep -q '"recharts".*3\.' "$FRONTEND_DIR/package.json"; then
    test_result 0 "Recharts installed"
else
    test_result 1 "Recharts NOT found"
fi

# Test 5.2: Check marked dependency
echo -n "Testing: Marked dependency... "
if grep -q '"marked"' "$FRONTEND_DIR/package.json"; then
    test_result 0 "Marked installed"
else
    test_result 1 "Marked NOT found"
fi

echo ""
echo "======================================"
echo "RESULTS"
echo "======================================"
echo -e "${GREEN}Passed:${NC} $PASS"
echo -e "${RED}Failed:${NC} $FAIL"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo ""
    echo "The implementation is ready for manual testing."
    echo ""
    echo "Next steps:"
    echo "1. Start backend: cd backend && python3 -m uvicorn main_api_app:app --reload"
    echo "2. Start frontend: cd frontend-nextjs && npm run dev"
    echo "3. Open browser: http://localhost:3000"
    echo "4. See IMPLEMENTATION_TEST_SUMMARY.md for manual test procedures"
    exit 0
else
    echo -e "${RED}✗ SOME TESTS FAILED${NC}"
    echo ""
    echo "Please review the failures above and fix the issues."
    exit 1
fi
