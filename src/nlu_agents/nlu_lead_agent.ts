import {
  SubAgentInput,
  AnalyticalAgentResponse,
  CreativeAgentResponse,
  PracticalAgentResponse,
  EnrichedIntent,
} from './nlu_types';
import { AnalyticalAgent } from './analytical_agent';
import { CreativeAgent } from './creative_agent';
import { PracticalAgent } from './practical_agent';
import { SynthesizingAgent } from './synthesizing_agent';
import { TurnContext } from 'botbuilder';
import { AgentLLMService } from './nlu_types';
import { DataAnalystSkill } from '../skills/dataAnalystSkill';
import { AdvancedResearchSkill } from '../skills/researchSkillIndex';
import { LegalDocumentAnalysisSkill } from '../skills/legalSkillIndex';
import { SocialMediaAgent } from '../skills/socialMediaSkill';
import { ContentCreationAgent } from '../skills/contentCreationSkill';
import { PersonalizedShoppingAgent } from '../skills/personalizedShoppingSkill';
import { RecruitmentRecommendationAgent } from '../skills/recruitmentRecommendationSkill';
import { VibeHackingAgent } from '../skills/vibeHackingSkill';
import { TaxAgent } from './tax_agent';
import { MarketingAutomationAgent } from '../skills/marketingAutomationSkill';
import { WorkflowAgent } from './workflow_agent';
import { WorkflowGenerator } from './workflow_generator';

export class NLULeadAgent {
  private analyticalAgent: AnalyticalAgent;
  private creativeAgent: CreativeAgent;
  private practicalAgent: PracticalAgent;
  private synthesizingAgent: SynthesizingAgent;
  private dataAnalystSkill: DataAnalystSkill;
  private advancedResearchSkill: AdvancedResearchSkill;
  private legalDocumentAnalysisSkill: LegalDocumentAnalysisSkill;
  private socialMediaAgent: SocialMediaAgent;
  private contentCreationAgent: ContentCreationAgent;
  private personalizedShoppingAgent: PersonalizedShoppingAgent;
  private recruitmentRecommendationAgent: RecruitmentRecommendationAgent;
  private vibeHackingAgent: VibeHackingAgent;
  private taxAgent: TaxAgent;
  private marketingAutomationAgent: MarketingAutomationAgent;
  private workflowAgent: WorkflowAgent;
  private workflowGenerator: WorkflowGenerator;
  private agentName: string = 'NLULeadAgent';

  constructor(
    llmService: AgentLLMService,
    context: TurnContext,
    memory: any,
    functions: any
  ) {
    this.analyticalAgent = new AnalyticalAgent(llmService);
    this.creativeAgent = new CreativeAgent(llmService);
    this.practicalAgent = new PracticalAgent(llmService);
    this.synthesizingAgent = new SynthesizingAgent(llmService);
    this.dataAnalystSkill = new DataAnalystSkill(context, memory, functions);
    this.advancedResearchSkill = new AdvancedResearchSkill();
    this.legalDocumentAnalysisSkill = new LegalDocumentAnalysisSkill();
    this.socialMediaAgent = new SocialMediaAgent(llmService);
    this.contentCreationAgent = new ContentCreationAgent(llmService);
    this.personalizedShoppingAgent = new PersonalizedShoppingAgent(llmService);
    this.recruitmentRecommendationAgent = new RecruitmentRecommendationAgent(
      llmService
    );
    this.vibeHackingAgent = new VibeHackingAgent(llmService);
    this.taxAgent = new TaxAgent(llmService);
    this.marketingAutomationAgent = new MarketingAutomationAgent(llmService);
    this.workflowAgent = new WorkflowAgent(llmService);
    this.workflowGenerator = new WorkflowGenerator();
  }

