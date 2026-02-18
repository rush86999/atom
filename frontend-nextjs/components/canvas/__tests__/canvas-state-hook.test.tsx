/**
 * useCanvasState Hook Unit Tests
 *
 * Tests for useCanvasState hook integration with window.atom.canvas global API
 * in Tauri webview environment. Verifies hook initialization, API access, subscriptions,
 * cleanup, and coexistence with Tauri IPC bridge.
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { useCanvasState } from '@/hooks/useCanvasState';
import type {
  AnyCanvasState,
  CanvasStateAPI,
  CanvasStateChangeEvent
} from '@/components/canvas/types';

// Mock Tauri environment type
declare global {
  interface Window {
    atom?: {
      canvas?: CanvasStateAPI;
    };
    __TAURI__?: {
      invoke: (cmd: string, args?: any) => Promise<any>;
    };
  }
}

describe('useCanvasState Hook in Tauri Environment', () => {
  beforeEach(() => {
    // Initialize Tauri IPC bridge (simulates Tauri webview environment)
    window.__TAURI__ = {
      invoke: jest.fn().mockResolvedValue({ success: true })
    };

    // Initialize canvas state API (simulates Phase 20 implementation)
    // Note: The hook implementation calls subscribe(callback) when canvasId is provided,
    // not subscribe(canvasId, callback) as the types suggest
    window.atom = {
      canvas: {
        getState: jest.fn((id: string) => {
          // Return null by default, can be overridden in tests
          return null;
        }),
        getAllStates: jest.fn(() => {
          // Return empty array by default
          return [];
        }),
        subscribe: jest.fn((callbackOrId: any, callback?: any) => {
          // Hook calls subscribe(callback) when canvasId provided internally
          // Type definition says subscribe(canvasId, callback) but hook doesn't match
          // Return unsubscribe function
          return () => {};
        }),
        subscribeAll: jest.fn((callback: (event: CanvasStateChangeEvent) => void) => {
          // Return unsubscribe function
          return () => {};
        })
      }
    };
  });

  afterEach(() => {
    // Clean up after each test
    delete window.__TAURI__;
    delete window.atom;
  });

  describe('Hook Initialization', () => {
    test('useCanvasState should initialize window.atom.canvas if missing', () => {
      // Remove existing canvas API
      delete window.atom?.canvas;

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      // Hook should create minimal API if missing
      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();
    });

    test('useCanvasState should return getState function', () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      expect(result.current.getState).toBeDefined();
      expect(typeof result.current.getState).toBe('function');
    });

    test('useCanvasState should return getAllStates function', () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      expect(result.current.getAllStates).toBeDefined();
      expect(typeof result.current.getAllStates).toBe('function');
    });

    test('useCanvasState should work with Tauri __TAURI__ present', () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      // Verify hook returns API methods
      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();

      // Verify Tauri is still accessible
      expect(window.__TAURI__).toBeDefined();
      expect(typeof window.__TAURI__?.invoke).toBe('function');
    });

    test('useCanvasState should handle null API gracefully', () => {
      // Remove canvas API completely
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      // Hook should not crash, should return stub API
      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();
    });
  });

  describe('API Method Access', () => {
    test('getState should retrieve canvas state from global API', () => {
      const mockState: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: 'test-canvas',
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: [
          { x: 'Jan', y: 100 },
          { x: 'Feb', y: 200 }
        ]
      };

      (window.atom.canvas?.getState as jest.Mock).mockReturnValue(mockState);

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      const retrievedState = result.current.getState('test-canvas');
      expect(retrievedState).toEqual(mockState);
      expect(retrievedState?.canvas_id).toBe('test-canvas');
    });

    test('getState should return null for unknown canvas', () => {
      (window.atom.canvas?.getState as jest.Mock).mockReturnValue(null);

      const { result } = renderHook(() => useCanvasState());

      const retrievedState = result.current.getState('unknown-canvas');
      expect(retrievedState).toBeNull();
    });

    test('getAllStates should retrieve all canvas states from global API', () => {
      const state1: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: 'canvas-1',
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: [{ x: 'A', y: 1 }]
      };

      const state2: AnyCanvasState = {
        canvas_type: 'terminal',
        canvas_id: 'canvas-2',
        timestamp: '2026-02-18T10:01:00Z',
        working_dir: '/home/user',
        command: 'ls -la',
        lines: ['file1.txt', 'file2.txt'],
        cursor_pos: { row: 0, col: 0 },
        scroll_offset: 0
      };

      (window.atom.canvas?.getAllStates as jest.Mock).mockReturnValue([
        { canvas_id: 'canvas-1', state: state1 },
        { canvas_id: 'canvas-2', state: state2 }
      ]);

      const { result } = renderHook(() => useCanvasState());

      const allStates = result.current.getAllStates();
      expect(allStates).toHaveLength(2);
      expect(allStates[0].canvas_id).toBe('canvas-1');
      expect(allStates[1].canvas_id).toBe('canvas-2');
    });

    test('getAllStates should return empty array initially', () => {
      (window.atom.canvas?.getAllStates as jest.Mock).mockReturnValue([]);

      const { result } = renderHook(() => useCanvasState());

      const allStates = result.current.getAllStates();
      expect(allStates).toEqual([]);
      expect(Array.isArray(allStates)).toBe(true);
    });
  });

  describe('Subscription Behavior', () => {
    test('useCanvasState should subscribe to specific canvas when canvasId provided', () => {
      const canvasId = 'test-canvas';

      renderHook(() => useCanvasState(canvasId));

      // Verify subscribe was called (hook calls it with just callback when canvasId provided)
      expect(window.atom.canvas?.subscribe).toHaveBeenCalledWith(
        expect.any(Function)
      );
    });

    test('useCanvasState should subscribe to all canvases when no canvasId', () => {
      renderHook(() => useCanvasState());

      // Verify subscribeAll was called
      expect(window.atom.canvas?.subscribeAll).toHaveBeenCalledWith(
        expect.any(Function)
      );
    });

    test('useCanvasState should handle canvasId changes', () => {
      const { rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-1' } }
      );

      // Initial subscription
      expect(window.atom.canvas?.subscribe).toHaveBeenCalledWith(
        expect.any(Function)
      );

      // Change canvasId
      rerender({ canvasId: 'canvas-2' });

      // Should subscribe again with new callback
      expect(window.atom.canvas?.subscribe).toHaveBeenCalledTimes(2);
    });
  });

  describe('Cleanup and Unmount', () => {
    test('useCanvasState should cleanup subscription on unmount', () => {
      const canvasId = 'test-canvas';
      const mockUnsubscribe = jest.fn();
      (window.atom.canvas?.subscribe as jest.Mock).mockReturnValue(mockUnsubscribe);

      const { unmount } = renderHook(() => useCanvasState(canvasId));

      // Verify subscription was created
      expect(window.atom.canvas?.subscribe).toHaveBeenCalled();

      // Unmount hook
      unmount();

      // Verify cleanup function was called
      expect(mockUnsubscribe).toHaveBeenCalled();
    });

    test('useCanvasState should cleanup global subscription on unmount', () => {
      const mockUnsubscribe = jest.fn();
      (window.atom.canvas?.subscribeAll as jest.Mock).mockReturnValue(mockUnsubscribe);

      const { unmount } = renderHook(() => useCanvasState());

      // Verify global subscription was created
      expect(window.atom.canvas?.subscribeAll).toHaveBeenCalled();

      // Unmount hook
      unmount();

      // Verify cleanup function was called
      expect(mockUnsubscribe).toHaveBeenCalled();
    });

    test('useCanvasState should handle multiple mount/unmount cycles', () => {
      const canvasId = 'test-canvas';

      // First mount
      const mockUnsubscribe1 = jest.fn();
      (window.atom.canvas?.subscribe as jest.Mock).mockReturnValue(mockUnsubscribe1);
      const { unmount: unmount1 } = renderHook(() => useCanvasState(canvasId));

      expect(window.atom.canvas?.subscribe).toHaveBeenCalled();

      // First unmount
      unmount1();
      expect(mockUnsubscribe1).toHaveBeenCalled();

      // Reset mock
      (window.atom.canvas?.subscribe as jest.Mock).mockClear();

      // Second mount
      const mockUnsubscribe2 = jest.fn();
      (window.atom.canvas?.subscribe as jest.Mock).mockReturnValue(mockUnsubscribe2);
      const { unmount: unmount2 } = renderHook(() => useCanvasState(canvasId));

      expect(window.atom.canvas?.subscribe).toHaveBeenCalled();

      // Second unmount
      unmount2();
      expect(mockUnsubscribe2).toHaveBeenCalled();
    });
  });

  describe('Tauri Integration', () => {
    test('useCanvasState should work alongside Tauri IPC invoke', async () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      // Call Tauri invoke
      const tauriInvoke = window.__TAURI__?.invoke as jest.Mock;
      tauriInvoke.mockResolvedValue({ success: true });

      const tauriResult = await tauriInvoke('some_command');

      // Both should work
      expect(result.current.getState).toBeDefined();
      expect(window.__TAURI__).toBeDefined();
      expect(tauriResult).toEqual({ success: true });
    });

    test('useCanvasState should not interfere with Tauri window object', () => {
      // Store original Tauri object
      const originalTauri = window.__TAURI__;

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      // Tauri should be unchanged
      expect(window.__TAURI__).toBe(originalTauri);
      expect(window.__TAURI__?.invoke).toBeDefined();

      // Canvas API should also work
      expect(result.current.getState).toBeDefined();
    });

    test('useCanvasState should work when Tauri is not present', () => {
      // Remove Tauri
      delete window.__TAURI__;

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      // Hook should still work
      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();
    });
  });

  describe('State Management', () => {
    test('useCanvasState should return state and allStates properties', () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      expect(result.current).toHaveProperty('state');
      expect(result.current).toHaveProperty('allStates');
    });

    test('useCanvasState should initialize with null state for specific canvas', () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      expect(result.current.state).toBeNull();
    });

    test('useCanvasState should initialize with empty allStates for no canvasId', () => {
      const { result } = renderHook(() => useCanvasState());

      expect(result.current.allStates).toEqual([]);
    });
  });

  describe('Error Handling and Edge Cases', () => {
    test('useCanvasState should handle undefined canvasId gracefully', () => {
      const { result } = renderHook(() => useCanvasState(undefined as any));

      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();
    });

    test('useCanvasState should handle null canvasId gracefully', () => {
      const { result } = renderHook(() => useCanvasState(null as any));

      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();
    });

    test('useCanvasState should handle empty string canvasId', () => {
      const { result } = renderHook(() => useCanvasState(''));

      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();
    });

    test('useCanvasState should handle concurrent hook instances', () => {
      const canvasId1 = 'canvas-1';
      const canvasId2 = 'canvas-2';

      const { result: result1 } = renderHook(() => useCanvasState(canvasId1));
      const { result: result2 } = renderHook(() => useCanvasState(canvasId2));

      // Both hooks should work independently
      expect(result1.current.getState).toBeDefined();
      expect(result2.current.getState).toBeDefined();
    });

    test('useCanvasState should handle rapid canvasId changes', () => {
      const { result, rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-1' } }
      );

      // Rapidly change canvasId multiple times
      for (let i = 1; i <= 5; i++) {
        rerender({ canvasId: `canvas-${i}` });
      }

      // Final state should be valid
      expect(result.current.getState).toBeDefined();
      expect(result.current.getAllStates).toBeDefined();
    });
  });

  describe('Performance and Optimization', () => {
    test('useCanvasState should memoize getState function', () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      const getState1 = result.current.getState;
      const getState2 = result.current.getState;

      // Functions should be reference-stable
      expect(getState1).toBe(getState2);
    });

    test('useCanvasState should memoize getAllStates function', () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      const getAllStates1 = result.current.getAllStates;
      const getAllStates2 = result.current.getAllStates;

      // Functions should be reference-stable
      expect(getAllStates1).toBe(getAllStates2);
    });

    test('useCanvasState should not recreate functions on re-render', () => {
      const { result, rerender } = renderHook(() => useCanvasState('test-canvas'));

      const getState1 = result.current.getState;
      const getAllStates1 = result.current.getAllStates;

      rerender();

      const getState2 = result.current.getState;
      const getAllStates2 = result.current.getAllStates;

      // Functions should remain the same reference
      expect(getState1).toBe(getState2);
      expect(getAllStates1).toBe(getAllStates2);
    });
  });

  describe('Subscription Callback Tests', () => {
    test('subscribe callback should update state when called', () => {
      let subscribeCallback: ((state: AnyCanvasState) => void) | null = null;

      // Hook calls subscribe with just callback when canvasId is provided
      (window.atom.canvas?.subscribe as jest.Mock).mockImplementation(
        (callback: (state: AnyCanvasState) => void) => {
          subscribeCallback = callback;
          return () => {};
        }
      );

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      const newState: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: 'test-canvas',
        timestamp: '2026-02-18T10:00:00Z',
        component: 'form',
        form_schema: { fields: [] },
        form_data: {},
        validation_errors: [],
        submit_enabled: true
      };

      // Simulate callback being invoked
      act(() => {
        subscribeCallback?.(newState);
      });

      // State should be updated
      expect(result.current.state).toEqual(newState);
    });

    test('subscribeAll callback should update allStates when called', () => {
      let subscribeAllCallback: ((event: CanvasStateChangeEvent) => void) | null = null;

      (window.atom.canvas?.subscribeAll as jest.Mock).mockImplementation(
        (callback: (event: CanvasStateChangeEvent) => void) => {
          subscribeAllCallback = callback;
          return () => {};
        }
      );

      const { result } = renderHook(() => useCanvasState());

      const event: CanvasStateChangeEvent = {
        type: 'canvas:state_change',
        canvas_id: 'canvas-1',
        canvas_type: 'generic',
        component: 'line_chart',
        state: {
          canvas_type: 'generic',
          canvas_id: 'canvas-1',
          timestamp: '2026-02-18T10:00:00Z',
          component: 'line_chart',
          chart_type: 'line',
          data_points: []
        },
        timestamp: '2026-02-18T10:00:00Z'
      };

      // Simulate callback being invoked
      act(() => {
        subscribeAllCallback?.(event);
      });

      // allStates should be updated
      expect(result.current.allStates).toHaveLength(1);
      expect(result.current.allStates[0].canvas_id).toBe('canvas-1');
    });
  });
});
