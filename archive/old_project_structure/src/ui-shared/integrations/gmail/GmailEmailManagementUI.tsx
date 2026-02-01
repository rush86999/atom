/**
 * Gmail Email Management UI Component
 * Complete Gmail email workflow automation interface
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
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Tfoot,
  TableContainer,
  Code,
  Textarea,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  List,
  ListItem,
  ListIcon,
  Alert,
  AlertIcon,
  Tag,
  TagLabel,
  TagCloseButton,
  SimpleGrid,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Drawer,
  DrawerBody,
  DrawerFooter,
  DrawerHeader,
  DrawerContent,
  DrawerCloseButton,
  useDisclosure,
  useColorModeValue,
  ChakraProvider,
  extendTheme
} from '@chakra-ui/react';
import {
  FiMail,
  FiSend,
  FiInbox,
  FiArchive,
  FiTrash2,
  FiEdit3,
  FiReply,
  FiReplyAll,
  FiForward,
  FiPaperclip,
  FiSearch,
  FiFilter,
  FiPlus,
  FiRefreshCw,
  FiDownload,
  FiUpload,
  FiStar,
  FiFlag,
  FiTag,
  FiFolder,
  FiUser,
  FiUsers,
  FiClock,
  FiCalendar,
  FiCheck,
  FiX,
  FiAlertTriangle,
  FiChevronDown,
  FiChevronRight,
  FiCopy,
  FiMoreHorizontal,
  FiMoreVertical,
  FiZoomIn,
  FiZoomOut,
  FiMaximize,
  FiMinimize,
  FiSettings,
  FiDatabase,
  FiZap,
  FiZapOff,
  FiActivity,
  FiHardDrive,
  FiShield,
  FiUnlock,
  FiEye,
  FiEyeOff,
  FiCheckCircle,
  FiXCircle,
  FiInfo,
  FiMessageSquare,
  FiMessageCircle,
  FiMessageCIRCLE,
  FiLogIn,
  FiLogOut,
  FiKey
} from 'react-icons/fi';

// Import Gmail skills
import { gmailSkills, gmailUtils } from './skills/gmailSkillsComplete';

interface GmailMessage {
  id: string;
  thread_id: string;
  subject: string;
  from_email: string;
  to_emails: string[];
  cc_emails: string[];
  bcc_emails: string[];
  date: string;
  body: string;
  body_html: string;
  snippet: string;
  labels: string[];
  is_read: boolean;
  is_starred: boolean;
  is_draft: boolean;
  is_sent: boolean;
  is_inbox: boolean;
  is_important: boolean;
  attachment_count: number;
  size: number;
  history_id: string;
  metadata: any;
}

interface GmailThread {
  id: string;
  thread_id: string;
  subject: string;
  message_count: number;
  participant_emails: string[];
  first_message_date: string;
  last_message_date: string;
  is_unread: boolean;
  labels: string[];
  total_size: number;
  total_attachments: number;
  last_message_snippet: string;
  metadata: any;
}

interface GmailLabel {
  id: string;
  name: string;
  type: string;
  message_list_visibility: string;
  label_list_visibility: string;
  color: any;
  total_messages: number;
  unread_messages: number;
  metadata: any;
}

interface GmailContact {
  id: string;
  email: string;
  name: string;
  avatar_url: string;
  interaction_count: number;
  first_interaction: string;
  last_interaction: string;
  sent_count: number;
  received_count: number;
  common_subjects: string[];
  common_labels: string[];
  metadata: any;
}

interface GmailMemorySettings {
  user_id: string;
  ingestion_enabled: boolean;
  sync_frequency: string;
  data_retention_days: number;
  include_labels: string[];
  exclude_labels: string[];
  include_threads: boolean;
  include_drafts: boolean;
  include_sent: boolean;
  include_received: boolean;
  max_messages_per_sync: number;
  max_attachment_size_mb: number;
  include_attachments: boolean;
  index_attachments: boolean;
  search_enabled: boolean;
  semantic_search_enabled: boolean;
  metadata_extraction_enabled: boolean;
  thread_tracking_enabled: boolean;
  contact_analysis_enabled: boolean;
  last_sync_timestamp?: string;
  next_sync_timestamp?: string;
  sync_in_progress: boolean;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
}

interface GmailSyncStatus {
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
    total_threads_ingested: number;
    total_attachments_ingested: number;
    total_contacts_processed: number;
    total_size_mb: number;
    failed_ingestions: number;
    last_ingestion_timestamp?: string;
    avg_messages_per_sync: number;
    avg_processing_time_ms: number;
  };
  settings: {
    include_labels: string[];
    exclude_labels: string[];
    include_threads: boolean;
    include_drafts: boolean;
    include_sent: boolean;
    include_received: boolean;
    max_messages_per_sync: number;
    max_attachment_size_mb: number;
    include_attachments: boolean;
    index_attachments: boolean;
    search_enabled: boolean;
    semantic_search_enabled: boolean;
    metadata_extraction_enabled: boolean;
    thread_tracking_enabled: boolean;
    contact_analysis_enabled: boolean;
  };
}

interface GmailEmailManagementUIProps {
  userId: string;
  accessToken: string;
  className?: string;
  height?: string | number;
  showMemoryControls?: boolean;
  enableRealtimeSync?: boolean;
  onMessageChange?: (message: GmailMessage) => void;
  onThreadChange?: (thread: GmailThread) => void;
  onSettingsChange?: (settings: GmailMemorySettings) => void;
}

const GmailEmailManagementUI: React.FC<GmailEmailManagementUIProps> = ({
  userId,
  accessToken,
  className = '',
  height = '800px',
  showMemoryControls = true,
  enableRealtimeSync = true,
  onMessageChange,
  onThreadChange,
  onSettingsChange
}) => {
  const toast = useToast();
  const { isOpen: composeOpen, onOpen: composeOnOpen, onClose: composeOnClose } = useDisclosure();
  const { isOpen: settingsOpen, onOpen: settingsOnOpen, onClose: settingsOnClose } = useDisclosure();
  const { isOpen: searchOpen, onOpen: searchOnOpen, onClose: searchOnClose } = useDisclosure();
  const { isOpen: messageOpen, onOpen: messageOnOpen, onClose: messageOnClose } = useDisclosure();

  // State management
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<GmailMessage[]>([]);
  const [threads, setThreads] = useState<GmailThread[]>([]);
  const [labels, setLabels] = useState<GmailLabel[]>([]);
  const [contacts, setContacts] = useState<GmailContact[]>([]);
  const [selectedMessage, setSelectedMessage] = useState<GmailMessage | null>(null);
  const [selectedThread, setSelectedThread] = useState<GmailThread | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<GmailMessage[]>([]);
  const [selectedLabels, setSelectedLabels] = useState<string[]>(['INBOX']);
  const [viewMode, setViewMode] = useState<'messages' | 'threads' | 'contacts'>('messages');
  const [sortBy, setSortBy] = useState<'date' | 'subject' | 'from'>('date');
  const [sortOrder, setSortOrder] = useState<'desc' | 'asc'>('desc');
  const [realtimeEnabled, setRealtimeEnabled] = useState(enableRealtimeSync);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);
  const [composeData, setComposeData] = useState({
    to: '',
    cc: '',
    bcc: '',
    subject: '',
    body: '',
    isHtml: false
  });
  
  // Memory management state
  const [memorySettings, setMemorySettings] = useState<GmailMemorySettings | null>(null);
  const [syncStatus, setSyncStatus] = useState<GmailSyncStatus | null>(null);
  const [tempSettings, setTempSettings] = useState<GmailMemorySettings | null>(null);
  const [hasChanges, setHasChanges] = useState(false);
  
  // Compose state
  const [attachments, setAttachments] = useState<File[]>([]);
  const [sendingMessage, setSendingMessage] = useState(false);

  // Color mode values
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Fetch functions
  const fetchMessages = useCallback(async (query: string = '', labelIds: string[] = ['INBOX']) => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/gmail/email-workflow/messages/list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': userId,
          'X-Access-Token': accessToken
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken,
          max_results: 50,
          query: query,
          label_ids: labelIds
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        const messagesData = data.messages.map((msg: any) => gmailUtils.createGmailMessage(msg));
        setMessages(messagesData);
        setConnected(true);
        
        toast({
          title: 'Messages Loaded',
          description: `Loaded ${messagesData.length} messages`,
          status: 'success',
          duration: 3000,
        });
      } else {
        setConnected(false);
        toast({
          title: 'Message Load Failed',
          description: data.error || 'Failed to load messages',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Gmail messages:', error);
      setConnected(false);
      toast({
        title: 'Connection Error',
        description: 'Failed to connect to Gmail',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  }, [userId, accessToken, toast]);

  const fetchThreads = useCallback(async (query: string = '', labelIds: string[] = ['INBOX']) => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/gmail/email-workflow/threads/list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': userId,
          'X-Access-Token': accessToken
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken,
          max_results: 50,
          query: query,
          label_ids: labelIds
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        const threadsData = data.threads.map((thread: any) => gmailUtils.createGmailThread(thread));
        setThreads(threadsData);
        setConnected(true);
      } else {
        setConnected(false);
        toast({
          title: 'Thread Load Failed',
          description: data.error || 'Failed to load threads',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error fetching Gmail threads:', error);
      setConnected(false);
    } finally {
      setLoading(false);
    }
  }, [userId, accessToken, toast]);

  const fetchLabels = useCallback(async () => {
    try {
      const response = await fetch('/api/gmail/email-workflow/labels/list', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': userId,
          'X-Access-Token': accessToken
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        const labelsData = data.labels.map((label: any) => gmailUtils.createGmailLabel(label));
        setLabels(labelsData);
      }
    } catch (error) {
      console.error('Error fetching Gmail labels:', error);
    }
  }, [userId, accessToken]);

  const fetchContacts = useCallback(async () => {
    try {
      // Search for contacts in memory
      const response = await fetch('/api/gmail/email-workflow/memory/contacts-search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          query: '',
          limit: 100
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        const contactsData = data.contacts.map((contact: any) => gmailUtils.createGmailContact(contact));
        setContacts(contactsData);
      }
    } catch (error) {
      console.error('Error fetching Gmail contacts:', error);
    }
  }, [userId]);

  const fetchMemorySettings = useCallback(async () => {
    try {
      const response = await fetch('/api/gmail/email-workflow/memory/settings', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setMemorySettings(data.settings);
        setTempSettings(data.settings);
        onSettingsChange?.(data.settings);
      }
    } catch (error) {
      console.error('Error fetching Gmail memory settings:', error);
    }
  }, [userId, onSettingsChange]);

  const fetchSyncStatus = useCallback(async () => {
    try {
      const response = await fetch('/api/gmail/email-workflow/memory/status', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ user_id: userId }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setSyncStatus(data.memory_status);
      }
    } catch (error) {
      console.error('Error fetching Gmail sync status:', error);
    }
  }, [userId]);

  const fetchMessage = useCallback(async (messageId: string) => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/gmail/email-workflow/messages/get', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': userId,
          'X-Access-Token': accessToken
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken,
          message_id: messageId,
          format: 'full',
          include_attachments: true
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        const message = gmailUtils.createGmailMessage(data.message);
        setSelectedMessage(message);
        onMessageChange?.(message);
      } else {
        toast({
          title: 'Message Load Failed',
          description: data.error || 'Failed to load message',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error fetching Gmail message:', error);
      toast({
        title: 'Message Error',
        description: 'Failed to load message',
        status: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [userId, accessToken, onMessageChange, toast]);

  const fetchThread = useCallback(async (threadId: string) => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/gmail/email-workflow/threads/get', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': userId,
          'X-Access-Token': accessToken
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken,
          thread_id: threadId
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        const thread = gmailUtils.createGmailThread(data.thread);
        setSelectedThread(thread);
        onThreadChange?.(thread);
      } else {
        toast({
          title: 'Thread Load Failed',
          description: data.error || 'Failed to load thread',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error fetching Gmail thread:', error);
      toast({
        title: 'Thread Error',
        description: 'Failed to load thread',
        status: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [userId, accessToken, onThreadChange, toast]);

  // Message operations
  const sendMessage = useCallback(async () => {
    try {
      setSendingMessage(true);
      
      const response = await fetch('/api/gmail/email-workflow/messages/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': userId,
          'X-Access-Token': accessToken
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken,
          to: composeData.to,
          cc: composeData.cc,
          bcc: composeData.bcc,
          subject: composeData.subject,
          body: composeData.body,
          is_html: composeData.isHtml
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        toast({
          title: 'Message Sent',
          description: 'Message sent successfully',
          status: 'success',
        });
        
        // Clear compose form
        setComposeData({
          to: '',
          cc: '',
          bcc: '',
          subject: '',
          body: '',
          isHtml: false
        });
        setAttachments([]);
        
        // Refresh messages
        await fetchMessages();
        
        composeOnClose();
      } else {
        toast({
          title: 'Send Failed',
          description: data.error || 'Failed to send message',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error sending Gmail message:', error);
      toast({
        title: 'Send Error',
        description: 'Failed to send message',
        status: 'error',
      });
    } finally {
      setSendingMessage(false);
    }
  }, [userId, accessToken, composeData, fetchMessages, toast, composeOnClose]);

  const trashMessage = useCallback(async (messageId: string) => {
    try {
      const response = await fetch('/api/gmail/email-workflow/messages/trash', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': userId,
          'X-Access-Token': accessToken
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken,
          message_id: messageId
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        toast({
          title: 'Message Trashed',
          description: 'Message moved to trash',
          status: 'success',
        });
        
        // Refresh messages
        await fetchMessages();
      } else {
        toast({
          title: 'Trash Failed',
          description: data.error || 'Failed to trash message',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error trashing Gmail message:', error);
      toast({
        title: 'Trash Error',
        description: 'Failed to trash message',
        status: 'error',
      });
    }
  }, [userId, accessToken, fetchMessages, toast]);

  // Memory management
  const startIngestion = useCallback(async (forceSync: boolean = false) => {
    try {
      setSyncInProgress(true);
      setSyncResult(null);
      
      const response = await fetch('/api/gmail/email-workflow/memory/ingest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken,
          force_sync: forceSync
        }),
      });

      const data = await response.json();
      
      setSyncResult(data);
      
      if (data.ok) {
        // Refresh sync status
        await fetchSyncStatus();
        
        toast({
          title: 'Ingestion Complete',
          description: `Ingested ${data.ingestion_result?.messages_ingested || 0} messages and ${data.ingestion_result?.threads_ingested || 0} threads`,
          status: 'success',
          duration: 5000,
        });
      } else {
        toast({
          title: 'Ingestion Failed',
          description: data.error || 'Failed to ingest email data',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (error) {
      console.error('Error starting Gmail ingestion:', error);
      toast({
        title: 'Ingestion Error',
        description: 'Failed to start email ingestion',
        status: 'error',
      });
    } finally {
      setSyncInProgress(false);
    }
  }, [userId, accessToken, fetchSyncStatus, toast]);

  const updateMemorySettings = useCallback(async (newSettings: GmailMemorySettings) => {
    try {
      const response = await fetch('/api/gmail/email-workflow/memory/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          user_id: userId,
          ...newSettings
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        setMemorySettings(prev => ({ ...prev, ...newSettings }));
        setTempSettings(prev => ({ ...prev, ...newSettings }));
        setHasChanges(false);
        onSettingsChange?.(newSettings);
        
        toast({
          title: 'Settings Updated',
          description: 'Gmail memory settings saved successfully',
          status: 'success',
        });
      }
    } catch (error) {
      console.error('Error updating Gmail settings:', error);
      toast({
        title: 'Settings Error',
        description: 'Failed to update Gmail settings',
        status: 'error',
      });
    }
  }, [userId, onSettingsChange, toast]);

  // Search functionality
  const searchMessages = useCallback(async (query: string) => {
    try {
      setLoading(true);
      
      const response = await fetch('/api/gmail/email-workflow/messages/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': userId,
          'X-Access-Token': accessToken
        },
        body: JSON.stringify({ 
          user_id: userId,
          access_token: accessToken,
          query: query,
          max_results: 50
        }),
      });

      const data = await response.json();
      
      if (data.ok) {
        const messagesData = data.messages.map((msg: any) => gmailUtils.createGmailMessage(msg));
        setSearchResults(messagesData);
      } else {
        toast({
          title: 'Search Error',
          description: data.error || 'Failed to search messages',
          status: 'error',
        });
      }
    } catch (error) {
      console.error('Error searching Gmail messages:', error);
      toast({
        title: 'Search Error',
        description: 'Failed to search messages',
        status: 'error',
      });
    } finally {
      setLoading(false);
    }
  }, [userId, accessToken, toast]);

  // Effects
  useEffect(() => {
    if (userId && accessToken) {
      fetchMessages();
      fetchLabels();
      fetchContacts();
    }
  }, [userId, accessToken, fetchMessages, fetchLabels, fetchContacts]);

  useEffect(() => {
    if (userId && showMemoryControls) {
      fetchMemorySettings();
      fetchSyncStatus();
    }
  }, [userId, showMemoryControls, fetchMemorySettings, fetchSyncStatus]);

  // Auto-refresh sync status
  useEffect(() => {
    if (!showMemoryControls) return;
    
    const interval = setInterval(() => {
      fetchSyncStatus();
    }, 30000); // Every 30 seconds
    
    return () => clearInterval(interval);
  }, [fetchSyncStatus, showMemoryControls]);

  // Debounced search
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      if (searchQuery) {
        searchMessages(searchQuery);
      } else {
        setSearchResults([]);
      }
    }, 300);
    
    return () => clearTimeout(timeoutId);
  }, [searchQuery, searchMessages]);

  // Memoized filtered items
  const filteredMessages = useMemo(() => {
    let filtered = messages;
    
    // Filter by labels
    if (selectedLabels.length > 0) {
      filtered = filtered.filter(msg => 
        selectedLabels.some(label => msg.labels.includes(label))
      );
    }
    
    // Sort messages
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'date':
          comparison = new Date(b.date).getTime() - new Date(a.date).getTime();
          break;
        case 'subject':
          comparison = a.subject.localeCompare(b.subject);
          break;
        case 'from':
          comparison = a.from_email.localeCompare(b.from_email);
          break;
      }
      
      return sortOrder === 'asc' ? -comparison : comparison;
    });
    
    return filtered;
  }, [messages, selectedLabels, sortBy, sortOrder]);

  const filteredThreads = useMemo(() => {
    let filtered = threads;
    
    // Filter by labels
    if (selectedLabels.length > 0) {
      filtered = filtered.filter(thread => 
        selectedLabels.some(label => thread.labels.includes(label))
      );
    }
    
    // Sort threads
    filtered.sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'date':
          comparison = new Date(b.last_message_date).getTime() - new Date(a.last_message_date).getTime();
          break;
        case 'subject':
          comparison = a.subject.localeCompare(b.subject);
          break;
        default:
          comparison = 0;
      }
      
      return sortOrder === 'asc' ? -comparison : comparison;
    });
    
    return filtered;
  }, [threads, selectedLabels, sortBy, sortOrder]);

  return (
    <Box className={className} height={height} display="flex" borderWidth={1} borderRadius="lg" overflow="hidden">
      <VStack flex={1} spacing={0} align="stretch">
        {/* Header */}
        <HStack 
          p={4} 
          borderBottomWidth={1} 
          bg="gmail.dark.50" 
          justify="space-between"
        >
          <HStack spacing={3} flex={1}>
            <Icon as={FiMail} boxSize={5} color="gmail.500" />
            <VStack spacing={0} align="start" flex={1}>
              <HStack spacing={2}>
                <Text fontWeight="bold">Gmail Email Management</Text>
                <Badge colorScheme="gmail">Email</Badge>
                {realtimeEnabled && (
                  <Badge colorScheme="green" variant="outline">
                    <Icon as={FiZap} boxSize={3} mr={1} />
                    Live
                  </Badge>
                )}
              </HStack>
              <Text fontSize="xs" color="gray.500">
                {connected ? 'Connected to Gmail' : 'Not connected'} › {viewMode} view
              </Text>
            </VStack>
          </HStack>
          
          <HStack spacing={2}>
            <Tooltip label="Compose">
              <IconButton 
                icon={<FiEdit3 />} 
                variant="ghost" 
                size="sm"
                onClick={composeOnOpen}
                colorScheme="gmail"
              />
            </Tooltip>
            
            <Tooltip label="Search">
              <IconButton 
                icon={<FiSearch />} 
                variant="ghost" 
                size="sm"
                onClick={searchOnOpen}
              />
            </Tooltip>
            
            <Tooltip label="Refresh">
              <IconButton 
                icon={<FiRefreshCw />} 
                variant="ghost" 
                size="sm"
                onClick={() => viewMode === 'messages' ? fetchMessages() : viewMode === 'threads' ? fetchThreads() : fetchContacts()}
                isLoading={loading}
              />
            </Tooltip>
            
            {showMemoryControls && (
              <>
                <Tooltip label="Memory Settings">
                  <IconButton 
                    icon={<FiSettings />} 
                    variant="ghost" 
                    size="sm"
                    onClick={settingsOnOpen}
                  />
                </Tooltip>
                
                <Tooltip label={`Last sync: ${syncStatus?.stats.last_ingestion_timestamp ? gmailUtils.formatDateTime(syncStatus.stats.last_ingestion_timestamp) : 'Never'}`}>
                  <IconButton 
                    icon={<FiDatabase />} 
                    variant="ghost" 
                    size="sm"
                    onClick={() => startIngestion(false)}
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

        {/* Toolbar */}
        <HStack p={3} borderBottomWidth={1} bg="gray.50">
          {/* View Mode Tabs */}
          <HStack spacing={1}>
            <Button
              size="sm"
              variant={viewMode === 'messages' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'messages' ? 'gmail' : 'gray'}
              onClick={() => setViewMode('messages')}
              leftIcon={<FiInbox />}
            >
              Messages
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'threads' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'threads' ? 'gmail' : 'gray'}
              onClick={() => setViewMode('threads')}
              leftIcon={<FiMessageSquare />}
            >
              Threads
            </Button>
            <Button
              size="sm"
              variant={viewMode === 'contacts' ? 'solid' : 'outline'}
              colorScheme={viewMode === 'contacts' ? 'gmail' : 'gray'}
              onClick={() => setViewMode('contacts')}
              leftIcon={<FiUsers />}
            >
              Contacts
            </Button>
          </HStack>
          
          <Divider orientation="vertical" h={6} />
          
          {/* Search Input */}
          <Input
            placeholder="Search messages..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            size="sm"
            maxW="300px"
            leftIcon={<FiSearch />}
          />
          
          {/* Labels Filter */}
          <Menu>
            <MenuButton as={Button} variant="outline" size="sm" rightIcon={<FiChevronDown />}>
              Labels: {selectedLabels.length}
            </MenuButton>
            <MenuList>
              {labels.map((label) => (
                <MenuItem
                  key={label.id}
                  onClick={() => {
                    if (selectedLabels.includes(label.name)) {
                      setSelectedLabels(prev => prev.filter(l => l !== label.name));
                    } else {
                      setSelectedLabels(prev => [...prev, label.name]);
                    }
                  }}
                >
                  <HStack justify="space-between" w="full">
                    <Text>{label.name}</Text>
                    {selectedLabels.includes(label.name) && <Icon as={FiCheck} color="green.500" />}
                  </HStack>
                </MenuItem>
              ))}
            </MenuList>
          </Menu>
          
          {/* Sort Controls */}
          <Menu>
            <MenuButton as={Button} variant="ghost" size="sm" rightIcon={<FiChevronDown />}>
              Sort: {sortBy}
            </MenuButton>
            <MenuList>
              <MenuItem onClick={() => setSortBy('date')}>Date</MenuItem>
              <MenuItem onClick={() => setSortBy('subject')}>Subject</MenuItem>
              {viewMode === 'messages' && <MenuItem onClick={() => setSortBy('from')}>From</MenuItem>}
              <Divider />
              <MenuItem onClick={() => setSortOrder('desc')}>Newest First</MenuItem>
              <MenuItem onClick={() => setSortOrder('asc')}>Oldest First</MenuItem>
            </MenuList>
          </Menu>
        </HStack>

        <HStack flex={1} spacing={0} align="stretch">
          {/* Main Content */}
          <VStack flex={1} spacing={0} align="stretch">
            {viewMode === 'messages' && (
              <>
                {/* Messages List */}
                <ScrollArea flex={1}>
                  <VStack spacing={0} align="stretch">
                    {connected && filteredMessages.length > 0 ? (
                      filteredMessages.map((message) => (
                        <MessageListItem
                          key={message.id}
                          message={message}
                          selected={selectedMessage?.id === message.id}
                          onSelect={() => {
                            fetchMessage(message.id);
                            messageOnOpen();
                          }}
                          onReply={() => {
                            setComposeData({
                              ...composeData,
                              to: message.from_email,
                              subject: `Re: ${message.subject}`,
                              body: `\n\n---\nFrom: ${message.from_email}\nDate: ${gmailUtils.formatDateTime(message.date)}\nSubject: ${message.subject}\n\n${message.body}`
                            });
                            composeOnOpen();
                          }}
                          onForward={() => {
                            setComposeData({
                              ...composeData,
                              subject: `Fwd: ${message.subject}`,
                              body: `\n\n--- Forwarded message ---\nFrom: ${message.from_email}\nDate: ${gmailUtils.formatDateTime(message.date)}\nSubject: ${message.subject}\n\n${message.body}`
                            });
                            composeOnOpen();
                          }}
                          onTrash={() => trashMessage(message.id)}
                          onStar={() => {
                            // Implement star functionality
                          }}
                        />
                      ))
                    ) : (
                      <VStack spacing={4} align="center" py={8}>
                        <Icon as={FiMail} boxSize={8} color="gray.400" />
                        <Text color="gray.500" textAlign="center">
                          {connected ? 'No messages found' : 'Connect to Gmail'}
                        </Text>
                        {connected && (
                          <Button
                            size="sm"
                            colorScheme="gmail"
                            onClick={() => fetchMessages()}
                          >
                            Refresh
                          </Button>
                        )}
                      </VStack>
                    )}
                  </VStack>
                </ScrollArea>
              </>
            )}
            
            {viewMode === 'threads' && (
              <>
                {/* Threads List */}
                <ScrollArea flex={1}>
                  <VStack spacing={0} align="stretch">
                    {connected && filteredThreads.length > 0 ? (
                      filteredThreads.map((thread) => (
                        <ThreadListItem
                          key={thread.id}
                          thread={thread}
                          selected={selectedThread?.id === thread.id}
                          onSelect={() => {
                            fetchThread(thread.thread_id);
                          }}
                        />
                      ))
                    ) : (
                      <VStack spacing={4} align="center" py={8}>
                        <Icon as={FiMessageSquare} boxSize={8} color="gray.400" />
                        <Text color="gray.500" textAlign="center">
                          {connected ? 'No threads found' : 'Connect to Gmail'}
                        </Text>
                      </VStack>
                    )}
                  </VStack>
                </ScrollArea>
              </>
            )}
            
            {viewMode === 'contacts' && (
              <>
                {/* Contacts List */}
                <ScrollArea flex={1}>
                  <VStack spacing={0} align="stretch" p={4}>
                    {contacts.length > 0 ? (
                      contacts.map((contact) => (
                        <ContactListItem
                          key={contact.id}
                          contact={contact}
                        />
                      ))
                    ) : (
                      <VStack spacing={4} align="center" py={8}>
                        <Icon as={FiUsers} boxSize={8} color="gray.400" />
                        <Text color="gray.500" textAlign="center">
                          No contacts found
                        </Text>
                      </VStack>
                    )}
                  </VStack>
                </ScrollArea>
              </>
            )}
          </VStack>
        </HStack>
      </VStack>

      {/* Compose Message Modal */}
      <Modal 
        isOpen={composeOpen} 
        onClose={composeOnClose}
        size="2xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiEdit3} />
              <Text>Compose Message</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <FormControl>
                <FormLabel>To</FormLabel>
                <Input
                  value={composeData.to}
                  onChange={(e) => setComposeData(prev => ({ ...prev, to: e.target.value }))}
                  placeholder="recipient@example.com"
                />
              </FormControl>
              
              <HStack spacing={4}>
                <FormControl>
                  <FormLabel>Cc</FormLabel>
                  <Input
                    value={composeData.cc}
                    onChange={(e) => setComposeData(prev => ({ ...prev, cc: e.target.value }))}
                    placeholder="cc@example.com"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Bcc</FormLabel>
                  <Input
                    value={composeData.bcc}
                    onChange={(e) => setComposeData(prev => ({ ...prev, bcc: e.target.value }))}
                    placeholder="bcc@example.com"
                  />
                </FormControl>
              </HStack>
              
              <FormControl>
                <FormLabel>Subject</FormLabel>
                <Input
                  value={composeData.subject}
                  onChange={(e) => setComposeData(prev => ({ ...prev, subject: e.target.value }))}
                  placeholder="Message subject"
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Message</FormLabel>
                <Textarea
                  value={composeData.body}
                  onChange={(e) => setComposeData(prev => ({ ...prev, body: e.target.value }))}
                  placeholder="Write your message..."
                  h="200px"
                />
              </FormControl>
              
              {attachments.length > 0 && (
                <VStack align="stretch" spacing={2}>
                  <Text fontSize="sm" fontWeight="medium">Attachments:</Text>
                  {attachments.map((file, index) => (
                    <HStack key={index} justify="space-between" p={2} bg="gray.50" borderRadius="md">
                      <Text fontSize="sm">{file.name}</Text>
                      <IconButton
                        icon={<FiX />}
                        variant="ghost"
                        size="xs"
                        onClick={() => setAttachments(prev => prev.filter((_, i) => i !== index))}
                      />
                    </HStack>
                  ))}
                </VStack>
              )}
            </VStack>
          </ModalBody>
          
          <ModalFooter>
            <HStack spacing={3}>
              <Button
                variant="outline"
                onClick={composeOnClose}
              >
                Cancel
              </Button>
              
              <Button
                colorScheme="gmail"
                onClick={sendMessage}
                isLoading={sendingMessage}
                isDisabled={!composeData.to || !composeData.subject}
                leftIcon={<FiSend />}
              >
                Send
              </Button>
            </HStack>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Message Details Modal */}
      <Modal 
        isOpen={messageOpen} 
        onClose={messageOnClose}
        size="3xl"
        scrollBehavior="inside"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            <HStack spacing={3}>
              <Icon as={FiMail} />
              <Text>{selectedMessage?.subject || 'Message'}</Text>
            </HStack>
          </ModalHeader>
          
          <ModalCloseButton />
          
          <ModalBody>
            {selectedMessage && (
              <VStack spacing={4} align="stretch">
                {/* Message Header */}
                <HStack justify="space-between" align="start">
                  <VStack align="start" spacing={2} flex={1}>
                    <Text fontWeight="medium">From: {selectedMessage.from_email}</Text>
                    <Text fontSize="sm">To: {selectedMessage.to_emails.join(', ')}</Text>
                    {selectedMessage.cc_emails.length > 0 && (
                      <Text fontSize="sm">Cc: {selectedMessage.cc_emails.join(', ')}</Text>
                    )}
                    <Text fontSize="xs" color="gray.500">
                      {gmailUtils.formatDateTime(selectedMessage.date)}
                    </Text>
                  </VStack>
                  
                  <HStack spacing={1}>
                    <IconButton
                      icon={<FiReply />}
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setComposeData({
                          ...composeData,
                          to: selectedMessage.from_email,
                          subject: `Re: ${selectedMessage.subject}`,
                          body: `\n\n---\nFrom: ${selectedMessage.from_email}\nDate: ${gmailUtils.formatDateTime(selectedMessage.date)}\nSubject: ${selectedMessage.subject}\n\n${selectedMessage.body}`
                        });
                        messageOnClose();
                        composeOnOpen();
                      }}
                    />
                    <IconButton
                      icon={<FiReplyAll />}
                      variant="ghost"
                      size="sm"
                    />
                    <IconButton
                      icon={<FiForward />}
                      variant="ghost"
                      size="sm"
                    />
                    <IconButton
                      icon={<FiTrash2 />}
                      variant="ghost"
                      size="sm"
                      colorScheme="red"
                      onClick={() => {
                        trashMessage(selectedMessage.id);
                        messageOnClose();
                      }}
                    />
                  </HStack>
                </HStack>
                
                <Divider />
                
                {/* Message Body */}
                <Box
                  p={4}
                  bg="gray.50"
                  borderRadius="md"
                  dangerouslySetInnerHTML={{ __html: selectedMessage.body_html || selectedMessage.body.replace(/\n/g, '<br>') }}
                />
                
                {/* Attachments */}
                {selectedMessage.attachment_count > 0 && (
                  <VStack align="stretch" spacing={2}>
                    <Text fontSize="sm" fontWeight="medium">Attachments ({selectedMessage.attachment_count})</Text>
                    {/* Attachment list would go here */}
                  </VStack>
                )}
              </VStack>
            )}
          </ModalBody>
          
          <ModalFooter>
            <Button
              variant="outline"
              onClick={messageOnClose}
            >
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Memory Settings Modal */}
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
              <Icon as={FiDatabase} />
              <Text>Gmail Memory Settings</Text>
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
                          <FormLabel htmlFor="gmail-ingestion-enabled">
                            Enable Email Memory
                          </FormLabel>
                          <Switch
                            id="gmail-ingestion-enabled"
                            isChecked={tempSettings.ingestion_enabled}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, ingestion_enabled: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Sync Frequency</FormLabel>
                          <Select
                            value={tempSettings.sync_frequency}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, sync_frequency: e.target.value }))}
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
                            onChange={(value) => setTempSettings(prev => ({ ...prev, data_retention_days: parseInt(value) || 365 }))}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* Message Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Message Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="gmail-include-threads">
                            Include Thread Messages
                          </FormLabel>
                          <Switch
                            id="gmail-include-threads"
                            isChecked={tempSettings.include_threads}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, include_threads: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="gmail-include-drafts">
                            Include Drafts
                          </FormLabel>
                          <Switch
                            id="gmail-include-drafts"
                            isChecked={tempSettings.include_drafts}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, include_drafts: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="gmail-include-sent">
                            Include Sent Messages
                          </FormLabel>
                          <Switch
                            id="gmail-include-sent"
                            isChecked={tempSettings.include_sent}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, include_sent: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="gmail-include-received">
                            Include Received Messages
                          </FormLabel>
                          <Switch
                            id="gmail-include-received"
                            isChecked={tempSettings.include_received}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, include_received: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Max Messages per Sync</FormLabel>
                          <NumberInput
                            value={tempSettings.max_messages_per_sync}
                            min={100}
                            max={10000}
                            onChange={(value) => setTempSettings(prev => ({ ...prev, max_messages_per_sync: parseInt(value) || 1000 }))}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* Attachment Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Attachment Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="gmail-include-attachments">
                            Include Attachments
                          </FormLabel>
                          <Switch
                            id="gmail-include-attachments"
                            isChecked={tempSettings.include_attachments}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, include_attachments: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="gmail-index-attachments">
                            Index Attachments
                          </FormLabel>
                          <Switch
                            id="gmail-index-attachments"
                            isChecked={tempSettings.index_attachments}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, index_attachments: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl>
                          <FormLabel>Max Attachment Size (MB)</FormLabel>
                          <NumberInput
                            value={tempSettings.max_attachment_size_mb}
                            min={1}
                            max={1000}
                            onChange={(value) => setTempSettings(prev => ({ ...prev, max_attachment_size_mb: parseInt(value) || 25 }))}
                          >
                            <NumberInputField />
                          </NumberInput>
                        </FormControl>
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                  
                  {/* Search Settings */}
                  <AccordionItem>
                    <h2>
                      <AccordionButton>
                        <HStack flex={1} justify="space-between">
                          <Text fontWeight="medium">Search Settings</Text>
                          <AccordionIcon />
                        </HStack>
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack spacing={4} align="stretch">
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="gmail-search-enabled">
                            Enable Email Search
                          </FormLabel>
                          <Switch
                            id="gmail-search-enabled"
                            isChecked={tempSettings.search_enabled}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, search_enabled: e.target.checked }))}
                          />
                        </FormControl>
                        
                        <FormControl display="flex" alignItems="center" justifyContent="space-between">
                          <FormLabel htmlFor="gmail-semantic-search">
                            Enable Semantic Search
                          </FormLabel>
                          <Switch
                            id="gmail-semantic-search"
                            isChecked={tempSettings.semantic_search_enabled}
                            onChange={(e) => setTempSettings(prev => ({ ...prev, semantic_search_enabled: e.target.checked }))}
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
                onClick={() => setTempSettings(memorySettings)}
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
                colorScheme="gmail"
                onClick={() => {
                  updateMemorySettings(tempSettings!);
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
    </Box>
  );
};

