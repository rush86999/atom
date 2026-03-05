/**
 * MSW Retry Scenario Handlers
 *
 * Factory functions for creating retry test scenarios with MSW (Mock Service Worker).
 * These handlers simulate transient failures, flaky endpoints, and error patterns
 * for testing retry logic, exponential backoff, and error recovery flows.
 *
 * Key Features:
 * - createFlakyEndpoint: Fails N times then succeeds
 * - createAlwaysFailingEndpoint: Always returns specific error
 * - createSlowEndpoint: Delayed response for timeout testing
 * - Preserves request bodies across retries for validation
 *
 * Usage:
 * ```typescript
 * import { server } from '@/tests/mocks/server';
 * import { createFlakyEndpoint } from '@/tests/mocks/scenarios/retry-scenarios';
 *
 * test('retries on transient failure', async () => {
 *   server.use(
 *     createFlakyEndpoint('/api/test', 2, 503)
 *   );
 *
 *   const response = await apiClient.get('/api/test');
 *   expect(response.status).toBe(200);
 * });
 * ```
 *
 * @module tests/mocks/scenarios/retry-scenarios
 */

import { rest, ResponseTransformer, RequestParams } from 'msw';

/**
 * Creates a flaky endpoint that fails N times before succeeding
 *
 * Useful for testing retry logic, exponential backoff, and recovery flows.
 * Tracks attempt count in closure and returns errors for first N attempts.
 *
 * @param endpoint - API endpoint path (e.g., '/api/agents/:id')
 * @param failureCount - Number of failures before success (default: 2)
 * @param failureStatus - HTTP status code for failures (default: 503)
 * @param method - HTTP method (default: 'get')
 * @returns MSW request handler
 *
 * @example
 * ```typescript
 * // Fails 2 times then succeeds
 * server.use(
 *   createFlakyEndpoint('/api/agents/agent-123/status', 2, 503, 'get')
 * );
 *
 * const response = await apiClient.get('/api/agents/agent-123/status');
 * // First 2 attempts: 503 Service Unavailable
 * // 3rd attempt: 200 OK
 * expect(response.status).toBe(200);
 * ```
 */
export function createFlakyEndpoint(
  endpoint: string,
  failureCount: number = 2,
  failureStatus: number = 503,
  method: 'get' | 'post' | 'put' | 'patch' | 'delete' = 'get'
) {
  let attempts = 0;

  const methodHandlers = {
    get: rest.get,
    post: rest.post,
    put: rest.put,
    patch: rest.patch,
    delete: rest.delete,
  };

  const handler = methodHandlers[method];

  return handler(endpoint, async (req: RequestParams, res: any, ctx: any) => {
    attempts++;

    if (attempts <= failureCount) {
      // Return error response
      return res(
        ctx.status(failureStatus),
        ctx.json({
          success: false,
          error: getErrorMessageForStatus(failureStatus),
          error_code: getErrorCodeForStatus(failureStatus),
          attempt: attempts,
          retry_after: 2,
          timestamp: new Date().toISOString(),
        })
      );
    }

    // Success response after N failures
    const successResponse = {
      success: true,
      data: {
        message: 'Success after retries',
        attempts: attempts,
      },
      metadata: {
        totalAttempts: attempts,
        failuresBeforeSuccess: failureCount,
        timestamp: new Date().toISOString(),
      },
    };

    return res(
      ctx.status(200),
      ctx.json(successResponse)
    );
  });
}

/**
 * Creates an endpoint that always fails with a specific error
 *
 * Useful for testing retry exhaustion, error handling, and user-friendly
 * error message display.
 *
 * @param endpoint - API endpoint path
 * @param statusCode - HTTP status code to return (default: 503)
 * @param method - HTTP method (default: 'get')
 * @returns MSW request handler
 *
 * @example
 * ```typescript
 * server.use(
 *   createAlwaysFailingEndpoint('/api/test', 503, 'get')
 * );
 *
 * try {
 *   await apiClient.get('/api/test');
 * } catch (error) {
 *   expect(error.response.status).toBe(503);
 * }
 * ```
 */
export function createAlwaysFailingEndpoint(
  endpoint: string,
  statusCode: number = 503,
  method: 'get' | 'post' | 'put' | 'patch' | 'delete' = 'get'
) {
  const methodHandlers = {
    get: rest.get,
    post: rest.post,
    put: rest.put,
    patch: rest.patch,
    delete: rest.delete,
  };

  const handler = methodHandlers[method];

  return handler(endpoint, (req: RequestParams, res: any, ctx: any) => {
    return res(
      ctx.status(statusCode),
      ctx.json({
        success: false,
        error: getErrorMessageForStatus(statusCode),
        error_code: getErrorCodeForStatus(statusCode),
        details: 'This endpoint always fails for testing purposes',
        timestamp: new Date().toISOString(),
      })
    );
  });
}

