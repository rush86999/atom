/**
 * TaskManagement Component Tests
 *
 * Tests verify the real TaskManagement wrapper
 * (components/TaskManagement.tsx) which fetches /api/v1/tasks and
 * /api/v1/projects and renders the shared TaskManagement board:
 * - loading state before data arrives
 * - tasks bucketed into the board columns with counts
 * - projects rendered with their task counts
 * - creating a task POSTs /api/v1/tasks, toasts, and appends the card
 * - marking a task complete PUTs { status: 'completed' }
 * - deleting a task DELETEs /api/v1/tasks/:id and removes the card
 * - fetch failure toasts "Error fetching data"
 *
 * API: GET/POST /api/v1/tasks, GET/DELETE /api/v1/tasks/:id,
 *      GET /api/v1/projects
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import TaskManagementWrapper from '../TaskManagement';

const tasks = [
  {
    id: 't-1',
    title: 'Write launch post',
    description: 'Draft the announcement',
    status: 'todo',
    priority: 'high',
    dueDate: '2026-08-20T00:00:00.000Z',
    createdAt: '2026-08-01T00:00:00.000Z',
    updatedAt: '2026-08-01T00:00:00.000Z',
    platform: 'local',
  },
  {
    id: 't-2',
    title: 'Fix login bug',
    description: 'Resolve auth error',
    status: 'in-progress',
    priority: 'medium',
    dueDate: '2026-08-25T00:00:00.000Z',
    createdAt: '2026-08-02T00:00:00.000Z',
    updatedAt: '2026-08-02T00:00:00.000Z',
    platform: 'local',
  },
  {
    id: 't-3',
    title: 'Deploy v1',
    status: 'completed',
    priority: 'low',
    dueDate: '2026-08-30T00:00:00.000Z',
    createdAt: '2026-08-03T00:00:00.000Z',
    updatedAt: '2026-08-03T00:00:00.000Z',
    platform: 'local',
  },
];

const projects = [
  {
    id: 'p-1',
    name: 'Website Launch',
    description: 'Marketing site',
    color: '#3182CE',
    progress: 40,
  },
];

describe('TaskManagement', () => {
  let postedBodies: any[];
  let updatedIds: string[];
  let deletedIds: string[];

  beforeEach(() => {
    jest.clearAllMocks();
    postedBodies = [];
    updatedIds = [];
    deletedIds = [];

    server.resetHandlers();
    server.use(
      rest.get('/api/v1/tasks', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ tasks }));
      }),
      rest.get('/api/v1/projects', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ projects }));
      }),
      rest.post('/api/v1/tasks', async (req, res, ctx) => {
        postedBodies.push(req.body);
        return res(
          ctx.status(201),
          ctx.json({
            task: {
              id: 't-new',
              title: (req.body as any)?.title,
              description: (req.body as any)?.description,
              status: (req.body as any)?.status,
              priority: (req.body as any)?.priority,
              dueDate: '2026-09-01T00:00:00.000Z',
              createdAt: '2026-08-07T00:00:00.000Z',
              updatedAt: '2026-08-07T00:00:00.000Z',
              platform: 'local',
            },
          })
        );
      }),
      rest.put('/api/v1/tasks/:id', async (req, res, ctx) => {
        updatedIds.push(String(req.params.id));
        return res(
          ctx.status(200),
          ctx.json({
            task: {
              id: String(req.params.id),
              title: 'Write launch post',
              status: 'completed',
              priority: 'high',
              dueDate: '2026-08-20T00:00:00.000Z',
              createdAt: '2026-08-01T00:00:00.000Z',
              updatedAt: '2026-08-07T00:00:00.000Z',
              platform: 'local',
            },
          })
        );
      }),
      rest.delete('/api/v1/tasks/:id', (req, res, ctx) => {
        deletedIds.push(String(req.params.id));
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );
  });

  it('shows the loading state before data arrives', () => {
    server.use(
      rest.get('/api/v1/tasks', (req, res, ctx) => {
        return res(ctx.delay(1000), ctx.json({ tasks }));
      })
    );
    render(<TaskManagementWrapper />);
    expect(screen.getByText('Loading tasks...')).toBeInTheDocument();
  });

  it('renders the board with tasks bucketed by status', async () => {
    render(<TaskManagementWrapper />);

    expect(await screen.findByText('Task Management')).toBeInTheDocument();
    expect(screen.getByText('3 tasks')).toBeInTheDocument();
    expect(screen.getAllByText('Write launch post').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Fix login bug').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Deploy v1')).toBeInTheDocument();
    expect(screen.getByText('TODO (1)')).toBeInTheDocument();
    expect(screen.getByText('IN PROGRESS (1)')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED (1)')).toBeInTheDocument();
    expect(screen.getByText('BLOCKED (0)')).toBeInTheDocument();
  });

  it('renders projects with their task counts', async () => {
    render(<TaskManagementWrapper />);

    expect(await screen.findByText('Website Launch')).toBeInTheDocument();
    expect(screen.getByText('Marketing site')).toBeInTheDocument();
    expect(screen.getByText(/0 tasks • 40% complete/)).toBeInTheDocument();
  });

  it('creates a task via the dialog, POSTs and appends it to the board', async () => {
    render(<TaskManagementWrapper />);
    await screen.findByText('Task Management');

    fireEvent.click(screen.getByTestId('new-task-btn'));
    await screen.findByRole('dialog');

    fireEvent.change(screen.getByTestId('task-title'), { target: { value: 'Ship docs' } });
    fireEvent.change(screen.getByPlaceholderText('Task description'), {
      target: { value: 'Write the manual' },
    });
    fireEvent.change(document.querySelector('input[type="date"]') as HTMLInputElement, {
      target: { value: '2026-09-15' },
    });
    fireEvent.click(screen.getByTestId('task-submit'));

    await waitFor(() => {
      expect(postedBodies).toHaveLength(1);
    });
    const body = postedBodies[0] as any;
    expect(body.title).toBe('Ship docs');
    expect(body.description).toBe('Write the manual');
    expect(body.status).toBe('todo');
    expect(body.priority).toBe('medium');

    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Task created' }));
    await waitFor(() => {
      expect(screen.getAllByText('Ship docs').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('4 tasks')).toBeInTheDocument();
  });

  it('marks a task complete via the check button and PUTs the update', async () => {
    render(<TaskManagementWrapper />);
    await screen.findAllByText('Write launch post');

    const todoCol = screen.getByText('TODO (1)').parentElement as HTMLElement;
    const completeBtn = todoCol.querySelector('button svg[class*="check"]')?.closest('button');
    expect(completeBtn).toBeTruthy();
    fireEvent.click(completeBtn as HTMLElement);

    await waitFor(() => {
      expect(updatedIds).toContain('t-1');
    });
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Task updated' }));
  });

  it('deletes a task and removes it from the board', async () => {
    render(<TaskManagementWrapper />);
    await screen.findAllByText('Write launch post');

    const upcomingRow = screen
      .getAllByText('Write launch post')
      .map((el) => el.closest('.flex.justify-between'))
      .find((el) => el && el.querySelector('svg.lucide-trash')) as HTMLElement;
    expect(upcomingRow).toBeTruthy();

    const deleteBtn = upcomingRow.querySelector('button svg.lucide-trash')?.closest('button');
    fireEvent.click(deleteBtn as HTMLElement);

    await waitFor(() => {
      expect(deletedIds).toContain('t-1');
    });
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Task deleted' }));
    expect(screen.queryByText('Write launch post')).not.toBeInTheDocument();
    expect(screen.getByText('2 tasks')).toBeInTheDocument();
  });

  it('toasts an error when the initial fetch fails', async () => {
    server.use(
      rest.get('/api/v1/tasks', (req, res, ctx) => {
        return res(ctx.status(500));
      }),
      rest.get('/api/v1/projects', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ projects }));
      })
    );

    render(<TaskManagementWrapper />);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Error fetching data' }));
    });
    expect(screen.getByText('Task Management')).toBeInTheDocument();
  });
});
