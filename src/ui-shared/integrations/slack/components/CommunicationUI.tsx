"""
ATOM Communication UI - Slack Integration
Complete communication interface with Slack integration, mini search, and message indexing
"""

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Input,
  InputGroup,
  InputLeftElement,
  InputRightElement,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Avatar,
  useToast,
  useColorModeValue,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Select,
  Textarea,
  Switch,
  Tag,
  TagLabel,
  TagLeftIcon,
  Badge,
  SimpleGrid,
  Icon,
  Tooltip,
  Flex,
  Spacer,
  IconButton,
  Popover,
  PopoverTrigger,
  PopoverContent,
  PopoverArrow,
  PopoverHeader,
  PopoverBody,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  List,
  ListItem,
  ListIcon,
  Collapse,
  useBreakpointValue,
  Spinner,
  useOutsideClick,
} from '@chakra-ui/react';
import {
  ChatIcon,
  SearchIcon,
  SettingsIcon,
  BellIcon,
  TimeIcon,
  UserIcon,
  ChannelIcon,
  FileIcon,
  LinkIcon,
  InfoIcon,
  CheckCircleIcon,
  WarningIcon,
  EditIcon,
  DeleteIcon,
  RepeatIcon,
  ExternalLinkIcon,
  SmallCloseIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  FilterIcon,
  CloseIcon,
} from '@chakra-ui/icons';

interface Message {
  id: string;
  text: string;
  user: string;
  userName: string;
  channel: string;
  channelName: string;
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
  source: 'slack' | 'teams' | 'gmail';
}

interface SearchResult {
  id: string;
  text: string;
  user: string;
  userName: string;
  channel: string;
  channelName: string;
  ts: string;
  source: 'slack' | 'teams' | 'gmail';
  score: number;
  highlights?: string[];
}

interface Channel {
  id: string;
  name: string;
  display_name?: string;
  is_private: boolean;
  is_archived: boolean;
  is_general: boolean;
  workspace_id: string;
  workspace_name: string;
  num_members: number;
}

interface CommunicationUIProps {
  atomMemory?: any;
  atomSearch?: any;
  atomWorkflow?: any;
  userId?: string;
  onSendMessage?: (message: any) => void;
  onSearchResults?: (results: SearchResult[]) => void;
}

interface MiniSearchProps {
  onSearch: (query: string) => Promise<SearchResult[]>;
  onSelectResult: (result: SearchResult) => void;
  placeholder?: string;
  maxResults?: number;
}

interface MessageComposerProps {
  channels: Channel[];
  selectedChannel: Channel | null;
  onSendMessage: (channelId: string, message: string, thread_ts?: string) => Promise<void>;
  onChannelSelect: (channel: Channel) => void;
  isReplyingTo?: Message;
  onCancelReply?: () => void;
}

interface MessageThreadProps {
  message: Message;
  onReply: (message: Message) => void;
  onSendMessage: (channelId: string, message: string, thread_ts: string) => Promise<void>;
}

