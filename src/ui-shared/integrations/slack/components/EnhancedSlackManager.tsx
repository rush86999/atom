/**
 * ATOM Enhanced Slack Manager Component
 * Complete Slack integration UI with real-time updates, mini search, and workflow automation
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
  ChannelIcon,
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
} from '@chakra-ui/icons';

// Types
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
  connection_status?: 'connected' | 'disconnected' | 'error';
  last_sync?: string;
  user_id?: string;
  bot_id?: string;
  member_count?: number;
  channel_count?: number;
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
  created: string;
  workspace_id: string;
  workspace_name?: string;
  unread_count?: number;
  last_message?: string;
  is_muted?: boolean;
}

interface SlackMessage {
  id: string;
  text: string;
  user_id: string;
  user_name: string;
  channel_id: string;
  channel_name: string;
  team_id: string;
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
  created_at: string;
  bot_profile?: any;
  mentions?: string[];
}

interface SlackFile {
  id: string;
  name: string;
  title: string;
  mimetype: string;
  filetype: string;
  pretty_type: string;
  size: number;
  user_id: string;
  username?: string;
  url_private: string;
  permalink: string;
  created: string;
  timestamp: string;
  is_public: boolean;
  public_url_shared: boolean;
  thumb_64?: string;
  thumb_360?: string;
  workspace_id: string;
  uploader_name?: string;
}

interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  triggers: any[];
  actions: any[];
  active: boolean;
  execution_count: number;
  last_executed?: string;
  created_by: string;
  created_at: string;
}

interface IngestionStatus {
  running: boolean;
  progress: number;
  stage: string;
  message: string;
  items_processed?: number;
  total_items?: number;
  started_at?: string;
  completed_at?: string;
  error?: string;
}

interface MiniSearchResult {
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

interface EnhancedSlackManagerProps {
  atomIngestionPipeline?: any;
  atomMemory?: any;
  atomSearch?: any;
  atomWorkflow?: any;
  onIntegrationUpdate?: (data: any) => void;
  onSendMessage?: (message: any) => void;
  onSearchResults?: (results: MiniSearchResult[]) => void;
  userId?: string;
}

// Context for shared state
interface SlackContextType {
  workspaces: SlackWorkspace[];
  channels: SlackChannel[];
  messages: SlackMessage[];
  files: SlackFile[];
  selectedWorkspace: SlackWorkspace | null;
  selectedChannel: SlackChannel | null;
  loading: boolean;
  error: string | null;
  refreshWorkspaces: () => void;
  refreshChannels: (workspaceId: string) => void;
  refreshMessages: (workspaceId: string, channelId: string) => void;
  selectWorkspace: (workspace: SlackWorkspace) => void;
  selectChannel: (channel: SlackChannel) => void;
  sendMessage: (workspaceId: string, channelId: string, text: string) => Promise<void>;
  searchMessages: (query: string, workspaceId?: string) => Promise<MiniSearchResult[]>;
}

const SlackContext = React.createContext<SlackContextType | null>(null);

// Hooks
const useSlack = () => {
  const context = useContext(SlackContext);
  if (!context) {
    throw new Error('useSlack must be used within EnhancedSlackManager');
  }
  return context;
};

// Mini Search Component
const MiniSearch: React.FC<{
  onSearch: (query: string) => Promise<MiniSearchResult[]>;
  onSelectResult: (result: MiniSearchResult) => void;
  placeholder?: string;
  maxResults?: number;
}> = ({ onSearch, onSelectResult, placeholder = "Search Slack messages...", maxResults = 8 }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<MiniSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);
  const bgColor = useColorModeValue('white', 'gray.800');

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

  return (
    <Box position="relative" w="full">
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
          bg={bgColor}
        />
        {loading && (
          <InputRightElement>
            <Icon as={RepeatIcon} color="blue.500" animation="spin" />
          </InputRightElement>
        )}
      </InputGroup>

      {isOpen && results.length > 0 && (
        <Box
          position="absolute"
          top="100%"
          left={0}
          right={0}
          bg={bgColor}
          border="1px solid"
          borderColor="gray.200"
          borderRadius="md"
          boxShadow="lg"
          zIndex={1000}
          mt={2}
          maxH="400px"
          overflowY="auto"
        >
          {results.map((result, index) => (
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
                <Icon as={ChatIcon} color="purple.500" mt={1} />
                <VStack align="start" spacing={1} flex={1}>
                  <HStack>
                    <Text fontWeight="medium" fontSize="sm">
                      {result.userName}
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      #{result.channelName}
                    </Text>
                  </HStack>
                  <Text fontSize="sm" noOfLines={2}>
                    {result.text}
                  </Text>
                  <Text fontSize="xs" color="gray.400">
                    {formatTimestamp(result.ts)}
                  </Text>
                </VStack>
              </HStack>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
};

// Message Component
const MessageItem: React.FC<{
  message: SlackMessage;
  onReply: (message: SlackMessage) => void;
  onReact: (message: SlackMessage, emoji: string) => void;
  onStar: (message: SlackMessage) => void;
}> = ({ message, onReply, onReact, onStar }) => {
  const [showReactions, setShowReactions] = useState(false);
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  const formatTimestamp = (ts: string) => {
    const date = new Date(parseFloat(ts) * 1000);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Card bg={bgColor} borderWidth="1px" borderColor={borderColor} size="sm" mb={2}>
      <CardBody>
        <HStack justify="space-between" align="start">
          <VStack align="start" spacing={2} flex={1}>
            <HStack>
              <Avatar size="xs" name={message.user_name} />
              <Text fontWeight="medium" fontSize="sm">
                {message.user_name}
              </Text>
              <Text fontSize="xs" color="gray.500">
                {formatTimestamp(message.ts)}
              </Text>
              {message.thread_ts && (
                <Badge colorScheme="blue" fontSize="xs">Thread</Badge>
              )}
              {message.bot_profile && (
                <Badge colorScheme="purple" fontSize="xs">Bot</Badge>
              )}
            </HStack>
            
            <Text fontSize="sm" noOfLines={message.thread_ts ? undefined : 3}>
              {message.text}
            </Text>
            
            {message.has_files && (
              <HStack>
                <Icon as={FileIcon} color="blue.500" />
                <Text fontSize="xs" color="blue.500">
                  {message.files.length} file(s)
                </Text>
              </HStack>
            )}
            
            {message.has_reactions && (
              <HStack spacing={1} flexWrap="wrap">
                {message.reactions.slice(0, 3).map((reaction, idx) => (
                  <Tag key={idx} size="sm" variant="outline">
                    {reaction.name}
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
                  icon={<SmileIcon />}
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
              icon={message.is_starred ? <StarIcon color="yellow.500" /> : <StarIcon />}
              onClick={() => onStar(message)}
              aria-label="Star"
            />
            
            <IconButton
              size="xs"
              variant="ghost"
              icon={<ChatIcon />}
              onClick={() => onReply(message)}
              aria-label="Reply"
            />
          </HStack>
        </HStack>
      </CardBody>
    </Card>
  );
};

// Workflow Automation Component
const WorkflowAutomation: React.FC<{
  workflows: WorkflowDefinition[];
  onCreateWorkflow: (workflow: Partial<WorkflowDefinition>) => void;
  onEditWorkflow: (workflow: WorkflowDefinition) => void;
  onDeleteWorkflow: (workflowId: string) => void;
  onExecuteWorkflow: (workflowId: string) => void;
}> = ({ workflows, onCreateWorkflow, onEditWorkflow, onDeleteWorkflow, onExecuteWorkflow }) => {
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [editingWorkflow, setEditingWorkflow] = useState<WorkflowDefinition | null>(null);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    active: true
  });

  const handleSubmit = () => {
    if (editingWorkflow) {
      onEditWorkflow({ ...editingWorkflow, ...formData });
    } else {
      onCreateWorkflow(formData);
    }
    setFormData({ name: '', description: '', active: true });
    setEditingWorkflow(null);
    onClose();
  };

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString();
  };

  return (
    <VStack spacing={4} align="stretch">
      <HStack justify="space-between">
        <Heading size="md">Workflow Automation</Heading>
        <Button
          leftIcon={<AddIcon />}
          onClick={onOpen}
          colorScheme="purple"
        >
          Create Workflow
        </Button>
      </HStack>

      <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
        {workflows.map((workflow) => (
          <Card key={workflow.id} variant="outline">
            <CardBody>
              <VStack spacing={3} align="stretch">
                <HStack justify="space-between">
                  <Text fontWeight="bold">{workflow.name}</Text>
                  <Switch
                    isChecked={workflow.active}
                    onChange={() => onEditWorkflow({ ...workflow, active: !workflow.active })}
                    size="sm"
                  />
                </HStack>
                
                <Text fontSize="sm" color="gray.600" noOfLines={2}>
                  {workflow.description}
                </Text>
                
                <HStack spacing={2} fontSize="sm">
                  <Tag size="sm">
                    <TagLabel>{workflow.triggers.length} triggers</TagLabel>
                  </Tag>
                  <Tag size="sm">
                    <TagLabel>{workflow.actions.length} actions</TagLabel>
                  </Tag>
                  <Tag size="sm" colorScheme={workflow.active ? 'green' : 'gray'}>
                    <TagLabel>{workflow.active ? 'Active' : 'Inactive'}</TagLabel>
                  </Tag>
                </HStack>
                
                <HStack spacing={2} fontSize="sm" color="gray.500">
                  <Text>Executed: {workflow.execution_count}</Text>
                  {workflow.last_executed && (
                    <Text>Last: {formatTimestamp(workflow.last_executed)}</Text>
                  )}
                </HStack>
                
                <HStack spacing={2}>
                  <Button
                    size="sm"
                    leftIcon={<PlayIcon />}
                    onClick={() => onExecuteWorkflow(workflow.id)}
                    isDisabled={!workflow.active}
                  >
                    Run
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    leftIcon={<EditIcon />}
                    onClick={() => {
                      setEditingWorkflow(workflow);
                      setFormData({
                        name: workflow.name,
                        description: workflow.description,
                        active: workflow.active
                      });
                      onOpen();
                    }}
                  >
                    Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    leftIcon={<DeleteIcon />}
                    onClick={() => onDeleteWorkflow(workflow.id)}
                    colorScheme="red"
                  >
                    Delete
                  </Button>
                </HStack>
              </VStack>
            </CardBody>
          </Card>
        ))}
      </SimpleGrid>

      {/* Create/Edit Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {editingWorkflow ? 'Edit Workflow' : 'Create Workflow'}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Workflow Name</FormLabel>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="Enter workflow name"
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Describe what this workflow does"
                  rows={3}
                />
              </FormControl>
              
              <FormControl display="flex" alignItems="center">
                <FormLabel htmlFor="active" mb="0">
                  Active
                </FormLabel>
                <Switch
                  id="active"
                  isChecked={formData.active}
                  onChange={(e) => setFormData({ ...formData, active: e.target.checked })}
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="outline" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button
              colorScheme="purple"
              onClick={handleSubmit}
              isDisabled={!formData.name.trim()}
            >
              {editingWorkflow ? 'Update' : 'Create'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </VStack>
  );
};

// Enhanced Slack Manager Component
const EnhancedSlackManager: React.FC<EnhancedSlackManagerProps> = ({
  atomIngestionPipeline,
  atomMemory,
  atomSearch,
  atomWorkflow,
  onIntegrationUpdate,
  onSendMessage,
  onSearchResults,
  userId = 'default-user'
}) => {
  // Core state
  const [workspaces, setWorkspaces] = useState<SlackWorkspace[]>([]);
  const [channels, setChannels] = useState<SlackChannel[]>([]);
  const [messages, setMessages] = useState<SlackMessage[]>([]);
  const [files, setFiles] = useState<SlackFile[]>([]);
  const [selectedWorkspace, setSelectedWorkspace] = useState<SlackWorkspace | null>(null);
  const [selectedChannel, setSelectedChannel] = useState<SlackChannel | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // UI state
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<MiniSearchResult[]>([]);
  const [replyingTo, setReplyingTo] = useState<SlackMessage | null>(null);
  const [messageText, setMessageText] = useState('');
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    stage: 'idle',
    message: ''
  });
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
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
      const response = await fetch('/api/integrations/slack/workspaces', {
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
      const response = await fetch('/api/integrations/slack/channels', {
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
      const response = await fetch('/api/integrations/slack/messages', {
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
          const messagesContainer = document.getElementById('messages-container');
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

  const sendMessage = useCallback(async (workspaceId: string, channelId: string, text: string, thread_ts?: string) => {
    if (!text.trim()) return;
    
    try {
      const response = await fetch('/api/integrations/slack/messages/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workspace_id: workspaceId,
          channel_id: channelId,
          text: text.trim(),
          thread_ts
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        setMessageText('');
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
  }, [userId, refreshMessages, onSendMessage, toast]);

  const searchMessages = useCallback(async (query: string, workspaceId?: string): Promise<MiniSearchResult[]> => {
    if (!query.trim()) return [];
    
    try {
      const response = await fetch('/api/integrations/slack/search', {
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
        const searchResults = (result.messages || []).map((msg: SlackMessage) => ({
          id: msg.id,
          text: msg.text,
          user: msg.user_id,
          userName: msg.user_name,
          channel: msg.channel_id,
          channelName: msg.channel_name,
          ts: msg.ts,
          source: 'slack' as const,
          score: 1.0
        }));
        
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

  // Context value
  const contextValue: SlackContextType = useMemo(() => ({
    workspaces,
    channels,
    messages,
    files,
    selectedWorkspace,
    selectedChannel,
    loading,
    error,
    refreshWorkspaces,
    refreshChannels,
    refreshMessages,
    selectWorkspace: setSelectedWorkspace,
    selectChannel: setSelectedChannel,
    sendMessage,
    searchMessages
  }), [workspaces, channels, messages, files, selectedWorkspace, selectedChannel, loading, error, refreshWorkspaces, refreshChannels, refreshMessages, sendMessage, searchMessages]);

  // Handlers
  const handleSearchResultSelect = useCallback((result: MiniSearchResult) => {
    // Find and switch to the channel
    const channel = channels.find(c => c.id === result.channel);
    if (channel) {
      setSelectedChannel(channel);
    }
    
    // Highlight the message
    setTimeout(() => {
      const element = document.getElementById(`message-${result.id}`);
      if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        element.style.border = '2px solid #4299E1';
        setTimeout(() => {
          element.style.border = '';
        }, 2000);
      }
    }, 500);
  }, [channels]);

  const handleMessageReact = useCallback(async (message: SlackMessage, emoji: string) => {
    // Implement message reaction
    toast({
      title: 'Reaction Added',
      description: `Reacted ${emoji} to message`,
      status: 'success'
    });
  }, [toast]);

  const handleMessageStar = useCallback(async (message: SlackMessage) => {
    // Implement message starring
    toast({
      title: message.is_starred ? 'Message Unstarred' : 'Message Starred',
      description: message.is_starred ? 'Removed from starred messages' : 'Added to starred messages',
      status: 'info'
    });
  }, [toast]);

  const handleCreateWorkflow = useCallback((workflowData: Partial<WorkflowDefinition>) => {
    const newWorkflow: WorkflowDefinition = {
      id: `workflow_${Date.now()}`,
      name: workflowData.name || '',
      description: workflowData.description || '',
      triggers: [],
      actions: [],
      active: workflowData.active || true,
      execution_count: 0,
      created_by: userId,
      created_at: new Date().toISOString()
    };
    
    setWorkflows(prev => [...prev, newWorkflow]);
    toast({
      title: 'Workflow Created',
      description: `"${newWorkflow.name}" has been created successfully`,
      status: 'success'
    });
  }, [userId, toast]);

  const handleEditWorkflow = useCallback((workflow: WorkflowDefinition) => {
    setWorkflows(prev => prev.map(w => w.id === workflow.id ? workflow : w));
    toast({
      title: 'Workflow Updated',
      description: `"${workflow.name}" has been updated successfully`,
      status: 'success'
    });
  }, [toast]);

  const handleDeleteWorkflow = useCallback((workflowId: string) => {
    const workflow = workflows.find(w => w.id === workflowId);
    setWorkflows(prev => prev.filter(w => w.id !== workflowId));
    toast({
      title: 'Workflow Deleted',
      description: `"${workflow?.name}" has been deleted`,
      status: 'info'
    });
  }, [workflows, toast]);

  const handleExecuteWorkflow = useCallback(async (workflowId: string) => {
    try {
      const response = await fetch('/api/integrations/slack/workflows/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          workflow_id: workflowId
        })
      });
      
      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Workflow Executed',
          description: `Execution started with ID: ${result.execution_id}`,
          status: 'success'
        });
      } else {
        toast({
          title: 'Error',
          description: result.error || 'Failed to execute workflow',
          status: 'error'
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to execute workflow',
        status: 'error'
      });
    }
  }, [userId, toast]);

  // Start data ingestion
  const startIngestion = useCallback(async () => {
    setIngestionStatus({
      running: true,
      progress: 0,
      stage: 'Starting',
      message: 'Initializing data ingestion...',
      items_processed: 0,
      total_items: 0
    });

    try {
      const result = await atomIngestionPipeline?.startIngestion({
        sourceType: 'slack',
        workspaceId: selectedWorkspace?.id,
        channelId: selectedChannel?.id,
        config: {
          syncOptions: {
            messageTypes: ['messages', 'replies', 'files'],
            realTimeSync: true,
            syncFrequency: 'realtime'
          },
          filters: {
            includePrivate: true,
            includeArchived: false,
            excludeBots: false
          }
        },
        callback: (status: any) => {
          setIngestionStatus(prev => ({
            ...prev,
            progress: status.progress,
            stage: status.stage,
            message: status.message,
            items_processed: status.itemsProcessed
          }));
        }
      });

      if (result?.success) {
        setIngestionStatus({
          running: false,
          progress: 100,
          stage: 'Complete',
          message: 'Data ingestion completed successfully',
          items_processed: result.itemsProcessed,
          total_items: result.totalItems,
          completed_at: new Date().toISOString()
        });
      } else {
        throw new Error(result?.error || 'Ingestion failed');
      }
    } catch (err) {
      setIngestionStatus({
        running: false,
        stage: 'Failed',
        message: 'Data ingestion failed',
        error: err instanceof Error ? err.message : 'Unknown error'
      });
    }
  }, [atomIngestionPipeline, selectedWorkspace, selectedChannel]);

  // Calculate stats
  const stats = useMemo(() => ({
    totalWorkspaces: workspaces.length,
    totalChannels: channels.length,
    totalMessages: messages.length,
    totalFiles: files.reduce((sum, f) => sum + f.size, 0),
    unreadMessages: unreadCount,
    activeWorkflows: workflows.filter(w => w.active).length
  }), [workspaces, channels, messages, files, unreadCount, workflows]);

  const isMobileView = isMobile;

  return (
    <SlackContext.Provider value={contextValue}>
      <Container maxW="container.xl" py={4}>
        {/* Header */}
        <Flex justify="space-between" align="center" mb={6}>
          <HStack spacing={3}>
            <Icon as={ChatIcon} w={8} h={8} color="purple.500" />
            <Box>
              <Heading size="lg">Enhanced Slack Integration</Heading>
              <Text fontSize="sm" color="gray.600">
                Real-time communication and workflow automation
              </Text>
            </Box>
          </HStack>
          
          <HStack spacing={3}>
            {/* Global Search */}
            <Box w={{ base: '200px', md: '300px' }}>
              <MiniSearch
                onSearch={searchMessages}
                onSelectResult={handleSearchResultSelect}
                placeholder="Search all Slack messages..."
              />
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
              <Icon as={ChannelIcon} color="blue.500" mr={1} />
              Available
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Messages</StatLabel>
            <StatNumber>{stats.totalMessages.toLocaleString()}</StatNumber>
            <StatHelpText>
              <Icon as={ChatIcon} color="orange.500" mr={1} />
              Indexed
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Files</StatLabel>
            <StatNumber>{files.length}</StatNumber>
            <StatHelpText>
              <Icon as={FileIcon} color="purple.500" mr={1} />
              Shared
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Workflows</StatLabel>
            <StatNumber>{stats.activeWorkflows}</StatNumber>
            <StatHelpText>
              <Icon as={PlayIcon} color="green.500" mr={1} />
              Active
            </StatHelpText>
          </Stat>
          
          <Stat>
            <StatLabel>Storage</StatLabel>
            <StatNumber>{(stats.totalFiles / 1024 / 1024).toFixed(1)} MB</StatNumber>
            <StatHelpText>
              <Icon as={FileIcon} color="blue.500" mr={1} />
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
                        leftIcon={<Avatar size="xs" name={workspace.name} src={workspace.icon} />}
                      >
                        <VStack align="start" spacing={0}>
                          <Text fontSize="sm">{workspace.name}</Text>
                          <Text fontSize="xs" color="gray.500">
                            {workspace.domain}.slack.com
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
                              <Text fontSize="sm">
                                {channel.is_private ? '🔒' : '#'}{channel.name}
                              </Text>
                              {channel.unread_count && channel.unread_count > 0 && (
                                <Badge size="sm" colorScheme="red" borderRadius="full">
                                  {channel.unread_count}
                                </Badge>
                              )}
                            </HStack>
                            {channel.last_message && (
                              <Text fontSize="xs" color="gray.500" noOfLines={1}>
                                {channel.last_message}
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
            <Tabs variant="enclosed" onChange={(index) => setActiveTab(['overview', 'messages', 'workflows', 'analytics', 'settings'][index])}>
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
                    <PlayIcon />
                    <Text display={{ base: 'none', md: 'inline' }}>Workflows</Text>
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
                        <Text fontWeight="bold">Enhanced Slack Integration</Text>
                        <Text>
                          Connect your Slack workspaces for real-time communication, 
                          automated workflows, and advanced search capabilities.
                        </Text>
                      </Box>
                    </Alert>

                    {/* Connection Status */}
                    <Card>
                      <CardHeader>
                        <Heading size="md">Connection Status</Heading>
                      </CardHeader>
                      <CardBody>
                        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
                          <VStack align="start" spacing={2}>
                            <Text fontWeight="medium">Active Workspaces</Text>
                            <Badge colorScheme="green" fontSize="lg" px={3} py={1}>
                              {stats.totalWorkspaces}
                            </Badge>
                          </VStack>
                          <VStack align="start" spacing={2}>
                            <Text fontWeight="medium">Connected Channels</Text>
                            <Badge colorScheme="blue" fontSize="lg" px={3} py={1}>
                              {stats.totalChannels}
                            </Badge>
                          </VStack>
                          <VStack align="start" spacing={2}>
                            <Text fontWeight="medium">Indexed Messages</Text>
                            <Badge colorScheme="orange" fontSize="lg" px={3} py={1}>
                              {stats.totalMessages.toLocaleString()}
                            </Badge>
                          </VStack>
                          <VStack align="start" spacing={2}>
                            <Text fontWeight="medium">Active Workflows</Text>
                            <Badge colorScheme="purple" fontSize="lg" px={3} py={1}>
                              {stats.activeWorkflows}
                            </Badge>
                          </VStack>
                        </SimpleGrid>
                      </CardBody>
                    </Card>

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
                            onClick={() => window.open('/api/auth/slack/authorize', '_blank')}
                            isDisabled={stats.totalWorkspaces > 0}
                          >
                            Connect Workspace
                          </Button>
                          <Button
                            leftIcon={<PlayIcon />}
                            colorScheme="green"
                            onClick={startIngestion}
                            isDisabled={!selectedWorkspace || ingestionStatus.running}
                          >
                            Start Data Ingestion
                          </Button>
                          <Button
                            leftIcon={<SearchIcon />}
                            colorScheme="blue"
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
                              <Avatar size="sm" name={message.user_name} />
                              <VStack align="start" spacing={0} flex={1}>
                                <HStack>
                                  <Text fontWeight="medium" fontSize="sm">
                                    {message.user_name}
                                  </Text>
                                  <Text fontSize="xs" color="gray.500">
                                    in #{message.channel_name}
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
                              <ChannelIcon />
                              <Text fontWeight="medium">
                                {selectedChannel.is_private ? '🔒' : '#'}{selectedChannel.name}
                              </Text>
                              <Badge colorScheme="purple" fontSize="xs">
                                {selectedWorkspace?.name}
                              </Badge>
                            </HStack>
                            <HStack>
                              <Text fontSize="sm" color="gray.600">
                                {selectedChannel.num_members} members
                              </Text>
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
                          id="messages-container"
                        >
                          {loading ? (
                            <HStack justify="center" py={8}>
                              <Icon as={RepeatIcon} animation="spin" />
                              <Text>Loading messages...</Text>
                            </HStack>
                          ) : messages.length === 0 ? (
                            <Text color="gray.500" textAlign="center" py={8}>
                              No messages in this channel
                            </Text>
                          ) : (
                            messages.map((message) => (
                              <MessageItem
                                key={message.id}
                                message={message}
                                onReply={setReplyingTo}
                                onReact={handleMessageReact}
                                onStar={handleMessageStar}
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
                              <Avatar size="xs" name={replyingTo.user_name} />
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
                                        replyingTo?.thread_ts
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

                {/* Workflows Tab */}
                <TabPanel>
                  <WorkflowAutomation
                    workflows={workflows}
                    onCreateWorkflow={handleCreateWorkflow}
                    onEditWorkflow={handleEditWorkflow}
                    onDeleteWorkflow={handleDeleteWorkflow}
                    onExecuteWorkflow={handleExecuteWorkflow}
                  />
                </TabPanel>

                {/* Analytics Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Text>Analytics and reporting features coming soon...</Text>
                    </Alert>
                    
                    <Card>
                      <CardHeader>
                        <Heading size="md">Activity Overview</Heading>
                      </CardHeader>
                      <CardBody>
                        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
                          <Stat>
                            <StatLabel>Total Messages</StatLabel>
                            <StatNumber>{stats.totalMessages.toLocaleString()}</StatNumber>
                          </Stat>
                          <Stat>
                            <StatLabel>Active Users</StatLabel>
                            <StatNumber>...</StatNumber>
                          </Stat>
                          <Stat>
                            <StatLabel>File Shares</StatLabel>
                            <StatNumber>{files.length}</StatNumber>
                          </Stat>
                        </SimpleGrid>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Settings Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Alert status="info" borderRadius="md">
                      <InfoIcon />
                      <Text>Advanced settings and configuration options coming soon...</Text>
                    </Alert>
                    
                    <Card>
                      <CardHeader>
                        <Heading size="md">Integration Settings</Heading>
                      </CardHeader>
                      <CardBody>
                        <VStack spacing={4} align="start">
                          <FormControl display="flex" alignItems="center">
                            <FormLabel htmlFor="real-time-sync" mb="0">
                              Real-time Sync
                            </FormLabel>
                            <Switch id="real-time-sync" defaultChecked />
                          </FormControl>
                          
                          <FormControl display="flex" alignItems="center">
                            <FormLabel htmlFor="enable-notifications" mb="0">
                              Enable Notifications
                            </FormLabel>
                            <Switch id="enable-notifications" defaultChecked />
                          </FormControl>
                          
                          <FormControl display="flex" alignItems="center">
                            <FormLabel htmlFor="index-messages" mb="0">
                              Index Messages for Search
                            </FormLabel>
                            <Switch id="index-messages" defaultChecked />
                          </FormControl>
                        </VStack>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>
          </Box>
        </Flex>

        {/* Ingestion Status Modal */}
        {ingestionStatus.running && (
          <Modal isOpen={true} onClose={() => {}} closeOnOverlayClick={false}>
            <ModalOverlay />
            <ModalContent>
              <ModalHeader>Data Ingestion</ModalHeader>
              <ModalCloseButton isDisabled />
              <ModalBody>
                <VStack spacing={4}>
                  <HStack justify="space-between" w="full">
                    <Text>{ingestionStatus.stage}</Text>
                    <Text>{Math.round(ingestionStatus.progress)}%</Text>
                  </HStack>
                  
                  <Progress
                    value={ingestionStatus.progress}
                    size="md"
                    colorScheme="purple"
                    w="full"
                    hasStripe
                    isAnimated
                  />
                  
                  <Text fontSize="sm" color="gray.600">
                    {ingestionStatus.message}
                  </Text>
                  
                  {ingestionStatus.items_processed && (
                    <Text fontSize="sm" color="gray.600">
                      Processed: {ingestionStatus.items_processed} items
                    </Text>
                  )}
                </VStack>
              </ModalBody>
            </ModalContent>
          </Modal>
        )}
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
            <Heading size="md">Slack Integration</Heading>
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
                    leftIcon={<Avatar size="xs" name={workspace.name} src={workspace.icon} />}
                    w="full"
                  >
                    {workspace.name}
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
                      {channel.is_private ? '🔒' : '#'}{channel.name}
                    </Button>
                  ))}
                </VStack>
              )}
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>
    </SlackContext.Provider>
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

// SmileIcon for reactions
const SmileIcon: React.FC = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
  </svg>
);

export default EnhancedSlackManager;
export { useSlack, SlackContext };