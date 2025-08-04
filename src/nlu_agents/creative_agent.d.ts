import { SubAgentInput, CreativeAgentResponse, AgentLLMService } from './nlu_types';
export declare class CreativeAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    analyze(input: SubAgentInput): Promise<CreativeAgentResponse>;
}
