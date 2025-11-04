/**
 * Slack Integration Manager Component
 * Complete Slack OAuth and API integration following GitHub pattern
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
  Tag,
  TagLabel,
  TagLeftIcon,
} from '@chakra-ui/react';
import {
  ChatIcon,
  ViewIcon,
  DeleteIcon,
  RepeatIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  AddIcon,
  SettingsIcon,
  LockIcon,
  UnlockIcon,
  InfoIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface SlackIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface SlackWorkspace {
  id: string;
  name: string;
  domain: string;
  url: string;
  icon?: string;
  enterprise_id?: string;
  enterprise_name?: string;
}

interface SlackChannel {
  id: string;
  name: string;
  display_name?: string;
  purpose?: string;
  topic?: string;
  is_private: boolean;
  is_archived: boolean;
  is_general: boolean;
  is_shared: boolean;
  is_org_shared: boolean;
  num_members: number;
  creator: string;
  created: number;
  workspace_id: string;
  type: 'channel' | 'im' | 'mpim' | 'group';
  unread_count?: number;
  latest?: string;
}

interface SlackUser {
  id: string;
  name: string;
  real_name: string;
  display_name: string;
  email?: string;
  team_id: string;
  is_admin: boolean;
  is_owner: boolean;
  is_primary_owner: boolean;
  is_restricted: boolean;
  is_ultra_restricted: boolean;
  is_bot: boolean;
  profile?: {
    real_name: string;
    display_name: string;
    image_24: string;
    image_32: string;
    image_48: string;
    image_72: string;
    image_192: string;
    title?: string;
    phone?: string;
    skype?: string;
  };
}

interface SlackMessage {
  type: string;
  subtype?: string;
  channel: string;
  user: string;
  text: string;
  ts: string;
  thread_ts?: string;
  reply_count?: number;
  reply_to?: string;
  file?: any;
  files?: any[];
  reactions?: any[];
  starred?: boolean;
  pinned?: boolean;
  is_starred?: boolean;
  is_pinned?: boolean;
}

export const SlackManager: React.FC<SlackIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Slack',
    platform: 'slack',
    enabled: true,
    settings: {
      workspaces: [],
      channels: [],
      users: [],
      messageTypes: ['messages', 'replies', 'mentions', 'files', 'reactions'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000), // 90 days ago
        end: new Date(),
      },
      includePrivateChannels: false,
      includeDirectMessages: false,
      includeFiles: true,
      maxMessages: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      webhookEvents: ['message', 'file_shared', 'reaction_added'],
    }
  });

  const [workspaces, setWorkspaces] = useState<SlackWorkspace[]>([]);
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [users, setUsers] = useState<SlackUser[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<string>('');
  const [currentUser, setCurrentUser] = useState<SlackUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    workspacesProcessed: 0,
    channelsProcessed: 0,
    messagesProcessed: 0,
    usersProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });

  // Check Slack service health
  const checkSlackHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/communication/health');
      const data = await response.json();
      
      if (data.services?.slack) {
        setHealth({
          connected: data.services.slack.status === 'healthy',
          lastSync: new Date().toISOString(),
          errors: data.services.slack.error ? [data.services.slack.error] : []
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Slack service health']
      });
    }
  }, []);

  // Load available workspaces
  const loadWorkspaces = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/slack/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setWorkspaces(data.workspaces);
      } else {
        setError(data.error || 'Failed to load workspaces');
      }
    } catch (err) {
      setError('Network error loading workspaces');
    } finally {
      setLoading(false);
    }
  };

  // Load channels for selected workspace
  const loadChannels = async () => {
    if (!selectedWorkspace) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/slack/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: selectedWorkspace,
          include_private: config.settings.includePrivateChannels,
          include_archived: false,
          limit: 200
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setChannels(data.channels);
      } else {
        setError(data.error || 'Failed to load channels');
      }
    } catch (err) {
      setError('Network error loading channels');
    } finally {
      setLoading(false);
    }
  };

  // Load users from selected workspace
  const loadUsers = async () => {
    if (!selectedWorkspace) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/slack/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: selectedWorkspace,
          include_restricted: false,
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
      const response = await fetch('/api/integrations/slack/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setCurrentUser(data.user);
      }
    } catch (err) {
      console.error('Error loading current user:', err);
    }
  };

  // Start Slack OAuth flow
  const startSlackOAuth = async () => {
    try {
      const response = await fetch('/api/auth/slack/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'channels:read',
            'channels:history',
            'groups:read',
            'groups:history',
            'im:read',
            'im:history',
            'mpim:read',
            'mpim:history',
            'users:read',
            'files:read',
            'reactions:read',
            'team:read'
          ]
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Open OAuth URL in popup
        const popup = window.open(
          data.authorization_url,
          'slack-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        // Listen for OAuth completion
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkSlackAuthStatus();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Slack OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Slack OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Check Slack auth status
  const checkSlackAuthStatus = async () => {
    try {
      const response = await fetch('/api/auth/slack/status', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (data.connected) {
        toast({
          title: 'Slack Connected',
          description: 'Successfully authenticated with Slack',
          status: 'success',
          duration: 3000,
        });
        
        // Load workspaces and current user
        loadWorkspaces();
        loadCurrentUser();
      } else {
        toast({
          title: 'Authentication Required',
          description: 'Please connect to Slack first',
          status: 'warning',
          duration: 3000,
        });
      }
    } catch (err) {
      toast({
        title: 'Status Check Failed',
        description: 'Could not verify Slack connection',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Start Slack data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      workspacesProcessed: 0,
      channelsProcessed: 0,
      messagesProcessed: 0,
      usersProcessed: 0,
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
        sourceType: 'slack',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Slack Ingestion Completed',
          description: `Successfully processed ${ingestionResult.messagesProcessed} messages`,
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
        title: 'Slack Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Handle workspace selection
  const handleWorkspaceToggle = (workspaceId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        workspaces: isChecked
          ? [...prev.settings.workspaces, workspaceId]
          : prev.settings.workspaces.filter(id => id !== workspaceId)
      }
    }));
  };

  // Handle channel selection
  const handleChannelToggle = (channelId: string, isChecked: boolean) => {
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        channels: isChecked
          ? [...prev.settings.channels, channelId]
          : prev.settings.channels.filter(id => id !== channelId)
      }
    }));
  };

  // Handle workspace select
  const handleWorkspaceSelect = (workspaceId: string) => {
    setSelectedWorkspace(workspaceId);
    loadChannels();
    loadUsers();
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
    checkSlackHealth();
  }, []);

  useEffect(() => {
    if (selectedWorkspace) {
      loadChannels();
      loadUsers();
    }
  }, [selectedWorkspace]);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={ChatIcon} w={6} h={6} color="purple.500" />
            <Heading size="md">Slack Integration</Heading>
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
                checkSlackHealth();
                loadWorkspaces();
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
                    name={currentUser.profile?.display_name || currentUser.real_name}
                    src={currentUser.profile?.image_48}
                    size="md"
                  />
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">
                      {currentUser.profile?.display_name || currentUser.real_name}
                    </Text>
                    <Text fontSize="sm" color="gray.600">@{currentUser.name}</Text>
                    {currentUser.profile?.title && (
                      <Text fontSize="sm" color="gray.500">{currentUser.profile.title}</Text>
                    )}
                    <HStack spacing={2}>
                      {currentUser.is_admin && <Badge size="sm" colorScheme="blue">Admin</Badge>}
                      {currentUser.is_owner && <Badge size="sm" colorScheme="purple">Owner</Badge>}
                      {currentUser.is_bot && <Badge size="sm" colorScheme="orange">Bot</Badge>}
                    </HStack>
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
                  Slack service {health.connected ? 'healthy' : 'unhealthy'}
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
                leftIcon={<ChatIcon />}
                onClick={startSlackOAuth}
                width="full"
                size="lg"
              >
                Connect to Slack
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Click to authenticate with Slack using OAuth 2.0
              </Text>
            </VStack>
          )}

          {/* Workspaces Selection */}
          {workspaces.length > 0 && (
            <FormControl>
              <FormLabel>Workspaces</FormLabel>
              <VStack align="start" spacing={3} maxH="300px" overflowY="auto">
                {workspaces.map((workspace) => (
                  <HStack key={workspace.id} justify="space-between" w="full">
                    <Checkbox
                      isChecked={config.settings.workspaces.includes(workspace.id)}
                      onChange={(e) => handleWorkspaceToggle(workspace.id, e.target.checked)}
                    >
                      <VStack align="start" spacing={1}>
                        <HStack>
                          <Text fontWeight="medium">{workspace.name}</Text>
                          <Tag size="sm" variant="subtle">
                            <TagLabel>slack.com</TagLabel>
                          </Tag>
                        </HStack>
                        <Text fontSize="sm" color="gray.600">Domain: {workspace.domain}</Text>
                        {workspace.enterprise_name && (
                          <Text fontSize="sm" color="gray.500">
                            Enterprise: {workspace.enterprise_name}
                          </Text>
                        )}
                      </VStack>
                    </Checkbox>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleWorkspaceSelect(workspace.id)}
                      leftIcon={<ViewIcon />}
                    >
                      View Channels
                    </Button>
                  </HStack>
                ))}
              </VStack>
              <FormHelperText>
                Select workspaces to ingest data from
              </FormHelperText>
            </FormControl>
          )}

          {/* Channels Selection */}
          {channels.length > 0 && (
            <FormControl>
              <FormLabel>
                Channels from {selectedWorkspace ? workspaces.find(w => w.id === selectedWorkspace)?.name : 'Selected Workspace'}
              </FormLabel>
              <SimpleGrid columns={responsiveGridCols} spacing={3} maxH="400px" overflowY="auto">
                {channels.map((channel) => (
                  <Card key={channel.id} variant="outline" size="sm">
                    <CardBody p={3}>
                      <VStack align="start" spacing={2}>
                        <HStack w="full" justify="space-between">
                          <Checkbox
                            isChecked={config.settings.channels.includes(channel.id)}
                            onChange={(e) => handleChannelToggle(channel.id, e.target.checked)}
                          >
                            <HStack>
                              <Text fontWeight="medium">{channel.display_name || channel.name}</Text>
                              {channel.is_private && (
                                <Icon as={LockIcon} w={3} h={3} color="orange.500" />
                              )}
                              {channel.is_shared && (
                                <Icon as={UnlockIcon} w={3} h={3} color="blue.500" />
                              )}
                            </HStack>
                          </Checkbox>
                        </HStack>
                        {channel.purpose && (
                          <Text fontSize="xs" color="gray.600" noOfLines={1}>
                            {channel.purpose}
                          </Text>
                        )}
                        <HStack spacing={2}>
                          <Badge size="sm" colorScheme={
                            channel.type === 'channel' ? 'green' :
                            channel.type === 'private' ? 'orange' :
                            channel.type === 'im' ? 'blue' : 'purple'
                          }>
                            {channel.type}
                          </Badge>
                          {channel.num_members && (
                            <Badge size="sm" variant="outline">
                              {channel.num_members} members
                            </Badge>
                          )}
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>
                ))}
              </SimpleGrid>
              <FormHelperText>
                Select channels to ingest messages from
              </FormHelperText>
            </FormControl>
          )}

          <Divider />

          {/* Message Types */}
          <FormControl>
            <FormLabel>Message Types</FormLabel>
            <Stack direction="row" spacing={4}>
              {['messages', 'replies', 'mentions', 'files', 'reactions', 'starred'].map((type) => (
                <Checkbox
                  key={type}
                  isChecked={config.settings.messageTypes.includes(type)}
                  onChange={(e) => {
                    const newTypes = e.target.checked
                      ? [...config.settings.messageTypes, type]
                      : config.settings.messageTypes.filter(t => t !== type);
                    updateConfig('messageTypes', newTypes);
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
          <Collapse in={showAdvanced} animateOpacity>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>Max Messages</FormLabel>
                <Input
                  type="number"
                  value={config.settings.maxMessages}
                  onChange={(e) => updateConfig('maxMessages', parseInt(e.target.value))}
                />
              </FormControl>

              <FormControl>
                <FormLabel>Sync Frequency</FormLabel>
                <Select
                  value={config.settings.syncFrequency}
                  onChange={(e) => updateConfig('syncFrequency', e.target.value)}
                >
                  <option value="realtime">Real-time</option>
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </Select>
              </FormControl>

              <HStack>
                <Checkbox
                  isChecked={config.settings.includePrivateChannels}
                  onChange={(e) => updateConfig('includePrivateChannels', e.target.checked)}
                >
                  Include Private Channels
                </Checkbox>
                <Checkbox
                  isChecked={config.settings.includeDirectMessages}
                  onChange={(e) => updateConfig('includeDirectMessages', e.target.checked)}
                >
                  Include Direct Messages
                </Checkbox>
                <Checkbox
                  isChecked={config.settings.includeFiles}
                  onChange={(e) => updateConfig('includeFiles', e.target.checked)}
                >
                  Include Files
                </Checkbox>
              </HStack>
            </VStack>
          </Collapse>

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
                    <Text>Ingesting Slack data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="purple"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Workspaces: {ingestionStatus.workspacesProcessed} | 
                    Channels: {ingestionStatus.channelsProcessed} | 
                    Messages: {ingestionStatus.messagesProcessed} | 
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
                window.open('https://slack.com', '_blank');
              }}
            >
              Open Slack
            </Button>

            <Button
              colorScheme="purple"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !health?.connected ||
                (config.settings.workspaces.length === 0 && config.settings.channels.length === 0) ||
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

export default SlackManager;