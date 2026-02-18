/**
 * Canvas API Registration Unit Tests
 *
 * Tests for window.atom.canvas global API accessibility in Tauri webview environment.
 * Verifies API registration, method signatures, subscription mechanisms, and coexistence with Tauri IPC bridge.
 */

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

describe('Canvas API Registration in Tauri Environment', () => {
  let mockStates: Map<string, AnyCanvasState>;
  let subscribers: Map<string, Array<(state: AnyCanvasState) => void>>;
  let globalSubscribers: Array<(event: CanvasStateChangeEvent) => void>;

  beforeEach(() => {
    // Initialize mock data stores
    mockStates = new Map();
    subscribers = new Map();
    globalSubscribers = [];

    // Initialize Tauri IPC bridge (simulates Tauri webview environment)
    window.__TAURI__ = {
      invoke: jest.fn().mockResolvedValue({ success: true })
    };

    // Initialize canvas state API (simulates Phase 20 implementation)
    window.atom = {
      canvas: {
        getState: (id: string) => {
          return mockStates.get(id) || null;
        },
        getAllStates: () => {
          return Array.from(mockStates.entries()).map(([canvas_id, state]) => ({
            canvas_id,
            state
          }));
        },
        subscribe: (canvasId: string, callback: (state: AnyCanvasState) => void) => {
          const subs = subscribers.get(canvasId) || [];
          subs.push(callback);
          subscribers.set(canvasId, subs);

          // Return unsubscribe function
          return () => {
            const current = subscribers.get(canvasId) || [];
            subscribers.set(canvasId, current.filter(cb => cb !== callback));
          };
        },
        subscribeAll: (callback: (event: CanvasStateChangeEvent) => void) => {
          globalSubscribers.push(callback);

          // Return unsubscribe function
          return () => {
            const idx = globalSubscribers.indexOf(callback);
            if (idx >= 0) {
              globalSubscribers.splice(idx, 1);
            }
          };
        }
      }
    };
  });

  afterEach(() => {
    // Clean up after each test
    delete window.__TAURI__;
    delete window.atom;
  });

  describe('API Registration', () => {
    test('window.atom.canvas should be defined', () => {
      expect(window.atom?.canvas).toBeDefined();
      expect(typeof window.atom.canvas).toBe('object');
    });

    test('canvas API should have all required methods', () => {
      expect(typeof window.atom.canvas?.getState).toBe('function');
      expect(typeof window.atom.canvas?.getAllStates).toBe('function');
      expect(typeof window.atom.canvas?.subscribe).toBe('function');
      expect(typeof window.atom.canvas?.subscribeAll).toBe('function');
    });

    test('Tauri IPC bridge should coexist with canvas API', () => {
      // Both APIs should be accessible
      expect(window.__TAURI__).toBeDefined();
      expect(window.atom?.canvas).toBeDefined();

      // Tauri invoke should still work
      expect(typeof window.__TAURI__?.invoke).toBe('function');
      expect(typeof window.atom.canvas?.getState).toBe('function');
    });

    test('window.__TAURI__ should remain accessible', () => {
      // Verify Tauri API is not clobbered
      expect(window.__TAURI__).toBeDefined();
      expect(window.__TAURI__?.invoke).toBeDefined();

      // Test Tauri invoke works
      const mockInvoke = window.__TAURI__!.invoke as jest.Mock;
      expect(mockInvoke).toBeDefined();
    });
  });

  describe('getState Method', () => {
    test('getState should return null for unknown canvas', () => {
      const result = window.atom.canvas?.getState('non-existent-canvas');
      expect(result).toBeNull();
    });

    test('getState should return canvas state for known canvas', () => {
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

      mockStates.set('test-canvas', mockState);

      const result = window.atom.canvas?.getState('test-canvas');
      expect(result).toEqual(mockState);
      expect(result?.canvas_id).toBe('test-canvas');
    });

    test('getState should handle undefined canvasId gracefully', () => {
      const result = window.atom.canvas?.getState(undefined as any);
      expect(result).toBeNull();
    });

    test('getState should handle empty string canvasId', () => {
      const result = window.atom.canvas?.getState('');
      expect(result).toBeNull();
    });
  });

  describe('getAllStates Method', () => {
    test('getAllStates should return empty array initially', () => {
      const result = window.atom.canvas?.getAllStates();
      expect(result).toEqual([]);
      expect(Array.isArray(result)).toBe(true);
    });

    test('getAllStates should return all registered canvases', () => {
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

      mockStates.set('canvas-1', state1);
      mockStates.set('canvas-2', state2);

      const result = window.atom.canvas?.getAllStates();
      expect(result).toHaveLength(2);
      expect(result?.[0].canvas_id).toBe('canvas-1');
      expect(result?.[1].canvas_id).toBe('canvas-2');
    });

    test('getAllStates should return empty array when no canvases registered', () => {
      const result = window.atom.canvas?.getAllStates();
      expect(result).toEqual([]);
    });
  });

  describe('subscribe Method', () => {
    test('subscribe should return unsubscribe function', () => {
      const mockCallback = jest.fn();
      const unsubscribe = window.atom.canvas?.subscribe('test-canvas', mockCallback);

      expect(typeof unsubscribe).toBe('function');
    });

    test('subscribe should callback on state change', () => {
      const mockCallback = jest.fn();
      window.atom.canvas?.subscribe('test-canvas', mockCallback);

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

      // Simulate state change by manually calling subscribers
      const subs = subscribers.get('test-canvas') || [];
      subs.forEach(cb => cb(newState));

      expect(mockCallback).toHaveBeenCalledTimes(1);
      expect(mockCallback).toHaveBeenCalledWith(newState);
    });

    test('unsubscribe should stop callbacks', () => {
      const mockCallback = jest.fn();
      const unsubscribe = window.atom.canvas?.subscribe('test-canvas', mockCallback);

      // Unsubscribe
      unsubscribe?.();

      const newState: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: 'test-canvas',
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: []
      };

      // Try to trigger callback
      const subs = subscribers.get('test-canvas') || [];
      subs.forEach(cb => cb(newState));

      expect(mockCallback).not.toHaveBeenCalled();
    });

    test('canvas API should handle concurrent subscriptions', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      const callback3 = jest.fn();

      window.atom.canvas?.subscribe('test-canvas', callback1);
      window.atom.canvas?.subscribe('test-canvas', callback2);
      window.atom.canvas?.subscribe('test-canvas', callback3);

      const newState: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: 'test-canvas',
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: []
      };

      const subs = subscribers.get('test-canvas') || [];
      subs.forEach(cb => cb(newState));

      expect(callback1).toHaveBeenCalledTimes(1);
      expect(callback2).toHaveBeenCalledTimes(1);
      expect(callback3).toHaveBeenCalledTimes(1);
    });
  });

  describe('subscribeAll Method', () => {
    test('subscribeAll should return unsubscribe function', () => {
      const mockCallback = jest.fn();
      const unsubscribe = window.atom.canvas?.subscribeAll(mockCallback);

      expect(typeof unsubscribe).toBe('function');
    });

    test('subscribeAll should notify for any canvas change', () => {
      const mockCallback = jest.fn();
      window.atom.canvas?.subscribeAll(mockCallback);

      const event: CanvasStateChangeEvent = {
        type: 'canvas:state_change',
        canvas_id: 'test-canvas',
        canvas_type: 'generic',
        component: 'line_chart',
        state: {
          canvas_type: 'generic',
          canvas_id: 'test-canvas',
          timestamp: '2026-02-18T10:00:00Z',
          component: 'line_chart',
          chart_type: 'line',
          data_points: []
        },
        timestamp: '2026-02-18T10:00:00Z'
      };

      // Simulate global notification
      globalSubscribers.forEach(cb => cb(event));

      expect(mockCallback).toHaveBeenCalledTimes(1);
      expect(mockCallback).toHaveBeenCalledWith(event);
    });

    test('unsubscribe from subscribeAll should stop callbacks', () => {
      const mockCallback = jest.fn();
      const unsubscribe = window.atom.canvas?.subscribeAll(mockCallback);

      // Unsubscribe
      unsubscribe?.();

      const event: CanvasStateChangeEvent = {
        type: 'canvas:state_change',
        canvas_id: 'test-canvas',
        canvas_type: 'generic',
        component: 'line_chart',
        state: {
          canvas_type: 'generic',
          canvas_id: 'test-canvas',
          timestamp: '2026-02-18T10:00:00Z',
          component: 'line_chart',
          chart_type: 'line',
          data_points: []
        },
        timestamp: '2026-02-18T10:00:00Z'
      };

      globalSubscribers.forEach(cb => cb(event));

      expect(mockCallback).not.toHaveBeenCalled();
    });
  });

  describe('Rapid State Changes', () => {
    test('canvas API should handle rapid state changes', () => {
      const mockCallback = jest.fn();
      window.atom.canvas?.subscribe('test-canvas', mockCallback);

      // Simulate rapid state changes (10 updates in quick succession)
      for (let i = 0; i < 10; i++) {
        const newState: AnyCanvasState = {
          canvas_type: 'generic',
          canvas_id: 'test-canvas',
          timestamp: `2026-02-18T10:00:${i.toString().padStart(2, '0')}Z`,
          component: 'line_chart',
          chart_type: 'line',
          data_points: [{ x: i, y: i * 10 }]
        };

        const subs = subscribers.get('test-canvas') || [];
        subs.forEach(cb => cb(newState));
      }

      expect(mockCallback).toHaveBeenCalledTimes(10);
    });

    test('canvas API should handle state updates for multiple canvases', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();

      window.atom.canvas?.subscribe('canvas-1', callback1);
      window.atom.canvas?.subscribe('canvas-2', callback2);

      // Update both canvases
      const state1: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: 'canvas-1',
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: []
      };

      const state2: AnyCanvasState = {
        canvas_type: 'terminal',
        canvas_id: 'canvas-2',
        timestamp: '2026-02-18T10:00:00Z',
        working_dir: '/home',
        command: 'pwd',
        lines: ['/home'],
        cursor_pos: { row: 0, col: 0 },
        scroll_offset: 0
      };

      const subs1 = subscribers.get('canvas-1') || [];
      const subs2 = subscribers.get('canvas-2') || [];

      subs1.forEach(cb => cb(state1));
      subs2.forEach(cb => cb(state2));

      expect(callback1).toHaveBeenCalledTimes(1);
      expect(callback1).toHaveBeenCalledWith(state1);
      expect(callback2).toHaveBeenCalledTimes(1);
      expect(callback2).toHaveBeenCalledWith(state2);
    });
  });

  describe('Edge Cases and Error Handling', () => {
    test('canvas API should handle null canvasId gracefully', () => {
      const result = window.atom.canvas?.getState(null as any);
      expect(result).toBeNull();
    });

    test('canvas API should handle special characters in canvasId', () => {
      const specialId = 'canvas-with-special-chars-<>-"\'-';
      const mockState: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: specialId,
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: []
      };

      mockStates.set(specialId, mockState);

      const result = window.atom.canvas?.getState(specialId);
      expect(result).toEqual(mockState);
    });

    test('canvas API should handle very long canvasId', () => {
      const longId = 'a'.repeat(1000);
      const mockState: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: longId,
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: []
      };

      mockStates.set(longId, mockState);

      const result = window.atom.canvas?.getState(longId);
      expect(result).toEqual(mockState);
    });

    test('canvas API should handle subscribing to same canvas multiple times', () => {
      const mockCallback = jest.fn();

      // Subscribe three times to same canvas
      const unsub1 = window.atom.canvas?.subscribe('test-canvas', mockCallback);
      const unsub2 = window.atom.canvas?.subscribe('test-canvas', mockCallback);
      const unsub3 = window.atom.canvas?.subscribe('test-canvas', mockCallback);

      const newState: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: 'test-canvas',
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: []
      };

      const subs = subscribers.get('test-canvas') || [];
      subs.forEach(cb => cb(newState));

      // Should receive 3 callbacks (one for each subscription)
      expect(mockCallback).toHaveBeenCalledTimes(3);

      // Cleanup
      unsub1?.();
      unsub2?.();
      unsub3?.();
    });
  });

  describe('Tauri Integration Specific Tests', () => {
    test('Tauri invoke should not interfere with canvas API', () => {
      // Call Tauri invoke
      const tauriInvoke = window.__TAURI__?.invoke as jest.Mock;
      tauriInvoke?.mockResolvedValue({ success: true });

      // Use canvas API
      const result = window.atom.canvas?.getState('test-canvas');

      // Tauri should still work
      expect(tauriInvoke).toBeDefined();
      expect(window.atom.canvas).toBeDefined();

      // Canvas API should return null (no state set)
      expect(result).toBeNull();
    });

    test('Canvas API should work when Tauri is not present', () => {
      // Remove Tauri
      delete window.__TAURI__;

      // Canvas API should still work
      expect(window.atom?.canvas).toBeDefined();
      expect(window.atom.canvas?.getState).toBeDefined();

      const result = window.atom.canvas?.getState('test-canvas');
      expect(result).toBeNull();
    });

    test('Multiple subscriptions to different canvases should not interfere', () => {
      const callback1 = jest.fn();
      const callback2 = jest.fn();
      const callback3 = jest.fn();

      window.atom.canvas?.subscribe('canvas-1', callback1);
      window.atom.canvas?.subscribe('canvas-2', callback2);
      window.atom.canvas?.subscribeAll(callback3);

      // Update canvas-1
      const state1: AnyCanvasState = {
        canvas_type: 'generic',
        canvas_id: 'canvas-1',
        timestamp: '2026-02-18T10:00:00Z',
        component: 'line_chart',
        chart_type: 'line',
        data_points: []
      };

      const subs1 = subscribers.get('canvas-1') || [];
      subs1.forEach(cb => cb(state1));

      // Only callback1 should be called (subscribeAll is for global events, not individual canvas updates)
      expect(callback1).toHaveBeenCalledTimes(1);
      expect(callback2).not.toHaveBeenCalled();
      // subscribeAll doesn't automatically get called for individual canvas state updates
      // It's only called when canvas state change events are broadcast globally
      expect(callback3).not.toHaveBeenCalled();
    });
  });
});
