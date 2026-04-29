/**
 * Trello Integration Component Tests
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import TrelloIntegration from '../TrelloIntegration';

describe('TrelloIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Trello integration component', () => {
    renderWithProviders(<TrelloIntegration />);
    expect(screen.getByText(/trello/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/trello/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://trello.com/1/authorize',
          })
        );
      })
    );

    renderWithProviders(<TrelloIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('trello.com');
    });
  });

  it('fetches boards', async () => {
    server.use(
      rest.get('/api/integrations/trello/boards', (req, res, ctx) => {
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

    renderWithProviders(<TrelloIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test Board')).toBeInTheDocument();
    });
  });
});
