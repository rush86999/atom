import React, { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/tauri";
import { open, message } from "@tauri-apps/api/dialog";
import { readDir, readTextFile } from "@tauri-apps/api/fs";
import {
  Box,
  Input,
  Button,
  VStack,
  HStack,
  Text,
  Heading,
  Card,
  CardBody,
  Stack,
  Badge,
  Flex,
  Spinner,
  Alert,
  AlertIcon,
  Select,
  Checkbox,
  CheckboxGroup,
  Progress,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  IconButton,
  Tooltip,
  Divider,
} from "@chakra-ui/react";
import {
  SearchIcon,
  ChevronDownIcon,
  StarIcon,
  AddIcon,
  FolderIcon,
  FileIcon,
} from "@chakra-ui/icons";

interface SearchResult {
  id: string;
  title: string;
  content: string;
  doc_type: string;
  source_uri: string;
  similarity_score: number;
  keyword_score?: number;
  combined_score?: number;
  metadata: {
    created_at: string;
    author?: string;
    tags?: string[];
    participants?: string[];
    file_size?: number;
    file_path?: string;
  };
}

interface LocalFile {
  path: string;
  name: string;
  size: number;
  modified: string;
  type: string;
}

interface IngestionStatus {
  status: "idle" | "scanning" | "processing" | "completed" | "error";
  filesProcessed: number;
  totalFiles: number;
  currentFile?: string;
  error?: string;
}

const Research: React.FC = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchType, setSearchType] = useState<
    "hybrid" | "semantic" | "keyword"
  >("hybrid");
  const [localFiles, setLocalFiles] = useState<LocalFile[]>([]);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    status: "idle",
    filesProcessed: 0,
    totalFiles: 0,
  });
  const [activeTab, setActiveTab] = useState(0);

  // Mock user ID - in real app this would come from auth context
  const userId = "desktop-user-123";

  // Supported file extensions for local ingestion
  const supportedExtensions = [
    ".txt",
    ".md",
    ".pdf",
    ".docx",
    ".pptx",
    ".xlsx",
    ".csv",
    ".json",
  ];

  // Load local files from a directory
  const loadLocalFiles = async (directoryPath: string) => {
    try {
      const entries = await readDir(directoryPath, { recursive: true });
      const files: LocalFile[] = [];

      for (const entry of entries) {
        if (entry.children) {
          // This is a directory, skip for now
          continue;
        }

        const fileExtension = entry.name
          ?.toLowerCase()
          .substring(entry.name.lastIndexOf("."));
        if (fileExtension && supportedExtensions.includes(fileExtension)) {
          files.push({
            path: entry.path,
            name: entry.name || "Unknown",
            size: entry.size || 0,
            modified: new Date().toISOString(), // Tauri doesn't provide modified time in readDir
            type: fileExtension.substring(1),
          });
        }
      }

      setLocalFiles(files);
    } catch (err) {
      console.error("Failed to load local files:", err);
      await message(`Failed to load files: ${err}`, {
        title: "Error",
        type: "error",
      });
    }
  };

  // Select directory for local files
  const selectDirectory = async () => {
    try {
      const selected = await open({
        directory: true,
        multiple: false,
        title: "Select directory to scan for documents",
      });

      if (selected && typeof selected === "string") {
        await loadLocalFiles(selected);
        await message(`Loaded ${localFiles.length} files from directory`, {
          title: "Success",
          type: "info",
        });
      }
    } catch (err) {
      console.error("Failed to select directory:", err);
    }
  };

  // Ingest selected files to LanceDB
  const ingestSelectedFiles = async () => {
    if (selectedFiles.length === 0) {
      await message("Please select files to ingest", {
        title: "Warning",
        type: "warning",
      });
      return;
    }

    setIngestionStatus({
      status: "scanning",
      filesProcessed: 0,
      totalFiles: selectedFiles.length,
    });

    try {
      for (let i = 0; i < selectedFiles.length; i++) {
        const filePath = selectedFiles[i];
        const file = localFiles.find((f) => f.path === filePath);

        setIngestionStatus((prev) => ({
          ...prev,
          status: "processing",
          currentFile: file?.name,
          filesProcessed: i,
        }));

        // Read file content
        const content = await readTextFile(filePath);

        // Call backend to ingest document
        await invoke("ingest_document", {
          filePath,
          content,
          userId,
          title: file?.name || "Untitled",
          docType: file?.type || "document",
        });

        // Simulate processing delay
        await new Promise((resolve) => setTimeout(resolve, 500));
      }

      setIngestionStatus({
        status: "completed",
        filesProcessed: selectedFiles.length,
        totalFiles: selectedFiles.length,
      });

      await message(`Successfully ingested ${selectedFiles.length} files`, {
        title: "Success",
        type: "info",
      });
      setSelectedFiles([]);
    } catch (err) {
      setIngestionStatus({
        status: "error",
        filesProcessed: 0,
        totalFiles: selectedFiles.length,
        error: `Failed to ingest files: ${err}`,
      });
      await message(`Failed to ingest files: ${err}`, {
        title: "Error",
        type: "error",
      });
    }
  };

  // Perform search using LanceDB
  const handleSearch = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const searchResults = await invoke("search_documents", {
        query: query.trim(),
        userId,
        searchType,
        limit: 20,
      });

      setResults(searchResults as SearchResult[]);
    } catch (err) {
      setError(`Search failed: ${err}`);
      console.error("Search error:", err);
    } finally {
      setLoading(false);
    }
  };

  // Toggle file selection
  const toggleFileSelection = (filePath: string) => {
    setSelectedFiles((prev) =>
      prev.includes(filePath)
        ? prev.filter((path) => path !== filePath)
        : [...prev, filePath],
    );
  };

  // Select all files
  const selectAllFiles = () => {
    setSelectedFiles(localFiles.map((file) => file.path));
  };

  // Clear selection
  const clearSelection = () => {
    setSelectedFiles([]);
  };

  const formatScore = (score: number) => {
    return (score * 100).toFixed(1) + "%";
  };

  const getDocTypeColor = (docType: string) => {
    const colors: { [key: string]: string } = {
      document: "blue",
      meeting: "green",
      note: "purple",
      email: "orange",
      pdf: "red",
      txt: "gray",
      md: "blue",
      docx: "blue",
    };
    return colors[docType] || "gray";
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  return (
    <Box maxW="1200px" mx="auto" p={6}>
      <VStack spacing={6} align="stretch">
        <Heading size="xl" color="blue.600">
          Research & Document Search
        </Heading>
        <Text fontSize="lg" color="gray.600">
          Search across your documents and ingest local files for AI-powered
          search
        </Text>

        <Tabs index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>Search Documents</Tab>
            <Tab>Local File Ingestion</Tab>
          </TabList>

          <TabPanels>
            {/* Search Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                {/* Search Controls */}
                <Card>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <HStack spacing={4}>
                        <Input
                          placeholder="Search across your documents, meetings, notes..."
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                          onKeyPress={(e) =>
                            e.key === "Enter" && handleSearch()
                          }
                          size="lg"
                          flex={1}
                        />
                        <Select
                          value={searchType}
                          onChange={(e) => setSearchType(e.target.value as any)}
                          width="180px"
                        >
                          <option value="hybrid">Hybrid Search</option>
                          <option value="semantic">Semantic Search</option>
                          <option value="keyword">Keyword Search</option>
                        </Select>
                        <Button
                          leftIcon={<SearchIcon />}
                          colorScheme="blue"
                          size="lg"
                          onClick={handleSearch}
                          isLoading={loading}
                          loadingText="Searching..."
                        >
                          Search
                        </Button>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>

                {/* Error Display */}
                {error && (
                  <Alert status="error" borderRadius="lg">
                    <AlertIcon />
                    {error}
                  </Alert>
                )}

                {/* Search Results */}
                <Box>
                  {loading ? (
                    <Flex justify="center" align="center" height="200px">
                      <Spinner size="xl" color="blue.500" />
                    </Flex>
                  ) : results.length > 0 ? (
                    <VStack spacing={4} align="stretch">
                      <Flex justify="space-between" align="center">
                        <Text color="gray.600">
                          Found {results.length} results for "{query}"
                        </Text>
                      </Flex>

                      {results.map((result) => (
                        <Card
                          key={result.id}
                          boxShadow="md"
                          _hover={{ boxShadow: "lg" }}
                          transition="all 0.2s"
                        >
                          <CardBody>
                            <VStack align="start" spacing={3}>
                              <Flex
                                justify="space-between"
                                width="100%"
                                align="start"
                              >
                                <Heading size="md" color="blue.700">
                                  {result.title}
                                </Heading>
                                <Badge
                                  colorScheme={getDocTypeColor(result.doc_type)}
                                >
                                  {result.doc_type}
                                </Badge>
                              </Flex>

                              <Text color="gray.700" noOfLines={3}>
                                {result.content}
                              </Text>

                              <Flex gap={4} wrap="wrap">
                                <HStack>
                                  <StarIcon color="yellow.500" />
                                  <Text fontSize="sm" color="gray.600">
                                    Relevance:{" "}
                                    {formatScore(
                                      result.combined_score ||
                                        result.similarity_score,
                                    )}
                                  </Text>
                                </HStack>

                                {result.metadata.author && (
                                  <Text fontSize="sm" color="gray.600">
                                    Author: {result.metadata.author}
                                  </Text>
                                )}

                                <Text fontSize="sm" color="gray.600">
                                  Created:{" "}
                                  {new Date(
                                    result.metadata.created_at,
                                  ).toLocaleDateString()}
                                </Text>

                                {result.metadata.file_path && (
                                  <Text
                                    fontSize="sm"
                                    color="gray.600"
                                    fontFamily="mono"
                                  >
                                    Path: {result.metadata.file_path}
                                  </Text>
                                )}
                              </Flex>

                              {result.metadata.tags &&
                                result.metadata.tags.length > 0 && (
                                  <Flex gap={2} wrap="wrap">
                                    {result.metadata.tags.map((tag, index) => (
                                      <Badge
                                        key={index}
                                        variant="subtle"
                                        colorScheme="gray"
                                      >
                                        {tag}
                                      </Badge>
                                    ))}
                                  </Flex>
                                )}
                            </VStack>
                          </CardBody>
                        </Card>
                      ))}
                    </VStack>
                  ) : query && !loading ? (
                    <Flex justify="center" align="center" height="200px">
                      <Text color="gray.500" fontSize="lg">
                        No results found for "{query}"
                      </Text>
                    </Flex>
                  ) : (
                    <Flex justify="center" align="center" height="200px">
                      <Text color="gray.500" fontSize="lg">
                        Enter a search query to find documents
                      </Text>
                    </Flex>
                  )}
                </Box>
              </VStack>
            </TabPanel>

            {/* Local File Ingestion Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                {/* Directory Selection */}
                <Card>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <Heading size="md">Local File Ingestion</Heading>
                      <Text color="gray.600">
                        Select a directory to scan for documents and add them to
                        your search index
                      </Text>

                      <HStack spacing={4}>
                        <Button
                          leftIcon={<FolderIcon />}
                          colorScheme="blue"
                          onClick={selectDirectory}
                        >
                          Select Directory
                        </Button>
                        <Text color="gray.600">
                          {localFiles.length > 0
                            ? `${localFiles.length} files found`
                            : "No directory selected"}
                        </Text>
                      </HStack>

                      {localFiles.length > 0 && (
                        <HStack spacing={4}>
                          <Button size="sm" onClick={selectAllFiles}>
                            Select All
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={clearSelection}
                          >
                            Clear Selection
                          </Button>
                          <Text color="gray.600">
                            {selectedFiles.length} of {localFiles.length} files
                            selected
                          </Text>
                        </HStack>
                      )}
                    </VStack>
                  </CardBody>
                </Card>

                {/* Ingestion Progress */}
                {ingestionStatus.status !== "idle" && (
                  <Card>
                    <CardBody>
                      <VStack spacing={3} align="stretch">
                        <Heading size="sm">Ingestion Progress</Heading>
                        <Progress
                          value={
                            (ingestionStatus.filesProcessed /
                              ingestionStatus.totalFiles) *
                            100
                          }
                          colorScheme="blue"
                          size="lg"
                          borderRadius="md"
                        />
                        <Flex justify="space-between">
                          <Text fontSize="sm" color="gray.600">
                            {ingestionStatus.status === "completed"
                              ? "Completed"
                              : ingestionStatus.status === "error"
                                ? "Error"
                                : `Processing... (${ingestionStatus.filesProcessed}/${ingestionStatus.totalFiles})`}
                          </Text>
                          <Text fontSize="sm" color="gray.600">
                            {ingestionStatus.currentFile &&
                              `Current: ${ingestionStatus.currentFile}`}
                          </Text>
                        </Flex>
                        {ingestionStatus.error && (
                          <Alert status="error" size="sm">
                            <AlertIcon />
                            {ingestionStatus.error}
                          </Alert>
                        )}
                      </VStack>
                    </CardBody>
                  </Card>
                )}

                {/* File List */}
                {localFiles.length > 0 && (
                  <Card>
                    <CardBody>
                      <VStack spacing={4} align="stretch">
                        <Flex justify="space-between" align="center">
                          <Heading size="md">Files Found</Heading>
                          <Button
                            leftIcon={<AddIcon />}
                            colorScheme="green"
                            onClick={ingestSelectedFiles}
                            isDisabled={
                              selectedFiles.length === 0 ||
                              ingestionStatus.status === "processing"
                            }
                          >
                            Ingest Selected Files
                          </Button>
                        </Flex>

                        <VStack
                          spacing={2}
                          align="stretch"
                          maxH="400px"
                          overflowY="auto"
                        >
                          {localFiles.map((file) => (
                            <Card
                              key={file.path}
                              variant={
                                selectedFiles.includes(file.path)
                                  ? "filled"
                                  : "outline"
                              }
                              cursor="pointer"
                              onClick={() => toggleFileSelection(file.path)}
                              _hover={{ bg: "gray.50" }}
                            >
                              <CardBody py={3}>
                                <Flex justify="space-between" align="center">
                                  <HStack spacing={3}>
                                    <FileIcon color="blue.500" />
                                    <VStack align="start" spacing={0}>
                                      <Text fontWeight="medium">
                                        {file.name}
                                      </Text>
                                      <Text fontSize="sm" color="gray.600">
                                        {formatFileSize(file.size)} •{" "}
                                        {file.type.toUpperCase()}
                                      </Text>
                                    </VStack>
                                  </HStack>
                                  <Checkbox
                                    isChecked={selectedFiles.includes(
                                      file.path,
                                    )}
                                    onChange={() =>
                                      toggleFileSelection(file.path)
                                    }
                                  />
                                </Flex>
                              </CardBody>
                            </Card>
                          ))}
                        </VStack>
                      </VStack>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default Research;
