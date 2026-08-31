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
  // Keep the latest state in a ref so we can update the registry WITHOUT
  // re-running the effect (and its cleanup) on every state reference change.
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => {
    ensureGlobalApi();

    // If canvasId changed, clean up the old registration.
    if (prevIdRef.current && prevIdRef.current !== canvasId) {
      delete _canvasRegistry[prevIdRef.current];
    }
    prevIdRef.current = canvasId;

    // Cleanup ONLY on unmount or canvasId change — NOT on every state update.
    // Previously `state` was in the deps array, so the cleanup ran on every
    // re-render, briefly deleting the registry entry and notifying null
    // (BUG-049: agents calling getState() during re-render saw null).
    return () => {
      delete _canvasRegistry[canvasId];
      _subscribers.forEach((cb) => cb(canvasId, null));
    };
  }, [canvasId]); // eslint-disable-line react-hooks/exhaustive-deps

  // Separate effect: update the registry when state changes, without the
  // unmount cleanup that caused the wipe-on-re-render.
  useEffect(() => {
    if (state) {
      _canvasRegistry[canvasId] = state;
    } else {
      delete _canvasRegistry[canvasId];
    }
    _subscribers.forEach((cb) => cb(canvasId, state));
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

/**
 * The open canvas as chat-message context — how ANY chat surface tells the
 * backend co-editor which canvas the user is looking at (the canvas page
 * sends the same fields explicitly). Reads the global registry, so it works
 * for every canvas app that registers, with no prop drilling.
 *
 * Skips placeholder registrations (no real canvas id yet) and the
 * view-orchestrator pseudo-canvas. Backend note: canvas_content here is a
 * best-effort snapshot — the orchestrator refreshes authoritative content
 * from the durable audit trail before planning.
 */
export function getOpenCanvasChatContext(): {
  canvas_id: string;
  canvas_type?: string;
  canvas_title?: string;
  canvas_content?: unknown;
} | null {
  for (const { canvas_id, state } of getAllCanvasStates()) {
    const s = state as any;
    if (!canvas_id || !s) continue;
    if (canvas_id.startsWith("canvas_") || canvas_id === "view_orchestrator") continue;
    return {
      canvas_id,
      canvas_type: s.type || s.component,
      canvas_title: s.title,
      canvas_content: s.data !== undefined ? s.data : s,
    };
  }
  return null;
}
