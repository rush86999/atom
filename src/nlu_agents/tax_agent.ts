import { SubAgentInput, TaxAgentResponse } from './nlu_types';
import { AgentLLMService } from './nlu_types';

export class TaxAgent {
  private agentName: string = 'TaxAgent';

  constructor(private llmService: AgentLLMService) {}

  public async analyze(input: SubAgentInput): Promise<TaxAgentResponse | null> {
    const normalizedQuery = input.userInput.toLowerCase().trim();

    if (normalizedQuery.includes('tax') || normalizedQuery.includes('taxes')) {
      return {
        isTaxRelated: true,
        confidence: 0.9,
        details: 'The query contains tax-related keywords.',
      };
    }

    return null;
  }
}
