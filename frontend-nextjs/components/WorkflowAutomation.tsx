import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import {
  Card,
  CardHeader,
  CardContent,
  CardFooter,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useToast } from "@/components/ui/use-toast";
import {
  Plus,
  CheckCircle,
  X,
  Edit,
  Trash2,
  Eye,
  ArrowRight,
  Settings,
  Clock,
  MessageSquare,
  Mail,
  Paperclip,
  ChevronDown,
  RefreshCw,
  Loader2,
  Layout as LayoutIcon,
  List,
  Play,
  AlertTriangle,
  FileText,
  Activity,
} from "lucide-react";

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  steps: WorkflowStep[];
  input_schema: any;
}

interface WorkflowStep {
  id: string;
  type: string;
  service?: string;
  action?: string;
  parameters: Record<string, any>;
  name: string;
}

interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  steps: WorkflowStep[];
  input_schema: any;
  created_at: string;
  updated_at: string;
  steps_count?: number;
}

interface WorkflowExecution {
  execution_id: string;
  workflow_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled" | "paused";
  start_time: string;
  end_time?: string;
  current_step: number;
  total_steps: number;
  trigger_data?: Record<string, any>;
  results?: Record<string, any>;
  errors?: string[];
  has_errors?: boolean;
}

interface ServiceInfo {
  name: string;
  actions: string[];
  description: string;
}

import WorkflowBuilder from "./Automations/WorkflowBuilder";


