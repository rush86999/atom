/**
 * GitHubIntegration Component Tests
 *
 * Tests verify the real GitHub integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile and repository data loading
 * - Repository search filtering
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/GitHubIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GitHubIntegration from '@/components/GitHubIntegration';
import { useToast } from '@/components/ui/use-toast';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const getToastMock = (): jest.Mock => (useToast as jest.Mock)().toast;

const githubHandlers = [
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({ providers: { github: { connected: true, source: 'user_connection' } } })
    );
  }),
  rest.get('/api/integrations/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ providers: { github: { connected: true, source: 'user_connection' } } }));
  }),

  rest.post('/api/integrations/github/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            login: 'rushi',
            name: 'Rushi Parikh',
            avatar_url: '',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/github/repositories', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          repositories: [
            {
              id: 1,
              name: 'atom',
              full_name: 'rushi/atom',
              description: 'AI automation platform',
              language: 'Python',
              private: false,
              fork: false,
              stargazers_count: 120,
              watchers_count: 10,
              html_url: 'https://github.com/rushi/atom',
            },
            {
              id: 2,
              name: 'notes-app',
              full_name: 'rushi/notes-app',
              description: 'Notes app',
              language: 'TypeScript',
              private: true,
              fork: false,
              stargazers_count: 5,
              watchers_count: 1,
              html_url: 'https://github.com/rushi/notes-app',
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/github/issues', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { issues: [] } }));
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

describe('GitHubIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...githubHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<GitHubIntegration />);

    expect(
      screen.getByRole('heading', { name: /github integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<GitHubIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect github account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<GitHubIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect github account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<GitHubIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<GitHubIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays repositories in the default Repositories tab
  test('displays repositories in the default Repositories tab', async () => {
    render(<GitHubIntegration />);

    await waitFor(() => {
      expect(screen.getByText('atom')).toBeInTheDocument();
      expect(screen.getByText('notes-app')).toBeInTheDocument();
    });
  });

  // Test 7: filters repositories by search query
  test('filters repositories by search query', async () => {
    render(<GitHubIntegration />);

    await settleData(/atom/);

    const searchInput = screen.getByPlaceholderText(/search repositories/i);
    fireEvent.change(searchInput, { target: { value: 'notes' } });

    await waitFor(() => {
      expect(screen.getByText('notes-app')).toBeInTheDocument();
    });
    expect(screen.queryByText('atom')).not.toBeInTheDocument();
  });

  // Test 8: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<GitHubIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect github account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: shows refresh status button
  test('shows refresh status button', async () => {
    render(<GitHubIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Extended coverage: issues tab, create-issue flow, profile tab, error paths
// ---------------------------------------------------------------------------
describe('GitHubIntegration (extended coverage)', () => {
  // NOTE: jest.config.js sets restoreMocks:true, which detaches describe-scope
  // spies after every test — create a fresh console.error spy per test.
  let errorSpy: jest.SpyInstance;
  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
  });

  const longBody = 'y'.repeat(250);

  const richIssues = [
    {
      id: 'i1',
      number: 42,
      title: 'Crash on startup',
      body: longBody,
      state: 'open',
      html_url: 'https://github.com/rushi/atom/issues/42',
      created_at: '2024-01-10T00:00:00Z',
      user: { login: 'alice', avatar_url: '' },
      labels: [{ id: 'l1', name: 'bug', color: 'd73a4a' }],
    },
    {
      id: 'i2',
      number: 43,
      title: 'Docs improvement',
      body: 'Short body',
      state: 'closed',
      html_url: 'https://github.com/rushi/atom/issues/43',
      created_at: '2024-01-11T00:00:00Z',
      user: { login: 'bob', avatar_url: '' },
      labels: [],
    },
  ];

  // NOTE: MSW resolves handlers in the order passed to server.use(), so the
  // data-rich overrides must come BEFORE the base githubHandlers.
  const richHandlers = [
    rest.post('/api/integrations/github/profile', (req, res, ctx) => {
      return res(
        ctx.status(200),
        ctx.json({
          data: {
            profile: {
              id: 'u1',
              login: 'rushi',
              name: 'Rushi Parikh',
              avatar_url: '',
              bio: 'Builder',
              public_repos: 12,
              followers: 34,
              following: 56,
              company: 'Atom Inc',
              location: 'SF',
              blog: 'https://rushi.dev',
              email: 'rushi@example.com',
              type: 'User',
              created_at: '2020-05-01T00:00:00Z',
            },
          },
        })
      );
    }),
    rest.post('/api/integrations/github/repositories', (req, res, ctx) => {
      return res(
        ctx.status(200),
        ctx.json({
          data: {
            repositories: [
              {
                id: 1,
                name: 'atom',
                full_name: 'rushi/atom',
                description: 'AI automation platform',
                language: 'Python',
                private: false,
                fork: false,
                stargazers_count: 120,
                watchers_count: 10,
                html_url: 'https://github.com/rushi/atom',
              },
              {
                id: 2,
                name: 'notes-app',
                full_name: 'rushi/notes-app',
                description: 'Notes app',
                language: 'TypeScript',
                private: true,
                fork: true,
                stargazers_count: 5,
                watchers_count: 1,
                html_url: 'https://github.com/rushi/notes-app',
              },
              {
                id: 3,
                name: 'labs',
                full_name: 'rushi/labs',
                description: 'Experiments',
                language: 'Rust',
                private: false,
                fork: false,
                stargazers_count: 0,
                watchers_count: 0,
                html_url: 'https://github.com/rushi/labs',
              },
            ],
          },
        })
      );
    }),
    rest.post('/api/integrations/github/issues', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { issues: richIssues } }));
    }),
    rest.post('/api/integrations/github/issues/create', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ data: { issue: { id: 'i999' } } }));
    }),
    ...githubHandlers,
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...richHandlers);
  });

  const settle = async (text: RegExp | string) => {
    await screen.findByText(text);
    await new Promise((r) => setTimeout(r, 50));
  };

  test('renders repository badges (Private, Fork, languages)', async () => {
    render(<GitHubIntegration />);

    await settle('atom');
    expect(screen.getByText('Private')).toBeInTheDocument();
    expect(screen.getByText('Fork')).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
    expect(screen.getByText('TypeScript')).toBeInTheDocument();
    expect(screen.getByText('Rust')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
  });

  test('selecting a repository loads its issues with labels and states', async () => {
    render(<GitHubIntegration />);
    await settle('atom');

    fireEvent.click(screen.getByText('atom'));
    fireEvent.click(screen.getByRole('button', { name: 'Issues' }));

    expect(await screen.findByText('#42 Crash on startup')).toBeInTheDocument();
    expect(screen.getByText('#43 Docs improvement')).toBeInTheDocument();
    expect(screen.getByText('open')).toBeInTheDocument();
    expect(screen.getByText('closed')).toBeInTheDocument();
    expect(screen.getByText('bug')).toBeInTheDocument();
    // body over 200 chars is truncated with an ellipsis
    expect(
      screen.getByText(
        (_, el) =>
          el?.tagName === 'P' && el.textContent === longBody.substring(0, 200) + '...'
      )
    ).toBeInTheDocument();

    // filter issues by search
    fireEvent.change(screen.getByPlaceholderText(/search issues/i), {
      target: { value: 'docs' },
    });
    expect(screen.getByText('#43 Docs improvement')).toBeInTheDocument();
    expect(screen.queryByText('#42 Crash on startup')).not.toBeInTheDocument();
  });

  test('creates an issue through the dialog', async () => {
    render(<GitHubIntegration />);
    await settle('atom');

    fireEvent.click(screen.getByText('atom'));
    fireEvent.click(screen.getByRole('button', { name: 'Issues' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create issue/i })[0]);
    const dialog = await screen.findByRole('dialog');

    // repository select (Radix, keyboard-opened)
    const repoTrigger = dialog.querySelector('button[role="combobox"]')!;
    fireEvent.keyDown(repoTrigger, { key: 'ArrowDown' });
    const repoOption = await waitFor(() => {
      const found = Array.from(document.querySelectorAll('[role="option"]')).find(
        (i) => i.textContent === 'rushi/atom'
      );
      if (!found) throw new Error('repo option not found');
      return found as HTMLElement;
    });
    fireEvent.click(repoOption);

    fireEvent.change(screen.getByPlaceholderText('Issue title'), {
      target: { value: 'Brand new bug' },
    });
    fireEvent.change(screen.getByPlaceholderText('Describe the issue...'), {
      target: { value: 'Steps to reproduce' },
    });

    const footerButtons = Array.from(dialog.querySelectorAll('button')).filter((b) =>
      /create issue/i.test(b.textContent || '')
    );
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Success', description: 'Issue created successfully' })
      );
    });
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
  });

  test('shows error toast when issue creation fails', async () => {
    server.use(
      rest.post('/api/integrations/github/issues/create', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<GitHubIntegration />);
    await settle('atom');

    fireEvent.click(screen.getByText('atom'));
    fireEvent.click(screen.getByRole('button', { name: 'Issues' }));
    fireEvent.click(screen.getAllByRole('button', { name: /create issue/i })[0]);
    const dialog = await screen.findByRole('dialog');

    const repoTrigger = dialog.querySelector('button[role="combobox"]')!;
    fireEvent.keyDown(repoTrigger, { key: 'ArrowDown' });
    const repoOption = await waitFor(() => {
      const found = Array.from(document.querySelectorAll('[role="option"]')).find(
        (i) => i.textContent === 'rushi/atom'
      );
      if (!found) throw new Error('repo option not found');
      return found as HTMLElement;
    });
    fireEvent.click(repoOption);

    fireEvent.change(screen.getByPlaceholderText('Issue title'), {
      target: { value: 'Doomed issue' },
    });
    const footerButtons = Array.from(dialog.querySelectorAll('button')).filter((b) =>
      /create issue/i.test(b.textContent || '')
    );
    fireEvent.click(footerButtons[footerButtons.length - 1]);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({ title: 'Error', description: 'Failed to create issue' })
      );
    });
  });

  test('renders the profile tab with account details', async () => {
    render(<GitHubIntegration />);
    await settle('atom');

    fireEvent.click(screen.getByRole('button', { name: 'Profile' }));

    expect(await screen.findByText('Public Repositories')).toBeInTheDocument();
    expect(screen.getByText('Followers')).toBeInTheDocument();
    expect(screen.getByText('Following')).toBeInTheDocument();
    expect(screen.getByText('Company: Atom Inc')).toBeInTheDocument();
    expect(screen.getByText('Location: SF')).toBeInTheDocument();
    expect(screen.getByText('Website: https://rushi.dev')).toBeInTheDocument();
    expect(screen.getByText('Email: rushi@example.com')).toBeInTheDocument();
    expect(screen.getByText('Account Type: User')).toBeInTheDocument();
    expect(screen.getByText(/Member Since:/)).toBeInTheDocument();
  });

  test('shows error toast when repository loading fails', async () => {
    server.use(
      rest.post('/api/integrations/github/repositories', (req, res) =>
        res.networkError('boom')
      )
    );

    render(<GitHubIntegration />);

    await waitFor(() => {
      expect(getToastMock()).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Error',
          description: 'Failed to load repositories from GitHub',
        })
      );
    });
  });

  test('logs errors when profile and issue loads fail', async () => {
    const netFail = (path: string) => rest.post(path, (req, res) => res.networkError('boom'));
    server.use(
      netFail('/api/integrations/github/profile'),
      netFail('/api/integrations/github/issues')
    );

    render(<GitHubIntegration />);
    await settle('atom');

    fireEvent.click(screen.getByText('atom'));

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to load user profile:', expect.anything());
      expect(errorSpy).toHaveBeenCalledWith('Failed to load issues:', expect.anything());
    });
  });

  test('treats health check network failure as disconnected', async () => {
    server.use(
      rest.get('/api/integrations/connection-status', (req, res) => res.networkError('boom'))
    );

    render(<GitHubIntegration />);

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Connection status check failed:', expect.anything());
      expect(
        screen.getByRole('button', { name: /connect github account/i })
      ).toBeInTheDocument();
    });
  });

  test('clicking Refresh Status re-runs the health check', async () => {
    render(<GitHubIntegration />);
    await settle('atom');

    fireEvent.click(screen.getByRole('button', { name: /refresh status/i }));
    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });
});
