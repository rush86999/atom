import React from 'react';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';

import TranscriptionRecorder from '../TranscriptionRecorder';
import { localModelsAPI } from '../../../lib/api';

jest.mock('../../../lib/api', () => ({
  __esModule: true,
  localModelsAPI: {
    listProviders: jest.fn(),
    getCapabilities: jest.fn(),
    transcribe: jest.fn(),
  },
}));

const api = localModelsAPI as unknown as {
  listProviders: jest.Mock;
  getCapabilities: jest.Mock;
  transcribe: jest.Mock;
};

const providers = [
  {
    id: 'provider-1',
    name: 'Local Whisper',
    provider_type: 'custom',
    is_active: true,
  },
];

const capabilities = [
  {
    model_id: 'whisper-small',
    supports_transcription: true,
    audio_input_cost_per_second_usd: 0,
  },
  {
    model_id: 'chat-only',
    supports_transcription: false,
    audio_input_cost_per_second_usd: null,
  },
];

class MockMediaRecorder {
  static isTypeSupported = jest.fn(() => true);

  state = 'inactive';
  ondataavailable: ((event: any) => void) | null = null;
  onstop: ((event: any) => void) | null = null;
  onerror: ((event: any) => void) | null = null;

  constructor(public stream: any, public options: any) {}

  start = jest.fn(() => {
    this.state = 'recording';
  });

  stop = jest.fn(() => {
    this.state = 'inactive';
    this.ondataavailable?.({
      data: new Blob([new Uint8Array([1, 2, 3, 4])], {
        type: 'audio/webm',
      }),
    });
    this.onstop?.({});
  });
}

describe('TranscriptionRecorder', () => {
  let getUserMedia: jest.Mock;
  let stopTrack: jest.Mock;

  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    stopTrack = jest.fn();
    getUserMedia = jest.fn().mockResolvedValue({
      getTracks: () => [{ stop: stopTrack }],
    });

    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia },
    });
    (global as any).MediaRecorder = MockMediaRecorder;

    api.listProviders.mockResolvedValue(providers);
    api.getCapabilities.mockResolvedValue(capabilities);
    api.transcribe.mockResolvedValue({ transcript: 'hello world' });
  });

  async function selectTranscriptionModel() {
    const user = userEvent.setup();
    await waitFor(() => expect(api.listProviders).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByLabelText('Provider')).toBeEnabled(),
    );

    await user.selectOptions(screen.getByLabelText('Provider'), 'provider-1');
    await waitFor(() =>
      expect(
        screen.getByRole('option', { name: 'whisper-small' }),
      ).toBeInTheDocument(),
    );
    await user.selectOptions(screen.getByLabelText('Model'), 'whisper-small');
    return user;
  }

  it('shows only models with an enabled audio transcription declaration', async () => {
    const user = userEvent.setup();
    render(<TranscriptionRecorder />);

    await waitFor(() => expect(api.listProviders).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByLabelText('Provider')).toBeEnabled(),
    );
    await user.selectOptions(screen.getByLabelText('Provider'), 'provider-1');

    await waitFor(() =>
      expect(
        screen.getByRole('option', { name: 'whisper-small' }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.queryByRole('option', { name: 'chat-only' }),
    ).not.toBeInTheDocument();
  });

  it('visibly identifies the explicitly selected provider and model', async () => {
    render(<TranscriptionRecorder />);
    await selectTranscriptionModel();

    expect(screen.getByTestId('selection-summary')).toHaveTextContent(
      'Local Whisper / whisper-small',
    );
  });

  it('records, stops, and waits for an explicit Transcribe action', async () => {
    render(<TranscriptionRecorder />);
    const user = await selectTranscriptionModel();

    expect(screen.getByRole('button', { name: 'Start recording' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Start recording' }));

    await waitFor(() =>
      expect(getUserMedia).toHaveBeenCalledWith({ audio: true }),
    );
    expect(screen.getByText(/Recording…/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Stop' }));

    await waitFor(() => expect(stopTrack).toHaveBeenCalled());
    expect(
      screen.getByRole('button', { name: 'Transcribe' }),
    ).toBeEnabled();
    // Stopping only prepares the recording. It must never auto-send audio.
    expect(api.transcribe).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Transcribe' }));

    await waitFor(() => expect(api.transcribe).toHaveBeenCalledTimes(1));
    const [providerId, modelId, blob, filename] = api.transcribe.mock.calls[0];
    expect(providerId).toBe('provider-1');
    expect(modelId).toBe('whisper-small');
    expect(blob).toBeInstanceOf(Blob);
    expect(filename).toBe('recording.webm');

    await waitFor(() =>
      expect(screen.getByTestId('confirmed-transcript')).toHaveTextContent(
        'hello world',
      ),
    );
  });

  it('shows the backend user-facing error and keeps the recording for retry', async () => {
    api.transcribe.mockRejectedValue({
      response: {
        data: { detail: 'That audio file could not be read. Try recording again.' },
      },
    });

    render(<TranscriptionRecorder />);
    const user = await selectTranscriptionModel();

    await user.click(screen.getByRole('button', { name: 'Start recording' }));
    await waitFor(() => expect(getUserMedia).toHaveBeenCalled());
    await user.click(screen.getByRole('button', { name: 'Stop' }));
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Transcribe' }),
      ).toBeEnabled(),
    );

    await user.click(screen.getByRole('button', { name: 'Transcribe' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'That audio file could not be read. Try recording again.',
    );
    expect(screen.queryByTestId('transcript-confirmation')).not.toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Transcribe' }),
    ).toBeEnabled();
  });

  it('releases microphone tracks when unmounted mid-recording', async () => {
    const { unmount } = render(<TranscriptionRecorder />);
    const user = await selectTranscriptionModel();

    await user.click(screen.getByRole('button', { name: 'Start recording' }));
    await waitFor(() => expect(getUserMedia).toHaveBeenCalled());
    expect(stopTrack).not.toHaveBeenCalled();

    unmount();

    expect(stopTrack).toHaveBeenCalled();
  });

  it('keeps recording and transcription disabled before a model is selected', async () => {
    render(<TranscriptionRecorder />);

    await waitFor(() => expect(api.listProviders).toHaveBeenCalled());

    expect(
      screen.getByRole('button', { name: 'Start recording' }),
    ).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Transcribe' })).toBeDisabled();
  });
});
