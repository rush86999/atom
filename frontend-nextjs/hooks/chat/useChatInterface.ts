'use client';

import { useState, useRef, useEffect, useCallback } from "react";
import { ChatMessageData, ReasoningStep } from "@/components/GlobalChat/ChatMessage";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useToast } from "@/components/ui/use-toast";
import { useFileUpload } from "@/hooks/useFileUpload";

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

    const { isConnected, lastMessage, streamingContent, subscribe } = useWebSocket();
    const { toast } = useToast();
    const { uploadFile, isUploading } = useFileUpload();

    const [activeAttachments, setActiveAttachments] = useState<any[]>([]);
    const [isVoiceModeOpen, setIsVoiceModeOpen] = useState(false);

    const scrollToBottom = useCallback(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, []);

    const loadSessionHistory = async (sid: string) => {
        try {
            setIsProcessing(true);
            setStatusMessage("Loading history...");
            const { apiClient } = await import('../../lib/api-client');
            const response = await apiClient.get(`/api/chat/history/${sid}?user_id=default_user`) as any;
            if (response.status === 200) {
                const data = response.data;
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

                    setMessages(chatMessages);
                }
            }
        } catch (error) {
            console.error("Failed to load history:", error);
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

    const handleSend = async () => {
        if (!input.trim()) return;

        const userMsg: ChatMessageData = {
            id: Date.now().toString(),
            type: "user",
            content: input,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMsg]);
        const currentInput = input;
        setInput("");
        setIsProcessing(true);
        setStatusMessage("Agent is thinking...");

        try {
            const { apiClient } = await import('../../lib/api-client');
            const response = await apiClient.post("/api/chat/message", {
                message: currentInput,
                session_id: sessionId,
                user_id: "default_user",
                context: {
                    current_page: "/chat",
                    agent_id: initialAgentId,
                    conversation_history: messages.slice(-5).map(m => ({
                        role: m.type === "user" ? "user" : "assistant",
                        content: m.content
                    })),
                    attachments: activeAttachments
                }
            }) as any;

            setActiveAttachments([]);
            const data = response.data;

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

    const handleFeedback = async (messageId: string, type: 'thumbs_up' | 'thumbs_down', comment?: string) => {
        try {
            const { apiClient } = await import('../../lib/api-client');
            const response = await apiClient.post("/api/atom-agent/feedback", {
                message_id: messageId,
                feedback: type,
                comment: comment,
                workspace_id: "default"
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

    const handleStop = () => {
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
            loadSessionHistory(sessionId);
            fetch(`/api/chat/sessions/${sessionId}?user_id=default_user`)
                .then(res => res.json())
                .then(data => {
                    if (data.title) setSessionTitle(data.title);
                }).catch(e => console.log("Bg fetch title error", e));
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
        handleSend,
        handleStop,
        handleTitleSave,
        handleFeedback,
        uploadFile,
        toast
    };
};
