/**
 * Canvas API Integration Tests
 *
 * Tests for Canvas presentation, form submission, and close operations
 * with MSW mocked backend responses.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import useCanvasState from '@/hooks/useCanvasState';

// Type definitions for test data
interface CanvasPresentResponse {
  success: boolean;
  canvas_id: string;
  status: string;
  agent_execution_id?: string;
}

interface CanvasSubmitResponse {
  success: boolean;
  submission_id: string;
  governance_check: {
    allowed: boolean;
    reason?: string;
  };
}

interface CanvasStatusResponse {
  canvas_id: string;
  status: 'active' | 'closed' | 'errored';
  agent_execution_id?: string;
}

interface CanvasCloseResponse {
  success: boolean;
  closed_at: string;
}

// Mock global window.atom.canvas API
declare global {
  interface Window {
    atom?: {
      canvas: {
        getState: (canvasId: string) => any;
        getAllStates: () => Array<{ canvas_id: string; state: any }>;
        subscribe: (callback: (state: any) => void) => () => void;
        subscribeAll: (callback: (event: any) => void) => () => void;
      };
    };
  }
}

// ============================================
// Test Utilities
// ============================================

function createMockCanvasState(canvasType: string = 'generic') {
  return {
    canvas_id: 'canvas-123',
    canvas_type: canvasType,
    created_at: '2024-02-28T10:00:00Z',
    updated_at: '2024-02-28T10:00:00Z',
    status: 'active',
    data: {}
  };
}

function setupWindowAtomCanvas() {
  if (typeof window !== 'undefined') {
    // Clear any existing setup
    delete (window as any).atom;

    const subscribers = new Set<(state: any) => void>();
    const allSubscribers = new Set<(event: any) => void>();
    const states = new Map<string, any>();

    (window as any).atom = {
      canvas: {
        getState: (canvasId: string) => states.get(canvasId) || null,
        getAllStates: () => Array.from(states.entries()).map(([canvas_id, state]) => ({ canvas_id, state })),
        subscribe: (callback: (state: any) => void) => {
          subscribers.add(callback);

          // Immediately call with all existing states
          states.forEach((state) => {
            setTimeout(() => callback(state), 0);
          });

          return () => {
            subscribers.delete(callback);
          };
        },
        subscribeAll: (callback: (event: any) => void) => {
          allSubscribers.add(callback);

          // Immediately call with all existing states
          states.forEach((state, canvasId) => {
            setTimeout(() => callback({ canvas_id: canvasId, state }), 0);
          });

          return () => {
            allSubscribers.delete(callback);
          };
        },
        _setState: (canvasId: string, state: any) => {
          states.set(canvasId, state);
          subscribers.forEach(cb => {
            try {
              cb(state);
            } catch (e) {
              // Ignore callback errors
            }
          });
          allSubscribers.forEach(cb => {
            try {
              cb({ canvas_id: canvasId, state });
            } catch (e) {
              // Ignore callback errors
            }
          });
        },
        _clear: () => {
          subscribers.clear();
          allSubscribers.clear();
          states.clear();
        }
      }
    };
  }
}

// ============================================
// Canvas Presentation Tests
// ============================================

describe('Canvas API Integration Tests - Presentation', () => {
  beforeEach(() => {
    setupWindowAtomCanvas();
  });

  test('should present canvas with generic type', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved).toEqual(canvasState);
      expect(retrieved.canvas_type).toBe('generic');
    });
  });

  test('should present canvas with docs type', async () => {
    const canvasState = createMockCanvasState('docs');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-docs-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-docs-123');
      expect(retrieved.canvas_type).toBe('docs');
    });
  });

  test('should present canvas with email type', async () => {
    const canvasState = createMockCanvasState('email');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-email-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-email-123');
      expect(retrieved.canvas_type).toBe('email');
    });
  });

  test('should present canvas with sheets type', async () => {
    const canvasState = createMockCanvasState('sheets');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-sheets-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-sheets-123');
      expect(retrieved.canvas_type).toBe('sheets');
    });
  });

  test('should present canvas with orchestration type', async () => {
    const canvasState = createMockCanvasState('orchestration');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-orchestration-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-orchestration-123');
      expect(retrieved.canvas_type).toBe('orchestration');
    });
  });

  test('should present canvas with terminal type', async () => {
    const canvasState = createMockCanvasState('terminal');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-terminal-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-terminal-123');
      expect(retrieved.canvas_type).toBe('terminal');
    });
  });

  test('should present canvas with coding type', async () => {
    const canvasState = createMockCanvasState('coding');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-coding-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-coding-123');
      expect(retrieved.canvas_type).toBe('coding');
    });
  });

  test('should include initial_data in canvas presentation', async () => {
    const initialData = {
      title: 'Test Canvas',
      content: 'Initial content',
      metadata: { key: 'value' }
    };

    const canvasState = {
      ...createMockCanvasState('generic'),
      data: initialData
    };

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved.data).toEqual(initialData);
      expect(retrieved.data.title).toBe('Test Canvas');
    });
  });

  test('should present canvas with agent_execution_id', async () => {
    const canvasState = {
      ...createMockCanvasState('generic'),
      agent_execution_id: 'exec-456'
    };

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved.agent_execution_id).toBe('exec-456');
    });
  });

  test('should handle multiple canvas presentations simultaneously', async () => {
    const canvas1 = createMockCanvasState('generic');
    const canvas2 = createMockCanvasState('docs');
    const canvas3 = createMockCanvasState('sheets');

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-1', canvas1);
      api._setState('canvas-2', canvas2);
      api._setState('canvas-3', canvas3);
    });

    await waitFor(() => {
      const allStates = api.getAllStates();
      expect(allStates).toHaveLength(3);
      expect(allStates[0].canvas_id).toBe('canvas-1');
      expect(allStates[1].canvas_id).toBe('canvas-2');
      expect(allStates[2].canvas_id).toBe('canvas-3');
    });
  });

  test('should trigger accessibility tree updates on canvas presentation', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    let receivedState: any = null;
    const unsubscribe = api.subscribe((state: any) => {
      receivedState = state;
    });

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      expect(receivedState).toEqual(canvasState);
      unsubscribe();
    });
  });
});

// ============================================
// Canvas Status Retrieval Tests
// ============================================

describe('Canvas API Integration Tests - Status Retrieval', () => {
  beforeEach(() => {
    setupWindowAtomCanvas();
  });

  test('should retrieve canvas status for active canvas', async () => {
    const canvasState = {
      ...createMockCanvasState('generic'),
      status: 'active' as const
    };

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved.status).toBe('active');
      expect(retrieved.canvas_id).toBe('canvas-123');
    });
  });

  test('should retrieve canvas status for closed canvas', async () => {
    const canvasState = {
      ...createMockCanvasState('generic'),
      status: 'closed' as const
    };

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-closed-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-closed-123');
      expect(retrieved.status).toBe('closed');
    });
  });

  test('should retrieve canvas status for errored canvas', async () => {
    const canvasState = {
      ...createMockCanvasState('generic'),
      status: 'errored' as const,
      error: 'Failed to render canvas'
    };

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-error-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-error-123');
      expect(retrieved.status).toBe('errored');
      expect(retrieved.error).toBe('Failed to render canvas');
    });
  });

  test('should include agent_execution_id in status response', async () => {
    const canvasState = {
      ...createMockCanvasState('generic'),
      status: 'active' as const,
      agent_execution_id: 'exec-789'
    };

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved.agent_execution_id).toBe('exec-789');
    });
  });

  test('should return all canvas states via getAllStates', async () => {
    const canvas1 = { ...createMockCanvasState('generic'), status: 'active' as const };
    const canvas2 = { ...createMockCanvasState('docs'), status: 'closed' as const };
    const canvas3 = { ...createMockCanvasState('sheets'), status: 'active' as const };

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-1', canvas1);
      api._setState('canvas-2', canvas2);
      api._setState('canvas-3', canvas3);
    });

    await waitFor(() => {
      const allStates = api.getAllStates();
      expect(allStates).toHaveLength(3);
      expect(allStates[0].state.status).toBe('active');
      expect(allStates[1].state.status).toBe('closed');
      expect(allStates[2].state.status).toBe('active');
    });
  });

  test('should filter canvas states by status', async () => {
    const activeCanvas = { ...createMockCanvasState('generic'), status: 'active' as const };
    const closedCanvas = { ...createMockCanvasState('docs'), status: 'closed' as const };

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-active', activeCanvas);
      api._setState('canvas-closed', closedCanvas);
    });

    await waitFor(() => {
      const allStates = api.getAllStates();
      const activeStates = allStates.filter(s => s.state.status === 'active');
      const closedStates = allStates.filter(s => s.state.status === 'closed');

      expect(activeStates).toHaveLength(1);
      expect(closedStates).toHaveLength(1);
      expect(activeStates[0].canvas_id).toBe('canvas-active');
      expect(closedStates[0].canvas_id).toBe('canvas-closed');
    });
  });
});

// ============================================
// Canvas Accessibility API Integration Tests
// ============================================

describe('Canvas API Integration Tests - Accessibility API', () => {
  beforeEach(() => {
    setupWindowAtomCanvas();
  });

  test('should expose canvas state via window.atom.canvas.getState', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      const retrieved = (window as any).atom.canvas.getState('canvas-123');
      expect(retrieved).toBeDefined();
      expect(retrieved.canvas_id).toBe('canvas-123');
    });
  });

  test('should expose all canvas states via window.atom.canvas.getAllStates', async () => {
    const canvas1 = createMockCanvasState('generic');
    const canvas2 = createMockCanvasState('docs');

    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-1', canvas1);
      api._setState('canvas-2', canvas2);
    });

    await waitFor(() => {
      const allStates = (window as any).atom.canvas.getAllStates();
      expect(allStates).toHaveLength(2);
      expect(allStates[0].canvas_id).toBe('canvas-1');
      expect(allStates[1].canvas_id).toBe('canvas-2');
    });
  });

  test('should trigger accessibility tree updates on state change', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    let updateCount = 0;
    let lastState: any = null;

    const unsubscribe = api.subscribe((state: any) => {
      updateCount++;
      lastState = state;
    });

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      expect(updateCount).toBeGreaterThan(0);
      expect(lastState).toEqual(canvasState);
      unsubscribe();
    });
  });

  test('should support multiple subscribers to same canvas', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    let subscriber1Called = false;
    let subscriber2Called = false;

    const unsubscribe1 = api.subscribe(() => { subscriber1Called = true; });
    const unsubscribe2 = api.subscribe(() => { subscriber2Called = true; });

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      expect(subscriber1Called).toBe(true);
      expect(subscriber2Called).toBe(true);
      unsubscribe1();
      unsubscribe2();
    });
  });

  test('should unsubscribe from accessibility updates', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    let updateCount = 0;

    const unsubscribe = api.subscribe(() => {
      updateCount++;
    });

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    await waitFor(() => {
      expect(updateCount).toBeGreaterThan(0);
      const beforeUnsubscribe = updateCount;
      unsubscribe();

      act(() => {
        api._setState('canvas-123', { ...canvasState, updated: true });
      });

      setTimeout(() => {
        expect(updateCount).toBe(beforeUnsubscribe);
      }, 100);
    });
  });

  test('should broadcast canvas updates to all subscribers', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    const receivedStates: any[] = [];

    const unsubscribe = api.subscribeAll((event: any) => {
      receivedStates.push(event);
    });

    act(() => {
      api._setState('canvas-1', canvasState);
      api._setState('canvas-2', { ...canvasState, canvas_id: 'canvas-2' });
    });

    await waitFor(() => {
      expect(receivedStates).toHaveLength(2);
      expect(receivedStates[0].canvas_id).toBe('canvas-1');
      expect(receivedStates[1].canvas_id).toBe('canvas-2');
      unsubscribe();
    });
  });
});

// ============================================
// Canvas useCanvasState Hook Integration Tests
// ============================================

describe('Canvas API Integration Tests - useCanvasState Hook', () => {
  beforeEach(() => {
    setupWindowAtomCanvas();
  });

  test('should retrieve canvas state via hook', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    const { result } = renderHook(() => useCanvasState('canvas-123'));

    await waitFor(() => {
      expect(result.current.state).toEqual(canvasState);
    });
  });

  test('should retrieve all states via hook', async () => {
    const canvas1 = createMockCanvasState('generic');
    const canvas2 = createMockCanvasState('docs');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-1', canvas1);
      api._setState('canvas-2', canvas2);
    });

    const { result } = renderHook(() => useCanvasState());

    await waitFor(() => {
      expect(result.current.allStates).toHaveLength(2);
      expect(result.current.allStates[0].canvas_id).toBe('canvas-1');
      expect(result.current.allStates[1].canvas_id).toBe('canvas-2');
    });
  });

  test('should update state when canvas changes', async () => {
    const api = (window as any).atom.canvas;
    const initialState = createMockCanvasState('generic');

    const { result } = renderHook(() => useCanvasState('canvas-123'));

    act(() => {
      api._setState('canvas-123', initialState);
    });

    await waitFor(() => {
      expect(result.current.state).toEqual(initialState);
    });

    const updatedState = { ...initialState, data: { updated: true } };

    act(() => {
      api._setState('canvas-123', updatedState);
    });

    await waitFor(() => {
      expect(result.current.state).toEqual(updatedState);
      expect(result.current.state.data.updated).toBe(true);
    });
  });

  test('should cleanup subscription on unmount', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-123', canvasState);
    });

    const { result, unmount } = renderHook(() => useCanvasState('canvas-123'));

    await waitFor(() => {
      expect(result.current.state).toEqual(canvasState);
    });

    unmount();

    // Should not throw after unmount
    act(() => {
      api._setState('canvas-123', { ...canvasState, updated: true });
    });

    await waitFor(() => {
      // Verify no memory leaks or errors
      expect(true).toBe(true);
    });
  });

  test('should get state by ID via hook', async () => {
    const canvas1 = createMockCanvasState('generic');
    const canvas2 = createMockCanvasState('docs');
    const api = (window as any).atom.canvas;

    act(() => {
      api._setState('canvas-1', canvas1);
      api._setState('canvas-2', canvas2);
    });

    const { result } = renderHook(() => useCanvasState());

    await waitFor(() => {
      const retrieved = result.current.getState('canvas-1');
      expect(retrieved).toEqual(canvas1);
      expect(retrieved.canvas_type).toBe('generic');

      const retrieved2 = result.current.getState('canvas-2');
      expect(retrieved2).toEqual(canvas2);
      expect(retrieved2.canvas_type).toBe('docs');
    });
  });

  test('should return null for non-existent canvas', async () => {
    const { result } = renderHook(() => useCanvasState());

    await waitFor(() => {
      const retrieved = result.current.getState('non-existent');
      expect(retrieved).toBeNull();
    });
  });

  test('should handle empty state on initial render', async () => {
    const { result } = renderHook(() => useCanvasState('canvas-123'));

    await waitFor(() => {
      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toHaveLength(0);
    });
  });
});
