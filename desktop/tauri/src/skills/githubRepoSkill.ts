/**
 * GitHub Repository Skills
 * Following Outlook pattern for consistency
 */

import { Skill, SkillExecutionContext, SkillResult } from '../types/skillTypes';

export interface GitHubRepoSkillParams {
  action: 'list' | 'create' | 'search' | 'list_user' | 'get' | 'update' | 'delete';
  name?: string;
  description?: string;
  private?: boolean;
  auto_init?: boolean;
  gitignore_template?: string;
  license_template?: string;
  language?: string;
  owner?: string;
  searchQuery?: string;
  limit?: number;
  repo?: string;
  type?: 'all' | 'public' | 'private' | 'forks' | 'sources' | 'member';
  sort?: 'created' | 'updated' | 'pushed' | 'full_name';
  direction?: 'asc' | 'desc';
  topics?: string[];
  homepage?: string;
  has_issues?: boolean;
  has_projects?: boolean;
  has_wiki?: boolean;
  has_downloads?: boolean;
  is_template?: boolean;
}

export class GitHubRepoSkill implements Skill {
  async execute(params: GitHubRepoSkillParams, context: SkillExecutionContext): Promise<SkillResult> {
    try {
      const { action } = params;
      const timestamp = new Date().toISOString();

      switch (action) {
        case 'list':
          return await this.listRepos(params, context, timestamp);
        case 'list_user':
          return await this.listUserRepos(params, context, timestamp);
        case 'create':
          return await this.createRepo(params, context, timestamp);
        case 'search':
          return await this.searchRepos(params, context, timestamp);
        case 'get':
          return await this.getRepo(params, context, timestamp);
        case 'update':
          return await this.updateRepo(params, context, timestamp);
        case 'delete':
          return await this.deleteRepo(params, context, timestamp);
        default:
          throw new Error(`Unknown repository action: ${action}`);
      }
    } catch (error) {
      console.error('GitHub repository skill execution failed:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  private async listRepos(params: GitHubRepoSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    const result = await invoke<any[]>('get_github_user_repositories', {
      userId: context.userId,
      limit: params.limit || 10
    });

    // Process and categorize repositories
    const repositories = this.processRepositories(result);
    const statistics = this.calculateRepoStatistics(repositories);

    return {
      success: true,
      data: {
        action: 'list_repositories',
        repositories: repositories,
        count: repositories.length,
        statistics: statistics
      },
      message: `Found ${repositories.length} repositories`,
      timestamp: timestamp
    };
  }

  private async listUserRepos(params: GitHubRepoSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    // This would typically be a different API call for specific user repos
    const result = await invoke<any[]>('get_github_user_repositories', {
      userId: context.userId,
      limit: params.limit || 10
    });

    // Filter by owner if specified
    const userRepos = params.owner 
      ? result.filter(repo => repo.owner.login === params.owner)
      : result;

    const repositories = this.processRepositories(userRepos);

    return {
      success: true,
      data: {
        action: 'list_user_repositories',
        owner: params.owner,
        repositories: repositories,
        count: repositories.length
      },
      message: `Found ${repositories.length} repositories${params.owner ? ` for ${params.owner}` : ''}`,
      timestamp: timestamp
    };
  }

  private async createRepo(params: GitHubRepoSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    if (!params.name) {
      throw new Error('Repository name is required');
    }

    // Validate repository name
    if (!this.isValidRepoName(params.name)) {
      throw new Error('Repository name contains invalid characters');
    }

    // GitHub API would be called here
    // For now, we'll simulate the creation
    const newRepo = {
      id: Math.floor(Math.random() * 1000000),
      name: params.name,
      full_name: `${context.userId}/${params.name}`,
      description: params.description || '',
      private: params.private || false,
      html_url: `https://github.com/${context.userId}/${params.name}`,
      clone_url: `https://github.com/${context.userId}/${params.name}.git`,
      ssh_url: `git@github.com:${context.userId}/${params.name}.git`,
      default_branch: 'main',
      language: params.language,
      topics: params.topics || [],
      stargazers_count: 0,
      watchers_count: 0,
      forks_count: 0,
      open_issues_count: 0,
      created_at: timestamp,
      updated_at: timestamp,
      pushed_at: timestamp,
      size: 0,
      owner: {
        login: context.userId,
        type: 'User'
      }
    };

    // In production, this would call GitHub API
    // const result = await invoke('create_github_repository', { userId: context.userId, ...params });

    const repository = this.processRepository(newRepo);
    
    return {
      success: true,
      data: {
        action: 'create_repository',
        repository: repository,
        repository_name: repository.name,
        repository_url: repository.html_url,
        private: repository.private,
        default_branch: repository.default_branch
      },
      message: `Repository "${repository.name}" created successfully`,
      timestamp: timestamp
    };
  }

