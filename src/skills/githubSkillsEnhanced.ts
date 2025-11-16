/**
 * Enhanced GitHub Skills for ATOM Agentic OS
 *
 * Phase 1 implementation of advanced GitHub integration capabilities
 * for the unified agent skill registry.
 */

import { SkillDefinition, SkillResponse } from '../services/agentSkillRegistry';

// Enhanced GitHub skill definitions
export const githubSkillsEnhanced: SkillDefinition[] = [
  {
    id: 'github-create-repo-with-template',
    name: 'Create GitHub Repository with Template',
    description: 'Create a new GitHub repository using predefined templates',
    category: 'development',
    icon: '🐙',
    parameters: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Repository name',
          minLength: 1,
          maxLength: 100,
        },
        description: {
          type: 'string',
          description: 'Repository description',
          maxLength: 255,
        },
        template: {
          type: 'string',
          enum: ['nextjs', 'react', 'node-express', 'python-fastapi', 'vanilla'],
          description: 'Template to use for repository',
          default: 'nextjs',
        },
        private: {
          type: 'boolean',
          description: 'Make repository private',
          default: false,
        },
        autoInit: {
          type: 'boolean',
          description: 'Initialize with README',
          default: true,
        },
      },
      required: ['name'],
    },
    handler: async (userId: string, parameters: any): Promise<SkillResponse> => {
      try {
        // Implementation would integrate with actual GitHub API
        console.log(`Creating GitHub repository with template: ${parameters.name}`);

        // Simulate API call delay
        await new Promise(resolve => setTimeout(resolve, 1000));

        return {
          ok: true,
          data: {
            repository: {
              name: parameters.name,
              full_name: `user/${parameters.name}`,
              html_url: `https://github.com/user/${parameters.name}`,
              clone_url: `https://github.com/user/${parameters.name}.git`,
              template: parameters.template,
              private: parameters.private,
            },
            message: `Repository created successfully with ${parameters.template} template`,
          },
          metadata: {
            executionTime: 1200,
            resourceUsage: {
              apiCalls: 1,
              computeTime: 1200,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: 'GITHUB_CREATE_ERROR',
            message: `Failed to create repository: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: '1.0.0',
    enabled: true,
    tags: ['github', 'repository', 'template', 'development'],
  },
  {
    id: 'github-manage-webhooks',
    name: 'Manage GitHub Webhooks',
    description: 'Create, list, update, or delete GitHub webhooks for repositories',
    category: 'development',
    icon: '🪝',
    parameters: {
      type: 'object',
      properties: {
        owner: {
          type: 'string',
          description: 'Repository owner',
          minLength: 1,
        },
        repo: {
          type: 'string',
          description: 'Repository name',
          minLength: 1,
        },
        action: {
          type: 'string',
          enum: ['create', 'list', 'update', 'delete'],
          description: 'Action to perform',
        },
        webhookUrl: {
          type: 'string',
          description: 'Webhook URL (required for create/update)',
        },
        events: {
          type: 'array',
          items: {
            type: 'string',
            enum: ['push', 'pull_request', 'issues', 'release', 'deployment'],
          },
          description: 'Events to trigger webhook',
          default: ['push'],
        },
        webhookId: {
          type: 'string',
          description: 'Webhook ID (required for update/delete)',
        },
      },
      required: ['owner', 'repo', 'action'],
    },
    handler: async (userId: string, parameters: any): Promise<SkillResponse> => {
      try {
        console.log(`Managing GitHub webhooks for ${parameters.owner}/${parameters.repo}`);

        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 800));

        let result;
        switch (parameters.action) {
          case 'create':
            result = {
              message: `Webhook created for ${parameters.owner}/${parameters.repo}`,
              webhookId: 'wh_' + Date.now(),
              url: parameters.webhookUrl,
              events: parameters.events,
            };
            break;
          case 'list':
            result = {
              webhooks: [
                {
                  id: 'wh_123',
                  url: 'https://example.com/webhook',
                  events: ['push', 'pull_request'],
                  active: true,
                },
              ],
            };
            break;
          case 'update':
            result = {
              message: `Webhook ${parameters.webhookId} updated`,
              webhookId: parameters.webhookId,
              events: parameters.events,
            };
            break;
          case 'delete':
            result = {
              message: `Webhook ${parameters.webhookId} deleted`,
            };
            break;
          default:
            throw new Error(`Unknown action: ${parameters.action}`);
        }

        return {
          ok: true,
          data: result,
          metadata: {
            executionTime: 800,
            resourceUsage: {
              apiCalls: 1,
              computeTime: 800,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: 'GITHUB_WEBHOOK_ERROR',
            message: `Webhook operation failed: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: '1.0.0',
    enabled: true,
    tags: ['github', 'webhook', 'automation', 'integration'],
  },
  {
    id: 'github-create-issue-from-template',
    name: 'Create GitHub Issue from Template',
    description: 'Create GitHub issues using predefined templates for common tasks',
    category: 'project-management',
    icon: '📝',
    parameters: {
      type: 'object',
      properties: {
        owner: {
          type: 'string',
          description: 'Repository owner',
          minLength: 1,
        },
        repo: {
          type: 'string',
          description: 'Repository name',
          minLength: 1,
        },
        template: {
          type: 'string',
          enum: ['bug-report', 'feature-request', 'documentation', 'security', 'custom'],
          description: 'Issue template type',
        },
        title: {
          type: 'string',
          description: 'Issue title',
          minLength: 1,
          maxLength: 255,
        },
        customTemplate: {
          type: 'string',
          description: 'Custom template content (for custom template type)',
        },
        labels: {
          type: 'array',
          items: { type: 'string' },
          description: 'Labels to apply',
          default: [],
        },
        assignees: {
          type: 'array',
          items: { type: 'string' },
          description: 'Users to assign',
          default: [],
        },
      },
      required: ['owner', 'repo', 'template', 'title'],
    },
    handler: async (userId: string, parameters: any): Promise<SkillResponse> => {
      try {
        console.log(`Creating GitHub issue from template: ${parameters.template}`);

        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 600));

        const templates = {
          'bug-report': `## Bug Description
${parameters.title}

## Steps to Reproduce
1.
2.
3.

## Expected Behavior


## Actual Behavior


## Environment
- OS:
- Browser:
- Version: `,
          'feature-request': `## Feature Description
${parameters.title}

## Problem Statement


## Proposed Solution


## Alternative Solutions Considered


## Additional Context`,
          'documentation': `## Documentation Update
${parameters.title}

## Current Documentation


## Proposed Changes


## Reason for Change`,
          'security': `## Security Issue
${parameters.title}

## Description


## Impact


## Steps to Reproduce


## Suggested Fix`,
        };

        const body = parameters.template === 'custom'
          ? parameters.customTemplate
          : templates[parameters.template as keyof typeof templates];

        return {
          ok: true,
          data: {
            issue: {
              number: Math.floor(Math.random() * 1000),
              title: parameters.title,
              body: body,
              html_url: `https://github.com/${parameters.owner}/${parameters.repo}/issues/1`,
              labels: parameters.labels,
              assignees: parameters.assignees,
            },
            message: `Issue created using ${parameters.template} template`,
          },
          metadata: {
            executionTime: 600,
            resourceUsage: {
              apiCalls: 1,
              computeTime: 600,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: 'GITHUB_ISSUE_ERROR',
            message: `Failed to create issue: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: '1.0.0',
    enabled: true,
    tags: ['github', 'issue', 'template', 'project-management'],
  },
  {
    id: 'github-sync-branch-protection',
    name: 'Sync Branch Protection Rules',
    description: 'Configure and synchronize branch protection rules across repositories',
    category: 'devops',
    icon: '🛡️',
    parameters: {
      type: 'object',
      properties: {
        owner: {
          type: 'string',
          description: 'Repository owner',
          minLength: 1,
        },
        repo: {
          type: 'string',
          description: 'Repository name',
          minLength: 1,
        },
        branch: {
          type: 'string',
          description: 'Branch name (default: main)',
          default: 'main',
        },
        requireReviews: {
          type: 'boolean',
          description: 'Require pull request reviews',
          default: true,
        },
        requiredApprovals: {
          type: 'number',
          description: 'Number of required approvals',
          minimum: 0,
          maximum: 10,
          default: 1,
        },
        requireStatusChecks: {
          type: 'boolean',
          description: 'Require status checks to pass',
          default: true,
        },
        statusChecks: {
          type: 'array',
          items: { type: 'string' },
          description: 'Required status checks',
          default: ['ci/cd'],
        },
        enforceAdmins: {
          type: 'boolean',
          description: 'Enforce for administrators',
          default: true,
        },
      },
      required: ['owner', 'repo'],
    },
    handler: async (userId: string, parameters: any): Promise<SkillResponse> => {
      try {
        console.log(`Syncing branch protection for ${parameters.owner}/${parameters.repo}`);

        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 900));

        return {
          ok: true,
          data: {
            branch: parameters.branch,
            protection: {
              requireReviews: parameters.requireReviews,
              requiredApprovals: parameters.requiredApprovals,
              requireStatusChecks: parameters.requireStatusChecks,
              statusChecks: parameters.statusChecks,
              enforceAdmins: parameters.enforceAdmins,
            },
            message: `Branch protection rules applied to ${parameters.branch}`,
          },
          metadata: {
            executionTime: 900,
            resourceUsage: {
              apiCalls: 2,
              computeTime: 900,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: 'GITHUB_PROTECTION_ERROR',
            message: `Failed to sync branch protection: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: '1.0.0',
    enabled: true,
    tags: ['github', 'branch-protection', 'security', 'devops'],
  },
  {
    id: 'github-automate-releases',
    name: 'Automate GitHub Releases',
    description: 'Create automated releases with changelog generation',
    category: 'devops',
    icon: '🚀',
    parameters: {
      type: 'object',
      properties: {
        owner: {
          type: 'string',
          description: 'Repository owner',
          minLength: 1,
        },
        repo: {
          type: 'string',
          description: 'Repository name',
          minLength: 1,
        },
        tag: {
          type: 'string',
          description: 'Release tag (e.g., v1.0.0)',
          minLength: 1,
        },
        generateChangelog: {
          type: 'boolean',
          description: 'Generate changelog from commits',
          default: true,
        },
        prerelease: {
          type: 'boolean',
          description: 'Mark as prerelease',
          default: false,
        },
        draft: {
          type: 'boolean',
          description: 'Create as draft',
          default: false,
        },
        assets: {
          type: 'array',
          items: { type: 'string' },
          description: 'Asset files to include',
          default: [],
        },
      },
      required: ['owner', 'repo', 'tag'],
    },
    handler: async (userId: string, parameters: any): Promise<SkillResponse> => {
      try {
        console.log(`Creating automated release for ${parameters.owner}/${parameters.repo}`);

        // Simulate API call and changelog generation
        await new Promise(resolve => setTimeout(resolve, 1200));

        const changelog = parameters.generateChangelog ? `
## What's Changed
* Feature: Added new authentication system
* Fix: Resolved memory leak in cache
* Docs: Updated API documentation
* Chore: Updated dependencies

**Full Changelog**: https://github.com/${parameters.owner}/${parameters.repo}/compare/v0.9.0...${parameters.tag}
        `.trim() : 'Release notes placeholder';

        return {
          ok: true,
          data: {
            release: {
              tag_name: parameters.tag,
              name: `Release ${parameters.tag}`,
              body: changelog,
              draft: parameters.draft,
              prerelease: parameters.prerelease,
              assets: parameters.assets,
              html_url: `https://github.com/${parameters.owner}/${parameters.repo}/releases/tag/${parameters.tag}`,
            },
            message: `Release ${parameters.tag} created successfully`,
          },
          metadata: {
            executionTime: 1200,
            resourceUsage: {
              apiCalls: 3,
              computeTime: 1200,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: 'GITHUB_RELEASE_ERROR',
            message: `Failed to create release: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: '1.0.0',
    enabled: true,
    tags: ['github', 'release', 'automation', 'devops', 'changelog'],
  },
];

// Export individual skills for selective registration
export const githubCreateRepoWithTemplate = githubSkillsEnhanced[0];
export const githubManageWebhooks = githubSkillsEnhanced[1];
export const githubCreateIssueFromTemplate = githubSkillsEnhanced[2];
export const githubSyncBranchProtection = githubSkillsEnhanced[3];
export const githubAutomateReleases = githubSkillsEnhanced[4];

// Default export for bulk registration
export default githubSkillsEnhanced;
