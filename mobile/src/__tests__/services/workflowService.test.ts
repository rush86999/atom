/**
 * Workflow Service Tests
 *
 * Tests for workflow API operations:
 * - List workflows with filter/query params
 * - Workflow details, execution details, logs and steps
 * - Trigger/cancel flows
 * - Search with query encoding
 * - Error handling (server errors, failure responses)
 */

import {
  getWorkflows,
  getWorkflowById,
  triggerWorkflow,
  getExecutionById,
  getExecutionLogs,
  getExecutionSteps,
  cancelExecution,
  getWorkflowExecutions,
  searchWorkflows,
} from '../../services/workflowService';
import apiService from '../../services/api';

// workflowService imports the DEFAULT export from './api'. Mock both the
// default and the named export with the same jest.fn() instances.
jest.mock('../../services/api', () => {
  const api = {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  };
  return { __esModule: true, default: api, apiService: api };
});

const mockApiService = apiService as jest.Mocked<typeof apiService>;

const okResponse = (data: any) => ({ success: true, data });
const errorResponse = (error: string) => ({ success: false, error });

const workflow = {
  id: 'wf-1',
  name: 'Sales Pipeline',
  description: 'Moves deals through stages',
  definition: { steps: [] },
  schema: {},
  isActive: true,
  createdAt: '2024-01-01T00:00:00Z',
  updatedAt: '2024-01-02T00:00:00Z',
};

