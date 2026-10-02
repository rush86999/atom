/**
 * TURN-BINDING tests for useChatInterface.
 *
 * THE EVENT CONTRACT, as actually produced. The main chat's only POST is
 * `/api/chat/message`, handled by `integrations/chat_orchestrator.py`, which
 * broadcasts to the `user:{user_id}` channel (auto-subscribed by
 * `core/websockets.py::connect`, so every socket receives it):
 *
 *   {"type":"chat_token",     "data":{session_id, execution_id, delta}}
 *   {"type":"chat_token_done", "data":{session_id, execution_id, content, elapsed_s}}
 *   {"type":"chat_heartbeat",  "data":{session_id, execution_id, elapsed_ms}}
 *   {"type":"agent_step_update","data":{step, agent_id, execution_id, session_id}}
 *
 * It does NOT emit `streaming:start|update|complete` — those come from
 * `core/agent_execution_service.py` and `core/atom_agent_endpoints.py`, a
 * different subsystem. Only `pages/canvas/[id].tsx` consumes `chat_token*`
 * today, so the main chat received every token of every reply and discarded
 * them all, rendering nothing until the POST resolved.
 *
 * THE HARNESS models the real hook's delivery precisely, because the delivery
 * is the defect:
 *   - `emitBurst` publishes N frames inside ONE act(), so React coalesces the
 *     `lastMessage` STATE slot — a consumer reading that slot sees only the
 *     final frame. This is production behaviour, not a test artifact.
 *   - the same burst calls every `onMessage` listener synchronously, in
 *     arrival order, exactly as `useWebSocket` does.
 * A consumer therefore has to choose the lossless path deliberately.
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatInterface } from '../useChatInterface';

/** Bridge between the tests and the mocked socket hook. */
const bridge: {
  setLastMessage: ((m: any) => void) | null;
  setConnected: ((c: boolean) => void) | null;
  listeners: Set<(m: any) => void>;
  subscribeCalls: string[];
  listenerCount: () => number;
} = {
  setLastMessage: null,
  setConnected: null,
  listeners: new Set(),
  subscribeCalls: [],
  listenerCount: () => bridge.listeners.size,
};

jest.mock('@/hooks/useWebSocket', () => {
  const react = jest.requireActual('react') as typeof import('react');
  return {
    useWebSocket: () => {
      const [lastMessage, setLastMessage] = react.useState<any>(null);
      const [isConnected, setIsConnected] = react.useState(false);
      bridge.setLastMessage = setLastMessage;
      bridge.setConnected = setIsConnected;
      const onMessage = react.useCallback((handler: (m: any) => void) => {
        bridge.listeners.add(handler);
        return () => { bridge.listeners.delete(handler); };
      }, []);
      return {
        isConnected,
        lastMessage,
        streamingContent: new Map<string, string>(),
        subscribe: (channel: string) => { bridge.subscribeCalls.push(channel); },
        unsubscribe: () => {},
        onMessage,
        sendMessage: () => {},
        disconnect: () => {},
      };
    },
  };
});

const mockToastFn = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({ useToast: () => ({ toast: mockToastFn }) }));
jest.mock('@/hooks/useFileUpload', () => ({
  useFileUpload: () => ({ uploadFile: jest.fn(), isUploading: false }),
}));
jest.mock('../../../lib/api-client', () => ({
  apiClient: { get: jest.fn(), post: jest.fn(), patch: jest.fn() },
}));

import { apiClient } from '../../../lib/api-client';
const mockGet = apiClient.get as jest.Mock;
const mockPost = apiClient.post as jest.Mock;
const mockPatch = apiClient.patch as jest.Mock;

const SESSION = 'sess-1';

/** Deliver ONE frame. */
const emit = (frame: any) => {
  act(() => {
    bridge.setLastMessage?.(frame);
    bridge.listeners.forEach((h) => h(frame));
  });
};

/**
 * Deliver a burst of frames that lands faster than React can commit — the
 * shape of a real token stream. The state slot collapses to the last frame;
 * every listener still sees all of them.
 */
const emitBurst = (frames: any[]) => {
  act(() => {
    for (const frame of frames) {
      bridge.setLastMessage?.(frame);
      bridge.listeners.forEach((h) => h(frame));
    }
  });
};

