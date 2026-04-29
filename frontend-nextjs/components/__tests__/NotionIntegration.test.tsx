/**
 * Notion Integration Component Tests
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import NotionIntegration from '../NotionIntegration';

describe('NotionIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Notion integration component', () => {
    renderWithProviders(<NotionIntegration />);
    expect(screen.getByText(/notion/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/notion/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://api.notion.com/oauth/authorize',
          })
        );
      })
    );

    renderWithProviders(<NotionIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('notion.com');
    });
  });

  it('fetches pages', async () => {
    server.use(
      rest.get('/api/integrations/notion/pages', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            pages: [
              { id: '1', title: 'Test page' },
            ],
          })
        );
      })
    );

    renderWithProviders(<NotionIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test page')).toBeInTheDocument();
    });
  });
});
