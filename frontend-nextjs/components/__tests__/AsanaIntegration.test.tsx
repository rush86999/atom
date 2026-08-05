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
  rest.get('/api/integrations/asana/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
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
    rest.get('/api/integrations/asana/health', (req, res, ctx) => {
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
      rest.get('/api/integrations/asana/health', (req, res, ctx) => {
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
