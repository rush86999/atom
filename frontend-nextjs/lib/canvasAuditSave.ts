/**
 * Persist a canvas edit to the append-only canvas audit trail
 * (PUT /api/canvas/{id}) — the store the /canvas/{id} page reads, the
 * websocket broadcast updates, and the chat co-editor plans against.
 * Saving anywhere else (the legacy artifacts store) makes the edit
 * invisible to all three, so the next co-edit silently reverts it.
 *
 * Content is the canvas type's NATIVE shape: dict for email drafts
 * ({to, cc, subject, body}), list-of-rows for sheets, plain string for
 * markdown/code/document bodies. The backend stores it verbatim.
 *
 * A truthy return means the server explicitly confirmed THIS canvas: a
 * success flag, an exact canvas_id match, and a verified audit receipt.
 * A genuine 404 returns false for legacy-artifact compatibility. Every
 * other unconfirmed/malformed outcome throws a non-retryable typed error
 * so callers cannot mistake it for a save and fall through to the legacy
 * artifacts store.
 */

export interface CanvasAuditSaveErrorDetails {
    status?: number;
    operationId?: string;
    auditId?: string;
}

/**
 * Safe, non-retryable failure for an audit save whose success the server
 * did not prove. It intentionally carries no raw response body, server
 * message, SQL, or transport exception.
 */
export class CanvasAuditSaveError extends Error {
    readonly retryable = false;
    readonly code = "CANVAS_AUDIT_UNCONFIRMED";
    declare readonly status?: number;
    declare readonly operationId?: string;
    declare readonly auditId?: string;
    declare readonly operation_id?: string;
    declare readonly audit_id?: string;

    constructor(details: CanvasAuditSaveErrorDetails = {}) {
        super("Canvas save could not be confirmed. Your edits were not verified.");
        this.name = "CanvasAuditSaveError";
        Object.setPrototypeOf(this, CanvasAuditSaveError.prototype);

        if (details.status !== undefined) this.status = details.status;
        if (details.operationId !== undefined) {
            this.operationId = details.operationId;
            this.operation_id = details.operationId;
        }
        if (details.auditId !== undefined) {
            this.auditId = details.auditId;
            this.audit_id = details.auditId;
        }
    }
}

/** A confirmed receipt from a stricter canvas audit save. */
export interface CanvasAuditReceipt {
    /** Server-issued canvas audit id: an exact, non-empty string. */
    auditId: string;
    /** Server-issued operation id when the receipt carries one. */
    operationId?: string;
}

type JsonRecord = Record<string, unknown>;

function asRecord(value: unknown): JsonRecord | undefined {
    return value !== null && typeof value === "object" && !Array.isArray(value)
        ? (value as JsonRecord)
        : undefined;
}

function opaqueIdentity(value: unknown): string | undefined {
    return typeof value === "string" && value.length > 0 ? value : undefined;
}

function isLegacyNotFound(status: number | undefined, data: unknown): boolean {
    if (status !== 404) return false;
    const body = asRecord(data);
    const verification = asRecord(body?.verification);
    return body?.replay !== "do_not_repeat"
        && verification?.effect !== "unknown"
        && verification?.effect !== "committed";
}

function isVerifiedResponse(data: unknown, canvasId: string): boolean {
    const body = asRecord(data);
    if (!body) return false;
    if (body.success !== true) return false;
    if (body.canvas_id !== canvasId) return false;

    const verification = asRecord(body.verification);
    return verification?.status === "verified";
}

function errorStatus(error: unknown): number | undefined {
    const candidate = (error as { response?: { status?: unknown }; status?: unknown })
        ?.response?.status ?? (error as { status?: unknown })?.status;
    return typeof candidate === "number" ? candidate : undefined;
}

function unconfirmedError(data: unknown, status?: number): CanvasAuditSaveError {
    const body = asRecord(data);
    // Existing server receipt fields are opaque identities, never guessed
    // from aliases or converted from numbers.
    const operationId = opaqueIdentity(body?.operation_id);
    const auditId = opaqueIdentity(body?.audit_id);

    return new CanvasAuditSaveError({ status, operationId, auditId });
}

interface CanvasAuditTransportOptions {
    retype?: boolean;
    expectedPriorAuditId?: string;
}

