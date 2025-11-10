import { EventEmitter } from "events";
import { Logger } from "../utils/logger";
import { v4 as uuidv4 } from "uuid";

/**
 * Multi-Integration Workflow Orchestration Engine
 * 
 * This engine coordinates complex workflows spanning multiple integrations,
 * providing intelligent routing, data transformation, and cross-platform
 * automation capabilities.
 */

export interface IntegrationCapability {
  id: string;
  name: string;
  integrationType: string;
  supportedActions: string[];
  supportedTriggers: string[];
  rateLimit: {
    requestsPerSecond: number;
    requestsPerHour: number;
  };
  requiresAuth: boolean;
  authType: 'oauth' | 'api_key' | 'basic' | 'none';
  healthStatus: 'healthy' | 'degraded' | 'unhealthy';
  lastHealthCheck: Date;
  metadata: Record<string, any>;
}

export interface IntegrationState {
  integrationId: string;
  isAvailable: boolean;
  isConnected: boolean;
  lastUsed: Date;
  usageCount: number;
  errorCount: number;
  rateLimitRemaining: number;
  rateLimitReset: Date;
  configuration: Record<string, any>;
  metrics: {
    averageResponseTime: number;
    successRate: number;
    totalRequests: number;
    errorRate: number;
  };
}

export interface WorkflowStep {
  id: string;
  name: string;
  type: 'integration_action' | 'data_transform' | 'condition' | 'parallel' | 'wait' | 'webhook' | 'notification' | 'ai_task' | 'advanced_branch';
  integrationId?: string;
  action?: string;
  parameters: Record<string, any>;
  dependsOn: string[];
  retryPolicy: {
    maxAttempts: number;
    delay: number;
    backoffMultiplier: number;
  };
  timeout: number;
  condition?: {
    field: string;
    operator: string;
    value: any;
  };
  errorHandler?: string;
  metadata: Record<string, any>;
  // Enhanced branch properties
  branchConfiguration?: {
    conditionType: 'field' | 'expression' | 'ai';
    fieldPath?: string;
    operator?: string;
    value?: string;
    branches: Array<{
      id: string;
      label: string;
      condition?: any;
    }>;
  };
  // Enhanced AI properties
  aiConfiguration?: {
    aiType: 'custom' | 'prebuilt' | 'workflow' | 'decision';
    prompt: string;
    model: string;
    temperature: number;
    maxTokens: number;
    prebuiltTask?: string;
  };
}

export interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  version: string;
  category: string;
  steps: WorkflowStep[];
  triggers: WorkflowTrigger[];
  variables: Record<string, any>;
  settings: {
    timeout?: number;
    retryPolicy?: {
      maxAttempts: number;
      delay: number;
    };
    priority: 'low' | 'normal' | 'high' | 'critical';
    parallelExecution: boolean;
  };
  integrations: string[];
  tags: string[];
  createdAt: Date;
  updatedAt: Date;
  enabled: boolean;
}

export interface WorkflowTrigger {
  id: string;
  type: 'manual' | 'scheduled' | 'event' | 'webhook' | 'integration_event';
  integrationId?: string;
  eventType?: string;
  schedule?: string; // Cron expression
  condition?: Record<string, any>;
  webhookPath?: string;
  enabled: boolean;
  metadata: Record<string, any>;
}

export interface WorkflowExecution {
  id: string;
  workflowId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled' | 'paused' | 'retrying';
  startedAt: Date;
  completedAt?: Date;
  triggeredBy: string;
  triggerData: Record<string, any>;
  currentStep?: string;
  stepExecutions: Map<string, StepExecution>;
  variables: Record<string, any>;
  result?: any;
  error?: string;
  executionTime?: number;
  retryCount: number;
  metadata: Record<string, any>;
}

export interface StepExecution {
  stepId: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped' | 'retrying';
  startedAt?: Date;
  completedAt?: Date;
  input: Record<string, any>;
  output?: any;
  error?: string;
  executionTime?: number;
  retryCount: number;
  logs: string[];
  metrics: {
    integrationResponseTime?: number;
    dataTransformTime?: number;
    memoryUsage?: number;
  };
}

export interface DataTransformation {
  id: string;
  name: string;
  type: 'map_fields' | 'filter_fields' | 'aggregate' | 'calculate' | 'format' | 'lookup' | 'custom';
  config: Record<string, any>;
  script?: string; // For custom transformations
}

export interface IntegrationRoute {
  fromIntegration: string;
  toIntegration: string;
  dataMapping: Record<string, string>;
  transformations: DataTransformation[];
  conditions: Record<string, any>[];
  priority: number;
  enabled: boolean;
}

export interface WorkflowAnalytics {
  workflowId: string;
  totalExecutions: number;
  successfulExecutions: number;
  failedExecutions: number;
  averageExecutionTime: number;
  successRate: number;
  lastExecution?: Date;
  mostUsedIntegrations: Array<{
    integrationId: string;
    usageCount: number;
    successRate: number;
  }>;
  commonFailurePoints: Array<{
    stepId: string;
    errorCount: number;
    lastError: string;
  }>;
  performanceMetrics: {
    averageStepTime: number;
    bottleneckSteps: string[];
    optimalParallelism: number;
  };
  recommendations: string[];
}

export interface OrchestrationConfig {
  maxConcurrentExecutions: number;
  maxStepsPerExecution: number;
  defaultTimeout: number;
  defaultRetryAttempts: number;
  enableCaching: boolean;
  enableMetrics: boolean;
  enableOptimization: boolean;
  healthCheckInterval: number;
  integrationHealthThreshold: number;
  autoRetryFailures: boolean;
  logLevel: 'debug' | 'info' | 'warn' | 'error';
}

export class MultiIntegrationWorkflowEngine extends EventEmitter {
  private logger: Logger;
  private config: OrchestrationConfig;
  private integrations: Map<string, IntegrationCapability>;
  private integrationStates: Map<string, IntegrationState>;
  private workflows: Map<string, WorkflowDefinition>;
  private executions: Map<string, WorkflowExecution>;
  private routes: Map<string, IntegrationRoute>;
  private analytics: Map<string, WorkflowAnalytics>;
  private executionQueue: WorkflowExecution[];
  private activeExecutions: Map<string, WorkflowExecution>;
  private stepHandlers: Map<string, Function>;
  private transformers: Map<string, Function>;

