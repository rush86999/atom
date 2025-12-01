import React, { useState, useEffect, useRef } from 'react';
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { MessageSquare, X, Minimize2, Maximize2, Trash2 } from "lucide-react";
import { ChatInput } from "./GlobalChat/ChatInput";
import { ChatMessage, ChatMessageData, ChatAction } from "./GlobalChat/ChatMessage";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";

import { useRouter } from 'next/router';

interface GlobalChatWidgetProps {
    userId?: string;
}

export function GlobalChatWidget({ userId = "anonymous" }: GlobalChatWidgetProps) {
    const [isOpen, setIsOpen] = useState(false);
    const [messages, setMessages] = useState<ChatMessageData[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [sessionId, setSessionId] = useState<string>("");
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const { toast } = useToast();
    const router = useRouter();

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

    const loadSessionHistory = async (sid: string, welcomeMsg: ChatMessageData) => {
        try {
            setIsLoading(true);
            const response = await fetch(`/api/atom-agent/sessions/${sid}/history`);
            const data = await response.json();

            if (data.success && data.messages && data.messages.length > 0) {
                const chatMessages: ChatMessageData[] = data.messages.map((msg: any) => ({
                    id: msg.id || `msg_${Date.now()}_${Math.random()}`,
                    type: msg.role === 'user' ? 'user' : 'assistant',
                    content: msg.content || '',
                    timestamp: new Date(msg.timestamp),
                    workflowData: msg.metadata?.workflow_id ? {
                        workflowId: msg.metadata.workflow_id,
                        workflowName: msg.metadata.workflow_name,
                        stepsCount: msg.metadata.steps_count,
                        isScheduled: msg.metadata.is_scheduled,
                    } : undefined,
                    actions: msg.metadata?.actions || [],
                }));
                setMessages(chatMessages);
            } else {
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
            const response = await fetch("/api/atom-agent/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: text,
                    user_id: userId,
                    session_id: sessionId,
                    current_page: router.asPath, // Send current page context
                    conversation_history: messages.slice(-10).map(msg => ({
                        role: msg.type === "user" ? "user" : "assistant",
                        content: msg.content,
                    })),
                }),
            });

            const data = await response.json();

            if (data.success) {
                const assistantMessage: ChatMessageData = {
                    id: `assistant_${Date.now()}`,
                    type: "assistant",
                    content: data.response.message,
                    timestamp: new Date(),
                    workflowData: data.response.workflow_id ? {
                        workflowId: data.response.workflow_id,
                        workflowName: data.response.workflow_name,
                        stepsCount: data.response.steps_count,
                        isScheduled: data.response.is_scheduled,
                        requiresConfirmation: data.response.requires_confirmation,
                    } : undefined,
                    actions: data.response.actions || [],
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
                variant: "destructive",
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
                toast({ title: "Execution Failed", description: String(e), variant: "destructive" });
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

                        {/* Input */}
                        <ChatInput onSendMessage={handleSendMessage} isLoading={isLoading} />
                    </div>
                </PopoverContent>
            </Popover>
        </div>
    );
}
