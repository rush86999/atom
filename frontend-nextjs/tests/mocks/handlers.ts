/**
 * MSW (Mock Service Worker) Handlers
 *
 * Reusable mock handlers for all API endpoints used in frontend integration tests.
 *
 * Handler Categories:
 * - commonHandlers: Health checks, CORS, and shared endpoints
 * - agentHandlers: Agent execution, chat streaming, workflow execution
 * - canvasHandlers: Form submissions, canvas status, canvas lifecycle
 * - deviceHandlers: Camera, screen recording, location, notifications, command execution
 * - agentErrorHandlers: Agent API error scenarios (500, 503, 429, 404, timeout)
 * - canvasErrorHandlers: Canvas API error scenarios (403, 500, 503, 404)
 * - deviceErrorHandlers: Device API error scenarios (503, timeout, 403, network errors)
 * - integrationErrorHandlers: OAuth/API integration errors (access_denied, timeout, 429, 503)
 *
 * Usage:
 * ```typescript
 * import { allHandlers, agentHandlers, agentErrorHandlers, overrideHandler } from '@/tests/mocks/handlers';
 *
 * // Use default handlers
 * server.use(...allHandlers);
 *
 * // Override specific handler for test scenario
 * overrideHandler(
 *   rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
 *     return res(ctx.status(404), ctx.json({ error: 'Agent not found' }));
 *   })
 * );
 *
 * // Use predefined error scenarios
 * server.use(...agentErrorHandlers.internalServerError);
 * server.use(...agentErrorHandlers.serviceUnavailable);
 *
 * // Test error recovery flows
 * test('recovers from 503 error', async () => {
 *   server.use(...agentErrorHandlers.serviceUnavailable);
 *   // ... test code that should retry and recover
 * });
 * ```
 *
 * Common Error Testing Patterns:
 *
 * 1. Server Error (500) - Test error boundaries and user-friendly messages
 *    ```typescript
 *    server.use(...agentErrorHandlers.internalServerError);
 *    await waitFor(() => expect(screen.getByText(/something went wrong/i)).toBeInTheDocument());
 *    ```
 *
 * 2. Service Unavailable (503) - Test retry logic and graceful degradation
 *    ```typescript
 *    server.use(...agentErrorHandlers.serviceUnavailable);
 *    // Verify loading state, then retry, then success
 *    ```
 *
 * 3. Rate Limiting (429) - Test backoff and retry-after header handling
 *    ```typescript
 *    server.use(...agentErrorHandlers.rateLimited);
 *    await waitFor(() => expect(screen.getByText(/too many requests/i)).toBeInTheDocument());
 *    ```
 *
 * 4. Timeout - Test timeout handling and user feedback
 *    ```typescript
 *    server.use(...agentErrorHandlers.timeout);
 *    await waitFor(() => expect(screen.getByText(/request timed out/i)).toBeInTheDocument());
 *    ```
 *
 * 5. Governance Errors (403) - Test maturity level gates
 *    ```typescript
 *    server.use(...canvasErrorHandlers.governanceCheckFailed);
 *    await waitFor(() => expect(screen.getByText(/insufficient maturity/i)).toBeInTheDocument());
 *    ```
 *
 * Note: This file contains endpoint-specific handlers. For generic error handlers
 * (network errors, malformed responses, etc.), see tests/mocks/errors.ts
 */

import { rest, RestHandler } from 'msw';

// ============================================================================
// Type Definitions
// ============================================================================

interface AgentExecution {
  id: string;
  agent_id: string;
  status: string;
  created_at: string;
}

interface CanvasAudit {
  id: string;
  canvas_id: string;
  action: string;
  timestamp: string;
}

interface DeviceSession {
  id: string;
  device_node_id: string;
  status: string;
}

// ============================================================================
// Common Utility Handlers
// ============================================================================

export const commonHandlers = [
  // Health check endpoint
  rest.get('/api/health', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
        version: '5.0.0'
      })
    );
  }),

  // Liveness probe (for Kubernetes)
  rest.get('/health/live', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ status: 'ok' })
    );
  }),

  // Readiness probe (for Kubernetes)
  rest.get('/health/ready', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'ready',
        database: 'connected',
        disk: 'ok'
      })
    );
  }),

  // Metrics endpoint (for Prometheus)
  rest.get('/health/metrics', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.set('Content-Type', 'text/plain'),
      ctx.body('# Mock Prometheus metrics\n')
    );
  }),

  // CORS preflight handling
  rest.options('*', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.set('Access-Control-Allow-Origin', '*'),
      ctx.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
      ctx.set('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    );
  }),
];

// ============================================================================
// Agent API Handlers
// ============================================================================

