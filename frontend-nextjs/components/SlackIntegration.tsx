/**
 * Slack Integration Component
 * Complete Slack communication and collaboration integration
 */

import React, { useState, useEffect, useCallback } from "react";
import {
    MessageSquare,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    Settings,
    RefreshCw,
    Clock,
    Star,
    Mail,
    Phone,
    Hash,
    Users,
    Building,
    Loader2,
    Lock,
    Globe,
    Archive,
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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface SlackChannel {
    id: string;
    name: string;
    purpose: string;
    num_members: number;
    is_archived: boolean;
    is_general: boolean;
    created: number;
    creator: string;
    is_private: boolean;
}

interface SlackMessage {
    team: string;
    user: string;
    user_profile: {
        real_name: string;
        display_name: string;
        image_24: string;
        image_32: string;
        image_48: string;
        image_72: string;
        image_192: string;
        image_512: string;
        image_102: string;
    };
    text: string;
    ts: string;
    attachments: Array<any>;
    reactions: Array<{
        name: string;
        count: number;
        users: string[];
    }>;
    thread_ts?: string;
    reply_count?: number;
    replies?: Array<{
        user: string;
        ts: string;
    }>;
    files?: Array<any>;
    upload?: boolean;
}

interface SlackUser {
    id: string;
    name: string;
    real_name: string;
    display_name: string;
    email?: string;
    phone?: string;
    title?: string;
    is_admin: boolean;
    is_owner: boolean;
    is_bot: boolean;
    deleted: boolean;
    profile: {
        real_name: string;
        display_name: string;
        real_name_normalized: string;
        display_name_normalized: string;
        email: string;
        image_24: string;
        image_32: string;
        image_48: string;
        image_72: string;
        image_192: string;
        image_512: string;
        image_1024: string;
        image_102: string;
    };
}

interface SlackWorkspace {
    id: string;
    name: string;
    domain: string;
    email_domain: string;
    icon: {
        image_34: string;
        image_44: string;
        image_68: string;
        image_88: string;
        image_102: string;
        image_132: string;
        image_230: string;
        image_default: boolean;
    };
}

const SlackIntegration: React.FC = () => {
    const [channels, setChannels] = useState<SlackChannel[]>([]);
    const [messages, setMessages] = useState<SlackMessage[]>([]);
    const [users, setUsers] = useState<SlackUser[]>([]);
    const [workspace, setWorkspace] = useState<SlackWorkspace | null>(null);
    const [loading, setLoading] = useState({
        channels: false,
        messages: false,
        users: false,
        workspace: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedChannel, setSelectedChannel] = useState("");
    const [messageText, setMessageText] = useState("");

    const [isMessageOpen, setIsMessageOpen] = useState(false);
    const [isChannelOpen, setIsChannelOpen] = useState(false);

    const [newMessage, setNewMessage] = useState({
        channel: "",
        text: "",
    });

    const [newChannel, setNewChannel] = useState({
        name: "",
        purpose: "",
        is_private: false,
    });

    const { toast } = useToast();

    // Load Slack data
    const loadWorkspace = useCallback(async () => {
        setLoading((prev) => ({ ...prev, workspace: true }));
        try {
            const response = await fetch("/api/integrations/slack/workspace", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setWorkspace(data.data?.workspace || null);
            }
        } catch (error) {
            console.error("Failed to load workspace:", error);
        } finally {
            setLoading((prev) => ({ ...prev, workspace: false }));
        }
    }, []);

    const loadChannels = useCallback(async () => {
        setLoading((prev) => ({ ...prev, channels: true }));
        try {
            const response = await fetch(`/api/integrations/slack/channels?user_id=current&limit=100`, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setChannels(data.data?.channels || []);
            }
        } catch (error) {
            console.error("Failed to load channels:", error);
            toast({
                title: "Error",
                description: "Failed to load channels from Slack",
                variant: "destructive",
            });
        } finally {
            setLoading((prev) => ({ ...prev, channels: false }));
        }
    }, [toast]);

    const loadMessages = async (channelId: string) => {
        if (!channelId) return;

        setLoading((prev) => ({ ...prev, messages: true }));
        try {
            const response = await fetch(`/api/integrations/slack/messages?user_id=current&channel=${channelId}&limit=50`, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setMessages(data.data?.messages || []);
            }
        } catch (error) {
            console.error("Failed to load messages:", error);
        } finally {
            setLoading((prev) => ({ ...prev, messages: false }));
        }
    };

    const loadUsers = useCallback(async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        try {
            const response = await fetch(`/api/integrations/slack/users?user_id=current&limit=100`, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
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
    }, []);

    // Check connection status
    const checkConnection = useCallback(async () => {
        try {
            const response = await fetch("/api/integrations/slack/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadWorkspace();
                loadChannels();
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
    }, [loadWorkspace, loadChannels, loadUsers]);

    const sendMessage = async () => {
        if (!newMessage.channel || !newMessage.text) return;

        try {
            const response = await fetch("/api/integrations/slack/messages", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    channel: newMessage.channel,
                    text: newMessage.text,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Message sent successfully",
                });
                setIsMessageOpen(false);
                setNewMessage({ channel: "", text: "" });
                if (newMessage.channel === selectedChannel) {
                    loadMessages(selectedChannel);
                }
            }
        } catch (error) {
            console.error("Failed to send message:", error);
            toast({
                title: "Error",
                description: "Failed to send message",
                variant: "destructive",
            });
        }
    };

    const createChannel = async () => {
        if (!newChannel.name) return;

        try {
            const response = await fetch("/api/integrations/slack/channels/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    name: newChannel.name,
                    purpose: newChannel.purpose,
                    is_private: newChannel.is_private,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Channel created successfully",
                });
                setIsChannelOpen(false);
                setNewChannel({ name: "", purpose: "", is_private: false });
                loadChannels();
            }
        } catch (error) {
            console.error("Failed to create channel:", error);
            toast({
                title: "Error",
                description: "Failed to create channel",
                variant: "destructive",
            });
        }
    };

    // Filter data based on search
    const filteredChannels = channels.filter(
        (channel) =>
            channel.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            channel.purpose.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredUsers = users.filter(
        (user) =>
            user.real_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (user.email &&
                user.email.toLowerCase().includes(searchQuery.toLowerCase()))
    );

    const filteredMessages = messages.filter(
        (message) =>
            message.text.toLowerCase().includes(searchQuery.toLowerCase()) ||
            (message.user_profile?.display_name || "")
                .toLowerCase()
                .includes(searchQuery.toLowerCase())
    );

    // Stats calculations
    const totalChannels = channels.length;
    const privateChannels = channels.filter((ch) => ch.is_private).length;
    const totalUsers = users.length;
    const activeUsers = users.filter((u) => !u.deleted && !u.is_bot).length;
    const totalMessages = messages.length;

    useEffect(() => {
        checkConnection();
    }, [checkConnection]);

    useEffect(() => {
        if (connected) {
            loadWorkspace();
            loadChannels();
            loadUsers();
        }
    }, [connected, loadChannels, loadWorkspace, loadUsers]);

    useEffect(() => {
        if (selectedChannel) {
            loadMessages(selectedChannel);
        }
    }, [selectedChannel]);

    const formatDate = (timestamp: string): string => {
        return new Date(parseFloat(timestamp) * 1000).toLocaleString();
    };

    const getStatusVariant = (channel: SlackChannel): "default" | "secondary" | "destructive" | "outline" => {
        if (channel.is_archived) return "secondary";
        if (channel.is_private) return "outline"; // Purple-ish usually, but outline is distinct
        if (channel.is_general) return "default"; // Green-ish
        return "secondary"; // Blue-ish
    };

    const getStatusLabel = (channel: SlackChannel): string => {
        if (channel.is_archived) return "Archived";
        if (channel.is_private) return "Private";
        if (channel.is_general) return "General";
        return "Public";
    };

    // Render connection status
    if (!connected && healthStatus !== "unknown") {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
                    <div className="space-y-2">
                        <h2 className="text-2xl font-semibold">Connect Slack</h2>
                        <p className="text-muted-foreground mb-6">
                            Connect your Slack workspace to start managing conversations
                            and teams
                        </p>
                    </div>

                    <Card className="max-w-md w-full">
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center space-y-4">
                                <MessageSquare className="w-16 h-16 text-purple-500 mb-4" />
                                <h3 className="text-xl font-semibold">Slack Integration</h3>
                                <p className="text-muted-foreground mt-2">
                                    Team communication and collaboration platform
                                </p>

                                <Button
                                    size="lg"
                                    className="w-full bg-purple-600 hover:bg-purple-700"
                                    onClick={() =>
                                    (window.location.href =
                                        "/api/integrations/slack/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Slack Workspace
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </div>
        );
    }

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <MessageSquare className="w-8 h-8 text-purple-500" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Slack Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Team communication and collaboration platform
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

                    {workspace && (
                        <div className="flex items-center space-x-4">
                            <Avatar className="w-8 h-8">
                                <AvatarImage src={workspace.icon.image_102} alt={workspace.name} />
                                <AvatarFallback>{workspace.name.charAt(0)}</AvatarFallback>
                            </Avatar>
                            <span className="font-bold">{workspace.name}</span>
                            <span className="text-muted-foreground">({workspace.domain})</span>
                        </div>
                    )}
                </div>

                {/* Services Overview */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Channels</p>
                                <div className="text-2xl font-bold">{totalChannels}</div>
                                <p className="text-xs text-muted-foreground">{privateChannels} private</p>
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
                                <p className="text-sm font-medium text-muted-foreground">Messages</p>
                                <div className="text-2xl font-bold">{totalMessages}</div>
                                <p className="text-xs text-muted-foreground">In selected channel</p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Workspace</p>
                                <div className="text-2xl font-bold truncate">{workspace?.name || "Unknown"}</div>
                                <p className="text-xs text-muted-foreground">Connected</p>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Main Content Tabs */}
                <Tabs defaultValue="channels">
                    <TabsList>
                        <TabsTrigger value="channels">Channels</TabsTrigger>
                        <TabsTrigger value="messages">Messages</TabsTrigger>
                        <TabsTrigger value="users">Users</TabsTrigger>
                        <TabsTrigger value="workspace">Workspace</TabsTrigger>
                    </TabsList>

                    {/* Channels Tab */}
                    <TabsContent value="channels" className="space-y-6 mt-6">
                        <div className="flex items-center space-x-4">
                            <div className="relative flex-1">
                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search channels..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-8"
                                />
                            </div>
                            <Button
                                className="bg-purple-600 hover:bg-purple-700"
                                onClick={() => setIsChannelOpen(true)}
                            >
                                <Plus className="mr-2 w-4 h-4" />
                                Create Channel
                            </Button>
                        </div>

                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-4">
                                    {loading.channels ? (
                                        <div className="flex justify-center p-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                                        </div>
                                    ) : (
                                        filteredChannels.map((channel) => (
                                            <div
                                                key={channel.id}
                                                className="flex items-center p-4 border rounded-md hover:bg-gray-50 cursor-pointer transition-colors"
                                                onClick={() => {
                                                    setSelectedChannel(channel.id);
                                                    loadMessages(channel.id);
                                                    // Switch to messages tab logic would go here if we had access to tab state control
                                                    // For now just loading messages
                                                }}
                                            >
                                                <div className="flex-1 space-y-1">
                                                    <div className="flex items-center space-x-2">
                                                        <span className="font-bold">#{channel.name}</span>
                                                        <Badge variant={getStatusVariant(channel)} className="text-xs">
                                                            {getStatusLabel(channel)}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-sm text-muted-foreground">
                                                        {channel.purpose || "No purpose"}
                                                    </p>
                                                    <p className="text-xs text-gray-500">
                                                        {channel.num_members} members
                                                    </p>
                                                </div>
                                                <ArrowRight className="w-4 h-4 text-gray-400" />
                                            </div>
                                        ))
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Messages Tab */}
                    <TabsContent value="messages" className="space-y-6 mt-6">
                        <div className="flex items-center space-x-4">
                            <Select
                                value={selectedChannel}
                                onValueChange={setSelectedChannel}
                            >
                                <SelectTrigger className="w-[300px]">
                                    <SelectValue placeholder="Select channel" />
                                </SelectTrigger>
                                <SelectContent>
                                    {channels.map((channel) => (
                                        <SelectItem key={channel.id} value={channel.id}>
                                            #{channel.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <div className="relative flex-1">
                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search messages..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-8"
                                />
                            </div>
                            <Button
                                className="bg-purple-600 hover:bg-purple-700"
                                onClick={() => setIsMessageOpen(true)}
                                disabled={!selectedChannel}
                            >
                                <Plus className="mr-2 w-4 h-4" />
                                Send Message
                            </Button>
                        </div>

                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-4 max-h-[600px] overflow-y-auto">
                                    {loading.messages ? (
                                        <div className="flex justify-center p-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                                        </div>
                                    ) : selectedChannel ? (
                                        filteredMessages.map((message) => (
                                            <div
                                                key={message.ts}
                                                className="flex items-start p-4 border rounded-md space-x-4"
                                            >
                                                <Avatar className="w-10 h-10">
                                                    <AvatarImage src={message.user_profile?.image_48} />
                                                    <AvatarFallback>{message.user_profile?.display_name?.charAt(0)}</AvatarFallback>
                                                </Avatar>
                                                <div className="flex-1 space-y-1">
                                                    <div className="flex items-center space-x-2">
                                                        <span className="font-bold">
                                                            {message.user_profile?.display_name || "Unknown"}
                                                        </span>
                                                        <span className="text-xs text-muted-foreground">
                                                            {formatDate(message.ts)}
                                                        </span>
                                                    </div>
                                                    <p className="text-sm">{message.text}</p>
                                                    {message.reactions && message.reactions.length > 0 && (
                                                        <div className="flex flex-wrap gap-2 mt-2">
                                                            {message.reactions.map((reaction, idx) => (
                                                                <Badge key={idx} variant="secondary" className="text-xs">
                                                                    {reaction.name} {reaction.count}
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="text-center py-8 text-muted-foreground">
                                            Select a channel to view messages
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Users Tab */}
                    <TabsContent value="users" className="space-y-6 mt-6">
                        <div className="flex items-center space-x-4">
                            <div className="relative flex-1">
                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search users..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-8"
                                />
                            </div>
                        </div>

                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-4">
                                    {loading.users ? (
                                        <div className="flex justify-center p-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                                        </div>
                                    ) : (
                                        filteredUsers.map((user) => (
                                            <div
                                                key={user.id}
                                                className="flex items-center p-4 border rounded-md hover:bg-gray-50 transition-colors"
                                            >
                                                <Avatar className="w-12 h-12 mr-4">
                                                    <AvatarImage src={user.profile.image_48} />
                                                    <AvatarFallback>{user.display_name?.charAt(0)}</AvatarFallback>
                                                </Avatar>
                                                <div className="flex-1 space-y-1">
                                                    <div className="flex items-center space-x-2">
                                                        <span className="font-bold">{user.real_name}</span>
                                                        {user.is_admin && (
                                                            <Badge variant="destructive" className="text-xs">Admin</Badge>
                                                        )}
                                                        {user.is_owner && (
                                                            <Badge className="bg-orange-500 hover:bg-orange-600 text-xs">Owner</Badge>
                                                        )}
                                                        {user.is_bot && (
                                                            <Badge variant="secondary" className="text-xs">Bot</Badge>
                                                        )}
                                                    </div>
                                                    <p className="text-sm text-muted-foreground">@{user.name}</p>
                                                    {user.title && (
                                                        <p className="text-xs text-gray-500">{user.title}</p>
                                                    )}
                                                    {user.profile.email && (
                                                        <div className="flex items-center text-xs text-gray-500 mt-1">
                                                            <Mail className="w-3 h-3 mr-1" />
                                                            {user.profile.email}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Workspace Tab */}
                    <TabsContent value="workspace" className="space-y-6 mt-6">
                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-6">
                                    {workspace ? (
                                        <>
                                            <div className="flex items-center space-x-6">
                                                <Avatar className="w-24 h-24">
                                                    <AvatarImage src={workspace.icon.image_102} />
                                                    <AvatarFallback>{workspace.name.charAt(0)}</AvatarFallback>
                                                </Avatar>
                                                <div className="space-y-2">
                                                    <h2 className="text-2xl font-bold">{workspace.name}</h2>
                                                    <p className="text-muted-foreground">{workspace.domain}.slack.com</p>
                                                    {workspace.email_domain && (
                                                        <p className="text-sm text-gray-500">
                                                            Email domain: {workspace.email_domain}
                                                        </p>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 pt-6 border-t">
                                                <div className="space-y-1">
                                                    <p className="text-sm font-medium text-muted-foreground">Total Channels</p>
                                                    <div className="text-2xl font-bold">{totalChannels}</div>
                                                </div>
                                                <div className="space-y-1">
                                                    <p className="text-sm font-medium text-muted-foreground">Total Users</p>
                                                    <div className="text-2xl font-bold">{totalUsers}</div>
                                                </div>
                                                <div className="space-y-1">
                                                    <p className="text-sm font-medium text-muted-foreground">Active Users</p>
                                                    <div className="text-2xl font-bold">{activeUsers}</div>
                                                </div>
                                            </div>
                                        </>
                                    ) : (
                                        <div className="text-center py-8 text-muted-foreground">
                                            Loading workspace information...
                                        </div>
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>

                {/* Send Message Modal */}
                <Dialog open={isMessageOpen} onOpenChange={setIsMessageOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Send Message</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Channel</label>
                                <Select
                                    value={newMessage.channel}
                                    onValueChange={(value) =>
                                        setNewMessage({
                                            ...newMessage,
                                            channel: value,
                                        })
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select a channel" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {channels.map((channel) => (
                                            <SelectItem key={channel.id} value={channel.id}>
                                                #{channel.name}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Message</label>
                                <Textarea
                                    placeholder="Type your message..."
                                    value={newMessage.text}
                                    onChange={(e) =>
                                        setNewMessage({
                                            ...newMessage,
                                            text: e.target.value,
                                        })
                                    }
                                    rows={4}
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsMessageOpen(false)}>
                                Cancel
                            </Button>
                            <Button
                                className="bg-purple-600 hover:bg-purple-700"
                                onClick={sendMessage}
                                disabled={!newMessage.channel || !newMessage.text}
                            >
                                Send Message
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Create Channel Modal */}
                <Dialog open={isChannelOpen} onOpenChange={setIsChannelOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Create Channel</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Channel Name</label>
                                <Input
                                    placeholder="channel-name"
                                    value={newChannel.name}
                                    onChange={(e) =>
                                        setNewChannel({
                                            ...newChannel,
                                            name: e.target.value,
                                        })
                                    }
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Purpose</label>
                                <Textarea
                                    placeholder="What's this channel about?"
                                    value={newChannel.purpose}
                                    onChange={(e) =>
                                        setNewChannel({
                                            ...newChannel,
                                            purpose: e.target.value,
                                        })
                                    }
                                    rows={3}
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsChannelOpen(false)}>
                                Cancel
                            </Button>
                            <Button
                                className="bg-purple-600 hover:bg-purple-700"
                                onClick={createChannel}
                                disabled={!newChannel.name}
                            >
                                Create Channel
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

export default SlackIntegration;
