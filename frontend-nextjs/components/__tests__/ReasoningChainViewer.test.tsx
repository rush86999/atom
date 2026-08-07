/**
 * ReasoningChainViewer Component Tests
 *
 * Tests verify the real ReasoningChainViewer component
 * (components/ReasoningChainViewer.tsx):
 * - loading state when only a chainId is provided
 * - chainData prop renders step count, duration, steps (icons/types/
 *   descriptions/confidence), final outcome, and renders the mermaid diagram
 * - chainId fetch: GET /api/v1/voice/reasoning/:chainId loads and renders
 * - fetch failure renders the error message
 * - expanding a step shows inputs/outputs JSON and duration/confidence detail
 * - step feedback: thumbs up calls onStepFeedback(stepId, 1); thumbs down
 *   opens the correction input and Enter submits onStepFeedback(stepId, 0, comment)
 * - no chainId + no chainData renders "No reasoning chain available"
 *
 * API: GET /api/v1/voice/reasoning/:chainId (mermaid render is mocked)
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { rest } from 'msw';
import { server } from '@/tests/mocks/server';

const mockMermaidRender = jest.fn();
jest.mock('mermaid', () => ({
  initialize: jest.fn(),
  render: mockMermaidRender,
}));

import ReasoningChainViewer from '../ReasoningChainViewer';

const chainData = {
  execution_id: 'exec-1',
  started_at: '2026-08-07T09:00:00.000Z',
  completed_at: '2026-08-07T09:00:05.000Z',
  total_duration_ms: 5230,
  final_outcome: 'Meeting scheduled for tomorrow 10am',
  step_count: 2,
  steps: [
    {
      id: 'step-1',
      type: 'intent_analysis',
      description: 'Classified the request as scheduling',
      inputs: { query: 'book a meeting' },
      outputs: { intent: 'schedule' },
      confidence: 0.92,
      duration_ms: 120.5,
      timestamp: '2026-08-07T09:00:00.000Z',
    },
    {
      id: 'step-2',
      type: 'integration_call',
      description: 'Created the calendar event',
      inputs: { calendar: 'primary' },
      outputs: { event_id: 'evt-42' },
      confidence: 0.65,
      duration_ms: 88.2,
      timestamp: '2026-08-07T09:00:01.000Z',
    },
  ],
  mermaid_diagram: 'flowchart TD\nA[Start] --> B[End]',
};

describe('ReasoningChainViewer', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockMermaidRender.mockResolvedValue({ svg: '<svg><text>rendered diagram</text></svg>' });

    server.resetHandlers();
    server.use(
      rest.get('/api/v1/voice/reasoning/:chainId', (req, res, ctx) => {
        return res(ctx.status(200), ctx.json(chainData));
      })
    );
  });

  it('shows the loading state when only a chainId is provided', () => {
    render(<ReasoningChainViewer chainId="exec-1" />);
    expect(screen.getByText('Loading reasoning chain...')).toBeInTheDocument();
  });

  it('renders a chain passed via chainData with steps and outcome', async () => {
    render(<ReasoningChainViewer chainData={chainData} />);

    expect(screen.getByText('AI Reasoning Chain')).toBeInTheDocument();
    expect(screen.getByText('2 steps')).toBeInTheDocument();
    expect(screen.getByText('5230ms')).toBeInTheDocument();
    expect(screen.getByText('intent analysis')).toBeInTheDocument();
    expect(screen.getByText('Classified the request as scheduling')).toBeInTheDocument();
    expect(screen.getByText('integration call')).toBeInTheDocument();
    expect(screen.getByText('Created the calendar event')).toBeInTheDocument();
    expect(screen.getByText('Final Outcome:')).toBeInTheDocument();
    expect(screen.getByText('Meeting scheduled for tomorrow 10am')).toBeInTheDocument();
  });

  it('renders the mermaid diagram into the diagram container', async () => {
    render(<ReasoningChainViewer chainData={chainData} />);

    await waitFor(() => {
      expect(mockMermaidRender).toHaveBeenCalledWith('reasoning-diagram', chainData.mermaid_diagram);
    });
    expect(document.querySelector('.mermaid-container')).toHaveTextContent('rendered diagram');
  });

  it('fetches the chain by id and renders it', async () => {
    render(<ReasoningChainViewer chainId="exec-1" />);

    expect(await screen.findByText('2 steps')).toBeInTheDocument();
    expect(screen.getByText('Created the calendar event')).toBeInTheDocument();
  });

  it('renders the error message when the chain fetch fails', async () => {
    server.use(
      rest.get('/api/v1/voice/reasoning/:chainId', (req, res, ctx) => {
        return res(ctx.status(404));
      })
    );

    render(<ReasoningChainViewer chainId="missing" />);

    expect(await screen.findByText('Failed to fetch reasoning chain')).toBeInTheDocument();
  });

  it('expands a step to show inputs, outputs and duration detail', async () => {
    render(<ReasoningChainViewer chainData={chainData} />);

    fireEvent.click(screen.getByText('Classified the request as scheduling'));

    expect(screen.getByText('Inputs:')).toBeInTheDocument();
    expect(screen.getByText(/book a meeting/)).toBeInTheDocument();
    expect(screen.getByText('Outputs:')).toBeInTheDocument();
    expect(screen.getByText(/"schedule"/)).toBeInTheDocument();
    expect(screen.getByText('Duration: 120.5ms')).toBeInTheDocument();
    expect(screen.getByText('Confidence: 92%')).toBeInTheDocument();
  });

  it('calls onStepFeedback with a positive score on thumbs up', async () => {
    const onStepFeedback = jest.fn().mockResolvedValue(undefined);
    render(<ReasoningChainViewer chainData={chainData} onStepFeedback={onStepFeedback} />);

    fireEvent.click(screen.getAllByRole('button')[0]);

    expect(onStepFeedback).toHaveBeenCalledWith('step-1', 1);
  });

  it('opens the correction input on thumbs down and submits the comment on Enter', async () => {
    const onStepFeedback = jest.fn().mockResolvedValue(undefined);
    render(<ReasoningChainViewer chainData={chainData} onStepFeedback={onStepFeedback} />);

    fireEvent.click(screen.getAllByRole('button')[1]);

    const input = screen.getByPlaceholderText('Provide a correction...');
    fireEvent.change(input, { target: { value: 'Wrong calendar' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(onStepFeedback).toHaveBeenCalledWith('step-1', 0, 'Wrong calendar');
    await waitFor(() => {
      expect(screen.queryByPlaceholderText('Provide a correction...')).not.toBeInTheDocument();
    });
  });

  it('does not render feedback buttons when no onStepFeedback is provided', () => {
    render(<ReasoningChainViewer chainData={chainData} />);
    expect(screen.queryByRole('button', { name: /thumbs up/i })).not.toBeInTheDocument();
  });

  it('renders the empty state when neither chainId nor chainData is provided', () => {
    render(<ReasoningChainViewer />);
    expect(screen.getByText('No reasoning chain available')).toBeInTheDocument();
  });
});
