/**
 * Trello Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/handlers';
import TrelloIntegration from '../TrelloIntegration';

describe('TrelloIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Trello integration component', () => {
    render(<TrelloIntegration />);
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

    render(<TrelloIntegration />);

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

    render(<TrelloIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test Board')).toBeInTheDocument();
    });
  });
});
