import React, { useState } from "react";
import {
  Card,
  CardHeader,
  CardContent,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Slider } from "@/components/ui/slider";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";
import {
  Plus,
  Edit,
  Trash2,
  Play,
  Square,
  Settings,
  AlertTriangle,
  Bot,
  Activity,
  CheckCircle,
  Clock,
  Zap,
} from "lucide-react";

interface Agent {
  id: string;
  name: string;
  role: string;
  status: "active" | "inactive" | "error";
  capabilities: string[];
  performance: {
    tasksCompleted: number;
    successRate: number;
    avgResponseTime: number;
  };
  config: {
    model: string;
    temperature: number;
    maxTokens: number;
  };
}

interface AgentManagerProps {
  onAgentCreate?: (agent: Omit<Agent, "id">) => void;
  onAgentUpdate?: (id: string, updates: Partial<Agent>) => void;
  onAgentDelete?: (id: string) => void;
  onAgentStart?: (id: string) => void;
  onAgentStop?: (id: string) => void;
  initialAgents?: Agent[];
}

const AgentManager: React.FC<AgentManagerProps> = ({
  onAgentCreate,
  onAgentUpdate,
  onAgentDelete,
  onAgentStart,
  onAgentStop,
  initialAgents = [],
}) => {
  const [agents, setAgents] = useState<Agent[]>(initialAgents);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const { toast } = useToast();

  const [newAgent, setNewAgent] = useState({
    name: "",
    role: "",
    capabilities: [] as string[],
    config: {
      model: "gpt-4",
      temperature: 0.7,
      maxTokens: 1000,
    },
  });

  const availableCapabilities = [
    "calendar_management",
    "task_management",
    "email_processing",
    "document_analysis",
    "financial_analysis",
    "social_media",
    "voice_commands",
    "workflow_automation",
  ];

  const handleCreateAgent = async () => {
    if (!newAgent.name.trim() || !newAgent.role.trim()) {
      toast({
        title: "Validation Error",
        description: "Name and role are required",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);
    try {
      const agentData = {
        ...newAgent,
        status: "inactive" as const,
        performance: {
          tasksCompleted: 0,
          successRate: 0,
          avgResponseTime: 0,
        },
      };

      onAgentCreate?.(agentData);

      // Simulate API call
      setTimeout(() => {
        const createdAgent: Agent = {
          id: Date.now().toString(),
          ...agentData,
        };

        setAgents((prev) => [...prev, createdAgent]);
        setNewAgent({
          name: "",
          role: "",
          capabilities: [],
          config: {
            model: "gpt-4",
            temperature: 0.7,
            maxTokens: 1000,
          },
        });
        setIsModalOpen(false);

        toast({
          title: "Agent Created",
          description: `${createdAgent.name} has been created successfully`,
        });
      }, 1000);
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create agent",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateAgent = (id: string, updates: Partial<Agent>) => {
    setAgents((prev) =>
      prev.map((agent) => (agent.id === id ? { ...agent, ...updates } : agent)),
    );
    onAgentUpdate?.(id, updates);
  };

  const handleDeleteAgent = (id: string) => {
    setAgents((prev) => prev.filter((agent) => agent.id !== id));
    onAgentDelete?.(id);

    toast({
      title: "Agent Deleted",
      description: "Agent has been removed successfully",
    });
  };

  const handleStartAgent = (id: string) => {
    handleUpdateAgent(id, { status: "active" });
    onAgentStart?.(id);

    toast({
      title: "Agent Started",
      description: "Agent is now active and processing tasks",
    });
  };

  const handleStopAgent = (id: string) => {
    handleUpdateAgent(id, { status: "inactive" });
    onAgentStop?.(id);

    toast({
      title: "Agent Stopped",
      description: "Agent has been deactivated",
    });
  };

  const toggleCapability = (capability: string) => {
    setNewAgent((prev) => ({
      ...prev,
      capabilities: prev.capabilities.includes(capability)
        ? prev.capabilities.filter((c) => c !== capability)
        : [...prev.capabilities, capability],
    }));
  };

  const getStatusColor = (status: Agent["status"]) => {
    switch (status) {
      case "active":
        return "bg-green-500 hover:bg-green-600";
      case "inactive":
        return "bg-gray-500 hover:bg-gray-600";
      case "error":
        return "bg-red-500 hover:bg-red-600";
      default:
        return "bg-gray-500 hover:bg-gray-600";
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold tracking-tight">Agent Manager</h2>
          <p className="text-gray-500">Manage and monitor your AI agents</p>
        </div>
        <Button onClick={() => setIsModalOpen(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Create Agent
        </Button>
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {agents.map((agent) => (
          <Card key={agent.id} className="flex flex-col">
            <CardHeader>
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <CardTitle className="text-lg flex items-center">
                    <Bot className="w-5 h-5 mr-2 text-blue-500" />
                    {agent.name}
                  </CardTitle>
                  <CardDescription>{agent.role}</CardDescription>
                </div>
                <Badge className={getStatusColor(agent.status)}>
                  {agent.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="flex-1 space-y-6">
              {/* Capabilities */}
              <div className="space-y-2">
                <p className="font-medium text-sm">Capabilities</p>
                <div className="flex flex-wrap gap-1">
                  {agent.capabilities.map((capability) => (
                    <Badge key={capability} variant="secondary" className="text-xs">
                      {capability.replace("_", " ")}
                    </Badge>
                  ))}
                </div>
              </div>

              {/* Performance */}
              <div className="space-y-2">
                <p className="font-medium text-sm">Performance</p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 flex items-center">
                      <CheckCircle className="w-3 h-3 mr-1" /> Tasks Completed
                    </span>
                    <span className="font-medium">
                      {agent.performance.tasksCompleted}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 flex items-center">
                      <Activity className="w-3 h-3 mr-1" /> Success Rate
                    </span>
                    <span className="font-medium">
                      {agent.performance.successRate}%
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-500 flex items-center">
                      <Clock className="w-3 h-3 mr-1" /> Avg Response
                    </span>
                    <span className="font-medium">
                      {agent.performance.avgResponseTime}ms
                    </span>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end space-x-2 pt-2">
                {agent.status === "active" ? (
                  <Button
                    size="sm"
                    variant="destructive"
                    onClick={() => handleStopAgent(agent.id)}
                  >
                    <Square className="w-4 h-4 mr-2" />
                    Stop
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    className="bg-green-600 hover:bg-green-700"
                    onClick={() => handleStartAgent(agent.id)}
                  >
                    <Play className="w-4 h-4 mr-2" />
                    Start
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSelectedAgent(agent);
                    setNewAgent({
                      name: agent.name,
                      role: agent.role,
                      capabilities: agent.capabilities,
                      config: agent.config,
                    });
                    setIsModalOpen(true);
                  }}
                >
                  <Edit className="w-4 h-4" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-red-500 hover:text-red-700 hover:bg-red-50"
                  onClick={() => handleDeleteAgent(agent.id)}
                >
                  <Trash2 className="w-4 h-4" />
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {agents.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12 space-y-4">
            <Bot className="w-12 h-12 text-gray-400" />
            <div className="text-center space-y-1">
              <h3 className="text-lg font-medium">No Agents Created</h3>
              <p className="text-gray-500">
                Create your first agent to get started with multi-agent automation
              </p>
            </div>
            <Button onClick={() => setIsModalOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create First Agent
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Create/Edit Agent Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {selectedAgent ? "Edit Agent" : "Create New Agent"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 py-4">
            <div className="space-y-2">
              <Label>Agent Name <span className="text-red-500">*</span></Label>
              <Input
                value={newAgent.name}
                onChange={(e) =>
                  setNewAgent((prev) => ({ ...prev, name: e.target.value }))
                }
                placeholder="Enter agent name"
              />
            </div>

            <div className="space-y-2">
              <Label>Role <span className="text-red-500">*</span></Label>
              <Input
                value={newAgent.role}
                onChange={(e) =>
                  setNewAgent((prev) => ({ ...prev, role: e.target.value }))
                }
                placeholder="Enter agent role"
              />
            </div>

            <div className="space-y-2">
              <Label>Capabilities</Label>
              <div className="grid grid-cols-2 gap-2">
                {availableCapabilities.map((capability) => (
                  <Button
                    key={capability}
                    size="sm"
                    variant={
                      newAgent.capabilities.includes(capability)
                        ? "default"
                        : "outline"
                    }
                    onClick={() => toggleCapability(capability)}
                    className="justify-start text-xs"
                    type="button"
                  >
                    {newAgent.capabilities.includes(capability) && (
                      <CheckCircle className="w-3 h-3 mr-2" />
                    )}
                    {capability.replace("_", " ")}
                  </Button>
                ))}
              </div>
            </div>

            <div className="space-y-4 border rounded-md p-4 bg-gray-50 dark:bg-gray-900">
              <div className="flex items-center space-x-2">
                <Settings className="w-4 h-4" />
                <Label className="font-semibold">Model Configuration</Label>
              </div>

              <div className="space-y-2">
                <Label>Model</Label>
                <Select
                  value={newAgent.config.model}
                  onValueChange={(value) =>
                    setNewAgent((prev) => ({
                      ...prev,
                      config: { ...prev.config, model: value },
                    }))
                  }
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="gpt-4">GPT-4</SelectItem>
                    <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
                    <SelectItem value="claude-2">Claude 2</SelectItem>
                    <SelectItem value="llama-2">Llama 2</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>Temperature</Label>
                    <span className="text-sm text-gray-500">{newAgent.config.temperature}</span>
                  </div>
                  <Slider
                    min={0}
                    max={1}
                    step={0.1}
                    value={[newAgent.config.temperature]}
                    onValueChange={(value) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        config: {
                          ...prev.config,
                          temperature: value[0],
                        },
                      }))
                    }
                  />
                </div>

                <div className="space-y-2">
                  <div className="flex justify-between">
                    <Label>Max Tokens</Label>
                    <span className="text-sm text-gray-500">{newAgent.config.maxTokens}</span>
                  </div>
                  <Slider
                    min={100}
                    max={4000}
                    step={100}
                    value={[newAgent.config.maxTokens]}
                    onValueChange={(value) =>
                      setNewAgent((prev) => ({
                        ...prev,
                        config: {
                          ...prev.config,
                          maxTokens: value[0],
                        },
                      }))
                    }
                  />
                </div>
              </div>
            </div>

            <Alert>
              <Zap className="h-4 w-4" />
              <AlertTitle>Note</AlertTitle>
              <AlertDescription>
                Agents can be started and stopped as needed. Active agents will
                process tasks automatically.
              </AlertDescription>
            </Alert>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreateAgent}
              disabled={isLoading || !newAgent.name.trim() || !newAgent.role.trim()}
            >
              {isLoading && <Activity className="mr-2 h-4 w-4 animate-spin" />}
              {selectedAgent ? "Update Agent" : "Create Agent"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AgentManager;
