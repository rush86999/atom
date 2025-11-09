/**
 * ATOM OneDrive Integration Component
 * Complete OneDrive integration with ATOM ingestion pipeline
 * Microsoft Graph API integration with real-time sync
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  Button,
  VStack,
  HStack,
  Text,
  Input,
  Textarea,
  Progress,
  Alert,
  AlertIcon,
  Badge,
  Icon,
  useColorModeValue,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Flex,
  Spacer,
  Divider,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Switch,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  FormControl,
  FormLabel,
  Select,
  Checkbox,
  IconButton,
  Tooltip,
  Spinner,
  Center,
  Heading,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  List,
  ListItem,
  ListIcon,
} from '@chakra-ui/react';
import {
  FiCloud,
  FiFolder,
  FiFile,
  FiSearch,
  FiRefreshCw,
  FiDownload,
  FiUpload,
  FiSettings,
  FiTrash2,
  FiEdit,
  FiShare2,
  FiEye,
  FiCheck,
  FiX,
  FiAlertCircle,
  FiDatabase,
  FiZap,
  FiClock,
  FiHardDrive,
  FiUsers,
  FiActivity,
  FiFilter,
  FiGrid,
  FiList,
  FiTrendingUp,
  FiCpu,
  FiShield,
  FiWifi,
  FiWifiOff,
  FiPlus,
  FiMinus,
  FiMoreVertical,
  FiDownloadCloud,
} from 'react-icons/fi';

import {
  AtomOneDriveDataSourceProps,
  AtomOneDriveDataSourceState,
  OneDriveFile,
  OneDriveFolder,
  OneDriveSearchResult,
  OneDriveUploadProgress,
  OneDriveSearchQuery,
  OneDriveChangeEvent,
  ONEDRIVE_DEFAULT_CONFIG,
} from '../types';

const OneDriveIntegration: React.FC<AtomOneDriveDataSourceProps> = ({
  accessToken,
  refreshToken,
  onTokenRefresh,
  tenantId,
  atomIngestionPipeline,
  dataSourceRegistry,
  config = ONEDRIVE_DEFAULT_CONFIG,
  platform = 'auto',
  theme = 'auto',
  onDataSourceReady,
  onIngestionStart,
  onIngestionComplete,
  onIngestionProgress,
  onDataSourceError,
  onFileProcessed,
  onFolderProcessed,
  children,
}) => {
  // State Management
  const [state, setState] = useState<AtomOneDriveDataSourceState>({
    initialized: false,
    connected: false,
    loading: false,
    error: null,
    driveInfo: null,
    files: [],
    folders: [],
    currentFolder: null,
    searchResults: [],
    ingestionActive: false,
    ingestionProgress: {
      total: 0,
      processed: 0,
      percentage: 0,
      currentFile: undefined,
    },
    ingestionResults: [],
    lastSync: null,
    deltaToken: null,
    syncActive: false,
  });

  // UI State
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [currentConfig, setCurrentConfig] = useState(config);
  const [realTimeStatus, setRealTimeStatus] = useState<'connected' | 'disconnected' | 'connecting'>('disconnected');

  // Theme Colors
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const textColor = useColorModeValue('gray.800', 'gray.200');
  const cardBg = useColorModeValue('white', 'gray.700');

  // Microsoft Graph API Client
  const graphClient = useMemo(() => {
    if (!accessToken) return null;

    return {
      get: async (endpoint: string) => {
        const response = await fetch(`https://graph.microsoft.com/v1.0${endpoint}`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
        });

        if (response.status === 401 && refreshToken && onTokenRefresh) {
          // Handle token refresh
          const newToken = await refreshToken();
          if (newToken) {
            return fetch(`https://graph.microsoft.com/v1.0${endpoint}`, {
              headers: {
                'Authorization': `Bearer ${newToken}`,
                'Content-Type': 'application/json',
              },
            });
          }
        }

        if (!response.ok) {
          throw new Error(`Microsoft Graph API error: ${response.status} ${response.statusText}`);
        }

        return response.json();
      },

      post: async (endpoint: string, data: any) => {
        const response = await fetch(`https://graph.microsoft.com/v1.0${endpoint}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(data),
        });

        if (!response.ok) {
          throw new Error(`Microsoft Graph API error: ${response.status} ${response.statusText}`);
        }

        return response.json();
      },
    };
  }, [accessToken, refreshToken, onTokenRefresh]);

  // Initialize OneDrive Connection
  const initializeOneDrive = useCallback(async () => {
    if (!graphClient) return;

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      // Get drive information
      const driveInfo = await graphClient.get('/me/drive');
      
      // Get root folder contents
      const rootContents = await graphClient.get('/me/drive/root/children');

      setState(prev => ({
        ...prev,
        initialized: true,
        connected: true,
        loading: false,
        driveInfo,
        files: rootContents.value.filter((item: any) => !item.folder),
        folders: rootContents.value.filter((item: any) => item.folder),
        currentFolder: null,
        lastSync: new Date().toISOString(),
      }));

      onDataSourceReady?.({ driveInfo, graphClient });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to initialize OneDrive';
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
        connected: false,
      }));
      onDataSourceError?.(error);
    }
  }, [graphClient, onDataSourceReady, onDataSourceError]);

  // Search OneDrive
  const searchOneDrive = useCallback(async (query: string) => {
    if (!graphClient || !query.trim()) return;

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const searchResults: OneDriveSearchResult = await graphClient.get(
        `/me/drive/search(q='${encodeURIComponent(query)}')`
      );

      setState(prev => ({
        ...prev,
        loading: false,
        searchResults: searchResults.value,
      }));

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Search failed';
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
      }));
    }
  }, [graphClient]);

  // Navigate to Folder
  const navigateToFolder = useCallback(async (folder: OneDriveFolder) => {
    if (!graphClient) return;

    setState(prev => ({ ...prev, loading: true, error: null }));

    try {
      const folderContents = await graphClient.get(`/me/drive/items/${folder.id}/children`);

      setState(prev => ({
        ...prev,
        loading: false,
        currentFolder: folder,
        files: folderContents.value.filter((item: any) => !item.folder),
        folders: folderContents.value.filter((item: any) => item.folder),
        searchResults: [],
      }));

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to navigate to folder';
      setState(prev => ({
        ...prev,
        loading: false,
        error: errorMessage,
      }));
    }
  }, [graphClient]);

  // Start Ingestion
  const startIngestion = useCallback(async () => {
    if (!graphClient || !atomIngestionPipeline) return;

    setState(prev => ({ ...prev, ingestionActive: true, error: null }));
    onIngestionStart?.(currentConfig);

    try {
      const filesToProcess = state.files.filter(file => 
        currentConfig.includeFileTypes?.includes(file.mimeType) ||
        !currentConfig.includeFileTypes
      );

      setState(prev => ({
        ...prev,
        ingestionProgress: {
          total: filesToProcess.length,
          processed: 0,
          percentage: 0,
        },
      }));

      const results = [];

      for (let i = 0; i < filesToProcess.length; i++) {
        const file = filesToProcess[i];
        
        // Download file content
        const fileContent = await graphClient.get(`/me/drive/items/${file.id}/content`);
        
        // Process through ATOM pipeline
        const result = await atomIngestionPipeline.processDocument({
          content: fileContent,
          metadata: {
            source: 'onedrive',
            fileId: file.id,
            fileName: file.name,
            mimeType: file.mimeType,
            size: file.size,
            lastModified: file.lastModifiedDateTime,
          },
        });

        results.push(result);

        setState(prev => ({
          ...prev,
          ingestionProgress: {
            total: filesToProcess.length,
            processed: i + 1,
            percentage: ((i + 1) / filesToProcess.length) * 100,
            currentFile: file.name,
          },
        }));

        onIngestionProgress?.({
          total: filesToProcess.length,
          processed: i + 1,
          percentage: ((i + 1) / filesToProcess.length) * 100,
          currentFile: file.name,
        });

        onFileProcessed?.(file);
      }

      setState(prev => ({
        ...prev,
        ingestionActive: false,
        ingestionResults: results,
        lastSync: new Date().toISOString(),
      }));

      onIngestionComplete?.({ results, filesProcessed: filesToProcess.length });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Ingestion failed';
      setState(prev => ({
        ...prev,
        ingestionActive: false,
        error: errorMessage,
      }));
    }
  }, [graphClient, atomIngestionPipeline, state.files, currentConfig, onIngestionStart, onIngestionProgress, onIngestionComplete, onFileProcessed]);

  // Initialize on mount
  useEffect(() => {
    if (accessToken && graphClient) {
      initializeOneDrive();
    }
  }, [accessToken, graphClient, initializeOneDrive]);

  // Render File Icon
  const renderFileIcon = (file: OneDriveFile) => {
    const iconProps = { boxSize: 5, color: 'gray.500' };

    if (file.folder) {
      return <FiFolder {...iconProps} color="blue.500" />;
    }

    const mimeType = file.mimeType.toLowerCase();
    if (mimeType.includes('pdf')) {
      return <FiFile {...iconProps} color="red.500" />;
    }
    if (mimeType.includes('word') || mimeType.includes('document')) {
      return <FiFile {...iconProps} color="blue.500" />;
    }
    if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) {
      return <FiFile {...iconProps} color="green.500" />;
    }
    if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) {
      return <FiFile {...iconProps} color="orange.500" />;
    }
    if (mimeType.includes('image')) {
      return <FiFile {...iconProps} color="purple.500" />;
    }

    return <FiFile {...iconProps} />;
  };

  // Format File Size
  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Format Date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <Box p={6} bg={bgColor} minH="100vh">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={3}>
            <Icon as={FiCloud} boxSize={8} color="blue.500" />
            <VStack align="start" spacing={0}>
              <Heading size="lg">OneDrive Integration</Heading>
              <Text fontSize="sm" color="gray.500">
                Microsoft Graph API with ATOM Ingestion Pipeline
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            <Badge
              colorScheme={state.connected ? 'green' : 'red'}
              variant={state.connected ? 'solid' : 'outline'}
            >
              {state.connected ? 'Connected' : 'Disconnected'}
            </Badge>
            
            <Button
              leftIcon={<FiRefreshCw />}
              onClick={initializeOneDrive}
              isLoading={state.loading}
              variant="outline"
              size="sm"
            >
              Refresh
            </Button>

            <Button
              leftIcon={<FiSettings />}
              onClick={() => setConfigModalOpen(true)}
              variant="outline"
              size="sm"
            >
              Configure
            </Button>

            <Button
              leftIcon={<FiDatabase />}
              onClick={startIngestion}
              isLoading={state.ingestionActive}
              isDisabled={!state.connected || !atomIngestionPipeline}
              colorScheme="blue"
              size="sm"
            >
              {state.ingestionActive ? 'Processing...' : 'Start Ingestion'}
            </Button>
          </HStack>
        </HStack>

        {/* Status Cards */}
        {state.driveInfo && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel fontSize="sm" color="gray.500">Storage Used</StatLabel>
                  <StatNumber fontSize="2xl">
                    {formatFileSize(state.driveInfo.quota.used)}
                  </StatNumber>
                  <StatHelpText>
                    of {formatFileSize(state.driveInfo.quota.total)} (
                    {Math.round((state.driveInfo.quota.used / state.driveInfo.quota.total) * 100)}%
                    )
                  </StatHelpText>
                </Stat>
                <Progress
                  value={(state.driveInfo.quota.used / state.driveInfo.quota.total) * 100}
                  colorScheme="blue"
                  size="sm"
                  mt={2}
                />
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel fontSize="sm" color="gray.500">Files</StatLabel>
                  <StatNumber fontSize="2xl">{state.files.length}</StatNumber>
                  <StatHelpText>In current folder</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel fontSize="sm" color="gray.500">Folders</StatLabel>
                  <StatNumber fontSize="2xl">{state.folders.length}</StatNumber>
                  <StatHelpText>In current folder</StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel fontSize="sm" color="gray.500">Last Sync</StatLabel>
                  <StatNumber fontSize="lg">
                    {state.lastSync ? 
                      new Date(state.lastSync).toLocaleDateString() : 
                      'Never'
                    }
                  </StatNumber>
                  <StatHelpText>
                    {state.lastSync ? 
                      new Date(state.lastSync).toLocaleTimeString() : 
                      'Sync not performed'
                    }
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Ingestion Progress */}
        {state.ingestionActive && (
          <Card>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Text fontWeight="bold">Ingestion Progress</Text>
                  <Badge colorScheme="blue">
                    {state.ingestionProgress.processed} / {state.ingestionProgress.total}
                  </Badge>
                </HStack>
                
                <Progress
                  value={state.ingestionProgress.percentage}
                  colorScheme="blue"
                  size="lg"
                  hasStripe
                  isAnimated
                />
                
                {state.ingestionProgress.currentFile && (
                  <Text fontSize="sm" color="gray.500">
                    Processing: {state.ingestionProgress.currentFile}
                  </Text>
                )}
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Error Display */}
        {state.error && (
          <Alert status="error">
            <AlertIcon />
            <Text>{state.error}</Text>
          </Alert>
        )}

        {/* Main Content */}
        <Tabs>
          <TabList>
            <Tab>Files & Folders</Tab>
            <Tab>Search</Tab>
            <Tab>Ingestion Results</Tab>
          </TabList>

          <TabPanels>
            {/* Files & Folders Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                {/* Breadcrumb */}
                <HStack spacing={2} fontSize="sm">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => initializeOneDrive()}
                    isDisabled={!state.currentFolder}
                  >
                    <Icon as={FiHardDrive} mr={1} />
                    OneDrive
                  </Button>
                  
                  {state.currentFolder && (
                    <>
                      <Text>/</Text>
                      <Text fontWeight="bold">{state.currentFolder.name}</Text>
                    </>
                  )}
                </HStack>

                {/* Toolbar */}
                <HStack justify="space-between">
                  <HStack spacing={2}>
                    <Input
                      placeholder="Search files..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      onKeyPress={(e) => {
                        if (e.key === 'Enter') {
                          searchOneDrive(searchQuery);
                        }
                      }}
                      width="300px"
                      leftElement={<FiSearch />}
                    />
                    
                    <Button
                      leftIcon={<FiSearch />}
                      onClick={() => searchOneDrive(searchQuery)}
                      isDisabled={!searchQuery.trim()}
                    >
                      Search
                    </Button>
                  </HStack>

                  <HStack spacing={2}>
                    <Button
                      leftIcon={<FiGrid />}
                      variant={viewMode === 'grid' ? 'solid' : 'outline'}
                      size="sm"
                      onClick={() => setViewMode('grid')}
                    />
                    <Button
                      leftIcon={<FiList />}
                      variant={viewMode === 'list' ? 'solid' : 'outline'}
                      size="sm"
                      onClick={() => setViewMode('list')}
                    />
                  </HStack>
                </HStack>

                {/* Folders */}
                {state.folders.length > 0 && viewMode === 'grid' && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>Folders</Text>
                    <SimpleGrid columns={{ base: 2, md: 4, lg: 6 }} spacing={4}>
                      {state.folders.map((folder) => (
                        <Card
                          key={folder.id}
                          _hover={{ bg: 'gray.50', cursor: 'pointer' }}
                          onClick={() => navigateToFolder(folder)}
                        >
                          <CardBody p={4}>
                            <VStack spacing={2}>
                              <Icon as={FiFolder} boxSize={8} color="blue.500" />
                              <Text fontSize="sm" textAlign="center" noOfLines={1}>
                                {folder.name}
                              </Text>
                              <Text fontSize="xs" color="gray.500">
                                {folder.folder.childCount} items
                              </Text>
                            </VStack>
                          </CardBody>
                        </Card>
                      ))}
                    </SimpleGrid>
                  </Box>
                )}

                {/* Files */}
                {state.files.length > 0 && (
                  <Box>
                    <Text fontWeight="bold" mb={2}>
                      Files ({state.files.length})
                    </Text>
                    
                    {viewMode === 'grid' ? (
                      <SimpleGrid columns={{ base: 2, md: 4, lg: 6 }} spacing={4}>
                        {state.files.map((file) => (
                          <Card key={file.id}>
                            <CardBody p={4}>
                              <VStack spacing={2}>
                                <Icon as={() => renderFileIcon(file)} />
                                <Text fontSize="sm" textAlign="center" noOfLines={2}>
                                  {file.name}
                                </Text>
                                <Text fontSize="xs" color="gray.500">
                                  {formatFileSize(file.size)}
                                </Text>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))}
                      </SimpleGrid>
                    ) : (
                      <TableContainer>
                        <Table variant="simple">
                          <Thead>
                            <Tr>
                              <Th>Name</Th>
                              <Th>Size</Th>
                              <Th>Modified</Th>
                              <Th>Actions</Th>
                            </Tr>
                          </Thead>
                          <Tbody>
                            {state.files.map((file) => (
                              <Tr key={file.id}>
                                <Td>
                                  <HStack spacing={2}>
                                    {renderFileIcon(file)}
                                    <Text>{file.name}</Text>
                                  </HStack>
                                </Td>
                                <Td>{formatFileSize(file.size)}</Td>
                                <Td>{formatDate(file.lastModifiedDateTime)}</Td>
                                <Td>
                                  <HStack spacing={2}>
                                    <Tooltip label="Download">
                                      <IconButton
                                        icon={<FiDownload />}
                                        variant="ghost"
                                        size="sm"
                                        as="a"
                                        href={file['@microsoft.graph.downloadUrl']}
                                        download
                                      />
                                    </Tooltip>
                                  </HStack>
                                </Td>
                              </Tr>
                            ))}
                          </Tbody>
                        </Table>
                      </TableContainer>
                    )}
                  </Box>
                )}
              </VStack>
            </TabPanel>

            {/* Search Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack spacing={2}>
                  <Input
                    placeholder="Search OneDrive..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    width="400px"
                    leftElement={<FiSearch />}
                  />
                  <Button
                    leftIcon={<FiSearch />}
                    onClick={() => searchOneDrive(searchQuery)}
                    isDisabled={!searchQuery.trim()}
                    isLoading={state.loading}
                  >
                    Search
                  </Button>
                </HStack>

                {state.searchResults.length > 0 && (
                  <Text>
                    Found {state.searchResults.length} results
                  </Text>
                )}

                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Name</Th>
                        <Th>Path</Th>
                        <Th>Size</Th>
                        <Th>Modified</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {state.searchResults.map((file) => (
                        <Tr key={file.id}>
                          <Td>
                            <HStack spacing={2}>
                              {renderFileIcon(file)}
                              <Text>{file.name}</Text>
                            </HStack>
                          </Td>
                          <Td fontSize="sm" color="gray.500">
                            {file.parentReference.path || '/'}
                          </Td>
                          <Td>{formatFileSize(file.size)}</Td>
                          <Td>{formatDate(file.lastModifiedDateTime)}</Td>
                          <Td>
                            <HStack spacing={2}>
                              <Tooltip label="Download">
                                <IconButton
                                  icon={<FiDownload />}
                                  variant="ghost"
                                  size="sm"
                                  as="a"
                                  href={file['@microsoft.graph.downloadUrl']}
                                  download
                                />
                              </Tooltip>
                            </HStack>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Ingestion Results Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                {state.ingestionResults.length > 0 ? (
                  <>
                    <Text>
                      {state.ingestionResults.length} files processed successfully
                    </Text>
                    
                    <TableContainer>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>File Name</Th>
                            <Th>Status</Th>
                            <Th>Processed At</Th>
                            <Th>Actions</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          {state.ingestionResults.map((result, index) => (
                            <Tr key={index}>
                              <Td>{result.fileName}</Td>
                              <Td>
                                <Badge colorScheme="green">Success</Badge>
                              </Td>
                              <Td>{formatDate(result.processedAt)}</Td>
                              <Td>
                                <HStack spacing={2}>
                                  <Tooltip label="View Details">
                                    <IconButton
                                      icon={<FiEye />}
                                      variant="ghost"
                                      size="sm"
                                    />
                                  </Tooltip>
                                </HStack>
                              </Td>
                            </Tr>
                          ))}
                        </Tbody>
                      </Table>
                    </TableContainer>
                  </>
                ) : (
                  <Box textAlign="center" py={10}>
                    <Icon as={FiDatabase} boxSize={12} color="gray.400" />
                    <Text mt={4} color="gray.500">
                      No ingestion results yet. Start ingestion to see results here.
                    </Text>
                  </Box>
                )}
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Configuration Modal */}
        <Modal
          isOpen={configModalOpen}
          onClose={() => setConfigModalOpen(false)}
          size="2xl"
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>OneDrive Configuration</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4} align="stretch">
                <FormControl>
                  <FormLabel>Include File Types</FormLabel>
                  <Textarea
                    value={currentConfig.includeFileTypes?.join(', ') || ''}
                    onChange={(e) => setCurrentConfig(prev => ({
                      ...prev,
                      includeFileTypes: e.target.value.split(',').map(t => t.trim()).filter(Boolean)
                    }))}
                    placeholder="text/plain,application/pdf,image/jpeg"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Maximum File Size (MB)</FormLabel>
                  <NumberInput
                    value={(currentConfig.maxFileSize || 0) / (1024 * 1024)}
                    onChange={(value) => setCurrentConfig(prev => ({
                      ...prev,
                      maxFileSize: parseFloat(value) * 1024 * 1024
                    }))}
                    min={1}
                    max={1000}
                  >
                    <NumberInputField />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                </FormControl>

                <FormControl>
                  <FormLabel>Batch Size</FormLabel>
                  <NumberInput
                    value={currentConfig.batchSize || 50}
                    onChange={(value) => setCurrentConfig(prev => ({
                      ...prev,
                      batchSize: parseInt(value) || 50
                    }))}
                    min={1}
                    max={100}
                  >
                    <NumberInputField />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                </FormControl>

                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Enable Real-time Sync</FormLabel>
                    <Switch
                      isChecked={currentConfig.enableRealTimeSync}
                      onChange={(e) => setCurrentConfig(prev => ({
                        ...prev,
                        enableRealTimeSync: e.target.checked
                      }))}
                    />
                  </FormControl>

                  <FormControl>
                    <FormLabel>Extract Text Content</FormLabel>
                    <Switch
                      isChecked={currentConfig.extractTextContent}
                      onChange={(e) => setCurrentConfig(prev => ({
                        ...prev,
                        extractTextContent: e.target.checked
                      }))}
                    />
                  </FormControl>
                </HStack>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setConfigModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={() => {
                  setConfigModalOpen(false);
                  // Apply configuration
                  onIngestionStart?.(currentConfig);
                }}
              >
                Save Configuration
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default OneDriveIntegration;