/**
 * Salesforce Integration Page
 * Complete Salesforce integration with comprehensive CRM functionality
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
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
} from "@chakra-ui/react";
import {
  CalendarIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  ExternalLinkIcon,
  AddIcon,
  SearchIcon,
  SettingsIcon,
  RepeatIcon,
  PhoneIcon,
  MoneyIcon,
  UserIcon,
  BuildingIcon,
} from "@chakra-ui/icons";

interface SalesforceAccount {
  id: string;
  name: string;
  type: string;
  website?: string;
  phone?: string;
  industry?: string;
  annualRevenue?: number;
  billingCity?: string;
  billingState?: string;
  billingCountry?: string;
  ownerName?: string;
  createdDate: string;
  lastActivityDate: string;
}

interface SalesforceContact {
  id: string;
  firstName: string;
  lastName: string;
  email?: string;
  phone?: string;
  title?: string;
  accountId?: string;
  accountName?: string;
  leadSource?: string;
  ownerName?: string;
  createdDate: string;
  lastActivityDate: string;
}

interface SalesforceOpportunity {
  id: string;
  name: string;
  accountId?: string;
  accountName?: string;
  amount?: number;
  stage: string;
  probability: number;
  closeDate: string;
  type?: string;
  leadSource?: string;
  ownerName?: string;
  createdDate: string;
  lastModified: string;
}

interface SalesforceLead {
  id: string;
  firstName: string;
  lastName: string;
  email?: string;
  phone?: string;
  company?: string;
  title?: string;
  leadSource?: string;
  status: string;
  rating?: string;
  annualRevenue?: number;
  ownerName?: string;
  createdDate: string;
  lastModified: string;
}

const SalesforceIntegration: React.FC = () => {
  const [accounts, setAccounts] = useState<SalesforceAccount[]>([]);
  const [contacts, setContacts] = useState<SalesforceContact[]>([]);
  const [opportunities, setOpportunities] = useState<SalesforceOpportunity[]>([]);
  const [leads, setLeads] = useState<SalesforceLead[]>([]);
  const [loading, setLoading] = useState({
    accounts: false,
    contacts: false,
    opportunities: false,
    leads: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAccount, setSelectedAccount] = useState("");

  const { isOpen, onOpen, onClose } = useDisclosure();
  const [newAccount, setNewAccount] = useState({
    name: "",
    type: "",
    website: "",
    phone: "",
    industry: "",
    annualRevenue: 0,
  });

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/salesforce/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
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

  // Load Salesforce data
  const loadAccounts = async () => {
    setLoading((prev) => ({ ...prev, accounts: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current", // Will be replaced with actual user ID
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setAccounts(data.data?.accounts || []);
      }
    } catch (error) {
      console.error("Failed to load accounts:", error);
      toast({
        title: "Error",
        description: "Failed to load accounts from Salesforce",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, accounts: false }));
    }
  };

  const loadContacts = async () => {
    setLoading((prev) => ({ ...prev, contacts: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setContacts(data.data?.contacts || []);
      }
    } catch (error) {
      console.error("Failed to load contacts:", error);
    } finally {
      setLoading((prev) => ({ ...prev, contacts: false }));
    }
  };

  const loadOpportunities = async () => {
    setLoading((prev) => ({ ...prev, opportunities: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/opportunities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setOpportunities(data.data?.opportunities || []);
      }
    } catch (error) {
      console.error("Failed to load opportunities:", error);
    } finally {
      setLoading((prev) => ({ ...prev, opportunities: false }));
    }
  };

  const loadLeads = async () => {
    setLoading((prev) => ({ ...prev, leads: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setLeads(data.data?.leads || []);
      }
    } catch (error) {
      console.error("Failed to load leads:", error);
    } finally {
      setLoading((prev) => ({ ...prev, leads: false }));
    }
  };

  // Create new account
  const createAccount = async () => {
    try {
      const response = await fetch("/api/integrations/salesforce/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          name: newAccount.name,
          type: newAccount.type,
          website: newAccount.website,
          phone: newAccount.phone,
          industry: newAccount.industry,
          annualRevenue: newAccount.annualRevenue,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Account created successfully",
          status: "success",
          duration: 3000,
        });
        onClose();
        setNewAccount({ name: "", type: "", website: "", phone: "", industry: "", annualRevenue: 0 });
        loadAccounts();
      }
    } catch (error) {
      console.error("Failed to create account:", error);
      toast({
        title: "Error",
        description: "Failed to create account",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredAccounts = accounts.filter((account) =>
    account.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    account.type?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    account.industry?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredContacts = contacts.filter((contact) =>
    `${contact.firstName} ${contact.lastName}`.toLowerCase().includes(searchQuery.toLowerCase()) ||
    contact.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    contact.title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredOpportunities = opportunities.filter((opportunity) =>
    opportunity.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    opportunity.stage?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    opportunity.accountName?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredLeads = leads.filter((lead) =>
    `${lead.firstName} ${lead.lastName}`.toLowerCase().includes(searchQuery.toLowerCase()) ||
    lead.company?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    lead.status?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const totalAccounts = accounts.length;
  const totalContacts = contacts.length;
  const totalOpportunities = opportunities.length;
  const totalLeads = leads.length;
  const totalOpportunityValue = opportunities.reduce((sum, opp) => sum + (opp.amount || 0), 0);

  useEffect(() => {
    checkConnection();
    if (connected) {
      loadAccounts();
      loadContacts();
      loadOpportunities();
      loadLeads();
    }
  }, [connected]);

  const getStageColor = (stage: string) => {
    switch (stage?.toLowerCase()) {
      case "prospecting":
        return "gray";
      case "qualification":
        return "yellow";
      case "needs analysis":
        return "orange";
      case "value proposition":
        return "blue";
      case "id. decision makers":
        return "purple";
      case "perception analysis":
        return "pink";
      case "proposal/price quote":
        return "teal";
      case "negotiation/review":
        return "cyan";
      case "closed won":
        return "green";
      case "closed lost":
        return "red";
      default:
        return "gray";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status?.toLowerCase()) {
      case "open":
        return "blue";
      case "contacted":
        return "yellow";
      case "qualified":
        return "green";
      case "unqualified":
        return "red";
      case "converted":
        return "purple";
      case "dead":
        return "gray";
      default:
        return "gray";
    }
  };

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1400px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={4}>
          <HStack spacing={4}>
            <Icon as={BuildingIcon} w={8} h={8} color="blue.500" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Salesforce Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Customer Relationship Management platform
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
                <WarningIcon mr={1} />
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
        </VStack>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardBody>
              <VStack spacing={6} py={8}>
                <Icon as={BuildingIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Salesforce</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Salesforce account to start managing customers,
                    accounts, and opportunities
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ExternalLinkIcon />}
                  onClick={() =>
                    (window.location.href = "/api/integrations/salesforce/auth/start")
                  }
                >
                  Connect Salesforce Account
                </Button>
              </VStack>
            </CardBody>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Stats Overview */}
            <SimpleGrid columns={{ base: 1, md: 2, lg: 4 }} spacing={6}>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Total Accounts</StatLabel>
                    <StatNumber>{totalAccounts}</StatNumber>
                    <StatHelpText>Customer accounts</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Total Contacts</StatLabel>
                    <StatNumber>{totalContacts}</StatNumber>
                    <StatHelpText>Customer contacts</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Opportunities</StatLabel>
                    <StatNumber>{totalOpportunities}</StatNumber>
                    <StatHelpText>Active deals</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Pipeline Value</StatLabel>
                    <StatNumber>${totalOpportunityValue.toLocaleString()}</StatNumber>
                    <StatHelpText>Total opportunity value</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Accounts</Tab>
                <Tab>Contacts</Tab>
                <Tab>Opportunities</Tab>
                <Tab>Leads</Tab>
              </TabList>

              <TabPanels>
                {/* Accounts Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    {/* Filters and Actions */}
                    <Card>
                      <CardBody>
                        <Stack
                          direction={{ base: "column", md: "row" }}
                          spacing={4}
                        >
                          <Input
                            placeholder="Search accounts..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            leftElement={<SearchIcon />}
                          />
                          <Spacer />
                          <Button
                            colorScheme="blue"
                            leftIcon={<AddIcon />}
                            onClick={onOpen}
                          >
                            New Account
                          </Button>
                        </Stack>
                      </CardBody>
                    </Card>

                    {/* Accounts Table */}
                    <Card>
                      <CardBody>
                        {loading.accounts ? (
                          <VStack spacing={4} py={8}>
                            <Text>Loading accounts...</Text>
                            <Progress size="sm" isIndeterminate width="100%" />
                          </VStack>
                        ) : filteredAccounts.length === 0 ? (
                          <VStack spacing={4} py={8}>
                            <Icon
                              as={BuildingIcon}
                              w={12}
                              h={12}
                              color="gray.400"
                            />
                            <Text color="gray.600">No accounts found</Text>
                            <Button
                              variant="outline"
                              leftIcon={<AddIcon />}
                              onClick={onOpen}
                            >
                              Create Your First Account
                            </Button>
                          </VStack>
                        ) : (
                          <Box overflowX="auto">
                            <Table variant="simple">
                              <Thead>
                                <Tr>
                                  <Th>Name</Th>
                                  <Th>Type</Th>
                                  <Th>Industry</Th>
                                  <Th>Revenue</Th>
                                  <Th>Owner</Th>
                                  <Th>Actions</Th>
                                </Tr>
                              </Thead>
                              <Tbody>
                                {filteredAccounts.map((account) => (
                                  <Tr key={account.id}>
                                    <Td>
                                      <VStack align="start" spacing={1}>
                                        <Text fontWeight="medium">
                                          {account.name}
                                        </Text>
                                        {account.website && (
                                          <Text
                                            fontSize="sm"
                                            color="gray.600"
                                            noOfLines={1}
                                          >
                                            {account.website}
                                          </Text>
                                        )}
                                      </VStack>
                                    </Td>
                                    <Td>
                                      <Badge colorScheme="blue" size="sm">
                                        {account.type}
                                      </Badge>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{account.industry || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {account.annualRevenue
                                          ? `$${account.annualRevenue.toLocaleString()}`
                                          : '-'}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{account.ownerName || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                      >
                                        View
                                      </Button>
                                    </Td>
                                  </Tr>
                                ))}
                              </Tbody>
                            </Table>
                          </Box>
                        )}
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Contacts Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <Input
                          placeholder="Search contacts..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          leftElement={<SearchIcon />}
                        />
                      </CardBody>
                    </Card>

                    <Card>
                      <CardBody>
                        {loading.contacts ? (
                          <VStack spacing={4} py={8}>
                            <Text>Loading contacts...</Text>
                            <Progress size="sm" isIndeterminate width="100%" />
                          </VStack>
                        ) : filteredContacts.length === 0 ? (
                          <VStack spacing={4} py={8}>
                            <Icon
                              as={UserIcon}
                              w={12}
                              h={12}
                              color="gray.400"
                            />
                            <Text color="gray.600">No contacts found</Text>
                          </VStack>
                        ) : (
                          <Box overflowX="auto">
                            <Table variant="simple">
                              <Thead>
                                <Tr>
                                  <Th>Name</Th>
                                  <Th>Title</Th>
                                  <Th>Email</Th>
                                  <Th>Account</Th>
                                  <Th>Owner</Th>
                                  <Th>Actions</Th>
                                </Tr>
                              </Thead>
                              <Tbody>
                                {filteredContacts.map((contact) => (
                                  <Tr key={contact.id}>
                                    <Td>
                                      <Text fontWeight="medium">
                                        {contact.firstName} {contact.lastName}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{contact.title || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{contact.email || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{contact.accountName || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{contact.ownerName || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                      >
                                        View
                                      </Button>
                                    </Td>
                                  </Tr>
                                ))}
                              </Tbody>
                            </Table>
                          </Box>
                        )}
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Opportunities Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <Input
                          placeholder="Search opportunities..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          leftElement={<SearchIcon />}
                        />
                      </CardBody>
                    </Card>

                    <Card>
                      <CardBody>
                        {loading.opportunities ? (
                          <VStack spacing={4} py={8}>
                            <Text>Loading opportunities...</Text>
                            <Progress size="sm" isIndeterminate width="100%" />
                          </VStack>
                        ) : filteredOpportunities.length === 0 ? (
                          <VStack spacing={4} py={8}>
                            <Icon
                              as={MoneyIcon}
                              w={12}
                              h={12}
                              color="gray.400"
                            />
                            <Text color="gray.600">No opportunities found</Text>
                          </VStack>
                        ) : (
                          <Box overflowX="auto">
                            <Table variant="simple">
                              <Thead>
                                <Tr>
                                  <Th>Name</Th>
                                  <Th>Account</Th>
                                  <Th>Amount</Th>
                                  <Th>Stage</Th>
                                  <Th>Close Date</Th>
                                  <Th>Owner</Th>
                                  <Th>Actions</Th>
                                </Tr>
                              </Thead>
                              <Tbody>
                                {filteredOpportunities.map((opportunity) => (
                                  <Tr key={opportunity.id}>
                                    <Td>
                                      <Text fontWeight="medium">
                                        {opportunity.name}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{opportunity.accountName || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">
                                        {opportunity.amount
                                          ? `$${opportunity.amount.toLocaleString()}`
                                          : '-'}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getStageColor(opportunity.stage)}
                                        size="sm"
                                      >
                                        <TagLabel>{opportunity.stage || '-'}</TagLabel>
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{opportunity.closeDate || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{opportunity.ownerName || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                      >
                                        View
                                      </Button>
                                    </Td>
                                  </Tr>
                                ))}
                              </Tbody>
                            </Table>
                          </Box>
                        )}
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>

                {/* Leads Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <Card>
                      <CardBody>
                        <Input
                          placeholder="Search leads..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                          leftElement={<SearchIcon />}
                        />
                      </CardBody>
                    </Card>

                    <Card>
                      <CardBody>
                        {loading.leads ? (
                          <VStack spacing={4} py={8}>
                            <Text>Loading leads...</Text>
                            <Progress size="sm" isIndeterminate width="100%" />
                          </VStack>
                        ) : filteredLeads.length === 0 ? (
                          <VStack spacing={4} py={8}>
                            <Icon
                              as={PhoneIcon}
                              w={12}
                              h={12}
                              color="gray.400"
                            />
                            <Text color="gray.600">No leads found</Text>
                          </VStack>
                        ) : (
                          <Box overflowX="auto">
                            <Table variant="simple">
                              <Thead>
                                <Tr>
                                  <Th>Name</Th>
                                  <Th>Company</Th>
                                  <Th>Email</Th>
                                  <Th>Status</Th>
                                  <Th>Rating</Th>
                                  <Th>Owner</Th>
                                  <Th>Actions</Th>
                                </Tr>
                              </Thead>
                              <Tbody>
                                {filteredLeads.map((lead) => (
                                  <Tr key={lead.id}>
                                    <Td>
                                      <Text fontWeight="medium">
                                        {lead.firstName} {lead.lastName}
                                      </Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{lead.company || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{lead.email || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getStatusColor(lead.status)}
                                        size="sm"
                                      >
                                        <TagLabel>{lead.status || '-'}</TagLabel>
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Badge colorScheme="gray" size="sm">
                                        {lead.rating || '-'}
                                      </Badge>
                                    </Td>
                                    <Td>
                                      <Text fontSize="sm">{lead.ownerName || '-'}</Text>
                                    </Td>
                                    <Td>
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        leftIcon={<ExternalLinkIcon />}
                                      >
                                        View
                                      </Button>
                                    </Td>
                                  </Tr>
                                ))}
                              </Tbody>
                            </Table>
                          </Box>
                        )}
                      </CardBody>
                    </Card>
                  </VStack>
                </TabPanel>
              </TabPanels>
            </Tabs>

            {/* Create Account Modal */}
            <Modal isOpen={isOpen} onClose={onClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create New Account</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Account Name</FormLabel>
                      <Input
                        placeholder="Account name"
                        value={newAccount.name}
                        onChange={(e) =>
                          setNewAccount({ ...newAccount, name: e.target.value })
                        }
                      />
                    </FormControl>
                    <FormControl isRequired>
                      <FormLabel>Type</FormLabel>
                      <Select
                        placeholder="Select type"
                        value={newAccount.type}
                        onChange={(e) =>
                          setNewAccount({ ...newAccount, type: e.target.value })
                        }
                      >
                        <option value="Prospect">Prospect</option>
                        <option value="Customer">Customer</option>
                        <option value="Partner">Partner</option>
                        <option value="Vendor">Vendor</option>
                      </Select>
                    </FormControl>
                    <FormControl>
                      <FormLabel>Website</FormLabel>
                      <Input
                        placeholder="https://example.com"
                        value={newAccount.website}
                        onChange={(e) =>
                          setNewAccount({ ...newAccount, website: e.target.value })
                        }
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel>Phone</FormLabel>
                      <Input
                        placeholder="+1 (555) 123-4567"
                        value={newAccount.phone}
                        onChange={(e) =>
                          setNewAccount({ ...newAccount, phone: e.target.value })
                        }
                      />
                    </FormControl>
                    <FormControl>
                      <FormLabel>Industry</FormLabel>
                      <Select
                        placeholder="Select industry"
                        value={newAccount.industry}
                        onChange={(e) =>
                          setNewAccount({ ...newAccount, industry: e.target.value })
                        }
                      >
                        <option value="Technology">Technology</option>
                        <option value="Healthcare">Healthcare</option>
                        <option value="Finance">Finance</option>
                        <option value="Retail">Retail</option>
                        <option value="Manufacturing">Manufacturing</option>
                        <option value="Education">Education</option>
                      </Select>
                    </FormControl>
                    <FormControl>
                      <FormLabel>Annual Revenue</FormLabel>
                      <Input
                        type="number"
                        placeholder="1000000"
                        value={newAccount.annualRevenue}
                        onChange={(e) =>
                          setNewAccount({
                            ...newAccount,
                            annualRevenue: parseInt(e.target.value) || 0,
                          })
                        }
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createAccount}
                    isDisabled={!newAccount.name || !newAccount.type}
                  >
                    Create Account
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>
          </>
        )}
      </VStack>
    </Box>
  );
};

export default SalesforceIntegration;