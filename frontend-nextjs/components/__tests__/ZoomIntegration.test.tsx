/**
 * Zoom Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import ZoomIntegration from '../ZoomIntegration';

describe('ZoomIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Zoom integration component', () => {
    render(<ZoomIntegration />);
    expect(screen.getByText(/zoom/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/zoom/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://zoom.us/oauth/authorize',
          })
        );
      })
    );

    render(<ZoomIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('zoom.us');
    });
  });

  it('fetches meetings', async () => {
    server.use(
      rest.get('/api/integrations/zoom/meetings', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            meetings: [
              { id: '1', topic: 'Test meeting' },
            ],
          })
        );
      })
    );

    render(<ZoomIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test meeting')).toBeInTheDocument();
    });
  });
});
