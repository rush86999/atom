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
      rest.get('/api/dashboard-dev', () => new Promise(() => {})) // never resolves
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
        return res(ctx.networkError('Network error'));
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
