'use client';

import React from 'react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Loader2 } from "lucide-react";
import { ChatMessage, ChatMessageData } from "../GlobalChat/ChatMessage";
import { marked } from "marked";

interface MessageListProps {
    messages: ChatMessageData[];
    currentStreamId: string | null;
    streamingContent: Map<string, string>;
    isProcessing: boolean;
    statusMessage: string;
    messagesEndRef: React.RefObject<HTMLDivElement>;
    handleActionClick: (action: any) => void;
    handleFeedback: (messageId: string, type: 'thumbs_up' | 'thumbs_down', comment?: string) => Promise<void>;
}

export const MessageList: React.FC<MessageListProps> = ({
    messages,
    currentStreamId,
    streamingContent,
    isProcessing,
    statusMessage,
    messagesEndRef,
    handleActionClick,
    handleFeedback,
}) => {
    return (
        <ScrollArea className="flex-1 p-4">
            <div className="space-y-4 max-w-3xl mx-auto">
                {Array.isArray(messages) && messages.map((msg) => (
                    <ChatMessage
                        key={msg.id}
                        message={msg}
                        onActionClick={handleActionClick}
                        onFeedback={handleFeedback}
                    />
                ))}

                {/* Show streaming message */}
                {currentStreamId && streamingContent.get(currentStreamId) && (
                    <div className="flex items-start gap-3 animate-in fade-in slide-in-from-bottom-2">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                            <Loader2 className="h-4 w-4 animate-spin text-primary" />
                        </div>
                        <div className="flex-1 space-y-2 overflow-hidden">
                            <div className="font-semibold text-sm">Atom Assistant</div>
                            <div className="prose dark:prose-invert max-w-none text-sm prose-p:leading-relaxed">
                                <div dangerouslySetInnerHTML={{
                                    __html: marked.parse(streamingContent.get(currentStreamId) || "")
                                }} />
                            </div>
                        </div>
                    </div>
                )}

                {isProcessing && !currentStreamId && (
                    <div className="flex items-center gap-2 text-xs text-muted-foreground ml-2 animate-in fade-in slide-in-from-bottom-2">
                        <Loader2 className="h-3 w-3 animate-spin" />
                        <span>{statusMessage}</span>
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>
        </ScrollArea>
    );
};
