/**
 * Reusable hook for registering canvas state into window.atom.canvas.
 *
 * Any component rendering a canvas can call this to make its state visible
 * to AI agents via `window.atom.canvas.getState(canvasId)`. This eliminates
 * the boilerplate monkey-patch pattern used in BarChart/LineChart/etc.
 *
 * Usage:
 *   const canvasId = "sheet_1";
 *   useCanvasStateRegistration(canvasId, {
 *     type: 'sheets',
 *     cells: sheetData,
 *     activeCell: 'B2',
 *     sheetName: 'Sheet1'
 *   });
 *
 * The state updates whenever the `state` argument changes (by reference).
 * On unmount, the registration is automatically cleaned up.
 */

import { useEffect, useRef } from 'react';
import type { AnyCanvasState } from '@/components/canvas/types';

// Global registry: canvasId -> state. Lives outside React so getState() is synchronous.
const _canvasRegistry: Record<string, AnyCanvasState> = {};

// Subscribers for state changes.
type Subscriber = (canvasId: string, state: AnyCanvasState | null) => void;
const _subscribers: Set<Subscriber> = new Set();

/**
 * Ensure the global window.atom.canvas API exists with our registry.
 * Called once on first registration.
 */
function ensureGlobalApi(): void {
  if (typeof window === 'undefined') return;

  if (!(window as any).atom?.canvas) {
    (window as any).atom = {
      canvas: {
        getState: (id?: string) => {
          if (id) return _canvasRegistry[id] || null;
          // No ID: return the first registered state (backward compat).
          const keys = Object.keys(_canvasRegistry);
          return keys.length > 0 ? _canvasRegistry[keys[0]] : null;
        },
        getAllStates: () => {
          return Object.entries(_canvasRegistry).map(([canvasId, state]) => ({
            canvas_id: canvasId,
            state,
          }));
        },
        subscribe: (id: string, cb: Subscriber) => {
          _subscribers.add(cb);
          return () => { _subscribers.delete(cb); };
        },
        subscribeAll: (cb: Subscriber) => {
          _subscribers.add(cb);
          return () => { _subscribers.delete(cb); };
        },
      },
    };
  }
}

/**
 * Register a canvas's state so agents can read it via getState().
 *
 * @param canvasId Unique canvas identifier.
 * @param state The canvas state object (type depends on canvas type).
 */
export function useCanvasStateRegistration(
  canvasId: string,
  state: AnyCanvasState | null,
): void {
  const prevIdRef = useRef<string | null>(null);

  useEffect(() => {
    ensureGlobalApi();

    // If canvasId changed, clean up the old registration.
    if (prevIdRef.current && prevIdRef.current !== canvasId) {
      delete _canvasRegistry[prevIdRef.current];
    }
    prevIdRef.current = canvasId;

    // Register or update the state.
    if (state) {
      _canvasRegistry[canvasId] = state;
    } else {
      delete _canvasRegistry[canvasId];
    }

    // Notify subscribers.
    _subscribers.forEach((cb) => cb(canvasId, state));

    // Cleanup on unmount.
    return () => {
      delete _canvasRegistry[canvasId];
      _subscribers.forEach((cb) => cb(canvasId, null));
    };
  }, [canvasId, state]);
}

/**
 * Get the current state of a canvas by ID (synchronous, for non-React callers).
 */
export function getCanvasState(canvasId: string): AnyCanvasState | null {
  return _canvasRegistry[canvasId] || null;
}

/**
 * Get all registered canvas states.
 */
export function getAllCanvasStates(): Array<{ canvas_id: string; state: AnyCanvasState }> {
  return Object.entries(_canvasRegistry).map(([canvas_id, state]) => ({ canvas_id, state }));
}
