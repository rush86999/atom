/**
 * useCanvasState Hook
 *
 * Provides access to canvas state API for components and AI agents.
 * Includes runtime verification for canvas state registration.
 */

import { useEffect, useCallback, useRef, useSyncExternalStore } from 'react';
import type {
  AgentOperationState,
  AnyCanvasState,
  CanvasStateAPI,
  CanvasStateChangeEvent,
  MatchConfidence
} from '@/components/canvas/types';

// Track registered canvases for verification
const registeredCanvases = new Set<string>();
const registrationWarnings = new Set<string>();
const canvasApiReadyListeners = new Set<() => void>();

function subscribeCanvasApiReady(onStoreChange: () => void) {
  canvasApiReadyListeners.add(onStoreChange);
  return () => canvasApiReadyListeners.delete(onStoreChange);
}

function getCanvasApiReady() {
  return typeof window !== 'undefined' && Boolean((window as any).atom?.canvas);
}

function getServerCanvasApiReady() {
  return false;
}

function ensureCanvasApi(): CanvasStateAPI | null {
  if (typeof window === 'undefined') return null;

  if (!(window as any).atom?.canvas) {
    (window as any).atom = {
      canvas: {
        getState: (): AnyCanvasState | null => null,
        getAllStates: (): Array<{ canvas_id: string; state: AnyCanvasState }> => [],
        subscribe: () => () => {},
        subscribeAll: () => () => {}
      }
    };
    console.info('[useCanvasState] Initialized canvas state API stub');
    canvasApiReadyListeners.forEach((listener) => listener());
  }

  return (window as any).atom?.canvas as CanvasStateAPI | null;
}

type CanvasApiStore = {
  states: Map<string, AnyCanvasState | null>;
  allStates: Array<{ canvas_id: string; state: AnyCanvasState }>;
  initializedAllStates: boolean;
  listeners: Set<() => void>;
};

const canvasApiStores = new WeakMap<CanvasStateAPI, CanvasApiStore>();
const subscribeToNothing = (): (() => void) => () => {};
const getServerNull = (): null => null;
const EMPTY_CANVAS_STATES: Array<{ canvas_id: string; state: AnyCanvasState }> = [];
const getServerEmptyArray = () => EMPTY_CANVAS_STATES;

function getCanvasApiStore(api: CanvasStateAPI): CanvasApiStore {
  let store = canvasApiStores.get(api);
  if (!store) {
    store = {
      states: new Map(),
      allStates: [],
      initializedAllStates: false,
      listeners: new Set(),
    };
    canvasApiStores.set(api, store);
  }
  return store;
}

function notifyCanvasStore(store: CanvasApiStore) {
  store.listeners.forEach((listener) => listener());
}

function getCanvasStateSnapshot(api: CanvasStateAPI, canvasId: string) {
  const store = getCanvasApiStore(api);
  if (!store.states.has(canvasId)) {
    store.states.set(canvasId, api.getState(canvasId));
    registeredCanvases.add(canvasId);
  }
  return store.states.get(canvasId) ?? null;
}

