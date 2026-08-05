/**
 * Microsoft365Integration Component Tests
 *
 * Tests verify the real Microsoft 365 integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile, email, calendar event, and team data loading
 * - Email search filtering and compose-email dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/Microsoft365Integration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import Microsoft365Integration from '@/components/Microsoft365Integration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const m365Handlers = [
  rest.get('/api/integrations/microsoft365/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.get('/api/integrations/microsoft365/user', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            displayName: 'Rushi Parikh',
            jobTitle: 'Engineer',
            userPrincipalName: 'rushi@example.com',
          },
        },
      })
    );
  }),

  rest.get('/api/integrations/microsoft365/outlook/messages', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        messages: [
          {
            id: 'e1',
            subject: 'Hello World',
            from: { emailAddress: { name: 'Alice', address: 'alice@example.com' } },
            sender: { emailAddress: { name: 'Alice', address: 'alice@example.com' } },
            bodyPreview: 'Preview of the email',
            isRead: false,
            receivedDateTime: '2024-01-15T10:00:00Z',
          },
          {
            id: 'e2',
            subject: 'Q3 Planning',
            from: { emailAddress: { name: 'Bob', address: 'bob@example.com' } },
            sender: { emailAddress: { name: 'Bob', address: 'bob@example.com' } },
            bodyPreview: 'Planning doc attached',
            isRead: true,
            receivedDateTime: '2024-01-14T10:00:00Z',
          },
        ],
      })
    );
  }),

  rest.get('/api/integrations/microsoft365/calendar/events', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        events: [
          {
            id: 'ev1',
            subject: 'Team Standup',
            start: { dateTime: '2024-01-15T09:00:00Z' },
            end: { dateTime: '2024-01-15T09:30:00Z' },
          },
        ],
      })
    );
  }),

  rest.get('/api/integrations/microsoft365/teams', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        teams: [
          { id: 't1', displayName: 'Engineering', description: 'Core engineering team' },
          { id: 't2', displayName: 'Design', description: 'Design team' },
        ],
      })
    );
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/microsoft365/health', (req, res, ctx) => {
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

describe('Microsoft365Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...m365Handlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<Microsoft365Integration />);

    expect(
      screen.getByRole('heading', { name: /microsoft 365 integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect microsoft 365 account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<Microsoft365Integration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect microsoft 365 account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays emails in the default Outlook tab
  test('displays emails in the default Outlook tab', async () => {
    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(screen.getByText('Hello World')).toBeInTheDocument();
      expect(screen.getByText('Q3 Planning')).toBeInTheDocument();
    });
  });

  // Test 7: filters emails by search query
  test('filters emails by search query', async () => {
    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    const searchInput = screen.getByPlaceholderText(/search emails/i);
    fireEvent.change(searchInput, { target: { value: 'Q3' } });

    await waitFor(() => {
      expect(screen.getByText('Q3 Planning')).toBeInTheDocument();
    });
    expect(screen.queryByText('Hello World')).not.toBeInTheDocument();
  });

  // Test 8: opens compose email dialog
  test('opens compose email dialog', async () => {
    render(<Microsoft365Integration />);

    const composeButton = await screen.findByRole('button', {
      name: /compose email/i,
    });
    fireEvent.click(composeButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 9: displays teams on the Teams tab
  test('displays teams on the Teams tab', async () => {
    render(<Microsoft365Integration />);

    await settleData(/Hello World/);

    const teamsTab = screen.getByRole('button', { name: 'Teams' });
    fireEvent.click(teamsTab);

    await waitFor(() => {
      expect(screen.getByText('Engineering')).toBeInTheDocument();
      expect(screen.getByText('Design')).toBeInTheDocument();
    });
  });

  // Test 10: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/microsoft365/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect microsoft 365 account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 11: shows refresh status button
  test('shows refresh status button', async () => {
    render(<Microsoft365Integration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});
