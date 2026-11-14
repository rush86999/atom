/**
 * Verified Skill Builder package deletion — the single web client for
 * `DELETE /api/admin/skills/{skill_id}?operation_id=...`.
 *
 * The backend route (backend/api/admin/skill_routes.py ->
 * core.skill_package_delete_service.delete_skill_package_verified) moves the
 * package out of the consumable tree, purges the quarantine and re-reads both
 * before it answers. The response contract is:
 *
 *   200 { success: true,
 *         data: { skill_id, name, deleted, outcome, effects {
 *                   package, quarantine, pre_files }, ... },
 *         metadata: { operation_id, audit_id, target_id, verification } }
 *       verification.status: "verified" | "already_applied" | "no_change"
 *   503 { detail: { error: { code }, verification, operation_id, audit_id,
 *                   target_id, data } }
 *       verification.effect: "partial" | "unknown",
 *       verification.replay: "do_not_repeat"
 *   409 { detail: { error: { code }, verification, operation_id, audit_id } }
 *       not applied: verification.replay === "safe_same_operation"
 *       operation conflict: code OPERATION_CONFLICT / AUTHORITY_CHANGED
 *   404 / 400 / 401 / 403 / 422 { detail: { error, verification } }
 *
 * Only an explicit success whose receipt names THIS package, THIS operation
 * and whose verification plus filesystem effects are confirmed is reported as
 * a deletion. A partial/unknown outcome is a typed, non-retryable failure:
 * this client never repeats the mutation, because the backend cannot
 * distinguish "quarantine purge failed" from "the request was lost after the
 * rename". The operation id is therefore supplied by the caller and stays
 * stable for an uncertain outcome — a later reconciliation replays the SAME
 * operation (the backend resumes a pending receipt instead of creating a
 * second one).
 */

type JsonRecord = Record<string, unknown>;

export const SKILL_PACKAGE_OPERATION_PREFIX = "skill-package:delete:";
const SAFE_OPERATION_RE = /^[A-Za-z0-9:_-]{1,180}$/;

export type SkillPackageDeleteConfirmed = "deleted" | "already_removed";

export type SkillPackageDeleteFailure =
  | "partial"
  | "unknown"
  | "not_applied"
  | "conflict"
  | "not_found"
  | "failed";

/**
 * What the operator may do next:
 * - ``same_operation``: nothing was applied; retrying with the SAME id is safe.
 * - ``do_not_repeat``: effect uncertain; reconcile (refresh) before any retry.
 * - ``new_operation``: refused before any effect; a later attempt needs a new id.
 */
export type SkillPackageDeleteReplay =
  | "same_operation"
  | "do_not_repeat"
  | "new_operation";

export interface SkillPackageDeleteReceipt {
  /** ``deleted`` only after a fresh, verified readback of both paths. */
  outcome: SkillPackageDeleteConfirmed;
  /** Exact normalized package id the server receipt was bound to. */
  skillId: string;
  operationId: string;
}

const REPLAY_BY_OUTCOME: Record<SkillPackageDeleteFailure, SkillPackageDeleteReplay> = {
  partial: "do_not_repeat",
  unknown: "do_not_repeat",
  not_applied: "same_operation",
  conflict: "new_operation",
  not_found: "new_operation",
  failed: "new_operation",
};

export class SkillPackageDeleteError extends Error {
  /**
   * Uncertain/refused mutations must never be replayed automatically by the
   * shared axios interceptor, a component effect, or an unconfirmed retry.
   */
  readonly retryable = false;
  readonly outcome: SkillPackageDeleteFailure;
  readonly replay: SkillPackageDeleteReplay;
  declare readonly status?: number;
  declare readonly operationId?: string;
  declare readonly auditId?: string;

  constructor(details: {
    outcome: SkillPackageDeleteFailure;
    status?: number;
    operationId?: string;
    auditId?: string;
  }) {
    super(skillPackageDeleteFailureMessage(details.outcome));
    this.name = "SkillPackageDeleteError";
    Object.setPrototypeOf(this, SkillPackageDeleteError.prototype);
    this.outcome = details.outcome;
    this.replay = REPLAY_BY_OUTCOME[details.outcome];
    if (details.status !== undefined) this.status = details.status;
    if (details.operationId !== undefined) this.operationId = details.operationId;
    if (details.auditId !== undefined) this.auditId = details.auditId;
  }
}

/** Safe, outcome-specific copy shared by the page and tests. */
export function skillPackageDeleteFailureMessage(
  outcome: SkillPackageDeleteFailure,
): string {
  switch (outcome) {
    case "partial":
      return "The skill package deletion is only partly verified. Do not repeat it; refresh to check what remains.";
    case "unknown":
      return "The deletion outcome is unknown. Do not repeat it; refresh to check whether the package is gone.";
    case "not_applied":
      return "The skill package was not deleted; nothing changed. You can retry this same operation safely.";
    case "conflict":
      return "This deletion was refused because its operation is already bound to different work. Refresh and start a new deletion.";
    case "not_found":
      return "This skill package was not found. It may already have been deleted.";
    default:
      return "The skill package could not be deleted. Refresh before trying again.";
  }
}

