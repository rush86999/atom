import { EventEmitter } from "events";

export interface WorkflowStep {
  type: "skill" | "condition" | "wait" | "parallel";
  action: string;
  parameters: Record<string, any>;
  dependsOn?: string[];
  next?: string;
  timeout?: number;
  retryPolicy?: RetryPolicy;
}

export interface RetryPolicy {
  maxAttempts: number;
  delay: number;
  backoffFactor: number;
}

export interface Workflow {
  name: string;
  description: string;
  steps: WorkflowStep[];
  requiredParameters: string[];
}

export interface Condition {
  type: "if" | "switch";
  expression: string;
  cases: Record<string, string>;
  default?: string;
}

export interface WorkflowDefinition {
  name: string;
  version: string;
  description: string;
  steps: WorkflowStep[];
  conditions?: Condition[];
  timeout?: number;
  retryPolicy?: RetryPolicy;
}

export interface WorkflowExecution {
  id: string;
  workflowName: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  startTime: Date;
  endTime?: Date;
  currentStep?: string;
  parameters: Record<string, any>;
  result?: any;
  error?: Error;
  steps: Map<string, WorkflowStepExecution>;
}

export interface WorkflowStepExecution {
  stepName: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  startTime?: Date;
  endTime?: Date;
  result?: any;
  error?: Error;
  attempts: number;
}

export interface WorkflowStats {
  totalExecutions: number;
  successfulExecutions: number;
  failedExecutions: number;
  averageExecutionTime: number;
  lastExecutionTime?: Date;
}

export class WorkflowService extends EventEmitter {
  private workflows: Map<string, WorkflowDefinition>;
  private availableWorkflows: Workflow[];
  private executions: Map<string, WorkflowExecution>;
  private stats: Map<string, WorkflowStats>;

  constructor() {
    super();
    this.workflows = new Map();
    this.availableWorkflows = [];
    this.executions = new Map();
    this.stats = new Map();
    this.initializeDefaultWorkflows();
  }

  private initializeDefaultWorkflows(): void {
    this.availableWorkflows = [
      {
        name: "calendar_scheduling",
        description: "Schedule meetings and events",
        steps: [
          {
            type: "skill",
            action: "calendar_create_event",
            parameters: {},
          },
        ],
        requiredParameters: ["meeting_time", "participant"],
      },
      {
        name: "financial_analysis",
        description: "Analyze financial reports and create summaries",
        steps: [
          {
            type: "skill",
            action: "analyze_financial_data",
            parameters: {},
          },
          {
            type: "skill",
            action: "generate_report",
            parameters: {},
            dependsOn: ["analyze_financial_data"],
          },
        ],
        requiredParameters: ["report_type", "time_period"],
      },
      {
        name: "document_processing",
        description: "Process and analyze documents",
        steps: [
          {
            type: "skill",
            action: "extract_text",
            parameters: {},
          },
          {
            type: "skill",
            action: "analyze_content",
            parameters: {},
            dependsOn: ["extract_text"],
          },
        ],
        requiredParameters: ["document_type"],
      },
    ];
  }

  async getAvailableWorkflows(): Promise<string[]> {
    return this.availableWorkflows.map((workflow) => workflow.name);
  }

  async getWorkflowDetails(workflowName: string): Promise<Workflow | null> {
    return this.availableWorkflows.find((w) => w.name === workflowName) || null;
  }

  async validateWorkflowParameters(
    workflowName: string,
    parameters: Record<string, any>,
  ): Promise<{ valid: boolean; missing: string[] }> {
    const workflow = this.availableWorkflows.find(
      (w) => w.name === workflowName,
    );
    if (!workflow) {
      return { valid: false, missing: [] };
    }

    const missingParams = workflow.requiredParameters.filter(
      (param) =>
        !parameters[param] &&
        parameters[param] !== false &&
        parameters[param] !== 0,
    );

    return {
      valid: missingParams.length === 0,
      missing: missingParams,
    };
  }

  async registerWorkflow(workflow: Workflow): Promise<boolean> {
    if (this.availableWorkflows.some((w) => w.name === workflow.name)) {
      return false;
    }
    this.availableWorkflows.push(workflow);
    return true;
  }

  async unregisterWorkflow(workflowName: string): Promise<boolean> {
    const index = this.availableWorkflows.findIndex(
      (w) => w.name === workflowName,
    );
    if (index === -1) {
      return false;
    }
    this.availableWorkflows.splice(index, 1);
    return true;
  }

  async listWorkflows(): Promise<Workflow[]> {
    return [...this.availableWorkflows];
  }

  async workflowExists(workflowName: string): Promise<boolean> {
    return this.availableWorkflows.some((w) => w.name === workflowName);
  }

  async executeWorkflow(
    workflowName: string,
    parameters: Record<string, any>,
  ): Promise<any> {
    const workflow = this.workflows.get(workflowName);
    if (!workflow) {
      throw new Error(`Workflow "${workflowName}" not found`);
    }

    const executionId = this.generateExecutionId();
    const execution: WorkflowExecution = {
      id: executionId,
      workflowName,
      status: "pending",
      startTime: new Date(),
      parameters,
      steps: new Map(),
    };

    this.executions.set(executionId, execution);
    this.emit("workflowStarted", execution);

    try {
      execution.status = "running";
      const result = await this.executeWorkflowSteps(workflow, execution);

      execution.status = "completed";
      execution.endTime = new Date();
      execution.result = result;

      this.updateStats(
        workflowName,
        true,
        execution.startTime,
        execution.endTime,
      );
      this.emit("workflowCompleted", execution);

      return result;
    } catch (error) {
      execution.status = "failed";
      execution.endTime = new Date();
      execution.error = error as Error;

      this.updateStats(
        workflowName,
        false,
        execution.startTime,
        execution.endTime,
      );
      this.emit("workflowFailed", execution);

      throw error;
    }
  }

