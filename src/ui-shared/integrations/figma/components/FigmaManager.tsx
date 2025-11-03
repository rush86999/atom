/**
 * Figma Integration Manager Component (Web App)
 * Complete Figma OAuth and API integration following established patterns
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
  Image,
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
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface FigmaIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface FigmaFile {
  key: string;
  thumbnail_url: string;
  name: string;
  content_readonly?: boolean;
  editor_type: string;
  last_modified: string;
  workspace_id: string;
  workspace_name: string;
  file_id: string;
  branch_id: string;
  thumbnail_url_default?: string;
}

interface FigmaTeam {
  id: string;
  name: string;
  description: string;
  profile_picture_url: string;
  users: Array<{
    id: string;
    name: string;
    username: string;
    profile_picture_url: string;
    role: string;
  }>;
}

interface FigmaUser {
  id: string;
  name: string;
  username: string;
  email?: string;
  profile_picture_url: string;
  department?: string;
  title?: string;
  organization_id?: string;
  role?: string;
  can_edit: boolean;
  has_guests: boolean;
  is_active: boolean;
}

interface FigmaProject {
  id: string;
  name: string;
  description?: string;
  team_id: string;
  team_name: string;
  files: Array<{
    key: string;
    name: string;
    thumbnail_url: string;
    last_modified: string;
  }>;
}

interface FigmaComponent {
  key: string;
  file_key: string;
  node_id: string;
  name: string;
  description?: string;
  component_type: string;
  thumbnail_url?: string;
  created_at?: string;
  modified_at?: string;
  creator_id?: string;
}

export const FigmaManager: React.FC<FigmaIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Figma',
    platform: 'figma',
    enabled: true,
    settings: {
      files: [],
      teams: [],
      projects: [],
      components: [],
      contentTypes: ['files', 'components', 'teams', 'users', 'comments', 'versions'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), // 90 days ago
        end: new Date(),
      },
      includeArchived: false,
      includeDeleted: false,
      includeComments: true,
      includeVersions: true,
      includeThumbnailData: true,
      maxItems: 500,
      realTimeSync: true,
      syncFrequency: 'realtime',
      webhookEvents: ['file_comment', 'file_update', 'file_version', 'library_publish'],
      workspaceId: '',
      workspaceName: '',
      teamId: '',
    }
  });

  const [files, setFiles] = useState<FigmaFile[]>([]);
  const [teams, setTeams] = useState<FigmaTeam[]>([]);
  const [projects, setProjects] = useState<FigmaProject[]>([]);
  const [components, setComponents] = useState<FigmaComponent[]>([]);
  const [users, setUsers] = useState<FigmaUser[]>([]);
  const [currentUser, setCurrentUser] = useState<FigmaUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showTokenDetails, setShowTokenDetails] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    filesProcessed: 0,
    componentsProcessed: 0,
    teamsProcessed: 0,
    usersProcessed: 0,
    commentsProcessed: 0,
    versionsProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('access_token_placeholder');

  // Check Figma service health
  const checkFigmaHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations/figma/health');
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
          errors: [data.error || 'Figma service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Figma service health']
      });
    }
  }, []);

  // Load available files
  const loadFiles = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/figma/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          team_id: config.settings.teamId,
          include_archived: config.settings.includeArchived,
          include_deleted: config.settings.includeDeleted,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setFiles(data.files);
      } else {
        setError(data.error || 'Failed to load files');
      }
    } catch (err) {
      setError('Network error loading files');
    } finally {
      setLoading(false);
    }
  };

  // Load teams
  const loadTeams = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/figma/teams', {
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
      const response = await fetch('/api/integrations/figma/projects', {
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

  // Load components
  const loadComponents = async (fileId?: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/figma/components', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          file_key: fileId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setComponents(data.components);
      } else {
        setError(data.error || 'Failed to load components');
      }
    } catch (err) {
      setError('Network error loading components');
    } finally {
      setLoading(false);
    }
  };

  // Load users
  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/figma/users', {
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
      const response = await fetch('/api/integrations/figma/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setCurrentUser(data.user);
        if (data.user.organization_id) {
          updateConfig('workspaceId', data.user.organization_id);
          updateConfig('workspaceName', data.user.organization_id || 'Personal Workspace');
        }
      }
    } catch (err) {
      console.error('Error loading current user:', err);
    }
  };

  // Start Figma OAuth flow (Web App)
  const startFigmaOAuth = async () => {
    try {
      const response = await fetch('/api/auth/figma/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'file_read',
            'file_write',
            'team_read',
            'team_write',
            'user_read',
            'user_write',
            'comments_read',
            'comments_write'
          ],
          redirect_uri: 'http://localhost:3000/oauth/figma/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Open OAuth URL in popup
        const popup = window.open(
          data.authorization_url,
          'figma-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        // Listen for OAuth completion
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkFigmaAuthStatus();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Figma OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Figma OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Check Figma auth status
  const checkFigmaAuthStatus = async () => {
    try {
      const response = await fetch('/api/auth/figma/status', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (data.connected) {
        toast({
          title: 'Figma Connected',
          description: 'Successfully authenticated with Figma',
          status: 'success',
          duration: 3000,
        });
        
        // Load data
        loadFiles();
        loadTeams();
        loadProjects();
        loadUsers();
        loadCurrentUser();
      } else {
        toast({
          title: 'Authentication Required',
          description: 'Please connect to Figma first',
          status: 'warning',
          duration: 3000,
        });
      }
    } catch (err) {
      toast({
        title: 'Status Check Failed',
        description: 'Could not verify Figma connection',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Start Figma data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      filesProcessed: 0,
      componentsProcessed: 0,
      teamsProcessed: 0,
      usersProcessed: 0,
      commentsProcessed: 0,
      versionsProcessed: 0,
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
        sourceType: 'figma',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Figma Ingestion Completed',
          description: `Successfully processed ${ingestionResult.filesProcessed} files`,
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
        title: 'Figma Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Handle file selection
  const handleFileToggle = (fileId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        files: isChecked
          ? [...prev.settings.files, fileId]
          : prev.settings.files.filter(id => id !== fileId)
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
    checkFigmaHealth();
  }, []);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={ViewListIcon} w={6} h={6} color="#F24E1E" />
            <Heading size="md">Figma Integration</Heading>
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
                checkFigmaHealth();
                loadFiles();
                loadTeams();
                loadProjects();
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
                    src={currentUser.profile_picture_url}
                    size="md"
                  />
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">{currentUser.name}</Text>
                    <Text fontSize="sm" color="gray.600">@{currentUser.username}</Text>
                    {currentUser.email && (
                      <Text fontSize="sm" color="gray.600">{currentUser.email}</Text>
                    )}
                    {currentUser.title && (
                      <Text fontSize="sm" color="gray.600">{currentUser.title}</Text>
                    )}
                    {currentUser.department && (
                      <Text fontSize="sm" color="gray.600">{currentUser.department}</Text>
                    )}
                    <Badge size="sm" colorScheme="blue">
                      {currentUser.role || 'member'}
                    </Badge>
                    {config.settings.workspaceName && (
                      <Text fontSize="sm" color="gray.500">
                        Workspace: {config.settings.workspaceName}
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
                  Figma service {health.connected ? 'healthy' : 'unhealthy'}
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
                colorScheme="purple"
                leftIcon={<ViewListIcon />}
                onClick={startFigmaOAuth}
                width="full"
                size="lg"
              >
                Connect to Figma
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Click to authenticate with Figma using OAuth 2.0
              </Text>
            </VStack>
          )}

          {/* Content Navigation */}
          {health?.connected && (
            <Tabs isFitted variant="enclosed" w="full">
              <TabList mb={4}>
                {['files', 'teams', 'projects', 'components', 'users'].map((tab) => (
                  <Tab key={tab} textTransform="capitalize">
                    {tab}
                  </Tab>
                ))}
              </TabList>

              <TabPanels>
                {/* Files Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Files</FormLabel>
                      <VStack align="start" spacing={3} maxH="400px" overflowY="auto">
                        {files.map((file) => (
                          <HStack key={file.file_id} justify="space-between" w="full" p={2} border="1px solid" borderColor={borderColor} borderRadius="md">
                            <Checkbox
                              isChecked={config.settings.files.includes(file.file_id)}
                              onChange={(e) => handleFileToggle(file.file_id, e.target.checked)}
                            >
                              <VStack align="start" spacing={1}>
                                <HStack>
                                  <Image
                                    src={file.thumbnail_url}
                                    alt={file.name}
                                    boxSize="32px"
                                    borderRadius="md"
                                    objectFit="cover"
                                  />
                                  <Text fontWeight="medium">{file.name}</Text>
                                  <Badge size="sm" colorScheme="purple">
                                    {file.editor_type || 'figma'}
                                  </Badge>
                                  {file.content_readonly && (
                                    <Badge size="sm" colorScheme="gray">Read Only</Badge>
                                  )}
                                </HStack>
                                <Text fontSize="sm" color="gray.500">
                                  Team: {file.workspace_name} • Modified: {new Date(file.last_modified).toLocaleDateString()}
                                </Text>
                              </VStack>
                            </Checkbox>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                loadComponents(file.file_id);
                              }}
                              leftIcon={<ViewIcon />}
                            >
                              View
                            </Button>
                          </HStack>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Select files to ingest data from
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
                                <Avatar
                                  name={team.name}
                                  src={team.profile_picture_url}
                                  size="sm"
                                />
                                <Text fontWeight="medium">{team.name}</Text>
                                <Badge size="sm" colorScheme="purple">
                                  {team.users?.length || 0} members
                                </Badge>
                              </HStack>
                              {team.description && (
                                <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                  {team.description}
                                </Text>
                              )}
                              <Text fontSize="sm" color="gray.500">
                                Team ID: {team.id}
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
                                <Text fontWeight="medium">{project.name}</Text>
                                {project.description && (
                                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                    {project.description}
                                  </Text>
                                )}
                                <HStack>
                                  <Badge size="sm" colorScheme="purple">
                                    {project.team_name}
                                  </Badge>
                                  <Badge size="sm" colorScheme="blue">
                                    {project.files?.length || 0} files
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

                {/* Components Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    <FormControl>
                      <FormLabel>Components Preview</FormLabel>
                      <VStack align="start" spacing={2} maxH="400px" overflowY="auto">
                        {components.slice(0, 20).map((component) => (
                          <Box
                            key={component.key}
                            p={3}
                            border="1px solid"
                            borderColor={borderColor}
                            borderRadius="md"
                            w="full"
                          >
                            <HStack justify="space-between" align="start">
                              <VStack align="start" spacing={2}>
                                <Text fontWeight="medium">{component.name}</Text>
                                {component.description && (
                                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                                    {component.description}
                                  </Text>
                                )}
                                <HStack>
                                  <Badge size="sm" colorScheme="purple">
                                    {component.component_type}
                                  </Badge>
                                  {component.thumbnail_url && (
                                    <Image
                                      src={component.thumbnail_url}
                                      alt={component.name}
                                      boxSize="24px"
                                      borderRadius="md"
                                      objectFit="cover"
                                    />
                                  )}
                                </HStack>
                              </VStack>
                            </HStack>
                          </Box>
                        ))}
                      </VStack>
                      <FormHelperText>
                        Showing first 20 components. Full component processing during ingestion.
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
                                  name={user.name}
                                  src={user.profile_picture_url}
                                  size="sm"
                                />
                                <VStack spacing={1} align="center">
                                  <Text fontWeight="medium" fontSize="sm">
                                    {user.name}
                                  </Text>
                                  <Text fontSize="xs" color="gray.600">
                                    @{user.username}
                                  </Text>
                                  {user.email && (
                                    <Text fontSize="xs" color="gray.600">
                                      {user.email}
                                    </Text>
                                  )}
                                  <Badge size="sm" colorScheme={
                                    user.role === 'admin' ? 'red' :
                                    user.role === 'owner' ? 'orange' : 'green'
                                  }>
                                    {user.role}
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
              {['files', 'components', 'teams', 'users', 'comments', 'versions'].map((type) => (
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
              isChecked={config.settings.includeArchived}
              onChange={(e) => updateConfig('includeArchived', e.target.checked)}
            >
              Include Archived
            </Checkbox>
            <Checkbox
              isChecked={config.settings.includeDeleted}
              onChange={(e) => updateConfig('includeDeleted', e.target.checked)}
            >
              Include Deleted
            </Checkbox>
            <Checkbox
              isChecked={config.settings.includeComments}
              onChange={(e) => updateConfig('includeComments', e.target.checked)}
            >
              Include Comments
            </Checkbox>
            <Checkbox
              isChecked={config.settings.includeVersions}
              onChange={(e) => updateConfig('includeVersions', e.target.checked)}
            >
              Include Versions
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
                    <Text>Ingesting Figma data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="purple"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Files: {ingestionStatus.filesProcessed} | 
                    Components: {ingestionStatus.componentsProcessed} | 
                    Teams: {ingestionStatus.teamsProcessed} | 
                    Users: {ingestionStatus.usersProcessed}
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
                window.open('https://www.figma.com', '_blank');
              }}
            >
              Open Figma
            </Button>

            <Button
              colorScheme="purple"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !health?.connected ||
                (config.settings.files.length === 0 && config.settings.teams.length === 0) ||
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

export default FigmaManager;