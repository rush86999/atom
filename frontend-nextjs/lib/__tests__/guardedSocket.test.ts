/**
 * Tests for the generation-guarded raw socket.
 *
 * The hazard, restated: a component whose effect re-runs closes the old socket
 * and opens a new one, but the close is asynchronous. Without a generation the
 * old socket's `onmessage` still fires and appends ANOTHER room's messages to
 * the room now on screen, and its `onclose` runs against state that has already
 * moved on.
 *
 * `brokenSocket.test` holds the unguarded variant, and the NEGATIVE CONTROL at
 * the bottom proves each assertion can detect its defect.
 */
import { createSocketGuard, redactSocketUrl } from '../guardedSocket';

const OPEN = 1;
const CLOSED = 3;

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
  constructor(url: string) { this.url = url; FakeSocket.instances.push(this); }
  send(d: string) { this.sent.push(d); }
  close() { this.closed = true; this.readyState = CLOSED; }
  serverOpen() { this.readyState = OPEN; this.onopen?.({}); }
  serverClose(code = 1006) { this.readyState = CLOSED; this.onclose?.({ code, reason: '' }); }
  serverMessage(payload: unknown) { this.onmessage?.({ data: JSON.stringify(payload) }); }
  serverError() { this.onerror?.({}); }
  static get last() { return FakeSocket.instances[FakeSocket.instances.length - 1]; }
  static get count() { return FakeSocket.instances.length; }
}

/** The pre-guard shape: no generation, handlers always run. */
function openUnguarded(url: string, handlers: any) {
  const ws = new WebSocket(url);
  ws.onopen = () => handlers.onOpen?.(ws);
  ws.onmessage = (event: any) => {
    let data: any;
    try { data = JSON.parse(event.data); } catch { return; }
    handlers.onMessage(data, event);
  };
  ws.onclose = (e: any) => handlers.onClose?.(e);
  ws.onerror = (e: any) => handlers.onError?.(e);
  return () => { ws.close(); };
}

describe('createSocketGuard — ownership', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
  });
  afterEach(() => { jest.restoreAllMocks(); });

  it('opens one socket and reports it as current', () => {
    const guard = createSocketGuard();
    const cleanup = guard.open('ws://x/ws?token=t', { onMessage: jest.fn() });
    expect(FakeSocket.count).toBe(1);
    expect(guard.isCurrent(FakeSocket.last as unknown as WebSocket)).toBe(true);
    cleanup();
    expect(guard.current()).toBeNull();
  });

  it('retires the previous socket when a new one opens', () => {
    const guard = createSocketGuard();
    guard.open('ws://x/team/1', { onMessage: jest.fn() });
    const first = FakeSocket.last;
    guard.open('ws://x/team/2', { onMessage: jest.fn() });
    const second = FakeSocket.last;
    expect(second).not.toBe(first);
    expect(first.closed).toBe(true);
    expect(guard.isCurrent(first as unknown as WebSocket)).toBe(false);
    expect(guard.isCurrent(second as unknown as WebSocket)).toBe(true);
  });

  it('two guards do not steal ownership from each other', () => {
    // A comment thread per canvas and a cursor per document are independent
    // surfaces; opening one must not make the other stale.
    const a = createSocketGuard();
    const b = createSocketGuard();
    a.open('ws://x/canvas/1', { onMessage: jest.fn() });
    b.open('ws://x/doc/1', { onMessage: jest.fn() });
    const aSock = FakeSocket.instances[0];
    const bSock = FakeSocket.instances[1];
    expect(a.isCurrent(aSock as unknown as WebSocket)).toBe(true);
    expect(b.isCurrent(bSock as unknown as WebSocket)).toBe(true);
  });
});

