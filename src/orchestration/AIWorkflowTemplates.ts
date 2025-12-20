import { MultiIntegrationWorkflowEngine, WorkflowDefinition, WorkflowStep, WorkflowTrigger } from "./MultiIntegrationWorkflowEngine";
import { Logger } from "../utils/logger";
import { EventEmitter } from "events";

/**
 * AI-Powered Cross-Platform Workflow Templates
 * 
 * Pre-built intelligent workflows that span multiple integrations
 * with automatic optimization and learning capabilities
 */

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: 'productivity' | 'communication' | 'data_management' | 'automation' | 'analytics' | 'collaboration';
  targetIntegrations: string[];
  aiOptimizations: {
    autoRouting: boolean;
    predictiveExecution: boolean;
    errorReduction: boolean;
    performanceOptimization: boolean;
  };
  userPersonalization: {
    adaptToUserBehavior: boolean;
    learnFromUsage: boolean;
    customizeInterface: boolean;
  };
  estimatedTimeSavings: string;
  complexity: 'simple' | 'moderate' | 'complex' | 'advanced';
  prerequisites: string[];
}

export interface AIWorkflowInsight {
  type: 'performance' | 'error_prediction' | 'optimization' | 'usage_pattern';
  confidence: number;
  message: string;
  suggestedAction?: string;
  impact: 'high' | 'medium' | 'low';
}

export class AIWorkflowTemplates extends EventEmitter {
  private engine: MultiIntegrationWorkflowEngine;
  private logger: Logger;
  private templates: Map<string, WorkflowTemplate>;
  private userWorkflows: Map<string, string[]>; // userId -> workflowIds
  private performanceData: Map<string, any[]>; // workflowId -> performance metrics
  private aiInsights: Map<string, AIWorkflowInsight[]>; // workflowId -> insights

  constructor(engine: MultiIntegrationWorkflowEngine) {
    super();
    this.engine = engine;
    this.logger = new Logger("AIWorkflowTemplates");
    this.templates = new Map();
    this.userWorkflows = new Map();
    this.performanceData = new Map();
    this.aiInsights = new Map();

    this.initializeTemplates();
    this.startAIOptimization();
  }

