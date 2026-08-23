/**
 * Ingestion scoping API (round 80s UI completion).
 *
 * Lets Settings > Memory Pipeline Schedules scope each pipeline to an
 * AI employee (agent): the backend persists the agent's role on
 * SyncConfiguration so every scheduled sync tags records for that
 * employee's memory (see core/hybrid_data_ingestion.py SyncConfiguration.role).
 */

import { apiClient } from "@/lib/api";

export interface ScopedAgent {
  agent_id: string;
  name: string;
  category: string;
  maturity_level?: string;
  confidence_score?: number;
}

/** GET /api/agent-governance/agents — real registry listing (R81). */
export async function listScopedAgents(): Promise<ScopedAgent[]> {
  const res = await apiClient.get("/api/agent-governance/agents");
  const data = res?.data;
  return Array.isArray(data) ? data : data?.agents || [];
}

/**
 * POST /api/data-ingestion/enable-sync?agent_id=<id> — persists role on
 * SyncConfiguration; scheduled auto-syncs tag new records for the employee.
 */
export async function enableScopedSync(
  integrationId: string,
  opts: { entityTypes?: string[]; syncLastNDays?: number; agentId?: string } = {}
): Promise<boolean> {
  const params = new URLSearchParams();
  if (opts.agentId) params.set("agent_id", opts.agentId);
  try {
    await apiClient.post(
      `/api/data-ingestion/sync/${encodeURIComponent(integrationId)}`,
      undefined,
      { params }
    );
    // enable-sync is a separate call; fire-and-forget is fine here because
    // failures are non-fatal for scheduling.
    void apiClient.post("/api/data-ingestion/enable-sync", {
      integration_id: integrationId,
      entity_types: opts.entityTypes || [],
      sync_last_n_days: opts.syncLastNDays ?? 30,
    }, { params });
    return true;
  } catch {
    return false;
  }
}
