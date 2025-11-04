/**
 * GitHub Integration Skills
 * Natural language commands for GitHub operations
 */

import { 
  GitHubRepository,
  GitHubIssue,
  GitHubPullRequest,
  GitHubCommit,
  GitHubUser,
  GitHubRelease,
  GitHubWebhook
} from '../types/github-types';

export interface GitHubSkillResult {
  success: boolean;
  data?: any;
  error?: string;
  action: string;
  platform: 'github';
}

export class GitHubSkills {
  private userId: string;
  private baseUrl: string;

  constructor(userId: string = 'default-user', baseUrl: string = '') {
    this.userId = userId;
    this.baseUrl = baseUrl;
  }

  /**
   * Execute natural language GitHub command
   */
  async executeCommand(command: string, context?: any): Promise<GitHubSkillResult> {
    const lowerCommand = command.toLowerCase().trim();

    try {
      // Repository commands
      if (lowerCommand.includes('repository') || lowerCommand.includes('repo')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listRepositories(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createRepository(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchRepositories(lowerCommand, context);
        }
      }

      // Issue commands
      if (lowerCommand.includes('issue')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listIssues(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createIssue(lowerCommand, context);
        }
        if (lowerCommand.includes('close') || lowerCommand.includes('resolve')) {
          return await this.closeIssue(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchIssues(lowerCommand, context);
        }
      }

      // Pull Request commands
      if (lowerCommand.includes('pull request') || lowerCommand.includes('pr')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listPullRequests(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createPullRequest(lowerCommand, context);
        }
        if (lowerCommand.includes('merge') || lowerCommand.includes('approve')) {
          return await this.mergePullRequest(lowerCommand, context);
        }
      }

      // Commit commands
      if (lowerCommand.includes('commit')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listCommits(lowerCommand, context);
        }
        if (lowerCommand.includes('search') || lowerCommand.includes('find')) {
          return await this.searchCommits(lowerCommand, context);
        }
      }

      // Release commands
      if (lowerCommand.includes('release')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listReleases(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createRelease(lowerCommand, context);
        }
      }

      // Organization commands
      if (lowerCommand.includes('organization') || lowerCommand.includes('org')) {
        return await this.listOrganizations(lowerCommand, context);
      }

      // User commands
      if (lowerCommand.includes('profile') || lowerCommand.includes('user')) {
        return await this.getUserProfile(lowerCommand, context);
      }

      // Webhook commands
      if (lowerCommand.includes('webhook')) {
        if (lowerCommand.includes('list') || lowerCommand.includes('show')) {
          return await this.listWebhooks(lowerCommand, context);
        }
        if (lowerCommand.includes('create')) {
          return await this.createWebhook(lowerCommand, context);
        }
      }

      // Default: Search across GitHub
      return await this.searchGitHub(lowerCommand, context);

    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
        action: 'execute_command',
        platform: 'github'
      };
    }
  }

