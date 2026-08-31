/**
 * AsanaIntegration Component Tests
 *
 * Tests verify the real Asana integration component
 * (components/AsanaIntegration.tsx):
 * - Connection status check (GET /api/integrations/asana/health)
 * - Disconnected / connect state
 * - Workspaces, projects, tasks, teams, and users data loading
 * - Task search filtering and the create-task dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import AsanaIntegration from '@/components/AsanaIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const tasks = [
  {
    id: 'task1',
    name: 'Complete Project',
    description: 'Finish all deliverables',
    due_on: '2026-03-15',
    assignee: { id: 'u1', name: 'Rushi Parikh' },
    projects: [{ id: 'proj1', name: 'Marketing Campaign' }],
    workspace: { id: 'ws1', name: 'My Workspace' },
    completed: false,
    created_at: '2026-01-01T00:00:00Z',
    modified_at: '2026-01-01T00:00:00Z',
    permalink_url: 'https://asana.com/task1',
    tags: [],
  },
  {
    id: 'task2',
    name: 'Review Code',
    due_on: '2026-03-10',
    assignee: null,
    projects: [{ id: 'proj2', name: 'Development' }],
    workspace: { id: 'ws1', name: 'My Workspace' },
    completed: true,
    created_at: '2026-01-01T00:00:00Z',
    modified_at: '2026-01-01T00:00:00Z',
    permalink_url: 'https://asana.com/task2',
    tags: [],
  },
];

const projects = [
  {
    id: 'proj1',
    name: 'Marketing Campaign',
    description: 'Q1 campaign launch',
    color: 'blue',
    due_date: '2026-03-20',
    current_status: { color: 'green', text: 'On Track' },
    owner: { id: 'u1', name: 'Rushi Parikh' },
    workspace: { id: 'ws1', name: 'My Workspace' },
    created_at: '2026-01-01T00:00:00Z',
    modified_at: '2026-01-01T00:00:00Z',
    permalink_url: 'https://asana.com/proj1',
  },
];

const workspaces = [
  {
    id: 'ws1',
    name: 'My Workspace',
    is_organization: true,
  },
];

const teams = [
  {
    id: 'team1',
    name: 'Engineering',
    description: 'Core engineering team',
    organization: { id: 'org1', name: 'Acme Inc' },
  },
];

const users = [
  {
    id: 'u1',
    name: 'Rushi Parikh',
    email: 'rushi@example.com',
  },
];

const asanaHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { asana: { connected: true, source: 'user_connection' } } }));
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { asana: { connected: true, source: 'user_connection' } } }));
  }),

  rest.get('/api/integrations/asana/workspaces', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { workspaces } }));
  }),

  rest.get('/api/integrations/asana/projects', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { projects } }));
  }),

  rest.get('/api/integrations/asana/tasks', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { tasks } }));
  }),

  rest.get('/api/integrations/asana/teams', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { teams } }));
  }),

  rest.get('/api/integrations/asana/users', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { users } }));
  }),

  rest.post('/api/integrations/asana/tasks', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true, data: { task: { id: 'task3' } } }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/integrations/connection-status', (req, res, ctx) => {
      return res(ctx.status(500), ctx.json({ error: 'not connected' }));
    })
  );
};

describe('AsanaIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...asanaHandlers);
  });

  // Test 1: shows the connect screen when not connected
  test('shows connect screen when not connected', async () => {
    setNotConnected();

    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect asana/i })
      ).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /connect asana account/i })
      ).toBeInTheDocument();
      expect(screen.getByText('Disconnected')).toBeInTheDocument();
    });
  });

  // Test 2: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<AsanaIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect asana account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 3: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /asana integration/i })
      ).toBeInTheDocument();
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 4: displays overview stat cards
  test('displays overview stat cards', async () => {
    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Total Tasks')).toBeInTheDocument();
      expect(screen.getByText('Overdue')).toBeInTheDocument();
      expect(screen.getByText('Assigned')).toBeInTheDocument();
      expect(screen.getByText('Completion Rate')).toBeInTheDocument();
    });
  });

  // Test 5: displays tasks in the default tab
  test('displays tasks in the default tab', async () => {
    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Complete Project')).toBeInTheDocument();
      expect(screen.getByText('Review Code')).toBeInTheDocument();
    });
  });

  // Test 6: filters tasks by search query
  test('filters tasks by search query', async () => {
    render(<AsanaIntegration />);

    await screen.findByText('Complete Project');

    const searchInput = screen.getByPlaceholderText('Search tasks...');
    fireEvent.change(searchInput, { target: { value: 'Review' } });

    expect(screen.queryByText('Complete Project')).not.toBeInTheDocument();
    expect(screen.getByText('Review Code')).toBeInTheDocument();
  });

  // Test 7: displays projects on the Projects tab
  test('displays projects on the Projects tab', async () => {
    render(<AsanaIntegration />);

    await screen.findByText('Complete Project');

    fireEvent.click(screen.getByRole('button', { name: 'Projects' }));

    await waitFor(() => {
      expect(screen.getByText('Marketing Campaign')).toBeInTheDocument();
      expect(screen.getByText('On Track')).toBeInTheDocument();
    });
  });

  // Test 8: displays teams on the Teams tab
  test('displays teams on the Teams tab', async () => {
    render(<AsanaIntegration />);

    await screen.findByText('Complete Project');

    fireEvent.click(screen.getByRole('button', { name: 'Teams' }));

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('Core engineering team')).toBeInTheDocument();
    });
  });

  // Test 9: displays workspaces on the Workspaces tab
  test('displays workspaces on the Workspaces tab', async () => {
    render(<AsanaIntegration />);

    await screen.findByText('Complete Project');

    fireEvent.click(screen.getByRole('button', { name: 'Workspaces' }));

    await waitFor(() => {
      expect(screen.getByText('My Workspace')).toBeInTheDocument();
      expect(screen.getByText('Organization')).toBeInTheDocument();
    });
  });

  // Test 10: New Task button opens the create dialog
  test('opens create task dialog', async () => {
    render(<AsanaIntegration />);

    await screen.findByText('Complete Project');

    fireEvent.click(screen.getByRole('button', { name: /new task/i }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /create new task/i })
      ).toBeInTheDocument();
    });
  });

  // Test 11: creating a task calls POST /api/integrations/asana/tasks
  test('creating a task calls the create endpoint', async () => {
    let requestBody: any = null;
    server.use(
      rest.post('/api/integrations/asana/tasks', (req, res, ctx) => {
        // MSW pre-parses JSON request bodies into objects
        requestBody = req.body as any;
        return res(
          ctx.status(200),
          ctx.json({ success: true, data: { task: { id: 'task3' } } })
        );
      })
    );

    render(<AsanaIntegration />);

    await screen.findByText('Complete Project');

    fireEvent.click(screen.getByRole('button', { name: /new task/i }));

    const nameInput = screen.getByPlaceholderText('Enter task name');
    fireEvent.change(nameInput, { target: { value: 'New Marketing Task' } });

    fireEvent.click(screen.getByRole('button', { name: /create task/i }));

    await waitFor(() => {
      expect(requestBody).toEqual(
        expect.objectContaining({ name: 'New Marketing Task' })
      );
    });
  });

  // Test 12: shows refresh status button
  test('shows refresh status button', async () => {
    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /refresh status/i })
      ).toBeInTheDocument();
    });
  });

  // Test 13: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'Server error' }));
      })
    );

    render(<AsanaIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect asana account/i })
      ).toBeInTheDocument();
    });
  });
});
