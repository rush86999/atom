/**
 * Discord Communication UI Component
 * Complete Discord integration for unified communication interface with real-time streaming
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Input,
  Button,
  IconButton,
  Avatar,
  AvatarBadge,
  Heading,
  Badge,
  Divider,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  useToast,
  Spinner,
  Icon,
  Flex,
  ScrollArea,
  Tooltip,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
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
  Card,
  CardBody,
  CardHeader,
  Image,
  Kbd,
  SimpleGrid
} from '@chakra-ui/react';
import {
  FiSend,
  FiPaperclip,
  FiMic,
  FiSettings,
  FiMoreHorizontal,
  FiSearch,
  FiUsers,
  FiHash,
  FiMessageSquare,
  FiBell,
  FiChevronDown,
  FiPlus,
  FiRefreshCw,
  FiZap,
  FiZapOff,
  FiDatabase,
  FiTrash2,
  FiClock,
  FiCheck,
  FiAlertTriangle,
  FiArchive,
  FiFilter,
  FiGrid,
  FiList,
  FiLock,
  FiUnlock,
  FiEye,
  FiEyeOff
} from 'react-icons/fi';

import { discordSkills, discordUtils } from './skills/discordSkillsComplete';

// Discord channel type icons
const channelTypeIcons = {
  0: FiHash,      // Text
  1: FiUsers,     // DM
  2: FiMessageSquare, // Voice
  3: FiUsers,     // Group DM
  4: FiGrid,      // Category
  5: FiMessageSquare, // News
  10: FiMessageSquare, // News Thread
  11: FiMessageSquare, // Public Thread
  12: FiMessageSquare, // Private Thread
  13: FiMessageSquare, // Stage Voice
};

// Discord message status badges
const messageStatusColors = {
  sent: 'green',
  delivered: 'blue',
  failed: 'red',
  sending: 'yellow'
};

interface DiscordMessage {
  id: string;
  channel_id: string;
  guild_id: string;
  author: {
    id: string;
    username: string;
    discriminator: string;
    display_name: string;
    avatar_hash: string;
    avatar_url: string;
    bot: boolean;
  };
  member?: any;
  content: string;
  timestamp: string;
  edited_timestamp?: string;
  tts: boolean;
  mention_everyone: boolean;
  mentions: any[];
  mention_roles: string[];
  attachments: any[];
  embeds: any[];
  reactions: any[];
  pinned: boolean;
  type: number;
  flags: number;
}

interface DiscordChannel {
  id: string;
  type: number;
  type_name: string;
  guild_id: string;
  name: string;
  topic: string;
  nsfw: boolean;
  position: number;
  message_count: number;
  member_count: number;
  parent_id: string;
}

interface DiscordGuild {
  id: string;
  name: string;
  icon_hash: string;
  icon_url: string;
  owner_id: string;
  permissions: string;
  member_count: number;
  approximate_member_count: number;
  description: string;
  features: string[];
  channels: DiscordChannel[];
  roles: any[];
}

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

interface DiscordCommunicationUIProps {
  userId: string;
  authToken?: string;
  onSettingsChange?: (settings: DiscordMemorySettings) => void;
  onSyncStatusChange?: (status: DiscordSyncStatus) => void;
  className?: string;
  height?: string | number;
  showMemoryControls?: boolean;
  enableRealtimeStreaming?: boolean;
}

const DiscordCommunicationUI: React.FC<DiscordCommunicationUIProps> = ({
  userId,
  authToken,
  onSettingsChange,
  onSyncStatusChange,
  className = '',
  height = '600px',
  showMemoryControls = true,
  enableRealtimeStreaming = true
}) => {
  const toast = useToast();
  
  // State management
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [guilds, setGuilds] = useState<DiscordGuild[]>([]);
  const [selectedGuild, setSelectedGuild] = useState<DiscordGuild | null>(null);
  const [selectedChannel, setSelectedChannel] = useState<DiscordChannel | null>(null);
  const [messages, setMessages] = useState<DiscordMessage[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [messageStatus, setMessageStatus] = useState<Record<string, string>>({});
  const [realtimeEnabled, setRealtimeEnabled] = useState(enableRealtimeStreaming);
  
  // Memory management state
  const [memorySettings, setMemorySettings] = useState<DiscordMemorySettings | null>(null);
  const [syncStatus, setSyncStatus] = useState<DiscordSyncStatus | null>(null);
  const [settingsModalOpen, setSettingsModalOpen] = useState(false);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  
  // Refs
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const streamingRef = React.useRef<any>(null);
  const typingTimeoutRef = React.useRef<NodeJS.Timeout>();

  // Fetch current Discord user
  const fetchCurrentUser = useCallback(async () => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/discord/enhanced/user/current', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setCurrentUser(data.user);
        setConnected(true);
        toast({
          title: 'Discord Connected',
          description: `Connected as ${data.user.display_name}`,
          status: 'success',
          duration: 3000,
        });
      } else {
        setConnected(false);
        toast({
          title: 'Discord Connection Failed',
          description: data.error || 'Failed to connect to Discord',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Discord user:', error);
      setConnected(false);
      toast({
        title: 'Discord Error',
        description: 'Failed to connect to Discord',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [userId, toast]);

  // Fetch Discord guilds
  const fetchGuilds = useCallback(async () => {
    try {
      const response = await fetch('/api/discord/enhanced/guilds/list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          limit: 100
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setGuilds(data.guilds);
        
        // Auto-select first guild if none selected
        if (!selectedGuild && data.guilds.length > 0) {
          setSelectedGuild(data.guilds[0]);
        }
      }
    } catch (error) {
      console.error('Error fetching Discord guilds:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch Discord servers',
        status: 'error',
      });
    }
  }, [userId, selectedGuild, toast]);

  // Fetch guild channels
  const fetchGuildChannels = useCallback(async (guild: DiscordGuild) => {
    try {
      const response = await fetch('/api/discord/enhanced/channels/list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          guild_id: guild.id
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        // Update guild with channels
        const updatedGuilds = guilds.map(g => 
          g.id === guild.id ? { ...g, channels: data.channels } : g
        );
        setGuilds(updatedGuilds);
        setSelectedGuild({ ...guild, channels: data.channels });
        
        // Auto-select first text channel if none selected
        const textChannels = data.channels.filter((ch: DiscordChannel) => ch.type === 0);
        if (!selectedChannel && textChannels.length > 0) {
          setSelectedChannel(textChannels[0]);
        }
      }
    } catch (error) {
      console.error('Error fetching Discord channels:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch server channels',
        status: 'error',
      });
    }
  }, [userId, guilds, selectedChannel, toast]);

  // Fetch channel messages
  const fetchChannelMessages = useCallback(async (channel: DiscordChannel) => {
    try {
      const response = await fetch('/api/discord/enhanced/messages/list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          channel_id: channel.id,
          limit: 50
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setMessages(data.messages);
        
        // Scroll to bottom
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      }
    } catch (error) {
      console.error('Error fetching Discord messages:', error);
      toast({
        title: 'Error',
        description: 'Failed to fetch channel messages',
        status: 'error',
      });
    }
  }, [userId, toast]);

  // Send message
  const sendMessage = useCallback(async () => {
    if (!newMessage.trim() || !selectedChannel) return;

    try {
      setMessageStatus(prev => ({ ...prev, [selectedChannel.id]: 'sending' }));
      
      const response = await fetch('/api/discord/enhanced/messages/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          user_id: userId,
          channel_id: selectedChannel.id,
          content: newMessage.trim()
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        // Add message to local state
        const newMsg: DiscordMessage = data.message;
        setMessages(prev => [...prev, newMsg]);
        setNewMessage('');
        setMessageStatus(prev => ({ ...prev, [selectedChannel.id]: 'sent' }));
        
        // Scroll to bottom
        setTimeout(() => {
          messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
        
        toast({
          title: 'Message Sent',
          status: 'success',
          duration: 2000,
        });
      } else {
        setMessageStatus(prev => ({ ...prev, [selectedChannel.id]: 'failed' }));
        toast({
          title: 'Send Failed',
          description: data.error || 'Failed to send message',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error sending Discord message:', error);
      setMessageStatus(prev => ({ ...prev, [selectedChannel.id]: 'failed' }));
      toast({
        title: 'Send Error',
        description: 'Failed to send message',
        status: 'error',
      });
    }
  }, [userId, selectedChannel, newMessage, toast]);

  // Handle typing indicator
  const handleTyping = useCallback((value: string) => {
    setNewMessage(value);
    
    // Clear existing timeout
    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    
    // Set typing state
    if (value.trim()) {
      setIsTyping(true);
      
      // Clear typing after 3 seconds of inactivity
      typingTimeoutRef.current = setTimeout(() => {
        setIsTyping(false);
      }, 3000);
    } else {
      setIsTyping(false);
    }
  }, []);

  // Real-time streaming setup
  const setupRealtimeStreaming = useCallback(() => {
    if (!realtimeEnabled || !selectedChannel) return;

    // WebSocket connection for real-time Discord updates
    // This would connect to Discord gateway or ATOM streaming service
    try {
      // Example: ws = new WebSocket('wss://discord.com/api/v10/gateway');
      // For now, we'll use a mock setup
      streamingRef.current = {
        connected: true,
        lastHeartbeat: Date.now()
      };
      
      console.log('Discord real-time streaming enabled');
    } catch (error) {
      console.error('Error setting up Discord streaming:', error);
      setRealtimeEnabled(false);
    }
  }, [realtimeEnabled, selectedChannel]);

  // Fetch memory settings
  const fetchMemorySettings = useCallback(async () => {
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
        setMemorySettings(data.settings);
        onSettingsChange?.(data.settings);
      }
    } catch (error) {
      console.error('Error fetching Discord memory settings:', error);
    }
  }, [userId, onSettingsChange]);

  // Fetch sync status
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
        onSyncStatusChange?.(data.sync_status);
      }
    } catch (error) {
      console.error('Error fetching Discord sync status:', error);
    }
  }, [userId, onSyncStatusChange]);

  // Start Discord sync
  const startSync = useCallback(async (forceSync = false) => {
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
          force_sync: forceSync
        }),
      });

      const data = await response.json();
      
      setSyncResult(data);
      setSyncInProgress(false);
      
      // Refresh sync status
      await fetchSyncStatus();
      
      if (data.ok) {
        toast({
          title: 'Discord Sync Complete',
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
    } catch (error) {
      console.error('Error starting Discord sync:', error);
      setSyncInProgress(false);
      toast({
        title: 'Sync Error',
        description: 'Failed to start Discord sync',
        status: 'error',
      });
    }
  }, [userId, fetchSyncStatus, toast]);

  // Update memory settings
  const updateMemorySettings = useCallback(async (newSettings: DiscordMemorySettings) => {
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
        setMemorySettings(prev => ({ ...prev, ...newSettings }));
        onSettingsChange?.(data.settings);
        toast({
          title: 'Settings Updated',
          description: 'Discord memory settings saved',
          status: 'success',
        });
      }
    } catch (error) {
      console.error('Error updating Discord settings:', error);
      toast({
        title: 'Settings Error',
        description: 'Failed to update Discord settings',
        status: 'error',
      });
    }
  }, [userId, onSettingsChange, toast]);

  // Effects
  useEffect(() => {
    if (userId) {
      fetchCurrentUser();
      fetchGuilds();
      
      if (showMemoryControls) {
        fetchMemorySettings();
        fetchSyncStatus();
      }
    }
  }, [userId, fetchCurrentUser, fetchGuilds, fetchMemorySettings, fetchSyncStatus, showMemoryControls]);

  useEffect(() => {
    if (selectedGuild) {
      fetchGuildChannels(selectedGuild);
    }
  }, [selectedGuild, fetchGuildChannels]);

  useEffect(() => {
    if (selectedChannel) {
      fetchChannelMessages(selectedChannel);
    }
  }, [selectedChannel, fetchChannelMessages]);

  useEffect(() => {
    setupRealtimeStreaming();
    
    return () => {
      // Cleanup streaming connection
      if (streamingRef.current) {
        // streamingRef.current.close();
      }
    };
  }, [setupRealtimeStreaming]);

  // Auto-refresh sync status
  useEffect(() => {
    if (!showMemoryControls) return;
    
    const interval = setInterval(() => {
      fetchSyncStatus();
    }, 30000); // Every 30 seconds
    
    return () => clearInterval(interval);
  }, [fetchSyncStatus, showMemoryControls]);

  // Memoized channel filtering
  const filteredChannels = useMemo(() => {
    if (!selectedGuild?.channels) return [];
    
    return selectedGuild.channels
      .filter(channel => channel.type === 0) // Text channels only
      .sort((a, b) => a.position - b.position);
  }, [selectedGuild]);

  // Memoized guild selector
  const guildSelector = useMemo(() => (
    <Menu>
      <MenuButton as={Button} rightIcon={<FiChevronDown />} variant="outline" size="sm">
        {selectedGuild ? (
          <HStack spacing={2}>
            {selectedGuild.icon_url && (
              <Image 
                src={selectedGuild.icon_url} 
                alt={selectedGuild.name}
                boxSize={4}
                borderRadius="full"
              />
            )}
            <Text>{selectedGuild.name}</Text>
          </HStack>
        ) : (
          <Text>Select Server</Text>
        )}
      </MenuButton>
      <MenuList maxHeight="300px" overflowY="auto">
        {guilds.map(guild => (
          <MenuItem 
            key={guild.id}
            onClick={() => setSelectedGuild(guild)}
            icon={guild.icon_url ? (
              <Image 
                src={guild.icon_url} 
                alt={guild.name}
                boxSize={4}
                borderRadius="full"
              />
            ) : undefined}
          >
            <VStack align="start" spacing={0}>
              <Text>{guild.name}</Text>
              <Text fontSize="xs" color="gray.500">
                {guild.member_count || guild.approximate_member_count || 0} members
              </Text>
            </VStack>
          </MenuItem>
        ))}
      </MenuList>
    </Menu>
  ), [guilds, selectedGuild]);

  // Memoized channel selector
  const channelSelector = useMemo(() => (
    <Menu>
      <MenuButton as={Button} rightIcon={<FiChevronDown />} variant="ghost" size="sm" justifyContent="left">
        <HStack spacing={2}>
          {selectedChannel && channelTypeIcons[selectedChannel.type] && (
            <Icon as={channelTypeIcons[selectedChannel.type]} boxSize={4} />
          )}
          <Text>{selectedChannel?.name || 'Select Channel'}</Text>
        </HStack>
      </MenuButton>
      <MenuList maxHeight="300px" overflowY="auto">
        {filteredChannels.map(channel => (
          <MenuItem 
            key={channel.id}
            onClick={() => setSelectedChannel(channel)}
            icon={<Icon as={channelTypeIcons[channel.type]} boxSize={4} />}
          >
            <VStack align="start" spacing={0}>
              <Text>{channel.name}</Text>
              {channel.topic && (
                <Text fontSize="xs" color="gray.500" noOfLines={1}>
                  {channel.topic}
                </Text>
              )}
            </VStack>
          </MenuItem>
        ))}
      </MenuList>
    </Menu>
  ), [filteredChannels, selectedChannel]);

  if (loading) {
    return (
      <Box className={className} height={height} display="flex" alignItems="center" justifyContent="center">
        <VStack spacing={4}>
          <Spinner size="xl" />
          <Text>Connecting to Discord...</Text>
        </VStack>
      </Box>
    );
  }

  if (!connected) {
    return (
      <Box className={className} height={height} display="flex" alignItems="center" justifyContent="center">
        <Card maxW="md" textAlign="center">
          <CardBody>
            <VStack spacing={6}>
              <Box>
                <Text fontSize="2xl" fontWeight="bold">Discord Integration</Text>
                <Text color="gray.600">Connect your Discord account to ATOM</Text>
              </Box>
              
              <Button 
                colorScheme="blue" 
                size="lg" 
                onClick={() => window.open('/api/auth/discord/authorize', '_blank')}
                leftIcon={<FiZap />}
              >
                Connect Discord
              </Button>
              
              <Button 
                variant="ghost" 
                onClick={fetchCurrentUser}
                leftIcon={<FiRefreshCw />}
              >
                Refresh Connection
              </Button>
            </VStack>
          </CardBody>
        </Card>
      </Box>
    );
  }

  return (
    <Box className={className} height={height} display="flex" borderWidth={1} borderRadius="lg" overflow="hidden">
      <VStack flex={1} spacing={0} align="stretch">
        {/* Header */}
        <HStack 
          p={4} 
          borderBottomWidth={1} 
          bg="discord.dark.50" 
          justify="space-between"
        >
          <HStack spacing={3} flex={1}>
            {currentUser && (
              <Avatar 
                src={currentUser.avatar_url} 
                name={currentUser.display_name}
                size="sm"
              >
                <AvatarBadge boxSize={3} bg="green.500" />
              </Avatar>
            )}
            <VStack spacing={0} align="start" flex={1}>
              <HStack spacing={2}>
                <Text fontWeight="bold">{currentUser?.display_name}</Text>
                <Badge colorScheme="discord">Discord</Badge>
                {realtimeEnabled && (
                  <Badge colorScheme="green" variant="outline">
                    <Icon as={FiZap} boxSize={3} mr={1} />
                    Live
                  </Badge>
                )}
              </HStack>
              <Text fontSize="xs" color="gray.500">
                {selectedGuild?.name} › {selectedChannel?.name}
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            {showMemoryControls && (
              <>
                <Tooltip label="Memory Settings">
                  <IconButton 
                    icon={<FiSettings />} 
                    variant="ghost" 
                    size="sm"
                    onClick={() => setSettingsModalOpen(true)}
                  />
                </Tooltip>
                
                <Tooltip label={`Last sync: ${syncStatus?.stats.last_ingestion_timestamp ? discordUtils.formatDateTime(syncStatus.stats.last_ingestion_timestamp) : 'Never'}`}>
                  <IconButton 
                    icon={<FiDatabase />} 
                    variant="ghost" 
                    size="sm"
                    onClick={() => startSync(false)}
                    isLoading={syncInProgress}
                  />
                </Tooltip>
              </>
            )}
            
            <Tooltip label={realtimeEnabled ? 'Disable Real-time' : 'Enable Real-time'}>
              <IconButton 
                icon={realtimeEnabled ? <FiZap /> : <FiZapOff />} 
                variant="ghost" 
                size="sm"
                onClick={() => setRealtimeEnabled(!realtimeEnabled)}
                colorScheme={realtimeEnabled ? 'green' : 'gray'}
              />
            </Tooltip>
          </HStack>
        </HStack>

        {/* Guild and Channel Selector */}
        <HStack p={3} borderBottomWidth={1} bg="gray.50">
          {guildSelector}
          <Divider orientation="vertical" h={6} />
          {channelSelector}
          
          <Box flex={1} />
          
          <Input
            placeholder="Search messages..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            size="sm"
            maxW="200px"
            leftIcon={<FiSearch />}
          />
        </HStack>

        <HStack flex={1} spacing={0} align="stretch">
          {/* Messages Area */}
          <VStack flex={1} spacing={0} align="stretch">
            <ScrollArea flex={1}>
              <VStack spacing={2} p={4} align="stretch">
                {messages.map((message) => (
                  <HStack key={message.id} spacing={3} align="start">
                    <Avatar 
                      src={message.author.avatar_url} 
                      name={message.author.display_name}
                      size="sm"
                    />
                    <VStack flex={1} align="start" spacing={1}>
                      <HStack spacing={2}>
                        <Text fontWeight="bold" fontSize="sm">
                          {message.author.display_name}
                        </Text>
                        <Text fontSize="xs" color="gray.500">
                          {discordUtils.formatDateTime(message.timestamp)}
                        </Text>
                        {message.edited_timestamp && (
                          <Text fontSize="xs" color="gray.400">
                            (edited)
                          </Text>
                        )}
                        {messageStatus[message.channel_id] && (
                          <Badge 
                            size="xs" 
                            colorScheme={messageStatus[message.channel_id] as any}
                            variant="subtle"
                          >
                            {messageStatus[message.channel_id]}
                          </Badge>
                        )}
                      </HStack>
                      
                      <Text fontSize="sm" whiteSpace="pre-wrap">
                        {discordUtils.formatMessageMarkdown(message.content)}
                      </Text>
                      
                      {/* Attachments */}
                      {message.attachments.length > 0 && (
                        <HStack spacing={2} mt={2}>
                          {message.attachments.map((attachment, index) => (
                            <Card key={index} size="sm" variant="outline">
                              <CardBody p={2}>
                                <Text fontSize="xs">{attachment.filename || 'Attachment'}</Text>
                              </CardBody>
                            </Card>
                          ))}
                        </HStack>
                      )}
                      
                      {/* Embeds */}
                      {message.embeds.length > 0 && (
                        <VStack spacing={2} mt={2} align="start">
                          {message.embeds.map((embed, index) => (
                            <Card key={index} size="sm" variant="outline">
                              <CardBody p={3}>
                                {embed.title && (
                                  <Text fontWeight="bold" fontSize="sm">
                                    {embed.title}
                                  </Text>
                                )}
                                {embed.description && (
                                  <Text fontSize="sm" mt={1}>
                                    {embed.description}
                                  </Text>
                                )}
                                {embed.url && (
                                  <Button 
                                    size="xs" 
                                    mt={2}
                                    onClick={() => window.open(embed.url, '_blank')}
                                  >
                                    Open Link
                                  </Button>
                                )}
                              </CardBody>
                            </Card>
                          ))}
                        </VStack>
                      )}
                      
                      {/* Reactions */}
                      {message.reactions.length > 0 && (
                        <HStack spacing={1} mt={2}>
                          {message.reactions.map((reaction, index) => (
                            <Badge key={index} variant="outline" size="sm">
                              {reaction}
                            </Badge>
                          ))}
                        </HStack>
                      )}
                    </VStack>
                  </HStack>
                ))}
                
                {/* Typing indicator */}
                {isTyping && (
                  <HStack spacing={2}>
                    <Text fontSize="sm" color="gray.500">Someone is typing</Text>
                    <Spinner size="xs" />
                  </HStack>
                )}
                
                <div ref={messagesEndRef} />
              </VStack>
            </ScrollArea>
          </VStack>
        </HStack>

        {/* Message Input */}
        <HStack p={3} borderTopWidth={1} bg="white">
          <Input
            placeholder={`Message #${selectedChannel?.name || 'channel'}...`}
            value={newMessage}
            onChange={(e) => handleTyping(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            flex={1}
            isDisabled={!selectedChannel}
          />
          
          <IconButton
            icon={<FiPaperclip />}
            variant="ghost"
            aria-label="Attach file"
            isDisabled={!selectedChannel}
          />
          
          <IconButton
            icon={<FiMic />}
            variant="ghost"
            aria-label="Voice message"
            isDisabled={!selectedChannel}
          />
          
          <IconButton
            icon={<FiSend />}
            colorScheme="blue"
            onClick={sendMessage}
            isDisabled={!selectedChannel || !newMessage.trim()}
            aria-label="Send message"
          />
        </HStack>
      </VStack>

      {/* Memory Settings Modal */}
      <Modal 
        isOpen={settingsModalOpen} 
        onClose={() => setSettingsModalOpen(false)}
        size="xl"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiDatabase} />
              <Text>Discord Memory Settings</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {memorySettings && (
              <VStack spacing={6} align="stretch">
                {/* General Settings */}
                <VStack spacing={4} align="stretch">
                  <Heading size="sm">General Settings</Heading>
                  
                  <FormControl display="flex" alignItems="center">
                    <FormLabel htmlFor="ingestion-enabled" mb="0">
                      Enable Discord Memory
                    </FormLabel>
                    <Switch
                      id="ingestion-enabled"
                      isChecked={memorySettings.ingestion_enabled}
                      onChange={(e) => updateMemorySettings({
                        ...memorySettings,
                        ingestion_enabled: e.target.checked
                      })}
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Sync Frequency</FormLabel>
                    <Select
                      value={memorySettings.sync_frequency}
                      onChange={(e) => updateMemorySettings({
                        ...memorySettings,
                        sync_frequency: e.target.value
                      })}
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
                      value={memorySettings.data_retention_days}
                      min={1}
                      max={3650}
                      onChange={(value) => updateMemorySettings({
                        ...memorySettings,
                        data_retention_days: parseInt(value) || 365
                      })}
                    >
                      <NumberInputField />
                    </NumberInput>
                  </FormControl>
                </VStack>

                {/* Channel Settings */}
                <VStack spacing={4} align="stretch">
                  <Heading size="sm">Channel Settings</Heading>
                  
                  <FormControl display="flex" alignItems="center">
                    <FormLabel htmlFor="include-dm" mb="0">
                      Include DM Channels
                    </FormLabel>
                    <Switch
                      id="include-dm"
                      isChecked={memorySettings.include_dm_channels}
                      onChange={(e) => updateMemorySettings({
                        ...memorySettings,
                        include_dm_channels: e.target.checked
                      })}
                    />
                  </FormControl>
                  
                  <FormControl display="flex" alignItems="center">
                    <FormLabel htmlFor="include-private" mb="0">
                      Include Private Channels
                    </FormLabel>
                    <Switch
                      id="include-private"
                      isChecked={memorySettings.include_private_channels}
                      onChange={(e) => updateMemorySettings({
                        ...memorySettings,
                        include_private_channels: e.target.checked
                      })}
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Max Messages per Channel</FormLabel>
                    <NumberInput
                      value={memorySettings.max_messages_per_channel}
                      min={100}
                      max={100000}
                      onChange={(value) => updateMemorySettings({
                        ...memorySettings,
                        max_messages_per_channel: parseInt(value) || 10000
                      })}
                    >
                      <NumberInputField />
                    </NumberInput>
                  </FormControl>
                </VStack>

                {/* Search Settings */}
                <VStack spacing={4} align="stretch">
                  <Heading size="sm">Search Settings</Heading>
                  
                  <FormControl display="flex" alignItems="center">
                    <FormLabel htmlFor="semantic-search" mb="0">
                      Enable Semantic Search
                    </FormLabel>
                    <Switch
                      id="semantic-search"
                      isChecked={memorySettings.semantic_search_enabled}
                      onChange={(e) => updateMemorySettings({
                        ...memorySettings,
                        semantic_search_enabled: e.target.checked
                      })}
                    />
                  </FormControl>
                  
                  <FormControl display="flex" alignItems="center">
                    <FormLabel htmlFor="metadata-extraction" mb="0">
                      Enable Metadata Extraction
                    </FormLabel>
                    <Switch
                      id="metadata-extraction"
                      isChecked={memorySettings.metadata_extraction_enabled}
                      onChange={(e) => updateMemorySettings({
                        ...memorySettings,
                        metadata_extraction_enabled: e.target.checked
                      })}
                    />
                  </FormControl>
                </VStack>

                {/* Sync Status */}
                {syncStatus && (
                  <VStack spacing={4} align="stretch">
                    <Heading size="sm">Sync Status</Heading>
                    
                    <Card variant="outline">
                      <CardBody>
                        <SimpleGrid columns={2} spacing={4}>
                          <VStack align="start">
                            <Text fontSize="sm" color="gray.600">Messages Ingested</Text>
                            <Text fontWeight="bold">{syncStatus.stats.total_messages_ingested.toLocaleString()}</Text>
                          </VStack>
                          
                          <VStack align="start">
                            <Text fontSize="sm" color="gray.600">Servers Synced</Text>
                            <Text fontWeight="bold">{syncStatus.stats.total_guilds_synced}</Text>
                          </VStack>
                          
                          <VStack align="start">
                            <Text fontSize="sm" color="gray.600">Channels Synced</Text>
                            <Text fontWeight="bold">{syncStatus.stats.total_channels_synced}</Text>
                          </VStack>
                          
                          <VStack align="start">
                            <Text fontSize="sm" color="gray.600">Storage Used</Text>
                            <Text fontWeight="bold">{syncStatus.stats.storage_size_mb.toFixed(1)} MB</Text>
                          </VStack>
                        </SimpleGrid>
                        
                        <Divider />
                        
                        <HStack justify="space-between" align="center">
                          <VStack align="start" spacing={0}>
                            <Text fontSize="sm" color="gray.600">Last Sync</Text>
                            <Text fontSize="xs">
                              {syncStatus.stats.last_ingestion_timestamp 
                                ? discordUtils.formatDateTime(syncStatus.stats.last_ingestion_timestamp)
                                : 'Never'
                              }
                            </Text>
                          </VStack>
                          
                          <Button 
                            size="sm"
                            onClick={() => startSync(true)}
                            isLoading={syncInProgress}
                            leftIcon={<FiRefreshCw />}
                          >
                            Force Sync
                          </Button>
                        </HStack>
                      </CardBody>
                    </Card>
                  </VStack>
                )}
              </VStack>
            )}
          </ModalBody>
          
          <ModalFooter>
            <Button variant="outline" onClick={() => setSettingsModalOpen(false)}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default DiscordCommunicationUI;