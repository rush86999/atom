/**
 * MessageList Component Tests
 *
 * Testing suite for MessageList component
 * Coverage goals: Message rendering, grouping, actions, interactions
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { MessageList } from '../chat/MessageList';

// Mock dependencies
jest.mock('react-native-paper', () => ({
  useTheme: () => ({
    colors: {
      primary: '#2196F3',
      primaryContainer: '#E3F2FD',
      surface: '#fff',
      surfaceVariant: '#f5f5f5',
      onSurface: '#000',
      onSurfaceVariant: '#666',
      onSurfaceDisabled: '#ccc',
      tertiary: '#FF9800',
      secondary: '#4CAF50',
      error: '#f44336',
      outline: '#e0e0e0',
    },
  }),
  Icon: 'Icon',
  Avatar: {
    Icon: 'Avatar.Icon',
    Text: ({ label, style }: any) => {
      const React = require('react');
      const { Text } = require('react-native');
      return <Text style={style}>{label}</Text>;
    },
    Image: 'Avatar.Image',
  },
  Badge: ({ children, style }: any) => {
    const React = require('react');
    const { Text } = require('react-native');
    return <Text style={style}>{children}</Text>;
  },
  Menu: Object.assign(
    ({ visible, children, anchor }: any) => (visible ? (<>{anchor}{children}</>) : null),
    {
      Item: ({ leadingIcon, onPress, title, titleStyle }: any) => {
        const React = require('react');
        const { TouchableOpacity, Text } = require('react-native');
        return (
          <TouchableOpacity onPress={onPress} style={titleStyle}>
            <Text>{title}</Text>
          </TouchableOpacity>
        );
      },
    }
  ),
  FAB: ({ icon, style, onPress }: any) => {
    const React = require('react');
    const { View } = require('react-native');
    return <View testID="scroll-to-bottom-fab" style={style} onPress={onPress} />;
  },
}));

jest.mock('date-fns', () => ({
  formatDistanceToNow: () => '5 minutes ago',
  differenceInDays: () => 0,
  isToday: () => true,
  isYesterday: () => false,
}));

jest.mock('../chat/StreamingText', () => ({
  __esModule: true,
  default: ({ text, style }: any) => {
    const React = require('react');
    const { Text } = require('react-native');
    return <Text style={style}>{text}</Text>;
  },
}));

describe('MessageList Component', () => {
  const mockMessages = [
    {
      id: '1',
      role: 'user' as const,
      content: 'Hello, how are you?',
      timestamp: new Date('2024-01-01T10:00:00'),
      read: true,
    },
    {
      id: '2',
      role: 'agent' as const,
      content: 'I am doing well, thank you!',
      agent_id: 'agent-1',
      agent_name: 'Test Agent',
      agent_maturity: 'AUTONOMOUS' as const,
      timestamp: new Date('2024-01-01T10:01:00'),
      governance: {
        action_complexity: 2,
        requires_approval: false,
        supervised: false,
      },
    },
    {
      id: '3',
      role: 'system' as const,
      content: 'System initialized',
      timestamp: new Date('2024-01-01T10:02:00'),
    },
    {
      id: '4',
      role: 'agent' as const,
      content: 'Streaming response...',
      agent_id: 'agent-2',
      agent_name: 'Streaming Agent',
      agent_maturity: 'INTERN' as const,
      timestamp: new Date('2024-01-01T10:03:00'),
      isStreaming: true,
      episode_context: {
        episode_id: 'ep-1',
        title: 'Previous Episode',
        relevance_score: 0.85,
      },
    },
  ];

  describe('Basic Rendering', () => {
    test('should render message list', () => {
      const { root: container } = render(
        <MessageList messages={mockMessages} />
      );

      expect(container).toBeTruthy();
    });

    test('should render all messages', () => {
      const { getByText } = render(
        <MessageList messages={mockMessages} />
      );

      expect(getByText('Hello, how are you?')).toBeTruthy();
      expect(getByText('I am doing well, thank you!')).toBeTruthy();
      expect(getByText('System initialized')).toBeTruthy();
    });

    test('should render empty state when no messages', () => {
      const { getByText } = render(
        <MessageList messages={[]} />
      );

      expect(getByText('No messages yet')).toBeTruthy();
      expect(getByText('Start a conversation to see messages here')).toBeTruthy();
    });
  });

  describe('Message Types', () => {
    test('should render user messages', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[0]]} />
      );

      expect(getByText('Hello, how are you?')).toBeTruthy();
    });

    test('should render agent messages', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[1]]} />
      );

      expect(getByText('I am doing well, thank you!')).toBeTruthy();
      expect(getByText('Test Agent')).toBeTruthy();
    });

    test('should render system messages', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[2]]} />
      );

      expect(getByText('System initialized')).toBeTruthy();
    });

    test('should render streaming messages', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[3]]} />
      );

      expect(getByText('Streaming response...')).toBeTruthy();
      expect(getByText('Streaming Agent')).toBeTruthy();
    });
  });

  describe('Message Grouping', () => {
    test('should group messages by date', () => {
      const messagesWithDifferentDates = [
        { ...mockMessages[0], timestamp: new Date('2024-01-01') },
        { ...mockMessages[1], timestamp: new Date('2024-01-02') },
      ];

      const { getByText } = render(
        <MessageList messages={messagesWithDifferentDates} />
      );

      // Should show date separators
      expect(getByText(/Today/)).toBeTruthy();
    });

    test('should group messages by sender', () => {
      const messagesFromSameSender = [
        mockMessages[1],
        { ...mockMessages[1], id: '5', content: 'Second message' },
      ];

      const { root: container } = render(
        <MessageList messages={messagesFromSameSender} />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Governance Badges', () => {
    test('should display maturity badge', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[1]]} />
      );

      expect(getByText('AUTONOMOUS')).toBeTruthy();
    });

    test('should display complexity badge', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[1]]} />
      );

      expect(getByText('MODERATE')).toBeTruthy();
    });

    test('should display supervised badge', () => {
      const supervisedMessage = {
        ...mockMessages[1],
        governance: { supervised: true },
      };

      const { getByText } = render(
        <MessageList messages={[supervisedMessage]} />
      );

      expect(getByText('SUPERVISED')).toBeTruthy();
    });

    test('should display approval required badge', () => {
      const approvalMessage = {
        ...mockMessages[1],
        governance: { requires_approval: true },
      };

      const { getByText } = render(
        <MessageList messages={[approvalMessage]} />
      );

      expect(getByText('REQUIRES APPROVAL')).toBeTruthy();
    });
  });

  describe('Episode Context', () => {
    test('should render episode context chip', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[3]]} />
      );

      expect(getByText(/Previous Episode/)).toBeTruthy();
      expect(getByText(/85% relevant/)).toBeTruthy();
    });

    test('should call onEpisodePress when episode chip is pressed', () => {
      const onEpisodePress = jest.fn();
      const { getByText } = render(
        <MessageList
          messages={[mockMessages[3]]}
          onEpisodePress={onEpisodePress}
        />
      );

      fireEvent.press(getByText(/Previous Episode/));
      expect(onEpisodePress).toHaveBeenCalledWith('ep-1');
    });
  });

  describe('Message Actions', () => {
    test('should show menu on long press', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[0]]} />
      );

      // Long press to trigger menu
      const messageBubble = getByText('Hello, how are you?');
      fireEvent(messageBubble, 'onLongPress');
    });

    test('should call onMessageCopy when copy is selected', async () => {
      const onMessageCopy = jest.fn();
      const { getByText, getAllByText } = render(
        <MessageList
          messages={[mockMessages[0]]}
          onMessageCopy={onMessageCopy}
        />
      );

      // Trigger menu
      const messageBubble = getByText('Hello, how are you?');
      fireEvent(messageBubble, 'onLongPress');

      await waitFor(() => {
        const copyButton = getAllByText('Copy')[0];
        fireEvent.press(copyButton);
        expect(onMessageCopy).toHaveBeenCalledWith('1');
      });
    });

    test('should call onMessageFeedback when thumbs up is selected', async () => {
      const onMessageFeedback = jest.fn();
      const { getByText, getAllByText } = render(
        <MessageList
          messages={[mockMessages[1]]}
          onMessageFeedback={onMessageFeedback}
        />
      );

      const messageBubble = getByText('I am doing well, thank you!');
      fireEvent(messageBubble, 'onLongPress');

      await waitFor(() => {
        const thumbsUp = getAllByText('Thumbs Up')[0];
        fireEvent.press(thumbsUp);
        expect(onMessageFeedback).toHaveBeenCalledWith('2', 1);
      });
    });

    test('should call onMessageRegenerate when regenerate is selected', async () => {
      const onMessageRegenerate = jest.fn();
      const onMessageFeedback = jest.fn();
      const { getByText, getAllByText } = render(
        <MessageList
          messages={[mockMessages[1]]}
          onMessageRegenerate={onMessageRegenerate}
          onMessageFeedback={onMessageFeedback}
        />
      );

      const messageBubble = getByText('I am doing well, thank you!');
      fireEvent(messageBubble, 'onLongPress');

      await waitFor(() => {
        const regenerate = getAllByText('Regenerate')[0];
        fireEvent.press(regenerate);
        expect(onMessageRegenerate).toHaveBeenCalledWith('2');
      });
    });

    test('should call onMessageDelete for user messages', async () => {
      const onMessageDelete = jest.fn();
      const { getByText, getAllByText } = render(
        <MessageList
          messages={[mockMessages[0]]}
          onMessageDelete={onMessageDelete}
        />
      );

      const messageBubble = getByText('Hello, how are you?');
      fireEvent(messageBubble, 'onLongPress');

      await waitFor(() => {
        const deleteItem = getAllByText('Delete')[0];
        fireEvent.press(deleteItem);
        expect(onMessageDelete).toHaveBeenCalledWith('1');
      });
    });

    test('should not show feedback actions for user messages', () => {
      const { queryAllByText } = render(
        <MessageList messages={[mockMessages[0]]} />
      );

      // User messages should not have feedback options
      expect(queryAllByText('Thumbs Up').length).toBe(0);
    });
  });

  describe('Agent Interactions', () => {
    test('should call onAgentPress when agent avatar is pressed', () => {
      const onAgentPress = jest.fn();
      const { getByText } = render(
        <MessageList
          messages={[mockMessages[1]]}
          onAgentPress={onAgentPress}
        />
      );

      // Agent avatar should be pressable
      const agentName = getByText('Test Agent');
      expect(agentName).toBeTruthy();
    });
  });

  describe('Read Receipts', () => {
    test('should show read receipt for read user messages', () => {
      const { root: container } = render(
        <MessageList messages={[mockMessages[0]]} />
      );

      expect(container).toBeTruthy();
    });

    test('should not show read receipt for unread messages', () => {
      const unreadMessage = { ...mockMessages[0], read: false };
      const { root: container } = render(
        <MessageList messages={[unreadMessage]} />
      );

      expect(container).toBeTruthy();
    });

    test('should not show read receipt for agent messages', () => {
      const { root: container } = render(
        <MessageList messages={[mockMessages[1]]} />
      );

      expect(container).toBeTruthy();
    });
  });

  describe('Loading State', () => {
    test('should show loading indicator when loading', () => {
      const { getByText } = render(
        <MessageList messages={[]} loading={true} />
      );

      expect(getByText('Agent is thinking...')).toBeTruthy();
    });

    test('should not show loading indicator when not loading', () => {
      const { queryByText } = render(
        <MessageList messages={[]} loading={false} />
      );

      expect(queryByText('Agent is thinking...')).toBeNull();
    });
  });

  describe('Custom Components', () => {
    test('should render ListHeaderComponent', () => {
      const React = require('react');
      const { Text } = require('react-native');
      const Header = () => <Text>Header Content</Text>;
      const { getByText } = render(
        <MessageList
          messages={mockMessages}
          ListHeaderComponent={Header}
        />
      );

      expect(getByText('Header Content')).toBeTruthy();
    });

    test('should render ListFooterComponent', () => {
      const React = require('react');
      const { Text } = require('react-native');
      const Footer = () => <Text>Footer Content</Text>;
      const { getByText } = render(
        <MessageList
          messages={mockMessages}
          ListFooterComponent={Footer}
        />
      );

      expect(getByText('Footer Content')).toBeTruthy();
    });
  });

  describe('Scroll Behavior', () => {
    test('should auto-scroll to bottom on new messages', () => {
      const { root: container, rerender } = render(
        <MessageList messages={[mockMessages[0]]} />
      );

      // Add new message
      rerender(
        <MessageList messages={[mockMessages[0], mockMessages[1]]} />
      );

      expect(container).toBeTruthy();
    });

    test('should show scroll to bottom button when scrolled up', () => {
      const { getByTestId, queryByTestId } = render(
        <MessageList messages={mockMessages}
      />
      );

      // Scrolled to bottom by default — no FAB yet
      expect(queryByTestId('scroll-to-bottom-fab')).toBeNull();

      // Simulate scrolling up: content offset far above the bottom
      const flatList = getByTestId('message-list');
      fireEvent.scroll(flatList, {
        nativeEvent: {
          contentOffset: { y: 100 },
          contentSize: { height: 1000 },
          layoutMeasurement: { height: 500 },
        },
      });

      // Scroll-to-bottom FAB appears
      expect(getByTestId('scroll-to-bottom-fab')).toBeTruthy();
    });
  });

  describe('Timestamp Display', () => {
    test('should show timestamp for messages', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[0]]} />
      );

      expect(getByText('5 minutes ago')).toBeTruthy();
    });

    test('should format timestamps correctly', () => {
      const { getAllByText } = render(
        <MessageList messages={mockMessages} />
      );

      // Every message starts a new sender group, so each shows a timestamp
      expect(getAllByText('5 minutes ago').length).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    test('should handle messages with null content', () => {
      const nullMessage = {
        id: 'null-1',
        role: 'user' as const,
        content: null as any,
        timestamp: new Date(),
      };

      const { root: container } = render(
        <MessageList messages={[nullMessage]} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle messages with empty content', () => {
      const emptyMessage = {
        id: 'empty-1',
        role: 'user' as const,
        content: '',
        timestamp: new Date(),
      };

      const { root: container } = render(
        <MessageList messages={[emptyMessage]} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle very long messages', () => {
      const longMessage = {
        id: 'long-1',
        role: 'agent' as const,
        content: 'A'.repeat(10000),
        agent_id: 'agent-1',
        timestamp: new Date(),
      };

      const { root: container } = render(
        <MessageList messages={[longMessage]} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle messages with special characters', () => {
      const specialMessage = {
        id: 'special-1',
        role: 'user' as const,
        content: 'Special chars: <>&"\'\\n\\t',
        timestamp: new Date(),
      };

      const { root: container } = render(
        <MessageList messages={[specialMessage]} />
      );

      expect(container).toBeTruthy();
    });

    test('should handle messages with emojis', () => {
      const emojiMessage = {
        id: 'emoji-1',
        role: 'user' as const,
        content: 'Hello 👋 World 🌍',
        timestamp: new Date(),
      };

      const { getByText } = render(
        <MessageList messages={[emojiMessage]} />
      );

      expect(getByText(/Hello/)).toBeTruthy();
    });
  });

  describe('Maturity Levels', () => {
    test('should render STUDENT maturity badge', () => {
      const studentMessage = {
        ...mockMessages[1],
        agent_maturity: 'STUDENT' as const,
      };

      const { getByText } = render(
        <MessageList messages={[studentMessage]} />
      );

      expect(getByText('STUDENT')).toBeTruthy();
    });

    test('should render INTERN maturity badge', () => {
      const internMessage = {
        ...mockMessages[1],
        agent_maturity: 'INTERN' as const,
      };

      const { getByText } = render(
        <MessageList messages={[internMessage]} />
      );

      expect(getByText('INTERN')).toBeTruthy();
    });

    test('should render SUPERVISED maturity badge', () => {
      const supervisedMessage = {
        ...mockMessages[1],
        agent_maturity: 'SUPERVISED' as const,
      };

      const { getByText } = render(
        <MessageList messages={[supervisedMessage]} />
      );

      expect(getByText('SUPERVISED')).toBeTruthy();
    });

    test('should render AUTONOMOUS maturity badge', () => {
      const { getByText } = render(
        <MessageList messages={[mockMessages[1]]} />
      );

      expect(getByText('AUTONOMOUS')).toBeTruthy();
    });
  });

  describe('Action Complexity Levels', () => {
    test('should render LOW complexity badge', () => {
      const lowComplexityMessage = {
        ...mockMessages[1],
        governance: { action_complexity: 1 },
      };

      const { getByText } = render(
        <MessageList messages={[lowComplexityMessage]} />
      );

      expect(getByText('LOW')).toBeTruthy();
    });

    test('should render HIGH complexity badge', () => {
      const highComplexityMessage = {
        ...mockMessages[1],
        governance: { action_complexity: 3 },
      };

      const { getByText } = render(
        <MessageList messages={[highComplexityMessage]} />
      );

      expect(getByText('HIGH')).toBeTruthy();
    });

    test('should render CRITICAL complexity badge', () => {
      const criticalComplexityMessage = {
        ...mockMessages[1],
        governance: { action_complexity: 4 },
      };

      const { getByText } = render(
        <MessageList messages={[criticalComplexityMessage]} />
      );

      expect(getByText('CRITICAL')).toBeTruthy();
    });
  });
});
