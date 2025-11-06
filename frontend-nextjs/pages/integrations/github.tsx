/**
 * GitHub Integration Page
 * Complete GitHub integration with comprehensive repository and code management features
 */

import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  Loader2, 
  Github, 
  Code, 
  GitBranch, 
  FileText, 
  Users, 
  Search, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Star,
  Eye,
  ForkLeft,
  MessageSquare,
  GitPullRequest,
  GitMerge,
  User,
  Calendar,
  Clock,
  Issue,
  ChevronRight,
  Filter
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface GitHubRepository {
  id: number;
  name: string;
  fullName: string;
  description?: string;
  private: boolean;
  fork: boolean;
  htmlUrl: string;
  cloneUrl: string;
  sshUrl: string;
  language?: string;
  stargazersCount: number;
  watchersCount: number;
  forksCount: number;
  openIssuesCount: number;
  defaultBranch: string;
  createdAt: string;
  updatedAt: string;
  pushedAt?: string;
  size: number;
  owner: {
    login: string;
    avatarUrl?: string;
  };
  topics: string[];
  license?: {
    name: string;
  };
  visibility: 'public' | 'private';
}

interface GitHubIssue {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: 'open' | 'closed';
  locked: boolean;
  comments: number;
  createdAt: string;
  updatedAt: string;
  closedAt?: string;
  user: {
    login: string;
    avatarUrl?: string;
  };
  assignee?: {
    login: string;
    avatarUrl?: string;
  };
  assignees: Array<{
    login: string;
    avatarUrl?: string;
  }>;
  labels: Array<{
    name: string;
    color: string;
  }>;
  milestone?: {
    title: string;
    state: 'open' | 'closed';
  };
  htmlUrl: string;
  reactions: {
    totalCount: number;
    plusOne: number;
    laugh: number;
    hooray: number;
    confused: number;
    heart: number;
    rocket: number;
    eyes: number;
  };
  repositoryUrl: string;
}

interface GitHubPullRequest {
  id: number;
  number: number;
  title: string;
  body?: string;
  state: 'open' | 'closed';
  locked: boolean;
  createdAt: string;
  updatedAt: string;
  closedAt?: string;
  mergedAt?: string;
  user: {
    login: string;
    avatarUrl?: string;
  };
  assignee?: {
    login: string;
    avatarUrl?: string;
  };
  assignees: Array<{
    login: string;
    avatarUrl?: string;
  }>;
  requestedReviewers: Array<{
    login: string;
    avatarUrl?: string;
  }>;
  labels: Array<{
    name: string;
    color: string;
  }>;
  milestone?: {
    title: string;
    state: 'open' | 'closed';
  };
  head: {
    label: string;
    ref: string;
    sha: string;
    repo: {
      name: string;
      fullName: string;
    };
  };
  base: {
    label: string;
    ref: string;
    sha: string;
    repo: {
      name: string;
      fullName: string;
    };
  };
  htmlUrl: string;
  diffUrl: string;
  patchUrl: string;
  mergeable?: boolean;
  merged: boolean;
  mergeableState?: 'clean' | 'conflicting' | 'unstable';
  comments: number;
  reviewComments: number;
  commits: number;
  additions: number;
  deletions: number;
  changedFiles: number;
}

interface GitHubUser {
  id: number;
  login: string;
  name?: string;
  email?: string;
  avatarUrl?: string;
  htmlUrl: string;
  type: 'User' | 'Organization';
  siteAdmin?: boolean;
  company?: string;
  blog?: string;
  location?: string;
  email?: string;
  hireable?: boolean;
  bio?: string;
  twitterUsername?: string;
  publicRepos: number;
  publicGists: number;
  followers: number;
  following: number;
  createdAt: string;
  updatedAt: string;
}

interface GitHubStatus {
  service: string;
  status: 'healthy' | 'degraded' | 'error' | 'unavailable';
  timestamp: string;
  components: {
    service?: { status: string; message: string };
    configuration?: { status: string; client_id_configured: boolean };
    database?: { status: string; message: string };
    api?: { status: string; rate_limit_remaining: number };
  };
}

