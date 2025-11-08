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

// Interfaces for Intercom data
interface IntercomContact {
  id: string;
  type: string;
  email: string;
  name?: string;
  phone?: string;
  role: string;
  created_at: string;
  updated_at: string;
  last_seen_at?: string;
  custom_attributes?: Record<string, any>;
  tags: string[];
  companies: Array<{ id: string; name: string }>;
}

interface IntercomConversation {
  id: string;
  type: string;
  created_at: string;
  updated_at: string;
  waiting_since?: string;
  snoozed_until?: string;
  source: Record<string, any>;
  contacts: Array<{ id: string; type: string }>;
  conversation_rating?: Record<string, any>;
  conversation_parts: Array<{
    id: string;
    type: string;
    part_type: string;
    body: string;
    author: { id: string; type: string };
    created_at: string;
  }>;
  tags: string[];
  assignee?: { id: string; type: string };
  open: boolean;
  read: boolean;
  priority: string;
}

interface IntercomTeam {
  id: string;
  type: string;
  name: string;
  admin_ids: string[];
  created_at: string;
  updated_at: string;
}

interface IntercomAdmin {
  id: string;
  type: string;
  name: string;
  email: string;
  job_title?: string;
  away_mode_enabled: boolean;
  away_mode_reassign: boolean;
  has_inbox_seat: boolean;
  team_ids: string[];
  created_at: string;
  updated_at: string;
}

interface IntercomStats {
  total_contacts: number;
  total_conversations: number;
  open_conversations: number;
  unassigned_conversations: number;
  team_count: number;
  admin_count: number;
  response_time_avg?: number;
  satisfaction_rating?: number;
}

