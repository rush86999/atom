/**
 * ATOM Enhanced Communication UI with Teams Integration
 * Unified communication interface that includes Slack, Teams, and future platforms
 */

import React, { useState, useEffect, useCallback, useMemo, useRef, useContext } from 'react';
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
  FormControl,
  FormLabel,
  Input,
  FormHelperText,
  Switch,
  Select,
  Stack,
  Avatar,
  Tag,
  TagLabel,
  TagLeftIcon,
  Spacer,
  Fade,
  ScaleFade,
  SlideFade,
  Divider,
  Progress,
  Alert,
  AlertIcon,
  IconButton,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverArrow,
  PopoverHeader,
  PopoverBody,
  List,
  ListItem,
  ListIcon,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Drawer,
  DrawerOverlay,
  DrawerContent,
  DrawerHeader,
  DrawerBody,
  DrawerCloseButton,
  useBreakpointValue,
  Flex,
  Grid,
  Container,
  Textarea,
  CheckboxGroup,
  Checkbox,
  InputGroup,
  InputLeftElement,
  InputRightElement,
  Kbd,
  Badge,
  SlideFade,
  AbsoluteCenter,
  Spinner,
  Center,
  Circle,
  useInterval,
} from '@chakra-ui/react';
import {
  ChatIcon,
  SearchIcon,
  SettingsIcon,
  ViewIcon,
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
  LockIcon,
  UnlockIcon,
  StarIcon,
  LinkIcon,
  EmailIcon,
  CalendarIcon,
  FilterIcon,
  CloseIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  SmallCloseIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  HamburgerIcon,
  PhoneIcon,
  VideoIcon,
  PhoneIcon as PhoneCallIcon,
  PhoneOffIcon,
  VideoCamera,
  VideoOffIcon,
  MicrophoneIcon,
  MicrophoneOffIcon,
  ScreenIcon,
  ShareIcon,
  HandsIcon,
  RecordIcon,
  StopIcon as StopRecordIcon,
  TeamIcon,
  UsersIcon,
  MessageIcon,
  NotificationIcon,
  InboxIcon,
  ArchiveIcon,
  BookmarkIcon,
  TagIcon,
  CopyIcon,
  DownloadIcon,
  UploadIcon,
  SendIcon,
  RefreshIcon,
  HistoryIcon,
  HeartIcon,
  ThumbUpIcon,
  ThumbDownIcon,
  ChatLeftIcon,
  Share2Icon,
  EyeIcon,
  EyeSlashIcon,
} from '@chakra-ui/icons';

// Import integration services
import { atomTeamsIntegration } from '../../services/atomTeamsIntegration';
import { atomMemoryService } from '../../services/atomMemoryService';
import { atomSearchService } from '../../services/atomSearchService';
import { atomWorkflowService } from '../../services/atomWorkflowService';

// Types
interface UnifiedWorkspace {
  id: string;
  name: string;
  type: 'slack' | 'microsoft_teams' | 'google_chat' | 'discord';
  platform: string;
  status: 'connected' | 'disconnected' | 'error';
  member_count: number;
  channel_count: number;
  icon_url?: string;
  integration_data: any;
  capabilities: {
    messaging: boolean;
    voice_calls: boolean;
    video_calls: boolean;
    screen_sharing: boolean;
    file_sharing: boolean;
    meetings: boolean;
    workflows: boolean;
    analytics: boolean;
  };
}

interface UnifiedChannel {
  id: string;
  name: string;
  display_name: string;
  description: string;
  type: 'standard' | 'private' | 'shared' | 'dm' | 'group_dm';
  platform: string;
  workspace_id: string;
  workspace_name: string;
  status: 'active' | 'archived' | 'readonly';
  member_count: number;
  message_count: number;
  unread_count: number;
  last_activity: string;
  is_private: boolean;
  is_muted: boolean;
  is_favorite: boolean;
  integration_data: any;
  capabilities: {
    messaging: boolean;
    file_sharing: boolean;
    voice_calls: boolean;
    video_calls: boolean;
    meetings: boolean;
    workflows: boolean;
  };
}

interface UnifiedMessage {
  id: string;
  content: string;
  html_content?: string;
  platform: string;
  workspace_id: string;
  workspace_name: string;
  channel_id: string;
  channel_name: string;
  user_id: string;
  user_name: string;
  user_email: string;
  user_avatar?: string;
  timestamp: string;
  thread_id?: string;
  reply_to_id?: string;
  message_type: string;
  importance?: string;
  subject?: string;
  is_edited: boolean;
  edit_timestamp?: string;
  reactions: any[];
  attachments: any[];
  mentions: any[];
  files: any[];
  metadata: any;
  integration_data: any;
  search_highlights?: string[];
}

interface UnifiedSearchResult {
  id: string;
  title: string;
  content: string;
  platform: string;
  workspace_id: string;
  channel_id: string;
  user_id: string;
  user_name: string;
  timestamp: string;
  type: 'message' | 'file' | 'user' | 'channel';
  url?: string;
  relevance_score: number;
  highlights: string[];
}

interface CallState {
  isCallActive: boolean;
  isMuted: boolean;
  isVideoOn: boolean;
  isScreenSharing: boolean;
  isRecording: boolean;
  callType: 'audio' | 'video' | 'meeting';
  participants: string[];
  duration: number;
  startTime?: string;
  platform: string;
  roomId?: string;
}

interface EnhancedCommunicationUIProps {
  atomIngestionPipeline?: any;
  atomMemory?: any;
  atomSearch?: any;
  atomWorkflow?: any;
  atomCallService?: any;
  onIntegrationUpdate?: (data: any) => void;
  onSendMessage?: (message: any) => void;
  onSearchResults?: (results: any[]) => void;
  onCallStart?: (callConfig: any) => void;
  userId?: string;
}

// Context for shared communication state
interface CommunicationContextType {
  workspaces: UnifiedWorkspace[];
  channels: UnifiedChannel[];
  messages: UnifiedMessage[];
  searchResults: UnifiedSearchResult[];
  selectedWorkspace: UnifiedWorkspace | null;
  selectedChannel: UnifiedChannel | null;
  callState: CallState;
  loading: boolean;
  error: string | null;
  activeTab: string;
  searchQuery: string;
  messageText: string;
  replyingTo: UnifiedMessage | null;
  unreadCounts: Record<string, number>;
  refreshWorkspaces: () => Promise<void>;
  refreshChannels: (workspaceId: string) => Promise<void>;
  refreshMessages: (workspaceId: string, channelId: string) => Promise<void>;
  selectWorkspace: (workspace: UnifiedWorkspace) => void;
  selectChannel: (channel: UnifiedChannel) => void;
  sendMessage: (workspaceId: string, channelId: string, text: string, options?: any) => Promise<void>;
  searchMessages: (query: string, workspaceId?: string) => Promise<UnifiedSearchResult[]>;
  startCall: (channelId: string, type: 'audio' | 'video') => void;
  endCall: () => void;
  toggleMute: () => void;
  toggleVideo: () => void;
  toggleScreenShare: () => void;
  toggleRecording: () => void;
  setActiveTab: (tab: string) => void;
  setSearchQuery: (query: string) => void;
  setMessageText: (text: string) => void;
  setReplyingTo: (message: UnifiedMessage | null) => void;
}

