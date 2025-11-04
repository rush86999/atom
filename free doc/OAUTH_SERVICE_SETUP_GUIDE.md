# OAuth Service Setup Guide

## Remaining Services to Configure

### Microsoft Outlook & Teams
1. **Azure Portal Setup**
   - Go to [Azure Portal](https://portal.azure.com)
   - Navigate to Azure Active Directory > App registrations
   - Create new registration or use existing
   - Add redirect URIs:
     - `https://YOUR_DOMAIN.com/api/auth/outlook/oauth2callback`
     - `https://YOUR_DOMAIN.com/api/auth/teams/oauth2callback`

2. **API Permissions**
   - Microsoft Graph > Mail.Read
   - Microsoft Graph > Calendars.Read
   - Microsoft Graph > Team.ReadBasic.All

3. **Environment Variables**
```bash
OUTLOOK_CLIENT_ID=your_microsoft_client_id
OUTLOOK_CLIENT_SECRET=your_microsoft_client_secret
TEAMS_CLIENT_ID=your_microsoft_client_id  # Can be same as Outlook
TEAMS_CLIENT_SECRET=your_microsoft_client_secret
```

### GitHub
1. **GitHub Developer Setup**
   - Go to [GitHub Developer Settings](https://github.com/settings/developers)
   - Create new OAuth App
   - Application name: "Atom AI Assistant"
   - Homepage URL: `https://YOUR_DOMAIN.com`
   - Authorization callback URL: `https://YOUR_DOMAIN.com/api/auth/github/oauth2callback`

2. **Scopes Required**
   - repo (access repositories)
   - user (read user profile)
   - read:org (read organization data)

3. **Environment Variables**
```bash
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

## Production Domain Setup
Replace `YOUR_DOMAIN.com` with your actual production domain in:
- Redirect URIs
- Environment variables
- OAuth configuration

## Verification Steps
1. Update environment variables with real credentials
2. Restart the backend server
3. Run validation: `python test_oauth_validation.py`
4. Verify all 10 services show as connected

Generated: 2025-11-01 12:29:48
