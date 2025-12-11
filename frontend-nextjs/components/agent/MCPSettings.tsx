import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import {
  Terminal,
  Server,
  Settings,
  Play,
  Square,
  RefreshCw,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  Save,
  RotateCcw
} from "lucide-react";

interface MCPServer {
  id: string;
  name: string;
  description: string;
  category: string;
  status: 'connected' | 'available' | 'unavailable';
  tools_count?: number;
}

interface AgentMCPConfig {
  enabled: boolean;
  auto_connect_servers: string[];
  default_servers: string[];
  tool_permissions: {
    [server_id: string]: {
      allowed_tools: string[];
      blocked_tools: string[];
    };
  };
  execution_settings: {
    timeout_seconds: number;
    max_concurrent_tools: number;
    retry_attempts: number;
  };
}

const MCPSettings: React.FC = () => {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [activeConnections, setActiveConnections] = useState<string[]>([]);
  const [config, setConfig] = useState<AgentMCPConfig>({
    enabled: true,
    auto_connect_servers: [],
    default_servers: [],
    tool_permissions: {},
    execution_settings: {
      timeout_seconds: 30,
      max_concurrent_tools: 5,
      retry_attempts: 3
    }
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const { toast } = useToast();

  // Fetch available servers
  const fetchServers = async () => {
    try {
      const response = await fetch('/api/mcp/servers');
      const data = await response.json();

      if (response.ok) {
        setServers(data.servers || []);
      }
    } catch (error) {
      console.error('Failed to fetch servers:', error);
    }
  };

  // Fetch active connections
  const fetchConnections = async () => {
    try {
      const response = await fetch('/api/mcp/connections');
      const data = await response.json();

      if (response.ok) {
        const connections = data.connections || [];
        setActiveConnections(connections.map((c: any) => c.server_id));
      }
    } catch (error) {
      console.error('Failed to fetch connections:', error);
    }
  };

  // Load agent configuration
  const loadConfig = async () => {
    try {
      const response = await fetch('/api/agent/mcp-config');
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      }
    } catch (error) {
      console.error('Failed to load config:', error);
    }
  };

  // Save configuration
  const saveConfig = async () => {
    try {
      setIsSaving(true);
      const response = await fetch('/api/agent/mcp-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });

      if (response.ok) {
        toast({
          title: "Settings Saved",
          description: "MCP configuration has been updated successfully.",
        });
      } else {
        throw new Error('Failed to save configuration');
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to save MCP configuration.",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  };

  // Connect to server
  const connectServer = async (serverId: string) => {
    try {
      const response = await fetch('/api/mcp/servers/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ server_id: serverId }),
      });

      if (response.ok) {
        setActiveConnections(prev => [...prev, serverId]);
        toast({
          title: "Connected",
          description: `Connected to ${serverId} server.`,
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to connect to server.",
        variant: "destructive",
      });
    }
  };

  // Disconnect from server
  const disconnectServer = async (serverId: string) => {
    try {
      const response = await fetch('/api/mcp/servers/disconnect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ server_id: serverId }),
      });

      if (response.ok) {
        setActiveConnections(prev => prev.filter(id => id !== serverId));
        toast({
          title: "Disconnected",
          description: `Disconnected from ${serverId} server.`,
        });
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to disconnect from server.",
        variant: "destructive",
      });
    }
  };

  useEffect(() => {
    const loadData = async () => {
      await Promise.all([
        fetchServers(),
        fetchConnections(),
        loadConfig()
      ]);
      setIsLoading(false);
    };

    loadData();
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold flex items-center gap-2">
            <Terminal className="h-6 w-6" />
            MCP Agent Settings
          </h2>
          <p className="text-gray-600 mt-1">
            Configure Model Context Protocol settings for the main agent
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={saveConfig} disabled={isSaving}>
            {isSaving ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save className="h-4 w-4 mr-2" />
                Save Settings
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Main Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            General Configuration
          </CardTitle>
          <CardDescription>
            Basic MCP settings for the main agent
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <Label>Enable MCP for Agent</Label>
              <p className="text-sm text-gray-500">
                Allow the main agent to use MCP server tools
              </p>
            </div>
            <Switch
              checked={config.enabled}
              onCheckedChange={(enabled) => setConfig(prev => ({ ...prev, enabled }))}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <Label htmlFor="timeout">Tool Timeout (seconds)</Label>
              <Input
                id="timeout"
                type="number"
                value={config.execution_settings.timeout_seconds}
                onChange={(e) => setConfig(prev => ({
                  ...prev,
                  execution_settings: {
                    ...prev.execution_settings,
                    timeout_seconds: parseInt(e.target.value) || 30
                  }
                }))}
              />
            </div>
            <div>
              <Label htmlFor="concurrent">Max Concurrent Tools</Label>
              <Input
                id="concurrent"
                type="number"
                value={config.execution_settings.max_concurrent_tools}
                onChange={(e) => setConfig(prev => ({
                  ...prev,
                  execution_settings: {
                    ...prev.execution_settings,
                    max_concurrent_tools: parseInt(e.target.value) || 5
                  }
                }))}
              />
            </div>
            <div>
              <Label htmlFor="retries">Retry Attempts</Label>
              <Input
                id="retries"
                type="number"
                value={config.execution_settings.retry_attempts}
                onChange={(e) => setConfig(prev => ({
                  ...prev,
                  execution_settings: {
                    ...prev.execution_settings,
                    retry_attempts: parseInt(e.target.value) || 3
                  }
                }))}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Server Selection */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            Server Configuration
          </CardTitle>
          <CardDescription>
            Select which MCP servers the agent should use by default
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <Label>Auto-connect Servers</Label>
              <p className="text-sm text-gray-500 mb-2">
                These servers will be automatically connected when the agent starts
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {servers.map((server) => (
                  <div key={server.id} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={config.auto_connect_servers.includes(server.id)}
                        onCheckedChange={(checked) => {
                          setConfig(prev => ({
                            ...prev,
                            auto_connect_servers: checked
                              ? [...prev.auto_connect_servers, server.id]
                              : prev.auto_connect_servers.filter(id => id !== server.id)
                          }));
                        }}
                      />
                      <div>
                        <div className="font-medium text-sm">{server.name}</div>
                        <div className="text-xs text-gray-500">{server.category}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      {activeConnections.includes(server.id) ? (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      ) : (
                        <XCircle className="h-4 w-4 text-gray-400" />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div>
              <Label>Default Servers</Label>
              <p className="text-sm text-gray-500 mb-2">
                These servers will be preferred by the agent for tool selection
              </p>
              <Select
                value={config.default_servers[0] || ''}
                onValueChange={(value) => {
                  setConfig(prev => ({
                    ...prev,
                    default_servers: value ? [value] : []
                  }));
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select default server" />
                </SelectTrigger>
                <SelectContent>
                  {servers.map((server) => (
                    <SelectItem key={server.id} value={server.id}>
                      {server.name} ({server.category})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Server Connection Status */}
      <Card>
        <CardHeader>
          <CardTitle>Server Connection Status</CardTitle>
          <CardDescription>
            Manage active connections to MCP servers
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {servers.map((server) => {
              const isConnected = activeConnections.includes(server.id);
              return (
                <div key={server.id} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <h4 className="font-medium">{server.name}</h4>
                      <Badge variant="outline">{server.category}</Badge>
                    </div>
                    {isConnected ? (
                      <Badge className="bg-green-500">
                        <CheckCircle className="h-3 w-3 mr-1" />
                        Connected
                      </Badge>
                    ) : (
                      <Badge variant="secondary">
                        <XCircle className="h-3 w-3 mr-1" />
                        Available
                      </Badge>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 mb-3">{server.description}</p>
                  {server.tools_count && (
                    <p className="text-xs text-gray-500 mb-3">
                      {server.tools_count} tools available
                    </p>
                  )}
                  <div className="flex gap-2">
                    {isConnected ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => disconnectServer(server.id)}
                      >
                        <Square className="h-3 w-3 mr-1" />
                        Disconnect
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => connectServer(server.id)}
                        disabled={server.status === 'unavailable'}
                      >
                        <Play className="h-3 w-3 mr-1" />
                        Connect
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => window.open(`/mcp`, '_blank')}
                    >
                      <Settings className="h-3 w-3 mr-1" />
                      Configure
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Info className="h-5 w-5" />
            About MCP Agent Integration
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <p>
              <strong>Model Context Protocol (MCP)</strong> allows the main agent to access specialized tools
              from external servers, extending its capabilities beyond built-in functions.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <div>
                <h4 className="font-medium mb-2">Available Server Types:</h4>
                <ul className="space-y-1 text-gray-600">
                  <li>• 📁 File system operations</li>
                  <li>• 🔍 Web search capabilities</li>
                  <li>• 🗄️ Database connectivity</li>
                  <li>• 💻 Development tools (Git, GitHub)</li>
                </ul>
              </div>
              <div>
                <h4 className="font-medium mb-2">Agent Benefits:</h4>
                <ul className="space-y-1 text-gray-600">
                  <li>• Extended tool capabilities</li>
                  <li>• Real-time data access</li>
                  <li>• Specialized functionality</li>
                  <li>• Workflow integration</li>
                </ul>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default MCPSettings;