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
  EmailIcon,
  TimeIcon,
  AttachmentIcon,
  StarIcon,
} from "@chakra-ui/icons";

// Interfaces for Mailchimp data
interface MailchimpAudience {
  id: string;
  name: string;
  member_count: number;
  unsubscribe_count: number;
  created_at: string;
  updated_at: string;
  contact: Record<string, any>;
  permission_reminder: string;
  campaign_defaults: Record<string, any>;
  stats?: Record<string, any>;
}

interface MailchimpContact {
  id: string;
  email_address: string;
  status: string;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  merge_fields?: Record<string, any>;
  stats?: Record<string, any>;
  ip_signup?: string;
  timestamp_signup?: string;
  ip_opt?: string;
  timestamp_opt?: string;
  member_rating: number;
  last_changed?: string;
  language?: string;
  vip: boolean;
  email_client?: string;
  tags: string[];
}

interface MailchimpCampaign {
  id: string;
  type: string;
  create_time: string;
  archive_url?: string;
  long_archive_url?: string;
  status: string;
  emails_sent: number;
  send_time?: string;
  content_type: string;
  recipients: Record<string, any>;
  settings: Record<string, any>;
  tracking: Record<string, any>;
  report_summary?: Record<string, any>;
}

interface MailchimpAutomation {
  id: string;
  create_time: string;
  start_time?: string;
  status: string;
  emails_sent: number;
  recipients: Record<string, any>;
  settings: Record<string, any>;
  tracking: Record<string, any>;
  trigger_settings: Record<string, any>;
  report_summary?: Record<string, any>;
}

interface MailchimpTemplate {
  id: number;
  type: string;
  name: string;
  drag_and_drop: boolean;
  responsive: boolean;
  category?: string;
  date_created: string;
  date_edited?: string;
  created_by: string;
  edited_by?: string;
  active: boolean;
  folder_id?: string;
}

interface MailchimpStats {
  total_audiences: number;
  total_contacts: number;
  total_campaigns: number;
  total_automations: number;
  active_campaigns: number;
  open_rate?: number;
  click_rate?: number;
  bounce_rate?: number;
  unsubscribe_rate?: number;
  revenue?: number;
}

