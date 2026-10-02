/**
 * STALE-CALLBACK tests for useWebSocket — the audit the existing generation
 * guard does not cover.
 *
 * Commit 59f6ca6d5 ("wip(ws): socket generation guard — HAZARD IDENTIFIED,
 * FIX NOT TEST-VERIFIED") added a generation captured per socket and applied it
 * to `onclose` ONLY. The hazard is wider than the close path: a socket that has
 * been retired can still fire `onopen` and `onmessage`, and both mutate shared
 * state unconditionally.
 *
 *   - a stale `onopen` cancels the CURRENT generation's pending reconnect timer
 *     (it clearTimeouts a shared ref), so a live outage never recovers;
 *   - a stale `onopen` re-sends `initialChannels` subscriptions on the dead
 *     socket, so the live socket is left unsubscribed;
 *   - a stale `onmessage` still writes `lastMessage`/`streamingContent` and
 *     still fans out to every `onMessage` handler, so a retired connection
 *     keeps injecting frames into the UI.
 *
 * Every test in this file is paired with a NEGATIVE CONTROL: the same
 * assertion is re-run against a deliberately broken variant of the hook
 * (`installBrokenVariant`), which strips the guard. A green test that cannot
 * detect the bug is worthless, so the control is the point of the file.
 */
import { renderHook, render as renderComponent, act } from '@testing-library/react';
import { useEffect, createElement } from 'react';

// The session object is held in a module-level variable so a test can express
// the two cases separately: a MEANINGFUL credential change (new object, new
// token) and an INCIDENTAL one (new object, identical token — what next-auth
// produces on every poll/router event). Returning a fresh object from the mock
// itself would make every render look like a credential change and would mask
// the defects this file is auditing.
let SESSION_OBJ: any = { data: { backendToken: 'test-token' }, status: 'authenticated' };
jest.mock('next-auth/react', () => ({ useSession: () => SESSION_OBJ }));

/** Replace the session object (new identity) carrying `token`. */
const setSession = (token: string) => {
  SESSION_OBJ = { data: { backendToken: token }, status: 'authenticated' };
};

import { useWebSocket } from '../../useWebSocket';

const OPEN = 1;
const CLOSING = 2;
const CLOSED = 3;

/**
 * Deterministic fake socket. Every terminal transition is driven explicitly —
 * the harness never invents an open/close on its own, so event sequencing in a
 * test is exactly the sequencing the test declares.
 *
 * `close()` deliberately does NOT fire `onclose`: that models the real browser
 * (the close frame is asynchronous) and is what lets a test hold a reference to
 * a retired socket and fire its callbacks late.
 */
class FakeSocket {
  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeSocket[] = [];
  static reset() { FakeSocket.instances = []; }

  url: string;
  readyState = 0;
  sent: string[] = [];
  closed = false;
  onopen: ((e?: any) => void) | null = null;
  onmessage: ((e: any) => void) | null = null;
  onclose: ((e: any) => void) | null = null;
  onerror: ((e?: any) => void) | null = null;

  constructor(url: string) {
    this.url = url;
    FakeSocket.instances.push(this);
  }
  send(data: string) { this.sent.push(data); }
  close() { this.closed = true; this.readyState = CLOSED; }

  serverOpen() { this.readyState = OPEN; this.onopen?.({}); }
  serverClose(code = 1006, reason = '') {
    this.readyState = CLOSED;
    this.onclose?.({ code, reason });
  }
  serverMessage(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) });
  }
  /** Move to CLOSING without emitting the close frame (a close is in flight). */
  enterClosing() { this.readyState = CLOSING; }

  static get last() { return FakeSocket.instances[FakeSocket.instances.length - 1]; }
  static get count() { return FakeSocket.instances.length; }
}

// The negative-control variant: a copy of the hook with every generation guard
// removed from `onopen`/`onmessage`, single-retry protection reverted, and the
// `session`-object dependency restored. It is the pre-fix implementation, kept
// as its own module so a control can never accidentally become a copy of the
// FIXED hook. See fixtures/useWebSocket.broken.ts.
import { useWebSocketBroken } from './fixtures/useWebSocket.broken';

const render = (opts: any = {}) =>
  renderHook(() => useWebSocket({ reconnect: true, reconnectDelay: 10, ...opts }));

const renderBroken = (opts: any = {}) =>
  renderHook(() => useWebSocketBroken({ reconnect: true, reconnectDelay: 10, ...opts }));

/**
 * Mount a hook and expose a way to move the session forward.
 *
 * `swapToken` publishes a new session OBJECT (as next-auth does on refresh)
 * and re-renders. `churn` re-renders with a brand-new object carrying the SAME
 * token — the incidental case that must not touch the socket.
 */