export const agentHandlers = [
  // Chat streaming endpoint
  rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        response: 'Mock agent response',
        execution_id: 'exec-mock-123',
        agent_id: 'agent-mock-456',
        timestamp: new Date().toISOString()
      })
    );
  }),

  // Execute generated workflow
  rest.post('/api/atom-agent/execute-generated', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        execution_id: 'exec-mock-456',
        status: 'running',
        workflow_id: 'workflow-default',
        created_at: new Date().toISOString()
      })
    );
  }),

  // Get agent status
  rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        agent_id: agentId,
        status: 'idle',
        maturity_level: 'AUTONOMOUS',
        confidence: 0.95,
        last_execution: null,
        created_at: new Date().toISOString()
      })
    );
  }),

  // Hybrid retrieval (episodic memory + knowledge graph)
  rest.post('/api/atom-agent/agents/:agentId/retrieve-hybrid', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        results: [],
        query: 'test query',
        retrieval_method: 'hybrid',
        agent_id: agentId,
        timestamp: new Date().toISOString()
      })
    );
  }),

  // List all agents
  rest.get('/api/atom-agent/agents', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        agents: [
          {
            id: 'agent-mock-001',
            name: 'Test Agent 1',
            description: 'Mock agent for testing',
            maturity_level: 'AUTONOMOUS',
            status: 'active'
          },
          {
            id: 'agent-mock-002',
            name: 'Test Agent 2',
            description: 'Another mock agent',
            maturity_level: 'SUPERVISED',
            status: 'active'
          }
        ],
        total: 2
      })
    );
  }),

  // Get agent by ID
  rest.get('/api/atom-agent/agents/:agentId', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        id: agentId,
        name: 'Test Agent',
        description: 'Mock agent details',
        maturity_level: 'AUTONOMOUS',
        status: 'active',
        created_at: new Date().toISOString()
      })
    );
  }),

  // Stop agent execution
  rest.post('/api/atom-agent/agents/:agentId/stop', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        agent_id: agentId,
        message: 'Agent execution stopped',
        stopped_at: new Date().toISOString()
      })
    );
  }),

  // Get chat history
  rest.get('/api/atom-agent/chat/history/:sessionId', (req, res, ctx) => {
    const { sessionId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        session_id: sessionId,
        messages: [
          {
            role: 'user',
            content: 'Test message',
            timestamp: new Date().toISOString()
          },
          {
            role: 'assistant',
            content: 'Test response',
            timestamp: new Date().toISOString()
          }
        ],
        total: 2
      })
    );
  }),
];

// ============================================================================
// Canvas API Handlers
// ============================================================================

export const canvasHandlers = [
  // Submit form
  rest.post('/api/canvas/submit', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        submission_id: 'sub-mock-789',
        governance_check: {
          allowed: true,
          agent_id: 'agent-mock-001',
          action_type: 'submit_form',
          maturity_level: 'SUPERVISED'
        },
        submitted_at: new Date().toISOString()
      })
    );
  }),

  // Get canvas status
  rest.get('/api/canvas/status', (req, res, ctx) => {
    const canvas_id = req.url.searchParams.get('canvas_id') || 'canvas-default';
    return res(
      ctx.status(200),
      ctx.json({
        canvas_id,
        status: 'active',
        created_at: new Date().toISOString(),
        last_updated: new Date().toISOString()
      })
    );
  }),

  // Close canvas
  rest.post('/api/canvas/:canvasId/close', (req, res, ctx) => {
    const { canvasId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        canvas_id: canvasId,
        closed_at: new Date().toISOString()
      })
    );
  }),

  // Update canvas
  rest.put('/api/canvas/:canvasId', (req, res, ctx) => {
    const { canvasId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        canvas_id: canvasId,
        updated_at: new Date().toISOString()
      })
    );
  }),

  // Get canvas audit history
  rest.get('/api/canvas/:canvasId/audit', (req, res, ctx) => {
    const { canvasId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        canvas_id: canvasId,
        audit_log: [
          {
            id: 'audit-mock-001',
            action: 'present',
            timestamp: new Date().toISOString(),
            agent_id: 'agent-mock-001'
          },
          {
            id: 'audit-mock-002',
            action: 'submit',
            timestamp: new Date().toISOString(),
            agent_id: 'agent-mock-001'
          }
        ],
        total: 2
      })
    );
  }),

  // Execute canvas action (e.g., form button click)
  rest.post('/api/canvas/:canvasId/execute', (req, res, ctx) => {
    const { canvasId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        canvas_id: canvasId,
        execution_id: 'exec-mock-789',
        governance_check: {
          allowed: true,
          action_type: 'canvas_action',
          maturity_level: 'SUPERVISED'
        },
        executed_at: new Date().toISOString()
      })
    );
  }),
];

// ============================================================================
// Device Capabilities Handlers
// ============================================================================

export const deviceHandlers = [
  // List all devices
  rest.get('/api/devices', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        devices: [
          {
            id: 'device-mock-001',
            device_id: 'camera-001',
            name: 'Mock Camera',
            node_type: 'camera',
            status: 'online'
          },
          {
            id: 'device-mock-002',
            device_id: 'screen-001',
            name: 'Mock Screen',
            node_type: 'screen',
            status: 'online'
          }
        ],
        total: 2
      })
    );
  }),

  // Get device info
  rest.get('/api/devices/:deviceId', (req, res, ctx) => {
    const { deviceId } = req.params;
    return res(
      ctx.status(200),
      ctx.json({
        id: deviceId,
        device_id: 'test-device',
        name: 'Mock Device',
        node_type: 'camera',
        capabilities: ['snap', 'stream'],
        status: 'online'
      })
    );
  }),

  // Camera snap
  rest.post('/api/devices/camera/snap', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        image_path: '/mock/capture.jpg',
        device_node_id: 'device-mock-001',
        captured_at: new Date().toISOString()
      })
    );
  }),

  // Screen record start
  rest.post('/api/devices/screen/record/start', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        session_id: 'screen-session-mock',
        status: 'recording',
        started_at: new Date().toISOString()
      })
    );
  }),

  // Screen record stop
  rest.post('/api/devices/screen/record/stop', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        recording_path: '/mock/recording.mp4',
        duration_seconds: 10,
        stopped_at: new Date().toISOString()
      })
    );
  }),

  // Get location
  rest.post('/api/devices/location', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        latitude: 37.7749,
        longitude: -122.4194,
        accuracy: 'high',
        timestamp: new Date().toISOString()
      })
    );
  }),

  // Send notification
  rest.post('/api/devices/notification', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        notification_id: 'notif-mock-123',
        sent_at: new Date().toISOString()
      })
    );
  }),

  // Execute command (AUTONOMOUS only)
  rest.post('/api/devices/execute', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        exit_code: 0,
        stdout: 'Mock command output',
        stderr: '',
        executed_at: new Date().toISOString()
      })
    );
  }),
];

