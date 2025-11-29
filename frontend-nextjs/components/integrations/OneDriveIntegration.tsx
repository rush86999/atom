import React, { useState, useEffect } from "react";
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
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";
import {
  ChevronRight,
  ExternalLink,
  RefreshCw,
  Loader2,
  Folder,
  FileText,
  Download,
  AlertTriangle,
} from "lucide-react";

interface OneDriveFile {
  id: string;
  name: string;
  mime_type?: string;
  created_time?: string;
  modified_time?: string;
  web_url?: string;
  parent_reference?: {
    id?: string;
    path?: string;
  };
  is_folder: boolean;
  size?: number;
  icon: string;
}

interface OneDriveConnectionStatus {
  is_connected: boolean;
  email?: string;
  display_name?: string;
  drive_id?: string;
  drive_type?: string;
  reason?: string;
}

interface FileListResponse {
  files: OneDriveFile[];
  next_page_token?: string;
}

const OneDriveIntegration: React.FC = () => {
  const [connectionStatus, setConnectionStatus] =
    useState<OneDriveConnectionStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [files, setFiles] = useState<OneDriveFile[]>([]);
  const [currentFolderId, setCurrentFolderId] = useState<string | undefined>(
    undefined,
  );
  const [pathHistory, setPathHistory] = useState<
    Array<{ id?: string; name: string }>
  >([{ name: "OneDrive", id: undefined }]);
  const [isLoadingFiles, setIsLoadingFiles] = useState(false);
  const [nextPageToken, setNextPageToken] = useState<string | undefined>(
    undefined,
  );
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  const fetchConnectionStatus = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch("/api/onedrive/connection-status");
      if (response.ok) {
        const data = await response.json();
        setConnectionStatus(data);
      } else {
        throw new Error("Failed to fetch connection status");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      setConnectionStatus({ is_connected: false, reason: "Connection failed" });
    } finally {
      setIsLoading(false);
    }
  };

  const fetchFiles = async (
    folderId?: string,
    pageToken?: string,
    isLoadMore = false,
  ) => {
    if (!connectionStatus?.is_connected) return;

    try {
      setIsLoadingFiles(true);
      setError(null);

      const params = new URLSearchParams();
      if (folderId && folderId !== "root") params.append("folder_id", folderId);
      if (pageToken) params.append("page_token", pageToken);

      const response = await fetch(
        `/api/onedrive/list-files?${params.toString()}`,
      );

      if (response.ok) {
        const data: FileListResponse = await response.json();

        if (isLoadMore) {
          setFiles((prev) => [...prev, ...data.files]);
        } else {
          setFiles(data.files);
        }

        setNextPageToken(data.next_page_token);
      } else {
        throw new Error("Failed to fetch files");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load files");
      if (!isLoadMore) {
        setFiles([]);
      }
    } finally {
      setIsLoadingFiles(false);
    }
  };

  const handleFileClick = (file: OneDriveFile) => {
    if (file.is_folder) {
      const newPath = [...pathHistory, { id: file.id, name: file.name }];
      setPathHistory(newPath);
      setCurrentFolderId(file.id);
      setFiles([]);
      setNextPageToken(undefined);
      fetchFiles(file.id);
    } else {
      if (file.web_url) {
        window.open(file.web_url, "_blank");
      }
    }
  };

  const handleBreadcrumbClick = (index: number) => {
    const newPath = pathHistory.slice(0, index + 1);
    const targetFolder = newPath[newPath.length - 1];

    setPathHistory(newPath);
    setCurrentFolderId(targetFolder.id);
    setFiles([]);
    setNextPageToken(undefined);
    fetchFiles(targetFolder.id);
  };

  const handleConnect = () => {
    window.location.href = "/api/auth/onedrive/authorize";
  };

  const handleDisconnect = async () => {
    try {
      const response = await fetch("/api/auth/onedrive/disconnect", {
        method: "POST",
      });
      if (response.ok) {
        toast({
          title: "Disconnected",
          description: "OneDrive has been disconnected",
        });
        await fetchConnectionStatus();
        setFiles([]);
        setPathHistory([{ name: "OneDrive", id: undefined }]);
        setCurrentFolderId(undefined);
      } else {
        throw new Error("Failed to disconnect");
      }
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to disconnect OneDrive",
        variant: "destructive",
      });
    }
  };

  const handleIngestFile = async (file: OneDriveFile) => {
    try {
      const response = await fetch("/api/onedrive/ingest-document", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          file_id: file.id,
          metadata: {
            name: file.name,
            mime_type: file.mime_type,
            web_url: file.web_url,
          },
        }),
      });

      if (response.ok) {
        toast({
          title: "File Ingested",
          description: `${file.name} has been added to search index`,
        });
      } else {
        throw new Error("Failed to ingest file");
      }
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to ingest file",
        variant: "destructive",
      });
    }
  };

  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return "N/A";
    const sizes = ["Bytes", "KB", "MB", "GB"];
    if (bytes === 0) return "0 Bytes";
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round((bytes / Math.pow(1024, i)) * 100) / 100 + " " + sizes[i];
  };

  const formatDate = (dateString?: string): string => {
    if (!dateString) return "N/A";
    return new Date(dateString).toLocaleDateString();
  };

  useEffect(() => {
    fetchConnectionStatus();
  }, []);

  useEffect(() => {
    if (connectionStatus?.is_connected) {
      fetchFiles(currentFolderId);
    }
  }, [connectionStatus?.is_connected, currentFolderId]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        <p className="mt-4 text-gray-500">Loading OneDrive integration...</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="space-y-1">
        <h2 className="text-2xl font-bold tracking-tight">
          OneDrive Integration
        </h2>
        <p className="text-gray-500">
          Connect your OneDrive to search and manage files directly within ATOM
        </p>
      </div>

      <div className="p-6 border rounded-lg bg-white dark:bg-gray-900 space-y-4">
        <h3 className="text-lg font-semibold">Connection Status</h3>

        {error && (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {connectionStatus?.is_connected ? (
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Badge className="bg-green-500 hover:bg-green-600">Connected</Badge>
              <span className="text-sm text-gray-600">
                as {connectionStatus.email || connectionStatus.display_name}
              </span>
            </div>
            {connectionStatus.drive_type && (
              <p className="text-sm text-gray-600">
                Drive Type: {connectionStatus.drive_type}
              </p>
            )}
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDisconnect}
            >
              Disconnect OneDrive
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center space-x-2">
              <Badge variant="destructive">Not Connected</Badge>
              {connectionStatus?.reason && (
                <span className="text-sm text-gray-600">{connectionStatus.reason}</span>
              )}
            </div>
            <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleConnect}>
              Connect OneDrive
            </Button>
          </div>
        )}
      </div>

      {connectionStatus?.is_connected && (
        <div className="p-6 border rounded-lg bg-white dark:bg-gray-900 space-y-4">
          <h3 className="text-lg font-semibold">Files & Folders</h3>

          <nav className="flex items-center space-x-2 text-sm text-gray-500 mb-4">
            {pathHistory.map((item, index) => (
              <React.Fragment key={item.id || "root"}>
                {index > 0 && <ChevronRight className="h-4 w-4" />}
                <button
                  onClick={() => handleBreadcrumbClick(index)}
                  className={`hover:underline ${index === pathHistory.length - 1
                      ? "font-semibold text-gray-900 dark:text-gray-100 cursor-default"
                      : "text-blue-500 cursor-pointer"
                    }`}
                  disabled={index === pathHistory.length - 1}
                >
                  {item.name}
                </button>
              </React.Fragment>
            ))}
          </nav>

          {isLoadingFiles && files.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
              <p className="mt-2 text-gray-500">Loading files...</p>
            </div>
          ) : files.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-gray-500">No files found in this folder</p>
            </div>
          ) : (
            <>
              <div className="border rounded-md">
                <Table>
                  <TableHeader>
                    <TableRow>
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
                        className={
                          file.is_folder
                            ? "cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800"
                            : ""
                        }
                        onClick={() => file.is_folder && handleFileClick(file)}
                      >
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            <span className="text-lg">{file.icon}</span>
                            <span className="font-medium">{file.name}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={file.is_folder ? "default" : "secondary"}>
                            {file.is_folder ? "Folder" : "File"}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatDate(file.modified_time)}</TableCell>
                        <TableCell>{formatFileSize(file.size)}</TableCell>
                        <TableCell>
                          <div className="flex items-center space-x-2">
                            {!file.is_folder && file.web_url && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  window.open(file.web_url, "_blank");
                                }}
                              >
                                <ExternalLink className="h-4 w-4" />
                              </Button>
                            )}
                            {!file.is_folder && (
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleIngestFile(file);
                                }}
                              >
                                <Download className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>

              {nextPageToken && (
                <div className="flex justify-center mt-4">
                  <Button
                    onClick={() =>
                      fetchFiles(currentFolderId, nextPageToken, true)
                    }
                    disabled={isLoadingFiles}
                    variant="outline"
                  >
                    {isLoadingFiles ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="mr-2 h-4 w-4" />
                    )}
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

export default OneDriveIntegration;
