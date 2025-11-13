/**
 * Enhanced WhatsApp Business Integration Component
 * Production-ready component with advanced features
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Card,
  CardHeader,
  CardBody,
  CardFooter,
  Badge,
  Input,
  Textarea,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
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
  Select,
  FormControl,
  FormLabel,
  Switch,
  Divider,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Spinner,
  useToast,
  IconButton,
  Tooltip,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatGroup,
  Stack,
  Avatar,
  Tag,
  TagLabel,
  Icon,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Checkbox,
  RadioGroup,
  Radio,
  SimpleGrid,
  Collapse,
  Flex,
  Grid,
  useBreakpointValue,
} from '@chakra-ui/react';
import {
  ChatIcon,
  PhoneIcon,
  TimeIcon,
  CheckCircleIcon,
  WarningIcon,
  InfoIcon,
  SettingsIcon,
  ExternalLinkIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ArrowForwardIcon,
  RepeatIcon,
  PlusSquareIcon,
  BarChartIcon,
  EmailIcon,
  SearchIcon,
  DownloadIcon,
  TestIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CloseIcon,
  BellIcon,
  CalendarIcon,
  LockIcon,
  UnlockIcon,
} from '@chakra-ui/icons';

// Enhanced interfaces
interface WhatsAppServiceMetrics {
  service_id: string;
  status: string;
  health_metrics: {
    last_health_check: string;
    consecutive_failures: number;
    uptime_percentage: number;
    message_success_rate: number;
  };
  analytics: any;
  configuration: {
    auto_reply_enabled: boolean;
    business_hours_enabled: boolean;
    message_retention_days: number;
  };
  performance: {
    average_response_time: number;
    peak_hours: string[];
    top_templates: string[];
    active_conversations: number;
  };
  timestamp: string;
}

interface BatchMessageRequest {
  recipients: string[];
  message: any;
  type: string;
  delay_between_messages: number;
  schedule_time?: string;
}

interface SearchFilters {
  query: string;
  status: string;
  date_from: string;
  date_to: string;
}

interface BusinessProfile {
  name: string;
  description: string;
  email: string;
  website: string;
  address?: string;
  phone?: string;
}

const EnhancedWhatsAppBusinessIntegration: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [serviceMetrics, setServiceMetrics] = useState<WhatsAppServiceMetrics | null>(null);
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [activeTab, setActiveTab] = useState(0);
  const [isConfigured, setIsConfigured] = useState(false);

  // Batch messaging state
  const [batchRecipients, setBatchRecipients] = useState('');
  const [batchMessage, setBatchMessage] = useState('');
  const [batchDelay, setBatchDelay] = useState(1);
  const [isBatchSending, setIsBatchSending] = useState(false);

  // Search state
  const [searchFilters, setSearchFilters] = useState<SearchFilters>({
    query: '',
    status: '',
    date_from: '',
    date_to: '',
  });
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);

  // Business profile state
  const [businessProfile, setBusinessProfile] = useState<BusinessProfile>({
    name: '',
    description: '',
    email: '',
    website: '',
  });

  // Advanced configuration
  const [advancedConfig, setAdvancedConfig] = useState({
    rate_limiting_enabled: true,
    message_retention_days: 30,
    auto_reply_enabled: false,
    business_hours_enabled: true,
    business_hours_start: '09:00',
    business_hours_end: '18:00',
    webhook_security_enabled: true,
    analytics_tracking_enabled: true,
  });

  const {
    isOpen: isBatchModalOpen,
    onOpen: onBatchModalOpen,
    onClose: onBatchModalClose,
  } = useDisclosure();

  const {
    isOpen: isConfigOpen,
    onOpen: onConfigOpen,
    onClose: onConfigClose,
  } = useDisclosure();

  const {
    isOpen: isProfileOpen,
    onOpen: onProfileOpen,
    onClose: onProfileClose,
  } = useDisclosure();

  const {
    isOpen: isAdvancedConfigOpen,
    onOpen: onAdvancedConfigOpen,
    onClose: onAdvancedConfigClose,
  } = useDisclosure();

  const toast = useToast();

  // Initialize service
  const initializeService = useCallback(async () => {
    try {
      const response = await fetch('/api/whatsapp/service/initialize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const result = await response.json();
      
      if (result.success) {
        setIsConfigured(true);
        toast({
          title: 'Service Initialized',
          description: 'WhatsApp Business service has been initialized successfully',
          status: 'success',
          duration: 3000,
        });
      } else {
        toast({
          title: 'Initialization Failed',
          description: result.error || 'Failed to initialize service',
          status: 'error',
          duration: 5000,
        });
      }
      
      return result.success;
    } catch (error) {
      console.error('Error initializing service:', error);
      toast({
        title: 'Error',
        description: 'Failed to initialize WhatsApp service',
        status: 'error',
        duration: 5000,
      });
      return false;
    }
  }, [toast]);

  // Fetch service metrics
  const fetchServiceMetrics = useCallback(async () => {
    try {
      const response = await fetch('/api/whatsapp/service/metrics');
      const data = await response.json();
      
      if (data.success || data.service_id) {
        setServiceMetrics(data);
        setIsConnected(data.status === 'healthy' || data.status === 'connected');
        return data;
      }
    } catch (error) {
      console.error('Error fetching metrics:', error);
    }
    return null;
  }, []);

  // Search conversations
  const searchConversations = useCallback(async () => {
    if (!searchFilters.query && !searchFilters.status && !searchFilters.date_from && !searchFilters.date_to) {
      toast({
        title: 'Search Criteria Required',
        description: 'Please provide at least one search parameter',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    setIsSearching(true);
    try {
      const params = new URLSearchParams(searchFilters as any).toString();
      const response = await fetch(`/api/whatsapp/conversations/search?${params}`);
      const data = await response.json();
      
      if (data.success) {
        setSearchResults(data.conversations);
        toast({
          title: 'Search Complete',
          description: `Found ${data.pagination.total} conversations`,
          status: 'success',
          duration: 3000,
        });
      } else {
        toast({
          title: 'Search Failed',
          description: data.error || 'Failed to search conversations',
          status: 'error',
          duration: 3000,
        });
      }
    } catch (error) {
      console.error('Error searching conversations:', error);
      toast({
        title: 'Search Error',
        description: 'An error occurred while searching',
        status: 'error',
        duration: 3000,
      });
    } finally {
      setIsSearching(false);
    }
  }, [searchFilters, toast]);

  // Send batch messages
  const sendBatchMessages = useCallback(async () => {
    if (!batchRecipients || !batchMessage) {
      toast({
        title: 'Validation Error',
        description: 'Recipients and message are required',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    const recipients = batchRecipients
      .split('\n')
      .map(r => r.trim())
      .filter(r => r);

    if (recipients.length === 0) {
      toast({
        title: 'Validation Error',
        description: 'At least one valid recipient is required',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    if (recipients.length > 100) {
      toast({
        title: 'Validation Error',
        description: 'Maximum 100 recipients allowed per batch',
        status: 'error',
        duration: 3000,
      });
      return;
    }

    setIsBatchSending(true);
    try {
      const response = await fetch('/api/whatsapp/send/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipients,
          message: { body: batchMessage },
          type: 'text',
          delay_between_messages: batchDelay,
        } as BatchMessageRequest),
      });

      const result = await response.json();
      
      if (result.success) {
        toast({
          title: 'Batch Sent Successfully',
          description: `Sent ${result.success_count}/${result.total_recipients} messages (${result.success_rate.toFixed(1)}% success rate)`,
          status: 'success',
          duration: 5000,
        });
        onBatchModalClose();
        setBatchRecipients('');
        setBatchMessage('');
      } else {
        toast({
          title: 'Batch Send Failed',
          description: result.error || 'Failed to send batch messages',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error sending batch:', error);
      toast({
        title: 'Send Error',
        description: 'An error occurred while sending batch messages',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsBatchSending(false);
    }
  }, [batchRecipients, batchMessage, batchDelay, onBatchModalClose, toast]);

  // Update business profile
  const updateBusinessProfile = useCallback(async () => {
    try {
      const response = await fetch('/api/whatsapp/configuration/business-profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          business_profile: businessProfile,
        }),
      });

      const result = await response.json();
      
      if (result.success) {
        toast({
          title: 'Profile Updated',
          description: 'Business profile has been updated successfully',
          status: 'success',
          duration: 3000,
        });
        onProfileClose();
      } else {
        toast({
          title: 'Update Failed',
          description: result.error || 'Failed to update business profile',
          status: 'error',
          duration: 3000,
        });
      }
    } catch (error) {
      console.error('Error updating profile:', error);
      toast({
        title: 'Update Error',
        description: 'An error occurred while updating profile',
        status: 'error',
        duration: 3000,
      });
    }
  }, [businessProfile, onProfileClose, toast]);

  // Export analytics
  const exportAnalytics = useCallback(async (format: string = 'json') => {
    try {
      const endDate = new Date().toISOString().split('T')[0];
      const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
      
      const response = await fetch(
        `/api/whatsapp/analytics/export?format=${format}&start_date=${startDate}&end_date=${endDate}`
      );
      
      if (format === 'csv' && response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `whatsapp_analytics_${startDate}_${endDate}.csv`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `whatsapp_analytics_${startDate}_${endDate}.json`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
      
      toast({
        title: 'Export Complete',
        description: `Analytics exported as ${format.toUpperCase()}`,
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      console.error('Error exporting analytics:', error);
      toast({
        title: 'Export Error',
        description: 'Failed to export analytics data',
        status: 'error',
        duration: 3000,
      });
    }
  }, [toast]);

  useEffect(() => {
    fetchServiceMetrics();
    
    // Set up periodic health checks
    const interval = setInterval(fetchServiceMetrics, 60000); // Every minute
    return () => clearInterval(interval);
  }, [fetchServiceMetrics]);

  // Calculate health score color
  const healthScoreColor = useMemo(() => {
    if (!serviceMetrics) return 'gray';
    const score = serviceMetrics.health_metrics.uptime_percentage;
    if (score >= 95) return 'green';
    if (score >= 90) return 'yellow';
    return 'red';
  }, [serviceMetrics]);

  const isMobile = useBreakpointValue({ base: true, md: false });

  if (isLoading) {
    return (
      <Box p={8}>
        <VStack spacing={4} align="center">
          <Spinner size="xl" />
          <Text>Loading WhatsApp Business integration...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box p={8}>
      {/* Header */}
      <HStack justify="space-between" mb={8} flexWrap="wrap" spacing={4}>
        <VStack align="start" spacing={1} minW="300px">
          <Heading size="xl">WhatsApp Business Integration</Heading>
          <Text color="gray.600">
            Production-ready customer communication platform
          </Text>
        </VStack>
        
        <HStack flexWrap="wrap" spacing={2}>
          <Badge
            colorScheme={isConnected ? 'green' : 'red'}
            px={3}
            py={1}
            borderRadius="full"
            fontSize="sm"
          >
            {isConnected ? 'Connected' : 'Disconnected'}
          </Badge>
          
          {!isConfigured && (
            <Button
              leftIcon={<SettingsIcon />}
              colorScheme="blue"
              onClick={initializeService}
              size="sm"
            >
              Initialize
            </Button>
          )}
          
          <Button
            leftIcon={<PlusSquareIcon />}
            colorScheme="green"
            onClick={onBatchModalOpen}
            disabled={!isConnected}
            size="sm"
          >
            Batch Send
          </Button>
          
          <Button
            leftIcon={<BarChartIcon />}
            variant="outline"
            onClick={() => exportAnalytics('json')}
            size="sm"
          >
            Export
          </Button>
          
          <Button
            leftIcon={<SettingsIcon />}
            variant="outline"
            onClick={onAdvancedConfigOpen}
            size="sm"
          >
            Advanced
          </Button>
        </HStack>
      </HStack>

      {/* Service Status Overview */}
      {serviceMetrics && (
        <Card mb={8}>
          <CardHeader>
            <HStack justify="space-between">
              <Heading size="md">Service Health</Heading>
              <Badge colorScheme={healthScoreColor} fontSize="sm">
                {serviceMetrics.health_metrics.uptime_percentage.toFixed(1)}% Uptime
              </Badge>
            </HStack>
          </CardHeader>
          <CardBody>
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
              <Stat>
                <StatLabel>Status</Stat>
                <StatNumber>
                  <Badge colorScheme={serviceMetrics.status === 'healthy' ? 'green' : 'red'}>
                    {serviceMetrics.status}
                  </Badge>
                </StatNumber>
              </Stat>
              
              <Stat>
                <StatLabel>Success Rate</Stat>
                <StatNumber>
                  {serviceMetrics.health_metrics.message_success_rate.toFixed(1)}%
                </StatNumber>
              </Stat>
              
              <Stat>
                <StatLabel>Active Conversations</Stat>
                <StatNumber>
                  {serviceMetrics.performance.active_conversations}
                </StatNumber>
              </Stat>
              
              <Stat>
                <StatLabel>Avg Response Time</Stat>
                <StatNumber>
                  {serviceMetrics.performance.average_response_time.toFixed(1)}m
                </StatNumber>
              </Stat>
            </SimpleGrid>
            
            <Divider my={4} />
            
            <HStack justify="space-between" align="center">
              <VStack align="start" spacing={1}>
                <Text fontSize="sm" color="gray.600">Last Health Check</Text>
                <Text fontSize="sm" fontWeight="medium">
                  {new Date(serviceMetrics.health_metrics.last_health_check).toLocaleString()}
                </Text>
              </VStack>
              
              <HStack spacing={2}>
                <Button
                  leftIcon={<RepeatIcon />}
                  variant="outline"
                  size="sm"
                  onClick={fetchServiceMetrics}
                >
                  Refresh
                </Button>
                
                <Button
                  leftIcon={<ExternalLinkIcon />}
                  variant="outline"
                  size="sm"
                  onClick={onProfileOpen}
                >
                  Business Profile
                </Button>
              </HStack>
            </HStack>
          </CardBody>
        </Card>
      )}

      {/* Main Content */}
      <Tabs variant="enclosed" onChange={setActiveTab}>
        <TabList>
          <Tab>Service Metrics</Tab>
          <Tab>Conversations</Tab>
          <Tab>Search</Tab>
          <Tab>Analytics</Tab>
        </TabList>

        <TabPanels>
          {/* Service Metrics Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              <Card>
                <CardHeader>
                  <Heading size="md">Performance Metrics</Heading>
                </CardHeader>
                <CardBody>
                  <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                    <VStack align="start">
                      <Heading size="sm" mb={2}>Message Statistics</Heading>
                      {serviceMetrics?.analytics?.message_statistics?.map((stat: any, index: number) => (
                        <HStack key={index} justify="space-between" w="full">
                          <Text fontSize="sm">{stat.direction} {stat.message_type}</Text>
                          <Text fontSize="sm" fontWeight="bold">{stat.count}</Text>
                        </HStack>
                      ))}
                    </VStack>
                    
                    <VStack align="start">
                      <Heading size="sm" mb={2}>Peak Usage Hours</Heading>
                      {serviceMetrics?.performance?.peak_hours?.map((hour: string, index: number) => (
                        <Tag key={index} colorScheme="blue" size="sm">
                          {hour}
                        </Tag>
                      ))}
                    </VStack>
                  </SimpleGrid>
                </CardBody>
              </Card>
              
              <Card>
                <CardHeader>
                  <Heading size="md">Top Templates</Heading>
                </CardHeader>
                <CardBody>
                  <VStack align="start" spacing={2}>
                    {serviceMetrics?.performance?.top_templates?.map((template: string, index: number) => (
                      <HStack key={index} justify="space-between" w="full">
                        <Text fontSize="sm">{template}</Text>
                        <Progress
                          value={(3 - index) * 33}
                          size="sm"
                          w="200px"
                          colorScheme="green"
                        />
                      </HStack>
                    ))}
                  </VStack>
                </CardBody>
              </Card>
            </VStack>
          </TabPanel>

          {/* Conversations Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              <HStack justify="space-between">
                <Heading size="md">Recent Conversations</Heading>
                <Button
                  leftIcon={<RepeatIcon />}
                  variant="outline"
                  size="sm"
                  onClick={fetchServiceMetrics}
                >
                  Refresh
                </Button>
              </HStack>
              
              {!isConnected ? (
                <Alert status="warning">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>Service Not Connected</AlertName>
                    <AlertDescription>
                      WhatsApp Business service is not connected. Please check your configuration.
                    </AlertDescription>
                  </Box>
                </Alert>
              ) : (
                <Grid templateColumns="repeat(auto-fill, minmax(400px, 1fr))" gap={4}>
                  {conversations.map((conversation: any) => (
                    <Card key={conversation.id} cursor="pointer">
                      <CardBody>
                        <HStack justify="space-between" mb={2}>
                          <HStack>
                            <Avatar size="sm" name={conversation.name} />
                            <VStack align="start" spacing={0}>
                              <Text fontWeight="medium">
                                {conversation.name || conversation.phone_number}
                              </Text>
                              <Text fontSize="sm" color="gray.600">
                                {conversation.phone_number}
                              </Text>
                            </VStack>
                          </HStack>
                          <Badge colorScheme="green">
                            {conversation.status}
                          </Badge>
                        </HStack>
                        
                        <HStack justify="space-between" mt={3}>
                          <Text fontSize="sm" color="gray.500">
                            {conversation.message_count || 0} messages
                          </Text>
                          <Text fontSize="sm" color="gray.500">
                            {new Date(conversation.last_message_at).toLocaleDateString()}
                          </Text>
                        </HStack>
                      </CardBody>
                    </Card>
                  ))}
                </Grid>
              )}
            </VStack>
          </TabPanel>

          {/* Search Tab */}
          <TabPanel>
            <Card>
              <CardHeader>
                <Heading size="md">Search Conversations</Heading>
              </CardHeader>
              <CardBody>
                <VStack spacing={4} align="stretch">
                  <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                    <FormControl>
                      <FormLabel>Search Query</FormLabel>
                      <Input
                        placeholder="Name or phone number"
                        value={searchFilters.query}
                        onChange={(e) => setSearchFilters({...searchFilters, query: e.target.value})}
                      />
                    </FormControl>
                    
                    <FormControl>
                      <FormLabel>Status</FormLabel>
                      <Select
                        value={searchFilters.status}
                        onChange={(e) => setSearchFilters({...searchFilters, status: e.target.value})}
                      >
                        <option value="">All Statuses</option>
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                        <option value="pending">Pending</option>
                      </Select>
                    </FormControl>
                    
                    <FormControl>
                      <FormLabel>From Date</FormLabel>
                      <Input
                        type="date"
                        value={searchFilters.date_from}
                        onChange={(e) => setSearchFilters({...searchFilters, date_from: e.target.value})}
                      />
                    </FormControl>
                    
                    <FormControl>
                      <FormLabel>To Date</FormLabel>
                      <Input
                        type="date"
                        value={searchFilters.date_to}
                        onChange={(e) => setSearchFilters({...searchFilters, date_to: e.target.value})}
                      />
                    </FormControl>
                  </SimpleGrid>
                  
                  <HStack justify="space-between">
                    <Button
                      leftIcon={<SearchIcon />}
                      colorScheme="blue"
                      onClick={searchConversations}
                      isLoading={isSearching}
                    >
                      Search
                    </Button>
                    
                    <Button
                      leftIcon={<RepeatIcon />}
                      variant="outline"
                      onClick={() => {
                        setSearchFilters({
                          query: '',
                          status: '',
                          date_from: '',
                          date_to: '',
                        });
                        setSearchResults([]);
                      }}
                    >
                      Clear
                    </Button>
                  </HStack>
                </VStack>
              </CardBody>
            </Card>
            
            {searchResults.length > 0 && (
              <Card mt={4}>
                <CardHeader>
                  <Heading size="md">Search Results ({searchResults.length})</Heading>
                </CardHeader>
                <CardBody>
                  <VStack spacing={2} align="stretch">
                    {searchResults.map((result: any) => (
                      <HStack
                        key={result.id}
                        p={3}
                        border="1px solid"
                        borderColor="gray.200"
                        borderRadius="md"
                        justify="space-between"
                      >
                        <VStack align="start" spacing={0}>
                          <Text fontWeight="medium">
                            {result.name || result.phone_number}
                          </Text>
                          <Text fontSize="sm" color="gray.600">
                            {result.phone_number}
                          </Text>
                        </VStack>
                        
                        <VStack align="end" spacing={0}>
                          <Badge colorScheme="green">{result.status}</Badge>
                          <Text fontSize="sm" color="gray.500">
                            {new Date(result.last_message_at).toLocaleDateString()}
                          </Text>
                        </VStack>
                      </HStack>
                    ))}
                  </VStack>
                </CardBody>
              </Card>
            )}
          </TabPanel>

          {/* Analytics Tab */}
          <TabPanel>
            <VStack spacing={6} align="stretch">
              <Card>
                <CardHeader>
                  <HStack justify="space-between">
                    <Heading size="md">Analytics Overview</Heading>
                    <HStack>
                      <Button
                        leftIcon={<DownloadIcon />}
                        variant="outline"
                        size="sm"
                        onClick={() => exportAnalytics('csv')}
                      >
                        Export CSV
                      </Button>
                      <Button
                        leftIcon={<DownloadIcon />}
                        variant="outline"
                        size="sm"
                        onClick={() => exportAnalytics('json')}
                      >
                        Export JSON
                      </Button>
                    </HStack>
                  </HStack>
                </CardHeader>
                <CardBody>
                  <StatGroup>
                    <Stat>
                      <StatLabel>Total Conversations</StatLabel>
                      <StatNumber>
                        {serviceMetrics?.analytics?.conversation_statistics?.total_conversations || 0}
                      </StatNumber>
                    </Stat>
                    <Stat>
                      <StatLabel>Active Conversations</StatLabel>
                      <StatNumber color="green.500">
                        {serviceMetrics?.analytics?.conversation_statistics?.active_conversations || 0}
                      </StatNumber>
                    </Stat>
                    <Stat>
                      <StatLabel>Messages Sent</StatLabel>
                      <StatNumber>
                        {serviceMetrics?.analytics?.message_statistics
                          ?.filter((m: any) => m.direction === 'outbound')
                          ?.reduce((sum: number, m: any) => sum + m.count, 0) || 0}
                      </StatNumber>
                    </Stat>
                    <Stat>
                      <StatLabel>Messages Received</StatLabel>
                      <StatNumber>
                        {serviceMetrics?.analytics?.message_statistics
                          ?.filter((m: any) => m.direction === 'inbound')
                          ?.reduce((sum: number, m: any) => sum + m.count, 0) || 0}
                      </StatNumber>
                    </Stat>
                  </StatGroup>
                </CardBody>
              </Card>
            </VStack>
          </TabPanel>
        </TabPanels>
      </Tabs>

      {/* Batch Send Modal */}
      <Modal isOpen={isBatchModalOpen} onClose={onBatchModalClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Send Batch Messages</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Recipients (one per line)</FormLabel>
                <Textarea
                  placeholder="+1234567890&#10;+9876543210&#10;+5555555555"
                  value={batchRecipients}
                  onChange={(e) => setBatchRecipients(e.target.value)}
                  rows={6}
                />
                <Text fontSize="sm" color="gray.600" mt={1}>
                  Maximum 100 recipients per batch
                </Text>
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>Message</FormLabel>
                <Textarea
                  placeholder="Type your message here..."
                  value={batchMessage}
                  onChange={(e) => setBatchMessage(e.target.value)}
                  rows={4}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Delay Between Messages (seconds)</FormLabel>
                <NumberInput
                  min={0}
                  max={60}
                  value={batchDelay}
                  onChange={(value) => setBatchDelay(Number(value))}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
              </FormControl>
              
              <Alert status="info">
                <AlertIcon />
                <Text fontSize="sm">
                  Messages will be sent sequentially to avoid rate limiting. 
                  Large batches may take several minutes to complete.
                </Text>
              </Alert>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onBatchModalClose}>
              Cancel
            </Button>
            <Button
              colorScheme="green"
              onClick={sendBatchMessages}
              isLoading={isBatchSending}
            >
              Send Batch
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Business Profile Modal */}
      <Modal isOpen={isProfileOpen} onClose={onProfileClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Business Profile</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Business Name</FormLabel>
                <Input
                  value={businessProfile.name}
                  onChange={(e) => setBusinessProfile({...businessProfile, name: e.target.value})}
                />
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={businessProfile.description}
                  onChange={(e) => setBusinessProfile({...businessProfile, description: e.target.value})}
                  rows={3}
                />
              </FormControl>
              
              <FormControl isRequired>
                <FormLabel>Email</FormLabel>
                <Input
                  type="email"
                  value={businessProfile.email}
                  onChange={(e) => setBusinessProfile({...businessProfile, email: e.target.value})}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Website</FormLabel>
                <Input
                  type="url"
                  value={businessProfile.website}
                  onChange={(e) => setBusinessProfile({...businessProfile, website: e.target.value})}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Address</FormLabel>
                <Input
                  value={businessProfile.address || ''}
                  onChange={(e) => setBusinessProfile({...businessProfile, address: e.target.value})}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onProfileClose}>
              Cancel
            </Button>
            <Button colorScheme="blue" onClick={updateBusinessProfile}>
              Save Profile
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Advanced Configuration Modal */}
      <Modal isOpen={isAdvancedConfigOpen} onClose={onAdvancedConfigClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Advanced Configuration</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0">Rate Limiting</FormLabel>
                <Switch
                  isChecked={advancedConfig.rate_limiting_enabled}
                  onChange={(e) => setAdvancedConfig({
                    ...advancedConfig,
                    rate_limiting_enabled: e.target.checked
                  })}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Message Retention Days</FormLabel>
                <NumberInput
                  min={1}
                  max={365}
                  value={advancedConfig.message_retention_days}
                  onChange={(value) => setAdvancedConfig({
                    ...advancedConfig,
                    message_retention_days: Number(value)
                  })}
                >
                  <NumberInputField />
                  <NumberInputStepper>
                    <NumberIncrementStepper />
                    <NumberDecrementStepper />
                  </NumberInputStepper>
                </NumberInput>
              </FormControl>
              
              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0">Auto Reply</FormLabel>
                <Switch
                  isChecked={advancedConfig.auto_reply_enabled}
                  onChange={(e) => setAdvancedConfig({
                    ...advancedConfig,
                    auto_reply_enabled: e.target.checked
                  })}
                />
              </FormControl>
              
              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0">Business Hours</FormLabel>
                <Switch
                  isChecked={advancedConfig.business_hours_enabled}
                  onChange={(e) => setAdvancedConfig({
                    ...advancedConfig,
                    business_hours_enabled: e.target.checked
                  })}
                />
              </FormControl>
              
              {advancedConfig.business_hours_enabled && (
                <SimpleGrid columns={2} spacing={4}>
                  <FormControl>
                    <FormLabel>Start Time</FormLabel>
                    <Input
                      type="time"
                      value={advancedConfig.business_hours_start}
                      onChange={(e) => setAdvancedConfig({
                        ...advancedConfig,
                        business_hours_start: e.target.value
                      })}
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>End Time</FormLabel>
                    <Input
                      type="time"
                      value={advancedConfig.business_hours_end}
                      onChange={(e) => setAdvancedConfig({
                        ...advancedConfig,
                        business_hours_end: e.target.value
                      })}
                    />
                  </FormControl>
                </SimpleGrid>
              )}
              
              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0">Webhook Security</FormLabel>
                <Switch
                  isChecked={advancedConfig.webhook_security_enabled}
                  onChange={(e) => setAdvancedConfig({
                    ...advancedConfig,
                    webhook_security_enabled: e.target.checked
                  })}
                />
              </FormControl>
              
              <FormControl display="flex" alignItems="center">
                <FormLabel mb="0">Analytics Tracking</FormLabel>
                <Switch
                  isChecked={advancedConfig.analytics_tracking_enabled}
                  onChange={(e) => setAdvancedConfig({
                    ...advancedConfig,
                    analytics_tracking_enabled: e.target.checked
                  })}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onAdvancedConfigClose}>
              Cancel
            </Button>
            <Button colorScheme="blue">
              Save Configuration
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default EnhancedWhatsAppBusinessIntegration;