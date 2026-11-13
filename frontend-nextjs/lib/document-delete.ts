/**
 * Verified knowledge-document deletion — the single web client for
 * `DELETE /api/documents/{doc_id}`.
 *
 * The backend route (backend/api/document_routes.py ->
 * core.document_delete_service.delete_document_verified) proves the effect by
 * reading back the vector base row, the `<doc_id>::` chunk family, the SQL
 * mirror/FTS row and the materialized file before it answers. That contract
 * is:
 *
 *   200 { success: true,
 *         data: { doc_id, deleted, complete, ... , verification },
 *         metadata: { operation_id, audit_id, target_id, verification } }
 *       verification.status: "verified" | "already_applied" | "no_change"
 *   503 { detail: { error: { code }, verification, operation_id, audit_id,
 *                   target_id, data } }
 *       verification.effect: "partial" | "unknown",
 *       verification.replay: "do_not_repeat"
 *   404 / 409 / 422 { detail: { error, verification } }   (not applied)
 *
 * Only an explicit success whose receipt names THIS document and whose
 * verification is confirmed is reported as a deletion. A partial/unknown
 * outcome is a typed, non-retryable failure: this client never repeats the
 * mutation, because the backend cannot distinguish "chunk cleanup failed"
 * from "the request was lost after the base row was removed". Both pages
 * render `deleteFailureMessage` verbatim so the user is told the truth
 * instead of a fabricated success.
 */

type JsonRecord = Record<string, unknown>;

export type DocumentDeleteConfirmed = "deleted" | "already_removed";

export type DocumentDeleteFailure =
  | "partial"
  | "unknown"
  | "not_found"
  | "failed";

export interface DocumentDeleteReceipt {
  /** ``deleted`` only after a fresh, verified readback of every surface. */
  outcome: DocumentDeleteConfirmed;
  /** Exact document id the server receipt was bound to. */
  docId: string;
}

export class DocumentDeleteError extends Error {
  /**
   * A mutation with a partial/unknown effect must never be replayed by the
   * shared axios interceptor, a component effect, or a retry button.
   */
  readonly retryable = false;
  readonly outcome: DocumentDeleteFailure;
  declare readonly status?: number;
  declare readonly operationId?: string;
  declare readonly auditId?: string;

  constructor(details: {
    outcome: DocumentDeleteFailure;
    status?: number;
    operationId?: string;
    auditId?: string;
  }) {
    super(deleteFailureMessage(details.outcome));
    this.name = "DocumentDeleteError";
    Object.setPrototypeOf(this, DocumentDeleteError.prototype);
    this.outcome = details.outcome;
    if (details.status !== undefined) this.status = details.status;
    if (details.operationId !== undefined) this.operationId = details.operationId;
    if (details.auditId !== undefined) this.auditId = details.auditId;
  }
}

/** Safe, outcome-specific copy shared by both document surfaces and tests. */
export function deleteFailureMessage(outcome: DocumentDeleteFailure): string {
  switch (outcome) {
    case "partial":
      return "The document deletion is only partly verified. Do not repeat it; refresh to check what remains.";
    case "unknown":
      return "The deletion outcome is unknown. Do not repeat it; refresh to check whether the document is gone.";
    case "not_found":
      return "This document was not found. It may already have been deleted.";
    default:
      return "The document could not be deleted. Refresh before trying again.";
  }
}

/** Truthful success copy for a confirmed receipt. */
export function deleteSuccessMessage(outcome: DocumentDeleteConfirmed): string {
  return outcome === "deleted"
    ? "Document deleted."
    : "Document was already deleted.";
}

const CONFIRMED_VERIFICATION = new Set([
  "verified",
  "already_applied",
  "no_change",
]);

function asRecord(value: unknown): JsonRecord | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : undefined;
}

