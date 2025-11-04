/**
 * Asana Integration Manager Component (Web App)
 * Complete Asana OAuth and API integration following established patterns
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Stack,
  Badge,
  Progress,
  Alert,
  AlertIcon,
  Divider,
  Flex,
  Icon,
  Tooltip,
  useToast,
  Card,
  CardBody,
  CardHeader,
  FormControl,
  FormLabel,
  Input,
  FormHelperText,
  Checkbox,
  Select,
  Switch,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  useColorModeValue,
  SimpleGrid,
  Avatar,
  useBreakpointValue,
  useTab,
  TabList,
  TabPanels,
  TabPanel,
  Tabs,
  Tag,
  TagLabel,
  TagLeftIcon,
  Code,
  useClipboard,
  useAccordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
} from '@chakra-ui/react';
import {
  ViewIcon,
  EditIcon,
  RepeatIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  AddIcon,
  SettingsIcon,
  InfoIcon,
  ViewListIcon,
  ArchiveIcon,
  UserIcon,
  CopyIcon,
  DesktopIcon,
  CalendarIcon,
  ChevronRightIcon,
  ProjectIcon,
  TaskIcon,
  SectionIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface AsanaIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface AsanaTask {
  gid: string;
  name: string;
  notes: string;
  completed: boolean;
  assignee: {
    gid: string;
    name: string;
    email: string;
    avatar_url_128x128: string;
  } | null;
  projects: Array<{
    gid: string;
    name: string;
    color: string;
  }>;
  parent: {
    gid: string;
    name: string;
  } | null;
  created_at: string;
  modified_at: string;
  due_on: string | null;
  due_at: string | null;
  start_at: string | null;
  tags: Array<{
    gid: string;
    name: string;
    color: string;
  }>;
  custom_fields: Array<{
    gid: string;
    name: string;
    type: string;
    enum_value: {
      gid: string;
      name: string;
      color: string;
    } | null;
  }>;
}

interface AsanaProject {
  gid: string;
  name: string;
  description: string;
  color: string;
  public: boolean;
  owner: {
    gid: string;
    name: string;
  } | null;
  team: {
    gid: string;
    name: string;
  } | null;
  created_at: string;
  modified_at: string;
  html_notes: string | null;
  archived: boolean;
  workspace: {
    gid: string;
    name: string;
  };
  members: Array<{
    gid: string;
    name: string;
    avatar_url_128x128: string;
  }>;
  followers: Array<{
    gid: string;
    name: string;
    avatar_url_128x128: string;
  }>;
  current_status: {
    gid: string;
    title: string;
    color: string;
    author: {
      gid: string;
      name: string;
    };
    modified_at: string;
  } | null;
  custom_field_settings: Array<{
    gid: string;
    name: string;
    type: string;
    project: {
      gid: string;
    };
  }>;
}

interface AsanaSection {
  gid: string;
  name: string;
  project: {
    gid: string;
    name: string;
    color: string;
  };
  created_at: string;
  tasks: Array<{
    gid: string;
    name: string;
    completed: boolean;
  }>;
}

interface AsanaUser {
  gid: string;
  name: string;
  email: string;
  avatar_url_128x128: string;
  workspaces: Array<{
    gid: string;
    name: string;
  }>;
}

interface AsanaTeam {
  gid: string;
  name: string;
  description: string;
  organization: {
    gid: string;
    name: string;
    permalink_url: string;
  } | null;
  members: Array<{
    gid: string;
    name: string;
    email: string;
    avatar_url_128x128: string;
  }>;
  projects: Array<{
    gid: string;
    name: string;
    color: string;
  }>;
}

export const AsanaManager: React.FC<AsanaIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Asana',
    platform: 'asana',
    enabled: true,
    settings: {
      tasks: [],
      projects: [],
      sections: [],
      teams: [],
      contentTypes: ['tasks', 'projects', 'sections', 'teams', 'subtasks'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), // 90 days ago
        end: new Date(),
      },
      includeCompleted: true,
      includeArchived: false,
      includeSubtasks: true,
      includeCustomFields: true,
      maxItems: 500,
      realTimeSync: true,
      syncFrequency: 'realtime',
      webhookEvents: ['task:added', 'task:changed', 'task:removed', 'project:changed', 'story:added'],
      workspaceId: '',
      workspaceName: '',
      teamId: '',
    }
  });

  const [tasks, setTasks] = useState<AsanaTask[]>([]);
  const [projects, setProjects] = useState<AsanaProject[]>([]);
  const [sections, setSections] = useState<AsanaSection[]>([]);
  const [teams, setTeams] = useState<AsanaTeam[]>([]);
  const [users, setUsers] = useState<AsanaUser[]>([]);
  const [currentUser, setCurrentUser] = useState<AsanaUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showTokenDetails, setShowTokenDetails] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    tasksProcessed: 0,
    projectsProcessed: 0,
    sectionsProcessed: 0,
    teamsProcessed: 0,
    commentsProcessed: 0,
    subtasksProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('access_token_placeholder');

  // Check Asana service health
  const checkAsanaHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations/asana/health');
      const data = await response.json();
      
      if (data.status === 'healthy') {
        setHealth({
          connected: true,
          lastSync: new Date().toISOString(),
          errors: []
        });
      } else {
        setHealth({
          connected: false,
          lastSync: new Date().toISOString(),
          errors: [data.error || 'Asana service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Asana service health']
      });
    }
  }, []);

  // Load available tasks
  const loadTasks = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/asana/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: config.settings.workspaceId,
          project_id: config.settings.projects[0],
          include_completed: config.settings.includeCompleted,
          include_archived: config.settings.includeArchived,
          include_subtasks: config.settings.includeSubtasks,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setTasks(data.tasks);
      } else {
        setError(data.error || 'Failed to load tasks');
      }
    } catch (err) {
      setError('Network error loading tasks');
    } finally {
      setLoading(false);
    }
  };

  // Load projects
  const loadProjects = async (workspaceId?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/asana/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId,
          team_id: config.settings.teamId,
          include_archived: config.settings.includeArchived,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setProjects(data.projects);
      } else {
        setError(data.error || 'Failed to load projects');
      }
    } catch (err) {
      setError('Network error loading projects');
    } finally {
      setLoading(false);
    }
  };

  // Load sections
  const loadSections = async (projectId?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/asana/sections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          project_id: projectId,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setSections(data.sections);
      } else {
        setError(data.error || 'Failed to load sections');
      }
    } catch (err) {
      setError('Network error loading sections');
    } finally {
      setLoading(false);
    }
  };

  // Load teams
  const loadTeams = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/asana/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: config.settings.workspaceId,
          limit: 20
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setTeams(data.teams);
      } else {
        setError(data.error || 'Failed to load teams');
      }
    } catch (err) {
      setError('Network error loading teams');
    } finally {
      setLoading(false);
    }
  };

  // Load users
  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/asana/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: config.settings.workspaceId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setUsers(data.users);
      } else {
        setError(data.error || 'Failed to load users');
      }
    } catch (err) {
      setError('Network error loading users');
    } finally {
      setLoading(false);
    }
  };

  // Load current user
  const loadCurrentUser = async () => {
    try {
      const response = await fetch('/api/integrations/asana/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setCurrentUser(data.user);
        if (data.user.workspaces && data.user.workspaces.length > 0) {
          updateConfig('workspaceId', data.user.workspaces[0].gid);
          updateConfig('workspaceName', data.user.workspaces[0].name);
        }
      }
    } catch (err) {
      console.error('Error loading current user:', err);
    }
  };

  // Start Asana OAuth flow (Web App)
  const startAsanaOAuth = async () => {
    try {
      const response = await fetch('/api/auth/asana/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'default',
            'tasks:read',
            'tasks:write',
            'projects:read',
            'projects:write',
            'stories:read',
            'stories:write',
            'teams:read',
            'users:read',
            'webhooks:read',
            'webhooks:write'
          ],
          redirect_uri: 'http://localhost:3000/oauth/asana/callback',
          state: `user-${userId}-${time.time()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Open OAuth URL in popup
        const popup = window.open(
          data.authorization_url,
          'asana-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        // Listen for OAuth completion
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkAsanaAuthStatus();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Asana OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Asana OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Check Asana auth status
  const checkAsanaAuthStatus = async () => {
    try {
      const response = await fetch('/api/auth/asana/status', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (data.connected) {
        toast({
          title: 'Asana Connected',
          description: 'Successfully authenticated with Asana',
          status: 'success',
          duration: 3000,
        });
        
        // Load data
        loadTasks();
        loadProjects();
        loadSections();
        loadTeams();
        loadUsers();
        loadCurrentUser();
      } else {
        toast({
          title: 'Authentication Required',
          description: 'Please connect to Asana first',
          status: 'warning',
          duration: 3000,
        });
      }
    } catch (err) {
      toast({
        title: 'Status Check Failed',
        description: 'Could not verify Asana connection',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Start Asana data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      tasksProcessed: 0,
      projectsProcessed: 0,
      sectionsProcessed: 0,
      teamsProcessed: 0,
      commentsProcessed: 0,
      subtasksProcessed: 0,
      errors: []
    }));

    try {
      // Configure data source in ATOM pipeline
      const dataSourceConfig = {
        ...config,
        health: health || { connected: false, lastSync: '', errors: [] }
      };

      if (onConfigurationChange) {
        onConfigurationChange(dataSourceConfig);
      }

      // Start ingestion through ATOM pipeline
      const ingestionResult = await atomIngestionPipeline.startIngestion({
        sourceType: 'asana',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Asana Ingestion Completed',
          description: `Successfully processed ${ingestionResult.tasksProcessed} tasks`,
          status: 'success',
          duration: 5000,
        });

        if (onIngestionComplete) {
          onIngestionComplete(ingestionResult);
        }
      } else {
        throw new Error(ingestionResult.error || 'Ingestion failed');
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      
      setIngestionStatus(prev => ({
        ...prev,
        running: false,
        errors: [...prev.errors, error.message]
      }));

      toast({
        title: 'Asana Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Handle task selection
  const handleTaskToggle = (taskId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        tasks: isChecked
          ? [...prev.settings.tasks, taskId]
          : prev.settings.tasks.filter(id => id !== taskId)
      }
    }));
  };

  // Handle project selection
  const handleProjectToggle = (projectId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        projects: isChecked
          ? [...prev.settings.projects, projectId]
          : prev.settings.projects.filter(id => id !== projectId)
      }
    }));
    
    // Load sections when project is selected
    if (isChecked) {
      loadSections(projectId);
    }
  };

  // Update configuration
  const updateConfig = (path: string, value: any) => {
    setConfig(prev => {
      const newConfig = { ...prev };
      const keys = path.split('.');
      let current: any = newConfig.settings;
      
      for (let i = 0; i < keys.length - 1; i++) {
        current[keys[i]] = current[keys[i]] || {};
        current = current[keys[i]];
      }
      
      current[keys[keys.length - 1]] = value;
      
      if (onConfigurationChange) {
        onConfigurationChange(newConfig);
      }
      
      return newConfig;
    });
  };

  useEffect(() => {
    checkAsanaHealth();
  }, []);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={TaskIcon} w={6} h={6} color="#27334D" />
            <Heading size="md">Asana Integration</Heading>
          </HStack>
          <HStack>
            <Badge
              colorScheme={health?.connected ? 'green' : 'red'}
              display="flex"
              alignItems="center"
            >
              <Icon as={health?.connected ? CheckCircleIcon : WarningIcon} mr={1} />
              {health?.connected ? 'Connected' : 'Disconnected'}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<RepeatIcon />}
              onClick={() => {
                checkAsanaHealth();
                loadTasks();
                loadProjects();
                loadSections();
                loadTeams();
                loadUsers();
                loadCurrentUser();
              }}
              isLoading={loading}
            >
              Refresh
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={6} align="stretch">
          {/* Current User Display */}
          {currentUser && (
            <Card bg={bgColor} border="1px" borderColor={borderColor}>
              <CardBody>
                <HStack spacing={4}>
                  <Avatar
                    name={currentUser.name}
                    src={currentUser.avatar_url_128x128}
                    size="md"
                  />
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">{currentUser.name}</Text>
                    <Text fontSize="sm" color="gray.600">{currentUser.email}</Text>
                    {currentUser.workspaces && currentUser.workspaces.length > 0 && (
                      <Text fontSize="sm" color="gray.500">
                        Workspace: {currentUser.workspaces[0].name}
                      </Text>
                    )}
                  </VStack>
                </HStack>
              </CardBody>
            </Card>
          )}

          {/* Health Status */}
          {health && (
            <Alert status={health.connected ? 'success' : 'warning'}>
              <AlertIcon />
              <Box>
                <Text fontWeight="bold">
                  Asana service {health.connected ? 'healthy' : 'unhealthy'}
                </Text>
                {health.errors.length > 0 && (
                  <Text fontSize="sm" color="red.500">
                    {health.errors.join(', ')}
                  </Text>
                )}
              </Box>
            </Alert>
          )}

          {/* Error Display */}
          {error && (
            <Alert status="error">
              <AlertIcon />
              <Text>{error}</Text>
            </Alert>
          )}

          {/* Authentication */}
          {!health?.connected && (
            <VStack>
              <Button
                colorScheme="orange"
                leftIcon={<TaskIcon />}
                onClick={startAsanaOAuth}
                width="full"
                size="lg"
              >
                Connect to Asana
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Click to authenticate with Asana using OAuth 2.0
              </Text>
            </VStack>
          )}

          {/* Content Navigation */}
          {health?.connected && (
            <Tabs isFitted variant="enclosed" w="full">
              <TabList mb={4}>
                {['tasks', 'projects', 'sections', 'teams', 'users'].map((tab) => (
                  <Tab key={tab} textTransform="capitalize">
                    {tab}
                  </Tab>
                ))}
              </TabList>

              <TabPanels>
                {/* Tasks Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Tasks</FormLabel>
                      <VStack align="start" spacing={3} maxH="400px" overflowY="auto">
                        {tasks.map((task) => (
                          <HStack key={task.gid} justify="space-between" w="full" p={2} border="1px solid" borderColor={borderColor} borderRadius="md">
                            <Checkbox
                              isChecked={config.settings.tasks.includes(task.gid)}
                              onChange={(e) => handleTaskToggle(task.gid, e.target.checked)}
                            >
                              <VStack align="start" spacing={1}>
                                <HStack>
                                  <Text fontWeight="medium">{task.name}</Text>
                                  {task.completed && (
                                    <Badge size="sm" colorScheme="green">
                                      Completed
                                    </Badge>
                                  )}
                                </HStack>
                                <Text fontSize="sm" color="gray.500" noOfLines={2}>
                                  {task.notes || 'No description'}
                                </Text>
                                {task.projects && task.projects.length > 0 && (
                                  <HStack>
                                    {task.projects.slice(0, 3).map((project) => (
                                      <Badge key={project.gid} size="sm" colorScheme="blue">
                                        {project.name}
                                      </Badge>
                                    ))}
                                  </HStack>
                                )}
                                <HStack>
                                  {task.assignee && (
                                    <HStack>
                                      <Avatar
                                        name={task.assignee.name}
                                        src={task.assignee.avatar_url_128x128}
                                        size="xs"
                                      />
                                      <Text fontSize="xs">{task.assignee.name}</Text>
                                    </HStack>
                                  )}
                                  {(task.due_on || task.due_at) && (
                                    <Text fontSize="xs" color="gray.500">
                                      Due: {task.due_on || task.due_at}
                                    </Text>
                                  )}
                                </HStack>
                              </VStack>
                            </Checkbox>
                            <Button
                              size="sm"
                              variant="outline"
                              leftIcon={<ExternalLinkIcon />}
                              onClick={() => {
                                window.open(`https://app.asana.com/0/${task.projects[0]?.gid}/${task.gid}`, '_blank');
                              }}
                            >
                              View
                            </Button>
                          </HStack>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Select tasks to ingest data from
                      </FormHelperText>
                    </FormControl>
                  </VStack>
                </TabPanel>

                {/* Projects Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Projects</FormLabel>
                      <VStack align="start" spacing={2} maxH="400px" overflowY="auto">
                        {projects.map((project) => (
                          <Checkbox
                            key={project.gid}
                            isChecked={config.settings.projects.includes(project.gid)}
                            onChange={(e) => handleProjectToggle(project.gid, e.target.checked)}
                          >
                            <VStack align="start" spacing={1}>
                              <HStack>
                                <Icon as={ProjectIcon} w={4} h={4} color={project.color} />
                                <Text fontWeight="medium">{project.name}</Text>
                                <Badge size="sm" colorScheme={project.archived ? 'red' : 'green'}>
                                  {project.archived ? 'Archived' : 'Active'}
                                </Badge>
                                <Badge size="sm" colorScheme={project.public ? 'blue' : 'gray'}>
                                  {project.public ? 'Public' : 'Private'}
                                </Badge>
                              </HStack>
                              {project.description && (
                                <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                  {project.description}
                                </Text>
                              )}
                              <HStack>
                                {project.team && (
                                  <Badge size="sm" colorScheme="purple">
                                    {project.team.name}
                                  </Badge>
                                )}
                                <Badge size="sm" colorScheme="gray">
                                  {project.members.length} members
                                </Badge>
                                <Text fontSize="sm" color="gray.500">
                                  Workspace: {project.workspace.name}
                                </Text>
                              </HStack>
                            </VStack>
                          </Checkbox>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Select projects to ingest data from
                      </FormHelperText>
                    </FormControl>
                  </VStack>
                </TabPanel>

                {/* Sections Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Sections Preview</FormLabel>
                      <VStack align="start" spacing={2} maxH="400px" overflowY="auto">
                        {sections.map((section) => (
                          <Box
                            key={section.gid}
                            p={3}
                            border="1px solid"
                            borderColor={borderColor}
                            borderRadius="md"
                            w="full"
                          >
                            <HStack justify="space-between" align="start">
                              <VStack align="start" spacing={2}>
                                <HStack>
                                  <Icon as={SectionIcon} w={4} h={4} color="gray" />
                                  <Text fontWeight="medium">{section.name}</Text>
                                </HStack>
                                <HStack>
                                  <Badge size="sm" colorScheme="blue">
                                    {section.project.name}
                                  </Badge>
                                  <Badge size="sm" colorScheme="gray">
                                    {section.tasks.length} tasks
                                  </Badge>
                                </HStack>
                              </VStack>
                            </HStack>
                          </Box>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Showing all sections. Full section processing during ingestion.
                      </FormHelperText>
                    </FormControl>
                  </VStack>
                </TabPanel>

                {/* Teams Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Teams</FormLabel>
                      <VStack align="start" spacing={2} maxH="400px" overflowY="auto">
                        {teams.map((team) => (
                          <Box
                            key={team.gid}
                            p={3}
                            border="1px solid"
                            borderColor={borderColor}
                            borderRadius="md"
                            w="full"
                          >
                            <HStack justify="space-between" align="start">
                              <VStack align="start" spacing={2}>
                                <HStack>
                                  <Icon as={ProjectIcon} w={4} h={4} color="purple" />
                                  <Text fontWeight="medium">{team.name}</Text>
                                </HStack>
                                {team.description && (
                                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                    {team.description}
                                  </Text>
                                )}
                                <HStack>
                                  <Badge size="sm" colorScheme="blue">
                                    {team.members.length} members
                                  </Badge>
                                  <Badge size="sm" colorScheme="green">
                                    {team.projects.length} projects
                                  </Badge>
                                </HStack>
                              </VStack>
                            </HStack>
                          </Box>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Teams provide organizational structure for projects and members
                      </FormHelperText>
                    </FormControl>
                  </VStack>
                </TabPanel>

                {/* Users Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Workspace Users</FormLabel>
                      <SimpleGrid columns={responsiveGridCols} spacing={3} maxH="400px" overflowY="auto">
                        {users.map((user) => (
                          <Card key={user.gid} variant="outline" size="sm">
                            <CardBody p={3}>
                              <VStack spacing={2} align="center">
                                <Avatar
                                  name={user.name}
                                  src={user.avatar_url_128x128}
                                  size="sm"
                                />
                                <VStack spacing={1} align="center">
                                  <Text fontWeight="medium" fontSize="sm">
                                    {user.name}
                                  </Text>
                                  <Text fontSize="xs" color="gray.600">
                                    {user.email}
                                  </Text>
                                </VStack>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))}
                      </SimpleGrid>
                    </FormControl>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          )}

          <Divider />

          {/* Content Types */}
          <FormControl>
            <FormLabel>Content Types</FormLabel>
            <Stack direction="row" spacing={4} wrap="wrap">
              {['tasks', 'projects', 'sections', 'teams', 'subtasks'].map((type) => (
                <Checkbox
                  key={type}
                  isChecked={config.settings.contentTypes.includes(type)}
                  onChange={(e) => {
                    const newTypes = e.target.checked
                      ? [...config.settings.contentTypes, type]
                      : config.settings.contentTypes.filter(t => t !== type);
                    updateConfig('contentTypes', newTypes);
                  }}
                >
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </Checkbox>
              ))}
            </Stack>
          </FormControl>

          {/* Date Range */}
          <FormControl>
            <FormLabel>Date Range</FormLabel>
            <HStack>
              <Input
                type="date"
                value={config.settings.dateRange.start.toISOString().split('T')[0]}
                onChange={(e) => updateConfig('dateRange.start', new Date(e.target.value))}
              />
              <Text>to</Text>
              <Input
                type="date"
                value={config.settings.dateRange.end.toISOString().split('T')[0]}
                onChange={(e) => updateConfig('dateRange.end', new Date(e.target.value))}
              />
            </HStack>
          </FormControl>

          {/* Advanced Settings */}
          <HStack>
            <Checkbox
              isChecked={config.settings.includeCompleted}
              onChange={(e) => updateConfig('includeCompleted', e.target.checked)}
            >
              Include Completed
            </Checkbox>
            <Checkbox
              isChecked={config.settings.includeArchived}
              onChange={(e) => updateConfig('includeArchived', e.target.checked)}
            >
              Include Archived
            </Checkbox>
            <Checkbox
              isChecked={config.settings.includeSubtasks}
              onChange={(e) => updateConfig('includeSubtasks', e.target.checked)}
            >
              Include Subtasks
            </Checkbox>
            <Checkbox
              isChecked={config.settings.includeCustomFields}
              onChange={(e) => updateConfig('includeCustomFields', e.target.checked)}
            >
              Include Custom Fields
            </Checkbox>
          </HStack>

          {/* Ingestion Progress */}
          {ingestionStatus.running && (
            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" w="full">
                    <Text>Ingesting Asana data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="orange"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Tasks: {ingestionStatus.tasksProcessed} | 
                    Projects: {ingestionStatus.projectsProcessed} | 
                    Sections: {ingestionStatus.sectionsProcessed} | 
                    Teams: {ingestionStatus.teamsProcessed} | 
                    Comments: {ingestionStatus.commentsProcessed} | 
                    Subtasks: {ingestionStatus.subtasksProcessed}
                  </Text>
                </VStack>
              </CardBody>
            </Card>
          )}

          {/* Action Buttons */}
          <HStack justify="space-between" w="full">
            <Button
              variant="outline"
              leftIcon={<ExternalLinkIcon />}
              onClick={() => {
                window.open('https://app.asana.com', '_blank');
              }}
            >
              Open Asana
            </Button>

            <Button
              colorScheme="orange"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !health?.connected ||
                (config.settings.tasks.length === 0 && config.settings.projects.length === 0) ||
                ingestionStatus.running
              }
              isLoading={ingestionStatus.running}
            >
              {ingestionStatus.running ? 'Ingesting...' : 'Start Ingestion'}
            </Button>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );
};

export default AsanaManager;