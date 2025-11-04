/**
 * Next.js Integration Skills
 * Enhanced skill implementations for Next.js/Vercel project management
 */

import { Skill, SkillContext, SkillResult } from '@shared/ui-shared/skills/types';
import {
  NextjsProject,
  NextjsBuild,
  NextjsDeployment,
  NextjsAnalytics,
  NextjsEnvironmentVariable,
} from '../types';

export const NextjsSkills: Record<string, Skill> = {
  // List all Next.js projects
  'nextjs-list-projects': {
    name: 'Next.js List Projects',
    description: 'List all Next.js projects from Vercel',
    parameters: {
      type: 'object',
      properties: {
        status: {
          type: 'string',
          enum: ['active', 'archived', 'suspended', 'all'],
          description: 'Filter projects by status',
          default: 'active'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of projects to return',
          default: 50
        },
        includeBuilds: {
          type: 'boolean',
          description: 'Include recent builds for each project',
          default: false
        },
        includeDeployments: {
          type: 'boolean',
          description: 'Include deployment information',
          default: true
        }
      },
      required: []
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/nextjs/projects', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: context.userId,
            status: params.status || 'active',
            limit: params.limit || 50,
            include_builds: params.includeBuilds || false,
            include_deployments: params.includeDeployments !== false,
          })
        });

        const data = await response.json();

        if (!data.ok) {
          throw new Error(data.error || 'Failed to fetch Next.js projects');
        }

        const projects: NextjsProject[] = data.projects || [];

        return {
          success: true,
          data: {
            projects,
            count: projects.length,
            summary: `Found ${projects.length} Next.js projects`
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  // Get project details
  'nextjs-get-project': {
    name: 'Next.js Get Project Details',
    description: 'Get detailed information about a specific Next.js project',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'string',
          description: 'The ID of the project to fetch'
        },
        includeAnalytics: {
          type: 'boolean',
          description: 'Include project analytics data',
          default: false
        },
        includeEnvironmentVariables: {
          type: 'boolean',
          description: 'Include environment variables',
          default: false
        },
        dateRange: {
          type: 'object',
          properties: {
            start: { type: 'string' },
            end: { type: 'string' }
          },
          description: 'Date range for analytics'
        }
      },
      required: ['projectId']
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const [projectResponse, analyticsResponse] = await Promise.all([
          fetch('/api/integrations/nextjs/project', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: context.userId,
              project_id: params.projectId,
              include_environment_variables: params.includeEnvironmentVariables || false,
            })
          }),
          params.includeAnalytics ? fetch('/api/integrations/nextjs/analytics', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: context.userId,
              project_id: params.projectId,
              date_range: params.dateRange || {
                start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
                end: new Date().toISOString()
              }
            })
          }) : Promise.resolve({ ok: true, json: () => ({}) })
        ]);

        const projectData = await projectResponse.json();
        const analyticsData = await analyticsResponse.json();

        if (!projectData.ok) {
          throw new Error(projectData.error || 'Failed to fetch project details');
        }

        const result: any = {
          project: projectData.project,
          success: true
        };

        if (params.includeAnalytics && analyticsData.ok) {
          result.analytics = analyticsData.analytics;
        }

        return result;
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  // List recent builds
  'nextjs-list-builds': {
    name: 'Next.js List Builds',
    description: 'List recent builds for a Next.js project',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'string',
          description: 'The ID of the project'
        },
        status: {
          type: 'string',
          enum: ['pending', 'building', 'ready', 'error', 'canceled', 'all'],
          description: 'Filter builds by status',
          default: 'all'
        },
        limit: {
          type: 'number',
          description: 'Maximum number of builds to return',
          default: 20
        },
        includeLogs: {
          type: 'boolean',
          description: 'Include build logs',
          default: false
        }
      },
      required: ['projectId']
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/nextjs/builds', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: context.userId,
            project_id: params.projectId,
            status: params.status || 'all',
            limit: params.limit || 20,
            include_logs: params.includeLogs || false,
          })
        });

        const data = await response.json();

        if (!data.ok) {
          throw new Error(data.error || 'Failed to fetch Next.js builds');
        }

        const builds: NextjsBuild[] = data.builds || [];

        return {
          success: true,
          data: {
            builds,
            count: builds.length,
            summary: `Found ${builds.length} builds for project ${params.projectId}`
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  // Deploy project
  'nextjs-deploy': {
    name: 'Next.js Deploy Project',
    description: 'Trigger a new deployment for a Next.js project',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'string',
          description: 'The ID of the project to deploy'
        },
        branch: {
          type: 'string',
          description: 'Git branch to deploy (default: main)',
          default: 'main'
        },
        force: {
          type: 'boolean',
          description: 'Force a new deployment even if no changes',
          default: false
        }
      },
      required: ['projectId']
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/nextjs/deploy', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: context.userId,
            project_id: params.projectId,
            branch: params.branch || 'main',
            force: params.force || false,
          })
        });

        const data = await response.json();

        if (!data.ok) {
          throw new Error(data.error || 'Failed to trigger deployment');
        }

        return {
          success: true,
          data: {
            deployment: data.deployment,
            message: `Deployment triggered for project ${params.projectId}`
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  // Get project analytics
  'nextjs-get-analytics': {
    name: 'Next.js Get Analytics',
    description: 'Get analytics data for a Next.js project',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'string',
          description: 'The ID of the project'
        },
        dateRange: {
          type: 'object',
          properties: {
            start: { type: 'string' },
            end: { type: 'string' }
          },
          description: 'Date range for analytics (default: last 30 days)'
        },
        metrics: {
          type: 'array',
          items: { type: 'string' },
          description: 'Specific metrics to include',
          default: ['pageViews', 'uniqueVisitors', 'bounceRate', 'avgSessionDuration']
        }
      },
      required: ['projectId']
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const dateRange = params.dateRange || {
          start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
          end: new Date().toISOString()
        };

        const response = await fetch('/api/integrations/nextjs/analytics', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: context.userId,
            project_id: params.projectId,
            date_range: dateRange,
            metrics: params.metrics || ['pageViews', 'uniqueVisitors', 'bounceRate', 'avgSessionDuration'],
          })
        });

        const data = await response.json();

        if (!data.ok) {
          throw new Error(data.error || 'Failed to fetch analytics data');
        }

        const analytics: NextjsAnalytics = data.analytics;

        return {
          success: true,
          data: {
            analytics,
            dateRange,
            summary: `Analytics for project ${params.projectId} from ${dateRange.start} to ${dateRange.end}`
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  // Get deployment status
  'nextjs-get-deployment-status': {
    name: 'Next.js Get Deployment Status',
    description: 'Get the status of a specific deployment',
    parameters: {
      type: 'object',
      properties: {
        deploymentId: {
          type: 'string',
          description: 'The ID of the deployment'
        },
        includeBuildInfo: {
          type: 'boolean',
          description: 'Include associated build information',
          default: true
        }
      },
      required: ['deploymentId']
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/nextjs/deployment/status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: context.userId,
            deployment_id: params.deploymentId,
            include_build_info: params.includeBuildInfo !== false,
          })
        });

        const data = await response.json();

        if (!data.ok) {
          throw new Error(data.error || 'Failed to fetch deployment status');
        }

        return {
          success: true,
          data: {
            deployment: data.deployment,
            build: data.build,
            status: data.deployment.status
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  // Manage environment variables
  'nextjs-manage-env-vars': {
    name: 'Next.js Manage Environment Variables',
    description: 'Manage environment variables for a Next.js project',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'string',
          description: 'The ID of the project'
        },
        action: {
          type: 'string',
          enum: ['list', 'create', 'update', 'delete'],
          description: 'Action to perform',
          default: 'list'
        },
        key: {
          type: 'string',
          description: 'Environment variable key (required for create/update/delete)'
        },
        value: {
          type: 'string',
          description: 'Environment variable value (required for create/update)'
        },
        target: {
          type: 'array',
          items: { type: 'string' },
          description: 'Deployment targets (production, preview, development)',
          default: ['production', 'preview']
        },
        type: {
          type: 'string',
          enum: ['plain', 'secret', 'system'],
          description: 'Variable type',
          default: 'plain'
        }
      },
      required: ['projectId', 'action']
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        let endpoint = '/api/integrations/nextjs/env-vars';
        let body: any = {
          user_id: context.userId,
          project_id: params.projectId,
          action: params.action,
        };

        if (params.action !== 'list') {
          body.key = params.key;
          if (params.action === 'create' || params.action === 'update') {
            body.value = params.value;
            body.target = params.target || ['production', 'preview'];
            body.type = params.type || 'plain';
          }
        }

        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });

        const data = await response.json();

        if (!data.ok) {
          throw new Error(data.error || 'Failed to manage environment variables');
        }

        return {
          success: true,
          data: {
            action: params.action,
            result: data.result,
            message: `Successfully ${params.action}ed environment variable${params.key ? ` ${params.key}` : 's'}`
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },

  // Get project health
  'nextjs-get-health': {
    name: 'Next.js Get Project Health',
    description: 'Get health and performance metrics for a Next.js project',
    parameters: {
      type: 'object',
      properties: {
        projectId: {
          type: 'string',
          description: 'The ID of the project'
        },
        includeBuildHealth: {
          type: 'boolean',
          description: 'Include recent build health metrics',
          default: true
        },
        includeDeploymentHealth: {
          type: 'boolean',
          description: 'Include deployment health metrics',
          default: true
        },
        includePerformance: {
          type: 'boolean',
          description: 'Include performance metrics',
          default: true
        }
      },
      required: ['projectId']
    },
    execute: async (params: any, context: SkillContext): Promise<SkillResult> => {
      try {
        const response = await fetch('/api/integrations/nextjs/health', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: context.userId,
            project_id: params.projectId,
            include_build_health: params.includeBuildHealth !== false,
            include_deployment_health: params.includeDeploymentHealth !== false,
            include_performance: params.includePerformance !== false,
          })
        });

        const data = await response.json();

        if (!data.ok) {
          throw new Error(data.error || 'Failed to fetch project health');
        }

        return {
          success: true,
          data: {
            health: data.health,
            projectId: params.projectId,
            timestamp: new Date().toISOString()
          }
        };
      } catch (error) {
        return {
          success: false,
          error: error instanceof Error ? error.message : 'Unknown error'
        };
      }
    }
  },
};

export default NextjsSkills;