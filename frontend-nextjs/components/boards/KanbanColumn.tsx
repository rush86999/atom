'use client';

import { useDroppable } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { Plus, AlertCircle } from 'lucide-react';
import { type BoardColumn, type BoardTask } from '../../lib/boards-api';
import { KanbanCard } from './KanbanCard';
import { cn } from '../../lib/utils';

interface Props {
  column: BoardColumn;
  tasks: BoardTask[];
  onTaskClick?: (task: BoardTask) => void;
  onAddTask?: (column: BoardColumn) => void;
}

export function KanbanColumn({ column, tasks, onTaskClick, onAddTask }: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: `column-${column.id}` });

  const overWipLimit =
    column.wip_limit !== null && tasks.length > column.wip_limit;

  return (
    <div
      ref={setNodeRef}
      className={cn(
        'flex w-72 flex-col rounded-lg bg-gray-100 border',
        isOver && 'ring-2 ring-blue-400 bg-blue-50',
      )}
    >
      <div className="flex items-center justify-between p-3 border-b">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-sm text-gray-800">{column.name}</h3>
          <span className={cn(
            'rounded-full px-2 py-0.5 text-[10px] font-medium',
            overWipLimit ? 'bg-red-100 text-red-700' : 'bg-gray-200 text-gray-700',
          )}>
            {tasks.length}
            {column.wip_limit !== null && ` / ${column.wip_limit}`}
          </span>
        </div>
        <button
          type="button"
          onClick={() => onAddTask?.(column)}
          className="rounded p-1 text-gray-500 hover:bg-gray-200 hover:text-gray-700"
          aria-label={`Add task to ${column.name}`}
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {overWipLimit && (
        <div className="flex items-center gap-1 bg-red-50 px-3 py-1 text-[10px] text-red-700">
          <AlertCircle className="h-3 w-3" />
          Over WIP limit
        </div>
      )}

      <div className="flex-1 space-y-2 overflow-y-auto p-2 min-h-[100px]">
        <SortableContext items={tasks.map((t) => t.id)} strategy={verticalListSortingStrategy}>
          {tasks.map((task) => (
            <KanbanCard key={task.id} task={task} onClick={onTaskClick} />
          ))}
        </SortableContext>
        {tasks.length === 0 && (
          <div className="flex h-20 items-center justify-center rounded border border-dashed text-xs text-gray-400">
            Drop tasks here
          </div>
        )}
      </div>
    </div>
  );
}
