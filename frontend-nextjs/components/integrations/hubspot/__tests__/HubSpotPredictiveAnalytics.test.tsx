/**
 * HubSpot Predictive Analytics Component Tests
 *
 * Test suite for HubSpot predictive lead scoring and CRM analytics
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '../../../tests/mocks/handlers';
import HubSpotPredictiveAnalytics from '../HubSpotPredictiveAnalytics';

describe('HubSpotPredictiveAnalytics Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders HubSpot predictive analytics component', () => {
    render(<HubSpotPredictiveAnalytics />);
    expect(screen.getByText(/hubspot|predictive|analytics/i)).toBeInTheDocument();
  });

  it('fetches lead scoring data', async () => {
    server.use(
      rest.get('/api/integrations/hubspot/lead-scores', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            leads: [
              { id: '1', email: 'test@example.com', score: 85, likelihood: 0.92 },
            ],
          })
        );
      })
    );

    render(<HubSpotPredictiveAnalytics connected={true} />);

    await waitFor(() => {
      expect(screen.getByText(/lead score|predictive score/i)).toBeInTheDocument();
    });
  });

  it('displays CRM sync status', async () => {
    server.use(
      rest.get('/api/integrations/hubspot/sync-status', (req, res, ctx) => {
        return res(
          ctx.status(200),
          ctx.json({
            success: true,
            status: 'synced',
            lastSync: new Date().toISOString(),
          })
        );
      })
    );

    render(<HubSpotPredictiveAnalytics connected={true} />);

    await waitFor(() => {
      expect(screen.getByText(/synced|last sync/i)).toBeInTheDocument();
    });
  });
});
