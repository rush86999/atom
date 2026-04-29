/**
 * AudioRecorder Component Tests
 *
 * Tests verify audio recording functionality, permissions,
 * playback, and export capabilities.
 *
 * Source: components/Audio/AudioRecorder.tsx (194 lines uncovered)
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AudioRecorder } from '../AudioRecorder';

// Mock MediaRecorder API
const mockMediaRecorder = {
  start: jest.fn(),
  stop: jest.fn(),
  pause: jest.fn(),
  resume: jest.fn(),
  ondataavailable: null,
  onstop: null,
  stream: null,
};

global.MediaRecorder = jest.fn().mockImplementation(() => mockMediaRecorder) as any;

// Mock navigator.mediaDevices
navigator.mediaDevices = {
  getUserMedia: jest.fn().mockResolvedValue({
    getTracks: () => [],
  }),
} as any;

describe('AudioRecorder', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: renders component
  test('renders component', () => {
    render(<AudioRecorder />);

    expect(screen.getByText(/record/i)).toBeInTheDocument();
  });

  // Test 2: requests microphone permission on mount
  test('requests microphone permission on mount', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({ audio: true });
    });
  });

  // Test 3: starts recording when record button clicked
  test('starts recording when record button clicked', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    expect(mockMediaRecorder.start).toHaveBeenCalled();
  });

  // Test 4: stops recording when stop button clicked
  test('stops recording when stop button clicked', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    await waitFor(() => {
      const stopButton = screen.getByRole('button', { name: /stop/i });
      fireEvent.click(stopButton);
    });

    expect(mockMediaRecorder.stop).toHaveBeenCalled();
  });

  // Test 5: displays recording time
  test('displays recording time', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    await waitFor(() => {
      expect(screen.getByText(/0:00/i)).toBeInTheDocument();
    });
  });

  // Test 6: handles permission denied
  test('handles permission denied', async () => {
    navigator.mediaDevices.getUserMedia = jest.fn().mockRejectedValue(
      new Error('Permission denied')
    );

    render(<AudioRecorder />);

    await waitFor(() => {
      expect(screen.getByText(/permission denied/i)).toBeInTheDocument();
    });
  });

  // Test 7: plays recorded audio
  test('plays recorded audio', async () => {
    render(<AudioRecorder />);

    // Record audio
    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    // Stop recording
    await waitFor(() => {
      const stopButton = screen.getByRole('button', { name: /stop/i });
      fireEvent.click(stopButton);
    });

    // Play audio
    await waitFor(() => {
      const playButton = screen.getByRole('button', { name: /play/i });
      fireEvent.click(playButton);
    });

    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
  });

  // Test 8: downloads recorded audio
  test('downloads recorded audio', async () => {
    render(<AudioRecorder />);

    // Record audio
    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    // Stop recording
    await waitFor(() => {
      const stopButton = screen.getByRole('button', { name: /stop/i });
      fireEvent.click(stopButton);
    });

    // Download
    await waitFor(() => {
      const downloadButton = screen.getByRole('button', { name: /download/i });
      expect(downloadButton).toBeInTheDocument();
    });
  });

  // Test 9: pauses recording
  test('pauses recording', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    await waitFor(() => {
      const pauseButton = screen.getByRole('button', { name: /pause/i });
      fireEvent.click(pauseButton);
    });

    expect(mockMediaRecorder.pause).toHaveBeenCalled();
  });

  // Test 10: resumes recording
  test('resumes recording', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    await waitFor(() => {
      const pauseButton = screen.getByRole('button', { name: /pause/i });
      fireEvent.click(pauseButton);
    });

    await waitFor(() => {
      const resumeButton = screen.getByRole('button', { name: /resume/i });
      fireEvent.click(resumeButton);
    });

    expect(mockMediaRecorder.resume).toHaveBeenCalled();
  });

  // Test 11: deletes recording
  test('deletes recording', async () => {
    render(<AudioRecorder />);

    // Record audio
    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    // Stop recording
    await waitFor(() => {
      const stopButton = screen.getByRole('button', { name: /stop/i });
      fireEvent.click(stopButton);
    });

    // Delete
    await waitFor(() => {
      const deleteButton = screen.getByRole('button', { name: /delete/i });
      fireEvent.click(deleteButton);
    });

    await waitFor(() => {
      expect(screen.queryByText(/play/i)).not.toBeInTheDocument();
    });
  });

  // Test 12: displays audio waveform
  test('displays audio waveform', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    await waitFor(() => {
      const waveform = screen.getByTestId(/waveform/i);
      expect(waveform).toBeInTheDocument();
    });
  });

  // Test 13: adjusts recording quality
  test('adjusts recording quality', () => {
    render(<AudioRecorder />);

    const qualitySelect = screen.getByRole('combobox', { name: /quality/i });
    fireEvent.change(qualitySelect, { target: { value: 'high' } });

    expect(qualitySelect).toHaveValue('high');
  });

  // Test 14: shows recording indicator
  test('shows recording indicator', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    await waitFor(() => {
      const indicator = screen.getByTestId(/recording-indicator/i);
      expect(indicator).toBeInTheDocument();
      expect(indicator).toHaveClass('recording');
    });
  });

  // Test 15: handles maximum recording duration
  test('handles maximum recording duration', async () => {
    render(<AudioRecorder />);

    await waitFor(() => {
      const recordButton = screen.getByRole('button', { name: /record/i });
      fireEvent.click(recordButton);
    });

    // Simulate max duration reached
    await waitFor(() => {
      expect(mockMediaRecorder.stop).toHaveBeenCalled();
    }, { timeout: 10000 });
  });
});
