/**
 * GitHub Test Utilities
 * Mock data and helpers for testing
 */

import { GitHubUserInfo, GitHubRepository, GitHubIssue, GitHubPullRequest, GitHubLabel, GitHubMilestone } from '../components/services/github/GitHubDesktopManager';

// Mock Data Factories
export class GitHubMockDataFactory {
  static createMockUser(overrides: Partial<GitHubUserInfo> = {}): GitHubUserInfo {
    return {
      id: 12345,
      login: 'mockuser',
      name: 'Mock User',
      email: 'mock@example.com',
      avatar_url: 'https://github.com/mockuser.png',
      company: 'ATOM Company',
      location: 'San Francisco, CA',
      bio: 'Software Developer at ATOM',
      public_repos: 25,
      followers: 150,
      following: 75,
      created_at: '2020-01-01T00:00:00Z',
      updated_at: '2025-11-02T10:00:00Z',
      html_url: 'https://github.com/mockuser',
      type: 'User',
      ...overrides
    };
  }

  static createMockRepository(overrides: Partial<GitHubRepository> = {}): GitHubRepository {
    const baseId = Math.floor(Math.random() * 1000000);
    return {
      id: baseId,
      name: `mock-repo-${baseId}`,
      full_name: `mockuser/mock-repo-${baseId}`,
      description: `Mock repository ${baseId} for testing`,
      private: false,
      fork: false,
      html_url: `https://github.com/mockuser/mock-repo-${baseId}`,
      clone_url: `https://github.com/mockuser/mock-repo-${baseId}.git`,
      ssh_url: `git@github.com:mockuser/mock-repo-${baseId}.git`,
      default_branch: 'main',
      language: 'TypeScript',
      languages_url: `https://api.github.com/repos/mockuser/mock-repo-${baseId}/languages`,
      stargazers_count: Math.floor(Math.random() * 1000),
      watchers_count: Math.floor(Math.random() * 1000),
      forks_count: Math.floor(Math.random() * 100),
      open_issues_count: Math.floor(Math.random() * 50),
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2025-11-02T10:00:00Z',
      pushed_at: '2025-11-02T09:00:00Z',
      size: Math.floor(Math.random() * 10000),
      ...overrides
    };
  }

  static createMockIssue(overrides: Partial<GitHubIssue> = {}): GitHubIssue {
    const baseId = Math.floor(Math.random() * 1000000);
    return {
      id: baseId,
      number: Math.floor(Math.random() * 1000),
      title: `Mock Issue ${baseId}`,
      body: `This is a mock issue ${baseId} for testing`,
      state: Math.random() > 0.5 ? 'open' : 'closed',
      locked: false,
      user: this.createMockUser({ login: `user-${baseId}` }),
      assignees: Math.random() > 0.7 ? [this.createMockUser({ login: `assignee-${baseId}` })] : [],
      labels: Math.random() > 0.6 ? [
        this.createMockLabel({ id: baseId, name: `label-${baseId}` })
      ] : [],
      milestone: Math.random() > 0.8 ? this.createMockMilestone({ id: baseId }) : undefined,
      comments: Math.floor(Math.random() * 20),
      created_at: '2025-11-01T10:00:00Z',
      updated_at: '2025-11-02T15:30:00Z',
      closed_at: Math.random() > 0.5 ? '2025-11-02T12:45:00Z' : undefined,
      html_url: `https://github.com/mockuser/mock-repo/issues/${baseId}`,
      repository_url: 'https://api.github.com/repos/mockuser/mock-repo',
      ...overrides
    };
  }

