/**
 * Microsoft Teams Integration Component
 * Complete Microsoft Teams collaboration and communication integration
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
    User,
    Paperclip,
    ExternalLink,
    Lock,
    Unlock,
    Loader2,
    MoreVertical,
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
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface MSTeams {
    id: string;
    displayName: string;
    description: string;
    createdDateTime: string;
    updatedDateTime: string;
    classification?: string;
    specialization: string;
    visibility: string;
    webUrl: string;
    internalId: string;
    isArchived: boolean;
    memberSettings?: {
        allowCreateUpdateRemoveChannels: boolean;
        allowAddRemoveApps: boolean;
        allowCreateUpdateRemoveTabs: boolean;
        allowCreateUpdateRemoveConnectors: boolean;
    };
    guestSettings?: {
        allowCreateUpdateChannels: boolean;
        allowDeleteChannels: boolean;
    };
    funSettings?: {
        allowGiphy: boolean;
        giphyContentRating: string;
        allowStickersAndMemes: boolean;
    };
}

interface MSTeamsChannel {
    id: string;
    displayName: string;
    description: string;
    createdDateTime: string;
    updatedDateTime: string;
    email: string;
    isFavoriteByDefault: boolean;
    membershipType: string;
    tenant: string;
    webUrl: string;
    filesFolder?: {
        id: string;
        name: string;
        webUrl: string;
    };
    moderatedSettings?: {
        allowNewMessagesFromBotsAndConnectors: boolean;
        allowNewMessagesFromEveryone: boolean;
        blockNewMessagesFromNonMembers: boolean;
    };
    tabs: MSTeamsTab[];
    messages: MSTeamsMessage[];
}

interface MSTeamsMessage {
    id: string;
    messageType: string;
    createdDateTime: string;
    lastModifiedDateTime: string;
    conversationId: string;
    from: {
        application?: {
            id: string;
            displayName: string;
        };
        device?: {
            id: string;
            displayName: string;
        };
        user?: {
            id: string;
            displayName: string;
        };
    };
    body: {
        content: string;
        contentType: string;
    };
    attachments?: Array<{
        id: string;
        contentType: string;
        name: string;
        url: string;
    }>;
    mentions?: Array<{
        id: number;
        mentionText: string;
        mentioned: {
            user?: {
                displayName: string;
                id: string;
                userIdentityType: string;
            };
        };
    }>;
    importance?: string;
    locale?: string;
    reactions?: Array<{
        reactionType: string;
        createdDateTime: string;
        user: {
            displayName: string;
            id: string;
        };
    }>;
    replies?: MSTeamsMessage[];
}

interface MSTeamsTab {
    id: string;
    displayName: string;
    teamsAppId: string;
    sortorderindex: string;
    webUrl: string;
    configuration?: {
        entityId: string;
        contentUrl: string;
        removeUrl: string;
        websiteUrl: string;
        suggestedDisplayName: string;
    };
}

interface MSTeamsUser {
    id: string;
    displayName: string;
    givenName?: string;
    surname?: string;
    mail?: string;
    mobilePhone?: string;
    jobTitle?: string;
    officeLocation?: string;
    preferredLanguage?: string;
    userPrincipalName: string;
    accountEnabled: boolean;
    department?: string;
    usageLocation?: string;
    licenseAssignmentStates?: Array<{
        skuId: string;
        disabledPlans?: string[];
        state: string;
    }>;
}

interface MSTeamsMeeting {
    id: string;
    subject?: string;
    body?: {
        contentType: string;
        content: string;
    };
    start: {
        dateTime: string;
        timeZone: string;
    };
    end: {
        dateTime: string;
        timeZone: string;
    };
    location?: {
        displayName: string;
    };
    attendees?: Array<{
        type: string;
        status: {
            response: string;
            time: string;
        };
        emailAddress: {
            name: string;
            address: string;
        };
    }>;
    isOnlineMeeting: boolean;
    onlineMeetingUrl?: string;
    joinUrl?: string;
    conferenceId?: string;
    tollNumber?: string;
    dialinUrl?: string;
    createdDateTime: string;
    lastModifiedDateTime: string;
}

const TeamsIntegration: React.FC = () => {
    const [teams, setTeams] = useState<MSTeams[]>([]);
    const [channels, setChannels] = useState<MSTeamsChannel[]>([]);
    const [messages, setMessages] = useState<MSTeamsMessage[]>([]);
    const [meetings, setMeetings] = useState<MSTeamsMeeting[]>([]);
    const [users, setUsers] = useState<MSTeamsUser[]>([]);
    const [userProfile, setUserProfile] = useState<MSTeamsUser | null>(null);
    const [currentTeam, setCurrentTeam] = useState<MSTeams | null>(null);
    const [currentChannel, setCurrentChannel] = useState<MSTeamsChannel | null>(
        null,
    );
    const [loading, setLoading] = useState({
        teams: false,
        channels: false,
        messages: false,
        meetings: false,
        users: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");

    // Form states
    const [teamForm, setTeamForm] = useState({
        name: "",
        description: "",
        visibility: "private",
        specialization: "none",
        classification: "",
    });

    const [channelForm, setChannelForm] = useState({
        name: "",
        description: "",
        membership_type: "standard",
        is_favorite_by_default: false,
    });

    const [messageForm, setMessageForm] = useState({
        content: "",
        importance: "normal",
        mentioned_users: [] as string[],
    });

    const [meetingForm, setMeetingForm] = useState({
        subject: "",
        body: "",
        start_time: "",
        end_time: "",
        attendees: [] as string[],
        is_online_meeting: true,
    });

    const [isTeamOpen, setIsTeamOpen] = useState(false);
    const [isChannelOpen, setIsChannelOpen] = useState(false);
    const [isMessageOpen, setIsMessageOpen] = useState(false);
    const [isMeetingOpen, setIsMeetingOpen] = useState(false);

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/teams/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
                loadTeams();
                loadUsers();
                loadMeetings();
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

    // Load Microsoft Teams data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/teams/profile", {
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

    const loadTeams = async () => {
        setLoading((prev) => ({ ...prev, teams: true }));
        try {
            const response = await fetch("/api/integrations/teams/teams", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setTeams(data.data?.teams || []);
            }
        } catch (error) {
            console.error("Failed to load teams:", error);
            toast({
                title: "Error",
                description: "Failed to load teams from Microsoft Teams",
                variant: "destructive",
            });
        } finally {
            setLoading((prev) => ({ ...prev, teams: false }));
        }
    };

    const loadChannels = async (teamId?: string) => {
        if (!teamId && !currentTeam) return;

        setLoading((prev) => ({ ...prev, channels: true }));
        try {
            const response = await fetch("/api/integrations/teams/channels", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    team_id: teamId || currentTeam?.id,
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setChannels(data.data?.channels || []);
            }
        } catch (error) {
            console.error("Failed to load channels:", error);
        } finally {
            setLoading((prev) => ({ ...prev, channels: false }));
        }
    };

    const loadMessages = async (channelId?: string) => {
        if (!channelId && !currentChannel) return;

        setLoading((prev) => ({ ...prev, messages: true }));
        try {
            const response = await fetch("/api/integrations/teams/messages", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    team_id: currentTeam?.id,
                    channel_id: channelId || currentChannel?.id,
                    limit: 50,
                }),
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

    const loadMeetings = async () => {
        setLoading((prev) => ({ ...prev, meetings: true }));
        try {
            const response = await fetch("/api/integrations/teams/meetings", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    start_date: new Date().toISOString(),
                    end_date: new Date(
                        Date.now() + 30 * 24 * 60 * 60 * 1000,
                    ).toISOString(),
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setMeetings(data.data?.meetings || []);
            }
        } catch (error) {
            console.error("Failed to load meetings:", error);
        } finally {
            setLoading((prev) => ({ ...prev, meetings: false }));
        }
    };

    const loadUsers = async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        try {
            const response = await fetch("/api/integrations/teams/users", {
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

    // Create operations
    const createTeam = async () => {
        if (!teamForm.name) return;

        try {
            const response = await fetch("/api/integrations/teams/teams/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    displayName: teamForm.name,
                    description: teamForm.description,
                    visibility: teamForm.visibility,
                    specialization: teamForm.specialization,
                    classification: teamForm.classification,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Team created successfully",
                });
                setIsTeamOpen(false);
                setTeamForm({
                    name: "",
                    description: "",
                    visibility: "private",
                    specialization: "none",
                    classification: "",
                });
                loadTeams();
            }
        } catch (error) {
            console.error("Failed to create team:", error);
            toast({
                title: "Error",
                description: "Failed to create team",
                variant: "destructive",
            });
        }
    };

    const createChannel = async () => {
        if (!channelForm.name || !currentTeam) return;

        try {
            const response = await fetch("/api/integrations/teams/channels/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    team_id: currentTeam.id,
                    displayName: channelForm.name,
                    description: channelForm.description,
                    membershipType: channelForm.membership_type,
                    isFavoriteByDefault: channelForm.is_favorite_by_default,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Channel created successfully",
                });
                setIsChannelOpen(false);
                setChannelForm({
                    name: "",
                    description: "",
                    membership_type: "standard",
                    is_favorite_by_default: false,
                });
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

    const sendMessage = async () => {
        if (!messageForm.content || !currentChannel) return;

        try {
            const response = await fetch("/api/integrations/teams/messages/send", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    team_id: currentTeam?.id,
                    channel_id: currentChannel.id,
                    content: messageForm.content,
                    importance: messageForm.importance,
                    mentions: messageForm.mentioned_users.map((userId) => ({
                        id: 0,
                        mentionText: `<at id="${userId}">User</at>`,
                        mentioned: {
                            user: {
                                displayName:
                                    users.find((u) => u.id === userId)?.displayName || "",
                                id: userId,
                                userIdentityType: "user",
                            },
                        },
                    })),
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Message sent successfully",
                });
                setIsMessageOpen(false);
                setMessageForm({
                    content: "",
                    importance: "normal",
                    mentioned_users: [],
                });
                loadMessages();
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

    const createMeeting = async () => {
        if (
            !meetingForm.subject ||
            !meetingForm.start_time ||
            !meetingForm.end_time
        )
            return;

        try {
            const response = await fetch("/api/integrations/teams/meetings/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    subject: meetingForm.subject,
                    body: {
                        contentType: "text",
                        content: meetingForm.body,
                    },
                    start: {
                        dateTime: meetingForm.start_time,
                        timeZone: "UTC",
                    },
                    end: {
                        dateTime: meetingForm.end_time,
                        timeZone: "UTC",
                    },
                    attendees: meetingForm.attendees.map((email) => ({
                        type: "required",
                        emailAddress: {
                            address: email,
                            name: email.split("@")[0],
                        },
                        status: {
                            response: "notResponded",
                            time: new Date().toISOString(),
                        },
                    })),
                    isOnlineMeeting: meetingForm.is_online_meeting,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Meeting scheduled successfully",
                });
                setIsMeetingOpen(false);
                setMeetingForm({
                    subject: "",
                    body: "",
                    start_time: "",
                    end_time: "",
                    attendees: [],
                    is_online_meeting: true,
                });
                loadMeetings();
            }
        } catch (error) {
            console.error("Failed to create meeting:", error);
            toast({
                title: "Error",
                description: "Failed to create meeting",
                variant: "destructive",
            });
        }
    };

    // Filter data based on search
    const filteredTeams = teams.filter(
        (team) =>
            team.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            team.description.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredChannels = channels.filter(
        (channel) =>
            channel.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            channel.description.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredMessages = messages.filter(
        (message) =>
            message.body.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
            message.from.user?.displayName
                ?.toLowerCase()
                .includes(searchQuery.toLowerCase()),
    );

    const filteredMeetings = meetings.filter(
        (meeting) =>
            (meeting.subject &&
                meeting.subject.toLowerCase().includes(searchQuery.toLowerCase())) ||
            (meeting.body?.content &&
                meeting.body.content.toLowerCase().includes(searchQuery.toLowerCase())),
    );

    const filteredUsers = users.filter(
        (user) =>
            user.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.mail?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.userPrincipalName.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    // Stats calculations
    const totalTeams = teams.length;
    const totalChannels = channels.length;
    const totalMeetings = meetings.length;
    const upcomingMeetings = meetings.filter(
        (m) => new Date(m.start.dateTime) > new Date(),
    ).length;
    const totalUsers = users.length;
    const activeUsers = users.filter((u) => u.accountEnabled).length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadUserProfile();
            loadTeams();
            loadUsers();
            loadMeetings();
        }
    }, [connected]);

    useEffect(() => {
        if (currentTeam) {
            loadChannels();
        }
    }, [currentTeam]);

    useEffect(() => {
        if (currentChannel) {
            loadMessages();
        }
    }, [currentChannel]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const getVisibilityVariant = (visibility: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (visibility?.toLowerCase()) {
            case "public":
                return "default";
            case "private":
                return "secondary";
            default:
                return "outline";
        }
    };

    const getSpecializationVariant = (specialization: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (specialization?.toLowerCase()) {
            case "educationstandard":
                return "default";
            case "educationclass":
                return "secondary";
            case "educationprofessionallearning":
                return "outline";
            default:
                return "outline";
        }
    };

    const getMembershipTypeVariant = (membershipType: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (membershipType?.toLowerCase()) {
            case "standard":
                return "default";
            case "private":
                return "secondary";
            case "shared":
                return "outline";
            default:
                return "outline";
        }
    };

    const getImportanceVariant = (importance?: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (importance?.toLowerCase()) {
            case "high":
                return "destructive";
            case "normal":
                return "secondary";
            case "low":
                return "outline";
            default:
                return "outline";
        }
    };

    const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status?.toLowerCase()) {
            case "accepted":
                return "default";
            case "tentative":
                return "secondary";
            case "declined":
                return "destructive";
            case "notresponded":
                return "outline";
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
                        <Settings className="w-8 h-8 text-[#2B579A]" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Microsoft Teams Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Team messaging and collaboration platform
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
                                <AvatarImage src="" alt={userProfile.displayName} />
                                <AvatarFallback>{userProfile.displayName.charAt(0)}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col">
                                <span className="font-bold">{userProfile.displayName}</span>
                                <span className="text-sm text-muted-foreground">
                                    {userProfile.jobTitle || userProfile.mail}
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
                                    <h2 className="text-2xl font-bold">Connect Microsoft Teams</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Microsoft Teams account to start managing teams
                                        and channels
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-[#2B579A] hover:bg-[#204275]"
                                    onClick={() =>
                                        (window.location.href = "/api/integrations/teams/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Microsoft Teams Account
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
                                        <p className="text-sm font-medium text-muted-foreground">Teams</p>
                                        <div className="text-2xl font-bold">{totalTeams}</div>
                                        <p className="text-xs text-muted-foreground">Active workspaces</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Channels</p>
                                        <div className="text-2xl font-bold">{totalChannels}</div>
                                        <p className="text-xs text-muted-foreground">Communication channels</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Meetings</p>
                                        <div className="text-2xl font-bold">{upcomingMeetings}</div>
                                        <p className="text-xs text-muted-foreground">{totalMeetings} total</p>
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
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="teams">
                            <TabsList>
                                <TabsTrigger value="teams">Teams</TabsTrigger>
                                <TabsTrigger value="channels">Channels</TabsTrigger>
                                <TabsTrigger value="messages">Messages</TabsTrigger>
                                <TabsTrigger value="meetings">Meetings</TabsTrigger>
                                <TabsTrigger value="users">Users</TabsTrigger>
                            </TabsList>

                            {/* Teams Tab */}
                            <TabsContent value="teams" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search teams..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#2B579A] hover:bg-[#204275]"
                                        onClick={() => setIsTeamOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Team
                                    </Button>
                                </div>

                                {loading.teams ? (
                                    <div className="flex justify-center py-8">
                                        <Loader2 className="w-8 h-8 animate-spin text-[#2B579A]" />
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                        {filteredTeams.map((team) => (
                                            <Card
                                                key={team.id}
                                                className={`cursor-pointer transition-all hover:shadow-md hover:-translate-y-0.5 ${currentTeam?.id === team.id ? "border-[#2B579A] ring-1 ring-[#2B579A]" : ""
                                                    }`}
                                                onClick={() => setCurrentTeam(team)}
                                            >
                                                <CardHeader>
                                                    <div className="flex flex-col space-y-2">
                                                        <div className="flex justify-between items-center w-full">
                                                            <span className="font-bold text-lg">{team.displayName}</span>
                                                            <div className="flex space-x-2">
                                                                <Badge variant={getVisibilityVariant(team.visibility)}>
                                                                    {team.visibility}
                                                                </Badge>
                                                                {team.isArchived && (
                                                                    <Badge variant="secondary">Archived</Badge>
                                                                )}
                                                            </div>
                                                        </div>
                                                        {team.description && (
                                                            <p className="text-sm text-muted-foreground">
                                                                {team.description}
                                                            </p>
                                                        )}
                                                    </div>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="flex flex-col space-y-3">
                                                        <div className="flex justify-between items-center">
                                                            <Badge variant={getSpecializationVariant(team.specialization)}>
                                                                {team.specialization}
                                                            </Badge>
                                                            <span className="text-xs text-muted-foreground">
                                                                Created: {formatDate(team.createdDateTime)}
                                                            </span>
                                                        </div>
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            className="w-full"
                                                            onClick={() => window.open(team.webUrl, "_blank")}
                                                        >
                                                            <ExternalLink className="mr-2 w-3 h-3" />
                                                            Open in Teams
                                                        </Button>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                )}
                            </TabsContent>

                            {/* Channels Tab */}
                            <TabsContent value="channels" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={currentTeam?.id || ""}
                                        onValueChange={(value) => {
                                            const team = teams.find((t) => t.id === value);
                                            setCurrentTeam(team || null);
                                        }}
                                    >
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Select team" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {teams.map((team) => (
                                                <SelectItem key={team.id} value={team.id}>
                                                    {team.displayName}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
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
                                        className="bg-[#2B579A] hover:bg-[#204275]"
                                        onClick={() => setIsChannelOpen(true)}
                                        disabled={!currentTeam}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Channel
                                    </Button>
                                </div>

                                {loading.channels ? (
                                    <div className="flex justify-center py-8">
                                        <Loader2 className="w-8 h-8 animate-spin text-[#2B579A]" />
                                    </div>
                                ) : currentTeam ? (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                        {filteredChannels.map((channel) => (
                                            <Card
                                                key={channel.id}
                                                className={`cursor-pointer transition-all hover:shadow-md hover:-translate-y-0.5 ${currentChannel?.id === channel.id ? "border-[#2B579A] ring-1 ring-[#2B579A]" : ""
                                                    }`}
                                                onClick={() => setCurrentChannel(channel)}
                                            >
                                                <CardHeader>
                                                    <div className="flex flex-col space-y-2">
                                                        <div className="flex justify-between items-center w-full">
                                                            <span className="font-bold text-lg">{channel.displayName}</span>
                                                            <div className="flex space-x-2">
                                                                <Badge variant={getMembershipTypeVariant(channel.membershipType)}>
                                                                    {channel.membershipType}
                                                                </Badge>
                                                                {channel.isFavoriteByDefault && (
                                                                    <Badge variant="secondary" className="bg-yellow-100 text-yellow-800 hover:bg-yellow-200">
                                                                        <Star className="mr-1 w-3 h-3" />
                                                                        Favorite
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                        </div>
                                                        {channel.description && (
                                                            <p className="text-sm text-muted-foreground">
                                                                {channel.description}
                                                            </p>
                                                        )}
                                                    </div>
                                                </CardHeader>
                                                <CardContent>
                                                    <div className="flex flex-col space-y-3">
                                                        <span className="text-xs text-muted-foreground">
                                                            Created: {formatDate(channel.createdDateTime)}
                                                        </span>
                                                        {channel.tabs && channel.tabs.length > 0 && (
                                                            <span className="text-xs text-muted-foreground">
                                                                {channel.tabs.length} tabs
                                                            </span>
                                                        )}
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            className="w-full"
                                                            onClick={() => window.open(channel.webUrl, "_blank")}
                                                        >
                                                            <ExternalLink className="mr-2 w-3 h-3" />
                                                            Open in Teams
                                                        </Button>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-center py-8 text-muted-foreground">
                                        Select a team to view channels
                                    </div>
                                )}
                            </TabsContent>

                            {/* Messages Tab */}
                            <TabsContent value="messages" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={currentTeam?.id || ""}
                                        onValueChange={(value) => {
                                            const team = teams.find((t) => t.id === value);
                                            setCurrentTeam(team || null);
                                            setCurrentChannel(null);
                                        }}
                                    >
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="Select team" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {teams.map((team) => (
                                                <SelectItem key={team.id} value={team.id}>
                                                    {team.displayName}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <Select
                                        value={currentChannel?.id || ""}
                                        onValueChange={(value) => {
                                            const channel = channels.find((c) => c.id === value);
                                            setCurrentChannel(channel || null);
                                        }}
                                        disabled={!currentTeam}
                                    >
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="Select channel" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {channels.map((channel) => (
                                                <SelectItem key={channel.id} value={channel.id}>
                                                    {channel.displayName}
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
                                        className="bg-[#2B579A] hover:bg-[#204275]"
                                        onClick={() => setIsMessageOpen(true)}
                                        disabled={!currentChannel}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Send Message
                                    </Button>
                                </div>

                                <div className="space-y-4">
                                    {loading.messages ? (
                                        <div className="flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#2B579A]" />
                                        </div>
                                    ) : currentChannel ? (
                                        filteredMessages.map((message) => (
                                            <Card key={message.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex space-x-4 items-start">
                                                        <Avatar>
                                                            <AvatarImage src="" alt={message.from.user?.displayName} />
                                                            <AvatarFallback>{message.from.user?.displayName?.charAt(0) || "?"}</AvatarFallback>
                                                        </Avatar>
                                                        <div className="flex-1 space-y-2">
                                                            <div className="flex justify-between w-full">
                                                                <span className="font-medium">
                                                                    {message.from.user?.displayName}
                                                                </span>
                                                                <div className="flex items-center space-x-2">
                                                                    {message.importance && (
                                                                        <Badge variant={getImportanceVariant(message.importance)}>
                                                                            {message.importance}
                                                                        </Badge>
                                                                    )}
                                                                    <span className="text-xs text-muted-foreground">
                                                                        {formatDate(message.createdDateTime)}
                                                                    </span>
                                                                </div>
                                                            </div>
                                                            <p className="text-sm whitespace-pre-wrap">
                                                                {message.body.content}
                                                            </p>
                                                            {message.reactions && message.reactions.length > 0 && (
                                                                <div className="flex flex-wrap gap-2">
                                                                    {message.reactions.map((reaction, index) => (
                                                                        <Badge key={index} variant="secondary" className="text-xs">
                                                                            {reaction.reactionType} {reaction.user.displayName}
                                                                        </Badge>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    ) : (
                                        <div className="text-center py-8 text-muted-foreground">
                                            Select a team and channel to view messages
                                        </div>
                                    )}
                                </div>
                            </TabsContent>

                            {/* Meetings Tab */}
                            <TabsContent value="meetings" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search meetings..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#2B579A] hover:bg-[#204275]"
                                        onClick={() => setIsMeetingOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Schedule Meeting
                                    </Button>
                                </div>

                                <div className="space-y-4">
                                    {loading.meetings ? (
                                        <div className="flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#2B579A]" />
                                        </div>
                                    ) : (
                                        filteredMeetings.map((meeting) => (
                                            <Card key={meeting.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex space-x-4 items-start">
                                                        <User className="w-6 h-6 text-[#2B579A]" />
                                                        <div className="flex-1 space-y-2">
                                                            <div className="flex justify-between w-full">
                                                                <span className="font-bold">{meeting.subject}</span>
                                                                {meeting.isOnlineMeeting && (
                                                                    <Badge className="bg-blue-100 text-blue-800 hover:bg-blue-200">
                                                                        <User className="mr-1 w-3 h-3" />
                                                                        Online Meeting
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                            {meeting.body?.content && (
                                                                <p className="text-sm text-muted-foreground">
                                                                    {meeting.body.content.substring(0, 200)}
                                                                    {meeting.body.content.length > 200 && "..."}
                                                                </p>
                                                            )}
                                                            <div className="flex space-x-4 text-sm text-muted-foreground">
                                                                <span>
                                                                    📅 {formatDate(meeting.start.dateTime)} -{" "}
                                                                    {formatDate(meeting.end.dateTime)}
                                                                </span>
                                                            </div>
                                                            {meeting.location && (
                                                                <p className="text-sm text-muted-foreground">
                                                                    📍 {meeting.location.displayName}
                                                                </p>
                                                            )}
                                                            {meeting.attendees && meeting.attendees.length > 0 && (
                                                                <div className="flex flex-wrap gap-2">
                                                                    {meeting.attendees.slice(0, 3).map((attendee) => (
                                                                        <Badge
                                                                            key={attendee.emailAddress.address}
                                                                            variant={getStatusVariant(attendee.status.response)}
                                                                        >
                                                                            {attendee.emailAddress.name}
                                                                        </Badge>
                                                                    ))}
                                                                    {meeting.attendees.length > 3 && (
                                                                        <Badge variant="secondary">
                                                                            +{meeting.attendees.length - 3} more
                                                                        </Badge>
                                                                    )}
                                                                </div>
                                                            )}
                                                            {meeting.joinUrl && (
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline"
                                                                    onClick={() => window.open(meeting.joinUrl, "_blank")}
                                                                >
                                                                    <User className="mr-2 w-4 h-4" />
                                                                    Join Meeting
                                                                </Button>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Users Tab */}
                            <TabsContent value="users" className="space-y-6 mt-6">
                                <div className="relative">
                                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                    <Input
                                        placeholder="Search users..."
                                        value={searchQuery}
                                        onChange={(e) => setSearchQuery(e.target.value)}
                                        className="pl-8"
                                    />
                                </div>

                                {loading.users ? (
                                    <div className="flex justify-center py-8">
                                        <Loader2 className="w-8 h-8 animate-spin text-[#2B579A]" />
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                        {filteredUsers.map((user) => (
                                            <Card key={user.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex space-x-4">
                                                        <Avatar className="w-12 h-12">
                                                            <AvatarImage src="" alt={user.displayName} />
                                                            <AvatarFallback>{user.displayName.charAt(0)}</AvatarFallback>
                                                        </Avatar>
                                                        <div className="flex-1 space-y-1">
                                                            <div className="flex items-center space-x-2">
                                                                <span className="font-bold">{user.displayName}</span>
                                                                <Badge variant={user.accountEnabled ? "default" : "destructive"}>
                                                                    {user.accountEnabled ? "Active" : "Inactive"}
                                                                </Badge>
                                                            </div>
                                                            <p className="text-sm text-muted-foreground">
                                                                {user.mail || user.userPrincipalName}
                                                            </p>
                                                            {user.jobTitle && (
                                                                <p className="text-sm text-muted-foreground">
                                                                    {user.jobTitle}
                                                                </p>
                                                            )}
                                                            {user.department && (
                                                                <p className="text-xs text-muted-foreground">
                                                                    {user.department}
                                                                </p>
                                                            )}
                                                            {user.officeLocation && (
                                                                <p className="text-xs text-muted-foreground">
                                                                    📍 {user.officeLocation}
                                                                </p>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))}
                                    </div>
                                )}
                            </TabsContent>
                        </Tabs>

                        {/* Create Team Modal */}
                        <Dialog open={isTeamOpen} onOpenChange={setIsTeamOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Create Team</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Team Name</label>
                                        <Input
                                            placeholder="Enter team name"
                                            value={teamForm.name}
                                            onChange={(e) =>
                                                setTeamForm({
                                                    ...teamForm,
                                                    name: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Team description"
                                            value={teamForm.description}
                                            onChange={(e) =>
                                                setTeamForm({
                                                    ...teamForm,
                                                    description: e.target.value,
                                                })
                                            }
                                            rows={3}
                                        />
                                    </div>
                                    <div className="flex space-x-4">
                                        <div className="flex-1 space-y-2">
                                            <label className="text-sm font-medium leading-none">Visibility</label>
                                            <Select
                                                value={teamForm.visibility}
                                                onValueChange={(value) =>
                                                    setTeamForm({
                                                        ...teamForm,
                                                        visibility: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="public">Public</SelectItem>
                                                    <SelectItem value="private">Private</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="flex-1 space-y-2">
                                            <label className="text-sm font-medium leading-none">Specialization</label>
                                            <Select
                                                value={teamForm.specialization}
                                                onValueChange={(value) =>
                                                    setTeamForm({
                                                        ...teamForm,
                                                        specialization: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="none">None</SelectItem>
                                                    <SelectItem value="educationStandard">Education Standard</SelectItem>
                                                    <SelectItem value="educationClass">Education Class</SelectItem>
                                                    <SelectItem value="educationProfessionalLearning">Education Professional Learning</SelectItem>
                                                    <SelectItem value="educationStaff">Education Staff</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Classification</label>
                                        <Input
                                            placeholder="Team classification"
                                            value={teamForm.classification}
                                            onChange={(e) =>
                                                setTeamForm({
                                                    ...teamForm,
                                                    classification: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsTeamOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2B579A] hover:bg-[#204275]"
                                        onClick={createTeam}
                                        disabled={!teamForm.name}
                                    >
                                        Create Team
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
                                            placeholder="Enter channel name"
                                            value={channelForm.name}
                                            onChange={(e) =>
                                                setChannelForm({
                                                    ...channelForm,
                                                    name: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Channel description"
                                            value={channelForm.description}
                                            onChange={(e) =>
                                                setChannelForm({
                                                    ...channelForm,
                                                    description: e.target.value,
                                                })
                                            }
                                            rows={3}
                                        />
                                    </div>
                                    <div className="flex space-x-4">
                                        <div className="flex-1 space-y-2">
                                            <label className="text-sm font-medium leading-none">Membership Type</label>
                                            <Select
                                                value={channelForm.membership_type}
                                                onValueChange={(value) =>
                                                    setChannelForm({
                                                        ...channelForm,
                                                        membership_type: value,
                                                    })
                                                }
                                            >
                                                <SelectTrigger>
                                                    <SelectValue />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="standard">Standard</SelectItem>
                                                    <SelectItem value="private">Private</SelectItem>
                                                    <SelectItem value="shared">Shared</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <div className="flex-1 flex items-end pb-2">
                                            <div className="flex items-center space-x-2">
                                                <Checkbox
                                                    id="favorite"
                                                    checked={channelForm.is_favorite_by_default}
                                                    onCheckedChange={(checked) =>
                                                        setChannelForm({
                                                            ...channelForm,
                                                            is_favorite_by_default: checked as boolean,
                                                        })
                                                    }
                                                />
                                                <label
                                                    htmlFor="favorite"
                                                    className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                                >
                                                    Favorite by default
                                                </label>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsChannelOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2B579A] hover:bg-[#204275]"
                                        onClick={createChannel}
                                        disabled={!channelForm.name}
                                    >
                                        Create Channel
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Send Message Modal */}
                        <Dialog open={isMessageOpen} onOpenChange={setIsMessageOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Send Message</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Message</label>
                                        <Textarea
                                            placeholder="Type your message..."
                                            value={messageForm.content}
                                            onChange={(e) =>
                                                setMessageForm({
                                                    ...messageForm,
                                                    content: e.target.value,
                                                })
                                            }
                                            rows={6}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Importance</label>
                                        <Select
                                            value={messageForm.importance}
                                            onValueChange={(value) =>
                                                setMessageForm({
                                                    ...messageForm,
                                                    importance: value,
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="low">Low</SelectItem>
                                                <SelectItem value="normal">Normal</SelectItem>
                                                <SelectItem value="high">High</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Mention Users</label>
                                        <Select
                                            value={messageForm.mentioned_users[0] || ""}
                                            onValueChange={(value) =>
                                                setMessageForm({
                                                    ...messageForm,
                                                    mentioned_users: value ? [value] : [],
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select users to mention" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {users.map((user) => (
                                                    <SelectItem key={user.id} value={user.id}>
                                                        {user.displayName}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsMessageOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2B579A] hover:bg-[#204275]"
                                        onClick={sendMessage}
                                        disabled={!messageForm.content}
                                    >
                                        Send Message
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Schedule Meeting Modal */}
                        <Dialog open={isMeetingOpen} onOpenChange={setIsMeetingOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Schedule Meeting</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Subject</label>
                                        <Input
                                            placeholder="Meeting subject"
                                            value={meetingForm.subject}
                                            onChange={(e) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    subject: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Meeting description"
                                            value={meetingForm.body}
                                            onChange={(e) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    body: e.target.value,
                                                })
                                            }
                                            rows={4}
                                        />
                                    </div>
                                    <div className="flex space-x-4">
                                        <div className="flex-1 space-y-2">
                                            <label className="text-sm font-medium leading-none">Start Time</label>
                                            <Input
                                                type="datetime-local"
                                                value={meetingForm.start_time}
                                                onChange={(e) =>
                                                    setMeetingForm({
                                                        ...meetingForm,
                                                        start_time: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                        <div className="flex-1 space-y-2">
                                            <label className="text-sm font-medium leading-none">End Time</label>
                                            <Input
                                                type="datetime-local"
                                                value={meetingForm.end_time}
                                                onChange={(e) =>
                                                    setMeetingForm({
                                                        ...meetingForm,
                                                        end_time: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Attendees</label>
                                        <Input
                                            placeholder="Enter email addresses (comma separated)"
                                            value={meetingForm.attendees.join(", ")}
                                            onChange={(e) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    attendees: e.target.value
                                                        .split(",")
                                                        .map((s) => s.trim())
                                                        .filter((s) => s),
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <Checkbox
                                            id="online"
                                            checked={meetingForm.is_online_meeting}
                                            onCheckedChange={(checked) =>
                                                setMeetingForm({
                                                    ...meetingForm,
                                                    is_online_meeting: checked as boolean,
                                                })
                                            }
                                        />
                                        <label
                                            htmlFor="online"
                                            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                                        >
                                            Online Meeting
                                        </label>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsMeetingOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#2B579A] hover:bg-[#204275]"
                                        onClick={createMeeting}
                                        disabled={
                                            !meetingForm.subject ||
                                            !meetingForm.start_time ||
                                            !meetingForm.end_time
                                        }
                                    >
                                        Schedule Meeting
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

export default TeamsIntegration;
