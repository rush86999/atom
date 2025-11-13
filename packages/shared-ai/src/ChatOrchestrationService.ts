import { EventEmitter } from 'events';
import { Logger } from '../utils/logger';
import { NLUBridgeService } from '../nlu_agents/nlu_bridge_service';
import { WorkflowExecutionService } from '../workflows/WorkflowExecutionService';
import { ConversationalOrchestration } from '../orchestration/ConversationalOrchestration';

export interface ChatContext {
  userId: string;
  sessionId: string;
  conversationHistory: Array<{
    role: 'user' | 'assistant' | 'system';
    content: string;
    timestamp: Date;
    metadata?: Record<string, any>;
  }>;
  activeWorkflows: string[];
  userPreferences: {
    automationLevel: 'minimal' | 'moderate' | 'full';
    communicationStyle: 'professional' | 'friendly' | 'interactive';
    preferredServices: string[];
  };
}

export interface ChatResponse {
  message: string;
  type: 'text' | 'workflow' | 'multi_step' | 'confirmation' | 'error';
  metadata?: {
    workflowId?: string;
    processId?: string;
    nextSteps?: string[];
    suggestedActions?: string[];
    requiresConfirmation?: boolean;
    data?: Record<string, any>;
  };
}

export interface MultiStepProcess {
  id: string;
  name: string;
  currentStep: number;
  totalSteps: number;
  steps: Array<{
    id: string;
    title: string;
    description: string;
    status: 'pending' | 'active' | 'completed' | 'failed';
    requiredInput?: string;
    validation?: (input: string) => boolean;
    handler?: (input: string, context: ChatContext) => Promise<void>;
  }>;
  context: Record<string, any>;
}

export class ChatOrchestrationService extends EventEmitter {
  private logger: Logger;
  private nluBridge: NLUBridgeService;
  private workflowService: WorkflowExecutionService;
  private conversationalOrchestration: ConversationalOrchestration;
  private activeProcesses: Map<string, MultiStepProcess>;
  private chatContexts: Map<string, ChatContext>;

  constructor() {
    super();
    this.logger = new Logger('ChatOrchestrationService');
    this.nluBridge = new NLUBridgeService();
    this.workflowService = new WorkflowExecutionService();
    this.conversationalOrchestration = new ConversationalOrchestration();
    this.activeProcesses = new Map();
    this.chatContexts = new Map();
  }

  async initialize(): Promise<void> {
    try {
      await this.nluBridge.initialize();
      await this.workflowService.initialize();
      this.logger.info('Chat orchestration service initialized successfully');
    } catch (error) {
      this.logger.error('Failed to initialize chat orchestration service', error);
      throw error;
    }
  }

  async processMessage(userId: string, message: string): Promise<ChatResponse> {
    try {
      const context = await this.getOrCreateContext(userId);

      // Add user message to conversation history
      context.conversationHistory.push({
        role: 'user',
        content: message,
        timestamp: new Date()
      });

      // Check for active multi-step process
      const activeProcess = this.activeProcesses.get(userId);
      if (activeProcess) {
        return await this.handleProcessStep(userId, message, activeProcess, context);
      }

      // Analyze message with NLU system
      const nluResult = await this.nluBridge.analyzeWorkflowRequest(message, userId);

      if (nluResult?.isWorkflowRequest) {
        return await this.handleWorkflowRequest(userId, message, nluResult, context);
      }

      // Handle conversational requests
      const conversationalResult = await this.conversationalOrchestration.processUserMessage(
        userId,
        message,
        this.mapToBusinessContext(context)
      );

      return await this.handleConversationalResponse(userId, conversationalResult, context);
    } catch (error) {
      this.logger.error('Error processing chat message', error);
      return {
        message: "I encountered an error while processing your request. Please try again or rephrase your question.",
        type: 'error'
      };
    }
  }

  private async handleWorkflowRequest(
    userId: string,
    message: string,
    nluResult: any,
    context: ChatContext
  ): Promise<ChatResponse> {
    try {
      // Generate workflow from NLU analysis
      const workflowDefinition = await this.nluBridge.generateWorkflowFromNluAnalysis(nluResult);

      // Execute the workflow
      const workflowId = await this.workflowService.executeWorkflow(workflowDefinition);

      // Update context
      context.activeWorkflows.push(workflowId);
      this.chatContexts.set(userId, context);

      this.emit('workflowCreated', { userId, workflowId, workflowDefinition });

      return {
        message: `I've created and started a workflow for you! I'll automate: "${workflowDefinition.description}". The workflow ID is ${workflowId}. I'll keep you updated on its progress.`,
        type: 'workflow',
        metadata: {
          workflowId,
          nextSteps: ['Monitor workflow progress', 'Review automation results', 'Modify if needed'],
          suggestedActions: ['Check workflow status', 'Create another automation', 'View all workflows']
        }
      };
    } catch (error) {
      this.logger.error('Error handling workflow request', error);
      return {
        message: "I had trouble creating that workflow. Let me try a simpler approach or we can go through it step by step.",
        type: 'error',
        metadata: {
          suggestedActions: ['Try step-by-step setup', 'Describe the automation differently', 'Check service connections']
        }
      };
    }
  }

