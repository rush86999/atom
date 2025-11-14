/**
 * Zendesk Integration Page
 * Complete Zendesk customer support and help desk integration
 */

import React, { useState, useEffect } from "react";
import {
  Box as ChakraBox,
  VStack,
  HStack,
  Text,
  Button,
  Heading,
  Card,
  CardBody,
  CardHeader,
  Badge,
  Icon,
  useToast,
  SimpleGrid,
  Divider,
  useColorModeValue,
  Stack,
  Flex,
  Spacer,
  Input,
  Select,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
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
  useDisclosure,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
  Tag,
  TagLabel,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Avatar,
  Spinner,
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  Menu,
  MenuButton,
  MenuList,
  MenuItem,
  Checkbox,
  RadioGroup,
  Radio,
} from "@chakra-ui/react";
import {
  SettingsIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  RepeatIcon,
  TimeIcon,
  StarIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ChatIcon,
  EmailIcon,
  CalendarIcon,
  PhoneIcon,
  FileIcon,
  DownloadIcon,
  ExternalLinkIcon,
  WarningIcon,
  QuestionIcon,
} from "@chakra-ui/icons";

interface ZendeskTicket {
  id: number;
  url: string;
  external_id?: string;
  type: string;
  subject: string;
  raw_subject?: string;
  description: string;
  priority: string;
  status: string;
  recipient?: string;
  requester_id: number;
  requester?: {
    id: number;
    name: string;
    email: string;
    locale?: string;
    timezone?: string;
    user_fields?: any;
    role?: string;
    verified?: boolean;
    active?: boolean;
    phone?: string;
    photo?: {
      thumbnails?: Array<{
        url: string;
        id: string;
        file_name: string;
        content_url: string;
        content_type: string;
        size: number;
        width?: number;
        height?: number;
        inline?: boolean;
      }>;
    };
    organization_id?: number;
    organization?: {
      id: number;
      name: string;
      created_at: string;
      updated_at: string;
      domain_names?: string[];
      tags?: string[];
      organization_fields?: any;
      shared_tickets?: boolean;
      shared_comments?: boolean;
      external_id?: string;
    };
  };
  submitter_id?: number;
  assignee_id?: number;
  assignee?: {
    id: number;
    name: string;
    email: string;
    created_at: string;
    updated_at: string;
    active: boolean;
    verified: boolean;
    shared: boolean;
    shared_agent: boolean;
    photo?: {
      thumbnails?: Array<{
        url: string;
        id: string;
        file_name: string;
        content_url: string;
        content_type: string;
        size: number;
        width?: number;
        height?: number;
        inline?: boolean;
      }>;
    };
  };
  group_id?: number;
  group?: {
    id: number;
    name: string;
    description?: string;
    created_at: string;
    updated_at: string;
    url: string;
    deleted: boolean;
  };
  collaborator_ids?: number[];
  collaborators?: Array<{
    id: number;
    name: string;
    email: string;
    locale?: string;
    timezone?: string;
    user_fields?: any;
    role?: string;
    verified?: boolean;
    active?: boolean;
    phone?: string;
    photo?: {
      thumbnails?: Array<{
        url: string;
        id: string;
        file_name: string;
        content_url: string;
        content_type: string;
        size: number;
        width?: number;
        height?: number;
        inline?: boolean;
      }>;
    };
  }>;
  forum_topic_id?: number;
  problem_id?: number;
  has_incidents?: boolean;
  is_public?: boolean;
  due_at?: string;
  tags?: string[];
  via: {
    channel: string;
    source: {
      from: any;
      to: any;
      rel?: string;
    };
  };
  custom_fields?: Array<{
    id: number;
    value: any;
  }>;
  satisfaction_rating?: {
    id: number;
    score: string;
    comment?: string;
    created_at: string;
  };
  sharing_agreement_ids?: number[];
  followup_ids?: number[];
  ticket_form_id?: number;
  brand_id?: number;
  created_at: string;
  updated_at: string;
}

