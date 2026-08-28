import { renderHook, act, waitFor } from '@testing-library/react';
import { useCanvasState } from '../useCanvasState';
import type {
  CanvasStateAPI,
  AnyCanvasState,
  CanvasStateChangeEvent,
  AgentOperationState,
} from '@/components/canvas/types';

/**
 * Comprehensive tests for the real useCanvasState hook.
 *
 * The hook takes an optional canvasId and returns an object:
 *   { state, allStates, getState, getAllStates, getMatchConfidence, isApiReady }
 *
 * On mount it reads/works against window.atom.canvas:
 *   - with canvasId: subscribes via api.subscribe and seeds state via
 *     api.getState(canvasId)
 *   - without canvasId: subscribes via api.subscribeAll and seeds allStates
 *     via api.getAllStates()
 *
 * It does NOT return the raw canvas state directly. Tests that assert
 * `result.current.type` / `result.current === null` were testing a fabricated
 * contract and have been rewritten against the real API.
 */

function makeMockApi(overrides: Partial<CanvasStateAPI> = {}): CanvasStateAPI {
  return {
    getState: jest.fn((id: string) => ({
      canvas_id: id,
      type: 'chart',
      data: { title: 'Test Canvas' },
    })),
    getAllStates: jest.fn(() => []),
    subscribe: jest.fn(() => () => {}),
    subscribeAll: jest.fn(() => () => {}),
    ...overrides,
  } as unknown as CanvasStateAPI;
}