/**
 * Creates a slow endpoint with configurable delay
 *
 * Useful for testing timeout handling, loading states, and slow network scenarios.
 * Can be combined with retry logic to test timeout recovery.
 *
 * @param endpoint - API endpoint path
 * @param delayMs - Delay in milliseconds before response (default: 2000)
 * @param method - HTTP method (default: 'get')
 * @param succeed - Whether to return success or error (default: true)
 * @returns MSW request handler
 *
 * @example
 * ```typescript
 * // 2 second delay for testing loading states
 * server.use(
 *   createSlowEndpoint('/api/slow', 2000, 'get', true)
 * );
 *
 * const startTime = Date.now();
 * await apiClient.get('/api/slow');
 * const elapsed = Date.now() - startTime;
 * expect(elapsed).toBeGreaterThanOrEqual(1900);
 * ```
 */
export function createSlowEndpoint(
  endpoint: string,
  delayMs: number = 2000,
  method: 'get' | 'post' | 'put' | 'patch' | 'delete' = 'get',
  succeed: boolean = true
) {
  const methodHandlers = {
    get: rest.get,
    post: rest.post,
    put: rest.put,
    patch: rest.patch,
    delete: rest.delete,
  };

  const handler = methodHandlers[method];

  return handler(endpoint, async (req: RequestParams, res: any, ctx: any) => {
    // Add delay
    await new Promise(resolve => setTimeout(resolve, delayMs));

    if (succeed) {
      return res(
        ctx.status(200),
        ctx.json({
          success: true,
          data: {
            message: 'Slow response completed',
            delayMs: delayMs,
          },
          metadata: {
            actualDelay: delayMs,
            timestamp: new Date().toISOString(),
          },
        })
      );
    } else {
      return res(
        ctx.status(504),
        ctx.json({
          success: false,
          error: 'Gateway Timeout',
          error_code: 'UPSTREAM_TIMEOUT',
          details: `Request took longer than expected (${delayMs}ms)`,
          timeoutMs: delayMs,
        })
      );
    }
  });
}

/**
 * Creates an endpoint that validates request body preservation
 *
 * Verifies that POST/PUT/PATCH requests preserve their payloads across retries.
 * Useful for testing that retry logic doesn't lose request data.
 *
 * @param endpoint - API endpoint path
 * @param failureCount - Number of failures before success (default: 1)
 * @returns MSW request handler for POST requests
 *
 * @example
 * ```typescript
 * server.use(
 *   createBodyPreservationEndpoint('/api/data', 1)
 * );
 *
 * const requestBody = { message: 'test', value: 42 };
 * const response = await apiClient.post('/api/data', requestBody);
 *
 * // Verify body was preserved across retry
 * expect(response.data.received).toEqual(requestBody);
 * ```
 */
export function createBodyPreservationEndpoint(
  endpoint: string,
  failureCount: number = 1
) {
  let attempts = 0;

  return rest.post(endpoint, async (req: RequestParams, res: any, ctx: any) => {
    attempts++;

    // Capture request body for validation
    const body = await req.json();

    if (attempts <= failureCount) {
      return res(
        ctx.status(503),
        ctx.json({
          success: false,
          error: 'Service Unavailable',
          attempt: attempts,
        })
      );
    }

    // Success with body validation
    return res(
      ctx.status(200),
      ctx.json({
        success: true,
        received: body,
        metadata: {
          attempts: attempts,
          bodyPreserved: true,
          timestamp: new Date().toISOString(),
        },
      })
    );
  });
}

/**
 * Collection of common retry test scenarios
 *
 * Pre-configured handlers for typical retry testing patterns.
 * Can be used directly in tests or as a reference for custom scenarios.
 */
export const retryHandlers = {
  /**
   * 503 Service Unavailable - fails 2x then succeeds
   */
  flaky503: createFlakyEndpoint('/api/test/flaky', 2, 503),

  /**
   * 504 Gateway Timeout - always fails
   */
  always504: createAlwaysFailingEndpoint('/api/test/timeout', 504),

  /**
   * Slow endpoint - 2 second delay
   */
  slow2s: createSlowEndpoint('/api/test/slow', 2000),

  /**
   * POST endpoint with body preservation - fails 1x then succeeds
   */
  postWithBody: createBodyPreservationEndpoint('/api/test/body', 1),
};

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Maps HTTP status codes to error messages
 */
function getErrorMessageForStatus(status: number): string {
  const messages: Record<number, string> = {
    400: 'Bad Request',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'Not Found',
    408: 'Request Timeout',
    500: 'Internal Server Error',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
  };

  return messages[status] || `Error ${status}`;
}

/**
 * Maps HTTP status codes to error codes
 */
function getErrorCodeForStatus(status: number): string {
  const codes: Record<number, string> = {
    400: 'VALIDATION_ERROR',
    401: 'UNAUTHORIZED',
    403: 'FORBIDDEN',
    404: 'NOT_FOUND',
    408: 'REQUEST_TIMEOUT',
    500: 'INTERNAL_ERROR',
    503: 'SERVICE_UNAVAILABLE',
    504: 'GATEWAY_TIMEOUT',
  };

  return codes[status] || `ERROR_${status}`;
}
