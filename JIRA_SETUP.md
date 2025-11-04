# Jira Integration Setup Guide

## 1. Create Atlassian OAuth App

### For Jira Cloud (Recommended):
1. Go to: https://developer.atlassian.com/console/myapps/
2. Click "**Create new app**"
3. Select "**OAuth 2.0**"
4. Fill in app details:
   - **Name**: ATOM Agent Integration
   - **Description**: ATOM agent integration for issue management and data ingestion
   - **URL**: Your application URL
   - **Callback URL**: `https://localhost/oauth/jira/callback`

### Configure OAuth Scopes:
- **Jira API**: 
  - `read:jira-work`
  - `read:issue-details:jira`
  - `read:comments:jira`
  - `read:attachments:jira`
  - `read:project:jira`
  - `read:user:jira`
  - `read:board:jira`
  - `read:sprint:jira`

## 2. Alternative: Personal Access Token (PAT)

### For Development/Testing:
1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "**Create API token**"
3. Fill in details:
   - **Label**: ATOM Agent Integration
   - **Permissions**: Read access to Jira projects
4. Copy the token immediately (it won't be shown again)

## 3. Jira Server Configuration

### For Jira Server/Data Center:
1. Go to: `{your-jira-server}/plugins/servlet/oauth/consumer`
2. Create a new consumer:
   - **Name**: ATOM Agent Integration
   - **Consumer Key**: Generate (save this)
   - **Shared Secret**: Generate (save this)
   - **Callback URL**: `https://localhost/oauth/jira/callback`
   - **Permissions**: Read access

## 4. Environment Variables

Add to your `.env` file:

```bash
# Jira Cloud OAuth (Preferred)
JIRA_CLIENT_ID=your_jira_client_id
JIRA_CLIENT_SECRET=your_jira_client_secret
JIRA_REDIRECT_URI=https://localhost/oauth/jira/callback
JIRA_SERVER_URL=https://your-domain.atlassian.net

# Jira Server/Basic Auth
JIRA_USERNAME=your_jira_username
JIRA_API_TOKEN=your_jira_api_token
JIRA_SERVER_URL=https://your-jira-server.com

# For OAuth (if using OAuth)
JIRA_OAUTH_TOKEN=your_jira_oauth_token
JIRA_OAUTH_REFRESH_TOKEN=your_jira_oauth_refresh_token
```

## 5. Project Permissions

### Grant Access to Projects:
1. Go to your Jira project settings
2. Navigate to "**Permissions**"
3. Ensure your integration user has:
   - **Browse Projects**: Read access
   - **View Issues**: Read access
   - **View Comments**: Read access
   - **View Attachments**: Read access
   - **View Development Tools**: Read access (if using dev features)

## 6. Test Connection

### OAuth Flow Test:
```bash
curl -X GET "https://auth.atlassian.com/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=YOUR_REDIRECT_URI&response_type=code&scope=read:jira-work read:issue-details:jira"
```

### API Token Test:
```bash
curl -X GET "https://your-domain.atlassian.net/rest/api/3/myself" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

### Basic Auth Test:
```bash
curl -X GET "https://your-jira-server.com/rest/api/3/myself" \
  -u "YOUR_USERNAME:YOUR_API_TOKEN"
```

## 7. JQL Query Configuration

### Default JQL for ATOM:
```sql
status != "Done" AND updated >= -30d ORDER BY updated DESC
```

### Custom JQL Examples:
```sql
# Active issues in specific projects
project IN (PROJECT1, PROJECT2) AND status IN ("To Do", "In Progress")

# High priority issues
priority IN ("Highest", "High") AND status != "Done"

# Issues assigned to user
assignee = currentUser() AND status != "Done"

# Issues created in last 7 days
created >= -7d AND status != "Done"
```

## 8. Rate Limits and Best Practices

### Jira Cloud Rate Limits:
- **Standard Plan**: 1000 requests per hour
- **Premium Plan**: 5000 requests per hour
- **Enterprise**: 10000 requests per hour

### Best Practices:
1. **Use pagination**: Don't fetch more than 100 items per request
2. **Cache responses**: Cache project metadata and user info
3. **Implement retry logic**: Use exponential backoff for failures
4. **Use field filtering**: Request only necessary fields
5. **Batch requests**: Use bulk operations when possible

## 9. Webhook Configuration (Optional)

### Create Webhooks for Real-Time Updates:
1. Go to: `{your-jira-domain}/secure/admin/Webhooks!default.jspa`
2. Click "**Create new webhook**"
3. Configure:
   - **Name**: ATOM Agent Webhook
   - **URL**: `https://localhost/api/webhooks/jira`
   - **Events**: 
     - `jira:issue_created`
     - `jira:issue_updated`
     - `jira:comment_added`
     - `jira:attachment_added`

## 10. Security Considerations

### API Token Security:
- Store tokens securely in environment variables
- Use least privilege principle (only necessary permissions)
- Rotate tokens regularly
- Monitor API usage logs

### OAuth Security:
- Validate redirect URLs
- Use PKCE (Proof Key for Code Exchange)
- Store tokens encrypted at rest
- Implement token refresh mechanism

## 11. Troubleshooting

### Common Issues:
- **401 Unauthorized**: Check credentials and permissions
- **403 Forbidden**: User doesn't have access to requested resource
- **404 Not Found**: Incorrect API endpoint or issue doesn't exist
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Jira server error

### Solutions:
- Verify credentials and refresh tokens
- Check user permissions in Jira
- Validate API endpoints and URLs
- Implement rate limiting and retry logic
- Contact Jira admin for server issues

## 12. Integration Testing

### Test Workflow:
1. **Test authentication**: Verify OAuth or token access
2. **Test project access**: List projects the user can access
3. **Test issue retrieval**: Fetch issues using JQL
4. **Test comment retrieval**: Get comments for specific issues
5. **Test attachment retrieval**: Download attachments from issues
6. **Test search functionality**: Search for issues with different filters

### Sample Test Data:
```bash
# Test project listing
curl -X GET "{JIRA_SERVER}/rest/api/3/project/search" \
  -H "Authorization: Bearer {TOKEN}"

# Test issue search
curl -X GET "{JIRA_SERVER}/rest/api/3/search?jql=status!=Done&maxResults=10" \
  -H "Authorization: Bearer {TOKEN}"

# Test specific issue
curl -X GET "{JIRA_SERVER}/rest/api/3/issue/{ISSUE_ID}" \
  -H "Authorization: Bearer {TOKEN}"
```

---

## 🚀 Your Jira integration is now ready for ATOM agent data ingestion!

**📝 Important Notes:**
- Use OAuth 2.0 for production (more secure than API tokens)
- Configure proper rate limiting to avoid hitting API limits
- Test thoroughly with your specific Jira instance
- Monitor API usage and costs (especially for Jira Cloud)

**🔧 Next Steps:**
1. Configure credentials in your `.env` file
2. Test authentication and API access
3. Customize JQL queries for your needs
4. Deploy integration to staging for testing
5. Monitor logs and performance in production