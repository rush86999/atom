import { apiClient } from './api-client';

// Playbooks — company processes as procedural memory
// (docs/architecture/PLAYBOOK_USER_JOURNEY.md). The Training tab's Playbooks
// section is the only UI: drafts from corrections/teaching queue here for
// one-click supervisor approval; approved playbooks advise matching tasks.

export type PlaybookSource = 'authored' | 'taught' | 'learned';
export type PlaybookState = 'draft' | 'approved' | 'retired';

/** Autonomy-latch state the sleep-time job persists on a learned draft
    (Playbook Journey §6): the clean-replay streak toward promotion without
    a human click, or `blocked` when the agent-maturity gate holds it. */
export interface PlaybookAutoLatch {
  passes?: number;
  threshold?: number;
  blocked?: string;
}

export interface Playbook {
  id: string;
  name: string;
  description: string;
  trigger_canvas_type: string | null;
  trigger_keywords: string[];
  steps: string[];
  template_questions: string[];
  source: PlaybookSource;
  approval_state: PlaybookState;
  /** Bumped each time a recurring correction re-drafts the same rule —
      on a learned draft this doubles as a "seen n×" counter. */
  version: number;
  auto_latch?: PlaybookAutoLatch;
}

export interface PlaybookCreateInput {
  name: string;
  description?: string;
  trigger_canvas_type?: string | null;
  trigger_keywords?: string[];
  steps?: string[];
  template_questions?: string[];
}

export interface PlaybookUpdateInput {
  name?: string;
  description?: string;
  trigger_canvas_type?: string | null;
  trigger_keywords?: string[];
  steps?: string[];
  template_questions?: string[];
}

/** Summary of the eval replay that blocked a promotion (HTTP 409). */
export interface EvalGateBlock {
  ran: number;
  passed: number;
  failed: number;
  skipped: number;
  [key: string]: unknown;
}

// apiClient.fetch exists at runtime (same accessor convention as maturity-api).
type FetchLike = (url: string, init?: RequestInit) => Promise<Response>;
const rawFetch = apiClient as unknown as { fetch: FetchLike };
const fetchJson: FetchLike = (url, init) => rawFetch.fetch(url, init);

function playbookFromRow(row: Record<string, unknown>): Playbook {
  const lastEval = row.last_eval_result as Record<string, unknown> | null | undefined;
  return {
    id: String(row.id),
    name: String(row.name ?? ''),
    description: String(row.description ?? ''),
    trigger_canvas_type: (row.trigger_canvas_type as string) ?? null,
    trigger_keywords: Array.isArray(row.trigger_keywords) ? row.trigger_keywords.map(String) : [],
    steps: Array.isArray(row.steps) ? row.steps.map(String) : [],
    template_questions: Array.isArray(row.template_questions) ? row.template_questions.map(String) : [],
    source: (row.source as Playbook['source']) ?? 'authored',
    approval_state: (row.approval_state as Playbook['approval_state']) ?? 'draft',
    version: Number(row.version ?? 1),
    auto_latch: (lastEval?.auto_latch as Playbook['auto_latch']) ?? undefined,
  };
}

export async function listPlaybooks(includeDrafts = true): Promise<Playbook[]> {
  const res = await fetchJson(`/api/playbooks?include_drafts=${includeDrafts ? 'true' : 'false'}`);
  if (!res.ok) throw new Error(`Failed to load playbooks (${res.status})`);
  const body = await res.json();
  return (body.playbooks ?? []).map(playbookFromRow);
}

export async function createPlaybook(input: PlaybookCreateInput): Promise<PlaybookState> {
  const res = await fetchJson('/api/playbooks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(`Failed to create playbook (${res.status})`);
  const body = await res.json();
  return (body.approval_state as PlaybookState) ?? 'approved';
}

export async function updatePlaybook(id: string, patch: PlaybookUpdateInput): Promise<void> {
  const res = await fetchJson(`/api/playbooks/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    if (res.status === 409) throw new Error('Only draft playbooks can be edited — retire the approved one and re-draft instead.');
    throw new Error(`Failed to update playbook (${res.status})`);
  }
}

/**
 * THE HITL gate: draft → approved. Fails with an EvalGateBlock-shaped error
 * when the eval gate is in enforce mode and an origin eval regressed.
 */
export async function approvePlaybook(id: string): Promise<void> {
  const res = await fetchJson(`/api/playbooks/${id}/approve`, { method: 'POST' });
  if (!res.ok) {
    if (res.status === 409) {
      let gate: EvalGateBlock | null = null;
      try {
        const detail = (await res.json())?.detail;
        gate = detail?.eval_gate ?? null;
      } catch { /* body parse is best-effort */ }
      const failed = gate?.failed ?? '?';
      throw new Error(
        `Blocked by the eval gate: ${failed} originating eval(s) regressed. Fix or retire the rule — the draft is kept.`
      );
    }
    throw new Error(`Failed to approve playbook (${res.status})`);
  }
}

export async function retirePlaybook(id: string): Promise<void> {
  const res = await fetchJson(`/api/playbooks/${id}/retire`, { method: 'POST' });
  if (!res.ok) throw new Error(`Failed to retire playbook (${res.status})`);
}
