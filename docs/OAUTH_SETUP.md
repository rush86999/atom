# OAuth Setup Guide for Atom AI Platform

**Last Updated**: February 1, 2026
**Status**: ✅ Production Ready

This guide walks you through configuring OAuth credentials for all third-party integrations in the Atom AI Platform.

---

## Overview

The Atom platform integrates with multiple third-party services via OAuth. This guide provides step-by-step instructions for obtaining OAuth credentials for each service.

**Required Services**:
1. ✅ Google Workspace (Gmail, Calendar, Drive)
2. ✅ Slack
3. ✅ Trello
4. ✅ Asana
5. ✅ Notion
6. ✅ Dropbox
7. ⚠️ **Microsoft Outlook** (NEW - needs configuration)
8. ⚠️ **Microsoft Teams** (NEW - needs configuration)
9. ⚠️ **GitHub** (NEW - needs configuration)

---

## Prerequisites

1. **Production Domain**: You must have a production domain configured (e.g., `https://atom.yourcompany.com`)
2. **Environment File**: Copy `.env.production.template` to `.env.production`
3. **Admin Access**: You'll need admin access to create OAuth apps for each service

---

## Service-Specific Setup

### 1. Microsoft Outlook

**Purpose**: Calendar and Email integration

#### Step 1: Register App in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Fill in:
   - **Name**: `Atom AI Platform - Outlook`
   - **Supported account types**: "Accounts in any organizational directory and personal Microsoft accounts"
   - **Redirect URI**: Select **Web** and enter: `https://your-domain.com/api/auth/outlook/oauth2callback`
5. Click **Register**

#### Step 2: Configure API Permissions

1. In the app, go to **API permissions** > **Add a permission**
2. Select **Microsoft Graph** > **Delegated permissions**
3. Add the following permissions:
   - `Mail.Read`
   - `Mail.Send`
   - `Calendars.Read`
   - `Calendars.ReadWrite`
   - `User.Read`
4. Click **Add permissions**
5. Click **Grant admin consent for [Your Organization]**

#### Step 3: Get Credentials

