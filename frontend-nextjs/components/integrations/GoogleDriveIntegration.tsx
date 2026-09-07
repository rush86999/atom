import React, { useState, useEffect } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";
import { authFetch } from "@/lib/auth-headers";
import { notifyIngestionUpdated } from "@/lib/ingestion-events";
import { runIngestJob, fetchRecentJobs, type IngestJob } from "@/lib/ingest-jobs";
import IngestionJobsStrip from "@/components/integrations/IngestionJobsStrip";
import {
  ChevronRight,
  ArrowRight,
  RefreshCw,
  Loader2,
  Folder,
  FileText,
  FileSpreadsheet,
  Presentation,
  Image as ImageIcon,
  File,
  Video,
  Music,
  Download,
  ExternalLink,
  AlertTriangle,
  CheckCircle,
  XCircle
} from "lucide-react";

interface GoogleDriveFile {
  id: string;
  name: string;
  mimeType: string;
  modifiedTime?: string;
  webViewLink?: string;
  parents?: string[];
  capabilities?: {
    canDownload?: boolean;
    canExport?: boolean;
  };
  exportLinks?: Record<string, string>;
  isFolder: boolean;
  size?: number;
}

interface GoogleDriveConnectionStatus {
  isConnected: boolean;
  email?: string;
  reason?: string;
}

interface FileListResponse {
  files: GoogleDriveFile[];
  nextPageToken?: string;
}

