/**
 * JiraOAuthFlow Component Tests
 *
 * Tests verify the real Jira OAuth flow component
 * (components/JiraOAuthFlow.tsx):
 * - Idle state with the connect CTA
 * - OAuth start flow (GET /api/auth/jira/start) and redirect handling
 * - Start failure -> error state + onError callback + retry
 * - Callback error via URL params (?error=...)
 * - Full success flow (?success=true -> resources -> auto-select ->
 *   projects/issues from resource discovery) -> onIntegrationComplete
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts. The component builds absolute URLs against
 * http://localhost:8000 (NEXT_PUBLIC_API_BASE_URL unset in tests).
 */

import React from 'react';
import { renderWithProviders, screen, waitFor, act } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import { JiraOAuthFlow } from '../JiraOAuthFlow';

const resources = [
  {
    id: 'res1',
    name: 'acme.atlassian.net',
    url: 'https://acme.atlassian.net',
    scopes: ['read:jira-work'],
    cloud_id: 'CLOUD1',
    discovery: {
      projects: [
        { id: 'p1', key: 'ATL', name: 'Atlas' },
        { id: 'p2', key: 'ENG', name: 'Engine' },
      ],
      issues: [
        { id: 'i1', key: 'ATL-1', summary: 'Fix login flow', status: 'In Progress' },
      ],
    },
  },
];

const startHandler = rest.get(
  'http://localhost:8000/api/auth/jira/start',
  (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        auth_url: 'https://auth.atlassian.com/authorize?client_id=test',
      })
    );
  }
);

const resourcesHandler = rest.get(
  'http://localhost:8000/api/auth/jira/resources',
  (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ resources }));
  }
);

const projectsHandler = rest.get(
  'http://localhost:8000/api/auth/jira/CLOUD1/projects',
  (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        projects: resources[0].discovery.projects,
        issues: resources[0].discovery.issues,
      })
    );
  }
);

