# 🚀 ATOM External Service Setup Guide
# Practical Configuration for Production Deployment

## 📋 Overview

This guide provides step-by-step instructions for configuring the most critical external services required for ATOM's production deployment. Follow these instructions to enable real-world functionality.

---

## 🎯 Priority 1: Essential Services (Start Here)

### 1. OpenAI API Setup

**Required for**: AI conversations, embeddings, text processing

#### Setup Steps:
1. **Visit**: [OpenAI Platform](https://platform.openai.com)
2. **Sign in** or create account
3. **Navigate** to API Keys section
4. **Create new API key**
5. **Copy** the key and add to environment:

```bash
# In .env.production
OPENAI_API_KEY="sk-your-actual-api-key-here"
```

#### Testing:
```bash
# Test OpenAI integration
curl -X POST http://localhost:5059/api/atom/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello ATOM", "user_id": "test"}'
```

### 2. Google OAuth Setup

**Required for**: Gmail, Google Calendar, Google Drive integration

#### Setup Steps:
1. **Go to**: [Google Cloud Console](https://console.cloud.google.com)
2. **Create new project** or select existing
3. **Enable APIs**:
   - Google Drive API
   - Gmail API
   - Google Calendar API
4. **Configure OAuth consent screen**:
   - Application type: External
   - App name: "ATOM Personal Assistant"
   - User support email: your-email@domain.com
   - Developer contact: your-email@domain.com
   - Scopes: Add `/auth/drive`, `/auth/gmail.readonly`, `/auth/calendar`
5. **Create credentials**:
   - Application type: Web application
   - Name: "ATOM Web Client"
   - Authorized redirect URIs:
     - `http://localhost:5059/api/auth/gdrive/callback`
     - `https://your-production-domain.com/api/auth/gdrive/callback`
6. **Copy credentials** and add to environment:

```bash
# In .env.production
ATOM_GDRIVE_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
ATOM_GDRIVE_CLIENT_SECRET="your-google-client-secret"
ATOM_GDRIVE_REDIRECT_URI="http://localhost:5059/api/auth/gdrive/callback"
```

#### Testing:
```bash
# Test Google OAuth initiation
curl http://localhost:5059/api/auth/gdrive/initiate?user_id=test
```

### 3. Notion Integration

**Required for**: Task management, notes, project tracking

#### Setup Steps:
1. **Go to**: [Notion Integrations](https://www.notion.so/my-integrations)
2. **Create new integration**
3. **Configure**:
   - Name: "ATOM Personal Assistant"
   - Associated workspace: Select your workspace
   - Capabilities: Read content, Update content, Read user information
4. **Copy credentials**:

```bash
# In .env.production
NOTION_CLIENT_ID="your-notion-client-id"
NOTION_CLIENT_SECRET="your-notion-client-secret"
NOTION_REDIRECT_URI="http://localhost:5059/api/auth/notion/callback"
```

#### Testing:
```bash
# Test Notion OAuth
curl http://localhost:5059/api/auth/notion/initiate?user_id=test
```

---

## 🎯 Priority 2: Productivity Services

### 4. Trello Integration

**Required for**: Task boards, project management

#### Setup Steps:
1. **Visit**: [Trello Developer API Keys](https://trello.com/app-key)
2. **Generate API Key**
3. **Generate Token** using the API Key
4. **Add to environment**:

```bash
# In .env.production
TRELLO_API_KEY="your-trello-api-key"
TRELLO_API_TOKEN="your-trello-api-token"
```

#### Testing:
```bash
# Test Trello integration
curl http://localhost:5059/api/trello/boards
```

### 5. Dropbox Integration

**Required for**: File storage, document management

#### Setup Steps:
1. **Go to**: [Dropbox Developer Portal](https://www.dropbox.com/developers)
2. **Create new app**
3. **Choose**:
   - Scoped access
   - Full Dropbox access
   - App folder access
4. **Configure redirect URIs**:
   - `http://localhost:5059/api/auth/dropbox/callback`
5. **Copy credentials**:

```bash
# In .env.production
DROPBOX_CLIENT_ID="your-dropbox-client-id"
DROPBOX_CLIENT_SECRET="your-dropbox-client-secret"
DROPBOX_REDIRECT_URI="http://localhost:5059/api/auth/dropbox/callback"
```

#### Testing:
```bash
# Test Dropbox OAuth
curl http://localhost:5059/api/auth/dropbox/initiate?user_id=test
```

### 6. Asana Integration

**Required for**: Project management, task tracking

#### Setup Steps:
1. **Go to**: [Asana Developer Console](https://app.asana.com/0/developer-console)
2. **Create new app**
3. **Configure OAuth**:
   - Redirect URL: `http://localhost:5059/api/auth/asana/callback`
4. **Copy credentials**:

```bash
# In .env.production
ASANA_CLIENT_ID="your-asana-client-id"
ASANA_CLIENT_SECRET="your-asana-client-secret"
ASANA_REDIRECT_URI="http://localhost:5059/api/auth/asana/callback"
```

---

## 🎯 Priority 3: Communication Services

### 7. Slack Integration

**Required for**: Team communication, message search

#### Setup Steps:
1. **Go to**: [Slack API Apps](https://api.slack.com/apps)
2. **Create New App**
3. **Configure OAuth & Permissions**:
   - Redirect URLs: `http://localhost:5059/api/auth/slack/callback`
   - Scopes: `channels:read`, `chat:write`, `users:read`
4. **Install app to workspace**
5. **Copy credentials**:

```bash
# In .env.production
SLACK_CLIENT_ID="your-slack-client-id"
SLACK_CLIENT_SECRET="your-slack-client-secret"
SLACK_REDIRECT_URI="http://localhost:5059/api/auth/slack/callback"
```

### 8. Microsoft Outlook Integration

**Required for**: Email, calendar (alternative to Google)

#### Setup Steps:
1. **Go to**: [Azure Portal](https://portal.azure.com)
2. **App Registrations** → New registration
3. **Configure**:
   - Supported account types: Personal Microsoft accounts
   - Redirect URI: `http://localhost:5059/api/auth/outlook/callback`
   - API permissions: Mail.Read, Calendars.Read, User.Read
4. **Copy credentials**:

```bash
# In .env.production
OUTLOOK_CLIENT_ID="your-outlook-client-id"
OUTLOOK_CLIENT_SECRET="your-outlook-client-secret"
OUTLOOK_REDIRECT_URI="http://localhost:5059/api/auth/outlook/callback"
```

---

## 🎯 Priority 4: Financial Services

### 9. Plaid Integration

**Required for**: Bank account connections, financial data

#### Setup Steps:
1. **Sign up**: [Plaid Dashboard](https://dashboard.plaid.com)
2. **Create new application**
3. **Select environment**: Start with "Sandbox" for testing
4. **Copy credentials**:

```bash
# In .env.production
PLAID_CLIENT_ID="your-plaid-client-id"
PLAID_SECRET="your-plaid-secret"
PLAID_ENVIRONMENT="sandbox"  # sandbox, development, or production
```

#### Testing:
```bash
# Test Plaid integration
curl http://localhost:5059/api/financial/accounts
```

---

## 🔧 Quick Configuration Script

Create a setup script to validate configurations:

```bash
#!/bin/bash
# save as setup_external_services.sh

echo "🔧 ATOM External Service Setup Validator"
echo "========================================"

# Check if environment file exists
if [ ! -f ".env.production" ]; then
    echo "❌ .env.production file not found"
    exit 1
fi

# Load environment
set -a
source .env.production
set +a

echo ""
echo "📋 Configuration Status:"
echo "------------------------"

# Check OpenAI
if [ -n "$OPENAI_API_KEY" ] && [ "$OPENAI_API_KEY" != "sk-your-production-openai-api-key-here" ]; then
    echo "✅ OpenAI API Key: Configured"
else
    echo "❌ OpenAI API Key: Not configured"
fi

# Check Google OAuth
if [ -n "$ATOM_GDRIVE_CLIENT_ID" ] && [ "$ATOM_GDRIVE_CLIENT_ID" != "your-google-client-id.apps.googleusercontent.com" ]; then
    echo "✅ Google OAuth: Configured"
else
    echo "❌ Google OAuth: Not configured"
fi

# Check Notion
if [ -n "$NOTION_CLIENT_ID" ] && [ "$NOTION_CLIENT_ID" != "your-notion-client-id" ]; then
    echo "✅ Notion Integration: Configured"
else
    echo "❌ Notion Integration: Not configured"
fi

# Check Trello
if [ -n "$TRELLO_API_KEY" ] && [ "$TRELLO_API_KEY" != "your-trello-api-key" ]; then
    echo "✅ Trello Integration: Configured"
else
    echo "❌ Trello Integration: Not configured"
fi

echo ""
echo "🚀 Next Steps:"
echo "1. Restart backend server after configuration changes"
echo "2. Test individual integrations"
echo "3. Configure frontend to use real services"
```

---

## 🧪 Testing Integration Flows

### Test Complete OAuth Flow:

1. **Start backend server** with configured environment
2. **Initiate OAuth** for each service:
   ```bash
   # Example for Google
   curl "http://localhost:5059/api/auth/gdrive/initiate?user_id=test-user-123"
   ```
3. **Follow redirect URL** in browser
4. **Complete OAuth flow** with service provider
5. **Verify callback** and token storage

### Test API Endpoints:

```bash
# Calendar integration
curl http://localhost:5059/api/calendar/events

# Task management
curl http://localhost:5059/api/tasks

# File search
curl http://localhost:5059/api/search?query=test

# Financial data
curl http://localhost:5059/api/financial/accounts
```

---

## 🔒 Security Best Practices

### Environment Security:
- Never commit `.env.production` to version control
- Use different credentials for development and production
- Rotate API keys every 90 days
- Use secret management services (AWS Secrets Manager, HashiCorp Vault)

### OAuth Security:
- Validate redirect URIs match exactly
- Implement proper state parameter validation
- Store refresh tokens securely with encryption
- Monitor for suspicious activity

### API Security:
- Implement rate limiting
- Validate all input parameters
- Use HTTPS in production
- Monitor API usage and quotas

---

## 📞 Troubleshooting Common Issues

### OAuth Redirect Errors:
- **Issue**: "Redirect URI mismatch"
- **Solution**: Ensure exact match in service configuration

### API Rate Limits:
- **Issue**: "Rate limit exceeded"
- **Solution**: Implement retry logic with exponential backoff

### Token Expiration:
- **Issue**: "Invalid token" errors
- **Solution**: Implement automatic token refresh

### CORS Issues:
- **Issue**: Frontend cannot connect to backend
- **Solution**: Configure proper CORS settings

---

## ✅ Configuration Checklist

- [ ] OpenAI API Key configured
- [ ] Google OAuth credentials set up
- [ ] Notion integration configured
- [ ] Trello API credentials added
- [ ] Dropbox OAuth configured
- [ ] Asana integration set up
- [ ] Slack integration configured (optional)
- [ ] Outlook integration configured (optional)
- [ ] Plaid credentials added (optional)
- [ ] All services tested individually
- [ ] OAuth flows working end-to-end
- [ ] API endpoints responding correctly
- [ ] Security measures implemented

---

**Last Updated**: October 18, 2025  
**Status**: Ready for Production Configuration

For additional help, refer to:
- `EXTERNAL_SERVICE_CONFIGURATION.md` - Complete service documentation
- `PRODUCTION_DEPLOYMENT_NEXT_STEPS.md` - Deployment instructions
- Backend logs for detailed error information