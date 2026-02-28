/**
 * Error Scenario Handlers
 *
 * Pre-configured MSW handlers for common error scenarios in API tests.
 * These handlers can be used to test error handling, retry logic, and
 * user-facing error messages.
 *
 * Usage:
 * ```typescript
 * import { errorHandlers } from '@/tests/mocks/errors';
 * import { overrideHandlers } from '@/tests/mocks/server';
 *
 * test('handles network errors', async () => {
 *   overrideHandlers(errorHandlers.networkError);
 *   // Test error handling
 * });
 * ```
 */

import { rest } from 'msw';

// ============================================================================
// Network Error Handlers
// ============================================================================

export const errorHandlers = {
  /**
   * Network failure handler
   *
   * Simulates a complete network failure (no response from server).
   * Use this to test offline behavior and network error recovery.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.networkError);
   * ```
   */
  networkError: [
    rest.get('/api/*', () => {
      // Simulate network failure
      throw new Error('Network request failed');
    }),
    rest.post('/api/*', () => {
      throw new Error('Network request failed');
    }),
    rest.put('/api/*', () => {
      throw new Error('Network request failed');
    }),
    rest.delete('/api/*', () => {
      throw new Error('Network request failed');
    }),
  ],

  /**
   * Unauthorized handler (401)
   *
   * Simulates authentication failure. Use this to test login redirects,
   * token refresh logic, and authentication error messages.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.unauthorized);
   * ```
   */
  unauthorized: [
    rest.get('/api/*', (req, res, ctx) => {
      return res(
        ctx.status(401),
        ctx.json({
          success: false,
          error_code: 'UNAUTHORIZED',
          error: 'Unauthorized - Authentication required',
          message: 'Please log in to continue',
        })
      );
    }),
  ],

  /**
   * Forbidden handler (403)
   *
   * Simulates authorization/governance failure. Use this to test permission
   * checks, maturity level gates, and governance error messages.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.forbidden);
   * ```
   */
  forbidden: [
    rest.get('/api/*', (req, res, ctx) => {
      return res(
        ctx.status(403),
        ctx.json({
          success: false,
          error_code: 'FORBIDDEN',
          error: 'Forbidden - Governance check failed',
          message: 'Agent does not have permission to perform this action',
          details: {
            required_maturity: 'AUTONOMOUS',
            current_maturity: 'INTERN',
          },
        })
      );
    }),
  ],

  /**
   * Not found handler (404)
   *
   * Simulates resource not found errors. Use this to test error handling
   * for missing agents, canvases, devices, etc.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.notFound);
   * ```
   */
  notFound: [
    rest.get('/api/*', (req, res, ctx) => {
      return res(
        ctx.status(404),
        ctx.json({
          success: false,
          error_code: 'NOT_FOUND',
          error: 'Resource not found',
          message: 'The requested resource does not exist',
        })
      );
    }),
  ],

  /**
   * Server error handler (500)
   *
   * Simulates internal server errors. Use this to test error boundary behavior,
   * error logging, and user-facing error messages.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.serverError);
   * ```
   */
  serverError: [
    rest.get('/api/*', (req, res, ctx) => {
      return res(
        ctx.status(500),
        ctx.json({
          success: false,
          error_code: 'INTERNAL_SERVER_ERROR',
          error: 'Internal server error',
          message: 'An unexpected error occurred. Please try again later.',
        })
      );
    }),
  ],

  /**
   * Service unavailable handler (503)
   *
   * Simulates service unavailability (maintenance, overload). Use this to test
   * retry logic, graceful degradation, and maintenance mode behavior.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.serviceUnavailable);
   * ```
   */
  serviceUnavailable: [
    rest.get('/api/*', (req, res, ctx) => {
      return res(
        ctx.status(503),
        ctx.json({
          success: false,
          error_code: 'SERVICE_UNAVAILABLE',
          error: 'Service unavailable',
          message: 'The service is temporarily unavailable. Please try again later.',
          retry_after: 60, // seconds
        })
      );
    }),
  ],

  /**
   * Rate limited handler (429)
   *
   * Simulates rate limiting. Use this to test rate limit handling, backoff
   * strategies, and user notifications for rate limits.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.rateLimited);
   * ```
   */
  rateLimited: [
    rest.get('/api/*', (req, res, ctx) => {
      return res(
        ctx.status(429),
        ctx.set('Retry-After', '60'),
        ctx.json({
          success: false,
          error_code: 'RATE_LIMIT_EXCEEDED',
          error: 'Rate limit exceeded',
          message: 'Too many requests. Please wait before trying again.',
          retry_after: 60, // seconds
        })
      );
    }),
  ],

  /**
   * Timeout handler
   *
   * Simulates request timeout. Use this to test timeout handling and
   * user feedback for slow/failed requests.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.timeout);
   * ```
   */
  timeout: [
    rest.get('/api/*', async (req, res, ctx) => {
      // Delay response for 35 seconds (longer than typical 30s timeout)
      await new Promise((resolve) => setTimeout(resolve, 35000));
      return res(ctx.status(200), ctx.json({}));
    }),
  ],

  /**
   * Malformed response handler
   *
   * Simulates invalid JSON or malformed responses. Use this to test response
   * parsing error handling.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.malformedResponse);
   * ```
   */
  malformedResponse: [
    rest.get('/api/*', (req, res, ctx) => {
      return res(
        ctx.status(200),
        ctx.set('Content-Type', 'application/json'),
        ctx.body('{ invalid json }')
      );
    }),
  ],

  /**
   * Slow response handler
   *
   * Simulates slow server responses (5s delay). Use this to test loading states,
   * progress indicators, and user experience during slow requests.
   *
   * @example
   * ```typescript
   * overrideHandlers(errorHandlers.slowResponse);
   * ```
   */
  slowResponse: [
    rest.get('/api/*', async (req, res, ctx) => {
      // Delay response by 5 seconds
      await new Promise((resolve) => setTimeout(resolve, 5000));
      return res(
        ctx.status(200),
        ctx.json({
          success: true,
          data: 'Slow response data',
        })
      );
    }),
  ],
};

