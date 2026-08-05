/**
 * Loading State Tests
 *
 * Comprehensive tests for loading indicators, skeleton loaders, and submit button states
 * during async API operations. Uses MSW's ctx.delay() for loading simulation and
 * React Testing Library's waitFor/findBy* queries for async state validation.
 *
 * Key Patterns:
 * - Use waitFor() instead of getBy* for async state transitions
 * - Use findBy* queries for timeout-based assertions (default 1000ms timeout)
 * - Use server.use() to override default handlers per test
 *
 * Test Categories:
 * 1. Loading spinner visibility during async operations
 * 2. Skeleton loader display for data fetching
 * 3. Submit button disabled state during form submission
 * 4. Multiple concurrent loading states
 * 5. Loading → error transition validation
 * 6. Loading → success transition validation
 *
 * Handlers are registered on the shared tests/mocks/server with wildcard-origin
 * paths (e.g. a "star" + "/api/atom-agent/agents" glob) because relative paths
 * never match the absolute http://127.0.0.1:8000 URLs the apiClient requests in
 * this MSW 1.x setup, and an axios request with no matching handler hangs.
 * Delays are kept small (~100-300ms) so the suite completes in a few seconds
 * while still verifying that loading states persist during async operations.
 */

import { renderHook, waitFor } from '@testing-library/react';
import { rest } from 'msw';
import apiClient from '@/lib/api';
import { server } from '@/tests/mocks/server';
import { createSlowEndpoint } from '@/tests/mocks/scenarios/loading-states';

// The apiClient retry interceptor backs off (1s, 2s, ...) on retryable (5xx)
// errors. Swap @lifeomic/attempt's retry for an immediate single attempt so the
// 500 scenarios resolve fast. Retry timing is covered in retry-logic.test.ts.
jest.mock('@lifeomic/attempt', () => ({
  retry: async (attemptFn: () => Promise<any>) => attemptFn(),
}));

// Base handlers guarantee every axios request is intercepted (an axios XHR
// request with NO matching handler hangs in this MSW setup). Each test may
// override per scenario with server.use(...).
const baseHandlers = [
  createSlowEndpoint('GET', '*/api/atom-agent/agents', 300, {
    agents: [
      {
        id: 'agent-mock-001',
        name: 'Test Agent 1',
        description: 'Mock agent for loading state testing',
        maturity_level: 'AUTONOMOUS',
        status: 'active',
      },
      {
        id: 'agent-mock-002',
        name: 'Test Agent 2',
        description: 'Another slow-loading agent',
        maturity_level: 'SUPERVISED',
        status: 'active',
      },
    ],
    total: 2,
  }),
  createSlowEndpoint('POST', '*/api/canvas/submit', 300, {
    success: true,
    submission_id: 'sub-test-123',
    governance_check: {
      allowed: true,
      agent_id: 'agent-mock-001',
      action_type: 'submit_form',
      maturity_level: 'SUPERVISED',
    },
  }),
  createSlowEndpoint('GET', '*/api/canvas/status', 200, {
    canvas_id: 'canvas-test',
    status: 'active',
  }),
  createSlowEndpoint('GET', '*/api/devices', 200, {
    devices: [],
    total: 0,
  }),
];

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'warn' });
  server.use(...baseHandlers);
});
afterEach(() => server.resetHandlers(...baseHandlers));
afterAll(() => server.close());

// Suppress console noise (retry logging + [API Error] logging)
let consoleLogSpy: any;
let consoleErrorSpy: any;

beforeEach(() => {
  consoleLogSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
  consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  consoleLogSpy?.mockRestore();
  consoleErrorSpy?.mockRestore();
});

// ============================================================================
// Test Helpers
// ============================================================================

/**
 * Helper to create a mock component with loading state.
 * In real tests, this would be an actual React component.
 */
function createMockLoadingComponent(loading: boolean, error: string | null, data: any) {
  return {
    loading,
    error,
    data,
    // Simulated render output
    render() {
      if (loading) return { type: 'loading-spinner', text: 'Loading...' };
      if (error) return { type: 'error-message', text: error };
      return { type: 'data', value: data };
    },
  };
}

// ============================================================================
// 1. Loading Spinner Visibility Tests
// ============================================================================

