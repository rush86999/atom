/**
 * HubSpotPredictiveAnalytics Component Tests
 *
 * Tests verify the real HubSpotPredictiveAnalytics component
 * (components/integrations/hubspot/HubSpotPredictiveAnalytics.tsx) — a pure
 * props-driven analytics dashboard. It makes no network calls (no MSW
 * handlers needed); models / predictions / forecast are passed in as props.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import HubSpotPredictiveAnalytics from '@/components/integrations/hubspot/HubSpotPredictiveAnalytics';

const mockModels = [
  {
    id: 'm1',
    name: 'Conversion Model',
    type: 'conversion' as const,
    accuracy: 85.5,
    lastTrained: '2026-04-20',
    status: 'active' as const,
    features: ['email', 'company'],
    performance: { precision: 0.85, recall: 0.8, f1Score: 0.82, auc: 0.88 },
  },
];

const mockPredictions = [
  {
    contactId: 'contact-123456',
    prediction: 0.85,
    confidence: 90,
    factors: [{ feature: 'email_engagement', impact: 0.5, value: 'high' }],
    recommendation: 'Contact within 24 hours',
    timeframe: '7d',
  },
];

const mockForecast = [
  {
    period: '2026-04',
    predicted: 50000,
    lowerBound: 45000,
    upperBound: 55000,
    confidence: 85,
  },
  {
    period: '2026-05',
    predicted: 55000,
    actual: 53000,
    lowerBound: 50000,
    upperBound: 60000,
    confidence: 80,
  },
];

describe('HubSpotPredictiveAnalytics', () => {
  // Test 1: renders component with no props (defaults to empty data)
  test('renders component', () => {
    render(<HubSpotPredictiveAnalytics />);

    expect(
      screen.getByRole('heading', { name: /predictive analytics/i })
    ).toBeInTheDocument();
  });

  // Test 2: shows empty state when no models are available
  test('shows empty state when no models', () => {
    render(<HubSpotPredictiveAnalytics models={[]} predictions={[]} forecast={[]} />);

    expect(screen.getByText('No Models Available')).toBeInTheDocument();
  });

  // Test 3: displays active models with status and accuracy
  test('displays active models', () => {
    render(<HubSpotPredictiveAnalytics models={mockModels} />);

    expect(screen.getByText('Active Models')).toBeInTheDocument();
    expect(screen.getByText('Conversion Model')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
    expect(screen.getByText('Accuracy')).toBeInTheDocument();
  });

  // Test 4: formats model accuracy and precision percentages
  test('formats values correctly', () => {
    render(<HubSpotPredictiveAnalytics models={mockModels} />);

    expect(screen.getByText('85.5%')).toBeInTheDocument();
    expect(screen.getByText('85.0%')).toBeInTheDocument(); // precision
  });

  // Test 5: displays the model selection dropdown
  test('displays model selection dropdown', () => {
    render(<HubSpotPredictiveAnalytics models={mockModels} />);

    expect(screen.getByText('Prediction Model')).toBeInTheDocument();
    expect(screen.getByText('Timeframe')).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: 'Conversion Model (conversion)' })
    ).toBeInTheDocument();
  });

  // Test 6: displays predictions table when data is available
  test('displays predictions table', () => {
    render(<HubSpotPredictiveAnalytics predictions={mockPredictions} />);

    expect(screen.getByText('Recent Predictions')).toBeInTheDocument();
    expect(screen.getByText('1 High Confidence')).toBeInTheDocument();
    expect(screen.getByText('Contact #123456')).toBeInTheDocument();
    expect(screen.getByText('Contact within 24 hours')).toBeInTheDocument();
  });

  // Test 7: displays forecast visualization
  test('displays forecast visualization', () => {
    render(<HubSpotPredictiveAnalytics forecast={mockForecast} />);

    expect(screen.getByText('Revenue Forecast')).toBeInTheDocument();
    expect(screen.getByText('$50,000')).toBeInTheDocument();
    expect(screen.getByText('Actual: $53,000')).toBeInTheDocument();
  });

  // Test 8: displays forecast performance metrics
  test('displays forecast performance', () => {
    render(
      <HubSpotPredictiveAnalytics
        models={mockModels}
        predictions={mockPredictions}
        forecast={mockForecast}
      />
    );

    expect(screen.getByText('Forecast Performance')).toBeInTheDocument();
    expect(screen.getByText('Forecast Accuracy')).toBeInTheDocument();
    expect(screen.getByText('Active Predictions')).toBeInTheDocument();
  });
});
