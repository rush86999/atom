import React, { useState, useEffect } from 'react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Loader2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Plus,
  Settings,
  Terminal,
  Database,
  Search,
  Folder,
  GitBranch,
  Brain,
  Globe,
  MessageSquare,
  Github,
  Cloud,
  Server,
  Trash2,
  Play,
  Square,
  Eye,
  Code,
  Package,
  HardDrive,
  Wifi,
  Lock
} from "lucide-react";

interface MCPServer {
  id: string;
  name: string;
  command: string;
  args: string[];
  description: string;
  category: string;
  icon: string;
  status: 'available' | 'connected' | 'unavailable' | 'mcp_unavailable' | 'configured';
  type: 'builtin' | 'custom';
  tools_count?: number;
  tools?: MCPTool[];
}

interface MCPTool {
  name: string;
  description: string;
  schema: any;
}

interface MCPConnection {
  server_id: string;
  connected_at: string;
  tools_count: number;
  config: any;
}

interface MCPCategory {
  name: string;
  count: number;
  servers: MCPServer[];
}

const MCPIntegration: React.FC = () => {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [categories, setCategories] = useState<Record<string, MCPCategory>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingConnections, setIsLoadingConnections] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  // Custom server form state
  const [customServerDialogOpen, setCustomServerDialogOpen] = useState(false);
  const [customServerForm, setCustomServerForm] = useState({
    server_id: '',
    command: '',
    args: '',
    description: '',
    category: 'custom',
    icon: '⚙️'
  });

  // Tool execution dialog state
  const [toolExecutionDialogOpen, setToolExecutionDialogOpen] = useState(false);
  const [selectedServer, setSelectedServer] = useState<MCPServer | null>(null);
  const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null);
  const [toolArguments, setToolArguments] = useState<string>('{}');
  const [isExecutingTool, setIsExecutingTool] = useState(false);
  const [toolExecutionResult, setToolExecutionResult] = useState<any>(null);

  // Fetch available servers
  const fetchServers = async () => {
    try {
      setIsLoading(true);
      setError(null);

      const response = await fetch('/api/mcp/servers');
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Failed to fetch MCP servers');
      }

      setServers(data.servers || []);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch MCP servers';
      setError(errorMessage);
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch active connections
  const fetchConnections = async () => {
    try {
      setIsLoadingConnections(true);

      const response = await fetch('/api/mcp/connections');
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Failed to fetch connections');
      }

      setConnections(data.connections || []);
    } catch (err) {
      console.error('Error fetching connections:', err);
    } finally {
      setIsLoadingConnections(false);
    }
  };

  // Fetch categories
  const fetchCategories = async () => {
    try {
      const response = await fetch('/api/mcp/categories');
      const data = await response.json();

      if (response.ok && data.categories) {
        setCategories(data.categories);
      }
    } catch (err) {
      console.error('Error fetching categories:', err);
    }
  };

  // Connect to server
  const connectToServer = async (serverId: string) => {
    try {
      const response = await fetch('/api/mcp/servers/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ server_id: serverId }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Failed to connect to server');
      }

      toast({
        title: "Success",
        description: `Connected to ${serverId} server`,
      });

      // Refresh data
      await Promise.all([fetchServers(), fetchConnections()]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to connect to server';
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  // Disconnect from server
  const disconnectFromServer = async (serverId: string) => {
    try {
      const response = await fetch('/api/mcp/servers/disconnect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ server_id: serverId }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Failed to disconnect from server');
      }

      toast({
        title: "Success",
        description: `Disconnected from ${serverId} server`,
      });

      // Refresh data
      await Promise.all([fetchServers(), fetchConnections()]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to disconnect from server';
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  // Add custom server
  const addCustomServer = async () => {
    try {
      const argsArray = customServerForm.args.split(' ').filter(arg => arg.trim());

      const response = await fetch('/api/mcp/servers/custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...customServerForm,
          args: argsArray
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Failed to add custom server');
      }

      toast({
        title: "Success",
        description: `Added ${customServerForm.server_id} server`,
      });

      // Close dialog and reset form
      setCustomServerDialogOpen(false);
      setCustomServerForm({
        server_id: '',
        command: '',
        args: '',
        description: '',
        category: 'custom',
        icon: '⚙️'
      });

      // Refresh servers
      await fetchServers();
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to add custom server';
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  // Execute tool
  const executeTool = async () => {
    if (!selectedServer || !selectedTool) return;

    try {
      setIsExecutingTool(true);
      let parsedArgs = {};

      try {
        parsedArgs = JSON.parse(toolArguments);
      } catch (e) {
        throw new Error('Invalid JSON in arguments');
      }

      const response = await fetch(`/api/mcp/connections/${selectedServer.id}/tools/${selectedTool.name}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          server_id: selectedServer.id,
          tool_name: selectedTool.name,
          arguments: parsedArgs
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.message || 'Failed to execute tool');
      }

      setToolExecutionResult(data.execution);
      toast({
        title: "Success",
        description: `Executed ${selectedTool.name} successfully`,
      });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to execute tool';
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
      setToolExecutionResult({ error: errorMessage });
    } finally {
      setIsExecutingTool(false);
    }
  };

  // Get status icon
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'connected':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'available':
      case 'configured':
        return <CheckCircle className="h-4 w-4 text-blue-500" />;
      case 'unavailable':
      case 'mcp_unavailable':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    }
  };

  // Get category icon
  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'storage':
        return <HardDrive className="h-4 w-4" />;
      case 'database':
        return <Database className="h-4 w-4" />;
      case 'search':
        return <Search className="h-4 w-4" />;
      case 'development':
        return <Code className="h-4 w-4" />;
      case 'memory':
        return <Brain className="h-4 w-4" />;
      case 'network':
        return <Wifi className="h-4 w-4" />;
      case 'communication':
        return <MessageSquare className="h-4 w-4" />;
      case 'infrastructure':
        return <Server className="h-4 w-4" />;
      default:
        return <Package className="h-4 w-4" />;
    }
  };

  // Load data on mount
  useEffect(() => {
    fetchServers();
    fetchConnections();
    fetchCategories();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Terminal className="h-6 w-6" />
            Model Context Protocol (MCP) Servers
          </h2>
          <p className="text-gray-600 mt-1">
            Connect to MCP servers to extend your agent's capabilities with specialized tools
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={() => fetchServers()} variant="outline" size="sm">
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
          <Dialog open={customServerDialogOpen} onOpenChange={setCustomServerDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4 mr-2" />
                Add Custom Server
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Custom MCP Server</DialogTitle>
                <DialogDescription>
                  Configure a custom MCP server to extend agent capabilities
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="server_id">Server ID</Label>
                  <Input
                    id="server_id"
                    value={customServerForm.server_id}
                    onChange={(e) => setCustomServerForm({ ...customServerForm, server_id: e.target.value })}
                    placeholder="e.g., my-custom-server"
                  />
                </div>
                <div>
                  <Label htmlFor="command">Command</Label>
                  <Input
                    id="command"
                    value={customServerForm.command}
                    onChange={(e) => setCustomServerForm({ ...customServerForm, command: e.target.value })}
                    placeholder="e.g., npx or python"
                  />
                </div>
                <div>
                  <Label htmlFor="args">Arguments (space-separated)</Label>
                  <Input
                    id="args"
                    value={customServerForm.args}
                    onChange={(e) => setCustomServerForm({ ...customServerForm, args: e.target.value })}
                    placeholder="e.g., @my/server-package --option value"
                  />
                </div>
                <div>
                  <Label htmlFor="description">Description</Label>
                  <Input
                    id="description"
                    value={customServerForm.description}
                    onChange={(e) => setCustomServerForm({ ...customServerForm, description: e.target.value })}
                    placeholder="Describe what this server does"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button onClick={() => setCustomServerDialogOpen(false)} variant="outline">
                  Cancel
                </Button>
                <Button onClick={addCustomServer}>
                  Add Server
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Available Servers</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{servers.length}</div>
            <p className="text-xs text-muted-foreground">Ready to connect</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Active Connections</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{connections.length}</div>
            <p className="text-xs text-muted-foreground">Currently connected</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Categories</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{Object.keys(categories).length}</div>
            <p className="text-xs text-muted-foreground">Server types</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="servers" className="w-full">
        <TabsList>
          <TabsTrigger value="servers">Servers</TabsTrigger>
          <TabsTrigger value="connections">Connections</TabsTrigger>
          <TabsTrigger value="categories">Categories</TabsTrigger>
        </TabsList>

        {/* Servers Tab */}
        <TabsContent value="servers" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Available MCP Servers</CardTitle>
              <CardDescription>
                Browse and connect to available MCP servers
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Server</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Tools</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {servers.map((server) => {
                    const isConnected = connections.some(c => c.server_id === server.id);
                    return (
                      <TableRow key={server.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{server.icon}</span>
                            <div>
                              <div className="font-medium">{server.name}</div>
                              <div className="text-sm text-gray-500">{server.description}</div>
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline" className="flex items-center gap-1 w-fit">
                            {getCategoryIcon(server.category)}
                            {server.category}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            {getStatusIcon(server.status)}
                            <span className="capitalize">{server.status.replace('_', ' ')}</span>
                          </div>
                        </TableCell>
                        <TableCell>
                          {server.tools_count !== undefined ? (
                            <Badge variant="secondary">{server.tools_count} tools</Badge>
                          ) : (
                            <span className="text-sm text-gray-500">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-2">
                            {isConnected ? (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => {
                                    setSelectedServer(server);
                                    setToolExecutionDialogOpen(true);
                                  }}
                                >
                                  <Play className="h-3 w-3 mr-1" />
                                  Tools
                                </Button>
                                <Button
                                  size="sm"
                                  variant="destructive"
                                  onClick={() => disconnectFromServer(server.id)}
                                >
                                  <Square className="h-3 w-3 mr-1" />
                                  Disconnect
                                </Button>
                              </>
                            ) : (
                              <Button
                                size="sm"
                                onClick={() => connectToServer(server.id)}
                                disabled={server.status === 'unavailable' || server.status === 'mcp_unavailable'}
                              >
                                <Plus className="h-3 w-3 mr-1" />
                                Connect
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Connections Tab */}
        <TabsContent value="connections" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Active Connections</CardTitle>
              <CardDescription>
                Currently connected MCP servers and their available tools
              </CardDescription>
            </CardHeader>
            <CardContent>
              {connections.length === 0 ? (
                <div className="text-center py-8">
                  <Terminal className="h-12 w-12 mx-auto text-gray-400 mb-4" />
                  <p className="text-gray-500">No active connections</p>
                  <p className="text-sm text-gray-400">Connect to MCP servers to see them here</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {connections.map((connection) => (
                    <Card key={connection.server_id} className="border-l-4 border-l-blue-500">
                      <CardHeader className="pb-3">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-lg">{connection.server_id}</CardTitle>
                          <div className="flex gap-2">
                            <Badge variant="outline">
                              {connection.tools_count} tools
                            </Badge>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => disconnectFromServer(connection.server_id)}
                            >
                              <Square className="h-3 w-3 mr-1" />
                              Disconnect
                            </Button>
                          </div>
                        </div>
                        <CardDescription>
                          Connected at {new Date(connection.connected_at).toLocaleString()}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="text-sm text-gray-600">
                          <strong>Command:</strong> {connection.config.command} {connection.config.args.join(' ')}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Categories Tab */}
        <TabsContent value="categories" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Server Categories</CardTitle>
              <CardDescription>
                Browse MCP servers by category
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(categories).map(([categoryKey, category]) => (
                  <Card key={categoryKey} className="cursor-pointer hover:shadow-md transition-shadow">
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2 text-lg">
                        {getCategoryIcon(categoryKey)}
                        {category.name}
                      </CardTitle>
                      <Badge variant="secondary" className="w-fit">
                        {category.count} servers
                      </Badge>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-2">
                        {category.servers.slice(0, 3).map((server) => (
                          <div key={server.id} className="flex items-center gap-2 text-sm">
                            <span>{server.icon}</span>
                            <span>{server.name}</span>
                            {getStatusIcon(server.status)}
                          </div>
                        ))}
                        {category.servers.length > 3 && (
                          <div className="text-xs text-gray-500">
                            +{category.servers.length - 3} more servers
                          </div>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Tool Execution Dialog */}
      <Dialog open={toolExecutionDialogOpen} onOpenChange={setToolExecutionDialogOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Execute Tool - {selectedServer?.name}</DialogTitle>
            <DialogDescription>
              Select and execute tools from the connected MCP server
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Tools List */}
            <div>
              <h4 className="font-medium mb-2">Available Tools</h4>
              <div className="space-y-2 max-h-64 overflow-y-auto border rounded-lg p-2">
                {selectedServer?.tools?.map((tool) => (
                  <div
                    key={tool.name}
                    className={`p-2 rounded cursor-pointer hover:bg-gray-100 ${selectedTool?.name === tool.name ? 'bg-blue-100' : ''}`}
                    onClick={() => {
                      setSelectedTool(tool);
                      setToolArguments('{}');
                    }}
                  >
                    <div className="font-medium text-sm">{tool.name}</div>
                    <div className="text-xs text-gray-500">{tool.description}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Tool Execution */}
            <div>
              <h4 className="font-medium mb-2">Execute {selectedTool?.name}</h4>
              <div className="space-y-4">
                <div>
                  <Label htmlFor="arguments">Arguments (JSON)</Label>
                  <textarea
                    id="arguments"
                    className="w-full h-32 p-2 border rounded-lg font-mono text-sm"
                    value={toolArguments}
                    onChange={(e) => setToolArguments(e.target.value)}
                    placeholder="{}"
                  />
                </div>
                <Button
                  onClick={executeTool}
                  disabled={!selectedTool || isExecutingTool}
                  className="w-full"
                >
                  {isExecutingTool ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      Executing...
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-2" />
                      Execute Tool
                    </>
                  )}
                </Button>

                {/* Result */}
                {toolExecutionResult && (
                  <div className="border rounded-lg p-4">
                    <h5 className="font-medium mb-2">Result</h5>
                    <pre className="text-xs bg-gray-100 p-2 rounded overflow-x-auto">
                      {JSON.stringify(toolExecutionResult, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setToolExecutionDialogOpen(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MCPIntegration;