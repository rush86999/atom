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
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  Switch,
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
  Flex
} from '@chakra-ui/react';
import {
  AddIcon,
  EditIcon,
  DeleteIcon,
  ViewIcon,
  SettingsIcon,
  EmailIcon,
  PhoneIcon,
  CalendarIcon,
  CheckIcon,
  CloseIcon,
  RepeatIcon,
  ExternalLinkIcon
} from '@chakra-ui/icons';
import { hubspotSkills } from './skills/hubspotSkills';

interface HubSpotConfig {
  accessToken?: string;
  hubId?: string;
  environment: 'production' | 'sandbox';
}

interface Contact {
  id: string;
  properties: {
    email?: string;
    firstname?: string;
    lastname?: string;
    phone?: string;
    company?: string;
    lifecyclestage?: string;
    createdate?: string;
    lastmodifieddate?: string;
  };
  createdAt?: string;
  updatedAt?: string;
}

interface Company {
  id: string;
  properties: {
    name?: string;
    domain?: string;
    phone?: string;
    address?: string;
    city?: string;
    state?: string;
    country?: string;
    industry?: string;
    annualrevenue?: string;
    description?: string;
  };
}

interface Deal {
  id: string;
  properties: {
    dealname?: string;
    amount?: string;
    closedate?: string;
    dealstage?: string;
    pipeline?: string;
    hubspot_owner_id?: string;
    createdate?: string;
    closed_won?: string;
  };
}

interface Campaign {
  id: string;
  name: string;
  status: string;
  type: string;
  createdAt: string;
  updatedAt: string;
  metrics: {
    sent: number;
    delivered: number;
    opened: number;
    clicked: number;
    converted: number;
  };
}

