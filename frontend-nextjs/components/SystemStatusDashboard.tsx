import React, { useState, useEffect } from 'react';
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
  Badge,
  Spinner,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  useToast,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  SimpleGrid,
  Flex,
  Icon,
  Tooltip,
} from '@chakra-ui/react';
import {
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  SettingsIcon,
  RepeatIcon,
  ArrowForwardIcon,
  CloseIcon,
  SunIcon,
  ExternalLinkIcon,
} from '@chakra-ui/icons';
import { systemAPI, serviceRegistryAPI, byokAPI, workflowAPI, apiUtils } from '../lib/api';

interface SystemStatusData {
  timestamp: string;
  overall_status: string;
  system: any;
  resources: any;
  services: any;
  features: any;
  uptime: any;
  version: any;
}

interface ServiceStatus {
  name: string;
  status: string;
  status_code?: number;
  response_time_ms?: number;
  error?: string;
  last_checked: string;
}

const SystemStatusDashboard: React.FC = () => {
  const [systemStatus, setSystemStatus] = useState<SystemStatusData | null>(null);
  const [services, setServices] = useState<any[]>([]);
  const [providers, setProviders] = useState<any[]>([]);
  const [workflows, setWorkflows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const toast = useToast();

  const fetchSystemData = async () => {
    try {
      setRefreshing(true);

      // Fetch system status
      const statusResponse = await systemAPI.getSystemStatus();
      setSystemStatus(statusResponse.data);

      // Fetch services
      const servicesResponse = await serviceRegistryAPI.getServices();
      setServices(servicesResponse.data.services || []);

      // Fetch AI providers
      const providersResponse = await byokAPI.getProviders();
      setProviders(providersResponse.data.providers || []);

      // Fetch workflow templates
      const workflowsResponse = await workflowAPI.getTemplates();
      setWorkflows(workflowsResponse.data.templates || []);

    } catch (error) {
      console.error('Error fetching system data:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch system status',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchSystemData();

    // Refresh every 30 seconds
    const interval = setInterval(fetchSystemData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'operational':
        return 'green';
      case 'degraded':
        return 'yellow';
      case 'unhealthy':
      case 'unreachable':
        return 'red';
      default:
        return 'gray';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'healthy':
      case 'operational':
        return CheckCircleIcon;
      case 'degraded':
        return WarningIcon;
      case 'unhealthy':
      case 'unreachable':
        return CloseIcon;
      default:
        return TimeIcon;
    }
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const formatBytes = (bytes: number) => {
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    if (bytes === 0) return '0 Bytes';
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  };

  if (loading) {
    return (
      <Box textAlign="center" py={8}>
        <Spinner size="xl" />
        <Text mt={4}>Loading system status...</Text>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Flex justify="space-between" align="center">
          <VStack align="start" spacing={1}>
            <Heading size="lg">System Status Dashboard</Heading>
            <Text color="gray.600">
              Last updated: {systemStatus ? new Date(systemStatus.timestamp).toLocaleString() : 'Unknown'}
            </Text>
          </VStack>
          <HStack spacing={3}>
            <Badge
              colorScheme={getStatusColor(systemStatus?.overall_status)}
              fontSize="md"
              px={3}
              py={1}
            >
              <Icon as={getStatusIcon(systemStatus?.overall_status)} mr={1} />
              {systemStatus?.overall_status?.toUpperCase() || 'UNKNOWN'}
            </Badge>
            <Tooltip label="Refresh status">
              <IconButton
                aria-label="Refresh"
                icon={<RepeatIcon />}
                isLoading={refreshing}
                onClick={fetchSystemData}
                variant="outline"
              />
            </Tooltip>
          </HStack>
        </Flex>

        {/* System Overview */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
          <Card>
            <CardBody>
              <VStack spacing={2} align="start">
                <Text fontSize="sm" color="gray.600">System Uptime</Text>
                <Heading size="lg">
                  {systemStatus ? formatUptime(systemStatus.uptime.system_seconds) : 'N/A'}
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  Process: {systemStatus ? formatUptime(systemStatus.uptime.process_seconds) : 'N/A'}
                </Text>
              </VStack>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <VStack spacing={2} align="start">
                <Text fontSize="sm" color="gray.600">CPU Usage</Text>
                <Heading size="lg">
                  {systemStatus?.resources?.cpu?.percent?.toFixed(1) || '0'}%
                </Heading>
                <Progress
                  value={systemStatus?.resources?.cpu?.percent || 0}
                  size="sm"
                  width="100%"
                  colorScheme={systemStatus?.resources?.cpu?.percent > 80 ? 'red' : 'green'}
                />
              </VStack>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <VStack spacing={2} align="start">
                <Text fontSize="sm" color="gray.600">Memory Usage</Text>
                <Heading size="lg">
                  {systemStatus?.resources?.memory?.system_used_percent?.toFixed(1) || '0'}%
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {systemStatus?.resources?.memory?.rss_mb || '0'} MB used
                </Text>
              </VStack>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <VStack spacing={2} align="start">
                <Text fontSize="sm" color="gray.600">Disk Usage</Text>
                <Heading size="lg">
                  {systemStatus?.resources?.disk?.percent?.toFixed(1) || '0'}%
                </Heading>
                <Text fontSize="xs" color="gray.500">
                  {systemStatus?.resources?.disk?.free_gb || '0'} GB free
                </Text>
              </VStack>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Services Status */}
        <Card>
          <CardHeader>
            <Heading size="md">Services Status</Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
              {systemStatus?.services && Object.entries(systemStatus.services).map(([serviceId, service]: [string, any]) => (
                <Card key={serviceId} size="sm" variant="outline">
                  <CardBody>
                    <HStack justify="space-between">
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="medium">{service.name}</Text>
                        <Badge colorScheme={getStatusColor(service.status)}>
                          {service.status}
                        </Badge>
                        {service.response_time_ms && (
                          <Text fontSize="xs" color="gray.500">
                            {service.response_time_ms}ms
                          </Text>
                        )}
                      </VStack>
                      <Icon as={getStatusIcon(service.status)} color={getStatusColor(service.status)} />
                    </HStack>
                    {service.error && (
                      <Text fontSize="xs" color="red.500" mt={2}>
                        {service.error}
                      </Text>
                    )}
                  </CardBody>
                </Card>
              ))}
            </SimpleGrid>
          </CardBody>
        </Card>

        {/* Features & Integrations */}
        <Grid templateColumns={{ base: '1fr', lg: '2fr 1fr' }} gap={6}>
          {/* Services & Providers */}
          <Card>
            <CardHeader>
              <Heading size="md">Services & AI Providers</Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                {/* Registered Services */}
                <Box>
                  <Text fontWeight="medium" mb={2}>Registered Services ({services.length})</Text>
                  <SimpleGrid columns={2} spacing={2}>
                    {services.map((service) => (
                      <Badge key={service.id} colorScheme="blue" variant="subtle" px={2} py={1}>
                        {service.name}
                      </Badge>
                    ))}
                  </SimpleGrid>
                </Box>

                {/* AI Providers */}
                <Box>
                  <Text fontWeight="medium" mb={2}>AI Providers ({providers.length})</Text>
                  <SimpleGrid columns={2} spacing={2}>
                    {providers.map((provider) => (
                      <Badge key={provider.id} colorScheme="green" variant="subtle" px={2} py={1}>
                        {provider.name}
                      </Badge>
                    ))}
                  </SimpleGrid>
                </Box>
              </VStack>
            </CardBody>
          </Card>

          {/* System Info */}
          <Card>
            <CardHeader>
              <Heading size="md">System Information</Heading>
            </CardHeader>
            <CardBody>
              <VStack spacing={3} align="stretch">
                <Box>
                  <Text fontSize="sm" color="gray.600">Platform</Text>
                  <Text fontSize="sm">{systemStatus?.system?.platform?.system || 'Unknown'}</Text>
                </Box>
                <Box>
                  <Text fontSize="sm" color="gray.600">Node</Text>
                  <Text fontSize="sm">{systemStatus?.system?.platform?.node || 'Unknown'}</Text>
                </Box>
                <Box>
                  <Text fontSize="sm" color="gray.600">Python Version</Text>
                  <Text fontSize="sm">{systemStatus?.system?.python?.version?.split(' ')[0] || 'Unknown'}</Text>
                </Box>
                <Box>
                  <Text fontSize="sm" color="gray.600">Process ID</Text>
                  <Text fontSize="sm">{systemStatus?.system?.process?.pid || 'Unknown'}</Text>
                </Box>
              </VStack>
            </CardBody>
          </Card>
        </Grid>

        {/* Feature Status */}
        <Card>
          <CardHeader>
            <Heading size="md">Feature Status</Heading>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
              {systemStatus?.features && Object.entries(systemStatus.features).map(([featureId, feature]: [string, any]) => (
                <Card key={featureId} size="sm">
                  <CardBody>
                    <VStack spacing={2} align="start">
                      <Badge colorScheme={getStatusColor(feature.status)}>
                        {feature.status}
                      </Badge>
                      <Text fontWeight="medium">{feature.description}</Text>
                      {feature.providers && (
                        <Text fontSize="sm" color="gray.600">
                          {feature.providers} providers
                        </Text>
                      )}
                      {feature.services_registered && (
                        <Text fontSize="sm" color="gray.600">
                          {feature.services_registered} services
                        </Text>
                      )}
                      {feature.templates_available && (
                        <Text fontSize="sm" color="gray.600">
                          {feature.templates_available} templates
                        </Text>
                      )}
                    </VStack>
                  </CardBody>
                </Card>
              ))}
            </SimpleGrid>
          </CardBody>
        </Card>

        {/* Alerts */}
        {systemStatus?.overall_status !== 'healthy' && (
          <Alert status="warning" variant="left-accent">
            <AlertIcon />
            <Box>
              <AlertTitle>System Status: {systemStatus?.overall_status?.toUpperCase()}</AlertTitle>
              <AlertDescription>
                Some services may be experiencing issues. Check the services status above for details.
              </AlertDescription>
            </Box>
          </Alert>
        )}
      </VStack>
    </Box>
  );
};

export default SystemStatusDashboard;
