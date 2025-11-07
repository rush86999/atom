import React, { useState, useEffect } from "react";
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Grid,
  GridItem,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Button,
  IconButton,
  Badge,
  Spinner,
  useToast,
  Progress,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Code,
  Divider,
  Flex,
  Tooltip,
  Switch,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Select,
} from "@chakra-ui/react";
import {
  CheckIcon,
  CloseIcon,
  SettingsIcon,
  CalendarIcon,
  ChatIcon,
  EmailIcon,
  AttachmentIcon,
  DownloadIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  AddIcon,
  RepeatIcon,
  ExternalLinkIcon,
  LockIcon,
  UnlockIcon,
  WarningIcon,
  InfoIcon,
} from "@chakra-ui/icons";

interface ServiceConnection {
  id: string;
  name: string;
  type: string;
  status: "connected" | "disconnected" | "error" | "pending";
  last_sync?: string;
  sync_status?: "syncing" | "success" | "failed";
  error_message?: string;
  config?: Record<string, any>;
  capabilities: string[];
  icon: string;
  description: string;
}

interface ServiceStats {
  total_services: number;
  connected_services: number;
  sync_success_rate: number;
  last_sync_overall: string;
  active_workflows: number;
}

interface SyncStatus {
  service_id: string;
  status: "syncing" | "success" | "failed";
  progress?: number;
  items_processed?: number;
  total_items?: number;
  last_sync?: string;
  error_message?: string;
}

