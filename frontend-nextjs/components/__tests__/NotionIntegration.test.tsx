/**
 * Notion Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/handlers';
import NotionIntegration from '../NotionIntegration';

describe('NotionIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders Notion integration component', () => {
    render(<NotionIntegration />);
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

    render(<NotionIntegration />);

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

    render(<NotionIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText('Test page')).toBeInTheDocument();
    });
  });
});
