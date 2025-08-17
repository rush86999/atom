<file_path>
atom/src/nlu_agents/smallBusinessLLMTranslator.ts
</file_path>

import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';
import dayjs from 'dayjs';

interface LLMParsedIntent {
  commandType: 'create_workflow' | 'optimize_existing' | 'get_suggestions' | 'modify_workflow';
  businessGoal: string;
  workflowCategory: 'finance' | 'customer_service' | 'marketing' | 'operations' | 'hr' | 'analytics';
  specificRequirements: {
    automationLevel: 'low-code' | 'no-code' | 'expert-setup';
    integrationNeeded: string[];
    maxCost: number;
    technicalComplexity: 'one-click' | 'guided' | 'advanced';
  };
  preferences: {
    notificationMethod: 'email' | 'sms' | 'slack' | 'none';
    frequency: string;
    approvalRequired: boolean;
  };
  entities: Record<string, any>;
}

interface ConversationContext {
  sessionId: string;
  userId: string;
  businessProfile: {
    industry: string;
    size: 'solo' | '2-5' | '6-20' | '21-50' | '51+';
    budget: number;
    technicalLevel: 'beginner' | 'intermediate' | 'advanced';
    currentTools: string[];
  };
  conversationHistory: ConversationMessage[];
}

interface ConversationMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

interface LLMResponse {
  understanding: string;
  command: LLMParsedIntent;
  setupInstructions: string[];
  estimatedImpact: string;
  timeline: string;
  riskLevel: 'low' | 'medium' | 'high';
  confidence: number;
  requiresConfirmation: boolean;
}

export class SmallBusinessLLMTranslator extends EventEmitter {
  private conversationContexts: Map<string, ConversationContext> = new Map();
  private llmClient: any; // Will be connected to actual LLM service
  private systemPrompt = `You are a small business automation expert that translates natural language into precise workflow commands.

CORE PRINCIPLES:
- Small businesses need FAST setup (under 15 minutes)
- Budget-conscious solutions ($0-$50/month max)
- One-click setup when possible
- No technical jargon
- Clear ROI in hours saved

OUTPUT FORMAT (JSON):
{
  "commandType": "create_workflow",
  "businessGoal": "[user's primary goal]",
  "workflowCategory": "[finance|customer_service|marketing|operations|hr|analytics]",
  "specificRequirements": {
    "automationLevel": "[low-code|no-code|expert-setup]",
    "integrationNeeded": ["list of tools"],
    "maxCost": [number],
    "technicalComplexity": "[one-click|guided|advanced]"
  },
  "preferences": {
    "notificationMethod": "[email|sms|slack|none]",
    "frequency": "[daily|weekly|monthly|custom]",
    "approvalRequired": [boolean]
  },
  "entities": {"extracted parameters"},
  "setupInstructions": ["step-by-step"],
  "estimatedImpact": "[hours saved + benefit]",
  "timeline": "Setup: X min, Full value: Y weeks",
  "riskLevel": "[low|medium|high]",
  "requiresConfirmation": [boolean]
}

EXAMPLES:
Input: "I'm tired of receipts taking over my life"
Output: {"commandType":"create_workflow","businessGoal":"automate receipt management","specificRequirements":{"maxCost":9,"automationLevel":"no-code"},
Input: "Customers forget about me after purchase"
Output: {"commandType":"create_workflow","businessGoal":"automate customer follow-up","workflowCategory":"customer_service","setupInstructions":["Connect email","Import customer list","Set follow-up schedule"]}
`;

  constructor(llmProvider?: any) {
    super();
    this.llmClient = llmProvider || this.createMockLLM();
  }

  private createMockLLM() {
    return {
      chat: async (messages: any[]) => {
        const lastMessage = messages[messages.length - 1]?.content || '';

        // Parse different types of requests with sophisticated understanding
        if (lastMessage.includes('receipt') || lastMessage.includes('expense')) {
          return {
            understanding: "User needs automated receipt processing and expense tracking",
            command: {
              commandType: 'create_workflow',
              businessGoal: 'automate receipt and expense management',
              workflowCategory: 'finance',
              specificRequirements: {
                automationLevel: 'no-code',
                integrationNeeded: ['phone_camera', 'email', 'accounting_software'],
                maxCost: 9,
                technicalComplexity: 'one-click'
              },
