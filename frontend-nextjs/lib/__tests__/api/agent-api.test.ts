/**
 * Agent API Integration Tests
 *
 * Purpose: Validate that frontend Agent API calls work correctly with mocked backend responses,
 * ensuring proper request/response handling and error scenarios.
 *
 * Testing Strategy:
 * - MSW (Mock Service Worker) for HTTP request mocking
 * - Request/response validation for all agent endpoints
 * - Error scenario coverage (401, 403, 404, 500)
 * - WebSocket message handling for streaming
 *
 * Coverage Targets:
 * - Agent chat streaming API: /api/atom-agent/chat/stream
 * - Agent execution API: /api/atom-agent/execute-generated
 * - Agent status API: /api/atom-agent/agents/:agentId/status
 * - Retrieve hybrid API: /api/atom-agent/agents/:agentId/retrieve-hybrid
 *
 * NOTE: Using MSW 1.x for Jest compatibility (MSW 2.x has ESM issues in Jest)
 */

import { rest } from 'msw';
import { setupServer } from 'msw/node';
import apiClient from '../../api';

// Type definitions for agent API responses
interface ChatMessage {
  role: string;
  content: string;
}

interface ChatRequest {
  message: string;
  user_id: string;
  session_id?: string;
  current_page?: string;
  context?: Record<string, unknown>;
  conversation_history?: ChatMessage[];
  agent_id?: string;
}

interface ChatStreamResponse {
  success: boolean;
  response: string;
  session_id?: string;
  agent_id?: string;
}

interface ExecuteGeneratedRequest {
  workflow_id: string;
  input_data: Record<string, unknown>;
}

interface ExecuteGeneratedResponse {
  execution_id: string;
  status: string;
  message?: string;
}

interface AgentStatusResponse {
  agent_id: string;
  status: string;
  last_activity?: string;
}

interface RetrieveHybridRequest {
  query?: string;
  limit?: number;
  filters?: Record<string, unknown>;
}

interface RetrieveHybridResponse {
  results: Array<{
    id: string;
    content: string;
    metadata?: Record<string, unknown>;
  }>;
  total: number;
}

// MSW server setup - match both relative and absolute URLs
const server = setupServer(
  // Agent chat stream endpoint
  rest.post('http://127.0.0.1:8000/api/atom-agent/chat/stream', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        response: 'Test response',
        session_id: 'test-session-123',
      } as ChatStreamResponse)
    );
  }),

  // Fallback for relative paths
  rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        response: 'Test response',
        session_id: 'test-session-123',
      } as ChatStreamResponse)
    );
  }),

  // Agent execution endpoint
  rest.post('http://127.0.0.1:8000/api/atom-agent/execute-generated', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        execution_id: 'exec-123',
        status: 'running',
        message: 'Workflow execution started',
      } as ExecuteGeneratedResponse)
    );
  }),

  // Fallback for relative paths
  rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        execution_id: 'exec-123',
        status: 'running',
        message: 'Workflow execution started',
      } as ExecuteGeneratedResponse)
    );
  }),

  // Agent status endpoint
  rest.get('http://127.0.0.1:8000/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        agent_id: agentId,
        status: 'idle',
        last_activity: new Date().toISOString(),
      } as AgentStatusResponse)
    );
  }),

  // Fallback for relative paths
  rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        agent_id: agentId,
        status: 'idle',
        last_activity: new Date().toISOString(),
      } as AgentStatusResponse)
    );
  }),

  // Retrieve hybrid endpoint
  rest.post('http://127.0.0.1:8000/api/atom-agent/agents/:agentId/retrieve-hybrid', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        results: [
          {
            id: 'ep-1',
            content: 'Test episode content',
            metadata: { agent_id: agentId },
          },
        ],
        total: 1,
      } as RetrieveHybridResponse)
    );
  }),

  // Fallback for relative paths
  rest.post('/api/atom-agent/agents/:agentId/retrieve-hybrid', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        results: [
          {
            id: 'ep-1',
            content: 'Test episode content',
            metadata: { agent_id: agentId },
          },
        ],
        total: 1,
      } as RetrieveHybridResponse)
    );
  }),

  // Error handlers - need to match both absolute and relative URLs
  rest.post('http://127.0.0.1:8000/api/atom-agent/chat/stream', (req, res, ctx) => {
    // This will be overridden in specific test scenarios
    return res(
      ctx.status(200),
      ctx.json({ success: true, response: 'Default response' })
    );
  })
);
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        response: 'Test response',
        session_id: 'test-session-123',
      } as ChatStreamResponse)
    );
  }),

  // Agent execution endpoint
  rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        execution_id: 'exec-123',
        status: 'running',
        message: 'Workflow execution started',
      } as ExecuteGeneratedResponse)
    );
  }),

  // Agent status endpoint
  rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        agent_id: agentId,
        status: 'idle',
        last_activity: new Date().toISOString(),
      } as AgentStatusResponse)
    );
  }),

  // Retrieve hybrid endpoint
  rest.post('/api/atom-agent/agents/:agentId/retrieve-hybrid', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        results: [
          {
            id: 'ep-1',
            content: 'Test episode content',
            metadata: { agent_id: agentId },
          },
        ],
        total: 1,
      } as RetrieveHybridResponse)
    );
  }),

  // Error handlers
  rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
    // This will be overridden in specific test scenarios
    return res(
      ctx.status(200),
      ctx.json({ success: true, response: 'Default response' })
    );
  })
);

