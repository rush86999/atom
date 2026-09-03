import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { useWebSocket } from "@/hooks/useWebSocket";

/**
 * Auto-Dev Review Panel — the supervisor side of the agent evolution
 * harness (canvas TrainingPanel covers teaching; this covers FIXING):
 *
 * - Proposed fixes: Memento skill candidates + AlphaEvolver tool mutations
 *   generated when the agent's tool errors repeat. Approve/reject here;
 *   nothing auto-deploys (candidates stay pending until a human acts).
 * - Recent tool errors: aggregated from the structured signals the
   integration layer records on executions — WHICH tool keeps failing for
 *   this agent, before a proposed fix even exists.
 *
 * Self-fetching via GET /api/autodev/candidates and
 * GET /api/autodev/tool-errors; mutations go through the /approve and
 * /reject endpoints.
 */

interface Candidate {
  kind: "skill" | "mutation";
  id: string;
  agent_id: string | null;
  name: string;
  description: string;
  failure: string;
  code: string;
  status: string;
  created_at: string | null;
}

interface Guidance {
  id: string;
  agent_id: string;
  kind: string;
  title: string;
  detail: string;
  importance: number;
  timestamp: string | null;
}

interface ToolError {
  signature: string;
  count: number;
  last_error: string;
  last_seen: string;
}

export function AutoDevReviewPanel({ agentId }: { agentId?: string | null }) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [toolErrors, setToolErrors] = useState<ToolError[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [guidance, setGuidance] = useState<Guidance[]>([]);
  const { lastMessage } = useWebSocket();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<{
        data: { candidates: Candidate[]; count: number };
      }>("/api/autodev/candidates");
      setCandidates(res.data?.data?.candidates ?? []);
      const g = await apiClient.get<{
        data: { guidance: Guidance[]; count: number };
      }>("/api/autodev/guidance");
      setGuidance(g.data?.data?.guidance ?? []);
      if (agentId) {
        const errRes = await apiClient.get<{
          data: { tool_errors: ToolError[]; count: number };
        }>(`/api/autodev/tool-errors?agent_id=${agentId}`);
        setToolErrors(errRes.data?.data?.tool_errors ?? []);
      } else {
        setToolErrors([]);
      }
    } catch (e) {
      setError("Could not load Auto-Dev review data");
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    load();
  }, [load]);

  // Live refresh: the backend pings `autodev_guidance` over the workspace
  // websocket when a tool-error pattern is detected or a fix is proposed.
  useEffect(() => {
    if (lastMessage?.type === "autodev_guidance") {
      load();
    }
  }, [lastMessage, load]);

  const act = async (kind: "skill" | "mutation", id: string, action: "approve" | "reject") => {
    setNotice(null);
    try {
      await apiClient.post(`/api/autodev/${kind === "skill" ? "skills" : "mutations"}/${id}/${action}`);
      setNotice(action === "approve" ? "Approved." : "Rejected.");
      await load();
    } catch (e) {
      setError("Action failed — try again");
    }
  };

  return (
    <div className="space-y-4" data-testid="autodev-review-panel">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Auto-Dev Fixes</h3>
          <p className="text-sm text-muted-foreground">
            Fixes your agents&apos; evolution harness proposed from repeated tool
            failures. Nothing changes until you approve it here.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          Refresh
        </Button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {notice && <p className="text-sm text-green-700">{notice}</p>}
      {loading && <p className="text-sm text-muted-foreground">Loading…</p>}

      {/* Guidance — tool-error patterns and proposal notices */}
      {guidance.length > 0 && (
        <div className="space-y-2" data-testid="autodev-guidance">
          {guidance.slice(0, 5).map((g) => (
            <div
              key={g.id}
              className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm dark:border-amber-800 dark:bg-amber-950"
            >
              <span className="font-medium">{g.title}</span>
              {g.detail && (
                <p className="text-xs text-muted-foreground mt-1">{g.detail}</p>
              )}
              <p className="text-xs text-muted-foreground mt-1">
                Review proposed fixes below.
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Proposed fixes */}
      <div className="space-y-2">
        {candidates.length === 0 && !loading && (
          <p className="text-sm text-muted-foreground">
            No pending fixes. When a tool of yours fails repeatedly, a fix
            proposal will appear here for your review.
          </p>
        )}
        {candidates.map((c) => (
          <div key={c.id} className="rounded-md border p-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Badge variant={c.kind === "mutation" ? "default" : "secondary"}>
                  {c.kind === "mutation" ? "Tool fix" : "New skill"}
                </Badge>
                <span className="font-medium">{c.name}</span>
              </div>
              <div className="flex gap-2">
                <Button size="sm" onClick={() => act(c.kind, c.id, "approve")}>
                  Approve
                </Button>
                <Button size="sm" variant="outline" onClick={() => act(c.kind, c.id, "reject")}>
                  Reject
                </Button>
              </div>
            </div>
            {c.failure && (
              <p className="text-sm text-muted-foreground">Failing with: {c.failure}</p>
            )}
            {c.code && (
              <div>
                <button
                  className="text-xs text-muted-foreground underline"
                  onClick={() => setExpanded(expanded === c.id ? null : c.id)}
                >
                  {expanded === c.id ? "Hide proposed code" : "Show proposed code"}
                </button>
                {expanded === c.id && (
                  <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted p-2 text-xs">
                    {c.code}
                  </pre>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Recent tool errors */}
      {agentId && toolErrors.length > 0 && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">Recent tool errors</h4>
          {toolErrors.map((e) => (
            <div key={e.signature} className="rounded-md border p-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="font-mono">{e.signature}</span>
                <Badge variant="destructive">{e.count}×</Badge>
              </div>
              {e.last_error && (
                <p className="text-xs text-muted-foreground mt-1">{e.last_error}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default AutoDevReviewPanel;
