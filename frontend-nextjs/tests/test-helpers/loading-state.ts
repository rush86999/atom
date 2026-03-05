/**
 * Loading State Test Helpers
 *
 * Reusable helper functions for testing loading states in React components and API calls.
 * These helpers reduce code duplication and provide consistent loading state testing patterns.
 *
 * Features:
 * - createLoadingStateTest: Configure test with slow endpoint
 * - assertLoadingState: Check for common loading indicators
 * - waitForLoadingComplete: Wait for loading states to clear
 * - mockSlowEndpoint: Helper to apply slow handler
 * - createProgressiveLoadingMock: Progressive loading simulation
 *
 * @example
 * ```typescript
 * import { render, screen } from '@testing-library/react';
 * import { waitForLoadingComplete, mockSlowEndpoint } from '@/tests/test-helpers/loading-state';
 * import { server } from '@/tests/mocks/server';
 *
 * test('loads data with loading state', async () => {
 *   const cleanup = mockSlowEndpoint(server, 'GET', '/api/test', 2000);
 *   render(<MyComponent />);
 *   await waitForLoadingComplete({ timeout: 3000 });
 *   cleanup();
 * });
 * ```
 */

import { RenderResult, waitFor, waitForOptions } from '@testing-library/react';
import { rest, RestHandler, RestContext } from 'msw';

// ============================================================================
// Type Definitions
// ============================================================================

interface LoadingStateTestConfig {
  endpoint: string;
  delay: number;
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  response?: any;
  status?: number;
}

interface LoadingStateResult {
  waitForLoading: (options?: waitForOptions) => Promise<void>;
  waitForData: (options?: waitForOptions) => Promise<void>;
  waitForError: (options?: waitForOptions) => Promise<void>;
}

interface LoadingIndicators {
  spinner?: boolean;
  skeleton?: boolean;
  progressBar?: boolean;
  loadingText?: boolean;
}

// ============================================================================
// Loading State Assertion Helpers
// ============================================================================

/**
 * Assert that a loading state is active in the rendered component.
 *
 * Checks for common loading indicators:
 * - Spinner elements (data-testid="loading-spinner")
 * - Skeleton elements (data-testid="skeleton-item")
 * - Progress bars (data-testid="progress-bar", role="progressbar")
 * - Loading text (text content matching /loading|loading...|please wait/i)
 *
 * @param renderResult - RenderResult from @testing-library/react render()
 * @returns true if any loading state detected, false otherwise
 *
 * @example
 * ```typescript
 * const { container } = render(<MyComponent />);
 * const isLoading = assertLoadingState({ container });
 * expect(isLoading).toBe(true);
 * ```
 */
export function assertLoadingState(renderResult: Partial<RenderResult>): boolean {
  const { container } = renderResult;

  if (!container) {
    throw new Error('renderResult must include container');
  }

  // Check for loading spinner
  const spinner = container.querySelector('[data-testid="loading-spinner"]');
  if (spinner) return true;

  // Check for skeleton items
  const skeleton = container.querySelector('[data-testid="skeleton-item"]');
  if (skeleton) return true;

  // Check for progress bar
  const progressBar = container.querySelector('[data-testid="progress-bar"], [role="progressbar"]');
  if (progressBar) return true;

  // Check for loading text
  const text = container.textContent || '';
  if (text && /loading|please wait|fetching|submitting/i.test(text)) {
    return true;
  }

  return false;
}

/**
 * Assert specific loading indicators are present.
 *
 * @param renderResult - RenderResult from @testing-library/react render()
 * @param indicators - Which indicators to check for
 * @returns Object showing which indicators were found
 *
 * @example
 * ```typescript
 * const { container } = render(<MyComponent />);
 * const indicators = assertSpecificLoadingStates({ container }, {
 *   spinner: true,
 *   skeleton: true,
 * });
 * expect(indicators.spinner).toBe(true);
 * expect(indicators.skeleton).toBe(true);
 * ```
 */
export function assertSpecificLoadingStates(
  renderResult: Partial<RenderResult>,
  indicators: LoadingIndicators
): Record<keyof LoadingIndicators, boolean> {
  const { container } = renderResult;
  const result: Record<keyof LoadingIndicators, boolean> = {
    spinner: false,
    skeleton: false,
    progressBar: false,
    loadingText: false,
  };

  if (!container) {
    throw new Error('renderResult must include container');
  }

  if (indicators.spinner !== false) {
    result.spinner = !!container.querySelector('[data-testid="loading-spinner"]');
  }

  if (indicators.skeleton !== false) {
    result.skeleton = !!container.querySelector('[data-testid="skeleton-item"]');
  }

  if (indicators.progressBar !== false) {
    result.progressBar = !!container.querySelector(
      '[data-testid="progress-bar"], [role="progressbar"]'
    );
  }

  if (indicators.loadingText !== false) {
    const text = container.textContent || '';
    result.loadingText = /loading|please wait|fetching|submitting/i.test(text);
  }

  return result;
}

