/**
 * Tests for the shared turn-binding mechanism.
 *
 * `hooks/chat/turnBinding.ts` is the general layer: every surface that POSTs to
 * `/api/chat/message` receives that turn's `chat_token` / `chat_token_done` /
 * `agent_step_update` frames on its socket, and each of them needs the same
 * decisions about which reply a frame belongs to. These tests pin those
 * decisions as pure functions, with no socket and no React render, so a
 * regression names the rule that broke rather than a rendering symptom.
 */
import {
    applyDone,
    applyStep,
    applyToken,
    bindFrame,
    convergeWithHttp,
    legacyStreamId,
    readReasoningStep,
    readStepExecution,
    readStepSession,
    resolveSession,
    streamBubbleId,
    type TurnBound,
} from '../turnBinding';

type Msg = TurnBound & { reasoningTrace?: unknown[]; model?: string };

const blank = (): Msg[] => [];

describe('turnBinding — session resolution', () => {
    it('treats "new" and empty as "not known yet", not as a session', () => {
        // The app uses the literal "new" as a placeholder. Filtering frames
        // against it rejects every frame from a real conversation.
        expect(resolveSession('new')).toBeNull();
        expect(resolveSession(null)).toBeNull();
        expect(resolveSession(undefined)).toBeNull();
        expect(resolveSession('')).toBeNull();
        expect(resolveSession('s1')).toBe('s1');
    });
});

describe('turnBinding — frame binding', () => {
    it('binds a frame carrying both ids', () => {
        const b = bindFrame({ session_id: 's1', execution_id: 'e1' }, 's1');
        expect(b).toEqual({ execution: 'e1', session: 's1', adoptedSession: false });
    });

    it('rejects a frame from another session', () => {
        expect(bindFrame({ session_id: 'other', execution_id: 'e1' }, 's1')).toBeNull();
    });

    it('adopts the session from the first frame of a new conversation', () => {
        const b = bindFrame({ session_id: 'fresh', execution_id: 'e1' }, null);
        expect(b).toEqual({ execution: 'e1', session: 'fresh', adoptedSession: true });
    });

    it('REFUSES a frame with no execution id instead of guessing a turn', () => {
        // Two turns can overlap on one session, so an id-less frame has no
        // defensible home. It must be reported, not placed.
        expect(bindFrame({ session_id: 's1', delta: 'x' }, 's1')).toBeNull();
        expect(bindFrame({ session_id: 's1', execution_id: '' }, 's1')).toBeNull();
        expect(bindFrame({ session_id: 's1', execution_id: 42 }, 's1')).toBeNull();
        expect(bindFrame(null, 's1')).toBeNull();
    });

    it('binds an execution-only frame when the panel session is unknown', () => {
        expect(bindFrame({ execution_id: 'e1' }, null))
            .toEqual({ execution: 'e1', session: null, adoptedSession: false });
    });
});

describe('turnBinding — token frames', () => {
    it('accumulates every frame of a burst in order', () => {
        let msgs = blank();
        for (let i = 1; i <= 50; i += 1) {
            msgs = applyToken(msgs, 'e1', `<${i}>`);
        }
        expect(msgs).toHaveLength(1);
        const expected = Array.from({ length: 50 }, (_, i) => `<${i + 1}>`).join('');
        expect(msgs[0].content).toBe(expected);
    });

    it('gives two concurrent turns one bubble each', () => {
        let msgs = blank();
        msgs = applyToken(msgs, 'eA', 'A1');
        msgs = applyToken(msgs, 'eB', 'B1');
        msgs = applyToken(msgs, 'eA', 'A2');
        msgs = applyToken(msgs, 'eB', 'B2');
        expect(msgs).toHaveLength(2);
        const byExec = (e: string) => msgs.find(m => m.executionId === e)!.content;
        expect(byExec('eA')).toBe('A1A2');
        expect(byExec('eB')).toBe('B1B2');
    });

    it('uses an execution-keyed id, not a session-keyed one', () => {
        // A session-keyed id is reused across turns, so turn N's reply lands in
        // turn N-1's bubble.
        expect(streamBubbleId('e1')).toBe('stream_e1');
        expect(streamBubbleId('e2')).not.toBe(streamBubbleId('e1'));
    });

    it('a frame arriving after finalization cannot corrupt the answer', () => {
        let msgs = applyToken(blank(), 'e1', 'Hello ');
        msgs = applyToken(msgs, 'e1', 'world');
        msgs = applyDone(msgs, 'e1', 'Hello world');
        expect(msgs[0].streaming).toBe(false);

        const after = applyToken(msgs, 'e1', ' GARBAGE');
        expect(after[0].content).toBe('Hello world');
        expect(after).toHaveLength(1);
    });

    it('records the agent id from the first frame and keeps it', () => {
        let msgs = applyToken(blank(), 'e1', 'a', 'agent-1');
        msgs = applyToken(msgs, 'e1', 'b', 'agent-2');
        expect(msgs[0].agentId).toBe('agent-1');
    });

    it('lets a surface supply its own message fields', () => {
        const msgs = applyToken(blank(), 'e1', 'x', undefined, () => ({
            id: 'ignored', type: 'assistant', content: 'seed:',
        } as Msg));
        expect(msgs[0].content).toBe('seed:x');
        expect(msgs[0].id).toBe('stream_e1');
    });
});

