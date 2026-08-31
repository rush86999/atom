/**
 * WakeWordDetector Component Tests
 *
 * Tests verify the real WakeWordDetector
 * (components/Voice/WakeWordDetector.tsx) with mocked audio APIs
 * (getUserMedia, AudioContext, analyser, requestAnimationFrame):
 * - default models + status card render
 * - loading state while the mic initializes
 * - microphone permission denied -> error toast, stays inactive
 * - start/stop listening lifecycle (tracks stopped, context closed)
 * - unmount cleanup runs without crashing (regression: streamRef /
 *   audioContextRef were referenced but never defined)
 * - simulated detection fires onDetection, records a detection card and
 *   toasts (regression: the interval used stale closure state and could
 *   never fire); stopping ends detection
 * - model selection, sensitivity slider, model upload validation and
 *   model download callbacks
 * - compact view and hidden navigation
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import WakeWordDetector from '../WakeWordDetector';

const mockToast = jest.fn();
jest.mock('@/components/ui/use-toast', () => ({
  useToast: (): any => ({ toast: mockToast, dismiss: jest.fn(), toasts: [] }),
  ToastProvider: ({ children }: { children: React.ReactNode }) => children,
}));

let rafQueue: Array<() => void> = [];
let trackStops: jest.Mock[] = [];
let audioCtxInstances: any[] = [];

const makeAnalyser = () => ({
  frequencyBinCount: 128,
  getByteFrequencyData: jest.fn((arr: Uint8Array) => {
    arr.fill(255); // max audio level
  }),
});

const installAudioMocks = () => {
  rafQueue = [];
  trackStops = [];
  audioCtxInstances = [];

  (global as any).requestAnimationFrame = (cb: () => void) => {
    rafQueue.push(cb);
    return rafQueue.length;
  };
  (global as any).cancelAnimationFrame = () => {
    rafQueue = [];
  };

  const getUserMedia = jest.fn().mockResolvedValue({
    getTracks: () => {
      const first = { stop: jest.fn() };
      trackStops.push(first.stop);
      return [first, { stop: jest.fn() }];
    },
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    value: { getUserMedia },
    configurable: true,
  });

  const MockAudioContext = jest.fn().mockImplementation(() => {
    const inst = {
      state: 'running',
      createMediaStreamSource: jest.fn(() => ({ connect: jest.fn() })),
      createAnalyser: jest.fn(() => makeAnalyser()),
      close: jest.fn().mockResolvedValue(undefined),
    };
    audioCtxInstances.push(inst);
    return inst;
  });
  (window as any).AudioContext = MockAudioContext;
  (window as any).webkitAudioContext = MockAudioContext;
};

const startListening = async () => {
  fireEvent.click(screen.getByRole('button', { name: /start listening/i }));
  await act(async () => {});
};

describe('WakeWordDetector', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    installAudioMocks();
    // Keep simulated detections deterministic: 0.9 > any probability
    // (audioLevel * sensitivity * 0.1 <= 0.1) so no random detections.
    jest.spyOn(Math, 'random').mockReturnValue(0.9);
  });

  it('renders the detector with default models and an inactive status', () => {
    render(<WakeWordDetector />);

    expect(screen.getByText('Wake Word Detector')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
    expect(screen.getByText('Hey Atom')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument(); // default model accuracy
    expect(screen.getByText('2')).toBeInTheDocument(); // default false positives
    expect(screen.getByText('Audio Level: 0%')).toBeInTheDocument();
    expect(
      screen.getByText('No detections yet. Start listening to detect wake words.')
    ).toBeInTheDocument();
  });

  it('shows the loading state while the microphone initializes', () => {
    (navigator.mediaDevices.getUserMedia as jest.Mock).mockReturnValue(
      new Promise(() => {})
    );
    render(<WakeWordDetector />);

    fireEvent.click(screen.getByRole('button', { name: /start listening/i }));

    expect(screen.getByText('Initializing audio...')).toBeInTheDocument();
  });

  it('toasts and stays inactive when microphone access is denied', async () => {
    (navigator.mediaDevices.getUserMedia as jest.Mock).mockRejectedValue(
      new Error('Permission denied')
    );
    render(<WakeWordDetector />);

    await startListening();

    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Microphone access denied', variant: 'error' })
    );
    expect(screen.getByText('Inactive')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start listening/i })).toBeInTheDocument();
    expect(audioCtxInstances).toHaveLength(0);
  });

  it('starts listening: shows Stop button, status Listening and toasts', async () => {
    render(<WakeWordDetector />);

    await startListening();

    expect(screen.getByRole('button', { name: /stop listening/i })).toBeInTheDocument();
    expect(screen.getByText('Listening')).toBeInTheDocument();
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith(
      expect.objectContaining({ audio: expect.objectContaining({ echoCancellation: true }) })
    );
    expect(audioCtxInstances).toHaveLength(1);
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Wake word detection started' })
    );
  });

  it('reflects a loud audio level via the visualization loop', async () => {
    render(<WakeWordDetector />);

    await startListening();

    act(() => {
      rafQueue.shift()?.();
    });

    expect(screen.getByText('Loud')).toBeInTheDocument();
    expect(screen.getByText('Audio Level: 100%')).toBeInTheDocument();
  });

  it('stops listening: cleans up tracks and the audio context, resets level', async () => {
    render(<WakeWordDetector />);

    await startListening();
    fireEvent.click(screen.getByRole('button', { name: /stop listening/i }));

    expect(screen.getByRole('button', { name: /start listening/i })).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
    expect(trackStops[0]).toHaveBeenCalled();
    expect(audioCtxInstances[0].close).toHaveBeenCalled();
    expect(screen.getByText('Audio Level: 0%')).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Wake word detection stopped' })
    );
  });

  it('unmounts without crashing and releases mic + audio context (regression)', async () => {
    const { unmount } = render(<WakeWordDetector />);

    await startListening();

    expect(() => unmount()).not.toThrow();
    expect(trackStops[0]).toHaveBeenCalled();
    expect(audioCtxInstances[0].close).toHaveBeenCalled();
    expect(rafQueue).toHaveLength(0);
  });

  it('detects the wake word from the simulated interval and records it', async () => {
    jest.useFakeTimers();
    (global as any).requestAnimationFrame = (cb: () => void) => {
      rafQueue.push(cb);
      return rafQueue.length;
    };
    (global as any).cancelAnimationFrame = () => {
      rafQueue = [];
    };
    // beforeEach already spied on Math.random (returns 0.9); override to 0.01
    (Math.random as jest.Mock).mockReturnValue(0.01);

    const onDetection = jest.fn();
    render(<WakeWordDetector onDetection={onDetection} />);

    await startListening();

    // drive one visualization frame so audioLevel becomes 1.0
    act(() => {
      rafQueue.shift()?.();
    });

    // probability = 1.0 * 0.7 * 0.1 = 0.07 > 0.01 -> detection fires
    act(() => {
      jest.advanceTimersByTime(1000);
    });

    expect(onDetection).toHaveBeenCalledTimes(1);
    expect(onDetection).toHaveBeenCalledWith(
      expect.objectContaining({ confidence: 0.505 }) // 0.01 * 0.5 + 0.5
    );
    expect(screen.getByText('Recent Detections (1)')).toBeInTheDocument();
    expect(screen.getByText('51% confidence')).toBeInTheDocument();
    expect(screen.getByText(/Duration: 510ms/)).toBeInTheDocument();
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Wake word detected!' })
    );

    // stopping ends detection: no new detections on later ticks
    fireEvent.click(screen.getByRole('button', { name: /stop listening/i }));
    act(() => {
      jest.advanceTimersByTime(3000);
    });
    expect(onDetection).toHaveBeenCalledTimes(1);

    jest.useRealTimers();
  });

  // If the fake-timer detection test fails before restoring real timers, the
  // remaining tests must not inherit fake timers (userEvent would hang).
  afterEach(() => {
    jest.useRealTimers();
  });

  it('switches models via the model select and toasts', async () => {
    const onModelChange = jest.fn();
    const user = userEvent.setup();
    render(<WakeWordDetector onModelChange={onModelChange} />);

    await user.click(screen.getByRole('combobox'));
    await user.click(
      await screen.findByRole('option', { name: 'Custom Wake Word - Custom (1.0.0)' })
    );

    expect(onModelChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'custom_wakeword', wakeWord: 'Custom' })
    );
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Model changed' })
    );
    // custom model has 0 accuracy and 0 false positives
    expect(screen.getByText('0%')).toBeInTheDocument();
  });

  it('uses provided initialModels when supplied', () => {
    const models = [
      {
        id: 'prod-1',
        name: 'Prod Model',
        description: 'Production model',
        version: '2.0.0',
        wakeWord: 'Hey Prod',
        sensitivity: 0.5,
        isActive: true,
        performance: { accuracy: 88, falsePositives: 1, detections: 3 },
        fileSize: 1.2,
        lastUpdated: new Date(),
      },
    ];
    render(<WakeWordDetector initialModels={models} />);

    expect(screen.getByText('Hey Prod')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('accepts valid model uploads and rejects invalid file types', () => {
    const onModelUpload = jest.fn();
    render(<WakeWordDetector onModelUpload={onModelUpload} />);

    const input = document.getElementById('model-upload') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [new File(['x'], 'my-model.bin')] } });

    expect(onModelUpload).toHaveBeenCalledWith(expect.any(File));
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Model uploaded' })
    );

    fireEvent.change(input, { target: { files: [new File(['x'], 'notes.txt')] } });
    expect(onModelUpload).toHaveBeenCalledTimes(1); // still only the valid one
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Invalid file type', variant: 'error' })
    );
  });

  it('starts a model download for models that have a file', () => {
    const onModelDownload = jest.fn();
    render(<WakeWordDetector onModelDownload={onModelDownload} />);

    fireEvent.click(screen.getByRole('button', { name: /download model/i }));

    expect(onModelDownload).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'default_wakeword' })
    );
    expect(mockToast).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Model download started' })
    );
  });

  it('adjusts sensitivity from settings and notifies onModelChange', async () => {
    const onModelChange = jest.fn();
    render(<WakeWordDetector onModelChange={onModelChange} />);

    fireEvent.click(screen.getAllByRole('button')[0]); // settings gear

    expect(await screen.findByText('Wake Word Settings')).toBeInTheDocument();
    expect(screen.getByText('70%')).toBeInTheDocument();

    fireEvent.change(screen.getByRole('slider'), { target: { value: '0.9' } });

    expect(screen.getByText('90%')).toBeInTheDocument();
    expect(onModelChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: 'default_wakeword', sensitivity: 0.9 })
    );

    fireEvent.click(screen.getByRole('button', { name: /close/i }));
    await waitFor(() => {
      expect(screen.queryByText('Wake Word Settings')).not.toBeInTheDocument();
    });
  });

  it('renders in compact view with the compact padding class', () => {
    const { container } = render(<WakeWordDetector compactView />);

    expect(container.querySelector('.space-y-6.p-2')).not.toBeNull();
    expect(container.querySelector('.space-y-6.p-6')).toBeNull();
  });

  it('hides the navigation header and controls when showNavigation is false', () => {
    render(<WakeWordDetector showNavigation={false} />);

    expect(screen.queryByText('Wake Word Detector')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /start listening/i })).not.toBeInTheDocument();
  });
});
