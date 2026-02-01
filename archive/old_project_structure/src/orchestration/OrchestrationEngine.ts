import { EventEmitter } from "events";
import { SkillRegistry } from "../skills";
import { Logger } from "../utils/logger";

export interface AgentProfile {
  id: string;
  name: string;
  skills: string[];
  capabilities: string[];
  priority: number;
  confidence: number;
  costPerTask?: number;
  maxConcurrentTasks?: number;
  currentLoad?: number;
}

export interface Task {
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

export interface ExecutionPlan {
  id: string;
  task: Task;
  steps: ExecutionStep[];
  estimatedDuration: number;
  createdAt: Date;
  status: "pending" | "running" | "completed" | "failed";
}

export interface ExecutionStep {
  stepNumber: number;
  description: string;
  agentId: string;
  skill: string;
  parameters: any;
  estimatedDuration: number;
  dependencies: number[];
  status: "pending" | "running" | "completed" | "failed";
  result?: any;
  error?: string;
  startedAt?: Date;
  completedAt?: Date;
}

export interface AgentExecution {
  agentId: string;
  planId: string;
  step: ExecutionStep;
  status: "pending" | "running" | "completed" | "failed";
  startedAt?: Date;
  completedAt?: Date;
  result?: any;
  error?: string;
}

export interface OrchestrationConfig {
  maxConcurrentAgents: number;
  delegationConfidenceThreshold: number;
  retryAttempts: number;
  recoveryMode: "redistribute" | "failover" | "retry";
  timeoutMs?: number;
  enableMetrics?: boolean;
}

export interface ExecutionHistory {
  taskId: string;
  status: "completed" | "failed";
  createdAt: Date;
  completedAt?: Date;
  totalTime?: number;
  results?: any;
  error?: string;
}

export class OrchestrationEngine extends EventEmitter {
  private skillRegistry: SkillRegistry;
  private logger: Logger;
  private config: OrchestrationConfig;
  private agents: Map<string, AgentProfile>;
  private activeExecutions: Map<string, ExecutionPlan>;
  private taskQueue: Task[];
  private executionHistory: ExecutionHistory[];
  private agentExecutions: Map<string, AgentExecution[]>;

  constructor(skillRegistry: SkillRegistry, config: OrchestrationConfig) {
    super();
    this.skillRegistry = skillRegistry;
    this.logger = new Logger("OrchestrationEngine");
    this.config = {
      timeoutMs: 300000,
      enableMetrics: true,
      ...config,
    };

    this.agents = new Map();
    this.activeExecutions = new Map();
    this.taskQueue = [];
    this.executionHistory = [];
    this.agentExecutions = new Map();

    this.logger.info("OrchestrationEngine initialized");
  }

  async registerAgent(agent: AgentProfile): Promise<void> {
    this.agents.set(agent.id, agent);
    this.logger.info(`Agent registered: ${agent.name} (${agent.id})`);
    this.emit("agent-registered", { agentId: agent.id, agentName: agent.name });
  }

  async unregisterAgent(agentId: string): Promise<void> {
    const agent = this.agents.get(agentId);
    if (agent) {
      this.agents.delete(agentId);
      this.logger.info(`Agent unregistered: ${agent.name} (${agentId})`);
      this.emit("agent-unregistered", { agentId, agentName: agent.name });
    }
  }

  async submitTask(task: Task): Promise<ExecutionPlan> {
    this.logger.info(`Submitting task: ${task.description}`);

    // Validate task requirements
    await this.validateTaskRequirements(task);

    // Create execution plan
    const executionPlan = await this.createExecutionPlan(task);

    // Add to active executions
    this.activeExecutions.set(executionPlan.id, executionPlan);

    // Execute the plan
    this.executePlan(executionPlan).catch((error) => {
      this.logger.error(
        `Execution failed for plan ${executionPlan.id}:`,
        error,
      );
    });

    return executionPlan;
  }

  private async validateTaskRequirements(task: Task): Promise<void> {
    const missingSkills: string[] = [];

    for (const requirement of task.requirements) {
      const hasSkill = Array.from(this.agents.values()).some((agent) =>
        agent.skills.includes(requirement),
      );

      if (!hasSkill) {
        missingSkills.push(requirement);
      }
    }

    if (missingSkills.length > 0) {
      throw new Error(`Missing required skills: ${missingSkills.join(", ")}`);
    }
  }

