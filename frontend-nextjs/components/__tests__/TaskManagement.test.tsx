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

// Upcoming Tasks only shows tasks with dueDate > now — keep fixtures future-dated
// (a fixed date turns into a stale fixture that silently breaks the suite).
const DAY = 24 * 60 * 60 * 1000;
const future = (days: number) => new Date(Date.now() + days * DAY).toISOString();

const tasks = [
  {
    id: 't-1',
    title: 'Write launch post',
    description: 'Draft the announcement',
    status: 'todo',
    priority: 'high',
    dueDate: future(5),
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
    dueDate: future(10),
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
  let postedProjectBodies: any[];
  let updatedProjectIds: string[];

  beforeEach(() => {
    jest.clearAllMocks();
    postedBodies = [];
    updatedIds = [];
    deletedIds = [];
    postedProjectBodies = [];
    updatedProjectIds = [];

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
              title: (req.body as any)?.title ?? 'Write launch post',
              status: (req.body as any)?.status ?? 'todo',
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
      }),
      rest.post('/api/v1/projects', async (req, res, ctx) => {
        postedProjectBodies.push(req.body);
        return res(
          ctx.status(201),
          ctx.json({
            project: {
              id: 'p-new',
              name: (req.body as any)?.name,
              description: (req.body as any)?.description,
              color: (req.body as any)?.color,
              progress: 0,
            },
          })
        );
      }),
      rest.put('/api/v1/projects/:id', async (req, res, ctx) => {
        updatedProjectIds.push(String(req.params.id));
        return res(
          ctx.status(200),
          ctx.json({
            project: {
              id: String(req.params.id),
              name: (req.body as any)?.name ?? 'Website Launch',
              description: (req.body as any)?.description ?? 'Marketing site',
              color: (req.body as any)?.color ?? '#3182CE',
              progress: 40,
            },
          })
        );
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

  it('edits a task via the dialog and PUTs the update', async () => {
    render(<TaskManagementWrapper />);
    await screen.findAllByText('Write launch post');

    fireEvent.click(screen.getAllByText('Write launch post')[0].closest('.cursor-pointer') as HTMLElement);
    await screen.findByRole('dialog');
    expect(screen.getByText('Edit Task')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('task-title'), { target: { value: 'Rewrite launch post' } });
    fireEvent.click(screen.getByTestId('task-submit'));

    await waitFor(() => {
      expect(updatedIds).toContain('t-1');
    });
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Task updated' }));
    await waitFor(() => {
      expect(screen.getAllByText('Rewrite launch post').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('creates a project via the dialog, POSTs and shows it', async () => {
    render(<TaskManagementWrapper />);
    await screen.findByText('Task Management');

    fireEvent.click(screen.getByRole('button', { name: /new project/i }));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByPlaceholderText('Project name'), { target: { value: 'Q4 Rebrand' } });
    fireEvent.change(screen.getByPlaceholderText('Project description'), {
      target: { value: 'Brand refresh' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Create Project' }));

    await waitFor(() => {
      expect(postedProjectBodies).toHaveLength(1);
    });
    expect((postedProjectBodies[0] as any).name).toBe('Q4 Rebrand');
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Project created' }));
    await waitFor(() => {
      expect(screen.getAllByText('Q4 Rebrand').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText(/0 tasks • 0% complete/)).toBeInTheDocument();
  });

  it('edits a project via the project card and PUTs the update', async () => {
    render(<TaskManagementWrapper />);
    await screen.findByText('Website Launch');

    fireEvent.click(screen.getByText('Website Launch').closest('.cursor-pointer') as HTMLElement);
    await screen.findByRole('dialog');
    expect(screen.getByText('Edit Project')).toBeInTheDocument();
    expect((screen.getByPlaceholderText('Project name') as HTMLInputElement).value).toBe(
      'Website Launch',
    );

    fireEvent.change(screen.getByPlaceholderText('Project name'), { target: { value: 'Rebrand 2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'Update Project' }));

    await waitFor(() => {
      expect(updatedProjectIds).toContain('p-1');
    });
    expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Project updated' }));
    await waitFor(() => {
      expect(screen.getAllByText('Rebrand 2026').length).toBeGreaterThanOrEqual(1);
    });
  });

  it('toasts failure when task creation fails', async () => {
    server.use(
      rest.post('/api/v1/tasks', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );
    render(<TaskManagementWrapper />);
    await screen.findByText('Task Management');

    fireEvent.click(screen.getByTestId('new-task-btn'));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByTestId('task-title'), { target: { value: 'Doomed' } });
    fireEvent.change(document.querySelector('input[type="date"]') as HTMLInputElement, {
      target: { value: '2026-12-01' },
    });
    fireEvent.click(screen.getByTestId('task-submit'));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Failed to create task' }));
    });
  });

  it('toasts failure when task update fails', async () => {
    server.use(
      rest.put('/api/v1/tasks/:id', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );
    render(<TaskManagementWrapper />);
    await screen.findAllByText('Write launch post');

    const todoCol = screen.getByText('TODO (1)').parentElement as HTMLElement;
    const completeBtn = todoCol.querySelector('button svg[class*="check"]')?.closest('button');
    fireEvent.click(completeBtn as HTMLElement);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Failed to update task' }));
    });
  });

  it('toasts failure when task deletion fails', async () => {
    server.use(
      rest.delete('/api/v1/tasks/:id', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );
    render(<TaskManagementWrapper />);
    await screen.findAllByText('Write launch post');

    const upcomingRow = screen
      .getAllByText('Write launch post')
      .map((el) => el.closest('.flex.justify-between'))
      .find((el) => el && el.querySelector('svg.lucide-trash')) as HTMLElement;
    const deleteBtn = upcomingRow.querySelector('button svg.lucide-trash')?.closest('button');
    fireEvent.click(deleteBtn as HTMLElement);

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Failed to delete task' }));
    });
  });

  it('toasts failure when project creation fails', async () => {
    server.use(
      rest.post('/api/v1/projects', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );
    render(<TaskManagementWrapper />);
    await screen.findByText('Task Management');

    fireEvent.click(screen.getByRole('button', { name: /new project/i }));
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByPlaceholderText('Project name'), { target: { value: 'Doomed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create Project' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Failed to create project' }));
    });
  });

  it('toasts failure when project update fails', async () => {
    server.use(
      rest.put('/api/v1/projects/:id', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );
    render(<TaskManagementWrapper />);
    await screen.findByText('Website Launch');

    fireEvent.click(screen.getByText('Website Launch').closest('.cursor-pointer') as HTMLElement);
    await screen.findByRole('dialog');
    fireEvent.change(screen.getByPlaceholderText('Project name'), { target: { value: 'Doomed' } });
    fireEvent.click(screen.getByRole('button', { name: 'Update Project' }));

    await waitFor(() => {
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Failed to update project' }));
    });
  });
});