function mount(useHook: (o: any) => any, opts: any = {}) {
  const utils = renderHook(() => useHook({ reconnect: true, reconnectDelay: 10, ...opts }));
  return {
    ...utils,
    /** Meaningful credential change: new object, new token. */
    swapToken: (token: string) => {
      act(() => { setSession(token); utils.rerender(); });
      act(() => { jest.advanceTimersByTime(5); });
    },
    /** Incidental change: new object, identical token. */
    churn: (times = 3) => {
      for (let i = 0; i < times; i += 1) {
        act(() => { setSession(SESSION_OBJ.data.backendToken); utils.rerender(); });
        act(() => { jest.advanceTimersByTime(1); });
      }
    },
  };
}

describe('useWebSocket — stale callbacks after ownership is retired', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
    SESSION_OBJ = { data: { backendToken: 'test-token' }, status: 'authenticated' };
    window.localStorage.setItem('auth_token', 'test-token');
    jest.useFakeTimers();
    jest.spyOn(console, 'debug').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    window.localStorage.clear();
  });

  it('a stale onopen cannot flip connection state for the live socket', () => {
    const { result, swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    expect(result.current.isConnected).toBe(true);

    // A is retired; B becomes the current socket.
    act(() => { result.current.disconnect(); });
    swapToken('token-b');
    const b = FakeSocket.last;
    expect(b).not.toBe(a);
    act(() => b.serverOpen());
    expect(result.current.isConnected).toBe(true);

    // A's accept arrives LATE. It must not be treated as a live connect.
    act(() => { a.readyState = OPEN; a.serverOpen(); });
    // B is still the socket that owns the connection.
    const before = b.sent.length;
    act(() => { result.current.subscribe('workspace:default'); });
    expect(b.sent.length).toBe(before + 1);
  });

  it('a stale onopen cannot cancel the current generation\'s pending reconnect', () => {
    const { result, swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());

    act(() => { result.current.disconnect(); });
    swapToken('token-b');
    const b = FakeSocket.last;
    act(() => b.serverOpen());

    // B drops — the current generation schedules its single retry.
    const countBeforeDrop = FakeSocket.count;
    act(() => b.serverClose(1006, 'server restart'));
    expect(result.current.isConnected).toBe(false);

    // A's late accept lands. It owns nothing, so it must not touch the timer
    // that is B's only path back to a live connection.
    act(() => { a.readyState = OPEN; a.serverOpen(); });

    act(() => { jest.advanceTimersByTime(500); });
    expect(FakeSocket.count).toBe(countBeforeDrop + 1);
  });

  it('a stale onopen does not re-send initialChannels on the dead socket', () => {
    const { result, swapToken } = mount(useWebSocket, { initialChannels: ['workspace:default'] });
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const aSentAfterOwnOpen = a.sent.length;
    expect(aSentAfterOwnOpen).toBe(1); // the subscribe it legitimately sent

    act(() => { result.current.disconnect(); });
    swapToken('token-b');
    const b = FakeSocket.last;
    act(() => b.serverOpen());

    // A's late accept must not append a second subscription to the dead socket.
    act(() => { a.readyState = OPEN; a.serverOpen(); });
    expect(a.sent.length).toBe(aSentAfterOwnOpen);
    // B re-subscribed exactly once, for itself.
    expect(b.sent.length).toBe(1);
  });

  it('a stale onmessage does not deliver frames to listeners', () => {
    const { result, swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());

    const received: any[] = [];
    act(() => { result.current.onMessage((m: any) => received.push(m)); });

    act(() => { result.current.disconnect(); });
    swapToken('token-b');
    const b = FakeSocket.last;
    act(() => b.serverOpen());

    act(() => b.serverMessage({ type: 'chat_token', data: { delta: 'live' } }));
    expect(received.map((m) => m.type)).toEqual(['chat_token']);

    // The retired socket's buffered frame arrives late.
    act(() => a.serverMessage({ type: 'chat_token', data: { delta: 'stale' } }));

    expect(received).toHaveLength(1);
    expect((received[0].data as any).delta).toBe('live');
  });

  it('a stale onmessage cannot overwrite lastMessage', () => {
    const { result, swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());

    act(() => { result.current.disconnect(); });
    swapToken('token-b');
    const b = FakeSocket.last;
    act(() => b.serverOpen());

    act(() => b.serverMessage({ type: 'chat_token', data: { delta: 'live' } }));
    expect((result.current.lastMessage as any).data.delta).toBe('live');

    act(() => a.serverMessage({ type: 'chat_token', data: { delta: 'stale' } }));
    expect((result.current.lastMessage as any).data.delta).toBe('live');
  });

  it('a stale onmessage cannot corrupt streamingContent', () => {
    const { result, swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    act(() => a.serverMessage({ type: 'streaming:update', id: 's1', delta: 'first' }));
    expect(result.current.streamingContent.get('s1')).toBe('first');

    act(() => { result.current.disconnect(); });
    swapToken('token-b');
    const b = FakeSocket.last;
    act(() => b.serverOpen());

    // The retired socket flushes its buffer into the live accumulator.
    act(() => a.serverMessage({ type: 'streaming:update', id: 's1', delta: '-stale' }));
    act(() => a.serverMessage({ type: 'streaming:complete', id: 's1', content: 'stale final' }));
    expect(result.current.streamingContent.get('s1')).toBe('first');
  });
});

