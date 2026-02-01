/**
 * Unified Agent Orchestration System
 *
 * Core orchestration engine that coordinates all autonomous agents and systems
 * within the ATOM agentic OS. Provides centralized management, coordination,
 * and intelligent routing between different agent capabilities.
 */

import { EventEmitter } from "events";
import { v4 as uuidv4 } from "uuid";

// Core interfaces
export interface AgentCapability {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  enabled: boolean;
  priority: number;
  dependencies: string[];
  metadata: Record<string, any>;
}

export interface AgentTask {
  id: string;
  type: string;
  description: string;
  priority: "low" | "medium" | "high" | "critical";
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  assignedAgent?: string;
  parameters: Record<string, any>;
  result?: any;
  error?: string;
  createdAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  timeout: number;
  retries: number;
  metadata: Record<string, any>;
}

export interface AgentSession {
  id: string;
  userId: string;
  startTime: Date;
  endTime?: Date;
  status: "active" | "completed" | "failed";
  tasks: AgentTask[];
  context: Record<string, any>;
  metrics: SessionMetrics;
}

export interface SessionMetrics {
  totalTasks: number;
  completedTasks: number;
  failedTasks: number;
  averageTaskTime: number;
  totalExecutionTime: number;
  resourceUsage: ResourceUsage;
}

export interface ResourceUsage {
  cpu: number;
  memory: number;
  network: number;
  storage: number;
  apiCalls: number;
}

export interface OrchestrationConfig {
  maxConcurrentTasks: number;
  taskTimeout: number;
  maxRetries: number;
  enableLoadBalancing: boolean;
  enableHealthChecks: boolean;
  healthCheckInterval: number;
  enableMetrics: boolean;
  metricsRetention: number;
}

export interface AgentHealth {
  agentId: string;
  status: "healthy" | "degraded" | "unhealthy";
  lastCheck: Date;
  responseTime: number;
  errorRate: number;
  resourceUsage: ResourceUsage;
}

export class AgentOrchestrationSystem extends EventEmitter {
  private agents: Map<string, AgentCapability> = new Map();
  private tasks: Map<string, AgentTask> = new Map();
  private sessions: Map<string, AgentSession> = new Map();
  private agentHealth: Map<string, AgentHealth> = new Map();
  private taskQueue: AgentTask[] = [];
  private runningTasks: Set<string> = new Set();
  private config: OrchestrationConfig;
  private isRunning: boolean = false;
  private healthCheckInterval?: NodeJS.Timeout;
  private metricsInterval?: NodeJS.Timeout;

  constructor(config: Partial<OrchestrationConfig> = {}) {
    super();
    this.config = {
      maxConcurrentTasks: 10,
      taskTimeout: 30000,
      maxRetries: 3,
      enableLoadBalancing: true,
      enableHealthChecks: true,
      healthCheckInterval: 30000,
      enableMetrics: true,
      metricsRetention: 24 * 60 * 60 * 1000, // 24 hours
      ...config,
    };
  }

  /**
   * Initialize the orchestration system
   */
  async initialize(): Promise<void> {
    if (this.isRunning) {
      throw new Error("Orchestration system already running");
    }

    console.log("🚀 Initializing Agent Orchestration System...");

    // Register core agents
    await this.registerCoreAgents();

    // Start background processes
    if (this.config.enableHealthChecks) {
      this.startHealthChecks();
    }

    if (this.config.enableMetrics) {
      this.startMetricsCollection();
    }

    // Start task processor
    this.startTaskProcessor();

    this.isRunning = true;
    console.log("✅ Agent Orchestration System initialized successfully");
    this.emit("system-initialized");
  }

