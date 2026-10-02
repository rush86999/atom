/**
 * A mock seam for `useWebSocket` in tests.
 *
 * WHY THIS EXISTS. Consumers read socket frames through the hook's `onMessage`
 * listener rather than its `lastMessage` state slot, because that slot is ONE
 * slot: a burst of frames inside a single render commit produces one commit, so
 * a consumer effect keyed on it observes only the newest frame. A test that
 * mocks the hook by handing out a `lastMessage` state slot therefore cannot
 * exercise the path production uses — it silently tests the coalescing
 * behaviour the code no longer has.
 *
 * `createWebSocketMock()` returns a `useWebSocket` replacement that keeps BOTH
 * surfaces, so a test can drive either:
 *
 *   - `wsMock().emit(frame)`     — one frame, to the slot AND every listener,
 *                                   exactly as the real hook does on the wire;
 *   - `wsMock().burst(frames)`    — a whole burst inside ONE act(), which is
 *                                   what makes the difference observable: a
 *                                   slot-driven consumer sees one frame, a
 *                                   listener-driven consumer sees all of them;
 *   - `wsMock().connect()`        — flip `isConnected` (and record subscribes).
 *
 * Usage, once per test file at module scope:
 *
 *   import { createWebSocketMock, wsMock } from '../../../tests/helpers/wsMock';
 *   jest.mock('@/hooks/useWebSocket', () => ({ useWebSocket: createWebSocketMock() }));
 *
 *   beforeEach(() => wsMock().reset());
 *   ...
 *   act(() => { wsMock().burst(frames); });
 */
import { act } from '@testing-library/react';

const React = require('react') as typeof import('react');

type Listener = (m: any) => void;

type Store = {
  React: typeof import('react');
  listeners: Set<Listener>;
  subscribeCalls: string[];
  sent: any[];
  /** Setters published by the most recently rendered mock hook instance. */
  setLastMessage: ((m: any) => void) | null;
  setConnectedState: ((c: boolean) => void) | null;
};

const store: Store = {
  React,
  listeners: new Set(),
  subscribeCalls: [],
  sent: [],
  setLastMessage: null,
  setConnectedState: null,
};

export type WebSocketMockBridge = {
  /** Deliver one frame to the state slot and every registered listener. */
  emit: (frame: any) => void;
  /** Deliver a burst inside ONE act — see the note on `burst` above. */
  burst: (frames: any[]) => void;
  /** Flip the mocked `isConnected`. */
  connect: () => void;
  disconnect: () => void;
  /** How many listeners are currently registered. */
  listenerCount: () => number;
  /** Channels passed to `subscribe()` so far. */
  subscribeCalls: () => string[];
  /** Payloads passed to `sendMessage()` so far. */
  sent: () => any[];
  /** Clear listeners and call records between tests. */
  reset: () => void;
};

const bridge: WebSocketMockBridge = {
  emit: (frame) => {
    act(() => {
      store.setLastMessage?.(frame);
      store.listeners.forEach((h) => h(frame));
    });
  },
  burst: (frames) => {
    // One act() for the whole burst: React coalesces the state updates, so a
    // slot-driven consumer sees only the final frame while every listener still
    // sees all of them. That difference is the whole point of the listener.
    act(() => {
      for (const frame of frames) {
        store.setLastMessage?.(frame);
        store.listeners.forEach((h) => h(frame));
      }
    });
  },
  connect: () => { act(() => { store.setConnectedState?.(true); }); },
  disconnect: () => { act(() => { store.setConnectedState?.(false); }); },
  listenerCount: () => store.listeners.size,
  subscribeCalls: () => store.subscribeCalls,
  sent: () => store.sent,
  reset: () => {
    store.listeners.clear();
    store.subscribeCalls.length = 0;
    store.sent.length = 0;
    store.setLastMessage = null;
    store.setConnectedState = null;
  },
};

/** The bridge. Read it at call time so the store is shared across suites. */
export const wsMock = (): WebSocketMockBridge => bridge;

/** Pass the RESULT of this call to `jest.mock`. */
export function createWebSocketMock(overrides: Record<string, any> = {}) {
  // A consumer that registers its listener on mount cannot be primed through
  // the state slot, so `seed` names a frame the mock replays to the FIRST
  // listener that registers. That mirrors reality: a frame can arrive before a
  // consumer subscribes, and the consumer still needs to see it.
  const seed = overrides.seed;
  // `isConnectedOf` is a LIVE reader, unlike a plain `isConnected` override
  // (an object spread evaluates a getter once, so the component would never see
  // the test flip the connection). Use it when a test drives connection state
  // from its own variable; `bridge.connect()` covers the common case.
  const isConnectedOf = overrides.isConnectedOf;
  return function useWebSocketMock() {
    const React = store.React;
    const [lastMessage, setLastMessage] = React.useState<any>(null);
    const [isConnected, setIsConnected] = React.useState(false);
    const [streamingContent] = React.useState(() => new Map<string, string>());

    store.setLastMessage = setLastMessage;
    store.setConnectedState = setIsConnected;

    const onMessage = React.useCallback((handler: Listener) => {
      const isFirst = store.listeners.size === 0;
      store.listeners.add(handler);
      if (isFirst && typeof seed === 'function') {
        const frame = seed();
        if (frame) handler(frame);
      }
      return () => { store.listeners.delete(handler); };
    }, []);

    return {
      isConnected: isConnectedOf ? isConnectedOf() || isConnected : isConnected,
      lastMessage,
      streamingContent,
      onMessage,
      subscribe: (channel: string) => { store.subscribeCalls.push(channel); },
      unsubscribe: () => {},
      sendMessage: (m: any) => { store.sent.push(m); },
      disconnect: () => {},
      reconnectAttempts: 0,
      ...overrides,
      // `seed` is a mock-time concern, not part of the hook's surface.
      seed: undefined,
    };
  };
}
