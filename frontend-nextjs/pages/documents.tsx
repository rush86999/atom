import React, { useState, useEffect, useCallback, useRef } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Upload, FileText, CheckCircle, AlertCircle, Search, RefreshCw, File, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';
import {
    deleteDocument,
    deleteFailureMessage,
    deleteSuccessMessage,
    DocumentDeleteError,
} from '../lib/document-delete';
import { useProductProfile } from '../lib/product-profile';

const PAGE_SIZE = 100;

type DocumentsMetadata = {
    total?: number;
    count?: number;
    limit?: number;
    offset?: number;
    has_more?: boolean;
    next_offset?: number;
    previous_offset?: number;
    stale_page?: boolean;
};

export default function DocumentsPage() {
    const router = useRouter();
    const { isCapabilityEnabled } = useProductProfile();
    const searchEnabled = isCapabilityEnabled('search');
    const [isUploading, setIsUploading] = useState(false);
    const [dragActive, setDragActive] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);
    const [documents, setDocuments] = useState<any[]>([]);
    const [loadingDocs, setLoadingDocs] = useState(true);
    const [docsError, setDocsError] = useState<string | null>(null);
    const [offset, setOffset] = useState(0);
    const [total, setTotal] = useState(0);
    const [hasMore, setHasMore] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    // `unreconciledIds` are documents whose deletion came back partial or
    // unknown. The mutation must not be repeated blindly, so their delete
    // control stays disabled until the user refreshes the list.
    const [unreconciledIds, setUnreconciledIds] = useState<string[]>([]);
    const [deleteNotice, setDeleteNotice] = useState<{ tone: 'success' | 'error'; message: string } | null>(null);
    const requestSeq = useRef(0);

    const fetchDocuments = useCallback(async (nextOffset: number) => {
        const seq = ++requestSeq.current;
        setLoadingDocs(true);
        setDocsError(null);
        try {
            const response = await api.get('/api/documents', {
                params: { limit: PAGE_SIZE, offset: nextOffset },
                validateStatus: (status) => status < 500,
            });
            if (seq !== requestSeq.current) return;

            if (response.status === 200 && response.data?.success) {
                const items = Array.isArray(response.data.data) ? response.data.data : [];
                const metadata: DocumentsMetadata = response.data.metadata || {};
                const nextTotal = typeof metadata.total === 'number' ? metadata.total : items.length;
                const resolvedOffset = typeof metadata.offset === 'number' ? metadata.offset : nextOffset;
                setDocuments(items);
                setOffset(resolvedOffset);
                setTotal(nextTotal);
                setHasMore(Boolean(metadata.has_more));
            } else {
                const detail = response.data?.detail;
                const message = typeof detail === 'string'
                    ? detail
                    : detail?.message || response.data?.message || 'Could not load documents.';
                setDocuments([]);
                setDocsError(message);
            }
        } catch (error) {
            if (seq === requestSeq.current) {
                console.error("Failed to fetch documents", error);
                setDocuments([]);
                setDocsError('Could not load documents. Please retry.');
            }
        } finally {
            if (seq === requestSeq.current) setLoadingDocs(false);
        }
    }, []);

    const handleFile = useCallback(async (file: File) => {
        setIsUploading(true);
        setUploadStatus(null);

        // Create FormData
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await api.post('/api/documents/upload', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
                validateStatus: (status) => status < 500,
            });

            if (response.status < 300) {
                setUploadStatus({
                    type: 'success',
                    message: `Successfully uploaded "${file.name}". It is now available to your agent.`
                });
                toast.success("Document uploaded successfully");
                // A new upload belongs on the first page of the newest-first
                // ordering, so reset pagination instead of refreshing a later
                // offset whose contents may have shifted.
                void fetchDocuments(0);
            } else {
                setUploadStatus({
                    type: 'error',
                    message: response.data?.detail || "Failed to upload document."
                });
                toast.error("Upload failed");
            }
        } catch (error: any) {
            console.error("Upload failed", error);
            setUploadStatus({
                type: 'error',
                message: error.response?.data?.detail || "Failed to upload document."
            });
            toast.error("Upload failed");
        } finally {
            setIsUploading(false);
        }
    }, [fetchDocuments]);

    const dropDocumentLocally = useCallback((docId: string) => {
        setDocuments((current) => current.filter((item) => item.id !== docId));
        setTotal((current) => Math.max(0, current - 1));
        setUnreconciledIds((current) => current.filter((id) => id !== docId));
    }, []);

    const handleDelete = useCallback(async (event: React.MouseEvent, doc: any) => {
        // The card itself opens the document; a delete must not navigate.
        event.stopPropagation();
        if (deletingId) return;
        if (!window.confirm(`Delete "${doc.title}"? This removes its searchable text and cannot be undone.`)) {
            return;
        }

        setDeletingId(doc.id);
        setDeleteNotice(null);
        try {
            const receipt = await deleteDocument(doc.id);
            dropDocumentLocally(doc.id);
            const message = deleteSuccessMessage(receipt.outcome);
            setDeleteNotice({ tone: 'success', message });
            toast.success(message);
            // Re-fetch the current page so rows shifted in from the next page
            // are shown. The existing offset-fallback effect handles the case
            // where this was the last row on a later page.
            void fetchDocuments(offset);
        } catch (error) {
            const failure = error instanceof DocumentDeleteError
                ? error
                : new DocumentDeleteError({ outcome: 'unknown' });
            if (failure.outcome === 'not_found') {
                // Definitively absent: the row is stale, so drop it. This is
                // not a claim that this request deleted it.
                dropDocumentLocally(doc.id);
            } else if (failure.outcome === 'partial' || failure.outcome === 'unknown') {
                // Unknown effect: keep the row and disable its delete control.
                setUnreconciledIds((current) =>
                    current.includes(doc.id) ? current : [...current, doc.id],
                );
            }
            // No automatic retry and no refetch for partial/unknown — the
            // backend marks the operation do_not_repeat. Refreshing is the
            // user's explicit reconciliation step.
            setDeleteNotice({ tone: 'error', message: deleteFailureMessage(failure.outcome) });
            toast.error(failure.outcome === 'failed' ? 'Delete failed' : 'Deletion not confirmed');
        } finally {
            setDeletingId(null);
        }
    }, [deletingId, dropDocumentLocally, fetchDocuments, offset]);

    const handleDrag = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (e.type === 'dragenter' || e.type === 'dragover') {
            setDragActive(true);
        } else if (e.type === 'dragleave') {
            setDragActive(false);
        }
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        setDragActive(false);
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
            handleFile(e.dataTransfer.files[0]);
        }
    }, [handleFile]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            handleFile(e.target.files[0]);
        }
    };

    useEffect(() => {
        void fetchDocuments(0);
    }, [fetchDocuments]);

    // A delete performed on another surface can leave the current offset
    // beyond the new end. Fall back to the previous page instead of showing a
    // false "empty library" for a non-empty workspace.
    useEffect(() => {
        if (!loadingDocs && documents.length === 0 && offset > 0 && total > 0) {
            void fetchDocuments(Math.max(0, offset - PAGE_SIZE));
        }
    }, [documents.length, loadingDocs, offset, total, fetchDocuments]);

    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const currentPage = Math.floor(offset / PAGE_SIZE) + 1;
    const rangeStart = documents.length === 0 ? 0 : offset + 1;
    const rangeEnd = documents.length === 0 ? 0 : offset + documents.length;

    return (
        <>
            <Head>
                <title>Knowledge Base | Atom</title>
            </Head>

            <div className="space-y-6">
                <div>
                    <h1 className="text-3xl font-bold tracking-tight text-foreground">Knowledge Base</h1>
                    <p className="text-muted-foreground mt-2">
                        Upload documents to your knowledge base to make them searchable by Atom agents.
                    </p>
                </div>

                <div className="grid gap-6 md:grid-cols-2">
                    {/* Upload Area */}
                    <Card>
                        <CardHeader>
                            <CardTitle>Upload Document</CardTitle>
                            <CardDescription>
                                Supported formats: PDF, DOCX, TXT, MD, CSV, XLSX
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            <div
                                className={`
                  border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors
                  ${dragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}
                  ${isUploading ? 'opacity-50 pointer-events-none' : ''}
                `}
                                onDragEnter={handleDrag}
                                onDragLeave={handleDrag}
                                onDragOver={handleDrag}
                                onDrop={handleDrop}
                                onClick={() => document.getElementById('file-upload')?.click()}
                            >
                                <input
                                    id="file-upload"
                                    type="file"
                                    className="hidden"
                                    onChange={handleChange}
                                    accept=".pdf,.docx,.txt,.md,.csv,.xlsx,.xls"
                                />

                                <div className="flex flex-col items-center justify-center gap-4">
                                    <div className="p-4 bg-muted rounded-full">
                                        {isUploading ? (
                                            <RefreshCw className="h-8 w-8 animate-spin text-primary" />
                                        ) : (
                                            <Upload className="h-8 w-8 text-primary" />
                                        )}
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-lg">
                                            {isUploading ? "Uploading..." : "Click to upload or drag and drop"}
                                        </h3>
                                        <p className="text-sm text-muted-foreground mt-1">
                                            PDF, DOCX, TXT, MD, CSV or XLSX (MAX. 50MB)
                                        </p>
                                    </div>
                                </div>
                            </div>

                            {uploadStatus && (
                                <div className={`mt-6 p-4 rounded-md flex items-start gap-3 ${uploadStatus.type === 'success' ? 'bg-green-500/10 text-green-600' : 'bg-destructive/10 text-destructive'
                                    }`}>
                                    {uploadStatus.type === 'success' ? (
                                        <CheckCircle className="h-5 w-5 shrink-0" />
                                    ) : (
                                        <AlertCircle className="h-5 w-5 shrink-0" />
                                    )}
                                    <p className="text-sm font-medium">{uploadStatus.message}</p>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Quick Actions / Status */}
                    <Card>
                        <CardHeader>
                            <CardTitle>{searchEnabled ? 'Search & Verify' : 'Search'}</CardTitle>
                            <CardDescription>
                                {searchEnabled
                                    ? 'Test your uploaded documents immediately.'
                                    : 'Search is not part of this release.'}
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            {searchEnabled ? (
                                <>
                                    <div className="bg-muted/50 p-4 rounded-lg">
                                        <h4 className="font-medium flex items-center gap-2 mb-2">
                                            <FileText className="h-4 w-4" />
                                            How it works
                                        </h4>
                                        <ul className="text-sm text-muted-foreground space-y-2 list-disc pl-5">
                                            <li>Documents are parsed and split into chunks.</li>
                                            <li>Chunks are embedded using AI models.</li>
                                            <li>They are stored in LanceDB for semantic search.</li>
                                            <li>Agents can access this knowledge immediately.</li>
                                        </ul>
                                    </div>

                                    <Button
                                        className="w-full"
                                        variant="outline"
                                        onClick={() => router.push('/search')}
                                    >
                                        <Search className="mr-2 h-4 w-4" />
                                        Go to Search Page
                                    </Button>
                                </>
                            ) : (
                                <>
                                    <p className="text-sm text-muted-foreground">
                                        Cross-surface search is deferred in this release.
                                        Your uploaded documents remain available to your
                                        agent in Chat.
                                    </p>
                                    <Button
                                        className="w-full"
                                        onClick={() => router.push('/chat')}
                                    >
                                        <FileText className="mr-2 h-4 w-4" />
                                        Ask in Chat
                                    </Button>
                                    <Button
                                        className="w-full"
                                        variant="outline"
                                        onClick={() => router.push('/agents')}
                                    >
                                        <Search className="mr-2 h-4 w-4" />
                                        Open Agents
                                    </Button>
                                </>
                            )}
                        </CardContent>
                    </Card>
                </div>

                {/* Documents List */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-bold tracking-tight">Your Documents</h2>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => void fetchDocuments(offset)}
                            disabled={loadingDocs}
                        >
                            <RefreshCw className={`h-4 w-4 mr-2 ${loadingDocs ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </div>

                    {deleteNotice && (
                        <div
                            data-testid="documents-delete-notice"
                            role={deleteNotice.tone === 'error' ? 'alert' : 'status'}
                            className={`flex items-start gap-3 rounded-md p-3 text-sm ${deleteNotice.tone === 'success'
                                ? 'bg-green-500/10 text-green-600'
                                : 'bg-destructive/10 text-destructive'
                                }`}
                        >
                            {deleteNotice.tone === 'success' ? (
                                <CheckCircle className="h-5 w-5 shrink-0" />
                            ) : (
                                <AlertCircle className="h-5 w-5 shrink-0" />
                            )}
                            <p className="font-medium">{deleteNotice.message}</p>
                        </div>
                    )}

                    {docsError ? (
                        <Card data-testid="documents-error">
                            <CardContent className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
                                <AlertCircle className="h-12 w-12 mb-4 text-destructive" />
                                <p>{docsError}</p>
                                <Button
                                    className="mt-4"
                                    variant="outline"
                                    onClick={() => void fetchDocuments(offset)}
                                    disabled={loadingDocs}
                                >
                                    Retry
                                </Button>
                            </CardContent>
                        </Card>
                    ) : loadingDocs && documents.length === 0 ? (
                        <Card data-testid="documents-loading">
                            <CardContent className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
                                <RefreshCw className="h-8 w-8 mb-4 animate-spin text-primary" />
                                <p>Loading documents…</p>
                            </CardContent>
                        </Card>
                    ) : documents.length === 0 ? (
                        <Card data-testid="documents-empty">
                            <CardContent className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
                                <FileText className="h-12 w-12 mb-4 opacity-20" />
                                <p>
                                    {total === 0
                                        ? 'No documents uploaded yet.'
                                        : 'No documents on this page.'}
                                </p>
                                {total > 0 && (
                                    <Button
                                        className="mt-4"
                                        variant="outline"
                                        onClick={() => void fetchDocuments(0)}
                                        disabled={loadingDocs}
                                    >
                                        Back to first page
                                    </Button>
                                )}
                            </CardContent>
                        </Card>
                    ) : (
                        <>
                            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                                {documents.map((doc) => (
                                    <Card
                                        key={doc.id}
                                        className="cursor-pointer hover:border-primary transition-colors group"
                                        onClick={() => router.push(`/documents/${doc.id}`)}
                                    >
                                        <CardHeader className="flex flex-row items-top justify-between space-y-0 pb-2">
                                            <CardTitle className="text-sm font-medium leading-none truncate pr-4">
                                                {doc.title}
                                            </CardTitle>
                                            <div className="flex items-center gap-1">
                                                <File className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                                                <Button
                                                    type="button"
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-7 w-7 shrink-0 text-muted-foreground hover:text-destructive"
                                                    aria-label={`Delete ${doc.title}`}
                                                    title={unreconciledIds.includes(doc.id)
                                                        ? 'Deletion not verified — refresh the list before trying again'
                                                        : 'Delete document'}
                                                    data-testid={`delete-document-${doc.id}`}
                                                    disabled={deletingId !== null || unreconciledIds.includes(doc.id)}
                                                    onClick={(event) => void handleDelete(event, doc)}
                                                >
                                                    {deletingId === doc.id ? (
                                                        <RefreshCw className="h-4 w-4 animate-spin" />
                                                    ) : (
                                                        <Trash2 className="h-4 w-4" />
                                                    )}
                                                </Button>
                                            </div>
                                        </CardHeader>
                                        <CardContent>
                                            <div className="text-xs text-muted-foreground line-clamp-3 mb-4">
                                                {doc.text_preview}
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                {new Date(doc.created_at).toLocaleDateString()}
                                            </p>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>

                            <div
                                className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
                                data-testid="documents-pagination"
                            >
                                <p className="text-sm text-muted-foreground" data-testid="documents-range">
                                    Showing {rangeStart}–{rangeEnd} of {total}
                                </p>
                                <div className="flex items-center gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        data-testid="documents-previous"
                                        onClick={() => void fetchDocuments(Math.max(0, offset - PAGE_SIZE))}
                                        disabled={loadingDocs || offset === 0}
                                    >
                                        Previous
                                    </Button>
                                    <span className="text-sm text-muted-foreground" data-testid="documents-page">
                                        Page {currentPage} of {pageCount}
                                    </span>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        data-testid="documents-next"
                                        onClick={() => void fetchDocuments(offset + PAGE_SIZE)}
                                        disabled={loadingDocs || !hasMore}
                                    >
                                        Next
                                    </Button>
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </>
    );
}
