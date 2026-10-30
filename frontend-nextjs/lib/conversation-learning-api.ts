import { apiClient } from "./api-client";

export interface LearningReferenceCandidate {
  resource_id: string;
  dataset_name: string;
  original_file_name: string;
  sheet: string;
  source_version: string;
  status: string;
}

export interface LearningReview {
  candidate_id: string;
  status: string;
  revision: number;
  digest: string;
  review_ready: boolean;
  proposed_lesson: string;
  where_it_applies: {
    applies_to: string[];
    context: Record<string, unknown>;
  };
  referenced_data_and_versions: Array<{
    reference: string;
    relation: string;
    status: string;
    basis: string | null;
    resource_id: string | null;
    file_name: string | null;
    sheet: string | null;
    source_version: string | null;
    candidates: LearningReferenceCandidate[];
  }>;
  method_and_assumptions: {
    method_status: string;
    method: Record<string, any>;
  };
  exceptions: Array<Record<string, unknown>>;
  unresolved_questions: Array<{
    dependency_id: string;
    kind: string;
    status: string;
    question: string;
    resource_id: string | null;
  }>;
  supporting_messages: Array<{
    message_id: string;
    is_authority: boolean;
  }>;
  authority: {
    message_id: string;
    excerpt: string;
  };
  confirmed_by: string | null;
  confirmed_revision: number | null;
  rejected_by: string | null;
  rejected_reason: string;
  invalidated_reason: string;
  promoted_entry_id: string | null;
}

export interface LearningCandidatePayload {
  candidate: Record<string, any>;
  review: LearningReview;
  review_ready: boolean;
  blocking: Array<Record<string, any>>;
}

export interface LearningThread {
  thread_id: string;
  subject: string;
  message_count: number;
  last_at: string;
}

export interface LearningEmployee {
  id: string;
  name: string;
  status: string;
  category: string;
  role: string;
}

export async function listLearningEmployees(): Promise<LearningEmployee[]> {
  const { data } = await apiClient.get(
    "/api/conversation-learning/employees"
  );
  return data?.employees || [];
}

export async function listLearningThreads(): Promise<LearningThread[]> {
  const { data } = await apiClient.get(
    "/api/conversation-learning/threads"
  );
  return data?.threads || [];
}

export async function getConversationEvidence(
  threadId: string
): Promise<Record<string, any>> {
  const { data } = await apiClient.post("/api/conversation-learning/evidence", {
    thread_id: threadId,
  });
  return data;
}

export async function listLearningCandidates(
  threadId: string
): Promise<LearningCandidatePayload[]> {
  const { data } = await apiClient.get(
    `/api/conversation-learning/threads/${encodeURIComponent(threadId)}/candidates`
  );
  return data?.candidates || [];
}

export async function getLearningCandidate(
  threadId: string,
  candidateId: string
): Promise<LearningCandidatePayload> {
  const { data } = await apiClient.get(
    `/api/conversation-learning/candidates/${encodeURIComponent(candidateId)}`,
    { params: { thread_id: threadId } }
  );
  return data;
}

export async function createLearningCandidate(payload: {
  thread_id: string;
  agent_id: string;
  proposed_lesson: string;
  method?: Record<string, any>;
  method_status?: string;
  applies_to?: string[];
  context?: Record<string, any>;
  references?: Array<Record<string, any>>;
  authority_message_id?: string;
  authority_excerpt?: string;
}): Promise<LearningCandidatePayload> {
  const { data } = await apiClient.post(
    "/api/conversation-learning/candidates",
    payload
  );
  return data;
}

export async function resolveLearningDependency(
  threadId: string,
  candidateId: string,
  payload: {
    dependency_id: string;
    resource_id?: string;
    column?: string;
    unit?: string;
    value?: unknown;
    confirmed_by?: string;
  }
): Promise<LearningCandidatePayload> {
  const { data } = await apiClient.post(
    `/api/conversation-learning/candidates/${encodeURIComponent(candidateId)}/resolve`,
    { thread_id: threadId, ...payload }
  );
  return data;
}

export async function confirmLearningCandidate(
  threadId: string,
  candidateId: string,
  reviewer: string,
  expectedRevision: number
): Promise<LearningCandidatePayload> {
  const { data } = await apiClient.post(
    `/api/conversation-learning/candidates/${encodeURIComponent(candidateId)}/confirm`,
    {
      thread_id: threadId,
      reviewer,
      expected_revision: expectedRevision,
    }
  );
  return data;
}

export async function promoteLearningCandidate(
  threadId: string,
  candidateId: string,
  reviewer: string,
  expectedRevision: number,
  expectedDigest: string
): Promise<{ lesson_id: string; candidate: Record<string, any> }> {
  const { data } = await apiClient.post(
    `/api/conversation-learning/candidates/${encodeURIComponent(candidateId)}/promote`,
    {
      thread_id: threadId,
      reviewer,
      expected_revision: expectedRevision,
      expected_digest: expectedDigest,
    }
  );
  return data;
}

export async function applyLearningCandidate(
  threadId: string,
  candidateId: string,
  rows: Array<Record<string, unknown>>,
  fieldMapping: Record<string, string> = {},
  context: Record<string, unknown> = {}
): Promise<{ lesson_id: string; result: Record<string, any> }> {
  const { data } = await apiClient.post(
    `/api/conversation-learning/candidates/${encodeURIComponent(candidateId)}/apply`,
    {
      thread_id: threadId,
      rows,
      field_mapping: fieldMapping,
      context,
    }
  );
  return data;
}

export async function rejectLearningCandidate(
  threadId: string,
  candidateId: string,
  reviewer: string,
  reason = ""
): Promise<LearningCandidatePayload> {
  const { data } = await apiClient.post(
    `/api/conversation-learning/candidates/${encodeURIComponent(candidateId)}/reject`,
    { thread_id: threadId, reviewer, reason }
  );
  return data;
}
