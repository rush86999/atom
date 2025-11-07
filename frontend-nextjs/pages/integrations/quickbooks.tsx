/**
 * QuickBooks Integration Page
 * Complete QuickBooks financial management integration
 */

import React, { useState, useEffect } from "react";
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
  Progress,
  Divider,
  useColorModeValue,
  Stack,
  Flex,
  Spacer,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  TableContainer,
  Input,
  InputGroup,
  InputLeftElement,
  Select,
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
  NumberIncrementStepper,
  NumberDecrementStepper,
  Textarea,
  useDisclosure,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
} from "@chakra-ui/react";
import {
  CreditCardIcon,
  DollarIcon,
  ExternalLinkIcon,
  CheckCircleIcon,
  WarningIcon,
  TimeIcon,
  SearchIcon,
  AddIcon,
  EditIcon,
  DeleteIcon,
  ViewIcon,
  RepeatIcon,
} from "@chakra-ui/icons";

interface QuickBooksData {
  invoices?: any[];
  customers?: any[];
  expenses?: any[];
  accounts?: any[];
  reports?: any[];
  connectionStatus?: boolean;
  lastSync?: string;
}

const QuickBooksIntegrationPage: React.FC = () => {
  const [data, setData] = useState<QuickBooksData>({});
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedTab, setSelectedTab] = useState("dashboard");
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [isEditing, setIsEditing] = useState(false);
  
  const { isOpen: isModalOpen, onOpen: onModalOpen, onClose: onModalClose } = useDisclosure();
  const { isOpen: isReportOpen, onOpen: onReportOpen, onClose: onReportClose } = useDisclosure();
  
  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Form states for modal
  const [formData, setFormData] = useState({
    customer_id: "",
    amount: 0,
    description: "",
    due_date: "",
    line_items: [],
  });

  // Fetch QuickBooks data
  const fetchQuickBooksData = async () => {
    try {
      const [invoicesRes, customersRes, expensesRes, accountsRes, healthRes] = await Promise.all([
        fetch('/api/quickbooks/invoices'),
        fetch('/api/quickbooks/customers'),
        fetch('/api/quickbooks/expenses'),
        fetch('/api/quickbooks/accounts'),
        fetch('/api/quickbooks/health'),
      ]);

      const invoices = invoicesRes.ok ? await invoicesRes.json() : [];
      const customers = customersRes.ok ? await customersRes.json() : [];
      const expenses = expensesRes.ok ? await expensesRes.json() : [];
      const accounts = accountsRes.ok ? await accountsRes.json() : [];
      const connectionStatus = healthRes.ok;

      setData({
        invoices: invoices.data || [],
        customers: customers.data || [],
        expenses: expenses.data || [],
        accounts: accounts.data || [],
        connectionStatus,
        lastSync: new Date().toISOString(),
      });
    } catch (error) {
      console.error('Error fetching QuickBooks data:', error);
      toast({
        title: "Error fetching data",
        description: "Failed to load QuickBooks data",
        status: "error",
        duration: 5000,
      });
    } finally {
      setLoading(false);
    }
  };

  // Connect to QuickBooks
  const handleConnect = () => {
    setConnecting(true);
    window.location.href = '/api/quickbooks/oauth/start';
  };

  // Create/Edit Invoice
  const handleInvoiceSubmit = async () => {
    try {
      const url = isEditing 
        ? `/api/quickbooks/invoices/${selectedItem?.Id}`
        : '/api/quickbooks/invoices';
      
      const response = await fetch(url, {
        method: isEditing ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          Line: formData.line_items,
          CustomerRef: {
            value: formData.customer_id,
          },
          TotalAmt: formData.amount,
          Description: formData.description,
          DueDate: formData.due_date,
        }),
      });

      if (response.ok) {
        toast({
          title: `Invoice ${isEditing ? 'updated' : 'created'}`,
          status: "success",
          duration: 3000,
        });
        onModalClose();
        fetchQuickBooksData();
        resetForm();
      } else {
        throw new Error('Failed to save invoice');
      }
    } catch (error) {
      toast({
        title: "Error",
        description: `Failed to ${isEditing ? 'update' : 'create'} invoice`,
        status: "error",
        duration: 5000,
      });
    }
  };

  // Delete Invoice
  const handleDeleteInvoice = async (invoiceId: string) => {
    try {
      const response = await fetch(`/api/quickbooks/invoices/${invoiceId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        toast({
          title: "Invoice deleted",
          status: "success",
          duration: 3000,
        });
        fetchQuickBooksData();
      } else {
        throw new Error('Failed to delete invoice');
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete invoice",
        status: "error",
        duration: 5000,
      });
    }
  };

  // Generate Report
  const handleGenerateReport = async (reportType: string) => {
    try {
      const response = await fetch(`/api/quickbooks/reports/${reportType}`);
      if (response.ok) {
        const report = await response.json();
        setData(prev => ({ ...prev, reports: { ...prev.reports, [reportType]: report } }));
        onReportOpen();
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to generate report",
        status: "error",
        duration: 5000,
      });
    }
  };

  // Reset form
  const resetForm = () => {
    setFormData({
      customer_id: "",
      amount: 0,
      description: "",
      due_date: "",
      line_items: [],
    });
    setIsEditing(false);
    setSelectedItem(null);
  };

  // Open modal for editing
  const openEditModal = (item?: any) => {
    if (item) {
      setFormData({
        customer_id: item.CustomerRef?.value || "",
        amount: item.TotalAmt || 0,
        description: item.Description || "",
        due_date: item.DueDate || "",
        line_items: item.Line || [],
      });
      setIsEditing(true);
      setSelectedItem(item);
    } else {
      resetForm();
    }
    onModalOpen();
  };

  useEffect(() => {
    fetchQuickBooksData();
  }, []);

  const filteredInvoices = data.invoices?.filter(invoice =>
    invoice.Description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    invoice.CustomerRef?.name?.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  const filteredCustomers = data.customers?.filter(customer =>
    customer.DisplayName?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    customer.PrimaryEmailAddr?.Address?.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  const filteredExpenses = data.expenses?.filter(expense =>
    expense.Description?.toLowerCase().includes(searchTerm.toLowerCase()) ||
    expense.AccountRef?.name?.toLowerCase().includes(searchTerm.toLowerCase())
  ) || [];

  if (loading) {
    return (
      <Box minH="100vh" bg={bgColor} p={6}>
        <VStack spacing={8} align="center" justify="center" minH="400px">
          <Text>Loading QuickBooks data...</Text>
        </VStack>
      </Box>
    );
  }

  if (!data.connectionStatus) {
    return (
      <Box minH="100vh" bg={bgColor} p={6}>
        <VStack spacing={8} align="center" justify="center" minH="400px">
          <Card maxW="md">
            <CardBody>
              <VStack spacing={6} align="center">
                <Icon as={CreditCardIcon} w={16} h={16} color="green.500" />
                <VStack spacing={2} align="center">
                  <Heading size="lg">Connect QuickBooks</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your QuickBooks account to manage invoices, customers, expenses, and financial reports
                  </Text>
                </VStack>
                <Button
                  colorScheme="green"
                  size="lg"
                  onClick={handleConnect}
                  isLoading={connecting}
                  leftIcon={<ExternalLinkIcon />}
                >
                  Connect QuickBooks
                </Button>
              </VStack>
            </CardBody>
          </Card>
        </VStack>
      </Box>
    );
  }

  return (
    <Box minH="100vh" bg={bgColor} p={6}>
      <VStack spacing={8} align="stretch" maxW="1200px" mx="auto">
        {/* Header */}
        <VStack align="start" spacing={2}>
          <HStack>
            <Icon as={CreditCardIcon} w={8} h={8} color="green.500" />
            <Heading size="2xl">QuickBooks Integration</Heading>
          </HStack>
          <Text color="gray.600" fontSize="lg">
            Manage your financial data with QuickBooks
          </Text>
          <HStack>
            <Badge colorScheme="green" display="flex" alignItems="center">
              <CheckCircleIcon w={3} h={3} mr={1} />
              Connected
            </Badge>
            {data.lastSync && (
              <Text fontSize="sm" color="gray.500">
                Last sync: {new Date(data.lastSync).toLocaleString()}
              </Text>
            )}
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RepeatIcon />}
              onClick={fetchQuickBooksData}
            >
              Refresh
            </Button>
          </HStack>
        </VStack>

        {/* Stats Overview */}
        <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
          <Card>
            <CardBody>
              <VStack spacing={1} align="center">
                <Text fontSize="2xl" fontWeight="bold" color="green.500">
                  {data.invoices?.length || 0}
                </Text>
                <Text fontSize="sm" color="gray.600">Invoices</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack spacing={1} align="center">
                <Text fontSize="2xl" fontWeight="bold" color="blue.500">
                  {data.customers?.length || 0}
                </Text>
                <Text fontSize="sm" color="gray.600">Customers</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack spacing={1} align="center">
                <Text fontSize="2xl" fontWeight="bold" color="orange.500">
                  {data.expenses?.length || 0}
                </Text>
                <Text fontSize="sm" color="gray.600">Expenses</Text>
              </VStack>
            </CardBody>
          </Card>
          <Card>
            <CardBody>
              <VStack spacing={1} align="center">
                <Text fontSize="2xl" fontWeight="bold" color="purple.500">
                  {data.accounts?.length || 0}
                </Text>
                <Text fontSize="sm" color="gray.600">Accounts</Text>
              </VStack>
            </CardBody>
          </Card>
        </SimpleGrid>

        {/* Quick Actions */}
        <Card>
          <CardHeader>
            <Heading size="md">Quick Actions</Heading>
          </CardHeader>
          <CardBody>
            <HStack spacing={4} wrap="wrap">
              <Button
                colorScheme="green"
                leftIcon={<AddIcon />}
                onClick={() => openEditModal()}
              >
                Create Invoice
              </Button>
              <Button
                colorScheme="blue"
                leftIcon={<DollarIcon />}
                onClick={() => handleGenerateReport('profitandloss')}
              >
                P&L Report
              </Button>
              <Button
                colorScheme="purple"
                leftIcon={<DollarIcon />}
                onClick={() => handleGenerateReport('balancesheet')}
              >
                Balance Sheet
              </Button>
              <Button
                colorScheme="orange"
                leftIcon={<DollarIcon />}
                onClick={() => handleGenerateReport('cashflow')}
              >
                Cash Flow
              </Button>
            </HStack>
          </CardBody>
        </Card>

        {/* Search */}
        <InputGroup>
          <InputLeftElement>
            <SearchIcon color="gray.400" />
          </InputLeftElement>
          <Input
            placeholder="Search invoices, customers, expenses..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </InputGroup>

        {/* Main Content Tabs */}
        <Tabs onChange={(index) => setSelectedTab(['dashboard', 'invoices', 'customers', 'expenses', 'accounts'][index])}>
          <TabList>
            <Tab>Dashboard</Tab>
            <Tab>Invoices ({data.invoices?.length || 0})</Tab>
            <Tab>Customers ({data.customers?.length || 0})</Tab>
            <Tab>Expenses ({data.expenses?.length || 0})</Tab>
            <Tab>Accounts ({data.accounts?.length || 0})</Tab>
          </TabList>

          <TabPanels>
            {/* Dashboard Tab */}
            <TabPanel>
              <VStack spacing={6}>
                <Alert status="info">
                  <AlertIcon />
                  <Box>
                    <AlertTitle>QuickBooks Dashboard</AlertTitle>
                    <AlertDescription>
                      Monitor your financial metrics and recent activity
                    </AlertDescription>
                  </Box>
                </Alert>
                <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
                  <Card>
                    <CardHeader>
                      <Heading size="sm">Recent Invoices</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={2} align="stretch">
                        {filteredInvoices.slice(0, 5).map((invoice: any) => (
                          <HStack key={invoice.Id} justify="space-between">
                            <VStack align="start" spacing={0}>
                              <Text fontSize="sm" fontWeight="medium">{invoice.Description}</Text>
                              <Text fontSize="xs" color="gray.500">{invoice.CustomerRef?.name}</Text>
                            </VStack>
                            <Text fontSize="sm" fontWeight="bold">${invoice.TotalAmt}</Text>
                          </HStack>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>
                  <Card>
                    <CardHeader>
                      <Heading size="sm">Recent Customers</Heading>
                    </CardHeader>
                    <CardBody>
                      <VStack spacing={2} align="stretch">
                        {filteredCustomers.slice(0, 5).map((customer: any) => (
                          <HStack key={customer.Id} justify="space-between">
                            <VStack align="start" spacing={0}>
                              <Text fontSize="sm" fontWeight="medium">{customer.DisplayName}</Text>
                              <Text fontSize="xs" color="gray.500">{customer.PrimaryEmailAddr?.Address}</Text>
                            </VStack>
                            <Badge colorScheme="green">Active</Badge>
                          </HStack>
                        ))}
                      </VStack>
                    </CardBody>
                  </Card>
                </SimpleGrid>
              </VStack>
            </TabPanel>

            {/* Invoices Tab */}
            <TabPanel>
              <Card>
                <CardHeader>
                  <HStack justify="space-between">
                    <Heading size="md">Invoices</Heading>
                    <Button
                      colorScheme="green"
                      size="sm"
                      leftIcon={<AddIcon />}
                      onClick={() => openEditModal()}
                    >
                      New Invoice
                    </Button>
                  </HStack>
                </CardHeader>
                <CardBody>
                  <TableContainer>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Invoice</Th>
                          <Th>Customer</Th>
                          <Th>Amount</Th>
                          <Th>Status</Th>
                          <Th>Actions</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {filteredInvoices.map((invoice: any) => (
                          <Tr key={invoice.Id}>
                            <Td>
                              <VStack align="start" spacing={0}>
                                <Text fontWeight="medium">{invoice.Description || `Invoice #${invoice.Id}`}</Text>
                                <Text fontSize="xs" color="gray.500">ID: {invoice.Id}</Text>
                              </VStack>
                            </Td>
                            <Td>{invoice.CustomerRef?.name || 'N/A'}</Td>
                            <Td fontWeight="bold">${invoice.TotalAmt || 0}</Td>
                            <Td>
                              <Badge colorScheme={invoice.Balance === 0 ? "green" : "yellow"}>
                                {invoice.Balance === 0 ? "Paid" : "Pending"}
                              </Badge>
                            </Td>
                            <Td>
                              <HStack spacing={2}>
                                <Button
                                  size="xs"
                                  variant="ghost"
                                  onClick={() => openEditModal(invoice)}
                                >
                                  <EditIcon />
                                </Button>
                                <Button
                                  size="xs"
                                  variant="ghost"
                                  colorScheme="red"
                                  onClick={() => handleDeleteInvoice(invoice.Id)}
                                >
                                  <DeleteIcon />
                                </Button>
                              </HStack>
                            </Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </TableContainer>
                </CardBody>
              </Card>
            </TabPanel>

            {/* Customers Tab */}
            <TabPanel>
              <Card>
                <CardHeader>
                  <Heading size="md">Customers</Heading>
                </CardHeader>
                <CardBody>
                  <TableContainer>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Name</Th>
                          <Th>Email</Th>
                          <Th>Phone</Th>
                          <Th>Balance</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {filteredCustomers.map((customer: any) => (
                          <Tr key={customer.Id}>
                            <Td>
                              <VStack align="start" spacing={0}>
                                <Text fontWeight="medium">{customer.DisplayName}</Text>
                                <Text fontSize="xs" color="gray.500">ID: {customer.Id}</Text>
                              </VStack>
                            </Td>
                            <Td>{customer.PrimaryEmailAddr?.Address || 'N/A'}</Td>
                            <Td>{customer.PrimaryPhone?.FreeFormNumber || 'N/A'}</Td>
                            <Td fontWeight="bold">${customer.Balance || 0}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </TableContainer>
                </CardBody>
              </Card>
            </TabPanel>

            {/* Expenses Tab */}
            <TabPanel>
              <Card>
                <CardHeader>
                  <Heading size="md">Expenses</Heading>
                </CardHeader>
                <CardBody>
                  <TableContainer>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Description</Th>
                          <Th>Account</Th>
                          <Th>Amount</Th>
                          <Th>Date</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {filteredExpenses.map((expense: any) => (
                          <Tr key={expense.Id}>
                            <Td>
                              <VStack align="start" spacing={0}>
                                <Text fontWeight="medium">{expense.Description || 'Expense'}</Text>
                                <Text fontSize="xs" color="gray.500">ID: {expense.Id}</Text>
                              </VStack>
                            </Td>
                            <Td>{expense.AccountRef?.name || 'N/A'}</Td>
                            <Td fontWeight="bold">${expense.TotalAmt || 0}</Td>
                            <Td>{expense.TxnDate || 'N/A'}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </TableContainer>
                </CardBody>
              </Card>
            </TabPanel>

            {/* Accounts Tab */}
            <TabPanel>
              <Card>
                <CardHeader>
                  <Heading size="md">Accounts</Heading>
                </CardHeader>
                <CardBody>
                  <TableContainer>
                    <Table variant="simple">
                      <Thead>
                        <Tr>
                          <Th>Name</Th>
                          <Th>Type</Th>
                          <Th>Classification</Th>
                          <Th>Balance</Th>
                        </Tr>
                      </Thead>
                      <Tbody>
                        {(data.accounts || []).map((account: any) => (
                          <Tr key={account.Id}>
                            <Td>
                              <VStack align="start" spacing={0}>
                                <Text fontWeight="medium">{account.Name}</Text>
                                <Text fontSize="xs" color="gray.500">ID: {account.Id}</Text>
                              </VStack>
                            </Td>
                            <Td>
                              <Badge colorScheme="blue">{account.AccountType || 'N/A'}</Badge>
                            </Td>
                            <Td>{account.AccountClassification || 'N/A'}</Td>
                            <Td fontWeight="bold">${account.CurrentBalance || 0}</Td>
                          </Tr>
                        ))}
                      </Tbody>
                    </Table>
                  </TableContainer>
                </CardBody>
              </Card>
            </TabPanel>
          </TabPanels>
        </Tabs>

        {/* Invoice Modal */}
        <Modal isOpen={isModalOpen} onClose={onModalClose} size="lg">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>
              {isEditing ? 'Edit Invoice' : 'Create New Invoice'}
            </ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4}>
                <FormControl>
                  <FormLabel>Customer</FormLabel>
                  <Select
                    placeholder="Select customer"
                    value={formData.customer_id}
                    onChange={(e) => setFormData({ ...formData, customer_id: e.target.value })}
                  >
                    {data.customers?.map((customer: any) => (
                      <option key={customer.Id} value={customer.Id}>
                        {customer.DisplayName}
                      </option>
                    ))}
                  </Select>
                </FormControl>

                <FormControl>
                  <FormLabel>Amount</FormLabel>
                  <NumberInput
                    value={formData.amount}
                    onChange={(value) => setFormData({ ...formData, amount: parseFloat(value) || 0 })}
                    min={0}
                    precision={2}
                  >
                    <NumberInputField />
                    <NumberInputStepper>
                      <NumberIncrementStepper />
                      <NumberDecrementStepper />
                    </NumberInputStepper>
                  </NumberInput>
                </FormControl>

                <FormControl>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Invoice description"
                  />
                </FormControl>

                <FormControl>
                  <FormLabel>Due Date</FormLabel>
                  <Input
                    type="date"
                    value={formData.due_date}
                    onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
                  />
                </FormControl>
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button variant="outline" mr={3} onClick={onModalClose}>
                Cancel
              </Button>
              <Button colorScheme="green" onClick={handleInvoiceSubmit}>
                {isEditing ? 'Update' : 'Create'} Invoice
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>

        {/* Report Modal */}
        <Modal isOpen={isReportOpen} onClose={onReportClose} size="xl">
          <ModalOverlay />
          <ModalContent>
            <ModalHeader>Financial Report</ModalHeader>
            <ModalCloseButton />
            <ModalBody>
              <VStack spacing={4} align="stretch">
                {data.reports?.profitandloss && (
                  <Card>
                    <CardHeader>
                      <Heading size="sm">Profit & Loss Summary</Heading>
                    </CardHeader>
                    <CardBody>
                      <Text>Report data would be displayed here in detail</Text>
                    </CardBody>
                  </Card>
                )}
                {data.reports?.balancesheet && (
                  <Card>
                    <CardHeader>
                      <Heading size="sm">Balance Sheet Summary</Heading>
                    </CardHeader>
                    <CardBody>
                      <Text>Balance sheet data would be displayed here</Text>
                    </CardBody>
                  </Card>
                )}
                {data.reports?.cashflow && (
                  <Card>
                    <CardHeader>
                      <Heading size="sm">Cash Flow Summary</Heading>
                    </CardHeader>
                    <CardBody>
                      <Text>Cash flow data would be displayed here</Text>
                    </CardBody>
                  </Card>
                )}
              </VStack>
            </ModalBody>
            <ModalFooter>
              <Button colorScheme="blue" onClick={onReportClose}>
                Close
              </Button>
            </ModalFooter>
          </ModalContent>
        </Modal>
      </VStack>
    </Box>
  );
};

export default QuickBooksIntegrationPage;