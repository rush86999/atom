/**
 * Agent Action Audit API client.
 *
 * Serves the read endpoints in backend/api/audit_routes.py — the per-decision
 * audit trail written by core/agent_action_audit.py — plus the correction
 * REQUEST link that reuses the existing reasoning-feedback persistence.
 *
 * NOTE: native fetch (not the shared apiClient) is used on purpose — the
 * repo's MSW test setup intercepts fetch but not axios' XHR adapter, so
 * apiClient calls hang in Jest (same reason as AgentHistoryTable).
 */

export interface ModelIdentity {
    recorded_label: string | null;
    label_kind: "router_tier_or_alias" | "unknown" | string;
    served_model: string | null;
    provider: string | null;
    provenance: "recorded_label_only" | "unknown" | string;
    note: string;
}

export interface CorrectionTarget {
    channel: "activity" | "learning" | "assignment" | "autodev" | string;
    label: string;
    target_id: string;
    href: string | null;
}

export interface CorrectionReceipt {
    feedback_id: string | null;
    status: string;
    applied: boolean;
    verified: boolean;
    channel: string | null;
    target_id: string | null;
    /** How the target was established: recorded subject metadata vs caller-asserted. */
    channel_target_basis?: string | null;
    /** True only when the server recorded this exact channel/target for the subject. */
    repair_link_proven?: boolean | null;
    reason: string | null;
}

export interface AuditEvent {
    id: string;
    timestamp: string | null;
    event_type: "agent_action" | "llm_call" | string;
    action: string;
    description: string | null;
    agent_id: string | null;
    agent_execution_id: string | null;
    user_id: string | null;
    workspace_id: string | null;
    success: boolean;
    error_message: string | null;
    metadata: Record<string, unknown>;
    model_identity?: ModelIdentity | null;
    authority?: Record<string, unknown> | null;
    correction_targets?: CorrectionTarget[];
    correction?: CorrectionReceipt | null;
}

export interface UsageSummary {
    status: "recorded_estimate" | "partial" | "known_free" | "unavailable" | string;
    cost_usd: number | null;
    currency: string;
    basis: string;
    rows: number;
    priced_rows: number;
    unpriced_rows: number;
    total_tokens: number;
    note: string;
}

export interface VerificationSummary {
    status: string;
    basis: string;
    counts: Record<string, number>;
    evidence: Array<{ step_number: number; status: string; evidence: string }>;
    note: string;
}

export interface ReadScope {
    kind: "owner" | "workspace" | string;
    workspace_id: string;
    supervisor: boolean;
    note: string;
}

export interface ExecutionSummary {
    execution_id: string | null;
    agent_id: string | null;
    started_at: string | null;
    status: string;
    completed_at: string | null;
    task_input?: string | null;
    tool_calls: number;
    llm_calls: number;
    failed_events: number;
    correction_requests?: number;
    usage?: UsageSummary;
    verification?: string;
    outcome?: { status: string; basis: string; note: string };
}

export interface ExecutionTimeline {
    execution_id: string;
    found_events: boolean;
    execution: {
        id: string;
        agent_id?: string | null;
        status?: string | null;
        input_summary?: string | null;
        output_summary?: string | null;
        error_message?: string | null;
        started_at?: string | null;
        completed_at?: string | null;
        triggered_by?: string | null;
        task_input?: string | null;
        outcome?: { status: string | null; basis: string; verification: string; note: string };
        verification?: VerificationSummary;
        usage?: UsageSummary;
        model_identity?: {
            recorded_llm_call_labels: string[];
            execution_provenance: Record<string, unknown> | null;
            requested_models: string[];
            resolved_models: string[];
            note: string;
        };
        correction_targets?: CorrectionTarget[];
        correction_requests?: number;
    };
    events: AuditEvent[];
    counts: { tool_calls: number; llm_calls: number; failed_events: number };
    read_scope?: ReadScope;
    evidence_limits?: { signed: boolean; hash_chain: boolean; note: string };
}

export interface AuditSummaryStats {
    days: number;
    total_events: number;
    by_event_type: Record<string, number>;
    by_action: Record<string, number>;
    failures?: number;
    success_rate: number | null;
    distinct_agents: number;
    executions_tracked: number;
    generated_at: string;
    read_scope?: ReadScope;
}

export interface AuditEventsQuery {
    agent_id?: string;
    execution_id?: string;
    event_type?: string;
    success?: boolean;
    start?: string;
    end?: string;
    limit?: number;
    offset?: number;
}

export type AuditErrorKind =
    | "network"
    | "unauthorized"
    | "forbidden"
    | "not_found"
    | "invalid"
    | "server"
    | "unknown";

export class AuditApiError extends Error {
    kind: AuditErrorKind;
    status: number | null;
    code: string;

    constructor(
        message: string,
        options: { kind: AuditErrorKind; status?: number | null; code?: string },
    ) {
        super(message);
        this.name = "AuditApiError";
        this.kind = options.kind;
        this.status = options.status ?? null;
        this.code = options.code ?? options.kind;
    }
}

