/**
 * Notion Integration Page
 * Complete Notion integration with comprehensive document and database management
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
  Database, 
  FileText, 
  Search, 
  Settings, 
  CheckCircle, 
  AlertCircle, 
  RefreshCw,
  Plus,
  Edit,
  Trash2,
  Layers,
  Folder,
  User,
  Eye,
  Calendar
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

interface NotionDatabase {
  id: string;
  title: string;
  description: string;
  icon: string;
  type: string;
  parent_id: string;
  properties: any[];
  created_time: string;
  last_edited_time: string;
  url: string;
}

interface NotionPage {
  id: string;
  title: string;
  parent_id: string;
  database_id: string;
  created_time: string;
  last_edited_time: string;
  cover: string;
  icon: string;
  url: string;
  archived: boolean;
  properties: any;
}

interface NotionBlock {
  id: string;
  type: string;
  content: string;
  parent_id: string;
  created_time: string;
  last_edited_time: string;
  has_children: boolean;
  children: NotionBlock[];
}

interface NotionUser {
  id: string;
  name: string;
  email: string;
  avatar_url: string;
  type: string;
  person: any;
  bot: any;
}

interface NotionWorkspace {
  id: string;
  name: string;
  icon: string;
  type: string;
  owner: NotionUser;
  created_time: string;
}

interface NotionStatus {
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

export default function NotionIntegration() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState('demo-user');
  const [status, setStatus] = useState<NotionStatus | null>(null);
  const [userInfo, setUserInfo] = useState<NotionUser | null>(null);
  const [workspaces, setWorkspaces] = useState<NotionWorkspace[]>([]);
  const [databases, setDatabases] = useState<NotionDatabase[]>([]);
  const [pages, setPages] = useState<NotionPage[]>([]);
  const [blocks, setBlocks] = useState<NotionBlock[]>([]);
  const [selectedDatabase, setSelectedDatabase] = useState('');
  const [selectedPage, setSelectedPage] = useState('');
  const [pageTitle, setPageTitle] = useState('');
  const [pageContent, setPageContent] = useState('');
  const [databaseTitle, setDatabaseTitle] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('overview');

  // API base URL
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:5058';
  const NOTION_ENHANCED_URL = `${API_BASE_URL}/api/integrations/notion`;
  const NOTION_OAUTH_URL = `${API_BASE_URL}/api/auth/notion`;

  // Load initial data
  useEffect(() => {
    loadStatus();
    if (activeTab === 'workspaces') {
      loadWorkspaces();
    } else if (activeTab === 'databases') {
      loadDatabases();
    } else if (activeTab === 'pages') {
      loadPages();
    } else if (activeTab === 'blocks') {
      loadBlocks();
    }
  }, [activeTab]);

  const loadStatus = async () => {
    try {
      const response = await fetch(`${NOTION_ENHANCED_URL}/health`);
      const data = await response.json();
      setStatus(data);
    } catch (error) {
      console.error('Failed to load status:', error);
      setStatus({
        service: 'notion_enhanced',
        status: 'error',
        timestamp: new Date().toISOString(),
        components: {}
      });
    }
  };

  const loadUserInfo = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${NOTION_ENHANCED_URL}/users/profile`, {
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
          description: `Successfully loaded profile for ${data.data.user.name}`,
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
        description: "Could not connect to Notion service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadWorkspaces = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${NOTION_ENHANCED_URL}/workspaces/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 50
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setWorkspaces(data.data.workspaces);
        toast({
          title: "Workspaces loaded",
          description: `Loaded ${data.data.workspaces.length} workspaces`,
        });
      } else {
        toast({
          title: "Failed to load workspaces",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load workspaces:', error);
      toast({
        title: "Error loading workspaces",
        description: "Could not connect to Notion service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadDatabases = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${NOTION_ENHANCED_URL}/databases/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setDatabases(data.data.databases);
        toast({
          title: "Databases loaded",
          description: `Loaded ${data.data.databases.length} databases`,
        });
      } else {
        toast({
          title: "Failed to load databases",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load databases:', error);
      toast({
        title: "Error loading databases",
        description: "Could not connect to Notion service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadPages = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${NOTION_ENHANCED_URL}/pages/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          query: searchQuery || '',
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setPages(data.data.pages);
        toast({
          title: "Pages loaded",
          description: `Loaded ${data.data.pages.length} pages`,
        });
      } else {
        toast({
          title: "Failed to load pages",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load pages:', error);
      toast({
        title: "Error loading pages",
        description: "Could not connect to Notion service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const loadBlocks = async () => {
    if (!selectedPage) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${NOTION_ENHANCED_URL}/blocks/list`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          page_id: selectedPage,
          limit: 100
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setBlocks(data.data.blocks);
        toast({
          title: "Blocks loaded",
          description: `Loaded ${data.data.blocks.length} blocks from page ${selectedPage}`,
        });
      } else {
        toast({
          title: "Failed to load blocks",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to load blocks:', error);
      toast({
        title: "Error loading blocks",
        description: "Could not connect to Notion service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const createPage = async () => {
    if (!pageTitle.trim() || !selectedDatabase) return;
    
    setLoading(true);
    try {
      const response = await fetch(`${NOTION_ENHANCED_URL}/pages/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          database_id: selectedDatabase,
          title: pageTitle.trim(),
          properties: {
            'Name': {
              'title': [
                {
                  'text': pageTitle.trim()
                }
              ]
            }
          }
        })
      });
      
      const data = await response.json();
      
      if (data.ok) {
        setPageTitle('');
        toast({
          title: "Page created",
          description: "Page created successfully",
        });
        // Reload pages
        setTimeout(() => loadPages(), 1000);
      } else {
        toast({
          title: "Failed to create page",
          description: data.error || "Unknown error",
          variant: "destructive",
        });
      }
    } catch (error) {
      console.error('Failed to create page:', error);
      toast({
        title: "Error creating page",
        description: "Could not connect to Notion service",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  const initiateOAuth = async () => {
    try {
      const response = await fetch(`${NOTION_OAUTH_URL}/authorize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
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

  const getDatabaseIcon = (database: NotionDatabase) => {
    switch (database.type) {
      case 'table': return <Database className="h-4 w-4 text-blue-500" />;
      case 'board': return <Layers className="h-4 w-4 text-green-500" />;
      case 'list': return <FileText className="h-4 w-4 text-purple-500" />;
      case 'gallery': return <Eye className="h-4 w-4 text-orange-500" />;
      case 'calendar': return <Calendar className="h-4 w-4 text-red-500" />;
      case 'timeline': return <Clock className="h-4 w-4 text-yellow-500" />;
      default: return <Database className="h-4 w-4 text-gray-500" />;
    }
  };

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Notion Integration</h1>
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
            Notion integration is {status.status}. 
            {status.components.configuration?.status !== 'configured' && 
              " OAuth configuration is incomplete. Please check environment variables."}
          </AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-6">
          <TabsTrigger value="overview" className="flex items-center">
            <Settings className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="workspaces" className="flex items-center">
            <Folder className="h-4 w-4 mr-2" />
            Workspaces
          </TabsTrigger>
          <TabsTrigger value="databases" className="flex items-center">
            <Database className="h-4 w-4 mr-2" />
            Databases
          </TabsTrigger>
          <TabsTrigger value="pages" className="flex items-center">
            <FileText className="h-4 w-4 mr-2" />
            Pages
          </TabsTrigger>
          <TabsTrigger value="blocks" className="flex items-center">
            <Layers className="h-4 w-4 mr-2" />
            Blocks
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
                      {userInfo.avatar_url && (
                        <img 
                          src={userInfo.avatar_url} 
                          alt={userInfo.name}
                          className="w-12 h-12 rounded-full"
                        />
                      )}
                      <div>
                        <div className="font-medium">{userInfo.name}</div>
                        <div className="text-sm text-muted-foreground">{userInfo.email}</div>
                      </div>
                    </div>
                    <div>
                      <span className="font-medium">Type:</span> {userInfo.type}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="workspaces" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Folder className="h-5 w-5 mr-2" />
                Notion Workspaces
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {workspaces.length > 0 ? (
                  workspaces.map((workspace) => (
                    <div key={workspace.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center space-x-3">
                        {workspace.icon && (
                          <img 
                            src={workspace.icon} 
                            alt={workspace.name}
                            className="w-8 h-8 rounded"
                          />
                        )}
                        <div>
                          <h4 className="font-medium">{workspace.name}</h4>
                          <div className="text-sm text-muted-foreground">{workspace.type}</div>
                        </div>
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>ID:</strong> {workspace.id}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Created:</strong> {formatDateTime(workspace.created_time)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No workspaces found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadWorkspaces} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Workspaces
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="databases" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Database className="h-5 w-5 mr-2" />
                Notion Databases
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {databases.length > 0 ? (
                  databases.map((database) => (
                    <div key={database.id} className="p-3 border rounded-lg space-y-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {getDatabaseIcon(database)}
                          <h4 className="font-medium">{database.title}</h4>
                        </div>
                        <Badge variant="outline" className="text-xs">
                          {database.type}
                        </Badge>
                      </div>
                      {database.description && (
                        <div className="text-sm text-muted-foreground">
                          {database.description}
                        </div>
                      )}
                      <div className="text-sm text-muted-foreground">
                        <strong>ID:</strong> {database.id}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Last Edited:</strong> {formatDateTime(database.last_edited_time)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No databases found"
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadDatabases} 
                disabled={loading}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Databases
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="pages" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <FileText className="h-5 w-5 mr-2" />
                Notion Pages
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Search */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="searchQuery">Search Pages</Label>
                <div className="flex space-x-2">
                  <Input
                    id="searchQuery"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search pages..."
                    className="flex-1"
                  />
                  <Button 
                    onClick={loadPages} 
                    disabled={loading}
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Page Creation */}
              <div className="space-y-2 mb-4 border rounded-lg p-3">
                <Label htmlFor="pageDatabase">Database</Label>
                <Select value={selectedDatabase} onValueChange={setSelectedDatabase}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a database" />
                  </SelectTrigger>
                  <SelectContent>
                    {databases.map((database) => (
                      <SelectItem key={database.id} value={database.id}>
                        <div className="flex items-center space-x-2">
                          {getDatabaseIcon(database)}
                          <span>{database.title}</span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Label htmlFor="pageTitle">Page Title</Label>
                <div className="flex space-x-2">
                  <Input
                    id="pageTitle"
                    value={pageTitle}
                    onChange={(e) => setPageTitle(e.target.value)}
                    placeholder="Enter page title"
                    className="flex-1"
                  />
                  <Button 
                    onClick={createPage} 
                    disabled={loading || !pageTitle.trim() || !selectedDatabase}
                  >
                    {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                  </Button>
                </div>
              </div>

              {/* Pages List */}
              <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3">
                {pages.length > 0 ? (
                  pages.map((page) => (
                    <div key={page.id} className="mb-3 p-2 border rounded">
                      <div className="flex items-center justify-between">
                        <h4 className="font-medium">{page.title}</h4>
                        {page.archived && <Badge variant="destructive" className="text-xs">Archived</Badge>}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Database:</strong> {page.database_id}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        <strong>Last Edited:</strong> {formatDateTime(page.last_edited_time)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No pages found. Try searching or create a new page."
                    )}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="blocks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Layers className="h-5 w-5 mr-2" />
                Notion Blocks
              </CardTitle>
            </CardHeader>
            <CardContent>
              {/* Page Selection */}
              <div className="space-y-2 mb-4">
                <Label htmlFor="blockPage">Select Page</Label>
                <Select value={selectedPage} onValueChange={setSelectedPage}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a page" />
                  </SelectTrigger>
                  <SelectContent>
                    {pages.map((page) => (
                      <SelectItem key={page.id} value={page.id}>
                        <span>{page.title}</span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {/* Blocks List */}
              <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-3">
                {blocks.length > 0 ? (
                  blocks.map((block) => (
                    <div key={block.id} className="mb-3 p-2 border rounded">
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline" className="text-xs">
                          {block.type}
                        </Badge>
                        {block.has_children && <Layers className="h-3 w-3 text-blue-500" />}
                      </div>
                      <div className="text-sm">
                        {block.content || 'Empty block'}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        <strong>Last Edited:</strong> {formatDateTime(block.last_edited_time)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-8 text-muted-foreground">
                    {loading ? (
                      <Loader2 className="h-6 w-6 animate-spin mx-auto" />
                    ) : (
                      "No blocks found. Select a page to view blocks."
                    )}
                  </div>
                )}
              </div>
              <Button 
                onClick={loadBlocks} 
                disabled={loading || !selectedPage}
                className="w-full mt-4"
              >
                {loading ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Refresh Blocks
              </Button>
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
                  Connect to Notion
                </Button>
                <p className="text-sm text-muted-foreground">
                  This will redirect you to Notion OAuth to authorize ATOM access to your workspace.
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