const GoogleDriveIntegration: React.FC = () => {
  const [connectionStatus, setConnectionStatus] = useState<GoogleDriveConnectionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [files, setFiles] = useState<GoogleDriveFile[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | undefined>(undefined);
  const [pathHistory, setPathHistory] = useState<Array<{ id?: string; name: string }>>([
    { name: 'My Drive', id: undefined }
  ]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [ingestingId, setIngestingId] = useState<string | null>(null);
  const [selectedFolderIds, setSelectedFolderIds] = useState<Set<string>>(new Set());
  const [ingestingFolders, setIngestingFolders] = useState(false);
  const [nextPageToken, setNextPageToken] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [recentJobs, setRecentJobs] = useState<IngestJob[]>([]);
  const [ingestedIds, setIngestedIds] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  // Ingest jobs live server-side and outlive this page — surface running /
  // recent ones so an ingest started before this page load is visible.
  useEffect(() => {
    refreshRecentJobs();
    const timer = setInterval(refreshRecentJobs, 15000);
    return () => clearInterval(timer);
  }, []);

  const refreshRecentJobs = async () => {
    setRecentJobs(await fetchRecentJobs(authFetch, "/api/gdrive"));
  };

  // Durable badge source of truth: which listed files are already in ATOM
  // memory (POST /ingested-ids probes the document store).
  const hydrateIngestedIds = async (listed: GoogleDriveFile[]) => {
    const fileIds = (listed || []).filter((f) => !f.isFolder).map((f) => f.id);
    if (fileIds.length === 0) return;
    try {
      const response = await authFetch("/api/gdrive/ingested-ids", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_ids: fileIds }),
      });
      if (!response.ok) return;
      const data = await response.json();
      const ingested: string[] = data?.data?.ingested ?? data?.ingested ?? [];
      if (ingested.length > 0) {
        setIngestedIds((prev) => new Set([...prev, ...ingested]));
      }
    } catch {
      // badges are best-effort
    }
  };

  // Fetch connection status
  const fetchConnectionStatus = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await authFetch('/api/gdrive/connection-status');
      if (response.ok) {
        const data = await response.json();
        setConnectionStatus(data);
      } else {
        throw new Error('Failed to fetch connection status');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error occurred');
      setConnectionStatus({ isConnected: false, reason: 'Connection failed' });
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch files from Google Drive
  const fetchFiles = async (folderId?: string, pageToken?: string, isLoadMore = false) => {
    if (!connectionStatus?.isConnected) return;

    try {
      setIsLoadingFiles(true);
      setError(null);

      const params = new URLSearchParams();
      if (folderId) params.append('folder_id', folderId);
      if (pageToken) params.append('page_token', pageToken);

      const response = await authFetch(`/api/gdrive/list-files?${params.toString()}`);

      if (response.ok) {
        const data: FileListResponse & { error?: string } = await response.json();

        if (data.error) {
          throw new Error(data.error);
        }

        if (isLoadMore) {
          setFiles(prev => [...prev, ...(data.files || [])]);
        } else {
          setFiles(data.files || []);
          // The listing changed (navigation/refresh) — selections refer to
          // rows that may no longer be on screen.
          setSelectedFolderIds(new Set());
          hydrateIngestedIds(data.files || []);
        }

        setNextPageToken(data.nextPageToken);
      } else {
        throw new Error('Failed to fetch files');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load files');
      if (!isLoadMore) {
        setFiles([]);
      }
    } finally {
      setIsLoadingFiles(false);
    }
  };

  // Handle file/folder click
  const handleFileClick = (file: GoogleDriveFile) => {
    if (file.isFolder) {
      // Navigate into folder
      const newPath = [...pathHistory, { id: file.id, name: file.name }];
      setPathHistory(newPath);
      setCurrentFolderId(file.id);
      setFiles([]);
      setNextPageToken(undefined);
      fetchFiles(file.id);
    } else {
      // Open file in new tab
      if (file.webViewLink) {
        window.open(file.webViewLink, '_blank');
      }
    }
  };

  // Handle breadcrumb click
  const handleBreadcrumbClick = (index: number) => {
    const newPath = pathHistory.slice(0, index + 1);
    const targetFolder = newPath[newPath.length - 1];

    setPathHistory(newPath);
    setCurrentFolderId(targetFolder.id);
    setFiles([]);
    setNextPageToken(undefined);
    fetchFiles(targetFolder.id);
  };

  // Handle Google Drive connection
  const handleConnect = () => {
    // Redirect to OAuth flow
    window.location.href = '/api/auth/gdrive/initiate';
  };

  // Mirrors Outlook's Switch Account: ?prompt=select_account forces Google's
  // account picker instead of reusing the signed-in session. The JWT goes in
  // the Authorization header via authFetch, never in a URL (URLs leak into
  // browser history / request logs).
  const handleSwitchAccount = async () => {
    try {
      const resp = await authFetch(
        '/api/v1/auth/oauth/google/initiate?prompt=select_account&format=json'
      );
      if (!resp.ok) throw new Error(`Initiate failed (${resp.status})`);
      const data = await resp.json();
      if (!data?.url) throw new Error('No auth URL returned');
      window.location.href = data.url;
    } catch (err) {
      console.error('Switch account error:', err);
    }
  };

  // Handle Google Drive disconnection
  const handleDisconnect = async () => {
    try {
      const response = await authFetch('/api/auth/gdrive/disconnect', { method: 'POST' });
      if (response.ok) {
        toast({
          title: 'Disconnected',
          description: 'Google Drive has been disconnected',
        });
        await fetchConnectionStatus();
        setFiles([]);
        setPathHistory([{ name: 'My Drive', id: undefined }]);
        setCurrentFolderId(undefined);
      } else {
        throw new Error('Failed to disconnect');
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to disconnect Google Drive',
        variant: 'destructive',
      });
    }
  };

  // Handle file ingestion
  const handleIngestFile = async (file: GoogleDriveFile) => {
    try {
      setIngestingId(file.id);
      // Backend JOB (a big file parses for minutes — the sync request died
      // at the proxy timeout with a phantom 500). Start + poll via the
      // shared lib.
      const data = await runIngestJob(
        authFetch,
        '/api/ingest-gdrive-document',
        '/api/gdrive',
        {
          file_id: file.id,
          metadata: {
            name: file.name,
            mimeType: file.mimeType,
            webViewLink: file.webViewLink,
          },
        },
        'file ingest'
      );
      if (data.success !== false) {
        setIngestedIds((prev) => new Set(prev).add(file.id));
        // Immediate per-app feedback: the page's ingestion card refreshes.
        notifyIngestionUpdated("google_drive");
        refreshRecentJobs();
        toast({
          title: data.unchanged ? 'Already in Memory' : 'File Ingested',
          description: data.unchanged
            ? `${file.name} was already in the search index — content unchanged, nothing re-ingested.`
            : `${file.name} has been added to search index`,
        });
      } else {
        throw new Error(data.error || 'Failed to ingest file');
      }
    } catch (err) {
      toast({
        title: 'Ingestion Error',
        description: err instanceof Error ? err.message : 'Failed to ingest file',
        variant: 'destructive',
      });
    } finally {
      setIngestingId(null);
    }
  };

  // Multi-folder ingestion: every selected folder's subtree is walked and
  // ingested in one backend call (folders are isolated server-side).
  const handleIngestSelectedFolders = async () => {
    const folders = files.filter(f => f.isFolder && selectedFolderIds.has(f.id));
    if (folders.length === 0) return;

    try {
      setIngestingFolders(true);
      const data = await runIngestJob(
        authFetch,
        '/api/gdrive/ingest-folders',
        '/api/gdrive',
        { folders: folders.map(f => ({ id: f.id, name: f.name })) },
        'folder ingest'
      );
      if (data.success !== false) {
        const succeeded = data.folders_succeeded ?? folders.length;
        notifyIngestionUpdated("google_drive");
        refreshRecentJobs();
        toast({
          title: 'Folder Ingestion Complete',
          description:
            `Ingested ${data.files_ingested ?? 0} file(s) from ${succeeded} of ${folders.length} folder(s) into ATOM memory.` +
            ((data.files_ingested ?? 0) === 0 ? ' No parseable files found.' : ''),
        });
        setSelectedFolderIds(new Set());
      } else {
        throw new Error(data.error || 'Failed to ingest folders');
      }
    } catch (err) {
      toast({
        title: 'Folder Ingestion Error',
        description: err instanceof Error ? err.message : 'Failed to ingest folders',
        variant: 'destructive',
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

  const listedFolders = files.filter(f => f.isFolder);
  const allListedFoldersSelected =
    listedFolders.length > 0 && listedFolders.every(f => selectedFolderIds.has(f.id));

  const toggleAllListedFolders = (checked: boolean) => {
    setSelectedFolderIds(prev => {
      const next = new Set(prev);
      listedFolders.forEach(f => (checked ? next.add(f.id) : next.delete(f.id)));
      return next;
    });
  };

  // Format file size
  const formatFileSize = (bytes?: number): string => {
    if (bytes === 0) return '0 Bytes';
    if (!bytes) return 'N/A';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Format date
  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  // Get file icon based on mime type
  const getFileIcon = (file: GoogleDriveFile) => {
    if (file.isFolder) return <Folder className="h-5 w-5 text-blue-500" />;

    const mimeType = file.mimeType;
    if (mimeType.includes('document')) return <FileText className="h-5 w-5 text-blue-400" />;
    if (mimeType.includes('spreadsheet')) return <FileSpreadsheet className="h-5 w-5 text-green-500" />;
    if (mimeType.includes('presentation')) return <Presentation className="h-5 w-5 text-orange-500" />;
    if (mimeType.includes('image')) return <ImageIcon className="h-5 w-5 text-purple-500" />;
    if (mimeType.includes('pdf')) return <FileText className="h-5 w-5 text-red-500" />;
    if (mimeType.includes('video')) return <Video className="h-5 w-5 text-red-400" />;
    if (mimeType.includes('audio')) return <Music className="h-5 w-5 text-pink-500" />;

    return <File className="h-5 w-5 text-gray-500 dark:text-gray-400" />;
  };

  // Initial load
  useEffect(() => {
    fetchConnectionStatus();
  }, []);

  // Fetch files when connection is established and folder changes
  useEffect(() => {
    if (connectionStatus?.isConnected) {
      fetchFiles(currentFolderId);
    }
  }, [connectionStatus?.isConnected, currentFolderId]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        <p className="mt-4 text-gray-500 dark:text-gray-400">Loading Google Drive integration...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <h2 className="text-2xl font-bold tracking-tight">Google Drive Integration</h2>
        <p className="text-gray-500 dark:text-gray-400">
          Connect your Google Drive to search and manage files directly within ATOM
        </p>
      </div>

      {/* Connection Status */}
      <div className="p-6 border rounded-lg bg-white dark:bg-gray-900 space-y-4">
        <h3 className="text-lg font-semibold">Connection Status</h3>

        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {connectionStatus?.isConnected ? (
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Badge className="bg-green-500 hover:bg-green-600">Connected</Badge>
              <span className="text-sm text-gray-600 dark:text-gray-400">as {connectionStatus.email}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSwitchAccount}
              >
                Switch Account
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDisconnect}
              >
                Disconnect Google Drive
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Badge variant="destructive">Not Connected</Badge>
              {connectionStatus?.reason && (
                <span className="text-sm text-gray-600 dark:text-gray-400">{connectionStatus.reason}</span>
              )}
            </div>
            <Button
              className="bg-blue-600 hover:bg-blue-700"
              onClick={handleConnect}
            >
              Connect Google Drive
            </Button>
          </div>
        )}
      </div>

      {/* File Browser - Only show when connected */}
      {connectionStatus?.isConnected && (
        <div className="p-6 border rounded-lg bg-white dark:bg-gray-900 space-y-4">
          <h3 className="text-lg font-semibold">Files & Folders</h3>

          {/* Breadcrumb Navigation */}
          <nav className="flex items-center space-x-2 text-sm text-gray-500 dark:text-gray-400 mb-4">
            {pathHistory.map((item, index) => (
              <React.Fragment key={item.id || 'root'}>
                {index > 0 && <ChevronRight className="h-4 w-4" />}
                <button
                  onClick={() => handleBreadcrumbClick(index)}
                  className={`hover:underline ${index === pathHistory.length - 1
                      ? 'font-semibold text-gray-900 dark:text-gray-100 cursor-default'
                      : 'text-blue-500 cursor-pointer'
                    }`}
                  disabled={index === pathHistory.length - 1}
                >
                  {item.name}
                </button>
              </React.Fragment>
            ))}
          </nav>

          {/* Files Table */}
          {isLoadingFiles && files.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
              <p className="mt-2 text-gray-500 dark:text-gray-400">Loading files...</p>
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500 dark:text-gray-400">No files found in this folder</p>
            </div>
          ) : (
            <>
              {/* Multi-folder selection bar */}
              {listedFolders.length > 0 && (
                <div className="flex items-center gap-3">
                  {selectedFolderIds.size > 0 ? (
                    <>
                      <Button
                        size="sm"
                        className="bg-blue-600 hover:bg-blue-700 text-white"
                        onClick={handleIngestSelectedFolders}
                        disabled={ingestingFolders}
                      >
                        {ingestingFolders ? (
                          <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        ) : (
                          <Download className="mr-2 h-4 w-4" />
                        )}
                        {ingestingFolders
                          ? 'Ingesting…'
                          : `Ingest ${selectedFolderIds.size} folder${selectedFolderIds.size === 1 ? '' : 's'}`}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
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

              {/* Running / recent ingest jobs — server-side state, visible after navigating away and back mid-ingest. */}
              <IngestionJobsStrip jobs={recentJobs} />
              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-10">
                        {listedFolders.length > 0 && (
                          <Checkbox
                            aria-label="Select all folders"
                            checked={allListedFoldersSelected}
                            onCheckedChange={(checked) => toggleAllListedFolders(checked === true)}
                          />
                        )}
                      </TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Modified</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {files.map((file) => (
                      <TableRow
                        key={file.id}
                        className={file.isFolder ? 'cursor-pointer hover:bg-gray-50 dark:bg-gray-800 dark:hover:bg-gray-800' : ''}
                        onClick={() => file.isFolder && handleFileClick(file)}
                      >
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          {file.isFolder && (
                            <Checkbox
                              aria-label={`Select folder ${file.name}`}
                              checked={selectedFolderIds.has(file.id)}
                              onCheckedChange={(checked) =>
                                toggleFolderSelection(file.id, checked === true)
                              }
                            />
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            {getFileIcon(file)}
                            <span className="font-medium">{file.name}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={file.isFolder ? "default" : "secondary"}>
                            {file.isFolder ? 'Folder' : 'File'}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatDate(file.modifiedTime)}</TableCell>
                        <TableCell>{formatFileSize(file.size)}</TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            {!file.isFolder && file.webViewLink && (
                              <Button
                                size="sm"
                                variant="ghost"
                                title="Open in Google Drive"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  window.open(file.webViewLink, '_blank');
                                }}
                              >
                                <ExternalLink className="h-4 w-4" />
                              </Button>
                            )}
                            {!file.isFolder && (
                              <Button
                                size="sm"
                                variant="ghost"
                                title="Ingest into ATOM Memory"
                                disabled={ingestingId === file.id}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleIngestFile(file);
                                }}
                              >
                                {ingestingId === file.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                                ) : (
                                  <Download className="h-4 w-4" />
                                )}
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {/* Load More Button */}
              {nextPageToken && (
                <div className="flex justify-center mt-4">
                  <Button
                    onClick={() => fetchFiles(currentFolderId, nextPageToken, true)}
                    disabled={isLoadingFiles}
                    variant="outline"
                  >
                    {isLoadingFiles ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
                    Load More Files
                  </Button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default GoogleDriveIntegration;
