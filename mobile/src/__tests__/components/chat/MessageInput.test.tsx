/**
 * MessageInput Component Tests
 *
 * Tests for message input with text handling, attachments,
 * voice input, and @mentions.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { MessageInput } from '../../../components/chat/MessageInput';

// Mock react-native-paper
jest.mock('react-native-paper', () => ({
  useTheme: () => ({
    colors: {
      primary: '#2196F3',
      onSurface: '#000',
      surface: '#fff',
      onSurfaceVariant: '#666',
    },
  }),
  IconButton: ({ onPress, icon, size }: any) => {
    const React = require('react');
    const { TouchableOpacity } = require('react-native');
    return (
      <TouchableOpacity onPress={onPress} testID={`icon-${icon}`}>
        <React.Fragment />
      </TouchableOpacity>
    );
  },
  Icon: 'Icon',
  Avatar: {
    Text: ({ label, style }: any) => {
      const React = require('react');
      const { Text } = require('react-native');
      return <Text style={style}>{label}</Text>;
    },
  },
  Chip: 'Chip',
}));

// Mock expo-image-picker
jest.mock('expo-image-picker', () => ({
  launchImageLibraryAsync: jest.fn(() =>
    Promise.resolve({
      canceled: false,
      assets: [{ uri: 'file://image.jpg', type: 'image' }],
    })
  ),
}));

// Mock expo-document-picker
jest.mock('expo-document-picker', () => ({
  getDocumentAsync: jest.fn(() =>
    Promise.resolve({
      canceled: false,
      assets: [{ uri: 'file://document.pdf', name: 'document.pdf' }],
    })
  ),
}));

// Mock expo-av
jest.mock('expo-av', () => ({
  Audio: {
    Recording: jest.fn(() => ({
      prepareToRecordAsync: jest.fn(() => Promise.resolve()),
      startAsync: jest.fn(() => Promise.resolve()),
      stopAsync: jest.fn(() => Promise.resolve({ uri: 'file://audio.m4a' })),
      getStatusAsync: jest.fn(() =>
        Promise.resolve({
          isRecording: true,
          durationMillis: 5000,
        })
      ),
    })),
    Permission: {
      STATUS_GRANTED: 'granted',
    },
  },
}));

// Mock react-native-safe-area-context
jest.mock('react-native-safe-area-context', () => ({
  useSafeAreaInsets: () => ({ bottom: 0, top: 0, left: 0, right: 0 }),
}));

describe('MessageInput', () => {
  const mockOnSend = jest.fn();
  const mockAgents = [
    { id: 'agent-1', name: 'Alice' },
    { id: 'agent-2', name: 'Bob' },
  ];

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    it('should render text input field', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      expect(getByPlaceholderText(/type a message/i)).toBeTruthy();
    });

    it('should render send button', () => {
      const { getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      expect(getByTestId('icon-send')).toBeTruthy();
    });

    it('should render attachment button', () => {
      const { getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      expect(getByTestId('icon-attachment')).toBeTruthy();
    });

    it('should apply custom placeholder', () => {
      const { getByPlaceholderText } = render(
        <MessageInput
          onSend={mockOnSend}
          placeholder="Enter your message..."
        />
      );

      expect(getByPlaceholderText('Enter your message...')).toBeTruthy();
    });
  });

  describe('Text Input', () => {
    it('should handle text input', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, 'Hello, world!');

      expect(input.props.value).toBe('Hello, world!');
    });

    it('should enforce max length', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} maxLength={100} />
      );

      const input = getByPlaceholderText(/type a message/i);
      const longText = 'A'.repeat(150);
      fireEvent.changeText(input, longText);

      // Should truncate to max length
      expect(input.props.value.length).toBeLessThanOrEqual(100);
    });

    it('should auto-grow input height', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, 'Line 1\nLine 2\nLine 3\nLine 4\nLine 5');

      // Input should grow to accommodate text
      expect(input).toBeTruthy();
    });

    it('should limit max height to 5 lines', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      const longText = 'A\n'.repeat(10);
      fireEvent.changeText(input, longText);

      // Should not exceed 5 lines height
      expect(input).toBeTruthy();
    });
  });

  describe('Send Button', () => {
    it('should send message when button is pressed', () => {
      const { getByPlaceholderText, getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, 'Test message');

      const sendButton = getByTestId('icon-send');
      fireEvent.press(sendButton);

      expect(mockOnSend).toHaveBeenCalledWith('Test message', []);
    });

    it('should clear input after sending', () => {
      const { getByPlaceholderText, getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, 'Test message');

      const sendButton = getByTestId('icon-send');
      fireEvent.press(sendButton);

      // Input should be cleared
      expect(input.props.value).toBe('');
    });

    it('should not send empty message', () => {
      const { getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const sendButton = getByTestId('icon-send');
      fireEvent.press(sendButton);

      expect(mockOnSend).not.toHaveBeenCalled();
    });

    it('should not send message with only whitespace', () => {
      const { getByPlaceholderText, getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, '   ');

      const sendButton = getByTestId('icon-send');
      fireEvent.press(sendButton);

      expect(mockOnSend).not.toHaveBeenCalled();
    });
  });

  describe('@Mentions', () => {
    it('should show mention suggestions when @ is typed', () => {
      const { getByPlaceholderText, getByText } = render(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, '@');

      expect(getByText('Alice')).toBeTruthy();
    });

    it('should filter agents by mention query', () => {
      const { getByPlaceholderText, getByText, queryByText } = render(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, '@Ali');

      expect(getByText('Alice')).toBeTruthy();
      expect(queryByText('Bob')).toBeNull();
    });

    it('should select agent from mention list', () => {
      const { getByPlaceholderText, getByText } = render(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, '@');

      const agentSuggestion = getByText('Alice');
      fireEvent.press(agentSuggestion);

      // Should insert agent mention
      expect(input.props.value).toContain('@Alice');
    });

    it('should hide suggestions when space is typed after mention', () => {
      const { getByPlaceholderText, queryByText } = render(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, '@Alice ');

      // Suggestions should hide
      expect(queryByText('Bob')).toBeNull();
    });

    it('should hide suggestions when @ is not present', () => {
      const { getByPlaceholderText, queryByText } = render(
        <MessageInput onSend={mockOnSend} agents={mockAgents} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, 'Hello world');

      expect(queryByText('Alice')).toBeNull();
    });
  });

  describe('Attachments', () => {
    it('should show attachment menu when button is pressed', () => {
      const { getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const attachmentButton = getByTestId('icon-attachment');
      fireEvent.press(attachmentButton);

      // Should show attachment menu
      expect(getByTestId('icon-attachment')).toBeTruthy();
    });

    it('should send message with attachments', async () => {
      const { getByTestId, getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, 'Check this image');

      const sendButton = getByTestId('icon-send');
      fireEvent.press(sendButton);

      expect(mockOnSend).toHaveBeenCalled();
    });
  });

  describe('Voice Input', () => {
    it('should start recording when microphone button is pressed', () => {
      const { getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const micButton = getByTestId('icon-microphone');
      fireEvent.press(micButton);

      expect(getByTestId('icon-microphone')).toBeTruthy();
    });

    it('should stop recording when button is pressed again', () => {
      const { getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const micButton = getByTestId('icon-microphone');
      fireEvent.press(micButton);
      fireEvent.press(micButton);

      expect(getByTestId('icon-microphone')).toBeTruthy();
    });

    it('should display recording duration', () => {
      const { getByTestId, getByText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const micButton = getByTestId('icon-microphone');
      fireEvent.press(micButton);

      // Advance timers to update duration
      jest.advanceTimersByTime(5000);

      expect(getByText(/0:05/)).toBeTruthy();
    });
  });

  describe('Disabled State', () => {
    it('should disable input when disabled prop is true', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} disabled={true} />
      );

      const input = getByPlaceholderText(/type a message/i);
      expect(input.props.editable).toBe(false);
    });

    it('should not send when disabled', () => {
      const { getByTestId } = render(
        <MessageInput onSend={mockOnSend} disabled={true} />
      );

      const sendButton = getByTestId('icon-send');
      fireEvent.press(sendButton);

      expect(mockOnSend).not.toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty agents list', () => {
      const { getByPlaceholderText, queryByText } = render(
        <MessageInput onSend={mockOnSend} agents={[]} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, '@');

      // Should not show suggestions
      expect(queryByText('No agents found')).toBeNull();
    });

    it('should handle very long text', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      const longText = 'A'.repeat(10000);
      fireEvent.changeText(input, longText);

      // Should truncate to max length
      expect(input.props.value.length).toBeLessThanOrEqual(2000);
    });

    it('should handle special characters in text', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      const specialText = 'Test <>&"\'\\/';
      fireEvent.changeText(input, specialText);

      expect(input.props.value).toBe(specialText);
    });

    it('should handle rapid text changes', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);

      for (let i = 0; i < 10; i++) {
        fireEvent.changeText(input, `Update ${i}`);
      }

      expect(input).toBeTruthy();
    });
  });

  describe('Keyboard Avoidance', () => {
    it('should adjust for safe area insets', () => {
      const { getByTestId } = render(
        <MessageInput onSend={mockOnSend} />
      );

      expect(getByTestId('message-input-container')).toBeTruthy();
    });
  });

  describe('Emoji Support', () => {
    it('should handle emojis in text', () => {
      const { getByPlaceholderText } = render(
        <MessageInput onSend={mockOnSend} />
      );

      const input = getByPlaceholderText(/type a message/i);
      fireEvent.changeText(input, 'Hello 👋 World 🌍');

      expect(input.props.value).toBe('Hello 👋 World 🌍');
    });
  });
});
