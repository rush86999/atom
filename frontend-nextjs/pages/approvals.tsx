import React, { useCallback, useEffect, useState } from "react";
import { getAuthToken, getCurrentUserId } from "@/lib/identity";

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
  agent_tier?: string;
  agent_confidence?: number;
  agent_domain?: string;
  lesson_plan?: {
    mentor?: string;
    domain?: string;
    objective?: string;
    tasks?: string[];
    materials?: string[];
    supervisor_note?: string;
  } | null;
};

/** Role-canvas cards spawned for a training session (Phase 2 registry). */
type SessionCanvas = {
  canvas_id: string;
  canvas_type: string;
  details?: {
    name?: string;
    default_tasks?: string[];
    trusted_scope?: { never?: string[] };
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
  const [editingAction, setEditingAction] = useState<string | null>(null);
  const [editedParams, setEditedParams] = useState<Record<string, string>>({});
  const [sessionCanvases, setSessionCanvases] = useState<Record<string, SessionCanvas[]>>({});
  const [loadingCanvases, setLoadingCanvases] = useState<Record<string, boolean>>({});

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
  const loadSessionCanvases = useCallback(async (sid: string) => {
    setLoadingCanvases((prev) => ({ ...prev, [sid]: true }));
    try {
      const res = await fetch(`${API}/api/maturity/training/sessions/${sid}/canvases`, { headers: headers() });
      if (res.ok) {
        const json = await res.json();
        setSessionCanvases((prev) => ({ ...prev, [sid]: Array.isArray(json.canvases) ? json.canvases : [] }));
      }
    } catch {
      // Non-critical: cards are a convenience, not a gate.
    } finally {
      setLoadingCanvases((prev) => ({ ...prev, [sid]: false }));
    }
  }, [headers]);

  const loadProposals = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/maturity/training/proposals`, { headers: headers() });
      if (res.ok) {
        const json = await res.json();
        const list = Array.isArray(json) ? json : (json.proposals ?? []);
        setProposals(list);
        // Fetch the role-canvas cards for every active session (best-effort).
        for (const p of list) {
          if (p.active_session_id) loadSessionCanvases(String(p.active_session_id));
        }
      }
    } catch {
      // Non-critical: the HITL queue still works without this section.
    }
  }, [headers, loadSessionCanvases]);

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

  const decide = async (id: string, decision: "approved" | "rejected", modifiedParams?: Record<string, unknown>) => {
    setNotice(null);
    try {
      const res = await fetch(`${API}/api/agents/approvals/${id}`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ decision, ...(modifiedParams ? { modified_params: modifiedParams } : {}) }),
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

  const [taskSuggestions, setTaskSuggestions] = useState<Record<string, { text: string; sending?: boolean }>>({});
  const [recordSearch, setRecordSearch] = useState<Record<string, { q: string; results: { record: string }[]; loading: boolean }>>({});
  const [pinnedRecords, setPinnedRecords] = useState<Record<string, string[]>>({});

  const updateTaskSuggestion = (sid: string, patch: Partial<{ text: string; sending: boolean }>) =>
    setTaskSuggestions((prev) => ({
      ...prev,
      [sid]: { text: "", ...(prev[sid] || {}), ...patch },
    }));

  // Supervisor suggests a task for the hire: lands in the lesson plan (so the
  // training record shows it) AND goes straight to the agent over chat —
  // agent-tagged, so the supervised pass is recorded as an episode.
  const suggestTask = async (p: TrainingProposal, sid: string) => {
    const st = taskSuggestions[sid];
    const text = (st?.text || "").trim();
    if (!text) return;
    setTaskSuggestions((prev) => ({ ...prev, [sid]: { text, sending: true } }));
    const pins = pinnedRecords[sid] || [];
    const scopeQ = recordSearch[sid]?.q?.trim();
    const scopedMessage =
      `Supervisor task: ${text}` +
      (pins.length ? `\nWork on EXACTLY these records:\n${pins.join("\n")}` : "") +
      (scopeQ && !pins.length ? `\nScope filter: ${scopeQ}` : "");
    try {
      const res = await fetch(`${API}/api/chat/message`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          message: scopedMessage,
          user_id: getCurrentUserId(),
          session_id: `training-chat-${sid}`,
          agent_id: p.agent_id,
        }),
      });
      if (!res.ok) {
        setError(`Task send failed (${res.status}).`);
        setTaskSuggestions((prev) => ({ ...prev, [sid]: { text, sending: false } }));
        return;
      }
      // record it in the lesson plan for the training record
      try {
        const plan = p.lesson_plan || {};
        const tasks = [...(plan.tasks || []), `Supervisor task: ${text}`];
        await fetch(`${API}/api/maturity/training/sessions/${sid}/guidance`, {
          method: "PATCH",
          headers: headers(),
          body: JSON.stringify({
            lesson_plan: { ...plan, tasks },
            supervisor_note: `Supervisor suggested task: ${text}`,
          }),
        });
      } catch { /* lesson persistence is best-effort */ }
      setNotice(`Task sent to ${p.agent_name || "the agent"}. It will work it in the training chat.`);
      setTaskSuggestions((prev) => ({ ...prev, [sid]: { text: "", sending: false } }));
      loadProposals();
    } catch (e) {
      setError(`Task send failed: ${String(e)}`);
      setTaskSuggestions((prev) => ({ ...prev, [sid]: { text, sending: false } }));
    }
  };

  const searchTimer = React.useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const searchRecords = (sid: string, agentId: string, q: string) => {
    setRecordSearch((prev) => ({ ...prev, [sid]: { ...(prev[sid] || { results: [], loading: false }), q, loading: !!q } }));
    if (searchTimer.current[sid]) clearTimeout(searchTimer.current[sid]);
    if (!q.trim()) {
      setRecordSearch((prev) => ({ ...prev, [sid]: { q, results: [], loading: false } }));
      return;
    }
    searchTimer.current[sid] = setTimeout(async () => {
      try {
        const res = await fetch(`${API}/api/data-ingestion/memory/records?q=${encodeURIComponent(q)}&agent_id=${agentId}`, { headers: headers() });
        const data = res.ok ? await res.json() : { results: [] };
        setRecordSearch((prev) => ({ ...prev, [sid]: { q, results: data.results || [], loading: false } }));
      } catch {
        setRecordSearch((prev) => ({ ...prev, [sid]: { q, results: [], loading: false } }));
      }
    }, 500);
  };

  const togglePin = (sid: string, record: string) =>
    setPinnedRecords((prev) => {
      const cur = prev[sid] || [];
      return { ...prev, [sid]: cur.includes(record) ? cur.filter((r) => r !== record) : [...cur, record] };
    });

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
                  {editingAction === a.id && (
                    <div className="mt-3">
                      <div className="text-xs text-gray-400 mb-1">
                        Modify the task before approving — the agent resumes with these params:
                      </div>
                      <textarea
                        rows={4}
                        value={editedParams[a.id] ?? JSON.stringify(a.params ?? {}, null, 2)}
                        onChange={(e) =>
                          setEditedParams((prev) => ({ ...prev, [a.id]: e.target.value }))
                        }
                        className="w-full px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-xs font-mono text-gray-200"
                      />
                    </div>
                  )}
                  <div className="flex gap-2 shrink-0">
                    {editingAction === a.id ? (
                      <>
                        <button
                          onClick={() => {
                            try {
                              const modified = JSON.parse(editedParams[a.id] ?? "{}");
                              decide(a.id, "approved", modified);
                              setEditingAction(null);
                            } catch {
                              setError("Modified params must be valid JSON.");
                            }
                          }}
                          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-medium"
                        >
                          Approve modified
                        </button>
                        <button
                          onClick={() => setEditingAction(null)}
                          className="px-4 py-2 rounded-lg bg-gray-700 text-sm font-medium"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => {
                            setEditingAction(a.id);
                            setEditedParams((prev) => ({
                              ...prev,
                              [a.id]: JSON.stringify(a.params ?? {}, null, 2),
                            }));
                          }}
                          className="px-4 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-sm font-medium"
                        >
                          Modify
                        </button>
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
                      </>
                    )}
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
            An INTERN may then PROPOSE automated actions: those arrive in this same queue for your
            approval, and you keep coaching it over chat the same way.
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
                      session {sid.slice(0, 8)} · {p.session_status}
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                      <span className="px-2 py-0.5 rounded-full bg-sky-900/40 text-sky-300">
                        Student: {p.agent_name || String(p.agent_id).slice(0, 8)}
                      </span>
                      <span className="px-2 py-0.5 rounded-full bg-gray-800 text-gray-300">
                        tier: {p.agent_tier || "student"}
                      </span>
                      {typeof p.agent_confidence === "number" && (
                        <span className="px-2 py-0.5 rounded-full bg-gray-800 text-gray-300">
                          confidence: {p.agent_confidence.toFixed(2)}
                        </span>
                      )}
                      {p.agent_domain && (
                        <span className="px-2 py-0.5 rounded-full bg-gray-800 text-gray-300">
                          domain: {p.agent_domain}
                        </span>
                      )}
                      <span className="px-2 py-0.5 rounded-full bg-indigo-900/40 text-indigo-300">
                        mentor: {p.lesson_plan?.mentor || "atom_main"}
                      </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <a
                        href={`/chat?agent_id=${p.agent_id}`}
                        className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-medium"
                      >
                        Chat with student →
                      </a>
                      <a
                        href="/chat?agent_id=atom_main"
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-medium"
                      >
                        Ask mentor (Atom) →
                      </a>
                      <span className="text-xs text-gray-500 self-center">
                        Tip: ask the mentor “how should we train the new hire on this lead?”, then run
                        its suggestion with the student and refine.
                      </span>
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
                    {(sessionCanvases[sid]?.length ?? 0) > 0 && (
                      <div className="mt-3">
                        <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">
                          Role canvases — session artifacts ({sessionCanvases[sid].length})
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                          {sessionCanvases[sid].map((cv) => {
                            const never = cv.details?.trusted_scope?.never || [];
                            const tasks = cv.details?.default_tasks || [];
                            return (
                              <div key={cv.canvas_id} className="rounded-lg border border-indigo-800/50 bg-indigo-950/20 p-3">
                                <div className="flex flex-wrap items-center gap-2 text-xs">
                                  <span className="px-2 py-0.5 rounded-full bg-indigo-900/50 text-indigo-300 uppercase">
                                    {cv.canvas_type}
                                  </span>
                                  <span className="font-medium text-indigo-200">
                                    {cv.details?.name || cv.canvas_type}
                                  </span>
                                </div>
                                {tasks.length > 0 && (
                                  <ul className="mt-2 space-y-1 text-xs text-gray-400 list-disc list-inside">
                                    {tasks.map((t, i) => <li key={i}>{t}</li>)}
                                  </ul>
                                )}
                                {never.length > 0 && (
                                  <div className="mt-2 text-xs text-red-400">
                                    🚫 never: {never.join(", ")}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}
                    {loadingCanvases[sid] && !(sessionCanvases[sid]?.length) && (
                      <div className="mt-3 text-xs text-gray-500">Loading role canvases…</div>
                    )}
                    <div className="mt-3 space-y-2">
                      {(() => {
                        const st = taskSuggestions[sid] || { text: "", sending: false };
                        const rs = recordSearch[sid] || { q: "", results: [], loading: false };
                        const pins = pinnedRecords[sid] || [];
                        return (
                          <>
                            <div className="flex gap-2">
                              <input
                                value={st.text}
                                onChange={(e) => updateTaskSuggestion(sid, { text: e.target.value })}
                                onKeyDown={(e) => { if (e.key === "Enter" && !st.sending) suggestTask(p, sid); }}
                                placeholder="Suggest a training task… e.g. Qualify the Northline lead over email"
                                className="flex-1 px-3 py-2 rounded-md bg-gray-800 border border-gray-700 text-sm text-gray-200"
                              />
                              <button
                                onClick={() => suggestTask(p, sid)}
                                disabled={st.sending || !st.text.trim()}
                                className="px-3 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 text-xs font-medium disabled:opacity-50"
                              >
                                {st.sending ? "Sending…" : "Suggest task"}
                              </button>
                            </div>
                            <div className="flex gap-2">
                              <input
                                value={rs.q}
                                onChange={(e) => searchRecords(sid, p.agent_id, e.target.value)}
                                placeholder="Limit to — search ingested records (lead, invoice, file…)"
                                className="flex-1 px-3 py-1.5 rounded-md bg-gray-800 border border-gray-700 text-xs text-gray-300"
                              />
                              {pins.length > 0 && (
                                <span className="self-center text-xs text-emerald-400">{pins.length} pinned</span>
                              )}
                            </div>
                            {rs.loading && <div className="text-xs text-gray-500">Searching memory…</div>}
                            {rs.results.length > 0 && (
                              <div className="space-y-1">
                                {rs.results.slice(0, 6).map((r) => {
                                  const pinned = pins.includes(r.record);
                                  return (
                                    <button
                                      key={r.record}
                                      onClick={() => togglePin(sid, r.record)}
                                      className={`block w-full text-left px-2 py-1 rounded text-xs truncate ${
                                        pinned
                                          ? "bg-emerald-900/40 text-emerald-300 border border-emerald-700"
                                          : "bg-gray-800/60 text-gray-400 hover:bg-gray-800"
                                      }`}
                                    >
                                      {pinned ? "📌 " : ""}{r.record.slice(0, 120)}
                                    </button>
                                  );
                                })}
                              </div>
                            )}
                          </>
                        );
                      })()}
                    </div>
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
