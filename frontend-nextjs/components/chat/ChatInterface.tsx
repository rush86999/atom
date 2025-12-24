import React, { useState, useRef, useEffect } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { ScrollArea } from "../ui/scroll-area";
import { Send, StopCircle, Paperclip, Mic } from "lucide-react";
import { ChatMessage } from "../GlobalChat/ChatMessage"; // Reuse existing message component
import { ChatMessageData } from "../GlobalChat/ChatMessage";

interface ChatInterfaceProps {
    sessionId: string | null;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ sessionId }) => {
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [messages, setMessages] = useState<ChatMessageData[]>([]);
    const messagesEndRef = useRef<HTMLDivElement>(null);

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
    }, [messages]);

    const loadSessionHistory = async (sid: string) => {
        try {
            setIsProcessing(true);
            const response = await fetch(`/api/atom-agent/sessions/${sid}/history`);
            if (response.ok) {
                const data = await response.json();
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

        try {
            const response = await fetch("/api/atom-agent/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: input,
                    session_id: sessionId,
                    user_id: "default_user",
                    current_page: "/chat",
                    conversation_history: messages.slice(-5).map(m => ({
                        role: m.type === "user" ? "user" : "assistant",
                        content: m.content
                    }))
                })
            });

            const data = await response.json();

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
                        />
                    ))}
                    {isProcessing && (
                        <div className="flex items-center gap-2 text-xs text-muted-foreground ml-2">
                            <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                            <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                            <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                            Agent is thinking...
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </ScrollArea>

            {/* Input Area */}
            <div className="p-4 border-t border-border bg-background">
                <div className="max-w-3xl mx-auto flex gap-2">
                    <Button variant="ghost" size="icon" className="shrink-0">
                        <Paperclip className="h-5 w-5 text-muted-foreground" />
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