const MailchimpIntegrationPage: React.FC = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [audiences, setAudiences] = useState<MailchimpAudience[]>([]);
  const [contacts, setContacts] = useState<MailchimpContact[]>([]);
  const [campaigns, setCampaigns] = useState<MailchimpCampaign[]>([]);
  const [automations, setAutomations] = useState<MailchimpAutomation[]>([]);
  const [templates, setTemplates] = useState<MailchimpTemplate[]>([]);
  const [stats, setStats] = useState<MailchimpStats | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState("dashboard");
  const [selectedAudience, setSelectedAudience] = useState<MailchimpAudience | null>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<MailchimpCampaign | null>(null);
  const [selectedContact, setSelectedContact] = useState<MailchimpContact | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [serverPrefix, setServerPrefix] = useState("");

  const {
    isOpen: isConnectModalOpen,
    onOpen: onConnectModalOpen,
    onClose: onConnectModalClose,
  } = useDisclosure();
  const {
    isOpen: isAudienceModalOpen,
    onOpen: onAudienceModalOpen,
    onClose: onAudienceModalClose,
  } = useDisclosure();
  const {
    isOpen: isCampaignModalOpen,
    onOpen: onCampaignModalOpen,
    onClose: onCampaignModalClose,
  } = useDisclosure();
  const {
    isOpen: isContactModalOpen,
    onOpen: onContactModalOpen,
    onClose: onContactModalClose,
  } = useDisclosure();
  const {
    isOpen: isCreateCampaignModalOpen,
    onOpen: onCreateCampaignModalOpen,
    onClose: onCreateCampaignModalClose,
  } = useDisclosure();
  const {
    isOpen: isCreateContactModalOpen,
    onOpen: onCreateContactModalOpen,
    onClose: onCreateContactModalClose,
  } = useDisclosure();

  const toast = useToast();

  // Load initial data
  useEffect(() => {
    loadMailchimpData();
  }, []);

  const loadMailchimpData = async () => {
    try {
      setIsLoading(true);

      // Check connection status
      const healthResponse = await fetch("/api/v1/mailchimp/health");
      if (healthResponse.ok) {
        setIsConnected(true);

        // Load audiences
        const audiencesResponse = await fetch("/api/v1/mailchimp/audiences?limit=50");
        if (audiencesResponse.ok) {
          const audiencesData = await audiencesResponse.json();
          setAudiences(audiencesData.data || []);
        }

        // Load campaigns
        const campaignsResponse = await fetch("/api/v1/mailchimp/campaigns?limit=50");
        if (campaignsResponse.ok) {
          const campaignsData = await campaignsResponse.json();
          setCampaigns(campaignsData.data || []);
        }

        // Load automations
        const automationsResponse = await fetch("/api/v1/mailchimp/automations");
        if (automationsResponse.ok) {
          const automationsData = await automationsResponse.json();
          setAutomations(automationsData.data || []);
        }

        // Load templates
        const templatesResponse = await fetch("/api/v1/mailchimp/templates");
        if (templatesResponse.ok) {
          const templatesData = await templatesResponse.json();
          setTemplates(templatesData.data || []);
        }

        // Load stats
        const statsResponse = await fetch("/api/v1/mailchimp/stats");
        if (statsResponse.ok) {
          const statsData = await statsResponse.json();
          setStats(statsData.data);
        }
      }
    } catch (error) {
      console.error("Failed to load Mailchimp data:", error);
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleConnect = async () => {
    if (!apiKey.trim() || !serverPrefix.trim()) {
      toast({
        title: "Missing Credentials",
        description: "Please enter both API Key and Server Prefix",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    try {
      const authResponse = await fetch("/api/v1/mailchimp/auth", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          api_key: apiKey,
          server_prefix: serverPrefix,
        }),
      });

      if (authResponse.ok) {
        setIsConnected(true);
        onConnectModalClose();

        toast({
          title: "Mailchimp Connected",
          description: "Successfully connected to Mailchimp",
          status: "success",
          duration: 3000,
          isClosable: true,
        });

        await loadMailchimpData();
      } else {
        throw new Error("Authentication failed");
      }
    } catch (error) {
      toast({
        title: "Connection Failed",
        description: "Failed to connect to Mailchimp",
        status: "error",
        duration: 3000,
        isClosable: true,
      });
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    try {
      const searchResponse = await fetch("/api/v1/mailchimp/search", {
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

  const loadAudienceContacts = async (audienceId: string) => {
    try {
      const contactsResponse = await fetch(`/api/v1/mailchimp/contacts?audience_id=${audienceId}&limit=50`);
      if (contactsResponse.ok) {
        const contactsData = await contactsResponse.json();
        setContacts(contactsData.data || []);
      }
    } catch (error) {
      console.error("Failed to load contacts:", error);
    }
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatNumber = (num: number): string => {
    return num.toLocaleString();
  };

  const formatPercentage = (num: number): string => {
    return `${(num * 100).toFixed(1)}%`;
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case "sent":
        return "green";
      case "scheduled":
        return "blue";
      case "sending":
        return "orange";
      case "draft":
        return "gray";
      case "paused":
        return "yellow";
      default:
        return "gray";
    }
  };

  const getContactStatusColor = (status: string): string => {
    switch (status) {
      case "subscribed":
        return "green";
      case "unsubscribed":
        return "red";
      case "cleaned":
        return "gray";
      case "pending":
        return "yellow";
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
              Connect Mailchimp
            </Heading>
            <Text color="gray.600" mb={6}>
              Connect your Mailchimp account to manage email marketing campaigns, audiences, and automations.
            </Text>
          </Box>

          <Card maxW="md" w="full">
            <CardBody>
              <VStack spacing={4}>
                <Box textAlign="center">
                  <Icon as={EmailIcon} w={12} h={12} color="blue.500" mb={4} />
                  <Heading size="md">Mailchimp Integration</Heading>
                  <Text color="gray.600" mt={2}>
                    Email marketing and automation platform
                  </Text>
                </Box>

                <Button
                  colorScheme="blue"
                  size="lg"
                  w="full"
                  onClick={onConnectModalOpen}
                >
                  Connect Mailchimp
                </Button>
              </VStack>
            </CardBody>
          </Card>
        </VStack>

        {/* Connect Modal */}
        <Modal isOpen={isConnectModalOpen} onClose={onConnectModalClose}>
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Connect Mailchimp</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <Text mb={4}>
                Connect your Mailchimp account using your API key and server prefix.
              </Text>

              <FormControl mb={4}>
                <FormLabel>Server Prefix</FormLabel>
                <Input
                  placeholder="us1"
                  value={serverPrefix}
                  onChange={(e) => setServerPrefix(e.target.value)}
                />
                <Text fontSize="sm" color="gray.600" mt={1}>
                  Your Mailchimp server prefix (e.g., "us1" for accounts in the US)
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
                  Find your API key in Mailchimp Account settings
                </Text>
              </FormControl>

              <Alert status="info" mb={4}>
                <AlertIcon />
                <Box>
                  <AlertTitle>API Authentication</AlertTitle>
                  <AlertDescription>
                    Mailchimp uses API key authentication with server-specific endpoints.
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
        <Text mt={4}>Loading Mailchimp data...</Text>
      </Box>
    );
  }

  return (
    <Box p={6}>
      {/* Header */}
      <Flex justify="space-between" align="center" mb={6}>
        <Box>
          <Heading size="lg">Mailchimp</Heading>
          <Text color="gray.600">Email marketing and automation platform</Text>
        </Box>
        <Button colorScheme="blue" onClick={loadMailchimpData}>
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
              placeholder="Search campaigns, contacts..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSearch()}
            />
          </InputGroup>
        </CardBody>
      </Card>

      {/* Navigation Tabs */}
      <Flex mb={6} borderBottom="1px" borderColor="gray.200">
        {["dashboard", "audiences", "campaigns", "automations", "templates"].map((tab) => (
          <Button
            key={tab}
            variant="ghost"
            mr={2}
            colorScheme={activeTab === tab ? "blue" : "gray"}
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
                  <StatLabel>Total Contacts</StatLabel>
                  <StatNumber>{formatNumber(stats.total_contacts)}</StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
                    8.2%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Open Rate</StatLabel>
                  <StatNumber>{formatPercentage(stats.open_rate || 0)}</StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
                    2.1%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Click Rate</StatLabel>
                  <StatNumber>{formatPercentage(stats.click_rate || 0)}</StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
                    1.5%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
          <GridItem>
            <Card>
              <CardBody>
                <Stat>
                  <StatLabel>Revenue</StatLabel>
                  <StatNumber>${(stats.revenue || 0).toLocaleString()}</StatNumber>
                  <StatHelpText>
                    <StatArrow type="increase" />
                    12.8%
                  </StatHelpText>
                </Stat>
              </CardBody>
            </Card>
          </GridItem>
        </Grid>
      )}

      {/* Audiences Tab */}
      {activeTab === "audiences" && (
        <Card>
          <CardHeader>
            <Flex justify="space-between" align="center">
              <Heading size="md">Audiences ({audiences.length})</Heading>
              <Button colorScheme="blue" size="sm" onClick={onCreateCampaignModalOpen}>
                Create Campaign
              </Button>
            </Flex>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>Status</Th>
                  <Th>Type</Th>
                  <Th>Recipients</Th>
                  <Th>Emails Sent</Th>
                  <Th>Open Rate</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {campaigns.map((campaign) => (
                  <Tr key={campaign.id}>
                    <Td fontWeight="medium">{campaign.settings.subject_line}</Td>
                    <Td>
                      <Badge colorScheme={getStatusColor(campaign.status)}>
                        {campaign.status}
                      </Badge>
                    </Td>
                    <Td>{campaign.type}</Td>
                    <Td>{campaign.recipients.list_name}</Td>
                    <Td>{formatNumber(campaign.emails_sent)}</Td>
                    <Td>
                      {campaign.report_summary ? formatPercentage(campaign.report_summary.open_rate) : "N/A"}
                    </Td>
                    <Td>
                      <Button
                        size="sm"
                        colorScheme="blue"
                        variant="ghost"
                        onClick={() => {
                          setSelectedCampaign(campaign);
                          onCampaignModalOpen();
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

      {/* Audiences Tab */}
      {activeTab === "audiences" && (
        <Card>
          <CardHeader>
            <Heading size="md">Audiences ({audiences.length})</Heading>
          </CardHeader>
          <CardBody>
            <Grid templateColumns="repeat(3, 1fr)" gap={6}>
              {audiences.map((audience) => (
                <GridItem key={audience.id}>
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Heading size="sm">{audience.name}</Heading>
                        <Text color="gray.600" fontSize="sm">
                          {audience.permission_reminder}
                        </Text>
                        <HStack spacing={4}>
                          <Badge colorScheme="green">
                            {formatNumber(audience.member_count)} members
                          </Badge>
                          <Badge colorScheme="red">
                            {formatNumber(audience.unsubscribe_count)} unsubscribed
                          </Badge>
                        </HStack>
                        {audience.stats && (
                          <VStack align="start" spacing={1} w="full">
                            <Text fontSize="sm">
                              <strong>Open Rate:</strong> {formatPercentage(audience.stats.open_rate || 0)}
                            </Text>
                            <Text fontSize="sm">
                              <strong>Click Rate:</strong> {formatPercentage(audience.stats.click_rate || 0)}
                            </Text>
                          </VStack>
                        )}
                        <HStack spacing={2}>
                          <Button
                            size="sm"
                            colorScheme="blue"
                            variant="ghost"
                            onClick={() => {
                              setSelectedAudience(audience);
                              onAudienceModalOpen();
                            }}
                          >
                            View
                          </Button>
                          <Button
                            size="sm"
                            colorScheme="green"
                            variant="ghost"
                            onClick={() => {
                              setSelectedAudience(audience);
                              loadAudienceContacts(audience.id);
                              setActiveTab("contacts");
                            }}
                          >
                            View Contacts
                          </Button>
                        </HStack>
                      </VStack>
                    </CardBody>
                  </Card>
                </GridItem>
              ))}
            </Grid>
          </CardBody>
        </Card>
      )}

      {/* Contacts Tab */}
      {activeTab === "contacts" && (
        <Card>
          <CardHeader>
            <Flex justify="space-between" align="center">
              <Heading size="md">Contacts ({contacts.length})</Heading>
              <Button colorScheme="blue" size="sm" onClick={onCreateContactModalOpen}>
                Add Contact
              </Button>
            </Flex>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Email</Th>
                  <Th>Name</Th>
                  <Th>Status</Th>
                  <Th>Member Rating</Th>
                  <Th>VIP</Th>
                  <Th>Last Changed</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {contacts.map((contact) => (
                  <Tr key={contact.id}>
                    <Td fontWeight="medium">{contact.email_address}</Td>
                    <Td>{contact.full_name || "Unknown"}</Td>
                    <Td>
                      <Badge colorScheme={getContactStatusColor(contact.status)}>
                        {contact.status}
                      </Badge>
                    </Td>
                    <Td>
                      <HStack>
                        {[...Array(5)].map((_, i) => (
                          <StarIcon
                            key={i}
                            color={i < contact.member_rating ? "yellow.400" : "gray.300"}
                            boxSize={3}
                          />
                        ))}
                      </HStack>
                    </Td>
                    <Td>
                      <Badge colorScheme={contact.vip ? "purple" : "gray"}>
                        {contact.vip ? "VIP" : "Standard"}
                      </Badge>
                    </Td>
                    <Td>{contact.last_changed ? formatDate(contact.last_changed) : "Never"}</Td>
                    <Td>
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
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>
      )}

      {/* Automations Tab */}
      {activeTab === "automations" && (
        <Card>
          <CardHeader>
            <Heading size="md">Automations ({automations.length})</Heading>
          </CardHeader>
          <CardBody>
            <Grid templateColumns="repeat(2, 1fr)" gap={6}>
              {automations.map((automation) => (
                <GridItem key={automation.id}>
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Heading size="sm">{automation.settings.title}</Heading>
                        <Text color="gray.600" fontSize="sm">
                          {automation.recipients.list_name}
                        </Text>
                        <Badge colorScheme={getStatusColor(automation.status)}>
                          {automation.status}
                        </Badge>
                        <Text fontSize="sm">
                          <strong>Emails Sent:</strong> {formatNumber(automation.emails_sent)}
                        </Text>
                        {automation.report_summary && (
                          <VStack align="start" spacing={1} w="full">
                            <Text fontSize="sm">
                              <strong>Open Rate:</strong> {formatPercentage(automation.report_summary.open_rate || 0)}
                            </Text>
                            <Text fontSize="sm">
                              <strong>Click Rate:</strong> {formatPercentage(automation.report_summary.click_rate || 0)}
                            </Text>
                          </VStack>
                        )}
                        <Text fontSize="sm">
                          Created: {formatDate(automation.create_time)}
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

      {/* Templates Tab */}
      {activeTab === "templates" && (
        <Card>
          <CardHeader>
            <Heading size="md">Templates ({templates.length})</Heading>
          </CardHeader>
          <CardBody>
            <Grid templateColumns="repeat(3, 1fr)" gap={6}>
              {templates.map((template) => (
                <GridItem key={template.id}>
                  <Card>
                    <CardBody>
                      <VStack align="start" spacing={3}>
                        <Heading size="sm">{template.name}</Heading>
                        <Text color="gray.600" fontSize="sm">
                          {template.category || "General"}
                        </Text>
                        <HStack spacing={2}>
                          <Badge colorScheme={template.drag_and_drop ? "green" : "gray"}>
                            {template.drag_and_drop ? "Drag & Drop" : "Code"}
                          </Badge>
                          <Badge colorScheme={template.responsive ? "blue" : "gray"}>
                            {template.responsive ? "Responsive" : "Fixed"}
                          </Badge>
                          <Badge colorScheme={template.active ? "green" : "red"}>
                            {template.active ? "Active" : "Inactive"}
                          </Badge>
                        </HStack>
                        <Text fontSize="sm">
                          Created: {formatDate(template.date_created)}
                        </Text>
                        {template.date_edited && (
                          <Text fontSize="sm">
                            Edited: {formatDate(template.date_edited)}
                          </Text>
                        )}
                      </VStack>
                    </CardBody>
                  </Card>
                </GridItem>
              ))}
            </Grid>
          </CardBody>
        </Card>
      )}

      {/* Audience Detail Modal */}
      <Modal isOpen={isAudienceModalOpen} onClose={onAudienceModalClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Audience Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedAudience && (
              <VStack spacing={4} align="start">
                <Box>
                  <Text fontWeight="bold">Name</Text>
                  <Text>{selectedAudience.name}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Permission Reminder</Text>
                  <Text>{selectedAudience.permission_reminder}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Member Count</Text>
                  <Text>{formatNumber(selectedAudience.member_count)}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Unsubscribe Count</Text>
                  <Text>{formatNumber(selectedAudience.unsubscribe_count)}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Contact Information</Text>
                  <VStack align="start" spacing={1} mt={1}>
                    <Text>Company: {selectedAudience.contact.company}</Text>
                    <Text>Address: {selectedAudience.contact.address1}</Text>
                    <Text>City: {selectedAudience.contact.city}</Text>
                    <Text>State: {selectedAudience.contact.state}</Text>
                    <Text>Country: {selectedAudience.contact.country}</Text>
                  </VStack>
                </Box>
                {selectedAudience.stats && (
                  <Box>
                    <Text fontWeight="bold">Performance Metrics</Text>
                    <VStack align="start" spacing={1} mt={1}>
                      <Text>Open Rate: {formatPercentage(selectedAudience.stats.open_rate || 0)}</Text>
                      <Text>Click Rate: {formatPercentage(selectedAudience.stats.click_rate || 0)}</Text>
                      <Text>Subscribe Rate: {formatPercentage(selectedAudience.stats.sub_rate || 0)}</Text>
                      <Text>Unsubscribe Rate: {formatPercentage(selectedAudience.stats.unsub_rate || 0)}</Text>
                    </VStack>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" onClick={onAudienceModalClose}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Campaign Detail Modal */}
      <Modal isOpen={isCampaignModalOpen} onClose={onCampaignModalClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Campaign Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedCampaign && (
              <VStack spacing={4} align="start">
                <Box>
                  <Text fontWeight="bold">Subject Line</Text>
                  <Text>{selectedCampaign.settings.subject_line}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Status</Text>
                  <Badge colorScheme={getStatusColor(selectedCampaign.status)}>
                    {selectedCampaign.status}
                  </Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold">Type</Text>
                  <Text>{selectedCampaign.type}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Recipients</Text>
                  <Text>{selectedCampaign.recipients.list_name}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Emails Sent</Text>
                  <Text>{formatNumber(selectedCampaign.emails_sent)}</Text>
                </Box>
                {selectedCampaign.send_time && (
                  <Box>
                    <Text fontWeight="bold">Send Time</Text>
                    <Text>{formatDate(selectedCampaign.send_time)}</Text>
                  </Box>
                )}
                {selectedCampaign.report_summary && (
                  <Box>
                    <Text fontWeight="bold">Performance Metrics</Text>
                    <VStack align="start" spacing={1} mt={1}>
                      <Text>Opens: {formatNumber(selectedCampaign.report_summary.opens || 0)}</Text>
                      <Text>Unique Opens: {formatNumber(selectedCampaign.report_summary.unique_opens || 0)}</Text>
                      <Text>Open Rate: {formatPercentage(selectedCampaign.report_summary.open_rate || 0)}</Text>
                      <Text>Clicks: {formatNumber(selectedCampaign.report_summary.clicks || 0)}</Text>
                      <Text>Click Rate: {formatPercentage(selectedCampaign.report_summary.click_rate || 0)}</Text>
                    </VStack>
                  </Box>
                )}
                {selectedCampaign.archive_url && (
                  <Box>
                    <Text fontWeight="bold">Archive URL</Text>
                    <Text color="blue.500" cursor="pointer" onClick={() => window.open(selectedCampaign.archive_url, '_blank')}>
                      View Campaign Archive
                    </Text>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" onClick={onCampaignModalClose}>
              Close
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>

      {/* Contact Detail Modal */}
      <Modal isOpen={isContactModalOpen} onClose={onContactModalClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Contact Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedContact && (
              <VStack spacing={4} align="start">
                <Box>
                  <Text fontWeight="bold">Email Address</Text>
                  <Text>{selectedContact.email_address}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Full Name</Text>
                  <Text>{selectedContact.full_name || "Unknown"}</Text>
                </Box>
                <Box>
                  <Text fontWeight="bold">Status</Text>
                  <Badge colorScheme={getContactStatusColor(selectedContact.status)}>
                    {selectedContact.status}
                  </Badge>
                </Box>
                <Box>
                  <Text fontWeight="bold">Member Rating</Text>
                  <HStack>
                    {[...Array(5)].map((_, i) => (
                      <StarIcon
                        key={i}
                        color={i < selectedContact.member_rating ? "yellow.400" : "gray.300"}
                        boxSize={4}
                      />
                    ))}
                  </HStack>
                </Box>
                <Box>
                  <Text fontWeight="bold">VIP Status</Text>
                  <Badge colorScheme={selectedContact.vip ? "purple" : "gray"}>
                    {selectedContact.vip ? "VIP" : "Standard"}
                  </Badge>
                </Box>
                {selectedContact.timestamp_signup && (
                  <Box>
                    <Text fontWeight="bold">Signup Date</Text>
                    <Text>{formatDate(selectedContact.timestamp_signup)}</Text>
                  </Box>
                )}
                {selectedContact.email_client && (
                  <Box>
                    <Text fontWeight="bold">Email Client</Text>
                    <Text>{selectedContact.email_client}</Text>
                  </Box>
                )}
                {selectedContact.tags.length > 0 && (
                  <Box>
                    <Text fontWeight="bold">Tags</Text>
                    <HStack spacing={2} mt={1}>
                      {selectedContact.tags.map((tag) => (
                        <Badge key={tag} colorScheme="blue">
                          {tag}
                        </Badge>
                      ))}
                    </HStack>
                  </Box>
                )}
              </VStack>
            )}
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" onClick={onContact
