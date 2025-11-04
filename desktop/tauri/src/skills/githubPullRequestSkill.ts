/**
 * GitHub Pull Request Skills
 * Following Outlook pattern for consistency
 */

import { Skill, SkillExecutionContext, SkillResult } from '../types/skillTypes';

export interface GitHubPullRequestSkillParams {
  action: 'list' | 'create' | 'search' | 'get' | 'update' | 'merge' | 'close' | 'reopen' | 'request_review' | 'approve' | 'request_changes';
  owner: string;
  repo: string;
  title?: string;
  body?: string;
  description?: string;
  head?: string;
  base?: string;
  draft?: boolean;
  pr_number?: number;
  state?: 'open' | 'closed' | 'all' | 'merged';
  searchQuery?: string;
  sort?: 'created' | 'updated' | 'popularity' | 'long-running';
  direction?: 'asc' | 'desc';
  limit?: number;
  assignees?: string[] | string;
  reviewers?: string[] | string;
  milestone?: number;
  labels?: string[] | string;
  maintainer_can_modify?: boolean;
  merge_method?: 'merge' | 'squash' | 'rebase';
  merge_commit_message?: string;
  request_reviewers?: string[] | string;
  team_reviewers?: string[] | string;
}

export class GitHubPullRequestSkill implements Skill {
  async execute(params: GitHubPullRequestSkillParams, context: SkillExecutionContext): Promise<SkillResult> {
    try {
      const { action } = params;
      const timestamp = new Date().toISOString();

      switch (action) {
        case 'list':
          return await this.listPullRequests(params, context, timestamp);
        case 'create':
          return await this.createPullRequest(params, context, timestamp);
        case 'search':
          return await this.searchPullRequests(params, context, timestamp);
        case 'get':
          return await this.getPullRequest(params, context, timestamp);
        case 'update':
          return await this.updatePullRequest(params, context, timestamp);
        case 'merge':
          return await this.mergePullRequest(params, context, timestamp);
        case 'close':
          return await this.closePullRequest(params, context, timestamp);
        case 'reopen':
          return await this.reopenPullRequest(params, context, timestamp);
        case 'request_review':
          return await this.requestReview(params, context, timestamp);
        case 'approve':
          return await this.approvePullRequest(params, context, timestamp);
        case 'request_changes':
          return await this.requestChanges(params, context, timestamp);
        default:
          throw new Error(`Unknown pull request action: ${action}`);
      }
    } catch (error) {
      console.error('GitHub pull request skill execution failed:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  private async listPullRequests(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    if (!params.owner || !params.repo) {
      throw new Error('Owner and repository are required');
    }

    const result = await invoke<any[]>('get_github_pull_requests', {
      userId: context.userId,
      owner: params.owner,
      repo: params.repo,
      state: params.state || 'open',
      limit: params.limit || 10
    });

    const pullRequests = this.processPullRequests(result);
    const statistics = this.calculatePullRequestStatistics(pullRequests);

    return {
      success: true,
      data: {
        action: 'list_pull_requests',
        pullRequests: pullRequests,
        count: pullRequests.length,
        repository: `${params.owner}/${params.repo}`,
        state: params.state || 'open',
        statistics: statistics
      },
      message: `Found ${pullRequests.length} pull requests in ${params.owner}/${params.repo}`,
      timestamp: timestamp
    };
  }

  private async createPullRequest(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    if (!params.owner || !params.repo || !params.title || !params.head || !params.base) {
      throw new Error('Owner, repository, title, head branch, and base branch are required');
    }

    // Validate branch names
    if (!this.isValidBranchName(params.head) || !this.isValidBranchName(params.base)) {
      throw new Error('Invalid branch names');
    }

    const result = await invoke<any>('create_github_pull_request', {
      userId: context.userId,
      owner: params.owner,
      repo: params.repo,
      title: params.title,
      body: params.body || params.description || '',
      head: params.head,
      base: params.base,
      draft: params.draft || false,
      maintainer_can_modify: params.maintainer_can_modify || false
    });

    const pullRequest = this.processPullRequest(result);
    
    return {
      success: true,
      data: {
        action: 'create_pull_request',
        pullRequest: pullRequest,
        pr_number: pullRequest.number,
        pr_title: pullRequest.title,
        pr_url: pullRequest.html_url,
        repository: `${params.owner}/${params.repo}`,
        head_branch: params.head,
        base_branch: params.base,
        draft: params.draft || false
      },
      message: `Pull request #${pullRequest.number} created successfully`,
      timestamp: timestamp
    };
  }

  private async searchPullRequests(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.searchQuery) {
      throw new Error('Search query is required');
    }

    // Mock search - in production, this would use GitHub search API
    const mockPullRequests = [
      {
        id: 2001,
        number: 15,
        title: "Add GitHub integration feature",
        body: "Implement GitHub integration with comprehensive API access",
        state: "open",
        locked: false,
        user: {
          login: "contributor1",
          name: "Contributor One",
          avatar_url: "https://github.com/contributor1.png",
          type: "User"
        },
        assignees: [
          {
            login: "developer1",
            name: "Developer One",
            avatar_url: "https://github.com/developer1.png",
            type: "User"
          }
        ],
        requested_reviewers: [
          {
            login: "reviewer1",
            name: "Reviewer One",
            avatar_url: "https://github.com/reviewer1.png",
            type: "User"
          }
        ],
        labels: [
          {
            id: 234,
            name: "feature",
            color: "0075ca"
          },
          {
            id: 567,
            name: "wip",
            color: "fbca04"
          }
        ],
        comments: 12,
        review_comments: 8,
        commits: 5,
        additions: 1250,
        deletions: 85,
        changed_files: 12,
        created_at: "2025-11-01T08:00:00Z",
        updated_at: "2025-11-02T16:20:00Z",
        mergeable: true,
        html_url: "https://github.com/atomcompany/atom-desktop/pull/15",
        head: {
          label: "contributor1:feature/github",
          ref_field: "feature/github",
          sha: "abc123def456",
          user: { login: "contributor1", name: "Contributor One" },
          repo: {
            full_name: "contributor1/atom-desktop",
            name: "atom-desktop",
            owner: { login: "contributor1" }
          }
        },
        base: {
          label: "atomcompany:main",
          ref_field: "main",
          sha: "xyz789uvw012",
          user: { login: "atomcompany", name: "ATOM Company" },
          repo: {
            full_name: "atomcompany/atom-desktop",
            name: "atom-desktop",
            owner: { login: "atomcompany" }
          }
        },
        repository: {
          full_name: "atomcompany/atom-desktop",
          private: false
        }
      }
    ];

    // Filter by search query (mock)
    const filteredPRs = mockPullRequests.filter(pr => 
      pr.title.toLowerCase().includes(params.searchQuery!.toLowerCase()) ||
      (pr.body && pr.body.toLowerCase().includes(params.searchQuery!.toLowerCase()))
    );

    const pullRequests = this.processPullRequests(filteredPRs);
    const searchResults = pullRequests.map(pr => ({
      ...pr,
      relevanceScore: this.calculatePRRelevance(pr, params.searchQuery!),
      searchHighlights: this.generatePRSearchHighlights(pr, params.searchQuery!)
    }));

    return {
      success: true,
      data: {
        action: 'search_pull_requests',
        searchQuery: params.searchQuery,
        pullRequests: searchResults,
        count: searchResults.length
      },
      message: `Found ${searchResults.length} pull requests matching "${params.searchQuery}"`,
      timestamp: timestamp
    };
  }

