import React, { useState, useEffect } from "react";
import {
  Box,
  VStack,
  HStack,
  Text,
  Card,
  CardBody,
  Badge,
  Icon,
  useColorModeValue,
  SimpleGrid,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Button,
  Spinner,
  Tooltip,
} from "@chakra-ui/react";
import {
  CheckCircleIcon,
  WarningTwoIcon,
  TimeIcon,
  SettingsIcon,
  ExternalLinkIcon,
  RepeatIcon,
} from "@chakra-ui/icons";

interface IntegrationHealth {
  id: string;
  name: string;
  status: "healthy" | "warning" | "error" | "unknown";
  lastSync?: string;
  responseTime?: number;
  errorCount?: number;
  connected: boolean;
  enabled: boolean;
  category: string;
  endpoints: {
    health: string;
    profile?: string;
    resources?: string;
  };
}

interface IntegrationHealthDashboardProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
  showDetails?: boolean;
}

const IntegrationHealthDashboard: React.FC<IntegrationHealthDashboardProps> = ({
  autoRefresh = true,
  refreshInterval = 30000, // 30 seconds
  showDetails = true,
}) => {
  const [integrations, setIntegrations] = useState<IntegrationHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.600");

  const integrationList: Omit<IntegrationHealth, "status" | "lastSync" | "responseTime" | "errorCount">[] = [
    {
      id: "github",
      name: "GitHub",
      connected: false,
      enabled: true,
      category: "development",
      endpoints: {
        health: "/api/integrations/github/health",
        profile: "/api/integrations/github/profile",
        resources: "/api/integrations/github/resources",
      },
    },
    {
      id: "azure",
      name: "Azure",
      connected: false,
      enabled: true,
      category: "cloud",
      endpoints: {
        health: "/api/integrations/azure/health",
        profile: "/api/integrations/azure/profile",
        resources: "/api/integrations/azure/resources",
      },
    },
    {
      id: "microsoft365",
      name: "Microsoft 365",
      connected: false,
      enabled: true,
      category: "productivity",
      endpoints: {
        health: "/api/integrations/microsoft365/health",
        profile: "/api/integrations/microsoft365/profile",
        resources: "/api/integrations/microsoft365/resources",
      },
    },
    {
      id: "notion",
      name: "Notion",
      connected: false,
      enabled: true,
      category: "productivity",
      endpoints: {
        health: "/api/integrations/notion/health",
        profile: "/api/integrations/notion/profile",
        resources: "/api/integrations/notion/resources",
      },
    },
    {
      id: "salesforce",
      name: "Salesforce",
      connected: false,
      enabled: true,
      category: "crm",
      endpoints: {
        health: "/api/integrations/salesforce/health",
        profile: "/api/integrations/salesforce/profile",
        resources: "/api/integrations/salesforce/resources",
      },
    },
    {
      id: "slack",
      name: "Slack",
      connected: false,
      enabled: true,
      category: "communication",
      endpoints: {
        health: "/api/integrations/slack/health",
        profile: "/api/integrations/slack/profile",
        resources: "/api/integrations/slack/resources",
      },
    },
    {
      id: "stripe",
      name: "Stripe",
      connected: false,
      enabled: true,
      category: "finance",
      endpoints: {
        health: "/api/integrations/stripe/health",
        profile: "/api/integrations/stripe/profile",
        resources: "/api/integrations/stripe/resources",
      },
    },
    {
      id: "teams",
      name: "Microsoft Teams",
      connected: false,
      enabled: true,
      category: "communication",
      endpoints: {
        health: "/api/integrations/teams/health",
        profile: "/api/integrations/teams/profile",
        resources: "/api/integrations/teams/resources",
      },
    },
    {
      id: "zoom",
      name: "Zoom",
      connected: false,
      enabled: true,
      category: "communication",
      endpoints: {
        health: "/api/integrations/zoom/health",
        profile: "/api/integrations/zoom/profile",
        resources: "/api/integrations/zoom/resources",
      },
    },
  ];

  const checkIntegrationHealth = async (integration: Omit<IntegrationHealth, "status" | "lastSync" | "responseTime" | "errorCount">): Promise<IntegrationHealth> => {
    const startTime = Date.now();
    let status: IntegrationHealth["status"] = "unknown";
    let connected = false;
    let errorCount = 0;

    try {
      const response = await fetch(integration.endpoints.health);
      const endTime = Date.now();
      const responseTime = endTime - startTime;

      if (response.ok) {
        const data = await response.json();
        connected = data.connected || data.status === "healthy";
        status = connected ? "healthy" : "warning";
      } else {
        status = "error";
        errorCount = 1;
      }

      return {
        ...integration,
        status,
        connected,
        lastSync: new Date().toISOString(),
        responseTime,
        errorCount,
      };
    } catch (error) {
      console.error(`Health check failed for ${integration.name}:`, error);
      return {
        ...integration,
        status: "error",
        connected: false,
        lastSync: new Date().toISOString(),
        responseTime: Date.now() - startTime,
        errorCount: 1,
      };
    }
  };

  const refreshHealthStatus = async () => {
    setRefreshing(true);
    try {
      const healthPromises = integrationList.map(checkIntegrationHealth);
      const results = await Promise.all(healthPromises);
      setIntegrations(results);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to refresh health status:", error);
    } finally {
      setRefreshing(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshHealthStatus();
  }, []);

  useEffect(() => {
    if (autoRefresh && !loading) {
      const interval = setInterval(refreshHealthStatus, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval, loading]);

  const getStatusColor = (status: IntegrationHealth["status"]) => {
    switch (status) {
      case "healthy":
        return "green";
      case "warning":
        return "yellow";
      case "error":
        return "red";
      default:
        return "gray";
    }
  };

  const getStatusIcon = (status: IntegrationHealth["status"]) => {
    switch (status) {
      case "healthy":
        return CheckCircleIcon;
      case "warning":
        return WarningTwoIcon;
      case "error":
        return WarningTwoIcon;
      default:
        return TimeIcon;
    }
  };

  const formatResponseTime = (ms?: number) => {
    if (!ms) return "N/A";
    return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}s`;
  };

  const formatLastSync = (dateString?: string) => {
    if (!dateString) return "Never";
    return new Date(dateString).toLocaleTimeString();
  };

  const healthyCount = integrations.filter(i => i.status === "healthy").length;
  const warningCount = integrations.filter(i => i.status === "warning").length;
  const errorCount = integrations.filter(i => i.status === "error").length;
  const totalCount = integrations.length;

  if (loading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading integration health status...</Text>
      </Box>
    );
  }

  return (
    <Box>
      {/* Summary Stats */}
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} mb={6}>
        <Card bg={bgColor} border="1px" borderColor={borderColor}>
          <CardBody>
            <Stat>
              <StatLabel>Total Integrations</StatLabel>
              <StatNumber>{totalCount}</StatNumber>
              <StatHelpText>All configured</StatHelpText>
            </Stat>
          </CardBody>
        </Card>

        <Card bg={bgColor} border="1px" borderColor={borderColor}>
          <CardBody>
            <Stat>
              <StatLabel>Healthy</StatLabel>
              <StatNumber color="green.500">{healthyCount}</StatNumber>
              <StatHelpText>Running smoothly</StatHelpText>
            </Stat>
          </CardBody>
        </Card>

        <Card bg={bgColor} border="1px" borderColor={borderColor}>
          <CardBody>
            <Stat>
              <StatLabel>Warnings</StatLabel>
              <StatNumber color="yellow.500">{warningCount}</StatNumber>
              <StatHelpText>Needs attention</StatHelpText>
            </Stat>
          </CardBody>
        </Card>

        <Card bg={bgColor} border="1px" borderColor={borderColor}>
          <CardBody>
            <Stat>
              <StatLabel>Errors</StatLabel>
              <StatNumber color="red.500">{errorCount}</StatNumber>
              <StatHelpText>Requires action</StatHelpText>
            </Stat>
          </CardBody>
        </Card>
      </SimpleGrid>

      {/* Health Progress */}
      <Card bg={bgColor} border="1px" borderColor={borderColor} mb={6}>
        <CardBody>
          <VStack spacing={4} align="stretch">
            <HStack justify="space-between">
              <Text fontWeight="bold">Overall Health</Text>
              <Text fontSize="sm" color="gray.500">
                {healthyCount}/{totalCount} healthy
              </Text>
            </HStack>
            <Progress
              value={(healthyCount / totalCount) * 100}
              colorScheme={
                healthyCount === totalCount ? "green" :
                healthyCount > totalCount / 2 ? "yellow" : "red"
              }
              size="lg"
              borderRadius="md"
            />
            <HStack justify="space-between" fontSize="sm">
              <Text>0%</Text>
              <Text>50%</Text>
              <Text>100%</Text>
            </HStack>
          </VStack>
        </CardBody>
      </Card>

      {/* Integration List */}
      <VStack spacing={4} align="stretch">
        <HStack justify="space-between">
          <Text fontWeight="bold" fontSize="lg">Integration Status</Text>
          <Button
            size="sm"
            leftIcon={<RepeatIcon />}
            onClick={refreshHealthStatus}
            isLoading={refreshing}
            loadingText="Refreshing"
          >
            Refresh
          </Button>
        </HStack>

        {lastUpdated && (
          <Text fontSize="sm" color="gray.500">
            Last updated: {lastUpdated.toLocaleString()}
          </Text>
        )}

        {integrations.map((integration) => (
          <Card
            key={integration.id}
            bg={bgColor}
            border="1px"
            borderColor={borderColor}
            _hover={{ shadow: "md" }}
            transition="all 0.2s"
          >
            <CardBody>
              <HStack spacing={4} align="start">
                <Icon
                  as={getStatusIcon(integration.status)}
                  w={6}
                  h={6}
                  color={`${getStatusColor(integration.status)}.500`}
                />

                <VStack align="start" flex={1} spacing={2}>
                  <HStack justify="space-between" width="100%">
                    <Text fontWeight="bold">{integration.name}</Text>
                    <HStack spacing={2}>
                      <Badge colorScheme="blue" size="sm">
                        {integration.category}
                      </Badge>
                      <Badge
                        colorScheme={getStatusColor(integration.status)}
                        size="sm"
                      >
                        {integration.status.toUpperCase()}
                      </Badge>
                      {integration.connected && (
                        <Badge colorScheme="green" size="sm">
                          CONNECTED
                        </Badge>
                      )}
                    </HStack>
                  </HStack>

                  {showDetails && (
                    <HStack spacing={6} fontSize="sm" color="gray.600">
                      <Tooltip label="Last synchronization">
                        <HStack spacing={1}>
                          <TimeIcon />
                          <Text>{formatLastSync(integration.lastSync)}</Text>
                        </HStack>
                      </Tooltip>

                      <Tooltip label="Response time">
                        <HStack spacing={1}>
                          <SettingsIcon />
                          <Text>{formatResponseTime(integration.responseTime)}</Text>
                        </HStack>
                      </Tooltip>

                      {integration.errorCount && integration.errorCount > 0 && (
                        <Tooltip label="Error count">
                          <HStack spacing={1}>
                            <WarningTwoIcon />
                            <Text>{integration.errorCount} errors</Text>
                          </HStack>
                        </Tooltip>
                      )}
                    </HStack>
                  )}
                </VStack>
              </HStack>
            </CardBody>
          </Card>
        ))}
      </VStack>

      {/* Status Legend */}
      <Card bg={bgColor} border="1px" borderColor={borderColor} mt={6}>
        <CardBody>
          <Text fontWeight="bold" mb={3}>Status Legend</Text>
          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
            <HStack>
              <Icon as={CheckCircleIcon} color="green.500" />
              <Text fontSize="sm">Healthy - Integration is working properly</Text>
            </HStack>
            <HStack>
              <Icon as={WarningTwoIcon} color="yellow.500" />
              <Text fontSize="sm">Warning - Minor issues detected</Text>
            </HStack>
            <HStack>
              <Icon as={WarningTwoIcon} color="red.500" />
              <Text fontSize="sm">Error - Integration requires attention</Text>
            </HStack>
          </SimpleGrid>
        </CardBody>
      </Card>
    </Box>
  );
};

export default IntegrationHealthDashboard;
