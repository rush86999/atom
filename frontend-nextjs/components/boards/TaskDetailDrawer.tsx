'use client';

import React, { useEffect, useRef, useState } from 'react';
import { X, Trash2, Send, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import {
  type BoardColumn,
  type BoardTask,
  listComments,
  postComment,
  proposeDecompose,
  commitDecompose,
  type BoardComment,
  DecomposeNeedsKeyError,
} from '../../lib/boards-api';
import { usePatchTask } from '../../hooks/useBoard';
import { CanvasWorkspacePanel } from './CanvasWorkspacePanel';

interface Props {
  boardId: string;
  task: BoardTask | null;
  columns?: BoardColumn[];
  open: boolean;
  onClose: () => void;
  onDelete: (task: BoardTask) => void;
}

const STATUS_GRAPH: Record<string, string[]> = {
  backlog: ['todo', 'blocked'],
  todo: ['in_progress', 'blocked', 'backlog'],
  in_progress: ['in_review', 'done', 'blocked', 'todo'],
  in_review: ['in_progress', 'done', 'blocked', 'todo'],
  blocked: ['todo', 'in_progress', 'in_review'],
  done: ['todo'],
};

interface TaskDraft {
  taskKey: string;
  title: string;
  description: string;
  newComment: string;
}

interface PendingMove {
  toColumnId: string;
  fromColumnId: string;
}

function createTaskDraft(taskKey: string, task: BoardTask | null): TaskDraft {
  return {
    taskKey,
    title: task?.title ?? '',
    description: task?.description || '',
    newComment: '',
  };
}

export function TaskDetailDrawer({
  boardId,
  task,
  columns = [],
  open,
  onClose,
  onDelete,
}: Props) {
  const patchTask = usePatchTask(boardId);
  const taskKey = `${boardId}:${task?.id ?? ''}`;
  const [draft, setDraft] = useState<TaskDraft>(() => createTaskDraft(taskKey, task));
  const activeDraft = draft.taskKey === taskKey ? draft : createTaskDraft(taskKey, task);
  const [comments, setComments] = useState<BoardComment[]>([]);
  const [showDecomposeModal, setShowDecomposeModal] = useState(false);
  const [pendingMove, setPendingMove] = useState<PendingMove | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);
  const moveRequestRef = useRef(0);
  const moveInFlightRef = useRef(false);
  const currentColumnRef = useRef<HTMLSpanElement>(null);
  const focusCurrentColumnRef = useRef(false);
  const taskId = task?.id ?? null;

  useEffect(() => {
    if (!taskId) return;
    listComments(boardId, taskId).then(setComments).catch(() => setComments([]));
  }, [boardId, taskId]);

  // Switching tasks (or closing the drawer) invalidates callbacks from any
  // move that was still in flight. Without this token an old request could
  // clear the new task's pending state or surface its error on the wrong task.
  useEffect(() => {
    moveRequestRef.current += 1;
    moveInFlightRef.current = false;
    setPendingMove(null);
    setMoveError(null);
  }, [taskKey]);

  // Once a successful move removes the focused destination button, keep
  // keyboard focus inside the drawer on the (stable) current-column label.
  useEffect(() => {
    if (!focusCurrentColumnRef.current) return;
    focusCurrentColumnRef.current = false;
    currentColumnRef.current?.focus();
  }, [pendingMove, task?.column_id]);

  if (!task) {
    return null;
  }

  const updateDraft = (updates: Partial<Omit<TaskDraft, 'taskKey'>>) => {
    setDraft(previous => ({
      ...(previous.taskKey === taskKey ? previous : createTaskDraft(taskKey, task)),
      ...updates,
    }));
  };

  const saveField = (field: 'title' | 'description', value: string) => {
    if (!task) return;
    if (task[field] === value) return;
    patchTask.mutate({
      taskId: task.id,
      input: { expected_version: task.version_id, [field]: value },
    });
  };

  const transition = (toStatus: string) => {
    patchTask.mutate({
      taskId: task.id,
      input: { expected_version: task.version_id, status: toStatus },
    });
  };

  const moveToColumn = (column: BoardColumn) => {
    if (column.id === task.column_id || pendingMove !== null || moveInFlightRef.current) return;
    moveInFlightRef.current = true;
    const requestId = ++moveRequestRef.current;
    const fromColumnId = task.column_id;

    setPendingMove({ toColumnId: column.id, fromColumnId });
    setMoveError(null);
    // The destination button becomes disabled while the request is in flight.
    // Move focus to the stable column label now so disabling it cannot drop
    // keyboard focus to <body>.
    currentColumnRef.current?.focus();

    patchTask.mutate(
      {
        taskId: task.id,
        input: { expected_version: task.version_id, column_id: column.id },
      },
      {
        onSuccess: (result) => {
          if (moveRequestRef.current !== requestId) return;
          moveInFlightRef.current = false;
          setPendingMove(null);
          if (result.conflict) {
            setMoveError('Another tab edited this task. Try the move again.');
            return;
          }
          focusCurrentColumnRef.current = true;
        },
        onError: (error) => {
          if (moveRequestRef.current !== requestId) return;
          moveInFlightRef.current = false;
          setPendingMove(null);
          setMoveError((error as Error).message);
        },
      },
    );
  };

  const submitComment = async () => {
    if (!activeDraft.newComment.trim()) return;
    try {
      const msg = await postComment(boardId, task.id, activeDraft.newComment.trim());
      setComments((prev) => [...prev, msg]);
      updateDraft({ newComment: '' });
    } catch (e) {
      toast.error(`Couldn't post comment: ${(e as Error).message}`);
    }
  };

  const allowedNext = STATUS_GRAPH[task.status] || [];

  // The shared optimistic cache updates the task's column_id as soon as the
  // PATCH starts. Keep rendering the source column while the move is pending
  // so the requested destination button stays present (and focusable) rather
  // than disappearing underneath the user.
  const displayColumnId = pendingMove?.fromColumnId ?? task.column_id;
  const displayColumnName =
    columns.find((column) => column.id === displayColumnId)?.name ?? 'Unknown column';
  const moveDestinationName =
    columns.find((column) => column.id === pendingMove?.toColumnId)?.name ?? 'selected column';
  const moveTargets = columns.filter((column) => column.id !== displayColumnId);
  const isMovePending = pendingMove !== null;

  return (
    <>
      <div
        className={`fixed inset-y-0 right-0 w-full max-w-md transform border-l bg-white shadow-xl transition-transform ${
          open ? 'translate-x-0' : 'translate-x-full'
        }`}
        role="dialog"
        aria-label={`Task: ${task.title}`}
      >
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b p-4">
            <input
              className="flex-1 text-lg font-semibold focus:outline-none"
              value={activeDraft.title}
              onChange={(e) => updateDraft({ title: e.target.value })}
              onBlur={() => saveField('title', activeDraft.title)}
            />
            <button onClick={onClose} aria-label="Close" className="ml-2 rounded p-1 hover:bg-gray-100">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div>
              <label className="text-xs font-medium uppercase text-gray-500">Column</label>
              <div className="mt-1 flex flex-wrap gap-1">
                <span
                  ref={currentColumnRef}
                  tabIndex={-1}
                  aria-label={`Current column: ${displayColumnName}`}
                  className="rounded bg-gray-200 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {displayColumnName}
                </span>
                {moveTargets.map((column) => (
                  <button
                    key={column.id}
                    type="button"
                    onClick={() => moveToColumn(column)}
                    disabled={isMovePending}
                    aria-label={`Move to ${column.name}`}
                    aria-busy={pendingMove?.toColumnId === column.id}
                    className="rounded border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700 hover:bg-blue-100 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    → {column.name}
                  </button>
                ))}
                {columns.length === 0 && (
                  <span className="px-1 py-1 text-xs text-gray-500">
                    Column moves unavailable.
                  </span>
                )}
              </div>
              {pendingMove && (
                <p role="status" className="mt-1 text-xs text-gray-500">
                  Moving to {moveDestinationName}…
                </p>
              )}
              {moveError && (
                <p role="alert" className="mt-1 text-xs text-red-600">
                  Couldn&apos;t move task: {moveError}
                </p>
              )}
            </div>

            <div>
              <label className="text-xs font-medium uppercase text-gray-500">Status</label>
              <div className="mt-1 flex flex-wrap gap-1">
                <span className="rounded bg-gray-200 px-2 py-1 text-xs">{task.status}</span>
                {allowedNext.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => transition(s)}
                    className="rounded border border-blue-200 bg-blue-50 px-2 py-1 text-xs text-blue-700 hover:bg-blue-100"
                  >
                    → {s.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-xs font-medium uppercase text-gray-500">Description</label>
              <textarea
                className="mt-1 w-full rounded border p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                rows={4}
                value={activeDraft.description}
                onChange={(e) => updateDraft({ description: e.target.value })}
                onBlur={() => saveField('description', activeDraft.description)}
              />
            </div>

            <CanvasWorkspacePanel task={task} />

            <div>
              <button
                type="button"
                onClick={() => setShowDecomposeModal(true)}
                className="flex items-center gap-2 rounded border border-purple-200 bg-purple-50 px-3 py-2 text-sm text-purple-700 hover:bg-purple-100"
              >
                <Sparkles className="h-4 w-4" />
                Decompose with AI
              </button>
            </div>

            <div>
              <label className="text-xs font-medium uppercase text-gray-500">
                Comments ({comments.length})
              </label>
              <div className="mt-2 space-y-2">
                {comments.map((c) => (
                  <div key={c.id} className="rounded border p-2 text-sm">
                    <div className="text-xs text-gray-500">
                      {c.author.display_name || c.author.user_id || c.author.agent_id}
                    </div>
                    <div>{c.content}</div>
                  </div>
                ))}
                {comments.length === 0 && (
                  <p className="text-xs text-gray-400">No comments yet.</p>
                )}
              </div>
              <div className="mt-2 flex gap-1">
                <input
                  className="flex-1 rounded border px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Add a comment…"
                  value={activeDraft.newComment}
                  onChange={(e) => updateDraft({ newComment: e.target.value })}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      submitComment();
                    }
                  }}
                />
                <button
                  type="button"
                  onClick={submitComment}
                  aria-label="Post comment"
                  className="rounded bg-blue-500 px-2 text-white hover:bg-blue-600"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>

          <div className="border-t p-4">
            <button
              type="button"
              onClick={() => onDelete(task)}
              className="flex items-center gap-2 text-sm text-red-600 hover:text-red-700"
            >
              <Trash2 className="h-4 w-4" />
              Delete task
            </button>
          </div>
        </div>
      </div>

      {showDecomposeModal && task && (
        <DecomposeModal
          boardId={boardId}
          task={task}
          onClose={() => setShowDecomposeModal(false)}
        />
      )}
    </>
  );
}