  private initializeTemplates(): void {
    // Template 1: Cross-Platform Task Creation & Sync
    const crossPlatformTaskTemplate: WorkflowDefinition = {
      id: "cross-platform-task-creation",
      name: "Universal Task Creation & Synchronization",
      description: "Create tasks across all project management platforms with automatic sync and intelligent routing",
      version: "1.0.0",
      category: "productivity",
      steps: [
        {
          id: "extract-task-details",
          name: "Extract Task Details",
          type: "data_transform",
          parameters: {
            extractionRules: {
              taskName: "title",
              description: "body",
              priority: "labels",
              assignee: "mentions",
              dueDate: "dates"
            }
          },
          dependsOn: [],
          retryPolicy: {
            maxAttempts: 3,
            delay: 1000,
            backoffMultiplier: 2
          },
          timeout: 10000,
          metadata: { aiPowered: true, model: "task-extraction-v2" }
        },
        {
          id: "determine-target-platforms",
          name: "Determine Target Platforms",
          type: "condition",
          parameters: {
            conditions: [
              { field: "user_preferences.target_platforms", operator: "exists", value: true },
              { field: "task_type", operator: "in", value: ["development", "design", "marketing"] }
            ]
          },
          dependsOn: ["extract-task-details"],
          retryPolicy: {
            maxAttempts: 2,
            delay: 500,
            backoffMultiplier: 1.5
          },
          timeout: 5000,
          condition: {
            field: "platform_selection_logic",
            operator: "ai_optimized",
            value: "predictive_routing"
          },
          metadata: { mlModel: "platform-predictor-v1" }
        },
        {
          id: "create-asana-task",
          name: "Create Asana Task",
          type: "integration_action",
          integrationId: "asana",
          action: "create_task",
          parameters: {
            taskMapping: {
              title: "extracted.taskName",
              description: "extracted.description",
              priority: "extracted.priority",
              assignee: "extracted.assignee",
              due_date: "extracted.dueDate"
            },
            retryOnError: true
          },
          dependsOn: ["determine-target-platforms"],
          retryPolicy: {
            maxAttempts: 3,
            delay: 2000,
            backoffMultiplier: 2
          },
          timeout: 15000,
          metadata: { platform: "asana", autoRetry: true }
        },
        {
          id: "create-trello-task",
          name: "Create Trello Card",
          type: "integration_action",
          integrationId: "trello",
          action: "create_card",
          parameters: {
            cardMapping: {
              title: "extracted.taskName",
              description: "extracted.description",
              list: "predicted.list",
              labels: "extracted.priority",
              members: "extracted.assignee"
            }
          },
          dependsOn: ["determine-target-platforms"],
          retryPolicy: {
            maxAttempts: 3,
            delay: 2000,
            backoffMultiplier: 2
          },
          timeout: 15000,
          metadata: { platform: "trello", autoRetry: true }
        },
        {
          id: "create-slack-notification",
          name: "Create Slack Notification",
          type: "integration_action",
          integrationId: "slack",
          action: "send_message",
          parameters: {
            channel: "task-creation",
            message: "📋 New task created: {{extracted.taskName}} across platforms",
            mentions: ["@team"]
          },
          dependsOn: ["create-asana-task", "create-trello-task"],
          retryPolicy: {
            maxAttempts: 2,
            delay: 1000,
            backoffMultiplier: 1.5
          },
          timeout: 8000,
          metadata: { platform: "slack", notification: true }
        },
        {
          id: "sync-task-states",
          name: "Sync Task States Across Platforms",
          type: "parallel",
          parameters: {
            syncOperations: [
              {
                from: "asana",
                to: "trello",
                fields: ["status", "completion_date", "comments"]
              },
              {
                from: "trello",
                to: "asana",
                fields: ["status", "due_date", "checklists"]
              }
            ],
            bidirectionalSync: true,
            conflictResolution: "latest_update_wins"
          },
          dependsOn: ["create-asana-task", "create-trello-task", "create-slack-notification"],
          retryPolicy: {
            maxAttempts: 5,
            delay: 3000,
            backoffMultiplier: 1.5
          },
          timeout: 30000,
          metadata: { syncType: "bidirectional", aiConflictResolution: true }
        }
      ],
      triggers: [
        {
          id: "task-creation-trigger",
          type: "manual",
          enabled: true,
          metadata: { autoAI: true }
        },
        {
          id: "email-to-task-trigger",
          type: "integration_event",
          integrationId: "gmail",
          eventType: "new_email_with_action_items",
          condition: {
            containsActionItems: true,
            importanceLevel: ["high", "normal"]
          },
          enabled: true,
          metadata: { aiExtraction: true }
        }
      ],
      variables: {
        taskDetails: {},
        userPreferences: {},
        platformSelection: {},
        syncResults: {}
      },
      settings: {
        timeout: 120000,
        retryPolicy: {
          maxAttempts: 3,
          delay: 5000
        },
        priority: "high",
        parallelExecution: true
      },
      integrations: ["asana", "trello", "slack", "gmail"],
      tags: ["cross-platform", "task-management", "ai-optimized", "sync"],
      createdAt: new Date(),
      updatedAt: new Date(),
      enabled: true
    };

    // Template 2: Unified Cross-Platform Search & Intelligence
    const unifiedSearchTemplate: WorkflowDefinition = {
      id: "unified-cross-platform-search",
      name: "Universal Search & Intelligence Aggregation",
      description: "Search across all connected platforms simultaneously with AI-powered result aggregation and prioritization",
      version: "1.0.0",
      category: "data_management",
      steps: [
        {
          id: "parse-search-query",
          name: "Parse and Optimize Search Query",
          type: "data_transform",
          parameters: {
            aiQueryOptimization: true,
            entityExtraction: true,
            intentDetection: true,
            platformSpecificOptimization: true
          },
          dependsOn: [],
          retryPolicy: {
            maxAttempts: 2,
            delay: 500,
            backoffMultiplier: 1.5
          },
          timeout: 8000,
          metadata: { aiModel: "query-optimizer-v3" }
        },
        {
          id: "parallel-search-execution",
          name: "Execute Parallel Platform Searches",
          type: "parallel",
          parameters: {
            searchOperations: [
              {
                platform: "google_drive",
                query: "optimized.google_drive_query",
                filters: "detected.file_types",
                sort: "relevance"
              },
              {
                platform: "slack",
                query: "optimized.slack_query",
                channels: "detected.channels",
                timeRange: "detected.time_period"
              },
              {
                platform: "asana",
                query: "optimized.asana_query",
                projects: "detected.projects",
                taskFilters: "detected.task_filters"
              },
              {
                platform: "gmail",
                query: "optimized.gmail_query",
                filters: "detected.email_filters",
                searchType: "comprehensive"
              },
              {
                platform: "notion",
                query: "optimized.notion_query",
                database: "detected.databases",
                properties: "detected.properties"
              }
            ],
            timeoutPerPlatform: 15000,
            fallbackOnError: true
          },
          dependsOn: ["parse-search-query"],
          retryPolicy: {
            maxAttempts: 2,
            delay: 1000,
            backoffMultiplier: 2
          },
          timeout: 60000,
          metadata: { parallelSearch: true, intelligentFallback: true }
        },
        {
          id: "ai-result-aggregation",
          name: "AI-Powered Result Aggregation & Ranking",
          type: "data_transform",
          parameters: {
            aggregationModel: "result-aggregator-v2",
            rankingAlgorithm: "relevance_with_context",
            deduplication: true,
            crossPlatformLinking: true,
            userPreferenceLearning: true,
            resultEnrichment: {
              addPlatformContext: true,
              extractRelationships: true,
              generatePreview: true
            }
          },
          dependsOn: ["parallel-search-execution"],
          retryPolicy: {
            maxAttempts: 3,
            delay: 2000,
            backoffMultiplier: 1.5
          },
          timeout: 20000,
          metadata: { aiAggregation: true, smartRanking: true }
        },
        {
          id: "generate-search-insights",
          name: "Generate Search Insights & Recommendations",
          type: "data_transform",
          parameters: {
            insightGeneration: true,
            relatedSuggestions: true,
            trendAnalysis: true,
            userBehaviorAnalysis: true
          },
          dependsOn: ["ai-result-aggregation"],
          retryPolicy: {
            maxAttempts: 2,
            delay: 1000,
            backoffMultiplier: 1.5
          },
          timeout: 10000,
          metadata: { aiInsights: true, personalized: true }
        }
      ],
      triggers: [
        {
          id: "universal-search-trigger",
          type: "manual",
          enabled: true,
          metadata: { voiceEnabled: true, autoComplete: true }
        },
        {
          id: "proactive-search-trigger",
          type: "event",
          condition: {
            contextChange: true,
            userActivity: true,
            timeContext: "working_hours"
          },
          enabled: true,
          metadata: { aiProactive: true }
        }
      ],
      variables: {
        originalQuery: {},
        optimizedQueries: {},
        searchResults: {},
        aggregatedResults: {},
        userInsights: {}
      },
      settings: {
        timeout: 90000,
        retryPolicy: {
          maxAttempts: 2,
          delay: 3000
        },
        priority: "normal",
        parallelExecution: true
      },
      integrations: ["google_drive", "slack", "asana", "gmail", "notion"],
      tags: ["search", "ai-powered", "cross-platform", "intelligence"],
      createdAt: new Date(),
      updatedAt: new Date(),
      enabled: true
    };

    // Template 3: AI-Powered Communication Orchestration
    const communicationOrchestrationTemplate: WorkflowDefinition = {
      id: "ai-communication-orchestration",
      name: "Intelligent Cross-Platform Communication Management",
      description: "AI-powered communication orchestration that routes messages intelligently across platforms based on context and urgency",
      version: "1.0.0",
      category: "communication",
      steps: [
        {
          id: "analyze-communication-context",
          name: "Analyze Communication Context & Intent",
          type: "data_transform",
          parameters: {
            contextAnalysis: {
              detectUrgency: true,
              detectPlatformPreference: true,
              detectRecipientAvailability: true,
              detectMessageType: true,
              detectProjectRelevance: true
            },
            aiModel: "communication-analyzer-v2"
          },
          dependsOn: [],
          retryPolicy: {
            maxAttempts: 3,
            delay: 1000,
            backoffMultiplier: 1.5
          },
          timeout: 15000,
          metadata: { aiContextAnalysis: true }
        },
        {
          id: "intelligent-platform-routing",
          name: "Intelligent Platform Routing Decision",
          type: "condition",
          parameters: {
            routingLogic: "ai_optimized",
            factors: [
              "recipient_availability",
              "message_urgency",
              "platform_preference",
              "project_context",
              "time_of_day",
              "historical_success"
            ],
            fallbackRules: [
              { condition: "high_urgency", platforms: ["slack", "teams"] },
              { condition: "formal_message", platforms: ["email"] },
              { condition: "project_related", platforms: ["asana", "slack"] },
              { condition: "document_sharing", platforms: ["google_drive", "sharepoint"] }
            ]
          },
          dependsOn: ["analyze-communication-context"],
          retryPolicy: {
            maxAttempts: 2,
            delay: 500,
            backoffMultiplier: 1.5
          },
          timeout: 8000,
          condition: {
            field: "routing_decision",
            operator: "ai_optimized",
            value: "multi_factor_analysis"
          },
          metadata: { aiRouting: true, learningEnabled: true }
        },
        {
          id: "execute-multi-platform-communication",
          name: "Execute Multi-Platform Communication",
          type: "parallel",
          parameters: {
            communicationChannels: [
              {
                platform: "slack",
                action: "send_message",
                conditions: ["casual_context", "urgent_message", "project_discussion"]
              },
              {
                platform: "teams",
                action: "send_message",
                conditions: ["enterprise_context", "formal_discussion", "corporate_environment"]
              },
              {
                platform: "gmail",
                action: "send_email",
                conditions: ["formal_message", "external_communication", "document_attachment"]
              },
              {
                platform: "asana",
                action: "create_task",
                conditions: ["actionable_message", "task_delegation", "project_assignment"]
              },
              {
                platform: "slack",
                action: "create_channel",
                conditions: ["new_project", "team_formation", "topic_discussion"]
              }
            ],
            personalization: {
              adaptToUserStyle: true,
              learnFromResponses: true,
              optimizeTiming: true
            }
          },
          dependsOn: ["intelligent-platform-routing"],
          retryPolicy: {
            maxAttempts: 3,
            delay: 2000,
            backoffMultiplier: 2
          },
          timeout: 25000,
          metadata: { parallelCommunication: true, aiPersonalization: true }
        },
        {
          id: "track-communication-outcomes",
          name: "Track Communication Outcomes & Learn",
          type: "data_transform",
          parameters: {
            outcomeTracking: {
              measureEngagement: true,
              trackResponseTimes: true,
              monitorEffectiveness: true,
              collectUserFeedback: true
            },
            learningModel: "communication-optimizer-v1",
            feedbackIntegration: true
          },
          dependsOn: ["execute-multi-platform-communication"],
          retryPolicy: {
            maxAttempts: 2,
            delay: 1000,
            backoffMultiplier: 1.5
          },
          timeout: 10000,
          metadata: { aiLearning: true, outcomeTracking: true }
        }
      ],
      triggers: [
        {
          id: "user-communication-trigger",
          type: "manual",
          enabled: true,
          metadata: { voiceEnabled: true, smartSuggestions: true }
        },
        {
          id: "context-aware-trigger",
          type: "event",
          condition: {
            contextRelevant: true,
            userActive: true,
            communicationNeeded: true
          },
          enabled: true,
          metadata: { aiProactive: true, contextAware: true }
        }
      ],
      variables: {
        communicationContext: {},
        routingDecisions: {},
        executionResults: {},
        learningData: {}
      },
      settings: {
        timeout: 60000,
        retryPolicy: {
          maxAttempts: 2,
          delay: 2000
        },
        priority: "high",
        parallelExecution: true
      },
      integrations: ["slack", "teams", "gmail", "asana"],
      tags: ["communication", "ai-powered", "orchestration", "intelligent_routing"],
      createdAt: new Date(),
      updatedAt: new Date(),
      enabled: true
    };

    // Template 4: Content & File Management Automation
    const contentFileManagementTemplate: WorkflowDefinition = {
      id: "content-file-management",
      name: "Auto-Archive & Task Linker",
      description: "Automatically archive, tag, and link new files from cloud storage to related tasks with intelligent context extraction",
      version: "1.0.0",
      category: "data_management",
      steps: [
        {
          id: "analyze-file-content",
          name: "Analyze File Content & Context",
          type: "data_transform",
          parameters: {
            extractionFields: ["project_name", "task_id", "keywords", "importance"],
            aiVisionEnabled: true,
            contextAwareness: "high"
          },
          dependsOn: [],
          retryPolicy: {
            maxAttempts: 3,
            delay: 1000,
            backoffMultiplier: 1.5
          },
          timeout: 20000,
          metadata: { aiPowered: true, model: "vision-analyzer-v1" }
        },
        {
          id: "identify-related-tasks",
          name: "Identify & Map to Related Tasks",
          type: "condition",
          parameters: {
            platforms: ["asana", "trello", "jira"],
            matchLogic: "semantic_similarity",
            confidenceThreshold: 0.8
          },
          dependsOn: ["analyze-file-content"],
          retryPolicy: {
            maxAttempts: 2,
            delay: 500,
            backoffMultiplier: 1.5
          },
          timeout: 10000,
          condition: {
            field: "task_mapping",
            operator: "ai_optimized",
            value: "contextual_linking"
          },
          metadata: { aiMatching: true }
        },
        {
          id: "execute-storage-organization",
          name: "Execute Storage Organization & Archiving",
          type: "integration_action",
          integrationId: "google_drive",
          action: "move_and_tag_file",
          parameters: {
            targetPath: "/Archive/{{extracted.project_name}}/{{current_year}}",
            tags: "predicted.tags",
            applyMetadata: true
          },
          dependsOn: ["identify-related-tasks"],
          retryPolicy: {
            maxAttempts: 3,
            delay: 2000,
            backoffMultiplier: 2
          },
          timeout: 15000,
          metadata: { platform: "google_drive", autoArchive: true }
        },
        {
          id: "send-team-notification",
          name: "Send Multi-Platform Notification",
          type: "integration_action",
          integrationId: "slack",
          action: "send_message",
          parameters: {
            channel: "extracted.project_channel",
            messageTemplate: "file_auto_linked",
            mentions: ["@project-team"]
          },
          dependsOn: ["execute-storage-organization"],
          retryPolicy: {
            maxAttempts: 2,
            delay: 1000,
            backoffMultiplier: 1.5
          },
          timeout: 8000,
          metadata: { platform: "slack", notification: true }
        }
      ],
      triggers: [
        {
          id: "new-file-trigger",
          type: "integration_event",
          integrationId: "google_drive",
          eventType: "new_file",
          enabled: true,
          metadata: { aiMonitoring: true }
        },
        {
          id: "manual-link-trigger",
          type: "manual",
          enabled: true,
          metadata: { uiShortcut: true }
        }
      ],
      variables: {
        fileMetadata: {},
        extractedContext: {},
        mappedTasks: {},
        archivingResults: {}
      },
      settings: {
        timeout: 60000,
        retryPolicy: {
          maxAttempts: 3,
          delay: 5000
        },
        priority: "normal",
        parallelExecution: false
      },
      integrations: ["google_drive", "dropbox", "asana", "trello", "slack"],
      tags: ["data-management", "ai-powered", "archiving", "automation"],
      createdAt: new Date(),
      updatedAt: new Date(),
      enabled: true
    };

    // Register templates with engine
    this.engine.registerWorkflow(crossPlatformTaskTemplate);
    this.engine.registerWorkflow(unifiedSearchTemplate);
    this.engine.registerWorkflow(communicationOrchestrationTemplate);
    this.engine.registerWorkflow(contentFileManagementTemplate);

    // Store template metadata
    this.templates.set("cross-platform-task-creation", {
      id: "cross-platform-task-creation",
      name: "Universal Task Creation & Synchronization",
      description: "Create tasks across all project management platforms with automatic sync",
      category: "productivity",
      targetIntegrations: ["asana", "trello", "slack", "jira", "monday"],
      aiOptimizations: {
        autoRouting: true,
        predictiveExecution: true,
        errorReduction: true,
        performanceOptimization: true
      },
      userPersonalization: {
        adaptToUserBehavior: true,
        learnFromUsage: true,
        customizeInterface: true
      },
      estimatedTimeSavings: "45 minutes per day",
      complexity: "moderate",
      prerequisites: ["asana_integration", "trello_integration", "slack_integration"]
    });

    this.templates.set("unified-cross-platform-search", {
      id: "unified-cross-platform-search",
      name: "Universal Search & Intelligence Aggregation",
      description: "Search across all connected platforms with AI-powered result aggregation",
      category: "data_management",
      targetIntegrations: ["google_drive", "slack", "asana", "gmail", "notion", "sharepoint"],
      aiOptimizations: {
        autoRouting: true,
        predictiveExecution: true,
        errorReduction: true,
        performanceOptimization: true
      },
      userPersonalization: {
        adaptToUserBehavior: true,
        learnFromUsage: true,
        customizeInterface: true
      },
      estimatedTimeSavings: "30 minutes per search",
      complexity: "advanced",
      prerequisites: ["at_least_3_integrations"]
    });

    this.templates.set("ai-communication-orchestration", {
      id: "ai-communication-orchestration",
      name: "Intelligent Cross-Platform Communication Management",
      description: "AI-powered communication orchestration with intelligent routing",
      category: "communication",
      targetIntegrations: ["slack", "teams", "gmail", "asana"],
      aiOptimizations: {
        autoRouting: true,
        predictiveExecution: true,
        errorReduction: true,
        performanceOptimization: true
      },
      userPersonalization: {
        adaptToUserBehavior: true,
        learnFromUsage: true,
        customizeInterface: true
      },
      estimatedTimeSavings: "25 minutes per day",
      complexity: "moderate",
      prerequisites: ["communication_integrations", "ai_context_analysis"]
    });

    this.templates.set("content-file-management", {
      id: "content-file-management",
      name: "Auto-Archive & Task Linker",
      description: "AI-powered cloud storage organization and task linking automation",
      category: "data_management",
      targetIntegrations: ["google_drive", "dropbox", "asana", "trello", "slack"],
      aiOptimizations: {
        autoRouting: true,
        predictiveExecution: true,
        errorReduction: true,
        performanceOptimization: true
      },
      userPersonalization: {
        adaptToUserBehavior: true,
        learnFromUsage: true,
        customizeInterface: true
      },
      estimatedTimeSavings: "35 minutes per day",
      complexity: "moderate",
      prerequisites: ["storage_integrations", "task_management_integrations"]
    });

    this.logger.info("AI Workflow Templates initialized with 4 intelligent templates");
  }