  /**
   * Register a new agent capability
   */
  async registerAgent(agent: AgentCapability): Promise<boolean> {
    try {
      // Validate agent
      if (!this.validateAgent(agent)) {
        console.error(`❌ Invalid agent definition: ${agent.name}`);
        return false;
      }

      // Check dependencies
      for (const dependency of agent.dependencies) {
        if (!this.agents.has(dependency)) {
          console.warn(
            `⚠️ Agent ${agent.name} depends on missing agent: ${dependency}`,
          );
        }
      }

      // Register agent
      this.agents.set(agent.id, agent);

      // Initialize health monitoring
      this.agentHealth.set(agent.id, {
        agentId: agent.id,
        status: "healthy",
        lastCheck: new Date(),
        responseTime: 0,
        errorRate: 0,
        resourceUsage: {
          cpu: 0,
          memory: 0,
          network: 0,
          storage: 0,
          apiCalls: 0,
        },
      });

      console.log(`✅ Registered agent: ${agent.name} (${agent.id})`);
      this.emit("agent-registered", { agent });
      return true;
    } catch (error) {
      console.error(`❌ Failed to register agent ${agent.name}:`, error);
      return false;
    }
  }

  /**
   * Submit a task for execution
   */
  async submitTask(taskRequest: {
    type: string;
    description: string;
    priority?: AgentTask["priority"];
    parameters: Record<string, any>;
    timeout?: number;
    metadata?: Record<string, any>;
  }): Promise<string> {
    const taskId = uuidv4();

    const task: AgentTask = {
      id: taskId,
      type: taskRequest.type,
      description: taskRequest.description,
      priority: taskRequest.priority || "medium",
      status: "pending",
      parameters: taskRequest.parameters,
      createdAt: new Date(),
      timeout: taskRequest.timeout || this.config.taskTimeout,
      retries: 0,
      metadata: taskRequest.metadata || {},
    };

    this.tasks.set(taskId, task);
    this.taskQueue.push(task);

    // Prioritize queue
    this.prioritizeTaskQueue();

    console.log(`📋 Task submitted: ${task.description} (${taskId})`);
    this.emit("task-submitted", { task });

    return taskId;
  }

  /**
   * Create a new orchestration session
   */
  async createSession(
    userId: string,
    context: Record<string, any> = {},
  ): Promise<string> {
    const sessionId = uuidv4();

    const session: AgentSession = {
      id: sessionId,
      userId,
      startTime: new Date(),
      status: "active",
      tasks: [],
      context,
      metrics: {
        totalTasks: 0,
        completedTasks: 0,
        failedTasks: 0,
        averageTaskTime: 0,
        totalExecutionTime: 0,
        resourceUsage: {
          cpu: 0,
          memory: 0,
          network: 0,
          storage: 0,
          apiCalls: 0,
        },
      },
    };

    this.sessions.set(sessionId, session);
    console.log(`🎯 Session created: ${sessionId} for user ${userId}`);
    this.emit("session-created", { session });

    return sessionId;
  }

  /**
   * Execute a complex workflow across multiple agents
   */
  async executeWorkflow(
    sessionId: string,
    workflow: {
      name: string;
      description: string;
      steps: Array<{
        agentType: string;
        task: string;
        parameters: Record<string, any>;
        dependsOn?: string[];
        timeout?: number;
      }>;
    },
  ): Promise<string[]> {
    const session = this.sessions.get(sessionId);
    if (!session) {
      throw new Error(`Session not found: ${sessionId}`);
    }

    console.log(
      `🔄 Executing workflow: ${workflow.name} in session ${sessionId}`,
    );

    const taskIds: string[] = [];
    const stepDependencies = new Map<string, string[]>();

    // Create all tasks first
    for (const step of workflow.steps) {
      const taskId = await this.submitTask({
        type: step.agentType,
        description: step.task,
        parameters: step.parameters,
        timeout: step.timeout,
        metadata: {
          workflow: workflow.name,
          sessionId,
          step: step.task,
        },
      });

      taskIds.push(taskId);

      if (step.dependsOn && step.dependsOn.length > 0) {
        stepDependencies.set(taskId, step.dependsOn);
      }

      // Add task to session
      const task = this.tasks.get(taskId);
      if (task) {
        session.tasks.push(task);
        session.metrics.totalTasks++;
      }
    }

    // Set up dependencies
    for (const [taskId, dependencies] of stepDependencies) {
      const task = this.tasks.get(taskId);
      if (task) {
        task.metadata.dependencies = dependencies;
      }
    }

    console.log(
      `📊 Workflow ${workflow.name} scheduled with ${taskIds.length} tasks`,
    );
    this.emit("workflow-scheduled", { sessionId, workflow, taskIds });

    return taskIds;
  }

