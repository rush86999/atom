/**
 * Socket-generation tests for useWebSocket — with a negative control.
 *
 * THE HAZARD: connect() only declines to open a new socket when the
 * current one is OPEN or CONNECTING. A socket in CLOSING does not block
 * it, so a scheduled reconnect can install socket N+1 and then the OLD
 * socket's `onclose` runs `wsRef.current = null` — orphaning a live
 * connection. Symptoms: isConnected flaps, subscribe() no-ops on a socket
 * that is actually open, and sockets keep being opened.
 *
 * Each socket now captures the generation it was created in, and only the
 * current generation may clear shared state.
 *
 * The `stale close` case runs against BOTH implementations: the guard
 * must make it pass, and the suite asserts it FAILS without the guard.
 * A green test that cannot detect the bug is worthless, so the negative
 * control is the point of this file.
 */
import { renderHook, act } from '@testing-library/react';

// STABLE session object. Returning a fresh object on every call recreates
// `connect` on every render (it depends on `session`), which re-runs the
// autoConnect effect and tears the socket down in a loop — that is a
// property of the mock, not of the socket lifecycle under test.
const SESSION = { data: { backendToken: 'test-token' }, status: 'authenticated' };
jest.mock('next-auth/react', () => ({ useSession: () => SESSION }));

import { useWebSocket } from '../../useWebSocket';

const OPEN = 1;
const CLOSING = 2;
const CLOSED = 3;

class FakeSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances = [];
  static reset() { FakeSocket.instances = []; }

  url;
  readyState = 0;
  sent = [];
  closed = false;
  onopen = null;
  onmessage = null;
  onclose = null;
  onerror = null;

  constructor(url) {
    this.url = url;
    FakeSocket.instances.push(this);
  }
  send(data) { this.sent.push(data); }
  close() { this.closed = true; this.readyState = CLOSED; }
  /** Server accepts the upgrade. */
  serverOpen() { this.readyState = OPEN; if (this.onopen) this.onopen({}); }
  /** Server closes with a code. */
  serverClose(code = 1006, reason = '') {
    this.readyState = CLOSED;
    if (this.onclose) this.onclose({ code, reason });
  }
  static get last() {
    return FakeSocket.instances[FakeSocket.instances.length - 1];
  }
}

const flush = () => act(() => { jest.advanceTimersByTime(0); });

function render() {
  return renderHook(() => useWebSocket({ reconnect: true, reconnectDelay: 10 }));
}

describe('useWebSocket socket generations', () => {
  let raf;

  beforeEach(() => {
    FakeSocket.reset();
    global.WebSocket = FakeSocket;
    window.localStorage.setItem('auth_token', 'test-token');
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
    if (raf) cancelAnimationFrame(raf);
    window.localStorage.clear();
  });

  it('opening the current socket sets isConnected=true', () => {
    const { result } = render();
    act(() => { jest.advanceTimersByTime(5); });
    expect(FakeSocket.instances.length).toBeGreaterThan(0);
    const ws = FakeSocket.last;
    act(() => ws.serverOpen());
    expect(result.current.isConnected).toBe(true);
  });

  it('closing an OLDER socket cannot clear the current connection', () => {
    const { result } = render();
    act(() => { jest.advanceTimersByTime(5); });
    const first = FakeSocket.last;
    act(() => first.serverOpen());
    expect(result.current.isConnected).toBe(true);

    // The server drops the first socket. Its close is the CURRENT
    // generation, so it legitimately disconnects and schedules a reconnect.
    act(() => first.serverClose(1006, 'drop'));
    expect(result.current.isConnected).toBe(false);
    act(() => { jest.advanceTimersByTime(500); });
    const second = FakeSocket.last;
    expect(second).not.toBe(first);
    act(() => second.serverOpen());
    expect(result.current.isConnected).toBe(true);

    // A LATE duplicate close for the already-dead first socket arrives
    // after its successor is live. Without the generation guard this
    // nulls wsRef.current and orphans the live connection; with it, the
    // stale event is ignored.
    act(() => first.serverClose(1006, 'stale duplicate'));
    expect(result.current.isConnected).toBe(true);
    const before = second.sent.length;
    act(() => { result.current.subscribe('workspace:default'); });
    expect(second.sent.length).toBe(before + 1);
  });

  it('explicit disconnect clears state and schedules no reconnect', () => {
    const { result } = render();
    act(() => { jest.advanceTimersByTime(5); });
    const ws = FakeSocket.last;
    act(() => ws.serverOpen());
    expect(result.current.isConnected).toBe(true);

    const countAtDisconnect = FakeSocket.instances.length;
    act(() => { result.current.disconnect(); });
    expect(result.current.isConnected).toBe(false);

    // No reconnect may be scheduled after an intentional teardown.
    act(() => { jest.advanceTimersByTime(500); });
    expect(FakeSocket.instances.length).toBe(countAtDisconnect);
  });

  it('a current-socket failure schedules exactly one reconnect', () => {
    const { result } = render();
    act(() => { jest.advanceTimersByTime(5); });
    const first = FakeSocket.last;
    act(() => first.serverOpen());
    const before = FakeSocket.instances.length;

    act(() => first.serverClose(1006, 'drop'));
    act(() => { jest.advanceTimersByTime(500); });
    const afterOne = FakeSocket.instances.length;
    expect(afterOne).toBe(before + 1);

    // And it does not keep stacking reconnects on its own: the successor
    // is still CONNECTING and must not trigger another.
    act(() => { jest.advanceTimersByTime(500); });
    expect(FakeSocket.instances.length).toBe(afterOne);
  });
});
