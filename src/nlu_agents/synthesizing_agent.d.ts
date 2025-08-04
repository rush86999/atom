import { SubAgentInput, AnalyticalAgentResponse, CreativeAgentResponse, PracticalAgentResponse, TaxAgentResponse, EnrichedIntent, AgentLLMService } from './nlu_types';
export declare class SynthesizingAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    synthesize(input: SubAgentInput, analytical: AnalyticalAgentResponse | null, creative: CreativeAgentResponse | null, practical: PracticalAgentResponse | null, socialMedia: any, contentCreation: any, personalizedShopping: any, recruitmentRecommendation: any, vibeHacking: any, tax: TaxAgentResponse | null, marketingAutomation: any): Promise<Partial<EnrichedIntent>>;
}
