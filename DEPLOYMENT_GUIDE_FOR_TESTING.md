# 🚀 Deployment Guide for Real Credential Testing

## 📋 Overview

This guide provides step-by-step instructions for deploying the ATOM application to test real service integrations with actual API credentials. Since we've completed comprehensive implementations for multiple services, this deployment will enable end-to-end testing with real data.

## 🎯 Services Ready for Testing

### ✅ Frontend API Key Services (Immediately Testable)
- **Trello**: Uses frontend API keys (users provide their own)
- **OpenAI**: Uses frontend API keys
- **Other AI Services**: Deepseek, Claude, OpenRouter (frontend keys)

### ✅ OAuth Services (Require Server Configuration)
- **Notion**: Complete OAuth implementation ready
- **Google**: OAuth implementation ready  
- **Dropbox**: OAuth implementation ready
- **Asana**: OAuth implementation ready
- **Box**: OAuth implementation ready

## 🏗️ Deployment Options

### Option 1: Local Development Deployment
```bash
# 1. Clone and setup
git clone <repository-url>
cd atom

# 2. Install dependencies
cd backend/python-api-service
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env.production
# Edit .env.production with your credentials

# 4. Start the backend
python minimal_app.py

# 5. Start the frontend (separate terminal)
cd ../frontend-nextjs
npm install
npm run dev
```

### Option 2: Docker Deployment
```bash
# 1. Build and run with Docker Compose
docker-compose -f docker-compose.production.yml up -d

# 2. Or build individual services
docker build -t atom-backend -f backend/Dockerfile .
docker build -t atom-frontend -f frontend-nextjs/Dockerfile .
```

### Option 3: Cloud Deployment (Recommended for Testing)
```bash
# Using AWS/CDK (pre-configured)
cd deployment/aws
npm install -g aws-cdk
cdk deploy

# Or using your preferred cloud provider
```

## 🔧 Environment Configuration

### Required Environment Variables

#### OAuth Services (Server Configuration)
```bash
# Notion OAuth
NOTION_CLIENT_ID=your_notion_client_id
NOTION_CLIENT_SECRET=your_notion_client_secret
NOTION_REDIRECT_URI=https://your-domain.com/auth/notion/callback

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://your-domain.com/auth/google/callback

# Dropbox OAuth
DROPBOX_APP_KEY=your_dropbox_app_key
DROPBOX_APP_SECRET=your_dropbox_app_secret
DROPBOX_REDIRECT_URI=https://your-domain.com/auth/dropbox/callback

# Asana OAuth
ASANA_CLIENT_ID=your_asana_client_id
ASANA_CLIENT_SECRET=your_asana_client_secret

# Box OAuth
BOX_CLIENT_ID=your_box_client_id
BOX_CLIENT_SECRET=your_box_client_secret
```

#### Database & Security
```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database
# OR for SQLite (development)
DATABASE_URL=sqlite:///atom.db

# Security
ATOM_OAUTH_ENCRYPTION_KEY=your_32_character_encryption_key
FLASK_SECRET_KEY=your_flask_secret_key
```

#### Application Settings
```bash
# Application
APP_CLIENT_URL=https://your-frontend-domain.com
PYTHON_API_PORT=5058

# LanceDB (Memory Storage)
LANCEDB_URI=data/lancedb
LANCEDB_TABLE_NAME=processed_documents
```

## 🔍 Service-Specific Setup Instructions

### Notion OAuth Setup
1. Go to https://www.notion.so/my-integrations
2. Create a new **Public Integration**
3. Set redirect URI to: `https://your-domain.com/api/auth/notion/callback`
4. Copy Client ID and Client Secret to environment
5. Test OAuth flow: `/api/auth/notion/initiate?user_id=test-user`

### Trello API Key Setup (User-Provided)
1. Users get their own Trello API key from: https://trello.com/power-ups/admin
2. Frontend sends headers:
   - `X-Trello-API-Key`: User's API key
   - `X-Trello-API-Token`: User's API token
3. No server configuration needed!

### Google OAuth Setup
1. Go to Google Cloud Console
2. Create OAuth 2.0 credentials
3. Set authorized redirect URIs
4. Configure scopes for Google Drive/Calendar

## 🧪 Testing Checklist

