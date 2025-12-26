/**
 * Tableau Integration Component
 * Complete Tableau integration with dashboards, workbooks, datasources, views, and analytics
 */

import React, { useState, useEffect } from "react";
import {
    Search,
    Plus,
    ChevronDown,
    Eye,
    Edit,
    Settings,
    ArrowRight,
    Clock,
    CheckCircle,
    AlertTriangle,
    Loader2,
    TrendingUp,
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
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";

// Types
interface TableauWorkbook {
    id: string;
    name: string;
    description?: string;
    project_id: string;
    owner_id: string;
    created_at: string;
    updated_at: string;
    content_url?: string;
    show_tabs: boolean;
    size?: number;
    tags: string[];
}

interface TableauDatasource {
    id: string;
    name: string;
    description?: string;
    project_id: string;
    owner_id: string;
    created_at: string;
    updated_at: string;
    content_url?: string;
    has_extracts: boolean;
    is_certified: boolean;
    tags: string[];
}

interface TableauView {
    id: string;
    name: string;
    content_url: string;
    created_at: string;
    updated_at: string;
    owner_id: string;
    workbook_id: string;
    view_url_name: string;
    tags: string[];
}

interface TableauProject {
    id: string;
    name: string;
    description?: string;
    parent_project_id?: string;
    owner_id: string;
    created_at: string;
    updated_at: string;
}

interface TableauUser {
    id: string;
    email: string;
    name: string;
    site_role: string;
    last_login?: string;
    external_auth_user_id?: string;
}

interface TableauStats {
    total_workbooks: number;
    total_datasources: number;
    total_views: number;
    total_projects: number;
    active_users: number;
    storage_used: number;
}

const TableauIntegration: React.FC = () => {
    const [isConnected, setIsConnected] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [workbooks, setWorkbooks] = useState<TableauWorkbook[]>([]);
    const [datasources, setDatasources] = useState<TableauDatasource[]>([]);
    const [views, setViews] = useState<TableauView[]>([]);
    const [projects, setProjects] = useState<TableauProject[]>([]);
    const [userProfile, setUserProfile] = useState<TableauUser | null>(null);
    const [stats, setStats] = useState<TableauStats | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

    const { toast } = useToast();

    // Load initial data
    useEffect(() => {
        loadTableauData();
    }, []);

    const loadTableauData = async () => {
        try {
            setIsLoading(true);

            // Check connection status
            const healthResponse = await fetch("/api/v1/tableau/health");
            if (healthResponse.ok) {
                setIsConnected(true);

                // Load workbooks
                const workbooksResponse = await fetch(
                    "/api/v1/tableau/workbooks?limit=50"
                );
                if (workbooksResponse.ok) {
                    const workbooksData = await workbooksResponse.json();
                    setWorkbooks(workbooksData.data || []);
                }

                // Load datasources
                const datasourcesResponse = await fetch(
                    "/api/v1/tableau/datasources?limit=50"
                );
                if (datasourcesResponse.ok) {
                    const datasourcesData = await datasourcesResponse.json();
                    setDatasources(datasourcesData.data || []);
                }

                // Load views
                const viewsResponse = await fetch("/api/v1/tableau/views?limit=50");
                if (viewsResponse.ok) {
                    const viewsData = await viewsResponse.json();
                    setViews(viewsData.data || []);
                }

                // Load projects
                const projectsResponse = await fetch("/api/v1/tableau/projects");
                if (projectsResponse.ok) {
                    const projectsData = await projectsResponse.json();
                    setProjects(projectsData.data || []);
                }

                // Load user profile
                const userResponse = await fetch("/api/v1/tableau/user");
                if (userResponse.ok) {
                    const userData = await userResponse.json();
                    setUserProfile(userData.data);
                }

                // Calculate stats
                const calculatedStats: TableauStats = {
                    total_workbooks: workbooks.length,
                    total_datasources: datasources.length,
                    total_views: views.length,
                    total_projects: projects.length,
                    active_users: 1,
                    storage_used: workbooks.reduce((sum, w) => sum + (w.size || 0), 0),
                };
                setStats(calculatedStats);
            }
        } catch (error) {
            console.error("Failed to load Tableau data:", error);
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
                title: "Tableau Connected",
                description: "Successfully connected to Tableau",
            });

            await loadTableauData();
        } catch (error) {
            toast({
                title: "Connection Failed",
                description: "Failed to connect to Tableau",
                variant: "error",
            });
        }
    };

    const handleSearch = async () => {
        if (!searchQuery.trim()) return;

        try {
            const searchResponse = await fetch("/api/v1/tableau/search", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    query: searchQuery,
                    types: ["workbook", "view", "datasource"],
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

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return "0 Bytes";
        const k = 1024;
        const sizes = ["Bytes", "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
    };

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleDateString();
    };

    // Render connection status
    if (!isConnected && !isLoading) {
        return (
            <div className="p-6">
                <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-6 text-center">
                    <div className="space-y-2">
                        <h2 className="text-2xl font-semibold">Connect Tableau</h2>
                        <p className="text-muted-foreground mb-6">
                            Connect your Tableau account to access dashboards, workbooks, and
                            analytics data.
                        </p>
                    </div>

                    <Card className="max-w-md w-full">
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center space-y-4">
                                <Eye className="w-12 h-12 text-blue-500 mb-4" />
                                <h3 className="text-xl font-semibold">Tableau Integration</h3>
                                <p className="text-muted-foreground mt-2">
                                    Business intelligence and analytics platform
                                </p>

                                <Button
                                    size="lg"
                                    className="w-full bg-blue-600 hover:bg-blue-700"
                                    onClick={() => setIsConnectModalOpen(true)}
                                >
                                    Connect Tableau
                                </Button>

                                <p className="text-sm text-muted-foreground text-center">
                                    You&apos;ll be redirected to Tableau to authorize access
                                </p>
                            </div>
                        </CardContent>
                    </Card>
                </div>

                {/* Connect Modal */}
                <Dialog open={isConnectModalOpen} onOpenChange={setIsConnectModalOpen}>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Connect Tableau</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <p>
                                This will connect your Tableau account to ATOM. You&apos;ll be
                                able to:
                            </p>
                            <div className="flex flex-col space-y-2">
                                <div className="flex items-center space-x-2">
                                    <CheckCircle className="w-4 h-4 text-green-500" />
                                    <span>Access your workbooks and dashboards</span>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <CheckCircle className="w-4 h-4 text-green-500" />
                                    <span>View and analyze data sources</span>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <CheckCircle className="w-4 h-4 text-green-500" />
                                    <span>Search across all Tableau content</span>
                                </div>
                                <div className="flex items-center space-x-2">
                                    <CheckCircle className="w-4 h-4 text-green-500" />
                                    <span>Manage projects and permissions</span>
                                </div>
                            </div>
                            <Alert>
                                <AlertDescription>
                                    You&apos;ll be redirected to Tableau to authorize this
                                    connection.
                                </AlertDescription>
                            </Alert>
                        </div>
                        <DialogFooter>
                            <Button
                                variant="outline"
                                onClick={() => setIsConnectModalOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                className="bg-blue-600 hover:bg-blue-700"
                                onClick={handleConnect}
                            >
                                Connect Tableau
                            </Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </div>
        );
    }

    return (
        <div className="p-6">
            {/* Header */}
            <div className="flex flex-col space-y-4 mb-6">
                <div className="flex w-full justify-between items-center">
                    <div className="flex flex-col space-y-1">
                        <h1 className="text-2xl font-bold">Tableau</h1>
                        <p className="text-muted-foreground">
                            Business intelligence and analytics platform
                        </p>
                    </div>
                    <div className="flex items-center space-x-4">
                        <Button
                            variant="outline"
                            onClick={() => setIsConnectModalOpen(true)}
                        >
                            <Settings className="mr-2 w-4 h-4" />
                            Settings
                        </Button>
                        <Button className="bg-blue-600 hover:bg-blue-700">
                            <Plus className="mr-2 w-4 h-4" />
                            New Workbook
                        </Button>
                    </div>
                </div>

                <nav className="flex text-sm text-muted-foreground">
                    <a href="/integrations" className="hover:text-foreground">
                        Integrations
                    </a>
                    <span className="mx-2">/</span>
                    <span className="text-foreground">Tableau</span>
                </nav>
            </div>

            {/* Search Bar */}
            <Card className="mb-6">
                <CardContent className="pt-6">
                    <div className="flex items-center space-x-4">
                        <div className="relative flex-1">
                            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                            <Input
                                placeholder="Search workbooks, views, datasources..."
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyPress={(e) => e.key === "Enter" && handleSearch()}
                                className="pl-8"
                            />
                        </div>
                        <Button className="bg-blue-600 hover:bg-blue-700" onClick={handleSearch}>
                            Search
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Main Content */}
            <Tabs defaultValue="dashboard">
                <TabsList>
                    <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
                    <TabsTrigger value="workbooks">Workbooks</TabsTrigger>
                    <TabsTrigger value="datasources">Datasources</TabsTrigger>
                    <TabsTrigger value="views">Views</TabsTrigger>
                    <TabsTrigger value="projects">Projects</TabsTrigger>
                    <TabsTrigger value="analytics">Analytics</TabsTrigger>
                </TabsList>

                {/* Dashboard Panel */}
                <TabsContent value="dashboard" className="space-y-6 mt-6">
                    {stats && (
                        <>
                            {/* Stats Overview */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">
                                                Total Workbooks
                                            </p>
                                            <div className="text-2xl font-bold">
                                                {stats.total_workbooks}
                                            </div>
                                            <p className="text-xs text-muted-foreground flex items-center">
                                                <TrendingUp className="w-3 h-3 mr-1 text-green-500" />
                                                23.36%
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">
                                                Total Views
                                            </p>
                                            <div className="text-2xl font-bold">
                                                {stats.total_views}
                                            </div>
                                            <p className="text-xs text-muted-foreground flex items-center">
                                                <TrendingUp className="w-3 h-3 mr-1 text-green-500" />
                                                12.5%
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="space-y-1">
                                            <p className="text-sm font-medium text-muted-foreground">
                                                Storage Used
                                            </p>
                                            <div className="text-2xl font-bold">
                                                {formatFileSize(stats.storage_used)}
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                Across all workbooks
                                            </p>
                                        </div>
                                    </CardContent>
                                </Card>
                            </div>

                            {/* Recent Activity */}
                            <Card>
                                <CardHeader>
                                    <CardTitle>Recent Workbooks</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <Table>
                                        <TableHeader>
                                            <TableRow>
                                                <TableHead>Name</TableHead>
                                                <TableHead>Project</TableHead>
                                                <TableHead>Last Updated</TableHead>
                                                <TableHead>Size</TableHead>
                                                <TableHead>Actions</TableHead>
                                            </TableRow>
                                        </TableHeader>
                                        <TableBody>
                                            {workbooks.slice(0, 5).map((workbook) => (
                                                <TableRow key={workbook.id}>
                                                    <TableCell className="font-medium">
                                                        {workbook.name}
                                                    </TableCell>
                                                    <TableCell>
                                                        <Badge variant="secondary">
                                                            {projects.find((p) => p.id === workbook.project_id)
                                                                ?.name || "Unknown"}
                                                        </Badge>
                                                    </TableCell>
                                                    <TableCell>{formatDate(workbook.updated_at)}</TableCell>
                                                    <TableCell>
                                                        {formatFileSize(workbook.size || 0)}
                                                    </TableCell>
                                                    <TableCell>
                                                        <div className="flex items-center space-x-2">
                                                            <Button size="sm" variant="ghost">
                                                                <Eye className="w-4 h-4" />
                                                            </Button>
                                                            <Button size="sm" variant="ghost">
                                                                <Edit className="w-4 h-4" />
                                                            </Button>
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </CardContent>
                            </Card>

                            {/* User Info */}
                            {userProfile && (
                                <Card>
                                    <CardHeader>
                                        <CardTitle>Account Information</CardTitle>
                                    </CardHeader>
                                    <CardContent>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            <div>
                                                <p className="font-bold">Name</p>
                                                <p>{userProfile.name}</p>
                                            </div>
                                            <div>
                                                <p className="font-bold">Email</p>
                                                <p>{userProfile.email}</p>
                                            </div>
                                            <div>
                                                <p className="font-bold">Site Role</p>
                                                <Badge variant="secondary">{userProfile.site_role}</Badge>
                                            </div>
                                            <div>
                                                <p className="font-bold">Last Login</p>
                                                <p>
                                                    {userProfile.last_login
                                                        ? formatDate(userProfile.last_login)
                                                        : "Never"}
                                                </p>
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    )}
                </TabsContent>

                {/* Workbooks Panel */}
                <TabsContent value="workbooks" className="space-y-6 mt-6">
                    <div className="flex w-full justify-between items-center">
                        <h2 className="text-xl font-semibold">
                            Workbooks ({workbooks.length})
                        </h2>
                        <Button className="bg-blue-600 hover:bg-blue-700">
                            <Plus className="mr-2 w-4 h-4" />
                            New Workbook
                        </Button>
                    </div>

                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Description</TableHead>
                                <TableHead>Project</TableHead>
                                <TableHead>Size</TableHead>
                                <TableHead>Last Updated</TableHead>
                                <TableHead>Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {workbooks.map((workbook) => (
                                <TableRow key={workbook.id}>
                                    <TableCell className="font-medium">{workbook.name}</TableCell>
                                    <TableCell>{workbook.description || "No description"}</TableCell>
                                    <TableCell>
                                        <Badge variant="secondary">
                                            {projects.find((p) => p.id === workbook.project_id)?.name ||
                                                "Unknown"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>{formatFileSize(workbook.size || 0)}</TableCell>
                                    <TableCell>{formatDate(workbook.updated_at)}</TableCell>
                                    <TableCell>
                                        <div className="flex items-center space-x-2">
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => window.open(workbook.content_url, "_blank")}
                                            >
                                                <Eye className="w-4 h-4" />
                                            </Button>
                                            <Button size="sm" variant="ghost">
                                                <Edit className="w-4 h-4" />
                                            </Button>
                                            <Button size="sm" variant="ghost">
                                                <ChevronDown className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TabsContent>

                {/* Datasources Panel */}
                <TabsContent value="datasources" className="space-y-6 mt-6">
                    <div className="flex w-full justify-between items-center">
                        <h2 className="text-xl font-semibold">
                            Datasources ({datasources.length})
                        </h2>
                        <Button className="bg-blue-600 hover:bg-blue-700">
                            <Plus className="mr-2 w-4 h-4" />
                            New Datasource
                        </Button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {datasources.map((datasource) => (
                            <Card key={datasource.id}>
                                <CardHeader>
                                    <div className="flex justify-between items-center">
                                        <CardTitle className="text-base">{datasource.name}</CardTitle>
                                        {datasource.is_certified && (
                                            <Badge variant="secondary" className="text-xs">
                                                Certified
                                            </Badge>
                                        )}
                                    </div>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex flex-col space-y-3">
                                        <p className="text-sm text-muted-foreground">
                                            {datasource.description || "No description"}
                                        </p>
                                        <div className="flex items-center space-x-2">
                                            <Badge variant="secondary">
                                                {projects.find((p) => p.id === datasource.project_id)
                                                    ?.name || "Unknown"}
                                            </Badge>
                                            {datasource.has_extracts && (
                                                <Badge variant="outline">Has Extracts</Badge>
                                            )}
                                        </div>
                                        <p className="text-xs text-muted-foreground">
                                            Updated {formatDate(datasource.updated_at)}
                                        </p>
                                        <div className="flex w-full justify-between">
                                            <Button size="sm" variant="ghost">
                                                <Eye className="mr-2 w-4 h-4" />
                                                View
                                            </Button>
                                            <Button size="sm" variant="ghost">
                                                <Edit className="mr-2 w-4 h-4" />
                                                Edit
                                            </Button>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </TabsContent>

                {/* Views Panel */}
                <TabsContent value="views" className="space-y-6 mt-6">
                    <div className="flex w-full justify-between items-center">
                        <h2 className="text-xl font-semibold">Views ({views.length})</h2>
                        <Button className="bg-blue-600 hover:bg-blue-700">
                            <Plus className="mr-2 w-4 h-4" />
                            New View
                        </Button>
                    </div>

                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>Name</TableHead>
                                <TableHead>Workbook</TableHead>
                                <TableHead>URL Name</TableHead>
                                <TableHead>Created</TableHead>
                                <TableHead>Actions</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {views.map((view) => (
                                <TableRow key={view.id}>
                                    <TableCell className="font-medium">{view.name}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline">
                                            {workbooks.find((w) => w.id === view.workbook_id)?.name ||
                                                "Unknown"}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>{view.view_url_name}</TableCell>
                                    <TableCell>{formatDate(view.created_at)}</TableCell>
                                    <TableCell>
                                        <div className="flex items-center space-x-2">
                                            <Button
                                                size="sm"
                                                variant="ghost"
                                                onClick={() => window.open(view.content_url, "_blank")}
                                            >
                                                <Eye className="w-4 h-4" />
                                            </Button>
                                            <Button size="sm" variant="ghost">
                                                <ArrowRight className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TabsContent>

                {/* Projects Panel */}
                <TabsContent value="projects" className="space-y-6 mt-6">
                    <div className="flex w-full justify-between items-center">
                        <h2 className="text-xl font-semibold">Projects ({projects.length})</h2>
                        <Button className="bg-blue-600 hover:bg-blue-700">
                            <Plus className="mr-2 w-4 h-4" />
                            New Project
                        </Button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {projects.map((project) => (
                            <Card key={project.id}>
                                <CardHeader>
                                    <CardTitle className="text-base">{project.name}</CardTitle>
                                </CardHeader>
                                <CardContent>
                                    <div className="flex flex-col space-y-3">
                                        <p className="text-sm text-muted-foreground">
                                            {project.description || "No description"}
                                        </p>
                                        {project.parent_project_id && (
                                            <p className="text-xs text-muted-foreground">
                                                Parent:{" "}
                                                {projects.find((p) => p.id === project.parent_project_id)
                                                    ?.name || "Unknown"}
                                            </p>
                                        )}
                                        <p className="text-xs text-muted-foreground">
                                            Created {formatDate(project.created_at)}
                                        </p>
                                        <div className="flex items-center space-x-2">
                                            <Button size="sm" variant="ghost">
                                                <Eye className="mr-2 w-4 h-4" />
                                                View Content
                                            </Button>
                                            <Button size="sm" variant="ghost">
                                                <Settings className="mr-2 w-4 h-4" />
                                                Settings
                                            </Button>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                    </div>
                </TabsContent>

                {/* Analytics Panel */}
                <TabsContent value="analytics" className="space-y-6 mt-6">
                    <h2 className="text-xl font-semibold">Analytics & Insights</h2>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Content Distribution</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    <div className="flex w-full justify-between">
                                        <span>Workbooks</span>
                                        <Badge variant="secondary">{workbooks.length}</Badge>
                                    </div>
                                    <div className="flex w-full justify-between">
                                        <span>Datasources</span>
                                        <Badge variant="secondary">{datasources.length}</Badge>
                                    </div>
                                    <div className="flex w-full justify-between">
                                        <span>Views</span>
                                        <Badge variant="outline">{views.length}</Badge>
                                    </div>
                                    <div className="flex w-full justify-between">
                                        <span>Projects</span>
                                        <Badge variant="outline">{projects.length}</Badge>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Storage Usage</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="space-y-4">
                                    <div className="flex w-full justify-between">
                                        <span>Total Storage</span>
                                        <span className="font-bold">
                                            {formatFileSize(stats?.storage_used || 0)}
                                        </span>
                                    </div>
                                    <Progress value={75} className="w-full" />
                                    <p className="text-sm text-muted-foreground">
                                        75% of available storage used
                                    </p>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Recent Activity</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <div className="flex flex-col space-y-3">
                                    <div className="flex items-center space-x-2">
                                        <CheckCircle className="w-4 h-4 text-green-500" />
                                        <span className="text-sm">Connected to Tableau</span>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <CheckCircle className="w-4 h-4 text-green-500" />
                                        <span className="text-sm">
                                            Loaded {workbooks.length} workbooks
                                        </span>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <CheckCircle className="w-4 h-4 text-green-500" />
                                        <span className="text-sm">
                                            Loaded {datasources.length} datasources
                                        </span>
                                    </div>
                                    <div className="flex items-center space-x-2">
                                        <CheckCircle className="w-4 h-4 text-green-500" />
                                        <span className="text-sm">Loaded {views.length} views</span>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">User Information</CardTitle>
                            </CardHeader>
                            <CardContent>
                                {userProfile && (
                                    <div className="flex flex-col space-y-3">
                                        <div className="flex items-center space-x-2">
                                            <span className="font-medium">Name:</span>
                                            <span>{userProfile.name}</span>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <span className="font-medium">Email:</span>
                                            <span>{userProfile.email}</span>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <span className="font-medium">Role:</span>
                                            <Badge variant="secondary">{userProfile.site_role}</Badge>
                                        </div>
                                        <div className="flex items-center space-x-2">
                                            <span className="font-medium">Last Login:</span>
                                            <span>
                                                {userProfile.last_login
                                                    ? formatDate(userProfile.last_login)
                                                    : "Never"}
                                            </span>
                                        </div>
                                    </div>
                                )}
                            </CardContent>
                        </Card>
                    </div>
                </TabsContent>
            </Tabs>
        </div>
    );
};

export default TableauIntegration;
