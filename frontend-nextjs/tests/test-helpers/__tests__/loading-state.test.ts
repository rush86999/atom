/**
 * Loading State Test Helpers - Unit Tests
 *
 * Tests for the loading state test helper functions to ensure they work correctly.
 */

import { render, screen } from '@testing-library/react';
import { setupServer } from 'msw/node';
import { rest } from 'msw';
import {
  assertLoadingState,
  assertSpecificLoadingStates,
  waitForLoadingComplete,
  mockSlowEndpoint,
  createProgressiveLoadingMock,
  createLoadingStateTest,
  measureDelay,
  createLoadingTracker,
  assertTransitionOrder,
} from '../loading-state';

// ============================================================================
// Test Setup
// ============================================================================

const server = setupServer();

beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock component for testing
const TestComponent = ({ loading }: { loading: boolean }) => {
  if (loading) {
    return (
      <div>
        <div data-testid="loading-spinner">Loading...</div>
        <div data-testid="skeleton-item">Skeleton</div>
      </div>
    );
  }
  return <div data-testid="data-content">Data loaded</div>;
};

// ============================================================================
// assertLoadingState Tests
// ============================================================================

describe('assertLoadingState', () => {
  it('should detect loading spinner', () => {
    const { container } = render(<TestComponent loading={true} />);
    const isLoading = assertLoadingState({ container });
    expect(isLoading).toBe(true);
  });

  it('should return false when no loading state', () => {
    const { container } = render(<TestComponent loading={false} />);
    const isLoading = assertLoadingState({ container });
    expect(isLoading).toBe(false);
  });

  it('should throw error when container is missing', () => {
    expect(() => assertLoadingState({})).toThrow('renderResult must include container');
  });
});

// ============================================================================
// assertSpecificLoadingStates Tests
// ============================================================================

describe('assertSpecificLoadingStates', () => {
  it('should detect spinner indicator', () => {
    const { container } = render(<TestComponent loading={true} />);
    const indicators = assertSpecificLoadingStates({ container }, { spinner: true });
    expect(indicators.spinner).toBe(true);
  });

  it('should detect skeleton indicator', () => {
    const { container } = render(<TestComponent loading={true} />);
    const indicators = assertSpecificLoadingStates({ container }, { skeleton: true });
    expect(indicators.skeleton).toBe(true);
  });

  it('should return object with all indicator states', () => {
    const { container } = render(<TestComponent loading={true} />);
    const indicators = assertSpecificLoadingStates(
      { container },
      { spinner: true, skeleton: true, progressBar: true, loadingText: true }
    );
    expect(indicators).toHaveProperty('spinner');
    expect(indicators).toHaveProperty('skeleton');
    expect(indicators).toHaveProperty('progressBar');
    expect(indicators).toHaveProperty('loadingText');
  });
});

// ============================================================================
// waitForLoadingComplete Tests
// ============================================================================

describe('waitForLoadingComplete', () => {
  it('should wait for loading to clear', async () => {
    const { container, rerender } = render(<TestComponent loading={true} />);

    // Initially loading
    expect(assertLoadingState({ container })).toBe(true);

    // Wait for loading to complete (with timeout)
    const promise = waitForLoadingComplete({ container }, 3000);

    // Clear loading after 1s
    setTimeout(() => {
      rerender(<TestComponent loading={false} />);
    }, 1000);

    await promise;

    // Loading cleared
    expect(assertLoadingState({ container })).toBe(false);
  }, 5000);

  it('should throw error if timeout exceeded', async () => {
    const { container } = render(<TestComponent loading={true} />);

    await expect(
      waitForLoadingComplete({ container }, 500)
    ).rejects.toThrow();
  }, 2000);
});

// ============================================================================
// mockSlowEndpoint Tests
// ============================================================================

describe('mockSlowEndpoint', () => {
  it('should create slow GET endpoint', async () => {
    const cleanup = mockSlowEndpoint(server, 'GET', '/api/test', 1000, { data: 'test' });

    const startTime = Date.now();
    const response = await fetch('http://localhost/api/test');
    const endTime = Date.now();
    const elapsed = endTime - startTime;

    expect(elapsed).toBeGreaterThanOrEqual(900); // Allow 100ms variance
    cleanup();
  }, 5000);

  it('should return cleanup function', () => {
    const cleanup = mockSlowEndpoint(server, 'POST', '/api/test2', 500);
    expect(typeof cleanup).toBe('function');
    cleanup();
  });

  it('should throw error for invalid method', () => {
    expect(() =>
      mockSlowEndpoint(server as any, 'INVALID' as any, '/api/test', 1000)
    ).toThrow('Invalid HTTP method');
  });
});

