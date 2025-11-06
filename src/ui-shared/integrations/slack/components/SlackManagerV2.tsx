"""
Enhanced Slack Integration Manager Component
Complete Slack integration with real-time updates and advanced features
"""

import React, { useState, useEffect, useCallback, useMemo } from 'react';
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
  Progress,
  Alert,
  AlertIcon,
  Divider,
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
  Badge,
  useToast,
  useColorModeValue,
  SimpleGrid,
  Icon,
  Tooltip,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  IconButton,
  FormControl,
  FormLabel,
  Input,
  FormHelperText,
  Checkbox,
  Select,
  Switch,
  Stack,
  Avatar,
  Tag,
  TagLabel,
  TagLeftIcon,
  Spacer,
  Fade,
  ScaleFade,
  SlideFade,
} from '@chakra-ui/react';
import {
  ChatIcon,
  SettingsIcon,
  ViewIcon,
  SearchIcon,
  TimeIcon,
  CheckCircleIcon,
  WarningIcon,
  InfoIcon,
  RepeatIcon,
  ExternalLinkIcon,
  AddIcon,
  DeleteIcon,
  EditIcon,
  MoreVerticalIcon,
  BellIcon,
  FileIcon,
  UserIcon,
  ChannelIcon,
  LockIcon,
  UnlockIcon,
  StarIcon,
  LinkIcon,
  EmailIcon,
  CalendarIcon,
} from '@chakra-ui/icons';

interface SlackIntegrationProps {
  atomIngestionPipeline: any;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: any) => void;
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
  is_verified?: boolean;
  plan?: string;
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
  num_members: number;
  created: number;
  workspace_id: string;
  workspace_name?: string;
}

interface SlackUser {
  id: string;
  name: string;
  real_name: string;
  display_name: string;
  email?: string;
  is_bot: boolean;
  is_admin: boolean;
  is_owner: boolean;
  presence: string;
  avatar?: string;
  profile?: any;
}

interface SlackMessage {
  id: string;
  text: string;
  user: string;
  user_name?: string;
  channel: string;
  channel_name?: string;
  team: string;
  ts: string;
  thread_ts?: string;
  type: string;
  subtype?: string;
  reactions: any[];
  files: any[];
  pinned_to: string[];
  is_starred: boolean;
  reply_count: number;
  has_files: boolean;
  has_reactions: boolean;
}

interface SlackFile {
  id: string;
  name: string;
  title: string;
  mimetype: string;
  filetype: string;
  pretty_type: string;
  size: number;
  user: string;
  username?: string;
  url_private: string;
  permalink: string;
  created: number;
  timestamp: number;
  is_public: boolean;
  public_url_shared: boolean;
  thumb_64?: string;
  thumb_360?: string;
  workspace_id: string;
  uploader_name?: string;
}

interface DataSourceConfig {
  name: string;
  platform: string;
  enabled: boolean;
  settings: {
    workspaces: SlackWorkspace[];
    channels: SlackChannel[];
    users: SlackUser[];
    syncOptions: {
      messageTypes: string[];
      dateRange: {
        start: Date;
        end: Date;
      };
      realTimeSync: boolean;
      syncFrequency: string;
    };
    filters: {
      includePrivate: boolean;
      includeArchived: boolean;
      excludeBots: boolean;
      dateFilter?: {
        start: string;
        end: string;
      };
      userFilter?: string[];
    };
    features: {
      reactions: boolean;
      threads: boolean;
      mentions: boolean;
      starred: boolean;
      pinned: boolean;
      files: boolean;
    };
    notifications: {
      newMessages: boolean;
      mentions: boolean;
      fileShares: boolean;
      channelUpdates: boolean;
    };
  };
}

interface IngestionStatus {
  running: boolean;
  progress: number;
  stage: string;
  message: string;
  itemsProcessed?: number;
  totalItems?: number;
  startTime?: string;
  endTime?: string;
  error?: string;
}

interface HealthStatus {
  connected: boolean;
  last_check?: string;
  error_count?: number;
  total_requests?: number;
  workspace_count?: number;
  channel_count?: number;
  user_count?: number;
}

