import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';
import { Logger } from '../utils/logger';
import { SkillRegistry } from '../skills';

interface AgentProfile {
  id: string;
  name: string;
  skills: string[];
  capabilities: string[];
  priority: number;
  confidence: number;
  history?: AgentExecution[];
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

interface ExecutionPlan {
  id: string;
  task: Task;
  assignedAgents: AgentProfile[];
  steps: ExecutionStep[];
  estimatedDuration: number;
  complexityScore: number;
}

interface ExecutionStep {
  agentId: string;
  stepNumber: number;
  action: string;
  inputs: any;
  expectedOutputs: string[];
  prerequisites: string[];
}

interface AgentExecution {
  agentId: string;
  taskId: string;
  stepNumber: number;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'redelegated';
  results: any;
  errors: string[];
  createdAt: Date;
  completedAt?: Date;
}

interface OrchestrationConfig {
  maxConcurrentAgents: number;
  delegationConfidenceThreshold: number;
  retryAttempts: number;
  recoveryMode: 'fallback' | 'redistribute' | 'failover';
}

export class OrchestrationEngine extends EventEmitter {
  private skillRegistry: SkillRegistry;
  private logger: Logger;
  private config: OrchestrationConfig;
  private agents: Map<string, AgentProfile> = new Map();
  private activeExecutions: Map<string, ExecutionPlan> = new Map();
  private taskQueue: Task[] = [];
  private executionHistory: AgentExecution[] = [];

  constructor(skillRegistry: SkillRegistry, config: OrchestrationConfig = {}) {
    super();
    this.skillRegistry = skillRegistry;
    this.logger = new Logger('OrchestrationEngine');
    this.config = {
      maxConcurrentAgents: 5,
      delegationConfidenceThreshold: 0.7,
      retryAttempts: 3,
      recoveryMode: 'redistribute',
      ...config
    };
  }

  async registerAgent(agentProfile: AgentProfile): Promise<void> {
    this.agents.set(agentProfile.id, agentProfile);
    this.logger.info(`Agent ${agentProfile.name} registered with skills: ${agentProfile.skills.join(', ')}`);
    this.emit('agent-registered', agentProfile);
  }

  async unregisterAgent(agentId: string): Promise<void> {
    if (this.agents.has(agentId)) {
      const agent = this.agents.get(agentId)!;
      this.agents.delete(agentId);
      this.logger.info(`Agent ${agent.name} unregistered`);
      this.emit('agent-unregistered', { agentId });
    }
  }

  async submitTask(task: Task): Promise<ExecutionPlan> {
    this.logger.info(`New task submitted: ${task.description}`);

    // Validate task requirements
    const validationResult = await this.validateTaskRequirements(task);
    if (!validationResult.valid) {
      throw new Error(`Task validation failed: ${validationResult.errors.join(', ')}`);
    }

    // Generate execution plan
    const plan = await this.createExecutionPlan(task);

    // Add to queue or execute immediately based on priority
    if (task.priority >= 8) {
      await this.executePlan(plan);
    } else {
      this.taskQueue.push(task);
      this.processQueue();
    }

    return plan;
  }

  async createExecutionPlan(task: Task): Promise<ExecutionPlan> {
    const availableAgents = Array.from(this.agents.values());
    const matchingAgents = this.findMatchingAgents(task, availableAgents);

    // Calculate complexity score based on requirements
    const complexityScore = this.calculateComplexityScore(task);

    // Create execution steps
    const steps = await this.generateExecutionSteps(task, matchingAgents);
    const estimatedDuration = this.estimateDuration(steps);

    return {
      id: uuidv4(),
      task,
      assignedAgents: matchingAgents,
      steps,
      estimatedDuration,
      complexityScore
    };
  }

  private async validateTaskRequirements(task: Task): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = [];

