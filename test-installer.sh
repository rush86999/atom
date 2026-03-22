#!/bin/bash

# Test the Atom installer script
set -e

echo "=================================="
echo "Atom Installer Script Test Suite"
echo "=================================="
echo ""

SCRIPT_PATH="./install-mac-mini.sh"
PASSED=0
FAILED=0

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

test_pass() {
    echo -e "${GREEN}✓ PASS${NC}: $1"
    PASSED=$((PASSED + 1))
}

test_fail() {
    echo -e "${RED}✗ FAIL${NC}: $1"
    FAILED=$((FAILED + 1))
}

echo "Test 1: Script file exists"
if [ -f "$SCRIPT_PATH" ]; then
    test_pass "Script file exists"
else
    test_fail "Script file not found"
    exit 1
fi

echo ""
echo "Test 2: Script is executable"
if [ -x "$SCRIPT_PATH" ]; then
    test_pass "Script is executable"
else
    test_fail "Script is not executable"
fi

echo ""
echo "Test 3: Shebang is correct"
if head -n 1 "$SCRIPT_PATH" | grep -q '#!/bin/bash'; then
    test_pass "Shebang is #!/bin/bash"
else
    test_fail "Shebang is incorrect"
fi

echo ""
echo "Test 4: Script has no syntax errors (extended test)"
# Test by sourcing in a subshell with error handling
OUTPUT=$(bash -c "set +e; source '$SCRIPT_PATH' 2>&1" || true)

if echo "$OUTPUT" | grep -q "syntax error"; then
    test_fail "Syntax errors found:\n$OUTPUT"
else
    # Syntax might be OK - test individual functions
    test_pass "No critical syntax errors detected"
fi

echo ""
echo "Test 5: Key functions are defined"
FUNCTIONS=(
    "print_header"
    "print_success"
    "print_error"
    "print_warning"
    "print_info"
    "check_macos"
    "check_docker"
    "check_git"
    "check_ports"
    "configure_environment"
    "start_services"
    "troubleshoot_menu"
)

for FUNC in "${FUNCTIONS[@]}"; do
    if grep -q "^$FUNC()" "$SCRIPT_PATH"; then
        test_pass "Function $FUNC() defined"
    else
        test_fail "Function $FUNC() not found"
    fi
done

echo ""
echo "Test 6: Required variables are set"
VARS=(
    "RED"
    "GREEN"
    "YELLOW"
    "BLUE"
    "CYAN"
    "NC"
)

for VAR in "${VARS[@]}"; do
    if grep -q "^$VAR=" "$SCRIPT_PATH"; then
        test_pass "Variable $VAR defined"
    else
        test_fail "Variable $VAR not found"
    fi
done

echo ""
echo "Test 7: Script contains troubleshooting mode"
if grep -q "troubleshoot" "$SCRIPT_PATH"; then
    test_pass "Troubleshooting features present"
else
    test_fail "No troubleshooting features found"
fi

echo ""
echo "Test 8: Error handling is present"
if grep -q "set -e" "$SCRIPT_PATH" && grep -q "exit 1" "$SCRIPT_PATH"; then
    test_pass "Error handling configured"
else
    test_fail "Error handling missing"
fi

echo ""
echo "Test 9: Docker Compose references are correct"
if grep -q "docker-compose-personal.yml" "$SCRIPT_PATH"; then
    test_pass "Docker Compose file referenced"
else
    test_fail "Docker Compose file not referenced"
fi

echo ""
echo "Test 10: Encryption key generation is included"
if grep -q "openssl rand -base64 32" "$SCRIPT_PATH"; then
    test_pass "Encryption key generation included"
else
    test_fail "Encryption key generation missing"
fi

echo ""
echo "Test 11: API key configuration is present"
if grep -q "OPENAI_API_KEY" "$SCRIPT_PATH" && grep -q "ANTHROPIC_API_KEY" "$SCRIPT_PATH"; then
    test_pass "API key configuration present"
else
    test_fail "API key configuration missing"
fi

echo ""
echo "Test 12: Health check endpoints are tested"
if grep -q "health/live" "$SCRIPT_PATH" && grep -q "health/ready" "$SCRIPT_PATH"; then
    test_pass "Health check endpoints included"
else
    test_fail "Health check endpoints missing"
fi

echo ""
echo "Test 13: Port checking is implemented"
if grep -q "lsof -i :" "$SCRIPT_PATH"; then
    test_pass "Port checking implemented"
else
    test_fail "Port checking missing"
fi

echo ""
echo "Test 14: Service status checking is included"
if grep -q "docker-compose.*ps" "$SCRIPT_PATH"; then
    test_pass "Service status checking included"
else
    test_fail "Service status checking missing"
fi

echo ""
echo "Test 15: Log viewing functionality is present"
if grep -q "docker-compose.*logs" "$SCRIPT_PATH"; then
    test_pass "Log viewing functionality present"
else
    test_fail "Log viewing functionality missing"
fi

echo ""
echo "=================================="
echo "Test Results"
echo "=================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed. Please review.${NC}"
    exit 1
fi