  /**
   * List repositories
   */
  private async listRepositories(command: string, context?: any): Promise<GitHubSkillResult> {
    try {
      const response = await fetch(`${this.baseUrl}/api/integrations/github/repositories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          type: 'all',
          limit: this.extractLimit(command) || 50,
          sort: this.extractSort(command),
          include_forks: command.includes('fork'),
          include_archived: command.includes('archived')
        })
      });

      const data = await response.json();

      if (data.ok) {
        const repos = data.repositories;
        const summary = this.generateRepositorySummary(repos);
        
        return {
          success: true,
          data: {
            repositories: repos,
            summary,
            total: data.total_count
          },
          action: 'list_repositories',
          platform: 'github'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list repositories',
        action: 'list_repositories',
        platform: 'github'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_repositories',
        platform: 'github'
      };
    }
  }

  /**
   * Create repository
   */
  private async createRepository(command: string, context?: any): Promise<GitHubSkillResult> {
    try {
      const repoInfo = this.extractRepositoryInfo(command);
      
      if (!repoInfo.name) {
        return {
          success: false,
          error: 'Repository name is required. Example: "create repository my-repo"',
          action: 'create_repository',
          platform: 'github'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/github/repositories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: repoInfo
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            repository: data.repository,
            url: data.repository.html_url,
            message: `Repository ${repoInfo.name} created successfully`
          },
          action: 'create_repository',
          platform: 'github'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create repository',
        action: 'create_repository',
        platform: 'github'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_repository',
        platform: 'github'
      };
    }
  }

  /**
   * Search repositories
   */
  private async searchRepositories(command: string, context?: any): Promise<GitHubSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search repositories python"',
          action: 'search_repositories',
          platform: 'github'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/github/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'repositories',
          limit: this.extractLimit(command) || 20,
          sort: 'stars',
          order: 'desc'
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            repositories: data.repositories,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'search_repositories',
          platform: 'github'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search repositories',
        action: 'search_repositories',
        platform: 'github'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'search_repositories',
        platform: 'github'
      };
    }
  }

  /**
   * List issues
   */
  private async listIssues(command: string, context?: any): Promise<GitHubSkillResult> {
    try {
      const filters = this.extractIssueFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/github/issues`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          filters,
          limit: this.extractLimit(command) || 50,
          sort: 'updated',
          order: 'desc'
        })
      });

      const data = await response.json();

      if (data.ok) {
        const issues = data.issues;
        const summary = this.generateIssueSummary(issues);
        
        return {
          success: true,
          data: {
            issues,
            summary,
            total: data.total_count
          },
          action: 'list_issues',
          platform: 'github'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list issues',
        action: 'list_issues',
        platform: 'github'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_issues',
        platform: 'github'
      };
    }
  }

  /**
   * Create issue
   */
  private async createIssue(command: string, context?: any): Promise<GitHubSkillResult> {
    try {
      const issueInfo = this.extractIssueInfo(command);
      
      if (!issueInfo.title) {
        return {
          success: false,
          error: 'Issue title is required. Example: "create issue Bug in login page with error when entering password"',
          action: 'create_issue',
          platform: 'github'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/github/issues`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          operation: 'create',
          data: issueInfo
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            issue: data.issue,
            url: data.issue.html_url,
            message: `Issue "${issueInfo.title}" created in ${issueInfo.repository}`
          },
          action: 'create_issue',
          platform: 'github'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to create issue',
        action: 'create_issue',
        platform: 'github'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'create_issue',
        platform: 'github'
      };
    }
  }

  /**
   * List pull requests
   */
  private async listPullRequests(command: string, context?: any): Promise<GitHubSkillResult> {
    try {
      const filters = this.extractPRFilters(command);
      
      const response = await fetch(`${this.baseUrl}/api/integrations/github/pull_requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          filters,
          limit: this.extractLimit(command) || 50,
          sort: 'updated',
          order: 'desc'
        })
      });

      const data = await response.json();

      if (data.ok) {
        const prs = data.pull_requests;
        const summary = this.generatePRSummary(prs);
        
        return {
          success: true,
          data: {
            pull_requests: prs,
            summary,
            total: data.total_count
          },
          action: 'list_pull_requests',
          platform: 'github'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to list pull requests',
        action: 'list_pull_requests',
        platform: 'github'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'list_pull_requests',
        platform: 'github'
      };
    }
  }

  /**
   * Search GitHub globally
   */
  private async searchGitHub(command: string, context?: any): Promise<GitHubSkillResult> {
    try {
      const searchQuery = this.extractSearchQuery(command);
      if (!searchQuery) {
        return {
          success: false,
          error: 'Search query is required. Example: "search python documentation"',
          action: 'search_github',
          platform: 'github'
        };
      }

      const response = await fetch(`${this.baseUrl}/api/integrations/github/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: this.userId,
          query: searchQuery,
          type: 'global',
          limit: this.extractLimit(command) || 20
        })
      });

      const data = await response.json();

      if (data.ok) {
        return {
          success: true,
          data: {
            results: data.results,
            total_count: data.total_count,
            query: searchQuery
          },
          action: 'search_github',
          platform: 'github'
        };
      }

      return {
        success: false,
        error: data.error || 'Failed to search GitHub',
        action: 'search_github',
        platform: 'github'
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Network error',
        action: 'search_github',
        platform: 'github'
      };
    }
  }

  // Helper methods for extracting information from commands
  
  private extractLimit(command: string): number | null {
    const limitMatch = command.match(/limit\s+(\d+)/i);
    return limitMatch ? parseInt(limitMatch[1]) : null;
  }

  private extractSort(command: string): string {
    if (command.includes('stars')) return 'stars';
    if (command.includes('updated')) return 'updated';
    if (command.includes('created')) return 'created';
    if (command.includes('name')) return 'name';
    return 'updated';
  }

  private extractSearchQuery(command: string): string {
    const patterns = [
      /search\s+for\s+["']([^"']+)["']/i,
      /search\s+["']([^"']+)["']/i,
      /find\s+["']([^"']+)["']/i,
      /search\s+(\w+)/i,
      /find\s+(\w+)/i
    ];

    for (const pattern of patterns) {
      const match = command.match(pattern);
      if (match && match[1]) {
        return match[1];
      }
    }

    return '';
  }

  private extractRepositoryInfo(command: string): any {
    const info: any = {};

    // Extract repository name
    const nameMatch = command.match(/(?:repo|repository)\s+["']?([^"'\s]+)["']?/i);
    if (nameMatch) {
      info.name = nameMatch[1];
    }

    // Extract description
    const descMatch = command.match(/(?:desc|description)\s+["']([^"']+)["']/i);
    if (descMatch) {
      info.description = descMatch[1];
    }

    // Extract visibility
    if (command.includes('private')) {
      info.private = true;
    } else if (command.includes('public')) {
      info.private = false;
    }

    // Extract language
    const langMatch = command.match(/(?:lang|language)\s+["']?([^"'\s]+)["']?/i);
    if (langMatch) {
      info.language = langMatch[1];
    }

    return info;
  }

  private extractIssueInfo(command: string): any {
    const info: any = {};

    // Extract title
    const titleMatch = command.match(/(?:issue|bug|ticket)\s+["']?([^"']+)["']?/i);
    if (titleMatch) {
      info.title = titleMatch[1];
    }

    // Extract repository
    const repoMatch = command.match(/in\s+["']?([^"'\s]+)["']?/i);
    if (repoMatch) {
      info.repository = repoMatch[1];
    }

    // Extract labels
    const labelMatch = command.match(/(?:label|tag)\s+["']?([^"'\s]+)["']?/i);
    if (labelMatch) {
      info.labels = [labelMatch[1]];
    }

    // Extract body (everything after "with" or description)
    const bodyMatch = command.match(/(?:with|description)\s+["']([^"']+)["']/i);
    if (bodyMatch) {
      info.body = bodyMatch[1];
    }

    return info;
  }

  private extractIssueFilters(command: string): any {
    const filters: any = {};

    if (command.includes('open')) {
      filters.state = 'open';
    } else if (command.includes('closed')) {
      filters.state = 'closed';
    }

    if (command.includes('my')) {
      filters.creator = 'me';
    }

    if (command.includes('assigned')) {
      filters.assignee = 'me';
    }

    return filters;
  }

  private extractPRFilters(command: string): any {
    const filters: any = {};

    if (command.includes('open')) {
      filters.state = 'open';
    } else if (command.includes('closed') || command.includes('merged')) {
      filters.state = 'closed';
    }

    if (command.includes('my')) {
      filters.author = 'me';
    }

    if (command.includes('review')) {
      filters.reviewer = 'me';
    }

    return filters;
  }

  private generateRepositorySummary(repos: GitHubRepository[]): string {
    const total = repos.length;
    const privateCount = repos.filter(r => r.private).length;
    const forkCount = repos.filter(r => r.fork).length;
    const languageCount = new Set(repos.map(r => r.language).filter(Boolean)).size;

    return `Found ${total} repositories: ${privateCount} private, ${forkCount} forks, ${languageCount} languages`;
  }

  private generateIssueSummary(issues: GitHubIssue[]): string {
    const total = issues.length;
    const openCount = issues.filter(i => i.state === 'open').length;
    const closedCount = issues.filter(i => i.state === 'closed').length;
    const bugCount = issues.filter(i => i.labels?.some(l => l.name?.toLowerCase().includes('bug'))).length;

    return `Found ${total} issues: ${openCount} open, ${closedCount} closed, ${bugCount} bugs`;
  }

  private generatePRSummary(prs: GitHubPullRequest[]): string {
    const total = prs.length;
    const openCount = prs.filter(pr => pr.state === 'open').length;
    const mergedCount = prs.filter(pr => pr.state === 'closed' && pr.merged).length;
    const reviewCount = prs.filter(pr => pr.status === 'review_required').length;

    return `Found ${total} pull requests: ${openCount} open, ${mergedCount} merged, ${reviewCount} need review`;
  }
}

// Export singleton instance
export const githubSkills = new GitHubSkills();

// Export types
export type { GitHubSkillResult };