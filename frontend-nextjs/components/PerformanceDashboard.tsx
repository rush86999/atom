/**
 * Performance Monitoring Dashboard Component
 * Real-time system and application performance monitoring
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Card,
  CardBody,
  CardHeader,
  SimpleGrid,
  Progress,
  Badge,
  useToast,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Tab,
  TabList,
  TabPanel,
  TabPanels,
  Tabs,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Button,
  Select,
  Alert,
  AlertIcon,
  Spinner,
  Icon,
} from '@chakra-ui/react';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import { 
  CheckCircleIcon, 
  WarningIcon, 
  XCircleIcon,
  TimeIcon,
  MemoryIcon,
  CpuIcon,
  NetworkIcon,
} from '@chakra-ui/icons';

interface HealthData {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  uptime: number;
  version: string;
  environment: string;
  checks: {
    database: { status: string; responseTime: number; };
    redis: { status: string; responseTime: number; connected: boolean; };
    auth: { status: string; };
    memory: { status: string; used: number; total: number; percentage: number; };
    cpu: { status: string; usage: number; };
    integrations: { total: number; healthy: number; unhealthy: number; details: any[]; };
  };
  performance: {
    responseTime: number;
    throughput: number;
    errorRate: number;
    lastHour: { requests: number; errors: number; averageResponseTime: number; };
  };
}

interface AnalyticsData {
  timestamp: string;
  metrics: {
    users: { total: number; active: number; new: number; };
    integrations: { total: number; connected: number; usage: any[]; };
    performance: { averageResponseTime: number; throughput: number; errorRate: number; };
    features: { searchQueries: number; workflowExecutions: number; agentTasks: number; aiInteractions: number; };
  };
}

const PerformanceDashboard: React.FC = () => {
  const [healthData, setHealthData] = useState<HealthData | null>(null);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [timeRange, setTimeRange] = useState('24h');
  const [selectedMetric, setSelectedMetric] = useState('responseTime');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  
  const toast = useToast();

  useEffect(() => {
    fetchHealthData();
    fetchAnalyticsData();
    
    let interval: NodeJS.Timeout;
    if (autoRefresh) {
      interval = setInterval(() => {
        fetchHealthData();
        fetchAnalyticsData();
      }, 30000); // Refresh every 30 seconds
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [autoRefresh, timeRange]);

  const fetchHealthData = async () => {
    try {
      const response = await fetch('/api/health');
      if (response.ok) {
        const data = await response.json();
        setHealthData(data);
      } else {
        throw new Error('Health check failed');
      }
    } catch (err) {
      console.error('Failed to fetch health data:', err);
      setError('Failed to fetch health data');
    }
  };

  const fetchAnalyticsData = async () => {
    try {
      const response = await fetch(`/api/analytics?timeRange=${timeRange}`);
      if (response.ok) {
        const data = await response.json();
        setAnalyticsData(data.data);
      }
    } catch (err) {
      console.error('Failed to fetch analytics data:', err);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'green';
      case 'degraded': return 'yellow';
      case 'unhealthy': return 'red';
      default: return 'gray';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircleIcon />;
      case 'degraded': return <WarningIcon />;
      case 'unhealthy': return <XCircleIcon />;
      default: return <TimeIcon />;
    }
  };

  const formatUptime = (seconds: number) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${days}d ${hours}h ${minutes}m`;
  };

  const performanceData = healthData ? [
    { time: new Date().toLocaleTimeString(), responseTime: healthData.performance.responseTime },
    { time: new Date(Date.now() - 60000).toLocaleTimeString(), responseTime: healthData.performance.responseTime * 0.9 },
    { time: new Date(Date.now() - 120000).toLocaleTimeString(), responseTime: healthData.performance.responseTime * 1.1 },
    { time: new Date(Date.now() - 180000).toLocaleTimeString(), responseTime: healthData.performance.responseTime * 0.95 },
    { time: new Date(Date.now() - 240000).toLocaleTimeString(), responseTime: healthData.performance.responseTime * 1.05 },
  ] : [];

  const integrationHealthData = healthData ? healthData.checks.integrations.details.map(integ => ({
    name: integ.service,
    status: integ.status,
    value: integ.status === 'healthy' ? 1 : 0,
  })) : [];

  const COLORS = ['#10b981', '#ef4444', '#3b82f6', '#f59e0b', '#8b5cf6'];

  if (loading && !healthData) {
    return (
      <Box p={8}>
        <VStack spacing={4}>
          <Spinner size="xl" />
          <Text>Loading performance data...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box minH="100vh" bg="gray.50" p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <VStack align="start" spacing={1}>
            <Heading size="2xl">Performance Monitor</Heading>
            <Text color="gray.600">
              Real-time system health and performance metrics
            </Text>
          </VStack>
          
          <HStack spacing={4}>
            <Select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              width="120px"
            >
              <option value="1h">1 Hour</option>
              <option value="24h">24 Hours</option>
              <option value="7d">7 Days</option>
              <option value="30d">30 Days</option>
            </Select>
            
            <Button
              size="sm"
              colorScheme={autoRefresh ? "green" : "gray"}
              onClick={() => setAutoRefresh(!autoRefresh)}
            >
              {autoRefresh ? 'Auto-refresh On' : 'Auto-refresh Off'}
            </Button>
          </HStack>
        </HStack>

        {error && (
          <Alert status="error">
            <AlertIcon />
            {error}
          </Alert>
        )}

        {/* Health Status Overview */}
        {healthData && (
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>System Status</StatLabel>
                  <HStack>
                    <StatNumber>
                      <Badge colorScheme={getStatusColor(healthData.status)}>
                        {healthData.status.toUpperCase()}
                      </Badge>
                    </StatNumber>
                    <Icon color={getStatusColor(healthData.status)} as={getStatusIcon(healthData.status)} />
                  </HStack>
                  <StatHelpText>
                    Last updated: {new Date(healthData.timestamp).toLocaleTimeString()}
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Uptime</StatLabel>
                  <StatNumber>{formatUptime(healthData.uptime)}</StatNumber>
                  <StatHelpText>
                    Version: {healthData.version}
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Response Time</StatLabel>
                  <StatNumber>{healthData.performance.responseTime}ms</StatNumber>
                  <StatHelpText>
                    Error Rate: {healthData.performance.errorRate.toFixed(2)}%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Healthy Integrations</StatLabel>
                  <StatNumber>
                    {healthData.checks.integrations.healthy}/{healthData.checks.integrations.total}
                  </StatNumber>
                  <StatHelpText>
                    {healthData.checks.integrations.unhealthy} unhealthy
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Resource Usage */}
        {healthData && (
          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
            <Card>
              <CardHeader>
                <HStack>
                  <MemoryIcon />
                  <Heading size="md">Memory</Heading>
                </HStack>
              </CardHeader>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" width="100%">
                    <Text>Used</Text>
                    <Text fontWeight="bold">
                      {(healthData.checks.memory.used / 1024 / 1024).toFixed(1)} MB
                    </Text>
                  </HStack>
                  <Progress
                    value={healthData.checks.memory.percentage}
                    colorScheme={healthData.checks.memory.percentage > 80 ? 'red' : 
                                healthData.checks.memory.percentage > 60 ? 'yellow' : 'green'}
                    width="100%"
                  />
                  <Text fontSize="sm" color="gray.600">
                    {healthData.checks.memory.percentage.toFixed(1)}% utilized
                  </Text>
                </VStack>
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <HStack>
                  <CpuIcon />
                  <Heading size="md">CPU</Heading>
                </HStack>
              </CardHeader>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" width="100%">
                    <Text>Usage</Text>
                    <Text fontWeight="bold">{healthData.checks.cpu.usage.toFixed(1)}%</Text>
                  </HStack>
                  <Progress
                    value={healthData.checks.cpu.usage}
                    colorScheme={healthData.checks.cpu.usage > 80 ? 'red' : 
                                healthData.checks.cpu.usage > 60 ? 'yellow' : 'green'}
                    width="100%"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Load average
                  </Text>
                </VStack>
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <HStack>
                  <NetworkIcon />
                  <Heading size="md">Redis</Heading>
                </HStack>
              </CardHeader>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" width="100%">
                    <Text>Status</Text>
                    <Badge colorScheme={healthData.checks.redis.connected ? 'green' : 'red'}>
                      {healthData.checks.redis.connected ? 'Connected' : 'Disconnected'}
                    </Badge>
                  </HStack>
                  <Text fontSize="sm" color="gray.600">
                    Response Time: {healthData.checks.redis.responseTime}ms
                  </Text>
                </VStack>
              </CardBody>
            </Card>
          </SimpleGrid>
        )}

        {/* Performance Charts */}
        <Tabs variant="enclosed">
          <TabList>
            <Tab>Response Time</Tab>
            <Tab>Integration Health</Tab>
            <Tab>User Activity</Tab>
            <Tab>Error Rate</Tab>
          </TabList>

          <TabPanels>
            <TabPanel>
              <Card>
                <CardBody>
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={performanceData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="responseTime"
                        stroke="#3b82f6"
                        strokeWidth={2}
                        name="Response Time (ms)"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </CardBody>
              </Card>
            </TabPanel>

            <TabPanel>
              <Card>
                <CardBody>
                  <ResponsiveContainer width="100%" height={300}>
                    <PieChart>
                      <Pie
                        data={integrationHealthData}
                        cx="50%"
                        cy="50%"
                        outerRadius={80}
                        fill="#8884d8"
                        dataKey="value"
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {integrationHealthData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </CardBody>
              </Card>
            </TabPanel>

            <TabPanel>
              {analyticsData && (
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                  <Card>
                    <CardBody>
                      <Stat>
                        <StatLabel>Active Users</StatLabel>
                        <StatNumber>{analyticsData.metrics.users.active}</StatNumber>
                        <StatHelpText>
                          +{analyticsData.metrics.users.new} new users
                        </StatHelpText>
                      </Stat>
                    </CardBody>
                  </Card>
                  
                  <Card>
                    <CardBody>
                      <Stat>
                        <StatLabel>Feature Usage</StatLabel>
                        <StatNumber>{analyticsData.metrics.features.searchQueries}</StatNumber>
                        <StatHelpText>
                          Search queries in {timeRange}
                        </StatHelpText>
                      </Stat>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              )}
            </TabPanel>

            <TabPanel>
              <Card>
                <CardBody>
                  <ResponsiveContainer width="100%" height={300}>
                    <AreaChart data={performanceData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="time" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Area
                        type="monotone"
                        dataKey="responseTime"
                        stroke="#ef4444"
                        fill="#ef4444"
                        fillOpacity={0.3}
                        name="Error Rate"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardBody>
              </Card>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Detailed System Information */}
        {healthData && (
          <Card>
            <CardHeader>
              <Heading size="md">System Details</Heading>
            </CardHeader>
            <CardBody>
              <Table size="sm">
                <Thead>
                  <Tr>
                    <Th>Component</Th>
                    <Th>Status</Th>
                    <Th>Response Time</Th>
                    <Th>Last Check</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  <Tr>
                    <Td>Database</Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(healthData.checks.database.status)}>
                        {healthData.checks.database.status}
                      </Badge>
                    </Td>
                    <Td>{healthData.checks.database.responseTime}ms</Td>
                    <Td>{new Date(healthData.timestamp).toLocaleTimeString()}</Td>
                  </Tr>
                  <Tr>
                    <Td>Redis</Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(healthData.checks.redis.status)}>
                        {healthData.checks.redis.status}
                      </Badge>
                    </Td>
                    <Td>{healthData.checks.redis.responseTime}ms</Td>
                    <Td>{new Date(healthData.timestamp).toLocaleTimeString()}</Td>
                  </Tr>
                  <Tr>
                    <Td>Auth Service</Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(healthData.checks.auth.status)}>
                        {healthData.checks.auth.status}
                      </Badge>
                    </Td>
                    <Td>-</Td>
                    <Td>{new Date(healthData.timestamp).toLocaleTimeString()}</Td>
                  </Tr>
                </Tbody>
              </Table>
            </CardBody>
          </Card>
        )}
      </VStack>
    </Box>
  );
};

export default PerformanceDashboard;