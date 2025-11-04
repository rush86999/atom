# GitHub Integration Documentation

## Overview

The ATOM GitHub Integration provides comprehensive GitHub repository, issue, and pull request management capabilities through natural language commands and a modern desktop interface.

## Features

### 🔐 Authentication
- **OAuth 2.0 Flow**: Secure authentication with GitHub
- **Token Management**: Encrypted token storage and refresh
- **Scope Management**: Configurable access permissions
- **Connection Monitoring**: Real-time status updates

### 📚 Repository Management
- **Browse Repositories**: View user and organization repositories
- **Search Repositories**: Find repositories by name, language, or topics
- **Create Repositories**: Initialize new repositories with options
- **Repository Analytics**: Detailed statistics and health metrics
- **Repository Updates**: Modify repository settings and metadata

### 🐛 Issue Management
- **Issue Listing**: Filter and search repository issues
- **Issue Creation**: Create issues with labels and assignees
- **Issue Updates**: Modify status, assignees, and metadata
- **Issue Analytics**: Priority distribution and resolution tracking
- **Bulk Operations**: Manage multiple issues efficiently

### 🔄 Pull Request Management
- **PR Listing**: View open, closed, and merged pull requests
- **PR Creation**: Create pull requests from branches
- **PR Analytics**: Complexity scoring and risk assessment
- **Review Management**: Request reviews and track status
- **Merge Operations**: Support for different merge strategies

### 🤖 Natural Language Interface
- **Plain English Commands**: Simple, intuitive commands
- **Context Awareness**: Smart parameter extraction
- **Suggestions**: Context-aware recommendations
- **Quick Actions**: Pre-defined common operations

## Getting Started

### 1. Connect GitHub

#### Method 1: Desktop Manager
1. Navigate to **Settings** → **GitHub Integration**
2. Click **"Connect GitHub"**
3. Complete OAuth in browser
4. Grant required permissions

#### Method 2: Natural Language
```
"Connect GitHub" or "GitHub help"
```

### 2. Basic Commands

#### Repository Commands
```bash
# List repositories
"Show me my repositories"
"List my repositories"
"My repos"

# Create repository
"Create repository 'my-project' with description 'My awesome project'"
"New repository 'awesome-app' private with TypeScript"

# Search repositories
"Search repositories for 'react components'"
"Find repos with 'machine learning' language"
```

#### Issue Commands
```bash
# List issues
"Show me open issues for atomcompany/atom-desktop"
"List closed issues in my-repo"
"Issues for owner/repo"

# Create issue
"Create issue 'Add GitHub integration' with labels 'feature, enhancement'"
"New issue 'Bug in login page' assigned to developer1"
"Report issue 'API timeout' in atomcompany/api"

# Search issues
"Search issues for 'bug' in atomcompany/atom-desktop"
"Find issues labeled 'urgent'"
```

#### Pull Request Commands
```bash
# List pull requests
"Show me open pull requests for atomcompany/atom-desktop"
"List PRs in my-repo"
"Pull requests for owner/repo"

# Create pull request
"Create PR 'Add feature' from feature-branch to main"
"New pull request 'Fix bug' from hotfix to develop"
"PR 'Update docs' from docs-update to main"

# Search pull requests
"Search PRs for 'integration' in atomcompany/atom-desktop"
"Find pull requests labeled 'bug-fix'"
```

## Advanced Features

### Repository Analytics

#### Health Score
Repository health is calculated based on:
- **README Presence**: +5 points for README
- **License**: +3 points for license
- **Documentation**: +2 points for wiki/docs
- **Activity**: Recent commits and issues
- **Community**: Stars, forks, and contributors

#### Popularity Metrics
```typescript
interface PopularityScore {
  stars: number;        // Weight: 60%
  forks: number;        // Weight: 30%
  watchers: number;     // Weight: 10%
  totalScore: number;
}
```

#### Activity Level
```typescript
interface ActivityMetrics {
  issueActivity: number;    // Weight: 30%
  commitActivity: number;   // Weight: 50%
  contributionActivity: number; // Weight: 20%
  recencyMultiplier: number;  // Decay over time
}
```

### Issue Management

#### Priority Classification
Issues are automatically classified as:
- **Critical**: Security issues, critical bugs
- **High**: Important bugs, breaking changes
- **Medium**: New features, moderate bugs
- **Low**: Documentation, minor improvements

