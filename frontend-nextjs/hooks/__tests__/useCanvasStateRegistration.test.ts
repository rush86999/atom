/**
 * useCanvasStateRegistration hook tests (hooks/useCanvasStateRegistration.ts)
 *
 * Verifies the real hook against its module-level registry:
 * - register / update / unregister of canvas state in the synchronous
 *   _canvasRegistry (visible via getCanvasState + window.atom.canvas.*)
 * - lifecycle: canvasId change cleans up the OLD id, unmount notifies
 *   subscribers with null (BUG-049 regression guard)
 * - subscriber set: subscribe/subscribeAll callbacks fire on register,
 *   update, and null-out; unsubscribing stops notifications
 * - ensureGlobalApi() never clobbers a pre-existing window.atom.canvas API
 *
 * NOTE: the registry + subscriber set are module-level singletons. RTL's
 * auto-cleanup unmounts each test's hooks, which runs the unmount cleanup
 * (delete entry + notify null), so the registry starts empty per test.
 */

import React from 'react';
import { renderHook, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import {
  useCanvasStateRegistration,
  getCanvasState,
  getAllCanvasStates,
} from '@/hooks/useCanvasStateRegistration';

describe('useCanvasStateRegistration', () => {
  beforeEach(() => {
    delete (window as any).atom;
  });

  // ensureGlobalApi only runs inside the hook effect; mount+unmount a
  // throwaway hook so window.atom.canvas exists for direct API assertions.
  const initGlobalApi = () => {
    const { unmount } = renderHook(() => useCanvasStateRegistration('__init__', null));
    unmount();
    expect((window as any).atom.canvas).toBeDefined();
  };

  test('registers state and exposes it synchronously via all accessors', () => {
    const state = { type: 'sheets', cells: { A1: 'x' } };
    renderHook(() => useCanvasStateRegistration('sheet_1', state as any));

    expect(getCanvasState('sheet_1')).toBe(state);
    expect((window as any).atom.canvas.getState('sheet_1')).toBe(state);
    // No-id getState returns the first registered state (backward compat).
    expect((window as any).atom.canvas.getState()).toBe(state);
    expect((window as any).atom.canvas.getAllStates()).toEqual([
      { canvas_id: 'sheet_1', state },
    ]);
    expect(getAllCanvasStates()).toEqual([{ canvas_id: 'sheet_1', state }]);
  });

  test('updates the registry when the state object changes by reference', () => {
    const state1 = { type: 'sheets', cells: { A1: 'x' } };
    const { rerender } = renderHook(
      ({ s }) => useCanvasStateRegistration('sheet_1', s as any),
      { initialProps: { s: state1 } },
    );

    expect(getCanvasState('sheet_1')).toBe(state1);

    const state2 = { type: 'sheets', cells: { A1: 'y' } };
    rerender({ s: state2 });
    expect(getCanvasState('sheet_1')).toBe(state2);
  });

  test('null state removes the registry entry', () => {
    const { rerender } = renderHook(
      ({ s }) => useCanvasStateRegistration('sheet_1', s as any),
      { initialProps: { s: { type: 'sheets' } as any } },
    );
    expect(getCanvasState('sheet_1')).toBeDefined();

    rerender({ s: null });
    expect(getCanvasState('sheet_1')).toBeNull();
    expect((window as any).atom.canvas.getState('sheet_1')).toBeNull();
  });

  test('changing canvasId cleans up the old registration', () => {
    const { rerender } = renderHook(
      ({ id }) => useCanvasStateRegistration(id, { type: 'sheets' } as any),
      { initialProps: { id: 'old_id' } },
    );
    expect(getCanvasState('old_id')).toBeDefined();

    rerender({ id: 'new_id' });
    expect(getCanvasState('old_id')).toBeNull();
    expect(getCanvasState('new_id')).toBeDefined();
  });

  test('unmount removes the entry and notifies subscribers with null', () => {
    const subscriber = jest.fn();
    const { unmount } = renderHook(() =>
      useCanvasStateRegistration('sheet_1', { type: 'sheets' } as any),
    );
    (window as any).atom.canvas.subscribe('sheet_1', subscriber);

    unmount();
    expect(getCanvasState('sheet_1')).toBeNull();
    expect(subscriber).toHaveBeenCalledWith('sheet_1', null);
  });

  test('subscribe receives updates; unsubscribe stops notifications', () => {
    initGlobalApi();
    const subscriber = jest.fn();
    const unsubscribe = (window as any).atom.canvas.subscribe('sheet_1', subscriber);

    const { rerender } = renderHook(
      ({ s }) => useCanvasStateRegistration('sheet_1', s as any),
      { initialProps: { s: { type: 'sheets', v: 1 } as any } },
    );
    expect(subscriber).toHaveBeenCalledWith('sheet_1', { type: 'sheets', v: 1 });

    rerender({ s: { type: 'sheets', v: 2 } });
    expect(subscriber).toHaveBeenLastCalledWith('sheet_1', { type: 'sheets', v: 2 });

    act(() => unsubscribe());
    rerender({ s: { type: 'sheets', v: 3 } });
    expect(subscriber).not.toHaveBeenCalledWith('sheet_1', { type: 'sheets', v: 3 });
  });

  test('subscribeAll callbacks fire for every registered canvas', () => {
    initGlobalApi();
    const subscriber = jest.fn();
    (window as any).atom.canvas.subscribeAll(subscriber);

    renderHook(() => useCanvasStateRegistration('a', { type: 'sheets' } as any));
    expect(subscriber).toHaveBeenCalledWith('a', { type: 'sheets' });

    renderHook(() => useCanvasStateRegistration('b', { type: 'chart' } as any));
    expect(subscriber).toHaveBeenCalledWith('b', { type: 'chart' });
  });

  test('getCanvasState returns null for unknown ids and empty registry', () => {
    initGlobalApi();
    expect(getCanvasState('nope')).toBeNull();
    expect((window as any).atom.canvas.getState()).toBeNull();
    expect(getAllCanvasStates()).toEqual([]);
  });

  test('ensureGlobalApi does not clobber a pre-existing window.atom.canvas API', () => {
    const customGetState = jest.fn(() => 'custom');
    (window as any).atom = { canvas: { getState: customGetState } };

    renderHook(() => useCanvasStateRegistration('sheet_1', { type: 'sheets' } as any));

    // Registry still works internally…
    expect(getCanvasState('sheet_1')).toBeDefined();
    // …but the pre-existing API surface is left untouched.
    expect((window as any).atom.canvas.getState('sheet_1')).toBe('custom');
    expect((window as any).atom.canvas.subscribe).toBeUndefined();
  });
});
