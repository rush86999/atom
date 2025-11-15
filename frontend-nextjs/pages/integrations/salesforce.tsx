/**
 * Salesforce Integration Page
 * Complete Salesforce CRM and sales platform integration
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
  Divider,
  useColorModeValue,
  Stack,
  Flex,
  Spacer,
  Input,
  InputGroup,
  InputLeftElement,
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
  Alert,
  AlertIcon,
  TableContainer,
  Link,
} from "@chakra-ui/react";
import {
  GenericAvatarIcon,
  CheckCircleIcon,
  WarningTwoIcon,
  ArrowForwardIcon,
  AddIcon,
  SearchIcon,
  SettingsIcon,
  RepeatIcon,
  TimeIcon,
  StarIcon,
  ViewIcon,
  EditIcon,
  DeleteIcon,
  ChatIcon,
  EmailIcon,
  PhoneIcon,
  CalendarIcon,
} from "@chakra-ui/icons";

interface SalesforceLead {
  id: string;
  FirstName?: string;
  LastName: string;
  Email?: string;
  Phone?: string;
  Company?: string;
  Title?: string;
  Industry?: string;
  AnnualRevenue?: number;
  LeadSource?: string;
  Status: string;
  Rating?: string;
  Description?: string;
  Street?: string;
  City?: string;
  State?: string;
  PostalCode?: string;
  Country?: string;
  CreatedDate: string;
  LastModifiedDate: string;
  IsConverted: boolean;
  ConvertedAccountId?: string;
  ConvertedContactId?: string;
  ConvertedOpportunityId?: string;
  OwnerId: string;
  Owner: {
    Name: string;
    Email?: string;
    Title?: string;
    Department?: string;
  };
}

interface SalesforceOpportunity {
  id: string;
  Name: string;
  AccountId?: string;
  AccountName?: string;
  Amount?: number;
  CurrencyIsoCode?: string;
  CloseDate: string;
  StageName: string;
  Probability: number;
  Type?: string;
  LeadSource?: string;
  IsClosed: boolean;
  IsWon: boolean;
  ForecastCategory: string;
  Description?: string;
  ExpectedRevenue?: number;
  TotalOpportunityQuantity?: number;
  CreatedDate: string;
  LastModifiedDate: string;
  OwnerId: string;
  Owner: {
    Name: string;
    Email?: string;
    Title?: string;
  };
  ContactId?: string;
  ContactName?: string;
  CampaignId?: string;
  CampaignName?: string;
  PrimaryPartnerId?: string;
  PrimaryPartnerName?: string;
}

interface SalesforceAccount {
  id: string;
  Name: string;
  Type?: string;
  Industry?: string;
  AnnualRevenue?: number;
  Phone?: string;
  Website?: string;
  Description?: string;
  NumberOfEmployees?: number;
  BillingStreet?: string;
  BillingCity?: string;
  BillingState?: string;
  BillingPostalCode?: string;
  BillingCountry?: string;
  ShippingStreet?: string;
  ShippingCity?: string;
  ShippingState?: string;
  ShippingPostalCode?: string;
  ShippingCountry?: string;
  CreatedDate: string;
  LastModifiedDate: string;
  OwnerId: string;
  Owner: {
    Name: string;
    Email?: string;
    Title?: string;
  };
  ParentId?: string;
  ParentName?: string;
  AccountSource?: string;
  Sic?: string;
}

interface SalesforceContact {
  id: string;
  FirstName?: string;
  LastName: string;
  Email?: string;
  Phone?: string;
  MobilePhone?: string;
  Title?: string;
  Department?: string;
  AccountId?: string;
  AccountName?: string;
  LeadSource?: string;
  Description?: string;
  Birthdate?: string;
  AssistantName?: string;
  AssistantPhone?: string;
  ReportsToId?: string;
  ReportsToName?: string;
  MailingStreet?: string;
  MailingCity?: string;
  MailingState?: string;
  MailingPostalCode?: string;
  MailingCountry?: string;
  CreatedDate: string;
  LastModifiedDate: string;
  OwnerId: string;
  Owner: {
    Name: string;
    Email?: string;
    Title?: string;
  };
}

interface SalesforceCase {
  id: string;
  CaseNumber: string;
  Subject?: string;
  Description?: string;
  Status: string;
  Priority: string;
  Origin?: string;
  Type?: string;
  Reason?: string;
  IsEscalated: boolean;
  ParentId?: string;
  ParentCaseNumber?: string;
  SuppliedEmail?: string;
  SuppliedName?: string;
  SuppliedPhone?: string;
  SuppliedCompany?: string;
  ContactId?: string;
  ContactName?: string;
  AccountId?: string;
  AccountName?: string;
  CreatedDate: string;
  LastModifiedDate: string;
  ClosedDate?: string;
  OwnerId: string;
  Owner: {
    Name: string;
    Email?: string;
    Title?: string;
  };
  Comments: Array<{
    CommentBody: string;
    CreatedDate: string;
    CreatedById: string;
    CreatedBy: {
      Name: string;
      SmallPhotoUrl?: string;
    };
  }>;
}

interface SalesforceUser {
  id: string;
  Username: string;
  Email: string;
  Name: string;
  FirstName?: string;
  LastName?: string;
  Title?: string;
  Department?: string;
  CompanyName?: string;
  Phone?: string;
  MobilePhone?: string;
  Fax?: string;
  Street?: string;
  City?: string;
  State?: string;
  PostalCode?: string;
  Country?: string;
  Alias: string;
  TimeZoneSidKey: string;
  LocaleSidKey: string;
  LanguageLocaleKey: string;
  IsActive: boolean;
  Profile: {
    Name: string;
    Permissions: string[];
  };
  UserPermissions: string[];
  UserType: string;
  LastLoginDate?: string;
  CreatedDate: string;
  LastModifiedDate: string;
  UserRole?: {
    Name: string;
    DeveloperName: string;
  };
  ManagerId?: string;
  ManagerName?: string;
}

const SalesforceIntegration: React.FC = () => {
  const [leads, setLeads] = useState<SalesforceLead[]>([]);
  const [opportunities, setOpportunities] = useState<SalesforceOpportunity[]>(
    [],
  );
  const [accounts, setAccounts] = useState<SalesforceAccount[]>([]);
  const [contacts, setContacts] = useState<SalesforceContact[]>([]);
  const [cases, setCases] = useState<SalesforceCase[]>([]);
  const [users, setUsers] = useState<SalesforceUser[]>([]);
  const [userProfile, setUserProfile] = useState<SalesforceUser | null>(null);
  const [loading, setLoading] = useState({
    leads: false,
    opportunities: false,
    accounts: false,
    contacts: false,
    cases: false,
    users: false,
    profile: false,
  });
  const [connected, setConnected] = useState(false);
  const [healthStatus, setHealthStatus] = useState<
    "healthy" | "error" | "unknown"
  >("unknown");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedAccount, setSelectedAccount] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");

  // Form states
  const [leadForm, setLeadForm] = useState({
    FirstName: "",
    LastName: "",
    Email: "",
    Phone: "",
    Company: "",
    Title: "",
    Industry: "",
    AnnualRevenue: "",
    LeadSource: "",
    Status: "Open - Not Contacted",
    Rating: "",
    Description: "",
    Street: "",
    City: "",
    State: "",
    PostalCode: "",
    Country: "",
  });

  const [opportunityForm, setOpportunityForm] = useState({
    Name: "",
    AccountId: "",
    Amount: "",
    CloseDate: "",
    StageName: "Prospecting",
    Probability: "10",
    Type: "New Customer",
    LeadSource: "",
    Description: "",
  });

  const [accountForm, setAccountForm] = useState({
    Name: "",
    Type: "",
    Industry: "",
    AnnualRevenue: "",
    Phone: "",
    Website: "",
    Description: "",
    NumberOfEmployees: "",
    BillingStreet: "",
    BillingCity: "",
    BillingState: "",
    BillingPostalCode: "",
    BillingCountry: "",
  });

  const {
    isOpen: isLeadOpen,
    onOpen: onLeadOpen,
    onClose: onLeadClose,
  } = useDisclosure();
  const {
    isOpen: isOpportunityOpen,
    onOpen: onOpportunityOpen,
    onClose: onOpportunityClose,
  } = useDisclosure();
  const {
    isOpen: isAccountOpen,
    onOpen: onAccountOpen,
    onClose: onAccountClose,
  } = useDisclosure();

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
        loadUserProfile();
        loadLeads();
        loadOpportunities();
        loadAccounts();
        loadContacts();
        loadCases();
        loadUsers();
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
  const loadUserProfile = async () => {
    setLoading((prev) => ({ ...prev, profile: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/profile", {
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

  const loadLeads = async () => {
    setLoading((prev) => ({ ...prev, leads: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
          status: selectedStatus || "",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setLeads(data.data?.leads || []);
      }
    } catch (error) {
      console.error("Failed to load leads:", error);
      toast({
        title: "Error",
        description: "Failed to load leads from Salesforce",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading((prev) => ({ ...prev, leads: false }));
    }
  };

  const loadOpportunities = async () => {
    setLoading((prev) => ({ ...prev, opportunities: true }));
    try {
      const response = await fetch(
        "/api/integrations/salesforce/opportunities",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "current",
            limit: 50,
            is_closed: false,
          }),
        },
      );

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

  const loadAccounts = async () => {
    setLoading((prev) => ({ ...prev, accounts: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
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

  const loadContacts = async () => {
    setLoading((prev) => ({ ...prev, contacts: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/contacts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
          account_id: selectedAccount,
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

  const loadCases = async () => {
    setLoading((prev) => ({ ...prev, cases: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: "current",
          limit: 50,
          status: "New,Working",
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setCases(data.data?.cases || []);
      }
    } catch (error) {
      console.error("Failed to load cases:", error);
    } finally {
      setLoading((prev) => ({ ...prev, cases: false }));
    }
  };

  const loadUsers = async () => {
    setLoading((prev) => ({ ...prev, users: true }));
    try {
      const response = await fetch("/api/integrations/salesforce/users", {
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

  // Create records
  const createLead = async () => {
    if (!leadForm.LastName) return;

    try {
      const response = await fetch(
        "/api/integrations/salesforce/leads/create",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "current",
            ...leadForm,
          }),
        },
      );

      if (response.ok) {
        toast({
          title: "Success",
          description: "Lead created successfully",
          status: "success",
          duration: 3000,
        });
        onLeadClose();
        setLeadForm({
          FirstName: "",
          LastName: "",
          Email: "",
          Phone: "",
          Company: "",
          Title: "",
          Industry: "",
          AnnualRevenue: "",
          LeadSource: "",
          Status: "Open - Not Contacted",
          Rating: "",
          Description: "",
          Street: "",
          City: "",
          State: "",
          PostalCode: "",
          Country: "",
        });
        loadLeads();
      }
    } catch (error) {
      console.error("Failed to create lead:", error);
      toast({
        title: "Error",
        description: "Failed to create lead",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createOpportunity = async () => {
    if (!opportunityForm.Name || !opportunityForm.AccountId) return;

    try {
      const response = await fetch(
        "/api/integrations/salesforce/opportunities/create",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "current",
            ...opportunityForm,
          }),
        },
      );

      if (response.ok) {
        toast({
          title: "Success",
          description: "Opportunity created successfully",
          status: "success",
          duration: 3000,
        });
        onOpportunityClose();
        setOpportunityForm({
          Name: "",
          AccountId: "",
          Amount: "",
          CloseDate: "",
          StageName: "Prospecting",
          Probability: "10",
          Type: "New Customer",
          LeadSource: "",
          Description: "",
        });
        loadOpportunities();
      }
    } catch (error) {
      console.error("Failed to create opportunity:", error);
      toast({
        title: "Error",
        description: "Failed to create opportunity",
        status: "error",
        duration: 3000,
      });
    }
  };

  const createAccount = async () => {
    if (!accountForm.Name) return;

    try {
      const response = await fetch(
        "/api/integrations/salesforce/accounts/create",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: "current",
            ...accountForm,
          }),
        },
      );

      if (response.ok) {
        toast({
          title: "Success",
          description: "Account created successfully",
          status: "success",
          duration: 3000,
        });
        onAccountClose();
        setAccountForm({
          Name: "",
          Type: "",
          Industry: "",
          AnnualRevenue: "",
          Phone: "",
          Website: "",
          Description: "",
          NumberOfEmployees: "",
          BillingStreet: "",
          BillingCity: "",
          BillingState: "",
          BillingPostalCode: "",
          BillingCountry: "",
        });
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
  const filteredLeads = leads.filter(
    (lead) =>
      (lead.FirstName &&
        lead.FirstName.toLowerCase().includes(searchQuery.toLowerCase())) ||
      lead.LastName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (lead.Email &&
        lead.Email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (lead.Company &&
        lead.Company.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const filteredOpportunities = opportunities.filter(
    (opp) =>
      opp.Name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (opp.AccountName &&
        opp.AccountName.toLowerCase().includes(searchQuery.toLowerCase())) ||
      opp.StageName.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredAccounts = accounts.filter(
    (account) =>
      account.Name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (account.Type &&
        account.Type.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (account.Industry &&
        account.Industry.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const filteredContacts = contacts.filter(
    (contact) =>
      (contact.FirstName &&
        contact.FirstName.toLowerCase().includes(searchQuery.toLowerCase())) ||
      contact.LastName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (contact.Email &&
        contact.Email.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (contact.AccountName &&
        contact.AccountName.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  const filteredCases = cases.filter(
    (case_) =>
      (case_.Subject &&
        case_.Subject.toLowerCase().includes(searchQuery.toLowerCase())) ||
      case_.Status.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (case_.AccountName &&
        case_.AccountName.toLowerCase().includes(searchQuery.toLowerCase())) ||
      case_.CaseNumber.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const filteredUsers = users.filter(
    (user) =>
      user.Name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.Email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (user.Title &&
        user.Title.toLowerCase().includes(searchQuery.toLowerCase())) ||
      (user.Department &&
        user.Department.toLowerCase().includes(searchQuery.toLowerCase())),
  );

  // Stats calculations
  const totalLeads = leads.length;
  const openLeads = leads.filter(
    (l) => l.Status !== "Qualified" && !l.IsConverted,
  ).length;
  const totalOpportunities = opportunities.length;
  const openOpportunities = opportunities.filter((o) => !o.IsClosed).length;
  const totalAmount = opportunities.reduce(
    (sum, o) => sum + (o.Amount || 0),
    0,
  );
  const totalAccounts = accounts.length;
  const totalContacts = contacts.length;
  const openCases = cases.filter((c) => !c.ClosedDate).length;
  const totalUsers = users.length;
  const activeUsers = users.filter((u) => u.IsActive).length;

  useEffect(() => {
    checkConnection();
  }, [checkConnection]);

  useEffect(() => {
    if (connected) {
      loadUserProfile();
      loadLeads();
      loadOpportunities();
      loadAccounts();
      loadContacts();
      loadCases();
      loadUsers();
    }
  }, [
    connected,
    loadUserProfile,
    loadLeads,
    loadOpportunities,
    loadAccounts,
    loadContacts,
    loadCases,
    loadUsers,
  ]);

  useEffect(() => {
    if (selectedAccount) {
      loadContacts();
    }
  }, [selectedAccount, loadContacts]);

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleString();
  };

  const formatCurrency = (amount: number, currency?: string): string => {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
    }).format(amount);
  };

  const getLeadStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case "open - not contacted":
        return "gray";
      case "working - contacted":
        return "yellow";
      case "nurturing":
        return "blue";
      case "qualified":
        return "green";
      case "converted":
        return "purple";
      default:
        return "gray";
    }
  };

  const getOpportunityStageColor = (stage: string): string => {
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
        return "indigo";
      case "closed won":
        return "green";
      case "closed lost":
        return "red";
      default:
        return "gray";
    }
  };

  const getCaseStatusColor = (status: string): string => {
    switch (status?.toLowerCase()) {
      case "new":
        return "blue";
      case "working":
        return "yellow";
      case "escalated":
        return "orange";
      case "closed":
        return "green";
      default:
        return "gray";
    }
  };

  const getCasePriorityColor = (priority: string): string => {
    switch (priority?.toLowerCase()) {
      case "high":
        return "red";
      case "medium":
        return "yellow";
      case "low":
        return "green";
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
            <Icon as={GenericAvatarIcon} w={8} h={8} color="#00A1E0" />
            <VStack align="start" spacing={1}>
              <Heading size="2xl">Salesforce Integration</Heading>
              <Text color="gray.600" fontSize="lg">
                Customer relationship management and sales platform
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
              <Avatar name={userProfile.Name} />
              <VStack align="start" spacing={0}>
                <Text fontWeight="bold">{userProfile.Name}</Text>
                <Text fontSize="sm" color="gray.600">
                  {userProfile.Title || userProfile.Email}
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
                <Icon as={GenericAvatarIcon} w={16} h={16} color="gray.400" />
                <VStack spacing={2}>
                  <Heading size="lg">Connect Salesforce</Heading>
                  <Text color="gray.600" textAlign="center">
                    Connect your Salesforce organization to manage leads,
                    opportunities, and customers
                  </Text>
                </VStack>
                <Button
                  colorScheme="blue"
                  size="lg"
                  leftIcon={<ArrowForwardIcon />}
                  onClick={() =>
                    (window.location.href =
                      "/api/integrations/salesforce/auth/start")
                  }
                >
                  Connect Salesforce Organization
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
                    <StatLabel>Leads</StatLabel>
                    <StatNumber>{totalLeads}</StatNumber>
                    <StatHelpText>{openLeads} open</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Opportunities</StatLabel>
                    <StatNumber>{totalOpportunities}</StatNumber>
                    <StatHelpText>
                      {formatCurrency(totalAmount)} total
                    </StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Accounts</StatLabel>
                    <StatNumber>{totalAccounts}</StatNumber>
                    <StatHelpText>{totalContacts} contacts</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
              <Card>
                <CardBody>
                  <Stat>
                    <StatLabel>Support Cases</StatLabel>
                    <StatNumber>{openCases}</StatNumber>
                    <StatHelpText>Open tickets</StatHelpText>
                  </Stat>
                </CardBody>
              </Card>
            </SimpleGrid>

            {/* Main Content Tabs */}
            <Tabs variant="enclosed">
              <TabList>
                <Tab>Leads</Tab>
                <Tab>Opportunities</Tab>
                <Tab>Accounts</Tab>
                <Tab>Contacts</Tab>
                <Tab>Cases</Tab>
                <Tab>Users</Tab>
              </TabList>

              <TabPanels>
                {/* Leads Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Filter by status"
                        value={selectedStatus}
                        onChange={(e) => setSelectedStatus(e.target.value)}
                        width="200px"
                      >
                        <option value="">All Status</option>
                        <option value="Open - Not Contacted">
                          Open - Not Contacted
                        </option>
                        <option value="Working - Contacted">
                          Working - Contacted
                        </option>
                        <option value="Nurturing">Nurturing</option>
                        <option value="Qualified">Qualified</option>
                      </Select>
                      <InputGroup>
                        <InputLeftElement>
                          <SearchIcon />
                        </InputLeftElement>
                        <Input
                          placeholder="Search opportunities..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </InputGroup>
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onLeadOpen}
                      >
                        Create Lead
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
                                <Th>Status</Th>
                                <Th>Email</Th>
                                <Th>Phone</Th>
                                <Th>Owner</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.leads ? (
                                <Tr>
                                  <Td colSpan={7}>
                                    <Spinner size="xl" />
                                  </Td>
                                </Tr>
                              ) : (
                                filteredLeads.map((lead) => (
                                  <Tr key={lead.id}>
                                    <Td>
                                      <VStack align="start" spacing={0}>
                                        <Text fontWeight="medium">
                                          {lead.FirstName &&
                                            `${lead.FirstName} `}
                                          {lead.LastName}
                                        </Text>
                                        {lead.IsConverted && (
                                          <Badge colorScheme="green" size="sm">
                                            Converted
                                          </Badge>
                                        )}
                                      </VStack>
                                    </Td>
                                    <Td>{lead.Company}</Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getLeadStatusColor(
                                          lead.Status,
                                        )}
                                        size="sm"
                                      >
                                        {lead.Status}
                                      </Tag>
                                    </Td>
                                    <Td>{lead.Email}</Td>
                                    <Td>{lead.Phone}</Td>
                                    <Td>{lead.Owner?.Name}</Td>
                                    <Td>
                                      <HStack>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          leftIcon={<ViewIcon />}
                                        >
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

                {/* Opportunities Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Input
                        placeholder="Search opportunities..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftAddon={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onOpportunityOpen}
                      >
                        Create Opportunity
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Account</Th>
                                <Th>Amount</Th>
                                <Th>Close Date</Th>
                                <Th>Stage</Th>
                                <Th>Probability</Th>
                                <Th>Owner</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.opportunities ? (
                                <Tr>
                                  <Td colSpan={8}>
                                    <Spinner size="xl" />
                                  </Td>
                                </Tr>
                              ) : (
                                filteredOpportunities.map((opp) => (
                                  <Tr key={opp.id}>
                                    <Td>
                                      <HStack>
                                        <Text fontWeight="medium">
                                          {opp.Name}
                                        </Text>
                                        {opp.IsWon && (
                                          <Badge colorScheme="green" size="sm">
                                            Won
                                          </Badge>
                                        )}
                                      </HStack>
                                    </Td>
                                    <Td>{opp.AccountName}</Td>
                                    <Td>
                                      {formatCurrency(
                                        opp.Amount || 0,
                                        opp.CurrencyIsoCode,
                                      )}
                                    </Td>
                                    <Td>{formatDate(opp.CloseDate)}</Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getOpportunityStageColor(
                                          opp.StageName,
                                        )}
                                        size="sm"
                                      >
                                        {opp.StageName}
                                      </Tag>
                                    </Td>
                                    <Td>{opp.Probability}%</Td>
                                    <Td>{opp.Owner?.Name}</Td>
                                    <Td>
                                      <HStack>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          leftIcon={<ViewIcon />}
                                        >
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
                        leftAddon={<SearchIcon />}
                      />
                      <Spacer />
                      <Button
                        colorScheme="blue"
                        leftIcon={<AddIcon />}
                        onClick={onAccountOpen}
                      >
                        Create Account
                      </Button>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Type</Th>
                                <Th>Industry</Th>
                                <Th>Phone</Th>
                                <Th>Website</Th>
                                <Th>Employees</Th>
                                <Th>Annual Revenue</Th>
                                <Th>Owner</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.accounts ? (
                                <Tr>
                                  <Td colSpan={9}>
                                    <Spinner size="xl" />
                                  </Td>
                                </Tr>
                              ) : (
                                filteredAccounts.map((account) => (
                                  <Tr key={account.id}>
                                    <Td>
                                      <Text fontWeight="medium">
                                        {account.Name}
                                      </Text>
                                    </Td>
                                    <Td>{account.Type}</Td>
                                    <Td>{account.Industry}</Td>
                                    <Td>{account.Phone}</Td>
                                    <Td>
                                      {account.Website && (
                                        <Link
                                          href={account.Website}
                                          isExternal
                                          color="blue.500"
                                        >
                                          {account.Website}
                                        </Link>
                                      )}
                                    </Td>
                                    <Td>{account.NumberOfEmployees}</Td>
                                    <Td>
                                      {formatCurrency(
                                        account.AnnualRevenue || 0,
                                      )}
                                    </Td>
                                    <Td>{account.Owner?.Name}</Td>
                                    <Td>
                                      <HStack>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          leftIcon={<ViewIcon />}
                                        >
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

                {/* Contacts Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <Select
                        placeholder="Filter by account"
                        value={selectedAccount}
                        onChange={(e) => setSelectedAccount(e.target.value)}
                        width="200px"
                      >
                        <option value="">All Accounts</option>
                        {accounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.Name}
                          </option>
                        ))}
                      </Select>
                      <Input
                        placeholder="Search contacts..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        leftAddon={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Account</Th>
                                <Th>Title</Th>
                                <Th>Email</Th>
                                <Th>Phone</Th>
                                <Th>Department</Th>
                                <Th>Owner</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.contacts ? (
                                <Tr>
                                  <Td colSpan={8}>
                                    <Spinner size="xl" />
                                  </Td>
                                </Tr>
                              ) : (
                                filteredContacts.map((contact) => (
                                  <Tr key={contact.id}>
                                    <Td>
                                      <Text fontWeight="medium">
                                        {contact.FirstName &&
                                          `${contact.FirstName} `}
                                        {contact.LastName}
                                      </Text>
                                    </Td>
                                    <Td>{contact.AccountName}</Td>
                                    <Td>{contact.Title}</Td>
                                    <Td>{contact.Email}</Td>
                                    <Td>{contact.Phone}</Td>
                                    <Td>{contact.Department}</Td>
                                    <Td>{contact.Owner?.Name}</Td>
                                    <Td>
                                      <HStack>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          leftIcon={<ViewIcon />}
                                        >
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

                {/* Cases Tab */}
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    <HStack spacing={4}>
                      <InputGroup>
                        <InputLeftElement>
                          <SearchIcon />
                        </InputLeftElement>
                        <Input
                          placeholder="Search users..."
                          value={searchQuery}
                          onChange={(e) => setSearchQuery(e.target.value)}
                        />
                      </InputGroup>
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Case Number</Th>
                                <Th>Subject</Th>
                                <Th>Status</Th>
                                <Th>Priority</Th>
                                <Th>Account</Th>
                                <Th>Contact</Th>
                                <Th>Created</Th>
                                <Th>Owner</Th>
                                <Th>Actions</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.cases ? (
                                <Tr>
                                  <Td colSpan={10}>
                                    <Spinner size="xl" />
                                  </Td>
                                </Tr>
                              ) : (
                                filteredCases.map((case_) => (
                                  <Tr key={case_.id}>
                                    <Td>
                                      <Text
                                        fontWeight="medium"
                                        color="blue.600"
                                      >
                                        {case_.CaseNumber}
                                      </Text>
                                    </Td>
                                    <Td>{case_.Subject}</Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getCaseStatusColor(
                                          case_.Status,
                                        )}
                                        size="sm"
                                      >
                                        {case_.Status}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      <Tag
                                        colorScheme={getCasePriorityColor(
                                          case_.Priority,
                                        )}
                                        size="sm"
                                      >
                                        {case_.Priority}
                                      </Tag>
                                    </Td>
                                    <Td>{case_.AccountName}</Td>
                                    <Td>{case_.ContactName}</Td>
                                    <Td>{formatDate(case_.CreatedDate)}</Td>
                                    <Td>{case_.Owner?.Name}</Td>
                                    <Td>
                                      <HStack>
                                        <Button
                                          size="sm"
                                          variant="outline"
                                          leftIcon={<ViewIcon />}
                                        >
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
                        leftAddon={<SearchIcon />}
                      />
                    </HStack>

                    <Card>
                      <CardBody>
                        <TableContainer>
                          <Table variant="simple">
                            <Thead>
                              <Tr>
                                <Th>Name</Th>
                                <Th>Username</Th>
                                <Th>Email</Th>
                                <Th>Title</Th>
                                <Th>Department</Th>
                                <Th>Profile</Th>
                                <Th>Status</Th>
                                <Th>Last Login</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {loading.users ? (
                                <Tr>
                                  <Td colSpan={8}>
                                    <Spinner size="xl" />
                                  </Td>
                                </Tr>
                              ) : (
                                filteredUsers.map((user) => (
                                  <Tr key={user.id}>
                                    <Td>
                                      <HStack>
                                        <Avatar name={user.Name} size="sm" />
                                        <Text fontWeight="medium">
                                          {user.Name}
                                        </Text>
                                      </HStack>
                                    </Td>
                                    <Td>{user.Username}</Td>
                                    <Td>{user.Email}</Td>
                                    <Td>{user.Title}</Td>
                                    <Td>{user.Department}</Td>
                                    <Td>{user.Profile?.Name}</Td>
                                    <Td>
                                      <Tag
                                        colorScheme={
                                          user.IsActive ? "green" : "red"
                                        }
                                        size="sm"
                                      >
                                        {user.IsActive ? "Active" : "Inactive"}
                                      </Tag>
                                    </Td>
                                    <Td>
                                      {user.LastLoginDate
                                        ? formatDate(user.LastLoginDate)
                                        : "Never"}
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

            {/* Create Lead Modal */}
            <Modal isOpen={isLeadOpen} onClose={onLeadClose} size="xl">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Lead</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>First Name</FormLabel>
                        <Input
                          placeholder="First name"
                          value={leadForm.FirstName}
                          onChange={(e) =>
                            setLeadForm({
                              ...leadForm,
                              FirstName: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                      <FormControl isRequired>
                        <FormLabel>Last Name</FormLabel>
                        <Input
                          placeholder="Last name"
                          value={leadForm.LastName}
                          onChange={(e) =>
                            setLeadForm({
                              ...leadForm,
                              LastName: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Company</FormLabel>
                        <Input
                          placeholder="Company name"
                          value={leadForm.Company}
                          onChange={(e) =>
                            setLeadForm({
                              ...leadForm,
                              Company: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                      <FormControl>
                        <FormLabel>Title</FormLabel>
                        <Input
                          placeholder="Job title"
                          value={leadForm.Title}
                          onChange={(e) =>
                            setLeadForm({ ...leadForm, Title: e.target.value })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Email</FormLabel>
                        <Input
                          type="email"
                          placeholder="email@example.com"
                          value={leadForm.Email}
                          onChange={(e) =>
                            setLeadForm({ ...leadForm, Email: e.target.value })
                          }
                        />
                      </FormControl>
                      <FormControl>
                        <FormLabel>Phone</FormLabel>
                        <Input
                          placeholder="Phone number"
                          value={leadForm.Phone}
                          onChange={(e) =>
                            setLeadForm({ ...leadForm, Phone: e.target.value })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Industry</FormLabel>
                        <Select
                          value={leadForm.Industry}
                          onChange={(e) =>
                            setLeadForm({
                              ...leadForm,
                              Industry: e.target.value,
                            })
                          }
                        >
                          <option value="">Select Industry</option>
                          <option value="Technology">Technology</option>
                          <option value="Financial Services">
                            Financial Services
                          </option>
                          <option value="Healthcare">Healthcare</option>
                          <option value="Manufacturing">Manufacturing</option>
                          <option value="Retail">Retail</option>
                        </Select>
                      </FormControl>
                      <FormControl>
                        <FormLabel>Annual Revenue</FormLabel>
                        <Input
                          placeholder="1000000"
                          value={leadForm.AnnualRevenue}
                          onChange={(e) =>
                            setLeadForm({
                              ...leadForm,
                              AnnualRevenue: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Lead Source</FormLabel>
                        <Select
                          value={leadForm.LeadSource}
                          onChange={(e) =>
                            setLeadForm({
                              ...leadForm,
                              LeadSource: e.target.value,
                            })
                          }
                        >
                          <option value="">Select Source</option>
                          <option value="Web">Web</option>
                          <option value="Phone">Phone</option>
                          <option value="Partner">Partner</option>
                          <option value="Public Relations">
                            Public Relations
                          </option>
                          <option value="Seminar">Seminar</option>
                          <option value="Trade Show">Trade Show</option>
                        </Select>
                      </FormControl>
                      <FormControl>
                        <FormLabel>Rating</FormLabel>
                        <Select
                          value={leadForm.Rating}
                          onChange={(e) =>
                            setLeadForm({ ...leadForm, Rating: e.target.value })
                          }
                        >
                          <option value="">Select Rating</option>
                          <option value="Hot">Hot</option>
                          <option value="Warm">Warm</option>
                          <option value="Cold">Cold</option>
                        </Select>
                      </FormControl>
                    </HStack>

                    <FormControl>
                      <FormLabel>Address</FormLabel>
                      <VStack spacing={2}>
                        <Input
                          placeholder="Street"
                          value={leadForm.Street}
                          onChange={(e) =>
                            setLeadForm({ ...leadForm, Street: e.target.value })
                          }
                        />
                        <HStack spacing={2}>
                          <Input
                            placeholder="City"
                            value={leadForm.City}
                            onChange={(e) =>
                              setLeadForm({ ...leadForm, City: e.target.value })
                            }
                          />
                          <Input
                            placeholder="State"
                            value={leadForm.State}
                            onChange={(e) =>
                              setLeadForm({
                                ...leadForm,
                                State: e.target.value,
                              })
                            }
                          />
                          <Input
                            placeholder="Postal Code"
                            value={leadForm.PostalCode}
                            onChange={(e) =>
                              setLeadForm({
                                ...leadForm,
                                PostalCode: e.target.value,
                              })
                            }
                          />
                        </HStack>
                        <Input
                          placeholder="Country"
                          value={leadForm.Country}
                          onChange={(e) =>
                            setLeadForm({
                              ...leadForm,
                              Country: e.target.value,
                            })
                          }
                        />
                      </VStack>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Additional information..."
                        value={leadForm.Description}
                        onChange={(e) =>
                          setLeadForm({
                            ...leadForm,
                            Description: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onLeadClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createLead}
                    disabled={!leadForm.LastName}
                  >
                    Create Lead
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Opportunity Modal */}
            <Modal
              isOpen={isOpportunityOpen}
              onClose={onOpportunityClose}
              size="xl"
            >
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Opportunity</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Opportunity Name</FormLabel>
                      <Input
                        placeholder="Opportunity name"
                        value={opportunityForm.Name}
                        onChange={(e) =>
                          setOpportunityForm({
                            ...opportunityForm,
                            Name: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <FormControl isRequired>
                      <FormLabel>Account</FormLabel>
                      <Select
                        value={opportunityForm.AccountId}
                        onChange={(e) =>
                          setOpportunityForm({
                            ...opportunityForm,
                            AccountId: e.target.value,
                          })
                        }
                      >
                        <option value="">Select Account</option>
                        {accounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.Name}
                          </option>
                        ))}
                      </Select>
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Amount</FormLabel>
                        <Input
                          placeholder="100000"
                          value={opportunityForm.Amount}
                          onChange={(e) =>
                            setOpportunityForm({
                              ...opportunityForm,
                              Amount: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                      <FormControl>
                        <FormLabel>Close Date</FormLabel>
                        <Input
                          type="date"
                          value={opportunityForm.CloseDate}
                          onChange={(e) =>
                            setOpportunityForm({
                              ...opportunityForm,
                              CloseDate: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Stage</FormLabel>
                        <Select
                          value={opportunityForm.StageName}
                          onChange={(e) =>
                            setOpportunityForm({
                              ...opportunityForm,
                              StageName: e.target.value,
                            })
                          }
                        >
                          <option value="Prospecting">Prospecting</option>
                          <option value="Qualification">Qualification</option>
                          <option value="Needs Analysis">Needs Analysis</option>
                          <option value="Value Proposition">
                            Value Proposition
                          </option>
                          <option value="Id. Decision Makers">
                            Id. Decision Makers
                          </option>
                          <option value="Perception Analysis">
                            Perception Analysis
                          </option>
                          <option value="Proposal/Price Quote">
                            Proposal/Price Quote
                          </option>
                          <option value="Negotiation/Review">
                            Negotiation/Review
                          </option>
                          <option value="Closed Won">Closed Won</option>
                          <option value="Closed Lost">Closed Lost</option>
                        </Select>
                      </FormControl>
                      <FormControl>
                        <FormLabel>Probability (%)</FormLabel>
                        <Input
                          type="number"
                          min="0"
                          max="100"
                          value={opportunityForm.Probability}
                          onChange={(e) =>
                            setOpportunityForm({
                              ...opportunityForm,
                              Probability: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Type</FormLabel>
                        <Select
                          value={opportunityForm.Type}
                          onChange={(e) =>
                            setOpportunityForm({
                              ...opportunityForm,
                              Type: e.target.value,
                            })
                          }
                        >
                          <option value="New Customer">New Customer</option>
                          <option value="Existing Business">
                            Existing Business
                          </option>
                          <option value="Partner">Partner</option>
                        </Select>
                      </FormControl>
                      <FormControl>
                        <FormLabel>Lead Source</FormLabel>
                        <Select
                          value={opportunityForm.LeadSource}
                          onChange={(e) =>
                            setOpportunityForm({
                              ...opportunityForm,
                              LeadSource: e.target.value,
                            })
                          }
                        >
                          <option value="">Select Source</option>
                          <option value="Web">Web</option>
                          <option value="Phone">Phone</option>
                          <option value="Partner">Partner</option>
                          <option value="Public Relations">
                            Public Relations
                          </option>
                          <option value="Seminar">Seminar</option>
                          <option value="Trade Show">Trade Show</option>
                        </Select>
                      </FormControl>
                    </HStack>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Opportunity description..."
                        value={opportunityForm.Description}
                        onChange={(e) =>
                          setOpportunityForm({
                            ...opportunityForm,
                            Description: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onOpportunityClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createOpportunity}
                    disabled={
                      !opportunityForm.Name || !opportunityForm.AccountId
                    }
                  >
                    Create Opportunity
                  </Button>
                </ModalFooter>
              </ModalContent>
            </Modal>

            {/* Create Account Modal */}
            <Modal isOpen={isAccountOpen} onClose={onAccountClose} size="xl">
              <ModalOverlay />
              <ModalContent>
                <ModalHeader>Create Account</ModalHeader>
                <ModalCloseButton />
                <ModalBody>
                  <VStack spacing={4}>
                    <FormControl isRequired>
                      <FormLabel>Account Name</FormLabel>
                      <Input
                        placeholder="Account name"
                        value={accountForm.Name}
                        onChange={(e) =>
                          setAccountForm({
                            ...accountForm,
                            Name: e.target.value,
                          })
                        }
                      />
                    </FormControl>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Type</FormLabel>
                        <Select
                          value={accountForm.Type}
                          onChange={(e) =>
                            setAccountForm({
                              ...accountForm,
                              Type: e.target.value,
                            })
                          }
                        >
                          <option value="">Select Type</option>
                          <option value="Partner">Partner</option>
                          <option value="Customer">Customer</option>
                          <option value="Competitor">Competitor</option>
                        </Select>
                      </FormControl>
                      <FormControl>
                        <FormLabel>Industry</FormLabel>
                        <Select
                          value={accountForm.Industry}
                          onChange={(e) =>
                            setAccountForm({
                              ...accountForm,
                              Industry: e.target.value,
                            })
                          }
                        >
                          <option value="">Select Industry</option>
                          <option value="Technology">Technology</option>
                          <option value="Financial Services">
                            Financial Services
                          </option>
                          <option value="Healthcare">Healthcare</option>
                          <option value="Manufacturing">Manufacturing</option>
                          <option value="Retail">Retail</option>
                        </Select>
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Phone</FormLabel>
                        <Input
                          placeholder="Phone number"
                          value={accountForm.Phone}
                          onChange={(e) =>
                            setAccountForm({
                              ...accountForm,
                              Phone: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                      <FormControl>
                        <FormLabel>Website</FormLabel>
                        <Input
                          placeholder="https://www.example.com"
                          value={accountForm.Website}
                          onChange={(e) =>
                            setAccountForm({
                              ...accountForm,
                              Website: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <HStack spacing={4} width="full">
                      <FormControl>
                        <FormLabel>Annual Revenue</FormLabel>
                        <Input
                          placeholder="1000000"
                          value={accountForm.AnnualRevenue}
                          onChange={(e) =>
                            setAccountForm({
                              ...accountForm,
                              AnnualRevenue: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                      <FormControl>
                        <FormLabel>Number of Employees</FormLabel>
                        <Input
                          placeholder="100"
                          value={accountForm.NumberOfEmployees}
                          onChange={(e) =>
                            setAccountForm({
                              ...accountForm,
                              NumberOfEmployees: e.target.value,
                            })
                          }
                        />
                      </FormControl>
                    </HStack>

                    <FormControl>
                      <FormLabel>Billing Address</FormLabel>
                      <VStack spacing={2}>
                        <Input
                          placeholder="Street"
                          value={accountForm.BillingStreet}
                          onChange={(e) =>
                            setAccountForm({
                              ...accountForm,
                              BillingStreet: e.target.value,
                            })
                          }
                        />
                        <HStack spacing={2}>
                          <Input
                            placeholder="City"
                            value={accountForm.BillingCity}
                            onChange={(e) =>
                              setAccountForm({
                                ...accountForm,
                                BillingCity: e.target.value,
                              })
                            }
                          />
                          <Input
                            placeholder="State"
                            value={accountForm.BillingState}
                            onChange={(e) =>
                              setAccountForm({
                                ...accountForm,
                                BillingState: e.target.value,
                              })
                            }
                          />
                          <Input
                            placeholder="Postal Code"
                            value={accountForm.BillingPostalCode}
                            onChange={(e) =>
                              setAccountForm({
                                ...accountForm,
                                BillingPostalCode: e.target.value,
                              })
                            }
                          />
                        </HStack>
                        <Input
                          placeholder="Country"
                          value={accountForm.BillingCountry}
                          onChange={(e) =>
                            setAccountForm({
                              ...accountForm,
                              BillingCountry: e.target.value,
                            })
                          }
                        />
                      </VStack>
                    </FormControl>

                    <FormControl>
                      <FormLabel>Description</FormLabel>
                      <Textarea
                        placeholder="Account description..."
                        value={accountForm.Description}
                        onChange={(e) =>
                          setAccountForm({
                            ...accountForm,
                            Description: e.target.value,
                          })
                        }
                        rows={3}
                      />
                    </FormControl>
                  </VStack>
                </ModalBody>
                <ModalFooter>
                  <Button variant="outline" mr={3} onClick={onAccountClose}>
                    Cancel
                  </Button>
                  <Button
                    colorScheme="blue"
                    onClick={createAccount}
                    disabled={!accountForm.Name}
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
