/**
 * Freshdesk Integration Component
 * Complete Freshdesk customer support integration for ATOM
 * Provides ticket management, contact management, and analytics
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Input,
  Select,
  Badge,
  Card,
  CardBody,
  CardHeader,
  Heading,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  FormControl,
  FormLabel,
  Textarea,
  useDisclosure,
  useToast,
  Spinner,
  Alert,
  AlertIcon,
  SimpleGrid,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Progress,
  List,
  ListItem,
  ListIcon,
  Divider
} from '@chakra-ui/react';
import {
  FreshdeskConfig,
  FreshdeskIntegrationState,
  FreshdeskTicket,
  FreshdeskContact,
  FreshdeskCompany,
  FreshdeskAgent,
  FreshdeskGroup,
  FreshdeskFilters,
  FreshdeskStatistics,
  FreshdeskSkill,
  FRESHDESK_TICKET_STATUS,
  FRESHDESK_TICKET_PRIORITY,
  FRESHDESK_TICKET_SOURCE
} from './types';
import { freshdeskSkills } from './skills/freshdeskSkills';

interface FreshdeskIntegrationProps {
  config?: Partial<FreshdeskConfig>;
  onConfigChange?: (config: FreshdeskConfig) => void;
  onTicketSelect?: (ticket: FreshdeskTicket) => void;
  onContactSelect?: (contact: FreshdeskContact) => void;
  onCompanySelect?: (company: FreshdeskCompany) => void;
  height?: string;
  width?: string;
}

const FreshdeskIntegration: React.FC<FreshdeskIntegrationProps> = ({
  config: initialConfig,
  onConfigChange,
  onTicketSelect,
  onContactSelect,
  onCompanySelect,
  height = '100%',
  width = '100%'
}) => {
  // State Management
  const [state, setState] = useState<FreshdeskIntegrationState>({
    isAuthenticated: false,
    config: null,
    user: null,
    tickets: [],
    contacts: [],
    companies: [],
    agents: [],
    groups: [],
    conversations: [],
    satisfactionRatings: [],
    slaPolicies: [],
    loading: false,
    error: null,
    filters: {},
    pagination: {
      tickets: { page: 1, hasMore: true, total: 0 },
      contacts: { page: 1, hasMore: true, total: 0 },
      companies: { page: 1, hasMore: true, total: 0 }
    },
    statistics: {
      totalTickets: 0,
      openTickets: 0,
      pendingTickets: 0,
      resolvedTickets: 0,
      closedTickets: 0,
      overdueTickets: 0,
      dueToday: 0,
      satisfactionRating: 0,
      averageResponseTime: 0,
      averageResolutionTime: 0,
      ticketsByPriority: {},
      ticketsByStatus: {},
      ticketsByAgent: {},
      ticketsByGroup: {},
      ticketsBySource: {},
      topContacts: [],
      topCompanies: [],
      agentPerformance: []
    }
  });

  // Modals
  const { isOpen: isTicketModalOpen, onOpen: onTicketModalOpen, onClose: onTicketModalClose } = useDisclosure();
  const { isOpen: isContactModalOpen, onOpen: onContactModalOpen, onClose: onContactModalClose } = useDisclosure();
  const { isOpen: isCompanyModalOpen, onOpen: onCompanyModalOpen, onClose: onCompanyModalClose } = useDisclosure();

  const toast = useToast();

  // Form States
  const [newTicket, setNewTicket] = useState({
    subject: '',
    description: '',
    priority: FRESHDESK_TICKET_PRIORITY.MEDIUM,
    requester_email: '',
    company_id: 0,
    group_id: 0,
    tags: []
  });

  const [newContact, setNewContact] = useState({
    name: '',
    email: '',
    phone: '',
    company_id: 0,
    job_title: '',
    description: ''
  });

  const [newCompany, setNewCompany] = useState({
    name: '',
    description: '',
    domains: [],
    note: ''
  });

  // Initialize Integration
  useEffect(() => {
    if (initialConfig) {
      const config: FreshdeskConfig = {
        domain: initialConfig.domain || '',
        apiVersion: initialConfig.apiVersion || 'v2',
        rateLimit: {
          requestsPerMinute: 1000,
          requestsPerHour: 60000,
          requestsPerDay: 1000000,
          ...initialConfig.rateLimit
        },
        features: {
          ticketManagement: true,
          contactManagement: true,
          companyManagement: true,
          agentManagement: true,
          groupManagement: true,
          satisfactionTracking: true,
          slaManagement: true,
          knowledgeBase: true,
          forums: true,
          analytics: true,
          automation: true,
          customFields: true,
          timeTracking: true,
          phoneSupport: false,
          chatSupport: false,
          socialSupport: false,
          ...initialConfig.features
        },
        preferences: {
          defaultPriority: FRESHDESK_TICKET_PRIORITY.MEDIUM,
          defaultStatus: FRESHDESK_TICKET_STATUS.OPEN,
          autoAssign: false,
          escalateUnassigned: true,
          notifyOnUpdate: true,
          includeSignature: true,
          enableSpellCheck: true,
          timeFormat: '24h',
          dateFormat: 'YYYY-MM-DD',
          timezone: 'UTC',
          language: 'en',
          ...initialConfig.preferences
        },
        ...initialConfig
      };

      setState(prev => ({ ...prev, config, isAuthenticated: true }));
      loadInitialData(config);
    }
  }, [initialConfig]);

  // Load Initial Data
  const loadInitialData = async (config: FreshdeskConfig) => {
    setState(prev => ({ ...prev, loading: true }));
    
    try {
      // Mock data loading - replace with actual API calls
      const mockTickets: FreshdeskTicket[] = [
        {
          id: 1,
          subject: 'Unable to login to account',
          description: 'User reports login issues with their account',
          description_text: 'User reports login issues with their account',
          status: FRESHDESK_TICKET_STATUS.OPEN,
          priority: FRESHDESK_TICKET_PRIORITY.HIGH,
          source: FRESHDESK_TICKET_SOURCE.EMAIL,
          requester_id: 101,
          responder_id: 1,
          group_id: 1,
          created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
          tags: ['login', 'urgent']
        },
        {
          id: 2,
          subject: 'Feature request for dashboard',
          description: 'Customer would like to see additional analytics on the dashboard',
          description_text: 'Customer would like to see additional analytics on the dashboard',
          status: FRESHDESK_TICKET_STATUS.PENDING,
          priority: FRESHDESK_TICKET_PRIORITY.MEDIUM,
          source: FRESHDESK_TICKET_SOURCE.PORTAL,
          requester_id: 102,
          responder_id: 2,
          group_id: 2,
          created_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
          updated_at: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
          tags: ['feature-request', 'dashboard']
        }
      ];

      const mockStatistics: FreshdeskStatistics = {
        totalTickets: 245,
        openTickets: 23,
        pendingTickets: 12,
        resolvedTickets: 198,
        closedTickets: 12,
        overdueTickets: 5,
        dueToday: 8,
        satisfactionRating: 4.2,
        averageResponseTime: 3.2,
        averageResolutionTime: 24.5,
        ticketsByPriority: {
          'Low': 45,
          'Medium': 120,
          'High': 65,
          'Urgent': 15
        },
        ticketsByStatus: {
          'Open': 23,
          'Pending': 12,
          'Resolved': 198,
          'Closed': 12
        },
        ticketsByAgent: {
          'John Doe': 45,
          'Jane Smith': 38,
          'Mike Johnson': 29
        },
        ticketsByGroup: {
          'Support': 67,
          'Technical': 34,
          'Billing': 28
        },
        ticketsBySource: {
          'Email': 120,
          'Portal': 45,
          'Phone': 30,
          'Chat': 50
        },
        topContacts: [
          { name: 'Acme Corp', email: 'support@acme.com', ticketCount: 12 },
          { name: 'Tech Industries', email: 'help@tech.com', ticketCount: 8 }
        ],
        topCompanies: [
          { name: 'Acme Corp', ticketCount: 12 },
          { name: 'Tech Industries', ticketCount: 8 }
        ],
        agentPerformance: [
          {
            agent: 'John Doe',
            ticketsHandled: 45,
            averageResponseTime: 2.8,
            averageResolutionTime: 18.5,
            satisfactionRating: 4.5
          }
        ]
      };

      setState(prev => ({
        ...prev,
        tickets: mockTickets,
        statistics: mockStatistics,
        loading: false,
        pagination: {
          ...prev.pagination,
          tickets: { page: 1, hasMore: false, total: mockTickets.length }
        }
      }));
    } catch (error) {
      setState(prev => ({
        ...prev,
        error: error instanceof Error ? error.message : 'Failed to load data',
        loading: false
      }));
    }
  };

  // Ticket Actions
  const handleCreateTicket = async () => {
    try {
      const skillResult = await freshdeskSkills.createTicket(
        { config: state.config!, state, user: state.user! },
        {
          subject: newTicket.subject,
          description: newTicket.description,
          priority: newTicket.priority,
          requester_id: parseInt(newTicket.requester_email) || 0,
          group_id: newTicket.group_id || 0,
          company_id: newTicket.company_id || 0
        }
      );

      if (skillResult.result.success) {
        toast({
          title: 'Ticket created',
          description: skillResult.result.message,
          status: 'success',
          duration: 3000
        });
        
        // Reset form
        setNewTicket({
          subject: '',
          description: '',
          priority: FRESHDESK_TICKET_PRIORITY.MEDIUM,
          requester_email: '',
          company_id: 0,
          group_id: 0,
          tags: []
        });
        
        onTicketModalClose();
        loadInitialData(state.config!);
      } else {
        toast({
          title: 'Error',
          description: skillResult.result.error,
          status: 'error',
          duration: 3000
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 3000
      });
    }
  };

  const handleUpdateTicketStatus = async (ticketId: number, status: number) => {
    try {
      const skillResult = await freshdeskSkills.updateTicket(
        { config: state.config!, state, user: state.user! },
        { ticket_id: ticketId, status }
      );

      if (skillResult.result.success) {
        toast({
          title: 'Ticket updated',
          description: skillResult.result.message,
          status: 'success',
          duration: 3000
        });
        loadInitialData(state.config!);
      } else {
        toast({
          title: 'Error',
          description: skillResult.result.error,
          status: 'error',
          duration: 3000
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 3000
      });
    }
  };

  // Status Badge Component
  const getStatusBadge = (status: number) => {
    const statusConfig = {
      [FRESHDESK_TICKET_STATUS.OPEN]: { color: 'red', label: 'Open' },
      [FRESHDESK_TICKET_STATUS.PENDING]: { color: 'yellow', label: 'Pending' },
      [FRESHDESK_TICKET_STATUS.RESOLVED]: { color: 'green', label: 'Resolved' },
      [FRESHDESK_TICKET_STATUS.CLOSED]: { color: 'gray', label: 'Closed' }
    };

    const config = statusConfig[status] || { color: 'gray', label: 'Unknown' };
    return <Badge colorScheme={config.color}>{config.label}</Badge>;
  };

  // Priority Badge Component
  const getPriorityBadge = (priority: number) => {
    const priorityConfig = {
      [FRESHDESK_TICKET_PRIORITY.LOW]: { color: 'blue', label: 'Low' },
      [FRESHDESK_TICKET_PRIORITY.MEDIUM]: { color: 'yellow', label: 'Medium' },
      [FRESHDESK_TICKET_PRIORITY.HIGH]: { color: 'orange', label: 'High' },
      [FRESHDESK_TICKET_PRIORITY.URGENT]: { color: 'red', label: 'Urgent' }
    };

    const config = priorityConfig[priority] || { color: 'gray', label: 'Unknown' };
    return <Badge colorScheme={config.color}>{config.label}</Badge>;
  };

  if (!state.isAuthenticated) {
    return (
      <Box p={8}>
        <Alert status="warning">
          <AlertIcon />
          <Text>Freshdesk integration requires authentication and configuration</Text>
        </Alert>
      </Box>
    );
  }

  if (state.loading) {
    return (
      <Box p={8} display="flex" justifyContent="center">
        <VStack spacing={4}>
          <Spinner size="xl" />
          <Text>Loading Freshdesk data...</Text>
        </VStack>
      </Box>
    );
  }

  return (
    <Box h={height} w={width} overflow="hidden">
      <VStack h="full" spacing={4} p={4}>
        {/* Header */}
        <HStack justify="space-between" w="full">
          <Heading size="lg">Freshdesk Integration</Heading>
          <Button colorScheme="blue" onClick={onTicketModalOpen}>
            Create Ticket
          </Button>
        </HStack>

        {/* Statistics Dashboard */}
        <SimpleGrid columns={{ base: 1, md: 4 }} spacing={4} w="full">
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Total Tickets</StatLabel>
                <StatNumber>{state.statistics.totalTickets}</StatNumber>
                <StatHelpText>All time</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Open Tickets</StatLabel>
                <StatNumber color="red.500">{state.statistics.openTickets}</StatNumber>
                <StatHelpText>Need attention</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Satisfaction</StatLabel>
                <StatNumber>{state.statistics.satisfactionRating}/5</StatNumber>
                <StatHelpText>Customer rating</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
          
          <Card>
            <CardBody>
              <Stat>
                <StatLabel>Avg Response Time</StatLabel>
                <StatNumber>{state.statistics.averageResponseTime}h</StatNumber>
                <StatHelpText>Response time</StatHelpText>
              </Stat>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Main Content Tabs */}
        <Tabs flex={1} w="full">
          <TabList>
            <Tab>Tickets</Tab>
            <Tab>Analytics</Tab>
            <Tab>Contacts</Tab>
            <Tab>Companies</Tab>
            <Tab>Agents</Tab>
            <Tab>Groups</Tab>
          </TabList>

          <TabPanels flex={1}>
            {/* Tickets Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack spacing={4}>
                  <Input placeholder="Search tickets..." />
                  <Select placeholder="Filter by status">
                    <option value="">All Status</option>
                    <option value={FRESHDESK_TICKET_STATUS.OPEN.toString()}>Open</option>
                    <option value={FRESHDESK_TICKET_STATUS.PENDING.toString()}>Pending</option>
                    <option value={FRESHDESK_TICKET_STATUS.RESOLVED.toString()}>Resolved</option>
                    <option value={FRESHDESK_TICKET_STATUS.CLOSED.toString()}>Closed</option>
                  </Select>
                  <Select placeholder="Filter by priority">
                    <option value="">All Priority</option>
                    <option value={FRESHDESK_TICKET_PRIORITY.LOW.toString()}>Low</option>
                    <option value={FRESHDESK_TICKET_PRIORITY.MEDIUM.toString()}>Medium</option>
                    <option value={FRESHDESK_TICKET_PRIORITY.HIGH.toString()}>High</option>
                    <option value={FRESHDESK_TICKET_PRIORITY.URGENT.toString()}>Urgent</option>
                  </Select>
                </HStack>

                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>ID</Th>
                        <Th>Subject</Th>
                        <Th>Status</Th>
                        <Th>Priority</Th>
                        <Th>Created</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {state.tickets.map((ticket) => (
                        <Tr 
                          key={ticket.id} 
                          onClick={() => onTicketSelect?.(ticket)}
                          cursor="pointer"
                          _hover={{ bg: 'gray.50' }}
                        >
                          <Td>#{ticket.id}</Td>
                          <Td>{ticket.subject}</Td>
                          <Td>{getStatusBadge(ticket.status)}</Td>
                          <Td>{getPriorityBadge(ticket.priority)}</Td>
                          <Td>{new Date(ticket.created_at).toLocaleDateString()}</Td>
                          <Td>
                            <HStack spacing={2}>
                              <Button 
                                size="xs" 
                                colorScheme="green"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleUpdateTicketStatus(ticket.id, FRESHDESK_TICKET_STATUS.RESOLVED);
                                }}
                              >
                                Resolve
                              </Button>
                              <Button 
                                size="xs" 
                                colorScheme="red"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleUpdateTicketStatus(ticket.id, FRESHDESK_TICKET_STATUS.CLOSED);
                                }}
                              >
                                Close
                              </Button>
                            </HStack>
                          </Td>
                        </Tr>
                      ))}
                    </Tbody>
                  </Table>
                </TableContainer>
              </VStack>
            </TabPanel>

            {/* Analytics Tab */}
            <TabPanel>
              <VStack spacing={6} align="stretch">
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                  <Card>
                    <CardHeader>
                      <Heading size="md">Tickets by Status</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={3} align="stretch">
                        {Object.entries(state.statistics.ticketsByStatus).map(([status, count]) => (
                          <HStack key={status} justify="space-between">
                            <Text>{status}</Text>
                            <Badge>{count}</Badge>
                          </HStack>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>

                  <Card>
                    <CardHeader>
                      <Heading size="md">Tickets by Priority</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={3} align="stretch">
                        {Object.entries(state.statistics.ticketsByPriority).map(([priority, count]) => (
                          <HStack key={priority} justify="space-between">
                            <Text>{priority}</Text>
                            <Badge>{count}</Badge>
                          </HStack>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>

                <Card>
                  <CardHeader>
                    <Heading size="md">Top Contacts</Heading>
                  </CardHeader>
                  <CardBody>
                    <List spacing={2}>
                      {state.statistics.topContacts.map((contact, index) => (
                        <ListItem key={index}>
                          <HStack justify="space-between">
                            <Box>
                              <Text fontWeight="bold">{contact.name}</Text>
                              <Text fontSize="sm" color="gray.600">{contact.email}</Text>
                            </Box>
                            <Badge>{contact.ticketCount} tickets</Badge>
                          </HStack>
                        </ListItem>
                      ))}
                    </List>
                  </CardBody>
                </Card>
              </VStack>
            </TabPanel>

            {/* Contacts Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Heading size="md">Contacts</Heading>
                  <Button colorScheme="blue" onClick={onContactModalOpen}>
                    Add Contact
                  </Button>
                </HStack>
                
                <Text color="gray.600">Contact management features coming soon</Text>
              </VStack>
            </TabPanel>

            {/* Companies Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <HStack justify="space-between">
                  <Heading size="md">Companies</Heading>
                  <Button colorScheme="blue" onClick={onCompanyModalOpen}>
                    Add Company
                  </Button>
                </HStack>
                
                <Text color="gray.600">Company management features coming soon</Text>
              </VStack>
            </TabPanel>

            {/* Agents Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Heading size="md">Agents</Heading>
                <Text color="gray.600">Agent management features coming soon</Text>
              </VStack>
            </TabPanel>

            {/* Groups Tab */}
            <TabPanel>
              <VStack spacing={4} align="stretch">
                <Heading size="md">Groups</Heading>
                <Text color="gray.600">Group management features coming soon</Text>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Create Ticket Modal */}
        <Modal isOpen={isTicketModalOpen} onClose={onTicketModalClose} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Ticket</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Subject</FormLabel>
                  <Input
                    value={newTicket.subject}
                    onChange={(e) => setNewTicket(prev => ({ ...prev, subject: e.target.value }))}
                    placeholder="Enter ticket subject"
                  />
                </FormControl>

                <FormControl isRequired>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={newTicket.description}
                    onChange={(e) => setNewTicket(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe the issue in detail"
                    rows={6}
                  />
                </FormControl>

                <HStack spacing={4} w="full">
                  <FormControl>
                    <FormLabel>Priority</FormLabel>
                    <Select
                      value={newTicket.priority}
                      onChange={(e) => setNewTicket(prev => ({ ...prev, priority: parseInt(e.target.value) }))}
                    >
                      <option value={FRESHDESK_TICKET_PRIORITY.LOW}>Low</option>
                      <option value={FRESHDESK_TICKET_PRIORITY.MEDIUM}>Medium</option>
                      <option value={FRESHDESK_TICKET_PRIORITY.HIGH}>High</option>
                      <option value={FRESHDESK_TICKET_PRIORITY.URGENT}>Urgent</option>
                    </Select>
                  </FormControl>

                  <FormControl>
                    <FormLabel>Requester Email</FormLabel>
                    <Input
                      value={newTicket.requester_email}
                      onChange={(e) => setNewTicket(prev => ({ ...prev, requester_email: e.target.value }))}
                      placeholder="customer@example.com"
                    />
                  </FormControl>
                </HStack>

                <Button
                  colorScheme="blue"
                  w="full"
                  onClick={handleCreateTicket}
                  isDisabled={!newTicket.subject || !newTicket.description}
                >
                  Create Ticket
                </Button>
              </VStack>
            </ModalBody>
          </ModalContent>
        </Modal>

        {/* Create Contact Modal */}
        <Modal isOpen={isContactModalOpen} onClose={onContactModalClose} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Contact</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <HStack spacing={4} w="full">
                  <FormControl isRequired>
                    <FormLabel>Name</FormLabel>
                    <Input
                      value={newContact.name}
                      onChange={(e) => setNewContact(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Contact name"
                    />
                  </FormControl>

                  <FormControl isRequired>
                    <FormLabel>Email</FormLabel>
                    <Input
                      value={newContact.email}
                      onChange={(e) => setNewContact(prev => ({ ...prev, email: e.target.value }))}
                      placeholder="contact@example.com"
                    />
                  </FormControl>
                </HStack>

                <FormControl>
                  <FormLabel>Phone</FormLabel>
                  <Input
                    value={newContact.phone}
                    onChange={(e) => setNewContact(prev => ({ ...prev, phone: e.target.value }))}
                    placeholder="+1-555-0123"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Job Title</FormLabel>
                  <Input
                    value={newContact.job_title}
                    onChange={(e) => setNewContact(prev => ({ ...prev, job_title: e.target.value }))}
                    placeholder="Product Manager"
                  />
                </FormControl>

                <Button colorScheme="blue" w="full">
                  Create Contact
                </Button>
              </VStack>
            </ModalBody>
          </ModalContent>
        </Modal>

        {/* Create Company Modal */}
        <Modal isOpen={isCompanyModalOpen} onClose={onCompanyModalClose} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Company</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Company Name</FormLabel>
                  <Input
                    value={newCompany.name}
                    onChange={(e) => setNewCompany(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Acme Corporation"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={newCompany.description}
                    onChange={(e) => setNewCompany(prev => ({ ...prev, description: e.target.value }))}
                    placeholder="Brief description of the company"
                    rows={3}
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Domains</FormLabel>
                  <Input
                    value={newCompany.domains?.join(', ')}
                    onChange={(e) => setNewCompany(prev => ({ 
                      ...prev, 
                      domains: e.target.value.split(',').map(d => d.trim()).filter(d => d) 
                    }))}
                    placeholder="acme.com, corp.acme.com"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Notes</FormLabel>
                  <Textarea
                    value={newCompany.note}
                    onChange={(e) => setNewCompany(prev => ({ ...prev, note: e.target.value }))}
                    placeholder="Additional notes about the company"
                    rows={3}
                  />
                </FormControl>

                <Button colorScheme="blue" w="full">
                  Create Company
                </Button>
              </VStack>
            </ModalBody>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default FreshdeskIntegration;