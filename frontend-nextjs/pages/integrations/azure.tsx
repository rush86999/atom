/**
 * Azure Integration Page
 * Complete Microsoft Azure cloud platform integration
 */

import React, { useState, useEffect } from 'react';
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
  Divider,
  useColorModeValue,
  Stack,
  Spacer,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
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
  FormControl,
  FormLabel,
  Input,
  Select,
  Textarea,
  useDisclosure,
  Tag,
  TagLabel,
  Flex,
  Grid,
  GridItem,
  Alert,
  AlertIcon,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  NumberInput,
  NumberInputField,
  Switch,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  FormErrorMessage,
  RadioGroup,
  Radio,
} from "@chakra-ui/react";
import {
  CloudIcon,
  ServerIcon,
  DatabaseIcon,
  GlobeIcon,
  SettingsIcon,
  ExternalLinkIcon,
  SearchIcon,
  AddIcon,
  RepeatIcon,
  PlayIcon,
  StopIcon,
  PauseIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  CheckCircleIcon,
  WarningIcon,
  InfoIcon,
  FolderIcon,
  CubeIcon,
  MoneyIcon,
  ChartBarIcon,
  CpuIcon,
  DiskIcon,
  NetworkIcon,
} from "@chakra-ui/icons";

interface AzureResourceGroup {
  id: string;
  name: string;
  location: string;
  tags: Record<string, string>;
  created_at: string;
}

interface AzureVirtualMachine {
  id: string;
  name: string;
  location: string;
  size: string;
  status: string;
  os_type: string;
  admin_username: string;
  public_ip: string;
  created_at: string;
  resource_group: string;
}

interface AzureStorageAccount {
  id: string;
  name: string;
  location: string;
  type: string;
  tier: string;
  replication: string;
  access_tier: string;
  blob_endpoint: string;
  file_endpoint: string;
  created_at: string;
  resource_group: string;
}

interface AzureAppService {
  id: string;
  name: string;
  location: string;
  state: string;
  host_names: string[];
  app_service_plan: string;
  runtime: string;
  https_only: boolean;
  created_at: string;
  resource_group: string;
}

interface AzureCostItem {
  date: string;
  service_name: string;
  resource_group: string;
  currency: string;
  cost: number;
}

interface AzureFile {
  name: string;
  size: number;
  content_type: string;
  last_modified: string;
  etag: string;
}

