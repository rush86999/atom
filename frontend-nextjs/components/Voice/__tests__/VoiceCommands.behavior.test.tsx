import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import VoiceCommands from '../VoiceCommands';

const mockStart = jest.fn();
const mockStop = jest.fn();
let currentMockInstance: any = null;

class MockSpeechRecognition {
  continuous = false;
  interimResults = false;
  lang = 'en-US';
  onstart: any = null;
  onend: any = null;
  onresult: any = null;
  onerror: any = null;

  constructor() {
    currentMockInstance = this;
  }

  start() {
    mockStart();
    if (this.onstart) this.onstart();
  }

  stop() {
    mockStop();
    if (this.onend) this.onend();
  }

  abort() {}
}

Object.defineProperty(window, 'SpeechRecognition', {
  writable: true,
  value: MockSpeechRecognition,
});

Object.defineProperty(window, 'webkitSpeechRecognition', {
  writable: true,
  value: MockSpeechRecognition,
});

const mockCommand = {
  id: 'test-command',
  phrase: 'open calendar',
  action: 'navigate',
  description: 'Open the calendar view',
  enabled: true,
  confidenceThreshold: 0.7,
  parameters: { route: '/calendar' },
  usageCount: 5,
  lastUsed: new Date('2024-01-01'),
};

// The handler reads `event.results[i].isFinal` (on the result LIST), not the
// per-alternative object.
const fireFinalResult = (transcript: string, confidence: number) => {
  act(() => {
    currentMockInstance.onresult({
      resultIndex: 0,
      results: [{ isFinal: true, 0: { transcript, confidence } }],
    });
  });
};

