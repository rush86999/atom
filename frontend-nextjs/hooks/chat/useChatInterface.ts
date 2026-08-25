'use client';

import { useState, useRef, useEffect, useCallback } from "react";
import { ChatMessageData, ReasoningStep } from "@/components/GlobalChat/ChatMessage";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useToast } from "@/components/ui/use-toast";
import { useFileUpload } from "@/hooks/useFileUpload";
import { getCurrentUserId } from "@/lib/identity";

interface UseChatInterfaceProps {
    sessionId: string | null;
    initialAgentId?: string | null;
    onSessionCreated?: (sessionId: string) => void;
}

export const useChatInterface = ({ sessionId, initialAgentId, onSessionCreated }: UseChatInterfaceProps) => {
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [statusMessage, setStatusMessage] = useState("Agent is thinking...");
    const [messages, setMessages] = useState<ChatMessageData[]>([]);
    const [pendingApproval, setPendingApproval] = useState<{ action_id: string; tool: string; reason: string } | null>(null);
    const [currentStreamId, setCurrentStreamId] = useState<string | null>(null);
    const [sessionTitle, setSessionTitle] = useState("Current Session");
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

    const { isConnected, lastMessage, streamingContent, subscribe } = useWebSocket();
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

    const loadSessionHistory = async (sid: string) => {
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
                        if (historyItem.message) {
                            chatMessages.push({
                                id: `msg_user_${idx}`,
                                type: "user",
                                content: historyItem.message,
                                timestamp: new Date(historyItem.timestamp || Date.now()),
                                actions: [],
                            });
                        }

                        const assistantContent = historyItem.response?.message || historyItem.response;
                        const assistantActions = historyItem.response?.suggested_actions || historyItem.response?.metadata?.actions || [];
                        
                        if (assistantContent && typeof assistantContent === 'string') {
                            chatMessages.push({
                                id: `msg_assistant_${idx}`,
                                type: "assistant",
                                content: assistantContent,
                                timestamp: new Date(historyItem.timestamp || Date.now()),
                                actions: assistantActions,
                            });
                        } else if (assistantContent && typeof assistantContent === 'object' && assistantContent.message) {
                            chatMessages.push({
                                id: `msg_assistant_${idx}`,
                                type: "assistant",
                                content: assistantContent.message,
                                timestamp: new Date(historyItem.timestamp || Date.now()),
                                actions: assistantContent.suggested_actions || [],
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
    };

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

    const handleSend = async (overrideText?: string): Promise<boolean> => {
        // overrideText is used by handleRegenerate to re-send the original
        // prompt (input is empty at that point). Without it, regenerate would
        // silently delete the exchange and produce nothing.
        const currentInput = (overrideText ?? input).trim();
        if (!currentInput) return false;

        // Clear any prior provider-error banner before attempting another send.
        setProviderError(null);

        const userMsg: ChatMessageData = {
            id: Date.now().toString(),
            type: "user",
            content: currentInput,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setIsProcessing(true);
        setStatusMessage("Agent is thinking...");
        _restFulfilledRef.current = false;

        try {
            const { apiClient } = await import('../../lib/api-client');
            // Create an AbortController so handleStop can cancel this request.
            abortControllerRef.current = new AbortController();
            // Safety-net: reset isProcessing after 120s if no response/stream-complete.
            if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
            processingTimeoutRef.current = setTimeout(() => {
                setIsProcessing(false);
            }, 120000);

            const response = await apiClient.post("/api/chat/message", {
                message: currentInput,
                session_id: sessionId,
                user_id: getCurrentUserId(),
                context: {
                    current_page: "/chat",
                    agent_id: initialAgentId,
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

            // Clear the safety-net timeout on any successful resolution.
            if (processingTimeoutRef.current) {
                clearTimeout(processingTimeoutRef.current);
                processingTimeoutRef.current = null;
            }

            if (data.success && data.message) {
                if (data.session_id && data.session_id !== sessionId && data.session_id !== "new") {
                    onSessionCreated?.(data.session_id);
                }

                const agentMsg: ChatMessageData = {
                    id: (Date.now() + 1).toString(),
                    type: "assistant",
                    content: data.message,
                    timestamp: new Date(),
                    actions: data.metadata?.actions || data.suggested_actions || [],
                    model: data.model,
                    provider: data.provider,
                    memoryContext: data.memory_context || undefined,
                };
                setMessages(prev => [...prev, agentMsg]);
                // Mark this generation as REST-fulfilled so the WebSocket
                // streaming:complete path doesn't append a duplicate.
                _restFulfilledRef.current = true;
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
            // Clear attachments on EVERY exit path too. Previously this only
            // ran after a successful response, so a request rejected with 400
            // (e.g. the backend security middleware flagging base64 image
            // data) left the attachment stuck in state — and it was re-sent
            // (and re-rejected) with every subsequent message, permanently
            // breaking the chat until a page refresh.
            setActiveAttachments([]);
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

    useEffect(() => {
        if (sessionId && sessionId !== "new") {
            // BUG-106: Clear messages immediately so the previous session's
            // conversation doesn't flash during the async history fetch.
            setMessages([]);
            setIsProcessing(false);
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
        }
    }, [sessionId]);

    useEffect(() => {
        scrollToBottom();
    }, [messages, statusMessage, streamingContent, scrollToBottom]);

    useEffect(() => {
        if (isConnected) {
            subscribe("workspace:default");
        }
    }, [isConnected, subscribe]);

    useEffect(() => {
        if (!lastMessage) return;
        const msg = lastMessage as any;

        if (msg.type === "agent_step_update") {
            const step: ReasoningStep = {
                step: msg.step?.step || 1,
                thought: msg.step?.thought,
                action: msg.step?.action,
                observation: msg.step?.output,
                final_answer: msg.step?.final_answer,
            };

            if (msg.step?.action) {
                setStatusMessage(`Executing ${msg.step.action.tool}...`);
            } else if (msg.step?.thought) {
                setStatusMessage("Thinking...");
            }

            setMessages(prev => {
                const lastMsg = prev[prev.length - 1];
                if (lastMsg && lastMsg.type === "assistant") {
                    return [...prev.slice(0, -1), {
                        ...lastMsg,
                        reasoningTrace: [...(lastMsg.reasoningTrace || []), step]
                    }];
                }
                return prev;
            });
        }

        if (msg.type === "hitl_paused") {
            setPendingApproval({ action_id: msg.action_id, tool: msg.tool, reason: msg.reason });
            setStatusMessage("Waiting for approval...");
        }

        if (msg.type === "hitl_decision") {
            setPendingApproval(null);
            setStatusMessage("Resuming execution...");
        }

        if (msg.type === "streaming:complete" && msg.id === currentStreamId) {
            // Dedupe guard: skip if the REST path already appended the message.
            if (!_restFulfilledRef.current) {
                const agentMsg: ChatMessageData = {
                    id: msg.id,
                    type: "assistant",
                    content: msg.content,
                    timestamp: new Date(),
                    actions: [],
                };
                setMessages(prev => [...prev, agentMsg]);
            }
            setCurrentStreamId(null);
            setIsProcessing(false);
            if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
        }

        // Safety-net: if streaming:complete arrives with a mismatched id (or
        // currentStreamId is null because streaming:start was missed), still
        // reset isProcessing so the spinner never gets permanently stuck.
        if (msg.type === "streaming:complete" && msg.id !== currentStreamId) {
            setIsProcessing(false);
            if (processingTimeoutRef.current) clearTimeout(processingTimeoutRef.current);
        }

        if (msg.type === "streaming:start") {
            setCurrentStreamId(msg.id);
        }
    }, [lastMessage, currentStreamId]);

    return {
        input,
        setInput,
        isProcessing,
        statusMessage,
        messages,
        pendingApproval,
        sessionTitle,
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
