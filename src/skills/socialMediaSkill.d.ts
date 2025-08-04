import { SubAgentInput, SocialMediaAgentResponse, AgentLLMService } from '../nlu_agents/nlu_types';
export declare class SocialMediaAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    analyze(input: SubAgentInput): Promise<SocialMediaAgentResponse>;
}
