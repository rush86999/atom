/**
 * Tauri Window Management Operation Tests
 *
 * Tests window lifecycle operations:
 * - Show operations (from hidden, from tray, with focus)
 * - Hide operations (to tray, prevent close, idempotent)
 * - Focus operations (bring to front, switch windows, after show)
 * - Close operations (destroy window, cleanup)
 *
 * Tests window operations from main.rs lines 1728-1739, 1748-1752.
 */

import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import {
  mockWindowShow,
  mockWindowHide,
  mockWindowFocus,
  mockWindowClose,
  mockWindowMinimize,
  getWindowState,
  setWindowState,
  getAllWindowStates,
  closeAllWindows,
  setupWindowMocks,
  cleanupWindowMocks,
} from './tauriWindow.mock';
import type { WindowLabel } from '@tauri-apps/api/window';

describe('Window Show Operations', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should show window from hidden state', () => {
    // Arrange: Window is hidden
    setWindowState('main', { visible: false, minimized: true });

    // Act: Show window
    mockWindowShow('main');

    // Assert: Window is visible and not minimized
    const state = getWindowState('main');
    expect(state).toBeDefined();
    expect(state?.visible).toBe(true);
    expect(state?.minimized).toBe(false);
    expect(state?.focused).toBe(true); // Show also focuses
  });

  it('should be idempotent when showing already visible window', () => {
    // Arrange: Window is already visible
    setWindowState('main', {
      visible: true,
      minimized: false,
      focused: true,
      position: { x: 100, y: 100 },
      size: { width: 1200, height: 800 },
    });

    // Act: Show window again
    mockWindowShow('main');

    // Assert: State remains consistent
    const state = getWindowState('main');
    expect(state?.visible).toBe(true);
    expect(state?.minimized).toBe(false);
    expect(state?.focused).toBe(true);
  });

  it('should show window with focus option', () => {
    // Arrange: Window is hidden and unfocused
    setWindowState('main', { visible: false, focused: false });

    // Act: Show window (show implicitly focuses)
    mockWindowShow('main');

    // Assert: Window is visible and focused
    const state = getWindowState('main');
    expect(state?.visible).toBe(true);
    expect(state?.focused).toBe(true);
  });

  it('should show window from minimized state (tray icon)', () => {
    // Arrange: Window is minimized to tray (main.rs:1737)
    setWindowState('main', {
      visible: false,
      minimized: true,
      focused: false,
    });

    // Act: Show window from tray
    mockWindowShow('main');

    // Assert: Window restored from tray
    const state = getWindowState('main');
    expect(state?.visible).toBe(true);
    expect(state?.minimized).toBe(false); // No longer minimized
    expect(state?.focused).toBe(true); // Also focused (main.rs:1739)
  });
});

describe('Window Hide Operations', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should hide window from visible state', () => {
    // Arrange: Window is visible
    setWindowState('main', {
      visible: true,
      minimized: false,
      focused: true,
    });

    // Act: Hide window
    mockWindowHide('main');

    // Assert: Window is hidden and minimized
    const state = getWindowState('main');
    expect(state?.visible).toBe(false);
    expect(state?.minimized).toBe(true); // Hide minimizes
    expect(state?.focused).toBe(false); // Lost focus
  });

  it('should minimize window to tray (main.rs:1750)', () => {
    // Arrange: Window is visible
    setWindowState('main', { visible: true, minimized: false });

    // Act: Hide window (minimize to tray)
    mockWindowHide('main');

    // Assert: Window minimized to tray
    const state = getWindowState('main');
    expect(state?.visible).toBe(false);
    expect(state?.minimized).toBe(true);
  });

  it('should be idempotent when hiding already hidden window', () => {
    // Arrange: Window is already hidden
    setWindowState('main', {
      visible: false,
      minimized: true,
      focused: false,
    });

    // Act: Hide window again
    mockWindowHide('main');

    // Assert: State remains consistent
    const state = getWindowState('main');
    expect(state?.visible).toBe(false);
    expect(state?.minimized).toBe(true);
    expect(state?.focused).toBe(false);
  });

  it('should hide window before prevent_close (main.rs:1750)', () => {
    // Arrange: Window is visible
    setWindowState('main', { visible: true, focused: true });

    // Act: Hide window (simulates CloseRequested → prevent_close workflow)
    mockWindowHide('main');

    // Assert: Window hidden instead of closed
    const state = getWindowState('main');
    expect(state?.visible).toBe(false);
    expect(state?.minimized).toBe(true);
    // Window still exists in tracking (not closed)
    expect(getAllWindowStates().has('main' as WindowLabel)).toBe(true);
  });
});

describe('Window Focus Operations', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should bring window to front on focus', () => {
    // Arrange: Window exists but not focused
    setWindowState('main', {
      visible: true,
      focused: false,
      minimized: false,
    });

    // Act: Focus window
    mockWindowFocus('main');

    // Assert: Window is focused and visible
    const state = getWindowState('main');
    expect(state?.focused).toBe(true);
    expect(state?.visible).toBe(true);
    expect(state?.minimized).toBe(false);
  });

  it('should be idempotent when focusing already focused window', () => {
    // Arrange: Window is already focused
    setWindowState('main', { focused: true, visible: true });

    // Act: Focus window again
    mockWindowFocus('main');

    // Assert: State remains consistent
    const state = getWindowState('main');
    expect(state?.focused).toBe(true);
    expect(state?.visible).toBe(true);
  });

  it('should focus window after show (main.rs:1729, 1739)', () => {
    // Arrange: Window is hidden
    setWindowState('main', { visible: false, focused: false });

    // Act: Show window (which implicitly focuses)
    mockWindowShow('main');

    // Assert: Window is focused after show
    const state = getWindowState('main');
    expect(state?.visible).toBe(true);
    expect(state?.focused).toBe(true);
  });

  it('should switch focus between multiple windows', () => {
    // Arrange: Two windows, second is focused
    setWindowState('main', { focused: false });
    setWindowState('secondary', { focused: true });

    // Act: Focus main window
    mockWindowFocus('main');

    // Assert: Main window focused, secondary unfocused
    const mainState = getWindowState('main');
    const secondaryState = getWindowState('secondary');
    expect(mainState?.focused).toBe(true);
    expect(secondaryState?.focused).toBe(false);
  });
});

