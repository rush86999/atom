'use client';

import React from 'react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2 } from "lucide-react";
import { ChatMessage, ChatMessageData } from "../GlobalChat/ChatMessage";
import ChatMarkdown from "@/components/canvas/ChatMarkdown";
import { AGENT_CHAT } from "@/src/lib/testIds";

interface BackgroundRunState {
    continuationId?: string;
    executionId?: string;
    since: number;
}

interface MessageListProps {
    messages: ChatMessageData[];
    currentStreamId: string | null;
    streamingContent: Map<string, string>;
    isProcessing: boolean;
    statusMessage: string;
    backgroundRun?: BackgroundRunState | null;
    messagesEndRef: React.RefObject<HTMLDivElement>;
    handleActionClick: (action: any) => void;
    handleFeedback: (messageId: string, type: 'thumbs_up' | 'thumbs_down', comment?: string) => Promise<void>;
    handleRegenerate?: (messageId: string) => void;
    handleForkFromHere?: (messageId: string) => void;
    handleOpenInCanvas?: (message: ChatMessageData) => void;
}


// BACKGROUND-RUN INDICATOR (2026-09-29): bound to a forked background
// run (e.g. a canvas edit that replied "still running"). Spins while
// fresh; after the stale window it stops animating and states the
// honest expectation (a notification will arrive) — never an eternal
// spinner, never a fake completion. Cleared by the terminal
// `chat_continuation` WS event.
const BACKGROUND_RUN_STALE_MS = 180000;

const BackgroundRunChip: React.FC<{ run: BackgroundRunState }> = ({ run }) => {
    const [now, setNow] = React.useState(Date.now());
    React.useEffect(() => {
        const t = setInterval(() => setNow(Date.now()), 15000);
        return () => clearInterval(t);
    }, []);
    const stale = now - run.since > BACKGROUND_RUN_STALE_MS;
    return (
        <div
            className="flex items-center gap-2 text-xs text-muted-foreground ml-2 animate-in fade-in slide-in-from-bottom-2"
            data-testid="background-run-indicator"
            aria-live="polite"
        >
            {!stale && <Loader2 className="h-3 w-3 animate-spin text-primary" />}
            <span>
                {stale
                    ? "Still running in the background — you'll get a notification when it finishes."
                    : "Working in the background — this can take a couple of minutes…"}
            </span>
        </div>
    );
};

export const MessageList: React.FC<MessageListProps> = ({
    messages,
    currentStreamId,
    streamingContent,
    isProcessing,
    statusMessage,
    backgroundRun,
    messagesEndRef,
    handleActionClick,
    handleFeedback,
    handleRegenerate,
    handleForkFromHere,
    handleOpenInCanvas,
}) => {
    return (
        <ScrollArea className="flex-1 p-4" data-testid="message-list">
            <div className="space-y-4 max-w-3xl mx-auto">
                {Array.isArray(messages) && messages.map((msg) => (
                    <ChatMessage
                        key={msg.id}
                        message={msg}
                        onActionClick={handleActionClick}
                        onFeedback={handleFeedback}
                        onRegenerate={handleRegenerate}
                        onFork={handleForkFromHere}
                        onOpenInCanvas={handleOpenInCanvas}
                    />
                ))}

                {/* Show streaming message */}
                {currentStreamId && streamingContent.get(currentStreamId) && (
                    <div
                        className="flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2"
                        data-testid={AGENT_CHAT.STREAMING_INDICATOR}
                        aria-live="polite"
                    >
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                            <Loader2 className="h-4 w-4 animate-spin text-primary" />
                        </div>
                        <div className="flex-1 space-y-2 overflow-hidden">
                            <div className="font-semibold text-sm">Atom Assistant</div>
                            <ChatMarkdown content={streamingContent.get(currentStreamId) || ""} />
                        </div>
                    </div>
                )}

                {isProcessing && !currentStreamId && (
                    <div
                        className="flex items-center gap-2 text-xs text-muted-foreground ml-2 animate-in fade-in slide-in-from-bottom-2"
                        data-testid={AGENT_CHAT.STREAMING_INDICATOR}
                        aria-live="polite"
                    >
                        <Loader2 className="h-3 w-3 animate-spin" />
                        <span>{statusMessage}</span>
                    </div>
                )}
                {backgroundRun && <BackgroundRunChip run={backgroundRun} />}
                <div ref={messagesEndRef} />
            </div>
        </ScrollArea>
    );
};
