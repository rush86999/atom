'use client';

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from 'next/router';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, StopCircle, Paperclip, Mic, AlertCircle, Loader2, Edit2, Check, X } from "lucide-react";
import { ChatMessage } from "../GlobalChat/ChatMessage";
import { ChatMessageData, ReasoningStep } from "../GlobalChat/ChatMessage";
import { VoiceInput } from "@/components/Voice/VoiceInput";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useToast } from "@/components/ui/use-toast";
import { useFileUpload } from "../../hooks/useFileUpload";
import { CanvasHost } from "./CanvasHost";
import { VoiceModeOverlay } from "@/components/Voice/VoiceModeOverlay";
import { marked } from "marked";

interface ChatInterfaceProps {
    sessionId: string | null;
    onSessionCreated?: (sessionId: string) => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ sessionId, onSessionCreated }) => {
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
    const { isConnected, lastMessage, streamingContent, subscribe } = useWebSocket();
    const { toast } = useToast();
    const { uploadFile, isUploading } = useFileUpload();
    const [activeAttachments, setActiveAttachments] = useState<any[]>([]); // Store uploaded docs

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    const handleTitleSave = async () => {
        if (!sessionId || !tempTitle.trim()) {
            setIsEditingTitle(false);
            return;
        }

        try {
            const response = await fetch(`/api/chat/sessions/${sessionId}`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: tempTitle, user_id: "default_user" }),
            });
            const data = await response.json();
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

    useEffect(() => {
        // "new" is a sentinel value meaning "start fresh chat" - don't load any existing session
        if (sessionId && sessionId !== "new") {
            initialLoad(sessionId);
        } else {
            // Fresh chat - show welcome message
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

    const initialLoad = (sid: string) => {
        loadSessionHistory(sid);
        // Fetch session details directly
        fetch(`/api/chat/sessions/${sid}?user_id=default_user`)
            .then(res => res.json())
            .then(data => {
                if (data.title) setSessionTitle(data.title);
            }).catch(e => console.log("Bg fetch title error", e));
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages, statusMessage]);

    // WebSocket subscription
    useEffect(() => {
        if (isConnected) {
            subscribe("workspace:default");
        }
    }, [isConnected, subscribe]);

    // Handle WebSocket messages
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

            // Update status message based on step
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

        // Handle streaming completion
        if (msg.type === "streaming:complete" && msg.id === currentStreamId) {
            const agentMsg: ChatMessageData = {
                id: msg.id,
                type: "assistant",
                content: msg.content,
                timestamp: new Date(),
                actions: [],
            };
            setMessages(prev => [...prev, agentMsg]);
            setCurrentStreamId(null);
            setIsProcessing(false);
        }

        // Handle streaming start
        if (msg.type === "streaming:start") {
            setCurrentStreamId(msg.id);
        }
    }, [lastMessage, currentStreamId]);

    const loadSessionHistory = async (sid: string) => {
        try {
            setIsProcessing(true);
            setStatusMessage("Loading history...");
            const { apiClient } = await import('../../lib/api-client');
            // Use correct backend endpoint: /api/chat/history/{session_id}?user_id=...
            const response = await apiClient.get(`/api/chat/history/${sid}?user_id=default_user`) as any;
            if (response.status === 200) {
                const data = response.data;
                // Backend history format: [{ message: string, response: { message: string }, timestamp: string }]
                if (data.messages && Array.isArray(data.messages)) {
                    const chatMessages: ChatMessageData[] = [];

                    data.messages.forEach((historyItem: any, idx: number) => {
                        // Each history item contains user message AND assistant response
                        // Add user message
                        if (historyItem.message) {
                            chatMessages.push({
                                id: `msg_user_${idx}`,
                                type: "user",
                                content: historyItem.message,
                                timestamp: new Date(historyItem.timestamp || Date.now()),
                                actions: [],
                            });
                        }

                        // Add assistant response
                        const assistantContent = historyItem.response?.message || historyItem.response;
                        if (assistantContent && typeof assistantContent === 'string') {
                            chatMessages.push({
                                id: `msg_assistant_${idx}`,
                                type: "assistant",
                                content: assistantContent,
                                timestamp: new Date(historyItem.timestamp || Date.now()),
                                actions: historyItem.response?.suggested_actions || [],
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

                    setMessages(chatMessages);
                }
            }
        } catch (error) {
            console.error("Failed to load history:", error);
        } finally {
            setIsProcessing(false);
        }
    };

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMsg: ChatMessageData = {
            id: Date.now().toString(),
            type: "user",
            content: input,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMsg]);
        setInput("");
        setIsProcessing(true);
        setStatusMessage("Agent is thinking...");

        try {
            const { apiClient } = await import('../../lib/api-client');
            // Use correct backend endpoint /api/chat/message
            const response = await apiClient.post("/api/chat/message", {
                message: input,
                session_id: sessionId,
                user_id: "default_user",
                context: {
                    current_page: "/chat",
                    conversation_history: messages.slice(-5).map(m => ({
                        role: m.type === "user" ? "user" : "assistant",
                        content: m.content
                    })),
                    attachments: activeAttachments // Pass uploaded files to backend
                }
            }) as any;

            // Clear attachments after sending
            setActiveAttachments([]);
            const data = response.data;

            // Response format: { success, message, session_id, intent, metadata, ... }
            if (data.success && data.message) {
                // If backend returned a new session_id, notify parent to update URL/state
                if (data.session_id && data.session_id !== sessionId && data.session_id !== "new") {
                    onSessionCreated?.(data.session_id);
                }

                const agentMsg: ChatMessageData = {
                    id: (Date.now() + 1).toString(),
                    type: "assistant",
                    content: data.message,
                    timestamp: new Date(),
                    actions: data.metadata?.actions || data.suggested_actions || [],
                };
                setMessages(prev => [...prev, agentMsg]);
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
        } finally {
            setIsProcessing(false);
        }
    };

    const handleActionClick = (action: any) => {
        console.log("Action clicked:", action);
        // Hub for global actions like 'execute', 'view', etc.
    };

    const handleFeedback = async (messageId: string, type: 'thumbs_up' | 'thumbs_down', comment?: string) => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            const response = await apiClient.post("/api/atom-agent/feedback", {
                message_id: messageId,
                feedback: type, // frontend uses 'thumbs_up'/'thumbs_down', backend seems to expect 'thumbs_up'/'thumbs_down' based on ReasoningChain.tsx
                comment: comment,
                workspace_id: "default" // Should come from context
            });

            // The apiClient.post (axios) returns the response directly, not just a Fetch response
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

    const handleStop = () => {
        setIsProcessing(false);
        // Add logic to cancel backend request
        const stopMsg: ChatMessageData = {
            id: Date.now().toString(),
            type: "system",
            content: "🚫 Agent execution stopped by user.",
            timestamp: new Date(),
        };
        setMessages(prev => [...prev, stopMsg]);
    };

    const handleHITLDecision = async (actionId: string, decision: 'approved' | 'rejected') => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            const response = await apiClient.post(`/api/agents/approvals/${actionId}`, { decision }) as any;
            const data = response.data;
            if (data.success) {
                toast({ title: `Action ${decision}`, variant: "default" });
                setPendingApproval(null);
            }
        } catch (e) {
            toast({ title: "Error", description: String(e), variant: "error" });
        }
    };

    const [isVoiceModeOpen, setIsVoiceModeOpen] = useState(false);

    return (
        <div className="flex flex-col h-full bg-background relative">
            <VoiceModeOverlay
                isOpen={isVoiceModeOpen}
                onClose={() => setIsVoiceModeOpen(false)}
                onSend={async (text) => {
                    // Simplified logic for upstream port
                    setInput(text);
                    // Use a temporary effect or direct call if refactored
                    // For now, we assume handleSend processes 'input' state if button clicked
                    // Ideally we should refactor handleSend here too, but to be minimal:
                    const originalInput = input;
                    setInput(text);
                    setTimeout(() => handleSend(), 0);
                }}
                isProcessing={isProcessing}
                lastAgentMessage={messages.filter(m => m.type === 'assistant').pop()?.content || null}
            />
            <CanvasHost lastMessage={lastMessage} />
            {/* Chat Header */}
            <div className="p-4 border-b border-border flex justify-between items-center bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div>
                    {isEditingTitle ? (
                        <div className="flex items-center gap-1">
                            <Input
                                value={tempTitle}
                                onChange={(e) => setTempTitle(e.target.value)}
                                className="h-8 w-64"
                                autoFocus
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") handleTitleSave();
                                    if (e.key === "Escape") setIsEditingTitle(false);
                                }}
                            />
                            <Button size="icon" variant="ghost" className="h-8 w-8 text-green-500 hover:text-green-600 hover:bg-green-100/10" onClick={handleTitleSave}>
                                <Check className="h-4 w-4" />
                            </Button>
                            <Button size="icon" variant="ghost" className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-100/10" onClick={() => setIsEditingTitle(false)}>
                                <X className="h-4 w-4" />
                            </Button>
                        </div>
                    ) : (
                        <div className="group flex items-center gap-2">
                            <div>
                                <h2 className="font-semibold">{sessionTitle}</h2>
                                <p className="text-xs text-muted-foreground">ID: {sessionId || "New Session"}</p>
                            </div>
                            <Button
                                size="icon"
                                variant="ghost"
                                className="h-6 w-6 text-primary hover:bg-muted" // Removed opacity, added high contrast
                                onClick={() => {
                                    if (!sessionId) {
                                        toast({ title: "New Session", description: "Send a message to start a session before renaming." });
                                        return;
                                    }
                                    setTempTitle(sessionTitle);
                                    setIsEditingTitle(true);
                                }}
                            >
                                <Edit2 className="h-4 w-4" /> {/* Slightly larger icon */}
                            </Button>
                        </div>
                    )}
                </div>
            </div>

            {/* Messages Area */}
            <ScrollArea className="flex-1 p-4">
                <div className="space-y-4 max-w-3xl mx-auto">
                    {messages.map((msg) => (
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

            {/* HITL Approval Banner */}
            {pendingApproval && (
                <div className="mx-4 mb-2 p-3 border-2 border-yellow-200 rounded-lg bg-yellow-50 animate-in slide-in-from-bottom-5">
                    <div className="flex items-center gap-2 text-yellow-800 font-medium text-sm mb-2">
                        <AlertCircle className="h-4 w-4" />
                        Approval Required
                    </div>
                    <p className="text-xs text-yellow-700 mb-2">
                        <strong>Action:</strong> {pendingApproval.tool}<br />
                        <strong>Reason:</strong> {pendingApproval.reason}
                    </p>
                    <div className="flex gap-2">
                        <Button size="sm" onClick={() => handleHITLDecision(pendingApproval.action_id, 'approved')}>
                            Approve
                        </Button>
                        <Button size="sm" variant="destructive" onClick={() => handleHITLDecision(pendingApproval.action_id, 'rejected')}>
                            Reject
                        </Button>
                    </div>
                </div>
            )}

            {/* Input Area */}
            <div className="p-4 border-t border-border bg-background">
                <div className="max-w-3xl mx-auto flex flex-col gap-2">
                    {isUploading && (
                        <div className="flex items-center gap-2 mb-2 p-2 bg-muted rounded-md animate-in fade-in">
                            <Loader2 className="h-4 w-4 animate-spin text-primary" />
                            <span className="text-xs font-medium">Uploading file...</span>
                        </div>
                    )}

                    {/* Attachment Chips */}
                    {activeAttachments.length > 0 && (
                        <div className="flex flex-wrap gap-2 mb-2 animate-in fade-in slide-in-from-bottom-2">
                            {activeAttachments.map((doc, idx) => (
                                <div key={doc.id || idx} className="flex items-center gap-1 bg-secondary text-secondary-foreground px-3 py-1 rounded-full text-xs border border-border">
                                    <Paperclip className="h-3 w-3" />
                                    <span className="max-w-[150px] truncate">{doc.title || "File"}</span>
                                    <button
                                        onClick={() => setActiveAttachments(prev => prev.filter((_, i) => i !== idx))}
                                        className="ml-1 hover:text-destructive"
                                    >
                                        <X className="h-3 w-3" />
                                    </button>
                                </div>
                            ))}
                        </div>
                    )}

                    <div className="flex gap-2">
                        <input
                            type="file"
                            id="chat-file-upload"
                            className="hidden"
                            onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) {
                                    uploadFile(file).then((doc) => {
                                        if (doc) {
                                            setActiveAttachments(prev => [...prev, doc]);
                                            toast({ title: "File Uploaded", description: file.name, variant: "default" });
                                        }
                                    });
                                }
                            }}
                        />
                        <Button
                            variant="ghost"
                            size="icon"
                            className="shrink-0"
                            onClick={() => document.getElementById('chat-file-upload')?.click()}
                            disabled={isUploading || isProcessing}
                        >
                            <Paperclip className="h-5 w-5 text-muted-foreground" />
                        </Button>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="shrink-0"
                            onClick={() => setIsVoiceModeOpen(true)}
                            title="Voice Mode"
                        >
                            <Mic className="h-5 w-5 text-muted-foreground" />
                        </Button>
                        <Input
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                            placeholder="Type a message..."
                            className="flex-1"
                            disabled={isProcessing}
                        />
                        {isProcessing ? (
                            <Button variant="destructive" size="icon" onClick={handleStop} title="Stop Agent">
                                <StopCircle className="h-5 w-5" />
                            </Button>
                        ) : (
                            <Button onClick={handleSend} size="icon">
                                <Send className="h-5 w-5" />
                            </Button>
                        )}
                    </div>
                </div>
                <div className="text-center mt-2">
                    <p className="text-[10px] text-muted-foreground">
                        AI can make mistakes. Please review generated code and plans.
                    </p>
                </div>
            </div>
        </div>
    );
};

export default ChatInterface;