  public async analyzeIntent(input: SubAgentInput): Promise<EnrichedIntent> {
    const P_LEAD_SUB_AGENTS_TIMER_LABEL = `[${this.agentName}] All Sub-Agents Processing Duration`;
    const P_LEAD_SYNTHESIS_TIMER_LABEL = `[${this.agentName}] Synthesis Duration`;

    console.time(P_LEAD_SUB_AGENTS_TIMER_LABEL);
    const [
      analyticalResponse,
      creativeResponse,
      practicalResponse,
      socialMediaResponse,
      contentCreationResponse,
      personalizedShoppingResponse,
      recruitmentRecommendationResponse,
      vibeHackingResponse,
      taxResponse,
      marketingAutomationResponse,
      workflowResponse,
    ] = await Promise.all([
      this.analyticalAgent.analyze(input).catch((e) => {
        console.error('AnalyticalAgent failed:', e);
        return null;
      }),
      this.creativeAgent.analyze(input).catch((e) => {
        console.error('CreativeAgent failed:', e);
        return null;
      }),
      this.practicalAgent.analyze(input).catch((e) => {
        console.error('PracticalAgent failed:', e);
        return null;
      }),
      this.socialMediaAgent.analyze(input).catch((e) => {
        console.error('SocialMediaAgent failed:', e);
        return null;
      }),
      this.contentCreationAgent.analyze(input).catch((e) => {
        console.error('ContentCreationAgent failed:', e);
        return null;
      }),
      this.personalizedShoppingAgent.analyze(input).catch((e) => {
        console.error('PersonalizedShoppingAgent failed:', e);
        return null;
      }),
      this.recruitmentRecommendationAgent.analyze(input).catch((e) => {
        console.error('RecruitmentRecommendationAgent failed:', e);
        return null;
      }),
      this.vibeHackingAgent.analyze(input).catch((e) => {
        console.error('VibeHackingAgent failed:', e);
        return null;
      }),
      this.taxAgent.analyze(input).catch((e) => {
        console.error('TaxAgent failed:', e);
        return null;
      }),
      this.marketingAutomationAgent.analyze(input).catch((e) => {
        console.error('MarketingAutomationAgent failed:', e);
        return null;
      }),
      this.workflowAgent.analyze(input).catch((e) => {
        console.error('WorkflowAgent failed:', e);
        return null;
      }),
    ]);
    console.timeEnd(P_LEAD_SUB_AGENTS_TIMER_LABEL);

    const synthesisResult = await this.synthesizingAgent.synthesize(
      input,
      analyticalResponse,
      creativeResponse,
      practicalResponse,
      socialMediaResponse,
      contentCreationResponse,
      personalizedShoppingResponse,
      recruitmentRecommendationResponse,
      vibeHackingResponse,
      taxResponse,
      marketingAutomationResponse,
      workflowResponse
    );

    if (synthesisResult.suggestedNextAction?.actionType === 'create_workflow') {
      const workflowDefinition = this.workflowGenerator.generate(synthesisResult);
      if (workflowDefinition) {
        await this.saveWorkflow(synthesisResult.primaryGoal, workflowDefinition);
        // We could potentially modify the enriched intent here to indicate success.
        synthesisResult.synthesisLog?.push("Successfully generated and saved the new workflow.");
      } else {
        synthesisResult.synthesisLog?.push("Failed to generate the workflow definition.");
      }
    } else if (synthesisResult.suggestedNextAction?.actionType === 'invoke_skill') {
      const skillId = synthesisResult.suggestedNextAction.skillId;
      if (skillId === 'advancedResearch') {
        // @ts-ignore
        const researchResult = await this.advancedResearchSkill.handler(
          synthesisResult.extractedParameters
        );
        console.log('Advanced Research Skill Result:', researchResult);
      } else if (skillId === 'legalDocumentAnalysis') {
        // @ts-ignore
        const legalResult = await this.legalDocumentAnalysisSkill.handler(
          synthesisResult.extractedParameters
        );
        console.log('Legal Document Analysis Skill Result:', legalResult);
      }
      // Add similar blocks for other skills
    }

    return {
      originalQuery: input.userInput,
      userId: input.userId,
      primaryGoal: synthesisResult.primaryGoal,
      primaryGoalConfidence: synthesisResult.primaryGoalConfidence,
      extractedParameters: synthesisResult.extractedParameters,
      identifiedTasks: synthesisResult.identifiedTasks,
      suggestedNextAction: synthesisResult.suggestedNextAction,
      alternativeInterpretations: creativeResponse?.alternativeGoals,
      potentialAmbiguities: creativeResponse?.ambiguityFlags,
      practicalConsiderations: {
        feasibility: practicalResponse?.feasibilityAssessment,
        efficiencyTips: practicalResponse?.efficiencyTips,
      },
      rawSubAgentResponses: {
        analytical: analyticalResponse,
        creative: creativeResponse,
        practical: practicalResponse,
        socialMedia: socialMediaResponse,
        contentCreation: contentCreationResponse,
        personalizedShopping: personalizedShoppingResponse,
        recruitmentRecommendation: recruitmentRecommendationResponse,
        vibeHacking: vibeHackingResponse,
        tax: taxResponse,
        marketingAutomation: marketingAutomationResponse,
        workflow: workflowResponse,
      },
      synthesisLog: synthesisResult.synthesisLog || [
        'Synthesis log not initialized.',
      ],
    };
  }
}

  private async saveWorkflow(name: string, definition: object): Promise<void> {
    const workflow = {
      name,
      definition,
      enabled: true,
    };

    try {
      // Assuming fetch is available in the environment.
      // In a real scenario, this URL should come from a config.
      const response = await fetch('http://localhost:8003/workflows/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflow),
      });

      if (!response.ok) {
        console.error('Failed to save workflow:', response.statusText);
      } else {
        console.log('Workflow saved successfully');
      }
    } catch (error) {
      console.error('Error saving workflow:', error);
    }
  }
}

console.log('NLULeadAgent class loaded.');