const IntercomIntegrationPage: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [contacts, setContacts] = useState<IntercomContact[]>([]);
  const [conversations, setConversations] = useState<IntercomConversation[]>(
    [],
  );
  const [teams, setTeams] = useState<IntercomTeam[]>([]);
  const [admins, setAdmins] = useState<IntercomAdmin[]>([]);
  const [stats, setStats] = useState<IntercomStats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");
  const [selectedContact, setSelectedContact] =
    useState<IntercomContact | null>(null);
  const [selectedConversation, setSelectedConversation] =
    useState<IntercomConversation | null>(null);
  const [messageText, setMessageText] = useState("");

  const {
    isOpen: isConnectModalOpen,
    onOpen: onConnectModalOpen,
    onClose: onConnectModalClose,
  } = useDisclosure();
  const {
    isOpen: isContactModalOpen,
    onOpen: onContactModalOpen,
    onClose: onContactModalClose,
  } = useDisclosure();
  const {
    isOpen: isConversationModalOpen,
    onOpen: onConversationModalOpen,
    onClose: onConversationModalClose,
  } = useDisclosure();
  const {
    isOpen: isMessageModalOpen,
    onOpen: onMessageModalOpen,
    onClose: onMessageModalClose,
  } = useDisclosure();

  const toast = useToast();

  // Load initial data
  useEffect(() => {
    loadIntercomData();
  }, []);

  const loadIntercomData = async () => {
    try {
      setIsLoading(true);

      // Check connection status
      const healthResponse = await fetch("/api/v1/intercom/health");
      if (healthResponse.ok) {
        setIsConnected(true);

        // Load contacts
        const contactsResponse = await fetch(
          "/api/v1/intercom/contacts?limit=50",
        );
        if (contactsResponse.ok) {
          const contactsData = await contactsResponse.json();
          setContacts(contactsData.data || []);
        }

        // Load conversations
        const conversationsResponse = await fetch(
          "/api/v1/intercom/conversations?limit=50",
        );
        if (conversationsResponse.ok) {
          const conversationsData = await conversationsResponse.json();
          setConversations(conversationsData.data || []);
        }

        // Load teams
        const teamsResponse = await fetch("/api/v1/intercom/teams");
        if (teamsResponse.ok) {
          const teamsData = await teamsResponse.json();
          setTeams(teamsData.data || []);
        }

        // Load admins
        const adminsResponse = await fetch("/api/v1/intercom/admins");
        if (adminsResponse.ok) {
          const adminsData = await adminsResponse.json();
          setAdmins(adminsData.data || []);
        }

        // Load stats
        const statsResponse = await fetch("/api/v1/intercom/stats");
        if (statsResponse.ok) {
          const statsData = await statsResponse.json();
          setStats(statsData.data);
        }
      }
    } catch (error) {
      console.error("Failed to load Intercom data:", error);
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    try {
      setIsConnected(true);
      onConnectModalClose();

      toast({
        title: "Intercom Connected",
        description: "Successfully connected to Intercom",
        status: "success",
        duration: 3000,
        isClosable: true,
      });

      await loadIntercomData();
    } catch (error) {
      toast({
        title: "Connection Failed",
        description: "Failed to connect to Intercom",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const searchResponse = await fetch("/api/v1/intercom/search", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query: searchQuery,
          type: "contact",
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

  const handleSendMessage = async () => {
    if (!selectedContact || !messageText.trim()) return;

    try {
      const messageResponse = await fetch("/api/v1/intercom/messages", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          contact_id: selectedContact.id,
          message: messageText,
          message_type: "comment",
        }),
      });

      if (messageResponse.ok) {
        toast({
          title: "Message Sent",
          description: "Message successfully sent to contact",
          status: "success",
          duration: 3000,
          isClosable: true,
        });
        setMessageText("");
        onMessageModalClose();
      }
    } catch (error) {
      toast({
        title: "Message Failed",
        description: "Failed to send message",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const getPriorityColor = (priority: string): string => {
    switch (priority) {
      case "priority":
        return "red";
      case "not_priority":
        return "gray";
      default:
        return "blue";
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case "open":
        return "green";
      case "closed":
        return "red";
      default:
        return "gray";
    }
  };

  // Render connection status
  if (!isConnected && !isLoading) {
    return (
      <Box p={6}>
        <VStack spacing={6} align="center" justify="center" minH="60vh">
          <Box textAlign="center">
            <Heading size="lg" mb={4}>
              Connect Intercom
            </Heading>
            <Text color="gray.600" mb={6}>
              Connect your Intercom account to manage customer conversations,
              contacts, and team collaboration.
            </Text>
          </Box>

          <Card maxW="md" w="full">
            <CardBody>
              <VStack spacing={4}>
                <Box textAlign="center">
                  <Icon as={ChatIcon} w={12} h={12} color="blue.500" mb={4} />
                  <Heading size="md">Intercom Integration</Heading>
                  <Text color="gray.600" mt={2}>
                    Customer communication platform
                  </Text>
                </Box>

                <Button
                  colorScheme="blue"
                  size="lg"
                  w="full"
                  onClick={onConnectModalOpen}
                >
                  Connect Intercom
                </Button>
              </VStack>
            </CardBody>
          </Card>
        </VStack>

        {/* Connect Modal */}
        <Modal isOpen={isConnectModalOpen} onClose={onConnectModalClose}>
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Connect Intercom</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <Text mb={4}>
                Connect your Intercom account to access customer conversations,
                contacts, and team management features.
              </Text>
              <Alert status="info" mb={4}>
                <AlertIcon />
                <Box>
                  <AlertTitle>OAuth 2.0 Required</AlertTitle>
                  <AlertDescription>
                    You'll be redirected to Intercom to authorize access to your
                    account.
                  </AlertDescription>
                </Box>
              </Alert>
            </ModalBody>
            <ModalFooter>
              <Button variant="ghost" mr={3} onClick={onConnectModalClose}>
                Cancel
              </Button>
              <Button colorScheme="blue" onClick={handleConnect}>
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
        <Text mt={4}>Loading Intercom data...</Text>
      </Box>
    );
  }

  return (
    <Box p={6}>
      {/* Header */}
      <Flex justify="space-between" align="center" mb={6}>
        <Box>
          <Heading size="lg">Intercom</Heading>
          <Text color="gray.600">
            Customer communication and support platform
          </Text>
        </Box>
        <Button colorScheme="blue" onClick={loadIntercomData}>
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
              placeholder="Search contacts, conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            />
          </InputGroup>
        </CardBody>
      </Card>

      {/* Navigation Tabs */}
      <Flex mb={6} borderBottom="1px" borderColor="gray.200">
        {["dashboard", "contacts", "conversations", "teams", "admins"].map(
          (tab) => (
            <Button
              key={tab}
              variant="ghost"
              mr={2}
              colorScheme={activeTab === tab ? "blue" : "gray"}
              onClick={() => setActiveTab(tab)}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </Button>
          ),
        )}
      </Flex>

      {/* Dashboard Tab */}
      {activeTab === "dashboard" && stats && (
        <Grid templateColumns="repeat(4, 1fr)" gap={6} mb={6}>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Total Contacts</StatLabel>
                  <StatNumber>{stats.total_contacts}</StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
                    23.36%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Open Conversations</StatLabel>
                  <StatNumber>{stats.open_conversations}</StatNumber>
                  <StatHelpText>
                    <StatArrow type="decrease" />
                    9.05%
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
                    {stats.response_time_avg?.toFixed(1)}h
                  </StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
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
                    5.2%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
        </Grid>
      )}

      {/* Contacts Tab */}
      {activeTab === "contacts" && (
        <Card>
          <CardHeader>
            <Flex justify="space-between" align="center">
              <Heading size="md">Contacts ({contacts.length})</Heading>
              <Button colorScheme="blue" size="sm">
                Add Contact
              </Button>
            </Flex>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>Email</Th>
                  <Th>Phone</Th>
                  <Th>Last Seen</Th>
                  <Th>Tags</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {contacts.map((contact) => (
                  <Tr key={contact.id}>
                    <Td fontWeight="medium">{contact.name || "Unknown"}</Td>
                    <Td>{contact.email}</Td>
                    <Td>{contact.phone || "-"}</Td>
                    <Td>
                      {contact.last_seen_at
                        ? formatDate(contact.last_seen_at)
                        : "Never"}
                    </Td>
                    <Td>
                      <HStack spacing={1}>
                        {contact.tags.slice(0, 2).map((tag) => (
                          <Badge key={tag} colorScheme="blue" size="sm">
                            {tag}
                          </Badge>
                        ))}
                        {contact.tags.length > 2 && (
                          <Badge colorScheme="gray" size="sm">
                            +{contact.tags.length - 2}
                          </Badge>
                        )}
                      </HStack>
                    </Td>
                    <Td>
                      <HStack spacing={2}>
                        <Button
                          size="sm"
                          colorScheme="blue"
                          variant="ghost"
                          onClick={() => {
                            setSelectedContact(contact);
                            onContactModalOpen();
                          }}
                        >
                          View
                        </Button>
                        <Button
                          size="sm"
                          colorScheme="green"
                          variant="ghost"
                          onClick={() => {
                            setSelectedContact(contact);
                            onMessageModalOpen();
                          }}
                        >
                          Message
                        </Button>
                      </HStack>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}

      {/* Conversations Tab */}
      {activeTab === "conversations" && (
        <Card>
          <CardHeader>
            <Heading size="md">Conversations ({conversations.length})</Heading>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>ID</Th>
                  <Th>Status</Th>
                  <Th>Priority</Th>
                  <Th>Assignee</Th>
                  <Th>Last Updated</Th>
                  <Th>Tags</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {conversations.map((conversation) => (
                  <Tr key={conversation.id}>
                    <Td fontWeight="medium">
                      {conversation.id.slice(0, 8)}...
                    </Td>
                    <Td>
                      <Badge
                        colorScheme={getStatusColor(
                          conversation.open ? "open" : "closed",
                        )}
                      >
                        {conversation.open ? "Open" : "Closed"}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge
                        colorScheme={getPriorityColor(conversation.priority)}
                      >
                        {conversation.priority}
                      </Badge>
                    </Td>
                    <Td>{conversation.assignee ? "Assigned" : "Unassigned"}</Td>
                    <Td>{formatDate(conversation.updated_at)}</Td>
                    <Td>
                      <HStack spacing={1}>
                        {conversation.tags.slice(0, 2).map((tag) => (
                          <Badge key={tag} colorScheme="purple" size="sm">
                            {tag}
                          </Badge>
                        ))}
                        {conversation.tags.length > 2 && (
                          <Badge colorScheme="gray" size="sm">
                            +{conversation.tags.length - 2}
                          </Badge>
                        )}
                      </HStack>
                    </Td>
                    <Td>
                      <Button
                        size="sm"
                        colorScheme="blue"
                        variant="ghost"
                        onClick={() => {
                          setSelectedConversation(conversation);
                          onConversationModalOpen();
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

      {/* Teams Tab */}
      {activeTab === "teams" && (
        <Card>
          <CardHeader>
            <Heading size="md">Teams ({teams.length})</Heading>
          </CardHeader>
          <CardBody>
            <Grid templateColumns="repeat(3, 1fr)" gap={6}>
              {teams.map((team) => (
                <GridItem key={team.id}>
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Heading size="sm">{team.name}</Heading>
                        <Text color="gray.600">
                          {team.admin_ids.length} admins
                        </Text>
                        <Text fontSize="sm">
                          Created: {formatDate(team.created_at)}
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

      {/* Admins Tab */}
      {activeTab === "admins" && (
        <Card>
          <CardHeader>
            <Heading size="md">Admins ({admins.length})</Heading>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>Email</Th>
                  <Th>Job Title</Th>
                  <Th>Status</Th>
                  <Th>Teams</Th>
                </Tr>
              </Thead>
              <Tbody>
                {admins.map((admin) => (
                  <Tr key={admin.id}>
                    <Td fontWeight="medium">{admin.name}</Td>
                    <Td>{admin.email}</Td>
                    <Td>{admin.job_title || "Not specified"}</Td>
                    <Td>
                      <Badge
                        colorScheme={
                          admin.away_mode_enabled ? "yellow" : "green"
                        }
                      >
                        {admin.away_mode_enabled ? "Away" : "Available"}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge colorScheme="blue">
                        {admin.team_ids.length} teams
                      </Badge>
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}

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
                  <Text>{selectedContact.name || "Unknown"}</Text>
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
                <Box>
                  <Text fontWeight="bold">Role</Text>
                  <Badge colorScheme="blue">{selectedContact.role}</Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold">Last Seen</Text>
                  <Text>
                    {selectedContact.last_seen_at
                      ? formatDate(selectedContact.last_seen_at)
                      : "Never"}
                  </Text>
                </Box>
                {selectedContact.tags.length > 0 && (
                  <Box>
                    <Text fontWeight="bold">Tags</Text>
                    <HStack spacing={2} mt={1}>
                      {selectedContact.tags.map((tag) => (
                        <Badge key={tag} colorScheme="purple">
                          {tag}
                        </Badge>
                      ))}
                    </HStack>
                  </Box>
                )}
                {selectedContact.companies.length > 0 && (
                  <Box>
                    <Text fontWeight="bold">Companies</Text>
                    <VStack align="start" spacing={1} mt={1}>
                      {selectedContact.companies.map((company) => (
                        <Text key={company.id}>{company.name}</Text>
                      ))}
                    </VStack>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" mr={3} onClick={onContactModalClose}>
              Close
            </Button>
            <Button
              colorScheme="green"
              onClick={() => {
                onContactModalClose();
                onMessageModalOpen();
              }}
            >
              Send Message
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Conversation Detail Modal */}
      <Modal
        isOpen={isConversationModalOpen}
        onClose={onConversationModalClose}
        size="xl"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Conversation Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedConversation && (
              <VStack spacing={4} align="start">
                <Box>
                  <Text fontWeight="bold">Conversation ID</Text>
                  <Text>{selectedConversation.id}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Status</Text>
                  <Badge
                    colorScheme={getStatusColor(
                      selectedConversation.open ? "open" : "closed",
                    )}
                  >
                    {selectedConversation.open ? "Open" : "Closed"}
                  </Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold">Priority</Text>
                  <Badge
                    colorScheme={getPriorityColor(
                      selectedConversation.priority,
                    )}
                  >
                    {selectedConversation.priority}
                  </Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold">Assignee</Text>
                  <Text>
                    {selectedConversation.assignee ? "Assigned" : "Unassigned"}
                  </Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Created</Text>
                  <Text>{formatDate(selectedConversation.created_at)}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Last Updated</Text>
                  <Text>{formatDate(selectedConversation.updated_at)}</Text>
                </Box>
                {selectedConversation.tags.length > 0 && (
                  <Box>
                    <Text fontWeight="bold">Tags</Text>
                    <HStack spacing={2} mt={1}>
                      {selectedConversation.tags.map((tag) => (
                        <Badge key={tag} colorScheme="purple">
                          {tag}
                        </Badge>
                      ))}
                    </HStack>
                  </Box>
                )}
                <Box w="full">
                  <Text fontWeight="bold" mb={2}>
                    Messages
                  </Text>
                  <VStack spacing={3} align="start" w="full">
                    {selectedConversation.conversation_parts.map((part) => (
                      <Box
                        key={part.id}
                        p={3}
                        bg="gray.50"
                        borderRadius="md"
                        w="full"
                      >
                        <Text fontSize="sm" color="gray.600">
                          {part.author.type === "admin" ? "Agent" : "Customer"}{" "}
                          • {formatDate(part.created_at)}
                        </Text>
                        <Text mt={1}>{part.body}</Text>
                      </Box>
                    ))}
                  </VStack>
                </Box>
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" onClick={onConversationModalClose}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Send Message Modal */}
      <Modal
        isOpen={isMessageModalOpen}
        onClose={onMessageModalClose}
        size="md"
      >
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Send Message</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <FormControl>
              <FormLabel>Message</FormLabel>
              <Textarea
                placeholder="Type your message here..."
                value={messageText}
                onChange={(e) => setMessageText(e.target.value)}
                rows={6}
              />
            </FormControl>
            {selectedContact && (
              <Text mt={2} fontSize="sm" color="gray.600">
                To: {selectedContact.name || "Unknown"} ({selectedContact.email}
                )
              </Text>
            )}
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onMessageModalClose}>
              Cancel
            </Button>
            <Button
              colorScheme="blue"
              onClick={handleSendMessage}
              isDisabled={!messageText.trim()}
            >
              Send Message
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default IntercomIntegrationPage;
