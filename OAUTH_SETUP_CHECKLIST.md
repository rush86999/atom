# OAuth Service Setup Checklist

## Priority Services (Require OAuth)
- [ ] Gmail - Client ID & Secret needed
- [ ] Outlook - Microsoft App registration needed
- [ ] Notion - Integration setup needed
- [ ] Google Drive - OAuth credentials needed
- [ ] Microsoft Teams - App registration needed

## Environment Variables Needed
```
# Gmail
GMAIL_CLIENT_ID=your-gmail-client-id
GMAIL_CLIENT_SECRET=your-gmail-client-secret

# Outlook
OUTLOOK_CLIENT_ID=your-outlook-client-id
OUTLOOK_CLIENT_SECRET=your-outlook-client-secret
OUTLOOK_TENANT_ID=common

# Notion
NOTION_CLIENT_ID=your-notion-client-id
NOTION_CLIENT_SECRET=your-notion-client-secret

# Google Drive
GDRIVE_CLIENT_ID=your-gdrive-client-id
GDRIVE_CLIENT_SECRET=your-gdrive-client-secret

# Microsoft Teams
TEAMS_CLIENT_ID=your-teams-client-id
TEAMS_CLIENT_SECRET=your-teams-client-secret
TEAMS_TENANT_ID=your-tenant-id
```

## Setup Instructions
1. Register applications in respective developer portals
2. Configure OAuth redirect URIs to: http://localhost:5058/api/{service}/oauth/callback
3. Add credentials to environment variables
4. Restart backend server
5. Test OAuth flow initiation

## Testing Commands
```bash
# Test OAuth initiation
curl http://localhost:5058/api/gmail/oauth/initiate

# Check service health
curl http://localhost:5058/api/gmail/health
```
