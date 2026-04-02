'use client';

/**
 * AgentOperationTracker Component
 * 
 * Displays real-time agent operations with progress tracking,
 * context explanations, and live operation logs.
 */

import React, { useState, useEffect } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Bot, Info, AlertTriangle, XCircle, CheckCircle2, Zap, Pause, RotateCcw } from 'lucide-react';
import { AgentOperationData, OperationLog } from './types';
import { cn } from '@/lib/utils';

export interface AgentOperationTrackerProps {
    operationId?: string;
    agentId?: string;
    tenantId?: string;
    initialData?: AgentOperationData;
    className?: string;
}

export const AgentOperationTracker: React.FC<AgentOperationTrackerProps> = ({
    operationId,
    initialData,
    className = ''
}) => {
    const [operation, setOperation] = useState<AgentOperationData | null>(initialData || null);
    const [logsExpanded, setLogsExpanded] = useState(true);
    const { lastMessage } = useWebSocket();

    useEffect(() => {
        if (!lastMessage) return;

        try {
            // Handle operation present
            if (lastMessage.type === 'canvas:update' && lastMessage.data?.component === 'agent_operation_tracker') {
                const data = lastMessage.data.data;

                // Filter by operationId if specified
                if (!operationId || data.operation_id === operationId) {
                    setOperation(data);
                }
            }

            // Handle operation updates
            if (lastMessage.type === 'canvas:update' && lastMessage.data?.action === 'update') {
                if (lastMessage.data.operation_id === operation?.operation_id) {
                    setOperation((prev) => prev ? ({
                        ...prev,
                        ...lastMessage.data.updates
                    }) : null);
                }
            }
        } catch (error) {
            console.error('Failed to process WebSocket message:', error);
        }
    }, [lastMessage, operationId, operation?.operation_id]);

    if (!operation) {
        return (
            <div className={cn("flex flex-col items-center justify-center p-8 space-y-4 text-center", className)}>
                <Bot className="w-8 h-8 text-muted-foreground animate-pulse" />
                <p className="text-sm text-muted-foreground">Waiting for agent operation data...</p>
            </div>
        );
    }

    const getStatusConfig = (status: string) => {
        switch (status) {
            case 'running':
                return { color: 'text-blue-600 bg-blue-50 dark:bg-blue-900/20', icon: <Zap className="w-3 h-3" />, label: 'Running' };
            case 'waiting':
                return { color: 'text-yellow-600 bg-yellow-50 dark:bg-yellow-900/20', icon: <Pause className="w-3 h-3" />, label: 'Waiting' };
            case 'completed':
                return { color: 'text-green-600 bg-green-50 dark:bg-green-900/20', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Completed' };
            case 'failed':
                return { color: 'text-red-600 bg-red-50 dark:bg-red-900/20', icon: <XCircle className="w-3 h-3" />, label: 'Failed' };
            default:
                return { color: 'text-gray-600 bg-gray-50 dark:bg-gray-800/20', icon: <RotateCcw className="w-3 h-3" />, label: status };
        }
    };

    const getLogConfig = (level: string) => {
        switch (level) {
            case 'info':
                return { icon: <Info className="w-3 h-3 text-blue-500" /> };
            case 'warning':
                return { icon: <AlertTriangle className="w-3 h-3 text-yellow-500" /> };
            case 'error':
                return { icon: <XCircle className="w-3 h-3 text-red-500" /> };
            default:
                return { icon: <Info className="w-3 h-3" /> };
        }
    };

    const statusConfig = getStatusConfig(operation.status);

    return (
        <Card className={cn("overflow-hidden border-none shadow-none bg-transparent", className)}>
            <CardHeader className="p-0 pb-4 flex flex-row items-center justify-between space-y-0">
                <div className="flex items-center space-x-3">
                    <div className="p-2 bg-primary/10 rounded-lg">
                        <Bot className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                        <CardTitle className="text-sm font-semibold">{operation.agent_name}</CardTitle>
                        <p className="text-xs text-muted-foreground">Operation: {operation.operation_type}</p>
                    </div>
                </div>
                <Badge variant="outline" className={cn("gap-1.5 px-2 py-0.5 border-none", statusConfig.color)}>
                    {statusConfig.icon}
                    {statusConfig.label}
                </Badge>
            </CardHeader>

            <CardContent className="p-0 space-y-4">
                {/* Progress Bar */}
                <div className="space-y-2">
                    <div className="flex justify-between text-[11px] font-medium text-muted-foreground uppercase tracking-wider">
                        <span>Progress</span>
                        <span>{Math.round(operation.progress)}%</span>
                    </div>
                    <Progress value={operation.progress} className="h-1.5" />
                    {operation.total_steps && (
                        <p className="text-[10px] text-muted-foreground text-right border-t border-border/50 pt-1">
                            Step {operation.current_step_index} of {operation.total_steps}
                        </p>
                    )}
                </div>

                {/* Current Step */}
                <div className="p-3 bg-muted/40 rounded-lg border border-border/50">
                    <p className="text-[11px] font-bold text-muted-foreground uppercase mb-1">Current Step</p>
                    <p className="text-sm font-medium leading-relaxed">{operation.current_step}</p>
                </div>

                {/* Context - What/Why/Next */}
                {(operation.context.what || operation.context.why || operation.context.next) && (
                    <div className="space-y-2">
                        <p className="text-[11px] font-bold text-muted-foreground uppercase">Chain of Thought</p>
                        <div className="grid gap-2">
                            {operation.context.what && (
                                <div className="p-2.5 bg-blue-500/5 border border-blue-500/20 rounded-md">
                                    <p className="text-[10px] font-bold text-blue-500 uppercase mb-0.5">Objective</p>
                                    <p className="text-xs text-foreground/90 leading-normal">{operation.context.what}</p>
                                </div>
                            )}
                            {operation.context.why && (
                                <div className="p-2.5 bg-purple-500/5 border border-purple-500/20 rounded-md">
                                    <p className="text-[10px] font-bold text-purple-500 uppercase mb-0.5">Reasoning</p>
                                    <p className="text-xs text-foreground/90 leading-normal">{operation.context.why}</p>
                                </div>
                            )}
                            {operation.context.next && (
                                <div className="p-2.5 bg-green-500/5 border border-green-500/20 rounded-md">
                                    <p className="text-[10px] font-bold text-green-500 uppercase mb-0.5">Anticipated Result</p>
                                    <p className="text-xs text-foreground/90 leading-normal">{operation.context.next}</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Logs */}
                <div className="space-y-2">
                    <button
                        onClick={() => setLogsExpanded(!logsExpanded)}
                        className="flex items-center justify-between w-full text-[11px] font-bold text-muted-foreground uppercase hover:text-foreground transition-colors"
                    >
                        <span>Activity Log ({operation.logs.length})</span>
                        <span className="text-[10px] opacity-50">{logsExpanded ? '▼' : '▶'}</span>
                    </button>

                    {logsExpanded && (
                        <ScrollArea className="h-40 rounded-lg border border-border/50 bg-muted/20 p-2">
                            <div className="space-y-2">
                                {operation.logs.map((log, index) => (
                                    <div key={index} className="flex items-start space-x-2.5 group">
                                        <div className="mt-0.5 opacity-70 group-hover:opacity-100 transition-opacity">
                                            {getLogConfig(log.level).icon}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className={cn("text-xs leading-normal",
                                                log.level === 'error' ? 'text-red-500 font-medium' :
                                                    log.level === 'warning' ? 'text-yellow-500' : 'text-foreground/80'
                                            )}>
                                                {log.message}
                                            </p>
                                            <p className="text-[9px] text-muted-foreground opacity-50 group-hover:opacity-100 transition-opacity">
                                                {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                            </p>
                                        </div>
                                    </div>
                                ))}
                                {operation.logs.length === 0 && (
                                    <p className="text-xs text-muted-foreground italic text-center py-4">No activity recorded yet</p>
                                )}
                            </div>
                        </ScrollArea>
                    )}
                </div>
            </CardContent>

            <div className="mt-4 pt-4 border-t border-border/50 flex justify-between items-center text-[10px] text-muted-foreground font-medium uppercase tracking-tighter">
                <span>Started: {new Date(operation.started_at).toLocaleTimeString()}</span>
                {operation.completed_at && (
                    <span className="text-green-500">
                        Completed: {new Date(operation.completed_at).toLocaleTimeString()}
                    </span>
                )}
            </div>

            {/* Accessibility Tree - Dual Representation */}
            <div
                role="log"
                aria-live="polite"
                aria-label="Agent operation state"
                style={{ display: 'none' }}
                data-canvas-state="agent_operation_tracker"
                data-operation-id={operation.operation_id}
                data-status={operation.status}
                data-progress={operation.progress}
            >
                {JSON.stringify(operation)}
            </div>
        </Card>
    );
};

export default AgentOperationTracker;
