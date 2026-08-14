/**
 * useUserActivity Branch Coverage Tests (wave 119)
 *
 * Closes the remaining gaps in useUserActivity.ts:
 * - recordActivity clearTimeout branch (repeated activity events)
 * - setManualOverride / clearManualOverride HTTP-error + network-error paths
 * - `document.hidden` interval skip (BUG-048)
 * - no-userId no-op guards
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { useUserActivity } from '../useUserActivity';

const heartbeatOk = (overrides: Record<string, unknown> = {}) => ({
  ok: true,
  status: 200,
  statusText: 'OK',
  json: async () => ({
    state: 'online',
    last_activity_at: new Date().toISOString(),
    manual_override: false,
    ...overrides,
  }),
});

Object.defineProperty(window, 'navigator', {
  value: { userAgent: 'Mozilla/5.0 (test)' },
  writable: true,
});

describe('useUserActivity - Branch Coverage', () => {
  let addEventListenerSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    global.fetch = jest.fn();
    global.mockFetch = global.fetch;
    (global.mockFetch as jest.Mock).mockResolvedValue(heartbeatOk());

    addEventListenerSpy = jest.spyOn(window, 'addEventListener');
  });

  afterEach(() => {
    jest.useRealTimers();
    addEventListenerSpy.mockRestore();
    // Restore document.hidden visibility in case a test flipped it
    Object.defineProperty(document, 'hidden', {
      value: false,
      configurable: true,
    });
  });

  function getListener(event: string): EventListener | undefined {
    return addEventListenerSpy.mock.calls.find(
      (call: any[]) => call[0] === event
    )?.[1] as EventListener | undefined;
  }

  test('repeated activity events clear the pending inactivity timeout', () => {
    renderHook(() => useUserActivity({ userId: 'user-123' }));

    const mousedown = getListener('mousedown');
    const setTimeoutSpy = jest.spyOn(global, 'setTimeout');

    act(() => {
      mousedown!(new Event('mousedown'));
      mousedown!(new Event('mousedown'));
    });

    expect(setTimeoutSpy).toHaveBeenCalledTimes(2);
  });

  test('setManualOverride sets error on HTTP failure', async () => {
    const { result } = renderHook(() =>
      useUserActivity({ userId: 'user-123' })
    );
    await waitFor(() => expect(result.current.state).toBeTruthy());

    (global.mockFetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 403,
      statusText: 'Forbidden',
    });

    await act(async () => {
      await result.current.setManualOverride('away');
    });

    expect(result.current.error).toBe('HTTP 403');
  });

  test('setManualOverride sets error on network failure', async () => {
    const { result } = renderHook(() =>
      useUserActivity({ userId: 'user-123' })
    );
    await waitFor(() => expect(result.current.state).toBeTruthy());

    (global.mockFetch as jest.Mock).mockRejectedValueOnce(
      new Error('override network down')
    );

    await act(async () => {
      await result.current.setManualOverride('away');
    });

    expect(result.current.error).toBe('override network down');
  });

  test('clearManualOverride sets error on HTTP failure', async () => {
    const { result } = renderHook(() =>
      useUserActivity({ userId: 'user-123' })
    );
    await waitFor(() => expect(result.current.state).toBeTruthy());

    (global.mockFetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    await act(async () => {
      await result.current.clearManualOverride();
    });

    expect(result.current.error).toBe('HTTP 500');
  });

  test('clearManualOverride sets error on network failure', async () => {
    const { result } = renderHook(() =>
      useUserActivity({ userId: 'user-123' })
    );
    await waitFor(() => expect(result.current.state).toBeTruthy());

    (global.mockFetch as jest.Mock).mockRejectedValueOnce(
      new Error('clear network down')
    );

    await act(async () => {
      await result.current.clearManualOverride();
    });

    expect(result.current.error).toBe('clear network down');
  });

  test('skips heartbeats while the tab is hidden', async () => {
    renderHook(() => useUserActivity({ userId: 'user-123' }));

    // Mount heartbeat consumed
    await act(async () => {
      await Promise.resolve();
    });
    const before = (global.mockFetch as jest.Mock).mock.calls.length;
    expect(before).toBeGreaterThanOrEqual(1);

    Object.defineProperty(document, 'hidden', {
      value: true,
      configurable: true,
    });

    act(() => {
      jest.advanceTimersByTime(90000);
    });

    // No new heartbeat calls while hidden
    expect((global.mockFetch as jest.Mock).mock.calls.length).toBe(before);
  });

  test('resumes heartbeats after the tab becomes visible again', async () => {
    renderHook(() => useUserActivity({ userId: 'user-123' }));
    await act(async () => {
      await Promise.resolve();
    });

    Object.defineProperty(document, 'hidden', {
      value: true,
      configurable: true,
    });
    act(() => {
      jest.advanceTimersByTime(30000);
    });

    Object.defineProperty(document, 'hidden', {
      value: false,
      configurable: true,
    });
    act(() => {
      jest.advanceTimersByTime(30000);
    });

    const calls = (global.mockFetch as jest.Mock).mock.calls.filter(
      ([url]: any) => String(url).includes('/activity/heartbeat')
    );
    expect(calls.length).toBeGreaterThanOrEqual(2);
  });

  test('setManualOverride is a no-op without a userId', async () => {
    const { result } = renderHook(() => useUserActivity({ userId: '' }));

    await act(async () => {
      await result.current.setManualOverride('away');
    });

    const overrideCalls = (global.mockFetch as jest.Mock).mock.calls.filter(
      ([url]: any) => String(url).includes('/activity/override')
    );
    expect(overrideCalls).toHaveLength(0);
  });

  test('clearManualOverride is a no-op without a userId', async () => {
    const { result } = renderHook(() => useUserActivity({ userId: '' }));

    await act(async () => {
      await result.current.clearManualOverride();
    });

    const overrideCalls = (global.mockFetch as jest.Mock).mock.calls.filter(
      ([url]: any) => String(url).includes('/activity/override')
    );
    expect(overrideCalls).toHaveLength(0);
  });
});
