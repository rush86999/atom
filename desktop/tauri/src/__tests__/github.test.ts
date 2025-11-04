/**
 * GitHub Integration Unit Tests
 * Following Outlook pattern for consistency
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { 
  githubRepoSkill, 
  GitHubRepoSkillParams 
} from '../skills/githubRepoSkill';
import { 
  githubIssueSkill, 
  GitHubIssueSkillParams 
} from '../skills/githubIssueSkill';
import { 
  githubPullRequestSkill, 
  GitHubPullRequestSkillParams 
} from '../skills/githubPullRequestSkill';
import { SkillExecutionContext } from '../types/skillTypes';

// Mock Tauri invoke
vi.mock('@tauri-apps/api/tauri', () => ({
  invoke: vi.fn()
}));

describe('GitHub Repo Skill', () => {
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

    vi.clearAllMocks();
  });

  describe('listRepositories', () => {
    it('should list repositories successfully', async () => {
      const { invoke } = await import('@tauri-apps/api/tauri');
      const mockRepos = [
        {
          id: 123456,
          name: 'atom-desktop',
          full_name: 'atomcompany/atom-desktop',
          description: 'ATOM Desktop Application',
          private: false,
          html_url: 'https://github.com/atomcompany/atom-desktop',
          stargazers_count: 42,
          forks_count: 15,
          open_issues_count: 8,
          language: 'TypeScript',
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2025-11-02T10:00:00Z'
        }
      ];
      
      (invoke as any).mockResolvedValue(mockRepos);

      const params: GitHubRepoSkillParams = {
        action: 'list',
        limit: 10
      };

      const result = await githubRepoSkill.execute(params, mockContext);

      expect(result.success).toBe(true);
      expect(result.data?.repositories).toBeDefined();
      expect(result.data?.count).toBe(1);
      expect(result.data?.repositories[0].name).toBe('atom-desktop');
      expect(result.data?.statistics).toBeDefined();
      expect(invoke).toHaveBeenCalledWith('get_github_user_repositories', {
        userId: 'test-user',
        limit: 10
      });
    });

    it('should handle API errors gracefully', async () => {
      const { invoke } = await import('@tauri-apps/api/tauri');
      (invoke as any).mockRejectedValue(new Error('API Error'));

      const params: GitHubRepoSkillParams = {
        action: 'list',
        limit: 10
      };

      const result = await githubRepoSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('API Error');
    });
  });

  describe('createRepository', () => {
    it('should create repository successfully', async () => {
      const params: GitHubRepoSkillParams = {
        action: 'create',
        name: 'test-repo',
        description: 'Test repository',
        private: false,
        language: 'TypeScript'
      };

      const result = await githubRepoSkill.execute(params, mockContext);

      expect(result.success).toBe(true);
      expect(result.data?.repository_name).toBe('test-repo');
      expect(result.data?.repository_url).toContain('test-repo');
      expect(result.message).toContain('created successfully');
    });

    it('should validate repository name', async () => {
      const params: GitHubRepoSkillParams = {
        action: 'create',
        name: '', // Invalid empty name
        description: 'Test repository'
      };

      const result = await githubRepoSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Repository name is required');
    });

    it('should validate repository name format', async () => {
      const params: GitHubRepoSkillParams = {
        action: 'create',
        name: 'invalid@name', // Invalid characters
        description: 'Test repository'
      };

      const result = await githubRepoSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('invalid characters');
    });
  });

  describe('searchRepositories', () => {
    it('should search repositories successfully', async () => {
      const { invoke } = await import('@tauri-apps/api/tauri');
      const mockRepos = [
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
      
      (invoke as any).mockResolvedValue(mockRepos);

      const params: GitHubRepoSkillParams = {
        action: 'search',
        searchQuery: 'react components',
        limit: 10
      };

      const result = await githubRepoSkill.execute(params, mockContext);

      expect(result.success).toBe(true);
      expect(result.data?.searchQuery).toBe('react components');
      expect(result.data?.repositories).toBeDefined();
      expect(result.message).toContain('Found');
      expect(result.message).toContain('react components');
    });

    it('should require search query', async () => {
      const params: GitHubRepoSkillParams = {
        action: 'search',
        limit: 10
      };

      const result = await githubRepoSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Search query is required');
    });
  });

  describe('Repository Processing', () => {
    it('should process repository data correctly', () => {
      const rawRepo = {
        id: 123456,
        name: 'test-repo',
        created_at: '2023-01-01T00:00:00Z',
        updated_at: '2025-11-02T10:00:00Z',
        stargazers_count: 42,
        forks_count: 15,
        open_issues_count: 8,
        language: 'TypeScript',
        size: 500 // Changed to 500 to be 'Medium'
      };

      // Access private method through reflection for testing
      const processed = githubRepoSkill['processRepository'](rawRepo);

      expect(processed.created).toBeInstanceOf(Date);
      expect(processed.updated).toBeInstanceOf(Date);
      expect(processed.daysSinceCreation).toBeGreaterThan(0);
      expect(processed.daysSinceUpdate).toBeGreaterThanOrEqual(0);
      expect(processed.popularity).toBeGreaterThan(0);
      expect(processed.sizeCategory).toBe('Medium');
    });

    it('should calculate repository statistics correctly', () => {
      const repos = [
        {
          stargazers_count: 42,
          forks_count: 15,
          open_issues_count: 8,
          language: 'TypeScript',
          private: false,
          fork: false,
          created_at: '2023-01-01T00:00:00Z',
          updated_at: '2025-11-02T10:00:00Z'
        },
        {
          stargazers_count: 28,
          forks_count: 12,
          open_issues_count: 5,
          language: 'Python',
          private: true,
          fork: true,
          created_at: '2023-02-01T00:00:00Z',
          updated_at: '2025-11-01T10:00:00Z'
        }
      ];

      const stats = githubRepoSkill['calculateRepoStatistics'](repos);

      expect(stats.total).toBe(2);
      expect(stats.public).toBe(1);
      expect(stats.private).toBe(1);
      expect(stats.forked).toBe(1);
      expect(stats.stars).toBe(70); // 42 + 28
      expect(stats.forks).toBe(27); // 15 + 12
      expect(stats.issues).toBe(13); // 8 + 5
      expect(stats.languages).toHaveLength(2);
      expect(stats.languages[0].language).toBe('TypeScript');
    });
  });
});

describe('GitHub Issue Skill', () => {
  let mockContext: SkillExecutionContext;

  beforeEach(() => {
    mockContext = {
      userId: 'test-user',
      sessionId: 'test-session',
      timestamp: '2025-11-02T10:00:00Z',
      intent: { name: 'github_list_issues', confidence: 0.9 },
      entities: [],
      confidence: 0.9
    };

    vi.clearAllMocks();
  });

  describe('listIssues', () => {
    it('should list issues successfully', async () => {
      const { invoke } = await import('@tauri-apps/api/tauri');
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
          updated_at: '2025-11-02T15:30:00Z'
        }
      ];
      
      (invoke as any).mockResolvedValue(mockIssues);

      const params: GitHubIssueSkillParams = {
        action: 'list',
        owner: 'atomcompany',
        repo: 'atom-desktop',
        state: 'open',
        limit: 10
      };

      const result = await githubIssueSkill.execute(params, mockContext);

      expect(result.success).toBe(true);
      expect(result.data?.issues).toBeDefined();
      expect(result.data?.count).toBe(1);
      expect(result.data?.issues[0].title).toBe('Add GitHub integration');
      expect(result.data?.statistics).toBeDefined();
    });

    it('should require owner and repository', async () => {
      const params: GitHubIssueSkillParams = {
        action: 'list',
        state: 'open'
      };

      const result = await githubIssueSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Owner and repository are required');
    });
  });

  describe('createIssue', () => {
    it('should create issue successfully', async () => {
      const { invoke } = await import('@tauri-apps/api/tauri');
      (invoke as any).mockResolvedValue({
        issue_number: 43,
        url: 'https://github.com/atomcompany/atom-desktop/issues/43'
      });

      const params: GitHubIssueSkillParams = {
        action: 'create',
        owner: 'atomcompany',
        repo: 'atom-desktop',
        title: 'Test issue',
        body: 'Test issue description',
        labels: ['bug'],
        assignees: ['developer1']
      };

      const result = await githubIssueSkill.execute(params, mockContext);

      expect(result.success).toBe(true);
      expect(result.data?.issue_number).toBe(43);
      expect(result.data?.issue_title).toBe('Test issue');
      expect(result.message).toContain('created successfully');
    });

    it('should require title', async () => {
      const params: GitHubIssueSkillParams = {
        action: 'create',
        owner: 'atomcompany',
        repo: 'atom-desktop',
        body: 'Test issue description'
      };

      const result = await githubIssueSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Issue title is required');
    });
  });

  describe('Issue Processing', () => {
    it('should process issue data correctly', () => {
      const rawIssue = {
        id: 1001,
        number: 42,
        title: 'Test issue',
        body: 'Test description',
        state: 'open',
        created_at: '2025-11-01T10:00:00Z',
        updated_at: '2025-11-02T15:30:00Z',
        closed_at: null,
        comments: 5,
        labels: [{ name: 'bug' }],
        assignees: [{ login: 'developer1' }]
      };

      const processed = githubIssueSkill['processIssue'](rawIssue);

      expect(processed.created).toBeInstanceOf(Date);
      expect(processed.updated).toBeInstanceOf(Date);
      expect(processed.daysSinceCreation).toBeGreaterThan(0);
      expect(processed.priority).toBeDefined();
      expect(processed.complexity).toBeDefined();
      expect(processed.healthScore).toBeGreaterThan(0);
      expect(processed.engagement).toBeDefined();
    });

    it('should calculate issue priority correctly', () => {
      const urgentIssue = {
        title: 'Critical security vulnerability',
        labels: [{ name: 'urgent' }]
      };

      const urgentPriority = githubIssueSkill['calculateIssuePriority'](urgentIssue);
      expect(urgentPriority).toBe('critical');

      const normalIssue = {
        title: 'Feature request',
        labels: []
      };

      const normalPriority = githubIssueSkill['calculateIssuePriority'](normalIssue);
      expect(['low', 'medium']).toContain(normalPriority);
    });
  });
});

describe('GitHub Pull Request Skill', () => {
  let mockContext: SkillExecutionContext;

  beforeEach(() => {
    mockContext = {
      userId: 'test-user',
      sessionId: 'test-session',
      timestamp: '2025-11-02T10:00:00Z',
      intent: { name: 'github_list_prs', confidence: 0.9 },
      entities: [],
      confidence: 0.9
    };

    vi.clearAllMocks();
  });

  describe('listPullRequests', () => {
    it('should list pull requests successfully', async () => {
      const { invoke } = await import('@tauri-apps/api/tauri');
      const mockPRs = [
        {
          id: 2001,
          number: 15,
          title: 'Add GitHub integration',
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
          review_comments: 8
        }
      ];
      
      (invoke as any).mockResolvedValue(mockPRs);

      const params: GitHubPullRequestSkillParams = {
        action: 'list',
        owner: 'atomcompany',
        repo: 'atom-desktop',
        state: 'open',
        limit: 10
      };

      const result = await githubPullRequestSkill.execute(params, mockContext);

      expect(result.success).toBe(true);
      expect(result.data?.pullRequests).toBeDefined();
      expect(result.data?.count).toBe(1);
      expect(result.data?.pullRequests[0].title).toBe('Add GitHub integration');
      expect(result.data?.statistics).toBeDefined();
    });

    it('should require owner and repository', async () => {
      const params: GitHubPullRequestSkillParams = {
        action: 'list',
        state: 'open'
      };

      const result = await githubPullRequestSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Owner and repository are required');
    });
  });

  describe('createPullRequest', () => {
    it('should create pull request successfully', async () => {
      const { invoke } = await import('@tauri-apps/api/tauri');
      (invoke as any).mockResolvedValue({
        id: 2002,
        number: 16,
        title: 'Test PR',
        body: 'Test PR description',
        state: 'open',
        user: { login: 'contributor1', name: 'Contributor One' },
        assignees: [{ login: 'developer1', name: 'Developer One' }],
        requested_reviewers: [{ login: 'reviewer1', name: 'Reviewer One' }],
        head: {
          label: 'atomcompany:feature/test',
          ref_field: 'feature/test',
          sha: 'abc123',
          user: { login: 'contributor1', name: 'Contributor One' }
        },
        base: {
          label: 'atomcompany:main',
          ref_field: 'main',
          sha: 'def456',
          user: { login: 'owner', name: 'Repo Owner' }
        },
        created_at: '2025-11-01T08:00:00Z',
        updated_at: '2025-11-02T16:20:00Z',
        additions: 1250,
        deletions: 85,
        changed_files: 12,
        commits: 5,
        comments: 12,
        review_comments: 8,
        html_url: 'https://github.com/atomcompany/atom-desktop/pull/16',
        merged: false,
        draft: false
      });

      const params: GitHubPullRequestSkillParams = {
        action: 'create',
        owner: 'atomcompany',
        repo: 'atom-desktop',
        title: 'Test PR',
        body: 'Test PR description',
        head: 'feature/test',
        base: 'main'
      };

      const result = await githubPullRequestSkill.execute(params, mockContext);

      expect(result.success).toBe(true);
      expect(result.data?.pr_number).toBe(16);
      expect(result.data?.pr_title).toBe('Test PR');
      expect(result.message).toContain('created successfully');
    });

    it('should require all mandatory fields', async () => {
      const params: GitHubPullRequestSkillParams = {
        action: 'create',
        owner: 'atomcompany',
        repo: 'atom-desktop',
        title: 'Test PR'
        // Missing head and base
      };

      const result = await githubPullRequestSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('title, head branch, and base branch are required');
    });

    it('should validate branch names', async () => {
      const params: GitHubPullRequestSkillParams = {
        action: 'create',
        owner: 'atomcompany',
        repo: 'atom-desktop',
        title: 'Test PR',
        head: 'invalid@branch', // Invalid characters
        base: 'main'
      };

      const result = await githubPullRequestSkill.execute(params, mockContext);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Invalid branch names');
    });
  });

  describe('Pull Request Processing', () => {
    it('should process PR data correctly', () => {
      const rawPR = {
        id: 2001,
        number: 15,
        title: 'Test PR',
        body: 'Test description',
        state: 'open',
        created_at: '2025-11-01T08:00:00Z',
        updated_at: '2025-11-02T16:20:00Z',
        closed_at: null,
        merged_at: null,
        additions: 1250,
        deletions: 85,
        changed_files: 12,
        commits: 5,
        comments: 12,
        review_comments: 8,
        mergeable: true,
        requested_reviewers: [{ login: 'reviewer1' }]
      };

      const processed = githubPullRequestSkill['processPullRequest'](rawPR);

      expect(processed.created).toBeInstanceOf(Date);
      expect(processed.updated).toBeInstanceOf(Date);
      expect(processed.daysSinceCreation).toBeGreaterThan(0);
      expect(processed.complexity).toBeDefined();
      expect(processed.riskLevel).toBeDefined();
      expect(processed.healthScore).toBeGreaterThan(0);
      expect(processed.engagement).toBeDefined();
      expect(processed.status).toBeDefined();
    });

    it('should calculate PR complexity correctly', () => {
      const simplePR = {
        changed_files: 5,
        additions: 100,
        deletions: 20,
        commits: 2,
        comments: 3
      };

      const simpleComplexity = githubPullRequestSkill['calculatePRComplexity'](simplePR);
      expect(simpleComplexity).toBe('low');

      const complexPR = {
        changed_files: 80,
        additions: 2000,
        deletions: 500,
        commits: 25,
        comments: 15
      };

      const complexComplexity = githubPullRequestSkill['calculatePRComplexity'](complexPR);
      expect(complexComplexity).toBe('high');
    });

    it('should calculate PR risk level correctly', () => {
      const riskyPR = {
        changed_files: 60,
        additions: 1500,
        deletions: 300,
        commits: 30,
        daysOld: 45,
        reviewers: [],
        requested_reviewers: []
      };

      const riskLevel = githubPullRequestSkill['calculatePRRiskLevel'](riskyPR);
      expect(['high', 'medium']).toContain(riskLevel);

      const safePR = {
        changed_files: 5,
        additions: 50,
        deletions: 10,
        commits: 3,
        daysOld: 5,
        requested_reviewers: [{ login: 'reviewer1' }]
      };

      const safeRisk = githubPullRequestSkill['calculatePRRiskLevel'](safePR);
      expect(['low', 'medium']).toContain(safeRisk);
    });
  });
});

describe('GitHub Skills Integration', () => {
  let mockContext: SkillExecutionContext;

  beforeEach(() => {
    mockContext = {
      userId: 'test-user',
      sessionId: 'test-session',
      timestamp: '2025-11-02T10:00:00Z',
      intent: { name: 'github_test', confidence: 0.9 },
      entities: [],
      confidence: 0.9
    };

    vi.clearAllMocks();
  });

  describe('Error Handling', () => {
    it('should handle unknown actions gracefully', async () => {
      const params = {
        action: 'unknown_action'
      } as any;

      const repoResult = await githubRepoSkill.execute(params, mockContext);
      expect(repoResult.success).toBe(false);
      expect(repoResult.error).toContain('Unknown repository action');

      const issueResult = await githubIssueSkill.execute(params, mockContext);
      expect(issueResult.success).toBe(false);
      expect(issueResult.error).toContain('Unknown issue action');

      const prResult = await githubPullRequestSkill.execute(params, mockContext);
      expect(prResult.success).toBe(false);
      expect(prResult.error).toContain('Unknown pull request action');
    });
  });

  describe('Data Validation', () => {
    it('should validate required fields across all skills', async () => {
      // Repo skill validations
      const createRepoNoName = await githubRepoSkill.execute({
        action: 'create'
      } as any, mockContext);
      expect(createRepoNoName.success).toBe(false);

      const searchRepoNoQuery = await githubRepoSkill.execute({
        action: 'search'
      } as any, mockContext);
      expect(searchRepoNoQuery.success).toBe(false);

      // Issue skill validations
      const createIssueNoTitle = await githubIssueSkill.execute({
        action: 'create',
        owner: 'test',
        repo: 'test'
      } as any, mockContext);
      expect(createIssueNoTitle.success).toBe(false);

      // PR skill validations
      const createPRNoTitle = await githubPullRequestSkill.execute({
        action: 'create',
        owner: 'test',
        repo: 'test'
      } as any, mockContext);
      expect(createPRNoTitle.success).toBe(false);
    });
  });

  describe('Performance Metrics', () => {
    it('should include relevant metrics in responses', async () => {
      const { invoke } = await import('@tauri-apps/api/tauri');
      (invoke as any).mockResolvedValue([]);

      const repoResult = await githubRepoSkill.execute({
        action: 'list',
        limit: 10
      }, mockContext);

      expect(repoResult.data?.statistics).toBeDefined();
      expect(repoResult.timestamp).toBeDefined();

      // Test timing information is included
      expect(typeof repoResult.timestamp).toBe('string');
      expect(new Date(repoResult.timestamp)).toBeInstanceOf(Date);
    });
  });
});