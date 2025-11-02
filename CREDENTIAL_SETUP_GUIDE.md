# 🔐 COMPREHENSIVE CREDENTIAL GUIDE FOR 3RD PARTY INTEGRATIONS

## 📋 REQUIRED THIRD-PARTY CREDENTIALS

### 1. 🐙 GITHUB INTEGRATION

#### Required Credentials:
- **GitHub Client ID**: Your OAuth application client ID
- **GitHub Client Secret**: Your OAuth application client secret
- **GitHub Personal Access Token**: For API access (optional, for testing)

#### How to Get GitHub Credentials:

1. **Create GitHub OAuth App:**
   - Go to: https://github.com/settings/applications/new
   - Application name: `ATOM Enterprise System`
   - Homepage URL: `http://localhost:3000`
   - Authorization callback URL: `http://localhost:3000/oauth/github/callback`
   - Click "Register application"

2. **Get Your Credentials:**
   - **Client ID**: Found on the app page
   - **Client Secret**: Click "Generate a new client secret"

3. **Optional: Generate Personal Access Token:**
   - Go to: https://github.com/settings/tokens
   - Click "Generate new token (classic)"
   - Scopes: `repo`, `user:email`, `admin:repo_hook`
   - Click "Generate token"
   - Copy the token (save it securely)

#### Environment Variables:
```bash
# Add to your .env file:
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here
GITHUB_ACCESS_TOKEN=your_github_personal_access_token_here
GITHUB_REDIRECT_URI=http://localhost:3000/oauth/github/callback
```

---

### 2. 🌍 GOOGLE INTEGRATION

#### Required Credentials:
- **Google Client ID**: Your OAuth 2.0 Client ID
- **Google Client Secret**: Your OAuth 2.0 Client Secret
- **Google Refresh Token**: For persistent access (generated after first auth)

#### How to Get Google Credentials:

1. **Create Google Cloud Project:**
   - Go to: https://console.cloud.google.com/
   - Click "Select a project" → "NEW PROJECT"
   - Project name: `ATOM Enterprise System`
   - Click "Create"

2. **Enable Required APIs:**
   - Go to: https://console.cloud.google.com/apis/dashboard
   - Click "+ ENABLE APIS AND SERVICES"
   - Search and enable:
     - **Google Calendar API**
     - **Google Drive API**
     - **Gmail API**

3. **Create OAuth 2.0 Credentials:**
   - Go to: https://console.cloud.google.com/apis/credentials
   - Click "+ CREATE CREDENTIALS" → "OAuth 2.0 Client IDs"
   - Application type: "Web application"
   - Name: `ATOM Enterprise System`
   - Authorized JavaScript origins: `http://localhost:3000`
   - Authorized redirect URIs: `http://localhost:3000/oauth/google/callback`
   - Click "Create"

4. **Get Your Credentials:**
   - **Client ID**: Displayed on the credentials page
   - **Client Secret**: Click the eye icon to view and copy

#### Environment Variables:
```bash
# Add to your .env file:
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_ACCESS_TOKEN=your_google_access_token_here
GOOGLE_REFRESH_TOKEN=your_google_refresh_token_here
GOOGLE_REDIRECT_URI=http://localhost:3000/oauth/google/callback
```

---

### 3. 💬 SLACK INTEGRATION

#### Required Credentials:
- **Slack Client ID**: Your Slack app Client ID
- **Slack Client Secret**: Your Slack app Client Secret
- **Slack Bot Token**: For bot API access (xoxb-...)
- **Slack Signing Secret**: For request verification (optional)

#### How to Get Slack Credentials:

1. **Create Slack App:**
   - Go to: https://api.slack.com/apps
   - Click "Create New App" → "From scratch"
   - App name: `ATOM Enterprise System`
   - Development workspace: Choose your workspace
   - Click "Create App"

2. **Configure OAuth & Permissions:**
   - Go to "OAuth & Permissions" in the sidebar
   - Scroll to "Redirect URLs"
   - Add: `http://localhost:3000/oauth/slack/callback`
   - Scroll to "Scopes"
   - Click "Add an OAuth Scope"
   - Add Bot Token Scopes:
     - `channels:read` - Read channels
     - `chat:read` - Read messages
     - `users:read` - Read user info
     - `files:read` - Read files

3. **Install App to Workspace:**
   - Scroll to top of "OAuth & Permissions"
   - Click "Install to Workspace"
   - Review permissions and click "Allow"

4. **Get Your Credentials:**
   - **Client ID**: Found on "OAuth & Permissions" page
   - **Client Secret**: Click "Show" under App Credentials
   - **Bot Token**: Found under "OAuth Tokens for Your Workspace" (starts with `xoxb-`)

#### Environment Variables:
```bash
# Add to your .env file:
SLACK_CLIENT_ID=your_slack_client_id_here
SLACK_CLIENT_SECRET=your_slack_client_secret_here
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token-here
SLACK_REDIRECT_URI=http://localhost:3000/oauth/slack/callback
SLACK_SIGNING_SECRET=your_slack_signing_secret_here
```