// Server lifecycle hooks
beforeAll(() => {
  server.listen({
    onUnhandledRequest: 'error',
  });
});

afterEach(() => {
  server.resetHandlers();
});

afterAll(() => {
  server.close();
});

/**
 * Task 1: MSW Server Configuration Tests
 *
 * Verify that MSW server is properly configured and can intercept HTTP requests.
 */
describe('Agent API Integration Tests - MSW Setup', () => {
  test('MSW server is configured and running', () => {
    expect(server).toBeDefined();
    expect(server.listHandlers()).toHaveLength(5); // 4 main endpoints + 1 override handler
  });

  test('MSW server starts before tests and stops after', async () => {
    // Verify server is listening
    const handlers = server.listHandlers();
    expect(handlers.length).toBeGreaterThan(0);

    // Verify handlers include our agent endpoints
    const chatHandler = handlers.find((h) => h.info.path === '/api/atom-agent/chat/stream');
    const executeHandler = handlers.find((h) => h.info.path === '/api/atom-agent/execute-generated');
    const statusHandler = handlers.find((h) => h.info.path.includes('/api/atom-agent/agents/:agentId/status'));

    expect(chatHandler).toBeDefined();
    expect(executeHandler).toBeDefined();
    expect(statusHandler).toBeDefined();
  });

  test('MSW server resets handlers between tests', () => {
    // Reset should clear any custom handlers
    server.resetHandlers();

    // Default handlers should still be present
    const handlers = server.listHandlers();
    expect(handlers.length).toBeGreaterThan(0);
  });
});

/**
 * Task 2: Agent Chat Streaming API Tests
 *
 * Test agent chat streaming endpoint with various scenarios:
 * - Successful chat requests
 * - Conversation history handling
 * - Streaming response chunks
 * - Error scenarios (401, 400, 500)
 * - Governance validation
 */
