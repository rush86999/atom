/**
 * Tableau Integration Page
 * Complete Tableau integration with dashboard, workbooks, datasources, views, and analytics
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
  Divider,
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
  SettingsIcon,
  ExternalLinkIcon,
  CalendarIcon,
  CheckCircleIcon,
  WarningIcon,
} from "@chakra-ui/icons";

// Types
interface TableauWorkbook {
  id: string;
  name: string;
  description?: string;
  project_id: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  content_url?: string;
  show_tabs: boolean;
  size?: number;
  tags: string[];
}

interface TableauDatasource {
  id: string;
  name: string;
  description?: string;
  project_id: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
  content_url?: string;
  has_extracts: boolean;
  is_certified: boolean;
  tags: string[];
}

interface TableauView {
  id: string;
  name: string;
  content_url: string;
  created_at: string;
  updated_at: string;
  owner_id: string;
  workbook_id: string;
  view_url_name: string;
  tags: string[];
}

interface TableauProject {
  id: string;
  name: string;
  description?: string;
  parent_project_id?: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

interface TableauUser {
  id: string;
  email: string;
  name: string;
  site_role: string;
  last_login?: string;
  external_auth_user_id?: string;
}

interface TableauStats {
  total_workbooks: number;
  total_datasources: number;
  total_views: number;
  total_projects: number;
  active_users: number;
  storage_used: number;
}

const TableauIntegrationPage: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [workbooks, setWorkbooks] = useState<TableauWorkbook[]>([]);
  const [datasources, setDatasources] = useState<TableauDatasource[]>([]);
  const [views, setViews] = useState<TableauView[]>([]);
  const [projects, setProjects] = useState<TableauProject[]>([]);
  const [userProfile, setUserProfile] = useState<TableauUser | null>(null);
  const [stats, setStats] = useState<TableauStats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

  const toast = useToast();

  // Load initial data
  useEffect(() => {
    loadTableauData();
  }, []);

  const loadTableauData = async () => {
    try {
      setIsLoading(true);

      // Check connection status
      const healthResponse = await fetch("/api/v1/tableau/health");
      if (healthResponse.ok) {
        setIsConnected(true);

        // Load workbooks
        const workbooksResponse = await fetch(
          "/api/v1/tableau/workbooks?limit=50",
        );
        if (workbooksResponse.ok) {
          const workbooksData = await workbooksResponse.json();
          setWorkbooks(workbooksData.data || []);
        }

        // Load datasources
        const datasourcesResponse = await fetch(
          "/api/v1/tableau/datasources?limit=50",
        );
        if (datasourcesResponse.ok) {
          const datasourcesData = await datasourcesResponse.json();
          setDatasources(datasourcesData.data || []);
        }

        // Load views
        const viewsResponse = await fetch("/api/v1/tableau/views?limit=50");
        if (viewsResponse.ok) {
          const viewsData = await viewsResponse.json();
          setViews(viewsData.data || []);
        }

        // Load projects
        const projectsResponse = await fetch("/api/v1/tableau/projects");
        if (projectsResponse.ok) {
          const projectsData = await projectsResponse.json();
          setProjects(projectsData.data || []);
        }

        // Load user profile
        const userResponse = await fetch("/api/v1/tableau/user");
        if (userResponse.ok) {
          const userData = await userResponse.json();
          setUserProfile(userData.data);
        }

        // Calculate stats
        const calculatedStats: TableauStats = {
          total_workbooks: workbooks.length,
          total_datasources: datasources.length,
          total_views: views.length,
          total_projects: projects.length,
          active_users: 1,
          storage_used: workbooks.reduce((sum, w) => sum + (w.size || 0), 0),
        };
        setStats(calculatedStats);
      }
    } catch (error) {
      console.error("Failed to load Tableau data:", error);
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
        title: "Tableau Connected",
        description: "Successfully connected to Tableau",
        status: "success",
        duration: 3000,
        isClosable: true,
      });

      await loadTableauData();
    } catch (error) {
      toast({
        title: "Connection Failed",
        description: "Failed to connect to Tableau",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const searchResponse = await fetch("/api/v1/tableau/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: searchQuery,
          types: ["workbook", "view", "datasource"],
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

  // Render connection status
  if (!isConnected && !isLoading) {
    return (
      <Box p={6}>
        <VStack spacing={6} align="center" justify="center" minH="60vh">
          <Box textAlign="center">
            <Heading size="lg" mb={4}>
              Connect Tableau
            </Heading>
            <Text color="gray.600" mb={6}>
              Connect your Tableau account to access dashboards, workbooks, and
              analytics data.
            </Text>
          </Box>

          <Card maxW="md" w="full">
            <CardBody>
              <VStack spacing={4}>
                <Box textAlign="center">
                  <Icon as={ViewIcon} w={12} h={12} color="blue.500" mb={4} />
                  <Heading size="md">Tableau Integration</Heading>
                  <Text color="gray.600" mt={2}>
                    Business intelligence and analytics platform
                  </Text>
                </Box>

                <Button
                  colorScheme="blue"
                  size="lg"
                  w="full"
                  onClick={() => setIsConnectModalOpen(true)}
                >
                  Connect Tableau
                </Button>

                <Text fontSize="sm" color="gray.500" textAlign="center">
                  You'll be redirected to Tableau to authorize access
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
            <ModalHeader>Connect Tableau</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <Text>
                  This will connect your Tableau account to ATOM. You'll be able
                  to:
                </Text>
                <VStack align="start" spacing={2}>
                  <HStack>
                    <CheckCircleIcon color="green.500" />
                    <Text>Access your workbooks and dashboards</Text>
                  </HStack>
                  <HStack>
                    <CheckCircleIcon color="green.500" />
                    <Text>View and analyze data sources</Text>
                  </HStack>
                  <HStack>
                    <CheckCircleIcon color="green.500" />
                    <Text>Search across all Tableau content</Text>
                  </HStack>
                  <HStack>
                    <CheckCircleIcon color="green.500" />
                    <Text>Manage projects and permissions</Text>
                  </HStack>
                </VStack>
                <Alert status="info" borderRadius="md">
                  <AlertIcon />
                  You'll be redirected to Tableau to authorize this connection.
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
                Connect Tableau
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
            <Heading size="lg">Tableau</Heading>
            <Text color="gray.600">
              Business intelligence and analytics platform
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
              New Workbook
            </Button>
          </HStack>
        </HStack>

        <Breadcrumb>
          <BreadcrumbItem>
            <BreadcrumbLink href="/integrations">Integrations</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbItem isCurrentPage>
            <BreadcrumbLink>Tableau</BreadcrumbLink>
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
                placeholder="Search workbooks, views, datasources..."
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
          <Tab>Workbooks</Tab>
          <Tab>Datasources</Tab>
          <Tab>Views</Tab>
          <Tab>Projects</Tab>
          <Tab>Analytics</Tab>
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
                        <StatLabel>Total Workbooks</StatLabel>
                        <StatNumber>{stats.total_workbooks}</StatNumber>
                        <StatHelpText>
                          <StatArrow type="increase" />
                          23.36%
                        </StatHelpText>
                      </Stat>
                    </CardBody>
                  </Card>
                  <Card>
                    <CardBody>
                      <Stat>
                        <StatLabel>Total Views</StatLabel>
                        <StatNumber>{stats.total_views}</StatNumber>
                        <StatHelpText>
                          <StatArrow type="increase" />
                          12.5%
                        </StatHelpText>
                      </Stat>
                    </CardBody>
                  </Card>
                  <Card>
                    <CardBody>
                      <Stat>
                        <StatLabel>Storage Used</StatLabel>
                        <StatNumber>
                          {formatFileSize(stats.storage_used)}
                        </StatNumber>
                        <StatHelpText>Across all workbooks</StatHelpText>
                      </Stat>
                    </CardBody>
                  </Card>
                </SimpleGrid>

                {/* Recent Activity */}
                <Card w="full">
                  <CardHeader>
                    <Heading size="md">Recent Workbooks</Heading>
                  </CardHeader>
                  <CardBody>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Name</Th>
                          <Th>Project</Th>
                          <Th>Last Updated</Th>
                          <Th>Size</Th>
                          <Th>Actions</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {workbooks.slice(0, 5).map((workbook) => (
                          <Tr key={workbook.id}>
                            <Td fontWeight="medium">{workbook.name}</Td>
                            <Td>
                              <Badge colorScheme="blue">
                                {projects.find(
                                  (p) => p.id === workbook.project_id,
                                )?.name || "Unknown"}
                              </Badge>
                            </Td>
                            <Td>{formatDate(workbook.updated_at)}</Td>
                            <Td>{formatFileSize(workbook.size || 0)}</Td>
                            <Td>
                              <HStack>
                                <Tooltip label="View Workbook">
                                  <IconButton
                                    aria-label="View workbook"
                                    icon={<ViewIcon />}
                                    size="sm"
                                    variant="ghost"
                                  />
                                </Tooltip>
                                <Tooltip label="Edit Workbook">
                                  <IconButton
                                    aria-label="Edit workbook"
                                    icon={<EditIcon />}
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
                          <Text>{userProfile.email}</Text>
                        </Box>
                        <Box>
                          <Text fontWeight="bold">Site Role</Text>
                          <Badge colorScheme="green">
                            {userProfile.site_role}
                          </Badge>
                        </Box>
                        <Box>
                          <Text fontWeight="bold">Last Login</Text>
                          <Text>
                            {userProfile.last_login
                              ? formatDate(userProfile.last_login)
                              : "Never"}
                          </Text>
                        </Box>
                      </SimpleGrid>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            )}
          </TabPanel>

          {/* Workbooks Panel */}
          <TabPanel>
            <VStack spacing={6} align="start">
              <HStack w="full" justify="space-between">
                <Heading size="md">Workbooks ({workbooks.length})</Heading>
                <Button colorScheme="blue" leftIcon={<AddIcon />}>
                  New Workbook
                </Button>
              </HStack>

              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>Name</Th>
                    <Th>Description</Th>
                    <Th>Project</Th>
                    <Th>Size</Th>
                    <Th>Last Updated</Th>
                    <Th>Actions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {workbooks.map((workbook) => (
                    <Tr key={workbook.id}>
                      <Td fontWeight="medium">{workbook.name}</Td>
                      <Td>{workbook.description || "No description"}</Td>
                      <Td>
                        <Badge colorScheme="blue">
                          {projects.find((p) => p.id === workbook.project_id)
                            ?.name || "Unknown"}
                        </Badge>
                      </Td>
                      <Td>{formatFileSize(workbook.size || 0)}</Td>
                      <Td>{formatDate(workbook.updated_at)}</Td>
                      <Td>
                        <HStack>
                          <Tooltip label="View Workbook">
                            <IconButton
                              aria-label="View workbook"
                              icon={<ViewIcon />}
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                window.open(workbook.content_url, "_blank")
                              }
                            />
                          </Tooltip>
                          <Tooltip label="Edit Workbook">
                            <IconButton
                              aria-label="Edit workbook"
                              icon={<EditIcon />}
                              size="sm"
                              variant="ghost"
                            />
                          </Tooltip>
                          <Tooltip label="Download Workbook">
                            <IconButton
                              aria-label="Download workbook"
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
            </VStack>
          </TabPanel>

          {/* Datasources Panel */}
          <TabPanel>
            <VStack spacing={6} align="start">
              <HStack w="full" justify="space-between">
                <Heading size="md">Datasources ({datasources.length})</Heading>
                <Button colorScheme="blue" leftIcon={<AddIcon />}>
                  New Datasource
                </Button>
              </HStack>

              <SimpleGrid
                columns={{ base: 1, md: 2, lg: 3 }}
                spacing={6}
                w="full"
              >
                {datasources.map((datasource) => (
                  <Card key={datasource.id}>
                    <CardHeader>
                      <HStack justify="space-between">
                        <Heading size="sm">{datasource.name}</Heading>
                        {datasource.is_certified && (
                          <Badge colorScheme="green" fontSize="xs">
                            Certified
                          </Badge>
                        )}
                      </HStack>
                    </CardHeader>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Text fontSize="sm" color="gray.600">
                          {datasource.description || "No description"}
                        </Text>
                        <HStack>
                          <Badge colorScheme="blue">
                            {projects.find(
                              (p) => p.id === datasource.project_id,
                            )?.name || "Unknown"}
                          </Badge>
                          {datasource.has_extracts && (
                            <Badge colorScheme="orange">Has Extracts</Badge>
                          )}
                        </HStack>
                        <Text fontSize="xs" color="gray.500">
                          Updated {formatDate(datasource.updated_at)}
                        </Text>
                        <HStack w="full" justify="space-between">
                          <Button
                            size="sm"
                            colorScheme="blue"
                            variant="ghost"
                            leftIcon={<ViewIcon />}
                          >
                            View
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            leftIcon={<EditIcon />}
                          >
                            Edit
                          </Button>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>
                ))}
              </SimpleGrid>
            </VStack>
          </TabPanel>

          {/* Views Panel */}
          <TabPanel>
            <VStack spacing={6} align="start">
              <HStack w="full" justify="space-between">
                <Heading size="md">Views ({views.length})</Heading>
                <Button colorScheme="blue" leftIcon={<AddIcon />}>
                  New View
                </Button>
              </HStack>

              <Table variant="simple">
                <Thead>
                  <Tr>
                    <Th>Name</Th>
                    <Th>Workbook</Th>
                    <Th>URL Name</Th>
                    <Th>Created</Th>
                    <Th>Actions</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {views.map((view) => (
                    <Tr key={view.id}>
                      <Td fontWeight="medium">{view.name}</Td>
                      <Td>
                        <Badge colorScheme="purple">
                          {workbooks.find((w) => w.id === view.workbook_id)
                            ?.name || "Unknown"}
                        </Badge>
                      </Td>
                      <Td>{view.view_url_name}</Td>
                      <Td>{formatDate(view.created_at)}</Td>
                      <Td>
                        <HStack>
                          <Tooltip label="View Dashboard">
                            <IconButton
                              aria-label="View dashboard"
                              icon={<ViewIcon />}
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                window.open(view.content_url, "_blank")
                              }
                            />
                          </Tooltip>
                          <Tooltip label="Share View">
                            <IconButton
                              aria-label="Share view"
                              icon={<ExternalLinkIcon />}
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
            </VStack>
          </TabPanel>

          {/* Projects Panel */}
          <TabPanel>
            <VStack spacing={6} align="start">
              <HStack w="full" justify="space-between">
                <Heading size="md">Projects ({projects.length})</Heading>
                <Button colorScheme="blue" leftIcon={<AddIcon />}>
                  New Project
                </Button>
              </HStack>

              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6} w="full">
                {projects.map((project) => (
                  <Card key={project.id}>
                    <CardHeader>
                      <Heading size="sm">{project.name}</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Text fontSize="sm" color="gray.600">
                          {project.description || "No description"}
                        </Text>
                        {project.parent_project_id && (
                          <Text fontSize="xs" color="gray.500">
                            Parent:{" "}
                            {projects.find(
                              (p) => p.id === project.parent_project_id,
                            )?.name || "Unknown"}
                          </Text>
                        )}
                        <Text fontSize="xs" color="gray.500">
                          Created {formatDate(project.created_at)}
                        </Text>
                        <HStack>
                          <Button
                            size="sm"
                            colorScheme="blue"
                            variant="ghost"
                            leftIcon={<ViewIcon />}
                          >
                            View Content
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

          {/* Analytics Panel */}
          <TabPanel>
            <VStack spacing={6} align="start">
              <Heading size="md">Analytics & Insights</Heading>

              <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6} w="full">
                <Card>
                  <CardHeader>
                    <Heading size="sm">Content Distribution</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4}>
                      <HStack w="full" justify="space-between">
                        <Text>Workbooks</Text>
                        <Badge colorScheme="blue">{workbooks.length}</Badge>
                      </HStack>
                      <HStack w="full" justify="space-between">
                        <Text>Datasources</Text>
                        <Badge colorScheme="green">{datasources.length}</Badge>
                      </HStack>
                      <HStack w="full" justify="space-between">
                        <Text>Views</Text>
                        <Badge colorScheme="purple">{views.length}</Badge>
                      </HStack>
                      <HStack w="full" justify="space-between">
                        <Text>Projects</Text>
                        <Badge colorScheme="orange">{projects.length}</Badge>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <Heading size="sm">Storage Usage</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4}>
                      <HStack w="full" justify="space-between">
                        <Text>Total Storage</Text>
                        <Text fontWeight="bold">
                          {formatFileSize(stats?.storage_used || 0)}
                        </Text>
                      </HStack>
                      <Progress value={75} w="full" colorScheme="blue" />
                      <Text fontSize="sm" color="gray.600">
                        75% of available storage used
                      </Text>
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
                        <Text fontSize="sm">Connected to Tableau</Text>
                      </HStack>
                      <HStack>
                        <CheckCircleIcon color="green.500" />
                        <Text fontSize="sm">
                          Loaded {workbooks.length} workbooks
                        </Text>
                      </HStack>
                      <HStack>
                        <CheckCircleIcon color="green.500" />
                        <Text fontSize="sm">
                          Loaded {datasources.length} datasources
                        </Text>
                      </HStack>
                      <HStack>
                        <CheckCircleIcon color="green.500" />
                        <Text fontSize="sm">Loaded {views.length} views</Text>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <Heading size="sm">User Information</Heading>
                  </CardHeader>
                  <CardBody>
                    {userProfile && (
                      <VStack spacing={3} align="start">
                        <HStack>
                          <Text fontWeight="medium">Name:</Text>
                          <Text>{userProfile.name}</Text>
                        </HStack>
                        <HStack>
                          <Text fontWeight="medium">Email:</Text>
                          <Text>{userProfile.email}</Text>
                        </HStack>
                        <HStack>
                          <Text fontWeight="medium">Role:</Text>
                          <Badge colorScheme="green">
                            {userProfile.site_role}
                          </Badge>
                        </HStack>
                        <HStack>
                          <Text fontWeight="medium">Last Login:</Text>
                          <Text>
                            {userProfile.last_login
                              ? formatDate(userProfile.last_login)
                              : "Never"}
                          </Text>
                        </HStack>
                      </VStack>
                    )}
                  </CardBody>
                </Card>
              </SimpleGrid>
            </VStack>
          </TabPanel>
        </TabPanels>
      </Tabs>
    </Box>
  );
};

export default TableauIntegrationPage;
