/**
 * Asana Integration Component Tests
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import AsanaIntegration from '../AsanaIntegration';

describe('AsanaIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Asana integration component', () => {
    renderWithProviders(<AsanaIntegration />);
    expect(screen.getByText(/asana/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/asana/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://app.asana.com/oauth/authorize',
          })
        );
      })
    );

    renderWithProviders(<AsanaIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('app.asana.com');
    });
  });

  it('fetches tasks', async () => {
    server.use(
      rest.get('/api/integrations/asana/tasks', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            tasks: [
              { id: '1', name: 'Test task' },
            ],
          })
        );
      })
    );

    renderWithProviders(<AsanaIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test task')).toBeInTheDocument();
    });
  });
});