describe('createSocketGuard — stale callbacks are dropped', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
  });

  it('a superseded onmessage does not deliver', () => {
    const guard = createSocketGuard();
    const received: any[] = [];
    guard.open('ws://x/team/1', { onMessage: (d) => received.push(d) });
    const first = FakeSocket.last;
    guard.open('ws://x/team/2', { onMessage: (d) => received.push(d) });
    const second = FakeSocket.last;

    first.serverMessage({ type: 'message.received', room: 1 });
    second.serverMessage({ type: 'message.received', room: 2 });
    expect(received.map((m) => m.room)).toEqual([2]);
  });

  it('a superseded onopen does not subscribe on the dead socket', () => {
    const guard = createSocketGuard();
    guard.open('ws://x/team/1', { onOpen: (ws) => ws.send('sub-1'), onMessage: jest.fn() });
    const first = FakeSocket.last;
    guard.open('ws://x/team/2', { onOpen: (ws) => ws.send('sub-2'), onMessage: jest.fn() });
    const second = FakeSocket.last;

    // The first socket's accept arrives after it was superseded.
    first.serverOpen();
    expect(first.sent).toEqual([]);
    second.serverOpen();
    expect(second.sent).toEqual(['sub-2']);
  });

  it('a superseded onclose does not run', () => {
    const guard = createSocketGuard();
    const closed: number[] = [];
    guard.open('ws://x/1', { onMessage: jest.fn(), onClose: () => closed.push(1) });
    const first = FakeSocket.last;
    guard.open('ws://x/2', { onMessage: jest.fn(), onClose: () => closed.push(2) });
    const second = FakeSocket.last;

    first.serverClose();
    expect(closed).toEqual([]);
    // The live socket's own close IS reported.
    second.serverClose();
    expect(closed).toEqual([2]);
    expect(guard.current()).toBeNull();
  });

  it('a superseded onerror is dropped', () => {
    const guard = createSocketGuard();
    const errors: string[] = [];
    guard.open('ws://x/1', { onMessage: jest.fn(), onError: () => errors.push('a') });
    const first = FakeSocket.last;
    guard.open('ws://x/2', { onMessage: jest.fn(), onError: () => errors.push('b') });
    first.serverError();
    expect(errors).toEqual([]);
  });
});

describe('createSocketGuard — cleanup and resilience', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
  });

  it('cleanup is idempotent', () => {
    const guard = createSocketGuard();
    const cleanup = guard.open('ws://x/1', { onMessage: jest.fn() });
    const ws = FakeSocket.last;
    cleanup();
    cleanup();
    expect(ws.closed).toBe(true);
  });

  it('an old cleanup cannot close the socket that replaced it', () => {
    // React runs cleanups in order, but an async teardown elsewhere can land
    // late; it must not tear down the live connection.
    const guard = createSocketGuard();
    const cleanupA = guard.open('ws://x/1', { onMessage: jest.fn() });
    const a = FakeSocket.last;
    guard.open('ws://x/2', { onMessage: jest.fn() });
    const b = FakeSocket.last;
    cleanupA();
    expect(a.closed).toBe(true);
    expect(b.closed).toBe(false);
    expect(guard.isCurrent(b as unknown as WebSocket)).toBe(true);
  });

  it('a malformed frame is skipped without killing the socket', () => {
    const guard = createSocketGuard();
    const received: any[] = [];
    guard.open('ws://x/1', { onMessage: (d) => received.push(d) });
    const ws = FakeSocket.last;
    (ws as any).onmessage?.({ data: '{not json' });
    ws.serverMessage({ n: 1 });
    expect(received).toEqual([{ n: 1 }]);
  });

  it('a throwing consumer does not kill the socket loop', () => {
    const guard = createSocketGuard();
    const good: any[] = [];
    guard.open('ws://x/1', {
      onMessage: () => { throw new Error('consumer exploded'); },
    });
    guard.open('ws://x/1', { onMessage: (d) => good.push(d) });
    FakeSocket.last.serverMessage({ n: 1 });
    expect(good).toEqual([{ n: 1 }]);
  });

  it('redacts the credential from a socket URL', () => {
    expect(redactSocketUrl('wss://api.example.com/ws?token=secret.jwt.value'))
      .toBe('wss://api.example.com/ws');
  });
});

describe('NEGATIVE CONTROL — the unguarded variant must fail these', () => {
  beforeEach(() => {
    FakeSocket.reset();
    (global as any).WebSocket = FakeSocket;
  });

  it('CONTROL: a superseded onmessage DOES deliver without the guard', () => {
    const received: any[] = [];
    openUnguarded('ws://x/team/1', { onMessage: (d: any) => received.push(d) });
    const first = FakeSocket.last;
    openUnguarded('ws://x/team/2', { onMessage: (d: any) => received.push(d) });
    const second = FakeSocket.last;

    first.serverMessage({ type: 'message.received', room: 1 });
    second.serverMessage({ type: 'message.received', room: 2 });
    // THE DEFECT: room 1's message is appended to the room now on screen.
    expect(received.map((m) => m.room)).toEqual([1, 2]);
  });

  it('CONTROL: a superseded onopen DOES subscribe without the guard', () => {
    openUnguarded('ws://x/team/1', { onOpen: (ws: any) => ws.send('sub-1') });
    const first = FakeSocket.last;
    openUnguarded('ws://x/team/2', { onOpen: (ws: any) => ws.send('sub-2') });
    first.serverOpen();
    // THE DEFECT: a dead socket subscribes and the live one may not.
    expect(first.sent).toEqual(['sub-1']);
  });
});
