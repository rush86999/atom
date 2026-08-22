import React, { useCallback, useEffect, useState } from 'react';
import {
  approveActionProposal,
  approveTrainingProposal,
  completeTrainingSession,
  listActionProposals,
  listTrainingProposals,
  rejectActionProposal,
  rejectTrainingProposal,
  TrainingCompletionResult,
} from '../../lib/maturity-api';

interface TrainingProposalRow {
  id: string;
  title: string | null;
  agent_name: string | null;
  status: string | null;
  capability_gaps?: string[];
}

interface ActionProposalRow {
  id: string;
  title: string | null;
  agent_name: string | null;
  status: string | null;
  reasoning?: string | null;
}

const PENDING = 'pending_approval';

/**
 * Supervisor approval panel for the agent maturity journey:
 * - STUDENT training proposals -> approve -> mark completed (confidence boost,
 *   possible STUDENT->INTERN promotion)
 * - INTERN action proposals -> approve (executes) / reject
 *
 * Self-fetching; calls `onChanged` after any successful mutation so parent
 * views can refresh agent maturity data.
 */
export function MaturityApprovalPanel({
  className,
  onChanged,
}: {
  className?: string;
  onChanged?: () => void;
}) {
  const [training, setTraining] = useState<TrainingProposalRow[]>([]);
  const [actions, setActions] = useState<ActionProposalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [completingId, setCompletingId] = useState<string | null>(null);
  const [performanceScore, setPerformanceScore] = useState('0.9');
  const [feedback, setFeedback] = useState('Completed via supervisor panel');
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [t, a] = await Promise.all([
        listTrainingProposals(),
        listActionProposals(),
      ]);
      setTraining(t as TrainingProposalRow[]);
      setActions(a as ActionProposalRow[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const run = useCallback(
    async (id: string, fn: () => Promise<string | void>, okMsg: string) => {
      setBusyId(id);
      setError(null);
      try {
        const override = await fn();
        setNotice(typeof override === 'string' ? override : okMsg);
        await refresh();
        onChanged?.();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusyId(null);
        setRejectingId(null);
        setRejectReason('');
      }
    },
    [refresh, onChanged]
  );

  const handleApproveTraining = (p: TrainingProposalRow) =>
    run(
      `train-${p.id}`,
      async () => {
        const { session_id } = await approveTrainingProposal(p.id);
        // Remember the session so "Mark completed" can target it.
        setCompletingId(session_id);
      },
      'Training approved'
    );

  const handleComplete = () =>
    run(
      `complete-${completingId}`,
      async () => {
        const result: TrainingCompletionResult =
          await completeTrainingSession(completingId as string, {
            performance_score: Number(performanceScore) || 0.9,
            supervisor_feedback: feedback || 'Completed via supervisor panel',
            errors_count: 0,
            tasks_completed: 10,
            total_tasks: 10,
          });
        setCompletingId(null);
        return result.promoted_to_intern
          ? 'Session completed — agent promoted to INTERN'
          : 'Training session completed';
      },
      'Training completed'
    );

  const pendingFirst = <T extends { status: string | null }>(rows: T[]) =>
    [...rows].sort((a, b) =>
      a.status === PENDING ? -1 : b.status === PENDING ? 1 : 0
    );

  return (
    <section
      data-testid="maturity-approval-panel"
      className={className}
      aria-label="Agent maturity approvals"
    >
      <h3 className="text-sm font-semibold mb-2">Maturity approvals</h3>

      {loading && <p className="text-xs text-gray-500">Loading proposals…</p>}
      {error && (
        <p role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-xs text-green-700">
          {notice}
        </p>
      )}

      {/* Completing a just-approved training session */}
      {completingId && (
        <div
          data-testid="complete-training-form"
          className="border rounded p-2 my-2 text-xs space-y-2"
        >
          <p className="font-medium">Complete training session</p>
          <label className="block">
            Performance score (0–1)
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={performanceScore}
              onChange={(e) => setPerformanceScore(e.target.value)}
              aria-label="Performance score"
              className="border rounded px-1 py-0.5 w-full"
            />
          </label>
          <label className="block">
            Feedback
            <input
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              aria-label="Supervisor feedback"
              className="border rounded px-1 py-0.5 w-full"
            />
          </label>
          <button
            onClick={handleComplete}
            disabled={busyId !== null}
            className="px-2 py-1 rounded bg-green-600 text-white disabled:opacity-50"
          >
            {busyId?.startsWith('complete') ? 'Saving…' : 'Mark completed'}
          </button>
        </div>
      )}

      {/* STUDENT training proposals */}
      <h4 className="text-xs font-semibold mt-3 mb-1 text-gray-600">
        Training proposals
      </h4>
      {!loading && pendingFirst(training).length === 0 && (
        <p className="text-xs text-gray-400">No training proposals.</p>
      )}
      <ul className="space-y-1">
        {pendingFirst(training).map((p) => (
          <li key={p.id} className="border rounded px-2 py-1 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate" title={p.title ?? p.id}>
                {p.title ?? p.id}
                {p.agent_name ? ` — ${p.agent_name}` : ''}
              </span>
              <span
                className={`px-1 rounded ${
                  p.status === PENDING
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {p.status ?? 'unknown'}
              </span>
            </div>
            {Array.isArray(p.capability_gaps) &&
              p.capability_gaps.length > 0 && (
                <div className="text-gray-500">
                  Gaps: {p.capability_gaps.join(', ')}
                </div>
              )}
            {p.status === PENDING && (
              <div className="mt-1 flex gap-1">
                <button
                  onClick={() => handleApproveTraining(p)}
                  disabled={busyId !== null}
                  className="px-2 py-0.5 rounded bg-blue-600 text-white disabled:opacity-50"
                >
                  {busyId === `train-${p.id}` ? '…' : 'Approve'}
                </button>
                <button
                  onClick={() => {
                    setRejectingId(p.id);
                    setRejectReason('');
                  }}
                  disabled={busyId !== null}
                  className="px-2 py-0.5 rounded border disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            )}
            {rejectingId === p.id && (
              <div className="mt-1 flex gap-1">
                <input
                  placeholder="Reason"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  aria-label="Rejection reason"
                  className="border rounded px-1 py-0.5 flex-1"
                />
                <button
                  onClick={() =>
                    run(
                      `train-rej-${p.id}`,
                      async () => rejectTrainingProposal(p.id, rejectReason),
                      'Training rejected'
                    )
                  }
                  disabled={!rejectReason.trim() || busyId !== null}
                  className="px-2 py-0.5 rounded bg-red-600 text-white disabled:opacity-50"
                >
                  Confirm
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>

      {/* INTERN action proposals */}
      <h4 className="text-xs font-semibold mt-3 mb-1 text-gray-600">
        Action proposals
      </h4>
      {!loading && pendingFirst(actions).length === 0 && (
        <p className="text-xs text-gray-400">No action proposals.</p>
      )}
      <ul className="space-y-1">
        {pendingFirst(actions).map((p) => (
          <li key={p.id} className="border rounded px-2 py-1 text-xs">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate" title={p.title ?? p.id}>
                {p.title ?? p.id}
                {p.agent_name ? ` — ${p.agent_name}` : ''}
              </span>
              <span
                className={`px-1 rounded ${
                  p.status === PENDING
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {p.status ?? 'unknown'}
              </span>
            </div>
            {p.status === PENDING && (
              <div className="mt-1 flex gap-1">
                <button
                  onClick={() =>
                    run(
                      `act-${p.id}`,
                      async () => {
                        await approveActionProposal(p.id);
                      },
                      'Proposal approved and executed'
                    )
                  }
                  disabled={busyId !== null}
                  className="px-2 py-0.5 rounded bg-blue-600 text-white disabled:opacity-50"
                >
                  {busyId === `act-${p.id}` ? 'Executing…' : 'Approve & execute'}
                </button>
                <button
                  onClick={() => {
                    setRejectingId(p.id);
                    setRejectReason('');
                  }}
                  disabled={busyId !== null}
                  className="px-2 py-0.5 rounded border disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            )}
            {rejectingId === p.id && (
              <div className="mt-1 flex gap-1">
                <input
                  placeholder="Reason"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  aria-label="Rejection reason"
                  className="border rounded px-1 py-0.5 flex-1"
                />
                <button
                  onClick={() =>
                    run(
                      `act-rej-${p.id}`,
                      async () => rejectActionProposal(p.id, rejectReason),
                      'Proposal rejected'
                    )
                  }
                  disabled={!rejectReason.trim() || busyId !== null}
                  className="px-2 py-0.5 rounded bg-red-600 text-white disabled:opacity-50"
                >
                  Confirm
                </button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}

export default MaturityApprovalPanel;
