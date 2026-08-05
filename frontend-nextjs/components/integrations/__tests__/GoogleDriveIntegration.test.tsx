/**
 * GoogleDriveIntegration Component Tests
 *
 * Tests verify the real Google Drive integration component:
 * - Connection status check (GET /api/gdrive/connection-status)
 * - Disconnected / connect state
 * - File and folder browsing (GET /api/gdrive/list-files)
 * - Disconnect flow
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/integrations/GoogleDriveIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import GoogleDriveIntegration from '@/components/integrations/GoogleDriveIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const connectedStatus = {
  isConnected: true,
  email: 'rushi@example.com',
};

const gdriveHandlers = [
  rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json(connectedStatus));
  }),

  rest.get('/api/gdrive/list-files', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        files: [
          {
            id: 'f1',
            name: 'Projects',
            isFolder: true,
            mimeType: 'application/vnd.google-apps.folder',
            modifiedTime: '2024-01-15T10:00:00Z',
            size: 0,
            webViewLink: '',
          },
          {
            id: 'f2',
            name: 'deck.pdf',
            isFolder: false,
            mimeType: 'application/pdf',
            modifiedTime: '2024-01-14T10:00:00Z',
            size: 2097152,
            webViewLink: 'https://drive.google.com/f2',
          },
        ],
        nextPageToken: null,
      })
    );
  }),

  rest.post('/api/auth/gdrive/disconnect', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ success: true }));
  }),
];

const setNotConnected = () => {
  server.use(
    rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
      return res(ctx.status(200), ctx.json({ isConnected: false, reason: 'Not connected' }));
    })
  );
};

describe('GoogleDriveIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...gdriveHandlers);
  });

  // Test 1: renders component
  test('renders component', async () => {
    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /google drive integration/i })
      ).toBeInTheDocument();
    });
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setNotConnected();

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect google drive/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setNotConnected();

    render(<GoogleDriveIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect google drive/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when connection status is healthy
  test('shows connected state when connection status is healthy', async () => {
    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays files and folders after connection
  test('displays files and folders after connection', async () => {
    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument();
      expect(screen.getByText('deck.pdf')).toBeInTheDocument();
    });
  });

  // Test 6: handles connection error as disconnected
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/gdrive/connection-status', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<GoogleDriveIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect google drive/i })
      ).toBeInTheDocument();
    });
  });

  // Test 7: disconnect button is clickable without crashing
  test('disconnect button is clickable without crashing', async () => {
    render(<GoogleDriveIntegration />);

    const disconnectButton = await screen.findByRole('button', {
      name: /disconnect google drive/i,
    });
    expect(() => fireEvent.click(disconnectButton)).not.toThrow();
  });
});
