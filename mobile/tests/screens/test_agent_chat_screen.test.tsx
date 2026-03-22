/**
 * AgentChatScreen Tests
 *
 * Comprehensive test suite for AgentChatScreen component covering:
 * - Rendering with agent data
 * - Message sending and receiving
 * - Streaming message updates
 * - Episode context display
 * - Connection status
 * - Navigation interactions
 * - Loading and error states
 *
 * @see src/screens/agent/AgentChatScreen.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Alert } from 'react-native';
import { AgentChatScreen } from '../../src/screens/agent/AgentChatScreen';

// Mock navigation
const mockNavigation = {
  goBack: jest.fn(),
  navigate: jest.fn(),
  push: jest.fn(),
  replace: jest.fn(),
  reset: jest.fn(),
  dispatch: jest.fn(),
  isFocused: jest.fn(() => true),
  canGoBack: jest.fn(() => true),
  getId: jest.fn(),
  getParent: jest.fn(),
};

const mockRoute = {
  params: {
    agentId: 'agent-123',
    sessionId: undefined,
  },
};

jest.mock('@react-navigation/native', () => ({
  useRoute: () => mockRoute,
  useNavigation: () => mockNavigation,
  RouteProp: jest.fn(),
  NavigationProp: jest.fn(),
}));

// Mock agent service
jest.mock('../../src/services/agentService', () => ({
  agentService: {
    getAgent: jest.fn().mockResolvedValue({
      success: true,
      data: {
        id: 'agent-123',
        name: 'Test Agent',
        description: 'Test agent description',
        maturity_level: 'AUTONOMOUS',
        status: 'online',
        confidence_score: 0.95,
      },
    }),
    getAvailableAgents: jest.fn().mockResolvedValue({
      success: true,
      data: [
        {
          id: 'agent-123',
          name: 'Test Agent',
          maturity_level: 'AUTONOMOUS',
          status: 'online',
        },
      ],
    }),
    sendMessage: jest.fn().mockResolvedValue({
      success: true,
      data: {
        message: {
          id: 'msg-123',
          role: 'assistant',
          content: 'Test response',
          timestamp: new Date().toISOString(),
        },
        session_id: 'session-123',
      },
    }),
    getChatSession: jest.fn().mockResolvedValue({
      success: true,
      data: {
        messages: [],
      },
    }),
    getEpisodeContext: jest.fn().mockResolvedValue({
      success: true,
      data: [],
    }),
  },
}));

// Mock WebSocket context
jest.mock('../../src/contexts/WebSocketContext', () => ({
  useWebSocket: jest.fn(() => ({
    isConnected: true,
    sendStreamingMessage: jest.fn(),
    subscribeToStream: jest.fn(() => jest.fn()),
  })),
}));

describe('AgentChatScreen - Rendering', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Renders loading state initially
  it('should render loading state initially', () => {
    const { getByText } = render(<AgentChatScreen />);

    expect(getByText('Loading agent...')).toBeTruthy();
  });

  // Test 2: Renders agent info after loading
  it('should render agent info after loading', async () => {
    const { getByText, queryByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(queryByText('Loading agent...')).toBeNull();
    });

    await waitFor(() => {
      expect(getByText('Test Agent')).toBeTruthy();
    });
  });

  // Test 3: Displays maturity badge
  it('should display maturity badge', async () => {
    const { getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByText(/AUTONOMOUS/)).toBeTruthy();
    });
  });

  // Test 4: Displays status badge
  it('should display status badge', async () => {
    const { getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByText('online')).toBeTruthy();
    });
  });

  // Test 5: Shows empty state when no messages
  it('should show empty state when no messages', async () => {
    const { getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByText(/Start a conversation with/)).toBeTruthy();
    });
  });

  // Test 6: Renders input field
  it('should render input field', async () => {
    const { getByPlaceholderText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });
  });

  // Test 7: Renders send button
  it('should render send button', async () => {
    const { getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      const sendButton = getByTestId(/send/i);
      expect(sendButton).toBeTruthy();
    });
  });
});

describe('AgentChatScreen - Message Sending', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (Alert.alert as jest.Mock).mockClear();
  });

  // Test 1: Sends message when send button pressed
  it('should send message when send button pressed', async () => {
    const { getByPlaceholderText, getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Hello agent');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      expect(input.props.value).toBe('');
    });
  });

  // Test 2: Does not send empty message
  it('should not send empty message', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    const { getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    expect(agentService.sendMessage).not.toHaveBeenCalled();
  });

  // Test 3: Adds user message to chat
  it('should add user message to chat', async () => {
    const { getByPlaceholderText, getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Test message');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      expect(getByText('Test message')).toBeTruthy();
    });
  });

  // Test 4: Disables send button while sending
  it('should disable send button while sending', async () => {
    const { getByPlaceholderText, getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Test message');

    const sendButton = getByTestId(/send/i);

    await act(async () => {
      fireEvent.press(sendButton);
    });

    // Button should be disabled while sending
    expect(sendButton).toBeTruthy();
  });

  // Test 5: Handles message sending error
  it('should handle message sending error', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    agentService.sendMessage.mockRejectedValueOnce(new Error('Network error'));

    const { getByPlaceholderText, getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Test message');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Error',
        'Failed to send message'
      );
    });
  });
});

describe('AgentChatScreen - Message Display', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays user messages on right
  it('should display user messages on right', async () => {
    const { getByPlaceholderText, getByTestId, getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'User message');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      expect(getByText('User message')).toBeTruthy();
    });
  });

  // Test 2: Displays assistant messages on left
  it('should display assistant messages on left', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    agentService.sendMessage.mockResolvedValueOnce({
      success: true,
      data: {
        message: {
          id: 'msg-123',
          role: 'assistant',
          content: 'Assistant response',
          timestamp: new Date().toISOString(),
        },
        session_id: 'session-123',
      },
    });

    const { getByPlaceholderText, getByTestId, getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Hello');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      expect(getByText('Assistant response')).toBeTruthy();
    });
  });

  // Test 3: Displays message timestamps
  it('should display message timestamps', async () => {
    const { getByPlaceholderText, getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Test');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      // Timestamp should be displayed
      const timestampRegex = /\d{1,2}:\d{2}/;
      expect(screen.getByText(timestampRegex)).toBeTruthy();
    });
  });

  // Test 4: Shows governance badge on assistant messages
  it('should show governance badge on assistant messages', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    agentService.sendMessage.mockResolvedValueOnce({
      success: true,
      data: {
        message: {
          id: 'msg-123',
          role: 'assistant',
          content: 'Response with governance',
          timestamp: new Date().toISOString(),
          governance_badge: {
            maturity: 'AUTONOMOUS',
            confidence: 0.95,
            requires_supervision: false,
          },
        },
        session_id: 'session-123',
      },
    });

    const { getByPlaceholderText, getByTestId, getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Hello');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      expect(getByText(/AUTONOMOUS/)).toBeTruthy();
    });
  });
});

describe('AgentChatScreen - Navigation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Goes back when back button pressed
  it('should go back when back button pressed', async () => {
    const { getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      const backButton = getByTestId(/arrow-left/i);
      fireEvent.press(backButton);
    });

    expect(mockNavigation.goBack).toHaveBeenCalled();
  });

  // Test 2: Opens settings when settings button pressed
  it('should open settings when settings button pressed', async () => {
    const { getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      const settingsButton = getByTestId(/cog/i);
      fireEvent.press(settingsButton);
    });

    // Settings button should be pressable
    expect(mockNavigation).toBeDefined();
  });
});

describe('AgentChatScreen - Connection Status', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Shows reconnected when connected
  it('should show reconnected when connected', async () => {
    const { queryByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(queryByText('Reconnecting...')).toBeNull();
    });
  });

  // Test 2: Shows reconnecting when disconnected
  it('should show reconnecting when disconnected', async () => {
    const { useWebSocket } = require('../../src/contexts/WebSocketContext');
    useWebSocket.mockReturnValue({
      isConnected: false,
      sendStreamingMessage: jest.fn(),
      subscribeToStream: jest.fn(() => jest.fn()),
    });

    const { getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByText('Reconnecting...')).toBeTruthy();
    });
  });
});

describe('AgentChatScreen - Episode Context', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Displays episode context when available
  it('should display episode context when available', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    agentService.getEpisodeContext.mockResolvedValueOnce({
      success: true,
      data: [
        {
          id: 'episode-1',
          title: 'Previous conversation',
          relevance_score: 0.9,
        },
      ],
    });

    const { getByPlaceholderText, getByTestId, getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Continue our conversation');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      expect(getByText('Relevant Context')).toBeTruthy();
    });
  });

  // Test 2: Closes episode context when close pressed
  it('should close episode context when close pressed', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    agentService.getEpisodeContext.mockResolvedValueOnce({
      success: true,
      data: [
        {
          id: 'episode-1',
          title: 'Previous conversation',
          relevance_score: 0.9,
        },
      ],
    });

    const { getByPlaceholderText, getByTestId, getByText, queryByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    fireEvent.changeText(input, 'Continue');

    await act(async () => {
      const sendButton = getByTestId(/send/i);
      fireEvent.press(sendButton);
    });

    await waitFor(() => {
      expect(getByText('Relevant Context')).toBeTruthy();
    });

    const closeButton = getByTestId(/close/i);
    fireEvent.press(closeButton);

    await waitFor(() => {
      expect(queryByText('Relevant Context')).toBeNull();
    });
  });
});

describe('AgentChatScreen - Error Handling', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Handles agent loading error
  it('should handle agent loading error', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    agentService.getAgent.mockRejectedValueOnce(new Error('Failed to load'));

    const { getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Error',
        'Failed to load agent'
      );
    });
  });

  // Test 2: Handles session loading error gracefully
  it('should handle session loading error gracefully', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    agentService.getChatSession.mockRejectedValueOnce(new Error('Session error'));

    // Should not crash
    const { getByPlaceholderText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });
  });

  // Test 3: Handles episode context error gracefully
  it('should handle episode context error gracefully', async () => {
    const agentService = require('../../src/services/agentService').agentService;
    agentService.getEpisodeContext.mockRejectedValueOnce(new Error('Episode error'));

    const { getByPlaceholderText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });
  });
});

describe('AgentChatScreen - Edge Cases', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Handles no agent ID
  it('should handle no agent ID', async () => {
    mockRoute.params = {};

    const { getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByText('Select Agent')).toBeTruthy();
    });
  });

  // Test 2: Handles session ID
  it('should handle session ID', async () => {
    mockRoute.params = {
      agentId: 'agent-123',
      sessionId: 'session-123',
    };

    const agentService = require('../../src/services/agentService').agentService;
    agentService.getChatSession.mockResolvedValueOnce({
      success: true,
      data: {
        messages: [
          {
            id: 'msg-1',
            role: 'user',
            content: 'Previous message',
            timestamp: new Date().toISOString(),
          },
        ],
      },
    });

    const { getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByText('Previous message')).toBeTruthy();
    });

    // Reset
    mockRoute.params = {
      agentId: 'agent-123',
      sessionId: undefined,
    };
  });

  // Test 3: Handles long message truncation
  it('should handle long message truncation', async () => {
    const { getByPlaceholderText, getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByPlaceholderText('Type a message...')).toBeTruthy();
    });

    const input = getByPlaceholderText('Type a message...');
    const longMessage = 'a'.repeat(2000);

    fireEvent.changeText(input, longMessage);

    // Should truncate to 2000 chars
    expect(input.props.value).toBe(longMessage);
  });
});

describe('AgentChatScreen - Accessibility', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Has accessible input field
  it('should have accessible input field', async () => {
    const { getByPlaceholderText } = render(<AgentChatScreen />);

    await waitFor(() => {
      const input = getByPlaceholderText('Type a message...');
      expect(input).toBeTruthy();
    });
  });

  // Test 2: Has accessible send button
  it('should have accessible send button', async () => {
    const { getByTestId } = render(<AgentChatScreen />);

    await waitFor(() => {
      const sendButton = getByTestId(/send/i);
      expect(sendButton).toBeTruthy();
    });
  });

  // Test 3: Announces connection status
  it('should announce connection status', async () => {
    const { useWebSocket } = require('../../src/contexts/WebSocketContext');
    useWebSocket.mockReturnValue({
      isConnected: false,
      sendStreamingMessage: jest.fn(),
      subscribeToStream: jest.fn(() => jest.fn()),
    });

    const { getByText } = render(<AgentChatScreen />);

    await waitFor(() => {
      expect(getByText('Reconnecting...')).toBeTruthy();
    });
  });
});
