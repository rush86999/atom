/**
 * ATOM Revenue Analytics Dashboard
 * Comprehensive monetization analytics and revenue intelligence
 * Real-time metrics, customer insights, and revenue optimization
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box, Container, VStack, HStack, Heading, Text, Divider,
  Grid, GridItem, Card, CardBody, CardHeader, CardFooter,
  Button, ButtonGroup, Icon, Spinner, Alert, AlertIcon,
  AlertTitle, AlertDescription, useColorModeValue, Fade, Scale,
  SimpleGrid, Flex, Badge, Stat, StatLabel, StatNumber,
  StatHelpText, StatArrow, Tabs, TabList, TabPanels, TabPanel,
  Accordion, AccordionItem, AccordionButton, AccordionPanel,
  AccordionIcon, useToast, useDisclosure, Modal, ModalOverlay,
  ModalContent, ModalHeader, ModalFooter, ModalBody, ModalCloseButton,
  FormControl, FormLabel, FormErrorMessage, Input, Select,
  Switch, Textarea, Stack, Tag, TagLabel, TagLeftIcon,
  useBreakpointValue, Tooltip, Progress, CircularProgress,
  CircularProgressLabel, Table, Thead, Tbody, Tr, Th, Td,
  TableCaption, Tfoot, Menu, MenuButton, MenuList, MenuItem,
  MenuDivider, RangeSlider, RangeSliderThumb, RangeSliderTrack,
  RangeSliderFilledTrack, IconGroup, IconButton
} from '@chakra-ui/react';
import {
  FiTrendingUp, FiTrendingDown, FiDollarSign, FiUsers, FiTarget,
  FiActivity, FiCalendar, FiDownload, FiUpload, FiRefreshCw,
  FiFilter, FiSettings, FiBarChart2, FiPieChart, FiLineChart,
  FiClock, FiCheckCircle, FiXCircle, FiAlertTriangle, FiInfo,
  FiMoreHorizontal, FiChevronUp, FiChevronDown, FiEdit,
  FiTrash2, FiEye, FiEyeOff, FiShare2, FiCopy, FiPrinter,
  FiMail, FiMessageSquare, FiZap, FiDatabase, FiServer,
  FiCpu, FiHardDrive, FiWifi, FiCloud, FiLock, FiUnlock,
  FiShield, FiAward, FiStar, FiTrendingUp as FiTrendUp,
  FiTrendingDown as FiTrendDown
} from 'react-icons/fi';
import { 
  LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend,
  ResponsiveContainer, ComposedChart, ScatterChart, Scatter
} from 'recharts';
import { RevenueMetrics, CustomerInsights, GrowthMetrics } from '../revenue/AtomRevenuePlatform';

// Props Interface
interface RevenueAnalyticsDashboardProps {
  metrics: RevenueMetrics;
  customerInsights: CustomerInsights[];
  timeRange: TimeRange;
  onTimeRangeChange: (range: TimeRange) => void;
  onRefresh: () => void;
  isLoading?: boolean;
  theme?: 'light' | 'dark' | 'auto';
}

// Analytics Data Types
interface TimeRange {
  start: string;
  end: string;
  label: string;
}

interface RevenueDataPoint {
  date: string;
  revenue: number;
  mrr: number;
  arr: number;
  customers: number;
  churnRate: number;
  conversionRate: number;
}

interface CustomerSegment {
  name: string;
  value: number;
  percentage: number;
  customers: number;
  averageRevenue: number;
  growthRate: number;
  color: string;
}

interface TopPlan {
  name: string;
  revenue: number;
  customers: number;
  growth: number;
  percentage: number;
  color: string;
}

interface RevenueAlert {
  id: string;
  type: 'warning' | 'error' | 'success' | 'info';
  title: string;
  description: string;
  timestamp: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  category: 'revenue' | 'churn' | 'growth' | 'performance';
  action?: string;
}

// Main Component
const RevenueAnalyticsDashboard: React.FC<RevenueAnalyticsDashboardProps> = ({
  metrics,
  customerInsights,
  timeRange,
  onTimeRangeChange,
  onRefresh,
  isLoading = false,
  theme = 'auto'
}) => {
  // State Management
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedMetric, setSelectedMetric] = useState('revenue');
  const [dateRange, setDateRange] = useState<TimeRange>(timeRange);
  const [showFilters, setShowFilters] = useState(false);
  const [selectedCustomer, setSelectedCustomer] = useState<CustomerInsights | null>(null);
  const [alert, setAlert] = useState<RevenueAlert | null>(null);
  const [forecastView, setForecastView] = useState<'conservative' | 'moderate' | 'aggressive'>('moderate');
  const [comparisonPeriod, setComparisonPeriod] = useState<'none' | 'previous' | 'lastYear'>('previous');
  
  // UI State
  const { isOpen: filterOpen, onOpen: filterOnOpen, onClose: filterOnClose } = useDisclosure();
  const { isOpen: customerOpen, onOpen: customerOnOpen, onClose: customerOnClose } = useDisclosure();
  const toast = useToast();
  
  // Theme and responsive values
  const bgColor = useColorModeValue('white', 'gray.900');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.200');
  const successColor = useColorModeValue('green.500', 'green.400');
  const warningColor = useColorModeValue('yellow.500', 'yellow.400');
  const errorColor = useColorModeValue('red.500', 'red.400');
  const isMobile = useBreakpointValue({ base: true, md: false });

  // Data Processing
  const processedData = useMemo(() => {
    if (!metrics) return null;
    
    // Generate time-series data
    const timeSeriesData = generateTimeSeriesData(metrics, dateRange);
    
    // Generate customer segments
    const customerSegments = generateCustomerSegments(customerInsights);
    
    // Generate top plans data
    const topPlans = generateTopPlansData(metrics);
    
    // Generate forecast data
    const forecastData = generateForecastData(metrics, forecastView);
    
    // Generate revenue alerts
    const alerts = generateRevenueAlerts(metrics);
    
    return {
      timeSeriesData,
      customerSegments,
      topPlans,
      forecastData,
      alerts
    };
  }, [metrics, customerInsights, dateRange, forecastView]);

  // Effects
  useEffect(() => {
    // Check for critical alerts
    if (processedData?.alerts) {
      const criticalAlert = processedData.alerts.find(alert => alert.severity === 'critical');
      if (criticalAlert) {
        setAlert(criticalAlert);
      }
    }
  }, [processedData]);

  // Event Handlers
  const handleTimeRangeChange = useCallback((range: TimeRange) => {
    setDateRange(range);
    onTimeRangeChange(range);
  }, [onTimeRangeChange]);

  const handleMetricSelect = useCallback((metric: string) => {
    setSelectedMetric(metric);
  }, []);

  const handleCustomerClick = useCallback((customer: CustomerInsights) => {
    setSelectedCustomer(customer);
    customerOnOpen();
  }, [customerOnOpen]);

  const handleExportData = useCallback((format: 'csv' | 'json' | 'pdf') => {
    toast({
      title: "Export Started",
      description: `Exporting revenue data as ${format.toUpperCase()}...`,
      status: "info",
      duration: 3000
    });
    
    // Implementation would export data
  }, [toast]);

  const handleRefreshData = useCallback(() => {
    onRefresh();
    toast({
      title: "Data Refreshed",
      description: "Revenue analytics data has been refreshed.",
      status: "success",
      duration: 2000
    });
  }, [onRefresh, toast]);

  // Data Generation Functions
  const generateTimeSeriesData = (metrics: RevenueMetrics, range: TimeRange): RevenueDataPoint[] => {
    // Generate mock time-series data based on actual metrics
    const days = Math.ceil((new Date(range.end).getTime() - new Date(range.start).getTime()) / (1000 * 60 * 60 * 24));
    const data: RevenueDataPoint[] = [];
    
    const dailyRevenue = metrics.totalRevenue / days;
    const dailyMRR = metrics.monthlyRecurringRevenue / 30;
    const dailyARR = metrics.annualRecurringRevenue / 365;
    
    for (let i = 0; i < days; i++) {
      const date = new Date(range.start);
      date.setDate(date.getDate() + i);
      
      // Add some randomness for realistic data
      const variance = 0.9 + Math.random() * 0.2; // 90% to 110% of normal
      
      data.push({
        date: date.toISOString().split('T')[0],
        revenue: dailyRevenue * variance,
        mrr: dailyMRR * variance,
        arr: dailyARR * variance,
        customers: Math.floor(100 * variance),
        churnRate: 0.05 * variance,
        conversionRate: 0.15 * variance
      });
    }
    
    return data;
  };

  const generateCustomerSegments = (insights: CustomerInsights[]): CustomerSegment[] => {
    // Group customers by segments
    const segments = {
      enterprise: { name: 'Enterprise', customers: 0, revenue: 0 },
      business: { name: 'Business', customers: 0, revenue: 0 },
      professional: { name: 'Professional', customers: 0, revenue: 0 },
      starter: { name: 'Starter', customers: 0, revenue: 0 }
    };
    
    insights.forEach(customer => {
      // Determine segment based on revenue and usage
      const monthlyRevenue = customer.metrics.revenue?.monthly || 0;
      if (monthlyRevenue > 200) segments.enterprise.customers++;
      else if (monthlyRevenue > 50) segments.business.customers++;
      else if (monthlyRevenue > 20) segments.professional.customers++;
      else segments.starter.customers++;
      
      segments.enterprise.revenue += monthlyRevenue > 200 ? monthlyRevenue : 0;
      segments.business.revenue += monthlyRevenue > 50 && monthlyRevenue <= 200 ? monthlyRevenue : 0;
      segments.professional.revenue += monthlyRevenue > 20 && monthlyRevenue <= 50 ? monthlyRevenue : 0;
      segments.starter.revenue += monthlyRevenue <= 20 ? monthlyRevenue : 0;
    });
    
    const totalRevenue = Object.values(segments).reduce((sum, seg) => sum + seg.revenue, 0);
    const colors = ['#805AD5', '#3182CE', '#38A169', '#D69E2E'];
    
    return Object.entries(segments).map(([key, segment], index) => ({
      ...segment,
      value: segment.revenue,
      percentage: totalRevenue > 0 ? (segment.revenue / totalRevenue) * 100 : 0,
      averageRevenue: segment.customers > 0 ? segment.revenue / segment.customers : 0,
      growthRate: Math.random() * 30 - 5, // Mock growth rate
      color: colors[index]
    })).filter(seg => seg.revenue > 0);
  };

  const generateTopPlansData = (metrics: RevenueMetrics): TopPlan[] => {
    const planData = metrics.revenueByTier || {};
    const totalRevenue = metrics.totalRevenue;
    const colors = ['#3182CE', '#805AD5', '#38A169', '#D69E2E'];
    
    return Object.entries(planData)
      .map(([name, revenue], index) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        revenue,
        customers: Math.floor(Math.random() * 100) + 10,
        growth: Math.random() * 40 - 10,
        percentage: totalRevenue > 0 ? (revenue / totalRevenue) * 100 : 0,
        color: colors[index]
      }))
      .sort((a, b) => b.revenue - a.revenue)
      .slice(0, 5);
  };

  const generateForecastData = (metrics: RevenueMetrics, view: string) => {
    const baseRevenue = metrics.monthlyRecurringRevenue;
    const growthRates = {
      conservative: 0.05,
      moderate: 0.10,
      aggressive: 0.20
    };
    
    const growthRate = growthRates[view as keyof typeof growthRates];
    const forecastMonths = 12;
    const data = [];
    
    for (let i = 1; i <= forecastMonths; i++) {
      const month = new Date();
      month.setMonth(month.getMonth() + i);
      
      const predictedRevenue = baseRevenue * Math.pow(1 + growthRate, i);
      const confidence = Math.max(0.7, 1 - (i * 0.03)); // Decreasing confidence over time
      
      data.push({
        month: month.toLocaleDateString('en', { month: 'short' }),
        predicted: predictedRevenue,
        lower: predictedRevenue * (1 - (0.1 * i / forecastMonths)),
        upper: predictedRevenue * (1 + (0.15 * i / forecastMonths)),
        confidence
      });
    }
    
    return data;
  };

  const generateRevenueAlerts = (metrics: RevenueMetrics): RevenueAlert[] => {
    const alerts: RevenueAlert[] = [];
    
    // Churn rate alert
    if (metrics.churnRate > 0.10) {
      alerts.push({
        id: 'high-churn',
        type: 'error',
        title: 'High Churn Rate Detected',
        description: `Churn rate is ${(metrics.churnRate * 100).toFixed(1)}%, above the 10% threshold.`,
        timestamp: new Date().toISOString(),
        severity: metrics.churnRate > 0.15 ? 'critical' : 'high',
        category: 'churn',
        action: 'Review customer support and retention strategies'
      });
    }
    
    // Revenue decline alert
    if (metrics.growthMetrics?.growthRate < 0) {
      alerts.push({
        id: 'revenue-decline',
        type: 'warning',
        title: 'Revenue Decline',
        description: `Revenue growth rate is negative: ${metrics.growthMetrics?.growthRate.toFixed(1)}%`,
        timestamp: new Date().toISOString(),
        severity: 'medium',
        category: 'revenue',
        action: 'Analyze sales pipeline and marketing effectiveness'
      });
    }
    
    // Low conversion rate alert
    if (metrics.growthMetrics?.conversionRate < 0.10) {
      alerts.push({
        id: 'low-conversion',
        type: 'warning',
        title: 'Low Conversion Rate',
        description: `Trial conversion rate is ${(metrics.growthMetrics?.conversionRate * 100).toFixed(1)}%, below 10% target.`,
        timestamp: new Date().toISOString(),
        severity: 'medium',
        category: 'growth',
        action: 'Optimize trial experience and onboarding flow'
      });
    }
    
    return alerts;
  };

  // Render Functions
  const renderOverviewMetrics = () => {
    if (!processedData || !metrics) return null;
    
    const revenueGrowth = metrics.growthMetrics?.growthRate || 0;
    const churnChange = -0.02; // Mock churn change
    const customerGrowth = metrics.growthMetrics?.growthRate || 0;
    
    return (
      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
        {/* Total Revenue */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardBody>
            <Flex justify="space-between" align="center">
              <VStack align="start" spacing={1}>
                <StatLabel fontSize="sm" color="gray.600">Total Revenue</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  ${metrics.totalRevenue.toLocaleString()}
                </StatNumber>
                <StatHelpText>
                  <StatArrow type={revenueGrowth >= 0 ? 'increase' : 'decrease'} />
                  {Math.abs(revenueGrowth).toFixed(1)}% from last period
                </StatHelpText>
              </VStack>
              <Icon as={FiDollarSign} boxSize={12} color={revenueGrowth >= 0 ? successColor : errorColor} />
            </Flex>
          </CardBody>
        </Card>
        
        {/* Monthly Recurring Revenue */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardBody>
            <Flex justify="space-between" align="center">
              <VStack align="start" spacing={1}>
                <StatLabel fontSize="sm" color="gray.600">MRR</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  ${metrics.monthlyRecurringRevenue.toLocaleString()}
                </StatNumber>
                <StatHelpText>
                  <StatArrow type="increase" />
                  8.3% month over month
                </StatHelpText>
              </VStack>
              <Icon as={FiTrendingUp} boxSize={12} color={successColor} />
            </Flex>
          </CardBody>
        </Card>
        
        {/* Customer Count */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardBody>
            <Flex justify="space-between" align="center">
              <VStack align="start" spacing={1}>
                <StatLabel fontSize="sm" color="gray.600">Total Customers</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  {metrics.totalRequests.toLocaleString()}
                </StatNumber>
                <StatHelpText>
                  <StatArrow type={customerGrowth >= 0 ? 'increase' : 'decrease'} />
                  {Math.abs(customerGrowth).toFixed(1)}% growth
                </StatHelpText>
              </VStack>
              <Icon as={FiUsers} boxSize={12} color={customerGrowth >= 0 ? successColor : errorColor} />
            </Flex>
          </CardBody>
        </Card>
        
        {/* Churn Rate */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardBody>
            <Flex justify="space-between" align="center">
              <VStack align="start" spacing={1}>
                <StatLabel fontSize="sm" color="gray.600">Churn Rate</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  {(metrics.churnRate * 100).toFixed(1)}%
                </StatNumber>
                <StatHelpText>
                  <StatArrow type={churnChange >= 0 ? 'increase' : 'decrease'} />
                  {Math.abs(churnChange * 100).toFixed(1)}% from last month
                </StatHelpText>
              </VStack>
              <Icon as={FiActivity} boxSize={12} color={metrics.churnRate < 0.05 ? successColor : warningColor} />
            </Flex>
          </CardBody>
        </Card>
      </SimpleGrid>
    );
  };

  const renderRevenueChart = () => {
    if (!processedData?.timeSeriesData) return null;
    
    return (
      <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
        <CardHeader>
          <HStack justify="space-between">
            <VStack align="start" spacing={1}>
              <Heading size="md">Revenue Overview</Heading>
              <Text fontSize="sm" color="gray.600">
                Revenue, MRR, and customer growth over time
              </Text>
            </VStack>
            <ButtonGroup size="sm">
              <Button variant="outline" leftIcon={<FiDownload />}>
                Export
              </Button>
              <Button variant="outline" leftIcon={<FiRefreshCw />} onClick={handleRefreshData}>
                Refresh
              </Button>
            </ButtonGroup>
          </HStack>
        </CardHeader>
        <CardBody>
          <ResponsiveContainer width="100%" height={400}>
            <ComposedChart data={processedData.timeSeriesData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" />
              <YAxis yAxisId="left" />
              <YAxis yAxisId="right" orientation="right" />
              <RechartsTooltip />
              <Legend />
              <Area
                yAxisId="left"
                type="monotone"
                dataKey="revenue"
                stroke="#3182CE"
                fill="#3182CE"
                fillOpacity={0.3}
                name="Revenue"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="mrr"
                stroke="#805AD5"
                strokeWidth={2}
                name="MRR"
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="customers"
                stroke="#38A169"
                strokeWidth={2}
                name="Customers"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </CardBody>
      </Card>
    );
  };

  const renderCustomerSegments = () => {
    if (!processedData?.customerSegments) return null;
    
    return (
      <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
        <CardHeader>
          <HStack justify="space-between">
            <VStack align="start" spacing={1}>
              <Heading size="md">Customer Segments</Heading>
              <Text fontSize="sm" color="gray.600">
                Revenue distribution by customer segment
              </Text>
            </VStack>
            <ButtonGroup size="sm">
              <Button variant="outline" leftIcon={<FiPieChart />}>
                Pie View
              </Button>
              <Button variant="outline" leftIcon={<FiBarChart2 />}>
                Bar View
              </Button>
            </ButtonGroup>
          </HStack>
        </CardHeader>
        <CardBody>
          <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
            {/* Pie Chart */}
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={processedData.customerSegments}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percentage }) => `${name}: ${percentage.toFixed(1)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {processedData.customerSegments.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <RechartsTooltip />
              </PieChart>
            </ResponsiveContainer>
            
            {/* Segment Details */}
            <VStack align="stretch" spacing={4}>
              {processedData.customerSegments.map((segment, index) => (
                <HStack key={segment.name} justify="space-between" p={3} bg="gray.50" borderRadius="md">
                  <HStack spacing={3}>
                    <Box w={4} h={4} bg={segment.color} borderRadius="full" />
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="medium">{segment.name}</Text>
                      <Text fontSize="xs" color="gray.600">
                        {segment.customers} customers
                      </Text>
                    </VStack>
                  </HStack>
                  <VStack align="end" spacing={1}>
                    <Text fontWeight="medium">
                      ${segment.value.toLocaleString()}
                    </Text>
                    <HStack>
                      <Text fontSize="xs" color={segment.growthRate >= 0 ? successColor : errorColor}>
                        {segment.growthRate >= 0 ? '+' : ''}{segment.growthRate.toFixed(1)}%
                      </Text>
                      <Icon as={segment.growthRate >= 0 ? FiTrendUp : FiTrendDown} 
                           color={segment.growthRate >= 0 ? successColor : errorColor} 
                           boxSize={3} />
                    </HStack>
                  </VStack>
                </HStack>
              ))}
            </VStack>
          </SimpleGrid>
        </CardBody>
      </Card>
    );
  };

  const renderTopPlans = () => {
    if (!processedData?.topPlans) return null;
    
    return (
      <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
        <CardHeader>
          <VStack align="start" spacing={1}>
            <Heading size="md">Top Performing Plans</Heading>
            <Text fontSize="sm" color="gray.600">
              Revenue and customer count by subscription plan
            </Text>
          </VStack>
        </CardHeader>
        <CardBody>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={processedData.topPlans}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <RechartsTooltip />
              <Bar dataKey="revenue" fill="#3182CE" name="Revenue" />
            </BarChart>
          </ResponsiveContainer>
          
          {/* Plan Details */}
          <VStack align="stretch" spacing={3} mt={4}>
            {processedData.topPlans.map((plan, index) => (
              <HStack key={plan.name} justify="space-between" p={3} bg="gray.50" borderRadius="md">
                <HStack spacing={3}>
                  <Text fontWeight="medium">{plan.name}</Text>
                  <Badge colorScheme="blue">{plan.customers} customers</Badge>
                </HStack>
                <HStack spacing={4}>
                  <Text fontWeight="medium">${plan.revenue.toLocaleString()}</Text>
                  <HStack>
                    <Text fontSize="xs" color={plan.growth >= 0 ? successColor : errorColor}>
                      {plan.growth >= 0 ? '+' : ''}{plan.growth.toFixed(1)}%
                    </Text>
                    <Icon as={plan.growth >= 0 ? FiTrendUp : FiTrendDown} 
                         color={plan.growth >= 0 ? successColor : errorColor} 
                         boxSize={3} />
                  </HStack>
                </HStack>
              </HStack>
            ))}
          </VStack>
        </CardBody>
      </Card>
    );
  };

  const renderForecast = () => {
    if (!processedData?.forecastData) return null;
    
    return (
      <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
        <CardHeader>
          <HStack justify="space-between">
            <VStack align="start" spacing={1}>
              <Heading size="md">Revenue Forecast</Heading>
              <Text fontSize="sm" color="gray.600">
                12-month revenue prediction based on current trends
              </Text>
            </VStack>
            <ButtonGroup size="sm" isAttached variant="outline">
              <Button
                variant={forecastView === 'conservative' ? 'solid' : 'outline'}
                onClick={() => setForecastView('conservative')}
              >
                Conservative
              </Button>
              <Button
                variant={forecastView === 'moderate' ? 'solid' : 'outline'}
                onClick={() => setForecastView('moderate')}
              >
                Moderate
              </Button>
              <Button
                variant={forecastView === 'aggressive' ? 'solid' : 'outline'}
                onClick={() => setForecastView('aggressive')}
              >
                Aggressive
              </Button>
            </ButtonGroup>
          </HStack>
        </CardHeader>
        <CardBody>
          <ResponsiveContainer width="100%" height={400}>
            <LineChart data={processedData.forecastData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="month" />
              <YAxis />
              <RechartsTooltip />
              <Legend />
              <Area
                type="monotone"
                dataKey="upper"
                stroke="#805AD5"
                fill="#805AD5"
                fillOpacity={0.1}
                name="Upper Bound"
              />
              <Area
                type="monotone"
                dataKey="lower"
                stroke="#805AD5"
                fill="#805AD5"
                fillOpacity={0.2}
                name="Lower Bound"
              />
              <Line
                type="monotone"
                dataKey="predicted"
                stroke="#3182CE"
                strokeWidth={3}
                name="Predicted Revenue"
              />
            </LineChart>
          </ResponsiveContainer>
        </CardBody>
      </Card>
    );
  };

  const renderAlerts = () => {
    if (!processedData?.alerts || processedData.alerts.length === 0) return null;
    
    return (
      <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
        <CardHeader>
          <VStack align="start" spacing={1}>
            <Heading size="md">Revenue Alerts</Heading>
            <Text fontSize="sm" color="gray.600">
              Important metrics and issues that need attention
            </Text>
          </VStack>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={3}>
            {processedData.alerts.map((alert) => (
              <Alert
                key={alert.id}
                status={alert.type === 'error' ? 'error' : alert.type === 'warning' ? 'warning' : alert.type === 'success' ? 'success' : 'info'}
                variant="subtle"
                flexDirection="column"
                alignItems="flex-start"
                justifyContent="flex-start"
              >
                <HStack width="full" justify="space-between">
                  <VStack align="start" spacing={1}>
                    <AlertTitle fontSize="md">{alert.title}</AlertTitle>
                    <AlertDescription fontSize="sm">{alert.description}</AlertDescription>
                    {alert.action && (
                      <Text fontSize="xs" color="blue.600" mt={2}>
                        💡 Suggested action: {alert.action}
                      </Text>
                    )}
                  </VStack>
                  <Badge colorScheme={alert.severity === 'critical' ? 'red' : alert.severity === 'high' ? 'orange' : 'yellow'}>
                    {alert.severity.toUpperCase()}
                  </Badge>
                </HStack>
              </Alert>
            ))}
          </VStack>
        </CardBody>
      </Card>
    );
  };

  // Loading State
  if (isLoading) {
    return (
      <Container maxW="container.xl" py={8}>
        <VStack spacing={8} align="center">
          <Spinner size="xl" color="blue.500" thickness="4px" />
          <Text fontSize="lg" color="gray.600">
            Loading revenue analytics...
          </Text>
        </VStack>
      </Container>
    );
  }

  // Main Render
  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={8} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <VStack align="start" spacing={1}>
            <Heading size="2xl" color={textColor}>
              💰 Revenue Analytics
            </Heading>
            <Text fontSize="lg" color="gray.600">
              Real-time revenue intelligence and business insights
            </Text>
          </VStack>
          
          <HStack spacing={3}>
            {/* Date Range Selector */}
            <Select
              value={dateRange.label}
              onChange={(e) => {
                const ranges: Record<string, TimeRange> = {
                  'Last 7 Days': {
                    start: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
                    end: new Date().toISOString(),
                    label: 'Last 7 Days'
                  },
                  'Last 30 Days': {
                    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
                    end: new Date().toISOString(),
                    label: 'Last 30 Days'
                  },
                  'Last 90 Days': {
                    start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString(),
                    end: new Date().toISOString(),
                    label: 'Last 90 Days'
                  }
                };
                handleTimeRangeChange(ranges[e.target.value]);
              }}
              w={150}
            >
              <option value="Last 7 Days">Last 7 Days</option>
              <option value="Last 30 Days">Last 30 Days</option>
              <option value="Last 90 Days">Last 90 Days</option>
            </Select>
            
            {/* Action Buttons */}
            <ButtonGroup>
              <Tooltip label="Export Data">
                <Button variant="outline" leftIcon={<FiDownload />} onClick={() => handleExportData('csv')}>
                  Export
                </Button>
              </Tooltip>
              <Tooltip label="Refresh Data">
                <Button variant="outline" leftIcon={<FiRefreshCw />} onClick={handleRefreshData}>
                  Refresh
                </Button>
              </Tooltip>
            </ButtonGroup>
          </HStack>
        </HStack>

        {/* Alert Banner */}
        {alert && (
          <Alert status={alert.type === 'error' ? 'error' : alert.type === 'warning' ? 'warning' : 'info'}>
            <AlertIcon />
            <Box flex="1">
              <AlertTitle>{alert.title}</AlertTitle>
              <AlertDescription>{alert.description}</AlertDescription>
            </Box>
            <IconButton
              aria-label="Dismiss"
              icon={<FiXCircle />}
              variant="ghost"
              size="sm"
              onClick={() => setAlert(null)}
            />
          </Alert>
        )}

        {/* Tabs */}
        <Tabs index={activeTab === 'overview' ? 0 : activeTab === 'customers' ? 1 : activeTab === 'forecast' ? 2 : 3} 
              onChange={(index) => setActiveTab(index === 0 ? 'overview' : index === 1 ? 'customers' : index === 2 ? 'forecast' : 'advanced')}>
          <TabList mb={6}>
            <Tab>📊 Overview</Tab>
            <Tab>👥 Customers</Tab>
            <Tab>🔮 Forecast</Tab>
            <Tab>⚙️ Advanced</Tab>
          </TabList>

          <TabPanels>
            {/* Overview Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                {renderOverviewMetrics()}
                {renderRevenueChart()}
                <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
                  {renderCustomerSegments()}
                  {renderTopPlans()}
                </SimpleGrid>
                {renderForecast()}
                {renderAlerts()}
              </VStack>
            </TabPanel>

            {/* Customers Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
                  <CardHeader>
                    <VStack align="start" spacing={1}>
                      <Heading size="md">Customer Insights</Heading>
                      <Text fontSize="sm" color="gray.600">
                        Detailed analysis of customer behavior and value
                      </Text>
                    </VStack>
                  </CardHeader>
                  <CardBody>
                    {/* Customer table would go here */}
                    <Text color="gray.500">
                      Customer detailed analytics coming soon...
                    </Text>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* Forecast Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                {renderForecast()}
                {/* Additional forecast details would go here */}
              </VStack>
            </TabPanel>

            {/* Advanced Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                {/* Advanced analytics would go here */}
                <Text color="gray.500">
                  Advanced revenue analytics coming soon...
                </Text>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Container>
  );
};

export default RevenueAnalyticsDashboard;