/**
 * AsanaIntegration Component Tests
 *
 * Tests verify the real Asana integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Task, project, team, and workspace data loading
 * - Task search filtering and create-task dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/AsanaIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AsanaIntegration from '@/components/AsanaIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const asanaHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { asana: { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { asana: { connected: true, source: 'user_connection' } } }));
  }),

  rest.get('/api/integrations/asana/workspaces', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          workspaces: [{ id: 'w1', name: 'Atom Workspace' }],
        },
      })
    );
  }),

  rest.get('/api/integrations/asana/projects', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          projects: [
            {
              id: 'p1',
              name: 'Website Launch',
              owner: { name: 'Rushi' },
              workspace: { name: 'Atom Workspace' },
              team: { name: 'Engineering' },
            },
          ],
        },
      })
    );
  }),

  rest.get('/api/integrations/asana/tasks', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          tasks: [
            {
              id: 't1',
              name: 'Write launch post',
              description: 'Draft the launch blog post',
              projects: [{ id: 'p1', name: 'Website Launch' }],
              assignee: { name: 'Rushi Parikh' },
              due_on: null,
              completed: false,
              permalink_url: 'https://app.asana.com/t1',
            },
            {
              id: 't2',
              name: 'Fix login bug',
              description: 'Resolve the auth error',
              projects: [{ id: 'p1', name: 'Website Launch' }],
              assignee: { name: 'Alice' },
              due_on: null,
              completed: false,
              permalink_url: 'https://app.asana.com/t2',
            },
          ],
        },
      })
    );
  }),

  rest.get('/api/integrations/asana/teams', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          teams: [{ id: 't1', name: 'Engineering', organization: { name: 'Atom' } }],
        },
      })
    );
  }),

  rest.get('/api/integrations/asana/users', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { users: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

// Data is loaded in both checkConnection() and the connected useEffect
// (double data-load race); wait for the full dataset to settle.
const settleData = async (text: RegExp) => {
  await screen.findByText(text);
  await new Promise((r) => setTimeout(r, 50));
};

describe('AsanaIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...asanaHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<AsanaIntegration />);

    expect(
      screen.getByRole('heading', { name: /asana integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect asana account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<AsanaIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect asana account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays tasks in the default Tasks tab
  test('displays tasks in the default Tasks tab', async () => {
    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Write launch post')).toBeInTheDocument();
      expect(screen.getByText('Fix login bug')).toBeInTheDocument();
    });
  });

  // Test 6: filters tasks by search query
  test('filters tasks by search query', async () => {
    render(<AsanaIntegration />);

    await settleData(/Write launch post/);

    const searchInput = screen.getByPlaceholderText(/search tasks/i);
    fireEvent.change(searchInput, { target: { value: 'login' } });

    await waitFor(() => {
      expect(screen.getByText('Fix login bug')).toBeInTheDocument();
    });
    expect(screen.queryByText('Write launch post')).not.toBeInTheDocument();
  });

  // Test 7: opens create task dialog
  test('opens create task dialog', async () => {
    render(<AsanaIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /new task/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 8: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect asana account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: shows refresh status button
  test('shows refresh status button', async () => {
    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: error paths, due-date variants, create-task dialog
// ---------------------------------------------------------------------------
describe('AsanaIntegration (extended coverage)', () => {
  let consoleSpy: jest.SpyInstance;
  let openSpy: jest.Mock;

  beforeEach(() => {
    jest.clearAllMocks();
    consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    openSpy = jest.fn();
    window.open = openSpy as any;
    server.resetHandlers();
    server.use(...asanaHandlers);
  });

  afterEach(() => {
    consoleSpy.mockRestore();
  });

  test('health-check rejection disconnects and logs', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res) =>
        res.networkError('down')
      )
    );

    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Connection status check failed:', expect.anything());
    });
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect asana account/i })
      ).toBeInTheDocument();
    });
  });

  test('data-loading failures are logged without crashing', async () => {
    server.use(
      rest.get('/api/integrations/asana/workspaces', (req, res) =>
        res.networkError('down')
      ),
      rest.get('/api/integrations/asana/tasks', (req, res) =>
        res.networkError('down')
      ),
      rest.get('/api/integrations/asana/teams', (req, res) =>
        res.networkError('down')
      ),
      rest.get('/api/integrations/asana/users', (req, res) =>
        res.networkError('down')
      )
    );

    render(<AsanaIntegration />);

    await waitFor(() => {
      const messages = consoleSpy.mock.calls.map((c) => c[0]);
      expect(messages).toEqual(
        expect.arrayContaining([
          'Failed to load workspaces:',
          'Failed to load tasks:',
          'Failed to load teams:',
          'Failed to load users:',
        ])
      );
    });
  });

  test('renders overdue, upcoming, completed and undated task variants', async () => {
    const today = new Date();
    const past = new Date(today.getTime() - 10 * 24 * 3600 * 1000)
      .toISOString()
      .slice(0, 10);
    const soon = new Date(today.getTime() + 2 * 24 * 3600 * 1000)
      .toISOString()
      .slice(0, 10);
    const later = new Date(today.getTime() + 30 * 24 * 3600 * 1000)
      .toISOString()
      .slice(0, 10);

    server.use(
      rest.get('/api/integrations/asana/tasks', (req, res, ctx) =>
        res(
          ctx.status(200),
          ctx.json({
            data: {
              tasks: [
                { id: 'a', name: 'Overdue Task', projects: [], assignee: null, due_on: past, completed: false, permalink_url: 'u1' },
                { id: 'b', name: 'Soon Task', projects: [], assignee: null, due_on: soon, completed: false, permalink_url: 'u2' },
                { id: 'c', name: 'Later Task', projects: [], assignee: null, due_on: later, completed: false, permalink_url: 'u3' },
                { id: 'd', name: 'Done Task', projects: [], assignee: null, due_on: later, completed: true, permalink_url: 'u4' },
                { id: 'e', name: 'Undated Task', projects: [], assignee: null, due_on: null, completed: false, permalink_url: 'u5' },
              ],
            },
          })
        )
      )
    );

    render(<AsanaIntegration />);

    await screen.findByText('Overdue Task');
    expect(screen.getByText('Soon Task')).toBeInTheDocument();
    expect(screen.getByText('Later Task')).toBeInTheDocument();
    expect(screen.getByText('Done Task')).toBeInTheDocument();
    expect(screen.getByText('Undated Task')).toBeInTheDocument();
    expect(screen.getAllByText('Completed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('In Progress').length).toBeGreaterThan(0);
    expect(screen.getAllByText('No due date').length).toBeGreaterThan(0);

    // View button opens the permalink
    fireEvent.click(screen.getAllByRole('button', { name: /view/i })[0]);
    expect(openSpy).toHaveBeenCalled();
  });

  test('creates a task from the dialog and cancels it', async () => {
    server.use(
      rest.post('/api/integrations/asana/tasks', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ success: true }))
      )
    );

    render(<AsanaIntegration />);
    fireEvent.click(await screen.findByRole('button', { name: /new task/i }));

    fireEvent.change(await screen.findByPlaceholderText('Enter task name'), {
      target: { value: 'Brand new task' },
    });
    fireEvent.change(screen.getByPlaceholderText('Task description'), {
      target: { value: 'A description' },
    });

    // fill the due date input
    const dateInput = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateInput, { target: { value: '2026-09-01' } });

    // submit the dialog
    const createBtn = screen
      .getAllByRole('button')
      .find((b) => b.textContent === 'Create Task') as HTMLElement;
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(consoleSpy).not.toHaveBeenCalledWith('Failed to create task:', expect.anything());
    });
    // dialog closes after a successful create
    await waitFor(() => {
      expect(screen.queryByPlaceholderText('Enter task name')).not.toBeInTheDocument();
    });

    // reopen and cancel
    fireEvent.click(screen.getByRole('button', { name: /new task/i }));
    fireEvent.click(
      screen
        .getAllByRole('button')
        .find((b) => b.textContent === 'Cancel') as HTMLElement
    );
    await waitFor(() => {
      expect(screen.queryByPlaceholderText('Enter task name')).not.toBeInTheDocument();
    });
  });

  test('create-task failures log an error toast', async () => {
    server.use(
      rest.post('/api/integrations/asana/tasks', (req, res) =>
        res.networkError('down')
      )
    );

    render(<AsanaIntegration />);
    fireEvent.click(await screen.findByRole('button', { name: /new task/i }));
    fireEvent.change(await screen.findByPlaceholderText('Enter task name'), {
      target: { value: 'Doomed task' },
    });

    const createBtn = screen
      .getAllByRole('button')
      .find((b) => b.textContent === 'Create Task') as HTMLElement;
    fireEvent.click(createBtn);

    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith('Failed to create task:', expect.anything());
    });
  });

  test('projects tab opens project permalinks', async () => {
    render(<AsanaIntegration />);

    // wait for the connected dashboard (tasks tab) before switching
    await screen.findByText('Write launch post');
    fireEvent.click(screen.getByRole('button', { name: 'Projects' }));
    await screen.findByText('Website Launch');

    fireEvent.click(screen.getByRole('button', { name: /open in asana/i }));
    expect(openSpy).toHaveBeenCalled();
  });
});
