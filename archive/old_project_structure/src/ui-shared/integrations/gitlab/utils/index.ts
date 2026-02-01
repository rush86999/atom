/**
 * GitLab Integration Utilities
 * Helper functions for GitLab data processing and manipulation
 */

import {
  GitLabProject,
  GitLabPipeline,
  GitLabIssue,
  GitLabMergeRequest,
  GitLabCommit,
  GitLabUser,
  GitLabBranch,
  GitLabJob,
  GitLabRelease
} from '../types';

export class GitLabUtils {
  /**
   * Format commit SHA for display
   */
  static formatCommitSha(sha: string): string {
    return sha.substring(0, 8);
  }

  /**
   * Format duration in seconds to human readable format
   */
  static formatDuration(seconds?: number): string {
    if (!seconds) return 'N/A';
    
    if (seconds < 60) {
      return `${Math.round(seconds)}s`;
    } else if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const remainingSeconds = seconds % 60;
      return `${minutes}m ${Math.round(remainingSeconds)}s`;
    } else {
      const hours = Math.floor(seconds / 3600);
      const remainingMinutes = Math.floor((seconds % 3600) / 60);
      return `${hours}h ${remainingMinutes}m`;
    }
  }

  /**
   * Get relative time string
   */
  static getRelativeTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffInSeconds < 60) {
      return 'just now';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes}m ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours}h ago`;
    } else if (diffInSeconds < 604800) {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days}d ago`;
    } else {
      const weeks = Math.floor(diffInSeconds / 604800);
      return `${weeks}w ago`;
    }
  }

  /**
   * Filter projects by search term
   */
  static filterProjects(
    projects: GitLabProject[],
    searchTerm: string
  ): GitLabProject[] {
    if (!searchTerm || searchTerm.trim() === '') {
      return projects;
    }

    const term = searchTerm.toLowerCase().trim();
    return projects.filter(project =>
      project.name.toLowerCase().includes(term) ||
      project.path.toLowerCase().includes(term) ||
      project.description?.toLowerCase().includes(term) ||
      project.namespace.name.toLowerCase().includes(term) ||
      project.namespace.full_path.toLowerCase().includes(term)
    );
  }

  /**
   * Sort projects by specified field
   */
  static sortProjects(
    projects: GitLabProject[],
    sortBy: string,
    sortOrder: 'asc' | 'desc' = 'desc'
  ): GitLabProject[] {
    return [...projects].sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortBy) {
        case 'name':
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
          break;
        case 'path':
          aValue = a.path.toLowerCase();
          bValue = b.path.toLowerCase();
          break;
        case 'created_at':
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
        case 'updated_at':
          aValue = new Date(a.updated_at).getTime();
          bValue = new Date(b.updated_at).getTime();
          break;
        case 'last_activity_at':
          aValue = new Date(a.last_activity_at).getTime();
          bValue = new Date(b.last_activity_at).getTime();
          break;
        case 'star_count':
          aValue = a.star_count;
          bValue = b.star_count;
          break;
        case 'forks_count':
          aValue = a.forks_count;
          bValue = b.forks_count;
          break;
        case 'open_issues_count':
          aValue = a.open_issues_count;
          bValue = b.open_issues_count;
          break;
        default:
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
      }

      if (aValue < bValue) {
        return sortOrder === 'asc' ? -1 : 1;
      } else if (aValue > bValue) {
        return sortOrder === 'asc' ? 1 : -1;
      } else {
        return 0;
      }
    });
  }

  /**
   * Sort pipelines by status or date
   */
  static sortPipelines(
    pipelines: GitLabPipeline[],
    sortBy: string = 'created_at',
    sortOrder: 'asc' | 'desc' = 'desc'
  ): GitLabPipeline[] {
    return [...pipelines].sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortBy) {
        case 'status':
          const statusOrder = {
            'running': 0,
            'pending': 1,
            'created': 2,
            'manual': 3,
            'success': 4,
            'failed': 5,
            'canceled': 6,
            'skipped': 7
          };
          aValue = statusOrder[a.status as keyof typeof statusOrder] || 999;
          bValue = statusOrder[b.status as keyof typeof statusOrder] || 999;
          break;
        case 'created_at':
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
        case 'updated_at':
          aValue = new Date(a.updated_at).getTime();
          bValue = new Date(b.updated_at).getTime();
          break;
        case 'duration':
          aValue = a.duration || 0;
          bValue = b.duration || 0;
          break;
        default:
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
      }

      if (aValue < bValue) {
        return sortOrder === 'asc' ? -1 : 1;
      } else if (aValue > bValue) {
        return sortOrder === 'asc' ? 1 : -1;
      } else {
        return 0;
      }
    });
  }

  /**
   * Sort issues by state or date
   */
  static sortIssues(
    issues: GitLabIssue[],
    sortBy: string = 'created_at',
    sortOrder: 'asc' | 'desc' = 'desc'
  ): GitLabIssue[] {
    return [...issues].sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortBy) {
        case 'state':
          const stateOrder = { 'opened': 0, 'closed': 1 };
          aValue = stateOrder[a.state as keyof typeof stateOrder] || 2;
          bValue = stateOrder[b.state as keyof typeof stateOrder] || 2;
          break;
        case 'created_at':
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
        case 'updated_at':
          aValue = new Date(a.updated_at).getTime();
          bValue = new Date(b.updated_at).getTime();
          break;
        case 'weight':
          aValue = a.weight || 0;
          bValue = b.weight || 0;
          break;
        case 'iid':
          aValue = a.iid;
          bValue = b.iid;
          break;
        default:
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
      }

      if (aValue < bValue) {
        return sortOrder === 'asc' ? -1 : 1;
      } else if (aValue > bValue) {
        return sortOrder === 'asc' ? 1 : -1;
      } else {
        return 0;
      }
    });
  }

  /**
   * Sort merge requests by state or date
   */
  static sortMergeRequests(
    mergeRequests: GitLabMergeRequest[],
    sortBy: string = 'created_at',
    sortOrder: 'asc' | 'desc' = 'desc'
  ): GitLabMergeRequest[] {
    return [...mergeRequests].sort((a, b) => {
      let aValue: any;
      let bValue: any;

      switch (sortBy) {
        case 'state':
          const stateOrder = { 'opened': 0, 'merged': 1, 'closed': 2, 'locked': 3 };
          aValue = stateOrder[a.state as keyof typeof stateOrder] || 4;
          bValue = stateOrder[b.state as keyof typeof stateOrder] || 4;
          break;
        case 'created_at':
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
        case 'updated_at':
          aValue = new Date(a.updated_at).getTime();
          bValue = new Date(b.updated_at).getTime();
          break;
        case 'iid':
          aValue = a.iid;
          bValue = b.iid;
          break;
        default:
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
      }

      if (aValue < bValue) {
        return sortOrder === 'asc' ? -1 : 1;
      } else if (aValue > bValue) {
        return sortOrder === 'asc' ? 1 : -1;
      } else {
        return 0;
      }
    });
  }

  /**
   * Get pipeline status color
   */
  static getPipelineStatusColor(status: string): string {
    const statusColors = {
      'created': 'gray',
      'waiting_for_resource': 'yellow',
      'preparing': 'yellow',
      'pending': 'yellow',
      'running': 'blue',
      'success': 'green',
      'failed': 'red',
      'canceled': 'gray',
      'skipped': 'gray',
      'manual': 'purple',
      'scheduled': 'orange'
    };
    return statusColors[status as keyof typeof statusColors] || 'gray';
  }

  /**
   * Get issue status color
   */
  static getIssueStatusColor(state: string, confidential?: boolean): string {
    if (confidential) return 'purple';
    
    const statusColors = {
      'opened': 'orange',
      'closed': 'green'
    };
    return statusColors[state as keyof typeof statusColors] || 'gray';
  }

  /**
   * Get merge request status color
   */
  static getMergeRequestStatusColor(state: string): string {
    const statusColors = {
      'opened': 'blue',
      'closed': 'gray',
      'locked': 'red',
      'merged': 'green'
    };
    return statusColors[state as keyof typeof statusColors] || 'gray';
  }

  /**
   * Get project visibility color
   */
  static getProjectVisibilityColor(visibility: string): string {
    const visibilityColors = {
      'public': 'green',
      'internal': 'yellow',
      'private': 'red'
    };
    return visibilityColors[visibility as keyof typeof visibilityColors] || 'gray';
  }

  /**
   * Calculate pipeline success rate
   */
  static calculatePipelineSuccessRate(pipelines: GitLabPipeline[]): number {
    if (pipelines.length === 0) return 0;
    
    const successfulPipelines = pipelines.filter(p => p.status === 'success').length;
    return Math.round((successfulPipelines / pipelines.length) * 100);
  }

  /**
   * Calculate average pipeline duration
   */
  static calculateAveragePipelineDuration(pipelines: GitLabPipeline[]): string {
    const pipelinesWithDuration = pipelines.filter(p => p.duration && p.duration > 0);
    
    if (pipelinesWithDuration.length === 0) return 'N/A';
    
    const totalDuration = pipelinesWithDuration.reduce((sum, p) => sum + p.duration!, 0);
    const averageDuration = totalDuration / pipelinesWithDuration.length;
    
    return this.formatDuration(averageDuration);
  }

  /**
   * Filter issues by state, labels, or assignee
   */
  static filterIssues(
    issues: GitLabIssue[],
    filters: {
      state?: string;
      labels?: string[];
      assignee?: string;
      author?: string;
      milestone?: string;
    }
  ): GitLabIssue[] {
    return issues.filter(issue => {
      if (filters.state && issue.state !== filters.state) {
        return false;
      }
      
      if (filters.labels && filters.labels.length > 0) {
        const issueLabelNames = issue.labels.map(l => l.title);
        const hasAllLabels = filters.labels.every(label => issueLabelNames.includes(label));
        if (!hasAllLabels) {
          return false;
        }
      }
      
      if (filters.assignee && issue.assignee?.username !== filters.assignee) {
        return false;
      }
      
      if (filters.author && issue.author.username !== filters.author) {
        return false;
      }
      
      if (filters.milestone && issue.milestone?.title !== filters.milestone) {
        return false;
      }
      
      return true;
    });
  }

  /**
   * Generate project summary
   */
  static generateProjectSummary(project: GitLabProject): string {
    const parts = [
      `Project: ${project.name}`,
      `Visibility: ${project.visibility}`,
      `Stars: ${project.star_count}`,
      `Forks: ${project.forks_count}`,
      `Open Issues: ${project.open_issues_count}`
    ];
    
    if (project.description) {
      parts.unshift(project.description);
    }
    
    return parts.join(' | ');
  }

  /**
   * Get file extension from path
   */
  static getFileExtension(path: string): string {
    const fileName = path.split('/').pop() || '';
    const extension = fileName.split('.').pop();
    return extension || '';
  }

  /**
   * Format file size
   */
  static formatFileSize(bytes?: number): string {
    if (!bytes) return 'N/A';
    
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024;
      unitIndex++;
    }
    
    return `${size.toFixed(2)} ${units[unitIndex]}`;
  }

  /**
   * Generate webhook URL for project
   */
  static generateWebhookUrl(baseUrl: string, projectId: number): string {
    return `${baseUrl}/api/webhooks/gitlab/${projectId}`;
  }

  /**
   * Validate GitLab project name
   */
  static validateProjectName(name: string): {
    isValid: boolean;
    errors: string[];
  } {
    const errors: string[] = [];
    
    if (!name || name.trim() === '') {
      errors.push('Project name is required');
    }
    
    if (name.length > 255) {
      errors.push('Project name must be less than 255 characters');
    }
    
    if (!/^[a-zA-Z0-9._-]+$/.test(name)) {
      errors.push('Project name can only contain letters, numbers, dots, hyphens, and underscores');
    }
    
    if (name.startsWith('.') || name.startsWith('-')) {
      errors.push('Project name cannot start with a dot or hyphen');
    }
    
    if (name.endsWith('.')) {
      errors.push('Project name cannot end with a dot');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Generate commit message excerpt
   */
  static getCommitMessageExcerpt(message: string, maxLength: number = 50): string {
    if (!message) return 'No message';
    
    // Remove issue numbers, merge request references, etc.
    const cleanedMessage = message
      .replace(/^(fix|feat|docs|style|refactor|test|chore)(\(.*\))?:\s*/i, '')
      .replace(/Closes #\d+/g, '')
      .replace(/Fixes #\d+/g, '')
      .replace(/Resolves #\d+/g, '')
      .trim();
    
    if (cleanedMessage.length <= maxLength) {
      return cleanedMessage;
    }
    
    return cleanedMessage.substring(0, maxLength).trim() + '...';
  }

  /**
   * Check if merge request can be merged
   */
  static canMergeMergeRequest(mr: GitLabMergeRequest): boolean {
    return (
      mr.state === 'opened' &&
      mr.merge_status === 'can_be_merged' &&
      !mr.draft &&
      !mr.has_conflicts &&
      !mr.discussions_locked
    );
  }

  /**
   * Calculate merge request completion percentage
   */
  static getMergeRequestCompletion(mr: GitLabMergeRequest): number {
    if (mr.task_completion_status) {
      const { count, completed_count } = mr.task_completion_status;
      if (count === 0) return 100;
      return Math.round((completed_count / count) * 100);
    }
    
    // Estimate based on approvals and discussions
    let completion = 50; // Base completion
    
    if (mr.approved_by && mr.approved_by.length > 0) {
      completion += 30;
    }
    
    if (!mr.discussions_to_resolve || mr.discussions_to_resolve.length === 0) {
      completion += 20;
    }
    
    return Math.min(100, completion);
  }

  /**
   * Get issue priority based on labels and weight
   */
  static getIssuePriority(issue: GitLabIssue): 'high' | 'medium' | 'low' {
    const highPriorityLabels = ['urgent', 'critical', 'high', 'bug'];
    const mediumPriorityLabels = ['medium', 'enhancement'];
    
    const issueLabels = issue.labels.map(l => l.title.toLowerCase());
    
    if (highPriorityLabels.some(label => issueLabels.includes(label))) {
      return 'high';
    }
    
    if (mediumPriorityLabels.some(label => issueLabels.includes(label))) {
      return 'medium';
    }
    
    if (issue.weight && issue.weight >= 5) {
      return 'high';
    } else if (issue.weight && issue.weight >= 3) {
      return 'medium';
    }
    
    return 'low';
  }

  /**
   * Format GitLab URL
   */
  static formatGitLabUrl(baseUrl: string, path: string): string {
    const cleanBaseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    const cleanPath = path.startsWith('/') ? path : '/' + path;
    return cleanBaseUrl + cleanPath;
  }

  /**
   * Generate avatar URL with size
   */
  static getAvatarUrl(url: string, size: number = 32): string {
    const separator = url.includes('?') ? '&' : '?';
    return `${url}${separator}s=${size}`;
  }

  /**
   * Check if branch is protected
   */
  static isBranchProtected(branch: GitLabBranch): boolean {
    return branch.protected || branch.name === 'main' || branch.name === 'master';
  }

  /**
   * Format job duration with queue time
   */
  static formatJobDurationWithQueue(job: GitLabJob): string {
    const durationStr = this.formatDuration(job.duration);
    const queueStr = job.queued_duration ? this.formatDuration(job.queued_duration) : '';
    
    if (queueStr) {
      return `Queue: ${queueStr} | Run: ${durationStr}`;
    }
    
    return durationStr;
  }

  /**
   * Generate file path for GitLab API
   */
  static generateFilePath(projectId: number, filePath: string, ref: string = 'main'): string {
    const encodedPath = encodeURIComponent(filePath);
    return `/projects/${projectId}/repository/files/${encodedPath}?ref=${ref}`;
  }

  /**
   * Calculate repository statistics
   */
  static calculateRepositoryStats(projects: GitLabProject[]): {
    totalProjects: number;
    totalStars: number;
    totalForks: number;
    totalOpenIssues: number;
    totalPrivateProjects: number;
    totalPublicProjects: number;
    averageStarsPerProject: number;
    averageForksPerProject: number;
  } {
    const totalProjects = projects.length;
    const totalStars = projects.reduce((sum, p) => sum + p.star_count, 0);
    const totalForks = projects.reduce((sum, p) => sum + p.forks_count, 0);
    const totalOpenIssues = projects.reduce((sum, p) => sum + p.open_issues_count, 0);
    const totalPrivateProjects = projects.filter(p => p.visibility === 'private').length;
    const totalPublicProjects = projects.filter(p => p.visibility === 'public').length;
    
    const averageStarsPerProject = totalProjects > 0 ? Math.round(totalStars / totalProjects) : 0;
    const averageForksPerProject = totalProjects > 0 ? Math.round(totalForks / totalProjects) : 0;
    
    return {
      totalProjects,
      totalStars,
      totalForks,
      totalOpenIssues,
      totalPrivateProjects,
      totalPublicProjects,
      averageStarsPerProject,
      averageForksPerProject
    };
  }
}

export default GitLabUtils;