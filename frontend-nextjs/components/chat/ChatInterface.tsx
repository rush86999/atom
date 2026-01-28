'use client';

import React, { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Send, StopCircle, Paperclip, AlertCircle, Loader2 } from "lucide-react";
import { ChatMessage } from "../GlobalChat/ChatMessage";
import { ChatMessageData, ReasoningStep } from "../GlobalChat/ChatMessage";
import { VoiceInput } from "@/components/Voice/VoiceInput";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useToast } from "@/components/ui/use-toast";
import { useFileUpload } from "../../hooks/useFileUpload";

interface ChatInterfaceProps {
    sessionId: string | null;
    onSessionCreated?: (sessionId: string) => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ sessionId }) => {
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [statusMessage, setStatusMessage] = useState("Agent is thinking...");
    const [messages, setMessages] = useState<ChatMessageData[]>([]);
    const [pendingApproval, setPendingApproval] = useState<{ action_id: string; tool: string; reason: string } | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const { isConnected, lastMessage, subscribe } = useWebSocket();
    const { toast } = useToast();
    const { uploadFile, isUploading } = useFileUpload();

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        if (sessionId) {
            loadSessionHistory(sessionId);
        } else {
            setMessages([
                {
                    id: "welcome",
                    type: "assistant",
                    content: "Hello! I'm your Atom Assistant. How can I help you today?",
                    timestamp: new Date(),
                }
            ]);
        }
    }, [sessionId]);

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
    }, [lastMessage]);

    const loadSessionHistory = async (sid: string) => {
        try {
            setIsProcessing(true);
            setStatusMessage("Loading history...");
            const { apiClient } = await import('../../lib/api-client');
            const response = await apiClient.get(`/api/atom-agent/sessions/${sid}/history`) as any;
            if (response.status === 200) {
                const data = response.data;
                if (data.success && data.messages) {
                    const chatMessages: ChatMessageData[] = data.messages.map((msg: any) => ({
                        id: msg.id || `msg_${Date.now()}_${Math.random()}`,
                        type: msg.role === 'user' ? 'user' : 'assistant',
                        content: msg.content || '',
                        timestamp: new Date(msg.timestamp),
                        actions: msg.metadata?.actions || [],
                    }));
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
            const response = await apiClient.post("/api/atom-agent/chat", {
                message: input,
                session_id: sessionId,
                user_id: "default_user",
                current_page: "/chat",
                conversation_history: messages.slice(-5).map(m => ({
                    role: m.type === "user" ? "user" : "assistant",
                    content: m.content
                }))
            }) as any;
            const data = response.data;

            if (data.success && data.response) {
                const agentMsg: ChatMessageData = {
                    id: (Date.now() + 1).toString(),
                    type: "assistant",
                    content: data.response.message,
                    timestamp: new Date(),
                    actions: data.response.actions || [],
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

    return (
        <div className="flex flex-col h-full bg-background">
            {/* Chat Header */}
            <div className="p-4 border-b border-border flex justify-between items-center bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <div>
                    <h2 className="font-semibold">Current Session</h2>
                    <p className="text-xs text-muted-foreground">ID: {sessionId || "New Session"}</p>
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
                    {isProcessing && (
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

                    <div className="flex gap-2">
                        <input
                            type="file"
                            id="chat-file-upload"
                            className="hidden"
                            onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) uploadFile(file);
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
                        <VoiceInput
                            onTranscriptChange={(transcript) => setInput(transcript)}
                            className="shrink-0"
                        />
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
