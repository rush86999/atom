import React, { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { getAuthToken, getCurrentUserId } from "@/lib/identity";
import { SelfDirectedPathwayCard } from "@/components/Agents/SelfDirectedPathwayCard";
import {
    type ActionProposal,
    type ActionProposalApprovalResult,
    SelfDirectedAgentProgress,
    readGraduationPromotionResponse,
} from "@/lib/maturity-api";
import { useActionProposals } from "@/hooks/useActionProposals";
import { buildActionProposalPreview } from "@/lib/action-proposal-preview";
import { useUserRole } from "@/lib/user-role";

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

const TASK_ADMISSION_ACTION = "never_autonomous_task";
const TASK_PREVIEW_LIMIT = 1200;
const TASK_CLASSIFICATION_DIMENSIONS: Array<{ key: string; label: string }> = [
  { key: "difficulty", label: "Difficulty" },
  { key: "category", label: "Category" },
  { key: "domain", label: "Domain" },
];

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asText(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function asIdList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (entry): entry is string => typeof entry === "string" && entry.trim().length > 0
  );
}

type ReviewedRuleBinding = { id: string; revision: string | null };

function readRuleBindings(params: Record<string, unknown>): ReviewedRuleBinding[] {
  if (!Array.isArray(params.rule_bindings)) return [];
  const bindings: ReviewedRuleBinding[] = [];
  for (const raw of params.rule_bindings) {
    const entry = asRecord(raw);
    const id = asText(entry?.id);
    if (!entry || !id) continue;
    const revisionValue = entry.revision;
    const revision =
      typeof revisionValue === "number" || typeof revisionValue === "string"
        ? String(revisionValue)
        : null;
    bindings.push({ id, revision });
  }
  return bindings;
}

/**
 * A never-autonomous task admission is a human decision on ONE exact task
 * execution. The server owns the task text, classification and rule match;
 * this card only renders what the server recorded. It never re-derives a
 * match, and it keeps hashes/ids out of the primary reading flow because
 * they are audit evidence, not something a reviewer reads to decide.
 */
