/**
 * Loading State MSW Handlers
 *
 * Mock Service Worker handlers for simulating slow endpoints and loading states.
 * These handlers use ctx.delay() to simulate network latency, enabling realistic
 * loading state testing without artificial setTimeouts.
 *
 * Features:
 * - Slow endpoint handlers with configurable delays (1s, 1.5s, 2s, 2.5s, 3s)
 * - Factory functions for creating delayed endpoints
 * - Progressive loading simulation (useful for skeleton → data transitions)
 * - Timestamps for latency validation in tests
 *
 * Usage:
 * ```typescript
 * import { slowHandlers, agentSlowHandlers } from '@/tests/mocks/scenarios/loading-states';
 * import { server } from '@/tests/mocks/server';
 *
 * // Use all slow handlers
 * server.use(...slowHandlers);
 *
 * // Use specific API handlers
 * server.use(...agentSlowHandlers);
 *
 * // Create custom slow endpoint
 * import { createSlowEndpoint } from '@/tests/mocks/scenarios/loading-states';
 * server.use(createSlowEndpoint('GET', '/api/custom', 2000));
 * ```
 */

import { rest, RestContext, RestRequest } from 'msw';

// ============================================================================
// Type Definitions
// ============================================================================

interface SlowEndpointConfig {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  delayMs: number;
  response?: any;
  status?: number;
}

interface ProgressiveLoadingConfig {
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  path: string;
  delays: number[];
  response?: any;
  status?: number;
}

// ============================================================================
// Factory Functions
// ============================================================================

/**
 * Create a slow endpoint handler with configurable delay.
 *
 * @param method - HTTP method (GET, POST, PUT, DELETE, PATCH)
 * @param path - API endpoint path (supports MSW path patterns like :param)
 * @param delayMs - Delay in milliseconds before responding
 * @param response - Response data (default: { success: true, timestamp: string })
 * @param status - HTTP status code (default: 200)
 *
 * @returns MSW RestHandler for the slow endpoint
 *
 * @example
 * ```typescript
 * const slowAgentEndpoint = createSlowEndpoint('GET', '/api/atom-agent/agents', 2000);
 * server.use(slowAgentEndpoint);
 * ```
 */
