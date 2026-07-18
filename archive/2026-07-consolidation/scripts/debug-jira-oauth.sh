#!/bin/bash

# ATOM Jira OAuth Test Script
# Comprehensive OAuth debugging and testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Emoji for output
ROCKET="🚀"
CHECK="✅"
ERROR="❌"
WARNING="⚠️"
INFO="ℹ️"
DEBUG="🔍"

echo -e "${BLUE}${ROCKET} ATOM Jira OAuth Debug Tool${NC}"
echo -e "${BLUE}===================================${NC}"
echo

# Function to check environment variable
check_env() {
    local var_name="$1"
    local var_value="${!var_name}"
    
    if [ -z "$var_value" ]; then
        echo -e "${RED}${ERROR} $var_name not configured${NC}"
        return 1
    else
        echo -e "${GREEN}${CHECK} $var_name configured${NC}"
        return 0
    fi
}

# Function to test URL connectivity
test_url() {
    local url="$1"
    local description="$2"
    
    echo -e "${INFO} Testing $description..."
    
    if curl -s --max-time 10 -o /dev/null -w "%{http_code}" "$url" | grep -q "200"; then
        echo -e "${GREEN}${CHECK} $description accessible${NC}"
        return 0
    else
        echo -e "${RED}${ERROR} $description not accessible${NC}"
        return 1
    fi
}

