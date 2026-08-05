/**
 * HubSpotAIService Component Tests
 *
 * Tests verify the real HubSpot AI lead-scoring component
 * (components/integrations/hubspot/HubSpotAIService.tsx):
 * - AI configuration panel (model selector, factor weights, thresholds,
 *   automation toggles, custom prompt)
 * - Lead analysis flow (POST /api/hubspot/ai/analyze-lead)
 * - Prediction result rendering (score, key factors, recommendations, stats)
 * - Error handling and disabled state
 *
 * Uses the shared MSW server (tests/mocks/server.ts) registered in
 * tests/setup.ts — per-file setupServer() does NOT override the global server.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import HubSpotAIService from '@/components/integrations/hubspot/HubSpotAIService';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const mockContact = {
  id: 'contact-123',
  email: 'test@example.com',
  name: 'Test Contact',
};

const mockPrediction = {
  leadScore: 85,
  confidence: 92,
  predictedValue: 25000,
  conversionProbability: 78,
  timeframe: '2-3 weeks',
  keyFactors: [
    { factor: 'Engagement', impact: 0.42, description: 'High email and website interaction' },
    { factor: 'Demographics', impact: 0.3, description: 'Fits target customer profile' },
    { factor: 'Behavior', impact: 0.28, description: 'Recent product interest' },
  ],
  recommendations: [
    { action: 'Immediate follow-up', priority: 'high' as const, description: 'Contact within 24 hours' },
    { action: 'Send personalized demo', priority: 'medium' as const, description: 'Schedule product demo' },
    { action: 'Add to nurture campaign', priority: 'low' as const, description: 'Include in email sequence' },
  ],
};

// Captures the last analyze request body so the payload can be verified.
let lastBody: any = null;

const aiHandlers = [
  rest.post('/api/hubspot/ai/analyze-lead', (req, res, ctx) => {
    lastBody = typeof req.body === 'string' ? JSON.parse(req.body) : req.body;
    return res(ctx.status(200), ctx.json(mockPrediction));
  }),
];

describe('HubSpotAIService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    lastBody = null;
    server.resetHandlers();
    server.use(...aiHandlers);
  });

  // Test 1: renders AI configuration panel
  test('renders AI configuration panel', () => {
    render(<HubSpotAIService contact={mockContact} />);

    expect(screen.getByText('AI Lead Scoring')).toBeInTheDocument();
    expect(screen.getByText('Enabled')).toBeInTheDocument();
  });

  // Test 2: renders scoring model selector with options
  test('renders scoring model selector with options', () => {
    render(<HubSpotAIService contact={mockContact} />);

    expect(screen.getByText('Scoring Model')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Enhanced Scoring' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Predictive Analytics' })).toBeInTheDocument();
  });

  // Test 3: displays scoring factor weights
  test('displays scoring factor weights', () => {
    render(<HubSpotAIService contact={mockContact} />);

    expect(screen.getByText('Scoring Factors Weight')).toBeInTheDocument();
    expect(screen.getByText('engagement')).toBeInTheDocument();
    expect(screen.getByText('demographics')).toBeInTheDocument();
    expect(screen.getByText('behavior')).toBeInTheDocument();
  });

  // Test 4: displays score threshold inputs
  test('displays score thresholds', () => {
    render(<HubSpotAIService contact={mockContact} />);

    expect(screen.getByText('Score Thresholds')).toBeInTheDocument();
    expect(screen.getByText('hot Lead')).toBeInTheDocument();
    expect(screen.getByText('warm Lead')).toBeInTheDocument();
    expect(screen.getByText('cold Lead')).toBeInTheDocument();
  });

  // Test 5: displays automation toggles
  test('displays automation toggles', () => {
    render(<HubSpotAIService contact={mockContact} />);

    expect(screen.getByText('Automation')).toBeInTheDocument();
    expect(screen.getByText('auto Assign')).toBeInTheDocument();
    expect(screen.getByText('auto Followup')).toBeInTheDocument();
    expect(screen.getByText('smart Segmentation')).toBeInTheDocument();
  });

  // Test 6: renders analyze lead button when a contact is provided
  test('renders analyze lead button', () => {
    render(<HubSpotAIService contact={mockContact} />);

    expect(screen.getByText('Lead Analysis')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /analyze lead/i })).toBeInTheDocument();
  });

  // Test 7: shows empty state before analysis
  test('shows empty state before analysis', () => {
    render(<HubSpotAIService contact={mockContact} />);

    expect(
      screen.getByText(/click "analyze lead" to get ai-powered insights/i)
    ).toBeInTheDocument();
  });

  // Test 8: performs lead analysis and displays results
  test('performs lead analysis and displays results', async () => {
    const onScoreUpdate = jest.fn();
    render(<HubSpotAIService contact={mockContact} onScoreUpdate={onScoreUpdate} />);

    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(screen.getByText('Hot Lead')).toBeInTheDocument();
      expect(screen.getByText('85')).toBeInTheDocument();
    });

    // Request payload reflects the contact id + default model
    expect(lastBody.contact_id).toBe('contact-123');
    expect(lastBody.model_id).toBe('enhanced');
    expect(onScoreUpdate).toHaveBeenCalledWith(mockPrediction);
  });

  // Test 9: displays error state when analysis fails
  test('displays error state when analysis fails', async () => {
    server.use(
      rest.post('/api/hubspot/ai/analyze-lead', (req, res, ctx) => {
        return res(ctx.status(500), ctx.json({ detail: 'Internal server error' }));
      })
    );

    render(<HubSpotAIService contact={mockContact} />);

    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(screen.getByText('Analysis Failed')).toBeInTheDocument();
      expect(screen.getByText('Internal server error')).toBeInTheDocument();
    });
  });

  // Test 10: displays key factors with impact percentages
  test('displays key factors with impact percentages', async () => {
    render(<HubSpotAIService contact={mockContact} />);

    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(screen.getByText('Key Scoring Factors')).toBeInTheDocument();
      expect(screen.getByText('Engagement')).toBeInTheDocument();
      expect(screen.getByText('42%')).toBeInTheDocument();
    });
  });

  // Test 11: displays AI recommendations with priority badges
  test('displays AI recommendations with priority badges', async () => {
    render(<HubSpotAIService contact={mockContact} />);

    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(screen.getByText('AI Recommendations')).toBeInTheDocument();
      expect(screen.getByText('Immediate follow-up')).toBeInTheDocument();
      expect(screen.getByText('high')).toBeInTheDocument();
    });
  });

  // Test 12: displays prediction statistics
  test('displays prediction statistics', async () => {
    render(<HubSpotAIService contact={mockContact} />);

    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(screen.getByText('Conversion Probability')).toBeInTheDocument();
      expect(screen.getByText('78%')).toBeInTheDocument();
      expect(screen.getByText('Expected Timeline')).toBeInTheDocument();
      expect(screen.getByText('2-3 weeks')).toBeInTheDocument();
      expect(screen.getByText('Predicted Value')).toBeInTheDocument();
    });
  });

  // Test 13: displays custom analysis prompt textarea
  test('displays custom analysis prompt textarea', () => {
    render(<HubSpotAIService contact={mockContact} />);

    const textarea = screen.getByPlaceholderText('Add specific criteria for AI analysis...');
    expect(textarea).toBeInTheDocument();

    fireEvent.change(textarea, { target: { value: 'Focus on recent engagement' } });
    expect(textarea).toHaveValue('Focus on recent engagement');
  });

  // Test 14: displays automation triggers section
  test('displays AI automation triggers section', () => {
    render(<HubSpotAIService contact={mockContact} />);

    expect(screen.getByText('AI Automation Triggers')).toBeInTheDocument();
    expect(screen.getByText('Hot Lead Trigger')).toBeInTheDocument();
    expect(screen.getByText('Behavioral Trigger')).toBeInTheDocument();
  });

  // Test 15: toggling the enabled checkbox shows the disabled state
  test('shows disabled state when AI scoring is disabled', () => {
    render(<HubSpotAIService contact={mockContact} />);

    fireEvent.click(screen.getAllByRole('checkbox')[0]);

    expect(
      screen.getByText('AI-powered lead scoring is currently disabled')
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /enable ai scoring/i })
    ).toBeInTheDocument();
  });
});
