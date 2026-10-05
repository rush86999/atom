'use client';

import { useCallback, useEffect, useRef } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
    applyDone,
    applyStep,
    applyToken,
    bindFrame,
    convergeWithHttp,
    legacyStreamId,
    readAgentId,
    readReasoningStep,
    readStepExecution,
    readStepSession,
    resolveSession,
    type TurnBound,
} from "./turnBinding";

/**
 * The socket half of streamed-turn handling, shared by every surface that POSTs
 * to `/api/chat/message`.
 *
 * WHY A HOOK AND NOT A HELPER. Two things have to be true for turn binding to
 * hold, and neither is a property of the pure functions in `./turnBinding`:
 *
 *   1. EVERY frame must be observed. `useWebSocket` also exposes a
 *      `lastMessage` state slot, and it is ONE slot: a token burst delivers
 *      hundreds of frames inside a few render commits, React coalesces the
 *      updates, and a `[lastMessage]` effect sees only the newest frame. A
 *      listener registered through `onMessage` fires for every frame in arrival
 *      order.
 *   2. NO frame may be handled by a stale render's closures. The listener is
 *      registered once, so every input the handler reads is mirrored into a ref
 *      and refreshed on each render.
 *
 * The hook owns both, plus the bookkeeping that must survive re-renders: which
 * session the panel is showing, which execution its own in-flight POST is
 * waiting on, and how many frames it declined to bind.
 *
 * A surface that wants the streamed text rendered supplies `renderStream`; a
 * surface that only needs the reasoning steps and HITL signals can leave it out.
 */
export type UseTurnStreamOptions<T extends TurnBound> = {
    /** The session this panel is showing. "new"/null means not known yet. */
    sessionId: string | null;
    /** True while this panel has an in-flight turn of its own. */
    isBusy?: boolean;
    /**
     * Apply a streamed frame to the surface's own message state. Omit to
     * receive only reasoning steps, HITL signals and the legacy stream id.
     */
    renderStream?: (action:
        | { kind: "token"; execution: string; delta: string; agentId?: string }
        | { kind: "done"; execution: string; content: string }
    ) => void;
    /** A reasoning step arrived for `execution` (null when it named no turn). */
    onReasoningStep?: (step: Record<string, any>, execution: string | null, agentId?: string) => void;
    /** HITL signals. `phase` is "paused" or "decision". */
    onHitl?: (phase: "paused" | "decision", msg: any) => void;
    /**
     * A background turn continuation landed. This is a chat-orchestrator event
     * with no place in the turn stream proper, but it rides the same account
     * channel, so it is surfaced here rather than leaving each surface to
     * register a second listener (which would double socket registrations and
     * re-introduce per-surface event plumbing).
     */
    onContinuation?: (msg: any) => void;
    /** A `streaming:start` frame opened a legacy stream. */
    onLegacyStreamStart?: (streamId: string) => void;
    /** A `streaming:complete` frame closed the legacy stream THIS panel started. */
    onLegacyStreamDone?: (streamId: string, content: string) => void;
    /** The panel learned its real session id from a frame (new conversation). */
    onSessionAdopted?: (sessionId: string) => void;
    /** The turn this panel's own in-flight POST is waiting on finished. */
    onLocalTurnSettled?: (execution: string) => void;
};

export type TurnStreamApi<T extends TurnBound> = {
    /**
     * The execution this panel's in-flight POST is waiting on, or null.
     *
     * Deliberately NOT cleared when the turn settles: the server's
     * `chat_token_done` routinely lands BEFORE the POST response, and the HTTP
     * body is still the authoritative final text for that same bubble. Keeping
     * the binding is what lets `converge` collapse the two into one message.
     */
    localExecution: () => string | null;
    /** Mark a new local turn as starting (no execution claimed yet). */
    beginLocalTurn: () => void;
    /**
     * Collapse an HTTP response onto the streamed bubble for `execution`.
     * Returns the new array, or null when the turn has no streamed bubble and
     * the caller should append the response as a new message.
     */
    converge: (
        prev: T[],
        payload: Record<string, any>,
    ) => T[] | null;
    /** Frames this panel declined to bind, by kind. Counts only, never content. */
    unboundCounts: () => Record<string, number>;
    /** Convenience wrappers over the shared pure functions. */
    applyTokenFrame: (prev: T[], execution: string, delta: string, agentId?: string) => T[];
    applyDoneFrame: (prev: T[], execution: string, content: string) => T[];
    applyStepFrame: (prev: T[], execution: string | null, step: unknown, agentId?: string) => T[];
    /** True when a turn is streaming, for the surface's own busy indicator. */
    isStreaming: () => boolean;
    /**
     * The socket surface this hook owns. Returned rather than re-fetched so a
     * panel cannot end up with two sockets to the same backend.
     */
    socket: {
        isConnected: boolean;
        streamingContent: Map<string, string>;
        subscribe: (channel: string) => void;
        unsubscribe: (channel: string) => void;
    };
};

