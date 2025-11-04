/**
 * Microsoft Teams Integration Manager Component
 * Complete Teams OAuth and API integration following GitHub pattern
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
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface TeamsIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface TeamsChannel {
  id: string;
  displayName: string;
  description?: string;
  membershipType: 'standard' | 'private' | 'shared';
  teamId: string;
  teamName: string;
  webUrl: string;
  tenantId: string;
  membersCount?: number;
}

interface TeamsTeam {
  id: string;
  displayName: string;
  description?: string;
  visibility: 'public' | 'private';
  specialization?: 'none' | 'educationStandard';
  webUrl: string;
  tenantId: string;
  membersCount?: number;
  channelsCount?: number;
  createdDateTime?: string;
}

interface TeamsUser {
  id: string;
  displayName: string;
  mail?: string;
  userPrincipalName: string;
  jobTitle?: string;
  department?: string;
  officeLocation?: string;
  avatar?: string;
  isTeamOwner?: boolean;
}

export const TeamsManager: React.FC<TeamsIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Microsoft Teams',
    platform: 'teams',
    enabled: true,
    settings: {
      teams: [],
      channels: [],
      users: [],
      messageTypes: ['messages', 'replies', 'mentions', 'files'],
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
      webhookEvents: ['messageCreated', 'messageUpdated', 'messageDeleted'],
      tenantId: '',
    }
  });

  const [teams, setTeams] = useState<TeamsTeam[]>([]);
  const [channels, setChannels] = useState<TeamsChannel[]>([]);
  const [users, setUsers] = useState<TeamsUser[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [currentUser, setCurrentUser] = useState<TeamsUser | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    teamsProcessed: 0,
    channelsProcessed: 0,
    messagesProcessed: 0,
    usersProcessed: 0,
    errors: []
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });

  // Check Teams service health
  const checkTeamsHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/communication/health');
      const data = await response.json();
      
      if (data.services?.teams) {
        setHealth({
          connected: data.services.teams.status === 'healthy',
          lastSync: new Date().toISOString(),
          errors: data.services.teams.error ? [data.services.teams.error] : []
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Teams service health']
      });
    }
  }, []);

  // Load available teams
  const loadTeams = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/teams/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          include_private: config.settings.includePrivateChannels,
          limit: 50
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

  // Load channels for selected team
  const loadChannels = async () => {
    if (!selectedTeam) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/integrations/teams/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          team_id: selectedTeam,
          include_private: config.settings.includePrivateChannels,
          limit: 100
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

  // Load current user
  const loadCurrentUser = async () => {
    try {
      const response = await fetch('/api/integrations/teams/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setCurrentUser(data.user);
        if (data.user.tenantId) {
          updateConfig('tenantId', data.user.tenantId);
        }
      }
    } catch (err) {
      console.error('Error loading current user:', err);
    }
  };

  // Start Teams OAuth flow
  const startTeamsOAuth = async () => {
    try {
      const response = await fetch('/api/auth/teams/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: ['Channel.ReadBasic.All', 'ChannelMessage.Read.All', 'Chat.Read', 'User.Read.All', 'Team.ReadBasic.All']
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Open OAuth URL in popup
        const popup = window.open(
          data.authorization_url,
          'teams-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        // Listen for OAuth completion
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkTeamsAuthStatus();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Teams OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Teams OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Check Teams auth status
  const checkTeamsAuthStatus = async () => {
    try {
      const response = await fetch('/api/auth/teams/status', {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const data = await response.json();
      
      if (data.connected) {
        toast({
          title: 'Teams Connected',
          description: 'Successfully authenticated with Microsoft Teams',
          status: 'success',
          duration: 3000,
        });
        
        // Load teams, channels, and current user
        loadTeams();
        loadCurrentUser();
      } else {
        toast({
          title: 'Authentication Required',
          description: 'Please connect to Microsoft Teams first',
          status: 'warning',
          duration: 3000,
        });
      }
    } catch (err) {
      toast({
        title: 'Status Check Failed',
        description: 'Could not verify Teams connection',
        status: 'error',
        duration: 3000,
      });
    }
  };

  // Start Teams data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      teamsProcessed: 0,
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
        sourceType: 'teams',
        config: dataSourceConfig.settings,
        callback: (status: IngestionStatus) => {
          setIngestionStatus(status);
        }
      });

      if (ingestionResult.success) {
        toast({
          title: 'Teams Ingestion Completed',
          description: `Successfully processed ${ingestionResult.teamsProcessed} teams`,
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
        title: 'Teams Ingestion Failed',
        description: error.message,
        status: 'error',
        duration: 5000,
      });

      if (onError) {
        onError(error);
      }
    }
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

  // Handle team select
  const handleTeamSelect = (teamId: string) => {
    setSelectedTeam(teamId);
    loadChannels();
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
    checkTeamsHealth();
  }, []);

  useEffect(() => {
    if (selectedTeam) {
      loadChannels();
    }
  }, [selectedTeam]);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={ChatIcon} w={6} h={6} color="blue.500" />
            <Heading size="md">Microsoft Teams Integration</Heading>
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
                checkTeamsHealth();
                loadTeams();
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
                    src={currentUser.avatar}
                    size="md"
                  />
                  <VStack align="start" spacing={1}>
                    <Text fontWeight="bold">{currentUser.displayName}</Text>
                    <Text fontSize="sm" color="gray.600">{currentUser.userPrincipalName}</Text>
                    {currentUser.jobTitle && (
                      <Text fontSize="sm" color="gray.500">{currentUser.jobTitle}</Text>
                    )}
                    {currentUser.tenantId && (
                      <Badge size="sm" colorScheme="blue">Tenant: {currentUser.tenantId}</Badge>
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
                  Teams service {health.connected ? 'healthy' : 'unhealthy'}
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
                leftIcon={<ChatIcon />}
                onClick={startTeamsOAuth}
                width="full"
                size="lg"
              >
                Connect to Microsoft Teams
              </Button>
              <Text fontSize="sm" color="gray.600" textAlign="center">
                Click to authenticate with Microsoft Teams using OAuth 2.0
              </Text>
            </VStack>
          )}

          {/* Teams Selection */}
          {teams.length > 0 && (
            <FormControl>
              <FormLabel>Teams</FormLabel>
              <VStack align="start" spacing={3} maxH="300px" overflowY="auto">
                {teams.map((team) => (
                  <HStack key={team.id} justify="space-between" w="full">
                    <Checkbox
                      isChecked={config.settings.teams.includes(team.id)}
                      onChange={(e) => handleTeamToggle(team.id, e.target.checked)}
                    >
                      <VStack align="start" spacing={1}>
                        <Text fontWeight="medium">{team.displayName}</Text>
                        {team.description && (
                          <Text fontSize="sm" color="gray.600">{team.description}</Text>
                        )}
                        <HStack spacing={4}>
                          <Badge size="sm" colorScheme={team.visibility === 'public' ? 'green' : 'yellow'}>
                            {team.visibility}
                          </Badge>
                          {team.membersCount && (
                            <Badge size="sm" colorScheme="blue">
                              {team.membersCount} members
                            </Badge>
                          )}
                          {team.channelsCount && (
                            <Badge size="sm" colorScheme="purple">
                              {team.channelsCount} channels
                            </Badge>
                          )}
                        </HStack>
                      </VStack>
                    </Checkbox>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleTeamSelect(team.id)}
                      leftIcon={<ViewIcon />}
                    >
                      View Channels
                    </Button>
                  </HStack>
                ))}
              </VStack>
              <FormHelperText>
                Select teams to ingest data from
              </FormHelperText>
            </FormControl>
          )}

          {/* Channels Selection */}
          {channels.length > 0 && (
            <FormControl>
              <FormLabel>
                Channels from {selectedTeam ? teams.find(t => t.id === selectedTeam)?.displayName : 'Selected Team'}
              </FormLabel>
              <VStack align="start" spacing={2} maxH="250px" overflowY="auto">
                {channels.map((channel) => (
                  <Checkbox
                    key={channel.id}
                    isChecked={config.settings.channels.includes(channel.id)}
                    onChange={(e) => handleChannelToggle(channel.id, e.target.checked)}
                  >
                    <VStack align="start" spacing={1}>
                      <HStack>
                        <Text fontWeight="medium">{channel.displayName}</Text>
                        <Badge size="sm" colorScheme={
                          channel.membershipType === 'private' ? 'red' :
                          channel.membershipType === 'shared' ? 'yellow' : 'green'
                        }>
                          {channel.membershipType}
                        </Badge>
                      </HStack>
                      {channel.description && (
                        <Text fontSize="sm" color="gray.600">{channel.description}</Text>
                      )}
                    </VStack>
                  </Checkbox>
                ))}
              </VStack>
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
              {['messages', 'replies', 'mentions', 'files', 'reactions'].map((type) => (
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

              <FormControl>
                <FormLabel>Tenant ID</FormLabel>
                <Input
                  value={config.settings.tenantId}
                  onChange={(e) => updateConfig('tenantId', e.target.value)}
                  placeholder="Microsoft 365 Tenant ID"
                />
                <FormHelperText>
                  Required for Microsoft Graph API access
                </FormHelperText>
              </FormControl>
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
                    <Text>Ingesting Teams data...</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="blue"
                    w="full"
                  />
                  <Text fontSize="sm" color="gray.600">
                    Teams: {ingestionStatus.teamsProcessed} | 
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
                window.open('https://teams.microsoft.com', '_blank');
              }}
            >
              Open Teams
            </Button>

            <Button
              colorScheme="green"
              leftIcon={<AddIcon />}
              onClick={startIngestion}
              isDisabled={
                !health?.connected ||
                (config.settings.teams.length === 0 && config.settings.channels.length === 0) ||
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

export default TeamsManager;