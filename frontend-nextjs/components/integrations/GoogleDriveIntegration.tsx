import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  VStack,
  HStack,
  Text,
  Heading,
  Spinner,
  Alert,
  AlertIcon,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Badge,
  IconButton,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  useToast,
} from '@chakra-ui/react';
import { ChevronRightIcon, DownloadIcon, ExternalLinkIcon, RepeatIcon } from '@chakra-ui/icons';

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
  const [nextPageToken, setNextPageToken] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const toast = useToast();

  // Fetch connection status
  const fetchConnectionStatus = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // This would typically call your backend API
      const response = await fetch('/api/gdrive/connection-status');
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

      const response = await fetch(`/api/gdrive/list-files?${params.toString()}`);

      if (response.ok) {
        const data: FileListResponse = await response.json();

        if (isLoadMore) {
          setFiles(prev => [...prev, ...data.files]);
        } else {
          setFiles(data.files);
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

  // Handle Google Drive disconnection
  const handleDisconnect = async () => {
    try {
      const response = await fetch('/api/auth/gdrive/disconnect', { method: 'POST' });
      if (response.ok) {
        toast({
          title: 'Disconnected',
          description: 'Google Drive has been disconnected',
          status: 'success',
          duration: 3000,
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
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Handle file ingestion
  const handleIngestFile = async (file: GoogleDriveFile) => {
    try {
      const response = await fetch('/api/ingest-gdrive-document', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          file_id: file.id,
          metadata: {
            name: file.name,
            mimeType: file.mimeType,
            webViewLink: file.webViewLink,
          },
        }),
      });

      if (response.ok) {
        toast({
          title: 'File Ingested',
          description: `${file.name} has been added to search index`,
          status: 'success',
          duration: 3000,
        });
      } else {
        throw new Error('Failed to ingest file');
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to ingest file',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Format file size
  const formatFileSize = (bytes?: number): string => {
    if (!bytes) return 'N/A';
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  // Format date
  const formatDate = (dateString?: string): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString();
  };

  // Get file icon based on mime type
  const getFileIcon = (file: GoogleDriveFile): string => {
    if (file.isFolder) return '📁';

    const mimeType = file.mimeType;
    if (mimeType.includes('document')) return '📄';
    if (mimeType.includes('spreadsheet')) return '📊';
    if (mimeType.includes('presentation')) return '📽️';
    if (mimeType.includes('image')) return '🖼️';
    if (mimeType.includes('pdf')) return '📕';
    if (mimeType.includes('video')) return '🎬';
    if (mimeType.includes('audio')) return '🎵';

    return '📄';
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
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading Google Drive integration...</Text>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>Google Drive Integration</Heading>
          <Text color="gray.600">
            Connect your Google Drive to search and manage files directly within ATOM
          </Text>
        </Box>

        {/* Connection Status */}
        <Box p={4} borderWidth={1} borderRadius="md" bg="white">
          <Heading size="md" mb={4}>Connection Status</Heading>

          {error && (
            <Alert status="error" mb={4}>
              <AlertIcon />
              {error}
            </Alert>
          )}

          {connectionStatus?.isConnected ? (
            <VStack align="start" spacing={3}>
              <HStack>
                <Badge colorScheme="green">Connected</Badge>
                <Text>as {connectionStatus.email}</Text>
              </HStack>
              <Button
                colorScheme="red"
                variant="outline"
                size="sm"
                onClick={handleDisconnect}
              >
                Disconnect Google Drive
              </Button>
            </VStack>
          ) : (
            <VStack align="start" spacing={3}>
              <Badge colorScheme="red">Not Connected</Badge>
              {connectionStatus?.reason && (
                <Text color="gray.600">{connectionStatus.reason}</Text>
              )}
              <Button
                colorScheme="blue"
                onClick={handleConnect}
              >
                Connect Google Drive
              </Button>
            </VStack>
          )}
        </Box>

        {/* File Browser - Only show when connected */}
        {connectionStatus?.isConnected && (
          <Box p={4} borderWidth={1} borderRadius="md" bg="white">
            <Heading size="md" mb={4}>Files & Folders</Heading>

            {/* Breadcrumb Navigation */}
            <Breadcrumb spacing={2} mb={4} separator={<ChevronRightIcon color="gray.500" />}>
              {pathHistory.map((item, index) => (
                <BreadcrumbItem key={item.id || 'root'}>
                  <BreadcrumbLink
                    onClick={() => handleBreadcrumbClick(index)}
                    color={index === pathHistory.length - 1 ? 'gray.700' : 'blue.500'}
                    cursor={index === pathHistory.length - 1 ? 'default' : 'pointer'}
                    fontWeight={index === pathHistory.length - 1 ? 'bold' : 'normal'}
                  >
                    {item.name}
                  </BreadcrumbLink>
                </BreadcrumbItem>
              ))}
            </Breadcrumb>

            {/* Files Table */}
            {isLoadingFiles && files.length === 0 ? (
              <Box textAlign="center" py={8}>
                <Spinner size="lg" />
                <Text mt={2}>Loading files...</Text>
              </Box>
            ) : files.length === 0 ? (
              <Box textAlign="center" py={8}>
                <Text color="gray.500">No files found in this folder</Text>
              </Box>
            ) : (
              <>
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Name</Th>
                      <Th>Type</Th>
                      <Th>Modified</Th>
                      <Th>Size</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {files.map((file) => (
                      <Tr
                        key={file.id}
                        _hover={{ bg: 'gray.50' }}
                        cursor={file.isFolder ? 'pointer' : 'default'}
                        onClick={() => handleFileClick(file)}
                      >
                        <Td>
                          <HStack>
                            <Text fontSize="lg">{getFileIcon(file)}</Text>
                            <Text fontWeight="medium">{file.name}</Text>
                          </HStack>
                        </Td>
                        <Td>
                          <Badge colorScheme={file.isFolder ? 'blue' : 'gray'}>
                            {file.isFolder ? 'Folder' : 'File'}
                          </Badge>
                        </Td>
                        <Td>{formatDate(file.modifiedTime)}</Td>
                        <Td>{formatFileSize(file.size)}</Td>
                        <Td>
                          <HStack spacing={2}>
                            {!file.isFolder && file.webViewLink && (
                              <IconButton
                                aria-label="Open in Google Drive"
                                icon={<ExternalLinkIcon />}
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  window.open(file.webViewLink, '_blank');
                                }}
                              />
                            )}
                            {!file.isFolder && (
                              <IconButton
                                aria-label="Ingest file"
                                icon={<DownloadIcon />}
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleIngestFile(file);
                                }}
                              />
                            )}
                          </HStack>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>

                {/* Load More Button */}
                {nextPageToken && (
                  <Box textAlign="center" mt={4}>
                    <Button
                      onClick={() => fetchFiles(currentFolderId, nextPageToken, true)}
                      isLoading={isLoadingFiles}
                      leftIcon={<RepeatIcon />}
                      variant="outline"
                    >
                      Load More Files
                    </Button>
                  </Box>
                )}
              </>
            )}
          </Box>
        )}
      </VStack>
    </Box>
  );
};

export default GoogleDriveIntegration;
