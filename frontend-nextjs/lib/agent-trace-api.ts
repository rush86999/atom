import { apiClient } from './api-client';

// Agent trace API for the Agent Workspace panel (chat right pane).
// - GET /api/chat/trace/{session_id} — persisted runs + reasoning steps for
//   history restore
// - POST /api/reasoning/feedback — per-step thumbs feedback; when the step
//   belongs to a persisted run the polarity is stamped on the reasoning-step
//   row (training signal for harness evolution / failure-pattern mining)

export interface TraceStep {
  step_number: number;
  step_type?: string | null;
  thought?: string | null;
  action?: string | null;
  action_input?: string | null;
  observation?: string | null;
  confidence?: number | null;
  verified?: string | null;
  verification_evidence?: string | null;
  duration_ms?: number | null;
  resolved_model?: string | null;
  feedback_score?: number | null;
  feedback_text?: string | null;
  timestamp?: string | null;
}

export interface TraceRun {
  execution_id: string;
  agent_id?: string | null;
  status?: string | null;
  triggered_by?: string | null;
  input_summary?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  duration_seconds?: number | null;
  steps: TraceStep[];
}

export interface SessionTraceResponse {
  runs: TraceRun[];
  session_id: string;
}

export async function fetchSessionTrace(
  sessionId: string,
  limit = 10
): Promise<SessionTraceResponse> {
  const res = await apiClient.get(`/api/chat/trace/${sessionId}`, {
    params: { limit },
  });
  const body = res.data ?? {};
  return { runs: body.runs ?? [], session_id: body.session_id ?? sessionId };
}

export interface StepFeedbackPayload {
  agentId: string;
  runId: string;
  /** Index of the step within its run (position-based, as the endpoint expects). */
  stepIndex: number;
  stepContent: Record<string, unknown>;
  feedbackType: 'thumbs_up' | 'thumbs_down';
  comment?: string;
  /** Persisted-run linkage: stamps feedback_score on the reasoning-step row. */
  executionId?: string;
  stepNumber?: number;
}

export async function submitStepFeedback(
  payload: StepFeedbackPayload
): Promise<void> {
  await apiClient.post('/api/reasoning/feedback', {
    agent_id: payload.agentId,
    run_id: payload.runId,
    step_index: payload.stepIndex,
    step_content: payload.stepContent,
    feedback_type: payload.feedbackType,
    comment: payload.comment,
    execution_id: payload.executionId,
    step_number: payload.stepNumber,
  });
}
