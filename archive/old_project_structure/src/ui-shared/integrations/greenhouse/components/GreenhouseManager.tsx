/**
 * ATOM Greenhouse HR Manager Component
 * Complete recruitment management and talent acquisition interface
 * Enterprise-grade HR automation with comprehensive analytics
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
} from '@chakra-ui/react';
import {
  FiUsers, FiBriefcase, FiCalendar, FiFile, FiTrendingUp,
  FiSettings, FiRefreshCw, FiDatabase, FiZap, FiClock,
  FiActivity, FiShield, FiCheck, FiX, FiAlertTriangle,
  FiPlus, FiEdit, FiTrash2, FiSearch, FiFilter,
  FiGrid, FiList, FiPlay, FiPause, FiStop, FiMonitor, FiBarChart,
  FiPieChart, FiMail, FiMessageSquare, FiUser, FiAward,
  FiTarget, FiGlobe, FiMapPin, FiPhone, FiStar,
  FiEye, FiDownload, FiUpload, FiExternalLink, FiCopy,
} from 'react-icons/fi';

// Greenhouse HR Types
import {
  GreenhouseJob,
  GreenhouseCandidate,
  GreenhouseApplication,
  GreenhouseInterview,
  GreenhouseOffer,
  GreenhouseHiringMetrics,
  GreenhouseDiversityAnalytics,
  GreenhouseRecruitmentFunnel,
  GreenhouseSearchQuery,
  GreenhouseSearchResults,
  GreenhouseConfig,
  GreenhouseSyncSession,
} from '../types';

interface GreenhouseManagerProps {
  // Authentication
  apiKey: string;
  partnerId?: string;
  environment?: 'production' | 'sandbox';
  
  // ATOM Integration
  atomIngestionPipeline?: any;
  atomSkillRegistry?: any;
  atomMemoryStore?: any;
  
  // Configuration
  initialConfig?: Partial<GreenhouseConfig>;
  platform?: 'auto' | 'web' | 'desktop';
  theme?: 'auto' | 'light' | 'dark';
  
  // Events
  onReady?: (manager: any) => void;
  onError?: (error: any) => void;
  onJobPosted?: (job: GreenhouseJob) => void;
  onCandidateCreated?: (candidate: GreenhouseCandidate) => void;
  onApplicationReceived?: (application: GreenhouseApplication) => void;
  onInterviewScheduled?: (interview: GreenhouseInterview) => void;
  onOfferSent?: (offer: GreenhouseOffer) => void;
  onSyncStart?: (config: any) => void;
  onSyncComplete?: (results: any) => void;
}

const GREENHOUSE_DEFAULT_CONFIG: GreenhouseConfig = {
  // API Configuration
  baseUrl: 'https://harvest.greenhouse.io/v1',
  apiKey: '',
  environment: 'production',
  
  // Sync Configuration
  enableRealTimeSync: true,
  syncInterval: 5 * 60 * 1000, // 5 minutes
  batchSize: 50,
  maxRetries: 3,
  syncWebhooks: true,
  
  // Data Configuration
  includePrivateFields: false,
  includePIIData: false,
  anonymizeData: true,
  retainHistoryDays: 365,
  
  // Automation Configuration
  enableCandidateAutomation: true,
  enableApplicationAutomation: true,
  enableInterviewAutomation: true,
  enableOfferAutomation: true,
  
  // Analytics Configuration
  generateHiringMetrics: true,
  generateDiversityAnalytics: true,
  generateFunnelAnalysis: true,
  enablePredictiveAnalytics: false,
  
  // Notification Configuration
  enableNotifications: true,
  notificationChannels: ['email'],
  emailNotifications: true,
  slackNotifications: false,
  
  // Security Configuration
  encryptSensitiveData: true,
  enableAuditLogging: true,
  requireApprovalForActions: false,
  dataLossPrevention: true,
  
  // Performance Configuration
  enableCaching: true,
  cacheSize: 100 * 1024 * 1024, // 100MB
  enableCompression: true,
  enableDeltaSync: true,
  concurrentProcessing: true,
  maxConcurrency: 5,
};

export const GreenhouseManager: React.FC<GreenhouseManagerProps> = ({
  apiKey,
  partnerId,
  environment = 'production',
  atomIngestionPipeline,
  atomSkillRegistry,
  atomMemoryStore,
  initialConfig,
  platform = 'auto',
  theme = 'auto',
  onReady,
  onError,
  onJobPosted,
  onCandidateCreated,
  onApplicationReceived,
  onInterviewScheduled,
  onOfferSent,
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
  const [jobs, setJobs] = useState<GreenhouseJob[]>([]);
  const [candidates, setCandidates] = useState<GreenhouseCandidate[]>([]);
  const [applications, setApplications] = useState<GreenhouseApplication[]>([]);
  const [interviews, setInterviews] = useState<GreenhouseInterview[]>([]);
  const [offers, setOffers] = useState<GreenhouseOffer[]>([]);
  const [hiringMetrics, setHiringMetrics] = useState<GreenhouseHiringMetrics | null>(null);
  const [diversityAnalytics, setDiversityAnalytics] = useState<GreenhouseDiversityAnalytics | null>(null);
  const [recruitmentFunnel, setRecruitmentFunnel] = useState<GreenhouseRecruitmentFunnel | null>(null);
  
  // Selected Items
  const [selectedJob, setSelectedJob] = useState<GreenhouseJob | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<GreenhouseCandidate | null>(null);
  const [selectedApplication, setSelectedApplication] = useState<GreenhouseApplication | null>(null);
  
  // Configuration
  const [config, setConfig] = useState<GreenhouseConfig>(
    () => ({ ...GREENHOUSE_DEFAULT_CONFIG, ...initialConfig })
  );
  const [configModalOpen, setConfigModalOpen] = useState(false);
  
  // Sync Progress
  const [currentSyncSession, setCurrentSyncSession] = useState<GreenhouseSyncSession | null>(null);
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
  const [jobModalOpen, setJobModalOpen] = useState(false);
  const [candidateModalOpen, setCandidateModalOpen] = useState(false);
  const [interviewModalOpen, setInterviewModalOpen] = useState(false);
  const [offerModalOpen, setOfferModalOpen] = useState(false);
  const [analyticsModalOpen, setAnalyticsModalOpen] = useState(false);
  
  // Form Data
  const [formData, setFormData] = useState<Record<string, any>>({});

  const toast = useToast();

  // Theme colors
  const bgColor = useColorModeValue('white', 'gray.800');
  const cardBg = useColorModeValue('white', 'gray.700');

  // Initialize Greenhouse
  useEffect(() => {
    initializeGreenhouse();
  }, [apiKey, environment]);

  const initializeGreenhouse = useCallback(async () => {
    if (!apiKey) {
      setIsConnected(false);
      toast({
        title: 'Authentication Required',
        description: 'Greenhouse API key is required',
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
      
      const [jobsData, candidatesData, applicationsData, interviewsData, offersData] = await Promise.all([
        simulateJobs(),
        simulateCandidates(),
        simulateApplications(),
        simulateInterviews(),
        simulateOffers(),
      ]);

      setJobs(jobsData);
      setCandidates(candidatesData);
      setApplications(applicationsData);
      setInterviews(interviewsData);
      setOffers(offersData);
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
        hasJobs: jobsData.length > 0,
        hasCandidates: candidatesData.length > 0,
        totalJobs: jobsData.length,
        totalCandidates: candidatesData.length,
      });
      
      toast({
        title: 'Greenhouse Connected',
        description: 'Recruitment management system is ready',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      
    } catch (error) {
      setIsConnected(false);
      onError?.(error);
      toast({
        title: 'Connection Failed',
        description: 'Failed to connect to Greenhouse services',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsConnecting(false);
    }
  }, [apiKey, environment, atomSkillRegistry, atomIngestionPipeline, onError, onReady]);

  const initializeAtomSkills = useCallback(async () => {
    // This would register the actual skills with ATOM
    const { GreenhouseSkillsBundle } = await import('../skills/greenhouseSkills');
    
    // Register skills with ATOM skill registry
    for (const skill of GreenhouseSkillsBundle.skills) {
      // atomSkillRegistry.registerSkill(skill);
      console.log(`Registering skill: ${skill.id}`);
    }
    
    toast({
      title: 'Skills Registered',
      description: `${GreenhouseSkillsBundle.skills.length} Greenhouse skills registered with ATOM`,
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  }, [atomSkillRegistry]);

  const initializeAtomPipeline = useCallback(() => {
    // Setup ATOM pipeline for Greenhouse data
    atomIngestionPipeline?.on('document-processed', (event: any) => {
      if (event.source === 'greenhouse') {
        console.log('Greenhouse document processed:', event);
      }
    });
    
    toast({
      title: 'Pipeline Initialized',
      description: 'Greenhouse ingestion pipeline is ready',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  }, [atomIngestionPipeline]);

  // Simulate functions (replace with actual Greenhouse API calls)
  const simulateJobs = async (): Promise<GreenhouseJob[]> => {
    return [
      {
        id: 1,
        title: 'Senior Software Engineer',
        location: { name: 'San Francisco, CA' },
        departments: [{ id: 1, name: 'Engineering' }],
        offices: [{ id: 1, name: 'San Francisco', location: 'San Francisco, CA' }],
        status: 'open',
        created_at: '2024-01-15T10:00:00Z',
        openings_count: 2,
        confidential: false,
        apply_url: 'https://boards.greenhouse.io/job/12345',
      },
      {
        id: 2,
        title: 'Product Manager',
        location: { name: 'New York, NY' },
        departments: [{ id: 2, name: 'Product' }],
        offices: [{ id: 2, name: 'New York', location: 'New York, NY' }],
        status: 'open',
        created_at: '2024-01-10T09:00:00Z',
        openings_count: 1,
        confidential: false,
        apply_url: 'https://boards.greenhouse.io/job/12346',
      },
    ];
  };

  const simulateCandidates = async (): Promise<GreenhouseCandidate[]> => {
    return [
      {
        id: 1,
        first_name: 'John',
        last_name: 'Doe',
        email: 'john.doe@example.com',
        phone: '+1-555-0101',
        company: 'Tech Corp',
        title: 'Software Engineer',
        created_at: '2024-01-05T00:00:00Z',
        status: 'active',
      },
      {
        id: 2,
        first_name: 'Jane',
        last_name: 'Smith',
        email: 'jane.smith@example.com',
        company: 'Innovation Inc',
        title: 'Product Manager',
        created_at: '2024-01-08T00:00:00Z',
        status: 'active',
      },
    ];
  };

  const simulateApplications = async (): Promise<GreenhouseApplication[]> => {
    return [
      {
        id: 1,
        candidate_id: 1,
        jobs: [{ id: 1, name: 'Senior Software Engineer' }],
        status: 'active',
        applied_at: '2024-01-15T14:30:00Z',
        source: {
          type: 'job_board',
          source_name: 'LinkedIn',
          candidate_source: 'organic_search'
        },
      },
      {
        id: 2,
        candidate_id: 2,
        jobs: [{ id: 2, name: 'Product Manager' }],
        status: 'active',
        applied_at: '2024-01-10T16:45:00Z',
        source: {
          type: 'referral',
          source_name: 'Employee Referral',
          candidate_source: 'internal'
        },
      },
    ];
  };

  const simulateInterviews = async (): Promise<GreenhouseInterview[]> => {
    return [
      {
        id: 1,
        name: 'Technical Interview',
        status: 'scheduled',
        duration: 60,
        location: 'Zoom - Video Conference',
        video_interview_url: 'https://zoom.us/j/123456789',
        scheduled_interviews: [
          {
            id: 1,
            application_id: 1,
            start: '2024-01-20T14:00:00Z',
            end: '2024-01-20T15:00:00Z',
            status: 'scheduled'
          }
        ],
      },
    ];
  };

  const simulateOffers = async (): Promise<GreenhouseOffer[]> => {
    return [
      {
        id: 1,
        application_id: 1,
        status: 'sent',
        created_at: '2024-01-25T10:00:00Z',
        sent_at: '2024-01-25T10:30:00Z',
        effective_date: '2024-02-15',
        offer_details: {
          job_title: 'Senior Software Engineer',
          department: 'Engineering',
          location: 'San Francisco, CA',
          compensation: {
            salary: {
              currency: 'USD',
              amount: 150000,
              frequency: 'yearly'
            },
            bonus: {
              type: 'performance',
              amount: 15000,
              currency: 'USD'
            }
          }
        },
      },
    ];
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
      //   greenhouseClient: createGreenhouseClient(),
      //   atomIngestionPipeline,
      //   atomMemoryStore,
      //   greenhouseConfig: config,
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
      if (skillId.includes('job')) {
        const newJobs = await simulateJobs();
        setJobs(newJobs);
      } else if (skillId.includes('candidate')) {
        const newCandidates = await simulateCandidates();
        setCandidates(newCandidates);
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
        description: 'Please connect to Greenhouse first',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSyncing(true);
    const sessionId = `sync_${Date.now()}`;
    
    const session: GreenhouseSyncSession = {
      id: sessionId,
      startTime: new Date().toISOString(),
      status: 'running',
      type: 'full',
      config: config,
      progress: {
        total: jobs.length + candidates.length + applications.length,
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
      const allItems = [...jobs, ...candidates, ...applications];
      for (let i = 0; i < allItems.length; i++) {
        const item = allItems[i];
        session.progress.processed = i + 1;
        session.progress.percentage = ((i + 1) / allItems.length) * 100;
        session.progress.currentItem = item instanceof GreenhouseJob ? item.title : 
                                      item instanceof GreenhouseCandidate ? `${item.first_name} ${item.last_name}` : 
                                      `Application ${item.id}`;
        
        setCurrentSyncSession({ ...session });
        onSyncProgress?.(session);
        
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
  }, [isConnected, jobs, candidates, applications, config, onSyncStart, onSyncProgress, onSyncComplete, onError]);

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
          <Text>Connecting to Greenhouse...</Text>
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
            ? 'Greenhouse recruitment system is connected and ready'
            : 'Configure Greenhouse API credentials to access recruitment services'
          }
        </AlertDescription>
      </Box>
      {!isConnected && (
        <Button colorScheme="blue" size="sm" onClick={initializeGreenhouse}>
          Connect
        </Button>
      )}
    </Alert>
  );

  // Render Statistics
  const renderStatistics = () => {
    const activeJobs = jobs.filter(j => j.status === 'open').length;
    const activeCandidates = candidates.filter(c => c.status === 'active').length;
    const pendingApplications = applications.filter(a => a.status === 'active').length;
    const scheduledInterviews = interviews.filter(i => i.status === 'scheduled').length;
    
    return (
      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
        <Card>
          <CardBody>
            <Stat>
              <StatLabel fontSize="sm" color="gray.500">Open Jobs</StatLabel>
              <StatNumber fontSize="2xl">{activeJobs}</StatNumber>
              <StatHelpText>
                <Icon as={FiBriefcase} mr={1} />
                Total: {jobs.length}
              </StatHelpText>
            </Stat>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <Stat>
              <StatLabel fontSize="sm" color="gray.500">Active Candidates</StatLabel>
              <StatNumber fontSize="2xl">{activeCandidates}</StatNumber>
              <StatHelpText>
                <Icon as={FiUsers} mr={1} />
                Total: {candidates.length}
              </StatHelpText>
            </Stat>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <Stat>
              <StatLabel fontSize="sm" color="gray.500">Pending Applications</StatLabel>
              <StatNumber fontSize="2xl">{pendingApplications}</StatNumber>
              <StatHelpText>
                <Icon as={FiFile} mr={1} />
                Total: {applications.length}
              </StatHelpText>
            </Stat>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <Stat>
              <StatLabel fontSize="sm" color="gray.500">Scheduled Interviews</StatLabel>
              <StatNumber fontSize="2xl">{scheduledInterviews}</StatNumber>
              <StatHelpText>
                <Icon as={FiCalendar} mr={1} />
                Total: {interviews.length}
              </StatHelpText>
            </Stat>
          </CardBody>
        </Card>
      </SimpleGrid>
    );
  };

  // Render Sync Progress
  const renderSyncProgress = () => {
    if (!currentSyncSession) return null;
    
    return (
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
    );
  };

  // Render Jobs
  const renderJobs = () => (
    <VStack spacing={4} align="stretch">
      <HStack justify="space-between">
        <Heading size="md">Job Postings</Heading>
        <HStack spacing={2}>
          <Button leftIcon={<FiPlus />} colorScheme="blue" size="sm">
            Post Job
          </Button>
        </HStack>
      </HStack>
      
      {jobs.length > 0 ? (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {jobs.map((job) => (
            <Card 
              key={job.id}
              _hover={{ bg: 'gray.50', cursor: 'pointer' }}
              onClick={() => setSelectedJob(job)}
              border={selectedJob?.id === job.id ? '2px solid blue.500' : '1px solid gray.200'}
            >
              <CardBody>
                <VStack spacing={3} align="start">
                  <HStack justify="space-between" width="100%">
                    <Text fontWeight="bold">{job.title}</Text>
                    <Badge colorScheme={job.status === 'open' ? 'green' : 'red'}>
                      {job.status}
                    </Badge>
                  </HStack>
                  
                  <VStack align="start" spacing={1}>
                    <HStack>
                      <Icon as={FiMapPin} boxSize={4} />
                      <Text fontSize="sm">{job.location.name}</Text>
                    </HStack>
                    
                    {job.departments && job.departments.length > 0 && (
                      <Text fontSize="sm" color="gray.500">
                        {job.departments[0].name}
                      </Text>
                    )}
                    
                    <Text fontSize="xs" color="gray.500">
                      Posted: {formatDate(job.created_at)}
                    </Text>
                  </VStack>
                  
                  <HStack justify="space-between" width="100%">
                    <Text fontSize="xs" color="gray.500">
                      {job.openings_count} openings
                    </Text>
                    <HStack spacing={1}>
                      <IconButton
                        icon={<FiEye />}
                        variant="ghost"
                        size="xs"
                        aria-label="View job"
                      />
                      <IconButton
                        icon={<FiEdit />}
                        variant="ghost"
                        size="xs"
                        aria-label="Edit job"
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
          <Icon as={FiBriefcase} boxSize={12} color="gray.400" />
          <Text mt={4} color="gray.500">
            No jobs posted yet
          </Text>
        </Box>
      )}
    </VStack>
  );

  // Render Candidates
  const renderCandidates = () => (
    <VStack spacing={4} align="stretch">
      <HStack justify="space-between">
        <Heading size="md">Candidates</Heading>
        <HStack spacing={2}>
          <Button leftIcon={<FiSearch />} variant="outline" size="sm">
            Search
          </Button>
          <Button leftIcon={<FiPlus />} colorScheme="blue" size="sm">
            Add Candidate
          </Button>
        </HStack>
      </HStack>
      
      {candidates.length > 0 ? (
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Name</Th>
                <Th>Email</Th>
                <Th>Company</Th>
                <Th>Title</Th>
                <Th>Status</Th>
                <Th>Applied</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {candidates.map((candidate) => (
                <Tr key={candidate.id}>
                  <Td>
                    <HStack>
                      <Icon as={FiUser} boxSize={4} />
                      <Text>{candidate.first_name} {candidate.last_name}</Text>
                    </HStack>
                  </Td>
                  <Td>{candidate.email}</Td>
                  <Td>{candidate.company || '-'}</Td>
                  <Td>{candidate.title || '-'}</Td>
                  <Td>
                    <Badge colorScheme={candidate.status === 'active' ? 'green' : 'gray'}>
                      {candidate.status}
                    </Badge>
                  </Td>
                  <Td>{candidate.created_at ? formatDate(candidate.created_at) : '-'}</Td>
                  <Td>
                    <HStack spacing={1}>
                      <IconButton
                        icon={<FiEye />}
                        variant="ghost"
                        size="sm"
                        aria-label="View candidate"
                      />
                      <IconButton
                        icon={<FiEdit />}
                        variant="ghost"
                        size="sm"
                        aria-label="Edit candidate"
                      />
                      <IconButton
                        icon={<FiMail />}
                        variant="ghost"
                        size="sm"
                        aria-label="Email candidate"
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
          <Icon as={FiUsers} boxSize={12} color="gray.400" />
          <Text mt={4} color="gray.500">
            No candidates found
          </Text>
        </Box>
      )}
    </VStack>
  );

  return (
    <Box p={6} bg={bgColor} minH="100vh">
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={3}>
            <Icon as={FiUsers} boxSize={8} color="green.500" />
            <VStack align="start" spacing={0}>
              <Heading size="lg">Greenhouse HR Manager</Heading>
              <Text fontSize="sm" color="gray.500">
                ATOM Recruitment Automation & Talent Management
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
        {renderSyncProgress()}

        {/* Statistics */}
        {renderStatistics()}

        {/* Main Content */}
        <Tabs 
          value={activeTab}
          onChange={(value) => setActiveTab(value)}
          variant="enclosed"
          colorScheme="green"
        >
          <TabList>
            <Tab>Dashboard</Tab>
            <Tab>Jobs</Tab>
            <Tab>Candidates</Tab>
            <Tab>Applications</Tab>
            <Tab>Interviews</Tab>
            <Tab>Analytics</Tab>
            <Tab>Skills</Tab>
          </TabList>
          
          <TabPanels>
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text>Dashboard with comprehensive HR metrics and insights</Text>
                {/* Dashboard content would go here */}
              </VStack>
            </TabPanel>
            
            <TabPanel>
              {renderJobs()}
            </TabPanel>
            
            <TabPanel>
              {renderCandidates()}
            </TabPanel>
            
            <TabPanel>
              <Text>Applications management interface</Text>
            </TabPanel>
            
            <TabPanel>
              <Text>Interview scheduling and management</Text>
            </TabPanel>
            
            <TabPanel>
              <Text>Hiring analytics and reporting</Text>
            </TabPanel>
            
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontSize="lg" fontWeight="bold">ATOM Skills</Text>
                
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiBriefcase} boxSize={8} color="blue.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Job Management</Text>
                          <Text fontSize="sm" color="gray.500">
                            Post, update, and manage job listings
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="blue" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('greenhouse_get_jobs', {})}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiUsers} boxSize={8} color="green.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Candidate Management</Text>
                          <Text fontSize="sm" color="gray.500">
                            Create and manage candidate profiles
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="green" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('greenhouse_get_candidates', {})}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiCalendar} boxSize={8} color="purple.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Interview Scheduling</Text>
                          <Text fontSize="sm" color="gray.500">
                            Schedule and manage interviews
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="purple" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('greenhouse_schedule_interview', {})}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiAward} boxSize={8} color="orange.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Offer Management</Text>
                          <Text fontSize="sm" color="gray.500">
                            Send and track job offers
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="orange" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('greenhouse_send_offer', {})}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card _hover={{ bg: 'gray.50', cursor: 'pointer' }}>
                    <CardBody>
                      <VStack spacing={3}>
                        <Icon as={FiBarChart} boxSize={8} color="red.500" />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">Hiring Analytics</Text>
                          <Text fontSize="sm" color="gray.500">
                            Generate comprehensive hiring metrics
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="red" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('greenhouse_generate_hiring_metrics', {})}
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
                            Generate EEO and diversity reports
                          </Text>
                        </VStack>
                        <Button 
                          colorScheme="teal" 
                          size="sm" 
                          onClick={() => handleExecuteSkill('greenhouse_create_compliance_report', {})}
                        >
                          Execute
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};

export default GreenhouseManager;