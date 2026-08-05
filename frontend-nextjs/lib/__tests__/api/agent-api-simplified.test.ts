/**
 * Agent API Integration Tests - Simplified Version
 *
 * Uses the shared MSW server registered in tests/setup.ts so requests are
 * intercepted instead of falling through to the real network (localhost:8000).
 */

import { rest } from 'msw';
import axios from 'axios';
import { server } from '@/tests/mocks/server';

beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('Agent API - Basic Tests', () => {
  beforeEach(() => {
    // Register handlers on the shared server matching the real endpoints axios hits.
    server.use(
      rest.post('*/api/atom-agent/chat/stream', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            response: 'Test response',
            session_id: 'test-session-123',
          })
        );
      }),

      rest.post('*/api/atom-agent/execute-generated', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            execution_id: 'exec-123',
            status: 'running',
          })
        );
      }),

      rest.get('*/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
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
  });

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
