'use client';

import React from 'react';
import { Button } from "@/components/ui/button";
import { Input as UiInput } from "@/components/ui/input";
import { Send, StopCircle, Paperclip, Mic, X, Loader2 } from "lucide-react";

interface ChatInputProps {
    input: string;
    setInput: (value: string) => void;
    isProcessing: boolean;
    isUploading: boolean;
    activeAttachments: any[];
    setActiveAttachments: React.Dispatch<React.SetStateAction<any[]>>;
    handleSend: () => Promise<void>;
    handleStop: () => void;
    setIsVoiceModeOpen: (isOpen: boolean) => void;
    uploadFile: (file: File) => Promise<any>;
    toast: any;
    messagesCount: number;
}

export const ChatInput: React.FC<ChatInputProps> = ({
    input,
    setInput,
    isProcessing,
    isUploading,
    activeAttachments,
    setActiveAttachments,
    handleSend,
    handleStop,
    setIsVoiceModeOpen,
    uploadFile,
    toast,
    messagesCount,
}) => {
    return (
        <div className="p-4 border-t border-border bg-background">
            <div className="max-w-3xl mx-auto flex flex-col gap-2">
                {isUploading && (
                    <div className="flex items-center gap-2 mb-2 p-2 bg-muted rounded-md animate-in fade-in">
                        <Loader2 className="h-4 w-4 animate-spin text-primary" />
                        <span className="text-xs font-medium">Uploading file...</span>
                    </div>
                )}

                {/* Attachment Chips */}
                {Array.isArray(activeAttachments) && activeAttachments.length > 0 && (
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
                    <UiInput
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
                        <Button onClick={handleSend} size="icon" disabled={!input.trim()}>
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
    );
};
