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
  result_value?: string | null;
  result_unit?: string | null;
  result_measure?: string | null;
  prior_result_count?: number;
  artifact_revision: string | null;
  gap_ids: string[];
  waiting: Record<string, unknown>;
  approval_request: Record<string, unknown>;
  failure: Record<string, unknown>;
}

export interface AssignmentMapping {
  concept: string;
  sheet: string;
  column: string;
  unit: string;
  unit_authority: string;
  required_unit: string;
  source_unit: string;
  source_unit_column: string;
  source_version: string;
  revision: number;
  lesson_id: string | null;
  lesson_revision: number | null;
  teaching_revision: string;
  source: string | null;
  dataset_name: string | null;
  external_id: string | null;
  available_columns: string[];
  numeric_columns: string[];
  correctable: boolean;
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
    mappings: AssignmentMapping[];
    mapping_history: Record<string, unknown>[];
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

export interface AssignmentSource {
  dataset_name: string;
  sheet: string;
  file_name: string;
  source: string;
  external_id: string;
  source_version: string;
  kind: string;
  columns: string[];
  numeric_columns: string[];
  row_count: number;
  coverage: Record<string, unknown>;
  ingested_at?: string | null;
}

export interface AssignmentAgent {
  id: string;
  name: string;
  status?: string;
  category?: string;
}

export async function listAssignmentSources(
  query = ""
): Promise<AssignmentSource[]> {
  const { data } = await apiClient.get<AssignmentSource[]>(
    "/api/assignments/sources",
    { params: query ? { query } : undefined }
  );
  return data;
}

export async function listAssignmentAgents(): Promise<AssignmentAgent[]> {
  const { data } = await apiClient.get("/api/agents/");
  const rows = Array.isArray(data) ? data : data?.data || [];
  return rows.map((row: Record<string, unknown>) => ({
    id: String(row.id || ""),
    name: String(row.name || row.id || "Employee"),
    status: row.status ? String(row.status) : undefined,
    category: row.category ? String(row.category) : undefined,
  })).filter((row: AssignmentAgent) => row.id);
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

export async function correctAssignmentMapping(
  runId: string,
  payload: {
    concept: string;
    expected_revision: number;
    column: string;
    unit?: string;
    evidence?: string;
    sheet?: string;
    source_version?: string;
  }
): Promise<AssignmentDetail> {
  const { data } = await apiClient.post<AssignmentDetail>(
    `/api/assignments/${encodeURIComponent(runId)}/mappings/correct`,
    payload
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

export async function downloadAssignmentDeliverable(
  runId: string,
  deliverableId: string
): Promise<{ blob: Blob; filename: string }> {
  const response = await apiClient.get(
    `/api/assignments/${encodeURIComponent(runId)}/deliverables/${encodeURIComponent(deliverableId)}/download`,
    { responseType: "blob" }
  );
  const disposition = String(response.headers?.["content-disposition"] || "");
  const match = disposition.match(/filename=\"?([^\";]+)\"?/i);
  return {
    blob: response.data as Blob,
    filename: match?.[1] || "assignment-artifact",
  };
}
