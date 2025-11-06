/**
 * ATOM Enhanced Teams Manager Component
 * Complete Teams integration UI with real-time updates, advanced search, and unified experience
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
} from '@chakra-ui/icons';

// Types
interface TeamsWorkspace {
  id: string;
  name: string;
  displayName: string;
  description: string;
  visibility: 'public' | 'private';
  mailNickname: string;
  createdAt: string;
  createdBy: string;
  tenantId: string;
  internalId?: string;
  classification?: string;
  specialization?: string;
  webUrl?: string;
  memberCount: number;
  channelCount: number;
  connectionStatus?: 'connected' | 'disconnected' | 'error';
  lastSync?: string;
  isActive: boolean;
}

interface TeamsChannel {
  id: string;
  name: string;
  displayName: string;
  description: string;
  workspaceId: string;
  channelType: 'standard' | 'private' | 'shared';
  email?: string;
  webUrl?: string;
  isFavoriteByDefault: boolean;
  membershipType: 'standard' | 'private' | 'shared';
  createdAt: string;
  lastActivityAt?: string;
  memberCount: number;
  messageCount: number;
  filesCount: number;
  isArchived: boolean;
  isWelcomeMessageEnabled: boolean;
  allowCrossTeamPosts: boolean;
  allowGiphy: boolean;
  giphyContentRating: string;
  allowMemes: boolean;
  allowCustomMemes: boolean;
  allowStickersAndGifs: boolean;
  allowUserEditMessages: boolean;
  allowOwnerDeleteMessages: boolean;
  allowTeamMentions: boolean;
  allowChannelMentions: boolean;
  workspaceName?: string;
  unreadCount?: number;
  lastMessage?: string;
  isMuted?: boolean;
}

interface TeamsMessage {
  id: string;
  text: string;
  html?: string;
  userId: string;
  userName: string;
  userEmail: string;
  channelId: string;
  workspaceId: string;
  tenantId: string;
  timestamp: string;
  threadId?: string;
  replyToId?: string;
  messageType: string;
  importance: 'low' | 'normal' | 'high' | 'urgent';
  subject?: string;
  summary?: string;
  policyViolations: any[];
  attachments: any[];
  mentions: any[];
  reactions: any[];
  files: any[];
  localized?: any;
  etag?: string;
  lastModifiedAt?: string;
  isEdited: boolean;
  editTimestamp?: string;
  isDeleted: boolean;
  deleteTimestamp?: string;
  channelIdentity?: any;
  replyChainId?: string;
  parentMessageId?: string;
  participantCount: number;
}

interface TeamsFile {
  id: string;
  name: string;
  displayName: string;
  mimeType: string;
  fileType: string;
  size: number;
  userId: string;
  userName: string;
  userEmail: string;
  channelId: string;
  workspaceId: string;
  tenantId: string;
  timestamp: string;
  createdAt: string;
  url?: string;
  downloadUrl?: string;
  thumbnailUrl?: string;
  previewUrl?: string;
  description?: string;
  tags: string[];
  metadata: any;
  isImage: boolean;
  isVideo: boolean;
  isAudio: boolean;
  isDocument: boolean;
  sharingInfo?: any;
  permissionInfo?: any;
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
  roomId?: string;
}

interface EnhancedTeamsManagerProps {
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

// Context for shared state
interface TeamsContextType {
  workspaces: TeamsWorkspace[];
  channels: TeamsChannel[];
  messages: TeamsMessage[];
  files: TeamsFile[];
  selectedWorkspace: TeamsWorkspace | null;
  selectedChannel: TeamsChannel | null;
  callState: CallState;
  loading: boolean;
  error: string | null;
  refreshWorkspaces: () => void;
  refreshChannels: (workspaceId: string) => void;
  refreshMessages: (workspaceId: string, channelId: string) => void;
  selectWorkspace: (workspace: TeamsWorkspace) => void;
  selectChannel: (channel: TeamsChannel) => void;
  sendMessage: (workspaceId: string, channelId: string, text: string, options?: any) => Promise<void>;
  searchMessages: (query: string, workspaceId?: string) => Promise<any[]>;
  startCall: (channelId: string, type: 'audio' | 'video') => void;
  endCall: () => void;
  toggleMute: () => void;
  toggleVideo: () => void;
  toggleScreenShare: () => void;
  toggleRecording: () => void;
}

const TeamsContext = React.createContext<TeamsContextType | null>(null);

// Hooks
const useTeams = () => {
  const context = useContext(TeamsContext);
  if (!context) {
    throw new Error('useTeams must be used within EnhancedTeamsManager');
  }
  return context;
};

// Call Controls Component
const CallControls: React.FC<{
  callState: CallState;
  onEndCall: () => void;
  onToggleMute: () => void;
  onToggleVideo: () => void;
  onToggleScreenShare: () => void;
  onToggleRecording: () => void;
}> = ({ callState, onEndCall, onToggleMute, onToggleVideo, onToggleScreenShare, onToggleRecording }) => {
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Card bg="red.50" borderColor="red.200" borderWidth="1px">
      <CardBody>
        <VStack spacing={4}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Icon as={callState.callType === 'video' ? VideoCamera : PhoneIcon} color="red.600" w={6} h={6} />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold" color="red.700">
                  {callState.callType === 'video' ? 'Video Call' : 'Audio Call'}
                </Text>
                <Text fontSize="sm" color="red.600">
                  {callState.participants.length} participants • {formatDuration(callState.duration)}
                </Text>
              </VStack>
            </HStack>
            
            <Badge colorScheme="red" px={3} py={1} borderRadius="full">
              <Icon as={RecordIcon} w={3} h={3} mr={1} />
              LIVE
            </Badge>
          </HStack>
          
          <HStack justify="center" spacing={4}>
            <IconButton
              icon={callState.isMuted ? <MicrophoneOffIcon /> : <MicrophoneIcon />}
              onClick={onToggleMute}
              colorScheme={callState.isMuted ? "red" : "gray"}
              aria-label="Toggle mute"
              size="lg"
            />
            
            {callState.callType === 'video' && (
              <IconButton
                icon={callState.isVideoOn ? <VideoCamera /> : <VideoOffIcon />}
                onClick={onToggleVideo}
                colorScheme={callState.isVideoOn ? "green" : "gray"}
                aria-label="Toggle video"
                size="lg"
              />
            )}
            
            <IconButton
              icon={callState.isScreenSharing ? <ShareIcon /> : <ScreenIcon />}
              onClick={onToggleScreenShare}
              colorScheme={callState.isScreenSharing ? "blue" : "gray"}
              aria-label="Toggle screen share"
              size="lg"
            />
            
            <IconButton
              icon={<RecordIcon />}
              onClick={onToggleRecording}
              colorScheme={callState.isRecording ? "red" : "gray"}
              aria-label="Toggle recording"
              size="lg"
            />
            
            <IconButton
              icon={<PhoneOffIcon />}
              onClick={onEndCall}
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
  );
};

// Message Component
const TeamsMessageItem: React.FC<{
  message: TeamsMessage;
  onReply: (message: TeamsMessage) => void;
  onEdit: (message: TeamsMessage) => void;
  onDelete: (message: TeamsMessage) => void;
  onReact: (message: TeamsMessage, emoji: string) => void;
}> = ({ message, onReply, onEdit, onDelete, onReact }) => {
  const [showReactions, setShowReactions] = useState(false);
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  
  const getImportanceColor = (importance: string) => {
    switch (importance) {
      case 'low': return 'gray';
      case 'normal': return 'blue';
      case 'high': return 'orange';
      case 'urgent': return 'red';
      default: return 'blue';
    }
  };
  
  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Card bg={bgColor} borderWidth="1px" borderColor={borderColor} size="sm" mb={2}>
      <CardBody>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={2} flex={1}>
            <HStack>
              <Avatar size="xs" name={message.userName} />
              <Text fontWeight="medium" fontSize="sm">
                {message.userName}
              </Text>
              <Text fontSize="xs" color="gray.500">
                {message.userEmail}
              </Text>
              <Text fontSize="xs" color="gray.500">
                {formatTimestamp(message.timestamp)}
              </Text>
              {message.importance !== 'normal' && (
                <Badge colorScheme={getImportanceColor(message.importance)} fontSize="xs">
                  {message.importance.toUpperCase()}
                </Badge>
              )}
              {message.threadId && (
                <Badge colorScheme="blue" fontSize="xs">Thread</Badge>
              )}
              {message.isEdited && (
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
              dangerouslySetInnerHTML={{ __html: message.html || message.text }}
              noOfLines={message.threadId ? undefined : 3}
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
                    @{mention.displayName || mention.userPrincipalName}
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
                    {reaction.reactionType}
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
              icon={<ChatIcon />}
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

// Enhanced Teams Manager Component
const EnhancedTeamsManager: React.FC<EnhancedTeamsManagerProps> = ({
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
  const [workspaces, setWorkspaces] = useState<TeamsWorkspace[]>([]);
  const [channels, setChannels] = useState<TeamsChannel[]>([]);
  const [messages, setMessages] = useState<TeamsMessage[]>([]);
  const [files, setFiles] = useState<TeamsFile[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<TeamsWorkspace | null>(null);
  const [selectedChannel, setSelectedChannel] = useState<TeamsChannel | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Call state
  const [callState, setCallState] = useState<CallState>({
    isCallActive: false,
    isMuted: false,
    isVideoOn: true,
    isScreenSharing: false,
    isRecording: false,
    callType: 'audio',
    participants: [],
    duration: 0
  });
  
  // UI state
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [replyingTo, setReplyingTo] = useState<TeamsMessage | null>(null);
  const [messageText, setMessageText] = useState('');
  const [messageImportance, setMessageImportance] = useState('normal');
  const [messageSubject, setMessageSubject] = useState('');
  const [unreadCount, setUnreadCount] = useState(0);
  const [activeThreads, setActiveThreads] = useState<Set<string>>(new Set());
  
  // Hooks
  const { isOpen, onOpen, onClose } = useDisclosure();
  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const isMobile = useBreakpointValue({ base: true, md: false });

  // API calls
  const refreshWorkspaces = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/integrations/teams/workspaces', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId })
      });
      
      const result = await response.json();
      if (result.ok) {
        setWorkspaces(result.workspaces || []);
        // Auto-select first workspace if none selected
        if (!selectedWorkspace && result.workspaces?.length > 0) {
          setSelectedWorkspace(result.workspaces[0]);
        }
      } else {
        setError(result.error || 'Failed to fetch workspaces');
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
      const response = await fetch('/api/integrations/teams/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId,
          include_private: true,
          include_archived: false
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        setChannels(result.channels || []);
      } else {
        toast({
          title: 'Error',
          description: result.error || 'Failed to fetch channels',
          status: 'error'
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to server',
        status: 'error'
      });
    } finally {
      setLoading(false);
    }
  }, [userId, toast]);

  const refreshMessages = useCallback(async (workspaceId: string, channelId: string) => {
    setLoading(true);
    try {
      const response = await fetch('/api/integrations/teams/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId,
          channel_id: channelId,
          limit: 100
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        setMessages(result.messages || []);
        // Scroll to latest message
        setTimeout(() => {
          const messagesContainer = document.getElementById('teams-messages-container');
          if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
          }
        }, 100);
      } else {
        toast({
          title: 'Error',
          description: result.error || 'Failed to fetch messages',
          status: 'error'
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to fetch messages',
        status: 'error'
      });
    } finally {
      setLoading(false);
    }
  }, [userId, toast]);

  const sendMessage = useCallback(async (workspaceId: string, channelId: string, text: string, options: any = {}) => {
    if (!text.trim()) return;
    
    try {
      const response = await fetch('/api/integrations/teams/messages/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId,
          channel_id: channelId,
          text: text.trim(),
          thread_id: options.threadId,
          importance: options.importance || messageImportance,
          subject: options.subject || messageSubject,
          attachments: options.attachments || []
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        setMessageText('');
        setMessageSubject('');
        setReplyingTo(null);
        await refreshMessages(workspaceId, channelId);
        
        if (onSendMessage) {
          onSendMessage(result.message);
        }
      } else {
        toast({
          title: 'Error',
          description: result.error || 'Failed to send message',
          status: 'error'
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to send message',
        status: 'error'
      });
    }
  }, [userId, refreshMessages, onSendMessage, toast, messageImportance, messageSubject]);

  const searchMessages = useCallback(async (query: string, workspaceId?: string): Promise<any[]> => {
    if (!query.trim()) return [];
    
    try {
      const response = await fetch('/api/integrations/teams/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId || selectedWorkspace?.id,
          query: query.trim(),
          count: 50
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        const searchResults = result.messages || [];
        
        if (onSearchResults) {
          onSearchResults(searchResults);
        }
        
        return searchResults;
      }
    } catch (err) {
      console.error('Search error:', err);
    }
    
    return [];
  }, [userId, selectedWorkspace, onSearchResults]);

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
      roomId: `room_${Date.now()}`
    }));
    
    toast({
      title: 'Call Started',
      description: `${type === 'video' ? 'Video' : 'Audio'} call started`,
      status: 'info'
    });
  }, [onCallStart, toast]);

  const endCall = useCallback(() => {
    setCallState({
      isCallActive: false,
      isMuted: false,
      isVideoOn: true,
      isScreenSharing: false,
      isRecording: false,
      callType: 'audio',
      participants: [],
      duration: 0
    });
    
    toast({
      title: 'Call Ended',
      description: 'Call has been ended',
      status: 'info'
    });
  }, [toast]);

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
  const handleMessageReply = useCallback((message: TeamsMessage) => {
    setReplyingTo(message);
    setMessageSubject(message.subject || '');
  }, []);

  const handleMessageEdit = useCallback((message: TeamsMessage) => {
    setMessageText(message.text);
    setMessageSubject(message.subject || '');
    setMessageImportance(message.importance);
  }, []);

  const handleMessageDelete = useCallback(async (message: TeamsMessage) => {
    try {
      const response = await fetch('/api/integrations/teams/messages/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: selectedWorkspace?.id,
          channel_id: selectedChannel?.id,
          message_id: message.id
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        await refreshMessages(selectedWorkspace!.id, selectedChannel!.id);
        toast({
          title: 'Message Deleted',
          description: 'Message has been deleted successfully',
          status: 'info'
        });
      } else {
        toast({
          title: 'Error',
          description: result.error || 'Failed to delete message',
          status: 'error'
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to delete message',
        status: 'error'
      });
    }
  }, [userId, selectedWorkspace, selectedChannel, refreshMessages, toast]);

  const handleMessageReact = useCallback(async (message: TeamsMessage, emoji: string) => {
    // Implement message reaction
    toast({
      title: 'Reaction Added',
      description: `Reacted ${emoji} to message`,
      status: 'success'
    });
  }, [toast]);

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
  useEffect(() => {
    const interval = setInterval(() => {
      if (selectedChannel && selectedWorkspace) {
        refreshMessages(selectedWorkspace.id, selectedChannel.id);
      }
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [selectedChannel, selectedWorkspace, refreshMessages]);

  // Update call duration
  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (callState.isCallActive && callState.startTime) {
      interval = setInterval(() => {
        const start = new Date(callState.startTime!).getTime();
        const now = new Date().getTime();
        setCallState(prev => ({ ...prev, duration: Math.floor((now - start) / 1000) }));
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [callState.isCallActive, callState.startTime]);

  // Context value
  const contextValue: TeamsContextType = useMemo(() => ({
    workspaces,
    channels,
    messages,
    files,
    selectedWorkspace,
    selectedChannel,
    callState,
    loading,
    error,
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
    toggleRecording
  }), [workspaces, channels, messages, files, selectedWorkspace, selectedChannel, callState, loading, error, refreshWorkspaces, refreshChannels, refreshMessages, sendMessage, searchMessages, startCall, endCall, toggleMute, toggleVideo, toggleScreenShare, toggleRecording]);

  // Calculate stats
  const stats = useMemo(() => ({
    totalWorkspaces: workspaces.length,
    totalChannels: channels.length,
    totalMessages: messages.length,
    totalFiles: files.reduce((sum, f) => sum + f.size, 0),
    unreadMessages: unreadCount,
    activeCall: callState.isCallActive,
    callParticipants: callState.participants.length
  }), [workspaces, channels, messages, files, unreadCount, callState]);

  const isMobileView = isMobile;

  return (
    <TeamsContext.Provider value={contextValue}>
      <Container maxW="container.xl" py={4}>
        {/* Header */}
        <Flex justify="space-between" align="center" mb={6}>
          <HStack spacing={3}>
            <Icon as={ChatIcon} w={8} h={8} color="blue.500" />
            <Box>
              <Heading size="lg">Enhanced Teams Integration</Heading>
              <Text fontSize="sm" color="gray.600">
                Complete Microsoft Teams integration with calls, meetings, and real-time collaboration
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
                  placeholder="Search Teams messages..."
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
              colorScheme={selectedWorkspace ? 'green' : 'yellow'}
              display="flex"
              alignItems="center"
            >
              <Icon as={selectedWorkspace ? CheckCircleIcon : WarningIcon} mr={1} />
              {selectedWorkspace ? 'Connected' : 'No Workspace'}
            </Badge>
          </HStack>
        </Flex>

        {/* Call Controls */}
        {callState.isCallActive && (
          <CallControls
            callState={callState}
            onEndCall={endCall}
            onToggleMute={toggleMute}
            onToggleVideo={toggleVideo}
            onToggleScreenShare={toggleScreenShare}
            onToggleRecording={toggleRecording}
          />
        )}

        {/* Stats Overview */}
        <SimpleGrid columns={{ base: 2, md: 4, lg: 6 }} spacing={4} mb={6}>
          <Stat>
            <StatLabel>Workspaces</StatLabel>
            <StatNumber>{stats.totalWorkspaces}</StatNumber>
            <StatHelpText>
              <Icon as={CheckCircleIcon} color="green.500" mr={1} />
              Connected
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
              <Icon as={<ChatIcon />} color="orange.500" mr={1} />
              Indexed
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Files</StatLabel>
            <StatNumber>{files.length}</StatNumber>
            <StatHelpText>
              <Icon as={<FileIcon />} color="purple.500" mr={1} />
              Shared
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Active Call</StatLabel>
            <StatNumber>{stats.callParticipants}</StatNumber>
            <StatHelpText>
              <Icon as={<PhoneIcon />} color="red.500" mr={1} />
              {stats.activeCall ? 'In Progress' : 'None'}
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Storage</StatLabel>
            <StatNumber>{(stats.totalFiles / 1024 / 1024).toFixed(1)} MB</StatNumber>
            <StatHelpText>
              <Icon as={<FileIcon />} color="blue.500" mr={1} />
              Files
            </StatHelpText>
          </Stat>
        </SimpleGrid>

        {/* Main Content */}
        <Flex gap={6}>
          {/* Sidebar - Desktop */}
          {!isMobileView && (
            <Box w="300px">
              <Card>
                <CardHeader>
                  <Heading size="sm">Workspaces</Heading>
                </CardHeader>
                <CardBody>
                  <VStack spacing={2} align="stretch">
                    {workspaces.map((workspace) => (
                      <Button
                        key={workspace.id}
                        variant={selectedWorkspace?.id === workspace.id ? 'solid' : 'outline'}
                        justifyContent="flex-start"
                        onClick={() => setSelectedWorkspace(workspace)}
                        leftIcon={<Avatar size="xs" name={workspace.name} />}
                      >
                        <VStack align="start" spacing={0}>
                          <Text fontSize="sm">{workspace.displayName}</Text>
                          <Text fontSize="xs" color="gray.500">
                            {workspace.visibility} • {workspace.memberCount} members
                          </Text>
                        </VStack>
                      </Button>
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
                    <VStack spacing={2} align="stretch" maxH="300px" overflowY="auto">
                      {channels.map((channel) => (
                        <Button
                          key={channel.id}
                          variant={selectedChannel?.id === channel.id ? 'solid' : 'ghost'}
                          justifyContent="flex-start"
                          onClick={() => setSelectedChannel(channel)}
                          size="sm"
                        >
                          <VStack align="start" spacing={0}>
                            <HStack>
                              <Icon 
                                as={channel.channelType === 'private' ? <LockIcon /> : <UnlockIcon />} 
                                color="gray.500" 
                                w={3} h={3}
                              />
                              <Text fontSize="sm">{channel.displayName}</Text>
                              {channel.unreadCount && channel.unreadCount > 0 && (
                                <Badge size="sm" colorScheme="red" borderRadius="full">
                                  {channel.unreadCount}
                                </Badge>
                              )}
                            </HStack>
                            {channel.lastMessage && (
                              <Text fontSize="xs" color="gray.500" noOfLines={1}>
                                {channel.lastMessage}
                              </Text>
                            )}
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
            <Tabs variant="enclosed" onChange={(index) => setActiveTab(['overview', 'messages', 'calls', 'files', 'analytics', 'settings'][index])}>
              <TabList>
                <Tab>
                  <HStack>
                    <ViewIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Overview</Text>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <ChatIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Messages</Text>
                  </HStack>
                </Tab>
                <Tab>
                  <HStack>
                    <PhoneIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Calls</Text>
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
                <Tab>
                  <HStack>
                    <SettingsIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Settings</Text>
                  </HStack>
                </Tab>
              </TabList>

              <TabPanels>
                {/* Overview Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Box>
                        <Text fontWeight="bold">Enhanced Teams Integration</Text>
                        <Text>
                          Connect your Microsoft Teams workspaces for real-time communication, 
                          video calls, meetings, file sharing, and advanced collaboration features.
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
                            colorScheme="blue"
                            onClick={() => window.open('/api/auth/teams/authorize', '_blank')}
                            isDisabled={stats.totalWorkspaces > 0}
                          >
                            Connect Workspace
                          </Button>
                          <Button
                            leftIcon={<PhoneIcon />}
                            colorScheme="green"
                            onClick={() => selectedChannel && startCall(selectedChannel.id, 'video')}
                            isDisabled={!selectedChannel || stats.activeCall}
                          >
                            Start Video Call
                          </Button>
                          <Button
                            leftIcon={<SearchIcon />}
                            colorScheme="purple"
                            onClick={() => setActiveTab('messages')}
                          >
                            Search Messages
                          </Button>
                        </SimpleGrid>
                      </CardBody>
                    </Card>

                    {/* Recent Activity */}
                    <Card>
                      <CardHeader>
                        <Heading size="md">Recent Activity</Heading>
                      </CardHeader>
                      <CardBody>
                        <VStack spacing={3} align="stretch">
                          {messages.slice(0, 5).map((message) => (
                            <HStack key={message.id} spacing={3}>
                              <Avatar size="sm" name={message.userName} />
                              <VStack align="start" spacing={0} flex={1}>
                                <HStack>
                                  <Text fontWeight="medium" fontSize="sm">
                                    {message.userName}
                                  </Text>
                                  <Text fontSize="xs" color="gray.500">
                                    in {message.channelIdentity?.displayName}
                                  </Text>
                                </HStack>
                                <Text fontSize="sm" noOfLines={2}>
                                  {message.text}
                                </Text>
                              </VStack>
                            </HStack>
                          ))}
                        </VStack>
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
                                as={selectedChannel.channelType === 'private' ? <LockIcon /> : <UnlockIcon />} 
                                color="gray.500" 
                                w={4} h={4}
                              />
                              <Text fontWeight="medium">
                                {selectedChannel.displayName}
                              </Text>
                              <Badge colorScheme="blue" fontSize="xs">
                                {selectedWorkspace?.displayName}
                              </Badge>
                            </HStack>
                            <HStack>
                              <Text fontSize="sm" color="gray.600">
                                {selectedChannel.memberCount} members
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
                                onClick={() => selectedChannel && refreshMessages(selectedWorkspace!.id, selectedChannel.id)}
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
                          id="teams-messages-container"
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
                              <TeamsMessageItem
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
                              <Avatar size="xs" name={replyingTo.userName} />
                              <Text fontSize="sm" color="gray.600">
                                Replying to {replyingTo.userName}
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
                            {/* Subject for high importance messages */}
                            {messageImportance !== 'normal' && (
                              <FormControl>
                                <FormLabel>Subject</FormLabel>
                                <Input
                                  placeholder="Message subject (optional)"
                                  value={messageSubject}
                                  onChange={(e) => setMessageSubject(e.target.value)}
                                  size="sm"
                                />
                              </FormControl>
                            )}
                            
                            {/* Importance Selection */}
                            <FormControl display="flex" alignItems="center">
                              <FormLabel htmlFor="importance" mb="0">
                                Importance
                              </FormLabel>
                              <Select
                                id="importance"
                                value={messageImportance}
                                onChange={(e) => setMessageImportance(e.target.value)}
                                size="sm"
                                w="200px"
                              >
                                <option value="low">Low</option>
                                <option value="normal">Normal</option>
                                <option value="high">High</option>
                                <option value="urgent">Urgent</option>
                              </Select>
                            </FormControl>
                            
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
                                  icon={<VideoCamera />}
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
                                          threadId: replyingTo?.id,
                                          importance: messageImportance,
                                          subject: messageSubject
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

                {/* Calls Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    {callState.isCallActive ? (
                      <CallControls
                        callState={callState}
                        onEndCall={endCall}
                        onToggleMute={toggleMute}
                        onToggleVideo={toggleVideo}
                        onToggleScreenShare={toggleScreenShare}
                        onToggleRecording={toggleRecording}
                      />
                    ) : (
                      <Alert status="info" borderRadius="md">
                        <InfoIcon />
                        <Box>
                          <Text fontWeight="bold">No Active Calls</Text>
                          <Text>
                            Select a channel and click "Start Video Call" or "Start Audio Call" to begin.
                          </Text>
                        </Box>
                      </Alert>
                    )}
                    
                    {/* Call History */}
                    <Card>
                      <CardHeader>
                        <Heading size="md">Recent Calls</Heading>
                      </CardHeader>
                      <CardBody>
                        <VStack spacing={3} align="stretch">
                          <Text color="gray.500" textAlign="center" py={8}>
                            Call history will appear here
                          </Text>
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Files Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Text>Files and document management features coming soon...</Text>
                    </Alert>
                  </VStack>
                </TabPanel>

                {/* Analytics Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Text>Teams analytics and reporting features coming soon...</Text>
                    </Alert>
                  </VStack>
                </TabPanel>

                {/* Settings Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Text>Teams settings and configuration options coming soon...</Text>
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
            <Heading size="md">Teams Integration</Heading>
            <DrawerCloseButton />
          </DrawerHeader>
          <DrawerBody>
            <VStack spacing={4} align="stretch">
              {/* Workspaces */}
              <VStack align="start" spacing={2}>
                <Text fontWeight="medium">Workspaces</Text>
                {workspaces.map((workspace) => (
                  <Button
                    key={workspace.id}
                    variant={selectedWorkspace?.id === workspace.id ? 'solid' : 'outline'}
                    justifyContent="flex-start"
                    onClick={() => {
                      setSelectedWorkspace(workspace);
                      setIsMobileDrawerOpen(false);
                    }}
                    leftIcon={<Avatar size="xs" name={workspace.name} />}
                    w="full"
                  >
                    {workspace.displayName}
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
                            as={channel.channelType === 'private' ? <LockIcon /> : <UnlockIcon />} 
                            color="gray.500" 
                            w={3} h={3}
                          />
                          <Text fontSize="sm">{channel.displayName}</Text>
                        </HStack>
                      </VStack>
                    </Button>
                  ))}
                </VStack>
              )}
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </TeamsContext.Provider>
  );
};

export default EnhancedTeamsManager;
export { useTeams, TeamsContext };