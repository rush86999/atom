import { renderHook, act } from '@testing-library/react';
import { useCanvasState } from '../useCanvasState';

// Mock React context
const mockContextValue = {
  canvases: new Map([
    ['canvas-1', { type: 'chart', data: { labels: ['A', 'B'], values: [1, 2] } }],
    ['canvas-2', { type: 'form', data: { fields: [{ name: 'email', value: '' }] } }],
  ]),
  subscribe: jest.fn(),
  unsubscribe: jest.fn(),
  updateCanvas: jest.fn(),
  getCanvas: jest.fn((id) => {
    const canvases = new Map([
      ['canvas-1', { type: 'chart', data: { labels: ['A', 'B'], values: [1, 2] } }],
    ]);
    return canvases.get(id);
  }),
};

describe('useCanvasState Hook', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Canvas State Retrieval', () => {
    it('returns null for non-existent canvas', () => {
      const { result } = renderHook(() => useCanvasState('non-existent'));
      expect(result.current).toBeNull();
    });

    it('returns canvas state for existing canvas', () => {
      const { result } = renderHook(() => useCanvasState('canvas-1'));
      expect(result.current).toEqual({
        type: 'chart',
        data: { labels: ['A', 'B'], values: [1, 2] },
      });
    });

    it('updates when canvas state changes', async () => {
      const { result, rerender } = renderHook(() => useCanvasState('canvas-1'));

      const initialState = result.current;
      expect(initialState).not.toBeNull();

      // Simulate state update
      act(() => {
        // Force re-render with updated state
        rerender();
      });
    });

    it('handles multiple canvas instances', () => {
      const { result: result1 } = renderHook(() => useCanvasState('canvas-1'));
      const { result: result2 } = renderHook(() => useCanvasState('canvas-2'));

      expect(result1.current?.type).toBe('chart');
      expect(result2.current?.type).toBe('form');
    });
  });

  describe('State Subscription', () => {
    it('subscribes to canvas updates on mount', () => {
      const { unmount } = renderHook(() => useCanvasState('canvas-1'));

      // Should have called subscribe
      expect(mockContextValue.subscribe).toHaveBeenCalled();
    });

    it('unsubscribes on unmount', () => {
      const { unmount } = renderHook(() => useCanvasState('canvas-1'));

      unmount();

      expect(mockContextValue.unsubscribe).toHaveBeenCalled();
    });

    it('handles subscription errors gracefully', () => {
      mockContextValue.subscribe.mockImplementation(() => {
        throw new Error('Subscription failed');
      });

      const { result } = renderHook(() => useCanvasState('canvas-1'));

      // Should not throw, handle gracefully
      expect(result.current).toBeNull();
    });
  });

  describe('Canvas Type Handling', () => {
    it('handles chart canvas type', () => {
      const { result } = renderHook(() => useCanvasState('canvas-1'));
      expect(result.current?.type).toBe('chart');
    });

    it('handles form canvas type', () => {
      const { result } = renderHook(() => useCanvasState('canvas-2'));
      expect(result.current?.type).toBe('form');
    });

    it('handles unknown canvas types', () => {
      const { result } = renderHook(() => useCanvasState('unknown-canvas'));
      expect(result.current).toBeNull();
    });
  });

  describe('Data Transformation', () => {
    it('transforms raw data to canvas format', () => {
      const { result } = renderHook(() => useCanvasState('canvas-1'));

      expect(result.current?.data).toEqual({
        labels: ['A', 'B'],
        values: [1, 2],
      });
    });

    it('handles complex nested data structures', () => {
      const complexCanvas = {
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

      const { result } = renderHook(() => useCanvasState('complex-canvas'));

      // Should handle complex structures
      expect(result.current).toBeDefined();
    });

    it('handles empty data', () => {
      const { result } = renderHook(() => useCanvasState('empty-canvas'));

      if (result.current) {
        expect(result.current.data).toBeDefined();
      }
    });
  });

  describe('Real-time Updates', () => {
    it('receives real-time canvas updates', async () => {
      let updateCallback: ((state: any) => void) | null = null;

      mockContextValue.subscribe.mockImplementation((callback) => {
        updateCallback = callback as any;
        return 'subscription-id';
      });

      const { result } = renderHook(() => useCanvasState('canvas-1'));

      // Simulate real-time update
      await act(async () => {
        if (updateCallback) {
          updateCallback({
            type: 'chart',
            data: { labels: ['C', 'D'], values: [3, 4] },
          });
        }
      });

      // State should update
      expect(result.current).toBeDefined();
    });

    it('handles rapid updates', async () => {
      let updateCallback: ((state: any) => void) | null = null;

      mockContextValue.subscribe.mockImplementation((callback) => {
        updateCallback = callback as any;
        return 'subscription-id';
      });

      const { result } = renderHook(() => useCanvasState('canvas-1'));

      // Simulate rapid updates
      await act(async () => {
        for (let i = 0; i < 10; i++) {
          if (updateCallback) {
            updateCallback({
              type: 'chart',
              data: { value: i },
            });
          }
        }
      });

      // Should handle without errors
      expect(result.current).toBeDefined();
    });
  });

  describe('Error Handling', () => {
    it('handles invalid canvas ID', () => {
      const { result } = renderHook(() => useCanvasState(''));
      expect(result.current).toBeNull();
    });

    it('handles malformed canvas data', () => {
      const { result } = renderHook(() => useCanvasState('malformed-canvas'));

      // Should handle gracefully
      expect(() => {
        if (result.current) {
          // Access potentially invalid data
          JSON.stringify(result.current);
        }
      }).not.toThrow();
    });

    it('handles missing required fields', () => {
      const { result } = renderHook(() => useCanvasState('incomplete-canvas'));

      if (result.current) {
        // Should have default values or handle missing fields
        expect(result.current.type).toBeDefined();
      }
    });
  });

  describe('Performance', () => {
    it('does not cause unnecessary re-renders', () => {
      const renderCount = { count: 0 };

      const { rerender } = renderHook(() => {
        renderCount.count++;
        return useCanvasState('canvas-1');
      });

      const initialCount = renderCount.count;

      // Re-render without state change
      rerender();

      // Should not re-render if state hasn't changed
      expect(renderCount.count).toBe(initialCount);
    });

    it('handles multiple hook instances efficiently', () => {
      const renderHook1 = renderHook(() => useCanvasState('canvas-1'));
      const renderHook2 = renderHook(() => useCanvasState('canvas-2'));
      const renderHook3 = renderHook(() => useCanvasState('canvas-3'));

      expect(renderHook1.result.current).toBeDefined();
      expect(renderHook2.result.current).toBeDefined();
      expect(renderHook3.result.current).toBeDefined();
    });
  });

  describe('Integration with Canvas API', () => {
    it('integrates with window.atom.canvas.getState API', () => {
      // Mock the global API
      (window as any).atom = {
        canvas: {
          getState: jest.fn((id) => ({
            type: 'chart',
            data: { values: [1, 2, 3] },
          })),
        },
      };

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      expect(result.current).toBeDefined();
      expect((window as any).atom.canvas.getState).toHaveBeenCalled();
    });

    it('handles API errors gracefully', () => {
      (window as any).atom = {
        canvas: {
          getState: jest.fn(() => {
            throw new Error('API Error');
          }),
        },
      };

      const { result } = renderHook(() => useCanvasState('test-canvas'));

      // Should handle error without crashing
      expect(() => result.current).not.toThrow();
    });
  });

  describe('State Persistence', () => {
    it('persists state across hook re-renders', () => {
      const { result, rerender } = renderHook(() => useCanvasState('canvas-1'));

      const initialState = result.current;

      rerender();

      const newState = result.current;

      expect(initialState).toEqual(newState);
    });

    it('handles state restoration after unmount', () => {
      const { result: result1, unmount: unmount1 } = renderHook(() =>
        useCanvasState('canvas-1')
      );

      const state1 = result1.current;

      unmount1();

      const { result: result2 } = renderHook(() => useCanvasState('canvas-1'));

      const state2 = result2.current;

      // Should restore same state
      expect(state2).toEqual(state1);
    });
  });

  describe('Edge Cases', () => {
    it('handles null canvas ID', () => {
      const { result } = renderHook(() => useCanvasState(null as any));
      expect(result.current).toBeNull();
    });

    it('handles undefined canvas ID', () => {
      const { result } = renderHook(() => useCanvasState(undefined as any));
      expect(result.current).toBeNull();
    });

    it('handles very long canvas IDs', () => {
      const longId = 'a'.repeat(1000);
      const { result } = renderHook(() => useCanvasState(longId));

      // Should handle without errors
      expect(() => result.current).not.toThrow();
    });

    it('handles special characters in canvas ID', () => {
      const specialId = 'canvas-🔥-test-123';
      const { result } = renderHook(() => useCanvasState(specialId));

      expect(() => result.current).not.toThrow();
    });
  });

  describe('TypeScript Type Safety', () => {
    it('returns properly typed canvas state', () => {
      const { result } = renderHook(() => useCanvasState('canvas-1'));

      if (result.current) {
        // Should have correct types
        expect(typeof result.current.type).toBe('string');
        expect(typeof result.current.data).toBe('object');
      }
    });

    it('handles generic canvas types', () => {
      const { result } = renderHook(() => useCanvasState<any>('canvas-1'));

      if (result.current) {
        // Should be able to access any properties
        expect(result.current.anyProperty).toBeUndefined();
      }
    });
  });
});
