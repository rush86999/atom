/**
 * JiraIntegration Component Tests
 *
 * Tests verify the real Jira integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile, projects, users, issues, and sprints data loading
 * - Search filtering and create-issue dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/JiraIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom';
import JiraIntegration from '@/components/JiraIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

// The real shadcn Select (Radix) throws on <SelectItem value="">. The Jira
// component renders empty-value items in the Issues tab and create-issue
// dialog, which would crash Radix in jsdom. Mock the Select primitive with a
// context-aware implementation so the Issues tab and dialog can render and be
// interacted with (trigger -> open content -> click item calls onValueChange).
jest.mock('@/components/ui/select', () => {
  const { createContext, useContext, useState } = jest.requireActual('react');
  const SelectCtx = createContext<any>(null);

  const Select = ({ value, onValueChange, children }: any) => {
    const [open, setOpen] = useState(false);
    return (
      <SelectCtx.Provider value={{ value, onValueChange, open, setOpen }}>
        <div data-testid="select-root">{children}</div>
      </SelectCtx.Provider>
    );
  };
  const SelectTrigger = ({ children, className, ...props }: any) => {
    const { setOpen } = useContext(SelectCtx);
    return (
      <button type="button" className={className} onClick={() => setOpen((o: boolean) => !o)} {...props}>
        {children}
      </button>
    );
  };
  const SelectContent = ({ children }: any) => {
    const { open } = useContext(SelectCtx);
    return open ? <div data-testid="select-content">{children}</div> : null;
  };
  const SelectItem = ({ value, children }: any) => {
    const { onValueChange, setOpen } = useContext(SelectCtx);
    return (
      <span onClick={() => { onValueChange(value); setOpen(false); }}>{children}</span>
    );
  };
  const SelectValue = ({ placeholder }: any) => <span data-testid="select-value" />;
  return { Select, SelectTrigger, SelectContent, SelectItem, SelectValue };
});

const jiraHandlers = [
  rest.get('/api/integrations/jira/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/jira/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            accountId: 'u1',
            displayName: 'Rushi Parikh',
            emailAddress: 'rushi@example.com',
            avatarUrls: { '48x48': 'https://example.com/avatar.png' },
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/jira/projects', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          projects: [
            {
              id: '10000',
              key: 'TEST',
              name: 'Test Project',
              projectTypeKey: 'software',
              lead: { displayName: 'John Doe', emailAddress: 'john@example.com', avatarUrls: {} },
              url: 'https://test.atlassian.net/browse/TEST',
              description: 'A test project',
              isPrivate: false,
              archived: false,
              issueTypes: [],
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/jira/users', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          users: [
            {
              accountId: '12345',
              accountType: 'atlassian',
              active: true,
              displayName: 'John Doe',
              emailAddress: 'john@example.com',
              avatarUrls: {},
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/jira/issues', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          issues: [
            {
              id: '10001',
              key: 'TEST-1',
              fields: {
                summary: 'Test issue summary',
                description: 'Test issue description',
                status: { name: 'To Do', statusCategory: { colorName: 'blue-gray' } },
                priority: { name: 'Medium', iconUrl: '' },
                reporter: { displayName: 'Jane Smith', emailAddress: '', avatarUrls: {} },
                created: '2024-01-15T10:00:00.000Z',
                updated: '2024-01-15T10:00:00.000Z',
                issuetype: { name: 'Story', iconUrl: '' },
                project: { key: 'TEST', name: 'Test Project' },
              },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/jira/sprints', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          sprints: [
            {
              id: 1,
              state: 'active',
              name: 'Sprint 1',
              originBoardId: 1,
              goal: 'Ship it',
              issues: [],
            },
          ],
        },
      })
    );
  }),
];

// Projects/profile are loaded in both checkConnection() and the connected
// useEffect (double data-load race); wait for the full dataset to settle before
// interacting so a transient loading re-render can't wipe the list.
const settleData = async (text: RegExp) => {
  await screen.findByText(text);
  await new Promise((r) => setTimeout(r, 50));
};

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/jira/health', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

describe('JiraIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...jiraHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<JiraIntegration />);

    expect(
      screen.getByRole('heading', { name: /jira integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<JiraIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect jira account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<JiraIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect jira account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<JiraIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<JiraIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays projects after connection
  test('displays projects after connection', async () => {
    render(<JiraIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });
  });

  // Test 7: filters projects by search query
  test('filters projects by search query', async () => {
    render(<JiraIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search projects/i);
    fireEvent.change(searchInput, { target: { value: 'zzz' } });

    await waitFor(() => {
      expect(screen.queryByText('Test Project')).not.toBeInTheDocument();
    });
  });

  // Test 8: shows create project button (the component has no create-project
  // dialog; the button just opens state)
  test('shows create project button', async () => {
    render(<JiraIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create project/i,
    });
    expect(() => fireEvent.click(createButton)).not.toThrow();
  });

  // Test 9: displays users on the Team tab
  test('displays users on the Team tab', async () => {
    render(<JiraIntegration />);

    const teamTab = await screen.findByRole('button', { name: 'Team' });
    fireEvent.click(teamTab);

    await waitFor(() => {
      expect(screen.getByText('John Doe')).toBeInTheDocument();
    });
  });

  // Test 10: loads issues after selecting a project
  test('loads issues after selecting a project', async () => {
    render(<JiraIntegration />);

    await settleData(/Test Project/);

    // Click the project card to select it (sets selectedProject key 'TEST')
    fireEvent.click(screen.getByText('Test Project'));

    // Switch to Issues tab
    const issuesTab = screen.getByRole('button', { name: 'Issues' });
    fireEvent.click(issuesTab);

    await waitFor(() => {
      expect(screen.getByText('TEST-1')).toBeInTheDocument();
      expect(screen.getByText('Test issue summary')).toBeInTheDocument();
    });
  });

  // Test 11: loads sprints after selecting a project
  test('loads sprints after selecting a project', async () => {
    render(<JiraIntegration />);

    await settleData(/Test Project/);

    fireEvent.click(screen.getByText('Test Project'));

    const sprintsTab = screen.getByRole('button', { name: 'Sprints' });
    fireEvent.click(sprintsTab);

    await waitFor(() => {
      expect(screen.getByText('Sprint 1')).toBeInTheDocument();
    });
  });

  // Test 12: creates a new issue via the dialog
  test('creates a new issue via the dialog', async () => {
    const issuePosts: any[] = [];
    server.use(
      rest.post('/api/integrations/jira/issues/create', (req, res, ctx) => {
        issuePosts.push(req.body);
        return res(ctx.status(200), ctx.json({ success: true }));
      })
    );

    render(<JiraIntegration />);

    await settleData(/Test Project/);

    // Select the project so the Create Issue button becomes enabled
    fireEvent.click(screen.getByText('Test Project'));

    const issuesTab = screen.getByRole('button', { name: 'Issues' });
    fireEvent.click(issuesTab);

    const createButton = await screen.findByRole('button', {
      name: /create issue/i,
    });
    fireEvent.click(createButton);

    // Fill in the summary and project selects inside the dialog
    const summaryInput = await screen.findByPlaceholderText(/issue summary/i);
    fireEvent.change(summaryInput, { target: { value: 'New test issue' } });

    // Select a project via the dialog's project Select (first trigger)
    const dialog = screen.getByRole('dialog');
    const dialogButtons = within(dialog).getAllByRole('button');
    fireEvent.click(dialogButtons[0]);
    const projectItem = await within(dialog).findByText(/Test Project \(TEST\)/);
    fireEvent.click(projectItem);

    const submitButton = within(dialog).getByRole('button', { name: 'Create Issue' });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(issuePosts.some((body) => body.summary === 'New test issue')).toBe(true);
    });
  });

  // Test 13: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/jira/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<JiraIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect jira account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 14: shows refresh status button
  test('shows refresh status button', async () => {
    render(<JiraIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});
