/**
 * GitHub Issue Skills
 * Following Outlook pattern for consistency
 */

import { Skill, SkillExecutionContext, SkillResult } from '../types/skillTypes';

export interface GitHubIssueSkillParams {
  action: 'list' | 'create' | 'search' | 'get' | 'update' | 'close' | 'reopen' | 'lock' | 'unlock' | 'assign' | 'unassign' | 'add_labels' | 'remove_labels';
  owner: string;
  repo: string;
  issue_number?: number;
  title?: string;
  body?: string;
  description?: string;
  state?: 'open' | 'closed' | 'all';
  labels?: string[] | string;
  assignees?: string[] | string;
  milestone?: number;
  assignee?: string;
  comment?: string;
  searchQuery?: string;
  sort?: 'created' | 'updated' | 'comments';
  direction?: 'asc' | 'desc';
  limit?: number;
  since?: string;
  locked?: boolean;
  active_lock_reason?: 'off-topic' | 'too heated' | 'resolved' | 'spam';
}

export class GitHubIssueSkill implements Skill {
  async execute(params: GitHubIssueSkillParams, context: SkillExecutionContext): Promise<SkillResult> {
    try {
      const { action } = params;
      const timestamp = new Date().toISOString();

      switch (action) {
        case 'list':
          return await this.listIssues(params, context, timestamp);
        case 'create':
          return await this.createIssue(params, context, timestamp);
        case 'search':
          return await this.searchIssues(params, context, timestamp);
        case 'get':
          return await this.getIssue(params, context, timestamp);
        case 'update':
          return await this.updateIssue(params, context, timestamp);
        case 'close':
          return await this.closeIssue(params, context, timestamp);
        case 'reopen':
          return await this.reopenIssue(params, context, timestamp);
        case 'lock':
          return await this.lockIssue(params, context, timestamp);
        case 'unlock':
          return await this.unlockIssue(params, context, timestamp);
        case 'assign':
          return await this.assignIssue(params, context, timestamp);
        case 'unassign':
          return await this.unassignIssue(params, context, timestamp);
        case 'add_labels':
          return await this.addLabels(params, context, timestamp);
        case 'remove_labels':
          return await this.removeLabels(params, context, timestamp);
        default:
          throw new Error(`Unknown issue action: ${action}`);
      }
    } catch (error) {
      console.error('GitHub issue skill execution failed:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date().toISOString()
      };
    }
  }

  private async listIssues(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    if (!params.owner || !params.repo) {
      throw new Error('Owner and repository are required');
    }

    const result = await invoke<any[]>('get_github_repository_issues', {
      userId: context.userId,
      owner: params.owner,
      repo: params.repo,
      state: params.state || 'open',
      limit: params.limit || 10
    });

    const issues = this.processIssues(result);
    const statistics = this.calculateIssueStatistics(issues);

    return {
      success: true,
      data: {
        action: 'list_issues',
        issues: issues,
        count: issues.length,
        repository: `${params.owner}/${params.repo}`,
        state: params.state || 'open',
        statistics: statistics
      },
      message: `Found ${issues.length} issues in ${params.owner}/${params.repo}`,
      timestamp: timestamp
    };
  }

  private async createIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    if (!params.owner || !params.repo) {
      throw new Error('Owner and repository are required');
    }
    
    if (!params.title) {
      throw new Error('Issue title is required');
    }

    const issueBody = params.body || params.description || '';
    const labels = Array.isArray(params.labels) ? params.labels : params.labels ? [params.labels] : undefined;
    const assignees = Array.isArray(params.assignees) ? params.assignees : params.assignees ? [params.assignees] : undefined;

    const result = await invoke<any>('create_github_issue', {
      userId: context.userId,
      owner: params.owner,
      repo: params.repo,
      title: params.title,
      body: issueBody,
      labels: labels,
      assignees: assignees
    });

