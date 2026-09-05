import { apiClient } from './api-client';

// Types for the agent maturity journey API (/api/maturity/*, restored R81).
// Supervisor-facing: review STUDENT training proposals, complete training
// sessions (confidence boost -> promotion), and approve/reject INTERN
// action proposals.

export interface TrainingProposal {
  id: string;
  agent_id: string;
  agent_name: string | null;
  title: string | null;
  description: string | null;
  status: string | null;
  capability_gaps: string[];
  learning_objectives: string[];
  estimated_duration_hours: number | null;
  created_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
}

export interface TrainingProposalDetail extends TrainingProposal {
  proposal_type?: string;
  duration_estimation_confidence?: number | null;
  duration_estimation_reasoning?: string | null;
  training_scenario_template?: string | null;
}

export interface TrainingSessionSummary {
  id: string;
  status: string | null;
  supervisor_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_tasks: number | null;
  tasks_completed: number | null;
}

export interface TrainingCompletionResult {
  session_id: string;
  confidence_boost?: number;
  new_confidence?: number;
  promoted_to_intern?: boolean;
  [key: string]: unknown;
}

/** Linked work evidence for a training session (backend-derived). */
export interface SessionEvidence {
  episodes: number;
  successes: number;
  success_ratio: number;
  window_started_at: string | null;
  required_episodes: number;
}

export interface ActionProposal {
  id: string;
  tenant_id?: string | null;
  agent_id: string;
  agent_name: string | null;
  canvas_id?: string | null;
  session_id?: string | null;
  title: string | null;
  description: string | null;
  status: string | null;
  proposed_action: Record<string, unknown> | null;
  reasoning: string | null;
  reversible: boolean | null;
  created_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
}

// apiClient.fetch exists at runtime (attached in lib/api.ts) but is not part
// of the axios type surface — route through one typed accessor instead of
// sprinkling casts at every call site.
type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
const rawFetch = apiClient as unknown as { fetch: FetchLike };
const fetchJson: FetchLike = (url, init) => rawFetch.fetch(url, init);

function query(params: Record<string, string | number | undefined>): string {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== '') qs.set(k, String(v));
  });
  const s = qs.toString();
  return s ? `?${s}` : '';
}

// ── Training proposals (STUDENT journey) ────────────────────────────────────

export async function listTrainingProposals(opts: {
  agentId?: string;
  statusFilter?: string;
  limit?: number;
} = {}): Promise<TrainingProposal[]> {
  const res = await fetchJson(
    `/api/maturity/training/proposals${query({
      agent_id: opts.agentId,
      status_filter: opts.statusFilter,
      limit: opts.limit,
    })}`
  );
  const body = await res.json();
  return body.proposals ?? [];
}

export async function getTrainingProposal(
  proposalId: string
): Promise<TrainingProposalDetail> {
  const res = await fetchJson(
    `/api/maturity/training/proposals/${proposalId}`
  );
  return res.json();
}

/** Approve a training proposal; returns the created session id. */
export async function approveTrainingProposal(
  proposalId: string,
  durationOverride?: Record<string, unknown>
): Promise<{ session_id: string; proposal_id: string }> {
  const res = await fetchJson(
    `/api/maturity/training/proposals/${proposalId}/approve`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approve: true, duration_override: durationOverride }),
    }
  );
  if (!res.ok) throw new Error(`Approve failed (${res.status})`);
  return res.json();
}

export async function rejectTrainingProposal(
  proposalId: string,
  reason: string
): Promise<void> {
  const res = await fetchJson(
    `/api/maturity/training/proposals/${proposalId}/reject`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason }),
    }
  );
  if (!res.ok) throw new Error(`Reject failed (${res.status})`);
}

/** Live linked-evidence counts for a training session. */
export async function getTrainingSessionEvidence(
  sessionId: string
): Promise<SessionEvidence> {
  const res = await fetchJson(
    `/api/maturity/training/sessions/${sessionId}/evidence`
  );
  if (!res.ok) throw new Error(`Evidence fetch failed (${res.status})`);
  return res.json();
}

