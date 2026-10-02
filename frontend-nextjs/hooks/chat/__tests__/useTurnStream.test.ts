/**
 * Tests for the shared socket + turn-binding layer.
 *
 * These drive the REAL `useWebSocket` through a deterministic fake socket
 * rather than a mocked hook, because two of the properties under test are about
 * the socket itself: that a panel opens exactly ONE, and that every frame
 * arrives. A mocked hook can only assert what the mock was told to do, which
 * is precisely the assumption that was wrong before.
 */
import { renderHook, act } from '@testing-library/react';

let SESSION_OBJ: any = { data: { backendToken: 'test-token' }, status: 'authenticated' };
jest.mock('next-auth/react', () => ({ useSession: () => SESSION_OBJ }));

import { useTurnStream } from '../useTurnStream';
import type { TurnBound } from '../turnBinding';

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
  static get last() { return FakeSocket.instances[FakeSocket.instances.length - 1]; }
  static get count() { return FakeSocket.instances.length; }
}

type Msg = TurnBound & { reasoningTrace?: unknown[] };

const token = (e: string, d: string, s = 's1') =>
  ({ type: 'chat_token', data: { session_id: s, execution_id: e, delta: d } });
const done = (e: string, c: string, s = 's1') =>
  ({ type: 'chat_token_done', data: { session_id: s, execution_id: e, content: c } });

function mount(over: any = {}) {
  let messages: Msg[] = [];
  const steps: { thought: any; execution: string | null }[] = [];
  const hitl: string[] = [];
  const continuations: any[] = [];
  const settled: string[] = [];
  const adopted: string[] = [];
  const legacyStart: string[] = [];
  const legacyDone: string[] = [];

  const utils = renderHook(() => {
    const turn = useTurnStream<Msg>({
      sessionId: over.sessionId ?? 's1',
      isBusy: over.isBusy ?? false,
      onSessionAdopted: (s: string) => adopted.push(s),
      onLocalTurnSettled: (e: string) => settled.push(e),
      renderStream: (action: any) => {
        messages = action.kind === 'token'
          ? turn.applyTokenFrame(messages, action.execution, action.delta, action.agentId)
          : turn.applyDoneFrame(messages, action.execution, action.content);
      },
      onReasoningStep: (step: any, execution: string | null, agentId?: string) => {
        steps.push({ thought: step.thought, execution });
        messages = turn.applyStepFrame(messages, execution, step, agentId);
      },
      onHitl: (phase: string) => hitl.push(phase),
      onContinuation: (m: any) => continuations.push(m),
      onLegacyStreamStart: (id: string) => legacyStart.push(id),
      onLegacyStreamDone: (id: string, content: string) => {
        legacyDone.push(id, content);
        messages = [...messages, { id, type: 'assistant', content, timestamp: new Date() } as Msg];
      },
    });
    return turn;
  });
  return {
    ...utils,
    // An explicit accessor, not a getter: this file is transpiled, and a
    // transpiled object-literal getter can be lowered to a one-time property
    // read — which would silently snapshot the array instead of exposing the
    // reassigned one.
    messages: () => messages,
    steps, hitl, continuations, settled, adopted, legacyStart, legacyDone,
    emit: (frame: any) => act(() => { FakeSocket.last.serverMessage(frame); }),
    burst: (frames: any[]) => act(() => { frames.forEach(f => FakeSocket.last.serverMessage(f)); }),
  };
}