const AzureIntegration: React.FC = () => {
  const [resourceGroups, setResourceGroups] = useState<AzureResourceGroup[]>([]);
  const [virtualMachines, setVirtualMachines] = useState<AzureVirtualMachine[]>([]);
  const [storageAccounts, setStorageAccounts] = useState<AzureStorageAccount[]>([]);
  const [appServices, setAppServices] = useState<AzureAppService[]>([]);
  const [costAnalysis, setCostAnalysis] = useState<AzureCostItem[]>([]);
  const [blobFiles, setBlobFiles] = useState<AzureFile[]>([]);
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<"healthy" | "error" | "unknown">("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedResourceGroup, setSelectedResourceGroup] = useState("");
  const [selectedStorageAccount, setSelectedStorageAccount] = useState("");
  const [selectedContainer, setSelectedContainer] = useState("");

  // Form states
  const [vmForm, setVmForm] = useState({
    resource_group: "",
    vm_name: "",
    location: "",
    size: "Standard_B2s",
    image_publisher: "MicrosoftWindowsServer",
    image_offer: "WindowsServer",
    image_sku: "2019-Datacenter",
    admin_username: "",
    admin_password: "",
    network_interface_id: ""
  });

  const [appForm, setAppForm] = useState({
    resource_group: "",
    app_name: "",
    location: "",
    plan_tier: "Basic",
    plan_size: "B1",
    python_version: "",
    node_version: "",
    https_only: true
  });

  const { isOpen: isVMOOpen, onOpen: onVMTOpen, onClose: onVMClose } = useDisclosure();
  const { isOpen: isAppOpen, onOpen: onAppOpen, onClose: onAppClose } = useDisclosure();
  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/azure/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
      } else {
        setConnected(false);
        setHealthStatus("error");
      }
    } catch (error) {
      console.error("Health check failed:", error);
      setConnected(false);
      setHealthStatus("error");
    }
  };

  // Load Azure resources
  const loadResourceGroups = async () => {
    try {
      const response = await fetch("/api/azure/resource-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setResourceGroups(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load resource groups:", error);
    }
  };

  const loadVirtualMachines = async () => {
    try {
      const response = await fetch("/api/azure/virtual-machines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          resource_group: selectedResourceGroup,
          limit: 50
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setVirtualMachines(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load virtual machines:", error);
    }
  };

  const loadStorageAccounts = async () => {
    try {
      const response = await fetch("/api/azure/storage-accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          resource_group: selectedResourceGroup,
          limit: 50
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setStorageAccounts(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load storage accounts:", error);
    }
  };

  const loadAppServices = async () => {
    try {
      const response = await fetch("/api/azure/app-services", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          resource_group: selectedResourceGroup,
          limit: 50
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setAppServices(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load app services:", error);
    }
  };

  const loadCostAnalysis = async () => {
    try {
      const response = await fetch("/api/azure/costs/analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          timeframe: "LastMonth"
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCostAnalysis(data.data?.costs || []);
      }
    } catch (error) {
      console.error("Failed to load cost analysis:", error);
    }
  };

  const loadBlobFiles = async () => {
    if (!selectedStorageAccount || !selectedContainer) return;

    try {
      const response = await fetch("/api/azure/storage/files", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          storage_account: selectedStorageAccount,
          container_name: selectedContainer
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setBlobFiles(data.data || []);
      }
    } catch (error) {
      console.error("Failed to load blob files:", error);
    }
  };

  // Create virtual machine
  const createVirtualMachine = async () => {
    try {
      const response = await fetch("/api/azure/virtual-machines/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...vmForm,
          user_id: "current"
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Virtual machine creation initiated",
          status: "success",
          duration: 3000,
        });
        onVMClose();
        setVmForm({
          resource_group: "",
          vm_name: "",
          location: "",
          size: "Standard_B2s",
          image_publisher: "MicrosoftWindowsServer",
          image_offer: "WindowsServer",
          image_sku: "2019-Datacenter",
          admin_username: "",
          admin_password: "",
          network_interface_id: ""
        });
        loadVirtualMachines();
      }
    } catch (error) {
      console.error("Failed to create virtual machine:", error);
      toast({
        title: "Error",
        description: "Failed to create virtual machine",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Deploy app service
  const deployAppService = async () => {
    try {
      const response = await fetch("/api/azure/app-services/deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...appForm,
          user_id: "current"
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "App service deployment initiated",
          status: "success",
          duration: 3000,
        });
        onAppClose();
        setAppForm({
          resource_group: "",
          app_name: "",
          location: "",
          plan_tier: "Basic",
          plan_size: "B1",
          python_version: "",
          node_version: "",
          https_only: true
        });
        loadAppServices();
      }
    } catch (error) {
      console.error("Failed to deploy app service:", error);
      toast({
        title: "Error",
        description: "Failed to deploy app service",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredVMs = virtualMachines.filter((vm) =>
    vm.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    vm.resource_group.toLowerCase().includes(searchQuery.toLowerCase()) ||
    vm.status.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredStorage = storageAccounts.filter((storage) =>
    storage.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    storage.resource_group.toLowerCase().includes(searchQuery.toLowerCase()) ||
    storage.tier.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredApps = appServices.filter((app) =>
    app.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    app.resource_group.toLowerCase().includes(searchQuery.toLowerCase()) ||
    app.state.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const totalRG = resourceGroups.length;
  const totalVMs = virtualMachines.length;
  const runningVMs = virtualMachines.filter((vm) => vm.status === "Running").length;
  const totalStorage = storageAccounts.length;
  const totalApps = appServices.length;
  const runningApps = appServices.filter((app) => app.state === "Running").length;
  const totalCost = costAnalysis.reduce((sum, item) => sum + item.cost, 0);

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadResourceGroups();
      loadVirtualMachines();
      loadStorageAccounts();
      loadAppServices();
      loadCostAnalysis();
    }
  }, [connected, selectedResourceGroup]);

  useEffect(() => {
    if (selectedStorageAccount && selectedContainer) {
      loadBlobFiles();
    }
  }, [selectedStorageAccount, selectedContainer]);

  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case "running":
        return "green";
      case "stopped":
        return "red";
      case "starting":
        return "yellow";
      case "stopping":
        return "orange";
      case "creating":
        return "blue";
      case "deleting":
        return "red";
      default:
        return "gray";
    }
  };

  const getTierColor = (tier: string): string => {
    switch (tier?.toLowerCase()) {
      case "premium":
        return "purple";
      case "standard":
        return "blue";
      case "basic":
        return "green";
      default:
        return "gray";
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={CloudIcon} w={8} h={8} color="blue.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Microsoft Azure Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Cloud computing platform for infrastructure and services
              </Text>
            </VStack>
          </HStack>

          <HStack spacing={4}>
            <Badge
              colorScheme={healthStatus === "healthy" ? "green" : "red"}
              display="flex"
              alignItems="center"
            >
              {healthStatus === "healthy" ? (
                <CheckCircleIcon mr={1} />
              ) : (
                <WarningIcon mr={1} />
              )}
              {connected ? "Connected" : "Disconnected"}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RepeatIcon />}
              onClick={checkConnection}
            >
              Refresh Status
            </Button>
          </HStack>
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={CloudIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Azure</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Azure account to start managing cloud resources
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() =>
                    (window.location.href = "/api/integrations/azure/auth/start")
                  }
                >
                  Connect Azure Account
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Services Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Virtual Machines</StatLabel>
                    <StatNumber>{totalVMs}</StatNumber>
                    <StatHelpText>{runningVMs} running</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Storage Accounts</StatLabel>
                    <StatNumber>{totalStorage}</StatNumber>
                    <StatHelpText>Blob and file storage</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>App Services</StatLabel>
                    <StatNumber>{totalApps}</StatNumber>
                    <StatHelpText>{runningApps} running</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Monthly Cost</StatLabel>
                    <StatNumber>${totalCost.toFixed(2)}</StatNumber>
                    <StatHelpText>Last 30 days</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Resource Groups</Tab>
                <Tab>Virtual Machines</Tab>
                <Tab>Storage</Tab>
                <Tab>App Services</Tab>
                <Tab>Cost Analysis</Tab>
                <Tab>File Browser</Tab>
              </TabList>

              <TabPanels>
                {/* Resource Groups Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Location</Th>
                                <Th>Created</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {resourceGroups.map((rg) => (
                                <Tr key={rg.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={FolderIcon} color="blue.500" />
                                      <Text fontWeight="medium">{rg.name}</Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{rg.location}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(rg.created_at)}</Text>
                                  </Td>
                                  <Td>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      onClick={() => setSelectedResourceGroup(rg.name)}
                                    >
                                      View Resources
                                    </Button>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Virtual Machines Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search VMs..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Select
                        placeholder="Resource Group"
                        value={selectedResourceGroup}
                        onChange={(e) => setSelectedResourceGroup(e.target.value)}
                        width="200px"
                      >
                        <option value="">All Resource Groups</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>{rg.name}</option>
                        ))}
                      </Select>
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onVMTOpen}
                      >
                        Create VM
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Size</Th>
                                <Th>OS</Th>
                                <Th>Status</Th>
                                <Th>Resource Group</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredVMs.map((vm) => (
                                <Tr key={vm.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={ServerIcon} color="blue.500" />
                                      <Text fontWeight="medium">{vm.name}</Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{vm.size}</Text>
                                  </Td>
                                  <Td>
                                    <Badge colorScheme="gray" size="sm">
                                      {vm.os_type}
                                    </Badge>
                                  </Td>
                                  <Td>
                                    <Tag colorScheme={getStatusColor(vm.status)} size="sm">
                                      <TagLabel>{vm.status}</TagLabel>
                                    </Tag>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{vm.resource_group}</Text>
                                  </Td>
                                  <Td>
                                    <HStack>
                                      {vm.status === "Running" ? (
                                        <Button size="sm" variant="outline" leftIcon={<StopIcon />}>
                                          Stop
                                        </Button>
                                      ) : (
                                        <Button size="sm" variant="outline" leftIcon={<PlayIcon />}>
                                          Start
                                        </Button>
                                      )}
                                      <Button size="sm" variant="outline" leftIcon={<ViewIcon />}>
                                        Details
                                      </Button>
                                    </HStack>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Storage Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Type</Th>
                                <Th>Tier</Th>
                                <Th>Replication</Th>
                                <Th>Resource Group</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredStorage.map((storage) => (
                                <Tr key={storage.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={DatabaseIcon} color="blue.500" />
                                      <Text fontWeight="medium">{storage.name}</Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{storage.type}</Text>
                                  </Td>
                                  <Td>
                                    <Tag colorScheme={getTierColor(storage.tier)} size="sm">
                                      <TagLabel>{storage.tier}</TagLabel>
                                    </Tag>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{storage.replication}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{storage.resource_group}</Text>
                                  </Td>
                                  <Td>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      leftIcon={<ViewIcon />}
                                      onClick={() => setSelectedStorageAccount(storage.name)}
                                    >
                                      Browse
                                    </Button>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* App Services Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search apps..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onAppOpen}
                      >
                        Deploy App
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Runtime</Th>
                                <Th>State</Th>
                                <Th>Host Names</Th>
                                <Th>Resource Group</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredApps.map((app) => (
                                <Tr key={app.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={GlobeIcon} color="blue.500" />
                                      <Text fontWeight="medium">{app.name}</Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{app.runtime}</Text>
                                  </Td>
                                  <Td>
                                    <Tag colorScheme={getStatusColor(app.state)} size="sm">
                                      <TagLabel>{app.state}</TagLabel>
                                    </Tag>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{app.host_names[0]}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{app.resource_group}</Text>
                                  </Td>
                                  <Td>
                                    <HStack>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                        onClick={() => window.open(`https://${app.host_names[0]}`)}
                                      >
                                        Open
                                      </Button>
                                      <Button size="sm" variant="outline" leftIcon={<ViewIcon />}>
                                        Details
                                      </Button>
                                    </HStack>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Cost Analysis Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info">
                      <InfoIcon />
                      <Text>Cost analysis for the last billing period</Text>
                    </Alert>

                    <Card>
                      <CardBody>
                        <VStack spacing={4} align="stretch">
                          {costAnalysis.map((cost, index) => (
                            <HStack key={index} justify="space-between" p={3} borderWidth="1px" borderRadius="md">
                              <VStack align="start" spacing={1}>
                                <Text fontWeight="medium">{cost.service_name}</Text>
                                <Text fontSize="sm" color="gray.600">
                                  {cost.resource_group} • {cost.date}
                                </Text>
                              </VStack>
                              <Text fontSize="lg" fontWeight="bold" color="blue.500">
                                ${cost.cost.toFixed(2)}
                              </Text>
                            </HStack>
                          ))}
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* File Browser Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Storage Account"
                        value={selectedStorageAccount}
                        onChange={(e) => setSelectedStorageAccount(e.target.value)}
                        width="200px"
                      >
                        {storageAccounts.map((storage) => (
                          <option key={storage.id} value={storage.name}>{storage.name}</option>
                        ))}
                      </Select>
                      <Input
                        placeholder="Container name"
                        value={selectedContainer}
                        onChange={(e) => setSelectedContainer(e.target.value)}
                        width="200px"
                      />
                      <Button
                        colorScheme="blue"
                        onClick={loadBlobFiles}
                        disabled={!selectedStorageAccount || !selectedContainer}
                      >
                        Load Files
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Size</Th>
                                <Th>Type</Th>
                                <Th>Last Modified</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {blobFiles.map((file, index) => (
                                <Tr key={index}>
                                  <Td>
                                    <HStack>
                                      <Icon as={CubeIcon} color="blue.500" />
                                      <Text fontWeight="medium">{file.name}</Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatFileSize(file.size)}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{file.content_type}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{formatDate(file.last_modified)}</Text>
                                  </Td>
                                  <Td>
                                    <HStack>
                                      <Button size="sm" variant="outline">
                                        Download
                                      </Button>
                                      <Button size="sm" variant="outline">
                                        Delete
                                      </Button>
                                    </HStack>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create VM Modal */}
            <Modal isOpen={isVMOOpen} onClose={onVMClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Virtual Machine</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Resource Group</FormLabel>
                      <Select
                        value={vmForm.resource_group}
                        onChange={(e) => setVmForm({ ...vmForm, resource_group: e.target.value })}
                      >
                        <option value="">Select Resource Group</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>{rg.name}</option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>VM Name</FormLabel>
                      <Input
                        placeholder="my-vm"
                        value={vmForm.vm_name}
                        onChange={(e) => setVmForm({ ...vmForm, vm_name: e.target.value })}
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Location</FormLabel>
                      <Select
                        value={vmForm.location}
                        onChange={(e) => setVmForm({ ...vmForm, location: e.target.value })}
                      >
                        <option value="">Select Location</option>
                        <option value="East US">East US</option>
                        <option value="West US">West US</option>
                        <option value="West Europe">West Europe</option>
                        <option value="Southeast Asia">Southeast Asia</option>
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>VM Size</FormLabel>
                      <Select
                        value={vmForm.size}
                        onChange={(e) => setVmForm({ ...vmForm, size: e.target.value })}
                      >
                        <option value="Standard_B1s">Standard_B1s (1 vCPU, 1 GB RAM)</option>
                        <option value="Standard_B2s">Standard_B2s (1 vCPU, 2 GB RAM)</option>
                        <option value="Standard_B2ms">Standard_B2ms (2 vCPU, 8 GB RAM)</option>
                        <option value="Standard_D2s_v3">Standard_D2s_v3 (2 vCPU, 8 GB RAM)</option>
                        <option value="Standard_D4s_v3">Standard_D4s_v3 (4 vCPU, 16 GB RAM)</option>
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Admin Username</FormLabel>
                      <Input
                        placeholder="azureuser"
                        value={vmForm.admin_username}
                        onChange={(e) => setVmForm({ ...vmForm, admin_username: e.target.value })}
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Admin Password</FormLabel>
                      <Input
                        type="password"
                        placeholder="SecurePassword123!"
                        value={vmForm.admin_password}
                        onChange={(e) => setVmForm({ ...vmForm, admin_password: e.target.value })}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onVMClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createVirtualMachine}
                    disabled={!vmForm.resource_group || !vmForm.vm_name || !vmForm.admin_username || !vmForm.admin_password}
                  >
                    Create VM
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Deploy App Service Modal */}
            <Modal isOpen={isAppOpen} onClose={onAppClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Deploy App Service</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Resource Group</FormLabel>
                      <Select
                        value={appForm.resource_group}
                        onChange={(e) => setAppForm({ ...appForm, resource_group: e.target.value })}
                      >
                        <option value="">Select Resource Group</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>{rg.name}</option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>App Name</FormLabel>
                      <Input
                        placeholder="my-app"
                        value={appForm.app_name}
                        onChange={(e) => setAppForm({ ...appForm, app_name: e.target.value })}
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Location</FormLabel>
                      <Select
                        value={appForm.location}
                        onChange={(e) => setAppForm({ ...appForm, location: e.target.value })}
                      >
                        <option value="">Select Location</option>
                        <option value="East US">East US</option>
                        <option value="West US">West US</option>
                        <option value="West Europe">West Europe</option>
                        <option value="Southeast Asia">Southeast Asia</option>
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Runtime</FormLabel>
                      <RadioGroup
                        value={appForm.python_version ? "python" : appForm.node_version ? "node" : ""}
                        onChange={(value) => {
                          if (value === "python") {
                            setAppForm({ ...appForm, python_version: "3.9", node_version: "" });
                          } else if (value === "node") {
                            setAppForm({ ...appForm, node_version: "18", python_version: "" });
                          }
                        }}
                      >
                        <Stack direction="row">
                          <Radio value="python">Python</Radio>
                          <Radio value="node">Node.js</Radio>
                        </Stack>
                      </RadioGroup>
                    </FormControl>

                    <FormControl>
                      <FormLabel>HTTPS Only</FormLabel>
                      <Switch
                        isChecked={appForm.https_only}
                        onChange={(e) => setAppForm({ ...appForm, https_only: e.target.checked })}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onAppClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={deployAppService}
                    disabled={!appForm.resource_group || !appForm.app_name || !appForm.location}
                  >
                    Deploy App
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}
      </VStack>
    </Box>
  );
};

export default AzureIntegration;