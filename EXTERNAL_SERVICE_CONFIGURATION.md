# 🚀 ATOM External Service Configuration Guide

## 📋 Overview

This guide provides comprehensive instructions for configuring all external services required for ATOM's production deployment. Follow these steps to set up API keys, OAuth credentials, and service integrations.

---

## 🔐 Required Environment Variables

### Core Application Variables
```bash
# Database Configuration
DATABASE_URL="postgresql://atom_user:your-secure-password@localhost:5432/atom_db"

# Application Security
FLASK_SECRET_KEY="your-flask-secret-key-here"
ATOM_OAUTH_ENCRYPTION_KEY="32-byte-base64-encoded-key"

# Application URLs
APP_CLIENT_URL="https://your-frontend-domain.com"
PYTHON_API_PORT="5058"
```

### AI & Machine Learning Services

#### OpenAI API
```bash
# Required for AI conversations, embeddings, and text processing
OPENAI_API_KEY="sk-your-openai-api-key-here"
```

#### Deepgram API
```bash
# Required for audio transcription in meetings
DEEPGRAM_API_KEY="your-deepgram-api-key-here"
```

### Communication & Email Services

#### Gmail Integration
```bash
# OAuth credentials for Gmail integration
ATOM_GDRIVE_CLIENT_ID="your-google-client-id.apps.googleusercontent.com"
ATOM_GDRIVE_CLIENT_SECRET="your-google-client-secret"
ATOM_GDRIVE_REDIRECT_URI="https://your-backend-domain.com/api/auth/gdrive/callback"
```

#### Outlook Integration
```bash
# OAuth credentials for Outlook integration
OUTLOOK_CLIENT_ID="your-outlook-client-id"
OUTLOOK_CLIENT_SECRET="your-outlook-client-secret"
OUTLOOK_REDIRECT_URI="https://your-backend-domain.com/api/auth/outlook/callback"
```

### File Storage Services

#### Dropbox Integration
```bash
# OAuth credentials for Dropbox
DROPBOX_CLIENT_ID="your-dropbox-client-id"
DROPBOX_CLIENT_SECRET="your-dropbox-client-secret"
DROPBOX_REDIRECT_URI="https://your-backend-domain.com/api/auth/dropbox/callback"
```

#### Box Integration
```bash
# OAuth credentials for Box
BOX_CLIENT_ID="your-box-client-id"
BOX_CLIENT_SECRET="your-box-client-secret"
BOX_REDIRECT_URI="https://your-backend-domain.com/api/auth/box/callback"
```

### Task Management & Productivity

#### Notion Integration
```bash
# OAuth credentials for Notion
NOTION_CLIENT_ID="your-notion-client-id"
NOTION_CLIENT_SECRET="your-notion-client-secret"
NOTION_REDIRECT_URI="https://your-backend-domain.com/api/auth/notion/callback"
```

#### Trello Integration
```bash
# API key and token for Trello
TRELLO_API_KEY="your-trello-api-key"
TRELLO_API_TOKEN="your-trello-api-token"
```

#### Asana Integration
```bash
# OAuth credentials for Asana
ASANA_CLIENT_ID="your-asana-client-id"
ASANA_CLIENT_SECRET="your-asana-client-secret"
ASANA_REDIRECT_URI="https://your-backend-domain.com/api/auth/asana/callback"
```

#### Jira Integration
```bash
# API credentials for Jira
JIRA_API_TOKEN="your-jira-api-token"
JIRA_DOMAIN="your-domain.atlassian.net"
JIRA_EMAIL="your-email@domain.com"
```

### Financial Services

#### Plaid Integration
```bash
# Required for bank account connections and financial data
PLAID_CLIENT_ID="your-plaid-client-id"
PLAID_SECRET="your-plaid-secret"
PLAID_ENVIRONMENT="sandbox"  # or "development" or "production"
```

#### QuickBooks Integration
```bash
# OAuth credentials for QuickBooks
QUICKBOOKS_CLIENT_ID="your-quickbooks-client-id"
QUICKBOOKS_CLIENT_SECRET="your-quickbooks-client-secret"
QUICKBOOKS_REDIRECT_URI="https://your-backend-domain.com/api/auth/quickbooks/callback"
```

#### Xero Integration
```bash
# OAuth credentials for Xero
XERO_CLIENT_ID="your-xero-client-id"
XERO_CLIENT_SECRET="your-xero-client-secret"
XERO_REDIRECT_URI="https://your-backend-domain.com/api/auth/xero/callback"
```

### CRM & Sales Services

#### Salesforce Integration
```bash
# OAuth credentials for Salesforce
SALESFORCE_CLIENT_ID="your-salesforce-client-id"
SALESFORCE_CLIENT_SECRET="your-salesforce-client-secret"
SALESFORCE_REDIRECT_URI="https://your-backend-domain.com/api/auth/salesforce/callback"
SALESFORCE_INSTANCE_URL="https://your-instance.salesforce.com"
```

#### HubSpot Integration
```bash
# API key for HubSpot
HUBSPOT_API_KEY="your-hubspot-api-key"
```

### Social Media Services

#### Twitter/X Integration
```bash
# API credentials for Twitter/X
TWITTER_API_KEY="your-twitter-api-key"
TWITTER_API_SECRET="your-twitter-api-secret"
TWITTER_ACCESS_TOKEN="your-twitter-access-token"
TWITTER_ACCESS_SECRET="your-twitter-access-secret"
```

