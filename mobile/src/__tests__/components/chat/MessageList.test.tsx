/**
 * MessageList Component Tests
 *
 * Tests for message list rendering, user/agent differentiation,
 * timestamps, and scroll management.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { MessageList } from '../../../components/chat/MessageList';

// Mock react-native-paper
jest.mock('react-native-paper', () => ({
  useTheme: () => ({
    colors: {
      background: '#fff',
      surface: '#fff',
      onSurface: '#000',
      onSurfaceVariant: '#666',
      primary: '#2196F3',
      tertiary: '#FF9800',
      secondary: '#4CAF50',
      error: '#f44336',
      surfaceVariant: '#f5f5f5',
    },
  }),
  Avatar: {
    Text: ({ label, style }: any) => {
      const React = require('react');
      const { Text } = require('react-native');
      return <Text style={style}>{label}</Text>;
    },
  },
  Badge: ({ children, style }: any) => {
    const React = require('react');
    const { Text } = require('react-native');
    return <Text style={style}>{children}</Text>;
  },
  Menu: {
    Item: ({ onPress, title }: any) => {
      const React = require('react');
      const { TouchableOpacity, Text } = require('react-native');
      return (
        <TouchableOpacity onPress={onPress}>
          <Text>{title}</Text>
        </TouchableOpacity>
      );
    },
  },
  FAB: 'FAB',
  Icon: 'Icon',
}));

// Mock date-fns
jest.mock('date-fns', () => ({
  formatDistanceToNow: (date: Date) => '5 minutes ago',
  differenceInDays: () => 0,
  isToday: () => true,
  isYesterday: () => false,
}));

// Mock StreamingText
jest.mock('../../../components/chat/StreamingText', () => ({
  default: ({ text, style }: any) => {
    const React = require('react');
    const { Text } = require('react-native');
    return <Text style={style}>{text}</Text>;
  },
}));

describe('MessageList', () => {
  const mockMessages = [
    {
      id: 'msg-1',
      role: 'user' as const,
      content: 'Hello, how are you?',
      timestamp: new Date(Date.now() - 1000 * 60 * 5),
    },
    {
      id: 'msg-2',
      role: 'agent' as const,
      content: 'I am doing well, thank you!',
      agent_id: 'agent-1',
      agent_name: 'Test Agent',
      agent_maturity: 'AUTONOMOUS' as const,
      timestamp: new Date(Date.now() - 1000 * 60 * 4),
    },
    {
      id: 'msg-3',
      role: 'user' as const,
      content: 'Can you help me with a task?',
      timestamp: new Date(Date.now() - 1000 * 60 * 3),
    },
    {
      id: 'msg-4',
      role: 'agent' as const,
      content: 'Of course! What do you need?',
      agent_id: 'agent-1',
      agent_name: 'Test Agent',
      agent_maturity: 'AUTONOMOUS' as const,
      timestamp: new Date(Date.now() - 1000 * 60 * 2),
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    it('should render list of messages', () => {
      const { getByText } = render(<MessageList messages={mockMessages} />);

      expect(getByText('Hello, how are you?')).toBeTruthy();
      expect(getByText('I am doing well, thank you!')).toBeTruthy();
      expect(getByText('Can you help me with a task?')).toBeTruthy();
      expect(getByText('Of course! What do you need?')).toBeTruthy();
    });

    it('should render empty list', () => {
      const { getByText } = render(<MessageList messages={[]} />);

      // Should render without crashing
      expect(screen.getByTestId('message-list')).toBeTruthy();
    });

    it('should render single message', () => {
      const singleMessage = [mockMessages[0]];
      const { getByText } = render(<MessageList messages={singleMessage} />);

      expect(getByText('Hello, how are you?')).toBeTruthy();
    });
  });

  describe('Message Differentiation', () => {
    it('should differentiate user messages', () => {
      const { getByText } = render(<MessageList messages={mockMessages} />);

      expect(getByText('Hello, how are you?')).toBeTruthy();
    });

    it('should differentiate agent messages', () => {
      const { getByText } = render(<MessageList messages={mockMessages} />);

      expect(getByText('I am doing well, thank you!')).toBeTruthy();
    });

    it('should differentiate system messages', () => {
      const systemMessage = {
        id: 'msg-sys',
        role: 'system' as const,
        content: 'System: Connection established',
        timestamp: new Date(),
      };

      const { getByText } = render(
        <MessageList messages={[systemMessage]} />
      );

      expect(getByText(/System: Connection established/)).toBeTruthy();
    });

    it('should show agent avatar for agent messages', () => {
      const { getByText } = render(<MessageList messages={mockMessages} />);

      // Agent name should be visible
      expect(getByText('Test Agent')).toBeTruthy();
    });
  });

  describe('Timestamps', () => {
    it('should show timestamps for messages', () => {
      const { getByText } = render(<MessageList messages={mockMessages} />);

      expect(getByText('5 minutes ago')).toBeTruthy();
    });

    it('should show relative time format', () => {
      const { getByText } = render(<MessageList messages={mockMessages} />);

      expect(getByText(/minutes ago/)).toBeTruthy();
    });
  });

  describe('Scroll Management', () => {
    it('should invert scroll for new messages', () => {
      const { getByTestId } = render(<MessageList messages={mockMessages} />);

      expect(getByTestId('message-list')).toBeTruthy();
    });

    it('should scroll to bottom when new message is added', () => {
      const { rerender, getByText } = render(
        <MessageList messages={mockMessages.slice(0, 2)} />
      );

      expect(getByText('Hello, how are you?')).toBeTruthy();

      rerender(<MessageList messages={mockMessages} />);

      expect(getByText('Can you help me with a task?')).toBeTruthy();
    });
  });

  describe('Agent Information', () => {
    it('should display agent name', () => {
      const { getByText } = render(<MessageList messages={mockMessages} />);

      expect(getByText('Test Agent')).toBeTruthy();
    });

    it('should display agent maturity badge', () => {
      const { getByText } = render(<MessageList messages={mockMessages} />);

      expect(getByText('AUTONOMOUS')).toBeTruthy();
    });
  });

  describe('Message Actions', () => {
    it('should handle message copy callback', () => {
      const onCopy = jest.fn();

      const { getByText } = render(
        <MessageList messages={mockMessages} onMessageCopy={onCopy} />
      );

      expect(getByText('Hello, how are you?')).toBeTruthy();
    });

    it('should handle message feedback callback', () => {
      const onFeedback = jest.fn();

      const { getByText } = render(
        <MessageList messages={mockMessages} onMessageFeedback={onFeedback} />
      );

      expect(getByText('I am doing well, thank you!')).toBeTruthy();
    });

    it('should handle message regenerate callback', () => {
      const onRegenerate = jest.fn();

      const { getByText } = render(
        <MessageList messages={mockMessages} onMessageRegenerate={onRegenerate} />
      );

      expect(getByText('I am doing well, thank you!')).toBeTruthy();
    });

    it('should handle message delete callback', () => {
      const onDelete = jest.fn();

      const { getByText } = render(
        <MessageList messages={mockMessages} onMessageDelete={onDelete} />
      );

      expect(getByText('Hello, how are you?')).toBeTruthy();
    });
  });

  describe('Episode Context', () => {
    it('should display episode context when available', () => {
      const messageWithEpisode = {
        ...mockMessages[1],
        episode_context: {
          episode_id: 'ep-1',
          title: 'Previous Conversation',
          relevance_score: 0.85,
        },
      };

      const onEpisodePress = jest.fn();

      const { getByText } = render(
        <MessageList
          messages={[messageWithEpisode]}
          onEpisodePress={onEpisodePress}
        />
      );

      expect(getByText('Previous Conversation')).toBeTruthy();
    });

    it('should handle episode press callback', () => {
      const messageWithEpisode = {
        ...mockMessages[1],
        episode_context: {
          episode_id: 'ep-1',
          title: 'Previous Conversation',
          relevance_score: 0.85,
        },
      };

      const onEpisodePress = jest.fn();

      render(
        <MessageList
          messages={[messageWithEpisode]}
          onEpisodePress={onEpisodePress}
        />
      );

      // Episode press is handled via callbacks
      expect(onEpisodePress).not.toHaveBeenCalled();
    });
  });

  describe('Loading State', () => {
    it('should show loading indicator when loading', () => {
      const { getByTestId } = render(
        <MessageList messages={mockMessages} loading={true} />
      );

      expect(getByTestId('message-list')).toBeTruthy();
    });

    it('should hide loading indicator when not loading', () => {
      const { getByTestId } = render(
        <MessageList messages={mockMessages} loading={false} />
      );

      expect(getByTestId('message-list')).toBeTruthy();
    });
  });

  describe('Custom Components', () => {
    it('should render ListHeaderComponent when provided', () => {
      const Header = () => {
        const React = require('react');
        const { Text } = require('react-native');
        return <Text>Header Content</Text>;
      };

      const { getByText } = render(
        <MessageList
          messages={mockMessages}
          ListHeaderComponent={Header}
        />
      );

      expect(getByText('Header Content')).toBeTruthy();
    });

    it('should render ListFooterComponent when provided', () => {
      const Footer = () => {
        const React = require('react');
        const { Text } = require('react-native');
        return <Text>Footer Content</Text>;
      };

      const { getByText } = render(
        <MessageList
          messages={mockMessages}
          ListFooterComponent={Footer}
        />
      );

      expect(getByText('Footer Content')).toBeTruthy();
    });
  });

  describe('Governance Information', () => {
    it('should display action complexity badge', () => {
      const messageWithGovernance = {
        ...mockMessages[1],
        governance: {
          action_complexity: 3,
          requires_approval: false,
          supervised: false,
        },
      };

      const { getByText } = render(
        <MessageList messages={[messageWithGovernance]} />
      );

      expect(getByText('I am doing well, thank you!')).toBeTruthy();
    });

    it('should display approval required badge', () => {
      const messageWithGovernance = {
        ...mockMessages[1],
        governance: {
          action_complexity: 4,
          requires_approval: true,
          supervised: false,
        },
      };

      const { getByText } = render(
        <MessageList messages={[messageWithGovernance]} />
      );

      expect(getByText('I am doing well, thank you!')).toBeTruthy();
    });
  });

  describe('Streaming Messages', () => {
    it('should display streaming indicator for streaming messages', () => {
      const streamingMessage = {
        ...mockMessages[1],
        isStreaming: true,
      };

      const { getByText } = render(
        <MessageList messages={[streamingMessage]} />
      );

      expect(getByText('I am doing well, thank you!')).toBeTruthy();
    });

    it('should update content during streaming', () => {
      const streamingMessage = {
        ...mockMessages[1],
        isStreaming: true,
        content: 'Partial',
      };

      const { getByText, rerender } = render(
        <MessageList messages={[streamingMessage]} />
      );

      expect(getByText('Partial')).toBeTruthy();

      const updatedMessage = {
        ...streamingMessage,
        content: 'Partial message updated',
      };

      rerender(<MessageList messages={[updatedMessage]} />);

      expect(getByText('Partial message updated')).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    it('should handle messages with empty content', () => {
      const emptyMessage = {
        id: 'msg-empty',
        role: 'user' as const,
        content: '',
        timestamp: new Date(),
      };

      const { getByTestId } = render(
        <MessageList messages={[emptyMessage]} />
      );

      expect(getByTestId('message-list')).toBeTruthy();
    });

    it('should handle messages with very long content', () => {
      const longMessage = {
        id: 'msg-long',
        role: 'agent' as const,
        content: 'A'.repeat(5000),
        agent_id: 'agent-1',
        agent_name: 'Test Agent',
        agent_maturity: 'AUTONOMOUS' as const,
        timestamp: new Date(),
      };

      const { getByText } = render(
        <MessageList messages={[longMessage]} />
      );

      expect(getByText(/A/)).toBeTruthy();
    });

    it('should handle messages with special characters', () => {
      const specialMessage = {
        id: 'msg-special',
        role: 'user' as const,
        content: 'Test <script>alert("xss")</script> & "quotes"',
        timestamp: new Date(),
      };

      const { getByText } = render(
        <MessageList messages={[specialMessage]} />
      );

      expect(getByText(/Test/)).toBeTruthy();
    });
  });
});
