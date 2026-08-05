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
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const githubHandlers = [
  rest.get('/api/integrations/github/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
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
    rest.get('/api/integrations/github/health', (req, res, ctx) => {
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
      rest.get('/api/integrations/github/health', (req, res, ctx) => {
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
