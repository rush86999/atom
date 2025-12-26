import React, { useState, useEffect } from "react";
import {
    Settings,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    RefreshCw,
    Loader2,
    Eye,
    Database as DatabaseIcon,
    FileText,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface NotionPage {
    id: string;
    created_time: string;
    last_edited_time: string;
    properties: {
        title?: {
            title: Array<{ text: { content: string } }>;
        };
        status?: {
            select: { name: string; color?: string };
        };
        priority?: {
            select: { name: string; color?: string };
        };
        assignee?: {
            people: Array<{ name?: string; avatar_url?: string }>;
        };
        due_date?: {
            date: { start: string; end?: string };
        };
        tags?: {
            multi_select: Array<{ name: string; color?: string }>;
        };
        created_by?: {
            created_by: { name?: string; avatar_url?: string };
        };
    };
    parent: {
        type: string;
        page_id?: string;
        database_id?: string;
        workspace?: boolean;
    };
    url: string;
    archived: boolean;
    in_trash: boolean;
    public_url?: string;
}

interface NotionDatabase {
    id: string;
    created_time: string;
    last_edited_time: string;
    title: Array<{ text: { content: string } }>;
    properties: Record<string, any>;
    parent: {
        type: string;
        page_id?: string;
        workspace?: boolean;
    };
    url: string;
    archived: boolean;
    is_inline: boolean;
    description: Array<{ text: { content: string } }>;
    icon: {
        type: string;
        emoji?: string;
        file?: { url: string };
    };
    cover: {
        type: string;
        external?: { url: string };
    };
}

interface NotionUser {
    id: string;
    name?: string;
    avatar_url?: string;
    type: string;
    person?: {
        email: string;
    };
    bot?: {
        owner?: { type: string; user?: { object: string; id: string } };
    };
}

interface NotionSearchResult {
    object: string;
    id: string;
    created_time: string;
    last_edited_time: string;
    has_children: boolean;
    archived: boolean;
    properties?: any;
    title?: string;
    url: string;
}

const NotionIntegration: React.FC = () => {
    const [pages, setPages] = useState<NotionPage[]>([]);
    const [databases, setDatabases] = useState<NotionDatabase[]>([]);
    const [users, setUsers] = useState<NotionUser[]>([]);
    const [searchResults, setSearchResults] = useState<NotionSearchResult[]>([]);
    const [loading, setLoading] = useState({
        pages: false,
        databases: false,
        users: false,
        search: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedDatabase, setSelectedDatabase] = useState("");
    const [selectedFilter, setSelectedFilter] = useState("all");

    // Form states
    const [pageForm, setPageForm] = useState({
        parent_type: "page",
        parent_id: "",
        title: "",
        children: [] as any[],
    });

    const [databaseForm, setDatabaseForm] = useState({
        parent_type: "page",
        parent_id: "",
        title: "",
        properties: {} as any,
        is_inline: false,
    });

    const [isPageModalOpen, setIsPageModalOpen] = useState(false);
    const [isDatabaseModalOpen, setIsDatabaseModalOpen] = useState(false);

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/notion/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadDatabases();
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
    };

    // Load Notion data
    const loadPages = async (databaseId?: string) => {
        setLoading((prev) => ({ ...prev, pages: true }));
        try {
            const response = await fetch("/api/integrations/notion/pages", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    database_id: databaseId,
                    filter:
                        selectedFilter !== "all"
                            ? {
                                property: "status",
                                select: { equals: selectedFilter },
                            }
                            : undefined,
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setPages(data.data?.pages || []);
            }
        } catch (error) {
            console.error("Failed to load pages:", error);
            toast({
                title: "Error",
                description: "Failed to load pages from Notion",
                variant: "error",
            });
        } finally {
            setLoading((prev) => ({ ...prev, pages: false }));
        }
    };

    const loadDatabases = async () => {
        setLoading((prev) => ({ ...prev, databases: true }));
        try {
            const response = await fetch("/api/integrations/notion/databases", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setDatabases(data.data?.databases || []);
                if (data.data?.databases?.length > 0) {
                    setSelectedDatabase(data.data.databases[0].id);
                }
            }
        } catch (error) {
            console.error("Failed to load databases:", error);
        } finally {
            setLoading((prev) => ({ ...prev, databases: false }));
        }
    };

    const loadUsers = async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        try {
            const response = await fetch("/api/integrations/notion/users", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 50,
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

    const searchNotion = async () => {
        if (!searchQuery) return;

        setLoading((prev) => ({ ...prev, search: true }));
        try {
            const response = await fetch("/api/integrations/notion/search", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    query: searchQuery,
                    filter: {
                        property: "object",
                        value: selectedFilter === "all" ? undefined : selectedFilter,
                    },
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setSearchResults(data.data?.results || []);
            }
        } catch (error) {
            console.error("Failed to search:", error);
        } finally {
            setLoading((prev) => ({ ...prev, search: false }));
        }
    };

    const createPage = async () => {
        try {
            const response = await fetch("/api/integrations/notion/pages/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    parent: {
                        type: pageForm.parent_type,
                        [pageForm.parent_type === "database_id"
                            ? "database_id"
                            : "page_id"]: pageForm.parent_id,
                    },
                    properties: {
                        title: {
                            title: [
                                {
                                    text: {
                                        content: pageForm.title,
                                    },
                                },
                            ],
                        },
                    },
                    children: pageForm.children,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Page created successfully",
                });
                setIsPageModalOpen(false);
                setPageForm({
                    parent_type: "page",
                    parent_id: "",
                    title: "",
                    children: [],
                });
                if (selectedDatabase) {
                    loadPages(selectedDatabase);
                }
            }
        } catch (error) {
            console.error("Failed to create page:", error);
            toast({
                title: "Error",
                description: "Failed to create page",
                variant: "error",
            });
        }
    };

    const createDatabase = async () => {
        try {
            const response = await fetch(
                "/api/integrations/notion/databases/create",
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        user_id: "current",
                        parent: {
                            type: databaseForm.parent_type,
                            [databaseForm.parent_type === "page_id"
                                ? "page_id"
                                : "workspace"]: databaseForm.parent_id,
                        },
                        title: [
                            {
                                text: {
                                    content: databaseForm.title,
                                },
                            },
                        ],
                        properties: databaseForm.properties,
                        is_inline: databaseForm.is_inline,
                    }),
                },
            );

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Database created successfully",
                });
                setIsDatabaseModalOpen(false);
                setDatabaseForm({
                    parent_type: "page",
                    parent_id: "",
                    title: "",
                    properties: {},
                    is_inline: false,
                });
                loadDatabases();
            }
        } catch (error) {
            console.error("Failed to create database:", error);
            toast({
                title: "Error",
                description: "Failed to create database",
                variant: "error",
            });
        }
    };

    // Filter data based on search
    const filteredDatabases = databases.filter((db) =>
        db.title[0]?.text.content.toLowerCase().includes(searchQuery.toLowerCase()),
    );

    const filteredPages = pages.filter((page) =>
        page.properties.title?.title[0]?.text.content
            .toLowerCase()
            .includes(searchQuery.toLowerCase()),
    );

    // Stats calculations
    const totalDatabases = databases.length;
    const totalPages = pages.length;
    const totalUsers = users.length;
    const activePages = pages.filter((p) => !p.archived).length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadDatabases();
            loadUsers();
        }
    }, [connected]);

    useEffect(() => {
        if (selectedDatabase) {
            loadPages(selectedDatabase);
        }
    }, [selectedDatabase, selectedFilter]);

    useEffect(() => {
        if (searchQuery) {
            searchNotion();
        } else {
            setSearchResults([]);
        }
    }, [searchQuery, selectedFilter]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const getStatusColor = (status?: string): string => {
        switch (status?.toLowerCase()) {
            case "done":
                return "bg-green-100 text-green-800";
            case "in progress":
                return "bg-yellow-100 text-yellow-800";
            case "not started":
                return "bg-gray-100 text-gray-800";
            case "blocked":
                return "bg-red-100 text-red-800";
            default:
                return "bg-gray-100 text-gray-800";
        }
    };

    const getPriorityColor = (priority?: string): string => {
        switch (priority?.toLowerCase()) {
            case "high":
                return "bg-red-100 text-red-800";
            case "medium":
                return "bg-yellow-100 text-yellow-800";
            case "low":
                return "bg-blue-100 text-blue-800";
            default:
                return "bg-gray-100 text-gray-800";
        }
    };

    const getPageTitle = (page: NotionPage): string => {
        return page.properties.title?.title[0]?.text.content || "Untitled";
    };

    const getDatabaseTitle = (db: NotionDatabase): string => {
        return db.title[0]?.text.content || "Untitled Database";
    };

    return (
        <div className="min-h-screen bg-background p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Settings className="w-8 h-8 text-black" />
                        <div className="flex flex-col space-y-1">
                            <h1 className="text-3xl font-bold">Notion Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Document management and knowledge base platform
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center space-x-4">
                        <Badge
                            variant={healthStatus === "healthy" ? "default" : "destructive"}
                            className="flex items-center"
                        >
                            {healthStatus === "healthy" ? (
                                <CheckCircle className="mr-1 w-4 h-4" />
                            ) : (
                                <AlertTriangle className="mr-1 w-4 h-4" />
                            )}
                            {connected ? "Connected" : "Disconnected"}
                        </Badge>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={checkConnection}
                            className="flex items-center"
                        >
                            <RefreshCw className="mr-2 w-4 h-4" />
                            Refresh Status
                        </Button>
                    </div>
                </div>

                {!connected ? (
                    // Connection Required State
                    <Card>
                        <CardContent className="py-8">
                            <div className="flex flex-col items-center space-y-6 text-center">
                                <Settings className="w-16 h-16 text-muted-foreground" />
                                <div className="space-y-2">
                                    <h2 className="text-2xl font-semibold">Connect Notion</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Notion workspace to start managing documents and databases
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    onClick={() =>
                                        (window.location.href = "/api/integrations/notion/auth/start")
                                    }
                                    className="flex items-center bg-black hover:bg-gray-800"
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Notion Workspace
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    // Connected State
                    <>
                        {/* Stats Overview */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Databases</p>
                                        <div className="text-2xl font-bold">{totalDatabases}</div>
                                        <p className="text-xs text-muted-foreground">Knowledge bases</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Pages</p>
                                        <div className="text-2xl font-bold">{totalPages}</div>
                                        <p className="text-xs text-muted-foreground">{activePages} active</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Users</p>
                                        <div className="text-2xl font-bold">{totalUsers}</div>
                                        <p className="text-xs text-muted-foreground">Team members</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Search Results</p>
                                        <div className="text-2xl font-bold">{searchResults.length}</div>
                                        <p className="text-xs text-muted-foreground">Current query</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="databases" className="w-full">
                            <TabsList>
                                <TabsTrigger value="databases">Databases</TabsTrigger>
                                <TabsTrigger value="pages">Pages</TabsTrigger>
                                <TabsTrigger value="search">Search</TabsTrigger>
                                <TabsTrigger value="users">Users</TabsTrigger>
                            </TabsList>

                            {/* Databases Tab */}
                            <TabsContent value="databases" className="space-y-6 mt-6">
                                <div className="flex items-center space-x-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search databases..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <div className="flex-1" />
                                    <Button onClick={() => setIsDatabaseModalOpen(true)} className="flex items-center bg-black hover:bg-gray-800">
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Database
                                    </Button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.databases ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : (
                                        filteredDatabases.map((db) => (
                                            <Card
                                                key={db.id}
                                                className={`cursor-pointer hover:shadow-md transition-all border ${selectedDatabase === db.id
                                                    ? "border-blue-500"
                                                    : "border-border"
                                                    }`}
                                                onClick={() => {
                                                    setSelectedDatabase(db.id);
                                                    loadPages(db.id);
                                                }}
                                            >
                                                <CardHeader>
                                                    <div className="flex flex-col space-y-2">
                                                        <div className="flex items-center justify-between">
                                                            <p className="font-bold text-lg">{getDatabaseTitle(db)}</p>
                                                            {db.icon?.emoji && (
                                                                <p className="text-2xl">{db.icon.emoji}</p>
                                                            )}
                                                        </div>
                                                        <p className="text-sm text-muted-foreground">
                                                            {db.description[0]?.text.content || "No description"}
                                                        </p>
                                                    </div>
                                                </CardHeader>
                                                <CardContent className="space-y-3">
                                                    <div className="flex items-center justify-between">
                                                        <Badge variant="secondary">Database</Badge>
                                                        <Badge
                                                            variant={db.is_inline ? "default" : "outline"}
                                                            className={
                                                                db.is_inline
                                                                    ? "bg-green-100 text-green-800"
                                                                    : ""
                                                            }
                                                        >
                                                            {db.is_inline ? "Inline" : "Full Page"}
                                                        </Badge>
                                                    </div>
                                                    <p className="text-xs text-muted-foreground">
                                                        Created: {formatDate(db.created_time)}
                                                    </p>
                                                    <p className="text-xs text-muted-foreground">
                                                        Modified: {formatDate(db.last_edited_time)}
                                                    </p>
                                                    <a href={db.url} target="_blank" rel="noopener noreferrer">
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            className="w-full flex items-center"
                                                        >
                                                            <Eye className="mr-2 w-4 h-4" />
                                                            Open in Notion
                                                        </Button>
                                                    </a>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Pages Tab */}
                            <TabsContent value="pages" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select value={selectedDatabase} onValueChange={(value) => {
                                        setSelectedDatabase(value);
                                        loadPages(value);
                                    }}>
                                        <SelectTrigger className="w-[300px]">
                                            <SelectValue placeholder="Select database" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {databases.map((db) => (
                                                <SelectItem key={db.id} value={db.id}>
                                                    {getDatabaseTitle(db)}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <Select value={selectedFilter} onValueChange={setSelectedFilter}>
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="Filter by status" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Status</SelectItem>
                                            <SelectItem value="Not Started">Not Started</SelectItem>
                                            <SelectItem value="In Progress">In Progress</SelectItem>
                                            <SelectItem value="Done">Done</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search pages..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <div className="flex-1" />
                                    <Button
                                        onClick={() => setIsPageModalOpen(true)}
                                        disabled={!selectedDatabase}
                                        className="flex items-center bg-black hover:bg-gray-800"
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Page
                                    </Button>
                                </div>

                                <div className="space-y-4">
                                    {loading.pages ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : selectedDatabase ? (
                                        filteredPages.map((page) => (
                                            <Card key={page.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex flex-col space-y-4">
                                                        <div className="flex flex-col space-y-2">
                                                            <div className="flex items-center justify-between">
                                                                <a
                                                                    href={page.url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className="flex items-center space-x-2"
                                                                >
                                                                    <p className="font-bold text-lg">{getPageTitle(page)}</p>
                                                                    {page.properties.status?.select && (
                                                                        <Badge className={getStatusColor(page.properties.status.select.name)}>
                                                                            {page.properties.status.select.name}
                                                                        </Badge>
                                                                    )}
                                                                </a>
                                                                <p className="text-xs text-muted-foreground">
                                                                    {formatDate(page.last_edited_time)}
                                                                </p>
                                                            </div>

                                                            <div className="flex items-center space-x-4">
                                                                {page.properties.priority?.select && (
                                                                    <Badge className={getPriorityColor(page.properties.priority.select.name)}>
                                                                        Priority: {page.properties.priority.select.name}
                                                                    </Badge>
                                                                )}
                                                                {page.properties.due_date?.date && (
                                                                    <Badge variant="secondary">
                                                                        Due: {new Date(page.properties.due_date.date.start).toLocaleDateString()}
                                                                    </Badge>
                                                                )}
                                                            </div>

                                                            {page.properties.tags?.multi_select && (
                                                                <div className="flex flex-wrap gap-1">
                                                                    {page.properties.tags.multi_select.map((tag) => (
                                                                        <Badge key={tag.name} variant="outline">
                                                                            {tag.name}
                                                                        </Badge>
                                                                    ))}
                                                                </div>
                                                            )}

                                                            <a href={page.url} target="_blank" rel="noopener noreferrer">
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline"
                                                                    className="w-fit flex items-center"
                                                                >
                                                                    <Eye className="mr-2 w-4 h-4" />
                                                                    Open in Notion
                                                                </Button>
                                                            </a>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    ) : (
                                        <p className="text-muted-foreground text-center py-8">
                                            Select a database to view pages
                                        </p>
                                    )}
                                </div>
                            </TabsContent>

                            {/* Search Tab */}
                            <TabsContent value="search" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select value={selectedFilter} onValueChange={setSelectedFilter}>
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="Filter by type" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="all">All Types</SelectItem>
                                            <SelectItem value="page">Pages</SelectItem>
                                            <SelectItem value="database">Databases</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search all content..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            onKeyPress={(e) => {
                                                if (e.key === "Enter") {
                                                    searchNotion();
                                                }
                                            }}
                                            className="pl-8"
                                        />
                                    </div>
                                </div>

                                <div className="space-y-4">
                                    {loading.search ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : searchResults.length > 0 ? (
                                        searchResults.map((result) => (
                                            <Card key={result.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex items-start space-x-4">
                                                        {result.object === "database" ? (
                                                            <DatabaseIcon className="w-6 h-6 text-blue-500" />
                                                        ) : (
                                                            <FileText className="w-6 h-6 text-blue-500" />
                                                        )}
                                                        <div className="flex flex-col space-y-2 flex-1">
                                                            <div className="flex items-center justify-between">
                                                                <a
                                                                    href={result.url}
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                >
                                                                    <p className="font-bold">{result.title || result.object}</p>
                                                                </a>
                                                                <Badge variant="secondary">{result.object}</Badge>
                                                            </div>
                                                            <p className="text-xs text-muted-foreground">
                                                                Modified: {formatDate(result.last_edited_time)}
                                                            </p>
                                                            <a href={result.url} target="_blank" rel="noopener noreferrer">
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline"
                                                                    className="w-fit flex items-center"
                                                                >
                                                                    <Eye className="mr-2 w-4 h-4" />
                                                                    Open in Notion
                                                                </Button>
                                                            </a>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    ) : searchQuery ? (
                                        <p className="text-muted-foreground text-center py-8">
                                            No results found for &ldquo;{searchQuery}&rdquo;
                                        </p>
                                    ) : (
                                        <p className="text-muted-foreground text-center py-8">
                                            Enter a search query to find content
                                        </p>
                                    )}
                                </div>
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

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.users ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : (
                                        users
                                            .filter(
                                                (user) =>
                                                    user.name
                                                        ?.toLowerCase()
                                                        .includes(searchQuery.toLowerCase()) ||
                                                    user.person?.email
                                                        ?.toLowerCase()
                                                        .includes(searchQuery.toLowerCase()),
                                            )
                                            .map((user) => (
                                                <Card key={user.id}>
                                                    <CardContent className="pt-6">
                                                        <div className="flex items-center space-x-4">
                                                            <Avatar className="w-12 h-12">
                                                                <AvatarImage src={user.avatar_url} />
                                                                <AvatarFallback>
                                                                    {user.name?.slice(0, 2) || "U"}
                                                                </AvatarFallback>
                                                            </Avatar>
                                                            <div className="flex flex-col space-y-1 flex-1">
                                                                <p className="font-bold">{user.name || "Unknown"}</p>
                                                                {user.person?.email && (
                                                                    <p className="text-sm text-muted-foreground">
                                                                        {user.person.email}
                                                                    </p>
                                                                )}
                                                                <div className="flex items-center space-x-2">
                                                                    <Badge
                                                                        variant={user.type === "person" ? "default" : "secondary"}
                                                                        className={
                                                                            user.type === "person"
                                                                                ? "bg-green-100 text-green-800"
                                                                                : "bg-blue-100 text-blue-800"
                                                                        }
                                                                    >
                                                                        {user.type}
                                                                    </Badge>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            ))
                                    )}
                                </div>
                            </TabsContent>
                        </Tabs>
                    </>
                )}
            </div>

            {/* Create Page Modal */}
            <Dialog open={isPageModalOpen} onOpenChange={setIsPageModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create Page</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="page-parent">Parent</Label>
                            <Select
                                value={pageForm.parent_id}
                                onValueChange={(value) =>
                                    setPageForm({ ...pageForm, parent_id: value })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select parent" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value={selectedDatabase}>Selected Database</SelectItem>
                                    {databases.map((db) => (
                                        <SelectItem key={db.id} value={db.id}>
                                            {getDatabaseTitle(db)}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="page-title">Page Title</Label>
                            <Input
                                id="page-title"
                                placeholder="Enter page title"
                                value={pageForm.title}
                                onChange={(e) =>
                                    setPageForm({ ...pageForm, title: e.target.value })
                                }
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="page-content">Initial Content</Label>
                            <Textarea
                                id="page-content"
                                placeholder="Optional initial content..."
                                value={
                                    pageForm.children?.[0]?.paragraph?.text?.[0]?.text?.content || ""
                                }
                                onChange={(e) =>
                                    setPageForm({
                                        ...pageForm,
                                        children: e.target.value
                                            ? [
                                                {
                                                    object: "block",
                                                    type: "paragraph",
                                                    paragraph: {
                                                        text: [
                                                            {
                                                                type: "text",
                                                                text: { content: e.target.value },
                                                            },
                                                        ],
                                                    },
                                                },
                                            ]
                                            : [],
                                    })
                                }
                                rows={4}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsPageModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={createPage}
                            disabled={!pageForm.title}
                            className="bg-black hover:bg-gray-800"
                        >
                            Create Page
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* Create Database Modal */}
            <Dialog open={isDatabaseModalOpen} onOpenChange={setIsDatabaseModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create Database</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="db-parent">Parent</Label>
                            <Select
                                value={databaseForm.parent_id}
                                onValueChange={(value) =>
                                    setDatabaseForm({ ...databaseForm, parent_id: value })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Workspace Root" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="">Workspace Root</SelectItem>
                                    {databases.map((db) => (
                                        <SelectItem key={db.id} value={db.id}>
                                            Inside: {getDatabaseTitle(db)}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="db-name">Database Name</Label>
                            <Input
                                id="db-name"
                                placeholder="Enter database name"
                                value={databaseForm.title}
                                onChange={(e) =>
                                    setDatabaseForm({ ...databaseForm, title: e.target.value })
                                }
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="db-type">Database Type</Label>
                            <Select
                                value={databaseForm.is_inline ? "inline" : "full"}
                                onValueChange={(value) =>
                                    setDatabaseForm({
                                        ...databaseForm,
                                        is_inline: value === "inline",
                                    })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="full">Full Page</SelectItem>
                                    <SelectItem value="inline">Inline</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsDatabaseModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={createDatabase}
                            disabled={!databaseForm.title}
                            className="bg-black hover:bg-gray-800"
                        >
                            Create Database
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div >
    );
};

export default NotionIntegration;
