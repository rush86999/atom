/**
 * KanbanBoard Component Tests
 *
 * Tests verify the real KanbanBoard component
 * (components/Projects/KanbanBoard.tsx):
 * - renders null until the Strict-Mode rAF gate fires, then the loading spinner
 * - loads tasks via GET /api/v1/tasks?platform=all and buckets them into the
 *   To Do / In Progress / Completed columns with per-column counts
 * - unknown statuses fall back into the To Do column
 * - search-free rendering of task cards (title, priority badge, assignee,
 *   due date)
 * - New Task dialog: creating a task POSTs /api/v1/tasks with the form
 *   payload, closes the dialog, toasts "Task created" and appends the card
 * - drag-end across columns PUTs /api/v1/tasks/:id with the new status and
 *   moves the card locally (react-beautiful-dnd is mocked; the component's
 *   real onDragEnd handler runs)
 * - failed status-update PUT shows the error toast
 *
 * API: GET /api/v1/tasks, POST /api/v1/tasks, PUT /api/v1/tasks/:id
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

// react-beautiful-dnd is mocked: DragDropContext captures the component's
// real onDragEnd handler; Droppable/Draggable render plain divs so the board
// layout is fully present in jsdom. The component's own drag logic (column
// moves, PUT) is what the tests exercise.
let capturedOnDragEnd: ((result: any) => void) | null = null;
jest.mock('react-beautiful-dnd', () => ({
  __esModule: true,
  DragDropContext: ({ children, onDragEnd }: any) => {
    capturedOnDragEnd = onDragEnd;
    return children;
  },
  Droppable: ({ children, droppableId }: any) =>
    children(
      {
        droppableProps: { 'data-droppable-id': droppableId },
        innerRef: jest.fn(),
        placeholder: null,
      },
      { isDraggingOver: false }
    ),
  Draggable: ({ children, draggableId }: any) =>
    children(
      {
        draggableProps: { 'data-draggable-id': draggableId },
        innerRef: jest.fn(),
        dragHandleProps: { 'data-testid': `drag-handle-${draggableId}` },
      },
      { isDragging: false }
    ),
}));

import KanbanBoard from '../KanbanBoard';

const tasksPayload = {
  success: true,
  tasks: [
    {
      id: 't-1',
      title: 'Design landing page',
      description: 'Mockup and copy for the landing page',
      status: 'todo',
      priority: 'high',
      dueDate: '2026-08-20T00:00:00.000Z',
      assignee: 'Rushi',
    },
    {
      id: 't-2',
      title: 'Implement auth flow',
      description: 'Wire up login and refresh tokens',
      status: 'in-progress',
      priority: 'medium',
    },
    {
      id: 't-3',
      title: 'Ship v1.0',
      description: 'Final release cut',
      status: 'completed',
      priority: 'low',
    },
    {
      id: 't-4',
      title: 'Mystery status task',
      description: 'Falls back to To Do',
      status: 'backlog',
      priority: 'low',
    },
  ],
};

describe('KanbanBoard', () => {
  let postedTasks: any[];
  let updatedTasks: { id: string; status: string }[];
  let tasksFetchCount: number;

  beforeEach(() => {
    jest.clearAllMocks();
    capturedOnDragEnd = null;
    postedTasks = [];
    updatedTasks = [];
    tasksFetchCount = 0;

    server.resetHandlers();
    server.use(
      rest.get('/api/v1/tasks', (req, res, ctx) => {
        tasksFetchCount += 1;
        return res(ctx.status(200), ctx.json(tasksPayload));
      }),
      rest.post('/api/v1/tasks', async (req, res, ctx) => {
        postedTasks.push(req.body);
        return res(ctx.status(201), ctx.json({ task: { id: 't-new' } }));
      }),
      rest.put('/api/v1/tasks/:id', async (req, res, ctx) => {
        updatedTasks.push({ id: String(req.params.id), status: (req.body as any)?.status });
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );
  });

  it('renders nothing until the rAF gate fires, then loads the board', async () => {
    render(<KanbanBoard />);
    expect(document.body.textContent).toBe('');

    expect(await screen.findByText('Project Board')).toBeInTheDocument();
    expect(tasksFetchCount).toBeGreaterThanOrEqual(1);
  });

  it('renders the board columns with counts and task cards', async () => {
    render(<KanbanBoard />);

    expect(await screen.findByText('Project Board')).toBeInTheDocument();
    expect(screen.getByText('To Do')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();
    expect(screen.getByText('Completed')).toBeInTheDocument();

    expect(screen.getByText('Design landing page')).toBeInTheDocument();
    expect(screen.getByText('Mockup and copy for the landing page')).toBeInTheDocument();
    expect(screen.getByText('Implement auth flow')).toBeInTheDocument();
    expect(screen.getByText('Ship v1.0')).toBeInTheDocument();

    const todoCol = screen.getByText('To Do').closest('div')!.parentElement as HTMLElement;
    expect(within(todoCol).getByText('2')).toBeInTheDocument();
  });

  it('buckets an unknown task status into the To Do column', async () => {
    render(<KanbanBoard />);
    expect(await screen.findByText('Mystery status task')).toBeInTheDocument();

    const todoCol = screen.getByText('To Do').closest('div')!.parentElement as HTMLElement;
    expect(within(todoCol).getByText('Mystery status task')).toBeInTheDocument();
  });

  it('renders priority badge, assignee badge and due date on task cards', async () => {
    render(<KanbanBoard />);

    expect(await screen.findByText('high')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
    expect(screen.getAllByText('low').length).toBe(2);
    expect(screen.getByText('Rushi')).toBeInTheDocument();

    const expectedDue = new Date('2026-08-20T00:00:00.000Z').toLocaleDateString();
    expect(screen.getByText(`Due: ${expectedDue}`)).toBeInTheDocument();
  });

  it('creates a task through the dialog and appends it to the board', async () => {
    render(<KanbanBoard />);
    await screen.findByText('Project Board');

    fireEvent.click(screen.getByRole('button', { name: /new task/i }));
    await screen.findByRole('dialog');

    fireEvent.change(screen.getByPlaceholderText('Task title'), {
      target: { value: 'Write docs' },
    });
    fireEvent.change(screen.getByPlaceholderText('Task details'), {
      target: { value: 'Document the API' },
    });
    fireEvent.click(screen.getByRole('button', { name: /create$/i }));

    await waitFor(() => {
      expect(postedTasks).toHaveLength(1);
    });
    const body = postedTasks[0] as any;
    expect(body.title).toBe('Write docs');
    expect(body.description).toBe('Document the API');
    expect(body.priority).toBe('medium');
    expect(body.status).toBe('todo');
    expect(typeof body.dueDate).toBe('string');

    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Task created' }));
    expect(await screen.findByText('Write docs')).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  it('cancels the new-task dialog without posting', async () => {
    render(<KanbanBoard />);
    await screen.findByText('Project Board');

    fireEvent.click(screen.getByRole('button', { name: /new task/i }));
    await screen.findByRole('dialog');
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(postedTasks).toHaveLength(0);
  });

  it('moves a card across columns on drag end and PUTs the new status', async () => {
    render(<KanbanBoard />);
    await screen.findByText('Project Board');
    expect(capturedOnDragEnd).toBeTruthy();

    capturedOnDragEnd!({
      source: { droppableId: 'todo', index: 0 },
      destination: { droppableId: 'completed', index: 0 },
    });

    await waitFor(() => {
      expect(updatedTasks).toHaveLength(1);
    });
    expect(updatedTasks[0]).toEqual({ id: 't-1', status: 'completed' });

    const completedCol = screen.getByText('Completed').closest('div')!.parentElement as HTMLElement;
    expect(within(completedCol).getByText('Design landing page')).toBeInTheDocument();
  });

  it('toasts a failure when the drag-end status PUT fails', async () => {
    server.use(
      rest.put('/api/v1/tasks/:id', (req, res, ctx) => {
        return res.networkError('boom');
      })
    );

    render(<KanbanBoard />);
    await screen.findByText('Project Board');

    capturedOnDragEnd!({
      source: { droppableId: 'todo', index: 0 },
      destination: { droppableId: 'in-progress', index: 0 },
    });

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Failed to update task status' })
      );
    });
  });

  it('does not call the API when drag ends without a destination', async () => {
    render(<KanbanBoard />);
    await screen.findByText('Project Board');

    capturedOnDragEnd!({
      source: { droppableId: 'todo', index: 0 },
      destination: null,
    });

    await new Promise((r) => setTimeout(r, 50));
    expect(updatedTasks).toHaveLength(0);
  });
});
