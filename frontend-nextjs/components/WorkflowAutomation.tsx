import React, { useState, useEffect, useCallback, useRef } from 'react';
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
  History, // [Lesson 3]
  GitBranch, // [Lesson 3]
  Sparkles,
  Download,
} from "lucide-react";

interface WorkflowTemplate {
  id: string;
  template_id?: string; // For backend parity
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

// Node-based (graph) workflow shapes persisted by the v1 workflows API
// ({nodes, connections}); optional because step-based workflows omit them.
interface WorkflowNodeConnection {
  id: string;
  source: string;
  target: string;
  // The backend treats this as an optional, opaque string. It is not parsed or
  // converted into an event contract here.
  condition?: string;
}

interface WorkflowNodeDefinition {
  id: string;
  type: string;
  title?: string;
  description?: string;
  position?: { x: number; y: number };
  config?: Record<string, any>;
  connections?: WorkflowNodeConnection[];
}

// Persisted audit entries returned by the v1 workflow GET/PUT responses.
// The backend owns these values; the UI only renders them.
interface WorkflowCorrection {
  who?: string;
  when?: string;
  reason?: string;
  before_revision?: number | string;
  after_revision?: number | string;
}

interface WorkflowDefinition {
  id: string;
  name: string;
  description: string;
  version?: string;
  revision?: number | string;
  created_from_template?: string;
  steps: WorkflowStep[];
  input_schema: any;
  created_at: string;
  updated_at: string;
  steps_count?: number;
  nodes?: WorkflowNodeDefinition[];
  connections?: WorkflowNodeConnection[];
  // Persisted values are owned by the backend; keep them verbatim when an
  // existing graph is reused. Triggers are a string array, not event objects.
  triggers?: string[];
  enabled?: boolean;
  corrections?: WorkflowCorrection[];
}

const isRecord = (value: any): value is Record<string, any> =>
  value !== null && typeof value === 'object' && !Array.isArray(value);

// Normalize only the fields the workflow audit contract declares. Missing
// fields stay missing so the UI can show a neutral fallback instead of
// inventing sample history.
const normalizeWorkflowCorrections = (value: any): WorkflowCorrection[] => {
  if (!Array.isArray(value)) return [];
  return value.filter(isRecord).map((entry) => ({
    who: typeof entry.who === 'string' ? entry.who : undefined,
    when: typeof entry.when === 'string' ? entry.when : undefined,
    reason: typeof entry.reason === 'string' ? entry.reason : undefined,
    before_revision: entry.before_revision,
    after_revision: entry.after_revision,
  }));
};

// The contract field is `corrections`; accept the obvious history aliases so a
// persisted audit payload is not silently dropped if the server names the
// collection differently. An absent collection stays undefined so callers can
// distinguish "not returned" from "returned empty".
const getPersistedWorkflowCorrections = (
  data: any
): WorkflowCorrection[] | undefined => {
  if (!isRecord(data)) return undefined;
  const candidates = [
    data.corrections,
    data.correction_history,
    data.change_history,
  ];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) {
      return normalizeWorkflowCorrections(candidate);
    }
  }
  return undefined;
};

const formatCorrectionValue = (
  value: number | string | undefined
): string =>
  value === undefined || value === null || value === ''
    ? 'Unknown'
    : String(value);

// Builder node data is intentionally flat (label/service/action plus the
// action's parameter values), but older/other callers may also supply a nested
// `parameters` bag and/or a `config` object edited by NodeConfigSidebar.
const BUILDER_DATA_META_KEYS = new Set([
  'id',
  'label',
  'description',
  'service',
  'serviceId',
  'action',
  'config',
  'parameters',
  '_workflowId',
  '_analytics',
]);

// The execution engine reads these at the config root (not as action inputs),
// so they must survive a builder round-trip without being folded into
// `parameters`.
const ROOT_CONFIG_META_KEYS = new Set([
  'continue_on_error',
  'timeout',
  'input_schema',
  'output_schema',
]);

const mergeParameterRecords = (
  ...sources: Array<Record<string, any> | undefined>
): Record<string, any> => {
  const merged: Record<string, any> = {};
  sources.forEach((source) => {
    if (!isRecord(source)) return;
    Object.keys(source).forEach((key) => {
      if (source[key] !== undefined) merged[key] = source[key];
    });
  });
  return merged;
};

const getBuilderNodeParameters = (data: any): Record<string, any> => {
  if (!isRecord(data)) return {};

  const flat: Record<string, any> = {};
  Object.keys(data).forEach((key) => {
    if (
      !BUILDER_DATA_META_KEYS.has(key) &&
      !ROOT_CONFIG_META_KEYS.has(key) &&
      data[key] !== undefined
    ) {
      flat[key] = data[key];
    }
  });

  const explicitParameters = isRecord(data.parameters) ? data.parameters : {};
  const nestedConfig = isRecord(data.config) ? data.config : {};
  const nestedParameters = isRecord(nestedConfig.parameters)
    ? nestedConfig.parameters
    : {};
  const configFields: Record<string, any> = {};
  Object.keys(nestedConfig).forEach((key) => {
    if (
      key !== 'parameters' &&
      key !== 'service' &&
      key !== 'action' &&
      key !== 'description' &&
      !ROOT_CONFIG_META_KEYS.has(key)
    ) {
      configFields[key] = nestedConfig[key];
    }
  });

  // The nested config (edited most recently by the sidebar) wins over any
  // stale flat copies left on the node.
  return mergeParameterRecords(flat, explicitParameters, nestedParameters, configFields);
};

