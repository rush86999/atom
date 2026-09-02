"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Send, ArrowLeft, RefreshCw, History, Trash2, GraduationCap, MessageSquare, ShieldCheck } from "lucide-react";
import { CanvasPanel } from "@/components/canvas/CanvasPanel";
import { CanvasVersionHistory } from "@/components/canvas/CanvasVersionHistory";
import { isCanvasContentFrame } from "@/lib/canvasFrame";
import { MiniAppHarness } from "@/components/canvas/MiniAppHarness";
import { TrainingPanel } from "@/components/canvas/TrainingPanel";
import { JourneyPanel } from "@/components/canvas/JourneyPanel";
import { AutonomyPanel } from "@/components/canvas/AutonomyPanel";
import { ChatFeedbackControls, ChatFeedbackType } from "@/components/canvas/ChatFeedbackControls";
import { useWebSocket } from "@/hooks/useWebSocket";
import { ReasoningChain, type ReasoningStep } from "@/components/Agents/ReasoningChain";
import { fetchSessionTrace, submitStepFeedback } from "@/lib/agent-trace-api";
import { useCanvasStateRegistration } from "@/hooks/useCanvasStateRegistration";
import { getCurrentUserId } from "@/lib/identity";
import type { CanvasTrainingContext } from "@/lib/maturity-api";

interface CanvasMessage {
    id: string;
    type: "user" | "assistant" | "system";
    content: string;
    timestamp: Date;
    /** True while reply tokens are still arriving over the WebSocket. */
    streaming?: boolean;
    // Training feedback state + attribution for the feedback calls.
    feedback?: ChatFeedbackType | null;
    model?: string | null;
    provider?: string | null;
    // Reasoning steps for THIS reply (live-captured from agent_step_update)
    // + the identifiers step-level training feedback needs.
    reasoningTrace?: ReasoningStep[];
    executionId?: string;
    agentId?: string;
}

