/**
 * Outlook Integration Component
 * Enhanced Microsoft Outlook integration
 * Complete email, calendar, contact, and task management interface
 */

import React, { useState, useEffect } from "react";
import {
    Mail,
    Clock,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    Settings,
    RefreshCw,
    Phone,
    Star,
    Calendar,
    User,
    CheckSquare,
    Loader2,
    Paperclip,
    MapPin,
    Briefcase,
    Building,
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
import { Progress } from "@/components/ui/progress";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface OutlookEmail {
    id: string;
    subject: string;
    from: {
        name: string;
        email: string;
    };
    to: Array<{
        name: string;
        email: string;
    }>;
    body: string;
    receivedDateTime: string;
    isRead: boolean;
    hasAttachments: boolean;
    importance: "low" | "normal" | "high";
    webLink?: string;
}

interface OutlookEvent {
    id: string;
    subject: string;
    start: {
        dateTime: string;
        timeZone: string;
    };
    end: {
        dateTime: string;
        timeZone: string;
    };
    location?: string;
    attendees?: Array<{
        name: string;
        email: string;
        type: string;
    }>;
    isAllDay: boolean;
    showAs: "free" | "tentative" | "busy" | "oof";
}

interface OutlookContact {
    id: string;
    displayName: string;
    emailAddresses: Array<{
        address: string;
        name?: string;
    }>;
    businessPhones: string[];
    mobilePhone?: string;
    jobTitle?: string;
    companyName?: string;
}

interface OutlookTask {
    id: string;
    title: string;
    status:
    | "notStarted"
    | "inProgress"
    | "completed"
    | "waitingOnOthers"
    | "deferred";
    importance: "low" | "normal" | "high";
    dueDateTime?: string;
    reminderDateTime?: string;
    categories: string[];
}

interface OutlookUser {
    id: string;
    displayName: string;
    mail: string;
    userPrincipalName: string;
    jobTitle?: string;
    officeLocation?: string;
}

const OutlookIntegration: React.FC = () => {
    const [emails, setEmails] = useState<OutlookEmail[]>([]);
    const [events, setEvents] = useState<OutlookEvent[]>([]);
    const [contacts, setContacts] = useState<OutlookContact[]>([]);
    const [tasks, setTasks] = useState<OutlookTask[]>([]);
    const [userProfile, setUserProfile] = useState<OutlookUser | null>(null);
    const [loading, setLoading] = useState({
        emails: false,
        events: false,
        contacts: false,
        tasks: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedFolder, setSelectedFolder] = useState("inbox");
    const [selectedImportance, setSelectedImportance] = useState("");

    const [isComposeOpen, setIsComposeOpen] = useState(false);
    const [newEmail, setNewEmail] = useState({
        to: "",
        subject: "",
        body: "",
        importance: "normal" as "low" | "normal" | "high",
    });

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/outlook/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
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

    // Load Outlook data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/outlook/profile", {
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

    const loadEmails = async () => {
        setLoading((prev) => ({ ...prev, emails: true }));
        try {
            const response = await fetch("/api/integrations/outlook/emails", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    folder: selectedFolder,
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setEmails(data.data?.emails || []);
            }
        } catch (error) {
            console.error("Failed to load emails:", error);
            toast({
                title: "Error",
                description: "Failed to load emails from Outlook",
                variant: "destructive",
            });
        } finally {
            setLoading((prev) => ({ ...prev, emails: false }));
        }
    };

    const loadEvents = async () => {
        setLoading((prev) => ({ ...prev, events: true }));
        try {
            const response = await fetch("/api/integrations/outlook/events", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    start_date: new Date().toISOString(),
                    end_date: new Date(
                        Date.now() + 7 * 24 * 60 * 60 * 1000
                    ).toISOString(),
                    limit: 20,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setEvents(data.data?.events || []);
            }
        } catch (error) {
            console.error("Failed to load events:", error);
        } finally {
            setLoading((prev) => ({ ...prev, events: false }));
        }
    };

    const loadContacts = async () => {
        setLoading((prev) => ({ ...prev, contacts: true }));
        try {
            const response = await fetch("/api/integrations/outlook/contacts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 30,
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

    const loadTasks = async () => {
        setLoading((prev) => ({ ...prev, tasks: true }));
        try {
            const response = await fetch("/api/integrations/outlook/tasks", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 20,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setTasks(data.data?.tasks || []);
            }
        } catch (error) {
            console.error("Failed to load tasks:", error);
        } finally {
            setLoading((prev) => ({ ...prev, tasks: false }));
        }
    };

    // Send email
    const sendEmail = async () => {
        try {
            const response = await fetch("/api/integrations/outlook/emails/send", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    to: newEmail.to,
                    subject: newEmail.subject,
                    body: newEmail.body,
                    importance: newEmail.importance,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Email sent successfully",
                });
                setIsComposeOpen(false);
                setNewEmail({ to: "", subject: "", body: "", importance: "normal" });
                loadEmails();
            }
        } catch (error) {
            console.error("Failed to send email:", error);
            toast({
                title: "Error",
                description: "Failed to send email",
                variant: "destructive",
            });
        }
    };

    // Filter emails based on search and filters
    const filteredEmails = emails.filter((email) => {
        const matchesSearch =
            email.subject.toLowerCase().includes(searchQuery.toLowerCase()) ||
            email.from.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            email.from.email.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesImportance =
            !selectedImportance || email.importance === selectedImportance;

        return matchesSearch && matchesImportance;
    });

    // Stats calculations
    const totalEmails = emails.length;
    const unreadEmails = emails.filter((email) => !email.isRead).length;
    const importantEmails = emails.filter(
        (email) => email.importance === "high"
    ).length;
    const upcomingEvents = events.filter(
        (event) => new Date(event.start.dateTime) > new Date()
    ).length;
    const completedTasks = tasks.filter(
        (task) => task.status === "completed"
    ).length;
    const completionRate =
        tasks.length > 0 ? (completedTasks / tasks.length) * 100 : 0;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadEmails();
            loadEvents();
            loadContacts();
            loadTasks();
        }
    }, [connected, selectedFolder]);

    const getImportanceVariant = (importance: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (importance) {
            case "high":
                return "destructive";
            case "normal":
                return "default"; // Blue-ish usually
            case "low":
                return "secondary";
            default:
                return "secondary";
        }
    };

    const getStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status) {
            case "completed":
                return "default"; // Green-ish
            case "inProgress":
                return "secondary"; // Orange-ish
            case "notStarted":
                return "outline"; // Gray
            case "waitingOnOthers":
                return "secondary"; // Yellow-ish
            case "deferred":
                return "destructive"; // Red
            default:
                return "secondary";
        }
    };

    const getStatusLabel = (status: string) => {
        switch (status) {
            case "completed":
                return "Completed";
            case "inProgress":
                return "In Progress";
            case "notStarted":
                return "Not Started";
            case "waitingOnOthers":
                return "Waiting";
            case "deferred":
                return "Deferred";
            default:
                return "Unknown";
        }
    };

    const formatDateTime = (dateTime: string) => {
        return (
            new Date(dateTime).toLocaleDateString() +
            " " +
            new Date(dateTime).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
            })
        );
    };

    // Render connection status
    if (!connected && healthStatus !== "unknown") {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
                    <div className="space-y-2">
                        <h2 className="text-2xl font-semibold">Connect Outlook</h2>
                        <p className="text-muted-foreground mb-6">
                            Connect your Outlook account to manage emails, calendar,
                            contacts, and tasks
                        </p>
                    </div>

                    <Card className="max-w-md w-full">
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center space-y-4">
                                <Mail className="w-16 h-16 text-blue-500 mb-4" />
                                <h3 className="text-xl font-semibold">Outlook Integration</h3>
                                <p className="text-muted-foreground mt-2">
                                    Email, calendar, contacts, and task management
                                </p>

                                <Button
                                    size="lg"
                                    className="w-full bg-blue-600 hover:bg-blue-700"
                                    onClick={() =>
                                        (window.location.href = "/api/auth/outlook/authorize")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Outlook Account
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
                        <Mail className="w-8 h-8 text-blue-500" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Outlook Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Email, calendar, contacts, and task management
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
                        {userProfile && (
                            <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
                                {userProfile.displayName}
                            </Badge>
                        )}
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={checkConnection}
                        >
                            <RefreshCw className="mr-2 w-3 h-3" />
                            Refresh Status
                        </Button>
                    </div>
                </div>

                {/* Stats Overview */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Total Emails</p>
                                <div className="text-2xl font-bold">{totalEmails}</div>
                                <p className="text-xs text-muted-foreground">In selected folder</p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Unread</p>
                                <div className="text-2xl font-bold">{unreadEmails}</div>
                                <p className="text-xs text-muted-foreground">Require attention</p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Important</p>
                                <div className="text-2xl font-bold">{importantEmails}</div>
                                <p className="text-xs text-muted-foreground">High priority</p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Upcoming Events</p>
                                <div className="text-2xl font-bold">{upcomingEvents}</div>
                                <p className="text-xs text-muted-foreground">Next 7 days</p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Task Completion</p>
                                <div className="text-2xl font-bold">{Math.round(completionRate)}%</div>
                                <Progress value={completionRate} className="h-2 mt-2" />
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Main Content Tabs */}
                <Tabs defaultValue="emails">
                    <TabsList>
                        <TabsTrigger value="emails">Emails</TabsTrigger>
                        <TabsTrigger value="calendar">Calendar</TabsTrigger>
                        <TabsTrigger value="contacts">Contacts</TabsTrigger>
                        <TabsTrigger value="tasks">Tasks</TabsTrigger>
                    </TabsList>

                    {/* Emails Tab */}
                    <TabsContent value="emails" className="space-y-6 mt-6">
                        <Card>
                            <CardContent className="pt-6">
                                <div className="flex flex-col md:flex-row gap-4 mb-6">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search emails..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <Select
                                        value={selectedFolder}
                                        onValueChange={setSelectedFolder}
                                    >
                                        <SelectTrigger className="w-[180px]">
                                            <SelectValue placeholder="Select folder" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="inbox">Inbox</SelectItem>
                                            <SelectItem value="sent">Sent Items</SelectItem>
                                            <SelectItem value="drafts">Drafts</SelectItem>
                                            <SelectItem value="archive">Archive</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Select
                                        value={selectedImportance}
                                        onValueChange={setSelectedImportance}
                                    >
                                        <SelectTrigger className="w-[180px]">
                                            <SelectValue placeholder="All Importance" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="high">High</SelectItem>
                                            <SelectItem value="normal">Normal</SelectItem>
                                            <SelectItem value="low">Low</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Button
                                        className="bg-blue-600 hover:bg-blue-700"
                                        onClick={() => setIsComposeOpen(true)}
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        New Email
                                    </Button>
                                </div>

                                {loading.emails ? (
                                    <div className="flex justify-center p-8">
                                        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                                    </div>
                                ) : filteredEmails.length === 0 ? (
                                    <div className="flex flex-col items-center justify-center py-12 text-center">
                                        <Mail className="w-12 h-12 text-gray-300 mb-4" />
                                        <p className="text-lg font-medium text-gray-900">No emails found</p>
                                        <p className="text-muted-foreground mb-4">Try adjusting your filters or search query</p>
                                        <Button variant="outline" onClick={() => setIsComposeOpen(true)}>
                                            Compose New Email
                                        </Button>
                                    </div>
                                ) : (
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>From</TableHead>
                                                <TableHead>Subject</TableHead>
                                                <TableHead>Importance</TableHead>
                                                <TableHead>Received</TableHead>
                                                <TableHead>Status</TableHead>
                                                <TableHead>Actions</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {filteredEmails.map((email) => (
                                                <TableRow key={email.id}>
                                                    <TableCell>
                                                        <div className="flex flex-col">
                                                            <span className="font-medium">{email.from.name}</span>
                                                            <span className="text-xs text-muted-foreground">{email.from.email}</span>
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <div className="flex flex-col max-w-[300px]">
                                                            <span className="font-medium truncate">{email.subject}</span>
                                                            {email.body && (
                                                                <span className="text-xs text-muted-foreground truncate">
                                                                    {email.body}
                                                                </span>
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant={getImportanceVariant(email.importance)}>
                                                            {email.importance}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell className="text-sm">
                                                        {formatDateTime(email.receivedDateTime)}
                                                    </TableCell>
                                                    <TableCell>
                                                        <div className="flex space-x-2">
                                                            {!email.isRead && (
                                                                <Badge variant="destructive">Unread</Badge>
                                                            )}
                                                            {email.hasAttachments && (
                                                                <Badge variant="secondary" className="flex items-center">
                                                                    <Paperclip className="w-3 h-3 mr-1" />
                                                                    Attachment
                                                                </Badge>
                                                            )}
                                                            {email.isRead && !email.hasAttachments && (
                                                                <CheckCircle className="w-4 h-4 text-green-500" />
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                    <TableCell>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => window.open(email.webLink, "_blank")}
                                                        >
                                                            <ArrowRight className="w-4 h-4" />
                                                        </Button>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                )}
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Calendar Tab */}
                    <TabsContent value="calendar" className="space-y-6 mt-6">
                        <Card>
                            <CardContent className="pt-6">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {events.map((event) => (
                                        <Card key={event.id}>
                                            <CardContent className="pt-6">
                                                <div className="space-y-3">
                                                    <div className="flex items-start justify-between">
                                                        <h3 className="font-bold text-lg">{event.subject}</h3>
                                                        <Badge variant={event.showAs === "busy" ? "destructive" : "default"}>
                                                            {event.showAs}
                                                        </Badge>
                                                    </div>
                                                    <div className="text-sm text-muted-foreground flex items-center">
                                                        <Clock className="w-4 h-4 mr-2" />
                                                        <span>
                                                            {formatDateTime(event.start.dateTime)} -{" "}
                                                            {formatDateTime(event.end.dateTime)}
                                                        </span>
                                                    </div>
                                                    {event.location && (
                                                        <div className="text-sm text-muted-foreground flex items-center">
                                                            <MapPin className="w-4 h-4 mr-2" />
                                                            <span>{event.location}</span>
                                                        </div>
                                                    )}
                                                    {event.attendees && event.attendees.length > 0 && (
                                                        <div className="pt-2">
                                                            <p className="text-xs font-medium mb-2">Attendees ({event.attendees.length})</p>
                                                            <div className="flex -space-x-2 overflow-hidden">
                                                                {event.attendees.slice(0, 3).map((attendee, index) => (
                                                                    <Avatar key={index} className="inline-block border-2 border-background w-8 h-8">
                                                                        <AvatarFallback className="bg-blue-100 text-blue-600 text-xs">
                                                                            {attendee.name.charAt(0)}
                                                                        </AvatarFallback>
                                                                    </Avatar>
                                                                ))}
                                                                {event.attendees.length > 3 && (
                                                                    <div className="flex items-center justify-center w-8 h-8 rounded-full border-2 border-background bg-muted text-[10px] font-medium">
                                                                        +{event.attendees.length - 3}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        </div>
                                                    )}
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Contacts Tab */}
                    <TabsContent value="contacts" className="space-y-6 mt-6">
                        <Card>
                            <CardContent className="pt-6">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {contacts.map((contact) => (
                                        <Card key={contact.id}>
                                            <CardContent className="pt-6">
                                                <div className="space-y-3">
                                                    <div className="flex items-center space-x-3">
                                                        <Avatar className="h-10 w-10">
                                                            <AvatarFallback className="bg-blue-100 text-blue-600">
                                                                {contact.displayName.charAt(0)}
                                                            </AvatarFallback>
                                                        </Avatar>
                                                        <div>
                                                            <h3 className="font-bold">{contact.displayName}</h3>
                                                            {contact.jobTitle && (
                                                                <p className="text-xs text-muted-foreground">{contact.jobTitle}</p>
                                                            )}
                                                        </div>
                                                    </div>

                                                    <div className="space-y-2 pt-2">
                                                        {contact.emailAddresses.map((email, index) => (
                                                            <div key={index} className="flex items-center text-sm text-muted-foreground">
                                                                <Mail className="w-4 h-4 mr-2" />
                                                                <span className="truncate">{email.address}</span>
                                                            </div>
                                                        ))}
                                                        {contact.businessPhones.length > 0 && (
                                                            <div className="flex items-center text-sm text-muted-foreground">
                                                                <Phone className="w-4 h-4 mr-2" />
                                                                <span>{contact.businessPhones[0]}</span>
                                                            </div>
                                                        )}
                                                        {contact.companyName && (
                                                            <div className="flex items-center text-sm text-muted-foreground">
                                                                <Building className="w-4 h-4 mr-2" />
                                                                <span>{contact.companyName}</span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Tasks Tab */}
                    <TabsContent value="tasks" className="space-y-6 mt-6">
                        <Card>
                            <CardContent className="pt-6">
                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {tasks.map((task) => (
                                        <Card key={task.id}>
                                            <CardContent className="pt-6">
                                                <div className="space-y-3">
                                                    <div className="flex justify-between items-start">
                                                        <h3 className="font-bold text-lg">{task.title}</h3>
                                                        <Badge variant={getImportanceVariant(task.importance)}>
                                                            {task.importance}
                                                        </Badge>
                                                    </div>

                                                    <Badge variant={getStatusVariant(task.status)} className="w-fit">
                                                        {getStatusLabel(task.status)}
                                                    </Badge>

                                                    {task.dueDateTime && (
                                                        <div className="flex items-center text-sm text-muted-foreground">
                                                            <Clock className="w-4 h-4 mr-2" />
                                                            <span>Due: {formatDateTime(task.dueDateTime)}</span>
                                                        </div>
                                                    )}

                                                    {task.categories.length > 0 && (
                                                        <div className="flex flex-wrap gap-2 pt-2">
                                                            {task.categories.map((category, index) => (
                                                                <Badge key={index} variant="outline" className="text-xs">
                                                                    {category}
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    )}
                                                </div>
                                            </CardContent>
                                        </Card>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>

                {/* Compose Email Modal */}
                <Dialog open={isComposeOpen} onOpenChange={setIsComposeOpen}>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Compose New Email</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">To</label>
                                <Input
                                    placeholder="recipient@example.com"
                                    value={newEmail.to}
                                    onChange={(e) =>
                                        setNewEmail({ ...newEmail, to: e.target.value })
                                    }
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Subject</label>
                                <Input
                                    placeholder="Email subject"
                                    value={newEmail.subject}
                                    onChange={(e) =>
                                        setNewEmail({ ...newEmail, subject: e.target.value })
                                    }
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
                                        <SelectValue placeholder="Select importance" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="low">Low</SelectItem>
                                        <SelectItem value="normal">Normal</SelectItem>
                                        <SelectItem value="high">High</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none">Body</label>
                                <Textarea
                                    placeholder="Email content"
                                    value={newEmail.body}
                                    onChange={(e) =>
                                        setNewEmail({ ...newEmail, body: e.target.value })
                                    }
                                    rows={8}
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsComposeOpen(false)}>
                                Cancel
                            </Button>
                            <Button
                                className="bg-blue-600 hover:bg-blue-700"
                                onClick={sendEmail}
                                disabled={!newEmail.to || !newEmail.subject || !newEmail.body}
                            >
                                Send Email
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

export default OutlookIntegration;