describe('VoiceCommands behavior', () => {
  const onCommandExecute = jest.fn();
  const onCommandUpdate = jest.fn();
  const onCommandCreate = jest.fn();
  const onCommandDelete = jest.fn();
  const onCommandRecognized = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    currentMockInstance = null;
    mockStart.mockClear();
    mockStop.mockClear();
    window.SpeechRecognition = MockSpeechRecognition;
    window.webkitSpeechRecognition = MockSpeechRecognition;
  });

  const renderWith = (props: any = {}) =>
    render(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
        onCommandExecute={onCommandExecute}
        onCommandUpdate={onCommandUpdate}
        onCommandCreate={onCommandCreate}
        onCommandDelete={onCommandDelete}
        onCommandRecognized={onCommandRecognized}
        {...props}
      />
    );

  const waitForRecognition = async () => {
    await waitFor(() => expect(currentMockInstance).not.toBeNull());
  };

  it('fires onstart toast and shows Listening state, then onend restores Inactive', async () => {
    const toastModule = require('@/components/ui/use-toast');
    const toastFn = toastModule.useToast().toast;

    renderWith();
    await waitForRecognition();

    await act(async () => {
      fireEvent.click(screen.getByText('Start Listening'));
    });

    expect(mockStart).toHaveBeenCalled();
    expect(screen.getByText('Listening')).toBeInTheDocument();
    expect(screen.getByText('Stop Listening')).toBeInTheDocument();
    expect(toastFn).toHaveBeenCalledWith(expect.objectContaining({ title: 'Voice recognition started' }));

    await act(async () => {
      fireEvent.click(screen.getByText('Stop Listening'));
    });

    expect(mockStop).toHaveBeenCalled();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
    expect(screen.getByText('Start Listening')).toBeInTheDocument();
  });

  it('executes a recognized command, bumps usage and notifies callbacks', async () => {
    renderWith();
    await waitForRecognition();

    fireFinalResult('open calendar', 0.85);

    expect(onCommandExecute).toHaveBeenCalledWith(mockCommand, { route: '/calendar' });
    expect(onCommandRecognized).toHaveBeenCalledWith(
      expect.objectContaining({ transcript: 'open calendar', processed: true, command: mockCommand })
    );
    expect(onCommandUpdate).toHaveBeenCalledWith(
      'test-command',
      expect.objectContaining({ usageCount: 6, lastUsed: expect.any(Date) })
    );
    // Usage count re-rendered
    expect(screen.getByText('6 uses')).toBeInTheDocument();
    // Result recorded
    expect(screen.getByText('View Results (1)')).toBeInTheDocument();
  });

  it('rejects negated commands (BUG-107)', async () => {
    renderWith();
    await waitForRecognition();

    fireFinalResult("don't open calendar", 0.95);

    expect(onCommandExecute).not.toHaveBeenCalled();
    expect(onCommandUpdate).not.toHaveBeenCalled();
    expect(onCommandRecognized).toHaveBeenCalledWith(
      expect.objectContaining({ transcript: "don't open calendar", processed: false })
    );
  });

  it('rejects commands below the confidence threshold', async () => {
    renderWith();
    await waitForRecognition();

    fireFinalResult('open calendar', 0.5);

    expect(onCommandExecute).not.toHaveBeenCalled();
  });

  it('does not match disabled commands', async () => {
    const disabled = { ...mockCommand, phrase: 'send email', enabled: false };
    renderWith({ initialCommands: [disabled] });
    await waitForRecognition();

    fireFinalResult('send email', 0.99);

    expect(onCommandExecute).not.toHaveBeenCalled();
  });

  it('shows interim transcripts in the Current Input alert', async () => {
    renderWith();
    await waitForRecognition();

    act(() => {
      currentMockInstance.onresult({
        resultIndex: 0,
        results: [{ isFinal: false, 0: { transcript: 'open cal', confidence: 0.3 } }],
      });
    });

    expect(screen.getByText('Current Input')).toBeInTheDocument();
    expect(screen.getByText('open cal')).toBeInTheDocument();
    // Interim confidence is not propagated (only final results report it)
    expect(screen.getByText('Confidence: 0%')).toBeInTheDocument();
  });

  it('shows a no-match toast for unrecognized phrases', async () => {
    const toastModule = require('@/components/ui/use-toast');
    const toastFn = toastModule.useToast().toast;

    renderWith();
    await waitForRecognition();

    fireFinalResult('play music', 0.9);

    expect(onCommandExecute).not.toHaveBeenCalled();
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'No matching command found' })
    );
  });

  it('reports speech recognition errors via toast and resets listening', async () => {
    const toastModule = require('@/components/ui/use-toast');
    const toastFn = toastModule.useToast().toast;

    renderWith();
    await waitForRecognition();

    act(() => {
      currentMockInstance.onerror({ error: 'audio-capture' });
    });

    expect(toastFn).toHaveBeenCalledWith(expect.objectContaining({ title: 'Speech recognition error' }));
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('shows a warning toast when speech recognition is unsupported', async () => {
    const toastModule = require('@/components/ui/use-toast');
    const toastFn = toastModule.useToast().toast;

    window.SpeechRecognition = undefined as any;
    window.webkitSpeechRecognition = undefined as any;

    renderWith();

    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Speech recognition not supported' })
    );
  });

  it('stops recognition on unmount', async () => {
    const { unmount } = renderWith();
    await waitForRecognition();

    unmount();
    expect(mockStop).toHaveBeenCalled();
  });

  it('handles start() throwing via an error toast', async () => {
    const toastModule = require('@/components/ui/use-toast');
    const toastFn = toastModule.useToast().toast;
    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    renderWith();
    await waitForRecognition();

    currentMockInstance.start = () => {
      throw new Error('permission denied');
    };

    await act(async () => {
      fireEvent.click(screen.getByText('Start Listening'));
    });

    expect(toastFn).toHaveBeenCalledWith(expect.objectContaining({ title: 'Error starting voice recognition' }));
    consoleSpy.mockRestore();
  });

  it('creates a command through the Manage Commands dialog', async () => {
    renderWith();
    await waitForRecognition();

    fireEvent.click(screen.getByText('Manage Commands'));
    expect(screen.getByText('Create Command', { selector: 'h2' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Voice Phrase'), { target: { value: 'open settings' } });
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Opens settings' } });

    fireEvent.click(screen.getByText('Create Command', { selector: 'button' }));

    expect(onCommandCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        phrase: 'open settings',
        description: 'Opens settings',
        usageCount: 0,
        id: expect.any(String),
      })
    );
    // New command appears in the list
    expect(screen.getByText('"open settings"')).toBeInTheDocument();
    expect(screen.getByText('Available Commands (2)')).toBeInTheDocument();
  });

  it('rejects invalid parameters JSON with an error toast', async () => {
    const toastModule = require('@/components/ui/use-toast');
    const toastFn = toastModule.useToast().toast;

    renderWith();
    await waitForRecognition();

    fireEvent.click(screen.getByText('Manage Commands'));
    fireEvent.change(screen.getByLabelText('Voice Phrase'), { target: { value: 'x' } });
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'y' } });
    fireEvent.change(screen.getByLabelText('Parameters (JSON)'), { target: { value: '{bad json' } });

    fireEvent.click(screen.getByText('Create Command', { selector: 'button' }));

    expect(onCommandCreate).not.toHaveBeenCalled();
    expect(toastFn).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Invalid parameters' })
    );
  });

  it('edits an existing command from its card', async () => {
    renderWith();
    await waitForRecognition();

    const settingsButtons = screen.getAllByRole('button').filter(b => b.querySelector('.lucide-settings'));
    // [0] = header "Manage Commands", [1] = the command card's edit button
    fireEvent.click(settingsButtons[1]);
    expect(screen.getByText('Edit Command', { selector: 'h2' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Voice Phrase'), { target: { value: 'open agenda' } });
    fireEvent.click(screen.getByText('Update Command', { selector: 'button' }));

    expect(onCommandUpdate).toHaveBeenCalledWith('test-command', expect.objectContaining({ phrase: 'open agenda' }));
    expect(screen.getByText('"open agenda"')).toBeInTheDocument();
  });

  it('deletes a command from its card', async () => {
    renderWith();
    await waitForRecognition();

    fireEvent.click(
      screen.getAllByRole('button').find(b => b.querySelector('.lucide-trash-2'))!
    );

    expect(onCommandDelete).toHaveBeenCalledWith('test-command');
    expect(screen.getByText('Available Commands (0)')).toBeInTheDocument();
    expect(screen.queryByText('"open calendar"')).not.toBeInTheDocument();
  });

  it('toggles a command enabled/disabled from its card', async () => {
    renderWith();
    await waitForRecognition();

    fireEvent.click(
      screen.getAllByRole('button').find(b => b.querySelector('.lucide-circle-check'))!
    );

    expect(onCommandUpdate).toHaveBeenCalledWith('test-command', { enabled: false });
    expect(screen.getByText('Available Commands (0)')).toBeInTheDocument();
  });

  it('shows recognition results in the results dialog', async () => {
    renderWith();
    await waitForRecognition();

    fireFinalResult('open calendar', 0.85);
    fireEvent.click(screen.getByText('View Results (1)'));

    expect(screen.getByText('Recognition Results')).toBeInTheDocument();
    // Card + dialog both render the quoted transcript
    expect(screen.getAllByText('"open calendar"').length).toBe(2);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('shows an empty state in the results dialog', async () => {
    renderWith();
    await waitForRecognition();

    fireEvent.click(screen.getByText('View Results (0)'));
    expect(screen.getByText('No results yet.')).toBeInTheDocument();
  });
});

describe('VoiceCommands command form fields', () => {
  const onCommandCreate = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    currentMockInstance = null;
  });

  it('captures action, confidence threshold and enabled switch on create', async () => {
    render(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
        onCommandCreate={onCommandCreate}
      />
    );
    await waitFor(() => expect(currentMockInstance).not.toBeNull());

    fireEvent.click(screen.getByText('Manage Commands'));

    fireEvent.change(screen.getByLabelText('Voice Phrase'), { target: { value: 'ship report' } });
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Sends the report' } });

    // Action select (Radix): open then pick "Send Email"
    const trigger = screen.getByRole('combobox');
    fireEvent.pointerDown(trigger);
    fireEvent.click(trigger);
    fireEvent.click(await screen.findByRole('option', { name: 'Send Email' }));

    // Confidence threshold
    fireEvent.change(screen.getByLabelText('Confidence Threshold'), { target: { value: '0.9' } });

    // Enabled switch: toggle OFF
    const toggle = screen.getByRole('switch');
    expect(toggle).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'false');

    fireEvent.click(screen.getByText('Create Command', { selector: 'button' }));

    expect(onCommandCreate).toHaveBeenCalledWith(
      expect.objectContaining({
        phrase: 'ship report',
        action: 'send_email',
        description: 'Sends the report',
        confidenceThreshold: 0.9,
        enabled: false,
      })
    );
    // Disabled commands do not appear in the active list
    expect(screen.getByText('Available Commands (1)')).toBeInTheDocument();
  });
});

describe('VoiceCommands dialog cancel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    currentMockInstance = null;
  });

  it('closes the create dialog without creating a command on Cancel', async () => {
    const onCommandCreate = jest.fn();
    render(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
        onCommandCreate={onCommandCreate}
      />
    );
    await waitFor(() => expect(currentMockInstance).not.toBeNull());

    fireEvent.click(screen.getByText('Manage Commands'));
    expect(screen.getByText('Create Command', { selector: 'h2' })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Voice Phrase'), { target: { value: 'cancel me' } });
    fireEvent.click(screen.getByText('Cancel', { selector: 'button' }));

    expect(onCommandCreate).not.toHaveBeenCalled();
    expect(screen.queryByText('Create Command', { selector: 'h2' })).not.toBeInTheDocument();
    expect(screen.queryByText('"cancel me"')).not.toBeInTheDocument();
  });
});
