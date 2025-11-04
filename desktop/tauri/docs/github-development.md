# GitHub Integration - Development Guide

## Architecture Overview

The GitHub Integration follows a modular architecture with clear separation of concerns:

```
src/
├── components/services/github/
│   ├── GitHubDesktopManager.tsx     # UI Component
│   └── types/                      # TypeScript Types
├── skills/
│   ├── githubRepoSkill.ts           # Repository Management
│   ├── githubIssueSkill.ts         # Issue Management
│   ├── githubPullRequestSkill.ts   # PR Management
│   └── githubSkills.ts             # Exports
├── services/
│   └── nlpService.ts              # Natural Language Processing
└── types/
    └── skillTypes.ts               # Common Skill Types
```

## Core Concepts

### Skills Pattern
All GitHub operations follow the Skills pattern:

```typescript
interface Skill {
  execute(params: SkillParams, context: SkillExecutionContext): Promise<SkillResult>;
}

interface SkillResult {
  success: boolean;
  data?: any;
  error?: string;
  message?: string;
  timestamp: string;
}
```

### Natural Language Processing
The NLP service handles intent recognition and entity extraction:

```typescript
interface NLPResult {
  intent: Intent;
  entities: Entity[];
  confidence: number;
  processedText: string;
}
```

### Tauri Commands
Rust backend provides secure API endpoints:

```rust
#[tauri::command]
async fn get_github_user_repositories(
  user_id: String,
  limit: Option<u32>
) -> Result<Vec<GitHubRepository>, String>
```

## Development Setup

### Prerequisites
- Node.js 18+
- Rust 1.57+
- Tauri CLI
- Git

### Installation
```bash
# Clone repository
git clone <repository-url>
cd atom/desktop/tauri

# Install dependencies
npm install

# Install Tauri CLI
npm install -g @tauri-apps/cli

# Setup environment variables
cp .env.example .env
```

### Development Commands
```bash
# Start development server
npm run tauri dev

# Run tests
npm test

# Run integration tests
npm run test:integration

# Build for production
npm run tauri build

# Run GitHub tests only
npm run test:github
```

## Component Development

### GitHub Desktop Manager
The main UI component provides:

- **Connection Status**: Visual OAuth state
- **Repository Browser**: Tab-based repository interface
- **Issue Management**: List, create, and manage issues
- **PR Management**: Pull request overview and actions

#### State Management
```typescript
const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting' | 'error'>('disconnected');
const [userInfo, setUserInfo] = useState<GitHubUserInfo | null>(null);
const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
```

#### API Calls
```typescript
const loadUserData = async () => {
  setIsLoading(true);
  try {
    const repos = await invoke<GitHubRepository[]>('get_github_user_repositories', {
      userId: 'desktop-user',
      limit: 20
    });
    setRepositories(repos);
  } catch (error) {
    logger.error('Failed to load GitHub data', error);
  } finally {
    setIsLoading(false);
  }
};
```

### Skills Development

#### Creating New Skills
Follow the established pattern:

```typescript
export class GitHubCustomSkill implements Skill {
  async execute(params: GitHubCustomSkillParams, context: SkillExecutionContext): Promise<SkillResult> {
    try {
      const { action } = params;
      
      switch (action) {
        case 'custom_action':
          return await this.handleCustomAction(params, context);
        default:
          throw new Error(`Unknown action: ${action}`);
      }
    } catch (error) {
      return {
        success: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }
  }
  
  private async handleCustomAction(params: GitHubCustomSkillParams, context: SkillExecutionContext): Promise<SkillResult> {
    // Implementation
    return {
      success: true,
      data: { result: 'custom_result' },
      timestamp: new Date().toISOString()
    };
  }
}
```

#### Parameter Validation
Always validate input parameters:

```typescript
private validateParams(params: GitHubCustomSkillParams): void {
  if (!params.required_param) {
    throw new Error('Required parameter is missing');
  }
  
  if (this.isValidFormat(params.format_param)) {
    throw new Error('Invalid format parameter');
  }
}
```

#### Error Handling
Implement comprehensive error handling:

```typescript
private async handleAPIError(error: any): Promise<SkillResult> {
  if (error.response?.status === 401) {
    return {
      success: false,
      error: 'Authentication failed. Please reconnect GitHub.',
      timestamp: new Date().toISOString()
    };
  }
  
  if (error.response?.status === 429) {
    return {
      success: false,
      error: 'Rate limit exceeded. Please try again later.',
      timestamp: new Date().toISOString()
    };
  }
  
  return {
    success: false,
    error: `Unexpected error: ${error.message}`,
    timestamp: new Date().toISOString()
  };
}
```

## Backend Development

### Tauri Commands
Define secure Rust commands:

