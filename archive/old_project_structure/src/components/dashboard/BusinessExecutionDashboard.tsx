/**
 * ATOM Business Execution Dashboard
 * Real-time business metrics, revenue tracking, and market execution monitoring
 * Provides complete visibility into ATOM business performance and growth
 */

import React, { useState, useEffect } from 'react';
import {
  Box, VStack, HStack, Grid, GridItem,
  Card, CardHeader, CardBody,
  Heading, Text, Stat, StatLabel, StatNumber, StatHelpText, StatArrow,
  SimpleGrid, Progress, Badge, Button, ButtonGroup,
  Table, Thead, Tbody, Tr, Th, Td, TableContainer,
  Tabs, TabList, TabPanels, Tab, TabPanel,
  useColorModeValue, useToast, useBreakpointValue,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell, BarChart, Bar
} from '@chakra-ui/react';
import { FiTrendingUp, FiTrendingDown, FiDollarSign, FiUsers, FiActivity, FiTarget, FiAward, FiClock } from 'react-icons/fi';

// Business Metrics Types
interface BusinessMetrics {
  revenue: {
    mrr: number;
    arr: number;
    monthlyGrowth: number;
    yearlyGrowth: number;
    todayRevenue: number;
    todaySignups: number;
    todayCustomers: number;
  };
  customers: {
    total: number;
    new: number;
    churned: number;
    retention: number;
    expansion: number;
    trialToPaid: number;
    enterprise: number;
    smb: number;
    professional: number;
    starter: number;
  };
  acquisition: {
    monthlyBudget: number;
    monthlySpend: number;
    cac: number;
    ltv: number;
    ltvCacRatio: number;
    roi: number;
    conversionRate: number;
    trialSignups: number;
    websiteVisitors: number;
  };
  sales: {
    pipeline: number;
    newLeads: number;
    qualifiedLeads: number;
    conversionRate: number;
    averageDealSize: number;
    salesCycle: number;
    winRate: number;
    enterpriseDeals: number;
    teamQuota: number;
    teamPerformance: number;
  };
  support: {
    tickets: number;
    responseTime: number;
    resolutionTime: number;
    satisfaction: number;
    churnRisk: number;
    expansionOpportunities: number;
    healthScore: number;
    nps: number;
  };
  product: {
    maus: number;
    daus: number;
    engagement: number;
    featureAdoption: Record<string, number>;
    workflows: number;
    integrations: number;
    uptime: number;
    performance: number;
  };
  market: {
    share: number;
    competition: Record<string, number>;
    positioning: string;
    brandAwareness: number;
    sentiment: number;
    ranking: Record<string, number>;
  };
}

// Target Metrics
interface TargetMetrics {
  revenue: {
    monthlyTarget: number;
    yearlyTarget: number;
    growthTarget: number;
  };
  customers: {
    monthlyTarget: number;
    yearlyTarget: number;
    retentionTarget: number;
  };
  acquisition: {
    monthlyTarget: number;
    cacTarget: number;
    ltvTarget: number;
    conversionTarget: number;
  };
  sales: {
    monthlyTarget: number;
    winRateTarget: number;
    cycleTarget: number;
  };
  support: {
    responseTarget: number;
    resolutionTarget: number;
    satisfactionTarget: number;
  };
}

// Charts Data
interface ChartData {
  timeline: string[];
  revenue: number[];
  customers: number[];
  acquisition: number[];
  conversion: number[];
  ltv: number[];
  cac: number[];
  pipeline: number[];
}

