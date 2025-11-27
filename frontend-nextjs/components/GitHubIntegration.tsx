/**
 * GitHub Integration Component
 * Complete GitHub repository and project management integration
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
    Loader2,
    Eye,
    Star,
    ExternalLink,
    MessageSquare,
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

interface GitHubRepository {
    id: number;
    name: string;
    full_name: string;
    description: string;
    private: boolean;
    fork: boolean;
    html_url: string;
    clone_url: string;
    ssh_url: string;
    language: string;
    languages_url: string;
    stargazers_count: number;
    watchers_count: number;
    forks_count: number;
    open_issues_count: number;
    size: number;
    default_branch: string;
    created_at: string;
    updated_at: string;
    pushed_at: string;
    owner: {
        login: string;
        id: number;
        avatar_url: string;
        type: string;
    };
}

interface GitHubIssue {
    id: number;
    number: number;
    title: string;
    body: string;
    state: "open" | "closed";
    locked: boolean;
    comments: number;
    created_at: string;
    updated_at: string;
    closed_at: string;
    html_url: string;
    user: {
        login: string;
        id: number;
        avatar_url: string;
    };
    assignee?: {
        login: string;
        id: number;
        avatar_url: string;
    };
    labels: Array<{
        id: number;
        name: string;
        color: string;
    }>;
    milestone?: {
        id: number;
        title: string;
        state: string;
    };
    pull_request?: {
        url: string;
        html_url: string;
    };
}

interface GitHubUser {
    id: number;
    login: string;
    name: string;
    email?: string;
    bio?: string;
    company?: string;
    location?: string;
    blog?: string;
    avatar_url: string;
    html_url: string;
    public_repos: number;
    followers: number;
    following: number;
    created_at: string;
    updated_at: string;
    type: "User" | "Bot";
}

const GitHubIntegration: React.FC = () => {
    const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
    const [issues, setIssues] = useState<GitHubIssue[]>([]);
    const [userProfile, setUserProfile] = useState<GitHubUser | null>(null);
    const [loading, setLoading] = useState({
        repositories: false,
        issues: false,
        profile: false,
    });
    const [connected, setConnected] = useState(false);
    const [healthStatus, setHealthStatus] = useState<
        "healthy" | "error" | "unknown"
    >("unknown");
    const [searchQuery, setSearchQuery] = useState("");
    const [selectedRepository, setSelectedRepository] = useState("");

    const [isIssueModalOpen, setIsIssueModalOpen] = useState(false);
    const [isRepoModalOpen, setIsRepoModalOpen] = useState(false);

    const [newIssue, setNewIssue] = useState({
        title: "",
        body: "",
        repository: "",
        labels: [] as string[],
    });

    const [newRepository, setNewRepository] = useState({
        name: "",
        description: "",
        private: false,
    });

    const { toast } = useToast();

    // Check connection status
    const checkConnection = async () => {
        try {
            const response = await fetch("/api/integrations/github/health");
            if (response.ok) {
                setConnected(true);
                setHealthStatus("healthy");
                loadUserProfile();
                loadRepositories();
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

    // Load GitHub data
    const loadUserProfile = async () => {
        setLoading((prev) => ({ ...prev, profile: true }));
        try {
            const response = await fetch("/api/integrations/github/profile", {
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

    const loadRepositories = async () => {
        setLoading((prev) => ({ ...prev, repositories: true }));
        try {
            const response = await fetch("/api/integrations/github/repositories", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    limit: 100,
                    type: "owner",
                }),
            });

            if (response.ok) {
                const data = await response.json();
                setRepositories(data.data?.repositories || []);
            }
        } catch (error) {
            console.error("Failed to load repositories:", error);
            toast({
                title: "Error",
                description: "Failed to load repositories from GitHub",
                variant: "destructive",
            });
        } finally {
            setLoading((prev) => ({ ...prev, repositories: false }));
        }
    };

    const loadIssues = async (repoName?: string) => {
        setLoading((prev) => ({ ...prev, issues: true }));
        try {
            const response = await fetch("/api/integrations/github/issues", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    repository: repoName || selectedRepository,
                    state: "open",
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

    const createIssue = async () => {
        if (!newIssue.title || !newIssue.repository) return;

        try {
            const response = await fetch("/api/integrations/github/issues/create", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    user_id: "current",
                    repository: newIssue.repository,
                    title: newIssue.title,
                    body: newIssue.body,
                    labels: newIssue.labels,
                }),
            });

            if (response.ok) {
                toast({
                    title: "Success",
                    description: "Issue created successfully",
                });
                setIsIssueModalOpen(false);
                setNewIssue({ title: "", body: "", repository: "", labels: [] });
                if (newIssue.repository === selectedRepository) {
                    loadIssues(selectedRepository);
                }
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

    // Filter data based on search
    const filteredRepositories = repositories.filter(
        (repo) =>
            repo.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
            repo.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            repo.language?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const filteredIssues = issues.filter(
        (issue) =>
            issue.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
            issue.body?.toLowerCase().includes(searchQuery.toLowerCase()) ||
            issue.user.login.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Stats calculations
    const totalRepos = repositories.length;
    const publicRepos = repositories.filter((repo) => !repo.private).length;
    const privateRepos = repositories.filter((repo) => repo.private).length;
    const totalStars = repositories.reduce(
        (sum, repo) => sum + repo.stargazers_count,
        0
    );
    const totalForks = repositories.reduce(
        (sum, repo) => sum + repo.forks_count,
        0
    );
    const openIssues = issues.filter((issue) => issue.state === "open").length;

    useEffect(() => {
        checkConnection();
    }, []);

    useEffect(() => {
        if (connected) {
            loadUserProfile();
            loadRepositories();
        }
    }, [connected]);

    useEffect(() => {
        if (selectedRepository) {
            loadIssues(selectedRepository);
        }
    }, [selectedRepository]);

    const formatDate = (dateString: string): string => {
        return new Date(dateString).toLocaleString();
    };

    const getLanguageColor = (language: string): string => {
        const colors: { [key: string]: string } = {
            JavaScript: "bg-yellow-100 text-yellow-800",
            TypeScript: "bg-blue-100 text-blue-800",
            Python: "bg-green-100 text-green-800",
            Java: "bg-orange-100 text-orange-800",
            Go: "bg-cyan-100 text-cyan-800",
            Rust: "bg-orange-100 text-orange-800",
            Ruby: "bg-red-100 text-red-800",
            PHP: "bg-purple-100 text-purple-800",
            "C++": "bg-blue-100 text-blue-800",
            C: "bg-gray-100 text-gray-800",
            Shell: "bg-gray-100 text-gray-800",
            HTML: "bg-orange-100 text-orange-800",
            CSS: "bg-blue-100 text-blue-800",
        };
        return colors[language] || "bg-gray-100 text-gray-800";
    };

    const getStateColor = (state: string): string => {
        return state === "open"
            ? "bg-green-100 text-green-800"
            : "bg-gray-100 text-gray-800";
    };

    return (
        <div className="min-h-screen bg-background p-6">
            <div className="max-w-[1400px] mx-auto space-y-8">
                {/* Header */}
                <div className="flex flex-col space-y-4">
                    <div className="flex items-center space-x-4">
                        <Eye className="w-8 h-8 text-black" />
                        <div className="flex flex-col space-y-1">
                            <h1 className="text-3xl font-bold">GitHub Integration</h1>
                            <p className="text-lg text-muted-foreground">
                                Complete repository and project management platform
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
                                <AvatarImage src={userProfile.avatar_url} />
                                <AvatarFallback>{userProfile.login.slice(0, 2)}</AvatarFallback>
                            </Avatar>
                            <div className="flex flex-col">
                                <p className="font-bold">
                                    {userProfile.name || userProfile.login}
                                </p>
                                <p className="text-sm text-muted-foreground">
                                    @{userProfile.login}
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
                                    <h2 className="text-2xl font-semibold">Connect GitHub</h2>
                                    <p className="text-muted-foreground">
                                        Connect your GitHub account to start managing repositories
                                        and projects
                                    </p>
                                </div>
                                <Button
                                    size="lg"
                                    onClick={() =>
                                    (window.location.href =
                                        "/api/integrations/github/auth/start")
                                    }
                                    className="flex items-center bg-black hover:bg-gray-800"
                                >
                                    <ArrowRight className="mr-2 w-4 h-4" />
                                    Connect GitHub Account
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
                                        <p className="text-sm font-medium text-muted-foreground">
                                            Repositories
                                        </p>
                                        <div className="text-2xl font-bold">{totalRepos}</div>
                                        <p className="text-xs text-muted-foreground">
                                            {privateRepos} private, {publicRepos} public
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">
                                            Stars
                                        </p>
                                        <div className="text-2xl font-bold">{totalStars}</div>
                                        <p className="text-xs text-muted-foreground">
                                            Across all repos
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">
                                            Open Issues
                                        </p>
                                        <div className="text-2xl font-bold">{openIssues}</div>
                                        <p className="text-xs text-muted-foreground">
                                            Need attention
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                            <Card>
                                <CardContent className="pt-6">
                                    <div className="space-y-1">
                                        <p className="text-sm font-medium text-muted-foreground">
                                            Forks
                                        </p>
                                        <div className="text-2xl font-bold">{totalForks}</div>
                                        <p className="text-xs text-muted-foreground">
                                            Community contributions
                                        </p>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>

                        {/* Main Content Tabs */}
                        <Tabs defaultValue="repositories" className="w-full">
                            <TabsList>
                                <TabsTrigger value="repositories">Repositories</TabsTrigger>
                                <TabsTrigger value="issues">Issues</TabsTrigger>
                                <TabsTrigger value="profile">Profile</TabsTrigger>
                            </TabsList>

                            {/* Repositories Tab */}
                            <TabsContent value="repositories" className="space-y-6 mt-6">
                                <div className="flex items-center space-x-4">
                                    <div className="relative flex-1">
                                        <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                                        <Input
                                            placeholder="Search repositories..."
                                            value={searchQuery}
                                            onChange={(e) => setSearchQuery(e.target.value)}
                                            className="pl-8"
                                        />
                                    </div>
                                    <div className="flex-1" />
                                    <Button
                                        onClick={() => setIsRepoModalOpen(true)}
                                        className="flex items-center bg-black hover:bg-gray-800"
                                    >
                                        <Plus className="mr-2 w-4 h-4" />
                                        New Repository
                                    </Button>
                                </div>

                                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                                    {loading.repositories ? (
                                        <div className="flex items-center justify-center py-8">
                                            <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                                        </div>
                                    ) : (
                                        filteredRepositories.map((repo) => (
                                            <Card
                                                key={repo.id}
                                                className={`cursor-pointer hover:shadow-md transition-all border ${selectedRepository === repo.full_name
                                                        ? "border-blue-500"
                                                        : "border-border"
                                                    }`}
                                                onClick={() => setSelectedRepository(repo.full_name)}
                                            >
                                                <CardHeader>
                                                    <div className="flex flex-col space-y-2">
                                                        <div className="flex items-center justify-between">
                                                            <p className="font-bold text-lg">{repo.name}</p>
                                                            <div className="flex items-center space-x-1">
                                                                {repo.private && (
                                                                    <Badge variant="outline">Private</Badge>
                                                                )}
                                                                {repo.fork && (
                                                                    <Badge variant="secondary">Fork</Badge>
                                                                )}
                                                            </div>
                                                        </div>
                                                        <p className="text-sm text-muted-foreground">
                                                            {repo.description}
                                                        </p>
                                                    </div>
                                                </CardHeader>
                                                <CardContent className="space-y-3">
                                                    {repo.language && (
                                                        <Badge className={getLanguageColor(repo.language)}>
                                                            {repo.language}
                                                        </Badge>
                                                    )}
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center space-x-4">
                                                            <div className="flex items-center space-x-1">
                                                                <Star className="w-4 h-4 text-yellow-500" />
                                                                <span className="text-sm">
                                                                    {repo.stargazers_count}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center space-x-1">
                                                                <Eye className="w-4 h-4 text-blue-500" />
                                                                <span className="text-sm">
                                                                    {repo.watchers_count}
                                                                </span>
                                                            </div>
                                                        </div>
                                                        <a
                                                            href={repo.html_url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            onClick={(e) => e.stopPropagation()}
                                                        >
                                                            <ExternalLink className="w-4 h-4" />
                                                        </a>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    )}
                                </div>
                            </TabsContent>

                            {/* Issues Tab */}
                            <TabsContent value="issues" className="space-y-6 mt-6">
                                <div className="flex flex-col md:flex-row gap-4">
                                    <Select
                                        value={selectedRepository}
                                        onValueChange={setSelectedRepository}
                                    >
                                        <SelectTrigger className="w-[300px]">
                                            <SelectValue placeholder="Select repository" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {repositories.map((repo) => (
                                                <SelectItem key={repo.id} value={repo.full_name}>
                                                    {repo.full_name}
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
                                        disabled={!selectedRepository}
                                        className="flex items-center bg-black hover:bg-gray-800"
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
                                    ) : selectedRepository ? (
                                        filteredIssues.map((issue) => (
                                            <Card key={issue.id}>
                                                <CardContent className="pt-6">
                                                    <div className="flex items-start space-x-4">
                                                        <Avatar className="w-8 h-8">
                                                            <AvatarImage src={issue.user.avatar_url} />
                                                            <AvatarFallback>
                                                                {issue.user.login.slice(0, 2)}
                                                            </AvatarFallback>
                                                        </Avatar>
                                                        <div className="flex flex-col space-y-2 flex-1">
                                                            <div className="flex items-center justify-between">
                                                                <div className="flex items-center space-x-2">
                                                                    <a
                                                                        href={issue.html_url}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                    >
                                                                        <p className="font-bold">
                                                                            #{issue.number} {issue.title}
                                                                        </p>
                                                                    </a>
                                                                    <Badge className={getStateColor(issue.state)}>
                                                                        {issue.state}
                                                                    </Badge>
                                                                </div>
                                                                <p className="text-xs text-muted-foreground">
                                                                    {formatDate(issue.created_at)}
                                                                </p>
                                                            </div>
                                                            <p className="text-sm text-muted-foreground">
                                                                {issue.body?.substring(0, 200)}
                                                                {issue.body && issue.body.length > 200 && "..."}
                                                            </p>
                                                            <div className="flex items-center space-x-4">
                                                                {issue.labels.map((label) => (
                                                                    <Badge
                                                                        key={label.id}
                                                                        style={{ backgroundColor: `#${label.color}` }}
                                                                        className="text-white"
                                                                    >
                                                                        {label.name}
                                                                    </Badge>
                                                                ))}
                                                                <div className="flex items-center space-x-1">
                                                                    <MessageSquare className="w-4 h-4 text-muted-foreground" />
                                                                    <span className="text-xs">
                                                                        {issue.comments}
                                                                    </span>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    </div>
                                                </CardContent>
                                            </Card>
                                        ))
                                    ) : (
                                        <p className="text-muted-foreground text-center py-8">
                                            Select a repository to view issues
                                        </p>
                                    )}
                                </div>
                            </TabsContent>

                            {/* Profile Tab */}
                            <TabsContent value="profile" className="mt-6">
                                <Card>
                                    <CardContent className="pt-6">
                                        {userProfile ? (
                                            <div className="flex flex-col space-y-6">
                                                <div className="flex items-center space-x-6">
                                                    <Avatar className="w-24 h-24">
                                                        <AvatarImage src={userProfile.avatar_url} />
                                                        <AvatarFallback>
                                                            {userProfile.login.slice(0, 2)}
                                                        </AvatarFallback>
                                                    </Avatar>
                                                    <div className="flex flex-col space-y-2">
                                                        <h2 className="text-2xl font-bold">
                                                            {userProfile.name || userProfile.login}
                                                        </h2>
                                                        <p className="text-muted-foreground">
                                                            @{userProfile.login}
                                                        </p>
                                                        {userProfile.bio && <p>{userProfile.bio}</p>}
                                                        <a
                                                            href={userProfile.html_url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                        >
                                                            <Button size="sm" className="flex items-center">
                                                                <ExternalLink className="mr-2 w-4 h-4" />
                                                                View Profile
                                                            </Button>
                                                        </a>
                                                    </div>
                                                </div>

                                                <div className="border-t pt-6" />

                                                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                                                    <div>
                                                        <p className="text-sm font-medium text-muted-foreground">
                                                            Public Repositories
                                                        </p>
                                                        <div className="text-2xl font-bold">
                                                            {userProfile.public_repos}
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-medium text-muted-foreground">
                                                            Followers
                                                        </p>
                                                        <div className="text-2xl font-bold">
                                                            {userProfile.followers}
                                                        </div>
                                                    </div>
                                                    <div>
                                                        <p className="text-sm font-medium text-muted-foreground">
                                                            Following
                                                        </p>
                                                        <div className="text-2xl font-bold">
                                                            {userProfile.following}
                                                        </div>
                                                    </div>
                                                </div>

                                                <div className="border-t pt-6" />

                                                <div className="flex flex-col space-y-2">
                                                    <p className="font-bold">Account Details</p>
                                                    {userProfile.company && (
                                                        <p>Company: {userProfile.company}</p>
                                                    )}
                                                    {userProfile.location && (
                                                        <p>Location: {userProfile.location}</p>
                                                    )}
                                                    {userProfile.blog && (
                                                        <p>Website: {userProfile.blog}</p>
                                                    )}
                                                    {userProfile.email && (
                                                        <p>Email: {userProfile.email}</p>
                                                    )}
                                                    <p>Account Type: {userProfile.type}</p>
                                                    <p>
                                                        Member Since: {formatDate(userProfile.created_at)}
                                                    </p>
                                                </div>
                                            </div>
                                        ) : (
                                            <p className="text-muted-foreground">
                                                Loading profile information...
                                            </p>
                                        )}
                                    </CardContent>
                                </Card>
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
                            <Label htmlFor="issue-repo">Repository</Label>
                            <Select
                                value={newIssue.repository}
                                onValueChange={(value) =>
                                    setNewIssue({ ...newIssue, repository: value })
                                }
                            >
                                <SelectTrigger>
                                    <SelectValue placeholder="Select a repository" />
                                </SelectTrigger>
                                <SelectContent>
                                    {repositories.map((repo) => (
                                        <SelectItem key={repo.id} value={repo.full_name}>
                                            {repo.full_name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="issue-title">Title</Label>
                            <Input
                                id="issue-title"
                                placeholder="Issue title"
                                value={newIssue.title}
                                onChange={(e) =>
                                    setNewIssue({ ...newIssue, title: e.target.value })
                                }
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="issue-description">Description</Label>
                            <Textarea
                                id="issue-description"
                                placeholder="Describe the issue..."
                                value={newIssue.body}
                                onChange={(e) =>
                                    setNewIssue({ ...newIssue, body: e.target.value })
                                }
                                rows={6}
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setIsIssueModalOpen(false)}
                        >
                            Cancel
                        </Button>
                        <Button
                            onClick={createIssue}
                            disabled={!newIssue.title || !newIssue.repository}
                            className="bg-black hover:bg-gray-800"
                        >
                            Create Issue
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
};

export default GitHubIntegration;
