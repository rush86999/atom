/**
 * Tauri Window Management Mock
 *
 * Provides mock implementations for Tauri window operations including:
 * - Window show/hide/focus/close operations
 * - Window state tracking (visibility, focus, minimize, position, size)
 * - State persistence (save/load/clear)
 * - Multi-window management
 *
 * Tests window operations from main.rs lines 1728-1739, 1748-1752.
 */

import { mockIPC } from '@tauri-apps/api/mocks';
import type { WindowLabel } from '@tauri-apps/api/window';

/**
 * Window state tracking structure
 */
interface WindowState {
  label: string;
  visible: boolean;
  focused: boolean;
  minimized: boolean;
  position: { x: number; y: number };
  size: { width: number; height: number };
}

/**
 * In-memory window state storage
 * Simulates window state across the application lifecycle
 */
const windowStates: Map<WindowLabel, WindowState> = new Map();

/**
 * Persistent storage simulation for window state
 * Simulates localStorage or file-based persistence
 */
const persistentWindowState: Map<WindowLabel, Partial<WindowState>> = new Map();

/**
 * Default window state for newly created windows
 */
const DEFAULT_WINDOW_STATE: WindowState = {
  label: 'main',
  visible: true,
  focused: false,
  minimized: false,
  position: { x: 100, y: 100 },
  size: { width: 1200, height: 800 },
};

/**
 * Get or create window state
 */
function getOrCreateWindowState(label: WindowLabel): WindowState {
  if (!windowStates.has(label)) {
    windowStates.set(label, { ...DEFAULT_WINDOW_STATE, label });
  }
  return windowStates.get(label)!;
}

/**
 * Simulate window.show() operation
 * Corresponds to main.rs:1728, 1737 (tray icon show window)
 *
 * @param windowLabel - Window identifier (default: 'main')
 */
export function mockWindowShow(windowLabel: WindowLabel = 'main'): void {
  const state = getOrCreateWindowState(windowLabel);
  state.visible = true;
  state.minimized = false; // Show restores from minimized state

  // Show automatically focuses window (common desktop behavior)
  mockWindowFocus(windowLabel);
}

/**
 * Simulate window.hide() operation
 * Corresponds to main.rs:1750 (minimize to tray behavior)
 *
 * @param windowLabel - Window identifier (default: 'main')
 */
export function mockWindowHide(windowLabel: WindowLabel = 'main'): void {
  const state = getOrCreateWindowState(windowLabel);
  state.visible = false;
  state.focused = false;
  state.minimized = true; // Hide typically minimizes
}

/**
 * Simulate window.set_focus() operation
 * Corresponds to main.rs:1729, 1739 (focus window from tray)
 *
 * @param windowLabel - Window identifier (default: 'main')
 */
export function mockWindowFocus(windowLabel: WindowLabel = 'main'): void {
  // Unfocus all other windows first
  windowStates.forEach((state) => {
    state.focused = false;
  });

  // Focus the specified window
  const state = getOrCreateWindowState(windowLabel);
  state.visible = true; // Focus typically shows window
  state.focused = true;
  state.minimized = false;
}

/**
 * Simulate window.close() operation
 * Removes window from tracking (destroy)
 *
 * @param windowLabel - Window identifier (default: 'main')
 */
export function mockWindowClose(windowLabel: WindowLabel = 'main'): void {
  windowStates.delete(windowLabel);
}

/**
 * Simulate window.minimize() operation
 * Minimizes window without hiding (e.g., to taskbar)
 *
 * @param windowLabel - Window identifier (default: 'main')
 */
export function mockWindowMinimize(windowLabel: WindowLabel = 'main'): void {
  const state = getOrCreateWindowState(windowLabel);
  state.minimized = true;
  state.focused = false;
}

/**
 * Simulate window.maximize() operation
 *
 * @param windowLabel - Window identifier (default: 'main')
 */
export function mockWindowMaximize(windowLabel: WindowLabel = 'main'): void {
  const state = getOrCreateWindowState(windowLabel);
  state.minimized = false;
  state.size = { width: 1920, height: 1080 }; // Typical max resolution
  state.visible = true;
}

