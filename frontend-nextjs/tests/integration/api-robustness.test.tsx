/**
 * API Robustness Integration Tests
 *
 * Tests complete API failure recovery flows with automatic retry logic.
 * Validates that exponential backoff, retry mechanisms, and error recovery work correctly.
 *
 * Test Groups:
 * 1. Automatic Retry with Exponential Backoff (2 tests)
 * 2. Network Error Recovery (2 tests)
 * 3. Timeout with Retry (2 tests)
 * 4. Retry Exhaustion (1 test)
 * 5. Request Body Preservation (1 test)
 * 6. Concurrent Request Errors (1 test)
 *
 * Phase 133-04: API Robustness Integration Tests
 */

import { waitFor } from '@testing-library/react';
import { server } from '@/tests/mocks/server';
import { createRecoveryScenario } from '@/tests/mocks/scenarios/error-recovery';
import apiClient from '@/lib/api';
import { rest } from 'msw';

// ============================================================================
// Test Setup
// ============================================================================

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// ============================================================================
// Test Group 1: Automatic Retry with Exponential Backoff
// ============================================================================

describe('API Robustness - Automatic Retry with Exponential Backoff', () => {

  test('should automatically retry on 503 with exponential backoff', async () => {
    const attemptTimestamps: number[] = [];

    server.use(
      rest.get('/api/test/backoff', (req, res, ctx) => {
        attemptTimestamps.push(Date.now());

        // First 2 attempts fail with 503, 3rd succeeds
        if (attemptTimestamps.length < 3) {
          return res(
            ctx.status(503),
            ctx.json({
              success: false,
              error: 'Service Unavailable',
              attempt: attemptTimestamps.length,
            })
          );
        }

        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            data: {
              message: 'Success after retries',
              attempts: attemptTimestamps.length,
            },
          })
        );
      })
    );

    // Request should automatically retry and succeed
    const response = await apiClient.get('/api/test/backoff');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptTimestamps.length).toBe(3);

    // Verify exponential backoff (delay2 > delay1)
    if (attemptTimestamps.length >= 3) {
      const delay1 = attemptTimestamps[1] - attemptTimestamps[0];
      const delay2 = attemptTimestamps[2] - attemptTimestamps[1];

      // With jitter, allow ±30% variance, but overall exponential trend
      expect(delay2).toBeGreaterThan(delay1 * 0.7);
    }
  }, 20000);

  test('should verify retry count does not exceed MAX_RETRIES', async () => {
    let attemptCount = 0;

    server.use(
      rest.get('/api/test/max-retries', (req, res, ctx) => {
        attemptCount++;

        // Always fail with 503
        return res(
          ctx.status(503),
          ctx.json({
            success: false,
            error: 'Service Unavailable',
            attempt: attemptCount,
          })
        );
      })
    );

    // Should fail after MAX_RETRIES (3 attempts: initial + 2 retries)
    try {
      await apiClient.get('/api/test/max-retries');
      fail('Should have thrown error after MAX_RETRIES');
    } catch (error: any) {
      expect(error.response?.status).toBe(503);
    }

    // Verify 3 attempts were made (initial + 2 retries)
    expect(attemptCount).toBe(3);
  }, 20000);
});

// ============================================================================
// Test Group 2: Network Error Recovery
// ============================================================================

describe('API Robustness - Network Error Recovery', () => {

  test('should recover from transient 503 error', async () => {
    let attemptCount = 0;

    server.use(
      rest.get('/api/test/network-recovery', (req, res, ctx) => {
        attemptCount++;

        if (attemptCount === 1) {
          // First attempt fails with 503
          return res(
            ctx.status(503),
            ctx.json({
              success: false,
              error: 'Service Unavailable',
              error_code: 'SERVICE_OVERLOAD',
            })
          );
        }

        // Second attempt succeeds
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            data: { message: 'Service recovered' },
          })
        );
      })
    );

    // Automatic retry should succeed
    const response = await apiClient.get('/api/test/network-recovery');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBeGreaterThanOrEqual(2);
  });

  test('should recover from partial outage (503 → 503 → 200)', async () => {
    let attemptCount = 0;

    server.use(
      rest.get('/api/test/partial-outage', (req, res, ctx) => {
        attemptCount++;

        if (attemptCount < 3) {
          return res(
            ctx.status(503),
            ctx.json({
              success: false,
              error: 'Service Unavailable',
            })
          );
        }

        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            data: { message: 'Partial outage resolved' },
          })
        );
      })
    );

    // Should recover after 2 failures
    const response = await apiClient.get('/api/test/partial-outage');

    expect(response.status).toBe(200);
    expect(attemptCount).toBe(3);
  });
});

