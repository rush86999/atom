'use client';

import React, { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { ChatMessageData, ReasoningStep } from "../GlobalChat/ChatMessage";
import { useWebSocket } from "@/hooks/useWebSocket";
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
        handleSend,
        handleStop,
        handleTitleSave,
        handleFeedback,
        uploadFile,
        toast,
        providerError,
    } = useChatInterface({ sessionId, initialAgentId, onSessionCreated });

    const handleActionClick = (action: any) => {
        console.log("Action clicked:", action);
    };

    // P1.4: clicking an example prompt sends it as a new user message.
    const handleExamplePromptClick = (prompt: string) => {
        setInput(prompt);
        // Defer to next tick so state update lands before send fires.
        setTimeout(() => handleSend(), 0);
    };

    const showEmptyState = messages.length === 0 && !providerError;

    return (
        <div className="flex flex-col h-full bg-background relative">
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
                currentStreamId={null} /* Stream ID handling moved inside useChatInterface */
                streamingContent={streamingContent}
                isProcessing={isProcessing}
                statusMessage={statusMessage}
                messagesEndRef={messagesEndRef}
                handleActionClick={handleActionClick}
                handleFeedback={handleFeedback}
            />

            <ChatInput
                input={input}
                setInput={setInput}
                isProcessing={isProcessing}
                isUploading={isUploading}
                activeAttachments={activeAttachments}
                setActiveAttachments={setActiveAttachments}
                handleSend={handleSend}
                handleStop={handleStop}
                setIsVoiceModeOpen={setIsVoiceModeOpen}
                uploadFile={uploadFile}
                toast={toast}
                messagesCount={messages.length}
            />
        </div>
    );
};

export default ChatInterface;
