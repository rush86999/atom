import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ReasoningChain, ReasoningStep } from '../ReasoningChain';

// Real behavior (verified against source):
// - Steps are COLLAPSED by default; the header "Reasoning Process (N steps)"
//   must be clicked to reveal step contents.
// - Type badges render the raw type string (lowercase, uppercased via CSS only).
// - Feedback controls (thumbs up/down/comment) have no accessible names; they
//   are located by their lucide icon class.
// - With onFeedback provided the component calls it directly (no network);
//   without it, it POSTs to /api/reasoning/feedback.
// - Submitting a comment always records a thumbs_down correction.
// - Empty steps render nothing.

const mockSteps: ReasoningStep[] = [
  {
    type: 'thought',
    thought: 'I need to analyze the user request',
    timestamp: new Date('2024-01-01T10:00:00'),
  },
  {
    type: 'action',
    action: { tool: 'web_search', params: { query: 'test' } },
    timestamp: new Date('2024-01-01T10:00:01'),
  },
  {
    type: 'observation',
    observation: 'Search results found',
    timestamp: new Date('2024-01-01T10:00:02'),
  },
];

const buttonWithIcon = (iconClass: string) =>
  screen.getAllByRole('button').find((btn) => btn.querySelector(`.${iconClass}`));

const expandChain = () => {
  fireEvent.click(screen.getByText(/Reasoning Process/));
};

