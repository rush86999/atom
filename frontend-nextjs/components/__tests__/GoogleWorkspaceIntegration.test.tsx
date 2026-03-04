/**
 * Google Workspace Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import GoogleWorkspaceIntegration from '../GoogleWorkspaceIntegration';

describe('GoogleWorkspaceIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Google Workspace integration component', () => {
    render(<GoogleWorkspaceIntegration />);
    expect(screen.getByText(/google workspace|g suite/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/google/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
          })
        );
      })
    );

    render(<GoogleWorkspaceIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('accounts.google.com');
    });
  });

  it('fetches Google Drive files', async () => {
    server.use(
      rest.get('/api/integrations/google/drive/files', (req, res, ctx) => {
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

    render(<GoogleWorkspaceIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('test-file.pdf')).toBeInTheDocument();
    });
  });
});
