import { EventEmitter } from 'events';
import { OrchestrationEngine } from './OrchestrationEngine';
import { AgentRegistry } from './AgentRegistry';
import { Logger } from '../utils/logger';
import { SkillRegistry } from '../skills';

export interface OrchestrationConfig {
  autoOptimization: boolean;
  performanceMonitoring: boolean;
  loadBalancing: boolean;
  predictiveScheduling: boolean;
}

export interface WorkflowRequest {
  id?: string;
  type: 'business-automation' | 'marketing-campaign' | 'financial-planning' | 'content-creation' | 'system-management';
  description: string;
  businessContext?: {
    industry?: string;
    companySize?: 'solo' | 'small' | 'medium' | 'large';
    technicalSkill?: 'beginner' | 'intermediate' | 'advanced';
    goals?: string[];
    constraints?: string[];
  };
  requirements: string[];
  priority: number;
  deadline?: Date;
  interactive?: boolean;
}

export interface SystemMetrics {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  activeAgents: number;
  averageTaskDuration: number;
  systemHealth: 'excellent' | 'good' | 'degraded' | 'critical';
  nextScheduledOptimization?: Date;
}

interface Task {
  id: string;
  type: string;
  description: string;
  requirements: string[];
  priority: number;
  deadline?: Date;
  dependencies: string[];
  context: any;
}


export class OrchestrationManager extends EventEmitter {
  private engine: OrchestrationEngine;
  private agentRegistry: AgentRegistry;
  private logger: Logger;
  private config: OrchestrationConfig;
  private metricsCollector: MetricsCollector;
  private optimizationManager: OptimizationManager;

  constructor(skillRegistry: SkillRegistry, config: OrchestrationConfig = {}) {
    super();
    this.logger = new Logger('OrchestrationManager');
    this.agentRegistry = new AgentRegistry(skillRegistry);
    this.engine = new OrchestrationEngine(skillRegistry, {
      maxConcurrentAgents: 5,
      delegationConfidenceThreshold: 0.7,
      retryAttempts: 3,
      recoveryMode: 'redistribute'
    });

    this.config = {
      autoOptimization: true,
      performanceMonitoring: true,
      loadBalancing: true,
      predictiveScheduling: true,
      ...config
    };

    this.metricsCollector = new MetricsCollector();
    this.optimizationManager = new OptimizationManager(this.engine, this.agentRegistry, this.config);

    this.initialize();
  }

  private initialize(): void {
    this.logger.info('Initializing advanced orchestration system');

    // Register all agents from registry with the engine
    const agentProfiles = this.agentRegistry.getAllAgents().map(agentDef => ({
      id: agentDef.id,
      name: agentDef.name,
      skills: agentDef.skills,
      capabilities: agentDef.capabilities,
      priority: agentDef.priority,
      confidence: agentDef.confidence
    }));

    agentProfiles.forEach(profile => {
      this.engine.registerAgent(profile);
    });

    // Setup system monitoring
    this.setupEventListeners();

    // Start optimization loop
    if (this.config.autoOptimization) {
      this.startOptimizationLoop();
    }

    this.logger.info('Orchestration system initialized successfully');
  }

  private setupEventListeners(): void {
    this.engine.on('execution-started', (data) => {
      this.logger.info(`Execution started: ${data.plan.task.description}`);
      this.metricsCollector.recordTaskStart(data.plan.task.id);
    });

    this.engine.on('execution-completed', (data) => {
      this.logger.info(`Execution completed: ${data.completedSteps.length} steps, ${data.totalTime}ms`);
      this.metricsCollector.recordTaskComplete(data.taskId, data.totalTime, true);
    });

    this.engine.on('execution-failed', (data) => {
      this.logger.error(`Execution failed: ${data.taskId}`, data.error);
      this.metricsCollector.recordTaskComplete(data.taskId, 0, false);
    });

    this.engine.on('step-started', (data) => {
      this.logger.debug(`Step ${data.step.stepNumber} started for ${data.execution.agentId}`);
    });

    this.engine.on('step-completed', (data) => {
      this.logger.debug(`Step ${data.step.stepNumber} completed by ${data.execution.agentId}`);
    });

    this.agentRegistry.on('optimization-needed', (data) => {
      this.logger.warn(`Agent optimization needed for ${data.criticalAgents.length} agents`);
      this.optimizationManager.triggerOptimization();
    });
  }

