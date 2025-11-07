import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  HStack,
  Heading,
  Text,
  Button,
  Card,
  CardBody,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Input,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  Select,
  Divider,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Progress,
  IconButton,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Flex,
  Tag,
  TagLabel,
  TagLeftIcon,
  TagRightIcon,
  Switch,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  Checkbox,
  CheckboxGroup,
  Stack
} from '@chakra-ui/react';
import {
  AddIcon,
  EditIcon,
  DeleteIcon,
  ViewIcon,
  SettingsIcon,
  EmailIcon,
  ChatIcon,
  PhoneIcon,
  CheckIcon,
  CloseIcon,
  RepeatIcon,
  ExternalLinkIcon,
  TimeIcon,
  WarningIcon,
  InfoIcon,
  StarIcon,
  SearchIcon,
  FilterIcon,
  DownloadIcon,
  BellIcon
} from '@chakra-ui/icons';
import { zendeskSkills } from './skills/zendeskSkills';

interface ZendeskConfig {
  subdomain?: string;
  accessToken?: string;
  environment: 'production' | 'sandbox';
}

interface ZendeskTicket {
  id: number;
  subject: string;
  description: string;
  status: string;
  priority: string;
  type: string;
  requester_id: number;
  requester: {
    id: number;
    name: string;
    email: string;
    role: string;
  };
  assignee_id?: number;
  assignee?: {
    id: number;
    name: string;
    email: string;
  };
  group_id?: number;
  group?: {
    id: number;
    name: string;
  };
  organization_id?: number;
  organization?: {
    id: number;
    name: string;
  };
  via: {
    channel: string;
    source: {
      from: any;
      to: any;
      rel: string;
    };
  };
  created_at: string;
  updated_at: string;
  due_at?: string;
  custom_fields?: Array<{
    id: number;
    value: any;
  }>;
  tags: string[];
  satisfaction_rating?: {
    score: string;
    comment: string;
  };
}

interface ZendeskUser {
  id: number;
  name: string;
  email: string;
  role: string;
  custom_role_id?: number;
  default_group_id?: number;
  phone?: string;
  shared_phone_number?: boolean;
  shared_agent?: boolean;
  notes?: string;
  active: boolean;
  verified: boolean;
  locale?: string;
  timezone?: string;
  last_login_at?: string;
  two_factor_auth_enabled?: boolean;
  signature?: string;
  details?: string;
  photo?: {
    thumbnails: {
      small: string;
      medium: string;
      large: string;
    };
  };
  tags: string[];
  restricted_agent: boolean;
  only_private_comments: boolean;
  ticket_restriction: string;
  suspended?: boolean;
  custom_fields?: Array<{
    id: number;
    value: any;
  }>;
}

interface ZendeskGroup {
  id: number;
  name: string;
  description: string;
  is_public: boolean;
  default: boolean;
  created_at: string;
  updated_at: string;
  deleted_at?: string;
}

interface ZendeskOrganization {
  id: number;
  name: string;
  notes?: string;
  shared_tickets?: boolean;
  shared_comments?: boolean;
  domain_names?: string[];
  group_id?: number;
  created_at: string;
  updated_at: string;
  tags: string[];
  external_id?: string;
  custom_fields?: Array<{
    id: number;
    value: any;
  }>;
}

interface ZendeskMetric {
  tickets_solved: number;
  tickets_unsolved: number;
  tickets_on_hold: number;
  tickets_opened: number;
  tickets_closed: number;
  tickets_reopened: number;
  tickets_satisfaction_score: number;
  tickets_abandonment_rate: number;
  tickets_first_resolution_time: number;
  tickets_average_reply_time: number;
  tickets_full_resolution_time: number;
  tickets_agent_stations: number;
}

