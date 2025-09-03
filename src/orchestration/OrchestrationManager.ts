import { EventEmitter } from "events";
import { OrchestrationEngine } from "./OrchestrationEngine";
import { AgentRegistry } from "./AgentRegistry";
import { Logger } from "../utils/logger";
import { SkillRegistry } from "../skills";
import { MetricsCollector } from "./MetricsCollector";
import { OptimizationManager } from "./OptimizationManager";

export interface OrchestrationConfig {
  autoOptimization: boolean;
  performanceMonitoring: boolean;
  loadBalancing: boolean;
  predictiveScheduling: boolean;
  maxConcurrentAgents?: number;
  delegationConfidenceThreshold?: number;
  retryAttempts?: number;
  recoveryMode?: "redistribute" | "failover" | "retry";
}

export interface WorkflowRequest {
  id?: string;
  type:
    | "business-automation"
    | "marketing-campaign"
    | "financial-planning"
    | "content-creation"
    | "system-management";
  description: string;
  businessContext?: {
    industry?: string;
    companySize?: "solo" | "small" | "medium" | "large";
    technicalSkill?: "beginner" | "intermediate" | "advanced";
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
  systemHealth: "excellent" | "good" | "degraded" | "critical";
  nextScheduledOptimization?: Date;
  successRate: number;
  throughput: number;
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
  createdAt: Date;
  status: "pending" | "running" | "completed" | "failed";
}

interface ExecutionHistory {
  taskId: string;
  status: "completed" | "failed";
  createdAt: Date;
  completedAt?: Date;
  totalTime?: number;
  results?: any;
  error?: string;
}

export class OrchestrationManager extends EventEmitter {
  private engine: OrchestrationEngine;
  private agentRegistry: AgentRegistry;
  private logger: Logger;
  private config: OrchestrationConfig;
  private metricsCollector: MetricsCollector;
  private optimizationManager: OptimizationManager;
  private executionHistory: ExecutionHistory[] = [];
  private activeTasks: Map<string, Task> = new Map();

  constructor(
    skillRegistry: SkillRegistry,
    config: Partial<OrchestrationConfig> = {},
  ) {
    super();
    this.logger = new Logger("OrchestrationManager");
    this.agentRegistry = new AgentRegistry(skillRegistry);

    const engineConfig = {
      maxConcurrentAgents: config.maxConcurrentAgents || 5,
      delegationConfidenceThreshold:
        config.delegationConfidenceThreshold || 0.7,
      retryAttempts: config.retryAttempts || 3,
      recoveryMode: config.recoveryMode || "redistribute",
    };

    this.engine = new OrchestrationEngine(skillRegistry, engineConfig);

    this.config = {
      autoOptimization: true,
      performanceMonitoring: true,
      loadBalancing: true,
      predictiveScheduling: true,
      ...config,
    };

    this.metricsCollector = new MetricsCollector();
    this.optimizationManager = new OptimizationManager(
      this.engine,
      this.agentRegistry,
      this.config,
    );

    this.initialize();
  }

  private initialize(): void {
    this.logger.info("Initializing advanced orchestration system");

    // Register all agents from registry with the engine
    const agentProfiles = this.agentRegistry.getAllAgents().map((agentDef) => ({
      id: agentDef.id,
      name: agentDef.name,
      skills: agentDef.skills,
      capabilities: agentDef.capabilities,
      priority: agentDef.priority,
      confidence: agentDef.confidence,
    }));

    agentProfiles.forEach((profile) => {
      this.engine.registerAgent(profile);
    });

    // Setup system monitoring
    this.setupEventListeners();

    // Start optimization loop
    if (this.config.autoOptimization) {
      this.startOptimizationLoop();
    }

    this.logger.info("Orchestration system initialized successfully");
  }

