
import React, { useEffect, useState } from 'react';
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Loader2, RefreshCcw, CheckCircle2, XCircle, Clock } from "lucide-react";
import { differenceInMilliseconds, format } from 'date-fns';

interface LogEntry {
    id: string;
    step_id: string;
    status: string;
    duration_ms: number;
    created_at: string;
    trigger_data?: any;
    results?: any;
}

interface LogsSidebarProps {
    workflowId: string;
    onClose: () => void;
}

export function LogsSidebar({ workflowId, onClose }: LogsSidebarProps) {
    const [logs, setLogs] = useState<LogEntry[]>([]);
    const [loading, setLoading] = useState(false);
    const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);

    const fetchLogs = async () => {
        if (!workflowId) return;
        setLoading(true);
        try {
            // Frontend proxy /api/analytics -> Backend /api/v1/analytics
            const res = await fetch(`/api/analytics/workflows/${workflowId}/logs`);
            if (res.ok) {
                const data = await res.json();
                setLogs(data);
            }
        } catch (error) {
            console.error("Failed to fetch logs", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchLogs();
        // Poll every 5 seconds for live updates
        const interval = setInterval(fetchLogs, 5000);
        return () => clearInterval(interval);
    }, [workflowId]);

    return (
        <div className="w-96 border-l bg-white flex flex-col h-full shadow-xl z-20 absolute right-0 top-0 bottom-0">
            <div className="p-4 border-b flex justify-between items-center bg-gray-50">
                <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                    <Clock className="w-4 h-4" /> Execution History
                </h3>
                <div className="flex gap-2">
                    <Button variant="ghost" size="icon" onClick={fetchLogs} disabled={loading}>
                        <RefreshCcw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
                    </Button>
                    <Button variant="ghost" size="icon" onClick={onClose}>
                        <span className="text-xl">×</span>
                    </Button>
                </div>
            </div>

            <ScrollArea className="flex-1 p-4">
                {logs.length === 0 && !loading ? (
                    <div className="text-center text-gray-500 mt-10">No logs found yet.</div>
                ) : (
                    <div className="space-y-3">
                        {logs.map(log => (
                            <div
                                key={log.id}
                                className={`border rounded-lg p-3 text-sm cursor-pointer hover:bg-gray-50 transition-colors ${selectedLog?.id === log.id ? 'ring-2 ring-blue-500 bg-blue-50' : ''}`}
                                onClick={() => setSelectedLog(selectedLog?.id === log.id ? null : log)}
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div className="flex items-center gap-2">
                                        {log.status === 'COMPLETED' ? (
                                            <CheckCircle2 className="w-4 h-4 text-green-500" />
                                        ) : (
                                            <XCircle className="w-4 h-4 text-red-500" />
                                        )}
                                        <span className="font-medium">{log.step_id}</span>
                                    </div>
                                    <span className="text-xs text-gray-500">
                                        {format(new Date(log.created_at), 'HH:mm:ss')}
                                    </span>
                                </div>
                                <div className="flex justify-between text-xs text-gray-500">
                                    <span>Duration: {log.duration_ms.toFixed(0)}ms</span>
                                    <span className="capitalize">{log.status.toLowerCase()}</span>
                                </div>

                                {selectedLog?.id === log.id && (
                                    <div className="mt-3 pt-3 border-t space-y-2 animate-in slide-in-from-top-1 duration-200">
                                        {log.trigger_data && (
                                            <div>
                                                <div className="text-xs font-semibold text-gray-700 mb-1">Inputs:</div>
                                                <pre className="bg-gray-100 p-2 rounded text-[10px] overflow-x-auto">
                                                    {JSON.stringify(log.trigger_data, null, 2)}
                                                </pre>
                                            </div>
                                        )}
                                        {log.results && (
                                            <div>
                                                <div className="text-xs font-semibold text-gray-700 mb-1">Outputs:</div>
                                                <pre className="bg-gray-100 p-2 rounded text-[10px] overflow-x-auto">
                                                    {JSON.stringify(log.results, null, 2)}
                                                </pre>
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}
            </ScrollArea>
        </div>
    );
}
