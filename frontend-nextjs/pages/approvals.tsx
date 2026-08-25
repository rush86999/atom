import React, { useCallback, useEffect, useState } from "react";
import { getAuthToken } from "@/lib/identity";

/**
 * Approvals — the HITL queue (gap #4).
 * Pending human-in-the-loop actions across all agents: what wants to run,
 * why it paused, and one-click approve/reject. Previously pending actions
 * were only visible one-at-a-time inside the floating chat widget.
 * Backend: GET /api/agents/approvals/pending · POST /api/agents/approvals/{id}
 */

type PendingAction = {
  id: string;
  agent_id?: string;
  action_type: string;
  params?: Record<string, unknown>;
  reason?: string;
  created_at?: string;
};

type TrainingProposal = {
  id: string;
  agent_id: string;
  agent_name?: string;
  title: string;
  description?: string;
  status: string;
  capability_gaps?: unknown[];
  created_at?: string;
};

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function ApprovalsPage() {
  const [actions, setActions] = useState<PendingAction[]>([]);
  const [proposals, setProposals] = useState<TrainingProposal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const headers = useCallback(() => ({
    "Content-Type": "application/json",
    Authorization: `Bearer ${getAuthToken() || ""}`,
  }), []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/agents/approvals/pending`, { headers: headers() });
      if (!res.ok) {
        setError(`Failed to load pending approvals (${res.status}). Admin/agent-manage permission required.`);
        return;
      }
      setActions(await res.json());
    } catch (e) {
      setError(`Failed to load: ${String(e)}`);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  // Training proposals (STUDENT → INTERN): the maturity-training surface is
  // backend-complete (R81) but had zero UI — team leads could never see or
  // decide on training proposals from the app. Best-effort: a 403 signals
  // the viewer is not a supervisor, which is surfaced as a subtle note.
  const loadProposals = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/maturity/training/proposals`, { headers: headers() });
      if (res.ok) {
        const json = await res.json();
        setProposals(Array.isArray(json) ? json : (json.proposals ?? []));
      }
    } catch {
      // Non-critical: the HITL queue still works without this section.
    }
  }, [headers]);

  useEffect(() => {
    load();
    loadProposals();
    const t = setInterval(() => { load(); loadProposals(); }, 15000); // auto-refresh; approvals can be time-sensitive
    return () => clearInterval(t);
  }, [load, loadProposals]);

  const decideProposal = async (id: string, approve: boolean) => {
    setNotice(null);
    try {
      const res = await fetch(`${API}/api/maturity/training/proposals/${id}/${approve ? "approve" : "reject"}`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(approve ? { approve: true } : { reason: "Rejected via Approvals page" }),
      });
      if (!res.ok) {
        setError(`Training decision failed (${res.status}). Supervisor (TEAM_LEAD+) permission required.`);
        return;
      }
      setNotice(`Training proposal ${approve ? "approved" : "rejected"}.`);
      loadProposals();
    } catch (e) {
      setError(`Training decision failed: ${String(e)}`);
    }
  };

  const decide = async (id: string, decision: "approved" | "rejected") => {
    setNotice(null);
    try {
      const res = await fetch(`${API}/api/agents/approvals/${id}`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ decision }),
      });
      if (!res.ok) {
        setError(`Decision failed (${res.status})`);
        return;
      }
      setNotice(`Action ${decision}.`);
      load();
    } catch (e) {
      setError(`Decision failed: ${String(e)}`);
    }
  };

  const fmtParams = (p?: Record<string, unknown>) => {
    if (!p) return "—";
    try {
      return JSON.stringify(p).slice(0, 160);
    } catch {
      return "—";
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6 lg:p-10">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-1">Approvals</h1>
        <p className="text-sm text-gray-400 mb-6">
          Actions paused for human approval. Agents wait here until a decision is made.
        </p>

        {error && <div className="mb-4 p-3 rounded-lg bg-red-900/40 border border-red-700 text-sm">{error}</div>}
        {notice && <div className="mb-4 p-3 rounded-lg bg-emerald-900/40 border border-emerald-700 text-sm">{notice}</div>}

        {loading ? (
          <p className="text-gray-400">Loading…</p>
        ) : actions.length === 0 ? (
          <div className="rounded-xl border border-gray-800 p-10 text-center text-gray-500">
            Nothing waiting for approval. 🎉
          </div>
        ) : (
          <div className="space-y-3">
            {actions.map((a) => (
              <div key={a.id} className="rounded-xl border border-amber-800/60 bg-gray-900 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium text-amber-300">
                      {a.action_type}
                      {a.agent_id && <span className="ml-2 text-xs text-gray-500">agent {String(a.agent_id).slice(0, 8)}</span>}
                    </div>
                    {a.reason && <div className="text-sm text-gray-400 mt-1">{a.reason}</div>}
                    <div className="text-xs text-gray-500 mt-1 font-mono break-all">{fmtParams(a.params)}</div>
                    <div className="text-xs text-gray-600 mt-1">
                      {a.created_at ? new Date(a.created_at).toLocaleString() : ""}
                    </div>
                  </div>
                  <div className="flex gap-2 shrink-0">
                    <button
                      onClick={() => decide(a.id, "approved")}
                      className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-medium"
                    >
                      Approve
                    </button>
                    <button
                      onClick={() => decide(a.id, "rejected")}
                      className="px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-sm font-medium"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-10">
          <h2 className="text-lg font-semibold">Training Proposals (STUDENT → INTERN)</h2>
          <p className="text-sm text-gray-400 mb-4">
            Agents who need supervised training before their next maturity tier. Supervisors (TEAM_LEAD+) can approve or reject.
          </p>
          {proposals.length === 0 ? (
            <div className="rounded-xl border border-gray-800 p-6 text-center text-gray-500">
              No training proposals waiting.
            </div>
          ) : (
            <div className="space-y-3">
              {proposals.filter((p) => p.status === "pending").map((p) => (
                <div key={p.id} className="rounded-xl border border-sky-800/60 bg-gray-900 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium text-sky-300">{p.title}</div>
                      <div className="text-xs text-gray-500 mt-1">agent {p.agent_name || String(p.agent_id).slice(0, 8)}</div>
                      {p.description && <div className="text-sm text-gray-400 mt-1">{p.description}</div>}
                      {Array.isArray(p.capability_gaps) && p.capability_gaps.length > 0 && (
                        <div className="text-xs text-gray-500 mt-1">
                          {p.capability_gaps.length} capability gap{p.capability_gaps.length > 1 ? "s" : ""} identified
                        </div>
                      )}
                      <div className="text-xs text-gray-600 mt-1">
                        {p.created_at ? new Date(p.created_at).toLocaleString() : ""}
                      </div>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button
                        onClick={() => decideProposal(p.id, true)}
                        className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-medium"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => decideProposal(p.id, false)}
                        className="px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-sm font-medium"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
