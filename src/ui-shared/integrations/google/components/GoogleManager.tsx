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
  useNumberInput,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Spinner,
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
} from '@chakra-ui/icons';
import {
  ATOMDataSource,
  AtomIngestionPipeline,
  DataSourceConfig,
  IngestionStatus,
  DataSourceHealth,
} from '@shared/ui-shared/data-sources/types';

interface GoogleIntegrationProps {
  atomIngestionPipeline: AtomIngestionPipeline;
  onIngestionComplete?: (result: any) => void;
  onConfigurationChange?: (config: DataSourceConfig) => void;
  onError?: (error: Error) => void;
  userId?: string;
}

interface GoogleMessage {
  id: string;
  thread_id: string;
  snippet: string;
  subject: string;
  from: string;
  to: string;
  date: string;
  labels: string[];
  size_estimate: number;
  history_id: string;
  internal_date: string;
  is_unread: boolean;
  is_important: boolean;
  has_attachments: boolean;
  url: string;
}

interface GoogleEvent {
  id: string;
  summary: string;
  description: string;
  location: string;
  start: any;
  end: any;
  all_day: boolean;
  status: string;
  visibility: string;
  attendees: Array<{email: string, displayName?: string, responseStatus?: string}>;
  creator: {email: string, displayName?: string};
  organizer: {email: string, displayName?: string};
  hangout_link: string;
  conference_data?: any;
  recurrence: string[];
  reminders: any;
  attachments: any[];
  color_id: string;
  url: string;
}

interface GoogleFile {
  id: string;
  name: string;
  mimeType: string;
  size: string;
  created_time: string;
  modified_time: string;
  parents: string[];
  web_view_link: string;
  web_content_link: string;
  icon_link: string;
  thumbnail_link: string;
  is_folder: boolean;
  is_google_doc: boolean;
  file_extension: string;
  full_file_extension: string;
  md5_checksum: string;
  version: string;
  original_filename: string;
  url: string;
}

interface GoogleUser {
  id: string;
  name: string;
  email: string;
  picture: string;
  verified_email: boolean;
  hd: string;
}

/**
 * Enhanced Google Integration Manager
 * Complete Google ecosystem integration: Gmail, Calendar, Drive, Docs, Sheets, Slides
 */
