# 🔑 ATOM Real API Key Acquisition & Testing Guide

## 🎯 Overview

This guide provides detailed, step-by-step instructions for obtaining real API keys and testing the ATOM personal assistant application in production mode. Follow these instructions to transition from development to live deployment.

## 📋 Prerequisites

- ✅ ATOM application backend fully operational
- ✅ All real service implementations completed and verified
- ✅ Integration testing framework ready
- ✅ Production environment templates available

## 🚀 Phase 1: API Key Acquisition (Priority Order)

### Priority 1: Core AI & Cloud Services (Essential)

#### 1.1 OpenAI API Key
**URL**: https://platform.openai.com/api-keys
**Time**: 5 minutes
**Cost**: Pay-per-use (free credits available)

**Steps:**
1. Visit https://platform.openai.com/api-keys
2. Sign in to your OpenAI account
3. Click "Create new secret key"
4. Name it "ATOM Personal Assistant"
5. Copy the generated key (starts with `sk-`)
6. **Important**: Save the key immediately - you won't see it again

**Environment Variable:**
```bash
OPENAI_API_KEY=sk-your-actual-key-here
```

#### 1.2 Google OAuth Credentials
**URL**: https://console.cloud.google.com/apis/credentials
**Time**: 15 minutes
**Cost**: Free with usage limits

**Steps:**
1. Go to Google Cloud Console
2. Create new project: "ATOM Personal Assistant"
3. Enable required APIs:
   - Google Calendar API
   - Google Drive API
   - Gmail API
   - Google Contacts API
4. Navigate to "Credentials" → "Create Credentials" → "OAuth 2.0 Client ID"
5. Configure application type: "Web application"
6. Set authorized redirect URIs:
   - `http://localhost:5058/auth/google/callback` (development)
   - `https://localhost/auth/google/callback` (production)
7. Download the OAuth client configuration JSON
8. Copy Client ID and Client Secret

**Environment Variables:**
```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

#### 1.3 Dropbox App Keys
**URL**: https://www.dropbox.com/developers/apps
**Time**: 10 minutes
**Cost**: Free with storage limits

**Steps:**
1. Visit Dropbox Developer Portal
2. Click "Create app"
3. Choose configuration:
   - Choose an API: Scoped access
   - Type of data access: Full Dropbox
   - App folder name: "ATOM Personal Assistant"
4. Generate access token
5. Copy App Key and App Secret

**Environment Variables:**
```bash
DROPBOX_APP_KEY=your-app-key
DROPBOX_APP_SECRET=your-app-secret
DROPBOX_ACCESS_TOKEN=your-access-token
```

### Priority 2: Productivity & Project Management

#### 2.1 Trello API Keys
**URL**: https://trello.com/power-ups/admin
**Time**: 10 minutes
**Cost**: Free

**Steps:**
1. Go to Trello Developer Portal
2. Click "Generate a new API key"
3. Copy the API Key
4. Generate token using this URL (replace YOUR_API_KEY):
   ```
   https://trello.com/1/authorize?expiration=never&scope=read,write,account&response_type=token&key=YOUR_API_KEY
   ```
5. Authorize the application and copy the generated token

**Environment Variables:**
```bash
TRELLO_API_KEY=your-api-key
TRELLO_API_TOKEN=your-generated-token
```

#### 2.2 Asana OAuth App
**URL**: https://app.asana.com/0/developer-console
**Time**: 10 minutes
**Cost**: Free

**Steps:**
1. Visit Asana Developer Console
2. Click "Create new app"
3. Configure OAuth settings:
   - Redirect URI: `http://localhost:5058/auth/asana/callback`
   - Scopes: `default` (includes tasks, projects, etc.)
4. Copy Client ID and Client Secret

**Environment Variables:**
```bash
ASANA_CLIENT_ID=your-client-id
ASANA_CLIENT_SECRET=your-client-secret
```

#### 2.3 Notion Integration Token
**URL**: https://www.notion.so/my-integrations
**Time**: 5 minutes
**Cost**: Free

**Steps:**
1. Go to Notion Integrations page
2. Click "New integration"
3. Name: "ATOM Personal Assistant"
4. Select associated workspace
5. Set capabilities (read/content/update as needed)
6. Copy the "Internal Integration Token" (starts with `secret_`)

**Environment Variable:**
```bash
NOTION_API_TOKEN=secret_your-token-here
```

