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
  Badge,
  Spinner,
  useToast,
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
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  Switch,
  Progress,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  IconButton,
  Tooltip,
  Divider,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Code,
  Tag,
  TagLabel,
  TagCloseButton,
} from "@chakra-ui/react";
import {
  AddIcon,
  CheckIcon,
  CloseIcon,
  SettingsIcon,
  CalendarIcon,
  ChatIcon,
  EmailIcon,
  AttachmentIcon,
  DownloadIcon,
  RepeatIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ExternalLinkIcon,
  WarningIcon,
  InfoIcon,
  StarIcon,
  TimeIcon,
} from "@chakra-ui/icons";

interface Service {
  id: string;
  name: string;
  status: "connected" | "disconnected" | "error" | "pending";
  type: "integration" | "core";
  description: string;
  capabilities: string[];
  health: "healthy" | "degraded" | "unhealthy";
  last_checked: string;
  configuration?: Record<string, any>;
  oauth_url?: string;
  api_key_required?: boolean;
}

interface ServiceConnection {
  id: string;
  service_id: string;
  name: string;
  status: "active" | "inactive" | "error";
  connected_at: string;
  last_sync: string;
  sync_status: "syncing" | "success" | "failed";
  error_count: number;
}

interface ServiceStats {
  total_services: number;
  active_services: number;
  healthy_services: number;
  sync_success_rate: number;
  total_connections: number;
  last_updated: string;
}

