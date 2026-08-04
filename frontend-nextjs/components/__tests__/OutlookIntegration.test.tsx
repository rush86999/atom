/**
 * Outlook Integration Component Tests
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import OutlookIntegration from '../OutlookIntegration';

describe('OutlookIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Outlook integration component', () => {
    renderWithProviders(<OutlookIntegration />);
    expect(screen.getByText(/outlook/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection and forwards the auth token', async () => {
    const user = userEvent.setup();
    localStorage.setItem('auth_token', 'test-jwt-token');

    let capturedAuthHeader: string | null = null;
    server.use(
      rest.get('/api/integrations/outlook/health', (req, res, ctx) => {
        return res(ctx.status(500));
      }),
      rest.get('/api/auth/outlook/authorize', (req, res, ctx) => {
        capturedAuthHeader = req.headers.get('Authorization');
        return res(
          ctx.status(200),
          ctx.json({
            auth_url: 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
          })
        );
      })
    );

    renderWithProviders(<OutlookIntegration />);

    const connectButton = await screen.findByRole('button', {
      name: /connect/i,
    });
    await user.click(connectButton);

    // B7 integration: the secured /api/auth/outlook/authorize endpoint now
    // requires a valid token (Plan 315). The connect flow must forward it.
    // (Redirect navigation is not assertable in jsdom — same limitation as
    // the Asana/Box connect tests; the token forwarding is the B7 contract.)
    await waitFor(() => {
      expect(capturedAuthHeader).toBe('Bearer test-jwt-token');
    });
  });

  it('fetches emails', async () => {
    server.use(
      rest.post('/api/integrations/outlook/emails', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            data: {
              emails: [
                { id: '1', subject: 'Test email', from: { name: 'A', email: 'a@x.com' } },
              ],
            },
          })
        );
      })
    );

    renderWithProviders(<OutlookIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test email')).toBeInTheDocument();
    });
  });
});