export default function CanvasDetailPage() {
    const router = useRouter();
    // Direct URL loads in dev can serve the route shell with an EMPTY
    // router.query (observed live 2026-08-31: __NEXT_DATA__.query:{} →
    // canvasId undefined → loadCanvas bails before clearing `loading` → the
    // page spins on "Loading canvas…" forever; client-side navigation from
    // the canvases list always worked). window.location.pathname is
    // authoritative for /canvas/[id] — but ONLY after mount: using it
    // during the hydration render made the client's first output differ
    // from the server HTML ("Canvas undefined" vs "Canvas e7249…") and
    // blew up hydration itself (Recoverable Error: text content does not
    // match). Mount-gated, the first render matches the server, then the
    // id resolves.
    const routerId = router.query?.id;
    const [mounted, setMounted] = useState(false);
    useEffect(() => setMounted(true), []);
    const canvasId = (Array.isArray(routerId) ? routerId[0] : routerId)
        || (mounted ? window.location.pathname.split("/")[2] : undefined);
    const userId = typeof window !== "undefined" ? (localStorage.getItem("user_id") || getCurrentUserId()) : getCurrentUserId();

    // Canvas state
    const [canvasData, setCanvasData] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [showHistory, setShowHistory] = useState(false);

    // Chat panel state
    const [messages, setMessages] = useState<CanvasMessage[]>([]);
    // CanvasPanel registers a flush of its pending autosave here; every chat
    // send awaits it first — the co-editor plans against the durable store,
    // and an unsaved composer edit ("i added my signature, adjust" inside
    // the autosave debounce window) was invisible to the agent, which then
    // planned from the pre-edit snapshot and clobbered the user's work
    // (observed live 2026-09-02).
    const panelFlushRef = useRef<(() => Promise<void>) | null>(null);
    const registerPanelFlush = useCallback((fn: () => Promise<void>) => {
        panelFlushRef.current = fn;
    }, []);
    // Mirror for async helpers (late-reply polling) that must read the
    // current transcript without re-creating handleSendMessage per render.
    const messagesRef = useRef<CanvasMessage[]>([]);
    useEffect(() => { messagesRef.current = messages; }, [messages]);
    const [historyRuns, setHistoryRuns] = useState<any[]>([]);
    const [chatInput, setChatInput] = useState("");
    // Auto-grow the co-editor composer to fit multi-line messages.
    const chatInputRef = useRef<HTMLTextAreaElement>(null);
    useEffect(() => {
        const el = chatInputRef.current;
        if (el) {
            el.style.height = 'auto';
            el.style.height = `${el.scrollHeight}px`;
        }
    }, [chatInput]);
    const [isAgentResponding, setIsAgentResponding] = useState(false);
    // Transient confirmation under the chat input after a feedback submit.
    const [feedbackNotice, setFeedbackNotice] = useState<string | null>(null);
    // Session continuity: the panel used to send session_id "new" on EVERY
    // turn, so each message started a disconnected conversation. The canvas→
    // session association is DB-backed (CanvasContext, written by the chat
    // route on every canvas turn) so it survives refreshes AND works across
    // devices/browsers; ?session= (arrived via chat) still wins as the
    // explicit navigation intent.
    const [chatSessionId, setChatSessionId] = useState<string | null>(null);
    const hydratedSessionRef = useRef<string | null>(null);
    // Thumbs choices restored from the canvas context (survive refresh);
    // keyed by assistant message input_summary — exactly what the feedback
    // call sends as the stable message identity.
    const [restoredFeedback, setRestoredFeedback] = useState<Record<string, { feedback_type: ChatFeedbackType; comment?: string }> | null>(null);

    // Resolve the panel's session: ?session= wins, else the server-side
    // binding for this canvas.
    useEffect(() => {
        if (!canvasId || typeof window === "undefined") return;
        const fromQuery = router.query.session as string | undefined;
        if (fromQuery && fromQuery !== "new") {
            setChatSessionId(fromQuery);
        }
        let cancelled = false;
        (async () => {
            try {
                const { apiClient } = await import("../../lib/api-client");
                const resp = await apiClient.get(`/api/canvas/${canvasId}/context`);
                const snap = (resp as any).data || resp;
                const state = snap?.current_state || snap?.data?.current_state;
                const bound = state?.chat_session_id;
                if (!cancelled && bound) setChatSessionId(bound);
                // Persisted thumbs state (keyed by assistant message
                // input_summary) — applied to restored messages at hydration.
                if (!cancelled && state?.chat_feedback) {
                    setRestoredFeedback(state.chat_feedback as Record<string, { feedback_type: ChatFeedbackType; comment?: string }>);
                }
            } catch {
                // No context/binding yet — the panel starts a new
                // conversation on first send; the binding appears after it.
            }
        })();
        return () => { cancelled = true; };
    }, [canvasId, router.query.session]);

    // Hydrate the panel transcript from the session store so a refresh
    // doesn't wipe the co-editing conversation (same pattern as
    // GlobalChatWidget's loadSessionHistory).
    useEffect(() => {
        if (!chatSessionId || hydratedSessionRef.current === chatSessionId) return;
        hydratedSessionRef.current = chatSessionId;
        let cancelled = false;
        (async () => {
            try {
                const { apiClient } = await import("../../lib/api-client");
                const resp = await apiClient.get(
                    `/api/chat/history/${chatSessionId}?user_id=${userId}`
                );
                const data = (resp as any).data || resp;
                const rebuilt: CanvasMessage[] = [];
                for (const h of data?.messages || []) {
                    const ts = new Date(h.timestamp || Date.now());
                    if (typeof h.message === "string" && h.message.trim()) {
                        rebuilt.push({
                            id: `hu_${rebuilt.length}`,
                            type: "user",
                            content: h.message,
                            timestamp: ts,
                        });
                    }
                    const ai = h?.response?.message;
                    if (typeof ai === "string" && ai.trim()) {
                        // Restore the thumbs state recorded on the canvas
                        // context — keyed by the same input_summary slice
                        // the feedback call sends (stable across refresh).
                        const restored = restoredFeedback?.[ai.slice(0, 200)];
                        rebuilt.push({
                            id: `ha_${rebuilt.length}`,
                            type: "assistant",
                            content: ai,
                            timestamp: ts,
                            feedback: restored?.feedback_type ?? null,
                        });
                    }
                }
                if (!cancelled && rebuilt.length > 0) setMessages(rebuilt);
            } catch {
                // Stale/dead session id — clear the state so the next send
                // starts fresh instead of reusing it. (The server binding is
                // not deleted: the id may be valid again later, e.g. after a
                // transient history-store failure; a later turn rebinds.)
                if (!cancelled) setChatSessionId(null);
                hydratedSessionRef.current = null;
            }
        })();
        return () => { cancelled = true; };
    }, [chatSessionId, canvasId, userId, restoredFeedback]);

    // Restored sessions: the reasoning steps of PAST canvas turns were
    // persisted all along (AgentReasoningStep) but never surfaced. Pull the
    // session trace once so supervisors can review + rate old runs too.
    useEffect(() => {
        if (!chatSessionId || typeof window === "undefined") return;
        let cancelled = false;
        (async () => {
            try {
                const { runs } = await fetchSessionTrace(chatSessionId, 5);
                if (!cancelled && runs?.length) setHistoryRuns(runs);
            } catch {
                // trace API is AGENT_VIEW-gated; non-viewers just lose history
            }
        })();
        return () => { cancelled = true; };
    }, [chatSessionId]);

    // Apply restored thumbs to whatever assistant messages are loaded —
    // separate from hydration so it works regardless of which fetch
    // (context vs. history) resolves first.
    useEffect(() => {
        if (!restoredFeedback) return;
        setMessages(prev => prev.map(m =>
            m.type === "assistant" && m.feedback == null
                ? { ...m, feedback: restoredFeedback[m.content.slice(0, 200)]?.feedback_type ?? null }
                : m
        ));
    }, [restoredFeedback]);

    // WebSocket — page-agnostic, auto-subscribes to user:{userId}
    const { lastMessage, isConnected } = useWebSocket({});

    // Training panel state: the sidebar hosts the co-editor chat and the
    // agent training panel (approve, teach, score, graduate) side by side.
    const [sideTab, setSideTab] = useState<"chat" | "training" | "journey" | "autonomy">("chat");
    // Keep the co-editor transcript pinned to the newest message. sideTab is
    // a dependency because switching tabs UNMOUNTS the chat list — the end
    // anchor goes null with it, so returning to the Chat tab remounts the
    // list scrolled to the TOP. Without re-running this effect on the tab
    // change the user lands on the first message instead of the latest.
    const chatEndRef = useRef<HTMLDivElement>(null);
    const chatTabMountedRef = useRef(sideTab === "chat");
    useEffect(() => {
        if (sideTab !== "chat") {
            chatTabMountedRef.current = false;
            return;
        }
        // Instant jump when the list just remounted (it sits at the top);
        // smooth follow for new messages while the tab stays open.
        const behavior = chatTabMountedRef.current ? "smooth" : "auto";
        chatTabMountedRef.current = true;
        chatEndRef.current?.scrollIntoView({ behavior });
    }, [messages, isAgentResponding, sideTab]);
    const [trainingCtx, setTrainingCtx] = useState<CanvasTrainingContext | null>(null);

    // The canvas's hire must be known on the CHAT tab too, not just when the
    // training panel is opened — the co-editor chat runs as this agent
    // (persona, tier behavior, learning mode when not yet mature). The panel
    // re-fetches on its own mount; this just resolves identity up front.
    useEffect(() => {
        if (!canvasId || typeof window === "undefined") return;
        let cancelled = false;
        (async () => {
            try {
                const { getCanvasTrainingContext } = await import("../../lib/maturity-api");
                const ctx = await getCanvasTrainingContext(
                    canvasId as string,
                    (router.query.agent_id as string) || undefined
                );
                if (!cancelled && ctx?.agent) setTrainingCtx(ctx);
            } catch {
                // No resolvable hire — chat runs as the platform assistant.
            }
        })();
        return () => { cancelled = true; };
    }, [canvasId, router.query.agent_id]);

    // Register canvas state for AI accessibility
    const canvasState = canvasData ? {
        type: canvasData.canvas_type || "generic",
        component: canvasData.canvas_type || "generic",
        title: canvasData.title || canvasId as string,
        data: canvasData.content,
        // Training read-back: the agent can see it is being trained on this
        // canvas, by whom, and in which session.
        ...(trainingCtx?.agent ? {
            training: {
                agent_id: trainingCtx.agent.id,
                session_id: trainingCtx.linked_session?.id ?? null,
                tier: trainingCtx.agent.tier,
            },
        } : {}),
    } : null;
    useCanvasStateRegistration(canvasId as string, canvasState as any);

    // Load canvas content by ID
    const loadCanvas = useCallback(async () => {
        if (!canvasId) return;
        try {
            const { apiClient } = await import("../../lib/api-client");
            const resp = await apiClient.get(`/api/canvas/${canvasId}`);
            const data = (resp as any).data || resp;
            if (data.success !== false) {
                // Derive the version from the append-only audit trail: each
                // present/update appends a row, matching the v{n} badge that
                // the chat flow shows. Best-effort — never blocks rendering.
                let version: number | undefined;
                try {
                    const hist = await apiClient.get(`/api/canvas/${canvasId}/history`);
                    const histData = (hist as any).data || hist;
                    const count = histData?.count ?? histData?.history?.length;
                    if (typeof count === "number" && count > 0) {
                        version = count;
                    }
                } catch {
                    // History is best-effort; version badge simply stays hidden.
                }
                setCanvasData({ ...data, version });
            }
        } catch (e) {
            console.error("Failed to load canvas:", e);
        } finally {
            setLoading(false);
        }
    }, [canvasId]);

    useEffect(() => {
        loadCanvas();
    }, [loadCanvas]);

    // Training-session canvases ARE the supervised pass — open straight onto
    // the training tab so the supervisor can teach/score without hunting.
    useEffect(() => {
        if (canvasData?.content?.type === "training_session") setSideTab("training");
    }, [canvasData?.content?.type]);

    // Mirror for the WS handler: step events are filtered by the chat
    // session, which is set asynchronously — a state read here would be a
    // stale closure.
    const chatSessionIdRef = useRef<string | null>(null);
    useEffect(() => { chatSessionIdRef.current = chatSessionId; }, [chatSessionId]);

    // Listen for live canvas updates via WebSocket
    useEffect(() => {
        if (!lastMessage) return;
        const msg = typeof lastMessage === "string" ? JSON.parse(lastMessage) : lastMessage;

        // Reasoning steps for the co-editor chat — the SAME events the main
        // chat's workspace panel consumes. The orchestrator records these on
        // canvas turns (edit planning, governance gates, actions) and
        // persists AgentReasoningStep rows, so capturing them here closes
        // the training gap: every canvas turn's reasoning is visible AND
        // thumb-rateable like regular chat.
        if (msg.type === "agent_step_update") {
            const payload = msg.data ?? msg;
            const rawStep = payload?.step && typeof payload.step === "object" ? payload.step : null;
            if (!rawStep) return;
            const evtSession = payload.session_id ?? rawStep.session_id;
            const activeSession = chatSessionIdRef.current;
            if (evtSession && activeSession && evtSession !== activeSession) return;
            const observation = rawStep.observation ?? rawStep.output ?? "";
            const step = {
                type: rawStep.type ?? rawStep.step_type ?? "step",
                // content renders first in ReasoningStepItem — on canvas turns
                // the observation IS the substance (gate decisions, edit
                // results), so it outranks the thought line.
                content: observation || rawStep.thought || undefined,
                thought: rawStep.thought,
                action: rawStep.action,
                observation,
                step: rawStep.step_number ?? rawStep.step,
            } as unknown as ReasoningStep;
            const executionId = String(payload.execution_id ?? rawStep.execution_id ?? "live");
            const wireAgentId = payload.agent_id ?? msg.agent_id;
            setMessages(prev => {
                const next = [...prev];
                for (let i = next.length - 1; i >= 0; i--) {
                    if (next[i].type === "assistant") {
                        next[i] = {
                            ...next[i],
                            executionId,
                            agentId: next[i].agentId ?? wireAgentId,
                            reasoningTrace: [...(next[i].reasoningTrace || []), step],
                        };
                        break;
                    }
                }
                return next;
            });
            return;
        }

        // STREAMED REPLY: the backend broadcasts reply tokens over this
        // socket as they generate — render them into a live assistant bubble
        // so time-to-first-content is seconds, not the full generation.
        if (msg.type === "chat_token" || msg.type === "chat_token_done") {
            const data = msg.data || {};
            // First-message race: tokens arrive BEFORE the POST response
            // sets chatSessionId (the server creates the session id). Only
            // filter once the panel knows its session.
            if (msg.type === "chat_token" && chatSessionId && data.session_id !== chatSessionId) return;
            setMessages(prev => {
                const streamId = `stream_${data.session_id}`;
                const existing = prev.find(m => m.id === streamId);
                // The stream id is session-keyed, so it is REUSED across
                // turns. A bubble with that id that already FINISHED belongs
                // to a previous turn: appending this turn's reply into it
                // rendered the answer under the WRONG question and left the
                // newest question visually unanswered (observed live
                // 2026-09-02: turn 3's reply overwrote turn 2's bubble).
                // Retire the finished bubble (unique permanent id, stays
                // where it was rendered) and open a fresh stream bubble at
                // the end of the thread for this turn. `!== true` (not
                // `=== false`) so a bubble the done event created without
                // the flag also counts as finished.
                if (existing && existing.streaming !== true) {
                    const retired = { ...existing, id: `a_${existing.timestamp.getTime()}_${Math.random().toString(36).slice(2, 7)}` };
                    const fresh: CanvasMessage = { id: streamId, type: "assistant", content: "", timestamp: new Date(), streaming: true };
                    if (msg.type === "chat_token_done") {
                        const finalContent = String(data.content ?? "");
                        if (!finalContent) return [...prev.map(m => (m.id === streamId ? retired : m))];
                        fresh.content = finalContent;
                        fresh.streaming = false;
                    } else {
                        fresh.content = String(data.delta ?? "");
                    }
                    return [...prev.map(m => (m.id === streamId ? retired : m)), fresh];
                }
                if (msg.type === "chat_token_done") {
                    const finalContent = String(data.content ?? (existing?.content ?? ""));
                    if (!finalContent) return prev.filter(m => m.id !== streamId);
                    if (existing) {
                        return prev.map(m => (m.id === streamId ? { ...m, content: finalContent, streaming: false } : m));
                    }
                    return [...prev, { id: streamId, type: "assistant" as const, content: finalContent, timestamp: new Date() }];
                }
                const delta = String(data.delta ?? "");
                if (existing) {
                    return prev.map(m => (m.id === streamId ? { ...m, content: m.content + delta } : m));
                }
                return [...prev, { id: streamId, type: "assistant" as const, content: delta, timestamp: new Date(), streaming: true }];
            });
            return;
        }

        if (msg.type === "canvas:update" || msg.type === "canvas:present") {
            const data = msg.data || msg;
            // mini_app_state broadcasts are consumed by the MiniAppHarness (live
            // state preview) — they must NOT overwrite the rendered canvas content.
            if (data.action === "mini_app_state") return;
            if (data.canvas_id === canvasId && data.action !== "close") {
                // Event frames (email_send status, mini_app_state, …) ride the
                // same channel without carrying canvas content. Applying them
                // as content replaced the user's draft with a {status, payload}
                // blob (observed live 2026-08-31: a failed send made the open
                // email draft vanish). The durable store is untouched.
                if (!isCanvasContentFrame(data)) return;
                setCanvasData((prev: any) => ({
                    ...prev,
                    content: data.data || data.content,
                    title: data.title || prev?.title,
                    canvas_type: data.component || data.canvas_type || prev?.canvas_type,
                }));
            }
            if (data.action === "close" && data.canvas_id === canvasId) {
                setCanvasData(null);
            }
        }
    }, [lastMessage, canvasId]);

    // Toggle the version-history slide-out. Fetching + restore live in the
    // shared CanvasVersionHistory component (the chat-page host uses it too).
    const loadHistory = () => setShowHistory(!showHistory);

    // Delete canvas
    const handleDelete = async () => {
        if (!canvasId) return;
        if (!confirm("Delete this canvas? The audit history is preserved.")) return;
        try {
            const { apiClient } = await import("../../lib/api-client");
            await apiClient.delete(`/api/canvas/${canvasId}`);
            router.push("/canvas");
        } catch (e) {
            console.error("Delete failed:", e);
        }
    };

    // Send message to agent about this canvas
    const handleSendMessage = async () => {
        if (!chatInput.trim()) return;
        const userMsg: CanvasMessage = {
            id: `u_${Date.now()}`,
            type: "user",
            content: chatInput,
            timestamp: new Date(),
        };
        setMessages(prev => {
            // Retire any lingering stream bubble from the PREVIOUS turn
            // before this turn's user message lands. The stream id is
            // session-keyed, so a bubble that survived its turn (socket died
            // before chat_token_done — it stays stuck mid-stream) would
            // otherwise swallow the NEXT turn's reply and render it under
            // the wrong question. Renamed here it stays visible where it
            // was, and this turn's tokens open a fresh bubble.
            const prevSid = chatSessionId;
            const retired = prevSid
                ? prev.map(m => (m.id === `stream_${prevSid}` ? { ...m, id: `a_${m.timestamp.getTime()}_${Math.random().toString(36).slice(2, 7)}` } : m))
                : prev;
            return [...retired, userMsg];
        });
        setChatInput("");
        setIsAgentResponding(true);
        // Persist any pending composer edit BEFORE the turn reads the canvas:
        // the agent's view of the draft is the durable store, not this page's
        // local state (flush is a no-op when nothing is pending).
        try {
            await panelFlushRef.current?.();
        } catch {
            // A failed flush must not eat the user's message — the autosave
            // retry path still owns surfacing save problems.
        }

        try {
            const { apiClient } = await import("../../lib/api-client");
            // Expanded-from-chat canvases coordinate with the SAME agent and
            // the SAME conversation: session keeps continuity, agent_id keeps
            // the hire's persona, role-aware memory and tier behavior. On
            // standalone canvases the training panel's resolved agent fills
            // the identity in (audit-row provenance).
            const fromChat = router.query.from === "chat";
            const agentId = (router.query.agent_id as string) || trainingCtx?.agent?.id || undefined;
            const resp = await apiClient.post("/api/chat/message", {
                message: chatInput,
                user_id: userId,
                session_id: chatSessionId || (fromChat ? (router.query.session as string) : undefined) || "new",
                agent_id: agentId,
                context: {
                    current_page: `/canvas/${canvasId}`,
                    canvas_id: canvasId,
                    canvas_type: canvasData?.canvas_type,
                    canvas_title: canvasData?.title,
                    canvas_content: canvasData?.content,
                    agent_id: agentId,
                    conversation_history: messages.slice(-5).map(m => ({
                        role: m.type === "user" ? "user" : "assistant",
                        content: m.content,
                    })),
                },
            }, {
                // The agent loop (LLM + canvas summary + embeddings) regularly
                // exceeds the global 10s axios timeout — same override the
                // main chat uses (useChatInterface). Without it the reply is
                // generated server-side but the UI already showed "Could not
                // reach the agent", and the auto-retry re-fired the request.
                timeout: 120000,
                // @ts-ignore
                retry: false,
            });
            const data = (resp as any).data || resp;
            if (data.session_id && data.session_id !== "new") {
                setChatSessionId(data.session_id);
            }
            if (data.success && data.message) {
                // The authoritative reply either FINALIZES the streamed
                // bubble (same session) or appends a fresh assistant message
                // (no-stream fallback) — never both, which duplicated every
                // streamed reply (observed live 2026-09-01).
                const streamId = `stream_${data.session_id}`;
                setMessages(prev => {
                    const streamed = prev.find(m => m.id === streamId);
                    if (streamed) {
                        return prev.map(m => (m.id === streamId ? {
                            ...m,
                            content: data.message,
                            streaming: false,
                            model: data.model ?? m.model ?? null,
                            provider: data.provider ?? m.provider ?? null,
                        } : m));
                    }
                    return [...prev, {
                        id: `a_${Date.now()}`,
                        type: "assistant",
                        content: data.message,
                        timestamp: new Date(),
                        // Attribution for the message-level feedback call.
                        model: data.model ?? null,
                        provider: data.provider ?? null,
                    }];
                });
                // The WS canvas:update broadcast is the primary live carrier,
                // but a stale socket silently drops it — an auth-expiry close
                // never reconnects while the JWT lives in localStorage, and a
                // throttled background tab can miss frames — leaving the reply
                // claiming an edit the canvas never shows (observed live:
                // audit row + broadcast landed, page stayed on the old draft).
                // Both handled turns flag themselves in the response
                // (metadata.canvas_edit.updated / metadata.canvas_action —
                // chat_routes maps the orchestrator's `data` to `metadata`);
                // re-fetch from the audit trail so the canvas converges even
                // when the broadcast was missed. Focus moved to the chat
                // input on send, so the composer's onBlur already flushed
                // pending autosave — the durable store holds the newest
                // draft at this point.
                if (data.metadata?.canvas_edit?.updated || data.metadata?.canvas_action) {
                    loadCanvas();
                }
            } else if (data.error_code === "no_llm_provider") {
                setMessages(prev => [...prev, {
                    id: "sys",
                    type: "system",
                    content: "⚠️ No AI provider configured. Add an API key in Settings.",
                    timestamp: new Date(),
                }]);
            } else {
                // Unsuccessful replies must still surface — a silent spinner
                // that ends with no message reads as "chat is broken".
                setMessages(prev => [...prev, {
                    id: `sys_${Date.now()}`,
                    type: "system",
                    content: `⚠️ ${data.message || "The agent could not handle that request."}`,
                    timestamp: new Date(),
                }]);
            }
        } catch (e: any) {
            // Long agent turns can outlive this request: the backend keeps
            // working and PERSISTS the reply even after the browser gives up
            // (observed live 2026-08-31: the panel showed "Could not reach
            // the agent" for a turn whose finished reply sat in chat history
            // — a page reload made it "magically" appear). On timeout-shaped
            // failures (no response / abort / 504), poll the durable history
            // briefly for the late reply before declaring failure. Real 4xx
            // responses skip the poll — retrying those is pointless.
            const timedOut = !e?.response || e?.code === "ECONNABORTED" || e?.response?.status === 504;
            let lateReply: CanvasMessage | null = null;
            const sid = timedOut
                ? chatSessionId || (router.query.from === "chat" ? (router.query.session as string) : undefined)
                : undefined;
            if (sid) {
                const { apiClient } = await import("../../lib/api-client");
                for (let attempt = 0; attempt < 12 && !lateReply; attempt++) {
                    await new Promise(r => setTimeout(r, 5000));
                    try {
                        const resp = await apiClient.get(
                            `/api/chat/history/${sid}?user_id=${userId}`,
                            { timeout: 10000 },
                        );
                        const data = (resp as any).data || resp;
                        const rows: any[] = data?.messages || [];
                        const lastAi = [...rows].reverse().find(
                            r => r?.role === "assistant" && typeof r?.response?.message === "string" && r.response.message.trim(),
                        );
                        const content = lastAi?.response?.message;
                        // Only accept an assistant message the panel
                        // isn't already showing (the guard keeps a
                        // previous turn's reply from being re-rendered).
                        if (content && !messagesRef.current.some(m => m.type === "assistant" && m.content === content)) {
                            lateReply = {
                                id: `a_${Date.now()}`,
                                type: "assistant",
                                content,
                                timestamp: new Date(lastAi?.timestamp || Date.now()),
                                model: (lastAi as any)?.model ?? null,
                                provider: (lastAi as any)?.provider ?? null,
                            };
                        }
                    } catch {
                        // History hiccup mid-poll — keep trying.
                    }
                }
            }
            if (lateReply) {
                setMessages(prev => [...prev, lateReply!]);
                setChatSessionId(prev => prev || sid!);
            } else {
                setMessages(prev => [...prev, {
                    id: "err",
                    type: "system",
                    content: "⚠️ Could not reach the agent. Please try again.",
                    timestamp: new Date(),
                }]);
            }
        } finally {
            setIsAgentResponding(false);
        }
    };

    // Thumbs/note feedback on an assistant reply — the "chat for training"
    // channel. Two loops, two calls:
    // - /api/reasoning/feedback is the TRAINING loop: governance stores an
    //   AgentFeedback row, adjudicates it, and moves the agent's confidence
    //   + learning log (same endpoint AgentWorkspace uses per step).
    // - /api/chat/feedback keeps the model-routing learner in parity with
    //   the main chat (best-effort; the backend never errors it either).
    // A note submits as thumbs_down + text (corrective) so adjudication
    // reads the polarity; clicking the already-chosen thumb just clears it.
    const handleFeedback = async (msg: CanvasMessage, type: ChatFeedbackType, comment?: string) => {
        if (!comment && msg.feedback === type) {
            setMessages(prev => prev.map(m => (m.id === msg.id ? { ...m, feedback: null } : m)));
            // Also clear the PERSISTED choice — otherwise the stale thumb
            // reappears from the canvas context on the next refresh.
            try {
                const { apiClient } = await import("../../lib/api-client");
                await apiClient.post(`/api/canvas/${canvasId}/chat-feedback/clear`, {
                    input_summary: msg.content.slice(0, 200),
                });
            } catch {
                // best-effort: local clear already happened
            }
            return;
        }
        setMessages(prev => prev.map(m => (m.id === msg.id ? { ...m, feedback: type } : m)));
        setFeedbackNotice(null);
        const agentId = (router.query.agent_id as string) || trainingCtx?.agent?.id || undefined;
        try {
            if (agentId) {
                await submitStepFeedback({
                    agentId,
                    runId: chatSessionId || "canvas",
                    stepIndex: -1,
                    stepContent: {
                        input_summary: msg.content.slice(0, 200),
                        canvas_id: canvasId,
                        source: "canvas_chat",
                    },
                    feedbackType: type,
                    comment,
                });
            }
            try {
                const { apiClient } = await import("../../lib/api-client");
                await apiClient.post("/api/chat/feedback", {
                    message_id: msg.id,
                    feedback: type,
                    comment,
                    model: msg.model ?? undefined,
                    provider: msg.provider ?? undefined,
                    session_id: chatSessionId ?? undefined,
                });
            } catch {
                // router-learning feedback is best-effort by design
            }
            setFeedbackNotice("✓ Feedback recorded — it feeds the agent's training.");
            setTimeout(() => setFeedbackNotice(null), 4000);
        } catch {
            setFeedbackNotice("⚠️ Feedback could not be recorded — try again.");
        }
    };

    // Email canvases persist {to, cc, subject, body} in the audit trail; the
    // CanvasPanel email composer reads `metadata` from the message payload,
    // so derive it here or the To/Cc/Subject fields render empty on
    // /canvas/{id}.
    const emailMetadata =
        canvasData?.canvas_type === "email" && canvasData.content && typeof canvasData.content === "object"
            ? {
                to: canvasData.content.to || "",
                cc: canvasData.content.cc || "",
                subject: canvasData.content.subject || "",
            }
            : undefined;

    const canvasLastMessage = canvasData ? {
        type: "canvas:update",
        data: {
            action: "present",
            // File-bound office canvases (content.office_file) render the
            // editable OfficeFileCanvas; format → component names — note
            // xlsx maps to office_EXCEL (the naive `office_${format}`
            // produced "office_xlsx", which no component case handles, so
            // excel canvases fell to the raw-JSON fallback). Audit-sourced
            // content carries the office_* component name directly.
            component: canvasData.content?.office_file
                ? (({ xlsx: "office_excel", docx: "office_word", pptx: "office_pptx" } as Record<string, string>)[canvasData.content.format] || `office_${canvasData.content.format || "docx"}`)
                : (typeof canvasData.content?.component === "string" && canvasData.content.component.startsWith("office_"))
                    ? canvasData.content.component
                    : (canvasData.canvas_type || "markdown"),
            canvas_id: canvasId,
            data: canvasData.content,
            title: canvasData.title,
            version: canvasData.version,
            ...(emailMetadata ? { metadata: emailMetadata } : {}),
        },
    } : lastMessage;

    return (
        // _app.tsx already wraps every non-standalone page in <Layout> — a
        // second wrapper here rendered a duplicate navigation sidebar.
        <>
            <Head>
                {/* Single-string child: `X | Atom` as JSX children renders an
                    ARRAY into <title>, which fails hydration and froze the
                    page on its SSR shell ("Loading canvas…" forever). */}
                <title>{`${canvasData?.title || "Canvas"} | Atom`}</title>
            </Head>
            <div className="h-[calc(100vh-3.5rem)] flex flex-col">
                {/* Canvas header bar */}
                <div className="flex items-center justify-between border-b px-4 py-2 shrink-0">
                    <div className="flex items-center gap-3">
                        {router.query.from === "chat" && (
                            <Button
                                variant="ghost"
                                size="sm"
                                data-testid="canvas-back-to-chat"
                                title={router.query.agent_id ? "Back to the agent chat" : "Back to chat"}
                                onClick={() => {
                                    const agentId = router.query.agent_id;
                                    router.push(agentId ? `/chat?agent_id=${agentId}` : "/chat");
                                }}
                            >
                                <ArrowLeft className="h-4 w-4 mr-1" /> Back to chat
                            </Button>
                        )}
                        <Link href="/canvas">
                            <Button variant="ghost" size="sm">
                                <ArrowLeft className="h-4 w-4 mr-1" /> All Canvases
                            </Button>
                        </Link>
                        {/* canvasId comes from the URL: the client router
                            initializes it BEFORE hydration while the server
                            shell rendered "Canvas undefined" — a legitimate
                            text mismatch, suppressed for this element only. */}
                        <h1 suppressHydrationWarning className="text-lg font-semibold truncate max-w-xs md:max-w-md">
                            {canvasData?.title || `Canvas ${canvasId}`}
                        </h1>
                        {canvasData?.canvas_type && (
                            <span className="text-[10px] uppercase bg-muted px-1.5 py-0.5 rounded text-muted-foreground">
                                {canvasData.canvas_type}
                            </span>
                        )}
                        {/* The hire attached to this canvas: name · category
                            (sales, …) · maturity tier · confidence — visible
                            to the end user without opening the training tab. */}
                        {trainingCtx?.agent && (
                            <span
                                data-testid="canvas-hire-badge"
                                title={`${trainingCtx.agent.name || "Hire"} — ${trainingCtx.agent.domain || "general"} · ${trainingCtx.agent.tier || "student"} · ${Math.round((trainingCtx.agent.confidence ?? 0) * 100)}% confidence`}
                                className="hidden md:flex items-center gap-1.5 text-[10px] bg-muted px-2 py-0.5 rounded text-muted-foreground max-w-xs"
                            >
                                <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${
                                    (trainingCtx.agent.tier || "").toLowerCase() === "autonomous"
                                        ? "bg-green-500"
                                        : (trainingCtx.agent.tier || "").toLowerCase() === "supervised"
                                            ? "bg-orange-500"
                                            : (trainingCtx.agent.tier || "").toLowerCase() === "intern"
                                                ? "bg-amber-400"
                                                : "bg-sky-400"
                                }`} />
                                <span className="truncate font-medium text-foreground">
                                    {trainingCtx.agent.name || "Hire"}
                                </span>
                                <span className="truncate lowercase">
                                    {trainingCtx.agent.domain || "general"}
                                </span>
                                <span className="uppercase font-semibold shrink-0">
                                    {trainingCtx.agent.tier || "student"}
                                </span>
                                <span className="shrink-0">
                                    {Math.round((trainingCtx.agent.confidence ?? 0) * 100)}%
                                </span>
                            </span>
                        )}
                    </div>
                    <div className="flex items-center gap-1">
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setSideTab("training")}
                            title="Agent training — teach, score, graduate"
                            data-testid="canvas-training-button"
                        >
                            <GraduationCap className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={loadCanvas} title="Refresh">
                            <RefreshCw className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={loadHistory} title="Version history">
                            <History className="h-4 w-4" />
                        </Button>
                        <Button variant="ghost" size="sm" onClick={handleDelete} title="Delete">
                            <Trash2 className="h-4 w-4 text-red-500" />
                        </Button>
                    </div>
                </div>

                {/* Main content: canvas + side chat */}
                <div className="flex-1 flex overflow-hidden">
                    {/* Canvas panel (left/center, takes most space) + mini-app harness (bottom) */}
                    <div className="flex-1 flex flex-col overflow-hidden">
                        <div className="flex-1 overflow-hidden">
                            {loading ? (
                                <div className="flex items-center justify-center h-full">
                                    <p className="text-muted-foreground">Loading canvas…</p>
                                </div>
                            ) : canvasData ? (
                                <CanvasPanel lastMessage={canvasLastMessage} registerFlushBeforeSend={registerPanelFlush} />
                            ) : (
                                <div className="flex items-center justify-center h-full">
                                    <Card className="max-w-md text-center">
                                        <CardContent className="pt-6">
                                            <p className="text-muted-foreground mb-4">Canvas not found or deleted.</p>
                                            <Link href="/canvas"><Button>Browse Canvases</Button></Link>
                                        </CardContent>
                                    </Card>
                                </div>
                            )}
                        </div>
                        {canvasData && (
                            <MiniAppHarness canvasId={canvasId as string} lastMessage={lastMessage} />
                        )}
                    </div>

                    {/* Side panel (right): agent co-editor chat ↔ agent training */}
                    <div className="w-80 border-l flex flex-col bg-muted/30 shrink-0">
                        {/* Panel tabs */}
                        <div className="px-2 pt-1.5 border-b bg-background/50 shrink-0" role="tablist" aria-label="Agent panel">
                            {/* 4-column grid: a flex row of four labelled tabs is wider
                                than the w-80 panel — the last tabs were clipped out
                                of view entirely (Journey/Autonomy "missing"). */}
                            <div className="grid grid-cols-4 gap-0.5">
                                <button
                                    role="tab"
                                    aria-selected={sideTab === "chat"}
                                    onClick={() => setSideTab("chat")}
                                    className={`px-1 py-1.5 text-[11px] font-medium rounded-t-md border-b-2 flex items-center justify-center gap-1 whitespace-nowrap ${
                                        sideTab === "chat"
                                            ? "border-primary text-foreground"
                                            : "border-transparent text-muted-foreground hover:text-foreground"
                                    }`}
                                    data-testid="canvas-side-tab-chat"
                                >
                                    <MessageSquare className="h-3.5 w-3.5" /> Chat
                                </button>
                                <button
                                    role="tab"
                                    aria-selected={sideTab === "training"}
                                    onClick={() => setSideTab("training")}
                                    className={`px-1 py-1.5 text-[11px] font-medium rounded-t-md border-b-2 flex items-center justify-center gap-1 whitespace-nowrap ${
                                        sideTab === "training"
                                            ? "border-primary text-foreground"
                                            : "border-transparent text-muted-foreground hover:text-foreground"
                                    }`}
                                    data-testid="canvas-side-tab-training"
                                >
                                    <GraduationCap className="h-3.5 w-3.5" /> Training
                                </button>
                                <button
                                    role="tab"
                                    aria-selected={sideTab === "journey"}
                                    onClick={() => setSideTab("journey")}
                                    className={`px-1 py-1.5 text-[11px] font-medium rounded-t-md border-b-2 flex items-center justify-center gap-1 whitespace-nowrap ${
                                        sideTab === "journey"
                                            ? "border-primary text-foreground"
                                            : "border-transparent text-muted-foreground hover:text-foreground"
                                    }`}
                                    data-testid="canvas-side-tab-journey"
                                >
                                    <History className="h-3.5 w-3.5" /> Journey
                                </button>
                                <button
                                    role="tab"
                                    aria-selected={sideTab === "autonomy"}
                                    onClick={() => setSideTab("autonomy")}
                                    className={`px-1 py-1.5 text-[11px] font-medium rounded-t-md border-b-2 flex items-center justify-center gap-1 whitespace-nowrap ${
                                        sideTab === "autonomy"
                                            ? "border-primary text-foreground"
                                            : "border-transparent text-muted-foreground hover:text-foreground"
                                    }`}
                                    data-testid="canvas-side-tab-autonomy"
                                >
                                    <ShieldCheck className="h-3.5 w-3.5" /> Autonomy
                                </button>
                            </div>
                        </div>

                        {sideTab === "training" ? (
                            <TrainingPanel
                                canvasId={canvasId as string}
                                agentIdHint={(router.query.agent_id as string) || undefined}
                                onContextLoaded={setTrainingCtx}
                            />
                        ) : sideTab === "journey" ? (
                            <JourneyPanel canvasId={canvasId as string} />
                        ) : sideTab === "autonomy" ? (
                            <AutonomyPanel
                                canvasId={canvasId as string}
                                agentId={
                                    (router.query.agent_id as string) ||
                                    trainingCtx?.agent?.id ||
                                    undefined
                                }
                            />
                        ) : (
                            <>
                        {/* Chat header */}
                        <div className="px-3 py-2 border-b bg-background/50 shrink-0">
                            <div className="flex items-center gap-2">
                                <div className="h-2 w-2 rounded-full bg-green-500" title={isConnected ? "Connected" : "Disconnected"} />
                                <span className="text-sm font-medium">Agent Co-Editor</span>
                            </div>
                            <p className="text-[10px] text-muted-foreground mt-0.5">
                                Chat with the agent while editing this canvas
                            </p>
                        </div>

                        {/* Chat messages */}
                        <div className="flex-1 overflow-y-auto p-3 space-y-3">
                            {messages.length === 0 && (
                                <div className="text-center text-muted-foreground text-sm py-8">
                                    <p className="mb-2">💬 Ask the agent to modify this canvas</p>
                                    <p className="text-xs">e.g. "Add a new row to the spreadsheet" or "Change the chart to a bar chart"</p>
                                </div>
                            )}
                            {messages.map(msg => (
                                <div key={msg.id} className={`text-sm ${msg.type === "user" ? "text-right" : ""}`}>
                                    <div className={`inline-block max-w-[85%] px-3 py-2 rounded-lg ${
                                        msg.type === "user"
                                            ? "bg-primary text-primary-foreground"
                                            : msg.type === "system"
                                            ? "bg-amber-100 text-amber-900 dark:bg-amber-900/30 dark:text-amber-200"
                                            : "bg-background border"
                                    }`}>
                                        {msg.content}
                                    </div>
                                    {msg.type === "assistant" && !!msg.reasoningTrace?.length && (
                                        <ReasoningChain
                                            steps={msg.reasoningTrace}
                                            agentId={msg.agentId || trainingCtx?.agent?.id || "atom_main"}
                                            runId={msg.executionId}
                                            onFeedback={async (idx, type, comment) => {
                                                const steps = msg.reasoningTrace || [];
                                                try {
                                                    await submitStepFeedback({
                                                        agentId: msg.agentId || trainingCtx?.agent?.id || "atom_main",
                                                        runId: msg.executionId || chatSessionId || "live",
                                                        stepIndex: idx,
                                                        stepContent: {
                                                            step: (steps[idx] as any)?.step,
                                                            thought: steps[idx]?.thought,
                                                            action: steps[idx]?.action,
                                                            observation: steps[idx]?.observation,
                                                        },
                                                        feedbackType: type,
                                                        comment,
                                                        executionId: msg.executionId && msg.executionId !== "live" ? msg.executionId : undefined,
                                                        stepNumber: (steps[idx] as any)?.step,
                                                    });
                                                } catch {
                                                    // best-effort, same as message-level feedback
                                                }
                                            }}
                                        />
                                    )}
                                    {msg.type === "assistant" && (
                                        <ChatFeedbackControls
                                            selected={msg.feedback ?? null}
                                            onFeedback={(type, comment) => handleFeedback(msg, type, comment)}
                                        />
                                    )}
                                </div>
                            ))}
                            {historyRuns.length > 0 && (
                                <div className="pt-1 space-y-2" data-testid="canvas-history-runs">
                                    <p className="text-[10px] uppercase font-bold text-muted-foreground tracking-wider">
                                        Previous run reasoning
                                    </p>
                                    {historyRuns.slice().reverse().map(run => (
                                        <ReasoningChain
                                            key={run.execution_id}
                                            steps={(run.steps || []).map((s: any) => ({
                                                type: s.step_type ?? "step",
                                                thought: s.thought,
                                                action: s.action,
                                                observation: s.observation,
                                                step: s.step_number,
                                            }))}
                                            agentId={run.agent_id || trainingCtx?.agent?.id || "atom_main"}
                                            runId={run.execution_id}
                                            onFeedback={async (idx, type, comment) => {
                                                const steps = run.steps || [];
                                                try {
                                                    await submitStepFeedback({
                                                        agentId: run.agent_id || trainingCtx?.agent?.id || "atom_main",
                                                        runId: run.execution_id,
                                                        stepIndex: idx,
                                                        stepContent: {
                                                            step: steps[idx]?.step_number,
                                                            thought: steps[idx]?.thought,
                                                            action: steps[idx]?.action,
                                                            observation: steps[idx]?.observation,
                                                        },
                                                        feedbackType: type,
                                                        comment,
                                                        executionId: run.execution_id,
                                                        stepNumber: steps[idx]?.step_number,
                                                    });
                                                } catch {
                                                    // best-effort
                                                }
                                            }}
                                        />
                                    ))}
                                </div>
                            )}
                            {isAgentResponding && (
                                <div className="text-sm text-muted-foreground">
                                    <span className="animate-pulse">●●● Agent is working…</span>
                                </div>
                            )}
                            <div ref={chatEndRef} />
                        </div>

                        {/* Chat input */}
                        <div className="p-3 border-t shrink-0">
                            {feedbackNotice && (
                                <p role="status" data-testid="canvas-feedback-notice" className="text-[10px] text-green-600 dark:text-green-400 pb-1.5">
                                    {feedbackNotice}
                                </p>
                            )}
                            <div className="flex gap-2 items-end">
                                <Textarea
                                    ref={chatInputRef}
                                    rows={1}
                                    value={chatInput}
                                    onChange={(e: any) => setChatInput(e.target.value)}
                                    onKeyDown={(e: any) => e.key === "Enter" && !e.shiftKey && (e.preventDefault(), handleSendMessage())}
                                    placeholder="Ask the agent to edit…"
                                    disabled={isAgentResponding}
                                    className="flex-1 min-h-[44px] max-h-[140px] resize-none px-4 py-2.5 text-base"
                                />
                                <Button size="icon" className="h-11 w-11 shrink-0" onClick={handleSendMessage} disabled={isAgentResponding || !chatInput.trim()} aria-label="Send message">
                                    <Send className="h-5 w-5" />
                                </Button>
                            </div>
                        </div>
                            </>
                        )}
                    </div>
                </div>

                {/* Version history slide-out — shared component, same panel the
                    chat-page host renders (restore works for every canvas app) */}
                {showHistory && (
                    <div className="absolute right-80 top-12 bottom-0 w-64 bg-background border-l shadow-lg z-10 overflow-y-auto">
                        <div className="p-3 border-b flex justify-between items-center">
                            <h3 className="text-sm font-semibold">Version History</h3>
                            <Button variant="ghost" size="sm" onClick={() => setShowHistory(false)}>
                                <ArrowLeft className="h-3 w-3" />
                            </Button>
                        </div>
                        <CanvasVersionHistory
                            canvasId={canvasId as string}
                            onRestored={() => loadCanvas()}
                        />
                    </div>
                )}
            </div>
        </>
    );
}