describe('turnBinding — completion frames', () => {
    it('finalizes the named turn and leaves the other alone', () => {
        let msgs = applyToken(blank(), 'eA', 'A text');
        msgs = applyToken(msgs, 'eB', 'B text');
        msgs = applyDone(msgs, 'eA', 'A final');
        expect(msgs.find(m => m.executionId === 'eA')!.content).toBe('A final');
        expect(msgs.find(m => m.executionId === 'eA')!.streaming).toBe(false);
        expect(msgs.find(m => m.executionId === 'eB')!.streaming).toBe(true);
        expect(msgs.find(m => m.executionId === 'eB')!.content).toBe('B text');
    });

    it('a duplicate completion does not produce a second bubble', () => {
        let msgs = applyToken(blank(), 'e1', 'once');
        msgs = applyDone(msgs, 'e1', 'once');
        msgs = applyDone(msgs, 'e1', 'once');
        msgs = applyDone(msgs, 'e1', 'once');
        expect(msgs.filter(m => m.content === 'once')).toHaveLength(1);
    });

    it('an empty completion still closes the turn it names', () => {
        let msgs = applyToken(blank(), 'e1', 'partial');
        msgs = applyDone(msgs, 'e1', '');
        expect(msgs[0].streaming).toBe(false);
        expect(msgs[0].content).toBe('partial');
    });

    it('an empty completion with no bubble does not invent one', () => {
        expect(applyDone(blank(), 'e1', '')).toHaveLength(0);
    });

    it('a done frame with no prior bubble opens the turn with its final text', () => {
        // Tokens can be dropped (a socket that was down when they were sent) and
        // the done frame carries the whole answer.
        const msgs = applyDone(blank(), 'e1', 'complete answer');
        expect(msgs).toHaveLength(1);
        expect(msgs[0].content).toBe('complete answer');
        expect(msgs[0].streaming).toBe(false);
    });
});

