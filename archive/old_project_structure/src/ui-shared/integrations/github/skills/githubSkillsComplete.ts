/**
 * GitHub Integration Skills
 * Provides comprehensive GitHub repository and code management capabilities
 */

import { IntegrationSkill, SkillExecutionContext } from '../types';
import { Octokit } from '@octokit/rest';

export interface GitHubSkillConfig {
  accessToken?: string;
  baseUrl?: string;
  userAgent?: string;
}

export interface GitHubRepository {
  id: number;
  name: string;
  fullName: string;
  description?: string;
  private: boolean;
  fork: boolean;
  htmlUrl: string;
  cloneUrl: string;
  sshUrl: string;
  language?: string;
  stargazersCount: number;
  watchersCount: number;
  forksCount: number;
  openIssuesCount: number;
  defaultBranch: string;
  createdAt: string;
  updatedAt: string;
  pushedAt?: string;
  size: number;
  owner: {
    login: string;
    avatarUrl?: string;
  };
  topics: string[];
  license?: {
    name: string;
  };
  visibility: 'public' | 'private';
}

export interface GitHubIssue {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: 'open' | 'closed';
  locked: boolean;
  comments: number;
  createdAt: string;
  updatedAt: string;
  closedAt?: string;
  user: {
    login: string;
    avatarUrl?: string;
  };
  assignee?: {
    login: string;
    avatarUrl?: string;
  };
  assignees: Array<{
    login: string;
    avatarUrl?: string;
  }>;
  labels: Array<{
    name: string;
    color: string;
  }>;
  milestone?: {
    title: string;
    state: 'open' | 'closed';
  };
  htmlUrl: string;
  reactions: {
    totalCount: number;
    plusOne: number;
    laugh: number;
    hooray: number;
    confused: number;
    heart: number;
    rocket: number;
    eyes: number;
  };
  repositoryUrl: string;
}

export interface GitHubPullRequest {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: 'open' | 'closed';
  locked: boolean;
  createdAt: string;
  updatedAt: string;
  closedAt?: string;
  mergedAt?: string;
  mergeCommitSha?: string;
  head: {
    ref: string;
    sha: string;
    label: string;
    repo: {
      name: string;
      url: string;
    };
  };
  base: {
    ref: string;
    sha: string;
    label: string;
    repo: {
      name: string;
      url: string;
    };
  };
  user: {
    login: string;
    avatarUrl?: string;
  };
  assignees: Array<{
    login: string;
    avatarUrl?: string;
  }>;
  requestedReviewers: Array<{
    login: string;
    avatarUrl?: string;
  }>;
  labels: Array<{
    name: string;
    color: string;
  }>;
  milestone?: {
    title: string;
    state: 'open' | 'closed';
  };
  commits: number;
  additions: number;
  deletions: number;
  changedFiles: number;
  htmlUrl: string;
  diffUrl: string;
  patchUrl: string;
}

export interface GitHubUser {
  id: number;
  login: string;
  name?: string;
  email?: string;
  bio?: string;
  company?: string;
  location?: string;
  blog?: string;
  avatarUrl?: string;
  htmlUrl: string;
  followers: number;
  following: number;
  publicRepos: number;
  createdAt: string;
  updatedAt: string;
}

/**
 * GitHub Skills Registry
 */