const CommunicationContext = React.createContext<CommunicationContextType | null>(null);

// Hooks
const useCommunication = () => {
  const context = useContext(CommunicationContext);
  if (!context) {
    throw new Error('useCommunication must be used within EnhancedCommunicationUI');
  }
  return context;
};

// Platform Badge Component
const PlatformBadge: React.FC<{ platform: string; size?: string }> = ({ platform, size = 'sm' }) => {
  const getPlatformConfig = (platform: string) => {
    switch (platform) {
      case 'slack':
        return {
          colorScheme: 'purple',
          icon: ChatIcon,
          label: 'Slack'
        };
      case 'microsoft_teams':
        return {
          colorScheme: 'blue',
          icon: TeamIcon,
          label: 'Teams'
        };
      case 'google_chat':
        return {
          colorScheme: 'green',
          icon: ChatIcon,
          label: 'Google Chat'
        };
      case 'discord':
        return {
          colorScheme: 'indigo',
          icon: ChatIcon,
          label: 'Discord'
        };
      default:
        return {
          colorScheme: 'gray',
          icon: ChatIcon,
          label: platform
        };
    }
  };

  const config = getPlatformConfig(platform);
  const IconComponent = config.icon;

  return (
    <Badge colorScheme={config.colorScheme} size={size}>
      <IconComponent mr={1} />
      {config.label}
    </Badge>
  );
};

// Message Component
const UnifiedMessageItem: React.FC<{
  message: UnifiedMessage;
  onReply: (message: UnifiedMessage) => void;
  onEdit: (message: UnifiedMessage) => void;
  onDelete: (message: UnifiedMessage) => void;
  onReact: (message: UnifiedMessage, emoji: string) => void;
}> = ({ message, onReply, onEdit, onDelete, onReact }) => {
  const [showReactions, setShowReactions] = useState(false);
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  
  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const getImportanceColor = (importance: string) => {
    switch (importance) {
      case 'low': return 'gray';
      case 'normal': return 'blue';
      case 'high': return 'orange';
      case 'urgent': return 'red';
      default: return 'blue';
    }
  };

  return (
    <Card bg={bgColor} borderWidth="1px" borderColor={borderColor} size="sm" mb={2}>
      <CardBody>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={2} flex={1}>
            <HStack>
              <Avatar size="xs" name={message.user_name} src={message.user_avatar} />
              <Text fontWeight="medium" fontSize="sm">
                {message.user_name}
              </Text>
              <PlatformBadge platform={message.platform} size="xs" />
              <Text fontSize="xs" color="gray.500">
                {formatTimestamp(message.timestamp)}
              </Text>
              {message.importance && message.importance !== 'normal' && (
                <Badge colorScheme={getImportanceColor(message.importance)} fontSize="xs">
                  {message.importance.toUpperCase()}
                </Badge>
              )}
              {message.thread_id && (
                <Badge colorScheme="blue" fontSize="xs">Thread</Badge>
              )}
              {message.is_edited && (
                <Badge colorScheme="gray" fontSize="xs">Edited</Badge>
              )}
            </HStack>
            
            {message.subject && (
              <Text fontWeight="bold" fontSize="sm" color="blue.600">
                {message.subject}
              </Text>
            )}
            
            <Box 
              fontSize="sm" 
              dangerouslySetInnerHTML={{ __html: message.html_content || message.content }}
              noOfLines={message.thread_id ? undefined : 3}
            />
            
            {message.attachments && message.attachments.length > 0 && (
              <HStack>
                <Icon as={<FileIcon />} color="blue.500" />
                <Text fontSize="xs" color="blue.500">
                  {message.attachments.length} attachment(s)
                </Text>
              </HStack>
            )}
            
            {message.mentions && message.mentions.length > 0 && (
              <HStack spacing={1} flexWrap="wrap">
                <Icon as={<LinkIcon />} color="purple.500" />
                {message.mentions.slice(0, 3).map((mention, idx) => (
                  <Tag key={idx} size="sm" colorScheme="purple">
                    @{mention.name}
                  </Tag>
                ))}
                {message.mentions.length > 3 && (
                  <Text fontSize="xs" color="gray.500">
                    +{message.mentions.length - 3} more mentions
                  </Text>
                )}
              </HStack>
            )}
            
            {message.reactions && message.reactions.length > 0 && (
              <HStack spacing={1} flexWrap="wrap">
                {message.reactions.slice(0, 3).map((reaction, idx) => (
                  <Tag key={idx} size="sm" variant="outline">
                    {reaction.emoji}
                    <TagLabel>{reaction.count}</TagLabel>
                  </Tag>
                ))}
                {message.reactions.length > 3 && (
                  <Text fontSize="xs" color="gray.500">
                    +{message.reactions.length - 3} more
                  </Text>
                )}
              </HStack>
            )}
            
            {message.search_highlights && message.search_highlights.length > 0 && (
              <HStack>
                <Icon as={<SearchIcon />} color="green.500" />
                <Text fontSize="xs" color="green.500">
                  {message.search_highlights.length} highlight(s)
                </Text>
              </HStack>
            )}
          </VStack>
          
          <HStack>
            <Popover
              isOpen={showReactions}
              onOpen={() => setShowReactions(true)}
              onClose={() => setShowReactions(false)}
              placement="bottom-start"
            >
              <PopoverTrigger>
                <IconButton
                  size="xs"
                  variant="ghost"
                  icon={<AddIcon />}
                  aria-label="React"
                />
              </PopoverTrigger>
              <PopoverContent>
                <PopoverArrow />
                <PopoverHeader>React</PopoverHeader>
                <PopoverBody>
                  <HStack spacing={2}>
                    {['👍', '❤️', '😂', '😮', '😢', '🔥'].map(emoji => (
                      <Button
                        key={emoji}
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          onReact(message, emoji);
                          setShowReactions(false);
                        }}
                      >
                        {emoji}
                      </Button>
                    ))}
                  </HStack>
                </PopoverBody>
              </PopoverContent>
            </Popover>
            
            <IconButton
              size="xs"
              variant="ghost"
              icon={<ChatLeftIcon />}
              onClick={() => onReply(message)}
              aria-label="Reply"
            />
            
            <IconButton
              size="xs"
              variant="ghost"
              icon={<EditIcon />}
              onClick={() => onEdit(message)}
              aria-label="Edit"
            />
            
            <IconButton
              size="xs"
              variant="ghost"
              icon={<DeleteIcon />}
              onClick={() => onDelete(message)}
              aria-label="Delete"
            />
          </HStack>
        </HStack>
      </CardBody>
    </Card>
  );
};

