/**
 * Turn binding for streamed chat replies — the shared mechanism.
 *
 * WHY THIS EXISTS. Three separate surfaces POST to `/api/chat/message`
 * (`useChatInterface` on /chat, `components/GlobalChatWidget.tsx`, and
 * `pages/canvas/[id].tsx`). `integrations/chat_orchestrator.py` broadcasts that
 * turn's reply to the `user:{id}` channel as `chat_token` / `chat_token_done`,
 * each stamped with `session_id` and `execution_id`. `core/websockets.py`
 * auto-subscribes every socket to `user:{id}`, so every one of those surfaces
 * RECEIVES every turn on the account — including turns a second tab or an API
 * client is driving.
 *
 * Binding a frame to a reply is therefore not a presentation detail: without it
 * two concurrent turns write into the same bubble, a late frame corrupts an
 * answer the user has already read, and one turn's completion ends another
 * turn's spinner. Every surface needs the same decision, so it lives here once,
 * as pure functions over a message array, and each surface only supplies its
 * own extra event handling.
 *
 * The functions are pure and side-effect free so the rules can be tested
 * directly, without a socket or a React render.
 */

/** The turn-ownership fields a message needs to be addressable by a frame. */
export type TurnBound = {
    id: string;
    type: string;
    content: string;
    /** The server's per-turn execution id. */
    executionId?: string;
    /** True while tokens for this turn are still arriving. */
    streaming?: boolean;
    /** The agent that produced this turn, when the frame carried one. */
    agentId?: string;
};

/**
 * Stable, turn-unique bubble id.
 *
 * Keying on the EXECUTION rather than the session is what lets two turns
 * coexist: a session-keyed id is reused across turns, so turn N's reply lands
 * in turn N-1's bubble.
 */
export const streamBubbleId = (executionId: string): string => `stream_${executionId}`;

/**
 * Normalize a session id for comparison.
 *
 * The app uses the literal string "new" as a placeholder for "no session yet".
 * It is not a session, so a panel in that state must not filter frames against
 * it — otherwise every frame from a real conversation is rejected as foreign.
 */
export const resolveSession = (sessionId: string | null | undefined): string | null =>
    sessionId && sessionId !== "new" ? sessionId : null;

export type BoundFrame = {
    execution: string;
    /** The session the frame belongs to, when it carried one. */
    session: string | null;
    /** True when this frame established the panel's session (new conversation). */
    adoptedSession: boolean;
};

/**
 * Resolve a streamed frame to the turn it belongs to, or reject it.
 *
 * Returns null when the frame CANNOT be bound unambiguously — either it names
 * no execution, or it names a different session than the panel is showing.
 *
 * An id-less frame is deliberately not guessed at. With two turns able to
 * overlap on one session there is no defensible way to choose, so the caller
 * counts it and leaves it out of the transcript rather than writing it into
 * whichever bubble happens to be last.
 */
export const bindFrame = (
    data: any,
    panelSession: string | null,
): BoundFrame | null => {
    const execution = typeof data?.execution_id === "string" && data.execution_id
        ? data.execution_id
        : null;
    if (!execution) return null;
    const session = typeof data?.session_id === "string" && data.session_id
        ? data.session_id
        : null;
    if (session && panelSession && session !== panelSession) return null;
    return {
        execution,
        session,
        adoptedSession: Boolean(session && !panelSession),
    };
};

/** The legacy `streaming:*` stream id, when the frame names one. */
export const legacyStreamId = (msg: any): string | null => {
    const id = msg?.id ?? msg?.data?.id;
    return typeof id === "string" && id ? id : null;
};

/**
 * Read a reasoning step out of an `agent_step_update` frame.
 *
 * Emitters disagree on envelope: `core/agent_routes` broadcasts flat
 * `{step: {...}}` while the chat orchestrator wraps in `{data: {step: {...}}}`.
 * Only a nested-object step is accepted — a bare number or an absent step would
 * otherwise append junk `{step: 1}` entries.
 *
 * Returns null for anything that is not a usable step.
 */
export const readReasoningStep = (msg: any): Record<string, any> | null => {
    const payload = msg?.data ?? msg;
    const step = payload?.step;
    if (!step || typeof step !== "object") return null;
    return step;
};

/** The execution a reasoning step belongs to, or null when it names none. */
export const readStepExecution = (msg: any): string | null => {
    const payload = msg?.data ?? msg;
    const raw = payload?.execution_id ?? payload?.step?.execution_id;
    return typeof raw === "string" && raw ? raw : null;
};

/** The session a reasoning step belongs to, or null when it names none. */
export const readStepSession = (msg: any): string | null => {
    const payload = msg?.data ?? msg;
    const raw = payload?.session_id ?? payload?.step?.session_id;
    return typeof raw === "string" && raw ? raw : null;
};

