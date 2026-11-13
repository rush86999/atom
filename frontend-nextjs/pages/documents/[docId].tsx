import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Spinner } from '../../components/ui/spinner';
import { ArrowLeft, Calendar, Download, FileText, User, Tag, Trash2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { Alert, AlertDescription } from '../../components/ui/alert';
import api from '../../lib/api';
import {
    deleteDocument,
    deleteFailureMessage,
    deleteSuccessMessage,
    DocumentDeleteError,
} from '../../lib/document-delete';

interface DocumentDetails {
    id: string;
    title: string;
    content: string;
    type: string;
    metadata: any;
    ingested_at: string;
}

export default function DocumentDetailsPage() {
    const router = useRouter();
    const { docId } = router.query;
    const [document, setDocument] = useState<DocumentDetails | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [exportFormat, setExportFormat] = useState<'text' | 'markdown' | 'json'>('text');
    const [exporting, setExporting] = useState(false);
    const [exportError, setExportError] = useState<string | null>(null);
    const [deleting, setDeleting] = useState(false);
    const [deleteNotice, setDeleteNotice] = useState<string | null>(null);

    useEffect(() => {
        if (!docId) return;

        const fetchDocument = async () => {
            try {
                const response = await api.get(`/api/documents/${docId}`);
                if (response.data.success) {
                    setDocument(response.data.data);
                } else {
                    setError(response.data.message || "Failed to load document");
                }
            } catch (err: any) {
                console.error("Error fetching document:", err);
                setError(err.response?.data?.message || "Failed to fetch document details");
            } finally {
                setLoading(false);
            }
        };

        fetchDocument();
    }, [docId]);

    const exportStoredText = async () => {
        if (!document || exporting) return;
        setExporting(true);
        setExportError(null);
        try {
            const response = await api.get(
                `/api/documents/${encodeURIComponent(document.id)}/export`,
                {
                    params: { format: exportFormat },
                    responseType: 'blob',
                },
            );
            const blob = response.data instanceof Blob
                ? response.data
                : new Blob([response.data]);
            const link = window.document.createElement('a');
            const url = window.URL.createObjectURL(blob);
            const extension = exportFormat === 'json'
                ? 'json'
                : exportFormat === 'markdown' ? 'md' : 'txt';
            const baseTitle = String(document.title || 'document')
                .replace(/\.[a-z0-9]{1,8}$/i, '')
                .replace(/[\\/:*?"<>|\r\n]+/g, '_')
                .trim()
                .slice(0, 100) || `document-${document.id.slice(0, 12)}`;
            link.href = url;
            link.download = `${baseTitle}.${extension}`;
            link.rel = 'noopener';
            window.document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err: any) {
            const detail = err?.response?.data?.detail;
            const message = typeof detail === 'string'
                ? detail
                : detail?.error?.message
                    || detail?.message
                    || 'The stored document could not be exported. Refresh and retry.';
            setExportError(message);
        } finally {
            setExporting(false);
        }
    };

    const handleDelete = async () => {
        if (!document || deleting) return;
        if (!window.confirm(`Delete "${document.title}"? This removes its searchable text and cannot be undone.`)) {
            return;
        }

        setDeleting(true);
        setDeleteNotice(null);
        try {
            const receipt = await deleteDocument(document.id);
            toast.success(deleteSuccessMessage(receipt.outcome));
            // The document is gone; return to the library instead of leaving
            // a page that can no longer be re-read.
            router.push('/documents');
        } catch (error) {
            const failure = error instanceof DocumentDeleteError
                ? error
                : new DocumentDeleteError({ outcome: 'unknown' });
            // Disclose the truth and stay put. Partial/unknown deletions are
            // do_not_repeat, so no automatic retry is attempted here.
            setDeleteNotice(deleteFailureMessage(failure.outcome));
            toast.error(failure.outcome === 'failed' ? 'Delete failed' : 'Deletion not confirmed');
        } finally {
            setDeleting(false);
        }
    };

    if (loading) {
        return (
            <div className="flex justify-center items-center h-[50vh]">
                <Spinner className="h-10 w-10 text-primary" />
            </div>
        );
    }

    if (error || !document) {
        return (
            <div className="p-6">
                <Alert variant="destructive">
                    <AlertDescription>{error || "Document not found"}</AlertDescription>
                </Alert>
                <Button
                    variant="outline"
                    className="mt-4"
                    onClick={() => router.back()}
                >
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Go Back
                </Button>
            </div>
        );
    }

    return (
        <>
            <Head>
                <title>{document.title} | Atom Knowledge Base</title>
            </Head>

            <div className="space-y-6 max-w-5xl mx-auto p-6">
                {/* Header */}
                <div className="flex items-center gap-4 mb-6">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => router.back()}
                        aria-label="Go back"
                        className="shrink-0"
                    >
                        <ArrowLeft className="h-6 w-6" />
                    </Button>
                    <div>
                        <h1 className="text-3xl font-bold tracking-tight text-foreground">
                            {document.title}
                        </h1>
                        <div className="flex items-center gap-3 mt-2 text-muted-foreground text-sm">
                            <Badge variant="secondary" className="uppercase">
                                {document.type}
                            </Badge>
                            <span className="flex items-center gap-1">
                                <Calendar className="h-3 w-3" />
                                {new Date(document.ingested_at).toLocaleDateString()}
                            </span>
                            {document.metadata?.author && (
                                <span className="flex items-center gap-1">
                                    <User className="h-3 w-3" />
                                    {document.metadata.author}
                                </span>
                            )}
                        </div>
                    </div>
                    <Button
                        type="button"
                        variant="outline"
                        className="ml-auto shrink-0 text-destructive"
                        data-testid="document-delete"
                        onClick={handleDelete}
                        disabled={deleting}
                    >
                        <Trash2 className="mr-2 h-4 w-4" />
                        {deleting ? 'Deleting…' : 'Delete'}
                    </Button>
                </div>

                {deleteNotice && (
                    <div
                        role="alert"
                        data-testid="document-delete-notice"
                        className="flex items-start gap-3 rounded-md bg-destructive/10 p-3 text-sm text-destructive"
                    >
                        <AlertCircle className="h-5 w-5 shrink-0" />
                        <p className="font-medium">{deleteNotice}</p>
                    </div>
                )}

                <div
                    className="flex flex-wrap items-end gap-2 rounded-md border bg-muted/20 p-3"
                    data-testid="document-export"
                >
                    <div className="space-y-1">
                        <p className="text-sm font-medium">Export stored text</p>
                        <p className="text-xs text-muted-foreground">
                            Downloads the extracted text Atom stores for this
                            document. Original file bytes are not included.
                        </p>
                    </div>
                    <label className="sr-only" htmlFor="document-export-format">
                        Export format
                    </label>
                    <select
                        id="document-export-format"
                        data-testid="document-export-format"
                        aria-label="Export format"
                        className="rounded border bg-background px-2 py-1 text-sm"
                        value={exportFormat}
                        onChange={(event) =>
                            setExportFormat(event.target.value as 'text' | 'markdown' | 'json')
                        }
                        disabled={exporting}
                    >
                        <option value="text">Text (.txt)</option>
                        <option value="markdown">Markdown (.md)</option>
                        <option value="json">JSON (.json)</option>
                    </select>
                    <Button
                        type="button"
                        variant="outline"
                        data-testid="document-export-submit"
                        onClick={exportStoredText}
                        disabled={exporting}
                    >
                        <Download className="mr-2 h-4 w-4" />
                        {exporting ? 'Exporting…' : 'Download'}
                    </Button>
                    {exportError && (
                        <p
                            data-testid="document-export-error"
                            className="w-full text-sm text-red-700"
                        >
                            {exportError}
                        </p>
                    )}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Main Content */}
                    <div className="lg:col-span-2 space-y-6">
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <FileText className="h-5 w-5" />
                                    Document Content
                                </CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="prose dark:prose-invert max-w-none whitespace-pre-wrap font-mono text-sm bg-muted/30 p-4 rounded-md">
                                    {document.content}
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* Sidebar / Metadata */}
                    <div className="space-y-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Metadata</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <p className="text-sm font-medium">Source</p>
                                    <p className="text-sm text-muted-foreground break-all">
                                        {document.metadata?.source || "Unknown"}
                                    </p>
                                </div>
                                <div className="space-y-2">
                                    <p className="text-sm font-medium">ID</p>
                                    <p className="text-xs font-mono text-muted-foreground break-all bg-muted p-1 rounded">
                                        {document.id}
                                    </p>
                                </div>
                                {document.metadata && Object.entries(document.metadata).map(([key, value]) => {
                                    if (key === 'title' || key === 'source' || key === 'doc_id' || key === 'ingested_at' || key.startsWith('_')) return null;
                                    return (
                                        <div key={key} className="space-y-1">
                                            <p className="text-sm font-medium capitalize">{key.replace(/_/g, ' ')}</p>
                                            <p className="text-sm text-muted-foreground truncate">
                                                {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                            </p>
                                        </div>
                                    );
                                })}
                            </CardContent>
                        </Card>
                    </div>
                </div>
            </div>
        </>
    );
}