  private setupEventListeners(): void {
    this.engine.on("execution-started", (data) => {
      this.logger.info(`Execution started: ${data.plan.task.description}`);
      this.metricsCollector.recordTaskStart(data.plan.task.id);

      // Update task status
      const task = this.activeTasks.get(data.plan.task.id);
      if (task) {
        task.status = "running";
      }
    });

    this.engine.on("execution-completed", (data) => {
      this.logger.info(
        `Execution completed: ${data.completedSteps.length} steps, ${data.totalTime}ms`,
      );
      this.metricsCollector.recordTaskComplete(
        data.taskId,
        data.totalTime,
        true,
      );

      // Add to history
      this.executionHistory.push({
        taskId: data.taskId,
        status: "completed",
        createdAt: new Date(data.taskId.split("_")[1]),
        completedAt: new Date(),
        totalTime: data.totalTime,
        results: data.results,
      });

      // Remove from active tasks
      this.activeTasks.delete(data.taskId);
    });

    this.engine.on("execution-failed", (data) => {
      this.logger.error(`Execution failed: ${data.taskId}`, data.error);
      this.metricsCollector.recordTaskComplete(data.taskId, 0, false);

      // Add to history
      this.executionHistory.push({
        taskId: data.taskId,
        status: "failed",
        createdAt: new Date(data.taskId.split("_")[1]),
        completedAt: new Date(),
        error: data.error.message,
      });

      // Remove from active tasks
      this.activeTasks.delete(data.taskId);
    });

    this.engine.on("step-started", (data) => {
      this.logger.debug(
        `Step ${data.step.stepNumber} started for ${data.execution.agentId}`,
      );
    });

    this.engine.on("step-completed", (data) => {
      this.logger.debug(
        `Step ${data.step.stepNumber} completed by ${data.execution.agentId}`,
      );
    });

    this.agentRegistry.on("optimization-needed", (data) => {
      this.logger.warn(
        `Agent optimization needed for ${data.criticalAgents.length} agents`,
      );
      this.optimizationManager.triggerOptimization();
    });
  }

  async submitWorkflow(workflow: WorkflowRequest): Promise<string> {
    const task = this.convertWorkflowToTask(workflow);
    this.logger.info(`Submitted workflow: ${workflow.description}`);

    const executionPlan = await this.engine.submitTask(task);
    this.emit("workflow-submitted", { workflow, taskId: task.id });

    return executionPlan.id;
  }

  async getWorkflowStatus(workflowId: string): Promise<{
    id: string;
    status: "pending" | "running" | "completed" | "failed";
    progress: number;
    estimatedDuration: number;
    results?: any;
    lastUpdate: Date;
  }> {
    const plan = this.engine
      .getActiveExecutions()
      .find((p) => p.id === workflowId);

    if (plan) {
      const activeSteps = plan.steps.length;
      const completedSteps = plan.steps.filter(
        (step) => step.status === "completed",
      ).length;
      return {
        id: workflowId,
        status: "running",
        progress: (completedSteps / activeSteps) * 100,
        estimatedDuration: plan.estimatedDuration,
        lastUpdate: new Date(),
      };
    }

    const history = this.executionHistory.find((e) => e.taskId === workflowId);
    if (history) {
      return {
        id: workflowId,
        status: history.status,
        progress: 100,
        estimatedDuration: 0,
        results: history.results,
        lastUpdate: history.completedAt || new Date(),
      };
    }

    return {
      id: workflowId,
      status: "pending",
      progress: 0,
      estimatedDuration: 0,
      lastUpdate: new Date(),
    };
  }

  getSystemMetrics(): SystemMetrics {
    const history = this.executionHistory;
    const totalTasks = history.length;
    const completedTasks = history.filter(
      (h) => h.status === "completed",
    ).length;
    const failedTasks = history.filter((h) => h.status === "failed").length;
    const successRate = totalTasks > 0 ? completedTasks / totalTasks : 1;

    const avgDuration =
      completedTasks > 0
        ? history
            .filter((h) => h.status === "completed")
            .reduce((sum, h) => sum + (h.totalTime || 0), 0) / completedTasks
        : 0;

    const health = this.assessSystemHealth();

    // Calculate throughput (tasks per hour)
    const oneHourAgo = new Date(Date.now() - 3600000);
    const recentTasks = history.filter(
      (h) => h.completedAt && h.completedAt > oneHourAgo,
    );
    const throughput = recentTasks.length;

    return {
      totalTasks,
      completedTasks,
      failedTasks,
      activeAgents: this.engine.getRegisteredAgents().length,
      averageTaskDuration: avgDuration,
      systemHealth: health.status,
      nextScheduledOptimization: health.nextOptimization,
      successRate,
      throughput,
    };
  }

