/**
 * useBoard hook unit tests.
 *
 * Covers useBoards, useBoard, useTasks, useCreateBoard, useCreateTask,
 * usePatchTask (optimistic updates, conflict handling) and useDeleteTask,
 * using a real QueryClient + mocked boards-api + mocked sonner toasts.
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import * as React from 'react';

jest.mock('sonner', () => ({
  toast: {
    error: jest.fn(),
    warning: jest.fn(),
  },
}));

jest.mock('../../lib/boards-api', () => ({
  listBoards: jest.fn(),
  getBoard: jest.fn(),
  createBoard: jest.fn(),
  listTasks: jest.fn(),
  createTask: jest.fn(),
  patchTask: jest.fn(),
  deleteTask: jest.fn(),
}));

import { toast } from 'sonner';
import * as boardsApi from '../../lib/boards-api';
import {
  useBoards,
  useBoard,
  useTasks,
  useCreateBoard,
  useCreateTask,
  usePatchTask,
  useDeleteTask,
} from '../useBoard';

const mockToastError = toast.error as jest.Mock;
const mockToastWarning = toast.warning as jest.Mock;

const wrapper = ({ children }: { children: React.ReactNode }) => {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
};

// Wrapper factory over an externally-owned QueryClient (needed when a test
// must seed the cache before/after a mutation runs).
const makeWrapper = (qc: QueryClient) => ({ children }: { children: React.ReactNode }) => (
  <QueryClientProvider client={qc}>{children}</QueryClientProvider>
);

describe('useBoard hooks', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('useBoards', () => {
    test('fetches boards via listBoards', async () => {
      const boards = [{ id: 'b1', name: 'Board' }];
      (boardsApi.listBoards as jest.Mock).mockResolvedValue(boards);

      const { result } = renderHook(() => useBoards(), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(boards);
      expect(boardsApi.listBoards).toHaveBeenCalled();
    });

    test('surfaces listBoards errors', async () => {
      (boardsApi.listBoards as jest.Mock).mockRejectedValue(new Error('boom'));

      const { result } = renderHook(() => useBoards(), { wrapper });

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect((result.current.error as Error).message).toBe('boom');
    });
  });

  describe('useBoard', () => {
    test('fetches board detail when boardId is provided', async () => {
      const detail = { id: 'b1', name: 'Board', columns: [] as any[] };
      (boardsApi.getBoard as jest.Mock).mockResolvedValue(detail);

      const { result } = renderHook(() => useBoard('b1'), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(detail);
      expect(boardsApi.getBoard).toHaveBeenCalledWith('b1');
    });

    test('does not fetch when boardId is null (disabled)', () => {
      const { result } = renderHook(() => useBoard(null), { wrapper });

      expect(result.current.isPending).toBe(true);
      expect(boardsApi.getBoard).not.toHaveBeenCalled();
    });
  });

  describe('useTasks', () => {
    test('fetches tasks when boardId is provided', async () => {
      const tasks = [{ id: 't1', title: 'Task' }];
      (boardsApi.listTasks as jest.Mock).mockResolvedValue(tasks);

      const { result } = renderHook(() => useTasks('b1'), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(result.current.data).toEqual(tasks);
    });

    test('does not fetch when boardId is null', () => {
      const { result } = renderHook(() => useTasks(null), { wrapper });

      expect(result.current.isPending).toBe(true);
      expect(boardsApi.listTasks).not.toHaveBeenCalled();
    });
  });

  describe('useCreateBoard', () => {
    test('creates a board and invalidates the boards query', async () => {
      const created = { id: 'b2', name: 'New' };
      (boardsApi.createBoard as jest.Mock).mockResolvedValue(created);

      const { result } = renderHook(() => useCreateBoard(), { wrapper });

      await act(async () => {
        await result.current.mutateAsync({ name: 'New' });
      });

      expect(boardsApi.createBoard).toHaveBeenCalledWith({ name: 'New' });
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });
  });

  describe('useCreateTask', () => {
    test('creates a task and invalidates the task query', async () => {
      const task = { id: 't2', title: 'Do it' };
      (boardsApi.createTask as jest.Mock).mockResolvedValue(task);

      const { result } = renderHook(() => useCreateTask('b1'), { wrapper });

      await act(async () => {
        await result.current.mutateAsync({ title: 'Do it', column_id: 'c1' });
      });

      expect(boardsApi.createTask).toHaveBeenCalledWith('b1', { title: 'Do it', column_id: 'c1' });
    });

    test('shows an error toast when creation fails', async () => {
      (boardsApi.createTask as jest.Mock).mockRejectedValue(new Error('failed'));

      const { result } = renderHook(() => useCreateTask('b1'), { wrapper });

      await act(async () => {
        try {
          await result.current.mutateAsync({ title: 'x', column_id: 'c1' });
        } catch {
          /* expected */
        }
      });

      expect(mockToastError).toHaveBeenCalledWith("Couldn't create task: failed");
    });
  });

  describe('usePatchTask', () => {
    test('applies an optimistic update and commits the server task on success', async () => {
      const serverTask = { id: 't1', title: 'Patched', status: 'done' };
      (boardsApi.patchTask as jest.Mock).mockResolvedValue({ task: serverTask, conflict: false });

      // Seed the task cache so the optimistic updater and the onSuccess
      // cache write both exercise their task-mapping branches.
      const qc = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
      });
      qc.setQueryData(['board', 'b1', 'tasks'], [{ id: 't1', title: 'Original' }]);

      const { result } = renderHook(() => usePatchTask('b1'), { wrapper: makeWrapper(qc) });

      await act(async () => {
        await result.current.mutateAsync({ taskId: 't1', input: { expected_version: 1, title: 'Patched', status: 'done' } });
      });

      expect(boardsApi.patchTask).toHaveBeenCalledWith('b1', 't1', {
        expected_version: 1,
        title: 'Patched',
        status: 'done',
      });
      await waitFor(() => {
        const cached = qc.getQueryData(['board', 'b1', 'tasks']) as any[];
        expect(cached.find((t: any) => t.id === 't1').title).toBe('Patched');
      });
    });

    test('toasts a warning and refetches on conflict', async () => {
      (boardsApi.patchTask as jest.Mock).mockResolvedValue({
        task: { id: 't1', title: 'Other' },
        conflict: true,
      });

      const { result } = renderHook(() => usePatchTask('b1'), { wrapper });

      await act(async () => {
        await result.current.mutateAsync({ taskId: 't1', input: { expected_version: 0 } });
      });

      expect(mockToastWarning).toHaveBeenCalledWith(
        'Another tab edited this task. Refreshed to latest.'
      );
    });

    test('toasts an error and refetches on failure', async () => {
      (boardsApi.patchTask as jest.Mock).mockRejectedValue(new Error('nope'));

      const { result } = renderHook(() => usePatchTask('b1'), { wrapper });

      await act(async () => {
        try {
          await result.current.mutateAsync({ taskId: 't1', input: { expected_version: 1 } });
        } catch {
          /* expected */
        }
      });

      expect(mockToastError).toHaveBeenCalledWith("Couldn't save: nope");
    });

    test('no-ops the optimistic update when the task cache is empty', async () => {
      // When no tasks are cached for the board, applyOptimistic and the
      // onSuccess cache write must tolerate the undefined cache (no crash).
      (boardsApi.patchTask as jest.Mock).mockResolvedValue({
        task: { id: 't1', title: 'New' },
        conflict: false,
      });

      const { result } = renderHook(() => usePatchTask('b1'), { wrapper });

      await act(async () => {
        await result.current.mutateAsync({ taskId: 't1', input: { expected_version: 1 } });
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockToastWarning).not.toHaveBeenCalled();
    });
  });

  describe('useDeleteTask', () => {
    test('deletes a task and invalidates the task query', async () => {
      (boardsApi.deleteTask as jest.Mock).mockResolvedValue(undefined);

      const { result } = renderHook(() => useDeleteTask('b1'), { wrapper });

      await act(async () => {
        await result.current.mutateAsync('t1');
      });

      expect(boardsApi.deleteTask).toHaveBeenCalledWith('b1', 't1');
      await waitFor(() => expect(result.current.isSuccess).toBe(true));
    });

    test('toasts an error when deletion fails', async () => {
      (boardsApi.deleteTask as jest.Mock).mockRejectedValue(new Error('gone'));

      const { result } = renderHook(() => useDeleteTask('b1'), { wrapper });

      await act(async () => {
        try {
          await result.current.mutateAsync('t1');
        } catch {
          /* expected */
        }
      });

      expect(mockToastError).toHaveBeenCalledWith("Couldn't delete: gone");
    });
  });
});
