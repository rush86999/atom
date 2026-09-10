import { apiClient } from './api-client';

// GoalRuns — role-scoped, multi-canvas, self-steering processes
// (docs/architecture/GOAL_RUN_ORCHESTRATION.md). A run is a long-lived,
// event-resumable execution of one goal: the plan is a familiar path, the
// router re-decides direction after every step, and every decision is
// logged with its rationale — the informal process made visible.

export type GoalRunStatus =
  | 'planning' | 'active' | 'waiting' | 'paused_hitl'
  | 'achieved' | 'failed' | 'cancelled';

export type SupervisionMode = 'training' | 'shadow' | 'autonomous';

// A GoalObjective — the WHAT a run pursues. Goals had no HTTP surface until
// 2026-09-10 (creatable only by the agent action `goals.create`), so the
// run-start journey could not name its own goal.
export interface Goal {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  progress: number;
  criteria: Record<string, unknown>[];
  key_results: Record<string, unknown>[];
  owner_id?: string | null;
  source?: string | null;
  target_date?: string | null;
  created_at?: string | null;
}

export interface CreateGoalInput {
  title: string;
  description?: string;
  criteria?: Record<string, unknown>[];
  key_results?: Record<string, unknown>[];
  target_date?: string;
}

export interface CreateGoalRunInput {
  goal_id: string;
  agent_id?: string;
  role?: string;
  supervision_mode?: SupervisionMode;
  parameters?: Record<string, unknown>;
  /** false stages a dormant run (no first loop turn). Defaults to starting. */
  start?: boolean;
}

export interface StartResult {
  advanced?: boolean;
  decision?: string;
  held?: boolean;
  reason?: string;
  error?: string;
}

export interface GoalRunStep {
  id: string;
  kind: string; // canvas_work | integration_action | human_checkpoint | wait_for
  title: string;
  canvas_type?: string;
  done?: boolean;
}

export interface DecisionEntry {
  ts: string;
  kind: string; // decision | wake | held_for_approval | override | approved | wake | goal_achieved | run_done | cancelled | checkpoint_created
  decision?: string;
  rationale?: string;
  parameter_diff?: Record<string, unknown>;
  step_id?: string;
  canvas_id?: string;
  event?: string;
  model?: string;
  confidence?: number;
  hitl_id?: string;
  reviewer?: string;
}

export interface GoalRun {
  id: string;
  goal_id: string;
  agent_id: string | null;
  role: string | null;
  status: GoalRunStatus;
  supervision_mode: SupervisionMode;
  plan: GoalRunStep[];
  cursor: string | null;
  parameters: Record<string, unknown>;
  waiting_on: Record<string, unknown> | null;
  pending_decision: DecisionEntry | null;
  decision_log: DecisionEntry[];
  replan_count: number;
  steps_executed: number;
  human_interventions: number;
  created_at: string | null;
}

export interface GoalRunCanvas {
  id: string;
  name: string;
  canvas_type: string;
  step_id: string | null;
  created_at: string | null;
}

export interface PromotionEvidence {
  agent_id: string;
  recommendation: SupervisionMode;
  evidence: Record<string, {
    runs: number;
    achieved: number;
    achieved_ratio: number;
    interventions_per_run: number;
  }>;
  note: string;
}

// apiClient.fetch exists at runtime (same accessor convention as playbook-api).
type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
const rawFetch = apiClient as unknown as { fetch: FetchLike };
const fetchJson: FetchLike = (url, init) => rawFetch.fetch(url, init);

function runFromRow(row: Record<string, unknown>): GoalRun {
  return {
    id: String(row.id),
    goal_id: String(row.goal_id ?? ''),
    agent_id: (row.agent_id as string) ?? null,
    role: (row.role as string) ?? null,
    status: (row.status as GoalRun['status']) ?? 'planning',
    supervision_mode: (row.supervision_mode as GoalRun['supervision_mode']) ?? 'shadow',
    plan: Array.isArray(row.plan) ? (row.plan as GoalRunStep[]) : [],
    cursor: (row.cursor as string) ?? null,
    parameters: (row.parameters as Record<string, unknown>) ?? {},
    waiting_on: (row.waiting_on as Record<string, unknown>) ?? null,
    pending_decision: (row.pending_decision as GoalRun['pending_decision']) ?? null,
    decision_log: Array.isArray(row.decision_log) ? (row.decision_log as DecisionEntry[]) : [],
    replan_count: Number(row.replan_count ?? 0),
    steps_executed: Number(row.steps_executed ?? 0),
    human_interventions: Number(row.human_interventions ?? 0),
    created_at: (row.created_at as string) ?? null,
  };
}

export async function listGoalRuns(opts?: {
  goalId?: string;
  agentId?: string;
  role?: string;
  status?: string;
  includeTerminal?: boolean;
}): Promise<GoalRun[]> {
  const qs = new URLSearchParams();
  if (opts?.goalId) qs.set('goal_id', opts.goalId);
  if (opts?.agentId) qs.set('agent_id', opts.agentId);
  if (opts?.role) qs.set('role', opts.role);
  if (opts?.status) qs.set('status', opts.status);
  if (opts?.includeTerminal === false) qs.set('include_terminal', 'false');
  const res = await fetchJson(`/api/goal-runs${qs.size ? `?${qs.toString()}` : ''}`);
  if (!res.ok) throw new Error(`Failed to load goal runs (${res.status})`);
  const body = await res.json();
  return (body.runs ?? []).map(runFromRow);
}

