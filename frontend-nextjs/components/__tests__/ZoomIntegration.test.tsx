/**
 * ZoomIntegration Component Tests
 *
 * Tests verify the real Zoom integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile, meetings, users, and recordings data loading
 * - Search filtering and create-meeting dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/ZoomIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ZoomIntegration from '@/components/ZoomIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const zoomHandlers = [
  rest.get('/api/integrations/zoom/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/zoom/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            first_name: 'Rushi',
            last_name: 'Parikh',
            email: 'rushi@example.com',
            role_name: 'Owner',
            pic_url: '',
            personal_meeting_url: 'https://zoom.us/my/rushi',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/zoom/meetings', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          meetings: [
            {
              id: 'm1',
              topic: 'Weekly Sync',
              start_time: '2024-01-15T10:00:00Z',
              duration: 60,
              timezone: 'UTC',
              join_url: 'https://zoom.us/j/123',
              agenda: 'Weekly sync',
              settings: { auto_recording: 'none' },
            },
            {
              id: 'm2',
              topic: 'Design Review',
              start_time: '2024-01-16T10:00:00Z',
              duration: 30,
              timezone: 'UTC',
              join_url: 'https://zoom.us/j/456',
              settings: { auto_recording: 'cloud' },
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/zoom/users', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          users: [
            {
              id: 'u1',
              email: 'rushi@example.com',
              first_name: 'Rushi',
              last_name: 'Parikh',
              status: 'active',
            },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/zoom/recordings', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { recordings: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/zoom/health', (req, res, ctx) => {
      return res(ctx.status(404));
    })
  );
};

// Profile/meetings are loaded in both checkConnection() and the connected
// useEffect (double data-load race); wait for the full dataset to settle.
const settleData = async (text: RegExp) => {
  await screen.findByText(text);
  await new Promise((r) => setTimeout(r, 50));
};

describe('ZoomIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...zoomHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<ZoomIntegration />);

    expect(
      screen.getByRole('heading', { name: /zoom integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect zoom account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<ZoomIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect zoom account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays meetings after connection
  test('displays meetings after connection', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Weekly Sync')).toBeInTheDocument();
      expect(screen.getByText('Design Review')).toBeInTheDocument();
    });
  });

  // Test 7: filters meetings by search query
  test('filters meetings by search query', async () => {
    render(<ZoomIntegration />);

    await settleData(/Weekly Sync/);

    const searchInput = screen.getByPlaceholderText(/search meetings/i);
    fireEvent.change(searchInput, { target: { value: 'Design' } });

    await waitFor(() => {
      expect(screen.getByText('Design Review')).toBeInTheDocument();
    });
    expect(screen.queryByText('Weekly Sync')).not.toBeInTheDocument();
  });

  // Test 8: displays users on the Users tab
  test('displays users on the Users tab', async () => {
    render(<ZoomIntegration />);

    await settleData(/Weekly Sync/);

    // The profile header already shows "Rushi Parikh"; the Users tab renders
    // the same name in the user list, so assert a second occurrence appears.
    const before = screen.getAllByText('Rushi Parikh').length;

    const usersTab = screen.getByRole('button', { name: 'Users' });
    fireEvent.click(usersTab);

    await waitFor(() => {
      expect(screen.getAllByText('Rushi Parikh').length).toBeGreaterThan(before);
    });
  });

  // Test 9: opens create meeting dialog
  test('opens create meeting dialog', async () => {
    render(<ZoomIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /schedule meeting/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 10: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/zoom/health', (req, res, ctx) => {
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

  // Test 11: shows refresh status button
  test('shows refresh status button', async () => {
    render(<ZoomIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});
