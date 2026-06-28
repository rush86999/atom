'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback } from 'react';
import { toast } from 'sonner';

import {
  type BoardTask,
  type TaskCreateInput,
  type TaskPatchInput,
  type Board,
  type BoardDetail,
  createBoard,
  createTask,
  deleteTask,
  getBoard,
  listBoards,
  listTasks,
  patchTask,
} from '../lib/boards-api';

export function useBoards() {
  return useQuery<Board[]>({
    queryKey: ['boards'],
    queryFn: listBoards,
  });
}

export function useBoard(boardId: string | null) {
  return useQuery<BoardDetail>({
    queryKey: ['board', boardId],
    queryFn: () => getBoard(boardId!),
    enabled: Boolean(boardId),
  });
}

export function useCreateBoard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; description?: string }) => createBoard(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['boards'] });
    },
  });
}

export function useTasks(boardId: string | null) {
  return useQuery<BoardTask[]>({
    queryKey: ['board', boardId, 'tasks'],
    queryFn: () => listTasks(boardId!),
    enabled: Boolean(boardId),
  });
}

export function useCreateTask(boardId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: TaskCreateInput) => createTask(boardId, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['board', boardId, 'tasks'] });
    },
    onError: (err) => toast.error(`Couldn't create task: ${(err as Error).message}`),
  });
}

export function usePatchTask(boardId: string) {
  const qc = useQueryClient();

  const applyOptimistic = useCallback(
    (taskId: string, patch: Partial<BoardTask>) => {
      qc.setQueryData<BoardTask[]>(['board', boardId, 'tasks'], (old) => {
        if (!old) return old;
        return old.map((t) => (t.id === taskId ? { ...t, ...patch } : t));
      });
    },
    [qc, boardId],
  );

  return useMutation({
    mutationFn: ({ taskId, input }: { taskId: string; input: TaskPatchInput }) =>
      patchTask(boardId, taskId, input),
    onMutate: async ({ taskId, input }) => {
      const patch: Partial<BoardTask> = {};
      if (input.title !== undefined) patch.title = input.title;
      if (input.description !== undefined) patch.description = input.description;
      if (input.priority !== undefined) patch.priority = input.priority;
      if (input.column_id !== undefined) patch.column_id = input.column_id;
      if (input.status !== undefined) patch.status = input.status;
      if (input.assignee_user_id !== undefined) patch.assignee_user_id = input.assignee_user_id;
      applyOptimistic(taskId, patch);
    },
    onSuccess: ({ task, conflict }) => {
      if (conflict) {
        qc.invalidateQueries({ queryKey: ['board', boardId, 'tasks'] });
        toast.warning('Another tab edited this task. Refreshed to latest.');
        return;
      }
      qc.setQueryData<BoardTask[]>(['board', boardId, 'tasks'], (old) => {
        if (!old) return old;
        return old.map((t) => (t.id === task.id ? task : t));
      });
    },
    onError: (err, _vars) => {
      qc.invalidateQueries({ queryKey: ['board', boardId, 'tasks'] });
      toast.error(`Couldn't save: ${(err as Error).message}`);
    },
  });
}

export function useDeleteTask(boardId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => deleteTask(boardId, taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['board', boardId, 'tasks'] });
    },
    onError: (err) => toast.error(`Couldn't delete: ${(err as Error).message}`),
  });
}
