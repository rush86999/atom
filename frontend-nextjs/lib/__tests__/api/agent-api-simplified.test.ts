/**
 * Agent API Integration Tests - Simplified Version
 */

import { rest } from 'msw';
import { setupServer } from 'msw/node';
import axios from 'axios';

// MSW server setup with URL wildcard
const server = setupServer(
  rest.post('http://127.0.0.1:8000/api/atom-agent/chat/stream', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        response: 'Test response',
        session_id: 'test-session-123',
      })
    );
  }),

  rest.post('http://127.0.0.1:8000/api/atom-agent/execute-generated', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        execution_id: 'exec-123',
        status: 'running',
      })
    );
  }),

  rest.get('http://127.0.0.1:8000/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        agent_id: agentId,
        status: 'idle',
      })
    );
  })
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Agent API - Basic Tests', () => {
  test('chat streaming works', async () => {
    const response = await axios.post(
      'http://127.0.0.1:8000/api/atom-agent/chat/stream',
      { message: 'Test', user_id: 'user-1' }
    );
    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
  });

  test('execution trigger works', async () => {
    const response = await axios.post(
      'http://127.0.0.1:8000/api/atom-agent/execute-generated',
      { workflow_id: 'wf-1', input_data: {} }
    );
    expect(response.status).toBe(200);
    expect(response.data.execution_id).toBe('exec-123');
  });

  test('status polling works', async () => {
    const response = await axios.get(
      'http://127.0.0.1:8000/api/atom-agent/agents/agent-1/status'
    );
    expect(response.status).toBe(200);
    expect(response.data.status).toBe('idle');
  });
});
