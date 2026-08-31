"use client";

import React, { useState } from "react";
import { ThumbsUp, ThumbsDown, MessageSquare, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export type ChatFeedbackType = "thumbs_up" | "thumbs_down";

/**
 * Per-message feedback row for the canvas co-editor chat.
 *
 * Mirrors AgentWorkspace's step-feedback conventions so both surfaces train
 * the same way: chosen state renders via color classes, and a note submits
 * as thumbs_down + text (corrective) — the polarity governance adjudication
 * reads. Purely presentational; the parent owns state and the API calls.
 */
export function ChatFeedbackControls({
    selected,
    disabled,
    onFeedback,
}: {
    selected?: ChatFeedbackType | null;
    disabled?: boolean;
    onFeedback: (type: ChatFeedbackType, comment?: string) => void;
}) {
    const [noteOpen, setNoteOpen] = useState(false);
    const [note, setNote] = useState("");

    const submitNote = () => {
        const text = note.trim();
        setNoteOpen(false);
        setNote("");
        if (!text) return;
        onFeedback("thumbs_down", text);
    };

    return (
        <div className="flex flex-col gap-1 mt-1" data-testid="canvas-chat-feedback">
            <div className="flex items-center gap-0.5">
                <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    aria-label="Thumbs up"
                    title="Good reply — helps training"
                    disabled={disabled}
                    onClick={() => onFeedback("thumbs_up")}
                >
                    <ThumbsUp
                        className={`h-3.5 w-3.5 ${
                            selected === "thumbs_up"
                                ? "text-green-500"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    />
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    aria-label="Thumbs down"
                    title="Wrong reply — corrects the agent"
                    disabled={disabled}
                    onClick={() => onFeedback("thumbs_down")}
                >
                    <ThumbsDown
                        className={`h-3.5 w-3.5 ${
                            selected === "thumbs_down"
                                ? "text-red-500"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    />
                </Button>
                <Button
                    variant="ghost"
                    size="sm"
                    className="h-6 w-6 p-0"
                    aria-label="Add note"
                    title="Tell the agent what to learn"
                    disabled={disabled}
                    onClick={() => setNoteOpen((open) => !open)}
                >
                    <MessageSquare
                        className={`h-3.5 w-3.5 ${
                            noteOpen
                                ? "text-primary"
                                : "text-muted-foreground hover:text-foreground"
                        }`}
                    />
                </Button>
                <span className="text-[9px] text-muted-foreground ml-1">
                    feedback trains the agent
                </span>
            </div>
            {noteOpen && (
                <div className="flex gap-1">
                    <Input
                        value={note}
                        onChange={(e: any) => setNote(e.target.value)}
                        onKeyDown={(e: any) =>
                            e.key === "Enter" && (e.preventDefault(), submitNote())
                        }
                        aria-label="Feedback note"
                        placeholder="What should the agent learn?"
                        className="h-6 text-xs"
                        autoFocus
                    />
                    <Button
                        size="icon"
                        className="h-6 w-6"
                        onClick={submitNote}
                        disabled={!note.trim()}
                        aria-label="Send feedback note"
                        title="Send feedback note"
                    >
                        <Send className="h-3 w-3" />
                    </Button>
                </div>
            )}
        </div>
    );
}

export default ChatFeedbackControls;
