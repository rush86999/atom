'use client';

import React, { useState, useRef, useEffect } from "react";
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
        toast
    } = useChatInterface({ sessionId, initialAgentId, onSessionCreated });

    const handleActionClick = (action: any) => {
        console.log("Action clicked:", action);
    };

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
