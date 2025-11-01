# 🔐 REAL CREDENTIALS SETUP GUIDE

## 📋 Current Status
- ✅ **7 Services with Real Credentials**: Gmail, Slack, Trello, Asana, Notion, Dropbox, Google Drive
- 🔧 **3 Services Needing Real Credentials**: Outlook, Teams, GitHub

---

## 🎯 Services Needing Real Credentials

### 1. Microsoft Outlook/Office365 OAuth
**Status**: ❌ Needs real credentials
**Impact**: Email access, calendar integration, contact management

#### Setup Steps:
1. **Go to Microsoft Azure Portal**: https://portal.azure.com
2. **Navigate to**: Azure Active Directory → App registrations
3. **Click**: "New registration"
4. **Fill in**:
   - **Name**: "ATOM AI Assistant"
   - **Supported account types**: "Accounts in any organizational directory and personal Microsoft accounts"
   - **Redirect URI**: Web → `http://localhost:5058/api/auth/outlook/callback`
5. **Click**: "Register"
6. **Copy credentials**:
   - **Application (client) ID** → Add to `.env` as `OUTLOOK_CLIENT_ID`
   - **Directory (tenant) ID** → Add to `.env` as `OUTLOOK_TENANT_ID`
7. **Create client secret**:
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Add description → Expiration: 12 months
   - Copy the **Value** → Add to `.env` as `OUTLOOK_CLIENT_SECRET`
8. **Add API permissions**:
   - Go to "API permissions"
   - Click "Add a permission" → "Microsoft Graph"
   - Add: `Mail.Read`, `Mail.Send`, `User.Read`, `Calendars.ReadWrite`
   - Grant admin consent if needed

#### Environment Variables:
```bash
OUTLOOK_CLIENT_ID=your-microsoft-app-client-id
OUTLOOK_CLIENT_SECRET=your-microsoft-app-client-secret
OUTLOOK_TENANT_ID=common
```

---

### 2. Microsoft Teams OAuth
**Status**: ❌ Needs real credentials
**Impact**: Teams messaging, channels, chat integration

#### Setup Steps:
1. **Use existing Microsoft App**: OR create new app for Teams
2. **If using existing app**: Add Teams permissions
3. **If creating new app**: Follow Outlook steps above
4. **Add Teams-specific permissions**:
   - Go to "API permissions"
   - Add: `Chat.ReadWrite`, `ChannelMessage.ReadWrite.All`, `Team.ReadBasic.All`
   - Grant admin consent
5. **Same redirect URI**: `http://localhost:5058/api/auth/teams/callback`

#### Environment Variables:
```bash
TEAMS_CLIENT_ID=your-microsoft-app-client-id
TEAMS_CLIENT_SECRET=your-microsoft-app-client-secret
TEAMS_TENANT_ID=common
```

---

### 3. GitHub OAuth
**Status**: ❌ Needs real credentials
**Impact**: Repository access, issues, pull requests, commits

#### Setup Steps:
1. **Go to GitHub**: https://github.com/settings/applications/new
2. **Fill in**:
   - **Application name**: "ATOM AI Assistant"
   - **Homepage URL**: `http://localhost:3000`
   - **Authorization callback URL**: `http://localhost:5058/api/auth/github/callback`
3. **Click**: "Register application"
4. **Copy credentials**:
   - **Client ID** → Add to `.env` as `GITHUB_CLIENT_ID`
   - **Generate Client Secret** → Add to `.env` as `GITHUB_CLIENT_SECRET`
5. **Default permissions**: Read access to public repositories
   - For more access, request additional scopes in OAuth flow

#### Environment Variables:
```bash
GITHUB_CLIENT_ID=your-github-oauth-client-id
GITHUB_CLIENT_SECRET=your-github-oauth-client-secret
```

---

## 🔄 IMPLEMENTATION STEPS

### Step 1: Add Credentials to .env
```bash
# Open .env file in project root
nano .env

# Add these lines (replace with your actual values)
OUTLOOK_CLIENT_ID=your-microsoft-app-client-id
OUTLOOK_CLIENT_SECRET=your-microsoft-app-client-secret
OUTLOOK_TENANT_ID=common

TEAMS_CLIENT_ID=your-microsoft-app-client-id
TEAMS_CLIENT_SECRET=your-microsoft-app-client-secret
TEAMS_TENANT_ID=common

GITHUB_CLIENT_ID=your-github-oauth-client-id
GITHUB_CLIENT_SECRET=your-github-oauth-client-secret
```

### Step 2: Update Production Environment
```bash
# Copy to production environment
cp .env .env.production

# Update production redirect URIs for production domain
# From: http://localhost:5058/api/auth/{service}/callback
# To: https://your-domain.com/api/auth/{service}/callback
```

