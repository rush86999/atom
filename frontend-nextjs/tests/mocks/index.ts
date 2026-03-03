/**
 * MSW Mock Utilities - Barrel Export
 *
 * Central export point for all MSW mock utilities and handlers.
 * Provides a clean import interface for test files.
 *
 * Usage:
 * ```typescript
 * // Import everything from mocks
 * import { server, overrideHandler, allHandlers } from '@/tests/mocks';
 *
 * // Or import specific utilities
 * import { agentHandlers, canvasHandlers } from '@/tests/mocks/handlers';
 * import { setupMockServer } from '@/tests/mocks/server';
 * ```
 */

// Server utilities
export {
  server,
  setupMockServer,
  resetMockServer,
  overrideHandler,
  overrideHandlers,
  closeMockServer,
} from './server';

// Handler collections
export {
  allHandlers,
  commonHandlers,
  agentHandlers,
  canvasHandlers,
  deviceHandlers,
} from './handlers';

// Re-export MSW utilities for convenience
export { rest, RestHandler, DefaultRequestBodyType } from 'msw';

// Default export is the server instance
export { default } from './server';