  /**
   * Get task status
   */
  getTaskStatus(taskId: string): AgentTask | undefined {
    return this.tasks.get(taskId);
  }

  /**
   * Get session status
   */
  getSessionStatus(sessionId: string): AgentSession | undefined {
    return this.sessions.get(sessionId);
  }

  /**
   * Get agent health status
   */
  getAgentHealth(agentId: string): AgentHealth | undefined {
    return this.agentHealth.get(agentId);
  }

  /**
   * Get system status
   */
  getSystemStatus(): {
    isRunning: boolean;
    totalAgents: number;
    totalTasks: number;
    runningTasks: number;
    queuedTasks: number;
    activeSessions: number;
    healthStatus: "healthy" | "degraded" | "unhealthy";
  } {
    const activeSessions = Array.from(this.sessions.values()).filter(
      (session) => session.status === "active",
    ).length;

    const unhealthyAgents = Array.from(this.agentHealth.values()).filter(
      (health) => health.status !== "healthy",
    ).length;

    const healthStatus =
      unhealthyAgents === 0
        ? "healthy"
        : unhealthyAgents < this.agents.size * 0.3
          ? "degraded"
          : "unhealthy";

    return {
      isRunning: this.isRunning,
      totalAgents: this.agents.size,
      totalTasks: this.tasks.size,
      runningTasks: this.runningTasks.size,
      queuedTasks: this.taskQueue.length,
      activeSessions,
      healthStatus,
    };
  }

  /**
   * Stop the orchestration system
   */
  async shutdown(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    console.log("🛑 Shutting down Agent Orchestration System...");

    // Stop background processes
    if (this.healthCheckInterval) {
      clearInterval(this.healthCheckInterval);
    }

    if (this.metricsInterval) {
      clearInterval(this.metricsInterval);
    }

    // Cancel running tasks
    for (const taskId of this.runningTasks) {
      const task = this.tasks.get(taskId);
      if (task && task.status === "running") {
        task.status = "cancelled";
        task.completedAt = new Date();
        this.emit("task-cancelled", { task });
      }
    }

    this.runningTasks.clear();
    this.isRunning = false;

    console.log("✅ Agent Orchestration System shut down successfully");
    this.emit("system-shutdown");
  }

  // Private methods

  private async registerCoreAgents(): Promise<void> {
    const coreAgents: AgentCapability[] = [
      {
        id: "autonomous-orchestrator",
        name: "Autonomous Orchestrator",
        description: "Coordinates complex workflows across multiple systems",
        category: "orchestration",
        version: "1.0.0",
        enabled: true,
        priority: 10,
        dependencies: [],
        metadata: { type: "core" },
      },
      {
        id: "workflow-engine",
        name: "Workflow Engine",
        description: "Executes predefined workflow patterns",
        category: "execution",
        version: "1.0.0",
        enabled: true,
        priority: 8,
        dependencies: ["autonomous-orchestrator"],
        metadata: { type: "core" },
      },
      {
        id: "skill-executor",
        name: "Skill Executor",
        description: "Executes individual agent skills",
        category: "execution",
        version: "1.0.0",
        enabled: true,
        priority: 7,
        dependencies: [],
        metadata: { type: "core" },
      },
    ];

    for (const agent of coreAgents) {
      await this.registerAgent(agent);
    }
  }