    for (const requirement of task.requirements) {
      const hasSkill = Array.from(this.agents.values()).some(agent =>
        agent.skills.includes(requirement) || agent.capabilities.includes(requirement)
      );

      if (!hasSkill) {
        errors.push(`No agent available for requirement: ${requirement}`);
      }
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  private findMatchingAgents(task: Task, availableAgents: AgentProfile[]): AgentProfile[] {
    const matchingAgents: AgentProfile[] = [];

    for (const agent of availableAgents) {
      const hasAllSkills = task.requirements.every(req =>
        agent.skills.includes(req) || agent.capabilities.includes(req)
      );

      if (hasAllSkills) {
        const priorityMultiplier = agent.priority * agent.confidence;
        matchingAgents.push({ ...agent, confidence: priorityMultiplier });
      }
    }

    // Sort by confidence and priority
    return matchingAgents
      .sort((a, b) => (b.confidence * b.priority) - (a.confidence * a.priority))
      .slice(0, this.config.maxConcurrentAgents);
  }

  private async generateExecutionSteps(
    task: Task,
    agents: AgentProfile[]
  ): Promise<ExecutionStep[]> {
    const steps: ExecutionStep[] = [];
    const agentMap = new Map(agents.map(a => [a.id, a]));

    let stepNumber = 1;

    // Handle task dependencies first
    if (task.dependencies.length > 0) {
      for (const dependency of task.dependencies) {
        steps.push({
          agentId: agents[0]?.id || 'default-agent',
          stepNumber: stepNumber++,
          action: 'resolve-dependency',
          inputs: { dependency },
          expectedOutputs: [`dependency-${dependency}-resolved`],
          prerequisites: []
        });
      }
    }

    // Generate main execution steps based on task type
    switch (task.type) {
      case 'business-workflow':
        steps.push(...this.generateBusinessWorkflowSteps(task, agents, agentMap));
        break;
      case 'conversational':
        steps.push(...this.generateConversationalSteps(task, agents));
        break;
      case 'analytical':
        steps.push(...this.generateAnalyticalSteps(task, agents));
        break;
      case 'creative':
        steps.push(...this.generateCreativeSteps(task, agents));
        break;
      default:
        steps.push(...this.generateGenericSteps(task, agents));
    }

    return steps;
  }

  private generateBusinessWorkflowSteps(
    task: Task,
    agents: AgentProfile[],
    agentMap: Map<string, AgentProfile>
  ): ExecutionStep[] {
    const steps: ExecutionStep[] = [];
    let stepNumber = 1;

    // Setup phase
    steps.push({
      agentId: this.getAgentForSkill('business-setup', agents),
      stepNumber: stepNumber++,
      action: 'analyze-requirements',
      inputs: task.context,
      expectedOutputs: ['requirements-analysis'],
      prerequisites: []
    });

    // Execution phase
    steps.push({
      agentId: this.getAgentForSkill('business-execution', agents),
      stepNumber: stepNumber++,
      action: 'execute-business-flow',
      inputs: task.context,
      expectedOutputs: ['workflow-execution-results'],
      prerequisites: ['requirements-analysis']
    });

    return steps;
  }

  private generateConversationalSteps(task: Task, agents: AgentProfile[]): ExecutionStep[] {
    const conversationalAgent = agents.find(a => a.capabilities.includes('nlp'));

    return [{
      agentId: conversationalAgent?.id || agents[0]?.id || 'default',
      stepNumber: 1,
      action: 'process-conversation',
      inputs: task.description,
      expectedOutputs: ['conversation-response'],
      prerequisites: []
    }];
  }

  private generateAnalyticalSteps(task: Task, agents: AgentProfile[]): ExecutionStep[] {
    return [{
      agentId: this.getAgentForSkill('analysis', agents),
      stepNumber: 1,
      action: 'perform-analysis',
      inputs: task.context,
      expectedOutputs: ['analysis-report', 'insights'],
      prerequisites: task.dependencies.map(d => `dependency-${d}-resolved`)
    }];
  }

  private generateCreativeSteps(task: Task, agents: AgentProfile[]): ExecutionStep[] {
    const creativeAgent = agents.find(a => a.capabilities.includes('creative'));

    return [{
      agentId: creativeAgent?.id || agents[0]?.id || 'default',
      stepNumber: 1,
      action: 'generate-creative-content',
      inputs: task.context,
      expectedOutputs: ['creative-output', 'formatted-content'],
      prerequisites: []
    }];
  }

  private generateGenericSteps(task: Task, agents: AgentProfile[]): ExecutionStep[] {
    return [{
      agentId: agents[0]?.id || 'default',
      stepNumber: 1,
      action: 'execute-generic-task',
      inputs: task.context,
      expectedOutputs: ['task-results'],
      prerequisites: []
    }];
  }

  private getAgentForSkill(skill: string, agents: AgentProfile[]): string {
    const agent = agents.find(a => a.skills.includes(skill) || a.capabilities.includes(skill));
    return agent?.id || agents[0]?.id || 'default';
  }

  private calculateComplexityScore(task: Task): number {
    let score = 0;

    // Base score from requirements
    score += task.requirements.length * 2;

    // Priority multiplier
    score += task.priority * 0.5;

    // Dependencies
    score += task.dependencies.length * 1.5;

    // Time sensitivity
    if (task.deadline) {
      const hoursUntilDeadline = (task.deadline.getTime() - Date.now()) / (1000 * 60 * 60);
      if (hoursUntilDeadline < 24) score += 5;
      else if (hoursUntilDeadline < 72) score += 3;
    }

    return Math.min(score, 10); // Cap at 10
  }

  private estimateDuration(steps: ExecutionStep[]): number {
    const baseTimePerStep = 30; // seconds
    return steps.length * baseTimePerStep * (1.5 + Math.random() * 0.5);
  }

  async executePlan(plan: ExecutionPlan): Promise<any> {
    this.logger.info(`Executing plan ${plan.id} for task: ${plan.task.description}`);

    const executionContext = {
      planId: plan.id,
      startTime: Date.now(),
      completedSteps: [],
      errors: []
    };

    try {
      this.activeExecutions.set(plan.id, plan);
      this.emit('execution-started', { plan });

      // Execute each step sequentially
      for (const step of plan.steps) {
        const result = await this.executeStep(step, executionContext);

        if (result.status === 'failed') {
          executionContext.errors.push(...result.errors);
          await this.handleExecutionFailure(plan, step, result.errors);
          break;
        }

        executionContext.completedSteps.push({
          step: step.stepNumber,
          result: result.results
        });
      }

      const finalResult = {
        planId: plan.id,
        taskId: plan.task.id,
        completedSteps: executionContext.completedSteps,
        totalTime: Date.now() - executionContext.startTime,
        success: executionContext.errors.length === 0
      };

      this.activeExecutions.delete(plan.id);
      this.executionHistory.push({
        agentId: 'combined',
        taskId: plan.task.id,
        stepNumber: plan.steps.length,
        status: finalResult.success ? 'completed' : 'failed',
        results: finalResult,
        errors: executionContext.errors,
        createdAt: new Date()
      });

      this.emit('execution-completed', finalResult);
      return finalResult;

    } catch (error) {
      this.logger.error(`Execution failed for plan ${plan.id}`, error);
      this.activeExecutions.delete(plan.id);

      const errorResult = {
        planId: plan.id,
        taskId: plan.task.id,
        error: error.message,
        status: 'failed'
      };

      this.emit('execution-failed', errorResult);
      throw error;
    }
  }

  private async executeStep(step: ExecutionStep, context: any): Promise<{
    status: 'completed' | 'failed';
    results: any;
    errors: string[];
  }> {
    const agent = this.agents.get(step.agentId);
    if (!agent) {
      return {
        status: 'failed',
        results: null,
        errors: [`Agent ${step.agentId} not found`]
      };
    }

    const execution: AgentExecution = {
      agentId: step.agentId,
      taskId: context.planId,
      stepNumber: step.stepNumber,
      status: 'running',
      results: {},
      errors: [],
      createdAt: new Date()
    };

    try {
      this.emit('step-started', { execution, step });

      // Execute with appropriate skill
      const result = await this.invokeSkillForStep(step, agent);

      execution.status = 'completed';
      execution.results = result;
      execution.completedAt = new Date();

      this.emit('step-completed', { execution, step });

      return {
        status: 'completed',
        results: result,
        errors: []
      };

    } catch (error) {
      execution.status = 'failed';
      execution.errors = [error.message];
      execution.completedAt = new Date();

      this.emit('step-failed', { execution, error });

      return {
        status: 'failed',
        results: null,
        errors: [error.message]
      };
    }
  }

  private async invokeSkillForStep(step: ExecutionStep, agent: AgentProfile): Promise<any> {
    // Find appropriate skill from task type
    const skillName = this.mapActionToSkill(step.action);

    if (!skillName) {
      throw new Error(`No skill found for action: ${step.action}`);
    }

    // Create execution context
    const context = {
      agentId: agent.id,
      action: step.action,
      inputs: step.inputs,
      expectedOutputs: step.expectedOutputs,
      prerequisites: step.prerequisites
    };

    // Execute skill with retry logic
    const maxRetries = this.config.retryAttempts;
    let lastError: Error | null = null;

    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        // Get skill from registry and execute
        const skill = this.skillRegistry.getSkill(skillName);
        if (!skill) {
          throw new Error(`Skill ${skillName} not found in registry`);
        }

        const result = await skill.execute(context);
        return result;
      } catch (error) {
        lastError = error;

        if (attempt < maxRetries - 1) {
          await this.delay(Math.pow(2, attempt) * 1000); // Exponential backoff
          this.logger.warn(`Retry attempt ${attempt + 1} for ${skillName}`);
        }
      }
    }