const SlackIntegrationManager: React.FC<SlackIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  // State management
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Slack',
    platform: 'slack',
    enabled: true,
    settings: {
      workspaces: [],
      channels: [],
      users: [],
      syncOptions: {
        messageTypes: ['messages', 'replies', 'files'],
        dateRange: {
          start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000),
          end: new Date(),
        },
        realTimeSync: true,
        syncFrequency: 'realtime',
      },
      filters: {
        includePrivate: false,
        includeArchived: false,
        excludeBots: false,
      },
      features: {
        reactions: true,
        threads: true,
        mentions: true,
        starred: true,
        pinned: true,
        files: true,
      },
      notifications: {
        newMessages: true,
        mentions: true,
        fileShares: true,
        channelUpdates: false,
      },
    }
  });

  const [data, setData] = useState({
    workspaces: [] as SlackWorkspace[],
    channels: [] as SlackChannel[],
    users: [] as SlackUser[],
    messages: [] as SlackMessage[],
    files: [] as SlackFile[],
  });

  const [state, setState] = useState({
    loading: false,
    error: null as string | null,
    health: null as HealthStatus | null,
    selectedWorkspace: null as SlackWorkspace | null,
    selectedChannel: null as SlackChannel | null,
    ingestionStatus: {
      running: false,
      progress: 0,
      stage: 'idle',
      message: '',
    } as IngestionStatus,
    searchQuery: '',
    searchResults: [] as any[],
    showSearch: false,
  });

  const [modals, setModals] = useState({
    configuration: false,
    search: false,
    workspaceDetails: false,
    channelDetails: false,
    userDetails: false,
  });

  // Hooks
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  // Utility functions
  const formatTimestamp = (ts: string) => {
    const date = new Date(parseFloat(ts) * 1000);
    return date.toLocaleString();
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active':
      case 'online':
      case 'connected':
        return 'green';
      case 'away':
      case 'inactive':
        return 'yellow';
      case 'offline':
      case 'disconnected':
        return 'red';
      default:
        return 'gray';
    }
  };

  // API functions
  const fetchWorkspaces = useCallback(async () => {
    setState(prev => ({ ...prev, loading: true, error: null }));
    
    try {
      const response = await fetch('/api/integrations/slack/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
      });
      
      const result = await response.json();
      
      if (result.ok) {
        setData(prev => ({
          ...prev,
          workspaces: result.workspaces || []
        }));
        setState(prev => ({
          ...prev,
          health: {
            ...prev.health,
            workspace_count: result.workspaces?.length || 0
          }
        }));
      } else {
        setState(prev => ({ ...prev, error: result.error || 'Failed to fetch workspaces' }));
        toast({
          title: 'Error',
          description: result.error || 'Failed to fetch workspaces',
          status: 'error',
        });
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Network error';
      setState(prev => ({ ...prev, error }));
      toast({
        title: 'Network Error',
        description: 'Failed to connect to server',
        status: 'error',
      });
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [userId, toast]);

  const fetchChannels = useCallback(async (workspaceId: string) => {
    setState(prev => ({ ...prev, loading: true }));
    
    try {
      const response = await fetch('/api/integrations/slack/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId,
          include_private: config.settings.filters.includePrivate,
          include_archived: config.settings.filters.includeArchived,
        })
      });
      
      const result = await response.json();
      
      if (result.ok) {
        setData(prev => ({
          ...prev,
          channels: result.channels || []
        }));
        setState(prev => ({
          ...prev,
          health: {
            ...prev.health,
            channel_count: result.channels?.length || 0
          }
        }));
      } else {
        setState(prev => ({ ...prev, error: result.error || 'Failed to fetch channels' }));
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Network error';
      setState(prev => ({ ...prev, error }));
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [userId, config.settings.filters.includePrivate, config.settings.filters.includeArchived]);

  const fetchUsers = useCallback(async (workspaceId: string) => {
    setState(prev => ({ ...prev, loading: true }));
    
    try {
      const response = await fetch('/api/integrations/slack/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId,
          include_restricted: true,
          include_bots: !config.settings.filters.excludeBots,
        })
      });
      
      const result = await response.json();
      
      if (result.ok) {
        setData(prev => ({
          ...prev,
          users: result.users || []
        }));
        setState(prev => ({
          ...prev,
          health: {
            ...prev.health,
            user_count: result.users?.length || 0
          }
        }));
      } else {
        setState(prev => ({ ...prev, error: result.error || 'Failed to fetch users' }));
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Network error';
      setState(prev => ({ ...prev, error }));
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [userId, config.settings.filters.excludeBots]);

  const fetchMessages = useCallback(async (channelId: string, workspaceId: string) => {
    setState(prev => ({ ...prev, loading: true }));
    
    try {
      const response = await fetch('/api/integrations/slack/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId,
          channel_id: channelId,
          limit: 100,
          filters: config.settings.filters,
        })
      });
      
      const result = await response.json();
      
      if (result.ok) {
        setData(prev => ({
          ...prev,
          messages: result.messages || []
        }));
      } else {
        setState(prev => ({ ...prev, error: result.error || 'Failed to fetch messages' }));
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Network error';
      setState(prev => ({ ...prev, error }));
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [userId, config.settings.filters]);

  const searchMessages = useCallback(async (query: string) => {
    if (!query.trim() || !data.workspaces.length) return;
    
    setState(prev => ({ ...prev, loading: true }));
    
    try {
      const response = await fetch('/api/integrations/slack/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: data.workspaces[0].id,
          query: query.trim(),
          count: 50,
        })
      });
      
      const result = await response.json();
      
      if (result.ok) {
        setState(prev => ({
          ...prev,
          searchResults: result.messages || []
        }));
      } else {
        setState(prev => ({ ...prev, error: result.error || 'Search failed' }));
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Network error';
      setState(prev => ({ ...prev, error }));
    } finally {
      setState(prev => ({ ...prev, loading: false }));
    }
  }, [userId, data.workspaces]);

  // OAuth and authentication
  const handleOAuth = useCallback(async () => {
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
            'team:read',
            'chat:write',
            'chat:write.public'
          ]
        })
      });
      
      const result = await response.json();
      
      if (result.ok) {
        const popup = window.open(
          result.authorization_url,
          'slack-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        // Listen for OAuth completion
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            fetchWorkspaces();
          }
        }, 1000);
        
        toast({
          title: 'OAuth Started',
          description: 'Please complete the authorization in the popup window',
          status: 'info',
        });
      } else {
        toast({
          title: 'OAuth Failed',
          description: result.error,
          status: 'error',
        });
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : 'Network error';
      toast({
        title: 'Network Error',
        description: 'Failed to start OAuth flow',
        status: 'error',
      });
    }
  }, [userId, fetchWorkspaces, toast]);

  // Configuration management
  const updateConfiguration = useCallback((path: string, value: any) => {
    setConfig(prev => {
      const newConfig = { ...prev };
      const keys = path.split('.');
      let current: any = newConfig.settings;
      
      for (let i = 0; i < keys.length - 1; i++) {
        if (!current[keys[i]]) {
          current[keys[i]] = {};
        }
        current = current[keys[i]];
      }
      
      current[keys[keys.length - 1]] = value;
      
      if (onConfigurationChange) {
        onConfigurationChange(newConfig);
      }
      
      return newConfig;
    });
  }, [onConfigurationChange]);

  // Ingestion management
  const startIngestion = useCallback(async () => {
    setState(prev => ({
      ...prev,
      ingestionStatus: {
        running: true,
        progress: 0,
        stage: 'Starting',
        message: 'Initializing ingestion...',
        itemsProcessed: 0,
        totalItems: 0,
        startTime: new Date().toISOString(),
      }
    }));

    try {
      const result = await atomIngestionPipeline.startIngestion({
        sourceType: 'slack',
        config: config.settings,
        callback: (status: any) => {
          setState(prev => ({
            ...prev,
            ingestionStatus: {
              ...prev.ingestionStatus,
              progress: status.progress,
              stage: status.stage,
              message: status.message,
              itemsProcessed: status.itemsProcessed,
            }
          }));
        }
      });

      if (result.success) {
        setState(prev => ({
          ...prev,
          ingestionStatus: {
            ...prev.ingestionStatus,
            running: false,
            progress: 100,
            stage: 'Complete',
            message: 'Ingestion completed successfully',
            endTime: new Date().toISOString(),
          }
        }));

        toast({
          title: 'Ingestion Complete',
          description: `Processed ${result.itemsProcessed} items`,
          status: 'success',
        });
        
        if (onIngestionComplete) {
          onIngestionComplete(result);
        }
      } else {
        throw new Error(result.error || 'Ingestion failed');
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error('Unknown error');
      
      setState(prev => ({
        ...prev,
        ingestionStatus: {
          ...prev.ingestionStatus,
          running: false,
          stage: 'Failed',
          message: error.message,
          error: error.message,
          endTime: new Date().toISOString(),
        }
      }));

      toast({
        title: 'Ingestion Failed',
        description: error.message,
        status: 'error',
      });

      if (onError) {
        onError(error);
      }
    }
  }, [atomIngestionPipeline, config.settings, onIngestionComplete, onError, toast]);

  // Memoized components
  const StatsOverview = useMemo(() => (
    <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
      <Stat>
        <StatLabel>Workspaces</StatLabel>
        <StatNumber>{data.workspaces.length}</StatNumber>
        <StatHelpText>
          <Icon as={CheckCircleIcon} color="green.500" mr={1} />
          Connected
        </StatHelpText>
      </Stat>
      <Stat>
        <StatLabel>Channels</StatLabel>
        <StatNumber>{data.channels.length}</StatNumber>
        <StatHelpText>
          <Icon as={ChannelIcon} color="blue.500" mr={1} />
          Available
        </StatHelpText>
      </Stat>
      <Stat>
        <StatLabel>Users</StatLabel>
        <StatNumber>{data.users.length}</StatNumber>
        <StatHelpText>
          <Icon as={UserIcon} color="purple.500" mr={1} />
          Active
        </StatHelpText>
      </Stat>
      <Stat>
        <StatLabel>Messages</StatLabel>
        <StatNumber>{data.messages.length}</StatNumber>
        <StatHelpText>
          <Icon as={ChatIcon} color="orange.500" mr={1} />
          Indexed
        </StatHelpText>
      </Stat>
    </SimpleGrid>
  ), [data]);

  const WorkspacesList = useMemo(() => (
    <VStack spacing={4} align="stretch">
      <HStack justify="space-between">
        <Heading size="md">Workspaces</Heading>
        <HStack>
          <Button
            leftIcon={<RepeatIcon />}
            onClick={fetchWorkspaces}
            isLoading={state.loading}
            size="sm"
          >
            Refresh
          </Button>
          <Button
            leftIcon={<AddIcon />}
            onClick={handleOAuth}
            size="sm"
            colorScheme="purple"
          >
            Add Workspace
          </Button>
        </HStack>
      </HStack>
      
      {data.workspaces.length === 0 ? (
        <Alert status="info" borderRadius="md">
          <InfoIcon />
          <Box>
            <Text fontWeight="bold">No workspaces connected</Text>
            <Text>Click "Add Workspace" to connect your Slack workspace</Text>
          </Box>
        </Alert>
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
          {data.workspaces.map((workspace) => (
            <Card key={workspace.id} variant="outline" borderWidth="1px" borderColor={borderColor}>
              <CardBody>
                <VStack spacing={3} align="stretch">
                  <HStack justify="space-between">
                    <HStack>
                      <Avatar
                        name={workspace.name}
                        src={workspace.icon}
                        size="sm"
                      />
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="bold">{workspace.name}</Text>
                        <Text fontSize="sm" color="gray.600">
                          {workspace.domain}.slack.com
                        </Text>
                      </VStack>
                    </HStack>
                    <Menu>
                      <MenuButton
                        as={IconButton}
                        icon={<MoreVerticalIcon />}
                        variant="ghost"
                        size="sm"
                      />
                      <MenuList>
                        <MenuItem
                          icon={<ViewIcon />}
                          onClick={() => {
                            setState(prev => ({ ...prev, selectedWorkspace: workspace }));
                            fetchChannels(workspace.id);
                          }}
                        >
                          View Channels
                        </MenuItem>
                        <MenuItem
                          icon={<UserIcon />}
                          onClick={() => {
                            setState(prev => ({ ...prev, selectedWorkspace: workspace }));
                            fetchUsers(workspace.id);
                          }}
                        >
                          View Users
                        </MenuItem>
                        <MenuItem
                          icon={<SettingsIcon />}
                          onClick={() => setModals(prev => ({ ...prev, configuration: true }))}
                        >
                          Configure
                        </MenuItem>
                        <MenuItem
                          icon={<DeleteIcon />}
                          onClick={() => {/* Handle disconnect */}}
                          color="red.500"
                        >
                          Disconnect
                        </MenuItem>
                      </MenuList>
                    </Menu>
                  </HStack>
                  
                  <HStack spacing={2} flexWrap="wrap">
                    <Badge colorScheme="green" display="flex" alignItems="center">
                      <Icon as={CheckCircleIcon} mr={1} />
                      Connected
                    </Badge>
                    {workspace.enterprise_name && (
                      <Badge colorScheme="blue">Enterprise</Badge>
                    )}
                    {workspace.is_verified && (
                      <Badge colorScheme="purple">Verified</Badge>
                    )}
                  </HStack>
                  
                  <HStack spacing={4} fontSize="sm" color="gray.600">
                    <HStack>
                      <ChannelIcon />
                      <Text>{data.channels.filter(c => c.workspace_id === workspace.id).length} channels</Text>
                    </HStack>
                    <HStack>
                      <UserIcon />
                      <Text>{data.users.filter(u => (u as any).workspace_id === workspace.id).length} users</Text>
                    </HStack>
                  </HStack>
                </VStack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>
      )}
    </VStack>
  ), [data.workspaces, data.channels, data.users, state.loading, fetchWorkspaces, fetchChannels, fetchUsers, borderColor]);

  const SearchInterface = useMemo(() => (
    <VStack spacing={4} align="stretch">
      <Heading size="md">Search Messages</Heading>
      
      <FormControl>
        <Input
          placeholder="Search messages, files, or users..."
          value={state.searchQuery}
          onChange={(e) => {
            setState(prev => ({ ...prev, searchQuery: e.target.value }));
            if (e.target.value.trim()) {
              searchMessages(e.target.value);
            } else {
              setState(prev => ({ ...prev, searchResults: [] }));
            }
          }}
          onKeyPress={(e) => {
            if (e.key === 'Enter' && state.searchQuery.trim()) {
              searchMessages(state.searchQuery);
            }
          }}
        />
        <FormHelperText>
          Search across all connected workspaces and channels
        </FormHelperText>
      </FormControl>
      
      {state.searchResults.length > 0 && (
        <VStack spacing={2} align="stretch" maxH="400px" overflowY="auto">
          {state.searchResults.map((message: any) => (
            <Card key={message.id} size="sm" variant="outline">
              <CardBody>
                <VStack spacing={2} align="start">
                  <HStack justify="space-between" w="full">
                    <HStack>
                      <Avatar size="xs" name={message.user_name} />
                      <Text fontWeight="medium">{message.user_name}</Text>
                      <Text fontSize="sm" color="gray.600">in #{message.channel_name}</Text>
                    </HStack>
                    <Text fontSize="xs" color="gray.500">
                      {formatTimestamp(message.ts)}
                    </Text>
                  </HStack>
                  
                  <Text fontSize="sm" noOfLines={2}>
                    {message.text}
                  </Text>
                  
                  {message.has_files && (
                    <HStack>
                      <FileIcon />
                      <Text fontSize="xs" color="gray.600">
                        {message.file_count} file(s)
                      </Text>
                    </HStack>
                  )}
                  
                  {message.has_reactions && (
                    <HStack>
                      <Text fontSize="xs" color="gray.600">
                        {message.reaction_count} reaction(s)
                      </Text>
                    </HStack>
                  )}
                </VStack>
              </CardBody>
            </Card>
          ))}
        </VStack>
      )}
      
      {state.searchQuery && !state.loading && state.searchResults.length === 0 && (
        <Alert status="info">
          <InfoIcon />
          <Text>No results found for "{state.searchQuery}"</Text>
        </Alert>
      )}
    </VStack>
  ), [state.searchQuery, state.searchResults, state.loading, searchMessages]);

  const ConfigurationPanel = useMemo(() => (
    <VStack spacing={6} align="stretch">
      <Heading size="md">Configuration</Heading>
      
      <FormControl>
        <FormLabel>Sync Options</FormLabel>
        <VStack align="start" spacing={3}>
          <Checkbox
            isChecked={config.settings.syncOptions.realTimeSync}
            onChange={(e) => updateConfiguration('syncOptions.realTimeSync', e.target.checked)}
          >
            Real-time Sync
          </Checkbox>
          <Checkbox
            isChecked={config.settings.features.reactions}
            onChange={(e) => updateConfiguration('features.reactions', e.target.checked)}
          >
            Include Reactions
          </Checkbox>
          <Checkbox
            isChecked={config.settings.features.threads}
            onChange={(e) => updateConfiguration('features.threads', e.target.checked)}
          >
            Include Threads
          </Checkbox>
          <Checkbox
            isChecked={config.settings.features.files}
            onChange={(e) => updateConfiguration('features.files', e.target.checked)}
          >
            Include Files
          </Checkbox>
        </VStack>
      </FormControl>
      
      <FormControl>
        <FormLabel>Filters</FormLabel>
        <VStack align="start" spacing={3}>
          <Checkbox
            isChecked={config.settings.filters.includePrivate}
            onChange={(e) => updateConfiguration('filters.includePrivate', e.target.checked)}
          >
            Include Private Channels
          </Checkbox>
          <Checkbox
            isChecked={config.settings.filters.includeArchived}
            onChange={(e) => updateConfiguration('filters.includeArchived', e.target.checked)}
          >
            Include Archived Channels
          </Checkbox>
          <Checkbox
            isChecked={config.settings.filters.excludeBots}
            onChange={(e) => updateConfiguration('filters.excludeBots', e.target.checked)}
          >
            Exclude Bot Messages
          </Checkbox>
        </VStack>
      </FormControl>
      
      <FormControl>
        <FormLabel>Sync Frequency</FormLabel>
        <Select
          value={config.settings.syncOptions.syncFrequency}
          onChange={(e) => updateConfiguration('syncOptions.syncFrequency', e.target.value)}
        >
          <option value="realtime">Real-time</option>
          <option value="hourly">Hourly</option>
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
        </Select>
      </FormControl>
      
      <FormControl>
        <FormLabel>Notifications</FormLabel>
        <VStack align="start" spacing={3}>
          <Checkbox
            isChecked={config.settings.notifications.newMessages}
            onChange={(e) => updateConfiguration('notifications.newMessages', e.target.checked)}
          >
            New Messages
          </Checkbox>
          <Checkbox
            isChecked={config.settings.notifications.mentions}
            onChange={(e) => updateConfiguration('notifications.mentions', e.target.checked)}
          >
            Mentions
          </Checkbox>
          <Checkbox
            isChecked={config.settings.notifications.fileShares}
            onChange={(e) => updateConfiguration('notifications.fileShares', e.target.checked)}
          >
            File Shares
          </Checkbox>
        </VStack>
      </FormControl>
    </VStack>
  ), [config, updateConfiguration]);

  const IngestionPanel = useMemo(() => (
    <VStack spacing={6} align="stretch">
      <HStack justify="space-between">
        <Heading size="md">Data Ingestion</Heading>
        <Button
          colorScheme="purple"
          leftIcon={<AddIcon />}
          onClick={startIngestion}
          isDisabled={!data.workspaces.length || state.ingestionStatus.running}
          isLoading={state.ingestionStatus.running}
        >
          {state.ingestionStatus.running ? 'Ingesting...' : 'Start Ingestion'}
        </Button>
      </HStack>

      {state.ingestionStatus.running && (
        <Card>
          <CardBody>
            <VStack spacing={3}>
              <HStack justify="space-between" w="full">
                <Text>{state.ingestionStatus.stage}</Text>
                <Text>{Math.round(state.ingestionStatus.progress)}%</Text>
              </HStack>
              <Progress
                value={state.ingestionStatus.progress}
                size="md"
                colorScheme="purple"
                w="full"
              />
              <Text fontSize="sm" color="gray.600">
                {state.ingestionStatus.message}
              </Text>
              {state.ingestionStatus.itemsProcessed && (
                <Text fontSize="sm" color="gray.600">
                  Processed: {state.ingestionStatus.itemsProcessed} items
                </Text>
              )}
            </VStack>
          </CardBody>
        </Card>
      )}
      
      <Alert status="info">
        <InfoIcon />
        <Box>
          <Text fontWeight="bold">Data Ingestion</Text>
          <Text>
            ATOM will sync your Slack data based on the configuration above.
            Real-time sync will listen for new messages and events.
          </Text>
        </Box>
      </Alert>
    </VStack>
  ), [data.workspaces.length, state.ingestionStatus, startIngestion]);

  // Effects
  useEffect(() => {
    fetchWorkspaces();
  }, [fetchWorkspaces]);

  useEffect(() => {
    const interval = setInterval(() => {
      // Update health status periodically
      if (data.workspaces.length > 0) {
        setState(prev => ({
          ...prev,
          health: {
            ...prev.health,
            connected: true,
            last_check: new Date().toISOString(),
          }
        }));
      }
    }, 30000); // Every 30 seconds

    return () => clearInterval(interval);
  }, [data.workspaces]);

  return (
    <Card bg={bgColor} borderWidth="1px" borderColor={borderColor}>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={ChatIcon} w={6} h={6} color="purple.500" />
            <Heading size="md">Slack Integration</Heading>
          </HStack>
          <HStack>
            <Badge
              colorScheme={state.health?.connected ? 'green' : 'red'}
              display="flex"
              alignItems="center"
            >
              <Icon as={state.health?.connected ? CheckCircleIcon : WarningIcon} mr={1} />
              {state.health?.connected ? 'Connected' : 'Disconnected'}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<ExternalLinkIcon />}
              onClick={() => window.open('https://slack.com', '_blank')}
            >
              Open Slack
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <Tabs isLazy variant="enclosed">
          <TabList>
            <Tab>
              <HStack>
                <Icon as={ViewIcon} />
                <Text>Overview</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <Icon as={ChatIcon} />
                <Text>Workspaces</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <Icon as={SearchIcon} />
                <Text>Search</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <Icon as={SettingsIcon} />
                <Text>Configuration</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <Icon as={TimeIcon} />
                <Text>Ingestion</Text>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
            <TabPanel>
              <VStack spacing={6} align="stretch">
                {data.workspaces.length > 0 ? StatsOverview : (
                  <Alert status="info" borderRadius="md">
                    <InfoIcon />
                    <Box>
                      <Text fontWeight="bold">Slack not connected</Text>
                      <Text>Connect your Slack workspace to start ingesting data</Text>
                    </Box>
                    <Button
                      ml={4}
                      colorScheme="purple"
                      leftIcon={<ChatIcon />}
                      onClick={handleOAuth}
                    >
                      Connect to Slack
                    </Button>
                  </Alert>
                )}
                
                {state.ingestionStatus.running && (
                  <Fade in>
                    <Card>
                      <CardBody>
                        <VStack spacing={3}>
                          <HStack justify="space-between" w="full">
                            <Text>{state.ingestionStatus.stage}</Text>
                            <Text>{Math.round(state.ingestionStatus.progress)}%</Text>
                          </HStack>
                          <Progress
                            value={state.ingestionStatus.progress}
                            size="md"
                            colorScheme="purple"
                            w="full"
                          />
                          <Text fontSize="sm" color="gray.600">
                            {state.ingestionStatus.message}
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  </Fade>
                )}
              </VStack>
            </TabPanel>

            <TabPanel>
              {WorkspacesList}
            </TabPanel>

            <TabPanel>
              {SearchInterface}
            </TabPanel>

            <TabPanel>
              {ConfigurationPanel}
            </TabPanel>

            <TabPanel>
              {IngestionPanel}
            </TabPanel>
          </TabPanels>
        </Tabs>
      </CardBody>
    </Card>
  );
};

export default SlackIntegrationManager;