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

export type AgentJobWait = {
  id: string;
  kind?: string;
  status: string;
  question: string;
  missing_fact?: string | null;
  correlation_id: string;
  subject?: { label?: string | null } | null;
  can_answer?: boolean;
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
  result?: { status?: string; output?: string | null } | null;
};

type Props = {
  agentId?: string | null;
  jobId?: string | null;
  onForget?: () => void;
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

/**
 * Shows the current state of one admitted agent job: the exact open question
 * (an information request, never an effect approval), its blocking fact, and
 * the durable public result. Everything rendered here comes from an authorized
 * server read; cached job ids are locators only.
 */
export default function AgentJobWaitPanel({ agentId, jobId, onForget }: Props) {
  const [job, setJob] = useState<AgentJobReadback | null>(null);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
      // A new question (or a terminal state) invalidates any typed answer.
      setAnswer("");
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

    const stillCurrent = () => !cancelled && jobKeyRef.current === key;

    const stopPolling = () => {
      if (timer) {
        clearTimeout(timer);
        timer = null;
      }
    };

    const load = async () => {
      stopPolling();
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
        if (!stillCurrent()) return;
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
        if (!stillCurrent()) return;
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
        if (!stillCurrent() || err?.name === "AbortError") return;
        setError(
          "Could not reach the server. Refresh the job state; no answer was re-sent.",
        );
      } finally {
        if (stillCurrent()) setLoading(false);
      }
    };

    loadRef.current = load;
    load();

    return () => {
      cancelled = true;
      stopPolling();
      controller.abort();
      if (loadRef.current === load) loadRef.current = null;
    };
  }, [agentId, jobId, apply]);

  const refresh = useCallback(() => {
    setError(null);
    void loadRef.current?.();
  }, []);

  const submitAnswer = useCallback(async () => {
    const current = jobRef.current;
    const wait = current?.wait;
    const text = answer.trim();
    if (
      !agentId
      || !jobId
      || !wait
      || !wait.can_answer
      || !text
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
  }, [agentId, jobId, answer, submitting, apply]);

  if (!agentId || !jobId) return null;

  const openWait =
    job?.job_status === "waiting" && job.wait ? job.wait : null;
  const waitUnavailable =
    job?.job_status === "waiting" && !job.wait && Boolean(job.wait_unavailable);
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
    : statusLabel(job?.job_status);

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
          {openWait.can_answer ? (
            <div className="space-y-2">
              <Textarea
                aria-label="Answer the agent's question"
                data-testid="agent-job-answer-input"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type the missing fact…"
                className="min-h-[80px]"
              />
              <Button
                data-testid="agent-job-answer-submit"
                onClick={submitAnswer}
                disabled={submitting || !answer.trim()}
              >
                {submitting ? "Sending…" : "Send answer"}
              </Button>
            </div>
          ) : (
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
