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

// The global setup mock for this context has no `latestCommand` surface, so
// this file overrides it with a controllable mock to drive the agent-command
// effect inside AudioRecorder (START/STOP/CANCEL commands).
let mockLatestCommand: any = null;
const mockClearLastCommand = jest.fn();
jest.mock('@/contexts/AgentAudioControlContext', () => ({
  AgentAudioControlProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  useAgentAudioControl: () => ({
    latestCommand: mockLatestCommand,
    clearLastCommand: mockClearLastCommand,
    isRecording: false,
    startRecording: jest.fn(),
    stopRecording: jest.fn(),
    isProcessing: false,
  }),
  AgentAudioCommand: {},
}));

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

// ---------------------------------------------------------------------------
// Extended coverage: agent commands, recorder errors, mime negotiation,
// upload guards, and the uploading state
// ---------------------------------------------------------------------------
describe('AudioRecorder (extended coverage)', () => {
  let errorSpy: jest.SpyInstance;
  let warnSpy: jest.SpyInstance;
  let logSpy: jest.SpyInstance;

  beforeEach(() => {
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
    warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
    logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
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
    mockLatestCommand = null;
    mockClearLastCommand.mockClear();
  });

  afterEach(() => {
    errorSpy.mockRestore();
    warnSpy.mockRestore();
    logSpy.mockRestore();
  });

  const startRecording = async () => {
    fireEvent.click(screen.getByRole('button', { name: /record/i }));
    await waitFor(() => expect(mockRecorder.start).toHaveBeenCalled());
  };

  const finishRecording = () => {
    mockRecorder.ondataavailable({ data: new Blob(['some audio data']) });
    mockRecorder.onstop();
  };

  // Re-renders the component so the context mock's latestCommand is picked up.
  // A NEW element tree must be created per sendCommand() — rerender()ing the
  // identical element reference lets React bail out without re-rendering.
  const renderAgent = () => {
    const onRecordingComplete = jest.fn();
    const onRecordingError = jest.fn();
    const makeTree = () => (
      <AgentAudioControlProvider>
        <AudioRecorder
          userId="test-user"
          onRecordingComplete={onRecordingComplete}
          onRecordingError={onRecordingError}
        />
      </AgentAudioControlProvider>
    );
    const view = render(makeTree());
    return {
      ...view,
      onRecordingComplete,
      onRecordingError,
      sendCommand: (command: any) => {
        mockLatestCommand = command;
        view.rerender(makeTree());
      },
    };
  };

  test('uses the initial suggested title when idle', () => {
    renderRecorder({ initialSuggestedTitle: 'Preset Title' });
    expect(screen.getByPlaceholderText('Optional title for your audio note')).toHaveValue(
      'Preset Title'
    );
  });

  test('agent START_RECORDING_SESSION command starts a recording', async () => {
    mockLatestCommand = {
      action: 'START_RECORDING_SESSION',
      payload: { suggestedTitle: 'Agent Note', linkedEventId: 'event-9' },
    };
    renderRecorder();

    await waitFor(() => expect(mockRecorder.start).toHaveBeenCalled());
    expect(mockClearLastCommand).toHaveBeenCalled();
    expect(getUserMediaMock).toHaveBeenCalled();
  });

  test('agent STOP command stops an active recording and uploads', async () => {
    const agent = renderAgent();
    await startRecording();

    agent.sendCommand({ action: 'STOP_RECORDING_SESSION' });

    await waitFor(() => expect(mockRecorder.stop).toHaveBeenCalled());
    finishRecording();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(mockClearLastCommand).toHaveBeenCalled();
  });

  test('agent CANCEL command cancels an active recording', async () => {
    const agent = renderAgent();
    await startRecording();

    agent.sendCommand({ action: 'CANCEL_RECORDING_SESSION' });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /record/i })).toBeInTheDocument();
    });
    expect(mockClearLastCommand).toHaveBeenCalled();
  });

  test('agent STOP and unknown commands outside a recording only warn', async () => {
    const agent = renderAgent();

    // STOP while idle -> warn, no recorder interaction
    agent.sendCommand({ action: 'STOP_RECORDING_SESSION' });
    await waitFor(() =>
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('STOP_RECORDING_SESSION')
      )
    );

    // unknown action -> warn
    warnSpy.mockClear();
    agent.sendCommand({ action: 'SOMETHING_ELSE' });
    await waitFor(() =>
      expect(warnSpy).toHaveBeenCalledWith(
        'Received unknown agent audio command action:',
        'SOMETHING_ELSE'
      )
    );
  });

  test('agent START while recording is ignored with a warning', async () => {
    const agent = renderAgent();
    await startRecording();
    const startCalls = mockRecorder.start.mock.calls.length;

    agent.sendCommand({ action: 'START_RECORDING_SESSION' });

    await waitFor(() =>
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('current status is recording')
      )
    );
    expect(mockRecorder.start.mock.calls.length).toBe(startCalls);
  });

  test('handles MediaRecorder runtime errors and preserves the title', async () => {
    renderRecorder({ initialSuggestedTitle: 'Keep Me' });
    await startRecording();

    mockRecorder.onerror({ error: { name: 'InvalidStateError' } });

    await waitFor(() =>
      expect(
        screen.getByText('MediaRecorder error: InvalidStateError')
      ).toBeInTheDocument()
    );
    // Title preserved after a recorder error
    expect(screen.getByPlaceholderText('Optional title for your audio note')).toHaveValue(
      'Keep Me'
    );
  });

  test('reports unsupported media devices without crashing', async () => {
    (navigator as any).mediaDevices = undefined;
    const { onRecordingError } = renderRecorder();

    fireEvent.click(screen.getByRole('button', { name: /record/i }));

    await waitFor(() =>
      expect(
        screen.getByText('Microphone access is not supported by your browser.')
      ).toBeInTheDocument()
    );
    expect(onRecordingError).toHaveBeenCalledWith(
      'Microphone access is not supported by your browser.'
    );
  });

  test('reports a friendly error when no microphone is found', async () => {
    getUserMediaMock.mockRejectedValue(
      Object.assign(new Error('none'), { name: 'NotFoundError' })
    );
    const { onRecordingError } = renderRecorder();

    fireEvent.click(screen.getByRole('button', { name: /record/i }));

    await waitFor(() =>
      expect(screen.getByText(/no microphone found/i)).toBeInTheDocument()
    );
    expect(onRecordingError).toHaveBeenCalledWith(expect.stringMatching(/no microphone found/i));
  });

  test('falls back to no mimeType when no audio type is supported', async () => {
    (global as any).MediaRecorder.isTypeSupported = jest.fn(() => false);
    renderRecorder();
    await startRecording();

    // MediaRecorder constructed without a mimeType option
    expect((global as any).MediaRecorder).toHaveBeenCalledWith(
      expect.anything(),
      undefined
    );
  });

  test('reports missing user id at upload time', async () => {
    const { onRecordingError } = renderRecorder({ userId: '' });
    await startRecording();
    fireEvent.click(screen.getByRole('button', { name: /stop & save/i }));
    finishRecording();

    await waitFor(() =>
      expect(onRecordingError).toHaveBeenCalledWith('User ID is missing.')
    );
    expect(global.fetch).not.toHaveBeenCalled();
  });

  test('shows the uploading message while the note is processed', async () => {
    let resolveUpload: (v: any) => void = () => {};
    (global as any).fetch = jest.fn(
      () =>
        new Promise((resolve) => {
          resolveUpload = resolve;
        })
    );

    renderRecorder();
    await startRecording();
    fireEvent.click(screen.getByRole('button', { name: /stop & save/i }));
    finishRecording();

    await waitFor(() =>
      expect(screen.getByText('Processing and saving your note...')).toBeInTheDocument()
    );

    resolveUpload({
      ok: true,
      json: async () => ({
        ok: true,
        data: { notion_page_url: 'u', title: 't', summary_preview: 's' },
      }),
    });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /record/i })).toBeInTheDocument()
    );
  });

  test('reports network failures during upload', async () => {
    (global as any).fetch = jest.fn().mockRejectedValue(new Error('offline'));
    const { onRecordingError } = renderRecorder();

    await startRecording();
    fireEvent.click(screen.getByRole('button', { name: /stop & save/i }));
    finishRecording();

    await waitFor(() =>
      expect(onRecordingError).toHaveBeenCalledWith(
        'Network error or server unavailable: offline'
      )
    );
  });

  test('empty data chunks are not accumulated', async () => {
    renderRecorder();
    await startRecording();

    mockRecorder.ondataavailable({ data: new Blob([]) });
    fireEvent.click(screen.getByRole('button', { name: /stop & save/i }));
    mockRecorder.onstop();

    // Blob type falls back since no chunks were collected
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
  });
});
