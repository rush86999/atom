/**
 * QuickBooks Integration Component Tests
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../tests/mocks/server';
import QuickBooksIntegration from '../QuickBooksIntegration';

describe('QuickBooksIntegration Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders QuickBooks integration component', () => {
    render(<QuickBooksIntegration />);
    expect(screen.getByText(/quickbooks/i)).toBeInTheDocument();
  });

  it('initiates OAuth connection', async () => {
    const user = userEvent.setup();

    server.use(
      rest.post('/api/integrations/quickbooks/connect', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            authUrl: 'https://appcenter.intuit.com/connect/oauth2',
          })
        );
      })
    );

    render(<QuickBooksIntegration />);

    const connectButton = screen.getByRole('button', { name: /connect/i });
    await user.click(connectButton);

    await waitFor(() => {
      expect(window.location.href).toContain('intuit.com');
    });
  });

  it('fetches invoices', async () => {
    server.use(
      rest.get('/api/integrations/quickbooks/invoices', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            invoices: [
              { id: '1', total: 100.0, customerName: 'Test Customer' },
            ],
          })
        );
      })
    );

    render(<QuickBooksIntegration connected={true} />);

    await waitFor(() => {
      expect(screen.getByText(/test customer/i)).toBeInTheDocument();
    });
  });
});
