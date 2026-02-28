/**
 * MSW Setup Verification Tests
 *
 * Basic tests to verify MSW is correctly installed, configured, and working.
 * These tests ensure the mocking infrastructure is functional before writing
 * integration tests.
 */

import { server, overrideHandler, rest } from '../server';
import { agentHandlers, canvasHandlers, deviceHandlers } from '../handlers';
import { errorHandlers } from '../errors';

describe('MSW Setup', function() {
  // Default handlers should be loaded
  test('should have default handlers configured', function() {
    expect(server).toBeDefined();
    const handlers = server.listHandlers();
    expect(handlers.length).toBeGreaterThan(40);
  });

  // Test health check endpoint
  test('should mock health check endpoint', async function() {
    const response = await fetch('/api/health');
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.status).toBe('healthy');
    expect(data.timestamp).toBeDefined();
  });

  // Test agent endpoint
  test('should mock agent status endpoint', async function() {
    const response = await fetch('/api/atom-agent/agents/test-agent/status');
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.agent_id).toBe('test-agent');
    expect(data.status).toBe('idle');
    expect(data.maturity_level).toBe('AUTONOMOUS');
  });

  // Test canvas endpoint
  test('should mock canvas submit endpoint', async function() {
    const response = await fetch('/api/canvas/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        canvas_id: 'test-canvas',
        form_data: { test: 'data' },
      }),
    });
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.success).toBe(true);
    expect(data.submission_id).toBeDefined();
    expect(data.governance_check).toBeDefined();
  });

  // Test device endpoint
  test('should mock device endpoint', async function() {
    const response = await fetch('/api/devices');
    const data = await response.json();

    expect(response.status).toBe(200);
    expect(data.devices).toBeDefined();
    expect(data.devices.length).toBeGreaterThan(0);
    expect(data.total).toBe(2);
  });

  // Test handler override
  test('should allow handler override for test scenarios', async function() {
    // Override agent status to return 404
    overrideHandler(
      rest.get('/api/atom-agent/agents/:agentId/status', function(req, res, ctx) {
        return res(
          ctx.status(404),
          ctx.json({ error: 'Agent not found' })
        );
      })
    );

    const response = await fetch('/api/atom-agent/agents/non-existent/status');
    const data = await response.json();

    expect(response.status).toBe(404);
    expect(data.error).toBe('Agent not found');
  });

  // Test error handlers
  test('should provide error scenario handlers', function() {
    expect(errorHandlers.networkError).toBeDefined();
    expect(errorHandlers.unauthorized).toBeDefined();
    expect(errorHandlers.forbidden).toBeDefined();
    expect(errorHandlers.notFound).toBeDefined();
    expect(errorHandlers.serverError).toBeDefined();
    expect(errorHandlers.serviceUnavailable).toBeDefined();
    expect(errorHandlers.rateLimited).toBeDefined();
  });

  // Test handler exports
  test('should export all handler collections', function() {
    expect(agentHandlers).toBeDefined();
    expect(agentHandlers.length).toBeGreaterThan(0);

    expect(canvasHandlers).toBeDefined();
    expect(canvasHandlers.length).toBeGreaterThan(0);

    expect(deviceHandlers).toBeDefined();
    expect(deviceHandlers.length).toBeGreaterThan(0);
  });

  // Test that handlers cover all major endpoints
  test('should have handlers for all major API categories', function() {
    // Health checks
    expect(server.listHandlers()).toContainEqual(
      expect.objectContaining({
        path: '/api/health',
      })
    );

    // Verify handlers exist for each category
    const handlers = server.listHandlers();
    const handlerCount = handlers.length;

    // Should have at least 40 handlers total
    expect(handlerCount).toBeGreaterThan(40);
  });

  // Test that handlers can be reset
  test('should allow handler reset', function() {
    const initialCount = server.listHandlers().length;

    // Add a temporary handler
    overrideHandler(
      rest.get('/api/test', function(req, res, ctx) {
        return res(ctx.status(200));
      })
    );

    expect(server.listHandlers().length).toBe(initialCount + 1);

    // Reset handlers
    server.resetHandlers();
    expect(server.listHandlers().length).toBe(initialCount);
  });
});
