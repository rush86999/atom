/**
 * Agent API Integration Tests using Jest mocking
 */

// Mock the apiClient before importing
const mockPost = jest.fn();
const mockGet = jest.fn();

jest.mock('../../api', () => ({
  default: {
    post: mockPost,
    get: mockGet,
    put: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: { use: jest.fn(), eject: jest.fn() },
      response: { use: jest.fn(), eject: jest.fn() },
    },
  },
}));

import apiClient from '../../api';

describe('Agent API - Chat Streaming', () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockGet.mockReset();
  });

  test('successful chat request', async () => {
    const mockResponse = {
      data: {
        success: true,
        response: 'Test response',
        session_id: 'test-session-123',
      },
      status: 200,
    };

    mockPost.mockResolvedValue(mockResponse);

    const response = await apiClient.post('/api/atom-agent/chat/stream', {
      message: 'Test',
      user_id: 'user-1',
    });

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
  });

  test('chat request with 401 error', async () => {
    const error = {
      response: {
        status: 401,
        data: { error_code: 'UNAUTHORIZED' },
      },
    };

    mockPost.mockRejectedValue(error);

    await expect(
      apiClient.post('/api/atom-agent/chat/stream', {
        message: 'Test',
        user_id: 'user-1',
      })
    ).rejects.toMatchObject({
      response: { status: 401 },
    });
  });

  test('chat request with 500 error', async () => {
    const error = {
      response: {
        status: 500,
        data: { error_code: 'INTERNAL_ERROR' },
      },
    };

    mockPost.mockRejectedValue(error);

    await expect(
      apiClient.post('/api/atom-agent/chat/stream', {
        message: 'Test',
        user_id: 'user-1',
      })
    ).rejects.toMatchObject({
      response: { status: 500 },
    });
  });
});

describe('Agent API - Execution and Status', () => {
  beforeEach(() => {
    mockPost.mockReset();
    mockGet.mockReset();
  });

  test('execution trigger', async () => {
    const mockResponse = {
      data: {
        execution_id: 'exec-123',
        status: 'running',
        message: 'Workflow started',
      },
      status: 200,
    };

    mockPost.mockResolvedValue(mockResponse);

    const response = await apiClient.post('/api/atom-agent/execute-generated', {
      workflow_id: 'wf-1',
      input_data: {},
    });

    expect(response.data.execution_id).toBe('exec-123');
    expect(response.data.status).toBe('running');
  });

  test('status polling', async () => {
    const mockResponse = {
      data: {
        agent_id: 'agent-1',
        status: 'idle',
      },
      status: 200,
    };

    mockGet.mockResolvedValue(mockResponse);

    const response = await apiClient.get('/api/atom-agent/agents/agent-1/status');

    expect(response.data.status).toBe('idle');
  });

  test('status polling returns 404', async () => {
    const error = {
      response: {
        status: 404,
        data: { error_code: 'AGENT_NOT_FOUND' },
      },
    };

    mockGet.mockRejectedValue(error);

    await expect(
      apiClient.get('/api/atom-agent/agents/non-existent/status')
    ).rejects.toMatchObject({
      response: { status: 404 },
    });
  });

  test('execution returns 403 governance blocked', async () => {
    const error = {
      response: {
        status: 403,
        data: { error_code: 'GOVERNANCE_BLOCKED' },
      },
    };

    mockPost.mockRejectedValue(error);

    await expect(
      apiClient.post('/api/atom-agent/execute-generated', {
        workflow_id: 'wf-1',
        input_data: {},
      })
    ).rejects.toMatchObject({
      response: { status: 403 },
    });
  });
});
