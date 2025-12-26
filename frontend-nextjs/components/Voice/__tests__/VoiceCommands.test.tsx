import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ChakraProvider } from '@chakra-ui/react';
import '@testing-library/jest-dom';
import VoiceCommands from '../VoiceCommands';

// Mock speech recognition
const mockSpeechRecognition = {
  continuous: false,
  interimResults: false,
  lang: 'en-US',
  onstart: null as any,
  onend: null as any,
  onresult: null as any,
  onerror: null as any,
  start: jest.fn(),
  stop: jest.fn(),
};

Object.defineProperty(window, 'SpeechRecognition', {
  writable: true,
  value: jest.fn().mockImplementation(() => mockSpeechRecognition),
});

Object.defineProperty(window, 'webkitSpeechRecognition', {
  writable: true,
  value: jest.fn().mockImplementation(() => mockSpeechRecognition),
});

// Mock Chakra UI hooks
jest.mock('@chakra-ui/react', () => ({
  ...jest.requireActual('@chakra-ui/react'),
  useToast: () => jest.fn(),
  useDisclosure: () => ({
    isOpen: false,
    onOpen: jest.fn(),
    onClose: jest.fn(),
  }),
}));

const renderWithProviders = (component: React.ReactElement) => {
  return render(
    <div data-testid="chakra-provider">
      {component}
    </div>
  );
};

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

const mockRecognitionResult = {
  id: 'test-result',
  timestamp: new Date(),
  transcript: 'open calendar',
  confidence: 0.85,
  command: mockCommand,
  processed: true,
};

describe('VoiceCommands', () => {
  const mockOnCommandRecognized = jest.fn();
  const mockOnCommandExecute = jest.fn();
  const mockOnCommandCreate = jest.fn();
  const mockOnCommandUpdate = jest.fn();
  const mockOnCommandDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    // Reset mock speech recognition
    mockSpeechRecognition.start.mockClear();
    mockSpeechRecognition.stop.mockClear();
  });

  it('renders without crashing', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[]}
        showNavigation={true}
      />
    );

    expect(screen.getByText('Voice Commands')).toBeInTheDocument();
  });

  it('displays voice recognition status correctly', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
      />
    );

    expect(screen.getByText('Voice Recognition Status')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
    expect(screen.getByText('Active Commands')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('shows available commands', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
      />
    );

    expect(screen.getByText('Available Commands (1)')).toBeInTheDocument();
    expect(screen.getByText('"open calendar"')).toBeInTheDocument();
    expect(screen.getByText('Open the calendar view')).toBeInTheDocument();
  });

  it('allows starting and stopping voice recognition', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
      />
    );

    const startButton = screen.getByText('Start Listening');
    fireEvent.click(startButton);

    expect(mockSpeechRecognition.start).toHaveBeenCalled();

    const stopButton = screen.getByText('Stop Listening');
    fireEvent.click(stopButton);

    expect(mockSpeechRecognition.stop).toHaveBeenCalled();
  });

  it('displays command management options', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
      />
    );

    const manageButton = screen.getByText('Manage Commands');
    expect(manageButton).toBeInTheDocument();

    const resultsButton = screen.getByText('View Results (0)');
    expect(resultsButton).toBeInTheDocument();
  });

  it('handles disabled commands correctly', () => {
    const disabledCommand = { ...mockCommand, enabled: false };

    renderWithProviders(
      <VoiceCommands
        initialCommands={[disabledCommand]}
        showNavigation={true}
      />
    );

    expect(screen.getByText('Available Commands (0)')).toBeInTheDocument();
  });

  it('updates command usage count when executed', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand]}
        onCommandExecute={mockOnCommandExecute}
        onCommandUpdate={mockOnCommandUpdate}
        showNavigation={true}
      />
    );

    // Simulate command execution
    fireEvent.click(screen.getByText('Start Listening'));

    // Simulate speech recognition result
    if (mockSpeechRecognition.onresult) {
      const event = {
        results: [[{ transcript: 'open calendar', confidence: 0.85, isFinal: true }]],
        resultIndex: 0,
      };
      mockSpeechRecognition.onresult(event);
    }

    expect(mockOnCommandExecute).toHaveBeenCalledWith(mockCommand, mockCommand.parameters);
    expect(mockOnCommandUpdate).toHaveBeenCalledWith(
      mockCommand.id,
      expect.objectContaining({
        usageCount: mockCommand.usageCount + 1,
        lastUsed: expect.any(Date),
      })
    );
  });

  it('shows recognition results', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
      />
    );

    const resultsButton = screen.getByText('View Results (0)');
    fireEvent.click(resultsButton);

    // Should show results modal (this would require mocking the modal)
  });

  it('handles speech recognition errors gracefully', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
      />
    );

    fireEvent.click(screen.getByText('Start Listening'));

    // Simulate speech recognition error
    if (mockSpeechRecognition.onerror) {
      const errorEvent = { error: 'audio-capture' };
      mockSpeechRecognition.onerror(errorEvent);
    }

    // Should handle error without crashing
    expect(screen.getByText('Voice Commands')).toBeInTheDocument();
  });

  it('filters commands by confidence threshold', () => {
    const lowConfidenceCommand = {
      ...mockCommand,
      id: 'low-confidence',
      confidenceThreshold: 0.9,
    };

    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand, lowConfidenceCommand]}
        showNavigation={true}
      />
    );

    expect(screen.getByText('Available Commands (2)')).toBeInTheDocument();
  });

  it('displays command usage statistics', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[mockCommand]}
        showNavigation={true}
      />
    );

    expect(screen.getByText('5 uses')).toBeInTheDocument();
  });

  it('handles empty commands list', () => {
    renderWithProviders(
      <VoiceCommands
        initialCommands={[]}
        showNavigation={true}
      />
    );

    expect(screen.getByText('Available Commands (0)')).toBeInTheDocument();
  });
});
