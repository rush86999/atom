/**
 * LinearIntegration Component Tests
 *
 * Tests verify the real Linear integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Issue loading, search filtering, and team display
 * - Create-issue dialog and submission flow
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/LinearIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import LinearIntegration from '@/components/LinearIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const linearHandlers = [
  rest.get('/api/integrations/linear/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/linear/teams', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          teams: [
            {
              id: '1',
              name: 'Engineering',
              description: 'Core engineering team',
              key: 'ENG',
              memberCount: 12,
            },
            {
              id: '2',
              name: 'Design',
              description: 'Design team',
              key: 'DES',
              memberCount: 8,
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/linear/issues', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          issues: [
            {
              id: 'i1',
              title: 'Bug fix',
              description: 'Fix the crash',
              state: 'todo',
              priority: 2,
              team: '1',
              updatedAt: '2024-01-01T00:00:00Z',
              url: 'https://linear.example.com/issue/1',
            },
            {
              id: 'i2',
              title: 'Feature request',
              description: 'Add dark mode',
              state: 'inProgress',
              priority: 3,
              team: '1',
              updatedAt: '2024-01-01T00:00:00Z',
              url: 'https://linear.example.com/issue/2',
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/linear/projects', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { projects: [] } }));
  }),

  rest.post('/api/integrations/linear/cycles', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { cycles: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/linear/health', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

describe('LinearIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...linearHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<LinearIntegration />);

    expect(
      screen.getByRole('heading', { name: /linear integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<LinearIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect linear account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt to its virtual console; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<LinearIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect linear account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays issues after connection
  test('displays issues after connection', async () => {
    render(<LinearIntegration />);

    // Issues only load after teams are fetched; wait for the full list.
    await waitFor(() => {
      expect(screen.getByText('Bug fix')).toBeInTheDocument();
      expect(screen.getByText('Feature request')).toBeInTheDocument();
    });
  });

  // Test 6: filters issues by search query
  test('filters issues by search query', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Bug fix')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search issues/i);
    fireEvent.change(searchInput, { target: { value: 'Feature' } });

    await waitFor(() => {
      expect(screen.getByText('Feature request')).toBeInTheDocument();
    });
    expect(screen.queryByText('Bug fix')).not.toBeInTheDocument();
  });

  // Test 7: displays teams after connection
  test('displays teams after connection', async () => {
    render(<LinearIntegration />);

    // The project's shadcn Tabs is a custom implementation (plain <button>,
    // no role="tab"), so query the trigger as a button.
    const teamsTab = await screen.findByRole('button', { name: 'Teams' });
    fireEvent.click(teamsTab);

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('Design')).toBeInTheDocument();
    });
  });

  // Test 8: opens create issue dialog
  test('opens create issue dialog', async () => {
    render(<LinearIntegration />);

    const newIssueButton = await screen.findByRole('button', {
      name: /new issue/i,
    });
    fireEvent.click(newIssueButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: /create new issue/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: creates new issue via dialog
  test('creates new issue via dialog', async () => {
    const issuePosts: any[] = [];
    server.use(
      rest.post('/api/integrations/linear/issues', (req, res, ctx) => {
        issuePosts.push(req.body);
        return res(ctx.status(200), ctx.json({ data: { issues: [] } }));
      })
    );

    render(<LinearIntegration />);

    const newIssueButton = await screen.findByRole('button', {
      name: /new issue/i,
    });
    fireEvent.click(newIssueButton);

    const titleInput = await screen.findByPlaceholderText(/issue title/i);
    fireEvent.change(titleInput, { target: { value: 'Test issue' } });

    const createButton = screen.getByRole('button', { name: 'Create Issue' });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(issuePosts.some((body) => body.title === 'Test issue')).toBe(true);
    });
  });

  // Test 10: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/linear/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<LinearIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect linear account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 11: shows refresh status button
  test('shows refresh status button', async () => {
    render(<LinearIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /refresh status/i })
      ).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: rich datasets, tab content, filters, modal fields, errors
// ---------------------------------------------------------------------------
describe('LinearIntegration (extended coverage)', () => {
  let errorSpy: jest.SpyInstance;
  let openSpy: jest.Mock;

  const richIssues = [
    { id: 'r1', title: 'Backlog item', description: null, state: 'backlog', priority: 0, team: '1', updatedAt: '2024-01-01T00:00:00Z', url: 'https://linear.example.com/r1' },
    { id: 'r2', title: 'Todo item', description: 'd2', state: 'todo', priority: 1, team: '1', updatedAt: '2024-01-02T00:00:00Z', url: 'https://linear.example.com/r2' },
    { id: 'r3', title: 'Progress item', description: 'd3', state: 'inProgress', priority: 2, team: '1', updatedAt: '2024-01-03T00:00:00Z', url: 'https://linear.example.com/r3' },
    { id: 'r4', title: 'Done item', description: 'd4', state: 'done', priority: 3, team: '1', updatedAt: '2024-01-04T00:00:00Z', url: 'https://linear.example.com/r4' },
    { id: 'r5', title: 'Canceled item', description: 'd5', state: 'canceled', priority: 4, team: '1', updatedAt: '2024-01-05T00:00:00Z', url: 'https://linear.example.com/r5' },
    { id: 'r6', title: 'Weird item', description: 'd6', state: 'somethingElse', priority: 9, team: '2', updatedAt: '2024-01-06T00:00:00Z', url: 'https://linear.example.com/r6' },
  ];

  const richProjects = [
    { id: 'p1', name: 'Active Project', description: 'In flight', state: 'active', progress: 65.4 },
    { id: 'p2', name: 'Planned Project', description: 'Not started', state: 'planned', progress: 0 },
  ];

  const richCycles = [
    { id: 'c1', name: 'Cycle 14', number: 14, startsAt: '2026-08-01T00:00:00Z', endsAt: '2026-08-14T00:00:00Z', progress: 42.6 },
  ];

  const richHandlers = [
    rest.post('/api/integrations/linear/issues', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { issues: richIssues } }));
    }),
    rest.post('/api/integrations/linear/projects', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { projects: richProjects } }));
    }),
    rest.post('/api/integrations/linear/cycles', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { cycles: richCycles } }));
    }),
    ...linearHandlers,
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...richHandlers);
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    openSpy = jest.fn();
    window.open = openSpy as any;
  });

  const settle = async () => {
    await screen.findByText('Backlog item');
    await new Promise((r) => setTimeout(r, 50));
  };

  test('renders issues across states and priorities with badges', async () => {
    render(<LinearIntegration />);
    await settle();

    for (const title of ['Backlog item', 'Todo item', 'Progress item', 'Done item', 'Canceled item', 'Weird item']) {
      expect(screen.getByText(title)).toBeInTheDocument();
    }
    expect(screen.getByText('No priority')).toBeInTheDocument();
    expect(screen.getByText('Low')).toBeInTheDocument();
    expect(screen.getByText('Medium')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('Urgent')).toBeInTheDocument();
    expect(screen.getByText('Unknown')).toBeInTheDocument();
    // Stats
    expect(screen.getByText('6')).toBeInTheDocument();
    expect(screen.getByText('17%')).toBeInTheDocument();
  });

  test('opens the issue url from the View button', async () => {
    render(<LinearIntegration />);
    await settle();

    fireEvent.click(screen.getAllByRole('button', { name: /view/i })[0]);
    expect(openSpy).toHaveBeenCalledWith('https://linear.example.com/r1', '_blank');
  });

  test('renders projects with progress and state badges', async () => {
    render(<LinearIntegration />);
    await settle();

    fireEvent.click(screen.getByRole('button', { name: 'Projects' }));
    expect(await screen.findByText('Active Project')).toBeInTheDocument();
    expect(screen.getByText('Planned Project')).toBeInTheDocument();
    expect(screen.getByText('65%')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
    expect(screen.getByText('planned')).toBeInTheDocument();
  });

  test('renders cycles with dates and progress', async () => {
    render(<LinearIntegration />);
    await settle();

    fireEvent.click(screen.getByRole('button', { name: 'Cycles' }));
    expect((await screen.findAllByText('Cycle 14')).length).toBeGreaterThan(0);
    expect(screen.getByText('43% Complete')).toBeInTheDocument();
  });

  test('shows the empty state when the search matches nothing', async () => {
    render(<LinearIntegration />);
    await settle();

    fireEvent.change(screen.getByPlaceholderText(/search issues/i), {
      target: { value: 'zzz-no-match' },
    });
    expect(await screen.findByText('No issues found')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /create your first issue/i }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  const selectRadixOption = async (trigger: HTMLElement, optionText: string) => {
    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    const option = await waitFor(() => {
      const found = Array.from(document.querySelectorAll('[role="option"]')).find(
        (el) => el.textContent === optionText
      );
      expect(found).toBeDefined();
      return found as HTMLElement;
    });
    fireEvent.click(option);
  };

  test('filters issues by state via the state select', async () => {
    render(<LinearIntegration />);
    await settle();

    const triggers = screen.getAllByRole('combobox');
    // Triggers: team, state, priority
    await selectRadixOption(triggers[1], 'Done');
    await waitFor(() => {
      expect(screen.getByText('Done item')).toBeInTheDocument();
    });
    expect(screen.queryByText('Backlog item')).not.toBeInTheDocument();
  });

  test('filters issues by priority via the priority select', async () => {
    render(<LinearIntegration />);
    await settle();

    const triggers = screen.getAllByRole('combobox');
    await selectRadixOption(triggers[2], 'Urgent');
    await waitFor(() => {
      expect(screen.getByText('Canceled item')).toBeInTheDocument();
    });
    expect(screen.queryByText('Backlog item')).not.toBeInTheDocument();
  });

  test('creates an issue with team and priority selected in the modal', async () => {
    const created: any[] = [];
    server.use(
      rest.post('/api/integrations/linear/issues', (req, res, ctx) => {
        created.push(req.body);
        return res(ctx.status(200), ctx.json({ data: { issues: richIssues } }));
      })
    );

    render(<LinearIntegration />);
    await settle();

    fireEvent.click(screen.getByRole('button', { name: /new issue/i }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.change(
      within(dialog).getByPlaceholderText(/issue title/i),
      { target: { value: 'Brand new issue' } }
    );
    fireEvent.change(
      within(dialog).getByPlaceholderText(/issue description/i),
      { target: { value: 'A description' } }
    );

    // Modal team select (the only combobox inside the dialog portal)
    const modalTrigger = within(dialog).getAllByRole('combobox')[0];
    await selectRadixOption(modalTrigger, 'Engineering');
    const priorityTrigger = within(dialog).getAllByRole('combobox')[1];
    await selectRadixOption(priorityTrigger, 'High');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Issue' }));

    await waitFor(() => {
      expect(created.length).toBeGreaterThan(0);
      expect(
        created.some(
          (b) =>
            b.title === 'Brand new issue' &&
            b.team_id === '1' &&
            b.priority === 3
        )
      ).toBe(true);
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows an error toast when issue creation fails', async () => {
    const createCalls: string[] = [];
    server.use(
      rest.post('/api/integrations/linear/issues', (req, res) => {
        createCalls.push('called');
        return res.networkError('boom');
      })
    );

    render(<LinearIntegration />);
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /new issue/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /new issue/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.change(
      within(dialog).getByPlaceholderText(/issue title/i),
      { target: { value: 'Failing issue' } }
    );
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create Issue' }));

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to create issue:', expect.anything());
    });
  });

  test('cancels the create-issue dialog', async () => {
    render(<LinearIntegration />);
    await settle();

    fireEvent.click(screen.getByRole('button', { name: /new issue/i }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('logs errors when data loads fail', async () => {
    const netFail = (path: string) => rest.post(path, (req, res) => res.networkError('boom'));
    server.use(netFail('/api/integrations/linear/teams'));

    const { unmount } = render(<LinearIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load teams:', expect.anything());
    });
    unmount();
    errorSpy.mockClear();

    // With teams loading fine, the remaining loaders run and can fail.
    server.resetHandlers();
    server.use(
      netFail('/api/integrations/linear/issues'),
      netFail('/api/integrations/linear/projects'),
      netFail('/api/integrations/linear/cycles'),
      ...linearHandlers
    );

    render(<LinearIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load issues:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load projects:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load cycles:', expect.anything());
    });
  });

  test('treats a health-check network failure as disconnected', async () => {
    server.use(
      rest.get('/api/integrations/linear/health', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<LinearIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Health check failed:', expect.anything());
      expect(
        screen.getByRole('button', { name: /connect linear account/i })
      ).toBeInTheDocument();
    });
  });
});