/** The agent id a frame names, or undefined. */
export const readAgentId = (msg: any): string | undefined => {
    const payload = msg?.data ?? msg;
    const raw = payload?.agent_id ?? msg?.agent_id;
    return typeof raw === "string" && raw ? raw : undefined;
};

/**
 * Append streamed text to a turn's bubble, creating it on the first frame.
 *
 * A turn that has already been finalized is CLOSED: a frame arriving after its
 * `chat_token_done` is a re-fire, not a continuation, and appending it would
 * corrupt text the user has already read.
 */
export function applyToken<T extends TurnBound>(
    prev: T[],
    execution: string,
    delta: string,
    agentId?: string,
    makeMessage?: () => T,
): T[] {
    const id = streamBubbleId(execution);
    const existing = prev.find(m => m.id === id);
    if (existing) {
        if (existing.streaming !== true) return prev;
        return prev.map(m => (m.id === id
            ? { ...m, content: m.content + delta, agentId: m.agentId ?? agentId }
            : m));
    }
    const created: any = makeMessage
        ? makeMessage()
        : {
            id,
            type: "assistant",
            content: "",
            timestamp: new Date(),
        };
    return [...prev, {
        ...created,
        id,
        type: created.type ?? "assistant",
        content: (created.content ?? "") + delta,
        streaming: true,
        executionId: execution,
        ...(agentId ? { agentId } : {}),
    } as T];
}

/**
 * Apply the authoritative final text for a turn and close it.
 *
 * A duplicate `chat_token_done` for an already-finalized turn is ignored —
 * re-running the finalize path produced a second bubble with the same text.
 */
export function applyDone<T extends TurnBound>(
    prev: T[],
    execution: string,
    finalContent: string,
    makeMessage?: () => T,
): T[] {
    const id = streamBubbleId(execution);
    const existing = prev.find(m => m.id === id);
    if (existing) {
        if (existing.streaming !== true) return prev;
        return prev.map(m => (m.id === id
            ? { ...m, content: finalContent || m.content, streaming: false }
            : m));
    }
    if (!finalContent) return prev;
    const created: any = makeMessage
        ? makeMessage()
        : { id, type: "assistant", content: "", timestamp: new Date() };
    return [...prev, {
        ...created,
        id,
        type: created.type ?? "assistant",
        content: finalContent,
        streaming: false,
        executionId: execution,
    } as T];
}

/**
 * Attach a reasoning step to the execution it names, opening the turn's bubble
 * on demand.
 *
 * The rule this replaces was "append to the last message if it is an
 * assistant". That files a NEW turn's first step under the PREVIOUS turn's
 * finished answer whenever that answer is still the newest bubble — which is
 * the state of the list for most of a turn. Binding by execution id lands the
 * trace on the reply it belongs to, and creating the bubble on demand means no
 * step is ever buffered-and-dropped for want of a place to put it.
 *
 * `execution` null means the step named no turn; the caller decides what to do
 * (this returns `prev` unchanged so the caller can buffer it).
 */
export function applyStep<T extends TurnBound>(
    prev: T[],
    execution: string | null,
    step: unknown,
    agentId?: string,
    makeMessage?: () => T,
): T[] {
    if (!execution) return prev;
    const id = streamBubbleId(execution);
    const existing = prev.find(m => m.id === id);
    if (existing) {
        return prev.map(m => (m.id === id
            ? { ...m, reasoningTrace: [...((m as any).reasoningTrace || []), step] }
            : m));
    }
    const created: any = makeMessage
        ? makeMessage()
        : { id, type: "assistant", content: "", timestamp: new Date() };
    return [...prev, {
        ...created,
        id,
        type: created.type ?? "assistant",
        streaming: true,
        executionId: execution,
        ...(agentId ? { agentId } : {}),
        reasoningTrace: [step],
    } as T];
}

/**
 * Converge an HTTP response onto the bubble that streamed this turn.
 *
 * The response is the authoritative FINAL text for a turn that may already have
 * a provisional bubble on screen. Replacing it in place keeps one bubble per
 * turn, in the right position under the right question, with its execution
 * binding and any reasoning the stream already attached. Appending instead is
 * what produced two bubbles carrying the same answer.
 *
 * Returns `null` when the turn has no streamed bubble, meaning the caller
 * should append the response as a new message.
 */
export function convergeWithHttp<T extends TurnBound>(
    prev: T[],
    execution: string | null,
    payload: Record<string, any>,
): T[] | null {
    if (!execution) return null;
    const id = streamBubbleId(execution);
    if (!prev.some(m => m.id === id)) return null;
    return prev.map(m => (m.id === id
        ? {
            ...m,
            ...payload,
            streaming: false,
        }
        : m));
}
