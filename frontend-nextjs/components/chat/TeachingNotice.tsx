"use client";

/**
 * Inline "train the agent from chat" card.
 *
 * The chat path had no teaching channel: /teach was reachable only from the
 * canvas Training tab's form. Now a user can teach the agent while working —
 * `/teach <rule>` in either the canvas co-editor chat or regular chat, or a
 * clear directive ("always …", "from now on …") that the backend DETECTS.
 *
 * Detected cues are never saved on their own (lessons are permanent prompt
 * instructions — see docs/canvas/agent-learning.md, poisoning rule). This card
 * is the human gate: it shows the exact rule and asks for one click. An
 * explicit /teach command arrives already saved and renders as a confirmation.
 *
 * Shared by both chat surfaces (`GlobalChat/ChatMessage` and the canvas
 * side-chat in `pages/canvas/[id].tsx`) so they can never drift.
 */
import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { deleteTeachingPoint, teachAgent } from '@/lib/maturity-api';
import { useUserRole } from '@/lib/user-role';

export interface TeachingAgentBrief {
  id: string;
  name?: string | null;
  status?: string | null;
  category?: string | null;
  confidence?: number | null;
}

export interface TeachingNoticeData {
  status: 'saved' | 'duplicate' | 'suggested' | 'needs_agent' | 'empty' | 'error';
  lesson: string;
  message: string;
  /** The agent the lesson was / would be saved to. */
  agent?: TeachingAgentBrief | null;
  /** Choices when the chat has no attached agent (status `needs_agent`). */
  agents?: TeachingAgentBrief[];
  /** `student` (confidence circuit) | `standing_guidance` (any tier). */
  mode?: string | null;
  teaching_point_id?: string | null;
  canvas_id?: string | null;
  /** Lesson scope: 'global' applies to all of the agent's work, 'goal' only
   * while working `goal_id`. Absent reads as global. */
  scope?: 'global' | 'goal';
  goal_id?: string | null;
  goal_title?: string | null;
  /** True when the goal scope came from INFERENCE (not from an explicit
   * context) — the card says so, and offers the one-click widen. */
  goal_inferred?: boolean;
}

interface TeachingNoticeProps {
  notice: TeachingNoticeData;
  /** Called after an inline save so the parent can refresh its state. */
  onTaught?: (notice: TeachingNoticeData) => void;
  className?: string;
}

function _tierLabel(agent?: TeachingAgentBrief | null): string {
  const status = (agent?.status || '').toString();
  return status ? status.toUpperCase() : '';
}

