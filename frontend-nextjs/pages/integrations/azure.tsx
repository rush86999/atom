/**
 * Azure Integration Page
 * Complete Microsoft Azure cloud platform integration
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
  Divider,
  useColorModeValue,
  Stack,
  Flex,
  Spacer,
  Input,
  Select,
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
  FormControl,
  FormLabel,
  Textarea,
  useDisclosure,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
  Tag,
  TagLabel,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Avatar,
  Spinner,
  Alert,
  AlertIcon,
} from "@chakra-ui/react";
import {
  SunIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  SettingsIcon,
  RepeatIcon,
  StarIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ChatIcon,
  CloudIcon,
  ServerIcon,
  DatabaseIcon,
  SettingsIcon as Settings,
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

interface AzureSubscription {
  id: string;
  subscriptionId: string;
  displayName: string;
  state: string;
  tenantId: string;
  policies?: any[];
}

const AzureIntegration: React.FC = () => {
  const [resourceGroups, setResourceGroups] = useState<AzureResourceGroup[]>([]);
  const [virtualMachines, setVirtualMachines] = useState<AzureVirtualMachine[]>([]);
  const [storageAccounts, setStorageAccounts] = useState<AzureStorageAccount[]>([]);
  const [appServices, setAppServices] = useState<AzureAppService[]>([]);
  const [subscriptions, setSubscriptions] = useState<AzureSubscription[]>([]);
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedResourceGroup, setSelectedResourceGroup] = useState("");
  const [selectedSubscription, setSelectedSubscription] = useState("");
  const [selectedLocation, setSelectedLocation] = useState("");

  // Form states
  const [vmForm, setVmForm] = useState({
    resource_group: "",
    vm_name: "",
    location: "East US",
    size: "Standard_B2s",
    image_publisher: "MicrosoftWindowsServer",
    image_offer: "WindowsServer",
    image_sku: "2019-Datacenter",
    admin_username: "",
    admin_password: "",
    network_interface_id: "",
  });

  const [appForm, setAppForm] = useState({
    resource_group: "",
    app_name: "",
    location: "East US",
    plan_tier: "Basic",
    plan_size: "B1",
    runtime: "NODE",
    https_only: true,
  });

  const [storageForm, setStorageForm] = useState({
    resource_group: "",
    storage_name: "",
    location: "East US",
    account_type: "Standard_LRS",
    tier: "Standard",
  });

  const {
    isOpen: isVMOOpen,
    onOpen: onVMTOpen,
    onClose: onVMClose,
  } = useDisclosure();
  const {
    isOpen: isAppOpen,
    onOpen: onAppOpen,
    onClose: onAppClose,
  } = useDisclosure();
  const {
    isOpen: isStorageOpen,
    onOpen: onStorageOpen,
    onClose: onStorageClose,
  } = useDisclosure();

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
        loadSubscriptions();
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
  const loadSubscriptions = async () => {
    try {
      const response = await fetch("/api/integrations/azure/subscriptions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setSubscriptions(data.data?.subscriptions || []);
        if (data.data?.subscriptions?.length > 0) {
          setSelectedSubscription(data.data.subscriptions[0].subscriptionId);
        }
      }
    } catch (error) {
      console.error("Failed to load subscriptions:", error);
    }
  };

  const loadResourceGroups = async () => {
    try {
      const response = await fetch("/api/integrations/azure/resource-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          subscription_id: selectedSubscription,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setResourceGroups(data.data?.resourceGroups || []);
      }
    } catch (error) {
      console.error("Failed to load resource groups:", error);
    }
  };

  const loadVirtualMachines = async () => {
    try {
      const response = await fetch("/api/integrations/azure/virtual-machines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          subscription_id: selectedSubscription,
          resource_group: selectedResourceGroup,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setVirtualMachines(data.data?.virtualMachines || []);
      }
    } catch (error) {
      console.error("Failed to load virtual machines:", error);
    }
  };

  const loadStorageAccounts = async () => {
    try {
      const response = await fetch("/api/integrations/azure/storage-accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          subscription_id: selectedSubscription,
          resource_group: selectedResourceGroup,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setStorageAccounts(data.data?.storageAccounts || []);
      }
    } catch (error) {
      console.error("Failed to load storage accounts:", error);
    }
  };

  const loadAppServices = async () => {
    try {
      const response = await fetch("/api/integrations/azure/app-services", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          subscription_id: selectedSubscription,
          resource_group: selectedResourceGroup,
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setAppServices(data.data?.appServices || []);
      }
    } catch (error) {
      console.error("Failed to load app services:", error);
    }
  };

  // Create resources
  const createVirtualMachine = async () => {
    try {
      const response = await fetch("/api/integrations/azure/virtual-machines/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...vmForm,
          user_id: "current",
          subscription_id: selectedSubscription,
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
          location: "East US",
          size: "Standard_B2s",
          image_publisher: "MicrosoftWindowsServer",
          image_offer: "WindowsServer",
          image_sku: "2019-Datacenter",
          admin_username: "",
          admin_password: "",
          network_interface_id: "",
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

  const deployAppService = async () => {
    try {
      const response = await fetch("/api/integrations/azure/app-services/deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...appForm,
          user_id: "current",
          subscription_id: selectedSubscription,
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
          location: "East US",
          plan_tier: "Basic",
          plan_size: "B1",
          runtime: "NODE",
          https_only: true,
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

  const createStorageAccount = async () => {
    try {
      const response = await fetch("/api/integrations/azure/storage-accounts/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...storageForm,
          user_id: "current",
          subscription_id: selectedSubscription,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Storage account creation initiated",
          status: "success",
          duration: 3000,
        });
        onStorageClose();
        setStorageForm({
          resource_group: "",
          storage_name: "",
          location: "East US",
          account_type: "Standard_LRS",
          tier: "Standard",
        });
        loadStorageAccounts();
      }
    } catch (error) {
      console.error("Failed to create storage account:", error);
      toast({
        title: "Error",
        description: "Failed to create storage account",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredVMs = virtualMachines.filter(
    (vm) =>
      vm.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      vm.resource_group.toLowerCase().includes(searchQuery.toLowerCase()) ||
      vm.status.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredStorage = storageAccounts.filter(
    (storage) =>
      storage.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      storage.resource_group.toLowerCase().includes(searchQuery.toLowerCase()) ||
      storage.tier.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredApps = appServices.filter(
    (app) =>
      app.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.resource_group.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.state.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Stats calculations
  const totalRG = resourceGroups.length;
  const totalVMs = virtualMachines.length;
  const runningVMs = virtualMachines.filter(
    (vm) => vm.status.toLowerCase() === "running",
  ).length;
  const totalStorage = storageAccounts.length;
  const totalApps = appServices.length;
  const runningApps = appServices.filter(
    (app) => app.state.toLowerCase() === "running",
  ).length;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected && selectedSubscription) {
      loadResourceGroups();
      loadVirtualMachines();
      loadStorageAccounts();
      loadAppServices();
    }
  }, [connected, selectedSubscription, selectedResourceGroup]);

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

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SunIcon} w={8} h={8} color="blue.500" />
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
                <WarningTwoIcon mr={1} />
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

          {subscriptions.length > 0 && (
            <HStack spacing={4}>
              <Select
                placeholder="Select Subscription"
                value={selectedSubscription}
                onChange={(e) => setSelectedSubscription(e.target.value)}
                width="300px"
              >
                {subscriptions.map((sub) => (
                  <option key={sub.subscriptionId} value={sub.subscriptionId}>
                    {sub.displayName} ({sub.state})
                  </option>
                ))}
              </Select>
            </HStack>
          )}
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={SunIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Azure</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Azure account to start managing cloud resources
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/azure/auth/start")
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
                    <StatLabel>Resource Groups</StatLabel>
                    <StatNumber>{totalRG}</StatNumber>
                    <StatHelpText>Resource organization</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Virtual Machines</Tab>
                <Tab>App Services</Tab>
                <Tab>Storage</Tab>
                <Tab>Resource Groups</Tab>
              </TabList>

              <TabPanels>
                {/* Virtual Machines Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Resource Group"
                        value={selectedResourceGroup}
                        onChange={(e) =>
                          setSelectedResourceGroup(e.target.value)
                        }
                        width="200px"
                      >
                        <option value="">All Resource Groups</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>
                            {rg.name}
                          </option>
                        ))}
                      </Select>
                      <Input
                        placeholder="Search VMs..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
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
                                <Th>IP Address</Th>
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
                                    <Tag
                                      colorScheme={getStatusColor(vm.status)}
                                      size="sm"
                                    >
                                      <TagLabel>{vm.status}</TagLabel>
                                    </Tag>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">
                                      {vm.resource_group}
                                    </Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{vm.public_ip || "N/A"}</Text>
                                  </Td>
                                  <Td>
                                    <HStack>
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

                {/* App Services Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Resource Group"
                        value={selectedResourceGroup}
                        onChange={(e) =>
                          setSelectedResourceGroup(e.target.value)
                        }
                        width="200px"
                      >
                        <option value="">All Resource Groups</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>
                            {rg.name}
                          </option>
                        ))}
                      </Select>
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
                                <Th>HTTPS Only</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredApps.map((app) => (
                                <Tr key={app.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={SettingsIcon} color="blue.500" />
                                      <Text fontWeight="medium">
                                        {app.name}
                                      </Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{app.runtime}</Text>
                                  </Td>
                                  <Td>
                                    <Tag
                                      colorScheme={getStatusColor(app.state)}
                                      size="sm"
                                    >
                                      <TagLabel>{app.state}</TagLabel>
                                    </Tag>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">
                                      {app.host_names[0]}
                                    </Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">
                                      {app.resource_group}
                                    </Text>
                                  </Td>
                                  <Td>
                                    <Badge
                                      colorScheme={app.https_only ? "green" : "red"}
                                      size="sm"
                                    >
                                      {app.https_only ? "Enabled" : "Disabled"}
                                    </Badge>
                                  </Td>
                                  <Td>
                                    <HStack>
                                      <Button size="sm" variant="outline" leftIcon={<ViewIcon />}>
                                        Details
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        onClick={() =>
                                          window.open(
                                            `https://${app.host_names[0]}`,
                                          )
                                        }
                                      >
                                        Open
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
                    <HStack spacing={4}>
                      <Select
                        placeholder="Resource Group"
                        value={selectedResourceGroup}
                        onChange={(e) =>
                          setSelectedResourceGroup(e.target.value)
                        }
                        width="200px"
                      >
                        <option value="">All Resource Groups</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>
                            {rg.name}
                          </option>
                        ))}
                      </Select>
                      <Input
                        placeholder="Search storage..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onStorageOpen}
                      >
                        Create Storage
                      </Button>
                    </HStack>

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
                                <Th>Location</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {filteredStorage.map((storage) => (
                                <Tr key={storage.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={DatabaseIcon} color="blue.500" />
                                      <Text fontWeight="medium">
                                        {storage.name}
                                      </Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{storage.type}</Text>
                                  </Td>
                                  <Td>
                                    <Tag
                                      colorScheme={getTierColor(storage.tier)}
                                      size="sm"
                                    >
                                      <TagLabel>{storage.tier}</TagLabel>
                                    </Tag>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">
                                      {storage.replication}
                                    </Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">
                                      {storage.resource_group}
                                    </Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{storage.location}</Text>
                                  </Td>
                                  <Td>
                                    <HStack>
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

                {/* Resource Groups Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search resource groups..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Location</Th>
                                <Th>Created</Th>
                                <Th>Tags</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {resourceGroups
                                .filter(rg =>
                                  rg.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                                  rg.location.toLowerCase().includes(searchQuery.toLowerCase())
                                )
                                .map((rg) => (
                                <Tr key={rg.id}>
                                  <Td>
                                    <HStack>
                                      <Icon as={CloudIcon} color="blue.500" />
                                      <Text fontWeight="medium">{rg.name}</Text>
                                    </HStack>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">{rg.location}</Text>
                                  </Td>
                                  <Td>
                                    <Text fontSize="sm">
                                      {formatDate(rg.created_at)}
                                    </Text>
                                  </Td>
                                  <Td>
                                    <HStack wrap="wrap">
                                      {Object.entries(rg.tags).map(([key, value]) => (
                                        <Tag key={key} size="sm" colorScheme="gray">
                                          {key}: {value}
                                        </Tag>
                                      ))}
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
                        onChange={(e) =>
                          setVmForm({
                            ...vmForm,
                            resource_group: e.target.value,
                          })
                        }
                      >
                        <option value="">Select Resource Group</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>
                            {rg.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>VM Name</FormLabel>
                      <Input
                        placeholder="my-vm"
                        value={vmForm.vm_name}
                        onChange={(e) =>
                          setVmForm({ ...vmForm, vm_name: e.target.value })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Location</FormLabel>
                      <Select
                        value={vmForm.location}
                        onChange={(e) =>
                          setVmForm({ ...vmForm, location: e.target.value })
                        }
                      >
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
                        onChange={(e) =>
                          setVmForm({ ...vmForm, size: e.target.value })
                        }
                      >
                        <option value="Standard_B1s">
                          Standard_B1s (1 vCPU, 1 GB RAM)
                        </option>
                        <option value="Standard_B2s">
                          Standard_B2s (1 vCPU, 2 GB RAM)
                        </option>
                        <option value="Standard_B2ms">
                          Standard_B2ms (2 vCPU, 8 GB RAM)
                        </option>
                        <option value="Standard_D2s_v3">
                          Standard_D2s_v3 (2 vCPU, 8 GB RAM)
                        </option>
                        <option value="Standard_D4s_v3">
                          Standard_D4s_v3 (4 vCPU, 16 GB RAM)
                        </option>
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Admin Username</FormLabel>
                      <Input
                        placeholder="azureuser"
                        value={vmForm.admin_username}
                        onChange={(e) =>
                          setVmForm({
                            ...vmForm,
                            admin_username: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Admin Password</FormLabel>
                      <Input
                        type="password"
                        placeholder="SecurePassword123!"
                        value={vmForm.admin_password}
                        onChange={(e) =>
                          setVmForm({
                            ...vmForm,
                            admin_password: e.target.value,
                          })
                        }
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
                    disabled={
                      !vmForm.resource_group ||
                      !vmForm.vm_name ||
                      !vmForm.admin_username ||
                      !vmForm.admin_password
                    }
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
                        onChange={(e) =>
                          setAppForm({
                            ...appForm,
                            resource_group: e.target.value,
                          })
                        }
                      >
                        <option value="">Select Resource Group</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>
                            {rg.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>App Name</FormLabel>
                      <Input
                        placeholder="my-app"
                        value={appForm.app_name}
                        onChange={(e) =>
                          setAppForm({ ...appForm, app_name: e.target.value })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Location</FormLabel>
                      <Select
                        value={appForm.location}
                        onChange={(e) =>
                          setAppForm({ ...appForm, location: e.target.value })
                        }
                      >
                        <option value="East US">East US</option>
                        <option value="West US">West US</option>
                        <option value="West Europe">West Europe</option>
                        <option value="Southeast Asia">Southeast Asia</option>
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Runtime</FormLabel>
                      <Select
                        value={appForm.runtime}
                        onChange={(e) =>
                          setAppForm({ ...appForm, runtime: e.target.value })
                        }
                      >
                        <option value="NODE">Node.js</option>
                        <option value="PYTHON">Python</option>
                        <option value="JAVA">Java</option>
                        <option value="DOTNETCORE">.NET Core</option>
                      </Select>
                    </FormControl>

                    <FormControl>
                      <FormLabel>HTTPS Only</FormLabel>
                      <Input
                        type="checkbox"
                        checked={appForm.https_only}
                        onChange={(e) =>
                          setAppForm({
                            ...appForm,
                            https_only: e.target.checked,
                          })
                        }
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
                    disabled={
                      !appForm.resource_group ||
                      !appForm.app_name ||
                      !appForm.location
                    }
                  >
                    Deploy App
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Storage Account Modal */}
            <Modal isOpen={isStorageOpen} onClose={onStorageClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Storage Account</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Resource Group</FormLabel>
                      <Select
                        value={storageForm.resource_group}
                        onChange={(e) =>
                          setStorageForm({
                            ...storageForm,
                            resource_group: e.target.value,
                          })
                        }
                      >
                        <option value="">Select Resource Group</option>
                        {resourceGroups.map((rg) => (
                          <option key={rg.id} value={rg.name}>
                            {rg.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Storage Account Name</FormLabel>
                      <Input
                        placeholder="mystorageaccount"
                        value={storageForm.storage_name}
                        onChange={(e) =>
                          setStorageForm({
                            ...storageForm,
                            storage_name: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Location</FormLabel>
                      <Select
                        value={storageForm.location}
                        onChange={(e) =>
                          setStorageForm({
                            ...storageForm,
                            location: e.target.value,
                          })
                        }
                      >
                        <option value="East US">East US</option>
                        <option value="West US">West US</option>
                        <option value="West Europe">West Europe</option>
                        <option value="Southeast Asia">Southeast Asia</option>
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Account Type</FormLabel>
                      <Select
                        value={storageForm.account_type}
                        onChange={(e) =>
                          setStorageForm({
                            ...storageForm,
                            account_type: e.target.value,
                          })
                        }
                      >
                        <option value="Standard_LRS">Standard LRS</option>
                        <option value="Standard_ZRS">Standard ZRS</option>
                        <option value="Standard_GRS">Standard GRS</option>
                        <option value="Premium_LRS">Premium LRS</option>
                      </Select>
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Tier</FormLabel>
                      <Select
                        value={storageForm.tier}
                        onChange={(e) =>
                          setStorageForm({
                            ...storageForm,
                            tier: e.target.value,
                          })
                        }
                      >
                        <option value="Standard">Standard</option>
                        <option value="Premium">Premium</option>
                      </Select>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onStorageClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createStorageAccount}
                    disabled={
                      !storageForm.resource_group ||
                      !storageForm.storage_name ||
                      !storageForm.location
                    }
                  >
                    Create Storage
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