// Workspace Card Component
const WorkspaceCard: React.FC<{
  workspace: UnifiedWorkspace;
  isSelected: boolean;
  onSelect: () => void;
  onConnect: () => void;
  onDisconnect: () => void;
}> = ({ workspace, isSelected, onSelect, onConnect, onDisconnect }) => {
  const getPlatformColor = (platform: string) => {
    switch (platform) {
      case 'Slack': return 'purple';
      case 'Microsoft Teams': return 'blue';
      case 'Google Chat': return 'green';
      case 'Discord': return 'indigo';
      default: return 'gray';
    }
  };

  return (
    <Card
      cursor="pointer"
      bg={isSelected ? useColorModeValue('blue.50', 'blue.900') : undefined}
      borderColor={isSelected ? 'blue.500' : undefined}
      borderWidth={isSelected ? '2px' : '1px'}
      onClick={onSelect}
      transition="all 0.2s"
      _hover={{ shadow: 'md', transform: 'translateY(-1px)' }}
    >
      <CardBody>
        <HStack spacing={4} align="start">
          <Avatar
            size="md"
            name={workspace.name}
            src={workspace.icon_url}
            bg={`${getPlatformColor(workspace.platform)}.500`}
          />
          
          <VStack align="start" spacing={1} flex={1}>
            <HStack>
              <Text fontWeight="bold" fontSize="md">
                {workspace.name}
              </Text>
              <PlatformBadge platform={workspace.type} size="xs" />
            </HStack>
            
            <Text fontSize="sm" color="gray.600" noOfLines={1}>
              {workspace.platform}
            </Text>
            
            <HStack spacing={4} pt={1}>
              <Stat size="sm">
                <StatNumber fontSize="xs">{workspace.channel_count}</StatNumber>
                <StatLabel fontSize="xs">Channels</StatLabel>
              </Stat>
              
              <Stat size="sm">
                <StatNumber fontSize="xs">{workspace.member_count}</StatNumber>
                <StatLabel fontSize="xs">Members</StatLabel>
              </Stat>
            </HStack>
          </VStack>
          
          <VStack spacing={2}>
            <Badge
              colorScheme={workspace.status === 'connected' ? 'green' : 'yellow'}
              display="flex"
              alignItems="center"
            >
              <Icon as={workspace.status === 'connected' ? CheckCircleIcon : WarningIcon} mr={1} />
              {workspace.status}
            </Badge>
            
            <HStack spacing={1}>
              {workspace.capabilities.messaging && (
                <Tooltip label="Messaging">
                  <Icon as={<ChatIcon />} color="gray.500" w={3} h={3} />
                </Tooltip>
              )}
              {workspace.capabilities.voice_calls && (
                <Tooltip label="Voice Calls">
                  <Icon as={<PhoneIcon />} color="gray.500" w={3} h={3} />
                </Tooltip>
              )}
              {workspace.capabilities.video_calls && (
                <Tooltip label="Video Calls">
                  <Icon as={<VideoIcon />} color="gray.500" w={3} h={3} />
                </Tooltip>
              )}
              {workspace.capabilities.file_sharing && (
                <Tooltip label="File Sharing">
                  <Icon as={<FileIcon />} color="gray.500" w={3} h={3} />
                </Tooltip>
              )}
              {workspace.capabilities.meetings && (
                <Tooltip label="Meetings">
                  <Icon as={<CalendarIcon />} color="gray.500" w={3} h={3} />
                </Tooltip>
              )}
            </HStack>
            
            <Menu>
              <MenuButton
                as={IconButton}
                icon={<MoreVerticalIcon />}
                variant="ghost"
                size="xs"
                aria-label="Workspace menu"
              />
              <MenuList>
                {workspace.status === 'connected' ? (
                  <MenuItem icon={<DisconnectIcon />} onClick={onDisconnect}>
                    Disconnect
                  </MenuItem>
                ) : (
                  <MenuItem icon={<ConnectIcon />} onClick={onConnect}>
                    Connect
                  </MenuItem>
                )}
                <MenuItem icon={<SettingsIcon />}>
                  Configure
                </MenuItem>
                <MenuItem icon={<RefreshIcon />}>
                  Sync
                </MenuItem>
              </MenuList>
            </Menu>
          </VStack>
        </HStack>
      </CardBody>
    </Card>
  );
};

// Search Results Component
const SearchResultsPanel: React.FC<{
  searchResults: UnifiedSearchResult[];
  searchQuery: string;
  onResultClick: (result: UnifiedSearchResult) => void;
}> = ({ searchResults, searchQuery, onResultClick }) => {
  return (
    <VStack spacing={3} align="stretch">
      <HStack justify="space-between">
        <Heading size="sm">
          Search Results ({searchResults.length})
        </Heading>
        <Text fontSize="xs" color="gray.500">
          "{searchQuery}"
        </Text>
      </HStack>
      
      <VStack spacing={2} maxH="500px" overflowY="auto">
        {searchResults.map((result) => (
          <Card
            key={result.id}
            cursor="pointer"
            size="sm"
            _hover={{ bg: useColorModeValue('gray.50', 'gray.700') }}
            onClick={() => onResultClick(result)}
          >
            <CardBody>
              <HStack justify="space-between" align="start">
                <VStack align="start" spacing={1} flex={1}>
                  <HStack>
                    <Text fontWeight="medium" fontSize="sm" noOfLines={1}>
                      {result.title}
                    </Text>
                    <PlatformBadge platform={result.platform} size="xs" />
                  </HStack>
                  
                  <Text fontSize="sm" color="gray.600" noOfLines={2}>
                    {result.content}
                  </Text>
                  
                  <HStack>
                    <Avatar size="xs" name={result.user_name} />
                    <Text fontSize="xs" color="gray.500">
                      {result.user_name}
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      •
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      {new Date(result.timestamp).toLocaleDateString()}
                    </Text>
                  </HStack>
                  
                  {result.highlights.length > 0 && (
                    <HStack>
                      <Icon as={<SearchIcon />} color="green.500" />
                      <Text fontSize="xs" color="green.500">
                        {result.highlights.length} highlight(s)
                      </Text>
                    </HStack>
                  )}
                </VStack>
                
                <Badge colorScheme="blue" size="sm">
                  <Icon as={<EyeIcon />} mr={1} />
                  {result.type}
                </Badge>
              </HStack>
            </CardBody>
          </Card>
        ))}
        
        {searchResults.length === 0 && (
          <Center py={8}>
            <VStack>
              <Icon as={<SearchIcon />} w={8} h={8} color="gray.400" />
              <Text color="gray.500">No results found</Text>
              <Text fontSize="sm" color="gray.400">
                Try adjusting your search query
              </Text>
            </VStack>
          </Center>
        )}
      </VStack>
    </VStack>
  );
};