export function useTurnStream<T extends TurnBound = TurnBound>(
    options: UseTurnStreamOptions<T>,
): TurnStreamApi<T> {
    const {
        sessionId,
        isBusy = false,
        renderStream,
        onReasoningStep,
        onHitl,
        onContinuation,
        onLegacyStreamStart,
        onLegacyStreamDone,
        onSessionAdopted,
        onLocalTurnSettled,
    } = options;

    // THIS HOOK OWNS THE SOCKET. Every surface that POSTs to
    // /api/chat/message needs both the socket and the turn binding, and a
    // surface that called `useWebSocket` as well would open a SECOND socket to
    // the same backend for the same panel — the exact resource duplication this
    // module exists to remove. So the socket bits a surface needs are returned
    // from here rather than fetched separately.
    const { onMessage, isConnected, streamingContent, subscribe, unsubscribe } = useWebSocket();

    // The session this panel is SHOWING, normalized. null means "not known
    // yet", and a null session never filters a frame out.
    const panelSessionRef = useRef<string | null>(resolveSession(sessionId));
    const localExecutionRef = useRef<string | null>(null);
    const legacyStreamRef = useRef<string | null>(null);
    const unboundRef = useRef<Record<string, number>>({});
    const streamingRef = useRef(false);

    // MIRRORED INPUTS — the listener is registered once, so everything it
    // reads must be read from a ref that a render has just refreshed.
    const isBusyRef = useRef(isBusy);
    const optsRef = useRef(options);
    useEffect(() => {
        isBusyRef.current = isBusy;
        optsRef.current = options;
    });

    useEffect(() => {
        const real = resolveSession(sessionId);
        if (real !== panelSessionRef.current) {
            panelSessionRef.current = real;
            // A different conversation: the previous turn's binding no longer
            // describes anything on screen.
            localExecutionRef.current = null;
            legacyStreamRef.current = null;
        }
    }, [sessionId]);

    const noteUnbound = useCallback((kind: string) => {
        unboundRef.current[kind] = (unboundRef.current[kind] || 0) + 1;
    }, []);

    const bind = useCallback((data: any): string | null => {
        const bound = bindFrame(data, panelSessionRef.current);
        if (!bound) return null;
        if (bound.adoptedSession) {
            panelSessionRef.current = bound.session;
            optsRef.current.onSessionAdopted?.(bound.session as string);
        }
        return bound.execution;
    }, []);

    const settleLocal = useCallback((execution: string) => {
        if (localExecutionRef.current !== execution) return false;
        streamingRef.current = false;
        optsRef.current.onLocalTurnSettled?.(execution);
        return true;
    }, []);

    const handleSocketMessage = useCallback((raw: any) => {
        if (!raw) return;
        let msg: any;
        try {
            msg = typeof raw === "string" ? JSON.parse(raw) : raw;
        } catch {
            return;
        }
        if (!msg || typeof msg.type !== "string") return;
        const o = optsRef.current;

        // ---- streamed reply -------------------------------------------------
        // integrations/chat_orchestrator.py, broadcast to `user:{id}`:
        //   chat_token      {data:{session_id, execution_id, delta}}
        //   chat_token_done {data:{session_id, execution_id, content, elapsed_s}}
        if (msg.type === "chat_token" || msg.type === "chat_token_done") {
            const data = msg.data || {};
            const execution = bind(data);
            if (!execution) {
                // No execution id, or a different session. Counting it is the
                // honest outcome — guessing which turn it belonged to is how a
                // reply ends up under the wrong question.
                noteUnbound(msg.type);
                return;
            }
            // The first frame of a local turn teaches this panel which
            // execution its own in-flight POST is waiting on: the server mints
            // the id before it emits a token, so the POST has not answered yet.
            if (localExecutionRef.current === null && isBusyRef.current) {
                localExecutionRef.current = execution;
            }
            if (msg.type === "chat_token") {
                streamingRef.current = true;
                o.renderStream?.({
                    kind: "token",
                    execution,
                    delta: String(data.delta ?? ""),
                    agentId: readAgentId(msg),
                });
                return;
            }
            o.renderStream?.({
                kind: "done",
                execution,
                content: String(data.content ?? ""),
            });
            streamingRef.current = false;
            settleLocal(execution);
            return;
        }

        // Heartbeat: emitted while a long turn is thinking. No content, no
        // terminal meaning — it must never finalize anything.
        if (msg.type === "chat_heartbeat") return;

        if (msg.type === "chat_continuation") {
            o.onContinuation?.(msg);
            return;
        }

        if (msg.type === "agent_step_update") {
            const step = readReasoningStep(msg);
            if (!step) {
                noteUnbound("agent_step_update:malformed");
                return;
            }
            const panel = panelSessionRef.current;
            const stepSession = readStepSession(msg);
            if (stepSession && panel && stepSession !== panel) {
                noteUnbound("agent_step_update:session");
                return;
            }
            o.onReasoningStep?.(step, readStepExecution(msg), readAgentId(msg));
            return;
        }

        // HITL frames ride the same account-wide channel as everything else, so
        // an approval raised by another conversation must not open a prompt in
        // this one, and another conversation's decision must not dismiss this
        // one's.
        if (msg.type === "hitl_paused" || msg.type === "hitl_decision") {
            const hitlSession = msg.session_id ?? msg.data?.session_id;
            const panel = panelSessionRef.current;
            if (hitlSession && panel && hitlSession !== panel) {
                noteUnbound(`${msg.type}:session`);
                return;
            }
            o.onHitl?.(msg.type === "hitl_paused" ? "paused" : "decision", msg);
            return;
        }

        // ---- legacy streaming:* envelope -------------------------------------
        // Produced by core/agent_execution_service.py and
        // core/atom_agent_endpoints.py (agent TASK streaming). The chat
        // orchestrator does not emit these, but those producers exist and
        // `MessageList` renders `streamingContent` by `currentStreamId`.
        //
        // Kept strictly bound: a completion for a stream this panel did not
        // start — a mismatched id, or a frame whose id was lost — is FOREIGN.
        // It must not end this panel's spinner or append its content. A local
        // turn is released by its own request resolving, or by a timeout, never
        // by somebody else's event.
        if (msg.type === "streaming:start") {
            const id = legacyStreamId(msg);
            if (id) {
                legacyStreamRef.current = id;
                o.onLegacyStreamStart?.(id);
            } else {
                noteUnbound("streaming:start:unidentifiable");
            }
            return;
        }
        if (msg.type === "streaming:complete") {
            const id = legacyStreamId(msg);
            if (!id || id !== legacyStreamRef.current) {
                noteUnbound("streaming:complete:foreign");
                return;
            }
            legacyStreamRef.current = null;
            o.onLegacyStreamDone?.(id, String(msg.content ?? msg.data?.content ?? ""));
        }
    }, [bind, noteUnbound, settleLocal]);

    useEffect(() => onMessage(handleSocketMessage), [onMessage, handleSocketMessage]);

    return {
        localExecution: () => localExecutionRef.current,
        beginLocalTurn: () => { localExecutionRef.current = null; },
        converge: (prev, payload) => convergeWithHttp(prev, localExecutionRef.current, payload),
        unboundCounts: () => ({ ...unboundRef.current }),
        applyTokenFrame: (prev, execution, delta, agentId) =>
            applyToken(prev, execution, delta, agentId),
        applyDoneFrame: (prev, execution, content) => applyDone(prev, execution, content),
        applyStepFrame: (prev, execution, step, agentId) =>
            applyStep(prev, execution, step, agentId),
        isStreaming: () => streamingRef.current,
        socket: { isConnected, streamingContent, subscribe, unsubscribe },
    };
}
