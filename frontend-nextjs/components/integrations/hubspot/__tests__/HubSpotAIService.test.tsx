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

  // Test 16: the disabled view can be re-enabled inline
  test('re-enables AI scoring from the disabled view', () => {
    render(<HubSpotAIService contact={mockContact} />);

    fireEvent.click(screen.getAllByRole('checkbox')[0]);
    fireEvent.click(screen.getByRole('button', { name: /enable ai scoring/i }));

    expect(screen.getByText('AI Lead Scoring')).toBeInTheDocument();
    expect(
      screen.queryByText('AI-powered lead scoring is currently disabled')
    ).not.toBeInTheDocument();
  });

  // Test 17: warm lead band
  test('labels a mid-range score as a Warm Lead', async () => {
    server.use(
      rest.post('/api/hubspot/ai/analyze-lead', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ ...mockPrediction, leadScore: 60 }))
      )
    );

    render(<HubSpotAIService contact={mockContact} />);
    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(screen.getByText('Warm Lead')).toBeInTheDocument();
    });
  });

  // Test 18: cold lead band
  test('labels a low score as a Cold Lead', async () => {
    server.use(
      rest.post('/api/hubspot/ai/analyze-lead', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ ...mockPrediction, leadScore: 20 }))
      )
    );

    render(<HubSpotAIService contact={mockContact} />);
    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(screen.getByText('Cold Lead')).toBeInTheDocument();
    });
  });

  // Test 19: model selector change flows into the request payload
  test('sends the selected model id when analyzing', async () => {
    render(<HubSpotAIService contact={mockContact} />);

    fireEvent.change(screen.getByRole('combobox'), {
      target: { value: 'predictive' },
    });
    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(lastBody.model_id).toBe('predictive');
    });
  });

  // Test 20: invalid prediction payloads are rejected
  test('shows an error when the server returns a malformed prediction', async () => {
    server.use(
      rest.post('/api/hubspot/ai/analyze-lead', (req, res, ctx) =>
        res(ctx.status(200), ctx.json({ leadScore: 'high' }))
      )
    );

    render(<HubSpotAIService contact={mockContact} />);
    fireEvent.click(screen.getByRole('button', { name: /analyze lead/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid prediction data format from server')).toBeInTheDocument();
    });
  });

  // Test 21: threshold inputs update config
  test('updates the hot threshold from the number input', () => {
    render(<HubSpotAIService contact={mockContact} />);

    const hotInput = screen.getByDisplayValue('75');
    fireEvent.change(hotInput, { target: { value: '90' } });

    expect((hotInput as HTMLInputElement).value).toBe('90');
    // Hot lead trigger description reflects the new threshold
    expect(
      screen.getByText(/lead score exceeds 90/)
    ).toBeInTheDocument();
  });

  // Test 22: factor weight sliders update the displayed weight
  test('updates a factor weight via the slider', () => {
    render(<HubSpotAIService contact={mockContact} />);

    // engagement starts at 35; move the native range input to 40
    const engagementSlider = screen.getAllByRole('slider')[0] as HTMLInputElement;
    expect(engagementSlider.value).toBe('35');

    fireEvent.change(engagementSlider, { target: { value: '40' } });

    expect((screen.getAllByRole('slider')[0] as HTMLInputElement).value).toBe('40');
    expect(screen.getByText('40%')).toBeInTheDocument();
  });

  // Test 23: automation checkboxes toggle shared config state
  test('toggles automation settings via checkboxes', () => {
    render(<HubSpotAIService contact={mockContact} />);

    // checkboxes: [0] enabled, [1] autoAssign, [2] autoFollowup,
    // [3] smartSegmentation, [4] hot-trigger autoAssign, [5] behavioral autoFollowup
    const checkboxes = screen.getAllByRole('checkbox');
    expect(checkboxes.length).toBe(6);
    expect((checkboxes[4] as HTMLInputElement).checked).toBe(true); // autoAssign on

    // Toggle autoAssign in the Automation panel; the Hot Lead Trigger card
    // checkbox reflects the same config state.
    fireEvent.click(checkboxes[1]);
    expect((screen.getAllByRole('checkbox')[4] as HTMLInputElement).checked).toBe(false);

    // Toggle the behavioral trigger card checkbox directly (autoFollowup)
    fireEvent.click(screen.getAllByRole('checkbox')[5]);
    expect((screen.getAllByRole('checkbox')[2] as HTMLInputElement).checked).toBe(true);

    // Toggle the hot trigger card checkbox directly (autoAssign back on)
    fireEvent.click(screen.getAllByRole('checkbox')[4]);
    expect((screen.getAllByRole('checkbox')[1] as HTMLInputElement).checked).toBe(true);

    // The hot trigger description still renders the configured threshold
    expect(screen.getByText(/lead score exceeds 75/)).toBeInTheDocument();
  });
});
