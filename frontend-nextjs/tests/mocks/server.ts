/**
 * MSW (Mock Service Worker) Server Setup
 *
 * Configures the MSW server for API mocking in Jest tests.
 *
 * Features:
 * - Automatic server lifecycle management (beforeAll, afterEach, afterAll)
 * - Handler override utilities for test-specific scenarios
 * - Reset functionality to clean up test state
 * - Error detection for unhandled requests
 *
 * Usage in tests/setup.ts:
 * ```typescript
 * import { server } from './mocks/server';
 *
 * beforeAll(() => server.listen());
 * afterEach(() => server.resetHandlers());
 * afterAll(() => server.close());
 * ```
 *
 * Usage in test files:
 * ```typescript
 * import { overrideHandler, rest } from '@/tests/mocks/server';
 *
 * test('handles error scenario', () => {
 *   overrideHandler(
 *     rest.get('/api/endpoint', (req, res, ctx) => {
 *       return res(ctx.status(500));
 *     })
 *   );
 *   // ... test code
 * });
 * ```
 */

import { setupServer, SetupServerApi } from 'msw/node';
import { allHandlers } from './handlers';

// ============================================================================
// Server Setup
// ============================================================================

/**
 * MSW server instance with all default handlers
 *
 * The server is configured with:
 * - onUnhandledRequest: 'error' - Fails tests for unhandled API requests
 * - All default handlers from handlers.ts loaded
 */
export const server: SetupServerApi = setupServer(...allHandlers);

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Start the mock server with optional custom handlers
 *
 * Use this for manual server control (not needed if using tests/setup.ts)
 *
 * @param customHandlers - Optional array of handlers to override defaults
 * @returns The server instance for chaining
 *
 * @example
 * ```typescript
 * setupMockServer([
 *   rest.get('/api/custom', (req, res, ctx) => {
 *     return res(ctx.json({ custom: 'response' }));
 *   })
 * ]);
 * ```
 */
export function setupMockServer(customHandlers?: any[]): SetupServerApi {
  if (customHandlers && customHandlers.length > 0) {
    server.use(...customHandlers);
  }
  server.listen({ onUnhandledRequest: 'error' });
  return server;
}

/**
 * Reset all handlers to default state
 *
 * Removes any test-specific handlers added via overrideHandler/overrideHandlers
 * and restores the original handlers from handlers.ts
 *
 * @example
 * ```typescript
 * test('first test with override', () => {
 *   overrideHandler(customHandler);
 *   // ... test code
 * });
 *
 * test('second test without override', () => {
 *   resetMockServer(); // Restore defaults
 *   // ... test code
 * });
 * ```
 */
export function resetMockServer(): void {
  server.resetHandlers(...allHandlers);
}

/**
 * Override a specific handler for a test scenario
 *
 * Use this to mock specific responses for individual tests without affecting
 * other tests. The override persists until server.resetHandlers() is called
 * (which happens automatically in afterEach).
 *
 * @param handler - A single MSW handler (rest.get/post/put/delete)
 *
 * @example
 * ```typescript
 * import { overrideHandler, rest } from '@/tests/mocks/server';
 *
 * test('handles 404 error', async () => {
 *   overrideHandler(
 *     rest.get('/api/agent/:id', (req, res, ctx) => {
 *       return res(
 *         ctx.status(404),
 *         ctx.json({ error: 'Agent not found' })
 *       );
 *     })
 *   );
 *
 *   const response = await fetchAgentStatus('non-existent');
 *   expect(response.error).toBe('Agent not found');
 * });
 * ```
 */
export function overrideHandler(handler: any): void {
  server.use(handler);
}

/**
 * Override multiple handlers for a test scenario
 *
 * Use this to mock multiple endpoints for a single test scenario.
 *
 * @param handlers - Multiple MSW handlers
 *
 * @example
 * ```typescript
 * import { overrideHandlers, rest } from '@/tests/mocks/server';
 *
 * test('handles loading states with errors', async () => {
 *   overrideHandlers(
 *     rest.get('/api/agents', (req, res, ctx) => {
 *       return res(ctx.delay(1000), ctx.status(500));
 *     }),
 *     rest.get('/api/canvas/status', (req, res, ctx) => {
 *       return res(ctx.delay(500), ctx.status(503));
 *     })
 *   );
 *
 *   // Test loading and error states
 * });
 * ```
 */
export function overrideHandlers(...handlers: any[]): void {
  server.use(...handlers);
}

/**
 * Close the mock server
 *
 * Use this for manual cleanup (not needed if using tests/setup.ts)
 *
 * @example
 * ```typescript
 * afterAll(() => {
 *   closeMockServer();
 * });
 * ```
 */
export function closeMockServer(): void {
  server.close();
}

// ============================================================================
// Default Export
// ============================================================================

export default server;