function DecomposeModal({
  boardId,
  task,
  onClose,
}: {
  boardId: string;
  task: BoardTask;
  onClose: () => void;
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rationale, setRationale] = useState('');
  const [subtasks, setSubtasks] = useState<
    { title: string; column_name: string; description?: string }[]
  >([]);

  useEffect(() => {
    let cancelled = false;
    proposeDecompose(boardId, task.id)
      .then((result) => {
        if (cancelled) return;
        setRationale(result.rationale);
        setSubtasks(result.subtasks.map((s) => ({
          title: s.title,
          column_name: s.column_name,
          description: s.description || undefined,
        })));
      })
      .catch((e) => {
        if (cancelled) return;
        setError(e instanceof DecomposeNeedsKeyError ? e.message : (e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [boardId, task.id]);

  const confirm = async () => {
    setLoading(true);
    try {
      await commitDecompose(boardId, task.id, subtasks);
      toast.success(`Created ${subtasks.length} subtasks`);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Decompose: {task.title}</h3>
          <button onClick={onClose} aria-label="Close">
            <X className="h-5 w-5" />
          </button>
        </div>

        {loading && <p className="mt-4 text-sm text-gray-500">Asking the LLM Ask…</p>}
        {error && (
          <div className="mt-4 rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {rationale && (
          <p className="mt-4 text-sm italic text-gray-600">{rationale}</p>
        )}

        {subtasks.length > 0 && (
          <ul className="mt-4 space-y-2">
            {subtasks.map((s, i) => (
              <li key={i} className="rounded border p-2 text-sm">
                <input
                  className="w-full font-medium focus:outline-none"
                  value={s.title}
                  onChange={(e) => {
                    const next = [...subtasks];
                    next[i] = { ...s, title: e.target.value };
                    setSubtasks(next);
                  }}
                />
                <div className="mt-1 text-xs text-gray-500">
                  {s.column_name} — {s.description}
                </div>
              </li>
            ))}
          </ul>
        )}

        {subtasks.length > 0 && (
          <div className="mt-4 flex justify-end gap-2">
            <button
              onClick={onClose}
              className="rounded border px-3 py-1 text-sm"
            >
              Cancel
            </button>
            <button
              onClick={confirm}
              disabled={loading}
              className="rounded bg-purple-500 px-3 py-1 text-sm text-white hover:bg-purple-600"
            >
              Create {subtasks.length} subtasks
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