export async function completeTrainingSession(
  sessionId: string,
  input: {
    /** Supervisor's claimed score — the backend caps it by linked evidence. */
    performance_score?: number;
    supervisor_feedback: string;
    errors_count?: number;
    /** Ignored by the backend: task progress comes from the episode ledger. */
    tasks_completed?: number;
    total_tasks?: number;
    capabilities_developed?: string[];
    capability_gaps_remaining?: string[];
  }
): Promise<TrainingCompletionResult> {
  const res = await fetchJson(
    `/api/maturity/training/sessions/${sessionId}/complete`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        capabilities_developed: [],
        capability_gaps_remaining: [],
        ...input,
      }),
    }
  );
  if (!res.ok) {
    // Surface the backend's structured reason (e.g. insufficient linked
    // evidence) instead of a bare status code.
    let message = `Complete failed (${res.status})`;
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === 'string') message = detail;
      else if (detail?.message) message = detail.message;
    } catch {
      // non-JSON error body — keep the generic message
    }
    throw new Error(message);
  }
  return res.json();
}

export async function getTrainingHistory(
  agentId: string,
  limit = 50
): Promise<TrainingSessionSummary[]> {
  const res = await fetchJson(
    `/api/maturity/agents/${agentId}/training-history${query({ limit })}`
  );
  const body = await res.json();
  return body.training_history ?? [];
}

// ── Canvas training panel (/canvas/{id} training tab) ───────────────────────

export interface CanvasTrainingAgent {
  id: string;
  name: string | null;
  tier: string | null;
  confidence: number | null;
  domain: string | null;
}

export interface CanvasTrainingSession {
  id: string;
  agent_id: string;
  status: string | null;
  started_at: string | null;
  completed_at: string | null;
  lesson_plan: Record<string, unknown> | null;
  supervisor_note?: string | null;
  canvas_id?: string | null;
  promoted_to_intern?: boolean;
  performance_score?: number | null;
  evidence: SessionEvidence;
}

/** One entry of the agent's learning journal (mentor lesson or observation). */
export interface TeachingPoint {
  source: string; // "teacher" | "observation"
  topic: string;
  text: string;
  learned_at: string | null;
  teacher_agent_id?: string | null;
  /** The canvas the lesson was taught on (right-panel teaches), when captured. */
  canvas?: { canvas_id: string; name: string; canvas_type: string; label: string } | null;
}

export interface CanvasTrainingContext {
  canvas_id: string;
  agent: CanvasTrainingAgent | null;
  linked_session: CanvasTrainingSession | null;
  pending_proposal: TrainingProposal | null;
  viewer_is_supervisor: boolean;
  /** All teaching points given to the agent, newest first. */
  teaching_points?: TeachingPoint[];
}

/**
 * Everything the canvas training panel needs in one read: which agent is
 * being trained on this canvas, the linked training session (with live
 * evidence), any pending training proposal, and whether the viewer may use
 * the supervisor controls.
 */
export async function getCanvasTrainingContext(
  canvasId: string,
  agentIdHint?: string
): Promise<CanvasTrainingContext> {
  const res = await fetchJson(
    `/api/maturity/training/context${query({
      canvas_id: canvasId,
      agent_id: agentIdHint,
    })}`
  );
  if (!res.ok) throw new Error(`Context fetch failed (${res.status})`);
  return res.json();
}

/** Deliver a mentor lesson to a STUDENT agent (the learning channel).
 * canvasId (the canvas the panel is teaching from) is snapshotted into the
 * lesson so retrieval later knows what the lesson was about. */
