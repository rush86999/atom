import React, { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getApiBase } from "@/lib/api-base";
import { getAuthToken } from "@/lib/identity";
import { handleSessionExpired } from "@/lib/auth-headers";

const API_BASE = getApiBase();
const POLL_MS = 2500;
const MAX_POLLS = 40;
// A long admitted run can still be active when the bounded poll window is
// spent (40 x 2.5s observed exhausting before the final lifecycle event).
// Only the durable outcome frame can prompt an extra read: it names the exact
// job and carries a non-active job_status. Generic chat/progress frames are
// ignored. Reads are coalesced, never lifetime-capped — the same job may ask
// several facts over its life.
const EVENT_REFRESH_COALESCE_MS = 1000;
const DURABLE_NON_ACTIVE_JOB_STATUSES = new Set([
  "waiting",
  "awaiting_information",
  "awaiting_input",
  "awaiting_approval",
  "success",
  "failed",
  "cancelled",
  "canceled",
]);

export type AgentJobWait = {
  id: string;
  kind?: string;
  status: string;
  question: string;
  missing_fact?: string | null;
  correlation_id: string;
  subject?: { label?: string | null } | null;
  can_answer?: boolean;
  // Server-projected owner-set absolute deadline and wait age. A read is pure:
  // these fields never cause the client to expire or dispatch anything.
  deadline?: string | null;
  waiting_since?: string | null;
  waiting_age_seconds?: number | null;
  deadline_passed?: boolean;
};

export type AuthorizedAnswerSource = {
  document_id?: string | null;
  dataset_name?: string | null;
  sheet?: string | null;
  source?: string | null;
  external_id?: string | null;
  source_version?: string | null;
  kind?: string | null;
  file_name?: string | null;
};

export type AgentJobReadback = {
  agent_id: string;
  job_id: string;
  execution_id?: string | null;
  job_status: string;
  outcome?: string | null;
  reason?: string | null;
  next_action?: string | null;
  requires_reconciliation?: boolean;
  wait?: AgentJobWait | null;
  wait_unavailable?: boolean;
  deadline?: string | null;
  waiting_since?: string | null;
  waiting_age_seconds?: number | null;
  deadline_passed?: boolean;
  result?: { status?: string; output?: string | null } | null;
};

type Props = {
  agentId?: string | null;
  jobId?: string | null;
  onForget?: () => void;
  /**
   * Optional message registrar from the page's existing WebSocket hook.
   * The page already subscribes to the workspace channel, so reusing its
   * listener avoids opening a second socket. Only the durable outcome frame
   * (exact job_id + agent_id + non-active job_status) triggers the same
   * authorized GET used by polling/Refresh — it never claims, advances or
   * re-sends anything. Generic chat/progress frames are ignored.
   */
  onMessage?: (handler: (message: any) => void) => () => void;
};

const statusLabel = (status?: string | null): string => {
  switch (status) {
    case "waiting":
      return "Waiting for your answer";
    case "pending":
    case "running":
      return "Working";
    case "success":
      return "Completed";
    case "failed":
      return "Not completed";
    case "cancelled":
    case "canceled":
      return "Cancelled";
    default:
      return "Unknown";
  }
};

const failureMessage = (job: AgentJobReadback): string => {
  if (job.job_status === "cancelled" || job.job_status === "canceled") {
    return "This job was cancelled. No further work was started.";
  }
  if (
    job.reason === "wait_deadline_exceeded" ||
    job.outcome === "expired" ||
    job.deadline_passed
  ) {
    return "The owner-set deadline passed before the information arrived. No further work was started; review the deadline or start a new authorized run.";
  }
  if (job.requires_reconciliation || job.reason === "execution_uncertain") {
    return "The outcome is uncertain. Reconcile the original operation before retrying; the answer was not re-sent.";
  }
  if (job.reason === "execution_waiting_unbacked") {
    return "The agent reported waiting, but the question could not be verified. Refresh or review the job.";
  }
  if (job.reason === "execution_blocked") {
    return "The job is blocked by a missing prerequisite. Resolve it before retrying.";
  }
  if (job.job_status === "failed") {
    return "The job did not complete. Refresh the job state before retrying.";
  }
  return "The job is not complete. Refresh the job state before retrying.";
};