  private async handleConversationalResponse(
    userId: string,
    conversationalResult: any,
    context: ChatContext
  ): Promise<ChatResponse> {
    const response: ChatResponse = {
      message: conversationalResult.response,
      type: 'text'
    };

    if (conversationalResult.workflowId) {
      response.type = 'workflow';
      response.metadata = {
        workflowId: conversationalResult.workflowId,
        nextSteps: conversationalResult.followUpQuestions || []
      };
    }

    if (conversationalResult.followUpQuestions) {
      response.metadata = {
        ...response.metadata,
        suggestedActions: conversationalResult.followUpQuestions
      };
    }

    // Add assistant response to conversation history
    context.conversationHistory.push({
      role: 'assistant',
      content: response.message,
      timestamp: new Date(),
      metadata: response.metadata
    });

    this.chatContexts.set(userId, context);

    return response;
  }

  private async handleProcessStep(
    userId: string,
    message: string,
    process: MultiStepProcess,
    context: ChatContext
  ): Promise<ChatResponse> {
    const currentStep = process.steps[process.currentStep];

    try {
      // Validate input if validation function exists
      if (currentStep.validation && !currentStep.validation(message)) {
        return {
          message: `I need more specific information for "${currentStep.title}". ${currentStep.description}`,
          type: 'confirmation',
          metadata: {
            processId: process.id,
            requiresConfirmation: true
          }
        };
      }

      // Execute step handler if exists
      if (currentStep.handler) {
        await currentStep.handler(message, context);
      }

      // Update process state
      currentStep.status = 'completed';
      process.currentStep++;

      if (process.currentStep < process.totalSteps) {
        // Move to next step
        const nextStep = process.steps[process.currentStep];
        nextStep.status = 'active';

        this.activeProcesses.set(userId, process);

        return {
          message: `Great! Now ${nextStep.description}`,
          type: 'multi_step',
          metadata: {
            processId: process.id,
            nextSteps: [nextStep.description],
            data: process.context
          }
        };
      } else {
        // Process completed
        this.activeProcesses.delete(userId);
        await this.finalizeProcess(process, context);

        return {
          message: `Perfect! I've completed the ${process.name} process successfully. Everything is set up and ready to go.`,
          type: 'text',
          metadata: {
            suggestedActions: ['Start another process', 'Check the results', 'Modify settings']
          }
        };
      }
    } catch (error) {
      this.logger.error('Error handling process step', error);
      return {
        message: `I encountered an issue with this step. Let's try again: ${currentStep.description}`,
        type: 'error',
        metadata: {
          processId: process.id
        }
      };
    }
  }

  async startMultiStepProcess(userId: string, processName: string, initialContext?: Record<string, any>): Promise<ChatResponse> {
    const process = this.createProcess(processName, initialContext);
    this.activeProcesses.set(userId, process);

    const firstStep = process.steps[0];

    return {
      message: `Let's set up ${process.name}! ${firstStep.description}`,
      type: 'multi_step',
      metadata: {
        processId: process.id,
        nextSteps: [firstStep.description],
        data: process.context
      }
    };
  }

