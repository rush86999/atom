import React, { useEffect, useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2 } from "lucide-react";

interface ExecutionJob {
    id: string;
    agent_id: string;
    agent_name?: string;
    status: string;
    started_at: string | null;
    completed_at: string | null;
    duration_seconds?: number | null;
    result_summary?: string;
    error_message?: string;
    triggered_by?: string;
}

// Renders the started_at timestamp in an ISO-8601 style ("2026-08-12 22:45")
// so it carries the calendar date AND time-of-day information. The backend
// emits naive UTC ISO strings ("2026-08-12T22:45:00" — no timezone suffix),
// which JS would otherwise parse as LOCAL time; append "Z" so the display
// stays in UTC and matches the stored value.
const formatTimestamp = (value: string | null | undefined): string => {
    if (!value) return "—";
    try {
        const hasTz = /(Z|[+-]\d{2}:?\d{2})$/.test(value);
        const date = new Date(hasTz ? value : `${value}Z`);
        if (Number.isNaN(date.getTime())) return value;
        return date.toISOString().replace('T', ' ').slice(0, 16);
    } catch {
        return value;
    }
};

export const AgentHistoryTable: React.FC = () => {
    const [jobs, setJobs] = useState<ExecutionJob[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        fetchHistory();
        const interval = setInterval(fetchHistory, 15000);
        return () => clearInterval(interval);
    }, []);

    const fetchHistory = async () => {
        try {
            setLoading(true);

            // NOTE: native fetch (not the shared apiClient) is used on purpose —
            // the repo's MSW test setup intercepts fetch but not axios' XHR
            // adapter, so apiClient calls hang in Jest.
            const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
            const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
            const headers = token ? { 'Authorization': `Bearer ${token}` } : {};

            const [historyRes, agentsRes] = await Promise.allSettled([
                fetch(`${API_BASE}/api/agents/history`, { headers }),
                fetch(`${API_BASE}/api/agents`, { headers }),
            ]);

            let history: any[] = [];
            if (historyRes.status === 'fulfilled' && historyRes.value.ok) {
                const data = await historyRes.value.json();
                history = Array.isArray(data) ? data : (data?.data || []);
            } else {
                throw new Error(
                    historyRes.status === 'rejected'
                        ? historyRes.reason?.message || 'Network error'
                        : `HTTP ${historyRes.value.status}`
                );
            }

            // Map agent ids to names so rows show a human-readable agent
            // (the /history endpoint only returns agent_id).
            const agentNames: Record<string, string> = {};
            if (agentsRes.status === 'fulfilled' && agentsRes.value.ok) {
                const data = await agentsRes.value.json();
                const agents: any[] = Array.isArray(data) ? data : (data?.data || []);
                agents.forEach((a: any) => {
                    if (a?.id) agentNames[a.id] = a.name || a.id;
                });
            }

            setJobs(history.map((job: any) => ({
                id: job.id,
                agent_id: job.agent_id,
                agent_name: agentNames[job.agent_id] || job.agent_id,
                status: job.status || 'unknown',
                started_at: job.started_at || job.start_time || null,
                completed_at: job.completed_at || job.end_time || null,
                duration_seconds: job.duration_seconds,
                result_summary: job.result_summary || job.logs || "",
                error_message: job.error_message,
                triggered_by: job.triggered_by,
            })));
            setError(null);
        } catch (err) {
            console.error("Failed to fetch history", err);
            setError("Failed to load execution history.");
        } finally {
            setLoading(false);
        }
    };

    const statusVariant = (status: string) => {
        switch (status) {
            case 'success': return 'default';
            case 'failed': case 'error': return 'destructive';
            case 'running': case 'blocked': return 'secondary';
            default: return 'outline';
        }
    };

    return (
        <Card className="h-full border-gray-200 dark:border-gray-700" data-testid="execution-history-container">
            <CardHeader>
                <CardTitle>Execution History</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border h-96 overflow-y-auto" data-testid="execution-history-list">
                    {loading && (
                        <div className="flex items-center justify-center gap-2 p-6 text-sm text-muted-foreground" data-testid="history-loading-spinner">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Loading history...
                        </div>
                    )}
                    {!loading && jobs.length === 0 && (
                        <div className="p-6 text-center text-sm text-muted-foreground" data-testid="empty-history-message">
                            No history available.
                        </div>
                    )}
                    {!loading && jobs.length > 0 && (
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Agent</TableHead>
                                    <TableHead>Status</TableHead>
                                    <TableHead>Start Time</TableHead>
                                    <TableHead>Result</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {jobs.map((job) => (
                                    <TableRow key={job.id} data-testid="execution-history-entry">
                                        <TableCell className="font-medium" data-testid="history-entry-agent">{job.agent_name}</TableCell>
                                        <TableCell>
                                            <Badge variant={statusVariant(job.status)} data-testid="history-entry-status">
                                                {job.status}
                                            </Badge>
                                        </TableCell>
                                        <TableCell data-testid="history-entry-timestamp">{formatTimestamp(job.started_at)}</TableCell>
                                        <TableCell className="max-w-[200px] truncate" title={job.result_summary || job.error_message || ""}>
                                            <span data-testid="history-entry-result">{job.result_summary || job.error_message || "-"}</span>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    )}
                    {error && (
                        <div className="p-4 text-center text-sm text-destructive" data-testid="execution-error-message">
                            {error}
                        </div>
                    )}
                </div>
            </CardContent>
        </Card>
    );
};

export default AgentHistoryTable;
