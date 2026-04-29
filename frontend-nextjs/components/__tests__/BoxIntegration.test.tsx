/**
 * Box Integration Component Tests
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import BoxIntegration from '../BoxIntegration';

describe('BoxIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Box integration component', () => {
    renderWithProviders(<BoxIntegration />);
    expect(screen.getByText(/box/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/box/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://account.box.com/api/oauth2/authorize',
          })
        );
      })
    );

    renderWithProviders(<BoxIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('account.box.com');
    });
  });

  it('fetches files', async () => {
    server.use(
      rest.get('/api/integrations/box/files', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            files: [
              { id: '1', name: 'test-file.pdf' },
            ],
          })
        );
      })
    );

    renderWithProviders(<BoxIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('test-file.pdf')).toBeInTheDocument();
    });
  });
});
