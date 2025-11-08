import React from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Grid,
  GridItem,
  Card,
  CardBody,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  Progress,
  SimpleGrid,
  useColorModeValue,
  Badge,
  Icon,
  Flex,
  Divider,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
} from '@chakra-ui/react';
import { FiTrendingUp, FiUsers, FiDollarSign, FiTarget, FiMail, FiActivity } from 'react-icons/fi';

export interface HubSpotDashboardProps {
  analytics: {
    totalContacts: number;
    totalCompanies: number;
    totalDeals: number;
    totalDealValue: number;
    winRate: number;
    contactGrowth: number;
    companyGrowth: number;
    dealGrowth: number;
    campaignPerformance: number;
    leadConversionRate: number;
    emailOpenRate: number;
    emailClickRate: number;
    monthlyRevenue: number;
    quarterlyGrowth: number;
    topPerformingCampaigns?: Array<{
      name: string;
      performance: number;
      roi: number;
      budget: number;
    }>;
    recentActivities?: Array<{
      type: string;
      description: string;
      timestamp: string;
      contact: string;
    }>;
    pipelineStages?: Array<{
      stage: string;
      count: number;
      value: number;
      probability: number;
    }>;
  };
  loading?: boolean;
}

const HubSpotDashboard: React.FC<HubSpotDashboardProps> = ({ analytics, loading = false }) => {
  const bgColor = useColorModeValue('white', 'gray.800');
  const cardBg = useColorModeValue('gray.50', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  const getGrowthColor = (value: number) => {
    if (value > 0) return 'green.500';
    if (value < 0) return 'red.500';
    return 'gray.500';
  };

  const getPerformanceColor = (value: number) => {
    if (value >= 80) return 'green';
    if (value >= 60) return 'yellow';
    if (value >= 40) return 'orange';
    return 'red';
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
    }).format(value);
  };

  if (loading) {
    return (
      <Box p={6} bg={bgColor} borderRadius="lg">
        <VStack spacing={4}>
          <Text>Loading dashboard data...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box p={6} bg={bgColor} borderRadius="lg">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <VStack align="start" spacing={2}>
          <Heading size="lg">HubSpot Analytics Dashboard</Heading>
          <Text color="gray.600">
            Comprehensive overview of your CRM performance and marketing analytics
          </Text>
        </VStack>

        {/* Key Metrics */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
          {/* Contacts Metric */}
          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <HStack justify="space-between" align="start">
                  <Box>
                    <StatLabel>Total Contacts</StatLabel>
                    <StatNumber>{analytics.totalContacts.toLocaleString()}</StatNumber>
                    <StatHelpText>
                      <StatArrow
                        type={analytics.contactGrowth > 0 ? 'increase' : 'decrease'}
                        color={getGrowthColor(analytics.contactGrowth)}
                      />
                      {Math.abs(analytics.contactGrowth)}% from last month
                    </StatHelpText>
                  </Box>
                  <Icon as={FiUsers} boxSize={6} color="blue.500" />
                </HStack>
              </Stat>
            </CardBody>
          </Card>

          {/* Companies Metric */}
          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <HStack justify="space-between" align="start">
                  <Box>
                    <StatLabel>Total Companies</StatLabel>
                    <StatNumber>{analytics.totalCompanies.toLocaleString()}</StatNumber>
                    <StatHelpText>
                      <StatArrow
                        type={analytics.companyGrowth > 0 ? 'increase' : 'decrease'}
                        color={getGrowthColor(analytics.companyGrowth)}
                      />
                      {Math.abs(analytics.companyGrowth)}% from last month
                    </StatHelpText>
                  </Box>
                  <Icon as={FiTarget} boxSize={6} color="purple.500" />
                </HStack>
              </Stat>
            </CardBody>
          </Card>

          {/* Deals Metric */}
          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <HStack justify="space-between" align="start">
                  <Box>
                    <StatLabel>Active Deals</StatLabel>
                    <StatNumber>{analytics.totalDeals.toLocaleString()}</StatNumber>
                    <StatHelpText>
                      <StatArrow
                        type={analytics.dealGrowth > 0 ? 'increase' : 'decrease'}
                        color={getGrowthColor(analytics.dealGrowth)}
                      />
                      {Math.abs(analytics.dealGrowth)}% from last month
                    </StatHelpText>
                  </Box>
                  <Icon as={FiDollarSign} boxSize={6} color="green.500" />
                </HStack>
              </Stat>
            </CardBody>
          </Card>

          {/* Revenue Metric */}
          <Card bg={cardBg}>
            <CardBody>
              <Stat>
                <HStack justify="space-between" align="start">
                  <Box>
                    <StatLabel>Monthly Revenue</StatLabel>
                    <StatNumber>{formatCurrency(analytics.monthlyRevenue)}</StatNumber>
                    <StatHelpText>
                      <StatArrow
                        type={analytics.quarterlyGrowth > 0 ? 'increase' : 'decrease'}
                        color={getGrowthColor(analytics.quarterlyGrowth)}
                      />
                      {Math.abs(analytics.quarterlyGrowth)}% this quarter
                    </StatHelpText>
                  </Box>
                  <Icon as={FiTrendingUp} boxSize={6} color="orange.500" />
                </HStack>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Performance Metrics */}
        <Grid templateColumns={{ base: '1fr', lg: '2fr 1fr' }} gap={6}>
          {/* Left Column - Main Performance */}
          <VStack spacing={6} align="stretch">
            {/* Win Rate & Conversion */}
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
              <Card bg={cardBg}>
                <CardBody>
                  <VStack align="start" spacing={3}>
                    <HStack>
                      <Icon as={FiTarget} color="green.500" />
                      <Text fontWeight="semibold">Win Rate</Text>
                    </HStack>
                    <Progress
                      value={analytics.winRate}
                      size="lg"
                      colorScheme="green"
                      borderRadius="full"
                    />
                    <Text fontSize="2xl" fontWeight="bold">
                      {analytics.winRate.toFixed(1)}%
                    </Text>
                    <Text fontSize="sm" color="gray.600">
                      Deal conversion success rate
                    </Text>
                  </VStack>
                </CardBody>
              </Card>

              <Card bg={cardBg}>
                <CardBody>
                  <VStack align="start" spacing={3}>
                    <HStack>
                      <Icon as={FiUsers} color="blue.500" />
                      <Text fontWeight="semibold">Lead Conversion</Text>
                    </HStack>
                    <Progress
                      value={analytics.leadConversionRate}
                      size="lg"
                      colorScheme="blue"
                      borderRadius="full"
                    />
                    <Text fontSize="2xl" fontWeight="bold">
                      {analytics.leadConversionRate.toFixed(1)}%
                    </Text>
                    <Text fontSize="sm" color="gray.600">
                      Lead to customer conversion
                    </Text>
                  </VStack>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Email Performance */}
            <Card bg={cardBg}>
              <CardBody>
                <VStack align="start" spacing={4}>
                  <HStack>
                    <Icon as={FiMail} color="purple.500" />
                    <Text fontWeight="semibold">Email Performance</Text>
                  </HStack>
                  <SimpleGrid columns={2} spacing={4} width="full">
                    <VStack align="start" spacing={1}>
                      <Text fontSize="sm" color="gray.600">
                        Open Rate
                      </Text>
                      <Progress
                        value={analytics.emailOpenRate}
                        size="sm"
                        colorScheme="purple"
                        width="full"
                      />
                      <Text fontSize="lg" fontWeight="semibold">
                        {analytics.emailOpenRate.toFixed(1)}%
                      </Text>
                    </VStack>
                    <VStack align="start" spacing={1}>
                      <Text fontSize="sm" color="gray.600">
                        Click Rate
                      </Text>
                      <Progress
                        value={analytics.emailClickRate}
                        size="sm"
                        colorScheme="teal"
                        width="full"
                      />
                      <Text fontSize="lg" fontWeight="semibold">
                        {analytics.emailClickRate.toFixed(1)}%
                      </Text>
                    </VStack>
                  </SimpleGrid>
                </VStack>
              </CardBody>
            </Card>

            {/* Pipeline Stages */}
            {analytics.pipelineStages && analytics.pipelineStages.length > 0 && (
              <Card bg={cardBg}>
                <CardBody>
                  <VStack align="start" spacing={4}>
                    <HStack>
                      <Icon as={FiActivity} color="orange.500" />
                      <Text fontWeight="semibold">Pipeline Stages</Text>
                    </HStack>
                    <VStack align="stretch" spacing={3} width="full">
                      {analytics.pipelineStages.map((stage, index) => (
                        <Box key={index}>
                          <HStack justify="space-between" mb={1}>
                            <Text fontSize="sm" fontWeight="medium">
                              {stage.stage}
                            </Text>
                            <Badge colorScheme="blue">
                              {stage.count} deals
                            </Badge>
                          </HStack>
                          <Progress
                            value={stage.probability}
                            size="sm"
                            colorScheme="orange"
                            borderRadius="full"
                          />
                          <HStack justify="space-between" mt={1}>
                            <Text fontSize="xs" color="gray.600">
                              {stage.probability}% probability
                            </Text>
                            <Text fontSize="xs" color="gray.600">
                              {formatCurrency(stage.value)}
                            </Text>
                          </HStack>
                        </Box>
                      ))}
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            )}
          </VStack>

          {/* Right Column - Campaigns & Activities */}
          <VStack spacing={6} align="stretch">
            {/* Top Performing Campaigns */}
            {analytics.topPerformingCampaigns && analytics.topPerformingCampaigns.length > 0 && (
              <Card bg={cardBg}>
                <CardBody>
                  <VStack align="start" spacing={4}>
                    <Text fontWeight="semibold">Top Performing Campaigns</Text>
                    <VStack align="stretch" spacing={3} width="full">
                      {analytics.topPerformingCampaigns.map((campaign, index) => (
                        <Box
                          key={index}
                          p={3}
                          border="1px"
                          borderColor={borderColor}
                          borderRadius="md"
                        >
                          <VStack align="start" spacing={1}>
                            <Text fontSize="sm" fontWeight="medium">
                              {campaign.name}
                            </Text>
                            <HStack justify="space-between" width="full">
                              <Badge
                                colorScheme={getPerformanceColor(campaign.performance)}
                              >
                                {campaign.performance}%
                              </Badge>
                              <Text fontSize="sm" color="gray.600">
                                ROI: {campaign.roi}%
                              </Text>
                            </HStack>
                            <Progress
                              value={campaign.performance}
                              size="xs"
                              colorScheme={getPerformanceColor(campaign.performance)}
                              width="full"
                            />
                          </VStack>
                        </Box>
                      ))}
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            )}

            {/* Recent Activities */}
            {analytics.recentActivities && analytics.recentActivities.length > 0 && (
              <Card bg={cardBg}>
                <CardBody>
                  <VStack align="start" spacing={4}>
                    <Text fontWeight="semibold">Recent Activities</Text>
                    <VStack align="stretch" spacing={2} width="full">
                      {analytics.recentActivities.slice(0, 5).map((activity, index) => (
                        <HStack
                          key={index}
                          p={2}
                          border="1px"
                          borderColor={borderColor}
                          borderRadius="md"
                          justify="space-between"
                        >
                          <VStack align="start" spacing={0}>
                            <Text fontSize="sm" fontWeight="medium">
                              {activity.type}
                            </Text>
                            <Text fontSize="xs" color="gray.600">
                              {activity.description}
                            </Text>
                            <Text fontSize="xs" color="gray.500">
                              {activity.contact}
                            </Text>
                          </VStack>
                          <Text fontSize="xs" color="gray.500">
                            {new Date(activity.timestamp).toLocaleDateString()}
                          </Text>
                        </HStack>
                      ))}
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            )}
          </VStack>
        </Grid>

        {/* Summary Stats */}
        <Card bg={cardBg}>
          <CardBody>
            <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
              <VStack align="center" spacing={1}>
                <Text fontSize="2xl" fontWeight="bold" color="green.500">
                  {formatCurrency(analytics.totalDealValue)}
                </Text>
                <Text fontSize="sm" color="gray.600" textAlign="center">
                  Total Deal Value
                </Text>
              </VStack>
              <VStack align="center" spacing={1}>
                <Text fontSize="2xl" fontWeight="bold" color="blue.500">
                  {analytics.campaignPerformance.toFixed(1)}%
                </Text>
                <Text fontSize="sm" color="gray.600" textAlign="center">
                  Campaign Performance
                </Text>
              </VStack>
              <VStack align="center" spacing={1}>
                <Text fontSize="2xl" fontWeight="bold" color="purple.500">
                  {(analytics.totalContacts + analytics.totalCompanies).toLocaleString()}
                </Text>
                <Text fontSize="sm" color="gray.600" textAlign="center">
                  Total Records
                </Text>
              </VStack>
              <VStack align="center" spacing={1}>
                <Text fontSize="2xl" fontWeight="bold" color="orange.500">
                  {analytics.winRate > 0 ? '↑' : '↓'}
                </Text>
                <Text fontSize="sm" color="gray.600" textAlign="center">
                  Performance Trend
                </Text>
              </VStack>
            </SimpleGrid>
          </CardBody>
        </Card>
      </VStack>
    </Box>
  );
};

export default HubSpotDashboard;
