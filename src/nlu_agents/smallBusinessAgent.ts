<file_path>
atom/src/nlu_agents/smallBusinessAgent.ts
</file_path>

import { EventEmitter } from 'events';
import { v4 as uuidv4 } from 'uuid';
import dayjs from 'dayjs';
import { SmallBusinessLLMTranslator } from './smallBusinessLLMTranslator';
import { SubAgentInput } from './nlu_types';

interface SMBWorkflowSuggestion {
  id: string;
  name: string;
  description: string;
  estimatedTimeSave: string;
  monthlyCost: string;
  setupTime: string;
  instructions: string[];
  requiresApproval: boolean;
  complexity: 'one-click' | 'guided' | 'advanced';
}

interface BusinessContext {
  budget: number;
  employeeCount: number;
  industry: string;
  techSkill: 'beginner' | 'intermediate' | 'advanced';
  timeConstraint: string;
  currentTools: string[];
}

interface SMBIntentResponse {
  originalQuery: string;
  userId: string;
  businessGoal: string;
  suggestedWorkflow: SMBWorkflowSuggestion;
  commandSequence: any[];
  confirmationRequired: boolean;
  estimatedImpact: string;
  confidence: number;
}

export class SmallBusinessAgent {
  private llmTranslator: SmallBusinessLLMTranslator;
  private logger = {
    info: (message: string, data?: any) =>
      console.log(`[SmallBusinessAgent] ${message}`, data),
    error: (message: string, error?: any) =>
      console.error(`[SmallBusinessAgent] ${message}`, error)
  };

  constructor() {
    this.llmTranslator = new SmallBusinessLLMTranslator();
  }

  /**
   * Use LLM to translate natural language into small business automation commands
   */
  public async analyzeSmallBusinessIntent(input: SubAgentInput): Promise<SMBIntentResponse | null> {
    try {
      // Get business context from metadata or create defaults
      const businessContext = await this.extractBusinessContext(input);

      // Use LLM for sophisticated intent understanding
      const llmResponse = await this.llmTranslator.translateToWorkflowCommand(
        input.userInput,
        input.userId,
        { businessContext }
      );

      if (!llmResponse || llmResponse.confidence < 0.6) {
        return null; // Let general NLU handle it
      }

      // Map LLM response to SMB-optimized workflow
      const workflowSuggestion = this.createSMBWorkflow(llmResponse);

      this.logger.info('SMB intent detected via LLM', {
        userId: input.userId,
        businessGoal: llmResponse.businessGoal,
        confidence: llmResponse.confidence
      });

      return {
        originalQuery: input.userInput,
        userId: input.userId,
        businessGoal: llmResponse.businessGoal,
        suggestedWorkflow: workflowSuggestion,
        commandSequence: this.generateCommands(llmResponse, workflowSuggestion),
        confirmationRequired: llmResponse.requiresConfirmation,
        estimatedImpact: llmResponse.estimatedImpact,
        confidence: llmResponse.confidence
      };

    } catch (error) {
      this.logger.error('Error analyzing SMB intent', error);
      return null;
    }
  }

  /**
   * Create SMB-optimized workflow from LLM response
   */
  private createSMBWorkflow(llmResponse: any): SMBWorkflowSuggestion {
    const baseWorkflows = {
      finance: {
        name: 'Smart Finance Tracker',
        description: 'Automatically handles receipts, expenses, and cash flow monitoring with small business focus',
        monthlyCost: '$0-19/month',
        instructions: [
          'Take one photo of any receipt to test',
          'Connect your accounting software (if any)',
          'Set up weekly financial summaries'
        ]
      },
      'customer_service': {
        name: 'Customer Relationship Bot',
        description: 'Never lose customers due to poor follow-up with automated thank-you emails and periodic check-ins',
        monthlyCost: 'Free with email',
        instructions: [
          'Connect your email account',
          'Import customer email list',
          'Set follow-up schedule preferences'
        ]
      },
      'marketing': {
        name: 'Social Media Autopilot',
        description: 'Maintains consistent online presence across Facebook, Instagram, and LinkedIn without daily effort',
        monthlyCost: '$0-15/month',
        instructions: [
          'Choose platforms to focus on',
          'Upload 3-5 photos or post examples',
          'Set posting frequency preferences'
        ]
      },
      'operations': {
        name: 'Appointment & Operations Manager',
        description: 'Reduces no-shows and automates routine business operations for maximum efficiency',
        monthlyCost: '$0-10/month',
        instructions: [
          'Link to Google Calendar or other calendar',
          'Choose reminder schedule (text, email)',
          'Set no-show prevention messages'
        ]
      }
    };

    const category =
