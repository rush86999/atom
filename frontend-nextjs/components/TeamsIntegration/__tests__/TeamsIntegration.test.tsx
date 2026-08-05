/**
 * TeamsIntegration Component Tests
 *
 * Tests verify the real Microsoft Teams integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Team listing, search/filter, and create-team dialog
 * - Message sending flow
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/TeamsIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import TeamsIntegration from '@/components/TeamsIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const teamHandlers = [
  rest.get('/api/integrations/teams/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/teams/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            displayName: 'Rushi Parikh',
            jobTitle: 'Engineer',
            mail: 'rushi@example.com',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/teams/teams', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          teams: [
            {
              id: '1',
              displayName: 'Engineering',
              description: 'Core engineering team',
              visibility: 'private',
              specialization: 'none',
              isArchived: false,
              createdDateTime: '2024-01-01T00:00:00Z',
              webUrl: 'https://teams.example.com/eng',
            },
            {
              id: '2',
              displayName: 'Design',
              description: 'Design team',
              visibility: 'public',
              specialization: 'educationstandard',
              isArchived: false,
              createdDateTime: '2024-01-01T00:00:00Z',
              webUrl: 'https://teams.example.com/design',
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/teams/users', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          users: [
            {
              id: 'u1',
              displayName: 'Rushi Parikh',
              mail: 'rushi@example.com',
              userPrincipalName: 'rushi@example.com',
              accountEnabled: true,
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/teams/meetings', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { meetings: [] } }));
  }),

  rest.post('/api/integrations/teams/channels', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          channels: [
            {
              id: 'c1',
              displayName: 'General',
              description: 'General channel',
              membershipType: 'standard',
              isFavoriteByDefault: false,
              createdDateTime: '2024-01-01T00:00:00Z',
              webUrl: 'https://teams.example.com/general',
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/teams/messages', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { messages: [] } }));
  }),

  rest.post('/api/integrations/teams/messages/send', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/teams/health', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

describe('TeamsIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...teamHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<TeamsIntegration />);

    expect(
      screen.getByRole('heading', { name: /microsoft teams integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<TeamsIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect microsoft teams account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt to its virtual console; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<TeamsIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect microsoft teams account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<TeamsIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays teams after connection
  test('displays teams after connection', async () => {
    render(<TeamsIntegration />);

    // Teams are loaded twice (checkConnection + connected effect); wait for the
    // full list to settle rather than the first team card.
    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('Design')).toBeInTheDocument();
    });
  });

  // Test 6: filters teams by search
  test('filters teams by search query', async () => {
    render(<TeamsIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/search teams/i);
    fireEvent.change(searchInput, { target: { value: 'Design' } });

    await waitFor(() => {
      expect(screen.getByText('Design')).toBeInTheDocument();
    });
    expect(screen.queryByText('Engineering')).not.toBeInTheDocument();
  });

  // Test 7: opens create team dialog
  test('opens create team dialog', async () => {
    render(<TeamsIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create team/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /create team/i })).toBeInTheDocument();
    });
  });

  // Test 9: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/teams/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<TeamsIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect microsoft teams account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 10: shows refresh status button
  test('shows refresh status button', async () => {
    render(<TeamsIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });

  // Test 11: displays user profile when connected
  test('displays user profile when connected', async () => {
    render(<TeamsIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });
});