---

### 4. 🌐 OUTLOOK/MICROSOFT 365 INTEGRATION

#### Required Credentials:
- **Microsoft App ID**: Your Azure AD application ID
- **Microsoft App Secret**: Your Azure AD client secret
- **Microsoft Tenant ID**: Your Azure AD tenant ID

#### How to Get Microsoft Credentials:

1. **Create Azure AD App:**
   - Go to: https://portal.azure.com/
   - Search "Azure Active Directory" → Click
   - Click "App registrations" → "New registration"
   - Name: `ATOM Enterprise System`
   - Supported account types: "Accounts in any organizational directory"
   - Redirect URI: `http://localhost:3000/oauth/outlook/callback`
   - Click "Register"

2. **Configure API Permissions:**
   - Go to "API permissions"
   - Click "Add a permission" → "Microsoft Graph"
   - Select "Delegated permissions"
   - Add these permissions:
     - `Mail.Read` - Read emails
     - `Calendars.Read` - Read calendars
     - `Files.Read` - Read files
   - Click "Add permissions"

3. **Create Client Secret:**
   - Go to "Certificates & secrets"
   - Click "New client secret"
   - Description: `ATOM Enterprise System`
   - Expiration: Choose duration
   - Click "Add"
   - Immediately copy the secret value (it won't be shown again)

4. **Get Your Credentials:**
   - **Application (client) ID**: Found on app overview page
   - **Directory (tenant) ID**: Found on app overview page
   - **Client Secret**: The secret value you just created

#### Environment Variables:
```bash
# Add to your .env file:
MICROSOFT_CLIENT_ID=your_microsoft_app_id_here
MICROSOFT_CLIENT_SECRET=your_microsoft_app_secret_here
MICROSOFT_TENANT_ID=your_microsoft_tenant_id_here
OUTLOOK_REDIRECT_URI=http://localhost:3000/oauth/outlook/callback
```

---

### 5. 🏢 MICROSOFT TEAMS INTEGRATION

#### Required Credentials:
- **Teams App ID**: Your Teams app ID
- **Teams App Secret**: Your Teams app client secret
- **Teams Tenant ID**: Your Azure AD tenant ID

#### How to Get Teams Credentials:

1. **Teams uses same Azure AD app as Outlook:**
   - Use the same app registration you created for Outlook
   - The credentials are the same
   - Just enable additional Teams permissions

2. **Add Teams Permissions:**
   - Go to your Azure AD app
   - Click "API permissions"
   - Add Microsoft Graph delegated permissions:
     - `Team.ReadBasic.All` - Read teams
     - `Channel.ReadBasic.All` - Read channels
     - `Chat.Read` - Read chats

#### Environment Variables:
```bash
# Same as Microsoft credentials - already configured above
TEAMS_CLIENT_ID=your_microsoft_app_id_here
TEAMS_CLIENT_SECRET=your_microsoft_app_secret_here
TEAMS_TENANT_ID=your_microsoft_tenant_id_here
TEAMS_REDIRECT_URI=http://localhost:3000/oauth/teams/callback
```

---

## 🔧 HOW TO ADD CREDENTIALS MANUALLY

### Step 1: Create Your .env File
```bash
# Navigate to your project root
cd /path/to/atom

# Create .env file
touch .env

# Make it secure (only you can read)
chmod 600 .env
```

### Step 2: Add All Required Credentials
```bash
# Copy and paste this template into your .env file
# Then replace each value with your actual credentials

# ==== APPLICATION SETTINGS ====
FLASK_ENV=development
DEBUG=True
SECRET_KEY=your-own-secret-key-here
PYTHON_API_PORT=8000

# ==== GITHUB INTEGRATION ====
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here
GITHUB_ACCESS_TOKEN=your_github_personal_access_token_here
GITHUB_REDIRECT_URI=http://localhost:3000/oauth/github/callback

# ==== GOOGLE INTEGRATION ====
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here
GOOGLE_ACCESS_TOKEN=your_google_access_token_here
GOOGLE_REFRESH_TOKEN=your_google_refresh_token_here
GOOGLE_REDIRECT_URI=http://localhost:3000/oauth/google/callback

# ==== SLACK INTEGRATION ====
SLACK_CLIENT_ID=your_slack_client_id_here
SLACK_CLIENT_SECRET=your_slack_client_secret_here
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token-here
SLACK_SIGNING_SECRET=your_slack_signing_secret_here
SLACK_REDIRECT_URI=http://localhost:3000/oauth/slack/callback

# ==== MICROSOFT/OUTLOOK INTEGRATION ====
MICROSOFT_CLIENT_ID=your_microsoft_app_id_here
MICROSOFT_CLIENT_SECRET=your_microsoft_app_secret_here
MICROSOFT_TENANT_ID=your_microsoft_tenant_id_here
OUTLOOK_REDIRECT_URI=http://localhost:3000/oauth/outlook/callback

# ==== MICROSOFT TEAMS INTEGRATION ====
TEAMS_CLIENT_ID=your_microsoft_app_id_here
TEAMS_CLIENT_SECRET=your_microsoft_app_secret_here
TEAMS_TENANT_ID=your_microsoft_tenant_id_here
TEAMS_REDIRECT_URI=http://localhost:3000/oauth/teams/callback

# ==== SECURITY SETTINGS ====
ATOM_OAUTH_ENCRYPTION_KEY=your-32-character-encryption-key-here
CSRF_ENABLED=True
```

### Step 3: Test Your Credentials
```bash
# Start your backend
cd backend/python-api-service
python clean_backend.py

# In another terminal, test OAuth endpoints
curl http://localhost:8000/api/oauth/github/url
curl http://localhost:8000/api/oauth/google/url
curl http://localhost:8000/api/oauth/slack/url
```

---

## 🧪 TESTING YOUR INTEGRATIONS

### 1. Test GitHub Integration:
```bash
# Test GitHub OAuth URL generation
curl http://localhost:8000/api/oauth/github/url

# Expected response (should contain GitHub OAuth URL):
{
  "oauth_url": "https://github.com/login/oauth/authorize?client_id=YOUR_ID&...",
  "success": true
}
```

### 2. Test Google Integration:
```bash
# Test Google OAuth URL generation
curl http://localhost:8000/api/oauth/google/url

# Expected response:
{
  "oauth_url": "https://accounts.google.com/oauth/authorize?client_id=YOUR_ID&...",
  "success": true
}
```

### 3. Test Slack Integration:
```bash
# Test Slack OAuth URL generation
curl http://localhost:8000/api/oauth/slack/url

# Expected response:
{
  "oauth_url": "https://slack.com/oauth/v2/authorize?client_id=YOUR_ID&...",
  "success": true
}
```

### 4. Test Real Service Connections:
```bash
# Test real GitHub API connection
curl http://localhost:8000/api/real/github/repositories

# Test real Google API connection
curl http://localhost:8000/api/real/google/calendar

# Test real Slack API connection
curl http://localhost:8000/api/real/slack/channels
```

---

## 🔒 SECURITY BEST PRACTICES

### 1. Keep Your .env File Secure:
- ✅ Never commit .env to version control
- ✅ Set file permissions: `chmod 600 .env`
- ✅ Use strong, unique secrets
- ✅ Rotate credentials regularly

### 2. Production Security:
- ✅ Use production OAuth apps (not development)
- ✅ Use HTTPS redirect URLs in production
- ✅ Implement proper token storage
- ✅ Set up monitoring for API usage

### 3. Credential Management:
- ✅ Store credentials in environment variables
- ✅ Use vault services for production
- ✅ Implement proper encryption
- ✅ Regular security audits

---

## 🚀 NEXT STEPS

### 1. Add Credentials:
- Follow the guides above for each service
- Update your .env file with actual credentials
- Test each integration individually

### 2. Test OAuth Flows:
- Visit your frontend application
- Click "Connect GitHub/Google/Slack"
- Complete OAuth authentication flows
- Verify tokens are stored properly

### 3. Test API Connections:
- Test real service API endpoints
- Verify data retrieval works
- Check error handling and rate limits
- Monitor API usage and performance

### 4. Deploy to Production:
- Create production OAuth applications
- Update redirect URLs to production domain
- Configure production environment variables
- Test production authentication flows

---

## 📞 SUPPORT

If you need help with any of these integrations:

1. **GitHub Issues**: https://github.com/settings/apps
2. **Google Cloud Support**: https://console.cloud.google.com/support
3. **Slack API Support**: https://api.slack.com/support
4. **Microsoft Azure Support**: https://azure.microsoft.com/support

---

## ✅ CHECKLIST

- [ ] Create GitHub OAuth app and get credentials
- [ ] Create Google Cloud project and get credentials
- [ ] Create Slack app and get credentials
- [ ] Create Azure AD app for Outlook/Teams and get credentials
- [ ] Update .env file with all credentials
- [ ] Test OAuth URL generation for each service
- [ ] Test real API connections for each service
- [ ] Verify authentication flows work end-to-end
- [ ] Set up production OAuth apps when ready
- [ ] Configure production environment variables

---

## 🎉 READY TO INTEGRATE!

Once you've added all your credentials following this guide, your enterprise system will be able to:

- ✅ Authenticate users with GitHub, Google, and Slack
- ✅ Access real data from all three services
- ✅ Perform cross-service searches and aggregations
- ✅ Automate workflows across all platforms
- ✅ Monitor service health and API usage
- ✅ Scale for production enterprise usage

**🚀 Your enterprise system will be fully integrated with real 3rd-party services!**

---

*Last Updated: November 2025*
*Version: 1.0 - Comprehensive Guide*