/** Truthful success copy for a confirmed receipt. */
export function skillPackageDeleteSuccessMessage(
  outcome: SkillPackageDeleteConfirmed,
): string {
  return outcome === "deleted"
    ? "Skill package deleted."
    : "Skill package was already deleted.";
}

/** Canonicalize a caller-supplied id the same way the backend does. */
export function canonicalSkillPackageOperationId(value: unknown): string {
  const supplied = typeof value === "string" ? value.trim() : "";
  return supplied.startsWith(SKILL_PACKAGE_OPERATION_PREFIX)
    ? supplied
    : `${SKILL_PACKAGE_OPERATION_PREFIX}${supplied}`;
}

/**
 * A fresh operation id for one delete intention.
 *
 * Callers must persist it before dispatching and reuse it for every retry of
 * the same intention (the backend keys its durable receipt on this id).
 */
export function newSkillPackageDeleteOperationId(): string {
  const cryptoObject = (globalThis as {
    crypto?: { randomUUID?: () => string };
  }).crypto;
  if (cryptoObject && typeof cryptoObject.randomUUID === "function") {
    return `${SKILL_PACKAGE_OPERATION_PREFIX}${cryptoObject
      .randomUUID()
      .replace(/-/g, "")}`;
  }
  const random = Math.random().toString(16).slice(2);
  const random2 = Math.random().toString(16).slice(2);
  return `${SKILL_PACKAGE_OPERATION_PREFIX}${Date.now().toString(16)}${random}${random2}`;
}

/**
 * Client-side mirror of the backend's package-name canonicalization
 * (`core.skill_builder_service.normalize_skill_name`). It exists only to bind
 * a receipt to the intended package; it never selects a path.
 */
export function normalizeSkillPackageId(value: unknown): string {
  return String(value ?? "")
    .split("")
    .filter((character) => /[A-Za-z0-9_-]/.test(character))
    .join("")
    .toLowerCase();
}

const CONFIRMED_VERIFICATION = new Set([
  "verified",
  "already_applied",
  "no_change",
]);

/** The service only calls an outcome verified when both paths are gone. */
const RETIRED_PACKAGE_EFFECTS = new Set(["retired", "absent"]);
const PURGED_QUARANTINE_EFFECTS = new Set(["deleted", "absent"]);

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

function transportError(error: unknown): SkillPackageDeleteError {
  const status = errorStatus(error);
  if (status === undefined) {
    // No response at all: the request may have reached the server, so the
    // effect is unknown and must not be retried automatically.
    return new SkillPackageDeleteError({ outcome: "unknown" });
  }

  const body = asDetail(
    (error as { response?: { data?: unknown } })?.response?.data,
  );
  const verification = asRecord(body?.verification);
  const code = asRecord(body?.error)?.code;
  const operationId = opaqueIdentity(body?.operation_id);
  const auditId = opaqueIdentity(body?.audit_id);

  if (status === 503) {
    const effect = verification?.effect;
    const verificationStatus = verification?.status;
    // A refusal raised before any intent (e.g. AUTHORITY_UNAVAILABLE) says
    // effect=none explicitly; that is a known no-op, not an unknown outcome.
    if (effect === "none" && verificationStatus === "not_attempted") {
      return new SkillPackageDeleteError({
        outcome: "failed",
        status,
        operationId,
        auditId,
      });
    }
    // The route separates "committed but unverified" from "confirmation
    // lost". Only an explicit partial receipt is partial; a bare proxy 503
    // proves nothing about the mutation.
    if (
      code === "SKILL_PACKAGE_EFFECT_UNKNOWN" ||
      effect === "unknown"
    ) {
      return new SkillPackageDeleteError({
        outcome: "unknown",
        status,
        operationId,
        auditId,
      });
    }
    const committedUnverified =
      code === "SKILL_PACKAGE_DELETE_UNVERIFIED" ||
      effect === "partial" ||
      effect === "committed" ||
      verificationStatus === "committed_unverified";
    return new SkillPackageDeleteError({
      outcome: committedUnverified ? "partial" : "unknown",
      status,
      operationId,
      auditId,
    });
  }

  if (status === 404) {
    // A genuine absent package is a truthful "not found"; a contradictory
    // 404 that still carries do_not_repeat/unknown proves nothing.
    return new SkillPackageDeleteError({
      outcome: isContradictoryAbsence(body) ? "unknown" : "not_found",
      status,
      operationId,
      auditId,
    });
  }

  if (status === 409) {
    // ``not_applied`` means the rename was refused before any effect, so the
    // SAME operation id is safe to retry. Everything else is an operation
    // conflict or an authority change and needs a fresh intention.
    const replay = verification?.replay;
    if (
      replay === "safe_same_operation" ||
      code === "SKILL_PACKAGE_DELETE_NOT_APPLIED"
    ) {
      return new SkillPackageDeleteError({
        outcome: "not_applied",
        status,
        operationId,
        auditId,
      });
    }
    if (code === "OPERATION_CONFLICT" || code === "AUTHORITY_CHANGED") {
      return new SkillPackageDeleteError({
        outcome: "conflict",
        status,
        operationId,
        auditId,
      });
    }
    return new SkillPackageDeleteError({
      outcome: "failed",
      status,
      operationId,
      auditId,
    });
  }

  if (
    status === 400 ||
    status === 401 ||
    status === 403 ||
    status === 422
  ) {
    // The route refused before applying anything.
    return new SkillPackageDeleteError({
      outcome: "failed",
      status,
      operationId,
      auditId,
    });
  }

  // Any other server/proxy failure is ambiguous: the mutation may have
  // landed before the error was produced.
  return new SkillPackageDeleteError({
    outcome: "unknown",
    status,
    operationId,
    auditId,
  });
}

