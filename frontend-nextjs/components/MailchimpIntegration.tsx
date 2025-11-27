/**
 * Mailchimp Integration Component
 * Email marketing and automation platform integration
 */

import React, { useState, useEffect } from "react";
import {
    Mail,
    Search,
    RefreshCw,
    Users,
    BarChart2,
    Send,
    FileText,
    Settings,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Loader2,
    ExternalLink,
    Star,
    Clock,
    TrendingUp,
    MousePointer,
    DollarSign,
    UserPlus,
    UserMinus,
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

// Interfaces for Mailchimp data
interface MailchimpAudience {
    id: string;
    name: string;
    member_count: number;
    unsubscribe_count: number;
    created_at: string;
    updated_at: string;
    contact: Record<string, any>;
    permission_reminder: string;
    campaign_defaults: Record<string, any>;
    stats?: Record<string, any>;
}

interface MailchimpContact {
    id: string;
    email_address: string;
    status: string;
    full_name?: string;
    first_name?: string;
    last_name?: string;
    merge_fields?: Record<string, any>;
    stats?: Record<string, any>;
    ip_signup?: string;
    timestamp_signup?: string;
    ip_opt?: string;
    timestamp_opt?: string;
    member_rating: number;
    last_changed?: string;
    language?: string;
    vip: boolean;
    email_client?: string;
    tags: string[];
}

interface MailchimpCampaign {
    id: string;
    type: string;
    create_time: string;
    archive_url?: string;
    long_archive_url?: string;
    status: string;
    emails_sent: number;
    send_time?: string;
    content_type: string;
    recipients: Record<string, any>;
    settings: Record<string, any>;
    tracking: Record<string, any>;
    report_summary?: Record<string, any>;
}

interface MailchimpAutomation {
    id: string;
    create_time: string;
    start_time?: string;
    status: string;
    emails_sent: number;
    recipients: Record<string, any>;
    settings: Record<string, any>;
    tracking: Record<string, any>;
    trigger_settings: Record<string, any>;
    report_summary?: Record<string, any>;
}

interface MailchimpTemplate {
    id: number;
    type: string;
    name: string;
    drag_and_drop: boolean;
    responsive: boolean;
    category?: string;
    date_created: string;
    date_edited?: string;
    created_by: string;
    edited_by?: string;
    active: boolean;
    folder_id?: string;
}

interface MailchimpStats {
    total_audiences: number;
    total_contacts: number;
    total_campaigns: number;
    total_automations: number;
    active_campaigns: number;
    open_rate?: number;
    click_rate?: number;
    bounce_rate?: number;
    unsubscribe_rate?: number;
    revenue?: number;
}

const MailchimpIntegration: React.FC = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [audiences, setAudiences] = useState<MailchimpAudience[]>([]);
    const [contacts, setContacts] = useState<MailchimpContact[]>([]);
    const [campaigns, setCampaigns] = useState<MailchimpCampaign[]>([]);
    const [automations, setAutomations] = useState<MailchimpAutomation[]>([]);
    const [templates, setTemplates] = useState<MailchimpTemplate[]>([]);
    const [stats, setStats] = useState<MailchimpStats | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedAudience, setSelectedAudience] =
        useState<MailchimpAudience | null>(null);
    const [selectedCampaign, setSelectedCampaign] =
        useState<MailchimpCampaign | null>(null);
    const [selectedContact, setSelectedContact] =
        useState<MailchimpContact | null>(null);
    const [apiKey, setApiKey] = useState("");
    const [serverPrefix, setServerPrefix] = useState("");

    const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
    const [isAudienceModalOpen, setIsAudienceModalOpen] = useState(false);
    const [isCampaignModalOpen, setIsCampaignModalOpen] = useState(false);
    const [isContactModalOpen, setIsContactModalOpen] = useState(false);
    const [isCreateCampaignModalOpen, setIsCreateCampaignModalOpen] = useState(false);
    const [isCreateContactModalOpen, setIsCreateContactModalOpen] = useState(false);

    const { toast } = useToast();

    // Load initial data
    useEffect(() => {
        loadMailchimpData();
    }, []);

    const loadMailchimpData = async () => {
        try {
            setIsLoading(true);

            // Check connection status
            const healthResponse = await fetch("/api/v1/mailchimp/health");
            if (healthResponse.ok) {
                setIsConnected(true);

                // Load audiences
                const audiencesResponse = await fetch(
                    "/api/v1/mailchimp/audiences?limit=50",
                );
                if (audiencesResponse.ok) {
                    const audiencesData = await audiencesResponse.json();
                    setAudiences(audiencesData.data || []);
                }

                // Load campaigns
                const campaignsResponse = await fetch(
                    "/api/v1/mailchimp/campaigns?limit=50",
                );
                if (campaignsResponse.ok) {
                    const campaignsData = await campaignsResponse.json();
                    setCampaigns(campaignsData.data || []);
                }

                // Load automations
                const automationsResponse = await fetch(
                    "/api/v1/mailchimp/automations",
                );
                if (automationsResponse.ok) {
                    const automationsData = await automationsResponse.json();
                    setAutomations(automationsData.data || []);
                }

                // Load templates
                const templatesResponse = await fetch("/api/v1/mailchimp/templates");
                if (templatesResponse.ok) {
                    const templatesData = await templatesResponse.json();
                    setTemplates(templatesData.data || []);
                }

                // Load stats
                const statsResponse = await fetch("/api/v1/mailchimp/stats");
                if (statsResponse.ok) {
                    const statsData = await statsResponse.json();
                    setStats(statsData.data);
                }
            }
        } catch (error) {
            console.error("Failed to load Mailchimp data:", error);
            setIsConnected(false);
        } finally {
            setIsLoading(false);
        }
    };

    const handleConnect = async () => {
        if (!apiKey.trim() || !serverPrefix.trim()) {
            toast({
                title: "Missing Credentials",
                description: "Please enter both API Key and Server Prefix",
                variant: "destructive",
            });
            return;
        }

        try {
            const authResponse = await fetch("/api/v1/mailchimp/auth", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    api_key: apiKey,
                    server_prefix: serverPrefix,
                }),
            });

            if (authResponse.ok) {
                setIsConnected(true);
                setIsConnectModalOpen(false);

                toast({
                    title: "Mailchimp Connected",
                    description: "Successfully connected to Mailchimp",
                });

                await loadMailchimpData();
            } else {
                throw new Error("Authentication failed");
            }
        } catch (error) {
            toast({
                title: "Connection Failed",
                description: "Failed to connect to Mailchimp",
                variant: "destructive",
            });
        }
    };

    const handleSearch = async () => {
        if (!searchQuery.trim()) return;

        try {
            const searchResponse = await fetch("/api/v1/mailchimp/search", {
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

    const loadAudienceContacts = async (audienceId: string) => {
        try {
            const contactsResponse = await fetch(
                `/api/v1/mailchimp/contacts?audience_id=${audienceId}&limit=50`,
            );
            if (contactsResponse.ok) {
                const contactsData = await contactsResponse.json();
                setContacts(contactsData.data || []);
            }
        } catch (error) {
            console.error("Failed to load contacts:", error);
        }
    };

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleDateString();
    };

    const formatNumber = (num: number): string => {
        return num.toLocaleString();
    };

    const formatPercentage = (num: number): string => {
        return `${(num * 100).toFixed(1)}%`;
    };

    const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status) {
            case "sent":
                return "default"; // green-ish
            case "scheduled":
                return "outline"; // blue-ish
            case "sending":
                return "secondary"; // orange-ish
            case "draft":
                return "secondary"; // gray-ish
            case "paused":
                return "destructive"; // yellow-ish mapped to destructive for visibility or custom
            default:
                return "outline";
        }
    };

    const getContactStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status) {
            case "subscribed":
                return "default"; // green-ish
            case "unsubscribed":
                return "destructive"; // red-ish
            case "cleaned":
                return "outline"; // gray-ish
            case "pending":
                return "secondary"; // yellow-ish
            default:
                return "outline";
        }
    };

    // Render connection status
    if (!isConnected && !isLoading) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6">
                    <div className="text-center space-y-2">
                        <h2 className="text-2xl font-bold">Connect Mailchimp</h2>
                        <p className="text-muted-foreground max-w-md">
                            Connect your Mailchimp account to manage email marketing
                            campaigns, audiences, and automations.
                        </p>
                    </div>

                    <Card className="w-full max-w-md">
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center space-y-4">
                                <div className="p-3 bg-blue-100 rounded-full">
                                    <Mail className="w-8 h-8 text-blue-600" />
                                </div>
                                <div className="text-center">
                                    <h3 className="text-lg font-bold">Mailchimp Integration</h3>
                                    <p className="text-sm text-muted-foreground">
                                        Email marketing and automation platform
                                    </p>
                                </div>

                                <Button
                                    size="lg"
                                    className="w-full bg-blue-600 hover:bg-blue-700"
                                    onClick={() => setIsConnectModalOpen(true)}
                                >
                                    Connect Mailchimp
                                </Button>
                            </div>
                        </CardContent>
                    </Card>

                    {/* Connect Modal */}
                    <Dialog open={isConnectModalOpen} onOpenChange={setIsConnectModalOpen}>
                        <DialogContent>
                            <DialogHeader>
                                <DialogTitle>Connect Mailchimp</DialogTitle>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <p className="text-sm text-muted-foreground">
                                    Connect your Mailchimp account using your API key and server
                                    prefix.
                                </p>

                                <div className="space-y-2">
                                    <label className="text-sm font-medium leading-none">Server Prefix</label>
                                    <Input
                                        placeholder="us1"
                                        value={serverPrefix}
                                        onChange={(e) => setServerPrefix(e.target.value)}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Your Mailchimp server prefix (e.g., &quot;us1&quot; for accounts in the US)
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
                                        Find your API key in Mailchimp Account settings
                                    </p>
                                </div>

                                <div className="bg-blue-50 p-4 rounded-md flex items-start space-x-2">
                                    <AlertTriangle className="w-5 h-5 text-blue-600 mt-0.5" />
                                    <div className="text-sm text-blue-800">
                                        <p className="font-medium">API Authentication</p>
                                        <p>Mailchimp uses API key authentication with server-specific endpoints.</p>
                                    </div>
                                </div>
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
            </div>
        );
    }

    if (isLoading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-[60vh]">
                <Loader2 className="w-12 h-12 animate-spin text-blue-500" />
                <p className="mt-4 text-muted-foreground">Loading Mailchimp data...</p>
            </div>
        );
    }

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                    <div className="flex items-center space-x-4">
                        <div className="p-2 bg-yellow-400 rounded-lg">
                            <Mail className="w-8 h-8 text-black" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold">Mailchimp</h1>
                            <p className="text-lg text-muted-foreground">
                                Email marketing and automation platform
                            </p>
                        </div>
                    </div>
                    <Button variant="outline" onClick={loadMailchimpData}>
                        <RefreshCw className="mr-2 w-4 h-4" />
                        Refresh Data
                    </Button>
                </div>

                {/* Search Bar */}
                <div className="relative">
                    <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                        placeholder="Search campaigns, contacts..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        onKeyPress={(e) => e.key === "Enter" && handleSearch()}
                        className="pl-10 h-12 text-lg"
                    />
                </div>

                {/* Main Content Tabs */}
                <Tabs defaultValue="dashboard" className="space-y-6">
                    <TabsList>
                        <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
                        <TabsTrigger value="audiences">Audiences</TabsTrigger>
                        <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
                        <TabsTrigger value="automations">Automations</TabsTrigger>
                        <TabsTrigger value="templates">Templates</TabsTrigger>
                        <TabsTrigger value="contacts">Contacts</TabsTrigger>
                    </TabsList>

                    {/* Dashboard Tab */}
                    <TabsContent value="dashboard" className="space-y-6">
                        {stats && (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="flex items-center justify-between space-y-0 pb-2">
                                            <p className="text-sm font-medium text-muted-foreground">Total Contacts</p>
                                            <Users className="h-4 w-4 text-muted-foreground" />
                                        </div>
                                        <div className="text-2xl font-bold">{formatNumber(stats.total_contacts)}</div>
                                        <p className="text-xs text-muted-foreground flex items-center mt-1">
                                            <TrendingUp className="w-3 h-3 text-green-500 mr-1" />
                                            <span className="text-green-500 font-medium">8.2%</span>
                                            <span className="ml-1">from last month</span>
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="flex items-center justify-between space-y-0 pb-2">
                                            <p className="text-sm font-medium text-muted-foreground">Open Rate</p>
                                            <Eye className="h-4 w-4 text-muted-foreground" />
                                        </div>
                                        <div className="text-2xl font-bold">{formatPercentage(stats.open_rate || 0)}</div>
                                        <p className="text-xs text-muted-foreground flex items-center mt-1">
                                            <TrendingUp className="w-3 h-3 text-green-500 mr-1" />
                                            <span className="text-green-500 font-medium">2.1%</span>
                                            <span className="ml-1">from last month</span>
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="flex items-center justify-between space-y-0 pb-2">
                                            <p className="text-sm font-medium text-muted-foreground">Click Rate</p>
                                            <MousePointer className="h-4 w-4 text-muted-foreground" />
                                        </div>
                                        <div className="text-2xl font-bold">{formatPercentage(stats.click_rate || 0)}</div>
                                        <p className="text-xs text-muted-foreground flex items-center mt-1">
                                            <TrendingUp className="w-3 h-3 text-green-500 mr-1" />
                                            <span className="text-green-500 font-medium">1.5%</span>
                                            <span className="ml-1">from last month</span>
                                        </p>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="flex items-center justify-between space-y-0 pb-2">
                                            <p className="text-sm font-medium text-muted-foreground">Revenue</p>
                                            <DollarSign className="h-4 w-4 text-muted-foreground" />
                                        </div>
                                        <div className="text-2xl font-bold">${(stats.revenue || 0).toLocaleString()}</div>
                                        <p className="text-xs text-muted-foreground flex items-center mt-1">
                                            <TrendingUp className="w-3 h-3 text-green-500 mr-1" />
                                            <span className="text-green-500 font-medium">12.8%</span>
                                            <span className="ml-1">from last month</span>
                                        </p>
                                    </CardContent>
                                </Card>
                            </div>
                        )}
                    </TabsContent>

                    {/* Audiences Tab */}
                    <TabsContent value="audiences" className="space-y-6">
                        <div className="flex justify-between items-center">
                            <h2 className="text-xl font-bold">Audiences ({audiences.length})</h2>
                            <Button onClick={() => setIsCreateCampaignModalOpen(true)}>
                                <Plus className="mr-2 w-4 h-4" />
                                Create Campaign
                            </Button>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {audiences.map((audience) => (
                                <Card key={audience.id}>
                                    <CardHeader>
                                        <CardTitle className="text-lg">{audience.name}</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <p className="text-sm text-muted-foreground line-clamp-2">
                                            {audience.permission_reminder}
                                        </p>
                                        <div className="flex space-x-2">
                                            <Badge variant="secondary" className="bg-green-100 text-green-800 hover:bg-green-200">
                                                <UserPlus className="w-3 h-3 mr-1" />
                                                {formatNumber(audience.member_count)} members
                                            </Badge>
                                            <Badge variant="secondary" className="bg-red-100 text-red-800 hover:bg-red-200">
                                                <UserMinus className="w-3 h-3 mr-1" />
                                                {formatNumber(audience.unsubscribe_count)} unsubscribed
                                            </Badge>
                                        </div>
                                        {audience.stats && (
                                            <div className="grid grid-cols-2 gap-2 pt-2 border-t">
                                                <div className="text-sm">
                                                    <span className="text-muted-foreground">Open Rate:</span>
                                                    <div className="font-medium">{formatPercentage(audience.stats.open_rate || 0)}</div>
                                                </div>
                                                <div className="text-sm">
                                                    <span className="text-muted-foreground">Click Rate:</span>
                                                    <div className="font-medium">{formatPercentage(audience.stats.click_rate || 0)}</div>
                                                </div>
                                            </div>
                                        )}
                                        <div className="flex space-x-2 pt-2">
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="flex-1"
                                                onClick={() => {
                                                    setSelectedAudience(audience);
                                                    setIsAudienceModalOpen(true);
                                                }}
                                            >
                                                Details
                                            </Button>
                                            <Button
                                                variant="outline"
                                                size="sm"
                                                className="flex-1"
                                                onClick={() => {
                                                    setSelectedAudience(audience);
                                                    loadAudienceContacts(audience.id);
                                                    // Note: In a real app, we'd switch tabs here programmatically
                                                    // For now we'll just load the data
                                                    toast({
                                                        title: "Contacts Loaded",
                                                        description: `Loaded contacts for ${audience.name}. Switch to Contacts tab to view.`,
                                                    });
                                                }}
                                            >
                                                Load Contacts
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>

                    {/* Campaigns Tab */}
                    <TabsContent value="campaigns" className="space-y-6">
                        <Card>
                            <CardContent className="p-0">
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm text-left">
                                        <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                                            <tr>
                                                <th className="px-6 py-3">Name</th>
                                                <th className="px-6 py-3">Status</th>
                                                <th className="px-6 py-3">Type</th>
                                                <th className="px-6 py-3">Recipients</th>
                                                <th className="px-6 py-3">Emails Sent</th>
                                                <th className="px-6 py-3">Open Rate</th>
                                                <th className="px-6 py-3">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {campaigns.map((campaign) => (
                                                <tr key={campaign.id} className="bg-white border-b hover:bg-gray-50">
                                                    <td className="px-6 py-4 font-medium text-gray-900">
                                                        {campaign.settings.subject_line}
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <Badge variant={getStatusVariant(campaign.status)}>
                                                            {campaign.status}
                                                        </Badge>
                                                    </td>
                                                    <td className="px-6 py-4">{campaign.type}</td>
                                                    <td className="px-6 py-4">{campaign.recipients.list_name}</td>
                                                    <td className="px-6 py-4">{formatNumber(campaign.emails_sent)}</td>
                                                    <td className="px-6 py-4">
                                                        {campaign.report_summary
                                                            ? formatPercentage(campaign.report_summary.open_rate)
                                                            : "N/A"}
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => {
                                                                setSelectedCampaign(campaign);
                                                                setIsCampaignModalOpen(true);
                                                            }}
                                                        >
                                                            <Eye className="w-4 h-4" />
                                                        </Button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Automations Tab */}
                    <TabsContent value="automations" className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {automations.map((automation) => (
                                <Card key={automation.id}>
                                    <CardHeader>
                                        <div className="flex justify-between items-start">
                                            <CardTitle className="text-lg">{automation.settings.title}</CardTitle>
                                            <Badge variant={getStatusVariant(automation.status)}>
                                                {automation.status}
                                            </Badge>
                                        </div>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <p className="text-sm text-muted-foreground">
                                            List: {automation.recipients.list_name}
                                        </p>
                                        <div className="grid grid-cols-3 gap-4 border-t border-b py-4">
                                            <div className="text-center">
                                                <div className="text-2xl font-bold">{formatNumber(automation.emails_sent)}</div>
                                                <div className="text-xs text-muted-foreground">Sent</div>
                                            </div>
                                            <div className="text-center">
                                                <div className="text-2xl font-bold">
                                                    {automation.report_summary ? formatPercentage(automation.report_summary.open_rate || 0) : "0%"}
                                                </div>
                                                <div className="text-xs text-muted-foreground">Open Rate</div>
                                            </div>
                                            <div className="text-center">
                                                <div className="text-2xl font-bold">
                                                    {automation.report_summary ? formatPercentage(automation.report_summary.click_rate || 0) : "0%"}
                                                </div>
                                                <div className="text-xs text-muted-foreground">Click Rate</div>
                                            </div>
                                        </div>
                                        <p className="text-xs text-muted-foreground text-right">
                                            Created: {formatDate(automation.create_time)}
                                        </p>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>

                    {/* Templates Tab */}
                    <TabsContent value="templates" className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {templates.map((template) => (
                                <Card key={template.id}>
                                    <CardHeader>
                                        <CardTitle className="text-lg">{template.name}</CardTitle>
                                        <p className="text-sm text-muted-foreground">{template.category || "General"}</p>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <div className="flex flex-wrap gap-2">
                                            <Badge variant="outline">
                                                {template.drag_and_drop ? "Drag & Drop" : "Code"}
                                            </Badge>
                                            <Badge variant="outline">
                                                {template.responsive ? "Responsive" : "Fixed"}
                                            </Badge>
                                            <Badge variant={template.active ? "default" : "destructive"}>
                                                {template.active ? "Active" : "Inactive"}
                                            </Badge>
                                        </div>
                                        <div className="text-xs text-muted-foreground space-y-1 pt-2">
                                            <p>Created: {formatDate(template.date_created)}</p>
                                            {template.date_edited && (
                                                <p>Edited: {formatDate(template.date_edited)}</p>
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    </TabsContent>

                    {/* Contacts Tab */}
                    <TabsContent value="contacts" className="space-y-6">
                        <div className="flex justify-between items-center">
                            <h2 className="text-xl font-bold">Contacts ({contacts.length})</h2>
                            <Button onClick={() => setIsCreateContactModalOpen(true)}>
                                <Plus className="mr-2 w-4 h-4" />
                                Add Contact
                            </Button>
                        </div>

                        <Card>
                            <CardContent className="p-0">
                                <div className="overflow-x-auto">
                                    <table className="w-full text-sm text-left">
                                        <thead className="text-xs text-gray-700 uppercase bg-gray-50">
                                            <tr>
                                                <th className="px-6 py-3">Email</th>
                                                <th className="px-6 py-3">Name</th>
                                                <th className="px-6 py-3">Status</th>
                                                <th className="px-6 py-3">Rating</th>
                                                <th className="px-6 py-3">VIP</th>
                                                <th className="px-6 py-3">Last Changed</th>
                                                <th className="px-6 py-3">Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {contacts.map((contact) => (
                                                <tr key={contact.id} className="bg-white border-b hover:bg-gray-50">
                                                    <td className="px-6 py-4 font-medium text-gray-900">
                                                        {contact.email_address}
                                                    </td>
                                                    <td className="px-6 py-4">{contact.full_name || "Unknown"}</td>
                                                    <td className="px-6 py-4">
                                                        <Badge variant={getContactStatusVariant(contact.status)}>
                                                            {contact.status}
                                                        </Badge>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <div className="flex space-x-0.5">
                                                            {[...Array(5)].map((_, i) => (
                                                                <Star
                                                                    key={i}
                                                                    className={`w-3 h-3 ${i < contact.member_rating ? "text-yellow-400 fill-yellow-400" : "text-gray-300"}`}
                                                                />
                                                            ))}
                                                        </div>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <Badge variant={contact.vip ? "default" : "outline"} className={contact.vip ? "bg-purple-600 hover:bg-purple-700" : ""}>
                                                            {contact.vip ? "VIP" : "Standard"}
                                                        </Badge>
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        {contact.last_changed ? formatDate(contact.last_changed) : "Never"}
                                                    </td>
                                                    <td className="px-6 py-4">
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={() => {
                                                                setSelectedContact(contact);
                                                                setIsContactModalOpen(true);
                                                            }}
                                                        >
                                                            <Eye className="w-4 h-4" />
                                                        </Button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>

                {/* Audience Detail Modal */}
                <Dialog open={isAudienceModalOpen} onOpenChange={setIsAudienceModalOpen}>
                    <DialogContent className="max-w-lg">
                        <DialogHeader>
                            <DialogTitle>Audience Details</DialogTitle>
                        </DialogHeader>
                        {selectedAudience && (
                            <div className="space-y-4 py-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Name</h4>
                                        <p className="font-medium">{selectedAudience.name}</p>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Permission Reminder</h4>
                                        <p className="text-sm">{selectedAudience.permission_reminder}</p>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Member Count</h4>
                                        <p className="font-medium">{formatNumber(selectedAudience.member_count)}</p>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Unsubscribe Count</h4>
                                        <p className="font-medium">{formatNumber(selectedAudience.unsubscribe_count)}</p>
                                    </div>
                                </div>

                                <div className="border-t pt-4">
                                    <h4 className="font-medium mb-2">Contact Information</h4>
                                    <div className="text-sm space-y-1 text-muted-foreground">
                                        <p>Company: {selectedAudience.contact.company}</p>
                                        <p>Address: {selectedAudience.contact.address1}</p>
                                        <p>City: {selectedAudience.contact.city}</p>
                                        <p>State: {selectedAudience.contact.state}</p>
                                        <p>Country: {selectedAudience.contact.country}</p>
                                    </div>
                                </div>

                                {selectedAudience.stats && (
                                    <div className="border-t pt-4">
                                        <h4 className="font-medium mb-2">Performance Metrics</h4>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <p className="text-sm text-muted-foreground">Open Rate</p>
                                                <p className="font-medium">{formatPercentage(selectedAudience.stats.open_rate || 0)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Click Rate</p>
                                                <p className="font-medium">{formatPercentage(selectedAudience.stats.click_rate || 0)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Subscribe Rate</p>
                                                <p className="font-medium">{formatPercentage(selectedAudience.stats.sub_rate || 0)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Unsubscribe Rate</p>
                                                <p className="font-medium">{formatPercentage(selectedAudience.stats.unsub_rate || 0)}</p>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                        <DialogFooter>
                            <Button onClick={() => setIsAudienceModalOpen(false)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Campaign Detail Modal */}
                <Dialog open={isCampaignModalOpen} onOpenChange={setIsCampaignModalOpen}>
                    <DialogContent className="max-w-lg">
                        <DialogHeader>
                            <DialogTitle>Campaign Details</DialogTitle>
                        </DialogHeader>
                        {selectedCampaign && (
                            <div className="space-y-4 py-4">
                                <div>
                                    <h4 className="text-sm font-medium text-muted-foreground">Subject Line</h4>
                                    <p className="font-medium">{selectedCampaign.settings.subject_line}</p>
                                </div>

                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Status</h4>
                                        <Badge variant={getStatusVariant(selectedCampaign.status)} className="mt-1">
                                            {selectedCampaign.status}
                                        </Badge>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Type</h4>
                                        <p>{selectedCampaign.type}</p>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Recipients</h4>
                                        <p>{selectedCampaign.recipients.list_name}</p>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Emails Sent</h4>
                                        <p>{formatNumber(selectedCampaign.emails_sent)}</p>
                                    </div>
                                </div>

                                {selectedCampaign.send_time && (
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Send Time</h4>
                                        <p>{formatDate(selectedCampaign.send_time)}</p>
                                    </div>
                                )}

                                {selectedCampaign.report_summary && (
                                    <div className="border-t pt-4">
                                        <h4 className="font-medium mb-2">Performance Metrics</h4>
                                        <div className="grid grid-cols-2 gap-4">
                                            <div>
                                                <p className="text-sm text-muted-foreground">Opens</p>
                                                <p className="font-medium">{formatNumber(selectedCampaign.report_summary.opens || 0)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Unique Opens</p>
                                                <p className="font-medium">{formatNumber(selectedCampaign.report_summary.unique_opens || 0)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Open Rate</p>
                                                <p className="font-medium">{formatPercentage(selectedCampaign.report_summary.open_rate || 0)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Clicks</p>
                                                <p className="font-medium">{formatNumber(selectedCampaign.report_summary.clicks || 0)}</p>
                                            </div>
                                            <div>
                                                <p className="text-sm text-muted-foreground">Click Rate</p>
                                                <p className="font-medium">{formatPercentage(selectedCampaign.report_summary.click_rate || 0)}</p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {selectedCampaign.archive_url && (
                                    <div className="pt-2">
                                        <Button
                                            variant="link"
                                            className="p-0 h-auto text-blue-600"
                                            onClick={() => window.open(selectedCampaign.archive_url, "_blank")}
                                        >
                                            View Campaign Archive <ExternalLink className="ml-1 w-3 h-3" />
                                        </Button>
                                    </div>
                                )}
                            </div>
                        )}
                        <DialogFooter>
                            <Button onClick={() => setIsCampaignModalOpen(false)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Contact Detail Modal */}
                <Dialog open={isContactModalOpen} onOpenChange={setIsContactModalOpen}>
                    <DialogContent className="max-w-lg">
                        <DialogHeader>
                            <DialogTitle>Contact Details</DialogTitle>
                        </DialogHeader>
                        {selectedContact && (
                            <div className="space-y-4 py-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Email Address</h4>
                                        <p className="font-medium">{selectedContact.email_address}</p>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Full Name</h4>
                                        <p className="font-medium">{selectedContact.full_name || "Unknown"}</p>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Status</h4>
                                        <Badge variant={getContactStatusVariant(selectedContact.status)} className="mt-1">
                                            {selectedContact.status}
                                        </Badge>
                                    </div>
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">VIP Status</h4>
                                        <Badge variant={selectedContact.vip ? "default" : "outline"} className={`mt-1 ${selectedContact.vip ? "bg-purple-600" : ""}`}>
                                            {selectedContact.vip ? "VIP" : "Standard"}
                                        </Badge>
                                    </div>
                                </div>

                                <div>
                                    <h4 className="text-sm font-medium text-muted-foreground mb-1">Member Rating</h4>
                                    <div className="flex space-x-1">
                                        {[...Array(5)].map((_, i) => (
                                            <Star
                                                key={i}
                                                className={`w-4 h-4 ${i < selectedContact.member_rating ? "text-yellow-400 fill-yellow-400" : "text-gray-300"}`}
                                            />
                                        ))}
                                    </div>
                                </div>

                                {selectedContact.timestamp_signup && (
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Signup Date</h4>
                                        <p>{formatDate(selectedContact.timestamp_signup)}</p>
                                    </div>
                                )}

                                {selectedContact.email_client && (
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground">Email Client</h4>
                                        <p>{selectedContact.email_client}</p>
                                    </div>
                                )}

                                {selectedContact.tags.length > 0 && (
                                    <div>
                                        <h4 className="text-sm font-medium text-muted-foreground mb-2">Tags</h4>
                                        <div className="flex flex-wrap gap-2">
                                            {selectedContact.tags.map((tag) => (
                                                <Badge key={tag} variant="secondary">
                                                    {tag}
                                                </Badge>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                        <DialogFooter>
                            <Button onClick={() => setIsContactModalOpen(false)}>Close</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

export default MailchimpIntegration;
