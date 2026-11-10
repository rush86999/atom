import { apiClient } from './api-client';

// Typed client for the employee onboarding API (backend:
// api/agent_onboarding_routes.py). Self-serve agent creation, history-mined
// automation suggestions, and agent maturity guidance.

export interface AgentVerification {
  status?: string;
  effect?: string;
  audit_id?: string;
  replay?: string;
}

export interface AgentCreationReceipt {
  operation_id?: string;
  audit_id?: string;
  verification?: AgentVerification;
}

export interface GuidedAgentResult extends AgentCreationReceipt {
  agent_id: string;
  name: string;
  category: string;
  template?: string;
  maturity: string;
  created_by: 'employee' | 'agent';
}

export interface GuidedAgentPending {
  status: 'pending_approval';
  hitl_action_id: string | null;
  reason: string;
}

export interface CustomAgentResult extends AgentCreationReceipt {
  agent_id: string;
  agent_name?: string;
  category?: string;
  tenant_id?: string;
  workspace_id?: string;
}

export function newCreationOperationId(): string {
  const cryptoObj =
    typeof globalThis !== 'undefined' ? (globalThis as any).crypto : undefined;
  if (cryptoObj && typeof cryptoObj.randomUUID === 'function') {
    return cryptoObj.randomUUID();
  }
  return `ui-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function unwrapCreationEnvelope(res: any, label: string): any {
  const envelope = res?.data;
  if (envelope && envelope.success === false) {
    const err: any = new Error(`${label} was not accepted`);
    err.code = 'CREATION_NOT_ACCEPTED';
    err.response = res;
    throw err;
  }
  return envelope?.data ?? envelope;
}

function assertVerifiedCreation(data: any, label: string): any {
  if (!data || typeof data.agent_id !== 'string' || !data.agent_id.trim()) {
    const err: any = new Error(`${label} returned no exact agent id`);
    err.code = 'UNVERIFIED_CREATE';
    err.data = data;
    throw err;
  }
  const status = data?.verification?.status;
  if (status !== 'verified' && status !== 'already_applied') {
    const err: any = new Error(
      `${label} was not verified; reconcile before retrying`
    );
    err.code = 'UNVERIFIED_CREATE';
    err.data = data;
    throw err;
  }
  return data;
}

export interface AutomationSuggestion {
  title: string;
  description: string;
  trigger?: string;
  steps?: string[];
  evidence?: string;
  estimated_time_saved_minutes_per_month?: number;
}

export interface AutomationSuggestionsResult {
  history_summary: {
    frequent_manual_agent_runs: { task: string; count: number }[];
    frequently_approved_actions: { action: string; approvals: number }[];
    most_run_workflows: { workflow_id: string; runs: number }[];
  };
  suggestions: AutomationSuggestion[];
}

export interface MaturityLevelGuide {
  level: 'student' | 'intern' | 'supervised' | 'autonomous';
  title: string;
  what_it_can_do: string;
  what_it_cannot_do: string;
  useful_for: string;
}

export interface MaturityGuide {
  levels: MaturityLevelGuide[];
}

export interface AgentMaturityGuide {
  agent_id: string;
  agent_name: string;
  current_level: string;
  level_guide: MaturityLevelGuide;
  what_it_can_do_today: { complexity_band: number; example_actions: string[] };
  learning_progress: {
    role: string;
    curriculum: string[];
    lessons_from_teacher: number;
    observations: number;
    pathways_used: string[];
  };
  mastery: {
    mastered: string[];
    in_progress: Record<string, number>;
    threshold: number;
  };
  readiness: {
    ready_for_graduation_review: boolean;
    confidence: number;
    confidence_needed_for_training_review: number;
    note: string;
  };
  assessment?: {
    allowed?: boolean;
    required?: boolean;
    state?: string;
    message?: string;
    receipt_id?: string;
    review_action_id?: string;
    candidate_capability_qualified?: boolean;
    exception?: { kind?: string; reason?: string } | null;
    next_action?: {
      state?: string;
      code?: string;
      message?: string;
      next_action?: string;
      review_action_id?: string;
    } | null;
  } | null;
  next_level: string | null;
  how_to_advance: string;
}

export async function createGuidedAgent(
  goal: string,
  context?: string,
  options?: { operationId?: string }
): Promise<GuidedAgentResult | GuidedAgentPending> {
  const operationId = options?.operationId;
  const res = await apiClient.post(
    '/api/agents/guided',
    { goal, context },
    {
      ...(operationId ? { params: { operation_id: operationId } } : {}),
      // A create is not idempotent at the transport layer. A 503 or a lost
      // network confirmation may already have committed; never replay it
      // automatically. The same operation id can be reused only when the
      // user explicitly retries the unchanged intent.
      retry: false,
    }
  );
  const data = unwrapCreationEnvelope(res, 'Agent creation');
  if (data?.status === 'pending_approval') {
    return {
      status: 'pending_approval',
      hitl_action_id: data.hitl_action_id ?? null,
      reason: data.reason || 'Human approval required',
    };
  }
  return assertVerifiedCreation(data, 'Agent creation') as GuidedAgentResult;
}

export async function createCustomAgent(
  payload: {
    name: string;
    description?: string;
    category: string;
    configuration?: Record<string, unknown>;
    schedule_config?: Record<string, unknown> | null;
  },
  options?: { operationId?: string }
): Promise<CustomAgentResult> {
  const operationId = options?.operationId;
  const res = await apiClient.post('/api/agents/custom', payload, {
    ...(operationId ? { params: { operation_id: operationId } } : {}),
    // Same no-auto-replay rule as guided creation: a lost confirmation is
    // uncertain, not permission to POST the hire again.
    retry: false,
  });
  const data = unwrapCreationEnvelope(res, 'Employee hire');
  return assertVerifiedCreation(data, 'Employee hire') as CustomAgentResult;
}

export async function getAutomationSuggestions(
  limit = 5
): Promise<AutomationSuggestionsResult> {
  const res = await apiClient.get('/api/agents/automation-suggestions', {
    params: { limit },
  });
  return res.data?.data ?? res.data;
}

export async function getMaturityGuide(): Promise<MaturityGuide> {
  const res = await apiClient.get('/api/agents/maturity-guide');
  return res.data?.data ?? res.data;
}

export async function getAgentMaturityGuide(
  agentId: string
): Promise<AgentMaturityGuide> {
  const res = await apiClient.get(`/api/agents/${agentId}/maturity-guide`);
  return res.data?.data ?? res.data;
}
