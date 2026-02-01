/**
 * GitLab Skills - Integration skills for GitLab platform
 * Provides AI agent capabilities for GitLab operations
 */

import { Skill, SkillContext, SkillResult } from '../types';

export interface GitLabProject {
  id: number;
  name: string;
  description: string;
  path_with_namespace: string;
  web_url: string;
  visibility: string;
  last_activity_at: string;
  default_branch: string;
  open_issues_count: number;
  star_count: number;
  forks_count: number;
}

export interface GitLabIssue {
  id: number;
  iid: number;
  title: string;
  description: string;
  state: string;
  labels: string[];
  author: {
    name: string;
    username: string;
  };
  assignee?: {
    name: string;
    username: string;
  };
  web_url: string;
  created_at: string;
  updated_at: string;
}

export interface GitLabMergeRequest {
  id: number;
  iid: number;
  title: string;
  description: string;
  state: string;
  source_branch: string;
  target_branch: string;
  author: {
    name: string;
    username: string;
  };
  assignee?: {
    name: string;
    username: string;
  };
  web_url: string;
  created_at: string;
  updated_at: string;
  merge_status: string;
}

export interface GitLabPipeline {
  id: number;
  status: string;
  ref: string;
  sha: string;
  web_url: string;
  created_at: string;
  updated_at: string;
  duration?: number;
}

export interface GitLabBranch {
  name: string;
  commit: {
    id: string;
    short_id: string;
    title: string;
    author_name: string;
    author_email: string;
    created_at: string;
  };
  protected: boolean;
  default: boolean;
  can_push: boolean;
}

export interface GitLabCommit {
  id: string;
  short_id: string;
  title: string;
  author_name: string;
  author_email: string;
  authored_date: string;
  committer_name: string;
  committer_email: string;
  committed_date: string;
  message: string;
  web_url: string;
}

/**
 * GitLab Skills - AI agent capabilities for GitLab operations
 */
