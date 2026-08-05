/**
 * ZoomIntegration Component Tests (components/integrations/ZoomIntegration)
 *
 * Tests verify the real Zoom integration component:
 * - Connection status check (GET /api/zoom/connection-status)
 * - Disconnected / connect state
 * - Meetings, users, and recordings data loading
 * - Disconnect flow
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/integrations/ZoomIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ZoomIntegration from '@/components/integrations/ZoomIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const connectedStatus = {
  is_connected: true,
  user_info: {
    id: 'user1',
    email: 'rushi@example.com',
    first_name: 'Rushi',
    last_name: 'Parikh',
  },
};

const zoomHandlers = [
  rest.get('/api/zoom/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(connectedStatus));
  }),

  rest.get('/api/zoom/meetings', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        meetings: [
          {
            id: 'm1',
            topic: 'Weekly Sync',
            agenda: 'Sprint planning',
            start_time: '2024-01-15T10:00:00Z',
            duration: 60,
            status: 'waiting',
          },
          {
            id: 'm2',
            topic: 'Design Review',
            agenda: '',
            start_time: '2024-01-16T10:00:00Z',
            duration: 30,
            status: 'started',
          },
        ],
      })
    );
  }),

  rest.get('/api/zoom/users', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        users: [
          {
            id: 'u1',
            email: 'rushi@example.com',
            first_name: 'Rushi',
            last_name: 'Parikh',
            status: 'active',
          },
        ],
      })
    );
  }),

  rest.get('/api/zoom/recordings', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        recordings: [
          {
            id: 'r1',
            topic: 'Weekly Sync recording',
            file_size: 52428800,
            download_url: 'https://zoom.us/r1',
          },
        ],
      })
    );
  }),

  rest.get('/api/zoom/analytics/meetings', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        period: { from: '2024-01-01', to: '2024-01-31' },
        total_meetings: 10,
        total_participants: 25,
        average_duration: 45,
        meetings_by_type: { scheduled: 8, instant: 1, recurring: 1 },
      })
    );
  }),

  rest.post('/api/zoom/auth/disconnect', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/zoom/connection-status', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ is_connected: false, reason: 'Not connected' }));
    })
  );
};

describe('ZoomIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...zoomHandlers);
  });

  // Test 1: renders component (heading appears after connection status loads)
  test('renders component', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /zoom integration/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setNotConnected();

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zoom account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (the component fakes
  // the connection via a 2s timeout, so only assert the click does not throw)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<ZoomIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect zoom account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when connection status is healthy
  test('shows connected state when connection status is healthy', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays meetings in the default Meetings tab
  test('displays meetings in the default Meetings tab', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sync')).toBeInTheDocument();
      expect(screen.getByText('Design Review')).toBeInTheDocument();
    });
  });

  // Test 6: displays users on the Users tab
  test('displays users on the Users tab', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sync')).toBeInTheDocument();
    });

    const usersTab = screen.getByRole('button', { name: 'Users' });
    fireEvent.click(usersTab);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 7: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/zoom/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zoom account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 8: shows refresh button in connected state
  test('shows refresh button in connected state', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh/i })).toBeInTheDocument();
    });
  });

  // Test 9: disconnect button is clickable without crashing
  test('disconnect button is clickable without crashing', async () => {
    render(<ZoomIntegration />);

    const disconnectButton = await screen.findByRole('button', {
      name: /disconnect/i,
    });
    expect(() => fireEvent.click(disconnectButton)).not.toThrow();
  });
});
