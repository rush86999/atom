/**
 * TaskDetailDrawer Component Tests (components/boards/TaskDetailDrawer.tsx)
 *
 * Tests verify the real TaskDetailDrawer component:
 * - renders nothing when no task is selected
 * - renders title/description inputs, status chip, and allowed next-status
 *   transition buttons from the STATUS_GRAPH
 * - status transition PATCHes the task with expected_version
 * - title/description blur only PATCHes when the value changed
 * - loads comments and posts new ones (Enter + button); empty comments are
 *   not posted
 * - Decompose with AI modal: proposes subtasks, lets you edit titles, and
 *   commits them; 424 surfaces the DecomposeNeedsKeyError message
 * - Delete task invokes the onDelete callback
 * - Create Workspace (CanvasWorkspacePanel) PATCHes with workspace: true
 *
 * APIs: GET/POST /api/boards/:boardId/tasks/:taskId/comments,
 *       PATCH /api/boards/:boardId/tasks/:taskId,
 *       POST /api/boards/:boardId/tasks/:taskId/decompose,
 *       POST /api/boards/:boardId/tasks/:taskId/decompose/commit
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type BoardTask } from '../../../lib/boards-api';

const mockToast = {
  success: jest.fn(),
  error: jest.fn(),
  info: jest.fn(),
  warning: jest.fn(),
  default: jest.fn(),
};
jest.mock('sonner', () => ({
  __esModule: true,
  default: mockToast,
  toast: mockToast,
}));

import { TaskDetailDrawer } from '../TaskDetailDrawer';

const boardId = 'b-1';

const task: BoardTask = {
  id: 't-1',
  board_id: boardId,
  column_id: 'col-todo',
  title: 'Fix login bug',
  description: 'Session token not refreshing',
  status: 'in_progress',
  priority: 'high',
  assignee_user_id: null,
  assignee_agent_id: null,
  parent_task_id: null,
  root_task_id: null,
  sort_order: 0,
  due_at: null,
  labels: [],
  metadata_json: {},
  created_by_user_id: null,
  canvas_id: null,
  version_id: 3,
  created_at: '2026-08-01T00:00:00.000Z',
  updated_at: '2026-08-01T00:00:00.000Z',
  canvas: null,
};

function renderDrawer(overrides?: { task?: BoardTask | null; open?: boolean }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const onClose = jest.fn();
  const onDelete = jest.fn();
  const utils = render(
    <QueryClientProvider client={qc}>
      <TaskDetailDrawer
        boardId={boardId}
        task={overrides?.task !== undefined ? overrides.task : task}
        open={overrides?.open !== undefined ? overrides.open : true}
        onClose={onClose}
        onDelete={onDelete}
      />
    </QueryClientProvider>
  );
  return { ...utils, onClose, onDelete };
}

const comment = (id: string, content: string, author: string): any => ({
  id,
  task_id: task.id,
  conversation_id: null,
  content,
  author: { user_id: author, agent_id: null, display_name: null },
  parent_message_id: null,
  created_at: '2026-08-07T10:00:00.000Z',
  replies: [],
});

describe('TaskDetailDrawer', () => {
  let patches: { id: string; input: any }[];
  let postedComments: { taskId: string; content: string }[];
  let proposeBodies: any[];
  let commitBodies: any[];

  beforeEach(() => {
    jest.clearAllMocks();
    patches = [];
    postedComments = [];
    proposeBodies = [];
    commitBodies = [];

    server.resetHandlers();
    server.use(
      rest.get(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/${task.id}/comments`, (req, res, ctx) =>
        res(ctx.status(200), ctx.json([comment('c1', 'Looking into it', 'alice')]))
      ),
      rest.post(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/${task.id}/comments`, async (req, res, ctx) => {
        postedComments.push({ taskId: "t-1", content: (req.body as any).content });
        return res(ctx.status(201), ctx.json(comment('c2', (req.body as any).content, 'bob')));
      }),
      rest.patch(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/:taskId`, async (req, res, ctx) => {
        patches.push({ id: String(req.params.taskId), input: req.body as any });
        return res(ctx.status(200), ctx.json({ ...task, ...(req.body as any) }));
      }),
      rest.post(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/${task.id}/decompose`, async (req, res, ctx) => {
        proposeBodies.push(req.body);
        return res(
          ctx.status(200),
          ctx.json({
            parent_task_id: task.id,
            rationale: 'Splits into smaller steps',
            subtasks: [
              { title: 'Reproduce bug', column_name: 'To Do', description: 'Write steps' },
              { title: 'Fix token refresh', column_name: 'To Do', description: null },
            ],
            depth: 1,
            max_depth: 3,
          })
        );
      }),
      rest.post(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/${task.id}/decompose/commit`, async (req, res, ctx) => {
        commitBodies.push(req.body);
        return res(
          ctx.status(200),
          ctx.json({ parent_task_id: task.id, created_task_ids: ['s1', 's2'], spawned_workspaces: false })
        );
      })
    );
  });

  it('renders nothing when no task is selected', () => {
    renderDrawer({ task: null });

    expect(document.body.textContent).toBe('');
  });

  it('renders the task title, description and status with allowed transitions', async () => {
    renderDrawer();

    expect(await screen.findByDisplayValue('Fix login bug')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Session token not refreshing')).toBeInTheDocument();

    // current status chip
    expect(screen.getByText('in_progress')).toBeInTheDocument();

    // in_progress → in_review, done, blocked, todo (STATUS_GRAPH)
    expect(screen.getByRole('button', { name: '→ in review' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '→ done' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '→ blocked' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '→ todo' })).toBeInTheDocument();
  });

  it('PATCHes the new status when a transition button is clicked', async () => {
    renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: '→ done' }));

    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0]).toEqual({
      id: 't-1',
      input: { expected_version: 3, status: 'done' },
    });
  });

  it('PATCHes the title on blur only when it changed', async () => {
    renderDrawer();
    const titleInput = await screen.findByDisplayValue('Fix login bug');

    // no change → no PATCH
    fireEvent.blur(titleInput);
    await new Promise((r) => setTimeout(r, 50));
    expect(patches).toHaveLength(0);

    fireEvent.change(titleInput, { target: { value: 'Fix login token bug' } });
    fireEvent.blur(titleInput);

    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0]).toEqual({
      id: 't-1',
      input: { expected_version: 3, title: 'Fix login token bug' },
    });
  });

  it('PATCHes the description on blur', async () => {
    renderDrawer();
    const descInput = await screen.findByDisplayValue('Session token not refreshing');

    fireEvent.change(descInput, { target: { value: 'Token expiry race' } });
    fireEvent.blur(descInput);

    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0].input.description).toBe('Token expiry race');
  });

  it('loads and renders existing comments', async () => {
    renderDrawer();

    expect(await screen.findByText('Looking into it')).toBeInTheDocument();
    expect(screen.getByText('alice')).toBeInTheDocument();
    expect(screen.getByText('Comments (1)')).toBeInTheDocument();
  });

  it('posts a comment via the button and appends it to the list', async () => {
    renderDrawer();
    await screen.findByText('Looking into it');

    fireEvent.change(screen.getByPlaceholderText('Add a comment…'), {
      target: { value: 'Fixed in next release' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post comment' }));

    await waitFor(() => expect(postedComments).toHaveLength(1));
    expect(postedComments[0]).toEqual({ taskId: 't-1', content: 'Fixed in next release' });

    expect(await screen.findByText('Fixed in next release')).toBeInTheDocument();
    expect(screen.getByText('Comments (2)')).toBeInTheDocument();
  });

  it('posts a comment with the Enter key but not for empty input', async () => {
    renderDrawer();
    await screen.findByText('Looking into it');

    const input = screen.getByPlaceholderText('Add a comment…');

    // empty / whitespace → no post
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await new Promise((r) => setTimeout(r, 50));
    expect(postedComments).toHaveLength(0);

    fireEvent.change(input, { target: { value: 'Enter-posted comment' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => expect(postedComments).toHaveLength(1));
    expect(postedComments[0].content).toBe('Enter-posted comment');
  });

  it('toasts an error when posting a comment fails', async () => {
    server.use(
      rest.post(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/${task.id}/comments`, (req, res, ctx) =>
        res.networkError('boom')
      )
    );

    renderDrawer();
    await screen.findByText('Looking into it');

    fireEvent.change(screen.getByPlaceholderText('Add a comment…'), {
      target: { value: 'Doomed' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Post comment' }));

    await waitFor(() => {
      expect(mockToast.error).toHaveBeenCalledWith(
        expect.stringContaining("Couldn't post comment:")
      );
    });
  });

  it('decomposes a task: proposes subtasks, edits a title, and commits', async () => {
    renderDrawer();

    fireEvent.click(await screen.findByText('Decompose with AI'));

    expect(await screen.findByText('Decompose: Fix login bug')).toBeInTheDocument();
    expect(await screen.findByText('Splits into smaller steps')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Reproduce bug')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Fix token refresh')).toBeInTheDocument();

    // edit a subtask title before committing
    fireEvent.change(screen.getByDisplayValue('Reproduce bug'), {
      target: { value: 'Reproduce in staging' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create 2 subtasks' }));

    await waitFor(() => expect(commitBodies).toHaveLength(1));
    expect(proposeBodies).toHaveLength(1);
    expect(commitBodies[0]).toEqual({
      proposals: [
        { title: 'Reproduce in staging', column_name: 'To Do', description: 'Write steps' },
        { title: 'Fix token refresh', column_name: 'To Do', description: undefined },
      ],
      spawn_workspaces: false,
    });

    expect(mockToast.success).toHaveBeenCalledWith('Created 2 subtasks');
    await waitFor(() => {
      expect(screen.queryByText('Decompose: Fix login bug')).not.toBeInTheDocument();
    });
  });

  it('surfaces the BYOK key error when decompose returns 424', async () => {
    server.use(
      rest.post(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/${task.id}/decompose`, (req, res, ctx) =>
        res(ctx.status(424), ctx.json({}))
      )
    );

    renderDrawer();

    fireEvent.click(await screen.findByText('Decompose with AI'));

    expect(
      await screen.findByText(/requires a tenant BYOK key/i)
    ).toBeInTheDocument();
  });

  it('calls onDelete when Delete task is clicked', async () => {
    const { onDelete } = renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: /delete task/i }));

    expect(onDelete).toHaveBeenCalledWith(task);
  });

  it('calls onClose when the X button is clicked', async () => {
    const { onClose } = renderDrawer();

    fireEvent.click(await screen.findByRole('button', { name: 'Close' }));

    expect(onClose).toHaveBeenCalled();
  });

  it('renders the drawer translated off-screen when closed', () => {
    renderDrawer({ open: false });

    const drawer = document.querySelector('[role="dialog"]')!;
    expect(drawer.className).toContain('translate-x-full');
  });

  it('creates a task workspace from the CanvasWorkspacePanel (workspace: true)', async () => {
    renderDrawer();

    expect(await screen.findByText('Task workspace')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Create Workspace' }));

    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0].input).toEqual({ expected_version: 3, workspace: true });
  });
});