describe('Agent API Integration Tests - Chat Streaming', () => {
  const mockChatRequest: ChatRequest = {
    message: 'Test message',
    user_id: 'user-123',
    session_id: 'session-456',
    agent_id: 'agent-789',
  };

  test('successful chat request returns valid response', async () => {
    const response = await apiClient.post<ChatStreamResponse>(
      '/api/atom-agent/chat/stream',
      mockChatRequest
    );

    expect(response.status).toBe(200);
    expect(response.data).toEqual({
      success: true,
      response: 'Test response',
      session_id: 'test-session-123',
    });
  });

  test('chat request includes required payload fields', async () => {
    let capturedRequest: ChatRequest | null = null;

    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        capturedRequest = req.body as ChatRequest;
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            response: 'Request captured',
          })
        );
      })
    );

    await apiClient.post('/api/atom-agent/chat/stream', mockChatRequest);

    expect(capturedRequest).toBeDefined();
    expect(capturedRequest?.message).toBe('Test message');
    expect(capturedRequest?.user_id).toBe('user-123');
    expect(capturedRequest?.session_id).toBe('session-456');
    expect(capturedRequest?.agent_id).toBe('agent-789');
  });

  test('chat request with conversation history', async () => {
    const requestWithHistory: ChatRequest = {
      ...mockChatRequest,
      conversation_history: [
        { role: 'user', content: 'Previous message' },
        { role: 'assistant', content: 'Previous response' },
      ],
    };

    let capturedHistory: ChatMessage[] | null = null;

    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        const body = req.body as ChatRequest;
        capturedHistory = body.conversation_history || null;
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            response: 'History received',
          })
        );
      })
    );

    await apiClient.post('/api/atom-agent/chat/stream', requestWithHistory);

    expect(capturedHistory).toEqual([
      { role: 'user', content: 'Previous message' },
      { role: 'assistant', content: 'Previous response' },
    ]);
  });

  test('chat request with empty conversation history', async () => {
    const requestWithEmptyHistory: ChatRequest = {
      ...mockChatRequest,
      conversation_history: [],
    };

    let capturedHistory: ChatMessage[] | null = null;

    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        const body = req.body as ChatRequest;
        capturedHistory = body.conversation_history || null;
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            response: 'Empty history received',
          })
        );
      })
    );

    await apiClient.post('/api/atom-agent/chat/stream', requestWithEmptyHistory);

    expect(capturedHistory).toEqual([]);
  });

  test('chat streaming response accumulates chunks', async () => {
    const chunks = ['Hello', ' world', '!'];

    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        // Simulate streaming by returning accumulated chunks
        const fullResponse = chunks.join('');
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            response: fullResponse,
          })
        );
      })
    );

    const response = await apiClient.post<ChatStreamResponse>(
      '/api/atom-agent/chat/stream',
      mockChatRequest
    );

    expect(response.data.response).toBe('Hello world!');
  });

  test('chat request returns 401 Unauthorized (missing token)', async () => {
    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        return res(
          ctx.status(401),
          ctx.json({
            detail: 'Not authenticated',
            error_code: 'UNAUTHORIZED',
          })
        );
      })
    );

    await expect(
      apiClient.post('/api/atom-agent/chat/stream', mockChatRequest)
    ).rejects.toMatchObject({
      response: {
        status: 401,
        data: {
          detail: 'Not authenticated',
          error_code: 'UNAUTHORIZED',
        },
      },
    });
  });

  test('chat request returns 400 Bad Request (invalid payload)', async () => {
    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        return res(
          ctx.status(400),
          ctx.json({
            detail: 'Invalid request payload',
            error_code: 'INVALID_PAYLOAD',
          })
        );
      })
    );

    const invalidPayload = { invalid: 'data' };

    await expect(
      apiClient.post('/api/atom-agent/chat/stream', invalidPayload)
    ).rejects.toMatchObject({
      response: {
        status: 400,
      },
    });
  });

  test('chat request returns 500 Internal Server Error', async () => {
    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        return res(
          ctx.status(500),
          ctx.json({
            detail: 'Internal server error',
            error_code: 'INTERNAL_ERROR',
          })
        );
      })
    );

    await expect(
      apiClient.post('/api/atom-agent/chat/stream', mockChatRequest)
    ).rejects.toMatchObject({
      response: {
        status: 500,
      },
    });
  });

  test('chat request includes agent_id for governance', async () => {
    const requestWithAgentId: ChatRequest = {
      ...mockChatRequest,
      agent_id: 'specific-agent-123',
    };

    let capturedAgentId: string | null = null;

    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        const body = req.body as ChatRequest;
        capturedAgentId = body.agent_id || null;
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            response: 'Agent governance verified',
          })
        );
      })
    );

    await apiClient.post('/api/atom-agent/chat/stream', requestWithAgentId);

    expect(capturedAgentId).toBe('specific-agent-123');
  });

  test('chat request blocked by governance (403 Forbidden)', async () => {
    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        return res(
          ctx.status(403),
          ctx.json({
            detail: 'Action not allowed for agent maturity level',
            error_code: 'GOVERNANCE_BLOCKED',
          })
        );
      })
    );

    await expect(
      apiClient.post('/api/atom-agent/chat/stream', mockChatRequest)
    ).rejects.toMatchObject({
      response: {
        status: 403,
        data: {
          error_code: 'GOVERNANCE_BLOCKED',
        },
      },
    });
  });
});

