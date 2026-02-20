import React, { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';
import Layout from '../components/layout/Layout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Upload, FileText, CheckCircle, AlertCircle, Search, RefreshCw, File } from 'lucide-react';
import { toast } from 'sonner';
import api from '../lib/api';

export default function DocumentsPage() {
    const router = useRouter();
    const [isUploading, setIsUploading] = useState(false);
    const [dragActive, setDragActive] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null);

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
    }, []);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        e.preventDefault();
        if (e.target.files && e.target.files[0]) {
            handleFile(e.target.files[0]);
        }
    };

    const [documents, setDocuments] = useState<any[]>([]);
    const [loadingDocs, setLoadingDocs] = useState(true);

    useEffect(() => {
        fetchDocuments();
    }, []);

    const fetchDocuments = async () => {
        try {
            const response = await api.get('/api/documents');
            if (response.data.success) {
                setDocuments(response.data.data);
            }
        } catch (error) {
            console.error("Failed to fetch documents", error);
            toast.error("Failed to load documents");
        } finally {
            setLoadingDocs(false);
        }
    };

    const handleFile = async (file: File) => {
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
            });

            setUploadStatus({
                type: 'success',
                message: `Successfully uploaded "${file.name}". It is now searchable.`
            });
            toast.success("Document uploaded successfully");
            fetchDocuments(); // Refresh list

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
    };

    return (
        <Layout>
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
                                Supported formats: PDF, DOCX, TXT, MD
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
                                    accept=".pdf,.docx,.txt,.md"
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
                                            PDF, DOCX, TXT or MD (MAX. 10MB)
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
                            <CardTitle>Search & Verify</CardTitle>
                            <CardDescription>
                                Test your uploaded documents immediately.
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
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
                        </CardContent>
                    </Card>
                </div>

                {/* Documents List */}
                <div className="space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-xl font-bold tracking-tight">Your Documents</h2>
                        <Button variant="ghost" size="sm" onClick={fetchDocuments} disabled={loadingDocs}>
                            <RefreshCw className={`h-4 w-4 mr-2 ${loadingDocs ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </div>

                    {documents.length === 0 && !loadingDocs ? (
                        <Card>
                            <CardContent className="flex flex-col items-center justify-center p-12 text-center text-muted-foreground">
                                <FileText className="h-12 w-12 mb-4 opacity-20" />
                                <p>No documents uploaded yet.</p>
                            </CardContent>
                        </Card>
                    ) : (
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
                                        <File className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
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
                    )}
                </div>
            </div>
        </Layout>
    );
}
