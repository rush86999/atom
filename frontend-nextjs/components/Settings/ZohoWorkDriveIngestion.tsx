'use client';

import React, { useState, useEffect } from 'react';
import { getAuthToken } from '@/lib/identity';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../ui/card';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { useToast } from '../ui/use-toast';
import { HardDrive, RefreshCw, Folder, File, Download, Search, CheckCircle, AlertTriangle, ExternalLink } from 'lucide-react';
import { Checkbox } from '../ui/checkbox';
import { notifyIngestionUpdated } from '@/lib/ingestion-events';
import { runIngestJob, fetchRecentJobs, type FetchLike, type IngestJob } from '@/lib/ingest-jobs';
import IngestionJobsStrip from '../integrations/IngestionJobsStrip';

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

interface ZohoTeamFolder {
    id: string;
    name: string;
    team_id?: string;
    team_name?: string;
    workspace_id?: string;
    type?: string;
}

interface ListParams {
    parent_id: string;
    workspace_id?: string;
    team_id?: string;
    folderName?: string;
    recursive?: boolean;
}

interface Breadcrumb {
    id: string;
    name: string;
    teamFolderId?: string;
}

// Keep in sync with PARSEABLE_EXTS in backend/integrations/zoho_workdrive_service.py
const INGESTABLE_EXTS = ['.docx', '.xlsx', '.xls', '.csv', '.pdf', '.txt', '.md', '.pptx'];

/** The backend CSRF middleware exempts Bearer-token requests but rejects
 * cookie-only POSTs (403 csrf_token_invalid) — every fetch carries the JWT
 * (same pattern as pages/approvals.tsx). */
