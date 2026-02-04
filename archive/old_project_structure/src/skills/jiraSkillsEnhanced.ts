/**
 * Enhanced Jira Skills for ATOM Agentic OS
 *
 * Phase 1 implementation of advanced Jira integration capabilities
 * for the unified agent skill registry.
 */

import { SkillDefinition, SkillResponse } from "../services/agentSkillRegistry";

// Enhanced Jira skill definitions
export const jiraSkillsEnhanced: SkillDefinition[] = [
  {
    id: "jira-create-epic-with-stories",
    name: "Create Jira Epic with Stories",
    description:
      "Create a Jira epic along with related user stories in a single operation",
    category: "project-management",
    icon: "📚",
    parameters: {
      type: "object",
      properties: {
        projectKey: {
          type: "string",
          description: "Jira project key",
          minLength: 2,
          maxLength: 10,
        },
        epicName: {
          type: "string",
          description: "Epic name/title",
          minLength: 1,
          maxLength: 255,
        },
        epicDescription: {
          type: "string",
          description: "Epic description",
          maxLength: 32768,
        },
        stories: {
          type: "array",
          items: {
            type: "object",
            properties: {
              summary: {
                type: "string",
                description: "Story summary",
                minLength: 1,
                maxLength: 255,
              },
              description: {
                type: "string",
                description: "Story description",
                maxLength: 32768,
              },
              storyPoints: {
                type: "number",
                description: "Story points estimate",
                minimum: 0,
                maximum: 100,
              },
              priority: {
                type: "string",
                enum: ["Highest", "High", "Medium", "Low", "Lowest"],
                description: "Story priority",
                default: "Medium",
              },
            },
            required: ["summary"],
          },
          description: "User stories to create under the epic",
          default: [],
        },
        labels: {
          type: "array",
          items: { type: "string" },
          description: "Labels for the epic",
          default: [],
        },
        assignee: {
          type: "string",
          description: "Assignee account ID",
        },
      },
      required: ["projectKey", "epicName"],
    },
    handler: async (
      userId: string,
      parameters: any,
    ): Promise<SkillResponse> => {
      try {
        console.log(
          `Creating Jira epic with ${parameters.stories?.length || 0} stories`,
        );

        // Simulate API call delay
        await new Promise((resolve) => setTimeout(resolve, 1500));

        const epicKey = `${parameters.projectKey}-${Math.floor(Math.random() * 1000)}`;
        const storyKeys =
          parameters.stories?.map(
            (_: any, index: number) =>
              `${parameters.projectKey}-${Math.floor(Math.random() * 1000) + index}`,
          ) || [];

        return {
          ok: true,
          data: {
            epic: {
              key: epicKey,
              summary: parameters.epicName,
              description: parameters.epicDescription,
              project: parameters.projectKey,
              labels: parameters.labels,
              assignee: parameters.assignee,
              url: `https://jira.example.com/browse/${epicKey}`,
            },
            stories:
              parameters.stories?.map((story: any, index: number) => ({
                key: storyKeys[index],
                summary: story.summary,
                description: story.description,
                storyPoints: story.storyPoints,
                priority: story.priority,
                epic: epicKey,
                url: `https://jira.example.com/browse/${storyKeys[index]}`,
              })) || [],
            message: `Epic ${epicKey} created with ${storyKeys.length} stories`,
          },
          metadata: {
            executionTime: 1500,
            resourceUsage: {
              apiCalls: parameters.stories?.length + 1 || 1,
              computeTime: 1500,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: "JIRA_EPIC_CREATION_ERROR",
            message: `Failed to create epic with stories: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: "1.0.0",
    enabled: true,
    tags: ["jira", "epic", "story", "project-management", "agile"],
  },
  {
    id: "jira-sync-with-github",
    name: "Sync Jira with GitHub",
    description:
      "Synchronize Jira issues with GitHub repositories and pull requests",
    category: "integration",
    icon: "🔄",
    parameters: {
      type: "object",
      properties: {
        jiraProjectKey: {
          type: "string",
          description: "Jira project key",
          minLength: 2,
          maxLength: 10,
        },
        githubOwner: {
          type: "string",
          description: "GitHub repository owner",
          minLength: 1,
        },
        githubRepo: {
          type: "string",
          description: "GitHub repository name",
          minLength: 1,
        },
        syncDirection: {
          type: "string",
          enum: ["jira-to-github", "github-to-jira", "bidirectional"],
          description: "Sync direction",
          default: "bidirectional",
        },
        autoLinkPrs: {
          type: "boolean",
          description: "Automatically link pull requests to Jira issues",
          default: true,
        },
        updateStatus: {
          type: "boolean",
          description: "Update Jira status based on GitHub actions",
          default: true,
        },
        customMappings: {
          type: "object",
          description: "Custom field mappings between Jira and GitHub",
          properties: {
            jiraStatusToGithub: {
              type: "object",
              description: "Jira status to GitHub state mapping",
            },
            githubLabelsToJira: {
              type: "object",
              description: "GitHub labels to Jira components mapping",
            },
          },
        },
      },
      required: ["jiraProjectKey", "githubOwner", "githubRepo"],
    },
    handler: async (
      userId: string,
      parameters: any,
    ): Promise<SkillResponse> => {
      try {
        console.log(
          `Syncing Jira project ${parameters.jiraProjectKey} with GitHub ${parameters.githubOwner}/${parameters.githubRepo}`,
        );

        // Simulate sync process
        await new Promise((resolve) => setTimeout(resolve, 2000));

        const syncResults = {
          jiraIssuesLinked: Math.floor(Math.random() * 10) + 5,
          githubPrsLinked: Math.floor(Math.random() * 8) + 3,
          statusUpdates: Math.floor(Math.random() * 5) + 1,
          conflictsResolved: Math.floor(Math.random() * 3),
        };

        return {
          ok: true,
          data: {
            syncSummary: {
              direction: parameters.syncDirection,
              jiraProject: parameters.jiraProjectKey,
              githubRepo: `${parameters.githubOwner}/${parameters.githubRepo}`,
              ...syncResults,
            },
            details: {
              linkedIssues: [
                { jiraKey: `${parameters.jiraProjectKey}-123`, githubPr: 45 },
                { jiraKey: `${parameters.jiraProjectKey}-124`, githubPr: 46 },
              ],
              statusUpdates: [
                {
                  issue: `${parameters.jiraProjectKey}-123`,
                  from: "To Do",
                  to: "In Progress",
                },
              ],
            },
            message: `Sync completed: ${syncResults.jiraIssuesLinked} issues linked, ${syncResults.githubPrsLinked} PRs processed`,
          },
          metadata: {
            executionTime: 2000,
            resourceUsage: {
              apiCalls: 15,
              computeTime: 2000,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: "JIRA_GITHUB_SYNC_ERROR",
            message: `Sync failed: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: "1.0.0",
    enabled: true,
    tags: ["jira", "github", "sync", "integration", "devops"],
  },
  {
    id: "jira-bulk-transition-issues",
    name: "Bulk Transition Jira Issues",
    description:
      "Transition multiple Jira issues to a new status in a single operation",
    category: "project-management",
    icon: "⚡",
    parameters: {
      type: "object",
      properties: {
        issueKeys: {
          type: "array",
          items: {
            type: "string",
            description: "Jira issue keys (e.g., PROJ-123, PROJ-124)",
          },
          description: "Issue keys to transition",
          minItems: 1,
        },
        transition: {
          type: "string",
          description: "Target transition name",
          minLength: 1,
        },
        comment: {
          type: "string",
          description: "Comment to add to all transitions",
          maxLength: 32768,
        },
        skipFailures: {
          type: "boolean",
          description: "Continue on individual transition failures",
          default: false,
        },
        notifyUsers: {
          type: "boolean",
          description: "Notify assigned users about the transition",
          default: true,
        },
      },
      required: ["issueKeys", "transition"],
    },
    handler: async (
      userId: string,
      parameters: any,
    ): Promise<SkillResponse> => {
      try {
        console.log(
          `Bulk transitioning ${parameters.issueKeys.length} issues to "${parameters.transition}"`,
        );

        // Simulate bulk operation
        await new Promise((resolve) => setTimeout(resolve, 1000));

        const results = parameters.issueKeys.map(
          (issueKey: string, index: number) => ({
            issueKey,
            success: index < parameters.issueKeys.length - 1, // Simulate one failure
            error:
              index === parameters.issueKeys.length - 1
                ? "Transition not available"
                : undefined,
            transition: parameters.transition,
            comment: parameters.comment,
          }),
        );

        const successful = results.filter((r) => r.success).length;
        const failed = results.filter((r) => !r.success).length;

        return {
          ok: true,
          data: {
            transitionSummary: {
              total: parameters.issueKeys.length,
              successful,
              failed,
              transition: parameters.transition,
            },
            results,
            message: `Bulk transition completed: ${successful} successful, ${failed} failed`,
          },
          metadata: {
            executionTime: 1000,
            resourceUsage: {
              apiCalls: parameters.issueKeys.length,
              computeTime: 1000,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: "JIRA_BULK_TRANSITION_ERROR",
            message: `Bulk transition failed: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: "1.0.0",
    enabled: true,
    tags: ["jira", "bulk", "transition", "workflow", "automation"],
  },
  {
    id: "jira-generate-sprint-report",
    name: "Generate Sprint Report",
    description:
      "Generate comprehensive sprint reports with metrics and insights",
    category: "analytics",
    icon: "📊",
    parameters: {
      type: "object",
      properties: {
        boardId: {
          type: "number",
          description: "Jira board ID",
          minimum: 1,
        },
        sprintId: {
          type: "number",
          description: "Sprint ID",
          minimum: 1,
        },
        includeMetrics: {
          type: "boolean",
          description: "Include velocity and burndown metrics",
          default: true,
        },
        includeStories: {
          type: "boolean",
          description: "Include detailed story breakdown",
          default: true,
        },
        format: {
          type: "string",
          enum: ["json", "html", "markdown", "pdf"],
          description: "Report format",
          default: "json",
        },
      },
      required: ["boardId", "sprintId"],
    },
    handler: async (
      userId: string,
      parameters: any,
    ): Promise<SkillResponse> => {
      try {
        console.log(
          `Generating sprint report for board ${parameters.boardId}, sprint ${parameters.sprintId}`,
        );

        // Simulate report generation
        await new Promise((resolve) => setTimeout(resolve, 1800));

        const report = {
          sprint: {
            id: parameters.sprintId,
            name: `Sprint ${parameters.sprintId}`,
            startDate: new Date(
              Date.now() - 14 * 24 * 60 * 60 * 1000,
            ).toISOString(),
            endDate: new Date().toISOString(),
            goal: "Complete authentication feature and bug fixes",
          },
          metrics: parameters.includeMetrics
            ? {
                velocity: 42,
                committedPoints: 45,
                completedPoints: 42,
                carryOver: 3,
                burndown: Array.from({ length: 14 }, (_, i) => ({
                  day: i + 1,
                  remaining: 45 - i * 3,
                })),
              }
            : undefined,
          stories: parameters.includeStories
            ? {
                total: 15,
                completed: 14,
                inProgress: 1,
                notStarted: 0,
                breakdown: {
                  features: 8,
                  bugs: 5,
                  chores: 2,
                },
              }
            : undefined,
          teamPerformance: {
            members: 5,
            averageCycleTime: 2.3,
            throughput: 14,
          },
        };

        return {
          ok: true,
          data: {
            report,
            format: parameters.format,
            generatedAt: new Date().toISOString(),
            message: `Sprint report generated in ${parameters.format} format`,
          },
          metadata: {
            executionTime: 1800,
            resourceUsage: {
              apiCalls: 8,
              computeTime: 1800,
              memoryUsage: 0,
              storageUsage: 0,
            },
          },
        };
      } catch (error: any) {
        return {
          ok: false,
          error: {
            code: "JIRA_REPORT_ERROR",
            message: `Failed to generate sprint report: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: "1.0.0",
    enabled: true,
    tags: ["jira", "report", "sprint", "analytics", "metrics"],
  },
  {
    id: "jira-automate-workflow",
    name: "Automate Jira Workflow",
    description: "Create automated workflow rules for Jira issue management",
    category: "automation",
    icon: "🤖",
    parameters: {
      type: "object",
      properties: {
        projectKey: {
          type: "string",
          description: "Jira project key",
          minLength: 2,
          maxLength: 10,
        },
        ruleName: {
          type: "string",
          description: "Workflow rule name",
          minLength: 1,
        },
        trigger: {
          type: "string",
          enum: [
            "issue-created",
            "issue-updated",
            "comment-added",
            "status-changed",
          ],
          description: "Rule trigger event",
        },
        conditions: {
          type: "object",
          description: "Rule conditions",
          properties: {
            field: { type: "string" },
            operator: {
              type: "string",
              enum: ["equals", "contains", "greater-than", "less-than"],
            },
            value: { type: "string" },
          },
        },
        actions: {
          type: "array",
          items: {
            type: "object",
            properties: {
              type: {
                type: "string",
                enum: [
                  "transition",
                  "assign",
                  "comment",
                  "notify",
                  "field-update",
                ],
              },
              target: { type: "string" },
              value: { type: "string" },
            },
          },
          description: "Actions to perform when rule triggers",
        },
        enabled: {
          type: "boolean",
          description: "Enable the rule immediately",
          default: true,
        },
      },
      required: ["projectKey", "ruleName", "trigger", "actions"],
    },
    handler: async (
      userId: string,
      parameters: any,
    ): Promise<SkillResponse> => {
      try {
        console.log(`Creating automated workflow rule: ${parameters.ruleName}`);

        // Simulate rule creation
        await new Promise((resolve) => setTimeout(resolve, 1200));

        return {
          ok: true,
          data: {
            rule: {
              id: `rule_${Date.now()}`,
              name: parameters.ruleName,
              project: parameters.projectKey,
              trigger: parameters.trigger,
              conditions: parameters.conditions,
              actions: parameters.actions,
              enabled: parameters.enabled,
              created: new Date().toISOString(),
            },
            message: `Workflow rule "${parameters.ruleName}" created successfully`,
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
            code: "JIRA_WORKFLOW_ERROR",
            message: `Failed to create workflow rule: ${error.message}`,
            retryable: true,
          },
        };
      }
    },
    version: "1.0.0",
    enabled: true,
    tags: ["jira", "workflow", "automation", "rules", "efficiency"],
  },
];

// Export individual skills for selective registration
export const jiraCreateEpicWithStories = jiraSkillsEnhanced[0];
export const jiraSyncWithGitHub = jiraSkillsEnhanced[1];
export const jiraBulkTransitionIssues = jiraSkillsEnhanced[2];
export const jiraGenerateSprintReport = jiraSkillsEnhanced[3];
export const jiraAutomateWorkflow = jiraSkillsEnhanced[4];

// Default export for bulk registration
export default jiraSkillsEnhanced;
