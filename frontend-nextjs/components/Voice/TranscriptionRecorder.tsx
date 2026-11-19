'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { localModelsAPI } from '../../lib/api';

interface LocalModelProvider {
  id: string;
  name: string;
  provider_type?: string;
  is_active?: boolean;
}

interface LocalModelCapability {
  model_id: string;
  supports_transcription: boolean;
  audio_input_cost_per_second_usd: number | null;
}

interface TranscriptionModel {
  providerId: string;
  providerName: string;
  modelId: string;
}

type RecorderState =
  | 'idle'
  | 'requesting'
  | 'recording'
  | 'ready'
  | 'transcribing';

const PREFERRED_MIME_TYPES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/ogg',
  'audio/mp4',
];

function chooseMimeType(): string {
  if (typeof MediaRecorder === 'undefined') return '';
  if (typeof MediaRecorder.isTypeSupported !== 'function') return '';
  return (
    PREFERRED_MIME_TYPES.find((type) => MediaRecorder.isTypeSupported(type)) ||
    ''
  );
}

function filenameForBlob(blob: Blob): string {
  const type = (blob.type || '').toLowerCase();
  if (type.includes('wav')) return 'recording.wav';
  if (type.includes('ogg')) return 'recording.ogg';
  if (type.includes('mp4') || type.includes('m4a')) return 'recording.m4a';
  if (type.includes('mpeg') || type.includes('mp3')) return 'recording.mp3';
  return 'recording.webm';
}

function formatTime(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
    .toString()
    .padStart(2, '0');
  const remainder = (seconds % 60).toString().padStart(2, '0');
  return `${minutes}:${remainder}`;
}

function recordingErrorMessage(error: any): string {
  if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError') {
    return 'Microphone permission was denied. Enable microphone access in your browser and try again.';
  }
  if (error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') {
    return 'No microphone was found. Connect a microphone and try again.';
  }
  return 'Recording failed. Check microphone access and try again.';
}

function transcriptionErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim()) return detail;
  return 'Transcription failed. Please try again.';
}

function extractTranscript(payload: any): string | null {
  if (typeof payload === 'string') return payload;
  if (!payload || typeof payload !== 'object') return null;
  if (typeof payload.transcript === 'string') return payload.transcript;
  if (typeof payload.transcription === 'string') {
    return payload.transcription;
  }
  if (typeof payload.text === 'string') return payload.text;
  if (typeof payload.data === 'string') return payload.data;
  if (payload.data && typeof payload.data === 'object') {
    if (typeof payload.data.transcript === 'string') {
      return payload.data.transcript;
    }
    if (typeof payload.data.transcription === 'string') {
      return payload.data.transcription;
    }
    if (typeof payload.data.text === 'string') return payload.data.text;
  }
  return null;
}