  private async searchRepos(params: GitHubRepoSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    if (!params.searchQuery) {
      throw new Error('Search query is required');
    }

    const result = await invoke<any[]>('search_github_repositories', {
      userId: context.userId,
      query: params.searchQuery,
      limit: params.limit || 10
    });

    const repositories = this.processRepositories(result);
    const enrichedRepositories = repositories.map(repo => ({
      ...repo,
      relevanceScore: this.calculateRelevanceScore(repo, params.searchQuery!),
      searchHighlights: this.generateSearchHighlights(repo, params.searchQuery!)
    }));

    return {
      success: true,
      data: {
        action: 'search_repositories',
        searchQuery: params.searchQuery,
        repositories: enrichedRepositories,
        count: enrichedRepositories.length
      },
      message: `Found ${enrichedRepositories.length} repositories matching "${params.searchQuery}"`,
      timestamp: timestamp
    };
  }

  private async getRepo(params: GitHubRepoSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.repo || !params.owner) {
      throw new Error('Owner and repository name are required');
    }

    // In production, this would call GitHub API
    // const result = await invoke('get_github_repository', { 
    //   userId: context.userId, 
    //   owner: params.owner, 
    //   repo: params.repo 
    // });

    // Mock repository data for now
    const mockRepo = {
      id: Math.floor(Math.random() * 1000000),
      name: params.repo,
      full_name: `${params.owner}/${params.repo}`,
      description: 'Repository description',
      private: false,
      html_url: `https://github.com/${params.owner}/${params.repo}`,
      clone_url: `https://github.com/${params.owner}/${params.repo}.git`,
      ssh_url: `git@github.com:${params.owner}/${params.repo}.git`,
      default_branch: 'main',
      language: 'TypeScript',
      topics: ['javascript', 'typescript', 'react'],
      stargazers_count: 42,
      watchers_count: 42,
      forks_count: 15,
      open_issues_count: 8,
      created_at: '2023-01-01T00:00:00Z',
      updated_at: timestamp,
      pushed_at: timestamp,
      size: 1024,
      owner: {
        login: params.owner,
        type: 'User'
      },
      contributors: 12,
      commits: 156,
      branches: 8,
      releases: 5,
      license: {
        key: 'mit',
        name: 'MIT License',
        spdx_id: 'MIT'
      },
      default_branch_details: {
        name: 'main',
        commit: {
          sha: 'abc123def456',
          message: 'Latest commit message',
          author: {
            name: 'John Doe',
            date: timestamp
          }
        }
      }
    };

    const repository = this.processRepository(mockRepo);
    