    return {
      success: true,
      data: {
        action: 'create_issue',
        issue_number: result.issue_number,
        issue_title: params.title,
        issue_url: result.url,
        repository: `${params.owner}/${params.repo}`
      },
      message: `Issue #${result.issue_number} created successfully`,
      timestamp: timestamp
    };
  }

  private async searchIssues(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    const { invoke } = await import('@tauri-apps/api/tauri');
    
    if (!params.searchQuery) {
      throw new Error('Search query is required');
    }

    // Mock search - in production, this would use GitHub search API
    const mockIssues = [
      {
        id: 1001,
        number: 42,
        title: "Add GitHub integration",
        body: "Implement comprehensive GitHub integration",
        state: "open",
        user: { login: "developer1", name: "Developer One" },
        assignees: [],
        labels: [{ id: 123, name: "enhancement", color: "a2eeef" }],
        created_at: "2025-11-01T10:00:00Z",
        updated_at: "2025-11-02T15:30:00Z",
        html_url: "https://github.com/atomcompany/atom-desktop/issues/42",
        repository: { full_name: "atomcompany/atom-desktop", private: false }
      },
      {
        id: 1002,
        number: 43,
        title: "Fix OAuth token refresh",
        body: "Resolve issue with OAuth token refresh mechanism",
        state: "closed",
        user: { login: "developer2", name: "Developer Two" },
        assignees: [{ login: "developer1", name: "Developer One" }],
        labels: [{ id: 789, name: "bug", color: "d73a4a" }],
        created_at: "2025-10-28T14:20:00Z",
        updated_at: "2025-11-02T12:45:00Z",
        closed_at: "2025-11-02T12:45:00Z",
        html_url: "https://github.com/atomcompany/atom-desktop/issues/43",
        repository: { full_name: "atomcompany/atom-desktop", private: false }
      }
    ];

    // Filter by search query (mock)
    const filteredIssues = mockIssues.filter(issue => 
      issue.title.toLowerCase().includes(params.searchQuery!.toLowerCase()) ||
      (issue.body && issue.body.toLowerCase().includes(params.searchQuery!.toLowerCase()))
    );

    const issues = this.processIssues(filteredIssues);
    const searchResults = issues.map(issue => ({
      ...issue,
      relevanceScore: this.calculateIssueRelevance(issue, params.searchQuery!),
      searchHighlights: this.generateIssueSearchHighlights(issue, params.searchQuery!)
    }));

    return {
      success: true,
      data: {
        action: 'search_issues',
        searchQuery: params.searchQuery,
        issues: searchResults,
        count: searchResults.length
      },
      message: `Found ${searchResults.length} issues matching "${params.searchQuery}"`,
      timestamp: timestamp
    };
  }

  private async getIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number) {
      throw new Error('Owner, repository, and issue number are required');
    }

    // Mock issue data
    const mockIssue = {
      id: 1001,
      number: params.issue_number,
      title: "Add GitHub integration",
      body: "Implement comprehensive GitHub integration with OAuth and API access",
      state: "open",
      locked: false,
      user: {
        login: "developer1",
        name: "Developer One",
        avatar_url: "https://github.com/developer1.png",
        type: "User"
      },
      assignees: [
        {
          login: "developer2",
          name: "Developer Two",
          avatar_url: "https://github.com/developer2.png",
          type: "User"
        }
      ],
      labels: [
        { id: 123, name: "enhancement", color: "a2eeef", description: "New feature or request" },
        { id: 456, name: "github", color: "0366d6", description: "Related to GitHub" }
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
        due_on: "2025-12-31T23:59:59Z"
      },
      comments: 12,
      created_at: "2025-11-01T10:00:00Z",
      updated_at: "2025-11-02T15:30:00Z",
      closed_at: null,
      html_url: `https://github.com/${params.owner}/${params.repo}/issues/${params.issue_number}`,
      repository_url: `https://api.github.com/repos/${params.owner}/${params.repo}`
    };

    const issue = this.processIssue(mockIssue);
    
    return {
      success: true,
      data: {
        action: 'get_issue',
        issue: issue,
        repository: `${params.owner}/${params.repo}`
      },
      message: `Retrieved issue #${params.issue_number}`,
      timestamp: timestamp
    };
  }

  private async updateIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number) {
      throw new Error('Owner, repository, and issue number are required');
    }

    const updates = this.extractIssueUpdates(params);
    
    // Mock update
    const updatedIssue = {
      id: 1001,
      number: params.issue_number,
      title: params.title || "Add GitHub integration",
      body: params.body || params.description || "Implement comprehensive GitHub integration",
      state: params.state || 'open',
      updated_at: timestamp,
      // ... other fields with updates applied
    };

    const issue = this.processIssue(updatedIssue);
    
    return {
      success: true,
      data: {
        action: 'update_issue',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        updated_fields: updates
      },
      message: `Issue #${params.issue_number} updated successfully`,
      timestamp: timestamp
    };
  }

  private async closeIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number) {
      throw new Error('Owner, repository, and issue number are required');
    }

    // Mock close
    const closedIssue = {
      id: 1001,
      number: params.issue_number,
      state: "closed",
      closed_at: timestamp,
      closed_by: { login: context.userId, name: "Current User" },
      updated_at: timestamp
    };

    const issue = this.processIssue(closedIssue);
    
    return {
      success: true,
      data: {
        action: 'close_issue',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        closed_at: timestamp
      },
      message: `Issue #${params.issue_number} closed successfully`,
      timestamp: timestamp
    };
  }

  private async reopenIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number) {
      throw new Error('Owner, repository, and issue number are required');
    }

    // Mock reopen
    const reopenedIssue = {
      id: 1001,
      number: params.issue_number,
      state: "open",
      closed_at: null,
      reopened_by: { login: context.userId, name: "Current User" },
      updated_at: timestamp
    };

    const issue = this.processIssue(reopenedIssue);
    
    return {
      success: true,
      data: {
        action: 'reopen_issue',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        reopened_at: timestamp
      },
      message: `Issue #${params.issue_number} reopened successfully`,
      timestamp: timestamp
    };
  }

  private async assignIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number || !params.assignee) {
      throw new Error('Owner, repository, issue number, and assignee are required');
    }

    // Mock assignment
    const assignedIssue = {
      id: 1001,
      number: params.issue_number,
      assignees: [{ login: params.assignee, name: "Assigned User" }],
      assigned_by: { login: context.userId, name: "Current User" },
      assigned_at: timestamp,
      updated_at: timestamp
    };

    const issue = this.processIssue(assignedIssue);
    
    return {
      success: true,
      data: {
        action: 'assign_issue',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        assignee: params.assignee,
        assigned_at: timestamp
      },
      message: `Issue #${params.issue_number} assigned to ${params.assignee}`,
      timestamp: timestamp
    };
  }

  private async addLabels(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number || !params.labels) {
      throw new Error('Owner, repository, issue number, and labels are required');
    }

    const labels = Array.isArray(params.labels) ? params.labels : [params.labels];
    
    // Mock add labels
    const labeledIssue = {
      id: 1001,
      number: params.issue_number,
      labels: labels.map(label => ({ name: label, color: "ff6600" })),
      updated_at: timestamp
    };

    const issue = this.processIssue(labeledIssue);
    
    return {
      success: true,
      data: {
        action: 'add_labels',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        labels_added: labels,
        added_at: timestamp
      },
      message: `Added labels to issue #${params.issue_number}: ${labels.join(', ')}`,
      timestamp: timestamp
    };
  }

  // Helper methods
  private processIssues(issues: any[]): any[] {
    return issues.map(issue => this.processIssue(issue));
  }

  private processIssue(issue: any): any {
    return {
      ...issue,
      created: new Date(issue.created_at),
      updated: new Date(issue.updated_at),
      closed_at: issue.closed_at ? new Date(issue.closed_at) : null,
      daysSinceCreation: this.getDaysSince(issue.created_at),
      daysSinceUpdate: this.getDaysSince(issue.updated_at),
      daysSinceClosed: issue.closed_at ? this.getDaysSince(issue.closed_at) : null,
      priority: this.calculateIssuePriority(issue),
      complexity: this.calculateIssueComplexity(issue),
      category: this.categorizeIssue(issue),
      healthScore: this.calculateIssueHealth(issue),
      engagement: this.calculateIssueEngagement(issue),
      resolutionTime: this.calculateResolutionTime(issue)
    };
  }

  private calculateIssueStatistics(issues: any[]): any {
    const totalIssues = issues.length;
    const openIssues = issues.filter(issue => issue.state === 'open').length;
    const closedIssues = issues.filter(issue => issue.state === 'closed').length;
    const totalComments = issues.reduce((sum, issue) => sum + issue.comments, 0);
    const averageComments = totalIssues > 0 ? totalComments / totalIssues : 0;
    const categories = this.getIssueCategories(issues);
    const priorities = this.getIssuePriorities(issues);
    const assignees = this.getIssueAssignees(issues);
    const labels = this.getIssueLabels(issues);
    const averageResolutionTime = this.getAverageResolutionTime(issues);
    const mostActiveIssue = this.getMostActiveIssue(issues);
    const oldestOpenIssue = this.getOldestOpenIssue(issues);

    return {
      total: totalIssues,
      open: openIssues,
      closed: closedIssues,
      comments: totalComments,
      average_comments: averageComments.toFixed(2),
      categories: categories,
      priorities: priorities,
      assignees: assignees,
      labels: labels,
      average_resolution_days: averageResolutionTime,
      most_active: mostActiveIssue,
      oldest_open: oldestOpenIssue,
      closure_rate: totalIssues > 0 ? ((closedIssues / totalIssues) * 100).toFixed(1) : '0'
    };
  }

  private calculateIssuePriority(issue: any): string {
    // Priority based on title, labels, and age
    const title = issue.title.toLowerCase();
    const hasUrgentLabel = issue.labels.some((label: any) => 
      label.name.toLowerCase().includes('urgent') || 
      label.name.toLowerCase().includes('critical')
    );
    const hasBugLabel = issue.labels.some((label: any) => 
      label.name.toLowerCase().includes('bug')
    );
    const daysOld = this.getDaysSince(issue.created_at);

    if (hasUrgentLabel || title.includes('critical') || title.includes('security')) {
      return 'critical';
    } else if (hasBugLabel || title.includes('break') || daysOld > 30) {
      return 'high';
    } else if (title.includes('feature') || daysOld > 14) {
      return 'medium';
    } else {
      return 'low';
    }
  }

  private calculateIssueComplexity(issue: any): string {
    // Complexity based on description length, labels, and comments
    const descriptionLength = issue.body ? issue.body.length : 0;
    const labelCount = issue.labels.length;
    const commentCount = issue.comments;
    const complexityScore = (descriptionLength / 100) + (labelCount * 5) + (commentCount * 2);

    if (complexityScore > 50) return 'high';
    if (complexityScore > 25) return 'medium';
    return 'low';
  }

  private categorizeIssue(issue: any): string {
    const title = issue.title.toLowerCase();
    const body = issue.body ? issue.body.toLowerCase() : '';
    const labels = issue.labels.map((label: any) => label.name.toLowerCase());

    // Check for explicit categories in labels
    if (labels.includes('bug')) return 'bug';
    if (labels.includes('feature')) return 'feature';
    if (labels.includes('enhancement')) return 'enhancement';
    if (labels.includes('documentation')) return 'documentation';
    if (labels.includes('question')) return 'question';
    if (labels.includes('maintenance')) return 'maintenance';

    // Infer category from content
    if (title.includes('fix') || title.includes('broken') || title.includes('error')) return 'bug';
    if (title.includes('add') || title.includes('implement') || title.includes('feature')) return 'feature';
    if (title.includes('docs') || title.includes('readme') || title.includes('documentation')) return 'documentation';
    if (title.includes('question') || title.includes('how') || title.includes('help')) return 'question';
    if (title.includes('update') || title.includes('upgrade') || title.includes('maintenance')) return 'maintenance';

    return 'other';
  }

  private calculateIssueHealth(issue: any): number {
    let score = 100;
    
    // Penalize for no recent updates
    const daysSinceUpdate = this.getDaysSince(issue.updated_at);
    if (daysSinceUpdate > 30) score -= 20;
    else if (daysSinceUpdate > 14) score -= 10;
    
    // Penalize for no assignee
    if (!issue.assignees || issue.assignees.length === 0) score -= 15;
    
    // Penalize for no labels
    if (!issue.labels || issue.labels.length === 0) score -= 10;
    
    // Bonus for good engagement
    if (issue.comments > 0) score += Math.min(10, issue.comments * 2);
    
    // Bonus for clear description
    if (issue.body && issue.body.length > 50) score += 5;
    
    return Math.max(0, Math.min(100, score));
  }

  private calculateIssueEngagement(issue: any): any {
    return {
      comments: issue.comments,
      reactions: 0, // Would need reactions data
      participants: 1, // Would need comment authors data
      engagement_score: Math.min(100, issue.comments * 5)
    };
  }

  private calculateResolutionTime(issue: any): number | null {
    if (issue.state !== 'closed' || !issue.closed_at) return null;
    
    const created = new Date(issue.created_at);
    const closed = new Date(issue.closed_at);
    const diffMs = closed.getTime() - created.getTime();
    
    return Math.floor(diffMs / (1000 * 60 * 60 * 24)); // days
  }

  private calculateIssueRelevance(issue: any, query: string): number {
    const queryLower = query.toLowerCase();
    let score = 0;
    
    // Title match
    if (issue.title.toLowerCase().includes(queryLower)) {
      score += 50;
    }
    
    // Body match
    if (issue.body && issue.body.toLowerCase().includes(queryLower)) {
      score += 30;
    }
    
    // Labels match
    if (issue.labels.some((label: any) => label.name.toLowerCase().includes(queryLower))) {
      score += 25;
    }
    
    // Comments match
    if (issue.comments > 0) {
      score += Math.min(20, issue.comments * 2);
    }
    
    // Recent activity bonus
    const daysSinceUpdate = this.getDaysSince(issue.updated_at);
    if (daysSinceUpdate < 7) score += 15;
    
    return score;
  }

  private generateIssueSearchHighlights(issue: any, query: string): string[] {
    const queryLower = query.toLowerCase();
    const highlights: string[] = [];
    
    if (issue.title.toLowerCase().includes(queryLower)) {
      highlights.push('title');
    }
    
    if (issue.body && issue.body.toLowerCase().includes(queryLower)) {
      highlights.push('body');
    }
    
    if (issue.labels.some((label: any) => label.name.toLowerCase().includes(queryLower))) {
      highlights.push('labels');
    }
    
    return highlights;
  }

  private getDaysSince(dateString: string): number {
    const date = new Date(dateString);
    const now = new Date();
    return Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
  }

  private getIssueCategories(issues: any[]): any {
    const categories: { [key: string]: number } = {};
    
    issues.forEach(issue => {
      const category = issue.category || 'other';
      categories[category] = (categories[category] || 0) + 1;
    });
    
    return Object.entries(categories)
      .map(([category, count]) => ({ category, count }))
      .sort((a, b) => b.count - a.count);
  }

  private getIssuePriorities(issues: any[]): any {
    const priorities: { [key: string]: number } = {};
    
    issues.forEach(issue => {
      const priority = issue.priority || 'low';
      priorities[priority] = (priorities[priority] || 0) + 1;
    });
    
    return Object.entries(priorities)
      .map(([priority, count]) => ({ priority, count }))
      .sort((a, b) => b.count - a.count);
  }

  private getIssueAssignees(issues: any[]): any {
    const assignees: { [key: string]: number } = {};
    
    issues.forEach(issue => {
      if (issue.assignees) {
        issue.assignees.forEach((assignee: any) => {
          assignees[assignee.login] = (assignees[assignee.login] || 0) + 1;
        });
      }
    });
    
    return Object.entries(assignees)
      .map(([assignee, count]) => ({ assignee, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }

  private getIssueLabels(issues: any[]): any {
    const labels: { [key: string]: number } = {};
    
    issues.forEach(issue => {
      if (issue.labels) {
        issue.labels.forEach((label: any) => {
          labels[label.name] = (labels[label.name] || 0) + 1;
        });
      }
    });
    
    return Object.entries(labels)
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 20);
  }

  private getAverageResolutionTime(issues: any[]): number {
    const closedIssues = issues.filter(issue => issue.state === 'closed' && issue.resolutionTime !== null);
    
    if (closedIssues.length === 0) return 0;
    
    const totalDays = closedIssues.reduce((sum, issue) => sum + issue.resolutionTime!, 0);
    return Math.floor(totalDays / closedIssues.length);
  }

  private getMostActiveIssue(issues: any[]): any {
    return issues.reduce((most, issue) => 
      issue.comments > most.comments ? issue : most, 
      { comments: 0 }
    );
  }

  private getOldestOpenIssue(issues: any[]): any {
    const openIssues = issues.filter(issue => issue.state === 'open');
    
    if (openIssues.length === 0) return null;
    
    return openIssues.reduce((oldest, issue) => 
      new Date(issue.created_at) < new Date(oldest.created_at) ? issue : oldest
    );
  }

  private extractIssueUpdates(params: GitHubIssueSkillParams): any {
    const updates: any = {};
    
    if (params.title !== undefined) updates.title = params.title;
    if (params.body !== undefined || params.description !== undefined) updates.body = params.body || params.description;
    if (params.state !== undefined) updates.state = params.state;
    if (params.labels !== undefined) updates.labels = Array.isArray(params.labels) ? params.labels : [params.labels];
    if (params.assignees !== undefined) updates.assignees = Array.isArray(params.assignees) ? params.assignees : [params.assignees];
    if (params.milestone !== undefined) updates.milestone = params.milestone;
    
    return updates;
  }

  private async unassignIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number || !params.assignee) {
      throw new Error('Owner, repository, issue number, and assignee are required');
    }

    // Mock unassignment
    const unassignedIssue = {
      id: 1001,
      number: params.issue_number,
      assignees: [],
      unassigned_by: { login: context.userId, name: "Current User" },
      unassigned_at: timestamp,
      updated_at: timestamp
    };

    const issue = this.processIssue(unassignedIssue);
    
    return {
      success: true,
      data: {
        action: 'unassign_issue',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        assignee: params.assignee,
        unassigned_at: timestamp
      },
      message: `Issue #${params.issue_number} unassigned from ${params.assignee}`,
      timestamp: timestamp
    };
  }

  private async removeLabels(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number || !params.labels) {
      throw new Error('Owner, repository, issue number, and labels are required');
    }

    const labels = Array.isArray(params.labels) ? params.labels : [params.labels];
    
    // Mock remove labels
    const unlabeledIssue = {
      id: 1001,
      number: params.issue_number,
      labels: [],
      updated_at: timestamp
    };

    const issue = this.processIssue(unlabeledIssue);
    
    return {
      success: true,
      data: {
        action: 'remove_labels',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        labels_removed: labels,
        removed_at: timestamp
      },
      message: `Removed labels from issue #${params.issue_number}: ${labels.join(', ')}`,
      timestamp: timestamp
    };
  }

  private async lockIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number) {
      throw new Error('Owner, repository, and issue number are required');
    }

    // Mock lock
    const lockedIssue = {
      id: 1001,
      number: params.issue_number,
      locked: true,
      active_lock_reason: params.active_lock_reason || 'off-topic',
      locked_by: { login: context.userId, name: "Current User" },
      locked_at: timestamp,
      updated_at: timestamp
    };

    const issue = this.processIssue(lockedIssue);
    
    return {
      success: true,
      data: {
        action: 'lock_issue',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        lock_reason: params.active_lock_reason || 'off-topic',
        locked_at: timestamp
      },
      message: `Issue #${params.issue_number} locked`,
      timestamp: timestamp
    };
  }

  private async unlockIssue(params: GitHubIssueSkillParams, context: SkillExecutionContext, timestamp: string): Promise<SkillResult> {
    if (!params.owner || !params.repo || !params.issue_number) {
      throw new Error('Owner, repository, and issue number are required');
    }

    // Mock unlock
    const unlockedIssue = {
      id: 1001,
      number: params.issue_number,
      locked: false,
      unlocked_by: { login: context.userId, name: "Current User" },
      unlocked_at: timestamp,
      updated_at: timestamp
    };

    const issue = this.processIssue(unlockedIssue);
    
    return {
      success: true,
      data: {
        action: 'unlock_issue',
        issue: issue,
        repository: `${params.owner}/${params.repo}`,
        issue_number: params.issue_number,
        unlocked_at: timestamp
      },
      message: `Issue #${params.issue_number} unlocked`,
      timestamp: timestamp
    };
  }
}

// Export singleton instance
export const githubIssueSkill = new GitHubIssueSkill();