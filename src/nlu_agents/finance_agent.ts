import { SubAgentInput, FinanceAgentResponse } from './nlu_types';
import { AgentLLMService } from './nlu_types';

export class FinanceAgent {
  private agentName: string = 'FinanceAgent';

  constructor(private llmService: AgentLLMService) {}

  public async analyze(input: SubAgentInput): Promise<FinanceAgentResponse | null> {
    const normalizedQuery = input.userInput.toLowerCase().trim();

    const createKeywords = ['create rule', 'new rule', 'add rule', 'always categorize'];
    const listKeywords = ['list rules', 'show rules', 'see rules'];
    const updateKeywords = ['update rule', 'change rule', 'modify rule'];
    const deleteKeywords = ['delete rule', 'remove rule'];

    if (createKeywords.some(keyword => normalizedQuery.includes(keyword))) {
      return {
        isFinanceRelated: true,
        confidence: 0.9,
        intent: 'create_transaction_rule',
        details: 'The query seems to be about creating a new transaction categorization rule.',
      };
    }

    if (listKeywords.some(keyword => normalizedQuery.includes(keyword))) {
      return {
        isFinanceRelated: true,
        confidence: 0.9,
        intent: 'list_transaction_rules',
        details: 'The query seems to be about listing existing transaction categorization rules.',
      };
    }

    if (updateKeywords.some(keyword => normalizedQuery.includes(keyword))) {
      return {
        isFinanceRelated: true,
        confidence: 0.9,
        intent: 'update_transaction_rule',
        details: 'The query seems to be about updating an existing transaction categorization rule.',
      };
    }

    if (deleteKeywords.some(keyword => normalizedQuery.includes(keyword))) {
      return {
        isFinanceRelated: true,
        confidence: 0.9,
        intent: 'delete_transaction_rule',
        details: 'The query seems to be about deleting an existing transaction categorization rule.',
      };
    }

    return null;
  }
}
