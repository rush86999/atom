/**
 * QuickBooks Integration Component
 * Complete QuickBooks financial management and accounting integration
 */

import React, { useState, useEffect } from "react";
import {
    Settings,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    RefreshCw,
    Clock,
    Star,
    Eye,
    Edit,
    Trash,
    MessageSquare,
    Mail,
    Calendar,
    DollarSign,
    FileText,
    Download,
    ExternalLink,
    Loader2,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

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

    const [isCustomerOpen, setIsCustomerOpen] = useState(false);
    const [isInvoiceOpen, setIsInvoiceOpen] = useState(false);
    const [isBillOpen, setIsBillOpen] = useState(false);

    const { toast } = useToast();

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
                variant: "destructive",
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
                });
                setIsCustomerOpen(false);
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
                variant: "destructive",
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
                });
                setIsInvoiceOpen(false);
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
                variant: "destructive",
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
                });
                setIsBillOpen(false);
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
                variant: "destructive",
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

    const getStatusVariant = (active: boolean): "default" | "destructive" => {
        return active ? "default" : "destructive";
    };

    const getBalanceVariant = (balance: number): "default" | "secondary" | "destructive" | "outline" => {
        if (balance > 0) return "destructive"; // Outstanding balance is usually bad/needs attention
        if (balance < 0) return "default";
        return "secondary";
    };

    const getAccountTypeVariant = (type: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (type?.toLowerCase()) {
            case "asset":
                return "default";
            case "liability":
                return "destructive";
            case "equity":
                return "secondary";
            case "revenue":
                return "default";
            case "expense":
                return "destructive";
            default:
                return "outline";
        }
    };

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Settings className="w-8 h-8 text-[#2CA01C]" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">QuickBooks Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Financial management and accounting platform
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center space-x-4">
                        <Badge
                            variant={healthStatus === "healthy" ? "default" : "destructive"}
                            className="flex items-center space-x-1"
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
                        >
                            <RefreshCw className="mr-2 w-3 h-3" />
                            Refresh Status
                        </Button>
                    </div>

                    {companyInfo && (
                        <div className="flex items-center space-x-4">
                            <div className="flex flex-col">
                                <span className="font-bold">{companyInfo.CompanyName}</span>
                                <span className="text-sm text-muted-foreground">
                                    {companyInfo.LegalName || companyInfo.CompanyName}
                                </span>
                                {companyInfo.Email && (
                                    <span className="text-sm text-muted-foreground">
                                        {companyInfo.Email.Address}
                                    </span>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                {!connected ? (
                    // Connection Required State
                    <Card>
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center justify-center space-y-6 py-8">
                                <Settings className="w-16 h-16 text-gray-400" />
                                <div className="space-y-2 text-center">
                                    <h2 className="text-2xl font-bold">Connect QuickBooks</h2>
                                    <p className="text-muted-foreground">
                                        Connect your QuickBooks account to start managing finances and accounting
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-[#2CA01C] hover:bg-[#238016]"
                                    onClick={() =>
                                    (window.location.href =
                                        "/api/integrations/quickbooks/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect QuickBooks Account
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
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Customers</p>
                                        <div className="text-2xl font-bold">{totalCustomers}</div>
                                        <p className="text-xs text-muted-foreground">{formatCurrency(outstandingInvoices)} outstanding</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Invoices</p>
                                        <div className="text-2xl font-bold">{totalInvoices}</div>
                                        <p className="text-xs text-muted-foreground">{formatCurrency(totalRevenue)} total</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Bills</p>
                                        <div className="text-2xl font-bold">{totalBills}</div>
                                        <p className="text-xs text-muted-foreground">{formatCurrency(outstandingBills)} outstanding</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Employees</p>
                                        <div className="text-2xl font-bold">{activeEmployees}</div>
                                        <p className="text-xs text-muted-foreground">{totalEmployees} total</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="customers">
                            <TabsList>
                                <TabsTrigger value="customers">Customers</TabsTrigger>
                                <TabsTrigger value="invoices">Invoices</TabsTrigger>
                                <TabsTrigger value="bills">Bills</TabsTrigger>
                                <TabsTrigger value="accounts">Accounts</TabsTrigger>
                                <TabsTrigger value="employees">Employees</TabsTrigger>
                                <TabsTrigger value="vendors">Vendors</TabsTrigger>
                            </TabsList>

                            {/* Customers Tab */}
                            <TabsContent value="customers" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search customers..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#2CA01C] hover:bg-[#238016]"
                                        onClick={() => setIsCustomerOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Customer
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Name</TableHead>
                                                    <TableHead>Company</TableHead>
                                                    <TableHead>Email</TableHead>
                                                    <TableHead>Phone</TableHead>
                                                    <TableHead>Balance</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead>Actions</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.customers ? (
                                                    <TableRow>
                                                        <TableCell colSpan={7} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#2CA01C]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    filteredCustomers.map((customer) => (
                                                        <TableRow key={customer.Id}>
                                                            <TableCell className="font-bold">{customer.DisplayName}</TableCell>
                                                            <TableCell>{customer.CompanyName}</TableCell>
                                                            <TableCell>{customer.PrimaryEmailAddr?.Address}</TableCell>
                                                            <TableCell>{customer.PrimaryPhone?.FreeFormNumber}</TableCell>
                                                            <TableCell>
                                                                <Badge variant={getBalanceVariant(customer.Balance)}>
                                                                    {formatCurrency(customer.Balance)}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getStatusVariant(customer.Active)}>
                                                                    {customer.Active ? "Active" : "Inactive"}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Button size="sm" variant="outline">
                                                                    <Eye className="mr-2 w-3 h-3" />
                                                                    Details
                                                                </Button>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Invoices Tab */}
                            <TabsContent value="invoices" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search invoices..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#2CA01C] hover:bg-[#238016]"
                                        onClick={() => setIsInvoiceOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Invoice
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Invoice #</TableHead>
                                                    <TableHead>Customer</TableHead>
                                                    <TableHead>Date</TableHead>
                                                    <TableHead>Due Date</TableHead>
                                                    <TableHead>Total</TableHead>
                                                    <TableHead>Balance</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead>Actions</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.invoices ? (
                                                    <TableRow>
                                                        <TableCell colSpan={8} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#2CA01C]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    filteredInvoices.map((invoice) => (
                                                        <TableRow key={invoice.Id}>
                                                            <TableCell className="font-bold">{invoice.DocNumber}</TableCell>
                                                            <TableCell>{invoice.CustomerRef.name}</TableCell>
                                                            <TableCell>{formatDate(invoice.TxnDate)}</TableCell>
                                                            <TableCell>{formatDate(invoice.DueDate)}</TableCell>
                                                            <TableCell>{formatCurrency(invoice.TotalAmt)}</TableCell>
                                                            <TableCell>
                                                                <Badge variant={getBalanceVariant(invoice.Balance)}>
                                                                    {formatCurrency(invoice.Balance)}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={invoice.Balance > 0 ? "destructive" : "default"}>
                                                                    {invoice.Balance > 0 ? "Outstanding" : "Paid"}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <div className="flex space-x-2">
                                                                    <Button size="sm" variant="outline">
                                                                        <Eye className="mr-2 w-3 h-3" />
                                                                        Details
                                                                    </Button>
                                                                    {invoice.InvoiceLink && (
                                                                        <Button
                                                                            size="sm"
                                                                            variant="outline"
                                                                            onClick={() => window.open(invoice.InvoiceLink, "_blank")}
                                                                        >
                                                                            <ExternalLink className="mr-2 w-3 h-3" />
                                                                            View
                                                                        </Button>
                                                                    )}
                                                                </div>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Bills Tab */}
                            <TabsContent value="bills" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search bills..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#2CA01C] hover:bg-[#238016]"
                                        onClick={() => setIsBillOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Bill
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Bill #</TableHead>
                                                    <TableHead>Vendor</TableHead>
                                                    <TableHead>Date</TableHead>
                                                    <TableHead>Due Date</TableHead>
                                                    <TableHead>Total</TableHead>
                                                    <TableHead>Balance</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead>Actions</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.bills ? (
                                                    <TableRow>
                                                        <TableCell colSpan={8} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#2CA01C]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    filteredBills.map((bill) => (
                                                        <TableRow key={bill.Id}>
                                                            <TableCell className="font-bold">{bill.DocNumber}</TableCell>
                                                            <TableCell>{bill.VendorRef.name}</TableCell>
                                                            <TableCell>{formatDate(bill.TxnDate)}</TableCell>
                                                            <TableCell>{formatDate(bill.DueDate)}</TableCell>
                                                            <TableCell>{formatCurrency(bill.TotalAmt)}</TableCell>
                                                            <TableCell>
                                                                <Badge variant={getBalanceVariant(bill.Balance)}>
                                                                    {formatCurrency(bill.Balance)}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={bill.Balance > 0 ? "destructive" : "default"}>
                                                                    {bill.Balance > 0 ? "Outstanding" : "Paid"}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Button size="sm" variant="outline">
                                                                    <Eye className="mr-2 w-3 h-3" />
                                                                    Details
                                                                </Button>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Accounts Tab */}
                            <TabsContent value="accounts" className="space-y-6 mt-6">
                                <div className="relative">
                                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                    <Input
                                        placeholder="Search accounts..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="pl-8"
                                    />
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Name</TableHead>
                                                    <TableHead>Type</TableHead>
                                                    <TableHead>SubType</TableHead>
                                                    <TableHead>Classification</TableHead>
                                                    <TableHead>Current Balance</TableHead>
                                                    <TableHead>Status</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.accounts ? (
                                                    <TableRow>
                                                        <TableCell colSpan={6} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#2CA01C]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    filteredAccounts.map((account) => (
                                                        <TableRow key={account.Id}>
                                                            <TableCell className="font-bold">{account.Name}</TableCell>
                                                            <TableCell>
                                                                <Badge variant={getAccountTypeVariant(account.AccountType)}>
                                                                    {account.AccountType}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>{account.AccountSubType}</TableCell>
                                                            <TableCell>{account.Classification}</TableCell>
                                                            <TableCell>
                                                                <Badge variant={getBalanceVariant(account.CurrentBalance)}>
                                                                    {formatCurrency(account.CurrentBalance)}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getStatusVariant(account.Active)}>
                                                                    {account.Active ? "Active" : "Inactive"}
                                                                </Badge>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Employees Tab */}
                            <TabsContent value="employees" className="space-y-6 mt-6">
                                <div className="relative">
                                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                    <Input
                                        placeholder="Search employees..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="pl-8"
                                    />
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Name</TableHead>
                                                    <TableHead>Title</TableHead>
                                                    <TableHead>Email</TableHead>
                                                    <TableHead>Phone</TableHead>
                                                    <TableHead>Bill Rate</TableHead>
                                                    <TableHead>Status</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.employees ? (
                                                    <TableRow>
                                                        <TableCell colSpan={6} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#2CA01C]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    filteredEmployees.map((employee) => (
                                                        <TableRow key={employee.Id}>
                                                            <TableCell className="font-bold">{employee.DisplayName}</TableCell>
                                                            <TableCell>{employee.Title}</TableCell>
                                                            <TableCell>{employee.PrimaryEmailAddr?.Address}</TableCell>
                                                            <TableCell>{employee.PrimaryPhone?.FreeFormNumber}</TableCell>
                                                            <TableCell>
                                                                {employee.BillRate ? (
                                                                    <Badge variant="secondary">
                                                                        {formatCurrency(employee.BillRate)}
                                                                    </Badge>
                                                                ) : (
                                                                    <span className="text-muted-foreground">-</span>
                                                                )}
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getStatusVariant(employee.Active)}>
                                                                    {employee.Active ? "Active" : employee.Status}
                                                                </Badge>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Vendors Tab */}
                            <TabsContent value="vendors" className="space-y-6 mt-6">
                                <div className="relative">
                                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                    <Input
                                        placeholder="Search vendors..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="pl-8"
                                    />
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Name</TableHead>
                                                    <TableHead>Company</TableHead>
                                                    <TableHead>Email</TableHead>
                                                    <TableHead>Phone</TableHead>
                                                    <TableHead>Balance</TableHead>
                                                    <TableHead>Status</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.vendors ? (
                                                    <TableRow>
                                                        <TableCell colSpan={6} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#2CA01C]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    filteredVendors.map((vendor) => (
                                                        <TableRow key={vendor.Id}>
                                                            <TableCell className="font-bold">{vendor.DisplayName}</TableCell>
                                                            <TableCell>{vendor.CompanyName}</TableCell>
                                                            <TableCell>{vendor.PrimaryEmailAddr?.Address}</TableCell>
                                                            <TableCell>{vendor.PrimaryPhone?.FreeFormNumber}</TableCell>
                                                            <TableCell>
                                                                <Badge variant={getBalanceVariant(vendor.Balance)}>
                                                                    {formatCurrency(vendor.Balance)}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getStatusVariant(vendor.Active)}>
                                                                    {vendor.Active ? "Active" : "Inactive"}
                                                                </Badge>
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>
                        </Tabs>

                        {/* Create Customer Modal */}
                        <Dialog open={isCustomerOpen} onOpenChange={setIsCustomerOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create Customer</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Display Name</label>
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
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Company Name</label>
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
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Email</label>
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
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Phone</label>
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
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Address</label>
                                        <div className="space-y-2">
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
                                            <div className="grid grid-cols-3 gap-2">
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
                                            </div>
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
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsCustomerOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2CA01C] hover:bg-[#238016]"
                                        onClick={createCustomer}
                                        disabled={!customerForm.DisplayName}
                                    >
                                        Create Customer
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Create Invoice Modal */}
                        <Dialog open={isInvoiceOpen} onOpenChange={setIsInvoiceOpen}>
                            <DialogContent className="max-w-2xl">
                                <DialogHeader>
                                    <DialogTitle>Create Invoice</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Customer</label>
                                        <Select
                                            value={invoiceForm.CustomerRef.value}
                                            onValueChange={(value) => {
                                                const customer = customers.find(c => c.Id === value);
                                                setInvoiceForm({
                                                    ...invoiceForm,
                                                    CustomerRef: {
                                                        value: value,
                                                        name: customer?.DisplayName || "",
                                                    },
                                                });
                                            }}
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Customer" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {customers.map((customer) => (
                                                    <SelectItem key={customer.Id} value={customer.Id}>
                                                        {customer.DisplayName}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Invoice Date</label>
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
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Due Date</label>
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
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-bold leading-none">Invoice Lines</label>
                                        {invoiceForm.Line.map((line, index) => (
                                            <div key={index} className="flex space-x-2 items-end">
                                                <div className="flex-1 space-y-1">
                                                    <Input
                                                        placeholder="Description"
                                                        value={line.Description}
                                                        onChange={(e) => {
                                                            const newLines = [...invoiceForm.Line];
                                                            newLines[index].Description = e.target.value;
                                                            setInvoiceForm({ ...invoiceForm, Line: newLines });
                                                        }}
                                                    />
                                                </div>
                                                <div className="w-32 space-y-1">
                                                    <Input
                                                        type="number"
                                                        placeholder="Amount"
                                                        value={line.Amount}
                                                        onChange={(e) => {
                                                            const newLines = [...invoiceForm.Line];
                                                            newLines[index].Amount = parseFloat(e.target.value);
                                                            setInvoiceForm({ ...invoiceForm, Line: newLines });
                                                        }}
                                                    />
                                                </div>
                                                <Button
                                                    size="icon"
                                                    variant="destructive"
                                                    onClick={() => {
                                                        const newLines = invoiceForm.Line.filter((_, i) => i !== index);
                                                        setInvoiceForm({ ...invoiceForm, Line: newLines });
                                                    }}
                                                >
                                                    <Trash className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        ))}

                                        <Button
                                            variant="outline"
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
                                            <Plus className="mr-2 w-4 h-4" />
                                            Add Line
                                        </Button>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsInvoiceOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2CA01C] hover:bg-[#238016]"
                                        onClick={createInvoice}
                                        disabled={!invoiceForm.CustomerRef.value || invoiceForm.Line.length === 0}
                                    >
                                        Create Invoice
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Create Bill Modal */}
                        <Dialog open={isBillOpen} onOpenChange={setIsBillOpen}>
                            <DialogContent className="max-w-2xl">
                                <DialogHeader>
                                    <DialogTitle>Create Bill</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Vendor</label>
                                        <Select
                                            value={billForm.VendorRef.value}
                                            onValueChange={(value) => {
                                                const vendor = vendors.find(v => v.Id === value);
                                                setBillForm({
                                                    ...billForm,
                                                    VendorRef: {
                                                        value: value,
                                                        name: vendor?.DisplayName || "",
                                                    },
                                                });
                                            }}
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Vendor" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {vendors.map((vendor) => (
                                                    <SelectItem key={vendor.Id} value={vendor.Id}>
                                                        {vendor.DisplayName}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Bill Date</label>
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
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Due Date</label>
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
                                        </div>
                                    </div>

                                    <div className="space-y-2">
                                        <label className="text-sm font-bold leading-none">Bill Lines</label>
                                        {billForm.Line.map((line, index) => (
                                            <div key={index} className="flex space-x-2 items-end">
                                                <div className="flex-1 space-y-1">
                                                    <Input
                                                        placeholder="Description"
                                                        value={line.Description}
                                                        onChange={(e) => {
                                                            const newLines = [...billForm.Line];
                                                            newLines[index].Description = e.target.value;
                                                            setBillForm({ ...billForm, Line: newLines });
                                                        }}
                                                    />
                                                </div>
                                                <div className="w-32 space-y-1">
                                                    <Input
                                                        type="number"
                                                        placeholder="Amount"
                                                        value={line.Amount}
                                                        onChange={(e) => {
                                                            const newLines = [...billForm.Line];
                                                            newLines[index].Amount = parseFloat(e.target.value);
                                                            setBillForm({ ...billForm, Line: newLines });
                                                        }}
                                                    />
                                                </div>
                                                <Button
                                                    size="icon"
                                                    variant="destructive"
                                                    onClick={() => {
                                                        const newLines = billForm.Line.filter((_, i) => i !== index);
                                                        setBillForm({ ...billForm, Line: newLines });
                                                    }}
                                                >
                                                    <Trash className="w-4 h-4" />
                                                </Button>
                                            </div>
                                        ))}

                                        <Button
                                            variant="outline"
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
                                            <Plus className="mr-2 w-4 h-4" />
                                            Add Line
                                        </Button>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsBillOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2CA01C] hover:bg-[#238016]"
                                        onClick={createBill}
                                        disabled={!billForm.VendorRef.value || billForm.Line.length === 0}
                                    >
                                        Create Bill
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

export default QuickBooksIntegration;
