/**
 * VoiceModeOverlay Component Tests
 *
 * Tests verify the real VoiceModeOverlay
 * (components/Voice/VoiceModeOverlay.tsx) with a fully mocked Web Speech API:
 * - renders nothing while closed
 * - opens the overlay and starts recognition ("I'm listening...")
 * - unsupported browsers alert instead of crashing
 * - interim results render live transcript
 * - final results send the transcript and switch to "Thinking..."
 * - mic button toggles listening on/off
 * - close button stops recognition + speech and fires onClose
 * - agent messages are spoken with markdown stripped and preferred voice;
 *   utterance onstart/onend drive the "Atom Speaking..." -> idle transition
 * - no speech while isProcessing, and no repeat of the same message
 *
 * Web Speech API mocks: webkitSpeechRecognition, SpeechSynthesisUtterance,
 * window.speechSynthesis (see beforeEach).
 */
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import { VoiceModeOverlay } from '../VoiceModeOverlay';

// Classic-JSX compatibility: source module has no default React import.
(global as any).React = React;

interface MockRecognition {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: null | ((e?: any) => void);
  onresult: null | ((e?: any) => void);
  onerror: null | ((e?: any) => void);
  onend: null | ((e?: any) => void);
  start: jest.Mock;
  stop: jest.Mock;
}

let recognitionInstances: MockRecognition[] = [];
let utteranceInstances: any[] = [];

