import { apiClient } from './api-client';

// Typed client for the BPE (Belief/Progress/Experience) agent workspace.
// Admin-only surface: /api/v1/admin/bpe/*. Flag overrides ride the shared
// runtime-settings API (see runtime-settings-api.ts) — env vars always win.

type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;

function rawClient(): { fetch: FetchLike } {
  return apiClient as unknown as { fetch: FetchLike };
}

async function readJson<T>(res: Response, what: string): Promise<T> {
  if (res.status === 403) {
    throw new Error('Admin role required to view the BPE workspace surface.');
  }
  if (!res.ok) {
    throw new Error(`${what} failed (${res.status})`);
  }
  return ((await res.json()) as { data: T }).data;
}

export interface BpeFlagState {
  value: unknown;
  source: 'env' | 'db' | 'default' | 'unknown';
  type: string;
  description: string;
}

export interface BpeModes {
  workspace_enabled: boolean;
  automation_active: boolean;
  consult_gating_active: boolean;
  evolution_apply_enabled: boolean;
}

export interface BpePolicyAgentState {
  episodes: number;
  value_ema: number;
  consults_total: number;
  commit_note_total: number;
  consult_episodes: number;
  updated_at: number;
  render_mode: 'full' | 'recall_only';
  suppressed: boolean;
  harness_call_rate: number;
}

export interface BpeFamilyReadiness {
  family: string;
  evaluated_genomes: number;
  best_fitness: number;
  apply_ready: boolean;
}

export interface BpeWorkspaceSummary {
  workspace_id: string;
  agent_id: string;
  scope_key: string;
  progress_count: number;
  progress_done: number;
  pending_notes: number;
  experience_counts: Record<string, number>;
  episode_consults: number;
}

export interface BpeTelemetrySummary {
  window_spans: number;
  aggregate: Record<string, { count: number; avg_latency_ms: number; error_count: number }>;
  automation_flips: { at: number | null; detail: Record<string, unknown> }[];
}

export interface BpeMetaActionDoc {
  name: string;
  description: string;
  parameters: unknown;
}

export interface BpeOverview {
  flags: Record<string, BpeFlagState>;
  modes: BpeModes;
  thresholds: {
    min_episodes_for_value_gate: number;
    recall_only_share: number;
    recall_only_min_episodes: number;
    min_evaluated_genomes: number;
    evolution_apply_fitness: number;
    population_size: number;
    target_call_rate: number;
  };
  active_bounds: Record<string, number>;
  gene_bounds: Record<string, { min: number; max: number }>;
  consult_policy: Record<string, BpePolicyAgentState>;
  population: Record<string, { genome: Record<string, number>; fitness: number }[]>;
  evolution_readiness: BpeFamilyReadiness[];
  workspaces: BpeWorkspaceSummary[];
  persistence: { data_dir: string | null; snapshot_files: number };
  telemetry: BpeTelemetrySummary;
  meta_actions: BpeMetaActionDoc[];
}

export interface BpeWorkspaceDetail {
  workspace_id: string;
  agent_id: string;
  scope_key: string;
  progress: { title: string; status: string; committed_at: number; updated_at: number }[];
  pending_notes: string[];
  experience: Record<string, { content: string; uses: number; added_at: number }[]>;
}

export async function getBpeOverview(): Promise<BpeOverview> {
  const res = await rawClient().fetch('/api/v1/admin/bpe/overview');
  return readJson<BpeOverview>(res, 'BPE overview');
}

export async function getBpeWorkspaceDetail(
  workspaceId: string,
  agentId: string,
  scopeKey: string
): Promise<BpeWorkspaceDetail> {
  const params = new URLSearchParams({
    workspace_id: workspaceId,
    agent_id: agentId,
    scope_key: scopeKey,
  });
  const res = await rawClient().fetch(`/api/v1/admin/bpe/workspaces/detail?${params}`);
  return readJson<BpeWorkspaceDetail>(res, 'Workspace detail');
}

export async function applyBpeGenome(family: string): Promise<{ applied: boolean; reason?: string; bounds?: Record<string, number> }> {
  const res = await rawClient().fetch(`/api/v1/admin/bpe/evolution/apply/${encodeURIComponent(family)}`, {
    method: 'POST',
  });
  const body = (await res.json()) as {
    applied: boolean;
    reason?: string;
    data?: { bounds: Record<string, number> };
  };
  if (!res.ok) {
    throw new Error(`Genome apply failed (${res.status})`);
  }
  return { applied: body.applied, reason: body.reason, bounds: body.data?.bounds };
}
