import { EventEmitter } from "events";
import { MultiIntegrationWorkflowEngine, WorkflowDefinition, WorkflowExecution, IntegrationCapability } from "./MultiIntegrationWorkflowEngine";
import { Logger } from "../utils/logger";

/**
 * Enhanced Workflow Management Service
 * 
 * This service provides high-level workflow management capabilities including
 * workflow templates, AI-powered optimization, and comprehensive monitoring.
 */

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  definition: Omit<WorkflowDefinition, 'id' | 'createdAt' | 'updatedAt'>;
  parameters: WorkflowParameter[];
  integrations: string[];
  tags: string[];
  popularity: number;
  isPublic: boolean;
  createdBy: string;
  createdAt: Date;
}

export interface WorkflowParameter {
  name: string;
  type: 'string' | 'number' | 'boolean' | 'object' | 'array' | 'select' | 'multiselect';
  required: boolean;
  defaultValue?: any;
  description: string;
  validation?: {
    min?: number;
    max?: number;
    pattern?: string;
    options?: any[];
  };
}

export interface WorkflowInstance {
  id: string;
  templateId: string;
  name: string;
  description: string;
  workflowId: string;
  parameters: Record<string, any>;
  status: 'active' | 'inactive' | 'archived';
  schedule?: string; // Cron expression
  lastExecution?: Date;
  nextExecution?: Date;
  executionCount: number;
  successCount: number;
  errorCount: number;
  createdBy: string;
  createdAt: Date;
  updatedAt: Date;
}

export interface WorkflowExecutionRequest {
  workflowId: string;
  parameters?: Record<string, any>;
  triggeredBy: string;
  priority?: 'low' | 'normal' | 'high' | 'critical';
  timeout?: number;
  metadata?: Record<string, any>;
}

export interface WorkflowOptimization {
  workflowId: string;
  optimizations: Array<{
    type: 'parallel' | 'caching' | 'batching' | 'routing' | 'retry';
    description: string;
    impact: 'low' | 'medium' | 'high';
    estimatedImprovement: number; // percentage
    implementation: {
      steps: string[];
      changes: Record<string, any>;
    };
  }>;
  overallScore: number;
  recommendations: string[];
  autoApply: boolean;
}

export interface WorkflowMetrics {
  workflowId: string;
  timeRange: {
    start: Date;
    end: Date;
  };
  executions: {
    total: number;
    successful: number;
    failed: number;
    cancelled: number;
    averageDuration: number;
    successRate: number;
  };
  performance: {
    fastestExecution: number;
    slowestExecution: number;
    averageStepTime: number;
    bottleneckSteps: string[];
  };
  integrations: Array<{
    integrationId: string;
    usage: number;
    errorRate: number;
    averageResponseTime: number;
  }>;
  costs: {
    total: number;
    breakdown: Record<string, number>;
  };
  trends: Array<{
    date: string;
    executions: number;
    successRate: number;
    averageDuration: number;
  }>;
}

export interface WorkflowCategory {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  workflowCount: number;
  isSystem: boolean;
}

export interface WorkflowSearchFilters {
  category?: string;
  integration?: string;
  tags?: string[];
  status?: string;
  createdBy?: string;
  dateRange?: {
    start: Date;
    end: Date;
  };
  text?: string;
}

export interface WorkflowExport {
  workflow: WorkflowDefinition;
  instances: WorkflowInstance[];
  executions: WorkflowExecution[];
  analytics: any;
  exportedAt: Date;
  exportedBy: string;
  format: 'json' | 'yaml';
}

export class EnhancedWorkflowService extends EventEmitter {
  private workflowEngine: MultiIntegrationWorkflowEngine;
  private logger: Logger;
  private templates: Map<string, WorkflowTemplate>;
  private instances: Map<string, WorkflowInstance>;
  private categories: Map<string, WorkflowCategory>;
  private optimizations: Map<string, WorkflowOptimization>;
  private metrics: Map<string, WorkflowMetrics[]>;

