# 🚀 Enhanced GitHub Integration

## Overview

The enhanced GitHub integration provides comprehensive API coverage for GitHub with enterprise-grade features including repository management, issue tracking, pull request automation, workflow management, and advanced search capabilities.

## 🌟 Key Features

### Core Capabilities
- **User & Organization Management** - Profile information, organization membership, team management
- **Repository Operations** - Repository creation, branch management, file operations
- **Issue Tracking** - Issue creation, label management, assignee tracking
- **Pull Request Management** - PR creation, code review workflows, merge operations
- **Workflow Automation** - GitHub Actions integration, workflow monitoring
- **Advanced Search** - Code search, issue search, cross-organization filtering
- **Webhook Integration** - Real-time event notifications, custom webhook configuration

## 📁 File Structure

```
atom/backend/consolidated/integrations/
├── github_service.py           # Main GitHub service class
├── github_routes.py            # Flask routes for GitHub API
├── test_github_service.py      # Unit tests for service
├── test_github_routes.py       # Unit tests for routes
├── test_github_integration.py  # Integration tests
├── demo_github_integration.py  # Demonstration script
└── GITHUB_INTEGRATION_COMPLETE.md  # Comprehensive documentation
```

## 🛠️ Quick Start

### 1. Environment Setup

```bash
# Set GitHub OAuth credentials
export GITHUB_CLIENT_ID=your_client_id
export GITHUB_CLIENT_SECRET=your_client_secret
export GITHUB_REDIRECT_URI=http://localhost:3000/api/integrations/github/callback

# Optional: Set access token directly
export GITHUB_ACCESS_TOKEN=your_personal_access_token
```

### 2. Basic Usage

```python
from github_service import GitHubService

# Initialize service
github_service = GitHubService()

# Set access token
github_service.set_access_token("your_access_token")

# Get user profile
profile = github_service.get_user_profile()
print(f"User: {profile['login']}")

# List repositories
repos = github_service.get_repositories()
for repo in repos:
    print(f"Repository: {repo['name']}")
```

### 3. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/github/status` | Integration status |
| `POST` | `/api/github/auth/set-token` | Set access token |
| `GET` | `/api/github/user/profile` | User profile |
| `GET` | `/api/github/repositories` | List repositories |
| `POST` | `/api/github/repositories` | Create repository |
| `GET` | `/api/github/repositories/{owner}/{repo}/issues` | List issues |
| `POST` | `/api/github/repositories/{owner}/{repo}/issues` | Create issue |
| `GET` | `/api/github/search/code` | Search code |
| `GET` | `/api/github/rate-limit` | Rate limit status |

## 🔧 Configuration

### Environment Variables

```bash
# Required for OAuth
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
GITHUB_REDIRECT_URI=your_redirect_uri

# Optional
GITHUB_API_TIMEOUT=30
GITHUB_MAX_RETRIES=3
```

### Required OAuth Scopes

```yaml
user:
  - read:user
  - user:email
repo:
  - repo
  - repo:status
workflow:
  - workflow
```

## 🧪 Testing

### Run Unit Tests

```bash
# Service tests
python -m pytest test_github_service.py -v

# Route tests  
python -m pytest test_github_routes.py -v

# Integration tests
python test_github_integration.py
```

### Run Demo

```bash
# Run comprehensive demo
python demo_github_integration.py

# With access token for full functionality
export GITHUB_ACCESS_TOKEN=your_token
python demo_github_integration.py
```

## 📚 API Examples

### Repository Management

```python
# Create repository
repo = github_service.create_repository(
    name="my-project",
    description="A new project",
    private=True,
    auto_init=True
)

# Get repository details
repo_details = github_service.get_repository("owner", "repo-name")

# List branches
branches = github_service.get_branches("owner", "repo-name")
```

### Issue Tracking

```python
# Create issue
issue = github_service.create_issue(
    owner="organization",
    repo="repository", 
    title="Bug Report",
    body="Detailed description...",
    labels=["bug", "high-priority"],
    assignees=["developer1"]
)

# Search issues
issues = github_service.search_issues("bug label:high-priority")
```

### Pull Request Management

```python
# Create pull request
pr = github_service.create_pull_request(
    owner="organization",
    repo="repository",
    title="New Feature",
    head="feature-branch",
    base="main",
    body="Implementation details..."
)

# Add code review
review = github_service.create_pull_request_review(
    owner="organization",
    repo="repository",
    pull_number=pr["number"],
    body="Great work! Minor suggestions.",
    event="APPROVE"
)
```

### Search Operations

```python
# Search code
code_results = github_service.search_code("def main()", org="organization")

# Search issues
issue_results = github_service.search_issues("bug fix", org="organization")
```

## 🔒 Security & Best Practices

### Rate Limiting
- Automatic rate limit monitoring
- Exponential backoff for retries
- Request queuing when approaching limits

### Error Handling
```python
try:
    result = github_service._make_request("GET", "/user")
    if result is None:
        logger.error("API request failed")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
```

### Token Security
- Encrypted token storage
- Token refresh mechanisms
- Minimal scope requests
- Audit logging

## 📊 Monitoring

### Health Checks
```python
health = github_service.health_check()
print(f"Status: {health['status']}")
print(f"Rate Limit: {health['rate_limit_remaining']}")
```

### Key Metrics
- API response times
- Error rates
- Rate limit utilization
- User activity patterns

## 🚀 Advanced Features

### Workflow Automation
```python
# Get workflow runs
workflow_runs = github_service.get_workflow_runs("owner", "repo")

# Trigger workflow
github_service.trigger_workflow("owner", "repo", "ci.yml", "main")
```

### Webhook Management
```python
# Create webhook
webhook = github_service.create_webhook(
    owner="owner",
    repo="repo", 
    url="https://example.com/webhook",
    events=["push", "pull_request"]
)
```

## 🔮 Future Enhancements

### Planned Features
- AI-powered code review suggestions
- Repository analytics dashboard
- Advanced security scanning
- Real-time webhook processing
- Bulk operations support

## 🆘 Troubleshooting

### Common Issues

1. **Authentication Failures**
   - Verify token validity and scopes
   - Check OAuth app configuration

2. **Rate Limiting**
   - Monitor rate limit headers
   - Implement request queuing

3. **Permission Errors**
   - Verify repository access
   - Check organization permissions

### Debugging

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Test connectivity
profile = github_service.get_user_profile()
limits = github_service.get_rate_limit()
```

## 📖 Additional Resources

- [GitHub REST API Documentation](https://docs.github.com/en/rest)
- [GitHub OAuth App Guide](https://docs.github.com/en/developers/apps)
- [Complete Integration Documentation](GITHUB_INTEGRATION_COMPLETE.md)

---

**Built with ❤️ by the ATOM Team**

*Version: 2.0.0*  
*Last Updated: December 2023*