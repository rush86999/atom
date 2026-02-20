import React, { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Layout from '../../components/layout/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Spinner } from '../../components/ui/spinner';
import { ArrowLeft, Calendar, FileText, User, Tag } from 'lucide-react';
import { Alert, AlertDescription } from '../../components/ui/alert';
import api from '../../lib/api';

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

    if (loading) {
        return (
            <Layout>
                <div className="flex justify-center items-center h-[50vh]">
                    <Spinner className="h-10 w-10 text-primary" />
                </div>
            </Layout>
        );
    }

    if (error || !document) {
        return (
            <Layout>
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
            </Layout>
        );
    }

    return (
        <Layout>
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
                            {document.metadata.author && (
                                <span className="flex items-center gap-1">
                                    <User className="h-3 w-3" />
                                    {document.metadata.author}
                                </span>
                            )}
                        </div>
                    </div>
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
                                        {document.metadata.source || "Unknown"}
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
        </Layout>
    );
}