/**
 * Save window state to persistent storage
 * Simulates saving window position, size, and state
 *
 * @param windowLabel - Window identifier (default: 'main')
 */
export function saveWindowState(windowLabel: WindowLabel = 'main'): void {
  const state = windowStates.get(windowLabel);
  if (state) {
    persistentWindowState.set(windowLabel, {
      position: state.position,
      size: state.size,
      minimized: state.minimized,
    });
  }
}

/**
 * Load window state from persistent storage
 * Simulates restoring window state on app startup
 *
 * @param windowLabel - Window identifier (default: 'main')
 * @returns Saved state or undefined if not found
 */
export function loadWindowState(
  windowLabel: WindowLabel = 'main'
): Partial<WindowState> | undefined {
  return persistentWindowState.get(windowLabel);
}

/**
 * Clear window state from persistent storage
 * Simulates logout/reset scenario
 *
 * @param windowLabel - Window identifier (default: 'main')
 */
export function clearWindowState(windowLabel?: WindowLabel): void {
  if (windowLabel) {
    persistentWindowState.delete(windowLabel);
  } else {
    persistentWindowState.clear();
  }
}

/**
 * Get current window state
 *
 * @param windowLabel - Window identifier
 * @returns Current window state or undefined
 */
export function getWindowState(
  windowLabel: WindowLabel
): WindowState | undefined {
  return windowStates.get(windowLabel);
}

/**
 * Set window state properties
 * Useful for test setup scenarios
 *
 * @param windowLabel - Window identifier
 * @param state - Partial state to update
 */
export function setWindowState(
  windowLabel: WindowLabel,
  state: Partial<WindowState>
): void {
  const currentState = getOrCreateWindowState(windowLabel);
  windowStates.set(windowLabel, { ...currentState, ...state });
}

/**
 * Get all tracked window states
 *
 * @returns Map of all window states
 */
export function getAllWindowStates(): Map<WindowLabel, WindowState> {
  return new Map(windowStates);
}

/**
 * Close all tracked windows
 * Useful for test cleanup
 */
export function closeAllWindows(): void {
  windowStates.clear();
}

/**
 * Setup window mocks for testing
 * Configures IPC mocks for window operations
 */
export function setupWindowMocks(): void {
  mockIPC((cmd, payload) => {
    switch (cmd) {
      case 'plugin:window|show':
        mockWindowShow(payload as WindowLabel);
        return { success: true };

      case 'plugin:window|hide':
        mockWindowHide(payload as WindowLabel);
        return { success: true };

      case 'plugin:window|focus':
        mockWindowFocus(payload as WindowLabel);
        return { success: true };

      case 'plugin:window|close':
        mockWindowClose(payload as WindowLabel);
        return { success: true };

      case 'plugin:window|minimize':
        mockWindowMinimize(payload as WindowLabel);
        return { success: true };

      case 'plugin:window|maximize':
        mockWindowMaximize(payload as WindowLabel);
        return { success: true };

      case 'plugin:window|save_state':
        saveWindowState(payload as WindowLabel);
        return { success: true };

      case 'plugin:window|load_state':
        const state = loadWindowState(payload as WindowLabel);
        return { success: true, state };

      case 'plugin:window|clear_state':
        clearWindowState(payload as WindowLabel);
        return { success: true };

      default:
        return { success: false, error: 'Unknown command' };
    }
  });
}

/**
 * Cleanup all window state
 * Resets all tracking to initial state
 */
export function cleanupWindowMocks(): void {
  windowStates.clear();
  persistentWindowState.clear();
}

/**
 * Mock getCurrentWindow for window API calls
 * Returns a mock window object
 */
export function mockGetCurrentWindow(label: WindowLabel = 'main') {
  return {
    label,
    show: () => mockWindowShow(label),
    hide: () => mockWindowHide(label),
    setFocus: () => mockWindowFocus(label),
    close: () => mockWindowClose(label),
    minimize: () => mockWindowMinimize(label),
    maximize: () => mockWindowMaximize(label),
    getState: () => getWindowState(label),
  };
}
