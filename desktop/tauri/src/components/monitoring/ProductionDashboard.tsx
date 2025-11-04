/**
 * Production Monitoring Dashboard for Outlook Integration
 * Real-time metrics, health checks, and alerts
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Text,
  VStack,
  HStack,
  Grid,
  GridItem,
  Progress,
  Badge,
  Alert,
  AlertIcon,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  useToast,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Divider,
  IconButton,
  Tooltip
} from '@chakra-ui/react';
import {
  TimeIcon,
  ViewIcon,
  WarningIcon,
  CheckCircleIcon,
  RepeatIcon,
  ExternalLinkIcon
} from '@chakra-ui/icons';
import { outlookMonitoringService, MonitoringMetrics, HealthCheck } from '../monitoring/outlookMonitoring';

interface DashboardData {
  metrics: MonitoringMetrics;
  healthChecks: Record<string, HealthCheck>;
  lastUpdate: string;
  alerts: Array<{
    id: string;
    severity: string;
    message: string;
    timestamp: string;
  }>;
}

export const ProductionDashboard: React.FC = () => {
  const [data, setData] = useState<DashboardData>({
    metrics: outlookMonitoringService.getMetrics(),
    healthChecks: outlookMonitoringService.getHealthChecks(),
    lastUpdate: new Date().toISOString(),
    alerts: []
  });
  const [isLoading, setIsLoading] = useState(true);
  const toast = useToast();

  useEffect(() => {
    const updateData = () => {
      setData({
        metrics: outlookMonitoringService.getMetrics(),
        healthChecks: outlookMonitoringService.getHealthChecks(),
        lastUpdate: new Date().toISOString(),
        alerts: getActiveAlerts()
      });
      setIsLoading(false);
    };

    // Initial load
    updateData();

    // Update every 10 seconds
    const interval = setInterval(updateData, 10000);

    return () => clearInterval(interval);
  }, []);

  const getActiveAlerts = () => {
    // Mock alerts - in production, get from monitoring service
    return [
      {
        id: '1',
        severity: 'medium',
        message: 'OAuth response time is elevated',
        timestamp: new Date().toISOString()
      },
      {
        id: '2',
        severity: 'low',
        message: 'CPU usage is above normal threshold',
        timestamp: new Date(Date.now() - 5 * 60000).toISOString()
      }
    ];
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'green';
      case 'degraded': return 'yellow';
      case 'unhealthy': return 'red';
      default: return 'gray';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'red';
      case 'high': return 'orange';
      case 'medium': return 'yellow';
      case 'low': return 'blue';
      default: return 'gray';
    }
  };

  const formatResponseTime = (ms: number) => {
    return `${ms.toFixed(0)}ms`;
  };

  const formatPercentage = (value: number) => {
    return `${value.toFixed(1)}%`;
  };

  const MetricCard: React.FC<{
    title: string;
    value: string | number;
    subtitle?: string;
    status?: 'good' | 'warning' | 'error';
  }> = ({ title, value, subtitle, status }) => (
    <Card>
      <CardBody>
        <Stat>
          <StatLabel fontSize="sm" color="gray.600">{title}</StatLabel>
          <StatNumber fontSize="2xl" fontWeight="bold">
            {value}
          </StatNumber>
          {subtitle && (
            <StatHelpText fontSize="xs" color="gray.500">
              {subtitle}
            </StatHelpText>
          )}
        </Stat>
        {status && (
          <Badge
            mt={2}
            colorScheme={
              status === 'good' ? 'green' :
              status === 'warning' ? 'yellow' : 'red'
            }
          >
            {status}
          </Badge>
        )}
      </CardBody>
    </Card>
  );

  const HealthStatusCard: React.FC<{ service: string; health: HealthCheck }> = ({ service, health }) => (
    <Card size="sm">
      <CardBody>
        <HStack justify="space-between">
          <VStack align="start" spacing={0}>
            <Text fontSize="sm" fontWeight="medium">{service}</Text>
            <Text fontSize="xs" color="gray.500">
              Response: {health.responseTime >= 0 ? formatResponseTime(health.responseTime) : 'N/A'}
            </Text>
          </VStack>
          <Badge colorScheme={getStatusColor(health.status)}>
            {health.status}
          </Badge>
        </HStack>
      </CardBody>
    </Card>
  );

  const AlertCard: React.FC<{ alert: any }> = ({ alert }) => (
    <Alert status={getSeverityColor(alert.severity) as any} variant="subtle">
      <AlertIcon />
      <Box flex={1}>
        <Text fontSize="sm" fontWeight="medium">{alert.message}</Text>
        <Text fontSize="xs" color="gray.600">
          {new Date(alert.timestamp).toLocaleString()}
        </Text>
      </Box>
    </Alert>
  );

  if (isLoading) {
    return (
      <Box p={8}>
        <VStack spacing={4}>
          <Text>Loading production dashboard...</Text>
          <Progress size="sm" isIndeterminate />
        </VStack>
      </Box>
    );
  }

  return (
    <Box p={6} bg="gray.50" minH="100vh">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <Box>
            <Heading size="lg" color="gray.800">Outlook Integration Dashboard</Heading>
            <Text fontSize="sm" color="gray.600">
              Production Monitoring • Last updated: {new Date(data.lastUpdate).toLocaleString()}
            </Text>
          </Box>
          <HStack spacing={2}>
            <Tooltip label="Refresh data">
              <IconButton
                aria-label="Refresh"
                icon={<RepeatIcon />}
                onClick={() => window.location.reload()}
                variant="ghost"
              />
            </Tooltip>
            <Tooltip label="Open logs">
              <IconButton
                aria-label="Logs"
                icon={<ExternalLinkIcon />}
                onClick={() => window.open('/logs', '_blank')}
                variant="ghost"
              />
            </Tooltip>
          </HStack>
        </HStack>

        {/* Main Tabs */}
        <Tabs variant="soft-rounded" colorScheme="blue">
          <TabList>
            <Tab>Overview</Tab>
            <Tab>Metrics</Tab>
            <Tab>Health</Tab>
            <Tab>Alerts</Tab>
          </TabList>

          <TabPanels>
            {/* Overview Tab */}
            <TabPanel>
              <VStack spacing={6}>
                {/* Key Metrics */}
                <SimpleGrid columns={4} spacing={4}>
                  <MetricCard
                    title="Active Users"
                    value={data.metrics.activeUsers}
                    status="good"
                  />
                  <MetricCard
                    title="Success Rate"
                    value={formatPercentage(data.metrics.oauthSuccessRate)}
                    subtitle="OAuth operations"
                    status={data.metrics.oauthSuccessRate > 95 ? 'good' : 'warning'}
                  />
                  <MetricCard
                    title="Avg Response Time"
                    value={formatResponseTime(data.metrics.oauthResponseTime)}
                    subtitle="All operations"
                    status={data.metrics.oauthResponseTime < 2000 ? 'good' : 'warning'}
                  />
                  <MetricCard
                    title="Error Rate"
                    value={formatPercentage(data.metrics.errorRate)}
                    subtitle="Last 24 hours"
                    status={data.metrics.errorRate < 1 ? 'good' : 'warning'}
                  />
                </SimpleGrid>

                {/* Service Status */}
                <Box>
                  <Heading size="md" mb={4} color="gray.700">Service Status</Heading>
                  <SimpleGrid columns={3} spacing={4}>
                    {Object.entries(data.healthChecks).map(([service, health]) => (
                      <HealthStatusCard key={service} service={service} health={health} />
                    ))}
                  </SimpleGrid>
                </Box>

                {/* Recent Alerts */}
                <Box>
                  <Heading size="md" mb={4} color="gray.700">Recent Alerts</Heading>
                  <VStack spacing={2} align="stretch">
                    {data.alerts.slice(0, 3).map(alert => (
                      <AlertCard key={alert.id} alert={alert} />
                    ))}
                  </VStack>
                </Box>
              </VStack>
            </TabPanel>

            {/* Metrics Tab */}
            <TabPanel>
              <VStack spacing={6}>
                {/* OAuth Metrics */}
                <Card>
                  <CardHeader>
                    <Heading size="md">OAuth Metrics</Heading>
                  </CardHeader>
                  <CardBody>
                    <SimpleGrid columns={2} spacing={4}>
                      <MetricCard
                        title="Success Rate"
                        value={formatPercentage(data.metrics.oauthSuccessRate)}
                        status={data.metrics.oauthSuccessRate > 95 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Response Time"
                        value={formatResponseTime(data.metrics.oauthResponseTime)}
                        status={data.metrics.oauthResponseTime < 3000 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Failure Rate"
                        value={formatPercentage(data.metrics.oauthFailureRate)}
                        status={data.metrics.oauthFailureRate < 5 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Token Refresh Rate"
                        value={formatPercentage(data.metrics.tokenRefreshRate)}
                      />
                    </SimpleGrid>
                  </CardBody>
                </Card>

                {/* Email Metrics */}
                <Card>
                  <CardHeader>
                    <Heading size="md">Email Metrics</Heading>
                  </CardHeader>
                  <CardBody>
                    <SimpleGrid columns={2} spacing={4}>
                      <MetricCard
                        title="Send Success Rate"
                        value={formatPercentage(data.metrics.emailSendSuccessRate)}
                        status={data.metrics.emailSendSuccessRate > 98 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Send Response Time"
                        value={formatResponseTime(data.metrics.emailSendResponseTime)}
                        status={data.metrics.emailSendResponseTime < 5000 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Search Response Time"
                        value={formatResponseTime(data.metrics.emailSearchResponseTime)}
                        status={data.metrics.emailSearchResponseTime < 3000 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Triage Accuracy"
                        value={formatPercentage(data.metrics.emailTriageAccuracy)}
                        status={data.metrics.emailTriageAccuracy > 85 ? 'good' : 'warning'}
                      />
                    </SimpleGrid>
                  </CardBody>
                </Card>

                {/* Calendar Metrics */}
                <Card>
                  <CardHeader>
                    <Heading size="md">Calendar Metrics</Heading>
                  </CardHeader>
                  <CardBody>
                    <SimpleGrid columns={2} spacing={4}>
                      <MetricCard
                        title="Create Success Rate"
                        value={formatPercentage(data.metrics.calendarCreateSuccessRate)}
                        status={data.metrics.calendarCreateSuccessRate > 95 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Update Success Rate"
                        value={formatPercentage(data.metrics.calendarUpdateSuccessRate)}
                        status={data.metrics.calendarUpdateSuccessRate > 95 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Search Response Time"
                        value={formatResponseTime(data.metrics.calendarSearchResponseTime)}
                        status={data.metrics.calendarSearchResponseTime < 2000 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Event Retrieval Time"
                        value={formatResponseTime(data.metrics.calendarEventRetrievalTime)}
                        status={data.metrics.calendarEventRetrievalTime < 1000 ? 'good' : 'warning'}
                      />
                    </SimpleGrid>
                  </CardBody>
                </Card>

                {/* System Metrics */}
                <Card>
                  <CardHeader>
                    <Heading size="md">System Metrics</Heading>
                  </CardHeader>
                  <CardBody>
                    <SimpleGrid columns={2} spacing={4}>
                      <MetricCard
                        title="Memory Usage"
                        value={formatPercentage(data.metrics.memoryUsage)}
                        status={data.metrics.memoryUsage < 80 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="CPU Usage"
                        value={formatPercentage(data.metrics.cpuUsage)}
                        status={data.metrics.cpuUsage < 70 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Disk Usage"
                        value={formatPercentage(data.metrics.diskUsage)}
                        status={data.metrics.diskUsage < 90 ? 'good' : 'warning'}
                      />
                      <MetricCard
                        title="Network Latency"
                        value={formatResponseTime(data.metrics.networkLatency)}
                        status={data.metrics.networkLatency < 1000 ? 'good' : 'warning'}
                      />
                    </SimpleGrid>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* Health Tab */}
            <TabPanel>
              <VStack spacing={6}>
                <Box>
                  <Heading size="md" mb={4} color="gray.700">Service Health Checks</Heading>
                  <SimpleGrid columns={2} spacing={4}>
                    {Object.entries(data.healthChecks).map(([service, health]) => (
                      <Card key={service}>
                        <CardBody>
                          <HStack justify="space-between" mb={3}>
                            <Text fontSize="lg" fontWeight="medium">{service}</Text>
                            <Badge colorScheme={getStatusColor(health.status)} fontSize="sm">
                              {health.status}
                            </Badge>
                          </HStack>
                          <VStack align="start" spacing={2}>
                            <HStack justify="space-between" w="full">
                              <Text fontSize="sm" color="gray.600">Response Time:</Text>
                              <Text fontSize="sm" fontWeight="medium">
                                {health.responseTime >= 0 ? formatResponseTime(health.responseTime) : 'N/A'}
                              </Text>
                            </HStack>
                            <HStack justify="space-between" w="full">
                              <Text fontSize="sm" color="gray.600">Last Check:</Text>
                              <Text fontSize="sm">
                                {new Date(health.lastCheck).toLocaleTimeString()}
                              </Text>
                            </HStack>
                            {health.details && (
                              <Box w="full">
                                <Text fontSize="sm" color="gray.600" mb={1}>Details:</Text>
                                <Box bg="gray.50" p={2} rounded="md" w="full">
                                  <Text fontSize="xs" fontFamily="mono">
                                    {JSON.stringify(health.details, null, 2)}
                                  </Text>
                                </Box>
                              </Box>
                            )}
                          </VStack>
                        </CardBody>
                      </Card>
                    ))}
                  </SimpleGrid>
                </Box>
              </VStack>
            </TabPanel>

            {/* Alerts Tab */}
            <TabPanel>
              <VStack spacing={6}>
                <Box>
                  <Heading size="md" mb={4} color="gray.700">Active Alerts</Heading>
                  <VStack spacing={3} align="stretch">
                    {data.alerts.length > 0 ? (
                      data.alerts.map(alert => (
                        <AlertCard key={alert.id} alert={alert} />
                      ))
                    ) : (
                      <Alert status="success">
                        <CheckCircleIcon />
                        <Box>
                          <Text fontWeight="medium">No active alerts</Text>
                          <Text fontSize="sm" color="gray.600">
                            All systems are operating normally
                          </Text>
                        </Box>
                      </Alert>
                    )}
                  </VStack>
                </Box>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default ProductionDashboard;