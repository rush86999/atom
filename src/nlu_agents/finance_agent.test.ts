import { FinanceAgent } from './finance_agent';
import { AgentLLMService } from './nlu_types';

describe('FinanceAgent', () => {
  let financeAgent: FinanceAgent;
  let llmMock: AgentLLMService;

  beforeEach(() => {
    llmMock = {
      generate: jest.fn(),
    };
    financeAgent = new FinanceAgent(llmMock);
  });

  it('should identify a create_transaction_rule intent', async () => {
    const input = { userInput: 'create a new rule for Starbucks' };
    const response = await financeAgent.analyze(input);
    expect(response?.intent).toBe('create_transaction_rule');
  });

  it('should identify a list_transaction_rules intent', async () => {
    const input = { userInput: 'show me my transaction rules' };
    const response = await financeAgent.analyze(input);
    expect(response?.intent).toBe('list_transaction_rules');
  });

  it('should identify an update_transaction_rule intent', async () => {
    const input = { userInput: 'update rule 123' };
    const response = await financeAgent.analyze(input);
    expect(response?.intent).toBe('update_transaction_rule');
  });

  it('should identify a delete_transaction_rule intent', async () => {
    const input = { userInput: 'delete rule 456' };
    const response = await financeAgent.analyze(input);
    expect(response?.intent).toBe('delete_transaction_rule');
  });

  it('should return null for non-finance queries', async () => {
    const input = { userInput: 'what is the weather today?' };
    const response = await financeAgent.analyze(input);
    expect(response).toBeNull();
  });
});
