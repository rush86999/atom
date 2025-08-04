import { SubAgentInput, LegalDocumentAnalysisAgentResponse, AgentLLMService } from '../nlu_agents/nlu_types';
export declare class LegalDocumentAnalysisAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    private constructPrompt;
    analyze(input: SubAgentInput): Promise<LegalDocumentAnalysisAgentResponse>;
}