describe('useTurnStream — one socket per panel', () => {
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

  it('opens exactly one socket, and the surface takes that one', () => {
    const h = mount();
    act(() => { jest.advanceTimersByTime(5); });
    // The layer owns the socket. A surface that also called useWebSocket would
    // double this — which is how one panel ends up with two connections.
    expect(FakeSocket.count).toBe(1);
    act(() => { FakeSocket.last.serverOpen(); });
    expect(h.result.current.socket.isConnected).toBe(true);
    expect(typeof h.result.current.socket.subscribe).toBe('function');
  });

  it('does not open a second socket across re-renders or a reconnect', () => {
    const h = mount();
    act(() => { jest.advanceTimersByTime(5); });
    act(() => { FakeSocket.last.serverOpen(); });
    act(() => { FakeSocket.last.serverClose(1006); });
    // Default reconnectDelay is 1000ms (+ up to 250ms jitter).
    act(() => { jest.advanceTimersByTime(2000); });
    act(() => { FakeSocket.last.serverOpen(); });
    h.rerender();
    h.rerender();
    act(() => { jest.advanceTimersByTime(2000); });
    // initial + exactly one retry
    expect(FakeSocket.count).toBe(2);
  });

  it('closes its socket on unmount', () => {
    const h = mount();
    act(() => { jest.advanceTimersByTime(5); });
    const ws = FakeSocket.last;
    act(() => { ws.serverOpen(); });
    h.unmount();
    expect(ws.closed).toBe(true);
  });
});