// Message List Item Component
const MessageListItem: React.FC<{
  message: GmailMessage;
  selected: boolean;
  onSelect: () => void;
  onReply: () => void;
  onForward: () => void;
  onTrash: () => void;
  onStar: () => void;
}> = ({ message, selected, onSelect, onReply, onForward, onTrash, onStar }) => {
  return (
    <HStack
      p={4}
      bg={selected ? 'gmail.light.200' : 'transparent'}
      _hover={{ bg: 'gmail.light.100' }}
      cursor="pointer"
      onClick={onSelect}
      borderWidth={0}
      borderBottomWidth={1}
      borderColor="gray.100"
    >
      <Box flex={1}>
        <HStack justify="space-between" align="start" mb={2}>
          <VStack align="start" spacing={0}>
            <Text fontSize="sm" fontWeight="medium" noOfLines={1}>
              {message.from_email}
            </Text>
            <Text fontSize="xs" color="gray.500">
              To: {message.to_emails.join(', ')}
            </Text>
          </VStack>
          
          <VStack align="end" spacing={1}>
            <Text fontSize="xs" color="gray.500">
              {gmailUtils.formatRelativeTime(message.date)}
            </Text>
            <HStack spacing={1}>
              {message.is_starred && <Icon as={FiStar} color="yellow.500" boxSize={3} />}
              {message.attachment_count > 0 && <Icon as={FiPaperclip} color="gray.500" boxSize={3} />}
            </HStack>
          </VStack>
        </HStack>
        
        <Text fontSize="sm" fontWeight="medium" mb={1} noOfLines={1}>
          {message.subject}
        </Text>
        
        <Text fontSize="xs" color="gray.600" noOfLines={2}>
          {message.snippet}
        </Text>
      </VStack>
      
      <HStack spacing={1} opacity={0} _groupHover={{ opacity: 1 }}>
        <IconButton
          icon={<FiReply />}
          variant="ghost"
          size="xs"
          onClick={(e) => {
            e.stopPropagation();
            onReply();
          }}
        />
        <IconButton
          icon={<FiForward />}
          variant="ghost"
          size="xs"
          onClick={(e) => {
            e.stopPropagation();
            onForward();
          }}
        />
        <IconButton
          icon={<FiStar />}
          variant="ghost"
          size="xs"
          color={message.is_starred ? 'yellow' : 'gray'}
          onClick={(e) => {
            e.stopPropagation();
            onStar();
          }}
        />
        <IconButton
          icon={<FiTrash2 />}
          variant="ghost"
          size="xs"
          colorScheme="red"
          onClick={(e) => {
            e.stopPropagation();
            onTrash();
          }}
        />
      </HStack>
    </HStack>
  );
};