const MiniSearch: React.FC<MiniSearchProps> = ({
  onSearch,
  onSelectResult,
  placeholder = "Search messages...",
  maxResults = 8
}) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);

  const debouncedSearch = useCallback(
    debounce(async (searchQuery: string) => {
      if (!searchQuery.trim()) {
        setResults([]);
        setIsOpen(false);
        return;
      }

      setLoading(true);
      try {
        const searchResults = await onSearch(searchQuery);
        setResults(searchResults.slice(0, maxResults));
        setIsOpen(searchResults.length > 0);
        setSelectedIndex(0);
      } catch (error) {
        console.error('Search error:', error);
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300),
    [onSearch, maxResults]
  );

  useEffect(() => {
    debouncedSearch(query);
  }, [query, debouncedSearch]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!isOpen) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(prev => (prev + 1) % results.length);
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(prev => (prev - 1 + results.length) % results.length);
        break;
      case 'Enter':
        e.preventDefault();
        if (results[selectedIndex]) {
          onSelectResult(results[selectedIndex]);
          setIsOpen(false);
          setQuery('');
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        break;
    }
  }, [isOpen, results, selectedIndex, onSelectResult]);

  const formatTimestamp = (ts: string) => {
    const date = new Date(parseFloat(ts) * 1000);
    return date.toLocaleString();
  };

  const getSourceIcon = (source: string) => {
    switch (source) {
      case 'slack': return ChatIcon;
      case 'teams': return '🎯';
      case 'gmail': return '📧';
      default: return ChatIcon;
    }
  };

  return (
    <Box position="relative">
      <InputGroup>
        <InputLeftElement>
          <Icon as={SearchIcon} color="gray.400" />
        </InputLeftElement>
        <Input
          ref={searchRef}
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => query && results.length > 0 && setIsOpen(true)}
        />
        {loading && (
          <InputRightElement>
            <Spinner size="sm" />
          </InputRightElement>
        )}
      </InputGroup>

      {isOpen && results.length > 0 && (
        <Box
          position="absolute"
          top="100%"
          left={0}
          right={0}
          bg="white"
          border="1px solid"
          borderColor="gray.200"
          borderRadius="md"
          boxShadow="lg"
          zIndex={1000}
          mt={2}
        >
          {results.map((result, index) => {
            const SourceIcon = getSourceIcon(result.source);
            return (
              <Box
                key={result.id}
                py={2}
                px={3}
                cursor="pointer"
                bg={index === selectedIndex ? 'gray.100' : 'transparent'}
                _hover={{ bg: 'gray.100' }}
                onClick={() => {
                  onSelectResult(result);
                  setIsOpen(false);
                  setQuery('');
                }}
              >
                <HStack spacing={2} align="start">
                  <Icon as={SourceIcon} color="gray.500" mt={1} />
                  <VStack align="start" spacing={1} flex={1}>
                    <Text fontSize="sm" fontWeight="medium" noOfLines={1}>
                      {result.userName}
                    </Text>
                    <Text fontSize="xs" color="gray.600" noOfLines={2}>
                      {result.text}
                    </Text>
                    <HStack spacing={2}>
                      <Text fontSize="xs" color="gray.500">
                        #{result.channelName}
                      </Text>
                      <Text fontSize="xs" color="gray.500">
                        {formatTimestamp(result.ts)}
                      </Text>
                    </HStack>
                  </VStack>
                </HStack>
              </Box>
            );
          })}
        </Box>
      )}
    </Box>
  );
};