#### Complexity Assessment
```typescript
interface IssueComplexity {
  descriptionLength: number;  // Weight: 30%
  labelCount: number;        // Weight: 25%
  commentCount: number;      // Weight: 20%
  assigneeCount: number;     // Weight: 25%
  totalScore: number;
  category: 'low' | 'medium' | 'high';
}
```

#### Resolution Analytics
```typescript
interface ResolutionMetrics {
  averageResolutionTime: number;
  closureRate: number;
  firstResponseTime: number;
  engagementRate: number;
}
```

### Pull Request Management

#### Risk Assessment
Pull request risk is evaluated based on:
- **Code Changes**: Number of files and lines changed
- **Commit History**: Number of commits
- **Age**: Time since creation
- **Review Status**: Code review completeness
- **Conflicts**: Merge conflict presence

#### Merge Strategies
- **Squash Merge**: Single commit with all changes
- **Regular Merge**: Preserve commit history
- **Rebase Merge**: Rebase onto target branch

#### Review Workflow
```typescript
interface ReviewWorkflow {
  automaticReview: boolean;    // Auto-assign reviewers
  requiredReviewers: number;    // Minimum required reviewers
  approvalThreshold: number;    // Required approvals
  changeRequestHandling: 'strict' | 'flexible';
}
```

## API Reference

### Authentication Commands

#### Get OAuth URL
```typescript
const result = await invoke('get_github_oauth_url', {
  userId: string
});
```

#### Exchange OAuth Code
```typescript
const result = await invoke('exchange_github_oauth_code', {
  code: string,
  state: string
});
```

#### Check Connection
```typescript
const result = await invoke('get_github_connection', {
  userId: string
});
```

### Repository Commands

#### List Repositories
```typescript
const repos = await invoke('get_github_user_repositories', {
  userId: string,
  limit?: number
});
```

#### Search Repositories
```typescript
const results = await invoke('search_github_repositories', {
  userId: string,
  query: string,
  limit?: number
});
```

#### Create Repository
```typescript
const result = await invoke('create_github_repository', {
  userId: string,
  name: string,
  description?: string,
  private?: boolean,
  language?: string
});
```

### Issue Commands

#### List Issues
```typescript
const issues = await invoke('get_github_repository_issues', {
  userId: string,
  owner: string,
  repo: string,
  state?: 'open' | 'closed' | 'all',
  limit?: number
});
```

#### Create Issue
```typescript
const result = await invoke('create_github_issue', {
  userId: string,
  owner: string,
  repo: string,
  title: string,
  body?: string,
  labels?: string[],
  assignees?: string[]
});
```

### Pull Request Commands

#### List Pull Requests
```typescript
const prs = await invoke('get_github_pull_requests', {
  userId: string,
  owner: string,
  repo: string,
  state?: 'open' | 'closed' | 'all',
  limit?: number
});
```

#### Create Pull Request
```typescript
const result = await invoke('create_github_pull_request', {
  userId: string,
  owner: string,
  repo: string,
  title: string,
  body?: string,
  head: string,
  base: string
});
```

## Configuration

### Scopes
The integration requests the following GitHub scopes:

| Scope | Purpose | Required |
|--------|---------|----------|
| `repo` | Full repository access | ✅ |
| `user` | User profile access | ✅ |
| `issues` | Issue management | ✅ |
| `pull_requests` | Pull request operations | ✅ |

### Settings
Configuration options available in Settings:

| Setting | Description | Default |
|---------|-------------|----------|
| Auto-refresh | Enable automatic data refresh | ✅ |
| Refresh interval | Minutes between refreshes | 5 |
| Notifications | Show desktop notifications | ✅ |
| Cache size | Maximum cached items | 100 |
| Default branch | Default branch for new repos | main |

## Troubleshooting

### Common Issues

#### Connection Problems
**Issue**: GitHub connection fails
**Solution**: 
1. Check internet connection
2. Verify GitHub credentials
3. Clear browser cookies
4. Re-authenticate

#### API Rate Limits
**Issue**: "API rate limit exceeded" error
**Solution**:
1. Wait for rate limit reset
2. Reduce request frequency
3. Use authentication headers

#### Repository Access
**Issue**: Cannot access private repositories
**Solution**:
1. Verify repository permissions
2. Check OAuth scopes
3. Ensure correct authentication

#### Token Expiration
**Issue**: Tokens expire frequently
**Solution**:
1. Enable automatic token refresh
2. Check token expiration time
3. Manually refresh tokens

