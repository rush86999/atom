/**
 * useCanvasState Branch Coverage Tests (wave 119)
 *
 * Closes the remaining gaps in useCanvasState.ts:
 * - verifyCanvasAPI false path (no window.atom.canvas) → getState /
 *   getAllStates / getMatchConfidence guards (lines 28-29, 179, 196, 210)
 * - stub API initialization when window.atom is absent (line 73)
 * - window.atom present but atom.canvas missing → console.error early return
 *   (lines 82-83)
 * - 5s registration-verification timeout warning (lines 92-94)
 * - "previously registered but now returns null" warning (line 184)
 * - getCanvasRegistrationStatus / clearCanvasRegistrationWarnings
 *   (lines 231, 243)
 */

import { renderHook, act } from '@testing-library/react';
import { useCanvasState, getCanvasRegistrationStatus, clearCanvasRegistrationWarnings } from '../useCanvasState';

const originalAtom = (window as any).atom;

function installApi(api: Partial<Record<string, any>>) {
  (window as any).atom = { canvas: api };
}

const fullApi = {
  getState: jest.fn(() => null),
  getAllStates: jest.fn(() => []),
  subscribe: jest.fn(() => jest.fn()),
  subscribeAll: jest.fn(() => jest.fn()),
};

describe('useCanvasState - Branch Coverage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    installApi(fullApi);
  });

  afterEach(() => {
    if (originalAtom === undefined) {
      delete (window as any).atom;
    } else {
      (window as any).atom = originalAtom;
    }
  });

  // A getter-only window.atom makes the hook's stub assignment silently
  // no-op (sloppy-mode), leaving the canvas API genuinely unavailable — the
  // only way verifyCanvasAPI/!api guard paths are reachable in a browser env.
  function makeAtomUnassignable() {
    Object.defineProperty(window, 'atom', {
      get: () => undefined,
      configurable: true,
    });
  }

  test('getState returns null and warns when the canvas API is missing', () => {
    makeAtomUnassignable();
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();
    const errorSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() => useCanvasState());

    act(() => {
      expect(result.current.getState('canvas-1')).toBeNull();
    });

    expect(warnSpy).toHaveBeenCalledWith(
      '[useCanvasState] Canvas API not found. Make sure canvas components are mounted.'
    );
    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });

  test('getAllStates returns [] when the canvas API is missing', () => {
    makeAtomUnassignable();
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();
    const errorSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() => useCanvasState());

    act(() => {
      expect(result.current.getAllStates()).toEqual([]);
    });

    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });

  test('getMatchConfidence returns null when the canvas API is missing', () => {
    makeAtomUnassignable();
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();
    const errorSpy = jest.spyOn(console, 'error').mockImplementation();

    const { result } = renderHook(() => useCanvasState());

    act(() => {
      expect(result.current.getMatchConfidence('op-1')).toBeNull();
    });

    expect(warnSpy).toHaveBeenCalled();
    warnSpy.mockRestore();
    errorSpy.mockRestore();
  });

  test('initializes the canvas state API stub when window.atom is absent', () => {
    delete (window as any).atom;
    const infoSpy = jest.spyOn(console, 'info').mockImplementation();

    // Render WITH a canvasId so the stub's subscribe() is exercised too
    const { result } = renderHook(() => useCanvasState('canvas-stub'));

    expect((window as any).atom?.canvas).toBeDefined();
    expect((window as any).atom.canvas.subscribe).toBeInstanceOf(Function);
    expect((window as any).atom.canvas.subscribeAll).toBeInstanceOf(Function);
    expect(result.current.isApiReady).toBe(true);
    expect(infoSpy).toHaveBeenCalledWith(
      '[useCanvasState] Initialized canvas state API stub'
    );
    infoSpy.mockRestore();
  });

  test('logs an error when window.atom exists without a canvas API', () => {
    makeAtomUnassignable();
    const errorSpy = jest.spyOn(console, 'error').mockImplementation();
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();

    const { result } = renderHook(() => useCanvasState());

    expect(errorSpy).toHaveBeenCalledWith(
      '[useCanvasState] Failed to initialize canvas state API'
    );
    expect(result.current.isApiReady).toBe(false);
    expect(result.current.state).toBeNull();
    errorSpy.mockRestore();
    warnSpy.mockRestore();
  });

  test('warns when a canvas is not registered within the verification window', () => {
    jest.useFakeTimers();
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();

    installApi({
      ...fullApi,
      getState: jest.fn(() => null),
    });

    const { unmount } = renderHook(() => useCanvasState('canvas-unregistered'));

    act(() => {
      jest.advanceTimersByTime(5000);
    });

    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('may not be properly registered'),
      { canvasId: 'canvas-unregistered' }
    );

    unmount();
    jest.useRealTimers();
    warnSpy.mockRestore();
  });

  test('does not warn when the canvas IS registered within the verification window', () => {
    jest.useFakeTimers();
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();

    installApi({
      ...fullApi,
      getState: jest.fn(() => ({ canvas_id: 'canvas-ok' })),
    });

    const { unmount } = renderHook(() => useCanvasState('canvas-ok'));

    act(() => {
      jest.advanceTimersByTime(5000);
    });

    expect(warnSpy).not.toHaveBeenCalledWith(
      expect.stringContaining('may not be properly registered'),
      expect.anything()
    );

    unmount();
    jest.useRealTimers();
    warnSpy.mockRestore();
  });

  test('warns when a previously registered canvas now returns null', () => {
    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();

    installApi({
      ...fullApi,
      getState: jest.fn((id: string) =>
        id === 'canvas-gone' ? null : { canvas_id: id }
      ),
      subscribe: jest.fn(() => jest.fn()),
    });

    const { result } = renderHook(() => useCanvasState('canvas-gone'));

    act(() => {
      expect(result.current.getState('canvas-gone')).toBeNull();
    });

    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining('was previously registered but now returns null'),
      { canvasId: 'canvas-gone' }
    );
    warnSpy.mockRestore();
  });

  test('getCanvasRegistrationStatus reports registered ids and warnings', () => {
    clearCanvasRegistrationWarnings();

    const warnSpy = jest.spyOn(console, 'warn').mockImplementation();
    installApi({
      ...fullApi,
      getState: jest.fn(() => null),
    });

    renderHook(() => useCanvasState('canvas-status-1'));
    act(() => {
      jest.advanceTimersByTime(0);
    });

    const status = getCanvasRegistrationStatus();
    expect(status.registeredIds).toContain('canvas-status-1');
    expect(status.warningCount).toBe(0);

    // Now trigger a warning via a null-state subscription event
    installApi({
      ...fullApi,
      getState: jest.fn(() => null),
      subscribe: jest.fn((cb: (s: any) => void) => {
        cb(null);
        return jest.fn();
      }),
    });
    renderHook(() => useCanvasState('canvas-status-2'));

    const statusAfter = getCanvasRegistrationStatus();
    expect(statusAfter.warningCount).toBeGreaterThan(0);
    expect(
      statusAfter.warnings.some((w: string) => w.includes('canvas-status-2'))
    ).toBe(true);

    clearCanvasRegistrationWarnings();
    expect(getCanvasRegistrationStatus().warningCount).toBe(0);
    warnSpy.mockRestore();
  });
});