const ServiceManagement: React.FC = () => {
  const [services, setServices] = useState<Service[]>([]);
  const [connections, setConnections] = useState<ServiceConnection[]>([]);
  const [stats, setStats] = useState<ServiceStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const [selectedService, setSelectedService] = useState<Service | null>(null);

  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();

  // Mock data for demonstration
  const mockServices: Service[] = [
    {
      id: "calendar",
      name: "Google Calendar",
      status: "connected",
      type: "integration",
      description: "Calendar integration for event management and scheduling",
      capabilities: [
        "create_event",
        "find_availability",
        "list_events",
        "update_event",
        "delete_event",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
      oauth_url: "/api/atom/auth/calendar/initiate",
    },
    {
      id: "tasks",
      name: "Task Management",
      status: "connected",
      type: "integration",
      description: "Asana and Trello task management integration",
      capabilities: [
        "create_task",
        "update_task",
        "list_tasks",
        "assign_task",
        "complete_task",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
    },
    {
      id: "email",
      name: "Gmail",
      status: "connected",
      type: "integration",
      description: "Email integration for communication and automation",
      capabilities: [
        "send_email",
        "list_emails",
        "search_emails",
        "create_draft",
        "manage_labels",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
      oauth_url: "/api/atom/auth/gmail/initiate",
    },
    {
      id: "slack",
      name: "Slack",
      status: "connected",
      type: "integration",
      description: "Slack messaging and channel management",
      capabilities: [
        "send_message",
        "list_channels",
        "search_messages",
        "create_channel",
        "manage_members",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
      oauth_url: "/api/atom/auth/slack/initiate",
    },
    {
      id: "notion",
      name: "Notion",
      status: "connected",
      type: "integration",
      description: "Notion workspace and database integration",
      capabilities: [
        "create_page",
        "update_page",
        "search_pages",
        "query_database",
        "manage_blocks",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
      oauth_url: "/api/atom/auth/notion/initiate",
    },
    {
      id: "dropbox",
      name: "Dropbox",
      status: "connected",
      type: "integration",
      description: "Dropbox file storage and sharing",
      capabilities: [
        "upload_file",
        "download_file",
        "list_files",
        "share_file",
        "manage_folders",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
      oauth_url: "/api/atom/auth/dropbox/initiate",
    },
    {
      id: "gdrive",
      name: "Google Drive",
      status: "connected",
      type: "integration",
      description: "Google Drive file management and collaboration",
      capabilities: [
        "upload_file",
        "download_file",
        "list_files",
        "share_file",
        "search_files",
        "manage_permissions",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
      oauth_url: "/api/auth/gdrive/initiate",
    },
    {
      id: "onedrive",
      name: "OneDrive",
      status: "connected",
      type: "integration",
      description: "Microsoft OneDrive file management and collaboration",
      capabilities: [
        "upload_file",
        "download_file",
        "list_files",
        "share_file",
        "search_files",
        "manage_permissions",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
      oauth_url: "/api/auth/onedrive/authorize",
    },
    {
      id: "github",
      name: "GitHub",
      status: "connected",
      type: "integration",
      description: "GitHub repository and project management",
      capabilities: [
        "create_issue",
        "list_repos",
        "search_code",
        "manage_pr",
        "webhook_management",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
      oauth_url: "/api/atom/auth/github/initiate",
    },
    {
      id: "workflow",
      name: "Workflow Automation",
      status: "active",
      type: "core",
      description:
        "Workflow automation engine with natural language processing",
      capabilities: [
        "create_workflow",
        "execute_workflow",
        "schedule_workflow",
        "monitor_execution",
        "manage_templates",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
    },
    {
      id: "notifications",
      name: "Notifications",
      status: "active",
      type: "core",
      description: "Unified notification system across all platforms",
      capabilities: [
        "send_notification",
        "manage_preferences",
        "schedule_reminders",
        "batch_notifications",
        "analytics",
      ],
      health: "healthy",
      last_checked: new Date().toISOString(),
    },
  ];

  const mockConnections: ServiceConnection[] = [
    {
      id: "1",
      service_id: "calendar",
      name: "Primary Calendar",
      status: "active",
      connected_at: "2025-10-01T10:00:00Z",
      last_sync: new Date().toISOString(),
      sync_status: "success",
      error_count: 0,
    },
    {
      id: "2",
      service_id: "tasks",
      name: "Asana Workspace",
      status: "active",
      connected_at: "2025-10-02T14:30:00Z",
      last_sync: new Date().toISOString(),
      sync_status: "success",
      error_count: 2,
    },
    {
      id: "3",
      service_id: "email",
      name: "Gmail Account",
      status: "active",
      connected_at: "2025-10-03T09:15:00Z",
      last_sync: new Date().toISOString(),
      sync_status: "syncing",
      error_count: 0,
    },
  ];

  const mockStats: ServiceStats = {
    total_services: mockServices.length,
    active_services: mockServices.filter(
      (s) => s.status === "connected" || s.status === "active",
    ).length,
    healthy_services: mockServices.filter((s) => s.health === "healthy").length,
    sync_success_rate: 95.2,
    total_connections: mockConnections.length,
    last_updated: new Date().toISOString(),
  };

  const fetchServices = async () => {
    try {
      const response = await fetch("/api/services");
      if (response.ok) {
        const data = await response.json();
        setServices(data.services || mockServices);
        setStats(data.stats || mockStats);
      } else {
        // Fallback to mock data
        setServices(mockServices);
        setStats(mockStats);
        setConnections(mockConnections);
      }
    } catch (error) {
      console.error("Error fetching services:", error);
      // Fallback to mock data
      setServices(mockServices);
      setStats(mockStats);
      setConnections(mockConnections);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchServices();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchServices();
  };

  const handleServiceConnect = async (service: Service) => {
    try {
      if (service.oauth_url) {
        // Redirect to OAuth flow
        window.location.href = service.oauth_url;
      } else {
        // Manual configuration
        setSelectedService(service);
        onOpen();
      }
    } catch (error) {
      toast({
        title: "Connection Failed",
        description: `Failed to connect to ${service.name}`,
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleServiceDisconnect = async (serviceId: string) => {
    try {
      const response = await fetch(`/api/services/${serviceId}/disconnect`, {
        method: "POST",
      });

      if (response.ok) {
        toast({
          title: "Service Disconnected",
          description: "Service has been disconnected successfully",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
        fetchServices();
      } else {
        throw new Error("Disconnect failed");
      }
    } catch (error) {
      toast({
        title: "Disconnect Failed",
        description: "Failed to disconnect the service",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSyncNow = async (connectionId: string) => {
    try {
      const response = await fetch(
        `/api/services/connections/${connectionId}/sync`,
        {
          method: "POST",
        },
      );

      if (response.ok) {
        toast({
          title: "Sync Started",
          description: "Data synchronization has been initiated",
          status: "success",
          duration: 2000,
          isClosable: true,
        });
        fetchServices();
      }
    } catch (error) {
      toast({
        title: "Sync Failed",
        description: "Failed to start synchronization",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "connected":
      case "active":
        return "green";
      case "disconnected":
      case "inactive":
        return "gray";
      case "error":
        return "red";
      case "pending":
        return "yellow";
      default:
        return "gray";
    }
  };

  const getHealthColor = (health: string) => {
    switch (health) {
      case "healthy":
        return "green";
      case "degraded":
        return "yellow";
      case "unhealthy":
        return "red";
      default:
        return "gray";
    }
  };

  const getSyncStatusColor = (status: string) => {
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

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <Box p={8}>
        <VStack spacing={4} align="center">
          <Spinner size="xl" />
          <Text>Loading service management...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box p={8}>
      {/* Header */}
      <HStack justify="space-between" mb={8}>
        <VStack align="start" spacing={1}>
          <Heading size="xl">Service Management</Heading>
          <Text color="gray.600">
            Manage your connected services and integrations
          </Text>
        </VStack>
        <Button
          leftIcon={<RepeatIcon />}
          colorScheme="blue"
          onClick={handleRefresh}
          isLoading={refreshing}
        >
          Refresh
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
                  {stats.active_services}
                </Text>
                <Text color="gray.600">Active Services</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack align="center">
                <Text fontSize="2xl" fontWeight="bold" color="green.500">
                  {stats.healthy_services}
                </Text>
                <Text color="gray.600">Healthy Services</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack align="center">
                <Text fontSize="2xl" fontWeight="bold" color="purple.500">
                  {stats.sync_success_rate}%
                </Text>
                <Text color="gray.600">Sync Success Rate</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack align="center">
                <Text fontSize="2xl" fontWeight="bold" color="orange.500">
                  {stats.total_connections}
                </Text>
                <Text color="gray.600">Connections</Text>
              </VStack>
            </CardBody>
          </Card>
        </Grid>
      )}

      {/* Main Tabs */}
      <Tabs variant="enclosed" onChange={setActiveTab}>
        <TabList>
          <Tab>All Services</Tab>
          <Tab>Active Connections</Tab>
          <Tab>Service Health</Tab>
          <Tab>Integration Settings</Tab>
        </TabList>

        <TabPanels>
          {/* All Services Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              <Grid
                templateColumns="repeat(auto-fill, minmax(300px, 1fr))"
                gap={6}
              >
                {services.map((service) => (
                  <Card
                    key={service.id}
                    borderWidth="1px"
                    borderColor="gray.200"
                  >
                    <CardHeader>
                      <HStack justify="space-between" align="start">
                        <VStack align="start" spacing={1}>
                          <Heading size="md">{service.name}</Heading>
                          <Badge
                            colorScheme={getStatusColor(service.status)}
                            size="sm"
                          >
                            {service.status}
                          </Badge>
                        </VStack>
                        <Badge
                          colorScheme={getHealthColor(service.health)}
                          size="sm"
                        >
                          {service.health}
                        </Badge>
                      </HStack>
                    </CardHeader>
                    <CardBody>
                      <Text color="gray.600" mb={3}>
                        {service.description}
                      </Text>

                      <VStack align="start" spacing={2} mb={4}>
                        <Text fontSize="sm" fontWeight="medium">
                          Capabilities:
                        </Text>
                        <HStack flexWrap="wrap" spacing={1}>
                          {service.capabilities
                            .slice(0, 3)
                            .map((capability) => (
                              <Tag
                                key={capability}
                                size="sm"
                                colorScheme="blue"
                              >
                                <TagLabel>{capability}</TagLabel>
                              </Tag>
                            ))}
                          {service.capabilities.length > 3 && (
                            <Tag size="sm" colorScheme="gray">
                              <TagLabel>
                                +{service.capabilities.length - 3} more
                              </TagLabel>
                            </Tag>
                          )}
                        </HStack>
                      </VStack>

                      <Text fontSize="sm" color="gray.500">
                        Last checked: {formatDate(service.last_checked)}
                      </Text>
                    </CardBody>
                    <CardFooter>
                      <HStack spacing={2} w="full">
                        {service.status === "connected" ||
                        service.status === "active" ? (
                          <>
                            <Button
                              size="sm"
                              colorScheme="blue"
                              leftIcon={<SettingsIcon />}
                              flex={1}
                            >
                              Configure
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              colorScheme="red"
                              onClick={() =>
                                handleServiceDisconnect(service.id)
                              }
                            >
                              Disconnect
                            </Button>
                          </>
                        ) : (
                          <Button
                            size="sm"
                            colorScheme="green"
                            leftIcon={<AddIcon />}
                            flex={1}
                            onClick={() => handleServiceConnect(service)}
                          >
                            Connect
                          </Button>
                        )}
                      </HStack>
                    </CardFooter>
                  </Card>
                ))}
              </Grid>
            </VStack>
          </TabPanel>

          {/* Active Connections Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              <Heading size="lg">Active Service Connections</Heading>
              {connections.map((connection) => (
                <Card key={connection.id}>
                  <CardHeader>
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <Heading size="md">{connection.name}</Heading>
                        <Text color="gray.600">
                          Service:{" "}
                          {
                            services.find((s) => s.id === connection.service_id)
                              ?.name
                          }
                        </Text>
                      </VStack>
                      <HStack spacing={3}>
                        <Badge colorScheme={getStatusColor(connection.status)}>
                          {connection.status}
                        </Badge>
                        <Badge
                          colorScheme={getSyncStatusColor(
                            connection.sync_status,
                          )}
                        >
                          {connection.sync_status}
                        </Badge>
                      </HStack>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <Grid templateColumns="repeat(4, 1fr)" gap={4}>
                      <Stat>
                        <StatLabel>Connected</StatLabel>
                        <StatNumber fontSize="md">
                          {formatDate(connection.connected_at)}
                        </StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel>Last Sync</StatLabel>
                        <StatNumber fontSize="md">
                          {formatDate(connection.last_sync)}
                        </StatNumber>
                      </Stat>
                      <Stat>
                        <StatLabel>Error Count</StatLabel>
                        <StatNumber fontSize="md">
                          {connection.error_count}
                        </StatNumber>
                        {connection.error_count > 0 && (
                          <StatHelpText>
                            <StatArrow type="decrease" />
                            Needs attention
                          </StatHelpText>
                        )}
                      </Stat>
                      <Stat>
                        <StatLabel>Actions</StatLabel>
                        <HStack spacing={2}>
                          <IconButton
                            aria-label="Sync now"
                            icon={<RepeatIcon />}
                            size="sm"
                            colorScheme="blue"
                            onClick={() => handleSyncNow(connection.id)}
                          />
                          <IconButton
                            aria-label="View details"
                            icon={<ViewIcon />}
                            size="sm"
                            variant="outline"
                          />
                        </HStack>
                      </Stat>
                    </Grid>
                  </CardBody>
                </Card>
              ))}
            </VStack>
          </TabPanel>

          {/* Service Health Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              <Heading size="lg">Service Health Monitoring</Heading>
              {services.map((service) => (
                <Card key={service.id}>
                  <CardHeader>
                    <HStack justify="space-between">
                      <Heading size="md">{service.name}</Heading>
                      <Badge
                        colorScheme={getHealthColor(service.health)}
                        size="lg"
                      >
                        {service.health.toUpperCase()}
                      </Badge>
                    </HStack>
                  </CardHeader>
                  <CardBody>
                    <VStack align="start" spacing={4}>
                      <Box w="full">
                        <HStack justify="space-between" mb={2}>
                          <Text fontWeight="medium">Service Status</Text>
                          <Badge colorScheme={getStatusColor(service.status)}>
                            {service.status}
                          </Badge>
                        </HStack>
                        <Progress
                          value={
                            service.health === "healthy"
                              ? 100
                              : service.health === "degraded"
                                ? 60
                                : 20
                          }
                          colorScheme={getHealthColor(service.health)}
                          size="sm"
                          borderRadius="md"
                        />
                      </Box>

                      <Box w="full">
                        <HStack justify="space-between" mb={2}>
                          <Text fontWeight="medium">Capability Coverage</Text>
                          <Text fontSize="sm" color="gray.600">
                            {service.capabilities.length} capabilities
                          </Text>
                        </HStack>
                        <Progress
                          value={(service.capabilities.length / 10) * 100}
                          colorScheme="blue"
                          size="sm"
                          borderRadius="md"
                        />
                      </Box>

                      <HStack justify="space-between" w="full">
                        <Text fontWeight="medium">Last Checked</Text>
                        <Text fontSize="sm" color="gray.600">
                          {formatDate(service.last_checked)}
                        </Text>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>
              ))}
            </VStack>
          </TabPanel>

          {/* Integration Settings Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              <Heading size="lg">Integration Settings</Heading>

              <Card>
                <CardHeader>
                  <Heading size="md">Global Sync Settings</Heading>
                </CardHeader>
                <CardBody>
                  <VStack spacing={4} align="start">
                    <FormControl>
                      <FormLabel>Auto-sync Interval</FormLabel>
                      <Select defaultValue="15">
                        <option value="5">Every 5 minutes</option>
                        <option value="15">Every 15 minutes</option>
                        <option value="30">Every 30 minutes</option>
                        <option value="60">Every hour</option>
                      </Select>
                    </FormControl>

                    <FormControl display="flex" alignItems="center">
                      <FormLabel mb="0">Enable Background Sync</FormLabel>
                      <Switch defaultChecked />
                    </FormControl>

                    <FormControl display="flex" alignItems="center">
                      <FormLabel mb="0">Error Notifications</FormLabel>
                      <Switch defaultChecked />
                    </FormControl>

                    <FormControl display="flex" alignItems="center">
                      <FormLabel mb="0">Performance Analytics</FormLabel>
                      <Switch defaultChecked />
                    </FormControl>
                  </VStack>
                </CardBody>
                <CardFooter>
                  <Button colorScheme="blue">Save Settings</Button>
                </CardFooter>
              </Card>

              <Card>
                <CardHeader>
                  <Heading size="md">Service-Specific Settings</Heading>
                </CardHeader>
                <CardBody>
                  <Accordion allowMultiple>
                    {services.map((service) => (
                      <AccordionItem key={service.id}>
                        <AccordionButton>
                          <Box flex="1" textAlign="left">
                            <HStack>
                              <Text fontWeight="medium">{service.name}</Text>
                              <Badge
                                colorScheme={getStatusColor(service.status)}
                              >
                                {service.status}
                              </Badge>
                            </HStack>
                          </Box>
                          <AccordionIcon />
                        </AccordionButton>
                        <AccordionPanel pb={4}>
                          <VStack spacing={4} align="start">
                            <FormControl>
                              <FormLabel>Sync Priority</FormLabel>
                              <Select defaultValue="normal">
                                <option value="low">Low</option>
                                <option value="normal">Normal</option>
                                <option value="high">High</option>
                              </Select>
                            </FormControl>

                            <FormControl display="flex" alignItems="center">
                              <FormLabel mb="0">
                                Enable Real-time Updates
                              </FormLabel>
                              <Switch
                                defaultChecked={service.type === "core"}
                              />
                            </FormControl>

                            <FormControl>
                              <FormLabel>Data Retention</FormLabel>
                              <Select defaultValue="30">
                                <option value="7">7 days</option>
                                <option value="30">30 days</option>
                                <option value="90">90 days</option>
                                <option value="365">1 year</option>
                              </Select>
                            </FormControl>

                            <Button size="sm" colorScheme="blue">
                              Save {service.name} Settings
                            </Button>
                          </VStack>
                        </AccordionPanel>
                      </AccordionItem>
                    ))}
                  </Accordion>
                </CardBody>
              </Card>
            </VStack>
          </TabPanel>
        </TabPanels>
      </Tabs>

      {/* Service Configuration Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Configure {selectedService?.name}</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedService && (
              <VStack spacing={4} align="stretch">
                <FormControl>
                  <FormLabel>API Key</FormLabel>
                  <Input placeholder="Enter your API key" />
                </FormControl>

                <FormControl>
                  <FormLabel>Service URL</FormLabel>
                  <Input placeholder="https://api.example.com" />
                </FormControl>

                <FormControl>
                  <FormLabel>Configuration Notes</FormLabel>
                  <Textarea placeholder="Any additional configuration details..." />
                </FormControl>

                <Alert status="info">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>OAuth Recommended</AlertTitle>
                    <AlertDescription>
                      For better security, we recommend using OAuth
                      authentication instead of API keys.
                    </AlertDescription>
                  </Box>
                </Alert>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button colorScheme="blue">Save Configuration</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default ServiceManagement;
