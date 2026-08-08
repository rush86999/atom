/**
 * VoiceInput Component Tests (root components/VoiceInput.tsx)
 *
 * Tests verify the real, Web Speech API-based VoiceInput:
 * - shows an error when speech recognition is unsupported
 * - mic button toggles recognition start/stop with listening indicator
 * - interim + final results render the transcript; final results call
 *   onTranscript
 * - recognition errors surface the error text and stop listening
 * - recognition ending stops listening
 * - "Send to Atom" submits the transcript to /api/v1/voice/command and
 *   forwards the response to onCommand
 * - error responses (non-ok) and network failures do NOT forward to
 *   onCommand (regression: !response.ok was never checked)
 * - unmount stops recognition
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import VoiceInput from '../VoiceInput';

interface MockRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: null | ((e?: any) => void);
  onerror: null | ((e?: any) => void);
  onend: null | ((e?: any) => void);
  start: jest.Mock;
  stop: jest.Mock;
}

let recognitionInstances: MockRecognition[] = [];

const installSpeechRecognition = () => {
  recognitionInstances = [];
  const SpeechRecognition = jest.fn().mockImplementation(() => {
    const inst: MockRecognition = {
      continuous: false,
      interimResults: false,
      lang: '',
      onresult: null,
      onerror: null,
      onend: null,
      start: jest.fn(),
      stop: jest.fn(),
    };
    recognitionInstances.push(inst);
    return inst;
  });
  (window as any).webkitSpeechRecognition = SpeechRecognition;
  (window as any).SpeechRecognition = SpeechRecognition;
};

const getRecognition = () => {
  expect(recognitionInstances.length).toBeGreaterThan(0);
  return recognitionInstances[recognitionInstances.length - 1];
};

const fireResult = (inst: MockRecognition, result: any) => {
  act(() => {
    inst.onresult?.({ resultIndex: 0, results: [result] });
  });
};

const fireHandler = (inst: MockRecognition, handler: 'onerror' | 'onend', arg?: any) => {
  act(() => {
    inst[handler]?.(arg);
  });
};

describe('VoiceInput', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    installSpeechRecognition();
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, result: 'email drafted' }),
    });
  });

  it('shows a support error when speech recognition is unavailable', async () => {
    delete (window as any).webkitSpeechRecognition;
    delete (window as any).SpeechRecognition;

    render(<VoiceInput onTranscript={() => {}} />);

    expect(
      await screen.findByText('Voice input is not supported in this browser')
    ).toBeInTheDocument();
    expect(recognitionInstances).toHaveLength(0);
  });

  it('starts recognition and shows the listening indicator on mic click', () => {
    render(<VoiceInput onTranscript={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));

    const inst = getRecognition();
    expect(inst.start).toHaveBeenCalled();
    expect(inst.lang).toBe('en-US');
    expect(inst.interimResults).toBe(true);
    expect(screen.getByText('Listening...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stop listening/i })).toBeInTheDocument();
  });

  it('stops recognition on a second mic click', () => {
    render(<VoiceInput onTranscript={() => {}} />);

    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));
    const inst = getRecognition();
    fireEvent.click(screen.getByRole('button', { name: /stop listening/i }));

    expect(inst.stop).toHaveBeenCalled();
    expect(screen.queryByText('Listening...')).not.toBeInTheDocument();
  });

  it('renders interim results and exposes Send to Atom', () => {
    render(<VoiceInput onTranscript={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));

    fireResult(getRecognition(), { isFinal: false, 0: { transcript: 'draft an email' } });

    expect(screen.getByText('draft an email')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send to atom/i })).toBeInTheDocument();
  });

  it('calls onTranscript for final results only', () => {
    const onTranscript = jest.fn();
    render(<VoiceInput onTranscript={onTranscript} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));
    const inst = getRecognition();

    fireResult(inst, { isFinal: false, 0: { transcript: 'partial' } });
    expect(onTranscript).not.toHaveBeenCalled();

    fireResult(inst, { isFinal: true, 0: { transcript: 'final words' } });
    expect(onTranscript).toHaveBeenCalledWith('final words');
  });

  it('shows recognition errors and stops listening', () => {
    render(<VoiceInput onTranscript={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));
    const inst = getRecognition();

    fireHandler(inst, 'onerror', { error: 'not-allowed' });

    expect(screen.getByText('Voice error: not-allowed')).toBeInTheDocument();
    expect(screen.queryByText('Listening...')).not.toBeInTheDocument();
  });

  it('stops listening when recognition ends', () => {
    render(<VoiceInput onTranscript={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));
    const inst = getRecognition();

    fireHandler(inst, 'onend');

    expect(screen.queryByText('Listening...')).not.toBeInTheDocument();
  });

  it('submits the transcript to /api/v1/voice/command and forwards the result', async () => {
    const onCommand = jest.fn();
    const onTranscript = jest.fn();
    render(<VoiceInput onTranscript={onTranscript} onCommand={onCommand} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));

    fireResult(getRecognition(), { isFinal: true, 0: { transcript: 'schedule a meeting' } });
    fireEvent.click(screen.getByRole('button', { name: /send to atom/i }));

    await waitFor(() => {
      expect(onCommand).toHaveBeenCalledWith({ success: true, result: 'email drafted' });
    });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/voice/command',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: 'schedule a meeting', language: 'en' }),
      })
    );
  });

  it('does not forward non-ok command responses to onCommand (regression)', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ error: 'boom' }),
    });
    const onCommand = jest.fn();
    render(<VoiceInput onTranscript={() => {}} onCommand={onCommand} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));

    fireResult(getRecognition(), { isFinal: true, 0: { transcript: 'do a thing' } });
    fireEvent.click(screen.getByRole('button', { name: /send to atom/i }));

    await screen.findByText('Failed to process voice command');
    expect(onCommand).not.toHaveBeenCalled();
  });

  it('shows an error when the command fetch rejects', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('network down'));
    render(<VoiceInput onTranscript={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));

    fireResult(getRecognition(), { isFinal: true, 0: { transcript: 'do a thing' } });
    fireEvent.click(screen.getByRole('button', { name: /send to atom/i }));

    expect(await screen.findByText('Failed to process voice command')).toBeInTheDocument();
  });

  it('does not submit an empty transcript', () => {
    render(<VoiceInput onTranscript={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));

    expect(screen.queryByRole('button', { name: /send to atom/i })).not.toBeInTheDocument();
  });

  it('stops recognition on unmount', () => {
    const { unmount } = render(<VoiceInput onTranscript={() => {}} />);
    fireEvent.click(screen.getByRole('button', { name: /start voice input/i }));
    const inst = getRecognition();

    unmount();

    expect(inst.stop).toHaveBeenCalled();
  });

  it('applies the custom className', () => {
    const { container } = render(
      <VoiceInput onTranscript={() => {}} className="my-voice-input" />
    );

    expect(container.querySelector('.my-voice-input')).toBeInTheDocument();
  });
});
