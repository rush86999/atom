# 🔑 ATOM API Key Integration Guide

## 📋 Overview

This guide provides step-by-step instructions for obtaining and configuring real API keys for the ATOM personal assistant application. Follow these instructions to transition from mock services to real integrations.

## 🎯 Required API Keys

### Core Services (Priority 1)
- [ ] **OpenAI API Key** - For AI capabilities
- [ ] **Google OAuth Credentials** - For Calendar, Drive, Gmail
- [ ] **Notion API Token** - For Notion integration
- [ ] **Dropbox App Keys** - For file storage

### Additional Services (Priority 2)
- [ ] **Trello API Keys** - For task management
- [ ] **Asana OAuth App** - For project management
- [ ] **Slack Bot Token** - For messaging
- [ ] **GitHub Access Token** - For code integration

### Optional Services (Priority 3)
- [ ] **Plaid Credentials** - For financial data
- [ ] **Deepgram API Key** - For audio transcription
- [ ] **LinkedIn Marketing API** - For social media

## 📝 Step-by-Step Acquisition Guide

### 1. OpenAI API Key
**URL**: https://platform.openai.com/api-keys

1. Sign in to your OpenAI account
2. Navigate to API Keys section
3. Click "Create new secret key"
4. Copy the key (starts with `sk-`)
5. Set environment variable: `OPENAI_API_KEY=sk-your-key-here`

### 2. Google OAuth Credentials
**URL**: https://console.cloud.google.com/apis/credentials

1. Create a new project or select existing one
2. Enable required APIs:
   - Google Calendar API
   - Google Drive API
   - Gmail API
3. Create OAuth 2.0 Client ID
4. Configure authorized redirect URIs:
   - `http://localhost:5058/auth/google/callback` (development)
   - `https://localhost/auth/google/callback` (production)
5. Download credentials JSON
6. Set environment variables:
   - `GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com`
   - `GOOGLE_CLIENT_SECRET=your-client-secret`

### 3. Notion Integration
**URL**: https://www.notion.so/my-integrations

1. Click "New integration"
2. Name your integration (e.g., "ATOM Personal Assistant")
3. Select associated workspace
4. Set capabilities (read/content/update as needed)
5. Copy the "Internal Integration Token" (starts with `secret_`)
6. Set environment variable: `NOTION_API_TOKEN=secret_your-token-here`

### 4. Dropbox App
**URL**: https://www.dropbox.com/developers/apps

1. Click "Create app"
2. Choose:
   - Scoped access
   - Full Dropbox access
   - App name (e.g., "ATOM Assistant")
3. Generate access token or set up OAuth
4. Set environment variables:
   - `DROPBOX_APP_KEY=your-app-key`
   - `DROPBOX_APP_SECRET=your-app-secret`
   - `DROPBOX_ACCESS_TOKEN=your-access-token`

### 5. Trello API Keys (Frontend API Key Model)
**URL**: https://trello.com/power-ups/admin

**Authentication Model**: Frontend API Keys (each user provides their own API key and token)

1. Go to Trello Developer Portal
2. Click "Generate a new API key"
3. Copy the API Key
4. Manually generate a token using: https://trello.com/1/authorize?expiration=never&scope=read,write,account&response_type=token&key=YOUR_API_KEY
5. **Users enter these in the frontend** (no server environment variables needed):
   - API Key: `your-api-key`
   - API Token: `your-generated-token`

**Frontend Headers**:
- `X-Trello-API-Key`: Your Trello API key
- `X-Trello-API-Token`: Your Trello API token

### 6. Asana OAuth App
**URL**: https://app.asana.com/0/developer-console

1. Create new app
2. Configure OAuth:
   - Redirect URI: `http://localhost:5058/auth/asana/callback`
   - Scopes: `default` (includes tasks, projects, etc.)
3. Copy Client ID and Client Secret
4. Set environment variables:
   - `ASANA_CLIENT_ID=your-client-id`
   - `ASANA_CLIENT_SECRET=your-client-secret`

## 🔧 Configuration Steps

### 1. Create Production Environment File
```bash
cp .env.production.template .env.production
```

