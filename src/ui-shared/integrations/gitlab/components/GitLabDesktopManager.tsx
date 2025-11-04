/**
 * GitLab Desktop Manager
 * Enhanced desktop integration for GitLab with Tauri
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Progress,
  Divider,
  useColorModeValue,
  Alert,
  AlertIcon,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalCloseButton,
  ModalBody,
  ModalFooter,
  FormControl,
  FormLabel,
  Input,
  Switch,
  Checkbox,
  Select,
  NumberInput,
  NumberInputField,
  Stack,
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
  TableContainer,
  Tag,
  Spinner,
  useDisclosure,
  List,
  ListItem,
  ListIcon,
  Avatar,
  AvatarGroup,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  IconButton,
  Drawer,
  DrawerOverlay,
  DrawerContent,
  DrawerHeader,
  DrawerCloseButton,
  DrawerBody
} from '@chakra-ui/react';
import {
  GitlabIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  SettingsIcon,
  ExternalLinkIcon,
  AddIcon,
  ViewIcon,
  RepeatIcon,
  BellIcon,
  RocketIcon,
  CodeIcon,
  BugIcon,
  MergeIcon,
  HistoryIcon,
  UserIcon,
  GroupIcon,
  ServerIcon,
  ClockIcon,
  CheckIcon,
  CrossIcon,
  DocumentIcon,
  FolderIcon,
  LinkIcon,
  RefreshIcon,
  DesktopIcon,
  NotificationIcon,
  StarIcon,
  EditIcon,
  TrashIcon,
  FilterIcon,
  SearchIcon,
  DownloadIcon,
  UploadIcon
} from '@chakra-ui/icons';
import {
  GitLabProject,
  GitLabConfig,
  GitLabPipeline,
  GitLabIssue,
  GitLabMergeRequest,
  GitLabUser,
  GitLabBranch,
  GitLabCommit
} from '../types';
import { useGitLabProjects, useGitLabPipelines, useGitLabIssues, useGitLabConfig } from '../hooks';
import { GitLabUtils } from '../utils';

interface GitLabDesktopManagerProps {
  atomIngestionPipeline?: any;
  onConfigurationChange?: (config: GitLabConfig) => void;
  onIngestionComplete?: (result: any) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

const GitLabDesktopManager: React.FC<GitLabDesktopManagerProps> = ({
  atomIngestionPipeline,
  onConfigurationChange,
  onIngestionComplete,
  onError,
  userId = 'default-user'
}) => {
  const [config, setConfig] = useState<GitLabConfig>({
    platform: 'gitlab',
    projects: [],
    groups: [],
    include_private_projects: true,
    include_internal_projects: true,
    include_public_projects: false,
    sync_frequency: 'realtime',
    include_pipelines: true,
    include_jobs: true,
    include_issues: true,
    include_merge_requests: true,
    include_releases: true,
    include_webhooks: true,
    max_projects: 50,
    max_pipelines: 100,
    max_jobs: 200,
    max_issues: 100,
    max_merge_requests: 100,
    date_range: {
      start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
      end: new Date()
    },
    webhook_events: [
      'push',
      'merge_request',
      'issue',
      'pipeline',
      'job'
    ],
    enable_notifications: true,
    background_sync: true,
    desktop_notifications: true,
    offline_mode: false
  });

  const [isConnected, setIsConnected] = useState(false);
  const [health, setHealth] = useState({ connected: false, error: null });
  const [ingestionStatus, setIngestionStatus] = useState({
    running: false,
    progress: 0,
    message: ''
  });
  const [selectedProject, setSelectedProject] = useState<GitLabProject | null>(null);
  const [selectedTab, setSelectedTab] = useState('overview');
  const [desktopConfig, setDesktopConfig] = useState({
    autoLaunch: true,
    minimizeToTray: true,
    startInBackground: false,
    notificationsEnabled: true,
    soundEnabled: true,
    syncInterval: 300000, // 5 minutes
    maxCacheSize: 100 // MB
  });
  const [isOnline, setIsOnline] = useState(true);
  const [cacheStatus, setCacheStatus] = useState({
    size: 0,
    entries: 0,
    lastSync: null
  });

  const toast = useToast();
  const { isOpen: isConfigOpen, onOpen: onConfigOpen, onClose: onConfigClose } = useDisclosure();
  const { isOpen: isProjectOpen, onOpen: onProjectOpen, onClose: onProjectClose } = useDisclosure();
  const { isOpen: isDesktopOpen, onOpen: onDesktopOpen, onClose: onDesktopClose } = useDisclosure();
  const { isOpen: isFilterOpen, onOpen: onFilterOpen, onClose: onFilterClose } = useDisclosure();
  
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  // Tauri integration hooks
  const [tauriAvailable, setTauriAvailable] = useState(false);
  const [notificationPermission, setNotificationPermission] = useState('default');

  // Custom hooks for data management
  const {
    projects,
    pipelines,
    issues,
    mergeRequests,
    loading,
    error,
    refreshProjects,
    filterProjects,
    sortProjects,
    projectStats
  } = useGitLabProjects(userId, {
    limit: config.max_projects,
    includePipelines: config.include_pipelines,
    includeIssues: config.include_issues,
    includeMergeRequests: config.include_merge_requests,
    autoRefresh: config.background_sync,
    refreshInterval: config.sync_frequency === 'realtime' ? 30000 : 300000
  });

  const { pipelines: allPipelines } = useGitLabPipelines(userId, {
    limit: config.max_pipelines,
    projectId: selectedProject?.id
  });

  const { issues: allIssues } = useGitLabIssues(userId, {
    limit: config.max_issues,
    projectId: selectedProject?.id
  });

  // Check Tauri availability
  useEffect(() => {
    if (typeof window !== 'undefined' && window.__TAURI__) {
      setTauriAvailable(true);
      checkDesktopCapabilities();
    }
  }, []);

  // Check online status
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const checkDesktopCapabilities = async () => {
    try {
      // Check notification permission
      if (window.__TAURI__?.notification) {
        const permission = await window.__TAURI__.notification.requestPermission();
        setNotificationPermission(permission);
      }
    } catch (error) {
      console.error('Desktop capabilities check failed:', error);
    }
  };

  const checkGitLabHealth = async () => {
    try {
      const response = await fetch('/api/integrations/gitlab/health');
      const data = await response.json();
      
      if (response.ok) {
        setHealth({ connected: data.status === 'healthy', error: null });
        setIsConnected(data.status === 'healthy');
      } else {
        setHealth({ connected: false, error: data.error });
        setIsConnected(false);
      }
    } catch (err) {
      setHealth({ connected: false, error: 'Failed to connect to GitLab' });
      setIsConnected(false);
    }
  };

  const startDesktopOAuth = async () => {
    if (!tauriAvailable) {
      toast({
        title: 'Desktop Not Available',
        description: 'This feature requires the desktop application',
        status: 'warning',
        duration: 3000
      });
      return;
    }

    try {
      // Open system browser for OAuth
      await window.__TAURI__.shell.open('https://gitlab.com/oauth/authorize?client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:8080/auth/gitlab/callback&response_type=code&scope=read_repository+api+read_user');

      // Monitor for OAuth completion via Tauri events
      if (window.__TAURI__?.event) {
        const unlisten = await window.__TAURI__.event.listen('gitlab-oauth-success', (event: any) => {
          checkGitLabHealth();
          refreshProjects();
          
          if (config.desktop_notifications && notificationPermission === 'granted') {
            new Notification('GitLab Connected', {
              body: 'Successfully connected to your GitLab account',
              icon: '/icons/gitlab.png'
            });
          }

          toast({
            title: 'GitLab Connected',
            description: 'Successfully connected to your GitLab account',
            status: 'success',
            duration: 3000
          });
        });

        // Auto-cleanup after 5 minutes
        setTimeout(() => unlisten(), 300000);
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Desktop OAuth failed');
      onError?.(error);
      
      toast({
        title: 'GitLab OAuth Failed',
        description: error.message,
        status: 'error',
        duration: 5000
      });
    }
  };

  const startDesktopIngestion = async () => {
    if (!isConnected || !atomIngestionPipeline) {
      toast({
        title: 'Cannot Start Ingestion',
        description: 'Please connect to GitLab first',
        status: 'warning',
        duration: 3000
      });
      return;
    }

    setIngestionStatus({ running: true, progress: 0, message: 'Starting desktop data ingestion...' });
    
    try {
      // Show desktop notification
      if (config.desktop_notifications && notificationPermission === 'granted') {
        new Notification('GitLab Ingestion Started', {
          body: 'Syncing your GitLab data to ATOM...',
          icon: '/icons/gitlab.png'
        });
      }

      // Register integration with ATOM pipeline
      await atomIngestionPipeline.registerIntegration({
        platform: 'gitlab',
        config,
        userId
      });

      setIngestionStatus({ running: true, progress: 25, message: 'Registering desktop integration...' });
      
      // Start data ingestion
      const result = await atomIngestionPipeline.executeSkill('gitlab-start-ingestion', {
        user_id: userId,
        config
      });

      setIngestionStatus({ running: true, progress: 75, message: 'Processing GitLab data...' });
      
      // Update progress and complete
      setIngestionStatus({ running: true, progress: 100, message: 'Desktop ingestion complete!' });
      
      onIngestionComplete?.(result);
      
      // Show completion notification
      if (config.desktop_notifications && notificationPermission === 'granted') {
        new Notification('GitLab Ingestion Complete', {
          body: 'Successfully ingested GitLab data into ATOM',
          icon: '/icons/gitlab.png'
        });
      }
      
      toast({
        title: 'GitLab Desktop Ingestion Complete',
        description: 'Successfully ingested GitLab data into ATOM',
        status: 'success',
        duration: 3000
      });
      
      setTimeout(() => {
        setIngestionStatus({ running: false, progress: 0, message: '' });
      }, 2000);
      
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Desktop ingestion failed');
      onError?.(error);
      
      setIngestionStatus({ running: false, progress: 0, message: '' });
      
      toast({
        title: 'Desktop Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000
      });
    }
  };

  const refreshDesktopProjects = async () => {
    await refreshProjects();
    
    if (config.desktop_notifications && notificationPermission === 'granted') {
      new Notification('GitLab Projects Refreshed', {
        body: 'Projects have been updated',
        icon: '/icons/gitlab.png'
      });
    }
  };

  const openProjectInBrowser = async (project: GitLabProject) => {
    if (tauriAvailable && window.__TAURI__?.shell) {
      await window.__TAURI__.shell.open(project.namespace.web_url);
    }
  };

  const minimizeToTray = async () => {
    if (tauriAvailable && window.__TAURI__?.window) {
      await window.__TAURI__.window.getCurrent().hide();
    }
  };

  const clearCache = async () => {
    if (tauriAvailable && window.__TAURI__?.fs) {
      try {
        // Clear desktop cache
        await window.__TAURI__.fs.removeDir('cache/gulab', { recursive: true });
        setCacheStatus({ size: 0, entries: 0, lastSync: null });
        
        toast({
          title: 'Cache Cleared',
          description: 'GitLab cache has been cleared',
          status: 'info',
          duration: 3000
        });
      } catch (error) {
        toast({
          title: 'Cache Clear Failed',
          description: 'Failed to clear cache',
          status: 'error',
          duration: 3000
        });
      }
    }
  };

  const updateConfig = (newConfig: Partial<GitLabConfig>) => {
    const updatedConfig = { ...config, ...newConfig };
    setConfig(updatedConfig);
    onConfigurationChange?.(updatedConfig);
  };

  const updateDesktopConfig = (newConfig: Partial<typeof desktopConfig>) => {
    const updatedConfig = { ...desktopConfig, ...newConfig };
    setDesktopConfig(updatedConfig);
    
    // Save to local storage
    if (tauriAvailable && window.__TAURI__?.storage) {
      window.__TAURI__.storage.set({
        key: 'gitlab-desktop-config',
        value: JSON.stringify(updatedConfig)
      });
    }
  };

  const handleProjectClick = (project: GitLabProject) => {
    setSelectedProject(project);
    onProjectOpen();
  };

  const getProjectVisibility = (visibility: string) => {
    const colors = {
      public: 'green',
      internal: 'yellow',
      private: 'red'
    };
    return colors[visibility as keyof typeof colors] || 'gray';
  };

  const getPipelineStatus = (status: string) => {
    const colors = {
      success: 'green',
      running: 'blue',
      failed: 'red',
      pending: 'yellow',
      created: 'gray',
      skipped: 'gray',
      canceled: 'gray',
      manual: 'purple'
    };
    return colors[status as keyof typeof colors] || 'gray';
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      {/* Desktop Header */}
      <VStack spacing={6} align="stretch">
        <HStack justify="space-between">
          <HStack spacing={4}>
            <Icon as={GitlabIcon} w={10} h={10} color="orange.500" />
            <VStack align="start" spacing={1">
              <Heading size="2xl" color="orange.500">
                GitLab Desktop
              </Heading>
              <HStack>
                <Icon as={DesktopIcon} w={4} h={4} color="blue.500" />
                <Text color="gray.600" fontSize="md">
                  Desktop Application
                </Text>
                {!isOnline && (
                  <Badge colorScheme="red" size="sm">
                    Offline
                  </Badge>
                )}
              </HStack>
            </VStack>
          </HStack>
          
          <HStack spacing={4}>
            <IconButton
              variant="outline"
              aria-label="Desktop settings"
              icon={<SettingsIcon />}
              onClick={onDesktopOpen}
            />
            <IconButton
              variant="outline"
              aria-label="Clear cache"
              icon={<TrashIcon />}
              onClick={clearCache}
            />
            <IconButton
              variant="outline"
              aria-label="Minimize to tray"
              icon={<DesktopIcon />}
              onClick={minimizeToTray}
            />
            <Button
              variant="outline"
              leftIcon={<RefreshIcon />}
              onClick={refreshDesktopProjects}
              isLoading={loading}
            >
              Refresh
            </Button>
            {!isConnected ? (
              <Button
                colorScheme="orange"
                leftIcon={<GitlabIcon />}
                onClick={startDesktopOAuth}
              >
                Connect GitLab
              </Button>
            ) : (
              <Button
                colorScheme="green"
                leftIcon={<RocketIcon />}
                onClick={startDesktopIngestion}
                isDisabled={ingestionStatus.running}
              >
                {ingestionStatus.running ? 'Ingesting...' : 'Start Ingestion'}
              </Button>
            )}
          </HStack>
        </HStack>

        {/* Desktop Status Bar */}
        <Card>
          <CardBody>
            <HStack justify="space-between" align="center">
              <HStack spacing={4}>
                <Icon
                  as={health.connected ? CheckCircleIcon : WarningIcon}
                  w={6} h={6}
                  color={health.connected ? 'green.500' : 'red.500'}
                />
                <VStack align="start" spacing={1">
                  <Text fontWeight="bold" fontSize="lg">
                    GitLab Desktop Connection
                  </Text>
                  <HStack>
                    <Text color="gray.600">
                      {health.connected 
                        ? 'Successfully connected to GitLab API' 
                        : health.error || 'Not connected to GitLab'
                      }
                    </Text>
                    {tauriAvailable && (
                      <HStack>
                        <Icon as={DesktopIcon} w={3} h={3} color="blue.500" />
                        <Text fontSize="xs" color="blue.500">
                          Desktop Mode
                        </Text>
                      </HStack>
                    )}
                  </HStack>
                </VStack>
              </HStack>
              
              <HStack spacing={4}>
                <HStack>
                  <Icon as={NotificationIcon} w={4} h={4} color={notificationPermission === 'granted' ? 'green' : 'yellow'} />
                  <Text fontSize="sm">
                    {notificationPermission === 'granted' ? 'Notifications Enabled' : 'Notifications Disabled'}
                  </Text>
                </HStack>
                <Badge
                  colorScheme={health.connected ? 'green' : 'red'}
                  variant="solid"
                  px={4}
                  py={2}
                  fontSize="md"
                >
                  {health.connected ? 'Connected' : 'Disconnected'}
                </Badge>
              </HStack>
            </HStack>
          </CardBody>
        </Card>

        {/* Desktop Ingestion Progress */}
        {ingestionStatus.running && (
          <Card>
            <CardBody>
              <VStack spacing={4}>
                <HStack justify="space-between" w="full">
                  <Text fontWeight="bold">Desktop Data Ingestion Progress</Text>
                  <Text>{Math.round(ingestionStatus.progress)}%</Text>
                </HStack>
                <Progress
                  value={ingestionStatus.progress}
                  colorScheme="orange"
                  size="lg"
                  w="full"
                />
                <Text color="gray.600" fontSize="sm">
                  {ingestionStatus.message}
                </Text>
              </VStack>
            </CardBody>
          </Card>
        )}

        {/* Main Content Tabs */}
        <Tabs value={selectedTab} onChange={(v) => setSelectedTab(v as string)}>
          <TabList>
            <Tab>Overview</Tab>
            <Tab>Projects</Tab>
            <Tab>Pipelines</Tab>
            <Tab>Issues</Tab>
            <Tab>Merge Requests</Tab>
            <Tab>Desktop</Tab>
          </TabList>

          <TabPanels>
            {/* Overview Tab */}
            <TabPanel>
              <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Total Projects</StatLabel>
                      <StatNumber color="orange.500">{projectStats.total}</StatNumber>
                      <StatHelpText>
                        <HStack>
                          <Icon as={FolderIcon} color="green.500" />
                          <Text>{projectStats.active} active</Text>
                        </HStack>
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Total Pipelines</StatLabel>
                      <StatNumber color="blue.500">{allPipelines.length}</StatNumber>
                      <StatHelpText>
                        <HStack>
                          <Icon as={CheckIcon} color="green.500" />
                          <Text>{allPipelines.filter(p => p.status === 'success').length} successful</Text>
                        </HStack>
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Total Issues</StatLabel>
                      <StatNumber color="purple.500">{allIssues.length}</StatNumber>
                      <StatHelpText>
                        <HStack>
                          <Icon as={BugIcon} color="red.500" />
                          <Text>{allIssues.filter(i => i.state === 'opened').length} open</Text>
                        </HStack>
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>

                <Card>
                  <CardBody>
                    <Stat>
                      <StatLabel>Merge Requests</StatLabel>
                      <StatNumber color="teal.500">{mergeRequests.length}</StatNumber>
                      <StatHelpText>
                        <HStack>
                          <Icon as={MergeIcon} color="orange.500" />
                          <Text>{mergeRequests.filter(mr => mr.state === 'opened').length} open</Text>
                        </HStack>
                      </StatHelpText>
                    </Stat>
                  </CardBody>
                </Card>
              </SimpleGrid>

              <VStack spacing={4} mt={6}>
                <HStack justify="space-between">
                  <Text fontWeight="bold" fontSize="lg">Desktop Activity</Text>
                  <HStack>
                    <Icon as={ClockIcon} color="blue.500" />
                    <Text fontSize="sm" color="gray.600">
                      Last sync: {GitLabUtils.getRelativeTime(new Date().toISOString())}
                    </Text>
                  </HStack>
                </HStack>
                <Card>
                  <CardBody>
                    <List spacing={3}>
                      {projects.slice(0, 5).map((project, index) => (
                        <ListItem key={index}>
                          <HStack justify="space-between" w="full">
                            <HStack>
                              <Icon as={CodeIcon} color="orange.500" />
                              <Text fontWeight="medium">{project.name}</Text>
                              <Badge colorScheme={getProjectVisibility(project.visibility)} size="sm">
                                {project.visibility}
                              </Badge>
                            </HStack>
                            <HStack>
                              <Button
                                size="xs"
                                variant="outline"
                                leftIcon={<ExternalLinkIcon />}
                                onClick={() => openProjectInBrowser(project)}
                              >
                                Open
                              </Button>
                              <Text fontSize="sm" color="gray.500">
                                Updated {GitLabUtils.getRelativeTime(project.updated_at)}
                              </Text>
                            </HStack>
                          </HStack>
                        </ListItem>
                      ))}
                    </List>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* Projects Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Text fontWeight="bold" fontSize="lg">
                    GitLab Projects ({projects.length})
                  </Text>
                  <HStack spacing={2}>
                    <IconButton
                      size="sm"
                      aria-label="Filter projects"
                      icon={<FilterIcon />}
                      onClick={onFilterOpen}
                    />
                    <Input
                      placeholder="Search projects..."
                      size="sm"
                      w="200px"
                      onChange={(e) => filterProjects(e.target.value)}
                    />
                    <Select
                      size="sm"
                      w="120px"
                      onChange={(e) => sortProjects(e.target.value, 'desc')}
                    >
                      <option value="updated_at">Last Updated</option>
                      <option value="name">Name</option>
                      <option value="star_count">Stars</option>
                      <option value="forks_count">Forks</option>
                    </Select>
                  </HStack>
                </HStack>

                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {projects.map((project, index) => (
                    <Card
                      key={index}
                      cursor="pointer"
                      onClick={() => handleProjectClick(project)}
                      _hover={{ shadow: 'md' }}
                      bg={bgColor}
                      border="1px"
                      borderColor={borderColor}
                    >
                      <CardBody>
                        <VStack spacing={3} align="start">
                          <HStack justify="space-between" w="full">
                            <HStack>
                              <Icon as={CodeIcon} color="orange.500" />
                              <Text fontWeight="bold" noOfLines={1}>
                                {project.name}
                              </Text>
                            </HStack>
                            <Badge colorScheme={getProjectVisibility(project.visibility)} size="sm">
                              {project.visibility}
                            </Badge>
                          </HStack>
                          
                          {project.description && (
                            <Text color="gray.600" fontSize="sm" noOfLines={2}>
                              {project.description}
                            </Text>
                          )}
                          
                          <HStack justify="space-between" w="full">
                            <HStack spacing={4}>
                              <HStack>
                                <Icon as={StarIcon} w={4} h={4} color="yellow.500" />
                                <Text fontSize="sm">{project.star_count}</Text>
                              </HStack>
                              <HStack>
                                <Icon as={GitlabIcon} w={4} h={4" color="blue.500" />
                                <Text fontSize="sm">{project.forks_count}</Text>
                              </HStack>
                            </HStack>
                            
                            <Badge 
                              colorScheme={project.archived ? 'red' : 'green'} 
                              size="sm"
                            >
                              {project.archived ? 'Archived' : 'Active'}
                            </Badge>
                          </HStack>
                          
                          <Text fontSize="xs" color="gray.500">
                            Updated {GitLabUtils.getRelativeTime(project.updated_at)}
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Pipelines Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontWeight="bold" fontSize="lg">
                  Recent Pipelines ({allPipelines.length})
                </Text>
                
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Pipeline</Th>
                        <Th>Project</Th>
                        <Th>Ref</Th>
                        <Th>Status</Th>
                        <Th>Duration</Th>
                        <Th>Created</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {allPipelines.slice(0, 20).map((pipeline, index) => (
                        <Tr key={index}>
                          <Td>
                            <HStack>
                              <Icon as={ClockIcon} color="orange.500" />
                              <Text fontWeight="medium">#{pipeline.iid}</Text>
                            </HStack>
                          </Td>
                          <Td>{pipeline.project_id}</Td>
                          <Td>
                            <Badge colorScheme="gray" size="sm">
                              {pipeline.ref}
                            </Badge>
                          </Td>
                          <Td>
                            <Badge colorScheme={getPipelineStatus(pipeline.status)} size="sm">
                              {pipeline.status}
                            </Badge>
                          </Td>
                          <Td>
                            {pipeline.duration 
                              ? `${Math.round(pipeline.duration / 60)}m ${pipeline.duration % 60}s`
                              : '-'
                            }
                          </Td>
                          <Td>{GitLabUtils.getRelativeTime(pipeline.created_at)}</Td>
                          <Td>
                            <IconButton
                              size="sm"
                              variant="ghost"
                              aria-label="View pipeline"
                              icon={<ViewIcon />}
                            />
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Issues Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontWeight="bold" fontSize="lg">
                  Issues ({allIssues.length})
                </Text>
                
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                  {allIssues.slice(0, 20).map((issue, index) => (
                    <Card key={index}>
                      <CardBody>
                        <VStack spacing={3} align="start">
                          <HStack justify="space-between" w="full">
                            <Text fontWeight="bold" noOfLines={1}>
                              #{issue.iid} {issue.title}
                            </Text>
                            <Badge 
                              colorScheme={issue.state === 'opened' ? 'orange' : 'gray'} 
                              size="sm"
                            >
                              {issue.state}
                            </Badge>
                          </HStack>
                          
                          <Text color="gray.600" fontSize="sm" noOfLines={2}>
                            {issue.description}
                          </Text>
                          
                          <HStack justify="space-between" w="full">
                            <HStack>
                              {issue.assignees && issue.assignees.length > 0 && (
                                <AvatarGroup size="xs" max={3}>
                                  {issue.assignees.slice(0, 3).map((assignee, idx) => (
                                    <Avatar
                                      key={idx}
                                      name={assignee.name}
                                      src={assignee.avatar_url}
                                      size="xs"
                                    />
                                  ))}
                                </AvatarGroup>
                              )}
                              {issue.labels && issue.labels.length > 0 && (
                                <HStack spacing={1}>
                                  {issue.labels.slice(0, 3).map((label, idx) => (
                                    <Tag key={idx} size="sm" bgColor={`#${label.color}`}>
                                      {label.title}
                                    </Tag>
                                  ))}
                                </HStack>
                              )}
                            </HStack>
                            <Text fontSize="xs" color="gray.500">
                              Created {GitLabUtils.getRelativeTime(issue.created_at)}
                            </Text>
                          </HStack>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Merge Requests Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Text fontWeight="bold" fontSize="lg">
                  Merge Requests ({mergeRequests.length})
                </Text>
                
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>MR</Th>
                        <Th>Title</Th>
                        <Th>Author</Th>
                        <Th>Source → Target</Th>
                        <Th>Status</Th>
                        <Th>Created</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {mergeRequests.slice(0, 20).map((mr, index) => (
                        <Tr key={index}>
                          <Td>
                            <HStack>
                              <Icon as={MergeIcon} color="teal.500" />
                              <Text fontWeight="medium">!{mr.iid}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            <Text noOfLines={1} maxW="300px">
                              {mr.title}
                            </Text>
                          </Td>
                          <Td>
                            <HStack>
                              <Avatar
                                name={mr.author.name}
                                src={mr.author.avatar_url}
                                size="xs"
                              />
                              <Text fontSize="sm">{mr.author.username}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            <HStack>
                              <Text fontSize="sm">{mr.source_branch}</Text>
                              <Text fontSize="xs">→</Text>
                              <Text fontSize="sm">{mr.target_branch}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            <Badge 
                              colorScheme={
                                mr.state === 'opened' ? 'blue' :
                                mr.state === 'merged' ? 'green' :
                                mr.state === 'closed' ? 'gray' : 'yellow'
                              } 
                              size="sm"
                            >
                              {mr.state}
                            </Badge>
                          </Td>
                          <Td>{GitLabUtils.getRelativeTime(mr.created_at)}</Td>
                          <Td>
                            <IconButton
                              size="sm"
                              variant="ghost"
                              aria-label="View merge request"
                              icon={<ViewIcon />}
                            />
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Desktop Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <Card>
                  <CardHeader>
                    <Heading size="lg">Desktop Settings</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <FormControl display="flex" alignItems="center">
                        <FormLabel htmlFor="auto-launch" mb="0">
                          Auto Launch on Startup
                        </FormLabel>
                        <Switch
                          id="auto-launch"
                          isChecked={desktopConfig.autoLaunch}
                          onChange={(e) => updateDesktopConfig({ autoLaunch: e.target.checked })}
                        />
                      </FormControl>

                      <FormControl display="flex" alignItems="center">
                        <FormLabel htmlFor="minimize-tray" mb="0">
                          Minimize to System Tray
                        </FormLabel>
                        <Switch
                          id="minimize-tray"
                          isChecked={desktopConfig.minimizeToTray}
                          onChange={(e) => updateDesktopConfig({ minimizeToTray: e.target.checked })}
                        />
                      </FormControl>

                      <FormControl display="flex" alignItems="center">
                        <FormLabel htmlFor="start-background" mb="0">
                          Start in Background
                        </FormLabel>
                        <Switch
                          id="start-background"
                          isChecked={desktopConfig.startInBackground}
                          onChange={(e) => updateDesktopConfig({ startInBackground: e.target.checked })}
                        />
                      </FormControl>

                      <FormControl display="flex" alignItems="center">
                        <FormLabel htmlFor="desktop-notifications" mb="0">
                          Enable Desktop Notifications
                        </FormLabel>
                        <Switch
                          id="desktop-notifications"
                          isChecked={desktopConfig.notificationsEnabled}
                          onChange={(e) => updateDesktopConfig({ notificationsEnabled: e.target.checked })}
                        />
                      </FormControl>

                      <FormControl display="flex" alignItems="center">
                        <FormLabel htmlFor="sound-enabled" mb="0">
                          Enable Sound Notifications
                        </FormLabel>
                        <Switch
                          id="sound-enabled"
                          isChecked={desktopConfig.soundEnabled}
                          onChange={(e) => updateDesktopConfig({ soundEnabled: e.target.checked })}
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Sync Interval (minutes)</FormLabel>
                        <NumberInput
                          value={desktopConfig.syncInterval / 60000}
                          min={1}
                          max={60}
                          onChange={(value) => updateDesktopConfig({ syncInterval: parseInt(value) * 60000 || 300000 })}
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>

                      <FormControl>
                        <FormLabel>Max Cache Size (MB)</FormLabel>
                        <NumberInput
                          value={desktopConfig.maxCacheSize}
                          min={10}
                          max={1000}
                          onChange={(value) => updateDesktopConfig({ maxCacheSize: parseInt(value) || 100 })}
                        >
                          <NumberInputField />
                        </NumberInput>
                      </FormControl>
                    </VStack>
                  </CardBody>
                </Card>

                <Card>
                  <CardHeader>
                    <Heading size="lg">Desktop Performance</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={4} align="stretch">
                      <HStack justify="space-between">
                        <Text>Cache Size</Text>
                        <Text>{cacheStatus.size} MB</Text>
                      </HStack>
                      <HStack justify="space-between">
                        <Text>Cache Entries</Text>
                        <Text>{cacheStatus.entries}</Text>
                      </HStack>
                      <HStack justify="space-between">
                        <Text>Last Sync</Text>
                        <Text>
                          {cacheStatus.lastSync 
                            ? GitLabUtils.getRelativeTime(cacheStatus.lastSync) 
                            : 'Never'
                          }
                        </Text>
                      </HStack>
                      <HStack justify="space-between">
                        <Text>Desktop Mode</Text>
                        <Badge colorScheme={tauriAvailable ? 'green' : 'yellow'}>
                          {tauriAvailable ? 'Available' : 'Web Mode'}
                        </Badge>
                      </HStack>
                      <HStack justify="space-between">
                        <Text>Notification Permission</Text>
                        <Badge colorScheme={notificationPermission === 'granted' ? 'green' : 'red'}>
                          {notificationPermission}
                        </Badge>
                      </HStack>
                    </VStack>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Desktop Configuration Drawer */}
        <Drawer isOpen={isDesktopOpen} placement="right" onClose={onDesktopClose} size="md">
          <DrawerOverlay />
          <DrawerContent>
            <DrawerCloseButton />
            <DrawerHeader>
              <HStack>
                <Icon as={SettingsIcon} color="orange.500" />
                <Text>GitLab Desktop Configuration</Text>
              </HStack>
            </DrawerHeader>
            <DrawerBody>
              <VStack spacing={6} align="stretch">
                <FormControl>
                  <FormLabel>Sync Frequency</FormLabel>
                  <Select
                    value={config.sync_frequency}
                    onChange={(e) => updateConfig({ sync_frequency: e.target.value as any })}
                  >
                    <option value="realtime">Real-time</option>
                    <option value="hourly">Hourly</option>
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                  </Select>
                </FormControl>

                <FormControl display="flex" alignItems="center">
                  <FormLabel htmlFor="desktop-notifications" mb="0">
                    Desktop Notifications
                  </FormLabel>
                  <Switch
                    id="desktop-notifications"
                    isChecked={config.desktop_notifications}
                    onChange={(e) => updateConfig({ desktop_notifications: e.target.checked })}
                  />
                </FormControl>

                <FormControl display="flex" alignItems="center">
                  <FormLabel htmlFor="offline-mode" mb="0">
                    Offline Mode
                  </FormLabel>
                  <Switch
                    id="offline-mode"
                    isChecked={config.offline_mode}
                    onChange={(e) => updateConfig({ offline_mode: e.target.checked })}
                  />
                </FormControl>

                <HStack spacing={4}>
                  <Button
                    colorScheme="orange"
                    onClick={onDesktopClose}
                  >
                    Save Settings
                  </Button>
                  <Button
                    variant="outline"
                    onClick={clearCache}
                  >
                    Clear Cache
                  </Button>
                </HStack>
              </VStack>
            </DrawerBody>
          </DrawerContent>
        </Drawer>
      </VStack>
    </Box>
  );
};

// Tauri type definitions
declare global {
  interface Window {
    __TAURI__?: {
      shell: {
        open: (url: string) => Promise<void>;
      };
      window: {
        getCurrent: () => {
          hide: () => Promise<void>;
          show: () => Promise<void>;
          close: () => Promise<void>;
        };
      };
      notification: {
        requestPermission: () => Promise<string>;
        isPermissionGranted: () => Promise<boolean>;
        sendNotification: (options: NotificationOptions) => void;
      };
      fs: {
        removeDir: (path: string, options?: { recursive?: boolean }) => Promise<void>;
        exists: (path: string) => Promise<boolean>;
        readDir: (path: string) => Promise<string[]>;
        writeFile: (path: string, contents: string) => Promise<void>;
        readFile: (path: string) => Promise<string>;
      };
      storage: {
        set: (options: { key: string; value: string }) => Promise<void>;
        get: (key: string) => Promise<string | null>;
        remove: (key: string) => Promise<void>;
        clear: () => Promise<void>;
      };
      event: {
        listen: (event: string, handler: (event: any) => void) => Promise<() => void>;
        emit: (event: string, payload?: any) => Promise<void>;
      };
    };
  }
}

export default GitLabDesktopManager;