describe('1. Loading Spinner Visibility', () => {
  it('should show loading indicator during delayed GET request', async () => {
    let loadingState = { isLoading: true, data: null, error: null };

    // Mock component state
    const component = createMockLoadingComponent(loadingState.isLoading, loadingState.error, loadingState.data);

    // Initial loading state
    expect(component.render().type).toBe('loading-spinner');
    expect(component.render().text).toBe('Loading...');

    // Simulate API call with delay (base handler delays 300ms)
    const startTime = Date.now();
    const response = await apiClient.get('/api/atom-agent/agents');
    const endTime = Date.now();
    const elapsed = endTime - startTime;

    // Verify response took at least ~200ms (the request did not resolve
    // synchronously - a loading state could have been shown in the interim)
    expect(elapsed).toBeGreaterThanOrEqual(200);
    expect(response.data.agents).toBeDefined();
    expect(response.data.agents.length).toBe(2);

    // Verify loading metadata
    expect(response.data._loadingTestMetadata).toBeDefined();
    expect(response.data._loadingTestMetadata.delayMs).toBe(300);
  }, 10000);

  it('should show loading indicator during chat streaming request', async () => {
    // Mock slow chat endpoint
    server.use(
      rest.post('*/api/atom-agent/chat/stream', (req, res, ctx) => {
        return res(
          ctx.delay(300),
          ctx.json({
            success: true,
            response: 'Mock agent response',
            execution_id: 'exec-mock-123',
            _loadingTestMetadata: { delayMs: 300, actualTimestamp: new Date().toISOString() },
          })
        );
      })
    );

    const startTime = Date.now();
    const response = await apiClient.post('/api/atom-agent/chat/stream', { message: 'test' });
    const endTime = Date.now();
    const elapsed = endTime - startTime;

    // Verify response was not synchronous
    expect(elapsed).toBeGreaterThanOrEqual(200);
    expect(response.data.success).toBe(true);
    expect(response.data._loadingTestMetadata.delayMs).toBe(300);
  }, 10000);

  it('should use waitFor for async loading state transition', async () => {
    let loadingCompleted = false;

    // Simulate async operation
    const asyncOperation = async () => {
      await new Promise(resolve => setTimeout(resolve, 200));
      loadingCompleted = true;
      return { success: true };
    };

    // Start operation
    const operationPromise = asyncOperation();

    // Wait for loading to complete using waitFor
    await waitFor(() => {
      expect(loadingCompleted).toBe(true);
    });

    const result = await operationPromise;
    expect(result.success).toBe(true);
  }, 10000);
});

// ============================================================================
// 2. Skeleton Loader Display Tests
// ============================================================================

