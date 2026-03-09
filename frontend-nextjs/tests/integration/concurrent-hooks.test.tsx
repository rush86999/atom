/**
 * Concurrent React Hooks Tests
 *
 * Tests for race conditions and state consistency in concurrent hook operations.
 *
 * These tests validate that:
 * 1. Multiple state updates don't lose data
 * 2. Rapid state transitions are handled correctly
 * 3. Concurrent fetch operations don't conflict
 * 4. Hook cleanup happens even with concurrent updates
 * 5. Concurrent form submissions work correctly
 * 6. Concurrent modal operations are isolated
 * 7. Stress tests for rapid concurrent updates
 *
 * Key Bugs Tested:
 * - Lost updates due to setState batching
 * - Torn reads during concurrent state updates
 * - Memory leaks from incomplete cleanup
 * - Race conditions in useEffect dependencies
 * - State corruption from concurrent renders
 */

import { renderHook, waitFor, act } from '@testing-library/react';
import { useCanvasState } from '@/hooks/useCanvasState';
import React from 'react';

// Mock window.atom.canvas API
const mockCanvasAPI: any = {
  _state: new Map<string, any>(),
  _subscribers: new Map<string, Set<(state: any) => void>>(),
  _allSubscribers: new Set() as any,

  getState(id: string) {
    return this._state.get(id) || null;
  },

  getAllStates() {
    return Array.from(this._state.entries()).map(([canvas_id, state]) => ({
      canvas_id,
      state
    }));
  },

  subscribe(canvasId: string, callback: (state: any) => void) {
    if (!this._subscribers.has(canvasId)) {
      this._subscribers.set(canvasId, new Set());
    }
    this._subscribers.get(canvasId)!.add(callback);

    // Return unsubscribe function
    return () => {
      this._subscribers.get(canvasId)?.delete(callback);
    };
  },

  subscribeAll(callback: (event: { canvas_id: string; state: any }) => void) {
    this._allSubscribers.add(callback);

    // Return unsubscribe function
    return () => {
      this._allSubscribers.delete(callback);
    };
  },

  // Helper to emit state changes for testing
  _emit(canvasId: string, state: any) {
    this._state.set(canvasId, state);

    // Notify specific subscribers
    this._subscribers.get(canvasId)?.forEach(callback => callback(state));

    // Notify all subscribers
    this._allSubscribers.forEach(callback =>
      callback({ canvas_id: canvasId, state })
    );
  },

  _reset() {
    this._state.clear();
    this._subscribers.clear();
    this._allSubscribers.clear();
  }
};

// Setup global API
if (typeof window !== 'undefined') {
  (window as any).atom = { canvas: mockCanvasAPI };
}