export const githubSkills: Record<string, IntegrationSkill> = {
  
  /**
   * Create a new GitHub repository
   */
  githubCreateRepo: {
    id: 'githubCreateRepo',
    name: 'Create GitHub Repository',
    description: 'Create a new repository on GitHub',
    category: 'code-management',
    icon: '📦',
    parameters: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Repository name (required)'
        },
        description: {
          type: 'string',
          description: 'Repository description (optional)'
        },
        private: {
          type: 'boolean',
          description: 'Whether repository should be private (default: false)',
          default: false
        },
        autoInit: {
          type: 'boolean',
          description: 'Initialize with README (default: true)',
          default: true
        },
        license: {
          type: 'string',
          description: 'License template (optional)',
          enum: ['mit', 'apache-2.0', 'gpl-3.0', 'bsd-3-clause', 'none']
        },
        gitignoreTemplate: {
          type: 'string',
          description: 'Gitignore template (optional)'
        }
      },
      required: ['name']
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as GitHubSkillConfig;
        const response = await fetch('/api/github/repositories/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            name: params.name,
            description: params.description || '',
            private: params.private || false,
            auto_init: params.autoInit !== false
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to create repository');
        }

        return {
          success: true,
          data: {
            repository: result.data.repository,
            url: result.data.url,
            cloneUrl: result.data.clone_url,
            sshUrl: result.data.ssh_url,
            message: 'Repository created successfully'
          }
        };
      } catch (error) {
        console.error('Error creating GitHub repository:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * List GitHub repositories
   */
  githubListRepos: {
    id: 'githubListRepos',
    name: 'List GitHub Repositories',
    description: 'List repositories accessible to the user',
    category: 'code-management',
    icon: '📚',
    parameters: {
      type: 'object',
      properties: {
        type: {
          type: 'string',
          enum: ['all', 'owner', 'member'],
          description: 'Repository type (default: all)',
          default: 'all'
        },
        sort: {
          type: 'string',
          enum: ['created', 'updated', 'pushed', 'full_name'],
          description: 'Sort field (default: updated)',
          default: 'updated'
        },
        direction: {
          type: 'string',
          enum: ['asc', 'desc'],
          description: 'Sort direction (default: desc)',
          default: 'desc'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of repositories to return (default: 50)',
          default: 50
        },
        includeForks: {
          type: 'boolean',
          description: 'Include forked repositories (default: true)',
          default: true
        }
      }
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as GitHubSkillConfig;
        const response = await fetch('/api/github/repositories', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            type: params.type || 'all',
            sort: params.sort || 'updated',
            direction: params.direction || 'desc',
            limit: params.limit || 50
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to list repositories');
        }

        let repositories = result.data.repositories;
        
        // Filter out forks if requested
        if (params.includeForks === false) {
          repositories = repositories.filter((repo: GitHubRepository) => !repo.fork);
        }

        return {
          success: true,
          data: {
            repositories: repositories,
            totalCount: result.data.total_count,
            pagination: result.data.pagination
          }
        };
      } catch (error) {
        console.error('Error listing GitHub repositories:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * Create a new GitHub issue
   */
  githubCreateIssue: {
    id: 'githubCreateIssue',
    name: 'Create GitHub Issue',
    description: 'Create a new issue in a GitHub repository',
    category: 'issue-tracking',
    icon: '🐛',
    parameters: {
      type: 'object',
      properties: {
        owner: {
          type: 'string',
          description: 'Repository owner (default: developer)',
          default: 'developer'
        },
        repo: {
          type: 'string',
          description: 'Repository name (default: atom-platform)',
          default: 'atom-platform'
        },
        title: {
          type: 'string',
          description: 'Issue title (required)'
        },
        body: {
          type: 'string',
          description: 'Issue body/description (optional)'
        },
        labels: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Issue labels (optional)'
        },
        assignees: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Assignees (optional)'
        }
      },
      required: ['title']
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as GitHubSkillConfig;
        const response = await fetch('/api/github/issues/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            owner: params.owner || 'developer',
            repo: params.repo || 'atom-platform',
            title: params.title,
            body: params.body || '',
            labels: params.labels || [],
            assignees: params.assignees || []
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to create issue');
        }

        return {
          success: true,
          data: {
            issue: result.data.issue,
            url: result.data.url,
            message: 'Issue created successfully'
          }
        };
      } catch (error) {
        console.error('Error creating GitHub issue:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * List GitHub issues
   */
  githubListIssues: {
    id: 'githubListIssues',
    name: 'List GitHub Issues',
    description: 'List issues from repositories',
    category: 'issue-tracking',
    icon: '📝',
    parameters: {
      type: 'object',
      properties: {
        owner: {
          type: 'string',
          description: 'Repository owner (default: developer)',
          default: 'developer'
        },
        repo: {
          type: 'string',
          description: 'Repository name (default: atom-platform)',
          default: 'atom-platform'
        },
        state: {
          type: 'string',
          enum: ['open', 'closed', 'all'],
          description: 'Issue state (default: open)',
          default: 'open'
        },
        sort: {
          type: 'string',
          enum: ['created', 'updated', 'comments'],
          description: 'Sort field (default: updated)',
          default: 'updated'
        },
        direction: {
          type: 'string',
          enum: ['asc', 'desc'],
          description: 'Sort direction (default: desc)',
          default: 'desc'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of issues to return (default: 50)',
          default: 50
        },
        labels: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Filter by labels (optional)'
        }
      }
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as GitHubSkillConfig;
        const response = await fetch('/api/github/issues', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            owner: params.owner || 'developer',
            repo: params.repo || 'atom-platform',
            state: params.state || 'open',
            sort: params.sort || 'updated',
            direction: params.direction || 'desc',
            limit: params.limit || 50
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to list issues');
        }

        let issues = result.data.issues;
        
        // Filter by labels if provided
        if (params.labels && params.labels.length > 0) {
          issues = issues.filter((issue: GitHubIssue) => 
            issue.labels.some((label: any) => params.labels.includes(label.name))
          );
        }

        return {
          success: true,
          data: {
            issues: issues,
            totalCount: result.data.total_count,
            pagination: result.data.pagination
          }
        };
      } catch (error) {
        console.error('Error listing GitHub issues:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * Create a new pull request
   */
  githubCreatePR: {
    id: 'githubCreatePR',
    name: 'Create Pull Request',
    description: 'Create a new pull request in a GitHub repository',
    category: 'code-review',
    icon: '🔀',
    parameters: {
      type: 'object',
      properties: {
        owner: {
          type: 'string',
          description: 'Repository owner (default: developer)',
          default: 'developer'
        },
        repo: {
          type: 'string',
          description: 'Repository name (default: atom-platform)',
          default: 'atom-platform'
        },
        title: {
          type: 'string',
          description: 'Pull request title (required)'
        },
        head: {
          type: 'string',
          description: 'Head branch (required)'
        },
        base: {
          type: 'string',
          description: 'Base branch (default: main)',
          default: 'main'
        },
        body: {
          type: 'string',
          description: 'Pull request description (optional)'
        },
        draft: {
          type: 'boolean',
          description: 'Create as draft pull request (default: false)',
          default: false
        }
      },
      required: ['title', 'head']
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as GitHubSkillConfig;
        const response = await fetch('/api/github/pulls/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            owner: params.owner || 'developer',
            repo: params.repo || 'atom-platform',
            title: params.title,
            head: params.head,
            base: params.base || 'main',
            body: params.body || ''
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to create pull request');
        }

        return {
          success: true,
          data: {
            pullRequest: result.data.pull_request,
            url: result.data.url,
            diffUrl: result.data.diff_url,
            message: 'Pull request created successfully'
          }
        };
      } catch (error) {
        console.error('Error creating GitHub pull request:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * List pull requests
   */
  githubListPRs: {
    id: 'githubListPRs',
    name: 'List Pull Requests',
    description: 'List pull requests from a repository',
    category: 'code-review',
    icon: '🔄',
    parameters: {
      type: 'object',
      properties: {
        owner: {
          type: 'string',
          description: 'Repository owner (default: developer)',
          default: 'developer'
        },
        repo: {
          type: 'string',
          description: 'Repository name (default: atom-platform)',
          default: 'atom-platform'
        },
        state: {
          type: 'string',
          enum: ['open', 'closed', 'all'],
          description: 'Pull request state (default: open)',
          default: 'open'
        },
        sort: {
          type: 'string',
          enum: ['created', 'updated', 'popularity'],
          description: 'Sort field (default: created)',
          default: 'created'
        },
        direction: {
          type: 'string',
          enum: ['asc', 'desc'],
          description: 'Sort direction (default: desc)',
          default: 'desc'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of pull requests to return (default: 50)',
          default: 50
        }
      }
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as GitHubSkillConfig;
        const response = await fetch('/api/github/pulls', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            owner: params.owner || 'developer',
            repo: params.repo || 'atom-platform',
            state: params.state || 'open',
            sort: params.sort || 'created',
            direction: params.direction || 'desc',
            limit: params.limit || 50
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to list pull requests');
        }

        return {
          success: true,
          data: {
            pullRequests: result.data.pull_requests,
            totalCount: result.data.total_count,
            repository: result.data.repository,
            pagination: result.data.pagination
          }
        };
      } catch (error) {
        console.error('Error listing GitHub pull requests:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * Search GitHub
   */
  githubSearch: {
    id: 'githubSearch',
    name: 'Search GitHub',
    description: 'Search repositories, issues, and users on GitHub',
    category: 'search',
    icon: '🔍',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query (required)'
        },
        searchType: {
          type: 'string',
          enum: ['repositories', 'issues', 'users', 'code'],
          description: 'Search type (default: repositories)',
          default: 'repositories'
        },
        sort: {
          type: 'string',
          description: 'Sort field (varies by type)',
          default: 'updated'
        },
        order: {
          type: 'string',
          enum: ['asc', 'desc'],
          description: 'Sort order (default: desc)',
          default: 'desc'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results to return (default: 50)',
          default: 50
        }
      },
      required: ['query']
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as GitHubSkillConfig;
        const response = await fetch('/api/github/search', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            query: params.query,
            search_type: params.searchType || 'repositories',
            sort: params.sort || 'updated',
            order: params.order || 'desc',
            limit: params.limit || 50
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to search GitHub');
        }

        return {
          success: true,
          data: {
            results: result.data.repositories || result.data.issues || result.data.users || result.data.code,
            totalCount: result.data.total_count,
            query: params.query,
            searchType: params.searchType || 'repositories'
          }
        };
      } catch (error) {
        console.error('Error searching GitHub:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * Get user profile
   */
  githubGetProfile: {
    id: 'githubGetProfile',
    name: 'Get GitHub Profile',
    description: 'Get authenticated user GitHub profile and information',
    category: 'user-management',
    icon: '👤',
    parameters: {
      type: 'object',
      properties: {}
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as GitHubSkillConfig;
        const response = await fetch('/api/github/user/profile', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to get profile');
        }

        return {
          success: true,
          data: {
            user: result.data.user
          }
        };
      } catch (error) {
        console.error('Error getting GitHub profile:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  }
};

/**
 * GitHub skill hooks and utilities
 */
export const githubHooks = {
  /**
   * Validate GitHub access token
   */
  validateToken: async (accessToken: string): Promise<boolean> => {
    try {
      const response = await fetch('/api/github/health', {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });
      return response.ok;
    } catch {
      return false;
    }
  },

  /**
   * Format repository for display
   */
  formatRepository: (repo: GitHubRepository): string => {
    const visibility = repo.private ? '🔒 Private' : '🌍 Public';
    const language = repo.language ? ` ${repo.language}` : '';
    const stars = repo.stargazersCount > 0 ? ` ⭐ ${repo.stargazersCount}` : '';
    return `${repo.fullName}${language} (${visibility}${stars})`;
  },

  /**
   * Format issue for display
   */
  formatIssue: (issue: GitHubIssue): string => {
    const labels = issue.labels.length > 0 
      ? ` [${issue.labels.map(l => l.name).join(', ')}]` 
      : '';
    const state = issue.state === 'open' ? '🟢' : '🔴';
    return `${state} #${issue.number}: ${issue.title}${labels}`;
  },

  /**
   * Format pull request for display
   */
  formatPullRequest: (pr: GitHubPullRequest): string => {
    const status = pr.state === 'open' 
      ? (pr.mergedAt ? '🟣' : '🟢') 
      : (pr.mergedAt ? '🟣' : '🔴');
    return `${status} #${pr.number}: ${pr.title}`;
  },

  /**
   * Get issue URL
   */
  getIssueUrl: (issue: GitHubIssue): string => {
    return issue.htmlUrl || `https://github.com/owner/repo/issues/${issue.number}`;
  },

  /**
   * Get pull request URL
   */
  getPullRequestUrl: (pr: GitHubPullRequest): string => {
    return pr.htmlUrl || `https://github.com/owner/repo/pull/${pr.number}`;
  },

  /**
   * Extract repository name from full name
   */
  extractRepoName: (fullName: string): string => {
    return fullName.split('/')[1] || fullName;
  },

  /**
   * Generate repository URL
   */
  getRepoUrl: (owner: string, repo: string): string => {
    return `https://github.com/${owner}/${repo}`;
  },

  /**
   * Check if repository is fork
   */
  isFork: (repo: GitHubRepository): boolean => {
    return repo.fork || false;
  },

  /**
   * Get repository language color
   */
  getLanguageColor: (language: string): string => {
    const colors: Record<string, string> = {
      'TypeScript': '#3178c6',
      'JavaScript': '#f1e05a',
      'Python': '#3572A5',
      'Java': '#b07219',
      'C++': '#f34b7d',
      'C#': '#239120',
      'Go': '#00ADD8',
      'Rust': '#dea584',
      'Swift': '#ffac45',
      'Ruby': '#701516',
      'PHP': '#4F5D95',
      'HTML': '#e34c26',
      'CSS': '#563d7c',
      'Shell': '#89e051'
    };
    return colors[language] || '#cccccc';
  }
};

export default githubSkills;