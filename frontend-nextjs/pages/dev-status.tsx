import React, { useState, useEffect, useCallback } from "react";
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
  Progress,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
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
  Code,
  IconButton,
  Tooltip,
} from "@chakra-ui/react";
import {
  FiServer,
  FiCpu,
  FiDatabase,
  FiGitBranch,
  FiPackage,
  FiShield,
  FiMonitor,
  FiRefreshCw,
  FiPlay,
  FiStopCircle,
  FiCheckCircle,
  FiXCircle,
  FiAlertTriangle,
  FiInfo,
  FiTerminal,
  FiFolder,
} from "react-icons/fi";

// Tauri imports for desktop functionality
const { invoke } =
  typeof window !== "undefined" ? require("@tauri-apps/api") : { invoke: null };

const DevStatus = () => {
  const toast = useToast();
  const [systemStatus, setSystemStatus] = useState<any>(null);
  const [servicesStatus, setServicesStatus] = useState<any>({});
  const [buildStatus, setBuildStatus] = useState<any>({});
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  // Load system status
  const loadSystemStatus = useCallback(async () => {
    setIsRefreshing(true);
    try {
      // Load system info if available
      if (invoke) {
        const systemInfo = await invoke("get_system_info");
        setSystemStatus(systemInfo);
      }

      // Simulate service status checks
      const services = {
        frontend: await checkService("Frontend", "http://localhost:3000"),
        backend: await checkService("Backend", "http://localhost:3001"),
        database: await checkService("Database", null, true), // Assume database is running
        desktop: await checkService("Desktop App", null, true), // Assume desktop is running
      };

      setServicesStatus(services);

      // Check build status
      const buildInfo = {
        lastBuild: new Date(Date.now() - 300000), // 5 minutes ago
        buildTime: "2m 15s",
        status: "success",
        tests: {
          total: 156,
          passed: 152,
          failed: 4,
          coverage: "87%",
        },
      };
      setBuildStatus(buildInfo);

      setLastUpdate(new Date());
    } catch (error) {
      console.error("Failed to load system status:", error);
      toast({
        title: "Error",
        description: "Failed to load system status",
        status: "error",
        duration: 3000,
      });
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  // Simulate service health check
  const checkService = async (
    name: string,
    url: string | null,
    isRunning: boolean = false,
  ) => {
    if (url) {
      try {
        const response = await fetch(url, { method: "HEAD" });
        return {
          name,
          status: response.ok ? "healthy" : "unhealthy",
          responseTime: Math.random() * 100 + 50, // ms
          lastCheck: new Date(),
        } as const;
      } catch (error) {
        return {
          name,
          status: "unhealthy",
          responseTime: null,
          lastCheck: new Date(),
          error: (error as Error).message,
        } as const;
      }
    } else {
      return {
        name,
        status: isRunning ? "healthy" : "unknown",
        responseTime: null,
        lastCheck: new Date(),
      } as const;
    }
  };

  // Get status color
  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case "healthy":
      case "success":
        return "green";
      case "warning":
      case "degraded":
        return "yellow";
      case "unhealthy":
      case "error":
      case "failed":
        return "red";
      default:
        return "gray";
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case "healthy":
      case "success":
        return FiCheckCircle;
      case "warning":
      case "degraded":
        return FiAlertTriangle;
      case "unhealthy":
      case "error":
      case "failed":
        return FiXCircle;
      default:
        return FiInfo;
    }
  };

  useEffect(() => {
    loadSystemStatus();
    const interval = setInterval(loadSystemStatus, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, [loadSystemStatus]);

  const serviceList = Object.values(servicesStatus) as Array<{
    name: string;
    status: string;
    responseTime: number | null;
    lastCheck: Date;
    error?: string;
  }>;

  return (
    <Box p={6} maxW="1200px" mx="auto">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Flex align="center" justify="space-between">
          <Box>
            <Heading size="xl" mb={2}>
              Development Status
            </Heading>
            <Text color="gray.600">
              Real-time monitoring of development environment and services
            </Text>
          </Box>
          <Button
            leftIcon={<FiRefreshCw />}
            onClick={loadSystemStatus}
            isLoading={isRefreshing}
            colorScheme="blue"
          >
            Refresh
          </Button>
        </Flex>

        {/* System Overview */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Platform</StatLabel>
                <StatNumber fontSize="xl">
                  {systemStatus?.platform
                    ? systemStatus.platform.toUpperCase()
                    : "Web"}
                </StatNumber>
                <StatHelpText>
                  <StatArrow type="increase" />
                  {systemStatus?.architecture || "Unknown"}
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Services</StatLabel>
                <StatNumber fontSize="xl">
                  {serviceList.filter((s) => s.status === "healthy").length}/
                  {serviceList.length}
                </StatNumber>
                <StatHelpText>Healthy Services</StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Test Coverage</StatLabel>
                <StatNumber fontSize="xl">
                  {buildStatus.tests?.coverage || "0%"}
                </StatNumber>
                <StatHelpText>
                  {buildStatus.tests?.passed}/{buildStatus.tests?.total} tests
                  passed
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Last Update</StatLabel>
                <StatNumber fontSize="xl">
                  {lastUpdate.toLocaleTimeString()}
                </StatNumber>
                <StatHelpText>{lastUpdate.toLocaleDateString()}</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        <Tabs colorScheme="blue">
          <TabList>
            <Tab>
              <Icon as={FiServer} mr={2} />
              Services
            </Tab>
            <Tab>
              <Icon as={FiPackage} mr={2} />
              Build Status
            </Tab>
            <Tab>
              <Icon as={FiCpu} mr={2} />
              System Info
            </Tab>
          </TabList>

          <TabPanels>
            {/* Services Panel */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {serviceList.map((service: any, index) => (
                    <Card
                      key={index}
                      borderLeft="4px"
                      borderLeftColor={getStatusColor(service.status)}
                    >
                      <CardBody>
                        <HStack justify="space-between" mb={3}>
                          <Heading size="md">{service.name}</Heading>
                          <Icon
                            as={getStatusIcon(service.status)}
                            color={`${getStatusColor(service.status)}.500`}
                          />
                        </HStack>
                        <VStack align="stretch" spacing={2}>
                          <HStack justify="space-between">
                            <Text color="gray.600">Status:</Text>
                            <Badge colorScheme={getStatusColor(service.status)}>
                              {service.status}
                            </Badge>
                          </HStack>
                          {service.responseTime && (
                            <HStack justify="space-between">
                              <Text color="gray.600">Response Time:</Text>
                              <Text fontWeight="medium">
                                {service.responseTime.toFixed(0)}ms
                              </Text>
                            </HStack>
                          )}
                          <HStack justify="space-between">
                            <Text color="gray.600">Last Check:</Text>
                            <Text fontSize="sm">
                              {service.lastCheck.toLocaleTimeString()}
                            </Text>
                          </HStack>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>

                {/* Service Health Summary */}
                <Card>
                  <CardHeader>
                    <Heading size="md">Service Health Summary</Heading>
                  </CardHeader>
                  <CardBody>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Service</Th>
                          <Th>Status</Th>
                          <Th>Response Time</Th>
                          <Th>Last Check</Th>
                          <Th>Actions</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {serviceList.map((service: any, index) => (
                          <Tr key={index}>
                            <Td fontWeight="medium">{service.name}</Td>
                            <Td>
                              <Badge
                                colorScheme={getStatusColor(service.status)}
                              >
                                {service.status}
                              </Badge>
                            </Td>
                            <Td>
                              {service.responseTime
                                ? `${service.responseTime.toFixed(0)}ms`
                                : "N/A"}
                            </Td>
                            <Td>{service.lastCheck.toLocaleTimeString()}</Td>
                            <Td>
                              <Button size="sm" variant="outline">
                                Restart
                              </Button>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* Build Status Panel */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                  <Card>
                    <CardHeader>
                      <Heading size="md">Last Build</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack align="stretch" spacing={4}>
                        <HStack justify="space-between">
                          <Text color="gray.600">Status:</Text>
                          <Badge
                            colorScheme={getStatusColor(buildStatus.status)}
                            size="lg"
                          >
                            {buildStatus.status}
                          </Badge>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Time:</Text>
                          <Text fontWeight="medium">
                            {buildStatus.buildTime}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Completed:</Text>
                          <Text fontSize="sm">
                            {buildStatus.lastBuild
                              ? buildStatus.lastBuild.toLocaleString()
                              : "Never"}
                          </Text>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader>
                      <Heading size="md">Test Results</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack align="stretch" spacing={4}>
                        <HStack justify="space-between">
                          <Text color="gray.600">Total Tests:</Text>
                          <Text fontWeight="medium">
                            {buildStatus.tests?.total}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Passed:</Text>
                          <Text fontWeight="medium" color="green.500">
                            {buildStatus.tests?.passed}
                          </Text>
                        </HStack>
                        <HStack justify="space-between">
                          <Text color="gray.600">Failed:</Text>
                          <Text fontWeight="medium" color="red.500">
                            {buildStatus.tests?.failed}
                          </Text>
                        </HStack>
                        <Progress
                          value={
                            (buildStatus.tests?.passed /
                              buildStatus.tests?.total) *
                              100 || 0
                          }
                          colorScheme="green"
                          size="sm"
                          borderRadius="md"
                        />
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>

                <Card>
                  <CardHeader>
                    <Heading size="md">Build Actions</Heading>
                  </CardHeader>
                  <CardBody>
                    <HStack spacing={4}>
                      <Button leftIcon={<FiPlay />} colorScheme="green">
                        Start Build
                      </Button>
                      <Button
                        leftIcon={<FiStopCircle />}
                        colorScheme="red"
                        variant="outline"
                      >
                        Stop Build
                      </Button>
                      <Button
                        leftIcon={<FiPackage />}
                        colorScheme="blue"
                        variant="outline"
                      >
                        Package Release
                      </Button>
                      <Button
                        leftIcon={<FiTerminal />}
                        colorScheme="purple"
                        variant="outline"
                      >
                        Run Tests
                      </Button>
                    </HStack>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* System Info Panel */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                {systemStatus ? (
                  <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                    <Card>
                      <CardHeader>
                        <Heading size="md">Platform Information</Heading>
                      </CardHeader>
                      <CardBody>
                        <VStack align="stretch" spacing={3}>
                          {Object.entries(systemStatus).map(([key, value]) => (
                            <HStack key={key} justify="space-between">
                              <Text
                                fontWeight="medium"
                                textTransform="capitalize"
                              >
                                {key.replace(/_/g, " ")}:
                              </Text>
                              <Text>{String(value)}</Text>
                            </HStack>
                          ))}
                        </VStack>
                      </CardBody>
                    </Card>

                    <Card>
                      <CardHeader>
                        <Heading size="md">Capabilities</Heading>
                      </CardHeader>
                      <CardBody>
                        <VStack align="stretch" spacing={2}>
                          {systemStatus.features &&
                            Object.entries(systemStatus.features).map(
                              ([feature, enabled]) => (
                                <HStack key={feature} justify="space-between">
                                  <Text>
                                    {feature
                                      .split("_")
                                      .map(
                                        (word) =>
                                          word.charAt(0).toUpperCase() +
                                          word.slice(1),
                                      )
                                      .join(" ")}
                                  </Text>
                                  <Badge
                                    colorScheme={enabled ? "green" : "red"}
                                  >
                                    {enabled ? "Enabled" : "Disabled"}
                                  </Badge>
                                </HStack>
                              ),
                            )}
                        </VStack>
                      </CardBody>
                    </Card>
                  </SimpleGrid>
                ) : (
                  <Alert status="info">
                    <AlertIcon />
                    <Box>
                      <AlertTitle>Web Environment</AlertTitle>
                      <AlertDescription>
                        System information is only available in the desktop
                        application.
                      </AlertDescription>
                    </Box>
                  </Alert>
                )}

                {/* Development Tools Quick Access */}
                <Card>
                  <CardHeader>
                    <Heading size="md">Quick Actions</Heading>
                  </CardHeader>
                  <CardBody>
                    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
                      <Button
                        leftIcon={<FiTerminal />}
                        colorScheme="blue"
                        variant="outline"
                      >
                        Dev Tools
                      </Button>
                      <Button
                        leftIcon={<FiFolder />}
                        colorScheme="green"
                        variant="outline"
                      >
                        File Explorer
                      </Button>
                      <Button
                        leftIcon={<FiDatabase />}
                        colorScheme="purple"
                        variant="outline"
                      >
                        Database
                      </Button>
                      <Button
                        leftIcon={<FiGitBranch />}
                        colorScheme="orange"
                        variant="outline"
                      >
                        Git Status
                      </Button>
                    </SimpleGrid>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default DevStatus;
