<file_path>
atom/src/orchestration/conversationalWorkflowManager.ts
</file_path>

import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';
import dayjs from 'dayjs';

interface WorkflowDefinition {
    id: string;
    name: string;
    description: string;
    trigger: WorkflowTrigger;
    actions: WorkflowAction[];
    conditions: WorkflowCondition[];
    enabled: boolean;
    createdBy: string;
    lastModified: string;
}

interface WorkflowTrigger {
    type: 'voice' | 'scheduled' | 'event' | 'webhook' | 'intent_match';
    pattern?: string; // For voice/intent triggers
    schedule?: string; // For cron-like scheduling
    eventType?: string; // For webhook/events
    intentCriteria?: {
        primaryIntent: string;
        confidenceThreshold: number;
        requiredEntities?: string[];
    };
}

interface WorkflowAction {
    type: 'shell_command' | 'api_call' | 'skill_execution' | 'conditional_branch' | 'notification' | 'delay';
    parameters: any;
    retryPolicy?: {
        maxAttempts: number;
        delayBetweenRetries: number;
    };
}

interface WorkflowCondition {
    type: 'numeric_threshold' | 'business_logic' | 'time_window' | 'api_response' | 'error_rate';
    condition: string; // JSON condition expression
    actionOnTrue?: string;
    actionOnFalse?: string;
}

interface ConversationContext {
    userId: string;
    sessionId: string;
    currentIntent: string;
    detectedEntities: Record<string, any>;
    workflowState: 'creating' | 'editing' | 'confirming' | 'executing' | 'paused';
    step: number;
    definition: Partial<WorkflowDefinition>;
}

interface WorkflowExecution {
    id: string;
    workflowId: string;
    status: 'running' | 'paused' | 'completed' | 'failed' | 'waiting_condition';
    startTime: string;
    actionsCompleted: number;
    actionsTotal: number;
    lastAction?: string;
    currentAction?: WorkflowAction;
    metadata: any;
}

interface WorkflowResponse {
    message: string;
    requiresConfirmation?: boolean;
    confirmationType?: 'create' | 'update' | 'delete' | 'execute';
    workflowDetails?: any;
    nextStep?: string;
}

class ConversationalWorkflowManager extends EventEmitter {
    private workflows: Map<string, WorkflowDefinition> = new Map();
    private activeConversations: Map<string, ConversationContext> = new Map();
    private executions: Map<string, WorkflowExecution> = new Map();
    private logger;

    constructor() {
        super();
        this.logger = {
            info: (message: string, data?: any) => console.log(`[ConversationalWorkflowManager] ${message}`, data),
            error: (message: string, error?: any) => console.error(`[ConversationalWorkflowManager] ${message}`, error),
            debug: (message: string, data?: any) => console.debug(`[ConversationalWorkflowManager] ${message}`, data)
        };
    }

    /**
     * Process natural language input to create or manage workflows
     */
    async processNaturalLanguage(userId: string, text: string, sessionId?: string): Promise<{
        response: string;
        actions?: string[];
        requiresConfirmation?: boolean;
    }> {
        this.logger.info('Processing natural language', { userId, text, sessionId });

        // NLP processing to extract intent and entities
        const { intent, entities, confidence } = await this.extractIntentAndEntities(text);

        let context = this.activeConversations.get(sessionId || `default_${userId}`);

        if (!context) {
            context = {
                userId,
                sessionId: sessionId || uuidv4(),
                currentIntent: intent,
                detectedEntities: entities,
                workflowState: 'creating',
                step: 0,
                definition: { id: uuidv4(), createdBy: userId }
            };
            this.activeConversations.set(context.sessionId, context);
        }

        // Handle different intents
        switch (intent) {
            case 'create_workflow':
                return await this.handleCreateWorkflow(context, text, entities);
            case 'edit_workflow':
                return await this.handleEditWorkflow(context, text, entities);
            case 'list_workflows':
                return await this.handleListWorkflows(context);
            case 'execute_workflow':
                return await this.handleExecuteWorkflow(context, entities);
            case 'pause_workflow':
                return await this.handlePauseWorkflow(context, entities);
            case 'delete_workflow':
                return await this.handleDeleteWorkflow(context, entities);
            case 'describe_workflow':
                return await this.handleDescribeWorkflow(context, entities);
            case 'workflow_status':
                return await this.handleWorkflowStatus(context);
            case 'confirm
