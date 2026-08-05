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
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
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
