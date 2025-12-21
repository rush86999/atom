import React, { useEffect, useState } from 'react';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface AgentJob {
    id: string;
    agent_id: string;
    status: string;
    start_time: string;
    end_time: string;
    logs: string;
    result_summary: string;
}

export const AgentHistoryTable: React.FC = () => {
    const [jobs, setJobs] = useState<AgentJob[]>([]);

    useEffect(() => {
        fetchHistory();
        const interval = setInterval(fetchHistory, 5000); // Auto-refresh
        return () => clearInterval(interval);
    }, []);

    const fetchHistory = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/agents/history');
            if (res.ok) {
                const data = await res.json();
                setJobs(data);
            }
        } catch (error) {
            console.error("Failed to fetch history", error);
        }
    };

    return (
        <Card className="h-full border-gray-200">
            <CardHeader>
                <CardTitle>Execution History</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border h-96 overflow-y-auto">
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
                                <TableRow key={job.id}>
                                    <TableCell className="font-medium">{job.agent_id}</TableCell>
                                    <TableCell>
                                        <Badge variant={
                                            job.status === 'success' ? 'default' :
                                                job.status === 'failed' ? 'destructive' :
                                                    job.status === 'running' ? 'secondary' : 'outline'
                                        }>
                                            {job.status.toUpperCase()}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>{new Date(job.start_time).toLocaleString()}</TableCell>
                                    <TableCell className="max-w-[200px] truncate" title={job.result_summary || job.logs}>
                                        {job.result_summary || job.logs || "-"}
                                    </TableCell>
                                </TableRow>
                            ))}
                            {jobs.length === 0 && (
                                <TableRow>
                                    <TableCell colSpan={4} className="text-center h-24 text-muted-foreground">
                                        No history available.
                                    </TableCell>
                                </TableRow>
                            )}
                        </TableBody>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
};
