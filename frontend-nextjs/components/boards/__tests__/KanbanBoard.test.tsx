/**
 * KanbanBoard Component Tests (components/boards/KanbanBoard.tsx)
 *
 * Tests verify the real KanbanBoard component:
 * - shows "Loading board…" until /api/boards/:id/tasks resolves, then renders
 *   board name + columns with per-column counts (via react-query + MSW)
 * - tasks are bucketed into columns by column_id and sorted by sort_order
 * - clicking a task card opens the TaskDetailDrawer (real) with the task
 *   title and its comments loaded
 * - add-task button prompts for a title and POSTs /api/boards/:id/tasks;
 *   whitespace-only titles are rejected (BUG-128)
 * - drag-end across columns PATCHes the task with the new column_id and the
 *   task's expected_version (real onDragEnd captured from DndContext)
 * - same-column reorder swaps sort_orders with two sequential PATCHes
 * - the drawer can move a task to another column without pointer drag,
 *   showing pending/failure states and reading the updated task afterward
 * - a move that resolves after switching tasks does not affect the new task
 * - drawers rendered without column metadata never expose raw column ids
 * - drag end without a destination does nothing
 * - deleting a task from the drawer DELETEs it, toasts, and closes the drawer
 *
 * APIs: GET/POST /api/boards/:boardId/tasks,
 *       PATCH /api/boards/:boardId/tasks/:taskId,
 *       DELETE /api/boards/:boardId/tasks/:taskId,
 *       GET /api/boards/:boardId/tasks/:taskId/comments
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type BoardColumn, type BoardTask } from '../../../lib/boards-api';

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

// dnd-kit mocks: capture the board's real onDragEnd; render plain containers.
let capturedOnDragEnd: ((event: any) => void) | null = null;
jest.mock('@dnd-kit/core', () => ({
  DndContext: ({ children, onDragEnd }: any) => {
    capturedOnDragEnd = onDragEnd;
    return <div data-testid="dnd-context">{children}</div>;
  },
  PointerSensor: class {},
  useSensor: (sensor: any) => sensor,
  useSensors: (...sensors: any[]) => sensors,
  useDroppable: () => ({ setNodeRef: () => {}, isOver: false }),
}));

jest.mock('@dnd-kit/sortable', () => ({
  SortableContext: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  verticalListSortingStrategy: {},
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: () => {},
    transform: null,
    transition: null,
    isDragging: false,
  }),
}));

jest.mock('@dnd-kit/utilities', () => ({
  CSS: { Transform: { toString: () => '' } },
}));

import { KanbanBoard } from '../KanbanBoard';
import { TaskDetailDrawer } from '../TaskDetailDrawer';

const boardId = 'b-1';

const columns: BoardColumn[] = [
  { id: 'col-todo', board_id: boardId, name: 'To Do', position: 0, wip_limit: null, version_id: 1, task_count: 2 },
  { id: 'col-done', board_id: boardId, name: 'Done', position: 1, wip_limit: null, version_id: 1, task_count: 1 },
];

const board = {
  id: boardId,
  name: 'Sprint Board',
  slug: null,
  description: 'The main sprint board',
  owner_user_id: null,
  archived_at: null,
  version_id: 1,
  created_at: '2026-08-01T00:00:00.000Z',
  updated_at: '2026-08-01T00:00:00.000Z',
  columns,
};

const makeTask = (overrides: Partial<BoardTask>): BoardTask => ({
  id: 't-1',
  board_id: boardId,
  column_id: 'col-todo',
  title: 'Task one',
  description: null,
  status: 'todo',
  priority: 'normal',
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
  version_id: 1,
  created_at: '2026-08-01T00:00:00.000Z',
  updated_at: '2026-08-01T00:00:00.000Z',
  canvas: null,
  ...overrides,
});

const tasksPayload: BoardTask[] = [
  makeTask({ id: 't-1', title: 'Design landing page', column_id: 'col-todo', sort_order: 0 }),
  makeTask({ id: 't-2', title: 'Write copy', column_id: 'col-todo', sort_order: 1 }),
  makeTask({ id: 't-3', title: 'Ship v1.0', column_id: 'col-done', sort_order: 0 }),
];

function renderBoard(boardOverride: typeof board = board) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <KanbanBoard board={boardOverride} />
    </QueryClientProvider>
  );
}

describe('KanbanBoard', () => {
  let patches: { id: string; input: any }[];
  let creates: { title: string; column_id: string }[];
  // One PATCH handler is installed for every test. Per-test behavior is
  // selected with patchMode/patchGate instead of layering server.use overrides.
  let patchMode: 'success' | 'fail';
  let patchGate: Promise<void> | null;
  let releasePatch: (() => void) | null;
  beforeEach(() => {
    jest.clearAllMocks();
    capturedOnDragEnd = null;
    patches = [];
    creates = [];
    patchMode = 'success';
    patchGate = null;
    releasePatch = null;

    server.resetHandlers();
    server.use(
      rest.get(`http://127.0.0.1:8000/api/boards/${boardId}/tasks`, (req, res, ctx) =>
        res(ctx.status(200), ctx.json(tasksPayload))
      ),
      rest.post(`http://127.0.0.1:8000/api/boards/${boardId}/tasks`, async (req, res, ctx) => {
        creates.push(req.body as any);
        return res(ctx.status(201), ctx.json(makeTask({ id: 't-new', ...(req.body as any) })));
      }),
      rest.patch(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/:taskId`, async (req, res, ctx) => {
        patches.push({ id: String(req.params.taskId), input: req.body as any });
        if (patchGate) {
          await patchGate;
        }
        if (patchMode === 'fail') {
          return res(ctx.status(400), ctx.json({ detail: 'Move rejected' }));
        }
        const orig = tasksPayload.find((t) => t.id === String(req.params.taskId))!;
        return res(ctx.status(200), ctx.json({ ...orig, ...(req.body as any) }));
      }),
      rest.delete(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/:taskId`, (req, res, ctx) =>
        res(ctx.status(204))
      ),
      rest.get(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/:taskId/comments`, (req, res, ctx) =>
        res(ctx.status(200), ctx.json([]))
      ),
      rest.post(`http://127.0.0.1:8000/api/boards/${boardId}/tasks/:taskId/comments`, async (req, res, ctx) =>
        res(ctx.status(201), ctx.json({}))
      )
    );
  });

  it('renders loading state then the board with columns and bucketed tasks', async () => {
    renderBoard();

    expect(screen.getByText('Loading board…')).toBeInTheDocument();

    expect(await screen.findByText('Sprint Board')).toBeInTheDocument();
    expect(screen.getByText('The main sprint board')).toBeInTheDocument();

    expect(screen.getByText('To Do')).toBeInTheDocument();
    expect(screen.getByText('Done')).toBeInTheDocument();

    expect(screen.getByText('Design landing page')).toBeInTheDocument();
    expect(screen.getByText('Write copy')).toBeInTheDocument();
    expect(screen.getByText('Ship v1.0')).toBeInTheDocument();

    // per-column count badges
    const todoCol = screen.getByText('To Do').closest('div')!.parentElement as HTMLElement;
    expect(within(todoCol).getByText('2')).toBeInTheDocument();
    const doneCol = screen.getByText('Done').closest('div')!.parentElement as HTMLElement;
    expect(within(doneCol).getByText('1')).toBeInTheDocument();
  });

  it('renders an empty column with the drop placeholder', async () => {
    server.use(
      rest.get(`http://127.0.0.1:8000/api/boards/${boardId}/tasks`, (req, res, ctx) =>
        res(ctx.status(200), ctx.json([]))
      )
    );

    renderBoard();

    expect(await screen.findByText('Sprint Board')).toBeInTheDocument();
    expect(screen.getAllByText('Drop tasks here')).toHaveLength(2);
  });

  it('opens the task drawer when a task card is clicked', async () => {
    renderBoard();
    await screen.findByText('Design landing page');

    fireEvent.click(screen.getByText('Design landing page'));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveAttribute('aria-label', 'Task: Design landing page');
    // drawer input holds the task title; comments section shows empty state
    expect(within(dialog).getByDisplayValue('Design landing page')).toBeInTheDocument();
    expect(await within(dialog).findByText('No comments yet.')).toBeInTheDocument();
  });

  it('closes the drawer with the X button', async () => {
    renderBoard();
    await screen.findByText('Design landing page');

    fireEvent.click(screen.getByText('Design landing page'));
    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('creates a task via prompt and POSTs it to the board', async () => {
    const promptSpy = jest.spyOn(window, 'prompt').mockReturnValue('New task title');
    renderBoard();
    await screen.findByText('Sprint Board');

    fireEvent.click(screen.getByRole('button', { name: 'Add task to To Do' }));

    await waitFor(() => expect(creates).toHaveLength(1));
    expect(creates[0]).toEqual({ title: 'New task title', column_id: 'col-todo' });

    promptSpy.mockRestore();
  });

  it('rejects whitespace-only prompt titles (BUG-128)', async () => {
    const promptSpy = jest.spyOn(window, 'prompt').mockReturnValue('   ');
    renderBoard();
    await screen.findByText('Sprint Board');

    fireEvent.click(screen.getByRole('button', { name: 'Add task to To Do' }));

    await new Promise((r) => setTimeout(r, 100));
    expect(creates).toHaveLength(0);

    promptSpy.mockRestore();
  });

  it('does not POST when the prompt is cancelled', async () => {
    const promptSpy = jest.spyOn(window, 'prompt').mockReturnValue(null);
    renderBoard();
    await screen.findByText('Sprint Board');

    fireEvent.click(screen.getByRole('button', { name: 'Add task to To Do' }));

    await new Promise((r) => setTimeout(r, 100));
    expect(creates).toHaveLength(0);

    promptSpy.mockRestore();
  });

  it('moves a task across columns on drag end with the expected_version', async () => {
    renderBoard();
    await screen.findByText('Design landing page');
    expect(capturedOnDragEnd).toBeTruthy();

    act(() => {
      capturedOnDragEnd!({
        active: { id: 't-1' },
        over: { id: 'column-col-done' },
      });
    });

    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0]).toEqual({
      id: 't-1',
      input: { expected_version: 1, column_id: 'col-done' },
    });
  });

  it('reorders within a column with two sequential swap PATCHes', async () => {
    renderBoard();
    await screen.findByText('Design landing page');

    act(() => {
      capturedOnDragEnd!({
        active: { id: 't-1' },
        over: { id: 't-2' },
      });
    });

    await waitFor(() => expect(patches).toHaveLength(2));
    expect(patches[0]).toEqual({
      id: 't-1',
      input: { expected_version: 1, sort_order: 1 },
    });
    expect(patches[1]).toEqual({
      id: 't-2',
      input: { expected_version: 1, sort_order: 0 },
    });
  });

  it('moves a task between columns from the drawer with the expected_version', async () => {
    renderBoard();
    await screen.findByText('Design landing page');

    fireEvent.click(screen.getByText('Design landing page'));
    const dialog = await screen.findByRole('dialog');
    const currentColumn = within(dialog).getByLabelText('Current column: To Do');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Move to Done' }));

    await waitFor(() => expect(patches).toHaveLength(1));
    expect(patches[0]).toEqual({
      id: 't-1',
      input: { expected_version: 1, column_id: 'col-done' },
    });

    // The drawer uses the updated task from the query cache, not the snapshot
    // captured when it was opened.
    await waitFor(() => {
      expect(within(dialog).getByRole('button', { name: 'Move to To Do' })).toBeInTheDocument();
    });
    expect(within(dialog).queryByRole('button', { name: 'Move to Done' })).not.toBeInTheDocument();

    // The destination button disappeared, so focus moved to the stable
    // current-column label inside the drawer instead of falling to <body>.
    expect(currentColumn).toHaveAttribute('aria-label', 'Current column: Done');
    await waitFor(() => expect(currentColumn).toHaveFocus());
  });

  it('keeps the destination visible and disables moves while a drawer move is in flight', async () => {
    patchGate = new Promise<void>((resolve) => {
      releasePatch = () => resolve();
    });

    const boardWithReview = {
      ...board,
      columns: [
        ...columns,
        { id: 'col-review', board_id: boardId, name: 'In Review', position: 2, wip_limit: null, version_id: 1, task_count: 0 },
      ],
    };

    renderBoard(boardWithReview);
    await screen.findByText('Design landing page');

    fireEvent.click(screen.getByText('Design landing page'));
    const dialog = await screen.findByRole('dialog');
    const currentColumn = within(dialog).getByLabelText('Current column: To Do');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Move to Done' }));

    expect(await within(dialog).findByRole('status')).toHaveTextContent('Moving to Done');
    // The optimistic cache has already moved the task, but the requested
    // destination must remain rendered and busy for the whole request.
    const moveButton = within(dialog).getByRole('button', { name: 'Move to Done' });
    expect(moveButton).toBeDisabled();
    expect(moveButton).toHaveAttribute('aria-busy', 'true');
    expect(within(dialog).getByRole('button', { name: 'Move to In Review' })).toBeDisabled();
    expect(currentColumn).toHaveAttribute('aria-label', 'Current column: To Do');
    expect(currentColumn).toHaveFocus();

    await waitFor(() => expect(releasePatch).not.toBeNull());
    act(() => releasePatch!());

    await waitFor(() => {
      expect(within(dialog).getByRole('button', { name: 'Move to To Do' })).toBeInTheDocument();
    });
    expect(within(dialog).queryByRole('status')).not.toBeInTheDocument();
    expect(currentColumn).toHaveAttribute('aria-label', 'Current column: Done');
    await waitFor(() => expect(currentColumn).toHaveFocus());
  });

  it('reports a failed drawer move and restores the task to its original column', async () => {
    patchMode = 'fail';

    renderBoard();
    await screen.findByText('Design landing page');

    fireEvent.click(screen.getByText('Design landing page'));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Move to Done' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent("Couldn't move task");
    expect(mockToast.error).toHaveBeenCalledWith(expect.stringContaining("Couldn't save"));

    await waitFor(() => {
      expect(within(dialog).getByRole('button', { name: 'Move to Done' })).toBeEnabled();
      expect(within(dialog).queryByRole('button', { name: 'Move to To Do' })).not.toBeInTheDocument();
      expect(within(dialog).getByLabelText('Current column: To Do')).toBeInTheDocument();
    });
  });

  it('ignores a drawer move that finishes after switching tasks', async () => {
    patchGate = new Promise<void>((resolve) => {
      releasePatch = () => resolve();
    });

    renderBoard();
    await screen.findByText('Design landing page');

    fireEvent.click(screen.getByText('Design landing page'));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Move to Done' }));
    expect(await within(dialog).findByRole('status')).toHaveTextContent('Moving to Done');

    fireEvent.click(screen.getByText('Write copy'));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Task: Write copy');
    });
    const switchedDialog = screen.getByRole('dialog');

    // Fail the old task's in-flight request only after the drawer has switched.
    // The hook-level toast proves the old mutation settled; the new task must
    // not inherit its alert or lose its own state.
    patchMode = 'fail';
    await waitFor(() => expect(releasePatch).not.toBeNull());
    act(() => releasePatch!());
    await waitFor(() =>
      expect(mockToast.error).toHaveBeenCalledWith(expect.stringContaining("Couldn't save"))
    );

    // The stale callback must not clear or report state on the new task.
    await waitFor(() => {
      expect(within(switchedDialog).queryByRole('status')).not.toBeInTheDocument();
      expect(within(switchedDialog).queryByRole('alert')).not.toBeInTheDocument();
    });
    expect(within(switchedDialog).getByRole('button', { name: 'Move to Done' })).toBeEnabled();
  });

  it('does not expose raw column ids when column metadata is omitted', async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    render(
      <QueryClientProvider client={qc}>
        <TaskDetailDrawer
          boardId={boardId}
          task={tasksPayload[0]}
          open
          onClose={() => {}}
          onDelete={() => {}}
        />
      </QueryClientProvider>
    );

    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByLabelText('Current column: Unknown column')).toBeInTheDocument();
    expect(within(dialog).queryByText('col-todo')).not.toBeInTheDocument();
    expect(within(dialog).queryByRole('button', { name: /^Move to / })).not.toBeInTheDocument();
  });

  it('does nothing when drag ends without a destination', async () => {
    renderBoard();
    await screen.findByText('Design landing page');

    act(() => {
      capturedOnDragEnd!({ active: { id: 't-1' }, over: null });
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(patches).toHaveLength(0);
  });

  it('does nothing when dragging an unknown task id', async () => {
    renderBoard();
    await screen.findByText('Design landing page');

    act(() => {
      capturedOnDragEnd!({ active: { id: 'ghost' }, over: { id: 'column-col-done' } });
    });

    await new Promise((r) => setTimeout(r, 100));
    expect(patches).toHaveLength(0);
  });

  it('deletes a task from the drawer, toasts, and closes the drawer', async () => {
    renderBoard();
    await screen.findByText('Design landing page');

    fireEvent.click(screen.getByText('Design landing page'));
    await screen.findByRole('dialog');

    fireEvent.click(screen.getByRole('button', { name: /delete task/i }));

    await waitFor(() => {
      expect(mockToast.success).toHaveBeenCalledWith('Task deleted');
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });
});