const WorkflowAutomation: React.FC = () => {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowDefinition[]>([]);
  const [executions, setExecutions] = useState<WorkflowExecution[]>([]);
  const [services, setServices] = useState<Record<string, ServiceInfo>>({});
  const [selectedTemplate, setSelectedTemplate] =
    useState<WorkflowTemplate | null>(null);
  const [selectedWorkflow, setSelectedWorkflow] =
    useState<WorkflowDefinition | null>(null);
  const [activeExecution, setActiveExecution] =
    useState<WorkflowExecution | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [activeTab, setActiveTab] = useState("templates");
  const [viewMode, setViewMode] = useState<"classic" | "builder">("classic");

  // Modal states
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false);
  const [isExecutionModalOpen, setIsExecutionModalOpen] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isResumeModalOpen, setIsResumeModalOpen] = useState(false);
  const [resumeExecutionId, setResumeExecutionId] = useState<string | null>(null);

  const [builderInitialData, setBuilderInitialData] = useState<any>(null); // For AI generated workflows
  const [genPrompt, setGenPrompt] = useState("");

  const { toast } = useToast();

  // Fetch initial data
  useEffect(() => {
    fetchWorkflowData();
  }, []);

  // Check for draft in URL
  const router = useRouter();
  useEffect(() => {
    if (router.query.draft) {
      try {
        const draftData = JSON.parse(router.query.draft as string);
        setBuilderInitialData(draftData);
        setViewMode("builder");
        toast({ title: "Draft Loaded", description: "Loaded workflow from chat." });
        // Clean URL
        router.replace('/automation', undefined, { shallow: true });
      } catch (e) {
        console.error("Failed to parse draft", e);
      }
    }
  }, [router.query.draft]);

  // Poll for execution updates when modal is open or executions are running
  useEffect(() => {
    const hasRunning = executions.some(e => e.status === 'running');
    if (isExecutionModalOpen || hasRunning) {
      const interval = setInterval(fetchExecutions, 2000);
      return () => clearInterval(interval);
    }
  }, [isExecutionModalOpen, executions]);

  // Sync activeExecution with updated list
  useEffect(() => {
    if (activeExecution) {
      const updated = executions.find(e => e.execution_id === activeExecution.execution_id);
      if (updated && JSON.stringify(updated) !== JSON.stringify(activeExecution)) {
        setActiveExecution(updated);
      }
    }
  }, [executions]);

  const handleGenerativeCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!genPrompt.trim()) return;

    setLoading(true);
    // Mock AI Generation Logic
    // In real app, this would call an LLM endpoint
    setTimeout(() => {
      const generatedNodes = [
        { id: '1', type: 'trigger', position: { x: 250, y: 0 }, data: { label: 'Start: ' + genPrompt.substring(0, 15) + '...', integration: 'Webhook' } },
        { id: '2', type: 'ai_node', position: { x: 250, y: 200 }, data: { label: 'Process Request', prompt: 'Analyze: ' + genPrompt } },
        { id: '3', type: 'action', position: { x: 250, y: 400 }, data: { service: 'Slack', action: 'Notify User' } }
      ];
      const generatedEdges = [
        { id: 'e1-2', source: '1', target: '2' },
        { id: 'e2-3', source: '2', target: '3' }
      ];

      setBuilderInitialData({ nodes: generatedNodes, edges: generatedEdges });
      setViewMode("builder");
      toast({ title: "Workflow Generated", description: "AI created a draft workflow based on your prompt." });
      setLoading(false);
      setGenPrompt("");
    }, 1000);
  };

  const fetchWorkflowData = async () => {
    try {
      setLoading(true);
      await Promise.all([
        fetchTemplates(),
        fetchWorkflows(),
        fetchExecutions(),
        fetchServices(),
      ]);
    } catch (error) {
      console.error("Error fetching workflow data:", error);
      toast({
        title: "Error",
        description: "Failed to load workflow data",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  const fetchTemplates = async () => {
    try {
      const response = await fetch("/api/workflows/templates");
      const data = await response.json();
      if (data.success) {
        setTemplates(data.templates);
      }
    } catch (e) {
      console.error("Failed to fetch templates", e);
    }
  };

  const fetchWorkflows = async () => {
    try {
      const response = await fetch("/api/workflows/definitions");
      const data = await response.json();
      if (data.success) {
        setWorkflows(data.workflows);
      }
    } catch (e) {
      console.error("Failed to fetch workflows", e);
    }
  };

  const fetchExecutions = async () => {
    try {
      const response = await fetch("/api/workflows/executions");
      const data = await response.json();
      if (data.success) {
        setExecutions(data.executions);
      }
    } catch (e) {
      console.error("Failed to fetch executions", e);
    }
  };

  const fetchServices = async () => {
    try {
      const response = await fetch("/api/workflows/services");
      const data = await response.json();
      if (data.success) {
        setServices(data.services);
      }
    } catch (e) {
      console.error("Failed to fetch services", e);
    }

  };

  const handleBuilderSave = async (builderData: { nodes: any[]; edges: any[] }) => {
    try {
      setLoading(true);
      const response = await fetch("/api/workflows/definitions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: `Visual Workflow ${new Date().toLocaleTimeString()}`,
          description: "Created via Visual Builder",
          definition: builderData,
        }),
      });
      const data = await response.json();
      if (data.success) {
        toast({
          title: "Workflow Saved",
          description: "Your visual workflow has been saved to the database.",
        });
        await fetchWorkflowData(); // Refresh list
      } else {
        throw new Error(data.error || "Failed to save");
      }
    } catch (e) {
      console.error("Save error", e);
      toast({ title: "Error", description: "Failed to save workflow", variant: "error" });
    } finally {
      setLoading(false);
    }
  };

  const handleTemplateSelect = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
    setFormData({});
    setIsTemplateModalOpen(true);
  };

  const handleWorkflowSelect = (workflow: WorkflowDefinition) => {
    setSelectedWorkflow(workflow);
    setFormData({});
    setIsCreateModalOpen(true);
  };

  const handleExecuteWorkflow = async (
    workflowId: string,
    inputData: Record<string, any> = {},
  ) => {
    try {
      setExecuting(true);
      const response = await fetch("/api/workflows/execute", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          workflow_id: workflowId,
          input: inputData,
        }),
      });

      const data = await response.json();
      if (data.success) {
        toast({
          title: "Workflow Started",
          description: `Execution ${data.execution_id} has started`,
        });

        // Refresh executions list
        await fetchExecutions();

        // Show execution details
        setActiveExecution(data);
        setIsExecutionModalOpen(true);
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error("Error executing workflow:", error);
      toast({
        title: "Error",
        description: "Failed to execute workflow",
        variant: "error",
      });
    } finally {
      setExecuting(false);
    }
  };

  const handleCancelExecution = async (executionId: string) => {
    try {
      const response = await fetch(
        `/api/workflows/executions/${executionId}/cancel`,
        {
          method: "POST",
        },
      );

      const data = await response.json();
      if (data.success) {
        toast({
          title: "Execution Cancelled",
          description: `Execution ${executionId} has been cancelled`,
        });
        await fetchExecutions();
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error("Error cancelling execution:", error);
      toast({
        title: "Error",
        description: "Failed to cancel execution",
        variant: "error",
      });
    }
  };

  const handleResumeWorkflow = async (
    executionId: string,
    inputs: Record<string, any> = {}
  ) => {
    try {
      setExecuting(true);
      const response = await fetch(
        `/api/workflows/executions/${executionId}/resume`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ inputs }),
        }
      );

      const data = await response.json();
      if (data.success) {
        toast({
          title: "Execution Resumed",
          description: `Execution ${executionId} has been resumed`,
        });
        await fetchExecutions();
        setIsResumeModalOpen(false);
        setResumeExecutionId(null);
      } else {
        throw new Error(data.error);
      }
    } catch (error) {
      console.error("Error resuming execution:", error);
      toast({
        title: "Error",
        description: "Failed to resume execution",
        variant: "error",
      });
    } finally {
      setExecuting(false);
    }
  };

  const handleFormChange = (field: string, value: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const renderServiceIcon = (service: string) => {
    const iconClass = "w-4 h-4 mr-2";
    switch (service) {
      case "calendar":
        return <Clock className={`${iconClass} text-blue-500`} />;
      case "tasks":
        return <CheckCircle className={`${iconClass} text-green-500`} />;
      case "messages":
        return <MessageSquare className={`${iconClass} text-purple-500`} />;
      case "email":
        return <Mail className={`${iconClass} text-red-500`} />;
      case "documents":
        return <Paperclip className={`${iconClass} text-orange-500`} />;
      case "asana":
      case "trello":
      case "notion":
        return <LayoutIcon className={`${iconClass} text-teal-500`} />;
      case "dropbox":
        return <ChevronDown className={`${iconClass} text-blue-500`} />;
      default:
        return <Settings className={`${iconClass} text-gray-500`} />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-500 hover:bg-green-600";
      case "running":
        return "bg-blue-500 hover:bg-blue-600";
      case "failed":
        return "bg-red-500 hover:bg-red-600";
      case "cancelled":
        return "bg-orange-500 hover:bg-orange-600";
      case "pending":
        return "bg-yellow-500 hover:bg-yellow-600";
      case "paused":
        return "bg-amber-500 hover:bg-amber-600";
      default:
        return "bg-gray-500 hover:bg-gray-600";
    }
  };

  const getStatusBadgeVariant = (status: string) => {
    switch (status) {
      case "completed":
        return "default"; // Green-ish usually or customize
      case "running":
        return "secondary";
      case "failed":
        return "destructive";
      case "cancelled":
        return "outline";
      case "pending":
        return "secondary";
      case "paused":
        return "outline"; // Distinction
      default:
        return "outline";
    }
  };

  const renderInputField = (field: string, schema: any) => {
    const fieldSchema = schema.properties[field];
    const isRequired = schema.required?.includes(field);

    switch (fieldSchema.type) {
      case "string":
        if (fieldSchema.format === "email") {
          return (
            <div key={field} className="space-y-2">
              <Label htmlFor={field}>
                {fieldSchema.title} {isRequired && "*"}
              </Label>
              <Input
                id={field}
                type="email"
                value={formData[field] || ""}
                onChange={(e) => handleFormChange(field, e.target.value)}
                placeholder={fieldSchema.title}
                required={isRequired}
              />
              {fieldSchema.description && (
                <p className="text-sm text-gray-500">
                  {fieldSchema.description}
                </p>
              )}
            </div>
          );
        } else if (fieldSchema.format === "date") {
          return (
            <div key={field} className="space-y-2">
              <Label htmlFor={field}>
                {fieldSchema.title} {isRequired && "*"}
              </Label>
              <Input
                id={field}
                type="date"
                value={formData[field] || ""}
                onChange={(e) => handleFormChange(field, e.target.value)}
                required={isRequired}
              />
            </div>
          );
        } else {
          return (
            <div key={field} className="space-y-2">
              <Label htmlFor={field}>
                {fieldSchema.title} {isRequired && "*"}
              </Label>
              <Input
                id={field}
                type="text"
                value={formData[field] || ""}
                onChange={(e) => handleFormChange(field, e.target.value)}
                placeholder={fieldSchema.title}
                required={isRequired}
              />
              {fieldSchema.description && (
                <p className="text-sm text-gray-500">
                  {fieldSchema.description}
                </p>
              )}
            </div>
          );
        }

      case "array":
        return (
          <div key={field} className="space-y-2">
            <Label htmlFor={field}>
              {fieldSchema.title} {isRequired && "*"}
            </Label>
            <Textarea
              id={field}
              value={
                Array.isArray(formData[field]) ? formData[field].join(", ") : ""
              }
              onChange={(e) =>
                handleFormChange(
                  field,
                  e.target.value.split(",").map((s) => s.trim()),
                )
              }
              placeholder={`Enter ${fieldSchema.title} separated by commas`}
            />
            <p className="text-sm text-gray-500">
              Separate multiple values with commas
            </p>
          </div>
        );

      default:
        return (
          <div key={field} className="space-y-2">
            <Label htmlFor={field}>
              {fieldSchema.title} {isRequired && "*"}
            </Label>
            <Input
              id={field}
              type="text"
              value={formData[field] || ""}
              onChange={(e) => handleFormChange(field, e.target.value)}
              placeholder={fieldSchema.title}
              required={isRequired}
            />
          </div>
        );
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 space-y-4">
        <Loader2 className="w-12 h-12 animate-spin text-blue-500" />
        <p className="text-gray-600">Loading workflow automation...</p>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">
            Workflow Automation
          </h1>
          <p className="text-gray-500">
            Automate your tasks and processes across all connected services
          </p>
        </div>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            onClick={() => setViewMode(viewMode === "classic" ? "builder" : "classic")}
          >
            {viewMode === "classic" ? (
              <>
                <LayoutIcon className="w-4 h-4 mr-2" />
                Visual Builder
              </>
            ) : (
              <>
                <List className="w-4 h-4 mr-2" />
                Classic View
              </>
            )}
          </Button>
          <Button onClick={() => setIsCreateModalOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Create Workflow
          </Button>
        </div>
      </div>

      {viewMode === "builder" ? (
        <WorkflowBuilder />
      ) : (
        /* Main Content */
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="templates">Templates</TabsTrigger>
            <TabsTrigger value="workflows">My Workflows</TabsTrigger>
            <TabsTrigger value="executions">Executions</TabsTrigger>
            <TabsTrigger value="services">Services</TabsTrigger>
          </TabsList>

          {/* Templates Tab */}
          <TabsContent value="templates" className="mt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {templates.map((template) => (
                <Card
                  key={template.id}
                  className="hover:shadow-md transition-shadow cursor-pointer"
                >
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div className="flex items-center">
                        {renderServiceIcon(template.category)}
                        <CardTitle className="text-lg">{template.name}</CardTitle>
                      </div>
                      <Badge variant="secondary">
                        {template.steps.length} steps
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <CardDescription className="mb-4 min-h-[40px]">
                      {template.description}
                    </CardDescription>
                    <div className="space-y-2">
                      {template.steps.slice(0, 3).map((step, index) => (
                        <div key={step.id} className="flex items-center text-sm">
                          <Badge
                            variant="outline"
                            className="mr-2 w-5 h-5 flex items-center justify-center p-0"
                          >
                            {index + 1}
                          </Badge>
                          <span className="truncate">{step.name}</span>
                        </div>
                      ))}
                      {template.steps.length > 3 && (
                        <p className="text-xs text-gray-500 pl-7">
                          +{template.steps.length - 3} more steps
                        </p>
                      )}
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Button
                      className="w-full"
                      onClick={() => handleTemplateSelect(template)}
                    >
                      Use Template
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          </TabsContent>

          {/* My Workflows Tab */}
          <TabsContent value="workflows" className="mt-6">
            <div className="space-y-4">
              {workflows.map((workflow) => (
                <Card key={workflow.id}>
                  <CardHeader>
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <CardTitle>{workflow.name}</CardTitle>
                        <CardDescription>{workflow.description}</CardDescription>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Badge variant="outline">
                          {workflow.steps_count || workflow.steps?.length || 0}{" "}
                          steps
                        </Badge>
                        <Button variant="ghost" size="icon">
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => handleWorkflowSelect(workflow)}
                        >
                          <Play className="w-4 h-4 mr-2" />
                          Run
                        </Button>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xs text-gray-500">
                      Created:{" "}
                      {new Date(workflow.created_at).toLocaleDateString()}
                    </p>
                  </CardContent>
                </Card>
              ))}
              {workflows.length === 0 && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>No workflows yet</AlertTitle>
                  <AlertDescription>
                    Create your first workflow using a template or from scratch.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </TabsContent>

          {/* Executions Tab */}
          <TabsContent value="executions" className="mt-6">
            <div className="space-y-4">
              {executions.map((execution) => (
                <Card key={execution.execution_id}>
                  <CardContent className="pt-6">
                    <div className="flex flex-col md:flex-row justify-between gap-4">
                      <div className="space-y-2">
                        <div className="flex items-center space-x-2">
                          <Badge
                            className={getStatusColor(execution.status)}
                            variant="secondary"
                          >
                            {execution.status}
                          </Badge>
                          <span className="font-semibold">
                            {execution.workflow_id}
                          </span>
                        </div>
                        <div className="text-sm text-gray-500 space-y-1">
                          <p>
                            Started:{" "}
                            {new Date(execution.start_time).toLocaleString()}
                          </p>
                          {execution.end_time && (
                            <p>
                              Ended:{" "}
                              {new Date(execution.end_time).toLocaleString()}
                            </p>
                          )}
                        </div>
                      </div>

                      <div className="flex items-center space-x-4 min-w-[300px]">
                        <div className="flex-1 space-y-1">
                          <div className="flex justify-between text-xs">
                            <span>Progress</span>
                            <span>
                              {execution.current_step}/{execution.total_steps}
                            </span>
                          </div>
                          <Progress
                            value={
                              (execution.current_step / execution.total_steps) *
                              100
                            }
                            className="h-2"
                          />
                        </div>

                        <div className="flex items-center space-x-2">
                          {execution.status === "running" && (
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() =>
                                handleCancelExecution(execution.execution_id)
                              }
                            >
                              Cancel
                            </Button>
                          )}
                          {execution.status === "paused" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => {
                                setResumeExecutionId(execution.execution_id);
                                setFormData({}); // Clear form for new inputs
                                setIsResumeModalOpen(true);
                              }}
                            >
                              <Play className="w-3 h-3 mr-1" /> Resume
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => {
                              setActiveExecution(execution);
                              setIsExecutionModalOpen(true);
                            }}
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
              {executions.length === 0 && (
                <Alert>
                  <Activity className="h-4 w-4" />
                  <AlertTitle>No executions yet</AlertTitle>
                  <AlertDescription>
                    Execute a workflow to see execution history here.
                  </AlertDescription>
                </Alert>
              )}
            </div>
          </TabsContent>

          {/* Services Tab */}
          <TabsContent value="services" className="mt-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {Object.entries(services).map(([serviceName, serviceInfo]) => (
                <Card key={serviceName}>
                  <CardHeader>
                    <div className="flex items-center">
                      {renderServiceIcon(serviceName)}
                      <CardTitle className="text-lg capitalize">
                        {serviceName}
                      </CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-gray-600 mb-4 min-h-[40px]">
                      {serviceInfo.description}
                    </p>
                    <div className="space-y-2">
                      <p className="font-semibold text-sm">Available Actions:</p>
                      <div className="flex flex-wrap gap-2">
                        {serviceInfo.actions.slice(0, 5).map((action) => (
                          <Badge key={action} variant="secondary">
                            {action}
                          </Badge>
                        ))}
                        {serviceInfo.actions.length > 5 && (
                          <span className="text-xs text-gray-500 flex items-center">
                            +{serviceInfo.actions.length - 5} more
                          </span>
                        )}
                      </div>
                    </div>
                  </CardContent>
                  <CardFooter>
                    <Badge variant="outline" className="ml-auto">
                      {serviceInfo.actions.length} actions
                    </Badge>
                  </CardFooter>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      )}

      {/* Template Execution Modal */}
      <Dialog open={isTemplateModalOpen} onOpenChange={setIsTemplateModalOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Use Template: {selectedTemplate?.name}</DialogTitle>
          </DialogHeader>
          {selectedTemplate && (
            <div className="space-y-6">
              <p className="text-gray-600">{selectedTemplate.description}</p>

              <div className="space-y-2">
                <h3 className="font-semibold">Workflow Steps:</h3>
                <div className="space-y-2 pl-2 border-l-2 border-gray-200">
                  {selectedTemplate.steps.map((step, index) => (
                    <div key={step.id} className="flex items-start space-x-3">
                      <Badge variant="outline" className="mt-0.5">
                        {index + 1}
                      </Badge>
                      <div>
                        <p className="font-medium text-sm">{step.name}</p>
                        <p className="text-xs text-gray-500">
                          {step.service}.{step.action}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="font-semibold">Input Parameters:</h3>
                <div className="space-y-4">
                  {selectedTemplate.input_schema?.properties &&
                    Object.keys(selectedTemplate.input_schema.properties).map(
                      (field) =>
                        renderInputField(field, selectedTemplate.input_schema),
                    )}
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsTemplateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (selectedTemplate) {
                  handleExecuteWorkflow(selectedTemplate.id, formData);
                  setIsTemplateModalOpen(false);
                }
              }}
              disabled={executing}
            >
              {executing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Execute Workflow
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Workflow Execution Modal */}
      <Dialog open={isCreateModalOpen} onOpenChange={setIsCreateModalOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              Execute Workflow: {selectedWorkflow?.name}
            </DialogTitle>
          </DialogHeader>
          {selectedWorkflow && (
            <div className="space-y-6">
              <p className="text-gray-600">{selectedWorkflow.description}</p>

              <div className="space-y-2">
                <h3 className="font-semibold">Workflow Steps:</h3>
                <div className="space-y-2 pl-2 border-l-2 border-gray-200">
                  {selectedWorkflow.steps?.map((step, index) => (
                    <div key={step.id} className="flex items-start space-x-3">
                      <Badge variant="outline" className="mt-0.5">
                        {index + 1}
                      </Badge>
                      <div>
                        <p className="font-medium text-sm">{step.name}</p>
                        <p className="text-xs text-gray-500">
                          {step.service}.{step.action}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="space-y-4">
                <h3 className="font-semibold">Input Parameters:</h3>
                <div className="space-y-4">
                  {selectedWorkflow.input_schema?.properties &&
                    Object.keys(selectedWorkflow.input_schema.properties).map(
                      (field) =>
                        renderInputField(field, selectedWorkflow.input_schema),
                    )}
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (selectedWorkflow) {
                  handleExecuteWorkflow(selectedWorkflow.id, formData);
                  setIsCreateModalOpen(false);
                }
              }}
              disabled={executing}
            >
              {executing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Execute Workflow
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resume Execution Modal */}
      <Dialog open={isResumeModalOpen} onOpenChange={setIsResumeModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Resume Execution</DialogTitle>
            <DialogDescription>
              Provide missing parameters to resume the workflow.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Parameters</Label>
              {Object.keys(formData).map((key) => (
                <div key={key} className="flex items-center space-x-2">
                  <Input
                    placeholder="Key"
                    value={key}
                    disabled
                    className="flex-1"
                  />
                  <Input
                    placeholder="Value"
                    value={formData[key]}
                    onChange={(e) => handleFormChange(key, e.target.value)}
                    className="flex-1"
                  />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => {
                      const newData = { ...formData };
                      delete newData[key];
                      setFormData(newData);
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-red-500" />
                  </Button>
                </div>
              ))}

              <div className="flex items-center space-x-2">
                <Input
                  placeholder="New Parameter Key"
                  id="new-param-key"
                />
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => {
                    const keyInput = document.getElementById('new-param-key') as HTMLInputElement;
                    if (keyInput && keyInput.value) {
                      handleFormChange(keyInput.value, "");
                      keyInput.value = "";
                    }
                  }}
                >
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              <p className="text-xs text-gray-500">
                Add keys for any missing parameters required by the workflow step.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsResumeModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => {
                if (resumeExecutionId) {
                  handleResumeWorkflow(resumeExecutionId, formData);
                }
              }}
              disabled={executing}
            >
              {executing && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Resume
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Execution Details Modal */}
      <Dialog
        open={isExecutionModalOpen}
        onOpenChange={setIsExecutionModalOpen}
      >
        <DialogContent className="max-w-3xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Execution Details</DialogTitle>
          </DialogHeader>
          {activeExecution && (
            <div className="space-y-6">
              <div className="flex justify-between items-start">
                <div className="space-y-1">
                  <p className="font-bold">
                    Execution ID: {activeExecution.execution_id}
                  </p>
                  <p className="text-sm text-gray-500">
                    Workflow: {activeExecution.workflow_id}
                  </p>
                </div>
                <Badge className={getStatusColor(activeExecution.status)}>
                  {activeExecution.status}
                </Badge>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Started:</span>{" "}
                  {new Date(activeExecution.start_time).toLocaleString()}
                </div>
                {activeExecution.end_time && (
                  <div>
                    <span className="text-gray-500">Ended:</span>{" "}
                    {new Date(activeExecution.end_time).toLocaleString()}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>Progress</span>
                  <span>
                    Step {activeExecution.current_step} of{" "}
                    {activeExecution.total_steps}
                  </span>
                </div>
                <Progress
                  value={
                    (activeExecution.current_step /
                      activeExecution.total_steps) *
                    100
                  }
                  className="h-2"
                />
              </div>

              {activeExecution.results &&
                Object.keys(activeExecution.results).length > 0 && (
                  <div className="space-y-2">
                    <h3 className="font-semibold">Step Results:</h3>
                    <Accordion type="multiple" className="w-full">
                      {Object.entries(activeExecution.results).map(
                        ([stepId, result]) => (
                          <AccordionItem key={stepId} value={stepId}>
                            <AccordionTrigger>Step: {stepId}</AccordionTrigger>
                            <AccordionContent>
                              <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded-md overflow-x-auto text-xs">
                                {JSON.stringify(result, null, 2)}
                              </pre>
                            </AccordionContent>
                          </AccordionItem>
                        ),
                      )}
                    </Accordion>
                  </div>
                )}

              {activeExecution.errors && activeExecution.errors.length > 0 && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Errors</AlertTitle>
                  <div className="mt-2">
                    {activeExecution.errors.map((error, index) => (
                      <AlertDescription key={index} className="block">
                        {error}
                      </AlertDescription>
                    ))}
                  </div>
                </Alert>
              )}
            </div>
          )}
          <DialogFooter>
            <Button onClick={() => setIsExecutionModalOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default WorkflowAutomation;