export const GoogleIntegrationManager: React.FC<GoogleIntegrationProps> = ({
  atomIngestionPipeline,
  onIngestionComplete,
  onConfigurationChange,
  onError,
  userId = 'default-user',
}) => {
  const [config, setConfig] = useState<DataSourceConfig>({
    name: 'Google',
    platform: 'google',
    enabled: true,
    settings: {
      services: ['gmail', 'calendar', 'drive', 'docs', 'sheets', 'slides'],
      contentTypes: ['messages', 'events', 'files', 'contacts', 'tasks'],
      dateRange: {
        start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 days ago
        end: new Date(),
      },
      includeSpamTrash: false,
      includeDeleted: false,
      includeAttachments: true,
      maxItems: 1000,
      realTimeSync: true,
      syncFrequency: 'realtime',
      notificationEvents: ['new_message', 'event_reminder', 'file_shared'],
      calendarIds: ['primary'],
      driveFolders: [],
      searchQueries: {
        gmail: '',
        drive: '',
        calendar: ''
      },
      filters: {
        gmail: {
          unreadOnly: false,
          importantOnly: false,
          hasAttachments: false,
          labelIds: []
        },
        calendar: {
          onlyAttendee: false,
          onlyConfirmed: false
        },
        drive: {
          mimeType: '',
          folderIds: []
        }
      }
    }
  });

  // Data states
  const [messages, setMessages] = useState<GoogleMessage[]>([]);
  const [events, setEvents] = useState<GoogleEvent[]>([]);
  const [files, setFiles] = useState<GoogleFile[]>([]);
  const [currentUser, setCurrentUser] = useState<GoogleUser | null>(null);
  
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
    contactsProcessed: 0,
    tasksProcessed: 0,
    errors: []
  });

  // Modal states
  const [composeModalOpen, setComposeModalOpen] = useState(false);
  const [createEventModalOpen, setCreateEventModalOpen] = useState(false);
  const [createDocModalOpen, setCreateDocModalOpen] = useState(false);
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  
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
    reminders: 'email,10;popup,10'
  });
  
  const [docForm, setDocForm] = useState({
    name: '',
    content: '',
    folder: '',
    template: 'blank'
  });

  const toast = useToast();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const responsiveGridCols = useBreakpointValue({ base: 1, md: 2, lg: 3 });
  const { hasCopied, onCopy } = useClipboard('google_access_token_placeholder');

  useEffect(() => {
    checkGoogleHealth();
  }, []);

  useEffect(() => {
    if (health?.connected) {
      loadGoogleData();
    }
  }, [health]);

  const checkGoogleHealth = async () => {
    try {
      const response = await fetch('/api/integrations/google/health');
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
          errors: [data.error || 'Google service unhealthy']
        });
      }
    } catch (err) {
      setHealth({
        connected: false,
        lastSync: new Date().toISOString(),
        errors: ['Failed to check Google service health']
      });
    }
  };

  const loadGoogleData = async () => {
    setLoading(true);
    setError(null);
    
    try {
      await Promise.all([
        loadMessages(),
        loadEvents(),
        loadFiles(),
        loadUserProfile()
      ]);
    } catch (err) {
      setError('Failed to load Google data');
      toast({
        title: 'Error',
        description: 'Failed to load Google data',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const loadMessages = async (query?: string) => {
    try {
      const response = await fetch('/api/integrations/google/gmail/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: query || config.settings.searchQueries.gmail,
          max_results: 50,
          label_ids: config.settings.filters.gmail.labelIds,
          include_spam_trash: config.settings.includeSpamTrash
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
      const response = await fetch('/api/integrations/google/calendar/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          calendar_id: 'primary',
          time_min: config.settings.dateRange.start.toISOString(),
          time_max: config.settings.dateRange.end.toISOString(),
          max_results: 50,
          single_events: true,
          order_by: 'startTime'
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
      const response = await fetch('/api/integrations/google/drive/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          q: query || config.settings.searchQueries.drive,
          page_size: 50,
          fields: 'nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime, parents, webViewLink, thumbnailLink)',
          order_by: 'modifiedTime desc'
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

  const loadUserProfile = async () => {
    try {
      const response = await fetch('/api/integrations/google/user/profile', {
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
      const response = await fetch('/api/integrations/google/gmail/messages', {
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
        
        // Reset form and close modal
        setComposeForm({ to: '', subject: '', body: '', cc: '', bcc: '' });
        setComposeModalOpen(false);
        
        // Reload messages
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
      const response = await fetch('/api/integrations/google/calendar/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            summary: eventForm.summary,
            description: eventForm.description,
            location: eventForm.location,
            start: {
              dateTime: eventForm.startTime,
              timeZone: 'UTC'
            },
            end: {
              dateTime: eventForm.endTime,
              timeZone: 'UTC'
            },
            attendees: eventForm.attendees.split(',').map((email: string) => ({
              email: email.trim()
            })),
            reminders: {
              overrides: [
                { method: 'email', minutes: 10 },
                { method: 'popup', minutes: 10 }
              ]
            }
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
        
        // Reset form and close modal
        setEventForm({ summary: '', description: '', location: '', startTime: '', endTime: '', attendees: '', reminders: 'email,10;popup,10' });
        setCreateEventModalOpen(false);
        
        // Reload events
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
      const response = await fetch('/api/integrations/google/drive/files', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          operation: 'create',
          data: {
            name: docForm.name,
            mimeType: 'application/vnd.google-apps.document',
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
        
        // Reset form and close modal
        setDocForm({ name: '', content: '', folder: '', template: 'blank' });
        setCreateDocModalOpen(false);
        
        // Reload files
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

  const searchGoogleSuite = async () => {
    if (!searchQuery.trim()) {
      // Load default data
      await loadMessages();
      await loadEvents();
      await loadFiles();
      return;
    }

    setLoading(true);
    try {
      const response = await fetch('/api/integrations/google/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: searchQuery,
          services: ['gmail', 'calendar', 'drive'],
          max_results: 20
        })
      });

      const result = await response.json();
      if (result.ok) {
        // Update data based on search results
        const searchResults = result.data.results || [];
        
        // Group results by service
        const gmailResults = searchResults.filter((r: any) => r.service === 'gmail');
        const calendarResults = searchResults.filter((r: any) => r.service === 'calendar');
        const driveResults = searchResults.filter((r: any) => r.service === 'drive');
        
        // Update state with search results
        if (gmailResults.length > 0) {
          // Convert search results to message format
          const searchMessages = gmailResults.map((r: any) => ({
            id: r.id,
            thread_id: r.id,
            snippet: r.snippet,
            subject: r.title,
            from: 'Unknown',
            to: 'me',
            date: r.created_time,
            labels: [],
            size_estimate: 0,
            history_id: '',
            internal_date: '',
            is_unread: false,
            is_important: false,
            has_attachments: false,
            url: r.url
          }));
          setMessages(searchMessages);
        }
        
        if (calendarResults.length > 0) {
          // Convert search results to event format
          const searchEvents = calendarResults.map((r: any) => ({
            id: r.id,
            summary: r.title,
            description: r.snippet,
            location: '',
            start: { dateTime: r.created_time, timeZone: 'UTC' },
            end: { dateTime: r.created_time, timeZone: 'UTC' },
            all_day: false,
            status: 'confirmed',
            visibility: 'public',
            attendees: [],
            creator: { email: 'me', displayName: 'Me' },
            organizer: { email: 'me', displayName: 'Me' },
            hangout_link: '',
            recurrence: [],
            reminders: { useDefault: true },
            attachments: [],
            color_id: '1',
            url: r.url
          }));
          setEvents(searchEvents);
        }
        
        if (driveResults.length > 0) {
          // Convert search results to file format
          const searchFiles = driveResults.map((r: any) => ({
            id: r.id,
            name: r.title,
            mimeType: 'application/pdf', // Default
            size: '0',
            created_time: r.created_time,
            modified_time: r.created_time,
            parents: [],
            web_view_link: r.url,
            web_content_link: r.url,
            icon_link: '',
            thumbnail_link: '',
            is_folder: false,
            is_google_doc: false,
            file_extension: 'pdf',
            full_file_extension: 'pdf',
            md5_checksum: '',
            version: '1',
            original_filename: r.title,
            url: r.url
          }));
          setFiles(searchFiles);
        }
      }
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to search Google Suite',
        status: 'error',
        duration: 3000
      });
    } finally {
      setLoading(false);
    }
  };

  const startGoogleOAuth = async () => {
    try {
      const response = await fetch('/api/auth/google/authorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          scopes: [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/calendar.readonly',
            'https://www.googleapis.com/auth/calendar.events',
            'https://www.googleapis.com/auth/drive.readonly',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/documents.readonly',
            'https://www.googleapis.com/auth/spreadsheets.readonly',
            'https://www.googleapis.com/auth/presentations.readonly'
          ],
          redirect_uri: 'http://localhost:3000/oauth/google/callback',
          state: `user-${userId}-${Date.now()}`
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Open OAuth URL in popup
        const popup = window.open(
          data.authorization_url,
          'google-oauth',
          'width=500,height=600,scrollbars=yes,resizable=yes'
        );
        
        // Listen for OAuth completion
        const checkOAuth = setInterval(() => {
          if (popup?.closed) {
            clearInterval(checkOAuth);
            checkGoogleHealth();
          }
        }, 1000);
        
      } else {
        toast({
          title: 'OAuth Failed',
          description: data.error || 'Failed to start Google OAuth',
          status: 'error',
          duration: 5000,
        });
      }
    } catch (err) {
      toast({
        title: 'Network Error',
        description: 'Failed to connect to Google OAuth',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const renderMessageCard = (message: GoogleMessage) => (
    <Card key={message.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <HStack>
              <Avatar
                name={message.from}
                size="sm"
                bg="blue.500"
                color="white"
              />
              <VStack align="start" spacing={0}>
                <Text fontWeight="medium">{message.from}</Text>
                <Text fontSize="xs" color="gray.500">
                  {new Date(message.date).toLocaleDateString()} • {new Date(message.date).toLocaleTimeString()}
                </Text>
              </VStack>
            </HStack>
            <HStack>
              {message.is_unread && <Badge colorScheme="blue">Unread</Badge>}
              {message.is_important && <Badge colorScheme="red">Important</Badge>}
              {message.has_attachments && <Icon as={PaperclipIcon} color="gray.500" />}
            </HStack>
          </HStack>
          
          <Heading size="sm" noOfLines={2}>
            {message.subject || '(No Subject)'}
          </Heading>
          
          <Text fontSize="sm" color="gray.600" noOfLines={3}>
            {message.snippet}
          </Text>
          
          <HStack justify="space-between" w="full">
            <HStack spacing={2} fontSize="xs" color="gray.500">
              <Tag size="sm" colorScheme="gray">
                <TagLabel>Inbox</TagLabel>
              </Tag>
              <Text>{message.labels.map((label: string) => label).join(', ')}</Text>
            </HStack>
            
            <HStack>
              <Button
                size="sm"
                variant="ghost"
                leftIcon={<ViewIcon />}
                onClick={() => window.open(message.url, '_blank')}
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
                    to: message.from,
                    subject: `Re: ${message.subject || '(No Subject)'}`
                  });
                  setComposeModalOpen(true);
                }}
              >
                Reply
              </Button>
            </HStack>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderEventCard = (event: GoogleEvent) => (
    <Card key={event.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack justify="space-between" w="full">
            <Heading size="sm" noOfLines={2}>
              {event.summary}
            </Heading>
            <HStack>
              {event.status === 'confirmed' ? (
                <Badge colorScheme="green">Confirmed</Badge>
              ) : (
                <Badge colorScheme="yellow">Tentative</Badge>
              )}
              {event.hangout_link && <Icon as={VideoIcon} color="blue.500" />}
            </HStack>
          </HStack>
          
          {event.description && (
            <Text fontSize="sm" color="gray.600" noOfLines={3}>
              {event.description}
            </Text>
          )}
          
          <HStack spacing={4} fontSize="sm" color="gray.500">
            {event.location && (
              <HStack>
                <Icon as={LocationIcon} />
                <Text>{event.location}</Text>
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
                  <TagLabel>{attendee.displayName || attendee.email}</TagLabel>
                </Tag>
              ))}
              {event.attendees.length > 3 && (
                <Tag size="sm" colorScheme="gray">
                  <TagLabel>+{event.attendees.length - 3} more</TagLabel>
                </Tag>
              )}
            </HStack>
          )}
          
          <HStack justify="space-between" w="full">
            <HStack>
              <Badge size="sm" colorScheme="purple">
                {event.visibility === 'public' ? 'Public' : 'Private'}
              </Badge>
              {event.recurrence && event.recurrence.length > 0 && (
                <Badge size="sm" colorScheme="orange">Recurring</Badge>
              )}
            </HStack>
            
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<ExternalLinkIcon />}
              onClick={() => window.open(event.url, '_blank')}
            >
              Open in Calendar
            </Button>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const renderFileCard = (file: GoogleFile) => (
    <Card key={file.id} overflow="hidden" variant="outline">
      <CardBody p={4}>
        <VStack align="start" spacing={3}>
          <HStack>
            {file.thumbnail_link ? (
              <Image
                src={file.thumbnail_link}
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
                bg={getFileColor(file.mimeType)}
                display="flex"
                alignItems="center"
                justifyContent="center"
              >
                <Icon as={getFileIcon(file.mimeType)} color="white" />
              </Box>
            )}
            
            <VStack align="start" spacing={1} flex={1}>
              <Heading size="sm" noOfLines={2}>
                {file.name}
              </Heading>
              <HStack spacing={2} fontSize="xs" color="gray.500">
                <Tag size="sm" colorScheme={getFileTypeColor(file.mimeType)}>
                  <TagLabel>{getFileTypeLabel(file.mimeType)}</TagLabel>
                </Tag>
                {file.size !== '0' && <Text>{formatFileSize(file.size)}</Text>}
                {file.is_folder && <Icon as={FolderIcon} />}
              </HStack>
              <Text fontSize="xs" color="gray.400">
                Modified {new Date(file.modified_time).toLocaleDateString()}
              </Text>
            </VStack>
          </HStack>
          
          <HStack justify="space-between" w="full">
            <HStack>
              {file.is_google_doc && (
                <Badge size="sm" colorScheme="blue">Google Doc</Badge>
              )}
              {file.is_folder && (
                <Badge size="sm" colorScheme="green">Folder</Badge>
              )}
            </HStack>
            
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<ExternalLinkIcon />}
              onClick={() => window.open(file.url, '_blank')}
            >
              Open
            </Button>
          </HStack>
        </VStack>
      </CardBody>
    </Card>
  );

  const getFileColor = (mimeType: string): string => {
    if (mimeType.includes('folder')) return 'green.500';
    if (mimeType.includes('document')) return 'blue.500';
    if (mimeType.includes('spreadsheet')) return 'green.600';
    if (mimeType.includes('presentation')) return 'orange.500';
    if (mimeType.includes('pdf')) return 'red.500';
    if (mimeType.includes('image')) return 'purple.500';
    if (mimeType.includes('video')) return 'pink.500';
    return 'gray.500';
  };

  const getFileIcon = (mimeType: string) => {
    if (mimeType.includes('folder')) return FolderIcon;
    if (mimeType.includes('document')) return DocumentIcon;
    if (mimeType.includes('spreadsheet')) return TableIcon;
    if (mimeType.includes('presentation')) return SlidesIcon;
    if (mimeType.includes('pdf')) return DocumentIcon;
    if (mimeType.includes('image')) return ImageIcon;
    if (mimeType.includes('video')) return VideoIcon;
    return DocumentIcon;
  };

  const getFileTypeColor = (mimeType: string): string => {
    if (mimeType.includes('folder')) return 'green';
    if (mimeType.includes('document')) return 'blue';
    if (mimeType.includes('spreadsheet')) return 'green';
    if (mimeType.includes('presentation')) return 'orange';
    if (mimeType.includes('pdf')) return 'red';
    if (mimeType.includes('image')) return 'purple';
    if (mimeType.includes('video')) return 'pink';
    return 'gray';
  };

  const getFileTypeLabel = (mimeType: string): string => {
    if (mimeType.includes('folder')) return 'Folder';
    if (mimeType.includes('document')) return 'Doc';
    if (mimeType.includes('spreadsheet')) return 'Sheet';
    if (mimeType.includes('presentation')) return 'Slides';
    if (mimeType.includes('pdf')) return 'PDF';
    if (mimeType.includes('image')) return 'Image';
    if (mimeType.includes('video')) return 'Video';
    return 'File';
  };

  const formatFileSize = (size: string): string => {
    const bytes = parseInt(size);
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Import missing icons
  const PaperclipIcon = (props: any) => <Icon as={AttachmentIcon} {...props} />;
  const ReplyIcon = (props: any) => <Icon as={ChatIcon} {...props} />;
  const VideoIcon = (props: any) => <Icon as={VideoCallIcon} {...props} />;
  const LocationIcon = (props: any) => <Icon as={PlaceIcon} {...props} />;
  const TableIcon = (props: any) => <Icon as={ViewListIcon} {...props} />;
  const SlidesIcon = (props: any) => <Icon as={DesktopIcon} {...props} />;
  const ImageIcon = (props: any) => <Icon as={ImageIcon} {...props} />;
  const VideoCallIcon = (props: any) => <Icon as={VideoIcon} {...props} />;
  const AttachmentIcon = (props: any) => <Icon as={PaperclipIcon} {...props} />;
  const PlaceIcon = (props: any) => <Icon as={LocationIcon} {...props} />;

  if (!health?.connected) {
    return (
      <Box p={6}>
        <Alert status="warning">
          <AlertIcon />
          <AlertTitle>Google Not Connected</AlertTitle>
          <AlertDescription>
            Please connect your Google account to access Gmail, Calendar, Drive, and other services.
          </AlertDescription>
        </Alert>
        <Button
          mt={4}
          colorScheme="blue"
          onClick={startGoogleOAuth}
        >
          Connect Google Account
        </Button>
      </Box>
    );
  }

  return (
    <Box p={6}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <Box>
          <Heading size="lg" mb={2}>Google Integration</Heading>
          <Text color="gray.600">Manage Gmail, Calendar, Drive, and Google Workspace services</Text>
        </Box>

        {/* Search and Actions */}
        <HStack spacing={4}>
          <Input
            placeholder="Search Gmail, Calendar, Drive, Docs..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && searchGoogleSuite()}
            flex={1}
          />
          <Button
            leftIcon={<SearchIcon />}
            colorScheme="blue"
            onClick={searchGoogleSuite}
            isLoading={loading}
          >
            Search
          </Button>
          
          <Button
            leftIcon={<EmailIcon />}
            colorScheme="green"
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
            colorScheme="orange"
            onClick={() => setCreateDocModalOpen(true)}
          >
            New Doc
          </Button>
          
          <Button
            leftIcon={<UploadIcon />}
            colorScheme="teal"
            onClick={() => setUploadModalOpen(true)}
          >
            Upload
          </Button>
        </HStack>

        {/* Main Content Tabs */}
        <Tabs index={activeTab} onChange={setActiveTab}>
          <TabList>
            <Tab>
              <HStack>
                <Icon as={EmailIcon} />
                <Text>Gmail ({messages.length})</Text>
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
                <Text>Drive ({files.length})</Text>
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
            {/* Gmail Tab */}
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

            {/* Drive Tab */}
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
                    colorScheme="orange"
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

            {/* Profile Tab */}
            <TabPanel>
              <Card>
                <CardBody p={6}>
                  <VStack spacing={4} align="center">
                    <Avatar
                      name={currentUser?.name}
                      src={currentUser?.picture}
                      size="2xl"
                    />
                    <VStack align="center" spacing={2}>
                      <Heading size="lg">{currentUser?.name}</Heading>
                      <Text color="gray.600">{currentUser?.email}</Text>
                      {currentUser?.verified_email && (
                        <Badge colorScheme="green">Verified</Badge>
                      )}
                      {currentUser?.hd && (
                        <Text fontSize="sm" color="gray.500">
                          Organization: {currentUser.hd}
                        </Text>
                      )}
                    </VStack>
                    
                    <Divider />
                    
                    <VStack align="start" spacing={2} w="full">
                      <HStack justify="space-between" w="full">
                        <Text>Services</Text>
                        <HStack>
                          <Badge colorScheme="blue">Gmail</Badge>
                          <Badge colorScheme="purple">Calendar</Badge>
                          <Badge colorScheme="green">Drive</Badge>
                          <Badge colorScheme="orange">Docs</Badge>
                        </HStack>
                      </HStack>
                      
                      <HStack justify="space-between" w="full">
                        <Text>Storage Used</Text>
                        <Text>15 GB of 15 GB</Text>
                      </HStack>
                      
                      <Button
                        colorScheme="blue"
                        onClick={() => window.open('https://myaccount.google.com', '_blank')}
                      >
                        Manage Google Account
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
            <ModalHeader>Compose Email</ModalHeader>
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
                    placeholder="Event location or virtual meeting link"
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
            <ModalHeader>Create Document</ModalHeader>
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
                colorScheme="orange"
                onClick={createDocument}
                isLoading={loading}
              >
                Create Document
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Upload File Modal */}
        <Modal isOpen={uploadModalOpen} onClose={() => setUploadModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Upload File</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4} align="center">
                <Box
                  w="full"
                  h="200"
                  border="2px dashed"
                  borderColor="gray.300"
                  borderRadius="md"
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                  _hover={{ borderColor: 'blue.500' }}
                  cursor="pointer"
                >
                  <VStack spacing={2}>
                    <Icon as={UploadIcon} fontSize="3xl" color="gray.400" />
                    <Text color="gray.600">Click to browse or drag and drop</Text>
                    <Text fontSize="sm" color="gray.500">
                      Maximum file size: 100MB
                    </Text>
                  </VStack>
                </Box>
                
                <Button
                  leftIcon={<UploadIcon />}
                  colorScheme="teal"
                  w="full"
                >
                  Select Files
                </Button>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                onClick={() => setUploadModalOpen(false)}
              >
                Cancel
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default GoogleIntegrationManager;