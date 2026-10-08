'use client';

import { useState, useRef, useEffect, useCallback } from "react";
import { ChatMessageData, ReasoningStep, reasoningTextToStep } from "@/components/GlobalChat/ChatMessage";
import { useToast } from "@/components/ui/use-toast";
import { useFileUpload } from "@/hooks/useFileUpload";
import { getCurrentUserId } from "@/lib/identity";
import { getOpenCanvasChatContext } from "@/hooks/useCanvasStateRegistration";
import { chatTurnTouchedCanvas, syncCanvasFromStore } from "@/lib/canvasSync";
import { useTurnStream } from "@/hooks/chat/useTurnStream";

interface UseChatInterfaceProps {
    sessionId: string | null;
    initialAgentId?: string | null;
    /** Goal run this chat was opened from (?goal_run_id=…) — carried into
     * the request context so /teach scopes to the goal being worked. */
    initialGoalRunId?: string | null;
    onSessionCreated?: (sessionId: string) => void;
}

/**
 * A chat message plus the turn-ownership fields streamed frames need in order
 * to reach the right reply.
 *
 * It EXTENDS ChatMessageData rather than replacing it, so
 * components/chat/MessageList.tsx and everything else that renders
 * `messages` keeps accepting the array unchanged — no component edit is needed
 * to make the main chat stream.
 */
type TurnBoundMessage = ChatMessageData & {
    /** The server's per-turn execution id. Frames are routed by this, so two
     * overlapping turns never share a bubble. */
    executionId?: string;
    /** True while tokens for this turn are still arriving. */
    streaming?: boolean;
    /** The agent that produced this turn, when the frame carried one. */
    agentId?: string;
};

/** Stable, turn-unique bubble id. Keying on the EXECUTION (not the session)
 * is what lets two turns coexist: a session-keyed id is reused across turns,
 * so turn N's reply overwrites turn N-1's bubble. */
const streamBubbleId = (executionId: string) => `stream_${executionId}`;

/** The legacy `streaming:*` stream, when the frame names one. The main chat's
 * own orchestrator does NOT emit these (it emits chat_token*), but
 * `core/agent_execution_service.py` and `core/atom_agent_endpoints.py` do, and
 * `MessageList` renders `streamingContent` by `currentStreamId`. Kept working
 * for those producers; never allowed to finish a turn it does not own. */
const legacyStreamId = (msg: any): string | null => {
    const id = msg?.id ?? msg?.data?.id;
    return typeof id === "string" && id ? id : null;
};

