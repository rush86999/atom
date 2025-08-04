import { SubAgentInput, VibeHackingAgentResponse, AgentLLMService } from '../nlu_agents/nlu_types';
export declare class VibeHackingAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    analyze(input: SubAgentInput): Promise<VibeHackingAgentResponse>;
}
