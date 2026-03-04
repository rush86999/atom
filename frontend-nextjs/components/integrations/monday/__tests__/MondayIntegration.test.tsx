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
});