  constructor(config: OrchestrationConfig) {
    super();
    this.logger = new Logger("MultiIntegrationWorkflowEngine");
    this.config = {
      maxConcurrentExecutions: 10,
      maxStepsPerExecution: 100,
      defaultTimeout: 300000, // 5 minutes
      defaultRetryAttempts: 3,
      enableCaching: true,
      enableMetrics: true,
      enableOptimization: true,
      healthCheckInterval: 60000, // 1 minute
      integrationHealthThreshold: 0.8,
      autoRetryFailures: true,
      logLevel: 'info',
      ...config,
    };

    this.integrations = new Map();
    this.integrationStates = new Map();
    this.workflows = new Map();
    this.executions = new Map();
    this.routes = new Map();
    this.analytics = new Map();
    this.executionQueue = [];
    this.activeExecutions = new Map();
    this.stepHandlers = new Map();
    this.transformers = new Map();

    this.initializeHandlers();
    this.startHealthMonitoring();
    this.startExecutionProcessor();
    
    this.logger.info("Multi-Integration Workflow Engine initialized");
  }

  private initializeHandlers(): void {
    // Initialize step handlers
    this.stepHandlers.set('integration_action', this.handleIntegrationAction.bind(this));
    this.stepHandlers.set('data_transform', this.handleDataTransform.bind(this));
    this.stepHandlers.set('condition', this.handleCondition.bind(this));
    this.stepHandlers.set('parallel', this.handleParallel.bind(this));
    this.stepHandlers.set('wait', this.handleWait.bind(this));
    this.stepHandlers.set('webhook', this.handleWebhook.bind(this));
    this.stepHandlers.set('notification', this.handleNotification.bind(this));
    this.stepHandlers.set('ai_task', this.handleAITask.bind(this));
    this.stepHandlers.set('advanced_branch', this.handleAdvancedBranch.bind(this));

    // Initialize data transformers
    this.transformers.set('map_fields', this.transformMapFields.bind(this));
    this.transformers.set('filter_fields', this.transformFilterFields.bind(this));
    this.transformers.set('aggregate', this.transformAggregate.bind(this));
    this.transformers.set('calculate', this.transformCalculate.bind(this));
    this.transformers.set('format', this.transformFormat.bind(this));
    this.transformers.set('lookup', this.transformLookup.bind(this));
    this.transformers.set('custom', this.transformCustom.bind(this));
  }

  // Integration Management
  async registerIntegration(capability: IntegrationCapability): Promise<void> {
    this.integrations.set(capability.id, capability);
    
    // Initialize integration state
    const state: IntegrationState = {
      integrationId: capability.id,
      isAvailable: true,
      isConnected: false,
      lastUsed: new Date(),
      usageCount: 0,
      errorCount: 0,
      rateLimitRemaining: capability.rateLimit.requestsPerHour,
      rateLimitReset: new Date(Date.now() + 3600000),
      configuration: {},
      metrics: {
        averageResponseTime: 0,
        successRate: 1.0,
        totalRequests: 0,
        errorRate: 0,
      },
    };
    
    this.integrationStates.set(capability.id, state);
    this.logger.info(`Integration registered: ${capability.name} (${capability.id})`);
    this.emit("integration-registered", { integrationId: capability.id, name: capability.name });
  }

  async unregisterIntegration(integrationId: string): Promise<void> {
    const integration = this.integrations.get(integrationId);
    if (integration) {
      this.integrations.delete(integrationId);
      this.integrationStates.delete(integrationId);
      this.logger.info(`Integration unregistered: ${integration.name} (${integrationId})`);
      this.emit("integration-unregistered", { integrationId, name: integration.name });
    }
  }

  async updateIntegrationState(integrationId: string, updates: Partial<IntegrationState>): Promise<void> {
    const state = this.integrationStates.get(integrationId);
    if (state) {
      Object.assign(state, updates);
      this.integrationStates.set(integrationId, state);
      this.emit("integration-state-updated", { integrationId, state });
    }
  }

  // Workflow Management
  async registerWorkflow(workflow: WorkflowDefinition): Promise<void> {
    // Validate workflow
    await this.validateWorkflow(workflow);
    
    this.workflows.set(workflow.id, workflow);
    
    // Initialize analytics
    const analytics: WorkflowAnalytics = {
      workflowId: workflow.id,
      totalExecutions: 0,
      successfulExecutions: 0,
      failedExecutions: 0,
      averageExecutionTime: 0,
      successRate: 0,
      mostUsedIntegrations: [],
      commonFailurePoints: [],
      performanceMetrics: {
        averageStepTime: 0,
        bottleneckSteps: [],
        optimalParallelism: 1,
      },
      recommendations: [],
    };
    
    this.analytics.set(workflow.id, analytics);
    this.logger.info(`Workflow registered: ${workflow.name} (${workflow.id})`);
    this.emit("workflow-registered", { workflowId: workflow.id, name: workflow.name });
  }

  async executeWorkflow(
    workflowId: string, 
    triggeredBy: string, 
    triggerData: Record<string, any> = {}
  ): Promise<string> {
    const workflow = this.workflows.get(workflowId);
    if (!workflow) {
      throw new Error(`Workflow ${workflowId} not found`);
    }

    if (!workflow.enabled) {
      throw new Error(`Workflow ${workflowId} is disabled`);
    }

    // Check integration availability
    for (const integrationId of workflow.integrations) {
      const state = this.integrationStates.get(integrationId);
      if (!state || !state.isAvailable) {
        throw new Error(`Integration ${integrationId} is not available`);
      }
    }

    const executionId = uuidv4();
    const execution: WorkflowExecution = {
      id: executionId,
      workflowId,
      status: 'pending',
      startedAt: new Date(),
      triggeredBy,
      triggerData,
      stepExecutions: new Map(),
      variables: { ...workflow.variables, ...triggerData },
      retryCount: 0,
      metadata: {},
    };

    this.executions.set(executionId, execution);
    this.executionQueue.push(execution);

    this.logger.info(`Workflow execution queued: ${workflowId} (${executionId})`);
    this.emit("workflow-execution-queued", { executionId, workflowId });

    return executionId;
  }

