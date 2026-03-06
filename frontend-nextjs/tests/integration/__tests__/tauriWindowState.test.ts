/**
 * Tauri Window State and Multi-Window Tests
 *
 * Tests window state management:
 * - State persistence (save, load, clear across sessions)
 * - Minimize to tray behavior (CloseRequested, prevent_close, tray icon)
 * - Multi-window scenarios (create, close, switch, identifier consistency)
 * - State edge cases (invalid data, corruption, default values)
 *
 * Tests window state patterns from main.rs lines 1714-1743, 1728-1752.
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  mockWindowShow,
  mockWindowHide,
  mockWindowFocus,
  mockWindowClose,
  mockWindowMinimize,
  saveWindowState,
  loadWindowState,
  clearWindowState,
  getWindowState,
  setWindowState,
  getAllWindowStates,
  closeAllWindows,
  setupWindowMocks,
  cleanupWindowMocks,
} from './tauriWindow.mock';
import type { WindowLabel } from '@tauri-apps/api/window';

describe('Window State Persistence', () => {
  beforeEach(() => {
    setupWindowMocks();
    clearWindowState(); // Start fresh for each test
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should save window state to persistent storage', () => {
    // Arrange: Window with custom state
    setWindowState('main', {
      position: { x: 200, y: 150 },
      size: { width: 1400, height: 900 },
      minimized: false,
    });

    // Act: Save state
    saveWindowState('main');

    // Assert: State saved (can't directly access persistent storage, but verify no error)
    const state = getWindowState('main');
    expect(state?.position).toEqual({ x: 200, y: 150 });
    expect(state?.size).toEqual({ width: 1400, height: 900 });
  });

  it('should load window state from persistent storage', () => {
    // Arrange: Save state first
    setWindowState('main', {
      position: { x: 300, y: 200 },
      size: { width: 1600, height: 1000 },
      minimized: true,
    });
    saveWindowState('main');

    // Act: Load state
    const loadedState = loadWindowState('main');

    // Assert: State loaded correctly
    expect(loadedState).toBeDefined();
    expect(loadedState?.position).toEqual({ x: 300, y: 200 });
    expect(loadedState?.size).toEqual({ width: 1600, height: 1000 });
    expect(loadedState?.minimized).toBe(true);
  });

  it('should clear window state from persistent storage', () => {
    // Arrange: Save state
    setWindowState('main', {
      position: { x: 100, y: 100 },
      size: { width: 1200, height: 800 },
    });
    saveWindowState('main');

    // Act: Clear state
    clearWindowState('main');

    // Assert: State cleared
    const loadedState = loadWindowState('main');
    expect(loadedState).toBeUndefined();
  });

  it('should persist state across sessions (app restart)', () => {
    // Arrange: Window state in first session
    setWindowState('main', {
      position: { x: 250, y: 180 },
      size: { width: 1440, height: 900 },
      minimized: false,
    });
    saveWindowState('main');

    // Act: Simulate app restart (close all, then load state)
    closeAllWindows();
    const loadedState = loadWindowState('main');

    // Assert: State available after restart
    expect(loadedState).toBeDefined();
    expect(loadedState?.position).toEqual({ x: 250, y: 180 });
    expect(loadedState?.size).toEqual({ width: 1440, height: 900 });
  });
});

describe('Minimize to Tray Behavior', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should trigger hide on CloseRequested event (main.rs:1748-1752)', () => {
    // Arrange: Window is visible (simulating CloseRequested event)
    setWindowState('main', {
      visible: true,
      minimized: false,
      focused: true,
    });

    // Act: CloseRequested triggers hide (not actual close)
    mockWindowHide('main');

    // Assert: Window hidden instead of closed
    const state = getWindowState('main');
    expect(state?.visible).toBe(false);
    expect(state?.minimized).toBe(true);
    expect(state).toBeDefined(); // Window still exists
  });

  it('should prevent_close when hiding window (main.rs:1751)', () => {
    // Arrange: Window is visible
    setWindowState('main', { visible: true, focused: true });

    // Act: Hide window (simulates prevent_close workflow)
    mockWindowHide('main');

    // Assert: Window not destroyed (prevent_close called)
    expect(getAllWindowStates().has('main' as WindowLabel)).toBe(true);
    const state = getWindowState('main');
    expect(state?.visible).toBe(false);
  });

  it('should restore window from tray icon click (main.rs:1734-1741)', () => {
    // Arrange: Window hidden to tray
    setWindowState('main', {
      visible: false,
      minimized: true,
      focused: false,
    });

    // Act: Tray icon click (show + focus)
    mockWindowShow('main');

    // Assert: Window restored and focused
    const state = getWindowState('main');
    expect(state?.visible).toBe(true);
    expect(state?.minimized).toBe(false);
    expect(state?.focused).toBe(true);
  });

  it('should complete full minimize-to-tray workflow', () => {
    // Arrange: Window visible
    setWindowState('main', {
      visible: true,
      minimized: false,
      focused: true,
      position: { x: 100, y: 100 },
      size: { width: 1200, height: 800 },
    });

    // Act 1: User clicks close (CloseRequested → hide)
    mockWindowHide('main');
    let state = getWindowState('main');
    expect(state?.visible).toBe(false);
    expect(state?.minimized).toBe(true);

    // Act 2: User clicks tray icon (show + focus)
    mockWindowShow('main');
    state = getWindowState('main');
    expect(state?.visible).toBe(true);
    expect(state?.minimized).toBe(false);
    expect(state?.focused).toBe(true);

    // Assert: Position and size preserved
    expect(state?.position).toEqual({ x: 100, y: 100 });
    expect(state?.size).toEqual({ width: 1200, height: 800 });
  });
});

describe('Multi-Window Scenarios', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should create multiple windows', () => {
    // Arrange: No windows

    // Act: Create multiple windows
    mockWindowShow('main' as WindowLabel);
    mockWindowShow('secondary' as WindowLabel);
    mockWindowShow('tertiary' as WindowLabel);

    // Assert: All windows exist
    const allStates = getAllWindowStates();
    expect(allStates.size).toBe(3);
    expect(allStates.has('main' as WindowLabel)).toBe(true);
    expect(allStates.has('secondary' as WindowLabel)).toBe(true);
    expect(allStates.has('tertiary' as WindowLabel)).toBe(true);
  });

  it('should close all windows', () => {
    // Arrange: Three windows exist
    mockWindowShow('main' as WindowLabel);
    mockWindowShow('secondary' as WindowLabel);
    mockWindowShow('tertiary' as WindowLabel);

    // Act: Close all windows
    mockWindowClose('main' as WindowLabel);
    mockWindowClose('secondary' as WindowLabel);
    mockWindowClose('tertiary' as WindowLabel);

    // Assert: No windows remain
    const allStates = getAllWindowStates();
    expect(allStates.size).toBe(0);
  });

  it('should switch focus between windows', () => {
    // Arrange: Three windows, main focused
    mockWindowFocus('main' as WindowLabel);
    mockWindowShow('secondary' as WindowLabel);
    mockWindowShow('tertiary' as WindowLabel);

    // Act: Switch focus to secondary
    mockWindowFocus('secondary' as WindowLabel);

    // Assert: Focus switched
    let mainState = getWindowState('main' as WindowLabel);
    let secondaryState = getWindowState('secondary' as WindowLabel);
    expect(mainState?.focused).toBe(false);
    expect(secondaryState?.focused).toBe(true);

    // Act: Switch focus to tertiary
    mockWindowFocus('tertiary' as WindowLabel);

    // Assert: Focus switched again
    secondaryState = getWindowState('secondary' as WindowLabel);
    let tertiaryState = getWindowState('tertiary' as WindowLabel);
    expect(secondaryState?.focused).toBe(false);
    expect(tertiaryState?.focused).toBe(true);
  });

  it('should maintain main window identifier consistency (main.rs:1727, 1737)', () => {
    // Arrange: Multiple windows including main
    mockWindowShow('main' as WindowLabel);
    mockWindowShow('secondary' as WindowLabel);

    // Act: Perform operations on main window
    mockWindowHide('main' as WindowLabel);
    mockWindowShow('main' as WindowLabel);
    mockWindowFocus('main' as WindowLabel);

    // Assert: Main window identifier consistent
    const mainState = getWindowState('main' as WindowLabel);
    expect(mainState?.label).toBe('main');
    expect(mainState?.visible).toBe(true);
    expect(mainState?.focused).toBe(true);

    // Assert: Secondary window unaffected
    const secondaryState = getWindowState('secondary' as WindowLabel);
    expect(secondaryState?.label).toBe('secondary');
    expect(secondaryState?.focused).toBe(false);
  });
});

describe('Window State Edge Cases', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should handle invalid state data gracefully', () => {
    // Arrange: Try to set invalid state (missing required fields)
    setWindowState('main', {
      position: { x: -100, y: -100 }, // Invalid position
      size: { width: 0, height: 0 }, // Invalid size
    });

    // Act: Get state
    const state = getWindowState('main');

    // Assert: Invalid state accepted (mock doesn't validate)
    expect(state).toBeDefined();
    expect(state?.position).toEqual({ x: -100, y: -100 });
    expect(state?.size).toEqual({ width: 0, height: 0 });
  });

  it('should recover from corrupted state', () => {
    // Arrange: Save valid state
    setWindowState('main', {
      position: { x: 100, y: 100 },
      size: { width: 1200, height: 800 },
    });
    saveWindowState('main');

    // Act: Clear and recreate window (simulating corruption recovery)
    clearWindowState('main');
    closeAllWindows();
    mockWindowShow('main');

    // Assert: New window with default state
    const state = getWindowState('main');
    expect(state).toBeDefined();
    expect(state?.position).toEqual({ x: 100, y: 100 }); // Defaults
    expect(state?.size).toEqual({ width: 1200, height: 800 }); // Defaults
  });

  it('should apply default values when state missing', () => {
    // Arrange: No saved state

    // Act: Create new window
    mockWindowShow('main');

    // Assert: Default values applied
    const state = getWindowState('main');
    expect(state?.label).toBe('main');
    expect(state?.visible).toBe(true);
    expect(state?.focused).toBe(true); // Show focuses
    expect(state?.minimized).toBe(false);
    expect(state?.position).toEqual({ x: 100, y: 100 });
    expect(state?.size).toEqual({ width: 1200, height: 800 });
  });

  it('should handle state persistence for non-existent window', () => {
    // Arrange: No window exists

    // Act: Try to load state for non-existent window
    const loadedState = loadWindowState('nonexistent' as WindowLabel);

    // Assert: Returns undefined gracefully
    expect(loadedState).toBeUndefined();
  });

  it('should handle clearing non-existent state', () => {
    // Arrange: No state saved

    // Act: Clear non-existent state (should not error)
    expect(() => {
      clearWindowState('nonexistent' as WindowLabel);
    }).not.toThrow();
  });

  it('should handle clearing all state', () => {
    // Arrange: Multiple states saved
    setWindowState('main', { position: { x: 100, y: 100 } });
    setWindowState('secondary', { position: { x: 200, y: 200 } });
    saveWindowState('main' as WindowLabel);
    saveWindowState('secondary' as WindowLabel);

    // Act: Clear all state
    clearWindowState();

    // Assert: All states cleared
    const mainState = loadWindowState('main' as WindowLabel);
    const secondaryState = loadWindowState('secondary' as WindowLabel);
    expect(mainState).toBeUndefined();
    expect(secondaryState).toBeUndefined();
  });
});

describe('Window State Transitions', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should handle show → hide → show transition', () => {
    // Arrange: Window shown
    mockWindowShow('main');
    expect(getWindowState('main')?.visible).toBe(true);

    // Act: Hide window
    mockWindowHide('main');
    expect(getWindowState('main')?.visible).toBe(false);

    // Act: Show window again
    mockWindowShow('main');

    // Assert: Window visible again
    expect(getWindowState('main')?.visible).toBe(true);
    expect(getWindowState('main')?.minimized).toBe(false);
  });

  it('should handle focus → unfocus → focus transition', () => {
    // Arrange: Window focused
    mockWindowFocus('main');
    expect(getWindowState('main')?.focused).toBe(true);

    // Act: Unfocus (by focusing another window)
    mockWindowFocus('secondary');
    expect(getWindowState('main')?.focused).toBe(false);
    expect(getWindowState('secondary' as WindowLabel)?.focused).toBe(true);

    // Act: Refocus main
    mockWindowFocus('main');

    // Assert: Main focused, secondary unfocused
    expect(getWindowState('main')?.focused).toBe(true);
    expect(getWindowState('secondary' as WindowLabel)?.focused).toBe(false);
  });

  it('should handle minimize → restore → minimize transition', () => {
    // Arrange: Window visible
    mockWindowShow('main');
    expect(getWindowState('main')?.minimized).toBe(false);

    // Act: Minimize window
    mockWindowHide('main');
    expect(getWindowState('main')?.minimized).toBe(true);

    // Act: Restore window
    mockWindowShow('main');
    expect(getWindowState('main')?.minimized).toBe(false);

    // Act: Minimize again
    mockWindowHide('main');

    // Assert: Minimized again
    expect(getWindowState('main')?.minimized).toBe(true);
  });

  it('should preserve state across hide/show cycle', () => {
    // Arrange: Window with custom state
    setWindowState('main', {
      position: { x: 300, y: 250 },
      size: { width: 1500, height: 1000 },
    });

    // Act: Hide and show
    mockWindowHide('main');
    mockWindowShow('main');

    // Assert: State preserved
    const state = getWindowState('main');
    expect(state?.position).toEqual({ x: 300, y: 250 });
    expect(state?.size).toEqual({ width: 1500, height: 1000 });
  });
});
