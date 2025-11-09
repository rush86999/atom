/**
 * Monday.com Integration
 * Complete Work OS platform integration with boards, items, columns, groups, workflows, and team collaboration
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
  MenuItem, IconButton, Tag, TagLabel, TagCloseButton,
  List, ListItem, OrderedList, UnorderedList, Code,
  Tooltip, InputGroup, InputLeftElement, InputRightElement,
  NumberInput, NumberInputField, Stack, Wrap, WrapItem,
  Avatar, AvatarBadge, AvatarGroup, useColorModeValue
} from '@chakra-ui/react';
import {
  FiGrid, FiList, FiCalendar, FiUsers, FiActivity,
  FiSettings, FiFolder, FiZap, FiServer, FiDatabase,
  FiClock, FiPlus, FiEdit2, FiTrash2, FiSearch, FiFilter,
  FiDownload, FiUpload, FiRefreshCw, FiCheckCircle, FiAlertCircle,
  FiXCircle, FiEye, FiEyeOff, FiLock, FiUnlock, FiTag,
  FiBell, FiShare2, FiLink, FiGitBranch, FiPieChart,
  FiBarChart, FiTrendingUp, FiCpu, FiBox, FiPackage,
  FiTarget, FiFlag, FiBook, FiBookmark, FiStar, FiHeart,
  FiMessageSquare, FiMail, FiVideo, FiPhone, FiMap,
  FiMapPin, FiNavigation, FiGlobe, FiLayers, FiColumns,
  FiRows, FiMaximize, FiMinimize, FiExpand, FiShrink,
  FiCopy, FiMove, FiCornerUpLeft, FiCornerUpRight,
  FiCornerDownLeft, FiCornerDownRight, FiChevronLeft,
  FiChevronRight, FiChevronUp, FiChevronDown,
  FiMoreVertical, FiMoreHorizontal, FiMenu, FiSidebar,
  FiHome, FiBoard, FiBriefcase, FiAward, FiTrendingDown
} from 'react-icons/fi';
import { toast } from 'react-hot-toast';

// Types
export interface MondayUser {
  id: string;
  name: string;
  email: string;
  photoUrl: string;
  title: string;
  phone: string;
  country: string;
  timezone: string;
  location: string;
  joinDate: string;
  lastLogin: string;
  teamId: string;
  isActive: boolean;
  isGuest: boolean;
}

export interface MondayWorkspace {
  id: string;
  name: string;
  description: string;
  kind: string;
  logo: string;
  url: string;
  teams: MondayTeam[];
  users: MondayUser[];
  settings: {
    color: string;
    value: string;
  }[];
}

export interface MondayTeam {
  id: string;
  name: string;
  pictureUrl: string;
  users: MondayUser[];
  workspaceId: string;
}

export interface MondayBoard {
  id: string;
  name: string;
  description: string;
  boardKind: string;
  owner: MondayUser;
  teams: MondayTeam[];
  subscribers: MondayUser[];
  columns: MondayColumn[];
  groups: MondayGroup[];
  items: MondayItem[];
  boardFolder: string;
  state: string;
  permissions: string;
  tags: MondayTag[];
  updatedBy: MondayUser;
  updatedAt: string;
  created_at: string;
  pos: number;
  topGroup: string;
  automationSettings: any;
  workspaceId: string;
  teamId: string;
  subscribersCount: number;
  views: MondayView[];
  activityLog: MondayActivity[];
}

export interface MondayColumn {
  id: string;
  title: string;
  columnType: string;
  settingsStr: string;
  width: number;
  pos: string;
  archived: boolean;
  description: string;
  integrationId: string;
  defaultAccessRole: string;
  createdAt: string;
  updatedAt: string;
  createdBy: MondayUser;
  limit: any;
  mappingId: string;
  descriptionEditable: boolean;
}

export interface MondayGroup {
  id: string;
  title: string;
  color: string;
  position: number;
  deleted: boolean;
  archived: boolean;
  items: MondayItem[];
  boardId: string;
  createdAt: string;
  createdAtUtc: string;
  updatedAt: string;
  updatedAtUtc: string;
}

export interface MondayItem {
  id: string;
  name: string;
  boardId: string;
  creatorId: string;
  subscribers: MondayUser[];
  columnValues: Record<string, any>;
  group: MondayGroup;
  updates: MondayUpdate[];
  notifications: MondayNotification[];
  creator: MondayUser;
  createdAt: string;
  updatedAt: string;
  state: string;
  pos: number;
  assetCount: number;
  modifiedBy: MondayUser;
  stateStr: string;
  url: string;
  metadata: any;
  parentItemId: string;
  parentItem: MondayItem;
  subitems: MondayItem[];
}

export interface MondayUpdate {
  id: string;
  body: string;
  itemId: string;
  creator: MondayUser;
  createdAt: string;
  updatedAt: string;
  attachments: MondayFile[];
  replies: MondayReply[];
  assets: MondayFile[];
  textBody: string;
  temporaryFilePath: string;
  notifications: MondayNotification[];
  isPinned: boolean;
  delta: any;
  idString: string;
}

export interface MondayNotification {
  id: string;
  text: string;
  userId: string;
  targetId: string;
  targetName: string;
  targetType: string;
  itemId: string;
  parentItemId: string;
  type: string;
  state: string;
  email: string;
  account: string;
  hasAccountInfo: boolean;
  displayUserNames: boolean;
  isSilent: boolean;
  visited: boolean;
  isDeleted: boolean;
  createAt: string;
  isMobile: boolean;
  eventTrigger: string;
  data: any;
  assignees: MondayUser[];
}

export interface MondayFile {
  id: string;
  name: string;
  extension: string;
  originalName: string;
  size: number;
  uploadedAt: string;
  url: string;
  mimeType: string;
  groupId: string;
  boardId: string;
  itemId: string;
  updateId: string;
  fileId: string;
  assetType: string;
  publicUrl: string;
  thumbnails: any;
  createdBy: MondayUser;
}

export interface MondayReply {
  id: string;
  body: string;
  itemId: string;
  creatorId: string;
  creator: MondayUser;
  createdAt: string;
  updatedAt: string;
  updateId: string;
  attachments: MondayFile[];
}

export interface MondayView {
  id: string;
  name: string;
  type: string;
  settingsStr: string;
  boardId: string;
  fields: MondayColumn[];
  order: number;
  position: number;
  itemId: number;
  url: string;
  settings: any;
  columns: MondayColumn[];
  isDefault: boolean;
}

export interface MondayTag {
  id: string;
  name: string;
  color: string;
}

export interface MondayActivity {
  id: string;
  event: string;
  userId: string;
  user: MondayUser;
  itemId: string;
  boardId: string;
  entity: string;
  data: any;
  text: string;
  createdAt: string;
}

export interface MondayForm {
  id: string;
  title: string;
  boardId: string;
  columns: MondayColumn[];
  structure: any;
  settings: any;
  isPublished: boolean;
  url: string;
  submissions: MondayFormSubmission[];
}

export interface MondayFormSubmission {
  id: string;
  formId: string;
  itemId: string;
  answers: Record<string, any>;
  submittedAt: string;
  submittedBy: MondayUser;
}

export interface MondayAutomation {
  id: string;
  name: string;
  boardId: string;
  trigger: any;
  recipe: any;
  isActive: boolean;
  createdAt: string;
  lastExecuted: string;
  executionCount: number;
  errorCount: number;
  settings: any;
}

export interface MondayConfig {
  apiToken: string;
  version: string;
  baseUrl: string;
  timeout: number;
  maxRetries: number;
}

// Main Component Interface
export interface MondayManagerProps {
  config?: Partial<MondayConfig>;
  onError?: (error: Error) => void;
  onSuccess?: (message: string) => void;
  theme?: 'light' | 'dark';
  compact?: boolean;
}

// Main Component
export const MondayManager: React.FC<MondayManagerProps> = ({
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
  const [activeWorkspace, setActiveWorkspace] = useState<string>('');
  
  // Data State
  const [workspaces, setWorkspaces] = useState<MondayWorkspace[]>([]);
  const [boards, setBoards] = useState<MondayBoard[]>([]);
  const [users, setUsers] = useState<MondayUser[]>([]);
  const [columns, setColumns] = useState<MondayColumn[]>([]);
  const [groups, setGroups] = useState<MondayGroup[]>([]);
  const [items, setItems] = useState<MondayItem[]>([]);
  const [updates, setUpdates] = useState<MondayUpdate[]>([]);
  const [notifications, setNotifications] = useState<MondayNotification[]>([]);
  const [forms, setForms] = useState<MondayForm[]>([]);
  const [automations, setAutomations] = useState<MondayAutomation[]>([]);
  const [activities, setActivities] = useState<MondayActivity[]>([]);
  const [files, setFiles] = useState<MondayFile[]>([]);
  const [views, setViews] = useState<MondayView[]>([]);
  const [tags, setTags] = useState<MondayTag[]>([]);
  
  // Modal State
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [modalMode, setModalMode] = useState<'create' | 'edit' | 'view'>('view');
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [detailsModalOpen, setDetailsModalOpen] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  
  // Form State
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [configData, setConfigData] = useState<MondayConfig>({
    apiToken: config?.apiToken || '',
    version: config?.version || '2023-10',
    baseUrl: config?.baseUrl || 'https://api.monday.com/v2',
    timeout: config?.timeout || 30000,
    maxRetries: config?.maxRetries || 3
  });
  
  // Filter State
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedBoard, setSelectedBoard] = useState<string>('');
  const [selectedGroup, setSelectedGroup] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedAssignee, setSelectedAssignee] = useState<string>('');
  const [selectedPriority, setSelectedPriority] = useState<string>('all');
  const [dateRange, setDateRange] = useState<{ start: string; end: string }>({
    start: '',
    end: ''
  });
  
  // Toast
  const toast = useToast();

  // API Base URL
  const API_BASE_URL = '/api/monday';

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

  // Connect to Monday.com
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
        onSuccess?.('Monday.com connected successfully');
        toast({
          title: 'Connection Successful',
          description: 'Monday.com has been connected successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        
        // Load initial data
        loadDashboardData();
      } else {
        throw new Error(data.error || 'Connection failed');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Connection Failed',
        description: error.message || 'Failed to connect to Monday.com',
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
      const [workspacesData, boardsData, usersData] = await Promise.all([
        fetch(`${API_BASE_URL}/workspaces`).then(r => r.json().then(d => d.success ? d.data : [])),
        fetch(`${API_BASE_URL}/boards`).then(r => r.json().then(d => d.success ? d.data : [])),
        fetch(`${API_BASE_URL}/users`).then(r => r.json().then(d => d.success ? d.data : []))
      ]);
      
      setWorkspaces(workspacesData);
      setBoards(boardsData);
      setUsers(usersData);
      
      // Set default workspace
      if (workspacesData.length > 0) {
        setActiveWorkspace(workspacesData[0].id);
      }
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  // Load Board Data
  const loadBoardData = useCallback(async (boardId: string) => {
    setIsLoading(true);
    try {
      const [boardData, columnsData, groupsData, itemsData] = await Promise.all([
        fetch(`${API_BASE_URL}/boards/${boardId}`).then(r => r.json().then(d => d.success ? d.data : null)),
        fetch(`${API_BASE_URL}/boards/${boardId}/columns`).then(r => r.json().then(d => d.success ? d.data : [])),
        fetch(`${API_BASE_URL}/boards/${boardId}/groups`).then(r => r.json().then(d => d.success ? d.data : [])),
        fetch(`${API_BASE_URL}/boards/${boardId}/items`).then(r => r.json().then(d => d.success ? d.data : []))
      ]);
      
      if (boardData) {
        setSelectedItem(boardData);
        setColumns(columnsData);
        setGroups(groupsData);
        setItems(itemsData);
      }
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setIsLoading(false);
    }
  }, [onError]);

  // Create Board
  const createBoard = useCallback(async (boardData: Partial<MondayBoard>) => {
    try {
      const response = await fetch(`${API_BASE_URL}/boards`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(boardData)
      });
      const data = await response.json();
      
      if (data.success) {
        onSuccess?.('Board created successfully');
        toast({
          title: 'Board Created',
          description: 'Board created successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        
        // Reload boards
        loadDashboardData();
      } else {
        throw new Error(data.error || 'Failed to create board');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Create Failed',
        description: error.message || 'Failed to create board',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [onError, onSuccess, toast]);

  // Create Item
  const createItem = useCallback(async (itemData: Partial<MondayItem>) => {
    try {
      const response = await fetch(`${API_BASE_URL}/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(itemData)
      });
      const data = await response.json();
      
      if (data.success) {
        onSuccess?.('Item created successfully');
        toast({
          title: 'Item Created',
          description: 'Item created successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
        
        // Reload items
        if (selectedBoard) {
          loadBoardData(selectedBoard);
        }
      } else {
        throw new Error(data.error || 'Failed to create item');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Create Failed',
        description: error.message || 'Failed to create item',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [onError, onSuccess, toast, selectedBoard]);

  // Create Update
  const createUpdate = useCallback(async (updateData: Partial<MondayUpdate>) => {
    try {
      const response = await fetch(`${API_BASE_URL}/updates`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updateData)
      });
      const data = await response.json();
      
      if (data.success) {
        onSuccess?.('Update created successfully');
        toast({
          title: 'Update Created',
          description: 'Update created successfully',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error(data.error || 'Failed to create update');
      }
    } catch (error: any) {
      onError?.(error);
      toast({
        title: 'Create Failed',
        description: error.message || 'Failed to create update',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [onError, onSuccess, toast]);

  // Filter Items
  const filteredItems = useMemo(() => {
    let filtered = items;
    
    if (searchTerm) {
      filtered = filtered.filter(item => 
        item.name.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    
    if (selectedGroup) {
      filtered = filtered.filter(item => item.group?.id === selectedGroup);
    }
    
    if (selectedStatus && selectedStatus !== 'all') {
      filtered = filtered.filter(item => item.state === selectedStatus);
    }
    
    if (selectedAssignee) {
      filtered = filtered.filter(item => 
        item.subscribers.some(user => user.id === selectedAssignee)
      );
    }
    
    return filtered;
  }, [items, searchTerm, selectedGroup, selectedStatus, selectedAssignee]);

  // Format Date
  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  // Format DateTime
  const formatDateTime = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  // Get Column Type Icon
  const getColumnIcon = (columnType: string) => {
    const icons: Record<string, any> = {
      status_text: FiFlag,
      status: FiFlag,
      date: FiCalendar,
      person: FiUsers,
      color: FiTag,
      dropdown: FiChevronDown,
      numbers: FiBarChart,
      text: FiEdit2,
      email: FiMail,
      phone: FiPhone,
      link: FiLink,
      timeline: FiClock,
      rating: FiStar,
      checkbox: FiCheckCircle,
      file: FiFolder,
      board_relation: FiGrid,
      formula: FiCpu,
      auto_number: FiTarget,
      country: FiGlobe,
      timezone: FiClock,
      hour: FiClock,
      week: FiCalendar,
      long_text: FiEdit2,
      dependency: FiGitBranch
    };
    return icons[columnType] || FiEdit2;
  };

  // Get Status Color
  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      all: 'gray',
      working_on: 'blue',
      stuck: 'red',
      done: 'green',
      pending: 'orange',
      review: 'purple',
      blocked: 'red',
      archived: 'gray'
    };
    return colors[status] || 'gray';
  };

  // Render Connection Status
  const renderConnectionStatus = () => (
    <Alert status={isConnected ? 'success' : 'warning'} mb={4}>
      <AlertIcon as={isConnected ? FiCheckCircle : FiAlertCircle} />
      <Box flex="1">
        <AlertTitle>{isConnected ? 'Connected' : 'Not Connected'}</AlertTitle>
        <AlertDescription>
          {isConnected 
            ? 'Monday.com is connected and ready for use'
            : 'Connect to Monday.com to access all Work OS features'
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
      
      {/* Workspace Overview */}
      <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiBriefcase} color="blue.500" boxSize={8} />
              <Stat>
                <StatLabel>Workspaces</StatLabel>
                <StatNumber>{workspaces.length}</StatNumber>
                <StatHelpText>Total workspaces</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiGrid} color="green.500" boxSize={8} />
              <Stat>
                <StatLabel>Boards</StatLabel>
                <StatNumber>{boards.length}</StatNumber>
                <StatHelpText>Total boards</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiUsers} color="orange.500" boxSize={8} />
              <Stat>
                <StatLabel>Users</StatLabel>
                <StatNumber>{users.length}</StatNumber>
                <StatHelpText>Total users</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody>
            <HStack>
              <Icon as={FiList} color="purple.500" boxSize={8} />
              <Stat>
                <StatLabel>Items</StatLabel>
                <StatNumber>{items.length}</StatNumber>
                <StatHelpText>Total items</StatHelpText>
              </Stat>
            </HStack>
          </CardBody>
        </Card>
      </SimpleGrid>

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <HStack>
            <Icon as={FiActivity} color="blue.500" />
            <Heading size="md">Recent Activity</Heading>
          </HStack>
        </CardHeader>
        <CardBody>
          <VStack align="stretch" spacing={3}>
            {activities.slice(0, 5).map((activity) => (
              <HStack key={activity.id} p={3} borderWidth="1px" borderRadius="md">
                <Avatar size="sm" name={activity.user?.name} src={activity.user?.photoUrl} />
                <VStack align="start" spacing={0}>
                  <Text fontWeight="medium">{activity.text}</Text>
                  <Text fontSize="sm" color="gray.500">{formatDateTime(activity.createdAt)}</Text>
                </VStack>
              </HStack>
            ))}
          </VStack>
        </CardBody>
      </Card>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <Heading size="md">Quick Actions</Heading>
        </CardHeader>
        <CardBody>
          <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={4}>
            <Button 
              leftIcon={<FiPlus />}
              colorScheme="blue"
              onClick={() => {
                setModalMode('create');
                setFormData({ name: '', description: '', boardKind: 'public' });
                setCreateModalOpen(true);
              }}
            >
              Create Board
            </Button>
            <Button 
              leftIcon={<FiUsers />}
              colorScheme="green"
              onClick={() => setActiveTab('users')}
            >
              Manage Users
            </Button>
            <Button 
              leftIcon={<FiZap />}
              colorScheme="orange"
              onClick={() => setActiveTab('automations')}
            >
              Create Automation
            </Button>
            <Button 
              leftIcon={<FiBarChart />}
              colorScheme="purple"
              onClick={() => setActiveTab('analytics')}
            >
              View Analytics
            </Button>
          </SimpleGrid>
        </CardBody>
      </Card>
    </VStack>
  );

  // Render Boards Management
  const renderBoards = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Boards Management</Heading>
        <HStack>
          <Input 
            placeholder="Search boards..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            width="300px"
          />
          <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
            Refresh
          </Button>
          <Button 
            leftIcon={<FiPlus />}
            colorScheme="blue"
            onClick={() => {
              setModalMode('create');
              setFormData({ name: '', description: '', boardKind: 'public' });
              setCreateModalOpen(true);
            }}
          >
            Create Board
          </Button>
        </HStack>
      </Flex>
      
      {boards.length > 0 && (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {boards.filter(board => 
            searchTerm === '' || board.name.toLowerCase().includes(searchTerm.toLowerCase())
          ).map((board) => (
            <Card key={board.id} cursor="pointer" onClick={() => loadBoardData(board.id)}>
              <CardBody>
                <VStack align="start" spacing={3}>
                  <HStack justify="space-between" width="100%">
                    <Heading size="sm" noOfLines={1}>{board.name}</Heading>
                    <Badge colorScheme={board.state === 'active' ? 'green' : 'gray'}>
                      {board.state}
                    </Badge>
                  </HStack>
                  {board.description && (
                    <Text fontSize="sm" color="gray.600" noOfLines={2}>
                      {board.description}
                    </Text>
                  )}
                  <HStack justify="space-between" width="100%">
                    <HStack>
                      <Icon as={FiUsers} color="gray.500" />
                      <Text fontSize="sm">{board.subscribers.length}</Text>
                    </HStack>
                    <HStack>
                      <Icon as={FiList} color="gray.500" />
                      <Text fontSize="sm">{board.items?.length || 0}</Text>
                    </HStack>
                  </HStack>
                  <Text fontSize="xs" color="gray.500">
                    Updated: {formatDate(board.updatedAt)}
                  </Text>
                </VStack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>
      )}
      
      {isLoading && (
        <Center py={8}>
          <VStack>
            <Spinner size="xl" />
            <Text>Loading boards...</Text>
          </VStack>
        </Center>
      )}
    </VStack>
  );

  // Render Items Management
  const renderItems = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Items Management</Heading>
        <HStack>
          <Input 
            placeholder="Search items..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            width="300px"
          />
          <Select 
            value={selectedGroup}
            onChange={(e) => setSelectedGroup(e.target.value)}
            width="200px"
          >
            <option value="">All Groups</option>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>{group.title}</option>
            ))}
          </Select>
          <Select 
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            width="200px"
          >
            <option value="all">All Status</option>
            <option value="working_on">Working On</option>
            <option value="stuck">Stuck</option>
            <option value="done">Done</option>
            <option value="pending">Pending</option>
          </Select>
          <Button 
            leftIcon={<FiPlus />}
            colorScheme="blue"
            onClick={() => {
              setModalMode('create');
              setFormData({ name: '', groupId: selectedGroup });
              setCreateModalOpen(true);
            }}
          >
            Create Item
          </Button>
        </HStack>
      </Flex>
      
      {filteredItems.length > 0 && (
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Name</Th>
                <Th>Group</Th>
                <Th>Status</Th>
                <Th>Assignees</Th>
                <Th>Updated</Th>
                <Th>Actions</Th>
              </Tr>
            </Thead>
            <Tbody>
              {filteredItems.map((item) => (
                <Tr key={item.id}>
                  <Td>
                    <HStack>
                      <Icon as={FiList} color="blue.500" />
                      <VStack align="start" spacing={0}>
                        <Text fontWeight="medium">{item.name}</Text>
                        {item.creator && (
                          <Text fontSize="sm" color="gray.500">
                            By {item.creator.name}
                          </Text>
                        )}
                      </VStack>
                    </HStack>
                  </Td>
                  <Td>
                    <Badge colorScheme={item.group?.color || 'gray'}>
                      {item.group?.title || 'No Group'}
                    </Badge>
                  </Td>
                  <Td>
                    <Badge colorScheme={getStatusColor(item.state)}>
                      {item.stateStr || item.state}
                    </Badge>
                  </Td>
                  <Td>
                    <AvatarGroup size="sm" max={3}>
                      {item.subscribers.map((user) => (
                        <Avatar key={user.id} name={user.name} src={user.photoUrl} />
                      ))}
                    </AvatarGroup>
                  </Td>
                  <Td>
                    <Text fontSize="sm">{formatDate(item.updatedAt)}</Text>
                  </Td>
                  <Td>
                    <HStack spacing={2}>
                      <IconButton 
                        icon={<FiEye />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(item);
                          setModalMode('view');
                          setDetailsModalOpen(true);
                        }}
                      />
                      <IconButton 
                        icon={<FiEdit2 />} 
                        size="sm" 
                        variant="ghost"
                        onClick={() => {
                          setSelectedItem(item);
                          setModalMode('edit');
                          setCreateModalOpen(true);
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
            <Text>Loading items...</Text>
          </VStack>
        </Center>
      )}
    </VStack>
  );

  // Render Users Management
  const renderUsers = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Users Management</Heading>
        <HStack>
          <Input 
            placeholder="Search users..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            width="300px"
          />
          <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
            Refresh
          </Button>
        </HStack>
      </Flex>
      
      <SimpleGrid columns={{ base: 1, md: 2, lg: 3, xl: 4 }} spacing={4}>
        {users.filter(user => 
          searchTerm === '' || user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
          user.email.toLowerCase().includes(searchTerm.toLowerCase())
        ).map((user) => (
          <Card key={user.id}>
            <CardBody>
              <VStack align="center" spacing={3}>
                <Avatar size="xl" name={user.name} src={user.photoUrl}>
                  <AvatarBadge boxSize="1.25em" bg={user.isActive ? 'green.500' : 'red.500'} />
                </Avatar>
                <VStack align="center" spacing={1}>
                  <Heading size="sm" textAlign="center">{user.name}</Heading>
                  <Text fontSize="sm" color="gray.600">{user.email}</Text>
                  {user.title && (
                    <Text fontSize="xs" color="gray.500">{user.title}</Text>
                  )}
                  <Badge colorScheme={user.isGuest ? 'orange' : 'blue'}>
                    {user.isGuest ? 'Guest' : 'Member'}
                  </Badge>
                  <Text fontSize="xs" color="gray.500">
                    Joined: {formatDate(user.joinDate)}
                  </Text>
                </VStack>
              </VStack>
            </CardBody>
          </Card>
        ))}
      </SimpleGrid>
    </VStack>
  );

  // Render Automations Management
  const renderAutomations = () => (
    <VStack spacing={6} align="stretch">
      {renderConnectionStatus()}
      
      <Flex justify="space-between" align="center">
        <Heading size="lg">Automations</Heading>
        <HStack>
          <Button leftIcon={<FiRefreshCw />} onClick={loadDashboardData} isLoading={isLoading}>
            Refresh
          </Button>
          <Button leftIcon={<FiPlus />} colorScheme="orange">
            Create Automation
          </Button>
        </HStack>
      </Flex>
      
      {automations.length > 0 && (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={4}>
          {automations.map((automation) => (
            <Card key={automation.id}>
              <CardBody>
                <VStack align="start" spacing={3}>
                  <HStack justify="space-between" width="100%">
                    <Heading size="sm" noOfLines={1}>{automation.name}</Heading>
                    <Badge colorScheme={automation.isActive ? 'green' : 'red'}>
                      {automation.isActive ? 'Active' : 'Inactive'}
                    </Badge>
                  </HStack>
                  <Text fontSize="sm" color="gray.600">
                    Last executed: {automation.lastExecuted ? formatDateTime(automation.lastExecuted) : 'Never'}
                  </Text>
                  <HStack justify="space-between" width="100%">
                    <HStack>
                      <Icon as={FiPlay} color="gray.500" />
                      <Text fontSize="sm">{automation.executionCount}</Text>
                    </HStack>
                    {automation.errorCount > 0 && (
                      <HStack>
                        <Icon as={FiAlertCircle} color="red.500" />
                        <Text fontSize="sm" color="red.500">{automation.errorCount}</Text>
                      </HStack>
                    )}
                  </HStack>
                </VStack>
              </CardBody>
            </Card>
          ))}
        </SimpleGrid>
      )}
      
      {automations.length === 0 && (
        <Alert status="info">
          <AlertIcon as={FiInfo} />
          <AlertTitle>No Automations</AlertTitle>
          <AlertDescription>No automations have been created yet. Create your first automation to get started.</AlertDescription>
        </Alert>
      )}
    </VStack>
  );

  // Render Settings
  const renderSettings = () => (
    <VStack spacing={6} align="stretch">
      <Card>
        <CardHeader>
          <Heading size="lg">Monday.com Settings</Heading>
        </CardHeader>
        <CardBody>
          <VStack spacing={6}>
            <Alert status="info">
              <AlertIcon as={FiInfo} />
              <Box>
                <AlertTitle>Configuration Status</AlertTitle>
                <AlertDescription>
                  {isConnected 
                    ? 'Monday.com is properly configured and connected'
                    : 'Configure Monday.com API settings to enable all features'
                  }
                </AlertDescription>
              </Box>
            </Alert>
            
            <FormControl>
              <FormLabel>API Token</FormLabel>
              <Input 
                type="password"
                value={configData.apiToken}
                onChange={(e) => setConfigData({ ...configData, apiToken: e.target.value })}
                isDisabled={isConnected}
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>API Version</FormLabel>
              <Select 
                value={configData.version}
                onChange={(e) => setConfigData({ ...configData, version: e.target.value })}
                isDisabled={isConnected}
              >
                <option value="2023-10">2023-10 (Latest)</option>
                <option value="2023-07">2023-07</option>
                <option value="2023-04">2023-04</option>
              </Select>
            </FormControl>
            
            <FormControl>
              <FormLabel>Base URL</FormLabel>
              <Input 
                value={configData.baseUrl}
                onChange={(e) => setConfigData({ ...configData, baseUrl: e.target.value })}
                isDisabled={isConnected}
              />
            </FormControl>
            
            <FormControl>
              <FormLabel>Timeout (ms)</FormLabel>
              <NumberInput 
                value={configData.timeout}
                onChange={(value) => setConfigData({ ...configData, timeout: value })}
                min={1000}
                max={60000}
                isDisabled={isConnected}
              >
                <NumberInputField />
              </NumberInput>
            </FormControl>
            
            <FormControl>
              <FormLabel>Max Retries</FormLabel>
              <NumberInput 
                value={configData.maxRetries}
                onChange={(value) => setConfigData({ ...configData, maxRetries: value })}
                min={0}
                max={10}
                isDisabled={isConnected}
              >
                <NumberInputField />
              </NumberInput>
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

  // Load data when tab changes
  useEffect(() => {
    if (isConnected) {
      switch (activeTab) {
        case 'dashboard':
          loadDashboardData();
          break;
        case 'boards':
          loadDashboardData();
          break;
        case 'items':
          if (selectedBoard) {
            loadBoardData(selectedBoard);
          }
          break;
        case 'users':
          loadDashboardData();
          break;
        case 'automations':
          // Load automations data
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
            <Icon as={FiGrid} color="blue.500" boxSize={8} />
            <Heading size="xl">Monday.com</Heading>
          </HStack>
          <ButtonGroup>
            <Button leftIcon={<FiRefreshCw />} onClick={() => window.location.reload()}>
              Reload
            </Button>
          </ButtonGroup>
        </HStack>

        {/* Tabs */}
        <Tabs 
          index={['dashboard', 'boards', 'items', 'users', 'automations', 'settings'].indexOf(activeTab)}
          onChange={(index) => setActiveTab(['dashboard', 'boards', 'items', 'users', 'automations', 'settings'][index])}
          variant="enclosed"
          colorScheme="blue"
        >
          <TabList>
            <Tab>Dashboard</Tab>
            <Tab>Boards</Tab>
            <Tab>Items</Tab>
            <Tab>Users</Tab>
            <Tab>Automations</Tab>
            <Tab>Settings</Tab>
          </TabList>
          
          <TabPanels>
            <TabPanel>
              {renderDashboard()}
            </TabPanel>
            <TabPanel>
              {renderBoards()}
            </TabPanel>
            <TabPanel>
              {renderItems()}
            </TabPanel>
            <TabPanel>
              {renderUsers()}
            </TabPanel>
            <TabPanel>
              {renderAutomations()}
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
          <ModalHeader>Configure Monday.com</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <Alert status="info">
                <AlertIcon as={FiInfo} />
                <Box>
                  <AlertTitle>Configuration Required</AlertTitle>
                  <AlertDescription>
                    Enter your Monday.com API token to connect to your Work OS.
                  </AlertDescription>
                </Box>
              </Alert>
              
              <FormControl isInvalid={!configData.apiToken}>
                <FormLabel>API Token</FormLabel>
                <Input 
                  type="password"
                  value={configData.apiToken}
                  onChange={(e) => setConfigData({ ...configData, apiToken: e.target.value })}
                  placeholder="your-monday-api-token"
                />
                <FormErrorMessage>API Token is required</FormErrorMessage>
              </FormControl>
              
              <FormControl>
                <FormLabel>API Version</FormLabel>
                <Select 
                  value={configData.version}
                  onChange={(e) => setConfigData({ ...configData, version: e.target.value })}
                >
                  <option value="2023-10">2023-10 (Latest)</option>
                  <option value="2023-07">2023-07</option>
                  <option value="2023-04">2023-04</option>
                </Select>
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
              isDisabled={!configData.apiToken}
            >
              Connect
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Create Board Modal */}
      <Modal isOpen={createModalOpen} onClose={() => setCreateModalOpen(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>
            {modalMode === 'create' ? 'Create Board' : 'Create Item'}
          </ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl isInvalid={!formData.name}>
                <FormLabel>Name</FormLabel>
                <Input 
                  value={formData.name || ''}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder={modalMode === 'create' ? 'Board name' : 'Item name'}
                />
                <FormErrorMessage>Name is required</FormErrorMessage>
              </FormControl>
              
              {modalMode === 'create' && (
                <>
                  <FormControl>
                    <FormLabel>Description</FormLabel>
                    <Textarea 
                      value={formData.description || ''}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      placeholder="Board description"
                      rows={3}
                    />
                  </FormControl>
                  
                  <FormControl>
                    <FormLabel>Board Type</FormLabel>
                    <Select 
                      value={formData.boardKind || 'public'}
                      onChange={(e) => setFormData({ ...formData, boardKind: e.target.value })}
                    >
                      <option value="public">Public</option>
                      <option value="private">Private</option>
                      <option value="share">Share</option>
                    </Select>
                  </FormControl>
                </>
              )}
              
              {modalMode === 'edit' && selectedItem && (
                <FormControl>
                  <FormLabel>Group</FormLabel>
                  <Select 
                    value={formData.groupId || selectedItem.group?.id}
                    onChange={(e) => setFormData({ ...formData, groupId: e.target.value })}
                  >
                    <option value="">Select a group</option>
                    {groups.map((group) => (
                      <option key={group.id} value={group.id}>{group.title}</option>
                    ))}
                  </Select>
                </FormControl>
              )}
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={() => setCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button 
              colorScheme="blue" 
              onClick={() => {
                if (modalMode === 'create') {
                  createBoard(formData);
                } else {
                  createItem(formData);
                }
                setCreateModalOpen(false);
              }}
              isDisabled={!formData.name}
            >
              {modalMode === 'create' ? 'Create Board' : 'Create Item'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Container>
  );
};

export default MondayManager;