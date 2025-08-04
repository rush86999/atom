import { SubAgentInput, RecruitmentRecommendationAgentResponse, AgentLLMService } from '../nlu_agents/nlu_types';
export declare class RecruitmentRecommendationAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    analyze(input: SubAgentInput): Promise<RecruitmentRecommendationAgentResponse>;
}