describe('workflowService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ========================================================================
  // getWorkflows Tests
  // ========================================================================

  describe('getWorkflows', () => {
    test('should fetch workflows and return list with total', async () => {
      const workflows = [workflow, { ...workflow, id: 'wf-2' }];
      mockApiService.get.mockResolvedValue(okResponse(workflows));

      const result = await getWorkflows();

      expect(mockApiService.get).toHaveBeenCalledWith('/api/mobile/workflows?');
      expect(result).toEqual({ workflows, total: 2 });
    });

    test('should build query string from all filters', async () => {
      mockApiService.get.mockResolvedValue(okResponse([]));

      await getWorkflows({
        status: 'active',
        category: 'sales',
        search: 'pipeline',
        sort_by: 'updated_at',
        sort_order: 'desc',
      });

      expect(mockApiService.get).toHaveBeenCalledWith(
        '/api/mobile/workflows?status=active&category=sales&search=pipeline&sort_by=updated_at&sort_order=desc'
      );
    });

    test('should omit empty filters from the query string', async () => {
      mockApiService.get.mockResolvedValue(okResponse([]));

      await getWorkflows({ status: 'active' });

      expect(mockApiService.get).toHaveBeenCalledWith('/api/mobile/workflows?status=active');
    });

    test('should throw the server error when the fetch fails', async () => {
      mockApiService.get.mockResolvedValue(errorResponse('Workflows unavailable'));

      await expect(getWorkflows()).rejects.toThrow('Workflows unavailable');
    });

    test('should throw a fallback error when no server error is provided', async () => {
      mockApiService.get.mockResolvedValue({ success: false });

      await expect(getWorkflows()).rejects.toThrow('Failed to fetch workflows');
    });
  });

  // ========================================================================
  // getWorkflowById Tests
  // ========================================================================

  describe('getWorkflowById', () => {
    test('should fetch a single workflow by id', async () => {
      mockApiService.get.mockResolvedValue(okResponse(workflow));

      const result = await getWorkflowById('wf-1');

      expect(mockApiService.get).toHaveBeenCalledWith('/api/workflows/wf-1');
      expect(result).toEqual(workflow);
    });

    test('should throw when the workflow cannot be fetched', async () => {
      mockApiService.get.mockResolvedValue(errorResponse('Workflow not found'));

      await expect(getWorkflowById('missing')).rejects.toThrow('Workflow not found');
    });
  });

  // ========================================================================
  // triggerWorkflow Tests
  // ========================================================================

  describe('triggerWorkflow', () => {
    test('should POST the trigger request payload', async () => {
      const response = { execution_id: 'exec-1', status: 'pending' };
      mockApiService.post.mockResolvedValue(okResponse(response));

      const request = { workflow_id: 'wf-1', input: { deal: 'Acme' }, priority: 7 };
      const result = await triggerWorkflow(request);

      expect(mockApiService.post).toHaveBeenCalledWith(
        '/api/mobile/workflows/trigger',
        request
      );
      expect(result).toEqual(response);
    });

    test('should throw when the trigger fails', async () => {
      mockApiService.post.mockResolvedValue(errorResponse('Workflow is inactive'));

      await expect(
        triggerWorkflow({ workflow_id: 'wf-1', input: {} })
      ).rejects.toThrow('Workflow is inactive');
    });
  });

  // ========================================================================
  // Execution Tests
  // ========================================================================

  describe('Execution queries', () => {
    const execution = {
      id: 'exec-1',
      workflow_id: 'wf-1',
      status: 'completed',
      input: {},
      started_at: '2024-01-01T00:00:00Z',
    };

    test('should fetch execution details', async () => {
      mockApiService.get.mockResolvedValue(okResponse(execution));

      const result = await getExecutionById('exec-1');

      expect(mockApiService.get).toHaveBeenCalledWith('/api/executions/exec-1');
      expect(result).toEqual(execution);
    });

    test('should throw when execution details are unavailable', async () => {
      mockApiService.get.mockResolvedValue(errorResponse('Execution not found'));

      await expect(getExecutionById('missing')).rejects.toThrow('Execution not found');
    });

    test('should fetch execution logs', async () => {
      const logs = [{ timestamp: '2024-01-01T00:00:00Z', level: 'info', message: 'started' }];
      mockApiService.get.mockResolvedValue(okResponse(logs));

      const result = await getExecutionLogs('exec-1');

      expect(mockApiService.get).toHaveBeenCalledWith('/api/executions/exec-1/logs');
      expect(result).toEqual(logs);
    });

    test('should throw when execution logs are unavailable', async () => {
      mockApiService.get.mockResolvedValue(errorResponse('Logs unavailable'));

      await expect(getExecutionLogs('exec-1')).rejects.toThrow('Logs unavailable');
    });

    test('should fetch execution steps', async () => {
      const steps = [{ step_id: 's1', status: 'completed' }];
      mockApiService.get.mockResolvedValue(okResponse(steps));

      const result = await getExecutionSteps('exec-1');

      expect(mockApiService.get).toHaveBeenCalledWith('/api/executions/exec-1/steps');
      expect(result).toEqual(steps);
    });

    test('should throw when execution steps are unavailable', async () => {
      mockApiService.get.mockResolvedValue(errorResponse('Steps unavailable'));

      await expect(getExecutionSteps('exec-1')).rejects.toThrow('Steps unavailable');
    });

    test('should cancel a running execution', async () => {
      const response = { message: 'Execution cancelled' };
      mockApiService.post.mockResolvedValue(okResponse(response));

      const result = await cancelExecution('exec-1');

      expect(mockApiService.post).toHaveBeenCalledWith('/api/executions/exec-1/cancel');
      expect(result).toEqual(response);
    });

    test('should throw when cancelling fails', async () => {
      mockApiService.post.mockResolvedValue(errorResponse('Cannot cancel completed execution'));

      await expect(cancelExecution('exec-1')).rejects.toThrow(
        'Cannot cancel completed execution'
      );
    });

    test('should fetch recent executions with default limit', async () => {
      mockApiService.get.mockResolvedValue(okResponse([]));

      await getWorkflowExecutions('wf-1');

      expect(mockApiService.get).toHaveBeenCalledWith(
        '/api/workflows/wf-1/executions?limit=10'
      );
    });

    test('should fetch recent executions with custom limit', async () => {
      mockApiService.get.mockResolvedValue(okResponse([]));

      await getWorkflowExecutions('wf-1', 25);

      expect(mockApiService.get).toHaveBeenCalledWith(
        '/api/workflows/wf-1/executions?limit=25'
      );
    });

    test('should throw when recent executions cannot be fetched', async () => {
      mockApiService.get.mockResolvedValue(errorResponse('Executions unavailable'));

      await expect(getWorkflowExecutions('wf-1')).rejects.toThrow(
        'Executions unavailable'
      );
    });
  });

  // ========================================================================
  // searchWorkflows Tests
  // ========================================================================

  describe('searchWorkflows', () => {
    test('should search with an URL-encoded query', async () => {
      const results = [workflow];
      mockApiService.get.mockResolvedValue(okResponse(results));

      const result = await searchWorkflows('deal pipeline & active');

      expect(mockApiService.get).toHaveBeenCalledWith(
        '/api/mobile/workflows?search=deal%20pipeline%20%26%20active'
      );
      expect(result).toEqual(results);
    });

    test('should throw when the search fails', async () => {
      mockApiService.get.mockResolvedValue(errorResponse('Search unavailable'));

      await expect(searchWorkflows('x')).rejects.toThrow('Search unavailable');
    });
  });
});