interface ZendeskUser {
  id: number;
  url: string;
  name: string;
  email: string;
  created_at: string;
  updated_at: string;
  active: boolean;
  verified: boolean;
  shared: boolean;
  shared_agent: boolean;
  locale: string;
  timezone: string;
  phone?: string;
  signature?: string;
  details?: string;
  notes?: string;
  photo?: {
    thumbnails?: Array<{
      url: string;
      id: string;
      file_name: string;
      content_url: string;
      content_type: string;
      size: number;
      width?: number;
      height?: number;
      inline?: boolean;
    }>;
  };
  organization_id?: number;
  organization?: {
    id: number;
    name: string;
    created_at: string;
    updated_at: string;
    domain_names?: string[];
    tags?: string[];
    organization_fields?: any;
    shared_tickets?: boolean;
    shared_comments?: boolean;
    external_id?: string;
  };
  role: string;
  custom_role_id?: number;
  tags: string[];
  suspended?: boolean;
  last_login_at?: string;
  two_factor_auth_enabled?: boolean;
  user_fields?: any;
}

interface ZendeskGroup {
  id: number;
  url: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  deleted: boolean;
}

interface ZendeskView {
  id: number;
  url: string;
  title: string;
  active: boolean;
  position: number;
  description?: string;
  created_at: string;
  updated_at: string;
  conditions: {
    all: Array<{
      field: string;
      operator: string;
      value: any;
    }>;
    any: Array<{
      field: string;
      operator: string;
      value: any;
    }>;
  };
  execution: {
    order: Array<{
      field: string;
      direction: string;
    }>;
    group_by?: Array<{
      field: string;
      direction: string;
    }>;
    group_count?: number;
    group_custom_field?: number;
    sort_by?: string;
    sort_order?: string;
  };
  columns: Array<{
    id: number;
    title: string;
    type: string;
    field: string;
    width?: number;
  }>;
  restrictions?: {
    group_ids?: number[];
    user_ids?: number[];
  };
}

interface ZendeskOrganization {
  id: number;
  url: string;
  name: string;
  created_at: string;
  updated_at: string;
  domain_names: string[];
  tags: string[];
  organization_fields?: any;
  shared_tickets: boolean;
  shared_comments: boolean;
  external_id?: string;
  details?: string;
  notes?: string;
  group_id?: number;
}

