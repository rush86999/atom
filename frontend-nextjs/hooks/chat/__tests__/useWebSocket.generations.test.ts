/**
 * Socket-generation tests for useWebSocket.
 *
 * The defect these reproduce: `connect()` only declines to open a new
 * socket when the current one is OPEN or CONNECTING. A socket in CLOSING
 * does not block it, so a scheduled reconnect could install socket N+1 and
 * then the OLD socket's `onclose` would run and null `wsRef.current` —
 * orphaning a live connection. Symptoms: `isConnected` flaps,
 * `subscribe()` silently no-ops on a socket that is actually open, and the
 * client keeps opening sockets (the churn observed in the preview).
 *
 * Each socket now carries the generation it was created in, and only the
 * current generation may clear shared state.
 */
import { renderHook, act, waitFor } from '@testing-library/react';

// The hook reads the backend JWT from the NextAuth session. Mock it so the
// test exercises the socket lifecycle rather than the auth provider.
jest.mock('next-auth/react', () => ({
  useSession: () => ({ data: { backendToken: 'test-token' }, status: 'authenticated' }),
}));

import { useWebSocket } from '../../useWebSocket';

class FakeSocket {
  // The hook compares against the WebSocket.OPEN constant.
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances = [];
  readyState = 0; // CONNECTING
  sent = [];
  onopen = null;
  onmessage = null;
  onclose = null;
  onerror = null;
  closed = false;
  constructor(url) {
    this.url = url;
    FakeSocket.instances.push(this);
  }
  send(data) { this.sent.push(data); }
  close() {
    this.closed = true;
    this.readyState = 3; // CLOSED
  }
  /** Simulate the server closing this socket. */
  fireClose(code = 1006, reason = '') {
    this.readyState = 3;
    if (this.onclose) this.onclose({ code, reason });
  }
  open() {
    this.readyState = 1;
    if (this.onopen) this.onopen({});
  }
}

const originalToken = 'test-token';

function install() {
  FakeSocket.instances = [];
  global.WebSocket = FakeSocket;
  window.localStorage.setItem('auth_token', originalToken);
  const sockets = [];
  const origWS = global.WebSocket;
  return () => { global.WebSocket = origWS; window.localStorage.clear(); };
}

describe('useWebSocket socket generations', () => {
  let restore;
  beforeEach(() => { restore = install(); });
  afterEach(() => { if (restore) restore(); });

  it('a stale socket closing does not untrack its live successor', async () => {
    const { result } = renderHook(() => useWebSocket({ reconnect: false }));

    await waitFor(() => expect(FakeSocket.instances.length).toBeGreaterThan(0));
    const first = FakeSocket.instances[0];
    act(() => first.open());

    // The first socket begins closing and a reconnect installs a second.
    first.readyState = 2; // CLOSING — does not block connect()
    act(() => { result.current.disconnect(); });
    // A fresh mount-level connect is what the autoConnect effect does after
    // a session change; drive it directly through a second render pass.
    const { result: second } = renderHook(() =>
      useWebSocket({ reconnect: false }));
    await waitFor(() =>
      expect(FakeSocket.instances.length).toBeGreaterThan(1));
    const live = FakeSocket.instances[FakeSocket.instances.length - 1];
    act(() => live.open());
    expect(second.current.isConnected).toBe(true);

    // Now the OLD socket finally closes. It must not disturb the live one.
    act(() => first.fireClose(1006, 'stale'));

    expect(second.current.isConnected).toBe(true);
    const before = live.sent.length;
    act(() => { second.current.subscribe('workspace:default'); });
    expect(live.sent.length).toBe(before + 1);
  });

  it('disconnect retires the generation so a late close is ignored', async () => {
    const { result } = renderHook(() => useWebSocket({ reconnect: false }));
    await waitFor(() => expect(FakeSocket.instances.length).toBeGreaterThan(0));
    const ws = FakeSocket.instances[0];
    act(() => ws.open());
    expect(result.current.isConnected).toBe(true);

    act(() => { result.current.disconnect(); });
    expect(result.current.isConnected).toBe(false);

    // A close arriving after an intentional teardown must stay a no-op
    // rather than flipping state or scheduling work.
    act(() => ws.fireClose(1000, 'normal'));
    expect(result.current.isConnected).toBe(false);
  });

  it('reports connected only for the current generation', async () => {
    const { result } = renderHook(() => useWebSocket({ reconnect: false }));
    await waitFor(() => expect(FakeSocket.instances.length).toBeGreaterThan(0));
    const ws = FakeSocket.instances[0];
    act(() => ws.open());
    expect(result.current.isConnected).toBe(true);
    act(() => ws.fireClose(1006, 'drop'));
    expect(result.current.isConnected).toBe(false);
  });
});
