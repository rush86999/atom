"use client";

import React, { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { apiClient } from "@/lib/api-client";
import { getCurrentUserId } from "@/lib/identity";
import {
  approveTrainingProposal,
  CanvasTrainingContext,
  completeTrainingSession,
  getAgentGraduationProgress,
  getCanvasTrainingContext,
  getGraduationReadiness,
  GraduationProgress,
  GraduationReadiness,
  promoteAgent,
  rejectTrainingProposal,
  teachAgent,
  updateTrainingGuidance,
} from "@/lib/maturity-api";

// Session statuses the supervisor can still work (and complete). Mirrors
// _ACTIVE_SESSION_STATUSES on the backend.
const ACTIVE_STATUSES = ["scheduled", "active", "in_progress", "pending"];

const NEXT_TIER: Record<string, string> = {
  student: "intern",
  intern: "supervised",
  supervised: "autonomous",
};

const TIER_BADGE_CLASS: Record<string, string> = {
  student: "bg-amber-100 text-amber-800",
  intern: "bg-blue-100 text-blue-800",
  supervised: "bg-indigo-100 text-indigo-800",
  autonomous: "bg-green-100 text-green-800",
};

/**
 * Training panel for the canvas page — the supervisor (or any teacher)
 * trains the agent ON the canvas they are co-editing:
 *
 * - agent maturity card + career progress (episodes to next tier)
 * - teach a lesson (the learning channel, +confidence)
 * - active training session: lesson editor, live evidence, suggested tasks
 *   (delivered over the training chat so the supervised pass is recorded as
 *   an episode), and the evidence-gated score & complete form
 * - pending training proposal: approve/reject without leaving the canvas
 * - graduation: readiness score + promote (supervisor-only)
 *
 * Self-fetching via GET /api/maturity/training/context; every mutation goes
 * through the existing /api/maturity + graduation endpoints.
 */
export function TrainingPanel({
  canvasId,
  agentIdHint,
  onContextLoaded,
}: {
  canvasId: string;
  agentIdHint?: string;
  onContextLoaded?: (ctx: CanvasTrainingContext) => void;
}) {
  const [ctx, setCtx] = useState<CanvasTrainingContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [progress, setProgress] = useState<GraduationProgress | null>(null);
  const [readiness, setReadiness] = useState<GraduationReadiness | null>(null);

  // Teach form
  const [lesson, setLesson] = useState("");
  const [topic, setTopic] = useState("");
  const [teachBusy, setTeachBusy] = useState(false);

  // Lesson plan editor (objective + one-task-per-line)
  const [lessonDraft, setLessonDraft] = useState<{ objective: string; tasks: string }>({ objective: "", tasks: "" });
  const [lessonBusy, setLessonBusy] = useState(false);

  // Suggested task → training chat
  const [taskText, setTaskText] = useState("");
  const [taskBusy, setTaskBusy] = useState(false);

  // Score & complete form
  const [form, setForm] = useState({ score: "0.8", feedback: "", capabilities: "" });
  const [completeBusy, setCompleteBusy] = useState(false);
  const [completion, setCompletion] = useState<Record<string, unknown> | null>(null);

  // Proposal decisions
  const [rejectReason, setRejectReason] = useState("");
  const [proposalBusy, setProposalBusy] = useState(false);

  // Graduation
  const [promoteBusy, setPromoteBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const context = await getCanvasTrainingContext(canvasId, agentIdHint);
      setCtx(context);
      onContextLoaded?.(context);
      if (context.agent) {
        // Best-effort: AGENT_VIEW-gated; non-viewers just lose the bar.
        try {
          setProgress(await getAgentGraduationProgress(context.agent.id));
        } catch {
          setProgress(null);
        }
      } else {
        setProgress(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [canvasId, agentIdHint, onContextLoaded]);

  useEffect(() => {
    load();
  }, [load]);

  const agent = ctx?.agent ?? null;
  const isSupervisor = ctx?.viewer_is_supervisor ?? false;
  const session = ctx?.linked_session ?? null;
  const sessionActive =
    !!session && ACTIVE_STATUSES.includes((session.status || "").toLowerCase());
  const tier = (agent?.tier || "student").toLowerCase();
  const nextTier = NEXT_TIER[tier];

  // Lesson plan draft follows the loaded session (panel refreshes swap it).
  useEffect(() => {
    const plan = (session?.lesson_plan ?? {}) as Record<string, unknown>;
    const tasks = Array.isArray(plan.tasks) ? (plan.tasks as string[]) : [];
    setLessonDraft({
      objective: typeof plan.objective === "string" ? plan.objective : "",
      tasks: tasks.join("\n"),
    });
    setCompletion(null);
  }, [session?.id, session?.lesson_plan]);

  // Readiness (supervisors only — the promote decision needs it).
  useEffect(() => {
    if (!isSupervisor || !agent || !nextTier) {
      setReadiness(null);
      return;
    }
    let cancelled = false;
    getGraduationReadiness(agent.id, nextTier.toUpperCase())
      .then((r) => !cancelled && setReadiness(r))
      .catch(() => !cancelled && setReadiness(null));
    return () => {
      cancelled = true;
    };
  }, [isSupervisor, agent?.id, nextTier]);

  const handleTeach = async () => {
    if (!agent || !lesson.trim()) return;
    setTeachBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await teachAgent(agent.id, lesson.trim(), topic.trim() || undefined);
      const status = String((result as Record<string, unknown>).status ?? "ok");
      setNotice(
        status === "ok"
          ? `Lesson recorded — ${agent.name}'s confidence grew.`
          : status === "skipped"
            ? `${agent.name} is not a STUDENT — lessons apply to students (training confers maturity, learning alone never does).`
            : "Lesson recorded."
      );
      setLesson("");
      setTopic("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setTeachBusy(false);
    }
  };

  const handleSaveLesson = async () => {
    if (!session) return;
    setLessonBusy(true);
    setError(null);
    setNotice(null);
    try {
      const plan = { ...(session.lesson_plan ?? {}) } as Record<string, unknown>;
      plan.objective = lessonDraft.objective;
      plan.tasks = lessonDraft.tasks.split("\n").map((t) => t.trim()).filter(Boolean);
      await updateTrainingGuidance(session.id, plan);
      setNotice("Lesson plan saved.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLessonBusy(false);
    }
  };

  // Mirrors the /approvals suggested-task flow: the task goes to the agent
  // over the training chat (session id keys the recorded episode) and lands
  // in the lesson plan for the training record.
  const handleSuggestTask = async () => {
    if (!session || !agent || !taskText.trim()) return;
    setTaskBusy(true);
    setError(null);
    setNotice(null);
    try {
      const resp = await apiClient.post("/api/chat/message", {
        message: `Supervisor task: ${taskText.trim()}`,
        user_id: getCurrentUserId(),
        session_id: `training-chat-${session.id}`,
        agent_id: agent.id,
      });
      if ((resp as any)?.status === 403 || (resp as any)?.status === 401) throw new Error("Not allowed");
      const plan = { ...(session.lesson_plan ?? {}) } as Record<string, unknown>;
      const tasks = Array.isArray(plan.tasks) ? [...(plan.tasks as string[])] : [];
      tasks.push(`Supervisor task: ${taskText.trim()}`);
      plan.tasks = tasks;
      try {
        await updateTrainingGuidance(session.id, plan, `Supervisor suggested task: ${taskText.trim()}`);
      } catch {
        /* lesson persistence is best-effort, same as /approvals */
      }
      setNotice(`Task sent to ${agent.name} — it will work it in the training chat.`);
      setTaskText("");
      await load();
    } catch (e) {
      setError(`Task send failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setTaskBusy(false);
    }
  };

  const handleComplete = async () => {
    if (!session) return;
    setCompleteBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await completeTrainingSession(session.id, {
        performance_score: Number(form.score) || 0,
        supervisor_feedback: form.feedback.trim() || "Supervised pass completed on canvas.",
        capabilities_developed: form.capabilities.split(",").map((c) => c.trim()).filter(Boolean),
      });
      setCompletion(result as Record<string, unknown>);
      const promoted = Boolean((result as Record<string, unknown>).promoted_to_intern);
      setNotice(promoted ? "Training session completed — 🎓 promoted to INTERN!" : "Training session completed.");
      await load();
    } catch (e) {
      // The backend's 422 carries the live evidence counts — surface them.
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCompleteBusy(false);
    }
  };

  const handleApproveProposal = async () => {
    if (!ctx?.pending_proposal) return;
    setProposalBusy(true);
    setError(null);
    setNotice(null);
    try {
      const { session_id } = await approveTrainingProposal(ctx.pending_proposal.id);
      setNotice(`Training approved — session ${session_id.slice(0, 8)}… started.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProposalBusy(false);
      setRejectReason("");
    }
  };

  const handleRejectProposal = async () => {
    if (!ctx?.pending_proposal) return;
    setProposalBusy(true);
    setError(null);
    setNotice(null);
    try {
      await rejectTrainingProposal(ctx.pending_proposal.id, rejectReason.trim() || "Rejected from canvas");
      setNotice("Training proposal rejected.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProposalBusy(false);
      setRejectReason("");
    }
  };

  const handlePromote = async () => {
    if (!agent || !nextTier) return;
    if (!window.confirm(`Promote ${agent.name} to ${nextTier.toUpperCase()}? This unlocks the next action band.`)) return;
    setPromoteBusy(true);
    setError(null);
    setNotice(null);
    try {
      await promoteAgent(agent.id, nextTier);
      setNotice(`🎓 ${agent.name} graduated to ${nextTier.toUpperCase()}.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPromoteBusy(false);
    }
  };

  const evidence = session?.evidence ?? null;

  return (
    <div className="flex-1 overflow-y-auto p-3 space-y-4 text-sm" data-testid="training-panel">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Agent Training</span>
        <Button variant="ghost" size="sm" onClick={load} title="Refresh training state" data-testid="training-refresh">
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      </div>
      <p className="text-[10px] text-muted-foreground -mt-3">
        Train, teach, and graduate the agent from this canvas
      </p>

      {error && (
        <p role="alert" className="text-xs text-red-600 bg-red-50 dark:bg-red-900/20 rounded px-2 py-1">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-xs text-green-700 dark:text-green-400 bg-green-50 dark:bg-green-900/20 rounded px-2 py-1">
          {notice}
        </p>
      )}

      {loading && <p className="text-xs text-muted-foreground">Loading training context…</p>}

      {!loading && !agent && (
        <div className="text-xs text-muted-foreground text-center py-6" data-testid="training-no-agent">
          <p className="mb-1">🧑‍🏫 No agent linked to this canvas</p>
          <p>Open a canvas from an agent chat, or a training-session canvas, to train the agent here.</p>
        </div>
      )}

      {agent && (
        <>
          {/* Agent card */}
          <div className="border rounded-lg p-2.5 space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium truncate" data-testid="training-agent-name">{agent.name}</span>
              <span
                className={`text-[10px] uppercase px-1.5 py-0.5 rounded ${TIER_BADGE_CLASS[tier] ?? "bg-muted text-muted-foreground"}`}
                data-testid="training-tier-badge"
              >
                {tier}
              </span>
            </div>
            <div className="text-[11px] text-muted-foreground flex gap-2">
              {typeof agent.confidence === "number" && <span>confidence {(agent.confidence * 100).toFixed(0)}%</span>}
              {agent.domain && <span>· {agent.domain}</span>}
            </div>
            {progress && (progress.next_tier || progress.episode_count !== undefined) && (
              <p className="text-[11px] text-muted-foreground" data-testid="training-progress">
                {progress.next_tier
                  ? `${progress.episode_count ?? 0}${progress.next_threshold_episodes ? `/${progress.next_threshold_episodes}` : ""} successful episodes · next: ${progress.next_tier}`
                  : `${progress.episode_count ?? 0} successful episodes · top tier`}
              </p>
            )}
          </div>

          {/* Pending training proposal (supervisor, no active session) */}
          {isSupervisor && ctx?.pending_proposal && !sessionActive && (
            <div className="border border-amber-300 dark:border-amber-700 rounded-lg p-2.5 space-y-2" data-testid="pending-proposal-card">
              <p className="text-xs font-medium">Training proposal</p>
              <p className="text-xs">{ctx.pending_proposal.title ?? ctx.pending_proposal.id}</p>
              {!!ctx.pending_proposal.capability_gaps?.length && (
                <p className="text-[11px] text-muted-foreground">Gaps: {ctx.pending_proposal.capability_gaps.join(", ")}</p>
              )}
              {!!ctx.pending_proposal.estimated_duration_hours && (
                <p className="text-[11px] text-muted-foreground">~{ctx.pending_proposal.estimated_duration_hours}h</p>
              )}
              <div className="flex gap-1.5">
                <Button size="sm" className="h-7 text-xs" onClick={handleApproveProposal} disabled={proposalBusy} data-testid="approve-proposal">
                  {proposalBusy ? "…" : "Approve training"}
                </Button>
                <Button size="sm" variant="outline" className="h-7 text-xs" onClick={handleRejectProposal} disabled={proposalBusy || !rejectReason.trim()} data-testid="reject-proposal">
                  Reject
                </Button>
              </div>
              <Input
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Rejection reason (required to reject)"
                className="h-7 text-xs"
                aria-label="Rejection reason"
              />
            </div>
          )}

          {/* Training session */}
          {session && (
            <div className="border rounded-lg p-2.5 space-y-2.5" data-testid="training-session-section">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium">Training session</p>
                <span className={`text-[10px] px-1.5 py-0.5 rounded ${sessionActive ? "bg-blue-100 text-blue-800" : "bg-muted text-muted-foreground"}`}>
                  {session.status ?? "unknown"}
                </span>
              </div>

              {evidence && (
                <p
                  className="text-[11px]"
                  data-testid="session-evidence-counter"
                >
                  Recorded work runs:{" "}
                  <strong>{evidence.episodes}</strong>
                  {sessionActive && (
                    <span className={evidence.episodes >= evidence.required_episodes ? "text-green-700 dark:text-green-400" : "text-amber-700 dark:text-amber-400"}>
                      {" "}/ {evidence.required_episodes} required to complete
                    </span>
                  )}
                  {" "}· successful: <strong>{evidence.successes}</strong>
                </p>
              )}

              {/* Lesson plan: supervisor edits while active; everyone reads */}
              {(isSupervisor && sessionActive) ? (
                <div className="space-y-1.5">
                  <Input
                    value={lessonDraft.objective}
                    onChange={(e) => setLessonDraft((d) => ({ ...d, objective: e.target.value }))}
                    placeholder="Lesson objective"
                    className="h-7 text-xs"
                    aria-label="Lesson objective"
                    data-testid="lesson-objective-input"
                  />
                  <textarea
                    value={lessonDraft.tasks}
                    onChange={(e) => setLessonDraft((d) => ({ ...d, tasks: e.target.value }))}
                    placeholder="Tasks (one per line)"
                    rows={3}
                    className="w-full border rounded-md px-2 py-1 text-xs bg-background"
                    aria-label="Lesson tasks"
                    data-testid="lesson-tasks-input"
                  />
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={handleSaveLesson} disabled={lessonBusy} data-testid="lesson-save">
                    {lessonBusy ? "Saving…" : "Save lesson"}
                  </Button>
                </div>
              ) : (
                !!lessonDraft.objective && (
                  <div className="text-[11px] text-muted-foreground">
                    <p>Objective: {lessonDraft.objective}</p>
                    {!!lessonDraft.tasks && <p className="whitespace-pre-line">{"Tasks:\n" + lessonDraft.tasks}</p>}
                  </div>
                )
              )}

              {/* Completed-session summary */}
              {!sessionActive && (
                <p className="text-[11px] text-muted-foreground" data-testid="session-completed-summary">
                  {session.promoted_to_intern ? "🎓 This pass promoted the agent to INTERN." : "Session completed."}
                  {typeof session.performance_score === "number" && ` Score: ${(session.performance_score * 100).toFixed(0)}%.`}
                </p>
              )}

              {/* Suggest a task → training chat (records the supervised pass) */}
              {isSupervisor && sessionActive && (
                <div className="space-y-1.5">
                  <div className="flex gap-1.5">
                    <Input
                      value={taskText}
                      onChange={(e) => setTaskText(e.target.value)}
                      placeholder="Suggest a task for the trainee…"
                      className="h-7 text-xs"
                      aria-label="Suggested task"
                      data-testid="suggest-task-input"
                      onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), handleSuggestTask())}
                    />
                    <Button size="sm" className="h-7 text-xs" onClick={handleSuggestTask} disabled={taskBusy || !taskText.trim()} data-testid="suggest-task-send">
                      {taskBusy ? "…" : "Send"}
                    </Button>
                  </div>
                  <p className="text-[10px] text-muted-foreground">Sent to the training chat — the supervised pass is recorded as a work run.</p>
                </div>
              )}

              {/* Score & complete (evidence-gated) */}
              {isSupervisor && sessionActive && (
                <div className="border-t pt-2 space-y-1.5" data-testid="canvas-complete-training-form">
                  <p className="text-xs font-medium">Score & complete</p>
                  <div className="flex gap-1.5">
                    <Input
                      value={form.score}
                      onChange={(e) => setForm((f) => ({ ...f, score: e.target.value }))}
                      placeholder="Score 0–1"
                      className="h-7 text-xs w-24"
                      aria-label="Performance score"
                      data-testid="complete-performance-input"
                    />
                    <Input
                      value={form.capabilities}
                      onChange={(e) => setForm((f) => ({ ...f, capabilities: e.target.value }))}
                      placeholder="Capabilities developed (comma-sep)"
                      className="h-7 text-xs flex-1"
                      aria-label="Capabilities developed"
                      data-testid="complete-capabilities-input"
                    />
                  </div>
                  <textarea
                    value={form.feedback}
                    onChange={(e) => setForm((f) => ({ ...f, feedback: e.target.value }))}
                    placeholder="Supervisor feedback"
                    rows={2}
                    className="w-full border rounded-md px-2 py-1 text-xs bg-background"
                    aria-label="Supervisor feedback"
                    data-testid="complete-feedback-input"
                  />
                  <Button
                    size="sm"
                    className="h-7 text-xs bg-green-600 hover:bg-green-500"
                    onClick={handleComplete}
                    disabled={completeBusy || !evidence || evidence.episodes < evidence.required_episodes}
                    title={
                      evidence && evidence.episodes < evidence.required_episodes
                        ? `The hire needs ${evidence.required_episodes} recorded work runs in this session first`
                        : undefined
                    }
                    data-testid="complete-session-button"
                  >
                    {completeBusy ? "Completing…" : "Complete training session"}
                  </Button>
                </div>
              )}
            </div>
          )}

          {/* Teach a lesson — the learning channel, any signed-in human */}
          <div className="border rounded-lg p-2.5 space-y-1.5" data-testid="teach-section">
            <p className="text-xs font-medium">Teach a lesson</p>
            <textarea
              value={lesson}
              onChange={(e) => setLesson(e.target.value)}
              placeholder="A lesson, correction, or worked example…"
              rows={3}
              className="w-full border rounded-md px-2 py-1 text-xs bg-background"
              aria-label="Lesson"
              data-testid="teach-lesson-input"
            />
            <div className="flex gap-1.5">
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Topic (optional)"
                className="h-7 text-xs"
                aria-label="Topic"
                data-testid="teach-topic-input"
              />
              <Button size="sm" className="h-7 text-xs" onClick={handleTeach} disabled={teachBusy || lesson.trim().length < 5} data-testid="teach-submit">
                {teachBusy ? "Teaching…" : "Teach"}
              </Button>
            </div>
            <p className="text-[10px] text-muted-foreground">Learning grows confidence, but only training + graduation confer maturity.</p>
          </div>

          {/* Graduation (supervisor) */}
          {isSupervisor && (
            <div className="border rounded-lg p-2.5 space-y-2" data-testid="graduation-section">
              <p className="text-xs font-medium">Graduation</p>
              {!nextTier ? (
                <p className="text-[11px] text-muted-foreground">Top maturity tier reached.</p>
              ) : (
                <>
                  {readiness ? (
                    <div className="text-[11px] space-y-1">
                      <p data-testid="readiness-score">
                        Readiness for {nextTier.toUpperCase()}:{" "}
                        <strong>{typeof readiness.score === "number" ? `${Math.round(readiness.score)}/100` : "—"}</strong>
                        {readiness.ready && <span className="text-green-700 dark:text-green-400"> · ready</span>}
                      </p>
                      {!!readiness.gaps?.length && (
                        <p className="text-muted-foreground">Gaps: {readiness.gaps.slice(0, 3).join("; ")}</p>
                      )}
                      {readiness.recommendation && (
                        <p className="text-muted-foreground">{readiness.recommendation}</p>
                      )}
                    </div>
                  ) : (
                    <p className="text-[11px] text-muted-foreground">Readiness unavailable.</p>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-7 text-xs"
                    onClick={handlePromote}
                    disabled={promoteBusy}
                    data-testid="promote-agent-button"
                  >
                    {promoteBusy ? "Promoting…" : `Promote to ${nextTier.toUpperCase()}`}
                  </Button>
                </>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default TrainingPanel;
