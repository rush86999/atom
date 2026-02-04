import { v4 as uuidv4 } from 'uuid';

/**
 * Workflow Builder
 * 
 * Fluent API for building complex workflows with type safety
 * and validation.
 */

import { 
  WorkflowDefinition, 
  WorkflowStep, 
  WorkflowTrigger, 
  ActionType 
} from '../MultiIntegrationWorkflowEngine';

export class WorkflowBuilder {
  private workflow: Partial<WorkflowDefinition>;
  private stepCounter: number = 1;
  private triggerCounter: number = 1;

  constructor(
    id: string,
    name: string,
    description: string = '',
    category: string = 'automation'
  ) {
    this.workflow = {
      id,
      name,
      description,
      category,
      version: '1.0.0',
      steps: [],
      triggers: [],
      variables: {},
      settings: {
        timeout: 300000,
        retryPolicy: { maxAttempts: 3, delay: 5000 },
        priority: 'normal',
        parallelExecution: false,
      },
      integrations: [],
      tags: [],
      enabled: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
  }

  // Basic workflow configuration
  description(description: string): WorkflowBuilder {
    this.workflow.description = description;
    return this;
  }

  version(version: string): WorkflowBuilder {
    this.workflow.version = version;
    return this;
  }

  category(category: string): WorkflowBuilder {
    this.workflow.category = category;
    return this;
  }

  priority(priority: 'low' | 'normal' | 'high' | 'critical'): WorkflowBuilder {
    if (this.workflow.settings) {
      this.workflow.settings.priority = priority;
    }
    return this;
  }

  timeout(timeout: number): WorkflowBuilder {
    if (this.workflow.settings) {
      this.workflow.settings.timeout = timeout;
    }
    return this;
  }

  parallelExecution(enabled: boolean = true): WorkflowBuilder {
    if (this.workflow.settings) {
      this.workflow.settings.parallelExecution = enabled;
    }
    return this;
  }

  variables(vars: Record<string, any>): WorkflowBuilder {
    this.workflow.variables = { ...this.workflow.variables, ...vars };
    return this;
  }

  tags(...tags: string[]): WorkflowBuilder {
    this.workflow.tags = [...(this.workflow.tags || []), ...tags];
    return this;
  }

  // Step builders
  integrationAction(
    name: string,
    integrationId: string,
    action: string,
    parameters: Record<string, any> = {}
  ): StepBuilder {
    const stepId = `step-${this.stepCounter++}`;
    
    const step: WorkflowStep = {
      id: stepId,
      name,
      type: 'integration_action',
      integrationId,
      action,
      parameters,
      dependsOn: [],
      retryPolicy: { maxAttempts: 3, delay: 1000, backoffMultiplier: 2 },
      timeout: 30000,
      metadata: {},
    };

    return new StepBuilder(step, this);
  }

  dataTransform(
    name: string,
    transformType: string,
    parameters: Record<string, any> = {}
  ): StepBuilder {
    const stepId = `step-${this.stepCounter++}`;
    
    const step: WorkflowStep = {
      id: stepId,
      name,
      type: 'data_transform',
      parameters: { transformType, ...parameters },
      dependsOn: [],
      retryPolicy: { maxAttempts: 2, delay: 500, backoffMultiplier: 1.5 },
      timeout: 15000,
      metadata: {},
    };

    return new StepBuilder(step, this);
  }

  condition(
    name: string,
    condition: Record<string, any>
  ): StepBuilder {
    const stepId = `step-${this.stepCounter++}`;
    
    const step: WorkflowStep = {
      id: stepId,
      name,
      type: 'condition',
      parameters: { condition },
      dependsOn: [],
      retryPolicy: { maxAttempts: 1, delay: 1000, backoffMultiplier: 1 },
      timeout: 5000,
      metadata: {},
    };

    return new StepBuilder(step, this);
  }

  wait(
    name: string,
    duration: number
  ): StepBuilder {
    const stepId = `step-${this.stepCounter++}`;
    
    const step: WorkflowStep = {
      id: stepId,
      name,
      type: 'wait',
      parameters: { duration },
      dependsOn: [],
      retryPolicy: { maxAttempts: 1, delay: 1000, backoffMultiplier: 1 },
      timeout: duration + 5000,
      metadata: {},
    };

    return new StepBuilder(step, this);
  }

  webhook(
    name: string,
    url: string,
    payload: Record<string, any> = {}
  ): StepBuilder {
    const stepId = `step-${this.stepCounter++}`;
    
    const step: WorkflowStep = {
      id: stepId,
      name,
      type: 'webhook',
      parameters: { url, payload },
      dependsOn: [],
      retryPolicy: { maxAttempts: 3, delay: 2000, backoffMultiplier: 2 },
      timeout: 15000,
      metadata: {},
    };

    return new StepBuilder(step, this);
  }

  notification(
    name: string,
    type: string,
    recipients: string | string[],
    message: string
  ): StepBuilder {
    const stepId = `step-${this.stepCounter++}`;
    
    const step: WorkflowStep = {
      id: stepId,
      name,
      type: 'notification',
      parameters: { 
        type, 
        recipients: Array.isArray(recipients) ? recipients : [recipients], 
        message 
      },
      dependsOn: [],
      retryPolicy: { maxAttempts: 2, delay: 1000, backoffMultiplier: 1.5 },
      timeout: 10000,
      metadata: {},
    };

    return new StepBuilder(step, this);
  }

  parallel(
    name: string,
    ...steps: StepBuilder[]
  ): StepBuilder {
    const stepId = `step-${this.stepCounter++}`;
    
    const step: WorkflowStep = {
      id: stepId,
      name,
      type: 'parallel',
      parameters: { 
        steps: steps.map(sb => sb.build()) 
      },
      dependsOn: [],
      retryPolicy: { maxAttempts: 1, delay: 1000, backoffMultiplier: 1 },
      timeout: 60000,
      metadata: {},
    };

    return new StepBuilder(step, this);
  }

  // Trigger builders
  manualTrigger(name: string = 'manual'): TriggerBuilder {
    const triggerId = `trigger-${this.triggerCounter++}`;
    
    const trigger: WorkflowTrigger = {
      id: triggerId,
      type: 'manual',
      enabled: true,
      metadata: {},
    };

    return new TriggerBuilder(trigger, this);
  }

  scheduledTrigger(name: string, schedule: string): TriggerBuilder {
    const triggerId = `trigger-${this.triggerCounter++}`;
    
    const trigger: WorkflowTrigger = {
      id: triggerId,
      type: 'scheduled',
      schedule,
      enabled: true,
      metadata: {},
    };

    return new TriggerBuilder(trigger, this);
  }

  webhookTrigger(name: string, path: string): TriggerBuilder {
    const triggerId = `trigger-${this.triggerCounter++}`;
    
    const trigger: WorkflowTrigger = {
      id: triggerId,
      type: 'webhook',
      webhookPath: path,
      enabled: true,
      metadata: {},
    };

    return new TriggerBuilder(trigger, this);
  }

  integrationEventTrigger(name: string, integrationId: string, eventType: string): TriggerBuilder {
    const triggerId = `trigger-${this.triggerCounter++}`;
    
    const trigger: WorkflowTrigger = {
      id: triggerId,
      type: 'integration_event',
      integrationId,
      eventType,
      enabled: true,
      metadata: {},
    };

    return new TriggerBuilder(trigger, this);
  }

  // Internal methods
  addStep(step: WorkflowStep): WorkflowBuilder {
    if (!this.workflow.steps) {
      this.workflow.steps = [];
    }
    this.workflow.steps.push(step);
    return this;
  }

  addTrigger(trigger: WorkflowTrigger): WorkflowBuilder {
    if (!this.workflow.triggers) {
      this.workflow.triggers = [];
    }
    this.workflow.triggers.push(trigger);
    return this;
  }

  addIntegration(integrationId: string): WorkflowBuilder {
    if (!this.workflow.integrations) {
      this.workflow.integrations = [];
    }
    if (!this.workflow.integrations.includes(integrationId)) {
      this.workflow.integrations.push(integrationId);
    }
    return this;
  }

  // Build methods
  build(): WorkflowDefinition {
    if (!this.workflow.steps || this.workflow.steps.length === 0) {
      throw new Error('Workflow must have at least one step');
    }

    if (!this.workflow.triggers || this.workflow.triggers.length === 0) {
      throw new Error('Workflow must have at least one trigger');
    }

    return this.workflow as WorkflowDefinition;
  }

  validate(): { valid: boolean; errors: string[] } {
    const errors: string[] = [];

    if (!this.workflow.id) {
      errors.push('Workflow ID is required');
    }

    if (!this.workflow.name) {
      errors.push('Workflow name is required');
    }

    if (!this.workflow.steps || this.workflow.steps.length === 0) {
      errors.push('Workflow must have at least one step');
    }

    if (!this.workflow.triggers || this.workflow.triggers.length === 0) {
      errors.push('Workflow must have at least one trigger');
    }

    // Validate step dependencies
    if (this.workflow.steps) {
      const stepIds = new Set(this.workflow.steps.map(s => s.id));
      
      for (const step of this.workflow.steps) {
        for (const depId of step.dependsOn) {
          if (!stepIds.has(depId)) {
            errors.push(`Step ${step.id} depends on non-existent step ${depId}`);
          }
        }
      }

      // Check for circular dependencies
      const visited = new Set<string>();
      const recursionStack = new Set<string>();

      const hasCircularDependency = (stepId: string): boolean => {
        if (recursionStack.has(stepId)) {
          return true;
        }
        if (visited.has(stepId)) {
          return false;
        }

        visited.add(stepId);
        recursionStack.add(stepId);

        const step = this.workflow.steps!.find(s => s.id === stepId);
        if (step) {
          for (const depId of step.dependsOn) {
            if (hasCircularDependency(depId)) {
              return true;
            }
          }
        }

        recursionStack.delete(stepId);
        return false;
      };

      for (const step of this.workflow.steps) {
        if (hasCircularDependency(step.id)) {
          errors.push(`Circular dependency detected involving step ${step.id}`);
          break;
        }
      }
    }

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  toJSON(): string {
    return JSON.stringify(this.build(), null, 2);
  }
}

export class StepBuilder {
  private step: WorkflowStep;
  private workflowBuilder: WorkflowBuilder;

  constructor(step: WorkflowStep, workflowBuilder: WorkflowBuilder) {
    this.step = step;
    this.workflowBuilder = workflowBuilder;
  }

  parameters(params: Record<string, any>): StepBuilder {
    this.step.parameters = { ...this.step.parameters, ...params };
    return this;
  }

  timeout(timeout: number): StepBuilder {
    this.step.timeout = timeout;
    return this;
  }

  retry(maxAttempts: number, delay: number = 1000, backoffMultiplier: number = 2): StepBuilder {
    this.step.retryPolicy = { maxAttempts, delay, backoffMultiplier };
    return this;
  }

  dependsOn(...stepIds: string[]): StepBuilder {
    this.step.dependsOn = [...this.step.dependsOn, ...stepIds];
    return this;
  }

  condition(field: string, operator: string, value: any): StepBuilder {
    this.step.condition = { field, operator, value };
    return this;
  }

  errorHandler(stepId: string): StepBuilder {
    this.step.errorHandler = stepId;
    return this;
  }

  metadata(meta: Record<string, any>): StepBuilder {
    this.step.metadata = { ...this.step.metadata, ...meta };
    return this;
  }

  // Add step to workflow and return workflow builder
  add(): WorkflowBuilder {
    // Track integration usage
    if (this.step.integrationId) {
      this.workflowBuilder.addIntegration(this.step.integrationId);
    }

    return this.workflowBuilder.addStep(this.step);
  }

  // Get the built step
  build(): WorkflowStep {
    return this.step;
  }
}

export class TriggerBuilder {
  private trigger: WorkflowTrigger;
  private workflowBuilder: WorkflowBuilder;

  constructor(trigger: WorkflowTrigger, workflowBuilder: WorkflowBuilder) {
    this.trigger = trigger;
    this.workflowBuilder = workflowBuilder;
  }

  enabled(enabled: boolean = true): TriggerBuilder {
    this.trigger.enabled = enabled;
    return this;
  }

  condition(condition: Record<string, any>): TriggerBuilder {
    this.trigger.condition = condition;
    return this;
  }

  metadata(meta: Record<string, any>): TriggerBuilder {
    this.trigger.metadata = { ...this.trigger.metadata, ...meta };
    return this;
  }

  // Add trigger to workflow and return workflow builder
  add(): WorkflowBuilder {
    // Track integration usage
    if (this.trigger.integrationId) {
      this.workflowBuilder.addIntegration(this.trigger.integrationId);
    }

    return this.workflowBuilder.addTrigger(this.trigger);
  }

  // Get the built trigger
  build(): WorkflowTrigger {
    return this.trigger;
  }
}

// Convenience functions for creating common workflow patterns
export class WorkflowPatterns {
  static createSyncWorkflow(
    id: string,
    name: string,
    sourceIntegration: string,
    targetIntegration: string,
    mapping: Record<string, string>
  ): WorkflowBuilder {
    return new WorkflowBuilder(id, name, `Sync data from ${sourceIntegration} to ${targetIntegration}`)
      .integrationAction('Listen to source events', sourceIntegration, 'listen_events')
        .add()
      .dataTransform('Transform data', 'map_fields', { mapping })
        .add()
      .integrationAction('Create/update target', targetIntegration, 'upsert_record')
        .add()
      .notification('Send confirmation', 'slack', '#notifications', '✅ Sync completed: {{recordId}}')
        .add()
      .tags('sync', sourceIntegration, targetIntegration);
  }

  static createMonitorWorkflow(
    id: string,
    name: string,
    serviceIntegration: string,
    threshold: number,
    alertRecipients: string[]
  ): WorkflowBuilder {
    return new WorkflowBuilder(id, name, `Monitor ${serviceIntegration} health and send alerts`)
      .scheduledTrigger('Health check', '*/5 * * * *')
        .add()
      .integrationAction('Check service health', serviceIntegration, 'health_check')
        .add()
      .condition('Check threshold', {
        field: 'health.score',
        operator: 'lt',
        value: threshold,
      })
        .add()
      .notification('Send alert', 'email', alertRecipients, '🚨 Service health degraded: {{health.score}}')
        .add()
      .tags('monitoring', 'health', serviceIntegration)
      .priority('high');
  }

  static createDataProcessingWorkflow(
    id: string,
    name: string,
    sourceIntegration: string,
    transformations: Array<{ type: string; config: Record<string, any> }>
  ): WorkflowBuilder {
    const builder = new WorkflowBuilder(id, name, `Process and transform data from ${sourceIntegration}`)
      .integrationAction('Fetch data', sourceIntegration, 'fetch_data')
        .add();

    // Add transformation steps
    transformations.forEach((transform, index) => {
      builder.dataTransform(`Transform ${index + 1}`, transform.type, transform.config).add();
    });

    return builder
      .integrationAction('Store processed data', sourceIntegration, 'store_data')
        .add()
      .notification('Processing complete', 'slack', '#data', '🔄 Data processing completed')
        .add()
      .tags('data', 'processing', sourceIntegration);
  }

  static createApprovalWorkflow(
    id: string,
    name: string,
    requesterIntegration: string,
    approverIntegration: string,
    targetIntegration: string
  ): WorkflowBuilder {
    return new WorkflowBuilder(id, name, `Multi-step approval workflow`)
      .integrationAction('Create request', requesterIntegration, 'create_request')
        .add()
      .notification('Request approval', approverIntegration, 'approvers', '🔔 Approval required: {{requestId}}')
        .add()
      .condition('Wait for approval', {
        field: 'approval.status',
        operator: 'eq',
        value: 'approved',
      })
        .timeout(86400000) // 24 hours
        .add()
      .integrationAction('Execute approved action', targetIntegration, 'execute_action')
        .add()
      .notification('Approval completed', requesterIntegration, 'requester', '✅ Request approved and executed')
        .add()
      .tags('approval', 'workflow', requesterIntegration)
      .priority('high');
  }
}

// Export types
export { WorkflowDefinition, WorkflowStep, WorkflowTrigger };