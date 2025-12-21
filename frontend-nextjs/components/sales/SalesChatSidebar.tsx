import React, { useState, useRef, useEffect } from "react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { ScrollArea } from "../ui/scroll-area";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { Send, MessageSquare, ChevronRight, ChevronLeft, Bot, User, Sparkles } from "lucide-react";
import { ChatMessage, ChatMessageData } from "../GlobalChat/ChatMessage";
import { cn } from "../../lib/utils";

interface SalesChatSidebarProps {
    workspaceId: string;
}

const SalesChatSidebar: React.FC<SalesChatSidebarProps> = ({ workspaceId }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [input, setInput] = useState("");
    const [isProcessing, setIsProcessing] = useState(false);
    const [messages, setMessages] = useState<ChatMessageData[]>([
        {
            id: "sales-welcome",
            type: "assistant",
            content: "Hi! I'm your Sales Assistant. Ask me about your pipeline health, lead scores, or follow-up tasks.",
            timestamp: new Date(),
        }
    ]);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        if (isOpen) {
            scrollToBottom();
        }
    }, [messages, isOpen]);

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
                    user_id: "anonymous_sales_user",
                    workspace_id: workspaceId,
                })
            });

            const data = await response.json();

            if (data.success && data.response) {
                const assistantMsg: ChatMessageData = {
                    id: (Date.now() + 1).toString(),
                    type: "assistant",
                    content: data.response.message || "I've processed your request.",
                    timestamp: new Date(),
                    actions: data.response.actions || [],
                };
                setMessages(prev => [...prev, assistantMsg]);
            } else {
                throw new Error(data.error || "Failed to process message");
            }
        } catch (error) {
            console.error("Sales chat error:", error);
            const errorMsg: ChatMessageData = {
                id: "error",
                type: "system",
                content: "Error connecting to AI. Please try again.",
                timestamp: new Date(),
            };
            setMessages(prev => [...prev, errorMsg]);
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div
            className={cn(
                "fixed right-0 top-16 bottom-0 z-40 transition-all duration-300 ease-in-out border-l bg-background shadow-xl flex flex-col",
                isOpen ? "w-80 md:w-96" : "w-12"
            )}
        >
            {/* Toggle Button */}
            <Button
                variant="ghost"
                size="icon"
                onClick={() => setIsOpen(!isOpen)}
                className="absolute left-[-20px] top-4 h-10 w-10 rounded-full border bg-background shadow-md z-50 hover:bg-muted"
            >
                {isOpen ? <ChevronRight className="h-5 w-5" /> : <ChevronLeft className="h-5 w-5" />}
            </Button>

            {/* Header */}
            <div className={cn("p-4 border-b flex items-center gap-3 bg-muted/30", !isOpen && "items-center justify-center")}>
                <div className="bg-primary/10 p-2 rounded-lg">
                    <Bot className="h-5 w-5 text-primary" />
                </div>
                {isOpen && (
                    <div>
                        <h3 className="font-semibold text-sm">Sales Assistant</h3>
                        <div className="flex items-center gap-1 text-[10px] text-green-500 font-medium uppercase tracking-wider">
                            <Sparkles className="h-2 w-2" /> Online
                        </div>
                    </div>
                )}
            </div>

            {isOpen ? (
                <>
                    {/* Chat Messages */}
                    <ScrollArea className="flex-1 p-4">
                        <div className="space-y-4">
                            {messages.map((msg) => (
                                <ChatMessage
                                    key={msg.id}
                                    message={msg}
                                    onActionClick={(action) => console.log("Action click in sales sidebar:", action)}
                                />
                            ))}
                            {isProcessing && (
                                <div className="flex items-center gap-2 text-xs text-muted-foreground ml-2">
                                    <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce" />
                                    <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce delay-75" />
                                    <div className="h-2 w-2 bg-primary/50 rounded-full animate-bounce delay-150" />
                                    Analyzing pipeline...
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                    </ScrollArea>

                    {/* Input */}
                    <div className="p-4 border-t bg-muted/10">
                        <div className="flex gap-2">
                            <Input
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={(e) => e.key === "Enter" && handleSend()}
                                placeholder="Ask Sales Assistant..."
                                className="text-xs h-9"
                            />
                            <Button size="sm" onClick={handleSend} disabled={isProcessing}>
                                <Send className="h-4 w-4" />
                            </Button>
                        </div>
                        <p className="text-[9px] text-muted-foreground mt-2 text-center italic">
                            Try: "How's my weighted pipeline?" or "At-risk deals?"
                        </p>
                    </div>
                </>
            ) : (
                <div className="flex flex-col items-center pt-8 gap-4 overflow-hidden">
                    <MessageSquare className="h-4 w-4 text-muted-foreground rotate-90" />
                    <div className="[writing-mode:vertical-lr] text-xs font-medium text-muted-foreground uppercase tracking-widest whitespace-nowrap">
                        Sales AI
                    </div>
                </div>
            )}
        </div>
    );
};

export default SalesChatSidebar;
