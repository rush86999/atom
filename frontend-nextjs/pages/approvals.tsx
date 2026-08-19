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

const API = process.env.NEXT_PUBLIC_API_URL || "";

export default function ApprovalsPage() {
  const [actions, setActions] = useState<PendingAction[]>([]);
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

  useEffect(() => {
    load();
    const t = setInterval(load, 15000); // auto-refresh; approvals can be time-sensitive
    return () => clearInterval(t);
  }, [load]);

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
      </div>
    </div>
  );
}