  private validateAgent(agent: AgentCapability): boolean {
    return !!(agent.id && agent.name && agent.description && agent.category);
  }

  private prioritizeTaskQueue(): void {
    this.taskQueue.sort((a, b) => {
      const priorityWeights = { low: 1, medium: 2, high: 3, critical: 4 };
      return priorityWeights[b.priority] - priorityWeights[a.priority];
    });
  }

  private startTaskProcessor(): void {
    const processTasks = async () => {
      if (this.runningTasks.size >= this.config.maxConcurrentTasks) {
        return;
      }

      if (this.taskQueue.length === 0) {
        return;
      }

      const task = this.taskQueue.shift();
      if (!task) return;

      // Check dependencies
      const dependencies = task.metadata.dependencies as string[] | undefined;
      if (dependencies && dependencies.length > 0) {
        const allCompleted = dependencies.every((depId) => {
          const depTask = this.tasks.get(depId);
          return (
            depTask &&
            (depTask.status === "completed" || depTask.status === "failed")
          );
        });

        if (!allCompleted) {
          // Requeue task for later processing
          this.taskQueue.push(task);
          return;
        }
      }

      this.runningTasks.add(task.id);
      task.status = "running";
      task.startedAt = new Date();

      console.log(`▶️ Starting task: ${task.description} (${task.id})`);
      this.emit("task-started", { task });

      try {
        // Execute task (placeholder - would integrate with actual agent execution)
        const result = await this.executeTaskWithAgent(task);

        task.status = "completed";
        task.result = result;
        task.completedAt = new Date();

        console.log(`✅ Task completed: ${task.description} (${task.id})`);
        this.emit("task-completed", { task, result });

        // Update session metrics
        this.updateSessionMetrics(task);
      } catch (error) {
        task.status = "failed";
        task.error = error instanceof Error ? error.message : "Unknown error";
        task.completedAt = new Date();

        console.error(
          `❌ Task failed: ${task.description} (${task.id})`,
          error,
        );
        this.emit("task-failed", { task, error });

        // Handle retries
        if (task.retries < this.config.maxRetries) {
          task.retries++;
          task.status = "pending";
          this.taskQueue.push(task);
          console.log(
            `🔄 Retrying task: ${task.description} (attempt ${task.retries})`,
          );
        }
      } finally {
        this.runningTasks.delete(task.id);
      }
    };

    // Process tasks every 100ms
    setInterval(processTasks, 100);
  }

  private async executeTaskWithAgent(task: AgentTask): Promise<any> {
    // Placeholder implementation - would integrate with actual agent capabilities
    // This would route to the appropriate agent based on task type

    const agent = this.findSuitableAgent(task.type);
    if (!agent) {
      throw new Error(`No suitable agent found for task type: ${task.type}`);
    }

    // Simulate task execution
    await new Promise((resolve) =>
      setTimeout(resolve, 1000 + Math.random() * 2000),
    );

    return {
      success: true,
      agent: agent.name,
      executionTime: Date.now() - task.startedAt!.getTime(),
      data: { message: `Task executed by ${agent.name}` },
    };
  }

  private findSuitableAgent(taskType: string): AgentCapability | undefined {
    // Simple agent selection - would be more sophisticated in production
    return Array.from(this.agents.values()).find(
      (agent) => agent.enabled && agent.category === taskType,
    );
  }

  private updateSessionMetrics(task: AgentTask): void {
    const sessionId = task.metadata.sessionId as string | undefined;
    if (!sessionId) return;

    const session = this.sessions.get(sessionId);
    if (!session) return;

    const taskDuration =
      task.completedAt!.getTime() - task.startedAt!.getTime();

    session.metrics.completedTasks++;
    session.metrics.totalExecutionTime += taskDuration;
    session.metrics.averageTaskTime =
      session.metrics.totalExecutionTime / session.metrics.completedTasks;

    if (task.status === "failed") {
      session.metrics.failedTasks++;
    }
  }

