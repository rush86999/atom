/**
 * Dashboard Component Tests
 *
 * Tests verify the real Dashboard component (components/Dashboard.tsx):
 * - Fetches GET /api/dashboard-dev (response is the data object directly)
 * - Loading / loaded / error states
 * - Stats overview cards
 * - Calendar, tasks, and messages widgets
 * - Overview vs Workflow Automation tabs
 * - Refresh button refetches and shows a refreshing state
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 * The project's custom Tabs renders plain <button> triggers (no role="tab").
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import Dashboard from '@/components/Dashboard';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// Stable useToast mock so handler/toast identities never churn between renders.
const mockToast = { toast: jest.fn(), dismiss: jest.fn(), toasts: [] };
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => mockToast,
  ToastProvider: ({ children }: { children: any }) => children,
}));

// WorkflowAutomation is heavy; the real Dashboard renders it in the
// "Workflow Automation" tab. Replace it with a lightweight stub.
jest.mock('@/components/WorkflowAutomation', () => {
  return function MockWorkflowAutomation() {
    return <div data-testid="workflow-automation">Workflow Automation</div>;
  };
});

// The ui/spinner module references React without importing it, which throws
// "React is not defined" in the test runtime whenever the loading state
// renders the real Spinner. Mock it to a plain div so the Dashboard's own
// "Loading your dashboard..." label can still be asserted.
jest.mock('@/components/ui/spinner', () => ({
  Spinner: ({ className }: { className?: string }) => (
    <div data-testid="spinner" className={className} />
  ),
}));

const emptyData = {
  calendar: [],
  tasks: [],
  messages: [],
  stats: {
    upcomingEvents: 0,
    overdueTasks: 0,
    unreadMessages: 0,
    completedTasks: 0,
  },
};

const richData = {
  calendar: [
    {
      id: '1',
      title: 'Team Meeting',
      start: '2026-03-10T10:00:00',
      end: '2026-03-10T11:00:00',
      status: 'confirmed',
      location: 'Room 1',
    },
  ],
  tasks: [
    {
      id: '1',
      title: 'Complete Project',
      dueDate: '2026-03-11',
      priority: 'high',
      status: 'todo',
    },
  ],
  messages: [
    {
      id: '1',
      platform: 'email',
      from: 'john@example.com',
      subject: 'Project Update',
      preview: 'Here is the update...',
      timestamp: '2026-03-09T09:00:00',
      unread: true,
      priority: 'normal',
    },
  ],
  stats: {
    upcomingEvents: 5,
    overdueTasks: 2,
    unreadMessages: 10,
    completedTasks: 15,
  },
};

const defaultHandlers = [
  rest.get('/api/dashboard-dev', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(emptyData));
  }),
];

describe('Dashboard Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...defaultHandlers);
  });

  // Test 1: renders the dashboard header without crashing
  test('renders dashboard without crashing', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /atom agent dashboard/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: displays calendar, task, and message widgets
  test('displays dashboard widgets', async () => {
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json(richData));
      })
    );

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('Team Meeting')).toBeInTheDocument();
      expect(screen.getByText('Complete Project')).toBeInTheDocument();
      expect(screen.getByText('Project Update')).toBeInTheDocument();
      expect(screen.getByText("Today's Calendar")).toBeInTheDocument();
    });
  });

  // Test 3: displays the stats cards
  test('displays stats cards', async () => {
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json(richData));
      })
    );

    render(<Dashboard />);

    await waitFor(() => {
      expect(screen.getByText('5')).toBeInTheDocument(); // upcoming events
      expect(screen.getByText('2')).toBeInTheDocument(); // overdue tasks
      expect(screen.getByText('10')).toBeInTheDocument(); // unread messages
      expect(screen.getByText('15')).toBeInTheDocument(); // completed tasks
      expect(screen.getByText('Upcoming Events')).toBeInTheDocument();
      expect(screen.getByText('Overdue Tasks')).toBeInTheDocument();
      expect(screen.getByText('Unread Messages')).toBeInTheDocument();
      expect(screen.getByText('Completed Today')).toBeInTheDocument();
    });
  });

  // Test 4: shows the loading indicator while data is pending
  test('shows loading indicator while fetching data', () => {
    server.use(
      rest.get('/api/dashboard-dev', () => new Promise<undefined>(() => {})) // never resolves
    );

    render(<Dashboard />);

    expect(screen.getByText('Loading your dashboard...')).toBeInTheDocument();
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  // Test 5: hides the loading indicator after data loads
  test('hides loading indicator after data loads', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(
        screen.queryByText('Loading your dashboard...')
      ).not.toBeInTheDocument();
    });

    expect(
      screen.getByRole('heading', { name: /atom agent dashboard/i })
    ).toBeInTheDocument();
  });

  // Test 6: shows the error state on a network failure
  test('displays error state on network failure', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) => {
        // ctx.networkError is undefined at runtime (msw 1.x moved it to res.*);
        // the resulting throw inside the handler is what produces the network
        // failure this test asserts against, so preserve that exact behavior.
        return res((ctx as any).networkError('Network error'));
      })
    );

    render(<Dashboard />);

    await waitFor(() => {
      expect(
        screen.getByText(/unable to load dashboard/i)
      ).toBeInTheDocument();
      expect(screen.getByText(/please try refreshing the page/i)).toBeInTheDocument();
    });

    consoleSpy.mockRestore();
  });

  // Test 7: handles API error responses (non-2xx)
  test('handles API error responses', async () => {
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    render(<Dashboard />);

    await waitFor(() => {
      expect(
        screen.getByText(/unable to load dashboard/i)
      ).toBeInTheDocument();
    });

    consoleSpy.mockRestore();
  });

  // Test 8: the Overview tab is active by default and the Workflow
  // Automation tab mounts the WorkflowAutomation component
  test('navigates to Workflow Automation tab', async () => {
    render(<Dashboard />);

    await screen.findByRole('heading', { name: /atom agent dashboard/i });

    const workflowTab = screen.getByRole('button', {
      name: /workflow automation/i,
    });
    fireEvent.click(workflowTab);

    await waitFor(() => {
      expect(screen.getByTestId('workflow-automation')).toBeInTheDocument();
    });
  });

  // Test 9: shows empty-state messages when there is no data
  test('shows empty states when no data', async () => {
    render(<Dashboard />);

    await waitFor(() => {
      expect(
        screen.getByText('No events scheduled for today')
      ).toBeInTheDocument();
      expect(screen.getByText('No tasks assigned')).toBeInTheDocument();
      expect(screen.getByText('No messages')).toBeInTheDocument();
    });
  });

  // Test 10: refresh button refetches dashboard data
  test('refresh button refetches data', async () => {
    let dashboardCalls = 0;
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) => {
        dashboardCalls += 1;
        return res(ctx.status(200), ctx.json(emptyData));
      })
    );

    render(<Dashboard />);

    const refreshButton = await screen.findByRole('button', {
      name: /refresh/i,
    });
    fireEvent.click(refreshButton);

    await waitFor(() => {
      expect(dashboardCalls).toBe(2);
    });
  });

  // Test 11: shows refreshing state (button disabled) while refresh is pending
  test('shows refreshing state during refresh', async () => {
    let dashboardCalls = 0;
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) => {
        dashboardCalls += 1;
        if (dashboardCalls === 1) {
          return res(ctx.status(200), ctx.json(emptyData));
        }
        return new Promise(() => {}); // second call never resolves
      })
    );

    render(<Dashboard />);

    const refreshButton = await screen.findByRole('button', {
      name: /refresh/i,
    });
    fireEvent.click(refreshButton);

    await waitFor(() => {
      const refreshingButton = screen.getByRole('button', {
        name: /refreshing/i,
      });
      expect(refreshingButton).toBeDisabled();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: task completion, mark-as-read, platform icons, priorities
// ---------------------------------------------------------------------------
describe('Dashboard Component (extended coverage)', () => {
  let consoleSpy: jest.SpyInstance;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    server.resetHandlers();
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) =>
        res(ctx.status(200), ctx.json(richData))
      )
    );
  });

  // The complete-task button is an icon-only button (no accessible name).
  const getCompleteButton = (taskTitle: string) =>
    screen
      .getByText(taskTitle)
      .closest('div[class*="justify-between"]')!
      .querySelector('button') as HTMLElement;

  test('completing a task shows a success toast and refetches', async () => {
    let dashboardCalls = 0;
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) => {
        dashboardCalls += 1;
        return res(ctx.status(200), ctx.json(richData));
      }),
      rest.post('/api/tasks/1/complete', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true }))
      )
    );

    render(<Dashboard />);
    await screen.findByText('Complete Project');

    fireEvent.click(getCompleteButton('Complete Project'));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Task completed', variant: 'success' })
      );
    });
    await waitFor(() => expect(dashboardCalls).toBe(2));
  });

  test('task completion network failure shows an error toast', async () => {
    server.use(
      rest.post('/api/tasks/1/complete', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<Dashboard />);
    await screen.findByText('Complete Project');

    fireEvent.click(getCompleteButton('Complete Project'));

    await waitFor(() => {
      expect(mockToast.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to complete task',
          variant: 'error',
        })
      );
    });
  });

  test('non-ok task completion response does not toast', async () => {
    server.use(
      rest.post('/api/tasks/1/complete', (req, res, ctx) =>
        res(ctx.status(500))
      )
    );

    render(<Dashboard />);
    await screen.findByText('Complete Project');

    fireEvent.click(getCompleteButton('Complete Project'));

    // give the rejected-path microtasks a chance to run
    await new Promise((r) => setTimeout(r, 100));
    expect(mockToast.toast).not.toHaveBeenCalled();
  });

  test('clicking a message marks it as read and refetches; read messages lack the New badge', async () => {
    let dashboardCalls = 0;
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) => {
        dashboardCalls += 1;
        return res(ctx.status(200), ctx.json(richData));
      }),
      rest.post('/api/messages/1/read', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true }))
      )
    );

    render(<Dashboard />);
    await screen.findByText('Project Update');
    expect(screen.getByText('New')).toBeInTheDocument();

    fireEvent.click(screen.getByText('Project Update'));

    await waitFor(() => expect(dashboardCalls).toBe(2));
  });

  test('mark-as-read network failure is logged without crashing', async () => {
    render(<Dashboard />);
    await screen.findByText('Project Update');

    fireEvent.click(screen.getByText('Project Update'));

    await waitFor(() =>
      expect(consoleSpy).toHaveBeenCalledWith(
        'Error marking message as read:',
        expect.anything()
      )
    );
  });

  test('renders all platform icons and priority variants', async () => {
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) =>
        res(
          ctx.status(200),
          ctx.json({
            calendar: [],
            tasks: [
              { id: 't-high', title: 'High Task', dueDate: '2026-03-11', priority: 'high', status: 'todo' },
              { id: 't-med', title: 'Med Task', dueDate: '2026-03-11', priority: 'medium', status: 'in-progress', description: 'A medium task' },
              { id: 't-low', title: 'Low Task', dueDate: '2020-01-01', priority: 'low', status: 'todo' },
              { id: 't-done', title: 'Done Task', dueDate: '2026-03-11', priority: 'low', status: 'completed' },
            ],
            messages: [
              { id: 'm1', platform: 'email', from: 'a@b.c', subject: 'S1', preview: 'p', timestamp: '2026-03-09T09:00:00', unread: true, priority: 'normal' },
              { id: 'm2', platform: 'slack', from: 's@b.c', subject: 'S2', preview: 'p', timestamp: '2026-03-09T09:00:00', unread: true, priority: 'normal' },
              { id: 'm3', platform: 'teams', from: 't@b.c', subject: 'S3', preview: 'p', timestamp: '2026-03-09T09:00:00', unread: true, priority: 'normal' },
              { id: 'm4', platform: 'discord', from: 'd@b.c', subject: 'S4', preview: 'p', timestamp: '2026-03-09T09:00:00', unread: true, priority: 'normal' },
              { id: 'm5', platform: 'other', from: 'o@b.c', subject: 'S5', preview: 'p', timestamp: '2026-03-09T09:00:00', unread: false, priority: 'normal' },
            ],
            stats: { upcomingEvents: 0, overdueTasks: 0, unreadMessages: 0, completedTasks: 0 },
          })
        )
      )
    );

    render(<Dashboard />);

    expect(await screen.findByText('High Task')).toBeInTheDocument();
    expect(screen.getByText('Med Task')).toBeInTheDocument();
    expect(screen.getByText('A medium task')).toBeInTheDocument();
    // Low Task is not due today: shows the formatted due date, not "Today"
    expect(screen.getAllByText(/Due:/).length).toBeGreaterThan(0);
    expect(screen.queryByText('Due: Today')).not.toBeInTheDocument();
    expect(screen.getByText('Done Task')).toBeInTheDocument();
    // completed tasks have no complete button
    expect(screen.queryByRole('button', { name: /done task/i })).not.toBeInTheDocument();

    for (const subject of ['S1', 'S2', 'S3', 'S4', 'S5']) {
      expect(screen.getByText(subject)).toBeInTheDocument();
    }
  });

  test('renders tentative calendar events without a location', async () => {
    server.use(
      rest.get('/api/dashboard-dev', (req, res, ctx) =>
        res(
          ctx.status(200),
          ctx.json({
            calendar: [
              { id: 'e1', title: 'Maybe Meeting', start: '2026-03-10T10:00:00', end: '2026-03-10T11:00:00', status: 'tentative' },
            ],
            tasks: [],
            messages: [],
            stats: { upcomingEvents: 1, overdueTasks: 0, unreadMessages: 0, completedTasks: 0 },
          })
        )
      )
    );

    render(<Dashboard />);

    expect(await screen.findByText('Maybe Meeting')).toBeInTheDocument();
    expect(screen.getByText('tentative')).toBeInTheDocument();
  });
});
