import { WorkflowAgent } from './workflow_agent';
import { executeGraphQLQuery } from '../../atomic-docker/project/functions/atom-agent/_libs/graphqlClient';
import { SubAgentInput } from './nlu_types';
import { OpenAI } from 'openai';

// Mock dependencies
jest.mock('../../atomic-docker/project/functions/atom-agent/_libs/graphqlClient');
jest.mock('openai');

const mockedExecuteGraphQLQuery = executeGraphQLQuery as jest.MockedFunction<typeof executeGraphQLQuery>;
const mockedOpenAI = mocked(OpenAI);

describe('WorkflowAgent', () => {
  let agent: WorkflowAgent;

  beforeEach(() => {
    jest.clearAllMocks();
    agent = new WorkflowAgent('test-api-key');

    // Mock OpenAI
    mockedOpenAI.mockImplementation(() => ({
      chat: {
        completions: {
          create: jest.fn()
        }
      }
    } as any));
  });

  describe('Initialization', () => {
    it('should initialize with API key', () => {
      expect(agent).toBeDefined();
      expect(() => new WorkflowAgent('')).toThrow('API key is required');
    });
  });

  describe('analyze workflow', () => {
    it('should analyze workflow creation intent', async () => {
      const mockLLMResponse = {
        choices: [{
          message: {
            content: JSON.stringify({
              workflowType: 'email_automation',
              steps: ['trigger', 'condition', 'action'],
              parameters: {
                triggerType: 'new_email',
                conditions: ['from_client', 'contains_keyword'],
                actions: ['create_task', 'send_slack']
              }
            })
          }
        }]
      };

      (mockedOpenAI.client.chat.completions.create as jest.Mock).mockResolvedValue(mockLLMResponse);

      const input: SubAgentInput = {
        userInput: 'create a workflow that creates a task when I receive an email from a client',
        userId: 'test-user-123',
        context: { preferences: { notification_channels: ['email', 'slack'] } }
      };

      const result = await agent.analyze(input);

      expect(result.success).toBe(true);
      expect(result.workflow).toEqual({
        workflowType: 'email_automation',
        steps: ['trigger', 'condition', 'action'],
        parameters: expect.objectContaining({
          triggerType: 'new_email'
        })
      });
    });

    it('should handle complex workflow with multiple conditions', async () => {
      const mockLLMResponse = {
        choices: [{
          message: {
            content: JSON.stringify({
              workflowType: 'business_rules',
              triggers: [{ type: 'time', schedule: 'daily' }],
              conditions: [
                { type: 'hubspot', field: 'deal_stage', operator: 'equals', value: 'proposal_sent' },
                { type: 'date', field: 'last_activity', operator: 'greater_than', value: '30_days' }
              ],
              actions: [
                { type: 'email', template: 'follow_up_template' },
                { type: 'slack', channel: '@sales-team', message: 'Follow-up required' }
              ]
            })
          }
        }]
      };

      (mockedOpenAI.client.chat.completions.create as jest.Mock).mockResolvedValue(mockLLMResponse);

      const input: SubAgentInput = {
        userInput: 'create a daily workflow that sends follow-up emails to deals in proposal stage inactive for 30 days',
        userId: 'test-user-123'
      };

      const result = await agent.analyze(input);

      expect(result.success).toBe(true);
      expect(result.workflow.conditions).toHaveLength(2);
      expect(result.workflow.actions).toHaveLength(2);
    });

    it('should handle error gracefully on LLM failure', async () => {
      (mockedOpenAI.client.chat.completions.create as jest.Mock).mockRejectedValue(new Error('API Rate Limit'));

      const input: SubAgentInput = {
        userInput: 'create workflow',
        userId: 'test-user-123'
      };

      const result = await agent.analyze(input);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Error analyzing workflow');
    });

    it('should validate required fields', async () => {
      const mockLLMResponse = {
        choices: [{
          message: {
            content: JSON.stringify({
              workflowType: '',
              steps: []
            })
          }
        }]
      };

      (mockedOpenAI.client.chat.completions.create as jest.Mock).mockResolvedValue(mockLLMResponse);

      const input: SubAgentInput = {
        userInput: '',
        userId: 'test-user-123'
      };

      const result = await agent.analyze(input);

      expect(result.success).toBe(false