# Function to validate URL format
validate_url() {
    local url="$1"
    local name="$2"
    
    if [[ "$url" =~ ^https?:// ]] && [[ "$url" =~ [a-zA-Z0-9.-]+\.[a-zA-Z]{2,} ]]; then
        echo -e "${GREEN}${CHECK} $name format valid${NC}"
        return 0
    else
        echo -e "${RED}${ERROR} $name format invalid: $url${NC}"
        return 1
    fi
}

echo -e "${BLUE}${DEBUG} Step 1: Environment Configuration${NC}"
echo "-------------------------------------------"

# Check critical environment variables
CLIENT_ID_OK=false
CLIENT_SECRET_OK=false
SERVER_URL_OK=false
REDIRECT_URI_OK=false

# Check for both browser and server environment variables
if check_env "JIRA_CLIENT_ID" || check_env "NEXT_PUBLIC_JIRA_CLIENT_ID"; then
    CLIENT_ID_OK=true
fi

if check_env "JIRA_CLIENT_SECRET"; then
    CLIENT_SECRET_OK=true
fi

if check_env "JIRA_SERVER_URL" || check_env "NEXT_PUBLIC_JIRA_SERVER_URL"; then
    SERVER_URL_OK=true
fi

if check_env "JIRA_REDIRECT_URI" || check_env "NEXT_PUBLIC_JIRA_REDIRECT_URI"; then
    REDIRECT_URI_OK=true
fi

echo
echo -e "${BLUE}${DEBUG} Step 2: URL Format Validation${NC}"
echo "-----------------------------------------"

# Get actual values
CLIENT_ID="${JIRA_CLIENT_ID:-$NEXT_PUBLIC_JIRA_CLIENT_ID}"
CLIENT_SECRET="${JIRA_CLIENT_SECRET}"
SERVER_URL="${JIRA_SERVER_URL:-$NEXT_PUBLIC_JIRA_SERVER_URL}"
REDIRECT_URI="${JIRA_REDIRECT_URI:-$NEXT_PUBLIC_JIRA_REDIRECT_URI}"

# Validate URL formats
if [ "$SERVER_URL_OK" = true ]; then
    validate_url "$SERVER_URL" "Server URL"
fi

if [ "$REDIRECT_URI_OK" = true ]; then
    validate_url "$REDIRECT_URI" "Redirect URI"
fi

echo
echo -e "${BLUE}${DEBUG} Step 3: Server Connectivity${NC}"
echo "-------------------------------------"

# Test server connectivity if URL is valid
if [ "$SERVER_URL_OK" = true ]; then
    # Test multiple endpoints
    test_url "$SERVER_URL/rest/api/3/serverInfo" "Jira Server Info API"
    
    # Extract domain for CORS test
    DOMAIN=$(echo "$SERVER_URL" | sed -n 's|https\?://\([^/]*\).*|\1|p')
    test_url "https://auth.atlassian.com" "Atlassian OAuth Server"
else
    echo -e "${WARNING}${WARNING} Skipping server connectivity test (URL not configured)${NC}"
fi

echo
echo -e "${BLUE}${DEBUG} Step 4: OAuth Configuration${NC}"
echo "-------------------------------------"

if [ "$CLIENT_ID_OK" = true ] && [ "$REDIRECT_URI_OK" = true ]; then
    # Build OAuth URL
    OAUTH_URL="https://auth.atlassian.com/authorize?client_id=$CLIENT_ID&redirect_uri=$(echo "$REDIRECT_URI" | sed 's/&/%26/g' | sed 's/=/%3D/g')&response_type=code&scope=read:jira-work&state=$(date +%s)"
    
    echo -e "${INFO} OAuth Authorization URL:"
    echo "$OAUTH_URL"
    echo
    
    # Test OAuth URL is well-formed
    if [[ "$OAUTH_URL" =~ ^https://auth\.atlassian\.com/authorize\? ]]; then
        echo -e "${GREEN}${CHECK} OAuth URL format valid${NC}"
    else
        echo -e "${RED}${ERROR} OAuth URL format invalid${NC}"
    fi
else
    echo -e "${WARNING}${WARNING} Skipping OAuth URL generation (missing configuration)${NC}"
fi

echo
echo -e "${BLUE}${DEBUG} Step 5: Browser/CORS Test${NC}"
echo "----------------------------------"

if [ "$SERVER_URL_OK" = true ]; then
    echo -e "${INFO} CORS Test Instructions:"
    echo "1. Open your browser developer tools"
    echo "2. Run the following JavaScript:"
    echo
    echo "fetch('$SERVER_URL/rest/api/3/serverInfo', {"
    echo "  method: 'GET',"
    echo "  headers: { 'Accept': 'application/json' }"
    echo "}).then(r => r.json()).then(console.log).catch(console.error);"
    echo
    echo "3. Check console for CORS errors"
    echo
fi

echo
echo -e "${BLUE}${DEBUG} Step 6: Manual OAuth Test${NC}"
echo "-----------------------------------"

if [ "$CLIENT_ID_OK" = true ] && [ "$REDIRECT_URI_OK" = true ]; then
    echo -e "${INFO} Manual OAuth Test:"
    echo "1. Copy this URL to your browser:"
    if [ "$CLIENT_ID_OK" = true ]; then
        echo "$OAUTH_URL"
    fi
    echo
    echo "2. Complete the authorization in Jira"
    echo "3. You should be redirected to: $REDIRECT_URI"
    echo "4. Check URL parameters - you should see '?code=...' on success"
    echo "5. On error, check for '?error=...' parameter"
    echo
else
    echo -e "${ERROR}${ERROR} Cannot generate OAuth test URL (missing configuration)${NC}"
fi

echo
echo -e "${BLUE}${DEBUG} Step 7: Token Exchange Test${NC}"
echo "------------------------------------"

if [ "$CLIENT_ID_OK" = true ] && [ "$CLIENT_SECRET_OK" = true ]; then
    echo -e "${INFO} Token Exchange Command:"
    echo "curl -X POST 'https://auth.atlassian.com/oauth/token' \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{"
    echo "    \"grant_type\": \"authorization_code\","
    echo "    \"client_id\": \"$CLIENT_ID\","
    echo "    \"client_secret\": \"$CLIENT_SECRET\","
    echo "    \"code\": \"YOUR_AUTH_CODE_HERE\","
    echo "    \"redirect_uri\": \"$REDIRECT_URI\""
    echo "  }'"
    echo
    echo -e "${INFO} Replace YOUR_AUTH_CODE_HERE with the code from OAuth callback"
    echo
else
    echo -e "${WARNING}${WARNING} Cannot provide token exchange command (missing credentials)${NC}"
fi

echo
echo -e "${BLUE}${DEBUG} Step 8: Configuration Summary${NC}"
echo "-------------------------------------"

echo -e "${INFO} Configuration Status:"
echo -e "  Client ID: $([ "$CLIENT_ID_OK" = true ] && echo "${GREEN}${CHECK} Configured${NC}" || echo "${RED}${ERROR} Missing${NC}")"
echo -e "  Client Secret: $([ "$CLIENT_SECRET_OK" = true ] && echo "${GREEN}${CHECK} Configured${NC}" || echo "${RED}${ERROR} Missing${NC}")"
echo -e "  Server URL: $([ "$SERVER_URL_OK" = true ] && echo "${GREEN}${CHECK} Configured${NC}" || echo "${RED}${ERROR} Missing${NC}")"
echo -e "  Redirect URI: $([ "$REDIRECT_URI_OK" = true ] && echo "${GREEN}${CHECK} Configured${NC}" || echo "${RED}${ERROR} Missing${NC}")"

echo
echo -e "${INFO} Configuration Values (with secrets redacted):"
if [ -n "$CLIENT_ID" ]; then
    echo -e "  Client ID: ${BLUE}${CLIENT_ID:0:10}...${NC}"
fi
if [ -n "$SERVER_URL" ]; then
    echo -e "  Server URL: ${BLUE}$SERVER_URL${NC}"
fi
if [ -n "$REDIRECT_URI" ]; then
    echo -e "  Redirect URI: ${BLUE}$REDIRECT_URI${NC}"
fi
if [ -n "$CLIENT_SECRET" ]; then
    echo -e "  Client Secret: ${BLUE}***CONFIGURED***${NC}"
fi

echo
echo -e "${BLUE}${DEBUG} Step 9: Troubleshooting Suggestions${NC}"
echo "------------------------------------------"

if [ "$CLIENT_ID_OK" = false ] || [ "$CLIENT_SECRET_OK" = false ] || [ "$SERVER_URL_OK" = false ] || [ "$REDIRECT_URI_OK" = false ]; then
    echo -e "${WARNING}${WARNING} Issues Found - Fix Required:${NC}"
    echo
    
    if [ "$CLIENT_ID_OK" = false ]; then
        echo "1. Get Client ID from: https://developer.atlassian.com/console/myapps/"
        echo "2. Add to environment: JIRA_CLIENT_ID=your_client_id"
        echo "3. For browser: NEXT_PUBLIC_JIRA_CLIENT_ID=your_client_id"
        echo
    fi
    
    if [ "$CLIENT_SECRET_OK" = false ]; then
        echo "1. Get Client Secret from Atlassian Developer Console"
        echo "2. Add to server environment: JIRA_CLIENT_SECRET=your_client_secret"
        echo "3. Never expose client secret to browser"
        echo
    fi
    
    if [ "$SERVER_URL_OK" = false ]; then
        echo "1. Determine your Jira type:"
        echo "   - Jira Cloud: https://your-domain.atlassian.net"
        echo "   - Jira Server: https://your-jira-server.com"
        echo "2. Add to environment: JIRA_SERVER_URL=https://your-domain.atlassian.net"
        echo
    fi
    
    if [ "$REDIRECT_URI_OK" = false ]; then
        echo "1. Set redirect URI: JIRA_REDIRECT_URI=https://localhost/oauth/jira/callback"
        echo "2. For local dev: http://localhost:3000/oauth/jira/callback"
        echo "3. Ensure it matches Atlassian app configuration exactly"
        echo
    fi
else
    echo -e "${GREEN}${CHECK} All critical configuration is valid${NC}"
    echo
    echo -e "${INFO} Next Steps:"
    echo "1. Test OAuth flow manually using the URL above"
    echo "2. Check browser console for any errors"
    echo "3. Verify redirect callback works correctly"
    echo "4. Test token exchange with your auth code"
    echo "5. Use the ATOM Jira Debugger component for detailed testing"
fi

echo
echo -e "${BLUE}${DEBUG} Step 10: Resources${NC}"
echo "------------------------"

echo -e "${INFO} Helpful Links:"
echo "• Atlassian Developer Console: https://developer.atlassian.com/console/myapps/"
echo "• Jira OAuth Documentation: https://developer.atlassian.com/cloud/jira/platform/oauth-2-authorization-code-grants-3-lo-for-2-lo/"
echo "• Atlassian Status: https://status.atlassian.com/"
echo "• ATOM Jira Setup: ./JIRA_SETUP.md"
echo "• ATOM Jira Debug: ./JIRA_OAUTH_DEBUG.md"

echo
echo -e "${BLUE}${ROCKET} Debug Script Complete${NC}"
echo -e "${BLUE}============================${NC}"

# Exit with appropriate code
if [ "$CLIENT_ID_OK" = true ] && [ "$CLIENT_SECRET_OK" = true ] && [ "$SERVER_URL_OK" = true ] && [ "$REDIRECT_URI_OK" = true ]; then
    echo -e "${GREEN}${CHECK} All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}${ERROR} Some tests failed. Please fix the issues above.${NC}"
    exit 1
fi