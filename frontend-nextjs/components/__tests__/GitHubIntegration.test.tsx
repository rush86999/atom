/**
 * GitHub Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/handlers';
import GitHubIntegration from '../GitHubIntegration';

describe('GitHubIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders GitHub integration component', () => {
    render(<GitHubIntegration />);
    expect(screen.getByText(/github/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/github/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://github.com/login/oauth/authorize',
          })
        );
      })
    );

    render(<GitHubIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('github.com');
    });
  });

  it('fetches repositories', async () => {
    server.use(
      rest.get('/api/integrations/github/repos', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            repos: [
              { id: 1, name: 'test-repo', full_name: 'user/test-repo' },
            ],
          })
        );
      })
    );

    render(<GitHubIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('test-repo')).toBeInTheDocument();
    });
  });
});