const installSpeechMocks = () => {
  recognitionInstances = [];
  utteranceInstances = [];

  const SpeechRecognition = jest.fn().mockImplementation(() => {
    const inst: MockRecognition = {
      continuous: false,
      interimResults: false,
      lang: '',
      onstart: null,
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

  const SpeechSynthesisUtteranceMock = jest.fn().mockImplementation((text: string) => {
    const u: any = { text, voice: null, rate: 1, onstart: null, onend: null, onerror: null };
    utteranceInstances.push(u);
    return u;
  });
  (global as any).SpeechSynthesisUtterance = SpeechSynthesisUtteranceMock;

  const speechSynthesis = {
    cancel: jest.fn(),
    speak: jest.fn(),
    getVoices: jest.fn(() => [
      { name: 'Google US English' },
      { name: 'Other Voice' },
    ]),
  };
  Object.defineProperty(window, 'speechSynthesis', {
    value: speechSynthesis,
    configurable: true,
  });

  HTMLCanvasElement.prototype.getContext = jest.fn(
    () => ({ clearRect: jest.fn(), fill: jest.fn(), beginPath: jest.fn(), roundRect: jest.fn() })
  ) as any;

  return speechSynthesis;
};

const defaultProps = {
  isOpen: true,
  onClose: jest.fn(),
  onSend: jest.fn().mockResolvedValue(undefined),
  isProcessing: false,
  lastAgentMessage: null as string | null,
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

describe('VoiceModeOverlay', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    installSpeechMocks();
  });

  it('renders nothing when closed', () => {
    const { container } = render(<VoiceModeOverlay {...defaultProps} isOpen={false} />);
    expect(container.innerHTML).toBe('');
  });

  it('opens the overlay and starts recognition when open', () => {
    render(<VoiceModeOverlay {...defaultProps} />);

    const inst = getRecognition();
    expect(inst.start).toHaveBeenCalled();
    expect(inst.continuous).toBe(false);
    expect(inst.interimResults).toBe(true);
    expect(inst.lang).toBe('en-US');

    // initial mode is idle
    expect(screen.getByText('Tap to speak')).toBeInTheDocument();
    expect(screen.getByText('ATOM VOICE v1.0 • WEB SPEECH API')).toBeInTheDocument();

    // onstart switches to listening mode
    act(() => {
      inst.onstart?.();
    });
    expect(screen.getByText("I'm listening...")).toBeInTheDocument();
  });

  it('alerts and does not start recognition when the API is unsupported', () => {
    const alertSpy = jest.spyOn(window, 'alert').mockImplementation(() => {});
    delete (window as any).webkitSpeechRecognition;

    render(<VoiceModeOverlay {...defaultProps} />);

    expect(alertSpy).toHaveBeenCalledWith(
      'Voice not supported in this browser. Try Chrome/Edge.'
    );
    expect(recognitionInstances).toHaveLength(0);
    expect(screen.getByText('Tap to speak')).toBeInTheDocument();
  });

  it('renders the live interim transcript', () => {
    render(<VoiceModeOverlay {...defaultProps} />);
    const inst = getRecognition();

    fireResult(inst, { isFinal: false, 0: { transcript: 'hello there' } });

    expect(screen.getByText('"hello there"')).toBeInTheDocument();
  });

  it('sends the final transcript, stops recognition and switches to Thinking', async () => {
    const onSend = jest.fn().mockResolvedValue(undefined);
    render(<VoiceModeOverlay {...defaultProps} onSend={onSend} />);
    const inst = getRecognition();

    fireResult(inst, { isFinal: true, 0: { transcript: 'send an email' } });

    expect(onSend).toHaveBeenCalledWith('send an email');
    expect(inst.stop).toHaveBeenCalled();
    expect(screen.getByText('Thinking...')).toBeInTheDocument();
  });

  it('prefers final over interim when both are present in one event', async () => {
    const onSend = jest.fn().mockResolvedValue(undefined);
    render(<VoiceModeOverlay {...defaultProps} onSend={onSend} />);
    const inst = getRecognition();

    fireResult(inst, { isFinal: false, 0: { transcript: 'draft' } });
    expect(screen.getByText('"draft"')).toBeInTheDocument();

    fireResult(inst, { isFinal: true, 0: { transcript: 'draft a report' } });

    expect(onSend).toHaveBeenCalledWith('draft a report');
  });

  it('toggles listening off and on via the mic button', () => {
    render(<VoiceModeOverlay {...defaultProps} />);
    const first = getRecognition();
    act(() => {
      first.onstart?.();
    });

    const micButton = screen.getAllByRole('button')[1];
    fireEvent.click(micButton);
    expect(first.stop).toHaveBeenCalled();
    expect(screen.getByText('Tap to speak')).toBeInTheDocument();

    // click again -> a new recognition session starts
    fireEvent.click(micButton);
    expect(recognitionInstances).toHaveLength(2);
    expect(recognitionInstances[1].start).toHaveBeenCalled();
  });

  it('closes: stops recognition and speech, and fires onClose', () => {
    const onClose = jest.fn();
    const synthesis = installSpeechMocks();
    render(<VoiceModeOverlay {...defaultProps} onClose={onClose} />);
    const inst = getRecognition();

    fireEvent.click(screen.getAllByRole('button')[0]); // X close button

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(inst.stop).toHaveBeenCalled();
    expect(synthesis.cancel).toHaveBeenCalled();
  });

  it('speaks the agent message with markdown stripped and the preferred voice', () => {
    render(<VoiceModeOverlay {...defaultProps} lastAgentMessage="**Hello** `world`" />);

    expect(utteranceInstances).toHaveLength(1);
    const utterance = utteranceInstances[0];
    expect(utterance.text).toBe('Hello world');
    expect(utterance.voice).toEqual({ name: 'Google US English' });
    expect(utterance.rate).toBe(1.1);
    expect((window.speechSynthesis.speak as jest.Mock)).toHaveBeenCalledWith(utterance);
  });

  it('drives the mode through speaking -> idle via utterance events', () => {
    render(<VoiceModeOverlay {...defaultProps} lastAgentMessage="Here is your summary" />);
    const utterance = utteranceInstances[0];

    act(() => {
      utterance.onstart?.();
    });
    expect(screen.getByText('Atom Speaking...')).toBeInTheDocument();
    // transcript area shows the (truncated) spoken message
    expect(screen.getByText('"Here is your summary..."')).toBeInTheDocument();

    act(() => {
      utterance.onend?.();
    });
    expect(screen.getByText('Tap to speak')).toBeInTheDocument();
  });

  it('does not speak while the agent is still processing', () => {
    render(
      <VoiceModeOverlay {...defaultProps} isProcessing lastAgentMessage="Wait for it" />
    );

    expect(utteranceInstances).toHaveLength(0);
  });

  it('does not repeat an already-spoken message', () => {
    const { rerender } = render(
      <VoiceModeOverlay {...defaultProps} lastAgentMessage="First message" />
    );
    expect(utteranceInstances).toHaveLength(1);

    rerender(<VoiceModeOverlay {...defaultProps} lastAgentMessage="First message" />);
    expect(utteranceInstances).toHaveLength(1);

    rerender(<VoiceModeOverlay {...defaultProps} lastAgentMessage="Second message" />);
    expect(utteranceInstances).toHaveLength(2);
    expect(utteranceInstances[1].text).toBe('Second message');
  });

  it('falls back to the first available voice when Google US English is missing', () => {
    (window.speechSynthesis.getVoices as jest.Mock).mockReturnValue([{ name: 'Other Voice' }]);

    render(<VoiceModeOverlay {...defaultProps} lastAgentMessage="hi" />);

    expect(utteranceInstances[0].voice).toEqual({ name: 'Other Voice' });
  });

  it('stops recognition and speech on unmount', () => {
    const { unmount } = render(<VoiceModeOverlay {...defaultProps} />);
    const inst = getRecognition();

    unmount();

    expect(inst.stop).toHaveBeenCalled();
    expect((window.speechSynthesis.cancel as jest.Mock)).toHaveBeenCalled();
  });
});
