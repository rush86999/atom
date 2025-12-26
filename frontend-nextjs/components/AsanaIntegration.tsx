/**
 * Asana Integration Component
 * Complete project management and task tracking interface
 */

import React, { useState, useEffect } from "react";
import {
    Layout,
    Clock,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    Settings,
    RefreshCw,
    Star,
    Users,
    Briefcase,
    Building,
    Loader2,
    Calendar,
    CheckSquare,
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

interface AsanaTask {
    id: string;
    name: string;
    description?: string;
    due_on?: string;
    due_at?: string;
    assignee?: {
        id: string;
        name: string;
        email?: string;
    };
    projects: Array<{
        id: string;
        name: string;
    }>;
    workspace: {
        id: string;
        name: string;
    };
    completed: boolean;
    created_at: string;
    modified_at: string;
    permalink_url: string;
    tags: string[];
    custom_fields?: Array<{
        id: string;
        name: string;
        value: any;
    }>;
}

interface AsanaProject {
    id: string;
    name: string;
    description?: string;
    color?: string;
    due_date?: string;
    current_status?: {
        color: string;
        text: string;
    };
    owner?: {
        id: string;
        name: string;
    };
    workspace: {
        id: string;
        name: string;
    };
    team?: {
        id: string;
        name: string;
    };
    created_at: string;
    modified_at: string;
    permalink_url: string;
}

interface AsanaWorkspace {
    id: string;
    name: string;
    is_organization: boolean;
}

interface AsanaUser {
    id: string;
    name: string;
    email?: string;
    photo?: {
        image_21x21?: string;
        image_27x27?: string;
        image_36x36?: string;
        image_60x60?: string;
        image_128x128?: string;
    };
}

interface AsanaTeam {
    id: string;
    name: string;
    description?: string;
    organization?: {
        id: string;
        name: string;
    };
}

const AsanaIntegration: React.FC = () => {
    const [tasks, setTasks] = useState<AsanaTask[]>([]);
    const [projects, setProjects] = useState<AsanaProject[]>([]);
    const [workspaces, setWorkspaces] = useState<AsanaWorkspace[]>([]);
    const [teams, setTeams] = useState<AsanaTeam[]>([]);
    const [users, setUsers] = useState<AsanaUser[]>([]);
    const [loading, setLoading] = useState({
        tasks: false,
        projects: false,
        workspaces: false,
        teams: false,
        users: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedWorkspace, setSelectedWorkspace] = useState("");
    const [selectedProject, setSelectedProject] = useState("");
    const [selectedStatus, setSelectedStatus] = useState("");

    const [isCreateTaskOpen, setIsCreateTaskOpen] = useState(false);
    const [newTask, setNewTask] = useState({
        name: "",
        description: "",
        due_on: "",
        assignee: "",
        project: "",
    });

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/asana/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadWorkspaces();
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

    // Load Asana data
    const loadWorkspaces = async () => {
        setLoading((prev) => ({ ...prev, workspaces: true }));
        try {
            const response = await fetch("/api/integrations/asana/workspaces", {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setWorkspaces(data.data?.workspaces || []);
            }
        } catch (error) {
            console.error("Failed to load workspaces:", error);
        } finally {
            setLoading((prev) => ({ ...prev, workspaces: false }));
        }
    };

    const loadProjects = async () => {
        setLoading((prev) => ({ ...prev, projects: true }));
        try {
            const response = await fetch("/api/integrations/asana/projects", {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setProjects(data.data?.projects || []);
            }
        } catch (error) {
            console.error("Failed to load projects:", error);
        } finally {
            setLoading((prev) => ({ ...prev, projects: false }));
        }
    };

    const loadTasks = async () => {
        setLoading((prev) => ({ ...prev, tasks: true }));
        try {
            const response = await fetch("/api/integrations/asana/tasks", {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setTasks(data.data?.tasks || []);
            }
        } catch (error) {
            console.error("Failed to load tasks:", error);
            toast({
                title: "Error",
                description: "Failed to load tasks from Asana",
                variant: "error",
            });
        } finally {
            setLoading((prev) => ({ ...prev, tasks: false }));
        }
    };

    const loadTeams = async () => {
        setLoading((prev) => ({ ...prev, teams: true }));
        try {
            const response = await fetch("/api/integrations/asana/teams", {
                method: "GET",
                headers: { "Content-Type": "application/json" },
            });

            if (response.ok) {
                const data = await response.json();
                setTeams(data.data?.teams || []);
            }
        } catch (error) {
            console.error("Failed to load teams:", error);
        } finally {
            setLoading((prev) => ({ ...prev, teams: false }));
        }
    };

    const loadUsers = async () => {
        setLoading((prev) => ({ ...prev, users: true }));
        try {
            const response = await fetch("/api/integrations/asana/users", {
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
    };

    // Create new task
    const createTask = async () => {
        try {
            const response = await fetch("/api/integrations/asana/tasks", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    name: newTask.name,
                    description: newTask.description,
                    due_on: newTask.due_on || undefined,
                    assignee: newTask.assignee || undefined,
                    projects: newTask.project ? [newTask.project] : [],
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Task created successfully",
                });
                setIsCreateTaskOpen(false);
                setNewTask({
                    name: "",
                    description: "",
                    due_on: "",
                    assignee: "",
                    project: "",
                });
                loadTasks();
            }
        } catch (error) {
            console.error("Failed to create task:", error);
            toast({
                title: "Error",
                description: "Failed to create task",
                variant: "error",
            });
        }
    };

    // Filter tasks based on search and filters
    const filteredTasks = tasks.filter((task) => {
        const matchesSearch =
            task.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            task.description?.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesWorkspace =
            !selectedWorkspace || task.workspace.id === selectedWorkspace;
        const matchesProject =
            !selectedProject || task.projects.some((p) => p.id === selectedProject);
        const matchesStatus =
            !selectedStatus ||
            (selectedStatus === "completed" && task.completed) ||
            (selectedStatus === "incomplete" && !task.completed);

        return matchesSearch && matchesWorkspace && matchesProject && matchesStatus;
    });

    // Stats calculations
    const totalTasks = tasks.length;
    const completedTasks = tasks.filter((task) => task.completed).length;
    const overdueTasks = tasks.filter(
        (task) =>
            task.due_on && new Date(task.due_on) < new Date() && !task.completed,
    ).length;
    const assignedTasks = tasks.filter((task) => task.assignee).length;
    const completionRate =
        totalTasks > 0 ? (completedTasks / totalTasks) * 100 : 0;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadProjects();
            loadTasks();
            loadTeams();
            loadUsers();
        }
    }, [connected]);

    const getStatusVariant = (completed: boolean): "default" | "secondary" | "destructive" | "outline" => {
        return completed ? "default" : "secondary";
    };

    const getStatusLabel = (completed: boolean) => {
        return completed ? "Completed" : "In Progress";
    };

    const getDueDateVariant = (dueDate?: string, completed?: boolean): "default" | "secondary" | "destructive" | "outline" => {
        if (completed) return "secondary";
        if (!dueDate) return "secondary";
        const due = new Date(dueDate);
        const today = new Date();
        if (due < today) return "destructive";
        if (due < new Date(today.getTime() + 7 * 24 * 60 * 60 * 1000))
            return "outline"; // Orange-ish usually, but outline is distinct
        return "default"; // Green-ish
    };

    const formatDate = (dateString?: string) => {
        if (!dateString) return "No due date";
        return new Date(dateString).toLocaleDateString();
    };

    return (
        <div className="p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Layout className="w-8 h-8 text-green-500" />
                        <div className="flex flex-col">
                            <h1 className="text-3xl font-bold">Asana Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Project management and task tracking
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

                {!connected ? (
                    // Connection Required State
                    <Card>
                        <CardContent className="pt-6">
                            <div className="flex flex-col items-center justify-center space-y-6 py-8">
                                <Layout className="w-16 h-16 text-gray-400" />
                                <div className="space-y-2 text-center">
                                    <h2 className="text-2xl font-bold">Connect Asana</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Asana account to manage projects and tasks
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    className="bg-green-600 hover:bg-green-700"
                                    onClick={() =>
                                        (window.location.href = "/api/auth/asana/authorize")
                                    }
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Asana Account
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                ) : (
                    // Connected State
                    <>
                        {/* Stats Overview */}
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Total Tasks</p>
                                        <div className="text-2xl font-bold">{totalTasks}</div>
                                        <p className="text-xs text-muted-foreground">Across all projects</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Completed</p>
                                        <div className="text-2xl font-bold">{completedTasks}</div>
                                        <p className="text-xs text-muted-foreground">Tasks done</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Overdue</p>
                                        <div className="text-2xl font-bold">{overdueTasks}</div>
                                        <p className="text-xs text-muted-foreground">Need attention</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Assigned</p>
                                        <div className="text-2xl font-bold">{assignedTasks}</div>
                                        <p className="text-xs text-muted-foreground">With assignees</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Completion Rate</p>
                                        <div className="text-2xl font-bold">{Math.round(completionRate)}%</div>
                                        <div className="w-full bg-secondary h-2 rounded-full mt-2">
                                            <div
                                                className="bg-green-500 h-2 rounded-full"
                                                style={{ width: `${completionRate}%` }}
                                            />
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="tasks">
                            <TabsList>
                                <TabsTrigger value="tasks">Tasks</TabsTrigger>
                                <TabsTrigger value="projects">Projects</TabsTrigger>
                                <TabsTrigger value="teams">Teams</TabsTrigger>
                                <TabsTrigger value="workspaces">Workspaces</TabsTrigger>
                            </TabsList>

                            {/* Tasks Tab */}
                            <TabsContent value="tasks" className="space-y-6 mt-6">
                                {/* Filters and Actions */}
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="flex flex-col md:flex-row gap-4">
                                            <div className="relative flex-1">
                                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                                <Input
                                                    placeholder="Search tasks..."
                                                    value={searchQuery}
                                                    onChange={(e) => setSearchQuery(e.target.value)}
                                                    className="pl-8"
                                                />
                                            </div>
                                            <Select
                                                value={selectedWorkspace}
                                                onValueChange={setSelectedWorkspace}
                                            >
                                                <SelectTrigger className="w-[200px]">
                                                    <SelectValue placeholder="All Workspaces" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {workspaces.map((workspace) => (
                                                        <SelectItem key={workspace.id} value={workspace.id}>
                                                            {workspace.name}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <Select
                                                value={selectedProject}
                                                onValueChange={setSelectedProject}
                                            >
                                                <SelectTrigger className="w-[200px]">
                                                    <SelectValue placeholder="All Projects" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    {projects.map((project) => (
                                                        <SelectItem key={project.id} value={project.id}>
                                                            {project.name}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <Select
                                                value={selectedStatus}
                                                onValueChange={setSelectedStatus}
                                            >
                                                <SelectTrigger className="w-[150px]">
                                                    <SelectValue placeholder="All Status" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="completed">Completed</SelectItem>
                                                    <SelectItem value="incomplete">Incomplete</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <Button
                                                className="bg-green-600 hover:bg-green-700"
                                                onClick={() => setIsCreateTaskOpen(true)}
                                            >
                                                <Plus className="mr-2 w-4 h-4" />
                                                New Task
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>

                                {/* Tasks Table */}
                                <Card>
                                    <CardContent className="pt-6">
                                        {loading.tasks ? (
                                            <div className="flex flex-col items-center justify-center py-8 space-y-4">
                                                <p>Loading tasks...</p>
                                                <Loader2 className="w-8 h-8 animate-spin text-green-500" />
                                            </div>
                                        ) : filteredTasks.length === 0 ? (
                                            <div className="flex flex-col items-center justify-center py-8 space-y-4">
                                                <Layout className="w-12 h-12 text-gray-400" />
                                                <p className="text-muted-foreground">No tasks found</p>
                                                <Button
                                                    variant="outline"
                                                    onClick={() => setIsCreateTaskOpen(true)}
                                                >
                                                    <Plus className="mr-2 w-4 h-4" />
                                                    Create Your First Task
                                                </Button>
                                            </div>
                                        ) : (
                                            <Table>
                                                <TableHeader>
                                                    <TableRow>
                                                        <TableHead>Task Name</TableHead>
                                                        <TableHead>Projects</TableHead>
                                                        <TableHead>Assignee</TableHead>
                                                        <TableHead>Due Date</TableHead>
                                                        <TableHead>Status</TableHead>
                                                        <TableHead>Actions</TableHead>
                                                    </TableRow>
                                                </TableHeader>
                                                <TableBody>
                                                    {filteredTasks.map((task) => (
                                                        <TableRow key={task.id}>
                                                            <TableCell>
                                                                <div className="flex flex-col space-y-1">
                                                                    <span className="font-medium">{task.name}</span>
                                                                    {task.description && (
                                                                        <span className="text-xs text-muted-foreground line-clamp-2">
                                                                            {task.description}
                                                                        </span>
                                                                    )}
                                                                </div>
                                                            </TableCell>
                                                            <TableCell>
                                                                <div className="flex flex-col space-y-1">
                                                                    {task.projects.map((project) => (
                                                                        <Badge
                                                                            key={project.id}
                                                                            variant="outline"
                                                                            className="w-fit text-xs"
                                                                        >
                                                                            {project.name}
                                                                        </Badge>
                                                                    ))}
                                                                </div>
                                                            </TableCell>
                                                            <TableCell>
                                                                {task.assignee ? (
                                                                    <span className="text-sm">{task.assignee.name}</span>
                                                                ) : (
                                                                    <span className="text-sm text-muted-foreground">Unassigned</span>
                                                                )}
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getDueDateVariant(task.due_on, task.completed)}>
                                                                    {formatDate(task.due_on)}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Badge variant={getStatusVariant(task.completed)}>
                                                                    {getStatusLabel(task.completed)}
                                                                </Badge>
                                                            </TableCell>
                                                            <TableCell>
                                                                <Button
                                                                    size="sm"
                                                                    variant="outline"
                                                                    onClick={() => window.open(task.permalink_url, "_blank")}
                                                                >
                                                                    <ArrowRight className="mr-2 w-3 h-3" />
                                                                    View
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

                            {/* Projects Tab */}
                            <TabsContent value="projects" className="space-y-6 mt-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                            {projects.map((project) => (
                                                <Card key={project.id}>
                                                    <CardContent className="pt-6">
                                                        <div className="space-y-3">
                                                            <h3 className="font-bold text-lg">{project.name}</h3>
                                                            {project.description && (
                                                                <p className="text-sm text-muted-foreground line-clamp-2">
                                                                    {project.description}
                                                                </p>
                                                            )}
                                                            <div className="flex space-x-2">
                                                                {project.current_status && (
                                                                    <Badge
                                                                        variant={
                                                                            project.current_status.color === "green"
                                                                                ? "default"
                                                                                : project.current_status.color === "yellow"
                                                                                    ? "secondary"
                                                                                    : "destructive"
                                                                        }
                                                                    >
                                                                        {project.current_status.text}
                                                                    </Badge>
                                                                )}
                                                                {project.owner && (
                                                                    <Badge variant="outline">
                                                                        {project.owner.name}
                                                                    </Badge>
                                                                )}
                                                            </div>
                                                            <p className="text-xs text-muted-foreground">
                                                                Workspace: {project.workspace.name}
                                                            </p>
                                                            {project.team && (
                                                                <p className="text-xs text-muted-foreground">
                                                                    Team: {project.team.name}
                                                                </p>
                                                            )}
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                className="w-full mt-2"
                                                                onClick={() => window.open(project.permalink_url, "_blank")}
                                                            >
                                                                <ArrowRight className="mr-2 w-3 h-3" />
                                                                Open in Asana
                                                            </Button>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Teams Tab */}
                            <TabsContent value="teams" className="space-y-6 mt-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                            {teams.map((team) => (
                                                <Card key={team.id}>
                                                    <CardContent className="pt-6">
                                                        <div className="space-y-3">
                                                            <h3 className="font-bold text-lg">{team.name}</h3>
                                                            {team.description && (
                                                                <p className="text-sm text-muted-foreground">
                                                                    {team.description}
                                                                </p>
                                                            )}
                                                            {team.organization && (
                                                                <p className="text-xs text-muted-foreground">
                                                                    Organization: {team.organization.name}
                                                                </p>
                                                            )}
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Workspaces Tab */}
                            <TabsContent value="workspaces" className="space-y-6 mt-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                            {workspaces.map((workspace) => (
                                                <Card key={workspace.id}>
                                                    <CardContent className="pt-6">
                                                        <div className="space-y-3">
                                                            <h3 className="font-bold text-lg">{workspace.name}</h3>
                                                            <Badge variant={workspace.is_organization ? "default" : "secondary"}>
                                                                {workspace.is_organization ? "Organization" : "Workspace"}
                                                            </Badge>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>
                        </Tabs>

                        {/* Create Task Modal */}
                        <Dialog open={isCreateTaskOpen} onOpenChange={setIsCreateTaskOpen}>
                            <DialogContent>
                                <DialogHeader>
                                    <DialogTitle>Create New Task</DialogTitle>
                                </DialogHeader>
                                <div className="py-4 space-y-4">
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Task Name</label>
                                        <Input
                                            placeholder="Enter task name"
                                            value={newTask.name}
                                            onChange={(e) =>
                                                setNewTask({ ...newTask, name: e.target.value })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Description</label>
                                        <Textarea
                                            placeholder="Task description"
                                            value={newTask.description}
                                            onChange={(e) =>
                                                setNewTask({
                                                    ...newTask,
                                                    description: e.target.value,
                                                })
                                            }
                                            rows={3}
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Due Date</label>
                                        <Input
                                            type="date"
                                            value={newTask.due_on}
                                            onChange={(e) =>
                                                setNewTask({ ...newTask, due_on: e.target.value })
                                            }
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Assignee</label>
                                        <Select
                                            value={newTask.assignee}
                                            onValueChange={(value) =>
                                                setNewTask({ ...newTask, assignee: value })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select assignee" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {users.map((user) => (
                                                    <SelectItem key={user.id} value={user.id}>
                                                        {user.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <label className="text-sm font-medium leading-none">Project</label>
                                        <Select
                                            value={newTask.project}
                                            onValueChange={(value) =>
                                                setNewTask({ ...newTask, project: value })
                                            }
                                        >
                                            <SelectTrigger>
                                                <SelectValue placeholder="Select project" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {projects.map((project) => (
                                                    <SelectItem key={project.id} value={project.id}>
                                                        {project.name}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <DialogFooter>
                                    <Button variant="outline" onClick={() => setIsCreateTaskOpen(false)}>
                                        Cancel
                                    </Button>
                                    <Button
                                        className="bg-green-600 hover:bg-green-700"
                                        onClick={createTask}
                                        disabled={!newTask.name}
                                    >
                                        Create Task
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

export default AsanaIntegration;
