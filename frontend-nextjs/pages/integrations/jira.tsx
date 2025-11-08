/**
 * Jira Integration Page
 * Complete Jira integration with comprehensive project management and issue tracking features
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
  FolderOpen, 
  CheckSquare, 
  Users, 
  Calendar, 
  Search, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Bug,
  Star,
  Clock,
  User,
  MessageSquare,
  Tag,
  Flag,
  ChevronRight,
  Filter
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface JiraProject {
  id: string;
  key: string;
  name: string;
  description: string;
  projectType: string;
  lead: {
    accountId: string;
    displayName: string;
  };
  url: string;
  avatarUrls: {
    '48x48': string;
    '24x24': string;
  };
  projectCategory: {
    id: string;
    name: string;
    description: string;
  };
  style: string;
  isPrivate: boolean;
  issueTypes: Array<{
    id: string;
    name: string;
    iconUrl: string;
    description: string;
  }>;
  components: Array<{
    id: string;
    name: string;
    description: string;
  }>;
}

interface JiraIssue {
  id: string;
  key: string;
  summary: string;
  description: string;
  issueType: {
    id: string;
    name: string;
    iconUrl: string;
    description: string;
  };
  status: {
    id: string;
    name: string;
    statusCategory: {
      id: number;
      key: string;
      colorName: string;
    };
  };
  priority: {
    id: string;
    name: string;
    statusColor: string;
  };
  assignee: {
    accountId: string;
    displayName: string;
    emailAddress?: string;
  };
  reporter: {
    accountId: string;
    displayName: string;
    emailAddress?: string;
  };
  project: {
    id: string;
    key: string;
    name: string;
  };
  created: string;
  updated: string;
  dueDate: string;
  resolutionDate: string;
  components: Array<{
    id: string;
    name: string;
  }>;
  labels: string[];
  fixVersions: Array<{
    id: string;
    name: string;
  }>;
  versions: Array<{
    id: string;
    name: string;
  }>;
  environment: string;
  timeEstimate: number;
  timeSpent: number;
  watches: number;
  comments: any[];
}

interface JiraUser {
  accountId: string;
  displayName: string;
  emailAddress?: string;
  active: boolean;
  timeZone: string;
  locale: string;
  avatarUrls: {
    '48x48': string;
    '24x24': string;
  };
}

interface JiraSprint {
  id: number;
  name: string;
  state: string;
  startDate: string;
  endDate: string;
  completeDate: string;
  originBoardId: number;
  goal: string;
}

interface JiraStatus {
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

export default function JiraIntegration() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('demo-user');
  const [status, setStatus] = useState<JiraStatus | null>(null);
  const [userInfo, setUserInfo] = useState<JiraUser | null>(null);
  const [projects, setProjects] = useState<JiraProject[]>([]);
  const [issues, setIssues] = useState<JiraIssue[]>([]);
  const [users, setUsers] = useState<JiraUser[]>([]);
  const [sprints, setSprints] = useState<JiraSprint[]>([]);
  const [selectedProject, setSelectedProject] = useState('');
  const [issueTitle, setIssueTitle] = useState('');
  const [issueDescription, setIssueDescription] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
  const JIRA_ENHANCED_URL = `${API_BASE_URL}/api/integrations/jira`;
  const JIRA_OAUTH_URL = `${API_BASE_URL}/api/integrations/jira/auth`;

  // Load initial data
  useEffect(() => {
    loadStatus();
    if (activeTab === 'projects') {
      loadProjects();
    } else if (activeTab === 'issues') {
      loadIssues();
    } else if (activeTab === 'users') {
      loadUsers();
    } else if (activeTab === 'sprints') {
      loadSprints();
    }
  }, [activeTab]);

  const loadStatus = async () => {
    try {
      const response = await fetch(`${JIRA_ENHANCED_URL}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
      setStatus({
        service: 'jira_enhanced',
        status: 'error',
        timestamp: new Date().toISOString(),
        components: {}
      });
    }
  };

  const loadUserInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${JIRA_ENHANCED_URL}/users/profile`, {
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
          description: `Successfully loaded profile for ${data.data.user.displayName}`,
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
        description: "Could not connect to Jira service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadProjects = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${JIRA_ENHANCED_URL}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setProjects(data.data.projects);
        toast({
          title: "Projects loaded",
          description: `Loaded ${data.data.projects.length} projects`,
        });
      } else {
        toast({
          title: "Failed to load projects",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load projects:', error);
      toast({
        title: "Error loading projects",
        description: "Could not connect to Jira service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadIssues = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${JIRA_ENHANCED_URL}/issues`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          project_key: selectedProject,
          jql: searchQuery || '',
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setIssues(data.data.issues);
        toast({
          title: "Issues loaded",
          description: `Loaded ${data.data.issues.length} issues`,
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
        description: "Could not connect to Jira service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${JIRA_ENHANCED_URL}/users`, {
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
        description: "Could not connect to Jira service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadSprints = async () => {
    if (!selectedProject) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${JIRA_ENHANCED_URL}/sprints`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          project_key: selectedProject,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setSprints(data.data.sprints);
        toast({
          title: "Sprints loaded",
          description: `Loaded ${data.data.sprints.length} sprints from ${selectedProject}`,
        });
      } else {
        toast({
          title: "Failed to load sprints",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load sprints:', error);
      toast({
        title: "Error loading sprints",
        description: "Could not connect to Jira service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const createIssue = async () => {
    if (!issueTitle.trim() || !selectedProject) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${JIRA_ENHANCED_URL}/issues`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          project_key: selectedProject,
          summary: issueTitle.trim(),
          description: issueDescription.trim(),
          issue_type: 'Task'
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setIssueTitle('');
        setIssueDescription('');
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
        description: "Could not connect to Jira service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const initiateOAuth = async () => {
    try {
      const response = await fetch(`${JIRA_OAUTH_URL}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        // Redirect to OAuth URL
        window.location.href = `${JIRA_OAUTH_URL}/start`;
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

  const getPriorityColor = (priority: JiraIssue['priority']) => {
    switch (priority?.name?.toLowerCase()) {
      case 'highest': return 'bg-red-500';
      case 'high': return 'bg-orange-500';
      case 'medium': return 'bg-yellow-500';
      case 'low': return 'bg-green-500';
      case 'lowest': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusCategoryColor = (statusCategory: JiraIssue['status']['statusCategory']) => {
    switch (statusCategory?.key) {
      case 'done': return 'bg-green-500';
      case 'in_progress': return 'bg-blue-500';
      case 'to_do': return 'bg-gray-500';
      case 'undefined': return 'bg-gray-500';
      default: return 'bg-gray-500';
    }
  };

  const getIssueTypeIcon = (issueType: JiraIssue['issueType']) => {
    const iconUrl = issueType?.iconUrl;
    if (iconUrl) {
      return <img src={iconUrl} alt={issueType?.name} className="h-4 w-4" />;
    }
    return <Bug className="h-4 w-4 text-purple-500" />;
  };

  const getProjectIcon = (project: JiraProject) => {
    const avatarUrl = project.avatarUrls?.['48x48'];
    if (avatarUrl) {
      return <img src={avatarUrl} alt={project.name} className="h-8 w-8 rounded" />;
    }
    return <FolderOpen className="h-8 w-8 text-blue-500" />;
  };

  const getSprintStateColor = (state: string) => {
    switch (state) {
      case 'active': return 'bg-green-500';
      case 'closed': return 'bg-gray-500';
      case 'future': return 'bg-blue-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Jira Integration</h1>
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
            Jira integration is {status.status}. 
            {status.components.configuration?.status !== 'configured' && 
              " OAuth configuration is incomplete. Please check environment variables."}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-7">
          <TabsTrigger value="overview" className="flex items-center">
            <Settings className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="projects" className="flex items-center">
            <FolderOpen className="h-4 w-4 mr-2" />
            Projects
          </TabsTrigger>
          <TabsTrigger value="issues" className="flex items-center">
            <CheckSquare className="h-4 w-4 mr-2" />
            Issues
          </TabsTrigger>
          <TabsTrigger value="users" className="flex items-center">
            <Users className="h-4 w-4 mr-2" />
            Users
          </TabsTrigger>
          <TabsTrigger value="sprints" className="flex items-center">
            <Calendar className="h-4 w-4 mr-2" />
            Sprints
          </TabsTrigger>
          <TabsTrigger value="workflows" className="flex items-center">
            <Settings className="h-4 w-4 mr-2" />
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
                      {userInfo.avatarUrls?.['48x48'] && (
                        <img 
                          src={userInfo.avatarUrls['48x48']} 
                          alt={userInfo.displayName}
                          className="w-12 h-12 rounded-full"
                        />
                      )}
                      <div>
                        <div className="font-medium">{userInfo.displayName}</div>
                        <div className="text-sm text-muted-foreground">{userInfo.emailAddress}</div>
                      </div>
                    </div>
                    <div>
                      <span className="font-medium">Status:</span> {userInfo.active ? 'Active' : 'Inactive'}
                    </div>
                    <div>
                      <span className="font-medium">Time Zone:</span> {userInfo.timeZone}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="projects" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <FolderOpen className="h-5 w-5 mr-2" />
                Jira Projects
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {projects.length > 0 ? (
                  projects.map((project) => (
                    <div key={project.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {getProjectIcon(project)}
                          <h4 className="font-medium">{project.name}</h4>
                        </div>
                        <div className="flex items-center space-x-2">
                          {project.isPrivate && <Badge variant="outline" className="text-xs">Private</Badge>}
                          <Badge variant="outline" className="text-xs">{project.projectType}</Badge>
                        </div>
                      </div>
                      {project.description && (
                        <div className="text-sm text-muted-foreground">
                          {project.description}
                        </div>
                      )}
                      <div className="text-sm text-muted-foreground">
                        <strong>Key:</strong> {project.key}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Lead:</strong> {project.lead?.displayName}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No projects found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadProjects} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Projects
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="issues" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <CheckSquare className="h-5 w-5 mr-2" />
                Jira Issues
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Project Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="projectSelect">Select Project</Label>
                <Select value={selectedProject} onValueChange={setSelectedProject}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a project" />
                  </SelectTrigger>
                  <SelectContent>
                    {projects.map((project) => (
                      <SelectItem key={project.id} value={project.key}>
                        <div className="flex items-center space-x-2">
                          {getProjectIcon(project)}
                          <span>{project.name} ({project.key})</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Search */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="searchQuery">Search Issues (JQL)</Label>
                <div className="flex space-x-2">
                  <Input
                    id="searchQuery"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="status != 'Closed' ORDER BY created DESC"
                    className="flex-1"
                  />
                  <Button 
                    onClick={loadIssues} 
                    disabled={loading || !selectedProject}
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Issue Creation */}
              {selectedProject && (
                <div className="space-y-2 mb-4 border rounded-lg p-3">
                  <Label htmlFor="issueTitle">Issue Title</Label>
                  <Input
                    id="issueTitle"
                    value={issueTitle}
                    onChange={(e) => setIssueTitle(e.target.value)}
                    placeholder="Enter issue title"
                    className="mb-2"
                  />
                  <Label htmlFor="issueDescription">Description</Label>
                  <Textarea
                    id="issueDescription"
                    value={issueDescription}
                    onChange={(e) => setIssueDescription(e.target.value)}
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
                        {getIssueTypeIcon(issue.issueType)}
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-1">
                            <span className="font-medium">{issue.key}</span>
                            <span className="text-sm text-gray-600">{issue.summary}</span>
                            <div className="flex items-center space-x-1">
                              <Badge variant="outline" className={`${getPriorityColor(issue.priority)} text-white text-xs`}>
                                {issue.priority?.name}
                              </Badge>
                              <Badge variant="outline" className={`${getStatusCategoryColor(issue.status.statusCategory)} text-white text-xs`}>
                                {issue.status?.name}
                              </Badge>
                            </div>
                          </div>
                          <div className="flex items-center space-x-4 text-xs text-muted-foreground">
                            <span>Assignee: {issue.assignee?.displayName || 'Unassigned'}</span>
                            <span>Created: {formatDateTime(issue.created)}</span>
                            {issue.dueDate && <span>Due: {formatDateTime(issue.dueDate)}</span>}
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
                      "No issues found. Select a project and search or create a new issue."
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Users className="h-5 w-5 mr-2" />
                Jira Users
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {users.length > 0 ? (
                  users.map((user) => (
                    <div key={user.accountId} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center space-x-3">
                        <div className="w-10 h-10 rounded-full bg-gray-300 flex items-center justify-center">
                          {user.avatarUrls?.['48x48'] ? (
                            <img 
                              src={user.avatarUrls['48x48']} 
                              alt={user.displayName}
                              className="w-10 h-10 rounded-full"
                            />
                          ) : (
                            <User className="w-5 h-5" />
                          )}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <h4 className="font-medium">{user.displayName}</h4>
                            <Badge variant="outline" className="text-xs">
                              {user.active ? 'Active' : 'Inactive'}
                            </Badge>
                          </div>
                          {user.emailAddress && (
                            <div className="text-sm text-muted-foreground">{user.emailAddress}</div>
                          )}
                          <div className="text-sm text-muted-foreground">
                            <strong>Time Zone:</strong> {user.timeZone}
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

        <TabsContent value="sprints" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Calendar className="h-5 w-5 mr-2" />
                Jira Sprints
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Project Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="sprintProjectSelect">Select Project</Label>
                <Select value={selectedProject} onValueChange={setSelectedProject}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a project" />
                  </SelectTrigger>
                  <SelectContent>
                    {projects.map((project) => (
                      <SelectItem key={project.id} value={project.key}>
                        <div className="flex items-center space-x-2">
                          {getProjectIcon(project)}
                          <span>{project.name} ({project.key})</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Sprints List */}
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {sprints.length > 0 ? (
                  sprints.map((sprint) => (
                    <div key={sprint.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium">{sprint.name}</h4>
                        <div className="flex items-center space-x-2">
                          <Badge variant="outline" className={`${getSprintStateColor(sprint.state)} text-white text-xs`}>
                            {sprint.state}
                          </Badge>
                          <span className="text-sm text-muted-foreground">#{sprint.id}</span>
                        </div>
                      </div>
                      {sprint.goal && (
                        <div className="text-sm text-muted-foreground">
                          <strong>Goal:</strong> {sprint.goal}
                        </div>
                      )}
                      <div className="text-sm text-muted-foreground">
                        <strong>Duration:</strong> {formatDateTime(sprint.startDate)} - {formatDateTime(sprint.endDate)}
                      </div>
                      {sprint.completeDate && (
                        <div className="text-sm text-muted-foreground">
                          <strong>Completed:</strong> {formatDateTime(sprint.completeDate)}
                        </div>
                      )}
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No sprints found. Select a project to view sprints."
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadSprints} 
                disabled={loading || !selectedProject}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Sprints
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="workflows" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Settings className="h-5 w-5 mr-2" />
                Jira Workflows
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-center py-8 text-muted-foreground">
                <MessageSquare className="h-12 w-12 mx-auto mb-4 text-gray-400" />
                <h3 className="text-lg font-medium mb-2">Workflows Module</h3>
                <p className="text-sm max-w-md mx-auto">
                  Jira workflow management is under development. This will include:
                </p>
                <ul className="text-sm text-left mt-4 max-w-md mx-auto space-y-1">
                  <li>• Custom workflow creation and editing</li>
                  <li>• Status transitions and rules</li>
                  <li>• Issue type workflows</li>
                  <li>• Approval processes</li>
                  <li>• Workflow visualization</li>
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
                  Connect to Jira
                </Button>
                <p className="text-sm text-muted-foreground">
                  This will redirect you to Atlassian OAuth to authorize ATOM access to your Jira workspace.
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