function interpretSuccess(
  status: number | undefined,
  data: unknown,
  skillId: string,
  operationId: string,
): SkillPackageDeleteReceipt {
  const body = asRecord(data);
  const metadata = asRecord(body?.metadata);
  const payload = asRecord(body?.data);
  // The route always emits its receipt under `metadata`; read identity,
  // operation binding and verification from there only, so a malformed
  // payload cannot mask a missing/foreign receipt. `target_id` is a keyed
  // digest of tenant+package (never the name), so it is verified as opaque
  // material and identity is bound through `data.skill_id`/`name`.
  const verification = asRecord(metadata?.verification);
  const verificationStatus = opaqueIdentity(verification?.status);
  const payloadId =
    opaqueIdentity(payload?.skill_id) ?? opaqueIdentity(payload?.name);
  const payloadOperation = opaqueIdentity(payload?.operation_id);
  const effects = asRecord(payload?.effects);
  const expectedPackage = normalizeSkillPackageId(skillId);

  const confirmed =
    body?.success === true &&
    status !== undefined &&
    status >= 200 &&
    status < 300 &&
    metadata !== undefined &&
    opaqueIdentity(metadata.operation_id) === operationId &&
    opaqueIdentity(metadata.target_id) !== undefined &&
    payload !== undefined &&
    (payloadOperation === undefined || payloadOperation === operationId) &&
    payloadId !== undefined &&
    normalizeSkillPackageId(payloadId) === expectedPackage &&
    payload?.deleted === true &&
    effects !== undefined &&
    RETIRED_PACKAGE_EFFECTS.has(String(effects.package)) &&
    PURGED_QUARANTINE_EFFECTS.has(String(effects.quarantine)) &&
    verificationStatus !== undefined &&
    CONFIRMED_VERIFICATION.has(verificationStatus);

  if (!confirmed) {
    throw new SkillPackageDeleteError({ outcome: "unknown", status });
  }

  return {
    outcome: verificationStatus === "verified" ? "deleted" : "already_removed",
    skillId: expectedPackage,
    operationId,
  };
}

/**
 * Delete one published skill package through the verified backend route.
 *
 * Resolves only for a confirmed receipt (`deleted` or `already_removed`) and
 * throws a non-retryable `SkillPackageDeleteError` for every other outcome.
 * The caller owns `operationId`: keep it stable for an uncertain outcome so
 * reconciliation replays the same operation instead of creating a second one.
 */
export async function deleteSkillPackage(
  skillId: string,
  operationId: string,
): Promise<SkillPackageDeleteReceipt> {
  if (typeof skillId !== "string" || skillId.trim().length === 0) {
    throw new SkillPackageDeleteError({ outcome: "failed" });
  }
  if (typeof operationId !== "string" || operationId.trim().length === 0) {
    throw new SkillPackageDeleteError({ outcome: "failed" });
  }

  const canonicalOperationId = canonicalSkillPackageOperationId(operationId);
  if (!SAFE_OPERATION_RE.test(canonicalOperationId)) {
    throw new SkillPackageDeleteError({ outcome: "failed" });
  }

  let response: { status?: number; data?: unknown };
  try {
    const { apiClient } = await import("@/lib/api");
    response = await apiClient.delete(
      `/api/admin/skills/${encodeURIComponent(skillId)}`,
      {
        // The shared interceptor retries 5xx by default; a package delete is
        // not idempotent from the client's point of view.
        params: { operation_id: canonicalOperationId },
        retry: false,
        timeout: 30000,
      },
    );
  } catch (error) {
    throw transportError(error);
  }

  return interpretSuccess(
    response?.status,
    response?.data,
    skillId,
    canonicalOperationId,
  );
}