// ============================================================================
// Error Handler Factory
// ============================================================================

/**
 * Create a custom error handler for a specific endpoint
 *
 * @param method - HTTP method (get, post, put, delete)
 * @param path - Endpoint path
 * @param status - HTTP status code
 * @param errorResponse - Error response body
 * @returns MSW handler for the custom error scenario
 *
 * @example
 * ```typescript
 * const agentNotFound = createErrorHandler(
 *   'get',
 *   '/api/atom-agent/agents/:agentId',
 *   404,
 *   { error: 'Agent not found', agent_id: 'unknown' }
 * );
 * overrideHandlers(agentNotFound);
 * ```
 */
export const createErrorHandler = (
  method: 'get' | 'post' | 'put' | 'delete',
  path: string,
  status: number,
  errorResponse: Record<string, any>
) => {
  const restMethod = rest[method];
  return restMethod(path, (req, res, ctx) => {
    return res(
      ctx.status(status),
      ctx.json({
        success: false,
        error_code: `${status}`,
        ...errorResponse,
      })
    );
  });
};

// ============================================================================
// Specific Error Scenarios
// ============================================================================

/**
 * Agent not found error
 */
export const agentNotFoundError = createErrorHandler(
  'get',
  '/api/atom-agent/agents/:agentId',
  404,
  {
    error: 'Agent not found',
    message: 'The specified agent does not exist',
  }
);

/**
 * Canvas not found error
 */
export const canvasNotFoundError = createErrorHandler(
  'get',
  '/api/canvas/:canvasId',
  404,
  {
    error: 'Canvas not found',
    message: 'The specified canvas does not exist',
  }
);

/**
 * Device not found error
 */
export const deviceNotFoundError = createErrorHandler(
  'get',
  '/api/devices/:deviceId',
  404,
  {
    error: 'Device not found',
    message: 'The specified device does not exist or is offline',
  }
);

/**
 * Governance check failed error
 */
export const governanceCheckFailedError = createErrorHandler(
  'post',
  '/api/canvas/submit',
  403,
  {
    error: 'Governance check failed',
    message: 'Agent maturity level insufficient for this action',
    details: {
      required_maturity: 'SUPERVISED',
      current_maturity: 'INTERN',
      action_type: 'submit_form',
    },
  }
);