function opaqueIdentity(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function asDetail(value: unknown): JsonRecord | undefined {
  const body = asRecord(value);
  return asRecord(body?.detail) ?? body;
}

function errorStatus(error: unknown): number | undefined {
  const candidate = (error as { response?: { status?: unknown } })?.response
    ?.status;
  return typeof candidate === "number" ? candidate : undefined;
}

function isContradictoryAbsence(body: JsonRecord | undefined): boolean {
  const verification = asRecord(body?.verification);
  return (
    body?.replay === "do_not_repeat" ||
    verification?.replay === "do_not_repeat" ||
    verification?.effect === "unknown" ||
    verification?.effect === "committed"
  );
}

function transportError(error: unknown): DocumentDeleteError {
  const status = errorStatus(error);
  if (status === undefined) {
    // No response at all: the request may have reached the server, so the
    // effect is unknown and must not be retried automatically.
    return new DocumentDeleteError({ outcome: "unknown" });
  }

  const body = asDetail(
    (error as { response?: { data?: unknown } })?.response?.data,
  );
  const verification = asRecord(body?.verification);
  const operationId = opaqueIdentity(body?.operation_id);
  const auditId = opaqueIdentity(body?.audit_id);

  if (status === 503) {
    const code = asRecord(body?.error)?.code;
    const effect = verification?.effect;
    const verificationStatus = verification?.status;
    // The route separates "committed but unverified" from "confirmation
    // lost". Only an explicit partial receipt is partial; a bare proxy 503
    // proves nothing about the mutation.
    const committedUnverified =
      code === "DOCUMENT_DELETE_UNVERIFIED" ||
      effect === "partial" ||
      effect === "committed" ||
      verificationStatus === "committed_unverified";
    if (code === "DOCUMENT_EFFECT_UNKNOWN" || effect === "unknown") {
      return new DocumentDeleteError({
        outcome: "unknown",
        status,
        operationId,
        auditId,
      });
    }
    return new DocumentDeleteError({
      outcome: committedUnverified ? "partial" : "unknown",
      status,
      operationId,
      auditId,
    });
  }

  if (status === 404) {
    // A genuine absent document is a truthful "not found"; a contradictory
    // 404 that still carries do_not_repeat/unknown proves nothing.
    return new DocumentDeleteError({
      outcome: isContradictoryAbsence(body) ? "unknown" : "not_found",
      status,
      operationId,
      auditId,
    });
  }

  if (status === 400 || status === 401 || status === 403 || status === 409 || status === 422) {
    // The route refused or conflicted before applying anything.
    return new DocumentDeleteError({ outcome: "failed", status, operationId, auditId });
  }

  // Any other server/proxy failure is ambiguous: the mutation may have
  // landed before the error was produced.
  return new DocumentDeleteError({ outcome: "unknown", status, operationId, auditId });
}

function interpretSuccess(
  status: number | undefined,
  data: unknown,
  docId: string,
): DocumentDeleteReceipt {
  const body = asRecord(data);
  const metadata = asRecord(body?.metadata);
  const payload = asRecord(body?.data);
  const verification =
    asRecord(metadata?.verification) ?? asRecord(payload?.verification);
  const verificationStatus = opaqueIdentity(verification?.status);

  const targetId =
    opaqueIdentity(metadata?.target_id) ?? opaqueIdentity(payload?.doc_id);
  const payloadIdentity = payload?.doc_id;
  const payloadMatches =
    payloadIdentity === undefined || payloadIdentity === docId;

  const confirmed =
    body?.success === true &&
    status !== undefined &&
    status >= 200 &&
    status < 300 &&
    verificationStatus !== undefined &&
    CONFIRMED_VERIFICATION.has(verificationStatus) &&
    targetId === docId &&
    payloadMatches &&
    // A "verified" receipt must also claim the cleanup completed; anything
    // else is a partial outcome that the route should already have refused.
    (verificationStatus !== "verified" || payload?.complete === true);

  if (!confirmed) {
    throw new DocumentDeleteError({ outcome: "unknown", status });
  }

  return {
    outcome: verificationStatus === "verified" ? "deleted" : "already_removed",
    docId,
  };
}

/**
 * Delete one document through the verified backend route.
 *
 * Resolves only for a confirmed receipt (`deleted` or `already_removed`) and
 * throws a non-retryable `DocumentDeleteError` for every other outcome.
 * Callers must not automatically call this again after `partial`/`unknown`.
 */
export async function deleteDocument(
  docId: string,
): Promise<DocumentDeleteReceipt> {
  if (typeof docId !== "string" || docId.length === 0) {
    throw new DocumentDeleteError({ outcome: "failed" });
  }

  let response: { status?: number; data?: unknown };
  try {
    const { apiClient } = await import("@/lib/api");
    response = await apiClient.delete(
      `/api/documents/${encodeURIComponent(docId)}`,
      {
        // The shared interceptor retries 5xx by default; a document delete
        // is not idempotent from the client's point of view.
        retry: false,
        timeout: 30000,
      },
    );
  } catch (error) {
    throw transportError(error);
  }

  return interpretSuccess(response?.status, response?.data, docId);
}