function errorMessage(body: any, fallback: string): string {
  const detail = body?.error?.message || body?.detail || body?.message;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (detail && typeof detail === "object" && typeof detail.message === "string") {
    return detail.message;
  }
  return fallback;
}

const formatWaitAge = (seconds?: number | null): string | null => {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return null;
  }
  const total = Math.max(0, Math.floor(seconds));
  if (total < 60) return `${total}s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours}h ${minutes % 60}m`;
  return `${Math.floor(hours / 24)}d ${hours % 24}h`;
};

const formatDeadline = (value?: string | null): string | null => {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);
  return parsed.toLocaleString();
};

/**
 * Shows the current state of one admitted agent job: the exact open question
 * (an information request, never an effect approval), its blocking fact, and
 * the durable public result. Everything rendered here comes from an authorized
 * server read; cached job ids are locators only.
 */
export default function AgentJobWaitPanel({ agentId, jobId, onForget, onMessage }: Props) {
  const [job, setJob] = useState<AgentJobReadback | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sourcePickerOpen, setSourcePickerOpen] = useState(false);
  const [sources, setSources] = useState<AuthorizedAnswerSource[]>([]);
  const [sourceKey, setSourceKey] = useState("");
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState<string | null>(null);

  const jobKeyRef = useRef("");
  const waitIdentityRef = useRef<string | null>(null);
  const jobRef = useRef<AgentJobReadback | null>(null);
  const loadRef = useRef<(() => Promise<void>) | null>(null);
  const applyRef = useRef<((next: AgentJobReadback | null) => void) | null>(null);
  const submittingRef = useRef(false);
  const onForgetRef = useRef(onForget);
  useEffect(() => {
    onForgetRef.current = onForget;
  }, [onForget]);

  const apply = useCallback((next: AgentJobReadback | null) => {
    const nextWaitId = next?.wait?.id || null;
    if (waitIdentityRef.current !== nextWaitId) {
      // A new question (or a terminal state) invalidates any typed answer and
      // any selected source; the next question needs its own explicit input.
      setAnswer("");
      setSourceKey("");
      setSourcePickerOpen(false);
      setSourceError(null);
    }
    waitIdentityRef.current = nextWaitId;
    jobRef.current = next;
    setJob(next);
  }, []);
  applyRef.current = apply;

  useEffect(() => {
    const key = `${agentId || ""}:${jobId || ""}`;
    jobKeyRef.current = key;
    waitIdentityRef.current = null;
    jobRef.current = null;
    setJob(null);
    setAnswer("");
    setError(null);
    setNotice(null);
    setSubmitting(false);
    submittingRef.current = false;
    setLoading(Boolean(agentId && jobId));
    if (!agentId || !jobId) {
      loadRef.current = null;
      return;
    }

    const controller = new AbortController();
    let cancelled = false;
    let polls = 0;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let loadSeq = 0;
    let lastEventRefreshAt = 0;
    let eventTimer: ReturnType<typeof setTimeout> | null = null;

    const stillCurrent = () => !cancelled && jobKeyRef.current === key;
    // Only the newest read may apply. A status event can land while a poll
    // request is in flight; without this ordering guard the older (stale)
    // response could arrive last and overwrite the fresh state.
    const current = (seq: number) =>
      stillCurrent() && seq === loadSeq;

    const stopPolling = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const stopEventRefresh = () => {
      if (eventTimer) {
        clearTimeout(eventTimer);
        eventTimer = null;
      }
    };

    const load = async () => {
      stopPolling();
      const seq = ++loadSeq;
      try {
        const res = await fetch(
          `${API_BASE}/api/agents/${encodeURIComponent(agentId)}/jobs/${encodeURIComponent(jobId)}`,
          {
            headers: {
              Authorization: `Bearer ${getAuthToken() || ""}`,
              "Content-Type": "application/json",
            },
            signal: controller.signal,
          },
        );
        if (!current(seq)) return;
        if (res.status === 401) {
          handleSessionExpired();
          return;
        }
        if (res.status === 403 || res.status === 404) {
          apply(null);
          setError("This job is not available to the signed-in user.");
          onForgetRef.current?.();
          return;
        }
        if (!res.ok) {
          setError("Could not read the job state. Refresh to try again.");
          return;
        }
        const body = await res.json();
        if (!current(seq)) return;
        const next = (body?.data ?? body) as AgentJobReadback;
        if (!next || typeof next !== "object" || !next.job_status) {
          setError("The server returned no usable job state. Refresh to try again.");
          return;
        }
        apply(next);
        setError(null);
        const active = next.job_status === "pending" || next.job_status === "running";
        if (active && !next.wait && polls < MAX_POLLS) {
          polls += 1;
          timer = setTimeout(load, POLL_MS);
        }
      } catch (err: any) {
        if (!current(seq) || err?.name === "AbortError") return;
        setError(
          "Could not reach the server. Refresh the job state; no answer was re-sent.",
        );
      } finally {
        if (current(seq)) setLoading(false);
      }
    };

    // Only the durable outcome emitter identifies the exact job this panel
    // owns: it carries the authoritative job_id, agent_id and a non-active
    // job_status. Generic chat/progress frames (agent + execution/status
    // only) can arrive many times per run and must never consume a read.
    // A frame that does not prove the exact job is ignored.
    const isSameDurableJobEvent = (message: any): boolean => {
      if (!message || message.type !== "agent_status_change") return false;
      const payload =
        message.data && typeof message.data === "object" ? message.data : message;
      const eventJob = payload.job_id ?? message.job_id;
      const eventAgent = payload.agent_id ?? message.agent_id;
      const jobStatus = payload.job_status ?? message.job_status;
      if (!eventJob || String(eventJob) !== String(jobId)) return false;
      if (!agentId || !eventAgent || String(eventAgent) !== String(agentId)) {
        return false;
      }
      return (
        typeof jobStatus === "string" &&
        DURABLE_NON_ACTIVE_JOB_STATUSES.has(jobStatus)
      );
    };

    const runEventRefresh = () => {
      if (!stillCurrent()) return;
      lastEventRefreshAt = Date.now();
      void load();
    };

    const onStatusEvent = (message: any) => {
      if (!stillCurrent() || !isSameDurableJobEvent(message)) return;
      const since = Date.now() - lastEventRefreshAt;
      if (since >= EVENT_REFRESH_COALESCE_MS) {
        runEventRefresh();
        return;
      }
      // Coalesce repeated durable frames into one trailing read instead of
      // one GET per frame. There is no lifetime cap: a later wait (same job,
      // another fact) must still be delivered. Cleanup/job change cancels
      // this timer.
      if (eventTimer) return;
      eventTimer = setTimeout(() => {
        eventTimer = null;
        runEventRefresh();
      }, EVENT_REFRESH_COALESCE_MS - since);
    };

    loadRef.current = load;
    const unsubscribe = onMessage?.(onStatusEvent);
    load();

    return () => {
      cancelled = true;
      stopPolling();
      stopEventRefresh();
      unsubscribe?.();
      controller.abort();
      if (loadRef.current === load) loadRef.current = null;
    };
  }, [agentId, jobId, apply, onMessage]);

  const refresh = useCallback(() => {
    setError(null);
    void loadRef.current?.();
  }, []);

  const selectedSource = sources.find(
    (item, index) => String(index) === sourceKey,
  ) || null;

  const sourceLabel = (item: AuthorizedAnswerSource): string => {
    const name = String(item.file_name || item.dataset_name || item.document_id || "authorized source");
    const sheet = item.sheet ? ` / ${item.sheet}` : "";
    const version = item.source_version ? ` · ${String(item.source_version).slice(0, 12)}` : "";
    return `${name}${sheet}${version}`;
  };

  const loadSources = useCallback(async () => {
    if (sourceLoading) return;
    setSourceLoading(true);
    setSourceError(null);
    const key = jobKeyRef.current;
    try {
      const res = await fetch(
        `${API_BASE}/api/assignments/sources?limit=50`,
        {
          headers: {
            Authorization: `Bearer ${getAuthToken() || ""}`,
            "Content-Type": "application/json",
          },
        },
      );
      if (jobKeyRef.current !== key) return;
      if (res.status === 401) {
        handleSessionExpired();
        return;
      }
      if (!res.ok) {
        setSourceError("Authorized sources could not be loaded. Refresh and try again.");
        return;
      }
      const body = await res.json();
      const rows = Array.isArray(body?.data) ? body.data : (Array.isArray(body) ? body : []);
      if (jobKeyRef.current !== key) return;
      setSources(rows as AuthorizedAnswerSource[]);
      if (!rows.length) {
        setSourceError("No authorized documents or datasets are available for this job.");
      }
    } catch {
      if (jobKeyRef.current === key) {
        setSourceError("Authorized sources could not be loaded. Refresh and try again.");
      }
    } finally {
      if (jobKeyRef.current === key) setSourceLoading(false);
    }
  }, [sourceLoading]);

  const toggleSourcePicker = useCallback(() => {
    setSourcePickerOpen((open) => {
      const next = !open;
      if (next && !sources.length) void loadSources();
      return next;
    });
  }, [loadSources, sources.length]);

  const submitAnswer = useCallback(async () => {
    const current = jobRef.current;
    const wait = current?.wait;
    const text = answer.trim();
    const source = selectedSource;
    if (
      !agentId
      || !jobId
      || !wait
      || !wait.can_answer
      || (!text && !source)
      || submitting
      || submittingRef.current
    ) {
      return;
    }
    const key = jobKeyRef.current;
    submittingRef.current = true;
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/agents/${encodeURIComponent(agentId)}/jobs/${encodeURIComponent(jobId)}/answer`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${getAuthToken() || ""}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            answer: text,
            correlation_id: wait.correlation_id,
            ...(source
              ? {
                  source: Object.fromEntries(
                    Object.entries({
                      document_id: source.document_id,
                      dataset_name: source.dataset_name,
                      sheet: source.sheet,
                      source: source.source,
                      external_id: source.external_id,
                      source_version: source.source_version,
                      kind: source.kind,
                    }).filter(([, value]) => value !== null && value !== undefined && value !== ""),
                  ),
                }
              : {}),
          }),
        },
      );
      if (jobKeyRef.current !== key) return;
      if (res.status === 401) {
        handleSessionExpired();
        return;
      }
      let body: any = null;
      try {
        body = await res.json();
      } catch {
        body = null;
      }
      if (jobKeyRef.current !== key) return;

      if (res.ok) {
        const next = (body?.data ?? null) as AgentJobReadback | null;
        if (next && next.job_status) {
          // The server already returned an authoritative continuation state.
          apply(next);
        }
        setSourceKey("");
        setNotice(
          next?.wait
            ? "Answer accepted. The agent needs one more fact for the same job."
            : "Answer accepted. The same job is continuing.",
        );
        // Re-read so the panel shows the durable server state, not the POST
        // envelope or any cached text.
        await loadRef.current?.();
      } else if (res.status === 409) {
        // A stale answer is a normal race, not a raw server detail. Always
        // give the same actionable copy, then re-read authoritative state.
        await loadRef.current?.();
        if (jobKeyRef.current === key) {
          setError(
            "This question is no longer current. The job state was refreshed; read the new state before answering.",
          );
        }
      } else if (res.status === 503) {
        const message = errorMessage(
          body,
          "The outcome is uncertain. Refresh the job state; do not resend the answer blindly.",
        );
        await loadRef.current?.();
        if (jobKeyRef.current === key) setError(message);
      } else if (res.status === 403 || res.status === 404) {
        setError("This job is not available to the signed-in user.");
        apply(null);
        onForgetRef.current?.();
      } else {
        const message = errorMessage(
          body,
          "The answer was not accepted. Refresh the job state before retrying.",
        );
        await loadRef.current?.();
        if (jobKeyRef.current === key) setError(message);
      }
    } catch {
      // Deliberately no automatic resend: the effect may be ambiguous.
      await loadRef.current?.();
      if (jobKeyRef.current === key) {
        setError(
          "The answer outcome is uncertain. Refresh the job state; no automatic resend was made.",
        );
      }
    } finally {
      submittingRef.current = false;
      if (jobKeyRef.current === key) setSubmitting(false);
    }
  }, [agentId, jobId, answer, selectedSource, submitting, apply]);

  if (!agentId || !jobId) return null;

  const openWait =
    job?.job_status === "waiting" && job.wait ? job.wait : null;
  const waitUnavailable =
    job?.job_status === "waiting" && !job.wait && Boolean(job.wait_unavailable);
  const deadlinePassed = Boolean(
    job?.deadline_passed || openWait?.deadline_passed,
  );
  const completed = job?.job_status === "success";
  const active = job?.job_status === "pending" || job?.job_status === "running";
  const failed =
    Boolean(job) &&
    !completed &&
    !active &&
    !openWait &&
    !waitUnavailable &&
    !["waiting", "pending", "running"].includes(job?.job_status || "");
  const statusText = waitUnavailable
    ? "Waiting · question unavailable"
    : deadlinePassed && job?.job_status === "waiting"
      ? "Deadline passed"
      : statusLabel(job?.job_status);
  const waitAge = formatWaitAge(
    openWait?.waiting_age_seconds ?? job?.waiting_age_seconds,
  );
  const deadlineLabel = formatDeadline(
    openWait?.deadline ?? job?.deadline,
  );

  return (
    <section
      data-testid="agent-job-wait-panel"
      aria-live="polite"
      className="bg-white dark:bg-gray-800 p-4 rounded-lg border shadow-sm space-y-3"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-gray-100">
            Agent job
          </h3>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Same task · {String(jobId).slice(0, 8)}
          </p>
        </div>
        <Badge data-testid="agent-job-status" variant="outline">
          {statusText}
        </Badge>
      </div>

      {loading && !job && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Loading job state…
        </p>
      )}

      {error && (
        <div
          role="alert"
          data-testid="agent-job-error"
          className="p-3 text-sm bg-red-50 text-red-700 rounded border border-red-200"
        >
          {error}
        </div>
      )}

      {notice && (
        <p
          data-testid="agent-job-notice"
          className="text-sm text-green-700 bg-green-50 rounded p-2"
        >
          {notice}
        </p>
      )}

      {active && (
        <p className="text-sm text-gray-600 dark:text-gray-300">
          The agent is working on this job. This panel refreshes the job state
          without running the model.
        </p>
      )}

      {waitUnavailable && (
        <p
          data-testid="agent-job-wait-unavailable"
          className="text-sm text-amber-700 bg-amber-50 p-3 rounded border border-amber-200"
        >
          The job says it is waiting, but its question could not be verified.
          Refresh or review the job before answering.
        </p>
      )}

      {openWait && (
        <div className="space-y-3">
          <p className="text-sm text-gray-700 dark:text-gray-300">
            The agent needs one fact before the same job can continue.
          </p>
          {openWait.subject?.label && (
            <p className="text-sm text-gray-600 dark:text-gray-400">
              For: {openWait.subject.label}
            </p>
          )}
          {openWait.missing_fact && (
            <p
              data-testid="agent-job-blocking"
              className="text-sm font-medium text-amber-700"
            >
              Waiting for: {openWait.missing_fact}
            </p>
          )}
          <p
            data-testid="agent-job-question"
            className="p-3 rounded border bg-gray-50 dark:bg-gray-900/40 text-gray-900 dark:text-gray-100"
          >
            {openWait.question}
          </p>
          {(waitAge || deadlineLabel) && (
            <p
              data-testid="agent-job-wait-timing"
              className="text-xs text-gray-600 dark:text-gray-400"
            >
              {waitAge ? `Waiting for ${waitAge}` : "Waiting"}
              {deadlineLabel ? ` · Deadline: ${deadlineLabel}` : ""}
            </p>
          )}
          {deadlinePassed && (
            <p
              data-testid="agent-job-wait-expired"
              className="text-sm text-amber-700 bg-amber-50 p-3 rounded border border-amber-200"
            >
              The owner-set deadline passed before the information arrived.
              This wait can no longer be answered; review the deadline or start
              a new authorized run.
            </p>
          )}
          {openWait.can_answer && !deadlinePassed ? (
            <div className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                data-testid="agent-job-source-open"
                onClick={toggleSourcePicker}
                disabled={submitting || sourceLoading}
              >
                {sourcePickerOpen ? "Hide authorized sources" : "Attach an authorized source"}
              </Button>
              {sourcePickerOpen && (
                <div className="space-y-1">
                  {sourceLoading && (
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Loading authorized sources…
                    </p>
                  )}
                  {sourceError && (
                    <p
                      data-testid="agent-job-source-error"
                      className="text-xs text-amber-700"
                    >
                      {sourceError}
                    </p>
                  )}
                  <select
                    aria-label="Select an authorized source"
                    data-testid="agent-job-source-select"
                    className="w-full rounded border p-2 text-sm bg-white dark:bg-gray-900"
                    value={sourceKey}
                    onChange={(e) => setSourceKey(e.target.value)}
                  >
                    <option value="">Use a text answer only</option>
                    {sources.map((item, index) => (
                      <option key={`${item.document_id || item.dataset_name || index}`} value={String(index)}>
                        {sourceLabel(item)}
                      </option>
                    ))}
                  </select>
                  {selectedSource && (
                    <p className="text-xs text-gray-600 dark:text-gray-400">
                      The selected source will be bound to this exact question;
                      uploading a file elsewhere does not answer it.
                    </p>
                  )}
                </div>
              )}
              <Textarea
                aria-label="Answer the agent's question"
                data-testid="agent-job-answer-input"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder={selectedSource ? "Optional note or label for this source…" : "Type the missing fact…"}
                className="min-h-[80px]"
              />
              <Button
                data-testid="agent-job-answer-submit"
                onClick={submitAnswer}
                disabled={submitting || (!answer.trim() && !selectedSource)}
              >
                {submitting ? "Sending…" : "Send answer"}
              </Button>
            </div>
          ) : deadlinePassed ? null : (
            <p
              data-testid="agent-job-wait-closed"
              className="text-sm text-amber-700"
            >
              This question is no longer open. Refresh the job state before
              answering.
            </p>
          )}
          <p className="text-xs text-gray-500 dark:text-gray-400">
            This is information for the same task, not approval of an action.
            Action approvals remain on the Approvals page.
          </p>
        </div>
      )}

      {completed && (
        <div className="space-y-2">
          <p
            data-testid="agent-job-completed"
            className="text-sm font-medium text-green-700"
          >
            Completed
          </p>
          {job?.result?.output && (
            <pre
              data-testid="agent-job-result"
              className="whitespace-pre-wrap text-sm text-gray-800 dark:text-gray-200 bg-gray-50 dark:bg-gray-900/40 p-3 rounded border"
            >
              {job.result.output}
            </pre>
          )}
        </div>
      )}

      {failed && (
        <p
          data-testid="agent-job-failure"
          className="text-sm text-red-700 bg-red-50 p-3 rounded border border-red-200"
        >
          {failureMessage(job as AgentJobReadback)}
        </p>
      )}

      <div>
        <Button
          variant="outline"
          size="sm"
          data-testid="agent-job-refresh"
          onClick={refresh}
          disabled={submitting}
        >
          Refresh job state
        </Button>
      </div>
    </section>
  );
}
