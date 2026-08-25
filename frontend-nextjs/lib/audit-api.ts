/**
 * Agent Action Audit API client.
 *
 * Serves the read endpoints in backend/api/audit_routes.py — the per-decision
 * audit trail written by core/agent_action_audit.py.
 *
 * NOTE: native fetch (not the shared apiClient) is used on purpose — the
 * repo's MSW test setup intercepts fetch but not axios' XHR adapter, so
 * apiClient calls hang in Jest (same reason as AgentHistoryTable).
 */

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
        task_input?: string | null;
    };
    events: AuditEvent[];
    counts: { tool_calls: number; llm_calls: number; failed_events: number };
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

async function auditFetch<T>(path: string, params?: Record<string, string | number | boolean | undefined>): Promise<T> {
    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";
    const token =
        typeof window !== "undefined"
            ? window.localStorage.getItem("auth_token") ||
              window.localStorage.getItem("token")
            : null;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

    const qs = params
        ? new URLSearchParams(
              Object.entries(params)
                  .filter(([, v]) => v !== undefined && v !== "")
                  .map(([k, v]) => [k, String(v)]),
          ).toString()
        : "";
    const url = `${API_BASE}${path}${qs ? `?${qs}` : ""}`;

    const resp = await fetch(url, { headers });
    if (!resp.ok) {
        throw new Error(`Audit API error: HTTP ${resp.status}`);
    }
    return resp.json() as Promise<T>;
}

export const auditAPI = {
    summary: (days = 7) => auditFetch<AuditSummaryStats>("/api/audit/summary", { days }),

    executions: (agent_id?: string, limit = 50, offset = 0) =>
        auditFetch<{ items: ExecutionSummary[]; total: number }>("/api/audit/executions", {
            agent_id,
            limit,
            offset,
        }),

    timeline: (executionId: string) =>
        auditFetch<ExecutionTimeline>(`/api/audit/executions/${encodeURIComponent(executionId)}`),

    events: (query: AuditEventsQuery) =>
        auditFetch<{ items: AuditEvent[]; total: number; limit: number; offset: number }>(
            "/api/audit/events",
            query as Record<string, string | number | boolean | undefined>,
        ),
};