// ============================================================================
// Agent API Error Handlers (NEW - Phase 133)
// ============================================================================

/**
 * Agent API error scenario handlers for testing robustness.
 * These handlers simulate various error conditions for agent endpoints.
 *
 * Usage:
 * ```typescript
 * import { agentErrorHandlers } from '@/tests/mocks/handlers';
 * server.use(...agentErrorHandlers.internalServerError);
 * ```
 */
export const agentErrorHandlers = {
  /**
   * Internal Server Error (500) for GET /api/atom-agent/agents
   * Tests: Error boundaries, user-friendly error messages, logging
   */
  internalServerError: [
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      return res(
        ctx.status(500),
        ctx.json({
          success: false,
          error_code: 'INTERNAL_SERVER_ERROR',
          error: 'Internal server error',
          message: 'An unexpected error occurred. Please try again later.',
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Service Unavailable (503) for GET /api/atom-agent/agents
   * Tests: Retry logic, graceful degradation, maintenance mode
   */
  serviceUnavailable: [
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      return res(
        ctx.status(503),
        ctx.set('Retry-After', '60'),
        ctx.json({
          success: false,
          error_code: 'SERVICE_UNAVAILABLE',
          error: 'Service unavailable',
          message: 'The service is temporarily unavailable. Please try again later.',
          retry_after: 60,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Rate Limited (429) for GET /api/atom-agent/agents
   * Tests: Rate limit handling, backoff strategy, user notifications
   */
  rateLimited: [
    rest.get('/api/atom-agent/agents', (req, res, ctx) => {
      return res(
        ctx.status(429),
        ctx.set('Retry-After', '60'),
        ctx.json({
          success: false,
          error_code: 'RATE_LIMIT_EXCEEDED',
          error: 'Rate limit exceeded',
          message: 'Too many requests. Please wait before trying again.',
          retry_after: 60,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Not Found (404) for GET /api/atom-agent/agents/:agentId/status
   * Tests: Missing agent handling, user-friendly 404 messages
   */
  agentNotFound: [
    rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
      const { agentId } = req.params;
      return res(
        ctx.status(404),
        ctx.json({
          success: false,
          error_code: 'AGENT_NOT_FOUND',
          error: 'Agent not found',
          message: `The agent '${agentId}' does not exist or has been deleted.`,
          agent_id: agentId,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Internal Server Error (500) for GET /api/atom-agent/agents/:agentId/status
   * Tests: Agent status endpoint failure handling
   */
  agentStatusError: [
    rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
      return res(
        ctx.status(500),
        ctx.json({
          success: false,
          error_code: 'INTERNAL_SERVER_ERROR',
          error: 'Internal server error',
          message: 'Failed to retrieve agent status. Please try again later.',
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Timeout (35s delay) for POST /api/atom-agent/chat/stream
   * Tests: Timeout handling, user feedback for long-running requests
   * Note: Uses ctx.delay(35000) which exceeds the 10s API_TIMEOUT in api.ts
   */
  chatStreamTimeout: [
    rest.post('/api/atom-agent/chat/stream', async (req, res, ctx) => {
      // Delay response for 35 seconds (longer than typical 30s timeout)
      await new Promise((resolve) => setTimeout(resolve, 35000));
      return res(
        ctx.status(200),
        ctx.json({
          success: true,
          response: 'Delayed response',
        })
      );
    }),
  ],

  /**
   * Service Unavailable (503) for POST /api/atom-agent/chat/stream
   * Tests: Chat streaming service unavailability handling
   */
  chatStreamUnavailable: [
    rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
      return res(
        ctx.status(503),
        ctx.set('Retry-After', '30'),
        ctx.json({
          success: false,
          error_code: 'SERVICE_UNAVAILABLE',
          error: 'Chat service unavailable',
          message: 'The chat service is temporarily unavailable. Please try again later.',
          retry_after: 30,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],
};

// ============================================================================
// Canvas API Error Handlers (NEW - Phase 133)
// ============================================================================

/**
 * Canvas API error scenario handlers for testing robustness.
 * These handlers simulate various error conditions for canvas endpoints.
 */
export const canvasErrorHandlers = {
  /**
   * Governance Check Failed (403) for POST /api/canvas/submit
   * Tests: Maturity level gates, governance error messages, permission handling
   */
  governanceCheckFailed: [
    rest.post('/api/canvas/submit', (req, res, ctx) => {
      return res(
        ctx.status(403),
        ctx.json({
          success: false,
          error_code: 'GOVERNANCE_CHECK_FAILED',
          error: 'Forbidden - Governance check failed',
          message: 'Agent does not have permission to perform this action',
          details: {
            required_maturity: 'SUPERVISED',
            current_maturity: 'INTERN',
            action_type: 'submit_form',
            canvas_id: 'canvas-test-123',
          },
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Internal Server Error (500) for POST /api/canvas/submit
   * Tests: Form submission error handling
   */
  submitServerError: [
    rest.post('/api/canvas/submit', (req, res, ctx) => {
      return res(
        ctx.status(500),
        ctx.json({
          success: false,
          error_code: 'INTERNAL_SERVER_ERROR',
          error: 'Internal server error',
          message: 'Failed to submit form. Please try again later.',
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Service Unavailable (503) for POST /api/canvas/submit
   * Tests: Canvas service unavailability handling
   */
  submitServiceUnavailable: [
    rest.post('/api/canvas/submit', (req, res, ctx) => {
      return res(
        ctx.status(503),
        ctx.set('Retry-After', '45'),
        ctx.json({
          success: false,
          error_code: 'SERVICE_UNAVAILABLE',
          error: 'Canvas service unavailable',
          message: 'The canvas service is temporarily unavailable. Please try again later.',
          retry_after: 45,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Not Found (404) for GET /api/canvas/status
   * Tests: Missing canvas handling
   */
  canvasNotFound: [
    rest.get('/api/canvas/status', (req, res, ctx) => {
      const canvas_id = req.url.searchParams.get('canvas_id') || 'unknown';
      return res(
        ctx.status(404),
        ctx.json({
          success: false,
          error_code: 'CANVAS_NOT_FOUND',
          error: 'Canvas not found',
          message: `The canvas '${canvas_id}' does not exist or has been closed.`,
          canvas_id,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Gateway Timeout (504) for GET /api/canvas/status
   * Tests: Gateway timeout handling for canvas status
   */
  canvasStatusTimeout: [
    rest.get('/api/canvas/status', (req, res, ctx) => {
      return res(
        ctx.status(504),
        ctx.json({
          success: false,
          error_code: 'GATEWAY_TIMEOUT',
          error: 'Gateway timeout',
          message: 'The request timed out while retrieving canvas status.',
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Governance Check Failed (403) for POST /api/canvas/:canvasId/execute
   * Tests: Canvas action governance enforcement
   */
  executeGovernanceFailed: [
    rest.post('/api/canvas/:canvasId/execute', (req, res, ctx) => {
      const { canvasId } = req.params;
      return res(
        ctx.status(403),
        ctx.json({
          success: false,
          error_code: 'GOVERNANCE_CHECK_FAILED',
          error: 'Forbidden - Governance check failed',
          message: 'Agent maturity level insufficient for this action',
          details: {
            required_maturity: 'AUTONOMOUS',
            current_maturity: 'SUPERVISED',
            action_type: 'canvas_action',
            canvas_id: canvasId,
          },
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Internal Server Error (500) for POST /api/canvas/:canvasId/execute
   * Tests: Canvas action execution error handling
   */
  executeServerError: [
    rest.post('/api/canvas/:canvasId/execute', (req, res, ctx) => {
      return res(
        ctx.status(500),
        ctx.json({
          success: false,
          error_code: 'INTERNAL_SERVER_ERROR',
          error: 'Internal server error',
          message: 'Failed to execute canvas action. Please try again later.',
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],
};

// ============================================================================
// Device API Error Handlers (NEW - Phase 133)
// ============================================================================

/**
 * Device API error scenario handlers for testing robustness.
 * These handlers simulate various error conditions for device endpoints.
 */
export const deviceErrorHandlers = {
  /**
   * Service Unavailable (503) for POST /api/devices/camera/snap
   * Tests: Camera service unavailability handling
   */
  cameraUnavailable: [
    rest.post('/api/devices/camera/snap', (req, res, ctx) => {
      return res(
        ctx.status(503),
        ctx.json({
          success: false,
          error_code: 'DEVICE_UNAVAILABLE',
          error: 'Camera service unavailable',
          message: 'The camera service is temporarily unavailable. Please try again later.',
          retry_after: 30,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Timeout (35s delay) for POST /api/devices/camera/snap
   * Tests: Camera capture timeout handling
   */
  cameraTimeout: [
    rest.post('/api/devices/camera/snap', async (req, res, ctx) => {
      // Delay response for 35 seconds (longer than typical timeout)
      await new Promise((resolve) => setTimeout(resolve, 35000));
      return res(
        ctx.status(200),
        ctx.json({
          success: true,
          image_path: '/mock/capture.jpg',
        })
      );
    }),
  ],

  /**
   * Governance Check Failed (403) for POST /api/devices/screen/record/start
   * Tests: Screen recording maturity level gates
   */
  screenRecordingGovernanceFailed: [
    rest.post('/api/devices/screen/record/start', (req, res, ctx) => {
      return res(
        ctx.status(403),
        ctx.json({
          success: false,
          error_code: 'GOVERNANCE_CHECK_FAILED',
          error: 'Forbidden - Governance check failed',
          message: 'Agent maturity level insufficient for screen recording',
          details: {
            required_maturity: 'SUPERVISED',
            current_maturity: 'INTERN',
            action_type: 'screen_record_start',
          },
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Internal Server Error (500) for POST /api/devices/screen/record/start
   * Tests: Screen recording error handling
   */
  screenRecordingError: [
    rest.post('/api/devices/screen/record/start', (req, res, ctx) => {
      return res(
        ctx.status(500),
        ctx.json({
          success: false,
          error_code: 'INTERNAL_SERVER_ERROR',
          error: 'Internal server error',
          message: 'Failed to start screen recording. Please try again later.',
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Service Unavailable (503) for POST /api/devices/location
   * Tests: Location service unavailability handling
   */
  locationUnavailable: [
    rest.post('/api/devices/location', (req, res, ctx) => {
      return res(
        ctx.status(503),
        ctx.json({
          success: false,
          error_code: 'SERVICE_UNAVAILABLE',
          error: 'Location service unavailable',
          message: 'The location service is temporarily unavailable.',
          retry_after: 20,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Network Error for POST /api/devices/location
   * Tests: Location API network failure handling
   * Note: In Node.js/jsdom, network errors are simulated with 503 responses
   */
  locationNetworkError: [
    rest.post('/api/devices/location', (req, res, ctx) => {
      // Simulate network error with 503 Service Unavailable
      // Real network errors don't work in Node.js/jsdom environment
      return res(
        ctx.status(503),
        ctx.json({
          success: false,
          error_code: 'NETWORK_ERROR',
          error: 'Network error',
          message: 'Failed to reach location service. Please check your connection.',
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],
};

// ============================================================================
// Integration API Error Handlers (NEW - Phase 133)
// ============================================================================

/**
 * Integration API error scenario handlers for testing OAuth and API integration robustness.
 * These handlers simulate various error conditions for third-party service integrations.
 */
export const integrationErrorHandlers = {
  /**
   * OAuth Access Denied for all integration callbacks
   * Tests: OAuth denial handling, user feedback for cancelled authorization
   */
  oauthAccessDenied: [
    // Jira
    rest.get('/api/integrations/jira/callback', (req, res, ctx) => {
      return res(
        ctx.status(401),
        ctx.json({
          error: 'access_denied',
          error_description: 'User denied authorization',
          state: req.url.searchParams.get('state'),
        })
      );
    }),
    // Slack
    rest.get('/api/integrations/slack/callback', (req, res, ctx) => {
      return res(
        ctx.status(401),
        ctx.json({
          error: 'access_denied',
          error_description: 'User denied authorization',
        })
      );
    }),
    // Microsoft 365
    rest.get('/api/integrations/microsoft365/callback', (req, res, ctx) => {
      return res(
        ctx.status(401),
        ctx.json({
          error: 'access_denied',
          error_description: 'User denied authorization',
        })
      );
    }),
    // Generic for all other integrations
    rest.get('/api/integrations/*/callback', (req, res, ctx) => {
      return res(
        ctx.status(401),
        ctx.json({
          error: 'access_denied',
          error_description: 'User denied authorization',
        })
      );
    }),
  ],

  /**
   * OAuth Timeout for integration connection endpoints
   * Tests: OAuth flow timeout handling
   */
  oauthTimeout: [
    rest.post('/api/integrations/*/connect', async (req, res, ctx) => {
      // Delay response for 35 seconds to trigger timeout
      await new Promise((resolve) => setTimeout(resolve, 35000));
      return res(
        ctx.status(200),
        ctx.json({ authUrl: 'https://example.com/oauth/authorize' })
      );
    }),
  ],

  /**
   * Rate Limited (429) for integration API endpoints
   * Tests: Third-party API rate limit handling
   */
  apiRateLimited: [
    rest.get('/api/integrations/jira/issues', (req, res, ctx) => {
      return res(
        ctx.status(429),
        ctx.set('Retry-After', '3600'), // 1 hour
        ctx.json({
          success: false,
          error_code: 'RATE_LIMIT_EXCEEDED',
          error: 'Jira API rate limit exceeded',
          message: 'Too many requests to Jira API. Please wait before trying again.',
          retry_after: 3600,
          timestamp: new Date().toISOString(),
        })
      );
    }),
    rest.get('/api/integrations/slack/channels', (req, res, ctx) => {
      return res(
        ctx.status(429),
        ctx.set('Retry-After', '60'), // 1 minute
        ctx.json({
          success: false,
          error_code: 'RATE_LIMIT_EXCEEDED',
          error: 'Slack API rate limit exceeded',
          message: 'Too many requests to Slack API. Please wait before trying again.',
          retry_after: 60,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],

  /**
   * Service Unavailable (503) for integration APIs
   * Tests: Third-party service unavailability handling
   */
  serviceUnavailable: [
    rest.get('/api/integrations/jira/projects', (req, res, ctx) => {
      return res(
        ctx.status(503),
        ctx.json({
          success: false,
          error_code: 'SERVICE_UNAVAILABLE',
          error: 'Jira service unavailable',
          message: 'Jira API is temporarily unavailable. Please try again later.',
          retry_after: 300,
          timestamp: new Date().toISOString(),
        })
      );
    }),
    rest.get('/api/integrations/slack/channels', (req, res, ctx) => {
      return res(
        ctx.status(503),
        ctx.json({
          success: false,
          error_code: 'SERVICE_UNAVAILABLE',
          error: 'Slack service unavailable',
          message: 'Slack API is temporarily unavailable. Please try again later.',
          retry_after: 60,
          timestamp: new Date().toISOString(),
        })
      );
    }),
  ],
};

// ============================================================================
// Form Submission Handlers (NEW - Phase 109)
// ============================================================================

/**
 * Form submission handlers for MSW backend integration tests.
 * These handlers mock form submission endpoints with various scenarios:
 * - Success responses with submission IDs
 * - Server validation errors (400 with field_errors)
 * - Server errors (500, 503)
 * - Timeout scenarios (10s delay)
 * - Network failures (connection refused)
 */
export const formSubmissionHandlers = [
  // Submit form data successfully (default)
  rest.post('/api/forms/submit', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        submission_id: `sub-${Date.now()}`,
        message: 'Form submitted successfully',
        submitted_at: new Date().toISOString()
      })
    );
  }),

  // Form submission endpoint for validation error scenarios
  rest.post('/api/forms/error', (req, res, ctx) => {
    const body = req.body as any;

    // Simulate server validation error for specific field value
    if (body.email === 'invalid@example.com') {
      return res(
        ctx.status(400),
        ctx.json({
          success: false,
          error: 'Validation failed',
          field_errors: {
            email: 'This email is already registered'
          }
        })
      );
    }

    // Simulate multiple field errors
    if (body.email === 'multiple@example.com') {
      return res(
        ctx.status(400),
        ctx.json({
          success: false,
          error: 'Validation failed',
          field_errors: {
            email: 'Email format invalid',
            name: 'Name is required',
            age: 'Must be at least 18'
          }
        })
      );
    }

    // Default success for other cases
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        submission_id: 'sub-error-default',
        message: 'Form submitted successfully'
      })
    );
  }),

  // Form submission with server error (500)
  rest.post('/api/forms/server-error', (req, res, ctx) => {
    return res(
      ctx.status(500),
      ctx.json({
        success: false,
        error: 'Internal server error',
        timestamp: new Date().toISOString()
      })
    );
  }),

  // Form submission with service unavailable (503)
  rest.post('/api/forms/service-unavailable', (req, res, ctx) => {
    return res(
      ctx.status(503),
      ctx.json({
        success: false,
        error: 'Service temporarily unavailable',
        retry_after: 60
      })
    );
  }),

  // Form submission with unauthorized error (401)
  rest.post('/api/forms/unauthorized', (req, res, ctx) => {
    return res(
      ctx.status(401),
      ctx.json({
        success: false,
        error: 'Authentication required',
        code: 'UNAUTHORIZED'
      })
    );
  }),

  // Form submission with not found error (404)
  rest.post('/api/forms/not-found', (req, res, ctx) => {
    return res(
      ctx.status(404),
      ctx.json({
        success: false,
        error: 'Form endpoint not found',
        code: 'NOT_FOUND'
      })
    );
  }),

  // Form submission timeout simulation (10 second delay)
  rest.post('/api/forms/timeout', (req, res, ctx) => {
    return res(
      ctx.delay(10000),  // 10 second delay to trigger timeout
      ctx.status(200),
      ctx.json({
        success: true,
        submission_id: 'sub-timeout',
        message: 'Form submitted successfully (after delay)'
      })
    );
  }),

  // Form submission with slow network (2 second delay)
  rest.post('/api/forms/slow', (req, res, ctx) => {
    return res(
      ctx.delay(2000),  // 2 second delay to test loading state
      ctx.status(200),
      ctx.json({
        success: true,
        submission_id: 'sub-slow',
        message: 'Form submitted successfully'
      })
    );
  }),

  // Form submission with network error simulation
  rest.post('/api/forms/network-error', (req, res) => {
    // Simulate network failure by not responding properly
    // This will trigger a network error in the client
    return res.networkError('Network connection failed');
  }),

  // Form submission with connection refused simulation
  rest.post('/api/forms/connection-refused', (req, res) => {
    // Simulate connection refused (server not reachable)
    return res.networkError('Connection refused');
  }),
];

// ============================================================================
// Integration API Handlers (NEW - Phase 130)
// ============================================================================

/**
 * Integration component API handlers for third-party service mocking.
 * These handlers mock OAuth flows and API integration endpoints for:
 * - Jira, Slack, Microsoft 365, GitHub, Asana, Notion, Outlook, Zoom
 * - Google Workspace, QuickBooks, Box, Trello, Zendesk
 *
 * Usage:
 * ```typescript
 * import { integrationHandlers } from '@/tests/mocks/handlers';
 * server.use(...integrationHandlers);
 * ```
 */

// Jira Integration Handlers
export const jiraHandlers = [
  // OAuth connection initiation
  rest.post('/api/integrations/jira/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        authUrl: 'https://auth.atlassian.com/authorize',
        state: expect.any(String),
      })
    );
  }),

  // OAuth callback handling
  rest.get('/api/integrations/jira/callback', (req, res, ctx) => {
    const { code, error } = Object.fromEntries(req.url.searchParams);

    if (error === 'access_denied') {
      return res(
        ctx.status(401),
        ctx.json({
          error: 'access_denied',
          error_description: 'User denied authorization',
        })
      );
    }

    if (!code) {
      return res(
        ctx.status(400),
        ctx.json({ error: 'Missing authorization code' })
      );
    }

    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        status: 'connected',
        workspace: 'Test Workspace',
      })
    );
  }),

  // Fetch Jira projects
  rest.get('/api/integrations/jira/projects', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        projects: [
          {
            id: '10000',
            key: 'TEST',
            name: 'Test Project',
            projectTypeKey: 'software',
            lead: {
              displayName: 'John Doe',
              emailAddress: 'john@example.com',
              avatarUrls: {
                '48x48': 'https://example.com/avatar48.jpg',
              },
            },
            url: 'https://test.atlassian.net/browse/TEST',
            description: 'A test project',
            isPrivate: false,
            archived: false,
          },
        ],
      })
    );
  }),

  // Fetch Jira issues
  rest.get('/api/integrations/jira/issues', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        issues: [
          {
            id: '10001',
            key: 'TEST-1',
            fields: {
              summary: 'Test issue summary',
              status: { name: 'To Do' },
              priority: { name: 'Medium' },
              assignee: { displayName: 'John Doe' },
            },
          },
        ],
      })
    );
  }),

  // Create Jira issue
  rest.post('/api/integrations/jira/issues', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        issue: {
          id: '10002',
          key: 'TEST-2',
          fields: { summary: 'New test issue' },
        },
      })
    );
  }),

  // Fetch Jira users
  rest.get('/api/integrations/jira/users', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        users: [
          {
            accountId: '12345',
            displayName: 'John Doe',
            emailAddress: 'john@example.com',
            active: true,
          },
        ],
      })
    );
  }),

  // Fetch Jira sprints
  rest.get('/api/integrations/jira/sprints', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        sprints: [
          {
            id: 1,
            state: 'active',
            name: 'Sprint 1',
            startDate: '2024-01-15T10:00:00.000Z',
            endDate: '2024-01-29T10:00:00.000Z',
            originBoardId: 1,
          },
        ],
      })
    );
  }),

  // Update issue assignee
  rest.put('/api/integrations/jira/issues/:issueId/assignee', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true })
    );
  }),

  // Disconnect Jira
  rest.post('/api/integrations/jira/disconnect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true })
    );
  }),

  // Health check
  rest.get('/api/integrations/jira/health', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        status: 'healthy',
        timestamp: new Date().toISOString(),
      })
    );
  }),
];

// Slack Integration Handlers
export const slackHandlers = [
  // OAuth connection
  rest.post('/api/integrations/slack/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        authUrl: 'https://slack.com/oauth/v2/authorize',
        state: expect.any(String),
      })
    );
  }),

  // OAuth callback
  rest.get('/api/integrations/slack/callback', (req, res, ctx) => {
    const { error } = Object.fromEntries(req.url.searchParams);

    if (error === 'access_denied') {
      return res(
        ctx.status(401),
        ctx.json({ error: 'access_denied' })
      );
    }

    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        team: {
          id: 'T1234567890',
          name: 'Test Workspace',
          domain: 'test-workspace',
        },
      })
    );
  }),

  // Fetch channels
  rest.get('/api/integrations/slack/channels', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        channels: [
          {
            id: 'C1234567890',
            name: 'general',
            is_channel: true,
            is_archived: false,
            members: 150,
            topic: { value: 'Company-wide announcements' },
          },
          {
            id: 'C0987654321',
            name: 'engineering',
            is_channel: true,
            is_archived: false,
            members: 45,
          },
        ],
      })
    );
  }),

  // Fetch messages
  rest.get('/api/integrations/slack/messages/:channelId', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        messages: [
          {
            type: 'message',
            text: 'Test message from bot',
            ts: '1234567890.123456',
          },
        ],
      })
    );
  }),

  // Send message
  rest.post('/api/integrations/slack/messages', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        message: {
          type: 'message',
          text: req.body?.text || 'New test message',
          ts: '1234567892.123456',
        },
      })
    );
  }),

  // Fetch users
  rest.get('/api/integrations/slack/users', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        members: [
          {
            id: 'U1234567890',
            name: 'john.doe',
            deleted: false,
            real_name: 'John Doe',
            profile: {
              email: 'john@example.com',
              display_name: 'John Doe',
              status_text: 'Working on Atom',
              status_emoji: ':rocket:',
            },
          },
        ],
      })
    );
  }),

  // Create webhook
  rest.post('/api/integrations/slack/webhooks', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        webhook: {
          id: 'WH123456',
          url: 'https://hooks.slack.com/services/T123/B123/XXX',
          channel: 'general',
        },
      })
    );
  }),

  // Disconnect
  rest.post('/api/integrations/slack/disconnect', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

// Microsoft 365 Integration Handlers
export const microsoft365Handlers = [
  // OAuth connection
  rest.post('/api/integrations/microsoft365/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        authUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        state: expect.any(String),
      })
    );
  }),

  // OAuth callback
  rest.get('/api/integrations/microsoft365/callback', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        user: {
          displayName: 'John Doe',
          email: 'john@example.com',
        },
      })
    );
  }),

  // Fetch OneDrive files
  rest.get('/api/integrations/microsoft365/onedrive/files', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        files: [
          {
            id: '01VAN3K3DZKBUM5VWEWPCQWYFQKW7QF5RA',
            name: 'Document.docx',
            size: 12345,
            createdDateTime: '2024-01-15T10:00:00Z',
          },
        ],
      })
    );
  }),

  // Upload to OneDrive
  rest.post('/api/integrations/microsoft365/onedrive/upload', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        file: {
          id: 'new-file-id',
          name: 'uploaded-file.txt',
        },
      })
    );
  }),

  // Fetch Outlook emails
  rest.get('/api/integrations/microsoft365/outlook/emails', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        emails: [
          {
            id: 'AAMkAGViNDUxoczRAAA=',
            subject: 'Test Email',
            from: {
              emailAddress: {
                name: 'John Doe',
                address: 'john@example.com',
              },
            },
            receivedDateTime: '2024-01-15T10:00:00Z',
          },
        ],
      })
    );
  }),

  // Send Outlook email
  rest.post('/api/integrations/microsoft365/outlook/send', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        message: {
          id: 'new-email-id',
          subject: req.body?.subject || 'Test Subject',
        },
      })
    );
  }),

  // Disconnect
  rest.post('/api/integrations/microsoft365/disconnect', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

// Generic integration handlers for remaining services
export const genericIntegrationHandlers = [
  // GitHub
  rest.post('/api/integrations/github/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://github.com/login/oauth/authorize' })
    );
  }),
  rest.get('/api/integrations/github/repos', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        repos: [{ id: 1, name: 'test-repo', full_name: 'user/test-repo' }],
      })
    );
  }),

  // Asana
  rest.post('/api/integrations/asana/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://app.asana.com/oauth/authorize' })
    );
  }),
  rest.get('/api/integrations/asana/tasks', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, tasks: [{ id: '1', name: 'Test task' }] })
    );
  }),

  // Notion
  rest.post('/api/integrations/notion/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://api.notion.com/oauth/authorize' })
    );
  }),
  rest.get('/api/integrations/notion/pages', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, pages: [{ id: '1', title: 'Test page' }] })
    );
  }),

  // Outlook (standalone)
  rest.post('/api/integrations/outlook/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        authUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
      })
    );
  }),
  rest.get('/api/integrations/outlook/emails', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, emails: [{ id: '1', subject: 'Test email' }] })
    );
  }),

  // Zoom
  rest.post('/api/integrations/zoom/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://zoom.us/oauth/authorize' })
    );
  }),
  rest.get('/api/integrations/zoom/meetings', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, meetings: [{ id: '1', topic: 'Test meeting' }] })
    );
  }),

  // Google Workspace
  rest.post('/api/integrations/google/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://accounts.google.com/o/oauth2/v2/auth' })
    );
  }),
  rest.get('/api/integrations/google/drive/files', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, files: [{ id: '1', name: 'test-file.pdf' }] })
    );
  }),

  // QuickBooks
  rest.post('/api/integrations/quickbooks/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://appcenter.intuit.com/connect/oauth2' })
    );
  }),
  rest.get('/api/integrations/quickbooks/invoices', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        invoices: [{ id: '1', total: 100.0, customerName: 'Test Customer' }],
      })
    );
  }),

  // Box
  rest.post('/api/integrations/box/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://account.box.com/api/oauth2/authorize' })
    );
  }),
  rest.get('/api/integrations/box/files', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, files: [{ id: '1', name: 'test-file.pdf' }] })
    );
  }),

  // Trello
  rest.post('/api/integrations/trello/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://trello.com/1/authorize' })
    );
  }),
  rest.get('/api/integrations/trello/boards', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, boards: [{ id: '1', name: 'Test Board' }] })
    );
  }),

  // Zendesk
  rest.post('/api/integrations/zendesk/connect', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ authUrl: 'https://zendesk.com/oauth/authorize' })
    );
  }),
  rest.get('/api/integrations/zendesk/tickets', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ success: true, tickets: [{ id: '1', subject: 'Test ticket', status: 'open' }] })
    );
  }),
];

// Export all integration handlers
export const integrationHandlers = [
  ...jiraHandlers,
  ...slackHandlers,
  ...microsoft365Handlers,
  ...genericIntegrationHandlers,
];

// ============================================================================
// All Handlers Combined
// ============================================================================

/**
 * All default handlers for successful API responses.
 * Error handlers are exported separately and should be used as needed.
 */
export const allHandlers = [
  ...commonHandlers,
  ...agentHandlers,
  ...canvasHandlers,
  ...deviceHandlers,
  ...formSubmissionHandlers,  // Phase 109
  ...integrationHandlers,     // Phase 130
];

/**
 * All error scenario handlers for testing robustness.
 * These are not included in allHandlers by default.
 * Import and use specific error scenarios as needed in tests.
 *
 * Example:
 * ```typescript
 * import { agentErrorHandlers } from '@/tests/mocks/handlers';
 * server.use(...agentErrorHandlers.serviceUnavailable);
 * ```
 */
export const allErrorHandlers = {
  agent: agentErrorHandlers,
  canvas: canvasErrorHandlers,
  device: deviceErrorHandlers,
  integration: integrationErrorHandlers,
};
