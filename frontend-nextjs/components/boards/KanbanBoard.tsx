'use client';

import { DndContext, type DragEndEvent, PointerSensor, useSensor, useSensors } from '@dnd-kit/core';
import { useState } from 'react';
import { toast } from 'sonner';
import { type BoardDetail, type BoardTask } from '../../lib/boards-api';
import { useCreateTask, useDeleteTask, usePatchTask, useTasks } from '../../hooks/useBoard';
import { KanbanColumn } from './KanbanColumn';
import { TaskDetailDrawer } from './TaskDetailDrawer';
import { SlashCommandBar } from './SlashCommandBar';

interface Props {
  board: BoardDetail;
}

export function KanbanBoard({ board }: Props) {
  const { data: tasks, isLoading } = useTasks(board.id);
  const createTask = useCreateTask(board.id);
  const patchTask = usePatchTask(board.id);
  const deleteTask = useDeleteTask(board.id);
  const [openTaskId, setOpenTaskId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  if (isLoading || !tasks) {
    return <div className="p-8 text-gray-500">Loading board…</div>;
  }

  const tasksByColumn = new Map<string, BoardTask[]>();
  for (const t of tasks) {
    const list = tasksByColumn.get(t.column_id) || [];
    list.push(t);
    tasksByColumn.set(t.column_id, list);
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over) return;
    const activeId = String(active.id);
    const overId = String(over.id);

    const task = tasks.find((t) => t.id === activeId);
    if (!task) return;

    const targetColumnId = overId.startsWith('column-')
      ? overId.slice('column-'.length)
      : tasks.find((t) => t.id === overId)?.column_id;

    if (!targetColumnId || targetColumnId === task.column_id) {
      const overTask = tasks.find((t) => t.id === overId);
      if (overTask && overTask.id !== task.id) {
        patchTask.mutate({
          taskId: task.id,
          input: {
            expected_version: task.version_id,
            sort_order: overTask.sort_order,
          },
        });
      }
      return;
    }

    patchTask.mutate({
      taskId: task.id,
      input: {
        expected_version: task.version_id,
        column_id: targetColumnId,
      },
    });
  };

  const openTask = tasks.find((t) => t.id === openTaskId) || null;

  return (
    <DndContext sensors={sensors} onDragEnd={handleDragEnd}>
      <div className="flex h-full flex-col">
        <div className="border-b p-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold">{board.name}</h1>
              {board.description && (
                <p className="mt-1 text-sm text-gray-600">{board.description}</p>
              )}
            </div>
            <SlashCommandBar boardId={board.id} />
          </div>
        </div>

        <div className="flex-1 overflow-x-auto p-4">
          <div className="flex gap-4 h-full">
            {board.columns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                tasks={(tasksByColumn.get(column.id) || []).sort(
                  (a, b) => a.sort_order - b.sort_order,
                )}
                onTaskClick={(t) => setOpenTaskId(t.id)}
                onAddTask={(col) => {
                  const title = window.prompt(`New task in ${col.name}`);
                  if (!title) return;
                  createTask.mutate({ title, column_id: col.id });
                }}
              />
            ))}
          </div>
        </div>
      </div>

      <TaskDetailDrawer
        boardId={board.id}
        task={openTask}
        open={openTask !== null}
        onClose={() => setOpenTaskId(null)}
        onDelete={async (t) => {
          await deleteTask.mutateAsync(t.id);
          setOpenTaskId(null);
          toast.success('Task deleted');
        }}
      />
    </DndContext>
  );
}