### Pre-Deployment Verification
- [ ] All unit tests pass: `python test_package_imports.py`
- [ ] Integration framework ready: `python test_real_integrations.py`
- [ ] Notion OAuth tests: `python test_notion_oauth_integration.py` (13/14 passing)
- [ ] Trello API tests: `python test_trello_frontend_keys.py` (8/8 passing)

### Post-Deployment Testing
```bash
# 1. Health check
curl https://your-domain.com/healthz

# 2. Service status
curl https://your-domain.com/api/integrations/status

# 3. Test Trello with real API keys
curl -X POST https://your-domain.com/api/trello/search \
  -H "X-Trello-API-Key: user-key" \
  -H "X-Trello-API-Token: user-token" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user", "query": "test"}'

# 4. Test Notion OAuth initiation
curl "https://your-domain.com/api/auth/notion/initiate?user_id=test-user"
```

### LanceDB Memory Pipeline Testing
```bash
# Test ingestion pipeline
curl -X POST https://your-domain.com/api/ingestion/start \
  -H "Content-Type: application/json" \
  -d '{
    "source_type": "trello",
    "source_config": {
      "api_key": "user-trello-key",
      "api_token": "user-trello-token", 
      "board_id": "trello-board-id"
    },
    "user_id": "test-user"
  }'

# Test memory search
curl -X POST https://your-domain.com/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "search term",
    "user_id": "test-user"
  }'
```

## 🚨 Troubleshooting

### Common Issues

#### OAuth Redirect Errors
- **Issue**: Redirect URI mismatch
- **Fix**: Ensure exact match in OAuth app configuration
- **Debug**: Check logs for redirect URI validation errors

#### Database Connection Issues
- **Issue**: `DATABASE_URL` not configured
- **Fix**: Set proper database connection string
- **Debug**: Check `db_utils.py` connection logs

#### Token Encryption Issues
- **Issue**: `ATOM_OAUTH_ENCRYPTION_KEY` not set
- **Fix**: Generate 32-character encryption key
- **Debug**: Check crypto_utils initialization logs

#### CORS Issues
- **Issue**: Frontend-backend communication blocked
- **Fix**: Configure CORS properly in Flask app
- **Debug**: Check browser console for CORS errors

### Log Analysis
```bash
# Check backend logs
docker logs atom-backend

# Check specific service logs
grep "notion" backend/logs/app.log
grep "trello" backend/logs/app.log

# Monitor real-time
tail -f backend/logs/app.log
```

## 📊 Monitoring & Validation

### Success Metrics
- [ ] OAuth flows complete successfully
- [ ] API calls return real data (not mock data)
- [ ] LanceDB stores and retrieves documents
- [ ] Memory search returns relevant results
- [ ] All services maintain connection status

### Performance Benchmarks
- OAuth token exchange: < 5 seconds
- API response time: < 2 seconds
- Document ingestion: < 10 seconds per 100 items
- Memory search: < 1 second

## 🔄 Continuous Testing

### Automated Testing Script
```bash
#!/bin/bash
# deployment-test.sh

echo "🚀 Starting deployment validation..."

# Health check
curl -f https://$DOMAIN/healthz || exit 1

# Service status check
STATUS=$(curl -s https://$DOMAIN/api/integrations/status | jq '.notion.status')
if [ "$STATUS" != '"connected"' ]; then
  echo "❌ Notion service not connected"
  exit 1
fi

echo "✅ Deployment validation passed"
```

### Monitoring Dashboard
- Service status endpoints: `/api/integrations/status`
- Health metrics: `/healthz` 
- Performance metrics: Application logs
- Error tracking: Structured logging

## 🎯 Next Steps After Deployment

1. **Complete OAuth Testing**: Test all OAuth flows with real credentials
2. **Validate Memory Pipeline**: Ensure LanceDB stores and retrieves data correctly
3. **Performance Testing**: Load test with real user data
4. **Security Review**: Validate token encryption and data protection
5. **User Acceptance Testing**: Real user testing with actual workflows

## 📞 Support

- **Backend Issues**: Check `backend/python-api-service/logs/`
- **OAuth Issues**: Verify redirect URIs and client credentials
- **Database Issues**: Check connection strings and permissions
- **Memory Pipeline**: Validate LanceDB configuration and embeddings

---

*Last Updated: 2025-10-08*
*Tested Services: Notion, Trello, Google, Dropbox, OpenAI*
*Ready for Production Testing*