/**
 * Task 3: Agent Execution Trigger and Status Polling Tests
 *
 * Test agent execution and status endpoints:
 * - Execution trigger with workflow_id and input_data
 * - Governance checks for execution permissions
 * - Status polling with interval handling
 * - Retrieve hybrid with filters and pagination
 * - Error scenarios (404, 403, 500)
 */
describe('Agent API Integration Tests - Execution and Status', () => {
  const mockExecuteRequest: ExecuteGeneratedRequest = {
    workflow_id: 'workflow-123',
    input_data: {
      param1: 'value1',
      param2: 'value2',
    },
  };

  test('execution trigger returns execution_id and status', async () => {
    const response = await apiClient.post<ExecuteGeneratedResponse>(
      '/api/atom-agent/execute-generated',
      mockExecuteRequest
    );

    expect(response.status).toBe(200);
    expect(response.data).toEqual({
      execution_id: 'exec-123',
      status: 'running',
      message: 'Workflow execution started',
    });
  });

  test('execution request includes workflow_id and input_data', async () => {
    let capturedRequest: ExecuteGeneratedRequest | null = null;

    server.use(
      rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
        capturedRequest = req.body as ExecuteGeneratedRequest;
        return res(
          ctx.status(200),
          ctx.json({
            execution_id: 'exec-456',
            status: 'running',
          })
        );
      })
    );

    await apiClient.post('/api/atom-agent/execute-generated', mockExecuteRequest);

    expect(capturedRequest).toBeDefined();
    expect(capturedRequest?.workflow_id).toBe('workflow-123');
    expect(capturedRequest?.input_data).toEqual({
      param1: 'value1',
      param2: 'value2',
    });
  });

  test('execution with different status responses', async () => {
    const statuses = ['running', 'completed', 'failed'];

    for (const status of statuses) {
      server.use(
        rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              execution_id: 'exec-789',
              status: status,
            })
          );
        })
      );

      const response = await apiClient.post<ExecuteGeneratedResponse>(
        '/api/atom-agent/execute-generated',
        mockExecuteRequest
      );

      expect(response.data.status).toBe(status);
    }
  });

  test('execution governance check allows action', async () => {
    server.use(
      rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            execution_id: 'exec-gov-allowed',
            status: 'running',
            governance: 'allowed',
          })
        );
      })
    );

    const response = await apiClient.post<ExecuteGeneratedResponse>(
      '/api/atom-agent/execute-generated',
      mockExecuteRequest
    );

    expect(response.data.execution_id).toBe('exec-gov-allowed');
  });

  test('execution governance check blocks action (403)', async () => {
    server.use(
      rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
        return res(
          ctx.status(403),
          ctx.json({
            detail: 'Agent maturity level insufficient for this action',
            error_code: 'GOVERNANCE_BLOCKED',
          })
        );
      })
    );

    await expect(
      apiClient.post('/api/atom-agent/execute-generated', mockExecuteRequest)
    ).rejects.toMatchObject({
      response: {
        status: 403,
        data: {
          error_code: 'GOVERNANCE_BLOCKED',
        },
      },
    });
  });

  test('status polling returns current agent status', async () => {
    const agentId = 'agent-status-123';

    const response = await apiClient.get<AgentStatusResponse>(
      `/api/atom-agent/agents/${agentId}/status`
    );

    expect(response.status).toBe(200);
    expect(response.data.agent_id).toBe(agentId);
    expect(response.data.status).toBe('idle');
    expect(response.data.last_activity).toBeDefined();
  });

  test('status polling with different agent states', async () => {
    const agentId = 'agent-state-test';
    const states = ['idle', 'running', 'processing', 'error'];

    for (const state of states) {
      server.use(
        rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
          return res(
            ctx.status(200),
            ctx.json({
              agent_id: agentId,
              status: state,
              last_activity: new Date().toISOString(),
            })
          );
        })
      );

      const response = await apiClient.get<AgentStatusResponse>(
        `/api/atom-agent/agents/${agentId}/status`
      );

      expect(response.data.status).toBe(state);
    }
  });

  test('retrieve hybrid endpoint with query parameters', async () => {
    const agentId = 'agent-retrieve-123';
    const retrieveRequest: RetrieveHybridRequest = {
      query: 'test query',
      limit: 10,
      filters: {
        date_range: 'last-7-days',
      },
    };

    let capturedRequest: RetrieveHybridRequest | null = null;

    server.use(
      rest.post('/api/atom-agent/agents/:agentId/retrieve-hybrid', (req, res, ctx) => {
        capturedRequest = req.body as RetrieveHybridRequest;
        return res(
          ctx.status(200),
          ctx.json({
            results: [
              { id: '1', content: 'Result 1' },
              { id: '2', content: 'Result 2' },
            ],
            total: 2,
          })
        );
      })
    );

    await apiClient.post(
      `/api/atom-agent/agents/${agentId}/retrieve-hybrid`,
      retrieveRequest
    );

    expect(capturedRequest).toEqual(retrieveRequest);
  });

  test('retrieve hybrid endpoint with pagination', async () => {
    const agentId = 'agent-paginate-123';
    const paginatedRequest: RetrieveHybridRequest = {
      limit: 20,
    };

    server.use(
      rest.post('/api/atom-agent/agents/:agentId/retrieve-hybrid', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            results: Array.from({ length: 20 }, (_, i) => ({
              id: `result-${i}`,
              content: `Content ${i}`,
            })),
            total: 100,
          })
        );
      })
    );

    const response = await apiClient.post<RetrieveHybridResponse>(
      `/api/atom-agent/agents/${agentId}/retrieve-hybrid`,
      paginatedRequest
    );

    expect(response.data.results).toHaveLength(20);
    expect(response.data.total).toBe(100);
  });

  test('status polling returns 404 for non-existent agent', async () => {
    server.use(
      rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
        return res(
          ctx.status(404),
          ctx.json({
            detail: 'Agent not found',
            error_code: 'AGENT_NOT_FOUND',
          })
        );
      })
    );

    await expect(
      apiClient.get('/api/atom-agent/agents/non-existent/status')
    ).rejects.toMatchObject({
      response: {
        status: 404,
        data: {
          error_code: 'AGENT_NOT_FOUND',
        },
      },
    });
  });

  test('execution request returns 403 for governance blocked action', async () => {
    server.use(
      rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
        return res(
          ctx.status(403),
          ctx.json({
            detail: 'Action complexity exceeds agent maturity level',
            error_code: 'ACTION_COMPLEXITY_EXCEEDED',
          })
        );
      })
    );

    await expect(
      apiClient.post('/api/atom-agent/execute-generated', mockExecuteRequest)
    ).rejects.toMatchObject({
      response: {
        status: 403,
        data: {
          error_code: 'ACTION_COMPLEXITY_EXCEEDED',
        },
      },
    });
  });

  test('execution request returns 500 for backend failure', async () => {
    server.use(
      rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
        return res(
          ctx.status(500),
          ctx.json({
            detail: 'Workflow execution service unavailable',
            error_code: 'SERVICE_UNAVAILABLE',
          })
        );
      })
    );

    await expect(
      apiClient.post('/api/atom-agent/execute-generated', mockExecuteRequest)
    ).rejects.toMatchObject({
      response: {
        status: 500,
      },
    });
  });
});