  private async getPullRequest(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.pr_number) {
      throw new Error('Owner, repository, and pull request number are required');
    }

    // Mock detailed PR data
    const mockPR = {
      id: 2001,
      number: params.pr_number,
      title: "Add GitHub integration feature",
      body: "Implement GitHub integration with comprehensive API access",
      state: "open",
      locked: false,
      draft: false,
      user: {
        login: "contributor1",
        name: "Contributor One",
        avatar_url: "https://github.com/contributor1.png",
        type: "User"
      },
      assignees: [
        {
          login: "developer1",
          name: "Developer One",
          avatar_url: "https://github.com/developer1.png",
          type: "User"
        }
      ],
      requested_reviewers: [
        {
          login: "reviewer1",
          name: "Reviewer One",
          avatar_url: "https://github.com/reviewer1.png",
          type: "User"
        }
      ],
      labels: [
        {
          id: 234,
          name: "feature",
          color: "0075ca",
          description: "New functionality"
        },
        {
          id: 567,
          name: "wip",
          color: "fbca04",
          description: "Work in progress"
        }
      ],
      milestone: {
        id: 1,
        number: 1,
        title: "Q4 2025 Release",
        state: "open",
        open_issues: 5,
        closed_issues: 10,
        created_at: "2025-10-01T00:00:00Z",
        updated_at: "2025-11-01T12:00:00Z",
        due_on: "2025-12-31T23:59:59Z",
        closed_at: null,
        html_url: "https://github.com/atomcompany/atom-desktop/milestone/1"
      },
      comments: 12,
      review_comments: 8,
      commits: 5,
      additions: 1250,
      deletions: 85,
      changed_files: 12,
      created_at: "2025-11-01T08:00:00Z",
      updated_at: "2025-11-02T16:20:00Z",
      closed_at: null,
      merged_at: null,
      mergeable: true,
      mergeable_state: "clean",
      merged: false,
      merge_conflict: false,
      html_url: `https://github.com/${params.owner}/${params.repo}/pull/${params.pr_number}`,
      diff_url: `https://github.com/${params.owner}/${params.repo}/pull/${params.pr_number}.diff`,
      patch_url: `https://github.com/${params.owner}/${params.repo}/pull/${params.pr_number}.patch`,
      commits_url: `https://api.github.com/repos/${params.owner}/${params.repo}/pulls/${params.pr_number}/commits`,
      review_comments_url: `https://api.github.com/repos/${params.owner}/${params.repo}/pulls/${params.pr_number}/comments`,
      repository_url: `https://api.github.com/repos/${params.owner}/${params.repo}`,
      status: "success",
      sha: "abc123def456",
      base: {
        label: `${params.owner}:main`,
        ref_field: "main",
        sha: "xyz789uvw012",
        user: { login: params.owner, name: "Repo Owner" },
        repo: {
          full_name: `${params.owner}/${params.repo}`,
          name: params.repo,
          owner: { login: params.owner }
        }
      },
      head: {
        label: "contributor1:feature/github",
        ref_field: "feature/github",
        sha: "abc123def456",
        user: { login: "contributor1", name: "Contributor One" },
        repo: {
          full_name: "contributor1/atom-desktop",
          name: "atom-desktop",
          owner: { login: "contributor1" }
        }
      },
      maintainers_can_modify: false,
      merge_commit_message: null
    };