  // Route Management
  async registerRoute(route: IntegrationRoute): Promise<void> {
    const routeId = `${route.fromIntegration}->${route.toIntegration}`;
    this.routes.set(routeId, route);
    this.logger.info(`Route registered: ${routeId}`);
    this.emit("route-registered", { routeId, route });
  }

  async findOptimalRoute(fromIntegration: string, toIntegration: string, data: Record<string, any>): Promise<IntegrationRoute | null> {
    const routeId = `${fromIntegration}->${toIntegration}`;
    const directRoute = this.routes.get(routeId);
    
    if (directRoute && directRoute.enabled) {
      // Check if conditions are met
      if (this.evaluateRouteConditions(directRoute.conditions, data)) {
        return directRoute;
      }
    }

    // Find alternative routes
    const alternativeRoutes = Array.from(this.routes.values())
      .filter(route => 
        route.fromIntegration === fromIntegration && 
        route.toIntegration === toIntegration && 
        route.enabled &&
        this.evaluateRouteConditions(route.conditions, data)
      )
      .sort((a, b) => b.priority - a.priority);

    return alternativeRoutes.length > 0 ? alternativeRoutes[0] : null;
  }

  // Execution Processing
  private async startExecutionProcessor(): Promise<void> {
    setInterval(async () => {
      if (this.executionQueue.length > 0 && this.activeExecutions.size < this.config.maxConcurrentExecutions) {
        const execution = this.executionQueue.shift();
        if (execution) {
          this.activeExecutions.set(execution.id, execution);
          this.processExecution(execution).catch(error => {
            this.logger.error(`Execution processing failed: ${error}`, error);
          });
        }
      }
    }, 1000);
  }

  private async processExecution(execution: WorkflowExecution): Promise<void> {
    try {
      execution.status = 'running';
      this.emit("workflow-execution-started", { executionId: execution.id, workflowId: execution.workflowId });

      const workflow = this.workflows.get(execution.workflowId);
      if (!workflow) {
        throw new Error(`Workflow ${execution.workflowId} not found`);
      }

      // Process steps in dependency order
      const stepsInOrder = this.resolveStepDependencies(workflow.steps);
      
      for (const step of stepsInOrder) {
        if (execution.status === 'cancelled') {
          break;
        }

        await this.executeStep(execution, step, workflow);
      }

      if (execution.status === 'running') {
        execution.status = 'completed';
        execution.completedAt = new Date();
        execution.executionTime = execution.completedAt.getTime() - execution.startedAt.getTime();

        this.updateAnalytics(execution);
        this.logger.info(`Workflow execution completed: ${execution.id}`);
        this.emit("workflow-execution-completed", { executionId: execution.id });
      }
    } catch (error) {
      execution.status = 'failed';
      execution.error = error.message;
      execution.completedAt = new Date();
      execution.executionTime = execution.completedAt.getTime() - execution.startedAt.getTime();

      this.updateAnalytics(execution);
      this.logger.error(`Workflow execution failed: ${execution.id}`, error);
      this.emit("workflow-execution-failed", { executionId: execution.id, error });

      // Auto-retry if enabled
      if (this.config.autoRetryFailures && execution.retryCount < this.config.defaultRetryAttempts) {
        await this.retryExecution(execution);
      }
    } finally {
      this.activeExecutions.delete(execution.id);
    }
  }

  private async executeStep(
    execution: WorkflowExecution, 
    step: WorkflowStep, 
    workflow: WorkflowDefinition
  ): Promise<void> {
    const stepExecution: StepExecution = {
      stepId: step.id,
      status: 'pending',
      input: { ...execution.variables },
      logs: [],
      retryCount: 0,
      metrics: {},
    };

    execution.stepExecutions.set(step.id, stepExecution);
    execution.currentStep = step.id;

    // Check dependencies
    for (const depId of step.dependsOn) {
      const depExecution = execution.stepExecutions.get(depId);
      if (!depExecution || depExecution.status !== 'completed') {
        stepExecution.status = 'skipped';
        stepExecution.logs.push(`Skipped due to unmet dependency: ${depId}`);
        return;
      }
    }

    // Check condition if present
    if (step.condition) {
      const conditionMet = this.evaluateCondition(step.condition, execution.variables);
      if (!conditionMet) {
        stepExecution.status = 'skipped';
        stepExecution.logs.push(`Skipped due to unmet condition: ${JSON.stringify(step.condition)}`);
        return;
      }
    }

    stepExecution.status = 'running';
    stepExecution.startedAt = new Date();
    this.emit("step-execution-started", { executionId: execution.id, stepId: step.id });

    try {
      const handler = this.stepHandlers.get(step.type);
      if (!handler) {
        throw new Error(`No handler for step type: ${step.type}`);
      }

      const startTime = Date.now();
      const result = await this.executeWithRetry(
        () => handler(execution, step),
        step.retryPolicy,
        stepExecution
      );
      const endTime = Date.now();

      stepExecution.output = result;
      stepExecution.status = 'completed';
      stepExecution.completedAt = new Date();
      stepExecution.executionTime = endTime - startTime;

      // Update execution variables with step output
      if (result && typeof result === 'object') {
        Object.assign(execution.variables, result);
      }

      this.emit("step-execution-completed", { 
        executionId: execution.id, 
        stepId: step.id, 
        result,
        executionTime: stepExecution.executionTime
      });

    } catch (error) {
      stepExecution.status = 'failed';
      stepExecution.error = error.message;
      stepExecution.completedAt = new Date();
      
      this.logger.error(`Step execution failed: ${step.id}`, error);
      this.emit("step-execution-failed", { executionId: execution.id, stepId: step.id, error });

      // Handle error if error handler is specified
      if (step.errorHandler) {
        await this.handleStepError(execution, step, error);
      } else {
        throw error;
      }
    }
  }

