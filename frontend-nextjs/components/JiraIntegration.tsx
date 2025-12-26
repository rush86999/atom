import React, { useState, useEffect } from "react";
import {
    Eye,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    RefreshCw,
    Loader2,
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

interface JiraProject {
    id: string;
    key: string;
    name: string;
    projectTypeKey: string;
    lead: {
        displayName: string;
        emailAddress: string;
        avatarUrls: {
            "48x48": string;
            "24x24": string;
        };
    };
    url: string;
    description?: string;
    isPrivate: boolean;
    archived: boolean;
    issueTypes: Array<{
        id: string;
        name: string;
        description: string;
        iconUrl: string;
    }>;
}

interface JiraIssue {
    id: string;
    key: string;
    fields: {
        summary: string;
        description?: string;
        status: {
            name: string;
            statusCategory: {
                colorName: string;
            };
        };
        priority: {
            name: string;
            iconUrl: string;
        };
        assignee?: {
            displayName: string;
            emailAddress: string;
            avatarUrls: {
                "48x48": string;
                "24x24": string;
            };
        };
        reporter: {
            displayName: string;
            emailAddress: string;
            avatarUrls: {
                "48x48": string;
                "24x24": string;
            };
        };
        created: string;
        updated: string;
        resolution?: string;
        resolutiondate?: string;
        issuetype: {
            name: string;
            iconUrl: string;
        };
        project: {
            key: string;
            name: string;
        };
        components?: Array<{
            id: string;
            name: string;
        }>;
        fixVersions?: Array<{
            id: string;
            name: string;
        }>;
        labels?: string[];
        timeoriginalestimate?: number;
        timeestimate?: number;
        timespent?: number;
        aggregateprogress?: {
            progress: number;
            total: number;
        };
    };
}

interface JiraUser {
    accountId: string;
    accountType: string;
    active: boolean;
    displayName: string;
    emailAddress?: string;
    avatarUrls: {
        "48x48": string;
        "24x24": string;
        "16x16": string;
    };
    timeZone?: string;
    locale?: string;
}

interface JiraSprint {
    id: number;
    state: string;
    name: string;
    startDate?: string;
    endDate?: string;
    completeDate?: string;
    originBoardId: number;
    goal?: string;
    issues: Array<{
        id: string;
        key: string;
        fields: {
            summary: string;
            status: {
                name: string;
            };
            assignee?: {
                displayName: string;
                avatarUrls: {
                    "48x48": string;
                };
            };
        };
    }>;
}

const JiraIntegration: React.FC = () => {
    const [projects, setProjects] = useState<JiraProject[]>([]);
    const [issues, setIssues] = useState<JiraIssue[]>([]);
    const [users, setUsers] = useState<JiraUser[]>([]);
    const [sprints, setSprints] = useState<JiraSprint[]>([]);
    const [userProfile, setUserProfile] = useState<JiraUser | null>(null);
    const [loading, setLoading] = useState({
        projects: false,
        issues: false,
        users: false,
        sprints: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedProject, setSelectedProject] = useState("");
    const [selectedStatus, setSelectedStatus] = useState("");
    const [selectedAssignee, setSelectedAssignee] = useState("");

    const [isIssueModalOpen, setIsIssueModalOpen] = useState(false);
    const [isProjectModalOpen, setIsProjectModalOpen] = useState(false);

    const [newIssue, setNewIssue] = useState({
        project: "",
        summary: "",
        description: "",
        issueType: "Story",
        priority: "Medium",
        assignee: "",
    });

    const [newProject, setNewProject] = useState({
        name: "",
        key: "",
        description: "",
        type: "Software",
    });

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/jira/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
                loadProjects();
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

    // Load Jira data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/jira/profile", {
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

    const loadProjects = async () => {
        setLoading((prev) => ({ ...prev, projects: true }));
        try {
            const response = await fetch("/api/integrations/jira/projects", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setProjects(data.data?.projects || []);
            }
        } catch (error) {
            console.error("Failed to load projects:", error);
            toast({
                title: "Error",
                description: "Failed to load projects from Jira",
                variant: "error",
            });
        } finally {
            setLoading((prev) => ({ ...prev, projects: false }));
        }
    };

    const loadIssues = async () => {
        setLoading((prev) => ({ ...prev, issues: true }));
        try {
            const response = await fetch("/api/integrations/jira/issues", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    project: selectedProject,
                    status: selectedStatus,
                    assignee: selectedAssignee,
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setIssues(data.data?.issues || []);
            }
        } catch (error) {
            console.error("Failed to load issues:", error);
        } finally {
            setLoading((prev) => ({ ...prev, issues: false }));
        }
    };

    const loadUsers = async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        try {
            const response = await fetch("/api/integrations/jira/users", {
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

    const loadSprints = async (projectId: string) => {
        if (!projectId) return;

        setLoading((prev) => ({ ...prev, sprints: true }));
        try {
            const response = await fetch("/api/integrations/jira/sprints", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    project: projectId,
                    limit: 20,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setSprints(data.data?.sprints || []);
            }
        } catch (error) {
            console.error("Failed to load sprints:", error);
        } finally {
            setLoading((prev) => ({ ...prev, sprints: false }));
        }
    };

    const createIssue = async () => {
        if (!newIssue.project || !newIssue.summary) return;

        try {
            const response = await fetch("/api/integrations/jira/issues/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    project: newIssue.project,
                    summary: newIssue.summary,
                    description: newIssue.description,
                    issueType: newIssue.issueType,
                    priority: newIssue.priority,
                    assignee: newIssue.assignee,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Issue created successfully",
                });
                setIsIssueModalOpen(false);
                setNewIssue({
                    project: "",
                    summary: "",
                    description: "",
                    issueType: "Story",
                    priority: "Medium",
                    assignee: "",
                });
                if (newIssue.project === selectedProject) {
                    loadIssues();
                }
            }
        } catch (error) {
            console.error("Failed to create issue:", error);
            toast({
                title: "Error",
                description: "Failed to create issue",
                variant: "error",
            });
        }
    };

    // Filter data based on search
    const filteredProjects = projects.filter(
        (project) =>
            project.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            project.key.toLowerCase().includes(searchQuery.toLowerCase()) ||
            project.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredIssues = issues.filter(
        (issue) =>
            issue.fields.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
            issue.fields.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            issue.key.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Stats calculations
    const totalProjects = projects.length;
    const activeProjects = projects.filter((p) => !p.archived).length;
    const totalIssues = issues.length;
    const openIssues = issues.filter(
        (i) => i.fields.status.statusCategory.colorName !== "done"
    ).length;
    const inProgressIssues = issues.filter(
        (i) => i.fields.status.statusCategory.colorName === "in-progress"
    ).length;
    const doneIssues = issues.filter(
        (i) => i.fields.status.statusCategory.colorName === "done"
    ).length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadUserProfile();
            loadProjects();
            loadUsers();
        }
    }, [connected]);

    useEffect(() => {
        if (selectedProject) {
            loadIssues();
            loadSprints(selectedProject);
        }
    }, [selectedProject, selectedStatus, selectedAssignee]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const getStatusColor = (statusCategory: string): string => {
        switch (statusCategory?.toLowerCase()) {
            case "blue-gray":
            case "new":
                return "bg-gray-100 text-gray-800";
            case "yellow":
            case "in-progress":
                return "bg-yellow-100 text-yellow-800";
            case "green":
            case "done":
                return "bg-green-100 text-green-800";
            case "red":
            case "undefined":
                return "bg-red-100 text-red-800";
            default:
                return "bg-gray-100 text-gray-800";
        }
    };

    const getPriorityColor = (priority: string): string => {
        switch (priority?.toLowerCase()) {
            case "highest":
            case "blocker":
                return "bg-red-100 text-red-800";
            case "high":
            case "critical":
                return "bg-orange-100 text-orange-800";
            case "medium":
                return "bg-yellow-100 text-yellow-800";
            case "low":
            case "minor":
                return "bg-blue-100 text-blue-800";
            default:
                return "bg-gray-100 text-gray-800";
        }
    };

    return (
        <div className="min-h-screen bg-background p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Eye className="w-8 h-8 text-[#0052CC]" />
                        <div className="flex flex-col space-y-1">
                            <h1 className="text-3xl font-bold">Jira Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Project management and issue tracking platform
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

                    {userProfile && (
                        <div className="flex items-center space-x-4">
                            <Avatar>
                                <AvatarImage src={userProfile.avatarUrls?.["48x48"]} />
                                <AvatarFallback>{userProfile.displayName.slice(0, 2)}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col space-y-0">
                                <p className="font-bold">{userProfile.displayName}</p>
                                <p className="text-sm text-muted-foreground">
                                    {userProfile.emailAddress}
                                </p>
                            </div>
                        </div>
                    )}
                </div>

                {!connected ? (
                    // Connection Required State
                    <Card>
                        <CardContent className="py-8">
                            <div className="flex flex-col items-center space-y-6 text-center">
                                <Eye className="w-16 h-16 text-muted-foreground" />
                                <div className="space-y-2">
                                    <h2 className="text-2xl font-semibold">Connect Jira</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Jira instance to start managing projects and issues
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    onClick={() =>
                                        (window.location.href = "/api/integrations/jira/auth/start")
                                    }
                                    className="flex items-center"
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Jira Account
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
                                        <p className="text-sm font-medium text-muted-foreground">Projects</p>
                                        <div className="text-2xl font-bold">{totalProjects}</div>
                                        <p className="text-xs text-muted-foreground">{activeProjects} active</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Total Issues</p>
                                        <div className="text-2xl font-bold">{totalIssues}</div>
                                        <p className="text-xs text-muted-foreground">All status</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">In Progress</p>
                                        <div className="text-2xl font-bold">{inProgressIssues}</div>
                                        <p className="text-xs text-muted-foreground">Currently being worked</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Completed</p>
                                        <div className="text-2xl font-bold">{doneIssues}</div>
                                        <p className="text-xs text-muted-foreground">Done this sprint</p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="projects" className="w-full">
                            <TabsList>
                                <TabsTrigger value="projects">Projects</TabsTrigger>
                                <TabsTrigger value="issues">Issues</TabsTrigger>
                                <TabsTrigger value="sprints">Sprints</TabsTrigger>
                                <TabsTrigger value="team">Team</TabsTrigger>
                            </TabsList>

                            {/* Projects Tab */}
                            <TabsContent value="projects" className="space-y-6 mt-6">
                                <div className="flex items-center space-x-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search projects..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <div className="flex-1" />
                                    <Button onClick={() => setIsProjectModalOpen(true)} className="flex items-center">
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Project
                                    </Button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.projects ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : (
                                        filteredProjects.map((project) => (
                                            <Card
                                                key={project.id}
                                                className={`cursor-pointer hover:shadow-md transition-all border ${selectedProject === project.key
                                                    ? "border-blue-500"
                                                    : "border-border"
                                                    }`}
                                                onClick={() => setSelectedProject(project.key)}
                                            >
                                                <CardHeader>
                                                    <div className="flex flex-col space-y-2">
                                                        <div className="flex items-start justify-between">
                                                            <p className="font-bold text-lg">{project.name}</p>
                                                            <div className="flex items-center space-x-1">
                                                                {project.isPrivate && (
                                                                    <Badge variant="secondary" className="text-xs">
                                                                        Private
                                                                    </Badge>
                                                                )}
                                                                {project.archived && (
                                                                    <Badge variant="destructive" className="text-xs">
                                                                        Archived
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                        </div>
                                                        <p className="text-sm text-muted-foreground">
                                                            {project.description}
                                                        </p>
                                                        <p className="text-sm text-blue-600 font-bold">
                                                            {project.key}
                                                        </p>
                                                    </div>
                                                </CardHeader>
                                                <CardContent className="space-y-3">
                                                    {project.lead && (
                                                        <div className="flex items-center space-x-2">
                                                            <Avatar className="w-6 h-6">
                                                                <AvatarImage src={(project.lead.avatarUrls as any)?.["24x24"]} />
                                                                <AvatarFallback>{project.lead.displayName.slice(0, 2)}</AvatarFallback>
                                                            </Avatar>
                                                            <p className="text-sm">
                                                                Lead: {project.lead.displayName}
                                                            </p>
                                                        </div>
                                                    )}
                                                    <p className="text-xs text-muted-foreground">
                                                        Type: {project.projectTypeKey}
                                                    </p>
                                                    {project.issueTypes && (
                                                        <div className="flex flex-wrap gap-1">
                                                            {project.issueTypes.slice(0, 3).map((type) => (
                                                                <Badge key={type.id} variant="secondary" className="text-xs">
                                                                    {type.name}
                                                                </Badge>
                                                            ))}
                                                        </div>
                                                    )}
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Issues Tab */}
                            <TabsContent value="issues" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select value={selectedProject} onValueChange={setSelectedProject}>
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Select project" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {projects.map((project) => (
                                                <SelectItem key={project.id} value={project.key}>
                                                    {project.name} ({project.key})
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <Select value={selectedStatus} onValueChange={setSelectedStatus}>
                                        <SelectTrigger className="w-[150px]">
                                            <SelectValue placeholder="Status" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="">All Status</SelectItem>
                                            <SelectItem value="To Do">To Do</SelectItem>
                                            <SelectItem value="In Progress">In Progress</SelectItem>
                                            <SelectItem value="In Review">In Review</SelectItem>
                                            <SelectItem value="Done">Done</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Select value={selectedAssignee} onValueChange={setSelectedAssignee}>
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Assignee" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="">All Assignees</SelectItem>
                                            {users.map((user) => (
                                                <SelectItem key={user.accountId} value={user.accountId}>
                                                    {user.displayName}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search issues..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <div className="flex-1" />
                                    <Button
                                        onClick={() => setIsIssueModalOpen(true)}
                                        disabled={!selectedProject}
                                        className="flex items-center"
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        Create Issue
                                    </Button>
                                </div>

                                <div className="space-y-4">
                                    {loading.issues ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : selectedProject ? (
                                        filteredIssues.map((issue) => (
                                            <Card key={issue.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex flex-col space-y-4">
                                                        <div className="flex items-start space-y-2 flex-col flex-1">
                                                            <div className="flex items-center justify-between w-full">
                                                                <div className="flex items-center space-x-2">
                                                                    <p className="font-bold text-lg">{issue.key}</p>
                                                                    <p>{issue.fields.summary}</p>
                                                                </div>
                                                                <Badge
                                                                    className={getStatusColor(
                                                                        issue.fields.status.statusCategory.colorName
                                                                    )}
                                                                >
                                                                    {issue.fields.status.name}
                                                                </Badge>
                                                            </div>
                                                            <div className="flex items-center space-x-4">
                                                                <Badge className={getPriorityColor(issue.fields.priority.name)}>
                                                                    {issue.fields.priority.name}
                                                                </Badge>
                                                                <Badge variant="secondary">
                                                                    {issue.fields.issuetype.name}
                                                                </Badge>
                                                            </div>
                                                            <p className="text-sm text-muted-foreground">
                                                                {issue.fields.description?.substring(0, 200)}
                                                                {issue.fields.description &&
                                                                    issue.fields.description.length > 200 &&
                                                                    "..."}
                                                            </p>
                                                            <div className="flex items-center justify-between w-full">
                                                                <div className="flex items-center space-x-4">
                                                                    <Avatar className="w-6 h-6">
                                                                        <AvatarImage
                                                                            src={(issue.fields.reporter.avatarUrls as any)?.["24x24"]}
                                                                        />
                                                                        <AvatarFallback>
                                                                            {issue.fields.reporter.displayName.slice(0, 2)}
                                                                        </AvatarFallback>
                                                                    </Avatar>
                                                                    <p className="text-xs text-muted-foreground">
                                                                        Reporter: {issue.fields.reporter.displayName}
                                                                    </p>
                                                                    {issue.fields.assignee && (
                                                                        <>
                                                                            <Avatar className="w-6 h-6">
                                                                                <AvatarImage
                                                                                    src={issue.fields.assignee.avatarUrls?.["24x24"]}
                                                                                />
                                                                                <AvatarFallback>
                                                                                    {issue.fields.assignee.displayName.slice(0, 2)}
                                                                                </AvatarFallback>
                                                                            </Avatar>
                                                                            <p className="text-xs text-muted-foreground">
                                                                                Assignee: {issue.fields.assignee.displayName}
                                                                            </p>
                                                                        </>
                                                                    )}
                                                                </div>
                                                                <p className="text-xs text-muted-foreground">
                                                                    {formatDate(issue.fields.created)}
                                                                </p>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    ) : (
                                        <p className="text-muted-foreground text-center py-8">
                                            Select a project to view issues
                                        </p>
                                    )}
                                </div>
                            </TabsContent>

                            {/* Sprints Tab */}
                            <TabsContent value="sprints" className="space-y-6 mt-6">
                                <div className="flex items-center space-x-4">
                                    <Select value={selectedProject} onValueChange={setSelectedProject}>
                                        <SelectTrigger className="w-[200px]">
                                            <SelectValue placeholder="Select project" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {projects.map((project) => (
                                                <SelectItem key={project.id} value={project.key}>
                                                    {project.name} ({project.key})
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="space-y-4">
                                    {loading.sprints ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : selectedProject ? (
                                        sprints.map((sprint) => (
                                            <Card key={sprint.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex flex-col space-y-3">
                                                        <div className="flex items-center justify-between">
                                                            <h3 className="text-lg font-bold">{sprint.name}</h3>
                                                            <Badge
                                                                variant={sprint.state === "active" ? "default" : "secondary"}
                                                                className={
                                                                    sprint.state === "active"
                                                                        ? "bg-green-100 text-green-800"
                                                                        : ""
                                                                }
                                                            >
                                                                {sprint.state}
                                                            </Badge>
                                                        </div>
                                                        {sprint.goal && (
                                                            <p className="text-muted-foreground">Goal: {sprint.goal}</p>
                                                        )}
                                                        <div className="flex items-center space-x-4">
                                                            {sprint.startDate && (
                                                                <p className="text-sm text-muted-foreground">
                                                                    Start: {formatDate(sprint.startDate)}
                                                                </p>
                                                            )}
                                                            {sprint.endDate && (
                                                                <p className="text-sm text-muted-foreground">
                                                                    End: {formatDate(sprint.endDate)}
                                                                </p>
                                                            )}
                                                        </div>
                                                        <p className="text-sm font-bold">
                                                            {sprint.issues.length} issues
                                                        </p>
                                                        <div className="space-y-2 w-full">
                                                            {sprint.issues.map((issue) => (
                                                                <div
                                                                    key={issue.id}
                                                                    className="flex items-center p-2 bg-muted rounded-md"
                                                                >
                                                                    <p className="text-sm">{issue.key}</p>
                                                                    <p className="text-sm ml-2">{issue.fields.summary}</p>
                                                                    {issue.fields.assignee && (
                                                                        <Avatar className="w-5 h-5 ml-auto">
                                                                            <AvatarImage
                                                                                src={(issue.fields.assignee.avatarUrls as any)?.["24x24"]}
                                                                            />
                                                                            <AvatarFallback>
                                                                                {issue.fields.assignee.displayName.slice(0, 2)}
                                                                            </AvatarFallback>
                                                                        </Avatar>
                                                                    )}
                                                                </div>
                                                            ))}
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    ) : (
                                        <p className="text-muted-foreground text-center py-8">
                                            Select a project to view sprints
                                        </p>
                                    )}
                                </div>
                            </TabsContent>

                            {/* Team Tab */}
                            <TabsContent value="team" className="space-y-6 mt-6">
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
                                                    user.displayName
                                                        .toLowerCase()
                                                        .includes(searchQuery.toLowerCase()) ||
                                                    (user.emailAddress &&
                                                        user.emailAddress
                                                            .toLowerCase()
                                                            .includes(searchQuery.toLowerCase()))
                                            )
                                            .map((user) => (
                                                <Card key={user.accountId}>
                                                    <CardContent className="pt-6">
                                                        <div className="flex items-center space-x-4">
                                                            <Avatar className="w-12 h-12">
                                                                <AvatarImage src={user.avatarUrls?.["48x48"]} />
                                                                <AvatarFallback>
                                                                    {user.displayName.slice(0, 2)}
                                                                </AvatarFallback>
                                                            </Avatar>
                                                            <div className="flex flex-col space-y-1 flex-1">
                                                                <p className="font-bold">{user.displayName}</p>
                                                                {user.emailAddress && (
                                                                    <p className="text-sm text-muted-foreground">
                                                                        {user.emailAddress}
                                                                    </p>
                                                                )}
                                                                <div className="flex items-center space-x-2">
                                                                    <Badge
                                                                        variant={user.active ? "default" : "destructive"}
                                                                        className={
                                                                            user.active
                                                                                ? "bg-green-100 text-green-800"
                                                                                : "bg-red-100 text-red-800"
                                                                        }
                                                                    >
                                                                        {user.active ? "Active" : "Inactive"}
                                                                    </Badge>
                                                                    <Badge variant="secondary">{user.accountType}</Badge>
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

            {/* Create Issue Modal */}
            <Dialog open={isIssueModalOpen} onOpenChange={setIsIssueModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create Issue</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="issue-project">Project</Label>
                            <Select
                                value={newIssue.project}
                                onValueChange={(value) =>
                                    setNewIssue({ ...newIssue, project: value })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select a project" />
                                </SelectTrigger>
                                <SelectContent>
                                    {projects.map((project) => (
                                        <SelectItem key={project.id} value={project.key}>
                                            {project.name} ({project.key})
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="issue-summary">Summary</Label>
                            <Input
                                id="issue-summary"
                                placeholder="Issue summary"
                                value={newIssue.summary}
                                onChange={(e) =>
                                    setNewIssue({ ...newIssue, summary: e.target.value })
                                }
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="issue-description">Description</Label>
                            <Textarea
                                id="issue-description"
                                placeholder="Describe the issue..."
                                value={newIssue.description}
                                onChange={(e) =>
                                    setNewIssue({ ...newIssue, description: e.target.value })
                                }
                                rows={6}
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="issue-type">Issue Type</Label>
                            <Select
                                value={newIssue.issueType}
                                onValueChange={(value) =>
                                    setNewIssue({ ...newIssue, issueType: value })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="Story">Story</SelectItem>
                                    <SelectItem value="Task">Task</SelectItem>
                                    <SelectItem value="Bug">Bug</SelectItem>
                                    <SelectItem value="Epic">Epic</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="issue-priority">Priority</Label>
                            <Select
                                value={newIssue.priority}
                                onValueChange={(value) =>
                                    setNewIssue({ ...newIssue, priority: value })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="Highest">Highest</SelectItem>
                                    <SelectItem value="High">High</SelectItem>
                                    <SelectItem value="Medium">Medium</SelectItem>
                                    <SelectItem value="Low">Low</SelectItem>
                                    <SelectItem value="Lowest">Lowest</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="issue-assignee">Assignee</Label>
                            <Select
                                value={newIssue.assignee}
                                onValueChange={(value) =>
                                    setNewIssue({ ...newIssue, assignee: value })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Unassigned" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="">Unassigned</SelectItem>
                                    {users.map((user) => (
                                        <SelectItem key={user.accountId} value={user.accountId}>
                                            {user.displayName}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsIssueModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button
                            onClick={createIssue}
                            disabled={!newIssue.project || !newIssue.summary}
                        >
                            Create Issue
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default JiraIntegration;
