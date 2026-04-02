/**
 * Supervised Agent Monitor Component
 *
 * Live monitoring component for supervised agents in Canvas UI.
 * Shows real-time execution progress, logs, and supervisor controls.
 */

'use client';

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Terminal, Play, Pause, X, Shield, User } from 'lucide-react';

interface ExecutionLog {
    timestamp: string;
    level: 'info' | 'warning' | 'error';
    message: string;
    step?: number;
}

interface SupervisorInfo {
    type: 'autonomous_agent' | 'user';
    agent_id?: string;
    user_id?: string;
    name?: string;
}

interface SupervisedAgentMonitorProps {
    executionId: string;
    agentId: string;
    agentName?: string;
    supervisorInfo?: SupervisorInfo;
    onComplete?: (result: any) => void;
    onError?: (error: string) => void;
}

/**
 * Live monitoring panel for supervised agent execution
 *
 * Displays real-time execution logs, progress tracking, and supervisor controls.
 * Connects to WebSocket/SSE for live log streaming.
 *
 * @example
 * ```tsx
 * <SupervisedAgentMonitor
 *   executionId="exec-123"
 *   agentId="agent-456"
 *   agentName="FinanceReconciler"
 *   supervisorInfo={{
 *     type: "autonomous_agent",
 *     agent_id: "auto-789",
 *     name: "AutoFinanceChief"
 *   }}
 *   onComplete={(result) => console.log('Completed:', result)}
 * />
 * ```
 */
