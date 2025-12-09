#!/bin/bash

# Integration Testing Script - Phase 61-66 Fixes
# Tests all 16 fixed endpoints

set -e

FRONTEND_URL="http://localhost:3000"
BACKEND_URL="http://localhost:8000"

echo "=================================="
echo "Integration Test Suite - Phase 61-66"
echo "=================================="
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

test_endpoint() {
    local name=$1
    local url=$2
    local method=$3
    local data=$4
    
    echo -n "Testing $name... "
    
    if [ "$method" = "POST" ]; then
        status=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$url" \
            -H "Content-Type: application/json" \
            -d "$data" 2>/dev/null || echo "000")
    else
        status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    fi
    
    if [ "$status" = "200" ] || [ "$status" = "302" ]; then
        echo -e "${GREEN}✓ PASS${NC} (HTTP $status)"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC} (HTTP $status)"
        ((FAILED++))
    fi
}

echo "=== Slack Integration (4 endpoints) ==="
test_endpoint "Slack Channels" "$FRONTEND_URL/api/integrations/slack/channels" "GET"
test_endpoint "Slack Messages" "$FRONTEND_URL/api/integrations/slack/messages?channelId=C123" "GET"
test_endpoint "Slack Send Message" "$FRONTEND_URL/api/integrations/slack/messages/send" "POST" '{"channel":"C123","text":"test"}'
test_endpoint "Slack Users" "$FRONTEND_URL/api/integrations/slack/users?userId=U123" "GET"
echo ""

echo "=== HubSpot Integration (5 endpoints) ==="
test_endpoint "HubSpot Contacts" "$FRONTEND_URL/api/integrations/hubspot/contacts" "GET"
test_endpoint "HubSpot Companies" "$FRONTEND_URL/api/integrations/hubspot/companies" "GET"
test_endpoint "HubSpot Analytics" "$BACKEND_URL/api/hubspot/analytics" "GET"
test_endpoint "HubSpot AI Predictions" "$BACKEND_URL/api/hubspot/ai/predictions" "GET"
test_endpoint "HubSpot AI Analyze Lead" "$BACKEND_URL/api/hubspot/ai/analyze-lead" "POST" '{"contact_id":"test123"}'
echo ""

echo "=== Gmail Integration (2 endpoints) ==="
test_endpoint "Gmail Authorize" "$FRONTEND_URL/api/integrations/gmail/authorize" "GET"
test_endpoint "Gmail Status" "$FRONTEND_URL/api/integrations/gmail/status" "GET"
echo ""

echo "=== Profile Endpoints (4 integrations) ==="
test_endpoint "Salesforce Profile" "$FRONTEND_URL/api/integrations/salesforce/profile" "GET"
test_endpoint "Asana Profile" "$FRONTEND_URL/api/integrations/asana/profile" "GET"
test_endpoint "Figma Profile" "$FRONTEND_URL/api/integrations/figma/profile" "GET"
test_endpoint "Discord Profile" "$FRONTEND_URL/api/integrations/discord/profile" "GET"
echo ""

echo "=================================="
echo "Test Results"
echo "=================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo "Total: $((PASSED + FAILED))"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed. Please check the output above.${NC}"
    exit 1
fi