### Priority 3: Business & Communication Services

#### 3.1 Slack Bot Token
**URL**: https://api.slack.com/apps
**Time**: 15 minutes
**Cost**: Free

**Steps:**
1. Go to Slack API page
2. Create new app
3. Configure OAuth & Permissions
4. Add bot token scopes: `channels:read`, `chat:write`, `users:read`
5. Install app to workspace
6. Copy Bot User OAuth Token

**Environment Variable:**
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token
```

#### 3.2 GitHub Access Token
**URL**: https://github.com/settings/tokens
**Time**: 5 minutes
**Cost**: Free

**Steps:**
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Set expiration: No expiration (for development)
4. Select scopes: `repo`, `user`, `read:org`
5. Copy the generated token

**Environment Variable:**
```bash
GITHUB_ACCESS_TOKEN=ghp_your-token-here
```

## 🚀 Phase 2: Production Configuration

### 2.1 Create Production Environment File

```bash
# Navigate to project root
cd /home/developer/projects/atom/atom

# Copy production template
cp .env.production.template .env.production

# Edit with your real API keys
nano .env.production
```

### 2.2 Configure Production Environment

Edit `.env.production` with your acquired keys:

```env
# ===========================================
# CORE AI & CLOUD SERVICES
# ===========================================
OPENAI_API_KEY=sk-your-actual-openai-key-here
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret-here
DROPBOX_APP_KEY=your-dropbox-app-key
DROPBOX_APP_SECRET=your-dropbox-app-secret
DROPBOX_ACCESS_TOKEN=your-dropbox-access-token

# ===========================================
# PRODUCTIVITY SERVICES
# ===========================================
TRELLO_API_KEY=your-trello-api-key
TRELLO_API_TOKEN=your-trello-generated-token
ASANA_CLIENT_ID=your-asana-client-id
ASANA_CLIENT_SECRET=your-asana-client-secret
NOTION_API_TOKEN=secret_your-notion-token-here

# ===========================================
# BUSINESS & COMMUNICATION
# ===========================================
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
GITHUB_ACCESS_TOKEN=ghp_your-github-token

# ===========================================
# PRODUCTION SETTINGS
# ===========================================
ENABLE_MOCK_SERVICES=false
USE_SQLITE_FALLBACK=false
FLASK_ENV=production
DEBUG=false
LOG_LEVEL=INFO
DATABASE_URL=postgresql://user:pass@localhost:5432/atom_prod

# Encryption key (32-byte base64)
OAUTH_ENCRYPTION_KEY=your-32-byte-base64-encryption-key
```

### 2.3 Security Configuration

```bash
# Ensure production file is not tracked by git
echo ".env.production" >> .gitignore

# Set proper file permissions
chmod 600 .env.production
```

## 🚀 Phase 3: Integration Testing

### 3.1 Pre-Test Validation

```bash
# Test API key formats (without making actual API calls)
cd backend/python-api-service
python test_real_integrations.py --env ../../.env.production --keys-only
```

### 3.2 Start Production Server

```bash
# Set environment file
export ENV_FILE=../../.env.production

# Start the application
python start_app.py

# Expected output:
# * Starting ATOM Personal Assistant API...
# * Environment: production
# * Debug mode: off
# * Running on http://0.0.0.0:5058
```

### 3.3 Comprehensive Integration Testing

```bash
# In a new terminal, run full integration tests
cd backend/python-api-service
python test_real_integrations.py --env ../../.env.production --test-all
```

### 3.4 Manual Endpoint Testing

```bash
# Health check
curl http://localhost:5058/healthz

# OpenAI status
curl http://localhost:5058/api/integrations/openai/status

# Google OAuth initiation
curl http://localhost:5058/auth/google

# Trello boards
curl http://localhost:5058/api/integrations/trello/boards

# Dashboard with real data
curl http://localhost:5058/api/dashboard?user_id=test_user
```

## 🚀 Phase 4: Production Deployment

### 4.1 Using Gunicorn (Recommended)

```bash
# Install gunicorn if not already installed
pip install gunicorn

# Start production server
cd backend/python-api-service
gunicorn main_api_app:create_app \
  -b 0.0.0.0:5058 \
  --workers 4 \
  --threads 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --env ENV_FILE=../../.env.production
