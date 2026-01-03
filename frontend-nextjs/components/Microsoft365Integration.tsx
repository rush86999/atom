/**
 * Microsoft 365 Integration Component
 * Complete Microsoft 365 productivity suite integration
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
    MessageSquare,
    Mail,
    Calendar,
    Paperclip,
    Loader2,
    Video,
    FileText,
    Users,
    Trash2,
    Zap,
    Bot, // Assuming Bot icon exists or use generic
    Play,
    Database,
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

interface Microsoft365User {
    id: string;
    displayName: string;
    givenName: string;
    surname: string;
    userPrincipalName: string;
    jobTitle?: string;
    mail?: string;
    mobilePhone?: string;
    officeLocation?: string;
    department?: string;
    businessPhones: string[];
    accountEnabled: boolean;
}

interface Microsoft365Calendar {
    id: string;
    subject: string;
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
        address?: {
            street: string;
            city: string;
            state: string;
            postalCode: string;
            countryOrRegion: string;
        };
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
    organizer: {
        emailAddress: {
            name: string;
            address: string;
        };
    };
    isOnlineMeeting: boolean;
    onlineMeetingUrl?: string;
    createdDateTime: string;
    lastModifiedDateTime: string;
    recurrence?: any;
}

interface Microsoft365Email {
    id: string;
    subject: string;
    body: {
        contentType: string;
        content: string;
    };
    sender: {
        emailAddress: {
            name: string;
            address: string;
        };
    };
    from: {
        emailAddress: {
            name: string;
            address: string;
        };
    };
    toRecipients: Array<{
        emailAddress: {
            name: string;
            address: string;
        };
    }>;
    ccRecipients?: Array<{
        emailAddress: {
            name: string;
            address: string;
        };
    }>;
    bccRecipients?: Array<{
        emailAddress: {
            name: string;
            address: string;
        };
    }>;
    receivedDateTime: string;
    sentDateTime: string;
    hasAttachments: boolean;
    attachments?: Array<{
        id: string;
        contentType: string;
        name: string;
        size: number;
        isInline: boolean;
    }>;
    importance: "low" | "normal" | "high";
    isRead: boolean;
    isDraft: boolean;
    categories: string[];
    conversationId: string;
    webLink: string;
}

interface Microsoft365File {
    id: string;
    name: string;
    size: number;
    file?: {
        mimeType: string;
        hashes: {
            sha1Hash: string;
            quickXorHash: string;
        };
    };
    folder?: {
        childCount: number;
        view: {
            sortBy: string;
            sortOrder: string;
        };
    };
    createdDateTime: string;
    lastModifiedDateTime: string;
    parentReference: {
        driveId: string;
        driveType: string;
        id: string;
        name: string;
        path: string;
    };
    webUrl: string;
    createdBy?: {
        application?: {
            displayName: string;
            id: string;
        };
        device?: {
            displayName: string;
            id: string;
        };
        user?: {
            displayName: string;
            id: string;
        };
    };
    lastModifiedBy?: {
        application?: {
            displayName: string;
            id: string;
        };
        device?: {
            displayName: string;
            id: string;
        };
        user?: {
            displayName: string;
            id: string;
        };
    };
    sharePointIds?: {
        webUrl: string;
        siteId: string;
        siteUrl: string;
        listId: string;
        listItemId: string;
    }[];
}

interface Microsoft365Team {
    id: string;
    displayName: string;
    description: string;
    createdDateTime: string;
    updatedDateTime: string;
    classification?: string;
    specialization:
    | "none"
    | "educationStandard"
    | "educationClass"
    | "educationProfessionalLearning"
    | "educationStaff";
    visibility: "public" | "private";
    webUrl: string;
    internalId: string;
    isArchived: boolean;
    members?: Array<{
        displayName: string;
        id: string;
        roles: string[];
    }>;
    channels?: Array<{
        id: string;
        displayName: string;
        description: string;
        isFavoriteByDefault: boolean;
        membershipType: string;
        createdDateTime: string;
        lastModifiedDateTime: string;
    }>;
}

const Microsoft365Integration: React.FC = () => {
    const [users, setUsers] = useState<Microsoft365User[]>([]);
    const [calendars, setCalendars] = useState<Microsoft365Calendar[]>([]);
    const [emails, setEmails] = useState<Microsoft365Email[]>([]);
    const [files, setFiles] = useState<Microsoft365File[]>([]);
    const [teams, setTeams] = useState<Microsoft365Team[]>([]);
    const [userProfile, setUserProfile] = useState<Microsoft365User | null>(null);
    const [loading, setLoading] = useState({
        users: false,
        calendars: false,
        emails: false,
        files: false,
        teams: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedFolder, setSelectedFolder] = useState("");

    const [isEmailOpen, setIsEmailOpen] = useState(false);
    const [isCalendarOpen, setIsCalendarOpen] = useState(false);

    const [newEmail, setNewEmail] = useState({
        to: "",
        subject: "",
        body: "",
        importance: "normal" as "low" | "normal" | "high",
        cc: "",
    });

    const [newEvent, setNewEvent] = useState({
        subject: "",
        body: "",
        startTime: "",
        endTime: "",
        location: "",
        attendees: [] as string[],
    });

    const [webhookUrl, setWebhookUrl] = useState("https://api.atom.com/webhook");
    const [webhookResource, setWebhookResource] = useState("me/mailFolders('Inbox')/messages");

    const toast = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/microsoft365/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
                loadUsers();
                loadCalendars();
                loadEmails();
                loadFiles();
                loadTeams();
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

    // Load Microsoft 365 data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/microsoft365/user?access_token=fake_token", {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setUserProfile(data.data?.profile || data || null);
            }
        } catch (error) {
            console.error("Failed to load user profile:", error);
        } finally {
            setLoading((prev) => ({ ...prev, profile: false }));
        }
    };

    const loadUsers = async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        // Users endpoint not implemented in backend yet, skipping to avoid error
        setLoading((prev) => ({ ...prev, users: false }));
    };

    const loadCalendars = async () => {
        setLoading((prev) => ({ ...prev, calendars: true }));
        try {
            const startDate = new Date().toISOString();
            const endDate = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
            const response = await fetch(`/api/integrations/microsoft365/calendar/events?access_token=fake_token&start_date=${startDate}&end_date=${endDate}`, {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setCalendars(data.events || []);
            }
        } catch (error) {
            console.error("Failed to load calendars:", error);
        } finally {
            setLoading((prev) => ({ ...prev, calendars: false }));
        }
    };

    const loadEmails = async () => {
        setLoading((prev) => ({ ...prev, emails: true }));
        try {
            const response = await fetch("/api/integrations/microsoft365/outlook/messages?access_token=fake_token&folder_id=inbox&top=50", {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setEmails(data.messages || []);
            }
        } catch (error) {
            console.error("Failed to load emails:", error);
            toast({
                title: "Error",
                description: "Failed to load emails from Microsoft 365",
                variant: "error",
            });
        } finally {
            setLoading((prev) => ({ ...prev, emails: false }));
        }
    };

    const loadFiles = async () => {
        // Files endpoint not implemented in backend yet
        setLoading((prev) => ({ ...prev, files: false }));
    };

    const loadTeams = async () => {
        setLoading((prev) => ({ ...prev, teams: true }));
        try {
            const response = await fetch("/api/integrations/microsoft365/teams?access_token=fake_token", {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setTeams(data.teams || []);
            }
        } catch (error) {
            console.error("Failed to load teams:", error);
        } finally {
            setLoading((prev) => ({ ...prev, teams: false }));
        }
    };

    const sendEmail = async () => {
        if (!newEmail.to || !newEmail.subject || !newEmail.body) return;

        try {
            const response = await fetch(
                "/api/integrations/microsoft365/emails/send",
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: "current",
                        to: newEmail.to
                            .split(",")
                            .map((email) => ({ address: email.trim() })),
                        subject: newEmail.subject,
                        body: {
                            contentType: "text",
                            content: newEmail.body,
                        },
                        importance: newEmail.importance,
                        cc: newEmail.cc
                            ? newEmail.cc
                                .split(",")
                                .map((email) => ({ address: email.trim() }))
                            : [],
                    }),
                },
            );

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Email sent successfully",
                });
                setIsEmailOpen(false);
                setNewEmail({
                    to: "",
                    subject: "",
                    body: "",
                    importance: "normal",
                    cc: "",
                });
                loadEmails();
            }
        } catch (error) {
            console.error("Failed to send email:", error);
            toast({
                title: "Error",
                description: "Failed to send email",
                variant: "error",
            });
        }
    };

    const createCalendarEvent = async () => {
        if (!newEvent.subject || !newEvent.startTime || !newEvent.endTime) return;

        try {
            const response = await fetch(
                "/api/integrations/microsoft365/calendars/create",
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: "current",
                        subject: newEvent.subject,
                        body: {
                            contentType: "text",
                            content: newEvent.body,
                        },
                        start: {
                            dateTime: newEvent.startTime,
                            timeZone: "UTC",
                        },
                        end: {
                            dateTime: newEvent.endTime,
                            timeZone: "UTC",
                        },
                        location: {
                            displayName: newEvent.location,
                        },
                        attendees: newEvent.attendees.map((email) => ({
                            type: "required",
                            emailAddress: {
                                address: email,
                                name: email.split("@")[0],
                            },
                        })),
                    }),
                },
            );

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Calendar event created successfully",
                });
                setIsCalendarOpen(false);
                setNewEvent({
                    subject: "",
                    body: "",
                    startTime: "",
                    endTime: "",
                    location: "",
                    attendees: [],
                });
                loadCalendars();
            }
        } catch (error) {
            console.error("Failed to create calendar event:", error);
            toast({
                title: "Error",
                description: "Failed to create calendar event",
                variant: "error",
            });
        }
    };

    const createSubscription = async () => {
        try {
            const response = await fetch("/api/integrations/microsoft365/subscriptions", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    resource: webhookResource,
                    changeType: "created",
                    notificationUrl: webhookUrl,
                    expirationDateTime: new Date(Date.now() + 86400000).toISOString(), // +1 day
                }),
            });

            if (response.ok) {
                toast({ title: "Success", description: "Webhook subscription created!" });
            } else {
                throw new Error("Failed to create subscription");
            }
        } catch (error) {
            console.error("Subscription failed:", error);
            toast({ title: "Error", description: "Failed to create subscription", variant: "error" });
        }
    };

    const deleteItem = async (type: "message" | "event" | "file", id: string) => {
        if (!confirm("Are you sure you want to delete this item?")) return;

        let url = "";
        if (type === "message") url = `/api/integrations/microsoft365/outlook/messages/${id}`;
        if (type === "event") url = `/api/integrations/microsoft365/calendar/events/${id}`;
        if (type === "file") url = `/api/integrations/microsoft365/files/${id}`;

        try {
            const response = await fetch(url, { method: "DELETE" });
            if (response.ok) {
                toast({ title: "Success", description: "Item deleted successfully" });
                if (type === "message") loadEmails();
                if (type === "event") loadCalendars();
                if (type === "file") loadFiles();
            } else {
                throw new Error("Failed to delete");
            }
        } catch (error) {
            console.error("Delete failed:", error);
            toast({ title: "Error", description: "Failed to delete item", variant: "error" });
        }
    };

    // Filter data based on search
    const filteredEmails = emails.filter(
        (email) =>
            email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
            email.sender.emailAddress.name
                .toLowerCase()
                .includes(searchQuery.toLowerCase()) ||
            email.sender.emailAddress.address
                .toLowerCase()
                .includes(searchQuery.toLowerCase()),
    );

    const filteredCalendars = calendars.filter(
        (calendar) =>
            calendar.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
            calendar.location?.displayName
                .toLowerCase()
                .includes(searchQuery.toLowerCase()),
    );

    const filteredFiles = files.filter((file) =>
        file.name.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredUsers = users.filter(
        (user) =>
            user.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            user.userPrincipalName
                .toLowerCase()
                .includes(searchQuery.toLowerCase()) ||
            (user.mail &&
                user.mail.toLowerCase().includes(searchQuery.toLowerCase())),
    );

    const filteredTeams = teams.filter(
        (team) =>
            team.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
            team.description.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    // Stats calculations
    const totalUsers = users.length;
    const activeUsers = users.filter((u) => u.accountEnabled).length;
    const totalEmails = emails.length;
    const unreadEmails = emails.filter((e) => !e.isRead).length;
    const totalEvents = calendars.length;
    const upcomingEvents = calendars.filter(
        (e) => new Date(e.start.dateTime) > new Date(),
    ).length;
    const totalFiles = files.length;
    const totalTeams = teams.length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadUserProfile();
            loadUsers();
            loadCalendars();
            loadEmails();
            loadFiles();
            loadTeams();
        }
    }, [connected]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    const getImportanceVariant = (importance: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (importance) {
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

    const getFileIcon = (mimeType: string): any => {
        if (mimeType.startsWith("image/")) return FileText;
        if (mimeType.startsWith("video/")) return Video;
        if (mimeType.startsWith("audio/")) return FileText;
        if (mimeType.includes("pdf")) return FileText;
        if (mimeType.includes("word")) return FileText;
        if (mimeType.includes("excel") || mimeType.includes("spreadsheet"))
            return FileText;
        if (mimeType.includes("powerpoint") || mimeType.includes("presentation"))
            return FileText;
        if (mimeType.includes("zip") || mimeType.includes("rar"))
            return FileText;
        return FileText;
    };

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Settings className="w-8 h-8 text-[#0078D4]" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Microsoft 365 Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Complete productivity suite with Teams, Outlook, and OneDrive
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
                                <AvatarFallback>{userProfile.displayName.charAt(0)}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col">
                                <span className="font-bold">{userProfile.displayName}</span>
                                <span className="text-sm text-muted-foreground">
                                    {userProfile.jobTitle || userProfile.userPrincipalName}
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
                                    <h2 className="text-2xl font-bold">Connect Microsoft 365</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Microsoft 365 account to access Teams, Outlook,
                                        and OneDrive
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-[#0078D4] hover:bg-[#005a9e]"
                                    onClick={() =>
                                    (window.location.href =
                                        "/api/integrations/microsoft365/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Microsoft 365 Account
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
                                        <p className="text-sm font-medium text-muted-foreground">Users</p>
                                        <div className="text-2xl font-bold">{totalUsers}</div>
                                        <p className="text-xs text-muted-foreground">{activeUsers} active</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Emails</p>
                                        <div className="text-2xl font-bold">{totalEmails}</div>
                                        <p className="text-xs text-muted-foreground">{unreadEmails} unread</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Calendar Events</p>
                                        <div className="text-2xl font-bold">{upcomingEvents}</div>
                                        <p className="text-xs text-muted-foreground">{totalEvents} total</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Files</p>
                                        <div className="text-2xl font-bold">{totalFiles}</div>
                                        <p className="text-xs text-muted-foreground">OneDrive</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="outlook">
                            <TabsList>
                                <TabsTrigger value="outlook">Outlook</TabsTrigger>
                                <TabsTrigger value="calendar">Calendar</TabsTrigger>
                                <TabsTrigger value="onedrive">OneDrive</TabsTrigger>
                                <TabsTrigger value="teams">Teams</TabsTrigger>
                                <TabsTrigger value="users">Users</TabsTrigger>
                                <TabsTrigger value="automation" className="text-blue-600 font-semibold">
                                    <Zap className="w-4 h-4 mr-1" />
                                    Automation
                                </TabsTrigger>
                            </TabsList>

                            {/* Outlook Tab */}
                            <TabsContent value="outlook" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search emails..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#0078D4] hover:bg-[#005a9e]"
                                        onClick={() => setIsEmailOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Compose Email
                                    </Button>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <div className="flex flex-col divide-y">
                                            {loading.emails ? (
                                                <div className="flex justify-center py-8">
                                                    <Loader2 className="w-8 h-8 animate-spin text-[#0078D4]" />
                                                </div>
                                            ) : (
                                                filteredEmails.map((email) => (
                                                    <div
                                                        key={email.id}
                                                        className="flex items-start p-4 hover:bg-muted/50 cursor-pointer space-x-4"
                                                        onClick={() => window.open(email.webLink, "_blank")}
                                                    >
                                                        <Mail className="w-6 h-6 text-blue-500 mt-1" />
                                                        <div className="flex flex-col space-y-1 flex-1">
                                                            <div className="flex justify-between w-full">
                                                                <span className="font-bold">{email.subject}</span>
                                                                <div className="flex space-x-2">
                                                                    {!email.isRead && (
                                                                        <Badge variant="default">New</Badge>
                                                                    )}
                                                                    <Badge variant={getImportanceVariant(email.importance)}>
                                                                        {email.importance}
                                                                    </Badge>
                                                                </div>
                                                            </div>
                                                            <span className="text-sm text-muted-foreground">
                                                                From: {email.sender.emailAddress.name} (
                                                                {email.sender.emailAddress.address})
                                                            </span>
                                                            <div className="flex items-center space-x-2">
                                                                <span className="text-xs text-muted-foreground">
                                                                    {formatDate(email.receivedDateTime)}
                                                                </span>
                                                                <Button
                                                                    variant="ghost"
                                                                    size="icon"
                                                                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                                                    onClick={(e) => {
                                                                        e.stopPropagation();
                                                                        deleteItem("message", email.id);
                                                                    }}
                                                                >
                                                                    <Trash2 className="h-4 w-4" />
                                                                </Button>
                                                            </div>
                                                            {email.hasAttachments && (
                                                                <Badge variant="secondary" className="w-fit mt-1">
                                                                    <Paperclip className="w-3 h-3 mr-1" />
                                                                    Has attachments
                                                                </Badge>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Calendar Tab */}
                            <TabsContent value="calendar" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search calendar events..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Button
                                        className="bg-[#0078D4] hover:bg-[#005a9e]"
                                        onClick={() => setIsCalendarOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Event
                                    </Button>
                                </div>

                                <div className="space-y-4">
                                    {loading.calendars ? (
                                        <div className="flex justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-[#0078D4]" />
                                        </div>
                                    ) : (
                                        filteredCalendars.map((event) => (
                                            <Card key={event.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex items-start space-x-4">
                                                        <Calendar className="w-6 h-6 text-green-500 mt-1" />
                                                        <div className="flex flex-col space-y-2 flex-1">
                                                            <div className="flex justify-between w-full">
                                                                <span className="font-bold">{event.subject}</span>
                                                                <div className="flex items-center space-x-2">
                                                                    {event.isOnlineMeeting && (
                                                                        <Badge variant="secondary" className="flex items-center">
                                                                            <Video className="w-3 h-3 mr-1" />
                                                                            Online Meeting
                                                                        </Badge>
                                                                    )}
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="icon"
                                                                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                                                        onClick={(e) => {
                                                                            e.stopPropagation();
                                                                            deleteItem("event", event.id);
                                                                        }}
                                                                    >
                                                                        <Trash2 className="h-4 w-4" />
                                                                    </Button>
                                                                </div>
                                                            </div>
                                                            {event.body && (
                                                                <p className="text-sm text-muted-foreground">
                                                                    {event.body.content.substring(0, 200)}
                                                                    {event.body.content.length > 200 && "..."}
                                                                </p>
                                                            )}
                                                            <div className="flex space-x-4 text-sm text-muted-foreground">
                                                                <span>
                                                                    📅 {formatDate(event.start.dateTime)} -{" "}
                                                                    {formatDate(event.end.dateTime)}
                                                                </span>
                                                            </div>
                                                            {event.location && (
                                                                <span className="text-sm text-muted-foreground">
                                                                    📍 {event.location.displayName}
                                                                </span>
                                                            )}
                                                            {event.attendees && event.attendees.length > 0 && (
                                                                <div className="flex flex-wrap gap-2">
                                                                    {event.attendees.slice(0, 3).map((attendee) => (
                                                                        <Badge key={attendee.emailAddress.address} variant="outline">
                                                                            {attendee.emailAddress.name}
                                                                        </Badge>
                                                                    ))}
                                                                    {event.attendees.length > 3 && (
                                                                        <Badge variant="outline">
                                                                            +{event.attendees.length - 3} more
                                                                        </Badge>
                                                                    )}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* OneDrive Tab */}
                            <TabsContent value="onedrive" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search files..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <div className="flex flex-col divide-y">
                                            {loading.files ? (
                                                <div className="flex justify-center py-8">
                                                    <Loader2 className="w-8 h-8 animate-spin text-[#0078D4]" />
                                                </div>
                                            ) : (
                                                filteredFiles.map((file) => {
                                                    const FileIcon = getFileIcon(file.file?.mimeType || "");
                                                    return (
                                                        <div
                                                            key={file.id}
                                                            className="flex items-start p-4 hover:bg-muted/50 cursor-pointer space-x-4"
                                                            onClick={() => window.open(file.webUrl, "_blank")}
                                                        >
                                                            <FileIcon className="w-6 h-6 text-blue-500 mt-1" />
                                                            <div className="flex flex-col space-y-1 flex-1">
                                                                <span className="font-bold">{file.name}</span>
                                                                <div className="flex space-x-2 text-xs text-muted-foreground">
                                                                    <span>{formatFileSize(file.size)}</span>
                                                                    <span>• {formatDate(file.lastModifiedDateTime)}</span>
                                                                </div>
                                                            </div>
                                                            <Button
                                                                variant="ghost"
                                                                size="icon"
                                                                className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                                                onClick={(e) => {
                                                                    e.stopPropagation();
                                                                    deleteItem("file", file.id);
                                                                }}
                                                            >
                                                                <Trash2 className="h-4 w-4" />
                                                            </Button>
                                                        </div>
                                                    );
                                                })
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

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
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <div className="flex flex-col divide-y">
                                            {loading.teams ? (
                                                <div className="flex justify-center py-8">
                                                    <Loader2 className="w-8 h-8 animate-spin text-[#0078D4]" />
                                                </div>
                                            ) : (
                                                filteredTeams.map((team) => (
                                                    <div
                                                        key={team.id}
                                                        className="flex items-start p-4 hover:bg-muted/50 cursor-pointer space-x-4"
                                                        onClick={() => window.open(team.webUrl, "_blank")}
                                                    >
                                                        <MessageSquare className="w-6 h-6 text-purple-500 mt-1" />
                                                        <div className="flex flex-col space-y-1 flex-1">
                                                            <div className="flex justify-between w-full">
                                                                <span className="font-bold">{team.displayName}</span>
                                                                <div className="flex space-x-2">
                                                                    <Badge
                                                                        variant={
                                                                            team.visibility === "private"
                                                                                ? "secondary"
                                                                                : "default"
                                                                        }
                                                                    >
                                                                        {team.visibility}
                                                                    </Badge>
                                                                    {team.isArchived && (
                                                                        <Badge variant="destructive">Archived</Badge>
                                                                    )}
                                                                </div>
                                                            </div>
                                                            <p className="text-sm text-muted-foreground">
                                                                {team.description}
                                                            </p>
                                                            <div className="flex space-x-4 text-xs text-muted-foreground">
                                                                <span>Created: {formatDate(team.createdDateTime)}</span>
                                                                {team.channels && (
                                                                    <span>{team.channels.length} channels</span>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                        </div>
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
                                </div>

                                <Card>
                                    <CardContent className="p-0">
                                        <div className="flex flex-col divide-y">
                                            {loading.users ? (
                                                <div className="flex justify-center py-8">
                                                    <Loader2 className="w-8 h-8 animate-spin text-[#0078D4]" />
                                                </div>
                                            ) : (
                                                filteredUsers.map((user) => (
                                                    <div
                                                        key={user.id}
                                                        className="flex items-center p-4 hover:bg-muted/50 space-x-4"
                                                    >
                                                        <Avatar>
                                                            <AvatarFallback>{user.displayName.charAt(0)}</AvatarFallback>
                                                        </Avatar>
                                                        <div className="flex flex-col space-y-1 flex-1">
                                                            <div className="flex items-center space-x-2">
                                                                <span className="font-bold">{user.displayName}</span>
                                                                <Badge
                                                                    variant={user.accountEnabled ? "default" : "destructive"}
                                                                >
                                                                    {user.accountEnabled ? "Active" : "Inactive"}
                                                                </Badge>
                                                            </div>
                                                            <span className="text-sm text-muted-foreground">
                                                                {user.userPrincipalName}
                                                            </span>
                                                            {user.jobTitle && (
                                                                <span className="text-sm text-muted-foreground">
                                                                    {user.jobTitle}
                                                                </span>
                                                            )}
                                                            {user.department && (
                                                                <span className="text-xs text-muted-foreground">
                                                                    {user.department}
                                                                </span>
                                                            )}
                                                            {user.officeLocation && (
                                                                <span className="text-xs text-muted-foreground">
                                                                    📍 {user.officeLocation}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Automation Tab */}
                            <TabsContent value="automation" className="space-y-6 mt-6">
                                <Card className="border-blue-200 bg-blue-50/20">
                                    <CardHeader>
                                        <CardTitle className="text-blue-700 flex items-center">
                                            <Zap className="w-5 h-5 mr-2" />
                                            Advanced Automation Control
                                        </CardTitle>
                                        <p className="text-sm text-muted-foreground">
                                            Execute "Zero Human Interaction" workflows directly from this panel.
                                        </p>
                                    </CardHeader>
                                </Card>

                                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    {/* Excel Automation */}
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="flex items-center text-green-700">
                                                <FileText className="w-5 h-5 mr-2" />
                                                Excel Automation
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <div className="space-y-2">
                                                <label className="text-sm font-medium">Create Worksheet</label>
                                                <div className="flex gap-2">
                                                    <Input placeholder="Sheet Name (e.g. Report_2025)" id="excel-sheet-name" />
                                                    <Button variant="outline" onClick={() => {
                                                        const name = (document.getElementById("excel-sheet-name") as HTMLInputElement).value;
                                                        if (!name) return toast({ title: "Error", description: "Name required", variant: "destructive" });
                                                        fetch("/api/integrations/microsoft365/excel/execute?access_token=mock", {
                                                            method: "POST",
                                                            headers: { "Content-Type": "application/json" },
                                                            body: JSON.stringify({ action: "create_worksheet", params: { item_id: "mock_id", name } })
                                                        }).then(() => toast({ title: "Success", description: `Sheet '${name}' created via API` }));
                                                    }}>
                                                        <Play className="w-3 h-3 mr-1" /> Run
                                                    </Button>
                                                </div>
                                            </div>
                                            <div className="space-y-2">
                                                <label className="text-sm font-medium">Granular Row Update</label>
                                                <div className="text-xs text-muted-foreground mb-1">Simulates mapping dict &#123;"Region": "North", "Sales": "5000"&#125;</div>
                                                <Button className="w-full" variant="secondary" onClick={() => {
                                                    fetch("/api/integrations/microsoft365/excel/execute?access_token=mock", {
                                                        method: "POST",
                                                        headers: { "Content-Type": "application/json" },
                                                        body: JSON.stringify({
                                                            action: "append_row",
                                                            params: {
                                                                item_id: "mock_id",
                                                                table: "SalesTable",
                                                                column_mapping: { "Region": "North", "Sales": "5000" }
                                                            }
                                                        })
                                                    }).then(() => toast({ title: "Success", description: "Row appended with column mapping" }));
                                                }}>
                                                    Test Column Mapping
                                                </Button>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    {/* Teams Automation */}
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="flex items-center text-purple-700">
                                                <MessageSquare className="w-5 h-5 mr-2" />
                                                Teams Automation
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <div className="space-y-2">
                                                <label className="text-sm font-medium">Auto-Create Project Team</label>
                                                <Input placeholder="Project Name" id="team-name" />
                                                <Button className="w-full" onClick={() => {
                                                    const name = (document.getElementById("team-name") as HTMLInputElement).value;
                                                    if (!name) return;
                                                    fetch("/api/integrations/microsoft365/teams/execute?access_token=mock", {
                                                        method: "POST",
                                                        headers: { "Content-Type": "application/json" },
                                                        body: JSON.stringify({ action: "create_team", params: { display_name: name, description: "Auto-generated" } })
                                                    }).then(() => toast({ title: "Success", description: `Team '${name}' provisioning started` }));
                                                }}>
                                                    Provision Team
                                                </Button>
                                            </div>
                                            <div className="space-y-2">
                                                <label className="text-sm font-medium">Reply to Last Message</label>
                                                <Button variant="outline" className="w-full" onClick={() => {
                                                    fetch("/api/integrations/microsoft365/teams/execute?access_token=mock", {
                                                        method: "POST",
                                                        headers: { "Content-Type": "application/json" },
                                                        body: JSON.stringify({
                                                            action: "reply_to_message",
                                                            params: { team_id: "t1", channel_id: "c1", message_id: "m1", message: "Auto-reply: I am looking into this." }
                                                        })
                                                    }).then(() => toast({ title: "Success", description: "Bot replied to thread" }));
                                                }}>
                                                    Trigger Auto-Reply
                                                </Button>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    {/* Outlook Automation */}
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="flex items-center text-blue-700">
                                                <Mail className="w-5 h-5 mr-2" />
                                                Outlook Automation
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <div className="grid grid-cols-2 gap-4">
                                                <Button variant="outline" className="h-20 flex flex-col" onClick={() => {
                                                    fetch("/api/integrations/microsoft365/outlook/execute?access_token=mock", {
                                                        method: "POST",
                                                        headers: { "Content-Type": "application/json" },
                                                        body: JSON.stringify({ action: "move_email", params: { message_id: "1", destination_id: "archive" } })
                                                    }).then(() => toast({ title: "Success", description: "Email moved to Archive" }));
                                                }}>
                                                    <RefreshCw className="w-6 h-6 mb-2" />
                                                    Auto-Archive
                                                </Button>
                                                <Button variant="outline" className="h-20 flex flex-col" onClick={() => {
                                                    fetch("/api/integrations/microsoft365/outlook/execute?access_token=mock", {
                                                        method: "POST",
                                                        headers: { "Content-Type": "application/json" },
                                                        body: JSON.stringify({ action: "reply_email", params: { message_id: "1", comment: "Acknowledged." } })
                                                    }).then(() => toast({ title: "Success", description: "Sent quick acknowledgment" }));
                                                }}>
                                                    <Zap className="w-6 h-6 mb-2" />
                                                    Quick Ack
                                                </Button>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    {/* OneDrive Automation */}
                                    <Card>
                                        <CardHeader>
                                            <CardTitle className="flex items-center text-cyan-700">
                                                <Database className="w-5 h-5 mr-2" />
                                                OneDrive Automation
                                            </CardTitle>
                                        </CardHeader>
                                        <CardContent className="space-y-4">
                                            <div className="space-y-2">
                                                <label className="text-sm font-medium">Create Project Folder Structure</label>
                                                <Button className="w-full bg-cyan-600 hover:bg-cyan-700" onClick={() => {
                                                    // Chain of actions simulated
                                                    toast({ title: "Workflow Started", description: "Creating folders..." });
                                                    fetch("/api/integrations/microsoft365/onedrive/execute?access_token=mock", {
                                                        method: "POST",
                                                        headers: { "Content-Type": "application/json" },
                                                        body: JSON.stringify({ action: "create_folder", params: { name: "Project_Z_Assets" } })
                                                    }).then(() => toast({ title: "Success", description: "Folder structure created" }));
                                                }}>
                                                    Run "New Project" Workflow
                                                </Button>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>
                            </TabsContent>

                            {/* Webhooks Tab */}
                            <TabsContent value="webhooks" className="space-y-4">
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Webhook Triggers</CardTitle>
                                    </CardHeader>
                                    <CardContent className="space-y-4">
                                        <div className="grid w-full max-w-sm items-center gap-1.5">
                                            <label htmlFor="webhook-url">Notification URL</label>
                                            <Input
                                                id="webhook-url"
                                                value={webhookUrl}
                                                onChange={(e) => setWebhookUrl(e.target.value)}
                                                placeholder="https://api.atom.com/webhook"
                                            />
                                        </div>
                                        <div className="grid w-full max-w-sm items-center gap-1.5">
                                            <label htmlFor="webhook-resource">Resource</label>
                                            <Select
                                                value={webhookResource}
                                                onValueChange={setWebhookResource}
                                            >
                                                <SelectTrigger id="webhook-resource">
                                                    <SelectValue placeholder="Select resource" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="me/mailFolders('Inbox')/messages">Emails (Inbox)</SelectItem>
                                                    <SelectItem value="me/events">Calendar Events</SelectItem>
                                                    <SelectItem value="me/drive/root">OneDrive Files</SelectItem>
                                                </SelectContent>
                                            </Select>
                                        </div>
                                        <Button onClick={createSubscription}>
                                            Enable Notifications
                                        </Button>
                                    </CardContent>
                                </Card>
                            </TabsContent>
                        </Tabs>

                        {/* Compose Email Modal */}
                        <Dialog open={isEmailOpen} onOpenChange={setIsEmailOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Compose Email</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">To</label>
                                        <Input
                                            placeholder="recipient@example.com, recipient2@example.com"
                                            value={newEmail.to}
                                            onChange={(e) =>
                                                setNewEmail({
                                                    ...newEmail,
                                                    to: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Cc</label>
                                        <Input
                                            placeholder="cc@example.com"
                                            value={newEmail.cc}
                                            onChange={(e) =>
                                                setNewEmail({
                                                    ...newEmail,
                                                    cc: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Subject</label>
                                        <Input
                                            placeholder="Email subject"
                                            value={newEmail.subject}
                                            onChange={(e) =>
                                                setNewEmail({
                                                    ...newEmail,
                                                    subject: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Message</label>
                                        <Textarea
                                            placeholder="Your message..."
                                            value={newEmail.body}
                                            onChange={(e) =>
                                                setNewEmail({
                                                    ...newEmail,
                                                    body: e.target.value,
                                                })
                                            }
                                            rows={6}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Importance</label>
                                        <Select
                                            value={newEmail.importance}
                                            onValueChange={(value) =>
                                                setNewEmail({
                                                    ...newEmail,
                                                    importance: value as "low" | "normal" | "high",
                                                })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select Importance" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="low">Low</SelectItem>
                                                <SelectItem value="normal">Normal</SelectItem>
                                                <SelectItem value="high">High</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsEmailOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#0078D4] hover:bg-[#005a9e]"
                                        onClick={sendEmail}
                                        disabled={
                                            !newEmail.to || !newEmail.subject || !newEmail.body
                                        }
                                    >
                                        Send Email
                                    </Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {/* Create Event Modal */}
                        <Dialog open={isCalendarOpen} onOpenChange={setIsCalendarOpen}>
                            <DialogContent className="max-w-lg">
                                <DialogHeader>
                                    <DialogTitle>Create Calendar Event</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Subject</label>
                                        <Input
                                            placeholder="Event subject"
                                            value={newEvent.subject}
                                            onChange={(e) =>
                                                setNewEvent({
                                                    ...newEvent,
                                                    subject: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Event description"
                                            value={newEvent.body}
                                            onChange={(e) =>
                                                setNewEvent({
                                                    ...newEvent,
                                                    body: e.target.value,
                                                })
                                            }
                                            rows={4}
                                        />
                                    </div>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">Start Time</label>
                                            <Input
                                                type="datetime-local"
                                                value={newEvent.startTime}
                                                onChange={(e) =>
                                                    setNewEvent({
                                                        ...newEvent,
                                                        startTime: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                        <div className="space-y-2">
                                            <label className="text-sm font-medium leading-none">End Time</label>
                                            <Input
                                                type="datetime-local"
                                                value={newEvent.endTime}
                                                onChange={(e) =>
                                                    setNewEvent({
                                                        ...newEvent,
                                                        endTime: e.target.value,
                                                    })
                                                }
                                            />
                                        </div>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Location</label>
                                        <Input
                                            placeholder="Event location"
                                            value={newEvent.location}
                                            onChange={(e) =>
                                                setNewEvent({
                                                    ...newEvent,
                                                    location: e.target.value,
                                                })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Attendees</label>
                                        <Input
                                            placeholder="attendee@example.com, attendee2@example.com"
                                            value={newEvent.attendees.join(", ")}
                                            onChange={(e) =>
                                                setNewEvent({
                                                    ...newEvent,
                                                    attendees: e.target.value
                                                        .split(",")
                                                        .map((s) => s.trim())
                                                        .filter((s) => s),
                                                })
                                            }
                                        />
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsCalendarOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-[#0078D4] hover:bg-[#005a9e]"
                                        onClick={createCalendarEvent}
                                        disabled={
                                            !newEvent.subject ||
                                            !newEvent.startTime ||
                                            !newEvent.endTime
                                        }
                                    >
                                        Create Event
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

export default Microsoft365Integration;