  constructor(workflowEngine: MultiIntegrationWorkflowEngine) {
    super();
    this.workflowEngine = workflowEngine;
    this.logger = new Logger("EnhancedWorkflowService");
    this.templates = new Map();
    this.instances = new Map();
    this.categories = new Map();
    this.optimizations = new Map();
    this.metrics = new Map();

    this.initializeCategories();
    this.loadSystemTemplates();
    this.setupEventListeners();
  }

  private initializeCategories(): void {
    const defaultCategories: WorkflowCategory[] = [
      {
        id: 'automation',
        name: 'Automation',
        description: 'Automate repetitive tasks and processes',
        icon: '⚡',
        color: '#FF6B6B',
        workflowCount: 0,
        isSystem: true,
      },
      {
        id: 'integration',
        name: 'Integration',
        description: 'Connect and synchronize data between systems',
        icon: '🔗',
        color: '#4ECDC4',
        workflowCount: 0,
        isSystem: true,
      },
      {
        id: 'monitoring',
        name: 'Monitoring',
        description: 'Monitor systems and respond to events',
        icon: '📊',
        color: '#45B7D1',
        workflowCount: 0,
        isSystem: true,
      },
      {
        id: 'communication',
        name: 'Communication',
        description: 'Automate notifications and communications',
        icon: '💬',
        color: '#96CEB4',
        workflowCount: 0,
        isSystem: true,
      },
      {
        id: 'data_processing',
        name: 'Data Processing',
        description: 'Transform and process data workflows',
        icon: '🔄',
        color: '#FECA57',
        workflowCount: 0,
        isSystem: true,
      },
    ];

    for (const category of defaultCategories) {
      this.categories.set(category.id, category);
    }
  }

