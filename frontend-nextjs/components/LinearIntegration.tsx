import React, { useState, useEffect } from "react";
import {
    Clock,
    CheckCircle,
    AlertTriangle,
    ArrowRight,
    Plus,
    Search,
    Settings,
    RefreshCw,
    Filter,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

interface LinearIssue {
    id: string;
    title: string;
    description?: string;
    state: string;
    priority: number;
    assignee?: string;
    team: string;
    project?: string;
    cycle?: string;
    dueDate?: string;
    url: string;
    createdAt: string;
    updatedAt: string;
}

interface LinearTeam {
    id: string;
    name: string;
    description?: string;
    key: string;
    memberCount: number;
}

interface LinearProject {
    id: string;
    name: string;
    description?: string;
    state: string;
    progress: number;
    teamId: string;
}

interface LinearCycle {
    id: string;
    name: string;
    number: number;
    startsAt: string;
    endsAt: string;
    progress: number;
    teamId: string;
}

const LinearIntegration: React.FC = () => {
    const [issues, setIssues] = useState<LinearIssue[]>([]);
    const [teams, setTeams] = useState<LinearTeam[]>([]);
    const [projects, setProjects] = useState<LinearProject[]>([]);
    const [cycles, setCycles] = useState<LinearCycle[]>([]);
    const [loading, setLoading] = useState({
        issues: false,
        teams: false,
        projects: false,
        cycles: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedTeam, setSelectedTeam] = useState("");
    const [selectedState, setSelectedState] = useState("");
    const [selectedPriority, setSelectedPriority] = useState("");

    const [isModalOpen, setIsModalOpen] = useState(false);
    const [newIssue, setNewIssue] = useState({
        title: "",
        description: "",
        teamId: "",
        priority: 0,
    });

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/linear/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
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

    // Load Linear data
    const loadIssues = async () => {
        setLoading((prev) => ({ ...prev, issues: true }));
        try {
            const response = await fetch("/api/integrations/linear/issues", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current", // Will be replaced with actual user ID
                    team_id: selectedTeam || undefined,
                    limit: 50,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setIssues(data.data?.issues || []);
            }
        } catch (error) {
            console.error("Failed to load issues:", error);
            toast({
                title: "Error",
                description: "Failed to load issues from Linear",
                variant: "destructive",
            });
        } finally {
            setLoading((prev) => ({ ...prev, issues: false }));
        }
    };

    const loadTeams = async () => {
        setLoading((prev) => ({ ...prev, teams: true }));
        try {
            const response = await fetch("/api/integrations/linear/teams", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 20,
                }),
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

    const loadProjects = async () => {
        setLoading((prev) => ({ ...prev, projects: true }));
        try {
            const response = await fetch("/api/integrations/linear/projects", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    team_id: selectedTeam || undefined,
                    limit: 20,
                }),
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

    const loadCycles = async () => {
        setLoading((prev) => ({ ...prev, cycles: true }));
        try {
            const response = await fetch("/api/integrations/linear/cycles", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    team_id: selectedTeam || undefined,
                    limit: 10,
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setCycles(data.data?.cycles || []);
            }
        } catch (error) {
            console.error("Failed to load cycles:", error);
        } finally {
            setLoading((prev) => ({ ...prev, cycles: false }));
        }
    };

    // Create new issue
    const createIssue = async () => {
        try {
            const response = await fetch("/api/integrations/linear/issues", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    title: newIssue.title,
                    description: newIssue.description,
                    team_id: newIssue.teamId,
                    priority: newIssue.priority,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Issue created successfully",
                });
                setIsModalOpen(false);
                setNewIssue({ title: "", description: "", teamId: "", priority: 0 });
                loadIssues();
            }
        } catch (error) {
            console.error("Failed to create issue:", error);
            toast({
                title: "Error",
                description: "Failed to create issue",
                variant: "destructive",
            });
        }
    };

    // Filter issues based on search and filters
    const filteredIssues = issues.filter((issue) => {
        const matchesSearch =
            issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            issue.description?.toLowerCase().includes(searchQuery.toLowerCase());
        const matchesTeam = !selectedTeam || issue.team === selectedTeam;
        const matchesState = !selectedState || issue.state === selectedState;
        const matchesPriority =
            !selectedPriority || issue.priority.toString() === selectedPriority;

        return matchesSearch && matchesTeam && matchesState && matchesPriority;
    });

    // Stats calculations
    const totalIssues = issues.length;
    const backlogIssues = issues.filter(
        (issue) => issue.state === "backlog",
    ).length;
    const inProgressIssues = issues.filter(
        (issue) => issue.state === "inProgress",
    ).length;
    const completedIssues = issues.filter(
        (issue) => issue.state === "done",
    ).length;
    const completionRate =
        totalIssues > 0 ? (completedIssues / totalIssues) * 100 : 0;

    useEffect(() => {
        checkConnection();
        if (connected) {
            loadTeams();
        }
    }, [connected]);

    useEffect(() => {
        if (connected && teams.length > 0) {
            loadIssues();
            loadProjects();
            loadCycles();
        }
    }, [connected, teams, selectedTeam]);

    const getPriorityColor = (priority: number) => {
        switch (priority) {
            case 0:
                return "bg-gray-100 text-gray-800";
            case 1:
                return "bg-blue-100 text-blue-800";
            case 2:
                return "bg-orange-100 text-orange-800";
            case 3:
                return "bg-red-100 text-red-800";
            case 4:
                return "bg-purple-100 text-purple-800";
            default:
                return "bg-gray-100 text-gray-800";
        }
    };

    const getPriorityLabel = (priority: number) => {
        switch (priority) {
            case 0:
                return "No priority";
            case 1:
                return "Low";
            case 2:
                return "Medium";
            case 3:
                return "High";
            case 4:
                return "Urgent";
            default:
                return "Unknown";
        }
    };

    const getStateColor = (state: string) => {
        switch (state) {
            case "backlog":
                return "bg-gray-100 text-gray-800";
            case "todo":
                return "bg-blue-100 text-blue-800";
            case "inProgress":
                return "bg-orange-100 text-orange-800";
            case "done":
                return "bg-green-100 text-green-800";
            case "canceled":
                return "bg-red-100 text-red-800";
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
                        <Clock className="w-8 h-8 text-blue-500" />
                        <div className="flex flex-col space-y-1">
                            <h1 className="text-3xl font-bold">Linear Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Issue tracking and project management
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
                                <Clock className="w-16 h-16 text-muted-foreground" />
                                <div className="space-y-2">
                                    <h2 className="text-2xl font-semibold">Connect Linear</h2>
                                    <p className="text-muted-foreground">
                                        Connect your Linear account to start managing issues and projects
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    onClick={() =>
                                        (window.location.href = "/api/integrations/linear/auth/start")
                                    }
                                    className="flex items-center"
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect Linear Account
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
                                        <p className="text-sm font-medium text-muted-foreground">Total Issues</p>
                                        <div className="text-2xl font-bold">{totalIssues}</div>
                                        <p className="text-xs text-muted-foreground">Across all teams</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">In Progress</p>
                                        <div className="text-2xl font-bold">{inProgressIssues}</div>
                                        <p className="text-xs text-muted-foreground">Active work</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Completed</p>
                                        <div className="text-2xl font-bold">{completedIssues}</div>
                                        <p className="text-xs text-muted-foreground">Done this cycle</p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">Completion Rate</p>
                                        <div className="text-2xl font-bold">{Math.round(completionRate)}%</div>
                                        <Progress value={completionRate} className="mt-2 h-2" />
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="issues" className="w-full">
                            <TabsList>
                                <TabsTrigger value="issues">Issues</TabsTrigger>
                                <TabsTrigger value="teams">Teams</TabsTrigger>
                                <TabsTrigger value="projects">Projects</TabsTrigger>
                                <TabsTrigger value="cycles">Cycles</TabsTrigger>
                            </TabsList>

                            {/* Issues Tab */}
                            <TabsContent value="issues" className="space-y-6 mt-6">
                                {/* Filters and Actions */}
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="flex flex-col md:flex-row gap-4">
                                            <div className="relative flex-1">
                                                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                                <Input
                                                    placeholder="Search issues..."
                                                    value={searchQuery}
                                                    onChange={(e) => setSearchQuery(e.target.value)}
                                                    className="pl-8"
                                                />
                                            </div>
                                            <Select
                                                value={selectedTeam}
                                                onValueChange={setSelectedTeam}
                                            >
                                                <SelectTrigger className="w-[180px]">
                                                    <SelectValue placeholder="All Teams" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="all">All Teams</SelectItem>
                                                    {teams.map((team) => (
                                                        <SelectItem key={team.id} value={team.id}>
                                                            {team.name}
                                                        </SelectItem>
                                                    ))}
                                                </SelectContent>
                                            </Select>
                                            <Select
                                                value={selectedState}
                                                onValueChange={setSelectedState}
                                            >
                                                <SelectTrigger className="w-[180px]">
                                                    <SelectValue placeholder="All States" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="all">All States</SelectItem>
                                                    <SelectItem value="backlog">Backlog</SelectItem>
                                                    <SelectItem value="todo">Todo</SelectItem>
                                                    <SelectItem value="inProgress">In Progress</SelectItem>
                                                    <SelectItem value="done">Done</SelectItem>
                                                    <SelectItem value="canceled">Canceled</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <Select
                                                value={selectedPriority}
                                                onValueChange={setSelectedPriority}
                                            >
                                                <SelectTrigger className="w-[180px]">
                                                    <SelectValue placeholder="All Priorities" />
                                                </SelectTrigger>
                                                <SelectContent>
                                                    <SelectItem value="all">All Priorities</SelectItem>
                                                    <SelectItem value="0">No Priority</SelectItem>
                                                    <SelectItem value="1">Low</SelectItem>
                                                    <SelectItem value="2">Medium</SelectItem>
                                                    <SelectItem value="3">High</SelectItem>
                                                    <SelectItem value="4">Urgent</SelectItem>
                                                </SelectContent>
                                            </Select>
                                            <div className="flex-1" />
                                            <Button onClick={() => setIsModalOpen(true)} className="flex items-center">
                                                <Plus className="mr-2 w-4 h-4" />
                                                New Issue
                                            </Button>
                                        </div>
                                    </CardContent>
                                </Card>

                                {/* Issues Table */}
                                <Card>
                                    <CardContent className="pt-6">
                                        {loading.issues ? (
                                            <div className="flex flex-col items-center justify-center py-8 space-y-4">
                                                <p>Loading issues...</p>
                                                <Progress value={undefined} className="w-full max-w-md h-2" />
                                            </div>
                                        ) : filteredIssues.length === 0 ? (
                                            <div className="flex flex-col items-center justify-center py-8 space-y-4 text-center">
                                                <Clock className="w-12 h-12 text-muted-foreground" />
                                                <p className="text-muted-foreground">No issues found</p>
                                                <Button variant="outline" onClick={() => setIsModalOpen(true)}>
                                                    <Plus className="mr-2 w-4 h-4" />
                                                    Create Your First Issue
                                                </Button>
                                            </div>
                                        ) : (
                                            <div className="overflow-x-auto">
                                                <table className="w-full text-sm text-left">
                                                    <thead className="text-xs text-muted-foreground uppercase bg-muted/50">
                                                        <tr>
                                                            <th className="px-6 py-3">Title</th>
                                                            <th className="px-6 py-3">State</th>
                                                            <th className="px-6 py-3">Priority</th>
                                                            <th className="px-6 py-3">Team</th>
                                                            <th className="px-6 py-3">Updated</th>
                                                            <th className="px-6 py-3">Actions</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {filteredIssues.map((issue) => (
                                                            <tr key={issue.id} className="bg-background border-b hover:bg-muted/50">
                                                                <td className="px-6 py-4">
                                                                    <div className="flex flex-col space-y-1">
                                                                        <span className="font-medium">{issue.title}</span>
                                                                        {issue.description && (
                                                                            <span className="text-xs text-muted-foreground line-clamp-2">
                                                                                {issue.description}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                </td>
                                                                <td className="px-6 py-4">
                                                                    <Badge className={getStateColor(issue.state)}>
                                                                        {issue.state}
                                                                    </Badge>
                                                                </td>
                                                                <td className="px-6 py-4">
                                                                    <Badge className={getPriorityColor(issue.priority)}>
                                                                        {getPriorityLabel(issue.priority)}
                                                                    </Badge>
                                                                </td>
                                                                <td className="px-6 py-4 text-muted-foreground">
                                                                    {issue.team}
                                                                </td>
                                                                <td className="px-6 py-4 text-muted-foreground">
                                                                    {new Date(issue.updatedAt).toLocaleDateString()}
                                                                </td>
                                                                <td className="px-6 py-4">
                                                                    <Button
                                                                        variant="outline"
                                                                        size="sm"
                                                                        onClick={() => window.open(issue.url, "_blank")}
                                                                        className="flex items-center"
                                                                    >
                                                                        View
                                                                        <ArrowRight className="ml-2 w-3 h-3" />
                                                                    </Button>
                                                                </td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        )}
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Teams Tab */}
                            <TabsContent value="teams" className="space-y-6 mt-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                            {teams.map((team) => (
                                                <Card key={team.id} className="border shadow-sm">
                                                    <CardContent className="pt-6 space-y-3">
                                                        <h3 className="font-bold text-lg">{team.name}</h3>
                                                        <p className="text-sm text-muted-foreground">{team.description}</p>
                                                        <div className="flex items-center space-x-2">
                                                            <Badge variant="secondary">{team.key}</Badge>
                                                            <Badge variant="outline">{team.memberCount} members</Badge>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Projects Tab */}
                            <TabsContent value="projects" className="space-y-6 mt-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                            {projects.map((project) => (
                                                <Card key={project.id} className="border shadow-sm">
                                                    <CardContent className="pt-6 space-y-3">
                                                        <h3 className="font-bold text-lg">{project.name}</h3>
                                                        <p className="text-sm text-muted-foreground">{project.description}</p>
                                                        <div className="flex items-center space-x-2">
                                                            <Badge
                                                                className={
                                                                    project.state === "active"
                                                                        ? "bg-green-100 text-green-800"
                                                                        : "bg-gray-100 text-gray-800"
                                                                }
                                                            >
                                                                {project.state}
                                                            </Badge>
                                                            <div className="flex items-center space-x-2 flex-1">
                                                                <Progress value={project.progress} className="h-2 flex-1" />
                                                                <span className="text-xs text-muted-foreground">
                                                                    {Math.round(project.progress)}%
                                                                </span>
                                                            </div>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>

                            {/* Cycles Tab */}
                            <TabsContent value="cycles" className="space-y-6 mt-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                            {cycles.map((cycle) => (
                                                <Card key={cycle.id} className="border shadow-sm">
                                                    <CardContent className="pt-6 space-y-3">
                                                        <h3 className="font-bold text-lg">{cycle.name}</h3>
                                                        <p className="text-sm text-muted-foreground">Cycle {cycle.number}</p>
                                                        <div className="space-y-1 w-full">
                                                            <div className="flex justify-between text-xs text-muted-foreground">
                                                                <span>{new Date(cycle.startsAt).toLocaleDateString()}</span>
                                                                <span>{new Date(cycle.endsAt).toLocaleDateString()}</span>
                                                            </div>
                                                            <Progress value={cycle.progress} className="h-2" />
                                                            <div className="text-right text-xs text-muted-foreground">
                                                                {Math.round(cycle.progress)}% Complete
                                                            </div>
                                                        </div>
                                                    </CardContent>
                                                </Card>
                                            ))}
                                        </div>
                                    </CardContent>
                                </Card>
                            </TabsContent>
                        </Tabs>
                    </>
                )}
            </div>

            {/* Create Issue Modal */}
            <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create New Issue</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label htmlFor="title">Title</Label>
                            <Input
                                id="title"
                                placeholder="Issue title"
                                value={newIssue.title}
                                onChange={(e) => setNewIssue({ ...newIssue, title: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="description">Description</Label>
                            <Textarea
                                id="description"
                                placeholder="Issue description"
                                value={newIssue.description}
                                onChange={(e) => setNewIssue({ ...newIssue, description: e.target.value })}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="team">Team</Label>
                            <Select
                                value={newIssue.teamId}
                                onValueChange={(value) => setNewIssue({ ...newIssue, teamId: value })}
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select team" />
                                </SelectTrigger>
                                <SelectContent>
                                    {teams.map((team) => (
                                        <SelectItem key={team.id} value={team.id}>
                                            {team.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="priority">Priority</Label>
                            <Select
                                value={newIssue.priority.toString()}
                                onValueChange={(value) =>
                                    setNewIssue({ ...newIssue, priority: parseInt(value) })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select priority" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="0">No Priority</SelectItem>
                                    <SelectItem value="1">Low</SelectItem>
                                    <SelectItem value="2">Medium</SelectItem>
                                    <SelectItem value="3">High</SelectItem>
                                    <SelectItem value="4">Urgent</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setIsModalOpen(false)}>
                            Cancel
                        </Button>
                        <Button onClick={createIssue}>Create Issue</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default LinearIntegration;
