# Configure Missing Service Credentials

## Current Status

✅ **Dependencies Installed**: All Python packages for service handlers are now installed
✅ **Service Handlers Available**: 5 service handlers successfully imported
✅ **OpenAI Connected**: Fully functional

## 🔧 Missing Credentials to Configure

### 1. Notion API Token
**Issue**: Invalid API token
**Status**: ❌ Needs refresh

**Steps to Fix**:
1. Go to https://www.notion.so/my-integrations
2. Create a new integration or regenerate token for existing integration
3. Copy the new "Internal Integration Token"
4. Update environment variable:
   ```bash
   export NOTION_TOKEN="your_new_notion_token_here"
   ```

### 2. Jira Credentials
**Missing**: JIRA_SERVER_URL, JIRA_API_TOKEN
**Status**: ❌ Not configured

**Steps to Configure**:
1. Get your Jira server URL (e.g., `https://your-domain.atlassian.net`)
2. Generate an API token:
   - Go to https://id.atlassian.com/manage-profile/security/api-tokens
   - Create new API token
3. Set environment variables:
   ```bash
   export JIRA_SERVER_URL="https://your-domain.atlassian.net"
   export JIRA_API_TOKEN="your_jira_api_token"
   ```

### 3. Box Credentials
**Missing**: BOX_CLIENT_ID, BOX_CLIENT_SECRET
**Status**: ❌ Not configured

**Steps to Configure**:
1. Go to https://developer.box.com/
2. Create a new app or use existing app
3. Get Client ID and Client Secret
4. Set environment variables:
   ```bash
   export BOX_CLIENT_ID="your_box_client_id"
   export BOX_CLIENT_SECRET="your_box_client_secret"
   ```

## 🔐 OAuth Setup Required

### Services Needing OAuth Configuration:

#### Asana OAuth
- **Status**: Handler available, needs OAuth flow
- **Setup**:
  - Go to https://app.asana.com/0/developer-console
  - Create OAuth app
  - Configure redirect URI: `http://localhost:5058/api/auth/asana/oauth2callback`

#### Google OAuth
- **Status**: Client ID/Secret configured, needs OAuth flow
- **Setup**:
  - Go to https://console.cloud.google.com/apis/credentials
  - Configure OAuth consent screen
  - Add redirect URI: `http://localhost:5058/api/auth/gdrive/oauth2callback`

#### Slack OAuth
- **Status**: Client ID/Secret configured, needs OAuth flow
- **Setup**:
  - Go to https://api.slack.com/apps
  - Configure OAuth & Permissions
  - Add redirect URI: `http://localhost:5058/api/auth/slack/oauth2callback`

## 🚀 Quick Setup Commands

Add these to your `.env` file or run in terminal:

```bash
# Notion (replace with actual token)
export NOTION_TOKEN="ntn_your_new_notion_token_here"

# Jira (replace with actual values)
export JIRA_SERVER_URL="https://your-domain.atlassian.net"
export JIRA_API_TOKEN="your_jira_api_token_here"

# Box (replace with actual values)
export BOX_CLIENT_ID="your_box_client_id_here"
export BOX_CLIENT_SECRET="your_box_client_secret_here"
```

## 📊 Current Service Status

| Service | API Keys | Handler | OAuth | Status |
|---------|----------|---------|-------|---------|
| OpenAI | ✅ | N/A | N/A | ✅ Connected |
| Asana | ✅ | ✅ | ❌ | 🔧 Ready for OAuth |
| Trello | ✅ | ✅ | ❌ | 🔧 Ready for OAuth |
| Notion | ⚠️ | ✅ | N/A | 🔧 Fix Token |
| GitHub | ❌ | ✅ | N/A | 🔧 Add Token |
| Dropbox | ✅ | ✅ | ❌ | 🔧 Ready for OAuth |
| Slack | ✅ | ❌ | ❌ | 🔧 Create Handler |
| Jira | ❌ | ✅ | N/A | 🔧 Add Credentials |
| Box | ❌ | ✅ | ❌ | 🔧 Add Credentials |

## 🎯 Next Steps Priority

1. **HIGH**: Fix Notion token and configure Jira/Box credentials
2. **MEDIUM**: Create Slack handler and complete OAuth flows
3. **LOW**: Test actual API connectivity for all services

## ✅ Verification

After configuring credentials, run:
```bash
python3 validate_all_services.py
```

This will validate all services and show updated status.