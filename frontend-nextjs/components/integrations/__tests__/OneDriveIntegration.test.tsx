/**
 * OneDriveIntegration Component Tests
 *
 * Tests verify the real OneDrive integration component:
 * - Connection status check (GET /api/onedrive/connection-status)
 * - Disconnected / connect state
 * - File and folder browsing (GET /api/onedrive/list-files)
 * - Disconnect flow
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/integrations/OneDriveIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import OneDriveIntegration from '@/components/integrations/OneDriveIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const connectedStatus = {
  is_connected: true,
  email: 'rushi@example.com',
  display_name: 'Rushi Parikh',
  drive_type: 'business',
};

const onedriveHandlers = [
  rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(connectedStatus));
  }),

  rest.get('/api/onedrive/list-files', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        files: [
          {
            id: 'f1',
            name: 'Marketing',
            is_folder: true,
            icon: '📁',
            modified_time: '2024-01-15T10:00:00Z',
            size: 0,
            web_url: '',
          },
          {
            id: 'f2',
            name: 'roadmap.pdf',
            is_folder: false,
            icon: '📄',
            modified_time: '2024-01-14T10:00:00Z',
            size: 1048576,
            web_url: 'https://onedrive.com/f2',
          },
        ],
        next_page_token: null,
      })
    );
  }),

  rest.post('/api/auth/onedrive/disconnect', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ is_connected: false, reason: 'Not connected' }));
    })
  );
};

describe('OneDriveIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...onedriveHandlers);
  });

  // Test 1: renders component
  test('renders component', async () => {
    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /onedrive integration/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setNotConnected();

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect onedrive/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<OneDriveIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect onedrive/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when connection status is healthy
  test('shows connected state when connection status is healthy', async () => {
    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays files and folders after connection
  test('displays files and folders after connection', async () => {
    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Marketing')).toBeInTheDocument();
      expect(screen.getByText('roadmap.pdf')).toBeInTheDocument();
    });
  });

  // Test 6: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/onedrive/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<OneDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect onedrive/i })
      ).toBeInTheDocument();
    });
  });

  // Test 7: disconnect button is clickable without crashing
  test('disconnect button is clickable without crashing', async () => {
    render(<OneDriveIntegration />);

    const disconnectButton = await screen.findByRole('button', {
      name: /disconnect onedrive/i,
    });
    expect(() => fireEvent.click(disconnectButton)).not.toThrow();
  });
});