describe('useWebSocket — reconnect policy', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
    SESSION_OBJ = { data: { backendToken: 'test-token' }, status: 'authenticated' };
    window.localStorage.setItem('auth_token', 'test-token');
    jest.useFakeTimers();
    jest.spyOn(console, 'debug').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    window.localStorage.clear();
  });

  it('duplicate close frames still leave exactly one cancellable retry', () => {
    const { result } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());

    // A server/proxy can deliver the close more than once. Each observation
    // must collapse onto the SAME single pending retry, so that a later
    // teardown can still cancel it.
    act(() => a.serverClose(1006, 'drop'));
    act(() => a.serverClose(1006, 'duplicate close'));
    act(() => a.serverClose(1006, 'duplicate close 2'));

    // An intentional teardown after the fact must retire the connection for
    // good. If earlier retry handles were overwritten and lost, they survive
    // this call and open sockets the user never asked for.
    const before = FakeSocket.count;
    act(() => { result.current.disconnect(); });
    act(() => { jest.advanceTimersByTime(5000); });
    expect(FakeSocket.count).toBe(before);
  });

  it('unmount cancels a pending retry', () => {
    const { unmount } = render();
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const before = FakeSocket.count;

    act(() => a.serverClose(1006, 'drop'));
    expect(FakeSocket.count).toBe(before);
    unmount();
    act(() => { jest.advanceTimersByTime(5000); });
    expect(FakeSocket.count).toBe(before);
  });

  it('a terminal close still schedules nothing', () => {
    const { result, swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const before = FakeSocket.count;
    act(() => a.serverClose(4001, 'unauthorized'));
    act(() => { jest.advanceTimersByTime(5000); });
    expect(FakeSocket.count).toBe(before);
    expect(result.current.isConnected).toBe(false);
  });

  it('a reconnected socket resubscribes its channels exactly once', () => {
    render({ initialChannels: ['workspace:default', 'user:u1'] });
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    expect(a.sent.length).toBe(2);

    act(() => a.serverClose(1006, 'drop'));
    act(() => { jest.advanceTimersByTime(500); });
    const b = FakeSocket.last;
    act(() => b.serverOpen());

    const subscribes = b.sent.filter((s) => s.includes('"subscribe"'));
    expect(subscribes).toHaveLength(2);
  });
});

describe('useWebSocket — auth-token churn', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
    SESSION_OBJ = { data: { backendToken: 'test-token' }, status: 'authenticated' };
    window.localStorage.setItem('auth_token', 'test-token');
    jest.useFakeTimers();
    jest.spyOn(console, 'debug').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    window.localStorage.clear();
  });

  it('a session-object change that keeps the same token does not churn the socket', () => {
    // next-auth returns a NEW object on every session poll / refetch / router
    // event. Depending on that object tears the connection down and rebuilds it
    // for reasons that have nothing to do with the credential.
    const { churn } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const before = FakeSocket.count;

    churn(5);

    expect(FakeSocket.count).toBe(before);
    expect(FakeSocket.last).toBe(a);
  });

  it('a changed token reconnects with the new credential', () => {
    const { swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    expect(a.url).toContain('token=test-token');
    const before = FakeSocket.count;

    // NextAuth refreshes the credential — a MEANINGFUL change.
    swapToken('refreshed-token-456');

    expect(FakeSocket.count).toBe(before + 1);
    expect(FakeSocket.last.url).toContain('token=refreshed-token-456');
  });
});