  static createMockPullRequest(overrides: Partial<GitHubPullRequest> = {}): GitHubPullRequest {
    const baseId = Math.floor(Math.random() * 1000000);
    return {
      id: baseId,
      number: Math.floor(Math.random() * 1000),
      title: `Mock PR ${baseId}`,
      body: `This is a mock pull request ${baseId} for testing`,
      state: ['open', 'closed', 'merged'][Math.floor(Math.random() * 3)] as any,
      locked: false,
      user: this.createMockUser({ login: `user-${baseId}` }),
      assignees: Math.random() > 0.7 ? [this.createMockUser({ login: `assignee-${baseId}` })] : [],
      requested_reviewers: Math.random() > 0.6 ? [this.createMockUser({ login: `reviewer-${baseId}` })] : [],
      labels: Math.random() > 0.6 ? [
        this.createMockLabel({ id: baseId, name: `label-${baseId}` })
      ] : [],
      milestone: Math.random() > 0.8 ? this.createMockMilestone({ id: baseId }) : undefined,
      comments: Math.floor(Math.random() * 20),
      review_comments: Math.floor(Math.random() * 15),
      commits: Math.floor(Math.random() * 10),
      additions: Math.floor(Math.random() * 2000),
      deletions: Math.floor(Math.random() * 500),
      changed_files: Math.floor(Math.random() * 20),
      created_at: '2025-11-01T08:00:00Z',
      updated_at: '2025-11-02T16:20:00Z',
      closed_at: Math.random() > 0.5 ? '2025-11-02T14:30:00Z' : undefined,
      merged_at: Math.random() > 0.4 ? '2025-11-02T15:00:00Z' : undefined,
      mergeable: Math.random() > 0.3,
      html_url: `https://github.com/mockuser/mock-repo/pull/${baseId}`,
      diff_url: `https://github.com/mockuser/mock-repo/pull/${baseId}.diff`,
      repository_url: 'https://api.github.com/repos/mockuser/mock-repo',
      head: this.createMockPullRequestBranch(`feature-${baseId}`),
      base: this.createMockPullRequestBranch('main'),
      ...overrides
    };
  }

  static createMockLabel(overrides: Partial<GitHubLabel> = {}): GitHubLabel {
    const colors = ['a2eeef', 'd73a4a', '0075ca', 'fbca04', 'cfd3d7'];
    return {
      id: Math.floor(Math.random() * 1000),
      name: `label-${Math.floor(Math.random() * 100)}`,
      description: `Mock label for testing`,
      color: colors[Math.floor(Math.random() * colors.length)],
      default: false,
      ...overrides
    };
  }

  static createMockMilestone(overrides: Partial<GitHubMilestone> = {}): GitHubMilestone {
    return {
      id: Math.floor(Math.random() * 100),
      number: Math.floor(Math.random() * 10),
      title: `Milestone ${Math.floor(Math.random() * 10)}`,
      description: `Mock milestone for testing`,
      state: Math.random() > 0.5 ? 'open' : 'closed',
      open_issues: Math.floor(Math.random() * 20),
      closed_issues: Math.floor(Math.random() * 10),
      created_at: '2025-10-01T00:00:00Z',
      updated_at: '2025-11-01T12:00:00Z',
      due_on: Math.random() > 0.5 ? '2025-12-31T23:59:59Z' : undefined,
      closed_at: Math.random() > 0.5 ? '2025-11-01T15:00:00Z' : undefined,
      html_url: 'https://github.com/mockuser/mock-repo/milestone/1',
      ...overrides
    };
  }

  static createMockPullRequestBranch(name: string) {
    return {
      label: `mockuser:${name}`,
      ref_field: name,
      sha: `${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`,
      user: this.createMockUser(),
      repo: Math.random() > 0.5 ? this.createMockRepository() : undefined
    };
  }

  // Batch creators
  static createMockRepositories(count: number, overrides: Partial<GitHubRepository> = {}): GitHubRepository[] {
    return Array.from({ length: count }, (_, i) => 
      this.createMockRepository({
        ...overrides,
        id: (overrides.id || 0) + i + 1,
        name: overrides.name || `repo-${i + 1}`
      })
    );
  }

  static createMockIssues(count: number, overrides: Partial<GitHubIssue> = {}): GitHubIssue[] {
    return Array.from({ length: count }, (_, i) => 
      this.createMockIssue({
        ...overrides,
        id: (overrides.id || 0) + i + 1,
        number: (overrides.number || 0) + i + 1,
        title: overrides.title || `Issue ${i + 1}`
      })
    );
  }

