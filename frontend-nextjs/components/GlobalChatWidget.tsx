import React, { useState, useEffect, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { MessageSquare, X, Minimize2, Maximize2, Trash2, AlertCircle } from "lucide-react";
import { ChatInput } from "./GlobalChat/ChatInput";
import { ChatMessage, ChatMessageData, ChatAction, ReasoningStep } from "./GlobalChat/ChatMessage";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import { useWebSocket } from "../hooks/useWebSocket";
import { Badge } from "@/components/ui/badge";

import { useRouter } from 'next/router';

interface GlobalChatWidgetProps {
    userId?: string;
}

export function GlobalChatWidget({ userId = "anonymous" }: GlobalChatWidgetProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<ChatMessageData[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string>("");
    const [pendingApproval, setPendingApproval] = useState<{ action_id: string; tool: string; reason: string } | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const { toast } = useToast();
    const router = useRouter();
    const { isConnected, lastMessage, subscribe } = useWebSocket();

    // Initialize session
    useEffect(() => {
        const welcomeMessage: ChatMessageData = {
            id: "welcome",
            type: "assistant",
            content: 'Hi! I am your Universal ATOM Assistant. 🚀\n\nI can help you with:\n📅 **Calendar**: "Schedule meeting tomorrow"\n📧 **Email**: "Send email to boss"\n⚙️ **Workflows**: "Run Daily Report"\n\nWhat would you like to do?',
            timestamp: new Date(),
        };

        const storedSessionId = localStorage.getItem('atom_chat_session_id');

        if (storedSessionId) {
            setSessionId(storedSessionId);
            loadSessionHistory(storedSessionId, welcomeMessage);
        } else {
            const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            setSessionId(newSessionId);
            localStorage.setItem('atom_chat_session_id', newSessionId);
            setMessages([welcomeMessage]);
        }
    }, []);

    // Scroll to bottom
    useEffect(() => {
        if (isOpen) {
            messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }, [messages, isOpen]);

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

        // Agent step update - append to last assistant message's reasoningTrace
        if (msg.type === "agent_step_update") {
            const step: ReasoningStep = {
                step: msg.step?.step || 1,
                thought: msg.step?.thought,
                action: msg.step?.action,
                observation: msg.step?.output,
                final_answer: msg.step?.final_answer,
            };

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

        // HITL paused
        if (msg.type === "hitl_paused") {
            setPendingApproval({
                action_id: msg.action_id,
                tool: msg.tool,
                reason: msg.reason
            });
            toast({ title: "Approval Required", description: `Action '${msg.tool}' needs your approval.`, variant: "default" });
        }

        // HITL decision made
        if (msg.type === "hitl_decision") {
            setPendingApproval(null);
        }
    }, [lastMessage, toast]);

    const loadSessionHistory = async (sid: string, welcomeMsg: ChatMessageData) => {
        try {
            setIsLoading(true);
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
            const fetchUrl = `${baseUrl}/api/chat/history/${sid}?user_id=${userId || 'default_user'}`;
            console.log('Fetching history from:', fetchUrl);
            const response = await fetch(fetchUrl);

            if (response.ok) {
                try {
                    const data = await response.json();
                    if (data.messages && data.messages.length > 0) {
                        const chatMessages: ChatMessageData[] = data.messages.map((msg: any) => ({
                            id: msg.id || `msg_${Date.now()}_${Math.random()}`,
                            type: msg.role === 'user' ? 'user' : 'assistant',
                            content: msg.content || '',
                            timestamp: new Date(msg.timestamp || Date.now()),
                            // Map any additional metadata if backend provides it
                            actions: [] as ChatAction[],
                        }));
                        setMessages(chatMessages);
                    } else {
                        setMessages([welcomeMsg]);
                    }
                } catch (jsonError) {
                    console.error('Failed to parse history JSON:', jsonError);
                    setMessages([welcomeMsg]);
                }
            } else {
                console.warn(`No history found or failed to load: ${response.status}`);
                setMessages([welcomeMsg]);
            }
        } catch (error) {
            console.error('Failed to load history:', error);
            setMessages([welcomeMsg]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleSendMessage = async (text: string) => {
        const userMessage: ChatMessageData = {
            id: `user_${Date.now()}`,
            type: "user",
            content: text,
            timestamp: new Date(),
        };

        setMessages(prev => [...prev, userMessage]);
        setIsLoading(true);

        try {
            const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
            const response = await fetch(`${baseUrl}/api/chat/message`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    user_id: userId,
                    session_id: sessionId,
                    context: {
                        current_page: router.asPath, // Send current page context
                        conversation_history: messages.slice(-10).map(msg => ({
                            role: msg.type === "user" ? "user" : "assistant",
                            content: msg.content,
                        })),
                    }
                }),
            });

            const data = await response.json();

            if (data.success) {
                const assistantMessage: ChatMessageData = {
                    id: `assistant_${Date.now()}`,
                    type: "assistant", // Backend returns 'message', ensure mapping is handled if keys differ
                    content: data.message, // Backend 'message' field
                    timestamp: new Date(),
                    // Backend returns suggested_actions, map them if needed
                    actions: data.suggested_actions?.map((action: string) => ({ label: action, type: 'suggested' })) || [],
                };
                setMessages(prev => [...prev, assistantMessage]);
            } else {
                throw new Error(data.error || "Failed to process message");
            }
        } catch (error) {
            console.error("Error sending message:", error);
            toast({
                title: "Error",
                description: "Failed to process message. Please try again.",
                variant: "error",
            });
            setMessages(prev => [...prev, {
                id: `error_${Date.now()}`,
                type: "assistant",
                content: "Sorry, I encountered an error. Please try again.",
                timestamp: new Date(),
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const handleActionClick = async (action: ChatAction) => {
        // Handle "Open in Builder" action
        if (action.type === 'open_builder' && action.workflowData) {
            toast({ title: "Opening Builder", description: "Loading your draft..." });
            router.push({
                pathname: '/automation',
                query: { draft: JSON.stringify(action.workflowData) }
            });
            setIsOpen(false);
            return;
        }

        // Handle "View Template" action
        if (action.type === 'view_template' && action.templateId) {
            toast({ title: "Opening Template", description: `Loading template: ${action.templateId}` });
            router.push(`/marketplace?template=${action.templateId}`);
            setIsOpen(false);
            return;
        }

        toast({
            title: "Action Triggered",
            description: `Processing action: ${action.label}`,
        });

        // Implement specific action logic here (execute workflow, etc.)
        // For now, we'll just simulate a response
        if (action.type === 'execute' && action.workflowId) {
            // Call execute API
            try {
                const response = await fetch("/api/atom-agent/execute-generated", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ workflow_id: action.workflowId, input_data: {} }),
                });
                const data = await response.json();
                if (data.success) {
                    toast({ title: "Workflow Started", description: `Execution ID: ${data.execution_id}`, variant: "default" });
                } else {
                    throw new Error(data.error);
                }
            } catch (e) {
                toast({ title: "Execution Failed", description: String(e), variant: "error" });
            }
        }
    };

    const handleNewChat = () => {
        const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        setSessionId(newSessionId);
        localStorage.setItem('atom_chat_session_id', newSessionId);
        setMessages([{
            id: "welcome",
            type: "assistant",
            content: 'Hi! I am your Universal ATOM Assistant. 🚀\n\nNew session started.',
            timestamp: new Date(),
        }]);
        toast({ title: "New Chat", description: "Started a fresh conversation." });
    };

    const handleHITLDecision = async (actionId: string, decision: 'approved' | 'rejected') => {
        try {
            const response = await fetch(`/api/agents/approvals/${actionId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ decision }),
            });
            const data = await response.json();
            if (data.success) {
                toast({ title: `Action ${decision}`, description: `Decision recorded.`, variant: "default" });
                setPendingApproval(null);
            } else {
                throw new Error(data.error || "Failed to submit decision");
            }
        } catch (e) {
            toast({ title: "Error", description: String(e), variant: "error" });
        }
    };

    const handleMessageFeedback = async (messageId: string, type: 'thumbs_up' | 'thumbs_down', comment?: string) => {
        try {
            toast({
                title: comment ? "Correction Received" : (type === 'thumbs_up' ? "Helpful" : "Flagged"),
                description: comment ? "We'll use this to improve." : "Thanks for your feedback!",
            });

            // Send to backend (using the same endpoint but with context identifying it as a message)
            await fetch('/api/reasoning/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: "universal_assistant", // Mapping to global assistant
                    run_id: sessionId,
                    step_index: -1, // -1 indicates final output feedback
                    step_content: { thought: "Final Assistant Output", output: messages.find(m => m.id === messageId)?.content },
                    feedback_type: type,
                    comment: comment
                })
            });
        } catch (e) {
            console.error("Feedback failed", e);
        }
    };

    return (
        <div className="fixed bottom-6 right-6 z-50">
            <Popover open={isOpen} onOpenChange={setIsOpen}>
                <PopoverTrigger asChild>
                    <Button
                        className="h-14 w-14 rounded-full shadow-xl bg-blue-600 hover:bg-blue-700 text-white transition-all duration-300"
                        onClick={() => setIsOpen(true)}
                    >
                        <MessageSquare className="h-6 w-6 text-white" />
                    </Button>
                </PopoverTrigger>
                <PopoverContent
                    className="w-[380px] sm:w-[450px] h-[600px] p-0 mr-4 mb-2 shadow-2xl border-border/50 backdrop-blur-sm"
                    side="top"
                    align="end"
                >
                    <div className="flex flex-col h-full bg-background/95">
                        {/* Header */}
                        <div className="flex items-center justify-between p-4 border-b bg-muted/30">
                            <div className="flex items-center gap-2">
                                <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                                <h3 className="font-semibold text-sm">ATOM Assistant</h3>
                            </div>
                            <div className="flex items-center gap-1">
                                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={handleNewChat} title="New Chat">
                                    <Trash2 className="h-4 w-4 text-muted-foreground" />
                                </Button>
                                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setIsOpen(false)}>
                                    <X className="h-4 w-4 text-muted-foreground" />
                                </Button>
                            </div>
                        </div>

                        {/* Messages */}
                        <div className="flex-1 overflow-y-auto p-4 scrollbar-thin scrollbar-thumb-muted scrollbar-track-transparent">
                            {messages.map(msg => (
                                <ChatMessage
                                    key={msg.id}
                                    message={msg}
                                    onActionClick={handleActionClick}
                                    onFeedback={handleMessageFeedback}
                                />
                            ))}
                            {isLoading && (
                                <div className="flex items-center gap-2 text-xs text-muted-foreground ml-2">
                                    <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                    Thinking...
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* HITL Approval Banner */}
                        {pendingApproval && (
                            <div className="mx-4 mb-2 p-3 border-2 border-yellow-200 rounded-lg bg-yellow-50">
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

                        {/* Input */}
                        <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
                    </div>
                </PopoverContent>
            </Popover>
        </div>
    );
}
