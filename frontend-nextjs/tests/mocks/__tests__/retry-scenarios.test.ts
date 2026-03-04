/**
 * Retry Scenario Handlers Tests
 *
 * Validates that MSW retry scenario handlers are created correctly:
 * - Factory functions return valid MSW handlers
 * - Handlers have correct structure and properties
 * - Pre-configured handlers are available
 */

import {
  createFlakyEndpoint,
  createAlwaysFailingEndpoint,
  createSlowEndpoint,
  createBodyPreservationEndpoint,
  retryHandlers,
} from '../scenarios/retry-scenarios';

describe('Retry Scenario Handlers', () => {
  describe('createFlakyEndpoint', () => {
    it('should create a GET handler by default', () => {
      const handler = createFlakyEndpoint('/api/test', 2, 503);

      expect(handler).toBeDefined();
      expect(typeof handler).toBe('object');
    });

    it('should support different HTTP methods', () => {
      const getHandler = createFlakyEndpoint('/api/test', 1, 503, 'get');
      const postHandler = createFlakyEndpoint('/api/test', 1, 503, 'post');
      const putHandler = createFlakyEndpoint('/api/test', 1, 503, 'put');
      const patchHandler = createFlakyEndpoint('/api/test', 1, 503, 'patch');
      const deleteHandler = createFlakyEndpoint('/api/test', 1, 503, 'delete');

      expect(getHandler).toBeDefined();
      expect(postHandler).toBeDefined();
      expect(putHandler).toBeDefined();
      expect(patchHandler).toBeDefined();
      expect(deleteHandler).toBeDefined();
    });

    it('should accept custom failure count and status code', () => {
      const handler1 = createFlakyEndpoint('/api/test', 3, 500);
      const handler2 = createFlakyEndpoint('/api/test', 1, 504);

      expect(handler1).toBeDefined();
      expect(handler2).toBeDefined();
    });

    it('should use default values when not provided', () => {
      const handler = createFlakyEndpoint('/api/test');

      expect(handler).toBeDefined();
    });
  });

  describe('createAlwaysFailingEndpoint', () => {
    it('should create a GET handler by default', () => {
      const handler = createAlwaysFailingEndpoint('/api/test', 503);

      expect(handler).toBeDefined();
      expect(typeof handler).toBe('object');
    });

    it('should support different HTTP methods', () => {
      const getHandler = createAlwaysFailingEndpoint('/api/test', 404, 'get');
      const postHandler = createAlwaysFailingEndpoint('/api/test', 500, 'post');

      expect(getHandler).toBeDefined();
      expect(postHandler).toBeDefined();
    });

    it('should support different status codes', () => {
      const handler404 = createAlwaysFailingEndpoint('/api/test', 404);
      const handler500 = createAlwaysFailingEndpoint('/api/test', 500);
      const handler503 = createAlwaysFailingEndpoint('/api/test', 503);
      const handler504 = createAlwaysFailingEndpoint('/api/test', 504);

      expect(handler404).toBeDefined();
      expect(handler500).toBeDefined();
      expect(handler503).toBeDefined();
      expect(handler504).toBeDefined();
    });
  });

  describe('createSlowEndpoint', () => {
    it('should create a GET handler with delay', () => {
      const handler = createSlowEndpoint('/api/test', 2000);

      expect(handler).toBeDefined();
    });

    it('should support different HTTP methods', () => {
      const getHandler = createSlowEndpoint('/api/test', 1000, 'get');
      const postHandler = createSlowEndpoint('/api/test', 1000, 'post');

      expect(getHandler).toBeDefined();
      expect(postHandler).toBeDefined();
    });

    it('should support custom delay values', () => {
      const handler100ms = createSlowEndpoint('/api/test', 100);
      const handler5s = createSlowEndpoint('/api/test', 5000);

      expect(handler100ms).toBeDefined();
      expect(handler5s).toBeDefined();
    });

    it('should support success/failure mode', () => {
      const successHandler = createSlowEndpoint('/api/test', 1000, 'get', true);
      const failureHandler = createSlowEndpoint('/api/test', 1000, 'get', false);

      expect(successHandler).toBeDefined();
      expect(failureHandler).toBeDefined();
    });
  });

  describe('createBodyPreservationEndpoint', () => {
    it('should create a POST handler', () => {
      const handler = createBodyPreservationEndpoint('/api/test', 1);

      expect(handler).toBeDefined();
    });

    it('should accept custom failure count', () => {
      const handler1 = createBodyPreservationEndpoint('/api/test', 1);
      const handler2 = createBodyPreservationEndpoint('/api/test', 2);
      const handler3 = createBodyPreservationEndpoint('/api/test', 3);

      expect(handler1).toBeDefined();
      expect(handler2).toBeDefined();
      expect(handler3).toBeDefined();
    });
  });

  describe('retryHandlers collection', () => {
    it('should provide pre-configured flaky503 handler', () => {
      expect(retryHandlers.flaky503).toBeDefined();
      expect(typeof retryHandlers.flaky503).toBe('object');
    });

    it('should provide pre-configured always504 handler', () => {
      expect(retryHandlers.always504).toBeDefined();
      expect(typeof retryHandlers.always504).toBe('object');
    });

    it('should provide pre-configured slow2s handler', () => {
      expect(retryHandlers.slow2s).toBeDefined();
      expect(typeof retryHandlers.slow2s).toBe('object');
    });

    it('should provide pre-configured postWithBody handler', () => {
      expect(retryHandlers.postWithBody).toBeDefined();
      expect(typeof retryHandlers.postWithBody).toBe('object');
    });

    it('should export all four handlers', () => {
      const handlers = Object.keys(retryHandlers);

      expect(handlers).toContain('flaky503');
      expect(handlers).toContain('always504');
      expect(handlers).toContain('slow2s');
      expect(handlers).toContain('postWithBody');
      expect(handlers.length).toBe(4);
    });
  });

  describe('Handler structure validation', () => {
    it('should create handlers with expected MSW structure', () => {
      const handler = createFlakyEndpoint('/api/test', 1, 503);

      // MSW handlers should have these properties
      expect(handler).toHaveProperty('info');
      expect(handler.info).toHaveProperty('path', '/api/test');
      expect(handler.info).toHaveProperty('method');
    });

    it('should use correct HTTP method in handler info', () => {
      const getHandler = createFlakyEndpoint('/api/test', 1, 503, 'get');
      const postHandler = createFlakyEndpoint('/api/test', 1, 503, 'post');

      expect(getHandler.info.method).toBe('GET');
      expect(postHandler.info.method).toBe('POST');
    });
  });
});