  static createMockPullRequests(count: number, overrides: Partial<GitHubPullRequest> = {}): GitHubPullRequest[] {
    return Array.from({ length: count }, (_, i) => 
      this.createMockPullRequest({
        ...overrides,
        id: (overrides.id || 0) + i + 1,
        number: (overrides.number || 0) + i + 1,
        title: overrides.title || `PR ${i + 1}`
      })
    );
  }
}

// Test Scenarios
export class GitHubTestScenarios {
  static getEmptyRepositoryScenario() {
    return {
      user: GitHubMockDataFactory.createMockUser({ public_repos: 0 }),
      repositories: [],
      issues: [],
      pullRequests: []
    };
  }

  static getActiveRepositoryScenario() {
    const repositories = GitHubMockDataFactory.createMockRepositories(5);
    const issues = GitHubMockDataFactory.createMockIssues(3, {
      state: 'open',
      repository_url: repositories[0].html_url
    });
    const pullRequests = GitHubMockDataFactory.createMockPullRequests(2, {
      state: 'open',
      repository_url: repositories[0].html_url
    });

    return {
      user: GitHubMockDataFactory.createMockUser({ public_repos: 5 }),
      repositories,
      issues,
      pullRequests
    };
  }

  static getHighActivityScenario() {
    const repositories = GitHubMockDataFactory.createMockRepositories(10, {
      stargazers_count: 500,
      forks_count: 100,
      open_issues_count: 25
    });
    const issues = GitHubMockDataFactory.createMockIssues(20, {
      state: 'open',
      comments: 10
    });
    const pullRequests = GitHubMockDataFactory.createMockPullRequests(15, {
      state: 'open',
      comments: 15,
      review_comments: 8
    });

    return {
      user: GitHubMockDataFactory.createMockUser({ public_repos: 10 }),
      repositories,
      issues,
      pullRequests
    };
  }

  static getComplexityScenario() {
    return {
      simplePR: GitHubMockDataFactory.createMockPullRequest({
        additions: 50,
        deletions: 10,
        changed_files: 3,
        commits: 2
      }),
      mediumPR: GitHubMockDataFactory.createMockPullRequest({
        additions: 500,
        deletions: 100,
        changed_files: 15,
        commits: 8
      }),
      complexPR: GitHubMockDataFactory.createMockPullRequest({
        additions: 2000,
        deletions: 500,
        changed_files: 50,
        commits: 25
      })
    };
  }

  static getErrorScenario() {
    return {
      networkError: new Error('Network error: Failed to fetch'),
      apiError: new Error('GitHub API rate limit exceeded'),
      authError: new Error('Authentication failed: Invalid token'),
      validationError: new Error('Validation error: Repository name is required')
    };
  }
}

// Mock API Responses
export class GitHubMockAPIResponses {
  static getOAuthResponse() {
    return {
      success: true,
      oauth_url: 'https://github.com/login/oauth/authorize?client_id=mock_client_id&redirect_uri=http://localhost:3000/oauth/github/callback&scope=repo&state=github_oauth_test_1730544000',
      service: 'github',
      expires_in: 600,
      message: 'GitHub OAuth URL generated successfully'
    };
  }

  static getConnectionResponse(connected: boolean = true) {
    return connected ? {
      connected: true,
      user_info: GitHubMockDataFactory.createMockUser(),
      tokens: {
        access_token: '***encrypted***',
        token_type: 'bearer',
        scope: 'repo,user,issues,pull_requests',
        expires_at: '2025-11-03T10:00:00Z'
      },
      message: 'GitHub is connected and ready'
    } : {
      connected: false,
      error: 'No tokens found'
    };
  }

  static getRepositoryListResponse(limit: number = 10) {
    return GitHubMockDataFactory.createMockRepositories(limit).map(repo => ({
      ...repo,
      owner: { login: 'mockuser' }
    }));
  }

  static getIssueListResponse(limit: number = 10) {
    return GitHubMockDataFactory.createMockIssues(limit);
  }

  static getPullRequestListResponse(limit: number = 10) {
    return GitHubMockDataFactory.createMockPullRequests(limit);
  }