  private startAIOptimization(): void {
    // Start AI optimization loop
    setInterval(() => {
      this.analyzeWorkflowPerformance();
      this.generateAIInsights();
      this.optimizeWorkflows();
    }, 60000); // Run every minute

    this.logger.info("AI Optimization system started");
  }

  private analyzeWorkflowPerformance(): void {
    for (const [workflowId, executions] of this.performanceData.entries()) {
      if (executions.length < 5) continue; // Need minimum data

      const recentExecutions = executions.slice(-20); // Analyze last 20 executions
      const avgExecutionTime = recentExecutions.reduce((sum, exec) => sum + exec.duration, 0) / recentExecutions.length;
      const successRate = recentExecutions.filter(exec => exec.success).length / recentExecutions.length;

      // Store performance metrics
      const metrics = {
        workflowId,
        averageExecutionTime: avgExecutionTime,
        successRate,
        sampleSize: recentExecutions.length,
        lastAnalyzed: new Date()
      };

      // Generate insights if performance is below threshold
      if (avgExecutionTime > 30000) { // 30 seconds threshold
        this.generatePerformanceInsight(workflowId, {
          type: 'performance',
          confidence: 0.8,
          message: `Workflow execution is slow (avg ${avgExecutionTime}ms)`,
          suggestedAction: 'Consider optimizing parallel steps or reducing timeouts',
          impact: 'high'
        });
      }

      if (successRate < 0.9) { // 90% success rate threshold
        this.generatePerformanceInsight(workflowId, {
          type: 'error_prediction',
          confidence: 0.85,
          message: `Workflow success rate is low (${(successRate * 100).toFixed(1)}%)`,
          suggestedAction: 'Review error logs and add retry mechanisms',
          impact: 'high'
        });
      }
    }
  }

