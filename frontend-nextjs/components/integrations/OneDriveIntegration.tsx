import React, { useState, useEffect } from "react";
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
} from "@chakra-ui/react";
import {
  ChevronRightIcon,
  DownloadIcon,
  ExternalLinkIcon,
  RepeatIcon,
} from "@chakra-ui/icons";

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
  const toast = useToast();

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
          status: "success",
          duration: 3000,
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
        status: "error",
        duration: 3000,
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
          status: "success",
          duration: 3000,
        });
      } else {
        throw new Error("Failed to ingest file");
      }
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to ingest file",
        status: "error",
        duration: 3000,
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
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading OneDrive integration...</Text>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        <Box>
          <Heading size="lg" mb={2}>
            OneDrive Integration
          </Heading>
          <Text color="gray.600">
            Connect your OneDrive to search and manage files directly within
            ATOM
          </Text>
        </Box>

        <Box p={4} borderWidth={1} borderRadius="md" bg="white">
          <Heading size="md" mb={4}>
            Connection Status
          </Heading>

          {error && (
            <Alert status="error" mb={4}>
              <AlertIcon />
              {error}
            </Alert>
          )}

          {connectionStatus?.is_connected ? (
            <VStack align="start" spacing={3}>
              <HStack>
                <Badge colorScheme="green">Connected</Badge>
                <Text>
                  as {connectionStatus.email || connectionStatus.display_name}
                </Text>
              </HStack>
              {connectionStatus.drive_type && (
                <Text color="gray.600">
                  Drive Type: {connectionStatus.drive_type}
                </Text>
              )}
              <Button
                colorScheme="red"
                variant="outline"
                size="sm"
                onClick={handleDisconnect}
              >
                Disconnect OneDrive
              </Button>
            </VStack>
          ) : (
            <VStack align="start" spacing={3}>
              <Badge colorScheme="red">Not Connected</Badge>
              {connectionStatus?.reason && (
                <Text color="gray.600">{connectionStatus.reason}</Text>
              )}
              <Button colorScheme="blue" onClick={handleConnect}>
                Connect OneDrive
              </Button>
            </VStack>
          )}
        </Box>

        {connectionStatus?.is_connected && (
          <Box p={4} borderWidth={1} borderRadius="md" bg="white">
            <Heading size="md" mb={4}>
              Files & Folders
            </Heading>

            <Breadcrumb
              spacing={2}
              mb={4}
              separator={<ChevronRightIcon color="gray.500" />}
            >
              {pathHistory.map((item, index) => (
                <BreadcrumbItem key={item.id || "root"}>
                  <BreadcrumbLink
                    onClick={() => handleBreadcrumbClick(index)}
                    color={
                      index === pathHistory.length - 1 ? "gray.700" : "blue.500"
                    }
                    cursor={
                      index === pathHistory.length - 1 ? "default" : "pointer"
                    }
                    fontWeight={
                      index === pathHistory.length - 1 ? "bold" : "normal"
                    }
                  >
                    {item.name}
                  </BreadcrumbLink>
                </BreadcrumbItem>
              ))}
            </Breadcrumb>

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
                        _hover={{ bg: "gray.50" }}
                        cursor={file.is_folder ? "pointer" : "default"}
                        onClick={() => handleFileClick(file)}
                      >
                        <Td>
                          <HStack>
                            <Text fontSize="lg">{file.icon}</Text>
                            <Text fontWeight="medium">{file.name}</Text>
                          </HStack>
                        </Td>
                        <Td>
                          <Badge colorScheme={file.is_folder ? "blue" : "gray"}>
                            {file.is_folder ? "Folder" : "File"}
                          </Badge>
                        </Td>
                        <Td>{formatDate(file.modified_time)}</Td>
                        <Td>{formatFileSize(file.size)}</Td>
                        <Td>
                          <HStack spacing={2}>
                            {!file.is_folder && file.web_url && (
                              <IconButton
                                aria-label="Open in OneDrive"
                                icon={<ExternalLinkIcon />}
                                size="sm"
                                variant="ghost"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  window.open(file.web_url, "_blank");
                                }}
                              />
                            )}
                            {!file.is_folder && (
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

                {nextPageToken && (
                  <Box textAlign="center" mt={4}>
                    <Button
                      onClick={() =>
                        fetchFiles(currentFolderId, nextPageToken, true)
                      }
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

export default OneDriveIntegration;
