import { SubAgentInput, TaxAgentResponse } from './nlu_types';
import { AgentLLMService } from './nlu_types';
export declare class TaxAgent {
    private llmService;
    private agentName;
    constructor(llmService: AgentLLMService);
    analyze(input: SubAgentInput): Promise<TaxAgentResponse | null>;
}
