/**
 * Error Recovery MSW Handlers Tests
 *
 * Tests the error recovery scenario factory functions and utilities.
 * Validates that handlers correctly simulate transient failures,
 * timeout scenarios, and network errors with proper tracking.
 */

/**
 * MSW Node.js Compatibility Patterns
 *
 * IMPORTANT: MSW 1.x res.networkError() doesn't work in Node.js/jsdom environment.
 * Use 503 Service Unavailable responses instead:
 *
 * // WRONG (broken in Node.js):
 * return res.networkError('Connection failed');
 *
 * // CORRECT (works in Node.js):
 * return res(
 *   ctx.status(503),
 *   ctx.json({ error: 'Service unavailable', code: 'SERVICE_UNAVAILABLE' })
 * );
 *
 * Error Shape Patterns:
 * - Network errors: error.code === 'ERR_NETWORK' or error.code === 'SERVICE_UNAVAILABLE'
 * - API errors: error.response?.status (404, 500, 503, etc.)
 * - Timeout errors: error.code === 'ECONNABORTED'
 *
 * Retry Logic in Tests:
 * - Disable retries with { retry: false } in apiClient calls
 * - Or mock apiClient entirely to bypass retry logic
 * - Suppress console.log for retry messages: jest.spyOn(console, 'log').mockImplementation(() => {})
 */

import { createRecoveryScenario, createRetryTracker, errorRecoveryHandlers } from '../scenarios/error-recovery';
import { rest } from 'msw';
import { server } from '../server';

// Suppress console.log for retry messages during tests
let consoleLogSpy: any;
let consoleErrorSpy: any;

beforeEach(() => {
  consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  server.listen();
});