describe('JiraOAuthFlow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    window.history.replaceState({}, '', '/');
  });

  afterEach(() => {
    window.history.replaceState({}, '', '/');
    jest.useRealTimers();
  });

  test('renders the idle connect state', () => {
    renderWithProviders(<JiraOAuthFlow />);

    expect(
      screen.getByRole('heading', { name: /connect to jira/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /connect to jira/i })
    ).toBeInTheDocument();
    expect(screen.getByText('idle')).toBeInTheDocument();
  });

  test('starts the OAuth flow and requests the authorization URL', async () => {
    const user = userEvent.setup();
    const fetchSpy = jest.spyOn(global, 'fetch');
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    server.use(startHandler);

    renderWithProviders(<JiraOAuthFlow />);

    await user.click(
      screen.getByRole('button', { name: /connect to jira/i })
    );

    // The component requests the auth URL and moves into the loading UI
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /processing oauth flow/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getByText(/redirecting to authorization/i)
    ).toBeInTheDocument();

    expect(
      fetchSpy.mock.calls.some(
        ([url]) => String(url).includes('/api/auth/jira/start')
      )
    ).toBe(true);

    // jsdom cannot navigate; the loading state must remain stable
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByText('loading')).toBeInTheDocument();
    expect(consoleErrorSpy).not.toHaveBeenCalled();

    consoleErrorSpy.mockRestore();
  });

  test('reports a start failure through the error state and onError', async () => {
    const user = userEvent.setup();
    const onError = jest.fn();
    const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    server.use(
      rest.get('http://localhost:8000/api/auth/jira/start', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ error: 'oauth misconfigured' }));
      })
    );

    renderWithProviders(<JiraOAuthFlow onError={onError} />);

    await user.click(
      screen.getByRole('button', { name: /connect to jira/i })
    );

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /oauth integration failed/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getAllByText(/oauth start failed: 500/i).length
    ).toBeGreaterThan(0);
    expect(onError).toHaveBeenCalledWith(expect.stringContaining('OAuth start failed: 500'));
    expect(
      screen.getByRole('button', { name: /try again/i })
    ).toBeInTheDocument();

    consoleErrorSpy.mockRestore();
  });

  test('retries after a failure when the backend recovers', async () => {
    const user = userEvent.setup();
    let healthy = false;

    server.use(
      rest.get('http://localhost:8000/api/auth/jira/start', (req, res, ctx) => {
        if (!healthy) {
          return res(ctx.status(503), ctx.json({ error: 'unavailable' }));
        }
        return res(
          ctx.status(200),
          ctx.json({ auth_url: 'https://auth.atlassian.com/authorize?retry=1' })
        );
      })
    );

    renderWithProviders(<JiraOAuthFlow />);

    await user.click(
      screen.getByRole('button', { name: /connect to jira/i })
    );

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /oauth integration failed/i })
      ).toBeInTheDocument();
    });

    healthy = true;
    await user.click(screen.getByRole('button', { name: /try again/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /processing oauth flow/i })
      ).toBeInTheDocument();
    });
  });

  test('renders the error state from an OAuth callback error param', async () => {
    const onError = jest.fn();

    window.history.replaceState({}, '', '/?error=access_denied&description=User+denied');

    renderWithProviders(<JiraOAuthFlow onError={onError} />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /oauth integration failed/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getAllByText(/oauth error: access_denied - User denied/i).length
    ).toBeGreaterThan(0);
    expect(onError).toHaveBeenCalledWith(
      expect.stringContaining('access_denied')
    );
    expect(
      screen.getByText(/troubleshooting steps/i)
    ).toBeInTheDocument();
  });

  test('completes the flow: loads resources, auto-selects, and reports integration', async () => {
    const onIntegrationComplete = jest.fn();
    const onResourcesDiscovered = jest.fn();

    server.use(startHandler, resourcesHandler, projectsHandler);

    // The success branch fires loadResources after a 1s settle delay
    window.history.replaceState({}, '', '/?success=true');
    jest.useFakeTimers();

    renderWithProviders(
      <JiraOAuthFlow
        onIntegrationComplete={onIntegrationComplete}
        onResourcesDiscovered={onResourcesDiscovered}
      />
    );

    // Trigger the delayed resource load
    await act(async () => {
      jest.advanceTimersByTime(1100);
    });
    jest.useRealTimers();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /jira integration successful/i })
      ).toBeInTheDocument();
    });

    // Discovered resource card
    expect(screen.getByText('acme.atlassian.net')).toBeInTheDocument();
    expect(screen.getByText('CLOUD1')).toBeInTheDocument();
    expect(screen.getByText('1 scopes')).toBeInTheDocument();

    // Projects and issues come from resource discovery
    expect(screen.getByText('Atlas')).toBeInTheDocument();
    expect(screen.getByText('ATL')).toBeInTheDocument();
    expect(screen.getByText('Engine')).toBeInTheDocument();
    expect(screen.getByText('ATL-1')).toBeInTheDocument();
    expect(screen.getByText('Fix login flow')).toBeInTheDocument();
    expect(screen.getByText('In Progress')).toBeInTheDocument();

    expect(onResourcesDiscovered).toHaveBeenCalledWith(resources);
    expect(onIntegrationComplete).toHaveBeenCalledWith(
      expect.objectContaining({
        connected: true,
        resourceId: 'CLOUD1',
        resourceName: 'acme.atlassian.net',
        projectCount: 2,
        issueCount: 1,
        status: 'active',
      })
    );

    // Refresh resources re-runs the discovery
    const refreshButton = screen.getByRole('button', { name: /refresh resources/i });
    await act(async () => {
      refreshButton.click();
      await new Promise((r) => setTimeout(r, 20));
    });
    await waitFor(() => {
      expect(screen.getByText('acme.atlassian.net')).toBeInTheDocument();
    });
  });

  test('reports a resource load failure through the error state', async () => {
    const onError = jest.fn();

    server.use(
      rest.get('http://localhost:8000/api/auth/jira/resources', (req, res, ctx) => {
        return res(ctx.status(403), ctx.json({ error: 'forbidden' }));
      })
    );

    window.history.replaceState({}, '', '/?success=true');
    jest.useFakeTimers();

    renderWithProviders(<JiraOAuthFlow onError={onError} />);

    await act(async () => {
      jest.advanceTimersByTime(1100);
    });
    jest.useRealTimers();

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /oauth integration failed/i })
      ).toBeInTheDocument();
    });
    expect(
      screen.getAllByText(/failed to load resources: 403/i).length
    ).toBeGreaterThan(0);
    expect(onError).toHaveBeenCalledWith(
      expect.stringContaining('Failed to load resources: 403')
    );
    expect(
      screen.getByRole('button', { name: /reset/i })
    ).toBeInTheDocument();
  });

  test('reset returns from the error state to the idle connect view', async () => {
    const user = userEvent.setup();
    const onError = jest.fn();

    window.history.replaceState({}, '', '/?error=invalid_scope&description=Bad+scope');

    renderWithProviders(<JiraOAuthFlow onError={onError} />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /oauth integration failed/i })
      ).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /reset/i }));

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /connect to jira/i })
      ).toBeInTheDocument();
    });
    expect(onError).toHaveBeenCalledTimes(1);
  });
});
