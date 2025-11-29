import React, { useState, useEffect } from 'react';
import { Eye, Clock, CheckCircle, AlertTriangle } from 'lucide-react';
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface Execution {
    execution_id: string;
    workflow_id: string;
    status: 'success' | 'failed' | 'running' | 'completed';
    start_time: string;
    end_time?: string;
    duration_ms?: number;
    actions_executed: string[];
    errors: string[];
}

interface ExecutionHistoryListProps {
    workflowId: string;
    onSelectExecution: (executionId: string) => void;
    refreshTrigger?: number;
}

const ExecutionHistoryList: React.FC<ExecutionHistoryListProps> = ({
    workflowId,
    onSelectExecution,
    refreshTrigger
}) => {
    const [executions, setExecutions] = useState<Execution[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchHistory = async () => {
        if (!workflowId) return;

        try {
            setLoading(true);
            const response = await fetch(`/api/v1/workflows/${workflowId}/executions`);
            if (!response.ok) {
                throw new Error('Failed to fetch execution history');
            }
            const data = await response.json();
            setExecutions(data);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [workflowId, refreshTrigger]);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'success':
            case 'completed':
                return 'default';
            case 'failed':
                return 'destructive';
            case 'running':
                return 'default';
            default:
                return 'secondary';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'success':
            case 'completed':
                return <CheckCircle className="w-4 h-4 text-green-500" />;
            case 'failed':
                return <AlertTriangle className="w-4 h-4 text-red-500" />;
            case 'running':
                return <div className="animate-spin h-4 w-4 border-2 border-blue-500 border-t-transparent rounded-full" />;
            default:
                return <Clock className="w-4 h-4 text-gray-500" />;
        }
    };

    const formatDuration = (ms?: number) => {
        if (!ms) return '-';
        if (ms < 1000) return `${Math.round(ms)}ms`;
        return `${(ms / 1000).toFixed(2)}s`;
    };

    const formatDate = (dateStr: string) => {
        return new Date(dateStr).toLocaleString();
    };

    if (loading && executions.length === 0) {
        return (
            <div className="flex justify-center items-center h-48">
                <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="p-4 text-red-500 text-center">
                <AlertTriangle className="w-6 h-6 mx-auto mb-2" />
                <p>Error loading history: {error}</p>
            </div>
        );
    }

    if (executions.length === 0) {
        return (
            <div className="p-8 text-center text-muted-foreground">
                <Clock className="w-8 h-8 mx-auto mb-2" />
                <p>No execution history found for this workflow.</p>
                <p className="text-sm">Run the workflow to see results here.</p>
            </div>
        );
    }

    return (
        <div className="overflow-x-auto">
            <Table>
                <TableHeader>
                    <TableRow>
                        <TableHead>Status</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Duration</TableHead>
                        <TableHead>Actions</TableHead>
                        <TableHead>Details</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {executions.map((exec) => (
                        <TableRow
                            key={exec.execution_id}
                            className="hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
                            onClick={() => onSelectExecution(exec.execution_id)}
                        >
                            <TableCell>
                                <div className="flex items-center gap-2">
                                    {getStatusIcon(exec.status)}
                                    <Badge
                                        variant={getStatusColor(exec.status)}
                                        className={
                                            exec.status === 'success' || exec.status === 'completed'
                                                ? 'bg-green-500 hover:bg-green-600'
                                                : exec.status === 'running'
                                                    ? 'bg-blue-500 hover:bg-blue-600'
                                                    : ''
                                        }
                                    >
                                        {exec.status}
                                    </Badge>
                                </div>
                            </TableCell>
                            <TableCell>{formatDate(exec.start_time)}</TableCell>
                            <TableCell>{formatDuration(exec.duration_ms)}</TableCell>
                            <TableCell>{exec.actions_executed?.length || 0} nodes</TableCell>
                            <TableCell>
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onSelectExecution(exec.execution_id);
                                    }}
                                >
                                    <Eye className="w-4 h-4" />
                                </Button>
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </div>
    );
};

export default ExecutionHistoryList;
