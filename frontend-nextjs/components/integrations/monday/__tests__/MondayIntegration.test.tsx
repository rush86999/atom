/**
 * MondayIntegration Component Tests
 *
 * Tests verify the real Monday integration component
 * (components/integrations/monday/MondayIntegration.tsx):
 * - Not-connected state with "Connect Monday.com" OAuth flow
 *   (GET /api/integrations/monday/authorize)
 * - Connected state: boards + health load, analytics cards, item loading
 * - Disconnect flow
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import MondayIntegration from '@/components/integrations/monday/MondayIntegration';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const boards = [
  {
    id: 'b1',
    name: 'Test Board',
    description: 'A board for testing',
    board_kind: 'public',
    updated_at: '2026-04-20T10:00:00Z',
    items_count: 5,
    columns: [{ id: 'col1', title: 'Status', type: 'status' }],
  },
  {
    id: 'b2',
    name: 'Marketing Board',
    board_kind: 'private',
    updated_at: '2026-04-19T10:00:00Z',
    items_count: 3,
    columns: [],
  },
];

const boardItems = [
  {
    id: 'i1',
    name: 'Test Item',
    created_at: '2026-04-10T10:00:00Z',
    updated_at: '2026-04-20T10:00:00Z',
    state: 'active',
    column_values: [{ id: 'col1', text: 'Working', value: '{}', type: 'status' }],
  },
];

// Track authorize requests so the OAuth flow can be verified (window.location
// navigation is not implemented in jsdom).
let authorizeRequests = 0;

const mondayHandlers = [
  rest.get('/api/integrations/monday/boards', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ boards }));
  }),

  rest.get('/api/integrations/monday/health', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ status: 'healthy' }));
  }),

  rest.get('/api/integrations/monday/boards/:boardId/items', (req, res, ctx) => {
    return res(ctx.status(200), ctx.json({ items: boardItems }));
  }),

  rest.get('/api/integrations/monday/authorize', (req, res, ctx) => {
    authorizeRequests += 1;
    return res(
      ctx.status(200),
      ctx.json({ authorization_url: 'https://auth.monday.com/oauth2/authorize' })
    );
  }),
];

describe('MondayIntegration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    authorizeRequests = 0;
    server.resetHandlers();
    server.use(...mondayHandlers);
  });

  // Test 1: renders the connect screen when no access token
  test('renders connect screen when not connected', () => {
    render(<MondayIntegration onConnect={jest.fn()} onDisconnect={jest.fn()} />);

    expect(
      screen.getByRole('heading', { name: /connect monday\.com/i })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /connect monday\.com/i })
    ).toBeInTheDocument();
  });

  // Test 2: connect button initiates the OAuth authorize flow
  test('connect button initiates OAuth authorize flow', async () => {
    render(<MondayIntegration onConnect={jest.fn()} onDisconnect={jest.fn()} />);

    const connectButton = screen.getByRole('button', {
      name: /connect monday\.com/i,
    });
    expect(() => fireEvent.click(connectButton)).not.toThrow();

    await waitFor(() => {
      expect(authorizeRequests).toBe(1);
    });
  });

  // Test 3: shows connected state with boards after connecting
  test('shows connected state with boards', async () => {
    render(
      <MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />
    );

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /monday\.com integration/i })
      ).toBeInTheDocument();
      expect(screen.getByText('Test Board')).toBeInTheDocument();
      expect(screen.getByText('Marketing Board')).toBeInTheDocument();
    });
  });

  // Test 4: displays health status badge
  test('displays health status badge', async () => {
    render(
      <MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('healthy')).toBeInTheDocument();
    });
  });

  // Test 5: displays analytics cards
  test('displays analytics cards', async () => {
    render(
      <MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('Total Boards')).toBeInTheDocument();
      expect(screen.getByText('Total Items')).toBeInTheDocument();
      expect(screen.getByText('Active')).toBeInTheDocument();
    });
  });

  // Test 6: loads items when a board is clicked
  test('loads board items when a board is clicked', async () => {
    render(
      <MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />
    );

    const boardCard = await screen.findByText('Test Board');
    fireEvent.click(boardCard);

    await waitFor(() => {
      expect(screen.getByText('Test Item')).toBeInTheDocument();
      expect(screen.getByText('active')).toBeInTheDocument();
    });
  });

  // Test 7: shows empty state when no boards are found
  test('shows empty state when no boards', async () => {
    server.use(
      rest.get('/api/integrations/monday/boards', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json({ boards: [] }));
      })
    );

    render(
      <MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />
    );

    await waitFor(() => {
      expect(screen.getByText('No boards found')).toBeInTheDocument();
    });
  });

  // Test 8: disconnect button calls onDisconnect
  test('disconnect button calls onDisconnect', async () => {
    const onDisconnect = jest.fn();
    render(
      <MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={onDisconnect} />
    );

    const disconnectButton = await screen.findByRole('button', {
      name: /disconnect/i,
    });
    fireEvent.click(disconnectButton);

    expect(onDisconnect).toHaveBeenCalledTimes(1);
  });

  // Test 9: Search tab shows the search input
  test('shows search input on the Search tab', async () => {
    render(
      <MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />
    );

    await screen.findByText('Test Board');

    fireEvent.click(screen.getByRole('button', { name: 'Search' }));

    await waitFor(() => {
      expect(screen.getByText('Search Items')).toBeInTheDocument();
      expect(
        screen.getByPlaceholderText(/search across all boards/i)
      ).toBeInTheDocument();
    });
  });
});
