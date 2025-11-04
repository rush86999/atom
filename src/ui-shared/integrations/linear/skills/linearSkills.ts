/**
 * Linear Integration Skills
 * Provides comprehensive Linear task management and issue tracking capabilities
 */

import { IntegrationSkill, SkillExecutionContext } from '../types';
import { LinearClient } from '@linear/sdk';

export interface LinearSkillConfig {
  accessToken?: string;
  teamId?: string;
  projectId?: string;
  baseUrl?: string;
}

export interface LinearIssue {
  id: string;
  identifier: string;
  title: string;
  description?: string;
  status: {
    id: string;
    name: string;
    color: string;
    type: string;
  };
  priority: {
    id: string;
    label: string;
    priority: number;
  };
  assignee?: {
    id: string;
    name: string;
    displayName: string;
    avatarUrl?: string;
  };
  project?: {
    id: string;
    name: string;
    icon: string;
    color: string;
  };
  team: {
    id: string;
    name: string;
    icon: string;
  };
  labels: Array<{
    id: string;
    name: string;
    color: string;
  }>;
  createdAt: string;
  updatedAt: string;
  dueDate?: string;
  state: string;
  url: string;
}

export interface LinearTeam {
  id: string;
  name: string;
  description?: string;
  icon: string;
  color: string;
  organization: {
    id: string;
    name: string;
    urlKey: string;
  };
  createdAt: string;
  updatedAt: string;
  memberCount: number;
  issuesCount: number;
  cyclesCount: number;
  members: Array<{
    id: string;
    name: string;
    displayName: string;
    avatarUrl?: string;
    role: string;
  }>;
  projects: Array<{
    id: string;
    name: string;
    icon: string;
    color: string;
    state: string;
  }>;
}

export interface LinearProject {
  id: string;
  name: string;
  description?: string;
  url: string;
  icon: string;
  color: string;
  team: {
    id: string;
    name: string;
    icon: string;
  };
  state: string;
  progress: number;
  completedIssuesCount: number;
  startedIssuesCount: number;
  unstartedIssuesCount: number;
  backloggedIssuesCount: number;
  canceledIssuesCount: number;
  createdAt: string;
  updatedAt: string;
  scope: string;
}

/**
 * Linear Skills Registry
 */