```

### 4.2 Using Systemd Service (Linux)

Create `/etc/systemd/system/atom.service`:

```ini
[Unit]
Description=ATOM Personal Assistant API
After=network.target

[Service]
Type=simple
User=atom
WorkingDirectory=/opt/atom/backend/python-api-service
Environment=ENV_FILE=/opt/atom/.env.production
ExecStart=/opt/atom/venv/bin/gunicorn main_api_app:create_app \
  -b 0.0.0.0:5058 \
  --workers 4 \
  --threads 2 \
  --timeout 120
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4.3 Docker Deployment

```bash
# Build production image
docker build -t atom-api:latest -f backend/docker/Dockerfile.production .

# Run with environment file
docker run -d \
  --name atom-api \
  -p 5058:5058 \
  --env-file .env.production \
  atom-api:latest
```

## 🧪 Testing Checklist

### ✅ Pre-Deployment Tests

- [ ] All API keys acquired and validated
- [ ] Production environment file configured
- [ ] Application starts without errors
- [ ] Health endpoint returns 200 OK
- [ ] Database connections established
- [ ] OAuth encryption working

### ✅ Integration Tests

- [ ] OpenAI API responses received
- [ ] Google OAuth flow initiates
- [ ] Dropbox file operations work
- [ ] Trello board access functional
- [ ] Asana project retrieval successful
- [ ] Notion page access working
- [ ] Slack message sending tested
- [ ] GitHub repository access verified

### ✅ Performance Tests

- [ ] Response times under 2 seconds
- [ ] Concurrent user handling
- [ ] Memory usage stable
- [ ] Database query optimization
- [ ] Error rate below 1%

## 🔒 Security Best Practices

### Key Management
- [ ] Never commit API keys to version control
- [ ] Use environment variables for all secrets
- [ ] Rotate keys every 90 days
- [ ] Monitor API usage for anomalies
- [ ] Implement rate limiting

### Access Control
- [ ] Use principle of least privilege
- [ ] Enable 2FA on all service accounts
- [ ] Regular security audits
- [ ] Log all API access attempts

### Network Security
- [ ] Use HTTPS in production
- [ ] Configure proper CORS settings
- [ ] Implement request rate limiting
- [ ] Monitor for suspicious activity

## 🚨 Troubleshooting Guide

### Common Issues

**Invalid API Key Formats:**
- OpenAI keys must start with `sk-`
- Notion tokens must start with `secret_`
- GitHub tokens must start with `ghp_`
- Slack tokens must start with `xoxb-`

**OAuth Redirect URI Errors:**
- Ensure exact match in developer consoles
- Include protocol (http/https)
- Check for trailing slashes

**Rate Limiting:**
- Implement exponential backoff
- Cache responses when possible
- Monitor usage and upgrade plans if needed

**Permission Errors:**
- Verify all required API scopes are enabled
- Check OAuth consent screen configuration
- Ensure proper workspace/domain permissions

### Debug Mode

For troubleshooting, temporarily enable debug mode:

```bash
# Edit .env.production temporarily
DEBUG=true
LOG_LEVEL=DEBUG

# Restart application
python start_app.py
```

## 📊 Monitoring & Maintenance

### Daily Checks
- API usage and rate limits
- Error logs and exceptions
- Database connection health
- Response time metrics

### Weekly Tasks
- Security log review
- Backup verification
- Dependency updates
- Performance optimization

### Monthly Maintenance
- API key rotation
- Security audit
- Database optimization
- Infrastructure review

## 🎯 Success Metrics

- **API Response Time**: < 2 seconds average
- **Uptime**: > 99.5% availability
- **Error Rate**: < 1% of requests
- **User Satisfaction**: > 4.5/5 rating
- **Integration Success**: > 95% of API calls

## 📞 Support Resources

- **OpenAI Support**: https://help.openai.com/
- **Google Cloud Support**: https://cloud.google.com/support
- **Dropbox Developer Support**: https://www.dropbox.com/developers/support
- **Trello API Docs**: https://developer.atlassian.com/cloud/trello/
- **Asana Developer Portal**: https://developers.asana.com/

---

**Last Updated**: 2025-09-23  
**Maintained by**: ATOM Development Team  
**Status**: 🟢 READY FOR PRODUCTION DEPLOYMENT

> ⚠️ **Important**: Always test with a small subset of users before full production rollout. Monitor closely for the first 48 hours after deployment.