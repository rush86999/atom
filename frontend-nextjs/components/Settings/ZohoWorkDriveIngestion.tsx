'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { useToast } from '../ui/use-toast';
import { HardDrive, RefreshCw, Folder, File, Download, Search, CheckCircle, AlertTriangle } from 'lucide-react';

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

export default function ZohoWorkDriveIngestion({ userId }: { userId: string }) {
    const [teams, setTeams] = useState<ZohoTeam[]>([]);
    const [files, setFiles] = useState<ZohoFile[]>([]);
    const [currentFolderId, setCurrentFolderId] = useState<string>('root');
    const [loading, setLoading] = useState(false);
    const [ingesting, setIngesting] = useState<string | null>(null);
    const { toast } = useToast();

    useEffect(() => {
        fetchTeams();
    }, []);

    const fetchTeams = async () => {
        setLoading(true);
        try {
            const response = await fetch(`/api/zoho-workdrive/teams?user_id=${userId}`);
            const data = await response.json();
            if (data.success) {
                setTeams(data.data);
                // If teams exist, maybe load the first one's root
                if (data.data.length > 0) {
                    // In a real app, we might need to drill down into teams
                }
            }
        } catch (error) {
            console.error('Failed to fetch Zoho teams:', error);
        } finally {
            setLoading(false);
        }
    };

    const fetchFiles = async (parentId: string = 'root') => {
        setLoading(true);
        try {
            const response = await fetch('/api/zoho-workdrive/files/list', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, parent_id: parentId })
            });
            const data = await response.json();
            if (data.success) {
                setFiles(data.data);
                setCurrentFolderId(parentId);
            }
        } catch (error) {
            console.error('Failed to fetch Zoho files:', error);
            toast({
                title: "Error",
                description: "Failed to load files from Zoho WorkDrive",
                variant: "error"
            });
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
            const data = await response.json();
            if (data.success) {
                toast({
                    title: "Success",
                    description: `Successfully ingested ${file.name} to ATOM memory`,
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

    const formatSize = (bytes?: number) => {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

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
                            Sync and ingest documents directly from your Zoho WorkDrive teams.
                        </CardDescription>
                    </div>
                    <Button variant="outline" size="sm" onClick={() => fetchFiles(currentFolderId)} disabled={loading}>
                        <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Navigation/Breadcrumbs could go here */}

                    <div className="border rounded-md divide-y overflow-hidden">
                        {loading && files.length === 0 ? (
                            <div className="p-8 text-center text-gray-500">
                                <RefreshCw className="w-8 h-8 mx-auto mb-2 animate-spin" />
                                <p>Loading files...</p>
                            </div>
                        ) : files.length === 0 ? (
                            <div className="p-8 text-center text-gray-500">
                                <Search className="w-8 h-8 mx-auto mb-2" />
                                <p>No files found in this folder</p>
                                <Button variant="link" onClick={() => fetchFiles('root')}>Go to Root</Button>
                            </div>
                        ) : (
                            files.map(file => (
                                <div key={file.id} className="flex items-center justify-between p-3 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
                                    <div className="flex items-center gap-3 min-w-0">
                                        {file.type === 'folder' ? (
                                            <Folder className="w-5 h-5 text-yellow-500 flex-shrink-0" />
                                        ) : (
                                            <File className="w-5 h-5 text-gray-400 flex-shrink-0" />
                                        )}
                                        <div className="min-w-0">
                                            <p className="font-medium truncate">{file.name}</p>
                                            <p className="text-xs text-gray-500">
                                                {file.type === 'folder' ? 'Folder' : `${file.extension?.toUpperCase() || 'FILE'} • ${formatSize(file.size)}`}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-2">
                                        {file.type === 'folder' ? (
                                            <Button variant="ghost" size="sm" onClick={() => fetchFiles(file.id)}>
                                                Open
                                            </Button>
                                        ) : (
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                onClick={() => handleIngest(file)}
                                                disabled={ingesting === file.id}
                                            >
                                                {ingesting === file.id ? (
                                                    <RefreshCw className="w-3 h-3 animate-spin mr-1" />
                                                ) : (
                                                    <Download className="w-3 h-3 mr-1" />
                                                )}
                                                Ingest
                                            </Button>
                                        )}
                                    </div>
                                </div>
                            ))
                        )}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}
