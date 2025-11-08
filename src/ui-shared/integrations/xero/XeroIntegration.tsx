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
  NumberInput,
  NumberInputField,
  NumberInputStepper,
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
  Checkbox,
  CheckboxGroup,
  Stack,
  Textarea,
  RadioGroup,
  Radio,
  useDisclosure
} from '@chakra-ui/react';
import {
  AddIcon,
  EditIcon,
  DeleteIcon,
  ViewIcon,
  SettingsIcon,
  EmailIcon,
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
  CalendarIcon,
  DollarIcon,
  DocumentIcon,
  TrendingUpIcon,
  TrendingDownIcon,
  HamburgerIcon,
  BankIcon,
  CreditCardIcon,
  ReceiptIcon,
  FileTextIcon,
  CalculatorIcon
} from '@chakra-ui/icons';
import { xeroSkills } from './skills/xeroSkills';

interface XeroConfig {
  tenantId?: string;
  accessToken?: string;
  refreshToken?: string;
  environment: 'production' | 'sandbox';
}

interface XeroInvoice {
  invoiceID: string;
  invoiceNumber: string;
  type: string;
  contact: {
    contactID: string;
    name: string;
    emailAddress: string;
    phones: Array<{
      phoneNumber: string;
      phoneType: string;
    }>;
  };
  date: string;
  dueDate: string;
  status: string;
  lineAmountTypes: {
    subtotal: number;
    total: number;
    totalTax: number;
  };
  currencyCode: string;
  total: number;
  amountDue: number;
  amountPaid: number;
  url: string;
  hasAttachments: boolean;
  isSent: boolean;
  isPaid: boolean;
  creditNotes: Array<{
    creditNoteID: string;
    creditNoteNumber: string;
    amount: number;
  }>;
  payments: Array<{
    paymentID: string;
    amount: number;
    date: string;
    status: string;
  }>;
  createdDateUTC: string;
  updatedDateUTC: string;
  reference?: string;
  lineItems: Array<{
    lineItemID: string;
    description: string;
    quantity: number;
    unitAmount: number;
    accountCode: string;
    taxType: string;
    taxAmount: number;
    lineAmount: number;
    tracking?: Array<{
      trackingCategoryID: string;
      trackingOptionID: string;
      name: string;
    }>;
  }>;
}

interface XeroContact {
  contactID: string;
  contactNumber?: string;
  contactStatus: string;
  name: string;
  firstName?: string;
  lastName?: string;
  emailAddress?: string;
  skypeUserName?: string;
  bankAccountDetails?: {
    accountName: string;
    accountNumber: string;
    sortCode: string;
    bankName: string;
  };
  taxNumber?: string;
  accountsReceivableTaxType?: string;
  accountsPayableTaxType?: string;
  phones: Array<{
    phoneNumber: string;
    phoneType: string;
    phoneAreaCode?: string;
    phoneCountryCode?: string;
  }>;
  addresses: Array<{
    addressType: string;
    addressLine1: string;
    addressLine2?: string;
    addressLine3?: string;
    addressLine4?: string;
    city: string;
    region: string;
    postalCode: string;
    country: string;
    attentionTo?: string;
  }>;
  isCustomer: boolean;
  isSupplier: boolean;
  defaultCurrency: string;
  updatedDateUTC: string;
  contactGroups: Array<{
    contactGroupID: string;
    name: string;
    status: string;
  }>;
  website?: string;
  discount?: number;
  xeroNetworkKey?: string;
  salesTrackingCategories: Array<{
    trackingCategoryID: string;
    name: string;
    trackingOptionID: string;
    trackingOptionName: string;
    status: string;
  }>;
  purchasingTrackingCategories?: Array<{
    trackingCategoryID: string;
    name: string;
    trackingOptionID: string;
    trackingOptionName: string;
    status: string;
  }>;
  attachments?: Array<{
    id: string;
    fileName: string;
    url: string;
    mimeType: string;
    fileSize: number;
  }>;
}

interface XeroBankAccount {
  bankAccountID: string;
  code: string;
  name: string;
  type: string;
  bankAccountNumber: string;
  status: string;
  bankName: string;
  bankBranch: string;
  currencyCode: string;
  bankAccountNumber?: string;
  sortCode?: string;
  accountNumber?: string;
  bsb?: string;
  routingNumber?: string;
  includeInBankFeeds: boolean;
  showInExpenseClaims: boolean;
  displayInBankRegister: boolean;
  enableBankFeeds: boolean;
  bankAccountType: string;
  bankAccountClass: string;
  bankAccountStatus: string;
  url: string;
  numberOfAttachments?: number;
  updatedDateUTC: string;
  lastReconciliationDate?: string;
}