  private loadSystemTemplates(): void {
    const systemTemplates: WorkflowTemplate[] = [
      {
        id: 'sync-slack-notion',
        name: 'Sync Slack Messages to Notion',
        description: 'Automatically sync important Slack messages to a Notion database',
        category: 'integration',
        definition: {
          name: 'Slack to Notion Sync',
          description: 'Sync Slack messages to Notion database',
          version: '1.0.0',
          category: 'integration',
          steps: [
            {
              id: 'listen-slack',
              name: 'Listen to Slack Messages',
              type: 'integration_action',
              integrationId: 'slack',
              action: 'listen_messages',
              parameters: {
                channel: '{{channel}}',
                keywords: '{{keywords}}',
              },
              dependsOn: [],
              retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
              timeout: 30000,
              metadata: {},
            },
            {
              id: 'filter-messages',
              name: 'Filter Important Messages',
              type: 'condition',
              parameters: {
                condition: {
                  field: 'message.importance',
                  operator: 'gte',
                  value: 0.7,
                },
              },
              dependsOn: ['listen-slack'],
              retryPolicy: { maxAttempts: 1, delay: 1000, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
            {
              id: 'transform-data',
              name: 'Transform for Notion',
              type: 'data_transform',
              parameters: {
                transformType: 'map_fields',
                mapping: {
                  'title': 'message.text',
                  'content': 'message.content',
                  'author': 'message.user.name',
                  'timestamp': 'message.timestamp',
                },
              },
              dependsOn: ['filter-messages'],
              retryPolicy: { maxAttempts: 2, delay: 500, backoffMultiplier: 1.5 },
              timeout: 10000,
              metadata: {},
            },
            {
              id: 'create-notion-page',
              name: 'Create Notion Page',
              type: 'integration_action',
              integrationId: 'notion',
              action: 'create_page',
              parameters: {
                databaseId: '{{notionDatabaseId}}',
                properties: '{{transformedData}}',
              },
              dependsOn: ['transform-data'],
              retryPolicy: { maxAttempts: 3, delay: 2000, backoffMultiplier: 2 },
              timeout: 30000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'slack-trigger',
              type: 'integration_event',
              integrationId: 'slack',
              eventType: 'message_received',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {},
          settings: {
            timeout: 120000,
            retryPolicy: { maxAttempts: 3, delay: 5000 },
            priority: 'normal',
            parallelExecution: false,
          },
          integrations: ['slack', 'notion'],
          tags: ['slack', 'notion', 'sync', 'automation'],
          enabled: true,
        },
        parameters: [
          {
            name: 'channel',
            type: 'string',
            required: true,
            description: 'Slack channel to monitor',
          },
          {
            name: 'keywords',
            type: 'array',
            required: false,
            defaultValue: [],
            description: 'Keywords to filter messages',
          },
          {
            name: 'notionDatabaseId',
            type: 'string',
            required: true,
            description: 'Notion database ID for sync',
          },
        ],
        integrations: ['slack', 'notion'],
        tags: ['slack', 'notion', 'sync'],
        popularity: 85,
        isPublic: true,
        createdBy: 'system',
        createdAt: new Date(),
      },
      {
        id: 'github-jira-sync',
        name: 'GitHub to Jira Issue Sync',
        description: 'Sync GitHub issues and pull requests to Jira tickets',
        category: 'integration',
        definition: {
          name: 'GitHub Jira Sync',
          description: 'Sync GitHub issues to Jira tickets',
          version: '1.0.0',
          category: 'integration',
          steps: [
            {
              id: 'listen-github',
              name: 'Listen to GitHub Events',
              type: 'integration_action',
              integrationId: 'github',
              action: 'listen_webhook',
              parameters: {
                events: ['issues', 'pull_request'],
                repository: '{{repository}}',
              },
              dependsOn: [],
              retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
              timeout: 30000,
              metadata: {},
            },
            {
              id: 'transform-github-data',
              name: 'Transform GitHub Data for Jira',
              type: 'data_transform',
              parameters: {
                transformType: 'map_fields',
                mapping: {
                  'summary': 'issue.title',
                  'description': 'issue.body',
                  'priority': 'issue.labels',
                  'assignee': 'issue.assignee.login',
                },
              },
              dependsOn: ['listen-github'],
              retryPolicy: { maxAttempts: 2, delay: 500, backoffMultiplier: 1.5 },
              timeout: 10000,
              metadata: {},
            },
            {
              id: 'create-jira-ticket',
              name: 'Create Jira Ticket',
              type: 'integration_action',
              integrationId: 'jira',
              action: 'create_issue',
              parameters: {
                project: '{{jiraProject}}',
                issueType: '{{issueType}}',
                fields: '{{transformedData}}',
              },
              dependsOn: ['transform-github-data'],
              retryPolicy: { maxAttempts: 3, delay: 2000, backoffMultiplier: 2 },
              timeout: 30000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'github-webhook',
              type: 'webhook',
              webhookPath: '/webhooks/github',
              enabled: true,
              metadata: {},
            },
          ],
          variables: {},
          settings: {
            timeout: 120000,
            retryPolicy: { maxAttempts: 3, delay: 5000 },
            priority: 'normal',
            parallelExecution: false,
          },
          integrations: ['github', 'jira'],
          tags: ['github', 'jira', 'sync', 'development'],
          enabled: true,
        },
        parameters: [
          {
            name: 'repository',
            type: 'string',
            required: true,
            description: 'GitHub repository to monitor',
          },
          {
            name: 'jiraProject',
            type: 'string',
            required: true,
            description: 'Jira project key',
          },
          {
            name: 'issueType',
            type: 'select',
            required: true,
            defaultValue: 'Task',
            description: 'Jira issue type to create',
            validation: {
              options: ['Task', 'Bug', 'Story', 'Epic'],
            },
          },
        ],
        integrations: ['github', 'jira'],
        tags: ['github', 'jira', 'development'],
        popularity: 92,
        isPublic: true,
        createdBy: 'system',
        createdAt: new Date(),
      },
      {
        id: 'health-monitor-alert',
        name: 'System Health Monitor & Alert',
        description: 'Monitor system health and send alerts when issues are detected',
        category: 'monitoring',
        definition: {
          name: 'Health Monitor Alert',
          description: 'Monitor system health and send alerts',
          version: '1.0.0',
          category: 'monitoring',
          steps: [
            {
              id: 'check-health',
              name: 'Check System Health',
              type: 'integration_action',
              integrationId: 'system',
              action: 'health_check',
              parameters: {
                services: '{{services}}',
                threshold: '{{threshold}}',
              },
              dependsOn: [],
              retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
              timeout: 30000,
              metadata: {},
            },
            {
              id: 'evaluate-health',
              name: 'Evaluate Health Results',
              type: 'condition',
              parameters: {
                condition: {
                  field: 'health.overall',
                  operator: 'lt',
                  value: 0.8,
                },
              },
              dependsOn: ['check-health'],
              retryPolicy: { maxAttempts: 1, delay: 1000, backoffMultiplier: 1 },
              timeout: 5000,
              metadata: {},
            },
            {
              id: 'send-alert',
              name: 'Send Alert Notification',
              type: 'notification',
              parameters: {
                type: '{{alertType}}',
                recipients: '{{recipients}}',
                message: 'System health degraded: {{health.overall}}%',
              },
              dependsOn: ['evaluate-health'],
              retryPolicy: { maxAttempts: 3, delay: 2000, backoffMultiplier: 2 },
              timeout: 15000,
              metadata: {},
            },
          ],
          triggers: [
            {
              id: 'scheduled-health-check',
              type: 'scheduled',
              schedule: '*/5 * * * *', // Every 5 minutes
              enabled: true,
              metadata: {},
            },
          ],
          variables: {},
          settings: {
            timeout: 60000,
            retryPolicy: { maxAttempts: 2, delay: 3000 },
            priority: 'high',
            parallelExecution: false,
          },
          integrations: ['system'],
          tags: ['monitoring', 'health', 'alerts'],
          enabled: true,
        },
        parameters: [
          {
            name: 'services',
            type: 'array',
            required: true,
            defaultValue: ['api', 'database', 'cache'],
            description: 'Services to monitor',
          },
          {
            name: 'threshold',
            type: 'number',
            required: false,
            defaultValue: 0.8,
            description: 'Health threshold (0-1)',
            validation: {
              min: 0,
              max: 1,
            },
          },
          {
            name: 'alertType',
            type: 'select',
            required: true,
            defaultValue: 'email',
            description: 'Alert notification type',
            validation: {
              options: ['email', 'slack', 'teams', 'sms'],
            },
          },
          {
            name: 'recipients',
            type: 'array',
            required: true,
            description: 'Alert recipients',
          },
        ],
        integrations: ['system'],
        tags: ['monitoring', 'health', 'alerts'],
        popularity: 78,
        isPublic: true,
        createdBy: 'system',
        createdAt: new Date(),
      },
    ];

    for (const template of systemTemplates) {
      this.templates.set(template.id, template);
    }

    this.logger.info(`Loaded ${systemTemplates.length} system templates`);
  }

  private setupEventListeners(): void {
    this.workflowEngine.on('workflow-execution-completed', (data) => {
      this.handleWorkflowExecutionCompleted(data);
    });

    this.workflowEngine.on('workflow-execution-failed', (data) => {
      this.handleWorkflowExecutionFailed(data);
    });

    this.workflowEngine.on('integration-health-changed', (data) => {
      this.handleIntegrationHealthChanged(data);
    });
  }

  // Template Management
  async createTemplate(template: Omit<WorkflowTemplate, 'id' | 'createdAt' | 'popularity'>): Promise<string> {
    const templateId = `template_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const newTemplate: WorkflowTemplate = {
      ...template,
      id: templateId,
      popularity: 0,
      createdAt: new Date(),
    };

    this.templates.set(templateId, newTemplate);
    
    // Update category count
    const category = this.categories.get(template.category);
    if (category) {
      category.workflowCount++;
    }

    this.logger.info(`Template created: ${newTemplate.name} (${templateId})`);
    this.emit("template-created", { templateId, name: newTemplate.name });

    return templateId;
  }

  async getTemplate(templateId: string): Promise<WorkflowTemplate | null> {
    return this.templates.get(templateId) || null;
  }

  async listTemplates(filters?: WorkflowSearchFilters): Promise<WorkflowTemplate[]> {
    let templates = Array.from(this.templates.values());

    if (filters) {
      if (filters.category) {
        templates = templates.filter(t => t.category === filters.category);
      }
      if (filters.integration) {
        templates = templates.filter(t => t.integrations.includes(filters.integration));
      }
      if (filters.tags && filters.tags.length > 0) {
        templates = templates.filter(t => 
          filters.tags!.some(tag => t.tags.includes(tag))
        );
      }
      if (filters.text) {
        const searchLower = filters.text.toLowerCase();
        templates = templates.filter(t =>
          t.name.toLowerCase().includes(searchLower) ||
          t.description.toLowerCase().includes(searchLower)
        );
      }
    }

    return templates.sort((a, b) => b.popularity - a.popularity);
  }

  async updateTemplate(templateId: string, updates: Partial<WorkflowTemplate>): Promise<boolean> {
    const template = this.templates.get(templateId);
    if (!template) {
      return false;
    }

    Object.assign(template, updates);
    this.templates.set(templateId, template);
    
    this.logger.info(`Template updated: ${template.name} (${templateId})`);
    this.emit("template-updated", { templateId, name: template.name });

    return true;
  }

  async deleteTemplate(templateId: string): Promise<boolean> {
    const template = this.templates.get(templateId);
    if (!template) {
      return false;
    }

    this.templates.delete(templateId);
    
    // Update category count
    const category = this.categories.get(template.category);
    if (category) {
      category.workflowCount--;
    }

    this.logger.info(`Template deleted: ${template.name} (${templateId})`);
    this.emit("template-deleted", { templateId, name: template.name });

    return true;
  }

  // Instance Management
  async createInstance(
    templateId: string,
    name: string,
    description: string,
    parameters: Record<string, any>,
    createdBy: string
  ): Promise<string> {
    const template = this.templates.get(templateId);
    if (!template) {
      throw new Error(`Template ${templateId} not found`);
    }

    const workflowDefinition: WorkflowDefinition = {
      ...template.definition,
      id: `workflow_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    // Register workflow with engine
    await this.workflowEngine.registerWorkflow(workflowDefinition);

    const instanceId = `instance_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const instance: WorkflowInstance = {
      id: instanceId,
      templateId,
      name,
      description,
      workflowId: workflowDefinition.id,
      parameters,
      status: 'active',
      executionCount: 0,
      successCount: 0,
      errorCount: 0,
      createdBy,
      createdAt: new Date(),
      updatedAt: new Date(),
    };

    this.instances.set(instanceId, instance);
    
    this.logger.info(`Instance created: ${name} (${instanceId})`);
    this.emit("instance-created", { instanceId, name, workflowId: workflowDefinition.id });

    return instanceId;
  }

  async getInstance(instanceId: string): Promise<WorkflowInstance | null> {
    return this.instances.get(instanceId) || null;
  }

  async listInstances(workflowId?: string, status?: string): Promise<WorkflowInstance[]> {
    let instances = Array.from(this.instances.values());

    if (workflowId) {
      instances = instances.filter(i => i.workflowId === workflowId);
    }
    if (status) {
      instances = instances.filter(i => i.status === status);
    }

    return instances.sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime());
  }

  async executeInstance(
    instanceId: string,
    triggeredBy: string,
    overrideParameters?: Record<string, any>
  ): Promise<string> {
    const instance = this.instances.get(instanceId);
    if (!instance) {
      throw new Error(`Instance ${instanceId} not found`);
    }

    if (instance.status !== 'active') {
      throw new Error(`Instance ${instanceId} is not active`);
    }

    const executionParameters = {
      ...instance.parameters,
      ...overrideParameters,
    };

    const executionId = await this.workflowEngine.executeWorkflow(
      instance.workflowId,
      triggeredBy,
      executionParameters
    );

    // Update instance stats
    instance.executionCount++;
    instance.lastExecution = new Date();
    instance.updatedAt = new Date();

    this.emit("instance-executed", { instanceId, executionId });
    return executionId;
  }

  // Workflow Optimization
  async optimizeWorkflow(workflowId: string): Promise<WorkflowOptimization> {
    const analytics = await this.workflowEngine.getWorkflowAnalytics(workflowId);
    const workflow = this.workflowEngine.getRegisteredWorkflows().find(w => w.id === workflowId);
    
    if (!workflow || !analytics) {
      throw new Error(`Workflow ${workflowId} not found or no analytics available`);
    }

    const optimizations = this.generateOptimizations(workflow, analytics);
    const overallScore = this.calculateOptimizationScore(optimizations);
    const recommendations = this.generateRecommendations(workflow, analytics, optimizations);

    const optimization: WorkflowOptimization = {
      workflowId,
      optimizations,
      overallScore,
      recommendations,
      autoApply: false,
    };

    this.optimizations.set(workflowId, optimization);
    this.emit("workflow-optimized", { workflowId, overallScore });

    return optimization;
  }

  private generateOptimizations(workflow: WorkflowDefinition, analytics: any): any[] {
    const optimizations = [];

    // Parallel execution optimization
    const parallelizableSteps = this.findParallelizableSteps(workflow.steps);
    if (parallelizableSteps.length > 1) {
      optimizations.push({
        type: 'parallel',
        description: `Execute ${parallelizableSteps.length} steps in parallel`,
        impact: 'high',
        estimatedImprovement: Math.min((parallelizableSteps.length - 1) * 25, 60),
        implementation: {
          steps: parallelizableSteps.map(s => s.id),
          changes: {
            type: 'parallel_group',
            steps: parallelizableSteps,
          },
        },
      });
    }

    // Caching optimization
    const cacheableSteps = workflow.steps.filter(step => 
      step.type === 'integration_action' && 
      !step.parameters.freshness
    );
    if (cacheableSteps.length > 0) {
      optimizations.push({
        type: 'caching',
        description: `Cache results for ${cacheableSteps.length} integration calls`,
        impact: 'medium',
        estimatedImprovement: cacheableSteps.length * 15,
        implementation: {
          steps: cacheableSteps.map(s => s.id),
          changes: {
            enableCaching: true,
            cacheTtl: 300, // 5 minutes
          },
        },
      });
    }

    // Retry optimization
    const failedSteps = analytics.commonFailurePoints || [];
    if (failedSteps.length > 0) {
      optimizations.push({
        type: 'retry',
        description: `Improve retry logic for ${failedSteps.length} frequently failing steps`,
        impact: 'medium',
        estimatedImprovement: failedSteps.length * 20,
        implementation: {
          steps: failedSteps.map(fp => fp.stepId),
          changes: {
            retryPolicy: {
              maxAttempts: 5,
              delay: 2000,
              backoffMultiplier: 2,
              exponentialBackoff: true,
            },
          },
        },
      });
    }

    return optimizations;
  }

  private findParallelizableSteps(steps: any[]): any[] {
    // Find steps that don't depend on each other
    const parallelizable: any[] = [];
    const dependencies = new Map<string, string[]>();

    for (const step of steps) {
      dependencies.set(step.id, step.dependsOn || []);
    }

    // Simple algorithm: steps with no dependencies on each other can run in parallel
    for (const step of steps) {
      const canRunInParallel = steps.every(otherStep =>
        otherStep.id === step.id ||
        !step.dependsOn.includes(otherStep.id) ||
        !otherStep.dependsOn.includes(step.id)
      );

      if (canRunInParallel && step.type !== 'condition') {
        parallelizable.push(step);
      }
    }

    return parallelizable;
  }

  private calculateOptimizationScore(optimizations: any[]): number {
    if (optimizations.length === 0) return 0;

    const totalImprovement = optimizations.reduce((sum, opt) => sum + opt.estimatedImprovement, 0);
    const averageImpact = optimizations.reduce((sum, opt) => {
      const impactScore = opt.impact === 'high' ? 3 : opt.impact === 'medium' ? 2 : 1;
      return sum + impactScore;
    }, 0) / optimizations.length;

    return Math.min(Math.round((totalImprovement * averageImpact) / 10), 100);
  }

  private generateRecommendations(workflow: WorkflowDefinition, analytics: any, optimizations: any[]): string[] {
    const recommendations = [];

    if (analytics.successRate < 0.9) {
      recommendations.push("Consider improving error handling and adding monitoring for failed executions");
    }

    if (analytics.averageExecutionTime > 60000) {
      recommendations.push("Workflow execution is slow - consider enabling parallel execution or optimizing integration calls");
    }

    if (workflow.settings.timeout < 120000) {
      recommendations.push("Consider increasing timeout for complex workflows with multiple integration calls");
    }

    if (optimizations.length > 0) {
      const highImpactOptimizations = optimizations.filter(opt => opt.impact === 'high');
      if (highImpactOptimizations.length > 0) {
        recommendations.push(`High-impact optimizations available that could improve performance by ${highImpactOptimizations.reduce((sum, opt) => sum + opt.estimatedImprovement, 0)}%`);
      }
    }

    return recommendations;
  }

  // Analytics and Metrics
  async getWorkflowMetrics(workflowId: string, timeRange: { start: Date; end: Date }): Promise<WorkflowMetrics> {
    // This would typically query a time-series database
    // For now, return mock metrics
    const metrics: WorkflowMetrics = {
      workflowId,
      timeRange,
      executions: {
        total: 150,
        successful: 135,
        failed: 12,
        cancelled: 3,
        averageDuration: 45000,
        successRate: 0.9,
      },
      performance: {
        fastestExecution: 15000,
        slowestExecution: 120000,
        averageStepTime: 7500,
        bottleneckSteps: ['step-3', 'step-7'],
      },
      integrations: [
        {
          integrationId: 'slack',
          usage: 150,
          errorRate: 0.02,
          averageResponseTime: 250,
        },
        {
          integrationId: 'notion',
          usage: 135,
          errorRate: 0.01,
          averageResponseTime: 450,
        },
      ],
      costs: {
        total: 12.50,
        breakdown: {
          'slack': 3.75,
          'notion': 8.75,
        },
      },
      trends: [
        {
          date: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          executions: 20,
          successRate: 0.95,
          averageDuration: 42000,
        },
        {
          date: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
          executions: 25,
          successRate: 0.88,
          averageDuration: 48000,
        },
      ],
    };

    return metrics;
  }

  // Event Handlers
  private handleWorkflowExecutionCompleted(data: any): void {
    // Update instance statistics
    const instance = Array.from(this.instances.values())
      .find(i => i.workflowId === data.workflowId);
    
    if (instance) {
      instance.successCount++;
      instance.updatedAt = new Date();
    }

    this.emit("workflow-completed", data);
  }

  private handleWorkflowExecutionFailed(data: any): void {
    // Update instance statistics
    const instance = Array.from(this.instances.values())
      .find(i => i.workflowId === data.workflowId);
    
    if (instance) {
      instance.errorCount++;
      instance.updatedAt = new Date();
    }

    this.emit("workflow-failed", data);
  }

  private handleIntegrationHealthChanged(data: any): void {
    // Handle integration health changes
    this.logger.warn(`Integration health changed: ${data.integrationId} is now ${data.isHealthy ? 'healthy' : 'unhealthy'}`);
    this.emit("integration-health-changed", data);
  }

  // Public API Methods
  async getCategories(): Promise<WorkflowCategory[]> {
    return Array.from(this.categories.values());
  }

  async getOptimizations(workflowId: string): Promise<WorkflowOptimization | null> {
    return this.optimizations.get(workflowId) || null;
  }

  async searchWorkflows(filters: WorkflowSearchFilters): Promise<WorkflowTemplate[]> {
    return this.listTemplates(filters);
  }

  async exportWorkflow(workflowId: string, format: 'json' | 'yaml' = 'json'): Promise<WorkflowExport> {
    const workflow = this.workflowEngine.getRegisteredWorkflows().find(w => w.id === workflowId);
    const instances = Array.from(this.instances.values()).filter(i => i.workflowId === workflowId);
    
    if (!workflow) {
      throw new Error(`Workflow ${workflowId} not found`);
    }

    const exportData: WorkflowExport = {
      workflow,
      instances,
      executions: [], // Would fetch actual executions
      analytics: await this.workflowEngine.getWorkflowAnalytics(workflowId),
      exportedAt: new Date(),
      exportedBy: 'user', // Would get from context
      format,
    };

    return exportData;
  }
}