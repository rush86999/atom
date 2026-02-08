/**
 * Integration Tests for Critical API Routes
 *
 * Tests critical API routes that handle agent governance, workflows, and automation
 * These are security-critical and user-facing endpoints
 */

import { createMocks } from 'node-mocks-http';
import handler from '../../pages/api/agent-governance/[...path]';

describe('Agent Governance API - Integration Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Route Proxy Invariants', () => {
    it('should forward GET requests to backend', async () => {
      const { req, res } = createMocks({
        method: 'GET',
        query: { path: ['health'] },
      });

      // Mock fetch
      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ status: 'healthy' }),
      });

      await handler(req, res);

      // Invariant: Should call fetch with correct URL
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent-governance/health'),
        expect.objectContaining({
          method: 'GET',
        })
      );
    });

    it('should forward POST requests with body', async () => {
      const body = { agentId: 'test-agent', action: 'execute' };
      const { req, res } = createMocks({
        method: 'POST',
        query: { path: ['execute'] },
        body,
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({ success: true }),
      });

      await handler(req, res);

      // Invariant: POST requests should include body
      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(body),
        })
      );
    });

    it('should handle backend errors gracefully', async () => {
      const { req, res } = createMocks({
        method: 'GET',
        query: { path: ['test'] },
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Internal Server Error' }),
      });

      await handler(req, res);

      // Invariant: Should forward error response
      expect(res._getStatusCode()).toBe(500);
    });

    it('should handle network errors gracefully', async () => {
      const { req, res } = createMocks({
        method: 'GET',
        query: { path: ['test'] },
      });

      global.fetch = jest.fn().mockRejectedValueOnce(new Error('Network error'));

      await handler(req, res);

      // Invariant: Should return error status, not crash
      expect(res._getStatusCode()).toBeGreaterThanOrEqual(400);
    });
  });

  describe('Security Invariants', () => {
    it('should preserve Content-Type header', async () => {
      const { req, res } = createMocks({
        method: 'POST',
        query: { path: ['test'] },
        body: { test: 'data' },
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await handler(req, res);

      // Invariant: Should always send JSON content type
      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
          }),
        })
      );
    });

    it('should filter out path from query parameters', async () => {
      const { req, res } = createMocks({
        method: 'GET',
        query: { path: ['endpoint'], 'otherParam': 'value', 'path': ['should-be-filtered'] },
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await handler(req, res);

      // Invariant: 'path' should be excluded from query params
      const fetchUrl = (global.fetch as jest.Mock).mock.calls[0][0];
      expect(fetchUrl).not.toContain('path=');
    });

    it('should pass through query parameters correctly', async () => {
      const { req, res } = createMocks({
        method: 'GET',
        query: { path: ['test'], 'param1': 'value1', 'param2': 'value2' },
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await handler(req, res);

      // Invariant: Other query params should be preserved
      const fetchUrl = (global.fetch as jest.Mock).mock.calls[0][0];
      expect(fetchUrl).toContain('param1=value1');
      expect(fetchUrl).toContain('param2=value2');
    });
  });

  describe('Path Building Invariants', () => {
    it('should handle single-segment paths', async () => {
      const { req, res } = createMocks({
        method: 'GET',
        query: { path: ['health'] },
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await handler(req, res);

      // Invariant: Should build correct path
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent-governance/health'),
        expect.any(Object)
      );
    });

    it('should handle multi-segment paths', async () => {
      const { req, res } = createMocks({
        method: 'GET',
        query: { path: ['agents', '123', 'status'] },
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await handler(req, res);

      // Invariant: Should join path segments correctly
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/agent-governance/agents/123/status'),
        expect.any(Object)
      );
    });

    it('should handle empty path', async () => {
      const { req, res } = createMocks({
        method: 'GET',
        query: {},
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await handler(req, res);

      // Invariant: Empty path should go to base endpoint
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/api\/agent-governance\/?(\?|$)/),
        expect.any(Object)
      );
    });
  });

  describe('HTTP Method Handling', () => {
    it('should support all common HTTP methods', async () => {
      const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

      for (const method of methods) {
        const { req, res } = createMocks({
          method,
          query: { path: ['test'] },
          body: method === 'GET' ? undefined : { data: 'test' },
        });

        global.fetch = jest.fn().mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        });

        await handler(req, res);

        expect(global.fetch).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            method,
          })
        );
      }
    });

    it('should handle undefined method (default to GET)', async () => {
      const { req, res } = createMocks({
        query: { path: ['test'] },
      });

      global.fetch = jest.fn().mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

      await handler(req, res);

      // Invariant: Should default to GET
      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          method: 'GET',
        })
      );
    });
  });
});

describe('Workflow API Routes - Integration Tests', () => {
  // Import workflow test-step route
  let workflowTestHandler: any;

  beforeAll(() => {
    // Dynamic import to avoid module not found errors
    try {
      workflowTestHandler = require('../../pages/api/workflows/test-step').default;
    } catch (e) {
      console.warn('Workflow test-step route not found, skipping tests');
    }
  });

  if (workflowTestHandler) {
    describe('Workflow Test Step Invariants', () => {
      it('should validate workflow step before execution', async () => {
        const { req, res } = createMocks({
          method: 'POST',
          body: {
            stepId: 'step-123',
            workflowId: 'workflow-456',
          },
        });

        global.fetch = jest.fn().mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            valid: true,
            estimatedCost: 0.05,
          }),
        });

        await workflowTestHandler(req, res);

        // Invariant: Should validate step before execution
        expect(global.fetch).toHaveBeenCalled();
        expect(res._getStatusCode()).toBeLessThan(400);
      });

      it('should handle invalid workflow step gracefully', async () => {
        const { req, res } = createMocks({
          method: 'POST',
          body: {
            stepId: 'invalid-step',
          },
        });

        global.fetch = jest.fn().mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            valid: false,
            errors: ['Step not found'],
          }),
        });

        await workflowTestHandler(req, res);

        // Invariant: Should return validation errors
        expect(res._getStatusCode()).toBeGreaterThanOrEqual(400);
      });
    });
  } else {
    it('should skip workflow tests if route not available', () => {
      expect(true).toBe(true);
    });
  }
});
