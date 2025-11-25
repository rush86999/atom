import React, { useState, useCallback } from "react";
import {
  Plus,
  Play,
  Pause,
  Edit,
  Trash2,
  Zap,
  Clock,
  Users,
  Mail,
  Target,
  Info,
} from "lucide-react";
import { Card, CardContent } from "../../ui/card";
import { Button } from "../../ui/button";
import { Input } from "../../ui/input";
import { Badge } from "../../ui/badge";
import { Alert, AlertDescription, AlertTitle } from "../../ui/alert";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../../ui/tabs";

export interface WorkflowTrigger {
  id: string;
  name: string;
  type: "lead_score" | "behavior" | "engagement" | "company_size" | "custom";
  condition: string;
  value: any;
  enabled: boolean;
}

export interface WorkflowAction {
  id: string;
  type: "email" | "task" | "notification" | "assignment" | "webhook";
  config: Record<string, any>;
  delay?: number;
}

export interface Workflow {
  id: string;
  name: string;
  description: string;
  triggers: WorkflowTrigger[];
  actions: WorkflowAction[];
  enabled: boolean;
  lastRun?: string;
  runs: number;
  successRate: number;
}

export interface WorkflowExecution {
  id: string;
  workflowId: string;
  contactId: string;
  status: "running" | "completed" | "failed" | "paused";
  startedAt: string;
  completedAt?: string;
  actionsCompleted: number;
  totalActions: number;
}

interface HubSpotWorkflowAutomationProps {
  workflows?: Workflow[];
  onWorkflowCreate?: (workflow: Omit<Workflow, "id">) => void;
  onWorkflowUpdate?: (workflow: Workflow) => void;
  onWorkflowDelete?: (workflowId: string) => void;
  onWorkflowToggle?: (workflowId: string, enabled: boolean) => void;
}