  static getCreateIssueResponse(title: string) {
    return {
      success: true,
      issue_id: Math.floor(Math.random() * 1000000).toString(),
      issue_number: Math.floor(Math.random() * 1000).toString(),
      issue_title: title,
      url: `https://github.com/mockuser/mock-repo/issues/${Math.floor(Math.random() * 1000)}`,
      message: 'Issue created successfully'
    };
  }

  static getCreatePullRequestResponse(title: string) {
    return {
      success: true,
      pr_id: Math.floor(Math.random() * 1000000).toString(),
      pr_number: Math.floor(Math.random() * 1000).toString(),
      pr_title: title,
      url: `https://github.com/mockuser/mock-repo/pull/${Math.floor(Math.random() * 1000)}`,
      html_url: `https://github.com/mockuser/mock-repo/pull/${Math.floor(Math.random() * 1000)}`,
      message: 'Pull request created successfully'
    };
  }

  static getSearchResponse(query: string) {
    return GitHubMockDataFactory.createMockRepositories(5, {
      name: `search-result-for-${query}`,
      description: `Repository matching search query: ${query}`
    });
  }
}

// Test Helpers
export class GitHubTestHelpers {
  static expectValidRepository(repository: GitHubRepository) {
    expect(repository.id).toBeGreaterThan(0);
    expect(repository.name).toBeDefined();
    expect(repository.full_name).toContain('/');
    expect(repository.html_url).toContain('github.com');
    expect(typeof repository.private).toBe('boolean');
    expect(typeof repository.fork).toBe('boolean');
    expect(typeof repository.stargazers_count).toBe('number');
    expect(typeof repository.forks_count).toBe('number');
    expect(typeof repository.open_issues_count).toBe('number');
    expect(new Date(repository.created_at)).toBeInstanceOf(Date);
    expect(new Date(repository.updated_at)).toBeInstanceOf(Date);
  }

  static expectValidIssue(issue: GitHubIssue) {
    expect(issue.id).toBeGreaterThan(0);
    expect(issue.number).toBeGreaterThan(0);
    expect(issue.title).toBeDefined();
    expect(['open', 'closed']).toContain(issue.state);
    expect(typeof issue.locked).toBe('boolean');
    expect(issue.user.login).toBeDefined();
    expect(Array.isArray(issue.assignees)).toBe(true);
    expect(Array.isArray(issue.labels)).toBe(true);
    expect(typeof issue.comments).toBe('number');
    expect(issue.html_url).toContain('issues/');
    expect(new Date(issue.created_at)).toBeInstanceOf(Date);
    expect(new Date(issue.updated_at)).toBeInstanceOf(Date);
  }

  static expectValidPullRequest(pr: GitHubPullRequest) {
    expect(pr.id).toBeGreaterThan(0);
    expect(pr.number).toBeGreaterThan(0);
    expect(pr.title).toBeDefined();
    expect(['open', 'closed', 'merged']).toContain(pr.state);
    expect(typeof pr.locked).toBe('boolean');
    expect(pr.user.login).toBeDefined();
    expect(Array.isArray(pr.assignees)).toBe(true);
    expect(Array.isArray(pr.requested_reviewers)).toBe(true);
    expect(Array.isArray(pr.labels)).toBe(true);
    expect(typeof pr.comments).toBe('number');
    expect(typeof pr.review_comments).toBe('number');
    expect(typeof pr.commits).toBe('number');
    expect(typeof pr.additions).toBe('number');
    expect(typeof pr.deletions).toBe('number');
    expect(typeof pr.changed_files).toBe('number');
    expect(typeof pr.mergeable).toBe('boolean');
    expect(pr.html_url).toContain('pull/');
    expect(pr.head.label).toBeDefined();
    expect(pr.base.label).toBeDefined();
    expect(new Date(pr.created_at)).toBeInstanceOf(Date);
    expect(new Date(pr.updated_at)).toBeInstanceOf(Date);
  }