```rust
use serde::{Deserialize, Serialize};
use tauri::State;

#[derive(Serialize, Deserialize, Debug)]
pub struct GitHubRepository {
    pub id: i64,
    pub name: String,
    pub full_name: String,
    pub description: Option<String>,
    pub private: bool,
    pub html_url: String,
    pub stargazers_count: i32,
    pub forks_count: i32,
    pub open_issues_count: i32,
    pub language: Option<String>,
    pub created_at: String,
    pub updated_at: String,
}

#[tauri::command]
async fn get_github_user_repositories(
    user_id: String,
    limit: Option<u32>,
    state: State<AppState>
) -> Result<Vec<GitHubRepository>, String> {
    // Implementation
    Ok(repositories)
}
```

### Error Handling
Implement proper error handling:

```rust
#[derive(Debug, thiserror::Error)]
pub enum GitHubError {
    #[error("Authentication failed")]
    AuthenticationFailed,
    
    #[error("Rate limit exceeded")]
    RateLimitExceeded,
    
    #[error("Network error: {0}")]
    NetworkError(#[from] reqwest::Error),
    
    #[error("API error: {0}")]
    ApiError(String),
}

impl From<GitHubError> for String {
    fn from(error: GitHubError) -> Self {
        error.to_string()
    }
}
```

## Testing

### Unit Tests
Test individual components and skills:

```typescript
describe('GitHubRepoSkill', () => {
  let mockContext: SkillExecutionContext;

  beforeEach(() => {
    mockContext = {
      userId: 'test-user',
      sessionId: 'test-session',
      timestamp: '2025-11-02T10:00:00Z',
      intent: { name: 'github_list_repos', confidence: 0.9 },
      entities: [],
      confidence: 0.9
    };
  });

  it('should list repositories successfully', async () => {
    const { invoke } = await import('@tauri-apps/api/tauri');
    (invoke as any).mockResolvedValue(mockRepos);

    const result = await githubRepoSkill.execute({
      action: 'list',
      limit: 10
    }, mockContext);

    expect(result.success).toBe(true);
    expect(result.data?.repositories).toBeDefined();
  });
});
```

### Integration Tests
Test complete workflows:

```typescript
describe('GitHub Integration', () => {
  it('should complete full repository workflow', async () => {
    // 1. Authenticate
    const authResult = await invoke('get_github_oauth_url', { userId: 'test' });
    expect(authResult.success).toBe(true);

    // 2. List repositories
    const reposResult = await invoke('get_github_user_repositories', { 
      userId: 'test',
      limit: 10 
    });
    expect(reposResult).toBeDefined();

    // 3. Create repository
    const createResult = await invoke('create_github_repository', {
      userId: 'test',
      name: 'test-repo',
      description: 'Test repository'
    });
    expect(createResult.success).toBe(true);
  });
});
```

### Mock Data
Use consistent mock data factories:

```typescript
export class GitHubMockDataFactory {
  static createMockRepository(overrides: Partial<GitHubRepository> = {}): GitHubRepository {
    return {
      id: Math.floor(Math.random() * 1000000),
      name: 'mock-repo',
      full_name: 'user/mock-repo',
      description: 'Mock repository',
      private: false,
      html_url: 'https://github.com/user/mock-repo',
      stargazers_count: 42,
      forks_count: 15,
      open_issues_count: 8,
      language: 'TypeScript',
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2025-11-02T10:00:00Z',
      ...overrides
    };
  }
}
```

## Performance Optimization

### Caching Strategy
Implement multi-level caching:

```typescript
class GitHubCacheManager {
  private cache = new Map<string, CacheEntry>();
  private readonly TTL = {
    repositories: 5 * 60 * 1000,    // 5 minutes
    issues: 2 * 60 * 1000,         // 2 minutes
    pullRequests: 1 * 60 * 1000,   // 1 minute
    userInfo: 10 * 60 * 1000       // 10 minutes
  };

  async get<T>(key: string): Promise<T | null> {
    const entry = this.cache.get(key);
    if (entry && Date.now() - entry.timestamp < entry.ttl) {
      return entry.data;
    }
    return null;
  }

  set<T>(key: string, data: T, ttl: number): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl
    });
  }
}
```

### Batch Operations
Process multiple items efficiently:

```typescript
async function batchProcessIssues(
  issues: GitHubIssue[],
  processor: (issue: GitHubIssue) => Promise<void>
): Promise<void> {
  const BATCH_SIZE = 10;
  for (let i = 0; i < issues.length; i += BATCH_SIZE) {
    const batch = issues.slice(i, i + BATCH_SIZE);
    await Promise.all(batch.map(processor));
  }
}
```

### Memory Management
Implement cleanup strategies:

```typescript
class GitHubMemoryManager {
  private readonly MAX_CACHE_SIZE = 100;
  private readonly CLEANUP_INTERVAL = 5 * 60 * 1000; // 5 minutes

  constructor() {
    setInterval(() => this.cleanup(), this.CLEANUP_INTERVAL);
  }

  private cleanup(): void {
    // Remove old entries
    // Free unused memory
    // Maintain cache size limits
  }
}
```

## Security Considerations

### Token Management
Secure token storage and transmission:

