/**
 * Approvals Panel (MenuBar / Desktop)
 *
 * Round 80t2 — desktop parity: HITL approval journey, mirroring mobile
 * ApprovalsScreen and CLI approvals commands.
 *
 * Data sources (live Atom backend):
 *   GET  /api/agent-governance/pending-approvals    pending list
 *   POST /api/agent-governance/approve/:id          approve
 *   POST /api/agent-governance/reject/:id           reject
 */

import React, { useCallback, useEffect, useState } from "react";

interface PendingApproval {
  approval_id?: string;
  id?: string;
  workflow_name?: string;
  agent_name?: string;
  maturity_level?: string;
  requested_by?: string;
}

interface ApprovalsPanelProps {
  serverUrl?: string;
  /** JWT for auth-gated calls (RBAC: TEAM_LEAD+ enforced server-side). */
  token?: string | null;
}

export default function ApprovalsPanel({
  serverUrl,
  token,
}: ApprovalsPanelProps) {
  const [approvals, setApprovals] = useState<PendingApproval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const base = (serverUrl || "http://localhost:8000").replace(/\/$/, "");

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const headers: Record<string, string> = {};
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(
        `${base}/api/agent-governance/pending-approvals`,
        { headers }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setApprovals(data.pending_approvals || []);
    } catch (e: any) {
      setError(e?.message || "Failed to load approvals");
    } finally {
      setLoading(false);
    }
  }, [base, token]);

  useEffect(() => {
    load();
  }, [load]);

  const decide = useCallback(
    async (id: string, decision: "approve" | "reject") => {
      setBusyId(id);
      setError(null);
      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (token) headers.Authorization = `Bearer ${token}`;
        const res = await fetch(
          `${base}/api/agent-governance/${decision}/${id}`,
          { method: "POST", headers }
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        // Optimistic removal
        setApprovals((prev) => prev.filter((a) => (a.approval_id || a.id) !== id));
      } catch (e: any) {
        setError(e?.message || `Failed to ${decision}`);
      } finally {
        setBusyId(null);
      }
    },
    [base, token]
  );

  return (
    <div className="approvals-panel" data-testid="approvals-panel">
      <div className="approvals-summary">
        <span className="approvals-title">Pending Approvals</span>
        <span className="approvals-count" data-testid="approvals-count">
          {loading ? "Loading…" : `${approvals.length}`}
        </span>
        <button className="approvals-refresh" onClick={load}>Refresh</button>
      </div>

      {error && (
        <div className="approvals-error" role="alert">{error}</div>
      )}

      {!loading && approvals.length === 0 && (
        <div className="approvals-empty" data-testid="approvals-empty">
          No pending approvals.
        </div>
      )}

      <ul className="approvals-list">
        {approvals.map((a) => {
          const id = a.approval_id || a.id || "";
          return (
            <li key={id} className="approval-row" data-testid={`approval-row-${id}`}>
              <span className="approval-name">
                {a.workflow_name || a.agent_name || id}
              </span>
              {a.maturity_level ? (
                <span className={`approval-maturity ${a.maturity_level}`}>
                  {a.maturity_level}
                </span>
              ) : null}
              <button
                className="approval-reject"
                disabled={busyId === id}
                onClick={() => decide(id, "reject")}
                data-testid={`reject-${id}`}
              >
                Reject
              </button>
              <button
                className="approval-approve"
                disabled={busyId === id}
                onClick={() => decide(id, "approve")}
                data-testid={`approve-${id}`}
              >
                {busyId === id ? "…" : "Approve"}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
