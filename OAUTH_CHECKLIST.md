# OAuth Configuration Checklist

Use this checklist to track your OAuth configuration progress.

## Priority Order (by Business Value)

### ☐ 1. Google Workspace ($220K/year) - 30-45 min
**Services**: Gmail, Google Calendar, Google Drive

- [ ] Go to [Google Cloud Console](https://console.cloud.google.com)
- [ ] Create project "ATOM Integration"
- [ ] Enable APIs: Gmail, Calendar, Drive, People
- [ ] Configure OAuth consent screen
- [ ] Create OAuth credentials
- [ ] Copy Client ID to `.env` as `GOOGLE_CLIENT_ID`
- [ ] Copy Client Secret to `.env` as `GOOGLE_CLIENT_SECRET`
- [ ] Set `GOOGLE_REDIRECT_URI=http://localhost:8001/api/auth/google/callback`
- [ ] Test: Visit http://localhost:8001/api/auth/google/initiate
- [ ] Verify success in backend logs

### ☐ 2. Salesforce ($100K/year) - 20-30 min
**Service**: CRM, Lead Management

- [ ] Go to Salesforce Setup → App Manager
- [ ] Create Connected App "ATOM Integration"
- [ ] Enable OAuth Settings
- [ ] Set Callback URL: http://localhost:8001/api/auth/salesforce/callback
- [ ] Select scopes: Full access, Refresh token
- [ ] Copy Consumer Key to `.env` as `SALESFORCE_CLIENT_ID`
- [ ] Copy Consumer Secret to `.env` as `SALESFORCE_CLIENT_SECRET`
- [ ] Set `SALESFORCE_REDIRECT_URI=http://localhost:8001/api/auth/salesforce/callback`
- [ ] Test: Visit http://localhost:8001/api/auth/salesforce/initiate
- [ ] Verify success in backend logs

### ☐ 3. Microsoft 365 ($120K/year) - 30-45 min
**Services**: Outlook, OneDrive, Teams

- [ ] Go to [Azure Portal](https://portal.azure.com)
- [ ] App registrations → New registration
- [ ] Name: "ATOM", Multi-tenant
- [ ] Redirect URI: http://localhost:8001/api/auth/microsoft/callback
- [ ] API permissions → Microsoft Graph
- [ ] Add: Calendars.ReadWrite, Mail.ReadWrite, Files.ReadWrite.All, User.Read
- [ ] Certificates & secrets → New client secret
- [ ] Copy Application ID to `.env` as `MICROSOFT_CLIENT_ID`
- [ ] Copy Client Secret to `.env` as `MICROSOFT_CLIENT_SECRET`
- [ ] Set `MICROSOFT_REDIRECT_URI=http://localhost:8001/api/auth/microsoft/callback`
- [ ] Test: Visit http://localhost:8001/api/auth/microsoft/initiate
- [ ] Verify success in backend logs

### ☐ 4. Slack ($68K/year) - 15-20 min
**Service**: Team Communication

- [ ] Go to [Slack API](https://api.slack.com/apps)
- [ ] Create New App → From scratch
- [ ] App Name: "ATOM", Select workspace
- [ ] OAuth & Permissions → Redirect URLs
- [ ] Add: http://localhost:8001/api/auth/slack/callback
- [ ] Scopes: chat:write, channels:read, channels:history, users:read, files:write
- [ ] Copy Client ID to `.env` as `SLACK_CLIENT_ID`
- [ ] Copy Client Secret to `.env` as `SLACK_CLIENT_SECRET`
- [ ] Set `SLACK_REDIRECT_URI=http://localhost:8001/api/auth/slack/callback`
- [ ] Test: Visit http://localhost:8001/api/auth/slack/initiate
- [ ] Verify success in backend logs

### ☐ 5. GitHub ($32K/year) - 10-15 min
**Service**: Code Repository, PR Management

- [ ] Go to GitHub Settings → Developer settings → OAuth Apps
- [ ] New OAuth App
- [ ] Application name: "ATOM"
- [ ] Homepage URL: http://localhost:3000
- [ ] Callback URL: http://localhost:8001/api/auth/github/callback
- [ ] Copy Client ID to `.env` as `GITHUB_CLIENT_ID`
- [ ] Generate client secret
- [ ] Copy Client Secret to `.env` as `GITHUB_CLIENT_SECRET`
- [ ] Set `GITHUB_REDIRECT_URI=http://localhost:8001/api/auth/github/callback`
- [ ] Test: Visit http://localhost:8001/api/auth/github/initiate
- [ ] Verify success in backend logs

## Verification

After each integration:
- [ ] Run: `python oauth_config_assistant.py`
- [ ] Check configuration status
- [ ] Verify API health check
- [ ] Test OAuth flow in browser

## Final Validation

After all integrations:
- [ ] Run: `python backend/enhanced_validation_report.py`
- [ ] Verify business value increased from $0 to $540K+
- [ ] Check integration readiness improved from 48.7% to 80%+
- [ ] Run: `python backend/run_comprehensive_validation.py`
- [ ] Target: All high-value workflows operational

## Notes

- Keep OAuth credentials secure (never commit .env to git)
- Use production URLs when deploying (not localhost)
- Refresh tokens may expire - implement refresh logic
- Some integrations may require app review/approval for production use

## Estimated Total Time: 2-3 hours
## Estimated Business Value Unlocked: $540K+/year
