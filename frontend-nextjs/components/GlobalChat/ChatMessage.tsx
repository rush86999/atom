import React from 'react';
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
    User,
    Bot,
    Play,
    Calendar,
    Mail,
    Eye,
    CheckCircle,
    XCircle,
    Edit,
    Settings,
    Brain,
    Wrench,
    MessageCircle,
    ThumbsDown
} from "lucide-react";

export interface ChatAction {
    type: "execute" | "schedule" | "edit" | "confirm" | "cancel" |
    "create_event" | "send_email" | "view_inbox" | "view_calendar" |
    "view_template" | "open_builder";
    label: string;
    workflowId?: string;
    templateId?: string;
    workflowData?: any;
    data?: any;
}

export interface ChatMessageData {
    id: string;
    type: "user" | "assistant" | "system";
    content: string;
    timestamp: Date;
    workflowData?: {
        workflowId?: string;
        workflowName?: string;
        stepsCount?: number;
        isScheduled?: boolean;
        requiresConfirmation?: boolean;
    };
    actions?: ChatAction[];
    reasoningTrace?: ReasoningStep[];
}

export interface ReasoningStep {
    step: number;
    thought?: string;
    action?: { tool: string; params?: any };
    observation?: string;
    final_answer?: string;
}

interface ChatMessageProps {
    message: ChatMessageData;
    onActionClick: (action: ChatAction) => void;
}

export function ChatMessage({ message, onActionClick }: ChatMessageProps) {
    const isUser = message.type === 'user';

    const getActionIcon = (type: string) => {
        switch (type) {
            case 'execute': return <Play className="h-3 w-3 mr-1" />;
            case 'schedule': return <Calendar className="h-3 w-3 mr-1" />;
            case 'create_event': return <Calendar className="h-3 w-3 mr-1" />;
            case 'view_calendar': return <Calendar className="h-3 w-3 mr-1" />;
            case 'send_email': return <Mail className="h-3 w-3 mr-1" />;
            case 'view_inbox': return <Mail className="h-3 w-3 mr-1" />;
            case 'confirm': return <CheckCircle className="h-3 w-3 mr-1" />;
            case 'cancel': return <XCircle className="h-3 w-3 mr-1" />;
            case 'edit': return <Edit className="h-3 w-3 mr-1" />;
            case 'view_template': return <Eye className="h-3 w-3 mr-1" />;
            case 'open_builder': return <Edit className="h-3 w-3 mr-1" />;
            default: return <Settings className="h-3 w-3 mr-1" />;
        }
    };

    return (
        <div className={cn("flex w-full gap-2 mb-4", isUser ? "justify-end" : "justify-start")}>
            {!isUser && (
                <Avatar className="h-8 w-8">
                    <AvatarImage src="/bot-avatar.png" />
                    <AvatarFallback className="bg-primary text-primary-foreground"><Bot className="h-4 w-4" /></AvatarFallback>
                </Avatar>
            )}

            <div className={cn("flex flex-col max-w-[80%]", isUser ? "items-end" : "items-start")}>
                <Card className={cn(
                    "border-none shadow-sm",
                    isUser ? "bg-primary text-primary-foreground" : "bg-muted"
                )}>
                    <CardContent className="p-3 text-sm whitespace-pre-wrap">
                        {message.content}

                        {message.workflowData && (
                            <div className={cn(
                                "mt-3 p-2 rounded-md text-xs",
                                isUser ? "bg-primary-foreground/10" : "bg-background"
                            )}>
                                <div className="flex items-center gap-2 mb-1">
                                    <Badge variant="outline" className="text-[10px] h-5">
                                        {message.workflowData.stepsCount} steps
                                    </Badge>
                                    {message.workflowData.isScheduled && (
                                        <Badge variant="secondary" className="text-[10px] h-5">
                                            Scheduled
                                        </Badge>
                                    )}
                                </div>
                                <div className="font-medium">{message.workflowData.workflowName}</div>
                            </div>
                        )}

                        {/* Reasoning Trace */}
                        {message.reasoningTrace && message.reasoningTrace.length > 0 && (
                            <div className="mt-3 space-y-2 border-t pt-2">
                                <div className="flex items-center gap-1 text-xs text-muted-foreground font-medium">
                                    <Brain className="h-3 w-3" />
                                    Agent Reasoning
                                </div>
                                {message.reasoningTrace.map((step) => (
                                    <div key={step.step} className="p-2 rounded bg-background/50 text-xs space-y-1">
                                        <div className="flex items-center gap-2">
                                            <Badge variant="outline" className="text-[9px] h-4">
                                                Step {step.step}
                                            </Badge>
                                        </div>
                                        {step.thought && (
                                            <div className="text-muted-foreground flex items-start gap-1">
                                                <MessageCircle className="h-3 w-3 mt-0.5 shrink-0" />
                                                <span>{step.thought}</span>
                                            </div>
                                        )}
                                        {step.action && (
                                            <div className="font-mono text-blue-600 bg-blue-50 p-1 rounded flex items-start gap-1">
                                                <Wrench className="h-3 w-3 mt-0.5 shrink-0" />
                                                <span>{step.action.tool}({JSON.stringify(step.action.params || {})})</span>
                                            </div>
                                        )}
                                        {step.observation && (
                                            <div className="text-green-600 bg-green-50 p-1 rounded">
                                                → {step.observation}
                                            </div>
                                        )}
                                        {step.final_answer && (
                                            <div className="font-medium text-primary bg-primary/10 p-1.5 rounded">
                                                ✓ {step.final_answer}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </CardContent>

                    {message.actions && message.actions.length > 0 && (
                        <CardFooter className="p-2 pt-0 flex flex-wrap gap-2">
                            {message.actions.map((action, idx) => (
                                <Button
                                    key={idx}
                                    variant={action.type === 'execute' ? "default" : "secondary"}
                                    size="sm"
                                    className="h-7 text-xs px-2"
                                    onClick={() => onActionClick(action)}
                                >
                                    {getActionIcon(action.type)}
                                    {action.label}
                                </Button>
                            ))}
                        </CardFooter>
                    )}
                </Card>

                <span className="text-[10px] text-muted-foreground mt-1 px-1">
                    {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
            </div>

            {isUser && (
                <Avatar className="h-8 w-8">
                    <AvatarFallback className="bg-muted"><User className="h-4 w-4" /></AvatarFallback>
                </Avatar>
            )}
        </div>
    );
}