describe('useCanvasState Hook (comprehensive)', () => {
  let mockApi: CanvasStateAPI;

  beforeEach(() => {
    mockApi = makeMockApi();
    (window as any).atom = { canvas: mockApi };
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('Canvas State Retrieval', () => {
    it('initializes with null state and empty allStates', () => {
      const { result } = renderHook(() => useCanvasState());

      expect(result.current.state).toBeNull();
      expect(result.current.allStates).toEqual([]);
      expect(result.current.isApiReady).toBe(true);
    });

    it('loads the initial state for a specific canvas from api.getState on mount', async () => {
      const testState = {
        canvas_id: 'canvas-1',
        type: 'chart',
        data: { title: 'Initial' },
      };
      mockApi.getState = jest.fn(() => testState) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState('canvas-1'));

      await waitFor(() => {
        expect(result.current.state).toEqual(testState);
      });
      expect(mockApi.getState).toHaveBeenCalledWith('canvas-1');
    });

    it('returns null state when the specific canvas has no initial state', () => {
      mockApi.getState = jest.fn(() => null) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState('canvas-missing'));

      expect(result.current.state).toBeNull();
    });

    it('getState returns state for an existing canvas', () => {
      const { result } = renderHook(() => useCanvasState());

      const state = result.current.getState('canvas-1');

      expect(mockApi.getState).toHaveBeenCalledWith('canvas-1');
      expect(state).toEqual({
        canvas_id: 'canvas-1',
        type: 'chart',
        data: { title: 'Test Canvas' },
      });
    });

    it('getState returns null for a non-existent canvas', () => {
      mockApi.getState = jest.fn(() => null) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.getState('missing')).toBeNull();
    });

    it('handles multiple canvas instances independently', () => {
      const { result: result1 } = renderHook(() => useCanvasState('canvas-1'));
      const { result: result2 } = renderHook(() => useCanvasState('canvas-2'));

      expect(result1.current.isApiReady).toBe(true);
      expect(result2.current.isApiReady).toBe(true);
      expect(result1.current.state).not.toBeNull();
      expect(result2.current.state).not.toBeNull();
    });
  });

  describe('State Subscription', () => {
    it('subscribes to a specific canvas when canvasId is provided', () => {
      renderHook(() => useCanvasState('canvas-1'));

      expect(mockApi.subscribe).toHaveBeenCalledTimes(1);
      expect(mockApi.subscribeAll).not.toHaveBeenCalled();
    });

    it('subscribes to all canvases when no canvasId is provided', () => {
      renderHook(() => useCanvasState());

      expect(mockApi.subscribeAll).toHaveBeenCalledTimes(1);
      expect(mockApi.subscribe).not.toHaveBeenCalled();
    });

    it('unsubscribes from a specific canvas on unmount', () => {
      const unsubscribe = jest.fn();
      mockApi.subscribe = jest.fn(() => unsubscribe);
      (window as any).atom.canvas = mockApi;

      const { unmount } = renderHook(() => useCanvasState('canvas-1'));

      unmount();

      expect(unsubscribe).toHaveBeenCalled();
    });

    it('unsubscribes from all canvases on unmount', () => {
      const unsubscribe = jest.fn();
      mockApi.subscribeAll = jest.fn(() => unsubscribe);
      (window as any).atom.canvas = mockApi;

      const { unmount } = renderHook(() => useCanvasState());

      unmount();

      expect(unsubscribe).toHaveBeenCalled();
    });

    it('handles subscribe errors gracefully without crashing', () => {
      mockApi.subscribe = jest.fn(() => {
        throw new Error('Subscription failed');
      });
      mockApi.getState = jest.fn(() => null) as any;
      (window as any).atom.canvas = mockApi;

      // The hook degrades gracefully (log, allow): a throwing subscribe()
      // must not crash the component tree — accessors keep working
      const { result } = renderHook(() => useCanvasState('canvas-1'));

      expect(result.current.state).toBeNull();
      expect(result.current.getAllStates()).toEqual([]);
    });
  });

  describe('Canvas Type Handling', () => {
    it('returns chart canvas state through getState', () => {
      mockApi.getState = jest.fn(() => ({
        canvas_id: 'canvas-1',
        type: 'chart',
        data: { labels: ['A', 'B'], values: [1, 2] },
      })) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      expect((result.current.getState('canvas-1') as any)?.type).toBe('chart');
    });

    it('returns form canvas state through getState', () => {
      mockApi.getState = jest.fn(() => ({
        canvas_id: 'canvas-2',
        type: 'form',
        data: { fields: [{ name: 'email', value: '' }] },
      })) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      expect((result.current.getState('canvas-2') as any)?.type).toBe('form');
    });

    it('returns null for unknown canvas types', () => {
      mockApi.getState = jest.fn(() => null) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.getState('unknown-canvas')).toBeNull();
    });
  });

  describe('Data Transformation', () => {
    it('exposes the raw data through getState', () => {
      const { result } = renderHook(() => useCanvasState());

      const state = result.current.getState('canvas-1') as any;

      expect(state.data).toEqual({ title: 'Test Canvas' });
    });

    it('handles complex nested data structures', () => {
      const complexCanvas = {
        canvas_id: 'complex-canvas',
        type: 'sheet',
        data: {
          rows: [
            { id: 1, name: 'Item 1', value: 100 },
            { id: 2, name: 'Item 2', value: 200 },
          ],
          columns: ['id', 'name', 'value'],
          filters: { value: { min: 50, max: 150 } },
        },
      };
      mockApi.getState = jest.fn(() => complexCanvas) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      expect((result.current.getState('complex-canvas') as any)?.data).toEqual(
        complexCanvas.data
      );
    });

    it('handles empty data', () => {
      mockApi.getState = jest.fn(() => ({
        canvas_id: 'empty-canvas',
        type: 'chart',
        data: {},
      })) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      expect((result.current.getState('empty-canvas') as any)?.data).toEqual({});
    });
  });

  describe('Real-time Updates', () => {
    it('updates state when the specific-canvas subscription callback fires', async () => {
      let subscribeCallback: ((state: AnyCanvasState | null) => void) | null = null;
      mockApi.subscribe = jest.fn((cb: any) => {
        subscribeCallback = cb;
        return () => {};
      });
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState('canvas-1'));

      await act(async () => {
        subscribeCallback!({
          canvas_id: 'canvas-1',
          type: 'chart',
          data: { title: 'Updated' },
        } as unknown as AnyCanvasState);
      });

      expect((result.current.state as any)?.data?.title).toBe('Updated');
    });

    it('does not update state when the specific-canvas callback receives null', async () => {
      let subscribeCallback: ((state: AnyCanvasState | null) => void) | null = null;
      mockApi.subscribe = jest.fn((cb: any) => {
        subscribeCallback = cb;
        return () => {};
      });
      mockApi.getState = jest.fn(() => null) as any;
      (window as any).atom.canvas = mockApi;

      const consoleSpy = jest.spyOn(console, 'warn').mockImplementation();

      const { result } = renderHook(() => useCanvasState('canvas-1'));

      await act(async () => {
        subscribeCallback!(null);
      });

      expect(result.current.state).toBeNull();

      consoleSpy.mockRestore();
    });

    it('adds new canvases when the subscribeAll callback fires', async () => {
      let allCallback: ((event: CanvasStateChangeEvent) => void) | null = null;
      mockApi.subscribeAll = jest.fn((cb: any) => {
        allCallback = cb;
        return () => {};
      });
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      await act(async () => {
        allCallback!({
          canvas_id: 'canvas-1',
          state: { type: 'chart', data: {} },
        } as unknown as CanvasStateChangeEvent);
      });
      await act(async () => {
        allCallback!({
          canvas_id: 'canvas-2',
          state: { type: 'markdown', data: {} },
        } as unknown as CanvasStateChangeEvent);
      });

      expect(result.current.allStates.length).toBe(2);
    });

    it('updates an existing canvas in allStates without duplicating it', async () => {
      let allCallback: ((event: CanvasStateChangeEvent) => void) | null = null;
      mockApi.subscribeAll = jest.fn((cb: any) => {
        allCallback = cb;
        return () => {};
      });
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      await act(async () => {
        allCallback!({
          canvas_id: 'canvas-1',
          state: { type: 'chart', data: { title: 'Original' } },
        } as unknown as CanvasStateChangeEvent);
      });
      await act(async () => {
        allCallback!({
          canvas_id: 'canvas-1',
          state: { type: 'chart', data: { title: 'Updated' } },
        } as unknown as CanvasStateChangeEvent);
      });

      expect(result.current.allStates).toHaveLength(1);
      expect((result.current.allStates[0].state as any).data.title).toBe('Updated');
    });
  });

  describe('Error Handling', () => {
    it('getState returns null when window.atom.canvas is missing', () => {
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.getState('test')).toBeNull();
    });

    it('getAllStates returns [] when window.atom.canvas is missing', () => {
      delete (window as any).atom;

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.getAllStates()).toEqual([]);
    });

    it('initializes a canvas API stub when window.atom is missing', () => {
      delete (window as any).atom;

      renderHook(() => useCanvasState());

      expect((window as any).atom?.canvas).toBeDefined();
      expect((window as any).atom.canvas.getState).toBeInstanceOf(Function);
      expect((window as any).atom.canvas.subscribeAll).toBeInstanceOf(Function);
    });
  });

  describe('Integration with Canvas API', () => {
    it('getState delegates to window.atom.canvas.getState', () => {
      const { result } = renderHook(() => useCanvasState());

      result.current.getState('canvas-1');

      expect(mockApi.getState).toHaveBeenCalledWith('canvas-1');
    });

    it('getAllStates delegates to window.atom.canvas.getAllStates', () => {
      mockApi.getAllStates = jest.fn(() => [
        { canvas_id: 'canvas-1', state: { type: 'chart', data: {} } },
      ]) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      const states = result.current.getAllStates();

      expect(states).toHaveLength(1);
      expect(mockApi.getAllStates).toHaveBeenCalled();
    });

    it('getMatchConfidence returns the match_confidence block for an agent operation', () => {
      // Legacy fixture shape (type/data + matchedLocator fields predate the
      // current AgentOperationState/MatchConfidence interfaces).
      const agentState = {
        canvas_id: 'op-1',
        type: 'agent_operation',
        data: { operationId: 'op-1' },
        match_confidence: {
          level: 'high',
          score: 0.95,
          matchedLocator: '[data-testid="submit"]',
          reason: 'unique button',
        },
      } as unknown as AgentOperationState;
      mockApi.getState = jest.fn(() => agentState) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      const confidence = result.current.getMatchConfidence('op-1');

      expect(confidence).toEqual(agentState.match_confidence);
    });

    it('getMatchConfidence returns null for non-agent-operation canvases', () => {
      mockApi.getState = jest.fn(() => ({
        canvas_id: 'chart-1',
        type: 'chart',
        data: {},
      })) as any;
      (window as any).atom.canvas = mockApi;

      const { result } = renderHook(() => useCanvasState());

      expect(result.current.getMatchConfidence('chart-1')).toBeNull();
    });
  });

  describe('State Persistence', () => {
    it('persists state across hook re-renders', async () => {
      const { result, rerender } = renderHook(() => useCanvasState('canvas-1'));

      const initialState = result.current.state;

      rerender();
      rerender();

      expect(result.current.state).toEqual(initialState);
    });

    it('restores the same state after unmount and remount', async () => {
      const testState = {
        canvas_id: 'canvas-1',
        type: 'chart',
        data: { title: 'Persisted' },
      };
      mockApi.getState = jest.fn(() => testState) as any;
      (window as any).atom.canvas = mockApi;

      const { result: result1, unmount: unmount1 } = renderHook(() =>
        useCanvasState('canvas-1')
      );
      const state1 = result1.current.state;

      unmount1();

      const { result: result2 } = renderHook(() => useCanvasState('canvas-1'));

      expect(result2.current.state).toEqual(state1);
    });
  });

  describe('Edge Cases', () => {
    it('treats a null canvas ID as "all canvases"', () => {
      const { result } = renderHook(() => useCanvasState(null as any));

      expect(mockApi.subscribeAll).toHaveBeenCalled();
      expect(mockApi.subscribe).not.toHaveBeenCalled();
      expect(result.current.state).toBeNull();
    });

    it('treats an undefined canvas ID as "all canvases"', () => {
      const { result } = renderHook(() => useCanvasState(undefined as any));

      expect(mockApi.subscribeAll).toHaveBeenCalled();
      expect(result.current.state).toBeNull();
    });

    it('handles very long canvas IDs', async () => {
      const longId = 'a'.repeat(1000);
      const { result } = renderHook(() => useCanvasState(longId));

      expect(mockApi.subscribe).toHaveBeenCalledWith(expect.any(Function));
      expect(result.current.state).not.toBeNull();
    });

    it('handles special characters in canvas IDs', async () => {
      const specialId = 'canvas-🔥-test-123';
      const { result } = renderHook(() => useCanvasState(specialId));

      expect(mockApi.subscribe).toHaveBeenCalledWith(expect.any(Function));
      expect(result.current.state).not.toBeNull();
    });
  });

  describe('Cleanup', () => {
    it('unsubscribes on unmount even when a specific canvas was used', () => {
      const unsubscribe = jest.fn();
      mockApi.subscribe = jest.fn(() => unsubscribe);
      (window as any).atom.canvas = mockApi;

      const { unmount } = renderHook(() => useCanvasState('canvas-1'));

      unmount();

      expect(unsubscribe).toHaveBeenCalledTimes(1);
    });

    it('handles repeated unmounts gracefully', () => {
      const unsubscribe = jest.fn();
      mockApi.subscribeAll = jest.fn(() => unsubscribe);
      (window as any).atom.canvas = mockApi;

      const { unmount } = renderHook(() => useCanvasState());

      unmount();
      unmount();

      expect(unsubscribe).toHaveBeenCalledTimes(1);
    });
  });
});
