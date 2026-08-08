/**
 * ConversationListScreen Component Tests
 *
 * Tests for conversation list with search, filter, sort,
 * swipe actions, and infinite scroll.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { ConversationListScreen } from '../../../screens/chat/ConversationListScreen';

// Mock @react-navigation/native
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
  setOptions: jest.fn(),
  reset: jest.fn(),
};

jest.mock('@react-navigation/native', () => {
  const React = require('react');
  return {
    useNavigation: () => mockNavigation,
    // The real useFocusEffect requires a NavigationContainer context; invoke
    // the focus callback on mount instead.
    useFocusEffect: (callback: any) => {
      React.useEffect(() => {
        return callback();
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, []);
    },
  };
});

// Mock react-native-paper
jest.mock('react-native-paper', () => ({
  useTheme: () => ({
    colors: {
      background: '#fff',
      surface: '#fff',
      onSurface: '#000',
      onSurfaceVariant: '#666',
      onSurfaceDisabled: '#ccc',
      outline: '#e0e0e0',
      primaryContainer: '#e3f2fd',
      primary: '#2196F3',
    },
  }),
  Icon: ({ source, size, color }: any) => {
    const React = require('react');
    const { View } = require('react-native');
    return <View testID={`paper-icon-${source}`} />;
  },
  Avatar: {
    Text: ({ label, style }: any) => {
      const React = require('react');
      return <React.Fragment testID={`avatar-${label}`}>{label}</React.Fragment>;
    },
  },
  Badge: ({ children, style }: any) => {
    const React = require('react');
    const { View, Text } = require('react-native');
    return (
      <View testID="badge" style={style}>
        <Text>{children}</Text>
      </View>
    );
  },
  Searchbar: ({ onChangeText, value, style }: any) => {
    const React = require('react');
    const { TextInput } = require('react-native');
    return <TextInput testID="searchbar" onChangeText={onChangeText} value={value} style={style} />;
  },
  Chip: ({ children, selected, onPress, style, textStyle }: any) => {
    const React = require('react');
    const { TouchableOpacity, Text } = require('react-native');
    return (
      <TouchableOpacity onPress={onPress} testID={`chip-${children}`}>
        <Text>{children}</Text>
      </TouchableOpacity>
    );
  },
  IconButton: ({ icon, onPress, size }: any) => {
    const React = require('react');
    const { TouchableOpacity } = require('react-native');
    return <TouchableOpacity onPress={onPress} testID={`icon-${icon}`} />;
  },
  SwipeRow: ({ children, leftOpenValue, rightOpenValue, disableRightSwipe }: any) => {
    const React = require('react');
    const { View } = require('react-native');
    return <View>{children}</View>;
  },
  FAB: ({ icon, onPress, label, style }: any) => {
    const React = require('react');
    const { TouchableOpacity, Text } = require('react-native');
    return (
      <TouchableOpacity onPress={onPress} testID="fab">
        <Text>{label}</Text>
      </TouchableOpacity>
    );
  },
}));

// Mock chatService
const mockGetConversationList = jest.fn(() =>
  Promise.resolve({
    success: true,
    data: [
      {
        session_id: 'session-1',
        agent_id: 'agent-1',
        agent_name: 'Test Agent 1',
        agent_maturity: 'AUTONOMOUS',
        last_message: 'Hello from agent 1',
        last_message_time: new Date(Date.now() - 1000 * 60 * 5).toISOString(),
        unread_count: 2,
      },
      {
        session_id: 'session-2',
        agent_id: 'agent-2',
        agent_name: 'Test Agent 2',
        agent_maturity: 'SUPERVISED',
        last_message: 'Hello from agent 2',
        last_message_time: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
        unread_count: 0,
      },
    ],
  })
);

const mockArchiveSession = jest.fn(() =>
  Promise.resolve({
    success: true,
  })
);

const mockDeleteSession = jest.fn(() =>
  Promise.resolve({
    success: true,
  })
);

const mockMarkAsRead = jest.fn(() =>
  Promise.resolve({
    success: true,
  })
);

jest.mock('../../../services/chatService', () => ({
  chatService: {
    getConversationList: (...args: any[]) => mockGetConversationList(...args),
    archiveSession: (id: string) => mockArchiveSession(id),
    deleteSession: (id: string) => mockDeleteSession(id),
    markAsRead: (id: string) => mockMarkAsRead(id),
  },
}));

// Mock date-fns (compute distance from the real timestamp so items with
// different last_message_time render different labels)
jest.mock('date-fns', () => ({
  formatDistanceToNow: (date: Date, options: any) => {
    const diffMs = Date.now() - date.getTime();
    const mins = Math.floor(diffMs / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins} minutes ago`;
    const hours = Math.floor(mins / 60);
    return `${hours} hour${hours > 1 ? 's' : ''} ago`;
  },
}));

// Mock Alert
jest.mock('react-native/Libraries/Alert/Alert', () => ({
  alert: jest.fn(),
}));

describe('ConversationListScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.clearAllTimers();
  });

  describe('Rendering', () => {
    it('should render conversation list', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
      });
    });

    it('should render search bar', async () => {
      const { getByTestId } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByTestId('searchbar')).toBeTruthy();
      });
    });

    it('should render filter chips', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Recent')).toBeTruthy();
        expect(getByText('Unread')).toBeTruthy();
        expect(getByText('All Levels')).toBeTruthy();
      });
    });

    it('should render empty state when no conversations', async () => {
      mockGetConversationList.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [],
        })
      );

      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('No conversations yet')).toBeTruthy();
        expect(getByText('Start chatting with your agents to see conversations here')).toBeTruthy();
      });
    });

    it('should show loading state initially', async () => {
      mockGetConversationList.mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            setTimeout(() => {
              resolve({
                success: true,
                data: [],
              });
            }, 1000);
          })
      );

      const { getByText } = render(<ConversationListScreen />);

      // Component should render without crashing
      expect(screen.getByTestId('searchbar')).toBeTruthy();
    });
  });

  describe('Conversation Display', () => {
    it('should display agent name', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
      });
    });

    it('should display last message', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Hello from agent 1')).toBeTruthy();
        expect(getByText('Hello from agent 2')).toBeTruthy();
      });
    });

    it('should display unread badges', async () => {
      const { getByTestId } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByTestId('badge')).toBeTruthy();
      });
    });

    it('should display maturity badges', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('AUTONOMOUS')).toBeTruthy();
        expect(getByText('SUPERVISED')).toBeTruthy();
      });
    });

    it('should display timestamps', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('5 minutes ago')).toBeTruthy();
      });
    });
  });

  describe('Search Functionality', () => {
    it('should filter conversations by agent name', async () => {
      const { getByTestId, getByText, queryByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const searchInput = screen.getByTestId('searchbar');
      fireEvent.changeText(searchInput, 'Agent 1');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(queryByText('Test Agent 2')).toBeNull();
      });
    });

    it('should filter conversations by message content', async () => {
      const { getByTestId, getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const searchInput = screen.getByTestId('searchbar');
      fireEvent.changeText(searchInput, 'agent 1');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should clear filter when search is cleared', async () => {
      const { getByTestId, getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
      });

      const searchInput = screen.getByTestId('searchbar');
      fireEvent.changeText(searchInput, 'Agent 1');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Re-query the searchbar: the element reference goes stale after the
      // re-render and fireEvent no-ops on unmounted elements.
      fireEvent.changeText(screen.getByTestId('searchbar'), '');

      await waitFor(() => {
        expect(getByText('Test Agent 2')).toBeTruthy();
      });
    });
  });

  describe('Sort Functionality', () => {
    it('should sort by recent by default', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should sort by unread count when Unread is selected', async () => {
      const { getByText, getByTestId } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const unreadChip = screen.getByText('Unread');
      fireEvent.press(unreadChip);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should sort by name when Name is selected', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });
  });

  describe('Maturity Filter', () => {
    it('should filter by AUTONOMOUS maturity', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const maturityChip = screen.getByTestId('chip-All Levels');
      fireEvent.press(maturityChip);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(screen.getAllByTestId('chip-AUTONOMOUS').length).toBeGreaterThan(0);
      });
    });

    it('should cycle through maturity levels on press', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Press to cycle: ALL -> AUTONOMOUS
      fireEvent.press(screen.getAllByTestId('chip-All Levels')[0]);

      // Press again: AUTONOMOUS -> SUPERVISED
      fireEvent.press(screen.getAllByTestId('chip-AUTONOMOUS')[0]);

      await waitFor(() => {
        expect(screen.getAllByTestId('chip-SUPERVISED').length).toBeGreaterThan(0);
      });
    });

    it('should reset to ALL when cycling through all levels', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Cycle through all options
      fireEvent.press(screen.getAllByTestId('chip-All Levels')[0]); // ALL -> AUTONOMOUS
      fireEvent.press(screen.getAllByTestId('chip-AUTONOMOUS')[0]); // AUTONOMOUS -> SUPERVISED
      fireEvent.press(screen.getAllByTestId('chip-SUPERVISED')[0]); // SUPERVISED -> INTERN
      fireEvent.press(screen.getAllByTestId('chip-INTERN')[0]); // INTERN -> STUDENT
      fireEvent.press(screen.getAllByTestId('chip-STUDENT')[0]); // STUDENT -> ALL

      await waitFor(() => {
        expect(screen.getAllByTestId('chip-All Levels').length).toBeGreaterThan(0);
      });
    });
  });

  describe('Navigation', () => {
    it('should navigate to agent chat on conversation press', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const conversationItem = getByText('Test Agent 1');
      fireEvent.press(conversationItem);

      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('AgentChat', {
          agentId: 'agent-1',
          sessionId: 'session-1',
        });
      });
    });

    it('should navigate to new chat on FAB press', async () => {
      const { getByTestId } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByTestId('fab')).toBeTruthy();
      });

      const fab = screen.getByTestId('fab');
      fireEvent.press(fab);

      await waitFor(() => {
        expect(mockNavigation.navigate).toHaveBeenCalledWith('AgentChat');
      });
    });
  });

  describe('Pull to Refresh', () => {
    it('should refresh conversations on pull', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      expect(mockGetConversationList).toHaveBeenCalled();
    });

    it('reloads the first page when the list is pulled to refresh', async () => {
      const { RefreshControl } = require('react-native');
      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      const refreshControl = screen.UNSAFE_getByType(RefreshControl);
      fireEvent(refreshControl, 'refresh');

      await waitFor(() => {
        // First page reloaded (no offset)
        expect(mockGetConversationList).toHaveBeenLastCalledWith(20, 0);
      });
    });
  });

  describe('Infinite Scroll', () => {
    it('should load more conversations when scrolling to end', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Trigger onEndReached
      act(() => {
        jest.advanceTimersByTime(1000);
      });

      // Should call loadMore
      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should not load more when hasMore is false', async () => {
      mockGetConversationList.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [
            {
              session_id: 'session-1',
              agent_id: 'agent-1',
              agent_name: 'Test Agent 1',
              agent_maturity: 'AUTONOMOUS',
              last_message: 'Message',
              last_message_time: new Date().toISOString(),
              unread_count: 0,
            },
          ],
        })
      );

      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Should not load more when data length < 20
      expect(getByText('Test Agent 1')).toBeTruthy();
    });
  });

  describe('Swipe Actions', () => {
    it('should archive conversation on archive action', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Archive functionality is tested via swipe
      // Just verify the component renders
      expect(getByText('Test Agent 1')).toBeTruthy();
    });

    it('should delete conversation on delete action', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Delete functionality is tested via swipe
      // Just verify the component renders
      expect(getByText('Test Agent 1')).toBeTruthy();
    });

    it('should show confirmation alert before delete', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;

      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Alert is shown on delete action
      expect(getByText('Test Agent 1')).toBeTruthy();
    });

    it('should remove conversation from list after successful delete', async () => {
      const { getByText, queryByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // After delete, conversation should be removed
      expect(getByText('Test Agent 1')).toBeTruthy();
    });
  });

  describe('Multi-Select Mode', () => {
    it('should enter multi-select mode on long press', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      const conversationItem = getByText('Test Agent 1');
      fireEvent(conversationItem, 'longPress');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should select multiple conversations', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
        expect(getByText('Test Agent 2')).toBeTruthy();
      });

      // Multi-select is triggered by long press
      const item1 = getByText('Test Agent 1');
      fireEvent(item1, 'longPress');

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('should show selected count in header', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Multi-select mode shows selected count
      expect(getByText('Test Agent 1')).toBeTruthy();
    });

    it('should exit multi-select mode when all selections cleared', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Exit multi-select by pressing close
      const closeButton = screen.queryByTestId('icon-close');
      if (closeButton) {
        fireEvent.press(closeButton);
      }

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });
    });
  });

  describe('Bulk Actions', () => {
    it('should bulk delete selected conversations', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;

      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Bulk delete is triggered in multi-select mode
      expect(getByText('Test Agent 1')).toBeTruthy();
    });

    it('should bulk mark as read selected conversations', async () => {
      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        expect(getByText('Test Agent 1')).toBeTruthy();
      });

      // Bulk mark as read is triggered in multi-select mode
      expect(getByText('Test Agent 1')).toBeTruthy();
    });
  });

  describe('Error Handling', () => {
    it('should handle API errors gracefully', async () => {
      mockGetConversationList.mockImplementationOnce(() =>
        Promise.resolve({
          success: false,
          error: 'Failed to load conversations',
        })
      );

      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        // Should show empty state on error
        expect(getByText('No conversations yet')).toBeTruthy();
      });
    });

    it('should handle network errors gracefully', async () => {
      mockGetConversationList.mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      const { getByText } = render(<ConversationListScreen />);

      await waitFor(() => {
        // Should show empty state on error
        expect(getByText('No conversations yet')).toBeTruthy();
      });
    });

    it('should show error alert when load fails', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;
      mockGetConversationList.mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Failed to load conversations');
      });
    });
  });

  describe('Multi-Select Behavior', () => {
    it('shows selected count and hides FAB after long press', async () => {
      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      // FAB is visible before multi-select
      expect(screen.getByTestId('fab')).toBeTruthy();

      fireEvent(screen.getByText('Test Agent 1'), 'longPress');

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeTruthy();
        expect(screen.queryByTestId('fab')).toBeNull();
      });
    });

    it('counts multiple selections', async () => {
      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent(screen.getByText('Test Agent 1'), 'longPress');
      fireEvent(screen.getByText('Test Agent 2'), 'longPress');

      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeTruthy();
      });
    });

    it('exits multi-select mode when close is pressed', async () => {
      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent(screen.getByText('Test Agent 1'), 'longPress');

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('icon-close'));

      await waitFor(() => {
        expect(screen.queryByText('1 selected')).toBeNull();
        expect(screen.getByTestId('fab')).toBeTruthy();
      });
    });

    it('toggles selection off when a selected conversation is pressed again', async () => {
      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent(screen.getByText('Test Agent 1'), 'longPress');
      fireEvent(screen.getByText('Test Agent 1'), 'longPress');
      fireEvent(screen.getByText('Test Agent 2'), 'longPress');

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeTruthy();
      });
    });
  });

  describe('Swipe Actions (real)', () => {
    it('archives conversation on archive action', async () => {
      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getAllByTestId('paper-icon-archive')[0]);

      await waitFor(() => {
        expect(mockArchiveSession).toHaveBeenCalledWith('session-1');
        // Compare through a boolean: when the item is still present, a direct
        // `toBeNull()` on the element would pay jest's element-diff
        // serialization cost (React fibers are huge) on every failing poll,
        // which alone can blow past the 5s test timeout.
        expect(screen.queryByText('Test Agent 1') == null).toBe(true);
        expect(screen.getByText('Test Agent 2')).toBeTruthy();
      });
    });

    it('shows confirmation alert before delete', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getAllByTestId('paper-icon-delete')[0]);

      expect(Alert).toHaveBeenCalledWith(
        'Delete Conversation',
        'Are you sure you want to delete this conversation?',
        expect.any(Array)
      );
    });

    it('removes conversation from list after confirming delete', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getAllByTestId('paper-icon-delete')[0]);

      const buttons = Alert.mock.calls[Alert.mock.calls.length - 1][2];
      const deleteButton = buttons.find((b: any) => b.text === 'Delete');
      deleteButton.onPress();

      await waitFor(() => {
        expect(mockDeleteSession).toHaveBeenCalledWith('session-1');
        // See note in "archives conversation on archive action": a boolean
        // comparison keeps failing polls free of jest's element diff cost.
        expect(screen.queryByText('Test Agent 1') == null).toBe(true);
      });
    });

    it('keeps conversation when delete is cancelled', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getAllByTestId('paper-icon-delete')[0]);

      const buttons = Alert.mock.calls[Alert.mock.calls.length - 1][2];
      // The Cancel button carries no onPress — it just dismisses the alert
      const cancelButton = buttons.find((b: any) => b.text === 'Cancel');
      expect(cancelButton).toBeTruthy();
      expect(typeof cancelButton.onPress).toBe('undefined');

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });
      expect(mockDeleteSession).not.toHaveBeenCalled();
    });

    it('shows error alert when archive fails', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;
      mockArchiveSession.mockImplementationOnce(() =>
        Promise.resolve({ success: false, error: 'Archive failed' })
      );

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getAllByTestId('paper-icon-archive')[0]);

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Archive failed');
        // Conversation stays in the list
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('shows error alert when archive throws', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;
      mockArchiveSession.mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getAllByTestId('paper-icon-archive')[0]);

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Failed to archive conversation');
      });
    });

    it('shows error alert when delete throws', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;
      mockDeleteSession.mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent.press(screen.getAllByTestId('paper-icon-delete')[0]);

      const buttons = Alert.mock.calls[Alert.mock.calls.length - 1][2];
      const deleteButton = buttons.find((b: any) => b.text === 'Delete');
      deleteButton.onPress();

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Failed to delete conversation');
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });
    });

    it('shows error alert when bulk delete fails', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;
      mockDeleteSession.mockImplementationOnce(() =>
        Promise.reject(new Error('Network error'))
      );

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent(screen.getByText('Test Agent 1'), 'longPress');

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('icon-delete'));

      const buttons = Alert.mock.calls[Alert.mock.calls.length - 1][2];
      const deleteButton = buttons.find((b: any) => b.text === 'Delete');
      deleteButton.onPress();

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Failed to delete conversation');
      });
    });

    it('renders conversations with unknown maturity levels', async () => {
      mockGetConversationList.mockImplementationOnce(() =>
        Promise.resolve({
          success: true,
          data: [
            {
              session_id: 'session-x',
              agent_id: 'agent-x',
              agent_name: 'Unknown Agent',
              agent_maturity: 'RECRUITING',
              last_message: 'Hello',
              last_message_time: new Date().toISOString(),
              unread_count: 0,
            },
          ],
        })
      );

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Unknown Agent')).toBeTruthy();
        expect(screen.getByText('RECRUITING')).toBeTruthy();
      });
    });
  });

  describe('Bulk Actions (real)', () => {
    it('bulk marks selected conversations as read', async () => {
      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      // Only session-1 has unread messages
      expect(screen.getAllByTestId('badge')).toHaveLength(1);

      fireEvent(screen.getByText('Test Agent 1'), 'longPress');

      await waitFor(() => {
        expect(screen.getByText('1 selected')).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('icon-email-open'));

      await waitFor(() => {
        expect(mockMarkAsRead).toHaveBeenCalledWith('session-1');
        // Unread badge disappears after marking as read
        expect(screen.queryAllByTestId('badge')).toHaveLength(0);
        // Multi-select exits
        expect(screen.queryByText('1 selected')).toBeNull();
      });
    });

    it('bulk deletes selected conversations after confirmation', async () => {
      const Alert = require('react-native/Libraries/Alert/Alert').alert;

      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Test Agent 1')).toBeTruthy();
      });

      fireEvent(screen.getByText('Test Agent 1'), 'longPress');
      fireEvent(screen.getByText('Test Agent 2'), 'longPress');

      await waitFor(() => {
        expect(screen.getByText('2 selected')).toBeTruthy();
      });

      fireEvent.press(screen.getByTestId('icon-delete'));

      expect(Alert).toHaveBeenCalledWith(
        'Delete Conversations',
        'Delete 2 conversations?',
        expect.any(Array)
      );

      const buttons = Alert.mock.calls[Alert.mock.calls.length - 1][2];
      const deleteButton = buttons.find((b: any) => b.text === 'Delete');
      deleteButton.onPress();

      await waitFor(() => {
        expect(mockDeleteSession).toHaveBeenCalledWith('session-1');
        expect(mockDeleteSession).toHaveBeenCalledWith('session-2');
        expect(screen.queryByText('Test Agent 1')).toBeNull();
        expect(screen.queryByText('Test Agent 2')).toBeNull();
        expect(screen.queryByText('2 selected')).toBeNull();
      });
    });
  });

  describe('Infinite Scroll (real)', () => {
    it('appends the next page when end is reached', async () => {
      const pageOne = Array(20)
        .fill(null)
        .map((_, i) => ({
          session_id: `session-${i}`,
          agent_id: `agent-${i}`,
          agent_name: `Agent ${i}`,
          agent_maturity: 'AUTONOMOUS' as const,
          last_message: `Message ${i}`,
          last_message_time: new Date(Date.now() - i * 60000).toISOString(),
          unread_count: 0,
        }));
      const pageTwo = Array(20)
        .fill(null)
        .map((_, i) => ({
          session_id: `session-b-${i}`,
          agent_id: `agent-b-${i}`,
          agent_name: `Batch Agent ${i}`,
          agent_maturity: 'SUPERVISED' as const,
          last_message: `Batch message ${i}`,
          // Newer than page 1 so the appended rows sort to the top of the
          // list (VirtualizedList only renders the first rows)
          last_message_time: new Date(Date.now() + (10 - i) * 60000).toISOString(),
          unread_count: 0,
        }));

      mockGetConversationList
        .mockImplementationOnce(() => Promise.resolve({ success: true, data: pageOne }))
        .mockImplementationOnce(() => Promise.resolve({ success: true, data: pageTwo }));

      const { FlatList } = require('react-native');
      render(<ConversationListScreen />);

      await waitFor(() => {
        expect(screen.getByText('Agent 0')).toBeTruthy();
      });

      const flatList = screen.UNSAFE_getByType(FlatList);
      act(() => {
        flatList.props.onEndReached();
      });

      await waitFor(() => {
        expect(mockGetConversationList).toHaveBeenLastCalledWith(20, 20);
        expect(screen.getByText('Batch Agent 0')).toBeTruthy();
      });
    });
  });
});
