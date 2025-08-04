import { SubAgentInput, EnrichedIntent } from './nlu_types';
import { TurnContext } from 'botbuilder';
import { AgentLLMService } from './nlu_types';
export declare class NLULeadAgent {
    private analyticalAgent;
    private creativeAgent;
    private practicalAgent;
    private synthesizingAgent;
    private dataAnalystSkill;
    private advancedResearchSkill;
    private legalDocumentAnalysisSkill;
    private socialMediaAgent;
    private contentCreationAgent;
    private personalizedShoppingAgent;
    private recruitmentRecommendationAgent;
    private vibeHackingAgent;
    private taxAgent;
    private marketingAutomationAgent;
    private agentName;
    constructor(llmService: AgentLLMService, context: TurnContext, memory: any, functions: any);
    analyzeIntent(input: SubAgentInput): Promise<EnrichedIntent>;
}
