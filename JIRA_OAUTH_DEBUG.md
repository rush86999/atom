# 🔍 Jira OAuth Debugging Guide

## **🚨 QUICK TROUBLESHOOTING**

### **Issue 1: "Client ID Missing" Error**
```bash
❌ JIRA_CLIENT_ID not configured
```

**🔧 Solution:**
1. Go to: https://developer.atlassian.com/console/myapps/
2. Select your OAuth app
3. Copy the **Client ID**
4. Add to your `.env` file:
   ```bash
   # For browser (Next.js)
   NEXT_PUBLIC_JIRA_CLIENT_ID=your_client_id_here
   
   # For server-side
   JIRA_CLIENT_ID=your_client_id_here
   ```

---

### **Issue 2: "Cannot connect to Jira server" Error**
```bash
❌ Cannot connect to Jira server: https://your-domain.atlassian.net
```

**🔧 Solutions:**
1. **Check Server URL:**
   ```bash
   # Correct format for Jira Cloud
   JIRA_SERVER_URL=https://your-domain.atlassian.net
   
   # Correct format for Jira Server
   JIRA_SERVER_URL=https://your-jira-server.com
   ```

2. **Test Connectivity:**
   ```bash
   curl -I "https://your-domain.atlassian.net/rest/api/3/serverInfo"
   ```

3. **Check Network/Firewall:**
   - Ensure port 443 (HTTPS) is open
   - Check if corporate firewall blocks Atlassian domains
   - Verify DNS resolution

---

### **Issue 3: "Token exchange failed" Error**
```bash
❌ Token exchange failed: 400 - {"error":"invalid_client"}
```

**🔧 Solutions:**
1. **Check Client Secret:**
   ```bash
   # Must be configured on server-side only
   JIRA_CLIENT_SECRET=your_client_secret_here
   ```

2. **Verify Redirect URI:**
   ```bash
   # Must EXACTLY match your Atlassian app configuration
   JIRA_REDIRECT_URI=https://your-domain.com/oauth/jira/callback
   ```

3. **Check App Status:**
   - Ensure app is "Active" in Atlassian Developer Console
   - Verify all scopes are granted
   - Check if app needs re-authorization

---

## **🛠️ COMPLETE DEBUGGING WORKFLOW**

### **Step 1: Use the Debug Tools**
```tsx
// Import and use the debug components
import { JiraOAuthDebugger, JiraOAuthTestPage } from './debug/JiraOAuth';

// Add to your app
<JiraOAuthTestPage />
```

### **Step 2: Run Diagnostic Tests**
```bash
# Using the provided test script
./debug-jira-oauth.sh

# Or manually check each component:
curl -I "$JIRA_SERVER_URL/rest/api/3/serverInfo"
echo "Client ID: $JIRA_CLIENT_ID"
echo "Redirect URI: $JIRA_REDIRECT_URI"
```

### **Step 3: Check Environment Variables**
```bash
# Show all Jira-related environment variables
env | grep JIRA
```

**Expected output:**
```bash
JIRA_CLIENT_ID=your_client_id
JIRA_CLIENT_SECRET=your_client_secret
JIRA_SERVER_URL=https://your-domain.atlassian.net
JIRA_REDIRECT_URI=https://your-domain.com/oauth/jira/callback
```

---

## **🔧 ENVIRONMENT SETUP GUIDE**

### **For Development (Local)**
```bash
# .env.local
JIRA_CLIENT_ID=your_jira_client_id
JIRA_CLIENT_SECRET=your_jira_client_secret
JIRA_SERVER_URL=https://your-domain.atlassian.net
JIRA_REDIRECT_URI=http://localhost:3000/oauth/jira/callback
NEXT_PUBLIC_JIRA_CLIENT_ID=your_jira_client_id
NEXT_PUBLIC_JIRA_SERVER_URL=https://your-domain.atlassian.net
NEXT_PUBLIC_JIRA_REDIRECT_URI=http://localhost:3000/oauth/jira/callback
```

### **For Production**
```bash
# .env (server)
JIRA_CLIENT_ID=your_jira_client_id
JIRA_CLIENT_SECRET=your_jira_client_secret
JIRA_SERVER_URL=https://your-domain.atlassian.net
JIRA_REDIRECT_URI=https://your-domain.com/oauth/jira/callback

# .env.local (client)
NEXT_PUBLIC_JIRA_CLIENT_ID=your_jira_client_id
NEXT_PUBLIC_JIRA_SERVER_URL=https://your-domain.atlassian.net
NEXT_PUBLIC_JIRA_REDIRECT_URI=https://your-domain.com/oauth/jira/callback
```

---

## **🧪 TESTING PROCEDURES**

### **1. Manual OAuth Test**
```bash
# Build the authorization URL
echo "https://auth.atlassian.com/authorize?client_id=$JIRA_CLIENT_ID&redirect_uri=$JIRA_REDIRECT_URI&response_type=code&scope=read:jira-work"

# Visit this URL in your browser
# Complete authorization
# Check that you're redirected with a code parameter
```

### **2. Server Connectivity Test**
```bash
# Test Jira API endpoints
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     "https://your-domain.atlassian.net/rest/api/3/myself"

# Test with your specific server
curl -I "$JIRA_SERVER_URL/rest/api/3/serverInfo"
```

