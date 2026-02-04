/**
 * ATOM Performance Dashboard
 * Real-time monitoring dashboard for cache performance and system metrics
 * Provides visualizations and alerts for performance optimization
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box, Container, Heading, Text, VStack, HStack, SimpleGrid,
  Card, CardBody, CardHeader, Divider, Button, ButtonGroup,
  Tab, TabList, TabPanels, TabPanel, Tabs, Badge, Alert,
  AlertIcon, AlertTitle, AlertDescription, Progress, Stat,
  StatLabel, StatNumber, StatHelpText, Icon, Select, Input,
  Table, Thead, Tbody, Tr, Th, Td, TableContainer,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalFooter,
  ModalBody, ModalCloseButton, useDisclosure, FormControl,
  FormLabel, FormErrorMessage, Textarea, Checkbox, Switch,
  Spinner, Center, useToast, Accordion, AccordionItem,
  AccordionButton, AccordionPanel, AccordionIcon, Flex,
  Grid, GridItem, Link, Menu, MenuButton, MenuList,
  MenuItem, Chart, LineChart, AreaChart, BarChart,
  PieChart, ResponsiveContainer, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, Cell, Treemap,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis
} from '@chakra-ui/react';
import {
  FiCpu, FiDatabase, FiActivity, FiTrendingUp, FiTrendingDown,
  FiZap, FiClock, FiRefreshCw, FiSettings, FiAlertTriangle,
  FiCheckCircle, FiXCircle, FiInfo, FiBarChart2,
  FiPieChart, FiGrid, FiMonitor, FiServer, FiHardDrive,
  FiWifi, FiCloud, FiShield, FiLock, FiUnlock,
  FiFilter, FiDownload, FiUpload, FiMaximize2,
  FiMinimize2, FiEdit2, FiTrash2, FiCopy, FiEye,
  FiEyeOff, FiSave, FiCalendar, FiUser, FiUsers
} from 'react-icons/fi';
import { Line, Area, Bar, Pie, Radar, Treemap as TreemapComponent } from 'recharts';

// Types and Interfaces
export interface PerformanceMetrics {
  timestamp: string;
  cache: {
    hits: number;
    misses: number;
    hitRate: number;
    sets: number;
    deletes: number;
    errorRate: number;
    averageResponseTime: number;
    totalOperations: number;
    memoryUsage: {
      used: number;
      available: number;
      percentage: number;
    };
  };
  system: {
    cpu: number;
    memory: number;
    disk: number;
    network: {
      inbound: number;
      outbound: number;
    };
    uptime: number;
    requestRate: number;
  };
  integrations: Record<string, {
    requestCount: number;
    responseTime: number;
    errorRate: number;
    status: 'healthy' | 'degraded' | 'unavailable';
    lastSync: string;
  }>;
  alerts: AlertData[];
}

export interface AlertData {
  id: string;
  type: 'error' | 'warning' | 'info' | 'success';
  severity: 'low' | 'medium' | 'high' | 'critical';
  title: string;
  description: string;
  timestamp: string;
  source: string;
  resolved: boolean;
  acknowledged: boolean;
  actions?: Array<{
    label: string;
    action: () => void;
  }>;
}

export interface ChartData {
  timestamp: string;
  value: number;
  label?: string;
}

export interface TimeRange {
  label: string;
  value: number;
  unit: 'minutes' | 'hours' | 'days' | 'weeks';
}

// Props Interface
interface AtomPerformanceDashboardProps {
  onOptimize?: (type: string, config: any) => void;
  onRefresh?: () => void;
  height?: string;
  width?: string;
  autoRefresh?: boolean;
  refreshInterval?: number;
}

// Main Dashboard Component
const AtomPerformanceDashboard: React.FC<AtomPerformanceDashboardProps> = ({
  onOptimize,
  onRefresh,
  height = "100%",
  width = "100%",
  autoRefresh = true,
  refreshInterval = 30000
}) => {
  const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [timeRange, setTimeRange] = useState<TimeRange>({ label: 'Last Hour', value: 1, unit: 'hours' });
  const [selectedTab, setSelectedTab] = useState(0);
  const [autoRefreshEnabled, setAutoRefreshEnabled] = useState(autoRefresh);
  const { isOpen: settingsOpen, onOpen: settingsOnOpen, onClose: settingsOnClose } = useDisclosure();
  const { isOpen: alertOpen, onOpen: alertOnOpen, onClose: alertOnClose } = useDisclosure();
  const toast = useToast();

  // Mock data generator
  const generateMockMetrics = useCallback((): PerformanceMetrics => {
    const now = new Date();
    const cacheHits = Math.floor(Math.random() * 1000) + 500;
    const cacheMisses = Math.floor(Math.random() * 200) + 50;
    
    return {
      timestamp: now.toISOString(),
      cache: {
        hits: cacheHits,
        misses: cacheMisses,
        hitRate: (cacheHits / (cacheHits + cacheMisses)) * 100,
        sets: Math.floor(Math.random() * 100) + 20,
        deletes: Math.floor(Math.random() * 50) + 5,
        errorRate: Math.random() * 5,
        averageResponseTime: Math.random() * 100 + 50,
        totalOperations: cacheHits + cacheMisses,
        memoryUsage: {
          used: Math.floor(Math.random() * 512) + 256,
          available: 1024,
          percentage: 0
        }
      },
      system: {
        cpu: Math.random() * 80 + 10,
        memory: Math.random() * 70 + 20,
        disk: Math.random() * 50 + 10,
        network: {
          inbound: Math.random() * 1000 + 100,
          outbound: Math.random() * 800 + 50
        },
        uptime: Math.random() * 30 + 10,
        requestRate: Math.random() * 500 + 100
      },
      integrations: {
        'figma': {
          requestCount: Math.floor(Math.random() * 100) + 20,
          responseTime: Math.random() * 200 + 100,
          errorRate: Math.random() * 3,
          status: 'healthy',
          lastSync: new Date(now.getTime() - Math.random() * 60000).toISOString()
        },
        'github': {
          requestCount: Math.floor(Math.random() * 150) + 30,
          responseTime: Math.random() * 150 + 50,
          errorRate: Math.random() * 2,
          status: 'healthy',
          lastSync: new Date(now.getTime() - Math.random() * 120000).toISOString()
        },
        'slack': {
          requestCount: Math.floor(Math.random() * 200) + 50,
          responseTime: Math.random() * 100 + 30,
          errorRate: Math.random() * 1,
          status: 'healthy',
          lastSync: new Date(now.getTime() - Math.random() * 30000).toISOString()
        }
      },
      alerts: [
        {
          id: '1',
          type: 'warning',
          severity: 'medium',
          title: 'Cache Hit Rate Below Target',
          description: 'Cache hit rate is 75%, below the target of 80%',
          timestamp: new Date(now.getTime() - 300000).toISOString(),
          source: 'cache',
          resolved: false,
          acknowledged: false
        },
        {
          id: '2',
          type: 'error',
          severity: 'high',
          title: 'High Response Time Detected',
          description: 'Average response time increased to 250ms',
          timestamp: new Date(now.getTime() - 600000).toISOString(),
          source: 'api',
          resolved: false,
          acknowledged: true
        }
      ]
    };
  }, []);

  // Load metrics
  const loadMetrics = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      
      // In a real implementation, this would call the API
      await new Promise(resolve => setTimeout(resolve, 500));
      const mockData = generateMockMetrics();
      mockData.cache.memoryUsage.percentage = (mockData.cache.memoryUsage.used / mockData.cache.memoryUsage.available) * 100;
      
      setMetrics(mockData);
    } catch (err) {
      setError(err.message);
      toast({
        title: "Error loading metrics",
        description: err.message,
        status: "error",
        duration: 5000
      });
    } finally {
      setLoading(false);
    }
  }, [generateMockMetrics, toast]);

  // Auto-refresh effect
  useEffect(() => {
    loadMetrics();
    
    if (autoRefreshEnabled) {
      const interval = setInterval(loadMetrics, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [loadMetrics, autoRefreshEnabled, refreshInterval]);

  // Chart data processing
  const cacheChartData = useMemo(() => {
    if (!metrics) return [];
    
    const hours = timeRange.value;
    const data = [];
    
    for (let i = hours - 1; i >= 0; i--) {
      const timestamp = new Date(Date.now() - (i * 60 * 60 * 1000));
      const hitRate = 85 + Math.random() * 10;
      const responseTime = 100 + Math.random() * 50;
      
      data.push({
        timestamp: timestamp.toLocaleTimeString(),
        hitRate: parseFloat(hitRate.toFixed(2)),
        responseTime: parseFloat(responseTime.toFixed(2)),
        operations: Math.floor(Math.random() * 500) + 200
      });
    }
    
    return data;
  }, [metrics, timeRange]);

  const integrationStatusData = useMemo(() => {
    if (!metrics) return [];
    
    return Object.entries(metrics.integrations).map(([name, data]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      status: data.status,
      responseTime: data.responseTime,
      requestCount: data.requestCount,
      errorRate: data.errorRate
    }));
  }, [metrics]);

  const systemResourceData = useMemo(() => {
    if (!metrics) return [];
    
    return [
      { name: 'CPU', usage: metrics.system.cpu, total: 100 },
      { name: 'Memory', usage: metrics.system.memory, total: 100 },
      { name: 'Disk', usage: metrics.system.disk, total: 100 }
    ];
  }, [metrics]);

  const alertSeverityData = useMemo(() => {
    if (!metrics) return [];
    
    const severityCount = { critical: 0, high: 0, medium: 0, low: 0 };
    metrics.alerts.forEach(alert => {
      severityCount[alert.severity]++;
    });
    
    return Object.entries(severityCount).map(([severity, count]) => ({
      severity: severity.charAt(0).toUpperCase() + severity.slice(1),
      count,
      color: {
        critical: '#DC2626',
        high: '#EA580C',
        medium: '#D97706',
        low: '#65A30D'
      }[severity]
    }));
  }, [metrics]);

  // Handlers
  const handleOptimize = useCallback((type: string) => {
    const configs = {
      'cache': { strategy: 'aggressive', ttl: 600 },
      'memory': { gc: 'aggressive', compression: true },
      'api': { rateLimit: 1000, timeout: 30000 }
    };
    
    if (onOptimize) {
      onOptimize(type, configs[type]);
    }
    
    toast({
      title: "Optimization Started",
      description: `${type} optimization has been initiated`,
      status: "info",
      duration: 3000
    });
  }, [onOptimize, toast]);

  const handleRefresh = useCallback(() => {
    if (onRefresh) {
      onRefresh();
    }
    loadMetrics();
    
    toast({
      title: "Metrics Refreshed",
      description: "Performance metrics have been updated",
      status: "success",
      duration: 3000
    });
  }, [onRefresh, loadMetrics, toast]);

  const handleAlertAction = useCallback((alertId: string, action: string) => {
    if (metrics) {
      const updatedAlerts = metrics.alerts.map(alert => {
        if (alert.id === alertId) {
          switch (action) {
            case 'acknowledge':
              return { ...alert, acknowledged: true };
            case 'resolve':
              return { ...alert, resolved: true };
            case 'dismiss':
              return { ...alert, resolved: true, acknowledged: true };
            default:
              return alert;
          }
        }
        return alert;
      });
      
      setMetrics(prev => prev ? { ...prev, alerts: updatedAlerts } : null);
      
      toast({
        title: "Alert Updated",
        description: `Alert has been ${action}d`,
        status: "success",
        duration: 3000
      });
    }
  }, [metrics, toast]);

  const COLORS = {
    primary: '#3B82F6',
    success: '#10B981',
    warning: '#F59E0B',
    error: '#EF4444',
    info: '#6366F1'
  };

  if (loading && !metrics) {
    return (
      <Center h="400px">
        <VStack spacing={4}>
          <Spinner size="xl" color="blue.500" />
          <Text>Loading performance metrics...</Text>
        </VStack>
      </Center>
    );
  }

  if (error) {
    return (
      <Center h="400px">
        <VStack spacing={4}>
          <Alert status="error">
            <AlertIcon />
            <AlertTitle>Error Loading Metrics</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
          <Button onClick={loadMetrics} colorScheme="blue">
            Try Again
          </Button>
        </VStack>
      </Center>
    );
  }

  if (!metrics) return null;

  return (
    <Container maxW="container.xl" py={6} height={height} width={width}>
      <VStack spacing={6} h="full" align="stretch">
        {/* Header */}
        <HStack justify="space-between" w="full">
          <VStack align="start" spacing={1}>
            <Heading size="lg" color="gray.800">
              🚀 ATOM Performance Dashboard
            </Heading>
            <Text color="gray.600" fontSize="sm">
              Real-time monitoring and optimization insights
            </Text>
          </VStack>
          
          <HStack spacing={4}>
            <Select
              value={timeRange.label}
              onChange={(e) => {
                const ranges: TimeRange[] = [
                  { label: 'Last 15 Minutes', value: 15, unit: 'minutes' },
                  { label: 'Last Hour', value: 1, unit: 'hours' },
                  { label: 'Last 6 Hours', value: 6, unit: 'hours' },
                  { label: 'Last 24 Hours', value: 24, unit: 'hours' },
                  { label: 'Last 7 Days', value: 7, unit: 'days' }
                ];
                setTimeRange(ranges.find(r => r.label === e.target.value) || ranges[1]);
              }}
              w="150px"
              size="sm"
            >
              <option>Last 15 Minutes</option>
              <option>Last Hour</option>
              <option>Last 6 Hours</option>
              <option>Last 24 Hours</option>
              <option>Last 7 Days</option>
            </Select>
            
            <Switch
              isChecked={autoRefreshEnabled}
              onChange={setAutoRefreshEnabled}
              size="sm"
            >
              Auto-refresh
            </Switch>
            
            <Button
              variant="outline"
              size="sm"
              leftIcon={<FiRefreshCw />}
              onClick={handleRefresh}
              isLoading={loading}
            >
              Refresh
            </Button>
            
            <Button
              variant="outline"
              size="sm"
              leftIcon={<FiSettings />}
              onClick={settingsOnOpen}
            >
              Settings
            </Button>
          </HStack>
        </HStack>

        {/* Key Metrics */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel color="gray.600">Cache Hit Rate</StatLabel>
                <HStack>
                  <StatNumber fontSize="3xl" color={COLORS.primary}>
                    {metrics.cache.hitRate.toFixed(1)}%
                  </StatNumber>
                  {metrics.cache.hitRate >= 80 ? (
                    <FiTrendingUp color={COLORS.success} />
                  ) : (
                    <FiTrendingDown color={COLORS.warning} />
                  )}
                </HStack>
                <StatHelpText>
                  {metrics.cache.hits} hits / {metrics.cache.totalOperations} operations
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel color="gray.600">Avg Response Time</StatLabel>
                <HStack>
                  <StatNumber fontSize="3xl" color={COLORS.success}>
                    {metrics.cache.averageResponseTime.toFixed(0)}ms
                  </StatNumber>
                  <FiClock color={COLORS.info} />
                </HStack>
                <StatHelpText>
                  {metrics.cache.averageResponseTime <= 200 ? 'Optimal' : 'Needs optimization'}
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel color="gray.600">Memory Usage</StatLabel>
                <HStack>
                  <StatNumber fontSize="3xl" color={COLORS.warning}>
                    {metrics.cache.memoryUsage.percentage.toFixed(1)}%
                  </StatNumber>
                  <FiHardDrive color={COLORS.warning} />
                </HStack>
                <StatHelpText>
                  {metrics.cache.memoryUsage.used}MB / {metrics.cache.memoryUsage.available}MB
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>

          <Card>
            <CardBody>
              <Stat>
                <StatLabel color="gray.600">Active Integrations</StatLabel>
                <HStack>
                  <StatNumber fontSize="3xl" color={COLORS.success}>
                    {integrationStatusData.filter(i => i.status === 'healthy').length}
                  </StatNumber>
                  <FiZap color={COLORS.success} />
                </HStack>
                <StatHelpText>
                  {integrationStatusData.length} total integrations
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Main Content Tabs */}
        <Tabs
          index={selectedTab}
          onChange={setSelectedTab}
          variant="enclosed"
          colorScheme="blue"
          w="full"
          flex="1"
        >
          <TabList>
            <Tab><FiBarChart2 /> Performance</Tab>
            <Tab><FiGrid /> Integrations</Tab>
            <Tab><FiMonitor /> System Resources</Tab>
            <Tab><FiAlertTriangle /> Alerts</Tab>
          </TabList>

          <TabPanels flex="1">
            {/* Performance Tab */}
            <TabPanel h="full">
              <VStack spacing={6} h="full">
                {/* Cache Performance Chart */}
                <Card>
                  <CardHeader>
                    <Heading size="md">Cache Performance Trends</Heading>
                  </CardHeader>
                  <CardBody>
                    <ResponsiveContainer width="100%" height={300}>
                      <LineChart data={cacheChartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="timestamp" />
                        <YAxis yAxisId="left" />
                        <YAxis yAxisId="right" orientation="right" />
                        <Tooltip />
                        <Legend />
                        <Line
                          yAxisId="left"
                          type="monotone"
                          dataKey="hitRate"
                          stroke={COLORS.success}
                          name="Hit Rate (%)"
                          strokeWidth={2}
                        />
                        <Line
                          yAxisId="right"
                          type="monotone"
                          dataKey="responseTime"
                          stroke={COLORS.primary}
                          name="Response Time (ms)"
                          strokeWidth={2}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </CardBody>
                </Card>

                {/* Operations Chart */}
                <Card>
                  <CardHeader>
                    <Heading size="md">Cache Operations</Heading>
                  </CardHeader>
                  <CardBody>
                    <ResponsiveContainer width="100%" height={250}>
                      <AreaChart data={cacheChartData}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="timestamp" />
                        <YAxis />
                        <Tooltip />
                        <Area
                          type="monotone"
                          dataKey="operations"
                          stroke={COLORS.info}
                          fill={COLORS.info}
                          fillOpacity={0.3}
                          name="Operations"
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  </CardBody>
                </Card>

                {/* Optimization Actions */}
                <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
                  <Card>
                    <CardBody>
                      <VStack spacing={3} align="center">
                        <Icon as={FiDatabase} boxSize={10} color={COLORS.primary} />
                        <Heading size="sm">Cache Optimization</Heading>
                        <Text fontSize="sm" textAlign="center">
                          Improve cache performance with advanced strategies
                        </Text>
                        <Button
                          size="sm"
                          colorScheme="blue"
                          onClick={() => handleOptimize('cache')}
                        >
                          Optimize Cache
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardBody>
                      <VStack spacing={3} align="center">
                        <Icon as={FiCpu} boxSize={10} color={COLORS.warning} />
                        <Heading size="sm">Memory Management</Heading>
                        <Text fontSize="sm" textAlign="center">
                          Optimize memory usage and garbage collection
                        </Text>
                        <Button
                          size="sm"
                          colorScheme="orange"
                          onClick={() => handleOptimize('memory')}
                        >
                          Optimize Memory
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardBody>
                      <VStack spacing={3} align="center">
                        <Icon as={FiZap} boxSize={10} color={COLORS.success} />
                        <Heading size="sm">API Performance</Heading>
                        <Text fontSize="sm" textAlign="center">
                          Enhance API response times and throughput
                        </Text>
                        <Button
                          size="sm"
                          colorScheme="green"
                          onClick={() => handleOptimize('api')}
                        >
                          Optimize API
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Integrations Tab */}
            <TabPanel h="full">
              <VStack spacing={6} h="full">
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Integration</Th>
                        <Th>Status</Th>
                        <Th>Requests</Th>
                        <Th>Response Time</Th>
                        <Th>Error Rate</Th>
                        <Th>Last Sync</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {integrationStatusData.map((integration, index) => (
                        <Tr key={index}>
                          <Td fontWeight="medium">{integration.name}</Td>
                          <Td>
                            <Badge
                              colorScheme={
                                integration.status === 'healthy' ? 'green' :
                                integration.status === 'degraded' ? 'yellow' : 'red'
                              }
                            >
                              {integration.status}
                            </Badge>
                          </Td>
                          <Td>{integration.requestCount}</Td>
                          <Td>{integration.responseTime.toFixed(0)}ms</Td>
                          <Td>{integration.errorRate.toFixed(2)}%</Td>
                          <Td>{new Date(integration.lastSync).toLocaleString()}</Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* System Resources Tab */}
            <TabPanel h="full">
              <VStack spacing={6} h="full">
                <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
                  {/* Resource Usage Chart */}
                  <Card>
                    <CardHeader>
                      <Heading size="md">System Resources</Heading>
                    </CardHeader>
                    <CardBody>
                      <ResponsiveContainer width="100%" height={300}>
                        <BarChart data={systemResourceData}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="name" />
                          <YAxis domain={[0, 100]} />
                          <Tooltip />
                          <Bar
                            dataKey="usage"
                            fill={COLORS.primary}
                            name="Usage (%)"
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </CardBody>
                  </Card>

                  {/* Network Activity */}
                  <Card>
                    <CardHeader>
                      <Heading size="md">Network Activity</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={4}>
                        <HStack justify="space-between" w="full">
                          <Text>Inbound:</Text>
                          <Text fontWeight="bold">
                            {(metrics.system.network.inbound / 1024).toFixed(2)} MB/s
                          </Text>
                        </HStack>
                        <Progress
                          value={(metrics.system.network.inbound / 1000) * 100}
                          colorScheme="blue"
                        />
                        
                        <HStack justify="space-between" w="full">
                          <Text>Outbound:</Text>
                          <Text fontWeight="bold">
                            {(metrics.system.network.outbound / 1024).toFixed(2)} MB/s
                          </Text>
                        </HStack>
                        <Progress
                          value={(metrics.system.network.outbound / 1000) * 100}
                          colorScheme="green"
                        />
                        
                        <HStack justify="space-between" w="full">
                          <Text>Request Rate:</Text>
                          <Text fontWeight="bold">
                            {metrics.system.requestRate.toFixed(0)} req/min
                          </Text>
                        </HStack>
                        <Progress
                          value={(metrics.system.requestRate / 1000) * 100}
                          colorScheme="purple"
                        />
                        
                        <HStack justify="space-between" w="full">
                          <Text>Uptime:</Text>
                          <Text fontWeight="bold">
                            {metrics.system.uptime.toFixed(1)} days
                          </Text>
                        </HStack>
                        <Progress
                          value={(metrics.system.uptime / 30) * 100}
                          colorScheme="green"
                        />
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Alerts Tab */}
            <TabPanel h="full">
              <VStack spacing={6} h="full">
                <HStack justify="space-between" w="full">
                  <Heading size="md">Active Alerts</Heading>
                  <Button
                    leftIcon={<FiAlertTriangle />}
                    onClick={alertOnOpen}
                    colorScheme="red"
                    variant="outline"
                    size="sm"
                  >
                    View All Alerts
                  </Button>
                </HStack>

                {/* Alert Severity Distribution */}
                <Card>
                  <CardHeader>
                    <Heading size="sm">Alert Distribution</Heading>
                  </CardHeader>
                  <CardBody>
                    <ResponsiveContainer width="100%" height={200}>
                      <PieChart>
                        <Pie
                          data={alertSeverityData}
                          cx="50%"
                          cy="50%"
                          labelLine={false}
                          label={({ severity, count }) => `${severity}: ${count}`}
                          outerRadius={80}
                          fill="#8884d8"
                          dataKey="count"
                        >
                          {alertSeverityData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.color} />
                          ))}
                        </Pie>
                        <Tooltip />
                      </PieChart>
                    </ResponsiveContainer>
                  </CardBody>
                </Card>

                {/* Recent Alerts */}
                <Card>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      {metrics.alerts.slice(0, 5).map((alert, index) => (
                        <Alert
                          key={alert.id}
                          status={
                            alert.type === 'error' ? 'error' :
                            alert.type === 'warning' ? 'warning' :
                            alert.type === 'success' ? 'success' : 'info'
                          }
                          variant="subtle"
                        >
                          <VStack align="start" spacing={2}>
                            <HStack justify="space-between" w="full">
                              <Text fontWeight="bold">{alert.title}</Text>
                              <Badge
                                colorScheme={
                                  alert.severity === 'critical' ? 'red' :
                                  alert.severity === 'high' ? 'orange' :
                                  alert.severity === 'medium' ? 'yellow' : 'gray'
                                }
                                size="sm"
                              >
                                {alert.severity}
                              </Badge>
                            </HStack>
                            <Text fontSize="sm">{alert.description}</Text>
                            <HStack spacing={4} fontSize="xs" color="gray.600">
                              <FiClock />
                              <Text>{new Date(alert.timestamp).toLocaleString()}</Text>
                              <FiInfo />
                              <Text>{alert.source}</Text>
                            </HStack>
                            
                            {!alert.acknowledged && !alert.resolved && (
                              <HStack spacing={2}>
                                <Button
                                  size="xs"
                                  colorScheme="blue"
                                  onClick={() => handleAlertAction(alert.id, 'acknowledge')}
                                >
                                  Acknowledge
                                </Button>
                                <Button
                                  size="xs"
                                  colorScheme="green"
                                  onClick={() => handleAlertAction(alert.id, 'resolve')}
                                >
                                  Resolve
                                </Button>
                              </HStack>
                            )}
                          </VStack>
                        </Alert>
                      ))}
                    </VStack>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>

      {/* Settings Modal */}
      <Modal isOpen={settingsOpen} onClose={settingsOnClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Performance Settings</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Auto-refresh Interval</FormLabel>
                <Select
                  value={(refreshInterval / 1000).toString()}
                  onChange={(e) => {
                    // This would update the refresh interval
                    console.log('New interval:', e.target.value);
                  }}
                >
                  <option value="15">15 seconds</option>
                  <option value="30">30 seconds</option>
                  <option value="60">1 minute</option>
                  <option value="300">5 minutes</option>
                </Select>
              </FormControl>
              
              <FormControl>
                <FormLabel>Performance Alerts</FormLabel>
                <Switch
                  isChecked={true}
                  onChange={(e) => {
                    console.log('Performance alerts:', e.target.checked);
                  }}
                >
                  Enable performance alerts
                </Switch>
              </FormControl>
              
              <FormControl>
                <FormLabel>Auto-optimization</FormLabel>
                <Switch
                  isChecked={false}
                  onChange={(e) => {
                    console.log('Auto-optimization:', e.target.checked);
                  }}
                >
                  Enable automatic optimization
                </Switch>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="outline" onClick={settingsOnClose}>
              Cancel
            </Button>
            <Button colorScheme="blue" onClick={settingsOnClose}>
              Save Settings
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  );
};

export default AtomPerformanceDashboard;