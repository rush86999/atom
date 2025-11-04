/**
 * Linear Integration Manager Component (Web App)
 * Complete Linear OAuth and API integration following established patterns
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
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface LinearIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface LinearIssue {
  id: string;
  identifier: string;
  title: string;
  description: string;
  status: {
    id: string;
    name: string;
    color: string;
    type: string;
  };
  priority: {
    id: string;
    label: string;
    priority: number;
  };
  assignee: {
    id: string;
    name: string;
    avatarUrl: string;
    displayName: string;
  } | null;
  project: {
    id: string;
    name: string;
    icon: string;
    color: string;
  };
  team: {
    id: string;
    name: string;
    icon: string;
  };
  labels: Array<{
    id: string;
    name: string;
    color: string;
  }>;
  createdAt: string;
  updatedAt: string;
  dueDate: string | null;
  state: 'open' | 'closed' | 'canceled' | 'backlog' | 'triage' | 'started' | 'done';
}

interface LinearProject {
  id: string;
  name: string;
  description: string;
  url: string;
  icon: string;
  color: string;
  team: {
    id: string;
    name: string;
    icon: string;
  };
  state: string;
  progress: number;
  completedIssuesCount: number;
  startedIssuesCount: number;
  unstartedIssuesCount: number;
  backloggedIssuesCount: number;
  canceledIssuesCount: number;
  completedIssuesCountHistory: Array<{
    date: string;
    count: number;
  }>;
  scope: 'private' | 'public';
}

interface LinearTeam {
  id: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  organization: {
    id: string;
    name: string;
    urlKey: string;
  };
  createdAt: string;
  updatedAt: string;
  members: Array<{
    id: string;
    name: string;
    avatarUrl: string;
    displayName: string;
    role: string;
  }>;
  projects: Array<{
    id: string;
    name: string;
    icon: string;
    color: string;
    state: string;
  }>;
  issuesCount: number;
  cyclesCount: number;
}

interface LinearUser {
  id: string;
  name: string;
  displayName: string;
  email: string;
  avatarUrl: string;
  url: string;
  role: string;
  organization: {
    id: string;
    name: string;
    urlKey: string;
  };
  teams: Array<{
    id: string;
    name: string;
    icon: string;
  }>;
  active: boolean;
  lastSeen: string;
}

interface LinearCycle {
  id: string;
  name: string;
  description: string;
  number: number;
  startAt: string;
  endAt: string;
  completedAt: string | null;
  progress: number;
  issues: Array<{
    id: string;
    identifier: string;
    title: string;
    status: {
      id: string;
      name: string;
      color: string;
      type: string;
    };
    priority: {
      id: string;
      label: string;
      priority: number;
    };
    assignee: {
      id: string;
      name: string;
      avatarUrl: string;
      displayName: string;
    } | null;
    createdAt: string;
    updatedAt: string;
  }>;
  team: {
    id: string;
    name: string;
    icon: string;
  };
}

export const LinearManager: React.FC<LinearIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Linear',
    platform: 'linear',
    enabled: true,
    settings: {
      issues: [],
      projects: [],
      teams: [],
      cycles: [],
      contentTypes: ['issues', 'projects', 'teams', 'comments', 'cycles'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), // 90 days ago
        end: new Date(),
      },
      includeCompleted: true,
      includeCanceled: false,
      includeBacklog: true,
      includeComments: true,
      includeCycleHistory: true,
      maxItems: 500,
      realTimeSync: true,
      syncFrequency: 'realtime',
      webhookEvents: ['Issue:Created', 'Issue:Updated', 'Issue:StatusChanged', 'Comment:Created'],
      workspaceId: '',
      workspaceName: '',
      teamId: '',
    }
  });

  const [issues, setIssues] = useState<LinearIssue[]>([]);
  const [projects, setProjects] = useState<LinearProject[]>([]);
  const [teams, setTeams] = useState<LinearTeam[]>([]);
  const [cycles, setCycles] = useState<LinearCycle[]>([]);
  const [users, setUsers] = useState<LinearUser[]>([]);
  const [currentUser, setCurrentUser] = useState<LinearUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showTokenDetails, setShowTokenDetails] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    issuesProcessed: 0,
    projectsProcessed: 0,
    teamsProcessed: 0,
    commentsProcessed: 0,
    cyclesProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('access_token_placeholder');

  // Check Linear service health
  const checkLinearHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations/linear/health');
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
          errors: [data.error || 'Linear service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Linear service health']
      });
    }
  }, []);

  // Load available issues
  const loadIssues = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/linear/issues', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          team_id: config.settings.teamId,
          project_id: config.settings.projects[0],
          include_completed: config.settings.includeCompleted,
          include_canceled: config.settings.includeCanceled,
          include_backlog: config.settings.includeBacklog,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setIssues(data.issues);
      } else {
        setError(data.error || 'Failed to load issues');
      }
    } catch (err) {
      setError('Network error loading issues');
    } finally {
      setLoading(false);
    }
  };

  // Load teams
  const loadTeams = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/linear/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
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

  // Load projects
  const loadProjects = async (teamId?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/linear/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          team_id: teamId,
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

  // Load cycles
  const loadCycles = async (teamId?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/linear/cycles', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          team_id: teamId,
          include_completed: config.settings.includeCycleHistory,
          limit: 20
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setCycles(data.cycles);
      } else {
        setError(data.error || 'Failed to load cycles');
      }
    } catch (err) {
      setError('Network error loading cycles');
    } finally {
      setLoading(false);
    }
  };

  // Load users
  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/linear/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
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
      const response = await fetch('/api/integrations/linear/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setCurrentUser(data.user);
        if (data.user.organization) {
          updateConfig('workspaceId', data.user.organization.id);
          updateConfig('workspaceName', data.user.organization.name);
        }
      }
    } catch (err) {
      console.error('Error loading current user:', err);
    }
  };

  // Start Linear OAuth flow (Web App)
  const startLinearOAuth = async () => {
    try {
      const response = await fetch('/api/auth/linear/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'read',
            'write',
            'issues:read',
            'issues:write',
            'teams:read',
            'projects:read',
            'comments:read',
            'comments:write'
          ],
          redirect_uri: 'http://localhost:3000/oauth/linear/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Open OAuth URL in popup
        const popup = window.open(
          data.authorization_url,
          'linear-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        // Listen for OAuth completion
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkLinearAuthStatus();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Linear OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Linear OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Check Linear auth status
  const checkLinearAuthStatus = async () => {
    try {
      const response = await fetch('/api/auth/linear/status', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (data.connected) {
        toast({
          title: 'Linear Connected',
          description: 'Successfully authenticated with Linear',
          status: 'success',
          duration: 3000,
        });
        
        // Load data
        loadIssues();
        loadTeams();
        loadProjects();
        loadCycles();
        loadUsers();
        loadCurrentUser();
      } else {
        toast({
          title: 'Authentication Required',
          description: 'Please connect to Linear first',
          status: 'warning',
          duration: 3000,
        });
      }
    } catch (err) {
      toast({
        title: 'Status Check Failed',
        description: 'Could not verify Linear connection',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Start Linear data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      issuesProcessed: 0,
      projectsProcessed: 0,
      teamsProcessed: 0,
      commentsProcessed: 0,
      cyclesProcessed: 0,
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
        sourceType: 'linear',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Linear Ingestion Completed',
          description: `Successfully processed ${ingestionResult.issuesProcessed} issues`,
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
        title: 'Linear Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Handle issue selection
  const handleIssueToggle = (issueId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        issues: isChecked
          ? [...prev.settings.issues, issueId]
          : prev.settings.issues.filter(id => id !== issueId)
      }
    }));
  };

  // Handle team selection
  const handleTeamToggle = (teamId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        teams: isChecked
          ? [...prev.settings.teams, teamId]
          : prev.settings.teams.filter(id => id !== teamId)
      }
    }));
    
    // Load projects when team is selected
    if (isChecked) {
      loadProjects(teamId);
      loadCycles(teamId);
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
    checkLinearHealth();
  }, []);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={ViewListIcon} w={6} h={6} color="#5E6AD2" />
            <Heading size="md">Linear Integration</Heading>
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
                checkLinearHealth();
                loadIssues();
                loadTeams();
                loadProjects();
                loadCycles();
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
                    name={currentUser.displayName}
                    src={currentUser.avatarUrl}
                    size="md"
                  />
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">{currentUser.displayName}</Text>
                    <Text fontSize="sm" color="gray.600">{currentUser.email}</Text>
                    <Text fontSize="sm" color="gray.600">Role: {currentUser.role}</Text>
                    {currentUser.organization && (
                      <Text fontSize="sm" color="gray.500">
                        Organization: {currentUser.organization.name}
                      </Text>
                    )}
                    <Badge size="sm" colorScheme="blue">
                      {currentUser.active ? 'Active' : 'Inactive'}
                    </Badge>
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
                  Linear service {health.connected ? 'healthy' : 'unhealthy'}
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
                colorScheme="blue"
                leftIcon={<ViewListIcon />}
                onClick={startLinearOAuth}
                width="full"
                size="lg"
              >
                Connect to Linear
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Click to authenticate with Linear using OAuth 2.0
              </Text>
            </VStack>
          )}

          {/* Content Navigation */}
          {health?.connected && (
            <Tabs isFitted variant="enclosed" w="full">
              <TabList mb={4}>
                {['issues', 'teams', 'projects', 'cycles', 'users'].map((tab) => (
                  <Tab key={tab} textTransform="capitalize">
                    {tab}
                  </Tab>
                ))}
              </TabList>

              <TabPanels>
                {/* Issues Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Issues</FormLabel>
                      <VStack align="start" spacing={3} maxH="400px" overflowY="auto">
                        {issues.map((issue) => (
                          <HStack key={issue.id} justify="space-between" w="full" p={2} border="1px solid" borderColor={borderColor} borderRadius="md">
                            <Checkbox
                              isChecked={config.settings.issues.includes(issue.id)}
                              onChange={(e) => handleIssueToggle(issue.id, e.target.checked)}
                            >
                              <VStack align="start" spacing={1}>
                                <HStack>
                                  <Text fontWeight="medium">{issue.title}</Text>
                                  <Badge size="sm" colorScheme={issue.status.type === 'done' ? 'green' : issue.status.type === 'canceled' ? 'red' : 'blue'}>
                                    {issue.status.name}
                                  </Badge>
                                  <Badge size="sm" colorScheme={issue.priority.priority >= 4 ? 'red' : issue.priority.priority >= 3 ? 'orange' : 'gray'}>
                                    {issue.priority.label}
                                  </Badge>
                                </HStack>
                                <Text fontSize="sm" color="gray.500">
                                  {issue.identifier} • {issue.project.name} • {issue.team.name}
                                </Text>
                                {issue.assignee && (
                                  <HStack>
                                    <Avatar
                                      name={issue.assignee.displayName}
                                      src={issue.assignee.avatarUrl}
                                      size="xs"
                                    />
                                    <Text fontSize="xs">{issue.assignee.displayName}</Text>
                                  </HStack>
                                )}
                                {issue.dueDate && (
                                  <Text fontSize="xs" color="gray.500">
                                    Due: {new Date(issue.dueDate).toLocaleDateString()}
                                  </Text>
                                )}
                              </VStack>
                            </Checkbox>
                            <Button
                              size="sm"
                              variant="outline"
                              leftIcon={<ExternalLinkIcon />}
                              onClick={() => {
                                window.open(issue.url, '_blank');
                              }}
                            >
                              View
                            </Button>
                          </HStack>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Select issues to ingest data from
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
                          <Checkbox
                            key={team.id}
                            isChecked={config.settings.teams.includes(team.id)}
                            onChange={(e) => handleTeamToggle(team.id, e.target.checked)}
                          >
                            <VStack align="start" spacing={1}>
                              <HStack>
                                <Icon as={team.icon || ViewListIcon} w={4} h={4} color={team.color} />
                                <Text fontWeight="medium">{team.name}</Text>
                                <Badge size="sm" colorScheme="blue">
                                  {team.members?.length || 0} members
                                </Badge>
                              </HStack>
                              {team.description && (
                                <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                  {team.description}
                                </Text>
                              )}
                              <Text fontSize="sm" color="gray.500">
                                {team.issuesCount} issues • {team.cyclesCount} cycles
                              </Text>
                            </VStack>
                          </Checkbox>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Select teams to ingest data from
                      </FormHelperText>
                    </FormControl>
                  </VStack>
                </TabPanel>

                {/* Projects Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Projects Preview</FormLabel>
                      <VStack align="start" spacing={2} maxH="400px" overflowY="auto">
                        {projects.slice(0, 20).map((project) => (
                          <Box
                            key={project.id}
                            p={3}
                            border="1px solid"
                            borderColor={borderColor}
                            borderRadius="md"
                            w="full"
                          >
                            <HStack justify="space-between" align="start">
                              <VStack align="start" spacing={2}>
                                <HStack>
                                  <Icon as={project.icon || ViewListIcon} w={4} h={4} color={project.color} />
                                  <Text fontWeight="medium">{project.name}</Text>
                                  <Badge size="sm" colorScheme={project.state === 'published' ? 'green' : 'gray'}>
                                    {project.state}
                                  </Badge>
                                </HStack>
                                {project.description && (
                                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                    {project.description}
                                  </Text>
                                )}
                                <HStack>
                                  <Badge size="sm" colorScheme="blue">
                                    {project.team.name}
                                  </Badge>
                                  <Badge size="sm" colorScheme="gray">
                                    {project.completedIssuesCount} completed
                                  </Badge>
                                  <Badge size="sm" colorScheme="gray">
                                    {project.startedIssuesCount} in progress
                                  </Badge>
                                </HStack>
                              </VStack>
                            </HStack>
                          </Box>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Showing first 20 projects. Full project processing during ingestion.
                      </FormHelperText>
                    </FormControl>
                  </VStack>
                </TabPanel>

                {/* Cycles Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Cycles Preview</FormLabel>
                      <VStack align="start" spacing={2} maxH="400px" overflowY="auto">
                        {cycles.map((cycle) => (
                          <Box
                            key={cycle.id}
                            p={3}
                            border="1px solid"
                            borderColor={borderColor}
                            borderRadius="md"
                            w="full"
                          >
                            <HStack justify="space-between" align="start">
                              <VStack align="start" spacing={2}>
                                <HStack>
                                  <Icon as={CalendarIcon} w={4} h={4} color="blue" />
                                  <Text fontWeight="medium">{cycle.name}</Text>
                                  <Badge size="sm" colorScheme="purple">
                                    Cycle #{cycle.number}
                                  </Badge>
                                </HStack>
                                {cycle.description && (
                                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                    {cycle.description}
                                  </Text>
                                )}
                                <HStack>
                                  <Text fontSize="xs" color="gray.500">
                                    {new Date(cycle.startAt).toLocaleDateString()} - {new Date(cycle.endAt).toLocaleDateString()}
                                  </Text>
                                  <Progress value={cycle.progress} size="sm" w="100px" />
                                </HStack>
                                <HStack>
                                  <Badge size="sm" colorScheme="blue">
                                    {cycle.issues.length} issues
                                  </Badge>
                                  {cycle.completedAt && (
                                    <Badge size="sm" colorScheme="green">
                                      Completed
                                    </Badge>
                                  )}
                                </HStack>
                              </VStack>
                            </HStack>
                          </Box>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Showing all cycles. Full cycle processing during ingestion.
                      </FormHelperText>
                    </FormControl>
                  </VStack>
                </TabPanel>

                {/* Users Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Users</FormLabel>
                      <SimpleGrid columns={responsiveGridCols} spacing={3} maxH="400px" overflowY="auto">
                        {users.map((user) => (
                          <Card key={user.id} variant="outline" size="sm">
                            <CardBody p={3}>
                              <VStack spacing={2} align="center">
                                <Avatar
                                  name={user.displayName}
                                  src={user.avatarUrl}
                                  size="sm"
                                />
                                <VStack spacing={1} align="center">
                                  <Text fontWeight="medium" fontSize="sm">
                                    {user.displayName}
                                  </Text>
                                  <Text fontSize="xs" color="gray.600">
                                    {user.email}
                                  </Text>
                                  <Badge size="sm" colorScheme="blue">
                                    {user.role}
                                  </Badge>
                                  <Badge size="sm" colorScheme={user.active ? 'green' : 'red'}>
                                    {user.active ? 'Active' : 'Inactive'}
                                  </Badge>
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
              {['issues', 'projects', 'teams', 'comments', 'cycles'].map((type) => (
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
              isChecked={config.settings.includeCanceled}
              onChange={(e) => updateConfig('includeCanceled', e.target.checked)}
            >
              Include Canceled
            </Checkbox>
            <Checkbox
              isChecked={config.settings.includeBacklog}
              onChange={(e) => updateConfig('includeBacklog', e.target.checked)}
            >
              Include Backlog
            </Checkbox>
            <Checkbox
              isChecked={config.settings.includeComments}
              onChange={(e) => updateConfig('includeComments', e.target.checked)}
            >
              Include Comments
            </Checkbox>
          </HStack>

          <Button
            variant="outline"
            leftIcon={<SettingsIcon />}
            onClick={() => setShowAdvanced(!showAdvanced)}
            alignSelf="flex-start"
          >
            {showAdvanced ? 'Hide' : 'Show'} Advanced Settings
          </Button>

          {/* Ingestion Progress */}
          {ingestionStatus.running && (
            <Card>
              <CardBody>
                <VStack spacing={3}>
                  <HStack justify="space-between" w="full">
                    <Text>Ingesting Linear data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="blue"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Issues: {ingestionStatus.issuesProcessed} | 
                    Projects: {ingestionStatus.projectsProcessed} | 
                    Teams: {ingestionStatus.teamsProcessed} | 
                    Comments: {ingestionStatus.commentsProcessed} | 
                    Cycles: {ingestionStatus.cyclesProcessed}
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
                window.open('https://linear.app', '_blank');
              }}
            >
              Open Linear
            </Button>

            <Button
              colorScheme="blue"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !health?.connected ||
                (config.settings.issues.length === 0 && config.settings.teams.length === 0) ||
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

export default LinearManager;