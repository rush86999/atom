/**
 * ZendeskIntegration Component Tests
 *
 * Tests verify the real Zendesk integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile and ticket data loading
 * - Ticket search filtering and create-ticket dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/ZendeskIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ZendeskIntegration from '@/components/ZendeskIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const zendeskHandlers = [
  rest.get('/api/integrations/zendesk/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/zendesk/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            name: 'Rushi Parikh',
            email: 'rushi@example.com',
            role: 'admin',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/zendesk/tickets', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          tickets: [
            {
              id: 101,
              subject: 'Login issue',
              description: 'User cannot log in',
              status: 'open',
              priority: 'high',
              requester_id: 1,
              requester: { name: 'Alice' },
            },
            {
              id: 102,
              subject: 'Billing question',
              description: 'Invoice question',
              status: 'solved',
              priority: 'low',
              requester_id: 2,
              requester: { name: 'Bob' },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/zendesk/users', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { users: [] } }));
  }),
  rest.post('/api/integrations/zendesk/groups', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { groups: [] } }));
  }),
  rest.post('/api/integrations/zendesk/views', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { views: [] } }));
  }),
  rest.post('/api/integrations/zendesk/organizations', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { organizations: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/zendesk/health', (req, res, ctx) => {
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

describe('ZendeskIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...zendeskHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<ZendeskIntegration />);

    expect(
      screen.getByRole('heading', { name: /zendesk integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zendesk account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<ZendeskIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect zendesk account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays tickets in the default Tickets tab
  test('displays tickets in the default Tickets tab', async () => {
    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Login issue')).toBeInTheDocument();
      expect(screen.getByText('Billing question')).toBeInTheDocument();
    });
  });

  // Test 7: filters tickets by search query
  test('filters tickets by search query', async () => {
    render(<ZendeskIntegration />);

    await settleData(/Login issue/);

    const searchInput = screen.getByPlaceholderText(/search tickets/i);
    fireEvent.change(searchInput, { target: { value: 'Billing' } });

    await waitFor(() => {
      expect(screen.getByText('Billing question')).toBeInTheDocument();
    });
    expect(screen.queryByText('Login issue')).not.toBeInTheDocument();
  });

  // Test 8: opens create ticket dialog
  test('opens create ticket dialog', async () => {
    render(<ZendeskIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create ticket/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 9: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/zendesk/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zendesk account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 10: shows refresh status button
  test('shows refresh status button', async () => {
    render(<ZendeskIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});
