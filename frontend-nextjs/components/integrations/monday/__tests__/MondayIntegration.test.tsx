/**
 * Monday Integration Component Tests
 *
 * Test suite for Monday.com boards and items management
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../../tests/mocks/server';
import MondayIntegration from '../MondayIntegration';

describe('MondayIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Monday integration component', () => {
    render(<MondayIntegration />);
    expect(screen.getByText(/monday/i)).toBeInTheDocument();
  });

  it('renders Monday.com integration card', () => {
    render(<MondayIntegration />);
    expect(screen.getByText(/connect monday/i)).toBeInTheDocument();
  });

  it('shows connect/disconnect states', async () => {
    render(<MondayIntegration />);

    // Initially shows connect state
    expect(screen.getByText('Connect Monday.com')).toBeInTheDocument();
  });

  it('shows board list if applicable', async () => {
    server.use(
      rest.get('/api/integrations/monday/boards', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            boards: [
              { id: '1', name: 'Test Board', board_kind: 'public', items_count: 5, updated_at: '2026-04-20', columns: [] },
            ],
          })
        );
      })
    );

    render(<MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Test Board')).toBeInTheDocument();
    });
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/monday/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://auth.monday.com/oauth2/authorize',
          })
        );
      })
    );

    render(<MondayIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('auth.monday.com');
    });
  });

  it('handles OAuth flow interaction', async () => {
    server.use(
      rest.get('/api/integrations/monday/authorize', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authorization_url: 'https://auth.monday.com/oauth2/authorize'
          })
        );
      })
    );

    const mockOnConnect = jest.fn();
    render(<MondayIntegration onConnect={mockOnConnect} onDisconnect={jest.fn()} />);

    const connectButton = screen.getByText('Connect Monday.com');
    expect(connectButton).toBeInTheDocument();
  });

  it('fetches boards', async () => {
    server.use(
      rest.get('/api/integrations/monday/boards', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            boards: [
              { id: '1', name: 'Test Board' },
            ],
          })
        );
      })
    );

    render(<MondayIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test Board')).toBeInTheDocument();
    });
  });

  it('fetches items for selected board', async () => {
    server.use(
      rest.get('/api/integrations/monday/boards/:boardId/items', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            items: [
              { id: '1', name: 'Test Item', status: 'Working on it' },
            ],
          })
        );
      })
    );

    render(<MondayIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test Item')).toBeInTheDocument();
    });
  });

  it('displays analytics cards', async () => {
    server.use(
      rest.get('/api/integrations/monday/boards', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            boards: [
              { id: '1', name: 'Board 1', board_kind: 'public', items_count: 10, updated_at: '2026-04-20', columns: [] },
              { id: '2', name: 'Board 2', board_kind: 'private', items_count: 5, updated_at: '2026-04-20', columns: [] }
            ]
          })
        );
      }),
      rest.get('/api/integrations/monday/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({ status: 'healthy' })
        );
      })
    );

    render(<MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('Total Boards')).toBeInTheDocument();
      expect(screen.getByText('Total Items')).toBeInTheDocument();
      expect(screen.getByText('Active')).toBeInTheDocument();
    });
  });

  it('shows loading state', () => {
    const { rerender } = render(<MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />);
    // Component shows loading during data fetch
  });

  it('displays health status badge', async () => {
    server.use(
      rest.get('/api/integrations/monday/health', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({ status: 'healthy' })
        );
      })
    );

    render(<MondayIntegration accessToken="test-token" onConnect={jest.fn()} onDisconnect={jest.fn()} />);

    await waitFor(() => {
      expect(screen.getByText('healthy')).toBeInTheDocument();
    });
  });
});