// Main Enhanced Communication UI Component
const EnhancedCommunicationUI: React.FC<EnhancedCommunicationUIProps> = ({
  atomIngestionPipeline,
  atomMemory,
  atomSearch,
  atomWorkflow,
  atomCallService,
  onIntegrationUpdate,
  onSendMessage,
  onSearchResults,
  onCallStart,
  userId = 'default-user'
}) => {
  // Core state
  const [workspaces, setWorkspaces] = useState<UnifiedWorkspace[]>([]);
  const [channels, setChannels] = useState<UnifiedChannel[]>([]);
  const [messages, setMessages] = useState<UnifiedMessage[]>([]);
  const [searchResults, setSearchResults] = useState<UnifiedSearchResult[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<UnifiedWorkspace | null>(null);
  const [selectedChannel, setSelectedChannel] = useState<UnifiedChannel | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // UI state
  const [activeTab, setActiveTab] = useState('workspaces');
  const [searchQuery, setSearchQuery] = useState('');
  const [messageText, setMessageText] = useState('');
  const [replyingTo, setReplyingTo] = useState<UnifiedMessage | null>(null);
  const [unreadCounts, setUnreadCounts] = useState<Record<string, number>>({});
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  
  // Call state
  const [callState, setCallState] = useState<CallState>({
    isCallActive: false,
    isMuted: false,
    isVideoOn: true,
    isScreenSharing: false,
    isRecording: false,
    callType: 'audio',
    participants: [],
    duration: 0,
    platform: ''
  });
  
  // Hooks
  const { isOpen: isCallModalOpen, onOpen: onCallModalOpen, onClose: onCallModalClose } = useDisclosure();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const isMobile = useBreakpointValue({ base: true, md: false });

  // API calls
  const refreshWorkspaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Get unified workspaces from Teams integration
      if (atomTeamsIntegration) {
        const unified_workspaces = await atomTeams_integration.get_unified_workspaces(userId);
        setWorkspaces(unified_workspaces);
        
        // Auto-select first workspace if none selected
        if (!selectedWorkspace && unified_workspaces.length > 0) {
          setSelectedWorkspace(unified_workspaces[0]);
        }
      }
    } catch (err) {
      setError('Network error occurred');
    } finally {
      setLoading(false);
    }
  }, [userId, selectedWorkspace]);

  const refreshChannels = useCallback(async (workspaceId: string) => {
    setLoading(true);
    try {
      if (atomTeamsIntegration) {
        const unified_channels = await atomTeams_integration.get_unified_channels(workspaceId, userId);
        setChannels(unified_channels);
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to fetch channels',
        status: 'error'
      });
    } finally {
      setLoading(false);
    }
  }, [userId, toast]);

  const refreshMessages = useCallback(async (workspaceId: string, channelId: string) => {
    setLoading(true);
    try {
      if (atomTeamsIntegration) {
        const unified_messages = await atomTeams_integration.get_unified_messages(workspaceId, channelId, {
          limit: 100,
          include_sentiment: true,
          include_topics: true
        });
        setMessages(unified_messages);
        
        // Scroll to latest message
        setTimeout(() => {
          const messagesContainer = document.getElementById('unified-messages-container');
          if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
          }
        }, 100);
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to fetch messages',
        status: 'error'
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const sendMessage = useCallback(async (workspaceId: string, channelId: string, text: string, options: any = {}) => {
    if (!text.trim()) return;
    
    try {
      if (atomTeamsIntegration) {
        const result = await atomTeams_integration.send_unified_message(workspaceId, channelId, text, {
          thread_id: replyingTo?.id.replace('teams_', '') if replyingTo?.id?.startsWith('teams_') else replyingTo?.id,
          importance: options.importance || 'normal',
          subject: options.subject,
          attachments: options.attachments || []
        });
        
        if (result.ok) {
          setMessageText('');
          setReplyingTo(null);
          await refreshMessages(workspaceId, channelId);
          
          if (onSendMessage) {
            onSendMessage(result);
          }
        } else {
          toast({
            title: 'Error',
            description: result.error || 'Failed to send message',
            status: 'error'
          });
        }
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to send message',
        status: 'error'
      });
    }
  }, [replyingTo, refreshMessages, onSendMessage, toast]);

  const searchMessages = useCallback(async (query: string, workspaceId?: string): Promise<UnifiedSearchResult[]> => {
    if (!query.trim()) return [];
    
    try {
      if (atomTeamsIntegration) {
        const results = await atomTeams_integration.unified_search(query, workspaceId || selectedWorkspace?.id, {
          limit: 50,
          include_highlights: true
        });
        
        setSearchResults(results);
        
        if (onSearchResults) {
          onSearchResults(results);
        }
        
        return results;
      }
    } catch (err) {
      toast({
        title: 'Search Error',
        description: 'Failed to search messages',
        status: 'error'
      });
    }
    
    return [];
  }, [selectedWorkspace, onSearchResults, toast]);

  // Call functions
  const startCall = useCallback((channelId: string, type: 'audio' | 'video') => {
    if (onCallStart) {
      onCallStart({ channelId, type });
    }
    
    setCallState(prev => ({
      ...prev,
      isCallActive: true,
      callType: type,
      startTime: new Date().toISOString(),
      roomId: `room_${Date.now()}`,
      platform: selectedChannel?.workspace_name.includes('Teams') ? 'Microsoft Teams' : 'Slack'
    }));
    
    toast({
      title: 'Call Started',
      description: `${type === 'video' ? 'Video' : 'Audio'} call started`,
      status: 'info'
    });
    onCallModalOpen();
  }, [onCallStart, selectedChannel, toast, onCallModalOpen]);

  const endCall = useCallback(() => {
    setCallState({
      isCallActive: false,
      isMuted: false,
      isVideoOn: true,
      isScreenSharing: false,
      isRecording: false,
      callType: 'audio',
      participants: [],
      duration: 0,
      platform: ''
    });
    onCallModalClose();
    
    toast({
      title: 'Call Ended',
      description: 'Call has been ended',
      status: 'info'
    });
  }, [onCallModalClose, toast]);

  const toggleMute = useCallback(() => {
    setCallState(prev => ({ ...prev, isMuted: !prev.isMuted }));
  }, []);

  const toggleVideo = useCallback(() => {
    setCallState(prev => ({ ...prev, isVideoOn: !prev.isVideoOn }));
  }, []);

  const toggleScreenShare = useCallback(() => {
    setCallState(prev => ({ ...prev, isScreenSharing: !prev.isScreenSharing }));
  }, []);

  const toggleRecording = useCallback(() => {
    setCallState(prev => ({ ...prev, isRecording: !prev.isRecording }));
    
    toast({
      title: callState.isRecording ? 'Recording Stopped' : 'Recording Started',
      description: callState.isRecording ? 'Call recording has been stopped' : 'Call recording has been started',
      status: 'info'
    });
  }, [callState.isRecording, toast]);

  // Message handlers
  const handleMessageReply = useCallback((message: UnifiedMessage) => {
    setReplyingTo(message);
  }, []);

  const handleMessageEdit = useCallback((message: UnifiedMessage) => {
    setMessageText(message.content);
    setReplyingTo(null);
  }, []);

  const handleMessageDelete = useCallback(async (message: UnifiedMessage) => {
    // Implement message delete
    toast({
      title: 'Message Deleted',
      description: 'Message has been deleted',
      status: 'info'
    });
  }, [toast]);

  const handleMessageReact = useCallback(async (message: UnifiedMessage, emoji: string) => {
    // Implement message reaction
    toast({
      title: 'Reaction Added',
      description: `Reacted ${emoji} to message`,
      status: 'success'
    });
  }, [toast]);

  const handleSearchResultClick = useCallback((result: UnifiedSearchResult) => {
    // Navigate to the message/file
    setActiveTab('messages');
    
    // Select appropriate workspace and channel
    if (result.workspace_id && result.channel_id) {
      const workspace = workspaces.find(w => w.id === result.workspace_id);
      const channel = channels.find(c => c.id === result.channel_id);
      
      if (workspace && channel) {
        setSelectedWorkspace(workspace);
        setSelectedChannel(channel);
        // Scroll to the specific message
      }
    }
  }, [workspaces, channels]);

  // Effects
  useEffect(() => {
    refreshWorkspaces();
  }, [refreshWorkspaces]);

  useEffect(() => {
    if (selectedWorkspace) {
      refreshChannels(selectedWorkspace.id);
    }
  }, [selectedWorkspace, refreshChannels]);

  useEffect(() => {
    if (selectedChannel && selectedWorkspace) {
      refreshMessages(selectedWorkspace.id, selectedChannel.id);
    }
  }, [selectedChannel, selectedWorkspace, refreshMessages]);

  // Auto-refresh for real-time updates
  useInterval(() => {
    if (selectedChannel && selectedWorkspace) {
      refreshMessages(selectedWorkspace.id, selectedChannel.id);
    }
  }, 30000); // 30 seconds

  // Update call duration
  useInterval(() => {
    if (callState.isCallActive && callState.startTime) {
      const start = new Date(callState.startTime).getTime();
      const now = new Date().getTime();
      setCallState(prev => ({ ...prev, duration: Math.floor((now - start) / 1000) }));
    }
  }, 1000);

  // Context value
  const contextValue: CommunicationContextType = useMemo(() => ({
    workspaces,
    channels,
    messages,
    searchResults,
    selectedWorkspace,
    selectedChannel,
    callState,
    loading,
    error,
    activeTab,
    searchQuery,
    messageText,
    replyingTo,
    unreadCounts,
    refreshWorkspaces,
    refreshChannels,
    refreshMessages,
    selectWorkspace: setSelectedWorkspace,
    selectChannel: setSelectedChannel,
    sendMessage,
    searchMessages,
    startCall,
    endCall,
    toggleMute,
    toggleVideo,
    toggleScreenShare,
    toggleRecording,
    setActiveTab,
    setSearchQuery,
    setMessageText,
    setReplyingTo
  }), [workspaces, channels, messages, searchResults, selectedWorkspace, selectedChannel, callState, loading, error, activeTab, searchQuery, messageText, replyingTo, unreadCounts, refreshWorkspaces, refreshChannels, refreshMessages, sendMessage, searchMessages, startCall, endCall, toggleMute, toggleVideo, toggleScreenShare, toggleRecording, setActiveTab, setSearchQuery, setMessageText, setReplyingTo]);

  // Calculate stats
  const stats = useMemo(() => ({
    totalWorkspaces: workspaces.length,
    totalChannels: channels.length,
    totalMessages: messages.length,
    connectedWorkspaces: workspaces.filter(w => w.status === 'connected').length,
    totalUnread: Object.values(unreadCounts).reduce((sum, count) => sum + count, 0),
    activeCall: callState.isCallActive,
    callParticipants: callState.participants.length,
    platforms: [...new Set(workspaces.map(w => w.platform))]
  }), [workspaces, channels, messages, unreadCounts, callState]);

  const isMobileView = isMobile;

  return (
    <CommunicationContext.Provider value={contextValue}>
      <Container maxW="container.xl" py={4}>
        {/* Header */}
        <Flex justify="space-between" align="center" mb={6}>
          <HStack spacing={3}>
            <Icon as={<ChatIcon />} w={8} h={8} color="blue.500" />
            <Box>
              <Heading size="lg">Enhanced Communication Hub</Heading>
              <Text fontSize="sm" color="gray.600">
                Unified Slack, Teams, and multi-platform communication
              </Text>
            </Box>
          </HStack>
          
          <HStack spacing={3}>
            {/* Global Search */}
            <Box w={{ base: '200px', md: '300px' }}>
              <InputGroup>
                <InputLeftElement>
                  <Icon as={<SearchIcon />} color="gray.400" />
                </InputLeftElement>
                <Input
                  placeholder="Search all platforms..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      searchMessages(searchQuery);
                    }
                  }}
                  bg={bgColor}
                />
                <InputRightElement>
                  <Button
                    size="sm"
                    onClick={() => searchMessages(searchQuery)}
                    isDisabled={!searchQuery.trim()}
                  >
                    Search
                  </Button>
                </InputRightElement>
              </InputGroup>
            </Box>
            
            {/* Mobile Menu */}
            {isMobileView && (
              <IconButton
                icon={<HamburgerIcon />}
                onClick={() => setIsMobileDrawerOpen(true)}
                aria-label="Open menu"
              />
            )}
            
            {/* Connection Status */}
            <Badge
              colorScheme={stats.connectedWorkspaces > 0 ? 'green' : 'yellow'}
              display="flex"
              alignItems="center"
            >
              <Icon as={stats.connectedWorkspaces > 0 ? CheckCircleIcon : WarningIcon} mr={1} />
              {stats.connectedWorkspaces} Connected
            </Badge>
          </HStack>
        </Flex>

        {/* Stats Overview */}
        <SimpleGrid columns={{ base: 2, md: 4, lg: 6 }} spacing={4} mb={6}>
          <Stat>
            <StatLabel>Workspaces</StatLabel>
            <StatNumber>{stats.totalWorkspaces}</StatNumber>
            <StatHelpText>
              <Icon as={CheckCircleIcon} color="green.500" mr={1} />
              {stats.connectedWorkspaces} connected
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Channels</StatLabel>
            <StatNumber>{stats.totalChannels}</StatNumber>
            <StatHelpText>
              <Icon as={<ChatIcon />} color="blue.500" mr={1} />
              Available
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Messages</StatLabel>
            <StatNumber>{stats.totalMessages.toLocaleString()}</StatNumber>
            <StatHelpText>
              <Icon as={<MessageIcon />} color="orange.500" mr={1} />
              Indexed
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Unread</StatLabel>
            <StatNumber>{stats.totalUnread}</StatNumber>
            <StatHelpText>
              <Icon as={<NotificationIcon />} color="red.500" mr={1} />
              Total
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Active Call</StatLabel>
            <StatNumber>{stats.callParticipants}</StatNumber>
            <StatHelpText>
              <Icon as={<PhoneIcon />} color="purple.500" mr={1} />
              {stats.activeCall ? 'Active' : 'None'}
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Platforms</StatLabel>
            <StatNumber>{stats.platforms.length}</StatNumber>
            <StatHelpText>
              <Icon as={<TeamIcon />} color="teal.500" mr={1} />
              Integrated
            </StatHelpText>
          </Stat>
        </SimpleGrid>

        {/* Main Content */}
        <Flex gap={6}>
          {/* Sidebar - Desktop */}
          {!isMobileView && (
            <Box w="320px">
              <Card>
                <CardHeader>
                  <HStack justify="space-between">
                    <Heading size="sm">Workspaces</Heading>
                    <Button
                      size="xs"
                      variant="outline"
                      icon={<RepeatIcon />}
                      onClick={refreshWorkspaces}
                      isLoading={loading}
                      aria-label="Refresh workspaces"
                    />
                  </HStack>
                </CardHeader>
                <CardBody>
                  <VStack spacing={3} align="stretch" maxH="300px" overflowY="auto">
                    {workspaces.map((workspace) => (
                      <WorkspaceCard
                        key={workspace.id}
                        workspace={workspace}
                        isSelected={selectedWorkspace?.id === workspace.id}
                        onSelect={() => setSelectedWorkspace(workspace)}
                        onConnect={() => {
                          // Implement workspace connection
                          toast({
                            title: 'Connection',
                            description: `Connecting to ${workspace.name}...`,
                            status: 'info'
                          });
                        }}
                        onDisconnect={() => {
                          // Implement workspace disconnection
                          toast({
                            title: 'Disconnection',
                            description: `Disconnecting from ${workspace.name}...`,
                            status: 'info'
                          });
                        }}
                      />
                    ))}
                  </VStack>
                </CardBody>
              </Card>
              
              {selectedWorkspace && (
                <Card mt={4}>
                  <CardHeader>
                    <Heading size="sm">Channels</Heading>
                  </CardHeader>
                  <CardBody>
                    <VStack spacing={2} align="stretch" maxH="400px" overflowY="auto">
                      {channels.map((channel) => (
                        <Button
                          key={channel.id}
                          variant={selectedChannel?.id === channel.id ? 'solid' : 'ghost'}
                          justifyContent="flex-start"
                          onClick={() => setSelectedChannel(channel)}
                          size="sm"
                          p={2}
                        >
                          <VStack align="start" spacing={0} w="full">
                            <HStack w="full" justify="space-between">
                              <HStack>
                                <Icon 
                                  as={channel.is_private ? <LockIcon /> : <UnlockIcon />} 
                                  color="gray.500" 
                                  w={3} h={3}
                                />
                                <Text fontSize="sm" noOfLines={1} flex={1}>
                                  {channel.display_name}
                                </Text>
                              </HStack>
                              {channel.unread_count > 0 && (
                                <Badge size="sm" colorScheme="red" borderRadius="full">
                                  {channel.unread_count}
                                </Badge>
                              )}
                            </HStack>
                            <HStack w="full" justify="space-between">
                              <PlatformBadge platform={channel.platform} size="xs" />
                              <Text fontSize="xs" color="gray.500">
                                {channel.member_count} members
                              </Text>
                            </HStack>
                          </VStack>
                        </Button>
                      ))}
                    </VStack>
                  </CardBody>
                </Card>
              )}
            </Box>
          )}

          {/* Main Content Area */}
          <Box flex={1}>
            <Tabs variant="enclosed" onChange={(index) => setActiveTab(['workspaces', 'messages', 'search', 'calls', 'files', 'analytics'][index])}>
              <TabList>
                <Tab>
                  <HStack>
                    <TeamIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Workspaces</Text>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <ChatIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Messages</Text>
                    {stats.totalUnread > 0 && (
                      <Badge size="sm" colorScheme="red" borderRadius="full">
                        {stats.totalUnread}
                      </Badge>
                    )}
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <SearchIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Search</Text>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <PhoneIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Calls</Text>
                    {stats.activeCall && (
                      <Badge size="sm" colorScheme="red" borderRadius="full">
                        LIVE
                      </Badge>
                    )}
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <FileIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Files</Text>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <TimeIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Analytics</Text>
                  </HStack>
                </Tab>
              </TabList>

              <TabPanels>
                {/* Workspaces Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Box>
                        <Text fontWeight="bold">Multi-Platform Communication Hub</Text>
                        <Text>
                          Connect your Slack, Microsoft Teams, and other communication platforms 
                          for a unified messaging and collaboration experience.
                        </Text>
                      </Box>
                    </Alert>

                    {/* Quick Actions */}
                    <Card>
                      <CardHeader>
                        <Heading size="md">Quick Actions</Heading>
                      </CardHeader>
                      <CardBody>
                        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                          <Button
                            leftIcon={<AddIcon />}
                            colorScheme="purple"
                            onClick={() => window.open('/api/integrations/slack/oauth_url', '_blank')}
                          >
                            Connect Slack
                          </Button>
                          <Button
                            leftIcon={<AddIcon />}
                            colorScheme="blue"
                            onClick={() => window.open('/api/integrations/teams/oauth_url', '_blank')}
                          >
                            Connect Teams
                          </Button>
                          <Button
                            leftIcon={<SearchIcon />}
                            colorScheme="green"
                            onClick={() => setActiveTab('search')}
                          >
                            Search All Messages
                          </Button>
                        </SimpleGrid>
                      </CardBody>
                    </Card>

                    {/* All Workspaces Grid */}
                    <Card>
                      <CardHeader>
                        <Heading size="md">All Workspaces</Heading>
                      </CardHeader>
                      <CardBody>
                        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                          {workspaces.map((workspace) => (
                            <WorkspaceCard
                              key={workspace.id}
                              workspace={workspace}
                              isSelected={selectedWorkspace?.id === workspace.id}
                              onSelect={() => {
                                setSelectedWorkspace(workspace);
                                setActiveTab('messages');
                              }}
                              onConnect={() => {
                                toast({
                                  title: 'Connection',
                                  description: `Connecting to ${workspace.name}...`,
                                  status: 'info'
                                });
                              }}
                              onDisconnect={() => {
                                toast({
                                  title: 'Disconnection',
                                  description: `Disconnecting from ${workspace.name}...`,
                                  status: 'info'
                                });
                              }}
                            />
                          ))}
                        </SimpleGrid>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Messages Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch">
                    {/* Channel Header */}
                    {selectedChannel && (
                      <Card size="sm" variant="outline">
                        <CardBody>
                          <HStack justify="space-between">
                            <HStack>
                              <Icon 
                                as={selectedChannel.is_private ? <LockIcon /> : <UnlockIcon />} 
                                color="gray.500" 
                                w={4} h={4}
                              />
                              <Text fontWeight="medium">
                                {selectedChannel.display_name}
                              </Text>
                              <PlatformBadge platform={selectedChannel.platform} size="xs" />
                              <Badge colorScheme="blue" fontSize="xs">
                                {selectedWorkspace?.display_name}
                              </Badge>
                            </HStack>
                            <HStack>
                              <Text fontSize="sm" color="gray.600">
                                {selectedChannel.member_count} members
                              </Text>
                              <Button
                                size="xs"
                                variant="outline"
                                icon={<PhoneIcon />}
                                onClick={() => startCall(selectedChannel.id, 'video')}
                                isDisabled={stats.activeCall}
                                aria-label="Start call"
                              >
                                Call
                              </Button>
                              <IconButton
                                size="xs"
                                variant="ghost"
                                icon={<RepeatIcon />}
                                onClick={() => selectedChannel && selectedWorkspace && refreshMessages(selectedWorkspace.id, selectedChannel.id)}
                                aria-label="Refresh messages"
                              />
                            </HStack>
                          </HStack>
                        </CardBody>
                      </Card>
                    )}

                    {/* Messages */}
                    <Card>
                      <CardBody>
                        <VStack 
                          align="stretch" 
                          spacing={2} 
                          maxH="600px" 
                          overflowY="auto"
                          id="unified-messages-container"
                        >
                          {loading ? (
                            <HStack justify="center" py={8}>
                              <Icon as={<RepeatIcon />} animation="spin" />
                              <Text>Loading messages...</Text>
                            </HStack>
                          ) : messages.length === 0 ? (
                            <Text color="gray.500" textAlign="center" py={8}>
                              No messages in this channel
                            </Text>
                          ) : (
                            messages.map((message) => (
                              <UnifiedMessageItem
                                key={message.id}
                                message={message}
                                onReply={handleMessageReply}
                                onEdit={handleMessageEdit}
                                onDelete={handleMessageDelete}
                                onReact={handleMessageReact}
                              />
                            ))
                          )}
                        </VStack>
                      </CardBody>
                    </Card>

                    {/* Message Composer */}
                    {(replyingTo || selectedChannel) && (
                      <Card>
                        <CardBody>
                          {replyingTo && (
                            <HStack spacing={2} mb={3} p={2} bg="gray.50" borderRadius="md">
                              <Avatar size="xs" name={replyingTo.user_name} src={replyingTo.user_avatar} />
                              <Text fontSize="sm" color="gray.600">
                                Replying to {replyingTo.user_name}
                              </Text>
                              <Spacer />
                              <IconButton
                                size="xs"
                                variant="ghost"
                                icon={<SmallCloseIcon />}
                                onClick={() => setReplyingTo(null)}
                                aria-label="Cancel reply"
                              />
                            </HStack>
                          )}
                          
                          <VStack spacing={3}>
                            <Textarea
                              placeholder={replyingTo ? "Write a reply..." : "Type a message..."}
                              value={messageText}
                              onChange={(e) => setMessageText(e.target.value)}
                              rows={3}
                              resize="none"
                            />
                            
                            <HStack justify="space-between">
                              <HStack>
                                <IconButton
                                  size="sm"
                                  variant="outline"
                                  icon={<FileIcon />}
                                  aria-label="Attach file"
                                />
                                <IconButton
                                  size="sm"
                                  variant="outline"
                                  icon={<UserIcon />}
                                  aria-label="Mention user"
                                />
                                <IconButton
                                  size="sm"
                                  variant="outline"
                                  icon={<PhoneIcon />}
                                  onClick={() => selectedChannel && startCall(selectedChannel.id, 'audio')}
                                  isDisabled={stats.activeCall}
                                  aria-label="Start audio call"
                                />
                                <IconButton
                                  size="sm"
                                  variant="outline"
                                  icon={<VideoIcon />}
                                  onClick={() => selectedChannel && startCall(selectedChannel.id, 'video')}
                                  isDisabled={stats.activeCall}
                                  aria-label="Start video call"
                                />
                              </HStack>
                              
                              <HStack>
                                {replyingTo && (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    onClick={() => setReplyingTo(null)}
                                  >
                                    Cancel
                                  </Button>
                                )}
                                <Button
                                  colorScheme="blue"
                                  size="sm"
                                  onClick={() => {
                                    if (selectedChannel && selectedWorkspace) {
                                      sendMessage(
                                        selectedWorkspace.id,
                                        selectedChannel.id,
                                        messageText,
                                        {
                                          reply_to_id: replyingTo?.id
                                        }
                                      );
                                    }
                                  }}
                                  isDisabled={!messageText.trim() || !selectedChannel || !selectedWorkspace}
                                >
                                  Send
                                </Button>
                              </HStack>
                            </HStack>
                          </VStack>
                        </CardBody>
                      </Card>
                    )}
                  </VStack>
                </TabPanel>

                {/* Search Tab */}
                <TabPanel>
                  <SearchResultsPanel
                    searchResults={searchResults}
                    searchQuery={searchQuery}
                    onResultClick={handleSearchResultClick}
                  />
                </TabPanel>

                {/* Calls Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    {stats.activeCall && (
                      <Card bg="red.50" borderColor="red.200" borderWidth="1px">
                        <CardBody>
                          <VStack spacing={4}>
                            <HStack justify="space-between" w="full">
                              <HStack>
                                <Icon as={<PhoneIcon />} color="red.600" w={6} h={6} />
                                <VStack align="start" spacing={0}>
                                  <Text fontWeight="bold" color="red.700">
                                    {callState.callType === 'video' ? 'Video Call' : 'Audio Call'}
                                  </Text>
                                  <Text fontSize="sm" color="red.600">
                                    {callState.participants.length} participants • {Math.floor(callState.duration / 60)}:{(callState.duration % 60).toString().padStart(2, '0')}
                                  </Text>
                                </VStack>
                              </HStack>
                              
                              <Badge colorScheme="red" px={3} py={1} borderRadius="full">
                                <Icon as={<RecordIcon />} w={3} h={3} mr={1} />
                                LIVE
                              </Badge>
                            </HStack>
                            
                            <HStack justify="center" spacing={4}>
                              <IconButton
                                icon={callState.isMuted ? <MicrophoneOffIcon /> : <MicrophoneIcon />}
                                onClick={toggleMute}
                                colorScheme={callState.isMuted ? "red" : "gray"}
                                aria-label="Toggle mute"
                                size="lg"
                              />
                              
                              {callState.callType === 'video' && (
                                <IconButton
                                  icon={callState.isVideoOn ? <VideoCamera /> : <VideoOffIcon />}
                                  onClick={toggleVideo}
                                  colorScheme={callState.isVideoOn ? "green" : "gray"}
                                  aria-label="Toggle video"
                                  size="lg"
                                />
                              )}
                              
                              <IconButton
                                icon={callState.isScreenSharing ? <ShareIcon /> : <ScreenIcon />}
                                onClick={toggleScreenShare}
                                colorScheme={callState.isScreenSharing ? "blue" : "gray"}
                                aria-label="Toggle screen share"
                                size="lg"
                              />
                              
                              <IconButton
                                icon={<RecordIcon />}
                                onClick={toggleRecording}
                                colorScheme={callState.isRecording ? "red" : "gray"}
                                aria-label="Toggle recording"
                                size="lg"
                              />
                              
                              <IconButton
                                icon={<PhoneOffIcon />}
                                onClick={endCall}
                                colorScheme="red"
                                aria-label="End call"
                                size="lg"
                              />
                            </HStack>
                            
                            {callState.participants.length > 0 && (
                              <Box>
                                <Text fontSize="sm" fontWeight="medium" mb={2}>
                                  Participants ({callState.participants.length})
                                </Text>
                                <VStack spacing={2} align="start">
                                  {callState.participants.slice(0, 5).map((participant, idx) => (
                                    <HStack key={idx}>
                                      <Avatar size="xs" name={participant} />
                                      <Text fontSize="sm">{participant}</Text>
                                      {callState.isMuted && <Icon as={<MicrophoneOffIcon />} color="red.500" w={3} h={3} />}
                                    </HStack>
                                  ))}
                                  {callState.participants.length > 5 && (
                                    <Text fontSize="sm" color="gray.500">
                                      +{callState.participants.length - 5} more participants
                                    </Text>
                                  )}
                                </VStack>
                              </Box>
                            )}
                          </VStack>
                        </CardBody>
                      </Card>
                    )}
                    
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Text>Call features and history will appear here</Text>
                    </Alert>
                  </VStack>
                </TabPanel>

                {/* Files Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Text>Unified file management across platforms coming soon...</Text>
                    </Alert>
                  </VStack>
                </TabPanel>

                {/* Analytics Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Text>Multi-platform analytics and reporting coming soon...</Text>
                    </Alert>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </Box>
        </Flex>
      </Container>

      {/* Mobile Drawer */}
      <Drawer
        isOpen={isMobileDrawerOpen}
        placement="left"
        onClose={() => setIsMobileDrawerOpen(false)}
      >
        <DrawerOverlay />
        <DrawerContent>
          <DrawerHeader>
            <Heading size="md">Communication Hub</Heading>
            <DrawerCloseButton />
          </DrawerHeader>
          <DrawerBody>
            <VStack spacing={4} align="stretch">
              {/* Workspaces */}
              <VStack align="start" spacing={2}>
                <Text fontWeight="medium">Workspaces</Text>
                {workspaces.slice(0, 5).map((workspace) => (
                  <Button
                    key={workspace.id}
                    variant={selectedWorkspace?.id === workspace.id ? 'solid' : 'outline'}
                    justifyContent="flex-start"
                    onClick={() => {
                      setSelectedWorkspace(workspace);
                      setIsMobileDrawerOpen(false);
                    }}
                    leftIcon={<Avatar size="xs" name={workspace.name} src={workspace.icon_url} />}
                    w="full"
                  >
                    <VStack align="start" spacing={0}>
                      <HStack>
                        <Text fontSize="sm">{workspace.name}</Text>
                        <PlatformBadge platform={workspace.type} size="xs" />
                      </HStack>
                      <Text fontSize="xs" color="gray.500">
                        {workspace.platform} • {workspace.member_count} members
                      </Text>
                    </VStack>
                  </Button>
                ))}
              </VStack>
              
              {/* Channels */}
              {selectedWorkspace && (
                <VStack align="start" spacing={2}>
                  <Text fontWeight="medium">Channels</Text>
                  {channels.slice(0, 10).map((channel) => (
                    <Button
                      key={channel.id}
                      variant={selectedChannel?.id === channel.id ? 'solid' : 'ghost'}
                      justifyContent="flex-start"
                      onClick={() => {
                        setSelectedChannel(channel);
                        setIsMobileDrawerOpen(false);
                      }}
                      size="sm"
                      w="full"
                    >
                      <VStack align="start" spacing={0}>
                        <HStack>
                          <Icon 
                            as={channel.is_private ? <LockIcon /> : <UnlockIcon />} 
                            color="gray.500" 
                            w={3} h={3}
                          />
                          <Text fontSize="sm" noOfLines={1}>
                            {channel.display_name}
                          </Text>
                          {channel.unread_count > 0 && (
                            <Badge size="sm" colorScheme="red" borderRadius="full">
                              {channel.unread_count}
                            </Badge>
                          )}
                        </HStack>
                        <PlatformBadge platform={channel.platform} size="xs" />
                      </VStack>
                    </Button>
                  ))}
                </VStack>
              )}
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </CommunicationContext.Provider>
  );
};

export default EnhancedCommunicationUI;
export { useCommunication, CommunicationContext };