  private createProcess(processName: string, initialContext?: Record<string, any>): MultiStepProcess {
    const baseProcesses: Record<string, () => MultiStepProcess> = {
      'schedule_meeting': () => ({
        id: `process_${Date.now()}`,
        name: 'Meeting Scheduling',
        currentStep: 0,
        totalSteps: 4,
        context: initialContext || {},
        steps: [
          {
            id: 'step1',
            title: 'Event Details',
            description: 'What is the title and description of the meeting?',
            status: 'active',
            requiredInput: 'event_details',
            validation: (input) => input.length > 5,
            handler: async (input, context) => {
              // Extract title and description from input
              const lines = input.split('\n');
              context.conversationHistory.push({
                role: 'system',
                content: `User provided meeting details: ${input}`,
                timestamp: new Date()
              });
            }
          },
          {
            id: 'step2',
            title: 'Date & Time',
            description: 'When should this meeting happen? (e.g., "tomorrow at 2 PM" or "next Monday 10 AM")',
            status: 'pending',
            requiredInput: 'datetime',
            validation: (input) => /(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d+)/i.test(input),
            handler: async (input, context) => {
              // Parse datetime and create calendar event
              context.conversationHistory.push({
                role: 'system',
                content: `User selected time: ${input}`,
                timestamp: new Date()
              });
            }
          },
          {
            id: 'step3',
            title: 'Attendees',
            description: 'Who should be invited to this meeting? (provide email addresses or names)',
            status: 'pending',
            requiredInput: 'attendees',
            handler: async (input, context) => {
              // Process attendee list
              context.conversationHistory.push({
                role: 'system',
                content: `User provided attendees: ${input}`,
                timestamp: new Date()
              });
            }
          },
          {
            id: 'step4',
            title: 'Confirmation',
            description: 'Review and confirm all meeting details',
            status: 'pending',
            handler: async (input, context) => {
              // Finalize and create the calendar event
              await this.workflowService.executeWorkflow({
                name: 'Scheduled Meeting',
                description: 'Meeting scheduled via chat',
                trigger: { type: 'manual', service: 'atom' },
                steps: [
                  {
                    id: 'create_event',
                    type: 'action',
                    service: 'google_calendar',
                    action: 'create_event',
                    parameters: context.conversationHistory
                      .filter(msg => msg.role === 'system')
                      .reduce((acc, msg) => ({ ...acc, ...msg.content }), {})
                  }
                ]
              });
            }
          }
        ]
      }),
      'create_automation': () => ({
        id: `process_${Date.now()}`,
        name: 'Workflow Automation',
        currentStep: 0,
        totalSteps: 3,
        context: initialContext || {},
        steps: [
          {
            id: 'step1',
            title: 'Trigger',
            description: 'What should trigger this automation? (e.g., "when I receive an email", "when a task is completed")',
            status: 'active',
            requiredInput: 'trigger',
            validation: (input) => input.includes('when'),
            handler: async (input, context) => {
              context.conversationHistory.push({
                role: 'system',
                content: `Automation trigger: ${input}`,
                timestamp: new Date()
              });
            }
          },
          {
            id: 'step2',
            title: 'Action',
            description: 'What should happen when the trigger occurs? (e.g., "send a notification", "create a task", "update calendar")',
            status: 'pending',
            requiredInput: 'action',
            handler: async (input, context) => {
              context.conversationHistory.push({
                role: 'system',
                content: `Automation action: ${input}`,
                timestamp: new Date()
              });
            }
          },
          {
            id: 'step3',
            title: 'Configuration',
            description: 'Any specific settings or conditions for this automation?',
            status: 'pending',
            handler: async (input, context) => {
              // Create the final workflow
              const workflowDefinition = await this.nluBridge.generateWorkflowFromNluAnalysis({
                isWorkflowRequest: true,
                trigger: { service: 'atom', event: 'manual' },
                actions: [{ service: 'atom', action: 'custom' }],
                primaryGoal: 'Custom automation',
                extractedParameters: context.conversationHistory
                  .filter(msg => msg.role === 'system')
                  .reduce((acc, msg) => ({ ...acc, ...msg.content }), {})
              });

              await this.workflowService.executeWorkflow(workflowDefinition);
            }
          }
        ]
      })
    };

    return baseProcesses[processName]?.() || baseProcesses['schedule_meeting']();
  }

  private async finalizeProcess(process: MultiStepProcess, context: ChatContext): Promise<void> {
    this.logger.info(`Completed multi-step process: ${process.name}`, { processId: process.id });
    this.emit('processCompleted', { process, context });
  }

  private async getOrCreateContext(userId: string): Promise<ChatContext> {
    if (this.chatContexts.has(userId)) {
      return this.chatContexts.get(userId)!;
    }

    const newContext: ChatContext = {
      userId,
      sessionId: `session_${Date.now()}`,
      conversationHistory: [],
      activeWorkflows: [],
      userPreferences: {
        automationLevel: 'moderate',
        communicationStyle: 'friendly',
        preferredServices: ['gmail', 'google_calendar', 'notion']
      }
    };

    this.chatContexts.set(userId, newContext);
    return newContext;
  }

  private mapToBusinessContext(chatContext: ChatContext): any {
    return {
      companySize: 'solo',
      technicalSkill: 'intermediate',
      goals: ['automation', 'efficiency'],
      constraints: [],
      preferences: chatContext.userPreferences
    };
  }

  async getActiveProcess(userId: string): Promise<MultiStepProcess | null> {
    return this.activeProcesses.get(userId) || null;
  }

  async cancelProcess(userId: string): Promise<void> {
    this.activeProcesses.delete(userId);
    this.logger.info(`Cancelled active process for user: ${userId}`);
  }

  async getConversationHistory(userId: string): Promise<ChatContext['conversationHistory']> {
    const context = await this.getOrCreateContext(userId);
    return context.conversationHistory;
  }

  async clearConversationHistory(userId: string): Promise<void> {
    const context = await this.getOrCreateContext(userId);
    context.conversationHistory = [];
    this.chatContexts.set(userId, context);
  }

  async dispose(): Promise<void> {
    this.activeProcesses.clear();
    this.chatContexts.clear();
    await this.nluBridge.close();
    await this.workflowService.dispose();
  }
}

// Export singleton instance
export const chatOrchestrationService = new ChatOrchestrationService();
