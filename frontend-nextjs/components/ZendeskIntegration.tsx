/**
 * Zendesk Integration Component
 * Complete Zendesk customer support and help desk integration
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
    Phone,
    FileText,
    Download,
    ExternalLink,
    HelpCircle,
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

interface ZendeskTicket {
    id: number;
    url: string;
    external_id?: string;
    type: string;
    subject: string;
    raw_subject?: string;
    description: string;
    priority: string;
    status: string;
    recipient?: string;
    requester_id: number;
    requester?: {
        id: number;
        name: string;
        email: string;
        locale?: string;
        timezone?: string;
        user_fields?: any;
        role?: string;
        verified?: boolean;
        active?: boolean;
        phone?: string;
        photo?: {
            thumbnails?: Array<{
                url: string;
                id: string;
                file_name: string;
                content_url: string;
                content_type: string;
                size: number;
                width?: number;
                height?: number;
                inline?: boolean;
            }>;
        };
        organization_id?: number;
        organization?: {
            id: number;
            name: string;
            created_at: string;
            updated_at: string;
            domain_names?: string[];
            tags?: string[];
            organization_fields?: any;
            shared_tickets?: boolean;
            shared_comments?: boolean;
            external_id?: string;
        };
    };
    submitter_id?: number;
    assignee_id?: number;
    assignee?: {
        id: number;
        name: string;
        email: string;
        created_at: string;
        updated_at: string;
        active: boolean;
        verified: boolean;
        shared: boolean;
        shared_agent: boolean;
        photo?: {
            thumbnails?: Array<{
                url: string;
                id: string;
                file_name: string;
                content_url: string;
                content_type: string;
                size: number;
                width?: number;
                height?: number;
                inline?: boolean;
            }>;
        };
    };
    group_id?: number;
    group?: {
        id: number;
        name: string;
        description?: string;
        created_at: string;
        updated_at: string;
        url: string;
        deleted: boolean;
    };
    collaborator_ids?: number[];
    collaborators?: Array<{
        id: number;
        name: string;
        email: string;
        locale?: string;
        timezone?: string;
        user_fields?: any;
        role?: string;
        verified?: boolean;
        active?: boolean;
        phone?: string;
        photo?: {
            thumbnails?: Array<{
                url: string;
                id: string;
                file_name: string;
                content_url: string;
                content_type: string;
                size: number;
                width?: number;
                height?: number;
                inline?: boolean;
            }>;
        };
    }>;
    forum_topic_id?: number;
    problem_id?: number;
    has_incidents?: boolean;
    is_public?: boolean;
    due_at?: string;
    tags?: string[];
    via: {
        channel: string;
        source: {
            from: any;
            to: any;
            rel?: string;
        };
    };
    custom_fields?: Array<{
        id: number;
        value: any;
    }>;
    satisfaction_rating?: {
        id: number;
        score: string;
        comment?: string;
        created_at: string;
    };
    sharing_agreement_ids?: number[];
    followup_ids?: number[];
    ticket_form_id?: number;
    brand_id?: number;
    created_at: string;
    updated_at: string;
}

interface ZendeskUser {
    id: number;
    url: string;
    name: string;
    email: string;
    created_at: string;
    updated_at: string;
    active: boolean;
    verified: boolean;
    shared: boolean;
    shared_agent: boolean;
    locale: string;
    timezone: string;
    phone?: string;
    signature?: string;
    details?: string;
    notes?: string;
    photo?: {
        thumbnails?: Array<{
            url: string;
            id: string;
            file_name: string;
            content_url: string;
            content_type: string;
            size: number;
            width?: number;
            height?: number;
            inline?: boolean;
        }>;
    };
    organization_id?: number;
    organization?: {
        id: number;
        name: string;
        created_at: string;
        updated_at: string;
        domain_names?: string[];
        tags?: string[];
        organization_fields?: any;
        shared_tickets?: boolean;
        shared_comments?: boolean;
        external_id?: string;
    };
    role: string;
    custom_role_id?: number;
    tags: string[];
    suspended?: boolean;
    last_login_at?: string;
    two_factor_auth_enabled?: boolean;
    user_fields?: any;
}

interface ZendeskGroup {
    id: number;
    url: string;
    name: string;
    description?: string;
    created_at: string;
    updated_at: string;
    deleted: boolean;
}

interface ZendeskView {
    id: number;
    url: string;
    title: string;
    active: boolean;
    position: number;
    description?: string;
    created_at: string;
    updated_at: string;
    conditions: {
        all: Array<{
            field: string;
            operator: string;
            value: any;
        }>;
        any: Array<{
            field: string;
            operator: string;
            value: any;
        }>;
    };
    execution: {
        order: Array<{
            field: string;
            direction: string;
        }>;
        group_by?: Array<{
            field: string;
            direction: string;
        }>;
        group_count?: number;
        group_custom_field?: number;
        sort_by?: string;
        sort_order?: string;
    };
    columns: Array<{
        id: number;
        title: string;
        type: string;
        field: string;
        width?: number;
    }>;
    restrictions?: {
        group_ids?: number[];
        user_ids?: number[];
    };
}

interface ZendeskOrganization {
    id: number;
    url: string;
    name: string;
    created_at: string;
    updated_at: string;
    domain_names: string[];
    tags: string[];
    organization_fields?: any;
    shared_tickets: boolean;
    shared_comments: boolean;
    external_id?: string;
    details?: string;
    notes?: string;
    group_id?: number;
}

const ZendeskIntegration: React.FC = () => {
    const [tickets, setTickets] = useState<ZendeskTicket[]>([]);
    const [users, setUsers] = useState<ZendeskUser[]>([]);
    const [groups, setGroups] = useState<ZendeskGroup[]>([]);
    const [views, setViews] = useState<ZendeskView[]>([]);
    const [organizations, setOrganizations] = useState<ZendeskOrganization[]>([]);
    const [userProfile, setUserProfile] = useState<ZendeskUser | null>(null);
    const [loading, setLoading] = useState({
        tickets: false,
        users: false,
        groups: false,
        views: false,
        organizations: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedStatus, setSelectedStatus] = useState("");
    const [selectedPriority, setSelectedPriority] = useState("");

    // Form states
    const [ticketForm, setTicketForm] = useState({
        subject: "",
        description: "",
        priority: "normal",
        type: "question",
        status: "new",
        requester_id: "",
        assignee_id: "",
        group_id: "",
        tags: [] as string[],
        due_at: "",
    });

    const [userForm, setUserForm] = useState({
        name: "",
        email: "",
        phone: "",
        role: "end-user",
        organization_id: "",
        verified: false,
        suspended: false,
        tags: [] as string[],
    });

    const [organizationForm, setOrganizationForm] = useState({
        name: "",
        domain_names: [] as string[],
        tags: [] as string[],
        shared_tickets: false,
        shared_comments: false,
        notes: "",
    });

    const [isTicketOpen, setIsTicketOpen] = useState(false);
    const [isUserOpen, setIsUserOpen] = useState(false);
    const [isOrganizationOpen, setIsOrganizationOpen] = useState(false);

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/zendesk/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
                loadTickets();
                loadUsers();
                loadGroups();
                loadViews();
                loadOrganizations();
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

    // Load Zendesk data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/zendesk/profile", {
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

    const loadTickets = async () => {
        setLoading((prev) => ({ ...prev, tickets: true }));
        try {
            const response = await fetch("/api/integrations/zendesk/tickets", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                    status: selectedStatus || "",
                    priority: selectedPriority || "",
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setTickets(data.data?.tickets || []);
            }
        } catch (error) {
            console.error("Failed to load tickets:", error);
            toast({
                title: "Error",
                description: "Failed to load tickets from Zendesk",
                variant: "destructive",
            });
        } finally {
            setLoading((prev) => ({ ...prev, tickets: false }));
        }
    };

    const loadUsers = async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        try {
            const response = await fetch("/api/integrations/zendesk/users", {
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

    const loadGroups = async () => {
        setLoading((prev) => ({ ...prev, groups: true }));
        try {
            const response = await fetch("/api/integrations/zendesk/groups", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setGroups(data.data?.groups || []);
            }
        } catch (error) {
            console.error("Failed to load groups:", error);
        } finally {
            setLoading((prev) => ({ ...prev, groups: false }));
        }
    };

    const loadViews = async () => {
        setLoading((prev) => ({ ...prev, views: true }));
        try {
            const response = await fetch("/api/integrations/zendesk/views", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setViews(data.data?.views || []);
            }
        } catch (error) {
            console.error("Failed to load views:", error);
        } finally {
            setLoading((prev) => ({ ...prev, views: false }));
        }
    };

    const loadOrganizations = async () => {
        setLoading((prev) => ({ ...prev, organizations: true }));
        try {
            const response = await fetch("/api/integrations/zendesk/organizations", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setOrganizations(data.data?.organizations || []);
            }
        } catch (error) {
            console.error("Failed to load organizations:", error);
        } finally {
            setLoading((prev) => ({ ...prev, organizations: false }));
        }
    };

    // Create operations
    const createTicket = async () => {
        if (!ticketForm.subject || !ticketForm.description) return;

        try {
            const response = await fetch("/api/integrations/zendesk/tickets/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    ticket: {
                        subject: ticketForm.subject,
                        description: ticketForm.description,
                        priority: ticketForm.priority,
                        type: ticketForm.type,
                        status: ticketForm.status,
                        requester_id: parseInt(ticketForm.requester_id) || undefined,
                        assignee_id: parseInt(ticketForm.assignee_id) || undefined,
                        group_id: parseInt(ticketForm.group_id) || undefined,
                        tags: ticketForm.tags,
                        due_at: ticketForm.due_at || undefined,
                    },
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Ticket created successfully",
                });
                setIsTicketOpen(false);
                setTicketForm({
                    subject: "",
                    description: "",
                    priority: "normal",
                    type: "question",
                    status: "new",
                    requester_id: "",
                    assignee_id: "",
                    group_id: "",
                    tags: [],
                    due_at: "",
                });
                loadTickets();
            }
        } catch (error) {
            console.error("Failed to create ticket:", error);
            toast({
                title: "Error",
                description: "Failed to create ticket",
                variant: "destructive",
            });
        }
    };

    const createUser = async () => {
        if (!userForm.name || !userForm.email) return;

        try {
            const response = await fetch("/api/integrations/zendesk/users/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    user: {
                        name: userForm.name,
                        email: userForm.email,
                        phone: userForm.phone || undefined,
                        role: userForm.role,
                        organization_id: parseInt(userForm.organization_id) || undefined,
                        verified: userForm.verified,
                        suspended: userForm.suspended,
                        tags: userForm.tags,
                    },
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "User created successfully",
                });
                setIsUserOpen(false);
                setUserForm({
                    name: "",
                    email: "",
                    phone: "",
                    role: "end-user",
                    organization_id: "",
                    verified: false,
                    suspended: false,
                    tags: [],
                });
                loadUsers();
            }
        } catch (error) {
            console.error("Failed to create user:", error);
            toast({
                title: "Error",
                description: "Failed to create user",
                variant: "destructive",
            });
        }
    };

    const createOrganization = async () => {
        if (!organizationForm.name) return;

        try {
            const response = await fetch("/api/integrations/zendesk/organizations/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    organization: {
                        name: organizationForm.name,
                        domain_names: organizationForm.domain_names,
                        tags: organizationForm.tags,
                        shared_tickets: organizationForm.shared_tickets,
                        shared_comments: organizationForm.shared_comments,
                        notes: organizationForm.notes || undefined,
                    },
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Organization created successfully",
                });
                setIsOrganizationOpen(false);
                setOrganizationForm({
                    name: "",
                    domain_names: [],
                    tags: [],
                    shared_tickets: false,
                    shared_comments: false,
                    notes: "",
                });
                loadOrganizations();
            }
        } catch (error) {
            console.error("Failed to create organization:", error);
            toast({
                title: "Error",
                description: "Failed to create organization",
                variant: "destructive",
            });
        }
    };

    // Filter data based on search
    const filteredTickets = tickets.filter(
        (ticket) =>
            ticket.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
            ticket.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
            ticket.requester?.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredUsers = users.filter(
        (user) =>
            user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.email.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredOrganizations = organizations.filter(
        (org) =>
            org.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            org.domain_names.some(domain => domain.toLowerCase().includes(searchQuery.toLowerCase()))
    );

    // Stats calculations
    const totalTickets = tickets.length;
    const openTickets = tickets.filter(t => ["new", "open", "pending"].includes(t.status)).length;
    const solvedTickets = tickets.filter(t => t.status === "solved").length;
    const urgentTickets = tickets.filter(t => t.priority === "urgent").length;
    const totalUsers = users.length;
    const activeUsers = users.filter(u => u.active).length;
    const totalOrganizations = organizations.length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadUserProfile();
            loadTickets();
            loadUsers();
            loadGroups();
            loadViews();
            loadOrganizations();
        }
    }, [connected]);

    useEffect(() => {
        if (connected) {
            loadTickets();
        }
    }, [selectedStatus, selectedPriority]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status?.toLowerCase()) {
            case "new":
                return "default";
            case "open":
                return "destructive";
            case "pending":
                return "secondary";
            case "solved":
                return "outline";
            case "closed":
                return "outline";
            case "hold":
                return "secondary";
            default:
                return "outline";
        }
    };

    const getPriorityVariant = (priority: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (priority?.toLowerCase()) {
            case "urgent":
                return "destructive";
            case "high":
                return "destructive";
            case "normal":
                return "secondary";
            case "low":
                return "default";
            default:
                return "outline";
        }
    };

    const getTypeVariant = (type: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (type?.toLowerCase()) {
            case "question":
                return "default";
            case "incident":
                return "destructive";
            case "problem":
                return "destructive";
            case "task":
                return "secondary";
            default:
                return "outline";
        }
    };

    const getRoleVariant = (role: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (role?.toLowerCase()) {
            case "admin":
                return "destructive";
            case "agent":
                return "default";
            case "end-user":
                return "secondary";
            default:
                return "outline";
        }
    };

    const getViaVariant = (via: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (via?.toLowerCase()) {
            case "web":
                return "default";
            case "email":
                return "secondary";
            case "api":
                return "outline";
            case "voice":
                return "destructive";
            case "chat":
                return "default";
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
                        <Settings className="w-8 h-8 text-[#03363D]" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Zendesk Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Customer support and help desk platform
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

                    {userProfile && (
                        <div className="flex items-center space-x-4">
                            <Avatar>
                                <AvatarImage src={userProfile.photo?.thumbnails?.[0]?.url} />
                                <AvatarFallback>{userProfile.name.charAt(0)}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col">
                                <span className="font-bold">{userProfile.name}</span>
                                <span className="text-sm text-muted-foreground">
                                    {userProfile.email} • {userProfile.role}
                                </span>
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
                                    <h2 className="text-2xl font-bold">Connect Zendesk</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Zendesk account to start managing customer support tickets
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-[#03363D] hover:bg-[#022a30]"
                                    onClick={() =>
                                    (window.location.href =
                                        "/api/integrations/zendesk/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Zendesk Account
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
                                        <p className="text-sm font-medium text-muted-foreground">Tickets</p>
                                        <div className="text-2xl font-bold">{totalTickets}</div>
                                        <p className="text-xs text-muted-foreground">{openTickets} open</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Solved</p>
                                        <div className="text-2xl font-bold">{solvedTickets}</div>
                                        <p className="text-xs text-muted-foreground">Completed tickets</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Users</p>
                                        <div className="text-2xl font-bold">{activeUsers}</div>
                                        <p className="text-xs text-muted-foreground">{totalUsers} total</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Organizations</p>
                                        <div className="text-2xl font-bold">{totalOrganizations}</div>
                                        <p className="text-xs text-muted-foreground">Support orgs</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="tickets">
                            <TabsList>
                                <TabsTrigger value="tickets">Tickets</TabsTrigger>
                                <TabsTrigger value="users">Users</TabsTrigger>
                                <TabsTrigger value="groups">Groups</TabsTrigger>
                                <TabsTrigger value="views">Views</TabsTrigger>
                                <TabsTrigger value="organizations">Organizations</TabsTrigger>
                            </TabsList>

                            {/* Tickets Tab */}
                            <TabsContent value="tickets" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedStatus}
                                        onValueChange={setSelectedStatus}
                                    >
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="All Status" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Status</SelectItem>
                                            <SelectItem value="new">New</SelectItem>
                                            <SelectItem value="open">Open</SelectItem>
                                            <SelectItem value="pending">Pending</SelectItem>
                                            <SelectItem value="solved">Solved</SelectItem>
                                            <SelectItem value="closed">Closed</SelectItem>
                                            <SelectItem value="hold">Hold</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Select
                                        value={selectedPriority}
                                        onValueChange={setSelectedPriority}
                                    >
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="All Priority" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Priority</SelectItem>
                                            <SelectItem value="urgent">Urgent</SelectItem>
                                            <SelectItem value="high">High</SelectItem>
                                            <SelectItem value="normal">Normal</SelectItem>
                                            <SelectItem value="low">Low</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search tickets..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#03363D] hover:bg-[#022a30]"
                                        onClick={() => setIsTicketOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Ticket
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>ID</TableHead>
                                                    <TableHead>Subject</TableHead>
                                                    <TableHead>Requester</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead>Priority</TableHead>
                                                    <TableHead>Type</TableHead>
                                                    <TableHead>Created</TableHead>
                                                    <TableHead>Actions</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.tickets ? (
                                                    <TableRow>
                                                        <TableCell colSpan={8} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#03363D]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    filteredTickets.map((ticket) => (
                                                        <TableRow key={ticket.id}>
                                                            <TableCell className="font-bold">#{ticket.id}</TableCell>
                                                            <TableCell>
                                                                <div className="flex flex-col space-y-1">
                                                                    <span
                                                                        className="font-medium cursor-pointer text-blue-600 hover:text-blue-700"
                                                                        onClick={() => window.open(ticket.url, "_blank")}
                                                                    >
                                                                        {ticket.subject}
                                                                    </span>
                                                                    {ticket.via && (
                                                                        <Badge variant={getViaVariant(ticket.via.channel)} className="w-fit">
                                                                            {ticket.via.channel}
                                                                        </Badge>
                                                                    )}
                                                                </div>
                                                            </TableCell>
                                                            <TableCell>
                                                                <div className="flex items-center space-x-2">
                                                                    <Avatar className="w-6 h-6">
                                                                        <AvatarImage src={ticket.requester?.photo?.thumbnails?.[0]?.url} />
                                                                        <AvatarFallback>{ticket.requester?.name?.charAt(0)}</AvatarFallback>
                                                                    </Avatar>
                                                                    <span>{ticket.requester?.name}</span>
                                                                </div>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getStatusVariant(ticket.status)}>
                                                                    {ticket.status}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getPriorityVariant(ticket.priority)}>
                                                                    {ticket.priority}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getTypeVariant(ticket.type)}>
                                                                    {ticket.type}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell className="text-sm text-muted-foreground">
                                                                {formatDate(ticket.created_at)}
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

                            {/* Users Tab */}
                            <TabsContent value="users" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search users..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#03363D] hover:bg-[#022a30]"
                                        onClick={() => setIsUserOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create User
                                    </Button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.users ? (
                                        <div className="col-span-full flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#03363D]" />
                                        </div>
                                    ) : (
                                        filteredUsers.map((user) => (
                                            <Card key={user.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex items-start space-x-4">
                                                        <Avatar className="w-12 h-12">
                                                            <AvatarImage src={user.photo?.thumbnails?.[0]?.url} />
                                                            <AvatarFallback>{user.name.charAt(0)}</AvatarFallback>
                                                        </Avatar>
                                                        <div className="flex flex-col space-y-1 flex-1">
                                                            <span className="font-bold">{user.name}</span>
                                                            <span className="text-sm text-muted-foreground">
                                                                {user.email}
                                                            </span>
                                                            <div className="flex space-x-2">
                                                                <Badge variant={getRoleVariant(user.role)}>
                                                                    {user.role}
                                                                </Badge>
                                                                <Badge variant={user.active ? "default" : "destructive"}>
                                                                    {user.active ? "Active" : "Inactive"}
                                                                </Badge>
                                                            </div>
                                                            {user.organization && (
                                                                <span className="text-xs text-muted-foreground mt-1">
                                                                    {user.organization.name}
                                                                </span>
                                                            )}
                                                            {user.phone && (
                                                                <span className="text-xs text-muted-foreground flex items-center mt-1">
                                                                    <Phone className="w-3 h-3 mr-1" /> {user.phone}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Groups Tab */}
                            <TabsContent value="groups" className="space-y-6 mt-6">
                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>ID</TableHead>
                                                    <TableHead>Name</TableHead>
                                                    <TableHead>Description</TableHead>
                                                    <TableHead>Created</TableHead>
                                                    <TableHead>Updated</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.groups ? (
                                                    <TableRow>
                                                        <TableCell colSpan={5} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#03363D]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    groups.map((group) => (
                                                        <TableRow key={group.id}>
                                                            <TableCell className="font-bold">#{group.id}</TableCell>
                                                            <TableCell className="font-medium">{group.name}</TableCell>
                                                            <TableCell>{group.description}</TableCell>
                                                            <TableCell className="text-sm text-muted-foreground">
                                                                {formatDate(group.created_at)}
                                                            </TableCell>
                                                            <TableCell className="text-sm text-muted-foreground">
                                                                {formatDate(group.updated_at)}
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Views Tab */}
                            <TabsContent value="views" className="space-y-6 mt-6">
                                <Card>
                                    <CardContent className="p-0">
                                        <Table>
                                            <TableHeader>
                                                <TableRow>
                                                    <TableHead>Title</TableHead>
                                                    <TableHead>Description</TableHead>
                                                    <TableHead>Status</TableHead>
                                                    <TableHead>Created</TableHead>
                                                    <TableHead>Updated</TableHead>
                                                </TableRow>
                                            </TableHeader>
                                            <TableBody>
                                                {loading.views ? (
                                                    <TableRow>
                                                        <TableCell colSpan={5} className="text-center py-8">
                                                            <Loader2 className="w-8 h-8 animate-spin mx-auto text-[#03363D]" />
                                                        </TableCell>
                                                    </TableRow>
                                                ) : (
                                                    views.map((view) => (
                                                        <TableRow key={view.id}>
                                                            <TableCell className="font-medium">{view.title}</TableCell>
                                                            <TableCell>{view.description}</TableCell>
                                                            <TableCell>
                                                                <Badge variant={view.active ? "default" : "destructive"}>
                                                                    {view.active ? "Active" : "Inactive"}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell className="text-sm text-muted-foreground">
                                                                {formatDate(view.created_at)}
                                                            </TableCell>
                                                            <TableCell className="text-sm text-muted-foreground">
                                                                {formatDate(view.updated_at)}
                                                            </TableCell>
                                                        </TableRow>
                                                    ))
                                                )}
                                            </TableBody>
                                        </Table>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Organizations Tab */}
                            <TabsContent value="organizations" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search organizations..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#03363D] hover:bg-[#022a30]"
                                        onClick={() => setIsOrganizationOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Organization
                                    </Button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.organizations ? (
                                        <div className="col-span-full flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#03363D]" />
                                        </div>
                                    ) : (
                                        filteredOrganizations.map((org) => (
                                            <Card key={org.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex flex-col space-y-2">
                                                        <span className="font-bold text-lg">{org.name}</span>
                                                        {org.domain_names.length > 0 && (
                                                            <div className="flex flex-wrap gap-2">
                                                                {org.domain_names.map((domain, index) => (
                                                                    <Badge key={index} variant="secondary">
                                                                        {domain}
                                                                    </Badge>
                                                                ))}
                                                            </div>
                                                        )}
                                                        <div className="flex space-x-2">
                                                            {org.shared_tickets && (
                                                                <Badge variant="default">Shared Tickets</Badge>
                                                            )}
                                                            {org.shared_comments && (
                                                                <Badge variant="default">Shared Comments</Badge>
                                                            )}
                                                        </div>
                                                        {org.tags.length > 0 && (
                                                            <div className="flex flex-wrap gap-2">
                                                                {org.tags.map((tag, index) => (
                                                                    <Badge key={index} variant="outline">
                                                                        {tag}
                                                                    </Badge>
                                                                ))}
                                                            </div>
                                                        )}
                                                        <span className="text-xs text-muted-foreground mt-2">
                                                            Created: {formatDate(org.created_at)}
                                                        </span>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>
                        </Tabs>

                        {/* Create Ticket Modal */}
                        <Dialog open={isTicketOpen} onOpenChange={setIsTicketOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create Ticket</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Subject</label>
                                        <Input
                                            placeholder="Ticket subject"
                                            value={ticketForm.subject}
                                            onChange={(e) =>
                                                setTicketForm({
                                                    ...ticketForm,
                                                    subject: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Ticket description"
                                            value={ticketForm.description}
                                            onChange={(e) =>
                                                setTicketForm({
                                                    ...ticketForm,
                                                    description: e.target.value,
                                                })
                                            }
                                            rows={6}
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Type</label>
                                            <Select
                                                value={ticketForm.type}
                                                onValueChange={(value) =>
                                                    setTicketForm({
                                                        ...ticketForm,
                                                        type: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select Type" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="question">Question</SelectItem>
                                                    <SelectItem value="incident">Incident</SelectItem>
                                                    <SelectItem value="problem">Problem</SelectItem>
                                                    <SelectItem value="task">Task</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Priority</label>
                                            <Select
                                                value={ticketForm.priority}
                                                onValueChange={(value) =>
                                                    setTicketForm({
                                                        ...ticketForm,
                                                        priority: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select Priority" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="urgent">Urgent</SelectItem>
                                                    <SelectItem value="high">High</SelectItem>
                                                    <SelectItem value="normal">Normal</SelectItem>
                                                    <SelectItem value="low">Low</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Requester</label>
                                            <Select
                                                value={ticketForm.requester_id}
                                                onValueChange={(value) =>
                                                    setTicketForm({
                                                        ...ticketForm,
                                                        requester_id: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select User" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {users.map((user) => (
                                                        <SelectItem key={user.id} value={user.id.toString()}>
                                                            {user.name}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Assignee</label>
                                            <Select
                                                value={ticketForm.assignee_id}
                                                onValueChange={(value) =>
                                                    setTicketForm({
                                                        ...ticketForm,
                                                        assignee_id: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select Agent" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {users.filter(u => u.role === "agent" || u.role === "admin").map((user) => (
                                                        <SelectItem key={user.id} value={user.id.toString()}>
                                                            {user.name}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Due Date</label>
                                        <Input
                                            type="datetime-local"
                                            value={ticketForm.due_at}
                                            onChange={(e) =>
                                                setTicketForm({
                                                    ...ticketForm,
                                                    due_at: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsTicketOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#03363D] hover:bg-[#022a30]"
                                        onClick={createTicket}
                                        disabled={!ticketForm.subject || !ticketForm.description}
                                    >
                                        Create Ticket
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Create User Modal */}
                        <Dialog open={isUserOpen} onOpenChange={setIsUserOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create User</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Name</label>
                                            <Input
                                                placeholder="User name"
                                                value={userForm.name}
                                                onChange={(e) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        name: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Email</label>
                                            <Input
                                                type="email"
                                                placeholder="user@example.com"
                                                value={userForm.email}
                                                onChange={(e) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        email: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Role</label>
                                            <Select
                                                value={userForm.role}
                                                onValueChange={(value) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        role: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue placeholder="Select Role" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="end-user">End User</SelectItem>
                                                    <SelectItem value="agent">Agent</SelectItem>
                                                    <SelectItem value="admin">Admin</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Phone</label>
                                            <Input
                                                placeholder="Phone number"
                                                value={userForm.phone}
                                                onChange={(e) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        phone: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Organization</label>
                                        <Select
                                            value={userForm.organization_id}
                                            onValueChange={(value) =>
                                                setUserForm({
                                                    ...userForm,
                                                    organization_id: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Organization" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {organizations.map((org) => (
                                                    <SelectItem key={org.id} value={org.id.toString()}>
                                                        {org.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="flex space-x-4">
                                        <div className="flex items-center space-x-2">
                                            <Checkbox
                                                id="verified"
                                                checked={userForm.verified}
                                                onCheckedChange={(checked) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        verified: checked as boolean,
                                                    })
                                                }
                                            />
                                            <label
                                                htmlFor="verified"
                                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                            >
                                                Verified
                                            </label>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <Checkbox
                                                id="suspended"
                                                checked={userForm.suspended}
                                                onCheckedChange={(checked) =>
                                                    setUserForm({
                                                        ...userForm,
                                                        suspended: checked as boolean,
                                                    })
                                                }
                                            />
                                            <label
                                                htmlFor="suspended"
                                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                            >
                                                Suspended
                                            </label>
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsUserOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#03363D] hover:bg-[#022a30]"
                                        onClick={createUser}
                                        disabled={!userForm.name || !userForm.email}
                                    >
                                        Create User
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Create Organization Modal */}
                        <Dialog open={isOrganizationOpen} onOpenChange={setIsOrganizationOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create Organization</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Organization Name</label>
                                        <Input
                                            placeholder="Organization name"
                                            value={organizationForm.name}
                                            onChange={(e) =>
                                                setOrganizationForm({
                                                    ...organizationForm,
                                                    name: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Domain Names</label>
                                        <Input
                                            placeholder="domain1.com, domain2.com"
                                            value={organizationForm.domain_names.join(", ")}
                                            onChange={(e) =>
                                                setOrganizationForm({
                                                    ...organizationForm,
                                                    domain_names: e.target.value.split(",").map(s => s.trim()).filter(s => s),
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Notes</label>
                                        <Textarea
                                            placeholder="Organization notes"
                                            value={organizationForm.notes}
                                            onChange={(e) =>
                                                setOrganizationForm({
                                                    ...organizationForm,
                                                    notes: e.target.value,
                                                })
                                            }
                                            rows={3}
                                        />
                                    </div>
                                    <div className="flex space-x-4">
                                        <div className="flex items-center space-x-2">
                                            <Checkbox
                                                id="shared_tickets"
                                                checked={organizationForm.shared_tickets}
                                                onCheckedChange={(checked) =>
                                                    setOrganizationForm({
                                                        ...organizationForm,
                                                        shared_tickets: checked as boolean,
                                                    })
                                                }
                                            />
                                            <label
                                                htmlFor="shared_tickets"
                                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                            >
                                                Shared Tickets
                                            </label>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <Checkbox
                                                id="shared_comments"
                                                checked={organizationForm.shared_comments}
                                                onCheckedChange={(checked) =>
                                                    setOrganizationForm({
                                                        ...organizationForm,
                                                        shared_comments: checked as boolean,
                                                    })
                                                }
                                            />
                                            <label
                                                htmlFor="shared_comments"
                                                className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                            >
                                                Shared Comments
                                            </label>
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsOrganizationOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#03363D] hover:bg-[#022a30]"
                                        onClick={createOrganization}
                                        disabled={!organizationForm.name}
                                    >
                                        Create Organization
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

export default ZendeskIntegration;
