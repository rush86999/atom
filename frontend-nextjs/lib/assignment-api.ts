import { apiClient } from "./api-client";

export interface AssignmentStep {
  step_id: string;
  title: string;
  operation_type: string;
  adapter: string;
  depends_on: string[];
  required: boolean;
  effect: string;
  status: string;
  recovery_class: string;
  operation_id: string | null;
  attempts: number;
  result_summary: string | null;
  artifact_revision: string | null;
  gap_ids: string[];
  waiting: Record<string, unknown>;
  approval_request: Record<string, unknown>;
  failure: Record<string, unknown>;
}

export interface AssignmentDeliverable {
  deliverable_id: string;
  kind: string;
  description: string;
  required: boolean;
  step_id: string | null;
  status: string;
  artifact_revision: string | null;
  artifact_path: string | null;
  sha256: string | null;
}

export interface AssignmentDetail {
  run_id: string;
  assignment: {
    assignment_id: string;
    objective: string;
    employee_id: string | null;
    workspace_id: string | null;
    plan_revision: number;
    status: string;
    teaching_revision: string | null;
    teaching_fingerprint: string | null;
    deliverables: AssignmentDeliverable[];
    sources: Record<string, unknown>[];
    authorized_actions: string[];
    budget: Record<string, unknown>;
    steps: AssignmentStep[];
    created_at: string | null;
    updated_at: string | null;
    completed_at: string | null;
  };
  open_gaps: Array<Record<string, any>>;
  operations: Array<Record<string, any>>;
}

export interface AssignmentSummary {
  run_id: string;
  status: string;
  assignment: {
    assignment_id: string;
    objective: string;
    state: string;
    plan_revision: number;
    current_action: string | null;
  };
}

export async function listAssignments(): Promise<AssignmentSummary[]> {
  const { data } = await apiClient.get<AssignmentSummary[]>(
    "/api/assignments?include_terminal=true"
  );
  return data;
}

export async function createAssignment(payload: {
  objective: string;
  conversation_id?: string;
  agent_id?: string;
  sources: Record<string, unknown>[];
  source_scope?: Record<string, unknown>;
  discover?: boolean;
  deliverables: Record<string, unknown>[];
  calculation?: Record<string, unknown>;
  outbound?: Record<string, unknown>;
  wait?: Record<string, unknown>;
  task_context?: Record<string, unknown>;
  transport?: string;
}): Promise<Record<string, any>> {
  const { data } = await apiClient.post("/api/assignments", payload);
  return data;
}

export async function getAssignment(runId: string): Promise<AssignmentDetail> {
  const { data } = await apiClient.get<AssignmentDetail>(
    `/api/assignments/${encodeURIComponent(runId)}`
  );
  return data;
}

export async function resumeAssignment(runId: string): Promise<AssignmentDetail> {
  const { data } = await apiClient.post<AssignmentDetail>(
    `/api/assignments/${encodeURIComponent(runId)}/resume`
  );
  return data;
}

export async function cancelAssignment(
  runId: string,
  reason: string
): Promise<AssignmentDetail> {
  const { data } = await apiClient.post<AssignmentDetail>(
    `/api/assignments/${encodeURIComponent(runId)}/cancel`,
    { reason }
  );
  return data;
}

export async function resolveAssignmentGap(
  runId: string,
  questionId: string,
  resolution: string,
  evidence = ""
): Promise<AssignmentDetail> {
  const { data } = await apiClient.post<AssignmentDetail>(
    `/api/assignments/${encodeURIComponent(runId)}/gaps/${encodeURIComponent(questionId)}/resolve`,
    { resolution, evidence }
  );
  return data;
}

export async function recordAssignmentResponse(
  runId: string,
  correlationId: string,
  response: string,
  evidence = ""
): Promise<AssignmentDetail> {
  const { data } = await apiClient.post<AssignmentDetail>(
    `/api/assignments/${encodeURIComponent(runId)}/responses/${encodeURIComponent(correlationId)}`,
    { response, evidence }
  );
  return data;
}

export async function approveAssignmentStep(
  runId: string,
  stepId: string,
  note = ""
): Promise<Record<string, any>> {
  const { data } = await apiClient.post(
    `/api/assignments/${encodeURIComponent(runId)}/approve/${encodeURIComponent(stepId)}`,
    { note }
  );
  return data;
}