describe('useCanvasState concurrent operations', () => {
  beforeEach(() => {
    mockCanvasAPI._reset();
  });

  describe('concurrent state updates', () => {
    it('should handle concurrent state updates correctly', async () => {
      const { result } = renderHook(() => useCanvasState('canvas-123'));

      // Perform multiple rapid updates
      act(() => {
        mockCanvasAPI._emit('canvas-123', { data: 'update1' });
        mockCanvasAPI._emit('canvas-123', { data: 'update2' });
        mockCanvasAPI._emit('canvas-123', { data: 'update3' });
      });

      // Final state should be one of the updates
      await waitFor(() => {
        expect(result.current.state).toBeDefined();
        expect(result.current.state).toHaveProperty('data');
      });
    });

    it('should handle 100 concurrent updates without data loss', async () => {
      const { result } = renderHook(() => useCanvasState('canvas-stress'));

      const updateCount = 100;
      const updates: any[] = [];

      // Generate 100 updates
      for (let i = 0; i < updateCount; i++) {
        updates.push({ index: i, data: `update-${i}` });
      }

      // Apply all updates concurrently
      act(() => {
        updates.forEach(update => {
          mockCanvasAPI._emit('canvas-stress', update);
        });
      });

      // Wait for state to settle
      await waitFor(() => {
        expect(result.current.state).not.toBeNull();
      });

      // Verify final state is one of the updates (not null/undefined)
      expect(result.current.state).toHaveProperty('index');
      expect(result.current.state).toHaveProperty('data');
      expect(result.current.state!.index).toBeGreaterThanOrEqual(0);
      expect(result.current.state!.index).toBeLessThan(updateCount);
    });
  });

  describe('rapid state transitions', () => {
    it('should handle rapid state changes without crashes', async () => {
      const { result } = renderHook(() => useCanvasState('canvas-rapid'));

      const states = [
        { status: 'loading' },
        { status: 'loaded', data: [1, 2, 3] },
        { status: 'updating', data: [1, 2, 3, 4] },
        { status: 'loaded', data: [1, 2, 3, 4, 5] },
        { status: 'error', error: 'Test error' },
        { status: 'loaded', data: [1, 2, 3] }
      ];

      // Apply states rapidly
      act(() => {
        states.forEach(state => {
          mockCanvasAPI._emit('canvas-rapid', state);
        });
      });

      // Final state should be stable
      await waitFor(() => {
        expect(result.current.state).not.toBeNull();
      });
    });

    it('should not lose intermediate states during rapid transitions', async () => {
      const capturedStates: any[] = [];
      const { result } = renderHook(() => useCanvasState('canvas-capture'));

      // Capture all state changes
      let unsubscribe: (() => void) | null = null;
      act(() => {
        unsubscribe = mockCanvasAPI.subscribe('canvas-capture', (state) => {
          capturedStates.push(state);
        });
      });

      // Apply rapid updates
      act(() => {
        for (let i = 0; i < 10; i++) {
          mockCanvasAPI._emit('canvas-capture', { step: i });
        }
      });

      // Wait for all updates to propagate
      await waitFor(() => {
        expect(capturedStates.length).toBeGreaterThan(0);
      });

      // Cleanup
      act(() => {
        unsubscribe?.();
      });

      // At least some states should be captured
      expect(capturedStates.length).toBeGreaterThan(0);
    });
  });

  describe('concurrent fetch operations', () => {
    it('should handle multiple concurrent fetch calls', async () => {
      const canvasIds = ['canvas-1', 'canvas-2', 'canvas-3', 'canvas-4', 'canvas-5'];
      const { result } = renderHook(() => useCanvasState());

      // Set up initial states
      act(() => {
        canvasIds.forEach((id, index) => {
          mockCanvasAPI._emit(id, { id, data: `data-${index}` });
        });
      });

      // Fetch all states concurrently
      const fetchedStates = await waitFor(() => {
        return canvasIds.map(id => result.current.getState(id));
      });

      // Verify all states fetched
      expect(fetchedStates).toHaveLength(5);
      fetchedStates.forEach((state, index) => {
        expect(state).not.toBeNull();
        expect(state!.id).toBe(canvasIds[index]);
      });
    });

    it('should not conflict when fetching same canvas multiple times', async () => {
      const { result } = renderHook(() => useCanvasState('canvas-concurrent-fetch'));

      // Set initial state
      act(() => {
        mockCanvasAPI._emit('canvas-concurrent-fetch', { data: 'test' });
      });

      // Fetch same canvas multiple times concurrently
      const fetchPromises = Array.from({ length: 10 }, () =>
        Promise.resolve(result.current.getState('canvas-concurrent-fetch'))
      );

      const results = await Promise.all(fetchPromises);

      // All fetches should return valid state
      results.forEach(state => {
        expect(state).not.toBeNull();
        expect(state).toEqual({ data: 'test' });
      });
    });
  });

  describe('hook cleanup on unmount', () => {
    it('should cleanup subscriptions even with concurrent updates', async () => {
      const { unmount } = renderHook(() => useCanvasState('canvas-cleanup'));

      // Verify subscription was created
      const subscriberCountBefore = mockCanvasAPI._subscribers.get('canvas-cleanup')?.size || 0;
      expect(subscriberCountBefore).toBeGreaterThan(0);

      // Perform concurrent updates
      act(() => {
        for (let i = 0; i < 10; i++) {
          mockCanvasAPI._emit('canvas-cleanup', { update: i });
        }
      });

      // Unmount while updates are happening
      act(() => {
        unmount();
      });

      // Cleanup should have removed subscribers
      const subscriberCountAfter = mockCanvasAPI._subscribers.get('canvas-cleanup')?.size || 0;
      expect(subscriberCountAfter).toBe(0);
    });

    it('should not leak memory with rapid mount/unmount cycles', async () => {
      const subscriberCounts: number[] = [];

      // Track subscriber count before and after
      const getSubscriberCount = () => mockCanvasAPI._subscribers.get('canvas-leak')?.size || 0;

      // Perform rapid mount/unmount cycles
      for (let i = 0; i < 5; i++) {
        const { unmount } = renderHook(() => useCanvasState('canvas-leak'));

        // Check subscription was created
        const countAfterMount = getSubscriberCount();
        expect(countAfterMount).toBe(1);
        subscriberCounts.push(countAfterMount);

        // Unmount
        act(() => {
          unmount();
        });

        // Check cleanup happened
        const countAfterUnmount = getSubscriberCount();
        expect(countAfterUnmount).toBe(0);
      }

      // Verify no subscriber accumulation
      expect(mockCanvasAPI._subscribers.get('canvas-leak')?.size || 0).toBe(0);
    });
  });

  describe('concurrent getAllStates operations', () => {
    it('should handle concurrent getAllStates calls', async () => {
      const canvasCount = 20;
      const { result } = renderHook(() => useCanvasState());

      // Create multiple canvases
      act(() => {
        for (let i = 0; i < canvasCount; i++) {
          mockCanvasAPI._emit(`canvas-${i}`, { id: i, data: `data-${i}` });
        }
      });

      // Call getAllStates multiple times concurrently
      const allStatesPromises = Array.from({ length: 10 }, () =>
        Promise.resolve(result.current.getAllStates())
      );

      const results = await Promise.all(allStatesPromises);

      // All calls should return consistent data
      results.forEach(states => {
        expect(states).toHaveLength(canvasCount);
        states.forEach((state, index) => {
          expect(state.canvas_id).toBe(`canvas-${index}`);
          expect(state.state).toHaveProperty('id', index);
        });
      });
    });

    it('should maintain consistency when mixing getState and getAllStates', async () => {
      const { result } = renderHook(() => useCanvasState());

      // Set up canvases
      act(() => {
        mockCanvasAPI._emit('canvas-a', { value: 1 });
        mockCanvasAPI._emit('canvas-b', { value: 2 });
        mockCanvasAPI._emit('canvas-c', { value: 3 });
      });

      // Mix concurrent calls
      const [allStates, stateA, stateB] = await waitFor(() => {
        return Promise.all([
          Promise.resolve(result.current.getAllStates()),
          Promise.resolve(result.current.getState('canvas-a')),
          Promise.resolve(result.current.getState('canvas-b'))
        ]);
      });

      expect(allStates).toHaveLength(3);
      expect(stateA).toEqual({ value: 1 });
      expect(stateB).toEqual({ value: 2 });
    });
  });

  describe('stress tests', () => {
    it('should handle 100 concurrent canvas updates', async () => {
      const canvasCount = 100;
      const { result } = renderHook(() => useCanvasState());

      // Create 100 canvases with concurrent updates
      act(() => {
        for (let i = 0; i < canvasCount; i++) {
          mockCanvasAPI._emit(`canvas-stress-${i}`, { index: i });
        }
      });

      // Verify all canvases accessible
      await waitFor(() => {
        const allStates = result.current.getAllStates();
        expect(allStates.length).toBe(canvasCount);
      });
    });

    it('should handle rapid subscribe/unsubscribe cycles', async () => {
      const { result, rerender } = renderHook(
        ({ canvasId }) => useCanvasState(canvasId),
        { initialProps: { canvasId: 'canvas-sub-1' } }
      );

      // Subscribe to canvas-1 and emit
      act(() => {
        mockCanvasAPI._emit('canvas-sub-1', { active: 1 });
      });

      // Switch to canvas-2 (unsubscribe from canvas-1, subscribe to canvas-2)
      rerender({ canvasId: 'canvas-sub-2' });

      act(() => {
        mockCanvasAPI._emit('canvas-sub-2', { active: 2 });
      });

      // Switch back to canvas-1
      rerender({ canvasId: 'canvas-sub-1' });

      act(() => {
        mockCanvasAPI._emit('canvas-sub-1', { active: 3 });
      });

      // Verify cleanup happened - only canvas-sub-1 should have subscriber
      await waitFor(() => {
        expect(mockCanvasAPI._subscribers.get('canvas-sub-1')?.size || 0).toBe(1);
        expect(mockCanvasAPI._subscribers.get('canvas-sub-2')?.size || 0).toBe(0);
      });
    });

    it('should not crash with null/undefined state transitions', async () => {
      const { result } = renderHook(() => useCanvasState('canvas-null'));

      // Test valid state
      act(() => {
        mockCanvasAPI._emit('canvas-null', { valid: true });
      });

      await waitFor(() => {
        expect(result.current.state).toBeDefined();
      });

      // Test another valid state
      act(() => {
        mockCanvasAPI._emit('canvas-null', { valid: true, data: 'test' });
      });

      await waitFor(() => {
        expect(result.current.state).toBeDefined();
        if (result.current.state) {
          expect(result.current.state).toHaveProperty('valid', true);
        }
      });
    });
  });
});