const BusinessExecutionDashboard: React.FC = () => {
  const bgColor = useColorModeValue('white', 'gray.900');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.200');
  const successColor = useColorModeValue('green.500', 'green.400');
  const warningColor = useColorModeValue('yellow.500', 'yellow.400');
  const errorColor = useColorModeValue('red.500', 'red.400');
  const isMobile = useBreakpointValue({ base: true, md: false });
  
  const toast = useToast();
  const [metrics, setMetrics] = useState<BusinessMetrics | null>(null);
  const [targets, setTargets] = useState<TargetMetrics | null>(null);
  const [chartData, setChartData] = useState<ChartData | null>(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('30d');
  const [refreshInterval, setRefreshInterval] = useState(30); // seconds

  // Mock data for demonstration
  useEffect(() => {
    const generateMockData = () => {
      const mockMetrics: BusinessMetrics = {
        revenue: {
          mrr: 50000,
          arr: 600000,
          monthlyGrowth: 15.2,
          yearlyGrowth: 125.4,
          todayRevenue: 2500,
          todaySignups: 12,
          todayCustomers: 8
        },
        customers: {
          total: 1250,
          new: 125,
          churned: 15,
          retention: 94.2,
          expansion: 8.5,
          trialToPaid: 18.5,
          enterprise: 35,
          smb: 150,
          professional: 500,
          starter: 565
        },
        acquisition: {
          monthlyBudget: 75000,
          monthlySpend: 68000,
          cac: 45,
          ltv: 1200,
          ltvCacRatio: 26.7,
          roi: 8.5,
          conversionRate: 12.5,
          trialSignups: 380,
          websiteVisitors: 30000
        },
        sales: {
          pipeline: 450000,
          newLeads: 320,
          qualifiedLeads: 85,
          conversionRate: 28.5,
          averageDealSize: 15000,
          salesCycle: 42,
          winRate: 32.5,
          enterpriseDeals: 12,
          teamQuota: 150000,
          teamPerformance: 78.5
        },
        support: {
          tickets: 145,
          responseTime: 1.8,
          resolutionTime: 12.5,
          satisfaction: 4.6,
          churnRisk: 12.5,
          expansionOpportunities: 28,
          healthScore: 85.2,
          nps: 52
        },
        product: {
          maus: 8500,
          daus: 3200,
          engagement: 78.5,
          featureAdoption: {
            workflows: 82.5,
            integrations: 75.2,
            ai: 68.5,
            automation: 85.5,
            analytics: 45.2
          },
          workflows: 12500,
          integrations: 8900,
          uptime: 99.9,
          performance: 94.5
        },
        market: {
          share: 1.2,
          competition: {
            zapier: 35.5,
            make: 18.2,
            integromat: 12.8,
            tray: 8.5,
            automate: 6.2
          },
          positioning: 'AI-Powered Automation with Comprehensive Integration Suite',
          brandAwareness: 15.5,
          sentiment: 78.5,
          ranking: {
            automation: 8,
            integration: 5,
            ai: 12,
            enterprise: 15
          }
        }
      };

      const mockTargets: TargetMetrics = {
        revenue: {
          monthlyTarget: 50000,
          yearlyTarget: 600000,
          growthTarget: 20.0
        },
        customers: {
          monthlyTarget: 150,
          yearlyTarget: 2000,
          retentionTarget: 95.0
        },
        acquisition: {
          monthlyTarget: 500,
          cacTarget: 50,
          ltvTarget: 1000,
          conversionTarget: 15.0
        },
        sales: {
          monthlyTarget: 50000,
          winRateTarget: 35.0,
          cycleTarget: 35.0
        },
        support: {
          responseTarget: 2.0,
          resolutionTarget: 24.0,
          satisfactionTarget: 4.5
        }
      };

      const mockChartData: ChartData = {
        timeline: ['Day 1', 'Day 7', 'Day 14', 'Day 21', 'Day 30'],
        revenue: [35000, 42000, 48000, 52000, 50000],
        customers: [950, 1050, 1150, 1200, 1250],
        acquisition: [50, 75, 85, 95, 125],
        conversion: [8.5, 10.2, 11.5, 12.1, 12.5],
        ltv: [950, 1050, 1120, 1180, 1200],
        cac: [65, 58, 52, 48, 45],
        pipeline: [350000, 380000, 420000, 440000, 450000]
      };

      return { metrics: mockMetrics, targets: mockTargets, chartData: mockChartData };
    };

    const loadData = async () => {
      setLoading(true);
      try {
        // Simulate API call
        await new Promise(resolve => setTimeout(resolve, 1000));
        const data = generateMockData();
        setMetrics(data.metrics);
        setTargets(data.targets);
        setChartData(data.chartData);
      } catch (error) {
        toast({
          title: "Error loading business metrics",
          description: "Failed to load business execution data",
          status: "error",
          duration: 3000
        });
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [timeRange, toast]);

  // Auto-refresh
  useEffect(() => {
    const interval = setInterval(() => {
      window.location.reload();
    }, refreshInterval * 1000);

    return () => clearInterval(interval);
  }, [refreshInterval]);

  if (loading || !metrics || !targets || !chartData) {
    return (
      <Box p={8} textAlign="center">
        <Text fontSize="lg" color="gray.600">
          Loading ATOM Business Execution Dashboard...
        </Text>
      </Box>
    );
  }

  // Helper functions
  const getProgressColor = (value: number, target: number) => {
    const percentage = (value / target) * 100;
    if (percentage >= 100) return successColor;
    if (percentage >= 75) return warningColor;
    return errorColor;
  };

  const getProgressValue = (value: number, target: number) => {
    return Math.min((value / target) * 100, 100);
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0
    }).format(value);
  };

  const formatNumber = (value: number) => {
    return new Intl.NumberFormat('en-US').format(value);
  };

  return (
    <Box bg={bgColor} minH="100vh" p={4}>
      {/* Header */}
      <VStack align="stretch" spacing={6}>
        <HStack justify="space-between" align="center">
          <VStack align="start" spacing={1}>
            <Heading size="2xl" color={textColor}>
              🚀 ATOM Business Execution Dashboard
            </Heading>
            <Text fontSize="lg" color="gray.600">
              Real-time business metrics, revenue tracking, and market execution
            </Text>
          </VStack>
          
          <HStack spacing={3}>
            <ButtonGroup size="sm" isAttached variant="outline">
              <Button onClick={() => setTimeRange('7d')}>7D</Button>
              <Button onClick={() => setTimeRange('30d')}>30D</Button>
              <Button onClick={() => setTimeRange('90d')}>90D</Button>
              <Button onClick={() => setTimeRange('365d')}>1Y</Button>
            </ButtonGroup>
            
            <ButtonGroup size="sm" variant="outline">
              <Button leftIcon={<FiTrendingUp />}>Auto Refresh</Button>
              <Button onClick={() => window.location.reload()}>
                Refresh Now
              </Button>
            </ButtonGroup>
          </HStack>
        </HStack>

        {/* Key Metrics Overview */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
          {/* Revenue Metrics */}
          <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.600">Monthly Recurring Revenue</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  {formatCurrency(metrics.revenue.mrr)}
                </StatNumber>
                <StatHelpText>
                  <StatArrow type={metrics.revenue.monthlyGrowth >= 0 ? 'increase' : 'decrease'} />
                  {Math.abs(metrics.revenue.monthlyGrowth).toFixed(1)}% from last month
                </StatHelpText>
              </Stat>
              <Progress
                mt={4}
                value={getProgressValue(metrics.revenue.mrr, targets.revenue.monthlyTarget)}
                color={getProgressColor(metrics.revenue.mrr, targets.revenue.monthlyTarget)}
              />
              <Text fontSize="xs" color="gray.600" mt={1}>
                Target: {formatCurrency(targets.revenue.monthlyTarget)}
              </Text>
            </CardBody>
          </Card>

          {/* Customer Metrics */}
          <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.600">Total Customers</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  {formatNumber(metrics.customers.total)}
                </StatNumber>
                <StatHelpText>
                  <FiUsers /> {formatNumber(metrics.customers.new)} new this month
                </StatHelpText>
              </Stat>
              <Progress
                mt={4}
                value={getProgressValue(metrics.customers.total, targets.customers.yearlyTarget)}
                color={getProgressColor(metrics.customers.total, targets.customers.yearlyTarget)}
              />
              <Text fontSize="xs" color="gray.600" mt={1}>
                Target: {formatNumber(targets.customers.yearlyTarget)}
              </Text>
            </CardBody>
          </Card>

          {/* Acquisition Metrics */}
          <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.600">Customer Acquisition Cost</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  ${metrics.acquisition.cac}
                </StatNumber>
                <StatHelpText>
                  <StatArrow type={metrics.acquisition.cac <= targets.acquisition.cacTarget ? 'decrease' : 'increase'} />
                  LTV:CAC {metrics.acquisition.ltvCacRatio.toFixed(1)}:1
                </StatHelpText>
              </Stat>
              <Progress
                mt={4}
                value={getProgressValue(targets.acquisition.cacTarget, metrics.acquisition.cac)}
                color={getProgressColor(targets.acquisition.cacTarget, metrics.acquisition.cac)}
              />
              <Text fontSize="xs" color="gray.600" mt={1}>
                Target: ${targets.acquisition.cacTarget}
              </Text>
            </CardBody>
          </Card>

          {/* Sales Pipeline */}
          <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.600">Sales Pipeline</StatLabel>
                <StatNumber fontSize="2xl" fontWeight="bold">
                  {formatCurrency(metrics.sales.pipeline)}
                </StatNumber>
                <StatHelpText>
                  <FiTarget /> {formatNumber(metrics.sales.newLeads)} new leads
                </StatHelpText>
              </Stat>
              <Progress
                mt={4}
                value={getProgressValue(metrics.sales.teamPerformance, 100)}
                color={getProgressColor(metrics.sales.teamPerformance, 100)}
              />
              <Text fontSize="xs" color="gray.600" mt={1}>
                Team Performance: {metrics.sales.teamPerformance.toFixed(1)}%
              </Text>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Detailed Metrics Tabs */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardHeader>
            <Heading size="md">Detailed Business Metrics</Heading>
          </CardHeader>
          <CardBody>
            <Tabs variant="enclosed">
              <TabList>
                <Tab>📊 Revenue</Tab>
                <Tab>👥 Customers</Tab>
                <Tab>🎯 Acquisition</Tab>
                <Tab>💼 Sales</Tab>
                <Tab>🎧 Support</Tab>
                <Tab>🚀 Product</Tab>
                <Tab>📈 Market</Tab>
              </TabList>

              <TabPanels>
                {/* Revenue Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Annual Recurring Revenue</Text>
                        <Text fontSize="2xl" color={successColor}>{formatCurrency(metrics.revenue.arr)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Yearly Growth Rate</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.revenue.yearlyGrowth.toFixed(1)}%</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Today's Revenue</Text>
                        <Text fontSize="2xl" color={successColor}>{formatCurrency(metrics.revenue.todayRevenue)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Today's Signups</Text>
                        <Text fontSize="2xl" color={successColor}>{formatNumber(metrics.revenue.todaySignups)}</Text>
                      </Box>
                    </Grid>
                    
                    <Box h={300}>
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData.timeline.map((date, i) => ({
                          date,
                          revenue: chartData.revenue[i],
                          target: targets.revenue.monthlyTarget
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Line type="monotone" dataKey="revenue" stroke="#3182CE" name="MRR" />
                          <Line type="monotone" dataKey="target" stroke="#805AD5" strokeDasharray="5 5" name="Target" />
                        </LineChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>

                {/* Customers Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>New Customers (Month)</Text>
                        <Text fontSize="2xl" color={successColor}>{formatNumber(metrics.customers.new)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Churned Customers (Month)</Text>
                        <Text fontSize="2xl" color={errorColor}>{formatNumber(metrics.customers.churned)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Retention Rate</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.customers.retention.toFixed(1)}%</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Expansion Revenue</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.customers.expansion.toFixed(1)}%</Text>
                      </Box>
                    </Grid>
                    
                    <Box h={300}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={[
                              { name: 'Enterprise', value: metrics.customers.enterprise, color: '#805AD5' },
                              { name: 'Business', value: metrics.customers.smb, color: '#3182CE' },
                              { name: 'Professional', value: metrics.customers.professional, color: '#38A169' },
                              { name: 'Starter', value: metrics.customers.starter, color: '#D69E2E' }
                            ]}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, percentage }) => `${name}: ${percentage.toFixed(1)}%`}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                          >
                            {[
                              { name: 'Enterprise', value: metrics.customers.enterprise, color: '#805AD5' },
                              { name: 'Business', value: metrics.customers.smb, color: '#3182CE' },
                              { name: 'Professional', value: metrics.customers.professional, color: '#38A169' },
                              { name: 'Starter', value: metrics.customers.starter, color: '#D69E2E' }
                            ].map((entry, index) => (
                              <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>

                {/* Acquisition Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Monthly Budget</Text>
                        <Text fontSize="2xl" color={textColor}>{formatCurrency(metrics.acquisition.monthlyBudget)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Monthly Spend</Text>
                        <Text fontSize="2xl" color={warningColor}>{formatCurrency(metrics.acquisition.monthlySpend)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Customer Lifetime Value</Text>
                        <Text fontSize="2xl" color={successColor}>{formatCurrency(metrics.acquisition.ltv)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Return on Investment</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.acquisition.roi.toFixed(1)}x</Text>
                      </Box>
                    </Grid>
                    
                    <Box h={300}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData.timeline.map((date, i) => ({
                          date,
                          cac: chartData.cac[i],
                          ltv: chartData.ltv[i],
                          targetCAC: targets.acquisition.cacTarget
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="date" />
                          <YAxis />
                          <Tooltip />
                          <Legend />
                          <Bar dataKey="ltv" fill="#38A169" name="LTV" />
                          <Bar dataKey="cac" fill="#E53E3E" name="CAC" />
                          <Bar dataKey="targetCAC" fill="#805AD5" name="Target CAC" />
                        </BarChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>

                {/* Sales Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>New Leads (Month)</Text>
                        <Text fontSize="2xl" color={successColor}>{formatNumber(metrics.sales.newLeads)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Qualified Leads (Month)</Text>
                        <Text fontSize="2xl" color={successColor}>{formatNumber(metrics.sales.qualifiedLeads)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Average Deal Size</Text>
                        <Text fontSize="2xl" color={successColor}>{formatCurrency(metrics.sales.averageDealSize)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Win Rate</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.sales.winRate.toFixed(1)}%</Text>
                      </Box>
                    </Grid>
                    
                    <TableContainer>
                      <Table variant="simple">
                        <Thead>
                          <Tr>
                            <Th>Metric</Th>
                            <Th>Current</Th>
                            <Th>Target</Th>
                            <Th>Status</Th>
                          </Tr>
                        </Thead>
                        <Tbody>
                          <Tr>
                            <Td>Conversion Rate</Td>
                            <Td>{metrics.sales.conversionRate.toFixed(1)}%</Td>
                            <Td>{targets.sales.winRateTarget.toFixed(1)}%</Td>
                            <Td>
                              <Badge color={metrics.sales.conversionRate >= targets.sales.winRateTarget ? 'green' : 'yellow'}>
                                {metrics.sales.conversionRate >= targets.sales.winRateTarget ? 'On Track' : 'Needs Improvement'}
                              </Badge>
                            </Td>
                          </Tr>
                          <Tr>
                            <Td>Sales Cycle</Td>
                            <Td>{metrics.sales.salesCycle} days</Td>
                            <Td>{targets.sales.cycleTarget} days</Td>
                            <Td>
                              <Badge color={metrics.sales.salesCycle <= targets.sales.cycleTarget ? 'green' : 'yellow'}>
                                {metrics.sales.salesCycle <= targets.sales.cycleTarget ? 'Good' : 'Long'}
                              </Badge>
                            </Td>
                          </Tr>
                          <Tr>
                            <Td>Team Quota</Td>
                            <Td>{formatCurrency(metrics.sales.teamQuota)}</Td>
                            <Td>{formatCurrency(targets.sales.monthlyTarget)}</Td>
                            <Td>
                              <Badge color={metrics.sales.teamQuota >= targets.sales.monthlyTarget ? 'green' : 'yellow'}>
                                {metrics.sales.teamQuota >= targets.sales.monthlyTarget ? 'Achieved' : 'In Progress'}
                              </Badge>
                            </Td>
                          </Tr>
                        </Tbody>
                      </Table>
                    </TableContainer>
                  </VStack>
                </TabPanel>

                {/* Support Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Open Tickets</Text>
                        <Text fontSize="2xl" color={warningColor}>{formatNumber(metrics.support.tickets)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Response Time</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.support.responseTime} hrs</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Satisfaction Score</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.support.satisfaction}/5</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Net Promoter Score</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.support.nps}</Text>
                      </Box>
                    </Grid>
                    
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box p={4} border="1px" borderColor={borderColor} borderRadius="md">
                        <Text fontWeight="bold" color={textColor}>Churn Risk</Text>
                        <Text fontSize="xl" color={warningColor}>{metrics.support.churnRisk.toFixed(1)}%</Text>
                        <Progress value={metrics.support.churnRisk} color={warningColor} mt={2} />
                      </Box>
                      <Box p={4} border="1px" borderColor={borderColor} borderRadius="md">
                        <Text fontWeight="bold" color={textColor}>Expansion Opportunities</Text>
                        <Text fontSize="xl" color={successColor}>{formatNumber(metrics.support.expansionOpportunities)}</Text>
                        <Progress value={25} color={successColor} mt={2} />
                      </Box>
                    </Grid>
                  </VStack>
                </TabPanel>

                {/* Product Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Monthly Active Users</Text>
                        <Text fontSize="2xl" color={successColor}>{formatNumber(metrics.product.maus)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Daily Active Users</Text>
                        <Text fontSize="2xl" color={successColor}>{formatNumber(metrics.product.daus)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Engagement Rate</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.product.engagement.toFixed(1)}%</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Uptime</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.product.uptime.toFixed(1)}%</Text>
                      </Box>
                    </Grid>
                    
                    <Box h={300}>
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={Object.entries(metrics.product.featureAdoption).map(([feature, rate]) => ({
                          feature: feature.charAt(0).toUpperCase() + feature.slice(1),
                          adoption: rate
                        }))}>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="feature" />
                          <YAxis />
                          <Tooltip />
                          <Bar dataKey="adoption" fill="#3182CE" name="Adoption Rate" />
                        </BarChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>

                {/* Market Tab */}
                <TabPanel>
                  <VStack align="stretch" spacing={4}>
                    <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Market Share</Text>
                        <Text fontSize="2xl" color={warningColor}>{metrics.market.share.toFixed(1)}%</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Brand Awareness</Text>
                        <Text fontSize="2xl" color={warningColor}>{metrics.market.brandAwareness.toFixed(1)}%</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Sentiment Score</Text>
                        <Text fontSize="2xl" color={successColor}>{metrics.market.sentiment.toFixed(1)}</Text>
                      </Box>
                      <Box>
                        <Text fontWeight="bold" color={textColor}>Automation Ranking</Text>
                        <Text fontSize="2xl" color={warningColor}>#{metrics.market.ranking.automation}</Text>
                      </Box>
                    </Grid>
                    
                    <Box h={300}>
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={Object.entries(metrics.market.competition).map(([name, share]) => ({
                              name,
                              share
                            }))}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, share }) => `${name}: ${share.toFixed(1)}%`}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="share"
                          />
                          <Tooltip />
                        </PieChart>
                      </ResponsiveContainer>
                    </Box>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </CardBody>
        </Card>

        {/* Quick Actions */}
        <Card bg={bgColor} borderColor={borderColor} borderWidth={1}>
          <CardHeader>
            <Heading size="md">Quick Actions</Heading>
          </CardHeader>
          <CardBody>
            <Grid templateColumns="repeat(auto-fit, minmax(200px, 1fr))" gap={4}>
              <Button colorScheme="blue" size="sm" onClick={() => window.open('https://admin.atom-platform.com', '_blank')}>
                Admin Dashboard
              </Button>
              <Button colorScheme="green" size="sm" onClick={() => window.open('https://sales.atom-platform.com', '_blank')}>
                Sales Dashboard
              </Button>
              <Button colorScheme="purple" size="sm" onClick={() => window.open('https://acquisition.atom-platform.com', '_blank')}>
                Acquisition Dashboard
              </Button>
              <Button colorScheme="orange" size="sm" onClick={() => window.open('https://support.atom-platform.com', '_blank')}>
                Support Dashboard
              </Button>
            </Grid>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default BusinessExecutionDashboard;