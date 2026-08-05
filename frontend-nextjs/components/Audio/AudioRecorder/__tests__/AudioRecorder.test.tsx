/**
 * AudioRecorder Component Tests
 *
 * Tests verify audio recording functionality, permissions, and the
 * upload-to-processing flow triggered when a recording stops.
 *
 * Source: components/Audio/AudioRecorder.tsx
 *
 * Real behavior (verified against source):
 * - No microphone permission is requested on mount; only when "Record" is clicked.
 * - UI buttons: "Record" (idle/error), "Stop & Save" + "Cancel" (recording).
 * - Timer is formatted as MM:SS (00:00).
 * - On stop the component POSTs the blob to /api/process-recorded-audio-note.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AudioRecorder from '../../AudioRecorder';
import { AgentAudioControlProvider } from '@/contexts/AgentAudioControlContext';

const PROCESS_AUDIO_NOTE_ENDPOINT = '/api/process-recorded-audio-note';

// Fresh MediaRecorder instance per construction so each rendered component
// gets its own mock. The component requires a static isTypeSupported() and a
// `state` of "recording" before it will call stop().
let mockRecorder: any;
const getUserMediaMock = jest.fn();

const setupMediaMocks = () => {
  (global as any).MediaRecorder = jest.fn().mockImplementation(() => {
    mockRecorder = {
      start: jest.fn(),
      stop: jest.fn(),
      pause: jest.fn(),
      resume: jest.fn(),
      state: 'recording',
      ondataavailable: null,
      onstop: null,
      onerror: null,
      stream: null,
    };
    return mockRecorder;
  });
  (global as any).MediaRecorder.isTypeSupported = jest.fn(() => true);
};

// jsdom's FormData rejects jsdom-hostile Blobs (Node's native Blob shadows
// jsdom's, breaking the internal brand check), so swap in a tiny fake that
// simply records appended entries. This lets the component's upload path run.
class MockFormData {
  private entries: Array<[string, unknown, string | undefined]> = [];
  append(name: string, value: unknown, filename?: string) {
    this.entries.push([name, value, filename]);
  }
}

const renderRecorder = (props: Record<string, unknown> = {}) => {
  const onRecordingComplete = jest.fn();
  const onRecordingError = jest.fn();

  render(
    <AgentAudioControlProvider>
      <AudioRecorder
        userId="test-user"
        onRecordingComplete={onRecordingComplete}
        onRecordingError={onRecordingError}
        {...(props as any)}
      />
    </AgentAudioControlProvider>
  );

  return { onRecordingComplete, onRecordingError };
};

describe('AudioRecorder', () => {
  beforeEach(() => {
    // jest.config.js sets resetMocks/clearMocks/restoreMocks, which wipe mock
    // implementations between tests, so every mock must be re-established here.
    setupMediaMocks();
    (global as any).FormData = MockFormData;
    getUserMediaMock.mockReset();
    getUserMediaMock.mockResolvedValue({ getTracks: () => [] });
    (navigator as any).mediaDevices = { getUserMedia: getUserMediaMock };
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        data: {
          notion_page_url: 'https://notion.test/page',
          title: 'My Note',
          summary_preview: 'Summary',
        },
      }),
    });
  });

  // Clicks Record and waits for recording to actually start.
  const startRecording = async () => {
    fireEvent.click(screen.getByRole('button', { name: /record/i }));
    await waitFor(() => expect(mockRecorder.start).toHaveBeenCalled());
  };

  // Simulates the recorder finishing: pushes a data chunk then fires onstop,
  // which is what triggers the upload-to-processing flow. A real Blob is used
  // so jsdom can reconstruct the final recording blob in the component.
  const finishRecording = () => {
    mockRecorder.ondataavailable({ data: new Blob(['some audio data']) });
    mockRecorder.onstop();
  };

  test('renders the component with a Record button and title input', () => {
    renderRecorder();
    expect(screen.getByRole('button', { name: /record/i })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Optional title for your audio note')).toBeInTheDocument();
  });

  test('does not request microphone permission on mount', () => {
    renderRecorder();
    expect(getUserMediaMock).not.toHaveBeenCalled();
  });

  test('requests microphone permission when Record is clicked', async () => {
    renderRecorder();
    fireEvent.click(screen.getByRole('button', { name: /record/i }));
    await waitFor(() => expect(getUserMediaMock).toHaveBeenCalledWith({ audio: true }));
  });

  test('starts recording when Record is clicked', async () => {
    renderRecorder();
    await startRecording();
    expect(getUserMediaMock).toHaveBeenCalled();
    expect(mockRecorder.start).toHaveBeenCalled();
  });

  test('shows recording indicator and timer while recording', async () => {
    renderRecorder();
    await startRecording();
    expect(screen.getByText('Recording')).toBeInTheDocument();
    expect(screen.getByText(/^00:0\d$/)).toBeInTheDocument();
  });

  test('stops recording when Stop & Save is clicked', async () => {
    renderRecorder();
    await startRecording();
    fireEvent.click(screen.getByRole('button', { name: /stop & save/i }));
    expect(mockRecorder.stop).toHaveBeenCalled();
  });

  test('cancels recording and returns to the idle Record button', async () => {
    renderRecorder();
    await startRecording();
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.getByRole('button', { name: /record/i })).toBeInTheDocument();
  });

  test('shows a permission denied error when microphone access is rejected', async () => {
    getUserMediaMock.mockRejectedValue(
      Object.assign(new Error('denied'), { name: 'NotAllowedError' })
    );
    const { onRecordingError } = renderRecorder();
    fireEvent.click(screen.getByRole('button', { name: /record/i }));
    await waitFor(() =>
      expect(screen.getByText(/permission denied/i)).toBeInTheDocument()
    );
    expect(onRecordingError).toHaveBeenCalledWith(expect.stringMatching(/permission denied/i));
  });

  test('shows a generic error when microphone access fails', async () => {
    getUserMediaMock.mockRejectedValue(new Error('boom'));
    renderRecorder();
    fireEvent.click(screen.getByRole('button', { name: /record/i }));
    await waitFor(() =>
      expect(screen.getByText(/error accessing microphone/i)).toBeInTheDocument()
    );
  });

  test('uploads the recorded audio note to the processing endpoint when recording stops', async () => {
    renderRecorder();
    await startRecording();
    fireEvent.click(screen.getByRole('button', { name: /stop & save/i }));
    finishRecording();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(global.fetch).toHaveBeenCalledWith(
      PROCESS_AUDIO_NOTE_ENDPOINT,
      expect.objectContaining({ method: 'POST' })
    );
  });

  test('calls onRecordingComplete with the upload response data', async () => {
    const { onRecordingComplete } = renderRecorder();
    await startRecording();
    fireEvent.click(screen.getByRole('button', { name: /stop & save/i }));
    finishRecording();
    await waitFor(() =>
      expect(onRecordingComplete).toHaveBeenCalledWith(
        'https://notion.test/page',
        'My Note',
        'Summary'
      )
    );
  });

  test('shows an error and calls onRecordingError when the upload fails', async () => {
    (global as any).fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ ok: false, message: 'Failed to process audio note (HTTP 500).' }),
    });
    const { onRecordingError } = renderRecorder();
    await startRecording();
    fireEvent.click(screen.getByRole('button', { name: /stop & save/i }));
    finishRecording();
    await waitFor(() => expect(onRecordingError).toHaveBeenCalled());
    expect(screen.getByText(/failed to process audio note/i)).toBeInTheDocument();
  });
});