export const linearSkills: Record<string, IntegrationSkill> = {
  
  /**
   * Create a new Linear issue
   */
  linearCreateIssue: {
    id: 'linearCreateIssue',
    name: 'Create Linear Issue',
    description: 'Create a new issue in Linear',
    category: 'task-management',
    icon: '📋',
    parameters: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: 'Issue title'
        },
        description: {
          type: 'string',
          description: 'Issue description (optional)'
        },
        teamId: {
          type: 'string',
          description: 'Team ID (optional)'
        },
        projectId: {
          type: 'string',
          description: 'Project ID (optional)'
        },
        assigneeId: {
          type: 'string',
          description: 'Assignee user ID (optional)'
        },
        priority: {
          type: 'string',
          enum: ['urgent', 'high', 'medium', 'low'],
          description: 'Issue priority (default: medium)'
        },
        labels: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              id: { type: 'string' },
              name: { type: 'string' },
              color: { type: 'string' }
            }
          },
          description: 'Issue labels (optional)'
        }
      },
      required: ['title']
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as LinearSkillConfig;
        const response = await fetch('/api/linear/issues/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            title: params.title,
            description: params.description || '',
            team_id: params.teamId,
            project_id: params.projectId,
            assignee_id: params.assigneeId,
            priority: params.priority || 'medium',
            labels: params.labels || []
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
        console.error('Error creating Linear issue:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * List Linear issues
   */
  linearListIssues: {
    id: 'linearListIssues',
    name: 'List Linear Issues',
    description: 'List issues from Linear with optional filters',
    category: 'task-management',
    icon: '📝',
    parameters: {
      type: 'object',
      properties: {
        teamId: {
          type: 'string',
          description: 'Filter by team ID (optional)'
        },
        projectId: {
          type: 'string',
          description: 'Filter by project ID (optional)'
        },
        includeCompleted: {
          type: 'boolean',
          description: 'Include completed issues (default: true)',
          default: true
        },
        includeCanceled: {
          type: 'boolean',
          description: 'Include canceled issues (default: false)',
          default: false
        },
        includeBacklog: {
          type: 'boolean',
          description: 'Include backlog issues (default: true)',
          default: true
        },
        limit: {
          type: 'number',
          description: 'Maximum number of issues to return (default: 50)',
          default: 50
        }
      }
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as LinearSkillConfig;
        const response = await fetch('/api/linear/issues', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            team_id: params.teamId,
            project_id: params.projectId,
            include_completed: params.includeCompleted ?? true,
            include_canceled: params.includeCanceled ?? false,
            include_backlog: params.includeBacklog ?? true,
            limit: params.limit || 50
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to list issues');
        }

        return {
          success: true,
          data: {
            issues: result.data.issues,
            totalCount: result.data.total_count
          }
        };
      } catch (error) {
        console.error('Error listing Linear issues:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * List Linear teams
   */
  linearListTeams: {
    id: 'linearListTeams',
    name: 'List Linear Teams',
    description: 'List teams accessible to the user',
    category: 'project-management',
    icon: '👥',
    parameters: {
      type: 'object',
      properties: {
        limit: {
          type: 'number',
          description: 'Maximum number of teams to return (default: 20)',
          default: 20
        }
      }
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as LinearSkillConfig;
        const response = await fetch('/api/linear/teams', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            limit: params.limit || 20
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to list teams');
        }

        return {
          success: true,
          data: {
            teams: result.data.teams,
            totalCount: result.data.total_count
          }
        };
      } catch (error) {
        console.error('Error listing Linear teams:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * List Linear projects
   */
  linearListProjects: {
    id: 'linearListProjects',
    name: 'List Linear Projects',
    description: 'List projects from teams',
    category: 'project-management',
    icon: '🚀',
    parameters: {
      type: 'object',
      properties: {
        teamId: {
          type: 'string',
          description: 'Filter by team ID (optional)'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of projects to return (default: 50)',
          default: 50
        }
      }
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as LinearSkillConfig;
        const response = await fetch('/api/linear/projects', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            team_id: params.teamId,
            limit: params.limit || 50
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to list projects');
        }

        return {
          success: true,
          data: {
            projects: result.data.projects,
            totalCount: result.data.total_count
          }
        };
      } catch (error) {
        console.error('Error listing Linear projects:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * Search Linear
   */
  linearSearch: {
    id: 'linearSearch',
    name: 'Search Linear',
    description: 'Search across issues, teams, and projects in Linear',
    category: 'search',
    icon: '🔍',
    parameters: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query'
        },
        searchType: {
          type: 'string',
          enum: ['issues', 'global'],
          description: 'Search type (issues or global)',
          default: 'issues'
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
        const config = context.config as LinearSkillConfig;
        const response = await fetch('/api/linear/search', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            query: params.query,
            search_type: params.searchType || 'issues',
            limit: params.limit || 50
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to search Linear');
        }

        return {
          success: true,
          data: {
            results: result.data.results,
            totalCount: result.data.total_count,
            query: params.query
          }
        };
      } catch (error) {
        console.error('Error searching Linear:', error);
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
  linearGetProfile: {
    id: 'linearGetProfile',
    name: 'Get Linear Profile',
    description: 'Get the authenticated user profile and organization info',
    category: 'user-management',
    icon: '👤',
    parameters: {
      type: 'object',
      properties: {}
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as LinearSkillConfig;
        const response = await fetch('/api/linear/user/profile', {
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
            user: result.data.user,
            organization: result.data.organization
          }
        };
      } catch (error) {
        console.error('Error getting Linear profile:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  /**
   * List cycles
   */
  linearListCycles: {
    id: 'linearListCycles',
    name: 'List Linear Cycles',
    description: 'List cycles from teams',
    category: 'project-management',
    icon: '🔄',
    parameters: {
      type: 'object',
      properties: {
        teamId: {
          type: 'string',
          description: 'Filter by team ID (optional)'
        },
        includeCompleted: {
          type: 'boolean',
          description: 'Include completed cycles (default: true)',
          default: true
        },
        limit: {
          type: 'number',
          description: 'Maximum number of cycles to return (default: 20)',
          default: 20
        }
      }
    },
    execute: async (context: SkillExecutionContext, params: any) => {
      try {
        const config = context.config as LinearSkillConfig;
        const response = await fetch('/api/linear/cycles', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${config?.accessToken}`
          },
          body: JSON.stringify({
            user_id: context.userId,
            team_id: params.teamId,
            include_completed: params.includeCompleted ?? true,
            limit: params.limit || 20
          })
        });

        const result = await response.json();
        
        if (!result.ok) {
          throw new Error(result.error?.message || 'Failed to list cycles');
        }

        return {
          success: true,
          data: {
            cycles: result.data.cycles,
            totalCount: result.data.total_count
          }
        };
      } catch (error) {
        console.error('Error listing Linear cycles:', error);
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  }
};

/**
 * Linear skill hooks and utilities
 */
export const linearHooks = {
  /**
   * Validate Linear access token
   */
  validateToken: async (accessToken: string): Promise<boolean> => {
    try {
      const response = await fetch('/api/linear/health', {
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
   * Format issue for display
   */
  formatIssue: (issue: LinearIssue): string => {
    const priority = issue.priority.label;
    const status = issue.status.name;
    return `${issue.identifier}: ${issue.title} (${priority} priority, ${status})`;
  },

  /**
   * Get issue URL
   */
  getIssueUrl: (issue: LinearIssue): string => {
    return issue.url || `https://linear.app/issue/${issue.identifier}`;
  },

  /**
   * Extract user-friendly status
   */
  getHumanStatus: (state: string): string => {
    const statusMap: Record<string, string> = {
      'backlog': 'Backlog',
      'started': 'In Progress',
      'done': 'Completed',
      'canceled': 'Canceled',
      'triage': 'Triage',
      'open': 'Open'
    };
    return statusMap[state] || state;
  }
};

export default linearSkills;