### **3. Token Exchange Test**
```bash
# Simulate token exchange
curl -X POST "https://auth.atlassian.com/oauth/token" \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "authorization_code",
    "client_id": "'"$JIRA_CLIENT_ID"'",
    "client_secret": "'"$JIRA_CLIENT_SECRET"'",
    "code": "YOUR_AUTH_CODE",
    "redirect_uri": "'"$JIRA_REDIRECT_URI"'"
  }'
```

---

## **🐛 COMMON ERROR CODES**

| Error Code | Description | Solution |
|-------------|-------------|-----------|
| `invalid_client` | Client ID/secret incorrect | Check credentials, verify app is active |
| `invalid_grant` | Authorization code invalid/expired | Re-authorize, check code parameter |
| `redirect_uri_mismatch` | Redirect URI doesn't match | Ensure exact match with app configuration |
| `access_denied` | User denied access | User must grant permissions, check scopes |
| `server_error` | Atlassian server error | Retry, check Atlassian status page |
| `temporarily_unavailable` | Service temporarily unavailable | Wait and retry, check status |

---

## **🔍 DEBUG LOGGING**

### **Enable Debug Mode**
```bash
# Add to environment
JIRA_DEBUG_MODE=true
JIRA_LOG_LEVEL=debug

# In your component
const debugLog = process.env.JIRA_DEBUG_MODE === 'true' ? console.log : () => {};
```

### **Key Log Points**
1. **Configuration Loading**
2. **OAuth URL Construction**
3. **Authorization Code Receipt**
4. **Token Exchange Request**
5. **API Access with Token**

### **Sample Debug Output**
```
[JIRA-OAUTH] 📝 Loading configuration...
[JIRA-OAUTH] ✅ Client ID: ***configured***
[JIRA-OAUTH] ✅ Server URL: https://your-domain.atlassian.net
[JIRA-OAUTH] 🔗 Building OAuth URL...
[JIRA-OAUTH] ✅ OAuth URL: https://auth.atlassian.com/authorize?...
[JIRA-OAUTH] 📩 Received authorization code: ***12 chars***
[JIRA-OAUTH] 🔄 Exchanging code for token...
[JIRA-OAUTH] ✅ Token received, expires in 3600s
[JIRA-OAUTH] 🌐 Testing API access...
[JIRA-OAUTH] ✅ API access successful, retrieved 5 projects
```

---

## **🆘 GETTING HELP**

### **Self-Service Debugging**
1. **Use the Debug Component**: `<JiraOAuthDebugger />`
2. **Run the Test Script**: `./debug-jira-oauth.sh`
3. **Check Environment**: Run `env | grep JIRA`
4. **Review Logs**: Look for `[JIRA-OAUTH]` prefixed messages

### **If Issues Persist**
1. **Collect Debug Information**:
   ```bash
   # Save environment (remove secrets)
   env | grep JIRA | sed 's/=.*/=***REDACTED**/' > jira-debug-env.txt
   
   # Save test results
   ./debug-jira-oauth.sh > jira-debug-test.txt 2>&1
   
   # Save browser console errors (screenshot)
   ```
2. **Check Atlassian Status**:
   - https://status.atlassian.com/
   - https://developer.atlassian.com/platform/status/

3. **Review Atlassian Documentation**:
   - https://developer.atlassian.com/cloud/jira/platform/oauth-2-authorization-code-grants-3-lo-for-2-lo/
   - https://developer.atlassian.com/cloud/jira/platform/jira-rest-api/

---

## **🎯 SUCCESS INDICATORS**

### **✅ Successful OAuth Flow:**
1. **Configuration**: All environment variables set correctly
2. **Connectivity**: Jira server accessible
3. **Authorization**: User completes OAuth flow
4. **Token Exchange**: Access token received successfully
5. **API Access**: Can retrieve user data and projects

### **🎊 Final Confirmation:**
```bash
# Test complete integration
curl -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
     "$JIRA_SERVER_URL/rest/api/3/myself"

# Should return:
{
  "accountId": "...",
  "accountType": "atlassian",
  "active": true,
  "displayName": "Your Name",
  ...
}
```

---

## **📋 QUICK CHECKLIST**

### **Pre-Deployment Checklist:**
- [ ] Jira OAuth app created and active
- [ ] Client ID configured in environment
- [ ] Client Secret configured (server-side only)
- [ ] Server URL correctly formatted
- [ ] Redirect URI matches app configuration
- [ ] Required scopes granted
- [ ] HTTPS used for production
- [ ] CORS configured if needed
- [ ] Network connectivity verified
- [ ] Error handling implemented

### **Test Scenarios:**
- [ ] Normal OAuth flow
- [ ] User denies access
- [ ] Invalid credentials
- [ ] Network timeout
- [ ] CORS issues
- [ ] Token refresh
- [ ] API rate limiting

---

## **🚀 READY TO USE**

Once all tests pass:
1. ✅ Your Jira OAuth integration is working
2. ✅ ATOM agent can connect to Jira
3. ✅ Data ingestion pipeline is ready
4. ✅ Real-time sync capabilities available

**🎉 Congratulations! Your Jira integration is now fully operational!**