// Thread List Item Component
const ThreadListItem: React.FC<{
  thread: GmailThread;
  selected: boolean;
  onSelect: () => void;
}> = ({ thread, selected, onSelect }) => {
  return (
    <HStack
      p={4}
      bg={selected ? 'gmail.light.200' : 'transparent'}
      _hover={{ bg: 'gmail.light.100' }}
      cursor="pointer"
      onClick={onSelect}
      borderWidth={0}
      borderBottomWidth={1}
      borderColor="gray.100"
    >
      <Box flex={1}>
        <HStack justify="space-between" align="start" mb={2}>
          <VStack align="start" spacing={0}>
            <Text fontSize="sm" fontWeight="medium" noOfLines={1}>
              {thread.participant_emails[0]}
            </Text>
            <Text fontSize="xs" color="gray.500">
              {thread.participant_emails.length} participants
            </Text>
          </VStack>
          
          <VStack align="end" spacing={1}>
            <Text fontSize="xs" color="gray.500">
              {gmailUtils.formatRelativeTime(thread.last_message_date)}
            </Text>
            <HStack spacing={1}>
              {thread.is_unread && <Badge size="xs" colorScheme="red">Unread</Badge>}
              <Text fontSize="xs" color="gray.500">
                {thread.message_count} messages
              </Text>
              {thread.total_attachments > 0 && <Icon as={FiPaperclip} color="gray.500" boxSize={3} />}
            </HStack>
          </VStack>
        </HStack>
        
        <Text fontSize="sm" fontWeight="medium" mb={1} noOfLines={1}>
          {thread.subject}
        </Text>
        
        <Text fontSize="xs" color="gray.600" noOfLines={2}>
          {thread.last_message_snippet}
        </Text>
      </VStack>
    </HStack>
  );
};

// Contact List Item Component
const ContactListItem: React.FC<{
  contact: GmailContact;
}> = ({ contact }) => {
  return (
    <HStack
      p={4}
      borderWidth={0}
      borderBottomWidth={1}
      borderColor="gray.100"
    >
      <Avatar size="sm" name={contact.name || contact.email} src={contact.avatar_url}>
        <AvatarBadge boxSize="1.25em" bg="green.500" />
      </Avatar>
      
      <Box flex={1}>
        <Text fontSize="sm" fontWeight="medium">
          {contact.name || contact.email}
        </Text>
        <Text fontSize="xs" color="gray.500">
          {contact.email}
        </Text>
        <Text fontSize="xs" color="gray.500">
          {contact.interaction_count} interactions • Last: {gmailUtils.formatRelativeTime(contact.last_interaction)}
        </Text>
      </Box>
      
      <VStack align="end" spacing={1}>
        <Text fontSize="xs" color="gray.500">
          {contact.sent_count} sent
        </Text>
        <Text fontSize="xs" color="gray.500">
          {contact.received_count} received
        </Text>
      </VStack>
    </HStack>
  );
};

export default GmailEmailManagementUI;