  private startHealthChecks(): void {
    this.healthCheckInterval = setInterval(() => {
      this.performHealthChecks();
    }, this.config.healthCheckInterval);
  }

  private async performHealthChecks(): Promise<void> {
    for (const [agentId, health] of this.agentHealth) {
      try {
        // Simulate health check
        const responseTime = 50 + Math.random() * 100;
        const errorRate = Math.random() * 0.1; // 0-10% error rate

        health.responseTime = responseTime;
        health.errorRate = errorRate;
        health.lastCheck = new Date();

        // Update status based on metrics
        if (errorRate > 0.05 || responseTime > 500) {
          health.status = "degraded";
        } else if (errorRate > 0.1 || responseTime > 1000) {
          health.status = "unhealthy";
        } else {
          health.status = "healthy";
        }

        this.emit("health-check-completed", { agentId, health });
      } catch (error) {
        health.status = "unhealthy";
        health.lastCheck = new Date();
        console.error(`❌ Health check failed for agent ${agentId}:`, error);
        this.emit("health-check-failed", { agentId, health, error });
      }
    }
  }

  private startMetricsCollection(): void {
    this.metricsInterval = setInterval(() => {
      this.collectSystemMetrics();
    }, 60000); // Collect metrics every minute
  }

  private async collectSystemMetrics(): Promise<void> {
    const systemStatus = this.getSystemStatus();
    const metrics = {
      timestamp: new Date(),
      systemStatus,
      agentHealth: Array.from(this.agentHealth.entries()),
      taskMetrics: {
        total: this.tasks.size,
        running: this.runningTasks.size,
        queued: this.taskQueue.length,
        completed: Array.from(this.tasks.values()).filter(
          (t) => t.status === "completed",
        ).length,
        failed: Array.from(this.tasks.values()).filter(
          (t) => t.status === "failed",
        ).length,
      },
      sessionMetrics: {
        total: this.sessions.size,
        active: Array.from(this.sessions.values()).filter(
          (s) => s.status === "active",
        ).length,
      },
    };

    // Clean up old metrics (simplified implementation)
    const cutoffTime = Date.now() - this.config.metricsRetention;
    for (const [taskId, task] of this.tasks) {
      if (task.completedAt && task.completedAt.getTime() < cutoffTime) {
        this.tasks.delete(taskId);
      }
    }

    this.emit("metrics-collected", { metrics });
  }
}

// Export singleton instance
export const agentOrchestrationSystem = new AgentOrchestrationSystem();

// Convenience functions
export async function submitTask(taskRequest: {
  type: string;
  description: string;
  priority?: "low" | "medium" | "high" | "critical";
  parameters: Record<string, any>;
  timeout?: number;
  metadata?: Record<string, any>;
}): Promise<string> {
  return agentOrchestrationSystem.submitTask(taskRequest);
}

export async function createSession(
  userId: string,
  context?: Record<string, any>,
): Promise<string> {
  return agentOrchestrationSystem.createSession(userId, context);
}

export async function executeWorkflow(
  sessionId: string,
  workflow: {
    name: string;
    description: string;
    steps: Array<{
      agentType: string;
      task: string;
      parameters: Record<string, any>;
      dependsOn?: string[];
      timeout?: number;
    }>;
  },
): Promise<string[]> {
  return agentOrchestrationSystem.executeWorkflow(sessionId, workflow);
}

export function getSystemStatus() {
  return agentOrchestrationSystem.getSystemStatus();
}

export function getTaskStatus(taskId: string) {
  return agentOrchestrationSystem.getTaskStatus(taskId);
}

export function getSessionStatus(sessionId: string) {
  return agentOrchestrationSystem.getSessionStatus(sessionId);
}

// Auto-initialize on import (optional)
if (process.env.NODE_ENV !== "test") {
  agentOrchestrationSystem.initialize().catch(console.error);
}
