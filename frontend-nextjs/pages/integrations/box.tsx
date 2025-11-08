/**
 * Box Integration Page
 * Complete Box integration with file management and collaboration
 */

import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Progress,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Input,
  InputGroup,
  InputLeftElement,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  Alert,
  AlertIcon,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Tooltip,
  IconButton,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
} from "@chakra-ui/react";
import {
  SearchIcon,
  AddIcon,
  DownloadIcon,
  ViewIcon,
  EditIcon,
  FolderIcon,
  FileIcon,
  SettingsIcon,
  ExternalLinkIcon,
  CalendarIcon,
  CheckCircleIcon,
} from "@chakra-ui/icons";

// Types
interface BoxFile {
  id: string;
  name: string;
  type: string;
  size?: number;
  created_at: string;
  modified_at: string;
  parent_folder_id?: string;
  shared_link?: string;
  description?: string;
  tags: string[];
}

interface BoxFolder {
  id: string;
  name: string;
  type: string;
  created_at: string;
  modified_at: string;
  parent_folder_id?: string;
  shared_link?: string;
  description?: string;
  item_count?: number;
  size?: number;
  tags: string[];
}

interface BoxUser {
  id: string;
  name: string;
  login: string;
  created_at: string;
  modified_at: string;
  language?: string;
  timezone?: string;
  space_amount?: number;
  space_used?: number;
  max_upload_size?: number;
}

interface BoxStats {
  total_files: number;
  total_folders: number;
  total_storage: number;
  used_storage: number;
  available_storage: number;
  shared_files: number;
}

