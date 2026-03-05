/**
 * Outlook Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import OutlookIntegration from '../OutlookIntegration';

describe('OutlookIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Outlook integration component', () => {
    render(<OutlookIntegration />);
    expect(screen.getByText(/outlook/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/outlook/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
          })
        );
      })
    );

    render(<OutlookIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('login.microsoftonline.com');
    });
  });

  it('fetches emails', async () => {
    server.use(
      rest.get('/api/integrations/outlook/emails', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            emails: [
              { id: '1', subject: 'Test email' },
            ],
          })
        );
      })
    );

    render(<OutlookIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test email')).toBeInTheDocument();
    });
  });
});
