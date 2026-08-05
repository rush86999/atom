/**
 * TrelloIntegration Component Tests
 *
 * Tests verify the real Trello integration component:
 * - Health check / connection state
 * - OAuth connect flow
 * - Profile and board data loading
 * - Board search filtering and create-board dialog
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 *
 * Source: components/TrelloIntegration.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import TrelloIntegration from '@/components/TrelloIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const trelloHandlers = [
  rest.get('/api/integrations/trello/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.post('/api/integrations/trello/profile', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          profile: {
            id: 'u1',
            fullName: 'Rushi Parikh',
            username: 'rushi',
            initials: 'RP',
            avatarUrl: '',
          },
        },
      })
    );
  }),

  rest.post('/api/integrations/trello/boards', (req, res, ctx) => {
    return res(
      ctx.status(200),
      ctx.json({
        data: {
          boards: [
            { id: 'b1', name: 'Website Redesign', desc: 'Marketing site', pinned: true, prefs: { backgroundColor: '#0079BF' } },
            { id: 'b2', name: 'Mobile App', desc: 'iOS and Android', pinned: false, prefs: { backgroundColor: '#D29034' } },
          ],
        },
      })
    );
  }),

  rest.post('/api/integrations/trello/lists', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { lists: [] } }));
  }),
  rest.post('/api/integrations/trello/cards', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { cards: [] } }));
  }),
  rest.post('/api/integrations/trello/members', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ data: { members: [] } }));
  }),
];

const setDisconnected = () => {
  server.use(
    rest.get('/api/integrations/trello/health', (req, res, ctx) => {
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

describe('TrelloIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    server.resetHandlers();
    server.use(...trelloHandlers);
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<TrelloIntegration />);

    expect(
      screen.getByRole('heading', { name: /trello integration/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows connect button when not connected
  test('shows connect button when not connected', async () => {
    setDisconnected();

    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect trello account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 3: connect button is clickable without crashing (jsdom logs the
  // navigation attempt; the target is a static constant)
  test('connect button initiates connection flow', async () => {
    setDisconnected();

    render(<TrelloIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect trello account/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();
  });

  // Test 4: shows connected state when health check passes
  test('shows connected state when health check passes', async () => {
    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Connected')).toBeInTheDocument();
    });
  });

  // Test 5: displays user profile after connection
  test('displays user profile after connection', async () => {
    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Rushi Parikh')).toBeInTheDocument();
    });
  });

  // Test 6: displays boards in the default Boards tab
  test('displays boards in the default Boards tab', async () => {
    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(screen.getByText('Website Redesign')).toBeInTheDocument();
      expect(screen.getByText('Mobile App')).toBeInTheDocument();
    });
  });

  // Test 7: filters boards by search query
  test('filters boards by search query', async () => {
    render(<TrelloIntegration />);

    await settleData(/Website Redesign/);

    const searchInput = screen.getByPlaceholderText(/search boards/i);
    fireEvent.change(searchInput, { target: { value: 'Mobile' } });

    await waitFor(() => {
      expect(screen.getByText('Mobile App')).toBeInTheDocument();
    });
    expect(screen.queryByText('Website Redesign')).not.toBeInTheDocument();
  });

  // Test 8: opens create board dialog
  test('opens create board dialog', async () => {
    render(<TrelloIntegration />);

    const createButton = await screen.findByRole('button', {
      name: /create board/i,
    });
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  // Test 9: handles connection error
  test('handles connection error', async () => {
    server.use(
      rest.get('/api/integrations/trello/health', (req, res, ctx) => {
        return res(ctx.status(500));
      })
    );

    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /connect trello account/i })
      ).toBeInTheDocument();
    });
  });

  // Test 10: shows refresh status button
  test('shows refresh status button', async () => {
    render(<TrelloIntegration />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /refresh status/i })).toBeInTheDocument();
    });
  });
});
