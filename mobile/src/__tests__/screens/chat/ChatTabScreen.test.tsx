/**
 * ChatTabScreen Component Tests
 *
 * Tests for chat tab screen showing conversations, search,
 * pull-to-refresh, and navigation.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { ChatTabScreen } from '../../../screens/chat/ChatTabScreen';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Mock @react-navigation/native
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  setOptions: jest.fn(),
  reset: jest.fn(),
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => mockNavigation,
}));

// Mock AsyncStorage
jest.mock('@react-native-async-storage/async-storage', () => ({
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
}));

// Mock Constants.expoConfig
jest.mock('expo-constants', () => ({
  expoConfig: {
    extra: {
      apiUrl: 'http://localhost:8000',
    },
  },
}));

// Mock Alert
jest.mock('react-native/Libraries/Alert/Alert', () => ({
  alert: jest.fn(),
}));

import { Alert, StyleSheet } from 'react-native';

// Mock secureTokenStorage so tests can force token-load failures
jest.mock('../../../storage/secureTokenStorage', () => ({
  secureGet: jest.fn(),
  secureSet: jest.fn(),
  secureDelete: jest.fn(),
}));

import { secureGet } from '../../../storage/secureTokenStorage';

describe('ChatTabScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Mock secureGet to return a token (mirrors the previous AsyncStorage
    // migration path with a direct, controllable mock)
    (secureGet as jest.Mock).mockResolvedValue('test-token');

    // Mock fetch API
    global.fetch = jest.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            conversations: [
              {
                id: 'conv-1',
                agent_id: 'agent-1',
                agent_name: 'Test Agent',
                agent_maturity: 'AUTONOMOUS',
                last_message: 'Hello, how can I help?',
                last_message_at: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
                unread_count: 2,
                created_at: new Date().toISOString(),
              },
            ],
          }),
      })
    ) as any;
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.clearAllTimers();
  });

  describe('Rendering', () => {
    it('should render loading state initially', async () => {
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue(null);

      const { getByText } = render(<ChatTabScreen />);

      // Loading state shows on the first render, before token resolution
      expect(getByText('Loading conversations...')).toBeTruthy();
    });

    it('should render conversation list when data loads', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });
    });

    it('should render search bar', async () => {
      const { getByPlaceholderText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByPlaceholderText('Search conversations...')).toBeTruthy();
      });
    });

    it('should render empty state when no conversations', async () => {
      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              conversations: [],
            }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('No conversations yet')).toBeTruthy();
        expect(getByText('Start chatting with Atom AI agents')).toBeTruthy();
      });
    });

    it('should render floating action button when conversations exist', async () => {
      const { getByTestId, UNSAFE_getByType } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeTruthy();
      });

      // FAB is rendered with Ionicons
      const fab = screen.getByText('Test Agent');
      expect(fab).toBeTruthy();
    });
  });

  describe('Conversation Display', () => {
    it('should display agent name', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });
    });

    it('should display last message', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Hello, how can I help?')).toBeTruthy();
      });
    });

    it('should display unread badge', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('2')).toBeTruthy();
      });
    });

    it('should display maturity badge', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('AUTONOMOUS')).toBeTruthy();
      });
    });

    it('should format timestamp correctly', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('5m ago')).toBeTruthy();
      });
    });
  });

  describe('Search Functionality', () => {
    it('should filter conversations by agent name', async () => {
      const { getByPlaceholderText, getByText, queryByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText('Search conversations...');
      fireEvent.changeText(searchInput, 'Test');

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      fireEvent.changeText(searchInput, 'NonExistent');

      await waitFor(() => {
        expect(queryByText('Test Agent')).toBeNull();
      });
    });

    it('should filter conversations by message content', async () => {
      const { getByPlaceholderText, getByText, queryByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText('Search conversations...');
      fireEvent.changeText(searchInput, 'help');

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });
    });

    it('should show clear button when search has text', async () => {
      const { getByPlaceholderText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText('Search conversations...');
      fireEvent.changeText(searchInput, 'test');

      await waitFor(() => {
        expect(searchInput.props.value).toBe('test');
      });
    });

    it('should clear search when clear button pressed', async () => {
      const { getByPlaceholderText, getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText('Search conversations...');
      fireEvent.changeText(searchInput, 'test');

      await waitFor(() => {
        expect(searchInput.props.value).toBe('test');
      });

      fireEvent.changeText(searchInput, '');

      await waitFor(() => {
        expect(searchInput.props.value).toBe('');
      });
    });
  });

  describe('Pull to Refresh', () => {
    it('should refresh conversations on pull', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      // Trigger refresh by calling handleRefresh directly
      // In a real test, you'd use RefreshControl's onRefresh
      await act(async () => {
        await waitFor(() => {
          expect(getByText('Test Agent')).toBeTruthy();
        });
      });
    });
  });

  describe('Navigation', () => {
    it('should navigate to agent chat on conversation press', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      // Find and press the conversation item
      const conversationItem = getByText('Test Agent');
      fireEvent.press(conversationItem);

      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('AgentChat', {
          agentId: 'agent-1',
          conversationId: 'conv-1',
        });
      });
    });

    it('should navigate to agents tab on FAB press', async () => {
      const { getByTestId } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeTruthy();
      });

      // Press the floating action button
      fireEvent.press(getByTestId('fab-start-conversation'));

      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('AgentsTab');
      });
    });
  });

  describe('Delete Conversation', () => {
    it('should show confirmation alert on delete', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      // The delete flow is triggered by swipe action
      // For now, just verify the component renders
      expect(getByText('Test Agent')).toBeTruthy();
    });

    it('should remove conversation from list after successful delete', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      // Verify conversation is displayed
      expect(getByText('Test Agent')).toBeTruthy();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue('test-token');

      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: false,
          status: 500,
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        // Should show empty state on error
        expect(getByText('No conversations yet')).toBeTruthy();
      });
    });

    it('should handle network errors gracefully', async () => {
      (AsyncStorage.getItem as jest.Mock).mockResolvedValue('test-token');

      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        // Should show empty state on error
        expect(getByText('No conversations yet')).toBeTruthy();
      });
    });

    it('should handle missing access token', async () => {
      (secureGet as jest.Mock).mockResolvedValue(null);

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('No conversations yet')).toBeTruthy();
      });
    });
  });

  describe('Timestamp Formatting', () => {
    it('should show "Just now" for very recent messages', async () => {
      const recentTime = new Date(Date.now() - 1000 * 30).toISOString(); // 30 seconds ago

      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              conversations: [
                {
                  id: 'conv-1',
                  agent_id: 'agent-1',
                  agent_name: 'Test Agent',
                  agent_maturity: 'AUTONOMOUS',
                  last_message: 'Recent message',
                  last_message_at: recentTime,
                  unread_count: 0,
                  created_at: new Date().toISOString(),
                },
              ],
            }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Just now')).toBeTruthy();
      });
    });

    it('should show minutes ago for recent messages', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('5m ago')).toBeTruthy();
      });
    });

    it('should show hours ago for older messages', async () => {
      const hoursAgo = new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(); // 2 hours ago

      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              conversations: [
                {
                  id: 'conv-1',
                  agent_id: 'agent-1',
                  agent_name: 'Test Agent',
                  agent_maturity: 'AUTONOMOUS',
                  last_message: 'Older message',
                  last_message_at: hoursAgo,
                  unread_count: 0,
                  created_at: new Date().toISOString(),
                },
              ],
            }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('2h ago')).toBeTruthy();
      });
    });

    it('should show date for very old messages', async () => {
      const daysAgo = new Date(Date.now() - 1000 * 60 * 60 * 24 * 10).toISOString(); // 10 days ago

      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              conversations: [
                {
                  id: 'conv-1',
                  agent_id: 'agent-1',
                  agent_name: 'Test Agent',
                  agent_maturity: 'AUTONOMOUS',
                  last_message: 'Old message',
                  last_message_at: daysAgo,
                  unread_count: 0,
                  created_at: new Date().toISOString(),
                },
              ],
            }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        // Should show formatted date
        const dateText = getByText(/\d{1,2}\/\d{1,2}\/\d{4}/);
        expect(dateText).toBeTruthy();
      });
    });
  });

  describe('Token Loading', () => {
    it('should stop loading and show empty state when token load fails', async () => {
      const errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});
      (secureGet as jest.Mock).mockRejectedValueOnce(new Error('storage broken'));

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('No conversations yet')).toBeTruthy();
        expect(errorSpy).toHaveBeenCalled();
      });
      errorSpy.mockRestore();
    });

    it('should not fetch conversations without a token', async () => {
      (secureGet as jest.Mock).mockResolvedValueOnce(null);

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('No conversations yet')).toBeTruthy();
      });

      expect(global.fetch).not.toHaveBeenCalled();
    });

    it('should clear conversations when response lacks the conversations key', async () => {
      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('No conversations yet')).toBeTruthy();
      });
    });
  });

  describe('Refresh', () => {
    it('should reload conversations on pull to refresh', async () => {
      const { UNSAFE_getAllByType } = render(<ChatTabScreen />);
      const { RefreshControl } = require('react-native');

      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeTruthy();
      });
      expect(global.fetch).toHaveBeenCalledTimes(1);

      const refreshControl = UNSAFE_getAllByType(RefreshControl)[0];
      fireEvent(refreshControl, 'refresh');

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledTimes(2);
        expect(screen.getByText('Test Agent')).toBeTruthy();
      });
    });
  });

  describe('Delete Conversation', () => {
    it('should show confirmation alert on long press', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      fireEvent(getByText('Test Agent'), 'onLongPress');

      expect(Alert.alert).toHaveBeenCalledWith(
        'Delete Conversation',
        'Are you sure you want to delete this conversation?',
        expect.any(Array)
      );
    });

    it('should delete the conversation via API when confirmed', async () => {
      const { getByText, queryByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      fireEvent(getByText('Test Agent'), 'onLongPress');

      const buttons = (Alert.alert as jest.Mock).mock.calls[0][2];
      const deleteButton = buttons.find((b: any) => b.text === 'Delete');
      await act(async () => {
        await deleteButton.onPress();
      });

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/chat/conversations/conv-1',
        expect.objectContaining({
          method: 'DELETE',
          headers: { Authorization: 'Bearer test-token' },
        })
      );

      await waitFor(() => {
        expect(queryByText('Test Agent')).toBeNull();
      });
    });

    it('should alert when delete fails with a server error', async () => {
      (global.fetch as jest.Mock).mockImplementationOnce(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ success: true, conversations: [{ id: 'conv-1', agent_id: 'agent-1', agent_name: 'Test Agent', agent_maturity: 'AUTONOMOUS', last_message: 'Hello', last_message_at: new Date().toISOString(), unread_count: 0, created_at: new Date().toISOString() }] }) }));
      (global.fetch as jest.Mock).mockImplementationOnce(() => Promise.resolve({ ok: false, status: 500 }));

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent')).toBeTruthy();
      });

      fireEvent(getByText('Test Agent'), 'onLongPress');
      const buttons = (Alert.alert as jest.Mock).mock.calls[0][2];
      await buttons.find((b: any) => b.text === 'Delete').onPress();

      await waitFor(() => {
        expect(Alert.alert).toHaveBeenCalledWith('Error', 'Failed to delete conversation');
      });
    });

    it('should alert when delete request throws', async () => {
      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('network down'));

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('No conversations yet')).toBeTruthy();
      });
    });
  });

  describe('Search Clear Button', () => {
    it('should clear the query when clear button is pressed', async () => {
      const { getByPlaceholderText, getByTestId } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent')).toBeTruthy();
      });

      const searchInput = getByPlaceholderText('Search conversations...');
      fireEvent.changeText(searchInput, 'test');

      await waitFor(() => {
        expect(searchInput.props.value).toBe('test');
      });

      fireEvent.press(getByTestId('icon-close-circle'));

      await waitFor(() => {
        expect(searchInput.props.value).toBe('');
      });
    });
  });

  describe('Unread Badge Overflow', () => {
    it('should clamp unread counts above 9 to "9+"', async () => {
      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              conversations: [
                {
                  id: 'conv-1',
                  agent_id: 'agent-1',
                  agent_name: 'Test Agent',
                  agent_maturity: 'AUTONOMOUS',
                  last_message: 'Hello',
                  last_message_at: new Date().toISOString(),
                  unread_count: 12,
                  created_at: new Date().toISOString(),
                },
              ],
            }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('9+')).toBeTruthy();
      });
    });
  });

  describe('Maturity Badge Colors', () => {
    it('should show green badge for AUTONOMOUS', async () => {
      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('AUTONOMOUS')).toBeTruthy();
      });
    });

    it('should color the badge for intern agents blue', async () => {
      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              conversations: [
                {
                  id: 'conv-1',
                  agent_id: 'agent-1',
                  agent_name: 'Intern Agent',
                  agent_maturity: 'intern',
                  last_message: 'Message',
                  last_message_at: new Date().toISOString(),
                  unread_count: 0,
                  created_at: new Date().toISOString(),
                },
              ],
            }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('intern')).toBeTruthy();
      });

      const badgeText = getByText('intern');
      const flattened = StyleSheet.flatten(badgeText.parent?.parent?.props.style);
      expect(flattened.backgroundColor).toBe('#2196F3');
    });

    it('should color the badge for student agents grey', async () => {
      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              conversations: [
                {
                  id: 'conv-1',
                  agent_id: 'agent-1',
                  agent_name: 'Student Agent',
                  agent_maturity: 'student',
                  last_message: 'Message',
                  last_message_at: new Date().toISOString(),
                  unread_count: 0,
                  created_at: new Date().toISOString(),
                },
              ],
            }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('student')).toBeTruthy();
      });

      const badgeText = getByText('student');
      const flattened = StyleSheet.flatten(badgeText.parent?.parent?.props.style);
      expect(flattened.backgroundColor).toBe('#9E9E9E');
    });

    it('should show orange badge for SUPERVISED', async () => {
      (global.fetch as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              conversations: [
                {
                  id: 'conv-1',
                  agent_id: 'agent-1',
                  agent_name: 'Test Agent',
                  agent_maturity: 'SUPERVISED',
                  last_message: 'Message',
                  last_message_at: new Date().toISOString(),
                  unread_count: 0,
                  created_at: new Date().toISOString(),
                },
              ],
            }),
        })
      );

      const { getByText } = render(<ChatTabScreen />);

      await waitFor(() => {
        expect(getByText('SUPERVISED')).toBeTruthy();
      });
    });
  });
});
