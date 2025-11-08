/**
 * Microsoft 365 Unified Integration
 * Complete Microsoft 365 platform integration with unified authentication,
 * cross-service workflows, and enterprise management capabilities
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Box, Container, Heading, Text, VStack, HStack, SimpleGrid,
  Card, CardBody, CardHeader, Divider, Button, ButtonGroup,
  Tab, TabList, TabPanels, TabPanel, Tabs, Badge, Alert,
  AlertIcon, AlertTitle, AlertDescription, Progress, Stat,
  StatLabel, StatNumber, StatHelpText, Icon, Select, Input,
  Table, Thead, Tbody, Tr, Th, Td, TableContainer,
  Modal, ModalOverlay, ModalContent, ModalHeader, ModalFooter,
  ModalBody, ModalCloseButton, useDisclosure, FormControl,
  FormLabel, FormErrorMessage, Textarea, Checkbox, Switch,
  Spinner, Center, useToast, Accordion, AccordionItem,
  AccordionButton, AccordionPanel, AccordionIcon, Flex,
  Grid, GridItem, Link, Menu, MenuButton, MenuList,
  MenuItem, IconButton, Tag, TagLabel, TagCloseButton
} from '@chakra-ui/react';
import {
  FiUsers, FiMessageSquare, FiCalendar, FiFile, FiActivity,
  FiSettings, FiGlobe, FiCloud, FiZap, FiServer,
  FiDatabase, FiLock, FiPieChart, FiTrendingUp, FiRefreshCw,
  FiPlus, FiEdit2, FiTrash2, FiSearch, FiFilter, FiDownload,
  FiUpload, FiClock, FiCheckCircle, FiAlertCircle, FiXCircle,
  FiMic, FiVideo, FiMail, FiShare2, FiShield, FiKey,
  FiBarChart, FiGrid, FiCpu, FiBox, FiFolder, FiFolderOpen
} from 'react-icons/fi';
import { toast } from 'react-hot-toast';

// Types
export interface Microsoft365User {
  id: string;
  displayName: string;
  mail: string | null;
  userPrincipalName: string;
  jobTitle: string | null;
  department: string | null;
  officeLocation: string | null;
  companyName: string | null;
  lastSignInDateTime: string | null;
  usageLocation: string | null;
  accountEnabled: boolean;
  userType: string;
}

export interface Microsoft365Team {
  id: string;
  displayName: string;
  description: string | null;
  visibility: 'public' | 'private';
  mailNickname: string | null;
  createdDateTime: string;
  teamType: string;
  isArchived: boolean;
  memberCount: number;
  channelCount: number;
  ownerId: string;
  tags: string[];
}

export interface Microsoft365Channel {
  id: string;
  displayName: string;
  description: string | null;
  teamId: string;
  isFavoriteByDefault: boolean;
  email: string | null;
  membershipType: 'standard' | 'private' | 'shared';
  createdDateTime: string;
  webUrl: string;
  messageCount: number;
  moderatorCount: number;
}

export interface Microsoft365Message {
  id: string;
  subject: string | null;
  body: string;
  fromAddress: string;
  toAddresses: string[];
  ccAddresses: string[];
  bccAddresses: string[];
  timestamp: string;
  attachments: any[];
  messageType: 'email' | 'chat' | 'channel_message';
  conversationId: string | null;
  channelId: string | null;
  teamId: string | null;
  importance: 'low' | 'normal' | 'high';
  isRead: boolean;
  isDraft: boolean;
}

export interface Microsoft365Document {
  id: string;
  name: string;
  fileType: string;
  sizeBytes: number;
  modifiedDate: string;
  createdDate: string;
  filePath: string;
  shareLink: string | null;
  ownerId: string;
  parentFolderId: string | null;
  documentType: 'onedrive' | 'sharepoint' | 'teams_file';
  collaborationLink: string | null;
  versionCount: number;
  tags: string[];
  metadata: Record<string, any>;
  isShared: boolean;
}

export interface Microsoft365Event {
  id: string;
  subject: string;
  startTime: string;
  endTime: string;
  attendees: string[];
  organizer: string;
  description: string | null;
  location: string | null;
  eventType: 'meeting' | 'appointment' | 'all_day_event';
  teamsMeetingUrl: string | null;
  recordingUrl: string | null;
  meetingId: string | null;
  isOnline: boolean;
  status: 'scheduled' | 'started' | 'ended' | 'cancelled';
  isAllDay: boolean;
}

export interface Microsoft365Flow {
  id: string;
  displayName: string;
  description: string | null;
  flowType: 'automated' | 'instant' | 'scheduled';
  status: 'enabled' | 'disabled' | 'failed';
  createdDateTime: string;
  lastExecutionTime: string | null;
  executionCount: number;
  triggerType: string;
  connectorCount: number;
  environmentName: string;
  errorCount: number;
  successRate: number;
}

export interface Microsoft365Site {
  id: string;
  displayName: string;
  description: string | null;
  webUrl: string;
  siteType: 'team_site' | 'communication_site' | 'group_site';
  createdDateTime: string;
  lastModifiedDateTime: string;
  storageQuotaBytes: number;
  storageUsedBytes: number;
  ownerId: string;
  memberCount: number;
  permissionLevel: 'read' | 'write' | 'admin';
  isHubSite: boolean;
  hubSiteId: string | null;
  status: string;
}

export interface Microsoft365Analytics {
  teams: {
    totalTeams: number;
    activeTeams: number;
    totalChannels: number;
    totalMembers: number;
  };
  outlook: {
    emailsProcessed: number;
    calendarEvents: number;
    activeConversations: number;
  };
  onedrive: {
    documentsAccessed: number;
    storageUsed: number;
    filesShared: number;
  };
  powerAutomate: {
    flowsConfigured: number;
    activeFlows: number;
    successRate: number;
    totalExecutions: number;
  };
  sharepoint: {
    totalSites: number;
    documentsViewed: number;
    collaborationActivities: number;
  };
}

export interface Microsoft365Config {
  tenantId: string;
  clientId: string;
  clientSecret: string;
  redirectUri: string;
  scopes: string[];
}

// Main Component Interface
export interface Microsoft365ManagerProps {
  config?: Partial<Microsoft365Config>;
  onError?: (error: Error) => void;
  onSuccess?: (message: string) => void;
  theme?: 'light' | 'dark';
  compact?: boolean;
}

// Main Component
export const Microsoft365Manager: React.FC<Microsoft365ManagerProps> = ({
  config,
  onError,
  onSuccess,
  theme = 'light',
  compact = false
}) => {
  // State Management
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeService, setActiveService] = useState<string>('all');
  
  // Data State
  const [users, setUsers] = useState<Microsoft365User[]>([]);
  const [teams, setTeams] = useState<Microsoft365Team[]>([]);
  const [channels, setChannels] = useState<Microsoft365Channel[]>([]);
  const [messages, setMessages] = useState<Microsoft365Message[]>([]);
  const [documents, setDocuments] = useState<Microsoft365Document[]>([]);
  const [events, setEvents] = useState<Microsoft365Event[]>([]);
  const [flows, setFlows] = useState<Microsoft365Flow[]>([]);
  const [sites, setSites] = useState<Microsoft365Site[]>([]);
  const [analytics, setAnalytics] = useState<Microsoft365Analytics | null>(null);
  
  // Modal State
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [modalMode, setModalMode] = useState<'create' | 'edit' | 'view'>('view');
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [configModalOpen, setConfigModalOpen] = useState(false);
  
  // Form State
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [configData, setConfigData] = useState<Microsoft365Config>({
    tenantId: config?.tenantId || '',
    clientId: config?.clientId || '',
    clientSecret: config?.clientSecret || '',
    redirectUri: config?.redirectUri || '',
    scopes: config?.scopes || ['User.Read', 'Mail.Read', 'Files.Read', 'Team.ReadBasic.All']
  });
  
  // Toast
  const toast = useToast();

  // API Base URL
  const API_BASE_URL = '/api/m365';

  // Initialize Component
  useEffect(() => {
    checkConnection();
  }, []);

  // Check Connection Status
  const checkConnection = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/auth/status`);
      const data = await response.json();
      setIsConnected(data.authenticated);
    } catch (error) {
      setIsConnected(false);
    }
  }, []);

  // Connect to Microsoft 365
  const handleConnect = useCallback(async () => {
    setIsConnecting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/integration/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: configData })
      });
      const data = await response.json();
      
      if (data.success) {
        setIsConnected(true);
        setConfigModalOpen(false);
        onSuccess?.('Microsoft 365 connected successfully');
        toast({
          title: 'Connection Successful',
          description: 'Microsoft 365 has been connected successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error(data.error || 'Connection failed');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Connection Failed',
        description: error.message || 'Failed to connect to Microsoft 365',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsConnecting(false);
    }
  }, [configData, onError, onSuccess, toast]);

  // Load Dashboard Data
  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [teamsData, messagesData, documentsData, eventsData, flowsData, sitesData, analyticsData] = await Promise.all([
        fetch(`${API_BASE_URL}/teams`).then(r => r.json().then(d => d.success ? d.teams : [])),
        fetch(`${API_BASE_URL}/emails?limit=50`).then(r => r.json().then(d => d.success ? d.emails : [])),
        fetch(`${API_BASE_URL}/documents?limit=50`).then(r => r.json().then(d => d.success ? d.documents : [])),
        fetch(`${API_BASE_URL}/calendar/events?limit=50`).then(r => r.json().then(d => d.success ? d.events : [])),
        fetch(`${API_BASE_URL}/power-automate/flows`).then(r => r.json().then(d => d.success ? d.flows : [])),
        fetch(`${API_BASE_URL}/sharepoint/sites`).then(r => r.json().then(d => d.success ? d.sites : [])),
        fetch(`${API_BASE_URL}/analytics/unified`).then(r => r.json().then(d => d.success ? d.analytics : null))
      ]);
      
      setTeams(teamsData);
      setMessages(messagesData);
      setDocuments(documentsData);
      setEvents(eventsData);
      setFlows(flowsData);
      setSites(sitesData);
      setAnalytics(analyticsData);
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  // Load Teams Data
  const loadTeamsData = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/teams`);
      const data = await response.json();
      if (data.success) {
        setTeams(data.teams);
        
        // Load channels for each team
        const teamsWithChannels = await Promise.all(
          data.teams.map(async (team: Microsoft365Team) => {
            const channelsResponse = await fetch(`${API_BASE_URL}/teams/${team.id}/channels`);
            const channelsData = await channelsResponse.json();
            return { ...team, channels: channelsData.success ? channelsData.channels : [] };
          })
        );
        
        setTeams(teamsWithChannels);
      }
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  // Send Teams Message
  const sendTeamsMessage = useCallback(async (teamId: string, channelId: string, message: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/teams/${teamId}/channels/${channelId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message })
      });
      const data = await response.json();
      
      if (data.success) {
        onSuccess?.('Message sent successfully');
        toast({
          title: 'Message Sent',
          description: 'Message sent to Teams channel successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error(data.error || 'Failed to send message');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Send Failed',
        description: error.message || 'Failed to send message',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [onError, onSuccess, toast]);

  // Send Email
  const sendEmail = useCallback(async (toAddresses: string[], subject: string, body: string, ccAddresses?: string[]) => {
    try {
      const response = await fetch(`${API_BASE_URL}/emails/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_addresses: toAddresses,
          subject,
          body,
          cc_addresses: ccAddresses
        })
      });
      const data = await response.json();
      
      if (data.success) {
        onSuccess?.('Email sent successfully');
        toast({
          title: 'Email Sent',
          description: 'Email sent successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error(data.error || 'Failed to send email');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Send Failed',
        description: error.message || 'Failed to send email',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [onError, onSuccess, toast]);

  // Create Calendar Event
  const createCalendarEvent = useCallback(async (event: Partial<Microsoft365Event>) => {
    try {
      const response = await fetch(`${API_BASE_URL}/calendar/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(event)
      });
      const data = await response.json();
      
      if (data.success) {
        onSuccess?.('Event created successfully');
        toast({
          title: 'Event Created',
          description: 'Calendar event created successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        
        // Reload events
        loadCalendarEvents();
      } else {
        throw new Error(data.error || 'Failed to create event');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Create Failed',
        description: error.message || 'Failed to create event',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [onError, onSuccess, toast]);

  // Load Calendar Events
  const loadCalendarEvents = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/calendar/events?limit=100`);
      const data = await response.json();
      if (data.success) {
        setEvents(data.events);
      }
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  // Format File Size
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // Format Date
  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  // Format DateTime
  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  // Get Service Icon
  const getServiceIcon = (service: string) => {
    const icons: Record<string, any> = {
      teams: FiMessageSquare,
      outlook: FiMail,
      onedrive: FiFolder,
      sharepoint: FiServer,
      calendar: FiCalendar,
      power_automate: FiZap,
      power_bi: FiPieChart,
      users: FiUsers,
      analytics: FiBarChart,
      documents: FiFile,
      workflows: FiCpu
    };
    return icons[service] || FiGlobe;
  };

  // Render Connection Status
  const renderConnectionStatus = () => (
    <Alert status={isConnected ? 'success' : 'warning'} mb={4}>
      <AlertIcon as={isConnected ? FiCheckCircle : FiAlertCircle} />
      <Box flex="1">
        <AlertTitle>{isConnected ? 'Connected' : 'Not Connected'}</AlertTitle>
        <AlertDescription>
          {isConnected 
            ? 'Microsoft 365 is connected and ready for use'
            : 'Connect to Microsoft 365 to access all services'
          }
        </AlertDescription>
      </Box>
      {!isConnected && (
        <Button 
          colorScheme="blue" 
          size="sm" 
          onClick={() => setConfigModalOpen(true)}
          isLoading={isConnecting}
        >
          Connect
        </Button>
      )}
      {isConnected && (
        <Button colorScheme="red" size="sm" onClick={() => setIsConnected(false)}>
          Disconnect
        </Button>
      )}
    </Alert>
  );

  // Render Dashboard
  const renderDashboard = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      {/* Service Overview */}
      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiMessageSquare} color="blue.500" boxSize={8} />
              <Stat>
                <StatLabel>Teams</StatLabel>
                <StatNumber>{teams.length}</StatNumber>
                <StatHelpText>{teams.filter(t => !t.isArchived).length} active</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiMail} color="green.500" boxSize={8} />
              <Stat>
                <StatLabel>Messages</StatLabel>
                <StatNumber>{messages.length}</StatNumber>
                <StatHelpText>Recent activity</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiFile} color="orange.500" boxSize={8} />
              <Stat>
                <StatLabel>Documents</StatLabel>
                <StatNumber>{documents.length}</StatNumber>
                <StatHelpText>Across services</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiCalendar} color="purple.500" boxSize={8} />
              <Stat>
                <StatLabel>Events</StatLabel>
                <StatNumber>{events.length}</StatNumber>
                <StatHelpText>Scheduled meetings</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
      </SimpleGrid>

      {/* Analytics */}
      {analytics && (
        <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
          <Card>
            <CardHeader>
              <Heading size="md">Team Analytics</Heading>
            </CardHeader>
            <CardBody>
              <VStack align="stretch" spacing={3}>
                <HStack justify="space-between">
                  <Text>Total Teams</Text>
                  <Badge>{analytics.teams.totalTeams}</Badge>
                </HStack>
                <HStack justify="space-between">
                  <Text>Active Teams</Text>
                  <Badge colorScheme="green">{analytics.teams.activeTeams}</Badge>
                </HStack>
                <HStack justify="space-between">
                  <Text>Total Channels</Text>
                  <Badge>{analytics.teams.totalChannels}</Badge>
                </HStack>
                <HStack justify="space-between">
                  <Text>Total Members</Text>
                  <Badge>{analytics.teams.totalMembers}</Badge>
                </HStack>
              </VStack>
            </CardBody>
          </Card>
          
          <Card>
            <CardHeader>
              <Heading size="md">Document Analytics</Heading>
            </CardHeader>
            <CardBody>
              <VStack align="stretch" spacing={3}>
                <HStack justify="space-between">
                  <Text>Documents Accessed</Text>
                  <Badge>{analytics.onedrive.documentsAccessed}</Badge>
                </HStack>
                <HStack justify="space-between">
                  <Text>Storage Used</Text>
                  <Badge>{formatFileSize(analytics.onedrive.storageUsed)}</Badge>
                </HStack>
                <HStack justify="space-between">
                  <Text>Files Shared</Text>
                  <Badge colorScheme="blue">{analytics.onedrive.filesShared}</Badge>
                </HStack>
                <Progress 
                  value={(analytics.onedrive.storageUsed / (1024 * 1024 * 1024 * 100)) * 100} 
                  size="sm"
                  colorScheme="blue"
                  mt={2}
                />
              </VStack>
            </CardBody>
          </Card>
        </SimpleGrid>
      )}

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <Heading size="md">Quick Actions</Heading>
        </CardHeader>
        <CardBody>
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
            <Button 
              leftIcon={<FiMessageSquare />}
              colorScheme="blue"
              onClick={() => setActiveTab('teams')}
            >
              Manage Teams
            </Button>
            <Button 
              leftIcon={<FiMail />}
              colorScheme="green"
              onClick={() => setActiveTab('outlook')}
            >
              Send Email
            </Button>
            <Button 
              leftIcon={<FiCalendar />}
              colorScheme="purple"
              onClick={() => setActiveTab('calendar')}
            >
              Schedule Meeting
            </Button>
            <Button 
              leftIcon={<FiFile />}
              colorScheme="orange"
              onClick={() => setActiveTab('documents')}
            >
              Upload File
            </Button>
          </SimpleGrid>
        </CardBody>
      </Card>
    </VStack>
  );

  // Render Teams Management
  const renderTeams = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Teams Management</Heading>
        <Button leftIcon={<FiRefreshCw />} onClick={loadTeamsData} isLoading={isLoading}>
          Refresh
        </Button>
      </Flex>
      
      {teams.length > 0 && (
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Name</Th>
                <Th>Description</Th>
                <Th>Visibility</Th>
                <Th>Members</Th>
                <Th>Channels</Th>
                <Th>Status</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {teams.map((team) => (
                <Tr key={team.id}>
                  <Td>
                    <HStack>
                      <Icon as={FiMessageSquare} color="blue.500" />
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium">{team.displayName}</Text>
                        <Text fontSize="sm" color="gray.500">{team.mailNickname}</Text>
                      </VStack>
                    </HStack>
                  </Td>
                  <Td>
                    <Text noOfLines={2}>{team.description || 'No description'}</Text>
                  </Td>
                  <Td>
                    <Badge colorScheme={team.visibility === 'public' ? 'green' : 'orange'}>
                      {team.visibility}
                    </Badge>
                  </Td>
                  <Td>
                    <HStack>
                      <Icon as={FiUsers} />
                      <Text>{team.memberCount}</Text>
                    </HStack>
                  </Td>
                  <Td>
                    <HStack>
                      <Icon as={FiGrid} />
                      <Text>{team.channelCount}</Text>
                    </HStack>
                  </Td>
                  <Td>
                    <Badge colorScheme={team.isArchived ? 'red' : 'green'}>
                      {team.isArchived ? 'Archived' : 'Active'}
                    </Badge>
                  </Td>
                  <Td>
                    <HStack spacing={2}>
                      <IconButton 
                        icon={<FiEdit2 />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(team);
                          setModalMode('view');
                          onOpen();
                        }}
                      />
                      <IconButton 
                        icon={<FiPlus />} 
                        size="sm" 
                        variant="ghost"
                        colorScheme="blue"
                        onClick={() => {
                          setSelectedItem(team);
                          setFormData({ message: '', channelId: '' });
                          setModalMode('create');
                          onOpen();
                        }}
                      />
                    </HStack>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
      )}
      
      {isLoading && (
        <Center py={8}>
          <VStack>
            <Spinner size="xl" />
            <Text>Loading teams...</Text>
          </VStack>
        </Center>
      )}
      
      {!isLoading && teams.length === 0 && (
        <Alert status="info">
          <AlertIcon as={FiAlertCircle} />
          <AlertTitle>No Teams Found</AlertTitle>
          <AlertDescription>No Microsoft Teams found. Create your first team to get started.</AlertDescription>
        </Alert>
      )}
    </VStack>
  );

  // Render Outlook Management
  const renderOutlook = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Outlook Management</Heading>
        <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
          Refresh
        </Button>
      </Flex>
      
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        {/* Recent Messages */}
        <Card>
          <CardHeader>
            <HStack>
              <Icon as={FiMail} color="green.500" />
              <Heading size="md">Recent Messages</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={3}>
              {messages.slice(0, 5).map((message) => (
                <Box key={message.id} p={3} borderWidth="1px" borderRadius="md">
                  <VStack align="start" spacing={1}>
                    <HStack justify="space-between" width="100%">
                      <Text fontWeight="medium" noOfLines={1}>{message.subject || 'No Subject'}</Text>
                      <Badge colorScheme={message.isRead ? 'gray' : 'green'}>
                        {message.isRead ? 'Read' : 'Unread'}
                      </Badge>
                    </HStack>
                    <Text fontSize="sm" color="gray.600">
                      From: {message.fromAddress}
                    </Text>
                    <Text fontSize="sm" color="gray.500">
                      {formatDateTime(message.timestamp)}
                    </Text>
                  </VStack>
                </Box>
              ))}
            </VStack>
          </CardBody>
        </Card>
        
        {/* Quick Email Compose */}
        <Card>
          <CardHeader>
            <HStack>
              <Icon as={FiMail} color="blue.500" />
              <Heading size="md">Compose Email</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>To</FormLabel>
                <Input 
                  placeholder="recipient@example.com"
                  value={formData.toAddresses || ''}
                  onChange={(e) => setFormData({ ...formData, toAddresses: e.target.value.split(',') })}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Subject</FormLabel>
                <Input 
                  placeholder="Email subject"
                  value={formData.subject || ''}
                  onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Message</FormLabel>
                <Textarea 
                  placeholder="Type your message here..."
                  rows={6}
                  value={formData.body || ''}
                  onChange={(e) => setFormData({ ...formData, body: e.target.value })}
                />
              </FormControl>
              
              <Button 
                colorScheme="blue" 
                leftIcon={<FiMail />}
                onClick={() => {
                  if (formData.toAddresses && formData.subject && formData.body) {
                    sendEmail(
                      formData.toAddresses,
                      formData.subject,
                      formData.body
                    );
                  }
                }}
                isDisabled={!formData.toAddresses || !formData.subject || !formData.body}
              >
                Send Email
              </Button>
            </VStack>
          </CardBody>
        </Card>
      </SimpleGrid>
    </VStack>
  );

  // Render Calendar Management
  const renderCalendar = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Calendar Management</Heading>
        <Button leftIcon={<FiRefreshCw />} onClick={loadCalendarEvents} isLoading={isLoading}>
          Refresh
        </Button>
      </Flex>
      
      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        {/* Upcoming Events */}
        <Card>
          <CardHeader>
            <HStack>
              <Icon as={FiCalendar} color="purple.500" />
              <Heading size="md">Upcoming Events</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={3}>
              {events.slice(0, 5).map((event) => (
                <Box key={event.id} p={3} borderWidth="1px" borderRadius="md">
                  <VStack align="start" spacing={1}>
                    <HStack justify="space-between" width="100%">
                      <Text fontWeight="medium" noOfLines={1}>{event.subject}</Text>
                      <Badge colorScheme={event.status === 'scheduled' ? 'blue' : 'green'}>
                        {event.status}
                      </Badge>
                    </HStack>
                    <Text fontSize="sm" color="gray.600">
                      {formatDateTime(event.startTime)} - {formatDateTime(event.endTime)}
                    </Text>
                    <Text fontSize="sm" color="gray.500">
                      Organizer: {event.organizer}
                    </Text>
                    {event.location && (
                      <Text fontSize="sm" color="gray.500">
                        Location: {event.location}
                      </Text>
                    )}
                  </VStack>
                </Box>
              ))}
            </VStack>
          </CardBody>
        </Card>
        
        {/* Create Event */}
        <Card>
          <CardHeader>
            <HStack>
              <Icon as={FiPlus} color="blue.500" />
              <Heading size="md">Create Event</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Subject</FormLabel>
                <Input 
                  placeholder="Event subject"
                  value={formData.subject || ''}
                  onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Start Time</FormLabel>
                <Input 
                  type="datetime-local"
                  value={formData.start_time || ''}
                  onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>End Time</FormLabel>
                <Input 
                  type="datetime-local"
                  value={formData.end_time || ''}
                  onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Attendees</FormLabel>
                <Textarea 
                  placeholder=" attendee1@example.com, attendee2@example.com"
                  rows={3}
                  value={formData.attendees || ''}
                  onChange={(e) => setFormData({ ...formData, attendees: e.target.value.split(',').map(s => s.trim()) })}
                />
              </FormControl>
              
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea 
                  placeholder="Event description"
                  rows={4}
                  value={formData.description || ''}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </FormControl>
              
              <Button 
                colorScheme="blue" 
                leftIcon={<FiCalendar />}
                onClick={() => {
                  if (formData.subject && formData.start_time && formData.end_time) {
                    createCalendarEvent({
                      subject: formData.subject,
                      start_time: formData.start_time,
                      end_time: formData.end_time,
                      attendees: formData.attendees || [],
                      description: formData.description,
                      organizer: 'me',
                      event_type: 'meeting',
                      is_online: true,
                      status: 'scheduled'
                    });
                  }
                }}
                isDisabled={!formData.subject || !formData.start_time || !formData.end_time}
              >
                Create Event
              </Button>
            </VStack>
          </CardBody>
        </Card>
      </SimpleGrid>
    </VStack>
  );

  // Render Documents Management
  const renderDocuments = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Documents Management</Heading>
        <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
          Refresh
        </Button>
      </Flex>
      
      <SimpleGrid columns={{ base: 1, lg: 3 }} spacing={6}>
        {/* Recent Documents */}
        <Card>
          <CardHeader>
            <HStack>
              <Icon as={FiFile} color="orange.500" />
              <Heading size="md">Recent Documents</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack align="stretch" spacing={3}>
              {documents.slice(0, 5).map((doc) => (
                <Box key={doc.id} p={3} borderWidth="1px" borderRadius="md">
                  <HStack justify="space-between">
                    <VStack align="start" spacing={1}>
                      <Text fontWeight="medium" noOfLines={1}>{doc.name}</Text>
                      <Text fontSize="sm" color="gray.600">
                        {formatFileSize(doc.sizeBytes)}
                      </Text>
                      <Text fontSize="sm" color="gray.500">
                        {formatDate(doc.modifiedDate)}
                      </Text>
                    </VStack>
                    <Icon as={doc.isShared ? FiShare2 : FiFolder} color="blue.500" />
                  </HStack>
                </Box>
              ))}
            </VStack>
          </CardBody>
        </Card>
        
        {/* Upload Document */}
        <Card>
          <CardHeader>
            <HStack>
              <Icon as={FiUpload} color="blue.500" />
              <Heading size="md">Upload Document</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Service</FormLabel>
                <Select 
                  value={formData.document_type || 'onedrive'}
                  onChange={(e) => setFormData({ ...formData, document_type: e.target.value })}
                >
                  <option value="onedrive">OneDrive</option>
                  <option value="sharepoint">SharePoint</option>
                  <option value="teams">Teams</option>
                </Select>
              </FormControl>
              
              <FormControl>
                <FormLabel>File Path</FormLabel>
                <Input 
                  placeholder="/folder/filename.ext"
                  value={formData.file_path || ''}
                  onChange={(e) => setFormData({ ...formData, file_path: e.target.value })}
                />
              </FormControl>
              
              <Input 
                type="file"
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setFormData({ ...formData, file: e.target.files[0] });
                  }
                }}
              />
              
              <Button 
                colorScheme="blue" 
                leftIcon={<FiUpload />}
                onClick={() => {
                  if (formData.file_path && formData.file) {
                    // Handle file upload
                    toast({
                      title: 'Upload Started',
                      description: 'Document upload initiated',
                      status: 'info',
                      duration: 3000,
                      isClosable: true,
                    });
                  }
                }}
                isDisabled={!formData.file_path || !formData.file}
              >
                Upload Document
              </Button>
            </VStack>
          </CardBody>
        </Card>
        
        {/* Storage Usage */}
        <Card>
          <CardHeader>
            <HStack>
              <Icon as={FiDatabase} color="green.500" />
              <Heading size="md">Storage Usage</Heading>
            </HStack>
          </CardHeader>
          <CardBody>
            <VStack spacing={4}>
              <HStack justify="space-between" width="100%">
                <Text>Total Documents</Text>
                <Badge>{documents.length}</Badge>
              </HStack>
              
              <HStack justify="space-between" width="100%">
                <Text>Shared Files</Text>
                <Badge colorScheme="blue">
                  {documents.filter(d => d.isShared).length}
                </Badge>
              </HStack>
              
              <VStack width="100%" spacing={2}>
                <HStack justify="space-between">
                  <Text fontSize="sm">Storage Used</Text>
                  <Text fontSize="sm">
                    {formatFileSize(documents.reduce((sum, doc) => sum + doc.sizeBytes, 0))}
                  </Text>
                </HStack>
                <Progress 
                  value={(documents.reduce((sum, doc) => sum + doc.sizeBytes, 0) / (100 * 1024 * 1024 * 1024)) * 100} 
                  size="sm"
                  colorScheme="blue"
                />
              </VStack>
            </VStack>
          </CardBody>
        </Card>
      </SimpleGrid>
    </VStack>
  );

  // Render Settings
  const renderSettings = () => (
    <VStack spacing={6} align="stretch">
      <Card>
        <CardHeader>
          <Heading size="lg">Microsoft 365 Settings</Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={6}>
            <Alert status="info">
              <AlertIcon as={FiInfo} />
              <Box>
                <AlertTitle>Configuration Status</AlertTitle>
                <AlertDescription>
                  {isConnected 
                    ? 'Microsoft 365 is properly configured and connected'
                    : 'Configure Microsoft 365 settings to enable all services'
                  }
                </AlertDescription>
              </Box>
            </Alert>
            
            <FormControl>
              <FormLabel>Tenant ID</FormLabel>
              <Input 
                value={configData.tenantId}
                onChange={(e) => setConfigData({ ...configData, tenantId: e.target.value })}
                isDisabled={isConnected}
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Client ID</FormLabel>
              <Input 
                value={configData.clientId}
                onChange={(e) => setConfigData({ ...configData, clientId: e.target.value })}
                isDisabled={isConnected}
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Client Secret</FormLabel>
              <Input 
                type="password"
                value={configData.clientSecret}
                onChange={(e) => setConfigData({ ...configData, clientSecret: e.target.value })}
                isDisabled={isConnected}
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Redirect URI</FormLabel>
              <Input 
                value={configData.redirectUri}
                onChange={(e) => setConfigData({ ...configData, redirectUri: e.target.value })}
                isDisabled={isConnected}
              />
            </FormControl>
            
            <Button 
              colorScheme="blue" 
              leftIcon={<FiSettings />}
              onClick={() => setConfigModalOpen(true)}
              isDisabled={isConnected}
            >
              Configure Connection
            </Button>
          </VStack>
        </CardBody>
      </Card>
    </VStack>
  );

  // Render Modal Content
  const renderModalContent = () => {
    switch (modalMode) {
      case 'view':
        return (
          <VStack spacing={4}>
            {selectedItem && (
              <>
                <FormControl>
                  <FormLabel>Team Name</FormLabel>
                  <Input value={selectedItem.displayName} isDisabled />
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea 
                    value={selectedItem.description || ''}
                    isDisabled 
                    rows={3}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Visibility</FormLabel>
                  <Input value={selectedItem.visibility} isDisabled />
                </FormControl>
                <FormControl>
                  <FormLabel>Members</FormLabel>
                  <Input value={selectedItem.memberCount} isDisabled />
                </FormControl>
              </>
            )}
          </VStack>
        );
        
      case 'create':
        return (
          <VStack spacing={4}>
            <FormControl>
              <FormLabel>Message</FormLabel>
              <Textarea 
                placeholder="Type your message here..."
                value={formData.message || ''}
                onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                rows={4}
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Channel</FormLabel>
              <Select 
                value={formData.channelId || ''}
                onChange={(e) => setFormData({ ...formData, channelId: e.target.value })}
              >
                <option value="">Select a channel</option>
                {selectedItem?.channels?.map((channel: Microsoft365Channel) => (
                  <option key={channel.id} value={channel.id}>
                    {channel.displayName}
                  </option>
                ))}
              </Select>
            </FormControl>
          </VStack>
        );
        
      default:
        return null;
    }
  };

  // Load data when tab changes
  useEffect(() => {
    if (isConnected) {
      switch (activeTab) {
        case 'dashboard':
          loadDashboardData();
          break;
        case 'teams':
          loadTeamsData();
          break;
        case 'outlook':
          loadDashboardData(); // Load recent messages
          break;
        case 'calendar':
          loadCalendarEvents();
          break;
        case 'documents':
          loadDashboardData(); // Load recent documents
          break;
        default:
          break;
      }
    }
  }, [activeTab, isConnected]);

  return (
    <Container maxW="container.xl" py={8}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack>
            <Icon as={FiCloud} color="blue.500" boxSize={8} />
            <Heading size="xl">Microsoft 365</Heading>
          </HStack>
          <ButtonGroup>
            <Button leftIcon={<FiRefreshCw />} onClick={() => window.location.reload()}>
              Reload
            </Button>
          </ButtonGroup>
        </HStack>

        {/* Tabs */}
        <Tabs 
          index={['dashboard', 'teams', 'outlook', 'calendar', 'documents', 'settings'].indexOf(activeTab)}
          onChange={(index) => setActiveTab(['dashboard', 'teams', 'outlook', 'calendar', 'documents', 'settings'][index])}
          variant="enclosed"
          colorScheme="blue"
        >
          <TabList>
            <Tab>Dashboard</Tab>
            <Tab>Teams</Tab>
            <Tab>Outlook</Tab>
            <Tab>Calendar</Tab>
            <Tab>Documents</Tab>
            <Tab>Settings</Tab>
          </TabList>
          
          <TabPanels>
            <TabPanel>
              {renderDashboard()}
            </TabPanel>
            <TabPanel>
              {renderTeams()}
            </TabPanel>
            <TabPanel>
              {renderOutlook()}
            </TabPanel>
            <TabPanel>
              {renderCalendar()}
            </TabPanel>
            <TabPanel>
              {renderDocuments()}
            </TabPanel>
            <TabPanel>
              {renderSettings()}
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>

      {/* Configuration Modal */}
      <Modal isOpen={configModalOpen} onClose={() => setConfigModalOpen(false)} size="md">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Configure Microsoft 365</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <Alert status="info">
                <AlertIcon as={FiInfo} />
                <Box>
                  <AlertTitle>Configuration Required</AlertTitle>
                  <AlertDescription>
                    Enter your Microsoft 365 Azure AD application details to connect to the services.
                  </AlertDescription>
                </Box>
              </Alert>
              
              <FormControl isInvalid={!configData.tenantId}>
                <FormLabel>Tenant ID</FormLabel>
                <Input 
                  value={configData.tenantId}
                  onChange={(e) => setConfigData({ ...configData, tenantId: e.target.value })}
                  placeholder="your-tenant-id"
                />
                <FormErrorMessage>Tenant ID is required</FormErrorMessage>
              </FormControl>
              
              <FormControl isInvalid={!configData.clientId}>
                <FormLabel>Client ID</FormLabel>
                <Input 
                  value={configData.clientId}
                  onChange={(e) => setConfigData({ ...configData, clientId: e.target.value })}
                  placeholder="your-client-id"
                />
                <FormErrorMessage>Client ID is required</FormErrorMessage>
              </FormControl>
              
              <FormControl isInvalid={!configData.clientSecret}>
                <FormLabel>Client Secret</FormLabel>
                <Input 
                  type="password"
                  value={configData.clientSecret}
                  onChange={(e) => setConfigData({ ...configData, clientSecret: e.target.value })}
                  placeholder="your-client-secret"
                />
                <FormErrorMessage>Client Secret is required</FormErrorMessage>
              </FormControl>
              
              <FormControl>
                <FormLabel>Redirect URI</FormLabel>
                <Input 
                  value={configData.redirectUri}
                  onChange={(e) => setConfigData({ ...configData, redirectUri: e.target.value })}
                  placeholder="http://localhost:3000/oauth/m365/callback"
                />
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={() => setConfigModalOpen(false)}>
              Cancel
            </Button>
            <Button 
              colorScheme="blue" 
              onClick={handleConnect}
              isLoading={isConnecting}
              isDisabled={!configData.tenantId || !configData.clientId || !configData.clientSecret}
            >
              Connect
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Item Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {modalMode === 'view' ? 'View Details' : 
             modalMode === 'create' ? 'Send Message' : 'Edit Item'}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {renderModalContent()}
          </ModalBody>
          {modalMode === 'create' && (
            <ModalFooter>
              <Button variant="ghost" onClick={onClose}>
                Cancel
              </Button>
              <Button 
                colorScheme="blue" 
                onClick={() => {
                  if (selectedItem && formData.message && formData.channelId) {
                    sendTeamsMessage(
                      selectedItem.id,
                      formData.channelId,
                      formData.message
                    );
                    onClose();
                  }
                }}
                isDisabled={!formData.message || !formData.channelId}
              >
                Send Message
              </Button>
            </ModalFooter>
          )}
        </ModalContent>
      </Modal>
    </Container>
  );
};

export default Microsoft365Manager;