/**
 * useCanvasState Hook
 *
 * Provides access to canvas state API for components and AI agents.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import type {
  AnyCanvasState,
  CanvasStateAPI,
  CanvasStateChangeEvent
} from '@/components/canvas/types';

/**
 * Hook for accessing canvas state
 * @param canvasId - Optional canvas ID to filter for specific canvas
 * @returns Canvas state and API methods
 */
export function useCanvasState(canvasId?: string) {
  const [state, setState] = useState<AnyCanvasState | null>(null);
  const [allStates, setAllStates] = useState<Array<{ canvas_id: string; state: AnyCanvasState }>>([]);
  const unsubscribeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    // Initialize global API if not exists
    if (typeof window !== 'undefined' && !window.atom?.canvas) {
      (window as any).atom = {
        canvas: {
          getState: () => null,
          getAllStates: () => [],
          subscribe: () => () => {},
          subscribeAll: () => () => {}
        }
      };
    }

    const api = (window as any).atom?.canvas as CanvasStateAPI;
    if (!api) return;

    // Subscribe to specific canvas or all canvases
    if (canvasId) {
      unsubscribeRef.current = api.subscribe((newState) => {
        setState(newState);
      });
    } else {
      unsubscribeRef.current = api.subscribeAll((event: CanvasStateChangeEvent) => {
        setAllStates(prev => {
          const existing = prev.findIndex(s => s.canvas_id === event.canvas_id);
          if (existing >= 0) {
            const updated = [...prev];
            updated[existing] = { canvas_id: event.canvas_id, state: event.state };
            return updated;
          }
          return [...prev, { canvas_id: event.canvas_id, state: event.state }];
        });
      });
    }

    return () => {
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
      }
    };
  }, [canvasId]);

  const getState = useCallback((id: string) => {
    const api = (window as any).atom?.canvas as CanvasStateAPI;
    return api?.getState(id) || null;
  }, []);

  const getAllStates = useCallback(() => {
    const api = (window as any).atom?.canvas as CanvasStateAPI;
    return api?.getAllStates() || [];
  }, []);

  return {
    state,
    allStates,
    getState,
    getAllStates
  };
}

export default useCanvasState;