function authHeaders(json = true): Record<string, string> {
    return {
        ...(json ? { 'Content-Type': 'application/json' } : {}),
        Authorization: `Bearer ${getAuthToken() || ''}`,
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

export default function ZohoWorkDriveIngestion() {
    const [teams, setTeams] = useState<ZohoTeam[]>([]);
    const [teamFolders, setTeamFolders] = useState<ZohoTeamFolder[]>([]);
    const [files, setFiles] = useState<ZohoFile[]>([]);
    const [currentFolderId, setCurrentFolderId] = useState<string>('root');
    const [lastParams, setLastParams] = useState<ListParams>({ parent_id: 'root' });
    const [showAllFiles, setShowAllFiles] = useState(false);
    const [breadcrumbs, setBreadcrumbs] = useState<Breadcrumb[]>([{ id: 'root', name: 'My WorkDrive' }]);
    const [loading, setLoading] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [ingesting, setIngesting] = useState<string | null>(null);
    const [ingestingFolder, setIngestingFolder] = useState<string | null>(null);
    const [ingestingAll, setIngestingAll] = useState(false);
    const [selectedFolderIds, setSelectedFolderIds] = useState<Set<string>>(new Set());
    const [ingestingFolders, setIngestingFolders] = useState(false);
    const [ingestedFileIds, setIngestedFileIds] = useState<Set<string>>(new Set());
    const [ingestedFolderIds, setIngestedFolderIds] = useState<Set<string>>(new Set());
    const [recentJobs, setRecentJobs] = useState<IngestJob[]>([]);
    const { toast } = useToast();

    useEffect(() => {
        init();
    }, []);

    const init = async () => {
        setLoading(true);
        try {
            await Promise.all([fetchTeams(), fetchTeamFolders(), fetchFiles({ parent_id: 'root' })]);
        } finally {
            setLoading(false);
        }
    };

    // Ingestion jobs live server-side and outlive this page — surface them so
    // a tree walk started earlier (or on another panel) is visible instead of
    // the UI silently showing plain "Ingest" buttons again.
    useEffect(() => {
        refreshRecentJobs();
        const timer = setInterval(refreshRecentJobs, 15000);
        return () => clearInterval(timer);
    }, []);

    const refreshRecentJobs = async () => {
        const jobs = await fetchRecentJobs(apiFetch, '/api/zoho-workdrive');
        setRecentJobs(jobs);
        // A folder counts as ingested when a completed job covered it.
        setIngestedFolderIds(prev => {
            const next = new Set(prev);
            for (const job of jobs) {
                if (job?.status === 'completed' && Array.isArray(job?.folder_ids)) {
                    job.folder_ids.forEach((id: string) => next.add(id));
                }
            }
            return next;
        });
    };

    // Durable badge source of truth: check the visible file ids against the
    // document store so "Re-Ingest" survives page reloads (session-only React
    // state used to reset every navigation).
    const hydrateIngestedIds = async (listed: ZohoFile[]) => {
        const fileIds = (listed || []).filter((f: ZohoFile) => f.type === 'file').map((f: ZohoFile) => f.id);
        if (fileIds.length === 0) return;
        try {
            const response = await fetch('/api/zoho-workdrive/ingested-ids', {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ file_ids: fileIds })
            });
            if (!response.ok) return;
            const data = await response.json();
            const ingested: string[] = data?.data?.ingested ?? data?.ingested ?? [];
            if (ingested.length > 0) {
                setIngestedFileIds(prev => new Set([...prev, ...ingested]));
            }
        } catch {
            // badges are best-effort; the buttons still work without them
        }
    };

    const handleConnectZoho = async () => {
        // R88: the authorize endpoint derives identity from the auth session
        // (JWT/cookie) and fails closed. Browser navigations cannot send an
        // Authorization header, so fetch the provider URL with the JWT in the
        // header (format=json) and navigate to the returned URL — same
        // pattern as ZohoIntegrationDetail. A bare navigation 401'd with
        // "Could not validate credentials".
        try {
            const response = await fetch('/api/v1/auth/oauth/zoho/initiate?format=json', {
                headers: { Authorization: `Bearer ${getAuthToken() || ''}` },
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            if (!data?.url) throw new Error('No auth URL returned');
            window.location.href = data.url;
        } catch (err) {
            console.error('Zoho connect error:', err);
        }
    };

    const fetchTeams = async () => {
        try {
            const response = await fetch('/api/zoho-workdrive/teams', { headers: authHeaders(false) });
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

    const fetchTeamFolders = async () => {
        try {
            const response = await fetch('/api/zoho-workdrive/team-folders', { headers: authHeaders(false) });
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    setTeamFolders(data.data || []);
                }
            }
        } catch (error) {
            console.error('Failed to fetch Zoho team folders:', error);
        }
    };

    const fetchFiles = async (params: ListParams) => {
        setLoading(true);
        const { parent_id, workspace_id, team_id, folderName, recursive } = params;
        const inTeamContext = Boolean(workspace_id || team_id);
        try {
            const response = await fetch('/api/zoho-workdrive/files/list', {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({
                    parent_id,
                    ...(workspace_id ? { workspace_id } : {}),
                    ...(team_id ? { team_id } : {}),
                    ...(recursive ? { recursive: true } : {}),
                })
            });
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    setIsConnected(true);
                    setFiles(data.data || []);
                    setCurrentFolderId(parent_id);
                    hydrateIngestedIds(data.data || []);
                    // The listing changed (navigation/refresh) — selections
                    // refer to rows that may no longer be on screen.
                    setSelectedFolderIds(new Set());
                    setLastParams({
                        parent_id,
                        workspace_id,
                        team_id,
                        folderName,
                    });

                    if (inTeamContext) {
                        // Breadcrumbs for team folders are set by openTeamFolder.
                    } else if (parent_id === 'root') {
                        setBreadcrumbs([{ id: 'root', name: 'My WorkDrive' }]);
                    } else if (folderName) {
                        setBreadcrumbs(prev => [...prev.filter(b => b.id !== parent_id), { id: parent_id, name: folderName }]);
                    }
                }
            }
        } catch (error: any) {
            console.error('Failed to fetch Zoho files:', error);
        } finally {
            setLoading(false);
        }
    };

    const toggleAllFiles = () => {
        const next = !showAllFiles;
        setShowAllFiles(next);
        fetchFiles({ ...lastParams, recursive: next });
    };

    const openTeamFolder = async (tf: ZohoTeamFolder) => {
        setBreadcrumbs([
            { id: 'root', name: 'My WorkDrive' },
            { id: tf.id, name: tf.name, teamFolderId: tf.id },
        ]);
        await fetchFiles({ parent_id: tf.id, workspace_id: tf.workspace_id, team_id: tf.team_id });
    };

    // Ingestion runs as a backend JOB via the SHARED lib (lib/ingest-jobs.ts)
    // — a single big file or folder tree takes minutes to download + parse +
    // embed, and the old synchronous requests died at the browser/Next-dev-
    // proxy 30s timeout with a phantom 500. POST returns {job_id}; poll the
    // job status until completed/failed.
    const apiFetch: FetchLike = (url, init) =>
        fetch(url, { ...init, headers: { ...authHeaders(), ...(init?.headers || {}) } });

    const runFolderIngestJob = async (body: Record<string, unknown>): Promise<any> => {
        const data = await runIngestJob(
            apiFetch, '/api/zoho-workdrive/ingest-folder', '/api/zoho-workdrive',
            body, 'folder ingest'
        );
        refreshRecentJobs();
        return data;
    };

    // Hybrid-ingestion explicit pull: ingest one folder's contents on demand
    // (user-selected), regardless of the bulk content-mode setting.
    const handleIngestFolder = async (folder: { id: string; name: string; workspace_id?: string; team_id?: string }) => {
        setIngestingFolder(folder.id);
        try {
            const data = await runFolderIngestJob({
                folder_id: folder.id,
                ...(folder.workspace_id ? { workspace_id: folder.workspace_id } : {}),
                ...(folder.team_id ? { team_id: folder.team_id } : {}),
                recursive: true,
            });
            if (data.success) {
                const count = data.files_ingested ?? 0;
                setIngestedFolderIds(prev => new Set(prev).add(folder.id));
                notifyIngestionUpdated("zoho-workdrive");
                toast({
                    title: "Folder Ingestion Complete",
                    description: `Ingested ${count} file${count === 1 ? '' : 's'} from "${folder.name}" into AI working memory.` +
                        (data.errors?.length ? ` (${data.errors.length} failed)` : ''),
                });
            } else {
                throw new Error(data.error || 'Folder ingestion failed');
            }
        } catch (err: any) {
            toast({
                title: "Folder Ingestion Failed",
                description: err.message,
                variant: "error"
            });
        } finally {
            setIngestingFolder(null);
        }
    };

    // Multi-folder ingestion: one backend call carries every selected folder;
    // the server ingests each tree and isolates per-folder failures.
    const handleIngestSelectedFolders = async () => {
        const folders = files.filter(
            f => f.type === 'folder' && selectedFolderIds.has(f.id)
        );
        if (folders.length === 0) return;

        setIngestingFolders(true);
        try {
            const data = await runFolderIngestJob({
                folder_ids: folders.map(f => f.id),
                ...(lastParams.workspace_id ? { workspace_id: lastParams.workspace_id } : {}),
                ...(lastParams.team_id ? { team_id: lastParams.team_id } : {}),
                recursive: true,
            });
            if (data.success) {
                const succeeded = data.folders_succeeded ?? folders.length;
                notifyIngestionUpdated("zoho-workdrive");
                toast({
                    title: "Folder Ingestion Complete",
                    description: `Ingested ${data.files_ingested ?? 0} file(s) from ${succeeded} of ${folders.length} folder(s) into AI working memory.` +
                        ((data.files_ingested ?? 0) === 0 ? ' No parseable files found.' : ''),
                });
                setSelectedFolderIds(new Set());
            } else {
                throw new Error(data.error || 'Folder ingestion failed');
            }
        } catch (err: any) {
            toast({
                title: "Folder Ingestion Failed",
                description: err.message,
                variant: "error"
            });
        } finally {
            setIngestingFolders(false);
        }
    };

    const toggleFolderSelection = (folderId: string, checked: boolean) => {
        setSelectedFolderIds(prev => {
            const next = new Set(prev);
            if (checked) {
                next.add(folderId);
            } else {
                next.delete(folderId);
            }
            return next;
        });
    };

    const listedFolders = files.filter(f => f.type === 'folder');

    const handleBreadcrumb = (b: Breadcrumb) => {
        if (b.id === 'root') {
            fetchFiles({ parent_id: 'root' });
        } else if (b.teamFolderId) {
            const tf = teamFolders.find(t => t.id === b.teamFolderId);
            if (tf) openTeamFolder(tf);
        } else {
            fetchFiles({ parent_id: b.id, folderName: b.name });
        }
    };

    const handleIngest = async (file: ZohoFile) => {
        setIngesting(file.id);
        try {
            const data = await runIngestJob(
                apiFetch, '/api/zoho-workdrive/ingest', '/api/zoho-workdrive',
                { file_id: file.id }, 'file ingest'
            );
            refreshRecentJobs();
            if (data.success) {
                setIngestedFileIds(prev => new Set(prev).add(file.id));
                notifyIngestionUpdated("zoho-workdrive");
                toast({
                    title: data.unchanged ? "Already in Memory" : "Ingestion Successful",
                    description: data.unchanged
                        ? `${file.name} is already in AI Employee working memory — content unchanged since the last ingest.`
                        : `Loaded ${file.name} into AI Employee working memory.`,
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
        // Mirror of backend PARSEABLE_EXTS (integrations/zoho_workdrive_service.py):
        // /ingest-folder skips other extensions, so they shouldn't count as
        // failures or block the ingested badges.
        const ingestableFiles = files.filter(f =>
            f.type !== 'folder' &&
            INGESTABLE_EXTS.some(ext => (f.name || '').toLowerCase().endsWith(ext))
        );
        if (ingestableFiles.length === 0) return;

        setIngestingAll(true);
        try {
            // Server-side batch: one /ingest-folder job with a max_files cap
            // and aggregated error reporting, instead of N sequential /ingest
            // requests from the client. Runs as a backend job — polled to
            // completion.
            const data = await runFolderIngestJob({
                folder_id: currentFolderId,
                ...(lastParams.workspace_id ? { workspace_id: lastParams.workspace_id } : {}),
                ...(lastParams.team_id ? { team_id: lastParams.team_id } : {}),
                recursive: false,
            });
            if (data.success) {
                const ingested = data.files_ingested ?? 0;
                notifyIngestionUpdated("zoho-workdrive");
                // Only mark the visible files as ingested when every file in
                // the folder actually landed — per-file errors are listed in
                // data.errors and surfaced via the toast instead.
                if (ingested === ingestableFiles.length && (!data.errors || data.errors.length === 0)) {
                    setIngestedFileIds(prev => {
                        const next = new Set(prev);
                        ingestableFiles.forEach(f => next.add(f.id));
                        return next;
                    });
                }
                toast({
                    title: "Batch Ingestion Complete",
                    description: `Ingested ${ingested} of ${ingestableFiles.length} files into AI working memory.` +
                        (data.errors?.length ? ` (${data.errors.length} failed)` : ''),
                });
            } else {
                throw new Error(data.error || 'Batch ingestion failed');
            }
        } catch (error: any) {
            toast({
                title: "Batch Ingestion Failed",
                description: error.message,
                variant: "error"
            });
        } finally {
            setIngestingAll(false);
        }
    };

    const formatSize = (bytes?: number) => {
        if (!bytes) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    };

    const nonFolderFiles = files.filter(f => f.type !== 'folder');
    const showTeamFolders = currentFolderId === 'root' && !lastParams.workspace_id && !lastParams.team_id;
    const displayFiles = showAllFiles ? files.filter(f => f.type !== 'folder') : files;

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
                        <Button variant="outline" size="sm" onClick={toggleAllFiles} disabled={loading} className={showAllFiles ? 'bg-blue-50 border-blue-300 text-blue-700 dark:bg-blue-950 dark:text-blue-300' : ''}>
                            <Search className={`w-4 h-4 mr-2`} />
                            {showAllFiles ? 'Current Folder' : 'All Files'}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => fetchFiles(lastParams)} disabled={loading}>
                            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                            Refresh
                        </Button>
                    </div>
                </div>
            </CardHeader>
            <CardContent>
                <div className="space-y-4">
                    {/* Running / recent ingestion jobs — server-side state, so
                        this survives navigating away and back mid-ingest. */}
                    <IngestionJobsStrip jobs={recentJobs} />
                    {/* Breadcrumbs */}
                    {breadcrumbs.length > 1 && (
                        <div className="flex items-center gap-1 text-xs text-gray-500 mb-2">
                            {breadcrumbs.map((b, idx) => (
                                <React.Fragment key={b.id}>
                                    {idx > 0 && <span className="text-gray-400">/</span>}
                                    <button
                                        onClick={() => handleBreadcrumb(b)}
                                        className={`hover:underline ${idx === breadcrumbs.length - 1 ? 'font-semibold text-gray-800 dark:text-gray-200' : ''}`}
                                    >
                                        {b.name}
                                    </button>
                                </React.Fragment>
                            ))}
                        </div>
                    )}

                    {showTeamFolders && teamFolders.length > 0 && (
                        <div className="border rounded-md divide-y overflow-hidden">
                            <div className="px-3 py-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800">
                                Team Folders
                            </div>
                            {teamFolders.map(tf => (
                                <div
                                    key={tf.id}
                                    onDoubleClick={() => openTeamFolder(tf)}
                                    className="flex items-center justify-between p-3 hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-800 transition-colors cursor-pointer"
                                >
                                    <div className="flex items-center gap-3 min-w-0">
                                        <Folder className="w-5 h-5 text-yellow-500 flex-shrink-0" />
                                        <div className="min-w-0">
                                            <p className="font-medium truncate">{tf.name}</p>
                                            <p className="text-xs text-gray-500 dark:text-gray-400">
                                                {tf.team_name ? `${tf.team_name} • ` : ''}Team Folder
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2 pr-3">
                                        {ingestedFolderIds.has(tf.id) && (
                                            <Badge variant="outline" className="bg-green-50 text-green-700 border-green-200 dark:bg-green-950 dark:text-green-300 dark:border-green-800 text-[10px]">
                                                <CheckCircle className="w-3 h-3 mr-1 text-green-600 dark:text-green-400" />
                                                ingested
                                            </Badge>
                                        )}
                                        <Button
                                            variant="outline"
                                            size="sm"
                                            onClick={() => handleIngestFolder({ id: tf.id, name: tf.name, workspace_id: tf.workspace_id, team_id: tf.team_id })}
                                            disabled={ingestingFolder === tf.id}
                                            className="border-blue-300 text-blue-700 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-300"
                                        >
                                            <Download className={`w-3 h-3 mr-1 ${ingestingFolder === tf.id ? 'animate-bounce' : ''}`} />
                                            {ingestingFolder === tf.id ? 'Ingesting…' : ingestedFolderIds.has(tf.id) ? 'Re-Ingest' : 'Ingest'}
                                        </Button>
                                        <Button variant="ghost" size="sm" onClick={() => openTeamFolder(tf)}>
                                            Open
                                        </Button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Multi-folder selection bar */}
                    {listedFolders.length > 0 && (
                        <div className="flex items-center gap-3">
                            {selectedFolderIds.size > 0 ? (
                                <>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={handleIngestSelectedFolders}
                                        disabled={ingestingFolders || ingestingAll}
                                        className="border-blue-300 text-blue-700 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-300"
                                    >
                                        <Download className={`w-4 h-4 mr-2 ${ingestingFolders ? 'animate-bounce' : ''}`} />
                                        {ingestingFolders
                                            ? 'Ingesting…'
                                            : `Ingest ${selectedFolderIds.size} folder${selectedFolderIds.size === 1 ? '' : 's'}`}
                                    </Button>
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => setSelectedFolderIds(new Set())}
                                        disabled={ingestingFolders}
                                    >
                                        Clear selection
                                    </Button>
                                </>
                            ) : (
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                    Tick folders to ingest several at once (each folder is ingested with all its subfolders).
                                </span>
                            )}
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
                                        <Button variant="default" size="sm" onClick={() => fetchFiles(lastParams)} className="bg-blue-600 hover:bg-blue-700 text-white">
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
                                        <Button variant="outline" size="sm" onClick={() => fetchFiles({ parent_id: 'root' })}>Go to Root</Button>
                                    )}
                                </div>
                            </div>
                        ) : (
                            displayFiles.map(file => {
                                const isIngested = ingestedFileIds.has(file.id);
                                return (
                                    <div
                                        key={file.id}
                                        onDoubleClick={file.type === 'folder' ? () => fetchFiles({ parent_id: file.id, folderName: file.name }) : undefined}
                                        className={`flex items-center justify-between p-3 hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-800 transition-colors${file.type === 'folder' ? ' cursor-pointer' : ''}`}
                                    >
                                        <div className="flex items-center gap-3 min-w-0">
                                            {file.type === 'folder' && (
                                                <span onClick={(e) => e.stopPropagation()}>
                                                    <Checkbox
                                                        aria-label={`Select folder ${file.name}`}
                                                        checked={selectedFolderIds.has(file.id)}
                                                        onCheckedChange={(checked) =>
                                                            toggleFolderSelection(file.id, checked === true)
                                                        }
                                                    />
                                                </span>
                                            )}
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
                                                <>
                                                    <Button variant="ghost" size="sm" onClick={() => fetchFiles({ parent_id: file.id, folderName: file.name })}>
                                                        Open
                                                    </Button>
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => handleIngestFolder({ id: file.id, name: file.name })}
                                                        disabled={ingestingFolder === file.id || ingestingAll}
                                                        className="border-blue-300 text-blue-700 hover:bg-blue-50 dark:border-blue-700 dark:text-blue-300"
                                                    >
                                                        <Download className={`w-3 h-3 mr-1 ${ingestingFolder === file.id ? 'animate-bounce' : ''}`} />
                                                        {ingestingFolder === file.id ? 'Ingesting…' : ingestedFolderIds.has(file.id) ? 'Re-Ingest folder' : 'Ingest folder'}
                                                    </Button>
                                                </>
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