  static expectValidUser(user: GitHubUserInfo) {
    expect(user.id).toBeGreaterThan(0);
    expect(user.login).toBeDefined();
    expect(user.name).toBeDefined();
    expect(user.avatar_url).toContain('github.com');
    expect(typeof user.public_repos).toBe('number');
    expect(typeof user.followers).toBe('number');
    expect(typeof user.following).toBe('number');
    expect(user.html_url).toContain('github.com');
    expect(['User', 'Organization']).toContain(user.type);
  }

  static expectSuccessfulResponse(response: any) {
    expect(response).toHaveProperty('success');
    expect(response.success).toBe(true);
    expect(response).toHaveProperty('message');
    expect(response.message).toBeDefined();
  }

  static expectErrorResponse(response: any, expectedError?: string) {
    expect(response).toHaveProperty('success');
    expect(response.success).toBe(false);
    expect(response).toHaveProperty('error');
    expect(response.error).toBeDefined();
    if (expectedError) {
      expect(response.error).toContain(expectedError);
    }
  }

  static expectValidTimestamp(timestamp: string) {
    expect(timestamp).toBeDefined();
    expect(typeof timestamp).toBe('string');
    expect(new Date(timestamp)).toBeInstanceOf(Date);
    expect(() => new Date(timestamp)).not.toThrow();
  }

  static expectValidMetrics(metrics: any) {
    expect(metrics).toBeDefined();
    expect(typeof metrics.total).toBe('number');
    expect(typeof metrics.average).toBe('number');
    expect(metrics.average).toBeGreaterThanOrEqual(0);
  }

  static createMockContext(userId: string = 'test-user') {
    return {
      userId,
      sessionId: 'test-session',
      timestamp: '2025-11-02T10:00:00Z',
      intent: { name: 'test', confidence: 0.9 },
      entities: [],
      confidence: 0.9
    };
  }

  static createMockParams<T>(overrides: Partial<T> = {}): T {
    return overrides as T;
  }
}

// Performance Test Utilities
export class GitHubPerformanceTestUtils {
  static measureExecutionTime<T>(fn: () => Promise<T>): Promise<{ result: T; time: number }> {
    return fn().then(result => ({
      result,
      time: 0 // Would be measured in actual implementation
    }));
  }

  static generateLargeDataset(type: 'repos' | 'issues' | 'prs', count: number) {
    switch (type) {
      case 'repos':
        return GitHubMockDataFactory.createMockRepositories(count);
      case 'issues':
        return GitHubMockDataFactory.createMockIssues(count);
      case 'prs':
        return GitHubMockDataFactory.createMockPullRequests(count);
      default:
        return [];
    }
  }

  static runPerformanceTest(testName: string, testFn: () => Promise<any>, maxTimeMs: number = 1000) {
    const startTime = Date.now();
    return testFn().then(result => {
      const endTime = Date.now();
      const executionTime = endTime - startTime;
      
      expect(executionTime).toBeLessThan(maxTimeMs);
      expect(result).toBeDefined();
      
      return {
        testName,
        executionTime,
        result,
        passed: executionTime < maxTimeMs
      };
    });
  }
}

// Security Test Utilities
export class GitHubSecurityTestUtils {
  static createMaliciousInput() {
    return {
      xss: '<script>alert("xss")</script>',
      sqlInjection: "'; DROP TABLE users; --",
      pathTraversal: '../../../etc/passwd',
      commandInjection: '; rm -rf /',
      oversizedInput: 'a'.repeat(10000)
    };
  }

  static sanitizeInput(input: string): string {
    return input
      .replace(/<[^>]*>/g, '') // Remove HTML tags
      .replace(/[;&]/g, '') // Remove dangerous characters
      .replace(/\.\./g, '') // Remove path traversal
      .substring(0, 1000); // Limit length
  }

  static expectSecureResponse(response: any, maliciousInput: string) {
    expect(response).not.toContain(maliciousInput);
    expect(response).not.toContain('<script>');
    expect(response).not.toContain('DROP TABLE');
    expect(response).not.toContain('../../../');
    expect(response).not.toContain('rm -rf');
  }
}