export function createSlowEndpoint(
  method: SlowEndpointConfig['method'],
  path: string,
  delayMs: number,
  response: any = { success: true, timestamp: new Date().toISOString() },
  status: number = 200
) {
  const handlerMap = {
    GET: rest.get,
    POST: rest.post,
    PUT: rest.put,
    DELETE: rest.delete,
    PATCH: rest.patch,
  };

  return handlerMap[method](path, (req: RestRequest, res: any, ctx: RestContext) => {
    return res(
      ctx.delay(delayMs),
      ctx.status(status),
      ctx.json({
        ...response,
        _loadingTestMetadata: {
          delayMs,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  });
}

/**
 * Create a progressive loading endpoint that returns progressively faster responses.
 * Useful for testing skeleton → data transitions and optimistic updates.
 *
 * @param method - HTTP method
 * @param path - API endpoint path
 * @param delays - Array of delays for subsequent requests (e.g., [2000, 1000, 500])
 * @param response - Response data
 * @param status - HTTP status code
 *
 * @returns MSW RestHandler with progressive delay tracking
 *
 * @example
 * ```typescript
 * const progressiveEndpoint = createProgressiveLoadingEndpoint(
 *   'GET',
 *   '/api/atom-agent/agents',
 *   [2000, 1000, 500] // First request: 2s, second: 1s, third: 500ms
 * );
 * server.use(progressiveEndpoint);
 * ```
 */
export function createProgressiveLoadingEndpoint(
  method: ProgressiveLoadingConfig['method'],
  path: string,
  delays: number[],
  response: any = { success: true, timestamp: new Date().toISOString() },
  status: number = 200
) {
  let requestCount = 0;

  const handlerMap = {
    GET: rest.get,
    POST: rest.post,
    PUT: rest.put,
    DELETE: rest.delete,
    PATCH: rest.patch,
  };

  return handlerMap[method](path, (req: RestRequest, res: any, ctx: RestContext) => {
    const currentDelay = delays[Math.min(requestCount, delays.length - 1)];
    requestCount++;

    return res(
      ctx.delay(currentDelay),
      ctx.status(status),
      ctx.json({
        ...response,
        _progressiveLoadingMetadata: {
          requestNumber: requestCount,
          delayMs: currentDelay,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  });
}

// ============================================================================
// Slow Agent API Handlers
// ============================================================================

/**
 * Agent API handlers with simulated delays for testing loading states.
 */
export const agentSlowHandlers = [
  // GET /api/atom-agent/agents with 2s delay
  rest.get('/api/atom-agent/agents', (req, res, ctx) => {
    return res(
      ctx.delay(2000),
      ctx.json({
        agents: [
          {
            id: 'agent-mock-001',
            name: 'Test Agent 1',
            description: 'Mock agent for loading state testing',
            maturity_level: 'AUTONOMOUS',
            status: 'active',
          },
          {
            id: 'agent-mock-002',
            name: 'Test Agent 2',
            description: 'Another slow-loading agent',
            maturity_level: 'SUPERVISED',
            status: 'active',
          },
        ],
        total: 2,
        _loadingTestMetadata: {
          delayMs: 2000,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // GET /api/atom-agent/agents/:agentId/status with 1.5s delay
  rest.get('/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.delay(1500),
      ctx.json({
        agent_id: agentId,
        status: 'idle',
        maturity_level: 'AUTONOMOUS',
        confidence: 0.95,
        last_execution: null,
        created_at: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 1500,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // POST /api/atom-agent/chat/stream with 3s delay (slowest endpoint)
  rest.post('/api/atom-agent/chat/stream', (req, res, ctx) => {
    return res(
      ctx.delay(3000),
      ctx.json({
        success: true,
        response: 'Mock agent response after slow loading',
        execution_id: 'exec-mock-slow-123',
        agent_id: 'agent-mock-456',
        timestamp: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 3000,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // GET /api/atom-agent/agents/:agentId with 1.8s delay
  rest.get('/api/atom-agent/agents/:agentId', (req, res, ctx) => {
    const { agentId } = req.params;
    return res(
      ctx.delay(1800),
      ctx.json({
        id: agentId,
        name: 'Test Agent',
        description: 'Mock agent details with slow loading',
        maturity_level: 'AUTONOMOUS',
        status: 'active',
        created_at: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 1800,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),
];

// ============================================================================
// Slow Canvas API Handlers
// ============================================================================

/**
 * Canvas API handlers with simulated delays for testing loading states.
 */
export const canvasSlowHandlers = [
  // POST /api/canvas/submit with 2.5s delay (slow form submission)
  rest.post('/api/canvas/submit', (req, res, ctx) => {
    return res(
      ctx.delay(2500),
      ctx.json({
        success: true,
        submission_id: 'sub-mock-slow-789',
        governance_check: {
          allowed: true,
          agent_id: 'agent-mock-001',
          action_type: 'submit_form',
          maturity_level: 'SUPERVISED',
        },
        submitted_at: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 2500,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // GET /api/canvas/status with 1s delay
  rest.get('/api/canvas/status', (req, res, ctx) => {
    const canvas_id = req.url.searchParams.get('canvas_id') || 'canvas-default';
    return res(
      ctx.delay(1000),
      ctx.json({
        canvas_id,
        status: 'active',
        created_at: new Date().toISOString(),
        last_updated: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 1000,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // POST /api/canvas/:canvasId/execute with 2s delay
  rest.post('/api/canvas/:canvasId/execute', (req, res, ctx) => {
    const { canvasId } = req.params;
    return res(
      ctx.delay(2000),
      ctx.json({
        success: true,
        canvas_id: canvasId,
        execution_id: 'exec-mock-slow-789',
        governance_check: {
          allowed: true,
          action_type: 'canvas_action',
          maturity_level: 'SUPERVISED',
        },
        executed_at: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 2000,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // GET /api/canvas/:canvasId/audit with 1.2s delay
  rest.get('/api/canvas/:canvasId/audit', (req, res, ctx) => {
    const { canvasId } = req.params;
    return res(
      ctx.delay(1200),
      ctx.json({
        canvas_id: canvasId,
        audit_log: [
          {
            id: 'audit-mock-slow-001',
            action: 'present',
            timestamp: new Date().toISOString(),
            agent_id: 'agent-mock-001',
          },
          {
            id: 'audit-mock-slow-002',
            action: 'submit',
            timestamp: new Date().toISOString(),
            agent_id: 'agent-mock-001',
          },
        ],
        total: 2,
        _loadingTestMetadata: {
          delayMs: 1200,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),
];

// ============================================================================
// Slow Device API Handlers
// ============================================================================

/**
 * Device API handlers with simulated delays for testing loading states.
 */
export const deviceSlowHandlers = [
  // GET /api/devices with 1.5s delay
  rest.get('/api/devices', (req, res, ctx) => {
    return res(
      ctx.delay(1500),
      ctx.json({
        devices: [
          {
            id: 'device-mock-001',
            device_id: 'camera-001',
            name: 'Mock Camera (slow)',
            node_type: 'camera',
            status: 'online',
          },
          {
            id: 'device-mock-002',
            device_id: 'screen-001',
            name: 'Mock Screen (slow)',
            node_type: 'screen',
            status: 'online',
          },
        ],
        total: 2,
        _loadingTestMetadata: {
          delayMs: 1500,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // POST /api/devices/camera/snap with 2s delay
  rest.post('/api/devices/camera/snap', (req, res, ctx) => {
    return res(
      ctx.delay(2000),
      ctx.json({
        success: true,
        image_path: '/mock/capture-slow.jpg',
        device_node_id: 'device-mock-001',
        captured_at: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 2000,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // POST /api/devices/screen/record/start with 1.8s delay
  rest.post('/api/devices/screen/record/start', (req, res, ctx) => {
    return res(
      ctx.delay(1800),
      ctx.json({
        success: true,
        session_id: 'screen-session-slow',
        status: 'recording',
        started_at: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 1800,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),

  // POST /api/devices/notification with 1.2s delay
  rest.post('/api/devices/notification', (req, res, ctx) => {
    return res(
      ctx.delay(1200),
      ctx.json({
        success: true,
        notification_id: 'notif-mock-slow-123',
        sent_at: new Date().toISOString(),
        _loadingTestMetadata: {
          delayMs: 1200,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  }),
];

// ============================================================================
// All Slow Handlers Combined
// ============================================================================

/**
 * All slow endpoint handlers combined.
 * Use this to enable loading state testing across all APIs.
 */
export const slowHandlers = [
  ...agentSlowHandlers,
  ...canvasSlowHandlers,
  ...deviceSlowHandlers,
];

// ============================================================================
// Progressive Loading Handlers (Bonus)
// ============================================================================

/**
 * Progressive loading handlers that simulate faster responses on subsequent requests.
 * Useful for testing skeleton → data transitions and optimistic updates.
 */
export const progressiveLoadingHandlers = [
  // Progressive agent list loading
  createProgressiveLoadingEndpoint(
    'GET',
    '/api/atom-agent/agents/progressive',
    [2000, 1000, 500], // First: 2s, then 1s, then 500ms
    {
      agents: [
        {
          id: 'agent-progressive-001',
          name: 'Progressive Agent 1',
          maturity_level: 'AUTONOMOUS',
          status: 'active',
        },
      ],
      total: 1,
    }
  ),

  // Progressive canvas status loading
  createProgressiveLoadingEndpoint(
    'GET',
    '/api/canvas/status/progressive',
    [1500, 800, 400], // First: 1.5s, then 800ms, then 400ms
    {
      canvas_id: 'canvas-progressive',
      status: 'active',
      created_at: new Date().toISOString(),
    }
  ),
];