const MessageThread: React.FC<MessageThreadProps> = ({
  message,
  onReply,
  onSendMessage
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [threadMessages, setThreadMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const bgColor = useColorModeValue('gray.50', 'gray.700');

  const formatTimestamp = (ts: string) => {
    const date = new Date(parseFloat(ts) * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const loadThread = useCallback(async () => {
    if (!message.thread_ts) return;
    
    setLoading(true);
    try {
      const response = await fetch('/api/integrations/slack/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: 'default-user',
          workspace_id: message.team,
          channel_id: message.channel,
          thread_ts: message.thread_ts
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        setThreadMessages(result.messages || []);
      }
    } catch (error) {
      console.error('Error loading thread:', error);
    } finally {
      setLoading(false);
    }
  }, [message]);

  return (
    <Card bg={bgColor} size="sm" mb={2}>
      <CardBody>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={2} flex={1}>
            <HStack>
              <Avatar size="xs" name={message.userName} />
              <Text fontWeight="medium" fontSize="sm">
                {message.userName}
              </Text>
              <Text fontSize="xs" color="gray.500">
                {formatTimestamp(message.ts)}
              </Text>
              <Badge colorScheme="purple" fontSize="xs">
                Thread
              </Badge>
            </HStack>
            
            <Text fontSize="sm" noOfLines={isExpanded ? undefined : 2}>
              {message.text}
            </Text>
            
            {message.has_files && (
              <HStack>
                <FileIcon color="blue.500" />
                <Text fontSize="xs" color="blue.500">
                  {message.files.length} file(s)
                </Text>
              </HStack>
            )}
            
            {message.has_reactions && (
              <HStack spacing={1}>
                {message.reactions.slice(0, 3).map((reaction, idx) => (
                  <Tag key={idx} size="sm" variant="outline">
                    {reaction.name}
                    <TagLabel>{reaction.count}</TagLabel>
                  </Tag>
                ))}
              </HStack>
            )}
          </VStack>
          
          <VStack spacing={2}>
            <IconButton
              size="xs"
              variant="ghost"
              icon={isExpanded ? <ChevronUpIcon /> : <ChevronDownIcon />}
              onClick={() => {
                if (!isExpanded && threadMessages.length === 0) {
                  loadThread();
                }
                setIsExpanded(!isExpanded);
              }}
              aria-label="Toggle thread"
            />
            
            <IconButton
              size="xs"
              variant="ghost"
              icon={<ChatIcon />}
              onClick={() => onReply(message)}
              aria-label="Reply"
            />
          </VStack>
        </HStack>
        
        <Collapse in={isExpanded} animateOpacity>
          <VStack align="stretch" spacing={2} mt={3}>
            {loading && <Spinner size="sm" />}
            {threadMessages.map((threadMsg) => (
              <HStack key={threadMsg.id} spacing={2}>
                <Avatar size="xs" name={threadMsg.userName} />
                <VStack align="start" spacing={1} flex={1}>
                  <HStack>
                    <Text fontWeight="medium" fontSize="xs">
                      {threadMsg.userName}
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      {formatTimestamp(threadMsg.ts)}
                    </Text>
                  </HStack>
                  <Text fontSize="sm">{threadMsg.text}</Text>
                </VStack>
              </HStack>
            ))}
          </VStack>
        </Collapse>
      </CardBody>
    </Card>
  );
};

const MessageComposer: React.FC<MessageComposerProps> = ({
  channels,
  selectedChannel,
  onSendMessage,
  onChannelSelect,
  isReplyingTo,
  onCancelReply
}) => {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const toast = useToast();

  const handleSend = useCallback(async () => {
    if (!message.trim() || !selectedChannel) return;
    
    setLoading(true);
    try {
      await onSendMessage(
        selectedChannel.id,
        message,
        isReplyingTo?.thread_ts
      );
      setMessage('');
      if (onCancelReply) onCancelReply();
    } catch (error) {
      toast({
        title: 'Error sending message',
        description: 'Failed to send message. Please try again.',
        status: 'error'
      });
    } finally {
      setLoading(false);
    }
  }, [message, selectedChannel, onSendMessage, isReplyingTo, onCancelReply, toast]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }, [handleSend]);

  return (
    <Card>
      <CardBody>
        {isReplyingTo && (
          <HStack spacing={2} mb={3} p={2} bg="gray.50" borderRadius="md">
            <Avatar size="xs" name={isReplyingTo.userName} />
            <Text fontSize="sm" color="gray.600">
              Replying to {isReplyingTo.userName}
            </Text>
            <Spacer />
            <IconButton
              size="xs"
              variant="ghost"
              icon={<SmallCloseIcon />}
              onClick={onCancelReply}
              aria-label="Cancel reply"
            />
          </HStack>
        )}
        
        <FormControl>
          <FormLabel>Channel</FormLabel>
          <Select
            placeholder="Select a channel"
            value={selectedChannel?.id || ''}
            onChange={(e) => {
              const channel = channels.find(c => c.id === e.target.value);
              if (channel) onChannelSelect(channel);
            }}
            mb={3}
          >
            {channels.map((channel) => (
              <option key={channel.id} value={channel.id}>
                #{channel.name}
                {channel.is_private && ' (private)'}
              </option>
            ))}
          </Select>
        </FormControl>
        
        <Textarea
          placeholder="Type your message..."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          isDisabled={!selectedChannel || loading}
          rows={3}
          mb={3}
        />
        
        <HStack>
          <Button
            colorScheme="blue"
            onClick={handleSend}
            isLoading={loading}
            isDisabled={!message.trim() || !selectedChannel}
          >
            Send
          </Button>
          
          {isReplyingTo && (
            <Button
              variant="outline"
              onClick={onCancelReply}
            >
              Cancel Reply
            </Button>
          )}
        </HStack>
      </CardBody>
    </Card>
  );
};

const CommunicationUI: React.FC<CommunicationUIProps> = ({
  atomMemory,
  atomSearch,
  atomWorkflow,
  userId = 'default-user',
  onSendMessage,
  onSearchResults
}) => {
  // State management
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selectedChannel, setSelectedChannel] = useState<Channel | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [isComposing, setIsComposing] = useState(false);
  const [replyingTo, setReplyingTo] = useState<Message | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filters, setFilters] = useState({
    channel_id: '',
    date_range: 'today',
    has_files: false,
    has_reactions: false,
    is_starred: false
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  // Utility functions
  const formatTimestamp = (ts: string) => {
    const date = new Date(parseFloat(ts) * 1000);
    return date.toLocaleString();
  };

  const getSourceColor = (source: string) => {
    switch (source) {
      case 'slack': return 'purple';
      case 'teams': return 'blue';
      case 'gmail': return 'red';
      default: return 'gray';
    }
  };

  // Load channels
  const loadChannels = useCallback(async () => {
    try {
      const response = await fetch('/api/integrations/slack/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: 'default-workspace'
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        setChannels(result.channels || []);
        if (!selectedChannel && result.channels.length > 0) {
          setSelectedChannel(result.channels[0]);
        }
      }
    } catch (error) {
      toast({
        title: 'Error loading channels',
        description: 'Failed to load Slack channels.',
        status: 'error'
      });
    }
  }, [userId, selectedChannel, toast]);

  // Load messages for selected channel
  const loadMessages = useCallback(async () => {
    if (!selectedChannel) return;
    
    setLoading(true);
    try {
      const response = await fetch('/api/integrations/slack/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: selectedChannel.workspace_id,
          channel_id: selectedChannel.id,
          filters
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        setMessages(result.messages || []);
      }
    } catch (error) {
      toast({
        title: 'Error loading messages',
        description: 'Failed to load messages for channel.',
        status: 'error'
      });
    } finally {
      setLoading(false);
    }
  }, [selectedChannel, userId, filters, toast]);

  // Send message
  const sendMessage = useCallback(async (channelId: string, message: string, thread_ts?: string) => {
    try {
      const response = await fetch('/api/integrations/slack/messages/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: selectedChannel?.workspace_id,
          channel_id: channelId,
          text: message,
          thread_ts
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        // Refresh messages
        await loadMessages();
        
        if (onSendMessage) {
          onSendMessage(result.message);
        }
      } else {
        throw new Error(result.error || 'Failed to send message');
      }
    } catch (error) {
      throw error;
    }
  }, [userId, selectedChannel, loadMessages, onSendMessage]);

  // Search messages
  const searchMessages = useCallback(async (query: string) => {
    try {
      const response = await fetch('/api/integrations/slack/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: 'default-workspace',
          query
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        const results = (result.messages || []).map((msg: Message) => ({
          ...msg,
          source: 'slack' as const,
          score: 1.0
        }));
        setSearchResults(results);
        
        if (onSearchResults) {
          onSearchResults(results);
        }
        
        return results;
      }
    } catch (error) {
      console.error('Search error:', error);
    }
    
    return [];
  }, [userId, onSearchResults]);

  // Handle search result selection
  const handleSearchResultSelect = useCallback((result: SearchResult) => {
    // Find and select the channel
    const channel = channels.find(c => c.id === result.channel);
    if (channel) {
      setSelectedChannel(channel);
    }
    
    // Scroll to message after messages load
    setTimeout(() => {
      const element = document.getElementById(`message-${result.id}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        element.style.border = '2px solid #4299E1';
        setTimeout(() => {
          element.style.border = '';
        }, 2000);
      }
    }, 1000);
  }, [channels]);

  // Initialize
  useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  useEffect(() => {
    if (selectedChannel) {
      loadMessages();
    }
  }, [selectedChannel, loadMessages]);

  // Filter messages
  const filteredMessages = useMemo(() => {
    return messages.filter(msg => {
      if (filters.is_starred && !msg.is_starred) return false;
      if (filters.has_files && !msg.has_files) return false;
      if (filters.has_reactions && !msg.has_reactions) return false;
      return true;
    });
  }, [messages, filters]);

  return (
    <Card bg={bgColor} borderWidth="1px" borderColor={borderColor}>
      <CardHeader>
        <HStack justify="space-between">
          <HStack>
            <Icon as={ChatIcon} w={6} h={6} color="blue.500" />
            <Heading size="md">Communication Hub</Heading>
            {unreadCount > 0 && (
              <Badge colorScheme="red" borderRadius="full">
                {unreadCount}
              </Badge>
            )}
          </HStack>
          
          <HStack>
            <MiniSearch
              onSearch={searchMessages}
              onSelectResult={handleSearchResultSelect}
              placeholder="Search all messages..."
            />
            
            <Popover>
              <PopoverTrigger>
                <IconButton
                  variant="outline"
                  icon={<FilterIcon />}
                  aria-label="Filters"
                />
              </PopoverTrigger>
              <PopoverContent>
                <PopoverArrow />
                <PopoverHeader>Message Filters</PopoverHeader>
                <PopoverBody>
                  <VStack align="start" spacing={3}>
                    <FormControl display="flex" alignItems="center">
                      <FormLabel htmlFor="has_files" mb="0">
                        Has Files
                      </FormLabel>
                      <Switch
                        id="has_files"
                        isChecked={filters.has_files}
                        onChange={(e) => setFilters(prev => ({
                          ...prev,
                          has_files: e.target.checked
                        }))}
                      />
                    </FormControl>
                    
                    <FormControl display="flex" alignItems="center">
                      <FormLabel htmlFor="has_reactions" mb="0">
                        Has Reactions
                      </FormLabel>
                      <Switch
                        id="has_reactions"
                        isChecked={filters.has_reactions}
                        onChange={(e) => setFilters(prev => ({
                          ...prev,
                          has_reactions: e.target.checked
                        }))}
                      />
                    </FormControl>
                    
                    <FormControl display="flex" alignItems="center">
                      <FormLabel htmlFor="is_starred" mb="0">
                        Starred
                      </FormLabel>
                      <Switch
                        id="is_starred"
                        isChecked={filters.is_starred}
                        onChange={(e) => setFilters(prev => ({
                          ...prev,
                          is_starred: e.target.checked
                        }))}
                      />
                    </FormControl>
                  </VStack>
                </PopoverBody>
              </PopoverContent>
            </Popover>
            
            <IconButton
              variant="outline"
              icon={<RepeatIcon />}
              onClick={loadMessages}
              aria-label="Refresh messages"
            />
            
            <IconButton
              variant="outline"
              icon={isComposing ? <CloseIcon /> : <EditIcon />}
              onClick={() => setIsComposing(!isComposing)}
              aria-label={isComposing ? 'Close composer' : 'Open composer'}
            />
          </HStack>
        </HStack>
      </CardHeader>

      <CardBody>
        <VStack spacing={4} align="stretch">
          {/* Channel Selection */}
          {selectedChannel && (
            <Card size="sm" variant="outline">
              <CardBody>
                <HStack>
                  <ChannelIcon />
                  <Text fontWeight="medium">
                    #{selectedChannel.name}
                  </Text>
                  <Badge colorScheme="purple" fontSize="xs">
                    Slack
                  </Badge>
                  <Spacer />
                  <Text fontSize="sm" color="gray.600">
                    {selectedChannel.num_members} members
                  </Text>
                </HStack>
              </CardBody>
            </Card>
          )}

          {/* Messages */}
          <VStack align="stretch" spacing={2} maxH="500px" overflowY="auto">
            {loading && <Spinner />}
            
            {filteredMessages.length === 0 && !loading && (
              <Text color="gray.500" textAlign="center" py={8}>
                No messages found
              </Text>
            )}
            
            {filteredMessages.map((message) => (
              <Card
                key={message.id}
                id={`message-${message.id}`}
                size="sm"
                variant="outline"
                _hover={{ shadow: 'md' }}
                transition="all 0.2s"
              >
                <CardBody>
                  <HStack justify="space-between" align="start">
                    <VStack align="start" spacing={2} flex={1}>
                      <HStack>
                        <Avatar size="xs" name={message.userName} />
                        <Text fontWeight="medium" fontSize="sm">
                          {message.userName}
                        </Text>
                        <Text fontSize="xs" color="gray.500">
                          {formatTimestamp(message.ts)}
                        </Text>
                        <Badge colorScheme={getSourceColor(message.source)} fontSize="xs">
                          {message.source.toUpperCase()}
                        </Badge>
                        {message.is_starred && (
                          <Icon as={StarIcon} color="yellow.500" />
                        )}
                      </HStack>
                      
                      <Text fontSize="sm">{message.text}</Text>
                      
                      {/* File attachments */}
                      {message.has_files && (
                        <HStack spacing={2}>
                          <FileIcon color="blue.500" />
                          {message.files.slice(0, 2).map((file, idx) => (
                            <Tag key={idx} size="sm" colorScheme="blue">
                              <TagLabel>{file.name}</TagLabel>
                            </Tag>
                          ))}
                        </HStack>
                      )}
                      
                      {/* Reactions */}
                      {message.has_reactions && (
                        <HStack spacing={1}>
                          {message.reactions.slice(0, 3).map((reaction, idx) => (
                            <Tag key={idx} size="sm" variant="outline">
                              {reaction.name}
                              <TagLabel>{reaction.count}</TagLabel>
                            </Tag>
                          ))}
                        </HStack>
                      )}
                    </VStack>
                    
                    <VStack spacing={1}>
                      <IconButton
                        size="xs"
                        variant="ghost"
                        icon={<ChatIcon />}
                        onClick={() => setReplyingTo(message)}
                        aria-label="Reply"
                      />
                      {message.thread_ts && (
                        <MessageThread
                          message={message}
                          onReply={setReplyingTo}
                          onSendMessage={sendMessage}
                        />
                      )}
                    </VStack>
                  </HStack>
                </CardBody>
              </Card>
            ))}
          </VStack>

          {/* Message Composer */}
          {(isComposing || replyingTo) && (
            <MessageComposer
              channels={channels}
              selectedChannel={selectedChannel}
              onSendMessage={sendMessage}
              onChannelSelect={setSelectedChannel}
              isReplyingTo={replyingTo}
              onCancelReply={() => setReplyingTo(null)}
            />
          )}
        </VStack>
      </CardBody>
    </Card>
  );
};

// Utility function for debouncing
function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return (...args: Parameters<T>) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}

export default CommunicationUI;
export { MiniSearch, MessageThread, MessageComposer };