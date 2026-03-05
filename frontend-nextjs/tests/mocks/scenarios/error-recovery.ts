/**
 * MSW Error Recovery Scenario Handlers
 *
 * Factory functions for creating error recovery test scenarios with MSW (Mock Service Worker).
 * These handlers simulate realistic backend recovery patterns: transient failures that resolve,
 * timeout scenarios, network errors, and degraded service states.
 *
 * Key Features:
 * - createRecoveryScenario: Fails N times then succeeds with configurable delays
 * - createRetryTracker: Track attempt counts and timestamps for backoff validation
 * - Pre-configured handlers: flaky endpoints, timeout recovery, network recovery
 * - Realistic error payloads: error_code, message, retry_after, timestamps
 *
 * Usage:
 * ```typescript
 * import { server } from '@/tests/mocks/server';
 * import { errorRecoveryHandlers, createRecoveryScenario } from '@/tests/mocks/scenarios/error-recovery';
 *
 * test('recovers from transient failure', async () => {
 *   server.use(
 *     createRecoveryScenario('/api/test', {
 *       failAttempts: 2,
 *       successAfter: 3,
 *       errorType: 503,
 *       delayBetweenAttempts: 1000
 *     })
 *   );
 *
 *   const response = await apiClient.get('/api/test');
 *   expect(response.status).toBe(200);
 * });
 * ```
 *
 * @module tests/mocks/scenarios/error-recovery
 */

import { rest, RequestParams } from 'msw';

/**
 * Error recovery scenario configuration
 */
export interface RecoveryScenarioOptions {
  /** Number of failures before success (default: 2) */
  failAttempts?: number;
  /** Attempt number when success should occur (default: failAttempts + 1) */
  successAfter?: number;
  /** HTTP status code for failures (default: 503) */
  errorType?: number | 'network' | 'timeout';
  /** Delay between attempts in milliseconds (default: 0) */
  delayBetweenAttempts?: number;
  /** Custom error message (default: auto-generated from status) */
  errorMessage?: string;
  /** Method type (default: 'get') */
  method?: 'get' | 'post' | 'put' | 'patch' | 'delete';
}

/**
 * Retry tracker for attempt counting and timestamp recording
 */
export interface RetryTracker {
  /** Get current attempt count */
  getAttempts(): number;
  /** Get all attempt timestamps */
  getTimestamps(): number[];
  /** Reset attempt counter */
  reset(): void;
  /** Record an attempt with timestamp */
  trackAttempt(): number;
  /** Get time elapsed since first attempt */
  getElapsed(): number;
}

/**
 * Creates a recovery scenario handler that fails N times then succeeds
 *
 * Simulates realistic backend recovery patterns where services experience
 * transient failures then recover. Tracks attempt count and timestamps
 * for backoff validation.
 *
 * @param endpoint - API endpoint path (e.g., '/api/agents/:id')
 * @param options - Recovery configuration options
 * @returns MSW request handler
 *
 * @example
 * ```typescript
 * // Fails 2 times with 503, succeeds on 3rd attempt
 * server.use(
 *   createRecoveryScenario('/api/agents/agent-123/status', {
 *     failAttempts: 2,
 *     errorType: 503,
 *     delayBetweenAttempts: 500
 *   })
 * );
 * ```
 */
export function createRecoveryScenario(
  endpoint: string,
  options: RecoveryScenarioOptions = {}
) {
  const {
    failAttempts = 2,
    successAfter,
    errorType = 503,
    delayBetweenAttempts = 0,
    errorMessage,
    method = 'get'
  } = options;

  let attempts = 0;
  const timestamps: number[] = [];
  const successThreshold = successAfter ?? failAttempts + 1;

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
    timestamps.push(Date.now());

    // Add delay if configured
    if (delayBetweenAttempts > 0 && attempts > 1) {
      await new Promise(resolve => setTimeout(resolve, delayBetweenAttempts));
    }

    // Check if we should still fail
    if (attempts < successThreshold) {
      if (errorType === 'network') {
        // Simulate network error
        throw new Error('Network Error');
      }

      if (errorType === 'timeout') {
        // Simulate timeout (exceeds 10s axios timeout)
        await new Promise(resolve => setTimeout(resolve, 15000));
        return res(ctx.status(200), ctx.json({}));
      }

      // Return HTTP error response
      const status = errorType as number;
      return res(
        ctx.status(status),
        ctx.json({
          success: false,
          error: errorMessage || getErrorMessageForStatus(status),
          error_code: getErrorCodeForStatus(status),
          attempt: attempts,
          retry_after: Math.ceil((successThreshold - attempts) * 1.5),
          timestamp: new Date().toISOString(),
        })
      );
    }

    // Success response after recovery
    const successResponse = {
      success: true,
      data: {
        message: 'Service recovered successfully',
        endpoint: endpoint,
      },
      metadata: {
        totalAttempts: attempts,
        failuresBeforeSuccess: successThreshold - 1,
        recoveredAt: new Date().toISOString(),
        timestamps: timestamps,
      },
    };

    return res(
      ctx.status(200),
      ctx.json(successResponse)
    );
  });
}

