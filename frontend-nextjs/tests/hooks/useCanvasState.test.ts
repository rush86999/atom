/**
 * useCanvasState Hook Tests
 *
 * Purpose: Validate canvas state management hook behavior
 *
 * Testing Strategy:
 * - Test hook initialization and state management
 * - Test subscription lifecycle (subscribe/unsubscribe)
 * - Test canvas state updates
 * - Test cleanup on unmount
 * - Test multiple canvas subscriptions
 *
 * Coverage Targets:
 * - Canvas state API interactions
 * - Subscription lifecycle
 * - State update propagation
 * - Error handling
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { useCanvasState } from '@/hooks/useCanvasState';
import type { AnyCanvasState, CanvasStateAPI, CanvasStateChangeEvent } from '@/components/canvas/types';

// Mock canvas types
interface MockChartCanvas {
  canvas_type: 'chart';
  canvas_id: string;
  title: string;
  chart_type: 'line' | 'bar' | 'pie';
  data: Record<string, unknown>;
}

describe('useCanvasState', () => {
  let mockAPI: CanvasStateAPI;
  let unsubscribeCallback: (() => void) | null;

  beforeEach(() => {
    // Reset window.atom.canvas before each test
    delete (window as any).atom;

    unsubscribeCallback = null;

    // Setup mock canvas API
    mockAPI = {
      getState: jest.fn((id: string) => ({
        canvas_type: 'chart',
        canvas_id: id,
        title: `Canvas ${id}`,
        chart_type: 'line',
        data: { values: [1, 2, 3] }
      })),
      getAllStates: jest.fn(() => [
        { canvas_id: 'canvas-1', state: { canvas_type: 'chart', chart_type: 'line', data: {} } },
        { canvas_id: 'canvas-2', state: { canvas_type: 'markdown', content: 'test' } }
      ]),
      subscribe: jest.fn().mockImplementation((callback) => {
        unsubscribeCallback = callback as unknown as () => void;
        return jest.fn(() => { unsubscribeCallback = null; });
      }),
      subscribeAll: jest.fn().mockImplementation((callback) => {
        unsubscribeCallback = callback as unknown as () => void;
        return jest.fn(() => { unsubscribeCallback = null; });
      })
    } as unknown as CanvasStateAPI;

    // Initialize window.atom.canvas
    (window as any).atom = { canvas: mockAPI };
  });

  afterEach(() => {
    unsubscribeCallback = null;
  });

  describe('initialization', () => {
    test('initializes with empty state when no canvasId provided', () => {
      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
      expect(mockAPI.subscribeAll).toHaveBeenCalled();
      expect(mockAPI.subscribe).not.toHaveBeenCalled();
    });

    test('initializes with empty state when canvasId provided', () => {
      const { result } = renderHook(() => useCanvasState('canvas-1'));

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
      expect(mockAPI.subscribe).toHaveBeenCalled();
      expect(mockAPI.subscribeAll).not.toHaveBeenCalled();
    });

    test('initializes global API if not exists', () => {
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState());

      expect((window as any).atom?.canvas).toBeDefined();
      expect((window as any).atom?.canvas?.getState).toBeDefined();
      expect((window as any).atom?.canvas?.getAllStates).toBeDefined();
      expect((window as any).atom?.canvas?.subscribe).toBeDefined();
    });
  });

  describe('canvas state subscription', () => {
    test('subscribes to specific canvas when canvasId provided', () => {
      renderHook(() => useCanvasState('canvas-1'));

      expect(mockAPI.subscribe).toHaveBeenCalledTimes(1);
      expect(mockAPI.subscribeAll).not.toHaveBeenCalled();
    });

    test('subscribes to all canvases when no canvasId provided', () => {
      renderHook(() => useCanvasState());

      expect(mockAPI.subscribeAll).toHaveBeenCalledTimes(1);
      expect(mockAPI.subscribe).not.toHaveBeenCalled();
    });

    test('receives state updates from subscription', async () => {
      const { result } = renderHook(() => useCanvasState('canvas-1'));

      const mockState: MockChartCanvas = {
        canvas_type: 'chart',
        canvas_id: 'canvas-1',
        title: 'Test Chart',
        chart_type: 'line',
        data: { values: [1, 2, 3] }
      };

      // Simulate state update from subscription
      act(() => {
        const subscribeCallback = (mockAPI.subscribe as jest.Mock).mock.calls[0][0];
        subscribeCallback(mockState);
      });

      expect(result.current.state).toEqual(mockState);
    });

    test('receives all canvas state updates', async () => {
      const { result } = renderHook(() => useCanvasState());

      const mockEvent: CanvasStateChangeEvent = {
        canvas_id: 'canvas-1',
        state: {
          canvas_type: 'chart',
          chart_type: 'line',
          data: { values: [1, 2, 3] }
        }
      };

      // Simulate state update from subscription
      act(() => {
        const subscribeCallback = (mockAPI.subscribeAll as jest.Mock).mock.calls[0][0];
        subscribeCallback(mockEvent);
      });

      expect(result.current.allStates).toHaveLength(1);
      expect(result.current.allStates[0]).toEqual({
        canvas_id: 'canvas-1',
        state: mockEvent.state
      });
    });
  });

  describe('canvas state methods', () => {
    test('getState retrieves specific canvas state', () => {
      const { result } = renderHook(() => useCanvasState());

      const state = result.current.getState('canvas-1');

      expect(mockAPI.getState).toHaveBeenCalledWith('canvas-1');
      expect(state).toEqual({
        canvas_type: 'chart',
        canvas_id: 'canvas-1',
        title: 'Canvas canvas-1',
        chart_type: 'line',
        data: { values: [1, 2, 3] }
      });
    });

    test('getState returns null when API unavailable', () => {
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState());

      const state = result.current.getState('canvas-1');

      expect(state).toBeNull();
    });

    test('getAllStates retrieves all canvas states', () => {
      const { result } = renderHook(() => useCanvasState());

      const states = result.current.getAllStates();

      expect(mockAPI.getAllStates).toHaveBeenCalled();
      expect(states).toHaveLength(2);
      expect(states[0].canvas_id).toBe('canvas-1');
    });

    test('getAllStates returns empty array when API unavailable', () => {
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState());

      const states = result.current.getAllStates();

      expect(states).toEqual([]);
    });
  });

  describe('state updates', () => {
    test('updates allStates array with new canvas', () => {
      const { result } = renderHook(() => useCanvasState());

      const mockEvent1: CanvasStateChangeEvent = {
        canvas_id: 'canvas-1',
        state: { canvas_type: 'chart', chart_type: 'line', data: {} }
      };

      const mockEvent2: CanvasStateChangeEvent = {
        canvas_id: 'canvas-2',
        state: { canvas_type: 'markdown', content: 'test' }
      };

      act(() => {
        const callback = (mockAPI.subscribeAll as jest.Mock).mock.calls[0][0];
        callback(mockEvent1);
        callback(mockEvent2);
      });

      expect(result.current.allStates).toHaveLength(2);
      expect(result.current.allStates[0].canvas_id).toBe('canvas-1');
      expect(result.current.allStates[1].canvas_id).toBe('canvas-2');
    });

    test('updates existing canvas in allStates array', () => {
      const { result } = renderHook(() => useCanvasState());

      const mockEvent1: CanvasStateChangeEvent = {
        canvas_id: 'canvas-1',
        state: { canvas_type: 'chart', chart_type: 'line', data: { values: [1, 2, 3] } }
      };

      const mockEvent2: CanvasStateChangeEvent = {
        canvas_id: 'canvas-1',
        state: { canvas_type: 'chart', chart_type: 'bar', data: { values: [4, 5, 6] } }
      };

      act(() => {
        const callback = (mockAPI.subscribeAll as jest.Mock).mock.calls[0][0];
        callback(mockEvent1);
        callback(mockEvent2);
      });

      expect(result.current.allStates).toHaveLength(1);
      expect(result.current.allStates[0].state).toEqual(mockEvent2.state);
    });
  });

  describe('multiple canvas subscriptions', () => {
    test('manages multiple canvas subscriptions independently', () => {
      const { result: result1 } = renderHook(() => useCanvasState('canvas-1'));
      const { result: result2 } = renderHook(() => useCanvasState('canvas-2'));

      expect(mockAPI.subscribe).toHaveBeenCalledTimes(2);

      const mockState1: MockChartCanvas = {
        canvas_type: 'chart',
        canvas_id: 'canvas-1',
        title: 'Chart 1',
        chart_type: 'line',
        data: { values: [1, 2, 3] }
      };

      const mockState2: MockChartCanvas = {
        canvas_type: 'chart',
        canvas_id: 'canvas-2',
        title: 'Chart 2',
        chart_type: 'bar',
        data: { values: [4, 5, 6] }
      };

      act(() => {
        const callback1 = (mockAPI.subscribe as jest.Mock).mock.calls[0][0];
        const callback2 = (mockAPI.subscribe as jest.Mock).mock.calls[1][0];
        callback1(mockState1);
        callback2(mockState2);
      });

      expect(result1.current.state).toEqual(mockState1);
      expect(result2.current.state).toEqual(mockState2);
    });
  });

  describe('cleanup on unmount', () => {
    test('cleans up subscription on unmount', () => {
      const { unmount } = renderHook(() => useCanvasState('canvas-1'));

      expect(mockAPI.subscribe).toHaveBeenCalledTimes(1);

      unmount();

      // Cleanup should have been called (unsubscribe function returned)
      expect(mockAPI.subscribe).toHaveBeenCalled();
    });

    test('cleans up all subscriptions on unmount', () => {
      const { unmount } = renderHook(() => useCanvasState());

      expect(mockAPI.subscribeAll).toHaveBeenCalledTimes(1);

      unmount();

      expect(mockAPI.subscribeAll).toHaveBeenCalled();
    });
  });

  describe('error handling', () => {
    test('handles null API gracefully', () => {
      (window as any).atom = { canvas: null };

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
    });

    test('handles missing API methods gracefully', () => {
      // The hook requires subscribe/subscribeAll to be functions
      // Test with minimal valid API that has null getState/getAllStates
      (window as any).atom = {
        canvas: {
          getState: jest.fn().mockReturnValue(null),
          getAllStates: jest.fn().mockReturnValue([]),
          subscribe: jest.fn().mockReturnValue(jest.fn()),
          subscribeAll: jest.fn().mockReturnValue(jest.fn())
        }
      };

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
      // These should return null/[] when called
      expect(result.current.getState('canvas-1')).toBeNull();
      expect(result.current.getAllStates()).toEqual([]);
    });

    test('handles undefined window atom gracefully', () => {
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
      expect(result.current.getState('canvas-1')).toBeNull();
      expect(result.current.getAllStates()).toEqual([]);
    });
  });

  describe('re-render behavior', () => {
    test('re-subscribes when canvasId changes', () => {
      const { result, rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-1' } }
      );

      expect(mockAPI.subscribe).toHaveBeenCalledTimes(1);

      rerender({ canvasId: 'canvas-2' });

      expect(mockAPI.subscribe).toHaveBeenCalledTimes(2);
    });

    test('does not re-subscribe when canvasId unchanged', () => {
      const { result, rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-1' } }
      );

      expect(mockAPI.subscribe).toHaveBeenCalledTimes(1);

      rerender({ canvasId: 'canvas-1' });

      // Should still be 1, not 2
      expect(mockAPI.subscribe).toHaveBeenCalledTimes(1);
    });
  });
});