  private generateAIInsights(): void {
    for (const [workflowId, workflow] of this.workflows.entries()) {
      const insights: AIWorkflowInsight[] = [];

      // Usage pattern insights
      const userWorkflows = Array.from(this.userWorkflows.entries());
      const usageCount = userWorkflows.filter(([_, workflows]) =>
        workflows.includes(workflowId)
      ).length;

      if (usageCount === 0) {
        insights.push({
          type: 'usage_pattern',
          confidence: 0.9,
          message: 'This workflow has not been used by any users',
          suggestedAction: 'Promote this workflow or simplify it for better adoption',
          impact: 'medium'
        });
      }

      // Store insights
      this.aiInsights.set(workflowId, insights);
    }
  }

  private optimizeWorkflows(): void {
    for (const [workflowId, insights] of this.aiInsights.entries()) {
      const highImpactInsights = insights.filter(insight => insight.impact === 'high');

      if (highImpactInsights.length >= 2) {
        // Auto-optimize workflow if multiple high-impact issues
        this.autoOptimizeWorkflow(workflowId);
      }
    }
  }

  private autoOptimizeWorkflow(workflowId: string): void {
    const workflow = this.workflows.get(workflowId);
    if (!workflow) return;

    try {
      // Apply automatic optimizations
      const optimizations = [
        'increase_parallel_execution',
        'adjust_timeout_values',
        'enhance_error_handling',
        'optimize_step_order'
      ];

      for (const optimization of optimizations) {
        this.applyOptimization(workflow, optimization);
      }

      workflow.updatedAt = new Date();
      this.engine.registerWorkflow(workflow);

      this.logger.info(`Auto-optimized workflow: ${workflowId} with ${optimizations.length} optimizations`);
      this.emit("workflow-auto-optimized", { workflowId, optimizations });

    } catch (error) {
      this.logger.error(`Failed to auto-optimize workflow ${workflowId}:`, error);
    }
  }

