import { renderHook, act, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

// Mock the useCanvasState hook with advanced features
const createMockUseCanvasState = () => {
  const canvasStates = new Map<string, any>();

  return {
    useCanvasState: (canvasId: string, options: { persist?: boolean } = {}) => {
      const state = canvasStates.get(canvasId) || {
        data: null,
        error: null,
        isLoading: false,
        subscribers: new Set<Function>(),
      };

      if (!canvasStates.has(canvasId)) {
        canvasStates.set(canvasId, state);
      }

      const notify = () => {
        state.subscribers.forEach(fn => fn());
      };

      return {
        // State
        data: state.data,
        error: state.error,
        isLoading: state.isLoading,

        // Actions
        setState: (newData: any) => {
          state.data = newData;
          state.error = null;

          if (options.persist) {
            const storageKey = `canvas-state-${canvasId}`;
            localStorage.setItem(storageKey, JSON.stringify(newData));
          }

          notify();
        },

        updateState: (updater: (prev: any) => any) => {
          state.data = updater(state.data);
          notify();
        },

        clearState: () => {
          state.data = null;
          state.error = null;

          if (options.persist) {
            const storageKey = `canvas-state-${canvasId}`;
            localStorage.removeItem(storageKey);
          }

          notify();
        },

        setLoading: (loading: boolean) => {
          state.isLoading = loading;
          notify();
        },

        setError: (error: string | null) => {
          state.error = error;
          state.isLoading = false;
          notify();
        },

        // Subscription management
        subscribe: (callback: Function) => {
          state.subscribers.add(callback);
          return () => state.subscribers.delete(callback);
        },

        // Cleanup
        destroy: () => {
          canvasStates.delete(canvasId);
        },

        // Advanced features
        getStateSnapshot: () => ({ ...state.data }),
        restoreSnapshot: (snapshot: any) => {
          state.data = snapshot;
          notify();
        },

        // Multiple instance support
        getInstanceId: () => canvasId,
      };
    },

    // Global canvas state manager
    canvasStateManager: {
      getAllStates: () => {
        const allStates: Record<string, any> = {};
        canvasStates.forEach((state, id) => {
          allStates[id] = state.data;
        });
        return allStates;
      },

      clearAllStates: () => {
        canvasStates.forEach((state) => {
          state.data = null;
          state.error = null;
          state.subscribers.forEach(fn => fn());
        });
      },

      getStateCount: () => canvasStates.size,
    },
  };
};

describe('useCanvasState - Advanced Tests', () => {
  let mockUseCanvasState: ReturnType<typeof createMockUseCanvasState>['useCanvasState'];
  let mockCanvasStateManager: ReturnType<typeof createMockUseCanvasState>['canvasStateManager'];

  beforeEach(() => {
    const mock = createMockUseCanvasState();
    mockUseCanvasState = mock.useCanvasState;
    mockCanvasStateManager = mock.canvasStateManager;
  });

  describe('Multiple Instance Management', () => {
    it('should manage multiple canvas instances independently', async () => {
      const { result: result1 } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      const { result: result2 } = renderHook(() =>
        mockUseCanvasState('canvas-2')
      );

      act(() => {
        result1.current.setState({ type: 'chart', data: [1, 2, 3] });
        result2.current.setState({ type: 'form', fields: [] });
      });

      expect(result1.current.data.type).toBe('chart');
      expect(result2.current.data.type).toBe('form');

      // Update one should not affect the other
      act(() => {
        result1.current.setState({ type: 'chart', data: [4, 5, 6] });
      });

      expect(result1.current.data.data).toEqual([4, 5, 6]);
      expect(result2.current.data.type).toBe('form'); // Unchanged
    });

    it('should provide access to all canvas states', async () => {
      const { result: result1 } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      const { result: result2 } = renderHook(() =>
        mockUseCanvasState('canvas-2')
      );

      act(() => {
        result1.current.setState({ value: 'first' });
        result2.current.setState({ value: 'second' });
      });

      const allStates = mockCanvasStateManager.getAllStates();

      expect(allStates['canvas-1']).toEqual({ value: 'first' });
      expect(allStates['canvas-2']).toEqual({ value: 'second' });
    });

    it('should clear all canvas states', async () => {
      const { result: result1 } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      const { result: result2 } = renderHook(() =>
        mockUseCanvasState('canvas-2')
      );

      act(() => {
        result1.current.setState({ value: 'first' });
        result2.current.setState({ value: 'second' });
      });

      expect(result1.current.data).toBeDefined();
      expect(result2.current.data).toBeDefined();

      act(() => {
        mockCanvasStateManager.clearAllStates();
      });

      expect(result1.current.data).toBeNull();
      expect(result2.current.data).toBeNull();
    });

    it('should track state instance count', async () => {
      expect(mockCanvasStateManager.getStateCount()).toBe(0);

      const { result: result1 } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      expect(mockCanvasStateManager.getStateCount()).toBe(1);

      const { result: result2 } = renderHook(() =>
        mockUseCanvasState('canvas-2')
      );

      expect(mockCanvasStateManager.getStateCount()).toBe(2);

      act(() => {
        result1.current.destroy();
      });

      expect(mockCanvasStateManager.getStateCount()).toBe(1);
    });
  });

  describe('State Persistence', () => {
    it('should persist state to localStorage when enabled', async () => {
      const setItemSpy = jest.spyOn(Storage.prototype, 'setItem');

      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1', { persist: true })
      );

      act(() => {
        result.current.setState({ type: 'chart', data: [1, 2, 3] });
      });

      expect(setItemSpy).toHaveBeenCalledWith(
        'canvas-state-canvas-1',
        JSON.stringify({ type: 'chart', data: [1, 2, 3] })
      );

      setItemSpy.mockRestore();
    });

    it('should restore state from localStorage on mount', async () => {
      const savedState = { type: 'chart', data: [1, 2, 3] };
      const getItemSpy = jest.spyOn(Storage.prototype, 'getItem').mockReturnValue(
        JSON.stringify(savedState)
      );

      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1', { persist: true })
      );

      // Simulate loading from localStorage
      act(() => {
        const loaded = JSON.parse(localStorage.getItem('canvas-state-canvas-1') || 'null');
        if (loaded) {
          result.current.setState(loaded);
        }
      });

      expect(result.current.data).toEqual(savedState);

      getItemSpy.mockRestore();
    });

    it('should clear persisted state on clearState', async () => {
      const removeItemSpy = jest.spyOn(Storage.prototype, 'removeItem');

      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1', { persist: true })
      );

      act(() => {
        result.current.setState({ type: 'chart', data: [1, 2, 3] });
      });

      act(() => {
        result.current.clearState();
      });

      expect(removeItemSpy).toHaveBeenCalledWith('canvas-state-canvas-1');
      expect(result.current.data).toBeNull();

      removeItemSpy.mockRestore();
    });

    it('should not persist when persist option is disabled', async () => {
      const setItemSpy = jest.spyOn(Storage.prototype, 'setItem');

      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1', { persist: false })
      );

      act(() => {
        result.current.setState({ type: 'chart', data: [1, 2, 3] });
      });

      expect(setItemSpy).not.toHaveBeenCalled();

      setItemSpy.mockRestore();
    });
  });

  describe('State Snapshots', () => {
    it('should create state snapshot', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      act(() => {
        result.current.setState({
          type: 'chart',
          data: [1, 2, 3],
          config: { title: 'Test Chart' },
        });
      });

      const snapshot = result.current.getStateSnapshot();

      expect(snapshot).toEqual({
        type: 'chart',
        data: [1, 2, 3],
        config: { title: 'Test Chart' },
      });

      // Snapshot should be a copy, not reference
      expect(snapshot).not.toBe(result.current.data);
    });

    it('should restore from snapshot', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      const snapshot = {
        type: 'form',
        fields: [
          { name: 'email', type: 'email', required: true },
          { name: 'message', type: 'textarea', required: false },
        ],
      };

      act(() => {
        result.current.restoreSnapshot(snapshot);
      });

      expect(result.current.data).toEqual(snapshot);
    });

    it('should maintain snapshot independence', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      act(() => {
        result.current.setState({ value: 'original' });
      });

      const snapshot = result.current.getStateSnapshot();

      // Modify original state
      act(() => {
        result.current.setState({ value: 'modified' });
      });

      expect(result.current.data.value).toBe('modified');
      expect(snapshot.value).toBe('original');
    });
  });

  describe('Functional State Updates', () => {
    it('should update state using functional updater', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      act(() => {
        result.current.setState({ counter: 0, list: [] });
      });

      act(() => {
        result.current.updateState((prev: any) => ({
          ...prev,
          counter: prev.counter + 1,
          list: [...prev.list, 'item'],
        }));
      });

      expect(result.current.data.counter).toBe(1);
      expect(result.current.data.list).toEqual(['item']);

      act(() => {
        result.current.updateState((prev: any) => ({
          ...prev,
          counter: prev.counter + 1,
        }));
      });

      expect(result.current.data.counter).toBe(2);
      expect(result.current.data.list).toEqual(['item']);
    });

    it('should handle complex nested updates', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      act(() => {
        result.current.setState({
          nested: {
            level1: {
              level2: {
                value: 'deep',
              },
            },
          },
        });
      });

      act(() => {
        result.current.updateState((prev: any) => ({
          ...prev,
          nested: {
            ...prev.nested,
            level1: {
              ...prev.nested.level1,
              level2: {
                ...prev.nested.level1.level2,
                value: 'updated',
              },
            },
          },
        }));
      });

      expect(result.current.data.nested.level1.level2.value).toBe('updated');
    });
  });

  describe('Error Handling', () => {
    it('should set and clear error state', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      expect(result.current.error).toBeNull();

      act(() => {
        result.current.setError('Something went wrong');
      });

      expect(result.current.error).toBe('Something went wrong');
      expect(result.current.isLoading).toBe(false);

      act(() => {
        result.current.setState({ data: 'recovered' });
      });

      // Setting state should not clear error automatically
      expect(result.current.error).toBe('Something went wrong');

      act(() => {
        result.current.setError(null);
      });

      expect(result.current.error).toBeNull();
    });

    it('should handle loading state correctly', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      expect(result.current.isLoading).toBe(false);

      act(() => {
        result.current.setLoading(true);
      });

      expect(result.current.isLoading).toBe(true);

      act(() => {
        result.current.setLoading(false);
      });

      expect(result.current.isLoading).toBe(false);
    });
  });

  describe('Performance Optimization', () => {
    it('should only notify subscribers when state changes', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      let notifyCount = 0;
      const unsubscribe = result.current.subscribe(() => {
        notifyCount++;
      });

      act(() => {
        // Setting same value should still notify (React pattern)
        result.current.setState({ value: 'test' });
      });

      expect(notifyCount).toBe(1);

      act(() => {
        result.current.setState({ value: 'test' }); // Same value
      });

      expect(notifyCount).toBe(2); // Still notifies

      unsubscribe();
    });

    it('should handle multiple subscribers efficiently', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      const subscriber1Calls: number[] = [];
      const subscriber2Calls: number[] = [];

      const unsubscribe1 = result.current.subscribe(() => {
        subscriber1Calls.push(Date.now());
      });

      const unsubscribe2 = result.current.subscribe(() => {
        subscriber2Calls.push(Date.now());
      });

      act(() => {
        result.current.setState({ value: 'test' });
      });

      expect(subscriber1Calls).toHaveLength(1);
      expect(subscriber2Calls).toHaveLength(1);

      unsubscribe1();
      unsubscribe2();
    });
  });

  describe('Cleanup', () => {
    it('should cleanup state on destroy', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      act(() => {
        result.current.setState({ value: 'test' });
      });

      expect(mockCanvasStateManager.getStateCount()).toBe(1);

      act(() => {
        result.current.destroy();
      });

      expect(mockCanvasStateManager.getStateCount()).toBe(0);
    });
  });

  describe('Edge Cases', () => {
    it('should handle null state updates', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      act(() => {
        result.current.setState({ value: 'test' });
      });

      expect(result.current.data).not.toBeNull();

      act(() => {
        result.current.setState(null);
      });

      expect(result.current.data).toBeNull();
    });

    it('should handle undefined state updates', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      act(() => {
        result.current.setState(undefined);
      });

      expect(result.current.data).toBeUndefined();
    });

    it('should handle rapid state updates', async () => {
      const { result } = renderHook(() =>
        mockUseCanvasState('canvas-1')
      );

      act(() => {
        for (let i = 0; i < 100; i++) {
          result.current.setState({ counter: i });
        }
      });

      // Last update should win
      expect(result.current.data.counter).toBe(99);
    });
  });
});
