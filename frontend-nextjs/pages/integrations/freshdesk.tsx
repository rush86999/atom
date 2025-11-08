import React, { useState, useEffect } from "react";
import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Flex,
  Grid,
  GridItem,
  Heading,
  Text,
  VStack,
  HStack,
  Badge,
  Input,
  InputGroup,
  InputLeftElement,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatArrow,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalFooter,
  ModalBody,
  ModalCloseButton,
  useDisclosure,
  FormControl,
  FormLabel,
  Textarea,
  Select,
  Tag,
  TagLabel,
  TagCloseButton,
  Icon,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
} from "@chakra-ui/react";
import {
  SearchIcon,
  ChatIcon,
  PhoneIcon,
  EmailIcon,
  CalendarIcon,
  AttachmentIcon,
} from "@chakra-ui/icons";

// Interfaces for Freshdesk data
interface FreshdeskContact {
  id: number;
  name: string;
  email: string;
  phone?: string;
  mobile?: string;
  company_id?: number;
  job_title?: string;
  time_zone?: string;
  language?: string;
  created_at: string;
  updated_at: string;
  last_login_at?: string;
  active: boolean;
  custom_fields?: Record<string, any>;
}

interface FreshdeskTicket {
  id: number;
  subject: string;
  description: string;
  email: string;
  priority: number;
  status: number;
  source: number;
  type?: string;
  responder_id?: number;
  group_id?: number;
  company_id?: number;
  created_at: string;
  updated_at: string;
  due_by?: string;
  fr_due_by?: string;
  is_escalated: boolean;
  custom_fields?: Record<string, any>;
  tags: string[];
}

interface FreshdeskCompany {
  id: number;
  name: string;
  description?: string;
  note?: string;
  domains: string[];
  industry?: string;
  created_at: string;
  updated_at: string;
  custom_fields?: Record<string, any>;
}

interface FreshdeskAgent {
  id: number;
  email: string;
  name: string;
  available: boolean;
  available_since?: string;
  occasional: boolean;
  signature?: string;
  ticket_scope: number;
  group_ids: number[];
  role_ids: number[];
  created_at: string;
  updated_at: string;
  time_zone?: string;
  language?: string;
}

interface FreshdeskGroup {
  id: number;
  name: string;
  description?: string;
  escalated: boolean;
  agent_ids: number[];
  created_at: string;
  updated_at: string;
}

interface FreshdeskStats {
  total_tickets: number;
  open_tickets: number;
  pending_tickets: number;
  resolved_tickets: number;
  closed_tickets: number;
  total_contacts: number;
  total_companies: number;
  total_agents: number;
  total_groups: number;
  avg_first_response_time?: number;
  avg_resolution_time?: number;
  satisfaction_rating?: number;
}

