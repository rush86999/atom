'use client';

import Link from 'next/link';
import { ExternalLink, FolderPlus, FolderOpen, Users, FileText } from 'lucide-react';
import { type BoardTask } from '../../lib/boards-api';
import { usePatchTask } from '../../hooks/useBoard';

interface Props {
  task: BoardTask;
}

export function CanvasWorkspacePanel({ task }: Props) {
  const patchTask = usePatchTask(task.board_id);

  const createWorkspace = () => {
    patchTask.mutate({
      taskId: task.id,
      input: { expected_version: task.version_id, workspace: true },
    });
  };

  if (!task.canvas_id) {
    return (
      <div className="rounded border border-dashed border-purple-200 bg-purple-50 p-3">
        <div className="flex items-center gap-2 text-sm text-purple-700">
          <FolderPlus className="h-4 w-4" />
          <span className="font-medium">Task workspace</span>
        </div>
        <p className="mt-1 text-xs text-purple-600">
          Create a Canvas for this task to capture artifacts, comments, and live
          agent presence.
        </p>
        <button
          type="button"
          onClick={createWorkspace}
          disabled={patchTask.isPending}
          className="mt-2 rounded bg-purple-500 px-2 py-1 text-xs text-white hover:bg-purple-600 disabled:opacity-50"
        >
          Create Workspace
        </button>
      </div>
    );
  }

  const canvas = task.canvas;
  return (
    <div className="rounded border bg-gray-50 p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm font-medium text-gray-800">
          <FolderOpen className="h-4 w-4 text-purple-600" />
          Workspace
        </div>
        <Link
          href={`/canvas/${task.canvas_id}`}
          className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
        >
          Open <ExternalLink className="h-3 w-3" />
        </Link>
      </div>
      {canvas && (
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-600">
          <span className="flex items-center gap-1">
            <FileText className="h-3 w-3" />
            {canvas.artifact_count} artifact{canvas.artifact_count === 1 ? '' : 's'}
          </span>
          <span className="flex items-center gap-1">
            <Users className="h-3 w-3" />
            {canvas.presence_count} active
          </span>
          <span className={canvas.status === 'archived' ? 'text-gray-400' : 'text-green-600'}>
            {canvas.status}
          </span>
        </div>
      )}
    </div>
  );
}
