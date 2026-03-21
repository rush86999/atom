/**
 * OfflineIndicator Component Tests
 *
 * Comprehensive test suite for OfflineIndicator component covering:
 * - Online/offline states
 * - Sync progress display
 * - Pending actions count
 * - Error state with retry
 * - Sync now button
 * - Dismiss functionality
 * - Connecting animation
 * - Last sync time formatting
 * - Tap to view pending actions
 *
 * Coverage Target: 80%+
 */

import React from 'react';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { OfflineIndicator } from '../offline/OfflineIndicator';
import { offlineSyncService } from '../../services/offlineSyncService';

// Mock dependencies
jest.mock('react-native-vector-icons/Ionicons', () => 'Icon');
jest.mock('@react-navigation/native', () => ({
  ...jest.requireActual('@react-navigation/native'),
  useTheme: jest.fn(() => ({
    colors: {
      primary: '#2196F3',
      background: '#fff',
      card: '#fff',
      text: '#000',
      border: '#ccc',
      notification: '#FF3B30',
    },
  })),
}));

jest.mock('../../services/offlineSyncService', () => ({
  offlineSyncService: {
    subscribe: jest.fn(),
    getSyncState: jest.fn(),
    triggerSync: jest.fn(),
  },
}));

describe('OfflineIndicator Component', () => {
  const mockOnViewPendingActions = jest.fn();

  const mockSyncState = {
    lastSyncAt: new Date().toISOString(),
    lastSuccessfulSyncAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(),
    pendingCount: 3,
    syncInProgress: false,
    consecutiveFailures: 0,
    syncProgress: 0,
  };

  const renderWithNavigation = (component: React.ReactElement) => {
    return render(
      <NavigationContainer>
        {component}
      </NavigationContainer>
    );
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
      // Immediately call with initial state
      callback(mockSyncState);
      return jest.fn(); // Return unsubscribe function
    });

    (offlineSyncService.getSyncState as jest.Mock).mockResolvedValue(mockSyncState);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('Rendering', () => {
    test('should render correctly when offline', () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({ ...mockSyncState, pendingCount: 0 });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText('All Synced')).toBeTruthy();
    });

    test('should render when has pending actions', () => {
      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText('3 Pending Changes')).toBeTruthy();
    });

    test('should not render when dismissed', async () => {
      const { getByText, queryByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Should render initially
      expect(getByText('3 Pending Changes')).toBeTruthy();

      // Dismiss
      const dismissButton = getByText('3 Pending Changes').parent.parent.parent.findByProps({ testID: 'dismiss-button' });
      fireEvent.press(dismissButton);

      await waitFor(() => {
        expect(queryByText('3 Pending Changes')).toBeNull();
      });
    });

    test('should re-appear after 5 minutes when dismissed', async () => {
      const { getByText, queryByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Dismiss
      const dismissButton = getByText('3 Pending Changes').parent.parent.parent.findByProps({ testID: 'dismiss-button' });
      fireEvent.press(dismissButton);

      await waitFor(() => {
        expect(queryByText('3 Pending Changes')).toBeNull();
      });

      // Fast-forward 5 minutes
      act(() => {
        jest.advanceTimersByTime(5 * 60 * 1000);
      });

      // Should re-appear
      await waitFor(() => {
        expect(getByText('3 Pending Changes')).toBeTruthy();
      });
    });
  });

  describe('Online State', () => {
    test('should show green indicator when online and synced', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          pendingCount: 0,
          syncInProgress: false,
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText('All Synced')).toBeTruthy();
    });

    test('should show sync now button when online with pending actions', () => {
      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText('Sync Now')).toBeTruthy();
    });

    test('should not show sync now button when no pending actions', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          pendingCount: 0,
        });
        return jest.fn();
      });

      const { queryByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(queryByText('Sync Now')).toBeNull();
    });
  });

  describe('Offline State', () => {
    test('should show offline message when offline', async () => {
      (offlineSyncService.getSyncState as jest.Mock).mockResolvedValue({
        ...mockSyncState,
        syncInProgress: true, // Simulating offline
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      await waitFor(() => {
        expect(getByText('Offline - Changes Saved Locally')).toBeTruthy();
      });
    });

    test('should show cloud offline icon when offline', async () => {
      (offlineSyncService.getSyncState as jest.Mock).mockResolvedValue({
        ...mockSyncState,
        syncInProgress: true,
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      await waitFor(() => {
        expect(getByTestId('icon-cloud-offline')).toBeTruthy();
      });
    });
  });

  describe('Sync Progress', () => {
    test('should show sync progress when syncing', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByText, getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Trigger sync
      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: true,
          syncProgress: 50,
        });
      });

      await waitFor(() => {
        expect(getByText('Syncing... 50%')).toBeTruthy();
        expect(getByTestId('progress-bar')).toBeTruthy();
      });
    });

    test('should update progress bar width', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Start sync at 50%
      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: true,
          syncProgress: 50,
        });
      });

      await waitFor(() => {
        const progressBar = getByTestId('progress-bar-fill');
        expect(progressBar.props.style.width).toBe('50%');
      });

      // Update to 75%
      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: true,
          syncProgress: 75,
        });
      });

      await waitFor(() => {
        const progressBar = getByTestId('progress-bar-fill');
        expect(progressBar.props.style.width).toBe('75%');
      });
    });

    test('should hide progress bar when sync completes', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { queryByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Start sync
      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: true,
          syncProgress: 50,
        });
      });

      await waitFor(() => {
        expect(queryByTestId('progress-bar')).toBeTruthy();
      });

      // Complete sync
      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: false,
          syncProgress: 100,
        });
      });

      await waitFor(() => {
        expect(queryByTestId('progress-bar')).toBeNull();
      });
    });
  });

  describe('Error State', () => {
    test('should show error message when sync fails', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      act(() => {
        syncCallback({
          ...mockSyncState,
          consecutiveFailures: 3,
        });
      });

      await waitFor(() => {
        expect(getByText('Sync Error - Tap to Retry')).toBeTruthy();
      });
    });

    test('should show retry button when error', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      act(() => {
        syncCallback({
          ...mockSyncState,
          consecutiveFailures: 3,
        });
      });

      await waitFor(() => {
        expect(getByText('Retry')).toBeTruthy();
      });
    });

    test('should retry sync when retry button is pressed', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      (offlineSyncService.triggerSync as jest.Mock).mockResolvedValue(undefined);

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Set error state
      act(() => {
        syncCallback({
          ...mockSyncState,
          consecutiveFailures: 3,
        });
      });

      await waitFor(() => {
        expect(getByText('Retry')).toBeTruthy();
      });

      // Press retry
      const retryButton = getByText('Retry');
      fireEvent.press(retryButton);

      await waitFor(() => {
        expect(offlineSyncService.triggerSync).toHaveBeenCalled();
      });
    });

    test('should clear error when retry starts', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByText, queryByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Set error state
      act(() => {
        syncCallback({
          ...mockSyncState,
          consecutiveFailures: 3,
        });
      });

      await waitFor(() => {
        expect(getByText('Sync Error - Tap to Retry')).toBeTruthy();
      });

      // Press retry
      const retryButton = getByText('Retry');
      fireEvent.press(retryButton);

      // Error should clear
      await waitFor(() => {
        expect(queryByText('Sync Error - Tap to Retry')).toBeNull();
      });
    });
  });

  describe('Sync Now Button', () => {
    test('should call triggerSync when sync now is pressed', async () => {
      (offlineSyncService.triggerSync as jest.Mock).mockResolvedValue(undefined);

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      const syncNowButton = getByText('Sync Now');
      fireEvent.press(syncNowButton);

      await waitFor(() => {
        expect(offlineSyncService.triggerSync).toHaveBeenCalled();
      });
    });

    test('should not show sync now button when syncing', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { queryByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Start sync
      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: true,
        });
      });

      await waitFor(() => {
        expect(queryByText('Sync Now')).toBeNull();
      });
    });

    test('should show error if sync now fails', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      (offlineSyncService.triggerSync as jest.Mock).mockRejectedValue(new Error('Sync failed'));

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      const syncNowButton = getByText('Sync Now');
      fireEvent.press(syncNowButton);

      await waitFor(() => {
        expect(getByText('Sync Error - Tap to Retry')).toBeTruthy();
      });
    });
  });

  describe('Tap to View Pending Actions', () => {
    test('should call onViewPendingActions when tapped', () => {
      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      const indicator = getByText('3 Pending Changes').parent;
      fireEvent.press(indicator);

      expect(mockOnViewPendingActions).toHaveBeenCalled();
    });

    test('should not call onViewPendingActions when no pending actions', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          pendingCount: 0,
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      const indicator = getByText('All Synced').parent;
      fireEvent.press(indicator);

      expect(mockOnViewPendingActions).not.toHaveBeenCalled();
    });
  });

  describe('Last Sync Time', () => {
    test('should show "Just now" for recent sync', async () => {
      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText(/Last sync: Just now/)).toBeTruthy();
    });

    test('should show minutes ago for sync within hour', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          lastSuccessfulSyncAt: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText(/Last sync: 30m ago/)).toBeTruthy();
    });

    test('should show hours ago for sync within day', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          lastSuccessfulSyncAt: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText(/Last sync: 3h ago/)).toBeTruthy();
    });

    test('should show days ago for old sync', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          lastSuccessfulSyncAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText(/Last sync: 2d ago/)).toBeTruthy();
    });

    test('should show "Never" when no successful sync', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          lastSuccessfulSyncAt: null,
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText(/Last sync: Never/)).toBeTruthy();
    });
  });

  describe('Connecting Animation', () => {
    test('should start rotation animation when sync starts', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Start sync
      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: true,
        });
      });

      await waitFor(() => {
        expect(getByTestId('animated-icon')).toBeTruthy();
      });
    });

    test('should stop rotation animation when sync completes', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback({
          ...mockSyncState,
          syncInProgress: true,
        });
        return jest.fn();
      });

      const { queryByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Animation should be running
      expect(queryByTestId('animated-icon')).toBeTruthy();

      // Complete sync
      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: false,
        });
      });

      await waitFor(() => {
        expect(queryByTestId('animated-icon')).toBeNull();
      });
    });
  });

  describe('Dismissible', () => {
    test('should hide when dismiss button is pressed', async () => {
      const { getByText, queryByText, getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText('3 Pending Changes')).toBeTruthy();

      const dismissButton = getByTestId('dismiss-button');
      fireEvent.press(dismissButton);

      await waitFor(() => {
        expect(queryByText('3 Pending Changes')).toBeNull();
      });
    });

    test('should set timeout to re-appear after dismiss', () => {
      const setTimeoutSpy = jest.spyOn(global, 'setTimeout');

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      const dismissButton = getByTestId('dismiss-button');
      fireEvent.press(dismissButton);

      expect(setTimeoutSpy).toHaveBeenCalledWith(expect.any(Function), 5 * 60 * 1000);

      setTimeoutSpy.mockRestore();
    });
  });

  describe('Icon Display', () => {
    test('should show cloud-done icon when synced', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          pendingCount: 0,
          syncInProgress: false,
        });
        return jest.fn();
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByTestId('icon-cloud-done')).toBeTruthy();
    });

    test('should show sync icon when syncing', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: true,
        });
      });

      await waitFor(() => {
        expect(getByTestId('icon-sync')).toBeTruthy();
      });
    });

    test('should show alert-circle icon when error', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      act(() => {
        syncCallback({
          ...mockSyncState,
          consecutiveFailures: 3,
        });
      });

      await waitFor(() => {
        expect(getByTestId('icon-alert-circle')).toBeTruthy();
      });
    });
  });

  describe('Color States', () => {
    test('should show green when online and synced', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          pendingCount: 0,
          syncInProgress: false,
        });
        return jest.fn();
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      const container = getByTestId('indicator-container');
      expect(container.props.style.backgroundColor).toBe('#34C759');
    });

    test('should show orange when offline', async () => {
      (offlineSyncService.getSyncState as jest.Mock).mockResolvedValue({
        ...mockSyncState,
        syncInProgress: true,
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      await waitFor(() => {
        const container = getByTestId('indicator-container');
        expect(container.props.style.backgroundColor).toBe('#FF9500');
      });
    });

    test('should show blue when syncing', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      act(() => {
        syncCallback({
          ...mockSyncState,
          syncInProgress: true,
        });
      });

      await waitFor(() => {
        const container = getByTestId('indicator-container');
        expect(container.props.style.backgroundColor).toBe('#007AFF');
      });
    });

    test('should show red when error', async () => {
      let syncCallback: any;
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        syncCallback = callback;
        callback(mockSyncState);
        return jest.fn();
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      act(() => {
        syncCallback({
          ...mockSyncState,
          consecutiveFailures: 3,
        });
      });

      await waitFor(() => {
        const container = getByTestId('indicator-container');
        expect(container.props.style.backgroundColor).toBe('#FF3B30');
      });
    });
  });

  describe('Periodic Online Check', () => {
    test('should check online status every 10 seconds', () => {
      const setIntervalSpy = jest.spyOn(global, 'setInterval');

      renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(setIntervalSpy).toHaveBeenCalledWith(expect.any(Function), 10000);

      setIntervalSpy.mockRestore();
    });

    test('should clear interval on unmount', () => {
      const clearIntervalSpy = jest.spyOn(global, 'clearInterval');

      const { unmount } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      unmount();

      expect(clearIntervalSpy).toHaveBeenCalled();

      clearIntervalSpy.mockRestore();
    });
  });

  describe('Edge Cases', () => {
    test('should handle null lastSyncAt', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          lastSyncAt: null,
          lastSuccessfulSyncAt: null,
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText(/Last sync: Never/)).toBeTruthy();
    });

    test('should handle zero pending count', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          pendingCount: 0,
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText('All Synced')).toBeTruthy();
    });

    test('should handle large pending count', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          pendingCount: 999,
        });
        return jest.fn();
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText('999 Pending Changes')).toBeTruthy();
    });
  });
});
