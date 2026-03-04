/**
 * Box Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/handlers';
import BoxIntegration from '../BoxIntegration';

describe('BoxIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Box integration component', () => {
    render(<BoxIntegration />);
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

    render(<BoxIntegration />);

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

    render(<BoxIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('test-file.pdf')).toBeInTheDocument();
    });
  });
});
