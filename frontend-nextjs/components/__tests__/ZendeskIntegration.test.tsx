/**
 * Zendesk Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import ZendeskIntegration from '../ZendeskIntegration';

describe('ZendeskIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Zendesk integration component', () => {
    render(<ZendeskIntegration />);
    expect(screen.getByText(/zendesk/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/zendesk/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://zendesk.com/oauth/authorize',
          })
        );
      })
    );

    render(<ZendeskIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('zendesk.com');
    });
  });

  it('fetches tickets', async () => {
    server.use(
      rest.get('/api/integrations/zendesk/tickets', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            tickets: [
              { id: '1', subject: 'Test ticket', status: 'open' },
            ],
          })
        );
      })
    );

    render(<ZendeskIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test ticket')).toBeInTheDocument();
    });
  });
});
