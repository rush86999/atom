'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { useToast } from '../ui/use-toast';
import { HardDrive, RefreshCw, Folder, File, Download, Search, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';

interface ZohoFile {
    id: string;
    name: string;
    type: string;
    extension?: string;
    size?: number;
    modified_at?: string;
}

interface ZohoTeam {
    id: string;
    attributes: {
        name: string;
    };
}

function extractErrorMessage(text: string, status: number): string {
    let errMsg = `Server returned ${status}`;
    try {
        const json = JSON.parse(text);
        const err = json.error || json.detail || json.message;
        if (typeof err === 'string') {
            return err;
        } else if (err && typeof err.message === 'string') {
            return err.message;
        } else if (Array.isArray(json.detail)) {
            return json.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
        } else if (err) {
            return JSON.stringify(err);
        }
    } catch (_) {}
    return errMsg;
}

export default function ZohoWorkDriveIngestion({ userId }: { userId: string }) {
    const [teams, setTeams] = useState<ZohoTeam[]>([]);
    const [files, setFiles] = useState<ZohoFile[]>([]);
    const [currentFolderId, setCurrentFolderId] = useState<string>('root');
    const [breadcrumbs, setBreadcrumbs] = useState<{ id: string; name: string }[]>([{ id: 'root', name: 'My WorkDrive' }]);
    const [loading, setLoading] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [ingesting, setIngesting] = useState<string | null>(null);
    const [ingestingAll, setIngestingAll] = useState(false);
    const [ingestedFileIds, setIngestedFileIds] = useState<Set<string>>(new Set());
    const { toast } = useToast();

    useEffect(() => {
        init();
    }, []);

    const init = async () => {
        setLoading(true);
        try {
            await Promise.all([fetchTeams(), fetchFiles('root')]);
        } finally {
            setLoading(false);
        }
    };

    const handleConnectZoho = () => {
        window.location.href = `/api/v1/auth/oauth/zoho/authorize?user_id=${userId}`;
    };

    const fetchTeams = async () => {
        try {
            const response = await fetch(`/api/zoho-workdrive/teams?user_id=${userId}`);
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    setIsConnected(true);
                    setTeams(data.data || []);
                }
            }
        } catch (error) {
            console.error('Failed to fetch Zoho teams:', error);
        }
    };

    const fetchFiles = async (parentId: string = 'root', folderName?: string) => {
        setLoading(true);
        try {
            const response = await fetch('/api/zoho-workdrive/files/list', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, parent_id: parentId })
            });
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    setIsConnected(true);
                    setFiles(data.data || []);
                    setCurrentFolderId(parentId);
                    
                    if (parentId === 'root') {
                        setBreadcrumbs([{ id: 'root', name: 'My WorkDrive' }]);
                    } else if (folderName) {
                        setBreadcrumbs(prev => [...prev.filter(b => b.id !== parentId), { id: parentId, name: folderName }]);
                    }
                }
            }
        } catch (error: any) {
            console.error('Failed to fetch Zoho files:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleIngest = async (file: ZohoFile) => {
        setIngesting(file.id);
        try {
            const response = await fetch('/api/zoho-workdrive/ingest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, file_id: file.id })
            });
            if (!response.ok) {
                const text = await response.text();
                throw new Error(extractErrorMessage(text, response.status));
            }
            const data = await response.json();
            if (data.success) {
                setIngestedFileIds(prev => new Set(prev).add(file.id));
                toast({
                    title: "Ingestion Successful",
                    description: `Loaded ${file.name} into AI Employee working memory.`,
                });
            } else {
                throw new Error(data.error || 'Ingestion failed');
            }
        } catch (error: any) {
            toast({
                title: "Ingestion Failed",
                description: error.message,
                variant: "error"
            });
        } finally {
            setIngesting(null);
        }
    };

    const handleIngestAll = async () => {
        const ingestableFiles = files.filter(f => f.type !== 'folder');
        if (ingestableFiles.length === 0) return;
        
        setIngestingAll(true);
        let successCount = 0;
        for (const file of ingestableFiles) {
            try {
                const response = await fetch('/api/zoho-workdrive/ingest', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ user_id: userId, file_id: file.id })
                });
                if (response.ok) {
                    setIngestedFileIds(prev => new Set(prev).add(file.id));
                    successCount++;
                }
            } catch (err) {
                console.error(`Failed to ingest ${file.name}:`, err);
            }
        }
        setIngestingAll(false);
        toast({
            title: "Batch Ingestion Complete",
            description: `Ingested ${successCount} of ${ingestableFiles.length} files into AI working memory.`,
        });
    };

    const formatSize = (bytes?: number) => {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    const nonFolderFiles = files.filter(f => f.type !== 'folder');

    return (
        <Card className="w-full">
            <CardHeader>
                <div className="flex justify-between items-center">
                    <div>
                        <CardTitle className="flex items-center gap-2">
                            <HardDrive className="w-6 h-6 text-blue-600" />
                            Zoho WorkDrive Ingestion
                        </CardTitle>
                        <CardDescription>
                            Sync and ingest documents directly into AI Employee working memory.
                        </CardDescription>
                    </div>
                    <div className="flex items-center gap-3">
                        {isConnected ? (
                            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800 flex items-center gap-1.5 px-3 py-1 text-xs font-medium">
                                <CheckCircle className="w-3.5 h-3.5 text-green-600 dark:text-green-400" />
                                Connected
                            </Badge>
                        ) : null}
                        {nonFolderFiles.length > 0 && isConnected && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={handleIngestAll}
                                disabled={ingestingAll || loading}
                                className="border-blue-300 text-blue-700 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-300"
                            >
                                <Download className={`w-4 h-4 mr-2 ${ingestingAll ? 'animate-bounce' : ''}`} />
                                {ingestingAll ? "Ingesting..." : "Ingest All Files"}
                            </Button>
                        )}
                        <Button
                            variant={isConnected ? "outline" : "default"}
                            size="sm"
                            onClick={handleConnectZoho}
                            className={isConnected ? "text-gray-600 dark:text-gray-300" : "bg-blue-600 hover:bg-blue-700 text-white"}
                        >
                            <ExternalLink className="w-4 h-4 mr-2" />
                            {isConnected ? "Reconnect" : "Connect Zoho Account"}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => fetchFiles(currentFolderId)} disabled={loading}>
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Breadcrumbs */}
                    {breadcrumbs.length > 1 && (
                        <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
                            {breadcrumbs.map((b, idx) => (
                                <React.Fragment key={b.id}>
                                    {idx > 0 && <span className="text-gray-400">/</span>}
                                    <button
                                        onClick={() => fetchFiles(b.id)}
                                        className={`hover:underline ${idx === breadcrumbs.length - 1 ? 'font-semibold text-gray-800 dark:text-gray-200' : ''}`}
                                    >
                                        {b.name}
                                    </button>
                                </React.Fragment>
                            ))}
                        </div>
                    )}

                    <div className="border rounded-md divide-y overflow-hidden">
                        {loading && files.length === 0 ? (
                            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin text-blue-600" />
                                <p className="font-medium">Loading files from Zoho WorkDrive...</p>
                            </div>
                        ) : files.length === 0 ? (
                            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                <Search className="w-8 h-8 mx-auto mb-2 text-gray-400" />
                                <p className="font-medium text-gray-700 dark:text-gray-300">
                                    {isConnected ? "No files found in this folder" : "No files available"}
                                </p>
                                <p className="text-xs text-gray-500 mt-1 mb-4">
                                    {isConnected
                                        ? "Your Zoho WorkDrive is connected, but this folder contains no files yet. Upload files to Zoho WorkDrive and click Refresh."
                                        : "Connect your Zoho WorkDrive account to sync team folders and documents."}
                                </p>
                                <div className="flex items-center justify-center gap-3">
                                    {isConnected ? (
                                        <Button variant="default" size="sm" onClick={() => fetchFiles(currentFolderId)} className="bg-blue-600 hover:bg-blue-700 text-white">
                                            <RefreshCw className="w-4 h-4 mr-2" />
                                            Refresh Files
                                        </Button>
                                    ) : (
                                        <Button variant="default" size="sm" onClick={handleConnectZoho} className="bg-blue-600 hover:bg-blue-700 text-white">
                                            <ExternalLink className="w-4 h-4 mr-2" />
                                            Connect Zoho Account
                                        </Button>
                                    )}
                                    {currentFolderId !== 'root' && (
                                        <Button variant="outline" size="sm" onClick={() => fetchFiles('root')}>Go to Root</Button>
                                    )}
                                </div>
                            </div>
                        ) : (
                            files.map(file => {
                                const isIngested = ingestedFileIds.has(file.id);
                                return (
                                    <div key={file.id} className="flex items-center justify-between p-3 hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-800 transition-colors">
                                        <div className="flex items-center gap-3 min-w-0">
                                            {file.type === 'folder' ? (
                                                <Folder className="w-5 h-5 text-yellow-500 flex-shrink-0" />
                                            ) : (
                                                <File className="w-5 h-5 text-gray-400 flex-shrink-0" />
                                            )}
                                            <div className="min-w-0">
                                                <div className="flex items-center gap-2">
                                                    <p className="font-medium truncate">{file.name}</p>
                                                    {isIngested && (
                                                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 bg-green-50 text-green-700 border-green-200">
                                                            ✓ Ingested to Memory
                                                        </Badge>
                                                    )}
                                                </div>
                                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                                    {file.type === 'folder' ? 'Folder' : `${file.extension?.toUpperCase() || 'FILE'} • ${formatSize(file.size)}`}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            {file.type === 'folder' ? (
                                                <Button variant="ghost" size="sm" onClick={() => fetchFiles(file.id, file.name)}>
                                                    Open
                                                </Button>
                                            ) : (
                                                <Button
                                                    variant={isIngested ? "secondary" : "outline"}
                                                    size="sm"
                                                    onClick={() => handleIngest(file)}
                                                    disabled={ingesting === file.id || ingestingAll}
                                                >
                                                    {ingesting === file.id ? (
                                                        <RefreshCw className="w-3 h-3 animate-spin mr-1" />
                                                    ) : (
                                                        <Download className="w-3 h-3 mr-1" />
                                                    )}
                                                    {isIngested ? "Re-Ingest" : "Ingest"}
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                );
                            })
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