interface XeroTransaction {
  transactionID: string;
  type: string;
  contact?: {
    contactID: string;
    name: string;
  };
  lineItems: Array<{
    lineItemID: string;
    description: string;
    quantity: number;
    unitAmount: number;
    accountCode: string;
    taxType: string;
    taxAmount: number;
    lineAmount: number;
    tracking?: Array<{
      trackingCategoryID: string;
      trackingOptionID: string;
      name: string;
    }>;
  }>;
  date: string;
  status: string;
  lineAmountTypes: {
    subtotal: number;
    total: number;
    totalTax: number;
  };
  currencyCode: string;
  currencyRate: number;
  total: number;
  url: string;
  reference?: string;
  hasAttachments: boolean;
  createdDateUTC: string;
  updatedDateUTC: string;
  bankTransaction?: {
    bankTransactionID: string;
    amount: number;
    date: string;
    status: string;
    reference: string;
    details: string;
  };
  sourceTransactionID?: string;
  sourceSystem?: string;
  sourceTransactionType?: string;
  reconciliationStatus?: string;
}

interface XeroFinancialReport {
  reportID: string;
  reportName: string;
  reportTitles: Array<{
    title: string;
  }>;
  reportDate: string;
  rows: Array<{
    rowType: string;
    title?: string;
    cells: Array<{
      value: string;
    }>;
  }>;
  columns: Array<{
    columnName: string;
  }>;
  summary: Array<{
    columnName: string;
    value: string;
  }>;
  updatedDateUTC: string;
}