function subscribeCanvasState(
  api: CanvasStateAPI,
  canvasId: string,
  onStoreChange: () => void
) {
  const store = getCanvasApiStore(api);
  store.listeners.add(onStoreChange);
  try {
    const subscribeSingle = (api.subscribe.bind(api) as unknown) as (
      callback: (newState: AnyCanvasState | null) => void
    ) => () => void;
    const unsubscribe = subscribeSingle((newState) => {
      if (newState) {
        store.states.set(canvasId, newState);
        registeredCanvases.add(canvasId);
        registrationWarnings.delete(`${canvasId}:may not be properly registered`);
        notifyCanvasStore(store);
        return;
      }
      logWarningOnce(
        canvasId,
        `Received null state for canvas "${canvasId}". ` +
        `Canvas may have been unmounted or failed to initialize.`
      );
    });
    return () => {
      store.listeners.delete(onStoreChange);
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  } catch {
    store.listeners.delete(onStoreChange);
    logWarningOnce(canvasId, `Failed to subscribe to canvas "${canvasId}".`);
    return subscribeToNothing();
  }
}

function getAllCanvasStateSnapshot(api: CanvasStateAPI) {
  const store = getCanvasApiStore(api);
  if (!store.initializedAllStates) {
    store.allStates = api.getAllStates() || [];
    store.initializedAllStates = true;
    store.allStates.forEach(({ canvas_id }) => registeredCanvases.add(canvas_id));
  }
  return store.allStates;
}

function subscribeAllCanvasState(api: CanvasStateAPI, onStoreChange: () => void) {
  const store = getCanvasApiStore(api);
  store.listeners.add(onStoreChange);
  try {
    const unsubscribe = api.subscribeAll((event: CanvasStateChangeEvent) => {
      const existing = store.allStates.findIndex(
        (entry) => entry.canvas_id === event.canvas_id
      );
      if (existing >= 0) {
        const updated = [...store.allStates];
        updated[existing] = { canvas_id: event.canvas_id, state: event.state };
        store.allStates = updated;
      } else {
        store.allStates = [...store.allStates, { canvas_id: event.canvas_id, state: event.state }];
      }
      registeredCanvases.add(event.canvas_id);
      notifyCanvasStore(store);
    });
    return () => {
      store.listeners.delete(onStoreChange);
      if (typeof unsubscribe === 'function') unsubscribe();
    };
  } catch {
    store.listeners.delete(onStoreChange);
    logWarningOnce('*', 'Failed to subscribe to all canvases.');
    return subscribeToNothing();
  }
}

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

  // Check if API methods are present
  return (
    typeof api.getState === 'function' &&
    typeof api.getAllStates === 'function' &&
    typeof api.subscribe === 'function' &&
    typeof api.subscribeAll === 'function'
  );
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
  const isApiReady = useSyncExternalStore(
    subscribeCanvasApiReady,
    getCanvasApiReady,
    getServerCanvasApiReady
  );
  const api = typeof window !== 'undefined'
    ? ((window as any).atom?.canvas as CanvasStateAPI | undefined)
    : undefined;
  const state = useSyncExternalStore(
    useCallback(
      (onStoreChange: () => void) => canvasId && api
        ? subscribeCanvasState(api, canvasId, onStoreChange)
        : subscribeToNothing(),
      [api, canvasId]
    ),
    useCallback(
      () => canvasId && api ? getCanvasStateSnapshot(api, canvasId) : null,
      [api, canvasId]
    ),
    getServerNull
  );
  const allStates = useSyncExternalStore(
    useCallback(
      (onStoreChange: () => void) => !canvasId && api
        ? subscribeAllCanvasState(api, onStoreChange)
        : subscribeToNothing(),
      [api, canvasId]
    ),
    useCallback(
      () => !canvasId && api ? getAllCanvasStateSnapshot(api) : EMPTY_CANVAS_STATES,
      [api, canvasId]
    ),
    getServerEmptyArray
  );
  const verificationTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const api = ensureCanvasApi();
    if (!api) {
      console.error('[useCanvasState] Failed to initialize canvas state API');
      return;
    }

    if (canvasId) {
      registeredCanvases.add(canvasId);
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

    return () => {
      if (verificationTimeoutRef.current) {
        clearTimeout(verificationTimeoutRef.current);
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

  /**
   * Phase 5 — pre-action match-confidence accessor.
   * Mirrors getState() but extracts the match_confidence block from an
   * AgentOperationState. Returns null for non-agent-operation canvases
   * or when the locator API is off.
   */
  const getMatchConfidence = useCallback((opId: string): MatchConfidence | null => {
    const api = (window as any).atom?.canvas as CanvasStateAPI;
    if (!verifyCanvasAPI(api)) {
      return null;
    }
    const state = api?.getState(opId) as (AgentOperationState | null);
    return state?.match_confidence ?? null;
  }, []);

  return {
    state,
    allStates,
    getState,
    getAllStates,
    getMatchConfidence,
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
