import React, { useState, useEffect } from 'react';
import { ArrowLeft, CheckCircle, AlertTriangle, Clock, Download, Loader2 } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "@/components/ui/accordion";

interface ExecutionDetailViewProps {
    executionId: string;
    onBack: () => void;
}

interface ExecutionDetail {
    execution_id: string;
    workflow_id: string;
    status: string;
    start_time: string;
    end_time?: string;
    duration_ms?: number;
    results: Record<string, any>;
    errors: string[];
    trigger_data: any;
}

const ExecutionDetailView: React.FC<ExecutionDetailViewProps> = ({ executionId, onBack }) => {
    const [detail, setDetail] = useState<ExecutionDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [exporting, setExporting] = useState(false);
    const [exportError, setExportError] = useState<string | null>(null);

    useEffect(() => {
        const fetchDetail = async () => {
            try {
                setLoading(true);
                const response = await fetch(`/api/v1/workflows/executions/${executionId}`);
                if (!response.ok) {
                    throw new Error('Failed to fetch execution details');
                }
                const data = await response.json();
                setDetail(data);
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Unknown error');
            } finally {
                setLoading(false);
            }
        };

        if (executionId) {
            fetchDetail();
        }
    }, [executionId]);

    if (loading) {
        return (
            <div className="text-center py-10">
                <div className="animate-spin h-8 w-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto" />
                <p className="mt-4 text-muted-foreground">Loading execution details...</p>
            </div>
        );
    }

    if (error || !detail) {
        return (
            <div className="p-4">
                <Button onClick={onBack} variant="outline" className="mb-4">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to History
                </Button>
                <Alert variant="destructive">
                    <AlertTriangle className="h-4 w-4" />
                    <AlertDescription>{error || 'Execution not found'}</AlertDescription>
                </Alert>
            </div>
        );
    }

    const handleExport = async () => {
        if (!detail || exporting) return;
        setExportError(null);
        setExporting(true);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(
                `/api/v1/workflows/workflows/executions/${encodeURIComponent(detail.execution_id)}/export`,
                {
                    method: 'GET',
                    headers: token ? { Authorization: `Bearer ${token}` } : {},
                },
            );
            if (!response.ok) {
                let message = `Download failed (HTTP ${response.status})`;
                try {
                    const data = await response.json();
                    message = data?.detail?.message || data?.detail?.error
                        || data?.message || message;
                } catch {
                    // non-JSON refusal
                }
                setExportError(message);
                return;
            }
            const blob = await response.blob();
            const disposition = response.headers.get('content-disposition') || '';
            const match = /filename="?([^";]+)"?/i.exec(disposition);
            const fallback = `workflow-${String(detail.workflow_id || 'workflow').replace(/[^A-Za-z0-9_-]+/g, '-').slice(0, 48)}-execution-${String(detail.execution_id).replace(/[^A-Za-z0-9_-]+/g, '-').slice(0, 48)}.json`;
            const filename = (match?.[1] || fallback)
                .replace(/[\\/:*?"<>|\r\n]+/g, '_')
                .slice(0, 160);
            const url = window.URL.createObjectURL(blob);
            const link = window.document.createElement('a');
            link.href = url;
            link.download = filename;
            link.rel = 'noopener';
            window.document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            setExportError(
                err instanceof Error
                    ? err.message
                    : 'The execution result could not be downloaded. Refresh and retry.',
            );
        } finally {
            setExporting(false);
        }
    };

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'success':
            case 'completed':
                return 'bg-green-500 hover:bg-green-600';
            case 'failed':
                return 'bg-red-500 hover:bg-red-600';
            case 'running':
                return 'bg-blue-500 hover:bg-blue-600';
            default:
                return '';
        }
    };

    return (
        <div>
            <Button onClick={onBack} variant="outline" size="sm" className="mb-4">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to History
            </Button>

            <div className="space-y-6">
                {/* Header Info */}
                <Card>
                    <CardContent className="pt-6 space-y-4">
                        <div className="flex justify-between items-center">
                            <h2 className="text-xl font-semibold">Execution Details</h2>
                            <div className="flex items-center gap-2">
                                <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={handleExport}
                                    disabled={
                                        exporting ||
                                        !['completed', 'success'].includes(
                                            String(detail.status || '').toLowerCase(),
                                        )
                                    }
                                    title={
                                        ['completed', 'success'].includes(
                                            String(detail.status || '').toLowerCase(),
                                        )
                                            ? 'Download the completed execution results as JSON'
                                            : 'Only a completed execution has downloadable results'
                                    }
                                >
                                    {exporting ? (
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    ) : (
                                        <Download className="mr-2 h-4 w-4" />
                                    )}
                                    Download results
                                </Button>
                                <Badge className={getStatusColor(detail.status)}>
                                    {detail.status.toUpperCase()}
                                </Badge>
                            </div>
                        </div>

                        {exportError && (
                            <Alert variant="destructive">
                                <AlertTriangle className="h-4 w-4" />
                                <AlertDescription>{exportError}</AlertDescription>
                            </Alert>
                        )}

                        <div className="flex gap-8">
                            <div>
                                <p className="text-sm text-muted-foreground">Started</p>
                                <p className="font-medium">{new Date(detail.start_time).toLocaleString()}</p>
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">Duration</p>
                                <p className="font-medium">
                                    {detail.duration_ms ? `${(detail.duration_ms / 1000).toFixed(2)}s` : '-'}
                                </p>
                            </div>
                            <div>
                                <p className="text-sm text-muted-foreground">ID</p>
                                <p className="font-mono text-sm">{detail.execution_id}</p>
                            </div>
                        </div>

                        {detail.errors && detail.errors.length > 0 && (
                            <Alert variant="destructive">
                                <AlertTriangle className="h-4 w-4" />
                                <AlertDescription>
                                    <p className="font-bold">Execution Errors:</p>
                                    <div className="space-y-1">
                                        {detail.errors.map((err, idx) => (
                                            <p key={idx} className="text-sm">{err}</p>
                                        ))}
                                    </div>
                                </AlertDescription>
                            </Alert>
                        )}
                    </CardContent>
                </Card>

                {/* Trigger Data */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Trigger Data</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="bg-gray-50 dark:bg-gray-900 p-3 rounded-md overflow-x-auto">
                            <pre className="text-sm">
                                {JSON.stringify(detail.trigger_data, null, 2)}
                            </pre>
                        </div>
                    </CardContent>
                </Card>

                {/* Node Results */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Node Execution Results</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <Accordion type="multiple" defaultValue={["0"]}>
                            {Object.entries(detail.results || {}).map(([nodeId, result]: [string, any], index) => (
                                <AccordionItem key={nodeId} value={index.toString()}>
                                    <AccordionTrigger>
                                        <div className="flex items-center gap-2">
                                            {result.status === 'success' ? (
                                                <CheckCircle className="w-4 h-4 text-green-500" />
                                            ) : result.status === 'failed' ? (
                                                <AlertTriangle className="w-4 h-4 text-red-500" />
                                            ) : (
                                                <Clock className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                                            )}
                                            <span className="font-medium">{result.node_title || nodeId}</span>
                                            <Badge variant="secondary" className={getStatusColor(result.status)}>
                                                {result.status}
                                            </Badge>
                                        </div>
                                    </AccordionTrigger>
                                    <AccordionContent>
                                        <div className="space-y-3 pt-2">
                                            <div>
                                                <p className="text-xs font-bold text-muted-foreground mb-1">OUTPUT</p>
                                                <div className="bg-gray-50 dark:bg-gray-900 p-2 rounded-md">
                                                    <pre className="text-xs whitespace-pre-wrap">
                                                        {JSON.stringify(result.output, null, 2)}
                                                    </pre>
                                                </div>
                                            </div>
                                            {result.error && (
                                                <div>
                                                    <p className="text-xs font-bold text-red-500 mb-1">ERROR</p>
                                                    <div className="bg-red-50 dark:bg-red-900/20 p-2 rounded-md text-red-700 dark:text-red-400">
                                                        <p className="text-sm">{result.error}</p>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </AccordionContent>
                                </AccordionItem>
                            ))}
                        </Accordion>
                        {(!detail.results || Object.keys(detail.results).length === 0) && (
                            <p className="text-muted-foreground italic">No node results recorded.</p>
                        )}
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default ExecutionDetailView;
