import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import { VoiceInput } from '../VoiceInput';

// Mock useVoiceIO hook
const mockStartListening = jest.fn();
const mockStopListening = jest.fn();
const mockResetTranscript = jest.fn();
const mockToggleWakeWord = jest.fn();

jest.mock('@/hooks/useVoiceIO', () => ({
  useVoiceIO: jest.fn(() => ({
    isListening: false,
    transcript: '',
    startListening: mockStartListening,
    stopListening: mockStopListening,
    isSupported: true,
    resetTranscript: mockResetTranscript,
    wakeWordActive: false,
    toggleWakeWord: mockToggleWakeWord,
  })),
}));

describe('VoiceInput Component', () => {
  const mockOnTranscriptChange = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('shows microphone icon when not listening', () => {
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /start voice input/i });
      expect(micButton).toBeInTheDocument();
    });

    it('shows microphone off icon when listening', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: true,
        transcript: '',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /stop listening/i });
      expect(micButton).toBeInTheDocument();
    });

    it('shows wake word toggle button', () => {
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      expect(screen.getByText('ATOM')).toBeInTheDocument();
    });

    it('displays listening indicator when active', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: true,
        transcript: 'test transcript',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      expect(screen.getByText(/listening/i)).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('starts listening when microphone button clicked', async () => {
      const user = userEvent.setup();
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /start voice input/i });
      await user.click(micButton);

      expect(mockResetTranscript).toHaveBeenCalled();
      expect(mockStartListening).toHaveBeenCalled();
    });

    it('stops listening when microphone button clicked while active', async () => {
      const user = userEvent.setup();
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: true,
        transcript: 'test',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /stop listening/i });
      await user.click(micButton);

      expect(mockStopListening).toHaveBeenCalled();
    });

    it('enables wake word mode when ATOM button clicked', async () => {
      const user = userEvent.setup();
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const atomButton = screen.getByRole('button', { name: /enable wake word/i });
      await user.click(atomButton);

      expect(mockToggleWakeWord).toHaveBeenCalledWith(true);
    });

    it('disables wake word mode when ATOM button clicked while active', async () => {
      const user = userEvent.setup();
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: false,
        transcript: '',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: true,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const atomButton = screen.getByRole('button', { name: /disable wake word/i });
      await user.click(atomButton);

      expect(mockToggleWakeWord).toHaveBeenCalledWith(false);
    });
  });

  describe('Transcript Handling', () => {
    it('calls onTranscriptChange when transcript updates', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: false,
        transcript: 'new transcript',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      expect(mockOnTranscriptChange).toHaveBeenCalledWith('new transcript');
    });

    it('syncs transcript changes via useEffect', () => {
      const { rerender } = render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      // Rerender with new transcript value
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: false,
        transcript: 'updated transcript',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      rerender(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      expect(mockOnTranscriptChange).toHaveBeenCalledWith('updated transcript');
    });
  });

  describe('Browser Support', () => {
    it('shows disabled button when speech recognition not supported', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: false,
        transcript: '',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: false,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button');
      expect(micButton).toBeDisabled();
      expect(micButton).toHaveAttribute('title', expect.stringContaining(/not supported/i));
    });

    it('hides wake word button when not supported', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: false,
        transcript: '',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: false,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      expect(screen.queryByText('ATOM')).not.toBeInTheDocument();
    });
  });

  describe('Visual States', () => {
    it('shows destructive variant when listening', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: true,
        transcript: 'test',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /stop listening/i });
      expect(micButton).toHaveClass('destructive');
    });

    it('shows ghost variant when not listening', () => {
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /start voice input/i });
      expect(micButton).toHaveClass('ghost');
    });

    it('shows animated pulse when listening', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: true,
        transcript: 'test',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /stop listening/i });
      expect(micButton).toHaveClass('animate-pulse');
    });

    it('shows blue highlight when wake word enabled', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: false,
        transcript: '',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: true,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const atomButton = screen.getByRole('button', { name: /disable wake word/i });
      expect(atomButton).toHaveClass('text-blue-500');
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels', () => {
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /start voice input/i });
      expect(micButton).toHaveAttribute('title', 'Start Voice Input');

      const atomButton = screen.getByRole('button', { name: /enable wake word/i });
      expect(atomButton).toHaveAttribute('title', expect.stringContaining('Hey Atom'));
    });

    it('supports keyboard navigation', async () => {
      const user = userEvent.setup();
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      await user.tab();

      const micButton = screen.getByRole('button', { name: /start voice input/i });
      expect(micButton).toHaveFocus();
    });
  });

  describe('Custom ClassName', () => {
    it('applies custom className to container', () => {
      const { container } = render(
        <VoiceInput onTranscriptChange={mockOnTranscriptChange} className="custom-class" />
      );

      expect(container.querySelector('.custom-class')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles rapid start/stop clicks', async () => {
      const user = userEvent.setup();
      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      const micButton = screen.getByRole('button', { name: /start voice input/i });

      await user.click(micButton);
      await user.click(micButton);
      await user.click(micButton);

      // Should handle rapid clicks gracefully
      expect(mockStartListening).toHaveBeenCalled();
      expect(mockStopListening).toHaveBeenCalled();
    });

    it('handles empty transcript', () => {
      (require('@/hooks/useVoiceIO').useVoiceIO as jest.Mock).mockReturnValue({
        isListening: false,
        transcript: '',
        startListening: mockStartListening,
        stopListening: mockStopListening,
        isSupported: true,
        resetTranscript: mockResetTranscript,
        wakeWordActive: false,
        toggleWakeWord: mockToggleWakeWord,
      });

      render(<VoiceInput onTranscriptChange={mockOnTranscriptChange} />);

      // Should not call onTranscriptChange with empty string
      expect(mockOnTranscriptChange).not.toHaveBeenCalled();
    });
  });
});