### Error Codes

| Code | Description | Solution |
|-------|-------------|-----------|
| AUTH_001 | Invalid OAuth code | Re-authenticate |
| AUTH_002 | Expired tokens | Refresh tokens |
| API_001 | Rate limit exceeded | Wait and retry |
| API_002 | Invalid repository | Check repository name |
| API_003 | Permission denied | Verify access rights |
| NET_001 | Network error | Check connection |

### Debug Mode

Enable debug mode for detailed logging:

```typescript
// In console
localStorage.setItem('github_debug', 'true');
```

Debug logs include:
- API request/response details
- Token management events
- Error stack traces
- Performance metrics

## Performance

### Optimization Features

#### Caching
- **Repository Data**: 5 minute cache
- **Issue Data**: 2 minute cache
- **Pull Request Data**: 1 minute cache
- **User Data**: 10 minute cache

#### Batch Operations
- **Bulk Issue Updates**: Process 50 issues per batch
- **Multi-repo Operations**: Parallel repository access
- **Efficient Searching**: Index-based search

#### Memory Management
- **Data Pagination**: Limit loaded items
- **Lazy Loading**: Load data on demand
- **Cache Cleanup**: Remove old entries

### Metrics

#### Response Times
- **Authentication**: < 500ms
- **Repository List**: < 1s
- **Issue Search**: < 2s
- **Pull Request List**: < 1.5s

#### Data Limits
- **Repositories**: 1000 max
- **Issues**: 5000 max
- **Pull Requests**: 2000 max
- **Cache Size**: 100MB max

## Security

### Token Management
- **Encryption**: AES-256-GCM encryption
- **Storage**: Secure system keychain
- **Rotation**: Automatic token refresh
- **Revocation**: Secure token invalidation

### Data Protection
- **Local Storage**: Encrypted at rest
- **Transmission**: HTTPS/TLS encryption
- **Access Control**: Role-based permissions
- **Audit Logging**: Operation tracking

### Privacy Features
- **Data Minimization**: Only required data
- **Local Processing**: No external data sharing
- **User Consent**: Explicit permission requests
- **Data Deletion**: Complete removal on request

## Integration

### Other Services
GitHub Integration works seamlessly with:
- **Outlook Integration**: Issue notifications via email
- **Jira Integration**: Bidirectional issue sync
- **Slack Integration**: Real-time notifications
- **Notion Integration**: Repository documentation

### Webhooks
Configure webhooks for real-time updates:
1. Navigate to repository settings
2. Add webhook URL
3. Select event types
4. Configure security settings

### API Extensions
Extend functionality with custom skills:
```typescript
class CustomGitHubSkill implements Skill {
  async execute(params, context) {
    // Custom logic
  }
}
```

## Best Practices

### Repository Management
- Use descriptive names
- Maintain README files
- Use appropriate licenses
- Set up branch protection

### Issue Management
- Use clear titles
- Provide detailed descriptions
- Apply relevant labels
- Set proper assignees

### Pull Request Management
- Use descriptive titles
- Provide clear descriptions
- Keep PRs focused
- Request appropriate reviews

### Security
- Use strong passwords
- Enable two-factor authentication
- Regularly review access
- Monitor for suspicious activity

## Updates

### Version History
- **v1.0.0**: Initial release
- **v1.1.0**: Added pull request management
- **v1.2.0**: Enhanced analytics
- **v1.3.0**: Natural language improvements

### Upcoming Features
- **Repository Templates**: Pre-configured repository templates
- **Advanced Search**: Enhanced search with filters
- **Automation**: Custom workflows and actions
- **Collaboration Tools**: Enhanced team features

### Migration Guide
When upgrading versions:
1. Backup current configuration
2. Update application
3. Test authentication
4. Verify data integrity
5. Restore settings if needed

## Support

### Getting Help
- **Documentation**: Complete API reference
- **Troubleshooting**: Common issues and solutions
- **Community**: User forums and discussions
- **Contact**: Direct support channels

### Contributing
- **Code Repository**: GitHub development repo
- **Issue Reporting**: Bug reports and feature requests
- **Pull Requests**: Code contributions
- **Documentation**: Documentation improvements

### Feedback
Provide feedback through:
- In-app feedback forms
- GitHub issues
- Community forums
- Direct contact

---

*Last Updated: November 2, 2025*
*Version: 1.3.0*