import { AutonomousSystemOrchestrator } from './autonomousSystemOrchestrator';
import { executeGraphQLQuery } from '../../atomic-docker/project/functions/atom-agent/_libs/graphqlClient';
import { OpenAI } from 'openai';

// Mock dependencies
jest.mock('../../atomic-docker/project/functions/atom-agent/_libs/graphqlClient');
jest.mock('openai');

const mockedExecuteGraphQLQuery = executeGraphQLQuery as jest.MockedFunction<typeof executeGraphQLQuery>;
const mockOpenAI = {
  chat: {
    completions: {
      create: jest.fn()
    }
  }
};

describe('AutonomousSystemOrchestrator', () => {
  let orchestrator: AutonomousSystemOrchestrator;

  beforeEach(() => {
    jest.clearAllMocks();
    // Mock OpenAI client
    (OpenAI as jest.MockedClass<typeof OpenAI>).mockImplementation(() => mockOpenAI as any);
    orchestrator = new AutonomousSystemOrchestrator('test-api-key');
  });

  describe('Initialization', () => {
    it('should initialize with correct API key', () => {
      expect(orchestrator).toBeDefined();
      expect(() => new AutonomousSystemOrchestrator('')).toThrow('OpenAI API key is required');
    });
  });

  describe('analyzeDashboardMetrics', () => {
    it('should analyze system metrics successfully', async () => {
      const mockMetrics = {
        cpu_usage: 75,
        memory_usage: 80,
        disk_usage: 60,
        network_io: 1000
      };

      mockOpenAI.chat.completions.create.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              system_health: 'GOOD',
              recommendations: [
                'Consider optimizing memory usage on service A',
                'Scale up CPU allocation for service B'
              ],
              alerts: ['High memory usage detected']
            })
          }
        }]
      });

      const result = await orchestrator.analyzeDashboardMetrics(mockMetrics);

      expect(result.success).toBe(true);
      expect(result.recommendations).toHaveLength(2);
      expect(result.system_health).toBe('GOOD');
      expect(mockOpenAI.chat.completions.create).toHaveBeenCalledWith({
        model: 'gpt-4',
        messages: expect.any(Array),
        temperature: 0.1
      });
    });

    it('should handle API errors gracefully', async () => {
      const mockMetrics = { cpu_usage: 90, memory_usage: 95 };

      mockOpenAI.chat.completions.create.mockRejectedValueOnce(new Error('API error'));

      const result = await orchestrator.analyzeDashboardMetrics(mockMetrics);

      expect(result.success).toBe(false);
      expect(result.error).toContain('Failed to analyze metrics');
    });

    it('should validate required metrics', async () => {
      const result = await orchestrator.analyzeDashboardMetrics({});

      expect(result.success).toBe(false);
      expect(result.error).toContain('Metrics object is required');
    });
  });

  describe('optimizeWorkflows', () => {
    it('should optimize workflows based on system stats', async () => {
      const mockGraphQLData = {
        workflows: [
          { id: 'wf1', current_status: 'ACTIVE', error_rate: 0.05, avg_duration: 5000 },
          { id: 'wf2', current_status: 'FAILED', error_rate: 0.8, avg_duration: 10000 }
        ]
      };

      mockedExecuteGraphQLQuery.mockResolvedValueOnce(mockGraphQLData);

      mockOpenAI.chat.completions.create.mockResolvedValueOnce({
        choices: [{
          message: {
            content: JSON.stringify({
              optimization_plan: {
                recommendations: [
                  { workflow_id: 'wf2', action: 'RESTART', reason: 'High error rate' },
                  { workflow_id: 'wf1', action: 'OPTIMIZE', reason: 'Performance improvement available' }
                ],
                estimated_improvement: '40% performance increase'
              }
            })
          }
        }]
      });

      const result = await orchestrator.optimizeWorkflows();

      expect(result.success).toBe(true);
      expect(result.optimization_plan.recommendations).toHaveLength(2);
      expect(result.optimization_plan.estimated_improvement).toBe('40% performance increase');
      expect(mockedExecuteGraphQLQuery).toHaveBeenCalledWith(
        expect.any(String),
        { user_id: expect.any(String) },
        'GetSystemWorkflows'
      );
    });

    it('should handle empty workflow data', async () => {
      mockedExecuteGraphQLQuery.mockResolvedValueOnce({ workflows: [] });

      const result = await orchestrator.optimizeWorkflows();

      expect(result.success).toBe(true);
      expect(result.optimization_plan.recommendations).toEqual(['No active workflows