  async submitWorkflow(workflow: WorkflowRequest): Promise<string> {
    const task = this.convertWorkflowToTask(workflow);
    this.logger.info(`Submitted workflow: ${workflow.description}`);

    const executionPlan = await this.engine.submitTask(task);
    this.emit('workflow-submitted', { workflow, taskId: task.id });

    return executionPlan.id;
  }

  async getWorkflowStatus(workflowId: string): Promise<{
    id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    progress: number;
    estimatedDuration: number;
    results?: any;
    lastUpdate: Date;
  }> {
    const plan = this.engine.getActiveExecutions().find(p => p.id === workflowId);

    if (plan) {
      const activeSteps = plan.steps.length;
      const completedSteps = 0; // Would need to track this
      return {
        id: workflowId,
        status: 'running',
        progress: (completedSteps / activeSteps) * 100,
        estimatedDuration: plan.estimatedDuration,
        lastUpdate: new Date()
      };
    }

    const history = this.engine.getExecutionHistory().find(e => e.taskId === workflowId);
    if (history) {
      return {
        id: workflowId,
        status: history.status,
        progress: 100,
        estimatedDuration: 0,
        results: history.results,
        lastUpdate: history.completedAt || new Date()
      };
    }

    return {
      id: workflowId,
      status: 'pending',
      progress: 0,
      estimatedDuration: 0,
      lastUpdate: new Date()
    };
  }

  getSystemMetrics(): SystemMetrics {
    const history = this.engine.getExecutionHistory();
    const totalTasks = history.length;
    const completedTasks = history.filter(h => h.status === 'completed').length;
    const failedTasks = history.filter(h => h.status === 'failed').length;
    const avgDuration = history.length > 0
      ? history.reduce((sum, h) => sum + (h.completedAt ? h.completedAt.getTime() - h.createdAt.getTime() : 0), 0) / history.length
      : 0;

    const health = this.assessSystemHealth();

    return {
      totalTasks,
      completedTasks,
      failedTasks,
+      activeAgents: this.engine.getRegisteredAgents().length,
      averageTaskDuration: avgDuration,
      systemHealth: health.status,
      nextScheduledOptimization: health.nextOptimization
    };
  }

  private assessSystemHealth(): {
    status: SystemMetrics['systemHealth'];
    nextOptimization?: Date;
  } {
+    const metrics = this.engine.getSystemHealth();
+    const healthStatus = metrics.successRate;
+
+    if (healthStatus > 0.95) return { status: 'excellent' };
+    if (healthStatus > 0.85) return { status: 'good' };
+    if (healthStatus > 0.7) return { status: 'degraded' };
+    return { status: 'critical', nextOptimization: new Date(Date.now() + 60000) };
+  }

  private setupEventListeners(): void {
+    // Event listeners already set up above
+  }

  private startOptimizationLoop(): void {
+    setInterval(() => {
+      this.optimizationManager.performAutoOptimization();
+    }, 300000); // Every 5 minutes
+  }

  private convertWorkflowToTask(workflow: WorkflowRequest): Task {
    const task: Task = {
      id: `wf_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      type: this.mapWorkflowTypeToTaskType(workflow.type),
      description: workflow.description,
      requirements: workflow.requirements,
      priority: workflow.priority,
      deadline: workflow.deadline,
      dependencies: [],
      context: workflow.businessContext || {}
    };
+    };
+
+    return task;
+  }

  private mapWorkflowTypeToTaskType(type: WorkflowRequest['type']): string {
+    const
