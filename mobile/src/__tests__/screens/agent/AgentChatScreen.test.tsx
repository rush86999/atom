/**
 * AgentChatScreen Component Tests
 *
 * Tests for chat interface, message sending (streaming + fallback),
 * session loading, episode context, governance badges, and error paths.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Alert, StyleSheet } from 'react-native';
import { mockPlatform, restorePlatform } from '../../helpers/testUtils';

// Mock React Navigation (params are mutable so per-test agent/session ids work)
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  setOptions: jest.fn(),
  reset: jest.fn(),
};

const mockRouteParams: any = {
  agentId: 'agent-123',
  sessionId: undefined,
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
  useRoute: () => ({
    params: mockRouteParams,
  }),
}));

// Mock agentService
const mockGetAgent = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: {
      id: 'agent-123',
      name: 'Test Agent',
      description: 'A test agent for automation',
      maturity_level: 'AUTONOMOUS',
      status: 'online',
      confidence_score: 0.95,
      created_at: '2024-01-01T00:00:00Z',
    },
  })
);

const mockGetAvailableAgents = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: [
      {
        id: 'agent-123',
        name: 'Test Agent',
        maturity_level: 'AUTONOMOUS',
        status: 'online',
      },
    ],
  })
);

const mockSendMessage = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: {
      message: {
        id: 'msg-1',
        role: 'assistant',
        content: 'Hello! How can I help you?',
        timestamp: '2024-01-01T00:00:00Z',
      },
      session_id: 'session-123',
    },
  })
);

const mockGetChatSession = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: {
      messages: [
        {
          id: 'msg-0',
          role: 'user',
          content: 'Hello',
          timestamp: '2024-01-01T00:00:00Z',
        },
        {
          id: 'msg-1',
          role: 'assistant',
          content: 'Hi there!',
          agent_name: 'Test Agent',
          timestamp: '2024-01-01T00:00:01Z',
          governance_badge: {
            maturity: 'AUTONOMOUS',
            confidence: 0.95,
            requires_supervision: false,
          },
        },
      ],
    },
  })
);

const mockGetEpisodeContext = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: [],
  })
);

jest.mock('../../../services/agentService', () => ({
  agentService: {
    getAgent: (agentId: string) => mockGetAgent(agentId),
    getAvailableAgents: () => mockGetAvailableAgents(),
    sendMessage: (agentId: string, message: string, sessionId?: string) =>
      mockSendMessage(agentId, message, sessionId),
    getChatSession: (sessionId: string) => mockGetChatSession(sessionId),
    getEpisodeContext: (agentId: string, query: string, limit: number) =>
      mockGetEpisodeContext(agentId, query, limit),
  },
}));

// Mock WebSocketContext
const mockWebSocketContext: any = {
  isConnected: true,
  sendStreamingMessage: jest.fn(),
  subscribeToStream: jest.fn(() => jest.fn()),
};

let streamHandlers: any = {};

jest.mock('../../../contexts/WebSocketContext', () => ({
  useWebSocket: () => mockWebSocketContext,
}));

// Mock react-native-paper
jest.mock('react-native-paper', () => ({
  Icon: 'Icon',
  MD3Colors: {
    primary50: '#2196F3',
    secondary50: '#FF9800',
    error50: '#f44336',
    secondary20: '#E0E0E0',
  },
}));

import { AgentChatScreen } from '../../../screens/agent/AgentChatScreen';

describe('AgentChatScreen', () => {
  beforeEach(() => {
    mockPlatform('ios');
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockRouteParams.agentId = 'agent-123';
    mockRouteParams.sessionId = undefined;
    mockWebSocketContext.isConnected = true;
    mockWebSocketContext.subscribeToStream.mockImplementation(
      (sessionId: string, onChunk: any, onComplete: any, onError: any) => {
        streamHandlers = { sessionId, onChunk, onComplete, onError };
        return jest.fn();
      }
    );
  });

  afterEach(() => {
    restorePlatform();
    jest.useRealTimers();
    jest.clearAllTimers();
  });

  const renderChat = () => render(<AgentChatScreen />);

  const waitForAgent = async () => {
    await waitFor(() => {
      expect(screen.getByText('Test Agent')).toBeTruthy();
    });
  };

  const typeAndSend = async (text: string) => {
    const input = screen.getByPlaceholderText(/type a message/i);
    fireEvent.changeText(input, text);
    fireEvent.press(screen.getByTestId('send-message-button'));
    await act(async () => {});
  };

  describe('Screen Rendering', () => {
    it('renders loading state initially', async () => {
      const { getByText } = renderChat();

      await waitFor(() => {
        expect(getByText('Loading agent...')).toBeTruthy();
      });
    });

    it('renders chat interface with agent name', async () => {
      renderChat();

      await waitForAgent();
    });

    it('renders empty state when no messages', async () => {
      renderChat();

      await waitFor(() => {
        expect(screen.getByText(/Start a conversation with/)).toBeTruthy();
        expect(screen.getByText(/A test agent for automation/)).toBeTruthy();
      });
    });

    it('renders agent maturity badge', async () => {
      renderChat();

      await waitFor(() => {
        expect(screen.getByText('AUTONOMOUS')).toBeTruthy();
      });
    });

    it('renders agent status badge', async () => {
      renderChat();

      await waitFor(() => {
        expect(screen.getByText('online')).toBeTruthy();
      });
    });
  });

  describe('Agent Loading', () => {
    it('shows error alert when agent fetch fails with a server error', async () => {
      mockGetAgent.mockResolvedValueOnce({ success: false, error: 'Agent missing' });

      renderChat();

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Error', 'Agent missing');
      });
    });

    it('shows error alert when agent fetch throws', async () => {
      mockGetAgent.mockRejectedValueOnce(new Error('Network down'));

      renderChat();

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to load agent');
      });
    });

    it('loads available agents when no agentId is provided', async () => {
      mockRouteParams.agentId = undefined;

      renderChat();

      await waitFor(() => {
        expect(mockGetAvailableAgents).toHaveBeenCalled();
        expect(screen.getByText('Test Agent')).toBeTruthy();
      });
    });

    it('shows empty state when no agents are available', async () => {
      mockRouteParams.agentId = undefined;
      mockGetAvailableAgents.mockResolvedValueOnce({ success: true, data: [] });

      renderChat();

      await waitFor(() => {
        expect(screen.getByText('Select Agent')).toBeTruthy();
        expect(screen.getByText(/Start a conversation with the agent/)).toBeTruthy();
      });
    });

    it('logs an error when the available-agents fetch throws', async () => {
      mockRouteParams.agentId = undefined;
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      mockGetAvailableAgents.mockRejectedValueOnce(new Error('boom'));

      renderChat();

      await waitFor(() => {
        expect(errorSpy).toHaveBeenCalled();
        expect(screen.getByText('Select Agent')).toBeTruthy();
      });
      errorSpy.mockRestore();
    });
  });

  describe('Session Loading', () => {
    it('loads and renders a chat session when sessionId is provided', async () => {
      mockRouteParams.sessionId = 'session-1';

      renderChat();

      await waitFor(() => {
        expect(mockGetChatSession).toHaveBeenCalledWith('session-1');
        expect(screen.getByText('Hello')).toBeTruthy();
        expect(screen.getByText('Hi there!')).toBeTruthy();
      });
    });

    it('renders agent name for assistant session messages', async () => {
      mockRouteParams.sessionId = 'session-1';

      renderChat();

      await waitFor(() => {
        expect(screen.getAllByText('Test Agent').length).toBeGreaterThanOrEqual(2);
      });
    });

    it('logs an error when session load fails', async () => {
      mockRouteParams.sessionId = 'session-1';
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      mockGetChatSession.mockRejectedValueOnce(new Error('boom'));

      renderChat();

      await waitFor(() => {
        expect(errorSpy).toHaveBeenCalled();
      });
      errorSpy.mockRestore();
    });
  });

  describe('Input Handling', () => {
    it('renders text input field', async () => {
      renderChat();

      await waitForAgent();

      expect(screen.getByPlaceholderText(/type a message/i)).toBeTruthy();
    });

    it('enforces max length limit on the input', async () => {
      renderChat();

      await waitForAgent();

      const input = screen.getByPlaceholderText(/type a message/i);
      expect(input.props.maxLength).toBe(2000);
    });

    it('disables input while sending', async () => {
      renderChat();

      await waitForAgent();

      const input = screen.getByPlaceholderText(/type a message/i);
      expect(input.props.editable).toBe(true);

      fireEvent.changeText(input, 'Hello');
      fireEvent.press(screen.getByTestId('send-message-button'));

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/type a message/i).props.editable).toBe(false);
      });
    });
  });

  describe('Send Button Behavior', () => {
    it('disables send button when input is empty', async () => {
      renderChat();

      await waitForAgent();

      const sendButton = screen.getByTestId('send-message-button');
      expect(sendButton.props.accessibilityState?.disabled ?? sendButton.props.disabled).toBe(true);
    });

    it('does not send when input is whitespace only', async () => {
      renderChat();

      await waitForAgent();

      fireEvent.changeText(screen.getByPlaceholderText(/type a message/i), '   ');
      fireEvent.press(screen.getByTestId('send-message-button'));

      expect(mockWebSocketContext.sendStreamingMessage).not.toHaveBeenCalled();
      expect(mockSendMessage).not.toHaveBeenCalled();
    });

    it('clears input and appends the user message after sending', async () => {
      renderChat();

      await waitForAgent();

      const input = screen.getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, 'Hello there');
      fireEvent.press(screen.getByTestId('send-message-button'));

      await waitFor(() => {
        expect(input.props.value).toBe('');
        expect(screen.getByText('Hello there')).toBeTruthy();
      });
    });
  });

  describe('Streaming Messages (WebSocket connected)', () => {
    it('sends streaming message and subscribes to the stream', async () => {
      renderChat();

      await waitForAgent();

      await typeAndSend('Hi agent');

      expect(mockWebSocketContext.sendStreamingMessage).toHaveBeenCalledWith(
        'agent-123',
        'Hi agent',
        'new'
      );
      expect(mockWebSocketContext.subscribeToStream).toHaveBeenCalledWith(
        'new',
        expect.any(Function),
        expect.any(Function),
        expect.any(Function)
      );
    });

    it('renders streaming chunks and appends them to the streaming message', async () => {
      renderChat();

      await waitForAgent();

      await typeAndSend('Tell me a story');

      await act(async () => {
        streamHandlers.onChunk({ token: 'Once ', metadata: {} });
      });
      expect(screen.getByText('Once ')).toBeTruthy();

      await act(async () => {
        streamHandlers.onChunk({ token: 'upon ', metadata: {} });
      });
      expect(screen.getByText('Once upon ')).toBeTruthy();
    });

    it('renders governance badge from streaming chunk metadata', async () => {
      renderChat();

      await waitForAgent();

      await typeAndSend('Analyze this');

      await act(async () => {
        streamHandlers.onChunk({
          token: 'Working',
          metadata: {
            governance_badge: { maturity: 'SUPERVISED', confidence: 0.8 },
          },
        });
      });

      expect(screen.getByText('SUPERVISED')).toBeTruthy();
    });

    it('marks the stream complete and re-enables input', async () => {
      renderChat();

      await waitForAgent();

      await typeAndSend('Finish this');

      await act(async () => {
        streamHandlers.onChunk({ token: 'Final answer', metadata: {} });
      });
      expect(screen.getByText('Final answer')).toBeTruthy();

      await act(async () => {
        streamHandlers.onComplete();
      });

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/type a message/i).props.editable).toBe(true);
      });
      expect(screen.getByText('Final answer')).toBeTruthy();
    });

    it('alerts the user when the stream errors', async () => {
      renderChat();

      await waitForAgent();

      await typeAndSend('Broken stream');

      await act(async () => {
        streamHandlers.onError('Connection lost');
      });

      expect(Alert.alert).toHaveBeenCalledWith('Streaming Error', 'Connection lost');
      await waitFor(() => {
        expect(screen.getByPlaceholderText(/type a message/i).props.editable).toBe(true);
      });
    });

    it('unsubscribes from the stream after 30 seconds', async () => {
      const unsubscribe = jest.fn();
      mockWebSocketContext.subscribeToStream.mockReturnValue(unsubscribe);

      renderChat();

      await waitForAgent();

      await typeAndSend('Long request');

      act(() => {
        jest.advanceTimersByTime(30000);
      });

      expect(unsubscribe).toHaveBeenCalled();
    });
  });

  describe('Non-Streaming Fallback (WebSocket disconnected)', () => {
    it('sends via agentService and renders the assistant reply', async () => {
      mockWebSocketContext.isConnected = false;

      renderChat();

      await waitForAgent();

      await typeAndSend('Fallback message');

      await waitFor(() => {
        expect(mockSendMessage).toHaveBeenCalledWith('agent-123', 'Fallback message', undefined);
        expect(screen.getByText('Hello! How can I help you?')).toBeTruthy();
      });
    });

    it('shows the agent governance badge on the fallback reply', async () => {
      mockWebSocketContext.isConnected = false;

      renderChat();

      await waitForAgent();

      await typeAndSend('Reply with badge');

      await waitFor(() => {
        expect(screen.getAllByText('AUTONOMOUS').length).toBeGreaterThanOrEqual(2);
      });
    });

    it('alerts when the fallback send fails with a server error', async () => {
      mockWebSocketContext.isConnected = false;
      mockSendMessage.mockResolvedValueOnce({ success: false, error: 'Rate limited' });

      renderChat();

      await waitForAgent();

      await typeAndSend('Fail me');

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Error', 'Rate limited');
      });
    });

    it('alerts when the fallback send throws', async () => {
      mockWebSocketContext.isConnected = false;
      mockSendMessage.mockRejectedValueOnce(new Error('network'));

      renderChat();

      await waitForAgent();

      await typeAndSend('Crash me');

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to send message');
      });
    });
  });

  describe('Episode Context', () => {
    it('fetches and displays episode context after sending a message', async () => {
      mockGetEpisodeContext.mockResolvedValueOnce({
        success: true,
        data: [
          {
            id: 'ep-1',
            title: 'Sales Pipeline Review',
            summary: 'Reviewed Q3 pipeline',
            created_at: '2024-01-01T00:00:00Z',
            relevance_score: 0.87,
          },
        ],
      });

      renderChat();

      await waitForAgent();

      await typeAndSend('What did we do last time?');

      await waitFor(() => {
        expect(mockGetEpisodeContext).toHaveBeenCalledWith('agent-123', 'What did we do last time?', 3);
        expect(screen.getByText('Relevant Context')).toBeTruthy();
        expect(screen.getByText('Sales Pipeline Review')).toBeTruthy();
        expect(screen.getByText('87%')).toBeTruthy();
      });
    });

    it('logs when an episode chip is tapped', async () => {
      const logSpy = jest.spyOn(console, 'log').mockImplementation(() => {});
      mockGetEpisodeContext.mockResolvedValueOnce({
        success: true,
        data: [
          {
            id: 'ep-1',
            title: 'Sales Pipeline Review',
            summary: 'Reviewed Q3 pipeline',
            created_at: '2024-01-01T00:00:00Z',
            relevance_score: 0.87,
          },
        ],
      });

      renderChat();

      await waitForAgent();

      await typeAndSend('Remind me of context');

      await waitFor(() => {
        expect(screen.getByText('Sales Pipeline Review')).toBeTruthy();
      });

      fireEvent.press(screen.getByText('Sales Pipeline Review'));

      expect(logSpy).toHaveBeenCalledWith('Episode tapped:', 'ep-1');
      logSpy.mockRestore();
    });

    it('hides the episode panel when close is pressed', async () => {
      mockGetEpisodeContext.mockResolvedValueOnce({
        success: true,
        data: [
          {
            id: 'ep-1',
            title: 'Sales Pipeline Review',
            summary: 'Reviewed Q3 pipeline',
            created_at: '2024-01-01T00:00:00Z',
            relevance_score: 0.87,
          },
        ],
      });

      renderChat();

      await waitForAgent();

      await typeAndSend('Show me context');

      await waitFor(() => {
        expect(screen.getByText('Relevant Context')).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('episode-close-button'));

      await waitFor(() => {
        expect(screen.queryByText('Relevant Context')).toBeNull();
      });
    });

    it('does not show episodes when context is empty', async () => {
      renderChat();

      await waitForAgent();

      await typeAndSend('No context please');

      await waitFor(() => {
        expect(screen.queryByText('Relevant Context')).toBeNull();
      });
    });

    it('logs an error when episode context fetch fails', async () => {
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      mockGetEpisodeContext.mockRejectedValueOnce(new Error('boom'));

      renderChat();

      await waitForAgent();

      await typeAndSend('Context fail');

      await waitFor(() => {
        expect(errorSpy).toHaveBeenCalled();
      });
      errorSpy.mockRestore();
    });
  });

  describe('Connection Status', () => {
    it('shows reconnection status when disconnected', async () => {
      mockWebSocketContext.isConnected = false;

      renderChat();

      await waitForAgent();

      expect(screen.getByText('Reconnecting...')).toBeTruthy();
    });

    it('does not show reconnection status when connected', async () => {
      renderChat();

      await waitForAgent();

      expect(screen.queryByText('Reconnecting...')).toBeNull();
    });
  });

  describe('Header Actions', () => {
    it('navigates back when back button pressed', async () => {
      renderChat();

      await waitForAgent();

      fireEvent.press(screen.getByTestId('back-button'));
      expect(mockNavigation.goBack).toHaveBeenCalled();
    });
  });

  describe('Governance Badges', () => {
    it('shows correct badge for AUTONOMOUS agent', async () => {
      renderChat();

      await waitFor(() => {
        expect(screen.getByText('AUTONOMOUS')).toBeTruthy();
      });
    });

    it('renders INTERN agent with blue maturity badge', async () => {
      mockGetAgent.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'agent-123',
          name: 'Intern Agent',
          description: 'Learning',
          maturity_level: 'INTERN',
          status: 'offline',
          confidence_score: 0.6,
          created_at: '2024-01-01T00:00:00Z',
        },
      });

      renderChat();

      await waitFor(() => {
        expect(screen.getByText('INTERN')).toBeTruthy();
        expect(screen.getByText('offline')).toBeTruthy();
      });

      const badgeText = screen.getByText('INTERN');
      const parent = badgeText.parent;
      const badge = parent && parent.parent;
      const flattened = StyleSheet.flatten(badge?.props.style);
      expect(flattened && flattened.backgroundColor).toBe('#2196F3');
    });

    it('renders STUDENT agent with grey maturity badge', async () => {
      mockGetAgent.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'agent-123',
          name: 'Student Agent',
          description: 'Training',
          maturity_level: 'STUDENT',
          status: 'maintenance',
          confidence_score: 0.4,
          created_at: '2024-01-01T00:00:00Z',
        },
      });

      renderChat();

      await waitFor(() => {
        expect(screen.getByText('STUDENT')).toBeTruthy();
      });

      const badgeText = screen.getByText('STUDENT');
      const flattened = StyleSheet.flatten(badgeText.parent?.parent?.props.style);
      expect(flattened.backgroundColor).toBe('#9E9E9E');
    });

    it('renders SUPERVISED agent with orange maturity badge', async () => {
      mockGetAgent.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'agent-123',
          name: 'Supervised Agent',
          description: 'Supervised',
          maturity_level: 'SUPERVISED',
          status: 'busy',
          confidence_score: 0.75,
          created_at: '2024-01-01T00:00:00Z',
        },
      });

      renderChat();

      await waitFor(() => {
        expect(screen.getByText('SUPERVISED')).toBeTruthy();
        expect(screen.getByText('busy')).toBeTruthy();
      });

      const badgeText = screen.getByText('SUPERVISED');
      const flattened = StyleSheet.flatten(badgeText.parent?.parent?.props.style);
      expect(flattened.backgroundColor).toBe('#FF9800');
    });

    it('renders unknown maturity with the default grey color', async () => {
      mockGetAgent.mockResolvedValueOnce({
        success: true,
        data: {
          id: 'agent-123',
          name: 'Unknown Agent',
          description: 'Unknown',
          maturity_level: 'WEIRD' as any,
          status: 'unknown-status' as any,
          confidence_score: 0.5,
          created_at: '2024-01-01T00:00:00Z',
        },
      });

      renderChat();

      await waitFor(() => {
        expect(screen.getByText('WEIRD')).toBeTruthy();
      });

      const badgeText = screen.getByText('WEIRD');
      const flattened = StyleSheet.flatten(badgeText.parent?.parent?.props.style);
      expect(flattened.backgroundColor).toBe('#9E9E9E');
    });
  });

  describe('Edge Cases', () => {
    it('handles very long messages', async () => {
      renderChat();

      await waitForAgent();

      const input = screen.getByPlaceholderText(/type a message/i);
      const longMessage = 'a'.repeat(1999);
      fireEvent.changeText(input, longMessage);

      expect(input.props.value).toBe(longMessage);
    });

    it('renders message timestamps in HH:MM format', async () => {
      mockRouteParams.sessionId = 'session-1';

      renderChat();

      await waitFor(() => {
        expect(screen.getByText('Hi there!')).toBeTruthy();
      });

      // Both session messages render a localized time
      const times = screen.getAllByText(/\d{1,2}:\d{2}/);
      expect(times.length).toBe(2);
    });
  });
});
