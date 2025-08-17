<file_path>
atom/src/nlu_agents/integratedAgent.ts
</file_path>

import { EventEmitter } from 'events';
import { SmallBusinessAgent } from './smallBusinessAgent';
import { NLULeadAgent } from './nlu_lead_agent';
import { SubAgentInput, EnrichedIntent } from './nlu_types';
import { TurnContext } from 'botbuilder';

/**
 * IntegratedAgent - Combines general Atom capabilities with small business automation
 *
 * This agent seamlessly integrates the existing NLU Lead Agent with new small business
 * focused autonomous workflows, allowing small business owners to create automation
 * through simple conversation.
 */
export class IntegratedAgent extends EventEmitter {
  private nluLeadAgent: NLULeadAgent;
  private smallBusinessAgent: SmallBusinessAgent;

  constructor(
    llmService: any,
    context: TurnContext,
    memory: any,
    functions: any
  ) {
    super();
    this.nluLeadAgent = new NLULeadAgent(llmService, context, memory, functions);
    this.smallBusinessAgent = new SmallBusinessAgent();
  }

  public async processInput(input: SubAgentInput): Promise<EnrichedIntent> {
    const sessionId = `smb_${input.userId}_${Date.now()}`;

    // Check for small business context first
    const smbResponse = await this.smallBusinessAgent.analyzeSmallBusinessIntent(input);

    if (smbResponse) {
      // This is a small business automation request
      const enrichedIntent: EnrichedIntent = {
        originalQuery: input.userInput,
        userId: input.userId,
        primaryGoal: smbResponse.businessGoal,
        primaryGoalConfidence: 0.95,
        extractedParameters: {
          workflowType: smbResponse.suggestedWorkflow.id,
          smbWorkflow: true,
          ...smbResponse
        },
        identifiedTasks: [
          {
            taskType: 'create_smb_workflow',
            parameters: {
              workflowName: smbResponse.suggestedWorkflow.name,
              estimatedBenefit: smbResponse.estimatedBenefit,
              setupComplexity: smbResponse.setupComplexity
            }
          }
        ],
        suggestedNextAction: {
          actionType: 'create_smb_workflow',
          workflowName: smbResponse.suggestedWorkflow.name,
          instructions: smbResponse.suggestedWorkflow.instructions,
          requiresApproval: smbResponse.suggestedWorkflow.requiresApproval
        },
        synthesisLog: [`Small business workflow detected: ${smbResponse.suggestedWorkflow.name}`]
      };

      return enrichedIntent;
    }

    // Fallback to general NLU processing
    return await this.nluLeadAgent.analyzeIntent(input);
  }

  public async getWorkforceSummary(userId: string): Promise<{
    recommendedWorkflows: any[];
    estimatedSavings: string;
    setupProgress: number;
  }> {
    const recommended = this.smallBusinessAgent.getSmallBusinessRecommendations(userId);

    return {
      recommendedWorkflows: recommended.slice(0, 3),
      estimatedSavings: `${recommended.reduce((sum, wf) => parseInt(wf.estimatedTimeSave.split(' ')[0]), 0)}+ hours/week`,
      setupProgress: 0 // Would track actual setup progress
    };
  }
}
