/**
 * Intercom Integration Component
 * Customer communication and support platform integration
 */

import React, { useState, useEffect } from "react";
import {
    MessageSquare,
    Phone,
    Mail,
    Clock,
    Paperclip,
    Search,
    Users,
    Briefcase,
    Shield,
    TrendingUp,
    TrendingDown,
    Loader2,
    CheckCircle,
    AlertCircle,
    ArrowRight,
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

// Interfaces for Intercom data
interface IntercomContact {
    id: string;
    type: string;
    email: string;
    name?: string;
    phone?: string;
    role: string;
    created_at: string;
    updated_at: string;
    last_seen_at?: string;
    custom_attributes?: Record<string, any>;
    tags: string[];
    companies: Array<{ id: string; name: string }>;
}

interface IntercomConversation {
    id: string;
    type: string;
    created_at: string;
    updated_at: string;
    waiting_since?: string;
    snoozed_until?: string;
    source: Record<string, any>;
    contacts: Array<{ id: string; type: string }>;
    conversation_rating?: Record<string, any>;
    conversation_parts: Array<{
        id: string;
        type: string;
        part_type: string;
        body: string;
        author: { id: string; type: string };
        created_at: string;
    }>;
    tags: string[];
    assignee?: { id: string; type: string };
    open: boolean;
    read: boolean;
    priority: string;
}

interface IntercomTeam {
    id: string;
    type: string;
    name: string;
    admin_ids: string[];
    created_at: string;
    updated_at: string;
}

interface IntercomAdmin {
    id: string;
    type: string;
    name: string;
    email: string;
    job_title?: string;
    away_mode_enabled: boolean;
    away_mode_reassign: boolean;
    has_inbox_seat: boolean;
    team_ids: string[];
    created_at: string;
    updated_at: string;
}

interface IntercomStats {
    total_contacts: number;
    total_conversations: number;
    open_conversations: number;
    unassigned_conversations: number;
    team_count: number;
    admin_count: number;
    response_time_avg?: number;
    satisfaction_rating?: number;
}

const IntercomIntegration: React.FC = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [contacts, setContacts] = useState<IntercomContact[]>([]);
    const [conversations, setConversations] = useState<IntercomConversation[]>(
        []
    );
    const [teams, setTeams] = useState<IntercomTeam[]>([]);
    const [admins, setAdmins] = useState<IntercomAdmin[]>([]);
    const [stats, setStats] = useState<IntercomStats | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedContact, setSelectedContact] =
        useState<IntercomContact | null>(null);
    const [selectedConversation, setSelectedConversation] =
        useState<IntercomConversation | null>(null);
    const [messageText, setMessageText] = useState("");

    const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
    const [isContactModalOpen, setIsContactModalOpen] = useState(false);
    const [isConversationModalOpen, setIsConversationModalOpen] = useState(false);
    const [isMessageModalOpen, setIsMessageModalOpen] = useState(false);

    const { toast } = useToast();

    // Load initial data
    useEffect(() => {
        loadIntercomData();
    }, []);

    const loadIntercomData = async () => {
        try {
            setIsLoading(true);

            // Check connection status
            const healthResponse = await fetch("/api/v1/intercom/health");
            if (healthResponse.ok) {
                setIsConnected(true);

                // Load contacts
                const contactsResponse = await fetch(
                    "/api/v1/intercom/contacts?limit=50"
                );
                if (contactsResponse.ok) {
                    const contactsData = await contactsResponse.json();
                    setContacts(contactsData.data || []);
                }

                // Load conversations
                const conversationsResponse = await fetch(
                    "/api/v1/intercom/conversations?limit=50"
                );
                if (conversationsResponse.ok) {
                    const conversationsData = await conversationsResponse.json();
                    setConversations(conversationsData.data || []);
                }

                // Load teams
                const teamsResponse = await fetch("/api/v1/intercom/teams");
                if (teamsResponse.ok) {
                    const teamsData = await teamsResponse.json();
                    setTeams(teamsData.data || []);
                }

                // Load admins
                const adminsResponse = await fetch("/api/v1/intercom/admins");
                if (adminsResponse.ok) {
                    const adminsData = await adminsResponse.json();
                    setAdmins(adminsData.data || []);
                }

                // Load stats
                const statsResponse = await fetch("/api/v1/intercom/stats");
                if (statsResponse.ok) {
                    const statsData = await statsResponse.json();
                    setStats(statsData.data);
                }
            }
        } catch (error) {
            console.error("Failed to load Intercom data:", error);
            setIsConnected(false);
        } finally {
            setIsLoading(false);
        }
    };

    const handleConnect = async () => {
        try {
            setIsConnected(true);
            setIsConnectModalOpen(false);

            toast({
                title: "Intercom Connected",
                description: "Successfully connected to Intercom",
            });

            await loadIntercomData();
        } catch (error) {
            toast({
                title: "Connection Failed",
                description: "Failed to connect to Intercom",
                variant: "error",
            });
        }
    };

    const handleSearch = async () => {
        if (!searchQuery.trim()) return;

        try {
            const searchResponse = await fetch("/api/v1/intercom/search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    query: searchQuery,
                    type: "contact",
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

    const handleSendMessage = async () => {
        if (!selectedContact || !messageText.trim()) return;

        try {
            const messageResponse = await fetch("/api/v1/intercom/messages", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    contact_id: selectedContact.id,
                    message: messageText,
                    message_type: "comment",
                }),
            });

            if (messageResponse.ok) {
                toast({
                    title: "Message Sent",
                    description: "Message successfully sent to contact",
                });
                setMessageText("");
                setIsMessageModalOpen(false);
            }
        } catch (error) {
            toast({
                title: "Message Failed",
                description: "Failed to send message",
                variant: "error",
            });
        }
    };

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleDateString();
    };

    const getPriorityVariant = (priority: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (priority) {
            case "priority":
                return "destructive";
            case "not_priority":
                return "secondary";
            default:
                return "default";
        }
    };

    const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status) {
            case "open":
                return "default"; // Green-ish
            case "closed":
                return "destructive"; // Red-ish
            default:
                return "secondary";
        }
    };

    // Render connection status
    if (!isConnected && !isLoading) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
                    <div className="space-y-2">
                        <h2 className="text-2xl font-semibold">Connect Intercom</h2>
                        <p className="text-muted-foreground mb-6">
                            Connect your Intercom account to manage customer conversations,
                            contacts, and team collaboration.
                        </p>
                    </div>

                    <Card className="max-w-md w-full">
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center space-y-4">
                                <MessageSquare className="w-16 h-16 text-blue-500 mb-4" />
                                <h3 className="text-xl font-semibold">Intercom Integration</h3>
                                <p className="text-muted-foreground mt-2">
                                    Customer communication platform
                                </p>

                                <Button
                                    size="lg"
                                    className="w-full bg-blue-600 hover:bg-blue-700"
                                    onClick={() => setIsConnectModalOpen(true)}
                                >
                                    Connect Intercom
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Connect Modal */}
                <Dialog open={isConnectModalOpen} onOpenChange={setIsConnectModalOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Connect Intercom</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <p className="text-sm text-muted-foreground">
                                Connect your Intercom account to access customer conversations,
                                contacts, and team management features.
                            </p>
                            <Alert>
                                <AlertCircle className="h-4 w-4" />
                                <AlertTitle>OAuth 2.0 Required</AlertTitle>
                                <AlertDescription>
                                    You&apos;ll be redirected to Intercom to authorize access to your
                                    account.
                                </AlertDescription>
                            </Alert>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsConnectModalOpen(false)}>
                                Cancel
                            </Button>
                            <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleConnect}>
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
            <div className="flex flex-col items-center justify-center min-h-[60vh] p-6">
                <Loader2 className="w-12 h-12 animate-spin text-blue-500 mb-4" />
                <p className="text-lg text-muted-foreground">Loading Intercom data...</p>
            </div>
        );
    }

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex justify-between items-center">
                    <div className="flex flex-col space-y-1">
                        <h1 className="text-3xl font-bold">Intercom</h1>
                        <p className="text-lg text-muted-foreground">
                            Customer communication and support platform
                        </p>
                    </div>
                    <Button variant="outline" onClick={loadIntercomData}>
                        Refresh Data
                    </Button>
                </div>

                {/* Search Bar */}
                <Card>
                    <CardContent className="pt-6">
                        <div className="relative">
                            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search contacts, conversations..."
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
                        <TabsTrigger value="contacts">Contacts</TabsTrigger>
                        <TabsTrigger value="conversations">Conversations</TabsTrigger>
                        <TabsTrigger value="teams">Teams</TabsTrigger>
                        <TabsTrigger value="admins">Admins</TabsTrigger>
                    </TabsList>

                    {/* Dashboard Tab */}
                    <TabsContent value="dashboard" className="space-y-6 mt-6">
                        {stats && (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">Total Contacts</p>
                                            <div className="text-2xl font-bold">{stats.total_contacts}</div>
                                            <div className="flex items-center text-xs text-green-500">
                                                <TrendingUp className="w-3 h-3 mr-1" />
                                                23.36%
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">Open Conversations</p>
                                            <div className="text-2xl font-bold">{stats.open_conversations}</div>
                                            <div className="flex items-center text-xs text-green-500">
                                                <TrendingDown className="w-3 h-3 mr-1" />
                                                9.05%
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">Response Time</p>
                                            <div className="text-2xl font-bold">{stats.response_time_avg?.toFixed(1)}h</div>
                                            <div className="flex items-center text-xs text-red-500">
                                                <TrendingUp className="w-3 h-3 mr-1" />
                                                12.5%
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">Satisfaction</p>
                                            <div className="text-2xl font-bold">{stats.satisfaction_rating?.toFixed(1)}/5</div>
                                            <div className="flex items-center text-xs text-green-500">
                                                <TrendingUp className="w-3 h-3 mr-1" />
                                                5.2%
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>
                        )}
                    </TabsContent>

                    {/* Contacts Tab */}
                    <TabsContent value="contacts" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                                <CardTitle className="text-xl font-bold">Contacts ({contacts.length})</CardTitle>
                                <Button size="sm" className="bg-blue-600 hover:bg-blue-700">
                                    Add Contact
                                </Button>
                            </CardHeader>
                            <CardContent>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Email</TableHead>
                                            <TableHead>Phone</TableHead>
                                            <TableHead>Last Seen</TableHead>
                                            <TableHead>Tags</TableHead>
                                            <TableHead>Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {contacts.map((contact) => (
                                            <TableRow key={contact.id}>
                                                <TableCell className="font-medium">{contact.name || "Unknown"}</TableCell>
                                                <TableCell>{contact.email}</TableCell>
                                                <TableCell>{contact.phone || "-"}</TableCell>
                                                <TableCell>
                                                    {contact.last_seen_at
                                                        ? formatDate(contact.last_seen_at)
                                                        : "Never"}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex space-x-1">
                                                        {contact.tags.slice(0, 2).map((tag) => (
                                                            <Badge key={tag} variant="secondary" className="text-xs">
                                                                {tag}
                                                            </Badge>
                                                        ))}
                                                        {contact.tags.length > 2 && (
                                                            <Badge variant="outline" className="text-xs">
                                                                +{contact.tags.length - 2}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex space-x-2">
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => {
                                                                setSelectedContact(contact);
                                                                setIsContactModalOpen(true);
                                                            }}
                                                        >
                                                            View
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            className="text-green-600 hover:text-green-700 hover:bg-green-50"
                                                            onClick={() => {
                                                                setSelectedContact(contact);
                                                                setIsMessageModalOpen(true);
                                                            }}
                                                        >
                                                            Message
                                                        </Button>
                                                    </div>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Conversations Tab */}
                    <TabsContent value="conversations" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-xl font-bold">Conversations ({conversations.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>ID</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Priority</TableHead>
                                            <TableHead>Assignee</TableHead>
                                            <TableHead>Last Updated</TableHead>
                                            <TableHead>Tags</TableHead>
                                            <TableHead>Actions</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {conversations.map((conversation) => (
                                            <TableRow key={conversation.id}>
                                                <TableCell className="font-medium">
                                                    {conversation.id.slice(0, 8)}...
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={getStatusVariant(conversation.open ? "open" : "closed")}>
                                                        {conversation.open ? "Open" : "Closed"}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={getPriorityVariant(conversation.priority)}>
                                                        {conversation.priority}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>{conversation.assignee ? "Assigned" : "Unassigned"}</TableCell>
                                                <TableCell>{formatDate(conversation.updated_at)}</TableCell>
                                                <TableCell>
                                                    <div className="flex space-x-1">
                                                        {conversation.tags.slice(0, 2).map((tag) => (
                                                            <Badge key={tag} variant="secondary" className="text-xs">
                                                                {tag}
                                                            </Badge>
                                                        ))}
                                                        {conversation.tags.length > 2 && (
                                                            <Badge variant="outline" className="text-xs">
                                                                +{conversation.tags.length - 2}
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </TableCell>
                                                <TableCell>
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        onClick={() => {
                                                            setSelectedConversation(conversation);
                                                            setIsConversationModalOpen(true);
                                                        }}
                                                    >
                                                        View
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Teams Tab */}
                    <TabsContent value="teams" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-xl font-bold">Teams ({teams.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {teams.map((team) => (
                                        <Card key={team.id}>
                                            <CardContent className="pt-6">
                                                <div className="space-y-3">
                                                    <h3 className="font-bold text-lg">{team.name}</h3>
                                                    <p className="text-muted-foreground">
                                                        {team.admin_ids.length} admins
                                                    </p>
                                                    <p className="text-sm text-gray-500">
                                                        Created: {formatDate(team.created_at)}
                                                    </p>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Admins Tab */}
                    <TabsContent value="admins" className="space-y-6 mt-6">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-xl font-bold">Admins ({admins.length})</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead>Name</TableHead>
                                            <TableHead>Email</TableHead>
                                            <TableHead>Job Title</TableHead>
                                            <TableHead>Status</TableHead>
                                            <TableHead>Teams</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {admins.map((admin) => (
                                            <TableRow key={admin.id}>
                                                <TableCell className="font-medium">{admin.name}</TableCell>
                                                <TableCell>{admin.email}</TableCell>
                                                <TableCell>{admin.job_title || "Not specified"}</TableCell>
                                                <TableCell>
                                                    <Badge
                                                        variant={admin.away_mode_enabled ? "secondary" : "default"}
                                                        className={!admin.away_mode_enabled ? "bg-green-500 hover:bg-green-600" : ""}
                                                    >
                                                        {admin.away_mode_enabled ? "Away" : "Available"}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant="outline">
                                                        {admin.team_ids.length} teams
                                                    </Badge>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>

                {/* Contact Detail Modal */}
                <Dialog open={isContactModalOpen} onOpenChange={setIsContactModalOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Contact Details</DialogTitle>
                        </DialogHeader>
                        <div className="py-4">
                            {selectedContact && (
                                <div className="space-y-4">
                                    <div>
                                        <p className="font-bold text-sm">Name</p>
                                        <p>{selectedContact.name || "Unknown"}</p>
                                    </div>
                                    <div>
                                        <p className="font-bold text-sm">Email</p>
                                        <p>{selectedContact.email}</p>
                                    </div>
                                    {selectedContact.phone && (
                                        <div>
                                            <p className="font-bold text-sm">Phone</p>
                                            <p>{selectedContact.phone}</p>
                                        </div>
                                    )}
                                    <div>
                                        <p className="font-bold text-sm">Role</p>
                                        <Badge variant="secondary">{selectedContact.role}</Badge>
                                    </div>
                                    <div>
                                        <p className="font-bold text-sm">Last Seen</p>
                                        <p>
                                            {selectedContact.last_seen_at
                                                ? formatDate(selectedContact.last_seen_at)
                                                : "Never"}
                                        </p>
                                    </div>
                                    {selectedContact.tags.length > 0 && (
                                        <div>
                                            <p className="font-bold text-sm mb-2">Tags</p>
                                            <div className="flex flex-wrap gap-2">
                                                {selectedContact.tags.map((tag) => (
                                                    <Badge key={tag} variant="secondary">
                                                        {tag}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                    {selectedContact.companies.length > 0 && (
                                        <div>
                                            <p className="font-bold text-sm mb-2">Companies</p>
                                            <div className="space-y-1">
                                                {selectedContact.companies.map((company) => (
                                                    <p key={company.id} className="text-sm">{company.name}</p>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsContactModalOpen(false)}>
                                Close
                            </Button>
                            <Button
                                className="bg-green-600 hover:bg-green-700"
                                onClick={() => {
                                    setIsContactModalOpen(false);
                                    setIsMessageModalOpen(true);
                                }}
                            >
                                Send Message
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Conversation Detail Modal */}
                <Dialog open={isConversationModalOpen} onOpenChange={setIsConversationModalOpen}>
                    <DialogContent className="max-w-xl">
                        <DialogHeader>
                            <DialogTitle>Conversation Details</DialogTitle>
                        </DialogHeader>
                        <div className="py-4 max-h-[600px] overflow-y-auto">
                            {selectedConversation && (
                                <div className="space-y-4">
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <p className="font-bold text-sm">Conversation ID</p>
                                            <p className="text-sm text-muted-foreground">{selectedConversation.id}</p>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Status</p>
                                            <Badge variant={getStatusVariant(selectedConversation.open ? "open" : "closed")}>
                                                {selectedConversation.open ? "Open" : "Closed"}
                                            </Badge>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Priority</p>
                                            <Badge variant={getPriorityVariant(selectedConversation.priority)}>
                                                {selectedConversation.priority}
                                            </Badge>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Assignee</p>
                                            <p className="text-sm">{selectedConversation.assignee ? "Assigned" : "Unassigned"}</p>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Created</p>
                                            <p className="text-sm">{formatDate(selectedConversation.created_at)}</p>
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm">Last Updated</p>
                                            <p className="text-sm">{formatDate(selectedConversation.updated_at)}</p>
                                        </div>
                                    </div>

                                    {selectedConversation.tags.length > 0 && (
                                        <div>
                                            <p className="font-bold text-sm mb-2">Tags</p>
                                            <div className="flex flex-wrap gap-2">
                                                {selectedConversation.tags.map((tag) => (
                                                    <Badge key={tag} variant="secondary">
                                                        {tag}
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    <div className="pt-4 border-t">
                                        <p className="font-bold text-sm mb-3">Messages</p>
                                        <div className="space-y-3">
                                            {selectedConversation.conversation_parts.map((part) => (
                                                <div
                                                    key={part.id}
                                                    className="p-3 bg-muted rounded-md text-sm"
                                                >
                                                    <div className="flex justify-between text-xs text-muted-foreground mb-1">
                                                        <span>{part.author.type === "admin" ? "Agent" : "Customer"}</span>
                                                        <span>{formatDate(part.created_at)}</span>
                                                    </div>
                                                    <p>{part.body}</p>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button onClick={() => setIsConversationModalOpen(false)}>
                                Close
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Send Message Modal */}
                <Dialog open={isMessageModalOpen} onOpenChange={setIsMessageModalOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Send Message</DialogTitle>
                        </DialogHeader>
                        <div className="py-4 space-y-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Message</label>
                                <Textarea
                                    placeholder="Type your message here..."
                                    value={messageText}
                                    onChange={(e) => setMessageText(e.target.value)}
                                    rows={6}
                                />
                            </div>
                            {selectedContact && (
                                <p className="text-sm text-muted-foreground">
                                    To: {selectedContact.name || "Unknown"} ({selectedContact.email})
                                </p>
                            )}
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsMessageModalOpen(false)}>
                                Cancel
                            </Button>
                            <Button
                                className="bg-blue-600 hover:bg-blue-700"
                                onClick={handleSendMessage}
                                disabled={!messageText.trim()}
                            >
                                Send Message
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

export default IntercomIntegration;
