/**
 * Microsoft Teams Data Source Component
 * Teams-specific data ingestion for ATOM pipeline
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Checkbox,
  Select,
  Input,
  FormControl,
  FormLabel,
  FormHelperText,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Stack,
  Badge,
  Progress,
  Alert,
  AlertIcon,
  Divider,
  useToast,
  Collapse,
  Flex,
  Icon,
  Tooltip,
} from '@chakra-ui/react';
import {
  SearchIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  ViewIcon,
  CopyIcon,
  DownloadIcon,
  RepeatIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface ATOMTeamsDataSourceProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
}

export const ATOMTeamsDataSource: React.FC<ATOMTeamsDataSourceProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Microsoft Teams',
    platform: 'teams',
    enabled: true,
    settings: {
      teams: [],
      channels: [],
      messageTypes: ['chat', 'meetings', 'files'],
      dateRange: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
        end: new Date(),
      },
      includeAttachments: true,
      maxMessages: 1000,
      realTimeSync: false,
      syncFrequency: 'hourly',
    }
  });

  const [teams, setTeams] = useState<any[]>([]);
  const [channels, setChannels] = useState<any[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    messagesProcessed: 0,
    errors: []
  });

  const toast = useToast();

  // Check Teams service health
  const checkTeamsHealth = async () => {
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
  };

  // Load available teams
  const loadTeams = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/communication/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'current-user', // Replace with actual user ID
          platforms: ['teams']
        })
      });
      
      const data = await response.json();
      
      if (data.ok && data.teams) {
        setTeams(data.teams.filter((team: any) => team.platform === 'teams'));
      } else {
        setError(data.error || 'Failed to load Teams');
      }
    } catch (err) {
      setError('Network error loading Teams');
    } finally {
      setLoading(false);
    }
  };

  // Load channels for selected team
  const loadChannels = async (teamId: string) => {
    if (!teamId) return;
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('/api/communication/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'current-user',
          platforms: ['teams'],
          team_id: teamId
        })
      });
      
      const data = await response.json();
      
      if (data.ok && data.channels) {
        setChannels(data.channels.filter((channel: any) => channel.platform === 'teams'));
      } else {
        setError(data.error || 'Failed to load Teams channels');
      }
    } catch (err) {
      setError('Network error loading channels');
    } finally {
      setLoading(false);
    }
  };

  // Start Teams data ingestion
  const startIngestion = async () => {
    setIngestionStatus(prev => ({
      ...prev,
      running: true,
      progress: 0,
      messagesProcessed: 0,
      errors: []
    }));

    try {
      // Configure the data source in ATOM pipeline
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
          title: 'Teams ingestion completed',
          description: `Successfully processed ${ingestionResult.messagesProcessed} messages`,
          status: 'success',
          duration: 5000,
          isClosable: true,
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
        title: 'Teams ingestion failed',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });

      if (onError) {
        onError(error);
      }
    }
  };

  // Handle team selection
  const handleTeamSelect = (teamId: string) => {
    setSelectedTeam(teamId);
    loadChannels(teamId);
    
    // Update config
    setConfig(prev => ({
      ...prev,
      settings: {
        ...prev.settings,
        teams: [teamId],
        channels: []
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
    loadTeams();
  }, []);

  return (
    <Card>
      <CardHeader>
        <HStack justify="space-between">
          <Heading size="md">Microsoft Teams Data Source</Heading>
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
              onClick={loadTeams}
              isLoading={loading}
            >
              Refresh
            </Button>
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={6} align="stretch">
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

          {/* Team Selection */}
          <FormControl>
            <FormLabel>Select Teams/Workspaces</FormLabel>
            <Select
              placeholder="Choose a team to sync"
              value={selectedTeam}
              onChange={(e) => handleTeamSelect(e.target.value)}
              isDisabled={loading || teams.length === 0}
            >
              {teams.map((team) => (
                <option key={team.id} value={team.id}>
                  {team.name} ({team.platform})
                </option>
              ))}
            </Select>
            <FormHelperText>
              Select the Microsoft Teams workspace to ingest data from
            </FormHelperText>
          </FormControl>

          {/* Channel Selection */}
          {channels.length > 0 && (
            <FormControl>
              <FormLabel>Select Channels</FormLabel>
              <VStack align="start" spacing={2}>
                {channels.map((channel) => (
                  <Checkbox
                    key={channel.id}
                    isChecked={config.settings.channels.includes(channel.id)}
                    onChange={(e) => handleChannelToggle(channel.id, e.target.checked)}
                  >
                    <HStack>
                      <Text>{channel.name}</Text>
                      {channel.isPrivate && (
                        <Badge size="sm" colorScheme="yellow">Private</Badge>
                      )}
                    </HStack>
                  </Checkbox>
                ))}
              </VStack>
            </FormControl>
          )}

          <Divider />

          {/* Message Types */}
          <FormControl>
            <FormLabel>Message Types</FormLabel>
            <Stack direction="row" spacing={4}>
              {['chat', 'meetings', 'files'].map((type) => (
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

              <Checkbox
                isChecked={config.settings.includeAttachments}
                onChange={(e) => updateConfig('includeAttachments', e.target.checked)}
              >
                Include file attachments
              </Checkbox>
            </VStack>
          </Collapse>

          <Button
            variant="outline"
            leftIcon={<ViewIcon />}
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
                    Messages processed: {ingestionStatus.messagesProcessed}
                  </Text>
                </VStack>
              </CardBody>
            </Card>
          )}

          {/* Action Buttons */}
          <HStack justify="space-between" w="full">
            <Button
              variant="outline"
              leftIcon={<CopyIcon />}
              onClick={() => {
                // Copy configuration to clipboard
                navigator.clipboard.writeText(JSON.stringify(config, null, 2));
                toast({
                  title: 'Configuration copied',
                  status: 'success',
                  duration: 2000,
                });
              }}
            >
              Copy Config
            </Button>

            <Button
              colorScheme="blue"
              leftIcon={<DownloadIcon />}
              onClick={startIngestion}
              isDisabled={
                !health?.connected ||
                !selectedTeam ||
                config.settings.channels.length === 0 ||
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

export default ATOMTeamsDataSource;