#### LinkedIn Integration
```bash
# OAuth credentials for LinkedIn
LINKEDIN_CLIENT_ID="your-linkedin-client-id"
LINKEDIN_CLIENT_SECRET="your-linkedin-client-secret"
LINKEDIN_REDIRECT_URI="https://your-backend-domain.com/api/auth/linkedin/callback"
```

### Marketing Services

#### Mailchimp Integration
```bash
# API key for Mailchimp
MAILCHIMP_API_KEY="your-mailchimp-api-key"
MAILCHIMP_SERVER_PREFIX="us1"  # or your server prefix
```

#### Shopify Integration
```bash
# API credentials for Shopify
SHOPIFY_API_KEY="your-shopify-api-key"
SHOPIFY_API_SECRET="your-shopify-api-secret"
SHOPIFY_STORE_URL="your-store.myshopify.com"
```

### Other Services

#### GitHub Integration
```bash
# Personal access token for GitHub
GITHUB_ACCESS_TOKEN="your-github-access-token"
```

#### Zapier Integration
```bash
# Webhook URL for Zapier integration
ZAPIER_WEBHOOK_URL="your-zapier-webhook-url"
```

---

## 🔧 Service Setup Instructions

### 1. OpenAI API Setup
1. Visit [OpenAI Platform](https://platform.openai.com)
2. Create account or sign in
3. Navigate to API Keys section
4. Create new API key
5. Copy and add to environment variables

### 2. Google OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create new project or select existing
3. Enable Google Drive API and Gmail API
4. Configure OAuth consent screen
5. Create OAuth 2.0 credentials
6. Add authorized redirect URIs
7. Copy Client ID and Client Secret

### 3. Plaid Setup
1. Sign up at [Plaid Dashboard](https://dashboard.plaid.com)
2. Create new application
3. Select appropriate environment (sandbox/development/production)
4. Copy Client ID and Secret
5. Configure redirect URIs if needed

### 4. Notion Integration
1. Go to [Notion Integrations](https://www.notion.so/my-integrations)
2. Create new integration
3. Configure permissions and capabilities
4. Copy OAuth Client ID and Client Secret
5. Add integration to your workspace

### 5. Trello Integration
1. Visit [Trello Developer API Keys](https://trello.com/app-key)
2. Generate API Key
3. Generate Token using the API Key
4. Copy both API Key and Token

### 6. Dropbox Integration
1. Go to [Dropbox Developer Portal](https://www.dropbox.com/developers)
2. Create new app
3. Choose appropriate permissions
4. Generate OAuth credentials
5. Configure redirect URIs

---

## 🚀 Production Deployment Configuration

### Environment File Template
Create a `.env.production` file with all required variables:

```bash
# Core Application
DATABASE_URL="postgresql://atom_user:secure_password@your-db-host:5432/atom_db"
FLASK_SECRET_KEY="generate-secure-random-key"
ATOM_OAUTH_ENCRYPTION_KEY="vWk9b-yK47EWCYf5tY8zxyNX4vvTPjNTttSX7IQEO2g="
APP_CLIENT_URL="https://your-frontend-domain.com"
PYTHON_API_PORT="5058"

# AI Services
OPENAI_API_KEY="sk-your-production-openai-key"
DEEPGRAM_API_KEY="your-production-deepgram-key"

# Communication Services
ATOM_GDRIVE_CLIENT_ID="your-production-google-client-id"
ATOM_GDRIVE_CLIENT_SECRET="your-production-google-secret"
ATOM_GDRIVE_REDIRECT_URI="https://your-backend-domain.com/api/auth/gdrive/callback"

# Add all other production credentials...
```

### Docker Compose Configuration
For Docker deployment, ensure environment variables are passed:

```yaml
services:
  atom-backend:
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ATOM_GDRIVE_CLIENT_ID=${ATOM_GDRIVE_CLIENT_ID}
      # ... all other environment variables
```

---

## 🔒 Security Best Practices

### Key Management
- Store API keys in environment variables, never in code
- Use different keys for development and production
- Rotate keys regularly
- Use secret management services (AWS Secrets Manager, HashiCorp Vault)

### OAuth Security
- Use secure redirect URIs
- Implement proper state parameter validation
- Store refresh tokens securely with encryption
- Implement token refresh mechanisms

### Database Security
- Use strong passwords for database users
- Enable SSL/TLS for database connections
- Restrict database access to application servers only
- Regular security updates and patches

---

## 🧪 Testing Configuration

### Development Environment
Create a `.env.development` file with test credentials:

```bash
# Use sandbox/test credentials for development
PLAID_ENVIRONMENT="sandbox"
OPENAI_API_KEY="sk-test-key"  # Use test key if available
# ... other development credentials
```

### Integration Testing
- Use mock services for development
- Implement comprehensive error handling
- Test OAuth flows with test accounts
- Validate all API responses

---

## 📞 Support & Troubleshooting

### Common Issues
1. **OAuth Redirect Errors**: Ensure redirect URIs match exactly
2. **API Rate Limits**: Implement proper rate limiting and retry logic
3. **Token Expiration**: Implement automatic token refresh
4. **CORS Issues**: Configure proper CORS settings for frontend

### Monitoring
- Monitor API usage and quotas
- Set up alerts for failed authentication
- Log integration errors for debugging
- Track service health and availability

---

## ✅ Verification Checklist

- [ ] All environment variables configured
- [ ] OAuth applications created and configured
- [ ] API keys generated and stored securely
- [ ] Redirect URIs properly configured
- [ ] Database connections tested
- [ ] Integration endpoints tested
- [ ] Security measures implemented
- [ ] Monitoring and logging configured

---

**Last Updated**: October 18, 2025  
**Status**: Ready for Production Deployment