    throw lastError || new Error(`Failed to execute ${skillName} after ${maxRetries} attempts`);
  }

  private mapActionToSkill(action: string): string | undefined {
    const skillMapping: Record<string, string> = {
      'analyze-requirements': 'business-analysis',
      'execute-business-flow': 'business-execution',
      'process-conversation': 'conversational-ai',
      'perform-analysis': 'data-analysis',
      'generate-creative-content': 'content-creation'
    };

    return skillMapping[action];
  }

  private async handleExecutionFailure(plan: ExecutionPlan, failedStep: ExecutionStep, errors: string[]): Promise<void> {
    this.logger.error(`Handling failure for plan ${plan.id}`, { failedStep, errors });

    switch (this.config.recoveryMode) {
      case 'fallback':
        await this.executeFallback(plan, failedStep);
        break;
      case 'redistribute':
        await this.redistributeWork(plan, failedStep);
        break;
      case 'failover':
        this.failoverToBackup(plan);
        break;
    }
  }

  private async executeFallback(plan: ExecutionPlan, failedStep: ExecutionStep): Promise<void> {
    this.logger.info(`Executing fallback for step ${failedStep.stepNumber}`);

    // Try with simpler/cheaper agents or less complex approach
    const fallbackAgent = 'generic-fallback-agent';
    const fallbackResult = await this.invokeSkillForStep({
      ...failedStep,
      agentId: fallbackAgent
    }, this.agents.get(fallbackAgent)!);
  }

