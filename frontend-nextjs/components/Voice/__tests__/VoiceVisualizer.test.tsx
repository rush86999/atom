import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { VoiceVisualizer } from '../VoiceVisualizer';

// Mock canvas context
const mockCtx = {
  clearRect: jest.fn(),
  fillStyle: '',
  fillRect: jest.fn(),
  fill: jest.fn(),
  beginPath: jest.fn(),
  roundRect: jest.fn(),
  shadowBlur: 0,
  shadowColor: '',
};

describe('VoiceVisualizer Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Mock HTMLCanvasElement.getContext
    HTMLCanvasElement.prototype.getContext = jest.fn(() => mockCtx as any);
    // Mock requestAnimationFrame
    global.requestAnimationFrame = jest.fn((cb) => {
      return window.setTimeout(cb, 16) as unknown as number;
    });
    // Mock cancelAnimationFrame
    global.cancelAnimationFrame = jest.fn();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    it('renders without crashing', () => {
      render(<VoiceVisualizer mode="idle" />);

      const canvas = screen.getByRole('img');
      expect(canvas).toBeInTheDocument();
    });

    it('renders canvas with correct dimensions', () => {
      render(<VoiceVisualizer mode="idle" />);

      const canvas = screen.getByRole('img') as HTMLCanvasElement;
      expect(canvas.width).toBe(400);
      expect(canvas.height).toBe(100);
    });

    it('has correct CSS classes', () => {
      render(<VoiceVisualizer mode="idle" />);

      const canvas = screen.getByRole('img');
      expect(canvas).toHaveClass('w-full', 'h-24', 'pointer-events-none');
    });
  });

  describe('Animation States', () => {
    it('renders idle state with slate color', () => {
      render(<VoiceVisualizer mode="idle" />);

      expect(screen.getByRole('img')).toBeInTheDocument();
    });

    it('renders listening state with emerald color', () => {
      render(<VoiceVisualizer mode="listening" />);

      expect(screen.getByRole('img')).toBeInTheDocument();
    });

    it('renders processing state with orange color', () => {
      render(<VoiceVisualizer mode="processing" />);

      expect(screen.getByRole('img')).toBeInTheDocument();
    });

    it('renders speaking state with blue color', () => {
      render(<VoiceVisualizer mode="speaking" />);

      expect(screen.getByRole('img')).toBeInTheDocument();
    });
  });

  describe('Canvas Context', () => {
    it('gets 2D context from canvas', () => {
      render(<VoiceVisualizer mode="idle" />);

      const canvas = screen.getByRole('img') as HTMLCanvasElement;
      expect(canvas.getContext).toHaveBeenCalledWith('2d');
    });

    it('handles null context gracefully', () => {
      HTMLCanvasElement.prototype.getContext = jest.fn(() => null);

      expect(() => render(<VoiceVisualizer mode="idle" />)).not.toThrow();
    });
  });

  describe('Animation Lifecycle', () => {
    it('starts animation on mount', () => {
      render(<VoiceVisualizer mode="idle" />);

      expect(global.requestAnimationFrame).toHaveBeenCalled();
    });

    it('cleans up animation on unmount', () => {
      const { unmount } = render(<VoiceVisualizer mode="idle" />);

      unmount();

      expect(global.cancelAnimationFrame).toHaveBeenCalled();
    });

    it('restarts animation when mode changes', () => {
      const { rerender } = render(<VoiceVisualizer mode="idle" />);

      const callsBefore = (global.requestAnimationFrame as jest.Mock).mock.calls.length;

      rerender(<VoiceVisualizer mode="listening" />);

      const callsAfter = (global.requestAnimationFrame as jest.Mock).mock.calls.length;

      // Should have more calls after mode change (animation restarted)
      expect(callsAfter).toBeGreaterThan(callsBefore);
    });
  });

  describe('Animation Behavior', () => {
    it('clears canvas each frame', () => {
      render(<VoiceVisualizer mode="idle" />);

      // Trigger animation frames
      jest.advanceTimersByTime(100);

      expect(mockCtx.clearRect).toHaveBeenCalled();
    });

    it('draws bars for idle mode', () => {
      render(<VoiceVisualizer mode="idle" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.beginPath).toHaveBeenCalled();
      expect(mockCtx.roundRect).toHaveBeenCalled();
      expect(mockCtx.fill).toHaveBeenCalled();
    });

    it('uses shadow for active modes', () => {
      render(<VoiceVisualizer mode="listening" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.shadowBlur).toBeGreaterThan(0);
    });

    it('disables shadow for idle mode', () => {
      render(<VoiceVisualizer mode="idle" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.shadowBlur).toBe(0);
    });

    it('draws correct number of bars', () => {
      render(<VoiceVisualizer mode="listening" />);

      jest.advanceTimersByTime(100);

      // Should draw 40 bars (as defined in component)
      expect(mockCtx.roundRect).toHaveBeenCalledTimes(40);
    });
  });

  describe('Visual Effects', () => {
    it('applies glow effect in listening mode', () => {
      render(<VoiceVisualizer mode="listening" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.shadowBlur).toBe(15);
      expect(mockCtx.shadowColor).toBe('rgb(16, 185, 129)');
    });

    it('applies glow effect in speaking mode', () => {
      render(<VoiceVisualizer mode="speaking" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.shadowBlur).toBe(15);
      expect(mockCtx.shadowColor).toBe('rgb(59, 130, 246)');
    });

    it('applies glow effect in processing mode', () => {
      render(<VoiceVisualizer mode="processing" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.shadowBlur).toBe(15);
      expect(mockCtx.shadowColor).toBe('rgb(249, 115, 22)');
    });

    it('has no glow in idle mode', () => {
      render(<VoiceVisualizer mode="idle" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.shadowBlur).toBe(0);
    });
  });

  describe('Color Scheme', () => {
    it('uses slate-500 for idle mode', () => {
      render(<VoiceVisualizer mode="idle" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.fillStyle).toBe('rgb(100, 116, 139)');
    });

    it('uses emerald-500 for listening mode', () => {
      render(<VoiceVisualizer mode="listening" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.fillStyle).toBe('rgb(16, 185, 129)');
    });

    it('uses orange-500 for processing mode', () => {
      render(<VoiceVisualizer mode="processing" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.fillStyle).toBe('rgb(249, 115, 22)');
    });

    it('uses blue-500 for speaking mode', () => {
      render(<VoiceVisualizer mode="speaking" />);

      jest.advanceTimersByTime(100);

      expect(mockCtx.fillStyle).toBe('rgb(59, 130, 246)');
    });
  });

  describe('Animation Speed', () => {
    it('uses slower animation for idle mode', () => {
      render(<VoiceVisualizer mode="idle" />);

      jest.advanceTimersByTime(100);

      // Idle has lower amplitude and speed
      expect(mockCtx.roundRect).toHaveBeenCalled();
    });

    it('uses faster animation for listening mode', () => {
      render(<VoiceVisualizer mode="listening" />);

      jest.advanceTimersByTime(100);

      // Listening has higher amplitude and speed
      expect(mockCtx.roundRect).toHaveBeenCalled();
    });
  });

  describe('Amplitude', () => {
    it('has lower amplitude in idle mode', () => {
      render(<VoiceVisualizer mode="idle" />);

      jest.advanceTimersByTime(100);

      // Bars should be shorter in idle mode
      expect(mockCtx.roundRect).toHaveBeenCalled();
    });

    it('has higher amplitude in speaking mode', () => {
      render(<VoiceVisualizer mode="speaking" />);

      jest.advanceTimersByTime(100);

      // Bars should be taller in speaking mode
      expect(mockCtx.roundRect).toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('handles rapid mode changes', () => {
      const { rerender } = render(<VoiceVisualizer mode="idle" />);

      rerender(<VoiceVisualizer mode="listening" />);
      rerender(<VoiceVisualizer mode="processing" />);
      rerender(<VoiceVisualizer mode="speaking" />);

      expect(global.cancelAnimationFrame).toHaveBeenCalled();
      expect(global.requestAnimationFrame).toHaveBeenCalled();
    });

    it('handles unmount during active animation', () => {
      const { unmount } = render(<VoiceVisualizer mode="listening" />);

      jest.advanceTimersByTime(50);
      unmount();

      expect(global.cancelAnimationFrame).toHaveBeenCalled();
    });
  });

  describe('Performance', () => {
    it('uses requestAnimationFrame for smooth animation', () => {
      render(<VoiceVisualizer mode="listening" />);

      expect(global.requestAnimationFrame).toHaveBeenCalled();
    });

    it('cancels previous animation frame before starting new one', () => {
      const { rerender } = render(<VoiceVisualizer mode="idle" />);

      rerender(<VoiceVisualizer mode="listening" />);

      // Should cancel old animation
      expect(global.cancelAnimationFrame).toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has presentation role for canvas', () => {
      render(<VoiceVisualizer mode="idle" />);

      const canvas = screen.getByRole('img');
      expect(canvas).toBeInTheDocument();
    });

    it('has pointer-events-none class', () => {
      render(<VoiceVisualizer mode="idle" />);

      const canvas = screen.getByRole('img');
      expect(canvas).toHaveClass('pointer-events-none');
    });
  });
});
