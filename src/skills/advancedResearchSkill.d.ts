import { SubAgentInput, AdvancedResearchAgentResponse, AgentLLMService } from '../nlu_agents/nlu_types';
export declare class AdvancedResearchAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    private createCanvaDesign;
    analyze(input: SubAgentInput): Promise<AdvancedResearchAgentResponse>;
}