export const TranscriptionRecorder: React.FC = () => {
  const [providers, setProviders] = useState<LocalModelProvider[]>([]);
  const [capabilities, setCapabilities] = useState<
    Record<string, LocalModelCapability[]>
  >({});
  const [loadingModels, setLoadingModels] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedProviderId, setSelectedProviderId] = useState('');
  const [selectedModelId, setSelectedModelId] = useState('');
  const [state, setState] = useState<RecorderState>('idle');
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const mountedRef = useRef(true);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mimeTypeRef = useRef('');

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoadingModels(true);
      setLoadError(null);
      try {
        const providerPayload = await localModelsAPI.listProviders();
        const providerList: LocalModelProvider[] = Array.isArray(providerPayload)
          ? providerPayload.filter((provider: any) => provider?.id)
          : [];
        if (cancelled) return;
        setProviders(providerList);

        const entries = await Promise.all(
          providerList.map(
            async (provider): Promise<[string, LocalModelCapability[]]> => {
              try {
                const capabilityPayload = await localModelsAPI.getCapabilities(
                  provider.id,
                );
                return [
                  provider.id,
                  Array.isArray(capabilityPayload) ? capabilityPayload : [],
                ];
              } catch {
                return [provider.id, []];
              }
            },
          ),
        );
        if (cancelled) return;
        const nextCapabilities: Record<string, LocalModelCapability[]> = {};
        entries.forEach(([providerId, models]) => {
          nextCapabilities[providerId] = models;
        });
        setCapabilities(nextCapabilities);
      } catch {
        if (!cancelled) {
          setProviders([]);
          setCapabilities({});
          setLoadError(
            'Could not load your local models. Open Local Models settings, then retry.',
          );
        }
      } finally {
        if (!cancelled) setLoadingModels(false);
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stopStreamTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => {
        try {
          track.stop();
        } catch {
          // Track cleanup is best-effort; never mask the recording state.
        }
      });
      streamRef.current = null;
    }
  }, []);

  const cleanupRecorder = useCallback(() => {
    clearTimer();
    stopStreamTracks();
    const recorder = mediaRecorderRef.current;
    mediaRecorderRef.current = null;
    chunksRef.current = [];
    if (recorder) {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      recorder.onerror = null;
      if (recorder.state !== 'inactive') {
        try {
          recorder.stop();
        } catch {
          // Already stopped.
        }
      }
    }
  }, [clearTimer, stopStreamTracks]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      cleanupRecorder();
    };
  }, [cleanupRecorder]);

  const transcriptionModels = useMemo<TranscriptionModel[]>(() => {
    const models: TranscriptionModel[] = [];
    providers.forEach((provider) => {
      if (provider.is_active === false) return;
      (capabilities[provider.id] || []).forEach((capability) => {
        const audioRate = capability?.audio_input_cost_per_second_usd;
        if (
          capability?.supports_transcription === true &&
          typeof audioRate === 'number' &&
          Number.isFinite(audioRate) &&
          audioRate >= 0
        ) {
          models.push({
            providerId: provider.id,
            providerName: provider.name,
            modelId: capability.model_id,
          });
        }
      });
    });
    return models;
  }, [providers, capabilities]);

  const modelsForProvider = useMemo(
    () =>
      transcriptionModels.filter(
        (model) => model.providerId === selectedProviderId,
      ),
    [transcriptionModels, selectedProviderId],
  );

  const selectedProvider =
    providers.find((provider) => provider.id === selectedProviderId) || null;
  const selectedModel =
    modelsForProvider.find((model) => model.modelId === selectedModelId) ||
    null;
  const selectionReady = Boolean(selectedProvider && selectedModel);

  const handleProviderChange = (
    event: React.ChangeEvent<HTMLSelectElement>,
  ) => {
    setSelectedProviderId(event.target.value);
    setSelectedModelId('');
    setTranscript(null);
    setError(null);
  };

  const handleModelChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setSelectedModelId(event.target.value);
    setTranscript(null);
    setError(null);
  };

  const startRecording = useCallback(async () => {
    if (state === 'requesting' || state === 'recording' || state === 'transcribing') {
      return;
    }
    if (!selectionReady) {
      setError('Select a provider and model before recording.');
      return;
    }
    if (
      typeof navigator === 'undefined' ||
      !navigator.mediaDevices ||
      typeof navigator.mediaDevices.getUserMedia !== 'function' ||
      typeof MediaRecorder === 'undefined'
    ) {
      setError('Recording is not supported by this browser.');
      return;
    }

    setError(null);
    setTranscript(null);
    setAudioBlob(null);
    chunksRef.current = [];
    setElapsedSeconds(0);
    setState('requesting');

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;

      const mimeType = chooseMimeType();
      mimeTypeRef.current = mimeType;
      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined,
      );
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event: BlobEvent) => {
        if (event.data && event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onerror = () => {
        setError('Recording failed. Check microphone access and try again.');
        setState('idle');
        cleanupRecorder();
      };

      recorder.onstop = () => {
        const chunks = chunksRef.current;
        const blobType =
          mimeTypeRef.current || chunks[0]?.type || 'audio/webm';
        const blob = new Blob(chunks, { type: blobType });
        chunksRef.current = [];
        mediaRecorderRef.current = null;
        clearTimer();
        stopStreamTracks();

        if (blob.size === 0) {
          setAudioBlob(null);
          setState('idle');
          setError('No audio was captured. Try recording again.');
          return;
        }
        setAudioBlob(blob);
        setState('ready');
      };

      recorder.start();
      setState('recording');
      timerRef.current = setInterval(() => {
        setElapsedSeconds((seconds) => seconds + 1);
      }, 1000);
    } catch (caught) {
      cleanupRecorder();
      if (mountedRef.current) {
        setState('idle');
        setError(recordingErrorMessage(caught));
      }
    }
  }, [
    cleanupRecorder,
    clearTimer,
    selectionReady,
    state,
    stopStreamTracks,
  ]);

  const stopRecording = useCallback(() => {
    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === 'inactive') {
      clearTimer();
      stopStreamTracks();
      setState((current) => (current === 'recording' ? 'idle' : current));
      return;
    }
    // The onstop handler assembles the blob and moves to 'ready'. Tracks are
    // released immediately; the recorder has already finalized this segment.
    try {
      recorder.stop();
    } catch {
      cleanupRecorder();
      setState('idle');
      return;
    }
    clearTimer();
    stopStreamTracks();
  }, [cleanupRecorder, clearTimer, stopStreamTracks]);

  const transcribeRecording = useCallback(async () => {
    if (!audioBlob || !selectedProvider || !selectedModel) return;
    if (state === 'recording' || state === 'requesting' || state === 'transcribing') {
      return;
    }

    setError(null);
    setTranscript(null);
    setState('transcribing');

    try {
      const payload = await localModelsAPI.transcribe(
        selectedProvider.id,
        selectedModel.modelId,
        audioBlob,
        filenameForBlob(audioBlob),
      );
      const text = extractTranscript(payload);
      if (text === null) {
        throw new Error('missing transcript');
      }
      if (!mountedRef.current) return;
      setTranscript(text);
      setState('ready');
    } catch (caught) {
      if (!mountedRef.current) return;
      setError(transcriptionErrorMessage(caught));
      setState('ready');
    }
  }, [audioBlob, selectedModel, selectedProvider, state]);

  const busy =
    state === 'requesting' || state === 'recording' || state === 'transcribing';

  return (
    <section
      aria-label="Record and transcribe audio"
      className="rounded-lg border border-gray-200 bg-white p-6 shadow dark:border-gray-700 dark:bg-gray-800"
    >
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-gray-100">
          Record &amp; Transcribe
        </h2>
        <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
          Record an audio note, then explicitly send it to the selected
          workspace-registered model. Nothing is transcribed until you choose
          Transcribe.
        </p>
      </div>

      {loadingModels ? (
        <p className="mb-4 text-sm text-gray-600 dark:text-gray-400">
          Loading local models…
        </p>
      ) : null}

      {loadError ? (
        <p
          role="alert"
          className="mb-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
        >
          {loadError}
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700 dark:text-gray-300">
          Provider
          <select
            aria-label="Provider"
            value={selectedProviderId}
            onChange={handleProviderChange}
            disabled={busy || loadingModels}
            className="rounded border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
          >
            <option value="">Select a provider…</option>
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-sm font-medium text-gray-700 dark:text-gray-300">
          Model
          <select
            aria-label="Model"
            value={selectedModelId}
            onChange={handleModelChange}
            disabled={busy || loadingModels || !selectedProviderId}
            className="rounded border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100"
          >
            <option value="">Select a model…</option>
            {modelsForProvider.map((model) => (
              <option key={model.modelId} value={model.modelId}>
                {model.modelId}
              </option>
            ))}
          </select>
        </label>
      </div>

      <p
        data-testid="selection-summary"
        className="mt-3 text-sm text-gray-700 dark:text-gray-300"
      >
        <span className="font-semibold">Selected: </span>
        {selectedProvider && selectedModel
          ? `${selectedProvider.name} / ${selectedModel.modelId}`
          : 'No provider/model selected'}
      </p>

      {!loadingModels && !loadError && providers.length === 0 ? (
        <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">
          No local providers are registered yet. Register one in Local Models
          settings, then enable transcription for a model.
        </p>
      ) : null}

      {!loadingModels &&
      !loadError &&
      providers.length > 0 &&
      transcriptionModels.length === 0 ? (
        <p className="mt-3 text-sm text-amber-700 dark:text-amber-300">
          No workspace model has transcription enabled. Enable it for a model in
          Local Models settings first.
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void startRecording()}
          disabled={!selectionReady || busy}
          className="rounded bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          Start recording
        </button>
        <button
          type="button"
          onClick={stopRecording}
          disabled={state !== 'recording'}
          className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          Stop
        </button>
        <button
          type="button"
          onClick={() => void transcribeRecording()}
          disabled={!audioBlob || !selectionReady || busy}
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          Transcribe
        </button>
      </div>

      <div
        className="mt-4 text-sm text-gray-700 dark:text-gray-300"
        aria-live="polite"
      >
        {state === 'requesting' ? 'Requesting microphone permission…' : null}
        {state === 'recording'
          ? `Recording… ${formatTime(elapsedSeconds)}`
          : null}
        {state === 'ready' && audioBlob
          ? 'Recording ready. Choose Transcribe to send it to the selected model.'
          : null}
        {state === 'transcribing' ? 'Transcribing…' : null}
        {state === 'idle' && !audioBlob ? 'Ready to record.' : null}
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-4 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
        >
          {error}
        </p>
      ) : null}

      {transcript !== null ? (
        <div
          role="status"
          aria-live="polite"
          data-testid="transcript-confirmation"
          className="mt-5 rounded border border-emerald-300 bg-emerald-50 p-4 dark:border-emerald-800 dark:bg-emerald-950"
        >
          <h3 className="text-sm font-semibold text-emerald-900 dark:text-emerald-100">
            Transcript
          </h3>
          <p
            data-testid="confirmed-transcript"
            className="mt-2 whitespace-pre-wrap text-sm text-emerald-900 dark:text-emerald-100"
          >
            {transcript || 'No speech detected.'}
          </p>
        </div>
      ) : null}
    </section>
  );
};

export default TranscriptionRecorder;
