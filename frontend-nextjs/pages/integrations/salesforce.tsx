/**
 * Salesforce Integration Page
 * Complete Salesforce CRM and sales platform integration
 */

import React, { useState, useEffect } from "react";
import {
  CheckCircle,
  AlertTriangle,
  ArrowRight,
  Plus,
  Search,
  Settings,
  RefreshCw,
  Clock,
  Star,
  Eye,
  Edit,
  Trash2,
  MessageSquare,
  Mail,
  Phone,
  Calendar,
  User,
  Briefcase,
  Building,
  Globe,
  MapPin,
  DollarSign,
  Target,
  Users,
  FileText,
  LayoutDashboard,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";

// Helper hook for modal state
function useDisclosure() {
  const [isOpen, setIsOpen] = useState(false);
  const onOpen = () => setIsOpen(true);
  const onClose = () => setIsOpen(false);
  return { isOpen, onOpen, onClose };
}

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
  const [selectedType, setSelectedType] = useState("all");

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
          variant: "success",
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
        variant: "error",
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
          variant: "success",
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
        variant: "error",
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
          variant: "success",
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
        variant: "error",
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
    <div className="min-h-screen bg-background p-6">
      <div className="flex flex-col gap-8 max-w-[1400px] mx-auto">
        {/* Header */}
        <div className="flex flex-col gap-4 items-start">
          <div className="flex items-center gap-4">
            <div className="text-[#00A1E0]">
              <LayoutDashboard className="w-8 h-8" />
            </div>
            <div className="flex flex-col gap-1">
              <h1 className="text-3xl font-bold tracking-tight">Salesforce Integration</h1>
              <p className="text-lg text-muted-foreground">
                Customer relationship management and sales platform
              </p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <Badge
              variant={healthStatus === "healthy" ? "success" : "destructive"}
              className="flex items-center gap-1"
            >
              {healthStatus === "healthy" ? (
                <CheckCircle className="w-3 h-3 mr-1" />
              ) : (
                <AlertTriangle className="w-3 h-3 mr-1" />
              )}
              {connected ? "Connected" : "Disconnected"}
            </Badge>
            <Button
              variant="outline"
              size="sm"
              onClick={checkConnection}
              className="gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh Status
            </Button>
          </div>

          {userProfile && (
            <div className="flex items-center gap-4">
              <Avatar>
                <AvatarFallback>{userProfile.Name.charAt(0)}</AvatarFallback>
              </Avatar>
              <div className="flex flex-col">
                <span className="font-bold">{userProfile.Name}</span>
                <span className="text-sm text-muted-foreground">
                  {userProfile.Title || userProfile.Email}
                </span>
              </div>
            </div>
          )}
        </div>

        {!connected ? (
          // Connection Required State
          <Card>
            <CardContent className="pt-6">
              <div className="flex flex-col gap-6 py-8 items-center text-center">
                <LayoutDashboard className="w-16 h-16 text-muted-foreground" />
                <div className="flex flex-col gap-2">
                  <h2 className="text-2xl font-bold">Connect Salesforce</h2>
                  <p className="text-muted-foreground">
                    Connect your Salesforce organization to manage leads,
                    opportunities, and customers
                  </p>
                </div>
                <Button
                  size="lg"
                  onClick={() =>
                  (window.location.href =
                    "/api/integrations/salesforce/auth/start")
                  }
                  className="gap-2"
                >
                  <ArrowRight className="w-4 h-4" />
                  Connect Salesforce Organization
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          // Connected State
          <>
            {/* Services Overview */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
              <Card>
                <CardContent className="pt-6">
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium text-muted-foreground">Leads</span>
                    <span className="text-2xl font-bold">{totalLeads}</span>
                    <span className="text-xs text-muted-foreground">{openLeads} open</span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium text-muted-foreground">Opportunities</span>
                    <span className="text-2xl font-bold">{totalOpportunities}</span>
                    <span className="text-xs text-muted-foreground">
                      {formatCurrency(totalAmount)} total
                    </span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium text-muted-foreground">Accounts</span>
                    <span className="text-2xl font-bold">{totalAccounts}</span>
                    <span className="text-xs text-muted-foreground">{totalContacts} contacts</span>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-medium text-muted-foreground">Support Cases</span>
                    <span className="text-2xl font-bold">{openCases}</span>
                    <span className="text-xs text-muted-foreground">Open tickets</span>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Main Content Tabs */}
            <Tabs defaultValue="leads" className="w-full">
              <TabsList>
                <TabsTrigger value="leads">Leads</TabsTrigger>
                <TabsTrigger value="opportunities">Opportunities</TabsTrigger>
                <TabsTrigger value="accounts">Accounts</TabsTrigger>
                <TabsTrigger value="contacts">Contacts</TabsTrigger>
                <TabsTrigger value="cases">Cases</TabsTrigger>
                <TabsTrigger value="users">Users</TabsTrigger>
              </TabsList>
              {/* Leads Tab */}
              <TabsContent value="leads" className="space-y-6">
                <div className="flex items-center gap-4">
                  <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                    <SelectTrigger className="w-[200px]">
                      <SelectValue placeholder="Filter by status" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Status</SelectItem>
                      <SelectItem value="Open - Not Contacted">Open - Not Contacted</SelectItem>
                      <SelectItem value="Working - Contacted">Working - Contacted</SelectItem>
                      <SelectItem value="Nurturing">Nurturing</SelectItem>
                      <SelectItem value="Qualified">Qualified</SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search leads..."
                      value={searchQuery}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
                      className="pl-8 w-[300px]"
                    />
                  </div>
                  <div className="flex-1" />
                  <Button onClick={onLeadOpen} className="gap-2">
                    <Plus className="w-4 h-4" />
                    Create Lead
                  </Button>
                </div>

                <Card>
                  <CardContent className="p-0">
                    <div className="rounded-md border">
                      <table className="w-full text-sm text-left">
                        <thead className="bg-muted/50 text-muted-foreground">
                          <tr>
                            <th className="h-12 px-4 align-middle font-medium">Name</th>
                            <th className="h-12 px-4 align-middle font-medium">Company</th>
                            <th className="h-12 px-4 align-middle font-medium">Status</th>
                            <th className="h-12 px-4 align-middle font-medium">Email</th>
                            <th className="h-12 px-4 align-middle font-medium">Phone</th>
                            <th className="h-12 px-4 align-middle font-medium">Owner</th>
                            <th className="h-12 px-4 align-middle font-medium">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {loading.leads ? (
                            <tr>
                              <td colSpan={7} className="p-4 text-center">
                                <div className="flex justify-center">
                                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                                </div>
                              </td>
                            </tr>
                          ) : (
                            filteredLeads.map((lead) => (
                              <tr key={lead.id} className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                                <td className="p-4 align-middle">
                                  <div className="flex flex-col">
                                    <span className="font-medium">
                                      {lead.FirstName && `${lead.FirstName} `}
                                      {lead.LastName}
                                    </span>
                                    {lead.IsConverted && (
                                      <Badge variant="secondary" className="w-fit mt-1">
                                        Converted
                                      </Badge>
                                    )}
                                  </div>
                                </td>
                                <td className="p-4 align-middle">{lead.Company}</td>
                                <td className="p-4 align-middle">
                                  <Badge variant="outline">
                                    {lead.Status}
                                  </Badge>
                                </td>
                                <td className="p-4 align-middle">{lead.Email}</td>
                                <td className="p-4 align-middle">{lead.Phone}</td>
                                <td className="p-4 align-middle">{lead.Owner?.Name}</td>
                                <td className="p-4 align-middle">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="gap-2"
                                  >
                                    <Eye className="w-4 h-4" />
                                    Details
                                  </Button>
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>

              {/* Accounts Tab */}
              <TabsContent value="accounts" className="space-y-6">
                <div className="flex items-center gap-4">
                  <Select value={selectedType} onValueChange={setSelectedType}>
                    <SelectTrigger className="w-[200px]">
                      <SelectValue placeholder="Filter by type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All Types</SelectItem>
                      <SelectItem value="Customer">Customer</SelectItem>
                      <SelectItem value="Partner">Partner</SelectItem>
                      <SelectItem value="Prospect">Prospect</SelectItem>
                      <SelectItem value="Competitor">Competitor</SelectItem>
                    </SelectContent>
                  </Select>
                  <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search accounts..."
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-8 w-[300px]"
                    />
                  </div>
                  <div className="flex-1" />
                  <Button onClick={onAccountOpen} className="gap-2">
                    <Plus className="w-4 h-4" />
                    Create Account
                  </Button>
                </div>

                <Card>
                  <CardContent className="p-0">
                    <div className="rounded-md border">
                      <table className="w-full text-sm text-left">
                        <thead className="bg-muted/50 text-muted-foreground">
                          <tr>
                            <th className="h-12 px-4 align-middle font-medium">Name</th>
                            <th className="h-12 px-4 align-middle font-medium">Type</th>
                            <th className="h-12 px-4 align-middle font-medium">Industry</th>
                            <th className="h-12 px-4 align-middle font-medium">Phone</th>
                            <th className="h-12 px-4 align-middle font-medium">Website</th>
                            <th className="h-12 px-4 align-middle font-medium">Owner</th>
                            <th className="h-12 px-4 align-middle font-medium">Actions</th>
                          </tr>
                        </thead>
                        <tbody>
                          {loading.accounts ? (
                            <tr>
                              <td colSpan={7} className="p-4 text-center">
                                <div className="flex justify-center">
                                  <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
                                </div>
                              </td>
                            </tr>
                          ) : (
                            filteredAccounts.map((account) => (
                              <tr key={account.id} className="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted">
                                <td className="p-4 align-middle font-medium">{account.Name}</td>
                                <td className="p-4 align-middle">
                                  <Badge variant="outline">
                                    {account.Type}
                                  </Badge>
                                </td>
                                <td className="p-4 align-middle">{account.Industry}</td>
                                <td className="p-4 align-middle">{account.Phone}</td>
                                <td className="p-4 align-middle">
                                  {account.Website && (
                                    <a href={account.Website} target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline flex items-center gap-1">
                                      {account.Website}
                                    </a>
                                  )}
                                </td>
                                <td className="p-4 align-middle">{account.Owner?.Name}</td>
                                <td className="p-4 align-middle">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="gap-2"
                                  >
                                    <Eye className="w-4 h-4" />
                                    Details
                                  </Button>
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            {/* Create Lead Modal */}
            <Dialog open={isLeadOpen} onOpenChange={(open: boolean) => !open && onLeadClose()}>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create Lead</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="firstName">First Name</Label>
                      <Input
                        id="firstName"
                        placeholder="First name"
                        value={leadForm.FirstName}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({
                            ...leadForm,
                            FirstName: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="lastName" className="required">Last Name *</Label>
                      <Input
                        id="lastName"
                        placeholder="Last name"
                        value={leadForm.LastName}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({
                            ...leadForm,
                            LastName: e.target.value,
                          })
                        }
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="company">Company</Label>
                      <Input
                        id="company"
                        placeholder="Company name"
                        value={leadForm.Company}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({
                            ...leadForm,
                            Company: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="title">Title</Label>
                      <Input
                        id="title"
                        placeholder="Job title"
                        value={leadForm.Title}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({ ...leadForm, Title: e.target.value })
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="email">Email</Label>
                      <Input
                        id="email"
                        type="email"
                        placeholder="email@example.com"
                        value={leadForm.Email}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({ ...leadForm, Email: e.target.value })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="phone">Phone</Label>
                      <Input
                        id="phone"
                        placeholder="Phone number"
                        value={leadForm.Phone}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({ ...leadForm, Phone: e.target.value })
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="industry">Industry</Label>
                      <select
                        id="industry"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={leadForm.Industry}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
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
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="revenue">Annual Revenue</Label>
                      <Input
                        id="revenue"
                        placeholder="1000000"
                        value={leadForm.AnnualRevenue}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({
                            ...leadForm,
                            AnnualRevenue: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="leadSource">Lead Source</Label>
                      <select
                        id="leadSource"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={leadForm.LeadSource}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
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
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="rating">Rating</Label>
                      <select
                        id="rating"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={leadForm.Rating}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                          setLeadForm({ ...leadForm, Rating: e.target.value })
                        }
                      >
                        <option value="">Select Rating</option>
                        <option value="Hot">Hot</option>
                        <option value="Warm">Warm</option>
                        <option value="Cold">Cold</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Address</Label>
                    <div className="space-y-2">
                      <Input
                        placeholder="Street"
                        value={leadForm.Street}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({ ...leadForm, Street: e.target.value })
                        }
                      />
                      <div className="grid grid-cols-3 gap-2">
                        <Input
                          placeholder="City"
                          value={leadForm.City}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            setLeadForm({ ...leadForm, City: e.target.value })
                          }
                        />
                        <Input
                          placeholder="State"
                          value={leadForm.State}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            setLeadForm({
                              ...leadForm,
                              State: e.target.value,
                            })
                          }
                        />
                        <Input
                          placeholder="Postal Code"
                          value={leadForm.PostalCode}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            setLeadForm({
                              ...leadForm,
                              PostalCode: e.target.value,
                            })
                          }
                        />
                      </div>
                      <Input
                        placeholder="Country"
                        value={leadForm.Country}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setLeadForm({
                            ...leadForm,
                            Country: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      placeholder="Additional information..."
                      value={leadForm.Description}
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                        setLeadForm({
                          ...leadForm,
                          Description: e.target.value,
                        })
                      }
                      rows={3}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={onLeadClose}>
                    Cancel
                  </Button>
                  <Button
                    onClick={createLead}
                    disabled={!leadForm.LastName}
                  >
                    Create Lead
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Create Opportunity Modal */}
            <Dialog open={isOpportunityOpen} onOpenChange={(open: boolean) => !open && onOpportunityClose()}>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create Opportunity</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="oppName" className="required">Opportunity Name *</Label>
                    <Input
                      id="oppName"
                      placeholder="Opportunity name"
                      value={opportunityForm.Name}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                        setOpportunityForm({
                          ...opportunityForm,
                          Name: e.target.value,
                        })
                      }
                      required
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="oppAccount" className="required">Account *</Label>
                    <select
                      id="oppAccount"
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      value={opportunityForm.AccountId}
                      onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                        setOpportunityForm({
                          ...opportunityForm,
                          AccountId: e.target.value,
                        })
                      }
                      required
                    >
                      <option value="">Select Account</option>
                      {accounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.Name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="oppAmount">Amount</Label>
                      <Input
                        id="oppAmount"
                        placeholder="100000"
                        value={opportunityForm.Amount}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setOpportunityForm({
                            ...opportunityForm,
                            Amount: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="oppCloseDate">Close Date</Label>
                      <Input
                        id="oppCloseDate"
                        type="date"
                        value={opportunityForm.CloseDate}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setOpportunityForm({
                            ...opportunityForm,
                            CloseDate: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="oppStage">Stage</Label>
                      <select
                        id="oppStage"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={opportunityForm.StageName}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                          setOpportunityForm({
                            ...opportunityForm,
                            StageName: e.target.value,
                          })
                        }
                      >
                        <option value="Prospecting">Prospecting</option>
                        <option value="Qualification">Qualification</option>
                        <option value="Needs Analysis">Needs Analysis</option>
                        <option value="Value Proposition">Value Proposition</option>
                        <option value="Id. Decision Makers">Id. Decision Makers</option>
                        <option value="Perception Analysis">Perception Analysis</option>
                        <option value="Proposal/Price Quote">Proposal/Price Quote</option>
                        <option value="Negotiation/Review">Negotiation/Review</option>
                        <option value="Closed Won">Closed Won</option>
                        <option value="Closed Lost">Closed Lost</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="oppProb">Probability (%)</Label>
                      <Input
                        id="oppProb"
                        type="number"
                        min="0"
                        max="100"
                        value={opportunityForm.Probability}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setOpportunityForm({
                            ...opportunityForm,
                            Probability: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="oppType">Type</Label>
                      <select
                        id="oppType"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={opportunityForm.Type}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                          setOpportunityForm({
                            ...opportunityForm,
                            Type: e.target.value,
                          })
                        }
                      >
                        <option value="New Customer">New Customer</option>
                        <option value="Existing Business">Existing Business</option>
                        <option value="Partner">Partner</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="oppLeadSource">Lead Source</Label>
                      <select
                        id="oppLeadSource"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={opportunityForm.LeadSource}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
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
                        <option value="Public Relations">Public Relations</option>
                        <option value="Seminar">Seminar</option>
                        <option value="Trade Show">Trade Show</option>
                      </select>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="oppDesc">Description</Label>
                    <Textarea
                      id="oppDesc"
                      placeholder="Opportunity description..."
                      value={opportunityForm.Description}
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                        setOpportunityForm({
                          ...opportunityForm,
                          Description: e.target.value,
                        })
                      }
                      rows={3}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={onOpportunityClose}>
                    Cancel
                  </Button>
                  <Button
                    onClick={createOpportunity}
                    disabled={!opportunityForm.Name || !opportunityForm.AccountId}
                  >
                    Create Opportunity
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* Create Account Modal */}
            <Dialog open={isAccountOpen} onOpenChange={(open: boolean) => !open && onAccountClose()}>
              <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle>Create Account</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="accName" className="required">Account Name *</Label>
                    <Input
                      id="accName"
                      placeholder="Account name"
                      value={accountForm.Name}
                      onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                        setAccountForm({
                          ...accountForm,
                          Name: e.target.value,
                        })
                      }
                      required
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="accType">Type</Label>
                      <select
                        id="accType"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={accountForm.Type}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
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
                      </select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="accIndustry">Industry</Label>
                      <select
                        id="accIndustry"
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={accountForm.Industry}
                        onChange={(e: React.ChangeEvent<HTMLSelectElement>) =>
                          setAccountForm({
                            ...accountForm,
                            Industry: e.target.value,
                          })
                        }
                      >
                        <option value="">Select Industry</option>
                        <option value="Technology">Technology</option>
                        <option value="Financial Services">Financial Services</option>
                        <option value="Healthcare">Healthcare</option>
                        <option value="Manufacturing">Manufacturing</option>
                        <option value="Retail">Retail</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="accPhone">Phone</Label>
                      <Input
                        id="accPhone"
                        placeholder="Phone number"
                        value={accountForm.Phone}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setAccountForm({
                            ...accountForm,
                            Phone: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="accWebsite">Website</Label>
                      <Input
                        id="accWebsite"
                        placeholder="https://www.example.com"
                        value={accountForm.Website}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setAccountForm({
                            ...accountForm,
                            Website: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="accRevenue">Annual Revenue</Label>
                      <Input
                        id="accRevenue"
                        placeholder="1000000"
                        value={accountForm.AnnualRevenue}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setAccountForm({
                            ...accountForm,
                            AnnualRevenue: e.target.value,
                          })
                        }
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="accEmployees">Number of Employees</Label>
                      <Input
                        id="accEmployees"
                        placeholder="100"
                        value={accountForm.NumberOfEmployees}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setAccountForm({
                            ...accountForm,
                            NumberOfEmployees: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>Billing Address</Label>
                    <div className="space-y-2">
                      <Input
                        placeholder="Street"
                        value={accountForm.BillingStreet}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setAccountForm({
                            ...accountForm,
                            BillingStreet: e.target.value,
                          })
                        }
                      />
                      <div className="grid grid-cols-3 gap-2">
                        <Input
                          placeholder="City"
                          value={accountForm.BillingCity}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            setAccountForm({
                              ...accountForm,
                              BillingCity: e.target.value,
                            })
                          }
                        />
                        <Input
                          placeholder="State"
                          value={accountForm.BillingState}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            setAccountForm({
                              ...accountForm,
                              BillingState: e.target.value,
                            })
                          }
                        />
                        <Input
                          placeholder="Postal Code"
                          value={accountForm.BillingPostalCode}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                            setAccountForm({
                              ...accountForm,
                              BillingPostalCode: e.target.value,
                            })
                          }
                        />
                      </div>
                      <Input
                        placeholder="Country"
                        value={accountForm.BillingCountry}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                          setAccountForm({
                            ...accountForm,
                            BillingCountry: e.target.value,
                          })
                        }
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="accDesc">Description</Label>
                    <Textarea
                      id="accDesc"
                      placeholder="Account description..."
                      value={accountForm.Description}
                      onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                        setAccountForm({
                          ...accountForm,
                          Description: e.target.value,
                        })
                      }
                      rows={3}
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={onAccountClose}>
                    Cancel
                  </Button>
                  <Button
                    onClick={createAccount}
                    disabled={!accountForm.Name}
                  >
                    Create Account
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </>
        )}
      </div>
    </div>
  );
};

export default SalesforceIntegration;