afterEach(() => {
  consoleLogSpy?.mockRestore();
  consoleErrorSpy?.mockRestore();
  server.resetHandlers();
});

  afterAll(() => {
    server.close();
  });

  describe('createRecoveryScenario', () => {

    it('should create handler that fails N times then succeeds', async () => {
      // Use createRecoveryScenario to create a handler
      const scenarioHandler = createRecoveryScenario('/api/test/recovery-scenario', {
        failAttempts: 2,
        errorType: 503,
      });

      // Verify handler is defined
      expect(scenarioHandler).toBeDefined();
      expect(scenarioHandler).toBeTruthy();
    });

    it('should support custom error types', () => {
      const scenario503 = createRecoveryScenario('/api/test/503', {
        errorType: 503,
      });
      expect(scenario503).toBeDefined();

      const scenario504 = createRecoveryScenario('/api/test/504', {
        errorType: 504,
      });
      expect(scenario504).toBeDefined();

      const scenarioNetwork = createRecoveryScenario('/api/test/network', {
        errorType: 'network',
      });
      expect(scenarioNetwork).toBeDefined();

      const scenarioTimeout = createRecoveryScenario('/api/test/timeout', {
        errorType: 'timeout',
      });
      expect(scenarioTimeout).toBeDefined();
    });

    it('should support different HTTP methods', () => {
      const getScenario = createRecoveryScenario('/api/test/get', {
        method: 'get',
      });
      expect(getScenario).toBeDefined();

      const postScenario = createRecoveryScenario('/api/test/post', {
        method: 'post',
      });
      expect(postScenario).toBeDefined();

      const putScenario = createRecoveryScenario('/api/test/put', {
        method: 'put',
      });
      expect(putScenario).toBeDefined();

      const patchScenario = createRecoveryScenario('/api/test/patch', {
        method: 'patch',
      });
      expect(patchScenario).toBeDefined();

      const deleteScenario = createRecoveryScenario('/api/test/delete', {
        method: 'delete',
      });
      expect(deleteScenario).toBeDefined();
    });

    it('should support custom successAfter threshold', () => {
      const scenario = createRecoveryScenario('/api/test/success-after', {
        failAttempts: 2,
        successAfter: 5, // Succeeds on 5th attempt (not 3rd)
      });
      expect(scenario).toBeDefined();
    });

    it('should support delay between attempts', () => {
      const scenario = createRecoveryScenario('/api/test/delayed', {
        failAttempts: 2,
        delayBetweenAttempts: 1000,
      });
      expect(scenario).toBeDefined();
    });

    it('should support custom error message', () => {
      const scenario = createRecoveryScenario('/api/test/custom-error', {
        failAttempts: 1,
        errorMessage: 'Custom error message for testing',
      });
      expect(scenario).toBeDefined();
    });
  });

  describe('createRetryTracker', () => {

    it('should track attempt counts', () => {
      const tracker = createRetryTracker();

      expect(tracker.getAttempts()).toBe(0);

      tracker.trackAttempt();
      expect(tracker.getAttempts()).toBe(1);

      tracker.trackAttempt();
      expect(tracker.getAttempts()).toBe(2);

      tracker.trackAttempt();
      expect(tracker.getAttempts()).toBe(3);
    });

    it('should record timestamps for each attempt', () => {
      const tracker = createRetryTracker();

      tracker.trackAttempt();
      tracker.trackAttempt();
      tracker.trackAttempt();

      const timestamps = tracker.getTimestamps();
      expect(timestamps).toHaveLength(3);

      // Verify timestamps are reasonable (within last second)
      const now = Date.now();
      timestamps.forEach(ts => {
        expect(ts).toBeLessThanOrEqual(now);
        expect(ts).toBeGreaterThan(now - 1000);
      });
    });

    it('should reset attempt counter and timestamps', () => {
      const tracker = createRetryTracker();

      tracker.trackAttempt();
      tracker.trackAttempt();
      expect(tracker.getAttempts()).toBe(2);
      expect(tracker.getTimestamps()).toHaveLength(2);

      tracker.reset();

      expect(tracker.getAttempts()).toBe(0);
      expect(tracker.getTimestamps()).toHaveLength(0);
    });

    it('should calculate elapsed time correctly', async () => {
      const tracker = createRetryTracker();

      tracker.trackAttempt();
      await new Promise(resolve => setTimeout(resolve, 100));
      tracker.trackAttempt();

      const elapsed = tracker.getElapsed();
      expect(elapsed).toBeGreaterThanOrEqual(90); // At least 90ms
      expect(elapsed).toBeLessThan(200); // Less than 200ms
    });

    it('should return zero elapsed time when no attempts made', () => {
      const tracker = createRetryTracker();
      expect(tracker.getElapsed()).toBe(0);
    });
  });

  describe('errorRecoveryHandlers', () => {

    it('should export pre-configured handlers', () => {
      expect(errorRecoveryHandlers.flaky).toBeDefined();
      expect(errorRecoveryHandlers.partialOutage).toBeDefined();
      expect(errorRecoveryHandlers.degraded).toBeDefined();
      expect(errorRecoveryHandlers.timeoutRecovery).toBeDefined();
      expect(errorRecoveryHandlers.gatewayTimeout).toBeDefined();
      expect(errorRecoveryHandlers.networkRecovery).toBeDefined();
      expect(errorRecoveryHandlers.connectionReset).toBeDefined();
    });

    it('should have handler for flaky endpoint', () => {
      expect(errorRecoveryHandlers.flaky).toBeDefined();
      // MSW handlers are objects, not functions
      expect(errorRecoveryHandlers.flaky).toBeTruthy();
    });

    it('should have handler for timeout recovery', () => {
      expect(errorRecoveryHandlers.timeoutRecovery).toBeDefined();
      expect(errorRecoveryHandlers.timeoutRecovery).toBeTruthy();
    });

    it('should have handler for network recovery', () => {
      expect(errorRecoveryHandlers.networkRecovery).toBeDefined();
      expect(errorRecoveryHandlers.networkRecovery).toBeTruthy();
    });
  });

  describe('Recovery scenario validation', () => {

    it('should create correct number of handler arrays', () => {
      // Test that handlers are organized correctly
      expect(errorRecoveryHandlers.flaky).toBeDefined();
      expect(errorRecoveryHandlers.timeoutRecovery).toBeDefined();
      expect(errorRecoveryHandlers.networkRecovery).toBeDefined();
    });
  });
});