const getBuilderNodeService = (data: any): any =>
  isRecord(data?.config) && data.config.service !== undefined
    ? data.config.service
    : data?.service;

const getBuilderNodeAction = (data: any): any =>
  isRecord(data?.config) && data.config.action !== undefined
    ? data.config.action
    : data?.action;

const getBuilderNodeDescription = (data: any): string =>
  data?.description ??
  (isRecord(data?.config) ? data.config.description : undefined) ??
  '';

const getBuilderNodeRootConfig = (data: any): Record<string, any> => {
  if (!isRecord(data)) return {};
  const nestedConfig = isRecord(data.config) ? data.config : {};
  const rootConfig: Record<string, any> = {};
  ROOT_CONFIG_META_KEYS.forEach((key) => {
    if (nestedConfig[key] !== undefined) {
      rootConfig[key] = nestedConfig[key];
    } else if (data[key] !== undefined) {
      rootConfig[key] = data[key];
    }
  });
  return rootConfig;
};

const builderNodeToSavedConfig = (data: any): Record<string, any> => {
  const service = getBuilderNodeService(data);
  const action = getBuilderNodeAction(data);
  return {
    ...(service !== undefined ? { service } : {}),
    ...(action !== undefined ? { action } : {}),
    ...getBuilderNodeRootConfig(data),
    parameters: getBuilderNodeParameters(data),
  };
};

const savedNodeToBuilderNode = (node: WorkflowNodeDefinition): any => {
  const config = isRecord(node.config) ? node.config : {};
  const nestedParameters = isRecord(config.parameters) ? config.parameters : {};
  const flatParameters: Record<string, any> = {};
  Object.keys(config).forEach((key) => {
    if (key !== 'parameters' && key !== 'service' && key !== 'action' && key !== 'description') {
      flatParameters[key] = config[key];
    }
  });

  const service = config.service ?? nestedParameters.service;
  const action = config.action ?? nestedParameters.action;
  const description = node.description ?? config.description ?? '';

  return {
    id: node.id,
    type: node.type,
    position: node.position || { x: 250, y: 0 },
    data: {
      ...mergeParameterRecords(nestedParameters, flatParameters),
      label: node.title ?? node.id,
      description,
      ...(service !== undefined ? { service } : {}),
      ...(action !== undefined ? { action } : {}),
    },
  };
};

const savedConnectionToBuilderEdge = (connection: WorkflowNodeConnection): any => {
  const edge: any = {
    id: connection.id,
    source: connection.source,
    target: connection.target,
    type: 'addStepEdge',
  };

  const originalData = isRecord((connection as any).data)
    ? (connection as any).data
    : undefined;
  const condition =
    typeof connection.condition === 'string'
      ? connection.condition
      : typeof originalData?.condition === 'string'
        ? originalData.condition
        : undefined;

  if (originalData || condition !== undefined) {
    edge.data = {
      ...(originalData || {}),
      ...(condition !== undefined ? { condition } : {}),
    };
  }
  return edge;
};

const builderEdgeToSavedConnection = (edge: any): WorkflowNodeConnection => {
  const connection: WorkflowNodeConnection = {
    id: edge.id,
    source: edge.source,
    target: edge.target,
  };
  const condition =
    typeof edge?.data?.condition === 'string'
      ? edge.data.condition
      : typeof edge?.condition === 'string'
        ? edge.condition
        : undefined;

  if (condition !== undefined) connection.condition = condition;
  return connection;
};

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
import { extractApiErrorMessage } from "@/lib/api-error";