describe('turnBinding — reasoning steps', () => {
    const step = (thought: string) => ({ step: 1, thought });

    it('routes a step to the execution it names, not the newest reply', () => {
        let msgs = applyToken(blank(), 'e1', 'first reply');
        msgs = applyDone(msgs, 'e1', 'first reply');

        // Turn 2's reasoning arrives before turn 2 has any text. "Append to the
        // latest assistant message" would file it under turn 1's answer.
        msgs = applyStep(msgs, 'e2', step('planning turn two'));
        msgs = applyToken(msgs, 'e2', 'second reply');

        expect(msgs.find(m => m.executionId === 'e1')!.reasoningTrace).toBeUndefined();
        expect(msgs.find(m => m.executionId === 'e2')!.reasoningTrace).toHaveLength(1);
    });

    it('opens the turn bubble on demand so no step is dropped', () => {
        const msgs = applyStep(blank(), 'e9', step('thinking hard'));
        expect(msgs).toHaveLength(1);
        expect(msgs[0].content).toBe('');
        expect(msgs[0].streaming).toBe(true);
        expect(msgs[0].reasoningTrace).toHaveLength(1);
    });

    it('accumulates several steps in arrival order without duplicating', () => {
        let msgs = applyStep(blank(), 'e7', step('one'));
        msgs = applyStep(msgs, 'e7', step('two'));
        msgs = applyToken(msgs, 'e7', 'answer');
        const bubble = msgs.find(m => m.executionId === 'e7')!;
        expect(bubble.reasoningTrace).toHaveLength(2);
        expect((bubble.reasoningTrace as any[]).map(s => s.thought)).toEqual(['one', 'two']);
        expect(msgs).toHaveLength(1);
    });

    it('an unbound step leaves the transcript untouched for the caller to buffer', () => {
        const msgs = applyStep(blank(), null, step('anonymous'));
        expect(msgs).toHaveLength(0);
    });

    it('keeps each turn trace separate when turns overlap', () => {
        let msgs = applyToken(blank(), 'eA', 'A');
        msgs = applyStep(msgs, 'eB', step('B step'));
        msgs = applyStep(msgs, 'eA', step('A step'));
        expect(msgs.find(m => m.executionId === 'eA')!.reasoningTrace).toHaveLength(1);
        expect(msgs.find(m => m.executionId === 'eB')!.reasoningTrace).toHaveLength(1);
    });
});

describe('turnBinding — HTTP convergence', () => {
    it('replaces the streamed bubble instead of appending a second one', () => {
        let msgs = applyToken(blank(), 'e1', 'provisional');
        const out = convergeWithHttp(msgs, 'e1', { content: 'final answer', model: 'm' });
        expect(out).not.toBeNull();
        expect(out!).toHaveLength(1);
        expect(out![0].content).toBe('final answer');
        expect(out![0].streaming).toBe(false);
        expect(out![0].id).toBe('stream_e1');
    });

    it('returns null when the turn has no streamed bubble, so the caller appends', () => {
        expect(convergeWithHttp(blank(), 'e1', { content: 'x' })).toBeNull();
        expect(convergeWithHttp(blank(), null, { content: 'x' })).toBeNull();
    });

    it('preserves the reasoning the stream already attached', () => {
        let msgs = applyStep(blank(), 'e1', { step: 1, thought: 'why' });
        const out = convergeWithHttp(msgs, 'e1', { content: 'answer' });
        expect(out![0].reasoningTrace).toHaveLength(1);
    });
});

describe('turnBinding — envelope readers', () => {
    it('reads a wrapped step and a flat step alike', () => {
        const wrapped = { type: 'agent_step_update', data: { step: { step: 2, thought: 'a' } } };
        const flat = { type: 'agent_step_update', step: { step: 2, thought: 'a' } };
        expect(readReasoningStep(wrapped)).toEqual({ step: 2, thought: 'a' });
        expect(readReasoningStep(flat)).toEqual({ step: 2, thought: 'a' });
    });

    it('rejects a non-object step rather than appending junk', () => {
        // A bare number once produced `{step: 1}` entries in the drawer.
        expect(readReasoningStep({ data: { step: 1 } })).toBeNull();
        expect(readReasoningStep({ data: {} })).toBeNull();
        expect(readReasoningStep({ data: { step: "text" } })).toBeNull();
        expect(readReasoningStep(null)).toBeNull();
    });

    it('reads the execution and session a step names, from either level', () => {
        expect(readStepExecution({ data: { execution_id: 'e1' } })).toBe('e1');
        expect(readStepExecution({ data: { step: { execution_id: 'e2' } } })).toBe('e2');
        expect(readStepExecution({ data: {} })).toBeNull();
        expect(readStepSession({ data: { session_id: 's1' } })).toBe('s1');
        expect(readStepSession({ data: { step: { session_id: 's2' } } })).toBe('s2');
        expect(readStepSession({ data: {} })).toBeNull();
    });

    it('reads a legacy stream id from either level', () => {
        expect(legacyStreamId({ id: 's' })).toBe('s');
        expect(legacyStreamId({ data: { id: 's' } })).toBe('s');
        expect(legacyStreamId({})).toBeNull();
        expect(legacyStreamId({ id: '' })).toBeNull();
    });
});