export function TeachingNotice({ notice, onTaught, className }: TeachingNoticeProps) {
  const [current, setCurrent] = useState<TeachingNoticeData>(notice);
  const [busyId, setBusyId] = useState<string | null>(null);
  // Undo is a training-state mutation: the backend gates removal at
  // TEAM_LEAD+ (`_require_supervisor`), so only supervisors are offered the
  // control — everyone else would just collect a 403.
  const { isSupervisor } = useUserRole();
  const [undoing, setUndoing] = useState(false);
  const [undone, setUndone] = useState(false);
  const [undoError, setUndoError] = useState<string | null>(null);
  // A lesson scoped to a goal can always be WIDENED to all of the agent's
  // work (the backend allows that direction; it only blocks narrowing).
  const [widening, setWidening] = useState(false);

  const widenToAllWork = async () => {
    const agentId = current.agent?.id;
    if (!agentId) return;
    setWidening(true);
    setUndoError(null);
    try {
      const res = await teachAgent(agentId, current.lesson);
      if (res && (res.status === 'ok' || res.status === 'duplicate')) {
        setCurrent({
          ...current,
          scope: 'global',
          goal_id: null,
          goal_title: null,
          goal_inferred: false,
          message: '✓ Learned — applies to all of this agent\u2019s work now.',
        });
      } else {
        setUndoError('Could not widen that lesson.');
      }
    } catch (e) {
      setUndoError(e instanceof Error ? e.message : 'Could not widen that lesson.');
    } finally {
      setWidening(false);
    }
  };

  const undoTarget = current.teaching_point_id && current.agent?.id
    ? { agentId: current.agent.id, pointId: current.teaching_point_id }
    : null;

  const undo = async () => {
    if (!undoTarget) return;
    setUndoing(true);
    setUndoError(null);
    try {
      await deleteTeachingPoint(undoTarget.agentId, undoTarget.pointId);
      setUndone(true);
      onTaught?.({ ...current, status: 'empty', message: 'Lesson removed.' });
    } catch (e) {
      setUndoError(e instanceof Error ? e.message : "I couldn't undo that lesson.");
    } finally {
      setUndoing(false);
    }
  };

  const save = async (agentId: string) => {
    setBusyId(agentId);
    try {
      const result = await teachAgent(
        agentId,
        current.lesson,
        undefined,
        current.canvas_id || undefined,
      );
      const saved: TeachingNoticeData =
        result?.status === 'ok' || result?.status === 'skipped'
          ? {
              ...current,
              status: result?.status === 'ok' ? 'saved' : 'error',
              agent: { ...(current.agent || { id: agentId }), id: agentId },
              mode: (result?.mode as string) || current.mode || null,
              teaching_point_id:
                (result?.teaching_point_id as string) || current.teaching_point_id || null,
              message:
                result?.status === 'ok'
                  ? `✓ Learned — saved as a permanent lesson. It applies to all of their work from now on.`
                  : current.message,
            }
          : { ...current, status: 'error', message: 'I couldn\'t save that lesson — nothing was changed.' };
      setCurrent(saved);
      onTaught?.(saved);
    } catch {
      setCurrent({
        ...current,
        status: 'error',
        message: "I couldn't save that lesson — nothing was changed.",
      });
    } finally {
      setBusyId(null);
    }
  };

  if (undone) {
    return (
      <div
        className={`mt-2 rounded-md border border-muted bg-muted/40 px-2.5 py-1.5 text-[11px] text-muted-foreground ${className || ''}`}
        role="status"
        data-testid="teaching-undone"
      >
        Lesson removed — {current.agent?.name || 'the agent'} won't use it from now on.
      </div>
    );
  }

  if (current.status === 'saved') {
    return (
      <div
        className={`mt-2 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 py-1.5 text-[11px] text-emerald-900 dark:border-emerald-900/50 dark:bg-emerald-950/40 dark:text-emerald-200 ${className || ''}`}
        role="status"
        data-testid="teaching-saved"
      >
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <span className="font-semibold">Learned</span>
            {current.agent?.name ? <span> · {current.agent.name}</span> : null}
            {_tierLabel(current.agent) ? (
              <span className="ml-1 rounded bg-emerald-100 px-1 text-[9px] dark:bg-emerald-900/50">
                {_tierLabel(current.agent)}
              </span>
            ) : null}
            <div className="mt-0.5 whitespace-pre-wrap break-words">{current.lesson}</div>
            {current.scope === 'goal' && (
              <div className="mt-1 flex flex-wrap items-center gap-1.5" data-testid="teaching-scope">
                <span className="rounded bg-emerald-100 px-1 text-[9px] dark:bg-emerald-900/50">
                  {current.goal_title ? `this goal: ${current.goal_title}` : 'this goal only'}
                </span>
                {current.goal_inferred && (
                  <span className="text-[9px] opacity-80">(inferred)</span>
                )}
                {isSupervisor && (
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-5 px-1.5 text-[10px] text-emerald-900 hover:bg-emerald-100 dark:text-emerald-200 dark:hover:bg-emerald-900/50"
                    disabled={widening || undoing}
                    onClick={widenToAllWork}
                    title="Apply this rule to everything the agent does, not just this goal"
                    data-testid="teaching-widen"
                  >
                    {widening ? 'Applying…' : 'Apply to all work'}
                  </Button>
                )}
              </div>
            )}
          </div>
          {isSupervisor && undoTarget && (
            <Button
              size="sm"
              variant="ghost"
              className="h-5 shrink-0 px-1.5 text-[10px] text-emerald-900 hover:bg-emerald-100 dark:text-emerald-200 dark:hover:bg-emerald-900/50"
              disabled={undoing}
              onClick={undo}
              title="Remove this lesson — the agent stops using it from the next turn on"
              data-testid="teaching-undo"
            >
              {undoing ? 'Undoing…' : 'Undo'}
            </Button>
          )}
        </div>
        {undoError && (
          <div className="mt-1 text-[10px] text-red-700 dark:text-red-300" data-testid="teaching-undo-error">
            {undoError}
          </div>
        )}
      </div>
    );
  }

  if (current.status === 'duplicate') {
    return (
      <div
        className={`mt-2 rounded-md border border-muted bg-muted/40 px-2.5 py-1.5 text-[11px] text-muted-foreground ${className || ''}`}
        role="status"
        data-testid="teaching-duplicate"
      >
        {current.message}
        <div className="mt-0.5 whitespace-pre-wrap break-words italic">{current.lesson}</div>
      </div>
    );
  }

  if (current.status === 'suggested') {
    return (
      <div
        className={`mt-2 rounded-md border border-sky-200 bg-sky-50 px-2.5 py-2 text-[11px] text-sky-900 dark:border-sky-900/50 dark:bg-sky-950/40 dark:text-sky-200 ${className || ''}`}
        data-testid="teaching-suggestion"
      >
        <div className="font-semibold">Save as a permanent lesson?</div>
        <div className="mt-0.5 whitespace-pre-wrap break-words">{current.lesson}</div>
        <div className="mt-1.5 flex items-center gap-2">
          <Button
            size="sm"
            className="h-6 px-2 text-[10px]"
            disabled={busyId !== null || !current.agent?.id}
            onClick={() => save(current.agent?.id || '')}
            data-testid="teaching-save"
          >
            {busyId ? 'Saving…' : 'Save lesson'}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-6 px-2 text-[10px]"
            disabled={busyId !== null}
            onClick={() => setCurrent({ ...current, status: 'error', message: 'No problem — I won\'t remember that.' })}
            data-testid="teaching-dismiss"
          >
            Dismiss
          </Button>
        </div>
      </div>
    );
  }

  if (current.status === 'needs_agent') {
    return (
      <div
        className={`mt-2 rounded-md border border-amber-200 bg-amber-50 px-2.5 py-2 text-[11px] text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200 ${className || ''}`}
        role="status"
        data-testid="teaching-needs-agent"
      >
        <div className="whitespace-pre-wrap break-words">{current.message}</div>
        {current.lesson ? (
          <div className="mt-0.5 whitespace-pre-wrap break-words italic">"{current.lesson}"</div>
        ) : null}
        {(current.agents || []).length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5" data-testid="teaching-agent-options">
            {(current.agents || []).map((agent) => (
              <Button
                key={agent.id}
                size="sm"
                variant="outline"
                className="h-6 px-2 text-[10px]"
                disabled={busyId !== null}
                onClick={() => save(agent.id)}
                data-testid={`teaching-agent-option-${agent.id}`}
              >
                {busyId === agent.id ? 'Saving…' : agent.name || agent.id}
                {_tierLabel(agent) ? (
                  <span className="ml-1 text-[9px] opacity-70">{_tierLabel(agent)}</span>
                ) : null}
              </Button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className={`mt-2 rounded-md border px-2.5 py-1.5 text-[11px] ${className || ''}`}
      role="status"
      data-testid="teaching-notice"
    >
      {current.message}
    </div>
  );
}

export default TeachingNotice;
