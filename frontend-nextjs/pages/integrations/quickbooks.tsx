/**
 * QuickBooks Integration Page
 * Complete QuickBooks financial management and accounting integration
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
  NumberInput,
  NumberInputField,
  Checkbox,
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
  MoneyIcon,
  FileIcon,
  DownloadIcon,
  ExternalLinkIcon,
} from "@chakra-ui/icons";

interface QuickBooksCustomer {
  Id: string;
  DisplayName: string;
  Balance: number;
  BalanceWithJobs: number;
  PreferredDeliveryMethod: string;
  PrimaryPhone?: {
    FreeFormNumber: string;
  };
  PrimaryEmailAddr?: {
    Address: string;
  };
  PrimaryAddr?: {
    Line1: string;
    Line2?: string;
    Line3?: string;
    Line4?: string;
    Line5?: string;
    City: string;
    Country: string;
    CountrySubDivisionCode: string;
    PostalCode: string;
    Lat?: string;
    Long?: string;
  };
  CompanyName?: string;
    MiddleName?: string;
    FullyQualifiedName?: string;
    Title?: string;
    PrintOnCheckName?: string;
    Active: boolean;
    MetaData: {
      CreateTime: string;
      LastUpdatedTime: string;
    };
    Sparse?: boolean;
}

interface QuickBooksInvoice {
  Id: string;
  DocNumber: string;
  TxnDate: string;
  DueDate: string;
  Balance: number;
  TotalAmt: number;
  CustomerRef: {
    value: string;
    name: string;
  };
  CustomerMemo?: string;
  SalesTermRef?: {
    value: string;
    name: string;
  };
  DueDate?: string;
  Balance: number;
  TotalAmt: number;
  ApplyTaxAfterDiscount?: boolean;
  PrintStatus: string;
  EmailStatus: string;
  BillEmail?: {
    Address: string;
  };
  BillEmailCc?: string;
  BillEmailBcc?: string;
  InvoiceLink?: string;
  PrivateNote?: string;
  Deposit?: number;
  DepositToAccountRef?: {
    value: string;
    name: string;
  };
  AllowIPNPayment?: boolean;
  AllowOnlinePayment?: boolean;
  AllowOnlineCreditCardPayment?: boolean;
  AllowOnlineACHPayment?: boolean;
  EInvoiceStatus?: string;
  ETransferredStatus?: string;
  DeliveryInfo?: {
    DeliveryMethod: string;
    DeliveryTime: string;
    DeliveryType: string;
  };
}

interface QuickBooksBill {
  Id: string;
  DocNumber: string;
  TxnDate: string;
  DueDate: string;
  TotalAmt: number;
  Balance: number;
  VendorRef: {
    value: string;
    name: string;
  };
  AccountRef?: {
    value: string;
    name: string;
  };
  Line: Array<{
    Id?: string;
    LineNum?: number;
    Description?: string;
    Amount?: number;
    DetailType?: string;
    SalesItemLineDetail?: {
      ItemRef?: {
        value: string;
        name: string;
      };
      UnitPrice?: number;
      Qty?: number;
      TaxCodeRef?: {
        value: string;
        name: string;
      };
    };
    AccountBasedExpenseLineDetail?: {
      AccountRef?: {
        value: string;
        name: string;
      };
      TaxCodeRef?: {
        value: string;
        name: string;
      };
    };
  }>;
  PrivateNote?: string;
  Memo?: string;
  Attachments?: Array<{
    Id: string;
    FileName: string;
    ContentType: string;
    TempDownloadUri: string;
  }>;
  GlobalTaxCalculation?: string;
}

interface QuickBooksAccount {
  Id: string;
  Name: string;
  Classification: string;
  AccountType: string;
  AccountSubType: string;
  AcctNum?: string;
  Description?: string;
  OpeningBalance?: number;
  CurrentBalance: number;
  CurrentBalanceWithSubAccounts?: number;
  CurrencyRef?: {
    value: string;
    name: string;
  };
  Active: boolean;
  SubAccount?: boolean;
  ParentAccountRef?: {
    value: string;
    name: string;
  };
  Level?: number;
}

interface QuickBooksEmployee {
  Id: string;
  DisplayName: string;
  Title?: string;
  PrimaryAddr?: {
    Line1: string;
    City: string;
    Country: string;
    CountrySubDivisionCode: string;
    PostalCode: string;
  };
  PrimaryPhone?: {
    FreeFormNumber: string;
  };
  PrimaryEmailAddr?: {
    Address: string;
  };
  HiredDate?: string;
  ReleasedDate?: string;
  BillableTime?: boolean;
  BillRate?: number;
  Status: string;
  Ssn?: string;
  SSN?: string;
  Gender?: string;
  BirthDate?: string;
  Active: boolean;
  EmployeeType?: string;
  HourlyRate?: number;
  BillableTime?: boolean;
  BillRate?: number;
  Status: string;
}

interface QuickBooksVendor {
  Id: string;
  DisplayName: string;
  Balance: number;
  PrimaryPhone?: {
    FreeFormNumber: string;
  };
  PrimaryEmailAddr?: {
    Address: string;
  };
  PrimaryAddr?: {
    Line1: string;
    City: string;
    Country: string;
    CountrySubDivisionCode: string;
    PostalCode: string;
  };
  CompanyName?: string;
  TaxIdentifier?: string;
  AcctNum?: string;
  Active: boolean;
  CurrencyRef?: {
    value: string;
    name: string;
  };
}

const QuickBooksIntegration: React.FC = () => {
  const [customers, setCustomers] = useState<QuickBooksCustomer[]>([]);
  const [invoices, setInvoices] = useState<QuickBooksInvoice[]>([]);
  const [bills, setBills] = useState<QuickBooksBill[]>([]);
  const [accounts, setAccounts] = useState<QuickBooksAccount[]>([]);
  const [employees, setEmployees] = useState<QuickBooksEmployee[]>([]);
  const [vendors, setVendors] = useState<QuickBooksVendor[]>([]);
  const [companyInfo, setCompanyInfo] = useState<any>(null);
  const [loading, setLoading] = useState({
    customers: false,
    invoices: false,
    bills: false,
    accounts: false,
    employees: false,
    vendors: false,
    company: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState("all");

  // Form states
  const [customerForm, setCustomerForm] = useState({
    DisplayName: "",
    CompanyName: "",
    PrimaryEmailAddr: {
      Address: "",
    },
    PrimaryPhone: {
      FreeFormNumber: "",
    },
    PrimaryAddr: {
      Line1: "",
      City: "",
      Country: "",
      CountrySubDivisionCode: "",
      PostalCode: "",
    },
  });

  const [invoiceForm, setInvoiceForm] = useState({
    CustomerRef: {
      value: "",
      name: "",
    },
    TxnDate: "",
    DueDate: "",
    Line: [] as Array<{
      Description: string;
      Amount: number;
      SalesItemLineDetail: {
        ItemRef: {
          value: string;
          name: string;
        };
        Qty: number;
        UnitPrice: number;
      };
    }>,
  });

  const [billForm, setBillForm] = useState({
    VendorRef: {
      value: "",
      name: "",
    },
    TxnDate: "",
    DueDate: "",
    Line: [] as Array<{
      Description: string;
      Amount: number;
      AccountBasedExpenseLineDetail: {
        AccountRef: {
          value: string;
          name: string;
        };
      };
    }>,
  });

  const {
    isOpen: isCustomerOpen,
    onOpen: onCustomerOpen,
    onClose: onCustomerClose,
  } = useDisclosure();
  const {
    isOpen: isInvoiceOpen,
    onOpen: onInvoiceOpen,
    onClose: onInvoiceClose,
  } = useDisclosure();
  const {
    isOpen: isBillOpen,
    onOpen: onBillOpen,
    onClose: onBillClose,
  } = useDisclosure();

  const toast = useToast();
  const bgColor = useColorModeValue("white", "gray.800");
  const borderColor = useColorModeValue("gray.200", "gray.700");

  // Check connection status
  const checkConnection = async () => {
    try {
      const response = await fetch("/api/integrations/quickbooks/health");
      if (response.ok) {
        setConnected(true);
        setHealthStatus("healthy");
        loadCompanyInfo();
        loadCustomers();
        loadInvoices();
        loadBills();
        loadAccounts();
        loadEmployees();
        loadVendors();
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

  // Load QuickBooks data
  const loadCompanyInfo = async () => {
    setLoading((prev) => ({ ...prev, company: true }));
    try {
      const response = await fetch("/api/integrations/quickbooks/company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCompanyInfo(data.data?.company || null);
      }
    } catch (error) {
      console.error("Failed to load company info:", error);
    } finally {
      setLoading((prev) => ({ ...prev, company: false }));
    }
  };

  const loadCustomers = async () => {
    setLoading((prev) => ({ ...prev, customers: true }));
    try {
      const response = await fetch("/api/integrations/quickbooks/customers", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCustomers(data.data?.customers || []);
      }
    } catch (error) {
      console.error("Failed to load customers:", error);
      toast({
        title: "Error",
        description: "Failed to load customers from QuickBooks",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, customers: false }));
    }
  };

  const loadInvoices = async () => {
    setLoading((prev) => ({ ...prev, invoices: true }));
    try {
      const response = await fetch("/api/integrations/quickbooks/invoices", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setInvoices(data.data?.invoices || []);
      }
    } catch (error) {
      console.error("Failed to load invoices:", error);
    } finally {
      setLoading((prev) => ({ ...prev, invoices: false }));
    }
  };

  const loadBills = async () => {
    setLoading((prev) => ({ ...prev, bills: true }));
    try {
      const response = await fetch("/api/integrations/quickbooks/bills", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setBills(data.data?.bills || []);
      }
    } catch (error) {
      console.error("Failed to load bills:", error);
    } finally {
      setLoading((prev) => ({ ...prev, bills: false }));
    }
  };

  const loadAccounts = async () => {
    setLoading((prev) => ({ ...prev, accounts: true }));
    try {
      const response = await fetch("/api/integrations/quickbooks/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setAccounts(data.data?.accounts || []);
      }
    } catch (error) {
      console.error("Failed to load accounts:", error);
    } finally {
      setLoading((prev) => ({ ...prev, accounts: false }));
    }
  };

  const loadEmployees = async () => {
    setLoading((prev) => ({ ...prev, employees: true }));
    try {
      const response = await fetch("/api/integrations/quickbooks/employees", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setEmployees(data.data?.employees || []);
      }
    } catch (error) {
      console.error("Failed to load employees:", error);
    } finally {
      setLoading((prev) => ({ ...prev, employees: false }));
    }
  };

  const loadVendors = async () => {
    setLoading((prev) => ({ ...prev, vendors: true }));
    try {
      const response = await fetch("/api/integrations/quickbooks/vendors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 100,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setVendors(data.data?.vendors || []);
      }
    } catch (error) {
      console.error("Failed to load vendors:", error);
    } finally {
      setLoading((prev) => ({ ...prev, vendors: false }));
    }
  };

  // Create operations
  const createCustomer = async () => {
    if (!customerForm.DisplayName) return;

    try {
      const response = await fetch("/api/integrations/quickbooks/customers/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          ...customerForm,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Customer created successfully",
          status: "success",
          duration: 3000,
        });
        onCustomerClose();
        setCustomerForm({
          DisplayName: "",
          CompanyName: "",
          PrimaryEmailAddr: {
            Address: "",
          },
          PrimaryPhone: {
            FreeFormNumber: "",
          },
          PrimaryAddr: {
            Line1: "",
            City: "",
            Country: "",
            CountrySubDivisionCode: "",
            PostalCode: "",
          },
        });
        loadCustomers();
      }
    } catch (error) {
      console.error("Failed to create customer:", error);
      toast({
        title: "Error",
        description: "Failed to create customer",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createInvoice = async () => {
    if (!invoiceForm.CustomerRef.value || invoiceForm.Line.length === 0) return;

    try {
      const response = await fetch("/api/integrations/quickbooks/invoices/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          ...invoiceForm,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Invoice created successfully",
          status: "success",
          duration: 3000,
        });
        onInvoiceClose();
        setInvoiceForm({
          CustomerRef: {
            value: "",
            name: "",
          },
          TxnDate: "",
          DueDate: "",
          Line: [],
        });
        loadInvoices();
      }
    } catch (error) {
      console.error("Failed to create invoice:", error);
      toast({
        title: "Error",
        description: "Failed to create invoice",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createBill = async () => {
    if (!billForm.VendorRef.value || billForm.Line.length === 0) return;

    try {
      const response = await fetch("/api/integrations/quickbooks/bills/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          ...billForm,
        }),
      });

      if (response.ok) {
        toast({
          title: "Success",
          description: "Bill created successfully",
          status: "success",
          duration: 3000,
        });
        onBillClose();
        setBillForm({
          VendorRef: {
            value: "",
            name: "",
          },
          TxnDate: "",
          DueDate: "",
          Line: [],
        });
        loadBills();
      }
    } catch (error) {
      console.error("Failed to create bill:", error);
      toast({
        title: "Error",
        description: "Failed to create bill",
        status: "error",
        duration: 3000,
      });
    }
  };

  // Filter data based on search
  const filteredCustomers = customers.filter(
    (customer) =>
      customer.DisplayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      customer.CompanyName?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredInvoices = invoices.filter(
    (invoice) =>
      invoice.DocNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      invoice.CustomerRef.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredBills = bills.filter(
    (bill) =>
      bill.DocNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
      bill.VendorRef.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredAccounts = accounts.filter(
    (account) =>
      account.Name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      account.AccountType.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredEmployees = employees.filter(
    (employee) =>
      employee.DisplayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      employee.Title?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const filteredVendors = vendors.filter(
    (vendor) =>
      vendor.DisplayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      vendor.CompanyName?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Stats calculations
  const totalCustomers = customers.length;
  const totalInvoices = invoices.length;
  const totalBills = bills.length;
  const totalAccounts = accounts.length;
  const totalEmployees = employees.length;
  const totalVendors = vendors.length;
  const outstandingInvoices = invoices.reduce((sum, inv) => sum + inv.Balance, 0);
  const outstandingBills = bills.reduce((sum, bill) => sum + bill.Balance, 0);
  const totalRevenue = invoices.reduce((sum, inv) => sum + inv.TotalAmt, 0);
  const activeEmployees = employees.filter(emp => emp.Active).length;

  useEffect(() => {
    checkConnection();
  }, []);

  useEffect(() => {
    if (connected) {
      loadCompanyInfo();
      loadCustomers();
      loadInvoices();
      loadBills();
      loadAccounts();
      loadEmployees();
      loadVendors();
    }
  }, [connected]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const formatCurrency = (amount: number): string => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const getStatusColor = (active: boolean): string => {
    return active ? "green" : "red";
  };

  const getBalanceColor = (balance: number): string => {
    if (balance > 0) return "orange";
    if (balance < 0) return "green";
    return "gray";
  };

  const getAccountTypeColor = (type: string): string => {
    switch (type?.toLowerCase()) {
      case "asset":
        return "blue";
      case "liability":
        return "orange";
      case "equity":
        return "green";
      case "revenue":
        return "purple";
      case "expense":
        return "red";
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
            <Icon as={SettingsIcon} w={8} h={8} color="#2CA01C" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">QuickBooks Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Financial management and accounting platform
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

          {companyInfo && (
            <HStack spacing={4}>
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">{companyInfo.CompanyName}</Text>
                <Text fontSize="sm" color="gray.600">
                  {companyInfo.LegalName || companyInfo.CompanyName}
                </Text>
                {companyInfo.Email && (
                  <Text fontSize="sm" color="gray.500">
                    {companyInfo.Email.Address}
                  </Text>
                )}
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
                  <Heading size="lg">Connect QuickBooks</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your QuickBooks account to start managing finances and accounting
                  </Text>
                </VStack>
                <Button
                  colorScheme="green"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/quickbooks/auth/start")
                  }
                >
                  Connect QuickBooks Account
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
                    <StatLabel>Customers</StatLabel>
                    <StatNumber>{totalCustomers}</StatNumber>
                    <StatHelpText>{formatCurrency(outstandingInvoices)} outstanding</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Invoices</StatLabel>
                    <StatNumber>{totalInvoices}</StatNumber>
                    <StatHelpText>{formatCurrency(totalRevenue)} total</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Bills</StatLabel>
                    <StatNumber>{totalBills}</StatNumber>
                    <StatHelpText>{formatCurrency(outstandingBills)} outstanding</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Employees</StatLabel>
                    <StatNumber>{activeEmployees}</StatNumber>
                    <StatHelpText>{totalEmployees} total</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Customers</Tab>
                <Tab>Invoices</Tab>
                <Tab>Bills</Tab>
                <Tab>Accounts</Tab>
                <Tab>Employees</Tab>
                <Tab>Vendors</Tab>
              </TabList>

              <TabPanels>
                {/* Customers Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search customers..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="green"
                        leftIcon={<AddIcon />}
                        onClick={onCustomerOpen}
                      >
                        Create Customer
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Company</Th>
                                <Th>Email</Th>
                                <Th>Phone</Th>
                                <Th>Balance</Th>
                                <Th>Status</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.customers ? (
                                <Tr><Td colSpan={7}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                filteredCustomers.map((customer) => (
                                  <Tr key={customer.Id}>
                                    <Td>
                                      <Text fontWeight="bold">{customer.DisplayName}</Text>
                                    </Td>
                                    <Td>{customer.CompanyName}</Td>
                                    <Td>{customer.PrimaryEmailAddr?.Address}</Td>
                                    <Td>{customer.PrimaryPhone?.FreeFormNumber}</Td>
                                    <Td>
                                      <Tag colorScheme={getBalanceColor(customer.Balance)} size="sm">
                                        {formatCurrency(customer.Balance)}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={getStatusColor(customer.Active)} size="sm">
                                        {customer.Active ? "Active" : "Inactive"}
                                      </Tag>
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

                {/* Invoices Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search invoices..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="green"
                        leftIcon={<AddIcon />}
                        onClick={onInvoiceOpen}
                      >
                        Create Invoice
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Invoice #</Th>
                                <Th>Customer</Th>
                                <Th>Date</Th>
                                <Th>Due Date</Th>
                                <Th>Total</Th>
                                <Th>Balance</Th>
                                <Th>Status</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.invoices ? (
                                <Tr><Td colSpan={8}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                filteredInvoices.map((invoice) => (
                                  <Tr key={invoice.Id}>
                                    <Td>
                                      <Text fontWeight="bold">{invoice.DocNumber}</Text>
                                    </Td>
                                    <Td>{invoice.CustomerRef.name}</Td>
                                    <Td>{formatDate(invoice.TxnDate)}</Td>
                                    <Td>{formatDate(invoice.DueDate)}</Td>
                                    <Td>{formatCurrency(invoice.TotalAmt)}</Td>
                                    <Td>
                                      <Tag colorScheme={getBalanceColor(invoice.Balance)} size="sm">
                                        {formatCurrency(invoice.Balance)}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={invoice.Balance > 0 ? "orange" : "green"} size="sm">
                                        {invoice.Balance > 0 ? "Outstanding" : "Paid"}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <HStack>
                                        <Button size="sm" variant="outline" leftIcon={<ViewIcon />}>
                                          Details
                                        </Button>
                                        {invoice.InvoiceLink && (
                                          <Button
                                            size="sm"
                                            variant="outline"
                                            leftIcon={<ExternalLinkIcon />}
                                            onClick={() => window.open(invoice.InvoiceLink, "_blank")}
                                          >
                                            View
                                          </Button>
                                        )}
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

                {/* Bills Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search bills..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="green"
                        leftIcon={<AddIcon />}
                        onClick={onBillOpen}
                      >
                        Create Bill
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Bill #</Th>
                                <Th>Vendor</Th>
                                <Th>Date</Th>
                                <Th>Due Date</Th>
                                <Th>Total</Th>
                                <Th>Balance</Th>
                                <Th>Status</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.bills ? (
                                <Tr><Td colSpan={8}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                filteredBills.map((bill) => (
                                  <Tr key={bill.Id}>
                                    <Td>
                                      <Text fontWeight="bold">{bill.DocNumber}</Text>
                                    </Td>
                                    <Td>{bill.VendorRef.name}</Td>
                                    <Td>{formatDate(bill.TxnDate)}</Td>
                                    <Td>{formatDate(bill.DueDate)}</Td>
                                    <Td>{formatCurrency(bill.TotalAmt)}</Td>
                                    <Td>
                                      <Tag colorScheme={getBalanceColor(bill.Balance)} size="sm">
                                        {formatCurrency(bill.Balance)}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={bill.Balance > 0 ? "orange" : "green"} size="sm">
                                        {bill.Balance > 0 ? "Outstanding" : "Paid"}
                                      </Tag>
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

                {/* Accounts Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search accounts..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Type</Th>
                                <Th>SubType</Th>
                                <th>Classification</th>
                                <Th>Current Balance</Th>
                                <Th>Status</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.accounts ? (
                                <Tr><Td colSpan={6}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                filteredAccounts.map((account) => (
                                  <Tr key={account.Id}>
                                    <Td>
                                      <Text fontWeight="bold">{account.Name}</Text>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={getAccountTypeColor(account.AccountType)} size="sm">
                                        {account.AccountType}
                                      </Tag>
                                    </Td>
                                    <Td>{account.AccountSubType}</Td>
                                    <Td>{account.Classification}</Td>
                                    <Td>
                                      <Tag colorScheme={getBalanceColor(account.CurrentBalance)} size="sm">
                                        {formatCurrency(account.CurrentBalance)}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={getStatusColor(account.Active)} size="sm">
                                        {account.Active ? "Active" : "Inactive"}
                                      </Tag>
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

                {/* Employees Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search employees..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Title</Th>
                                <Th>Email</Th>
                                <Th>Phone</Th>
                                <th>Bill Rate</th>
                                <Th>Status</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.employees ? (
                                <Tr><Td colSpan={6}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                filteredEmployees.map((employee) => (
                                  <Tr key={employee.Id}>
                                    <Td>
                                      <Text fontWeight="bold">{employee.DisplayName}</Text>
                                    </Td>
                                    <Td>{employee.Title}</Td>
                                    <Td>{employee.PrimaryEmailAddr?.Address}</Td>
                                    <Td>{employee.PrimaryPhone?.FreeFormNumber}</Td>
                                    <Td>
                                      {employee.BillRate ? (
                                        <Tag colorScheme="blue" size="sm">
                                          {formatCurrency(employee.BillRate)}
                                        </Tag>
                                      ) : (
                                        <Text color="gray.400">-</Text>
                                      )}
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={getStatusColor(employee.Active)} size="sm">
                                        {employee.Active ? "Active" : employee.Status}
                                      </Tag>
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

                {/* Vendors Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search vendors..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftElement={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Company</Th>
                                <Th>Email</Th>
                                <Th>Phone</Th>
                                <Th>Balance</Th>
                                <Th>Status</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.vendors ? (
                                <Tr><Td colSpan={6}><Spinner size="xl" /></Td></Tr>
                              ) : (
                                filteredVendors.map((vendor) => (
                                  <Tr key={vendor.Id}>
                                    <Td>
                                      <Text fontWeight="bold">{vendor.DisplayName}</Text>
                                    </Td>
                                    <Td>{vendor.CompanyName}</Td>
                                    <Td>{vendor.PrimaryEmailAddr?.Address}</Td>
                                    <Td>{vendor.PrimaryPhone?.FreeFormNumber}</Td>
                                    <Td>
                                      <Tag colorScheme={getBalanceColor(vendor.Balance)} size="sm">
                                        {formatCurrency(vendor.Balance)}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag colorScheme={getStatusColor(vendor.Active)} size="sm">
                                        {vendor.Active ? "Active" : "Inactive"}
                                      </Tag>
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
              </TabPanels>
            </Tabs>

            {/* Create Customer Modal */}
            <Modal isOpen={isCustomerOpen} onClose={onCustomerClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Customer</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Display Name</FormLabel>
                      <Input
                        placeholder="Customer name"
                        value={customerForm.DisplayName}
                        onChange={(e) =>
                          setCustomerForm({
                            ...customerForm,
                            DisplayName: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Company Name</FormLabel>
                      <Input
                        placeholder="Company name"
                        value={customerForm.CompanyName}
                        onChange={(e) =>
                          setCustomerForm({
                            ...customerForm,
                            CompanyName: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Email</FormLabel>
                      <Input
                        type="email"
                        placeholder="email@example.com"
                        value={customerForm.PrimaryEmailAddr.Address}
                        onChange={(e) =>
                          setCustomerForm({
                            ...customerForm,
                            PrimaryEmailAddr: {
                              ...customerForm.PrimaryEmailAddr,
                              Address: e.target.value,
                            },
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Phone</FormLabel>
                      <Input
                        placeholder="Phone number"
                        value={customerForm.PrimaryPhone.FreeFormNumber}
                        onChange={(e) =>
                          setCustomerForm({
                            ...customerForm,
                            PrimaryPhone: {
                              ...customerForm.PrimaryPhone,
                              FreeFormNumber: e.target.value,
                            },
                          })
                        }
                      />
                    </FormControl>

                    <FormControl>
                      <FormLabel>Address</FormLabel>
                      <VStack spacing={2}>
                        <Input
                          placeholder="Street"
                          value={customerForm.PrimaryAddr.Line1}
                          onChange={(e) =>
                            setCustomerForm({
                              ...customerForm,
                              PrimaryAddr: {
                                ...customerForm.PrimaryAddr,
                                Line1: e.target.value,
                              },
                            })
                          }
                        />
                        <HStack spacing={2}>
                          <Input
                            placeholder="City"
                            value={customerForm.PrimaryAddr.City}
                            onChange={(e) =>
                              setCustomerForm({
                                ...customerForm,
                                PrimaryAddr: {
                                  ...customerForm.PrimaryAddr,
                                  City: e.target.value,
                                },
                              })
                            }
                          />
                          <Input
                            placeholder="State"
                            value={customerForm.PrimaryAddr.CountrySubDivisionCode}
                            onChange={(e) =>
                              setCustomerForm({
                                ...customerForm,
                                PrimaryAddr: {
                                  ...customerForm.PrimaryAddr,
                                  CountrySubDivisionCode: e.target.value,
                                },
                              })
                            }
                          />
                          <Input
                            placeholder="Postal Code"
                            value={customerForm.PrimaryAddr.PostalCode}
                            onChange={(e) =>
                              setCustomerForm({
                                ...customerForm,
                                PrimaryAddr: {
                                  ...customerForm.PrimaryAddr,
                                  PostalCode: e.target.value,
                                },
                              })
                            }
                          />
                        </HStack>
                        <Input
                          placeholder="Country"
                          value={customerForm.PrimaryAddr.Country}
                          onChange={(e) =>
                            setCustomerForm({
                              ...customerForm,
                              PrimaryAddr: {
                                ...customerForm.PrimaryAddr,
                                Country: e.target.value,
                              },
                            })
                          }
                        />
                      </VStack>
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onCustomerClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="green"
                    onClick={createCustomer}
                    disabled={!customerForm.DisplayName}
                  >
                    Create Customer
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Invoice Modal */}
            <Modal isOpen={isInvoiceOpen} onClose={onInvoiceClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Invoice</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Customer</FormLabel>
                      <Select
                        value={invoiceForm.CustomerRef.value}
                        onChange={(e) => {
                          const customer = customers.find(c => c.Id === e.target.value);
                          setInvoiceForm({
                            ...invoiceForm,
                            CustomerRef: {
                              value: e.target.value,
                              name: customer?.DisplayName || "",
                            },
                          });
                        }}
                      >
                        <option value="">Select Customer</option>
                        {customers.map((customer) => (
                          <option key={customer.Id} value={customer.Id}>
                            {customer.DisplayName}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl isRequired>
                        <FormLabel>Invoice Date</FormLabel>
                        <Input
                          type="date"
                          value={invoiceForm.TxnDate}
                          onChange={(e) =>
                            setInvoiceForm({
                              ...invoiceForm,
                              TxnDate: e.target.value,
                            })
                          }
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Due Date</FormLabel>
                        <Input
                          type="date"
                          value={invoiceForm.DueDate}
                          onChange={(e) =>
                            setInvoiceForm({
                              ...invoiceForm,
                              DueDate: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <Text fontWeight="bold">Invoice Lines</Text>
                    {invoiceForm.Line.map((line, index) => (
                      <HStack key={index} spacing={2}>
                        <Input
                          placeholder="Description"
                          value={line.Description}
                          onChange={(e) => {
                            const newLines = [...invoiceForm.Line];
                            newLines[index].Description = e.target.value;
                            setInvoiceForm({ ...invoiceForm, Line: newLines });
                          }}
                        />
                        <NumberInput
                          value={line.Amount}
                          onChange={(value) => {
                            const newLines = [...invoiceForm.Line];
                            newLines[index].Amount = value;
                            setInvoiceForm({ ...invoiceForm, Line: newLines });
                          }}
                        >
                          <NumberInputField />
                        </NumberInput>
                        <Button
                          size="sm"
                          variant="outline"
                          colorScheme="red"
                          onClick={() => {
                            const newLines = invoiceForm.Line.filter((_, i) => i !== index);
                            setInvoiceForm({ ...invoiceForm, Line: newLines });
                          }}
                        >
                          Remove
                        </Button>
                      </HStack>
                    ))}

                    <Button
                      variant="outline"
                      leftIcon={<AddIcon />}
                      onClick={() => {
                        setInvoiceForm({
                          ...invoiceForm,
                          Line: [
                            ...invoiceForm.Line,
                            {
                              Description: "",
                              Amount: 0,
                              SalesItemLineDetail: {
                                ItemRef: {
                                  value: "",
                                  name: "",
                                },
                                Qty: 1,
                                UnitPrice: 0,
                              },
                            },
                          ],
                        });
                      }}
                    >
                      Add Line
                    </Button>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onInvoiceClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="green"
                    onClick={createInvoice}
                    disabled={!invoiceForm.CustomerRef.value || invoiceForm.Line.length === 0}
                  >
                    Create Invoice
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Bill Modal */}
            <Modal isOpen={isBillOpen} onClose={onBillClose} size="lg">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Bill</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Vendor</FormLabel>
                      <Select
                        value={billForm.VendorRef.value}
                        onChange={(e) => {
                          const vendor = vendors.find(v => v.Id === e.target.value);
                          setBillForm({
                            ...billForm,
                            VendorRef: {
                              value: e.target.value,
                              name: vendor?.DisplayName || "",
                            },
                          });
                        }}
                      >
                        <option value="">Select Vendor</option>
                        {vendors.map((vendor) => (
                          <option key={vendor.Id} value={vendor.Id}>
                            {vendor.DisplayName}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl isRequired>
                        <FormLabel>Bill Date</FormLabel>
                        <Input
                          type="date"
                          value={billForm.TxnDate}
                          onChange={(e) =>
                            setBillForm({
                              ...billForm,
                              TxnDate: e.target.value,
                            })
                          }
                        />
                      </FormControl>

                      <FormControl>
                        <FormLabel>Due Date</FormLabel>
                        <Input
                          type="date"
                          value={billForm.DueDate}
                          onChange={(e) =>
                            setBillForm({
                              ...billForm,
                              DueDate: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <Text fontWeight="bold">Bill Lines</Text>
                    {billForm.Line.map((line, index) => (
                      <HStack key={index} spacing={2}>
                        <Input
                          placeholder="Description"
                          value={line.Description}
                          onChange={(e) => {
                            const newLines = [...billForm.Line];
                            newLines[index].Description = e.target.value;
                            setBillForm({ ...billForm, Line: newLines });
                          }}
                        />
                        <NumberInput
                          value={line.Amount}
                          onChange={(value) => {
                            const newLines = [...billForm.Line];
                            newLines[index].Amount = value;
                            setBillForm({ ...billForm, Line: newLines });
                          }}
                        >
                          <NumberInputField />
                        </NumberInput>
                        <Button
                          size="sm"
                          variant="outline"
                          colorScheme="red"
                          onClick={() => {
                            const newLines = billForm.Line.filter((_, i) => i !== index);
                            setBillForm({ ...billForm, Line: newLines });
                          }}
                        >
                          Remove
                        </Button>
                      </HStack>
                    ))}

                    <Button
                      variant="outline"
                      leftIcon={<AddIcon />}
                      onClick={() => {
                        setBillForm({
                          ...billForm,
                          Line: [
                            ...billForm.Line,
                            {
                              Description: "",
                              Amount: 0,
                              AccountBasedExpenseLineDetail: {
                                AccountRef: {
                                  value: "",
                                  name: "",
                                },
                              },
                            },
                          ],
                        });
                      }}
                    >
                      Add Line
                    </Button>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onBillClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="green"
                    onClick={createBill}
                    disabled={!billForm.VendorRef.value || billForm.Line.length === 0}
                  >
                    Create Bill
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

export default QuickBooksIntegration;