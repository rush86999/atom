import { WorkflowExecutionEngine, WorkflowTrigger, WorkflowExecutionResult } from './WorkflowExecutionEngine';
import { Workflow, Integration } from '../types';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAppStore } from '../store';

export class RealtimeWorkflowService {
  private executionEngine: WorkflowExecutionEngine;
  private workflows: Workflow[] = [];
  private integrations: Integration[] = [];

  constructor(userId: string) {
    this.executionEngine = new WorkflowExecutionEngine(userId);
    this.setupRealtimeListeners();
  }

  private setupRealtimeListeners(): void {
    // Listen for workflow triggers from WebSocket
    const { on } = useWebSocket({ enabled: true });

    // Integration-specific triggers
    on('github:new-issue', (data) => this.handleTrigger('github_new_issue', data));
    on('gmail:new-email', (data) => this.handleTrigger('gmail_new_email', data));
    on('notion:new-task', (data) => this.handleTrigger('notion_new_task', data));
    on('calendar:event-created', (data) => this.handleTrigger('calendar_event_created', data));
    on('slack:new-message', (data) => this.handleTrigger('slack_new_message', data));

    // Generic workflow execution trigger
    on('workflow:trigger', (data) => this.handleTrigger(data.triggerType, data.payload));

    // Listen for execution results to update UI
    this.executionEngine.on('workflow-executed', (result: WorkflowExecutionResult) => {
      this.handleExecutionResult(result);
    });

    this.executionEngine.on('workflow-execution-failed', (result: WorkflowExecutionResult) => {
      this.handleExecutionFailure(result);
    });
  }

  private async handleTrigger(triggerType: string, payload: any): Promise<void> {
    console.log(`[RealtimeWorkflowService] Received trigger: ${triggerType}`, payload);

    // Find workflows that match this trigger
    const matchingWorkflows = this.workflows.filter(workflow =>
      workflow.enabled && workflow.triggers.some(trigger => trigger.type === triggerType)
    );

    if (matchingWorkflows.length === 0) {
      console.log(`No enabled workflows found for trigger: ${triggerType}`);
      return;
    }

    // Execute matching workflows
    for (const workflow of matchingWorkflows) {
      const trigger: WorkflowTrigger = {
        workflowId: workflow.id,
        triggerType,
        payload,
        timestamp: new Date()
      };

      try {
        const result = await this.executionEngine.executeWorkflow(workflow.id, trigger);
        console.log(`Workflow ${workflow.name} executed:`, result);
      } catch (error) {
        console.error(`Failed to execute workflow ${workflow.name}:`, error);
      }
    }
  }

  private handleExecutionResult(result: WorkflowExecutionResult): void {
    const { updateWorkflow, addNotification } = useAppStore.getState();

    // Update workflow stats in store
    updateWorkflow(result.workflowId, {
      executionCount: this.executionEngine.getWorkflow(result.workflowId)?.executionCount || 0,
      lastExecuted: new Date().toISOString()
    });

    // Show success notification
    const workflow = this.executionEngine.getWorkflow(result.workflowId);
    if (workflow) {
      addNotification({
        type: 'success',
        title: 'Workflow Executed',
        message: `Workflow "${workflow.name}" completed successfully in ${result.executionTime}ms`
      });
    }

    // Emit real-time update via WebSocket
    const { emit } = useWebSocket({ enabled: true });
    emit('workflow:executed', {
      workflowId: result.workflowId,
      success: true,
      executionTime: result.executionTime,
      result: result.result,
      timestamp: new Date().toISOString()
    });
  }

  private handleExecutionFailure(result: WorkflowExecutionResult): void {
    const { addNotification } = useAppStore.getState();

    // Show error notification
    const workflow = this.executionEngine.getWorkflow(result.workflowId);
    if (workflow) {
      addNotification({
        type: 'error',
        title: 'Workflow Execution Failed',
        message: `Workflow "${workflow.name}" failed: ${result.error}`
      });
    }

    // Emit real-time update via WebSocket
    const { emit } = useWebSocket({ enabled: true });
    emit('workflow:execution-failed', {
      workflowId: result.workflowId,
      success: false,
      executionTime: result.executionTime,
      error: result.error,
      timestamp: new Date().toISOString()
    });
  }

  public async initialize(workflows: Workflow[], integrations: Integration[]): Promise<void> {
    this.workflows = workflows;
    this.integrations = integrations;
    await this.executionEngine.initialize(workflows, integrations);
  }

  public async shutdown(): Promise<void> {
    await this.executionEngine.shutdown();
  }

  public async executeWorkflowManually(workflowId: string, payload?: any): Promise<WorkflowExecutionResult> {
    const trigger: WorkflowTrigger = {
      workflowId,
      triggerType: 'manual',
      payload: payload || {},
      timestamp: new Date()
    };

    return await this.executionEngine.executeWorkflow(workflowId, trigger);
  }

  public getExecutionEngine(): WorkflowExecutionEngine {
    return this.executionEngine;
  }
}