  private applyOptimization(workflow: WorkflowDefinition, optimization: string): void {
    switch (optimization) {
      case 'increase_parallel_execution':
        workflow.settings.parallelExecution = true;
        // Increase parallel steps
        workflow.steps.forEach(step => {
          if (step.type === 'integration_action') {
            step.timeout = Math.min(step.timeout * 0.8, 30000); // Reduce timeout by 20%
          }
        });
        break;

      case 'adjust_timeout_values':
        workflow.settings.timeout = workflow.settings.timeout * 1.5;
        workflow.steps.forEach(step => {
          step.timeout = Math.min(step.timeout * 1.2, 60000); // Increase timeout by 20%
        });
        break;

      case 'enhance_error_handling':
        workflow.steps.forEach(step => {
          step.retryPolicy.maxAttempts = Math.min(step.retryPolicy.maxAttempts + 1, 5);
          step.retryPolicy.delay = step.retryPolicy.delay * 1.5;
        });
        break;

      case 'optimize_step_order':
        // Reorder steps for optimal execution
        workflow.steps.sort((a, b) => {
          // Prioritize integration actions first
          if (a.type === 'integration_action' && b.type !== 'integration_action') return -1;
          if (b.type === 'integration_action' && a.type !== 'integration_action') return 1;
          return 0;
        });
        break;
    }
  }

