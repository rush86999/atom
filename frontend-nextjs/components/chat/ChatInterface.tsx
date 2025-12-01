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
    const [messages, setMessages] = useState<ChatMessageData[]>([
        {
            id: "welcome",
            type: "assistant",
            content: "Hello! I'm your Atom Assistant. How can I help you today?",
            timestamp: new Date(),
        }
    ]);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

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

        // Simulate agent processing
        setTimeout(() => {
            const agentMsg: ChatMessageData = {
                id: (Date.now() + 1).toString(),
                type: "assistant",
                content: "I'm processing your request. I'll update the workspace on the right with my plan.",
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, agentMsg]);
            setIsProcessing(false);
        }, 1500);
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
                        <ChatMessage key={msg.id} message={msg} />
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