/**
 * Wait for all loading states to clear.
 *
 * Uses waitFor to poll until no loading indicators are present.
 * Throws a descriptive error if timeout is exceeded.
 *
 * @param renderResult - RenderResult from @testing-library/react render()
 * @param timeout - Maximum time to wait in milliseconds (default: 5000ms)
 * @returns Promise that resolves when loading is complete
 *
 * @example
 * ```typescript
 * render(<MyComponent />);
 * await waitForLoadingComplete({ container }, 3000);
 * expect(screen.getByText('Data loaded')).toBeVisible();
 * ```
 */
export async function waitForLoadingComplete(
  renderResult: Partial<RenderResult>,
  timeout: number = 5000
): Promise<void> {
  const { container } = renderResult;

  if (!container) {
    throw new Error('renderResult must include container');
  }

  await waitFor(
    () => {
      const isLoading = assertLoadingState({ container });
      if (isLoading) {
        throw new Error('Loading state still active');
      }
    },
    {
      timeout,
      interval: 100,
    }
  );
}

// ============================================================================
// MSW Handler Helpers
// ============================================================================

/**
 * Mock a slow endpoint for testing loading states.
 *
 * Applies an MSW handler with a delay to the server.
 * Returns a cleanup function to remove the handler.
 *
 * @param server - MSW server instance
 * @param method - HTTP method
 * @param path - API endpoint path
 * @param delayMs - Delay in milliseconds
 * @param response - Response data (default: { success: true })
 * @param status - HTTP status code (default: 200)
 * @returns Cleanup function to remove handler
 *
 * @example
 * ```typescript
 * import { server } from '@/tests/mocks/server';
 * import { mockSlowEndpoint } from '@/tests/test-helpers/loading-state';
 *
 * test('tests slow endpoint', () => {
 *   const cleanup = mockSlowEndpoint(server, 'GET', '/api/test', 2000);
 *   // ... test code ...
 *   cleanup();
 * });
 * ```
 */