const ServiceIntegrationDashboard: React.FC = () => {
  const [services, setServices] = useState<ServiceConnection[]>([]);
  const [stats, setStats] = useState<ServiceStats | null>(null);
  const [syncStatus, setSyncStatus] = useState<Record<string, SyncStatus>>({});
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [selectedService, setSelectedService] =
    useState<ServiceConnection | null>(null);
  const [activeTab, setActiveTab] = useState(0);

  const {
    isOpen: isServiceModalOpen,
    onOpen: onServiceModalOpen,
    onClose: onServiceModalClose,
  } = useDisclosure();
  const {
    isOpen: isConfigModalOpen,
    onOpen: onConfigModalOpen,
    onClose: onConfigModalClose,
  } = useDisclosure();

  const toast = useToast();

  // Sample service data - in production, this would come from API
  const sampleServices: ServiceConnection[] = [
    {
      id: "google_calendar",
      name: "Google Calendar",
      type: "calendar",
      status: "connected",
      last_sync: "2024-01-15T10:30:00Z",
      sync_status: "success",
      capabilities: [
        "read_events",
        "create_events",
        "update_events",
        "delete_events",
      ],
      icon: "calendar",
      description: "Manage your calendar events and schedules",
    },
    {
      id: "gmail",
      name: "Gmail",
      type: "email",
      status: "connected",
      last_sync: "2024-01-15T10:25:00Z",
      sync_status: "success",
      capabilities: [
        "read_emails",
        "send_emails",
        "manage_labels",
        "search_emails",
      ],
      icon: "email",
      description: "Send and receive emails with AI assistance",
    },
    {
      id: "asana",
      name: "Asana",
      type: "tasks",
      status: "connected",
      last_sync: "2024-01-15T09:45:00Z",
      sync_status: "success",
      capabilities: [
        "read_tasks",
        "create_tasks",
        "update_tasks",
        "manage_projects",
      ],
      icon: "tasks",
      description: "Project and task management platform",
    },
    {
      id: "trello",
      name: "Trello",
      type: "tasks",
      status: "connected",
      last_sync: "2024-01-15T08:15:00Z",
      sync_status: "syncing",
      capabilities: [
        "read_cards",
        "create_cards",
        "update_cards",
        "manage_boards",
      ],
      icon: "tasks",
      description: "Visual project management with boards and cards",
    },
    {
      id: "notion",
      name: "Notion",
      type: "documents",
      status: "connected",
      last_sync: "2024-01-14T16:20:00Z",
      sync_status: "success",
      capabilities: [
        "read_pages",
        "create_pages",
        "update_pages",
        "manage_databases",
      ],
      icon: "document",
      description: "All-in-one workspace for notes and documents",
    },
    {
      id: "dropbox",
      name: "Dropbox",
      type: "storage",
      status: "connected",
      last_sync: "2024-01-15T07:30:00Z",
      sync_status: "success",
      capabilities: [
        "read_files",
        "upload_files",
        "share_files",
        "manage_folders",
      ],
      icon: "storage",
      description: "Cloud storage and file sharing",
    },
    {
      id: "slack",
      name: "Slack",
      type: "messages",
      status: "disconnected",
      last_sync: "2024-01-10T14:20:00Z",
      sync_status: "failed",
      error_message: "Authentication token expired",
      capabilities: [
        "read_messages",
        "send_messages",
        "manage_channels",
        "search_messages",
      ],
      icon: "chat",
      description: "Team communication and collaboration",
    },
    {
      id: "github",
      name: "GitHub",
      type: "development",
      status: "pending",
      capabilities: [
        "read_repos",
        "manage_issues",
        "review_pull_requests",
        "manage_projects",
      ],
      icon: "code",
      description: "Code repository and project management",
    },
    {
      id: "zoom",
      name: "Zoom",
      type: "video_conferencing",
      status: "pending",
      capabilities: [
        "create_meetings",
        "manage_meetings",
        "view_recordings",
        "manage_users",
        "webhook_notifications",
      ],
      icon: "video",
      description: "Video conferencing and meeting management",
    },
    {
      id: "salesforce",
      name: "Salesforce",
      type: "crm",
      status: "pending",
      capabilities: [
        "manage_accounts",
        "manage_contacts",
        "manage_opportunities",
        "manage_leads",
        "sales_analytics",
        "search_data",
      ],
      icon: "crm",
      description: "Customer relationship management and sales automation",
    },
  ];

  useEffect(() => {
    fetchServiceData();
    // Set up periodic sync status updates
    const interval = setInterval(fetchSyncStatus, 30000); // Every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchServiceData = async () => {
    try {
      setLoading(true);
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1000));

      setServices(sampleServices);
      setStats({
        total_services: sampleServices.length,
        connected_services: sampleServices.filter(
          (s) => s.status === "connected",
        ).length,
        sync_success_rate: 85,
        last_sync_overall: "2024-01-15T10:30:00Z",
        active_workflows: 12,
      });

      // Initialize sync status
      const initialSyncStatus: Record<string, SyncStatus> = {};
      sampleServices.forEach((service) => {
        if (service.sync_status) {
          initialSyncStatus[service.id] = {
            service_id: service.id,
            status: service.sync_status,
            progress: service.sync_status === "syncing" ? 45 : 100,
            items_processed: service.sync_status === "syncing" ? 234 : 0,
            total_items: service.sync_status === "syncing" ? 520 : 0,
            last_sync: service.last_sync,
            error_message: service.error_message,
          };
        }
      });
      setSyncStatus(initialSyncStatus);
    } catch (error) {
      console.error("Error fetching service data:", error);
      toast({
        title: "Error",
        description: "Failed to load service integration data",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchSyncStatus = async () => {
    try {
      // Simulate API call for sync status
      const updatedSyncStatus = { ...syncStatus };

      // Update syncing services
      Object.keys(updatedSyncStatus).forEach((serviceId) => {
        const status = updatedSyncStatus[serviceId];
        if (status.status === "syncing") {
          // Simulate progress
          const newProgress = Math.min((status.progress || 0) + 10, 100);
          updatedSyncStatus[serviceId] = {
            ...status,
            progress: newProgress,
            items_processed: (status.items_processed || 0) + 50,
            status: newProgress === 100 ? "success" : "syncing",
          };
        }
      });

      setSyncStatus(updatedSyncStatus);
    } catch (error) {
      console.error("Error fetching sync status:", error);
    }
  };

  const handleServiceConnect = async (serviceId: string) => {
    try {
      setSyncing(true);
      // Simulate API call for service connection
      await new Promise((resolve) => setTimeout(resolve, 2000));

      const updatedServices = services.map((service) =>
        service.id === serviceId
          ? { ...service, status: "connected", sync_status: "syncing" as const }
          : service,
      );

      setServices(updatedServices);

      // Update sync status
      setSyncStatus((prev) => ({
        ...prev,
        [serviceId]: {
          service_id: serviceId,
          status: "syncing",
          progress: 0,
          items_processed: 0,
          total_items: 500,
          last_sync: new Date().toISOString(),
        },
      }));

      toast({
        title: "Service Connected",
        description: `${services.find((s) => s.id === serviceId)?.name} has been connected successfully`,
        status: "success",
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error("Error connecting service:", error);
      toast({
        title: "Connection Failed",
        description: "Failed to connect the service. Please try again.",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setSyncing(false);
    }
  };

  const handleServiceDisconnect = async (serviceId: string) => {
    try {
      // Simulate API call for service disconnection
      await new Promise((resolve) => setTimeout(resolve, 1000));

      const updatedServices = services.map((service) =>
        service.id === serviceId
          ? { ...service, status: "disconnected", sync_status: undefined }
          : service,
      );

      setServices(updatedServices);

      // Remove from sync status
      const updatedSyncStatus = { ...syncStatus };
      delete updatedSyncStatus[serviceId];
      setSyncStatus(updatedSyncStatus);

      toast({
        title: "Service Disconnected",
        description: `${services.find((s) => s.id === serviceId)?.name} has been disconnected`,
        status: "info",
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error("Error disconnecting service:", error);
      toast({
        title: "Disconnection Failed",
        description: "Failed to disconnect the service. Please try again.",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleManualSync = async (serviceId: string) => {
    try {
      setSyncing(true);
      // Simulate API call for manual sync
      await new Promise((resolve) => setTimeout(resolve, 1500));

      setSyncStatus((prev) => ({
        ...prev,
        [serviceId]: {
          service_id: serviceId,
          status: "syncing",
          progress: 0,
          items_processed: 0,
          total_items: 500,
          last_sync: new Date().toISOString(),
        },
      }));

      toast({
        title: "Sync Started",
        description: `Syncing ${services.find((s) => s.id === serviceId)?.name} data`,
        status: "info",
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error("Error starting manual sync:", error);
      toast({
        title: "Sync Failed",
        description: "Failed to start synchronization",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    } finally {
      setSyncing(false);
    }
  };

  const renderServiceIcon = (service: ServiceConnection) => {
    const iconProps = { boxSize: 6, color: getStatusColor(service.status) };
    switch (service.icon) {
      case "calendar":
        return <CalendarIcon {...iconProps} />;
      case "email":
        return <EmailIcon {...iconProps} />;
      case "tasks":
        return <CheckIcon {...iconProps} />;
      case "document":
        return <AttachmentIcon {...iconProps} />;
      case "storage":
        return <DownloadIcon {...iconProps} />;
      case "chat":
        return <ChatIcon {...iconProps} />;
      case "code":
        return <ViewIcon {...iconProps} />;
      default:
        return <SettingsIcon {...iconProps} />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
        return "green.500";
      case "disconnected":
        return "red.500";
      case "error":
        return "orange.500";
      case "pending":
        return "yellow.500";
      default:
        return "gray.500";
    }
  };

  const getStatusBadgeColor = (status: string) => {
    switch (status) {
      case "connected":
        return "green";
      case "disconnected":
        return "red";
      case "error":
        return "orange";
      case "pending":
        return "yellow";
      default:
        return "gray";
    }
  };

  const getSyncStatusColor = (status?: string) => {
    switch (status) {
      case "success":
        return "green";
      case "syncing":
        return "blue";
      case "failed":
        return "red";
      default:
        return "gray";
    }
  };

  const formatLastSync = (timestamp?: string) => {
    if (!timestamp) return "Never";
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  if (loading) {
    return (
      <Box p={8}>
        <VStack spacing={4} align="center">
          <Spinner size="xl" />
          <Text>Loading service integrations...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box p={8}>
      {/* Header */}
      <HStack justify="space-between" mb={8}>
        <VStack align="start" spacing={1}>
          <Heading size="xl">Service Integrations</Heading>
          <Text color="gray.600">
            Manage your connected services and data synchronization
          </Text>
        </VStack>
        <Button
          leftIcon={<AddIcon />}
          colorScheme="blue"
          onClick={onServiceModalOpen}
        >
          Add Service
        </Button>
      </HStack>

      {/* Stats Overview */}
      {stats && (
        <Grid templateColumns="repeat(5, 1fr)" gap={6} mb={8}>
          <Card>
            <CardBody>
              <VStack align="center">
                <Text fontSize="2xl" fontWeight="bold" color="blue.500">
                  {stats.total_services}
                </Text>
                <Text color="gray.600">Total Services</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack align="center">
                <Text fontSize="2xl" fontWeight="bold" color="green.500">
                  {stats.connected_services}
                </Text>
                <Text color="gray.600">Connected</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack align="center">
                <Text fontSize="2xl" fontWeight="bold" color="purple.500">
                  {stats.sync_success_rate}%
                </Text>
                <Text color="gray.600">Sync Success</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack align="center">
                <Text fontSize="2xl" fontWeight="bold" color="orange.500">
                  {stats.active_workflows}
                </Text>
                <Text color="gray.600">Active Workflows</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack align="center">
                <Text fontSize="sm" fontWeight="bold">
                  {formatLastSync(stats.last_sync_overall)}
                </Text>
                <Text color="gray.600">Last Sync</Text>
              </VStack>
            </CardBody>
          </Card>
        </Grid>
      )}

      {/* Main Content */}
      <Tabs variant="enclosed" onChange={setActiveTab}>
        <TabList>
          <Tab>All Services</Tab>
          <Tab>Sync Status</Tab>
          <Tab>Capabilities</Tab>
        </TabList>

        <TabPanels>
          {/* All Services Tab */}
          <TabPanel>
            <Grid
              templateColumns="repeat(auto-fill, minmax(350px, 1fr))"
              gap={6}
            >
              {services.map((service) => (
                <Card key={service.id}>
                  <CardHeader>
                    <HStack justify="space-between">
                      <HStack>
                        {renderServiceIcon(service)}
                        <VStack align="start" spacing={0}>
                          <Heading size="md">{service.name}</Heading>
                          <Text fontSize="sm" color="gray.600">
                            {service.description}
                          </Text>
                        </VStack>
                      </HStack>
                      <Badge colorScheme={getStatusBadgeColor(service.status)}>
                        {service.status}
                      </Badge>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <VStack align="start" spacing={3}>
                      <HStack justify="space-between" w="full">
                        <Text fontSize="sm" color="gray.600">
                          Last Sync:
                        </Text>
                        <Text fontSize="sm" fontWeight="medium">
                          {formatLastSync(service.last_sync)}
                        </Text>
                      </HStack>

                      {syncStatus[service.id] && (
                        <>
                          <VStack align="start" spacing={1} w="full">
                            <HStack justify="space-between" w="full">
                              <Text fontSize="sm" color="gray.600">
                                Sync Status:
                              </Text>
                              <Badge
                                colorScheme={getSyncStatusColor(
                                  syncStatus[service.id].status,
                                )}
                                size="sm"
                              >
                                {syncStatus[service.id].status}
                              </Badge>
                            </HStack>
                            {syncStatus[service.id].status === "syncing" && (
                              <Progress
                                value={syncStatus[service.id].progress}
                                size="sm"
                                w="full"
                                colorScheme="blue"
                                hasStripe
                                isAnimated
                              />
                            )}
                          </VStack>

                          {syncStatus[service.id].items_processed &&
                            syncStatus[service.id].total_items && (
                              <HStack justify="space-between" w="full">
                                <Text fontSize="sm" color="gray.600">
                                  Items Processed:
                                </Text>
                                <Text fontSize="sm" fontWeight="medium">
                                  {syncStatus[service.id].items_processed} /{" "}
                                  {syncStatus[service.id].total_items}
                                </Text>
                              </HStack>
                            )}
                        </>
                      )}

                      <VStack align="start" spacing={1} w="full">
                        <Text fontSize="sm" color="gray.600">
                          Capabilities:
                        </Text>
                        <HStack flexWrap="wrap" spacing={1}>
                          {service.capabilities
                            .slice(0, 3)
                            .map((capability) => (
                              <Badge
                                key={capability}
                                size="sm"
                                colorScheme="blue"
                                variant="subtle"
                              >
                                {capability}
                              </Badge>
                            ))}
                          {service.capabilities.length > 3 && (
                            <Badge
                              size="sm"
                              colorScheme="gray"
                              variant="subtle"
                            >
                              +{service.capabilities.length - 3} more
                            </Badge>
                          )}
                        </HStack>
                      </VStack>

                      {service.error_message && (
                        <Alert status="error" size="sm">
                          <AlertIcon />
                          <Text fontSize="sm">{service.error_message}</Text>
                        </Alert>
                      )}
                    </VStack>
                  </CardBody>
                  <CardFooter>
                    <HStack justify="space-between" w="full">
                      {service.status === "connected" ? (
                        <>
                          <Button
                            size="sm"
                            leftIcon={<RepeatIcon />}
                            colorScheme="blue"
                            variant="outline"
                            isLoading={syncing}
                            onClick={() => handleManualSync(service.id)}
                          >
                            Sync Now
                          </Button>
                          <Button
                            size="sm"
                            leftIcon={<CloseIcon />}
                            colorScheme="red"
                            variant="ghost"
                            onClick={() => handleServiceDisconnect(service.id)}
                          >
                            Disconnect
                          </Button>
                        </>
                      ) : (
                        <Button
                          size="sm"
                          leftIcon={<CheckIcon />}
                          colorScheme="green"
                          w="full"
                          isLoading={syncing}
                          onClick={() => handleServiceConnect(service.id)}
                        >
                          Connect
                        </Button>
                      )}
                    </HStack>
                  </CardFooter>
                </Card>
              ))}
            </Grid>
          </TabPanel>

          {/* Sync Status Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              {Object.values(syncStatus).map((status) => {
                const service = services.find(
                  (s) => s.id === status.service_id,
                );
                if (!service) return null;

                return (
                  <Card key={status.service_id}>
                    <CardBody>
                      <HStack justify="space-between">
                        <HStack>
                          {renderServiceIcon(service)}
                          <VStack align="start" spacing={0}>
                            <Heading size="md">{service.name}</Heading>
                            <Text fontSize="sm" color="gray.600">
                              {service.description}
                            </Text>
                          </VStack>
                        </HStack>
                        <Badge colorScheme={getSyncStatusColor(status.status)}>
                          {status.status}
                        </Badge>
                      </HStack>

                      <Divider my={4} />

                      <VStack align="start" spacing={3}>
                        <HStack justify="space-between" w="full">
                          <Text>Progress:</Text>
                          <Text fontWeight="medium">{status.progress}%</Text>
                        </HStack>

                        <Progress
                          value={status.progress}
                          size="lg"
                          w="full"
                          colorScheme={getSyncStatusColor(status.status)}
                          hasStripe={status.status === "syncing"}
                          isAnimated={status.status === "syncing"}
                        />

                        {status.items_processed && status.total_items && (
                          <HStack justify="space-between" w="full">
                            <Text>Items Processed:</Text>
                            <Text fontWeight="medium">
                              {status.items_processed} / {status.total_items}
                            </Text>
                          </HStack>
                        )}

                        <HStack justify="space-between" w="full">
                          <Text>Last Sync:</Text>
                          <Text fontWeight="medium">
                            {formatLastSync(status.last_sync)}
                          </Text>
                        </HStack>

                        {status.error_message && (
                          <Alert status="error" size="sm">
                            <AlertIcon />
                            <Text fontSize="sm">{status.error_message}</Text>
                          </Alert>
                        )}
                      </VStack>
                    </CardBody>
                    <CardFooter>
                      <Button
                        size="sm"
                        leftIcon={<RepeatIcon />}
                        colorScheme="blue"
                        isLoading={syncing}
                        onClick={() => handleManualSync(status.service_id)}
                      >
                        Sync Now
                      </Button>
                    </CardFooter>
                  </Card>
                );
              })}

              {Object.keys(syncStatus).length === 0 && (
                <Alert status="info">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>No Active Syncs</AlertTitle>
                    <AlertDescription>
                      No services are currently syncing. Start a sync to see
                      status here.
                    </AlertDescription>
                  </Box>
                </Alert>
              )}
            </VStack>
          </TabPanel>

          {/* Capabilities Tab */}
          <TabPanel>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Service</Th>
                  <Th>Status</Th>
                  <Th>Capabilities</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {services.map((service) => (
                  <Tr key={service.id}>
                    <Td>
                      <HStack>
                        {renderServiceIcon(service)}
                        <VStack align="start" spacing={0}>
                          <Text fontWeight="medium">{service.name}</Text>
                          <Text fontSize="sm" color="gray.600">
                            {service.description}
                          </Text>
                        </VStack>
                      </HStack>
                    </Td>
                    <Td>
                      <Badge colorScheme={getStatusBadgeColor(service.status)}>
                        {service.status}
                      </Badge>
                    </Td>
                    <Td>
                      <VStack align="start" spacing={1}>
                        {service.capabilities.map((capability) => (
                          <Badge
                            key={capability}
                            size="sm"
                            colorScheme="blue"
                            variant="subtle"
                          >
                            {capability}
                          </Badge>
                        ))}
                      </VStack>
                    </Td>
                    <Td>
                      <HStack>
                        {service.status === "connected" ? (
                          <>
                            <IconButton
                              aria-label="Sync service"
                              icon={<RepeatIcon />}
                              size="sm"
                              colorScheme="blue"
                              variant="ghost"
                              isLoading={syncing}
                              onClick={() => handleManualSync(service.id)}
                            />
                            <IconButton
                              aria-label="Disconnect service"
                              icon={<CloseIcon />}
                              size="sm"
                              colorScheme="red"
                              variant="ghost"
                              onClick={() =>
                                handleServiceDisconnect(service.id)
                              }
                            />
                          </>
                        ) : (
                          <Button
                            size="sm"
                            colorScheme="green"
                            isLoading={syncing}
                            onClick={() => handleServiceConnect(service.id)}
                          >
                            Connect
                          </Button>
                        )}
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </TabPanel>
        </TabPanels>
      </Tabs>

      {/* Add Service Modal */}
      <Modal
        isOpen={isServiceModalOpen}
        onClose={onServiceModalClose}
        size="lg"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Add New Service</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Text>
                Connect new services to expand your automation capabilities.
                Available services include calendar, email, task management,
                document storage, and communication platforms.
              </Text>

              <Alert status="info">
                <AlertIcon />
                <Box>
                  <AlertTitle>Coming Soon</AlertTitle>
                  <AlertDescription>
                    Service integration wizard is under development. For now,
                    use the connect buttons on individual service cards.
                  </AlertDescription>
                </Box>
              </Alert>

              <Text fontSize="sm" color="gray.600">
                Currently available services: Google Calendar, Gmail, Asana,
                Trello, Notion, Dropbox, Slack, GitHub, and more.
              </Text>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" onClick={onServiceModalClose}>
              Got it
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Service Configuration Modal */}
      <Modal isOpen={isConfigModalOpen} onClose={onConfigModalClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Configure {selectedService?.name}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedService && (
              <VStack spacing={4} align="stretch">
                <Text>
                  Configure settings and preferences for {selectedService.name}.
                </Text>

                <FormControl>
                  <FormLabel>Sync Frequency</FormLabel>
                  <Select placeholder="Select sync frequency">
                    <option value="realtime">Real-time</option>
                    <option value="15min">Every 15 minutes</option>
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                    <option value="manual">Manual only</option>
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>Data Retention</FormLabel>
                  <Select placeholder="Select retention period">
                    <option value="30days">30 days</option>
                    <option value="90days">90 days</option>
                    <option value="1year">1 year</option>
                    <option value="forever">Keep forever</option>
                  </Select>
                </FormControl>

                <Alert status="warning">
                  <AlertIcon />
                  <Text fontSize="sm">
                    Configuration changes will take effect on the next sync
                    cycle.
                  </Text>
                </Alert>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onConfigModalClose}>
              Cancel
            </Button>
            <Button colorScheme="blue">Save Configuration</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default ServiceIntegrationDashboard;
