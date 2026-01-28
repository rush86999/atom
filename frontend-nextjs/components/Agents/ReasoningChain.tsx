'use client';

import React, { useState } from 'react';
import { ChevronDown, ChevronRight, Brain, Terminal, Eye, ThumbsUp, ThumbsDown, MessageSquarePlus } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/use-toast';
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover";
import { Textarea } from "@/components/ui/textarea";

export interface ReasoningStep {
    type: 'thought' | 'action' | 'observation' | 'error';
    content: string;
    metadata?: any;
    timestamp: Date;
    feedback?: 'thumbs_up' | 'thumbs_down';
    comment?: string;
}

interface ReasoningChainProps {
    steps: ReasoningStep[];
    isThinking?: boolean;
    agentId?: string;
    runId?: string;
}

const ReasoningStepItem = ({ step, idx, localFeedback, onFeedback }: { step: ReasoningStep, idx: number, localFeedback?: { type: string, comment?: string }, onFeedback: (type: 'thumbs_up' | 'thumbs_down', comment?: string) => void }) => {
    const [showComment, setShowComment] = useState(false);
    const [comment, setComment] = useState(localFeedback?.comment || "");

    const handleSubmit = () => {
        onFeedback('thumbs_down', comment); // Defaulting to negative feedback when commenting, or should I let them choose?
        // Upstream implementation seems to imply "Submit" on comment is usually correction (thumbs_down) or just generic.
        // But wait, upstream allows ThumbsUp/Down independent of comment.
        // Let's support both. If they click submit here, we'll keep existing type or default to 'thumbs_down' if none.
        // Actually, upstream lines 224: `onFeedback(message.id, 'thumbs_down', comment);` -> It hardcodes thumbs_down on submit!
        // I will do the same for parity, assuming comments = corrections.
        onFeedback('thumbs_down', comment);
        setShowComment(false);
    };

    return (
        <div className="group text-sm animate-in fade-in slide-in-from-top-1 duration-200">
            <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                    {step.type === 'thought' && <Brain className="h-3 w-3 text-blue-500" />}
                    {step.type === 'action' && <Terminal className="h-3 w-3 text-orange-500" />}
                    {step.type === 'observation' && <Eye className="h-3 w-3 text-green-500" />}
                    <Badge variant="outline" className="text-[10px] uppercase">{step.type}</Badge>
                    <span className="text-[10px] text-muted-foreground">
                        {new Date(step.timestamp).toLocaleTimeString()}
                    </span>
                </div>

                {/* Feedback Controls */}
                <div className={`flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity ${localFeedback || showComment ? 'opacity-100' : ''}`}>
                    <Button
                        variant="ghost"
                        size="icon"
                        className={`h-5 w-5 ${localFeedback?.type === 'thumbs_up' ? 'text-green-600' : 'text-muted-foreground'}`}
                        onClick={() => onFeedback('thumbs_up')}
                    >
                        <ThumbsUp className="h-3 w-3" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className={`h-5 w-5 ${localFeedback?.type === 'thumbs_down' ? 'text-red-500' : 'text-muted-foreground'}`}
                        onClick={() => onFeedback('thumbs_down')}
                    >
                        <ThumbsDown className="h-3 w-3" />
                    </Button>
                    <Button
                        variant="ghost"
                        size="icon"
                        className={`h-5 w-5 ${showComment ? 'text-blue-500' : 'text-muted-foreground'}`}
                        onClick={() => setShowComment(!showComment)}
                    >
                        <MessageSquarePlus className="h-3 w-3" />
                    </Button>
                </div>
            </div>

            <div className="pl-6 text-muted-foreground font-mono text-xs bg-muted/20 p-2 rounded overflow-x-auto whitespace-pre-wrap">
                {step.content}
            </div>

            {/* Inline Comment Box */}
            {showComment && (
                <div className="ml-6 mt-2 bg-background border rounded-md p-2 shadow-sm space-y-2 animate-in fade-in slide-in-from-top-1">
                    <Textarea
                        placeholder="What was wrong or how can I improve?"
                        className="w-full text-xs p-2 border rounded focus:ring-1 focus:ring-primary outline-none min-h-[60px]"
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                    />
                    <div className="flex justify-end gap-2">
                        <Button size="sm" variant="ghost" className="h-6 text-[10px]" onClick={() => setShowComment(false)}>
                            Cancel
                        </Button>
                        <Button
                            size="sm"
                            className="h-6 text-[10px]"
                            disabled={!comment.trim()}
                            onClick={handleSubmit}
                        >
                            Submit Correction
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
};

export function ReasoningChain({ steps, isThinking, agentId = 'atom_main', runId }: ReasoningChainProps) {
    const [isOpen, setIsOpen] = useState(false);
    const { toast } = useToast();
    const [localFeedback, setLocalFeedback] = useState<Record<number, { type: string, comment?: string }>>({});

    if (!steps || steps.length === 0) return null;

    const handleFeedback = async (idx: number, type: 'thumbs_up' | 'thumbs_down', stepContent: any, comment?: string) => {
        setLocalFeedback(prev => ({ ...prev, [idx]: { type, comment } }));

        try {
            await fetch('/api/reasoning/feedback', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: agentId,
                    run_id: runId || 'manual_run_' + Date.now(),
                    step_index: idx,
                    step_content: { type: stepContent.type, content: stepContent.content },
                    feedback_type: type,
                    comment: comment
                })
            });
            toast({ title: "Feedback Recorded", description: "Your feedback helps ATOM improve." });
        } catch (e) {
            console.error("Feedback failed", e);
        }
    };

    return (
        <div className="w-full my-2">
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full p-2 rounded-md hover:bg-muted/50"
            >
                {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                <Brain className="h-3 w-3" />
                <span>Reasoning Process ({steps.length} steps)</span>
                {isThinking && <span className="animate-pulse ml-2 text-primary">Thinking...</span>}
            </button>

            {isOpen && (
                <div className="pl-4 border-l-2 border-muted ml-3 mt-1 space-y-2">
                    {steps.map((step, idx) => (
                        <ReasoningStepItem
                            key={idx}
                            step={step}
                            idx={idx}
                            localFeedback={localFeedback[idx]}
                            onFeedback={(type, comment) => handleFeedback(idx, type, step, comment)}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