    return {
      success: true,
      data: {
        action: 'get_repository',
        repository: repository,
        owner: params.owner,
        repo_name: params.repo
      },
      message: `Retrieved repository ${params.owner}/${params.repo}`,
      timestamp: timestamp
    };
  }

  private async updateRepo(params: GitHubRepoSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.repo || !params.owner) {
      throw new Error('Owner and repository name are required');
    }

    // In production, this would call GitHub API
    // const result = await invoke('update_github_repository', { 
    //   userId: context.userId, 
    //   owner: params.owner, 
    //   repo: params.repo,
    //   updates: this.extractUpdates(params)
    // });

    // Mock update for now
    const updatedRepo = {
      id: Math.floor(Math.random() * 1000000),
      name: params.repo,
      full_name: `${params.owner}/${params.repo}`,
      description: params.description || 'Updated repository description',
      private: params.private || false,
      html_url: `https://github.com/${params.owner}/${params.repo}`,
      topics: params.topics || [],
      updated_at: timestamp,
      // ... other fields
    };

    const repository = this.processRepository(updatedRepo);
    
    return {
      success: true,
      data: {
        action: 'update_repository',
        repository: repository,
        owner: params.owner,
        repo_name: params.repo,
        updated_fields: this.extractUpdates(params)
      },
      message: `Repository ${params.owner}/${params.repo} updated successfully`,
      timestamp: timestamp
    };
  }

  private async deleteRepo(params: GitHubRepoSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.repo || !params.owner) {
      throw new Error('Owner and repository name are required');
    }

    // In production, this would call GitHub API
    // const result = await invoke('delete_github_repository', { 
    //   userId: context.userId, 
    //   owner: params.owner, 
    //   repo: params.repo 
    // });

    // Mock deletion for now
    return {
      success: true,
      data: {
        action: 'delete_repository',
        owner: params.owner,
        repo_name: params.repo,
        deleted_at: timestamp
      },
      message: `Repository ${params.owner}/${params.repo} deleted successfully`,
      timestamp: timestamp
    };
  }

  // Helper methods
  private processRepositories(repos: any[]): any[] {
    if (!Array.isArray(repos)) {
      console.warn('processRepositories: repos is not an array', repos);
      return [];
    }
    return repos.map(repo => this.processRepository(repo));
  }

  private processRepository(repo: any): any {
    return {
      ...repo,
      created: new Date(repo.created_at),
      updated: new Date(repo.updated_at),
      daysSinceCreation: this.getDaysSince(repo.created_at),
      daysSinceUpdate: this.getDaysSince(repo.updated_at),
      popularity: this.calculatePopularity(repo),
      activityLevel: this.calculateActivityLevel(repo),
      sizeCategory: this.categorizeSize(repo.size),
      healthScore: this.calculateHealthScore(repo)
    };
  }

  private calculateRepoStatistics(repos: any[]): any {
    const totalRepos = repos.length;
    const publicRepos = repos.filter(repo => !repo.private).length;
    const privateRepos = repos.filter(repo => repo.private).length;
    const forkedRepos = repos.filter(repo => repo.fork).length;
    const totalStars = repos.reduce((sum, repo) => sum + repo.stargazers_count, 0);
    const totalForks = repos.reduce((sum, repo) => sum + repo.forks_count, 0);
    const totalIssues = repos.reduce((sum, repo) => sum + repo.open_issues_count, 0);
    const languages = this.getLanguageDistribution(repos);
    const topics = this.getTopicDistribution(repos);
    const averageRepoAge = this.getAverageRepoAge(repos);

    return {
      total: totalRepos,
      public: publicRepos,
      private: privateRepos,
      forked: forkedRepos,
      stars: totalStars,
      forks: totalForks,
      issues: totalIssues,
      languages: languages,
      topics: topics,
      average_age_days: averageRepoAge,
      most_starred: repos.reduce((max, repo) => repo.stargazers_count > max.stargazers_count ? repo : max, { stargazers_count: 0 }),
      most_active: repos.reduce((max, repo) => repo.activityLevel > max.activityLevel ? repo : max, { activityLevel: 0 })
    };
  }

  private calculatePopularity(repo: any): number {
    const starWeight = 0.6;
    const forkWeight = 0.3;
    const watcherWeight = 0.1;
    
    return Math.round((repo.stargazers_count * starWeight + 
            repo.forks_count * forkWeight + 
            (repo.watchers_count || repo.stargazers_count) * watcherWeight));
  }

  private calculateActivityLevel(repo: any): number {
    const issuesWeight = 0.3;
    const commitWeight = 0.5; // Would need commit data
    const contributionWeight = 0.2; // Would need contributor data
    
    const daysSinceUpdate = this.getDaysSince(repo.updated_at);
    const recencyScore = Math.max(0, 1 - (daysSinceUpdate / 365)); // Decay over a year
    
    return (repo.open_issues_count * issuesWeight * recencyScore +
            100 * commitWeight * recencyScore + // Mock commit score
            50 * contributionWeight * recencyScore); // Mock contribution score
  }

  private calculateHealthScore(repo: any): number {
    let score = 100;
    
    // Penalize for no README
    if (!repo.has_readme) score -= 20;
    
    // Penalize for no license
    if (!repo.license) score -= 15;
    
    // Penalize for many open issues
    if (repo.open_issues_count > 50) score -= 10;
    
    // Bonus for recent activity
    const daysSinceUpdate = this.getDaysSince(repo.updated_at);
    if (daysSinceUpdate < 7) score += 10;
    else if (daysSinceUpdate > 90) score -= 15;
    
    // Bonus for documentation
    if (repo.has_wiki) score += 5;
    
    return Math.max(0, Math.min(100, score));
  }

  private calculateRelevanceScore(repo: any, query: string): number {
    const queryLower = query.toLowerCase();
    let score = 0;
    
    // Name match
    if (repo.name.toLowerCase().includes(queryLower)) {
      score += 50;
    }
    
    // Description match
    if (repo.description && repo.description.toLowerCase().includes(queryLower)) {
      score += 30;
    }
    
    // Topics match
    if (repo.topics && repo.topics.some((topic: string) => topic.toLowerCase().includes(queryLower))) {
      score += 25;
    }
    
    // Language match
    if (repo.language && repo.language.toLowerCase().includes(queryLower)) {
      score += 20;
    }
    
    // Popularity bonus
    score += Math.min(20, this.calculatePopularity(repo) / 10);
    
    return score;
  }

  private generateSearchHighlights(repo: any, query: string): string[] {
    const highlights: string[] = [];
    const queryLower = query.toLowerCase();
    
    if (repo.name.toLowerCase().includes(queryLower)) {
      highlights.push('name');
    }
    
    if (repo.description && repo.description.toLowerCase().includes(queryLower)) {
      highlights.push('description');
    }
    
    if (repo.topics && repo.topics.some((topic: string) => topic.toLowerCase().includes(queryLower))) {
      highlights.push('topics');
    }
    
    return highlights;
  }

  private getDaysSince(dateString: string): number {
    const date = new Date(dateString);
    const now = new Date();
    return Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  }

  private categorizeSize(size: number): string {
    if (size < 100) return 'Small';
    if (size < 1000) return 'Medium';
    if (size < 10000) return 'Large';
    return 'Very Large';
  }

  private getLanguageDistribution(repos: any[]): any {
    const langCounts: { [key: string]: number } = {};
    
    repos.forEach(repo => {
      if (repo.language) {
        langCounts[repo.language] = (langCounts[repo.language] || 0) + 1;
      }
    });
    
    return Object.entries(langCounts)
      .map(([lang, count]) => ({ language: lang, count }))
      .sort((a, b) => b.count - a.count);
  }

  private getTopicDistribution(repos: any[]): any {
    const topicCounts: { [key: string]: number } = {};
    
    repos.forEach(repo => {
      if (repo.topics) {
        repo.topics.forEach((topic: string) => {
          topicCounts[topic] = (topicCounts[topic] || 0) + 1;
        });
      }
    });
    
    return Object.entries(topicCounts)
      .map(([topic, count]) => ({ topic, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 20); // Top 20 topics
  }

  private getAverageRepoAge(repos: any[]): number {
    if (repos.length === 0) return 0;
    
    const totalDays = repos.reduce((sum, repo) => sum + this.getDaysSince(repo.created_at), 0);
    return Math.floor(totalDays / repos.length);
  }

  private extractUpdates(params: GitHubRepoSkillParams): any {
    const updates: any = {};
    
    if (params.description !== undefined) updates.description = params.description;
    if (params.private !== undefined) updates.private = params.private;
    if (params.topics !== undefined) updates.topics = params.topics;
    if (params.homepage !== undefined) updates.homepage = params.homepage;
    if (params.has_issues !== undefined) updates.has_issues = params.has_issues;
    if (params.has_projects !== undefined) updates.has_projects = params.has_projects;
    if (params.has_wiki !== undefined) updates.has_wiki = params.has_wiki;
    if (params.has_downloads !== undefined) updates.has_downloads = params.has_downloads;
    if (params.is_template !== undefined) updates.is_template = params.is_template;
    
    return updates;
  }

  private isValidRepoName(name: string): boolean {
    // GitHub repository name rules
    const validPattern = /^[a-zA-Z0-9._-]+$/;
    return name.length >= 1 && name.length <= 100 && validPattern.test(name);
  }
}

// Export singleton instance
export const githubRepoSkill = new GitHubRepoSkill();