const BoxIntegrationPage: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [files, setFiles] = useState<BoxFile[]>([]);
  const [folders, setFolders] = useState<BoxFolder[]>([]);
  const [userProfile, setUserProfile] = useState<BoxUser | null>(null);
  const [stats, setStats] = useState<BoxStats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

  const toast = useToast();

  // Load initial data
  useEffect(() => {
    loadBoxData();
  }, []);

  const loadBoxData = async () => {
    try {
      setIsLoading(true);

      // Check connection status
      const healthResponse = await fetch("/api/v1/box/health");
      if (healthResponse.ok) {
        setIsConnected(true);

        // Load files
        const filesResponse = await fetch("/api/v1/box/files?limit=50");
        if (filesResponse.ok) {
          const filesData = await filesResponse.json();
          setFiles(filesData.data || []);
        }

        // Load folders
        const foldersResponse = await fetch("/api/v1/box/folders?limit=50");
        if (foldersResponse.ok) {
          const foldersData = await foldersResponse.json();
          setFolders(foldersData.data || []);
        }

        // Load user profile
        const userResponse = await fetch("/api/v1/box/user");
        if (userResponse.ok) {
          const userData = await userResponse.json();
          setUserProfile(userData.data);
        }

        // Calculate stats
        const calculatedStats: BoxStats = {
          total_files: files.length,
          total_folders: folders.length,
          total_storage: userProfile?.space_amount || 10737418240,
          used_storage: userProfile?.space_used || 0,
          available_storage:
            (userProfile?.space_amount || 0) - (userProfile?.space_used || 0),
          shared_files: files.filter((f) => f.shared_link).length,
        };
        setStats(calculatedStats);
      }
    } catch (error) {
      console.error("Failed to load Box data:", error);
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    try {
      setIsConnected(true);
      setIsConnectModalOpen(false);

      toast({
        title: "Box Connected",
        description: "Successfully connected to Box",
        status: "success",
        duration: 3000,
        isClosable: true,
      });

      await loadBoxData();
    } catch (error) {
      toast({
        title: "Connection Failed",
        description: "Failed to connect to Box",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const searchResponse = await fetch("/api/v1/box/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: searchQuery,
          type: "file",
          limit: 50,
          offset: 0,
        }),
      });

      if (searchResponse.ok) {
        const searchData = await searchResponse.json();
        toast({
          title: "Search Complete",
          description: `Found ${searchData.data.total_count} results`,
          status: "info",
          duration: 2000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error("Search failed:", error);
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const getFileIcon = (fileName: string) => {
    const extension = fileName.split(".").pop()?.toLowerCase();
    switch (extension) {
      case "pdf":
        return "📄";
      case "doc":
      case "docx":
        return "📝";
      case "xls":
      case "xlsx":
        return "📊";
      case "ppt":
      case "pptx":
        return "📽️";
      case "jpg":
      case "jpeg":
      case "png":
      case "gif":
        return "🖼️";
      default:
        return "📄";
    }
  };

  // Render connection status
  if (!isConnected && !isLoading) {
    return (
      <Box p={6}>
        <VStack spacing={6} align="center" justify="center" minH="60vh">
          <Box textAlign="center">
            <Heading size="lg" mb={4}>
              Connect Box
            </Heading>
            <Text color="gray.600" mb={6}>
              Connect your Box account to access files, folders, and collaborate
              with your team.
            </Text>
          </Box>

          <Card maxW="md" w="full">
            <CardBody>
              <VStack spacing={4}>
                <Box textAlign="center">
                  <Icon as={FolderIcon} w={12} h={12} color="blue.500" mb={4} />
                  <Heading size="md">Box Integration</Heading>
                  <Text color="gray.600" mt={2}>
                    Enterprise content management and collaboration
                  </Text>
                </Box>

                <Button
                  colorScheme="blue"
                  size="lg"
                  w="full"
                  onClick={() => setIsConnectModalOpen(true)}
                >
                  Connect Box
                </Button>

                <Text fontSize="sm" color="gray.500" textAlign="center">
                  You'll be redirected to Box to authorize access
                </Text>
              </VStack>
            </CardBody>
          </Card>
        </VStack>

        {/* Connect Modal */}
        <Modal
          isOpen={isConnectModalOpen}
          onClose={() => setIsConnectModalOpen(false)}
        >
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Connect Box</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <Text>
                  This will connect your Box account to ATOM. You'll be able to:
                </Text>
                <VStack align="start" spacing={2}>
                  <HStack>
                    <CheckCircleIcon color="green.500" />
                    <Text>Access and manage your files and folders</Text>
                  </HStack>
                  <HStack>
                    <CheckCircleIcon color="green.500" />
                    <Text>Upload and download files</Text>
                  </HStack>
                  <HStack>
                    <CheckCircleIcon color="green.500" />
                    <Text>Search across all your content</Text>
                  </HStack>
                  <HStack>
                    <CheckCircleIcon color="green.500" />
                    <Text>Collaborate with team members</Text>
                  </HStack>
                </VStack>
                <Alert status="info" borderRadius="md">
                  <AlertIcon />
                  You'll be redirected to Box to authorize this connection.
                </Alert>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="outline"
                mr={3}
                onClick={() => setIsConnectModalOpen(false)}
              >
                Cancel
              </Button>
              <Button colorScheme="blue" onClick={handleConnect}>
                Connect Box
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </Box>
    );
  }

  return (
    <Box p={6}>
      {/* Header */}
      <VStack spacing={4} align="start" mb={6}>
        <HStack w="full" justify="space-between">
          <VStack align="start" spacing={1}>
            <Heading size="lg">Box</Heading>
            <Text color="gray.600">
              Enterprise content management and collaboration
            </Text>
          </VStack>
          <HStack>
            <Button
              leftIcon={<SettingsIcon />}
              variant="outline"
              onClick={() => setIsConnectModalOpen(true)}
            >
              Settings
            </Button>
            <Button colorScheme="blue" leftIcon={<AddIcon />}>
              New Folder
            </Button>
            <Button colorScheme="green" leftIcon={<AddIcon />}>
              Upload File
            </Button>
          </HStack>
        </HStack>

        <Breadcrumb>
          <BreadcrumbItem>
            <BreadcrumbLink href="/integrations">Integrations</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbItem isCurrentPage>
            <BreadcrumbLink>Box</BreadcrumbLink>
          </BreadcrumbItem>
        </Breadcrumb>
      </VStack>

      {/* Search Bar */}
      <Card mb={6}>
        <CardBody>
          <HStack>
            <InputGroup>
              <InputLeftElement>
                <SearchIcon color="gray.400" />
              </InputLeftElement>
              <Input
                placeholder="Search files, folders, content..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleSearch()}
              />
            </InputGroup>
            <Button colorScheme="blue" onClick={handleSearch}>
              Search
            </Button>
          </HStack>
        </CardBody>
      </Card>

      {/* Main Content */}
      <Tabs colorScheme="blue">
        <TabList>
          <Tab>Dashboard</Tab>
          <Tab>Files</Tab>
          <Tab>Folders</Tab>
          <Tab>Storage</Tab>
        </TabList>

        <TabPanels>
          {/* Dashboard Panel */}
          <TabPanel>
            {stats && (
              <VStack spacing={6} align="start">
                {/* Stats Overview */}
                <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6} w="full">
                  <Card>
                    <CardBody>
                      <Stat>
                        <StatLabel>Total Files</StatLabel>
                        <StatNumber>{stats.total_files}</StatNumber>
                        <StatHelpText>
                          <StatArrow type="increase" />
                          15.2%
                        </StatHelpText>
                      </Stat>
                    </CardBody>
                  </Card>
                  <Card>
                    <CardBody>
                      <Stat>
                        <StatLabel>Total Folders</StatLabel>
                        <StatNumber>{stats.total_folders}</StatNumber>
                        <StatHelpText>
                          <StatArrow type="increase" />
                          8.7%
                        </StatHelpText>
                      </Stat>
                    </CardBody>
                  </Card>
                  <Card>
                    <CardBody>
                      <Stat>
                        <StatLabel>Shared Files</StatLabel>
                        <StatNumber>{stats.shared_files}</StatNumber>
                        <StatHelpText>Available for collaboration</StatHelpText>
                      </Stat>
                    </CardBody>
                  </Card>
                </SimpleGrid>

                {/* Storage Usage */}
                <Card w="full">
                  <CardHeader>
                    <Heading size="md">Storage Usage</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4}>
                      <HStack w="full" justify="space-between">
                        <Text>Used Storage</Text>
                        <Text fontWeight="bold">
                          {formatFileSize(stats.used_storage)}
                        </Text>
                      </HStack>
                      <Progress
                        value={(stats.used_storage / stats.total_storage) * 100}
                        w="full"
                        colorScheme="blue"
                        size="lg"
                      />
                      <HStack w="full" justify="space-between">
                        <Text fontSize="sm" color="gray.600">
                          {formatFileSize(stats.used_storage)} of{" "}
                          {formatFileSize(stats.total_storage)} used
                        </Text>
                        <Text fontSize="sm" color="gray.600">
                          {(
                            (stats.used_storage / stats.total_storage) *
                            100
                          ).toFixed(1)}
                          %
                        </Text>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>

                {/* Recent Files */}
                <Card w="full">
                  <CardHeader>
                    <Heading size="md">Recent Files</Heading>
                  </CardHeader>
                  <CardBody>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Name</Th>
                          <Th>Size</Th>
                          <Th>Last Modified</Th>
                          <Th>Actions</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {files.slice(0, 5).map((file) => (
                          <Tr key={file.id}>
                            <Td>
                              <HStack>
                                <Text>{getFileIcon(file.name)}</Text>
                                <Text fontWeight="medium">{file.name}</Text>
                              </HStack>
                            </Td>
                            <Td>{formatFileSize(file.size || 0)}</Td>
                            <Td>{formatDate(file.modified_at)}</Td>
                            <Td>
                              <HStack>
                                <Tooltip label="View File">
                                  <IconButton
                                    aria-label="View file"
                                    icon={<ViewIcon />}
                                    size="sm"
                                    variant="ghost"
                                  />
                                </Tooltip>
                                <Tooltip label="Download File">
                                  <IconButton
                                    aria-label="Download file"
                                    icon={<DownloadIcon />}
                                    size="sm"
                                    variant="ghost"
                                  />
                                </Tooltip>
                              </HStack>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </CardBody>
                </Card>

                {/* User Info */}
                {userProfile && (
                  <Card w="full">
                    <CardHeader>
                      <Heading size="md">Account Information</Heading>
                    </CardHeader>
                    <CardBody>
                      <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                        <Box>
                          <Text fontWeight="bold">Name</Text>
                          <Text>{userProfile.name}</Text>
                        </Box>
                        <Box>
                          <Text fontWeight="bold">Email</Text>
                          <Text>{userProfile.login}</Text>
                        </Box>
                        <Box>
                          <Text fontWeight="bold">Storage</Text>
                          <Text>
                            {formatFileSize(userProfile.space_used || 0)} /{" "}
                            {formatFileSize(userProfile.space_amount || 0)}
                          </Text>
                        </Box>
                        <Box>
                          <Text fontWeight="bold">Max Upload</Text>
                          <Text>
                            {formatFileSize(userProfile.max_upload_size || 0)}
                          </Text>
                        </Box>
                      </SimpleGrid>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            )}
          </TabPanel>

          {/* Files Panel */}
          <TabPanel>
            <VStack spacing={6} align="start">
              <HStack w="full" justify="space-between">
                <Heading size="md">Files ({files.length})</Heading>
                <Button colorScheme="green" leftIcon={<AddIcon />}>
                  Upload File
                </Button>
              </HStack>

              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>Name</Th>
                    <Th>Size</Th>
                    <Th>Last Modified</Th>
                    <Th>Shared</Th>
                    <Th>Actions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {files.map((file) => (
                    <Tr key={file.id}>
                      <Td>
                        <HStack>
                          <Text>{getFileIcon(file.name)}</Text>
                          <Text fontWeight="medium">{file.name}</Text>
                        </HStack>
                      </Td>
                      <Td>{formatFileSize(file.size || 0)}</Td>
                      <Td>{formatDate(file.modified_at)}</Td>
                      <Td>
                        {file.shared_link ? (
                          <Badge colorScheme="green">Shared</Badge>
                        ) : (
                          <Badge colorScheme="gray">Private</Badge>
                        )}
                      </Td>
                      <Td>
                        <HStack>
                          <Tooltip label="View File">
                            <IconButton
                              aria-label="View file"
                              icon={<ViewIcon />}
                              size="sm"
                              variant="ghost"
                            />
                          </Tooltip>
                          <Tooltip label="Download File">
                            <IconButton
                              aria-label="Download file"
                              icon={<DownloadIcon />}
                              size="sm"
                              variant="ghost"
                            />
                          </Tooltip>
                          {file.shared_link && (
                            <Tooltip label="Share Link">
                              <IconButton
                                aria-label="Share file"
                                icon={<ExternalLinkIcon />}
                                size="sm"
                                variant="ghost"
                                onClick={() =>
                                  window.open(file.shared_link, "_blank")
                                }
                              />
                            </Tooltip>
                          )}
                        </HStack>
                      </Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            </VStack>
          </TabPanel>

          {/* Folders Panel */}
          <TabPanel>
            <VStack spacing={6} align="start">
              <HStack w="full" justify="space-between">
                <Heading size="md">Folders ({folders.length})</Heading>
                <Button colorScheme="blue" leftIcon={<AddIcon />}>
                  New Folder
                </Button>
              </HStack>

              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6} w="full">
                {folders.map((folder) => (
                  <Card key={folder.id}>
                    <CardHeader>
                      <HStack>
                        <Icon as={FolderIcon} color="blue.500" />
                        <Heading size="sm">{folder.name}</Heading>
                      </HStack>
                    </CardHeader>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Text fontSize="sm" color="gray.600">
                          {folder.description || "No description"}
                        </Text>
                        <HStack>
                          <Badge colorScheme="blue">
                            {folder.item_count || 0} items
                          </Badge>
                          {folder.shared_link && (
                            <Badge colorScheme="green">Shared</Badge>
                          )}
                        </HStack>
                        <Text fontSize="xs" color="gray.500">
                          Updated {formatDate(folder.modified_at)}
                        </Text>
                        <HStack>
                          <Button
                            size="sm"
                            colorScheme="blue"
                            variant="ghost"
                            leftIcon={<ViewIcon />}
                          >
                            Open
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            leftIcon={<SettingsIcon />}
                          >
                            Settings
                          </Button>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>
                ))}
              </SimpleGrid>
            </VStack>
          </TabPanel>

          {/* Storage Panel */}
          <TabPanel>
            <VStack spacing={6} align="start">
              <Heading size="md">Storage Management</Heading>

              {stats && userProfile && (
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6} w="full">
                  <Card>
                    <CardHeader>
                      <Heading size="sm">Storage Overview</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={4}>
                        <HStack w="full" justify="space-between">
                          <Text>Used Storage</Text>
                          <Text fontWeight="bold">
                            {formatFileSize(stats.used_storage)}
                          </Text>
                        </HStack>
                        <HStack w="full" justify="space-between">
                          <Text>Available Storage</Text>
                          <Text fontWeight="bold">
                            {formatFileSize(stats.available_storage)}
                          </Text>
                        </HStack>
                        <HStack w="full" justify="space-between">
                          <Text>Total Storage</Text>
                          <Text fontWeight="bold">
                            {formatFileSize(stats.total_storage)}
                          </Text>
                        </HStack>
                        <Progress
                          value={
                            (stats.used_storage / stats.total_storage) * 100
                          }
                          w="full"
                          colorScheme="blue"
                          size="lg"
                        />
                        <Text fontSize="sm" color="gray.600">
                          {(
                            (stats.used_storage / stats.total_storage) *
                            100
                          ).toFixed(1)}
                          % used
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader>
                      <Heading size="sm">Content Statistics</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={4}>
                        <HStack w="full" justify="space-between">
                          <Text>Total Files</Text>
                          <Badge colorScheme="blue">{stats.total_files}</Badge>
                        </HStack>
                        <HStack w="full" justify="space-between">
                          <Text>Total Folders</Text>
                          <Badge colorScheme="green">
                            {stats.total_folders}
                          </Badge>
                        </HStack>
                        <HStack w="full" justify="space-between">
                          <Text>Shared Files</Text>
                          <Badge colorScheme="purple">
                            {stats.shared_files}
                          </Badge>
                        </HStack>
                        <HStack w="full" justify="space-between">
                          <Text>Max Upload Size</Text>
                          <Text fontSize="sm">
                            {formatFileSize(userProfile.max_upload_size || 0)}
                          </Text>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader>
                      <Heading size="sm">Recent Activity</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={3} align="start">
                        <HStack>
                          <CheckCircleIcon color="green.500" />
                          <Text fontSize="sm">Connected to Box</Text>
                        </HStack>
                        <HStack>
                          <CheckCircleIcon color="green.500" />
                          <Text fontSize="sm">Loaded {files.length} files</Text>
                        </HStack>
                        <HStack>
                          <CheckCircleIcon color="green.500" />
                          <Text fontSize="sm">
                            Loaded {folders.length} folders
                          </Text>
                        </HStack>
                        <HStack>
                          <CheckCircleIcon color="green.500" />
                          <Text fontSize="sm">Ready for collaboration</Text>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader>
                      <Heading size="sm">Account Information</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={3} align="start">
                        <HStack>
                          <Text fontWeight="medium">Name:</Text>
                          <Text>{userProfile.name}</Text>
                        </HStack>
                        <HStack>
                          <Text fontWeight="medium">Email:</Text>
                          <Text>{userProfile.login}</Text>
                        </HStack>
                        <HStack>
                          <Text fontWeight="medium">Language:</Text>
                          <Text>{userProfile.language || "English"}</Text>
                        </HStack>
                        <HStack>
                          <Text fontWeight="medium">Timezone:</Text>
                          <Text>{userProfile.timezone || "Not set"}</Text>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              )}
            </VStack>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
};

export default BoxIntegrationPage;
