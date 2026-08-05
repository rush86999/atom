/**
 * BoxIntegration Component Tests
 *
 * Tests verify the real Box integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile and folder/file data loading
 * - File & folder search filtering
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/BoxIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import BoxIntegration from '@/components/BoxIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const boxHandlers = [
  rest.get('/api/integrations/box/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/box/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            name: 'Rushi Parikh',
            login: 'rushi@example.com',
            avatar_url: '',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/box/folder/:folderId', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          folder: {
            id: '0',
            name: 'All Files',
            item_collection: {
              entries: [
                { type: 'folder', id: 'f1', name: 'Marketing', item_collection: { entries: [] } },
                { type: 'file', id: 'x1', name: 'roadmap.pdf', size: 1024, modified_at: '2024-01-15T10:00:00Z' },
                { type: 'file', id: 'x2', name: 'budget.xlsx', size: 2048, modified_at: '2024-01-14T10:00:00Z' },
              ],
            },
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/box/users', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { users: [] } }));
  }),
  rest.post('/api/integrations/box/collaborations', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { collaborations: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/box/health', (req, res, ctx) => {
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

describe('BoxIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...boxHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<BoxIntegration />);

    expect(
      screen.getByRole('heading', { name: /box integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<BoxIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect box account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<BoxIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect box account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<BoxIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<BoxIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays files and folders in the default Files tab
  test('displays files and folders in the default Files tab', async () => {
    render(<BoxIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Marketing')).toBeInTheDocument();
      expect(screen.getByText('roadmap.pdf')).toBeInTheDocument();
      expect(screen.getByText('budget.xlsx')).toBeInTheDocument();
    });
  });

  // Test 7: filters files by search query
  test('filters files by search query', async () => {
    render(<BoxIntegration />);

    await settleData(/roadmap.pdf/);

    const searchInput = screen.getByPlaceholderText(/search files and folders/i);
    fireEvent.change(searchInput, { target: { value: 'budget' } });

    await waitFor(() => {
      expect(screen.getByText('budget.xlsx')).toBeInTheDocument();
    });
    expect(screen.queryByText('roadmap.pdf')).not.toBeInTheDocument();
  });

  // Test 8: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/box/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<BoxIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect box account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 9: shows refresh status button
  test('shows refresh status button', async () => {
    render(<BoxIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});