const WorkflowAutomation: React.FC<{ triggerNew?: number }> = ({ triggerNew }) => {
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
  const [exportingExecution, setExportingExecution] = useState(false);
  const [exportExecutionError, setExportExecutionError] = useState<string | null>(null);

  const [builderInitialData, setBuilderInitialData] = useState<any>(null); // For AI generated workflows
  const [genPrompt, setGenPrompt] = useState("");
  // Same-ID editing is explicit: a workflow opened with the card Edit action is
  // updated in place, while fresh/AI/template/Run-to-builder paths stay creates.
  const [editingWorkflowId, setEditingWorkflowId] = useState<string | null>(null);
  const [editingRevision, setEditingRevision] = useState<number | string | null>(null);
  const [changeHistory, setChangeHistory] = useState<WorkflowCorrection[]>([]);
  const [savingWorkflow, setSavingWorkflow] = useState(false);
  const [builderSaveError, setBuilderSaveError] = useState<string | null>(null);
  const [builderSaveConflict, setBuilderSaveConflict] = useState(false);
  const [builderLoadKey, setBuilderLoadKey] = useState(0);
  const saveInFlightRef = useRef(false);
  const editSessionRef = useRef(0);

  // [Lesson 3] Time-Travel State
  const [isForkModalOpen, setIsForkModalOpen] = useState(false);
  const [forkStepId, setForkStepId] = useState<string | null>(null);
  const [forkVariables, setForkVariables] = useState<Record<string, any>>({});
  // [Lesson 3] UX: Raw string state for editable text area
  const [forkVariablesJson, setForkVariablesJson] = useState<string>("{}");
  const { toast } = useToast();

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

      editSessionRef.current += 1;
      setEditingWorkflowId(null);
      setEditingRevision(null);
      setChangeHistory([]);
      setBuilderSaveError(null);
      setBuilderSaveConflict(false);
      setBuilderInitialData({ nodes: generatedNodes, edges: generatedEdges });
      setViewMode("builder");
      toast({ title: "Workflow Generated", description: "AI created a draft workflow based on your prompt." });
      setLoading(false);
      setGenPrompt("");
    }, 1000);
  };

  const fetchTemplates = useCallback(async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const response = await fetch("/api/workflow-templates/", {
        headers: {
          ...(token ? { 'Authorization': `Bearer ${token}` } : {})
        }
      }); // Fixed endpoint with trailing slash
      if (response.ok) {
        const data = await response.json();
        // The API returns the list directly, not { success: true, templates: ... }
        // Also map template_id -> id for frontend compatibility
        const mapped = Array.isArray(data) ? data.map((t: any) => ({
          ...t,
          id: t.template_id
        })) : [];
        setTemplates(mapped);
      }
    } catch (e) {
      console.error("Failed to fetch templates", e);
    }
  }, []);

  const fetchWorkflows = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/workflows/workflows");
      const data = await response.json();
      // The v1 endpoint returns List[WorkflowDefinition] directly (not {success, workflows}).
      setWorkflows(Array.isArray(data) ? data : (data.workflows || []));
    } catch (e) {
      console.error("Failed to fetch workflows", e);
    }
  }, []);

  const fetchExecutions = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/workflow-ui/executions");
      const data = await response.json();
      if (data.success) {
        setExecutions(data.executions);
      }
    } catch (e) {
      console.error("Failed to fetch executions", e);
    }
  }, []);

  const fetchServices = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/workflow-ui/services");
      const data = await response.json();
      if (data.success) {
        setServices(data.services);
      }
    } catch (e) {
      console.error("Failed to fetch services", e);
    }

  }, []);

  const fetchWorkflowData = useCallback(async () => {
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
  }, [fetchTemplates, fetchWorkflows, fetchExecutions, fetchServices, toast]);

  const router = useRouter();
  const routerRef = useRef(router);
  routerRef.current = router;
  const draft = router.query.draft;

  useEffect(() => {
    fetchWorkflowData();
  }, [fetchWorkflowData]);

  useEffect(() => {
    if (triggerNew && triggerNew > 0) {
      editSessionRef.current += 1;
      setEditingWorkflowId(null);
      setEditingRevision(null);
      setChangeHistory([]);
      setBuilderSaveError(null);
      setBuilderSaveConflict(false);
      setBuilderInitialData(null);
      setSelectedWorkflow(null);
      setViewMode('builder');
    }
  }, [triggerNew]);

  useEffect(() => {
    if (draft) {
      try {
        const draftData = JSON.parse(draft as string);
        editSessionRef.current += 1;
        setEditingWorkflowId(null);
        setEditingRevision(null);
        setChangeHistory([]);
        setBuilderSaveError(null);
        setBuilderSaveConflict(false);
        setBuilderInitialData(draftData);
        setViewMode("builder");
        toast({ title: "Draft Loaded", description: "Loaded workflow from chat." });
        // Clean URL
        routerRef.current.replace('/automation', undefined, { shallow: true });
      } catch (e) {
        console.error("Failed to parse draft", e);
      }
    }
  }, [draft, toast]);

  useEffect(() => {
    const hasRunning = executions.some(e => e.status === 'running');
    if (isExecutionModalOpen || hasRunning) {
      const interval = setInterval(fetchExecutions, 2000);
      return () => clearInterval(interval);
    }
  }, [isExecutionModalOpen, executions, fetchExecutions]);

  useEffect(() => {
    if (activeExecution) {
      const updated = executions.find(e => e.execution_id === activeExecution.execution_id);
      if (updated && JSON.stringify(updated) !== JSON.stringify(activeExecution)) {
        setActiveExecution(updated);
      }
    }
  }, [activeExecution, executions]);

  const handleBuilderSave = async (
    builderData: { nodes: any[]; edges: any[] },
    saveOptions?: { reason?: string } | string
  ) => {
    // A pending save must not be duplicated by a second click or a second
    // callback from the canvas.
    if (saveInFlightRef.current) return;
    saveInFlightRef.current = true;

    const editSession = editSessionRef.current;
    const isSameIdEdit = Boolean(editingWorkflowId);
    const requestId = editingWorkflowId;
    const requestRevision = editingRevision;
    const reason =
      (typeof saveOptions === 'string'
        ? saveOptions
        : saveOptions?.reason || ''
      ).trim() || 'Updated via Visual Builder';

    try {
      setSavingWorkflow(true);
      setBuilderSaveError(null);
      setBuilderSaveConflict(false);
      const generatedName = `Visual Workflow ${new Date().toLocaleTimeString()}`;

      // Persist to the REAL workflow store. Existing visual workflows loaded
      // from the card Edit action are updated in place with PUT on that exact
      // resource (optimistic revision); fresh/AI/template/Run-to-builder paths
      // keep using the create endpoint.
      const token = localStorage.getItem('auth_token');
      const nodes = (builderData.nodes || []).map((n: any) => ({
        id: n.id,
        type: n.type,
        title: n.data?.label || n.id,
        description: getBuilderNodeDescription(n.data),
        position: n.position || { x: 0, y: 0 },
        config: builderNodeToSavedConfig(n.data),
        connections: [] as WorkflowNodeConnection[],
      }));
      const connections = (builderData.edges || []).map(builderEdgeToSavedConnection);

      // A reused graph is passed through `initialData` from `selectedWorkflow`
      // (without a separate draft). In that case preserve the persisted
      // workflow settings exactly; a fresh canvas keeps the safe defaults.
      const reusingSavedGraph = Boolean(selectedWorkflow) && !builderInitialData;
      const savedTriggers =
        reusingSavedGraph && Array.isArray(selectedWorkflow?.triggers)
          ? selectedWorkflow!.triggers
          : [];
      const savedEnabled =
        reusingSavedGraph && typeof selectedWorkflow?.enabled === 'boolean'
          ? selectedWorkflow!.enabled
          : true;
      const savedName = isSameIdEdit
        ? selectedWorkflow?.name || generatedName
        : generatedName;
      const savedDescription = isSameIdEdit
        ? selectedWorkflow?.description || ''
        : "Created via Visual Builder";
      const savedVersion = isSameIdEdit
        ? selectedWorkflow?.version || "1.0"
        : "1.0";

      const payload: Record<string, any> = {
        ...(isSameIdEdit
          ? { revision: requestRevision, reason }
          : {}),
        name: savedName,
        description: savedDescription,
        version: savedVersion,
        nodes,
        connections,
        triggers: savedTriggers,
        enabled: savedEnabled,
      };

      const url = isSameIdEdit
        ? `/api/v1/workflows/workflows/${encodeURIComponent(requestId!)}`
        : "/api/v1/workflows/workflows";
      const response = await fetch(url, {
        method: isSameIdEdit ? "PUT" : "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));

      // Do not let a late response from an older edit session replace the
      // workflow the user is currently editing.
      if (isSameIdEdit && editSession !== editSessionRef.current) return;

      if (isSameIdEdit && response.status === 409) {
        // Keep the builder and its unsaved local graph mounted; the user must
        // explicitly reload the newer persisted revision before retrying.
        setBuilderSaveError(
          "This workflow changed elsewhere. Your local changes are still here."
        );
        setBuilderSaveConflict(true);
        toast({
          title: "Reload required",
          description:
            "This workflow changed elsewhere. Reload the latest version before saving again.",
          variant: "error",
        });
        return;
      }

      if (!response.ok) {
        throw new Error(extractApiErrorMessage(data, "Failed to save", response.status));
      }

      const savedId = isSameIdEdit ? data.id || requestId : data.id;
      if (savedId) {
        const nextRevision =
          data.revision !== undefined ? data.revision : requestRevision;
        const responseCorrections = getPersistedWorkflowCorrections(data);
        const persistedCorrections =
          responseCorrections ?? selectedWorkflow?.corrections;
        if (isSameIdEdit) {
          setEditingWorkflowId(savedId);
          setEditingRevision(nextRevision);
        }
        // The PUT response carries the authoritative persisted corrections.
        // Only replace the visible history when the server actually returned
        // them; a missing field must not erase real audit data.
        if (responseCorrections !== undefined) {
          setChangeHistory(responseCorrections);
        }

        toast({
          title: isSameIdEdit ? "Workflow Updated" : "Workflow Saved",
          description: isSameIdEdit
            ? "Your workflow changes have been saved."
            : "Your visual workflow has been saved to the database.",
        });

        if (isSameIdEdit) {
          // Refresh the list without unmounting the builder. The local save is
          // already authoritative, so it does not need to wait for the list.
          void fetchWorkflows();
        } else {
          await fetchWorkflowData(); // Refresh list — now includes the new workflow
        }

        // Update current selected workflow so builder has the ID, revision and
        // graph/settings needed for a subsequent round-trip save.
        const responseNodes = Array.isArray(data.nodes) ? data.nodes : nodes;
        const responseConnections = Array.isArray(data.connections)
          ? data.connections
          : connections;
        const newWorkflow = {
          ...(selectedWorkflow || {}),
          id: savedId,
          name: data.name || savedName,
          description: data.description || savedDescription,
          version: data.version || savedVersion,
          revision: isSameIdEdit ? nextRevision : data.revision,
          steps: nodes.map((n: any) => ({
            id: n.id,
            name: n.title,
            type: n.type,
            service: n.config?.service,
            action: n.config?.action,
            parameters: n.config,
          })),
          input_schema: selectedWorkflow?.input_schema || {},
          created_at: selectedWorkflow?.created_at || new Date().toISOString(),
          updated_at: data.updated_at || new Date().toISOString(),
          nodes: responseNodes,
          connections: responseConnections,
          // The values we just sent are the persisted values; only accept a
          // response field when it is actually present.
          triggers: Array.isArray(data.triggers) ? data.triggers : savedTriggers,
          enabled:
            typeof data.enabled === 'boolean' ? data.enabled : savedEnabled,
          corrections: persistedCorrections,
        };
        setSelectedWorkflow(newWorkflow as WorkflowDefinition);
      } else {
        throw new Error(extractApiErrorMessage(data, "Failed to save"));
      }
    } catch (e) {
      console.error("Save error", e);
      toast({ title: "Error", description: "Failed to save workflow", variant: "error" });
    } finally {
      saveInFlightRef.current = false;
      setSavingWorkflow(false);
    }
  };

  const handleTemplateSelect = (template: WorkflowTemplate) => {
    setSelectedTemplate(template);
    setFormData({});
    setIsTemplateModalOpen(true);
  };

  const loadWorkflowForEditing = async (
    workflow: WorkflowDefinition
  ): Promise<WorkflowDefinition> => {
    const token = localStorage.getItem('auth_token');
    const response = await fetch(
      `/api/v1/workflows/workflows/${encodeURIComponent(workflow.id)}`,
      {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }
    );
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(
        extractApiErrorMessage(data, "Failed to load workflow", response.status)
      );
    }

    const persistedCorrections = getPersistedWorkflowCorrections(data);
    const loadedCorrections =
      persistedCorrections ??
      normalizeWorkflowCorrections(workflow.corrections);
    const loaded: WorkflowDefinition = {
      ...workflow,
      ...data,
      id: data.id || workflow.id,
      revision: data.revision ?? workflow.revision,
      corrections: loadedCorrections,
    };
    editSessionRef.current += 1;
    setBuilderInitialData(null);
    setSelectedWorkflow(loaded);
    setEditingWorkflowId(loaded.id);
    setEditingRevision(loaded.revision ?? null);
    setChangeHistory(loadedCorrections);
    setBuilderSaveError(null);
    setBuilderSaveConflict(false);
    setBuilderLoadKey((key) => key + 1);
    setViewMode("builder");
    return loaded;
  };

  const handleWorkflowEdit = async (workflow: WorkflowDefinition) => {
    // Step-based / template-derived workflows keep the canonical route editor.
    // Ordinary node-based (visual) workflows edit in place with the same ID.
    if (!Array.isArray(workflow.nodes) || workflow.created_from_template) {
      router.push(`/workflows/editor/${workflow.created_from_template || workflow.id}`);
      return;
    }

    // Invalidate any save still in flight for a previous edit session.
    editSessionRef.current += 1;
    try {
      setLoading(true);
      await loadWorkflowForEditing(workflow);
    } catch (error) {
      console.error("Failed to load workflow for editing", error);
      toast({
        title: "Error",
        description: "Failed to load workflow",
        variant: "error",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleReloadWorkflowEdit = async () => {
    if (!editingWorkflowId) return;
    // Invalidate any save still in flight before replacing the local graph.
    editSessionRef.current += 1;
    const base =
      selectedWorkflow ||
      ({
        id: editingWorkflowId,
        name: "",
        description: "",
        steps: [],
        input_schema: {},
        created_at: "",
        updated_at: "",
      } as WorkflowDefinition);

    try {
      setSavingWorkflow(true);
      await loadWorkflowForEditing(base);
    } catch (error) {
      console.error("Failed to reload workflow", error);
      toast({
        title: "Error",
        description: "Failed to reload workflow",
        variant: "error",
      });
    } finally {
      setSavingWorkflow(false);
    }
  };

  const handleWorkflowSelect = (workflow: WorkflowDefinition) => {
    editSessionRef.current += 1;
    setEditingWorkflowId(null);
    setEditingRevision(null);
    setChangeHistory([]);
    setBuilderSaveError(null);
    setBuilderSaveConflict(false);
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
      const token = localStorage.getItem('auth_token');
      const response = await fetch(
        `/api/v1/workflows/workflows/${workflowId}/execute`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(inputData),
        }
      );

      const data = await response.json();
      if (data.execution_id) {
        const status = String(data.status || "");
        const titles: Record<string, string> = {
          waiting_approval: "Waiting for Approval",
          completed: "Workflow Completed",
          failed: "Workflow Failed",
          running: "Workflow Started",
        };
        toast({
          title: titles[status] || "Execution Recorded",
          description: status === "waiting_approval"
            ? `Execution ${data.execution_id} is waiting for approval; no later step ran.`
            : `Execution ${data.execution_id} — status: ${status || "unknown"}`,
        });

        // Refresh executions list
        await fetchExecutions();

        // Show execution details
        setActiveExecution(data);
        setIsExecutionModalOpen(true);
      } else {
        throw new Error(extractApiErrorMessage(data, "Failed to execute workflow", response.status));
      }
    } catch (error) {
      console.error("Error executing workflow:", error);
      toast({
        title: "Error",
        description: error instanceof Error ? error.message : "Failed to execute workflow",
        variant: "error",
      });
    } finally {
      setExecuting(false);
    }
  };

  const handleExportExecution = async () => {
    if (!activeExecution || exportingExecution) return;
    const executionId = activeExecution.execution_id;
    setExportExecutionError(null);
    setExportingExecution(true);
    try {
      const token = localStorage.getItem("auth_token");
      const response = await fetch(
        `/api/v1/workflows/workflows/executions/${encodeURIComponent(executionId)}/export`,
        {
          method: "GET",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      );
      if (!response.ok) {
        let message = `Export failed (HTTP ${response.status})`;
        try {
          const data = await response.json();
          const detail = data?.detail;
          if (detail && typeof detail === 'object') {
            message = detail.message || detail.error || message;
          } else {
            message = extractApiErrorMessage(data, message, response.status);
          }
        } catch {
          // non-JSON refusal
        }
        setExportExecutionError(message);
        return;
      }
      const blob = await response.blob();
      const disposition = response.headers.get("content-disposition") || "";
      const match = /filename="?([^";]+)"?/i.exec(disposition);
      const fallback = `workflow-${String(activeExecution.workflow_id || "workflow").replace(/[^A-Za-z0-9_-]+/g, "-").slice(0, 48)}-execution-${String(executionId).replace(/[^A-Za-z0-9_-]+/g, "-").slice(0, 48)}.json`;
      const filename = (match?.[1] || fallback)
        .replace(/[\\/:*?"<>|\r\n]+/g, "_")
        .slice(0, 160);
      const url = window.URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = url;
      link.download = filename;
      link.rel = "noopener";
      window.document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast({
        title: "Results downloaded",
        description: filename,
      });
    } catch (error) {
      setExportExecutionError(
        error instanceof Error
          ? error.message
          : "The execution result could not be downloaded. Refresh and retry."
      );
    } finally {
      setExportingExecution(false);
    }
  };

  const handleCancelExecution = async (executionId: string) => {
    try {
      const response = await fetch(
        `/api/v1/workflow-ui/executions/${executionId}/cancel`,
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
        throw new Error(extractApiErrorMessage(data, "Failed to cancel execution", response.status));
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
        `/api/v1/workflows/workflows/${executionId}/resume`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(inputs),
        }
      );

      const data = await response.json();
      if (data.status === "resumed") {
        toast({
          title: "Execution Resumed",
          description: `Execution ${executionId} has been resumed`,
        });
        await fetchExecutions();
        setIsResumeModalOpen(false);
        setResumeExecutionId(null);
      } else {
        throw new Error(extractApiErrorMessage(data, "Failed to resume execution", response.status));
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

  // [Lesson 3] Time-Travel / Fork Handler
  const handleForkWorkflow = async (stepId?: string, variables?: Record<string, any>) => {
    const targetStepId = stepId || forkStepId;
    const targetVariables = variables || forkVariables;

    if (!activeExecution || !targetStepId) return;

    try {
      setExecuting(true);
      const token = localStorage.getItem('auth_token');
      const response = await fetch(
        `/api/time-travel/workflows/${activeExecution.execution_id}/fork`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            step_id: targetStepId,
            new_variables: targetVariables
          }),
        }
      );

      const data = await response.json();
      if (response.ok) {
        toast({
          title: "Timeline Forked! 🌌",
          description: `Created parallel universe: ${data.new_execution_id}`,
        });
        await fetchExecutions(); // Refresh list
        setIsForkModalOpen(false);
        setIsExecutionModalOpen(false); // Close details
      } else {
        throw new Error(extractApiErrorMessage(data, "Fork failed", response.status));
      }
    } catch (error) {
      console.error("Fork Error:", error);
      toast({
        title: "Time-Travel Failed",
        description: "Could not fork timeline.",
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
        return <Settings className={`${iconClass} text-gray-500 dark:text-gray-400`} />;
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
                <p className="text-sm text-gray-500 dark:text-gray-400">
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
                <p className="text-sm text-gray-500 dark:text-gray-400">
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
            <p className="text-sm text-gray-500 dark:text-gray-400">
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
        <p className="text-gray-600 dark:text-gray-400">Loading workflow automation...</p>
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
          <p className="text-gray-500 dark:text-gray-400">
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
          <Button
            onClick={() => {
              // "Create Workflow" starts a NEW workflow in the Visual Builder
              // (fresh canvas). Previously it opened the Execute-Workflow modal
              // with selectedWorkflow=null, rendering "Execute Workflow:
              // undefined" with a dead Execute button.
              editSessionRef.current += 1;
              setEditingWorkflowId(null);
              setEditingRevision(null);
              setChangeHistory([]);
              setBuilderSaveError(null);
              setBuilderSaveConflict(false);
              setBuilderInitialData(null);
              setSelectedWorkflow(null);
              setViewMode('builder');
            }}
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Workflow
          </Button>
        </div>
      </div>

      {viewMode === "builder" ? (
        <div className="space-y-4">
          {builderSaveError && (
            <Alert variant="destructive" data-testid="builder-save-error">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Reload required</AlertTitle>
              <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
                <span>{builderSaveError}</span>
                {builderSaveConflict && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleReloadWorkflowEdit}
                    disabled={savingWorkflow}
                  >
                    Reload latest
                  </Button>
                )}
              </AlertDescription>
            </Alert>
          )}
          <WorkflowBuilder
            key={editingWorkflowId ? `${editingWorkflowId}:${builderLoadKey}` : undefined}
            initialData={builderInitialData || (selectedWorkflow ? {
              // Node-based (graph) workflows persist `nodes`/`connections`; pass
              // them straight through so the original graph, positions, node
              // config/description and connection condition survive. Both flat
              // and nested (`config.parameters`) config forms are accepted.
              // Step-based workflows are linearized into builder nodes/edges.
              nodes: selectedWorkflow.nodes?.length
                ? selectedWorkflow.nodes.map(savedNodeToBuilderNode)
                : (selectedWorkflow.steps || []).map((s, i) => ({
                    id: s.id,
                    type: s.type === 'trigger' ? 'trigger' : 'action',
                    position: { x: 250, y: i * 200 + 50 },
                    data: {
                      label: s.name,
                      service: s.service || 'system',
                      action: s.action || 'execute',
                      ...s.parameters
                    }
                  })),
              edges: selectedWorkflow.nodes?.length
                ? (selectedWorkflow.connections || []).map(savedConnectionToBuilderEdge)
                : (selectedWorkflow.steps || []).slice(0, -1).map((s, i) => ({
                    id: `e${s.id}-${selectedWorkflow.steps[i + 1].id}`,
                    source: s.id,
                    target: selectedWorkflow.steps[i + 1].id,
                    type: 'addStepEdge'
                  }))
            } : undefined)}
            workflowId={selectedWorkflow?.id || selectedTemplate?.id}
            saving={savingWorkflow}
            onSave={handleBuilderSave}
          />
          {editingWorkflowId && (
            <details
              data-testid="workflow-change-history"
              className="rounded-lg border bg-white p-4 dark:bg-gray-900"
            >
              <summary
                aria-label="Change history"
                className="cursor-pointer text-sm font-semibold"
              >
                <span>Change history</span>
              </summary>
              <div className="mt-4 space-y-4">
                {changeHistory.length === 0 ? (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    No saved changes recorded for this workflow yet.
                  </p>
                ) : (
                  changeHistory.map((correction, index) => (
                    <div
                      key={`${String(correction.after_revision ?? 'revision')}-${index}`}
                      className="border-t pt-3 first:border-t-0 first:pt-0"
                    >
                      <dl className="grid grid-cols-1 gap-x-4 gap-y-2 text-sm sm:grid-cols-[7rem_1fr]">
                        <dt className="font-medium text-gray-500 dark:text-gray-400">
                          Reason
                        </dt>
                        <dd>{correction.reason || 'No reason provided'}</dd>

                        <dt className="font-medium text-gray-500 dark:text-gray-400">
                          Actor
                        </dt>
                        <dd>{correction.who || 'Unknown actor'}</dd>

                        <dt className="font-medium text-gray-500 dark:text-gray-400">
                          Time
                        </dt>
                        <dd>
                          {correction.when ? (
                            <time dateTime={correction.when}>
                              {correction.when}
                            </time>
                          ) : (
                            'Unknown time'
                          )}
                        </dd>

                        <dt className="font-medium text-gray-500 dark:text-gray-400">
                          Revisions
                        </dt>
                        <dd>
                          <span className="sr-only">
                            Before revision{' '}
                            {formatCorrectionValue(correction.before_revision)},
                            after revision{' '}
                            {formatCorrectionValue(correction.after_revision)}.
                          </span>
                          <span aria-hidden="true">
                            {formatCorrectionValue(correction.before_revision)}{' '}
                            &rarr;{' '}
                            {formatCorrectionValue(correction.after_revision)}
                          </span>
                        </dd>
                      </dl>
                    </div>
                  ))
                )}
              </div>
            </details>
          )}
        </div>
      ) : (
        /* Main Content */
        <>
          <form
            onSubmit={handleGenerativeCreate}
            className="mb-6 flex items-center space-x-2"
          >
            <Input
              value={genPrompt}
              onChange={(e) => setGenPrompt(e.target.value)}
              placeholder="Describe a workflow to generate with AI (e.g. send a daily digest)"
              aria-label="AI workflow prompt"
            />
            <Button type="submit" disabled={loading || executing}>
              <Sparkles className="w-4 h-4 mr-2" />
              Generate with AI
            </Button>
          </form>
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
                      {(template.steps || []).slice(0, 3).map((step, index) => (
                        <div key={step.id || index} className="flex items-center text-sm">
                          <Badge
                            variant="outline"
                            className="mr-2 w-5 h-5 flex items-center justify-center p-0"
                          >
                            {index + 1}
                          </Badge>
                          <span className="truncate">{step.name}</span>
                        </div>
                      ))}
                      {(template.steps || []).length > 3 && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 pl-7">
                          +{(template.steps || []).length - 3} more steps
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
                    <Button
                      variant="outline"
                      className="w-full mt-2"
                      onClick={() => router.push(`/workflows/editor/${template.template_id}`)}
                    >
                      <Edit className="w-4 h-4 mr-2" />
                      Edit in Builder
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
                          {workflow.steps_count ||
                            workflow.steps?.length ||
                            workflow.nodes?.length ||
                            0}{" "}
                          steps
                        </Badge>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label="Edit workflow"
                          title={`Edit ${workflow.name}`}
                          onClick={() => handleWorkflowEdit(workflow)}
                        >
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
                    <p className="text-xs text-gray-500 dark:text-gray-400">
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
                            {/* [Lesson 3] UX: Visual indicator for forked workflows */}
                            {
                              execution.execution_id.includes("-forked-") && (
                                <span className="text-xs text-purple-500 ml-1 font-normal">
                                  (forked)
                                </span>
                              )
                            }
                          </span >
                        </div >
                        <div className="text-sm text-gray-500 dark:text-gray-400 space-y-1">
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
                      </div >

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
                    </div >
                  </CardContent >
                </Card >
              ))}
              {
                executions.length === 0 && (
                  <Alert>
                    <Activity className="h-4 w-4" />
                    <AlertTitle>No executions yet</AlertTitle>
                    <AlertDescription>
                      Execute a workflow to see execution history here.
                    </AlertDescription>
                  </Alert>
                )
              }
            </div >
          </TabsContent >

          {/* Services Tab */}
          < TabsContent value="services" className="mt-6" >
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
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 min-h-[40px]">
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
                          <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center">
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
          </TabsContent >
        </Tabs >
        </>
      )}

      {/* Template Execution Modal */}
      <Dialog open={isTemplateModalOpen} onOpenChange={setIsTemplateModalOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Use Template: {selectedTemplate?.name}</DialogTitle>
          </DialogHeader>
          {selectedTemplate && (
            <div className="space-y-6">
              <p className="text-gray-600 dark:text-gray-400">{selectedTemplate.description}</p>

              <div className="space-y-2">
                <h3 className="font-semibold">Workflow Steps:</h3>
                <div className="space-y-2 pl-2 border-l-2 border-gray-200 dark:border-gray-700">
                  {selectedTemplate.steps.map((step, index) => (
                    <div key={step.id} className="flex items-start space-x-3">
                      <Badge variant="outline" className="mt-0.5">
                        {index + 1}
                      </Badge>
                      <div>
                        <p className="font-medium text-sm">{step.name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
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
              <p className="text-gray-600 dark:text-gray-400">{selectedWorkflow.description}</p>

              <div className="space-y-2">
                <h3 className="font-semibold">Workflow Steps:</h3>
                <div className="space-y-2 pl-2 border-l-2 border-gray-200 dark:border-gray-700">
                  {selectedWorkflow.steps?.map((step, index) => (
                    <div key={step.id} className="flex items-start space-x-3">
                      <Badge variant="outline" className="mt-0.5">
                        {index + 1}
                      </Badge>
                      <div>
                        <p className="font-medium text-sm">{step.name}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
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
              <p className="text-xs text-gray-500 dark:text-gray-400">
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
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Workflow: {activeExecution.workflow_id}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={handleExportExecution}
                    disabled={
                      exportingExecution ||
                      String(activeExecution.status || "").toLowerCase() !== "completed"
                    }
                    title={
                      String(activeExecution.status || "").toLowerCase() === "completed"
                        ? "Download the completed execution results as JSON"
                        : "Only a completed execution has downloadable results"
                    }
                  >
                    {exportingExecution ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Download className="w-4 h-4 mr-2" />
                    )}
                    Download results
                  </Button>
                  <Badge className={getStatusColor(activeExecution.status)}>
                    {activeExecution.status}
                  </Badge>
                </div>
              </div>

              {exportExecutionError && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertTitle>Download unavailable</AlertTitle>
                  <AlertDescription>{exportExecutionError}</AlertDescription>
                </Alert>
              )}

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500 dark:text-gray-400">Started:</span>{" "}
                  {new Date(activeExecution.start_time).toLocaleString()}
                </div>
                {activeExecution.end_time && (
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Ended:</span>{" "}
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
                              <div className="flex justify-between items-center mb-2">
                                <span className="font-semibold text-xs text-gray-500 dark:text-gray-400">
                                  Captured State
                                </span>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="h-6 text-xs bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100"
                                  onClick={() => {
                                    setForkStepId(stepId);
                                    // [Lesson 3] UX Enhancement: Pre-fill with existing data so user can edit
                                    // [Lesson 4] Safe Mode: Strip system keys to prevent accidents
                                    const systemKeys = ['status', 'error', 'timestamp', 'execution_time_ms', 'step_id', 'step_type', 'notes', 'requires_confirmation'];
                                    const safeVariables = { ...result };
                                    systemKeys.forEach(key => delete safeVariables[key]);

                                    setForkVariables(safeVariables);
                                    setForkVariablesJson(JSON.stringify(safeVariables, null, 2));
                                    setIsForkModalOpen(true);
                                  }}
                                >
                                  <GitBranch className="w-3 h-3 mr-1" />
                                  Fork & Time Travel
                                </Button>
                              </div>
                              <pre className="bg-gray-100 dark:bg-gray-800 p-4 rounded-md overflow-x-auto text-xs">
                                {JSON.stringify(result, null, 2)}
                              </pre>
                            </AccordionContent >
                          </AccordionItem >
                        ),
                      )}
                    </Accordion >
                  </div >
                )}
              {
                activeExecution.errors && activeExecution.errors.length > 0 && (
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
                )
              }
            </div >
          )}
          <DialogFooter>
            <Button onClick={() => setIsExecutionModalOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent >
      </Dialog >


      {/* [Lesson 3] Fork / Time Travel Modal */}
      < Dialog open={isForkModalOpen} onOpenChange={setIsForkModalOpen} >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center">
              <History className="w-5 h-5 mr-2 text-purple-500" />
              Time Travel: Fork from Step {forkStepId}
            </DialogTitle>
            <DialogDescription>
              Create a parallel universe starting from this step. You can patch variables to fix errors.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <Alert className="bg-purple-50 border-purple-200">
              <GitBranch className="h-4 w-4 text-purple-600" />
              <AlertTitle className="text-purple-800">Branching Timeline</AlertTitle>
              <AlertDescription className="text-purple-700 text-xs">
                Original execution {activeExecution?.execution_id} will be preserved. A new execution will function as a &quot;Clone&quot;.
              </AlertDescription>
            </Alert>

            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <Label>Hyperparameters & Variables</Label>
                <Badge variant="outline" className="text-xs font-normal text-gray-500 dark:text-gray-400">
                  {Object.keys(forkVariables).length} params
                </Badge>
              </div>

              {Object.keys(forkVariables).length === 0 ? (
                <div className="text-center py-6 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-md">
                  <p className="text-sm text-gray-500 dark:text-gray-400">No tunable parameters found for this step.</p>
                  <p className="text-xs text-gray-400 mt-1">Forking will proceed with original state.</p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2">
                  {Object.entries(forkVariables).map(([key, value]) => (
                    <div key={key} className="space-y-1">
                      <Label htmlFor={`param-${key}`} className="text-xs font-medium text-gray-600 dark:text-gray-400">
                        {key}
                      </Label>
                      <Input
                        id={`param-${key}`}
                        className="h-8 text-sm"
                        value={typeof value === 'object' ? JSON.stringify(value) : String(value)}
                        onChange={(e) => {
                          const newVal = e.target.value;
                          // Try to conserve types (number/bool) if possible, otherwise string
                          let typedVal: any = newVal;
                          if (newVal === 'true') typedVal = true;
                          else if (newVal === 'false') typedVal = false;
                          else if (!isNaN(Number(newVal)) && newVal.trim() !== '') typedVal = Number(newVal);

                          setForkVariables(prev => ({ ...prev, [key]: typedVal }));
                        }}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsForkModalOpen(false)}>
              Cancel
            </Button>
            <Button
              className="bg-purple-600 hover:bg-purple-700 text-white"
              onClick={() => {
                // [Lesson 4] Safe Mode: Direct Object Submission
                // No parsing needed, form keeps object in sync
                handleForkWorkflow(forkStepId!, forkVariables);
              }}
              disabled={executing}
            >
              {executing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <GitBranch className="w-4 h-4 mr-2" />}
              Fork Timeline
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog >

    </div >
  );
};

export default WorkflowAutomation;
