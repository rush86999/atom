"""
GitHub Enhanced Skills
Complete GitHub repository management and code collaboration system
"""

import { Skill, SkillContext, SkillResult } from '../../../types/skillTypes';

/**
 * GitHub Enhanced Skills
 * Complete GitHub repository management and code collaboration system
 */

// Repository Management Skills
export class GitHubCreateRepoSkill implements Skill {
  id = 'github_create_repo';
  name = 'Create GitHub Repository';
  description = 'Create a new repository in GitHub';
  category = 'development';
  examples = [
    'Create GitHub repo for my new project',
    'Start new repository called awesome-app',
    'Create private GitHub repository for client project'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract repository details
      const repoName = this.extractRepoName(intent) ||
                     entities.find((e: any) => e.type === 'repo_name')?.value ||
                     'new-repository';
      
      const description = this.extractDescription(intent) ||
                       entities.find((e: any) => e.type === 'description')?.value ||
                       intent;
      
      const visibility = this.extractVisibility(intent) ||
                       entities.find((e: any) => e.type === 'visibility')?.value ||
                       'public';
      
      const language = this.extractLanguage(intent) ||
                     entities.find((e: any) => e.type === 'language')?.value;

      if (!repoName) {
        return {
          success: false,
          message: 'Repository name is required',
          error: 'Missing repository name'
        };
      }

      // Call GitHub API
      const response = await fetch('/api/integrations/github/repositories', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          data: {
            name: repoName,
            description: description,
            private: visibility === 'private',
            auto_init: true,
            gitignore_template: this.getGitignoreTemplate(language),
            license_template: this.getLicenseTemplate(),
            default_branch: 'main'
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `GitHub repository "${repoName}" created successfully`,
          data: {
            repository: result.data.repository,
            url: result.data.url,
            name: repoName,
            visibility: visibility
          },
          actions: [
            {
              type: 'open_url',
              label: 'View on GitHub',
              url: result.data.url
            },
            {
              type: 'copy_to_clipboard',
              label: 'Clone URL',
              text: result.data.repository.clone_url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create GitHub repository: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating GitHub repository: ${error}`,
        error: error as any
      };
    }
  }

  private extractRepoName(intent: string): string | null {
    const patterns = [
      /create (?:github )?repo(?:sitory)? (?:called|named) (.+?)(?: for|with|:|$)/i,
      /create (?:github )?repo(?:sitory)? (.+?)(?: for|with|:|$)/i,
      /repo(?:sitory)? (?:called|named) (.+?)(?: for|with|:|$)/i,
      /start (?:new )?repo(?:sitory)? (.+?)(?: for|with|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    const patterns = [
      /(?:for|with) (.+?)(?: description|visibility|language|:|$)/i,
      /description (.+?)(?: visibility|language|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return intent;
  }

  private extractVisibility(intent: string): string | null {
    if (intent.toLowerCase().includes('private')) {
      return 'private';
    } else if (intent.toLowerCase().includes('public')) {
      return 'public';
    }
    return null;
  }

  private extractLanguage(intent: string): string | null {
    const languages = ['javascript', 'typescript', 'python', 'java', 'go', 'rust', 'c++', 'c#', 'php', 'ruby', 'swift', 'kotlin', 'dart'];
    
    for (const lang of languages) {
      if (intent.toLowerCase().includes(lang)) {
        return lang;
      }
    }
    
    return null;
  }

  private getGitignoreTemplate(language: string | null): string | null {
    const templates = {
      'javascript': 'Node',
      'typescript': 'Node',
      'python': 'Python',
      'java': 'Java',
      'go': 'Go',
      'rust': 'Rust',
      'c++': 'C++',
      'c#': 'VisualStudio',
      'php': 'PHP',
      'ruby': 'Ruby',
      'swift': 'Swift',
      'kotlin': 'Kotlin',
      'dart': 'Dart'
    };
    
    return language ? templates[language as keyof typeof templates] || null : null;
  }

  private getLicenseTemplate(): string | null {
    return 'mit'; // Default to MIT license
  }
}

export class GitHubSearchReposSkill implements Skill {
  id = 'github_search_repos';
  name = 'Search GitHub Repositories';
  description = 'Search repositories in GitHub';
  category = 'development';
  examples = [
    'Search GitHub for React repositories',
    'Find TypeScript projects on GitHub',
    'Look for open source Python repos'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search query
      const query = this.extractQuery(intent) ||
                 entities.find((e: any) => e.type === 'query')?.value ||
                 intent;
      
      const language = this.extractLanguage(intent) ||
                     entities.find((e: any) => e.type === 'language')?.value;
      
      const sort = this.extractSort(intent) ||
                 entities.find((e: any) => e.type === 'sort')?.value ||
                 'stars';
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Build search query
      let searchQuery = query;
      if (language) {
        searchQuery += ` language:${language}`;
      }

      // Call GitHub API
      const response = await fetch('/api/integrations/github/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: searchQuery,
          type: 'repositories',
          sort: sort,
          order: 'desc',
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const repos = result.data.results || [];
        const repoCount = repos.length;

        return {
          success: true,
          message: `Found ${repoCount} GitHub repositor${repoCount !== 1 ? 'ies' : 'y'} matching "${query}"`,
          data: {
            repositories: repos,
            total_count: result.data.total_count,
            query: query,
            language: language,
            sort: sort
          },
          actions: repos.map((repo: any) => ({
            type: 'open_url',
            label: `View ${repo.name}`,
            url: repo.html_url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search GitHub repositories: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching GitHub repositories: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:github for )?(.+?)(?: repositories|projects|repos|:|$)/i,
      /find (.+?) (?:repositories|projects|repos|on github|:|$)/i,
      /look for (.+?) (?:repositories|projects|repos|on github|:|$)/i,
      /(.+?) (?:repositories|projects|repos|on github|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractLanguage(intent: string): string | null {
    const languages = ['javascript', 'typescript', 'python', 'java', 'go', 'rust', 'c++', 'c#', 'php', 'ruby', 'swift', 'kotlin', 'dart', 'react', 'vue', 'angular'];
    
    for (const lang of languages) {
      if (intent.toLowerCase().includes(lang)) {
        return lang;
      }
    }
    
    return null;
  }

  private extractSort(intent: string): string | null {
    if (intent.toLowerCase().includes('stars')) {
      return 'stars';
    } else if (intent.toLowerCase().includes('forks')) {
      return 'forks';
    } else if (intent.toLowerCase().includes('updated')) {
      return 'updated';
    } else if (intent.toLowerCase().includes('created')) {
      return 'created';
    }
    return null;
  }
}

export class GitHubCreateIssueSkill implements Skill {
  id = 'github_create_issue';
  name = 'Create GitHub Issue';
  description = 'Create a new issue in GitHub';
  category = 'development';
  examples = [
    'Create GitHub issue for bug in my app',
    'File issue about authentication problem',
    'Open issue on testuser/repo for documentation'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract issue details
      const title = this.extractTitle(intent) ||
                 entities.find((e: any) => e.type === 'title')?.value;
      
      const description = this.extractDescription(intent) ||
                        entities.find((e: any) => e.type === 'description')?.value ||
                        intent;
      
      const repoPath = this.extractRepoPath(intent) ||
                      entities.find((e: any) => e.type === 'repo_path')?.value;
      
      const labels = this.extractLabels(intent) ||
                  entities.find((e: any) => e.type === 'labels')?.value ||
                  [];

      if (!title) {
        return {
          success: false,
          message: 'Issue title is required',
          error: 'Missing issue title'
        };
      }

      // Parse owner and repo from repo path
      let owner = 'testuser';
      let repo = 'awesome-project';
      
      if (repoPath && repoPath.includes('/')) {
        [owner, repo] = repoPath.split('/');
      }

      // Call GitHub API
      const response = await fetch('/api/integrations/github/issues', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          owner: owner,
          repo: repo,
          data: {
            title: title,
            body: description,
            labels: Array.isArray(labels) ? labels : labels.split(',').map((l: string) => l.trim())
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `GitHub issue "${title}" created successfully`,
          data: {
            issue: result.data.issue,
            url: result.data.url,
            title: title,
            repository: `${owner}/${repo}`
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Issue',
              url: result.data.url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create GitHub issue: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating GitHub issue: ${error}`,
        error: error as any
      };
    }
  }

  private extractTitle(intent: string): string | null {
    const patterns = [
      /create (?:github )?issue (?:titled|for) (.+?)(?: in|description|:|$)/i,
      /file issue (?:titled|for) (.+?)(?: in|description|:|$)/i,
      /open issue (?:titled|for) (.+?)(?: in|description|:|$)/i,
      /issue (?:titled|for) (.+?)(?: in|description|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    const patterns = [
      /(?:about|for) (.+?)(?: in|:|$)/i,
      /description (.+?)(?: in|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractRepoPath(intent: string): string | null {
    const patterns = [
      /in (.+?) (?:for|about|description|:|$)/i,
      /on (.+?) (?:for|about|description|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractLabels(intent: string): string[] {
    const labels = ['bug', 'enhancement', 'documentation', 'good first issue', 'help wanted'];
    const foundLabels: string[] = [];
    
    for (const label of labels) {
      if (intent.toLowerCase().includes(label)) {
        foundLabels.push(label);
      }
    }
    
    return foundLabels;
  }
}

export class GitHubCreatePullSkill implements Skill {
  id = 'github_create_pull';
  name = 'Create GitHub Pull Request';
  description = 'Create a new pull request in GitHub';
  category = 'development';
  examples = [
    'Create GitHub pull request from feature-branch to main',
    'Open PR for my changes on testuser/repo',
    'Create pull request for bug fix'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract PR details
      const title = this.extractTitle(intent) ||
                 entities.find((e: any) => e.type === 'title')?.value ||
                 'New feature implementation';
      
      const description = this.extractDescription(intent) ||
                        entities.find((e: any) => e.type === 'description')?.value ||
                        'Implement new feature with improvements';
      
      const repoPath = this.extractRepoPath(intent) ||
                      entities.find((e: any) => e.type === 'repo_path')?.value;
      
      const head = this.extractHead(intent) ||
                 entities.find((e: any) => e.type === 'head')?.value ||
                 'feature-branch';
      
      const base = this.extractBase(intent) ||
                 entities.find((e: any) => e.type === 'base')?.value ||
                 'main';

      // Parse owner and repo from repo path
      let owner = 'testuser';
      let repo = 'awesome-project';
      
      if (repoPath && repoPath.includes('/')) {
        [owner, repo] = repoPath.split('/');
      }

      // Call GitHub API
      const response = await fetch('/api/integrations/github/pulls', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          operation: 'create',
          owner: owner,
          repo: repo,
          data: {
            title: title,
            body: description,
            head: head,
            base: base,
            draft: false
          }
        })
      });

      const result = await response.json();

      if (result.ok) {
        return {
          success: true,
          message: `GitHub pull request "${title}" created successfully`,
          data: {
            pull_request: result.data.pull_request,
            url: result.data.url,
            title: title,
            repository: `${owner}/${repo}`,
            head: head,
            base: base
          },
          actions: [
            {
              type: 'open_url',
              label: 'View Pull Request',
              url: result.data.url
            }
          ]
        };
      } else {
        return {
          success: false,
          message: `Failed to create GitHub pull request: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error creating GitHub pull request: ${error}`,
        error: error as any
      };
    }
  }

  private extractTitle(intent: string): string | null {
    const patterns = [
      /create (?:github )?pull request (?:titled|for) (.+?)(?: from|to|:|$)/i,
      /open pr (?:titled|for) (.+?)(?: from|to|:|$)/i,
      /pull request (?:titled|for) (.+?)(?: from|to|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractDescription(intent: string): string | null {
    const patterns = [
      /(?:for|with) (.+?)(?: from|to|:|$)/i,
      /description (.+?)(?: from|to|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractRepoPath(intent: string): string | null {
    const patterns = [
      /on (.+?) (?:for|from|to|:|$)/i,
      /in (.+?) (?:for|from|to|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractHead(intent: string): string | null {
    const patterns = [
      /from (.+?)(?: to|:|$)/i,
      /branch (.+?)(?: to|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractBase(intent: string): string | null {
    const patterns = [
      /to (.+?)(?: from|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }
}

// GitHub Search Skill
export class GitHubSearchSkill implements Skill {
  id = 'github_search';
  name = 'Search GitHub';
  description = 'Search across GitHub repositories, issues, and pull requests';
  category = 'development';
  examples = [
    'Search GitHub for React hooks',
    'Find TypeScript repositories on GitHub',
    'Look for open issues about authentication'
  ];

  async execute(context: SkillContext): Promise<SkillResult> {
    try {
      const { intent, entities } = context;
      
      // Extract search details
      const query = this.extractQuery(intent) ||
                 entities.find((e: any) => e.type === 'query')?.value ||
                 intent;
      
      const searchType = this.extractSearchType(intent) ||
                       entities.find((e: any) => e.type === 'search_type')?.value ||
                       'repositories';
      
      const language = this.extractLanguage(intent) ||
                     entities.find((e: any) => e.type === 'language')?.value;
      
      const limit = entities.find((e: any) => e.type === 'limit')?.value || 20;

      // Build search query
      let searchQuery = query;
      if (language) {
        searchQuery += ` language:${language}`;
      }

      // Call GitHub API
      const response = await fetch('/api/integrations/github/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: context.user?.id || 'default',
          query: searchQuery,
          type: searchType,
          sort: 'updated',
          order: 'desc',
          limit: limit
        })
      });

      const result = await response.json();

      if (result.ok) {
        const searchResults = result.data.results || [];
        const resultCount = searchResults.length;

        return {
          success: true,
          message: `Found ${resultCount} result${resultCount !== 1 ? 's' : ''} for "${query}" in GitHub`,
          data: {
            results: searchResults,
            total_count: result.data.total_count,
            query: query,
            search_type: searchType,
            language: language
          },
          actions: searchResults.map((item: any) => ({
            type: 'open_url',
            label: `View ${item.name || item.title}`,
            url: item.html_url
          }))
        };
      } else {
        return {
          success: false,
          message: `Failed to search GitHub: ${result.error?.message || 'Unknown error'}`,
          error: result.error
        };
      }
    } catch (error) {
      return {
        success: false,
        message: `Error searching GitHub: ${error}`,
        error: error as any
      };
    }
  }

  private extractQuery(intent: string): string | null {
    const patterns = [
      /search (?:github for )?(.+?)(?: repositories|issues|pulls|:|$)/i,
      /find (.+?) (?:repositories|issues|pulls|on github|:|$)/i,
      /look for (.+?) (?:repositories|issues|pulls|on github|:|$)/i,
      /(.+?) (?:repositories|issues|pulls|on github|:|$)/i
    ];

    for (const pattern of patterns) {
      const match = intent.match(pattern);
      if (match) {
        return match[1].trim().replace(/^['"]|['"]$/g, '');
      }
    }

    return null;
  }

  private extractSearchType(intent: string): string | null {
    if (intent.toLowerCase().includes('issues')) {
      return 'issues';
    } else if (intent.toLowerCase().includes('pull') || intent.toLowerCase().includes('pr')) {
      return 'pulls';
    } else if (intent.toLowerCase().includes('users')) {
      return 'users';
    } else if (intent.toLowerCase().includes('code')) {
      return 'code';
    }
    return 'repositories';
  }

  private extractLanguage(intent: string): string | null {
    const languages = ['javascript', 'typescript', 'python', 'java', 'go', 'rust', 'c++', 'c#', 'php', 'ruby', 'swift', 'kotlin', 'dart', 'react', 'vue', 'angular'];
    
    for (const lang of languages) {
      if (intent.toLowerCase().includes(lang)) {
        return lang;
      }
    }
    
    return null;
  }
}

// Export all GitHub skills
export const GITHUB_SKILLS = [
  new GitHubCreateRepoSkill(),
  new GitHubSearchReposSkill(),
  new GitHubCreateIssueSkill(),
  new GitHubCreatePullSkill(),
  new GitHubSearchSkill()
];

// Export skills registry
export const GITHUB_SKILLS_REGISTRY = {
  'github_create_repo': GitHubCreateRepoSkill,
  'github_search_repos': GitHubSearchReposSkill,
  'github_create_issue': GitHubCreateIssueSkill,
  'github_create_pull': GitHubCreatePullSkill,
  'github_search': GitHubSearchSkill
};