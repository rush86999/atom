/**
 * GitLab Integration Skills
 * AI skill implementations for GitLab automation
 */

import { GitLabProject, GitLabPipeline, GitLabIssue, GitLabMergeRequest, GitLabConfig } from '../types';

export const GitLabSkills = {
  // List GitLab projects
  'gitlab-list-projects': async (params: {
    user_id: string;
    limit?: number;
    visibility?: string;
    archived?: boolean;
    search?: string;
    sort?: string;
    order?: string;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          limit: params.limit || 50,
          visibility: params.visibility || 'all',
          archived: params.archived || false,
          search: params.search,
          sort: params.sort || 'updated_at',
          order: params.order || 'desc',
          include_pipelines: true,
          include_issues: true,
          include_merge_requests: true
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch GitLab projects');
      }

      return {
        success: true,
        data: {
          projects: data.projects || [],
          total: data.projects?.length || 0,
          stats: {
            total: data.projects?.length || 0,
            archived: data.projects?.filter((p: GitLabProject) => p.archived).length || 0,
            public: data.projects?.filter((p: GitLabProject) => p.visibility === 'public').length || 0,
            private: data.projects?.filter((p: GitLabProject) => p.visibility === 'private').length || 0,
            internal: data.projects?.filter((p: GitLabProject) => p.visibility === 'internal').length || 0
          }
        },
        message: `Found ${data.projects?.length || 0} GitLab projects`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Get specific GitLab project
  'gitlab-get-project': async (params: {
    user_id: string;
    project_id: number;
    include_pipelines?: boolean;
    include_issues?: boolean;
    include_merge_requests?: boolean;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/project', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          include_pipelines: params.include_pipelines !== false,
          include_issues: params.include_issues !== false,
          include_merge_requests: params.include_merge_requests !== false
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch GitLab project');
      }

      return {
        success: true,
        data: {
          project: data.project,
          pipelines: data.pipelines || [],
          issues: data.issues || [],
          merge_requests: data.merge_requests || []
        },
        message: `Project details retrieved for ${data.project?.name || 'project'}`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // List GitLab pipelines
  'gitlab-list-pipelines': async (params: {
    user_id: string;
    project_id?: number;
    status?: string;
    ref?: string;
    limit?: number;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/pipelines', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          status: params.status,
          ref: params.ref,
          limit: params.limit || 100,
          include_jobs: true
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch GitLab pipelines');
      }

      return {
        success: true,
        data: {
          pipelines: data.pipelines || [],
          total: data.pipelines?.length || 0,
          stats: {
            total: data.pipelines?.length || 0,
            success: data.pipelines?.filter((p: GitLabPipeline) => p.status === 'success').length || 0,
            failed: data.pipelines?.filter((p: GitLabPipeline) => p.status === 'failed').length || 0,
            running: data.pipelines?.filter((p: GitLabPipeline) => p.status === 'running').length || 0,
            pending: data.pipelines?.filter((p: GitLabPipeline) => p.status === 'pending').length || 0
          }
        },
        message: `Found ${data.pipelines?.length || 0} GitLab pipelines`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // List GitLab issues
  'gitlab-list-issues': async (params: {
    user_id: string;
    project_id?: number;
    state?: string;
    labels?: string[];
    milestone?: string;
    author?: string;
    assignee?: string;
    limit?: number;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          state: params.state || 'opened',
          labels: params.labels,
          milestone: params.milestone,
          author: params.author,
          assignee: params.assignee,
          limit: params.limit || 100
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch GitLab issues');
      }

      return {
        success: true,
        data: {
          issues: data.issues || [],
          total: data.issues?.length || 0,
          stats: {
            total: data.issues?.length || 0,
            opened: data.issues?.filter((i: GitLabIssue) => i.state === 'opened').length || 0,
            closed: data.issues?.filter((i: GitLabIssue) => i.state === 'closed').length || 0,
            confidential: data.issues?.filter((i: GitLabIssue) => i.confidential).length || 0,
            weighted: data.issues?.filter((i: GitLabIssue) => i.weight !== undefined).length || 0
          }
        },
        message: `Found ${data.issues?.length || 0} GitLab issues`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Create GitLab issue
  'gitlab-create-issue': async (params: {
    user_id: string;
    project_id: number;
    title: string;
    description?: string;
    labels?: string[];
    assignee_ids?: number[];
    milestone_id?: number;
    weight?: number;
    confidential?: boolean;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/create-issue', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          title: params.title,
          description: params.description,
          labels: params.labels,
          assignee_ids: params.assignee_ids,
          milestone_id: params.milestone_id,
          weight: params.weight,
          confidential: params.confidential || false
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to create GitLab issue');
      }

      return {
        success: true,
        data: {
          issue: data.issue,
          url: data.issue?.web_url
        },
        message: `Issue created: ${data.issue?.title || params.title}`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // List GitLab merge requests
  'gitlab-list-merge-requests': async (params: {
    user_id: string;
    project_id?: number;
    state?: string;
    source_branch?: string;
    target_branch?: string;
    author?: string;
    assignee?: string;
    labels?: string[];
    milestone?: string;
    limit?: number;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/merge-requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          state: params.state || 'opened',
          source_branch: params.source_branch,
          target_branch: params.target_branch,
          author: params.author,
          assignee: params.assignee,
          labels: params.labels,
          milestone: params.milestone,
          limit: params.limit || 100
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch GitLab merge requests');
      }

      return {
        success: true,
        data: {
          merge_requests: data.merge_requests || [],
          total: data.merge_requests?.length || 0,
          stats: {
            total: data.merge_requests?.length || 0,
            opened: data.merge_requests?.filter((mr: GitLabMergeRequest) => mr.state === 'opened').length || 0,
            merged: data.merge_requests?.filter((mr: GitLabMergeRequest) => mr.state === 'merged').length || 0,
            closed: data.merge_requests?.filter((mr: GitLabMergeRequest) => mr.state === 'closed').length || 0,
            draft: data.merge_requests?.filter((mr: GitLabMergeRequest) => mr.draft).length || 0,
            with_conflicts: data.merge_requests?.filter((mr: GitLabMergeRequest) => mr.has_conflicts).length || 0
          }
        },
        message: `Found ${data.merge_requests?.length || 0} GitLab merge requests`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Create GitLab merge request
  'gitlab-create-merge-request': async (params: {
    user_id: string;
    project_id: number;
    source_branch: string;
    target_branch: string;
    title: string;
    description?: string;
    assignee_ids?: number[];
    reviewer_ids?: number[];
    labels?: string[];
    milestone_id?: number;
    remove_source_branch?: boolean;
    squash?: boolean;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/create-merge-request', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          source_branch: params.source_branch,
          target_branch: params.target_branch,
          title: params.title,
          description: params.description,
          assignee_ids: params.assignee_ids,
          reviewer_ids: params.reviewer_ids,
          labels: params.labels,
          milestone_id: params.milestone_id,
          remove_source_branch: params.remove_source_branch || false,
          squash: params.squash || false
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to create GitLab merge request');
      }

      return {
        success: true,
        data: {
          merge_request: data.merge_request,
          url: data.merge_request?.web_url
        },
        message: `Merge request created: ${data.merge_request?.title || params.title}`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Trigger GitLab pipeline
  'gitlab-trigger-pipeline': async (params: {
    user_id: string;
    project_id: number;
    ref: string;
    variables?: Array<{ key: string; value: string }>;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/trigger-pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          ref: params.ref,
          variables: params.variables
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to trigger GitLab pipeline');
      }

      return {
        success: true,
        data: {
          pipeline: data.pipeline,
          url: data.pipeline?.web_url,
          status: data.pipeline?.status
        },
        message: `Pipeline triggered for ${params.ref} in project ${params.project_id}`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Get GitLab health status
  'gitlab-get-health': async (params: {
    user_id: string;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/health', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to get GitLab health');
      }

      return {
        success: true,
        data: {
          status: data.status,
          connected: data.connected,
          user: data.user,
          token_status: data.token_status,
          last_check: data.last_check,
          api_version: data.api_version
        },
        message: `GitLab health: ${data.status || 'Unknown'}`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Start GitLab data ingestion
  'gitlab-start-ingestion': async (params: {
    user_id: string;
    config: GitLabConfig;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/start-ingestion', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          config: params.config
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to start GitLab ingestion');
      }

      return {
        success: true,
        data: {
          ingestion_id: data.ingestion_id,
          status: data.status,
          progress: data.progress,
          message: data.message,
          estimated_duration: data.estimated_duration
        },
        message: `GitLab ingestion started: ${data.status}`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Manage GitLab webhooks
  'gitlab-manage-webhooks': async (params: {
    user_id: string;
    project_id: number;
    action: 'list' | 'create' | 'update' | 'delete';
    webhook_url?: string;
    events?: string[];
    secret_token?: string;
    webhook_id?: number;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/webhooks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          action: params.action,
          webhook_url: params.webhook_url,
          events: params.events,
          secret_token: params.secret_token,
          webhook_id: params.webhook_id
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to manage GitLab webhooks');
      }

      return {
        success: true,
        data: {
          webhooks: data.webhooks,
          webhook: data.webhook,
          action: params.action
        },
        message: `Webhook ${params.action} completed successfully`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Get GitLab user information
  'gitlab-get-user': async (params: {
    user_id: string;
    target_user_id?: number;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/user', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          target_user_id: params.target_user_id
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to get GitLab user');
      }

      return {
        success: true,
        data: {
          user: data.user,
          projects_count: data.projects_count,
          groups_count: data.groups_count,
          followers: data.followers,
          following: data.following
        },
        message: `User information retrieved for ${data.user?.name || 'user'}`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Get GitLab commits
  'gitlab-list-commits': async (params: {
    user_id: string;
    project_id: number;
    branch?: string;
    since?: string;
    until?: string;
    author?: string;
    limit?: number;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/commits', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          branch: params.branch,
          since: params.since,
          until: params.until,
          author: params.author,
          limit: params.limit || 50
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch GitLab commits');
      }

      return {
        success: true,
        data: {
          commits: data.commits || [],
          total: data.commits?.length || 0
        },
        message: `Found ${data.commits?.length || 0} GitLab commits`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Get GitLab branches
  'gitlab-list-branches': async (params: {
    user_id: string;
    project_id: number;
    search?: string;
    limit?: number;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/branches', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          search: params.search,
          limit: params.limit || 100
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to fetch GitLab branches');
      }

      return {
        success: true,
        data: {
          branches: data.branches || [],
          total: data.branches?.length || 0,
          default_branch: data.default_branch
        },
        message: `Found ${data.branches?.length || 0} GitLab branches`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  },

  // Manage GitLab environment variables
  'gitlab-manage-environment-variables': async (params: {
    user_id: string;
    project_id: number;
    action: 'list' | 'create' | 'update' | 'delete';
    key?: string;
    value?: string;
    variable_type?: 'env_var' | 'file';
    protected?: boolean;
    masked?: boolean;
    raw?: boolean;
  }) => {
    try {
      const response = await fetch('/api/integrations/gitlab/environment-variables', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: params.user_id,
          project_id: params.project_id,
          action: params.action,
          key: params.key,
          value: params.value,
          variable_type: params.variable_type || 'env_var',
          protected: params.protected || false,
          masked: params.masked || false,
          raw: params.raw || false
        })
      });

      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Failed to manage GitLab environment variables');
      }

      return {
        success: true,
        data: {
          variables: data.variables || [],
          variable: data.variable,
          action: params.action
        },
        message: `Environment variable ${params.action} completed successfully`
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      };
    }
  }
};

export default GitLabSkills;