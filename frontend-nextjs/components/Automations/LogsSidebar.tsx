
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCcw, CheckCircle2, XCircle, Clock } from "lucide-react";
import { format } from 'date-fns';

/**
 * Receipt metadata returned by
 * GET /api/v1/analytics/workflows/{workflow_id}/logs
 *
 * Deliberately does not include trigger_data/results: execution payloads are
 * not part of the logs receipt contract and must never be rendered here.
 */
interface LogEntry {
    id: string;
    workflow_id?: string;
    execution_id?: string;
    step_id: string;
    status: string;
    duration_ms: number;
    created_at?: string;
    updated_at?: string;
    started_at?: string;
    completed_at?: string;
    finished_at?: string;
    timestamp?: string;
}

interface LogsSidebarProps {
    workflowId: string;
    onClose: () => void;
}

interface LogsState {
    workflowId: string | null;
    logs: LogEntry[];
    selectedId: string | null;
    loading: boolean;
    error: string | null;
    errorDetail: string | null;
}

const ERROR_MESSAGE = 'Failed to load logs.';
const POLL_INTERVAL_MS = 5000;

function timestampFor(log: LogEntry): string | undefined {
    return log.created_at
        || log.started_at
        || log.timestamp
        || log.updated_at
        || log.completed_at
        || log.finished_at;
}

function formatTime(log: LogEntry): string {
    const raw = timestampFor(log);
    if (!raw) return '—';

    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return raw;
    return format(date, 'HH:mm:ss');
}

function formatFullTime(log: LogEntry): string {
    const raw = timestampFor(log);
    if (!raw) return '—';

    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return raw;
    return format(date, 'yyyy-MM-dd HH:mm:ss');
}

function formatDuration(log: LogEntry): string {
    if (log.duration_ms === null || log.duration_ms === undefined) return '—';
    const duration = Number(log.duration_ms);
    if (!Number.isFinite(duration)) return '—';
    return `${duration.toFixed(0)}ms`;
}

function getStoredToken(): string | null {
    try {
        return localStorage.getItem('auth_token');
    } catch {
        return null;
    }
}