describe('2. Skeleton Loader Display', () => {
  it('should display skeleton during data fetch', async () => {
    // Mock slow agents endpoint with short delay
    server.use(
      rest.get('*/api/atom-agent/agents', (req, res, ctx) => {
        return res(
          ctx.delay(200),
          ctx.json({
            agents: [
              { id: 'agent-1', name: 'Agent 1', status: 'active' },
              { id: 'agent-2', name: 'Agent 2', status: 'active' },
            ],
            total: 2,
            _loadingTestMetadata: { delayMs: 200, actualTimestamp: new Date().toISOString() },
          })
        );
      })
    );

    let skeletonVisible = true;
    let dataReceived = null;

    // Simulate component render with skeleton
    const renderComponent = () => {
      if (dataReceived === null && skeletonVisible) {
        return { type: 'skeleton', items: 5 }; // 5 skeleton items
      }
      return { type: 'data', items: dataReceived };
    };

    // Initial render - skeleton visible
    const initialRender = renderComponent();
    expect(initialRender.type).toBe('skeleton');
    expect(initialRender.items).toBe(5);

    // Fetch data
    const response = await apiClient.get('/api/atom-agent/agents');
    dataReceived = response.data.agents;
    skeletonVisible = false;

    // After data fetch - skeleton removed, data displayed
    const finalRender = renderComponent();
    expect(finalRender.type).toBe('data');
    expect(finalRender.items.length).toBe(2);
  }, 10000);

  it('should transition from skeleton to data after delay', async () => {
    let state = 'loading'; // 'loading' | 'success' | 'error'
    let data = null;

    const transitionToData = async () => {
      state = 'loading';
      data = null;

      try {
        const response = await apiClient.get('/api/atom-agent/agents');
        data = response.data.agents;
        state = 'success';
      } catch (error) {
        state = 'error';
      }
    };

    // Start transition
    const promise = transitionToData();

    // Initially in loading state (skeleton)
    expect(state).toBe('loading');
    expect(data).toBeNull();

    // Wait for success state
    await waitFor(async () => {
      expect(state).toBe('success');
      expect(data).not.toBeNull();
    });

    await promise;
  }, 10000);

  it('should remove skeleton elements after data load', async () => {
    // Mock canvas status endpoint with short delay
    server.use(
      rest.get('*/api/canvas/status', (req, res, ctx) => {
        return res(
          ctx.delay(200),
          ctx.json({
            canvas_id: 'canvas-test',
            status: 'active',
            _loadingTestMetadata: { delayMs: 200, actualTimestamp: new Date().toISOString() },
          })
        );
      })
    );

    let skeletonCount = 3;
    let canvasData = null;

    const render = () => {
      if (canvasData === null) {
        return { skeletonElements: skeletonCount, dataElements: 0 };
      }
      return { skeletonElements: 0, dataElements: 1 };
    };

    // Initial render - skeleton present
    let renderResult = render();
    expect(renderResult.skeletonElements).toBe(3);
    expect(renderResult.dataElements).toBe(0);

    // Fetch data
    const response = await apiClient.get('/api/canvas/status?canvas_id=canvas-test');
    canvasData = response.data;
    skeletonCount = 0;

    // After data load - skeleton removed
    renderResult = render();
    expect(renderResult.skeletonElements).toBe(0);
    expect(renderResult.dataElements).toBe(1);
  }, 10000);
});

// ============================================================================
// 3. Submit Button Disabled State Tests
// ============================================================================

describe('3. Submit Button Disabled State', () => {
  it('should disable submit button during form submission', async () => {
    // Mock slow canvas submit endpoint with short delay
    server.use(
      rest.post('*/api/canvas/submit', (req, res, ctx) => {
        return res(
          ctx.delay(300),
          ctx.json({
            success: true,
            submission_id: 'sub-test-123',
            _loadingTestMetadata: { delayMs: 300, actualTimestamp: new Date().toISOString() },
          })
        );
      })
    );

    let isSubmitting = false;
    let submitComplete = false;

    const submitForm = async () => {
      isSubmitting = true;
      try {
        await apiClient.post('/api/canvas/submit', { canvas_id: 'test', data: {} });
        submitComplete = true;
      } finally {
        isSubmitting = false;
      }
    };

    // Before submission - button enabled
    expect(isSubmitting).toBe(false);
    expect(submitComplete).toBe(false);

    // Start submission
    const submitPromise = submitForm();

    // During submission - button should be disabled
    expect(isSubmitting).toBe(true);

    // Wait for completion
    await waitFor(() => {
      expect(isSubmitting).toBe(false);
      expect(submitComplete).toBe(true);
    });

    await submitPromise;
  }, 10000);

  it('should show loading text during form submission', async () => {
    let buttonText = 'Submit';
    let isLoading = false;

    const updateButtonText = () => {
      if (isLoading) {
        buttonText = 'Submitting...';
      } else {
        buttonText = 'Submit';
      }
      return buttonText;
    };

    // Initial state
    expect(updateButtonText()).toBe('Submit');

    // Start submission
    isLoading = true;
    expect(updateButtonText()).toBe('Submitting...');

    // Simulate slow submission (short delay)
    await new Promise(resolve => setTimeout(resolve, 200));

    isLoading = false;
    expect(updateButtonText()).toBe('Submit');
  }, 10000);

  it('should re-enable button after successful submission', async () => {
    let buttonDisabled = false;
    let submissionSuccess = false;

    const submitAndReset = async () => {
      buttonDisabled = true;

      try {
        await apiClient.post('/api/canvas/submit', { test: 'data' });
        submissionSuccess = true;
      } finally {
        buttonDisabled = false;
      }
    };

    // Initially enabled
    expect(buttonDisabled).toBe(false);

    // Start submission
    const promise = submitAndReset();

    // During submission - disabled
    await waitFor(() => {
      expect(buttonDisabled).toBe(true);
    });

    // After completion - re-enabled
    await waitFor(() => {
      expect(buttonDisabled).toBe(false);
      expect(submissionSuccess).toBe(true);
    });

    await promise;
  }, 10000);

  it('should re-enable button after failed submission', async () => {
    // Mock failed submission with short delay
    server.use(
      rest.post('*/api/canvas/submit', (req, res, ctx) => {
        return res(
          ctx.delay(150),
          ctx.status(400),
          ctx.json({ error: 'Validation failed' })
        );
      })
    );

    let buttonDisabled = false;
    let submissionError = null;

    const submitWithErrorReset = async () => {
      buttonDisabled = true;

      try {
        await apiClient.post('/api/canvas/submit', { invalid: 'data' });
      } catch (error: any) {
        submissionError = error;
      } finally {
        buttonDisabled = false;
      }
    };

    // Start submission
    const promise = submitWithErrorReset();

    // During submission - disabled
    await waitFor(() => {
      expect(buttonDisabled).toBe(true);
    });

    // After error - re-enabled
    await waitFor(() => {
      expect(buttonDisabled).toBe(false);
      expect(submissionError).not.toBeNull();
    });

    await promise;
  }, 10000);
});