describe('Window Close Operations', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should destroy window on close', () => {
    // Arrange: Window exists
    setWindowState('main', {
      visible: true,
      focused: true,
      minimized: false,
    });

    // Act: Close window
    mockWindowClose('main');

    // Assert: Window removed from tracking
    const state = getWindowState('main');
    expect(state).toBeUndefined();
    expect(getAllWindowStates().has('main' as WindowLabel)).toBe(false);
  });

  it('should close main window', () => {
    // Arrange: Main window exists
    setWindowState('main', {
      label: 'main',
      visible: true,
      focused: true,
    });

    // Act: Close main window
    mockWindowClose('main');

    // Assert: Main window destroyed
    const allStates = getAllWindowStates();
    expect(allStates.has('main' as WindowLabel)).toBe(false);
    expect(allStates.size).toBe(0);
  });

  it('should cleanup all windows on close', () => {
    // Arrange: Multiple windows exist
    setWindowState('main', { visible: true });
    setWindowState('secondary', { visible: true });
    setWindowState('tertiary', { visible: true });

    // Act: Close all windows
    mockWindowClose('main');
    mockWindowClose('secondary');
    mockWindowClose('tertiary');

    // Assert: All windows removed
    const allStates = getAllWindowStates();
    expect(allStates.size).toBe(0);
  });
});

describe('Window Minimize Operations', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should minimize window without hiding', () => {
    // Arrange: Window is visible
    setWindowState('main', {
      visible: true,
      minimized: false,
      focused: true,
    });

    // Act: Minimize window
    mockWindowMinimize('main');

    // Assert: Window minimized but visible (taskbar behavior)
    const state = getWindowState('main');
    expect(state?.minimized).toBe(true);
    expect(state?.focused).toBe(false);
    expect(state?.visible).toBe(true); // Still visible (taskbar)
  });

  it('should restore from minimized state on show', () => {
    // Arrange: Window is minimized
    setWindowState('main', {
      visible: false,
      minimized: true,
      focused: false,
    });

    // Act: Show window (restores from minimize)
    mockWindowShow('main');

    // Assert: Window no longer minimized
    const state = getWindowState('main');
    expect(state?.minimized).toBe(false);
    expect(state?.visible).toBe(true);
    expect(state?.focused).toBe(true);
  });

  it('should minimize multiple windows independently', () => {
    // Arrange: Two windows visible
    setWindowState('main', { visible: true, minimized: false });
    setWindowState('secondary', { visible: true, minimized: false });

    // Act: Minimize only main window
    mockWindowMinimize('main');

    // Assert: Only main minimized
    const mainState = getWindowState('main');
    const secondaryState = getWindowState('secondary');
    expect(mainState?.minimized).toBe(true);
    expect(secondaryState?.minimized).toBe(false);
  });

  it('should unfocus window on minimize', () => {
    // Arrange: Window is focused
    setWindowState('main', { focused: true, minimized: false });

    // Act: Minimize window
    mockWindowMinimize('main');

    // Assert: Window lost focus
    const state = getWindowState('main');
    expect(state?.focused).toBe(false);
  });
});

describe('Window Operation Edge Cases', () => {
  beforeEach(() => {
    setupWindowMocks();
  });

  afterEach(() => {
    closeAllWindows();
    cleanupWindowMocks();
  });

  it('should handle operations on non-existent window', () => {
    // Arrange: Window doesn't exist
    const beforeSize = getAllWindowStates().size;

    // Act: Try to focus non-existent window (creates it)
    mockWindowFocus('nonexistent' as WindowLabel);

    // Assert: Window created with default state
    const afterSize = getAllWindowStates().size;
    expect(afterSize).toBe(beforeSize + 1);
    const state = getWindowState('nonexistent' as WindowLabel);
    expect(state).toBeDefined();
    expect(state?.focused).toBe(true);
  });

  it('should maintain default window properties', () => {
    // Arrange: No window setup

    // Act: Create window via operation
    mockWindowShow('main');

    // Assert: Default properties applied
    const state = getWindowState('main');
    expect(state?.position).toEqual({ x: 100, y: 100 });
    expect(state?.size).toEqual({ width: 1200, height: 800 });
    expect(state?.label).toBe('main');
  });

  it('should handle rapid show/hide operations', () => {
    // Arrange: Window visible
    setWindowState('main', { visible: true });

    // Act: Rapid show/hide sequence
    mockWindowHide('main');
    mockWindowShow('main');
    mockWindowHide('main');
    mockWindowShow('main');

    // Assert: Final state consistent
    const state = getWindowState('main');
    expect(state?.visible).toBe(true);
    expect(state?.minimized).toBe(false);
  });

  it('should handle focus after close', () => {
    // Arrange: Window exists
    setWindowState('main', { visible: true, focused: true });

    // Act: Close then try to focus
    mockWindowClose('main');
    mockWindowFocus('main');

    // Assert: Window recreated with focus
    const state = getWindowState('main');
    expect(state).toBeDefined();
    expect(state?.focused).toBe(true);
  });
});