export async function teachAgent(
  agentId: string,
  lesson: string,
  topic?: string,
  canvasId?: string,
  opts?: { asPlaybook?: boolean; playbookCanvasType?: string }
): Promise<{ status: string; playbook_id?: string | null; [key: string]: unknown }> {
  const res = await fetchJson(`/api/agents/${agentId}/teach`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      lesson,
      topic,
      canvas_id: canvasId,
      // Playbook Journey P2: opt-in structured capture — the lesson ALSO
      // becomes a playbook draft in the Training tab's review queue.
      ...(opts?.asPlaybook ? { as_playbook: true } : {}),
      ...(opts?.playbookCanvasType ? { playbook_canvas_type: opts.playbookCanvasType } : {}),
    }),
  });
  if (!res.ok) throw new Error(`Teach failed (${res.status})`);
  return res.json();
}

/** Supervisor edits the mentor-proposed lesson plan for a session. */
export async function updateTrainingGuidance(
  sessionId: string,
  lessonPlan: Record<string, unknown>,
  supervisorNote?: string
): Promise<{ success: boolean; lesson_plan: Record<string, unknown> | null }> {
  const res = await fetchJson(
    `/api/maturity/training/sessions/${sessionId}/guidance`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(
        supervisorNote !== undefined
          ? { lesson_plan: lessonPlan, supervisor_note: supervisorNote }
          : { lesson_plan: lessonPlan }
      ),
    }
  );
  if (!res.ok) throw new Error(`Guidance save failed (${res.status})`);
  return res.json();
}

export interface GraduationReadiness {
  ready?: boolean;
  score?: number;
  episode_count?: number;
  intervention_rate?: number;
  recommendation?: string;
  gaps?: string[];
  current_maturity?: string;
  target_maturity?: string;
  [key: string]: unknown;
}

export async function getGraduationReadiness(
  agentId: string,
  targetMaturity = 'INTERN'
): Promise<GraduationReadiness> {
  const res = await fetchJson(
    `/api/episodes/graduation/readiness/${agentId}${query({
      target_maturity: targetMaturity,
    })}`
  );
  if (!res.ok) throw new Error(`Readiness fetch failed (${res.status})`);
  return res.json();
}

/** Promote an agent to the next tier (graduation). Supervisor-only backend. */
export async function promoteAgent(
  agentId: string,
  newMaturity: string
): Promise<{ agent_id: string; new_maturity: string; promoted: boolean }> {
  // This endpoint takes query params, not a JSON body.
  const res = await fetchJson(
    `/api/episodes/graduation/promote${query({
      agent_id: agentId,
      new_maturity: newMaturity,
    })}`,
    { method: 'POST' }
  );
  if (!res.ok) throw new Error(`Promote failed (${res.status})`);
  return res.json();
}

export interface GraduationProgress {
  current_tier?: string;
  next_tier?: string | null;
  episodes_to_next?: number | null;
  next_threshold_episodes?: number | null;
  episode_count?: number;
  [key: string]: unknown;
}

/** Tier progress from the shared /api/agents surface (AgentCard badge data). */
export async function getAgentGraduationProgress(
  agentId: string
): Promise<GraduationProgress> {
  const res = await fetchJson(`/api/agents/${agentId}/graduation-progress`);
  if (!res.ok) throw new Error(`Progress fetch failed (${res.status})`);
  return res.json();
}

// ── Action proposals (INTERN journey) ───────────────────────────────────────

export async function listActionProposals(opts: {
  agentId?: string;
  statusFilter?: string;
  limit?: number;
} = {}): Promise<ActionProposal[]> {
  const res = await fetchJson(
    `/api/maturity/proposals${query({
      agent_id: opts.agentId,
      status_filter: opts.statusFilter,
      limit: opts.limit,
    })}`
  );
  const body = await res.json();
  return body.proposals ?? [];
}

export async function approveActionProposal(
  proposalId: string,
  modifications?: Record<string, unknown>
): Promise<{ execution_result: unknown }> {
  const res = await fetchJson(`/api/maturity/proposals/${proposalId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approve: true, modifications }),
  });
  if (!res.ok) throw new Error(`Approve failed (${res.status})`);
  return res.json();
}

export async function rejectActionProposal(
  proposalId: string,
  reason: string
): Promise<void> {
  const res = await fetchJson(`/api/maturity/proposals/${proposalId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error(`Reject failed (${res.status})`);
}
