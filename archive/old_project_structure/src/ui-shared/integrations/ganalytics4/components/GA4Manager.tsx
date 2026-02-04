/**
 * ATOM Google Analytics 4 Manager Component
 * Complete web analytics and marketing measurement interface
 * Enterprise-grade digital analytics with comprehensive reporting
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box, VStack, HStack, Heading, Text, Button, Card, CardBody, CardHeader,
  Tabs, TabList, TabPanels, Tab, TabPanel, Alert, AlertIcon, Badge,
  Progress, Stat, StatLabel, StatNumber, StatHelpText, Divider, FormControl,
  FormLabel, Switch, NumberInput, NumberInputField, NumberInputStepper,
  NumberIncrementStepper, NumberDecrementStepper, Input, Select, Checkbox,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalFooter, ModalBody,
  ModalCloseButton, useDisclosure, useToast, SimpleGrid, Table,
  Thead, Tbody, Tr, Th, Td, TableContainer, Icon, Spinner,
  Center, Flex, Spacer, useColorModeValue, Tooltip, IconButton,
  Menu, MenuButton, MenuList, MenuItem, Tag, TagLabel, TagCloseButton,
  List, ListItem, ListIcon, Stack, AlertTitle, AlertDescription,
  Accordion, AccordionItem, AccordionButton, AccordionPanel, AccordionIcon,
  Textarea, RadioGroup, Radio, Link, Textarea as ChakraTextarea,
  Chart, LineChart, BarChart, PieChart, AreaChart, XAxis, YAxis,
  CartesianGrid, Tooltip as ChartTooltip, Legend, ResponsiveContainer,
  Cell
} from '@chakra-ui/react';
import {
  FiBarChart, FiTrendingUp, FiUsers, FiEye,
  FiSettings, FiRefreshCw, FiDatabase, FiZap, FiClock,
  FiActivity, FiShield, FiCheck, FiX, FiAlertTriangle,
  FiPlus, FiEdit, FiTrash2, FiSearch, FiFilter,
  FiGrid, FiList, FiPlay, FiPause, FiStop, FiMonitor, FiPieChart,
  FiMail, FiMessageSquare, FiUser, FiAward,
  FiTarget, FiGlobe, FiMapPin, FiPhone, FiStar,
  FiDownload, FiUpload, FiExternalLink, FiCopy,
  FiFile, FiCalendar, FiDollarSign, FiShoppingCart,
  FiLink, FiWifi, FiCpu, FiHardDrive,
  FiFlag, FiBell, FiLock, FiUnlock,
  FiChevronDown, FiChevronRight, FiMoreVertical,
  FiCrosshair, FiNavigation, FiCompass,
  FiLayers, FiPackage, FiTag, FiBookmark
} from 'react-icons/fi';

// GA4 Types
import {
  GA4Property,
  GA4DataStream,
  GA4Report,
  GA4Audience,
  GA4ConversionEvent,
  GA4UserEvent,
  GA4AudienceInsight,
  GA4RealtimeReport,
  GA4EcommerceEvent,
  GA4Config,
  GA4SyncSession,
  GA4ComplianceReport,
  GA4SearchQuery,
  GA4SearchResults
} from '../types';

interface GA4ManagerProps {
  // Authentication
  projectId: string;
  credentialType: 'service_account' | 'oauth2' | 'api_key';
  credentials: string;
  environment?: 'production' | 'sandbox';
  
  // ATOM Integration
  atomIngestionPipeline?: any;
  atomSkillRegistry?: any;
  atomMemoryStore?: any;
  
  // Configuration
  initialConfig?: Partial<GA4Config>;
  platform?: 'auto' | 'web' | 'desktop';
  theme?: 'auto' | 'light' | 'dark';
  
  // Events
  onReady?: (manager: any) => void;
  onError?: (error: any) => void;
  onPropertyCreated?: (property: GA4Property) => void;
  onReportGenerated?: (report: GA4Report) => void;
  onAudienceCreated?: (audience: GA4Audience) => void;
  onSyncStart?: (config: any) => void;
  onSyncComplete?: (results: any) => void;
}

const GA4_DEFAULT_CONFIG: GA4Config = {
  // API Configuration
  baseUrl: 'https://analyticsdata.googleapis.com',
  version: 'v1beta',
  credentialType: 'service_account',
  projectId: '',
  propertyId: '',
  environment: 'production',
  
  // Data Stream Configuration
  enableEnhancedMeasurement: true,
  dataRetentionDays: 50,
  
  // Sync Configuration
  enableRealTimeSync: true,
  syncInterval: 5 * 60 * 1000, // 5 minutes
  batchSize: 100,
  maxRetries: 3,
  enableDeltaSync: true,
  
  // Data Configuration
  enableUserIPAnonymization: true,
  enableDataRetention: true,
  enableServerSideTagging: false,
  includeUnsampledReports: true,
  includeAdPersonalization: false,
  
  // Analytics Configuration
  enableAudienceInsights: true,
  enableFunnelAnalysis: true,
  enableEcommerceTracking: true,
  enableConversionTracking: true,
  enableRevenueTracking: true,
  
  // Notification Configuration
  enableNotifications: true,
  notificationChannels: ['email'],
  emailNotifications: true,
  slackNotifications: false,
  
  // Security Configuration
  enableDataValidation: true,
  enableAccessControl: true,
  requireApproversForActions: false,
  enableAuditLogging: true,
  
  // Performance Configuration
  enableCaching: true,
  cacheSize: 100 * 1024 * 1024, // 100MB
  enableCompression: true,
  enableParallelProcessing: true,
  maxConcurrency: 5,
};

export const GA4Manager: React.FC<GA4ManagerProps> = ({
  projectId,
  credentialType,
  credentials,
  environment = 'production',
  atomIngestionPipeline,
  atomSkillRegistry,
  atomMemoryStore,
  initialConfig,
  platform = 'auto',
  theme = 'auto',
  onReady,
  onError,
  onPropertyCreated,
  onReportGenerated,
  onAudienceCreated,
  onSyncStart,
  onSyncComplete,
}) => {
  // State Management
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  
  // Data State
  const [properties, setProperties] = useState<GA4Property[]>([]);
  const [dataStreams, setDataStreams] = useState<GA4DataStream[]>([]);
  const [reports, setReports] = useState<GA4Report[]>([]);
  const [audiences, setAudiences] = useState<GA4Audience[]>([]);
  const [conversionEvents, setConversionEvents] = useState<GA4ConversionEvent[]>([]);
  const [userEvents, setUserEvents] = useState<GA4UserEvent[]>([]);
  const [audienceInsights, setAudienceInsights] = useState<GA4AudienceInsight[]>([]);
  const [realtimeReport, setRealtimeReport] = useState<GA4RealtimeReport | null>(null);
  const [ecommerceEvents, setEcommerceEvents] = useState<GA4EcommerceEvent[]>([]);
  
  // Selected Items
  const [selectedProperty, setSelectedProperty] = useState<GA4Property | null>(null);
  const [selectedDataStream, setSelectedDataStream] = useState<GA4DataStream | null>(null);
  const [selectedReport, setSelectedReport] = useState<GA4Report | null>(null);
  const [selectedAudience, setSelectedAudience] = useState<GA4Audience | null>(null);
  
  // Configuration
  const [config, setConfig] = useState<GA4Config>(
    () => ({ ...GA4_DEFAULT_CONFIG, ...initialConfig })
  );
  const [configModalOpen, setConfigModalOpen] = useState(false);
  
  // Sync Progress
  const [currentSyncSession, setCurrentSyncSession] = useState<GA4SyncSession | null>(null);
  const [syncProgress, setSyncProgress] = useState({
    total: 0,
    processed: 0,
    percentage: 0,
    currentItem: '',
    errors: 0,
    warnings: 0,
  });
  
  // UI State
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [filterStatus, setFilterStatus] = useState('all');
  
  // Modal State
  const [propertyModalOpen, setPropertyModalOpen] = useState(false);
  const [reportModalOpen, setReportModalOpen] = useState(false);
  const [audienceModalOpen, setAudienceModalOpen] = useState(false);
  const [complianceModalOpen, setComplianceModalOpen] = useState(false);
  
  // Form Data
  const [formData, setFormData] = useState<Record<string, any>>({});
  
  // Analytics State
  const [analyticsData, setAnalyticsData] = useState({
    totalUsers: 0,
    activeUsers: 0,
    sessions: 0,
    pageViews: 0,
    conversions: 0,
    revenue: 0,
    bounceRate: 0,
    avgSessionDuration: 0
  });

  const toast = useToast();

  // Theme colors
  const bgColor = useColorModeValue('white', 'gray.800');
  const cardBg = useColorModeValue('white', 'gray.700');

  // Initialize GA4
  useEffect(() => {
    initializeGA4();
  }, [projectId, credentialType, credentials]);

  const initializeGA4 = useCallback(async () => {
    if (!projectId || !credentials) {
      setIsConnected(false);
      toast({
        title: 'Authentication Required',
        description: 'Google Analytics 4 credentials are required',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsConnecting(true);
    try {
      // Simulate connection and initial data loading
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const [propertiesData, dataStreamsData, reportsData, audiencesData, realTimeData] = await Promise.all([
        simulateProperties(),
        simulateDataStreams(),
        simulateReports(),
        simulateAudiences(),
        simulateRealtimeReport(),
      ]);

      setProperties(propertiesData);
      setDataStreams(dataStreamsData);
      setReports(reportsData);
      setAudiences(audiencesData);
      setRealtimeReport(realTimeData);
      setIsConnected(true);
      
      // Initialize ATOM integration
      if (atomSkillRegistry) {
        await initializeAtomSkills();
      }
      
      if (atomIngestionPipeline) {
        await initializeAtomPipeline();
      }
      
      onReady?.({ 
        isConnected: true, 
        hasProperties: propertiesData.length > 0,
        hasReports: reportsData.length > 0,
        totalProperties: propertiesData.length,
        totalReports: reportsData.length,
      });
      
      toast({
        title: 'Google Analytics 4 Connected',
        description: 'Analytics management system is ready',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      
    } catch (error) {
      setIsConnected(false);
      onError?.(error);
      toast({
        title: 'Connection Failed',
        description: 'Failed to connect to Google Analytics 4 services',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsConnecting(false);
    }
  }, [projectId, credentialType, credentials, atomSkillRegistry, atomIngestionPipeline, onError, onReady]);

  const initializeAtomSkills = useCallback(async () => {
    // This would register the actual skills with ATOM
    const { GA4SkillsBundle } = await import('../skills/ganalytics4Skills');
    
    // Register skills with ATOM skill registry
    for (const skill of GA4SkillsBundle.skills) {
      // atomSkillRegistry.registerSkill(skill);
      console.log(`Registering skill: ${skill.id}`);
    }
    
    toast({
      title: 'Skills Registered',
      description: `${GA4SkillsBundle.skills.length} GA4 skills registered with ATOM`,
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  }, [atomSkillRegistry]);

  const initializeAtomPipeline = useCallback(() => {
    // Setup ATOM pipeline for GA4 data
    atomIngestionPipeline?.on('document-processed', (event: any) => {
      if (event.source === 'google_analytics_4') {
        console.log('GA4 document processed:', event);
      }
    });
    
    toast({
      title: 'Pipeline Initialized',
      description: 'Google Analytics 4 ingestion pipeline is ready',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  }, [atomIngestionPipeline]);

  // Simulate functions (replace with actual GA4 API calls)
  const simulateProperties = async (): Promise<GA4Property[]> => {
    return [
      {
        name: `properties/${projectId}`,
        parent: 'accounts/123456',
        displayName: 'Main Website',
        propertyType: 'PROPERTY_TYPE_WEB',
        industryCategory: 'Retail',
        time_zone: 'America/New_York',
        currencyCode: 'USD',
        create_time: '2024-01-15T10:00:00Z',
        account_id: '123456',
        property_id: projectId,
        dataStreams: []
      },
      {
        name: `properties/${projectId}-2`,
        parent: 'accounts/123456',
        displayName: 'Mobile App',
        propertyType: 'PROPERTY_TYPE_ANDROID',
        industryCategory: 'Technology',
        time_zone: 'America/New_York',
        currencyCode: 'USD',
        create_time: '2024-01-20T10:00:00Z',
        account_id: '123456',
        property_id: `${projectId}-2`,
        dataStreams: []
      },
    ];
  };

  const simulateDataStreams = async (): Promise<GA4DataStream[]> => {
    return [
      {
        name: `properties/${projectId}/dataStreams/123456789`,
        streamId: '123456789',
        displayName: 'Web Stream',
        type: 'DATA_STREAM_TYPE_WEB',
        webStreamData: {
          measurementId: 'G-XXXXXXXXXX',
          defaultUri: 'https://example.com',
          enhancedMeasurementSettings: {
            stream_enabled: true,
            page_views_enabled: true,
            scrolls_enabled: true,
            outbound_clicks_enabled: true,
            site_search_enabled: false,
            video_engagement_enabled: true,
            file_downloads_enabled: true,
            form_interactions_enabled: true,
            page_loads_enabled: true,
            page_changes_enabled: true,
            js_errors_enabled: true
          }
        },
        create_time: '2024-01-15T10:00:00Z'
      }
    ];
  };

  const simulateReports = async (): Promise<GA4Report[]> => {
    return [
      {
        name: 'sample-report',
        dimensions: [],
        metrics: [],
        dateRanges: [],
        property: `properties/${projectId}`,
        kind: 'analyticsData#runReport',
        rowCount: 1000,
        rows: []
      }
    ];
  };

  const simulateAudiences = async (): Promise<GA4Audience[]> => {
    return [
      {
        name: `properties/${projectId}/audiences/123456789`,
        displayName: 'All Users',
        description: 'All users who have visited the site',
        membershipDurationDays: 30,
        adsPersonalizationEnabled: true,
        create_time: '2024-01-15T10:00:00Z',
        membersCount: '100000',
        eligibleForSearch: true
      }
    ];
  };

  const simulateRealtimeReport = async (): Promise<GA4RealtimeReport> => {
    return {
      name: 'realtime-report',
      dimensions: [],
      metrics: [],
      property: `properties/${projectId}`,
      kind: 'analyticsData#runRealtimeReport',
      rowCount: 500,
      rows: []
    };
  };

  // Execute Skill
  const handleExecuteSkill = useCallback(async (skillId: string, input: any) => {
    if (!atomSkillRegistry) {
      toast({
        title: 'Skill Registry Not Available',
        description: 'ATOM skill registry is not configured',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    try {
      // This would execute the actual skill
      // const result = await atomSkillRegistry.executeSkill(skillId, input, {
      //   ga4Client: createGA4Client(),
      //   atomIngestionPipeline,
      //   atomMemoryStore,
      //   ga4Config: config,
      // });

      // Mock execution
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      toast({
        title: 'Skill Executed',
        description: `${skillId} completed successfully`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      
      // Refresh data based on skill type
      if (skillId.includes('property')) {
        const newProperties = await simulateProperties();
        setProperties(newProperties);
      } else if (skillId.includes('report')) {
        const newReports = await simulateReports();
        setReports(newReports);
      }
      
    } catch (error) {
      onError?.(error);
      toast({
        title: 'Skill Execution Failed',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [atomSkillRegistry, atomIngestionPipeline, atomMemoryStore, config, onError]);

  // Start Sync
  const handleStartSync = useCallback(async () => {
    if (!isConnected) {
      toast({
        title: 'Not Connected',
        description: 'Please connect to Google Analytics 4 first',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSyncing(true);
    const sessionId = `ga4_sync_${Date.now()}`;
    
    const session: GA4SyncSession = {
      id: sessionId,
      startTime: new Date().toISOString(),
      status: 'running',
      type: 'full',
      config: config,
      progress: {
        total: properties.length + dataStreams.length + reports.length,
        processed: 0,
        percentage: 0,
        currentItem: '',
        errors: 0,
        warnings: 0,
        bytesProcessed: 0,
      },
    };

    setCurrentSyncSession(session);
    onSyncStart?.(config);

    try {
      // Simulate sync process
      const allItems = [...properties, ...dataStreams, ...reports];
      for (let i = 0; i < allItems.length; i++) {
        const item = allItems[i];
        session.progress.processed = i + 1;
        session.progress.percentage = ((i + 1) / allItems.length) * 100;
        session.progress.currentItem = item instanceof GA4Property ? item.displayName : 
                                      item instanceof GA4DataStream ? item.displayName : 
                                      item instanceof GA4Report ? item.name : 
                                      'Data Item';
        
        setCurrentSyncSession({ ...session });
        
        // Simulate processing time
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      session.status = 'completed';
      setCurrentSyncSession(null);
      onSyncComplete?.(session);
      
      toast({
        title: 'Sync Completed',
        description: `Successfully synced ${allItems.length} items`,
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      
    } catch (error) {
      session.status = 'failed';
      session.error = error instanceof Error ? error.message : 'Sync failed';
      setCurrentSyncSession(null);
      onError?.(error);
      
      toast({
        title: 'Sync Failed',
        description: session.error,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSyncing(false);
    }
  }, [isConnected, properties, dataStreams, reports, config, onSyncStart, onSyncComplete, onError]);

  // Format utilities
  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  // Render Loading State
  if (isConnecting) {
    return (
      <Center minH="400px">
        <VStack spacing={4}>
          <Spinner size="xl" />
          <Text>Connecting to Google Analytics 4...</Text>
        </VStack>
      </Center>
    );
  }

  // Render Connection Status
  const renderConnectionStatus = () => (
    <Alert status={isConnected ? 'success' : 'warning'}>
      <AlertIcon />
      <Box flex="1">
        <AlertTitle>{isConnected ? 'Connected' : 'Not Connected'}</AlertTitle>
        <AlertDescription>
          {isConnected 
            ? 'Google Analytics 4 is connected and ready'
            : 'Configure GA4 credentials to access analytics services'
          }
        </AlertDescription>
      </Box>
      {!isConnected && (
        <Button colorScheme="blue" size="sm" onClick={initializeGA4}>
          Connect
        </Button>
      )}
    </Alert>
  );

  // Render Analytics Dashboard
  const renderAnalyticsDashboard = () => {
    const data = [
      { name: 'Mon', users: 4000, sessions: 2400, pageViews: 2400 },
      { name: 'Tue', users: 3000, sessions: 1398, pageViews: 2210 },
      { name: 'Wed', users: 2000, sessions: 9800, pageViews: 2290 },
      { name: 'Thu', users: 2780, sessions: 3908, pageViews: 2000 },
      { name: 'Fri', users: 1890, sessions: 4800, pageViews: 2181 },
      { name: 'Sat', users: 2390, sessions: 3800, pageViews: 2500 },
      { name: 'Sun', users: 3490, sessions: 4300, pageViews: 2100 }
    ];

    return (
      <VStack spacing={6} align="stretch">
        {/* Key Metrics */}
        <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
          <Card>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.500">Total Users</StatLabel>
                <StatNumber fontSize="2xl">245,678</StatNumber>
                <StatHelpText>
                  <Icon as={FiTrendingUp} mr={1} color="green.500" />
                  +12.5% from last month
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.500">Sessions</StatNumber>
                <StatNumber fontSize="2xl">1,845,234</StatNumber>
                <StatHelpText>
                  <Icon as={FiActivity} mr={1} color="blue.500" />
                  Avg: 3.2 per user
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.500">Page Views</StatNumber>
                <StatNumber fontSize="2xl">8,234,567</StatNumber>
                <StatHelpText>
                  <Icon as={FiEye} mr={1} color="purple.500" />
                  Avg: 4.6 per session
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody>
              <Stat>
                <StatLabel fontSize="sm" color="gray.500">Conversions</StatNumber>
                <StatNumber fontSize="2xl">45,678</StatNumber>
                <StatHelpText>
                  <Icon as={FiTarget} mr={1} color="orange.500" />
                  2.47% conversion rate
                </StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Charts */}
        <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
          <Card>
            <CardHeader>
              <Heading size="md">User Activity Trend</Heading>
            </CardHeader>
            <CardBody>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis />
                  <ChartTooltip />
                  <Legend />
                  <Line type="monotone" dataKey="users" stroke="#3182CE" strokeWidth={2} />
                  <Line type="monotone" dataKey="sessions" stroke="#805AD5" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <Heading size="md">Traffic Sources</Heading>
            </CardHeader>
            <CardBody>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={[
                      { name: 'Organic Search', value: 45, color: '#3182CE' },
                      { name: 'Direct', value: 25, color: '#805AD5' },
                      { name: 'Referral', value: 15, color: '#DD6B20' },
                      { name: 'Social', value: 10, color: '#38A169' },
                      { name: 'Email', value: 5, color: '#E53E3E' }
                    ]}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    dataKey="value"
                  >
                    {[
                      { name: 'Organic Search', value: 45, color: '#3182CE' },
                      { name: 'Direct', value: 25, color: '#805AD5' },
                      { name: 'Referral', value: 15, color: '#DD6B20' },
                      { name: 'Social', value: 10, color: '#38A169' },
                      { name: 'Email', value: 5, color: '#E53E3E' }
                    ].map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <ChartTooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </CardBody>
          </Card>
        </SimpleGrid>
      </VStack>
    );
  };

  // Render Properties
  const renderProperties = () => (
    <VStack spacing={4} align="stretch">
      <HStack justify="space-between">
        <Heading size="md">Properties</Heading>
        <HStack spacing={2}>
          <Button leftIcon={<FiPlus />} colorScheme="blue" size="sm">
            Create Property
          </Button>
        </HStack>
      </HStack>
      
      {properties.length > 0 ? (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {properties.map((property) => (
            <Card 
              key={property.name}
              _hover={{ bg: 'gray.50', cursor: 'pointer' }}
              onClick={() => setSelectedProperty(property)}
              border={selectedProperty?.name === property.name ? '2px solid blue.500' : '1px solid gray.200'}
            >
              <CardBody>
                <VStack spacing={3} align="start">
                  <HStack justify="space-between" width="100%">
                    <Text fontWeight="bold">{property.displayName}</Text>
                    <Badge colorScheme="green">
                      {property.propertyType.replace('PROPERTY_TYPE_', '')}
                    </Badge>
                  </HStack>
                  
                  <VStack align="start" spacing={1}>
                    <HStack>
                      <Icon as={FiGlobe} boxSize={4} />
                      <Text fontSize="sm">{property.industryCategory}</Text>
                    </HStack>
                    
                    <Text fontSize="sm" color="gray.500">
                      {property.currencyCode} • {property.time_zone}
                    </Text>
                    
                    <Text fontSize="xs" color="gray.500">
                      Created: {formatDate(property.create_time)}
                    </Text>
                  </VStack>
                  
                  <HStack justify="space-between" width="100%">
                    <Text fontSize="xs" color="gray.500">
                      {property.dataStreams?.length || 0} data streams
                    </Text>
                    <HStack spacing={1}>
                      <IconButton
                        icon={<FiEye />}
                        variant="ghost"
                        size="xs"
                        aria-label="View property"
                      />
                      <IconButton
                        icon={<FiEdit />}
                        variant="ghost"
                        size="xs"
                        aria-label="Edit property"
                      />
                    </HStack>
                  </HStack>
                </VStack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>
      ) : (
        <Box textAlign="center" py={10}>
          <Icon as={FiBarChart} boxSize={12} color="gray.400" />
          <Text mt={4} color="gray.500">
            No properties found
          </Text>
        </Box>
      )}
    </VStack>
  );

  // Render Reports
  const renderReports = () => (
    <VStack spacing={4} align="stretch">
      <HStack justify="space-between">
        <Heading size="md">Reports</Heading>
        <HStack spacing={2}>
          <Button leftIcon={<FiPlus />} colorScheme="blue" size="sm">
            Generate Report
          </Button>
        </HStack>
      </HStack>
      
      {reports.length > 0 ? (
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Report Name</Th>
                <Th>Dimensions</Th>
                <Th>Metrics</Th>
                <Th>Rows</Th>
                <Th>Created</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {reports.map((report) => (
                <Tr key={report.name}>
                  <Td>
                    <HStack>
                      <Icon as={FiFile} boxSize={4} />
                      <Text>{report.name}</Text>
                    </HStack>
                  </Td>
                  <Td>{report.dimensions.length}</Td>
                  <Td>{report.metrics.length}</Td>
                  <Td>{report.rowCount}</Td>
                  <Td>-</Td>
                  <Td>
                    <HStack spacing={1}>
                      <IconButton
                        icon={<FiEye />}
                        variant="ghost"
                        size="sm"
                        aria-label="View report"
                      />
                      <IconButton
                        icon={<FiDownload />}
                        variant="ghost"
                        size="sm"
                        aria-label="Export report"
                      />
                    </HStack>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
      ) : (
        <Box textAlign="center" py={10}>
          <Icon as={FiFile} boxSize={12} color="gray.400" />
          <Text mt={4} color="gray.500">
            No reports generated yet
          </Text>
        </Box>
      )}
    </VStack>
  );

  // Render Skills
  const renderSkills = () => (
    <VStack spacing={4} align="stretch">
      <Text fontSize="lg" fontWeight="bold">ATOM Skills</Text>
      
      <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiBarChart} boxSize={8} color="blue.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Property Management</Text>
                <Text fontSize="sm" color="gray.500">
                  Manage GA4 properties and data streams
                </Text>
              </VStack>
              <Button 
                colorScheme="blue" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_get_properties', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiFile} boxSize={8} color="green.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Report Generation</Text>
                <Text fontSize="sm" color="gray.500">
                  Generate comprehensive analytics reports
                </Text>
              </VStack>
              <Button 
                colorScheme="green" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_generate_report', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiUsers} boxSize={8} color="purple.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Audience Management</Text>
                <Text fontSize="sm" color="gray.500">
                  Create and manage GA4 audiences
                </Text>
              </VStack>
              <Button 
                colorScheme="purple" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_create_audience', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiShoppingCart} boxSize={8} color="orange.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Ecommerce Tracking</Text>
                <Text fontSize="sm" color="gray.500">
                  Track ecommerce events and conversions
                </Text>
              </VStack>
              <Button 
                colorScheme="orange" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_track_ecommerce_event', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiActivity} boxSize={8} color="red.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Real-time Analytics</Text>
                <Text fontSize="sm" color="gray.500">
                  Monitor real-time user activity
                </Text>
              </VStack>
              <Button 
                colorScheme="red" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_run_realtime_report', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiShield} boxSize={8} color="teal.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Compliance Reports</Text>
                <Text fontSize="sm" color="gray.500">
                  Generate GDPR and privacy compliance reports
                </Text>
              </VStack>
              <Button 
                colorScheme="teal" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_get_compliance_report', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiTarget} boxSize={8} color="cyan.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Conversion Optimization</Text>
                <Text fontSize="sm" color="gray.500">
                  Analyze and optimize conversion rates
                </Text>
              </VStack>
              <Button 
                colorScheme="cyan" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_optimize_conversion_rates', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiNavigation} boxSize={8} color="indigo.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Traffic Analysis</Text>
                <Text fontSize="sm" color="gray.500">
                  Analyze traffic sources and acquisition
                </Text>
              </VStack>
              <Button 
                colorScheme="indigo" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_analyze_traffic_sources', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>

        <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
          <CardBody>
            <VStack spacing={3}>
              <Icon as={FiCpu} boxSize={8} color="pink.500" />
              <VStack align="start" spacing={1}>
                <Text fontWeight="bold">Predictive Analytics</Text>
                <Text fontSize="sm" color="gray.500">
                  Use ML to predict user behavior
                </Text>
              </VStack>
              <Button 
                colorScheme="pink" 
                size="sm" 
                onClick={() => handleExecuteSkill('ganalytics4_predict_user_behavior', {})}
              >
                Execute
              </Button>
            </VStack>
          </CardBody>
        </Card>
      </SimpleGrid>
    </VStack>
  );

  return (
    <Box p={6} bg={bgColor} minH="100vh">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={3}>
            <Icon as={FiBarChart} boxSize={8} color="blue.500" />
            <VStack align="start" spacing={0}>
              <Heading size="lg">Google Analytics 4 Manager</Heading>
              <Text fontSize="sm" color="gray.500">
                ATOM Web Analytics & Marketing Measurement
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            <Badge
              colorScheme={isConnected ? 'green' : 'red'}
              variant="solid"
            >
              {isConnected ? 'Connected' : 'Disconnected'}
            </Badge>
            
            {isSyncing && (
              <Badge colorScheme="blue" variant="solid">
                Syncing
              </Badge>
            )}
            
            <Button
              leftIcon={<FiRefreshCw />}
              onClick={() => window.location.reload()}
              variant="outline"
              size="sm"
            >
              Refresh
            </Button>
            
            <Button
              leftIcon={<FiSettings />}
              onClick={() => setConfigModalOpen(true)}
              variant="outline"
              size="sm"
            >
              Configure
            </Button>
          </HStack>
        </HStack>

        {/* Connection Status */}
        {renderConnectionStatus()}

        {/* Sync Progress */}
        {currentSyncSession && (
          <Card>
            <CardHeader>
              <HStack justify="space-between">
                <Heading size="md">Data Sync Progress</Heading>
                <Badge colorScheme="blue" variant="solid">
                  {currentSyncSession.status}
                </Badge>
              </HStack>
            </CardHeader>
            <CardBody>
              <VStack spacing={4} align="stretch">
                <Progress
                  value={currentSyncSession.progress.percentage}
                  colorScheme="green"
                  size="lg"
                  hasStripe
                  isAnimated
                />
                
                <HStack justify="space-between">
                  <Text fontSize="sm">
                    {currentSyncSession.progress.processed} / {currentSyncSession.progress.total} items
                  </Text>
                  <Text fontSize="sm">
                    {currentSyncSession.progress.currentItem || 'Processing...'}
                  </Text>
                </HStack>
                
                {currentSyncSession.progress.errors > 0 && (
                  <Alert status="warning">
                    <AlertIcon />
                    <Text fontSize="sm">
                      {currentSyncSession.progress.errors} errors encountered during sync
                    </Text>
                  </Alert>
                )}
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Main Content */}
        <Tabs 
          value={activeTab}
          onChange={(value) => setActiveTab(value)}
          variant="enclosed"
          colorScheme="blue"
        >
          <TabList>
            <Tab>Dashboard</Tab>
            <Tab>Properties</Tab>
            <Tab>Reports</Tab>
            <Tab>Audiences</Tab>
            <Tab>Ecommerce</Tab>
            <Tab>Skills</Tab>
          </TabList>
          
          <TabPanels>
            <TabPanel>
              {renderAnalyticsDashboard()}
            </TabPanel>
            
            <TabPanel>
              {renderProperties()}
            </TabPanel>
            
            <TabPanel>
              {renderReports()}
            </TabPanel>
            
            <TabPanel>
              <Text>Audiences management interface</Text>
            </TabPanel>
            
            <TabPanel>
              <Text>Ecommerce tracking and analysis</Text>
            </TabPanel>
            
            <TabPanel>
              {renderSkills()}
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default GA4Manager;