  private async redistributeWork(plan: ExecutionPlan, failedStep: ExecutionStep): Promise<void> {
    this.logger.info(`Redistributing work from failed step ${failedStep.stepNumber}`);

    const availableAgents = Array.from(this.agents.values());
    const newAgent = availableAgents.find(a => a.id !== failedStep.agentId);

    if (newAgent) {
      const newResult = await this.invokeSkillForStep({
        ...failedStep,
        agentId: newAgent.id
      }, newAgent);
    }
  }

  private failoverToBackup(plan: ExecutionPlan): void {
    this.logger.info(`Initiating failover to backup system for plan ${plan.id}`);
    this.emit('failover-triggered', { planId: plan.id });
  }

  private async processQueue(): Promise<void> {
if (this.taskQueue.length === 0) return;

while (this.taskQueue.length > 0 && this.activeExecutions.size < this.config.maxConcurrentAgents) {
  const task = this.taskQueue.shift()!;
  const plan = await this.createExecutionPlan(task);
  await this.executePlan(plan);
}
}

private async delay(ms: number): Promise<void> {
return new Promise(resolve => setTimeout(resolve, ms));
}

// Public methods for monitoring and management
getActiveExecutions(): ExecutionPlan[] {
return Array.from(this.activeExecutions.values());
}

getQueuedTasks(): Task[] {
return [...this.taskQueue];
}

getExecutionHistory(): AgentExecution[] {
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
+    const successCount = this.executionHistory.filter(e => e.status === 'completed').length;
+    const totalCount = this.executionHistory.length;
+
+    return {
+      activeExecutions: this.activeExecutions.size,
+      queuedTasks: this.taskQueue.length,
+      registeredAgents: this.agents.size,
+      successRate: totalCount > 0 ? successCount / totalCount : 0
+    };
+  }
+}
+  }
+
+  getExecutionHistory(): AgentExecution[]