export const gitlabSkills: Skill[] = [
  {
    id: 'gitlab-list-projects',
    name: 'List GitLab Projects',
    description: 'List all GitLab projects accessible to the user',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        search: {
          type: 'string',
          description: 'Search term to filter projects',
        },
        owned: {
          type: 'boolean',
          description: 'Only show projects owned by the user',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of projects to return',
        },
      },
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/projects', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            search: params.search,
            owned: params.owned,
            limit: params.limit || 20,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch projects: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} GitLab projects`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to list GitLab projects: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-list-issues',
    name: 'List GitLab Issues',
    description: 'List issues from GitLab projects',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'number',
          description: 'Project ID to list issues from',
        },
        state: {
          type: 'string',
          description: 'Filter by issue state (opened, closed)',
          enum: ['opened', 'closed', 'all'],
        },
        labels: {
          type: 'array',
          items: { type: 'string' },
          description: 'Filter by labels',
        },
        assignee: {
          type: 'string',
          description: 'Filter by assignee username',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of issues to return',
        },
      },
      required: ['projectId'],
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/issues', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            project_id: params.projectId,
            state: params.state || 'opened',
            labels: params.labels,
            assignee_username: params.assignee,
            limit: params.limit || 50,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch issues: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} GitLab issues`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to list GitLab issues: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-create-issue',
    name: 'Create GitLab Issue',
    description: 'Create a new issue in a GitLab project',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'number',
          description: 'Project ID where the issue should be created',
        },
        title: {
          type: 'string',
          description: 'Issue title',
        },
        description: {
          type: 'string',
          description: 'Issue description',
        },
        labels: {
          type: 'array',
          items: { type: 'string' },
          description: 'Labels to apply to the issue',
        },
        assigneeIds: {
          type: 'array',
          items: { type: 'number' },
          description: 'User IDs to assign the issue to',
        },
      },
      required: ['projectId', 'title'],
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/create-issue', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            project_id: params.projectId,
            title: params.title,
            description: params.description,
            labels: params.labels,
            assignee_ids: params.assigneeIds,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to create issue: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Successfully created issue: "${params.title}"`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to create GitLab issue: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-list-merge-requests',
    name: 'List GitLab Merge Requests',
    description: 'List merge requests from GitLab projects',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'number',
          description: 'Project ID to list merge requests from',
        },
        state: {
          type: 'string',
          description: 'Filter by merge request state (opened, closed, merged)',
          enum: ['opened', 'closed', 'merged', 'all'],
        },
        sourceBranch: {
          type: 'string',
          description: 'Filter by source branch',
        },
        targetBranch: {
          type: 'string',
          description: 'Filter by target branch',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of merge requests to return',
        },
      },
      required: ['projectId'],
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/merge-requests', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            project_id: params.projectId,
            state: params.state || 'opened',
            source_branch: params.sourceBranch,
            target_branch: params.targetBranch,
            limit: params.limit || 20,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch merge requests: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} GitLab merge requests`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to list GitLab merge requests: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-create-merge-request',
    name: 'Create GitLab Merge Request',
    description: 'Create a new merge request in a GitLab project',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'number',
          description: 'Project ID where the merge request should be created',
        },
        title: {
          type: 'string',
          description: 'Merge request title',
        },
        description: {
          type: 'string',
          description: 'Merge request description',
        },
        sourceBranch: {
          type: 'string',
          description: 'Source branch name',
        },
        targetBranch: {
          type: 'string',
          description: 'Target branch name',
        },
        assigneeIds: {
          type: 'array',
          items: { type: 'number' },
          description: 'User IDs to assign the merge request to',
        },
      },
      required: ['projectId', 'title', 'sourceBranch', 'targetBranch'],
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/create-merge-request', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            project_id: params.projectId,
            title: params.title,
            description: params.description,
            source_branch: params.sourceBranch,
            target_branch: params.targetBranch,
            assignee_ids: params.assigneeIds,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to create merge request: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Successfully created merge request: "${params.title}"`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to create GitLab merge request: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-list-pipelines',
    name: 'List GitLab Pipelines',
    description: 'List CI/CD pipelines from GitLab projects',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'number',
          description: 'Project ID to list pipelines from',
        },
        status: {
          type: 'string',
          description: 'Filter by pipeline status',
          enum: ['running', 'pending', 'success', 'failed', 'canceled', 'skipped'],
        },
        ref: {
          type: 'string',
          description: 'Filter by branch or tag',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of pipelines to return',
        },
      },
      required: ['projectId'],
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/pipelines', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            project_id: params.projectId,
            status: params.status,
            ref: params.ref,
            limit: params.limit || 20,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch pipelines: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} GitLab pipelines`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to list GitLab pipelines: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-trigger-pipeline',
    name: 'Trigger GitLab Pipeline',
    description: 'Trigger a new CI/CD pipeline in a GitLab project',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'number',
          description: 'Project ID where the pipeline should be triggered',
        },
        ref: {
          type: 'string',
          description: 'Branch or tag to run the pipeline on',
        },
        variables: {
          type: 'object',
          description: 'Pipeline variables as key-value pairs',
        },
      },
      required: ['projectId', 'ref'],
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/trigger-pipeline', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            project_id: params.projectId,
            ref: params.ref,
            variables: params.variables || {},
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to trigger pipeline: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data,
          message: `Successfully triggered pipeline on branch "${params.ref}"`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to trigger GitLab pipeline: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-list-branches',
    name: 'List GitLab Branches',
    description: 'List branches from a GitLab project',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'number',
          description: 'Project ID to list branches from',
        },
        search: {
          type: 'string',
          description: 'Search term to filter branches',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of branches to return',
        },
      },
      required: ['projectId'],
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/branches', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            project_id: params.projectId,
            search: params.search,
            limit: params.limit || 50,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch branches: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} GitLab branches`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to list GitLab branches: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-list-commits',
    name: 'List GitLab Commits',
    description: 'List commits from a GitLab project',
    category: 'gitlab',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'number',
          description: 'Project ID to list commits from',
        },
        ref: {
          type: 'string',
          description: 'Branch, tag, or commit SHA to list commits from',
        },
        since: {
          type: 'string',
          description: 'Only commits after this date (ISO format)',
        },
        until: {
          type: 'string',
          description: 'Only commits before this date (ISO format)',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of commits to return',
        },
      },
      required: ['projectId'],
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/gitlab/commits', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            project_id: params.projectId,
            ref: params.ref,
            since: params.since,
            until: params.until,
            limit: params.limit || 50,
          }),
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch commits: ${response.statusText}`);
        }

        const data = await response.json();
        return {
          success: true,
          data: data.data || [],
          message: `Found ${data.data?.length || 0} GitLab commits`,
        };
      } catch (error) {
        return {
          success: false,
          error: `Failed to list GitLab commits: ${error}`,
        };
      }
    },
  },
  {
    id: 'gitlab-health-check',
    name: 'GitLab Health Check',
    description: 'Check