  private generatePerformanceInsight(workflowId: string, insight: AIWorkflowInsight): void {
    const insights = this.aiInsights.get(workflowId) || [];
    insights.push(insight);
    this.aiInsights.set(workflowId, insights);

    this.emit("workflow-insight-generated", { workflowId, insight });
    this.logger.info(`Generated insight for workflow ${workflowId}: ${insight.message}`);
  }

  // Public API methods
  async deployWorkflowTemplate(templateId: string, userId: string, customizations?: any): Promise<string> {
    const template = this.templates.get(templateId);
    if (!template) {
      throw new Error(`Template not found: ${templateId}`);
    }

    try {
      const workflow = this.workflows.get(templateId);
      if (!workflow) {
        throw new Error(`Workflow definition not found: ${templateId}`);
      }

      // Apply customizations
      if (customizations) {
        this.applyCustomizations(workflow, customizations);
      }

      // Execute workflow
      const executionId = await this.engine.executeWorkflow(templateId, {
        userId,
        triggeredBy: 'template_deployment',
        templateId,
        customizations,
        timestamp: new Date()
      });

      // Track user workflow
      const userWorkflows = this.userWorkflows.get(userId) || [];
      userWorkflows.push(templateId);
      this.userWorkflows.set(userId, userWorkflows);

      this.logger.info(`Deployed workflow template ${templateId} for user ${userId}`);
      return executionId;

    } catch (error) {
      this.logger.error(`Failed to deploy workflow template ${templateId}:`, error);
      throw error;
    }
  }

  getWorkflowTemplates(): WorkflowTemplate[] {
    return Array.from(this.templates.values());
  }

  getWorkflowInsights(workflowId: string): AIWorkflowInsight[] {
    return this.aiInsights.get(workflowId) || [];
  }

  getUserWorkflows(userId: string): string[] {
    return this.userWorkflows.get(userId) || [];
  }

  private applyCustomizations(workflow: WorkflowDefinition, customizations: any): void {
    if (customizations.integrations) {
      workflow.integrations = customizations.integrations;
    }

    if (customizations.priority) {
      workflow.settings.priority = customizations.priority;
    }

    if (customizations.timeout) {
      workflow.settings.timeout = customizations.timeout;
    }

    if (customizations.stepCustomizations) {
      for (const [stepId, customization] of Object.entries(customizations.stepCustomizations)) {
        const step = workflow.steps.find(s => s.id === stepId);
        if (step) {
          Object.assign(step, customization);
        }
      }
    }
  }
}