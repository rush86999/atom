import { apiClient } from './api-client';

// Typed client for the Trust Calibration Gateway (shadow, P0–P3 scaffold).
// Admin-only surface: /api/v1/trust-calibration/*.

export type TrustRecommendation = 'allow' | 'ask' | 'block';

export interface TrustAssessment {
  action_type: string;
  platform: string;
  p_approve: number;
  uncertainty: number;
  recommendation: TrustRecommendation;
  n_obs: number;
  sources: { hitl: number; proposal: number };
  thresholds: { tau_low: number; tau_uncertain: number };
  min_observations: number;
}

export interface TrustStats {
  enabled: boolean;
  shadow_only: boolean;
  observations: {
    total: number;
    by_source: Record<string, number>;
    approved: number;
    rejected: number;
  };
  calibration: {
    assessments_total: number;
    resolved: number;
    pending: number;
    brier: number | null;
    ece_10bin: number | null;
    recommendation_outcome_matrix: Record<
      string,
      Record<'approved' | 'rejected', number>
    >;
  };
  kernel: { half_life_days: number; max_obs: number };
  thresholds: {
    tau_low: number;
    tau_uncertain: number;
    min_observations: number;
  };
}

export interface AutomationStatus {
  mode: 'off' | 'notify' | 'approve' | 'auto';
  interval_min: number;
  resolved_enforce: boolean;
  latest_action: {
    id: string;
    verdict: string;
    state: string;
    created_at: string;
  } | null;
}

function query(params: Record<string, string | undefined>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '') qs.set(k, String(v));
  });
  const s = qs.toString();
  return s ? `?${s}` : '';
}

/** Three-tier assessment for a proposed action (allow/ask/block). */
export async function assessAction(opts: {
  actionType: string;
  platform?: string;
  agentId?: string;
}): Promise<TrustAssessment> {
  // apiClient.fetch exists at runtime (attached in lib/api.ts) but is not
  // part of the axios type surface — same accessor pattern as boards-api.
  type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
  const raw = apiClient as unknown as { fetch: FetchLike };

  const res = await raw.fetch(
    `/api/v1/trust-calibration/assess${query({
      action_type: opts.actionType,
      platform: opts.platform,
      agent_id: opts.agentId,
    })}`
  );
  if (!res.ok) throw new Error(`Assess failed (${res.status})`);
  return res.json();
}

export async function getTrustStats(): Promise<TrustStats> {
  type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
  const raw = apiClient as unknown as { fetch: FetchLike };
  const res = await raw.fetch('/api/v1/trust-calibration/stats');
  if (!res.ok) throw new Error(`Stats failed (${res.status})`);
  return res.json();
}

// ── Automation management ───────────────────────────────────────────────────

export async function getAutomation(): Promise<AutomationStatus> {
  type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
  const raw = apiClient as unknown as { fetch: FetchLike };
  const res = await raw.fetch('/api/v1/trust-calibration/automation');
  if (!res.ok) throw new Error(`Automation status failed (${res.status})`);
  return res.json();
}

export async function setAutomation(input: {
  mode?: 'off' | 'notify' | 'approve' | 'auto';
  intervalMin?: number;
}): Promise<{ mode: string; interval_min: number }> {
  type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
  const raw = apiClient as unknown as { fetch: FetchLike };
  const qs = new URLSearchParams();
  if (input.mode !== undefined) qs.set('mode', input.mode);
  if (input.intervalMin !== undefined) qs.set('interval_min', String(input.intervalMin));
  const res = await raw.fetch(`/api/v1/trust-calibration/automation?${qs}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Set automation failed (${res.status})`);
  return res.json();
}

export async function runCertificationNow(): Promise<Record<string, unknown>> {
  type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
  const raw = apiClient as unknown as { fetch: FetchLike };
  const res = await raw.fetch('/api/v1/trust-calibration/run-now', {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Run-now failed (${res.status})`);
  return res.json();
}