// ============================================================================
// createProgressiveLoadingMock Tests
// ============================================================================

describe('createProgressiveLoadingMock', () => {
  it('should create progressive loading handler', async () => {
    const handler = createProgressiveLoadingMock('/api/progressive', [1000, 500, 250]);
    server.use(handler);

    const response1 = await fetch('http://localhost/api/progressive');
    const data1 = await response1.json();
    expect(data1._progressiveLoadingMetadata.requestNumber).toBe(1);
    expect(data1._progressiveLoadingMetadata.delayMs).toBe(1000);

    const response2 = await fetch('http://localhost/api/progressive');
    const data2 = await response2.json();
    expect(data2._progressiveLoadingMetadata.requestNumber).toBe(2);
    expect(data2._progressiveLoadingMetadata.delayMs).toBe(500);
  }, 5000);

  it('should use last delay for subsequent requests', async () => {
    const handler = createProgressiveLoadingMock('/api/progressive2', [1000, 500]);
    server.use(handler);

    // Request 1: 1000ms
    await fetch('http://localhost/api/progressive2');

    // Request 2: 500ms
    await fetch('http://localhost/api/progressive2');

    // Request 3: 500ms (last delay reused)
    const response = await fetch('http://localhost/api/progressive2');
    const data = await response.json();
    expect(data._progressiveLoadingMetadata.requestNumber).toBe(3);
    expect(data._progressiveLoadingMetadata.delayMs).toBe(500);
  }, 5000);
});

// ============================================================================
// createLoadingStateTest Tests
// ============================================================================

describe('createLoadingStateTest', () => {
  it('should create loading state test helpers', async () => {
    // Mock slow endpoint
    server.use(
      rest.get('/api/test-data', (req, res, ctx) => {
        return res(
          ctx.delay(1000),
          ctx.json({ success: true, data: 'test' })
        );
      })
    );

    const { waitForLoading, waitForData } = await createLoadingStateTest(
      () => render(<TestComponent loading={true} />),
      { endpoint: '/api/test-data', delay: 1000 }
    );

    // waitForLoading should detect loading state
    await expect(waitForLoading({ timeout: 500 })).resolves.not.toThrow();

    // Note: waitForData would require component to actually clear loading state
    // This is a basic test that helpers are created
    expect(waitForLoading).toBeDefined();
    expect(waitForData).toBeDefined();
  });
});

// ============================================================================
// measureDelay Tests
// ============================================================================

describe('measureDelay', () => {
  it('should measure operation duration', async () => {
    const { durationMs, result, startTime, endTime } = await measureDelay(async () => {
      await new Promise(resolve => setTimeout(resolve, 500));
      return 'test result';
    });

    expect(result).toBe('test result');
    expect(durationMs).toBeGreaterThanOrEqual(450); // Allow 50ms variance
    expect(typeof startTime).toBe('number');
    expect(typeof endTime).toBe('number');
    expect(endTime).toBeGreaterThan(startTime);
  });

  it('should return zero duration for sync operation', async () => {
    const { durationMs } = await measureDelay(() => Promise.resolve('sync'));
    expect(durationMs).toBeGreaterThanOrEqual(0);
  });
});

// ============================================================================
// createLoadingTracker Tests
// ============================================================================

describe('createLoadingTracker', () => {
  it('should track loading states', () => {
    const tracker = createLoadingTracker();

    expect(tracker.getState()).toBe('idle');

    tracker.setLoading();
    expect(tracker.getState()).toBe('loading');

    tracker.setSuccess();
    expect(tracker.getState()).toBe('success');

    tracker.setError();
    expect(tracker.getState()).toBe('error');

    tracker.reset();
    expect(tracker.getState()).toBe('idle');
  });

  it('should return state getter', () => {
    const tracker = createLoadingTracker();
    const state = tracker.getState();
    expect(state).toBe('idle');
  });
});

// ============================================================================
// assertTransitionOrder Tests
// ============================================================================

describe('assertTransitionOrder', () => {
  it('should validate correct transition order', () => {
    const transitions = ['idle', 'loading', 'loading', 'success'];
    expect(() =>
      assertTransitionOrder(transitions, ['idle', 'loading', 'success'])
    ).not.toThrow();
  });

  it('should throw error for missing state', () => {
    const transitions = ['idle', 'loading'];
    expect(() =>
      assertTransitionOrder(transitions, ['idle', 'loading', 'success'])
    ).toThrow('Expected state "success" not found');
  });

  it('should throw error for out-of-order state', () => {
    const transitions = ['idle', 'success', 'loading'];
    expect(() =>
      assertTransitionOrder(transitions, ['idle', 'loading', 'success'])
    ).toThrow('appeared out of order');
  });
});