    const pullRequest = this.processPullRequest(mockPR);
    
    return {
      success: true,
      data: {
        action: 'get_pull_request',
        pullRequest: pullRequest,
        repository: `${params.owner}/${params.repo}`
      },
      message: `Retrieved pull request #${params.pr_number}`,
      timestamp: timestamp
    };
  }

  private async updatePullRequest(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.pr_number) {
      throw new Error('Owner, repository, and pull request number are required');
    }

    const updates = this.extractPRUpdates(params);
    
    // Mock update
    const updatedPR = {
      id: 2001,
      number: params.pr_number,
      title: params.title || "Add GitHub integration feature",
      body: params.body || params.description || "Implement GitHub integration with comprehensive API access",
      state: params.state || 'open',
      updated_at: timestamp,
      // ... other fields with updates applied
    };

    const pullRequest = this.processPullRequest(updatedPR);
    
    return {
      success: true,
      data: {
        action: 'update_pull_request',
        pullRequest: pullRequest,
        repository: `${params.owner}/${params.repo}`,
        pr_number: params.pr_number,
        updated_fields: updates
      },
      message: `Pull request #${params.pr_number} updated successfully`,
      timestamp: timestamp
    };
  }

  private async mergePullRequest(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.pr_number) {
      throw new Error('Owner, repository, and pull request number are required');
    }

    // Mock merge
    const mergedPR = {
      id: 2001,
      number: params.pr_number,
      state: "closed",
      merged: true,
      merged_at: timestamp,
      merged_by: { login: context.userId, name: "Current User" },
      merge_commit_sha: "merged123abc456",
      merge_method: params.merge_method || "merge"
    };

    const pullRequest = this.processPullRequest(mergedPR);
    
    return {
      success: true,
      data: {
        action: 'merge_pull_request',
        pullRequest: pullRequest,
        repository: `${params.owner}/${params.repo}`,
        pr_number: params.pr_number,
        merged_at: timestamp,
        merge_method: params.merge_method || 'merge'
      },
      message: `Pull request #${params.pr_number} merged successfully`,
      timestamp: timestamp
    };
  }

  private async requestReview(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.pr_number || !params.request_reviewers) {
      throw new Error('Owner, repository, PR number, and reviewers are required');
    }

    const reviewers = Array.isArray(params.request_reviewers) 
      ? params.request_reviewers 
      : [params.request_reviewers];

    // Mock review request
    const updatedPR = {
      id: 2001,
      number: params.pr_number,
      requested_reviewers: reviewers.map(username => ({
        login: username,
        name: username,
        type: "User"
      })),
      updated_at: timestamp
    };

    const pullRequest = this.processPullRequest(updatedPR);
    
    return {
      success: true,
      data: {
        action: 'request_review',
        pullRequest: pullRequest,
        repository: `${params.owner}/${params.repo}`,
        pr_number: params.pr_number,
        requested_reviewers: reviewers,
        requested_at: timestamp
      },
      message: `Review requested from ${reviewers.join(', ')} for PR #${params.pr_number}`,
      timestamp: timestamp
    };
  }

  // Helper methods
  private processPullRequests(pullRequests: any[]): any[] {
    if (!Array.isArray(pullRequests)) {
      console.warn('processPullRequests: pullRequests is not an array', pullRequests);
      return [];
    }
    return pullRequests.map(pr => this.processPullRequest(pr));
  }

  private processPullRequest(pr: any): any {
    return {
      ...pr,
      created: new Date(pr.created_at),
      updated: new Date(pr.updated_at),
      closed_at: pr.closed_at ? new Date(pr.closed_at) : null,
      merged_at: pr.merged_at ? new Date(pr.merged_at) : null,
      daysSinceCreation: this.getDaysSince(pr.created_at),
      daysSinceUpdate: this.getDaysSince(pr.updated_at),
      daysSinceClosed: pr.closed_at ? this.getDaysSince(pr.closed_at) : null,
      daysSinceMerged: pr.merged_at ? this.getDaysSince(pr.merged_at) : null,
      reviewTime: this.calculateReviewTime(pr),
      mergeTime: this.calculateMergeTime(pr),
      complexity: this.calculatePRComplexity(pr),
      riskLevel: this.calculatePRRiskLevel(pr),
      healthScore: this.calculatePRHealth(pr),
      engagement: this.calculatePREngagement(pr),
      status: this.determinePRStatus(pr)
    };
  }

  private calculatePullRequestStatistics(pullRequests: any[]): any {
    const totalPRs = pullRequests.length;
    const openPRs = pullRequests.filter(pr => pr.state === 'open').length;
    const closedPRs = pullRequests.filter(pr => pr.state === 'closed').length;
    const mergedPRs = pullRequests.filter(pr => pr.merged).length;
    const draftPRs = pullRequests.filter(pr => pr.draft).length;
    const totalClosedPRs = closedPRs;
    
    const totalCommits = pullRequests.reduce((sum, pr) => sum + pr.commits, 0);
    const totalAdditions = pullRequests.reduce((sum, pr) => sum + pr.additions, 0);
    const totalDeletions = pullRequests.reduce((sum, pr) => sum + pr.deletions, 0);
    const totalChangedFiles = pullRequests.reduce((sum, pr) => sum + pr.changed_files, 0);
    const totalComments = pullRequests.reduce((sum, pr) => sum + pr.comments, 0);
    
    const averageCommits = totalPRs > 0 ? totalCommits / totalPRs : 0;
    const averageAdditions = totalPRs > 0 ? totalAdditions / totalPRs : 0;
    const averageDeletions = totalPRs > 0 ? totalDeletions / totalPRs : 0;
    const averageChangedFiles = totalPRs > 0 ? totalChangedFiles / totalPRs : 0;
    const averageComments = totalPRs > 0 ? totalComments / totalPRs : 0;
    
    const authors = this.getPRAuthors(pullRequests);
    const reviewers = this.getPRReviewers(pullRequests);
    const labels = this.getPRLabels(pullRequests);
    const averageReviewTime = this.getAverageReviewTime(pullRequests);
    const averageMergeTime = this.getAverageMergeTime(pullRequests);
    const mergeRate = totalClosedPRs > 0 ? ((mergedPRs / totalClosedPRs) * 100).toFixed(1) : '0';

    return {
      total: totalPRs,
      open: openPRs,
      closed: closedPRs,
      merged: mergedPRs,
      draft: draftPRs,
      merge_rate: mergeRate,
      commits: {
        total: totalCommits,
        average: averageCommits.toFixed(1)
      },
      changes: {
        additions: totalAdditions,
        deletions: totalDeletions,
        changed_files: totalChangedFiles,
        average_additions: averageAdditions.toFixed(1),
        average_deletions: averageDeletions.toFixed(1),
        average_files: averageChangedFiles.toFixed(1)
      },
      engagement: {
        comments: totalComments,
        average_comments: averageComments.toFixed(1)
      },
      timing: {
        average_review_time_hours: averageReviewTime,
        average_merge_time_hours: averageMergeTime
      },
      contributors: {
        authors: authors,
        reviewers: reviewers
      },
      labels: labels
    };
  }

  private calculatePRRelevance(pr: any, query: string): number {
    const queryLower = query.toLowerCase();
    let score = 0;
    
    if (pr.title.toLowerCase().includes(queryLower)) {
      score += 50;
    }
    
    if (pr.body && pr.body.toLowerCase().includes(queryLower)) {
      score += 30;
    }
    
    if (pr.labels && pr.labels.some((label: any) => label.name.toLowerCase().includes(queryLower))) {
      score += 25;
    }
    
    if (pr.user && pr.user.login.toLowerCase().includes(queryLower)) {
      score += 15;
    }
    
    // Recent activity bonus
    const daysSinceUpdate = this.getDaysSince(pr.updated_at);
    if (daysSinceUpdate < 7) score += 10;
    
    return score;
  }

  private generatePRSearchHighlights(pr: any, query: string): string[] {
    const queryLower = query.toLowerCase();
    const highlights: string[] = [];
    
    if (pr.title.toLowerCase().includes(queryLower)) {
      highlights.push('title');
    }
    
    if (pr.body && pr.body.toLowerCase().includes(queryLower)) {
      highlights.push('body');
    }
    
    if (pr.labels && pr.labels.some((label: any) => label.name.toLowerCase().includes(queryLower))) {
      highlights.push('labels');
    }
    
    if (pr.user && pr.user.login.toLowerCase().includes(queryLower)) {
      highlights.push('author');
    }
    
    return highlights;
  }

  private calculateReviewTime(pr: any): number | null {
    // Mock calculation - in production, calculate from actual review timestamps
    if (pr.state === 'closed' && pr.merged_at) {
      const created = new Date(pr.created_at);
      const reviewed = new Date(pr.merged_at);
      return (reviewed.getTime() - created.getTime()) / (1000 * 60 * 60); // hours
    }
    return null;
  }

  private calculateMergeTime(pr: any): number | null {
    // Mock calculation - in production, calculate from actual timestamps
    if (pr.merged_at) {
      const created = new Date(pr.created_at);
      const merged = new Date(pr.merged_at);
      return (merged.getTime() - created.getTime()) / (1000 * 60 * 60); // hours
    }
    return null;
  }

  private calculatePRComplexity(pr: any): string {
    let complexityScore = 0;
    
    // File changes contribution
    complexityScore += Math.min(50, pr.changed_files * 2);
    
    // Line changes contribution
    complexityScore += Math.min(30, (pr.additions + pr.deletions) / 50);
    
    // Commit contribution
    complexityScore += Math.min(20, pr.commits * 4);
    
    // Comment contribution (indicates complexity)
    complexityScore += Math.min(15, pr.comments);
    
    if (complexityScore > 80) return 'high';
    if (complexityScore > 40) return 'medium';
    return 'low';
  }

  private calculatePRRiskLevel(pr: any): string {
    let riskScore = 0;
    
    // Large changes increase risk
    if (pr.changed_files > 50) riskScore += 30;
    if ((pr.additions + pr.deletions) > 1000) riskScore += 20;
    
    // Many commits indicate complex changes
    if (pr.commits > 20) riskScore += 15;
    
    // Old PRs might have conflicts
    const daysOld = this.getDaysSince(pr.created_at);
    if (daysOld > 30) riskScore += 10;
    if (daysOld > 60) riskScore += 15;
    
    // No reviewers increases risk
    if (!pr.requested_reviewers || pr.requested_reviewers.length === 0) riskScore += 25;
    
    // Draft status reduces risk
    if (pr.draft) riskScore = Math.max(0, riskScore - 20);
    
    if (riskScore > 60) return 'high';
    if (riskScore > 30) return 'medium';
    return 'low';
  }

  private calculatePRHealth(pr: any): number {
    let score = 100;
    
    // Penalize for no description
    if (!pr.body || pr.body.length < 20) score -= 20;
    
    // Penalize for no reviewers
    if (!pr.requested_reviewers || pr.requested_reviewers.length === 0) score -= 15;
    
    // Penalize for failing checks
    if (pr.status !== 'success') score -= 25;
    
    // Penalize for merge conflicts
    if (pr.merge_conflict) score -= 30;
    
    // Bonus for good description
    if (pr.body && pr.body.length > 100) score += 10;
    
    // Bonus for reviewers
    if (pr.requested_reviewers && pr.requested_reviewers.length > 0) score += 15;
    
    // Bonus for passing checks
    if (pr.status === 'success') score += 20;
    
    // Bonus for recent updates
    const daysSinceUpdate = this.getDaysSince(pr.updated_at);
    if (daysSinceUpdate < 7) score += 10;
    
    return Math.max(0, Math.min(100, score));
  }

  private calculatePREngagement(pr: any): any {
    return {
      comments: pr.comments,
      review_comments: pr.review_comments || 0,
      participants: 1 + (pr.requested_reviewers ? pr.requested_reviewers.length : 0),
      engagement_score: Math.min(100, (pr.comments + (pr.review_comments || 0)) * 5)
    };
  }

  private determinePRStatus(pr: any): string {
    if (pr.draft) return 'draft';
    if (pr.merged) return 'merged';
    if (pr.state === 'closed') return 'closed';
    if (pr.merge_conflict) return 'conflict';
    if (!pr.requested_reviewers || pr.requested_reviewers.length === 0) return 'waiting_for_reviewer';
    if (pr.status !== 'success') return 'checks_failing';
    return 'ready_to_merge';
  }

  private getDaysSince(dateString: string): number {
    const date = new Date(dateString);
    const now = new Date();
    return Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  }

  private getPRAuthors(pullRequests: any[]): any {
    const authors: { [key: string]: number } = {};
    
    pullRequests.forEach(pr => {
      if (pr.user) {
        authors[pr.user.login] = (authors[pr.user.login] || 0) + 1;
      }
    });
    
    return Object.entries(authors)
      .map(([author, count]) => ({ author, count }))
      .sort((a, b) => b.count - a.count);
  }

  private getPRReviewers(pullRequests: any[]): any {
    const reviewers: { [key: string]: number } = {};
    
    pullRequests.forEach(pr => {
      if (pr.requested_reviewers) {
        pr.requested_reviewers.forEach((reviewer: any) => {
          reviewers[reviewer.login] = (reviewers[reviewer.login] || 0) + 1;
        });
      }
    });
    
    return Object.entries(reviewers)
      .map(([reviewer, count]) => ({ reviewer, count }))
      .sort((a, b) => b.count - a.count);
  }

  private getPRLabels(pullRequests: any[]): any {
    const labels: { [key: string]: number } = {};
    
    pullRequests.forEach(pr => {
      if (pr.labels) {
        pr.labels.forEach((label: any) => {
          labels[label.name] = (labels[label.name] || 0) + 1;
        });
      }
    });
    
    return Object.entries(labels)
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 20);
  }

  private getAverageReviewTime(pullRequests: any[]): number {
    const reviewedPRs = pullRequests.filter(pr => pr.reviewTime !== null);
    
    if (reviewedPRs.length === 0) return 0;
    
    const totalReviewTime = reviewedPRs.reduce((sum, pr) => sum + pr.reviewTime!, 0);
    return Math.floor(totalReviewTime / reviewedPRs.length);
  }

  private getAverageMergeTime(pullRequests: any[]): number {
    const mergedPRs = pullRequests.filter(pr => pr.mergeTime !== null);
    
    if (mergedPRs.length === 0) return 0;
    
    const totalMergeTime = mergedPRs.reduce((sum, pr) => sum + pr.mergeTime!, 0);
    return Math.floor(totalMergeTime / mergedPRs.length);
  }

  private extractPRUpdates(params: GitHubPullRequestSkillParams): any {
    const updates: any = {};
    
    if (params.title !== undefined) updates.title = params.title;
    if (params.body !== undefined || params.description !== undefined) updates.body = params.body || params.description;
    if (params.state !== undefined) updates.state = params.state;
    if (params.draft !== undefined) updates.draft = params.draft;
    if (params.maintainer_can_modify !== undefined) updates.maintainer_can_modify = params.maintainer_can_modify;
    if (params.assignees !== undefined) updates.assignees = Array.isArray(params.assignees) ? params.assignees : [params.assignees];
    if (params.reviewers !== undefined) updates.reviewers = Array.isArray(params.reviewers) ? params.reviewers : [params.reviewers];
    if (params.labels !== undefined) updates.labels = Array.isArray(params.labels) ? params.labels : [params.labels];
    if (params.milestone !== undefined) updates.milestone = params.milestone;
    
    return updates;
  }

  private isValidBranchName(branch: string): boolean {
    // Basic validation for branch names (GitHub allows more characters)
    const validPattern = /^[a-zA-Z0-9._/-]+$/;
    return branch.length >= 1 && 
           branch.length <= 255 && 
           validPattern.test(branch) &&
           !branch.startsWith('-') && 
           !branch.endsWith('-') &&
           !branch.startsWith('.') &&
           !branch.endsWith('.');
  }

  private async closePullRequest(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.pr_number) {
      throw new Error('Owner, repository, and PR number are required');
    }

    // Mock close
    const closedPR = {
      id: 2001,
      number: params.pr_number,
      state: "closed",
      closed_at: timestamp,
      closed_by: { login: context.userId, name: "Current User" },
      updated_at: timestamp
    };

    const pullRequest = this.processPullRequest(closedPR);
    
    return {
      success: true,
      data: {
        action: 'close_pull_request',
        pullRequest: pullRequest,
        repository: `${params.owner}/${params.repo}`,
        pr_number: params.pr_number,
        closed_at: timestamp
      },
      message: `Pull request #${params.pr_number} closed successfully`,
      timestamp: timestamp
    };
  }

  private async reopenPullRequest(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.pr_number) {
      throw new Error('Owner, repository, and PR number are required');
    }

    // Mock reopen
    const reopenedPR = {
      id: 2001,
      number: params.pr_number,
      state: "open",
      closed_at: null,
      reopened_by: { login: context.userId, name: "Current User" },
      updated_at: timestamp
    };

    const pullRequest = this.processPullRequest(reopenedPR);
    
    return {
      success: true,
      data: {
        action: 'reopen_pull_request',
        pullRequest: pullRequest,
        repository: `${params.owner}/${params.repo}`,
        pr_number: params.pr_number,
        reopened_at: timestamp
      },
      message: `Pull request #${params.pr_number} reopened successfully`,
      timestamp: timestamp
    };
  }

  private async approvePullRequest(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.pr_number) {
      throw new Error('Owner, repository, and PR number are required');
    }

    // Mock approval
    const approvedPR = {
      id: 2001,
      number: params.pr_number,
      approved: true,
      approved_by: { login: context.userId, name: "Current User" },
      approved_at: timestamp,
      updated_at: timestamp
    };

    const pullRequest = this.processPullRequest(approvedPR);
    
    return {
      success: true,
      data: {
        action: 'approve_pull_request',
        pullRequest: pullRequest,
        repository: `${params.owner}/${params.repo}`,
        pr_number: params.pr_number,
        approved_at: timestamp
      },
      message: `Pull request #${params.pr_number} approved`,
      timestamp: timestamp
    };
  }

  private async requestChanges(params: GitHubPullRequestSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.pr_number) {
      throw new Error('Owner, repository, and PR number are required');
    }

    // Mock request changes
    const changesRequestedPR = {
      id: 2001,
      number: params.pr_number,
      changes_requested: true,
      changes_requested_by: { login: context.userId, name: "Current User" },
      changes_requested_at: timestamp,
      updated_at: timestamp
    };

    const pullRequest = this.processPullRequest(changesRequestedPR);
    
    return {
      success: true,
      data: {
        action: 'request_changes',
        pullRequest: pullRequest,
        repository: `${params.owner}/${params.repo}`,
        pr_number: params.pr_number,
        changes_requested_at: timestamp
      },
      message: `Changes requested for pull request #${params.pr_number}`,
      timestamp: timestamp
    };
  }
}

// Export singleton instance
export const githubPullRequestSkill = new GitHubPullRequestSkill();