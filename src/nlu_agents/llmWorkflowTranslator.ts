<file_path>
atom/src/nlu_agents/llmWorkflowTranslator.ts
</file_path>

import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';
import dayjs from 'dayjs';

interface LLMWorkflowIntent {
  primaryIntent: string;
  confidence: number;
  actionType: 'create_workflow' | 'modify_workflow' | 'execute_workflow' | 'analyze_workflow' | 'optimize_workflow';
  workflowTemplate?: string;
  parameters: Record<string, any>;
  businessContext: {
    userRole: string;
    companySize: string;
    industry: string;
    technicalLevel: string;
  };
  confirmationRequired: boolean;
  estimatedComplexity: 'low' | 'medium' | 'high';
  riskLevel: 'low' | 'medium' | 'high';
  expectedOutcome: string;
}

interface WorkflowTranslation {
  originalText: string;
  interpretedIntent: LLMWorkflowIntent;
  commandSequence: string[];
  rollbackCommands?: string[];
  successCriteria: string[];
  staleTime: string;
  metadata: {
    tokensUsed: number;
    responseTime: number;
    confidenceFactors: string[];
  };
}

interface ConversationContext {
  sessionId: string;
  userId: string;
  messageHistory: Message[];
  workflowState: 'discovery' | 'planning' | 'confirmation' | 'execution' | 'monitoring';
  lastTranslation?: WorkflowTranslation;
  userProfile?: UserProfile;
}

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  metadata?: any;
}

interface UserProfile {
  technicalExpertise: 'beginner' | 'intermediate' | 'advanced';
  preferredCommunicationStyle: 'concise' | 'detailed' | 'tutorial';
  businessContext: {
    role: string;
    industry?: string;
    companySize?: string;
    commonWorkflows?: string[];
  };
}

interface LLMConfiguration {
  model: string;
  maxTokens: number;
  temperature: number;
  systemPrompt: string;
  examples: Example[];
}

interface Example {
  input: string;
  expectedIntent: string;
  parameters: Record<string, any>;
  explanation: string;
}

export class LLMWorkflowTranslator extends EventEmitter {
  private conversationContexts: Map<string, ConversationContext> = new Map();
  private userProfiles: Map<string, UserProfile> = new Map();
  private promptTemplates: Map<string, string> = new Map();
  private errorHandler = new ErrorHandler(this);

  private llmConfig: LLMConfiguration = {
    model: 'gpt-4-turbo-preview',
    maxTokens: 2000,
    temperature: 0.2,
    systemPrompt: `You are Atom, an AI assistant that translates natural language into precise autonomous workflow commands. Your role:

1. Interpret user requests and extract business goals
2. Map requests to specific workflow templates or create custom workflows
3. Identify required parameters and dependencies
4. Assess complexity, risks, and success criteria
5. Provide clear rollback strategies
6. Adapt communication style to user expertise

Rules:
- Always provide exact parameter extraction
- Include confidence levels for interpretations
- Suggest wave-off strategies for high-risk operations
- Prefer existing templates when applicable
- Request clarification for ambiguous requests
- Validate business context alignment`,
    examples: [
      {
        input: "Create an automated system to monitor my competitors and send weekly alerts about their pricing changes",
        expectedIntent: "create_workflow",
        parameters: {
          template: "competitor_monitoring",
          trigger: "weekly",
          monitorTypes: ["pricing", "product_changes"],
          alertChannels: ["email", "slack"]
        },
        explanation: "Detected need for competitive intelligence workflow with automated monitoring and alerting"
      },
      {
        input: "I want to automate my invoice processing when clients upload receipts to my Dropbox",
        expectedIntent: "create_workflow",
        parameters: {
          trigger: "dropbox_upload",
          actions: ["extract_receipt_data", "create_invoice", "send_to_client", "update_accounting"],
          integrations: ["dropbox", "xero", "gmail"]
        },
        explanation: "Extracted receipt processing automation with multi-platform integration requirements"
      }
    ]
  };

  async translateToWorkflowCommand(
    userMessage: string,
    userId: string,
    context?: any
  ): Promise<WorkflowTranslation> {
    const sessionId = context?.sessionId || `workflow_${uuidv4()}`;
    const userProfile = await this.getUserProfile(userId);
    const conversationContext = this.initializeOrUpdateContext(sessionId, userId, userMessage, userProfile);

    try {
      const llmResponse = await this.callLLM(userMessage, conversationContext, userProfile