const HubSpotWorkflowAutomation: React.FC<HubSpotWorkflowAutomationProps> = ({
  workflows = [],
  onWorkflowCreate,
  onWorkflowUpdate,
  onWorkflowDelete,
  onWorkflowToggle,
}) => {
  const [activeTab, setActiveTab] = useState("active");
  const [isCreating, setIsCreating] = useState(false);
  const [newWorkflow, setNewWorkflow] = useState<Omit<Workflow, "id">>({
    name: "",
    description: "",
    triggers: [],
    actions: [],
    enabled: true,
    runs: 0,
    successRate: 100,
  });

  const triggerTypes = [
    { value: "lead_score", label: "Lead Score", icon: Target },
    { value: "behavior", label: "Behavior", icon: Users },
    { value: "engagement", label: "Engagement", icon: Mail },
    { value: "company_size", label: "Company Size", icon: Target },
    { value: "custom", label: "Custom", icon: Zap },
  ];

  const actionTypes = [
    { value: "email", label: "Send Email", icon: Mail },
    { value: "task", label: "Create Task", icon: Clock },
    { value: "notification", label: "Send Notification", icon: Users },
    { value: "assignment", label: "Assign to Team", icon: Target },
    { value: "webhook", label: "Webhook", icon: Zap },
  ];

  const handleCreateWorkflow = useCallback(() => {
    if (!newWorkflow.name.trim()) return;

    onWorkflowCreate?.(newWorkflow);
    setNewWorkflow({
      name: "",
      description: "",
      triggers: [],
      actions: [],
      enabled: true,
      runs: 0,
      successRate: 100,
    });
    setIsCreating(false);
  }, [newWorkflow, onWorkflowCreate]);

  const handleAddTrigger = useCallback(
    (trigger: Omit<WorkflowTrigger, "id">) => {
      setNewWorkflow((prev) => ({
        ...prev,
        triggers: [
          ...prev.triggers,
          { ...trigger, id: `trigger-${Date.now()}` },
        ],
      }));
    },
    [],
  );

  const handleAddAction = useCallback((action: Omit<WorkflowAction, "id">) => {
    setNewWorkflow((prev) => ({
      ...prev,
      actions: [...prev.actions, { ...action, id: `action-${Date.now()}` }],
    }));
  }, []);

  const getStatusColorScheme = (enabled: boolean) => {
    return enabled ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300" : "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300";
  };

  const getSuccessRateColorScheme = (rate: number) => {
    if (rate >= 90) return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300";
    if (rate >= 75) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300";
    if (rate >= 50) return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300";
    return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300";
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div className="space-y-1">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-gray-100">Workflow Automation</h2>
          <p className="text-gray-600 dark:text-gray-400">
            Automate your sales and marketing processes with intelligent workflows
          </p>
        </div>
        <Button onClick={() => setIsCreating(true)} className="bg-blue-600 hover:bg-blue-700">
          <Plus className="mr-2 h-4 w-4" />
          Create Workflow
        </Button>
      </div>

      {/* Workflow Creation Form */}
      {isCreating && (
        <Card>
          <CardContent className="pt-6">
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Create New Workflow</h3>
                <Button variant="outline" onClick={() => setIsCreating(false)}>Cancel</Button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Workflow Name</label>
                  <Input
                    value={newWorkflow.name}
                    onChange={(e) => setNewWorkflow((prev) => ({ ...prev, name: e.target.value }))}
                    placeholder="e.g., Hot Lead Follow-up"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-900 dark:text-gray-100">Description</label>
                  <Input
                    value={newWorkflow.description}
                    onChange={(e) => setNewWorkflow((prev) => ({ ...prev, description: e.target.value }))}
                    placeholder="Describe what this workflow does"
                  />
                </div>
              </div>

              <hr className="border-gray-200 dark:border-gray-700" />

              {/* Triggers Section */}
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Triggers</h4>
                  <select
                    className="text-sm border rounded px-2 py-1"
                    onChange={(e) => {
                      const type = triggerTypes.find(t => t.value === e.target.value);
                      if (type) {
                        handleAddTrigger({
                          name: `${type.label} Trigger`,
                          type: e.target.value as any,
                          condition: "equals",
                          value: "",
                          enabled: true,
                        });
                        e.target.value = "";
                      }
                    }}
                  >
                    <option value="">+ Add Trigger</option>
                    {triggerTypes.map((trigger) => (
                      <option key={trigger.value} value={trigger.value}>{trigger.label}</option>
                    ))}
                  </select>
                </div>

                {newWorkflow.triggers.map((trigger) => (
                  <Card key={trigger.id} className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-4">
                      <div className="space-y-2">
                        <div className="flex justify-between items-center">
                          <p className="font-medium text-gray-900 dark:text-gray-100">{trigger.name}</p>
                          <div className="flex items-center space-x-2">
                            <input type="checkbox" checked={trigger.enabled} onChange={() => { }} className="w-4 h-4" />
                            <Button size="sm" variant="outline" className="text-red-600"><Trash2 className="h-4 w-4" /></Button>
                          </div>
                        </div>
                        <div className="flex space-x-2">
                          <select className="flex-1 text-sm border rounded px-2 py-1" value={trigger.condition}>
                            <option value="equals">Equals</option>
                            <option value="greater_than">Greater Than</option>
                            <option value="less_than">Less Than</option>
                            <option value="contains">Contains</option>
                          </select>
                          <Input size="sm" value={trigger.value} onChange={() => { }} placeholder="Value" className="flex-1" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <hr className="border-gray-200 dark:border-gray-700" />

              {/* Actions Section */}
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100">Actions</h4>
                  <select
                    className="text-sm border rounded px-2 py-1"
                    onChange={(e) => {
                      const type = actionTypes.find(a => a.value === e.target.value);
                      if (type) {
                        handleAddAction({
                          type: e.target.value as any,
                          config: {},
                          delay: 0,
                        });
                        e.target.value = "";
                      }
                    }}
                  >
                    <option value="">+ Add Action</option>
                    {actionTypes.map((action) => (
                      <option key={action.value} value={action.value}>{action.label}</option>
                    ))}
                  </select>
                </div>

                {newWorkflow.actions.map((action) => (
                  <Card key={action.id} className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-4">
                      <div className="flex justify-between items-center">
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          {actionTypes.find((a) => a.value === action.type)?.label}
                        </p>
                        <div className="flex items-center space-x-2">
                          <Input
                            type="number"
                            value={action.delay || 0}
                            onChange={() => { }}
                            placeholder="Delay (min)"
                            className="w-24"
                          />
                          <Button size="sm" variant="outline" className="text-red-600"><Trash2 className="h-4 w-4" /></Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={handleCreateWorkflow}
                  disabled={!newWorkflow.name.trim()}
                  className="bg-blue-600 hover:bg-blue-700"
                >
                  Create Workflow
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Workflows List */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="active">Active Workflows</TabsTrigger>
          <TabsTrigger value="analytics">Workflow Analytics</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
        </TabsList>

        {/* Active Workflows Tab */}
        <TabsContent value="active" className="space-y-4 mt-6">
          {workflows.length === 0 ? (
            <Card className="bg-gray-50 dark:bg-gray-800">
              <CardContent className="pt-6">
                <div className="flex flex-col items-center space-y-4">
                  <Zap className="h-8 w-8 text-gray-400" />
                  <p className="text-center text-gray-600 dark:text-gray-400">
                    No workflows created yet. Create your first workflow to automate your processes.
                  </p>
                  <Button onClick={() => setIsCreating(true)} className="bg-blue-600 hover:bg-blue-700">
                    <Plus className="mr-2 h-4 w-4" />
                    Create Workflow
                  </Button>
                </div>
              </CardContent>
            </Card>
          ) : (
            workflows.map((workflow) => (
              <Card key={workflow.id}>
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex justify-between items-start">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <p className="font-semibold text-gray-900 dark:text-gray-100">{workflow.name}</p>
                          <Badge className={getStatusColorScheme(workflow.enabled)}>
                            {workflow.enabled ? "Active" : "Paused"}
                          </Badge>
                        </div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">{workflow.description}</p>
                      </div>
                      <div className="flex space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => onWorkflowToggle?.(workflow.id, !workflow.enabled)}
                        >
                          {workflow.enabled ? <Pause className="mr-1 h-4 w-4" /> : <Play className="mr-1 h-4 w-4" />}
                          {workflow.enabled ? "Pause" : "Resume"}
                        </Button>
                        <Button size="sm" variant="outline"><Edit className="mr-1 h-4 w-4" />Edit</Button>
                        <Button size="sm" variant="outline" className="text-red-600" onClick={() => onWorkflowDelete?.(workflow.id)}>
                          <Trash2 className="mr-1 h-4 w-4" />Delete
                        </Button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="flex items-center space-x-2">
                        <Zap className="h-4 w-4 text-blue-500" />
                        <div>
                          <p className="text-sm text-gray-600 dark:text-gray-400">Triggers</p>
                          <p className="font-medium text-gray-900 dark:text-gray-100">{workflow.triggers.length}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Play className="h-4 w-4 text-green-500" />
                        <div>
                          <p className="text-sm text-gray-600 dark:text-gray-400">Runs</p>
                          <p className="font-medium text-gray-900 dark:text-gray-100">{workflow.runs}</p>
                        </div>
                      </div>
                      <div className="flex items-center space-x-2">
                        <Target className="h-4 w-4 text-orange-500" />
                        <div>
                          <p className="text-sm text-gray-600 dark:text-gray-400">Success Rate</p>
                          <Badge className={getSuccessRateColorScheme(workflow.successRate)}>
                            {workflow.successRate}%
                          </Badge>
                        </div>
                      </div>
                    </div>

                    {workflow.lastRun && (
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Last run: {new Date(workflow.lastRun).toLocaleString()}
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="analytics" className="mt-6">
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100">Workflow Analytics</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <Card className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-6">
                      <div className="flex flex-col items-center space-y-2">
                        <p className="text-2xl font-bold text-blue-500">{workflows.length}</p>
                        <p className="text-sm text-gray-600 dark:text-gray-400 text-center">Total Workflows</p>
                      </div>
                    </CardContent>
                  </Card>
                  <Card className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-6">
                      <div className="flex flex-col items-center space-y-2">
                        <p className="text-2xl font-bold text-green-500">{workflows.filter((w) => w.enabled).length}</p>
                        <p className="text-sm text-gray-600 dark:text-gray-400 text-center">Active Workflows</p>
                      </div>
                    </CardContent>
                  </Card>
                  <Card className="bg-gray-50 dark:bg-gray-800">
                    <CardContent className="pt-6">
                      <div className="flex flex-col items-center space-y-2">
                        <p className="text-2xl font-bold text-orange-500">{workflows.reduce((sum, w) => sum + w.runs, 0)}</p>
                        <p className="text-sm text-gray-600 dark:text-gray-400 text-center">Total Executions</p>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Templates Tab */}
        <TabsContent value="templates" className="space-y-4 mt-6">
          <Alert variant="default" className="bg-blue-50 border-blue-200 dark:bg-blue-900/20 dark:border-blue-800">
            <Info className="h-4 w-4" />
            <AlertTitle>Workflow Templates</AlertTitle>
            <AlertDescription>
              Pre-built workflow templates to help you get started quickly.
            </AlertDescription>
          </Alert>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[
              { icon: Mail, title: "Welcome Sequence", desc: "Automatically send welcome emails to new contacts", color: "text-blue-500" },
              { icon: Target, title: "Lead Nurturing", desc: "Nurture leads with educational content and follow-ups", color: "text-green-500" },
              { icon: Users, title: "Re-engagement", desc: "Re-engage inactive contacts with targeted campaigns", color: "text-purple-500" },
              { icon: Clock, title: "Task Automation", desc: "Automatically create tasks for sales team follow-ups", color: "text-orange-500" },
            ].map((template, idx) => (
              <Card key={idx} className="bg-gray-50 dark:bg-gray-800 cursor-pointer hover:shadow-md transition-shadow">
                <CardContent className="pt-6">
                  <div className="space-y-3">
                    <div className="flex items-center space-x-2">
                      <template.icon className={`h-4 w-4 ${template.color}`} />
                      <p className="font-semibold text-gray-900 dark:text-gray-100">{template.title}</p>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-400">{template.desc}</p>
                    <Button size="sm" variant="outline" className="w-full">Use Template</Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default HubSpotWorkflowAutomation;
