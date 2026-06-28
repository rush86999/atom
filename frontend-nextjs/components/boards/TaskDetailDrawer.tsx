'use client';

import { useEffect, useState } from 'react';
import { X, Trash2, Send, Sparkles } from 'lucide-react';
import { toast } from 'sonner';
import {
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

export function TaskDetailDrawer({ boardId, task, open, onClose, onDelete }: Props) {
  const patchTask = usePatchTask(boardId);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [comments, setComments] = useState<BoardComment[]>([]);
  const [newComment, setNewComment] = useState('');
  const [showDecomposeModal, setShowDecomposeModal] = useState(false);

  useEffect(() => {
    if (!task) return;
    setTitle(task.title);
    setDescription(task.description || '');
    setNewComment('');
    listComments(boardId, task.id).then(setComments).catch(() => setComments([]));
  }, [boardId, task?.id]);

  if (!task) {
    return null;
  }

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

  const submitComment = async () => {
    if (!newComment.trim()) return;
    try {
      const msg = await postComment(boardId, task.id, newComment.trim());
      setComments((prev) => [...prev, msg]);
      setNewComment('');
    } catch (e) {
      toast.error(`Couldn't post comment: ${(e as Error).message}`);
    }
  };

  const allowedNext = STATUS_GRAPH[task.status] || [];

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
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              onBlur={() => saveField('title', title)}
            />
            <button onClick={onClose} aria-label="Close" className="ml-2 rounded p-1 hover:bg-gray-100">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
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
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onBlur={() => saveField('description', description)}
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
                  value={newComment}
                  onChange={(e) => setNewComment(e.target.value)}
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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rationale, setRationale] = useState('');
  const [subtasks, setSubtasks] = useState<
    { title: string; column_name: string; description?: string }[]
  >([]);

  const runPropose = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await proposeDecompose(boardId, task.id);
      setRationale(result.rationale);
      setSubtasks(result.subtasks.map((s) => ({
        title: s.title,
        column_name: s.column_name,
        description: s.description || undefined,
      })));
    } catch (e) {
      if (e instanceof DecomposeNeedsKeyError) {
        setError(e.message);
      } else {
        setError((e as Error).message);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runPropose();
  }, []);

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