/**
 * Creates a retry tracker for attempt counting and timing
 *
 * Useful for validating exponential backoff and retry behavior in tests.
 * Returns functions to track attempts, get counts, and measure delays.
 *
 * @returns Retry tracker interface
 *
 * @example
 * ```typescript
 * const tracker = createRetryTracker();
 *
 * test('validates exponential backoff', async () => {
 *   server.use(createRecoveryScenario('/api/test', { failAttempts: 2 }));
 *
 *   await apiClient.get('/api/test');
 *
 *   const timestamps = tracker.getTimestamps();
 *   const delay1 = timestamps[1] - timestamps[0];
 *   const delay2 = timestamps[2] - timestamps[1];
 *
 *   expect(delay2).toBeGreaterThan(delay1); // Exponential increase
 * });
 * ```
 */
export function createRetryTracker(): RetryTracker {
  let attempts = 0;
  let firstAttempt: number | null = null;
  const timestamps: number[] = [];

  return {
    getAttempts(): number {
      return attempts;
    },

    getTimestamps(): number[] {
      return [...timestamps];
    },

    reset(): void {
      attempts = 0;
      timestamps.length = 0;
      firstAttempt = null;
    },

    trackAttempt(): number {
      attempts++;
      const timestamp = Date.now();
      timestamps.push(timestamp);

      if (firstAttempt === null) {
        firstAttempt = timestamp;
      }

      return attempts;
    },

    getElapsed(): number {
      if (firstAttempt === null || timestamps.length === 0) {
        return 0;
      }
      return timestamps[timestamps.length - 1] - firstAttempt;
    },
  };
}

// ============================================================================
// Pre-configured Recovery Scenarios
// ============================================================================

/**
 * Transient error handlers - temporary failures that recover
 */
export const transientErrorHandlers = [
  /**
   * Flaky endpoint: Fails 2x with 503, succeeds on 3rd
   * Simulates service overload that resolves
   */
  createRecoveryScenario('/api/test/flaky', {
    failAttempts: 2,
    errorType: 503,
  }),

  /**
   * Partial outage: 503 → 503 → 200 recovery pattern
   * Simulates database connection issues
   */
  createRecoveryScenario('/api/test/partial-outage', {
    failAttempts: 2,
    errorType: 503,
  }),

  /**
   * Degraded service: Slow response → error → success
   * Simulates performance degradation
   */
  createRecoveryScenario('/api/test/degraded', {
    failAttempts: 1,
    successAfter: 2,
    errorType: 503,
    delayBetweenAttempts: 2000,
  }),
];

/**
 * Timeout recovery handlers - timeout then success
 */
export const timeoutRecoveryHandlers = [
  /**
   * Timeout recovery: 1st attempt times out, 2nd succeeds
   * Simulates upstream service timeout
   */
  createRecoveryScenario('/api/test/timeout-recovery', {
    failAttempts: 1,
    errorType: 'timeout',
    method: 'post',
  }),

  /**
   * Gateway timeout: 504 → 200
   * Simulates proxy/load balancer timeout
   */
  createRecoveryScenario('/api/test/gateway-timeout', {
    failAttempts: 1,
    errorType: 504,
  }),
];

/**
 * Network recovery handlers - network failure then recovery
 */
export const networkRecoveryHandlers = [
  /**
   * Network recovery: 1st attempt has network error, 2nd succeeds
   * Simulates DNS resolution failure or connection refused
   */
  createRecoveryScenario('/api/test/network-recovery', {
    failAttempts: 1,
    errorType: 'network',
  }),

  /**
   * Connection reset: ECONNRESET → 200
   * Simulates connection dropped by server
   */
  createRecoveryScenario('/api/test/connection-reset', {
    failAttempts: 1,
    errorType: 'network',
  }),
];

/**
 * All recovery handlers combined
 */
export const allRecoveryHandlers = [
  ...transientErrorHandlers,
  ...timeoutRecoveryHandlers,
  ...networkRecoveryHandlers,
];

/**
 * Pre-configured recovery scenarios by type
 */
export const errorRecoveryHandlers = {
  flaky: transientErrorHandlers[0],
  partialOutage: transientErrorHandlers[1],
  degraded: transientErrorHandlers[2],
  timeoutRecovery: timeoutRecoveryHandlers[0],
  gatewayTimeout: timeoutRecoveryHandlers[1],
  networkRecovery: networkRecoveryHandlers[0],
  connectionReset: networkRecoveryHandlers[1],
  all: [...transientErrorHandlers, ...timeoutRecoveryHandlers, ...networkRecoveryHandlers],
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
    502: 'Bad Gateway',
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
    502: 'BAD_GATEWAY',
    503: 'SERVICE_UNAVAILABLE',
    504: 'GATEWAY_TIMEOUT',
  };

  return codes[status] || `ERROR_${status}`;
}
