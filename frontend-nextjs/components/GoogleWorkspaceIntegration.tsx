/**
 * Google Workspace Integration Component
 * Complete Google Workspace productivity suite integration
 */

import React, { useState, useEffect } from "react";
import {
    FileEdit,
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
    Mail,
    MessageSquare,
    Calendar,
    FileText,
    FileSpreadsheet,
    Presentation,
    File,
    Loader2,
    MapPin,
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

// Types
interface GoogleDoc {
    id: string;
    name: string;
    mimeType: string;
    createdTime: string;
    modifiedTime: string;
    size: string;
    webViewLink: string;
    webContentLink: string;
    owners: Array<{
        displayName: string;
        email: string;
        photoLink: string;
    }>;
    permissions: Array<{
        id: string;
        type: string;
        role: string;
        emailAddress?: string;
        displayName?: string;
    }>;
    capabilities: {
        canEdit: boolean;
        canComment: boolean;
        canView: boolean;
        canCopy: boolean;
    };
    thumbnailLink?: string;
}

interface GoogleSheet {
    id: string;
    name: string;
    createdTime: string;
    modifiedTime: string;
    size: string;
    webViewLink: string;
    webContentLink: string;
    owners: Array<{
        displayName: string;
        email: string;
        photoLink: string;
    }>;
    sheets: Array<{
        properties: {
            sheetId: number;
            title: string;
            index: number;
            sheetType: string;
            gridProperties: {
                rowCount: number;
                columnCount: number;
            };
        };
    }>;
    spreadsheetId: string;
    spreadsheetUrl: string;
}

interface GoogleEvent {
    id: string;
    summary: string;
    description?: string;
    location?: string;
    start: {
        dateTime: string;
        timeZone?: string;
    };
    end: {
        dateTime: string;
        timeZone?: string;
    };
    attendees?: Array<{
        email: string;
        displayName?: string;
        responseStatus: string;
    }>;
    organizer: {
        email: string;
        displayName?: string;
    };
    created: string;
    updated: string;
    recurringEventId?: string;
    visibility: string;
    transparency: string;
    status: string;
    kind: string;
}

interface GoogleEmail {
    id: string;
    threadId: string;
    labelIds: string[];
    snippet: string;
    internalDate: string;
    payload: {
        headers: Array<{
            name: string;
            value: string;
        }>;
        mimeType: string;
        parts?: Array<{
            mimeType: string;
            body?: {
                data: string;
                size: number;
            };
        }>;
    };
    sizeEstimate: number;
    raw: string;
    historyId: string;
}

const GoogleWorkspaceIntegration: React.FC = () => {
    const [docs, setDocs] = useState<GoogleDoc[]>([]);
    const [sheets, setSheets] = useState<GoogleSheet[]>([]);
    const [events, setEvents] = useState<GoogleEvent[]>([]);
    const [emails, setEmails] = useState<GoogleEmail[]>([]);
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedFolder, setSelectedFolder] = useState("");
    const [loading, setLoading] = useState({
        docs: false,
        sheets: false,
        events: false,
        emails: false,
    });

    const [isDocOpen, setIsDocOpen] = useState(false);
    const [isEventOpen, setIsEventOpen] = useState(false);

    const [newDoc, setNewDoc] = useState({
        title: "",
        type: "document",
        folder: "",
    });

    const [newEvent, setNewEvent] = useState({
        summary: "",
        description: "",
        location: "",
        startTime: "",
        endTime: "",
        attendees: [] as string[],
    });

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/google-workspace/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadDocs();
                loadSheets();
                loadEvents();
                loadEmails();
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

    // Load Google Workspace data
    const loadDocs = async () => {
        setLoading((prev) => ({ ...prev, docs: true }));
        try {
            const response = await fetch("/api/integrations/google-workspace/docs", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 50,
                    folder: selectedFolder,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setDocs(data.data?.files || []);
            }
        } catch (error) {
            console.error("Failed to load documents:", error);
            toast({
                title: "Error",
                description: "Failed to load documents from Google Workspace",
                variant: "destructive",
            });
        } finally {
            setLoading((prev) => ({ ...prev, docs: false }));
        }
    };

    const loadSheets = async () => {
        setLoading((prev) => ({ ...prev, sheets: true }));
        try {
            const response = await fetch("/api/integrations/google-workspace/sheets", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setSheets(data.data?.files || []);
            }
        } catch (error) {
            console.error("Failed to load sheets:", error);
        } finally {
            setLoading((prev) => ({ ...prev, sheets: false }));
        }
    };

    const loadEvents = async () => {
        setLoading((prev) => ({ ...prev, events: true }));
        try {
            const response = await fetch("/api/integrations/google-workspace/events", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 50,
                    start_date: new Date().toISOString(),
                    end_date: new Date(
                        Date.now() + 7 * 24 * 60 * 60 * 1000
                    ).toISOString(),
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

    const loadEmails = async () => {
        setLoading((prev) => ({ ...prev, emails: true }));
        try {
            const response = await fetch("/api/integrations/google-workspace/emails", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 50,
                    label_ids: ["INBOX"],
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setEmails(data.data?.messages || []);
            }
        } catch (error) {
            console.error("Failed to load emails:", error);
        } finally {
            setLoading((prev) => ({ ...prev, emails: false }));
        }
    };

    const createDoc = async () => {
        if (!newDoc.title) return;

        try {
            const response = await fetch("/api/integrations/google-workspace/docs/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    title: newDoc.title,
                    type: newDoc.type,
                    folder: newDoc.folder,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: `${newDoc.type} created successfully`,
                });
                setIsDocOpen(false);
                setNewDoc({ title: "", type: "document", folder: "" });
                loadDocs();
            }
        } catch (error) {
            console.error("Failed to create document:", error);
            toast({
                title: "Error",
                description: "Failed to create document",
                variant: "destructive",
            });
        }
    };

    const createEvent = async () => {
        if (!newEvent.summary || !newEvent.startTime || !newEvent.endTime) return;

        try {
            const response = await fetch("/api/integrations/google-workspace/events/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    summary: newEvent.summary,
                    description: newEvent.description,
                    location: newEvent.location,
                    start: { dateTime: newEvent.startTime },
                    end: { dateTime: newEvent.endTime },
                    attendees: newEvent.attendees.map(email => ({ email })),
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Event created successfully",
                });
                setIsEventOpen(false);
                setNewEvent({
                    summary: "",
                    description: "",
                    location: "",
                    startTime: "",
                    endTime: "",
                    attendees: [],
                });
                loadEvents();
            }
        } catch (error) {
            console.error("Failed to create event:", error);
            toast({
                title: "Error",
                description: "Failed to create event",
                variant: "destructive",
            });
        }
    };

    // Filter data based on search
    const filteredDocs = docs.filter(
        (doc) =>
            doc.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredSheets = sheets.filter(
        (sheet) =>
            sheet.name.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredEvents = events.filter(
        (event) =>
            event.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
            event.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            event.location?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Stats calculations
    const totalDocs = docs.length;
    const totalSheets = sheets.length;
    const totalEvents = events.length;
    const totalEmails = emails.length;
    const upcomingEvents = events.filter(
        (event) => new Date(event.start.dateTime) > new Date()
    ).length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadDocs();
            loadSheets();
            loadEvents();
            loadEmails();
        }
    }, [connected]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const getMimeTypeIcon = (mimeType: string): any => {
        if (mimeType === "application/vnd.google-apps.document") {
            return FileText;
        } else if (mimeType === "application/vnd.google-apps.spreadsheet") {
            return FileSpreadsheet;
        } else if (mimeType === "application/vnd.google-apps.presentation") {
            return Presentation;
        } else if (mimeType === "application/pdf") {
            return File;
        } else {
            return Clock;
        }
    };

    const getMimeTypeColor = (mimeType: string): string => {
        if (mimeType === "application/vnd.google-apps.document") {
            return "text-blue-500";
        } else if (mimeType === "application/vnd.google-apps.spreadsheet") {
            return "text-green-500";
        } else if (mimeType === "application/vnd.google-apps.presentation") {
            return "text-orange-500";
        } else if (mimeType === "application/pdf") {
            return "text-red-500";
        } else {
            return "text-gray-500";
        }
    };

    const getResponseStatusVariant = (status: string): "default" | "secondary" | "destructive" | "outline" => {
        switch (status) {
            case "accepted":
                return "default"; // Green-ish usually, but default is black/white in shadcn. We might need custom classes for colors if strictly needed, but variants are safer.
            case "tentative":
                return "secondary";
            case "declined":
                return "destructive";
            case "needsAction":
                return "outline";
            default:
                return "outline";
        }
    };

    // Render connection status
    if (!connected && healthStatus !== "unknown") {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
                    <div className="space-y-2">
                        <h2 className="text-2xl font-semibold">Connect Google Workspace</h2>
                        <p className="text-muted-foreground mb-6">
                            Connect your Google Workspace account to start managing documents,
                            spreadsheets, calendars, and emails
                        </p>
                    </div>

                    <Card className="max-w-md w-full">
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center space-y-4">
                                <FileEdit className="w-16 h-16 text-gray-400 mb-4" />
                                <h3 className="text-xl font-semibold">Google Workspace</h3>
                                <p className="text-muted-foreground mt-2">
                                    Complete productivity suite integration
                                </p>

                                <Button
                                    size="lg"
                                    className="w-full bg-blue-600 hover:bg-blue-700"
                                    onClick={() =>
                                    (window.location.href =
                                        "/api/integrations/google-workspace/auth/start")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Google Workspace
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
                        <FileEdit className="w-8 h-8 text-blue-500" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Google Workspace Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Complete productivity suite (Docs, Sheets, Slides, Keep, Tasks)
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
                </div>

                {/* Services Overview */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Documents</p>
                                <div className="text-2xl font-bold">{totalDocs}</div>
                                <p className="text-xs text-muted-foreground">Google Docs files</p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Spreadsheets</p>
                                <div className="text-2xl font-bold">{totalSheets}</div>
                                <p className="text-xs text-muted-foreground">Google Sheets files</p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Events</p>
                                <div className="text-2xl font-bold">{upcomingEvents}</div>
                                <p className="text-xs text-muted-foreground">{totalEvents} total</p>
                            </div>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardContent className="pt-6">
                            <div className="space-y-1">
                                <p className="text-sm font-medium text-muted-foreground">Emails</p>
                                <div className="text-2xl font-bold">{totalEmails}</div>
                                <p className="text-xs text-muted-foreground">In Gmail</p>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Main Content Tabs */}
                <Tabs defaultValue="documents">
                    <TabsList>
                        <TabsTrigger value="documents">Documents</TabsTrigger>
                        <TabsTrigger value="spreadsheets">Spreadsheets</TabsTrigger>
                        <TabsTrigger value="calendar">Calendar</TabsTrigger>
                        <TabsTrigger value="gmail">Gmail</TabsTrigger>
                    </TabsList>

                    {/* Documents Tab */}
                    <TabsContent value="documents" className="space-y-6 mt-6">
                        <div className="flex items-center space-x-4">
                            <div className="relative flex-1">
                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search documents..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-8"
                                />
                            </div>
                            <Button
                                className="bg-blue-600 hover:bg-blue-700"
                                onClick={() => setIsDocOpen(true)}
                            >
                                <Plus className="mr-2 w-4 h-4" />
                                Create Document
                            </Button>
                        </div>

                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-4">
                                    {loading.docs ? (
                                        <div className="flex justify-center p-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                                        </div>
                                    ) : (
                                        docs.map((doc) => {
                                            const IconComponent = getMimeTypeIcon(doc.mimeType);
                                            return (
                                                <div
                                                    key={doc.id}
                                                    className="flex items-center p-4 border rounded-md hover:bg-gray-50 cursor-pointer transition-colors"
                                                    onClick={() => window.open(doc.webViewLink, "_blank")}
                                                >
                                                    <IconComponent className={`w-6 h-6 mr-4 ${getMimeTypeColor(doc.mimeType)}`} />
                                                    <div className="flex-1 space-y-1">
                                                        <p className="font-bold">{doc.name}</p>
                                                        <div className="flex items-center space-x-2">
                                                            <Badge variant="outline" className="text-xs">
                                                                {doc.mimeType.includes("document")
                                                                    ? "Document"
                                                                    : doc.mimeType.includes("spreadsheet")
                                                                        ? "Spreadsheet"
                                                                        : doc.mimeType.includes("presentation")
                                                                            ? "Presentation"
                                                                            : "File"}
                                                            </Badge>
                                                            <span className="text-xs text-muted-foreground">
                                                                {formatDate(doc.modifiedTime)}
                                                            </span>
                                                        </div>
                                                        {doc.owners.length > 0 && (
                                                            <div className="flex items-center space-x-2 mt-1">
                                                                <Avatar className="w-5 h-5">
                                                                    <AvatarImage src={doc.owners[0]?.photoLink} />
                                                                    <AvatarFallback>{doc.owners[0]?.displayName?.charAt(0)}</AvatarFallback>
                                                                </Avatar>
                                                                <span className="text-xs text-muted-foreground">
                                                                    {doc.owners[0]?.displayName}
                                                                </span>
                                                            </div>
                                                        )}
                                                    </div>
                                                    <ArrowRight className="w-4 h-4 text-gray-400" />
                                                </div>
                                            );
                                        })
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Spreadsheets Tab */}
                    <TabsContent value="spreadsheets" className="space-y-6 mt-6">
                        <div className="flex items-center space-x-4">
                            <div className="relative flex-1">
                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search spreadsheets..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-8"
                                />
                            </div>
                        </div>

                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-4">
                                    {loading.sheets ? (
                                        <div className="flex justify-center p-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-green-500" />
                                        </div>
                                    ) : (
                                        filteredSheets.map((sheet) => (
                                            <div
                                                key={sheet.id}
                                                className="flex items-center p-4 border rounded-md hover:bg-gray-50 cursor-pointer transition-colors"
                                                onClick={() => window.open(sheet.webViewLink, "_blank")}
                                            >
                                                <Settings className="w-6 h-6 mr-4 text-green-500" />
                                                <div className="flex-1 space-y-1">
                                                    <p className="font-bold">{sheet.name}</p>
                                                    <div className="flex items-center space-x-2">
                                                        <Badge variant="outline" className="text-xs border-green-200 text-green-700 bg-green-50">
                                                            Spreadsheet
                                                        </Badge>
                                                        <span className="text-xs text-muted-foreground">
                                                            {formatDate(sheet.modifiedTime)}
                                                        </span>
                                                    </div>
                                                    {sheet.sheets.length > 0 && (
                                                        <span className="text-xs text-muted-foreground block">
                                                            {sheet.sheets.length} sheets
                                                        </span>
                                                    )}
                                                </div>
                                                <ArrowRight className="w-4 h-4 text-gray-400" />
                                            </div>
                                        ))
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>

                    {/* Calendar Tab */}
                    <TabsContent value="calendar" className="space-y-6 mt-6">
                        <div className="flex items-center space-x-4">
                            <div className="relative flex-1">
                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search events..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-8"
                                />
                            </div>
                            <Button
                                className="bg-blue-600 hover:bg-blue-700"
                                onClick={() => setIsEventOpen(true)}
                            >
                                <Plus className="mr-2 w-4 h-4" />
                                Create Event
                            </Button>
                        </div>

                        <div className="space-y-4">
                            {loading.events ? (
                                <div className="flex justify-center p-8">
                                    <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                                </div>
                            ) : (
                                filteredEvents.map((event) => (
                                    <Card key={event.id}>
                                        <CardContent className="pt-6">
                                            <div className="flex items-start space-x-4">
                                                <Calendar className="w-6 h-6 text-blue-500 mt-1" />
                                                <div className="flex-1 space-y-2">
                                                    <p className="font-bold">{event.summary}</p>
                                                    {event.description && (
                                                        <p className="text-sm text-muted-foreground">
                                                            {event.description}
                                                        </p>
                                                    )}
                                                    <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                                                        <Clock className="w-4 h-4" />
                                                        <span>
                                                            {formatDate(event.start.dateTime)} -{" "}
                                                            {formatDate(event.end.dateTime)}
                                                        </span>
                                                    </div>
                                                    {event.location && (
                                                        <div className="flex items-center space-x-2 text-sm text-muted-foreground">
                                                            <MapPin className="w-4 h-4" />
                                                            <span>{event.location}</span>
                                                        </div>
                                                    )}
                                                    {event.attendees && event.attendees.length > 0 && (
                                                        <div className="flex flex-wrap gap-2 mt-2">
                                                            {event.attendees.map((attendee) => (
                                                                <Badge
                                                                    key={attendee.email}
                                                                    variant={getResponseStatusVariant(attendee.responseStatus)}
                                                                    className="text-xs"
                                                                >
                                                                    {attendee.displayName || attendee.email}
                                                                </Badge>
                                                            ))}
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

                    {/* Gmail Tab */}
                    <TabsContent value="gmail" className="space-y-6 mt-6">
                        <div className="flex items-center space-x-4">
                            <div className="relative flex-1">
                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search emails..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    className="pl-8"
                                />
                            </div>
                        </div>

                        <Card>
                            <CardContent className="pt-6">
                                <div className="space-y-4">
                                    {loading.emails ? (
                                        <div className="flex justify-center p-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-red-500" />
                                        </div>
                                    ) : (
                                        emails.map((email) => (
                                            <div key={email.id} className="p-4 border rounded-md hover:bg-gray-50 transition-colors">
                                                <div className="flex items-start space-x-4">
                                                    <Mail className="w-6 h-6 text-red-500 mt-1" />
                                                    <div className="flex-1 space-y-1">
                                                        <p className="font-bold text-sm">
                                                            {email.payload.headers.find(
                                                                (h) => h.name === "Subject"
                                                            )?.value || "No Subject"}
                                                        </p>
                                                        <p className="text-sm text-muted-foreground">
                                                            From:{" "}
                                                            {email.payload.headers.find(
                                                                (h) => h.name === "From"
                                                            )?.value}
                                                        </p>
                                                        <p className="text-xs text-muted-foreground">
                                                            {formatDate(email.internalDate)}
                                                        </p>
                                                        <p className="text-sm text-gray-600 mt-2">
                                                            {email.snippet}
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>
                            </CardContent>
                        </Card>
                    </TabsContent>
                </Tabs>

                {/* Create Document Modal */}
                <Dialog open={isDocOpen} onOpenChange={setIsDocOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Create Document</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                    Title
                                </label>
                                <Input
                                    placeholder="Enter document title"
                                    value={newDoc.title}
                                    onChange={(e) =>
                                        setNewDoc({
                                            ...newDoc,
                                            title: e.target.value,
                                        })
                                    }
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                    Type
                                </label>
                                <Select
                                    value={newDoc.type}
                                    onValueChange={(value) =>
                                        setNewDoc({
                                            ...newDoc,
                                            type: value,
                                        })
                                    }
                                >
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select type" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="document">Document</SelectItem>
                                        <SelectItem value="spreadsheet">Spreadsheet</SelectItem>
                                        <SelectItem value="presentation">Presentation</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsDocOpen(false)}>
                                Cancel
                            </Button>
                            <Button
                                className="bg-blue-600 hover:bg-blue-700"
                                onClick={createDoc}
                                disabled={!newDoc.title}
                            >
                                Create
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>

                {/* Create Event Modal */}
                <Dialog open={isEventOpen} onOpenChange={setIsEventOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Create Event</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                    Summary
                                </label>
                                <Input
                                    placeholder="Event title"
                                    value={newEvent.summary}
                                    onChange={(e) =>
                                        setNewEvent({
                                            ...newEvent,
                                            summary: e.target.value,
                                        })
                                    }
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                    Description
                                </label>
                                <Textarea
                                    placeholder="Event description"
                                    value={newEvent.description}
                                    onChange={(e) =>
                                        setNewEvent({
                                            ...newEvent,
                                            description: e.target.value,
                                        })
                                    }
                                    rows={3}
                                />
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                    Location
                                </label>
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
                                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                    Start Time
                                </label>
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
                                <label className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70">
                                    End Time
                                </label>
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
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsEventOpen(false)}>
                                Cancel
                            </Button>
                            <Button
                                className="bg-blue-600 hover:bg-blue-700"
                                onClick={createEvent}
                                disabled={
                                    !newEvent.summary ||
                                    !newEvent.startTime ||
                                    !newEvent.endTime
                                }
                            >
                                Create Event
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        </div>
    );
};

export default GoogleWorkspaceIntegration;
