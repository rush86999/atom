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
  active_session_id?: string;
  session_status?: string;
  lesson_plan?: {
    mentor?: string;
    domain?: string;
    objective?: string;
    tasks?: string[];
    materials?: string[];
    supervisor_note?: string;
  } | null;
};

const API = process.env.NEXT_PUBLIC_API_URL || "";

/** First-time walkthrough for the very first training session, login to
 * graduation. Dismissible; remembers dismissal for the browser. */
const TRAINING_GUIDE_KEY = "atom_training_guide_dismissed";

const TrainingGuide: React.FC = () => {
    const [open, setOpen] = React.useState(false);
    const [ready, setReady] = React.useState(false);

    React.useEffect(() => {
        if (typeof window === "undefined") return;
        setOpen(window.localStorage.getItem(TRAINING_GUIDE_KEY) !== "1");
        setReady(true);
    }, []);

    if (!ready) return null;

    return (
        <div className="mb-8 rounded-xl border border-indigo-800/60 bg-indigo-950/30 p-5">
            <div className="flex items-start justify-between gap-3">
                <div>
                    <h2 className="text-lg font-semibold text-indigo-200">
                        First training session — walkthrough
                    </h2>
                    <p className="text-sm text-gray-400 mt-1">
                        Your new hire is a STUDENT. It cannot act on real data until you
                        supervise a training pass and score it. Six steps, login to promotion.
                    </p>
                </div>
                <button
                    onClick={() => {
                        window.localStorage.setItem(TRAINING_GUIDE_KEY, "1");
                        setOpen(false);
                    }}
                    className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs text-gray-300 shrink-0"
                >
                    Hide guide
                </button>
            </div>
            {open && (
                <ol className="mt-4 space-y-3 text-sm text-gray-300 list-decimal list-inside">
                    <li>
                        <span className="font-medium text-gray-100">Sign in</span> at{" "}
                        <a href="/login" className="text-sky-400 hover:underline">/login</a> with your
                        supervisor account (must be TEAM_LEAD+ to decide trainings).
                    </li>
                    <li>
                        <span className="font-medium text-gray-100">Approve the proposal</span> — below
                        under <em>Training Proposals</em>, review what it was blocked from and its
                        capability gaps, then click <span className="text-emerald-400 font-medium">Approve</span>.
                        This opens a training session.
                    </li>
                    <li>
                        <span className="font-medium text-gray-100">Train it on real work</span> — open{" "}
                        <a href="/agents" className="text-sky-400 hover:underline">/agents</a>, run the
                        hire on a genuine task drawn from its connected data (e.g. “Review the newest
                        Zoho CRM leads and draft outreach for the top one” — leads from the Zoho sync,
                        customer threads from the Outlook poller, documents from WorkDrive/OneDrive).
                        Correct its drafts, approve its access requests, iterate. Each supervised
                        session is recorded as an episode.
                    </li>
                    <li>
                        <span className="font-medium text-gray-100">Score the pass</span> — come back
                        here to <em>Active Training Sessions</em>, fill in performance (be honest — the
                        trust math uses it), tasks completed/total, errors, and written feedback, then
                        click <span className="text-sky-400 font-medium">Complete Training Session</span>.
                    </li>
                    <li>
                        <span className="font-medium text-gray-100">Repeat ×3</span> — promotion needs
                        3 supervised sessions plus work episodes at a ≥ 0.7 success ratio (thresholds
                        auto-tune per domain as history builds).
                    </li>
                    <li>
                        <span className="font-medium text-gray-100">Graduation</span> — when the gate
                        clears, the agent is promoted to INTERN automatically: it may then run, asking
                        your approval per automated action, and it can help mentor the next hire in
                        this domain.
                    </li>
                </ol>
            )}
        </div>
    );
};

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

  // Complete an APPROVED training session: supervisor scores the pass and the
  // backend boosts confidence / promotes STUDENT → INTERN when earned.
  const [sessionForms, setSessionForms] = useState<Record<string, {
    performance_score: string; supervisor_feedback: string;
    tasks_completed: string; total_tasks: string; errors_count: string;
  }>>({});
  const [lessonDrafts, setLessonDrafts] = useState<Record<string, { objective: string; tasks_text: string; saving?: boolean }>>({});

  const lessonDraft = (sid: string, plan: NonNullable<TrainingProposal["lesson_plan"]> | undefined) => {
    if (!lessonDrafts[sid]) {
      setLessonDrafts((prev) => ({
        [sid]: {
          objective: plan?.objective || "",
          tasks_text: (plan?.tasks || []).join("\n"),
        },
      }));
      return { objective: plan?.objective || "", tasks_text: (plan?.tasks || []).join("\n") };
    }
    return lessonDrafts[sid];
  };

  const saveLesson = async (sid: string) => {
    const draft = lessonDrafts[sid];
    if (!draft) return;
    setLessonDrafts((prev) => ({ ...prev, [sid]: { ...draft, saving: true } }));
    try {
      const res = await fetch(`${API}/api/maturity/training/sessions/${sid}/guidance`, {
        method: "PATCH",
        headers: headers(),
        body: JSON.stringify({
          lesson_plan: {
            ...(proposals.find((p) => p.active_session_id === sid)?.lesson_plan || {}),
            objective: draft.objective,
            tasks: draft.tasks_text.split("\n").map((t) => t.trim()).filter(Boolean),
          },
        }),
      });
      setNotice(res.ok ? "Lesson plan saved." : `Lesson save failed (${res.status}).`);
    } catch (e) {
      setError(`Lesson save failed: ${String(e)}`);
    } finally {
      setLessonDrafts((prev) => ({ ...prev, [sid]: { ...draft, saving: false } }));
    }
  };

  const updateSessionForm = (sid: string, patch: Partial<{ performance_score: string; supervisor_feedback: string; tasks_completed: string; total_tasks: string; errors_count: string }>) =>
    setSessionForms((prev) => ({
      ...prev,
      [sid]: { performance_score: "0.8", supervisor_feedback: "", tasks_completed: "3", total_tasks: "3", errors_count: "0", ...prev[sid], ...patch },
    }));

  const completeSession = async (proposalId: string, sessionId: string) => {
    setNotice(null);
    const f = sessionForms[sessionId] || { performance_score: "0.8", supervisor_feedback: "", tasks_completed: "3", total_tasks: "3", errors_count: "0" };
    try {
      const res = await fetch(`${API}/api/maturity/training/sessions/${sessionId}/complete`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          performance_score: Number(f.performance_score) || 0,
          supervisor_feedback: f.supervisor_feedback || "Supervised pass completed.",
          errors_count: Number(f.errors_count) || 0,
          tasks_completed: Number(f.tasks_completed) || 0,
          total_tasks: Number(f.total_tasks) || 1,
          capabilities_developed: [],
          capability_gaps_remaining: [],
        }),
      });
      if (!res.ok) {
        setError(`Session completion failed (${res.status}).`);
        return;
      }
      const data = await res.json().catch(() => ({}));
      setNotice(`Training session completed.${data?.promotion ? " 🎓 Promotion granted!" : ""}`);
      loadProposals();
    } catch (e) {
      setError(`Session completion failed: ${String(e)}`);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6 lg:p-10">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-1">Approvals</h1>
        <p className="text-sm text-gray-400 mb-6">
          Actions paused for human approval. Agents wait here until a decision is made.
        </p>

        <TrainingGuide />

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
          <h2 className="text-lg font-semibold">Active Training Sessions</h2>
          <p className="text-sm text-gray-400 mb-4">
            Approved trainings in progress. Work with the agent (chat at /agents), then score the
            supervised pass here — completion boosts the agent's confidence and can promote it to INTERN.
          </p>
          {proposals.filter((p) => p.active_session_id).length === 0 ? (
            <div className="rounded-xl border border-gray-800 p-6 text-center text-gray-500">
              No active training sessions. Approve a proposal to start one.
            </div>
          ) : (
            <div className="space-y-3">
              {proposals.filter((p) => p.active_session_id).map((p) => {
                const sid = p.active_session_id as string;
                const f = sessionForms[sid] || { performance_score: "0.8", supervisor_feedback: "", tasks_completed: "3", total_tasks: "3", errors_count: "0" };
                return (
                  <div key={p.id} className="rounded-xl border border-emerald-800/60 bg-gray-900 p-4">
                    <div className="font-medium text-emerald-300">{p.title}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      agent {p.agent_name || String(p.agent_id).slice(0, 8)} · session {sid.slice(0, 8)} · {p.session_status}
                    </div>
                    {(() => {
                      const draft = lessonDraft(sid, p.lesson_plan);
                      const setD = (patch: Partial<{ objective: string; tasks_text: string }>) =>
                        setLessonDrafts((prev) => ({ ...prev, [sid]: { ...draft, ...patch } }));
                      return (
                        <div className="mt-3 p-3 rounded-lg bg-gray-800/60 border border-gray-700">
                          <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">
                            Mentor-proposed lesson — edit freely, then train the hire on it
                          </div>
                          <div className="text-xs text-gray-400 mb-1">Mentor: {p.lesson_plan?.mentor || "atom_main"}</div>
                          <label className="block text-xs text-gray-400">
                            Objective
                            <input
                              value={draft.objective}
                              onChange={(e) => setD({ objective: e.target.value })}
                              className="mt-1 w-full px-2 py-1.5 rounded-md bg-gray-800 border border-gray-700 text-sm text-gray-200"
                            />
                          </label>
                          <label className="block text-xs text-gray-400 mt-2">
                            Tasks (one per line)
                            <textarea
                              rows={4}
                              value={draft.tasks_text}
                              onChange={(e) => setD({ tasks_text: e.target.value })}
                              className="mt-1 w-full px-2 py-1.5 rounded-md bg-gray-800 border border-gray-700 text-sm text-gray-200 font-mono"
                            />
                          </label>
                          <div className="flex gap-2 mt-2">
                            <button
                              onClick={() => saveLesson(sid)}
                              className="px-3 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-xs font-medium"
                            >
                              Save lesson
                            </button>
                            <a
                              href={`/chat?agent_id=${p.agent_id}`}
                              className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-medium"
                            >
                              Open training chat →
                            </a>
                          </div>
                        </div>
                      );
                    })()}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
                      <label className="text-xs text-gray-400">
                        Performance (0–1)
                        <input
                          type="number" min={0} max={1} step={0.05}
                          value={f.performance_score}
                          onChange={(e) => updateSessionForm(sid, { performance_score: e.target.value })}
                          className="mt-1 w-full px-2 py-1.5 rounded-md bg-gray-800 border border-gray-700 text-sm"
                        />
                      </label>
                      <label className="text-xs text-gray-400">
                        Tasks completed
                        <input
                          type="number" min={0}
                          value={f.tasks_completed}
                          onChange={(e) => updateSessionForm(sid, { tasks_completed: e.target.value })}
                          className="mt-1 w-full px-2 py-1.5 rounded-md bg-gray-800 border border-gray-700 text-sm"
                        />
                      </label>
                      <label className="text-xs text-gray-400">
                        Total tasks
                        <input
                          type="number" min={1}
                          value={f.total_tasks}
                          onChange={(e) => updateSessionForm(sid, { total_tasks: e.target.value })}
                          className="mt-1 w-full px-2 py-1.5 rounded-md bg-gray-800 border border-gray-700 text-sm"
                        />
                      </label>
                      <label className="text-xs text-gray-400">
                        Errors
                        <input
                          type="number" min={0}
                          value={f.errors_count}
                          onChange={(e) => updateSessionForm(sid, { errors_count: e.target.value })}
                          className="mt-1 w-full px-2 py-1.5 rounded-md bg-gray-800 border border-gray-700 text-sm"
                        />
                      </label>
                    </div>
                    <textarea
                      placeholder="Supervisor feedback — what the agent did well, what to correct…"
                      value={f.supervisor_feedback}
                      onChange={(e) => updateSessionForm(sid, { supervisor_feedback: e.target.value })}
                      rows={2}
                      className="mt-3 w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-sm"
                    />
                    <button
                      onClick={() => completeSession(p.id, sid)}
                      className="mt-3 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-sm font-medium"
                    >
                      Complete Training Session
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

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
              {proposals.filter((p) => p.status === "pending" || p.status === "pending_approval").map((p) => (
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