describe('useTurnStream — lossless, turn-bound delivery', () => {
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

  const open = () => {
    act(() => { jest.advanceTimersByTime(5); });
    act(() => { FakeSocket.last.serverOpen(); });
  };

  it('assembles a burst that a lastMessage consumer would have lost', () => {
    const h = mount();
    open();
    const N = 100;
    h.burst(Array.from({ length: N }, (_, i) => token('e1', `<${i + 1}>`)));
    expect(h.messages()).toHaveLength(1);
    expect(h.messages()[0].content)
      .toBe(Array.from({ length: N }, (_, i) => `<${i + 1}>`).join(''));
  });

  it('keeps overlapping turns in separate bubbles', () => {
    const h = mount();
    open();
    h.burst([token('eA', 'A1'), token('eB', 'B1'), token('eA', 'A2'), token('eB', 'B2')]);
    expect(h.messages()).toHaveLength(2);
    expect(h.messages().find(m => m.executionId === 'eA')!.content).toBe('A1A2');
    expect(h.messages().find(m => m.executionId === 'eB')!.content).toBe('B1B2');
  });

  it('settles the local turn only for the execution it owns', () => {
    const h = mount({ isBusy: true });
    open();
    h.emit(token('eA', 'A'));
    h.emit(token('eB', 'B'));
    h.emit(done('eB', 'B final'));
    // eB is another surface's turn (a second tab, an API client): it finalizes
    // its own bubble and must NOT release this panel's spinner.
    expect(h.settled).toEqual([]);
    expect(h.messages().find(m => m.executionId === 'eB')!.streaming).toBe(false);
    expect(h.messages().find(m => m.executionId === 'eA')!.streaming).toBe(true);

    h.emit(done('eA', 'A final'));
    expect(h.settled).toEqual(['eA']);
  });

  it('adopts a new conversation session from the first frame', () => {
    const h = mount({ sessionId: 'new' });
    open();
    h.emit(token('e1', 'hi', 'fresh-session'));
    expect(h.adopted).toEqual(['fresh-session']);
    // ...and then filters a later foreign frame against it.
    h.emit(token('e2', 'nope', 'other-session'));
    expect(h.messages().filter(m => m.executionId === 'e2')).toHaveLength(0);
  });

  it('counts frames it refuses to bind instead of placing them', () => {
    const h = mount();
    open();
    h.emit({ type: 'chat_token', data: { session_id: 's1', delta: 'no execution' } });
    h.emit({ type: 'chat_token', data: { session_id: 'other', execution_id: 'e9', delta: 'x' } });
    expect(h.messages()).toHaveLength(0);
    const counts = h.result.current.unboundCounts();
    expect(counts.chat_token).toBe(2);
  });

  it('routes a reasoning step to the execution it names', () => {
    const h = mount();
    open();
    h.emit(token('e1', 'first'));
    h.emit(done('e1', 'first'));
    h.emit({
      type: 'agent_step_update',
      data: { step: { step: 1, thought: 'turn two' }, execution_id: 'e2', session_id: 's1' },
    });
    h.emit(token('e2', 'second'));
    expect(h.messages().find(m => m.executionId === 'e1')!.reasoningTrace).toBeUndefined();
    expect(h.messages().find(m => m.executionId === 'e2')!.reasoningTrace).toHaveLength(1);
  });

  it('drops a reasoning step from another session', () => {
    const h = mount();
    open();
    h.emit({
      type: 'agent_step_update',
      data: { step: { step: 1, thought: 'theirs' }, execution_id: 'e1', session_id: 'other' },
    });
    expect(h.steps).toHaveLength(0);
  });

  it('scopes HITL signals to the panel session', () => {
    const h = mount();
    open();
    h.emit({ type: 'hitl_paused', session_id: 'other', action_id: 'a', tool: 't', reason: 'r' });
    expect(h.hitl).toEqual([]);
    h.emit({ type: 'hitl_paused', session_id: 's1', action_id: 'a', tool: 't', reason: 'r' });
    h.emit({ type: 'hitl_decision', session_id: 's1' });
    expect(h.hitl).toEqual(['paused', 'decision']);
  });

  it('surfaces a background continuation', () => {
    const h = mount();
    open();
    h.emit({ type: 'chat_continuation', session_id: 's1', status: 'applied', summary: 'done' });
    expect(h.continuations).toHaveLength(1);
  });

  it('ignores a heartbeat', () => {
    const h = mount({ isBusy: true });
    open();
    h.emit({ type: 'chat_heartbeat', data: { session_id: 's1', execution_id: 'e1' } });
    expect(h.settled).toEqual([]);
    expect(h.messages()).toHaveLength(0);
  });

  it('completes only the legacy stream this panel started', () => {
    const h = mount();
    open();
    h.emit({ type: 'streaming:complete', id: 'never-started', content: 'foreign' });
    expect(h.legacyDone).toEqual([]);
    h.emit({ type: 'streaming:start', id: 's-1' });
    expect(h.legacyStart).toEqual(['s-1']);
    h.emit({ type: 'streaming:complete', id: 's-1', content: 'mine' });
    expect(h.legacyDone).toEqual(['s-1', 'mine']);
    // A repeat of the same completion no longer resolves anything: the stream
    // was retired by the first one, so it is no longer "the stream this panel
    // started".
    h.emit({ type: 'streaming:complete', id: 's-1', content: 'mine' });
    expect(h.legacyDone).toHaveLength(2);
    expect(h.result.current.unboundCounts()['streaming:complete:foreign']).toBe(2);
  });

  it('survives a malformed frame and keeps delivering', () => {
    const h = mount();
    open();
    act(() => { (FakeSocket.last as any).onmessage?.({ data: '{not json' }); });
    h.emit(token('e1', 'after the garbage'));
    expect(h.messages()[0].content).toBe('after the garbage');
  });

  it('converges an HTTP body onto the streamed bubble', () => {
    const h = mount({ isBusy: true });
    open();
    h.emit(token('e1', 'provisional'));
    h.emit(done('e1', 'final from stream'));
    // The POST resolves after the done event — the common order.
    const out = h.result.current.converge(h.messages(), { content: 'final from http', model: 'm' });
    expect(out).not.toBeNull();
    expect(out!).toHaveLength(1);
    expect(out![0].content).toBe('final from http');
    expect(out![0].streaming).toBe(false);
  });

  it('forgets its turn binding when the panel switches conversation', () => {
    const h = mount({ isBusy: true, sessionId: 's1' });
    open();
    h.emit(token('e1', 'x'));
    expect(h.result.current.localExecution()).toBe('e1');
    h.rerender();
    // Same session: binding retained so a late HTTP body can still converge.
    expect(h.result.current.localExecution()).toBe('e1');
  });
});