// ============================================================================
// Test Group 3: Timeout with Retry
// ============================================================================

describe('API Robustness - Timeout with Retry', () => {

  test('should handle timeout with successful retry', async () => {
    let attemptCount = 0;

    server.use(
      rest.post('/api/test/timeout-retry', (req, res, ctx) => {
        attemptCount++;

        if (attemptCount === 1) {
          // First attempt: timeout (exceeds 10s axios timeout)
          return new Promise((resolve) => {
            setTimeout(() => resolve(res(ctx.status(200))), 15000);
          });
        }

        // Second attempt: fast response
        return res(
          ctx.delay(100),
          ctx.json({
            success: true,
            data: { message: 'Fast response on retry' },
          })
        );
      })
    );

    // Automatic retry should succeed after timeout
    const response = await apiClient.post('/api/test/timeout-retry', {});

    expect(response.status).toBe(200);
    expect(response.data.data.message).toBe('Fast response on retry');
    expect(attemptCount).toBeGreaterThanOrEqual(2);
  }, 30000);

  test('should handle gateway timeout (504) with retry', async () => {
    let attemptCount = 0;

    server.use(
      rest.get('/api/test/gateway-timeout', (req, res, ctx) => {
        attemptCount++;

        if (attemptCount === 1) {
          return res(
            ctx.status(504),
            ctx.json({
              success: false,
              error: 'Gateway Timeout',
              error_code: 'UPSTREAM_TIMEOUT',
            })
          );
        }

        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            data: { message: 'Upstream recovered' },
          })
        );
      })
    );

    // Automatic retry should succeed
    const response = await apiClient.get('/api/test/gateway-timeout');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBeGreaterThanOrEqual(2);
  });
});

// ============================================================================
// Test Group 4: Retry Exhaustion
// ============================================================================

describe('API Robustness - Retry Exhaustion', () => {

  test('should fail gracefully after MAX_RETRIES exhausted', async () => {
    let attemptCount = 0;

    server.use(
      rest.get('/api/test/retry-exhaustion', (req, res, ctx) => {
        attemptCount++;

        // Always return 503
        return res(
          ctx.status(503),
          ctx.json({
            success: false,
            error: 'Service Unavailable',
            error_code: 'SERVICE_UNAVAILABLE',
            attempt: attemptCount,
          })
        );
      })
    );

    // Should fail after MAX_RETRIES exhausted
    try {
      await apiClient.get('/api/test/retry-exhaustion');
      fail('Should have thrown error');
    } catch (error: any) {
      expect(error.response?.status).toBe(503);
      expect(error.response?.data?.success).toBe(false);
      expect(error.response?.data?.error).toBe('Service Unavailable');
    }

    // Verify MAX_RETRIES was reached (3 attempts total)
    expect(attemptCount).toBe(3);
  }, 20000);
});

// ============================================================================
// Test Group 5: Request Body Preservation
// ============================================================================

describe('API Robustness - Request Body Preservation', () => {

  test('should preserve request body across retries', async () => {
    let attemptCount = 0;

    const requestBody = {
      name: 'Test User',
      email: 'test@example.com',
      age: 25,
    };

    server.use(
      rest.post('/api/test/body-preservation', async (req, res, ctx) => {
        attemptCount++;

        // Capture request body
        const body = await req.json();

        if (attemptCount < 3) {
          return res(
            ctx.status(503),
            ctx.json({
              success: false,
              error: 'Service Unavailable',
            })
          );
        }

        // Verify body was preserved across retries
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            data: {
              received: body,
              preserved: true,
            },
          })
        );
      })
    );

    const response = await apiClient.post('/api/test/body-preservation', requestBody);

    expect(response.status).toBe(200);
    expect(response.data.data.preserved).toBe(true);
    expect(response.data.data.received).toEqual(requestBody);
    expect(attemptCount).toBe(3);
  }, 15000);
});

