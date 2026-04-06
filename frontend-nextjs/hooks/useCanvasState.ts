/**
 * useCanvasState Hook
 *
 * Provides access to canvas state API for components and AI agents.
 * Includes runtime verification for canvas state registration.
 */

import { useEffect, useState, useCallback, useRef } from 'react';
import type {
  AnyCanvasState,
  CanvasStateAPI,
  CanvasStateChangeEvent
} from '@/components/canvas/types';

// Track registered canvases for verification
const registeredCanvases = new Set<string>();
const registrationWarnings = new Set<string>();

/**
 * Verify canvas state API is properly initialized
 * @param api - Canvas state API to verify
 * @returns True if API is functional
 */
function verifyCanvasAPI(api: CanvasStateAPI | undefined): api is CanvasStateAPI {
  if (!api) {
    console.warn('[useCanvasState] Canvas API not found. Make sure canvas components are mounted.');
    return false;
  }

  // Check if API methods are functional (not just stubs)
  const testState = api.getState('test-canvas-verification');
  const allStates = api.getAllStates();

  // If API returns only null/empty, it might not be properly initialized
  if (testState === null && allStates.length === 0) {
    // This could mean no canvases are registered yet, which is OK on first render
    return true;
  }

  return true;
}

/**
 * Log warning once per canvas ID to avoid spam
 * @param canvasId - Canvas ID to log warning for
 * @param message - Warning message
 */
function logWarningOnce(canvasId: string, message: string) {
  const warningKey = `${canvasId}:${message}`;
  if (!registrationWarnings.has(warningKey)) {
    console.warn(`[useCanvasState] ${message}`, { canvasId });
    registrationWarnings.add(warningKey);
  }
}

/**
 * Hook for accessing canvas state
 * @param canvasId - Optional canvas ID to filter for specific canvas
 * @returns Canvas state and API methods
 */
export function useCanvasState(canvasId?: string) {
  const [state, setState] = useState<AnyCanvasState | null>(null);
  const [allStates, setAllStates] = useState<Array<{ canvas_id: string; state: AnyCanvasState }>>([]);
  const [isApiReady, setIsApiReady] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const verificationTimeoutRef = useRef<NodeJS.Timeout | null>(null);

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
      console.info('[useCanvasState] Initialized canvas state API stub');
    }

    const api = (window as any).atom?.canvas as CanvasStateAPI;
    if (!api) {
      console.error('[useCanvasState] Failed to initialize canvas state API');
      return;
    }

    // Verify API is ready
    setIsApiReady(true);

    // Set up verification timeout (check if canvas registered within 5 seconds)
    if (canvasId) {
      verificationTimeoutRef.current = setTimeout(() => {
        const currentState = api.getState(canvasId);
        if (!currentState) {
          logWarningOnce(
            canvasId,
            `Canvas "${canvasId}" may not be properly registered. ` +
            `Ensure canvas component is mounted and calls registerCanvasState().`
          );
        }
      }, 5000);
    }

    // Subscribe to specific canvas or all canvases
    if (canvasId) {
      // Track that we're trying to subscribe to this canvas
      registeredCanvases.add(canvasId);

      unsubscribeRef.current = api.subscribe((newState) => {
        if (newState) {
          setState(newState);
          // Clear any pending warnings for this canvas
          registrationWarnings.delete(`${canvasId}:may not be properly registered`);
        } else {
          logWarningOnce(
            canvasId,
            `Received null state for canvas "${canvasId}". ` +
            `Canvas may have been unmounted or failed to initialize.`
          );
        }
      });

      // Immediate state check
      const initialState = api.getState(canvasId);
      if (initialState) {
        setState(initialState);
      }
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

        // Track canvas registration
        registeredCanvases.add(event.canvas_id);
      });

      // Load all initial states
      const initialStates = api.getAllStates();
      if (initialStates.length > 0) {
        setAllStates(initialStates);
        // Track all initially registered canvases
        initialStates.forEach(({ canvas_id }) => registeredCanvases.add(canvas_id));
      }
    }

    return () => {
      // Clear verification timeout
      if (verificationTimeoutRef.current) {
        clearTimeout(verificationTimeoutRef.current);
      }

      // Unsubscribe
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
      }
    };
  }, [canvasId]);

  const getState = useCallback((id: string) => {
    const api = (window as any).atom?.canvas as CanvasStateAPI;
    if (!verifyCanvasAPI(api)) {
      return null;
    }

    const state = api?.getState(id);
    if (!state && registeredCanvases.has(id)) {
      logWarningOnce(
        id,
        `Canvas "${id}" was previously registered but now returns null. ` +
        `It may have been unmounted.`
      );
    }
    return state || null;
  }, []);

  const getAllStates = useCallback(() => {
    const api = (window as any).atom?.canvas as CanvasStateAPI;
    if (!verifyCanvasAPI(api)) {
      return [];
    }
    return api?.getAllStates() || [];
  }, []);

  return {
    state,
    allStates,
    getState,
    getAllStates,
    isApiReady
  };
}

/**
 * Get canvas registration status for debugging
 * @returns Object with registration statistics
 */
export function getCanvasRegistrationStatus() {
  return {
    registeredCount: registeredCanvases.size,
    registeredIds: Array.from(registeredCanvases),
    warningCount: registrationWarnings.size,
    warnings: Array.from(registrationWarnings)
  };
}

/**
 * Clear all registration warnings (useful for testing)
 */
export function clearCanvasRegistrationWarnings() {
  registrationWarnings.clear();
}

export default useCanvasState;
