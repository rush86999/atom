import React, { useState } from 'react';
import { Check, ThumbsUp, ThumbsDown, ChevronDown, ChevronRight, Activity, Cpu } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

export interface ReasoningStep {
    id: string; // run_id
    index: number;
    timestamp: string;
    thought: string;
    action: string;
    action_input: any;
    observation: string;
    status: 'running' | 'completed' | 'failed';
}

interface ReasoningChainProps {
    steps: ReasoningStep[];
    isReasoning?: boolean; // Is the agent currently thinking?
    onFeedback?: (stepIndex: number, type: 'thumbs_up' | 'thumbs_down') => void;
    className?: string;
}

export const ReasoningChain: React.FC<ReasoningChainProps> = ({
    steps,
    isReasoning = false,
    onFeedback,
    className
}) => {
    const [expandedSteps, setExpandedSteps] = useState<Set<number>>(new Set());

    const toggleStep = (index: number) => {
        const newExpanded = new Set(expandedSteps);
        if (newExpanded.has(index)) {
            newExpanded.delete(index);
        } else {
            newExpanded.add(index);
        }
        setExpandedSteps(newExpanded);
    };

    return (
        <div className={cn("flex flex-col space-y-4 font-mono text-sm", className)}>
            {steps.map((step, idx) => (
                <div key={`${step.id}-${idx}`} className="border rounded-md bg-slate-50 overflow-hidden shadow-sm">
                    {/* Header: Thought & Status */}
                    <div
                        className="flex items-center justify-between p-3 bg-white border-b cursor-pointer hover:bg-gray-50 transition-colors"
                        onClick={() => toggleStep(idx)}
                    >
                        <div className="flex items-center gap-2 overflow-hidden">
                            <span className="text-gray-400 text-xs">#{idx + 1}</span>
                            {expandedSteps.has(idx) ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
                            <div className="flex items-center gap-2 truncate">
                                <Cpu className="w-4 h-4 text-purple-500" />
                                <span className="font-medium text-slate-700 truncate">{step.thought || "Thinking..."}</span>
                            </div>
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                            {onFeedback && (
                                <div className="flex gap-1 mr-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <Button size="icon" variant="ghost" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onFeedback(idx, 'thumbs_up'); }}>
                                        <ThumbsUp className="w-3 h-3 text-gray-400 hover:text-green-600" />
                                    </Button>
                                    <Button size="icon" variant="ghost" className="h-6 w-6" onClick={(e) => { e.stopPropagation(); onFeedback(idx, 'thumbs_down'); }}>
                                        <ThumbsDown className="w-3 h-3 text-gray-400 hover:text-red-600" />
                                    </Button>
                                </div>
                            )}
                            {step.status === 'completed' ? (
                                <Check className="w-4 h-4 text-green-500" />
                            ) : step.status === 'failed' ? (
                                <Activity className="w-4 h-4 text-red-500" />
                            ) : (
                                <div className="animate-spin rounded-full h-3 w-3 border-b-2 border-purple-500" />
                            )}
                        </div>
                    </div>

                    {/* Details: Action & Observation */}
                    {expandedSteps.has(idx) && (
                        <div className="p-3 bg-slate-50 space-y-3 animation-in slide-in-from-top-2 duration-200">
                            {step.action && (
                                <div className="space-y-1">
                                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Action</div>
                                    <div className="bg-white border rounded p-2 text-xs text-blue-700 break-all">
                                        <span className="font-bold">{step.action}</span>
                                        {step.action_input && (
                                            <pre className="mt-1 text-gray-600 overflow-x-auto">
                                                {JSON.stringify(step.action_input, null, 2)}
                                            </pre>
                                        )}
                                    </div>
                                </div>
                            )}
                            {step.observation && (
                                <div className="space-y-1">
                                    <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Observation</div>
                                    <div className="bg-white border rounded p-2 text-xs text-gray-600 max-h-40 overflow-y-auto">
                                        <pre className="whitespace-pre-wrap">{step.observation}</pre>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            ))}

            {isReasoning && (
                <div className="flex items-center gap-2 p-2 text-gray-500 animate-pulse">
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce" />
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce delay-100" />
                    <div className="w-2 h-2 bg-purple-400 rounded-full animate-bounce delay-200" />
                    <span className="text-xs ml-2">Reasoning...</span>
                </div>
            )}
        </div>
    );
};