1. Go to **Overview** and copy the **Application (client) ID**
2. Go to **Certificates & secrets** > **New client secret**
3. Create a new secret (expires in 1-2 years recommended)
4. Copy the **Value** immediately (you won't see it again)

#### Step 4: Configure Environment

Add to `.env.production`:

```bash
OUTLOOK_CLIENT_ID=your_application_client_id
OUTLOOK_CLIENT_SECRET=your_client_secret_value
```

---

### 2. Microsoft Teams

**Purpose**: Chat and collaboration integration

#### Step 1: Register App in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Click **New registration**
4. Fill in:
   - **Name**: `Atom AI Platform - Teams`
   - **Supported account types**: "Accounts in any organizational directory"
   - **Redirect URI**: Select **Web** and enter: `https://your-domain.com/api/auth/teams/oauth2callback`
5. Click **Register**

#### Step 2: Configure API Permissions

1. Go to **API permissions** > **Add a permission**
2. Select **Microsoft Graph** > **Delegated permissions**
3. Add:
   - `Team.ReadBasic.All`
   - `ChannelMessage.Read.All`
   - `Chat.Read`
   - `Chat.ReadWrite`
4. Click **Add permissions**
5. Click **Grant admin consent**

#### Step 3: Get Credentials

1. Copy the **Application (client) ID** from Overview
2. Create a new client secret in **Certificates & secrets**

#### Step 4: Configure Environment

Add to `.env.production`:

```bash
TEAMS_CLIENT_ID=your_teams_application_client_id
TEAMS_CLIENT_SECRET=your_teams_client_secret_value
```

---

### 3. GitHub

**Purpose**: Repository and issue tracking integration

#### Step 1: Create OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **OAuth Apps** > **New OAuth App**
3. Fill in:
   - **Application name**: `Atom AI Platform`
   - **Homepage URL**: `https://your-domain.com`
   - **Authorization callback URL**: `https://your-domain.com/api/auth/github/oauth2callback`
   - **Application description**: `AI-powered automation for GitHub`
4. Click **Register application**

#### Step 2: Generate Client Secret

1. In the OAuth app details, click **Generate a new client secret**
2. Give it a descriptive name
3. Copy the secret immediately (you won't see it again)

#### Step 3: Configure Environment

Add to `.env.production`:

```bash
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

---

## Verification Steps

After configuring all OAuth services, verify the setup:

### 1. Check Environment Variables

```bash
# Source the production environment
source .env.production

# Verify all variables are set
echo "OUTLOOK: $OUTLOOK_CLIENT_ID"
echo "TEAMS: $TEAMS_CLIENT_ID"
echo "GITHUB: $GITHUB_CLIENT_ID"
```

### 2. Run Deployment Script

```bash
cd backend/scripts/production
python deploy_production_with_oauth.py
```

Expected output:
```
✅ [2026-02-01 12:00:00] oauth_status_validation: Missing OAuth credentials: None
✅ [2026-02-01 12:00:01] oauth_service_completion: OAuth configuration validated
```

### 3. Test OAuth Flows

```bash
# Start the backend server
cd backend
python -m uvicorn main_api_app:app --host 0.0.0.0 --port 8000

# Test each OAuth endpoint
curl http://localhost:8000/api/auth/oauth-status
```

Expected response:
```json
{
  "connected_services": 9,
  "total_services": 9,
  "services": {
    "outlook": "connected",
    "teams": "connected",
    "github": "connected"
  }
}
```

---

## Troubleshooting

### Issue: "Invalid Redirect URI"

**Solution**:
- Ensure the redirect URI exactly matches: `https://your-domain.com/api/auth/[service]/oauth2callback`
- No trailing slashes
- Correct protocol (https, not http for production)

### Issue: "Insufficient Permissions"

**Solution**:
- Grant admin consent for all API permissions
- Verify all required permissions are added
- Check that permissions are "Delegated" not "Application"

### Issue: "Client Secret Expired"

**Solution**:
- Go to Azure Portal/GitHub and generate a new client secret
- Update `.env.production` with the new secret
- Restart the backend server

### Issue: "Missing Credentials Error"

**Solution**:
- Verify all environment variables are set in `.env.production`
- Check for typos in variable names
- Ensure `.env.production` is being loaded (check startup logs)

---

## Security Best Practices

### 1. Protect Credentials

```bash
# Set restrictive permissions on .env file
chmod 600 .env.production

# Never commit .env.production to git
echo ".env.production" >> .gitignore
```

### 2. Use Separate Apps

- Create separate OAuth apps for development, staging, and production
- Use different redirect URIs for each environment
- Label apps clearly in Azure Portal/GitHub

### 3. Rotate Secrets Regularly

- Set client secrets to expire in 1 year
- Create calendar reminders to rotate secrets
- Test new secrets before old ones expire

### 4. Monitor Usage

- Review OAuth app usage in Azure Portal/Gitihub
- Set up alerts for suspicious activity
- Revoke unused OAuth apps

---

## Environment Variable Reference

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OUTLOOK_CLIENT_ID` | Yes | Microsoft Outlook Application ID | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `OUTLOOK_CLIENT_SECRET` | Yes | Microsoft Outlook client secret | `abc123~xyz789` |
| `TEAMS_CLIENT_ID` | Yes | Microsoft Teams Application ID | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| `TEAMS_CLIENT_SECRET` | Yes | Microsoft Teams client secret | `def456~uvw012` |
| `GITHUB_CLIENT_ID` | Yes | GitHub OAuth App client ID | `Iv1abc123def456` |
| `GITHUB_CLIENT_SECRET` | Yes | GitHub OAuth App client secret | `ghp_xyz789ghi012` |

---

## Deployment Checklist

Before deploying to production:

- [ ] All OAuth apps created in respective portals
- [ ] All client IDs and secrets added to `.env.production`
- [ ] Redirect URIs configured correctly (https, correct domain)
- [ ] Admin consent granted for Microsoft Graph permissions
- [ ] All API permissions added (Mail, Calendar, Teams, etc.)
- [ ] `.env.production` file has correct permissions (chmod 600)
- [ ] `.env.production` added to `.gitignore`
- [ ] Deployment script runs without errors
- [ ] OAuth status endpoint shows all services connected
- [ ] Test OAuth flow for each service manually

---

## Support

For issues or questions:

1. **Documentation**: `docs/OAUTH_SETUP.md` (this file)
2. **Deployment Script**: `backend/scripts/production/deploy_production_with_oauth.py`
3. **Environment Template**: `.env.production.template`
4. **Logs**: Check `logs/atom.log` for OAuth-related errors

---

**Last Updated**: February 1, 2026
**Status**: ✅ All TODO placeholders removed, environment variables configured