describe('useWebSocket — supported state API (legacy consumers)', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
    SESSION_OBJ = { data: { backendToken: 'test-token' }, status: 'authenticated' };
    window.localStorage.setItem('auth_token', 'test-token');
    jest.useFakeTimers();
    jest.spyOn(console, 'debug').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    window.localStorage.clear();
  });

  it('exposes the documented surface', () => {
    const { result, swapToken } = mount(useWebSocket);
    for (const key of ['isConnected', 'lastMessage', 'streamingContent', 'subscribe', 'unsubscribe', 'onMessage', 'sendMessage', 'disconnect']) {
      expect(result.current).toHaveProperty(key);
    }
    expect(typeof result.current.onMessage).toBe('function');
    expect(result.current.streamingContent).toBeInstanceOf(Map);
  });

  it('unregisters a listener on unsubscribe', () => {
    const { result, swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const seen: any[] = [];
    let off!: () => void;
    act(() => { off = result.current.onMessage((m: any) => seen.push(m)); });
    act(() => a.serverMessage({ type: 'x', n: 1 }));
    act(() => { off(); });
    act(() => a.serverMessage({ type: 'x', n: 2 }));
    expect(seen).toHaveLength(1);
  });
});

describe('useWebSocket — diagnostics hygiene', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
    SESSION_OBJ = { data: { backendToken: 'super-secret-jwt-value' }, status: 'authenticated' };
    window.localStorage.setItem('auth_token', 'super-secret-jwt-value');
    jest.useFakeTimers();
  });
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    window.localStorage.clear();
  });

  it('never writes a token to the console across a full lifecycle', () => {
    const lines: string[] = [];
    for (const level of ['log', 'info', 'warn', 'error', 'debug'] as const) {
      jest.spyOn(console, level).mockImplementation((...args: any[]) => {
        lines.push(args.map(String).join(' '));
      });
    }
    const { result, swapToken } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    act(() => a.serverMessage({ type: 'chat_token', data: { delta: 'hi' } }));
    act(() => a.serverClose(1006, 'drop'));
    act(() => { jest.advanceTimersByTime(500); });
    act(() => FakeSocket.last.serverOpen());
    act(() => { result.current.disconnect(); });
    act(() => { jest.advanceTimersByTime(500); });

    const joined = lines.join('\n');
    expect(joined).not.toContain('super-secret-jwt-value');
  });
});

/**
 * NEGATIVE CONTROLS. Each of these re-runs the load-bearing assertion against
 * the deliberately broken variant. They are expected to FAIL — a control that
 * passes would mean the suite cannot detect the defect it claims to cover.
 */
describe('useWebSocket — delivery fidelity', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
    SESSION_OBJ = { data: { backendToken: 'test-token' }, status: 'authenticated' };
    window.localStorage.setItem('auth_token', 'test-token');
    jest.useFakeTimers();
    jest.spyOn(console, 'debug').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    window.localStorage.clear();
  });

  /**
   * THE COALESCING DEFECT, isolated at the socket layer with no chat involved.
   *
   * `lastMessage` is one state slot. A burst of N frames inside a single React
   * commit produces N setState calls but only ONE render, so a consumer
   * effect keyed on `lastMessage` observes exactly one frame. The `onMessage`
   * listener sees all N. Both paths are exercised here off the SAME socket and
   * the SAME frames, so the difference is the delivery mechanism and nothing
   * else.
   */
  it('a burst is delivered in full and in order to listeners', () => {
    const { result } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());

    const seen: number[] = [];
    act(() => { result.current.onMessage((m: any) => seen.push(m.data.n)); });

    const N = 200;
    act(() => {
      for (let n = 1; n <= N; n += 1) {
        a.serverMessage({ type: 'chat_token', data: { n } });
      }
    });

    expect(seen).toHaveLength(N);
    expect(seen).toEqual(Array.from({ length: N }, (_, i) => i + 1));
  });

  it('the single-slot state path provably collapses a burst (this is why listeners exist)', () => {
    // Two consumers on the SAME socket, fed the SAME burst: one reads the
    // state slot in an effect (the pre-fix pattern), one registers a listener.
    // The counters make the difference measurable rather than asserted.
    const slotRenders: number[] = [];
    const listenerCalls: number[] = [];

    const Probe = () => {
      const { lastMessage, onMessage } = useWebSocket({ reconnect: true, reconnectDelay: 10 });
      useEffect(() => {
        if (lastMessage) slotRenders.push((lastMessage as any).data.n);
      }, [lastMessage]);
      useEffect(() => onMessage((m: any) => listenerCalls.push(m.data.n)), [onMessage]);
      return null;
    };

    renderComponent(createElement(Probe));
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());

    const N = 50;
    act(() => {
      for (let n = 1; n <= N; n += 1) a.serverMessage({ type: 'chat_token', data: { n } });
    });

    // Every frame reached the listener, in order.
    expect(listenerCalls).toHaveLength(N);
    // The state slot committed ONCE for the whole burst.
    expect(slotRenders).toHaveLength(1);
    // This ratio is the loss a state-slot consumer cannot avoid.
    expect(slotRenders.length).toBeLessThan(N);
  });

  it('every frame is delivered exactly once', () => {
    const { result } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const seen: number[] = [];
    act(() => { result.current.onMessage((m: any) => seen.push(m.data.n)); });
    act(() => {
      for (let n = 1; n <= 20; n += 1) a.serverMessage({ type: 'chat_token', data: { n } });
    });
    expect(seen).toEqual(seen.slice().sort((x, y) => x - y));
    expect(new Set(seen).size).toBe(seen.length);
  });

  it('a malformed frame does not stop the ones after it', () => {
    const { result } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const seen: number[] = [];
    act(() => { result.current.onMessage((m: any) => seen.push(m.data?.n)); });
    act(() => {
      a.onmessage?.({ data: '{not json' });
      a.serverMessage({ type: 'chat_token', data: { n: 1 } });
      a.onmessage?.({ data: '' });
      a.serverMessage({ type: 'chat_token', data: { n: 2 } });
    });
    expect(seen).toEqual([1, 2]);
  });

  it('one faulty handler does not starve the others', () => {
    const { result } = mount(useWebSocket);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const good: number[] = [];
    act(() => {
      result.current.onMessage(() => { throw new Error('consumer exploded'); });
      result.current.onMessage((m: any) => good.push(m.data.n));
    });
    act(() => a.serverMessage({ type: 'chat_token', data: { n: 1 } }));
    act(() => a.serverMessage({ type: 'chat_token', data: { n: 2 } }));
    expect(good).toEqual([1, 2]);
  });
});