  private async executeWithRetry<T>(
    fn: () => Promise<T>,
    retryPolicy: { maxAttempts: number; delay: number; backoffMultiplier: number },
    stepExecution: StepExecution
  ): Promise<T> {
    let lastError: Error;
    
    for (let attempt = 1; attempt <= retryPolicy.maxAttempts; attempt++) {
      try {
        return await fn();
      } catch (error) {
        lastError = error;
        stepExecution.retryCount = attempt;
        stepExecution.logs.push(`Attempt ${attempt} failed: ${error.message}`);
        
        if (attempt < retryPolicy.maxAttempts) {
          const delay = retryPolicy.delay * Math.pow(retryPolicy.backoffMultiplier, attempt - 1);
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }
    
    throw lastError;
  }

  // Step Handlers
  private async handleIntegrationAction(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    if (!step.integrationId || !step.action) {
      throw new Error('Integration action requires integrationId and action');
    }

    const integration = this.integrations.get(step.integrationId);
    const state = this.integrationStates.get(step.integrationId);
    
    if (!integration || !state) {
      throw new Error(`Integration ${step.integrationId} not found`);
    }

    if (!state.isAvailable || state.rateLimitRemaining <= 0) {
      throw new Error(`Integration ${step.integrationId} is not available or rate limited`);
    }

    // Update integration state
    state.lastUsed = new Date();
    state.usageCount++;

    // Simulate integration call (in real implementation, this would call the actual integration)
    const startTime = Date.now();
    
    // This would be replaced with actual integration API call
    const result = {
      success: true,
      integration: integration.name,
      action: step.action,
      parameters: step.parameters,
      timestamp: new Date().toISOString(),
      data: { /* Integration response data */ }
    };

    const endTime = Date.now();
    const responseTime = endTime - startTime;

    // Update metrics
    state.metrics.totalRequests++;
    state.metrics.averageResponseTime = 
      (state.metrics.averageResponseTime * (state.metrics.totalRequests - 1) + responseTime) / 
      state.metrics.totalRequests;

    state.rateLimitRemaining--;
    
    if (stepExecution => execution.stepExecutions.get(step.stepId)) {
      stepExecution.metrics.integrationResponseTime = responseTime;
    }

    this.emit("integration-action-completed", { 
      integrationId: step.integrationId, 
      action: step.action, 
      responseTime,
      result 
    });

    return result;
  }

  private async handleDataTransform(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    const transformType = step.parameters.transformType;
    const transformer = this.transformers.get(transformType);
    
    if (!transformer) {
      throw new Error(`Unknown transform type: ${transformType}`);
    }

    const startTime = Date.now();
    const result = await transformer(execution.variables, step.parameters);
    const endTime = Date.now();
    
    if (stepExecution => execution.stepExecutions.get(step.stepId)) {
      stepExecution.metrics.dataTransformTime = endTime - startTime;
    }

    return result;
  }

  private async handleCondition(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    const condition = step.parameters.condition;
    const result = this.evaluateCondition(condition, execution.variables);
    return { conditionMet: result, evaluatedAt: new Date().toISOString() };
  }

  private async handleParallel(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    const parallelSteps = step.parameters.steps;
    const promises = parallelSteps.map((parallelStep: any) => 
      this.executeStep(execution, parallelStep, this.workflows.get(execution.workflowId)!)
    );
    
    const results = await Promise.all(promises);
    return { parallelResults: results, completedAt: new Date().toISOString() };
  }

  private async handleWait(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    const waitTime = step.parameters.duration || 1000;
    await new Promise(resolve => setTimeout(resolve, waitTime));
    return { waited: waitTime, completedAt: new Date().toISOString() };
  }

  private async handleWebhook(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    // Simulate webhook call
    return { webhookSent: true, url: step.parameters.url, completedAt: new Date().toISOString() };
  }

  private async handleNotification(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    // Simulate notification
    return { 
      notificationSent: true, 
      type: step.parameters.type, 
      recipient: step.parameters.recipient,
      completedAt: new Date().toISOString() 
    };
  }

  private async handleAITask(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    const aiConfig = step.aiConfiguration;
    if (!aiConfig) {
      throw new Error('AI task requires AI configuration');
    }

    try {
      // Prepare AI request
      const inputData = {
        input_data: execution.variables.input_data || execution.variables,
        context: execution.variables.context || {},
        ...execution.variables
      };

      let prompt = aiConfig.prompt;
      
      // Handle prebuilt tasks
      if (aiConfig.aiType === 'prebuilt' && aiConfig.prebuiltTask) {
        prompt = this.enhancePrebuiltPrompt(aiConfig.prebuiltTask, inputData);
      }

      // Handle workflow analysis
      if (aiConfig.aiType === 'workflow') {
        prompt = this.generateWorkflowAnalysisPrompt(aiConfig.prebuiltTask, execution, inputData);
      }

      // Handle decision making
      if (aiConfig.aiType === 'decision') {
        prompt = this.generateDecisionPrompt(aiConfig.prompt, inputData);
      }

      // Call AI service (this would integrate with actual AI service)
      const aiResult = await this.callAIService({
        prompt,
        model: aiConfig.model,
        temperature: aiConfig.temperature,
        maxTokens: aiConfig.maxTokens,
        data: inputData
      });

      const result = {
        result: aiResult.content,
        confidence: aiResult.confidence || 0.8,
        reasoning: aiResult.reasoning || 'AI processing completed',
        model: aiConfig.model,
        processedAt: new Date().toISOString(),
        aiType: aiConfig.aiType
      };

      this.emit("ai-task-completed", { 
        stepId: step.id,
        aiType: aiConfig.aiType,
        model: aiConfig.model,
        confidence: result.confidence
      });

      return result;

    } catch (error) {
      this.logger.error(`AI task failed: ${step.id}`, error);
      throw new Error(`AI task execution failed: ${error.message}`);
    }
  }

  private async handleAdvancedBranch(execution: WorkflowExecution, step: WorkflowStep): Promise<any> {
    const branchConfig = step.branchConfiguration;
    if (!branchConfig) {
      throw new Error('Advanced branch requires branch configuration');
    }

    try {
      let selectedBranch: string | null = null;
      let branchReasoning = '';

      // Evaluate condition based on type
      switch (branchConfig.conditionType) {
        case 'field':
          selectedBranch = this.evaluateFieldCondition(
            branchConfig.fieldPath!,
            branchConfig.operator!,
            branchConfig.value,
            execution.variables
          );
          branchReasoning = `Field ${branchConfig.fieldPath} ${branchConfig.operator} ${branchConfig.value}`;
          break;

        case 'expression':
          selectedBranch = this.evaluateJavaScriptExpression(
            branchConfig.value,
            execution.variables
          );
          branchReasoning = `Expression evaluation: ${branchConfig.value}`;
          break;

        case 'ai':
          const aiDecision = await this.makeAIBranchDecision(
            branchConfig.value,
            execution.variables,
            branchConfig.branches
          );
          selectedBranch = aiDecision.branch;
          branchReasoning = aiDecision.reasoning;
          break;
      }

      // Map boolean result to branch
      if (branchConfig.branches.length === 2 && !branchConfig.branches.find(b => b.id === selectedBranch)) {
        selectedBranch = selectedBranch === 'true' ? branchConfig.branches[0].id : branchConfig.branches[1].id;
      }

      const result = {
        selectedBranch,
        branchReasoning,
        availableBranches: branchConfig.branches.map(b => b.id),
        conditionType: branchConfig.conditionType,
        evaluatedAt: new Date().toISOString()
      };

      // Update execution variables with branch decision
      execution.variables._branchDecision = result;
      execution.variables._selectedBranch = selectedBranch;

      this.emit("branch-evaluated", { 
        stepId: step.id,
        selectedBranch,
        conditionType: branchConfig.conditionType
      });

      return result;

    } catch (error) {
      this.logger.error(`Advanced branch evaluation failed: ${step.id}`, error);
      throw new Error(`Branch evaluation failed: ${error.message}`);
    }
  }

  // Data Transformers
  private async transformMapFields(data: Record<string, any>, config: Record<string, any>): Promise<any> {
    const mapping = config.mapping || {};
    const result: Record<string, any> = {};
    
    for (const [targetField, sourceField] of Object.entries(mapping)) {
      const value = this.getNestedValue(sourceField as string, data);
      if (value !== undefined) {
        this.setNestedValue(targetField, value, result);
      }
    }
    
    return result;
  }

  private async transformFilterFields(data: Record<string, any>, config: Record<string, any>): Promise<any> {
    const fields = config.fields || [];
    const result: Record<string, any> = {};
    
    for (const field of fields) {
      const value = this.getNestedValue(field, data);
      if (value !== undefined) {
        this.setNestedValue(field, value, result);
      }
    }
    
    return result;
  }

  private async transformAggregate(data: Record<string, any>, config: Record<string, any>): Promise<any> {
    const aggregation = config.aggregation || {};
    const result: Record<string, any> = {};
    
    for (const [field, operation] of Object.entries(aggregation)) {
      const values = this.getNestedValue(field, data);
      const valueArray = Array.isArray(values) ? values : [values];
      
      switch (operation) {
        case 'count':
          result[`${field}_count`] = valueArray.filter(v => v !== null && v !== undefined).length;
          break;
        case 'sum':
          result[`${field}_sum`] = valueArray.reduce((sum, v) => sum + (Number(v) || 0), 0);
          break;
        case 'avg':
          const validValues = valueArray.filter(v => v !== null && v !== undefined && !isNaN(Number(v)));
          result[`${field}_avg`] = validValues.length > 0 ? 
            validValues.reduce((sum, v) => sum + Number(v), 0) / validValues.length : 0;
          break;
        case 'min':
          const numericValues = valueArray.filter(v => v !== null && v !== undefined && !isNaN(Number(v)));
          result[`${field}_min`] = numericValues.length > 0 ? Math.min(...numericValues.map(Number)) : 0;
          break;
        case 'max':
          const maxValues = valueArray.filter(v => v !== null && v !== undefined && !isNaN(Number(v)));
          result[`${field}_max`] = maxValues.length > 0 ? Math.max(...maxValues.map(Number)) : 0;
          break;
      }
    }
    
    return result;
  }

  private async transformCalculate(data: Record<string, any>, config: Record<string, any>): Promise<any> {
    const calculations = config.calculations || {};
    const result: Record<string, any> = {};
    
    for (const [fieldName, expression] of Object.entries(calculations)) {
      try {
        // Safe expression evaluation
        const context = { ...data, Math };
        const func = new Function(...Object.keys(context), `return ${expression}`);
        result[fieldName] = func(...Object.values(context));
      } catch (error) {
        this.logger.error(`Calculation failed for ${fieldName}: ${error}`);
        result[fieldName] = null;
      }
    }
    
    return result;
  }

  private async transformFormat(data: Record<string, any>, config: Record<string, any>): Promise<any> {
    const formatRules = config.formatRules || {};
    const result = { ...data };
    
    for (const [field, rule] of Object.entries(formatRules)) {
      const value = this.getNestedValue(field, data);
      if (value !== undefined) {
        let formattedValue = value;
        
        switch (rule) {
          case 'uppercase':
            formattedValue = String(value).toUpperCase();
            break;
          case 'lowercase':
            formattedValue = String(value).toLowerCase();
            break;
          case 'date':
            formattedValue = new Date(value).toISOString();
            break;
          case 'number':
            formattedValue = Number(value);
            break;
          default:
            if (typeof rule === 'string') {
              formattedValue = rule.replace('{value}', String(value));
            }
        }
        
        this.setNestedValue(field, formattedValue, result);
      }
    }
    
    return result;
  }

  private async transformLookup(data: Record<string, any>, config: Record<string, any>): Promise<any> {
    const lookupConfig = config.lookupConfig || {};
    const { lookupTable, keyField, valueField } = lookupConfig;
    
    if (!lookupTable || !keyField || !valueField) {
      return data;
    }
    
    const result = { ...data };
    const lookupKey = this.getNestedValue(keyField, data);
    
    if (lookupKey !== undefined && lookupTable[lookupKey] !== undefined) {
      this.setNestedValue(valueField, lookupTable[lookupKey], result);
    }
    
    return result;
  }

  private async transformCustom(data: Record<string, any>, config: Record<string, any>): Promise<any> {
    if (!config.script) {
      return data;
    }
    
    try {
      // Safe custom script execution
      const func = new Function('data', 'utils', config.script);
      const utils = { Math, Date, String, Number, Array, Object };
      return func(data, utils);
    } catch (error) {
      this.logger.error(`Custom transform failed: ${error}`);
      return data;
    }
  }

  // Utility Methods
  private resolveStepDependencies(steps: WorkflowStep[]): WorkflowStep[] {
    const resolved: WorkflowStep[] = [];
    const visited = new Set<string>();
    const visiting = new Set<string>();

    const visit = (step: WorkflowStep) => {
      if (visiting.has(step.id)) {
        throw new Error(`Circular dependency detected involving step: ${step.id}`);
      }
      if (visited.has(step.id)) {
        return;
      }

      visiting.add(step.id);
      
      for (const depId of step.dependsOn) {
        const depStep = steps.find(s => s.id === depId);
        if (depStep) {
          visit(depStep);
        }
      }
      
      visiting.delete(step.id);
      visited.add(step.id);
      resolved.push(step);
    };

    for (const step of steps) {
      visit(step);
    }

    return resolved;
  }

  private evaluateCondition(condition: Record<string, any>, data: Record<string, any>): boolean {
    try {
      const { field, operator, value } = condition;
      const actualValue = this.getNestedValue(field, data);
      
      switch (operator) {
        case 'eq':
          return actualValue === value;
        case 'ne':
          return actualValue !== value;
        case 'gt':
          return Number(actualValue) > Number(value);
        case 'lt':
          return Number(actualValue) < Number(value);
        case 'gte':
          return Number(actualValue) >= Number(value);
        case 'lte':
          return Number(actualValue) <= Number(value);
        case 'contains':
          return String(actualValue).includes(String(value));
        case 'not_contains':
          return !String(actualValue).includes(String(value));
        case 'starts_with':
          return String(actualValue).startsWith(String(value));
        case 'ends_with':
          return String(actualValue).endsWith(String(value));
        case 'is_null':
          return actualValue === null || actualValue === undefined;
        case 'is_not_null':
          return actualValue !== null && actualValue !== undefined;
        default:
          return false;
      }
    } catch (error) {
      this.logger.error(`Condition evaluation failed: ${error}`);
      return false;
    }
  }

  private evaluateRouteConditions(conditions: Record<string, any>[], data: Record<string, any>): boolean {
    return conditions.every(condition => this.evaluateCondition(condition, data));
  }

  private getNestedValue(path: string, data: Record<string, any>): any {
    return path.split('.').reduce((current, key) => {
      return current && current[key] !== undefined ? current[key] : undefined;
    }, data);
  }

  private setNestedValue(path: string, value: any, data: Record<string, any>): void {
    const keys = path.split('.');
    const lastKey = keys.pop()!;
    let current = data;
    
    for (const key of keys) {
      if (!(key in current) || typeof current[key] !== 'object') {
        current[key] = {};
      }
      current = current[key];
    }
    
    current[lastKey] = value;
  }

  private async validateWorkflow(workflow: WorkflowDefinition): Promise<void> {
    if (workflow.steps.length > this.config.maxStepsPerExecution) {
      throw new Error(`Workflow exceeds maximum steps limit: ${workflow.steps.length} > ${this.config.maxStepsPerExecution}`);
    }

    for (const step of workflow.steps) {
      if (!step.id || !step.name || !step.type) {
        throw new Error(`Invalid step: missing required fields`);
      }

      if (step.type === 'integration_action' && (!step.integrationId || !step.action)) {
        throw new Error(`Integration action step requires integrationId and action`);
      }
    }

    // Check for circular dependencies
    try {
      this.resolveStepDependencies(workflow.steps);
    } catch (error) {
      throw new Error(`Workflow validation failed: ${error.message}`);
    }
  }

  private async retryExecution(execution: WorkflowExecution): Promise<void> {
    execution.retryCount++;
    execution.status = 'retrying';
    
    this.logger.info(`Retrying execution: ${execution.id} (attempt ${execution.retryCount})`);
    
    // Reset failed steps
    for (const [stepId, stepExecution] of execution.stepExecutions) {
      if (stepExecution.status === 'failed') {
        stepExecution.status = 'pending';
        stepExecution.error = undefined;
        stepExecution.completedAt = undefined;
      }
    }
    
    // Re-queue execution
    this.executionQueue.push(execution);
    
    this.emit("execution-retrying", { executionId: execution.id, retryCount: execution.retryCount });
  }

  private async handleStepError(execution: WorkflowExecution, step: WorkflowStep, error: Error): Promise<void> {
    const errorHandlerStep = this.workflows.get(execution.workflowId)?.steps.find(s => s.id === step.errorHandler);
    if (errorHandlerStep) {
      this.logger.info(`Executing error handler for step ${step.id}: ${step.errorHandler}`);
      await this.executeStep(execution, errorHandlerStep, this.workflows.get(execution.workflowId)!);
    } else {
      throw error;
    }
  }

  private updateAnalytics(execution: WorkflowExecution): void {
    const analytics = this.analytics.get(execution.workflowId);
    if (!analytics) return;

    analytics.totalExecutions++;
    
    if (execution.status === 'completed') {
      analytics.successfulExecutions++;
    } else {
      analytics.failedExecutions++;
    }
    
    if (execution.executionTime) {
      analytics.averageExecutionTime = 
        (analytics.averageExecutionTime * (analytics.totalExecutions - 1) + execution.executionTime) / 
        analytics.totalExecutions;
    }
    
    analytics.successRate = analytics.successfulExecutions / analytics.totalExecutions;
    analytics.lastExecution = execution.completedAt;

    // Update integration usage stats
    const integrationUsage: Record<string, { count: number; errors: number }> = {};
    for (const [stepId, stepExecution] of execution.stepExecutions) {
      const step = this.workflows.get(execution.workflowId)?.steps.find(s => s.id === stepId);
      if (step?.integrationId) {
        if (!integrationUsage[step.integrationId]) {
          integrationUsage[step.integrationId] = { count: 0, errors: 0 };
        }
        integrationUsage[step.integrationId].count++;
        if (stepExecution.status === 'failed') {
          integrationUsage[step.integrationId].errors++;
        }
      }
    }

    analytics.mostUsedIntegrations = Object.entries(integrationUsage).map(([integrationId, stats]) => ({
      integrationId,
      usageCount: stats.count,
      successRate: (stats.count - stats.errors) / stats.count,
    }));

    // Update failure points
    analytics.commonFailurePoints = Array.from(execution.stepExecutions.entries())
      .filter(([_, stepExecution]) => stepExecution.status === 'failed')
      .map(([stepId, stepExecution]) => ({
        stepId,
        errorCount: 1,
        lastError: stepExecution.error || 'Unknown error',
      }));

    // Generate recommendations
    analytics.recommendations = this.generateRecommendations(analytics);
  }

  private generateRecommendations(analytics: WorkflowAnalytics): string[] {
    const recommendations: string[] = [];
    
    if (analytics.successRate < 0.8) {
      recommendations.push("Consider reviewing error-prone steps and improving error handling");
    }
    
    if (analytics.averageExecutionTime > 60000) {
      recommendations.push("Consider optimizing slow steps or enabling parallel execution");
    }
    
    const failedSteps = analytics.commonFailurePoints.length;
    if (failedSteps > 2) {
      recommendations.push(`${failedSteps} steps frequently fail - review these steps for reliability improvements`);
    }
    
    if (analytics.mostUsedIntegrations.length > 0) {
      const slowestIntegration = analytics.mostUsedIntegrations
        .sort((a, b) => b.successRate - a.successRate)
        .find(int => int.successRate < 0.9);
      
      if (slowestIntegration) {
        recommendations.push(`Integration ${slowestIntegration.integrationId} has low success rate (${(slowestIntegration.successRate * 100).toFixed(1)}%)`);
      }
    }
    
    return recommendations;
  }

  // AI Helper Methods
  private async callAIService(request: {
    prompt: string;
    model: string;
    temperature: number;
    maxTokens: number;
    data: any;
  }): Promise<{ content: any; confidence?: number; reasoning?: string }> {
    // This would integrate with actual AI service (OpenAI, Claude, etc.)
    // For now, simulating AI response
    
    this.logger.info(`Calling AI service with model: ${request.model}`);
    
    // Simulate AI processing time
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Simulate different AI responses based on context
    let response: any;
    let confidence = 0.8 + Math.random() * 0.2; // Random confidence between 0.8-1.0
    
    if (request.prompt.toLowerCase().includes('summarize')) {
      response = {
        summary: "This is a simulated AI summary of the provided content.",
        keyPoints: ["Point 1", "Point 2", "Point 3"],
        wordCount: request.data.input_data?.toString()?.split?.(' ')?.length || 0
      };
    } else if (request.prompt.toLowerCase().includes('classify')) {
      response = {
        category: "Business",
        subcategory: "Customer Service",
        confidence: confidence
      };
    } else if (request.prompt.toLowerCase().includes('sentiment')) {
      response = {
        sentiment: Math.random() > 0.5 ? "positive" : "neutral",
        score: Math.random(),
        confidence: confidence
      };
    } else {
      response = {
        result: `AI processed the input using ${request.model}`,
        analysis: "Simulated AI analysis based on the provided context",
        recommendations: ["Consider additional context", "Review parameters"],
        confidence: confidence
      };
    }
    
    return {
      content: response,
      confidence,
      reasoning: `Processed using ${request.model} with temperature ${request.temperature}`
    };
  }

  private enhancePrebuiltPrompt(taskId: string, inputData: any): string {
    const taskPrompts = {
      summarize: `Summarize the following text in a concise manner:\n\n${JSON.stringify(inputData)}\n\nSummary:`,
      extract: `Extract key information from the following data:\n\n${JSON.stringify(inputData)}\n\nExtracted information:`,
      classify: `Classify the following content into appropriate categories:\n\n${JSON.stringify(inputData)}\n\nClassification:`,
      translate: `Translate the following text:\n\n${JSON.stringify(inputData)}\n\nTranslation:`,
      sentiment: `Analyze the sentiment of the following text (positive/negative/neutral):\n\n${JSON.stringify(inputData)}\n\nSentiment analysis:`,
      generate: `Generate content based on the following context:\n\n${JSON.stringify(inputData)}\n\nGenerated content:`,
      validate: `Validate the following data and identify any issues:\n\n${JSON.stringify(inputData)}\n\nValidation results:`,
      transform: `Transform the following data according to the specified rules:\n\n${JSON.stringify(inputData)}\n\nTransformed data:`
    };
    
    return taskPrompts[taskId as keyof typeof taskPrompts] || taskPrompts.summarize;
  }

  private generateWorkflowAnalysisPrompt(analysisType: string, execution: WorkflowExecution, inputData: any): string {
    const workflowInfo = {
      workflowId: execution.workflowId,
      currentStep: execution.currentStep,
      variables: execution.variables,
      executionTime: execution.executionTime
    };
    
    const analysisPrompts = {
      optimize: `Analyze this workflow execution and suggest optimizations:\n\nWorkflow: ${JSON.stringify(workflowInfo)}\n\nOptimization recommendations:`,
      debug: `Debug this workflow execution and identify potential issues:\n\nWorkflow: ${JSON.stringify(workflowInfo)}\n\nDebug analysis:`,
      predict: `Based on this workflow state, predict likely outcomes:\n\nWorkflow: ${JSON.stringify(workflowInfo)}\n\nPredictions:`,
      improve: `Suggest improvements for this workflow execution:\n\nWorkflow: ${JSON.stringify(workflowInfo)}\n\nImprovement suggestions:`
    };
    
    return analysisPrompts[analysisType as keyof typeof analysisPrompts] || analysisPrompts.optimize;
  }

  private generateDecisionPrompt(criteria: string, inputData: any): string {
    return `Make a decision based on the following criteria and data:

Criteria: ${criteria}

Data: ${JSON.stringify(inputData)}

Please provide a decision (true/false) and your reasoning. Format your response as JSON:
{
  "decision": true/false,
  "reasoning": "Your reasoning here",
  "confidence": 0.0-1.0
}`;
  }

  // Branch Helper Methods
  private evaluateFieldCondition(fieldPath: string, operator: string, value: string, data: any): string {
    const actualValue = this.getNestedValue(fieldPath, data);
    
    let result = false;
    switch (operator) {
      case 'equals':
        result = actualValue === value;
        break;
      case 'not_equals':
        result = actualValue !== value;
        break;
      case 'greater_than':
        result = Number(actualValue) > Number(value);
        break;
      case 'less_than':
        result = Number(actualValue) < Number(value);
        break;
      case 'contains':
        result = String(actualValue).includes(String(value));
        break;
      case 'starts_with':
        result = String(actualValue).startsWith(String(value));
        break;
      case 'ends_with':
        result = String(actualValue).endsWith(String(value));
        break;
      case 'is_null':
        result = actualValue === null || actualValue === undefined;
        break;
      case 'is_not_null':
        result = actualValue !== null && actualValue !== undefined;
        break;
    }
    
    return result ? 'true' : 'false';
  }

  private evaluateJavaScriptExpression(expression: string, data: any): string {
    try {
      // Safe expression evaluation
      const context = { ...data, Math, Date, String, Number, Array, Object };
      const func = new Function(...Object.keys(context), `return ${expression}`);
      const result = func(...Object.values(context));
      return Boolean(result) ? 'true' : 'false';
    } catch (error) {
      this.logger.error(`JavaScript expression evaluation failed: ${error}`);
      return 'false';
    }
  }

  private async makeAIBranchDecision(prompt: string, data: any, branches: any[]): Promise<{ branch: string; reasoning: string }> {
    const aiPrompt = `Evaluate the following data and determine which branch should be taken:

Available branches:
${branches.map(b => `- ${b.id}: ${b.label}`).join('\n')}

Evaluation criteria: ${prompt}

Data: ${JSON.stringify(data)}

Please respond with only the branch ID that should be taken:`;

    try {
      const aiResult = await this.callAIService({
        prompt: aiPrompt,
        model: 'gpt-3.5-turbo',
        temperature: 0.3,
        maxTokens: 100,
        data
      });
      
      const selectedBranch = String(aiResult.content).trim();
      const validBranch = branches.find(b => b.id === selectedBranch);
      
      return {
        branch: validBranch ? validBranch.id : branches[0].id,
        reasoning: `AI selected branch "${selectedBranch}" based on evaluation criteria`
      };
    } catch (error) {
      this.logger.error(`AI branch decision failed: ${error}`);
      return {
        branch: branches[0].id,
        reasoning: 'AI decision failed, defaulting to first branch'
      };
    }
  }

  private async startHealthMonitoring(): Promise<void> {
    setInterval(async () => {
      for (const [integrationId, state] of this.integrationStates) {
        // Check integration health
        const isHealthy = await this.checkIntegrationHealth(integrationId);
        const wasHealthy = state.isAvailable;
        
        state.isAvailable = isHealthy;
        
        if (wasHealthy !== isHealthy) {
          this.emit("integration-health-changed", { 
            integrationId, 
            isHealthy, 
            wasHealthy 
          });
        }
      }
    }, this.config.healthCheckInterval);
  }

  private async checkIntegrationHealth(integrationId: string): Promise<boolean> {
    const integration = this.integrations.get(integrationId);
    const state = this.integrationStates.get(integrationId);
    
    if (!integration || !state) {
      return false;
    }

    // Health check criteria
    const criteria = [
      state.isConnected,
      state.metrics.successRate >= this.config.integrationHealthThreshold,
      state.rateLimitRemaining > 0,
      Date.now() < state.rateLimitReset.getTime() || state.rateLimitRemaining > 10,
    ];

    return criteria.every(Boolean);
  }

  // Public API Methods
  async getExecution(executionId: string): Promise<WorkflowExecution | null> {
    return this.executions.get(executionId) || null;
  }

  async getWorkflowAnalytics(workflowId: string): Promise<WorkflowAnalytics | null> {
    return this.analytics.get(workflowId) || null;
  }

  async getIntegrationHealth(): Promise<Map<string, IntegrationState>> {
    return new Map(this.integrationStates);
  }

  async cancelExecution(executionId: string): Promise<boolean> {
    const execution = this.executions.get(executionId);
    if (!execution) {
      return false;
    }

    execution.status = 'cancelled';
    execution.completedAt = new Date();
    
    this.emit("execution-cancelled", { executionId });
    return true;
  }

  async pauseExecution(executionId: string): Promise<boolean> {
    const execution = this.executions.get(executionId);
    if (!execution || execution.status !== 'running') {
      return false;
    }

    execution.status = 'paused';
    this.emit("execution-paused", { executionId });
    return true;
  }

  async resumeExecution(executionId: string): Promise<boolean> {
    const execution = this.executions.get(executionId);
    if (!execution || execution.status !== 'paused') {
      return false;
    }

    execution.status = 'running';
    this.executionQueue.push(execution);
    this.emit("execution-resumed", { executionId });
    return true;
  }

  getRegisteredWorkflows(): WorkflowDefinition[] {
    return Array.from(this.workflows.values());
  }

  getRegisteredIntegrations(): IntegrationCapability[] {
    return Array.from(this.integrations.values());
  }

  getActiveExecutions(): WorkflowExecution[] {
    return Array.from(this.activeExecutions.values());
  }

  getSystemHealth(): {
    totalWorkflows: number;
    totalIntegrations: number;
    activeExecutions: number;
    queuedExecutions: number;
    healthyIntegrations: number;
    systemUptime: number;
  } {
    const healthyIntegrations = Array.from(this.integrationStates.values())
      .filter(state => state.isAvailable).length;

    return {
      totalWorkflows: this.workflows.size,
      totalIntegrations: this.integrations.size,
      activeExecutions: this.activeExecutions.size,
      queuedExecutions: this.executionQueue.length,
      healthyIntegrations,
      systemUptime: Date.now() - (this as any).startTime || 0,
    };
  }
}