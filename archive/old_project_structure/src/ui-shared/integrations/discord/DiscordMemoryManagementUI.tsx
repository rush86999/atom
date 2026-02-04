/**
 * Discord Memory Management UI Component
 * Complete user-controlled memory system for Discord integration
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Heading,
  Badge,
  Button,
  IconButton,
  Card,
  CardBody,
  CardHeader,
  Divider,
  FormControl,
  FormLabel,
  Switch,
  Select,
  NumberInput,
  NumberInputField,
  CheckboxGroup,
  Checkbox,
  Stack,
  Progress,
  useToast,
  Spinner,
  Tooltip,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  SimpleGrid,
  Icon,
  Flex,
  Alert,
  AlertIcon,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Tag,
  TagLabel,
  TagCloseButton,
  Input,
  InputGroup,
  InputRightElement,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Drawer,
  DrawerBody,
  DrawerFooter,
  DrawerHeader,
  DrawerOverlay,
  DrawerContent,
  DrawerCloseButton,
  useDisclosure
} from '@chakra-ui/react';
import {
  FiDatabase,
  FiSettings,
  FiRefreshCw,
  FiSearch,
  FiFilter,
  FiTrash2,
  FiDownload,
  FiUpload,
  FiClock,
  FiCheck,
  FiAlertTriangle,
  FiPlay,
  FiPause,
  FiStop,
  FiZap,
  FiZapOff,
  FiShield,
  FiUnlock,
  FiEye,
  FiEyeOff,
  FiList,
  FiGrid,
  FiCalendar,
  FiActivity,
  FiHardDrive,
  FiCpu,
  FiWifi,
  FiWifiOff,
  FiToggleLeft,
  FiToggleRight,
  FiInfo,
  FiEdit3,
  FiSave,
  FiX,
  FiPlus,
  FiMinus,
  FiBarChart2,
  FiUsers,
  FiMessageSquare,
  FiHash,
  FiFolder,
  FiLock
} from 'react-icons/fi';

import { discordSkills, discordUtils } from './skills/discordSkillsComplete';

interface DiscordMemorySettings {
  user_id: string;
  ingestion_enabled: boolean;
  sync_frequency: string;
  data_retention_days: number;
  include_guilds: string[];
  exclude_guilds: string[];
  include_channels: string[];
  exclude_channels: string[];
  include_dm_channels: boolean;
  include_private_channels: boolean;
  max_messages_per_channel: number;
  semantic_search_enabled: boolean;
  metadata_extraction_enabled: boolean;
  last_sync_timestamp?: string;
  next_sync_timestamp?: string;
  sync_in_progress: boolean;
  error_message?: string;
}

interface DiscordSyncStatus {
  user_id: string;
  ingestion_enabled: boolean;
  sync_frequency: string;
  sync_in_progress: boolean;
  last_sync_timestamp?: string;
  next_sync_timestamp?: string;
  should_sync_now: boolean;
  error_message?: string;
  stats: {
    total_messages_ingested: number;
    total_guilds_synced: number;
    total_channels_synced: number;
    failed_ingestions: number;
    last_ingestion_timestamp?: string;
    avg_messages_per_minute: number;
    storage_size_mb: number;
  };
  settings: {
    include_guilds: string[];
    exclude_guilds: string[];
    include_channels: string[];
    exclude_channels: string[];
    include_dm_channels: boolean;
    include_private_channels: boolean;
    max_messages_per_channel: number;
    semantic_search_enabled: boolean;
    metadata_extraction_enabled: boolean;
  };
}

interface DiscordGuild {
  id: string;
  name: string;
  icon_url: string;
  member_count: number;
  approximate_member_count: number;
  description: string;
  features: string[];
  premium_tier: number;
}

interface DiscordChannel {
  id: string;
  name: string;
  type: number;
  type_name: string;
  topic: string;
  nsfw: boolean;
  position: number;
  message_count: number;
  member_count: number;
  parent_id: string;
}

interface DiscordMemoryManagementUIProps {
  userId: string;
  className?: string;
  compact?: boolean;
  showAdvanced?: boolean;
  onSettingsUpdate?: (settings: DiscordMemorySettings) => void;
  onSyncTrigger?: (force: boolean) => void;
}

const DiscordMemoryManagementUI: React.FC<DiscordMemoryManagementUIProps> = ({
  userId,
  className = '',
  compact = false,
  showAdvanced = true,
  onSettingsUpdate,
  onSyncTrigger
}) => {
  const toast = useToast();
  const { isOpen: settingsOpen, onOpen: settingsOnOpen, onClose: settingsOnClose } = useDisclosure();
  const { isOpen: guildsOpen, onOpen: guildsOnOpen, onClose: guildsOnClose } = useDisclosure();
  const { isOpen: channelsOpen, onOpen: channelsOnOpen, onClose: channelsOnClose } = useDisclosure();

  // State management
  const [loading, setLoading] = useState(false);
  const [settings, setSettings] = useState<DiscordMemorySettings | null>(null);
  const [syncStatus, setSyncStatus] = useState<DiscordSyncStatus | null>(null);
  const [availableGuilds, setAvailableGuilds] = useState<DiscordGuild[]>([]);
  const [availableChannels, setAvailableChannels] = useState<DiscordChannel[]>([]);
  const [selectedGuildId, setSelectedGuildId] = useState<string>('');
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [filterView, setFilterView] = useState<'settings' | 'status' | 'stats'>('settings');
  const [tempSettings, setTempSettings] = useState<DiscordMemorySettings | null>(null);
  const [hasChanges, setHasChanges] = useState(false);

  // Fetch functions
  const fetchSettings = useCallback(async () => {
    try {
      const response = await fetch('/api/discord/memory/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setSettings(data.settings);
        setTempSettings(data.settings);
      }
    } catch (error) {
      console.error('Error fetching Discord memory settings:', error);
    }
  }, [userId]);

  const fetchSyncStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/discord/memory/status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setSyncStatus(data.sync_status);
      }
    } catch (error) {
      console.error('Error fetching Discord sync status:', error);
    }
  }, [userId]);

  const fetchAvailableGuilds = useCallback(async () => {
    try {
      const response = await fetch('/api/discord/memory/guilds', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setAvailableGuilds(data.guilds);
      }
    } catch (error) {
      console.error('Error fetching available Discord guilds:', error);
    }
  }, [userId]);

  const fetchAvailableChannels = useCallback(async (guildId: string) => {
    try {
      const response = await fetch('/api/discord/memory/channels', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          guild_id: guildId 
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setAvailableChannels(data.channels);
      }
    } catch (error) {
      console.error('Error fetching available Discord channels:', error);
    }
  }, [userId]);

  // Update settings
  const updateSettings = useCallback(async (newSettings: DiscordMemorySettings) => {
    try {
      const response = await fetch('/api/discord/memory/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId, ...newSettings }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setSettings(data.settings);
        setTempSettings(data.settings);
        setHasChanges(false);
        onSettingsUpdate?.(data.settings);
        
        toast({
          title: 'Settings Updated',
          description: 'Discord memory settings saved successfully',
          status: 'success',
          duration: 3000,
        });
      }
    } catch (error) {
      console.error('Error updating Discord settings:', error);
      toast({
        title: 'Update Failed',
        description: 'Failed to update Discord memory settings',
        status: 'error',
        duration: 5000,
      });
    }
  }, [userId, onSettingsUpdate, toast]);

  // Start sync
  const startSync = useCallback(async (force: boolean = false) => {
    try {
      setSyncInProgress(true);
      setSyncResult(null);
      
      const response = await fetch('/api/discord/memory/sync', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          force_sync: force
        }),
      });

      const data = await response.json();
      
      setSyncResult(data);
      
      if (data.ok) {
        // Refresh sync status
        await fetchSyncStatus();
        
        toast({
          title: 'Sync Complete',
          description: `Synced ${data.sync_result?.messages_ingested || 0} messages from ${data.sync_result?.guilds_synced || 0} servers`,
          status: 'success',
          duration: 5000,
        });
      } else {
        toast({
          title: 'Sync Failed',
          description: data.error || 'Failed to sync Discord data',
          status: 'error',
          duration: 5000,
        });
      }
      
      onSyncTrigger?.(force);
      
    } catch (error) {
      console.error('Error starting Discord sync:', error);
      toast({
        title: 'Sync Error',
        description: 'Failed to start Discord sync',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setSyncInProgress(false);
    }
  }, [userId, fetchSyncStatus, onSyncTrigger, toast]);

  // Delete user data
  const deleteUserData = useCallback(async () => {
    if (!window.confirm('Are you sure you want to delete all Discord memory data? This action cannot be undone.')) {
      return;
    }
    
    try {
      const response = await fetch('/api/discord/memory/delete', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          confirm: true
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        await fetchSettings();
        await fetchSyncStatus();
        
        toast({
          title: 'Data Deleted',
          description: 'All Discord memory data has been deleted',
          status: 'success',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error deleting Discord user data:', error);
      toast({
        title: 'Delete Failed',
        description: 'Failed to delete Discord data',
        status: 'error',
        duration: 5000,
      });
    }
  }, [userId, fetchSettings, fetchSyncStatus, toast]);

  // Handle temp settings changes
  const handleTempSettingChange = useCallback((field: string, value: any) => {
    if (!tempSettings) return;
    
    const newSettings = { ...tempSettings, [field]: value };
    setTempSettings(newSettings);
    setHasChanges(JSON.stringify(newSettings) !== JSON.stringify(settings));
  }, [tempSettings, settings]);

  // Handle guild selection changes
  const handleGuildSelection = useCallback((guildId: string, checked: boolean) => {
    if (!tempSettings) return;
    
    const includeGuilds = [...(tempSettings.include_guilds || [])];
    const excludeGuilds = [...(tempSettings.exclude_guilds || [])];
    
    if (checked) {
      // Add to include list, remove from exclude
      if (!includeGuilds.includes(guildId)) {
        includeGuilds.push(guildId);
      }
      const excludeIndex = excludeGuilds.indexOf(guildId);
      if (excludeIndex > -1) {
        excludeGuilds.splice(excludeIndex, 1);
      }
    } else {
      // Add to exclude list, remove from include
      if (!excludeGuilds.includes(guildId)) {
        excludeGuilds.push(guildId);
      }
      const includeIndex = includeGuilds.indexOf(guildId);
      if (includeIndex > -1) {
        includeGuilds.splice(includeIndex, 1);
      }
    }
    
    handleTempSettingChange('include_guilds', includeGuilds);
    handleTempSettingChange('exclude_guilds', excludeGuilds);
  }, [tempSettings, handleTempSettingChange]);

  // Handle channel selection changes
  const handleChannelSelection = useCallback((channelId: string, checked: boolean) => {
    if (!tempSettings) return;
    
    const includeChannels = [...(tempSettings.include_channels || [])];
    const excludeChannels = [...(tempSettings.exclude_channels || [])];
    
    if (checked) {
      // Add to include list, remove from exclude
      if (!includeChannels.includes(channelId)) {
        includeChannels.push(channelId);
      }
      const excludeIndex = excludeChannels.indexOf(channelId);
      if (excludeIndex > -1) {
        excludeChannels.splice(excludeIndex, 1);
      }
    } else {
      // Add to exclude list, remove from include
      if (!excludeChannels.includes(channelId)) {
        excludeChannels.push(channelId);
      }
      const includeIndex = includeChannels.indexOf(channelId);
      if (includeIndex > -1) {
        includeChannels.splice(includeIndex, 1);
      }
    }
    
    handleTempSettingChange('include_channels', includeChannels);
    handleTempSettingChange('exclude_channels', excludeChannels);
  }, [tempSettings, handleTempSettingChange]);

  // Effects
  useEffect(() => {
    if (userId) {
      fetchSettings();
      fetchSyncStatus();
    }
  }, [userId, fetchSettings, fetchSyncStatus]);

  // Auto-refresh sync status
  useEffect(() => {
    const interval = setInterval(() => {
      fetchSyncStatus();
    }, 30000); // Every 30 seconds
    
    return () => clearInterval(interval);
  }, [fetchSyncStatus]);

  // Memoized components
  const syncStatusCard = useMemo(() => {
    if (!syncStatus) return null;
    
    const { stats, sync_in_progress, should_sync_now } = syncStatus;
    const progress = stats.total_messages_ingested > 0 ? 
      (stats.total_messages_ingested / (stats.total_messages_ingested + stats.failed_ingestions)) * 100 : 0;
    
    return (
      <Card variant="outline">
        <CardHeader>
          <HStack justify="space-between">
            <HStack spacing={3}>
              <Icon as={FiActivity} boxSize={5} color="discord.500" />
              <Heading size="sm">Sync Status</Heading>
              {sync_in_progress && (
                <Spinner size="sm" />
              )}
              {should_sync_now && !sync_in_progress && (
                <Badge colorScheme="orange" variant="outline">
                  Sync Available
                </Badge>
              )}
            </HStack>
            
            <HStack spacing={2}>
              <Button
                size="sm"
                variant="outline"
                onClick={() => fetchSyncStatus()}
                leftIcon={<FiRefreshCw />}
              >
                Refresh
              </Button>
              
              <Button
                size="sm"
                colorScheme="discord"
                onClick={() => startSync()}
                isLoading={syncInProgress || sync_in_progress}
                leftIcon={sync_in_progress ? <FiPause /> : <FiPlay />}
                disabled={sync_in_progress}
              >
                {sync_in_progress ? 'Syncing' : 'Start Sync'}
              </Button>
              
              {showAdvanced && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => startSync(true)}
                  isLoading={syncInProgress}
                  leftIcon={<FiZap />}
                >
                  Force
                </Button>
              )}
            </HStack>
          </HStack>
        </CardHeader>
        
        <CardBody>
          <VStack spacing={4} align="stretch">
            {/* Progress Bar */}
            <Box>
              <HStack justify="space-between" mb={2}>
                <Text fontSize="sm" fontWeight="medium">Sync Progress</Text>
                <Text fontSize="xs" color="gray.500">{progress.toFixed(1)}%</Text>
              </HStack>
              <Progress 
                value={progress} 
                size="sm" 
                colorScheme={progress >= 90 ? 'green' : progress >= 70 ? 'yellow' : 'red'}
              />
            </Box>
            
            {/* Stats Grid */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
              <VStack align="start" spacing={1}>
                <Text fontSize="xs" color="gray.500">Messages</Text>
                <Text fontSize="lg" fontWeight="bold">
                  {stats.total_messages_ingested.toLocaleString()}
                </Text>
              </VStack>
              
              <VStack align="start" spacing={1}>
                <Text fontSize="xs" color="gray.500">Servers</Text>
                <Text fontSize="lg" fontWeight="bold">
                  {stats.total_guilds_synced}
                </Text>
              </VStack>
              
              <VStack align="start" spacing={1}>
                <Text fontSize="xs" color="gray.500">Channels</Text>
                <Text fontSize="lg" fontWeight="bold">
                  {stats.total_channels_synced}
                </Text>
              </VStack>
              
              <VStack align="start" spacing={1}>
                <Text fontSize="xs" color="gray.500">Storage</Text>
                <Text fontSize="lg" fontWeight="bold">
                  {stats.storage_size_mb.toFixed(1)} MB
                </Text>
              </VStack>
            </SimpleGrid>
            
            {/* Last Sync Info */}
            <HStack justify="space-between" fontSize="sm" color="gray.600">
              <Text>Last Sync:</Text>
              <Text>
                {stats.last_ingestion_timestamp 
                  ? discordUtils.formatDateTime(stats.last_ingestion_timestamp)
                  : 'Never'
                }
              </Text>
            </HStack>
            
            {/* Error Message */}
            {syncStatus.error_message && (
              <Alert status="error">
                <AlertIcon />
                <Text fontSize="sm">{syncStatus.error_message}</Text>
              </Alert>
            )}
            
            {/* Sync Result */}
            {syncResult && (
              <Alert 
                status={syncResult.ok ? 'success' : 'error'}
                variant="subtle"
              >
                <AlertIcon />
                <VStack align="start" spacing={1}>
                  <Text fontSize="sm" fontWeight="medium">
                    {syncResult.ok ? 'Sync Completed' : 'Sync Failed'}
                  </Text>
                  {syncResult.ok && (
                    <Text fontSize="xs">
                      {syncResult.sync_result?.messages_ingested || 0} messages from {syncResult.sync_result?.guilds_synced || 0} servers
                    </Text>
                  )}
                  {syncResult.error && (
                    <Text fontSize="xs">{syncResult.error}</Text>
                  )}
                </VStack>
              </Alert>
            )}
          </VStack>
        </CardBody>
      </Card>
    );
  }, [syncStatus, syncInProgress, syncResult, showAdvanced, fetchSyncStatus, startSync]);

  const settingsCard = useMemo(() => {
    if (!tempSettings) return null;
    
    return (
      <Card variant="outline">
        <CardHeader>
          <HStack justify="space-between">
            <HStack spacing={3}>
              <Icon as={FiSettings} boxSize={5} color="discord.500" />
              <Heading size="sm">Memory Settings</Heading>
              {hasChanges && (
                <Badge colorScheme="orange" variant="outline">
                  Unsaved Changes
                </Badge>
              )}
            </HStack>
            
            <HStack spacing={2}>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setTempSettings(settings)}
                disabled={!hasChanges}
                leftIcon={<FiX />}
              >
                Reset
              </Button>
              
              <Button
                size="sm"
                colorScheme="discord"
                onClick={() => settingsOnOpen()}
                leftIcon={<FiEdit3 />}
              >
                Edit
              </Button>
            </HStack>
          </HStack>
        </CardHeader>
        
        <CardBody>
          <VStack spacing={4} align="stretch">
            {/* Quick Settings */}
            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
              <FormControl display="flex" alignItems="center" justifyContent="space-between">
                <FormLabel htmlFor="ingestion-enabled" mb="0">
                  Memory Ingestion
                </FormLabel>
                <Switch
                  id="ingestion-enabled"
                  isChecked={tempSettings.ingestion_enabled}
                  onChange={(e) => handleTempSettingChange('ingestion_enabled', e.target.checked)}
                />
              </FormControl>
              
              <FormControl display="flex" alignItems="center" justifyContent="space-between">
                <FormLabel htmlFor="sync-frequency" mb="0">
                  Sync Frequency
                </FormLabel>
                <Select
                  value={tempSettings.sync_frequency}
                  onChange={(e) => handleTempSettingChange('sync_frequency', e.target.value)}
                  size="sm"
                  w="120px"
                >
                  <option value="real-time">Real-time</option>
                  <option value="hourly">Hourly</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="manual">Manual</option>
                </Select>
              </FormControl>
              
              <FormControl display="flex" alignItems="center" justifyContent="space-between">
                <FormLabel htmlFor="dm-channels" mb="0">
                  Include DMs
                </FormLabel>
                <Switch
                  id="dm-channels"
                  isChecked={tempSettings.include_dm_channels}
                  onChange={(e) => handleTempSettingChange('include_dm_channels', e.target.checked)}
                />
              </FormControl>
              
              <FormControl display="flex" alignItems="center" justifyContent="space-between">
                <FormLabel htmlFor="private-channels" mb="0">
                  Include Private
                </FormLabel>
                <Switch
                  id="private-channels"
                  isChecked={tempSettings.include_private_channels}
                  onChange={(e) => handleTempSettingChange('include_private_channels', e.target.checked)}
                />
              </FormControl>
            </SimpleGrid>
            
            {/* Channel/Server Settings */}
            <HStack spacing={3}>
              <Button
                variant="outline"
                size="sm"
                leftIcon={<FiUsers />}
                onClick={() => {
                  fetchAvailableGuilds();
                  guildsOnOpen();
                }}
              >
                Manage Servers ({tempSettings.include_guilds?.length || 0})
              </Button>
              
              <Button
                variant="outline"
                size="sm"
                leftIcon={<FiHash />}
                onClick={() => {
                  if (selectedGuildId) {
                    fetchAvailableChannels(selectedGuildId);
                  }
                  channelsOnOpen();
                }}
                isDisabled={!selectedGuildId}
              >
                Manage Channels ({tempSettings.include_channels?.length || 0})
              </Button>
              
              <Box flex={1} />
              
              {showAdvanced && (
                <Button
                  variant="outline"
                  size="sm"
                  colorScheme="red"
                  leftIcon={<FiTrash2 />}
                  onClick={deleteUserData}
                >
                  Delete All Data
                </Button>
              )}
            </HStack>
          </VStack>
        </CardBody>
      </Card>
    );
  }, [tempSettings, settings, hasChanges, handleTempSettingChange, selectedGuildId, 
      fetchAvailableGuilds, fetchAvailableChannels, guildsOnOpen, channelsOnOpen, showAdvanced, deleteUserData]);

  const statsCard = useMemo(() => {
    if (!syncStatus) return null;
    
    return (
      <Card variant="outline">
        <CardHeader>
          <HStack spacing={3}>
            <Icon as={FiBarChart2} boxSize={5} color="discord.500" />
            <Heading size="sm">Statistics</Heading>
          </HStack>
        </CardHeader>
        
        <CardBody>
          <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
            <VStack align="start" spacing={1}>
              <Text fontSize="xs" color="gray.500">Total Messages</Text>
              <Text fontSize="2xl" fontWeight="bold">
                {syncStatus.stats.total_messages_ingested.toLocaleString()}
              </Text>
              <Progress 
                value={Math.min((syncStatus.stats.total_messages_ingested / 1000000) * 100, 100)} 
                size="xs" 
                w="full"
                mt={2}
              />
              <Text fontSize="xs" color="gray.500">of 1M limit</Text>
            </VStack>
            
            <VStack align="start" spacing={1}>
              <Text fontSize="xs" color="gray.500">Storage Used</Text>
              <Text fontSize="2xl" fontWeight="bold">
                {syncStatus.stats.storage_size_mb.toFixed(1)} MB
              </Text>
              <Progress 
                value={Math.min((syncStatus.stats.storage_size_mb / 1024) * 100, 100)} 
                size="xs" 
                w="full"
                mt={2}
              />
              <Text fontSize="xs" color="gray.500">of 1GB limit</Text>
            </VStack>
            
            <VStack align="start" spacing={1}>
              <Text fontSize="xs" color="gray.500">Avg Speed</Text>
              <Text fontSize="2xl" fontWeight="bold">
                {syncStatus.stats.avg_messages_per_minute.toFixed(1)}
              </Text>
              <Text fontSize="xs" color="gray.500">messages/min</Text>
            </VStack>
          </SimpleGrid>
        </CardBody>
      </Card>
    );
  }, [syncStatus]);

  if (loading) {
    return (
      <Box className={className} p={6}>
        <VStack spacing={4} align="center">
          <Spinner size="xl" />
          <Text>Loading Discord memory settings...</Text>
        </VStack>
      </Box>
    );
  }

  if (compact) {
    return (
      <Box className={className}>
        <VStack spacing={4} align="stretch">
          {syncStatusCard}
        </VStack>
      </Box>
    );
  }

  return (
    <Box className={className} p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={3}>
            <Icon as={FiDatabase} boxSize={6} color="discord.500" />
            <Box>
              <Heading size="lg">Discord Memory Management</Heading>
              <Text fontSize="sm" color="gray.600">
                Control your Discord data ingestion and memory settings
              </Text>
            </Box>
          </HStack>
          
          <Button
            variant="outline"
            onClick={() => fetchSettings()}
            leftIcon={<FiRefreshCw />}
          >
            Refresh
          </Button>
        </HStack>

        {/* Main Content */}
        <VStack spacing={6} align="stretch">
          {syncStatusCard}
          {settingsCard}
          {showAdvanced && statsCard}
        </VStack>
      </VStack>

      {/* Settings Modal */}
      <Modal 
        isOpen={settingsOpen} 
        onClose={settingsOnClose}
        size="2xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiSettings} />
              <Text>Discord Memory Settings</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {tempSettings && (
              <VStack spacing={6} align="stretch">
                {/* General Settings */}
                <Accordion allowToggle defaultIndex={[0]}>
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">General Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-ingestion-enabled">
                            Enable Discord Memory
                          </FormLabel>
                          <Switch
                            id="modal-ingestion-enabled"
                            isChecked={tempSettings.ingestion_enabled}
                            onChange={(e) => handleTempSettingChange('ingestion_enabled', e.target.checked)}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Sync Frequency</FormLabel>
                          <Select
                            value={tempSettings.sync_frequency}
                            onChange={(e) => handleTempSettingChange('sync_frequency', e.target.value)}
                          >
                            <option value="real-time">Real-time</option>
                            <option value="hourly">Hourly</option>
                            <option value="daily">Daily</option>
                            <option value="weekly">Weekly</option>
                            <option value="manual">Manual</option>
                          </Select>
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Data Retention (Days)</FormLabel>
                          <NumberInput
                            value={tempSettings.data_retention_days}
                            min={1}
                            max={3650}
                            onChange={(value) => handleTempSettingChange('data_retention_days', parseInt(value) || 365)}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* Channel Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Channel Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-dm-channels">
                            Include DM Channels
                          </FormLabel>
                          <Switch
                            id="modal-dm-channels"
                            isChecked={tempSettings.include_dm_channels}
                            onChange={(e) => handleTempSettingChange('include_dm_channels', e.target.checked)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-private-channels">
                            Include Private Channels
                          </FormLabel>
                          <Switch
                            id="modal-private-channels"
                            isChecked={tempSettings.include_private_channels}
                            onChange={(e) => handleTempSettingChange('include_private_channels', e.target.checked)}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Max Messages per Channel</FormLabel>
                          <NumberInput
                            value={tempSettings.max_messages_per_channel}
                            min={100}
                            max={100000}
                            onChange={(value) => handleTempSettingChange('max_messages_per_channel', parseInt(value) || 10000)}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* Advanced Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Advanced Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-semantic-search">
                            Enable Semantic Search
                          </FormLabel>
                          <Switch
                            id="modal-semantic-search"
                            isChecked={tempSettings.semantic_search_enabled}
                            onChange={(e) => handleTempSettingChange('semantic_search_enabled', e.target.checked)}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="modal-metadata-extraction">
                            Enable Metadata Extraction
                          </FormLabel>
                          <Switch
                            id="modal-metadata-extraction"
                            isChecked={tempSettings.metadata_extraction_enabled}
                            onChange={(e) => handleTempSettingChange('metadata_extraction_enabled', e.target.checked)}
                          />
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                </Accordion>
              </VStack>
            )}
          </ModalBody>
          
          <ModalFooter>
            <HStack spacing={3}>
              <Button
                variant="outline"
                onClick={() => setTempSettings(settings)}
                disabled={!hasChanges}
              >
                Reset
              </Button>
              
              <Button
                variant="outline"
                onClick={settingsOnClose}
              >
                Cancel
              </Button>
              
              <Button
                colorScheme="discord"
                onClick={() => {
                  updateSettings(tempSettings!);
                  settingsOnClose();
                }}
                disabled={!hasChanges || !tempSettings}
              >
                Save Changes
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Guilds Modal */}
      <Modal 
        isOpen={guildsOpen} 
        onClose={guildsOnClose}
        size="2xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiUsers} />
              <Text>Manage Discord Servers</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <InputGroup>
                  <Input
                    placeholder="Search servers..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  <InputRightElement>
                    <Icon as={FiSearch} color="gray.400" />
                  </InputRightElement>
                </InputGroup>
              </FormControl>
              
              {availableGuilds
                .filter(guild => 
                  searchQuery === '' || 
                  guild.name.toLowerCase().includes(searchQuery.toLowerCase())
                )
                .map(guild => {
                  const isIncluded = tempSettings?.include_guilds?.includes(guild.id) || false;
                  const isExcluded = tempSettings?.exclude_guilds?.includes(guild.id) || false;
                  
                  return (
                    <Card key={guild.id} variant={isIncluded ? 'solid' : 'outline'}>
                      <CardBody>
                        <HStack justify="space-between">
                          <HStack spacing={3}>
                            {guild.icon_url && (
                              <Image 
                                src={guild.icon_url} 
                                alt={guild.name}
                                boxSize={8}
                                borderRadius="full"
                              />
                            )}
                            <VStack align="start" spacing={0}>
                              <Text fontWeight="medium">{guild.name}</Text>
                              <Text fontSize="xs" color="gray.500">
                                {guild.member_count || guild.approximate_member_count || 0} members
                              </Text>
                            </VStack>
                          </HStack>
                          
                          <Switch
                            isChecked={isIncluded}
                            onChange={(e) => handleGuildSelection(guild.id, e.target.checked)}
                          />
                        </HStack>
                      </CardBody>
                    </Card>
                  );
                })
              }
            </VStack>
          </ModalBody>
          
          <ModalFooter>
            <Button
              variant="outline"
              onClick={guildsOnClose}
            >
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Channels Modal */}
      <Modal 
        isOpen={channelsOpen} 
        onClose={channelsOnClose}
        size="2xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiHash} />
              <Text>Manage Discord Channels</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <Select
                  value={selectedGuildId}
                  onChange={(e) => {
                    setSelectedGuildId(e.target.value);
                    fetchAvailableChannels(e.target.value);
                  }}
                  placeholder="Select a server first"
                >
                  {availableGuilds.map(guild => (
                    <option key={guild.id} value={guild.id}>
                      {guild.name}
                    </option>
                  ))}
                </Select>
              </FormControl>
              
              {availableChannels
                .filter(channel => channel.type === 0) // Text channels only
                .map(channel => {
                  const isIncluded = tempSettings?.include_channels?.includes(channel.id) || false;
                  
                  return (
                    <Card key={channel.id} variant={isIncluded ? 'solid' : 'outline'}>
                      <CardBody>
                        <HStack justify="space-between">
                          <HStack spacing={3}>
                            <Icon as={FiHash} boxSize={4} />
                            <VStack align="start" spacing={0}>
                              <Text fontWeight="medium">{channel.name}</Text>
                              {channel.topic && (
                                <Text fontSize="xs" color="gray.500" noOfLines={1}>
                                  {channel.topic}
                                </Text>
                              )}
                            </VStack>
                          </HStack>
                          
                          <Switch
                            isChecked={isIncluded}
                            onChange={(e) => handleChannelSelection(channel.id, e.target.checked)}
                          />
                        </HStack>
                      </CardBody>
                    </Card>
                  );
                })
              }
            </VStack>
          </ModalBody>
          
          <ModalFooter>
            <Button
              variant="outline"
              onClick={channelsOnClose}
            >
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default DiscordMemoryManagementUI;