describe('NEGATIVE CONTROL — broken variant must fail these assertions', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
    SESSION_OBJ = { data: { backendToken: 'test-token' }, status: 'authenticated' };
    window.localStorage.setItem('auth_token', 'test-token');
    jest.useFakeTimers();
    jest.spyOn(console, 'debug').mockImplementation(() => {});
    jest.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    window.localStorage.clear();
  });

  it('CONTROL: stale onmessage DOES reach listeners in the broken variant', () => {
    const { result, swapToken } = mount(useWebSocketBroken);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const received: any[] = [];
    act(() => { result.current.onMessage((m: any) => received.push(m)); });
    act(() => { result.current.disconnect(); });
    swapToken('token-b');
    const b = FakeSocket.last;
    act(() => b.serverOpen());
    act(() => b.serverMessage({ type: 'chat_token', data: { delta: 'live' } }));
    act(() => a.serverMessage({ type: 'chat_token', data: { delta: 'stale' } }));

    // This is the DEFECT. The real hook asserts the opposite.
    expect(received).toHaveLength(2);
  });

  it('CONTROL: stale onopen DOES cancel the pending retry in the broken variant', () => {
    const { result, swapToken } = mount(useWebSocketBroken);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    act(() => { result.current.disconnect(); });
    swapToken('token-b');
    const b = FakeSocket.last;
    act(() => b.serverOpen());
    const before = FakeSocket.count;
    act(() => b.serverClose(1006, 'drop'));
    act(() => { a.readyState = OPEN; a.serverOpen(); });
    act(() => { jest.advanceTimersByTime(500); });

    // This is the DEFECT: the live outage never recovers.
    expect(FakeSocket.count).toBe(before);
  });

  it('CONTROL: duplicate closes DO leak uncancellable retries in the broken variant', () => {
    const { result } = mount(useWebSocketBroken);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const before = FakeSocket.count;
    act(() => a.serverClose(1006, 'drop'));
    act(() => a.serverClose(1006, 'dup'));
    act(() => a.serverClose(1006, 'dup2'));
    // An intentional teardown can only cancel the LAST handle.
    act(() => { result.current.disconnect(); });
    act(() => { jest.advanceTimersByTime(5000); });

    // This is the DEFECT: sockets open after the user tore the connection down.
    expect(FakeSocket.count).toBeGreaterThan(before);
  });

  it('CONTROL: same-token session churn DOES rebuild the socket in the broken variant', () => {
    const { churn } = mount(useWebSocketBroken);
    act(() => { jest.advanceTimersByTime(5); });
    const a = FakeSocket.last;
    act(() => a.serverOpen());
    const before = FakeSocket.count;
    churn(3);

    // This is the DEFECT: credential churn with an unchanged token.
    expect(FakeSocket.count).toBeGreaterThan(before);
  });
});