export function SupervisedAgentMonitor({
    executionId,
    agentId,
    agentName,
    supervisorInfo,
    onComplete,
    onError
}: SupervisedAgentMonitorProps) {
    const [status, setStatus] = useState<'pending' | 'running' | 'completed' | 'failed' | 'cancelled'>('pending');
    const [logs, setLogs] = useState<ExecutionLog[]>([]);
    const [currentStep, setCurrentStep] = useState(0);
    const [totalSteps, setTotalSteps] = useState(0);
    const [canCancel, setCanCancel] = useState(false);
    const [output, setOutput] = useState<string | null>(null);

    // Connect to execution stream
    useEffect(() => {
        let eventSource: EventSource | null = null;

        const connectStream = () => {
            eventSource = new EventSource(`/api/v1/agents/${agentId}/stream/${executionId}`);

            eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    switch (data.type) {
                        case 'started':
                            setStatus('running');
                            setCanCancel(true);
                            addLog('info', 'Execution started');
                            break;

                        case 'step':
                            setCurrentStep(data.step);
                            setTotalSteps(data.totalSteps || 0);
                            addLog('info', data.message || `Step ${data.step}`, data.step);
                            break;

                        case 'log':
                            addLog(data.level || 'info', data.message);
                            break;

                        case 'progress':
                            setCurrentStep(data.current);
                            setTotalSteps(data.total);
                            break;

                        case 'completed':
                            setStatus('completed');
                            setCanCancel(false);
                            setOutput(data.output);
                            addLog('info', 'Execution completed successfully');
                            onComplete?.(data);
                            eventSource?.close();
                            break;

                        case 'failed':
                            setStatus('failed');
                            setCanCancel(false);
                            addLog('error', data.error || 'Execution failed');
                            onError?.(data.error);
                            eventSource?.close();
                            break;

                        case 'cancelled':
                            setStatus('cancelled');
                            setCanCancel(false);
                            addLog('warning', 'Execution was cancelled');
                            eventSource?.close();
                            break;
                    }
                } catch (error) {
                    console.error('[SupervisedAgentMonitor] Failed to parse event:', error);
                }
            };

            eventSource.onerror = (error) => {
                console.error('[SupervisedAgentMonitor] SSE error:', error);
                addLog('error', 'Connection lost');
                eventSource?.close();
            };
        };

        connectStream();

        return () => {
            eventSource?.close();
        };
    }, [executionId, agentId, onComplete, onError]);

    /**
     * Add log entry
     */
    const addLog = (level: ExecutionLog['level'], message: string, step?: number) => {
        setLogs(prev => [...prev, {
            timestamp: new Date().toISOString(),
            level,
            message,
            step
        }]);
    };

    /**
     * Cancel execution
     */
    const handleCancel = async () => {
        if (!canCancel) {
            return;
        }

        try {
            const response = await fetch(`/api/v1/agents/${agentId}/cancel/${executionId}`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error('Failed to cancel execution');
            }

            setStatus('cancelled');
            setCanCancel(false);
            addLog('warning', 'Execution cancelled by supervisor');
        } catch (error) {
            addLog('error', `Failed to cancel: ${error}`);
        }
    };

    /**
     * Get status badge color
     */
    const getStatusBadge = () => {
        switch (status) {
            case 'pending':
                return <Badge variant="secondary">Pending</Badge>;
            case 'running':
                return <Badge variant="default" className="bg-blue-500">Running</Badge>;
            case 'completed':
                return <Badge variant="default" className="bg-green-500">Completed</Badge>;
            case 'failed':
                return <Badge variant="destructive">Failed</Badge>;
            case 'cancelled':
                return <Badge variant="outline">Cancelled</Badge>;
        }
    };

    /**
     * Get log level color
     */
    const getLogColor = (level: ExecutionLog['level']) => {
        switch (level) {
            case 'info':
                return 'text-gray-700 dark:text-gray-300';
            case 'warning':
                return 'text-yellow-600 dark:text-yellow-400';
            case 'error':
                return 'text-red-600 dark:text-red-400';
        }
    };

    return (
        <Card className="p-4 space-y-4">
            {/* Header */}
            <div className="flex items-start justify-between">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <Terminal className="w-4 h-4" />
                        <h3 className="font-semibold">{agentName}</h3>
                        {getStatusBadge()}
                    </div>

                    {/* Supervisor info */}
                    <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <Shield className="w-3 h-3" />
                        <span>Supervised by:</span>
                        {supervisorInfo.type === 'autonomous_agent' ? (
                            <Badge variant="outline" className="text-xs">
                                <Shield className="w-3 h-3 mr-1" />
                                {supervisorInfo.name || supervisorInfo.agent_id}
                            </Badge>
                        ) : (
                            <Badge variant="outline" className="text-xs">
                                <User className="w-3 h-3 mr-1" />
                                You
                            </Badge>
                        )}
                    </div>
                </div>

                {/* Cancel button */}
                {canCancel && (
                    <Button
                        variant="destructive"
                        size="sm"
                        onClick={handleCancel}
                        className="gap-1"
                    >
                        <X className="w-3 h-3" />
                        Cancel
                    </Button>
                )}
            </div>

            {/* Progress bar */}
            {totalSteps > 0 && (
                <div className="space-y-1">
                    <div className="flex justify-between text-xs text-gray-600 dark:text-gray-400">
                        <span>Progress</span>
                        <span>{currentStep} / {totalSteps}</span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                        <div
                            className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${(currentStep / totalSteps) * 100}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Execution logs */}
            <ScrollArea className="h-48 w-full rounded-md border bg-gray-50 dark:bg-gray-900 p-3">
                <div className="space-y-1 font-mono text-xs">
                    {logs.map((log, index) => (
                        <div key={index} className={getLogColor(log.level)}>
                            <span className="text-gray-400">
                                {new Date(log.timestamp).toLocaleTimeString()}
                            </span>
                            {log.step && (
                                <span className="text-blue-500 ml-2">
                                    [Step {log.step}]
                                </span>
                            )}
                            <span className="ml-2">{log.message}</span>
                        </div>
                    ))}
                    {logs.length === 0 && (
                        <div className="text-gray-400 italic">
                            Waiting for execution to start...
                        </div>
                    )}
                </div>
            </ScrollArea>

            {/* Output preview */}
            {output && status === 'completed' && (
                <div className="space-y-2">
                    <h4 className="text-sm font-medium">Output</h4>
                    <ScrollArea className="h-24 w-full rounded-md border bg-gray-50 dark:bg-gray-900 p-2">
                        <pre className="text-xs font-mono whitespace-pre-wrap">
                            {output}
                        </pre>
                    </ScrollArea>
                </div>
            )}
        </Card>
    );
}

export default SupervisedAgentMonitor;