const HubSpotIntegration: React.FC = () => {
  const [config, setConfig] = useState<HubSpotConfig>({ environment: 'production' });
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const toast = useToast();

  // Data states
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [deals, setDeals] = useState<Deal[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);

  // Modal states
  const [isContactModalOpen, setIsContactModalOpen] = useState(false);
  const [isCompanyModalOpen, setIsCompanyModalOpen] = useState(false);
  const [isDealModalOpen, setIsDealModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<any>(null);

  // Forms
  const [contactForm, setContactForm] = useState({
    email: '',
    firstname: '',
    lastname: '',
    phone: '',
    company: '',
    lifecyclestage: 'lead'
  });

  const [companyForm, setCompanyForm] = useState({
    name: '',
    domain: '',
    phone: '',
    address: '',
    city: '',
    state: '',
    country: '',
    industry: '',
    annualrevenue: '',
    description: ''
  });

  const [dealForm, setDealForm] = useState({
    dealname: '',
    amount: '',
    closedate: '',
    dealstage: 'appointmentscheduled',
    pipeline: 'default'
  });

  // Analytics state
  const [analytics, setAnalytics] = useState({
    totalContacts: 0,
    totalCompanies: 0,
    totalDeals: 0,
    totalRevenue: 0,
    conversionRate: 0
  });

  useEffect(() => {
    checkAuthentication();
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated]);

  const checkAuthentication = async () => {
    try {
      const tokens = await hubspotSkills.getStoredTokens();
      if (tokens && tokens.accessToken) {
        setIsAuthenticated(true);
        setConfig({
          accessToken: tokens.accessToken,
          hubId: tokens.hubId,
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
      const [contactsData, companiesData, dealsData, campaignsData, analyticsData] = await Promise.all([
        hubspotSkills.getContacts({ limit: 50 }),
        hubspotSkills.getCompanies({ limit: 50 }),
        hubspotSkills.getDeals({ limit: 50 }),
        hubspotSkills.getCampaigns({ limit: 20 }),
        loadAnalytics()
      ]);

      setContacts(contactsData.results || []);
      setCompanies(companiesData.results || []);
      setDeals(dealsData.results || []);
      setCampaigns(campaignsData.results || []);
      setAnalytics(analyticsData);
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

  const loadAnalytics = async () => {
    try {
      const [contactCount, companyCount, dealCount, revenueData] = await Promise.all([
        hubspotSkills.getContactCount(),
        hubspotSkills.getCompanyCount(),
        hubspotSkills.getDealCount(),
        hubspotSkills.getDealAnalytics()
      ]);

      return {
        totalContacts: contactCount || 0,
        totalCompanies: companyCount || 0,
        totalDeals: dealCount || 0,
        totalRevenue: revenueData?.totalRevenue || 0,
        conversionRate: revenueData?.conversionRate || 0
      };
    } catch (error) {
      console.error('Failed to load analytics:', error);
      return {
        totalContacts: 0,
        totalCompanies: 0,
        totalDeals: 0,
        totalRevenue: 0,
        conversionRate: 0
      };
    }
  };

  const handleAuthentication = () => {
    window.location.href = `/auth/hubspot`;
  };

  const handleCreateContact = async () => {
    try {
      setLoading(true);
      const newContact = await hubspotSkills.createContact(contactForm);
      setContacts([...contacts, newContact]);
      setIsContactModalOpen(false);
      setContactForm({
        email: '',
        firstname: '',
        lastname: '',
        phone: '',
        company: '',
        lifecyclestage: 'lead'
      });
      toast({
        title: 'Contact created',
        description: 'Contact has been created successfully',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
    } catch (error) {
      toast({
        title: 'Error creating contact',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCompany = async () => {
    try {
      setLoading(true);
      const newCompany = await hubspotSkills.createCompany(companyForm);
      setCompanies([...companies, newCompany]);
      setIsCompanyModalOpen(false);
      setCompanyForm({
        name: '',
        domain: '',
        phone: '',
        address: '',
        city: '',
        state: '',
        country: '',
        industry: '',
        annualrevenue: '',
        description: ''
      });
      toast({
        title: 'Company created',
        description: 'Company has been created successfully',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
    } catch (error) {
      toast({
        title: 'Error creating company',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDeal = async () => {
    try {
      setLoading(true);
      const newDeal = await hubspotSkills.createDeal(dealForm);
      setDeals([...deals, newDeal]);
      setIsDealModalOpen(false);
      setDealForm({
        dealname: '',
        amount: '',
        closedate: '',
        dealstage: 'appointmentscheduled',
        pipeline: 'default'
      });
      toast({
        title: 'Deal created',
        description: 'Deal has been created successfully',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
    } catch (error) {
      toast({
        title: 'Error creating deal',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const getLifecycleStageBadge = (stage: string) => {
    const colors: { [key: string]: string } = {
      lead: 'gray',
      marketingqualifiedlead: 'purple',
      salesqualifiedlead: 'blue',
      opportunity: 'yellow',
      customer: 'green',
      evangelist: 'orange'
    };
    return colors[stage] || 'gray';
  };

  const getDealStageBadge = (stage: string) => {
    const colors: { [key: string]: string } = {
      appointmentscheduled: 'gray',
      qualifiedtobuy: 'blue',
      presentation scheduled': 'purple',
      decisionmakerboughtin: 'orange',
      contractsent: 'yellow',
      closedwon: 'green',
      closedlost: 'red'
    };
    return colors[stage] || 'gray';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatCurrency = (amount: string) => {
    if (!amount) return '-';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD'
    }).format(parseFloat(amount));
  };

  if (!isAuthenticated) {
    return (
      <Box minH="100vh" bg="white" p={6}>
        <VStack spacing={8} maxW="800px" mx="auto">
          <VStack spacing={4} textAlign="center">
            <Heading size="2xl" color="orange.500">HubSpot Integration</Heading>
            <Text fontSize="xl" color="gray.600">
              Complete CRM and marketing automation platform
            </Text>
            <Text color="gray.500">
              Manage contacts, companies, deals, and marketing campaigns in one place
            </Text>
          </VStack>

          <Card bg="orange.50" borderColor="orange.200" borderWidth={2}>
            <CardBody p={8} textAlign="center">
              <VStack spacing={6}>
                <Heading size="lg" color="orange.600">Connect to HubSpot</Heading>
                <Text color="gray.600">
                  Authenticate with HubSpot to access your CRM data and marketing tools
                </Text>
                <Button
                  size="lg"
                  colorScheme="orange"
                  onClick={handleAuthentication}
                  loadingText="Connecting to HubSpot..."
                  isLoading={loading}
                >
                  <ExternalLinkIcon mr={2} />
                  Connect HubSpot Account
                </Button>
              </VStack>
            </CardBody>
          </Card>

          <SimpleGrid columns={3} spacing={6} w="full">
            <Stat>
              <StatLabel>Campaign Management</StatLabel>
              <StatNumber color="orange.500">∞</StatNumber>
              <StatHelpText>Email & automation</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Lead Generation</StatLabel>
              <StatNumber color="orange.500">AI-Powered</StatNumber>
              <StatHelpText>Smart scoring</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Sales Pipeline</StatLabel>
              <StatNumber color="orange.500">Complete</StatNumber>
              <StatHelpText>Deal tracking</StatHelpText>
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
            <Heading size="2xl" color="orange.500">HubSpot Integration</Heading>
            <Text color="gray.600">
              {config.environment === 'sandbox' ? 'Sandbox' : 'Production'} • Hub ID: {config.hubId}
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
              colorScheme="orange"
              onClick={() => window.open('https://app.hubspot.com', '_blank')}
              rightIcon={<ExternalLinkIcon />}
            >
              Open HubSpot
            </Button>
          </HStack>
        </Flex>

        {/* Analytics Dashboard */}
        <SimpleGrid columns={5} spacing={4}>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Total Contacts</StatLabel>
            <StatNumber color="orange.500">{analytics.totalContacts.toLocaleString()}</StatNumber>
          </Stat>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Total Companies</StatLabel>
            <StatNumber color="orange.500">{analytics.totalCompanies.toLocaleString()}</StatNumber>
          </Stat>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Active Deals</StatLabel>
            <StatNumber color="orange.500">{analytics.totalDeals.toLocaleString()}</StatNumber>
          </Stat>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Pipeline Revenue</StatLabel>
            <StatNumber color="green.500">{formatCurrency(analytics.totalRevenue.toString())}</StatNumber>
          </Stat>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Conversion Rate</StatLabel>
            <StatNumber color="blue.500">{analytics.conversionRate.toFixed(1)}%</StatNumber>
          </Stat>
        </SimpleGrid>

        {/* Main Content */}
        <Tabs
          index={activeTab}
          onChange={(index) => setActiveTab(index)}
          bg="white"
          rounded="lg"
          shadow="sm"
        >
          <TabList borderBottomWidth={2} borderColor="gray.200">
            <Tab _selected={{ color: 'orange.500', borderBottomColor: 'orange.500' }}>
              <AddIcon mr={2} /> Contacts
            </Tab>
            <Tab _selected={{ color: 'orange.500', borderBottomColor: 'orange.500' }}>
              <AddIcon mr={2} /> Companies
            </Tab>
            <Tab _selected={{ color: 'orange.500', borderBottomColor: 'orange.500' }}>
              <AddIcon mr={2} /> Deals
            </Tab>
            <Tab _selected={{ color: 'orange.500', borderBottomColor: 'orange.500' }}>
              <EmailIcon mr={2} /> Campaigns
            </Tab>
          </TabList>

          <TabPanels>
            {/* Contacts Tab */}
            <TabPanel p={6}>
              <HStack justify="space-between" mb={6}>
                <Heading size="lg">Contacts</Heading>
                <Button
                  colorScheme="orange"
                  onClick={() => setIsContactModalOpen(true)}
                  leftIcon={<AddIcon />}
                >
                  Add Contact
                </Button>
              </HStack>

              <TableContainer>
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Name</Th>
                      <Th>Email</Th>
                      <Th>Phone</Th>
                      <Th>Company</Th>
                      <Th>Lifecycle Stage</Th>
                      <Th>Created</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {contacts.map((contact) => (
                      <Tr key={contact.id}>
                        <Td>
                          <Text fontWeight="medium">
                            {contact.properties.firstname} {contact.properties.lastname}
                          </Text>
                        </Td>
                        <Td>
                          <HStack>
                            <EmailIcon color="gray.400" />
                            <Text>{contact.properties.email || '-'}</Text>
                          </HStack>
                        </Td>
                        <Td>
                          <HStack>
                            <PhoneIcon color="gray.400" />
                            <Text>{contact.properties.phone || '-'}</Text>
                          </HStack>
                        </Td>
                        <Td>{contact.properties.company || '-'}</Td>
                        <Td>
                          <Badge colorScheme={getLifecycleStageBadge(contact.properties.lifecyclestage)}>
                            {contact.properties.lifecyclestage?.replace(/([A-Z])/g, ' $1').trim() || 'Lead'}
                          </Badge>
                        </Td>
                        <Td>{formatDate(contact.properties.createdate)}</Td>
                        <Td>
                          <Menu>
                            <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                            <MenuList>
                              <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                              <MenuItem icon={<EditIcon />}>Edit Contact</MenuItem>
                              <MenuItem icon={<DeleteIcon />}>Delete Contact</MenuItem>
                            </MenuList>
                          </Menu>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            </TabPanel>

            {/* Companies Tab */}
            <TabPanel p={6}>
              <HStack justify="space-between" mb={6}>
                <Heading size="lg">Companies</Heading>
                <Button
                  colorScheme="orange"
                  onClick={() => setIsCompanyModalOpen(true)}
                  leftIcon={<AddIcon />}
                >
                  Add Company
                </Button>
              </HStack>

              <TableContainer>
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Company Name</Th>
                      <Th>Domain</Th>
                      <Th>Industry</Th>
                      <Th>Phone</Th>
                      <Th>Annual Revenue</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {companies.map((company) => (
                      <Tr key={company.id}>
                        <Td>
                          <Text fontWeight="medium">{company.properties.name}</Text>
                        </Td>
                        <Td>{company.properties.domain || '-'}</Td>
                        <Td>{company.properties.industry || '-'}</Td>
                        <Td>
                          <HStack>
                            <PhoneIcon color="gray.400" />
                            <Text>{company.properties.phone || '-'}</Text>
                          </HStack>
                        </Td>
                        <Td>{formatCurrency(company.properties.annualrevenue)}</Td>
                        <Td>
                          <Menu>
                            <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                            <MenuList>
                              <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                              <MenuItem icon={<EditIcon />}>Edit Company</MenuItem>
                              <MenuItem icon={<DeleteIcon />}>Delete Company</MenuItem>
                            </MenuList>
                          </Menu>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            </TabPanel>

            {/* Deals Tab */}
            <TabPanel p={6}>
              <HStack justify="space-between" mb={6}>
                <Heading size="lg">Deals</Heading>
                <Button
                  colorScheme="orange"
                  onClick={() => setIsDealModalOpen(true)}
                  leftIcon={<AddIcon />}
                >
                  Add Deal
                </Button>
              </HStack>

              <TableContainer>
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Deal Name</Th>
                      <Th>Amount</Th>
                      <Th>Stage</Th>
                      <Th>Pipeline</Th>
                      <Th>Close Date</Th>
                      <Th>Actions</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {deals.map((deal) => (
                      <Tr key={deal.id}>
                        <Td>
                          <Text fontWeight="medium">{deal.properties.dealname}</Text>
                        </Td>
                        <Td>{formatCurrency(deal.properties.amount)}</Td>
                        <Td>
                          <Badge colorScheme={getDealStageBadge(deal.properties.dealstage)}>
                            {deal.properties.dealstage?.replace(/([A-Z])/g, ' $1').trim() || 'Unknown'}
                          </Badge>
                        </Td>
                        <Td>{deal.properties.pipeline || '-'}</Td>
                        <Td>
                          <HStack>
                            <CalendarIcon color="gray.400" />
                            <Text>{deal.properties.closedate ? formatDate(deal.properties.closedate) : '-'}</Text>
                          </HStack>
                        </Td>
                        <Td>
                          <Menu>
                            <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                            <MenuList>
                              <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                              <MenuItem icon={<EditIcon />}>Edit Deal</MenuItem>
                              <MenuItem icon={<DeleteIcon />}>Delete Deal</MenuItem>
                            </MenuList>
                          </Menu>
                        </Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </TableContainer>
            </TabPanel>

            {/* Campaigns Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <HStack justify="space-between" w="full">
                  <Heading size="lg">Marketing Campaigns</Heading>
                  <Button
                    colorScheme="orange"
                    onClick={() => window.open('https://app.hubspot.com/marketing', '_blank')}
                    rightIcon={<ExternalLinkIcon />}
                  >
                    Manage Campaigns
                  </Button>
                </HStack>

                <SimpleGrid columns={3} spacing={6} w="full">
                  {campaigns.map((campaign) => (
                    <Card key={campaign.id} borderWidth={1} borderColor="gray.200">
                      <CardBody>
                        <VStack align="start" spacing={4}>
                          <Heading size="sm">{campaign.name}</Heading>
                          <HStack>
                            <Badge colorScheme={campaign.status === 'active' ? 'green' : 'gray'}>
                              {campaign.status}
                            </Badge>
                            <Badge colorScheme="orange">{campaign.type}</Badge>
                          </HStack>
                          <Divider />
                          <VStack align="start" spacing={2} w="full">
                            <HStack justify="space-between" w="full">
                              <Text fontSize="sm" color="gray.600">Sent</Text>
                              <Text fontWeight="bold">{campaign.metrics.sent.toLocaleString()}</Text>
                            </HStack>
                            <HStack justify="space-between" w="full">
                              <Text fontSize="sm" color="gray.600">Opened</Text>
                              <Text fontWeight="bold">{campaign.metrics.opened.toLocaleString()}</Text>
                            </HStack>
                            <HStack justify="space-between" w="full">
                              <Text fontSize="sm" color="gray.600">Clicked</Text>
                              <Text fontWeight="bold">{campaign.metrics.clicked.toLocaleString()}</Text>
                            </HStack>
                            <HStack justify="space-between" w="full">
                              <Text fontSize="sm" color="gray.600">Converted</Text>
                              <Text fontWeight="bold" color="green.500">{campaign.metrics.converted.toLocaleString()}</Text>
                            </HStack>
                          </VStack>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Contact Modal */}
        <Modal isOpen={isContactModalOpen} onClose={() => setIsContactModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Add New Contact</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>First Name</FormLabel>
                  <Input
                    value={contactForm.firstname}
                    onChange={(e) => setContactForm({ ...contactForm, firstname: e.target.value })}
                    placeholder="John"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Last Name</FormLabel>
                  <Input
                    value={contactForm.lastname}
                    onChange={(e) => setContactForm({ ...contactForm, lastname: e.target.value })}
                    placeholder="Doe"
                  />
                </FormControl>
                <FormControl isRequired>
                  <FormLabel>Email</FormLabel>
                  <Input
                    type="email"
                    value={contactForm.email}
                    onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                    placeholder="john.doe@example.com"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Phone</FormLabel>
                  <Input
                    value={contactForm.phone}
                    onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })}
                    placeholder="+1 (555) 123-4567"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Company</FormLabel>
                  <Input
                    value={contactForm.company}
                    onChange={(e) => setContactForm({ ...contactForm, company: e.target.value })}
                    placeholder="Acme Corporation"
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsContactModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={handleCreateContact}
                isLoading={loading}
              >
                Create Contact
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Company Modal */}
        <Modal isOpen={isCompanyModalOpen} onClose={() => setIsCompanyModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Add New Company</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Company Name</FormLabel>
                  <Input
                    value={companyForm.name}
                    onChange={(e) => setCompanyForm({ ...companyForm, name: e.target.value })}
                    placeholder="Acme Corporation"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Domain</FormLabel>
                  <Input
                    value={companyForm.domain}
                    onChange={(e) => setCompanyForm({ ...companyForm, domain: e.target.value })}
                    placeholder="acme.com"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Phone</FormLabel>
                  <Input
                    value={companyForm.phone}
                    onChange={(e) => setCompanyForm({ ...companyForm, phone: e.target.value })}
                    placeholder="+1 (555) 123-4567"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Industry</FormLabel>
                  <Input
                    value={companyForm.industry}
                    onChange={(e) => setCompanyForm({ ...companyForm, industry: e.target.value })}
                    placeholder="Technology"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Annual Revenue</FormLabel>
                  <NumberInput>
                    <NumberInputField
                      value={companyForm.annualrevenue}
                      onChange={(value) => setCompanyForm({ ...companyForm, annualrevenue: value })}
                      placeholder="1000000"
                    />
                    <NumberInputStepper />
                  </NumberInput>
                </FormControl>
                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={companyForm.description}
                    onChange={(e) => setCompanyForm({ ...companyForm, description: e.target.value })}
                    placeholder="Company description..."
                    rows={3}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsCompanyModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={handleCreateCompany}
                isLoading={loading}
              >
                Create Company
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Deal Modal */}
        <Modal isOpen={isDealModalOpen} onClose={() => setIsDealModalOpen(false)} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Add New Deal</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl isRequired>
                  <FormLabel>Deal Name</FormLabel>
                  <Input
                    value={dealForm.dealname}
                    onChange={(e) => setDealForm({ ...dealForm, dealname: e.target.value })}
                    placeholder="New Product Sale"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Amount</FormLabel>
                  <NumberInput>
                    <NumberInputField
                      value={dealForm.amount}
                      onChange={(value) => setDealForm({ ...dealForm, amount: value })}
                      placeholder="50000"
                    />
                    <NumberInputStepper />
                  </NumberInput>
                </FormControl>
                <FormControl>
                  <FormLabel>Close Date</FormLabel>
                  <Input
                    type="date"
                    value={dealForm.closedate}
                    onChange={(e) => setDealForm({ ...dealForm, closedate: e.target.value })}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Stage</FormLabel>
                  <Input
                    value={dealForm.dealstage}
                    onChange={(e) => setDealForm({ ...dealForm, dealstage: e.target.value })}
                    placeholder="appointmentscheduled"
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsDealModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                colorScheme="orange"
                onClick={handleCreateDeal}
                isLoading={loading}
              >
                Create Deal
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default HubSpotIntegration;