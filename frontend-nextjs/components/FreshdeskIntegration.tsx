/**
 * Freshdesk Integration Component
 * Customer support and help desk platform integration
 */

import React, { useState, useEffect } from "react";
import {
    Search,
    MessageSquare,
    Phone,
    Mail,
    Clock,
    Paperclip,
    CheckCircle,
    AlertTriangle,
    ArrowUp,
    ArrowDown,
    Loader2,
    Plus,
    Eye,
    User,
    Building,
    Users,
    Headphones,
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
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

// Interfaces for Freshdesk data
interface FreshdeskContact {
    id: number;
    name: string;
    email: string;
    phone?: string;
    mobile?: string;
    company_id?: number;
    job_title?: string;
    time_zone?: string;
    language?: string;
    created_at: string;
    updated_at: string;
    last_login_at?: string;
    active: boolean;
    custom_fields?: Record<string, any>;
}

interface FreshdeskTicket {
    id: number;
    subject: string;
    description: string;
    email: string;
    priority: number;
    status: number;
    source: number;
    type?: string;
    responder_id?: number;
    group_id?: number;
    company_id?: number;
    created_at: string;
    updated_at: string;
    due_by?: string;
    fr_due_by?: string;
    is_escalated: boolean;
    custom_fields?: Record<string, any>;
    tags: string[];
}

interface FreshdeskCompany {
    id: number;
    name: string;
    description?: string;
    note?: string;
    domains: string[];
    industry?: string;
    created_at: string;
    updated_at: string;
    custom_fields?: Record<string, any>;
}

interface FreshdeskAgent {
    id: number;
    email: string;
    name: string;
    available: boolean;
    available_since?: string;
    occasional: boolean;
    signature?: string;
    ticket_scope: number;
    group_ids: number[];
    role_ids: number[];
    created_at: string;
    updated_at: string;
    time_zone?: string;
    language?: string;
}

interface FreshdeskGroup {
    id: number;
    name: string;
    description?: string;
    escalated: boolean;
    agent_ids: number[];
    created_at: string;
    updated_at: string;
}

interface FreshdeskStats {
    total_tickets: number;
    open_tickets: number;
    pending_tickets: number;
    resolved_tickets: number;
    closed_tickets: number;
    total_contacts: number;
    total_companies: number;
    total_agents: number;
    total_groups: number;
    avg_first_response_time?: number;
    avg_resolution_time?: number;
    satisfaction_rating?: number;
}

const FreshdeskIntegration: React.FC = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [contacts, setContacts] = useState<FreshdeskContact[]>([]);
    const [tickets, setTickets] = useState<FreshdeskTicket[]>([]);
    const [companies, setCompanies] = useState<FreshdeskCompany[]>([]);
    const [agents, setAgents] = useState<FreshdeskAgent[]>([]);
    const [groups, setGroups] = useState<FreshdeskGroup[]>([]);
    const [stats, setStats] = useState<FreshdeskStats | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedTicket, setSelectedTicket] = useState<FreshdeskTicket | null>(
        null
    );
    const [selectedContact, setSelectedContact] =
        useState<FreshdeskContact | null>(null);
    const [apiKey, setApiKey] = useState("");
    const [domain, setDomain] = useState("");

    const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
    const [isTicketModalOpen, setIsTicketModalOpen] = useState(false);
    const [isContactModalOpen, setIsContactModalOpen] = useState(false);
    const [isCreateTicketModalOpen, setIsCreateTicketModalOpen] = useState(false);

    const { toast } = useToast();

    // Load initial data
    useEffect(() => {
        loadFreshdeskData();
    }, []);

    const loadFreshdeskData = async () => {
        try {
            setIsLoading(true);

            // Check connection status
            const healthResponse = await fetch("/api/v1/freshdesk/health");
            if (healthResponse.ok) {
                setIsConnected(true);

                // Load contacts
                const contactsResponse = await fetch(
                    "/api/v1/freshdesk/contacts?limit=50"
                );
                if (contactsResponse.ok) {
                    const contactsData = await contactsResponse.json();
                    setContacts(contactsData.data || []);
                }

                // Load tickets
                const ticketsResponse = await fetch(
                    "/api/v1/freshdesk/tickets?limit=50"
                );
                if (ticketsResponse.ok) {
                    const ticketsData = await ticketsResponse.json();
                    setTickets(ticketsData.data || []);
                }

                // Load companies
                const companiesResponse = await fetch("/api/v1/freshdesk/companies");
                if (companiesResponse.ok) {
                    const companiesData = await companiesResponse.json();
                    setCompanies(companiesData.data || []);
                }

                // Load agents
                const agentsResponse = await fetch("/api/v1/freshdesk/agents");
                if (agentsResponse.ok) {
                    const agentsData = await agentsResponse.json();
                    setAgents(agentsData.data || []);
                }

                // Load groups
                const groupsResponse = await fetch("/api/v1/freshdesk/groups");
                if (groupsResponse.ok) {
                    const groupsData = await groupsResponse.json();
                    setGroups(groupsData.data || []);
                }

                // Load stats
                const statsResponse = await fetch("/api/v1/freshdesk/stats");
                if (statsResponse.ok) {
                    const statsData = await statsResponse.json();
                    setStats(statsData.data);
                }
            }
        } catch (error) {
            console.error("Failed to load Freshdesk data:", error);
            setIsConnected(false);
        } finally {
            setIsLoading(false);
        }
    };

    const handleConnect = async () => {
        if (!apiKey.trim() || !domain.trim()) {
            toast({
                title: "Missing Credentials",
                description: "Please enter both API Key and Domain",
                variant: "destructive",
            });
            return;
        }

        try {
            const authResponse = await fetch("/api/v1/freshdesk/auth", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    api_key: apiKey,
                    domain: domain,
                }),
            });

            if (authResponse.ok) {
                setIsConnected(true);
                setIsConnectModalOpen(false);

                toast({
                    title: "Freshdesk Connected",
                    description: "Successfully connected to Freshdesk",
                });

                await loadFreshdeskData();
            } else {
                throw new Error("Authentication failed");
            }
        } catch (error) {
            toast({
                title: "Connection Failed",
                description: "Failed to connect to Freshdesk",
                variant: "destructive",
            });
        }
    };

    const handleSearch = async () => {
        if (!searchQuery.trim()) return;

        try {
            const searchResponse = await fetch("/api/v1/freshdesk/search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    query: searchQuery,
                    type: "ticket",
                    limit: 50,
                    offset: 0,
                }),
            });

            if (searchResponse.ok) {
                const searchData = await searchResponse.json();
                toast({
                    title: "Search Complete",
                    description: `Found ${searchData.data.total_count} results`,
                });
            }
        } catch (error) {
            console.error("Search failed:", error);
        }
    };

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleDateString();
    };

    const getStatusVariant = (status: number): "default" | "secondary" | "destructive" | "outline" => {
        switch (status) {
            case 2: // Open
                return "default"; // Green-ish usually
            case 3: // Pending
                return "secondary"; // Yellow-ish
            case 4: // Resolved
                return "outline"; // Blue-ish
            case 5: // Closed
                return "secondary"; // Gray-ish
            default:
                return "secondary";
        }
    };

    const getStatusText = (status: number): string => {
        switch (status) {
            case 2:
                return "Open";
            case 3:
                return "Pending";
            case 4:
                return "Resolved";
            case 5:
                return "Closed";
            default:
                return "Unknown";
        }
    };

    const getPriorityVariant = (priority: number): "default" | "secondary" | "destructive" | "outline" => {
        switch (priority) {
            case 1:
                return "secondary"; // Low
            case 2:
                return "outline"; // Medium
            case 3:
                return "default"; // High
            case 4:
                return "destructive"; // Urgent
            default:
                return "secondary";
        }
    };

    const getPriorityText = (priority: number): string => {
        switch (priority) {
            case 1:
                return "Low";
            case 2:
                return "Medium";
            case 3:
                return "High";
            case 4:
                return "Urgent";
            default:
                return "Unknown";
        }
    };

    // Render connection status
    if (!isConnected && !isLoading) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
                    <div className="space-y-2">
                        <h2 className="text-2xl font-semibold">Connect Freshdesk</h2>
                        <p className="text-muted-foreground mb-6">
                            Connect your Freshdesk account to manage customer support tickets,
                            contacts, and team collaboration.
                        </p>
                    </div>

                    <Card className="max-w-md w-full">
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center space-y-4">
                                <MessageSquare className="w-16 h-16 text-green-500 mb-4" />
                                <h3 className="text-xl font-semibold">Freshdesk Integration</h3>
                                <p className="text-muted-foreground mt-2">
                                    Customer support and help desk platform
                                </p>

                                <Button
                                    size="lg"
                                    className="w-full bg-green-600 hover:bg-green-700"
                                    onClick={() => setIsConnectModalOpen(true)}
                                >
                                    Connect Freshdesk
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Connect Modal */}
                <Dialog open={isConnectModalOpen} onOpenChange={setIsConnectModalOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Connect Freshdesk</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <p className="text-sm text-muted-foreground">
                                Connect your Freshdesk account using your API key and domain.
                            </p>

                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Freshdesk Domain</label>
                                <Input
                                    placeholder="your-domain"
                                    value={domain}
                                    onChange={(e) => setDomain(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    Your Freshdesk subdomain (e.g., &quot;company&quot; for
                                    company.freshdesk.com)
                                </p>
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">API Key</label>
                                <Input
                                    type="password"
                                    placeholder="Enter your API key"
                                    value={apiKey}
                                    onChange={(e) => setApiKey(e.target.value)}
                                />
                                <p className="text-xs text-muted-foreground">
                                    Find your API key in Freshdesk Admin settings
                                </p>
                            </div>

                            <Alert>
                                <AlertTriangle className="h-4 w-4" />
                                <AlertTitle>API Authentication</AlertTitle>
                                <AlertDescription>
                                    Freshdesk uses API key authentication for secure integration.
                                </AlertDescription>
                            </Alert>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsConnectModalOpen(false)}>
                                Cancel
                            </Button>
                            <Button className="bg-green-600 hover:bg-green-700" onClick={handleConnect}>
                                Connect
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="p-6 flex flex-col items-center justify-center min-h-[400px]">
                <Loader2 className="w-12 h-12 animate-spin text-green-500 mb-4" />
                <p className="text-muted-foreground">Loading Freshdesk data...</p>
            </div>
        );
    }

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex justify-between items-center">
                    <div className="flex items-center space-x-4">
                        <MessageSquare className="w-8 h-8 text-green-500" />
                        <div>
                            <h1 className="text-3xl font-bold">Freshdesk</h1>
                            <p className="text-lg text-muted-foreground">Customer support and help desk platform</p>
                        </div>
                    </div>
                    <Button className="bg-green-600 hover:bg-green-700" onClick={loadFreshdeskData}>
                        Refresh Data
                    </Button>
                </div>

                {/* Search Bar */}
                <Card>
                    <CardContent className="pt-6">
                        <div className="relative">
                            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search tickets, contacts..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyPress={(e) => e.key === "Enter" && handleSearch()}
                                className="pl-8"
                            />
                        </div>
                    </CardContent>
                </Card>

                {/* Main Content Tabs */}
                <Tabs defaultValue="dashboard">
                    <TabsList>
                        <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
                        <TabsTrigger value="tickets">Tickets</TabsTrigger>
                        <TabsTrigger value="contacts">Contacts</TabsTrigger>
                        <TabsTrigger value="companies">Companies</TabsTrigger>
                        <TabsTrigger value="agents">Agents</TabsTrigger>
                        <TabsTrigger value="groups">Groups</TabsTrigger>
                    </TabsList>

                    {/* Dashboard Tab */}
                    <TabsContent value="dashboard" className="space-y-6 mt-6">
                        {stats && (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">Total Tickets</p>
                                            <div className="text-2xl font-bold">{stats.total_tickets}</div>
                                            <p className="text-xs text-green-500 flex items-center">
                                                <ArrowUp className="w-3 h-3 mr-1" />
                                                15.2%
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">Open Tickets</p>
                                            <div className="text-2xl font-bold">{stats.open_tickets}</div>
                                            <p className="text-xs text-green-500 flex items-center">
                                                <ArrowDown className="w-3 h-3 mr-1" />
                                                8.1%
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">Response Time</p>
                                            <div className="text-2xl font-bold">{stats.avg_first_response_time?.toFixed(1)}h</div>
                                            <p className="text-xs text-green-500 flex items-center">
                                                <ArrowDown className="w-3 h-3 mr-1" />
                                                12.5%
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">Satisfaction</p>
                                            <div className="text-2xl font-bold">{stats.satisfaction_rating?.toFixed(1)}/5</div>
                                            <p className="text-xs text-green-500 flex items-center">
                                                <ArrowUp className="w-3 h-3 mr-1" />
                                                3.7%
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        )}
                    </TabsContent>

                    {/* Tickets Tab */}
                    <TabsContent value="tickets" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <div className="flex justify-between items-center">
                                    <CardTitle>Tickets ({tickets.length})</CardTitle>
                                    <Button
                                        className="bg-green-600 hover:bg-green-700"
                                        size="sm"
                                        onClick={() => setIsCreateTicketModalOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Ticket
                                    </Button>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>ID</TableHead>
                                            <TableHead>Subject</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Priority</TableHead>
                                            <TableHead>Type</TableHead>
                                            <TableHead>Created</TableHead>
                                            <TableHead>Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {tickets.map((ticket) => (
                                            <TableRow key={ticket.id}>
                                                <TableCell className="font-medium">#{ticket.id}</TableCell>
                                                <TableCell>{ticket.subject}</TableCell>
                                                <TableCell>
                                                    <Badge variant={getStatusVariant(ticket.status)}>
                                                        {getStatusText(ticket.status)}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={getPriorityVariant(ticket.priority)}>
                                                        {getPriorityText(ticket.priority)}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>{ticket.type || "General"}</TableCell>
                                                <TableCell>{formatDate(ticket.created_at)}</TableCell>
                                                <TableCell>
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => {
                                                            setSelectedTicket(ticket);
                                                            setIsTicketModalOpen(true);
                                                        }}
                                                    >
                                                        <Eye className="w-4 h-4" />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Contacts Tab */}
                    <TabsContent value="contacts" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Contacts ({contacts.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Email</TableHead>
                                            <TableHead>Phone</TableHead>
                                            <TableHead>Company</TableHead>
                                            <TableHead>Last Login</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {contacts.map((contact) => (
                                            <TableRow key={contact.id}>
                                                <TableCell className="font-medium">{contact.name}</TableCell>
                                                <TableCell>{contact.email}</TableCell>
                                                <TableCell>{contact.phone || "-"}</TableCell>
                                                <TableCell>
                                                    {contact.company_id
                                                        ? `Company ${contact.company_id}`
                                                        : "-"}
                                                </TableCell>
                                                <TableCell>
                                                    {contact.last_login_at
                                                        ? formatDate(contact.last_login_at)
                                                        : "Never"}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={contact.active ? "default" : "destructive"}>
                                                        {contact.active ? "Active" : "Inactive"}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => {
                                                            setSelectedContact(contact);
                                                            setIsContactModalOpen(true);
                                                        }}
                                                    >
                                                        <Eye className="w-4 h-4" />
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Companies Tab */}
                    <TabsContent value="companies" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Companies ({companies.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {companies.map((company) => (
                                        <Card key={company.id}>
                                            <CardContent className="pt-6">
                                                <div className="space-y-3">
                                                    <div className="flex items-center space-x-2">
                                                        <Building className="w-5 h-5 text-gray-500" />
                                                        <h3 className="font-semibold">{company.name}</h3>
                                                    </div>
                                                    <p className="text-sm text-muted-foreground">
                                                        {company.description || "No description"}
                                                    </p>
                                                    <div className="text-sm">
                                                        <span className="font-medium">Domains:</span> {company.domains.join(", ")}
                                                    </div>
                                                    <div className="text-sm">
                                                        <span className="font-medium">Industry:</span>{" "}
                                                        {company.industry || "Not specified"}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        Created: {formatDate(company.created_at)}
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Agents Tab */}
                    <TabsContent value="agents" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Agents ({agents.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Email</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Groups</TableHead>
                                            <TableHead>Created</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {agents.map((agent) => (
                                            <TableRow key={agent.id}>
                                                <TableCell className="font-medium flex items-center">
                                                    <User className="w-4 h-4 mr-2 text-gray-500" />
                                                    {agent.name}
                                                </TableCell>
                                                <TableCell>{agent.email}</TableCell>
                                                <TableCell>
                                                    <Badge variant={agent.available ? "default" : "secondary"}>
                                                        {agent.available ? "Available" : "Away"}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="outline">
                                                        {agent.group_ids.length} groups
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>{formatDate(agent.created_at)}</TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Groups Tab */}
                    <TabsContent value="groups" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle>Groups ({groups.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {groups.map((group) => (
                                        <Card key={group.id}>
                                            <CardContent className="pt-6">
                                                <div className="space-y-3">
                                                    <div className="flex items-center space-x-2">
                                                        <Users className="w-5 h-5 text-gray-500" />
                                                        <h3 className="font-semibold">{group.name}</h3>
                                                    </div>
                                                    <p className="text-sm text-muted-foreground">
                                                        {group.description || "No description"}
                                                    </p>
                                                    <Badge variant={group.escalated ? "destructive" : "secondary"}>
                                                        {group.escalated ? "Escalated" : "Normal"}
                                                    </Badge>
                                                    <div className="text-sm">
                                                        <span className="font-medium">Agents:</span> {group.agent_ids.length}
                                                    </div>
                                                    <div className="text-xs text-muted-foreground">
                                                        Created: {formatDate(group.created_at)}
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>

                {/* Ticket Detail Modal */}
                <Dialog open={isTicketModalOpen} onOpenChange={setIsTicketModalOpen}>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Ticket Details</DialogTitle>
                        </DialogHeader>
                        <div className="py-4">
                            {selectedTicket && (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <p className="font-bold text-sm">Ticket ID</p>
                                            <p>#{selectedTicket.id}</p>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Status</p>
                                            <Badge variant={getStatusVariant(selectedTicket.status)}>
                                                {getStatusText(selectedTicket.status)}
                                            </Badge>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Priority</p>
                                            <Badge variant={getPriorityVariant(selectedTicket.priority)}>
                                                {getPriorityText(selectedTicket.priority)}
                                            </Badge>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Type</p>
                                            <p>{selectedTicket.type || "General"}</p>
                                        </div>
                                    </div>

                                    <div>
                                        <p className="font-bold text-sm">Subject</p>
                                        <p className="text-lg">{selectedTicket.subject}</p>
                                    </div>

                                    <div className="bg-muted p-4 rounded-md">
                                        <p className="font-bold text-sm mb-2">Description</p>
                                        <p className="text-sm whitespace-pre-wrap">{selectedTicket.description}</p>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4 text-sm text-muted-foreground">
                                        <div>
                                            <p>Created: {formatDate(selectedTicket.created_at)}</p>
                                        </div>
                                        <div>
                                            <p>Updated: {formatDate(selectedTicket.updated_at)}</p>
                                        </div>
                                    </div>

                                    {selectedTicket.tags.length > 0 && (
                                        <div>
                                            <p className="font-bold text-sm mb-2">Tags</p>
                                            <div className="flex flex-wrap gap-2">
                                                {selectedTicket.tags.map((tag) => (
                                                    <Badge key={tag} variant="secondary">
                                                        {tag}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {selectedTicket.is_escalated && (
                                        <Alert variant="destructive">
                                            <AlertTriangle className="h-4 w-4" />
                                            <AlertTitle>Escalated</AlertTitle>
                                            <AlertDescription>
                                                This ticket has been escalated
                                            </AlertDescription>
                                        </Alert>
                                    )}
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button className="bg-green-600 hover:bg-green-700" onClick={() => setIsTicketModalOpen(false)}>
                                Close
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Contact Detail Modal */}
                <Dialog open={isContactModalOpen} onOpenChange={setIsContactModalOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Contact Details</DialogTitle>
                        </DialogHeader>
                        <div className="py-4">
                            {selectedContact && (
                                <div className="space-y-4">
                                    <div className="flex items-center space-x-4">
                                        <div className="h-12 w-12 rounded-full bg-gray-200 flex items-center justify-center text-xl font-bold text-gray-600">
                                            {selectedContact.name.charAt(0)}
                                        </div>
                                        <div>
                                            <h3 className="text-lg font-bold">{selectedContact.name}</h3>
                                            <p className="text-muted-foreground">{selectedContact.email}</p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        {selectedContact.phone && (
                                            <div>
                                                <p className="font-bold text-sm">Phone</p>
                                                <p>{selectedContact.phone}</p>
                                            </div>
                                        )}
                                        {selectedContact.mobile && (
                                            <div>
                                                <p className="font-bold text-sm">Mobile</p>
                                                <p>{selectedContact.mobile}</p>
                                            </div>
                                        )}
                                        {selectedContact.job_title && (
                                            <div>
                                                <p className="font-bold text-sm">Job Title</p>
                                                <p>{selectedContact.job_title}</p>
                                            </div>
                                        )}
                                        <div>
                                            <p className="font-bold text-sm">Status</p>
                                            <Badge variant={selectedContact.active ? "default" : "destructive"}>
                                                {selectedContact.active ? "Active" : "Inactive"}
                                            </Badge>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Last Login</p>
                                            <p>
                                                {selectedContact.last_login_at
                                                    ? formatDate(selectedContact.last_login_at)
                                                    : "Never"}
                                            </p>
                                        </div>
                                        {selectedContact.time_zone && (
                                            <div>
                                                <p className="font-bold text-sm">Time Zone</p>
                                                <p>{selectedContact.time_zone}</p>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button className="bg-green-600 hover:bg-green-700" onClick={() => setIsContactModalOpen(false)}>
                                Close
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Create Ticket Modal */}
                <Dialog open={isCreateTicketModalOpen} onOpenChange={setIsCreateTicketModalOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Create New Ticket</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Subject</label>
                                <Input placeholder="Enter ticket subject" />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Description</label>
                                <Textarea placeholder="Enter detailed description" rows={6} />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Priority</label>
                                <Select>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select priority" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="1">Low</SelectItem>
                                        <SelectItem value="2">Medium</SelectItem>
                                        <SelectItem value="3">High</SelectItem>
                                        <SelectItem value="4">Urgent</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Type</label>
                                <Select>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select type" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="Question">Question</SelectItem>
                                        <SelectItem value="Incident">Incident</SelectItem>
                                        <SelectItem value="Problem">Problem</SelectItem>
                                        <SelectItem value="Feature Request">Feature Request</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsCreateTicketModalOpen(false)}>
                                Cancel
                            </Button>
                            <Button className="bg-green-600 hover:bg-green-700">Create Ticket</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

export default FreshdeskIntegration;