### 2. Edit Production Environment
Edit `.env.production` with your real API keys:
```env
# Core API Keys
OPENAI_API_KEY=sk-your-actual-openai-key-here
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
NOTION_API_TOKEN=secret_your-actual-notion-token

# Dropbox
DROPBOX_APP_KEY=your-dropbox-app-key
DROPBOX_APP_SECRET=your-dropbox-app-secret

# Trello (Optional - for development only)
# Note: Trello now uses frontend API keys, but you can still set these for testing
TRELLO_API_KEY=your-trello-api-key
TRELLO_API_TOKEN=your-trello-generated-token

# Asana
ASANA_CLIENT_ID=your-asana-client-id
ASANA_CLIENT_SECRET=your-asana-client-secret

# Change to production mode
ENABLE_MOCK_SERVICES=false
USE_SQLITE_FALLBACK=false
FLASK_ENV=production
DEBUG=false
```

### 3. Test Configuration
```bash
# Test API key formats
python backend/python-api-service/test_integrations.py --env .env.production --keys-only

# Test full integration (requires server running)
python backend/python-api-service/test_integrations.py --env .env.production --test-all
```

### 4. Start Production Server
```bash
# Using development server (for testing)
python backend/python-api-service/start_app.py

# Using production WSGI server (recommended)
gunicorn main_api_app:create_app -b 0.0.0.0:5058 --workers 4 --threads 2
```

## 🧪 Testing Integration Endpoints

### 1. Health Check
```bash
curl http://localhost:5058/healthz
```

### 2. API Key Validation
```bash
curl -X POST http://localhost:5058/api/integrations/validate \
  -H "X-OpenAI-API-Key: $OPENAI_API_KEY" \
  -H "X-Google-Client-ID: $GOOGLE_CLIENT_ID" \
  -H "X-Notion-API-Token: $NOTION_API_TOKEN" \
  -H "Content-Type: application/json"
```

### 3. Dashboard with Real Data
```bash
curl http://localhost:5058/api/dashboard?user_id=test_user \
  -H "X-OpenAI-API-Key: $OPENAI_API_KEY" \
  -H "X-Google-Client-ID: $GOOGLE_CLIENT_ID"
```

## 🔒 Security Best Practices

### 1. Environment Management
- Never commit real API keys to version control
- Use different keys for development and production
- Rotate keys regularly (every 90 days recommended)
- Use secrets manager for production deployments

### 2. Access Control
- Use principle of least privilege for API permissions
- Enable 2FA on all service accounts
- Regularly audit API key usage
- Monitor for suspicious activity

### 3. Backup and Recovery
- Backup API keys and configuration
- Document key rotation procedures
- Have emergency revocation procedures

## 🚨 Troubleshooting

### Common Issues

1. **Invalid Key Formats**
   - OpenAI keys must start with `sk-`
   - Notion tokens must start with `secret_`
   - GitHub tokens must start with `ghp_`

2. **OAuth Redirect URI Mismatch**
   - Ensure redirect URIs match exactly in developer consoles
   - Include both http and https versions if needed

3. **Rate Limiting**
   - Monitor API usage and implement caching
   - Use exponential backoff for retries
   - Consider premium tiers for high usage

4. **Permission Errors**
   - Verify all required API scopes are enabled
   - Check that OAuth consent screen is configured

### Debug Mode
For troubleshooting, enable debug mode temporarily:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
python backend/python-api-service/start_app.py
```

## 📞 Support Resources

- **OpenAI Support**: https://help.openai.com/
- **Google Cloud Support**: https://cloud.google.com/support
- **Notion API Docs**: https://developers.notion.com/
- **Dropbox Developer Support**: https://www.dropbox.com/developers/support
- **Trello API Docs**: https://developer.atlassian.com/cloud/trello/
- **Asana Developer Portal**: https://developers.asana.com/

## 🔄 Maintenance Schedule

| Task | Frequency | Responsibility |
|------|-----------|----------------|
| API Key Rotation | Quarterly | DevOps Team |
| Security Audit | Monthly | Security Team |
| Usage Monitoring | Weekly | Operations Team |
| Documentation Update | As needed | Development Team |

---

*Last Updated: 2025-09-20*  
*Maintained by: ATOM Development Team*