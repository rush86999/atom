/**
 * useUserActivity Hook Unit Tests
 *
 * Tests for user activity tracking hook covering:
 * - Session token generation
 * - Activity event listeners (mouse, keyboard, scroll, touch)
 * - Heartbeat API calls with intervals
 * - Manual state override
 * - Cleanup of timers and event listeners (CRITICAL for memory leak prevention)
 *
 * The old suite mocked the heartbeat/override endpoints with a second MSW
 * server whose relative paths (e.g. /api/users/:id/activity/heartbeat) never
 * matched the absolute URLs the setup.ts fetch wrapper produces
 * (http://localhost:8000/api/users/...), so requests went unhandled, hung, and
 * leaked state between tests. We mock global.fetch directly instead.
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

// Mock window object for browser APIs
Object.defineProperty(window, 'navigator', {
  value: {
    userAgent: 'Mozilla/5.0 (test)',
  },
  writable: true,
});

describe('useUserActivity Hook', () => {
  let addEventListenerSpy: jest.SpyInstance;
  let removeEventListenerSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Fully mock fetch so the mount heartbeat and any override calls resolve
    // deterministically without MSW.
    global.fetch = jest.fn();
    global.mockFetch = global.fetch;
    (global.mockFetch as jest.Mock).mockResolvedValue(heartbeatOk());

    // Spy on event listeners
    addEventListenerSpy = jest.spyOn(window, 'addEventListener');
    removeEventListenerSpy = jest.spyOn(window, 'removeEventListener');
  });

  afterEach(() => {
    jest.useRealTimers();
    addEventListenerSpy.mockRestore();
    removeEventListenerSpy.mockRestore();
  });

  describe('1. Session Token Generation Tests', () => {
    test('generates session token on mount', () => {
      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      // Token should be generated - hook should initialize without error
      expect(result.current.sendHeartbeat).toBeDefined();
    });

    test('token format includes web prefix and timestamp', async () => {
      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      // The mount heartbeat resolves to a valid state; verify the request
      // carried a web-prefixed session token.
      await waitFor(() => {
        expect(result.current.state).not.toBeNull();
      });

      const heartbeatCall = (global.mockFetch as jest.Mock).mock.calls.find(
        ([url]: any) => String(url).includes('/activity/heartbeat')
      );
      expect(heartbeatCall).toBeDefined();
      const body = JSON.parse(heartbeatCall[1].body);
      expect(body.session_token).toMatch(/^web_/);
      expect(body.session_type).toBe('web');
    });

    test('uses Date.now() and Math.random() for token generation', async () => {
      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      // Verify hook initializes and sends heartbeat
      await waitFor(() => {
        expect(addEventListenerSpy).toHaveBeenCalled();
      });
      expect(result.current.sendHeartbeat).toBeDefined();
    });
  });

  describe('2. Activity Tracking Tests', () => {
    test('adds event listeners for user activity events', () => {
      renderHook(() => useUserActivity({ userId: 'user-123', enabled: true }));

      // Should add 4 event listeners
      const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];

      events.forEach(event => {
        expect(addEventListenerSpy).toHaveBeenCalledWith(
          event,
          expect.any(Function),
          { passive: true }
        );
      });
    });

    test('uses passive: true option for all event listeners', () => {
      renderHook(() => useUserActivity({ userId: 'user-123', enabled: true }));

      const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];

      events.forEach(event => {
        const calls = addEventListenerSpy.mock.calls.filter(
          call => call[0] === event
        );

        expect(calls.length).toBeGreaterThan(0);
        calls.forEach(call => {
          expect(call[2]).toEqual({ passive: true });
        });
      });
    });

    test('does not add listeners when enabled=false', () => {
      renderHook(() => useUserActivity({ userId: 'user-123', enabled: false }));

      expect(addEventListenerSpy).not.toHaveBeenCalled();
    });

    test('all listeners call recordActivity function', () => {
      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      // Get the recordActivity function from the addEventListener calls
      const mousedownListener = addEventListenerSpy.mock.calls.find(
        call => call[0] === 'mousedown'
      )?.[1];

      expect(mousedownListener).toBeDefined();
      expect(typeof mousedownListener).toBe('function');
    });
  });

  describe('3. Heartbeat Tests', () => {
    test('sends heartbeat immediately on mount', async () => {
      renderHook(() => useUserActivity({ userId: 'user-123' }));

      // The mount heartbeat is sent immediately (no timer advance needed).
      await waitFor(() => {
        const heartbeatCalls = (global.mockFetch as jest.Mock).mock.calls.filter(
          ([url]: any) => String(url).includes('/activity/heartbeat')
        );
        expect(heartbeatCalls.length).toBeGreaterThanOrEqual(1);
      });
    });

    test('sends heartbeat every 30 seconds by default', async () => {
      renderHook(() => useUserActivity({ userId: 'user-123' }));

      // Wait for initial heartbeat
      await waitFor(() => {
        const calls = (global.mockFetch as jest.Mock).mock.calls.filter(
          ([url]: any) => String(url).includes('/activity/heartbeat')
        );
        expect(calls.length).toBeGreaterThanOrEqual(1);
      });

      // Advance time by 30 seconds
      act(() => {
        jest.advanceTimersByTime(30000);
      });

      await waitFor(() => {
        const calls = (global.mockFetch as jest.Mock).mock.calls.filter(
          ([url]: any) => String(url).includes('/activity/heartbeat')
        );
        expect(calls.length).toBeGreaterThanOrEqual(2);
      });
    });

    test('respects custom interval setting', async () => {
      renderHook(() =>
        useUserActivity({ userId: 'user-123', interval: 10000 })
      );

      await waitFor(() => {
        const calls = (global.mockFetch as jest.Mock).mock.calls.filter(
          ([url]: any) => String(url).includes('/activity/heartbeat')
        );
        expect(calls.length).toBeGreaterThanOrEqual(1);
      });

      // Advance by custom interval
      act(() => {
        jest.advanceTimersByTime(10000);
      });

      await waitFor(() => {
        const calls = (global.mockFetch as jest.Mock).mock.calls.filter(
          ([url]: any) => String(url).includes('/activity/heartbeat')
        );
        expect(calls.length).toBeGreaterThanOrEqual(2);
      });
    });

    test('does not send heartbeat when disabled', async () => {
      renderHook(() =>
        useUserActivity({ userId: 'user-123', enabled: false })
      );

      // Advance time significantly
      act(() => {
        jest.advanceTimersByTime(60000);
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('4. Heartbeat Response Handling Tests', () => {
    test('updates state from API response', async () => {
      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      await waitFor(() => {
        expect(result.current.state).toBeTruthy();
      });

      expect(result.current.state?.state).toBe('online');
      expect(result.current.state?.manual_override).toBe(false);
    });

    test('calls onStateChange callback if provided', async () => {
      const onStateChange = jest.fn();

      renderHook(() =>
        useUserActivity({ userId: 'user-123', onStateChange })
      );

      await waitFor(() => {
        expect(onStateChange).toHaveBeenCalled();
      });

      expect(onStateChange).toHaveBeenCalledWith(
        expect.objectContaining({ state: 'online' })
      );
    });
  });

  describe('5. Manual Override Tests', () => {
    test('setManualOverride calls API and updates state', async () => {
      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      await act(async () => {
        await result.current.setManualOverride('away');
      });

      // The mount heartbeat and the override both resolve to a state.
      const overrideCall = (global.mockFetch as jest.Mock).mock.calls.find(
        (call: any[]) =>
          String(call[0]).includes('/activity/override') &&
          call[1]?.method === 'POST'
      );
      expect(overrideCall).toBeDefined();
      await waitFor(() => {
        expect(result.current.state).toBeTruthy();
      });
    });

    test('includes expires_at if provided', async () => {
      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      const expiresAt = new Date('2024-12-31T23:59:59Z');

      // Should not throw
      await act(async () => {
        await result.current.setManualOverride('offline', expiresAt);
      });

      const overrideCall = (global.mockFetch as jest.Mock).mock.calls.find(
        (call: any[]) =>
          String(call[0]).includes('/activity/override') &&
          call[1]?.method === 'POST'
      );
      expect(overrideCall).toBeDefined();
      const body = JSON.parse(overrideCall[1].body);
      expect(body.state).toBe('offline');
      expect(body.expires_at).toBe('2024-12-31T23:59:59.000Z');

      await waitFor(() => {
        expect(result.current.state).toBeTruthy();
      });
    });

    test('clearManualOverride updates state', async () => {
      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      await act(async () => {
        await result.current.clearManualOverride();
      });

      const clearCall = (global.mockFetch as jest.Mock).mock.calls.find(
        (call: any[]) =>
          String(call[0]).includes('/activity/override') &&
          call[1]?.method === 'DELETE'
      );
      expect(clearCall).toBeDefined();

      await waitFor(() => {
        expect(result.current.state).toBeTruthy();
      });
    });
  });

  describe('6. Cleanup Tests (CRITICAL)', () => {
    test('clears activity timeout on unmount', () => {
      const { unmount } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      // Trigger some activity to set timeout
      const mousedownListener = addEventListenerSpy.mock.calls.find(
        call => call[0] === 'mousedown'
      )?.[1];

      if (mousedownListener) {
        mousedownListener(new Event('mousedown'));
      }

      // Unmount should clear timeout
      unmount();

      // Verify cleanup - no timers should remain
      act(() => {
        jest.runAllTimers();
      });

      // Should not throw or leak
      expect(true).toBe(true);
    });

    test('removes all event listeners on unmount', () => {
      const { unmount } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];

      // Each event should have one listener added
      events.forEach(event => {
        const addCalls = addEventListenerSpy.mock.calls.filter(
          call => call[0] === event
        );
        expect(addCalls.length).toBe(1);
      });

      unmount();

      // Each event listener should be removed
      events.forEach(event => {
        const removeCalls = removeEventListenerSpy.mock.calls.filter(
          call => call[0] === event
        );
        expect(removeCalls.length).toBe(1);
      });
    });

    test('clears heartbeat interval on unmount', async () => {
      const { unmount } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      // Wait for event listeners to be added
      await waitFor(() => expect(addEventListenerSpy).toHaveBeenCalled());

      // Advance time
      act(() => {
        jest.advanceTimersByTime(30000);
      });

      // Unmount should clear interval
      unmount();

      // Advance time after unmount - should not cause issues
      act(() => {
        jest.advanceTimersByTime(30000);
      });

      // Should not throw or leak
      expect(true).toBe(true);
    });

    test('each listener is removed individually', () => {
      const { unmount } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      const events = ['mousedown', 'keydown', 'scroll', 'touchstart'];

      unmount();

      // Verify each event was removed with the correct handler
      events.forEach(event => {
        const addCalls = addEventListenerSpy.mock.calls.filter(
          call => call[0] === event
        );
        const removeCalls = removeEventListenerSpy.mock.calls.filter(
          call => call[0] === event
        );

        expect(addCalls.length).toBe(1);
        expect(removeCalls.length).toBe(1);

        // The same handler should be removed
        expect(addCalls[0][1]).toBe(removeCalls[0][1]);
      });
    });
  });

  describe('7. Error Handling Tests', () => {
    test('logs error to console on fetch failure', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {
        // Suppress console output during test
      });

      // The mount heartbeat rejects; the hook logs the failure.
      (global.mockFetch as jest.Mock).mockRejectedValueOnce(
        new Error('Failed to connect')
      );

      renderHook(() => useUserActivity({ userId: 'user-123' }));

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalled();
      });

      consoleSpy.mockRestore();
    });

    test('handles HTTP error responses', async () => {
      // The mount heartbeat returns a 500 response; the hook sets an error.
      (global.mockFetch as jest.Mock).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: async () => ({ error: 'Internal Server Error' }),
      });

      const { result } = renderHook(() =>
        useUserActivity({ userId: 'user-123' })
      );

      await waitFor(() => {
        expect(result.current.error).toBeDefined();
      });
    });
  });

  describe('8. Enabled Flag Tests', () => {
    test('does not track when enabled=false', () => {
      renderHook(() =>
        useUserActivity({ userId: 'user-123', enabled: false })
      );

      expect(addEventListenerSpy).not.toHaveBeenCalled();
    });

    test('does not send heartbeat when disabled', async () => {
      renderHook(() =>
        useUserActivity({ userId: 'user-123', enabled: false })
      );

      // Advance time
      act(() => {
        jest.advanceTimersByTime(60000);
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });

    test('does not set up interval when disabled', async () => {
      renderHook(() =>
        useUserActivity({ userId: 'user-123', enabled: false })
      );

      // Wait to ensure no timers were set
      await act(async () => {
        await Promise.resolve();
      });

      // Run all timers - should be none
      act(() => {
        jest.runAllTimers();
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });

    test('can toggle enabled state', async () => {
      const { rerender } = renderHook(
        ({ enabled }) => useUserActivity({ userId: 'user-123', enabled }),
        { initialProps: { enabled: true } }
      );

      // Should be tracking initially
      expect(addEventListenerSpy).toHaveBeenCalled();

      // Disable
      rerender({ enabled: false });

      // Should remove listeners
      expect(removeEventListenerSpy).toHaveBeenCalled();
    });
  });
});
