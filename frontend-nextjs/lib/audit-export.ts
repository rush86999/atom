/**
 * Bounded evidence export for one authorized audit execution.
 *
 * The download is a literal copy of the rows the audit read already returned
 * for this subject. It is deliberately NOT presented as tamper-proof,
 * certified or complete: `saas_audit_logs` has no signature or hash chain, and
 * the read scope (own rows / current workspace) bounds what is included.
 */

import { ExecutionTimeline, ReadScope } from "./audit-api";

export const AUDIT_EVIDENCE_FORMAT = "atom.audit.evidence.bounded_copy.v1";

export const AUDIT_EVIDENCE_LIMITS =
    "Unsigned, bounded copy of the audit rows returned by the authorized read. " +
    "No signature or hash chain exists, so this file is not tamper-evident and " +
    "is not a completeness certificate. It contains only rows in the exporting " +
    "user's read scope; it is not a full-system export.";

export interface AuditEvidenceBundle {
    format: string;
    generated_at: string;
    source_app_version: string;
    execution_id: string;
    read_scope: ReadScope | null;
    filter_window: { start: string | null; end: string | null };
    row_count: number;
    rows: ExecutionTimeline["events"];
    execution: ExecutionTimeline["execution"];
    counts: ExecutionTimeline["counts"];
    integrity: {
        signed: false;
        hash_chain: false;
        tamper_evident: false;
        completeness_certified: false;
        statement: string;
    };
    coverage: {
        found_events: boolean;
        scope_note: string;
        note: string;
    };
}

/**
 * Build the evidence bundle from the SAME timeline payload the UI rendered —
 * no re-fetch, no re-derivation of row contents, so export fidelity is exact
 * for `rows`.
 */
export function buildAuditEvidenceBundle(
    timeline: ExecutionTimeline,
    options: { generatedAt?: string; appVersion?: string } = {},
): AuditEvidenceBundle {
    const timestamps = timeline.events
        .map((event) => event.timestamp)
        .filter((value): value is string => Boolean(value))
        .sort();

    return {
        format: AUDIT_EVIDENCE_FORMAT,
        generated_at: options.generatedAt || new Date().toISOString(),
        source_app_version: options.appVersion || "unknown",
        execution_id: timeline.execution_id,
        read_scope: timeline.read_scope || null,
        filter_window: {
            start: timestamps.length ? timestamps[0] : null,
            end: timestamps.length ? timestamps[timestamps.length - 1] : null,
        },
        row_count: timeline.events.length,
        rows: timeline.events,
        execution: timeline.execution,
        counts: timeline.counts,
        integrity: {
            signed: false,
            hash_chain: false,
            tamper_evident: false,
            completeness_certified: false,
            statement: AUDIT_EVIDENCE_LIMITS,
        },
        coverage: {
            found_events: timeline.found_events,
            scope_note:
                timeline.read_scope?.note ||
                "Scope is bounded by the authorized audit read that produced these rows.",
            note:
                "Row count/filter window describe THIS payload only. Missing rows " +
                "may mean no event was recorded, the run predates per-event " +
                "auditing, or the subject is outside the reader's scope.",
        },
    };
}

export function evidenceFilename(executionId: string, generatedAt: string): string {
    const safeId = String(executionId || "execution").replace(/[^A-Za-z0-9._:-]/g, "_");
    const safeTime = String(generatedAt || "")
        .replace(/[:.]/g, "-")
        .replace(/[^0-9TZ-]/gi, "");
    return `audit-evidence-${safeId}-${safeTime || "unknown-time"}.json`;
}

/** Serialize exactly what the download writes (also used by fidelity tests). */
export function serializeAuditEvidenceBundle(bundle: AuditEvidenceBundle): string {
    return JSON.stringify(bundle, null, 2);
}

/**
 * Trigger the browser download. Returns the serialized JSON so callers/tests
 * can assert the exact bytes without depending on a DOM download hook.
 */
export function downloadAuditEvidenceBundle(
    bundle: AuditEvidenceBundle,
    filename?: string,
): string {
    const json = serializeAuditEvidenceBundle(bundle);
    if (typeof window === "undefined" || typeof document === "undefined") {
        return json;
    }
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || evidenceFilename(bundle.execution_id, bundle.generated_at);
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return json;
}
