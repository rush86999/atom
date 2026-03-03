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
 *
 * Usage:
 * ```typescript
 * import { allHandlers, agentHandlers, overrideHandler } from '@/tests/mocks/handlers';
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
 * ```
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
// All Handlers Combined
// ============================================================================

export const allHandlers = [
  ...commonHandlers,
  ...agentHandlers,
  ...canvasHandlers,
  ...deviceHandlers,
  ...formSubmissionHandlers,  // NEW - Phase 109
];
