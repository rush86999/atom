import { apiClient } from './api-client';

// Typed client for the employee onboarding API (backend:
// api/agent_onboarding_routes.py). Self-serve agent creation, history-mined
// automation suggestions, and agent maturity guidance.

export interface GuidedAgentResult {
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
  next_level: string | null;
  how_to_advance: string;
}

export async function createGuidedAgent(
  goal: string,
  context?: string
): Promise<GuidedAgentResult | GuidedAgentPending> {
  const res = await apiClient.post('/api/agents/guided', { goal, context });
  return res.data?.data ?? res.data;
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
