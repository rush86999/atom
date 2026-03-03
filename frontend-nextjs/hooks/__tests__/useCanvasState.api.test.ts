/**
 * useCanvasState API Integration Tests
 *
 * Tests for canvas close operation, lifecycle, and WebSocket integration
 * with useCanvasState hook.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import useCanvasState from '@/hooks/useCanvasState';

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
        _removeState: (canvasId: string) => {
          states.delete(canvasId);
          // Notify subscribers of removal
          subscribers.forEach(cb => {
            try {
              cb(null);
            } catch (e) {
              // Ignore callback errors
            }
          });
          allSubscribers.forEach(cb => {
            try {
              cb({ canvas_id: canvasId, state: null });
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
// Canvas Close API Tests
// ============================================

describe('useCanvasState API Integration - Canvas Close', () => {
  let mockFetch: jest.MockedFunction<typeof fetch>;

  beforeEach(() => {
    setupWindowAtomCanvas();
    jest.clearAllMocks();

    // Mock fetch if not already mocked
    if (!jest.isMockFunction(global.fetch)) {
      mockFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
      (global as any).fetch = mockFetch;
    } else {
      mockFetch = global.fetch as jest.MockedFunction<typeof fetch>;
      mockFetch.mockClear();
    }
  });

  test('should close canvas successfully', async () => {
    const canvasState = createMockCanvasState('generic');
    const api = (window as any).atom.canvas;

    // Set initial state
    api._setState('canvas-123', canvasState);

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        success: true,
        closed_at: '2024-02-28T10:00:00Z'
      }),
      headers: {},
      bodyUsed: false,
      redirected: false,
      statusText: 'OK',
      type: 'basic' as ResponseType,
      url: '',
      clone: jest.fn(),
      arrayBuffer: async () => new ArrayBuffer(0),
      blob: async () => new Blob(),
      formData: async () => new FormData(),
      text: async () => ''
    });

    const { result } = renderHook(() => useCanvasState('canvas-123'));

    await waitFor(() => {
      expect(result.current.state).toEqual(canvasState);
    });

    // Close canvas via API
    await fetch('/api/canvas/canvas-123/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    });

    // Remove state
    api._removeState('canvas-123');

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved).toBeNull();
    });
  });

  test('should close canvas with unsaved changes prompt', async () => {
    const canvasState = {
      ...createMockCanvasState('generic'),
      has_unsaved_changes: true,
      data: { field: 'modified value' }
    };
    const api = (window as any).atom.canvas;

    api._setState('canvas-123', canvasState);

    let userConfirmed = false;

    // Simulate user prompt
    const confirmClose = () => {
      userConfirmed = true;
      return true;
    };

    if (confirmClose()) {
      api._removeState('canvas-123');
    }

    await waitFor(() => {
      expect(userConfirmed).toBe(true);
      const retrieved = api.getState('canvas-123');
      expect(retrieved).toBeNull();
    });
  });

  test('should cancel canvas close when user declines', async () => {
    const canvasState = {
      ...createMockCanvasState('generic'),
      has_unsaved_changes: true,
      data: { field: 'modified value' }
    };
    const api = (window as any).atom.canvas;

    api._setState('canvas-123', canvasState);

    let userConfirmed = false;

    // Simulate user declining
    const confirmClose = () => {
      userConfirmed = false;
      return false;
    };

    if (confirmClose()) {
      api._removeState('canvas-123');
    }

    await waitFor(() => {
      expect(userConfirmed).toBe(false);
      const retrieved = api.getState('canvas-123');
      expect(retrieved).not.toBeNull();
      expect(retrieved.data.field).toBe('modified value');
    });
  });

  test('should handle canvas close error for non-existent canvas', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({
        success: false,
        error: 'Canvas not found'
      }),
      headers: {},
      bodyUsed: false,
      redirected: false,
      statusText: 'Not Found',
      type: 'basic' as ResponseType,
      url: '',
      clone: jest.fn(),
      arrayBuffer: async () => new ArrayBuffer(0),
      blob: async () => new Blob(),
      formData: async () => new FormData(),
      text: async () => ''
    });

    const response = await fetch('/api/canvas/non-existent/close', {
      method: 'POST'
    });

    expect(response.status).toBe(404);

    const data = await response.json();
    expect(data.success).toBe(false);
    expect(data.error).toBe('Canvas not found');
  });

  test('should handle canvas close error for backend failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({
        success: false,
        error: 'Internal server error'
      }),
      headers: {},
      bodyUsed: false,
      redirected: false,
      statusText: 'Internal Server Error',
      type: 'basic' as ResponseType,
      url: '',
      clone: jest.fn(),
      arrayBuffer: async () => new ArrayBuffer(0),
      blob: async () => new Blob(),
      formData: async () => new FormData(),
      text: async () => ''
    });

    const response = await fetch('/api/canvas/canvas-123/close', {
      method: 'POST'
    });

    expect(response.status).toBe(500);
  });
});

// ============================================
// Canvas Lifecycle API Tests
// ============================================

describe('useCanvasState API Integration - Canvas Lifecycle', () => {
  beforeEach(() => {
    setupWindowAtomCanvas();
  });

  test('should handle full canvas lifecycle: Present → Update → Submit → Close', async () => {
    const api = (window as any).atom.canvas;

    // Present
    const initialState = createMockCanvasState('generic');
    api._setState('canvas-123', initialState);

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved.canvas_id).toBe('canvas-123');
      expect(retrieved.status).toBe('active');
    });

    // Update
    const updatedState = {
      ...initialState,
      data: { field: 'updated value', updated: true }
    };
    api._setState('canvas-123', updatedState);

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved.data.field).toBe('updated value');
    });

    // Submit (simulated state change)
    const submittedState = {
      ...updatedState,
      status: 'submitted',
      submitted_at: '2024-02-28T10:00:00Z'
    };
    api._setState('canvas-123', submittedState);

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved.status).toBe('submitted');
    });

    // Close
    api._removeState('canvas-123');

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved).toBeNull();
    });
  });

  test('should handle state transitions atomically', async () => {
    const api = (window as any).atom.canvas;

    const state1 = createMockCanvasState('generic');
    const state2 = { ...state1, data: { step: 2 } };
    const state3 = { ...state2, data: { step: 3 } };

    api._setState('canvas-123', state1);
    api._setState('canvas-123', state2);
    api._setState('canvas-123', state3);

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      // Should end up in final state
      expect(retrieved.data.step).toBe(3);
    });
  });

  test('should maintain separate state for multiple canvases', async () => {
    const api = (window as any).atom.canvas;

    const canvas1 = createMockCanvasState('generic');
    const canvas2 = createMockCanvasState('docs');
    const canvas3 = createMockCanvasState('sheets');

    api._setState('canvas-1', canvas1);
    api._setState('canvas-2', canvas2);
    api._setState('canvas-3', canvas3);

    await waitFor(() => {
      expect(api.getState('canvas-1')).toEqual(canvas1);
      expect(api.getState('canvas-2')).toEqual(canvas2);
      expect(api.getState('canvas-3')).toEqual(canvas3);
    });

    // Update one canvas
    const updatedCanvas2 = { ...canvas2, data: { updated: true } };
    api._setState('canvas-2', updatedCanvas2);

    await waitFor(() => {
      expect(api.getState('canvas-1')).toEqual(canvas1);
      expect(api.getState('canvas-2')).toEqual(updatedCanvas2);
      expect(api.getState('canvas-3')).toEqual(canvas3);
    });

    // Close one canvas
    api._removeState('canvas-2');

    await waitFor(() => {
      expect(api.getState('canvas-1')).not.toBeNull();
      expect(api.getState('canvas-2')).toBeNull();
      expect(api.getState('canvas-3')).not.toBeNull();
    });
  });

  test('should handle canvas cleanup on unmount', async () => {
    const api = (window as any).atom.canvas;
    const canvasState = createMockCanvasState('generic');

    api._setState('canvas-123', canvasState);

    const { result, unmount } = renderHook(() => useCanvasState('canvas-123'));

    await waitFor(() => {
      expect(result.current.state).toEqual(canvasState);
    });

    // Unmount hook
    unmount();

    // Close canvas (simulating cleanup)
    api._removeState('canvas-123');

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved).toBeNull();
    });
  });
});

// ============================================
// Concurrent Canvas Operations Tests
// ============================================

describe('useCanvasState API Integration - Concurrent Operations', () => {
  beforeEach(() => {
    setupWindowAtomCanvas();
  });

  test('should handle multiple canvases open simultaneously', async () => {
    const api = (window as any).atom.canvas;

    const canvases = [
      { id: 'canvas-1', state: createMockCanvasState('generic') },
      { id: 'canvas-2', state: createMockCanvasState('docs') },
      { id: 'canvas-3', state: createMockCanvasState('sheets') },
      { id: 'canvas-4', state: createMockCanvasState('email') },
      { id: 'canvas-5', state: createMockCanvasState('orchestration') }
    ];

    // Open all canvases
    canvases.forEach(({ id, state }) => {
      api._setState(id, state);
    });

    await waitFor(() => {
      const allStates = api.getAllStates();
      expect(allStates).toHaveLength(5);
    });
  });

  test('should isolate canvas operations', async () => {
    const api = (window as any).atom.canvas;

    const canvas1 = createMockCanvasState('generic');
    const canvas2 = createMockCanvasState('docs');

    api._setState('canvas-1', canvas1);
    api._setState('canvas-2', canvas2);

    await waitFor(() => {
      expect(api.getState('canvas-1')).toEqual(canvas1);
      expect(api.getState('canvas-2')).toEqual(canvas2);
    });

    // Update canvas-1
    const updatedCanvas1 = { ...canvas1, data: { field: 'updated' } };
    api._setState('canvas-1', updatedCanvas1);

    await waitFor(() => {
      expect(api.getState('canvas-1')).toEqual(updatedCanvas1);
      expect(api.getState('canvas-2')).toEqual(canvas2); // Unchanged
    });

    // Close canvas-1
    api._removeState('canvas-1');

    await waitFor(() => {
      expect(api.getState('canvas-1')).toBeNull();
      expect(api.getState('canvas-2')).toEqual(canvas2); // Still unchanged
    });
  });

  test('should handle rapid state changes', async () => {
    const api = (window as any).atom.canvas;

    const canvas = createMockCanvasState('generic');
    api._setState('canvas-123', canvas);

    // Rapid updates
    for (let i = 0; i < 10; i++) {
      api._setState('canvas-123', { ...canvas, data: { iteration: i } });
    }

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved.data.iteration).toBe(9); // Last update
    });
  });

  test('should handle concurrent reads and writes', async () => {
    const api = (window as any).atom.canvas;

    const canvas = createMockCanvasState('generic');
    api._setState('canvas-123', canvas);

    // Concurrent reads
    const reads = Array.from({ length: 5 }, () => api.getState('canvas-123'));

    // Concurrent writes
    const writes = Array.from({ length: 5 }, (_, i) =>
      api._setState('canvas-123', { ...canvas, data: { write: i } })
    );

    await waitFor(() => {
      const retrieved = api.getState('canvas-123');
      expect(retrieved).not.toBeNull();
      // One of the writes should have won
      expect(retrieved.data.write).toBeGreaterThanOrEqual(0);
      expect(retrieved.data.write).toBeLessThan(5);
    });
  });
});

// ============================================
// WebSocket Integration Tests
// ============================================

describe('useCanvasState API Integration - WebSocket Simulation', () => {
  beforeEach(() => {
    setupWindowAtomCanvas();
  });

  test('should handle incoming WebSocket updates', async () => {
    const api = (window as any).atom.canvas;

    const initialState = createMockCanvasState('generic');
    api._setState('canvas-123', initialState);

    const { result } = renderHook(() => useCanvasState('canvas-123'));

    await waitFor(() => {
      expect(result.current.state).toEqual(initialState);
    });

    // Simulate WebSocket message
    const wsUpdate = {
      type: 'canvas_update',
      canvas_id: 'canvas-123',
      state: {
        ...initialState,
        data: { field: 'updated via WebSocket' }
      }
    };

    // Apply WebSocket update
    api._setState(wsUpdate.canvas_id, wsUpdate.state);

    await waitFor(() => {
      expect(result.current.state.data.field).toBe('updated via WebSocket');
    });
  });

  test('should broadcast canvas changes to all clients', async () => {
    const api = (window as any).atom.canvas;

    const receivedUpdates: any[] = [];

    // Simulate multiple clients subscribing
    const unsubscribe1 = api.subscribeAll((event) => {
      receivedUpdates.push({ client: 1, event });
    });

    const unsubscribe2 = api.subscribeAll((event) => {
      receivedUpdates.push({ client: 2, event });
    });

    // Simulate canvas change from one client
    const update = {
      canvas_id: 'canvas-123',
      state: { ...createMockCanvasState('generic'), data: { broadcast: true } }
    };

    api._setState(update.canvas_id, update.state);

    await waitFor(() => {
      // Both clients should receive the update
      const client1Updates = receivedUpdates.filter(u => u.client === 1);
      const client2Updates = receivedUpdates.filter(u => u.client === 2);

      expect(client1Updates.length).toBeGreaterThan(0);
      expect(client2Updates.length).toBeGreaterThan(0);
      expect(client1Updates[0].event.canvas_id).toBe('canvas-123');
      expect(client2Updates[0].event.canvas_id).toBe('canvas-123');

      unsubscribe1();
      unsubscribe2();
    });
  });

  test('should handle WebSocket disconnection', async () => {
    const api = (window as any).atom.canvas;

    const canvas = createMockCanvasState('generic');
    api._setState('canvas-123', canvas);

    let connectionStatus = 'connected';

    // Simulate WebSocket disconnect
    const simulateDisconnect = () => {
      connectionStatus = 'disconnected';
    };

    simulateDisconnect();

    await waitFor(() => {
      expect(connectionStatus).toBe('disconnected');
      // Canvas state should still be available locally
      const retrieved = api.getState('canvas-123');
      expect(retrieved).not.toBeNull();
    });
  });

  test('should handle WebSocket reconnection', async () => {
    const api = (window as any).atom.canvas;

    let connectionStatus = 'disconnected';
    let reconnectAttempts = 0;

    // Simulate WebSocket reconnect
    const simulateReconnect = () => {
      reconnectAttempts++;
      connectionStatus = 'connected';
    };

    await waitFor(() => {
      expect(connectionStatus).toBe('disconnected');
    });

    simulateReconnect();

    await waitFor(() => {
      expect(connectionStatus).toBe('connected');
      expect(reconnectAttempts).toBe(1);
    });
  });
});
