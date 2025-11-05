import React, { useState, useEffect } from 'react';
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
  useTab,
  TabList,
  TabPanels,
  TabPanel,
  Tabs,
  Tag,
  TagLabel,
  TagLeftIcon,
  Image,
  Code,
  useClipboard,
  Textarea,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  List,
  ListItem,
  OrderedList,
  UnorderedList,
  Spinner,
} from '@chakra-ui/react';
import {
  ViewIcon,
  EditIcon,
  RepeatIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  AddIcon,
  SettingsIcon,
  InfoIcon,
  ViewListIcon,
  ArchiveIcon,
  UserIcon,
  CopyIcon,
  DesktopIcon,
  EmailIcon,
  CalendarIcon,
  FolderIcon,
  DocumentIcon,
  SearchIcon,
  ChatIcon,
  StarIcon,
  FilterIcon,
  DownloadIcon,
  UploadIcon,
  TrashIcon,
  EditIcon as EditDocIcon,
  SendIcon,
  BellIcon,
  ShareIcon,
  ClockIcon,
  LinkIcon,
  ReplyIcon,
  ForwardIcon,
  PhoneIcon,
  VideoIcon,
  TeamIcon,
  UserGroupIcon,
  BuildingIcon,
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface MicrosoftIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface OutlookMessage {
  id: string;
  subject: string;
  from: {
    emailAddress: {
      name: string;
      address: string;
    };
  };
  to: Array<{
    emailAddress: {
      name: string;
      address: string;
    };
  }>;
  body_preview: string;
  received_date_time: string;
  has_attachments: boolean;
  is_read: boolean;
  importance: string;
  conversation_id: string;
  web_link: string;
}

interface CalendarEvent {
  id: string;
  subject: string;
  start: {
    dateTime: string;
    timeZone: string;
  };
  end: {
    dateTime: string;
    timeZone: string;
  };
  location: {
    displayName: string;
    address?: any;
  };
  body_preview: string;
  attendees: Array<{
    emailAddress: {
      name: string;
      address: string;
    };
    status?: any;
  }>;
  importance: string;
  show_as: string;
  is_all_day: boolean;
  sensitivity: string;
  online_meeting?: {
    joinUrl: string;
    conferenceId: string;
  };
  web_link: string;
}

interface OneDriveFile {
  id: string;
  name: string;
  size: number;
  last_modified_date_time: string;
  parent_reference: {
    path: string;
    id: string;
  };
  web_url: string;
  file?: {
    mimeType: string;
    hashes?: {
      sha1Hash: string;
    };
  };
  folder?: {
    childCount?: number;
  };
  is_folder: boolean;
  thumbnails: Array<{
    id: string;
    large?: {
      url: string;
      width: number;
      height: number;
    };
  }>;
  created_date_time: string;
  content_type: string;
}

interface TeamsChannel {
  id: string;
  display_name: string;
  description: string;
  is_favorite_by_default: boolean;
  email: string;
  membership_type: string;
  web_url: string;
}

interface MicrosoftUser {
  id: string;
  display_name: string;
  user_principal_name: string;
  job_title: string;
  office_location: string;
  business_phones: string[];
  mobile_phone: string;
}

/**
 * Enhanced Microsoft Integration Manager
 * Complete Microsoft ecosystem integration: Outlook, Calendar, OneDrive, Teams, SharePoint
 */
export const MicrosoftIntegrationManager: React.FC<MicrosoftIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Microsoft',
    platform: 'microsoft',
    enabled: true,
    settings: {
      services: ['outlook', 'calendar', 'onedrive', 'teams', 'sharepoint'],
      contentTypes: ['messages', 'events', 'files', 'channels', 'sites'],
      dateRange: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
        end: new Date(),
      },
      includeAttachments: true,
      includeDeleted: false,
      maxItems: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      notificationEvents: ['new_message', 'event_reminder', 'file_shared', 'team_message'],
      calendarIds: ['primary'],
      oneDriveFolders: [],
      teamsChannels: [],
      searchQueries: {
        outlook: '',
        onedrive: '',
        calendar: '',
        teams: ''
      },
      filters: {
        outlook: {
          unreadOnly: false,
          importantOnly: false,
          hasAttachments: false,
          importance: ''
        },
        calendar: {
          onlyAttendee: false,
          onlyConfirmed: false,
          importance: ''
        },
        onedrive: {
          mimeType: '',
          folderIds: []
        }
      }
    }
  });

  // Data states
  const [messages, setMessages] = useState<OutlookMessage[]>([]);
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [files, setFiles] = useState<OneDriveFile[]>([]);
  const [channels, setChannels] = useState<TeamsChannel[]>([]);
  const [currentUser, setCurrentUser] = useState<MicrosoftUser | null>(null);
  
  // UI states
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<DataSourceHealth | null>(null);
  const [activeTab, setActiveTab] = useState(0);
  const [searchQuery, setSearchQuery] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showTokenDetails, setShowTokenDetails] = useState(false);
  const [ingestionStatus, setIngestionStatus] = useState<IngestionStatus>({
    running: false,
    progress: 0,
    messagesProcessed: 0,
    eventsProcessed: 0,
    filesProcessed: 0,
    channelsProcessed: 0,
    sitesProcessed: 0,
    errors: []
  });

  // Modal states
  const [composeModalOpen, setComposeModalOpen] = useState(false);
  const [createEventModalOpen, setCreateEventModalOpen] = useState(false);
  const [createDocModalOpen, setCreateDocModalOpen] = useState(false);
  const [sendTeamsModalOpen, setSendTeamsModalOpen] = useState(false);
  
  // Form states
  const [composeForm, setComposeForm] = useState({
    to: '',
    subject: '',
    body: '',
    cc: '',
    bcc: ''
  });
  
  const [eventForm, setEventForm] = useState({
    summary: '',
    description: '',
    location: '',
    startTime: '',
    endTime: '',
    attendees: '',
    importance: 'normal'
  });
  
  const [docForm, setDocForm] = useState({
    name: '',
    content: '',
    folder: '',
    template: 'blank'
  });
  
  const [teamsForm, setTeamsForm] = useState({
    channel: '',
    content: ''
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('microsoft_access_token_placeholder');

  useEffect(() => {
    checkMicrosoftHealth();
  }, []);

  useEffect(() => {
    if (health?.connected) {
      loadMicrosoftData();
    }
  }, [health]);

  const checkMicrosoftHealth = async () => {
    try {
      const response = await fetch('/api/integrations/microsoft/health');
      const data = await response.json();
      
      if (data.status === 'healthy') {
        setHealth({
          connected: true,
          lastSync: new Date().toISOString(),
          errors: []
        });
      } else {
        setHealth({
          connected: false,
          lastSync: new Date().toISOString(),
          errors: [data.error || 'Microsoft service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Microsoft service health']
      });
    }
  };

  const loadMicrosoftData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        loadMessages(),
        loadEvents(),
        loadFiles(),
        loadTeamsChannels(),
        loadUserProfile()
      ]);
    } catch (err) {
      setError('Failed to load Microsoft data');
      toast({
        title: 'Error',
        description: 'Failed to load Microsoft data',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (query?: string) => {
    try {
      const response = await fetch('/api/integrations/microsoft/outlook/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: query || config.settings.searchQueries.outlook,
          top: 50,
          select: 'id,subject,from,toRecipients,bodyPreview,receivedDateTime,hasAttachments,isRead,importance',
          filter: config.settings.filters.outlook.unreadOnly ? 'isRead eq false' : '',
          order_by: 'receivedDateTime desc'
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setMessages(data.data.messages || []);
      }
    } catch (err) {
      console.error('Error loading messages:', err);
    }
  };

  const loadEvents = async () => {
    try {
      const response = await fetch('/api/integrations/microsoft/calendar/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          calendar_id: 'primary',
          start_datetime: config.settings.dateRange.start.toISOString(),
          end_datetime: config.settings.dateRange.end.toISOString(),
          top: 50,
          select: 'id,subject,start,end,location,bodyPreview,attendees,importance,showAs',
          order_by: 'start/dateTime'
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setEvents(data.data.events || []);
      }
    } catch (err) {
      console.error('Error loading events:', err);
    }
  };

  const loadFiles = async (query?: string) => {
    try {
      const response = await fetch('/api/integrations/microsoft/onedrive/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          q: query || config.settings.searchQueries.onedrive,
          top: 50,
          select: 'id,name,size,lastModifiedDateTime,parentReference,webUrl,file,folder',
          filter: config.settings.filters.onedrive.mimeType ? `file/mimeType eq '${config.settings.filters.onedrive.mimeType}'` : '',
          order_by: 'lastModifiedDateTime desc'
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setFiles(data.data.files || []);
      }
    } catch (err) {
      console.error('Error loading files:', err);
    }
  };

  const loadTeamsChannels = async () => {
    try {
      const response = await fetch('/api/integrations/microsoft/teams/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          top: 50
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setChannels(data.data.channels || []);
      }
    } catch (err) {
      console.error('Error loading Teams channels:', err);
    }
  };

  const loadUserProfile = async () => {
    try {
      const response = await fetch('/api/integrations/microsoft/user/profile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      if (data.ok) {
        setCurrentUser(data.data.user);
      }
    } catch (err) {
      console.error('Error loading user profile:', err);
    }
  };

  const sendMessage = async () => {
    if (!composeForm.to.trim() || !composeForm.subject.trim()) {
      toast({
        title: 'Error',
        description: 'Recipient and subject are required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/microsoft/outlook/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'send',
          data: {
            to: composeForm.to,
            subject: composeForm.subject,
            body: composeForm.body,
            cc: composeForm.cc,
            bcc: composeForm.bcc
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Message sent successfully',
          status: 'success',
          duration: 3000
        });
        
        setComposeForm({ to: '', subject: '', body: '', cc: '', bcc: '' });
        setComposeModalOpen(false);
        await loadMessages();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to send message',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to send message',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const createEvent = async () => {
    if (!eventForm.summary.trim()) {
      toast({
        title: 'Error',
        description: 'Event title is required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/microsoft/calendar/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            summary: eventForm.summary,
            description: eventForm.description,
            start: {
              dateTime: eventForm.startTime,
              timeZone: 'UTC'
            },
            end: {
              dateTime: eventForm.endTime,
              timeZone: 'UTC'
            },
            location: {
              displayName: eventForm.location
            },
            attendees: eventForm.attendees.split(',').map((email: string) => ({
              emailAddress: {
                address: email.trim()
              }
            })),
            importance: eventForm.importance
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Calendar event created successfully',
          status: 'success',
          duration: 3000
        });
        
        setEventForm({ summary: '', description: '', location: '', startTime: '', endTime: '', attendees: '', importance: 'normal' });
        setCreateEventModalOpen(false);
        await loadEvents();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to create event',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to create event',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const createDocument = async () => {
    if (!docForm.name.trim()) {
      toast({
        title: 'Error',
        description: 'Document name is required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/microsoft/onedrive/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            name: docForm.name,
            content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            parents: docForm.folder ? [docForm.folder] : []
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Document created successfully',
          status: 'success',
          duration: 3000
        });
        
        setDocForm({ name: '', content: '', folder: '', template: 'blank' });
        setCreateDocModalOpen(false);
        await loadFiles();
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to create document',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to create document',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const sendTeamsMessage = async () => {
    if (!teamsForm.channel.trim() || !teamsForm.content.trim()) {
      toast({
        title: 'Error',
        description: 'Channel and message are required',
        status: 'error',
        duration: 3000
      });
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/microsoft/teams/channels', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'send_message',
          channel_id: teamsForm.channel,
          data: {
            content: teamsForm.content
          }
        })
      });

      const result = await response.json();
      if (result.ok) {
        toast({
          title: 'Success',
          description: 'Teams message sent successfully',
          status: 'success',
          duration: 3000
        });
        
        setTeamsForm({ channel: '', content: '' });
        setSendTeamsModalOpen(false);
      } else {
        toast({
          title: 'Error',
          description: result.error?.message || 'Failed to send Teams message',
          status: 'error',
          duration: 3000
        });
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to send Teams message',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const searchMicrosoftSuite = async () => {
    if (!searchQuery.trim()) {
      await Promise.all([
        loadMessages(),
        loadEvents(),
        loadFiles()
      ]);
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/microsoft/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: searchQuery,
          services: ['outlook', 'onedrive', 'calendar'],
          top: 20
        })
      });

      const result = await response.json();
      if (result.ok) {
        const searchResults = result.data.results || [];
        
        // Update data based on search results
        const outlookResults = searchResults.filter((r: any) => r.service === 'outlook');
        const calendarResults = searchResults.filter((r: any) => r.service === 'calendar');
        const onedriveResults = searchResults.filter((r: any) => r.service === 'onedrive');
        
        if (outlookResults.length > 0) {
          const searchMessages = outlookResults.map((r: any) => ({
            id: r.id,
            subject: r.title,
            from: { emailAddress: { name: 'Unknown', address: 'unknown@example.com' } },
            to: [],
            body_preview: r.snippet,
            received_date_time: r.created_date_time,
            has_attachments: false,
            is_read: false,
            importance: 'normal',
            conversation_id: r.id,
            web_link: r.url
          }));
          setMessages(searchMessages);
        }
        
        if (calendarResults.length > 0) {
          const searchEvents = calendarResults.map((r: any) => ({
            id: r.id,
            subject: r.title,
            start: { dateTime: r.created_date_time, timeZone: 'UTC' },
            end: { dateTime: r.created_date_time, timeZone: 'UTC' },
            location: { displayName: 'Unknown' },
            body_preview: r.snippet,
            attendees: [],
            importance: 'normal',
            show_as: 'busy',
            is_all_day: false,
            sensitivity: 'normal',
            web_link: r.url
          }));
          setEvents(searchEvents);
        }
        
        if (onedriveResults.length > 0) {
          const searchFiles = onedriveResults.map((r: any) => ({
            id: r.id,
            name: r.title,
            size: 0,
            last_modified_date_time: r.created_date_time,
            parent_reference: { path: '/Documents', id: 'folder_root' },
            web_url: r.url,
            file: { mimeType: 'application/pdf' },
            folder: null,
            is_folder: false,
            thumbnails: [],
            created_date_time: r.created_date_time,
            content_type: 'application/pdf'
          }));
          setFiles(searchFiles);
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to search Microsoft Suite',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const startMicrosoftOAuth = async () => {
    try {
      const response = await fetch('/api/auth/microsoft/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'https://graph.microsoft.com/Mail.Read',
            'https://graph.microsoft.com/Mail.Send',
            'https://graph.microsoft.com/Calendars.Read',
            'https://graph.microsoft.com/Calendars.ReadWrite',
            'https://graph.microsoft.com/Files.Read',
            'https://graph.microsoft.com/Files.ReadWrite',
            'https://graph.microsoft.com/Sites.Read.All',
            'https://graph.microsoft.com/Team.ReadBasic.All',
            'https://graph.microsoft.com/Channel.ReadBasic.All'
          ],
          redirect_uri: 'http://localhost:3000/oauth/microsoft/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        const popup = window.open(
          data.authorization_url,
          'microsoft-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkMicrosoftHealth();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Microsoft OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Microsoft OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const renderMessageCard = (message: OutlookMessage) => (
    <Card key={message.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Avatar
                name={message.from.emailAddress.name}
                size="sm"
                bg="blue.500"
                color="white"
              />
              <VStack align="start" spacing={0}>
                <Text fontWeight="medium">{message.from.emailAddress.name}</Text>
                <Text fontSize="xs" color="gray.500">
                  {message.from.emailAddress.address}
                </Text>
                <Text fontSize="xs" color="gray.500">
                  {new Date(message.received_date_time).toLocaleDateString()} • {new Date(message.received_date_time).toLocaleTimeString()}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              {!message.is_read && <Badge colorScheme="blue">Unread</Badge>}
              {message.importance === 'high' && <Badge colorScheme="red">Important</Badge>}
              {message.has_attachments && <Icon as={PaperclipIcon} color="gray.500" />}
            </HStack>
          </HStack>
          
          <Heading size="sm" noOfLines={2}>
            {message.subject || '(No Subject)'}
          </Heading>
          
          <Text fontSize="sm" color="gray.600" noOfLines={3}>
            {message.body_preview}
          </Text>
          
          <HStack justify="space-between" w="full">
            <HStack spacing={2} fontSize="xs" color="gray.500">
              <Tag size="sm" colorScheme="gray">
                <TagLabel>Inbox</TagLabel>
              </Tag>
            </HStack>
            
            <HStack>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<ViewIcon />}
                onClick={() => window.open(message.web_link, '_blank')}
              >
                View
              </Button>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<ReplyIcon />}
                onClick={() => {
                  setComposeForm({
                    ...composeForm,
                    to: message.from.emailAddress.address,
                    subject: `Re: ${message.subject || '(No Subject)'}`
                  });
                  setComposeModalOpen(true);
                }}
              >
                Reply
              </Button>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<ForwardIcon />}
              >
                Forward
              </Button>
            </HStack>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderEventCard = (event: CalendarEvent) => (
    <Card key={event.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <Heading size="sm" noOfLines={2}>
              {event.subject}
            </Heading>
            <HStack>
              {event.importance === 'high' ? (
                <Badge colorScheme="red">High Priority</Badge>
              ) : (
                <Badge colorScheme="green">Confirmed</Badge>
              )}
              {event.online_meeting && <Icon as={VideoIcon} color="blue.500" />}
            </HStack>
          </HStack>
          
          {event.body_preview && (
            <Text fontSize="sm" color="gray.600" noOfLines={3}>
              {event.body_preview}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            {event.location.displayName && (
              <HStack>
                <Icon as={LocationIcon} />
                <Text>{event.location.displayName}</Text>
              </HStack>
            )}
            <HStack>
              <Icon as={ClockIcon} />
              <Text>
                {new Date(event.start.dateTime || event.start.date).toLocaleString()} - 
                {new Date(event.end.dateTime || event.end.date).toLocaleString()}
              </Text>
            </HStack>
          </HStack>
          
          {event.attendees && event.attendees.length > 0 && (
            <HStack spacing={2}>
              {event.attendees.slice(0, 3).map((attendee, index) => (
                <Tag key={index} size="sm" colorScheme="blue">
                  <TagLabel>{attendee.emailAddress.displayName || attendee.emailAddress.address}</TagLabel>
                </Tag>
              ))}
              {event.attendees.length > 3 && (
                <Tag size="sm" colorScheme="gray">
                  <TagLabel>+{event.attendees.length - 3} more</TagLabel>
                </Tag>
              )}
            </HStack>
          )}
          
          {event.online_meeting && (
            <HStack>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<VideoIcon />}
                onClick={() => window.open(event.online_meeting!.joinUrl, '_blank')}
              >
                Join Teams Meeting
              </Button>
            </HStack>
          )}
          
          <HStack justify="space-between" w="full">
            <HStack>
              <Badge size="sm" colorScheme="purple">
                {event.sensitivity === 'private' ? 'Private' : 'Public'}
              </Badge>
              {event.is_all_day && (
                <Badge size="sm" colorScheme="orange">All Day</Badge>
              )}
            </HStack>
            
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<ExternalLinkIcon />}
              onClick={() => window.open(event.web_link, '_blank')}
            >
              Open in Calendar
            </Button>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderFileCard = (file: OneDriveFile) => (
    <Card key={file.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack>
            {file.thumbnails && file.thumbnails.length > 0 ? (
              <Image
                src={file.thumbnails[0].large?.url}
                alt={file.name}
                boxSize="12"
                objectFit="cover"
                borderRadius="md"
              />
            ) : (
              <Box
                w="12"
                h="12"
                rounded="md"
                bg={getFileColor(file.content_type || file.folder ? 'folder' : '')}
                display="flex"
                alignItems="center"
                justifyContent="center"
              >
                <Icon as={getFileIcon(file.content_type || file.folder ? 'folder' : '')} color="white" />
              </Box>
            )}
            
            <VStack align="start" spacing={1} flex={1}>
              <Heading size="sm" noOfLines={2}>
                {file.name}
              </Heading>
              <HStack spacing={2} fontSize="xs" color="gray.500">
                <Tag size="sm" colorScheme={getFileTypeColor(file.content_type || file.folder ? 'folder' : '')}>
                  <TagLabel>{getFileTypeLabel(file.content_type || file.folder ? 'folder' : '')}</TagLabel>
                </Tag>
                {file.size > 0 && <Text>{formatFileSize(file.size)}</Text>}
                {file.is_folder && <Icon as={FolderIcon} />}
              </HStack>
              <Text fontSize="xs" color="gray.400">
                Modified {new Date(file.last_modified_date_time).toLocaleDateString()}
              </Text>
            </VStack>
          </HStack>
          
          <HStack justify="space-between" w="full">
            <HStack>
              {file.is_folder && (
                <Badge size="sm" colorScheme="green">Folder</Badge>
              )}
              {file.file && file.file.mimeType && (
                <Badge size="sm" colorScheme="blue">{file.file.mimeType.split('.')[0]}</Badge>
              )}
            </HStack>
            
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<ExternalLinkIcon />}
              onClick={() => window.open(file.web_url, '_blank')}
            >
              Open
            </Button>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderChannelCard = (channel: TeamsChannel) => (
    <Card key={channel.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <VStack align="start" spacing={1}>
              <Heading size="sm">{channel.display_name}</Heading>
              <Text fontSize="sm" color="gray.600" noOfLines={2}>
                {channel.description}
              </Text>
            </VStack>
            <HStack>
              {channel.is_favorite_by_default && <Icon as={StarIcon} color="yellow.500" />}
              <Badge colorScheme="blue">{channel.membership_type}</Badge>
            </HStack>
          </HStack>
          
          <HStack spacing={2} fontSize="xs" color="gray.500">
            <Tag size="sm" colorScheme="gray">
              <TagLabel>{channel.email}</TagLabel>
            </Tag>
          </HStack>
          
          <HStack justify="space-between" w="full">
            <Text fontSize="xs" color="gray.400">
              Channel ID: {channel.id}
            </Text>
            
            <HStack>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<ChatIcon />}
                onClick={() => {
                  setTeamsForm({
                    channel: channel.id,
                    content: ''
                  });
                  setSendTeamsModalOpen(true);
                }}
              >
                Send Message
              </Button>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<ExternalLinkIcon />}
                onClick={() => window.open(channel.web_url, '_blank')}
              >
                Open in Teams
              </Button>
            </HStack>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const getFileColor = (mimeType: string): string => {
    if (mimeType === 'folder') return 'green.500';
    if (mimeType.includes('word')) return 'blue.500';
    if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return 'green.600';
    if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return 'orange.500';
    if (mimeType.includes('pdf')) return 'red.500';
    if (mimeType.includes('image')) return 'purple.500';
    if (mimeType.includes('video')) return 'pink.500';
    return 'gray.500';
  };

  const getFileIcon = (mimeType: string) => {
    if (mimeType === 'folder') return FolderIcon;
    if (mimeType.includes('word')) return DocumentIcon;
    if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return ViewListIcon;
    if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return DesktopIcon;
    if (mimeType.includes('pdf')) return DocumentIcon;
    if (mimeType.includes('image')) return ImageIcon;
    if (mimeType.includes('video')) return VideoIcon;
    return DocumentIcon;
  };

  const getFileTypeColor = (mimeType: string): string => {
    if (mimeType === 'folder') return 'green';
    if (mimeType.includes('word')) return 'blue';
    if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return 'green';
    if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return 'orange';
    if (mimeType.includes('pdf')) return 'red';
    if (mimeType.includes('image')) return 'purple';
    if (mimeType.includes('video')) return 'pink';
    return 'gray';
  };

  const getFileTypeLabel = (mimeType: string): string => {
    if (mimeType === 'folder') return 'Folder';
    if (mimeType.includes('word')) return 'Word Doc';
    if (mimeType.includes('excel') || mimeType.includes('spreadsheet')) return 'Excel';
    if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return 'PowerPoint';
    if (mimeType.includes('pdf')) return 'PDF';
    if (mimeType.includes('image')) return 'Image';
    if (mimeType.includes('video')) return 'Video';
    return 'File';
  };

  const formatFileSize = (size: number): string => {
    if (size === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(size) / Math.log(k));
    return parseFloat((size / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Import missing icons
  const PaperclipIcon = (props: any) => <Icon as={AttachmentIcon} {...props} />;
  const ReplyIcon = (props: any) => <Icon as={ChatIcon} {...props} />;
  const ForwardIcon = (props: any) => <Icon as={ShareIcon} {...props} />;
  const VideoIcon = (props: any) => <Icon as={VideoCallIcon} {...props} />;
  const LocationIcon = (props: any) => <Icon as={PlaceIcon} {...props} />;
  const AttachmentIcon = (props: any) => <Icon as={PaperclipIcon} {...props} />;
  const VideoCallIcon = (props: any) => <Icon as={PhoneIcon} {...props} />;
  const PlaceIcon = (props: any) => <Icon as={LocationIcon} {...props} />;
  const ImageIcon = (props: any) => <Icon as={ImageIcon} {...props} />;

  if (!health?.connected) {
    return (
      <Box p={6}>
        <Alert status="warning">
          <AlertIcon />
          <AlertTitle>Microsoft Not Connected</AlertTitle>
          <AlertDescription>
            Please connect your Microsoft account to access Outlook, Calendar, OneDrive, Teams, and SharePoint.
          </AlertDescription>
        </Alert>
        <Button
          mt={4}
          colorScheme="blue"
          onClick={startMicrosoftOAuth}
        >
          Connect Microsoft Account
        </Button>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>Microsoft Integration</Heading>
          <Text color="gray.600">Manage Outlook, Calendar, OneDrive, Teams, and SharePoint services</Text>
        </Box>

        {/* Search and Actions */}
        <HStack spacing={4}>
          <Input
            placeholder="Search Outlook, Calendar, OneDrive, Teams..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && searchMicrosoftSuite()}
            flex={1}
          />
          <Button
            leftIcon={<SearchIcon />}
            colorScheme="blue"
            onClick={searchMicrosoftSuite}
            isLoading={loading}
          >
            Search
          </Button>
          
          <Button
            leftIcon={<EmailIcon />}
            colorScheme="blue"
            onClick={() => setComposeModalOpen(true)}
          >
            Compose
          </Button>
          
          <Button
            leftIcon={<CalendarIcon />}
            colorScheme="purple"
            onClick={() => setCreateEventModalOpen(true)}
          >
            New Event
          </Button>
          
          <Button
            leftIcon={<DocumentIcon />}
            colorScheme="green"
            onClick={() => setCreateDocModalOpen(true)}
          >
            New Doc
          </Button>
          
          <Button
            leftIcon={<TeamIcon />}
            colorScheme="orange"
            onClick={() => setSendTeamsModalOpen(true)}
          >
            Teams Msg
          </Button>
        </HStack>

        {/* Main Content Tabs */}
        <Tabs index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>
              <HStack>
                <Icon as={EmailIcon} />
                <Text>Outlook ({messages.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <Icon as={CalendarIcon} />
                <Text>Calendar ({events.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <Icon as={FolderIcon} />
                <Text>OneDrive ({files.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <Icon as={TeamIcon} />
                <Text>Teams ({channels.length})</Text>
              </HStack>
            </Tab>
            <Tab>
              <HStack>
                <Icon as={UserIcon} />
                <Text>Profile</Text>
              </HStack>
            </Tab>
          </TabList>

          <TabPanels>
            {/* Outlook Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : messages.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <Icon as={EmailIcon} fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No messages found</Text>
                  <Button
                    mt={4}
                    colorScheme="blue"
                    onClick={() => setComposeModalOpen(true)}
                  >
                    Compose Your First Email
                  </Button>
                </Box>
              ) : (
                <VStack spacing={4} align="stretch">
                  {messages.map(renderMessageCard)}
                </VStack>
              )}
            </TabPanel>

            {/* Calendar Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : events.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <Icon as={CalendarIcon} fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No events found</Text>
                  <Button
                    mt={4}
                    colorScheme="purple"
                    onClick={() => setCreateEventModalOpen(true)}
                  >
                    Create Your First Event
                  </Button>
                </Box>
              ) : (
                <VStack spacing={4} align="stretch">
                  {events.map(renderEventCard)}
                </VStack>
              )}
            </TabPanel>

            {/* OneDrive Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : files.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <Icon as={FolderIcon} fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No files found</Text>
                  <Button
                    mt={4}
                    colorScheme="green"
                    onClick={() => setCreateDocModalOpen(true)}
                  >
                    Create Your First Document
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {files.map(renderFileCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Teams Tab */}
            <TabPanel>
              {loading ? (
                <Box display="flex" justifyContent="center" p={8}>
                  <Spinner size="xl" />
                </Box>
              ) : channels.length === 0 ? (
                <Box textAlign="center" p={8}>
                  <Icon as={TeamIcon} fontSize="4xl" color="gray.300" mb={4} />
                  <Text color="gray.500">No channels found</Text>
                  <Button
                    mt={4}
                    colorScheme="orange"
                    onClick={() => setSendTeamsModalOpen(true)}
                  >
                    Send Your First Message
                  </Button>
                </Box>
              ) : (
                <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                  {channels.map(renderChannelCard)}
                </SimpleGrid>
              )}
            </TabPanel>

            {/* Profile Tab */}
            <TabPanel>
              <Card>
                <CardBody p={6}>
                  <VStack spacing={4} align="center">
                    <Avatar
                      name={currentUser?.display_name}
                      size="2xl"
                      bg="blue.500"
                      color="white"
                    />
                    <VStack align="center" spacing={2}>
                      <Heading size="lg">{currentUser?.display_name}</Heading>
                      <Text color="gray.600">{currentUser?.user_principal_name}</Text>
                      {currentUser?.job_title && (
                        <Text fontSize="sm" color="gray.500">
                          {currentUser.job_title}
                        </Text>
                      )}
                      {currentUser?.office_location && (
                        <Text fontSize="sm" color="gray.500">
                          {currentUser.office_location}
                        </Text>
                      )}
                    </VStack>
                    
                    <Divider />
                    
                    <VStack align="start" spacing={2} w="full">
                      <HStack justify="space-between" w="full">
                        <Text>Services</Text>
                        <HStack>
                          <Badge colorScheme="blue">Outlook</Badge>
                          <Badge colorScheme="purple">Calendar</Badge>
                          <Badge colorScheme="green">OneDrive</Badge>
                          <Badge colorScheme="orange">Teams</Badge>
                          <Badge colorScheme="red">SharePoint</Badge>
                        </HStack>
                      </HStack>
                      
                      <HStack justify="space-between" w="full">
                        <Text>Contact Info</Text>
                        <HStack>
                          {currentUser?.business_phones && currentUser.business_phones.length > 0 && (
                            <Text fontSize="sm">{currentUser.business_phones[0]}</Text>
                          )}
                          {currentUser?.mobile_phone && (
                            <Text fontSize="sm">{currentUser.mobile_phone}</Text>
                          )}
                        </HStack>
                      </HStack>
                      
                      <Button
                        colorScheme="blue"
                        onClick={() => window.open('https://account.microsoft.com', '_blank')}
                      >
                        Manage Microsoft Account
                      </Button>
                    </VStack>
                  </VStack>
                </CardBody>
              </Card>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Compose Email Modal */}
        <Modal isOpen={composeModalOpen} onClose={() => setComposeModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Compose Outlook Email</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>To</FormLabel>
                  <Input
                    value={composeForm.to}
                    onChange={(e) => setComposeForm({...composeForm, to: e.target.value})}
                    placeholder="recipient@example.com"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Cc</FormLabel>
                  <Input
                    value={composeForm.cc}
                    onChange={(e) => setComposeForm({...composeForm, cc: e.target.value})}
                    placeholder="cc@example.com"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Bcc</FormLabel>
                  <Input
                    value={composeForm.bcc}
                    onChange={(e) => setComposeForm({...composeForm, bcc: e.target.value})}
                    placeholder="bcc@example.com"
                  />
                </FormControl>
                
                <FormControl isRequired>
                  <FormLabel>Subject</FormLabel>
                  <Input
                    value={composeForm.subject}
                    onChange={(e) => setComposeForm({...composeForm, subject: e.target.value})}
                    placeholder="Email subject"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Message</FormLabel>
                  <Textarea
                    value={composeForm.body}
                    onChange={(e) => setComposeForm({...composeForm, body: e.target.value})}
                    placeholder="Type your message here..."
                    rows={8}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setComposeModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="blue"
                onClick={sendMessage}
                isLoading={loading}
              >
                Send
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Event Modal */}
        <Modal isOpen={createEventModalOpen} onClose={() => setCreateEventModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create Calendar Event</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Event Title</FormLabel>
                  <Input
                    value={eventForm.summary}
                    onChange={(e) => setEventForm({...eventForm, summary: e.target.value})}
                    placeholder="Event title"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={eventForm.description}
                    onChange={(e) => setEventForm({...eventForm, description: e.target.value})}
                    placeholder="Event description"
                    rows={3}
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Location</FormLabel>
                  <Input
                    value={eventForm.location}
                    onChange={(e) => setEventForm({...eventForm, location: e.target.value})}
                    placeholder="Event location"
                  />
                </FormControl>
                
                <HStack>
                  <FormControl isRequired>
                    <FormLabel>Start Time</FormLabel>
                    <Input
                      type="datetime-local"
                      value={eventForm.startTime}
                      onChange={(e) => setEventForm({...eventForm, startTime: e.target.value})}
                    />
                  </FormControl>
                  
                  <FormControl isRequired>
                    <FormLabel>End Time</FormLabel>
                    <Input
                      type="datetime-local"
                      value={eventForm.endTime}
                      onChange={(e) => setEventForm({...eventForm, endTime: e.target.value})}
                    />
                  </FormControl>
                </HStack>
                
                <FormControl>
                  <FormLabel>Attendees</FormLabel>
                  <Input
                    value={eventForm.attendees}
                    onChange={(e) => setEventForm({...eventForm, attendees: e.target.value})}
                    placeholder="email1@example.com, email2@example.com"
                  />
                  <FormHelperText>
                    Separate multiple attendees with commas
                  </FormHelperText>
                </FormControl>
                
                <FormControl>
                  <FormLabel>Importance</FormLabel>
                  <Select
                    value={eventForm.importance}
                    onChange={(e) => setEventForm({...eventForm, importance: e.target.value})}
                  >
                    <option value="low">Low</option>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                  </Select>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateEventModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="purple"
                onClick={createEvent}
                isLoading={loading}
              >
                Create Event
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Create Document Modal */}
        <Modal isOpen={createDocModalOpen} onClose={() => setCreateDocModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create OneDrive Document</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Document Name</FormLabel>
                  <Input
                    value={docForm.name}
                    onChange={(e) => setDocForm({...docForm, name: e.target.value})}
                    placeholder="Document name"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Folder</FormLabel>
                  <Input
                    value={docForm.folder}
                    onChange={(e) => setDocForm({...docForm, folder: e.target.value})}
                    placeholder="Folder path (optional)"
                  />
                </FormControl>
                
                <FormControl>
                  <FormLabel>Template</FormLabel>
                  <Select
                    value={docForm.template}
                    onChange={(e) => setDocForm({...docForm, template: e.target.value})}
                  >
                    <option value="blank">Blank document</option>
                    <option value="resume">Resume</option>
                    <option value="report">Report</option>
                    <option value="meeting">Meeting notes</option>
                    <option value="project">Project proposal</option>
                  </Select>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setCreateDocModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="green"
                onClick={createDocument}
                isLoading={loading}
              >
                Create Document
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Send Teams Message Modal */}
        <Modal isOpen={sendTeamsModalOpen} onClose={() => setSendTeamsModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Send Teams Message</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Channel</FormLabel>
                  <Select
                    value={teamsForm.channel}
                    onChange={(e) => setTeamsForm({...teamsForm, channel: e.target.value})}
                    placeholder="Select a channel"
                  >
                    {channels.map((channel) => (
                      <option key={channel.id} value={channel.id}>
                        {channel.display_name}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                
                <FormControl isRequired>
                  <FormLabel>Message</FormLabel>
                  <Textarea
                    value={teamsForm.content}
                    onChange={(e) => setTeamsForm({...teamsForm, content: e.target.value})}
                    placeholder="Type your message here..."
                    rows={6}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setSendTeamsModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={sendTeamsMessage}
                isLoading={loading}
              >
                Send Message
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default MicrosoftIntegrationManager;