### Step 3: Restart Services
```bash
# Stop current OAuth server
pkill -f "python.*start_complete_oauth_server"

# Restart with new credentials
python start_complete_oauth_server.py

# Test updated credentials
python test_oauth_endpoints.py
```

### Step 4: Verify All Services
```bash
# Test authorization endpoints
python -c "
import requests
services = ['outlook', 'teams', 'github']
for service in services:
    try:
        response = requests.get(f'http://localhost:5058/api/auth/{service}/authorize?user_id=test')
        data = response.json()
        print(f'{service}: {data.get(\"ok\", False)} - {data.get(\"credentials\", \"unknown\")}')
    except:
        print(f'{service}: ERROR')
"
```

---

## ⚠️ IMPORTANT SECURITY NOTES

### 1. Redirect URI Security
- **Development**: `http://localhost:5058/api/auth/{service}/callback`
- **Production**: `https://your-domain.com/api/auth/{service}/callback`
- **NEVER use**: `http://your-domain.com` in production (HTTPS required)

### 2. Client Secret Management
- ✅ Store in environment variables only
- ✅ Rotate secrets every 90 days
- ✅ Use separate secrets for dev/prod
- ❌ Never commit secrets to Git
- ❌ Never share credentials publicly

### 3. OAuth Scopes
- ✅ Request minimum necessary permissions
- ✅ Document each scope's purpose
- ✅ Get user consent for sensitive operations
- ❌ Don't request excessive permissions

### 4. Production Deployment
- ✅ Use HTTPS everywhere
- ✅ Set proper CORS origins
- ✅ Configure rate limiting
- ✅ Enable security headers

---

## 🚀 Expected Outcome After Setup

### OAuth System Status:
- ✅ **Gmail**: Working with real credentials
- ✅ **Slack**: Working with real credentials  
- ✅ **Trello**: Working with real credentials
- ✅ **Asana**: Working with real credentials
- ✅ **Notion**: Working with real credentials
- ✅ **Dropbox**: Working with real credentials
- ✅ **Google Drive**: Working with real credentials
- ✅ **Outlook**: Working with real credentials (after setup)
- ✅ **Teams**: Working with real credentials (after setup)
- ✅ **GitHub**: Working with real credentials (after setup)

### Production Readiness:
- 🎯 **OAuth System**: 10/10 services operational (100%)
- 🎯 **Authorization Endpoints**: All working
- 🎯 **Status Endpoints**: All working
- 🎯 **Security**: CSRF protection, token encryption
- 🎯 **Integration**: All external services connected

---

## 🆘 TROUBLESHOOTING

### Common Issues:

#### Microsoft OAuth Errors:
- **AADSTS700016**: Application not found → Check client ID
- **AADSTS50194**: Invalid redirect URI → Update in Azure portal
- **AADSTS65001**: User not found → Check tenant ID

#### GitHub OAuth Errors:
- **redirect_uri_mismatch**: Update callback URL in GitHub
- **client_id_invalid**: Check client ID in GitHub app settings
- **bad_client_secret**: Regenerate client secret

#### General Issues:
- **Port conflicts**: Kill existing processes on port 5058
- **Environment variables**: Verify .env file format
- **CORS issues**: Check frontend-backend communication

### Debug Commands:
```bash
# Check OAuth status
curl "http://localhost:5058/api/auth/oauth-status?user_id=test"

# Check specific service status
curl "http://localhost:5058/api/auth/github/status?user_id=test"

# Test authorization endpoint
curl "http://localhost:5058/api/auth/github/authorize?user_id=test"

# Check server logs
tail -f complete_oauth_server.log
```

---

## 📞 SUPPORT & RESOURCES

### Documentation:
- Microsoft OAuth: https://docs.microsoft.com/en-us/azure/active-directory/develop/
- GitHub OAuth: https://docs.github.com/en/developers/apps/building-oauth-apps/
- OAuth 2.0 Guide: https://oauth.net/2/

### OAuth Test Tools:
- https://oauthdebugger.com/
- https://requestbin.com/ (for callback testing)
- https://jwt.io/ (for token debugging)

---

## ✅ SUCCESS CHECKLIST

After completing credential setup:

- [ ] Microsoft Outlook OAuth configured with real credentials
- [ ] Microsoft Teams OAuth configured with real permissions  
- [ ] GitHub OAuth app created with proper callback URL
- [ ] All 3 services added to .env file with real values
- [ ] OAuth server restarted with new credentials
- [ ] All authorization endpoints return success (200)
- [ ] All status endpoints show "connected" status
- [ ] OAuth system shows 10/10 services operational
- [ ] Production environment configured with HTTPS URLs
- [ ] Security audit completed for all credentials

**Once complete, ATOM OAuth authentication system will be 100% production-ready!** 🎉