function TaskAdmissionReview({ action }: { action: PendingAction }) {
  const params = asRecord(action.params) ?? {};
  const taskInput = asText(params.task_input);
  const profile = asRecord(params.task_profile);
  const bindings = readRuleBindings(params);
  const recordedRuleIds = bindings.length
    ? bindings.map((binding) => binding.id)
    : asIdList(params.rule_ids);
  const executionId = asText(params.execution_id);
  const taskFingerprint = asText(params.task_fingerprint);
  const ownerUserId = asText(params.owner_user_id);
  const preview = taskInput ? taskInput.slice(0, TASK_PREVIEW_LIMIT) : "";
  const previewTruncated = Boolean(taskInput && taskInput.length > TASK_PREVIEW_LIMIT);
  const classification = TASK_CLASSIFICATION_DIMENSIONS.map((dimension) => ({
    ...dimension,
    value: profile ? asText(profile[dimension.key]) : null,
  }));
  const missingClassification = classification.some((entry) => !entry.value);

  return (
    <div>
      <div data-testid="task-admission-primary">
        <div className="flex flex-wrap items-baseline gap-2">
          <div className="font-medium text-amber-300">Task execution admission</div>
          {action.agent_id && (
            <span className="text-xs text-gray-500">
              agent {String(action.agent_id).slice(0, 8)}
            </span>
          )}
        </div>
        <div className="text-xs text-gray-500 mt-1">
          A server-owned rule matched this task before autonomous work began. Review
          the exact task and classification below.
        </div>

        <div className="mt-3 rounded-lg border border-amber-700/60 bg-amber-950/20 p-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-amber-200">
            Task to approve
          </div>
          {taskInput ? (
            <>
              <pre
                data-testid="task-admission-task-input"
                className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-words font-mono text-sm text-gray-100"
              >
                {preview}
              </pre>
              <p className="mt-2 text-xs text-gray-500">
                {previewTruncated
                  ? `Preview truncated — showing the first ${TASK_PREVIEW_LIMIT.toLocaleString()} of ${taskInput.length.toLocaleString()} recorded characters. The approval binds the complete task; the fingerprint is in the technical details.`
                  : "Server-recorded task preview (up to 2,000 characters). The approval binds the complete task."}
              </p>
            </>
          ) : (
            <p data-testid="task-admission-task-input-missing" className="mt-2 text-sm text-amber-200">
              Task text unavailable — the server recorded no readable task preview for
              this admission. Reject and request a fresh review if you cannot verify
              the task.
            </p>
          )}
        </div>

        <div className="mt-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Server classification
          </div>
          {profile ? (
            <>
              <div
                data-testid="task-admission-classification"
                className="mt-2 flex flex-wrap gap-2 text-xs"
              >
                {classification.map((entry) => (
                  <span
                    key={entry.key}
                    className={`px-2 py-0.5 rounded-full ${
                      entry.value
                        ? "bg-sky-900/40 text-sky-200"
                        : "bg-gray-800 text-gray-400"
                    }`}
                  >
                    {entry.label}: {entry.value ?? "not classified"}
                  </span>
                ))}
              </div>
              {missingClassification && (
                <p className="mt-1 text-xs text-gray-500">
                  Some classification values are unavailable. Missing values are not
                  treated as a safe match.
                </p>
              )}
            </>
          ) : (
            <p
              data-testid="task-admission-classification-missing"
              className="mt-2 text-sm text-amber-200"
            >
              Task classification unavailable — the server recorded no trusted task
              profile. Missing classification is not evidence that the task is safe.
            </p>
          )}
        </div>

        <div className="mt-3 text-sm text-gray-300">
          <span className="font-semibold text-gray-200">Why this paused:</span>{" "}
          {asText(action.reason) || "The server did not provide a reason for this review."}
        </div>
        {asText(action.reason) && (
          <div className="mt-1 text-xs text-gray-500">
            Rule matching is decided by the server; this page does not re-evaluate or
            widen it. Any matched rule name is reported in the server reason above.
          </div>
        )}

        <div
          data-testid="task-admission-one-execution"
          className="mt-3 rounded-lg border border-indigo-800/60 bg-indigo-950/30 p-3 text-sm text-indigo-100"
        >
          <span className="font-semibold">
            Approving admits this one task execution only.
          </span>{" "}
          It does not edit the rule, disable future reviews, or authorize any other
          task. The task text and rule binding are immutable here, so this card has
          no Modify step; prepare a new task if the scope must change.
        </div>
      </div>

      <details
        data-testid="task-admission-binding"
        className="mt-3 rounded-lg border border-gray-800 bg-gray-950/50 p-3 text-xs text-gray-400"
      >
        <summary className="cursor-pointer text-gray-300">
          Technical binding (audit details)
        </summary>
        <dl className="mt-2 grid grid-cols-1 gap-x-4 gap-y-1 sm:grid-cols-3">
          <dt className="text-gray-500">Execution ID</dt>
          <dd className="font-mono break-all sm:col-span-2">
            {executionId ?? "Not recorded"}
          </dd>
          <dt className="text-gray-500">Task fingerprint</dt>
          <dd className="font-mono break-all sm:col-span-2">
            {taskFingerprint ?? "Not recorded"}
          </dd>
          <dt className="text-gray-500">Owner user ID</dt>
          <dd className="font-mono break-all sm:col-span-2">
            {ownerUserId ?? "Not recorded"}
          </dd>
        </dl>
        <div className="mt-2 font-semibold text-gray-400">
          Reviewed rule revisions
        </div>
        {bindings.length > 0 ? (
          <ul className="mt-1 space-y-0.5">
            {bindings.map((binding) => (
              <li key={`${binding.id}:${binding.revision ?? "unknown"}`}>
                <span className="font-mono">{binding.id}</span>
                {binding.revision === null
                  ? " — revision not recorded"
                  : ` — revision ${binding.revision}`}
              </li>
            ))}
          </ul>
        ) : recordedRuleIds.length > 0 ? (
          <ul className="mt-1 space-y-0.5">
            {recordedRuleIds.map((ruleId) => (
              <li key={ruleId}>
                <span className="font-mono">{ruleId}</span> — revision not recorded
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-1">
            No reviewed rule IDs or revisions were recorded in this approval.
          </p>
        )}
      </details>
    </div>
  );
}

/** First-time walkthrough for the very first training session, login to
 * graduation. Dismissible; remembers dismissal for the browser. */
const TRAINING_GUIDE_KEY = "atom_training_guide_dismissed";
const subscribeToNothing = () => () => {};
const getClientTrue = () => true;
const getServerFalse = () => false;
const subscribeToTrainingGuide = (onStoreChange: () => void) => {
    if (typeof window === "undefined") return () => {};
    const onStorage = (event: StorageEvent) => {
        if (event.key === TRAINING_GUIDE_KEY) onStoreChange();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
};
const getTrainingGuideOpen = () =>
    typeof window !== "undefined" && window.localStorage.getItem(TRAINING_GUIDE_KEY) !== "1";

const TrainingGuide: React.FC = () => {
    const ready = React.useSyncExternalStore(
        subscribeToNothing,
        getClientTrue,
        getServerFalse
    );
    const restoredOpen = React.useSyncExternalStore(
        subscribeToTrainingGuide,
        getTrainingGuideOpen,
        getServerFalse
    );
    const [openOverride, setOpenOverride] = React.useState<boolean | undefined>(undefined);
    const open = openOverride ?? restoredOpen;

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
                        setOpenOverride(false);
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
                        <Link href="/login" className="text-sky-400 hover:underline">/login</Link> with your
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
                        <Link href="/agents" className="text-sky-400 hover:underline">/agents</Link>, run the
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
                        <span className="font-medium text-gray-100">Build relevant experience</span> —
                        complete the training and work requirements shown in the agent’s readiness
                        panel. Requirements can vary with the current policy and domain history.
                    </li>
                    <li>
                        <span className="font-medium text-gray-100">Review capability before graduation</span> —
                        experience alone does not qualify an agent. Select its actual task evidence,
                        request a qualification review, and inspect the work against the rubric in
                        Approvals. A valid review and the remaining readiness requirements are needed
                        before promotion, unless the owner has explicitly configured an exception for
                        that agent. The new tier’s permissions apply only after promotion succeeds.
                    </li>
                </ol>
            )}
        </div>
    );
};

type RecentDecision = {
  id: string;
  action_type: string;
  status: string;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  created_at?: string | null;
  has_parameter_history?: boolean;
};

type DecisionHistoryRevision = {
  revision?: number | null;
  reviewed_params?: unknown;
  approved_params?: unknown;
  modified?: boolean | null;
  modified_by?: string | null;
  modified_at?: string | null;
  reason?: string | null;
};

type DecisionHistory = {
  approval_id: string;
  action_type: string;
  status: string;
  original_known: boolean;
  original_params?: unknown;
  effective_params?: unknown;
  modified?: boolean | null;
  revision?: number | null;
  modified_by?: string | null;
  modified_at?: string | null;
  reason?: string | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  history_entries: number;
  legacy_unrecorded: boolean;
  history_complete?: boolean;
  malformed_history_entries?: number;
  history_unreadable?: boolean;
  revisions?: DecisionHistoryRevision[];
  revisions_truncated?: boolean;
  redacted?: boolean;
};

type HistoryLoadState = "idle" | "loading" | "ready" | "denied" | "notfound" | "unavailable";

function formatTimestamp(value?: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString();
}

function classifyHistoryStatus(status: number): HistoryLoadState {
  if (status === 403) return "denied";
  if (status === 404) return "notfound";
  return "unavailable";
}

function TextBlock({ value, testId }: { value: unknown; testId: string }) {
  let text: string;
  try {
    const serialized = JSON.stringify(value, null, 2);
    text = serialized === undefined ? String(value) : serialized;
  } catch {
    text = String(value);
  }
  return (
    <pre
      data-testid={testId}
      className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap break-all rounded bg-gray-950 border border-gray-800 p-2 text-xs text-gray-200"
    >
      {text}
    </pre>
  );
}

/**
 * Redacted reviewed-vs-approved parameter history for ONE decided approval.
 * Rendered on demand only: the ordinary pending queue performs no extra
 * reads, and this view never receives the protected context_snapshot.
 * "Approved" is kept distinct from "executed"/"verified".
 */
function ParameterHistoryDetail({
  state,
  history,
}: {
  state?: HistoryLoadState;
  history?: DecisionHistory;
}) {
  if (state === "loading") {
    return <p className="text-xs text-gray-400" data-testid="parameter-history-loading">Loading parameter history…</p>;
  }
  if (state === "denied") {
    return (
      <p role="status" data-testid="parameter-history-denied" className="text-xs text-amber-300">
        You are not authorized to read this decision history.
      </p>
    );
  }
  if (state === "notfound") {
    return (
      <p role="status" data-testid="parameter-history-notfound" className="text-xs text-gray-400">
        Approval not found.
      </p>
    );
  }
  if (state === "unavailable") {
    return (
      <p role="alert" data-testid="parameter-history-unavailable" className="text-xs text-red-300">
        Decision history is unavailable right now. Retry by reopening this panel.
      </p>
    );
  }
  if (!history) return null;

  const originalText =
    history.original_known && history.original_params !== null
      ? history.original_params
      : null;
  const effectiveText =
    history.effective_params !== null && history.effective_params !== undefined
      ? history.effective_params
      : null;
  const revisions = Array.isArray(history.revisions) ? history.revisions : [];

  return (
    <div className="mt-2 rounded border border-gray-700 bg-gray-900/70 p-3 text-xs" data-testid="parameter-history">
      <p className="text-gray-200" data-testid="parameter-history-status">
        Decision status: <span className="font-mono">{history.status || "unknown"}</span>
      </p>
      <p className="text-gray-400 mt-1" data-testid="parameter-history-execution">
        {history.status === "executed"
          ? "Execution is recorded on this approval row; this history does not verify its outcome."
          : "This confirms the approval decision only. It does not confirm that the action executed or that its result was verified."}
      </p>
      <p className="text-gray-400 mt-1" data-testid="parameter-history-actor">
        By {history.reviewed_by || "unknown reviewer"}
        {history.reviewed_at ? ` at ${formatTimestamp(history.reviewed_at)}` : " at an unrecorded time"}
      </p>
      <p className="text-gray-400" data-testid="parameter-history-reason">
        {history.reason ? `Reason: ${history.reason}` : "No reason recorded."}
      </p>

      <div className="mt-2">
        <p className="font-medium text-gray-300">Reviewed (original)</p>
        {originalText !== null ? (
          <TextBlock value={originalText} testId="parameter-history-original" />
        ) : (
          <p className="text-amber-300" data-testid="parameter-history-original-unknown">
            Original reviewed parameters unavailable — this decision predates parameter
            history. Nothing was reconstructed.
          </p>
        )}
      </div>

      <div className="mt-2">
        <p className="font-medium text-gray-300">Approved (effective)</p>
        {effectiveText !== null ? (
          <TextBlock value={effectiveText} testId="parameter-history-effective" />
        ) : (
          <p className="text-gray-400" data-testid="parameter-history-effective-missing">
            No effective parameters were recorded (no approval).
          </p>
        )}
      </div>

      <p className="mt-2 text-gray-400" data-testid="parameter-history-modified">
        {history.modified === true
          ? "Parameters were modified before approval."
          : history.modified === false
            ? "Approved exactly as reviewed."
            : "Whether parameters were modified is unknown."}
      </p>

      {revisions.length > 0 && (
        <div className="mt-2" data-testid="parameter-history-revisions">
          <p className="font-medium text-gray-300">
            Revisions ({history.history_entries} recorded)
          </p>
          <ol className="list-decimal list-inside text-gray-400">
            {revisions.map((revision, index) => (
              <li key={`${revision.revision ?? "unknown"}-${index}`}>
                Revision {revision.revision ?? "unknown"} — {revision.modified_by || "unknown actor"}
                {revision.modified_at ? ` at ${formatTimestamp(revision.modified_at)}` : ""}
                {revision.reason ? ` — ${revision.reason}` : " — no reason recorded"}
              </li>
            ))}
          </ol>
          {history.revisions_truncated && (
            <p className="text-gray-500" data-testid="parameter-history-truncated">
              Only the most recent {revisions.length} revisions are shown (bounded read).
            </p>
          )}
        </div>
      )}

      {history.history_complete === false && (
        <p className="mt-2 text-amber-300" data-testid="parameter-history-incomplete">
          Some stored history entries could not be read; this lineage is incomplete.
        </p>
      )}
      {history.legacy_unrecorded && (
        <p className="mt-2 text-amber-300" data-testid="parameter-history-legacy">
          This approval predates parameter history. The reviewed original is unknown.
        </p>
      )}
      {history.redacted && (
        <p className="mt-2 text-gray-500" data-testid="parameter-history-redaction">
          Credential-shaped fields are redacted in this view. This is not a signed or
          certified record.
        </p>
      )}
    </div>
  );
}

/**
 * Discoverable, lazy audit readback on the existing Approvals page. Nothing is
 * fetched until the supervisor opens the section; each row's history is a
 * second on-demand read. Reloading the page reads the same durable rows.
 */
function DecisionHistoryPanel() {
  const [open, setOpen] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [recentState, setRecentState] = useState<HistoryLoadState>("idle");
  const [decisions, setDecisions] = useState<RecentDecision[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [historyState, setHistoryState] = useState<Record<string, HistoryLoadState>>({});
  const [histories, setHistories] = useState<Record<string, DecisionHistory>>({});

  const authHeaders = () => ({ Authorization: `Bearer ${getAuthToken() || ""}` });

  const loadRecent = useCallback(async () => {
    setRecentState("loading");
    try {
      const res = await fetch(`${API}/api/agents/approvals/recent?limit=20`, {
        headers: authHeaders(),
      });
      if (!res.ok) {
        setRecentState(classifyHistoryStatus(res.status));
        return;
      }
      const body = await res.json();
      setDecisions(Array.isArray(body) ? body : []);
      setRecentState("ready");
    } catch {
      setRecentState("unavailable");
    }
  }, []);

  const loadHistory = useCallback(async (id: string) => {
    setHistoryState((current) => ({ ...current, [id]: "loading" }));
    try {
      const res = await fetch(
        `${API}/api/agents/approvals/${encodeURIComponent(id)}/history?revision_limit=10`,
        { headers: authHeaders() }
      );
      if (!res.ok) {
        setHistoryState((current) => ({
          ...current,
          [id]: classifyHistoryStatus(res.status),
        }));
        return;
      }
      const body = await res.json();
      setHistories((current) => ({ ...current, [id]: body }));
      setHistoryState((current) => ({ ...current, [id]: "ready" }));
    } catch {
      setHistoryState((current) => ({ ...current, [id]: "unavailable" }));
    }
  }, []);

  const toggleOpen = () => {
    const next = !open;
    setOpen(next);
    if (next && !loaded) {
      setLoaded(true);
      loadRecent();
    }
  };

  return (
    <section className="mt-8" data-testid="decision-history-section">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">Decision history</h2>
          <p className="text-sm text-gray-400">
            What was originally reviewed versus what was approved. Loaded on demand.
          </p>
        </div>
        <button
          onClick={toggleOpen}
          aria-expanded={open}
          aria-controls="decision-history-body"
          className="px-4 py-2 rounded-lg bg-gray-800 hover:bg-gray-700 text-sm font-medium"
        >
          {open ? "Hide decision history" : "Show decision history"}
        </button>
      </div>

      {open && (
        <div id="decision-history-body" className="mt-3 rounded-xl border border-gray-800 p-4">
          {recentState === "loading" && (
            <p className="text-sm text-gray-400" data-testid="decision-history-loading">
              Loading recent decisions…
            </p>
          )}
          {recentState === "denied" && (
            <p role="status" data-testid="decision-history-denied" className="text-sm text-amber-300">
              You are not permitted to read decision history.
            </p>
          )}
          {recentState === "unavailable" && (
            <div data-testid="decision-history-unavailable">
              <p role="alert" className="text-sm text-red-300">
                Decision history is unavailable right now.
              </p>
              <button
                onClick={loadRecent}
                className="mt-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs"
              >
                Retry
              </button>
            </div>
          )}
          {recentState === "ready" && decisions.length === 0 && (
            <p className="text-sm text-gray-500" data-testid="decision-history-empty">
              No decided approvals recorded in your scope yet.
            </p>
          )}
          {recentState === "ready" && decisions.length > 0 && (
            <ul className="space-y-2">
              {decisions.map((decision) => (
                <li
                  key={decision.id}
                  data-testid={`decision-history-row-${decision.id}`}
                  className="rounded-lg border border-gray-800 p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm text-gray-300">
                      <span className="font-medium">{decision.action_type}</span>{" "}
                      <span className="font-mono text-xs text-gray-400" data-testid="decision-history-row-status">
                        {decision.status}
                      </span>{" "}
                      <span className="text-xs text-gray-500">
                        by {decision.reviewed_by || "unknown reviewer"}
                        {decision.reviewed_at || decision.created_at
                          ? ` at ${formatTimestamp(decision.reviewed_at || decision.created_at)}`
                          : ""}
                      </span>
                    </div>
                    <button
                      onClick={() => {
                        const next = !expanded[decision.id];
                        setExpanded((current) => ({ ...current, [decision.id]: next }));
                        if (next && !histories[decision.id]) loadHistory(decision.id);
                      }}
                      className="px-3 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-xs"
                    >
                      {expanded[decision.id] ? "Hide parameter history" : "Show parameter history"}
                    </button>
                  </div>
                  {expanded[decision.id] && (
                    <ParameterHistoryDetail
                      state={historyState[decision.id]}
                      history={histories[decision.id]}
                    />
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}


export default function ApprovalsPage() {
  // 2026-09-08 role-journey pass: decisions are team_lead+ on the backend.
  // Surface that BEFORE the click (members used to get raw 403 prose after
  // pressing Approve), and skip the supervisor-only queues for them.
  const { role, isSupervisor } = useUserRole();
  // "known" = we actually hold a role (fetch succeeded). A failed role fetch
  // fails OPEN — the backend enforces every gate; hiding actions on a
  // transient error would strand supervisors.
  const roleKnown = Boolean(role);
  const canDecide = !roleKnown || isSupervisor;
  const actionProposalsEnabled = !roleKnown || canDecide;
  const actionProposalsQuery = useActionProposals({
    statusFilter: "pending_approval",
    limit: 25,
    enabled: actionProposalsEnabled,
  });
  const [actions, setActions] = useState<PendingAction[]>([]);
  const [proposals, setProposals] = useState<TrainingProposal[]>([]);
  const [actionProposalBusy, setActionProposalBusy] = useState<Record<string, boolean>>({});
  const actionProposalBusyRef = useRef<Record<string, boolean>>({});
  const [rejectingActionProposalId, setRejectingActionProposalId] = useState<string | null>(null);
  const [actionRejectReason, setActionRejectReason] = useState("");
  // Self-directed STUDENT -> INTERN graduation queue: the evidence cards
  // for every STUDENT agent, so promotion is a one-visit review.
  const [selfDirectedQueue, setSelfDirectedQueue] = useState<SelfDirectedAgentProgress[]>([]);
  const [promotingAgentId, setPromotingAgentId] = useState<string | null>(null);
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
    if (roleKnown && !canDecide) return;
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
  }, [canDecide, headers, loadSessionCanvases, roleKnown]);

  const loadSelfDirected = useCallback(async () => {
    if (roleKnown && !canDecide) return;
    try {
      const res = await fetch(`${API}/api/maturity/training/self-directed`, { headers: headers() });
      if (res.ok) {
        const json = await res.json();
        setSelfDirectedQueue(Array.isArray(json.agents) ? json.agents : []);
      }
    } catch {
      // Non-critical: the HITL queue still works without this section.
    }
  }, [canDecide, headers, roleKnown]);

  const promoteFromQueue = async (agentId: string) => {
    setNotice(null);
    setError(null);
    setPromotingAgentId(agentId);
    try {
      // Raw fetch (page convention — matches decideProposal) so the call
      // carries the stored JWT via headers().
      const res = await fetch(
        `${API}/api/episodes/graduation/promote?agent_id=${agentId}&new_maturity=INTERN`,
        { method: "POST", headers: headers() }
      );
      await readGraduationPromotionResponse(res, agentId, "INTERN");
      setNotice("Agent promoted to INTERN.");
      await loadSelfDirected();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Promotion could not be confirmed. Refresh the agent status.');
    } finally {
      setPromotingAgentId(null);
    }
  };

  useEffect(() => {
    load();
    loadProposals();
    loadSelfDirected();
    const t = setInterval(() => { load(); loadProposals(); loadSelfDirected(); }, 15000); // auto-refresh; approvals can be time-sensitive
    return () => clearInterval(t);
  }, [load, loadProposals, loadSelfDirected]);

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

  const decideActionProposal = async (id: string, approve: boolean) => {
    if (actionProposalBusyRef.current[id]) return;
    actionProposalBusyRef.current[id] = true;
    setActionProposalBusy((current) => ({ ...current, [id]: true }));
    setNotice(null);
    setError(null);
    try {
      if (approve) {
        const result: ActionProposalApprovalResult =
          await actionProposalsQuery.approveMutation.mutateAsync({ proposalId: id });
        if (result.execution_result?.success === true) {
          setNotice("Proposal approved and executed.");
        } else {
          setError("Proposal approved, but execution failed.");
        }
      } else {
        const reason = actionRejectReason.trim();
        if (!reason) {
          setError("A rejection reason is required.");
          return;
        }
        await actionProposalsQuery.rejectMutation.mutateAsync({ proposalId: id, reason });
        setNotice("Proposal rejected.");
        setRejectingActionProposalId(null);
        setActionRejectReason("");
      }
    } catch (e) {
      setError(`Action proposal decision failed: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      delete actionProposalBusyRef.current[id];
      setActionProposalBusy((current) => {
        const next = { ...current };
        delete next[id];
        return next;
      });
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
        let message = `Decision failed (${res.status})`;
        try {
          const body = await res.json();
          const detail = body?.detail;
          if (detail && typeof detail === "object" && detail.message) {
            message = detail.message;
          }
        } catch {
          /* keep the status fallback */
        }
        setError(message);
        // A stale binding leaves the newer decision pending; refresh the
        // queue so the supervisor sees the current review rather than acting
        // on the old card again. load() clears error first, so restore the
        // targeted message after it completes.
        if (res.status === 409) {
          await load();
          setError(message);
        }
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
  // backend updates confidence; it may auto-promote only when readiness and
  // the capability-qualification gate (or an exact owner exception) allow it.
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
      setNotice(`Training session completed.${data?.promoted_to_intern ? " 🎓 Promotion granted!" : ""}`);
      loadProposals();
    } catch (e) {
      setError(`Session completion failed: ${String(e)}`);
    }
  };

  const pendingActionProposals: ActionProposal[] = actionProposalsQuery.pendingProposals ?? [];
  const actionProposalsLoading = actionProposalsEnabled && actionProposalsQuery.isPending;
  const actionProposalsError = actionProposalsEnabled && actionProposalsQuery.isError;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-6 lg:p-10">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-bold mb-1">Approvals</h1>
        <p className="text-sm text-gray-400 mb-6">
          Actions paused for human approval. Agents wait here until a decision is made.
        </p>

        <TrainingGuide />

        {roleKnown && !canDecide && (
          <div className="mb-4 p-3 rounded-lg bg-amber-900/30 border border-amber-700 text-sm text-amber-200">
            Reviewing approvals requires a supervisor role (team_lead or higher). You can see the
            queue below, but approve/reject is disabled — ask a team lead or admin to decide.
          </div>
        )}

        {error && <div role="alert" className="mb-4 p-3 rounded-lg bg-red-900/40 border border-red-700 text-sm">{error}</div>}
        {notice && <div role="status" aria-live="polite" className="mb-4 p-3 rounded-lg bg-emerald-900/40 border border-emerald-700 text-sm">{notice}</div>}

        {loading ? (
          <p className="text-gray-400">Loading…</p>
        ) : actions.length === 0 ? (
          <div className="rounded-xl border border-gray-800 p-10 text-center text-gray-500">
            Nothing waiting for approval. 🎉
          </div>
        ) : (
          <div className="space-y-3">
            {actions.map((a) => (
              <div
                key={a.id}
                data-testid={`approval-action-${a.id}`}
                className="rounded-xl border border-amber-800/60 bg-gray-900 p-4"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    {a.action_type === TASK_ADMISSION_ACTION ? (
                      <TaskAdmissionReview action={a} />
                    ) : (
                      <>
                        <div className="font-medium text-amber-300">
                          {a.action_type === "agent_qualification_review"
                            ? "Capability qualification review"
                            : a.action_type}
                          {a.agent_id && <span className="ml-2 text-xs text-gray-500">agent {String(a.agent_id).slice(0, 8)}</span>}
                        </div>
                        {a.reason && <div className="text-sm text-gray-400 mt-1">{a.reason}</div>}
                        {a.action_type === "agent_qualification_review" && (
                          <div className="mt-2 rounded border border-gray-700 p-2 text-xs space-y-1">
                            <p className="font-medium text-gray-300">Frozen rubric</p>
                            {((a.params?.rubric_criteria as Array<Record<string, unknown>> | undefined) || []).map((criterion) => (
                              <div key={String(criterion.id)} className="text-gray-400">
                                {String(criterion.id)}: {String(criterion.label)}
                              </div>
                            ))}
                            <p className="font-medium text-gray-300 pt-1">Scoped evidence</p>
                            {((a.params?.evidence as Array<Record<string, unknown>> | undefined) || []).map((item) => (
                              <div key={`${String(item.kind)}:${String(item.id)}`} className="text-gray-400">
                                <div>{String(item.kind)}:{String(item.id)}</div>
                                <div>Task: {String(item.task_preview || "")}</div>
                                <div>Output: {String(item.output_preview || "")}</div>
                              </div>
                            ))}
                          </div>
                        )}
                        <div className="text-xs text-gray-500 mt-1 font-mono break-all">{fmtParams(a.params)}</div>
                      </>
                    )}
                    <div className="text-xs text-gray-600 mt-1">
                      {a.created_at ? new Date(a.created_at).toLocaleString() : ""}
                    </div>
                  </div>
                  {editingAction === a.id && a.action_type !== TASK_ADMISSION_ACTION && (
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
                  <div className="flex gap-2 shrink-0" title={canDecide ? undefined : "Supervisor (team_lead+) role required"}>
                    {canDecide ? (
                    editingAction === a.id && a.action_type !== TASK_ADMISSION_ACTION ? (
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
                        {a.action_type !== TASK_ADMISSION_ACTION && (
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
                        )}
                        <button
                          onClick={() => decide(a.id, "approved")}
                          className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-medium"
                        >
                          {a.action_type === TASK_ADMISSION_ACTION ? "Approve this execution" : "Approve"}
                        </button>
                        <button
                          onClick={() => decide(a.id, "rejected")}
                          className="px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-sm font-medium"
                        >
                          Reject
                        </button>
                      </>
                    )
                    ) : (
                      <span className="text-xs text-gray-500 self-center">Read-only</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        <DecisionHistoryPanel />

        <div className="mt-10">
          <h2 className="text-lg font-semibold">Active Training Sessions</h2>
          <p className="text-sm text-gray-400 mb-4">
            Approved trainings in progress. Work with the agent (chat at /agents), then score the
            supervised pass here — completion records the pass evidence and updates the agent&apos;s
            confidence. Completion alone does not promote the agent: promotion requires the
            readiness requirements shown in the panel plus a passed capability qualification. An
            explicitly configured owner exception for that exact agent can waive the qualification
            review, not the readiness requirements. Otherwise the agent keeps its current tier and
            the panel shows what remains. An INTERN may then PROPOSE automated actions: those
            arrive in this same queue for your approval, and you keep coaching it over chat the
            same way.
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
                      <Link
                        href={`/chat?agent_id=${p.agent_id}`}
                        className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-medium"
                      >
                        Chat with student →
                      </Link>
                      <Link
                        href="/chat?agent_id=atom_main"
                        className="px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-medium"
                      >
                        Ask mentor (Atom) →
                      </Link>
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
                            <Link
                              href={`/chat?agent_id=${p.agent_id}`}
                              className="px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-xs font-medium"
                            >
                              Open training chat →
                            </Link>
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
          <h2 className="text-lg font-semibold">Self-Directed Graduation Queue (STUDENT → INTERN)</h2>
          <p className="text-sm text-gray-400 mb-4">
            STUDENT agents working toward graduation on real outcome-tracked work.
            Open the work, review the evidence, then promote when it holds up.
          </p>
          {selfDirectedQueue.length === 0 ? (
            <div className="rounded-xl border border-gray-800 p-6 text-center text-gray-500">
              No STUDENT agents awaiting graduation review.
            </div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {selfDirectedQueue.map((progress) => (
                <div key={progress.agent_id} className="rounded-xl border border-emerald-800/50 bg-gray-900 p-4">
                  <SelfDirectedPathwayCard
                    progress={progress}
                    compact
                    nextTierLabel="INTERN"
                    onPromote={canDecide ? () => promoteFromQueue(progress.agent_id) : undefined}
                    promoteBusy={promotingAgentId === progress.agent_id}
                  />
                </div>
              ))}
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
                    {canDecide ? (
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
                    ) : (
                      <span className="text-xs text-gray-500 shrink-0">Read-only</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-10">
          <h2 className="text-lg font-semibold">Agent Action Proposals (INTERN)</h2>
          <p className="text-sm text-gray-400 mb-4">
            Automated triggers — e.g. an ingested email classified for a domain — that an
            INTERN agent was not mature enough to run on its own. Approving <strong>executes
            the action now</strong> (the agent processes it and you can coach it afterwards);
            rejecting closes it and teaches the agent the correction.
          </p>
          <div aria-busy={actionProposalsLoading}>
            {actionProposalsLoading && (
              <p role="status" aria-live="polite" className="rounded-xl border border-gray-800 p-6 text-center text-gray-500">
                Loading agent action proposals…
              </p>
            )}
            {actionProposalsError && (
              <p role="alert" className="rounded-xl border border-red-800 p-6 text-center text-red-300">
                Could not load agent action proposals. Please retry.
              </p>
            )}
            {actionProposalsQuery.isSuccess && actionProposalsQuery.isAuthoritativeEmpty && (
              <div role="status" aria-live="polite" className="rounded-xl border border-gray-800 p-6 text-center text-gray-500">
                No agent action proposals waiting.
              </div>
            )}
            {actionProposalsQuery.isSuccess && pendingActionProposals.length > 0 && (
              <div className="space-y-3">
                {pendingActionProposals.map((p) => {
                  const preview = buildActionProposalPreview(p);
                  const busy = Boolean(actionProposalBusy[p.id]);
                  return (
                    <div key={p.id} aria-busy={busy} className="rounded-xl border border-violet-800/60 bg-gray-900 p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="font-medium text-violet-300">{p.title || "Untitled action proposal"}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            Target agent: {preview.targetAgent} · ID: {preview.targetAgentId} · action: {preview.actionType}
                          </div>
                          {p.description && <div className="text-sm text-gray-400 mt-1 whitespace-pre-line">{p.description}</div>}
                          <div className="mt-3 rounded-lg border border-gray-700 bg-gray-950/60 p-3 text-xs text-gray-300 space-y-2">
                            <div><span className="font-semibold text-gray-200">Prompt:</span> {preview.prompt}</div>
                            <div>
                              <div className="font-semibold text-gray-200">Parameters:</div>
                              <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-words">{preview.parameters}</pre>
                            </div>
                            <div>
                              <div className="font-semibold text-gray-200">Source content:</div>
                              <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap break-words">{preview.sourceContent}</pre>
                            </div>
                            <div>
                              <div className="font-semibold text-gray-200">Redacted payload:</div>
                              <pre data-testid="action-proposal-payload-preview" className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-words">{preview.payloadText}</pre>
                            </div>
                          </div>
                          {p.reasoning && (
                            <details className="text-xs text-gray-500 mt-1">
                              <summary className="cursor-pointer hover:text-gray-400">Why this was held</summary>
                              <div className="mt-1">{p.reasoning}</div>
                            </details>
                          )}
                          <div className="text-xs text-gray-600 mt-1">
                            {p.created_at ? new Date(p.created_at).toLocaleString() : ""}
                          </div>
                        </div>
                        {canDecide ? (
                          <div className="flex gap-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => decideActionProposal(p.id, true)}
                              disabled={busy}
                              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-sm font-medium disabled:opacity-50"
                            >
                              {busy ? "Running…" : "Approve & run"}
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setRejectingActionProposalId(p.id);
                                setActionRejectReason("");
                              }}
                              disabled={busy}
                              className="px-4 py-2 rounded-lg bg-red-700 hover:bg-red-600 text-sm font-medium disabled:opacity-50"
                            >
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-500 shrink-0">Read-only</span>
                        )}
                      </div>
                      {rejectingActionProposalId === p.id && (
                        <div className="mt-3 flex flex-wrap items-end gap-2">
                          <label className="flex-1 min-w-[220px] text-xs text-gray-400">
                            Rejection reason
                            <input
                              value={actionRejectReason}
                              onChange={(e) => setActionRejectReason(e.target.value)}
                              aria-label={`Rejection reason for ${p.title || p.id}`}
                              className="mt-1 w-full rounded-md border border-gray-700 bg-gray-800 px-2 py-1.5 text-sm text-gray-100"
                            />
                          </label>
                          <button
                            type="button"
                            onClick={() => decideActionProposal(p.id, false)}
                            disabled={busy || !actionRejectReason.trim()}
                            className="rounded-lg bg-red-700 px-3 py-2 text-xs font-medium text-white disabled:opacity-50"
                          >
                            Confirm rejection
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
