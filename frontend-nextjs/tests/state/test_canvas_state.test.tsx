import { renderHook, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { useCanvasState } from '@/hooks/useCanvasState';

// Mock window.atom.canvas API
const mockCanvasAPI = {
  getState: jest.fn(),
  getAllStates: jest.fn(),
  subscribe: jest.fn(),
  subscribeAll: jest.fn(),
};

describe('useCanvasState Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (window as any).atom = { canvas: mockCanvasAPI };
  });

  afterEach(() => {
    delete (window as any).atom;
  });

  describe('test_canvas_initial_state', () => {
    it('should initialize with null state', () => {
      mockCanvasAPI.getState.mockReturnValue(null);

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
    });

    it('should initialize with empty allStates array', () => {
      mockCanvasAPI.getAllStates.mockReturnValue([]);

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.allStates).toEqual([]);
    });

    it('should create global API if not exists', () => {
      delete (window as any).atom;

      renderHook(() => useCanvasState());

      expect((window as any).atom?.canvas).toBeDefined();
      expect((window as any).atom?.canvas?.getState).toBeDefined();
      expect((window as any).atom?.canvas?.getAllStates).toBeDefined();
    });
  });

  describe('test_canvas_update', () => {
    it('should update state when subscription callback fires', () => {
      let subscribeCallback: (state: any) => void;
      mockCanvasAPI.subscribe.mockImplementation((callback) => {
        subscribeCallback = callback;
        return () => {};
      });

      const { result } = renderHook(() => useCanvasState('canvas-123'));

      const newState = { type: 'chart', data: { title: 'Test Chart' } };

      act(() => {
        subscribeCallback!(newState);
      });

      expect(result.current.state).toEqual(newState);
    });

    it('should update allStates when subscribeAll callback fires', () => {
      let subscribeAllCallback: (event: any) => void;
      mockCanvasAPI.subscribeAll.mockImplementation((callback) => {
        subscribeAllCallback = callback;
        return () => {};
      });

      const { result } = renderHook(() => useCanvasState());

      const newEvent = {
        canvas_id: 'canvas-456',
        state: { type: 'form', data: { fields: [] } },
      };

      act(() => {
        subscribeAllCallback!(newEvent);
      });

      expect(result.current.allStates).toHaveLength(1);
      expect(result.current.allStates[0]).toEqual(newEvent);
    });

    it('should update existing canvas in allStates', () => {
      let subscribeAllCallback: (event: any) => void;
      mockCanvasAPI.subscribeAll.mockImplementation((callback) => {
        subscribeAllCallback = callback;
        return () => {};
      });

      const { result } = renderHook(() => useCanvasState());

      const event1 = {
        canvas_id: 'canvas-789',
        state: { type: 'chart', version: 1 },
      };

      act(() => {
        subscribeAllCallback!(event1);
      });

      const event2 = {
        canvas_id: 'canvas-789',
        state: { type: 'chart', version: 2 },
      };

      act(() => {
        subscribeAllCallback!(event2);
      });

      expect(result.current.allStates).toHaveLength(1);
      expect(result.current.allStates[0].state).toEqual({ type: 'chart', version: 2 });
    });
  });

  describe('test_canvas_reset', () => {
    it('should reset state to null on unmount', () => {
      const unsubscribe = jest.fn();
      mockCanvasAPI.subscribe.mockReturnValue(unsubscribe);

      const { result, unmount } = renderHook(() => useCanvasState('canvas-abc'));

      unmount();

      expect(unsubscribe).toHaveBeenCalledTimes(1);
    });

    it('should call unsubscribe on unmount', () => {
      const unsubscribe = jest.fn();
      mockCanvasAPI.subscribeAll.mockReturnValue(unsubscribe);

      const { unmount } = renderHook(() => useCanvasState());

      unmount();

      expect(unsubscribe).toHaveBeenCalledTimes(1);
    });

    it('should handle multiple subscriptions correctly', () => {
      const unsubscribe1 = jest.fn();
      const unsubscribe2 = jest.fn();

      mockCanvasAPI.subscribe
        .mockReturnValueOnce(unsubscribe1)
        .mockReturnValueOnce(unsubscribe2);

      const { unmount: unmount1 } = renderHook(() => useCanvasState('canvas-1'));
      const { unmount: unmount2 } = renderHook(() => useCanvasState('canvas-2'));

      unmount1();
      expect(unsubscribe1).toHaveBeenCalledTimes(1);

      unmount2();
      expect(unsubscribe2).toHaveBeenCalledTimes(1);
    });
  });

  describe('test_canvas_subscribe', () => {
    it('should subscribe to specific canvas when canvasId provided', () => {
      mockCanvasAPI.subscribe.mockReturnValue(() => {});

      renderHook(() => useCanvasState('canvas-specific'));

      expect(mockCanvasAPI.subscribe).toHaveBeenCalledWith(expect.any(Function));
      expect(mockCanvasAPI.subscribeAll).not.toHaveBeenCalled();
    });

    it('should subscribe to all canvases when no canvasId provided', () => {
      mockCanvasAPI.subscribeAll.mockReturnValue(() => {});

      renderHook(() => useCanvasState());

      expect(mockCanvasAPI.subscribeAll).toHaveBeenCalledWith(expect.any(Function));
      expect(mockCanvasAPI.subscribe).not.toHaveBeenCalled();
    });

    it('should call subscription callback on state changes', () => {
      let subscribeCallback: (state: any) => void;
      mockCanvasAPI.subscribe.mockImplementation((callback) => {
        subscribeCallback = callback;
        return () => {};
      });

      const { result } = renderHook(() => useCanvasState('canvas-123'));

      const mockStates = [
        { type: 'chart', data: { value: 1 } },
        { type: 'form', data: { fields: [] } },
        { type: 'sheet', data: { rows: [] } },
      ];

      mockStates.forEach((state, index) => {
        act(() => {
          subscribeCallback!(state);
        });

        expect(result.current.state).toEqual(state);
      });
    });

    it('should handle rapid state updates', () => {
      let subscribeCallback: (state: any) => void;
      mockCanvasAPI.subscribe.mockImplementation((callback) => {
        subscribeCallback = callback;
        return () => {};
      });

      const { result } = renderHook(() => useCanvasState('canvas-rapid'));

      act(() => {
        for (let i = 0; i < 10; i++) {
          subscribeCallback!({ type: 'chart', data: { iteration: i } });
        }
      });

      expect(result.current.state).toEqual({
        type: 'chart',
        data: { iteration: 9 },
      });
    });
  });

  describe('test_canvas_get_state', () => {
    it('should retrieve state for specific canvas ID', () => {
      const mockState = { type: 'chart', title: 'Test' };
      mockCanvasAPI.getState.mockReturnValue(mockState);

      const { result } = renderHook(() => useCanvasState());

      const retrievedState = result.current.getState('canvas-target');

      expect(retrievedState).toEqual(mockState);
      expect(mockCanvasAPI.getState).toHaveBeenCalledWith('canvas-target');
    });

    it('should return null for non-existent canvas', () => {
      mockCanvasAPI.getState.mockReturnValue(null);

      const { result } = renderHook(() => useCanvasState());

      const retrievedState = result.current.getState('non-existent');

      expect(retrievedState).toBeNull();
    });

    it('should retrieve all states when calling getAllStates', () => {
      const mockAllStates = [
        { canvas_id: 'canvas-1', state: { type: 'chart' } },
        { canvas_id: 'canvas-2', state: { type: 'form' } },
        { canvas_id: 'canvas-3', state: { type: 'sheet' } },
      ];

      mockCanvasAPI.getAllStates.mockReturnValue(mockAllStates);

      const { result } = renderHook(() => useCanvasState());

      const allStates = result.current.getAllStates();

      expect(allStates).toEqual(mockAllStates);
      expect(mockCanvasAPI.getAllStates).toHaveBeenCalled();
    });

    it('should handle empty getAllStates result', () => {
      mockCanvasAPI.getAllStates.mockReturnValue([]);

      const { result } = renderHook(() => useCanvasState());

      const allStates = result.current.getAllStates();

      expect(allStates).toEqual([]);
    });

    it('should provide stable function references', () => {
      mockCanvasAPI.getState.mockReturnValue(null);
      mockCanvasAPI.getAllStates.mockReturnValue([]);

      const { result, rerender } = renderHook(() => useCanvasState());

      const getStateFn1 = result.current.getState;
      const getAllStatesFn1 = result.current.getAllStates;

      rerender();

      const getStateFn2 = result.current.getState;
      const getAllStatesFn2 = result.current.getAllStates;

      expect(getStateFn1).toBe(getStateFn2);
      expect(getAllStatesFn1).toBe(getAllStatesFn2);
    });

    it('should handle missing API gracefully', () => {
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState());

      const retrievedState = result.current.getState('any-canvas');
      const allStates = result.current.getAllStates();

      expect(retrievedState).toBeNull();
      expect(allStates).toEqual([]);
    });
  });

  describe('test_canvas_state_edge_cases', () => {
    it('should handle undefined canvasId parameter', () => {
      mockCanvasAPI.subscribeAll.mockReturnValue(() => {});

      const { result } = renderHook(() => useCanvasState(undefined));

      expect(mockCanvasAPI.subscribeAll).toHaveBeenCalled();
    });

    it('should handle null canvasId parameter', () => {
      mockCanvasAPI.subscribeAll.mockReturnValue(() => {});

      const { result } = renderHook(() => useCanvasState(null as any));

      expect(mockCanvasAPI.subscribeAll).toHaveBeenCalled();
    });

    it('should handle canvasId changes', () => {
      const unsubscribe1 = jest.fn();
      const unsubscribe2 = jest.fn();

      mockCanvasAPI.subscribe
        .mockReturnValueOnce(unsubscribe1)
        .mockReturnValueOnce(unsubscribe2);

      const { rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-1' } as any }
      );

      rerender({ canvasId: 'canvas-2' });

      expect(unsubscribe1).toHaveBeenCalledTimes(1);
      expect(mockCanvasAPI.subscribe).toHaveBeenCalledTimes(2);
    });

    it('should handle subscription errors gracefully', () => {
      mockCanvasAPI.subscribe.mockImplementation(() => {
        throw new Error('Subscription failed');
      });

      expect(() => {
        renderHook(() => useCanvasState('canvas-error'));
      }).not.toThrow();
    });
  });
});