export default function GitHubIntegration() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('demo-user');
  const [status, setStatus] = useState<GitHubStatus | null>(null);
  const [userInfo, setUserInfo] = useState<GitHubUser | null>(null);
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [issues, setIssues] = useState<GitHubIssue[]>([]);
  const [pullRequests, setPullRequests] = useState<GitHubPullRequest[]>([]);
  const [users, setUsers] = useState<GitHubUser[]>([]);
  const [selectedRepository, setSelectedRepository] = useState('');
  const [issueTitle, setIssueTitle] = useState('');
  const [issueBody, setIssueBody] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
  const GITHUB_ENHANCED_URL = `${API_BASE_URL}/api/integrations/github`;
  const GITHUB_OAUTH_URL = `${API_BASE_URL}/api/auth/github`;

  // Load initial data
  useEffect(() => {
    loadStatus();
    if (activeTab === 'repositories') {
      loadRepositories();
    } else if (activeTab === 'issues') {
      loadIssues();
    } else if (activeTab === 'pulls') {
      loadPullRequests();
    } else if (activeTab === 'users') {
      loadUsers();
    }
  }, [activeTab]);

  const loadStatus = async () => {
    try {
      const response = await fetch(`${GITHUB_ENHANCED_URL}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
      setStatus({
        service: 'github_enhanced',
        status: 'error',
        timestamp: new Date().toISOString(),
        components: {}
      });
    }
  };

  const loadUserInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${GITHUB_ENHANCED_URL}/users/profile`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setUserInfo(data.data.user);
        toast({
          title: "User info loaded",
          description: `Successfully loaded profile for ${data.data.user.login}`,
        });
      } else {
        toast({
          title: "Failed to load user info",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load user info:', error);
      toast({
        title: "Error loading user info",
        description: "Could not connect to GitHub service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadRepositories = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${GITHUB_ENHANCED_URL}/repositories/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setRepositories(data.data.repositories);
        toast({
          title: "Repositories loaded",
          description: `Loaded ${data.data.repositories.length} repositories`,
        });
      } else {
        toast({
          title: "Failed to load repositories",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load repositories:', error);
      toast({
        title: "Error loading repositories",
        description: "Could not connect to GitHub service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadIssues = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${GITHUB_ENHANCED_URL}/issues/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          owner: selectedRepository.split('/')[0],
          repo: selectedRepository.split('/')[1],
          state: 'open',
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setIssues(data.data.issues);
        toast({
          title: "Issues loaded",
          description: `Loaded ${data.data.issues.length} issues from ${selectedRepository}`,
        });
      } else {
        toast({
          title: "Failed to load issues",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load issues:', error);
      toast({
        title: "Error loading issues",
        description: "Could not connect to GitHub service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadPullRequests = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${GITHUB_ENHANCED_URL}/pulls/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          owner: selectedRepository.split('/')[0],
          repo: selectedRepository.split('/')[1],
          state: 'open',
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setPullRequests(data.data.pullRequests);
        toast({
          title: "Pull requests loaded",
          description: `Loaded ${data.data.pullRequests.length} pull requests from ${selectedRepository}`,
        });
      } else {
        toast({
          title: "Failed to load pull requests",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load pull requests:', error);
      toast({
        title: "Error loading pull requests",
        description: "Could not connect to GitHub service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${GITHUB_ENHANCED_URL}/users/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 200
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setUsers(data.data.users);
        toast({
          title: "Users loaded",
          description: `Loaded ${data.data.users.length} users`,
        });
      } else {
        toast({
          title: "Failed to load users",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load users:', error);
      toast({
        title: "Error loading users",
        description: "Could not connect to GitHub service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const createIssue = async () => {
    if (!issueTitle.trim() || !selectedRepository) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${GITHUB_ENHANCED_URL}/issues/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          owner: selectedRepository.split('/')[0],
          repo: selectedRepository.split('/')[1],
          title: issueTitle.trim(),
          body: issueBody.trim()
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setIssueTitle('');
        setIssueBody('');
        toast({
          title: "Issue created",
          description: "Issue created successfully",
        });
        // Reload issues
        setTimeout(() => loadIssues(), 1000);
      } else {
        toast({
          title: "Failed to create issue",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to create issue:', error);
      toast({
        title: "Error creating issue",
        description: "Could not connect to GitHub service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const initiateOAuth = async () => {
    try {
      const response = await fetch(`${GITHUB_OAUTH_URL}/authorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Redirect to OAuth URL
        window.location.href = data.oauth_url;
      } else {
        toast({
          title: "OAuth failed",
          description: data.error || "Could not initiate OAuth flow",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('OAuth initiation failed:', error);
      toast({
        title: "OAuth error",
        description: "Could not initiate OAuth flow",
        variant: "destructive",
      });
    }
  };

  const formatDateTime = (dateTime: string) => {
    return new Date(dateTime).toLocaleString();
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy': return 'bg-green-500';
      case 'degraded': return 'bg-yellow-500';
      case 'error': return 'bg-red-500';
      case 'unavailable': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="h-4 w-4" />;
      case 'degraded': return <AlertCircle className="h-4 w-4" />;
      case 'error': return <AlertCircle className="h-4 w-4" />;
      case 'unavailable': return <AlertCircle className="h-4 w-4" />;
      default: return <AlertCircle className="h-4 w-4" />;
    }
  };

  const getRepositoryIcon = (repo: GitHubRepository) => {
    if (repo.private) {
      return <Github className="h-6 w-6 text-gray-500" />;
    } else if (repo.fork) {
      return <ForkLeft className="h-6 w-6 text-blue-500" />;
    } else {
      return <Github className="h-6 w-6 text-black" />;
    }
  };

  const getIssueStateColor = (state: string) => {
    switch (state) {
      case 'open': return 'bg-green-500';
      case 'closed': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getPRStateColor = (pr: GitHubPullRequest) => {
    if (pr.merged) {
      return 'bg-purple-500';
    } else if (pr.state === 'closed') {
      return 'bg-red-500';
    } else {
      return 'bg-green-500';
    }
  };

  const getPRMergeableColor = (mergeableState?: string) => {
    switch (mergeableState) {
      case 'clean': return 'bg-green-500';
      case 'conflicting': return 'bg-red-500';
      case 'unstable': return 'bg-yellow-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold flex items-center">
          <Github className="h-8 w-8 mr-3" />
          GitHub Integration
        </h1>
        <div className="flex items-center space-x-2">
          {status && (
            <Badge variant="outline" className={`${getStatusColor(status.status)} text-white`}>
              {getStatusIcon(status.status)}
              <span className="ml-1">{status.status}</span>
            </Badge>
          )}
          <Button onClick={loadStatus} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Status Alert */}
      {status && status.status !== 'healthy' && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            GitHub integration is {status.status}. 
            {status.components.configuration?.status !== 'configured' && 
              " OAuth configuration is incomplete. Please check environment variables."}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-8">
          <TabsTrigger value="overview" className="flex items-center">
            <Settings className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="repositories" className="flex items-center">
            <Github className="h-4 w-4 mr-2" />
            Repositories
          </TabsTrigger>
          <TabsTrigger value="issues" className="flex items-center">
            <Issue className="h-4 w-4 mr-2" />
            Issues
          </TabsTrigger>
          <TabsTrigger value="pulls" className="flex items-center">
            <GitPullRequest className="h-4 w-4 mr-2" />
            Pulls
          </TabsTrigger>
          <TabsTrigger value="users" className="flex items-center">
            <Users className="h-4 w-4 mr-2" />
            Users
          </TabsTrigger>
          <TabsTrigger value="actions" className="flex items-center">
            <GitBranch className="h-4 w-4 mr-2" />
            Actions
          </TabsTrigger>
          <TabsTrigger value="workflows" className="flex items-center">
            <GitMerge className="h-4 w-4 mr-2" />
            Workflows
          </TabsTrigger>
          <TabsTrigger value="oauth" className="flex items-center">
            <Search className="h-4 w-4 mr-2" />
            OAuth
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Service Status */}
            <Card>
              <CardHeader>
                <CardTitle>Service Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {status ? (
                  <>
                    <div className="flex items-center justify-between">
                      <span>Service</span>
                      <Badge variant={status.components.service?.status === 'available' ? 'default' : 'destructive'}>
                        {status.components.service?.status}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Configuration</span>
                      <Badge variant={status.components.configuration?.status === 'configured' ? 'default' : 'destructive'}>
                        {status.components.configuration?.status}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>Database</span>
                      <Badge variant={status.components.database?.status === 'connected' ? 'default' : 'destructive'}>
                        {status.components.database?.status}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span>API</span>
                      <Badge variant={status.components.api?.status === 'connected' ? 'default' : 'destructive'}>
                        {status.components.api?.status}
                      </Badge>
                    </div>
                  </>
                ) : (
                  <div className="text-center py-4">
                    <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    <p className="text-sm text-muted-foreground mt-2">Loading status...</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* User Info */}
            <Card>
              <CardHeader>
                <CardTitle>User Profile</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="userId">User ID</Label>
                  <Input
                    id="userId"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="Enter user ID"
                  />
                </div>
                <Button 
                  onClick={loadUserInfo} 
                  disabled={loading || !userId}
                  className="w-full"
                >
                  {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                  Load Profile
                </Button>
                
                {userInfo && (
                  <div className="space-y-2 pt-4 border-t">
                    <div className="flex items-center space-x-3">
                      {userInfo.avatarUrl && (
                        <img 
                          src={userInfo.avatarUrl} 
                          alt={userInfo.login}
                          className="w-12 h-12 rounded-full"
                        />
                      )}
                      <div>
                        <div className="font-medium">{userInfo.login}</div>
                        <div className="text-sm text-muted-foreground">{userInfo.name}</div>
                      </div>
                    </div>
                    {userInfo.company && (
                      <div>
                        <span className="font-medium">Company:</span> {userInfo.company}
                      </div>
                    )}
                    {userInfo.location && (
                      <div>
                        <span className="font-medium">Location:</span> {userInfo.location}
                      </div>
                    )}
                    <div>
                      <span className="font-medium">Public Repos:</span> {userInfo.publicRepos}
                    </div>
                    <div>
                      <span className="font-medium">Followers:</span> {userInfo.followers}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="repositories" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Github className="h-5 w-5 mr-2" />
                GitHub Repositories
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {repositories.length > 0 ? (
                  repositories.map((repo) => (
                    <div key={repo.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {getRepositoryIcon(repo)}
                          <h4 className="font-medium">{repo.name}</h4>
                        </div>
                        <div className="flex items-center space-x-2">
                          {repo.private && <Badge variant="outline" className="text-xs">Private</Badge>}
                          {repo.fork && <Badge variant="outline" className="text-xs">Fork</Badge>}
                          {repo.language && <Badge variant="default" className="text-xs">{repo.language}</Badge>}
                        </div>
                      </div>
                      {repo.description && (
                        <div className="text-sm text-muted-foreground">
                          {repo.description}
                        </div>
                      )}
                      <div className="flex items-center space-x-4 text-sm text-muted-foreground">
                        <div className="flex items-center space-x-1">
                          <Star className="h-3 w-3" />
                          <span>{repo.stargazersCount}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <ForkLeft className="h-3 w-3" />
                          <span>{repo.forksCount}</span>
                        </div>
                        <div className="flex items-center space-x-1">
                          <Eye className="h-3 w-3" />
                          <span>{repo.watchersCount}</span>
                        </div>
                        {repo.openIssuesCount > 0 && (
                          <div className="flex items-center space-x-1">
                            <Issue className="h-3 w-3" />
                            <span>{repo.openIssuesCount}</span>
                          </div>
                        )}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Updated:</strong> {formatDateTime(repo.updatedAt)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No repositories found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadRepositories} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Repositories
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="issues" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Issue className="h-5 w-5 mr-2" />
                GitHub Issues
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Repository Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="repoSelect">Select Repository</Label>
                <Select value={selectedRepository} onValueChange={setSelectedRepository}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a repository" />
                  </SelectTrigger>
                  <SelectContent>
                    {repositories.map((repo) => (
                      <SelectItem key={repo.id} value={repo.fullName}>
                        <div className="flex items-center space-x-2">
                          {getRepositoryIcon(repo)}
                          <span>{repo.fullName}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Issue Creation */}
              {selectedRepository && (
                <div className="space-y-2 mb-4 border rounded-lg p-3">
                  <Label htmlFor="issueTitle">Issue Title</Label>
                  <Input
                    id="issueTitle"
                    value={issueTitle}
                    onChange={(e) => setIssueTitle(e.target.value)}
                    placeholder="Enter issue title"
                    className="mb-2"
                  />
                  <Label htmlFor="issueBody">Description</Label>
                  <Textarea
                    id="issueBody"
                    value={issueBody}
                    onChange={(e) => setIssueBody(e.target.value)}
                    placeholder="Enter issue description"
                    className="mb-2"
                    rows={3}
                  />
                  <div className="flex space-x-2">
                    <Button 
                      onClick={createIssue} 
                      disabled={loading || !issueTitle.trim()}
                      className="flex-1"
                    >
                      {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Plus className="h-4 w-4 mr-2" />}
                      Create Issue
                    </Button>
                  </div>
                </div>
              )}

              {/* Issues List */}
              <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3">
                {issues.length > 0 ? (
                  issues.map((issue) => (
                    <div key={issue.id} className="mb-3">
                      <div className="flex items-start space-x-2">
                        <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium bg-gray-200">
                          {issue.user.login ? issue.user.login[0].toUpperCase() : '?'}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="font-medium">#{issue.number}</span>
                            <span className="text-sm text-gray-600">{issue.title}</span>
                            <Badge variant="outline" className={`${getIssueStateColor(issue.state)} text-white text-xs`}>
                              {issue.state}
                            </Badge>
                          </div>
                          <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                            <span>Created by {issue.user.login}</span>
                            <span>Created: {formatDateTime(issue.createdAt)}</span>
                            {issue.comments > 0 && (
                              <div className="flex items-center space-x-1">
                                <MessageSquare className="h-3 w-3" />
                                <span>{issue.comments}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No issues found. Select a repository to view issues."
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pulls" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <GitPullRequest className="h-5 w-5 mr-2" />
                GitHub Pull Requests
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Repository Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="prRepoSelect">Select Repository</Label>
                <Select value={selectedRepository} onValueChange={setSelectedRepository}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a repository" />
                  </SelectTrigger>
                  <SelectContent>
                    {repositories.map((repo) => (
                      <SelectItem key={repo.id} value={repo.fullName}>
                        <div className="flex items-center space-x-2">
                          {getRepositoryIcon(repo)}
                          <span>{repo.fullName}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Pull Requests List */}
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {pullRequests.length > 0 ? (
                  pullRequests.map((pr) => (
                    <div key={pr.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium">#{pr.number} {pr.title}</h4>
                        <div className="flex items-center space-x-2">
                          <Badge variant="outline" className={`${getPRStateColor(pr)} text-white text-xs`}>
                            {pr.merged ? 'Merged' : pr.state}
                          </Badge>
                          {pr.mergeableState && (
                            <Badge variant="outline" className={`${getPRMergeableColor(pr.mergeableState)} text-white text-xs`}>
                              {pr.mergeableState}
                            </Badge>
                          )}
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>From:</strong> {pr.head.label} <strong>To:</strong> {pr.base.label}
                      </div>
                      <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                        <span>Created by {pr.user.login}</span>
                        <span>Created: {formatDateTime(pr.createdAt)}</span>
                        <div className="flex items-center space-x-1">
                          <MessageSquare className="h-3 w-3" />
                          <span>{pr.comments}</span>
                        </div>
                        {pr.reviewComments > 0 && (
                          <div className="flex items-center space-x-1">
                            <MessageSquare className="h-3 w-3" />
                            <span>{pr.reviewComments}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No pull requests found. Select a repository to view pull requests."
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadPullRequests} 
                disabled={loading || !selectedRepository}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Pull Requests
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Users className="h-5 w-5 mr-2" />
                GitHub Users
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {users.length > 0 ? (
                  users.map((user) => (
                    <div key={user.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center">
                          {user.avatarUrl ? (
                            <img 
                              src={user.avatarUrl} 
                              alt={user.login}
                              className="w-10 h-10 rounded-full"
                            />
                          ) : (
                            <User className="w-5 h-5" />
                          )}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h4 className="font-medium">{user.login}</h4>
                            <Badge variant="outline" className="text-xs">
                              {user.type}
                            </Badge>
                          </div>
                          {user.name && (
                            <div className="text-sm text-muted-foreground">{user.name}</div>
                          )}
                          {user.company && (
                            <div className="text-sm text-muted-foreground">
                              <strong>Company:</strong> {user.company}
                            </div>
                          )}
                          {user.location && (
                            <div className="text-sm text-muted-foreground">
                              <strong>Location:</strong> {user.location}
                            </div>
                          )}
                          <div className="text-sm text-muted-foreground">
                            <strong>Public Repos:</strong> {user.publicRepos} | 
                            <strong>Followers:</strong> {user.followers}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No users found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadUsers} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Users
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="actions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <GitBranch className="h-5 w-5 mr-2" />
                GitHub Actions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <Settings className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-medium mb-2">Actions Module</h3>
                <p className="text-sm max-w-md mx-auto">
                  GitHub Actions management is under development. This will include:
                </p>
                <ul className="text-sm text-left mt-4 max-w-md mx-auto space-y-1">
                  <li>• Workflow run management</li>
                  <li>• Action history and logs</li>
                  <li>• Workflow configuration</li>
                  <li>• Scheduled and manual triggers</li>
                  <li>• Artifact management</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="workflows" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <GitMerge className="h-5 w-5 mr-2" />
                GitHub Workflows
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <Settings className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-medium mb-2">Workflows Module</h3>
                <p className="text-sm max-w-md mx-auto">
                  GitHub workflow management is under development. This will include:
                </p>
                <ul className="text-sm text-left mt-4 max-w-md mx-auto space-y-1">
                  <li>• Workflow file management</li>
                  <li>• Workflow run monitoring</li>
                  <li>• Branch protection rules</li>
                  <li>• Deployment pipeline management</li>
                  <li>• Integration with CI/CD services</li>
                </ul>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="oauth" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>OAuth Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-2">
                  <Label htmlFor="oauthUserId">User ID</Label>
                  <Input
                    id="oauthUserId"
                    value={userId}
                    onChange={(e) => setUserId(e.target.value)}
                    placeholder="Enter user ID for OAuth"
                  />
                </div>
                <Button 
                  onClick={initiateOAuth} 
                  disabled={!userId}
                  className="w-full"
                >
                  <Search className="h-4 w-4 mr-2" />
                  Connect to GitHub
                </Button>
                <p className="text-sm text-muted-foreground">
                  This will redirect you to GitHub OAuth to authorize ATOM access to your repositories.
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>OAuth Status</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {status?.components.oauth ? (
                  <>
                    <div className="flex items-center justify-between">
                      <span>Status</span>
                      <Badge variant="outline">
                        {status.components.oauth.status}
                      </Badge>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {status.components.oauth.message}
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    OAuth status not available
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}