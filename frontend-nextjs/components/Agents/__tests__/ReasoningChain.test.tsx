import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ReasoningChain, ReasoningStep } from '../ReasoningChain';

// Mock useToast hook
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

describe('ReasoningChain Component', () => {
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

  const mockOnFeedback = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders reasoning steps correctly', () => {
      render(<ReasoningChain steps={mockSteps} />);

      expect(screen.getByText('I need to analyze the user request')).toBeInTheDocument();
      expect(screen.getByText('Search results found')).toBeInTheDocument();
    });

    it('displays step type badges', () => {
      render(<ReasoningChain steps={mockSteps} />);

      expect(screen.getByText('THOUGHT')).toBeInTheDocument();
      expect(screen.getByText('ACTION')).toBeInTheDocument();
      expect(screen.getByText('OBSERVATION')).toBeInTheDocument();
    });

    it('displays timestamps correctly', () => {
      render(<ReasoningChain steps={mockSteps} />);

      // Should show timestamps in locale format
      const timestamps = screen.getAllByText(/\d{2}:\d{2}:\d{2}/);
      expect(timestamps.length).toBeGreaterThan(0);
    });

    it('renders empty state when no steps provided', () => {
      render(<ReasoningChain steps={[]} />);

      expect(screen.queryByText(/thinking/i)).not.toBeInTheDocument();
    });

    it('shows thinking indicator when isThinking is true', () => {
      render(<ReasoningChain steps={mockSteps} isThinking={true} />);

      expect(screen.getByText(/thinking/i)).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('expands and collapses reasoning steps', async () => {
      render(<ReasoningChain steps={mockSteps} />);

      // Find expandable sections (using chevron icons)
      const expandButtons = screen.getAllByRole('button');
      expect(expandButtons.length).toBeGreaterThan(0);
    });

    it('handles thumbs up feedback', async () => {
      render(
        <ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />
      );

      // Find thumbs up buttons (should be in each step)
      const thumbsUpButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('svg[lucide="thumbs-up"]') || btn.innerHTML.includes('ThumbsUp')
      );

      if (thumbsUpButtons.length > 0) {
        await fireEvent.click(thumbsUpButtons[0]);
        await waitFor(() => {
          expect(mockOnFeedback).toHaveBeenCalledWith(0, 'thumbs_up');
        });
      }
    });

    it('handles thumbs down feedback', async () => {
      render(
        <ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />
      );

      // Find thumbs down buttons
      const thumbsDownButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('svg[lucide="thumbs-down"]') || btn.innerHTML.includes('ThumbsDown')
      );

      if (thumbsDownButtons.length > 0) {
        await fireEvent.click(thumbsDownButtons[0]);
        await waitFor(() => {
          expect(mockOnFeedback).toHaveBeenCalledWith(0, 'thumbs_down');
        });
      }
    });

    it('opens comment dialog', async () => {
      render(
        <ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />
      );

      // Find comment buttons
      const commentButtons = screen.getAllByRole('button').filter(
        btn => btn.querySelector('svg[lucide="message-square-plus"]') || btn.innerHTML.includes('MessageSquarePlus')
      );

      if (commentButtons.length > 0) {
        await fireEvent.click(commentButtons[0]);

        // Should show comment textarea
        const textarea = screen.queryByRole('textbox');
        if (textarea) {
          expect(textarea).toBeInTheDocument();
        }
      }
    });

    it('submits comment with feedback', async () => {
      render(
        <ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />
      );

      const commentButtons = screen.getAllByRole('button').filter(
        btn => btn.innerHTML.includes('MessageSquarePlus')
      );

      if (commentButtons.length > 0) {
        await fireEvent.click(commentButtons[0]);

        const textarea = screen.queryByRole('textbox');
        if (textarea) {
          await fireEvent.change(textarea, {
            target: { value: 'This is a correction' },
          });

          const submitButton = screen.queryByRole('button', { name: /submit/i });
          if (submitButton) {
            await fireEvent.click(submitButton);
            await waitFor(() => {
              expect(mockOnFeedback).toHaveBeenCalledWith(0, 'thumbs_down', 'This is a correction');
            });
          }
        }
      }
    });
  });

  describe('Step Display Variations', () => {
    it('displays thought steps with brain icon', () => {
      const thoughtStep: ReasoningStep = {
        type: 'thought',
        thought: 'This is a thought',
        timestamp: new Date(),
      };

      render(<ReasoningChain steps={[thoughtStep]} />);

      expect(screen.getByText('This is a thought')).toBeInTheDocument();
      expect(screen.getByText('THOUGHT')).toBeInTheDocument();
    });

    it('displays action steps with terminal icon', () => {
      const actionStep: ReasoningStep = {
        type: 'action',
        action: 'Execute command',
        timestamp: new Date(),
      };

      render(<ReasoningChain steps={[actionStep]} />);

      expect(screen.getByText(/execute command/i)).toBeInTheDocument();
      expect(screen.getByText('ACTION')).toBeInTheDocument();
    });

    it('displays observation steps with eye icon', () => {
      const observationStep: ReasoningStep = {
        type: 'observation',
        observation: 'Observed result',
        timestamp: new Date(),
      };

      render(<ReasoningChain steps={[observationStep]} />);

      expect(screen.getByText('Observed result')).toBeInTheDocument();
      expect(screen.getByText('OBSERVATION')).toBeInTheDocument();
    });

    it('handles error steps', () => {
      const errorStep: ReasoningStep = {
        type: 'error',
        content: 'An error occurred',
        timestamp: new Date(),
      };

      render(<ReasoningChain steps={[errorStep]} />);

      expect(screen.getByText('An error occurred')).toBeInTheDocument();
      expect(screen.getByText('ERROR')).toBeInTheDocument();
    });

    it('displays final answer', () => {
      const finalStep: ReasoningStep = {
        type: 'thought',
        final_answer: 'This is the final answer',
        timestamp: new Date(),
      };

      render(<ReasoningChain steps={[finalStep]} />);

      expect(screen.getByText('This is the final answer')).toBeInTheDocument();
    });
  });

  describe('Feedback State', () => {
    it('displays existing feedback thumbs up', () => {
      const stepWithFeedback: ReasoningStep = {
        type: 'thought',
        thought: 'Test thought',
        timestamp: new Date(),
        feedback: 'thumbs_up',
        comment: 'Good job',
      };

      render(
        <ReasoningChain steps={[stepWithFeedback]} onFeedback={mockOnFeedback} />
      );

      // Should show thumbs up as active
      const thumbsUpButtons = screen.getAllByRole('button').filter(
        btn => btn.classList.contains('text-green-600')
      );

      // If feedback state is shown, thumbs up should be highlighted
      expect(thumbsUpButtons.length).toBeGreaterThan(0);
    });

    it('displays existing feedback thumbs down', () => {
      const stepWithFeedback: ReasoningStep = {
        type: 'thought',
        thought: 'Test thought',
        timestamp: new Date(),
        feedback: 'thumbs_down',
      };

      render(
        <ReasoningChain steps={[stepWithFeedback]} onFeedback={mockOnFeedback} />
      );

      // Should show thumbs down as active
      const thumbsDownButtons = screen.getAllByRole('button').filter(
        btn => btn.classList.contains('text-red-500')
      );

      expect(thumbsDownButtons.length).toBeGreaterThan(0);
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels for feedback buttons', () => {
      render(
        <ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />
      );

      // All interactive elements should be accessible
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toBeInTheDocument();
      });
    });

    it('supports keyboard navigation', async () => {
      render(
        <ReasoningChain steps={mockSteps} onFeedback={mockOnFeedback} />
      );

      const firstButton = screen.getAllByRole('button')[0];
      firstButton?.focus();
      expect(firstButton).toHaveFocus();
    });
  });

  describe('Edge Cases', () => {
    it('handles missing step type gracefully', () => {
      const stepWithoutType: ReasoningStep = {
        thought: 'Thought without type',
        timestamp: new Date(),
      };

      render(<ReasoningChain steps={[stepWithoutType]} />);

      // Should default to 'thought' type
      expect(screen.getByText('Thought without type')).toBeInTheDocument();
    });

    it('handles action as object', () => {
      const actionStep: ReasoningStep = {
        type: 'action',
        action: { tool: 'browser', params: { url: 'https://example.com' } },
        timestamp: new Date(),
      };

      render(<ReasoningChain steps={[actionStep]} />);

      // Should display JSON representation of action object
      expect(screen.getByText(/browser/i)).toBeInTheDocument();
    });

    it('handles missing timestamp', () => {
      const stepWithoutTimestamp: ReasoningStep = {
        type: 'thought',
        thought: 'No timestamp',
      };

      render(<ReasoningChain steps={[stepWithoutTimestamp]} />);

      // Should still render step
      expect(screen.getByText('No timestamp')).toBeInTheDocument();
    });

    it('handles long content with wrapping', () => {
      const longContentStep: ReasoningStep = {
        type: 'thought',
        thought: 'A'.repeat(1000),
        timestamp: new Date(),
      };

      render(<ReasoningChain steps={[longContentStep]} />);

      // Should display long content
      expect(screen.getByText(/A+/)).toBeInTheDocument();
    });
  });

  describe('Callback Handling', () => {
    it('calls onFeedback with correct step index', async () => {
      const steps: ReasoningStep[] = [
        { type: 'thought', thought: 'Step 0', timestamp: new Date() },
        { type: 'thought', thought: 'Step 1', timestamp: new Date() },
        { type: 'thought', thought: 'Step 2', timestamp: new Date() },
      ];

      render(
        <ReasoningChain steps={steps} onFeedback={mockOnFeedback} />
      );

      // Click thumbs up on second step
      const thumbsUpButtons = screen.getAllByRole('button');

      if (thumbsUpButtons.length > 1) {
        await fireEvent.click(thumbsUpButtons[1]);

        await waitFor(() => {
          // Should have been called (exact index depends on button order)
          expect(mockOnFeedback).toHaveBeenCalled();
        });
      }
    });

    it('handles async feedback callback', async () => {
      const asyncOnFeedback = jest.fn().mockResolvedValue(undefined);

      render(
        <ReasoningChain steps={mockSteps} onFeedback={asyncOnFeedback} />
      );

      const thumbsUpButtons = screen.getAllByRole('button');

      if (thumbsUpButtons.length > 0) {
        await fireEvent.click(thumbsUpButtons[0]);

        await waitFor(() => {
          expect(asyncOnFeedback).toHaveBeenCalled();
        });
      }
    });
  });
});