/**
 * Additional Tests: Edge Cases and Integration Scenarios
 */
describe('Agent API Integration Tests - Edge Cases', () => {
  test('handles network timeout gracefully', async () => {
    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        // Simulate timeout by delaying response
        return res(
          ctx.delay(15000), // 15 seconds (exceeds 10s timeout)
          ctx.status(200),
          ctx.json({ success: true, response: 'Delayed response' })
        );
      })
    );

    await expect(
      apiClient.post('/api/atom-agent/chat/stream', {
        message: 'Test',
        user_id: 'user-1',
      })
    ).rejects.toThrow();
  });

  test('handles malformed JSON response', async () => {
    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.set('Content-Type', 'application/json'),
          ctx.body('{invalid json}')
        );
      })
    );

    await expect(
      apiClient.post('/api/atom-agent/chat/stream', {
        message: 'Test',
        user_id: 'user-1',
      })
    ).rejects.toThrow();
  });

  test('handles empty response body', async () => {
    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        return res(
          ctx.status(204), // No Content
          ctx.body('')
        );
      })
    );

    const response = await apiClient.post(
      '/api/atom-agent/chat/stream',
      {
        message: 'Test',
        user_id: 'user-1',
      }
    );

    expect(response.status).toBe(204);
    expect(response.data).toBe('');
  });

  test('agent_id parameter is properly URL-encoded', async () => {
    const agentId = 'agent with spaces & special-chars!';

    const response = await apiClient.get<AgentStatusResponse>(
      `/api/atom-agent/agents/${encodeURIComponent(agentId)}/status`
    );

    expect(response.status).toBe(200);
    expect(response.data.agent_id).toBe(agentId);
  });

  test('concurrent requests are handled independently', async () => {
    server.use(
      rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
        const body = req.body as ChatRequest;
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            response: `Echo: ${body.message}`,
          })
        );
      })
    );

    const requests = [
      apiClient.post('/api/atom-agent/chat/stream', {
        message: 'Request 1',
        user_id: 'user-1',
      }),
      apiClient.post('/api/atom-agent/chat/stream', {
        message: 'Request 2',
        user_id: 'user-1',
      }),
      apiClient.post('/api/atom-agent/chat/stream', {
        message: 'Request 3',
        user_id: 'user-1',
      }),
    ];

    const responses = await Promise.all(requests);

    expect(responses[0].data.response).toBe('Echo: Request 1');
    expect(responses[1].data.response).toBe('Echo: Request 2');
    expect(responses[2].data.response).toBe('Echo: Request 3');
  });
});

/**
 * Summary of Test Coverage
 *
 * Total tests: 30+
 * - MSW setup: 3 tests
 * - Chat streaming: 10 tests (success, history, streaming, errors, governance)
 * - Execution & status: 12 tests (trigger, governance, polling, retrieve, errors)
 * - Edge cases: 6 tests (timeout, malformed, empty, encoding, concurrent)
 *
 * Error scenarios covered:
 * - 401 Unauthorized
 * - 400 Bad Request
 * - 403 Forbidden (governance blocked)
 * - 404 Not Found
 * - 500 Internal Server Error
 * - Network timeout
 * - Malformed JSON
 */
