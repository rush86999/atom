'use client';

/**
 * AgentRequestPrompt Component
 * 
 * Interactive component for agent requests that require user input,
 * decisions, or confirmation. Supports multiple options, consequences,
 * and urgency indicators.
 */

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
    AlertCircle,
    ChevronRight,
    CheckCircle2,
    XCircle,
    ShieldAlert,
    Clock,
    MessageSquare,
    HelpCircle
} from 'lucide-react';
import { RequestData, RequestOption } from './types';
import { cn } from '@/lib/utils';

export interface AgentRequestPromptProps {
    request: RequestData;
    onRespond: (requestId: string, action: string) => Promise<void>;
    className?: string;
}

export const AgentRequestPrompt: React.FC<AgentRequestPromptProps> = ({
    request,
    onRespond,
    className = ''
}) => {
    const [selectedOption, setSelectedOption] = useState<number | null>(
        request.suggested_option !== undefined ? request.suggested_option : null
    );
    const [submitting, setSubmitting] = useState(false);
    const [completed, setCompleted] = useState(false);

    const handleRespond = async () => {
        if (selectedOption === null || submitting) return;

        setSubmitting(true);
        try {
            const option = request.options[selectedOption];
            await onRespond(request.request_id, option.action);
            setCompleted(true);
        } catch (error) {
            console.error('Failed to submit response:', error);
        } finally {
            setSubmitting(false);
        }
    };

    if (completed) {
        return (
            <Card className={cn("overflow-hidden border-green-200 bg-green-50/50 dark:bg-green-950/10", className)}>
                <CardContent className="flex flex-col items-center justify-center p-8 text-center space-y-3">
                    <CheckCircle2 className="w-10 h-10 text-green-500" />
                    <div>
                        <h3 className="text-sm font-semibold text-green-800 dark:text-green-300">Response Submitted</h3>
                        <p className="text-xs text-green-700/70 dark:text-green-400/70">
                            The agent has been notified of your decision.
                        </p>
                    </div>
                </CardContent>
            </Card>
        );
    }

    const getUrgencyConfig = (urgency: string) => {
        switch (urgency) {
            case 'low':
                return { color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30', icon: <Clock className="w-3 h-3" />, label: 'Low Urgency' };
            case 'medium':
                return { color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30', icon: <AlertCircle className="w-3 h-3" />, label: 'Revision Needed' };
            case 'high':
                return { color: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30', icon: <ShieldAlert className="w-3 h-3" />, label: 'High Priority' };
            case 'blocking':
                return { color: 'bg-red-100 text-red-700 dark:bg-red-900/40', icon: <XCircle className="w-3 h-3" />, label: 'Action Required' };
            default:
                return { color: 'bg-gray-100 text-gray-700 dark:bg-gray-800', icon: <HelpCircle className="w-3 h-3" />, label: urgency };
        }
    };

    const urgencyConfig = getUrgencyConfig(request.urgency);

    return (
        <Card className={cn("overflow-hidden border-none shadow-none bg-transparent", className)}>
            <CardHeader className="p-0 pb-4 flex flex-row items-center justify-between space-y-0">
                <div className="flex items-center space-x-3 text-left">
                    <div className="p-2 bg-orange-500/10 rounded-lg">
                        <MessageSquare className="w-5 h-5 text-orange-500" />
                    </div>
                    <div>
                        <CardTitle className="text-sm font-semibold">{request.agent_name} Request</CardTitle>
                        <p className="text-xs text-muted-foreground">{request.title}</p>
                    </div>
                </div>
                <Badge variant="outline" className={cn("gap-1.5 px-2 py-0.5 border-none", urgencyConfig.color)}>
                    {urgencyConfig.icon}
                    {urgencyConfig.label}
                </Badge>
            </CardHeader>

            <CardContent className="p-0 space-y-5 text-left">
                {/* Explanation */}
                <div className="space-y-2">
                    <div className="flex items-center space-x-2 text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                        <HelpCircle className="w-3 h-3" />
                        <span>Context & Reasoning</span>
                    </div>
                    <p className="text-sm leading-relaxed text-foreground/90 bg-muted/30 p-3 rounded-lg border border-border/50">
                        {request.explanation}
                    </p>
                </div>

                {/* Impact Analysis */}
                <div className="grid grid-cols-2 gap-3">
                    <div className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-2.5">
                        <p className="text-[10px] font-bold text-blue-500 uppercase mb-1">Impact</p>
                        <p className="text-xs">{request.context.impact}</p>
                    </div>
                    <div className="bg-purple-500/5 border border-purple-500/20 rounded-lg p-2.5">
                        <p className="text-[10px] font-bold text-purple-500 uppercase mb-1">Operation</p>
                        <p className="text-xs truncate">{request.context.operation}</p>
                    </div>
                </div>

                {/* Options */}
                <div className="space-y-2.5">
                    <p className="text-[11px] font-bold text-muted-foreground uppercase">Select an Option</p>
                    <div className="grid gap-2">
                        {request.options.map((option, index) => (
                            <button
                                key={index}
                                onClick={() => setSelectedOption(index)}
                                className={cn(
                                    "flex flex-col p-3 rounded-xl border text-left transition-all duration-200 group relative overflow-hidden",
                                    selectedOption === index
                                        ? "border-primary bg-primary/5 ring-1 ring-primary"
                                        : "border-border bg-card hover:border-border/80 hover:bg-muted/30"
                                )}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className={cn(
                                        "text-sm font-bold",
                                        selectedOption === index ? "text-primary" : "text-foreground"
                                    )}>
                                        {option.label}
                                    </span>
                                    {selectedOption === index && (
                                        <div className="bg-primary text-primary-foreground rounded-full p-0.5">
                                            <ChevronRight className="w-3 h-3" />
                                        </div>
                                    )}
                                </div>
                                <p className="text-xs text-muted-foreground leading-normal mb-2">{option.description}</p>
                                <div className="flex items-center mt-auto pt-2 border-t border-border/50">
                                    <span className="text-[9px] font-bold uppercase tracking-tight text-muted-foreground/60 mr-2">Consequence:</span>
                                    <span className="text-[10px] italic text-muted-foreground line-clamp-1">{option.consequences}</span>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>
            </CardContent>

            <CardFooter className="px-0 pt-6 pb-2">
                <Button
                    onClick={handleRespond}
                    disabled={selectedOption === null || submitting}
                    className="w-full h-11 rounded-xl font-bold text-sm shadow-lg shadow-primary/20"
                >
                    {submitting ? 'Submitting...' : 'Confirm Decision'}
                </Button>
            </CardFooter>

            {/* Governance Footer */}
            {(request.governance.requires_signature || request.governance.audit_log_required) && (
                <div className="mt-2 flex items-center justify-center space-x-4 text-[9px] text-muted-foreground opacity-60">
                    {request.governance.requires_signature && (
                        <span className="flex items-center gap-1">
                            <ShieldAlert className="w-2.5 h-2.5" /> Electronic Signature Active
                        </span>
                    )}
                    {request.governance.audit_log_required && (
                        <span className="flex items-center gap-1">
                            <ScrollArea className="w-2.5 h-2.5" /> Permanently Logged
                        </span>
                    )}
                </div>
            )}

            {/* Accessibility Tree */}
            <div
                role="form"
                aria-label="Agent request prompt"
                style={{ display: 'none' }}
                data-canvas-state="agent_request_prompt"
                data-request-id={request.request_id}
                data-urgency={request.urgency}
            >
                {JSON.stringify(request)}
            </div>
        </Card>
    );
};

export default AgentRequestPrompt;