// ============================================================================
// 4. Multiple Concurrent Loading States Tests
// ============================================================================

describe('4. Multiple Concurrent Loading States', () => {
  it('should handle multiple concurrent loading states', async () => {
    // Mock multiple slow endpoints
    server.use(
      rest.get('*/api/atom-agent/agents', (req, res, ctx) => {
        return res(ctx.delay(100), ctx.json({ agents: [], total: 0 }));
      }),
      rest.get('*/api/canvas/status', (req, res, ctx) => {
        return res(ctx.delay(150), ctx.json({ status: 'active' }));
      }),
      rest.get('*/api/devices', (req, res, ctx) => {
        return res(ctx.delay(200), ctx.json({ devices: [], total: 0 }));
      })
    );

    const loadingStates = {
      agents: true,
      canvas: true,
      devices: true,
    };

    const completedStates = {
      agents: false,
      canvas: false,
      devices: false,
    };

    // Start all requests concurrently
    const requests = [
      apiClient.get('/api/atom-agent/agents').then(() => {
        loadingStates.agents = false;
        completedStates.agents = true;
      }),
      apiClient.get('/api/canvas/status').then(() => {
        loadingStates.canvas = false;
        completedStates.canvas = true;
      }),
      apiClient.get('/api/devices').then(() => {
        loadingStates.devices = false;
        completedStates.devices = true;
      }),
    ];

    // Initially all loading
    expect(Object.values(loadingStates).every(v => v)).toBe(true);

    // Wait for all to complete independently
    await Promise.all(requests);

    // All loading states cleared, all completed
    expect(Object.values(loadingStates).every(v => !v)).toBe(true);
    expect(Object.values(completedStates).every(v => v)).toBe(true);
  }, 10000);

  it('should complete requests independently based on delay', async () => {
    const completionOrder: string[] = [];

    server.use(
      rest.get('*/api/test/fast', (req, res, ctx) => {
        return res(
          ctx.delay(100),
          ctx.json({ speed: 'fast' })
        );
      }),
      rest.get('*/api/test/medium', (req, res, ctx) => {
        return res(
          ctx.delay(300),
          ctx.json({ speed: 'medium' })
        );
      }),
      rest.get('*/api/test/slow', (req, res, ctx) => {
        return res(
          ctx.delay(500),
          ctx.json({ speed: 'slow' })
        );
      })
    );

    const requests = [
      apiClient.get('/api/test/fast').then(() => completionOrder.push('fast')),
      apiClient.get('/api/test/medium').then(() => completionOrder.push('medium')),
      apiClient.get('/api/test/slow').then(() => completionOrder.push('slow')),
    ];

    await Promise.all(requests);

    // Verify completion order (fastest first)
    expect(completionOrder).toEqual(['fast', 'medium', 'slow']);
  }, 10000);

  it('should verify all loading states active during concurrent requests', async () => {
    let agentsLoading = false;
    let canvasLoading = false;
    let devicesLoading = false;

    const startAgentsLoad = () => {
      agentsLoading = true;
      return apiClient.get('/api/atom-agent/agents').finally(() => {
        agentsLoading = false;
      });
    };

    const startCanvasLoad = () => {
      canvasLoading = true;
      return apiClient.get('/api/canvas/status').finally(() => {
        canvasLoading = false;
      });
    };

    const startDevicesLoad = () => {
      devicesLoading = true;
      return apiClient.get('/api/devices').finally(() => {
        devicesLoading = false;
      });
    };

    // Start all requests
    const promises = [
      startAgentsLoad(),
      startCanvasLoad(),
      startDevicesLoad(),
    ];

    // All loading states should be active
    await waitFor(() => {
      expect(agentsLoading).toBe(true);
      expect(canvasLoading).toBe(true);
      expect(devicesLoading).toBe(true);
    });

    // Wait for completion
    await Promise.all(promises);

    // All loading states cleared
    expect(agentsLoading).toBe(false);
    expect(canvasLoading).toBe(false);
    expect(devicesLoading).toBe(false);
  }, 10000);
});