```typescript
class GitHubTokenManager {
  private async encryptToken(token: string): Promise<string> {
    const encoder = new TextEncoder();
    const data = encoder.encode(token);
    const key = await crypto.subtle.generateKey(
      { name: 'AES-GCM', length: 256 },
      true,
      ['encrypt', 'decrypt']
    );
    return await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv: crypto.getRandomValues(new Uint8Array(12)) },
      key,
      data
    );
  }

  private async decryptToken(encrypted: string): Promise<string> {
    // Decryption logic
  }
}
```

### Input Validation
Validate all user inputs:

```typescript
function validateRepositoryName(name: string): boolean {
  const validPattern = /^[a-zA-Z0-9._-]+$/;
  return name.length >= 1 && name.length <= 100 && validPattern.test(name);
}

function sanitizeSearchQuery(query: string): string {
  return query
    .replace(/[<>]/g, '') // Remove HTML tags
    .replace(/[;&]/g, '') // Remove dangerous characters
    .substring(0, 1000);  // Limit length
}
```

### Permission Checks
Verify user permissions:

```typescript
async function verifyRepositoryAccess(
  userId: string,
  owner: string,
  repo: string
): Promise<boolean> {
  try {
    await invoke('get_github_repository', { userId, owner, repo });
    return true;
  } catch (error) {
    return false;
  }
}
```

## Debugging

### Logging
Use structured logging:

```typescript
class Logger {
  info(message: string, data?: any): void {
    console.log(`[INFO] ${new Date().toISOString()} ${message}`, data);
  }

  error(message: string, error?: any): void {
    console.error(`[ERROR] ${new Date().toISOString()} ${message}`, error);
  }

  debug(message: string, data?: any): void {
    if (process.env.NODE_ENV === 'development') {
      console.debug(`[DEBUG] ${new Date().toISOString()} ${message}`, data);
    }
  }
}
```

### Error Reporting
Implement comprehensive error tracking:

```typescript
class GitHubErrorReporter {
  report(error: GitHubError, context: ErrorContext): void {
    const errorReport = {
      message: error.message,
      stack: error.stack,
      context: {
        userId: context.userId,
        action: context.action,
        timestamp: context.timestamp
      }
    };

    // Send to error tracking service
    this.sendErrorReport(errorReport);
  }
}
```

### Performance Monitoring
Monitor key metrics:

```typescript
class GitHubPerformanceMonitor {
  trackAPIRequest(endpoint: string, duration: number): void {
    const metric = {
      endpoint,
      duration,
      timestamp: Date.now()
    };

    this.recordMetric(metric);
  }

  trackUserAction(action: string, duration: number): void {
    const metric = {
      action,
      duration,
      timestamp: Date.now()
    };

    this.recordMetric(metric);
  }
}
```

## Deployment

### Build Process
Optimize for production:

```bash
# Build frontend
npm run build

# Build Tauri app
npm run tauri build

# Package for distribution
npm run tauri build -- --target x86_64-apple-darwin
```

### Environment Configuration
Configure for different environments:

```typescript
const config = {
  development: {
    apiURL: 'http://localhost:8083',
    debug: true,
    cacheEnabled: false
  },
  production: {
    apiURL: 'https://api.atom.com',
    debug: false,
    cacheEnabled: true
  }
};

const currentConfig = config[process.env.NODE_ENV || 'development'];
```

### Version Management
Follow semantic versioning:

```json
{
  "name": "atom-desktop",
  "version": "1.3.0",
  "build": 20251102001,
  "releaseNotes": "Added GitHub integration with full repository management"
}
```

## Contributing

### Code Style
Follow established conventions:

```typescript
// Use PascalCase for classes
class GitHubRepositoryManager {}

// Use camelCase for variables and functions
const repositoryList = [];

// Use UPPER_SNAKE_CASE for constants
const MAX_REPOSITORIES = 1000;

// Use descriptive names
function calculateRepositoryHealth(repository: GitHubRepository): number {}
```

### Testing Requirements
All changes must include:

1. **Unit Tests**: Test individual functions
2. **Integration Tests**: Test complete workflows
3. **Error Tests**: Test error conditions
4. **Performance Tests**: Test response times

### Documentation
Update documentation for:

1. **API Changes**: New or modified endpoints
2. **UI Changes**: Component updates
3. **Configuration**: New settings or options
4. **Examples**: Usage examples and best practices

## Troubleshooting

### Common Development Issues

#### Build Errors
```bash
# Clear build cache
npm run clean

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

#### Test Failures
```bash
# Update test dependencies
npm update vitest @vitest/ui

# Clear test cache
npx vitest --run --clear-cache
```

#### Tauri Issues
```bash
# Check Tauri installation
npx tauri --version

# Reinstall Tauri CLI
npm uninstall -g @tauri-apps/cli
npm install -g @tauri-apps/cli
```

### Debug Commands
Enable detailed logging:

```bash
# Development
DEBUG=github:* npm run tauri dev

# Testing
DEBUG=github:* npm test

# Production
RUST_LOG=debug npm run tauri build
```

---

*Last Updated: November 2, 2025*
*Version: 1.3.0*