export function mockSlowEndpoint(
  server: any,
  method: LoadingStateTestConfig['method'],
  path: string,
  delayMs: number,
  response: any = { success: true },
  status: number = 200
): () => void {
  const handlerMap = {
    GET: rest.get,
    POST: rest.post,
    PUT: rest.put,
    DELETE: rest.delete,
    PATCH: rest.patch,
  };

  const methodLower = (method || 'GET').toLowerCase() as keyof typeof handlerMap;
  const handlerCreator = handlerMap[methodLower.toUpperCase() as keyof typeof handlerMap];

  if (!handlerCreator) {
    throw new Error(`Invalid HTTP method: ${method}`);
  }

  const handler = handlerCreator(path, (req: any, res: any, ctx: RestContext) => {
    return res(
      ctx.delay(delayMs),
      ctx.status(status),
      ctx.json({
        ...response,
        _loadingTestMetadata: {
          delayMs,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  });

  server.use(handler);

  // Return cleanup function
  return () => {
    server.resetHandlers();
    // Re-apply default handlers if needed
    // server.use(...defaultHandlers);
  };
}

/**
 * Create a progressive loading mock that returns progressively faster responses.
 *
 * Useful for testing skeleton → data transitions and optimistic updates.
 * Each subsequent request uses the next delay in the array.
 *
 * @param endpoint - API endpoint path
 * @param delays - Array of delays for subsequent requests
 * @param method - HTTP method (default: 'GET')
 * @param response - Response data (default: { success: true })
 * @returns MSW RestHandler with attempt tracking
 *
 * @example
 * ```typescript
 * import { server } from '@/tests/mocks/server';
 * import { createProgressiveLoadingMock } from '@/tests/test-helpers/loading-state';
 *
 * test('tests progressive loading', () => {
 *   const handler = createProgressiveLoadingMock('/api/data', [2000, 1000, 500]);
 *   server.use(handler);
 *   // First request: 2s delay, second: 1s, third: 500ms
 * });
 * ```
 */
export function createProgressiveLoadingMock(
  endpoint: string,
  delays: number[],
  method: LoadingStateTestConfig['method'] = 'GET',
  response: any = { success: true }
): RestHandler {
  let attemptCount = 0;

  const handlerMap = {
    GET: rest.get,
    POST: rest.post,
    PUT: rest.put,
    DELETE: rest.delete,
    PATCH: rest.patch,
  };

  const handlerCreator = handlerMap[method];
  if (!handlerCreator) {
    throw new Error(`Invalid HTTP method: ${method}`);
  }

  return handlerCreator(endpoint, (req: any, res: any, ctx: RestContext) => {
    const currentDelay = delays[Math.min(attemptCount, delays.length - 1)];
    attemptCount++;

    return res(
      ctx.delay(currentDelay),
      ctx.json({
        ...response,
        _progressiveLoadingMetadata: {
          requestNumber: attemptCount,
          delayMs: currentDelay,
          actualTimestamp: new Date().toISOString(),
        },
      })
    );
  });
}

// ============================================================================
// Test Creation Helpers
// ============================================================================

/**
 * Create a loading state test with configured slow endpoint.
 *
 * Wraps test setup with loading assertions and returns helper functions
 * for waiting on loading/data/error states.
 *
 * @param component - React component to test
 * @param config - Loading state test configuration
 * @returns Object with waitForLoading, waitForData, waitForError functions
 *
 * @example
 * ```typescript
 * import { render } from '@testing-library/react';
 * import { createLoadingStateTest } from '@/tests/test-helpers/loading-state';
 * import { server } from '@/tests/mocks/server';
 * import MyComponent from './MyComponent';
 *
 * test('loading state test', async () => {
 *   const { waitForLoading, waitForData } = await createLoadingStateTest(
 *     () => render(<MyComponent />),
 *     { endpoint: '/api/test', delay: 2000 }
 *   );
 *
 *   await waitForLoading();
 *   await waitForData();
 * });
 * ```
 */
export async function createLoadingStateTest(
  componentRenderer: () => Partial<RenderResult>,
  config: LoadingStateTestConfig
): Promise<LoadingStateResult> {
  const renderResult = componentRenderer();

  const waitForLoading = async (options: waitForOptions = {}) => {
    await waitFor(
      () => {
        const isLoading = assertLoadingState(renderResult);
        if (!isLoading) {
          throw new Error('Loading state not found');
        }
      },
      { timeout: 1000, ...options }
    );
  };

  const waitForData = async (options: waitForOptions = {}) => {
    await waitFor(
      () => {
        const isLoading = assertLoadingState(renderResult);
        if (isLoading) {
          throw new Error('Still loading');
        }
      },
      { timeout: config.delay + 2000, ...options }
    );
  };

  const waitForError = async (options: waitForOptions = {}) => {
    await waitFor(
      () => {
        const { container } = renderResult;
        if (!container) {
          throw new Error('renderResult must include container');
        }

        const errorElement = container.querySelector('[data-testid="error-message"]');
        if (!errorElement) {
          throw new Error('Error message not found');
        }
      },
      { timeout: config.delay + 2000, ...options }
    );
  };

  return { waitForLoading, waitForData, waitForError };
}

// ============================================================================
// Utility Helpers
// ============================================================================

/**
 * Measure actual delay of an async operation.
 *
 * Useful for validating that loading states persist for expected durations.
 *
 * @param operation - Async function to measure
 * @returns Object with result, durationMs, startTime, endTime
 *
 * @example
 * ```typescript
 * import { measureDelay } from '@/tests/test-helpers/loading-state';
 * import apiClient from '@/lib/api';
 *
 * test('validates 2s delay', async () => {
 *   const { durationMs } = await measureDelay(() => apiClient.get('/api/slow'));
 *   expect(durationMs).toBeGreaterThanOrEqual(1900); // Allow 100ms variance
 * });
 * ```
 */
export async function measureDelay<T>(operation: () => Promise<T>): Promise<{
  result: T;
  durationMs: number;
  startTime: number;
  endTime: number;
}> {
  const startTime = Date.now();
  const result = await operation();
  const endTime = Date.now();
  const durationMs = endTime - startTime;

  return { result, durationMs, startTime, endTime };
}

/**
 * Create a loading state tracker for manual state management.
 *
 * Useful for testing components that manually manage loading state.
 *
 * @returns Object with getState, setLoading, reset methods
 *
 * @example
 * ```typescript
 * import { createLoadingTracker } from '@/tests/test-helpers/loading-state';
 *
 * test('tracks loading state', async () => {
 *   const tracker = createLoadingTracker();
 *   expect(tracker.getState()).toBe('idle');
 *
 *   tracker.setLoading();
 *   expect(tracker.getState()).toBe('loading');
 *
 *   tracker.setSuccess();
 *   expect(tracker.getState()).toBe('success');
 * });
 * ```
 */
export function createLoadingTracker() {
  let state: 'idle' | 'loading' | 'success' | 'error' = 'idle';

  return {
    getState: () => state,
    setLoading: () => {
      state = 'loading';
    },
    setSuccess: () => {
      state = 'success';
    },
    setError: () => {
      state = 'error';
    },
    reset: () => {
      state = 'idle';
    },
  };
}

/**
 * Assert that loading state transitions occur in expected order.
 *
 * @param transitions - Array of state transitions that occurred
 * @param expectedOrder - Expected order of state transitions
 *
 * @example
 * ```typescript
 * import { assertTransitionOrder } from '@/tests/test-helpers/loading-state';
 *
 * test('validates loading→success transition', () => {
 *   const transitions = ['idle', 'loading', 'loading', 'success'];
 *   assertTransitionOrder(transitions, ['idle', 'loading', 'success']);
 * });
 * ```
 */
export function assertTransitionOrder(
  transitions: string[],
  expectedOrder: string[]
): void {
  let transitionIndex = 0;

  for (const expectedState of expectedOrder) {
    const foundIndex = transitions.indexOf(expectedState, transitionIndex);

    if (foundIndex === -1) {
      throw new Error(
        `Expected state "${expectedState}" not found in transitions after index ${transitionIndex}`
      );
    }

    if (foundIndex < transitionIndex) {
      throw new Error(
        `State "${expectedState}" appeared out of order (at index ${foundIndex}, expected after ${transitionIndex})`
      );
    }

    transitionIndex = foundIndex + 1;
  }

  // All states found in correct order
  expect(true).toBe(true);
}
