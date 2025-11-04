# GitHub Integration Setup Guide

## 1. Create GitHub OAuth App

### For GitHub Personal Access Token (Recommended):
1. Go to: https://github.com/settings/tokens
2. Click "**Generate new token**" (classic)
3. Fill in the form:
   - **Note**: ATOM Agent Integration
   - **Expiration**: 90 days (recommended)
   - **Scopes**: 
     - ✅ **repo** (Full control of private repositories)
     - ✅ **public_repo** (Access public repositories)
     - ✅ **read:org** (Read org and team membership)
     - ✅ **read:user** (Read user profile data)
     - ✅ **user:email** (Read user email addresses)
     - ✅ **read:discussion** (Read team discussions)
     - ✅ **read:enterprise** (Read enterprise data)
     - ✅ **read:gpg_key** (Read GPG keys)
     - ✅ **read:ssh_signing_key** (Read SSH signing keys)
     - ✅ **read:project** (Read project boards)

4. Click "**Generate token**"
5. **Copy the token immediately** (it won't be shown again)

### For GitHub OAuth App (Advanced):
1. Go to: https://github.com/settings/applications/new
2. Fill in the form:
   - **Application name**: ATOM Agent Integration
   - **Homepage URL**: Your application URL
   - **Authorization callback URL**: `https://your-domain.com/oauth/github/callback`
3. Click "**Register application**"
4. Note down the **Client ID** and generate a **Client Secret**

## 2. Repository Permissions

### For Personal Access Token:
The token permissions automatically apply to repositories the user can access.

### For OAuth App:
1. After authorization, the app has access based on granted scopes
2. For private repositories, users must explicitly grant access
3. For organization repositories, organization approval may be required

## 3. Environment Variables

Add to your `.env` file:

```bash
# GitHub Personal Access Token (Recommended)
GITHUB_PERSONAL_ACCESS_TOKEN=your_github_personal_access_token

# GitHub OAuth App (Advanced)
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=https://your-domain.com/oauth/github/callback

# For OAuth (if using OAuth)
GITHUB_OAUTH_TOKEN=your_github_oauth_token
GITHUB_OAUTH_REFRESH_TOKEN=your_github_oauth_refresh_token
```

## 4. Rate Limits and Quotas

### GitHub Rate Limits:
- **Unauthenticated**: 60 requests per hour
- **Personal Access Token**: 5000 requests per hour
- **OAuth App**: 5000 requests per hour

### Best Practices:
1. **Use Personal Access Token**: Higher rate limits
2. **Cache responses**: Cache repository metadata and user info
3. **Use GraphQL**: More efficient for complex queries
4. **Batch requests**: Use pagination efficiently
5. **Implement retry logic**: Use exponential backoff
6. **Monitor rate limits**: Check X-RateLimit headers

## 5. GitHub API Configuration

### API Endpoints:
- **REST API**: `https://api.github.com`
- **GraphQL API**: `https://api.github.com/graphql`
- **GitHub Actions API**: `https://api.github.com`
- **GitHub Packages API**: `https://api.github.com`

### Configuration Options:
```bash
# API Configuration
GITHUB_API_BASE_URL=https://api.github.com
GITHUB_GRAPHQL_URL=https://api.github.com/graphql

# Request Settings
GITHUB_REQUEST_TIMEOUT=30000
GITHUB_MAX_RETRIES=3
GITHUB_RETRY_DELAY=1000

# Pagination
GITHUB_DEFAULT_PAGE_SIZE=100
GITHUB_MAX_PAGE_SIZE=100
```

## 6. Test Connection

### Test Personal Access Token:
```bash
curl -X GET "https://api.github.com/user" \
  -H "Authorization: token YOUR_PERSONAL_ACCESS_TOKEN"
```

### Test OAuth App:
```bash
curl -X GET "https://api.github.com/user" \
  -H "Authorization: Bearer YOUR_OAUTH_TOKEN"
```

### Test Rate Limits:
```bash
curl -X GET "https://api.github.com/rate_limit" \
  -H "Authorization: token YOUR_TOKEN"
```

## 7. Repository Access

### Discover User Repositories:
```bash
curl -X GET "https://api.github.com/user/repos?type=all&sort=updated&direction=desc&per_page=100" \
  -H "Authorization: token YOUR_TOKEN"
```

### Discover Organization Repositories:
```bash
curl -X GET "https://api.github.com/orgs/ORGNAME/repos?type=all&sort=updated&direction=desc&per_page=100" \
  -H "Authorization: token YOUR_TOKEN"
```

### Test Repository Access:
```bash
curl -X GET "https://api.github.com/repos/OWNER/REPO" \
  -H "Authorization: token YOUR_TOKEN"
```

## 8. Advanced Configuration

### Webhook Configuration (Optional):
1. Go to repository settings → Webhooks
2. Click "**Add webhook**"
3. Configure:
   - **Payload URL**: `https://your-domain.com/api/webhooks/github`
   - **Content type**: `application/json`
   - **Secret**: Your webhook secret
   - **Events**: 
     - ✅ **Pushes**
     - ✅ **Issues**
     - ✅ **Pull requests**
     - ✅ **Releases**
     - ✅ **Repository**

### GitHub Actions Integration:
```bash
# GitHub Actions Token
GITHUB_ACTIONS_TOKEN=your_github_actions_token

# Workflow Configuration
GITHUB_WORKFLOW_ENABLED=true
GITHUB_WORKFLOW_EVENTS=push,pull_request,release
```

### GitHub GraphQL Examples:
```graphql
query {
  user(login: "your-username") {
    repositories(first: 100, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        name
        fullName: nameWithOwner
        description
        isPrivate: isPrivate
        primaryLanguage {
          name
        }
        stargazerCount
        forkCount
        createdAt
        updatedAt
        defaultBranchRef {
          name
        }
      }
    }
  }
}
```

## 9. Search Configuration

### Repository Search:
```bash
curl -X GET "https://api.github.com/search/repositories?q=language:typescript+stars:>100&sort=stars&order=desc&per_page=100" \
  -H "Authorization: token YOUR_TOKEN"
```

### Issue Search:
```bash
curl -X GET "https://api.github.com/search/issues?q=repo:OWNER/REPO+state:open&sort=created&order=desc&per_page=100" \
  -H "Authorization: token YOUR_TOKEN"
```

### Code Search:
```bash
curl -X GET "https://api.github.com/search/code?q=filename:README+repo:OWNER/REPO&sort=indexed&order=desc&per_page=100" \
  -H "Authorization: token YOUR_TOKEN"
```

## 10. Integration Testing

### Test Workflow:
1. **Test authentication**: Verify token or OAuth access
2. **Test repository access**: List user repositories
3. **Test issue retrieval**: Fetch issues from repositories
4. **Test pull request access**: Get pull requests
5. **Test commit history**: Retrieve commit data
6. **Test file access**: Download repository files
7. **Test search functionality**: Search repositories and issues
8. **Test webhook delivery**: Verify webhook events

### Sample Test Code:
```javascript
// Test GitHub API
const testGitHub = async () => {
  try {
    // Test authentication
    const user = await fetch('https://api.github.com/user', {
      headers: { 'Authorization': `token ${TOKEN}` }
    }).then(r => r.json());
    console.log('Authenticated as:', user.login);
    
    // Test repositories
    const repos = await fetch('https://api.github.com/user/repos?per_page=10', {
      headers: { 'Authorization': `token ${TOKEN}` }
    }).then(r => r.json());
    console.log('Found repositories:', repos.length);
    
    // Test issues
    if (repos.length > 0) {
      const [owner, repo] = repos[0].full_name.split('/');
      const issues = await fetch(`https://api.github.com/repos/${owner}/${repo}/issues?per_page=5`, {
        headers: { 'Authorization': `token ${TOKEN}` }
      }).then(r => r.json());
      console.log('Found issues:', issues.length);
    }
    
    console.log('✅ GitHub integration test passed');
  } catch (error) {
    console.error('❌ GitHub integration test failed:', error);
  }
};
```

## 11. Security Considerations

### Token Security:
- Store tokens securely in environment variables
- Use least privilege principle (only necessary scopes)
- Rotate tokens regularly (every 90 days)
- Monitor token usage and audit logs
- Revoke unused or compromised tokens

### Repository Access:
- Only grant access to necessary repositories
- Use organization-level permissions for team access
- Implement proper access controls
- Monitor repository access logs
- Use branch protection and PR policies

### Webhook Security:
- Use secure webhook URLs (HTTPS)
- Implement webhook secret verification
- Validate webhook payloads
- Use IP allowlisting if possible
- Monitor webhook delivery logs

## 12. Troubleshooting

### Common Issues:
- **401 Unauthorized**: Check token validity and permissions
- **403 Forbidden**: Rate limit exceeded or insufficient permissions
- **404 Not Found**: Repository doesn't exist or no access
- **422 Unprocessable Entity**: Invalid request parameters
- **500 Internal Server Error**: GitHub API error

### Solutions:
- Verify token scopes and permissions
- Check rate limit status
- Validate repository names and URLs
- Implement proper error handling
- Use retry logic for transient errors

### Rate Limit Issues:
- Monitor X-RateLimit-Remaining header
- Implement proper rate limiting
- Use GraphQL for more efficient queries
- Cache responses when appropriate
- Use pagination for large datasets

---

## 🚀 Your GitHub integration is now ready for ATOM agent data ingestion!

**📝 Important Notes:**
- Use Personal Access Token for simplicity and higher rate limits
- Configure proper repository filtering to avoid hitting limits
- Test thoroughly with your specific repositories
- Monitor API usage and costs
- Use webhooks for real-time updates (optional)

**🔧 Next Steps:**
1. Generate a Personal Access Token with appropriate scopes
2. Configure credentials in your `.env` file
3. Test authentication and repository access
4. Customize repository and issue filtering
5. Deploy integration to staging for testing
6. Monitor logs and performance in production
7. Consider setting up webhooks for real-time sync (optional)