export function LogsSidebar({ workflowId, onClose }: LogsSidebarProps) {
    const [state, setState] = useState<LogsState>({
        workflowId: null,
        logs: [],
        selectedId: null,
        loading: false,
        error: null,
        errorDetail: null,
    });

    // The ref is updated during render so a response for the previous workflow
    // is already considered stale as soon as the parent switches workflows,
    // even if the response lands before the effect cleanup runs.
    const activeWorkflowId = useRef(workflowId);
    activeWorkflowId.current = workflowId;

    const requestSequence = useRef(0);

    const fetchLogs = useCallback(async () => {
        const requestedWorkflowId = workflowId;
        if (!requestedWorkflowId) {
            setState({
                workflowId: requestedWorkflowId,
                logs: [],
                selectedId: null,
                loading: false,
                error: null,
                errorDetail: null,
            });
            return;
        }

        const requestId = requestSequence.current + 1;
        requestSequence.current = requestId;

        const isStale = () => (
            requestSequence.current !== requestId
            || activeWorkflowId.current !== requestedWorkflowId
        );

        setState(prev => (
            prev.workflowId === requestedWorkflowId
                ? { ...prev, loading: true, error: null, errorDetail: null }
                : {
                    workflowId: requestedWorkflowId,
                    logs: [],
                    selectedId: null,
                    loading: true,
                    error: null,
                    errorDetail: null,
                }
        ));

        const fail = (detail: string) => {
            if (isStale()) return;
            setState(prev => (
                prev.workflowId === requestedWorkflowId
                    ? {
                        ...prev,
                        logs: [],
                        selectedId: null,
                        loading: false,
                        error: ERROR_MESSAGE,
                        errorDetail: detail,
                    }
                    : prev
            ));
        };

        try {
            const token = getStoredToken();
            const response = await fetch(
                `/api/v1/analytics/workflows/${encodeURIComponent(requestedWorkflowId)}/logs`,
                {
                    method: 'GET',
                    headers: token ? { Authorization: `Bearer ${token}` } : {},
                },
            );

            if (isStale()) return;

            if (!response.ok) {
                fail(`The server returned HTTP ${response.status}.`);
                return;
            }

            let data: unknown;
            try {
                data = await response.json();
            } catch {
                fail('The server returned an invalid response.');
                return;
            }

            if (isStale()) return;

            if (!Array.isArray(data)) {
                fail('The server returned an invalid response.');
                return;
            }

            const isLogEntry = (value: unknown): value is LogEntry => (
                typeof value === 'object'
                && value !== null
                && typeof (value as { id?: unknown }).id === 'string'
            );

            if (!data.every(isLogEntry)) {
                fail('The server returned an invalid response.');
                return;
            }

            const logs = data as LogEntry[];
            setState(prev => {
                if (prev.workflowId !== requestedWorkflowId) return prev;

                const selectedId = prev.selectedId && logs.some(log => log.id === prev.selectedId)
                    ? prev.selectedId
                    : null;

                return {
                    ...prev,
                    logs,
                    selectedId,
                    loading: false,
                    error: null,
                    errorDetail: null,
                };
            });
        } catch (error) {
            if (isStale()) return;
            if (error instanceof Error && error.name === 'AbortError') return;

            console.error("Failed to fetch logs", error);
            fail('The request could not be completed.');
        }
    }, [workflowId]);

    useEffect(() => {
        activeWorkflowId.current = workflowId;

        // Clear previous data synchronously in the effect as well as guarding
        // by workflow in render, so a workflow switch never flashes old logs or
        // an old selection.
        setState({
            workflowId,
            logs: [],
            selectedId: null,
            loading: Boolean(workflowId),
            error: null,
            errorDetail: null,
        });

        if (!workflowId) return;

        void fetchLogs();
        // Preserve live updates: poll the current workflow every 5 seconds.
        const interval = setInterval(() => {
            void fetchLogs();
        }, POLL_INTERVAL_MS);

        return () => {
            clearInterval(interval);
            // Invalidate in-flight requests from this workflow.
            requestSequence.current += 1;
        };
    }, [workflowId, fetchLogs]);

    // Derived from the state's workflow id as well as the current prop. This
    // makes prior logs/selection disappear in the same render as a switch,
    // rather than waiting for effects or a response.
    const hasCurrentData = state.workflowId === workflowId;
    const logs = hasCurrentData ? state.logs : [];
    const selectedId = hasCurrentData ? state.selectedId : null;
    const loading = !hasCurrentData || state.loading;
    const error = hasCurrentData ? state.error : null;
    const errorDetail = hasCurrentData ? state.errorDetail : null;

    const handleRefresh = () => {
        void fetchLogs();
    };

    const handleSelect = (log: LogEntry) => {
        setState(prev => ({
            ...prev,
            selectedId: prev.selectedId === log.id ? null : log.id,
        }));
    };

    return (
        <div className="w-96 border-l bg-white dark:bg-gray-900 flex flex-col h-full shadow-xl z-20 absolute right-0 top-0 bottom-0">
            <div className="p-4 border-b flex justify-between items-center bg-gray-50 dark:bg-gray-800">
                <h3 className="font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2">
                    <Clock className="w-4 h-4" /> Execution History
                </h3>
                <div className="flex gap-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={handleRefresh}
                        disabled={loading}
                        aria-label="Refresh logs"
                    >
                        <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <span className="text-xl">×</span>
                    </Button>
                </div>
            </div>

            <ScrollArea className="flex-1 p-4">
                {error ? (
                    <div role="alert" className="text-center text-red-600 dark:text-red-400 mt-10">
                        <div className="font-medium">{error}</div>
                        {errorDetail && (
                            <div className="text-xs mt-1 text-gray-500 dark:text-gray-400">{errorDetail}</div>
                        )}
                    </div>
                ) : loading && logs.length === 0 ? (
                    <div className="flex items-center justify-center gap-2 text-gray-500 dark:text-gray-400 mt-10">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Loading logs…</span>
                    </div>
                ) : logs.length === 0 ? (
                    <div className="text-center text-gray-500 dark:text-gray-400 mt-10">No logs found yet.</div>
                ) : (
                    <div className="space-y-3">
                        {logs.map(log => {
                            const status = typeof log.status === 'string' ? log.status : '';
                            const isCompleted = status.toUpperCase() === 'COMPLETED';
                            const isSelected = selectedId === log.id;

                            return (
                                <div
                                    key={log.id}
                                    className={`border rounded-lg p-3 text-sm cursor-pointer hover:bg-gray-50 dark:bg-gray-800 transition-colors ${isSelected ? 'ring-2 ring-blue-500 bg-blue-50' : ''}`}
                                    onClick={() => handleSelect(log)}
                                >
                                    <div className="flex justify-between items-start mb-2">
                                        <div className="flex items-center gap-2">
                                            {isCompleted ? (
                                                <CheckCircle2 className="w-4 h-4 text-green-500" />
                                            ) : (
                                                <XCircle className="w-4 h-4 text-red-500" />
                                            )}
                                            <span className="font-medium">{log.step_id || 'Unknown step'}</span>
                                        </div>
                                        <span className="text-xs text-gray-500 dark:text-gray-400">
                                            {formatTime(log)}
                                        </span>
                                    </div>
                                    <div className="flex justify-between text-xs text-gray-500 dark:text-gray-400">
                                        <span>Duration: {formatDuration(log)}</span>
                                        <span className="capitalize">{status.toLowerCase()}</span>
                                    </div>

                                    {isSelected && (
                                        <div className="mt-3 pt-3 border-t space-y-1 text-xs animate-in slide-in-from-top-1 duration-200">
                                            <div className="flex justify-between gap-3">
                                                <span className="text-gray-500 dark:text-gray-400">Log ID</span>
                                                <span className="font-mono break-all text-right">{log.id}</span>
                                            </div>
                                            <div className="flex justify-between gap-3">
                                                <span className="text-gray-500 dark:text-gray-400">Execution ID</span>
                                                <span className="font-mono break-all text-right">{log.execution_id || '—'}</span>
                                            </div>
                                            <div className="flex justify-between gap-3">
                                                <span className="text-gray-500 dark:text-gray-400">Workflow ID</span>
                                                <span className="font-mono break-all text-right">{log.workflow_id || '—'}</span>
                                            </div>
                                            <div className="flex justify-between gap-3">
                                                <span className="text-gray-500 dark:text-gray-400">Step ID</span>
                                                <span className="font-mono break-all text-right">{log.step_id || '—'}</span>
                                            </div>
                                            <div className="flex justify-between gap-3">
                                                <span className="text-gray-500 dark:text-gray-400">Timestamp</span>
                                                <span className="text-right">{formatFullTime(log)}</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </ScrollArea>
        </div>
    );
}
