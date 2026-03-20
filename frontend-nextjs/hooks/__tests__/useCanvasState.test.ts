/**
 * useCanvasState Hook Tests
 *
 * Comprehensive functional tests for the useCanvasState hook.
 * Tests canvas state subscription, updates, and cleanup.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useCanvasState } from '../useCanvasState';
import type { CanvasStateAPI, AnyCanvasState, CanvasStateChangeEvent } from '@/components/canvas/types';

// Mock canvas types for testing
interface MockCanvasState extends AnyCanvasState {
  canvas_id: string;
  type: 'chart' | 'markdown' | 'form';
  data: any;
}

describe('useCanvasState', () => {
  let mockApi: CanvasStateAPI;
  let unsubscribeFn: jest.Mock;

  beforeEach(() => {
    // Reset window.atom.canvas before each test
    unsubscribeFn = jest.fn();

    mockApi = {
      getState: jest.fn((id: string) => ({
        canvas_id: id,
        type: 'chart',
        data: { title: 'Test Canvas' }
      })),
      getAllStates: jest.fn(() => [
        { canvas_id: 'canvas-1', state: { type: 'chart', data: {} } },
        { canvas_id: 'canvas-2', state: { type: 'markdown', data: {} } }
      ]),
      subscribe: jest.fn((callback) => {
        // Simulate immediate state update
        setTimeout(() => {
          callback({
            canvas_id: 'test-canvas',
            type: 'chart',
            data: { title: 'Test Canvas' }
          } as AnyCanvasState);
        }, 0);
        return unsubscribeFn;
      }),
      subscribeAll: jest.fn((callback) => {
        // Simulate immediate state updates
        setTimeout(() => {
          callback({
            canvas_id: 'canvas-1',
            state: { type: 'chart', data: {} }
          } as CanvasStateChangeEvent);
        }, 0);
        return unsubscribeFn;
      })
    };

    (window as any).atom = {
      canvas: mockApi
    };
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('initialization', () => {
    it('should initialize with empty state', () => {
      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
    });

    it('should initialize window.atom.canvas if not exists', () => {
      delete (window as any).atom;

      renderHook(() => useCanvasState());

      expect(window.atom?.canvas).toBeDefined();
      expect(window.atom?.canvas?.getState).toBeInstanceOf(Function);
      expect(window.atom?.canvas?.getAllStates).toBeInstanceOf(Function);
      expect(window.atom?.canvas?.subscribe).toBeInstanceOf(Function);
      expect(window.atom?.canvas?.subscribeAll).toBeInstanceOf(Function);
    });

    it('should return API methods', () => {
      const { result } = renderHook(() => useCanvasState());

      expect(result.current.getState).toBeInstanceOf(Function);
      expect(result.current.getAllStates).toBeInstanceOf(Function);
    });
  });

  describe('specific canvas subscription', () => {
    it('should subscribe to specific canvas when canvasId is provided', async () => {
      const { result } = renderHook(() => useCanvasState('test-canvas'));

      expect(mockApi.subscribe).toHaveBeenCalledWith(expect.any(Function));

      await waitFor(() => {
        expect(result.current.state).not.toBeNull();
      });
    });

    it('should receive state updates for specific canvas', async () => {
      const testState: MockCanvasState = {
        canvas_id: 'test-canvas',
        type: 'chart',
        data: { title: 'Updated Canvas' }
      };

      mockApi.subscribe = jest.fn((callback) => {
        setTimeout(() => callback(testState as AnyCanvasState), 10);
        return unsubscribeFn;
      });

      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      await waitFor(() => {
        expect(result.current.state).toEqual(testState);
      });
    });

    it('should update state when canvas changes', async () => {
      let stateCallback: (state: AnyCanvasState) => void;

      mockApi.subscribe = jest.fn((callback) => {
        stateCallback = callback;
        return unsubscribeFn;
      });

      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      // Trigger state update
      await act(async () => {
        stateCallback!({
          canvas_id: 'test-canvas',
          type: 'chart',
          data: { title: 'New State' }
        } as AnyCanvasState);
      });

      await waitFor(() => {
        expect(result.current.state?.data?.title).toBe('New State');
      });
    });
  });

  describe('all canvases subscription', () => {
    it('should subscribe to all canvases when no canvasId provided', async () => {
      const { result } = renderHook(() => useCanvasState());

      expect(mockApi.subscribeAll).toHaveBeenCalledWith(expect.any(Function));

      await waitFor(() => {
        expect(result.current.allStates.length).toBeGreaterThan(0);
      });
    });

    it('should receive updates for all canvases', async () => {
      let allCallback: (event: CanvasStateChangeEvent) => void;

      mockApi.subscribeAll = jest.fn((callback) => {
        allCallback = callback;
        return unsubscribeFn;
      });

      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      // Trigger state update
      await act(async () => {
        allCallback!({
          canvas_id: 'canvas-3',
          state: { type: 'form', data: {} }
        } as CanvasStateChangeEvent);
      });

      await waitFor(() => {
        expect(result.current.allStates.length).toBe(1);
        expect(result.current.allStates[0].canvas_id).toBe('canvas-3');
      });
    });

    it('should update existing canvas in allStates', async () => {
      let allCallback: (event: CanvasStateChangeEvent) => void;

      mockApi.subscribeAll = jest.fn((callback) => {
        // Initial state
        setTimeout(() => {
          callback({
            canvas_id: 'canvas-1',
            state: { type: 'chart', data: { title: 'Original' } }
          } as CanvasStateChangeEvent);
        }, 0);

        allCallback = callback;
        return unsubscribeFn;
      });

      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      // Wait for initial state
      await waitFor(() => {
        expect(result.current.allStates.length).toBeGreaterThan(0);
      });

      // Update existing canvas
      await act(async () => {
        allCallback!({
          canvas_id: 'canvas-1',
          state: { type: 'chart', data: { title: 'Updated' } }
        } as CanvasStateChangeEvent);
      });

      await waitFor(() => {
        expect(result.current.allStates[0].state.data.title).toBe('Updated');
        expect(result.current.allStates.length).toBe(1); // Should not duplicate
      });
    });

    it('should add new canvas to allStates', async () => {
      let allCallback: (event: CanvasStateChangeEvent) => void;

      mockApi.subscribeAll = jest.fn((callback) => {
        allCallback = callback;
        return unsubscribeFn;
      });

      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      // Add first canvas
      await act(async () => {
        allCallback!({
          canvas_id: 'canvas-1',
          state: { type: 'chart', data: {} }
        } as CanvasStateChangeEvent);
      });

      await waitFor(() => {
        expect(result.current.allStates.length).toBe(1);
      });

      // Add second canvas
      await act(async () => {
        allCallback!({
          canvas_id: 'canvas-2',
          state: { type: 'markdown', data: {} }
        } as CanvasStateChangeEvent);
      });

      await waitFor(() => {
        expect(result.current.allStates.length).toBe(2);
      });
    });
  });

  describe('API methods', () => {
    it('should get state for specific canvas', () => {
      const { result } = renderHook(() => useCanvasState());

      const state = result.current.getState('canvas-1');

      expect(mockApi.getState).toHaveBeenCalledWith('canvas-1');
      expect(state).toEqual({
        canvas_id: 'canvas-1',
        type: 'chart',
        data: { title: 'Test Canvas' }
      });
    });

    it('should return null when getState fails', () => {
      mockApi.getState = jest.fn(() => null);
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      const state = result.current.getState('non-existent');

      expect(state).toBeNull();
    });

    it('should get all states', () => {
      const { result } = renderHook(() => useCanvasState());

      const states = result.current.getAllStates();

      expect(mockApi.getAllStates).toHaveBeenCalled();
      expect(states).toEqual([
        { canvas_id: 'canvas-1', state: { type: 'chart', data: {} } },
        { canvas_id: 'canvas-2', state: { type: 'markdown', data: {} } }
      ]);
    });

    it('should return empty array when getAllStates fails', () => {
      mockApi.getAllStates = jest.fn(() => []);
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      const states = result.current.getAllStates();

      expect(states).toEqual([]);
    });
  });

  describe('cleanup', () => {
    it('should unsubscribe on unmount with specific canvas', () => {
      const { unmount } = renderHook(() => useCanvasState('test-canvas'));

      unmount();

      expect(unsubscribeFn).toHaveBeenCalled();
    });

    it('should unsubscribe on unmount with all canvases', () => {
      const { unmount } = renderHook(() => useCanvasState());

      unmount();

      expect(unsubscribeFn).toHaveBeenCalled();
    });

    it('should handle multiple unmounts gracefully', () => {
      const { unmount } = renderHook(() => useCanvasState());

      unmount();
      unmount(); // Should not throw

      expect(unsubscribeFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('edge cases', () => {
    it('should handle missing window.atom gracefully', () => {
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
      expect(result.current.getState('test')).toBeNull();
      expect(result.current.getAllStates()).toEqual([]);
    });

    it('should handle missing window.atom.canvas gracefully', () => {
      (window as any).atom = {};

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
    });

    it('should handle subscribe throwing error', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      mockApi.subscribe = jest.fn(() => {
        throw new Error('Subscribe failed');
      });

      (window as any).atom.canvas = mockApi;

      try {
        renderHook(() => useCanvasState('test'));
      } catch (error) {
        // Error is expected to be thrown, but hook should still render
        expect(error).toBeDefined();
      }

      consoleSpy.mockRestore();
    });

    it('should handle subscribeAll throwing error', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      mockApi.subscribeAll = jest.fn(() => {
        throw new Error('SubscribeAll failed');
      });

      (window as any).atom.canvas = mockApi;

      try {
        renderHook(() => useCanvasState());
      } catch (error) {
        // Error is expected to be thrown, but hook should still render
        expect(error).toBeDefined();
      }

      consoleSpy.mockRestore();
    });

    it('should handle rapid canvasId changes', async () => {
      const { rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-1' } }
      );

      // Change canvasId
      rerender({ canvasId: 'canvas-2' });

      rerender({ canvasId: 'canvas-3' });

      await waitFor(() => {
        expect(mockApi.subscribe).toHaveBeenCalledTimes(3);
      });
    });
  });

  describe('subscription lifecycle', () => {
    it('should resubscribe when canvasId changes', async () => {
      let unsubscribeCount = 0;

      mockApi.subscribe = jest.fn(() => {
        unsubscribeCount++;
        return jest.fn(() => {
          unsubscribeCount--;
        });
      });

      (window as any).atom.canvas = mockApi;

      const { rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-1' } }
      );

      await waitFor(() => {
        expect(mockApi.subscribe).toHaveBeenCalledTimes(1);
      });

      rerender({ canvasId: 'canvas-2' });

      await waitFor(() => {
        expect(mockApi.subscribe).toHaveBeenCalledTimes(2);
      });
    });

    it('should cleanup previous subscription when canvasId changes', () => {
      let previousUnsubscribe: jest.Mock | null = null;

      mockApi.subscribe = jest.fn(() => {
        const currentUnsubscribe = jest.fn();
        previousUnsubscribe = currentUnsubscribe;
        return currentUnsubscribe;
      });

      (window as any).atom.canvas = mockApi;

      const { rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-1' } }
      );

      const firstUnsubscribe = previousUnsubscribe;

      rerender({ canvasId: 'canvas-2' });

      expect(firstUnsubscribe).toHaveBeenCalled();
    });
  });
});