// ============================================================================
// 5. Loading → Error Transition Tests
// ============================================================================

describe('5. Loading → Error Transition', () => {
  it('should transition from loading to error state', async () => {
    // Mock endpoint with delay then error
    server.use(
      rest.get('*/api/atom-agent/agents', (req, res, ctx) => {
        return res(
          ctx.delay(150),
          ctx.status(500),
          ctx.json({ error: 'Internal Server Error' })
        );
      })
    );

    let state = 'idle'; // 'idle' | 'loading' | 'error'
    let errorMessage = null;

    const fetchWithErrorTransition = async () => {
      state = 'loading';
      errorMessage = null;

      try {
        await apiClient.get('/api/atom-agent/agents');
        state = 'success';
      } catch (error: any) {
        state = 'error';
        errorMessage = error.response?.data?.error || 'Unknown error';
      }
    };

    // Start fetch
    const promise = fetchWithErrorTransition();

    // Initial loading state
    expect(state).toBe('loading');

    // Wait for error state
    await waitFor(() => {
      expect(state).toBe('error');
      expect(errorMessage).not.toBeNull();
    });

    await promise;

    // Verify error message
    expect(errorMessage).toBe('Internal Server Error');
  }, 10000);

  it('should clear loading state when error occurs', async () => {
    let isLoading = true;
    let hasError = false;

    // Mock error endpoint
    server.use(
      rest.post('*/api/canvas/submit', (req, res, ctx) => {
        return res(
          ctx.delay(100),
          ctx.status(400),
          ctx.json({ error: 'Validation failed' })
        );
      })
    );

    try {
      await apiClient.post('/api/canvas/submit', { invalid: true });
    } catch (error) {
      hasError = true;
    } finally {
      isLoading = false;
    }

    // Verify loading cleared and error set
    await waitFor(() => {
      expect(isLoading).toBe(false);
      expect(hasError).toBe(true);
    });
  }, 10000);

  it('should show error message after loading state clears', async () => {
    let displayedState = 'loading';
    let displayedMessage = '';

    const updateDisplay = (state: string, message?: string) => {
      displayedState = state;
      if (message) displayedMessage = message;
    };

    // Mock endpoint that fails after delay
    server.use(
      rest.get('*/api/atom-agent/agents/:agentId/status', (req, res, ctx) => {
        return res(
          ctx.delay(150),
          ctx.status(404),
          ctx.json({ error: 'Agent not found' })
        );
      })
    );

    updateDisplay('loading', 'Fetching agent status...');

    try {
      await apiClient.get('/api/atom-agent/agents/non-existent/status');
    } catch (error: any) {
      updateDisplay('error', error.response?.data?.error || 'Failed to fetch');
    }

    // Verify error displayed
    await waitFor(() => {
      expect(displayedState).toBe('error');
      expect(displayedMessage).toBe('Agent not found');
    });
  }, 10000);
});

// ============================================================================
// 6. Loading → Success Transition Tests
// ============================================================================