const ZendeskIntegration: React.FC = () => {
  const [config, setConfig] = useState<ZendeskConfig>({ environment: 'production' });
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const toast = useToast();

  // Data states
  const [tickets, setTickets] = useState<ZendeskTicket[]>([]);
  const [users, setUsers] = useState<ZendeskUser[]>([]);
  const [groups, setGroups] = useState<ZendeskGroup[]>([]);
  const [organizations, setOrganizations] = useState<ZendeskOrganization[]>([]);
  const [metrics, setMetrics] = useState<ZendeskMetric | null>(null);

  // Modal states
  const [isTicketModalOpen, setIsTicketModalOpen] = useState(false);
  const [isUserModalOpen, setIsUserModalOpen] = useState(false);
  const [isGroupModalOpen, setIsGroupModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<any>(null);

  // Filters and search
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [assigneeFilter, setAssigneeFilter] = useState('');

  // Forms
  const [ticketForm, setTicketForm] = useState({
    subject: '',
    description: '',
    type: 'question',
    priority: 'normal',
    status: 'open',
    requester_id: 0,
    assignee_id: undefined,
    group_id: undefined,
    tags: []
  });

  const [userForm, setUserForm] = useState({
    name: '',
    email: '',
    role: 'end-user',
    phone: '',
    notes: '',
    active: true,
    verified: true,
    tags: []
  });

  const [groupForm, setGroupForm] = useState({
    name: '',
    description: '',
    is_public: true,
    default: false
  });

  useEffect(() => {
    checkAuthentication();
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated]);

  const checkAuthentication = async () => {
    try {
      const tokens = await zendeskSkills.getStoredTokens();
      if (tokens && tokens.accessToken) {
        setIsAuthenticated(true);
        setConfig({
          accessToken: tokens.accessToken,
          subdomain: tokens.subdomain,
          environment: tokens.environment || 'production'
        });
      }
    } catch (error) {
      console.error('Authentication check failed:', error);
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const [ticketsData, usersData, groupsData, organizationsData, metricsData] = await Promise.all([
        zendeskSkills.getTickets({ limit: 100 }),
        zendeskSkills.getUsers({ limit: 100 }),
        zendeskSkills.getGroups(),
        zendeskSkills.getOrganizations({ limit: 100 }),
        zendeskSkills.getMetrics()
      ]);

      setTickets(ticketsData.tickets || []);
      setUsers(usersData.users || []);
      setGroups(groupsData.groups || []);
      setOrganizations(organizationsData.organizations || []);
      setMetrics(metricsData);
    } catch (error) {
      toast({
        title: 'Error loading data',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleAuthentication = () => {
    window.location.href = `/auth/zendesk`;
  };

  const handleCreateTicket = async () => {
    try {
      setLoading(true);
      const newTicket = await zendeskSkills.createTicket(ticketForm);
      setTickets([newTicket, ...tickets]);
      setIsTicketModalOpen(false);
      setTicketForm({
        subject: '',
        description: '',
        type: 'question',
        priority: 'normal',
        status: 'open',
        requester_id: 0,
        assignee_id: undefined,
        group_id: undefined,
        tags: []
      });
      toast({
        title: 'Ticket created',
        description: 'Ticket has been created successfully',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
    } catch (error) {
      toast({
        title: 'Error creating ticket',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    try {
      setLoading(true);
      const newUser = await zendeskSkills.createUser(userForm);
      setUsers([newUser, ...users]);
      setIsUserModalOpen(false);
      setUserForm({
        name: '',
        email: '',
        role: 'end-user',
        phone: '',
        notes: '',
        active: true,
        verified: true,
        tags: []
      });
      toast({
        title: 'User created',
        description: 'User has been created successfully',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
    } catch (error) {
      toast({
        title: 'Error creating user',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateGroup = async () => {
    try {
      setLoading(true);
      const newGroup = await zendeskSkills.createGroup(groupForm);
      setGroups([newGroup, ...groups]);
      setIsGroupModalOpen(false);
      setGroupForm({
        name: '',
        description: '',
        is_public: true,
        default: false
      });
      toast({
        title: 'Group created',
        description: 'Group has been created successfully',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
    } catch (error) {
      toast({
        title: 'Error creating group',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: { [key: string]: string } = {
      new: 'green',
      open: 'blue',
      pending: 'yellow',
      hold: 'orange',
      solved: 'purple',
      closed: 'gray'
    };
    return colors[status] || 'gray';
  };

  const getPriorityBadge = (priority: string) => {
    const colors: { [key: string]: string } = {
      urgent: 'red',
      high: 'orange',
      normal: 'blue',
      low: 'green'
    };
    return colors[priority] || 'gray';
  };

  const getTypeBadge = (type: string) => {
    const colors: { [key: string]: string } = {
      question: 'blue',
      incident: 'red',
      problem: 'orange',
      task: 'green'
    };
    return colors[type] || 'gray';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const getRelativeTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(hours / 24);
    
    if (days > 0) {
      return `${days} day${days > 1 ? 's' : ''} ago`;
    } else if (hours > 0) {
      return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else {
      return 'Just now';
    }
  };

  const filteredTickets = tickets.filter(ticket => {
    const matchesSearch = !searchQuery || 
      ticket.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.requester.name.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = !statusFilter || ticket.status === statusFilter;
    const matchesPriority = !priorityFilter || ticket.priority === priorityFilter;
    const matchesAssignee = !assigneeFilter || 
      (ticket.assignee && ticket.assignee.name.toLowerCase().includes(assigneeFilter.toLowerCase()));
    
    return matchesSearch && matchesStatus && matchesPriority && matchesAssignee;
  });

  if (!isAuthenticated) {
    return (
      <Box minH="100vh" bg="white" p={6}>
        <VStack spacing={8} maxW="800px" mx="auto">
          <VStack spacing={4} textAlign="center">
            <Heading size="2xl" color="red.500">Zendesk Integration</Heading>
            <Text fontSize="xl" color="gray.600">
              Complete customer support and ticketing management platform
            </Text>
            <Text color="gray.500">
              Manage support tickets, users, and customer service operations
            </Text>
          </VStack>

          <Card bg="red.50" borderColor="red.200" borderWidth={2}>
            <CardBody p={8} textAlign="center">
              <VStack spacing={6}>
                <Heading size="lg" color="red.600">Connect to Zendesk</Heading>
                <Text color="gray.600">
                  Authenticate with Zendesk to access your customer support data
                </Text>
                <Button
                  size="lg"
                  colorScheme="red"
                  onClick={handleAuthentication}
                  loadingText="Connecting to Zendesk..."
                  isLoading={loading}
                >
                  <ExternalLinkIcon mr={2} />
                  Connect Zendesk Account
                </Button>
              </VStack>
            </CardBody>
          </Card>

          <SimpleGrid columns={3} spacing={6} w="full">
            <Stat>
              <StatLabel>Ticket Management</StatLabel>
              <StatNumber color="red.500">∞</StatNumber>
              <StatHelpText>Complete ticket lifecycle</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Customer Support</StatLabel>
              <StatNumber color="red.500">24/7</StatNumber>
              <StatHelpText>Round-the-clock support</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Team Collaboration</StatLabel>
              <StatNumber color="red.500">∞</StatNumber>
              <StatHelpText>Seamless team workflows</StatHelpText>
            </Stat>
          </SimpleGrid>
        </VStack>
      </Box>
    );
  }

  return (
    <Box minH="100vh" bg="gray.50" p={6}>
      <VStack spacing={6} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <Flex justify="space-between" align="center" bg="white" p={6} rounded="lg" shadow="sm">
          <VStack align="start" spacing={2}>
            <Heading size="2xl" color="red.500">Zendesk Integration</Heading>
            <Text color="gray.600">
              {config.environment === 'sandbox' ? 'Sandbox' : 'Production'} • Subdomain: {config.subdomain}
            </Text>
          </VStack>
          <HStack>
            <Button
              variant="outline"
              onClick={loadData}
              isLoading={loading}
              leftIcon={<RepeatIcon />}
            >
              Refresh Data
            </Button>
            <Button
              colorScheme="red"
              onClick={() => window.open(`https://${config.subdomain}.zendesk.com`, '_blank')}
              rightIcon={<ExternalLinkIcon />}
            >
              Open Zendesk
            </Button>
          </HStack>
        </Flex>

        {/* Metrics Dashboard */}
        {metrics && (
          <SimpleGrid columns={6} spacing={4}>
            <Stat bg="white" p={4} rounded="lg" shadow="sm">
              <StatLabel>Tickets Solved</StatLabel>
              <StatNumber color="green.500">{metrics.tickets_solved.toLocaleString()}</StatNumber>
            </Stat>
            <Stat bg="white" p={4} rounded="lg" shadow="sm">
              <StatLabel>Tickets Open</StatLabel>
              <StatNumber color="blue.500">{metrics.tickets_opened.toLocaleString()}</StatNumber>
            </Stat>
            <Stat bg="white" p={4} rounded="lg" shadow="sm">
              <StatLabel>Tickets Pending</StatLabel>
              <StatNumber color="yellow.500">{metrics.tickets_unsolved.toLocaleString()}</StatNumber>
            </Stat>
            <Stat bg="white" p={4} rounded="lg" shadow="sm">
              <StatLabel>Satisfaction Score</StatLabel>
              <StatNumber color="purple.500">{metrics.tickets_satisfaction_score}%</StatNumber>
            </Stat>
            <Stat bg="white" p={4} rounded="lg" shadow="sm">
              <StatLabel>Resolution Time</StatLabel>
              <StatNumber color="orange.500">{metrics.tickets_first_resolution_time}h</StatNumber>
            </Stat>
            <Stat bg="white" p={4} rounded="lg" shadow="sm">
              <StatLabel>Reply Time</StatLabel>
              <StatNumber color="teal.500">{metrics.tickets_average_reply_time}h</StatNumber>
            </Stat>
          </SimpleGrid>
        )}

        {/* Main Content */}
        <Tabs
          index={activeTab}
          onChange={(index) => setActiveTab(index)}
          bg="white"
          rounded="lg"
          shadow="sm"
        >
          <TabList borderBottomWidth={2} borderColor="gray.200">
            <Tab _selected={{ color: 'red.500', borderBottomColor: 'red.500' }}>
              <ChatIcon mr={2} /> Tickets
            </Tab>
            <Tab _selected={{ color: 'red.500', borderBottomColor: 'red.500' }}>
              <StarIcon mr={2} /> Users
            </Tab>
            <Tab _selected={{ color: 'red.500', borderBottomColor: 'red.500' }}>
              <SettingsIcon mr={2} /> Groups
            </Tab>
            <Tab _selected={{ color: 'red.500', borderBottomColor: 'red.500' }}>
              <InfoIcon mr={2} /> Organizations
            </Tab>
          </TabList>

          <TabPanels>
            {/* Tickets Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                {/* Search and Filters */}
                <HStack spacing={4} w="full">
                  <Input
                    placeholder="Search tickets..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    leftIcon={<SearchIcon />}
                    flex={1}
                  />
                  <Select
                    placeholder="Status"
                    value={statusFilter}
                    onChange={(e) => setStatusFilter(e.target.value)}
                    w="150px"
                  >
                    <option value="">All Status</option>
                    <option value="new">New</option>
                    <option value="open">Open</option>
                    <option value="pending">Pending</option>
                    <option value="hold">Hold</option>
                    <option value="solved">Solved</option>
                    <option value="closed">Closed</option>
                  </Select>
                  <Select
                    placeholder="Priority"
                    value={priorityFilter}
                    onChange={(e) => setPriorityFilter(e.target.value)}
                    w="150px"
                  >
                    <option value="">All Priority</option>
                    <option value="urgent">Urgent</option>
                    <option value="high">High</option>
                    <option value="normal">Normal</option>
                    <option value="low">Low</option>
                  </Select>
                  <Button
                    colorScheme="red"
                    onClick={() => setIsTicketModalOpen(true)}
                    leftIcon={<AddIcon />}
                  >
                    New Ticket
                  </Button>
                </HStack>

                {/* Tickets Table */}
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>ID</Th>
                        <Th>Subject</Th>
                        <Th>Requester</Th>
                        <Th>Assignee</Th>
                        <Th>Status</Th>
                        <Th>Priority</Th>
                        <Th>Type</Th>
                        <Th>Created</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {filteredTickets.map((ticket) => (
                        <Tr key={ticket.id}>
                          <Td>
                            <Text fontWeight="medium">#{ticket.id}</Text>
                          </Td>
                          <Td>
                            <Text fontWeight="medium" noOfLines={2}>
                              {ticket.subject}
                            </Text>
                          </Td>
                          <Td>
                            <HStack>
                              <EmailIcon color="gray.400" />
                              <Text>{ticket.requester.name}</Text>
                            </HStack>
                          </Td>
                          <Td>
                            {ticket.assignee ? (
                              <Text>{ticket.assignee.name}</Text>
                            ) : (
                              <Text color="gray.500">Unassigned</Text>
                            )}
                          </Td>
                          <Td>
                            <Badge colorScheme={getStatusBadge(ticket.status)}>
                              {ticket.status}
                            </Badge>
                          </Td>
                          <Td>
                            <Badge colorScheme={getPriorityBadge(ticket.priority)}>
                              {ticket.priority}
                            </Badge>
                          </Td>
                          <Td>
                            <Badge colorScheme={getTypeBadge(ticket.type)}>
                              {ticket.type}
                            </Badge>
                          </Td>
                          <Td>
                            <VStack align="start" spacing={0}>
                              <Text fontSize="sm">{formatDate(ticket.created_at)}</Text>
                              <Text fontSize="xs" color="gray.500">
                                {getRelativeTime(ticket.created_at)}
                              </Text>
                            </VStack>
                          </Td>
                          <Td>
                            <Menu>
                              <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                              <MenuList>
                                <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                                <MenuItem icon={<EditIcon />}>Edit Ticket</MenuItem>
                                <MenuItem icon={<DeleteIcon />}>Delete Ticket</MenuItem>
                              </MenuList>
                            </Menu>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Users Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <HStack justify="space-between" w="full">
                  <Heading size="lg">Users</Heading>
                  <Button
                    colorScheme="red"
                    onClick={() => setIsUserModalOpen(true)}
                    leftIcon={<AddIcon />}
                  >
                    Add User
                  </Button>
                </HStack>

                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Name</Th>
                        <Th>Email</Th>
                        <Th>Role</Th>
                        <Th>Active</Th>
                        <Th>Verified</Th>
                        <Th>Tags</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {users.map((user) => (
                        <Tr key={user.id}>
                          <Td>
                            <HStack>
                              {user.photo?.thumbnails?.small && (
                                <img
                                  src={user.photo.thumbnails.small}
                                  alt={user.name}
                                  style={{ width: '24px', height: '24px', borderRadius: '50%' }}
                                />
                              )}
                              <Text fontWeight="medium">{user.name}</Text>
                            </HStack>
                          </Td>
                          <Td>{user.email}</Td>
                          <Td>
                            <Badge colorScheme={user.role === 'admin' ? 'red' : user.role === 'agent' ? 'blue' : 'gray'}>
                              {user.role}
                            </Badge>
                          </Td>
                          <Td>
                            <Badge colorScheme={user.active ? 'green' : 'red'}>
                              {user.active ? 'Active' : 'Inactive'}
                            </Badge>
                          </Td>
                          <Td>
                            <Badge colorScheme={user.verified ? 'green' : 'orange'}>
                              {user.verified ? 'Verified' : 'Not Verified'}
                            </Badge>
                          </Td>
                          <Td>
                            <HStack wrap="wrap" spacing={1}>
                              {user.tags.map((tag) => (
                                <Tag key={tag} size="sm" colorScheme="blue">
                                  {tag}
                                </Tag>
                              ))}
                            </HStack>
                          </Td>
                          <Td>
                            <Menu>
                              <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                              <MenuList>
                                <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                                <MenuItem icon={<EditIcon />}>Edit User</MenuItem>
                                <MenuItem icon={<DeleteIcon />}>Delete User</MenuItem>
                              </MenuList>
                            </Menu>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Groups Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <HStack justify="space-between" w="full">
                  <Heading size="lg">Groups</Heading>
                  <Button
                    colorScheme="red"
                    onClick={() => setIsGroupModalOpen(true)}
                    leftIcon={<AddIcon />}
                  >
                    Add Group
                  </Button>
                </HStack>

                <SimpleGrid columns={2} spacing={4} w="full">
                  {groups.map((group) => (
                    <Card key={group.id} borderWidth={1} borderColor="gray.200">
                      <CardBody>
                        <VStack align="start" spacing={4}>
                          <VStack align="start" spacing={2}>
                            <Heading size="sm">{group.name}</Heading>
                            {group.description && (
                              <Text color="gray.600" fontSize="sm">
                                {group.description}
                              </Text>
                            )}
                          </VStack>
                          <HStack spacing={2}>
                            <Badge colorScheme={group.is_public ? 'blue' : 'gray'}>
                              {group.is_public ? 'Public' : 'Private'}
                            </Badge>
                            {group.default && (
                              <Badge colorScheme="green">Default</Badge>
                            )}
                          </HStack>
                          <HStack spacing={2}>
                            <Button size="sm" variant="outline">
                              <EditIcon mr={1} /> Edit
                            </Button>
                            <Button size="sm" variant="outline" colorScheme="red">
                              <DeleteIcon mr={1} /> Delete
                            </Button>
                          </HStack>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Organizations Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <Heading size="lg">Organizations</Heading>

                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Name</Th>
                        <Th>Domain Names</Th>
                        <Th>Shared Tickets</Th>
                        <Th>Tags</Th>
                        <Th>Created</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {organizations.map((org) => (
                        <Tr key={org.id}>
                          <Td>
                            <Text fontWeight="medium">{org.name}</Text>
                          </Td>
                          <Td>
                            <HStack wrap="wrap" spacing={1}>
                              {org.domain_names?.map((domain) => (
                                <Tag key={domain} size="sm" colorScheme="blue">
                                  {domain}
                                </Tag>
                              ))}
                            </HStack>
                          </Td>
                          <Td>
                            <Badge colorScheme={org.shared_tickets ? 'green' : 'red'}>
                              {org.shared_tickets ? 'Enabled' : 'Disabled'}
                            </Badge>
                          </Td>
                          <Td>
                            <HStack wrap="wrap" spacing={1}>
                              {org.tags.map((tag) => (
                                <Tag key={tag} size="sm" colorScheme="gray">
                                  {tag}
                                </Tag>
                              ))}
                            </HStack>
                          </Td>
                          <Td>{formatDate(org.created_at)}</Td>
                          <Td>
                            <Menu>
                              <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                              <MenuList>
                                <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                                <MenuItem icon={<EditIcon />}>Edit Organization</MenuItem>
                                <MenuItem icon={<DeleteIcon />}>Delete Organization</MenuItem>
                              </MenuList>
                            </Menu>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Ticket Modal */}
        <Modal isOpen={isTicketModalOpen} onClose={() => setIsTicketModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Ticket</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Subject</FormLabel>
                  <Input
                    value={ticketForm.subject}
                    onChange={(e) => setTicketForm({ ...ticketForm, subject: e.target.value })}
                    placeholder="Enter ticket subject"
                  />
                </FormControl>
                <FormControl isRequired>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={ticketForm.description}
                    onChange={(e) => setTicketForm({ ...ticketForm, description: e.target.value })}
                    placeholder="Enter detailed description"
                    rows={4}
                  />
                </FormControl>
                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Type</FormLabel>
                    <Select
                      value={ticketForm.type}
                      onChange={(e) => setTicketForm({ ...ticketForm, type: e.target.value })}
                    >
                      <option value="question">Question</option>
                      <option value="incident">Incident</option>
                      <option value="problem">Problem</option>
                      <option value="task">Task</option>
                    </Select>
                  </FormControl>
                  <FormControl>
                    <FormLabel>Priority</FormLabel>
                    <Select
                      value={ticketForm.priority}
                      onChange={(e) => setTicketForm({ ...ticketForm, priority: e.target.value })}
                    >
                      <option value="urgent">Urgent</option>
                      <option value="high">High</option>
                      <option value="normal">Normal</option>
                      <option value="low">Low</option>
                    </Select>
                  </FormControl>
                </HStack>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsTicketModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={handleCreateTicket}
                isLoading={loading}
              >
                Create Ticket
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* User Modal */}
        <Modal isOpen={isUserModalOpen} onClose={() => setIsUserModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New User</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Name</FormLabel>
                  <Input
                    value={userForm.name}
                    onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
                    placeholder="Enter user name"
                  />
                </FormControl>
                <FormControl isRequired>
                  <FormLabel>Email</FormLabel>
                  <Input
                    type="email"
                    value={userForm.email}
                    onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                    placeholder="Enter user email"
                  />
                </FormControl>
                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Role</FormLabel>
                    <Select
                      value={userForm.role}
                      onChange={(e) => setUserForm({ ...userForm, role: e.target.value })}
                    >
                      <option value="end-user">End User</option>
                      <option value="agent">Agent</option>
                      <option value="admin">Admin</option>
                    </Select>
                  </FormControl>
                  <FormControl>
                    <FormLabel>Phone</FormLabel>
                    <Input
                      value={userForm.phone}
                      onChange={(e) => setUserForm({ ...userForm, phone: e.target.value })}
                      placeholder="Enter phone number"
                    />
                  </FormControl>
                </HStack>
                <FormControl>
                  <FormLabel>Notes</FormLabel>
                  <Textarea
                    value={userForm.notes}
                    onChange={(e) => setUserForm({ ...userForm, notes: e.target.value })}
                    placeholder="Enter user notes"
                    rows={3}
                  />
                </FormControl>
                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Active</FormLabel>
                    <Switch
                      isChecked={userForm.active}
                      onChange={(e) => setUserForm({ ...userForm, active: e.target.checked })}
                    />
                  </FormControl>
                  <FormControl>
                    <FormLabel>Verified</FormLabel>
                    <Switch
                      isChecked={userForm.verified}
                      onChange={(e) => setUserForm({ ...userForm, verified: e.target.checked })}
                    />
                  </FormControl>
                </HStack>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsUserModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={handleCreateUser}
                isLoading={loading}
              >
                Create User
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Group Modal */}
        <Modal isOpen={isGroupModalOpen} onClose={() => setIsGroupModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Group</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Group Name</FormLabel>
                  <Input
                    value={groupForm.name}
                    onChange={(e) => setGroupForm({ ...groupForm, name: e.target.value })}
                    placeholder="Enter group name"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={groupForm.description}
                    onChange={(e) => setGroupForm({ ...groupForm, description: e.target.value })}
                    placeholder="Enter group description"
                    rows={3}
                  />
                </FormControl>
                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Public</FormLabel>
                    <Switch
                      isChecked={groupForm.is_public}
                      onChange={(e) => setGroupForm({ ...groupForm, is_public: e.target.checked })}
                    />
                  </FormControl>
                  <FormControl>
                    <FormLabel>Default</FormLabel>
                    <Switch
                      isChecked={groupForm.default}
                      onChange={(e) => setGroupForm({ ...groupForm, default: e.target.checked })}
                    />
                  </FormControl>
                </HStack>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsGroupModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="red"
                onClick={handleCreateGroup}
                isLoading={loading}
              >
                Create Group
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default ZendeskIntegration;