  private async createExecutionPlan(task: Task): Promise<ExecutionPlan> {
    const planId = `plan_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    // Find matching agents
    const matchingAgents = this.findMatchingAgents(task);

    // Generate execution steps
    const steps = await this.generateExecutionSteps(task, matchingAgents);

    // Estimate total duration
    const estimatedDuration = this.estimateDuration(steps);

    const executionPlan: ExecutionPlan = {
      id: planId,
      task,
      steps,
      estimatedDuration,
      createdAt: new Date(),
      status: "pending",
    };

    this.logger.info(
      `Created execution plan ${planId} with ${steps.length} steps`,
    );
    return executionPlan;
  }

  private findMatchingAgents(task: Task): AgentProfile[] {
    const matchingAgents: AgentProfile[] = [];

    for (const agent of this.agents.values()) {
      const matchingSkills = agent.skills.filter((skill) =>
        task.requirements.includes(skill),
      );

      if (matchingSkills.length > 0) {
        matchingAgents.push({
          ...agent,
          capabilities: matchingSkills,
        });
      }
    }

    // Sort by priority and confidence
    matchingAgents.sort((a, b) => {
      if (a.priority !== b.priority) {
        return b.priority - a.priority;
      }
      return b.confidence - a.confidence;
    });

    return matchingAgents;
  }

  private async generateExecutionSteps(
    task: Task,
    agents: AgentProfile[],
  ): Promise<ExecutionStep[]> {
    const steps: ExecutionStep[] = [];
    let stepNumber = 1;

    // Generate steps based on task type
    switch (task.type) {
      case "business-automation":
        steps.push(
          ...this.generateBusinessWorkflowSteps(task, agents, stepNumber),
        );
        break;
      case "conversational":
        steps.push(
          ...this.generateConversationalSteps(task, agents, stepNumber),
        );
        break;
      case "analytical":
        steps.push(...this.generateAnalyticalSteps(task, agents, stepNumber));
        break;
      case "creative":
        steps.push(...this.generateCreativeSteps(task, agents, stepNumber));
        break;
      default:
        steps.push(...this.generateGenericSteps(task, agents, stepNumber));
    }

    return steps;
  }

  private generateBusinessWorkflowSteps(
    task: Task,
    agents: AgentProfile[],
    startStep: number,
  ): ExecutionStep[] {
    const steps: ExecutionStep[] = [];
    let stepNumber = startStep;

    // Analysis step
    steps.push({
      stepNumber: stepNumber++,
      description: `Analyze business requirements for: ${task.description}`,
      agentId:
        this.getAgentForSkill("business_analysis", agents)?.id || agents[0]?.id,
      skill: "business_analysis",
      parameters: { task, context: task.context },
      estimatedDuration: 120000,
      dependencies: [],
      status: "pending",
    });

    // Planning step
    steps.push({
      stepNumber: stepNumber++,
      description: `Create execution plan for: ${task.description}`,
      agentId: this.getAgentForSkill("planning", agents)?.id || agents[0]?.id,
      skill: "planning",
      parameters: { task, previousStep: steps[0] },
      estimatedDuration: 90000,
      dependencies: [1],
      status: "pending",
    });

    // Execution step
    steps.push({
      stepNumber: stepNumber++,
      description: `Execute business automation: ${task.description}`,
      agentId: this.getAgentForSkill("automation", agents)?.id || agents[0]?.id,
      skill: "automation",
      parameters: { task, previousSteps: steps.slice(0, 2) },
      estimatedDuration: 180000,
      dependencies: [2],
      status: "pending",
    });

    return steps;
  }

  private generateConversationalSteps(
    task: Task,
    agents: AgentProfile[],
    startStep: number,
  ): ExecutionStep[] {
    const steps: ExecutionStep[] = [];
    let stepNumber = startStep;

    steps.push({
      stepNumber: stepNumber++,
      description: `Process conversational task: ${task.description}`,
      agentId:
        this.getAgentForSkill("conversation", agents)?.id || agents[0]?.id,
      skill: "conversation",
      parameters: { task, context: task.context },
      estimatedDuration: 60000,
      dependencies: [],
      status: "pending",
    });

    return steps;
  }

  private generateAnalyticalSteps(
    task: Task,
    agents: AgentProfile[],
    startStep: number,
  ): ExecutionStep[] {
    const steps: ExecutionStep[] = [];
    let stepNumber = startStep;

    steps.push({
      stepNumber: stepNumber++,
      description: `Perform data analysis: ${task.description}`,
      agentId:
        this.getAgentForSkill("data_analysis", agents)?.id || agents[0]?.id,
      skill: "data_analysis",
      parameters: { task, context: task.context },
      estimatedDuration: 150000,
      dependencies: [],
      status: "pending",
    });

    steps.push({
      stepNumber: stepNumber++,
      description: `Generate analysis report`,
      agentId: this.getAgentForSkill("reporting", agents)?.id || agents[0]?.id,
      skill: "reporting",
      parameters: { task, previousStep: steps[0] },
      estimatedDuration: 90000,
      dependencies: [1],
      status: "pending",
    });

    return steps;
  }

  private generateCreativeSteps(
    task: Task,
    agents: AgentProfile[],
    startStep: number,
  ): ExecutionStep[] {
    const steps: ExecutionStep[] = [];
    let stepNumber = startStep;

    steps.push({
      stepNumber: stepNumber++,
      description: `Generate creative content: ${task.description}`,
      agentId:
        this.getAgentForSkill("content_creation", agents)?.id || agents[0]?.id,
      skill: "content_creation",
      parameters: { task, context: task.context },
      estimatedDuration: 120000,
      dependencies: [],
      status: "pending",
    });

    steps.push({
      stepNumber: stepNumber++,
      description: `Review and refine content`,
      agentId: this.getAgentForSkill("editing", agents)?.id || agents[0]?.id,
      skill: "editing",
      parameters: { task, previousStep: steps[0] },
      estimatedDuration: 60000,
      dependencies: [1],
      status: "pending",
    });

    return steps;
  }

  private generateGenericSteps(
    task: Task,
    agents: AgentProfile[],
    startStep: number,
  ): ExecutionStep[] {
    const steps: ExecutionStep[] = [];
    let stepNumber = startStep;

    steps.push({
      stepNumber: stepNumber++,
      description: `Execute task: ${task.description}`,
      agentId: agents[0]?.id,
      skill: task.requirements[0] || "general",
      parameters: { task, context: task.context },
      estimatedDuration: 120000,
      dependencies: [],
      status: "pending",
    });

    return steps;
  }

  private getAgentForSkill(
    skill: string,
    agents: AgentProfile[],
  ): AgentProfile | undefined {
    return agents.find((agent) => agent.skills.includes(skill));
  }

  private calculateComplexityScore(task: Task): number {
    let score = 0;

    // Base complexity based on requirements
    score += task.requirements.length * 0.1;

    // Priority increases complexity
    score += task.priority * 0.05;

    // Deadline pressure increases complexity
    if (task.deadline) {
      const timeUntilDeadline = task.deadline.getTime() - Date.now();
      if (timeUntilDeadline < 3600000)
        score += 0.3; // < 1 hour
      else if (timeUntilDeadline < 86400000)
        score += 0.2; // < 1 day
      else if (timeUntilDeadline < 604800000) score += 0.1; // < 1 week
    }

    // Dependencies increase complexity
    score += task.dependencies.length * 0.15;

    return Math.min(score, 1.0);
  }

  private estimateDuration(steps: ExecutionStep[]): number {
    return steps.reduce((total, step) => total + step.estimatedDuration, 0);
  }

  async executePlan(executionPlan: ExecutionPlan): Promise<void> {
    this.logger.info(`Executing plan ${executionPlan.id}`);
    executionPlan.status = "running";

    this.emit("execution-started", { plan: executionPlan });

    try {
      for (const step of executionPlan.steps) {
        await this.executeStep(executionPlan, step);
      }

      executionPlan.status = "completed";
      this.logger.info(`Plan ${executionPlan.id} completed successfully`);

      this.executionHistory.push({
        taskId: executionPlan.task.id,
        status: "completed",
        createdAt: executionPlan.createdAt,
        completedAt: new Date(),
        totalTime: Date.now() - executionPlan.createdAt.getTime(),
        results: executionPlan.steps.map((s) => s.result),
      });

      this.emit("execution-completed", {
        taskId: executionPlan.task.id,
        completedSteps: executionPlan.steps.filter(
          (s) => s.status === "completed",
        ),
        totalTime: Date.now() - executionPlan.createdAt.getTime(),
        results: executionPlan.steps.map((s) => s.result),
      });
    } catch (error) {
      executionPlan.status = "failed";
      this.logger.error(`Plan ${executionPlan.id} failed:`, error);

      this.executionHistory.push({
        taskId: executionPlan.task.id,
        status: "failed",
        createdAt: executionPlan.createdAt,
        completedAt: new Date(),
        error: error.message,
      });

      this.emit("execution-failed", {
        taskId: executionPlan.task.id,
        error,
        failedStep: executionPlan.steps.find((s) => s.status === "failed"),
      });

      await this.handleExecutionFailure(executionPlan, error);
    } finally {
      this.activeExecutions.delete(executionPlan.id);
    }
  }

  private async executeStep(
    executionPlan: ExecutionPlan,
    step: ExecutionStep,
  ): Promise<void> {
    // Check dependencies
    for (const dep of step.dependencies) {
      const dependency = executionPlan.steps.find((s) => s.stepNumber === dep);
      if (!dependency || dependency.status !== "completed") {
        throw new Error(`Dependency step ${dep} not completed`);
      }
    }

    step.status = "running";
    step.startedAt = new Date();

    this.emit("step-started", {
      step,
      execution: { planId: executionPlan.id, agentId: step.agentId },
    });

    try {
      const result = await this.invokeSkillForStep(executionPlan.task, step);
      step.result = result;
      step.status = "completed";
      step.completedAt = new Date();

      this.emit("step-completed", {
        step,
        execution: { planId: executionPlan.id, agentId: step.agentId, result },
      });
    } catch (error) {
      step.status = "failed";
      step.error = error.message;
      step.completedAt = new Date();

      this.emit("step-failed", {
        step,
        execution: { planId: executionPlan.id, agentId: step.agentId },
        error,
      });

      throw error;
    }
  }

  private async invokeSkillForStep(
    task: Task,
    step: ExecutionStep,
  ): Promise<any> {
    const agent = this.agents.get(step.agentId);
    if (!agent) {
      throw new Error(`Agent ${step.agentId} not found`);
    }

    // Map action to actual skill invocation
    const skillHandler = this.mapActionToSkill(step.skill);
    if (!skillHandler) {
      throw new Error(`Skill ${step.skill} not supported`);
    }

    this.logger.debug(
      `Invoking skill ${step.skill} for step ${step.stepNumber}`,
    );

    // Simulate skill execution (in real implementation, this would call actual skills)
    return new Promise((resolve, reject) => {
      setTimeout(
        () => {
          try {
            const result = {
              success: true,
              step: step.stepNumber,
              agent: agent.name,
              skill: step.skill,
              output: `Executed ${step.description} successfully`,
            };
            resolve(result);
          } catch (error) {
            reject(error);
          }
        },
        step.estimatedDuration * 0.8 +
          Math.random() * step.estimatedDuration * 0.4,
      );
    });
  }

  private mapActionToSkill(action: string): any {
    // This would map action names to actual skill implementations
    const skillMap: Record<string, any> = {
      business_analysis: () => ({
        type: "analysis",
        handler: "analyzeBusiness",
      }),
      planning: () => ({ type: "planning", handler: "createPlan" }),
      automation: () => ({ type: "automation", handler: "executeAutomation" }),
      conversation: () => ({
        type: "conversation",
        handler: "processConversation",
      }),
      data_analysis: () => ({ type: "analysis", handler: "analyzeData" }),
      reporting: () => ({ type: "reporting", handler: "generateReport" }),
      content_creation: () => ({ type: "creation", handler: "createContent" }),
      editing: () => ({ type: "editing", handler: "editContent" }),
    };

    return skillMap[action]?.();
  }

  private async handleExecutionFailure(
    executionPlan: ExecutionPlan,
    error: any,
  ): Promise<void> {
    this.logger.warn(`Handling execution failure for plan ${executionPlan.id}`);

    switch (this.config.recoveryMode) {
      case "redistribute":
        await this.redistributeWork(executionPlan);
        break;
      case "failover":
        await this.failoverToBackup(executionPlan);
        break;
      case "retry":
        await this.executeFallback(executionPlan);
        break;
      default:
        this.logger.error(
          `No recovery strategy for mode: ${this.config.recoveryMode}`,
        );
    }
  }

  private async executeFallback(executionPlan: ExecutionPlan): Promise<void> {
    if (this.config.retryAttempts > 0) {
      this.logger.info(`Retrying execution plan ${executionPlan.id}`);
      await this.delay(1000);
      await this.executePlan(executionPlan);
    }
  }

  private async redistributeWork(executionPlan: ExecutionPlan): Promise<void> {
    this.logger.info(`Redistributing work from plan ${executionPlan.id}`);

    // Find available agents for failed steps
    const failedSteps = executionPlan.steps.filter(
      (s) => s.status === "failed",
    );

    for (const step of failedSteps) {
      const availableAgents = this.findMatchingAgents(
        executionPlan.task,
      ).filter(
        (agent) =>
          agent.id !== step.agentId &&
          agent.currentLoad < (agent.maxConcurrentTasks || 3),
      );

      if (availableAgents.length > 0) {
        const newAgent = availableAgents[0];
        step.agentId = newAgent.id;
        step.status = "pending";
        this.logger.info(
          `Reassigned step ${step.stepNumber} to agent ${newAgent.name}`,
        );
      }
    }

    // Retry execution
    executionPlan.status = "pending";
    await this.executePlan(executionPlan);
  }

  private async failoverToBackup(executionPlan: ExecutionPlan): Promise<void> {
    this.logger.info(`Failing over to backup for plan ${executionPlan.id}`);

    // Create a simplified backup plan
    const backupPlan: ExecutionPlan = {
      ...executionPlan,
      id: `backup_${executionPlan.id}`,
      steps: executionPlan.steps.map((step) => ({
        ...step,
        status: "pending",
        agentId:
          this.findMatchingAgents(executionPlan.task)[0]?.id || step.agentId,
      })),
    };

    await this.executePlan(backupPlan);
  }

  private async processQueue(): Promise<void> {
    while (this.taskQueue.length > 0) {
      const task = this.taskQueue.shift();
      if (task) {
        try {
          await this.submitTask(task);
        } catch (error) {
          this.logger.error(`Failed to process queued task:`, error);
        }
      }
      await this.delay(100);
    }
  }

  private async delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  getActiveExecutions(): ExecutionPlan[] {
    return Array.from(this.activeExecutions.values());
  }

  getQueuedTasks(): Task[] {
    return [...this.taskQueue];
  }

  getExecutionHistory(): ExecutionHistory[] {
    return [...this.executionHistory];
  }

  getRegisteredAgents(): AgentProfile[] {
    return Array.from(this.agents.values());
  }

  getAgent(agentId: string): AgentProfile | undefined {
    return this.agents.get(agentId);
  }

  getSystemHealth(): {
    activeExecutions: number;
    queuedTasks: number;
    registeredAgents: number;
    successRate: number;
  } {
    const successCount = this.executionHistory.filter(
      (e) => e.status === "completed",
    ).length;
    const totalCount = this.executionHistory.length;

    return {
      activeExecutions: this.activeExecutions.size,
      queuedTasks: this.taskQueue.length,
      registeredAgents: this.agents.size,
      successRate: totalCount > 0 ? successCount / totalCount : 0,
    };
  }

  async cancelExecution(planId: string): Promise<void> {
    const execution = this.activeExecutions.get(planId);
    if (execution) {
      execution.status = "failed";
      this.activeExecutions.delete(planId);
      this.logger.info(`Cancelled execution plan ${planId}`);
      this.emit("execution-cancelled", { planId });
    }
  }

  clearHistory(): void {
    this.executionHistory = [];
    this.logger.info("Cleared execution history");
  }

  async shutdown(): Promise<void> {
    this.logger.info("Shutting down OrchestrationEngine");

    // Cancel all active executions
    for (const planId of this.activeExecutions.keys()) {
      await this.cancelExecution(planId);
    }

    // Clear queues
    this.taskQueue = [];

    this.logger.info("OrchestrationEngine shutdown complete");
  }
}
