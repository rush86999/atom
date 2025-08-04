import { SubAgentInput, AnalyticalAgentResponse, AgentLLMService } from './nlu_types';
export declare class AnalyticalAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    analyze(input: SubAgentInput): Promise<AnalyticalAgentResponse>;
}
