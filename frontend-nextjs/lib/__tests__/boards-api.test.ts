/**
 * boards-api Unit Tests
 *
 * Tests for the board/task API client functions in lib/boards-api.ts.
 * The apiClient.fetch adapter is mocked; responses are plain Response-shaped
 * objects ({ ok, status, json }).
 */

jest.mock('../api-client', () => ({
  apiClient: {
    fetch: jest.fn(),
  },
}));

import { apiClient } from '../api-client';
import {
  listBoards,
  getBoard,
  createBoard,
  listTasks,
  createTask,
  patchTask,
  deleteTask,
  proposeDecompose,
  commitDecompose,
  DecomposeNeedsKeyError,
  listComments,
  postComment,
} from '../boards-api';

const mockFetch = apiClient.fetch as jest.Mock;

const okResponse = (body: any, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: jest.fn().mockResolvedValue(body),
});

describe('boards-api', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('listBoards', () => {
    test('returns parsed boards on success', async () => {
      const boards = [{ id: 'b1', name: 'Board 1' }];
      mockFetch.mockResolvedValue(okResponse(boards));

      await expect(listBoards()).resolves.toEqual(boards);
      expect(mockFetch).toHaveBeenCalledWith('/api/boards');
    });

    test('throws when the response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 });

      await expect(listBoards()).rejects.toThrow('listBoards failed: 500');
    });
  });

  describe('getBoard', () => {
    test('returns board detail on success', async () => {
      const detail = { id: 'b1', columns: [] };
      mockFetch.mockResolvedValue(okResponse(detail));

      await expect(getBoard('b1')).resolves.toEqual(detail);
      expect(mockFetch).toHaveBeenCalledWith('/api/boards/b1');
    });

    test('throws when the response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 404 });

      await expect(getBoard('b1')).rejects.toThrow('getBoard failed: 404');
    });
  });

  describe('createBoard', () => {
    test('posts with seed_default_columns defaulted to true and merges input', async () => {
      const board = { id: 'b2', name: 'New Board' };
      mockFetch.mockResolvedValue(okResponse(board));

      await expect(createBoard({ name: 'New Board', description: 'd' })).resolves.toEqual(board);

      expect(mockFetch).toHaveBeenCalledWith('/api/boards', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ seed_default_columns: true, name: 'New Board', description: 'd' }),
      });
    });

    test('allows overriding seed_default_columns', async () => {
      mockFetch.mockResolvedValue(okResponse({ id: 'b2' }));

      await createBoard({ name: 'X', seed_default_columns: false });

      expect(JSON.parse(mockFetch.mock.calls[0][1].body).seed_default_columns).toBe(false);
    });

    test('throws when the response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 400 });

      await expect(createBoard({ name: 'X' })).rejects.toThrow('createBoard failed: 400');
    });
  });

  describe('listTasks', () => {
    test('lists tasks without a column filter', async () => {
      const tasks = [{ id: 't1' }];
      mockFetch.mockResolvedValue(okResponse(tasks));

      await expect(listTasks('b1')).resolves.toEqual(tasks);
      expect(mockFetch).toHaveBeenCalledWith('/api/boards/b1/tasks');
    });

    test('appends column_id query param when provided', async () => {
      mockFetch.mockResolvedValue(okResponse([]));

      await listTasks('b1', 'col-9');

      expect(mockFetch).toHaveBeenCalledWith('/api/boards/b1/tasks?column_id=col-9');
    });

    test('throws when the response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 });

      await expect(listTasks('b1')).rejects.toThrow('listTasks failed: 500');
    });
  });

  describe('createTask', () => {
    test('posts the task input', async () => {
      const task = { id: 't2' };
      const input = { title: 'Task', column_id: 'col-1' };
      mockFetch.mockResolvedValue(okResponse(task));

      await expect(createTask('b1', input)).resolves.toEqual(task);
      expect(mockFetch).toHaveBeenCalledWith('/api/boards/b1/tasks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      });
    });

    test('throws when the response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 422 });

      await expect(createTask('b1', { title: 'x', column_id: 'c' })).rejects.toThrow(
        'createTask failed: 422'
      );
    });
  });

  describe('patchTask', () => {
    test('returns the updated task with conflict=false on success', async () => {
      const task = { id: 't1', title: 'Updated' };
      mockFetch.mockResolvedValue(okResponse(task));

      const result = await patchTask('b1', 't1', { expected_version: 1, title: 'Updated' });

      expect(result).toEqual({ task, conflict: false });
    });

    test('returns conflict=true on 409', async () => {
      mockFetch.mockResolvedValue(okResponse({ error: 'conflict' }, 409));

      const result = await patchTask('b1', 't1', { expected_version: 0 });

      expect(result.conflict).toBe(true);
      expect(result.task).toEqual({ error: 'conflict' });
    });

    test('tolerates a non-JSON 409 body', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 409,
        json: jest.fn().mockRejectedValue(new Error('bad json')),
      });

      const result = await patchTask('b1', 't1', { expected_version: 0 });

      expect(result.conflict).toBe(true);
      expect(result.task).toEqual({});
    });

    test('throws on other error statuses', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 });

      await expect(patchTask('b1', 't1', { expected_version: 1 })).rejects.toThrow(
        'patchTask failed: 500'
      );
    });
  });

  describe('deleteTask', () => {
    test('resolves on 204 no content', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 204, json: jest.fn() });

      await expect(deleteTask('b1', 't1')).resolves.toBeUndefined();
    });

    test('resolves on 200', async () => {
      mockFetch.mockResolvedValue({ ok: true, status: 200, json: jest.fn() });

      await expect(deleteTask('b1', 't1')).resolves.toBeUndefined();
    });

    test('throws on error statuses other than 204', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 });

      await expect(deleteTask('b1', 't1')).rejects.toThrow('deleteTask failed: 500');
    });
  });

  describe('proposeDecompose', () => {
    test('returns the decompose preview on success', async () => {
      const preview = { parent_task_id: 't1', subtasks: [], depth: 1, max_depth: 3, rationale: '' };
      mockFetch.mockResolvedValue(okResponse(preview));

      await expect(proposeDecompose('b1', 't1')).resolves.toEqual(preview);
    });

    test('throws DecomposeNeedsKeyError on 424', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 424, json: jest.fn() });

      await expect(proposeDecompose('b1', 't1')).rejects.toBeInstanceOf(DecomposeNeedsKeyError);
      await expect(proposeDecompose('b1', 't1')).rejects.toThrow(
        'Task decomposition requires a tenant BYOK key'
      );
    });

    test('throws a generic error on other failures', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 });

      await expect(proposeDecompose('b1', 't1')).rejects.toThrow(
        'proposeDecompose failed: 500'
      );
    });
  });

  describe('commitDecompose', () => {
    test('commits with spawn_workspaces defaulting to false', async () => {
      const result = { parent_task_id: 't1', created_task_ids: ['s1'], spawned_workspaces: false };
      mockFetch.mockResolvedValue(okResponse(result));

      await expect(commitDecompose('b1', 't1', [{ title: 'Sub', column_name: 'Col' }])).resolves.toEqual(result);
      expect(mockFetch).toHaveBeenCalledWith('/api/boards/b1/tasks/t1/decompose/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposals: [{ title: 'Sub', column_name: 'Col' }],
          spawn_workspaces: false,
        }),
      });
    });

    test('honors spawnWorkspaces=true', async () => {
      mockFetch.mockResolvedValue(okResponse({}));

      await commitDecompose('b1', 't1', [], true);

      expect(JSON.parse(mockFetch.mock.calls[0][1].body).spawn_workspaces).toBe(true);
    });

    test('throws when the response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 });

      await expect(commitDecompose('b1', 't1', [])).rejects.toThrow(
        'commitDecompose failed: 500'
      );
    });
  });

  describe('listComments', () => {
    test('returns comments on success', async () => {
      const comments = [{ id: 'c1', content: 'hello' }];
      mockFetch.mockResolvedValue(okResponse(comments));

      await expect(listComments('b1', 't1')).resolves.toEqual(comments);
      expect(mockFetch).toHaveBeenCalledWith('/api/boards/b1/tasks/t1/comments');
    });

    test('throws when the response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 });

      await expect(listComments('b1', 't1')).rejects.toThrow('listComments failed: 500');
    });
  });

  describe('postComment', () => {
    test('posts a comment with parent_message_id when given', async () => {
      const comment = { id: 'c1', content: 'hi' };
      mockFetch.mockResolvedValue(okResponse(comment));

      await expect(postComment('b1', 't1', 'hi', 'p1')).resolves.toEqual(comment);
      expect(mockFetch).toHaveBeenCalledWith('/api/boards/b1/tasks/t1/comments', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: 'hi', parent_message_id: 'p1' }),
      });
    });

    test('omits parent_message_id when undefined', async () => {
      mockFetch.mockResolvedValue(okResponse({}));

      await postComment('b1', 't1', 'hi');

      expect(JSON.parse(mockFetch.mock.calls[0][1].body)).toEqual({ content: 'hi' });
    });

    test('throws when the response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500 });

      await expect(postComment('b1', 't1', 'hi')).rejects.toThrow('postComment failed: 500');
    });
  });
});
