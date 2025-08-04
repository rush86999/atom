import { SubAgentInput, PracticalAgentResponse, AgentLLMService } from './nlu_types';
export declare class PracticalAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    analyze(input: SubAgentInput): Promise<PracticalAgentResponse>;
}
