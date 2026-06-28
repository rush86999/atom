'use client';

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, FolderOpen, AlertCircle } from 'lucide-react';
import { type BoardTask } from '../../lib/boards-api';
import { cn } from '../../lib/utils';

interface Props {
  task: BoardTask;
  onClick?: (task: BoardTask) => void;
}

const PRIORITY_COLORS: Record<string, string> = {
  urgent: 'border-l-red-500',
  high: 'border-l-orange-500',
  normal: 'border-l-blue-500',
  low: 'border-l-gray-400',
};

const STATUS_BADGE: Record<string, string> = {
  blocked: 'bg-red-100 text-red-700',
  in_review: 'bg-purple-100 text-purple-700',
  in_progress: 'bg-blue-100 text-blue-700',
};

export function KanbanCard({ task, onClick }: Props) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: task.id,
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const priorityClass = PRIORITY_COLORS[task.priority] || PRIORITY_COLORS.normal;
  const statusBadge = STATUS_BADGE[task.status];

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'group relative cursor-pointer rounded-md border border-l-4 bg-white p-3 shadow-sm hover:shadow-md transition-shadow',
        priorityClass,
        isDragging && 'ring-2 ring-blue-500',
      )}
      onClick={() => onClick?.(task)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.(task);
        }
      }}
      aria-label={`Task: ${task.title}`}
    >
      <button
        type="button"
        className="absolute inset-0 cursor-grab active:cursor-grabbing"
        aria-label="Drag task"
        {...attributes}
        {...listeners}
        onClick={(e) => e.stopPropagation()}
      />

      <div className="relative pointer-events-none">
        <div className="flex items-start justify-between gap-2">
          <h4 className="font-medium text-sm text-gray-900 line-clamp-2">
            {task.title || <span className="italic text-gray-500">Untitled</span>}
          </h4>
          <GripVertical className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100" />
        </div>

        {task.description && (
          <p className="mt-1 text-xs text-gray-600 line-clamp-2">{task.description}</p>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[10px]">
          {statusBadge && (
            <span className={cn('rounded px-1.5 py-0.5 font-medium uppercase', statusBadge)}>
              {task.status.replace('_', ' ')}
            </span>
          )}
          {task.due_at && (
            <span className="text-gray-500">
              due {new Date(task.due_at).toLocaleDateString()}
            </span>
          )}
          {task.canvas_id && (
            <span className="flex items-center gap-0.5 text-purple-600">
              <FolderOpen className="h-3 w-3" />
              {task.canvas?.artifact_count ?? 0}
            </span>
          )}
        </div>

        {task.status === 'blocked' && (
          <div className="mt-2 flex items-center gap-1 rounded bg-red-50 px-1.5 py-0.5 text-[10px] text-red-700">
            <AlertCircle className="h-3 w-3" />
            Blocked
          </div>
        )}
      </div>
    </div>
  );
}