describe('ReasoningChain Component', () => {
  const mockOnFeedback = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders the collapsible header with step count', () => {
      render(<ReasoningChain steps={mockSteps} />);
      expect(screen.getByText('Reasoning Process (3 steps)')).toBeInTheDocument();
    });

    it('renders reasoning steps correctly after expanding', () => {
      render(<ReasoningChain steps={mockSteps} />);
      expandChain();

      expect(screen.getByText('I need to analyze the user request')).toBeInTheDocument();
      expect(screen.getByText('Search results found')).toBeInTheDocument();
    });

    it('displays step type badges', () => {
      render(<ReasoningChain steps={mockSteps} />);
      expandChain();

      expect(screen.getByText('thought')).toBeInTheDocument();
      expect(screen.getByText('action')).toBeInTheDocument();
      expect(screen.getByText('observation')).toBeInTheDocument();
    });

    it('displays timestamps correctly', () => {
      render(<ReasoningChain steps={mockSteps} />);
      expandChain();

      const timestamps = screen.getAllByText(/\d{2}:\d{2}:\d{2}/);
      expect(timestamps.length).toBeGreaterThanOrEqual(3);
    });

    it('renders nothing when no steps provided', () => {
      const { container } = render(<ReasoningChain steps={[]} />);
      expect(container.innerHTML).toBe('');
    });

    it('shows thinking indicator when isThinking is true', () => {
      render(<ReasoningChain steps={mockSteps} isThinking={true} />);
      expect(screen.getByText('Thinking...')).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('expands and collapses reasoning steps', () => {
      render(<ReasoningChain steps={mockSteps} />);

      // Collapsed: step content hidden.
      expect(screen.queryByText('I need to analyze the user request')).not.toBeInTheDocument();

      expandChain();
      expect(screen.getByText('I need to analyze the user request')).toBeInTheDocument();

      fireEvent.click(screen.getByText(/Reasoning Process/));
      expect(screen.queryByText('I need to analyze the user request')).not.toBeInTheDocument();
    });

    it('handles thumbs up feedback', async () => {
      render(<ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />);
      expandChain();

      const thumbsUp = buttonWithIcon('lucide-thumbs-up');
      expect(thumbsUp).toBeTruthy();
      fireEvent.click(thumbsUp!);

      await waitFor(() => {
        expect(mockOnFeedback).toHaveBeenCalledWith(0, 'thumbs_up', undefined);
      });
    });

    it('handles thumbs down feedback', async () => {
      render(<ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />);
      expandChain();

      const thumbsDown = buttonWithIcon('lucide-thumbs-down');
      expect(thumbsDown).toBeTruthy();
      fireEvent.click(thumbsDown!);

      await waitFor(() => {
        expect(mockOnFeedback).toHaveBeenCalledWith(0, 'thumbs_down', undefined);
      });
    });

    it('opens comment box and submits a correction', async () => {
      render(<ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />);
      expandChain();

      const commentButton = buttonWithIcon('lucide-message-square-plus');
      expect(commentButton).toBeTruthy();
      fireEvent.click(commentButton!);

      const textarea = screen.getByPlaceholderText('What was wrong or how can I improve?');
      expect(textarea).toBeInTheDocument();

      fireEvent.change(textarea, { target: { value: 'This is a correction' } });
      fireEvent.click(screen.getByText('Submit Correction'));

      await waitFor(() => {
        expect(mockOnFeedback).toHaveBeenCalledWith(0, 'thumbs_down', 'This is a correction');
      });
    });
  });

  describe('Step Display Variations', () => {
    it('displays thought steps with a thought badge', () => {
      render(<ReasoningChain steps={[{ type: 'thought', thought: 'This is a thought', timestamp: new Date() }]} />);
      expandChain();

      expect(screen.getByText('This is a thought')).toBeInTheDocument();
      expect(screen.getByText('thought')).toBeInTheDocument();
    });

    it('displays action steps with string action content', () => {
      render(<ReasoningChain steps={[{ type: 'action', action: 'Execute command', timestamp: new Date() }]} />);
      expandChain();

      expect(screen.getByText(/execute command/i)).toBeInTheDocument();
      expect(screen.getByText('action')).toBeInTheDocument();
    });

    it('displays observation steps with observation content', () => {
      render(<ReasoningChain steps={[{ type: 'observation', observation: 'Observed result', timestamp: new Date() }]} />);
      expandChain();

      expect(screen.getByText('Observed result')).toBeInTheDocument();
      expect(screen.getByText('observation')).toBeInTheDocument();
    });

    it('handles error steps', () => {
      render(<ReasoningChain steps={[{ type: 'error', content: 'An error occurred', timestamp: new Date() }]} />);
      expandChain();

      expect(screen.getByText('An error occurred')).toBeInTheDocument();
      expect(screen.getByText('error')).toBeInTheDocument();
    });

    it('displays final answer', () => {
      render(<ReasoningChain steps={[{ type: 'thought', final_answer: 'This is the final answer', timestamp: new Date() }]} />);
      expandChain();

      expect(screen.getByText('This is the final answer')).toBeInTheDocument();
    });
  });

  describe('Feedback State', () => {
    it('highlights the thumbs up button after it is clicked', async () => {
      render(<ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />);
      expandChain();

      const thumbsUp = buttonWithIcon('lucide-thumbs-up')!;
      fireEvent.click(thumbsUp);

      await waitFor(() => {
        expect(thumbsUp.className).toContain('text-green-600');
      });
    });

    it('highlights the thumbs down button after it is clicked', async () => {
      render(<ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />);
      expandChain();

      const thumbsDown = buttonWithIcon('lucide-thumbs-down')!;
      fireEvent.click(thumbsDown);

      await waitFor(() => {
        expect(thumbsDown.className).toContain('text-red-500');
      });
    });
  });

  describe('Accessibility', () => {
    it('renders all interactive buttons in the document', () => {
      render(<ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />);
      expandChain();

      const buttons = screen.getAllByRole('button');
      expect(buttons.length).toBeGreaterThan(0);
      buttons.forEach((button) => {
        expect(button).toBeInTheDocument();
      });
    });

    it('supports keyboard navigation', () => {
      render(<ReasoningChain steps={mockSteps} />);

      const headerButton = screen.getByText(/Reasoning Process/).closest('button')!;
      headerButton.focus();
      expect(headerButton).toHaveFocus();
    });
  });

  describe('Edge Cases', () => {
    it('handles missing step type gracefully', () => {
      render(<ReasoningChain steps={[{ thought: 'Thought without type', timestamp: new Date() }]} />);
      expandChain();

      expect(screen.getByText('Thought without type')).toBeInTheDocument();
      expect(screen.getByText('thought')).toBeInTheDocument();
    });

    it('handles action as object', () => {
      render(
        <ReasoningChain
          steps={[{ type: 'action', action: { tool: 'browser', params: { url: 'https://example.com' } }, timestamp: new Date() }]}
        />
      );
      expandChain();

      expect(screen.getByText(/browser/i)).toBeInTheDocument();
    });

    it('handles missing timestamp', () => {
      render(<ReasoningChain steps={[{ type: 'thought', thought: 'No timestamp' }]} />);
      expandChain();

      expect(screen.getByText('No timestamp')).toBeInTheDocument();
    });

    it('handles long content with wrapping', () => {
      render(<ReasoningChain steps={[{ type: 'thought', thought: 'A'.repeat(1000), timestamp: new Date() }]} />);
      expandChain();

      // Exact string match avoids colliding with the timestamp ("... AM").
      expect(screen.getByText('A'.repeat(1000))).toBeInTheDocument();
    });
  });

  describe('Callback Handling', () => {
    it('calls onFeedback with the correct step index', async () => {
      const steps: ReasoningStep[] = [
        { type: 'thought', thought: 'Step 0', timestamp: new Date() },
        { type: 'thought', thought: 'Step 1', timestamp: new Date() },
        { type: 'thought', thought: 'Step 2', timestamp: new Date() },
      ];

      render(<ReasoningChain steps={steps} onFeedback={mockOnFeedback} />);
      expandChain();

      const thumbsUps = screen
        .getAllByRole('button')
        .filter((btn) => btn.querySelector('.lucide-thumbs-up'));

      // Click thumbs up on the second step.
      fireEvent.click(thumbsUps[1]);

      await waitFor(() => {
        expect(mockOnFeedback).toHaveBeenCalledWith(1, 'thumbs_up', undefined);
      });
    });

    it('handles async feedback callback', async () => {
      const asyncOnFeedback = jest.fn().mockResolvedValue(undefined);

      render(<ReasoningChain steps={mockSteps} onFeedback={asyncOnFeedback} />);
      expandChain();

      const thumbsUp = buttonWithIcon('lucide-thumbs-up')!;
      fireEvent.click(thumbsUp);

      await waitFor(() => {
        expect(asyncOnFeedback).toHaveBeenCalledWith(0, 'thumbs_up', undefined);
      });
    });
  });
});
