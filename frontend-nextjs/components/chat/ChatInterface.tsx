'use client';

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { ChatMessageData, ReasoningStep } from "../GlobalChat/ChatMessage";
import { useWebSocket } from "@/hooks/useWebSocket";
import { CanvasTypePicker } from "./CanvasTypePicker";
import { useToast } from "@/components/ui/use-toast";
import { useFileUpload } from "../../hooks/useFileUpload";
import { VoiceModeOverlay } from "@/components/Voice/VoiceModeOverlay";
import { ChatHeader } from "./ChatHeader";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { useChatInterface } from "../../hooks/chat/useChatInterface";

interface ChatInterfaceProps {
    sessionId: string | null;
    onSessionCreated?: (sessionId: string) => void;
    initialAgentId?: string | null;
}

// P1.4: clickable example prompts shown in the empty state so a brand-new
// user has an obvious first message to send. Clicking one drops it into the
// input box and sends immediately via the existing handleSend path.
const EXAMPLE_PROMPTS = [
    "Summarize the benefits of multi-agent governance",
    "Show me a sample sales chart",
    "Draft a welcome email for new customers",
    "What can you help me automate?",
];

const ChatInterface: React.FC<ChatInterfaceProps> = ({ sessionId, onSessionCreated, initialAgentId }) => {
    const {
        input,
        setInput,
        isProcessing,
        statusMessage,
        messages,
        chatAgent,
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
        pendingImages,
        setPendingImages,
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
    } = useChatInterface({ sessionId, initialAgentId, onSessionCreated });

    // Suggested actions (UI gap #12, revised Aug 30): an action with a URL
    // navigates; a text suggestion PREFILLS the input instead of auto-
    // sending. Auto-sending made it look like the app spoke in the user's
    // voice ("Add a deadline" started a deadline conversation out of
    // nowhere) — prefill keeps the chip one keystroke away without the
    // surprise, and lets the user edit before sending.
    const handleActionClick = (action: any) => {
        if (!action) return;
        const text = typeof action === "string" ? action : (action.label || action.text || action.action);
        if (typeof action === "object" && action.url) {
            window.location.href = action.url;
            return;
        }
        if (text) {
            setInput(String(text));
        }
    };

    // P1.4: clicking an example prompt sends it as a new user message.
    const handleExamplePromptClick = (prompt: string) => {
        // Pass the prompt directly to handleSend — using setInput + setTimeout
        // races the stale input closure (setState is async, so handleSend()
        // reads the old empty value and no-ops).
        handleSend(prompt);
    };

    const showEmptyState = messages.length === 0 && !providerError;

    // Fork from here: copy the conversation up to (and including) the chosen
    // reply into a brand-new session and jump into it. Only history-loaded
    // messages carry the durable backend id the fork endpoint needs — live
    // messages use timestamp ids the backend can't resolve (a reload mints
    // real ids), so those get an explanatory toast instead of a failed call.
    const [forkingMessageId, setForkingMessageId] = React.useState<string | null>(null);
    const handleForkFromHere = async (messageId: string) => {
        if (!sessionId || sessionId === "new" || forkingMessageId) return;
        if (/^\d+$/.test(messageId)) {
            toast({
                title: "Can't fork this message yet",
                description: "Reload the conversation, then fork from an earlier reply.",
                variant: "warning",
            });
            return;
        }
        setForkingMessageId(messageId);
        try {
            const { apiClient } = await import("../../lib/api-client");
            const res = await apiClient.post(
                `/api/chat/sessions/${sessionId}/fork`,
                { up_to_message_id: messageId },
                { timeout: 15000 }
            );
            const data = res?.data;
            if (data?.success && data.session_id) {
                toast({
                    title: "Forked",
                    description: `New chat with ${data.messages_copied} messages copied.`,
                });
                onSessionCreated?.(data.session_id);
            } else {
                toast({
                    title: "Fork failed",
                    description: data?.error || "Could not fork this conversation.",
                    variant: "warning",
                });
            }
        } catch (error: any) {
            console.error("Error forking from message:", error);
            toast({
                title: "Fork failed",
                description: error?.response?.data?.detail || "Could not fork this conversation.",
                variant: "warning",
            });
        } finally {
            setForkingMessageId(null);
        }
    };

    // Expand the latest assistant draft into a co-editable canvas
    const [openingCanvas, setOpeningCanvas] = React.useState(false);
    // Canvas type for the draft: auto lets the backend classifier decide
    // (best match); the list is recommended-first — document and email lead,
    // the other canvas apps follow for when the owner disagrees.
    const [canvasTypeChoice, setCanvasTypeChoice] = React.useState<string>("auto");
    const lastAssistant = [...messages].reverse().find((m) => m.type === "assistant" && m.content?.trim());
    // Recent assistant messages, newest-first, WITH ids: the backend picks
    // the most recent DRAFT-SHAPED one (an answer that merely embeds a code
    // snippet or a small table no longer qualifies) and echoes the picked
    // id, so a fallback to an earlier reply is surfaced instead of silently
    // converting the wrong message.
    const draftCandidates = [...messages]
        .reverse()
        .filter((m) => m.type === "assistant" && m.content?.trim())
        .slice(0, 10)
        .map((m) => ({ id: m.id, content: m.content }));

    const createCanvasFromMessage = async (content: string, candidates: Array<{ id: string; content: string }>) => {
        const { apiClient } = await import("../../lib/api-client");
        const res = await apiClient.post("/api/chat/to-canvas", {
            content,
            candidates,
            title: `Draft — ${String(content).slice(0, 60)}`,
            session_id: sessionId,
            agent_id: initialAgentId,
            ...(canvasTypeChoice !== "auto" ? { canvas_type: canvasTypeChoice } : {}),
        }, { timeout: 30000 });
        return res.data;
    };

    const openCanvasFromData = (data: any, clickedMessageId?: string) => {
        if (data?.warning) {
            toast({ title: "Canvas type adjusted", description: data.warning });
        }
        // Transparency: when the draft scan picked an EARLIER reply than the
        // one the click was on, say so — conversion must never look like it
        // grabbed the wrong text. The toast gets a beat to read before the
        // navigation lands on the canvas.
        const fellBack = Boolean(
            clickedMessageId && data?.selected_message_id && data.selected_message_id !== clickedMessageId
        );
        if (fellBack) {
            toast({
                title: "Opened an earlier reply",
                description: "The latest message wasn't a draft, so the most recent draft-shaped reply was opened instead.",
            });
        }
        if (data?.url) {
            if (fellBack) {
                setTimeout(() => { window.location.href = data.url; }, 1200);
            } else {
                window.location.href = data.url;
            }
        }
    };

    const openInCanvas = async () => {
        if (!lastAssistant || openingCanvas) return;
        setOpeningCanvas(true);
        try {
            const data = await createCanvasFromMessage(lastAssistant.content, draftCandidates);
            openCanvasFromData(data, lastAssistant.id);
        } catch {
            // Same contract as openMessageInCanvas: failures are surfaced,
            // never swallowed.
            toast({
                title: "Couldn't open the canvas",
                description: "The backend didn't respond in time — it may be busy. Please try again in a moment.",
                variant: "destructive",
            });
        } finally {
            setOpeningCanvas(false);
        }
    };

    // Deterministic per-message conversion: the user picked the reply, so a
    // single-candidate window lets the classifier type it (email / code /
    // office shape) but can never re-select a different message from
    // history — the canvas is exactly the message the button was on.
    const openMessageInCanvas = async (message: ChatMessageData) => {
        if (openingCanvas || !message.content?.trim()) return;
        setOpeningCanvas(true);
        try {
            const data = await createCanvasFromMessage(
                message.content,
                [{ id: message.id, content: message.content }],
            );
            openCanvasFromData(data, message.id);
        } catch {
            // Never silent: an empty catch turned a backend outage into a
            // button that "does nothing" (2026-09-06 — to-canvas timed out
            // while the backend's event loop was saturated and the user had
            // no idea why). Say what happened.
            toast({
                title: "Couldn't open the canvas",
                description: "The backend didn't respond in time — it may be busy. Please try again in a moment.",
                variant: "destructive",
            });
        } finally {
            setOpeningCanvas(false);
        }
    };

    return (
        <div className="flex flex-col h-full bg-background relative" data-testid="chat-container">
            <VoiceModeOverlay
                isOpen={isVoiceModeOpen}
                onClose={() => setIsVoiceModeOpen(false)}
                onSend={async (text) => {
                    setInput(text);
                    // Small delay to ensure state update before send
                    setTimeout(() => handleSend(), 0);
                }}
                isProcessing={isProcessing}
                lastAgentMessage={messages.filter(m => m.type === 'assistant').pop()?.content || null}
            />

            <ChatHeader
                sessionTitle={sessionTitle}
                sessionId={sessionId}
                isEditingTitle={isEditingTitle}
                tempTitle={tempTitle}
                setTempTitle={setTempTitle}
                setIsEditingTitle={setIsEditingTitle}
                handleTitleSave={handleTitleSave}
                onRenameClick={() => {
                    if (!sessionId) {
                        toast({ title: "New Session", description: "Send a message before renaming." });
                        return;
                    }
                    setTempTitle(sessionTitle);
                    setIsEditingTitle(true);
                }}
            />

            {/* Who you're talking to: when the chat is scoped to a hire
                (?agent_id=…), always show its identity and maturity tier so
                the generic sidebar/title never leaves that ambiguous. */}
            {chatAgent && (
                <div
                    data-testid="chat-agent-identity"
                    className="mx-4 mt-2 flex items-center gap-2 rounded-md border border-purple-200 bg-purple-50 dark:bg-purple-950/30 dark:border-purple-800 px-3 py-1.5 text-sm"
                >
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-purple-600 text-white text-xs font-semibold">
                        {chatAgent.name.charAt(0).toUpperCase()}
                    </span>
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                        {chatAgent.name}
                    </span>
                    {chatAgent.category && (
                        <span className="text-xs text-muted-foreground">{chatAgent.category}</span>
                    )}
                    {chatAgent.status && (
                        <span
                            data-testid="chat-agent-tier"
                            className="ml-auto rounded-full px-2 py-0.5 text-xs font-medium border bg-amber-100 text-amber-800 border-amber-300 capitalize"
                        >
                            {chatAgent.status}
                        </span>
                    )}
                </div>
            )}

            {/* P1.1: actionable recovery banner when no LLM provider is configured. */}
            {providerError && (
                <div className="mx-4 mt-2 rounded-md border border-amber-300 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-800 p-3 text-sm">
                    <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                            <p className="font-medium text-amber-900 dark:text-amber-200">
                                {providerError.message}
                            </p>
                            <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                                Add an API key or enable local Ollama to start chatting.
                            </p>
                        </div>
                        <Link
                            href={providerError.recovery_url}
                            className="shrink-0 inline-flex items-center rounded-md bg-amber-600 hover:bg-amber-700 text-white px-3 py-1.5 text-xs font-medium"
                        >
                            Configure now →
                        </Link>
                    </div>
                </div>
            )}

            {/* P1.4: empty-state example prompts above the message list. */}
            {showEmptyState && (
                <div className="mx-4 my-3 rounded-lg border border-dashed border-gray-200 dark:border-gray-800 p-4">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground mb-3">
                        Try one of these
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {EXAMPLE_PROMPTS.map((prompt) => (
                            <button
                                key={prompt}
                                type="button"
                                onClick={() => handleExamplePromptClick(prompt)}
                                className="text-left text-sm rounded-md border border-gray-200 dark:border-gray-800 hover:border-purple-400 hover:bg-purple-50 dark:hover:bg-purple-950/30 px-3 py-2 transition-colors"
                            >
                                {prompt}
                            </button>
                        ))}
                    </div>
                </div>
            )}

            <MessageList
                messages={messages}
                currentStreamId={currentStreamId}
                streamingContent={streamingContent}
                isProcessing={isProcessing}
                statusMessage={statusMessage}
                messagesEndRef={messagesEndRef}
                handleActionClick={handleActionClick}
                handleFeedback={handleFeedback}
                handleRegenerate={handleRegenerate}
                handleForkFromHere={handleForkFromHere}
                handleOpenInCanvas={openMessageInCanvas}
            />

            <ChatInput
                input={input}
                setInput={setInput}
                isProcessing={isProcessing}
                isUploading={isUploading}
                pendingImages={pendingImages}
                setPendingImages={setPendingImages}
                activeAttachments={activeAttachments}
                setActiveAttachments={setActiveAttachments}
                // useChatInterface's handleSend resolves to a success boolean that
                // ChatInput ignores; adapt to ChatInput's Promise<void> prop type.
                handleSend={handleSend as unknown as (overrideText?: string, images?: string[]) => Promise<void>}
                handleStop={handleStop}
                setIsVoiceModeOpen={setIsVoiceModeOpen}
                uploadFile={uploadFile}
                toast={toast}
                messagesCount={messages.length}
            />

            {/* Expand the latest draft into a co-editable canvas (training surface) */}
            {lastAssistant && !isProcessing && (
                <div className="mx-4 mb-2 flex justify-end items-center gap-1.5">
                    <CanvasTypePicker
                        value={canvasTypeChoice}
                        onChange={setCanvasTypeChoice}
                        disabled={openingCanvas}
                    />
                    <button
                        onClick={openInCanvas}
                        disabled={openingCanvas}
                        className="px-3 py-1.5 rounded-lg border border-sky-500 text-sky-400 hover:bg-sky-950/40 text-xs font-medium disabled:opacity-50"
                    >
                        {openingCanvas ? "Opening…" : "Open latest draft in canvas"}
                    </button>
                </div>
            )}
        </div>
    );
};

export default ChatInterface;