const FreshdeskIntegrationPage: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [contacts, setContacts] = useState<FreshdeskContact[]>([]);
  const [tickets, setTickets] = useState<FreshdeskTicket[]>([]);
  const [companies, setCompanies] = useState<FreshdeskCompany[]>([]);
  const [agents, setAgents] = useState<FreshdeskAgent[]>([]);
  const [groups, setGroups] = useState<FreshdeskGroup[]>([]);
  const [stats, setStats] = useState<FreshdeskStats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");
  const [selectedTicket, setSelectedTicket] = useState<FreshdeskTicket | null>(
    null,
  );
  const [selectedContact, setSelectedContact] =
    useState<FreshdeskContact | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [domain, setDomain] = useState("");

  const {
    isOpen: isConnectModalOpen,
    onOpen: onConnectModalOpen,
    onClose: onConnectModalClose,
  } = useDisclosure();
  const {
    isOpen: isTicketModalOpen,
    onOpen: onTicketModalOpen,
    onClose: onTicketModalClose,
  } = useDisclosure();
  const {
    isOpen: isContactModalOpen,
    onOpen: onContactModalOpen,
    onClose: onContactModalClose,
  } = useDisclosure();
  const {
    isOpen: isCreateTicketModalOpen,
    onOpen: onCreateTicketModalOpen,
    onClose: onCreateTicketModalClose,
  } = useDisclosure();

  const toast = useToast();

  // Load initial data
  useEffect(() => {
    loadFreshdeskData();
  }, []);

  const loadFreshdeskData = async () => {
    try {
      setIsLoading(true);

      // Check connection status
      const healthResponse = await fetch("/api/v1/freshdesk/health");
      if (healthResponse.ok) {
        setIsConnected(true);

        // Load contacts
        const contactsResponse = await fetch(
          "/api/v1/freshdesk/contacts?limit=50",
        );
        if (contactsResponse.ok) {
          const contactsData = await contactsResponse.json();
          setContacts(contactsData.data || []);
        }

        // Load tickets
        const ticketsResponse = await fetch(
          "/api/v1/freshdesk/tickets?limit=50",
        );
        if (ticketsResponse.ok) {
          const ticketsData = await ticketsResponse.json();
          setTickets(ticketsData.data || []);
        }

        // Load companies
        const companiesResponse = await fetch("/api/v1/freshdesk/companies");
        if (companiesResponse.ok) {
          const companiesData = await companiesResponse.json();
          setCompanies(companiesData.data || []);
        }

        // Load agents
        const agentsResponse = await fetch("/api/v1/freshdesk/agents");
        if (agentsResponse.ok) {
          const agentsData = await agentsResponse.json();
          setAgents(agentsData.data || []);
        }

        // Load groups
        const groupsResponse = await fetch("/api/v1/freshdesk/groups");
        if (groupsResponse.ok) {
          const groupsData = await groupsResponse.json();
          setGroups(groupsData.data || []);
        }

        // Load stats
        const statsResponse = await fetch("/api/v1/freshdesk/stats");
        if (statsResponse.ok) {
          const statsData = await statsResponse.json();
          setStats(statsData.data);
        }
      }
    } catch (error) {
      console.error("Failed to load Freshdesk data:", error);
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    if (!apiKey.trim() || !domain.trim()) {
      toast({
        title: "Missing Credentials",
        description: "Please enter both API Key and Domain",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    try {
      const authResponse = await fetch("/api/v1/freshdesk/auth", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          api_key: apiKey,
          domain: domain,
        }),
      });

      if (authResponse.ok) {
        setIsConnected(true);
        onConnectModalClose();

        toast({
          title: "Freshdesk Connected",
          description: "Successfully connected to Freshdesk",
          status: "success",
          duration: 3000,
          isClosable: true,
        });

        await loadFreshdeskData();
      } else {
        throw new Error("Authentication failed");
      }
    } catch (error) {
      toast({
        title: "Connection Failed",
        description: "Failed to connect to Freshdesk",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const searchResponse = await fetch("/api/v1/freshdesk/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: searchQuery,
          type: "ticket",
          limit: 50,
          offset: 0,
        }),
      });

      if (searchResponse.ok) {
        const searchData = await searchResponse.json();
        toast({
          title: "Search Complete",
          description: `Found ${searchData.data.total_count} results`,
          status: "info",
          duration: 2000,
          isClosable: true,
        });
      }
    } catch (error) {
      console.error("Search failed:", error);
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusColor = (status: number): string => {
    switch (status) {
      case 2: // Open
        return "green";
      case 3: // Pending
        return "yellow";
      case 4: // Resolved
        return "blue";
      case 5: // Closed
        return "gray";
      default:
        return "gray";
    }
  };

  const getStatusText = (status: number): string => {
    switch (status) {
      case 2:
        return "Open";
      case 3:
        return "Pending";
      case 4:
        return "Resolved";
      case 5:
        return "Closed";
      default:
        return "Unknown";
    }
  };

  const getPriorityColor = (priority: number): string => {
    switch (priority) {
      case 1:
        return "gray";
      case 2:
        return "blue";
      case 3:
        return "orange";
      case 4:
        return "red";
      default:
        return "gray";
    }
  };

  const getPriorityText = (priority: number): string => {
    switch (priority) {
      case 1:
        return "Low";
      case 2:
        return "Medium";
      case 3:
        return "High";
      case 4:
        return "Urgent";
      default:
        return "Unknown";
    }
  };

  // Render connection status
  if (!isConnected && !isLoading) {
    return (
      <Box p={6}>
        <VStack spacing={6} align="center" justify="center" minH="60vh">
          <Box textAlign="center">
            <Heading size="lg" mb={4}>
              Connect Freshdesk
            </Heading>
            <Text color="gray.600" mb={6}>
              Connect your Freshdesk account to manage customer support tickets,
              contacts, and team collaboration.
            </Text>
          </Box>

          <Card maxW="md" w="full">
            <CardBody>
              <VStack spacing={4}>
                <Box textAlign="center">
                  <Icon as={ChatIcon} w={12} h={12} color="green.500" mb={4} />
                  <Heading size="md">Freshdesk Integration</Heading>
                  <Text color="gray.600" mt={2}>
                    Customer support and help desk platform
                  </Text>
                </Box>

                <Button
                  colorScheme="green"
                  size="lg"
                  w="full"
                  onClick={onConnectModalOpen}
                >
                  Connect Freshdesk
                </Button>
              </VStack>
            </CardBody>
          </Card>
        </VStack>

        {/* Connect Modal */}
        <Modal isOpen={isConnectModalOpen} onClose={onConnectModalClose}>
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Connect Freshdesk</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <Text mb={4}>
                Connect your Freshdesk account using your API key and domain.
              </Text>

              <FormControl mb={4}>
                <FormLabel>Freshdesk Domain</FormLabel>
                <Input
                  placeholder="your-domain"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                />
                <Text fontSize="sm" color="gray.600" mt={1}>
                  Your Freshdesk subdomain (e.g., "company" for
                  company.freshdesk.com)
                </Text>
              </FormControl>

              <FormControl mb={4}>
                <FormLabel>API Key</FormLabel>
                <Input
                  type="password"
                  placeholder="Enter your API key"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
                <Text fontSize="sm" color="gray.600" mt={1}>
                  Find your API key in Freshdesk Admin settings
                </Text>
              </FormControl>

              <Alert status="info" mb={4}>
                <AlertIcon />
                <Box>
                  <AlertTitle>API Authentication</AlertTitle>
                  <AlertDescription>
                    Freshdesk uses API key authentication for secure
                    integration.
                  </AlertDescription>
                </Box>
              </Alert>
            </ModalBody>
            <ModalFooter>
              <Button variant="ghost" mr={3} onClick={onConnectModalClose}>
                Cancel
              </Button>
              <Button colorScheme="green" onClick={handleConnect}>
                Connect
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </Box>
    );
  }

  if (isLoading) {
    return (
      <Box p={6} textAlign="center">
        <Spinner size="xl" />
        <Text mt={4}>Loading Freshdesk data...</Text>
      </Box>
    );
  }

  return (
    <Box p={6}>
      {/* Header */}
      <Flex justify="space-between" align="center" mb={6}>
        <Box>
          <Heading size="lg">Freshdesk</Heading>
          <Text color="gray.600">Customer support and help desk platform</Text>
        </Box>
        <Button colorScheme="green" onClick={loadFreshdeskData}>
          Refresh Data
        </Button>
      </Flex>

      {/* Search Bar */}
      <Card mb={6}>
        <CardBody>
          <InputGroup>
            <InputLeftElement pointerEvents="none">
              <SearchIcon color="gray.300" />
            </InputLeftElement>
            <Input
              placeholder="Search tickets, contacts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            />
          </InputGroup>
        </CardBody>
      </Card>

      {/* Navigation Tabs */}
      <Flex mb={6} borderBottom="1px" borderColor="gray.200">
        {[
          "dashboard",
          "tickets",
          "contacts",
          "companies",
          "agents",
          "groups",
        ].map((tab) => (
          <Button
            key={tab}
            variant="ghost"
            mr={2}
            colorScheme={activeTab === tab ? "green" : "gray"}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </Button>
        ))}
      </Flex>

      {/* Dashboard Tab */}
      {activeTab === "dashboard" && stats && (
        <Grid templateColumns="repeat(4, 1fr)" gap={6} mb={6}>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Tickets</StatLabel>
                  <StatNumber>{stats.total_tickets}</StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
                    15.2%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Open Tickets</StatLabel>
                  <StatNumber>{stats.open_tickets}</StatNumber>
                  <StatHelpText>
                    <StatArrow type="decrease" />
                    8.1%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Response Time</StatLabel>
                  <StatNumber>
                    {stats.avg_first_response_time?.toFixed(1)}h
                  </StatNumber>
                  <StatHelpText>
                    <StatArrow type="decrease" />
                    12.5%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Satisfaction</StatLabel>
                  <StatNumber>
                    {stats.satisfaction_rating?.toFixed(1)}/5
                  </StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
                    3.7%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
        </Grid>
      )}

      {/* Tickets Tab */}
      {activeTab === "tickets" && (
        <Card>
          <CardHeader>
            <Flex justify="space-between" align="center">
              <Heading size="md">Tickets ({tickets.length})</Heading>
              <Button
                colorScheme="green"
                size="sm"
                onClick={onCreateTicketModalOpen}
              >
                Create Ticket
              </Button>
            </Flex>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>ID</Th>
                  <Th>Subject</Th>
                  <Th>Status</Th>
                  <Th>Priority</Th>
                  <Th>Type</Th>
                  <Th>Created</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {tickets.map((ticket) => (
                  <Tr key={ticket.id}>
                    <Td fontWeight="medium">#{ticket.id}</Td>
                    <Td>{ticket.subject}</Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(ticket.status)}>
                        {getStatusText(ticket.status)}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge colorScheme={getPriorityColor(ticket.priority)}>
                        {getPriorityText(ticket.priority)}
                      </Badge>
                    </Td>
                    <Td>{ticket.type || "General"}</Td>
                    <Td>{formatDate(ticket.created_at)}</Td>
                    <Td>
                      <Button
                        size="sm"
                        colorScheme="green"
                        variant="ghost"
                        onClick={() => {
                          setSelectedTicket(ticket);
                          onTicketModalOpen();
                        }}
                      >
                        View
                      </Button>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}

      {/* Contacts Tab */}
      {activeTab === "contacts" && (
        <Card>
          <CardHeader>
            <Heading size="md">Contacts ({contacts.length})</Heading>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>Email</Th>
                  <Th>Phone</Th>
                  <Th>Company</Th>
                  <Th>Last Login</Th>
                  <Th>Status</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {contacts.map((contact) => (
                  <Tr key={contact.id}>
                    <Td fontWeight="medium">{contact.name}</Td>
                    <Td>{contact.email}</Td>
                    <Td>{contact.phone || "-"}</Td>
                    <Td>
                      {contact.company_id
                        ? `Company ${contact.company_id}`
                        : "-"}
                    </Td>
                    <Td>
                      {contact.last_login_at
                        ? formatDate(contact.last_login_at)
                        : "Never"}
                    </Td>
                    <Td>
                      <Badge colorScheme={contact.active ? "green" : "red"}>
                        {contact.active ? "Active" : "Inactive"}
                      </Badge>
                    </Td>
                    <Td>
                      <Button
                        size="sm"
                        colorScheme="green"
                        variant="ghost"
                        onClick={() => {
                          setSelectedContact(contact);
                          onContactModalOpen();
                        }}
                      >
                        View
                      </Button>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}

      {/* Companies Tab */}
      {activeTab === "companies" && (
        <Card>
          <CardHeader>
            <Heading size="md">Companies ({companies.length})</Heading>
          </CardHeader>
          <CardBody>
            <Grid templateColumns="repeat(3, 1fr)" gap={6}>
              {companies.map((company) => (
                <GridItem key={company.id}>
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Heading size="sm">{company.name}</Heading>
                        <Text color="gray.600" fontSize="sm">
                          {company.description}
                        </Text>
                        <Text fontSize="sm">
                          <strong>Domains:</strong> {company.domains.join(", ")}
                        </Text>
                        <Text fontSize="sm">
                          <strong>Industry:</strong>{" "}
                          {company.industry || "Not specified"}
                        </Text>
                        <Text fontSize="sm">
                          Created: {formatDate(company.created_at)}
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                </GridItem>
              ))}
            </Grid>
          </CardBody>
        </Card>
      )}

      {/* Agents Tab */}
      {activeTab === "agents" && (
        <Card>
          <CardHeader>
            <Heading size="md">Agents ({agents.length})</Heading>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>Email</Th>
                  <Th>Status</Th>
                  <Th>Groups</Th>
                  <Th>Created</Th>
                </Tr>
              </Thead>
              <Tbody>
                {agents.map((agent) => (
                  <Tr key={agent.id}>
                    <Td fontWeight="medium">{agent.name}</Td>
                    <Td>{agent.email}</Td>
                    <Td>
                      <Badge colorScheme={agent.available ? "green" : "yellow"}>
                        {agent.available ? "Available" : "Away"}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge colorScheme="blue">
                        {agent.group_ids.length} groups
                      </Badge>
                    </Td>
                    <Td>{formatDate(agent.created_at)}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}

      {/* Groups Tab */}
      {activeTab === "groups" && (
        <Card>
          <CardHeader>
            <Heading size="md">Groups ({groups.length})</Heading>
          </CardHeader>
          <CardBody>
            <Grid templateColumns="repeat(3, 1fr)" gap={6}>
              {groups.map((group) => (
                <GridItem key={group.id}>
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Heading size="sm">{group.name}</Heading>
                        <Text color="gray.600" fontSize="sm">
                          {group.description}
                        </Text>
                        <Badge colorScheme={group.escalated ? "red" : "blue"}>
                          {group.escalated ? "Escalated" : "Normal"}
                        </Badge>
                        <Text fontSize="sm">
                          <strong>Agents:</strong> {group.agent_ids.length}
                        </Text>
                        <Text fontSize="sm">
                          Created: {formatDate(group.created_at)}
                        </Text>
                      </VStack>
                    </CardBody>
                  </Card>
                </GridItem>
              ))}
            </Grid>
          </CardBody>
        </Card>
      )}

      {/* Ticket Detail Modal */}
      <Modal isOpen={isTicketModalOpen} onClose={onTicketModalClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Ticket Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedTicket && (
              <VStack spacing={4} align="start">
                <Box>
                  <Text fontWeight="bold">Ticket ID</Text>
                  <Text>#{selectedTicket.id}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Subject</Text>
                  <Text>{selectedTicket.subject}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Description</Text>
                  <Text>{selectedTicket.description}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Status</Text>
                  <Badge colorScheme={getStatusColor(selectedTicket.status)}>
                    {getStatusText(selectedTicket.status)}
                  </Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold">Priority</Text>
                  <Badge
                    colorScheme={getPriorityColor(selectedTicket.priority)}
                  >
                    {getPriorityText(selectedTicket.priority)}
                  </Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold">Type</Text>
                  <Text>{selectedTicket.type || "General"}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Created</Text>
                  <Text>{formatDate(selectedTicket.created_at)}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Last Updated</Text>
                  <Text>{formatDate(selectedTicket.updated_at)}</Text>
                </Box>
                {selectedTicket.tags.length > 0 && (
                  <Box>
                    <Text fontWeight="bold">Tags</Text>
                    <HStack spacing={2} mt={1}>
                      {selectedTicket.tags.map((tag) => (
                        <Badge key={tag} colorScheme="purple">
                          {tag}
                        </Badge>
                      ))}
                    </HStack>
                  </Box>
                )}
                {selectedTicket.is_escalated && (
                  <Alert status="warning">
                    <AlertIcon />
                    This ticket has been escalated
                  </Alert>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="green" onClick={onTicketModalClose}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Contact Detail Modal */}
      <Modal
        isOpen={isContactModalOpen}
        onClose={onContactModalClose}
        size="lg"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Contact Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedContact && (
              <VStack spacing={4} align="start">
                <Box>
                  <Text fontWeight="bold">Name</Text>
                  <Text>{selectedContact.name}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Email</Text>
                  <Text>{selectedContact.email}</Text>
                </Box>
                {selectedContact.phone && (
                  <Box>
                    <Text fontWeight="bold">Phone</Text>
                    <Text>{selectedContact.phone}</Text>
                  </Box>
                )}
                {selectedContact.mobile && (
                  <Box>
                    <Text fontWeight="bold">Mobile</Text>
                    <Text>{selectedContact.mobile}</Text>
                  </Box>
                )}
                {selectedContact.job_title && (
                  <Box>
                    <Text fontWeight="bold">Job Title</Text>
                    <Text>{selectedContact.job_title}</Text>
                  </Box>
                )}
                <Box>
                  <Text fontWeight="bold">Status</Text>
                  <Badge colorScheme={selectedContact.active ? "green" : "red"}>
                    {selectedContact.active ? "Active" : "Inactive"}
                  </Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold">Last Login</Text>
                  <Text>
                    {selectedContact.last_login_at
                      ? formatDate(selectedContact.last_login_at)
                      : "Never"}
                  </Text>
                </Box>
                {selectedContact.time_zone && (
                  <Box>
                    <Text fontWeight="bold">Time Zone</Text>
                    <Text>{selectedContact.time_zone}</Text>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="green" onClick={onContactModalClose}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Create Ticket Modal */}
      <Modal
        isOpen={isCreateTicketModalOpen}
        onClose={onCreateTicketModalClose}
        size="lg"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Create New Ticket</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <VStack spacing={4}>
              <FormControl>
                <FormLabel>Subject</FormLabel>
                <Input placeholder="Enter ticket subject" />
              </FormControl>
              <FormControl>
                <FormLabel>Description</FormLabel>
                <Textarea placeholder="Enter detailed description" rows={6} />
              </FormControl>
              <FormControl>
                <FormLabel>Priority</FormLabel>
                <Select>
                  <option value="1">Low</option>
                  <option value="2">Medium</option>
                  <option value="3">High</option>
                  <option value="4">Urgent</option>
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>Type</FormLabel>
                <Select>
                  <option value="Question">Question</option>
                  <option value="Incident">Incident</option>
                  <option value="Problem">Problem</option>
                  <option value="Feature Request">Feature Request</option>
                </Select>
              </FormControl>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onCreateTicketModalClose}>
              Cancel
            </Button>
            <Button colorScheme="green">Create Ticket</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default FreshdeskIntegrationPage;
