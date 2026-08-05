/**
 * VoiceVisualizer Component Tests
 *
 * Tests verify the canvas visualizer renders, animates via rAF, and applies
 * the correct color/glow per mode.
 *
 * Source: components/Voice/VoiceVisualizer.tsx
 *
 * Real behavior (verified against source):
 * - Renders a single <canvas width={400} height={100} className="w-full h-24
 *   pointer-events-none" />. The canvas has NO role/aria-label, so tests query
 *   it via document.querySelector('canvas').
 * - On mount (and every mode change) it runs one animate() frame immediately,
 *   then schedules the next frame via requestAnimationFrame. Each frame draws
 *   40 rounded bars with mode-specific fillStyle and shadow:
 *     idle:       rgb(100, 116, 139), shadowBlur 0
 *     listening:  rgb(16, 185, 129),  shadowBlur 15
 *     processing: rgb(249, 115, 22),  shadowBlur 15
 *     speaking:   rgb(59, 130, 246),  shadowBlur 15
 * - Cleanup calls cancelAnimationFrame(requestIdRef.current).
 *
 * NOTE: The component relies on Next.js's automatic JSX runtime (it imports no
 * default React), but this repo's Jest transform uses ts-jest with jsx:"react"
 * (classic runtime -> React.createElement). We expose React as a global so the
 * compiled component resolves it during render. requestAnimationFrame is mocked
 * to queue callbacks instead of running them, so frames can be driven manually.
 */

import React from 'react';
import { render } from '@testing-library/react';
import '@testing-library/jest-dom';
import { VoiceVisualizer } from '../VoiceVisualizer';

// Classic-JSX compatibility: source module has no default React import.
(global as any).React = React;

const mockCtx: any = {
  clearRect: jest.fn(),
  fillStyle: '',
  fillRect: jest.fn(),
  fill: jest.fn(),
  beginPath: jest.fn(),
  roundRect: jest.fn(),
  shadowBlur: 0,
  shadowColor: '',
};

let rafCallbacks: FrameRequestCallback[] = [];

const getCanvas = () => document.querySelector('canvas') as HTMLCanvasElement;

const renderVisualizer = (
  mode: 'idle' | 'listening' | 'processing' | 'speaking' = 'idle'
) => render(<VoiceVisualizer mode={mode} />);

describe('VoiceVisualizer Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    rafCallbacks = [];
    HTMLCanvasElement.prototype.getContext = jest.fn(() => mockCtx as any);
    global.requestAnimationFrame = jest.fn((cb: FrameRequestCallback) => {
      rafCallbacks.push(cb);
      return rafCallbacks.length;
    }) as any;
    global.cancelAnimationFrame = jest.fn();
  });

  describe('Rendering', () => {
    it('renders a canvas element', () => {
      renderVisualizer();
      expect(getCanvas()).toBeInTheDocument();
    });

    it('renders canvas with correct dimensions', () => {
      renderVisualizer();
      const canvas = getCanvas();
      expect(canvas.width).toBe(400);
      expect(canvas.height).toBe(100);
    });

    it('has correct CSS classes', () => {
      renderVisualizer();
      expect(getCanvas()).toHaveClass('w-full', 'h-24', 'pointer-events-none');
    });
  });

  describe('Canvas Context', () => {
    it('gets a 2D context from the canvas', () => {
      renderVisualizer();
      expect(HTMLCanvasElement.prototype.getContext).toHaveBeenCalledWith('2d');
    });

    it('handles null context gracefully', () => {
      HTMLCanvasElement.prototype.getContext = jest.fn(() => null);
      expect(() => renderVisualizer()).not.toThrow();
    });
  });

  describe('Animation Lifecycle', () => {
    it('starts animation on mount', () => {
      renderVisualizer();
      expect(global.requestAnimationFrame).toHaveBeenCalled();
    });

    it('cleans up animation on unmount', () => {
      const { unmount } = renderVisualizer();
      unmount();
      expect(global.cancelAnimationFrame).toHaveBeenCalled();
    });

    it('restarts animation when mode changes', () => {
      const { rerender } = render(<VoiceVisualizer mode="idle" />);
      const callsBefore = (global.requestAnimationFrame as jest.Mock).mock.calls.length;

      rerender(<VoiceVisualizer mode="listening" />);

      const callsAfter = (global.requestAnimationFrame as jest.Mock).mock.calls.length;
      expect(callsAfter).toBeGreaterThan(callsBefore);
    });
  });

  describe('Animation Behavior', () => {
    it('clears the canvas on each frame', () => {
      renderVisualizer('idle');
      // The initial animate() frame cleared once; run the queued frame for a second.
      rafCallbacks.pop()?.(performance.now());
      expect(mockCtx.clearRect).toHaveBeenCalledTimes(2);
    });

    it('draws bars', () => {
      renderVisualizer('idle');
      expect(mockCtx.beginPath).toHaveBeenCalled();
      expect(mockCtx.roundRect).toHaveBeenCalled();
      expect(mockCtx.fill).toHaveBeenCalled();
    });

    it('draws 40 bars per frame', () => {
      renderVisualizer('listening');
      expect(mockCtx.roundRect).toHaveBeenCalledTimes(40);
    });
  });

  describe('Visual Effects / Colors', () => {
    it.each([
      ['idle', 'rgb(100, 116, 139)', 0],
      ['listening', 'rgb(16, 185, 129)', 15],
      ['processing', 'rgb(249, 115, 22)', 15],
      ['speaking', 'rgb(59, 130, 246)', 15],
    ] as const)('%s mode uses %s with shadowBlur %d', (mode, color, shadowBlur) => {
      renderVisualizer(mode);
      expect(mockCtx.fillStyle).toBe(color);
      expect(mockCtx.shadowBlur).toBe(shadowBlur);
      if (shadowBlur > 0) {
        expect(mockCtx.shadowColor).toBe(color);
      }
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

    it('cancels the previous animation before starting a new one', () => {
      const { rerender } = render(<VoiceVisualizer mode="idle" />);
      rerender(<VoiceVisualizer mode="listening" />);
      expect(global.cancelAnimationFrame).toHaveBeenCalled();
    });
  });
});