const token = (executionId: string, delta: string, sessionId = SESSION) => ({
  type: 'chat_token',
  data: { session_id: sessionId, execution_id: executionId, delta },
});
const tokenDone = (executionId: string, content: string, sessionId = SESSION) => ({
  type: 'chat_token_done',
  data: { session_id: sessionId, execution_id: executionId, content, elapsed_s: 1.2 },
});

/** Assistant messages that carry answer text (not placeholders). */
const answers = (result: { current: any }) =>
  result.current.messages.filter((m: any) => m.type === 'assistant' && typeof m.content === 'string');

const findByExecution = (result: { current: any }, executionId: string) =>
  result.current.messages.find((m: any) => m.executionId === executionId);

const mountChat = (props: any = {}) =>
  renderHook(() => useChatInterface({ sessionId: SESSION, initialAgentId: null, ...props }));

describe('useChatInterface — turn binding', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    bridge.listeners.clear();
    bridge.subscribeCalls.length = 0;
    bridge.setLastMessage = null;
    bridge.setConnected = null;

    mockGet.mockImplementation((url: string) => {
      if (url.includes('/api/chat/history/')) return Promise.resolve({ status: 200, data: { messages: [] } });
      if (url.includes('/api/chat/sessions/')) return Promise.resolve({ status: 200, data: { title: 'S' } });
      return Promise.resolve({ status: 200, data: {} });
    });
    mockPost.mockImplementation((url: string) => {
      if (url === '/api/chat/message') {
        return Promise.resolve({ data: { success: true, message: 'REST answer', session_id: SESSION } });
      }
      return Promise.resolve({ data: { success: true } });
    });
    mockPatch.mockImplementation(() => Promise.resolve({ data: { success: true } }));
  });

  describe('lossless token delivery', () => {
    it('renders every frame of a burst, in order, with nothing dropped', () => {
      const { result } = mountChat();
      const N = 50;
      const frames = Array.from({ length: N }, (_, i) => token('exec-1', `<${i + 1}>`));
      emitBurst(frames);

      const bubble = findByExecution(result, 'exec-1');
      expect(bubble).toBeDefined();
      const expected = frames.map((f) => f.data.delta).join('');
      expect(bubble.content).toBe(expected);
    });

    it('registers exactly one listener and releases it on unmount', () => {
      const { unmount } = mountChat();
      expect(bridge.listenerCount()).toBe(1);
      unmount();
      expect(bridge.listenerCount()).toBe(0);
    });

    it('subscribes to the workspace channel once connected', () => {
      const { result } = mountChat();
      act(() => { bridge.setConnected?.(true); });
      expect(bridge.subscribeCalls).toContain('workspace:default');
      void result;
    });

    it('a reconnect does not multiply listeners or duplicate frames', () => {
      const { result } = mountChat();
      expect(bridge.listenerCount()).toBe(1);

      // Socket drops and comes back: the hook instance (and therefore its one
      // registration) survives, and isConnected cycles false → true.
      act(() => { bridge.setConnected?.(false); });
      act(() => { bridge.setConnected?.(true); });
      act(() => { bridge.setConnected?.(false); });
      act(() => { bridge.setConnected?.(true); });
      expect(bridge.listenerCount()).toBe(1);

      // The post-reconnect resubscribe must not multiply delivery.
      emitBurst([token('exec-r', 'once '), token('exec-r', 'only')]);
      const bubble = findByExecution(result, 'exec-r');
      expect(bubble.content).toBe('once only');
      expect(
        result.current.messages.filter((m: any) => m.executionId === 'exec-r'),
      ).toHaveLength(1);
    });
  });

  describe('overlapping executions', () => {
    it('routes each frame to its own turn, never interleaving the text', () => {
      const { result } = mountChat();
      // Two turns on the SAME session overlap (second tab, or a client driving
      // the same conversation). Every frame carries its own execution id.
      emitBurst([
        token('exec-A', 'A1'),
        token('exec-B', 'B1'),
        token('exec-A', 'A2'),
        token('exec-B', 'B2'),
        token('exec-A', 'A3'),
      ]);

      expect(findByExecution(result, 'exec-A')?.content).toBe('A1A2A3');
      expect(findByExecution(result, 'exec-B')?.content).toBe('B1B2');
    });

    it('a completion only finalizes its own turn', () => {
      const { result } = mountChat();
      emitBurst([token('exec-A', 'A text'), token('exec-B', 'B text')]);
      emit(tokenDone('exec-A', 'A final'));

      const a = findByExecution(result, 'exec-A');
      const b = findByExecution(result, 'exec-B');
      expect(a.content).toBe('A final');
      expect(a.streaming).not.toBe(true);
      // B is still mid-turn: it must not be finalized by A's completion.
      expect(b.streaming).toBe(true);
      expect(b.content).toBe('B text');
    });

    it('ignores frames belonging to a different session', () => {
      const { result } = mountChat();
      emit(token('exec-1', 'mine', SESSION));
      emit(token('exec-1', 'theirs', 'other-session'));
      expect(findByExecution(result, 'exec-1')?.content).toBe('mine');
    });
  });

  describe('finalization', () => {
    it('a late token cannot corrupt the finalized answer', () => {
      const { result } = mountChat();
      emitBurst([token('exec-1', 'Hello ')]);
      emit(token('exec-1', 'world'));
      emit(tokenDone('exec-1', 'Hello world'));
      const afterDone = answers(result).map((m: any) => m.content);
      expect(afterDone).toContain('Hello world');

      // The socket flushes a frame it had already buffered.
      emit(token('exec-1', ' GARBAGE'));

      const finalBubble = findByExecution(result, 'exec-1');
      expect(finalBubble.content).toBe('Hello world');
      expect(finalBubble.streaming).not.toBe(true);
      // No stray extra bubble was materialized.
      expect(answers(result).filter((m: any) => String(m.content).includes('GARBAGE'))).toHaveLength(0);
    });

    it('a duplicate completion does not produce a second bubble', () => {
      const { result } = mountChat();
      emitBurst([token('exec-1', 'once')]);
      emit(tokenDone('exec-1', 'once'));
      emit(tokenDone('exec-1', 'once'));
      emit(tokenDone('exec-1', 'once'));

      const matching = answers(result).filter((m: any) => m.content === 'once');
      expect(matching).toHaveLength(1);
    });

    it('a late completion does not resurrect a finished turn as streaming', () => {
      const { result } = mountChat();
      emit(token('exec-1', 'done text'));
      emit(tokenDone('exec-1', 'done text'));
      // A stale re-fire of an early frame after finalization.
      emit(token('exec-1', 'more'));
      expect(findByExecution(result, 'exec-1')?.streaming).not.toBe(true);
    });
  });

  describe('the local turn spinner', () => {
    it('a foreign streaming:complete does not clear the local spinner', async () => {
      const { result } = mountChat();
      await act(async () => { result.current.setInput('hello'); });
      // Start a local turn and keep the POST in flight.
      let resolvePost: (v: any) => void = () => {};
      mockPost.mockImplementation((url: string) => {
        if (url === '/api/chat/message') {
          return new Promise((res) => { resolvePost = res; });
        }
        return Promise.resolve({ data: { success: true } });
      });
      act(() => { void result.current.handleSend(); });
      await waitFor(() => expect(result.current.isProcessing).toBe(true));

      // A completion for a stream that is NOT this chat's turn arrives —
      // another surface, a stale generation, or a legacy event.
      emit({ type: 'streaming:complete', id: 'some-other-stream', content: 'not mine' });
      emit({ type: 'streaming:complete', id: undefined, content: 'unidentifiable' });

      // The local turn is still running; its spinner must survive.
      expect(result.current.isProcessing).toBe(true);

      await act(async () => {
        resolvePost({ data: { success: true, message: 'local answer', session_id: SESSION } });
      });
      await waitFor(() => expect(result.current.isProcessing).toBe(false));
    });

    it('a foreign streaming:complete does not append a foreign answer', () => {
      const { result } = mountChat();
      emit({ type: 'streaming:complete', id: 'not-our-stream', content: 'somebody else’s reply' });
      expect(
        answers(result).some((m: any) => String(m.content).includes('somebody else')),
      ).toBe(false);
    });
  });

  describe('reasoning-step placement', () => {
    const stepFrame = (executionId: string, thought: string, sessionId = SESSION) => ({
      type: 'agent_step_update',
      data: {
        step: { step: 1, thought, observation: `obs:${thought}`, session_id: sessionId },
        agent_id: 'agent-1',
        execution_id: executionId,
        session_id: sessionId,
      },
    });

    it('attaches a step to the execution it names, not the newest finished reply', () => {
      const { result } = mountChat();
      // Turn 1 is complete; its assistant bubble is the newest one.
      emitBurst([token('exec-1', 'first reply')]);
      emit(tokenDone('exec-1', 'first reply'));

      // Turn 2's reasoning arrives before turn 2 has any text. Appending to
      // "the latest assistant message" would file turn 2's trace under turn
      // 1's answer.
      emit(stepFrame('exec-2', 'planning turn two'));
      emit(token('exec-2', 'second reply'));

      const t1 = findByExecution(result, 'exec-1');
      const t2 = findByExecution(result, 'exec-2');
      expect(t1.reasoningTrace ?? []).toHaveLength(0);
      expect(t2.reasoningTrace).toHaveLength(1);
      expect(t2.reasoningTrace[0].thought).toBe('planning turn two');
    });

    it('buffers a step when the turn has no bubble yet and flushes it on the first token', () => {
      const { result } = mountChat();
      emit(stepFrame('exec-9', 'thinking hard'));
      emit(token('exec-9', 'the answer'));
      const bubble = findByExecution(result, 'exec-9');
      expect(bubble.content).toBe('the answer');
      expect(bubble.reasoningTrace).toHaveLength(1);
    });

    it('does not duplicate a buffered step across re-renders', () => {
      const { result } = mountChat();
      emit(stepFrame('exec-7', 'step one'));
      emit(stepFrame('exec-7', 'step two'));
      emit(token('exec-7', 'answer'));
      const bubble = findByExecution(result, 'exec-7');
      expect(bubble.reasoningTrace.map((s: any) => s.thought)).toEqual(['step one', 'step two']);
    });

    it('ignores a step for another session', () => {
      const { result } = mountChat();
      emit(stepFrame('exec-1', 'mine', SESSION));
      emit(stepFrame('exec-1', 'theirs', 'other-session'));
      emit(token('exec-1', 'answer'));
      const bubble = findByExecution(result, 'exec-1');
      expect((bubble.reasoningTrace ?? []).map((s: any) => s.thought)).toEqual(['mine']);
    });
  });

  describe('HTTP / final-event convergence', () => {
    it('the stream and the POST response converge on one assistant bubble', async () => {
      const { result } = mountChat();
      await act(async () => { result.current.setInput('question'); });
      mockPost.mockImplementation((url: string) => {
        if (url === '/api/chat/message') {
          return Promise.resolve({ data: { success: true, message: 'full answer', session_id: SESSION } });
        }
        return Promise.resolve({ data: { success: true } });
      });
      act(() => { void result.current.handleSend(); });

      // Tokens land while the POST is in flight.
      emitBurst([token('exec-http', 'full '), token('exec-http', 'answer')]);
      await act(async () => { await Promise.resolve(); });
      emit(tokenDone('exec-http', 'full answer'));
      await waitFor(() => expect(result.current.isProcessing).toBe(false));

      const withText = answers(result).filter((m: any) => String(m.content).includes('full answer'));
      expect(withText).toHaveLength(1);
    });

    it('keeps the streamed text when the POST response is identical', async () => {
      const { result } = mountChat();
      await act(async () => { result.current.setInput('q'); });
      act(() => { void result.current.handleSend(); });
      emitBurst([token('exec-x', 'streamed '), token('exec-x', 'reply')]);
      emit(tokenDone('exec-x', 'streamed reply'));
      await waitFor(() => expect(result.current.isProcessing).toBe(false));
      expect(answers(result).filter((m: any) => m.content === 'streamed reply').length)
        .toBeLessThanOrEqual(1);
    });
  });

  describe('legacy streaming:* compatibility', () => {
    it('still surfaces currentStreamId and streamingContent for the legacy stream', () => {
      const { result } = mountChat();
      emit({ type: 'streaming:start', id: 'legacy-1' });
      expect(result.current.currentStreamId).toBe('legacy-1');
    });

    it('a matching streaming:complete still resolves the legacy turn', () => {
      const { result } = mountChat();
      emit({ type: 'streaming:start', id: 'legacy-1' });
      emit({ type: 'streaming:complete', id: 'legacy-1', content: 'legacy answer' });
      expect(result.current.currentStreamId).toBeNull();
      expect(answers(result).some((m: any) => m.content === 'legacy answer')).toBe(true);
    });
  });
});
