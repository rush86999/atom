/**
 * CostCalculator component tests.
 *
 * The useCognitiveTier hook is mocked so estimateCost can be driven directly.
 * Covers cost estimation from prompt + requests/day, missing-tier fallback,
 * and the slider interaction (BUG: slider value was passed as an array while
 * the Slider component's onValueChange emits a plain number — moving the
 * slider broke the estimate and label).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { CostCalculator } from '../CostCalculator';

const mockEstimateCost = jest.fn();

jest.mock('@/hooks/useCognitiveTier', () => ({
  useCognitiveTier: () => ({
    estimateCost: mockEstimateCost,
  }),
}));

describe('CostCalculator', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockEstimateCost.mockResolvedValue([
      { tier: 'standard', estimated_cost_usd: 0.02, models_in_tier: [] },
    ]);
  });

  it('renders the calculator with prompt input and default 100 requests/day', () => {
    render(<CostCalculator selectedTier="standard" />);

    expect(screen.getByText('Cost Calculator')).toBeInTheDocument();
    expect(screen.getByText('Requests Per Day: 100')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Enter a sample query...')).toBeInTheDocument();
  });

  it('does not show an estimate until a prompt is entered', async () => {
    render(<CostCalculator selectedTier="standard" />);

    await waitFor(() => expect(mockEstimateCost).not.toHaveBeenCalled());
    expect(screen.queryByText(/Estimated monthly cost/)).not.toBeInTheDocument();
  });

  it('computes monthly cost from prompt cost per request and requests per day', async () => {
    render(<CostCalculator selectedTier="standard" />);

    fireEvent.change(screen.getByPlaceholderText('Enter a sample query...'), {
      target: { value: 'Analyze my sales data' },
    });

    await waitFor(() => expect(mockEstimateCost).toHaveBeenCalledWith('Analyze my sales data'));
    // 0.02 USD/request * 100 req/day * 30 days = $60.00
    expect(await screen.findByText('$60.00')).toBeInTheDocument();
    expect(screen.getByText('Estimated monthly cost')).toBeInTheDocument();
    expect(screen.getByText('* Estimates based on standard tier. Actual costs may vary.')).toBeInTheDocument();
  });

  it('updates the estimate and label when the slider moves to 200 requests/day', async () => {
    render(<CostCalculator selectedTier="standard" />);

    fireEvent.change(screen.getByPlaceholderText('Enter a sample query...'), {
      target: { value: 'Summarize the docs' },
    });
    await screen.findByText('$60.00');

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '200' } });

    expect(screen.getByText('Requests Per Day: 200')).toBeInTheDocument();
    // 0.02 USD/request * 200 req/day * 30 days = $120.00
    expect(await screen.findByText('$120.00')).toBeInTheDocument();
  });

  it('clears the estimate when the selected tier is missing from the API response', async () => {
    mockEstimateCost.mockResolvedValue([
      { tier: 'heavy', estimated_cost_usd: 0.5, models_in_tier: [] },
    ]);
    render(<CostCalculator selectedTier="standard" />);

    fireEvent.change(screen.getByPlaceholderText('Enter a sample query...'), {
      target: { value: 'hello' },
    });

    await waitFor(() => expect(mockEstimateCost).toHaveBeenCalled());
    expect(screen.queryByText(/Estimated monthly cost/)).not.toBeInTheDocument();
  });

  it('clears the estimate when the prompt is emptied', async () => {
    const { rerender } = render(<CostCalculator selectedTier="standard" />);

    const input = screen.getByPlaceholderText('Enter a sample query...');
    fireEvent.change(input, { target: { value: 'some query' } });
    await screen.findByText('$60.00');

    fireEvent.change(input, { target: { value: '' } });
    expect(screen.queryByText(/Estimated monthly cost/)).not.toBeInTheDocument();
    rerender(<CostCalculator selectedTier="standard" />);
  });
});
