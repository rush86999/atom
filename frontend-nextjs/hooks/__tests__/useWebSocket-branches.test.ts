/**
 * useWebSocket Branch Coverage Tests (wave 119)
 *
 * Closes the remaining gaps in useWebSocket.ts:
 * - relative (non-ws://) url join branch (line 94)
 * - onopen clearing a pending reconnect timeout (lines 110-111)
 * - sendMessage guard-true path (line 242)
 */

import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';

jest.mock('next-auth/react', () => ({
  useSession: jest.fn(),
}));

import { useSession } from 'next-auth/react';

describe('useWebSocket - Branch Coverage', () => {
  const simulateOpen = (ws: any) => {
    act(() => {
      ws.readyState = (global as any).WebSocket.OPEN;
      if (ws._onopen) {
        ws._onopen(new Event('open'));
      }
    });
  };

  const simulateCloseWithCode = (ws: any, code: number) => {
    act(() => {
      if (ws._onclose) {
        ws._onclose(new CloseEvent('close', { code }));
      }
    });
  };

  const getInstance = (i: number) =>
    (global as any).WebSocket.getMockInstances()[i];
  const callCount = () => (global as any).WebSocket.getMockCalls().length;

  beforeEach(() => {
    jest.clearAllMocks();
    ((global as any).WebSocket as any).mock.calls = [];
    ((global as any).WebSocket as any).mock.instances = [];

    (useSession as jest.Mock).mockReturnValue({
      data: { backendToken: 'test-session-token' },
      status: 'authenticated',
    });
  });

  test('joins relative urls onto the resolved ws base', () => {
    renderHook(() =>
      useWebSocket({ autoConnect: true, url: 'custom/socket' })
    );
    expect((global as any).WebSocket.getMockCalls()).toContainEqual([
      '/custom/socket?token=test-session-token',
    ]);
  });

  test('joins leading-slash relative urls without doubling the slash', () => {
    renderHook(() =>
      useWebSocket({ autoConnect: true, url: '/custom/socket' })
    );
    expect((global as any).WebSocket.getMockCalls()).toContainEqual([
      '/custom/socket?token=test-session-token',
    ]);
  });

  test('reuses full ws:// urls as-is', () => {
    renderHook(() =>
      useWebSocket({ autoConnect: true, url: 'ws://elsewhere.example/ws' })
    );
    expect((global as any).WebSocket.getMockCalls()).toContainEqual([
      'ws://elsewhere.example/ws?token=test-session-token',
    ]);
  });

  test('onopen clears a pending reconnect timeout after a transient close', () => {
    jest.useFakeTimers();

    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: true })
    );
    const ws0 = getInstance(0);
    simulateOpen(ws0);
    expect(result.current.isConnected).toBe(true);

    // Transient close schedules a reconnect (~1s + jitter); do NOT advance
    // timers — instead the same socket reopens (real-world close→reopen race).
    simulateCloseWithCode(ws0, 1006);
    simulateOpen(ws0);

    // The pending retry was cancelled by onopen: advancing past the backoff
    // window must NOT create a new socket.
    act(() => {
      jest.advanceTimersByTime(30000);
    });
    expect(callCount()).toBe(1);
    expect(result.current.isConnected).toBe(true);

    jest.useRealTimers();
  });

  test('sendMessage sends when the socket is OPEN', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: true })
    );
    const ws0 = getInstance(0);
    simulateOpen(ws0);

    act(() => {
      result.current.sendMessage({ type: 'hello', data: 1 });
    });

    expect(ws0.send).toHaveBeenCalledWith(
      JSON.stringify({ type: 'hello', data: 1 })
    );
  });

  test('sendMessage is a no-op while the socket is CONNECTING', () => {
    const { result } = renderHook(() =>
      useWebSocket({ autoConnect: true })
    );
    const ws0 = getInstance(0);
    expect(ws0.readyState).toBe(0); // CONNECTING

    act(() => {
      result.current.sendMessage({ type: 'hello' });
    });

    expect(ws0.send).not.toHaveBeenCalled();
  });
});
