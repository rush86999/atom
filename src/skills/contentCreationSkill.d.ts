import { SubAgentInput, ContentCreationAgentResponse, AgentLLMService } from '../nlu_agents/nlu_types';
export declare class ContentCreationAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    analyze(input: SubAgentInput): Promise<ContentCreationAgentResponse>;
}