export const useChatInterface = ({ sessionId, initialAgentId, initialGoalRunId, onSessionCreated }: UseChatInterfaceProps) => {
    const [input, setInput] = useState("");
    // Pending user-submitted images (data URLs) for the next send — routed
    // to vision-capable models via the chat request images field.
    const [pendingImages, setPendingImages] = useState<string[]>([]);
    const [isProcessing, setIsProcessing] = useState(false);
    const [statusMessage, setStatusMessage] = useState("Agent is thinking...");
    // BACKGROUND-RUN INDICATOR (2026-09-29): a turn that forked a canvas
    // edit to the background ("still running in the background") binds a
    // pending chip to THIS run — spinner until the terminal
    // `chat_continuation` WS event, then honest still-running wording
    // after a stale window (never an eternal spinner, never fake
    // completion).
    const [backgroundRun, setBackgroundRun] = useState<{
        continuationId?: string;
        executionId?: string;
        since: number;
    } | null>(null);
    const [messages, setMessages] = useState<TurnBoundMessage[]>([]);
    const [pendingApproval, setPendingApproval] = useState<{ action_id: string; tool: string; reason: string } | null>(null);
    const [currentStreamId, setCurrentStreamId] = useState<string | null>(null);
    const [sessionTitle, setSessionTitle] = useState("Current Session");
    // The hire this chat is scoped to (from ?agent_id=…). Surfaced in the UI
    // so the user can always see WHO they're talking to.
    const [chatAgent, setChatAgent] = useState<{ name: string; category: string | null; status: string | null } | null>(null);
    const [isEditingTitle, setIsEditingTitle] = useState(false);
    const [tempTitle, setTempTitle] = useState("");
    const messagesEndRef = useRef<HTMLDivElement>(null);
    // AbortController for cancelling the in-flight POST (handleStop).
    const abortControllerRef = useRef<AbortController | null>(null);
    // Safety-net timeout so isProcessing never gets permanently stuck if
    // streaming:complete is missed or the id mismatches.
    const processingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    // Dedupe guard: set true when the REST path appends the assistant message,
    // so the WebSocket streaming:complete path doesn't append a duplicate.
    const _restFulfilledRef = useRef(false);
    // Reasoning steps that arrive over WS BEFORE this turn's bubble exists. The
    // old handler silently DROPPED them (steps only attach to a trailing
    // assistant message, and while the agent is generating the last message is
    // the user's) — so the "Reasoning Process" drawer never showed anything on
    // the main chat page.
    const _pendingStepsRef = useRef<ReasoningStep[]>([]);

    // Turn ownership (which execution this panel's POST is waiting on, which
    // session it is showing, how many frames it declined to bind) lives in
    // useTurnStream below — the shared mechanism every surface that POSTs to
    // /api/chat/message uses. See hooks/chat/turnBinding.ts for why the rules
    // are general rather than per-surface.

    const { toast } = useToast();
    const { uploadFile, isUploading } = useFileUpload();

    const [activeAttachments, setActiveAttachments] = useState<any[]>([]);
    const [isVoiceModeOpen, setIsVoiceModeOpen] = useState(false);
    // P1.1: structured LLM-provider error for actionable recovery.
    // Null when there is no provider error to show.
    const [providerError, setProviderError] = useState<{ message: string; recovery_url: string; error_code: string } | null>(null);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, []);

    const loadSessionHistory = useCallback(async (sid: string) => {
        try {
            setIsProcessing(true);
            setStatusMessage("Loading history...");
            const { apiClient } = await import('../../lib/api-client');
            let response: any;
            try {
                response = await apiClient.get(`/api/chat/history/${sid}?user_id=${getCurrentUserId()}`, {
                    timeout: 8000,
                    // @ts-ignore
                    retry: false
                });
            } catch (error: any) {
                // The backend tolerates most history failures (200 + empty)
                // so this catch only runs on transport/403/5xx.
                console.error("Failed to load history:", error);
                if (error?.response?.status === 403) {
                    // 403 = this session id belongs to another account (a stale id
                    // persisted in localStorage from an earlier login/test run).
                    // Drop the stale pointer and switch to a fresh session so the
                    // error doesn't recur on every load.
                    if (typeof window !== "undefined") {
                        window.localStorage.removeItem("atom_chat_session_id");
                    }
                    onSessionCreated?.("new");
                }
                toast({
                    title: "Could not load history",
                    description: "Failed to load conversation history. Starting fresh.",
                    variant: "warning",
                });
                return;
            }

            if (response && response.status === 200) {
                const data = response.data || {};
                if (data.messages && Array.isArray(data.messages)) {
                    const chatMessages: ChatMessageData[] = [];

                    data.messages.forEach((historyItem: any, idx: number) => {
                        // Prefer the durable backend message id (needed by
                        // fork-from-here); fall back to a positional id for
                        // legacy payloads that don't carry one.
                        if (historyItem.message) {
                            chatMessages.push({
                                id: historyItem.id || `msg_user_${idx}`,
                                type: "user",
                                content: historyItem.message,
                                timestamp: new Date(historyItem.timestamp || Date.now()),
                                actions: [],
                            });
                        }

                        const assistantContent = historyItem.response?.message || historyItem.response;
                        const assistantActions = historyItem.response?.suggested_actions || historyItem.response?.metadata?.actions || [];

                        if (assistantContent && typeof assistantContent === 'string') {
                            const historyReasoningStep = reasoningTextToStep(historyItem.reasoning);
                            chatMessages.push({
                                id: historyItem.id || `msg_assistant_${idx}`,
                                type: "assistant",
                                content: assistantContent,
                                timestamp: new Date(historyItem.timestamp || Date.now()),
                                actions: assistantActions,
                                reasoning: historyItem.reasoning || undefined,
                                workbookResult: historyItem.workbook_result || undefined,
                                ...(historyReasoningStep ? { reasoningTrace: [historyReasoningStep] } : {}),
                            });
                        } else if (assistantContent && typeof assistantContent === 'object' && assistantContent.message) {
                            const historyReasoningStep = reasoningTextToStep(historyItem.reasoning);
                            chatMessages.push({
                                id: historyItem.id || `msg_assistant_${idx}`,
                                type: "assistant",
                                content: assistantContent.message,
                                timestamp: new Date(historyItem.timestamp || Date.now()),
                                actions: assistantContent.suggested_actions || [],
                                reasoning: historyItem.reasoning || undefined,
                                ...(historyReasoningStep ? { reasoningTrace: [historyReasoningStep] } : {}),
                            });
                        }
                    });

                    // MERGE, don't replace: history is fetched asynchronously —
                    // if the user already sent a message while it was loading,
                    // that optimistic message (ids are Date.now() strings,
                    // never `msg_*_${idx}`) must survive the history landing,
                    // otherwise sends during history load silently vanish.
                    const historyIds = new Set(chatMessages.map((m) => m.id));
                    setMessages((prev) => [
                        ...chatMessages,
                        ...prev.filter((m) => !historyIds.has(m.id)),
                    ]);
                }
            }
        } catch (error: any) {
            console.error("Failed to load history:", error);
            if (error?.response?.status === 403) {
                // 403 = this session id belongs to another account (a stale id
                // persisted in localStorage from an earlier login/test run).
                // Drop the stale pointer and switch to a fresh session so the
                // error doesn't recur on every load.
                if (typeof window !== "undefined") {
                    window.localStorage.removeItem("atom_chat_session_id");
                }
                onSessionCreated?.("new");
            }
            toast({
                title: "Could not load history",
                description: "Failed to load conversation history. Starting fresh.",
                variant: "warning",
            });
        } finally {
            setIsProcessing(false);
        }
    }, [onSessionCreated, toast]);

    const handleTitleSave = async () => {
        if (!sessionId || !tempTitle.trim()) {
            setIsEditingTitle(false);
            return;
        }

        try {
            const { apiClient } = await import('../../lib/api-client');
            const response = await apiClient.patch(`/api/chat/sessions/${sessionId}`, {
                title: tempTitle,
                user_id: getCurrentUserId(),
            }) as any;
            const data = response.data || response;
            if (data.success) {
                setSessionTitle(tempTitle);
                toast({ title: "Renamed", description: "Session renamed successfully." });
            } else {
                toast({ variant: "error", title: "Error", description: "Failed to rename session." });
            }
        } catch (error) {
            console.error("Rename failed", error);
            toast({ variant: "error", title: "Error", description: "Failed to rename session." });
        } finally {
            setIsEditingTitle(false);
        }
    };

    const handleSend = async (overrideText?: string, images?: string[]): Promise<boolean> => {
        // overrideText is used by handleRegenerate to re-send the original
        // prompt (input is empty at that point). Without it, regenerate would
        // silently delete the exchange and produce nothing.
        const currentInput = (overrideText ?? input).trim();
        if (!currentInput && !(images && images.length)) return false;
        // An image with no text still needs a message body for the model.
        const effectiveInput = currentInput || (images && images.length ? "What do you see in this image?" : "");

        // Clear any prior provider-error banner before attempting another send.
        setProviderError(null);

        const userMsg: ChatMessageData = {
            id: Date.now().toString(),
            type: "user",
            content: effectiveInput,
            timestamp: new Date(),
            images,
        } as any;

        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setPendingImages([]);
        setIsProcessing(true);
        setStatusMessage("Agent is thinking...");
        _restFulfilledRef.current = false;
        // This turn's steps belong to THIS turn's reply — drop any stragglers
        // buffered from a turn that never resolved.
        _pendingStepsRef.current = [];
        // New local turn: no execution is claimed yet. The first
        // session-matching chat_token that arrives while this POST is in flight
        // adopts the role, because the server mints the execution id before it
        // emits a token.
        turn.beginLocalTurn();

        try {
            const { apiClient } = await import('../../lib/api-client');
            // Create an AbortController so handleStop can cancel this request.
            abortControllerRef.current = new AbortController();
            // Transport idempotency key for THIS submitted turn: axios-level
            // network retries resend the identical body (same key → the
            // server replays instead of re-executing); a user-composed
            // retry is a new turn and mints a new key below.
            const requestId = (typeof crypto !== "undefined" && crypto.randomUUID
                ? crypto.randomUUID()
                : `req_${Date.now()}_${Math.random().toString(36).slice(2)}`);
            // Safety-net: reset isProcessing after 120s if no response/stream-complete.
            if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
            processingTimeoutRef.current = setTimeout(() => {
                setIsProcessing(false);
            }, 120000);

            const response = await apiClient.post("/api/chat/message", {
                message: effectiveInput,
                images: images && images.length ? images.slice(0, 2) : undefined,
                session_id: sessionId,
                user_id: getCurrentUserId(),
                request_id: requestId,
                context: {
                    current_page: "/chat",
                    agent_id: initialAgentId,
                    // Opened from a goal run: carry it so a /teach in this chat
                    // scopes the lesson to the goal the agent is working
                    // (deterministic — no inference needed).
                    ...(initialGoalRunId ? { goal_run_id: initialGoalRunId } : {}),
                    // An open canvas (any canvas app that registers into the
                    // window.atom.canvas registry) rides along so the chat
                    // can co-edit it — same contract the /canvas/{id} panel
                    // sends. The backend plans against the durable audit
                    // trail, so this is an identifier + best-effort snapshot.
                    ...(getOpenCanvasChatContext() || {}),
                    conversation_history: messages.slice(-5).map(m => ({
                        role: m.type === "user" ? "user" : "assistant",
                        content: m.content
                    })),
                    attachments: activeAttachments
                }
            }, {
                signal: abortControllerRef.current.signal,
                timeout: 120000,
                // @ts-ignore
                retry: false
            }) as any;

            setActiveAttachments([]);
            const data = response.data;

            // P1.1: detect the actionable "no LLM provider" structured error and
            // surface it as a recovery banner rather than an opaque error toast.
            if (data && data.error_code === "no_llm_provider") {
                setProviderError({
                    message: data.message || "You need an AI provider to do this.",
                    recovery_url: data.recovery_url || "/settings/ai",
                    error_code: data.error_code,
                });
                // The backend still created/persisted a session for this turn
                // (the user message is stored before the LLM call is attempted),
                // so propagate the real session id — otherwise a reload loses
                // the conversation entirely.
                if (data.session_id && data.session_id !== "unknown") {
                    onSessionCreated?.(data.session_id);
                }
                setMessages(prev => [...prev, {
                    id: "no-provider",
                    type: "system",
                    content: data.message || "No AI provider configured.",
                    timestamp: new Date(),
                }]);
                return false;
            }

            // Budget-exceeded: surface as a distinct error-type message so the
            // UI renders a budget-halted alert (not a normal assistant bubble).
            // Mirrors the no_llm_provider structured-error pattern above.
            if (data && data.error_code === "budget_exceeded") {
                if (processingTimeoutRef.current) {
                    clearTimeout(processingTimeoutRef.current);
                    processingTimeoutRef.current = null;
                }
                if (data.session_id && data.session_id !== "unknown") {
                    onSessionCreated?.(data.session_id);
                }
                setMessages(prev => [...prev, {
                    id: "budget-exceeded",
                    type: "error",
                    content: data.message || "Budget limit reached — execution halted.",
                    timestamp: new Date(),
                }]);
                return false;
            }

            // Turn-budget exhausted: the backend bounded this turn's reply
            // generation and answered with a structured failure instead of
            // letting the request run past this client's 120s timeout. Render
            // it as a retryable error bubble — do NOT fall through to the
            // success path, which would show an empty reply.
            if (data && data.error_code === "turn_budget_exceeded") {
                if (processingTimeoutRef.current) {
                    clearTimeout(processingTimeoutRef.current);
                    processingTimeoutRef.current = null;
                }
                if (data.session_id && data.session_id !== "unknown") {
                    onSessionCreated?.(data.session_id);
                }
                setMessages(prev => [...prev, {
                    id: `turn-budget-${Date.now()}`,
                    type: "error",
                    content: data.message
                        || "This turn ran past its time budget before a reply could be generated. Please try again.",
                    timestamp: new Date(),
                }]);
                return false;
            }

            // SHARED STRUCTURED-FAILURE HANDLING (2026-10-08 owner
            // priority 3): ANY backend response with success=false and a
            // message reaches the user as the backend's own truthful
            // text — never the generic data.error branch below, which
            // replaced messages like the empty-stream reply ("the model
            // returned no content…") with an opaque "Failed to process
            // request". Preserves the failure classification
            // (error_code), adopts the returned conversation identity so
            // a reload keeps the turn, keeps the composer usable (this
            // branch returns without touching sending state), and keys
            // the bubble by request/message identity instead of a fixed
            // "error" id (fixed ids collide across turns and break
            // convergence with persisted history).
            if (data && data.success === false && data.message) {
                if (processingTimeoutRef.current) {
                    clearTimeout(processingTimeoutRef.current);
                    processingTimeoutRef.current = null;
                }
                if (data.session_id && data.session_id !== "unknown") {
                    onSessionCreated?.(data.session_id);
                }
                setMessages(prev => [...prev, {
                    id: `failure-${data.error_code || "unknown"}-${
                        data.execution_id || Date.now()}`,
                    type: "error",
                    content: data.message,
                    errorCode: data.error_code || undefined,
                    timestamp: new Date(),
                }]);
                return false;
            }

            // Clear the safety-net timeout on any successful resolution.
            if (processingTimeoutRef.current) {
                clearTimeout(processingTimeoutRef.current);
                processingTimeoutRef.current = null;
            }

            if (data.success && data.message) {
                if (data.session_id && data.session_id !== sessionId && data.session_id !== "new") {
                    onSessionCreated?.(data.session_id);
                }

                // A forked background run: bind the pending indicator to
                // this run's ids (resolved by the chat_continuation
                // handler below).
                const _bgCanvasEdit = (data as any)?.data?.canvas_edit
                    || (data as any)?.metadata?.canvas_edit;
                if (_bgCanvasEdit?.background_started) {
                    setBackgroundRun({
                        continuationId: _bgCanvasEdit.continuation_id || undefined,
                        executionId: _bgCanvasEdit.execution_id || undefined,
                        since: Date.now(),
                    });
                }

                // Attach this turn's buffered WS steps, and fall back to the
                // REST payload's chain-of-thought when no WS step carried it
                // (stale socket / history-only clients still get the drawer).
                const bufferedSteps = _pendingStepsRef.current;
                _pendingStepsRef.current = [];
                const restReasoningStep = reasoningTextToStep(data.reasoning);
                const reasoningTrace: ReasoningStep[] = [
                    ...bufferedSteps,
                    ...(restReasoningStep && !bufferedSteps.some(
                        s => (s.thought || "").trim() === (data.reasoning || "").trim()
                    ) ? [restReasoningStep] : []),
                ];
                const agentMsg: ChatMessageData = {
                    id: (Date.now() + 1).toString(),
                    type: "assistant",
                    content: data.message,
                    timestamp: new Date(),
                    actions: data.metadata?.actions || data.suggested_actions || [],
                    model: data.model,
                    provider: data.provider,
                    memoryContext: data.memory_context || undefined,
                    workbookResult: (data as any)?.data?.workbook_result
                        || (data as any)?.metadata?.workbook_result
                        || undefined,
                    reasoning: data.reasoning || undefined,
                    // Train-from-chat: the backend attaches `teaching` to the
                    // turn (a /teach confirmation, or a detected directive
                    // awaiting one-click confirmation). Rendered inline by
                    // ChatMessage so both chat surfaces stay identical.
                    ...(data.metadata?.teaching
                        ? { teaching: data.metadata.teaching }
                        : {}),
                    ...(reasoningTrace.length ? { reasoningTrace } : {}),
                };
                // CONVERGE WITH THE STREAM. If this turn already streamed a
                // bubble, the HTTP response is the authoritative FINAL text for
                // that same bubble — replace it in place (keeping its id, its
                // position under the right question, its execution binding and
                // any reasoning the stream already attached). Appending here is
                // what produced two bubbles with the same answer.
                const converged = turn.converge(messagesRef.current, {
                    content: data.message,
                    actions: agentMsg.actions,
                    model: agentMsg.model,
                    provider: agentMsg.provider,
                    memoryContext: agentMsg.memoryContext,
                    reasoning: agentMsg.reasoning,
                    ...(agentMsg.teaching ? { teaching: agentMsg.teaching } : {}),
                    ...(reasoningTrace.length ? { reasoningTrace } : {}),
                });
                if (converged) {
                    setMessages(converged);
                    _restFulfilledRef.current = true;
                    if (chatTurnTouchedCanvas(data)) {
                        void syncCanvasFromStore(
                            data.metadata?.canvas_edit?.canvas_id
                            || data.metadata?.canvas_action?.canvas_id
                            || undefined,
                        );
                    }
                    return true;
                }
                setMessages(prev => [...prev, agentMsg]);
                // Mark this generation as REST-fulfilled so the WebSocket
                // streaming:complete path doesn't append a duplicate.
                _restFulfilledRef.current = true;
                // The agent just co-edited (or acted on) the open canvas. The
                // WS canvas:update broadcast is the primary live carrier, but
                // a stale socket can silently drop it — re-broadcast the
                // audit-trail content locally so every mounted canvas host
                // converges (lib/canvasSync; the /canvas/{id} page does the
                // same via its own refetch).
                if (chatTurnTouchedCanvas(data)) {
                    void syncCanvasFromStore(
                        data.metadata?.canvas_edit?.canvas_id
                        || data.metadata?.canvas_action?.canvas_id
                        || undefined,
                    );
                }
                return true;
            } else {
                throw new Error(data.error || "Failed to process request");
            }
        } catch (error) {
            console.error("Chat error:", error);
            setMessages(prev => [...prev, {
                id: "error",
                type: "system",
                content: "⚠️ I encountered an error. Please check your connection and try again.",
                timestamp: new Date(),
            }]);
            return false;
        } finally {
            // Clear the safety-net timeout on EVERY exit path, not just
            // success. Without this, an error/early-return (no_llm_provider,
            // budget_exceeded, network failure) left the 30s timer armed, so
            // it later fired setIsProcessing(false) during an unrelated future
            // interaction (BUG-014).
            if (processingTimeoutRef.current) {
                clearTimeout(processingTimeoutRef.current);
                processingTimeoutRef.current = null;
            }
            setIsProcessing(false);
        }
    };

    const handleFeedback = async (messageId: string, type: 'thumbs_up' | 'thumbs_down', comment?: string) => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            // Look up the message so feedback carries which model produced it —
            // this closes the loop for learning-based routing.
            const ratedMessage = messages.find(m => m.id === messageId);
            const response = await apiClient.post("/api/chat/feedback", {
                message_id: messageId,
                feedback: type,
                comment: comment,
                model: ratedMessage?.model,
                provider: ratedMessage?.provider,
                // The thinking that produced the rated reply — training signal
                // (backend also falls back to persisted message metadata).
                reasoning: ratedMessage?.reasoning
                    || (ratedMessage?.reasoningTrace || [])
                        .map(s => s.thought || "").filter(Boolean).join("\n\n")
                    || undefined,
            });

            const data = (response as any).data || response;

            if (data.success || response.status === 200) {
                toast({
                    title: "Feedback Submitted",
                    description: "Thank you for your feedback!",
                });
            } else {
                throw new Error(data.error || "Failed to submit feedback");
            }
        } catch (error) {
            console.error("Feedback error:", error);
            toast({
                title: "Error",
                description: "Failed to submit feedback. Please try again.",
                variant: "error"
            });
        }
    };

    const handleRegenerate = async (messageId: string) => {
        // Find the assistant message being regenerated and the user message
        // that preceded it, so we can re-send the original prompt.
        const idx = messages.findIndex(m => m.id === messageId);
        if (idx < 0) return;
        // Walk back to the previous user message.
        let userIdx = idx - 1;
        while (userIdx >= 0 && messages[userIdx].type !== 'user') userIdx -= 1;
        if (userIdx < 0) return;
        const originalPrompt = messages[userIdx].content;

        // Record an implicit negative signal for the response being regenerated
        // (the user asked for a different answer = the previous one wasn't good).
        try {
            const { apiClient } = await import('../../lib/api-client');
            const ratedMessage = messages[idx];
            await apiClient.post("/api/chat/feedback", {
                message_id: messageId,
                feedback: "thumbs_down",
                comment: "regenerated",
                model: ratedMessage?.model,
                provider: ratedMessage?.provider,
            });
        } catch {
            // Non-fatal — the regenerate still proceeds.
        }

        // Remove everything from the user message onward (the old exchange)
        // and re-send the original prompt to get a fresh response. Save the
        // original messages so we can restore them if the regenerate fails.
        const originalMessages = [...messages];
        setMessages(prev => prev.slice(0, userIdx));
        // handleSend never throws (it swallows errors internally), so the
        // boolean return is the failure signal: restore the original exchange
        // so the user doesn't lose their conversation.
        const ok = await handleSend(originalPrompt);
        if (!ok) {
            setMessages(originalMessages);
            toast({
                title: "Regenerate failed",
                description: "Could not generate a new response. Your original exchange is preserved.",
                variant: "error",
            });
        }
    };

    const handleStop = async () => {
        // Abort the in-flight POST so the backend connection is dropped and
        // a late response doesn't append after the "stopped" message.
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        if (processingTimeoutRef.current) {
            clearTimeout(processingTimeoutRef.current);
            processingTimeoutRef.current = null;
        }
        // Best-effort: tell the backend to cancel the in-flight processing
        // so it stops consuming tokens / executing tools. Non-blocking — the
        // frontend proceeds regardless.
        if (sessionId) {
            import('../../lib/api-client').then(({ apiClient }) => {
                apiClient.post(`/api/chat/cancel/${sessionId}`).catch(() => {});
            });
        }
        setIsProcessing(false);
        const stopMsg: ChatMessageData = {
            id: Date.now().toString(),
            type: "system",
            content: "🚫 Agent execution stopped by user.",
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, stopMsg]);
    };

    // Resolve the hire this chat is scoped to (?agent_id=…) for the identity
    // bar — independent of the welcome effect so restored sessions show it too.
    useEffect(() => {
        if (!initialAgentId) {
            setChatAgent(null);
            return;
        }
        let cancelled = false;
        import('../../lib/api-client').then(({ apiClient }) => {
            apiClient.get(`/api/agents/${initialAgentId}`, {
                timeout: 5000,
                // @ts-ignore
                retry: false
            })
                .then((resp: any) => {
                    if (cancelled) return;
                    const a = resp?.data?.data ?? resp?.data;
                    const name = a?.display_name || a?.name;
                    if (!name) return;
                    setChatAgent({ name, category: a?.category ?? null, status: a?.status ?? null });
                })
                .catch(() => { /* identity bar stays hidden */ });
        });
        return () => { cancelled = true; };
    }, [initialAgentId]);

    useEffect(() => {
        if (sessionId && sessionId !== "new") {
            // BUG-106: Clear messages immediately so the previous session's
            // conversation doesn't flash during the async history fetch.
            setMessages([]);
            setIsProcessing(false);
            // A background run bound to the OLD session must not leak into
            // this one.
            setBackgroundRun(null);
            loadSessionHistory(sessionId);
            import('../../lib/api-client').then(({ apiClient }) => {
                apiClient.get(`/api/chat/sessions/${sessionId}?user_id=${getCurrentUserId()}`, {
                    timeout: 5000,
                    // @ts-ignore
                    retry: false
                })
                    .then((resp: any) => {
                        const data = resp.data || resp;
                        if (data.title) setSessionTitle(data.title);
                    }).catch((e: any) => console.log("Bg fetch title error", e));
            });
        } else {
            setMessages([
                {
                    id: "welcome",
                    type: "assistant",
                    content: "Hello! I'm your Atom Assistant. How can I help you today?",
                    timestamp: new Date(),
                }
            ]);
            setSessionTitle("New Chat");
            // Chatting WITH a hire: greet as that employee, not the generic
            // platform assistant. Falls back to the generic welcome if the
            // agent can't be fetched.
            if (initialAgentId) {
                let cancelled = false;
                import('../../lib/api-client').then(({ apiClient }) => {
                    apiClient.get(`/api/agents/${initialAgentId}`, {
                        timeout: 5000,
                        // @ts-ignore
                        retry: false
                    })
                        .then((resp: any) => {
                            if (cancelled) return;
                            const a = resp?.data?.data ?? resp?.data;
                            const name = a?.display_name || a?.name;
                            if (!name) return;
                            const role = a?.category ? `${a.category} ` : "";
                            setMessages([
                                {
                                    id: "welcome",
                                    type: "assistant",
                                    content: `Hello! I'm ${name}, your ${role}hire. How can I help you today?`,
                                    timestamp: new Date(),
                                }
                            ]);
                        })
                        .catch(() => { /* keep generic welcome */ });
                });
                return () => { cancelled = true; };
            }
        }
    }, [sessionId, initialAgentId, loadSessionHistory]);

    // Synchronous view of the transcript. A `setMessages` updater body runs
    // LATER, when React processes the update, so anything that has to branch on
    // the current contents (rather than merely transform them) has to read it
    // from here — otherwise it reads `false` for a bubble that is about to be
    // found.
    const messagesRef = useRef<TurnBoundMessage[]>(messages);
    const loadSessionHistoryRef = useRef<((sid: string) => Promise<void>) | null>(null);
    const toastRef = useRef(toast);
    const sessionIdRef = useRef(sessionId);
    const _pendingStepsRef2 = _pendingStepsRef;
    useEffect(() => {
        messagesRef.current = messages;
        loadSessionHistoryRef.current = loadSessionHistory;
        toastRef.current = toast;
        sessionIdRef.current = sessionId;
    });

    // THE SHARED TURN STREAM. Lossless intake (one `onMessage` registration,
    // every frame observed, inputs mirrored into refs so no frame is handled by
    // a stale render) plus the general binding rules from ./turnBinding.
    const turn = useTurnStream<TurnBoundMessage>({
        sessionId,
        isBusy: isProcessing,
        onSessionAdopted: (sid) => { onSessionCreated?.(sid); },
        onContinuation: (msg) => {
            // A background turn continuation landed (an edit finished after the
            // interactive turn ended): refresh history so the late assistant
            // message and updated canvas state appear, and tell the user.
            if (msg.session_id !== sessionIdRef.current) return;
            // Resolve the pending background-run indicator (by id when the
            // reply carried one; the terminal event is session-scoped).
            setBackgroundRun(null);
            const summary: string = msg.summary || "A background task finished.";
            const status: string = msg.status || "";
            const titles: Record<string, string> = {
                applied: "Background update finished",
                awaiting_approval: "Draft ready for your review",
                already_applied: "Update had already landed",
                conflict: "Canvas changed — update held back",
                cancelled: "Background update cancelled",
                failed: "Background update could not finish",
            };
            const good = status === "applied" || status === "already_applied";
            toastRef.current({
                title: titles[status] || "Background update finished",
                description: summary.slice(0, 160),
                variant: good ? "default" : "warning",
            });
            void loadSessionHistoryRef.current?.(msg.session_id);
        },
        onLocalTurnSettled: () => {
            setIsProcessing(false);
            if (processingTimeoutRef.current) {
                clearTimeout(processingTimeoutRef.current);
                processingTimeoutRef.current = null;
            }
        },
        renderStream: (action) => {
            if (action.kind === "token") {
                setMessages(prev => turn.applyTokenFrame(prev, action.execution, action.delta, action.agentId));
                return;
            }
            setMessages(prev => turn.applyDoneFrame(prev, action.execution, action.content));
        },
        onReasoningStep: (rawStep, execution, agentId) => {
            const step: ReasoningStep = {
                step: rawStep.step || 1,
                thought: rawStep.thought,
                action: rawStep.action,
                observation: rawStep.observation ?? rawStep.output,
                final_answer: rawStep.final_answer,
            };
            if (rawStep.action) {
                setStatusMessage(`Executing ${rawStep.action.tool ?? rawStep.action}...`);
            } else if (rawStep.thought) {
                setStatusMessage("Thinking...");
            }
            if (!execution) {
                // The step named no turn, so there is nowhere unambiguous to
                // put it. Buffer it for this panel's own HTTP reply, which is
                // the one place it can be placed without guessing.
                _pendingStepsRef2.current = [..._pendingStepsRef2.current, step];
                return;
            }
            setMessages(prev => turn.applyStepFrame(prev, execution, step, agentId));
        },
        onHitl: (phase, msg) => {
            if (phase === "paused") {
                setPendingApproval({ action_id: msg.action_id, tool: msg.tool, reason: msg.reason });
                setStatusMessage("Waiting for approval...");
                return;
            }
            setPendingApproval(null);
            setStatusMessage("Resuming execution...");
        },
        onLegacyStreamStart: (id) => { setCurrentStreamId(id); },
        onLegacyStreamDone: (id, content) => {
            // Only ever called for the stream THIS panel started (the shared
            // layer drops foreign and unidentifiable completions), so it is
            // safe to resolve the turn here.
            if (!_restFulfilledRef.current) {
                const wsBuffered = _pendingStepsRef.current;
                _pendingStepsRef.current = [];
                setMessages(prev => [...prev, {
                    id,
                    type: "assistant" as const,
                    content,
                    timestamp: new Date(),
                    actions: [],
                    ...(wsBuffered.length ? { reasoningTrace: wsBuffered } : {}),
                }]);
            }
            setCurrentStreamId(null);
            setIsProcessing(false);
            if (processingTimeoutRef.current) {
                clearTimeout(processingTimeoutRef.current);
                processingTimeoutRef.current = null;
            }
        },
    });

    // The socket this surface uses is the one useTurnStream opened. Taking it
    // from there is what keeps /chat at one socket per panel.
    const { isConnected, streamingContent, subscribe } = turn.socket;

    useEffect(() => {
        scrollToBottom();
    }, [messages, statusMessage, streamingContent, scrollToBottom]);

    useEffect(() => {
        if (isConnected) {
            subscribe("workspace:default");
        }
    }, [isConnected, subscribe]);

    return {
        input,
        setInput,
        pendingImages,
        setPendingImages,
        isProcessing,
        statusMessage,
        backgroundRun,
        messages,
        pendingApproval,
        sessionTitle,
        chatAgent,
        isEditingTitle,
        setIsEditingTitle,
        tempTitle,
        setTempTitle,
        messagesEndRef,
        isVoiceModeOpen,
        setIsVoiceModeOpen,
        activeAttachments,
        setActiveAttachments,
        isUploading,
        streamingContent,
        currentStreamId,
        handleSend,
        handleStop,
        handleTitleSave,
        handleFeedback,
        handleRegenerate,
        uploadFile,
        toast,
        providerError,
        clearProviderError: () => setProviderError(null)
    };
};
