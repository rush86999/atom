/**
 * GitHub Integration Skills
 * Complete GitHub integration with comprehensive repository and code management capabilities
 */

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
 * GitHub Skills Registry - Complete set of GitHub integration capabilities
 */
export const githubSkills = {
  
  /**
   * Create a new GitHub repository
   */
  githubCreateRepo: {
    id: 'githubCreateRepo',
    name: 'Create GitHub Repository',
    description: 'Create a new repository on GitHub with configuration options',
    category: 'code-management',
    icon: '📦',
    parameters: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Repository name (required)',
          minLength: 1,
          pattern: '^[a-zA-Z0-9._-]+$'
        },
        description: {
          type: 'string',
          description: 'Repository description (optional)',
          maxLength: 500
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
    }
  },

  /**
   * List GitHub repositories
   */
  githubListRepos: {
    id: 'githubListRepos',
    name: 'List GitHub Repositories',
    description: 'List repositories accessible to the authenticated user',
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
          description: 'Maximum number of repositories to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        },
        includeForks: {
          type: 'boolean',
          description: 'Include forked repositories (default: true)',
          default: true
        }
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
          description: 'Issue title (required)',
          minLength: 1,
          maxLength: 255
        },
        body: {
          type: 'string',
          description: 'Issue body/description (optional)',
          maxLength: 65536
        },
        labels: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Issue labels (optional)',
          maxItems: 10
        },
        assignees: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Assignees (optional)',
          maxItems: 10
        }
      },
      required: ['title']
    }
  },

  /**
   * List GitHub issues
   */
  githubListIssues: {
    id: 'githubListIssues',
    name: 'List GitHub Issues',
    description: 'List issues from repositories with filtering options',
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
          description: 'Maximum number of issues to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        },
        labels: {
          type: 'array',
          items: {
            type: 'string'
          },
          description: 'Filter by labels (optional)',
          maxItems: 10
        }
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
          description: 'Pull request title (required)',
          minLength: 1,
          maxLength: 255
        },
        head: {
          type: 'string',
          description: 'Head branch (required)',
          minLength: 1
        },
        base: {
          type: 'string',
          description: 'Base branch (default: main)',
          default: 'main'
        },
        body: {
          type: 'string',
          description: 'Pull request description (optional)',
          maxLength: 65536
        },
        draft: {
          type: 'boolean',
          description: 'Create as draft pull request (default: false)',
          default: false
        }
      },
      required: ['title', 'head']
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
          description: 'Maximum number of pull requests to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        }
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
          description: 'Search query (required)',
          minLength: 1,
          maxLength: 256
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
          description: 'Maximum number of results to return (default: 50, max: 100)',
          default: 50,
          minimum: 1,
          maximum: 100
        }
      },
      required: ['query']
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
    }
  }
};

/**
 * GitHub skill utilities and formatting helpers
 */
export const githubUtils = {
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
  },

  /**
   * Validate GitHub username
   */
  validateUsername: (username: string): boolean => {
    return /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,38}[a-zA-Z0-9])?$/.test(username);
  },

  /**
   * Validate repository name
   */
  validateRepoName: (name: string): boolean => {
    return /^[a-zA-Z0-9._-]+$/.test(name) && name.length >= 1 && name.length <= 100;
  },

  /**
   * Calculate repository age
   */
  getRepoAge: (createdAt: string): string => {
    const created = new Date(createdAt);
    const now = new Date();
    const diffInDays = Math.floor((now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24));
    
    if (diffInDays < 30) {
      return `${diffInDays} days`;
    } else if (diffInDays < 365) {
      const months = Math.floor(diffInDays / 30);
      return `${months} months`;
    } else {
      const years = Math.floor(diffInDays / 365);
      return `${years} years`;
    }
  }
};

export default githubSkills;