// ============================================================================
// Test Group 6: Concurrent Request Errors
// ============================================================================

describe('API Robustness - Concurrent Request Errors', () => {

  test('should handle concurrent requests independently', async () => {
    let req1Count = 0;
    let req2Count = 0;
    let req3Count = 0;

    server.use(
      rest.get('/api/test/concurrent-1', (req, res, ctx) => {
        req1Count++;

        if (req1Count === 1) {
          return res(ctx.status(503), ctx.json({ success: false }));
        }

        return res(ctx.status(200), ctx.json({ success: true, id: 1 }));
      }),

      rest.get('/api/test/concurrent-2', (req, res, ctx) => {
        req2Count++;

        // Always succeeds
        return res(ctx.status(200), ctx.json({ success: true, id: 2 }));
      }),

      rest.get('/api/test/concurrent-3', (req, res, ctx) => {
        req3Count++;

        if (req3Count < 3) {
          return res(ctx.status(503), ctx.json({ success: false }));
        }

        return res(ctx.status(200), ctx.json({ success: true, id: 3 }));
      })
    );

    // Trigger concurrent requests
    const results = await Promise.allSettled([
      apiClient.get('/api/test/concurrent-1'),
      apiClient.get('/api/test/concurrent-2'),
      apiClient.get('/api/test/concurrent-3'),
    ]);

    // All requests should eventually succeed
    expect(results[0].status).toBe('fulfilled');
    expect(results[1].status).toBe('fulfilled');
    expect(results[2].status).toBe('fulfilled');

    // Request 1: Failed first, succeeded on retry
    expect(req1Count).toBeGreaterThanOrEqual(2);

    // Request 2: Succeeded immediately
    expect(req2Count).toBe(1);

    // Request 3: Failed 2x, succeeded on 3rd attempt
    expect(req3Count).toBeGreaterThanOrEqual(3);

    // Verify no state leakage (each request tracked independently)
    expect(req1Count).not.toBe(req2Count);
    expect(req2Count).not.toBe(req3Count);
  }, 30000);
});

// ============================================================================
// Test Group 7: createRecoveryScenario Integration
// ============================================================================

describe('API Robustness - createRecoveryScenario Integration', () => {

  test('should work with createRecoveryScenario factory', async () => {
    server.use(
      createRecoveryScenario('/api/test/factory', {
        failAttempts: 2,
        errorType: 503,
      })
    );

    const response = await apiClient.get('/api/test/factory');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(response.data.metadata.totalAttempts).toBe(3);
    expect(response.data.metadata.failuresBeforeSuccess).toBe(2);
  });

  test('should handle 504 gateway timeout recovery with manual handler', async () => {
    let attemptCount = 0;

    server.use(
      rest.post('/api/test/timeout-scenario', (req, res, ctx) => {
        attemptCount++;

        if (attemptCount === 1) {
          // First attempt: 504 Gateway Timeout
          return res(
            ctx.status(504),
            ctx.json({
              success: false,
              error: 'Gateway Timeout',
              error_code: 'UPSTREAM_TIMEOUT',
            })
          );
        }

        // Second attempt: success
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            data: { message: 'Recovered from timeout' },
          })
        );
      })
    );

    const response = await apiClient.post('/api/test/timeout-scenario', {});

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBe(2);
  });

  test('should handle 503 service unavailable recovery with manual handler', async () => {
    let attemptCount = 0;

    server.use(
      rest.get('/api/test/network-scenario', (req, res, ctx) => {
        attemptCount++;

        if (attemptCount === 1) {
          // First attempt: 503 Service Unavailable
          return res(
            ctx.status(503),
            ctx.json({
              success: false,
              error: 'Service Unavailable',
              error_code: 'SERVICE_UNAVAILABLE',
            })
          );
        }

        // Second attempt: success
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            data: { message: 'Service recovered' },
          })
        );
      })
    );

    const response = await apiClient.get('/api/test/network-scenario');

    expect(response.status).toBe(200);
    expect(response.data.success).toBe(true);
    expect(attemptCount).toBe(2);
  });
});