export async function getGoalRun(id: string): Promise<GoalRun> {
  const res = await fetchJson(`/api/goal-runs/${id}`);
  if (!res.ok) throw new Error(`Failed to load goal run (${res.status})`);
  return runFromRow(await res.json());
}

// ----------------------------------------------------------------- goals

export async function listGoals(opts?: {
  status?: string;
  includeTerminal?: boolean;
}): Promise<Goal[]> {
  const qs = new URLSearchParams();
  if (opts?.status) qs.set('status', opts.status);
  if (opts?.includeTerminal === false) qs.set('include_terminal', 'false');
  const res = await fetchJson(`/api/goals${qs.size ? `?${qs.toString()}` : ''}`);
  if (!res.ok) throw new Error(`Failed to load goals (${res.status})`);
  const body = await res.json();
  return (body.goals ?? []) as Goal[];
}

export async function getGoal(id: string): Promise<Goal> {
  const res = await fetchJson(`/api/goals/${id}`);
  if (!res.ok) throw new Error(`Failed to load goal (${res.status})`);
  return (await res.json()) as Goal;
}

export async function createGoal(input: CreateGoalInput): Promise<Goal> {
  const res = await fetchJson('/api/goals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detail = await readDetail(res, `Failed to create goal (${res.status})`);
    throw new Error(detail);
  }
  const body = await res.json();
  return body.goal as Goal;
}

/** Start a run. The backend kicks off the first loop turn, so the returned
    run is already working (or already held for approval in training mode). */
export async function createGoalRun(input: CreateGoalRunInput): Promise<{
  id: string;
  run: GoalRun;
  started: StartResult | null;
  seed_source: string | null;
}> {
  const res = await fetchJson('/api/goal-runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    const detail = await readDetail(res, `Failed to start goal run (${res.status})`);
    throw new Error(detail);
  }
  const body = await res.json();
  return {
    id: String(body.id),
    run: runFromRow(body.run ?? {}),
    started: (body.started as StartResult) ?? null,
    seed_source: (body.seed_source as string) ?? null,
  };
}

/** Pull a user-safe `detail` string out of an error body (FastAPI may send a
    bare string or a structured object). Falls back to `fallback`. */
async function readDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    const detail = body?.detail;
    if (typeof detail === 'string' && detail) return detail;
    if (detail && typeof detail === 'object' && typeof detail.error === 'string') {
      return detail.error;
    }
    if (typeof body?.message === 'string' && body.message) return body.message;
  } catch {
    /* best-effort */
  }
  return fallback;
}

export async function getGoalRunCanvases(id: string): Promise<GoalRunCanvas[]> {
  const res = await fetchJson(`/api/goal-runs/${id}/canvases`);
  if (!res.ok) throw new Error(`Failed to load run canvases (${res.status})`);
  const body = await res.json();
  return (body.canvases ?? []) as GoalRunCanvas[];
}

export async function resumeGoalRun(
  id: string,
  approved: boolean,
  guidance?: string,
): Promise<void> {
  const res = await fetchJson(`/api/goal-runs/${id}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, guidance }),
  });
  if (!res.ok) throw new Error(`Failed to resume goal run (${res.status})`);
}

export async function resolveCheckpoint(
  runId: string,
  hitlId: string,
  approved: boolean,
  guidance?: string,
): Promise<void> {
  const res = await fetchJson(`/api/goal-runs/${runId}/checkpoints/${hitlId}/resolve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, guidance }),
  });
  if (!res.ok) throw new Error(`Failed to resolve checkpoint (${res.status})`);
}

export async function advanceGoalRun(id: string): Promise<void> {
  const res = await fetchJson(`/api/goal-runs/${id}/advance`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to advance goal run (${res.status})`);
}

export async function cancelGoalRun(id: string): Promise<void> {
  const res = await fetchJson(`/api/goal-runs/${id}/cancel`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to cancel goal run (${res.status})`);
}

export async function setSupervisionMode(id: string, mode: SupervisionMode): Promise<void> {
  const res = await fetchJson(`/api/goal-runs/${id}/mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ supervision_mode: mode }),
  });
  if (!res.ok) throw new Error(`Failed to set supervision mode (${res.status})`);
}

export async function getPromotionEvidence(agentId: string): Promise<PromotionEvidence> {
  const res = await fetchJson(`/api/goal-runs/promotion/${agentId}`);
  if (!res.ok) throw new Error(`Failed to load promotion evidence (${res.status})`);
  return res.json();
}

export interface DistillResult {
  id: string;
  name: string;
  approval_state: string;
  steps: string[];
}

/** Distill a finished run's decision log into a playbook DRAFT in the
    Training panel's approval queue. Throws a user-safe message on 409
    (too thin / already drafted). */
export async function distillGoalRun(id: string): Promise<DistillResult> {
  const res = await fetchJson(`/api/goal-runs/${id}/distill`, { method: 'POST' });
  if (!res.ok) {
    if (res.status === 409) {
      let detail = '';
      try { detail = (await res.json())?.detail?.error ?? ''; } catch { /* best-effort */ }
      throw new Error(detail || 'Nothing new to distill from this run.');
    }
    throw new Error(`Failed to distill goal run (${res.status})`);
  }
  const body = await res.json();
  return body.draft as DistillResult;
}
