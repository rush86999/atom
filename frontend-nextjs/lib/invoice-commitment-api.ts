/**
 * Client for the published invoice-commitment route.
 *
 * GET  /api/assignments/{encoded_run}/invoice-commitment/{encoded_step}
 * PUT  /api/assignments/{encoded_run}/invoice-commitment/{encoded_step}
 *
 * Requests go through the shared named apiClient, which owns session and
 * bearer handling. Writes never retry here: the review UI decides how to
 * recover.
 */

import { apiClient } from "@/lib/api-client";

export type InvoiceCommitmentVerdict =
  | "confirmed"
  | "no_commitment"
  | "unclear";

export interface InvoiceCommitmentSource {
  operation_id?: string | null;
  reply_operation_id?: string | null;
  reply_message_id?: string | null;
  [key: string]: unknown;
}

export interface InvoiceCommitmentRevision {
  kind?: string;
  revision: number;
  step_id?: string;
  verdict: InvoiceCommitmentVerdict | string;
  commitment_date?: string | null;
  reason?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  operation_id?: string | null;
  reply_operation_id?: string | null;
  reply_message_id?: string | null;
  source?: InvoiceCommitmentSource | null;
  [key: string]: unknown;
}

export interface InvoiceCommitmentRead {
  run_id: string;
  step_id: string;
  revision: number;
  current: InvoiceCommitmentRevision | null;
  history: InvoiceCommitmentRevision[];
  [key: string]: unknown;
}

export interface InvoiceCommitmentWrite {
  expected_revision: number;
  verdict: InvoiceCommitmentVerdict;
  commitment_date: string | null;
  reason: string | null;
  expected_reply_id?: string;
}

export interface InvoiceCommitmentClient {
  read(
    runId: string,
    stepId: string,
  ): Promise<InvoiceCommitmentRead>;
  write(
    runId: string,
    stepId: string,
    body: InvoiceCommitmentWrite,
  ): Promise<InvoiceCommitmentRead>;
}

export function isInvoiceCommitmentConflict(error: unknown): boolean {
  const anyError = error as any;
  return (
    anyError?.status === 409 ||
    anyError?.response?.status === 409 ||
    anyError?.technical?.response?.status === 409
  );
}

export function invoiceCommitmentErrorMessage(
  error: unknown,
  fallback: string,
): string {
  const anyError = error as any;
  const raw =
    anyError?.response?.data ||
    anyError?.technical?.response?.data ||
    anyError?.data;
  const detail = raw?.detail ?? raw;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && detail.message) {
    return String(detail.message);
  }
  if (anyError?.message) return String(anyError.message);
  return fallback;
}

export function invoiceCommitmentPath(
  runId: string,
  stepId: string,
): string {
  return (
    `/api/assignments/${encodeURIComponent(runId)}` +
    `/invoice-commitment/${encodeURIComponent(stepId)}`
  );
}

export const invoiceCommitmentClient: InvoiceCommitmentClient = {
  async read(runId, stepId) {
    const response = await apiClient.get<InvoiceCommitmentRead>(
      invoiceCommitmentPath(runId, stepId),
    );
    return response.data;
  },
  async write(runId, stepId, body) {
    const response = await apiClient.put<InvoiceCommitmentRead>(
      invoiceCommitmentPath(runId, stepId),
      body,
      { retry: false },
    );
    return response.data;
  },
};
