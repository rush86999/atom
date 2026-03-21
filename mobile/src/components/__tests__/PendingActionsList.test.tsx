/**
 * PendingActionsList Component Tests
 *
 * Comprehensive test suite for PendingActionsList component covering:
 * - List rendering
 * - Action item display
 * - Delete actions
 * - Retry failed actions
 * - Filter by type
 * - Empty state
 * - Loading state
 * - Action icons
 * - Timestamps
 * - Swipe to delete
 *
 * Coverage Target: 80%+
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { ThemeProvider } from 'react-native-paper';
import { PendingActionsList } from '../offline/PendingActionsList';

// Mock dependencies
jest.mock('@react-navigation/native', () => ({
  useTheme: jest.fn(() => ({
    colors: {
      primary: '#2196F3',
      background: '#fff',
      card: '#fff',
      text: '#000',
      border: '#ccc',
      error: '#F44336',
      surface: '#fff',
    },
  })),
}));

describe('PendingActionsList Component', () => {
  const mockActions = [
    {
      id: 'action1',
      type: 'create',
      endpoint: '/api/agents',
      payload: { name: 'Test Agent' },
      timestamp: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
      retryCount: 0,
      error: null,
    },
    {
      id: 'action2',
      type: 'update',
      endpoint: '/api/workflows/123',
      payload: { status: 'active' },
      timestamp: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
      retryCount: 2,
      error: 'Network error',
    },
    {
      id: 'action3',
      type: 'delete',
      endpoint: '/api/canvas/456',
      payload: null,
      timestamp: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
      retryCount: 0,
      error: null,
    },
  ];

  const mockOnDelete = jest.fn();
  const mockOnRetry = jest.fn();

  const renderWithTheme = (component: React.ReactElement) => {
    return render(
      <ThemeProvider theme={{ colors: { primary: '#2196F3', onSurface: '#000', surface: '#fff', error: '#F44336', outline: '#ccc' } }}>
        {component}
      </ThemeProvider>
    );
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    test('should render list of actions', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('Test Agent')).toBeTruthy();
      expect(getByText('active')).toBeTruthy();
    });

    test('should render empty state when no actions', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={[]}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('No pending actions')).toBeTruthy();
    });

    test('should show action count', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('3 pending actions')).toBeTruthy();
    });
  });

  describe('Action Items', () => {
    test('should show action type icon', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByTestId('icon-create')).toBeTruthy();
      expect(getByTestId('icon-update')).toBeTruthy();
      expect(getByTestId('icon-delete')).toBeTruthy();
    });

    test('should show endpoint', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('/api/agents')).toBeTruthy();
      expect(getByText('/api/workflows/123')).toBeTruthy();
    });

    test('should show timestamp', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText(/5m ago/)).toBeTruthy();
      expect(getByText(/10m ago/)).toBeTruthy();
    });

    test('should show error message for failed actions', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('Network error')).toBeTruthy();
    });

    test('should show retry count for failed actions', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('Retried 2 times')).toBeTruthy();
    });
  });

  describe('Delete Actions', () => {
    test('should call onDelete when delete button is pressed', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      const deleteButton = getByTestId('delete-action1');
      fireEvent.press(deleteButton);

      expect(mockOnDelete).toHaveBeenCalledWith('action1');
    });

    test('should show confirmation dialog before delete', () => {
      const { getByTestId, getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      const deleteButton = getByTestId('delete-action1');
      fireEvent.press(deleteButton);

      expect(getByText('Delete this action?')).toBeTruthy();
    });

    test('should not delete if confirmation is cancelled', () => {
      const { getByTestId, getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      const deleteButton = getByTestId('delete-action1');
      fireEvent.press(deleteButton);

      const cancelButton = getByText('Cancel');
      fireEvent.press(cancelButton);

      expect(mockOnDelete).not.toHaveBeenCalled();
    });
  });

  describe('Retry Actions', () => {
    test('should show retry button for failed actions', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByTestId('retry-action2')).toBeTruthy();
    });

    test('should not show retry button for successful actions', () => {
      const { queryByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(queryByTestId('retry-action1')).toBeNull();
      expect(queryByTestId('retry-action3')).toBeNull();
    });

    test('should call onRetry when retry button is pressed', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      const retryButton = getByTestId('retry-action2');
      fireEvent.press(retryButton);

      expect(mockOnRetry).toHaveBeenCalledWith('action2');
    });
  });

  describe('Filter by Type', () => {
    test('should show all actions by default', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('Test Agent')).toBeTruthy();
      expect(getByText('active')).toBeTruthy();
    });

    test('should filter actions by type', () => {
      const { getByText, queryByText, getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      // Tap filter button
      const filterButton = getByTestId('filter-button');
      fireEvent.press(filterButton);

      // Select 'create' filter
      const createFilter = getByText('Create');
      fireEvent.press(createFilter);

      expect(getByText('Test Agent')).toBeTruthy();
      expect(queryByText('active')).toBeNull();
    });
  });

  describe('Loading State', () => {
    test('should show loading indicator when loading', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
          loading={true}
        />
      );

      expect(getByTestId('activity-indicator')).toBeTruthy();
    });

    test('should not show list when loading', () => {
      const { queryByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
          loading={true}
        />
      );

      expect(queryByText('Test Agent')).toBeNull();
    });
  });

  describe('Swipe to Delete', () => {
    test('should show delete button on swipe', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      const listItem = getByTestId('action-item-action1');

      // Simulate swipe
      fireEvent(listItem, 'onSwipeableOpen');

      expect(getByTestId('delete-button-swipe')).toBeTruthy();
    });

    test('should delete action when swipe delete is pressed', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      const listItem = getByTestId('action-item-action1');
      fireEvent(listItem, 'onSwipeableOpen');

      const deleteButton = getByTestId('delete-button-swipe');
      fireEvent.press(deleteButton);

      expect(mockOnDelete).toHaveBeenCalledWith('action1');
    });
  });

  describe('Action Details', () => {
    test('should show payload preview', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('{"name":"Test Agent"}')).toBeTruthy();
    });

    test('should show full payload on tap', () => {
      const { getByText, getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      const actionItem = getByTestId('action-item-action1');
      fireEvent.press(actionItem);

      expect(getByTestId('payload-modal')).toBeTruthy();
    });

    test('should close payload modal on close button press', () => {
      const { getByText, getByTestId, queryByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      const actionItem = getByTestId('action-item-action1');
      fireEvent.press(actionItem);

      expect(getByTestId('payload-modal')).toBeTruthy();

      const closeButton = getByText('Close');
      fireEvent.press(closeButton);

      expect(queryByTestId('payload-modal')).toBeNull();
    });
  });

  describe('Timestamp Formatting', () => {
    test('should show "Just now" for recent actions', () => {
      const recentAction = {
        ...mockActions[0],
        timestamp: new Date(Date.now() - 30 * 1000).toISOString(),
      };

      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={[recentAction]}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText(/Just now/)).toBeTruthy();
    });

    test('should show minutes for actions within hour', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText(/5m ago/)).toBeTruthy();
    });

    test('should show hours for actions within day', () => {
      const oldAction = {
        ...mockActions[0],
        timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
      };

      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={[oldAction]}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText(/3h ago/)).toBeTruthy();
    });

    test('should show days for old actions', () => {
      const veryOldAction = {
        ...mockActions[0],
        timestamp: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
      };

      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={[veryOldAction]}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText(/2d ago/)).toBeTruthy();
    });
  });

  describe('Error States', () => {
    test('should show error icon for failed actions', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByTestId('icon-error-action2')).toBeTruthy();
    });

    test('should show success icon for successful actions', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByTestId('icon-success-action1')).toBeTruthy();
    });

    test('should show warning icon for actions with retries', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByTestId('icon-warning-action2')).toBeTruthy();
    });
  });

  describe('Refresh', () => {
    test('should call onRefresh when refresh is triggered', () => {
      const mockOnRefresh = jest.fn();

      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
          onRefresh={mockOnRefresh}
          refreshing={false}
        />
      );

      const refreshControl = getByTestId('refresh-control');
      fireEvent(refreshControl, 'onRefresh');

      expect(mockOnRefresh).toHaveBeenCalled();
    });

    test('should show refreshing indicator when refreshing', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
          onRefresh={jest.fn()}
          refreshing={true}
        />
      );

      expect(getByTestId('refreshing-indicator')).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    test('should handle actions with null payload', () => {
      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText('No payload')).toBeTruthy();
    });

    test('should handle very long payloads', () => {
      const longPayloadAction = {
        ...mockActions[0],
        payload: { data: 'x'.repeat(1000) },
      };

      const { getByText } = renderWithTheme(
        <PendingActionsList
          actions={[longPayloadAction]}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(getByText(/{"data":"xxx/)).toBeTruthy();
    });

    test('should handle actions without error', () => {
      const { queryByText } = renderWithTheme(
        <PendingActionsList
          actions={[mockActions[0]]}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(queryByText('Network error')).toBeNull();
    });

    test('should handle zero retry count', () => {
      const { queryByText } = renderWithTheme(
        <PendingActionsList
          actions={[mockActions[0]]}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
        />
      );

      expect(queryByText('Retried')).toBeNull();
    });
  });

  describe('Batch Operations', () => {
    test('should select multiple actions', () => {
      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
          selectable={true}
        />
      );

      const checkbox1 = getByTestId('checkbox-action1');
      const checkbox2 = getByTestId('checkbox-action2');

      fireEvent.press(checkbox1);
      fireEvent.press(checkbox2);

      expect(checkbox1.props.checked).toBe(true);
      expect(checkbox2.props.checked).toBe(true);
    });

    test('should delete selected actions', () => {
      const mockOnBatchDelete = jest.fn();

      const { getByTestId } = renderWithTheme(
        <PendingActionsList
          actions={mockActions}
          onDelete={mockOnDelete}
          onRetry={mockOnRetry}
          onBatchDelete={mockOnBatchDelete}
          selectable={true}
        />
      );

      // Select actions
      fireEvent.press(getByTestId('checkbox-action1'));
      fireEvent.press(getByTestId('checkbox-action2'));

      // Press batch delete
      const batchDeleteButton = getByTestId('batch-delete-button');
      fireEvent.press(batchDeleteButton);

      expect(mockOnBatchDelete).toHaveBeenCalledWith(['action1', 'action2']);
    });
  });
});