function classifyStatus(status: number): AuditErrorKind {
    if (status === 401) return "unauthorized";
    if (status === 403) return "forbidden";
    if (status === 404) return "not_found";
    if (status === 422 || status === 400) return "invalid";
    if (status >= 500) return "server";
    return "unknown";
}

async function readErrorDetail(resp: Response): Promise<{ code: string; message: string }> {
    try {
        const body = await resp.json();
        const detail = body?.detail;
        if (typeof detail === "string") {
            return { code: `http_${resp.status}`, message: detail };
        }
        if (detail && typeof detail === "object") {
            return {
                code: String(detail.code || `http_${resp.status}`),
                message: String(detail.message || detail.detail || `HTTP ${resp.status}`),
            };
        }
    } catch {
        // non-JSON error body — fall through to the status text
    }
    return {
        code: `http_${resp.status}`,
        message: resp.statusText || `HTTP ${resp.status}`,
    };
}

function authHeaders(): Record<string, string> {
    const token =
        typeof window !== "undefined"
            ? window.localStorage.getItem("auth_token") ||
              window.localStorage.getItem("token")
            : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
}

async function jsonRequest<T>(
    path: string,
    init: RequestInit & { params?: Record<string, string | number | boolean | undefined> } = {},
): Promise<T> {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
    const { params, ...fetchInit } = init;
    const qs = params
        ? new URLSearchParams(
              Object.entries(params)
                  .filter(([, v]) => v !== undefined && v !== "")
                  .map(([k, v]) => [k, String(v)]),
          ).toString()
        : "";
    const url = `${API_BASE}${path}${qs ? `?${qs}` : ""}`;

    let resp: Response;
    try {
        resp = await fetch(url, {
            ...fetchInit,
            headers: { ...authHeaders(), ...(fetchInit.headers || {}) },
        });
    } catch {
        throw new AuditApiError(
            "Could not reach the audit service.",
            { kind: "network", code: "network_unreachable", status: null },
        );
    }

    if (!resp.ok) {
        const detail = await readErrorDetail(resp);
        const kind = classifyStatus(resp.status);
        throw new AuditApiError(detail.message, {
            kind,
            status: resp.status,
            code: detail.code,
        });
    }
    return resp.json() as Promise<T>;
}

async function auditFetch<T>(
    path: string,
    params?: Record<string, string | number | boolean | undefined>,
): Promise<T> {
    return jsonRequest<T>(path, { params });
}

export const auditAPI = {
    summary: (days = 7) => auditFetch<AuditSummaryStats>("/api/audit/summary", { days }),

    executions: (agent_id?: string, limit = 50, offset = 0) =>
        auditFetch<{ items: ExecutionSummary[]; total: number; read_scope?: ReadScope }>(
            "/api/audit/executions",
            { agent_id, limit, offset },
        ),

    timeline: (executionId: string) =>
        auditFetch<ExecutionTimeline>(
            `/api/audit/executions/${encodeURIComponent(executionId)}`,
        ),

    events: (query: AuditEventsQuery) =>
        auditFetch<{
            items: AuditEvent[];
            total: number;
            limit: number;
            offset: number;
            read_scope?: ReadScope;
        }>("/api/audit/events", query as Record<string, string | number | boolean | undefined>),

    /**
     * Record a correction REQUEST against an authorized audit event.
     *
     * Reuses POST /api/reasoning/feedback (the existing AgentFeedback write)
     * and asks the backend to link the resulting feedback row to the audit
     * subject. The response is a receipt, never an "applied/verified" claim.
     */
    correctionRequest: (payload: {
        agentId: string;
        executionId: string;
        auditId: string;
        stepIndex?: number;
        description?: string;
        eventAction?: string;
        reason: string;
        detail?: string;
        channel?: string | null;
        targetId?: string | null;
    }) =>
        jsonRequest<{
            success: boolean;
            data: CorrectionRequestResult;
            message?: string;
        }>("/api/reasoning/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                agent_id: payload.agentId,
                run_id: payload.executionId,
                step_index: payload.stepIndex ?? -1,
                step_content: {
                    source: "audit_trail",
                    audit_id: payload.auditId,
                    thought: payload.description || payload.eventAction,
                    action: payload.eventAction,
                    description: payload.description,
                    execution_id: payload.executionId,
                },
                feedback_type: "thumbs_down",
                comment: payload.detail
                    ? `${payload.reason}: ${payload.detail}`
                    : payload.reason,
                execution_id: payload.executionId,
                correction_requested: true,
                subject_audit_id: payload.auditId,
                correction_channel: payload.channel || undefined,
                correction_target_id: payload.targetId || undefined,
                correction_reason: payload.reason,
            }),
        }).then((body) => body.data),
};

export interface CorrectionRequestResult {
    id: string;
    feedback_id: string;
    correction_status:
        | "recorded"
        | "already_recorded"
        | "feedback_recorded_audit_unavailable"
        | string;
    correction_audit_id: string | null;
    applied: false;
    verified: false;
    channel?: string | null;
    channel_target_id?: string | null;
    channel_target_basis?: string | null;
    repair_link_proven?: boolean;
    status_note: string;
}