interface CanvasAuditTransportResult {
    data: unknown;
    status?: number;
    verified: boolean;
}

/**
 * Single transport for canvas audit saves. Returns null only for the
 * genuine legacy-artifact 404; every other unconfirmed outcome throws.
 */
async function putCanvasAudit(
    canvasId: string,
    canvasType: string,
    title: string | undefined,
    content: unknown,
    options: CanvasAuditTransportOptions = {}
): Promise<CanvasAuditTransportResult | null> {
    if (options.expectedPriorAuditId !== undefined
        && (typeof options.expectedPriorAuditId !== "string" || options.expectedPriorAuditId.length === 0)) {
        throw new CanvasAuditSaveError();
    }
    try {
        const { apiClient } = await import("@/lib/api");
        // JSON-encode EXPLICITLY: axios passes bare strings/arrays through
        // unserialized, and the backend's `content: Any = Body(...)` only
        // accepts a JSON document.
        const response = await apiClient.put(
            `/api/canvas/${encodeURIComponent(canvasId)}` +
            `?canvas_type=${encodeURIComponent(canvasType)}` +
            `&title=${encodeURIComponent(title || "")}` +
            (options.retype ? "&retype=true" : "") +
            // Bind only an explicitly provided prior audit id; never infer
            // it from counters or normalize its value.
            (options.expectedPriorAuditId !== undefined
                ? `&expected_prior_audit_id=${encodeURIComponent(options.expectedPriorAuditId)}`
                : ""),
            JSON.stringify(content),
            {
                headers: { "Content-Type": "application/json" },
                // Canvas mutations must never be replayed by the shared
                // axios retry interceptor: a retried 503 can duplicate an
                // audit row after an ambiguous transport failure.
                retry: false,
            }
        );

        // Legacy artifact ids are not canvas ids; keep the historical
        // legacy-fallback outcome for the caller.
        if (isLegacyNotFound(response?.status, response?.data)) return null;

        const status = typeof response?.status === "number" ? response.status : undefined;
        if (status !== undefined && (status < 200 || status >= 300)) {
            throw unconfirmedError(response?.data, status);
        }

        return {
            data: response?.data,
            status,
            verified: isVerifiedResponse(response?.data, canvasId),
        };
    } catch (error) {
        if (error instanceof CanvasAuditSaveError) throw error;

        const status = errorStatus(error);
        if (isLegacyNotFound(status, (error as {response?: {data?: unknown}})?.response?.data)) return null;

        throw unconfirmedError(
            (error as { response?: { data?: unknown } })?.response?.data,
            status
        );
    }
}

export async function saveCanvasAudit(
    canvasId: string,
    canvasType: string,
    title: string | undefined,
    content: unknown,
    options: { retype?: boolean } = {}
): Promise<boolean> {
    const result = await putCanvasAudit(canvasId, canvasType, title, content, options);
    if (result === null) return false;
    if (result.verified) return true;

    // Legacy bool contract: an exact-canvas verified response is enough;
    // no audit receipt (audit_id) is required on this path.
    throw unconfirmedError(result.data, result.status);
}

/**
 * Stricter canvas audit save that returns the server's canonical receipt.
 * Returns null only for the genuine legacy-artifact 404; a verified
 * response without an exact, non-empty audit_id is unconfirmed.
 */
export async function saveCanvasAuditReceipt(
    canvasId: string,
    canvasType: string,
    title: string | undefined,
    content: unknown,
    options: {
        retype?: boolean;
        expectedPriorAuditId?: string;
    } = {}
): Promise<CanvasAuditReceipt | null> {
    const result = await putCanvasAudit(canvasId, canvasType, title, content, options);
    if (result === null) return null;

    if (!result.verified) {
        throw unconfirmedError(result.data, result.status);
    }

    const body = asRecord(result.data);
    const auditId = opaqueIdentity(body?.audit_id);
    if (auditId === undefined) {
        // Stricter receipt path: a verified response without an exact,
        // non-empty audit_id is unconfirmed.
        throw unconfirmedError(result.data, result.status);
    }

    const operationId = opaqueIdentity(body?.operation_id);
    return operationId === undefined
        ? { auditId }
        : { auditId, operationId };
}