const ZendeskIntegration: React.FC = () => {
  const [tickets, setTickets] = useState<ZendeskTicket[]>([]);
  const [users, setUsers] = useState<ZendeskUser[]>([]);
  const [groups, setGroups] = useState<ZendeskGroup[]>([]);
  const [views, setViews] = useState<ZendeskView[]>([]);
  const [organizations, setOrganizations] = useState<ZendeskOrganization[]>([]);
  const [userProfile, setUserProfile] = useState<ZendeskUser | null>(null);
  const [loading, setLoading] = useState({
    tickets: false,
    users: false,
    groups: false,
    views: false,
    organizations: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [selectedPriority, setSelectedPriority] = useState("");

  // Form states
  const [ticketForm, setTicketForm] = useState({
    subject: "",
    description: "",
    priority: "normal",
    type: "question",
    status: "new",
    requester_id: "",
    assignee_id: "",
    group_id: "",
    tags: [] as string[],
    due_at: "",
  });

  const [userForm, setUserForm] = useState({
    name: "",
    email: "",
    phone: "",
    role: "end-user",
    organization_id: "",
    verified: false,
    suspended: false,
    tags: [] as string[],
  });

  const [organizationForm, setOrganizationForm] = useState({
    name: "",
    domain_names: [] as string[],
    tags: [] as string[],
    shared_tickets: false,
    shared_comments: false,
    notes: "",
  });

  const {
    isOpen: isTicketOpen,
    onOpen: onTicketOpen,
    onClose: onTicketClose,
  } = useDisclosure();
  const {
    isOpen: isUserOpen,
    onOpen: onUserOpen,
    onClose: onUserClose,
  } = useDisclosure();
  const {
    isOpen: isOrganizationOpen,
    onOpen: onOrganizationOpen,
    onClose: onOrganizationClose,
  } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/zendesk/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadUserProfile();
        loadTickets();
        loadUsers();
        loadGroups();
        loadViews();
        loadOrganizations();
      } else {
        setConnected(false);
        setHealthStatus("error");
      }
    } catch (error) {
      console.error("Health check failed:", error);
      setConnected(false);
      setHealthStatus("error");
    }
  };

  // Load Zendesk data
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/zendesk/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setUserProfile(data.data?.profile || null);
      }
    } catch (error) {
      console.error("Failed to load user profile:", error);
    } finally {
      setLoading((prev) => ({ ...prev, profile: false }));
    }
  };

  const loadTickets = async () => {
    setLoading((prev) => ({ ...prev, tickets: true }));
    try {
      const response = await fetch("/api/integrations/zendesk/tickets", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
          status: selectedStatus || "",
          priority: selectedPriority || "",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setTickets(data.data?.tickets || []);
      }
    } catch (error) {
      console.error("Failed to load tickets:", error);
      toast({
        title: "Error",
        description: "Failed to load tickets from Zendesk",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, tickets: false }));
    }
  };

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/zendesk/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setUsers(data.data?.users || []);
      }
    } catch (error) {
      console.error("Failed to load users:", error);
    } finally {
      setLoading((prev) => ({ ...prev, users: false }));
    }
  };

  const loadGroups = async () => {
    setLoading((prev) => ({ ...prev, groups: true }));
    try {
      const response = await fetch("/api/integrations/zendesk/groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setGroups(data.data?.groups || []);
      }
    } catch (error) {
      console.error("Failed to load groups:", error);
    } finally {
      setLoading((prev) => ({ ...prev, groups: false }));
    }
  };

  const loadViews = async () => {
    setLoading((prev) => ({ ...prev, views: true }));
    try {
      const response = await fetch("/api/integrations/zendesk/views", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setViews(data.data?.views || []);
      }
    } catch (error) {
      console.error("Failed to load views:", error);
    } finally {
      setLoading((prev) => ({ ...prev, views: false }));
    }
  };

  const loadOrganizations = async () => {
    setLoading((prev) => ({ ...prev, organizations: true }));
    try {
      const response = await fetch("/api/integrations/zendesk/organizations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setOrganizations(data.data?.organizations || []);
      }
    } catch (error) {
      console.error("Failed to load organizations:", error);
    } finally {
      setLoading((prev) => ({ ...prev, organizations: false }));
    }
  };

  // Create operations
  const createTicket = async () => {
    if (!ticketForm.subject || !ticketForm.description) return;

    try {
      const response = await fetch("/api/integrations/zendesk/tickets/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          ticket: {
            subject: ticketForm.subject,
            description: ticketForm.description,
            priority: ticketForm.priority,
            type: ticketForm.type,
            status: ticketForm.status,
            requester_id: parseInt(ticketForm.requester_id) || undefined,
            assignee_id: parseInt(ticketForm.assignee_id) || undefined,
            group_id: parseInt(ticketForm.group_id) || undefined,
            tags: ticketForm.tags,
            due_at: ticketForm.due_at || undefined,
          },
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Ticket created successfully",
          status: "success",
          duration: 3000,
        });
        onTicketClose();
        setTicketForm({
          subject: "",
          description: "",
          priority: "normal",
          type: "question",
          status: "new",
          requester_id: "",
          assignee_id: "",
          group_id: "",
          tags: [],
          due_at: "",
        });
        loadTickets();
      }
    } catch (error) {
      console.error("Failed to create ticket:", error);
      toast({
        title: "Error",
        description: "Failed to create ticket",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createUser = async () => {
    if (!userForm.name || !userForm.email) return;

    try {
      const response = await fetch("/api/integrations/zendesk/users/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          user: {
            name: userForm.name,
            email: userForm.email,
            phone: userForm.phone || undefined,
            role: userForm.role,
            organization_id: parseInt(userForm.organization_id) || undefined,
            verified: userForm.verified,
            suspended: userForm.suspended,
            tags: userForm.tags,
          },
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "User created successfully",
          status: "success",
          duration: 3000,
        });
        onUserClose();
        setUserForm({
          name: "",
          email: "",
          phone: "",
          role: "end-user",
          organization_id: "",
          verified: false,
          suspended: false,
          tags: [],
        });
        loadUsers();
      }
    } catch (error) {
      console.error("Failed to create user:", error);
      toast({
        title: "Error",
        description: "Failed to create user",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createOrganization = async () => {
    if (!organizationForm.name) return;

    try {
      const response = await fetch("/api/integrations/zendesk/organizations/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          organization: {
            name: organizationForm.name,
            domain_names: organizationForm.domain_names,
            tags: organizationForm.tags,
            shared_tickets: organizationForm.shared_tickets,
            shared_comments: organizationForm.shared_comments,
            notes: organizationForm.notes || undefined,
          },
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Organization created successfully",
          status: "success",
          duration: 3000,
        });
        onOrganizationClose();
        setOrganizationForm({
          name: "",
          domain_names: [],
          tags: [],
          shared_tickets: false,
          shared_comments: false,
          notes: "",
        });
        loadOrganizations();
      }
    } catch (error) {
      console.error("Failed to create organization:", error);
      toast({
        title: "Error",
        description: "Failed to create organization",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredTickets = tickets.filter(
    (ticket) =>
      ticket.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      ticket.requester?.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredUsers = users.filter(
    (user) =>
      user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredOrganizations = organizations.filter(
    (org) =>
      org.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      org.domain_names.some(domain => domain.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  // Stats calculations
  const totalTickets = tickets.length;
  const openTickets = tickets.filter(t => ["new", "open", "pending"].includes(t.status)).length;
  const solvedTickets = tickets.filter(t => t.status === "solved").length;
  const urgentTickets = tickets.filter(t => t.priority === "urgent").length;
  const totalUsers = users.length;
  const activeUsers = users.filter(u => u.active).length;
  const totalOrganizations = organizations.length;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadUserProfile();
      loadTickets();
      loadUsers();
      loadGroups();
      loadViews();
      loadOrganizations();
    }
  }, [connected]);

  useEffect(() => {
    if (connected) {
      loadTickets();
    }
  }, [selectedStatus, selectedPriority]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const getStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case "new":
        return "blue";
      case "open":
        return "orange";
      case "pending":
        return "yellow";
      case "solved":
        return "green";
      case "closed":
        return "gray";
      case "hold":
        return "red";
      default:
        return "gray";
    }
  };

  const getPriorityColor = (priority: string): string => {
    switch (priority?.toLowerCase()) {
      case "urgent":
        return "red";
      case "high":
        return "orange";
      case "normal":
        return "yellow";
      case "low":
        return "blue";
      default:
        return "gray";
    }
  };

  const getTypeColor = (type: string): string => {
    switch (type?.toLowerCase()) {
      case "question":
        return "blue";
      case "incident":
        return "red";
      case "problem":
        return "orange";
      case "task":
        return "green";
      default:
        return "gray";
    }
  };

  const getRoleColor = (role: string): string => {
    switch (role?.toLowerCase()) {
      case "admin":
        return "red";
      case "agent":
        return "blue";
      case "end-user":
        return "gray";
      default:
        return "gray";
    }
  };

  const getViaColor = (via: string): string => {
    switch (via?.toLowerCase()) {
      case "web":
        return "blue";
      case "email":
        return "green";
      case "api":
        return "purple";
      case "voice":
        return "orange";
      case "chat":
        return "pink";
      default:
        return "gray";
    }
  };

  return (
    <ChakraBox minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={SettingsIcon} w={8} h={8} color="#03363D" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Zendesk Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Customer support and help desk platform
              </Text>
            </VStack>
          </HStack>

          <HStack spacing={4}>
            <Badge
              colorScheme={healthStatus === "healthy" ? "green" : "red"}
              display="flex"
              alignItems="center"
            >
              {healthStatus === "healthy" ? (
                <CheckCircleIcon mr={1} />
              ) : (
                <WarningTwoIcon mr={1} />
              )}
              {connected ? "Connected" : "Disconnected"}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RepeatIcon />}
              onClick={checkConnection}
            >
              Refresh Status
            </Button>
          </HStack>

          {userProfile && (
            <HStack spacing={4}>
              <Avatar
                src={userProfile.photo?.thumbnails?.[0]?.url}
                name={userProfile.name}
              />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">{userProfile.name}</Text>
                <Text fontSize="sm" color="gray.600">
                  {userProfile.email} • {userProfile.role}
                </Text>
              </VStack>
            </HStack>
          )}
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={SettingsIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Zendesk</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Zendesk account to start managing customer support tickets
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/zendesk/auth/start")
                  }
                >
                  Connect Zendesk Account
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Services Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Tickets</StatLabel>
                    <StatNumber>{totalTickets}</StatNumber>
                    <StatHelpText>{openTickets} open</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Solved</StatLabel>
                    <StatNumber>{solvedTickets}</StatNumber>
                    <StatHelpText>Completed tickets</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Users</StatLabel>
                    <StatNumber>{activeUsers}</StatNumber>
                    <StatHelpText>{totalUsers} total</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Organizations</StatLabel>
                    <StatNumber>{totalOrganizations}</StatNumber>
                    <StatHelpText>Support orgs</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Tickets</Tab>
                <Tab>Users</Tab>
                <Tab>Groups</Tab>
                <Tab>Views</Tab>
                <Tab>Organizations</Tab>
              </TabList>

              <TabPanels>
                {/* Tickets Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Filter by status"
                        value={selectedStatus}
                        onChange={(e) => setSelectedStatus(e.target.value)}
                        width="150px"
                      >
                        <option value="">All Status</option>
                        <option value="new">New</option>
                        <option value="open">Open</option>
                        <option value="pending">Pending</option>
                        <option value="solved">Solved</option>
                        <option value="closed">Closed</option>
                        <option value="hold">Hold</option>
                      </Select>
                      <Select
                        placeholder="Filter by priority"
                        value={selectedPriority}
                        onChange={(e) => setSelectedPriority(e.target.value)}
                        width="150px"
                      >
                        <option value="">All Priority</option>
                        <option value="urgent">Urgent</option>
                        <option value="high">High</option>
                        <option value="normal">Normal</option>
                        <option value="low">Low</option>
                      </Select>
                      <Input
                        placeholder="Search tickets..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onTicketOpen}
                      >
                        Create Ticket
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>ID</Th>
                                <Th>Subject</Th>
                                <Th>Requester</Th>
                                <Th>Status</Th>
                                <Th>Priority</Th>
                                <Th>Type</Th>
                                <Th>Created</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.tickets ? (
                                <Tr><Td colSpan={8}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                filteredTickets.map((ticket) => (
                                  <Tr key={ticket.id}>
                                    <Td>
                                      <Text fontWeight="bold">#{ticket.id}</Text>
                                    </Td>
                                    <Td>
                                      <VStack align="start" spacing={1}>
                                        <Text
                                          fontWeight="medium"
                                          cursor="pointer"
                                          color="blue.600"
                                          _hover={{ color: "blue.700" }}
                                          onClick={() => window.open(ticket.url, "_blank")}
                                        >
                                          {ticket.subject}
                                        </Text>
                                        {ticket.via && (
                                          <Tag colorScheme={getViaColor(ticket.via.channel)} size="sm">
                                            {ticket.via.channel}
                                          </Tag>
                                        )}
                                      </VStack>
                                    </Td>
                                    <Td>
                                      <HStack>
                                        {ticket.requester?.photo?.thumbnails?.[0]?.url && (
                                          <Avatar
                                            src={ticket.requester.photo.thumbnails[0].url}
                                            name={ticket.requester.name}
                                            size="sm"
                                          />
                                        )}
                                        <Text>{ticket.requester?.name}</Text>
                                      </HStack>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={getStatusColor(ticket.status)} size="sm">
                                        {ticket.status}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={getPriorityColor(ticket.priority)} size="sm">
                                        {ticket.priority}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={getTypeColor(ticket.type)} size="sm">
                                        {ticket.type}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {formatDate(ticket.created_at)}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <HStack>
                                        <Button size="sm" variant="outline" leftIcon={<ViewIcon />}>
                                          Details
                                        </Button>
                                      </HStack>
                                    </Td>
                                  </Tr>
                                ))
                              )}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Users Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search users..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onUserOpen}
                      >
                        Create User
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.users ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredUsers.map((user) => (
                          <Card key={user.id}>
                            <CardBody>
                              <HStack spacing={4}>
                                <Avatar
                                  src={user.photo?.thumbnails?.[0]?.url}
                                  name={user.name}
                                  size="lg"
                                />
                                <VStack align="start" spacing={1} flex={1}>
                                  <Text fontWeight="bold">{user.name}</Text>
                                  <Text fontSize="sm" color="gray.600">
                                    {user.email}
                                  </Text>
                                  <HStack spacing={2}>
                                    <Tag colorScheme={getRoleColor(user.role)} size="sm">
                                      {user.role}
                                    </Tag>
                                    <Tag colorScheme={user.active ? "green" : "red"} size="sm">
                                      {user.active ? "Active" : "Inactive"}
                                    </Tag>
                                  </HStack>
                                  {user.organization && (
                                    <Text fontSize="xs" color="gray.500">
                                      {user.organization.name}
                                    </Text>
                                  )}
                                  {user.phone && (
                                    <Text fontSize="xs" color="gray.500">
                                      📞 {user.phone}
                                    </Text>
                                  )}
                                </VStack>
                              </HStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>

                {/* Groups Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>ID</Th>
                                <Th>Name</Th>
                                <Th>Description</Th>
                                <Th>Created</Th>
                                <Th>Updated</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.groups ? (
                                <Tr><Td colSpan={5}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                groups.map((group) => (
                                  <Tr key={group.id}>
                                    <Td>
                                      <Text fontWeight="bold">#{group.id}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontWeight="medium">{group.name}</Text>
                                    </Td>
                                    <Td>{group.description}</Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {formatDate(group.created_at)}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {formatDate(group.updated_at)}
                                      </Text>
                                    </Td>
                                  </Tr>
                                ))
                              )}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Views Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Title</Th>
                                <Th>Description</Th>
                                <Th>Status</Th>
                                <Th>Created</Th>
                                <Th>Updated</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.views ? (
                                <Tr><Td colSpan={5}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                views.map((view) => (
                                  <Tr key={view.id}>
                                    <Td>
                                      <Text fontWeight="medium">{view.title}</Text>
                                    </Td>
                                    <Td>{view.description}</Td>
                                    <Td>
                                      <Tag colorScheme={view.active ? "green" : "red"} size="sm">
                                        {view.active ? "Active" : "Inactive"}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {formatDate(view.created_at)}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {formatDate(view.updated_at)}
                                      </Text>
                                    </Td>
                                  </Tr>
                                ))
                              )}
                            </Tbody>
                          </Table>
                        </TableContainer>
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Organizations Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search organizations..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onOrganizationOpen}
                      >
                        Create Organization
                      </Button>
                    </HStack>

                    <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} spacing={6}>
                      {loading.organizations ? (
                        <Spinner size="xl" />
                      ) : (
                        filteredOrganizations.map((org) => (
                          <Card key={org.id}>
                            <CardBody>
                              <VStack align="start" spacing={2}>
                                <Text fontWeight="bold" fontSize="lg">
                                  {org.name}
                                </Text>
                                {org.domain_names.length > 0 && (
                                  <HStack wrap="wrap">
                                    {org.domain_names.map((domain, index) => (
                                      <Tag key={index} size="sm" colorScheme="gray">
                                        {domain}
                                      </Tag>
                                    ))}
                                  </HStack>
                                )}
                                <HStack spacing={2}>
                                  {org.shared_tickets && (
                                    <Tag size="sm" colorScheme="blue">
                                      Shared Tickets
                                    </Tag>
                                  )}
                                  {org.shared_comments && (
                                    <Tag size="sm" colorScheme="green">
                                      Shared Comments
                                    </Tag>
                                  )}
                                </HStack>
                                {org.tags.length > 0 && (
                                  <HStack wrap="wrap">
                                    {org.tags.map((tag, index) => (
                                      <Tag key={index} size="sm" colorScheme="gray">
                                        {tag}
                                      </Tag>
                                    ))}
                                  </HStack>
                                )}
                                <Text fontSize="xs" color="gray.500">
                                  Created: {formatDate(org.created_at)}
                                </Text>
                              </VStack>
                            </CardBody>
                          </Card>
                        ))
                      )}
                    </SimpleGrid>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Ticket Modal */}
            <Modal isOpen={isTicketOpen} onClose={onTicketClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Ticket</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Subject</FormLabel>
                      <Input
                        placeholder="Ticket subject"
                        value={ticketForm.subject}
                        onChange={(e) =>
                          setTicketForm({
                            ...ticketForm,
                            subject: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Ticket description"
                        value={ticketForm.description}
                        onChange={(e) =>
                          setTicketForm({
                            ...ticketForm,
                            description: e.target.value,
                          })
                        }
                        rows={6}
                      />
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Type</FormLabel>
                        <Select
                          value={ticketForm.type}
                          onChange={(e) =>
                            setTicketForm({
                              ...ticketForm,
                              type: e.target.value,
                            })
                          }
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
                          onChange={(e) =>
                            setTicketForm({
                              ...ticketForm,
                              priority: e.target.value,
                            })
                          }
                        >
                          <option value="urgent">Urgent</option>
                          <option value="high">High</option>
                          <option value="normal">Normal</option>
                          <option value="low">Low</option>
                        </Select>
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Requester</FormLabel>
                        <Select
                          value={ticketForm.requester_id}
                          onChange={(e) =>
                            setTicketForm({
                              ...ticketForm,
                              requester_id: e.target.value,
                            })
                          }
                        >
                          <option value="">Select User</option>
                          {users.map((user) => (
                            <option key={user.id} value={user.id}>
                              {user.name} ({user.email})
                            </option>
                          ))}
                        </Select>
                      </FormControl>

                      <FormControl>
                        <FormLabel>Assignee</FormLabel>
                        <Select
                          value={ticketForm.assignee_id}
                          onChange={(e) =>
                            setTicketForm({
                              ...ticketForm,
                              assignee_id: e.target.value,
                            })
                          }
                        >
                          <option value="">Select Agent</option>
                          {users.filter(u => u.role === "agent" || u.role === "admin").map((user) => (
                            <option key={user.id} value={user.id}>
                              {user.name} ({user.email})
                            </option>
                          ))}
                        </Select>
                      </FormControl>
                    </HStack>

                    <FormControl>
                      <FormLabel>Due Date</FormLabel>
                      <Input
                        type="datetime-local"
                        value={ticketForm.due_at}
                        onChange={(e) =>
                          setTicketForm({
                            ...ticketForm,
                            due_at: e.target.value,
                          })
                        }
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onTicketClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createTicket}
                    disabled={!ticketForm.subject || !ticketForm.description}
                  >
                    Create Ticket
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create User Modal */}
            <Modal isOpen={isUserOpen} onClose={onUserClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create User</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <HStack spacing={4} width="full">
                      <FormControl isRequired>
                        <FormLabel>Name</FormLabel>
                        <Input
                          placeholder="User name"
                          value={userForm.name}
                          onChange={(e) =>
                            setUserForm({
                              ...userForm,
                              name: e.target.value,
                            })
                          }
                        />
                      </FormControl>

                      <FormControl isRequired>
                        <FormLabel>Email</FormLabel>
                        <Input
                          type="email"
                          placeholder="user@example.com"
                          value={userForm.email}
                          onChange={(e) =>
                            setUserForm({
                              ...userForm,
                              email: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Role</FormLabel>
                        <Select
                          value={userForm.role}
                          onChange={(e) =>
                            setUserForm({
                              ...userForm,
                              role: e.target.value,
                            })
                          }
                        >
                          <option value="end-user">End User</option>
                          <option value="agent">Agent</option>
                          <option value="admin">Admin</option>
                        </Select>
                      </FormControl>

                      <FormControl>
                        <FormLabel>Phone</FormLabel>
                        <Input
                          placeholder="Phone number"
                          value={userForm.phone}
                          onChange={(e) =>
                            setUserForm({
                              ...userForm,
                              phone: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <FormControl>
                      <FormLabel>Organization</FormLabel>
                      <Select
                        value={userForm.organization_id}
                        onChange={(e) =>
                          setUserForm({
                            ...userForm,
                            organization_id: e.target.value,
                          })
                        }
                      >
                        <option value="">Select Organization</option>
                        {organizations.map((org) => (
                          <option key={org.id} value={org.id}>
                            {org.name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>
                          <Checkbox
                            isChecked={userForm.verified}
                            onChange={(e) =>
                              setUserForm({
                                ...userForm,
                                verified: e.target.checked,
                              })
                            }
                          >
                            Verified
                          </Checkbox>
                        </FormLabel>
                      </FormControl>

                      <FormControl>
                        <FormLabel>
                          <Checkbox
                            isChecked={userForm.suspended}
                            onChange={(e) =>
                              setUserForm({
                                ...userForm,
                                suspended: e.target.checked,
                              })
                            }
                          >
                            Suspended
                          </Checkbox>
                        </FormLabel>
                      </FormControl>
                    </HStack>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onUserClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createUser}
                    disabled={!userForm.name || !userForm.email}
                  >
                    Create User
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Organization Modal */}
            <Modal isOpen={isOrganizationOpen} onClose={onOrganizationClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Organization</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Organization Name</FormLabel>
                      <Input
                        placeholder="Organization name"
                        value={organizationForm.name}
                        onChange={(e) =>
                          setOrganizationForm({
                            ...organizationForm,
                            name: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Domain Names</FormLabel>
                      <Input
                        placeholder="domain1.com, domain2.com"
                        value={organizationForm.domain_names.join(", ")}
                        onChange={(e) =>
                          setOrganizationForm({
                            ...organizationForm,
                            domain_names: e.target.value.split(",").map(s => s.trim()).filter(s => s),
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Notes</FormLabel>
                      <Textarea
                        placeholder="Organization notes"
                        value={organizationForm.notes}
                        onChange={(e) =>
                          setOrganizationForm({
                            ...organizationForm,
                            notes: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>
                          <Checkbox
                            isChecked={organizationForm.shared_tickets}
                            onChange={(e) =>
                              setOrganizationForm({
                                ...organizationForm,
                                shared_tickets: e.target.checked,
                              })
                            }
                          >
                            Shared Tickets
                          </Checkbox>
                        </FormLabel>
                      </FormControl>

                      <FormControl>
                        <FormLabel>
                          <Checkbox
                            isChecked={organizationForm.shared_comments}
                            onChange={(e) =>
                              setOrganizationForm({
                                ...organizationForm,
                                shared_comments: e.target.checked,
                              })
                            }
                          >
                            Shared Comments
                          </Checkbox>
                        </FormLabel>
                      </FormControl>
                    </HStack>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onOrganizationClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createOrganization}
                    disabled={!organizationForm.name}
                  >
                    Create Organization
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}
      </VStack>
    </ChakraBox>
  );
};

export default ZendeskIntegration;