const XeroIntegration: React.FC = () => {
  const [config, setConfig] = useState<XeroConfig>({ environment: 'production' });
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState(0);
  const toast = useToast();

  // Data states
  const [invoices, setInvoices] = useState<XeroInvoice[]>([]);
  const [contacts, setContacts] = useState<XeroContact[]>([]);
  const [bankAccounts, setBankAccounts] = useState<XeroBankAccount[]>([]);
  const [transactions, setTransactions] = useState<XeroTransaction[]>([]);
  const [financialReports, setFinancialReports] = useState<XeroFinancialReport[]>([]);

  // Modal states
  const [isInvoiceModalOpen, setIsInvoiceModalOpen] = useState(false);
  const [isContactModalOpen, setIsContactModalOpen] = useState(false);
  const [isTransactionModalOpen, setIsTransactionModalOpen] = useState(false);

  // Forms
  const [invoiceForm, setInvoiceForm] = useState({
    type: 'ACCREC',
    contactID: '',
    date: new Date().toISOString().split('T')[0],
    dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    lineItems: [{
      description: '',
      quantity: 1,
      unitAmount: 0,
      accountCode: '200',
      taxType: 'OUTPUT'
    }],
    reference: '',
    currencyCode: 'USD'
  });

  const [contactForm, setContactForm] = useState({
    name: '',
    firstName: '',
    lastName: '',
    emailAddress: '',
    isCustomer: true,
    isSupplier: false,
    defaultCurrency: 'USD',
    phones: [],
    addresses: [],
    taxNumber: ''
  });

  const [transactionForm, setTransactionForm] = useState({
    type: 'SPEND',
    contactID: '',
    date: new Date().toISOString().split('T')[0],
    lineItems: [{
      description: '',
      quantity: 1,
      unitAmount: 0,
      accountCode: '400',
      taxType: 'NONE'
    }],
    reference: '',
    bankAccountID: ''
  });

  // Filters and search
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [dateFilter, setDateFilter] = useState('');
  const [contactFilter, setContactFilter] = useState('');

  useEffect(() => {
    checkAuthentication();
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated]);

  const checkAuthentication = async () => {
    try {
      const tokens = await xeroSkills.getStoredTokens();
      if (tokens && tokens.accessToken) {
        setIsAuthenticated(true);
        setConfig({
          accessToken: tokens.accessToken,
          tenantId: tokens.tenantId,
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
      const [invoicesData, contactsData, bankAccountsData, transactionsData] = await Promise.all([
        xeroSkills.getInvoices({ page: 1, per_page: 100 }),
        xeroSkills.getContacts({ page: 1, per_page: 100 }),
        xeroSkills.getBankAccounts(),
        xeroSkills.getBankTransactions({ page: 1, per_page: 100 })
      ]);

      setInvoices(invoicesData.invoices || []);
      setContacts(contactsData.contacts || []);
      setBankAccounts(bankAccountsData.bankAccounts || []);
      setTransactions(transactionsData.transactions || []);
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
    window.location.href = '/api/integrations/xero/auth/start';
  };

  const handleCreateInvoice = async () => {
    try {
      setLoading(true);
      const newInvoice = await xeroSkills.createInvoice(invoiceForm);
      setInvoices([newInvoice, ...invoices]);
      setIsInvoiceModalOpen(false);
      setInvoiceForm({
        type: 'ACCREC',
        contactID: '',
        date: new Date().toISOString().split('T')[0],
        dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        lineItems: [{
          description: '',
          quantity: 1,
          unitAmount: 0,
          accountCode: '200',
          taxType: 'OUTPUT'
        }],
        reference: '',
        currencyCode: 'USD'
      });
      toast({
        title: 'Invoice created',
        description: 'Invoice has been created successfully',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
    } catch (error) {
      toast({
        title: 'Error creating invoice',
        description: error.message,
        status: 'error',
        duration: 5000,
        isClosable: true
      });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateContact = async () => {
    try {
      setLoading(true);
      const newContact = await xeroSkills.createContact(contactForm);
      setContacts([newContact, ...contacts]);
      setIsContactModalOpen(false);
      setContactForm({
        name: '',
        firstName: '',
        lastName: '',
        emailAddress: '',
        isCustomer: true,
        isSupplier: false,
        defaultCurrency: 'USD',
        phones: [],
        addresses: [],
        taxNumber: ''
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

  const handleCreateTransaction = async () => {
    try {
      setLoading(true);
      const newTransaction = await xeroSkills.createBankTransaction(transactionForm);
      setTransactions([newTransaction, ...transactions]);
      setIsTransactionModalOpen(false);
      setTransactionForm({
        type: 'SPEND',
        contactID: '',
        date: new Date().toISOString().split('T')[0],
        lineItems: [{
          description: '',
          quantity: 1,
          unitAmount: 0,
          accountCode: '400',
          taxType: 'NONE'
        }],
        reference: '',
        bankAccountID: ''
      });
      toast({
        title: 'Transaction created',
        description: 'Transaction has been created successfully',
        status: 'success',
        duration: 3000,
        isClosable: true
      });
    } catch (error) {
      toast({
        title: 'Error creating transaction',
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
      DRAFT: 'gray',
      SUBMITTED: 'blue',
      AUTHORISED: 'purple',
      PAID: 'green',
      PARTIALLYPAID: 'yellow',
      VOIDED: 'red',
      DELETED: 'red'
    };
    return colors[status] || 'gray';
  };

  const getTransactionTypeBadge = (type: string) => {
    const colors: { [key: string]: string } = {
      SPEND: 'red',
      RECEIVE: 'green',
      TRANSFER: 'blue'
    };
    return colors[type] || 'gray';
  };

  const getBankAccountTypeBadge = (type: string) => {
    const colors: { [key: string]: string } = {
      BANK: 'blue',
      CREDITCARD: 'purple',
      PAYPAL: 'orange'
    };
    return colors[type] || 'gray';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const formatCurrency = (amount: number, currency: string = 'USD') => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  };

  const filteredInvoices = invoices.filter(invoice => {
    const matchesSearch = !searchQuery || 
      invoice.invoiceNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      invoice.contact.name.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = !statusFilter || invoice.status === statusFilter;
    const matchesContact = !contactFilter || invoice.contact.contactID === contactFilter;
    
    return matchesSearch && matchesStatus && matchesContact;
  });

  const filteredTransactions = transactions.filter(transaction => {
    const matchesSearch = !searchQuery || 
      transaction.reference?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      transaction.contact?.name.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesStatus = !statusFilter || transaction.status === statusFilter;
    const matchesDate = !dateFilter || transaction.date.startsWith(dateFilter);
    
    return matchesSearch && matchesStatus && matchesDate;
  });

  if (!isAuthenticated) {
    return (
      <Box minH="100vh" bg="white" p={6}>
        <VStack spacing={8} maxW="800px" mx="auto">
          <VStack spacing={4} textAlign="center">
            <Heading size="2xl" color="#03B0F9">Xero Integration</Heading>
            <Text fontSize="xl" color="gray.600">
              Complete small business accounting and financial management
            </Text>
            <Text color="gray.500">
              Manage invoices, contacts, bank transactions, and financial reporting
            </Text>
          </VStack>

          <Card bg="#F7F9FC" borderColor="#03B0F9" borderWidth={2}>
            <CardBody p={8} textAlign="center">
              <VStack spacing={6}>
                <Heading size="lg" color="#03B0F9">Connect to Xero</Heading>
                <Text color="gray.600">
                  Authenticate with Xero to access your accounting data
                </Text>
                <Button
                  size="lg"
                  bg="#03B0F9"
                  color="white"
                  onClick={handleAuthentication}
                  loadingText="Connecting to Xero..."
                  isLoading={loading}
                  _hover={{ bg: '#0291C7' }}
                >
                  <ExternalLinkIcon mr={2} />
                  Connect Xero Account
                </Button>
              </VStack>
            </CardBody>
          </Card>

          <SimpleGrid columns={3} spacing={6} w="full">
            <Stat>
              <StatLabel>Invoice Management</StatLabel>
              <StatNumber color="#03B0F9">∞</StatNumber>
              <StatHelpText>Create, send, and track invoices</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Contact Management</StatLabel>
              <StatNumber color="#03B0F9">∞</StatNumber>
              <StatHelpText>Manage customers and suppliers</StatHelpText>
            </Stat>
            <Stat>
              <StatLabel>Bank Reconciliation</StatLabel>
              <StatNumber color="#03B0F9">∞</StatNumber>
              <StatHelpText>Automatic bank feed and reconciliation</StatHelpText>
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
            <Heading size="2xl" color="#03B0F9">Xero Integration</Heading>
            <Text color="gray.600">
              {config.environment === 'sandbox' ? 'Sandbox' : 'Production'} • Tenant: {config.tenantId}
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
              bg="#03B0F9"
              color="white"
              onClick={() => window.open('https://go.xero.com/', '_blank')}
              rightIcon={<ExternalLinkIcon />}
              _hover={{ bg: '#0291C7' }}
            >
              Open Xero
            </Button>
          </HStack>
        </Flex>

        {/* Financial Summary Dashboard */}
        <SimpleGrid columns={4} spacing={4}>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Total Invoices</StatLabel>
            <StatNumber color="#03B0F9">{invoices.length}</StatNumber>
            <StatHelpText>
              <TrendingUpIcon mr={1} color="green" />
              Active invoices
            </StatHelpText>
          </Stat>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Total Contacts</StatLabel>
            <StatNumber color="#03B0F9">{contacts.length}</StatNumber>
            <StatHelpText>
              <InfoIcon mr={1} color="blue" />
              Customers and suppliers
            </StatHelpText>
          </Stat>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Total Transactions</StatLabel>
            <StatNumber color="#03B0F9">{transactions.length}</StatNumber>
            <StatHelpText>
              <BankIcon mr={1} color="orange" />
              Bank transactions
            </StatHelpText>
          </Stat>
          <Stat bg="white" p={4} rounded="lg" shadow="sm">
            <StatLabel>Bank Accounts</StatLabel>
            <StatNumber color="#03B0F9">{bankAccounts.length}</StatNumber>
            <StatHelpText>
              <CreditCardIcon mr={1} color="purple" />
              Connected accounts
            </StatHelpText>
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
            <Tab _selected={{ color: '#03B0F9', borderBottomColor: '#03B0F9' }}>
              <DocumentIcon mr={2} /> Invoices
            </Tab>
            <Tab _selected={{ color: '#03B0F9', borderBottomColor: '#03B0F9' }}>
              <EmailIcon mr={2} /> Contacts
            </Tab>
            <Tab _selected={{ color: '#03B0F9', borderBottomColor: '#03B0F9' }}>
              <BankIcon mr={2} /> Banking
            </Tab>
            <Tab _selected={{ color: '#03B0F9', borderBottomColor: '#03B0F9' }}>
              <CalculatorIcon mr={2} /> Reports
            </Tab>
          </TabList>

          <TabPanels>
            {/* Invoices Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                {/* Search and Filters */}
                <HStack spacing={4} w="full">
                  <Input
                    placeholder="Search invoices..."
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
                    <option value="DRAFT">Draft</option>
                    <option value="SUBMITTED">Submitted</option>
                    <option value="AUTHORISED">Authorised</option>
                    <option value="PAID">Paid</option>
                    <option value="PARTIALLYPAID">Partially Paid</option>
                    <option value="VOIDED">Voided</option>
                  </Select>
                  <Select
                    placeholder="Contact"
                    value={contactFilter}
                    onChange={(e) => setContactFilter(e.target.value)}
                    w="200px"
                  >
                    <option value="">All Contacts</option>
                    {contacts.map((contact) => (
                      <option key={contact.contactID} value={contact.contactID}>
                        {contact.name}
                      </option>
                    ))}
                  </Select>
                  <Button
                    bg="#03B0F9"
                    color="white"
                    onClick={() => setIsInvoiceModalOpen(true)}
                    leftIcon={<AddIcon />}
                    _hover={{ bg: '#0291C7' }}
                  >
                    New Invoice
                  </Button>
                </HStack>

                {/* Invoices Table */}
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Invoice #</Th>
                        <Th>Customer</Th>
                        <Th>Date</Th>
                        <Th>Due Date</Th>
                        <Th>Amount</Th>
                        <Th>Paid</Th>
                        <Th>Due</Th>
                        <Th>Status</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {filteredInvoices.map((invoice) => (
                        <Tr key={invoice.invoiceID}>
                          <Td>
                            <Text fontWeight="medium">{invoice.invoiceNumber}</Text>
                          </Td>
                          <Td>
                            <HStack>
                              <EmailIcon color="gray.400" />
                              <Text>{invoice.contact.name}</Text>
                            </HStack>
                          </Td>
                          <Td>{formatDate(invoice.date)}</Td>
                          <Td>{formatDate(invoice.dueDate)}</Td>
                          <Td>{formatCurrency(invoice.total, invoice.currencyCode)}</Td>
                          <Td>{formatCurrency(invoice.amountPaid, invoice.currencyCode)}</Td>
                          <Td>{formatCurrency(invoice.amountDue, invoice.currencyCode)}</Td>
                          <Td>
                            <Badge colorScheme={getStatusBadge(invoice.status)}>
                              {invoice.status}
                            </Badge>
                          </Td>
                          <Td>
                            <Menu>
                              <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                              <MenuList>
                                <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                                <MenuItem icon={<EditIcon />}>Edit Invoice</MenuItem>
                                <MenuItem icon={<DownloadIcon />}>Download PDF</MenuItem>
                                <MenuItem icon={<EmailIcon />}>Send Invoice</MenuItem>
                                <MenuItem icon={<DeleteIcon />}>Delete Invoice</MenuItem>
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

            {/* Contacts Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <HStack justify="space-between" w="full">
                  <Input
                    placeholder="Search contacts..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    leftIcon={<SearchIcon />}
                    flex={1}
                  />
                  <Button
                    bg="#03B0F9"
                    color="white"
                    onClick={() => setIsContactModalOpen(true)}
                    leftIcon={<AddIcon />}
                    _hover={{ bg: '#0291C7' }}
                  >
                    Add Contact
                  </Button>
                </HStack>

                {/* Contacts Table */}
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Name</Th>
                        <Th>Email</Th>
                        <Th>Phone</Th>
                        <Th>Type</Th>
                        <Th>Currency</Th>
                        <Th>Status</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {contacts.filter(contact => 
                        !searchQuery || contact.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                        contact.emailAddress?.toLowerCase().includes(searchQuery.toLowerCase())
                      ).map((contact) => (
                        <Tr key={contact.contactID}>
                          <Td>
                            <VStack align="start" spacing={1}>
                              <Text fontWeight="medium">{contact.name}</Text>
                              {contact.contactNumber && (
                                <Text fontSize="sm" color="gray.500">
                                  #{contact.contactNumber}
                                </Text>
                              )}
                            </VStack>
                          </Td>
                          <Td>
                            {contact.emailAddress && (
                              <HStack>
                                <EmailIcon color="gray.400" />
                                <Text>{contact.emailAddress}</Text>
                              </HStack>
                            )}
                          </Td>
                          <Td>
                            {contact.phones.length > 0 && (
                              <Text>{contact.phones[0].phoneNumber}</Text>
                            )}
                          </Td>
                          <Td>
                            <HStack spacing={2}>
                              {contact.isCustomer && (
                                <Badge colorScheme="green" variant="solid">
                                  Customer
                                </Badge>
                              )}
                              {contact.isSupplier && (
                                <Badge colorScheme="blue" variant="solid">
                                  Supplier
                                </Badge>
                              )}
                            </HStack>
                          </Td>
                          <Td>
                            <Badge colorScheme="gray">
                              {contact.defaultCurrency}
                            </Badge>
                          </Td>
                          <Td>
                            <Badge colorScheme={contact.contactStatus === 'ACTIVE' ? 'green' : 'red'}>
                              {contact.contactStatus}
                            </Badge>
                          </Td>
                          <Td>
                            <Menu>
                              <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                              <MenuList>
                                <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                                <MenuItem icon={<EditIcon />}>Edit Contact</MenuItem>
                                <MenuItem icon={<EmailIcon />}>Send Email</MenuItem>
                                <MenuItem icon={<DocumentIcon />}>Create Invoice</MenuItem>
                                <MenuItem icon={<DeleteIcon />}>Delete Contact</MenuItem>
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

            {/* Banking Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <HStack justify="space-between" w="full">
                  <Input
                    placeholder="Search transactions..."
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
                    <option value="AUTHORISED">Authorised</option>
                    <option value="DELETED">Deleted</option>
                  </Select>
                  <Select
                    placeholder="Date"
                    value={dateFilter}
                    onChange={(e) => setDateFilter(e.target.value)}
                    w="150px"
                  >
                    <option value="">All Dates</option>
                    <option value={new Date().toISOString().split('T')[0]}>Today</option>
                    <option value={new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}>Last 7 Days</option>
                    <option value={new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]}>Last 30 Days</option>
                  </Select>
                  <Button
                    bg="#03B0F9"
                    color="white"
                    onClick={() => setIsTransactionModalOpen(true)}
                    leftIcon={<AddIcon />}
                    _hover={{ bg: '#0291C7' }}
                  >
                    Add Transaction
                  </Button>
                </HStack>

                {/* Bank Accounts Summary */}
                <SimpleGrid columns={3} spacing={4} w="full">
                  {bankAccounts.map((account) => (
                    <Card key={account.bankAccountID} borderWidth={1} borderColor="gray.200">
                      <CardBody p={4}>
                        <VStack align="start" spacing={2}>
                          <HStack justify="space-between" w="full">
                            <Text fontWeight="medium">{account.name}</Text>
                            <Badge colorScheme={getBankAccountTypeBadge(account.type)} variant="solid" size="sm">
                              {account.type}
                            </Badge>
                          </HStack>
                          <Text fontSize="sm" color="gray.600">
                            {account.bankName}
                          </Text>
                          <Text fontSize="sm" color="gray.500">
                            {account.bankAccountNumber || account.accountNumber}
                          </Text>
                          <Badge colorScheme={account.status === 'ACTIVE' ? 'green' : 'red'} variant="outline" size="sm">
                            {account.status}
                          </Badge>
                        </VStack>
                      </CardBody>
                    </Card>
                  ))}
                </SimpleGrid>

                {/* Transactions Table */}
                <TableContainer>
                  <Table variant="simple">
                    <Thead>
                      <Tr>
                        <Th>Date</Th>
                        <Th>Type</Th>
                        <Th>Contact</Th>
                        <Th>Description</Th>
                        <Th>Account</Th>
                        <Th>Amount</Th>
                        <Th>Status</Th>
                        <Th>Actions</Th>
                      </Tr>
                    </Thead>
                    <Tbody>
                      {filteredTransactions.map((transaction) => (
                        <Tr key={transaction.transactionID}>
                          <Td>{formatDate(transaction.date)}</Td>
                          <Td>
                            <Badge colorScheme={getTransactionTypeBadge(transaction.type)}>
                              {transaction.type}
                            </Badge>
                          </Td>
                          <Td>
                            {transaction.contact && (
                              <Text>{transaction.contact.name}</Text>
                            )}
                          </Td>
                          <Td>
                            <Text noOfLines={2}>
                              {transaction.lineItems[0]?.description || 'No description'}
                            </Text>
                          </Td>
                          <Td>
                            <Text fontSize="sm" color="gray.600">
                              {transaction.lineItems[0]?.accountCode}
                            </Text>
                          </Td>
                          <Td>
                            <Text color={transaction.type === 'SPEND' ? 'red.500' : 'green.500'} fontWeight="medium">
                              {formatCurrency(transaction.total)}
                            </Text>
                          </Td>
                          <Td>
                            <Badge colorScheme={transaction.status === 'AUTHORISED' ? 'green' : 'red'}>
                              {transaction.status}
                            </Badge>
                          </Td>
                          <Td>
                            <Menu>
                              <MenuButton as={IconButton} icon={<ViewIcon />} variant="ghost" size="sm" />
                              <MenuList>
                                <MenuItem icon={<ViewIcon />}>View Details</MenuItem>
                                <MenuItem icon={<EditIcon />}>Edit Transaction</MenuItem>
                                <MenuItem icon={<BankIcon />}>Reconcile</MenuItem>
                                <MenuItem icon={<DeleteIcon />}>Delete Transaction</MenuItem>
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

            {/* Reports Tab */}
            <TabPanel p={6}>
              <VStack spacing={6}>
                <Heading size="lg">Financial Reports</Heading>
                <SimpleGrid columns={2} spacing={4} w="full">
                  <Card borderWidth={1} borderColor="gray.200" cursor="pointer" _hover={{ shadow: "md", transform: "translateY(-2px)" }} transition="all 0.2s">
                    <CardBody p={6}>
                      <VStack spacing={4}>
                        <HStack>
                          <FileTextIcon color="#03B0F9" boxSize={8} />
                          <Heading size="md">Profit & Loss</Heading>
                        </HStack>
                        <Text color="gray.600">
                          View detailed profit and loss statement for your business
                        </Text>
                        <Button bg="#03B0F9" color="white" size="sm" _hover={{ bg: '#0291C7' }}>
                          Generate Report
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                  <Card borderWidth={1} borderColor="gray.200" cursor="pointer" _hover={{ shadow: "md", transform: "translateY(-2px)" }} transition="all 0.2s">
                    <CardBody p={6}>
                      <VStack spacing={4}>
                        <HStack>
                          <TrendingUpIcon color="#03B0F9" boxSize={8} />
                          <Heading size="md">Balance Sheet</Heading>
                        </HStack>
                        <Text color="gray.600">
                          Comprehensive view of your assets, liabilities, and equity
                        </Text>
                        <Button bg="#03B0F9" color="white" size="sm" _hover={{ bg: '#0291C7' }}>
                          Generate Report
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                  <Card borderWidth={1} borderColor="gray.200" cursor="pointer" _hover={{ shadow: "md", transform: "translateY(-2px)" }} transition="all 0.2s">
                    <CardBody p={6}>
                      <VStack spacing={4}>
                        <HStack>
                          <ReceiptIcon color="#03B0F9" boxSize={8} />
                          <Heading size="md">Cash Flow</Heading>
                        </HStack>
                        <Text color="gray.600">
                          Track cash inflows and outflows over time
                        </Text>
                        <Button bg="#03B0F9" color="white" size="sm" _hover={{ bg: '#0291C7' }}>
                          Generate Report
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                  <Card borderWidth={1} borderColor="gray.200" cursor="pointer" _hover={{ shadow: "md", transform: "translateY(-2px)" }} transition="all 0.2s">
                    <CardBody p={6}>
                      <VStack spacing={4}>
                        <HStack>
                          <CalculatorIcon color="#03B0F9" boxSize={8} />
                          <Heading size="md">Aged Receivables</Heading>
                        </HStack>
                        <Text color="gray.600">
                          Monitor outstanding invoices and overdue payments
                        </Text>
                        <Button bg="#03B0F9" color="white" size="sm" _hover={{ bg: '#0291C7' }}>
                          Generate Report
                        </Button>
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              </VStack>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Invoice Modal */}
        <Modal isOpen={isInvoiceModalOpen} onClose={() => setIsInvoiceModalOpen(false)} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Create New Invoice</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Invoice Type</FormLabel>
                    <Select
                      value={invoiceForm.type}
                      onChange={(e) => setInvoiceForm({ ...invoiceForm, type: e.target.value })}
                    >
                      <option value="ACCREC">Accounts Receivable (Invoice)</option>
                      <option value="ACCPAY">Accounts Payable (Bill)</option>
                    </Select>
                  </FormControl>
                  <FormControl>
                    <FormLabel>Customer</FormLabel>
                    <Select
                      value={invoiceForm.contactID}
                      onChange={(e) => setInvoiceForm({ ...invoiceForm, contactID: e.target.value })}
                      placeholder="Select contact"
                    >
                      {contacts.filter(c => c.isCustomer).map((contact) => (
                        <option key={contact.contactID} value={contact.contactID}>
                          {contact.name}
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                </HStack>
                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Invoice Date</FormLabel>
                    <Input
                      type="date"
                      value={invoiceForm.date}
                      onChange={(e) => setInvoiceForm({ ...invoiceForm, date: e.target.value })}
                    />
                  </FormControl>
                  <FormControl>
                    <FormLabel>Due Date</FormLabel>
                    <Input
                      type="date"
                      value={invoiceForm.dueDate}
                      onChange={(e) => setInvoiceForm({ ...invoiceForm, dueDate: e.target.value })}
                    />
                  </FormControl>
                </HStack>
                <FormControl>
                  <FormLabel>Reference</FormLabel>
                  <Input
                    value={invoiceForm.reference}
                    onChange={(e) => setInvoiceForm({ ...invoiceForm, reference: e.target.value })}
                    placeholder="Invoice reference or PO number"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Line Items</FormLabel>
                  {invoiceForm.lineItems.map((item, index) => (
                    <HStack key={index} spacing={2} mb={2}>
                      <Input
                        placeholder="Description"
                        value={item.description}
                        onChange={(e) => {
                          const newItems = [...invoiceForm.lineItems];
                          newItems[index].description = e.target.value;
                          setInvoiceForm({ ...invoiceForm, lineItems: newItems });
                        }}
                      />
                      <NumberInput>
                        <NumberInputField
                          placeholder="Quantity"
                          value={item.quantity}
                          onChange={(value) => {
                            const newItems = [...invoiceForm.lineItems];
                            newItems[index].quantity = value;
                            setInvoiceForm({ ...invoiceForm, lineItems: newItems });
                          }}
                        />
                        <NumberInputStepper />
                      </NumberInput>
                      <NumberInput>
                        <NumberInputField
                          placeholder="Unit Amount"
                          value={item.unitAmount}
                          onChange={(value) => {
                            const newItems = [...invoiceForm.lineItems];
                            newItems[index].unitAmount = value;
                            setInvoiceForm({ ...invoiceForm, lineItems: newItems });
                          }}
                        />
                        <NumberInputStepper />
                      </NumberInput>
                    </HStack>
                  ))}
                  <Button
                    size="sm"
                    onClick={() => setInvoiceForm({
                      ...invoiceForm,
                      lineItems: [...invoiceForm.lineItems, {
                        description: '',
                        quantity: 1,
                        unitAmount: 0,
                        accountCode: '200',
                        taxType: 'OUTPUT'
                      }]
                    })}
                    leftIcon={<AddIcon />}
                  >
                    Add Line Item
                  </Button>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsInvoiceModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                bg="#03B0F9"
                color="white"
                onClick={handleCreateInvoice}
                isLoading={loading}
                _hover={{ bg: '#0291C7' }}
              >
                Create Invoice
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Contact Modal */}
        <Modal isOpen={isContactModalOpen} onClose={() => setIsContactModalOpen(false)} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Add New Contact</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>First Name</FormLabel>
                    <Input
                      value={contactForm.firstName}
                      onChange={(e) => setContactForm({ ...contactForm, firstName: e.target.value })}
                      placeholder="First name"
                    />
                  </FormControl>
                  <FormControl>
                    <FormLabel>Last Name</FormLabel>
                    <Input
                      value={contactForm.lastName}
                      onChange={(e) => setContactForm({ ...contactForm, lastName: e.target.value })}
                      placeholder="Last name"
                    />
                  </FormControl>
                </HStack>
                <FormControl>
                  <FormLabel>Company Name</FormLabel>
                  <Input
                    value={contactForm.name}
                    onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                    placeholder="Company name (if applicable)"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Email</FormLabel>
                  <Input
                    type="email"
                    value={contactForm.emailAddress}
                    onChange={(e) => setContactForm({ ...contactForm, emailAddress: e.target.value })}
                    placeholder="Email address"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Tax Number</FormLabel>
                  <Input
                    value={contactForm.taxNumber}
                    onChange={(e) => setContactForm({ ...contactForm, taxNumber: e.target.value })}
                    placeholder="Tax number or VAT ID"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Contact Type</FormLabel>
                  <CheckboxGroup
                    value={contactForm.isCustomer ? ['customer'] : contactForm.isSupplier ? ['supplier'] : []}
                    onChange={(values) => {
                      const isCustomer = values.includes('customer');
                      const isSupplier = values.includes('supplier');
                      setContactForm({ ...contactForm, isCustomer, isSupplier });
                    }}
                  >
                    <Stack spacing={4} direction="row">
                      <Checkbox value="customer">Customer</Checkbox>
                      <Checkbox value="supplier">Supplier</Checkbox>
                    </Stack>
                  </CheckboxGroup>
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
                bg="#03B0F9"
                color="white"
                onClick={handleCreateContact}
                isLoading={loading}
                _hover={{ bg: '#0291C7' }}
              >
                Add Contact
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Transaction Modal */}
        <Modal isOpen={isTransactionModalOpen} onClose={() => setIsTransactionModalOpen(false)} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Add Bank Transaction</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <HStack spacing={4}>
                  <FormControl>
                    <FormLabel>Transaction Type</FormLabel>
                    <Select
                      value={transactionForm.type}
                      onChange={(e) => setTransactionForm({ ...transactionForm, type: e.target.value })}
                    >
                      <option value="SPEND">Spend (Payment)</option>
                      <option value="RECEIVE">Receive (Payment)</option>
                      <option value="TRANSFER">Transfer</option>
                    </Select>
                  </FormControl>
                  <FormControl>
                    <FormLabel>Bank Account</FormLabel>
                    <Select
                      value={transactionForm.bankAccountID}
                      onChange={(e) => setTransactionForm({ ...transactionForm, bankAccountID: e.target.value })}
                      placeholder="Select bank account"
                    >
                      {bankAccounts.map((account) => (
                        <option key={account.bankAccountID} value={account.bankAccountID}>
                          {account.name} ({account.currencyCode})
                        </option>
                      ))}
                    </Select>
                  </FormControl>
                </HStack>
                <FormControl>
                  <FormLabel>Transaction Date</FormLabel>
                  <Input
                    type="date"
                    value={transactionForm.date}
                    onChange={(e) => setTransactionForm({ ...transactionForm, date: e.target.value })}
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Contact (Optional)</FormLabel>
                  <Select
                    value={transactionForm.contactID}
                    onChange={(e) => setTransactionForm({ ...transactionForm, contactID: e.target.value })}
                    placeholder="Select contact (optional)"
                  >
                    <option value="">No contact</option>
                    {contacts.map((contact) => (
                      <option key={contact.contactID} value={contact.contactID}>
                        {contact.name}
                      </option>
                    ))}
                  </Select>
                </FormControl>
                <FormControl>
                  <FormLabel>Reference</FormLabel>
                  <Input
                    value={transactionForm.reference}
                    onChange={(e) => setTransactionForm({ ...transactionForm, reference: e.target.value })}
                    placeholder="Transaction reference"
                  />
                </FormControl>
                <FormControl>
                  <FormLabel>Line Items</FormLabel>
                  {transactionForm.lineItems.map((item, index) => (
                    <HStack key={index} spacing={2} mb={2}>
                      <Input
                        placeholder="Description"
                        value={item.description}
                        onChange={(e) => {
                          const newItems = [...transactionForm.lineItems];
                          newItems[index].description = e.target.value;
                          setTransactionForm({ ...transactionForm, lineItems: newItems });
                        }}
                      />
                      <NumberInput>
                        <NumberInputField
                          placeholder="Amount"
                          value={item.unitAmount}
                          onChange={(value) => {
                            const newItems = [...transactionForm.lineItems];
                            newItems[index].unitAmount = value;
                            setTransactionForm({ ...transactionForm, lineItems: newItems });
                          }}
                        />
                        <NumberInputStepper />
                      </NumberInput>
                    </HStack>
                  ))}
                  <Button
                    size="sm"
                    onClick={() => setTransactionForm({
                      ...transactionForm,
                      lineItems: [...transactionForm.lineItems, {
                        description: '',
                        quantity: 1,
                        unitAmount: 0,
                        accountCode: '400',
                        taxType: 'NONE'
                      }]
                    })}
                    leftIcon={<AddIcon />}
                  >
                    Add Line Item
                  </Button>
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button
                variant="ghost"
                mr={3}
                onClick={() => setIsTransactionModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                bg="#03B0F9"
                color="white"
                onClick={handleCreateTransaction}
                isLoading={loading}
                _hover={{ bg: '#0291C7' }}
              >
                Add Transaction
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default XeroIntegration;