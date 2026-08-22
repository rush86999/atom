/**
 * Workflows Panel (MenuBar / Desktop)
 *
 * Round 80u — desktop parity: workflow visibility + trigger, mirroring the
 * mobile workflows suite via the same /api/mobile/workflows endpoints.
 *
 * Data sources (live Atom backend):
 *   GET  /api/mobile/workflows                catalog
 *   POST /api/mobile/workflows/trigger        run a workflow
 */

import React, { useCallback, useEffect, useState } from "react";

interface Workflow {
  id: string;
  name: string;
  status?: string;
  [key: string]: any;
}

interface WorkflowsPanelProps {
  serverUrl?: string;
  /** JWT for auth-gated calls. */
  token?: string | null;
}

const DEFAULT_SERVER_URL = "http://localhost:8000";

interface TriggerResponse {
  execution_id?: string;
  id?: string;
  status?: string;
  [key: string]: any;
}

export default function WorkflowsPanel({
  serverUrl,
  token,
}: WorkflowsPanelProps) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [triggeringId, setTriggeringId] = useState<string | null>(null);
  const [lastTriggered, setLastTriggered] = useState<{ id: string; exec: string } | null>(null);

  const base = (serverUrl || DEFAULT_SERVER_URL).replace(/\/$/, "");
  const headers = useCallback((): Record<string, string> => {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (token) h.Authorization = `Bearer ${token}`;
    return h;
  }, [token]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${base}/api/mobile/workflows`, { headers: headers() });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setWorkflows(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e?.message || "Failed to load workflows");
    } finally {
      setLoading(false);
    }
  }, [base, token]);

  useEffect(() => {
    load();
  }, [load]);

  const handleTrigger = useCallback(
    async (wf: Workflow) => {
      setTriggeringId(wf.id);
      setError(null);
      try {
        const res = await fetch(`${base}/api/mobile/workflows/trigger`, {
          method: "POST",
          headers: headers(),
          body: JSON.stringify({ workflow_id: wf.id }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: TriggerResponse = await res.json();
        const exec = data.execution_id || data.id || "";
        setLastTriggered({ id: wf.id, exec });
        // Refresh after a short grace period so status reflects the run.
        setTimeout(load, 2500);
      } catch (e: any) {
        setError(e?.message || `Failed to trigger ${wf.name}`);
      } finally {
        setTriggeringId(null);
      }
    },
    [base, headers, load]
  );

  return (
    <div className="workflows-panel" data-testid="workflows-panel">
      <div className="workflows-summary">
        <span className="workflows-title">Workflows</span>
        <span className="workflows-count" data-testid="workflows-count">
          {loading ? "Loading…" : `${workflows.length} available`}
        </span>
        <button className="workflows-refresh" onClick={load}>
          Refresh
        </button>
      </div>

      {error && (
        <div className="workflows-error" role="alert">
          {error}
        </div>
      )}

      {!loading && lastTriggered && (
        <div className="workflows-triggered" role="status" data-testid="trigger-confirmation">
          Triggered {lastTriggered.id}
          {lastTriggered.exec ? ` — execution ${lastTriggered.exec}` : ""}
        </div>
      )}

      {!loading && workflows.length === 0 && (
        <div className="workflows-empty">No workflows found.</div>
      )}

      {!loading && workflows.length > 0 && (
        <ul className="workflows-list">
          {workflows.map((wf) => (
            <li key={wf.id} className="workflows-row" data-testid={`workflow-row-${wf.id}`}>
              <span className="workflow-name">{wf.name}</span>
              {wf.status ? (
                <span className={`workflow-status ${wf.status}`}>{wf.status}</span>
              ) : null}
              <button
                className="workflow-trigger"
                disabled={triggeringId === wf.id}
                onClick={() => handleTrigger(wf)}
                data-testid={`trigger-${wf.id}`}
              >
                {triggeringId === wf.id ? "…" : "Run"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