  private assessSystemHealth(): {
    status: SystemMetrics["systemHealth"];
    nextOptimization?: Date;
  } {
    const metrics = this.getSystemMetrics();
    const healthStatus = metrics.successRate;

    if (healthStatus > 0.95) return { status: "excellent" };
    if (healthStatus > 0.85) return { status: "good" };
    if (healthStatus > 0.7) return { status: "degraded" };
    return {
      status: "critical",
      nextOptimization: new Date(Date.now() + 60000),
    };
  }

  private startOptimizationLoop(): void {
    setInterval(() => {
      this.optimizationManager.performAutoOptimization();
    }, 300000); // Every 5 minutes
  }

  private convertWorkflowToTask(workflow: WorkflowRequest): Task {
    const taskId = `wf_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    const task: Task = {
      id: taskId,
      type: this.mapWorkflowTypeToTaskType(workflow.type),
      description: workflow.description,
      requirements: workflow.requirements,
      priority: workflow.priority,
      deadline: workflow.deadline,
      dependencies: [],
      context: workflow.businessContext || {},
      createdAt: new Date(),
      status: "pending",
    };

    // Store in active tasks
    this.activeTasks.set(taskId, task);

    return task;
  }

  private mapWorkflowTypeToTaskType(type: WorkflowRequest["type"]): string {
    const typeMap: Record<WorkflowRequest["type"], string> = {
      "business-automation": "automation",
      "marketing-campaign": "marketing",
      "financial-planning": "financial",
      "content-creation": "content",
      "system-management": "system",
    };

    return typeMap[type] || "general";
  }

  getActiveExecutions() {
    return this.engine.getActiveExecutions();
  }

  getQueuedTasks() {
    return this.engine.getQueuedTasks();
  }

  getExecutionHistory(): ExecutionHistory[] {
    return [...this.executionHistory];
  }

  getRegisteredAgents() {
    return this.engine.getRegisteredAgents();
  }

  getAgent(agentId: string) {
    return this.engine.getAgent(agentId);
  }

  getSystemHealth() {
    return this.getSystemMetrics();
  }

  async shutdown(): Promise<void> {
    this.logger.info("Shutting down orchestration system");

    // Stop optimization loop
    if (this.optimizationManager) {
      this.optimizationManager.stop();
    }

    // Stop all active executions
    const activeExecutions = this.getActiveExecutions();
    for (const execution of activeExecutions) {
      await this.engine.cancelExecution(execution.id);
    }

    this.removeAllListeners();
    this.logger.info("Orchestration system shutdown complete");
  }

  async restart(): Promise<void> {
    this.logger.info("Restarting orchestration system");
    await this.shutdown();

    // Reinitialize
    this.executionHistory = [];
    this.activeTasks.clear();
    this.initialize();

    this.logger.info("Orchestration system restarted successfully");
  }

  clearHistory(): void {
    this.executionHistory = [];
    this.logger.info("Execution history cleared");
  }

  exportMetrics(): any {
    return {
      systemMetrics: this.getSystemMetrics(),
      agentMetrics: this.agentRegistry.getAgentMetrics(),
      optimizationMetrics: this.optimizationManager.getMetrics(),
      historicalData: {
        totalExecutions: this.executionHistory.length,
        successRate: this.getSystemMetrics().successRate,
        averageDuration: this.getSystemMetrics().averageTaskDuration,
      },
    };
  }
}
