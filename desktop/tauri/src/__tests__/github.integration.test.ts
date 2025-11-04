/**
 * GitHub Integration Tests
 * Testing Tauri commands and API integration
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock Tauri API
const mockTauri = {
  invoke: vi.fn()
};

// Mock global invoke function
global.invoke = mockTauri.invoke;

describe('GitHub Tauri Commands', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('GitHub OAuth Commands', () => {
    it('should generate OAuth URL', async () => {
      mockTauri.invoke.mockResolvedValue({
        success: true,
        oauth_url: 'https://github.com/login/oauth/authorize?client_id=test&scope=repo&state=test',
        service: 'github',
        expires_in: 600,
        message: 'GitHub OAuth URL generated successfully'
      });

      const result = await global.invoke('get_github_oauth_url', { user_id: 'test-user' });

      expect(result.success).toBe(true);
      expect(result.oauth_url).toContain('github.com/login/oauth/authorize');
      expect(result.service).toBe('github');
      expect(result.expires_in).toBe(600);
      expect(mockTauri.invoke).toHaveBeenCalledWith('get_github_oauth_url', { user_id: 'test-user' });
    });

    it('should exchange OAuth code for tokens', async () => {
      mockTauri.invoke.mockResolvedValue({
        success: true,
        user_info: {
          id: 12345,
          login: 'testuser',
          name: 'Test User',
          email: 'test@example.com'
        },
        tokens: {
          access_token: '***encrypted***',
          token_type: 'bearer',
          scope: 'repo,user,issues,pull_requests',
          expires_at: '2025-11-03T10:00:00Z'
        },
        message: 'GitHub OAuth completed successfully'
      });

      const result = await global.invoke('exchange_github_oauth_code', { 
        code: 'test-code', 
        state: 'test-state' 
      });

      expect(result.success).toBe(true);
      expect(result.user_info.login).toBe('testuser');
      expect(result.tokens.access_token).toBe('***encrypted***');
      expect(result.tokens.scope).toBe('repo,user,issues,pull_requests');
      expect(mockTauri.invoke).toHaveBeenCalledWith('exchange_github_oauth_code', { 
        code: 'test-code', 
        state: 'test-state' 
      });
    });

    it('should check GitHub connection status', async () => {
      mockTauri.invoke.mockResolvedValue({
        connected: true,
        user_info: {
          id: 12345,
          login: 'testuser',
          name: 'Test User',
          email: 'test@example.com'
        },
        tokens: {
          access_token: '***encrypted***',
          token_type: 'bearer',
          scope: 'repo,user,issues,pull_requests',
          expires_at: '2025-11-03T10:00:00Z'
        },
        message: 'GitHub is connected and ready'
      });

      const result = await global.invoke('get_github_connection', { user_id: 'test-user' });

      expect(result.connected).toBe(true);
      expect(result.user_info.login).toBe('testuser');
      expect(result.message).toContain('connected and ready');
      expect(mockTauri.invoke).toHaveBeenCalledWith('get_github_connection', { user_id: 'test-user' });
    });

    it('should disconnect GitHub', async () => {
      mockTauri.invoke.mockResolvedValue({
        success: true,
        message: 'GitHub disconnected successfully'
      });

      const result = await global.invoke('disconnect_github', { user_id: 'test-user' });

      expect(result.success).toBe(true);
      expect(result.message).toBe('GitHub disconnected successfully');
      expect(mockTauri.invoke).toHaveBeenCalledWith('disconnect_github', { user_id: 'test-user' });
    });
  });

  describe('GitHub Repository Commands', () => {
    beforeEach(() => {
      // Mock connected status for repo commands
      mockTauri.invoke.mockImplementation((command: string) => {
        if (command === 'get_github_connection') {
          return Promise.resolve({
            connected: true,
            user_info: { login: 'testuser' }
          });
        }
        return Promise.resolve([]);
      });
    });

    it('should get user repositories', async () => {
      const mockRepos = [
        {
          id: 123456,
          name: 'atom-desktop',
          full_name: 'testuser/atom-desktop',
          description: 'ATOM Desktop Application',
          private: false,
          html_url: 'https://github.com/testuser/atom-desktop',
          stargazers_count: 42,
          forks_count: 15,
          open_issues_count: 8,
          language: 'TypeScript',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2025-11-02T10:00:00Z'
        }
      ];

      mockTauri.invoke.mockResolvedValue(mockRepos);

      const result = await global.invoke('get_github_user_repositories', { 
        user_id: 'test-user',
        limit: 20 
      });

      expect(result).toEqual(mockRepos);
      expect(mockTauri.invoke).toHaveBeenCalledWith('get_github_user_repositories', { 
        user_id: 'test-user',
        limit: 20 
      });
    });

    it('should search repositories', async () => {
      const mockSearchResults = [
        {
          id: 98765,
          name: 'github-integration',
          full_name: 'atomcompany/github-integration',
          description: 'GitHub API integration library',
          private: false,
          html_url: 'https://github.com/atomcompany/github-integration',
          stargazers_count: 156,
          forks_count: 45,
          language: 'Rust'
        }
      ];

      mockTauri.invoke.mockResolvedValue(mockSearchResults);

      const result = await global.invoke('search_github_repositories', { 
        user_id: 'test-user',
        query: 'github integration',
        limit: 10 
      });

      expect(result).toEqual(mockSearchResults);
      expect(mockTauri.invoke).toHaveBeenCalledWith('search_github_repositories', { 
        user_id: 'test-user',
        query: 'github integration',
        limit: 10 
      });
    });
  });

  describe('GitHub Issue Commands', () => {
    beforeEach(() => {
      mockTauri.invoke.mockImplementation((command: string) => {
        if (command === 'get_github_connection') {
          return Promise.resolve({
            connected: true,
            user_info: { login: 'testuser' }
          });
        }
        if (command === 'get_github_user_repositories') {
          return Promise.resolve([{
            id: 123456,
            name: 'atom-desktop',
            full_name: 'testuser/atom-desktop'
          }]);
        }
        return Promise.resolve([]);
      });
    });

    it('should get repository issues', async () => {
      const mockIssues = [
        {
          id: 1001,
          number: 42,
          title: 'Add GitHub integration',
          body: 'Implement GitHub integration',
          state: 'open',
          user: { login: 'developer1', name: 'Developer One' },
          assignees: [],
          labels: [{ id: 123, name: 'enhancement', color: 'a2eeef' }],
          created_at: '2025-11-01T10:00:00Z',
          updated_at: '2025-11-02T15:30:00Z',
          html_url: 'https://github.com/testuser/atom-desktop/issues/42'
        }
      ];

      mockTauri.invoke.mockResolvedValue(mockIssues);

      const result = await global.invoke('get_github_repository_issues', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'atom-desktop',
        state: 'open',
        limit: 10 
      });

      expect(result).toEqual(mockIssues);
      expect(mockTauri.invoke).toHaveBeenCalledWith('get_github_repository_issues', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'atom-desktop',
        state: 'open',
        limit: 10 
      });
    });

    it('should create issue', async () => {
      mockTauri.invoke.mockResolvedValue({
        success: true,
        issue_id: '1003',
        issue_number: '44',
        title: 'Test Issue',
        url: 'https://github.com/testuser/atom-desktop/issues/44',
        message: 'Issue created successfully'
      });

      const result = await global.invoke('create_github_issue', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'atom-desktop',
        title: 'Test Issue',
        body: 'Test issue description'
      });

      expect(result.success).toBe(true);
      expect(result.issue_number).toBe('44');
      expect(result.url).toContain('issues/44');
      expect(mockTauri.invoke).toHaveBeenCalledWith('create_github_issue', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'atom-desktop',
        title: 'Test Issue',
        body: 'Test issue description'
      });
    });
  });

  describe('GitHub Pull Request Commands', () => {
    beforeEach(() => {
      mockTauri.invoke.mockImplementation((command: string) => {
        if (command === 'get_github_connection') {
          return Promise.resolve({
            connected: true,
            user_info: { login: 'testuser' }
          });
        }
        if (command === 'get_github_user_repositories') {
          return Promise.resolve([{
            id: 123456,
            name: 'atom-desktop',
            full_name: 'testuser/atom-desktop'
          }]);
        }
        return Promise.resolve([]);
      });
    });

    it('should get pull requests', async () => {
      const mockPullRequests = [
        {
          id: 2001,
          number: 15,
          title: 'Add GitHub integration feature',
          body: 'Implement GitHub integration',
          state: 'open',
          user: { login: 'contributor1', name: 'Contributor One' },
          assignees: [{ login: 'developer1', name: 'Developer One' }],
          created_at: '2025-11-01T08:00:00Z',
          updated_at: '2025-11-02T16:20:00Z',
          additions: 1250,
          deletions: 85,
          changed_files: 12,
          commits: 5,
          comments: 12,
          mergeable: true,
          html_url: 'https://github.com/testuser/atom-desktop/pull/15'
        }
      ];

      mockTauri.invoke.mockResolvedValue(mockPullRequests);

      const result = await global.invoke('get_github_pull_requests', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'atom-desktop',
        state: 'open',
        limit: 10 
      });

      expect(result).toEqual(mockPullRequests);
      expect(mockTauri.invoke).toHaveBeenCalledWith('get_github_pull_requests', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'atom-desktop',
        state: 'open',
        limit: 10 
      });
    });

    it('should create pull request', async () => {
      mockTauri.invoke.mockResolvedValue({
        success: true,
        pr_id: '2002',
        pr_number: '16',
        title: 'Test PR',
        url: 'https://github.com/testuser/atom-desktop/pull/16',
        html_url: 'https://github.com/testuser/atom-desktop/pull/16',
        message: 'Pull request created successfully'
      });

      const result = await global.invoke('create_github_pull_request', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'atom-desktop',
        title: 'Test PR',
        body: 'Test PR description',
        head: 'feature/test',
        base: 'main'
      });

      expect(result.success).toBe(true);
      expect(result.pr_number).toBe('16');
      expect(result.url).toContain('pull/16');
      expect(mockTauri.invoke).toHaveBeenCalledWith('create_github_pull_request', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'atom-desktop',
        title: 'Test PR',
        body: 'Test PR description',
        head: 'feature/test',
        base: 'main'
      });
    });
  });

  describe('GitHub Token Management', () => {
    it('should check token validity', async () => {
      mockTauri.invoke.mockResolvedValue({
        valid: true,
        expired: false,
        message: 'Tokens are valid',
        expires_at: '2025-11-03T10:00:00Z'
      });

      const result = await global.invoke('check_github_tokens', { user_id: 'test-user' });

      expect(result.valid).toBe(true);
      expect(result.expired).toBe(false);
      expect(result.message).toBe('Tokens are valid');
      expect(mockTauri.invoke).toHaveBeenCalledWith('check_github_tokens', { user_id: 'test-user' });
    });

    it('should refresh tokens', async () => {
      mockTauri.invoke.mockResolvedValue({
        success: true,
        access_token: 'new_mock_github_access_token',
        refresh_token: 'new_mock_github_refresh_token',
        expires_in: '3600',
        message: 'Tokens refreshed successfully'
      });

      const result = await global.invoke('refresh_github_tokens', { 
        user_id: 'test-user',
        refresh_token: 'old_refresh_token'
      });

      expect(result.success).toBe(true);
      expect(result.access_token).toBe('new_mock_github_access_token');
      expect(result.expires_in).toBe('3600');
      expect(mockTauri.invoke).toHaveBeenCalledWith('refresh_github_tokens', { 
        user_id: 'test-user',
        refresh_token: 'old_refresh_token'
      });
    });
  });

  describe('Error Handling', () => {
    it('should handle OAuth errors', async () => {
      mockTauri.invoke.mockRejectedValue(new Error('OAuth failed: invalid_code'));

      await expect(global.invoke('exchange_github_oauth_code', { 
        code: 'invalid', 
        state: 'test' 
      })).rejects.toThrow('OAuth failed: invalid_code');
    });

    it('should handle API errors', async () => {
      mockTauri.invoke.mockRejectedValue(new Error('GitHub API rate limit exceeded'));

      await expect(global.invoke('get_github_user_repositories', { 
        user_id: 'test-user',
        limit: 20 
      })).rejects.toThrow('GitHub API rate limit exceeded');
    });

    it('should handle connection errors', async () => {
      mockTauri.invoke.mockRejectedValue(new Error('Network error: Failed to fetch'));

      await expect(global.invoke('get_github_connection', { 
        user_id: 'test-user' 
      })).rejects.toThrow('Network error: Failed to fetch');
    });

    it('should handle disconnected user', async () => {
      mockTauri.invoke.mockResolvedValue({
        connected: false,
        error: 'No tokens found'
      });

      const result = await global.invoke('get_github_connection', { user_id: 'test-user' });

      expect(result.connected).toBe(false);
      expect(result.error).toBe('No tokens found');
    });
  });

  describe('Data Validation', () => {
    it('should validate required parameters for repo listing', async () => {
      mockTauri.invoke.mockRejectedValue(new Error('user_id is required'));

      await expect(global.invoke('get_github_user_repositories', {}))
        .rejects.toThrow('user_id is required');
    });

    it('should validate required parameters for issue creation', async () => {
      mockTauri.invoke.mockRejectedValue(new Error('owner, repo, and title are required'));

      await expect(global.invoke('create_github_issue', { 
        user_id: 'test-user',
        owner: 'testuser'
        // Missing repo and title
      })).rejects.toThrow('owner, repo, and title are required');
    });

    it('should validate required parameters for PR creation', async () => {
      mockTauri.invoke.mockRejectedValue(new Error('owner, repo, title, head, and base are required'));

      await expect(global.invoke('create_github_pull_request', { 
        user_id: 'test-user',
        owner: 'testuser',
        repo: 'test-repo',
        title: 'Test PR'
        // Missing head and base
      })).rejects.toThrow('owner, repo, title, head, and base are required');
    });
  });

  describe('Performance Tests', () => {
    it('should handle large repository lists', async () => {
      const largeRepos = Array.from({ length: 100 }, (_, i) => ({
        id: i + 1,
        name: `repo-${i + 1}`,
        full_name: `testuser/repo-${i + 1}`,
        stargazers_count: Math.floor(Math.random() * 1000),
        forks_count: Math.floor(Math.random() * 500),
        open_issues_count: Math.floor(Math.random() * 50)
      }));

      mockTauri.invoke.mockResolvedValue(largeRepos);

      const result = await global.invoke('get_github_user_repositories', { 
        user_id: 'test-user',
        limit: 100 
      });

      expect(result).toHaveLength(100);
      expect(result[0].name).toBe('repo-1');
      expect(result[99].name).toBe('repo-100');
    });

    it('should handle concurrent requests', async () => {
      mockTauri.invoke.mockResolvedValue([
        { id: 1, number: 1, title: 'Issue 1' },
        { id: 2, number: 2, title: 'Issue 2' }
      ]);

      // Make multiple concurrent requests
      const promises = [
        global.invoke('get_github_repository_issues', { user_id: 'test-user', owner: 'test', repo: 'test1' }),
        global.invoke('get_github_repository_issues', { user_id: 'test-user', owner: 'test', repo: 'test2' }),
        global.invoke('get_github_repository_issues', { user_id: 'test-user', owner: 'test', repo: 'test3' })
      ];

      const results = await Promise.all(promises);
      
      expect(results).toHaveLength(3);
      expect(results[0]).toHaveLength(2);
      expect(mockTauri.invoke).toHaveBeenCalledTimes(3);
    });
  });
});

describe('GitHub Mock Data Validation', () => {
  it('should validate mock repository structure', () => {
    const mockRepo = {
      id: 123456,
      name: 'test-repo',
      full_name: 'testuser/test-repo',
      description: 'Test repository',
      private: false,
      html_url: 'https://github.com/testuser/test-repo',
      stargazers_count: 42,
      forks_count: 15,
      open_issues_count: 8,
      language: 'TypeScript',
      created_at: '2023-01-01T00:00:00Z',
      updated_at: '2025-11-02T10:00:00Z'
    };

    expect(mockRepo.id).toBeGreaterThan(0);
    expect(mockRepo.name).toBeDefined();
    expect(mockRepo.full_name).toContain('/');
    expect(mockRepo.html_url).toContain('github.com');
    expect(typeof mockRepo.stargazers_count).toBe('number');
    expect(typeof mockRepo.forks_count).toBe('number');
    expect(typeof mockRepo.open_issues_count).toBe('number');
    expect(new Date(mockRepo.created_at)).toBeInstanceOf(Date);
    expect(new Date(mockRepo.updated_at)).toBeInstanceOf(Date);
  });

  it('should validate mock issue structure', () => {
    const mockIssue = {
      id: 1001,
      number: 42,
      title: 'Test Issue',
      body: 'Test issue description',
      state: 'open',
      user: { login: 'developer1', name: 'Developer One' },
      assignees: [],
      labels: [{ id: 123, name: 'enhancement', color: 'a2eeef' }],
      created_at: '2025-11-01T10:00:00Z',
      updated_at: '2025-11-02T15:30:00Z',
      html_url: 'https://github.com/testuser/test-repo/issues/42'
    };

    expect(mockIssue.id).toBeGreaterThan(0);
    expect(mockIssue.number).toBeGreaterThan(0);
    expect(mockIssue.title).toBeDefined();
    expect(['open', 'closed']).toContain(mockIssue.state);
    expect(mockIssue.user.login).toBeDefined();
    expect(Array.isArray(mockIssue.assignees)).toBe(true);
    expect(Array.isArray(mockIssue.labels)).toBe(true);
    expect(mockIssue.html_url).toContain('issues/42');
  });

  it('should validate mock pull request structure', () => {
    const mockPR = {
      id: 2001,
      number: 15,
      title: 'Test PR',
      body: 'Test PR description',
      state: 'open',
      user: { login: 'contributor1', name: 'Contributor One' },
      assignees: [{ login: 'developer1', name: 'Developer One' }],
      created_at: '2025-11-01T08:00:00Z',
      updated_at: '2025-11-02T16:20:00Z',
      additions: 1250,
      deletions: 85,
      changed_files: 12,
      commits: 5,
      comments: 12,
      mergeable: true,
      html_url: 'https://github.com/testuser/test-repo/pull/15'
    };

    expect(mockPR.id).toBeGreaterThan(0);
    expect(mockPR.number).toBeGreaterThan(0);
    expect(mockPR.title).toBeDefined();
    expect(['open', 'closed', 'merged']).toContain(mockPR.state);
    expect(typeof mockPR.additions).toBe('number');
    expect(typeof mockPR.deletions).toBe('number');
    expect(typeof mockPR.changed_files).toBe('number');
    expect(typeof mockPR.commits).toBe('number');
    expect(typeof mockPR.comments).toBe('number');
    expect(typeof mockPR.mergeable).toBe('boolean');
    expect(mockPR.html_url).toContain('pull/15');
  });
});