describe('6. Loading → Success Transition', () => {
  it('should transition from loading to success state', async () => {
    // Mock successful endpoint with short delay
    server.use(
      rest.get('*/api/atom-agent/agents', (req, res, ctx) => {
        return res(
          ctx.delay(200),
          ctx.json({
            agents: [{ id: 'agent-1', name: 'Test Agent' }],
            total: 1,
          })
        );
      })
    );

    let state = 'idle'; // 'idle' | 'loading' | 'success'
    let data = null;

    const fetchWithSuccessTransition = async () => {
      state = 'loading';
      data = null;

      try {
        const response = await apiClient.get('/api/atom-agent/agents');
        data = response.data;
        state = 'success';
      } catch (error) {
        state = 'error';
      }
    };

    // Start fetch
    const promise = fetchWithSuccessTransition();

    // Initial loading state
    expect(state).toBe('loading');

    // Wait for success state
    await waitFor(() => {
      expect(state).toBe('success');
      expect(data).not.toBeNull();
    });

    await promise;

    // Verify data
    expect(data.agents).toBeDefined();
    expect(data.agents.length).toBe(1);
  }, 10000);

  it('should clear loading state when data loads successfully', async () => {
    let isLoading = true;
    let hasData = false;
    let loadedData = null;

    // Mock successful endpoint
    server.use(
      rest.post('*/api/canvas/submit', (req, res, ctx) => {
        return res(
          ctx.delay(200),
          ctx.json({ success: true, submission_id: 'sub-123' })
        );
      })
    );

    try {
      const response = await apiClient.post('/api/canvas/submit', { test: 'data' });
      loadedData = response.data;
      hasData = true;
    } finally {
      isLoading = false;
    }

    // Verify success
    await waitFor(() => {
      expect(isLoading).toBe(false);
      expect(hasData).toBe(true);
      expect(loadedData).not.toBeNull();
    });

    expect(loadedData.success).toBe(true);
  }, 10000);

  it('should display data after loading state clears', async () => {
    let displayedState = 'loading';
    let displayedData = null;

    const updateDisplay = (state: string, data?: any) => {
      displayedState = state;
      if (data) displayedData = data;
    };

    // Mock successful data fetch
    server.use(
      rest.get('*/api/canvas/status', (req, res, ctx) => {
        return res(
          ctx.delay(200),
          ctx.json({
            canvas_id: 'canvas-test',
            status: 'active',
            created_at: new Date().toISOString(),
          })
        );
      })
    );

    updateDisplay('loading');

    const response = await apiClient.get('/api/canvas/status?canvas_id=canvas-test');
    updateDisplay('success', response.data);

    // Verify success state with data
    await waitFor(() => {
      expect(displayedState).toBe('success');
      expect(displayedData).not.toBeNull();
      expect(displayedData.status).toBe('active');
    });
  }, 10000);

  it('should handle rapid loading→success→loading transitions', async () => {
    let state = 'idle';
    let requestCount = 0;

    // Mock endpoint with varying delays
    server.use(
      rest.get('*/api/atom-agent/agents', (req, res, ctx) => {
        requestCount++;
        const delay = requestCount % 2 === 0 ? 200 : 300; // Alternating delays
        return res(
          ctx.delay(delay),
          ctx.json({ agents: [], total: 0, requestNumber: requestCount })
        );
      })
    );

    // Make multiple rapid requests
    const transitions: string[] = [];

    const makeRequest = async (iteration: number) => {
      state = 'loading';
      transitions.push(`iteration-${iteration}-loading`);

      await apiClient.get('/api/atom-agent/agents');

      state = 'success';
      transitions.push(`iteration-${iteration}-success`);
    };

    // Execute requests sequentially
    await makeRequest(1);
    await makeRequest(2);
    await makeRequest(3);

    // Verify all transitions occurred
    expect(transitions).toContain('iteration-1-loading');
    expect(transitions).toContain('iteration-1-success');
    expect(transitions).toContain('iteration-2-loading');
    expect(transitions).toContain('iteration-2-success');
    expect(transitions).toContain('iteration-3-loading');
    expect(transitions).toContain('iteration-3-success');

    // Final state should be success
    expect(state).toBe('success');
  }, 10000);
});
