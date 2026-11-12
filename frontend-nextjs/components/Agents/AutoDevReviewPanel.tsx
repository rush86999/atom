import React, { useCallback, useEffect, useRef, useState } from "react";
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
 * Self-fetching via GET /api/autodev/candidates?status=pending and
 * ?status=validated, plus GET /api/autodev/tool-errors. Pending items go
 * through /approve and /reject. A validated skill gets the separate explicit
 * typed /apply step only while its review binding still matches the current
 * material (apply_eligible === true); machine-validated or stale-binding
 * skills stay reviewable via approve/reject. The panel never runs the
 * proposed code.
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
  // Advisory review state from the list endpoint. Absent means "not reviewed"
  // / "not apply-eligible"; only an explicit true unlocks Apply.
  apply_eligible?: boolean;
  reviewed?: boolean;
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

/** Surface the backend's structured refusal instead of inventing success. */
function applyFailureMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  const nested = detail?.error?.message;
  if (typeof nested === "string" && nested.trim()) return nested;
  if (typeof error?.message === "string" && error.message.trim()) {
    return `Apply failed: ${error.message}`;
  }
  return "Apply refused — reload and review the current snapshot.";
}

export function AutoDevReviewPanel({ agentId }: { agentId?: string | null }) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [validatedSkills, setValidatedSkills] = useState<Candidate[]>([]);
  const [toolErrors, setToolErrors] = useState<ToolError[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [guidance, setGuidance] = useState<Guidance[]>([]);
  // Frames are read from the socket's `onMessage` listener rather than the
  // `lastMessage` state slot. That slot is ONE slot: a burst of frames inside a
  // single render commit produces one commit, so an effect keyed on it sees only
  // the newest frame — an `autodev_guidance` ping landing mid-burst never
  // triggered its reload. The in-flight guard keeps a burst of pings from
  // becoming one reload per frame.
  const { onMessage } = useWebSocket();
  const guidanceReloadInFlight = useRef(false);

  // The list endpoint is status-scoped (default pending). Approved-but-not-
  // applied skills are a separate status, so fetch both in the reviewer's
  // scope instead of treating approval as permission to apply.
  const candidateUrl = useCallback(
    (status: "pending" | "validated") => {
      const params = new URLSearchParams({ status });
      if (agentId) params.set("agent_id", agentId);
      return `/api/autodev/candidates?${params.toString()}`;
    },
    [agentId]
  );

  const load = useCallback(async (): Promise<boolean> => {
    setLoading(true);
    setError(null);
    try {
      const [pendingRes, approvedRes] = await Promise.all([
        apiClient.get<{
          data: { candidates: Candidate[]; count: number };
        }>(candidateUrl("pending")),
        apiClient.get<{
          data: { candidates: Candidate[]; count: number };
        }>(candidateUrl("validated")),
      ]);
      setCandidates(pendingRes.data?.data?.candidates ?? []);
      // Typed apply exists only for skill candidates; a validated tool
      // mutation keeps its own review lifecycle and gets no Apply button.
      setValidatedSkills(
        (approvedRes.data?.data?.candidates ?? []).filter(
          (c) => c.kind === "skill" && c.status === "validated"
        )
      );
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
      return true;
    } catch (e) {
      setError("Could not load Auto-Dev review data");
      return false;
    } finally {
      setLoading(false);
    }
  }, [agentId, candidateUrl]);

  useEffect(() => {
    load();
  }, [load]);

  // Live refresh: the backend pings `autodev_guidance` over the workspace
  // websocket when a tool-error pattern is detected or a fix is proposed.
  useEffect(() => onMessage((msg: any) => {
    if (msg?.type !== "autodev_guidance") return;
    if (guidanceReloadInFlight.current) return;
    guidanceReloadInFlight.current = true;
    void Promise.resolve(load()).finally(() => {
      guidanceReloadInFlight.current = false;
    });
  }), [onMessage, load]);

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

  // Explicit typed application, separate from approval. The backend writes
  // prompt instructions only; generated code stays review-only and is never
  // executed or used to widen this agent's authority.
  const applyReviewedSkill = async (id: string) => {
    setNotice(null);
    setError(null);
    setApplyingId(id);
    let failure: string | null = null;
    let success =
      "Reviewed skill applied as a typed prompt skill. Proposed code was not executed.";
    try {
      const res = await apiClient.post<{
        data?: { already_applied?: boolean };
      }>(`/api/autodev/skills/${id}/apply`);
      if (res.data?.data?.already_applied) {
        success = "This reviewed skill was already applied — no changes were made.";
      }
    } catch (e) {
      failure = applyFailureMessage(e);
    }

    // Always re-read the server state after an attempt. Never move the card
    // optimistically: a refusal may leave it approved, a success may promote it.
    const refreshed = await load();
    setApplyingId(null);
    if (failure) {
      setError(failure);
    } else if (refreshed) {
      setNotice(success);
    } else {
      setError(
        "The apply request finished, but the review list could not be refreshed. Reload to confirm."
      );
    }
  };

  return (
    <div className="space-y-4" data-testid="autodev-review-panel">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Auto-Dev Fixes</h3>
          <p className="text-sm text-muted-foreground">
            Fixes your agents&apos; evolution harness proposed from repeated tool
            failures. Approval records your review; applying a reviewed skill is
            a separate explicit step. Proposed code is never executed.
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

      {/* Validated skills — review state decides whether Apply is offered */}
      {validatedSkills.length > 0 && (
        <div
          className="space-y-2"
          data-testid="autodev-approved-skills"
          aria-label="Validated skills awaiting review or apply"
        >
          <h4 className="text-sm font-semibold">Validated skills</h4>
          <p className="text-xs text-muted-foreground">
            Validation is not review. Apply appears only while a review of this
            exact snapshot is still current; otherwise approve or reject the
            material. Applying installs the prompt instructions only — proposed
            code is never executed.
          </p>
          {validatedSkills.map((c) => {
            const canApply =
              c.status === "validated" && c.apply_eligible === true;
            return (
              <div
                key={c.id}
                className="rounded-md border border-green-300 bg-green-50 p-3 space-y-2 dark:border-green-800 dark:bg-green-950"
                data-testid={`autodev-approved-skill-${c.id}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">
                      {canApply ? "Reviewed skill" : "Needs review"}
                    </Badge>
                    <span className="font-medium">{c.name}</span>
                  </div>
                  <div className="flex gap-2">
                    {canApply ? (
                      <Button
                        size="sm"
                        onClick={() => applyReviewedSkill(c.id)}
                        disabled={applyingId !== null}
                      >
                        {applyingId === c.id ? "Applying…" : "Apply"}
                      </Button>
                    ) : (
                      <>
                        <Button
                          size="sm"
                          onClick={() => act("skill", c.id, "approve")}
                        >
                          Approve
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => act("skill", c.id, "reject")}
                        >
                          Reject
                        </Button>
                      </>
                    )}
                  </div>
                </div>
                {c.description && (
                  <p className="text-sm text-muted-foreground">{c.description}</p>
                )}
                {c.failure && (
                  <p className="text-sm text-muted-foreground">
                    Failing with: {c.failure}
                  </p>
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
            );
          })}
        </div>
      )}

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