  private async executeWorkflowSteps(
    workflow: WorkflowDefinition,
    execution: WorkflowExecution,
  ): Promise<any> {
    let result: any = null;

    for (const step of workflow.steps) {
      execution.currentStep = step.action;
      this.emit("stepStarted", execution, step);

      try {
        const stepResult = await this.executeStep(step, execution.parameters);
        result = stepResult;

        const stepExecution: WorkflowStepExecution = {
          stepName: step.action,
          status: "completed",
          startTime: new Date(),
          endTime: new Date(),
          result: stepResult,
          attempts: 1,
        };

        execution.steps.set(step.action, stepExecution);
        this.emit("stepCompleted", execution, step, stepResult);
      } catch (error) {
        const stepExecution: WorkflowStepExecution = {
          stepName: step.action,
          status: "failed",
          startTime: new Date(),
          endTime: new Date(),
          error: error as Error,
          attempts: 1,
        };

        execution.steps.set(step.action, stepExecution);
        this.emit("stepFailed", execution, step, error as Error);
        throw error;
      }
    }

    return result;
  }

  private async executeStep(
    step: WorkflowStep,
    parameters: Record<string, any>,
  ): Promise<any> {
    // This would integrate with the actual skill execution system
    // For now, return a mock response based on step type
    switch (step.type) {
      case "skill":
        return this.executeSkillStep(step, parameters);
      case "condition":
        return this.executeConditionStep(step, parameters);
      case "wait":
        return this.executeWaitStep(step, parameters);
      case "parallel":
        return this.executeParallelStep(step, parameters);
      default:
        throw new Error(`Unknown step type: ${step.type}`);
    }
  }

  private async executeSkillStep(
    step: WorkflowStep,
    parameters: Record<string, any>,
  ): Promise<any> {
    // Simulate skill execution
    await new Promise((resolve) => setTimeout(resolve, 100));

    return {
      success: true,
      step: step.action,
      parameters,
      timestamp: new Date().toISOString(),
    };
  }

  private async executeConditionStep(
    step: WorkflowStep,
    parameters: Record<string, any>,
  ): Promise<any> {
    // Simple condition evaluation
    return { conditionMet: true, evaluatedAt: new Date().toISOString() };
  }

  private async executeWaitStep(
    step: WorkflowStep,
    parameters: Record<string, any>,
  ): Promise<any> {
    const waitTime = step.timeout || 1000;
    await new Promise((resolve) => setTimeout(resolve, waitTime));
    return { waited: waitTime, completedAt: new Date().toISOString() };
  }

  private async executeParallelStep(
    step: WorkflowStep,
    parameters: Record<string, any>,
  ): Promise<any> {
    // Simulate parallel execution
    return { parallel: true, completedAt: new Date().toISOString() };
  }

  private generateExecutionId(): string {
    return `wf_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private updateStats(
    workflowName: string,
    success: boolean,
    startTime: Date,
    endTime: Date,
  ): void {
    const executionTime = endTime.getTime() - startTime.getTime();
    let stats = this.stats.get(workflowName);

    if (!stats) {
      stats = {
        totalExecutions: 0,
        successfulExecutions: 0,
        failedExecutions: 0,
        averageExecutionTime: 0,
      };
    }

    stats.totalExecutions++;
    if (success) {
      stats.successfulExecutions++;
    } else {
      stats.failedExecutions++;
    }

    // Update average execution time
    stats.averageExecutionTime =
      (stats.averageExecutionTime * (stats.totalExecutions - 1) +
        executionTime) /
      stats.totalExecutions;

    stats.lastExecutionTime = new Date();
    this.stats.set(workflowName, stats);
  }

  async getExecution(executionId: string): Promise<WorkflowExecution | null> {
    return this.executions.get(executionId) || null;
  }

  async getStats(workflowName: string): Promise<WorkflowStats | null> {
    return this.stats.get(workflowName) || null;
  }

  async getAllStats(): Promise<Map<string, WorkflowStats>> {
    return new Map(this.stats);
  }

  async cancelExecution(executionId: string): Promise<boolean> {
    const execution = this.executions.get(executionId);
    if (!execution || execution.status !== "running") {
      return false;
    }

    execution.status = "cancelled";
    execution.endTime = new Date();
    this.emit("workflowCancelled", execution);

    return true;
  }

  async registerWorkflowDefinition(
    definition: WorkflowDefinition,
  ): Promise<boolean> {
    if (this.workflows.has(definition.name)) {
      return false;
    }

    this.workflows.set(definition.name, definition);
    return true;
  }

  async getWorkflowDefinition(
    workflowName: string,
  ): Promise<WorkflowDefinition | null> {
    return this.workflows.get(workflowName) || null;
  }

  async listWorkflowDefinitions(): Promise<WorkflowDefinition[]> {
    return Array.from(this.workflows.values());
  }
}
