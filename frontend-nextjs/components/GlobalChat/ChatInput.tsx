import React, { useState, useRef, useEffect } from 'react';
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Send, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
    onSendMessage: (message: string) => void;
    isLoading: boolean;
}

export function ChatInput({ onSendMessage, isLoading }: ChatInputProps) {
    const [input, setInput] = useState("");
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const handleSend = () => {
        if (input.trim() && !isLoading) {
            onSendMessage(input);
            setInput("");
            // Reset height
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // Auto-resize
    useEffect(() => {
        if (textareaRef.current) {
            textareaRef.current.style.height = 'auto';
            textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
        }
    }, [input]);

    return (
        <div className="p-4 border-t bg-background">
            <div className="relative flex items-end gap-2">
                <Textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask ATOM to schedule meetings, send emails..."
                    className="min-h-[44px] max-h-[120px] resize-none pr-12 py-3"
                    disabled={isLoading}
                />
                <Button
                    size="icon"
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                    className="absolute right-2 bottom-2 h-8 w-8"
                >
                    {isLoading ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                        <Send className="h-4 w-4" />
                    )}
                </Button>
            </div>
            <p className="text-xs text-muted-foreground mt-2 text-center">
                Try: "Schedule standup tomorrow at 10am"
            </p>
        </div>
    );
}
