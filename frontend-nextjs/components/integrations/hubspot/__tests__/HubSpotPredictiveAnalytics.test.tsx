/**
 * HubSpot Predictive Analytics Component Tests
 *
 * Test suite for HubSpot predictive lead scoring and CRM analytics
 */

import React from 'react';
import { renderWithProviders, screen, waitFor } from '../../../../tests/test-utils';
import userEvent from '@testing-library/user-event';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';
import HubSpotPredictiveAnalytics from '../HubSpotPredictiveAnalytics';

describe('HubSpotPredictiveAnalytics Component', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('renders HubSpot predictive analytics component', () => {
    renderWithProviders(<HubSpotPredictiveAnalytics />);
    expect(screen.getByText(/hubspot|predictive|analytics/i)).toBeInTheDocument();
  });

  it('renders predictive analytics dashboard', () => {
    renderWithProviders(<HubSpotPredictiveAnalytics />);
    expect(screen.getByText('Predictive Analytics')).toBeInTheDocument();
  });

  it('shows metric cards/charts', () => {
    const mockModels = [
      {
        id: '1',
        name: 'Conversion Model',
        type: 'conversion' as const,
        accuracy: 85,
        lastTrained: '2026-04-20',
        status: 'active' as const,
        features: ['email', 'company'],
        performance: { precision: 0.85, recall: 0.80, f1Score: 0.82, auc: 0.88 }
      }
    ];

    renderWithProviders(<HubSpotPredictiveAnalytics models={mockModels} />);

    expect(screen.getByText('Active Models')).toBeInTheDocument();
    expect(screen.getByText('Forecast Performance')).toBeInTheDocument();
  });

  it('handles loading state', () => {
    renderWithProviders(<HubSpotPredictiveAnalytics />);
    // Component should render without crashing even with empty props
    expect(screen.getByText('Predictive Analytics')).toBeInTheDocument();
  });

  it('handles empty data state', () => {
    renderWithProviders(<HubSpotPredictiveAnalytics models={[]} predictions={[]} forecast={[]} />);

    expect(screen.getByText('No Models Available')).toBeInTheDocument();
  });

  it('formats values correctly (percentages, currency, etc)', () => {
    const mockModels = [
      {
        id: '1',
        name: 'Test Model',
        type: 'conversion' as const,
        accuracy: 85.5,
        lastTrained: '2026-04-20',
        status: 'active' as const,
        features: [],
        performance: { precision: 0.85, recall: 0.80, f1Score: 0.82, auc: 0.88 }
      }
    ];

    renderWithProviders(<HubSpotPredictiveAnalytics models={mockModels} />);

    expect(screen.getByText('85.5%')).toBeInTheDocument();
    expect(screen.getByText('85.0%')).toBeInTheDocument(); // precision
  });

  it('displays model selection dropdown', () => {
    const mockModels = [
      {
        id: 'model-1',
        name: 'Conversion Model',
        type: 'conversion' as const,
        accuracy: 85,
        lastTrained: '2026-04-20',
        status: 'active' as const,
        features: [],
        performance: { precision: 0.85, recall: 0.80, f1Score: 0.82, auc: 0.88 }
      }
    ];

    renderWithProviders(<HubSpotPredictiveAnalytics models={mockModels} />);

    expect(screen.getByText('Prediction Model')).toBeInTheDocument();
    expect(screen.getByText('Timeframe')).toBeInTheDocument();
  });

  it('displays predictions table when data available', () => {
    const mockPredictions = [
      {
        contactId: 'contact-123',
        prediction: 0.85,
        confidence: 90,
        factors: [{ feature: 'email_engagement', impact: 0.5, value: 'high' }],
        recommendation: 'Contact within 24 hours',
        timeframe: '7d'
      }
    ];

    renderWithProviders(<HubSpotPredictiveAnalytics predictions={mockPredictions} />);

    expect(screen.getByText('Recent Predictions')).toBeInTheDocument();
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

    renderWithProviders(<HubSpotPredictiveAnalytics connected={true} />);

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

    renderWithProviders(<HubSpotPredictiveAnalytics connected={true} />);

    await waitFor(() => {
      expect(screen.getByText(/synced|last sync/i)).toBeInTheDocument();
    });
  });

  it('displays forecast visualization', () => {
    const mockForecast = [
      {
        period: '2026-04',
        predicted: 50000,
        lowerBound: 45000,
        upperBound: 55000,
        confidence: 85
      },
      {
        period: '2026-05',
        predicted: 55000,
        actual: 53000,
        lowerBound: 50000,
        upperBound: 60000,
        confidence: 80
      }
    ];

    renderWithProviders(<HubSpotPredictiveAnalytics forecast={mockForecast} />);

    expect(screen.getByText('Revenue Forecast')).toBeInTheDocument();
    expect(screen.getByText('$50,000')).toBeInTheDocument();
    expect(screen.getByText('$53,000')).toBeInTheDocument(); // actual value
  });
});
