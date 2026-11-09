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
import NetInfo from '@react-native-community/netinfo';
import { render, fireEvent, waitFor, act } from '@testing-library/react-native';
import { NavigationContainer } from '@react-navigation/native';
import { OfflineIndicator } from '../offline/OfflineIndicator';
import { offlineSyncService } from '../../services/offlineSyncService';

// Mock dependencies
// (@expo/vector-icons Ionicons is mocked globally in jest.setup.js with
// testID `icon-${name}` — no local override needed)
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

function networkState(state: { isConnected: boolean | null; isInternetReachable: boolean | null }) {
  (NetInfo.fetch as jest.Mock).mockResolvedValue(state);
  (NetInfo.addEventListener as jest.Mock).mockImplementation(callback => {
    callback(state);
    return jest.fn();
  });
}

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
    networkState({ isConnected: true, isInternetReachable: true });

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

  describe('Authoritative network state', () => {
    test('disconnected idle work is offline rather than inferred online', async () => {
      networkState({ isConnected: false, isInternetReachable: false });
      const screen = renderWithNavigation(<OfflineIndicator />);
      await waitFor(() => expect(screen.getByText('Offline - Changes Saved Locally')).toBeTruthy());
    });

    test('connected active sync is syncing rather than inferred offline', async () => {
      networkState({ isConnected: true, isInternetReachable: true });
      const syncing = { ...mockSyncState, syncInProgress: true, syncProgress: 25 };
      (offlineSyncService.getSyncState as jest.Mock).mockResolvedValue(syncing);
      (offlineSyncService.subscribe as jest.Mock).mockImplementation(callback => {
        callback(syncing);
        return jest.fn();
      });
      const screen = renderWithNavigation(<OfflineIndicator />);
      await waitFor(() => expect(screen.getByText('Syncing... 25%')).toBeTruthy());
      expect(screen.queryByText('Offline - Changes Saved Locally')).toBeNull();
    });
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
      const { getByText, queryByText, getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Should render initially
      expect(getByText('3 Pending Changes')).toBeTruthy();

      // Dismiss
      const dismissButton = getByTestId('dismiss-button');
      fireEvent.press(dismissButton, { stopPropagation: jest.fn() });

      await waitFor(() => {
        expect(queryByText('3 Pending Changes')).toBeNull();
      });
    });

    test('should re-appear after 5 minutes when dismissed', async () => {
      const { getByText, queryByText, getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      // Dismiss
      const dismissButton = getByTestId('dismiss-button');
      fireEvent.press(dismissButton, { stopPropagation: jest.fn() });

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
      networkState({ isConnected: false, isInternetReachable: false });
      (offlineSyncService.getSyncState as jest.Mock).mockResolvedValue({
        ...mockSyncState,
        syncInProgress: false,
      });

      const { getByText } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      await waitFor(() => {
        expect(getByText('Offline - Changes Saved Locally')).toBeTruthy();
      });
    });

    test('should show cloud offline icon when offline', async () => {
      networkState({ isConnected: false, isInternetReachable: false });
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
        const { StyleSheet } = require('react-native');
        expect(StyleSheet.flatten(progressBar.props.style).width).toBe('50%');
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
        const { StyleSheet } = require('react-native');
        expect(StyleSheet.flatten(progressBar.props.style).width).toBe('75%');
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
      fireEvent.press(retryButton, { stopPropagation: jest.fn() });

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
      fireEvent.press(retryButton, { stopPropagation: jest.fn() });

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
      fireEvent.press(syncNowButton, { stopPropagation: jest.fn() });

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
      fireEvent.press(syncNowButton, { stopPropagation: jest.fn() });

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
      (offlineSyncService.subscribe as jest.Mock).mockImplementation((callback) => {
        callback({
          ...mockSyncState,
          lastSuccessfulSyncAt: new Date().toISOString(),
        });
        return jest.fn();
      });

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

      expect(queryByTestId('animated-icon')).toBeNull();
    });
  });

  describe('Dismissible', () => {
    test('should hide when dismiss button is pressed', async () => {
      const { getByText, queryByText, getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      expect(getByText('3 Pending Changes')).toBeTruthy();

      const dismissButton = getByTestId('dismiss-button');
      fireEvent.press(dismissButton, { stopPropagation: jest.fn() });

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
      fireEvent.press(dismissButton, { stopPropagation: jest.fn() });

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
      const { StyleSheet } = require('react-native');
      expect(StyleSheet.flatten(container.props.style).backgroundColor).toBe('#34C759');
    });

    test('should show orange when offline', async () => {
      networkState({ isConnected: false, isInternetReachable: false });
      (offlineSyncService.getSyncState as jest.Mock).mockResolvedValue({
        ...mockSyncState,
        syncInProgress: true,
      });

      const { getByTestId } = renderWithNavigation(
        <OfflineIndicator onViewPendingActions={mockOnViewPendingActions} />
      );

      await waitFor(() => {
        const container = getByTestId('indicator-container');
        const { StyleSheet } = require('react-native');
        expect(StyleSheet.flatten(container.props.style).backgroundColor).toBe('#FF9500');
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
        const { StyleSheet } = require('react-native');
        expect(StyleSheet.flatten(container.props.style).backgroundColor).toBe('#007AFF');
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
        const { StyleSheet } = require('react-native');
        expect(StyleSheet.flatten(container.props.style).backgroundColor).toBe('#FF3B30');
      });
    });
  });

  describe('Live Network Updates', () => {
    test('should update online status from network events', async () => {
      const screen = renderWithNavigation(<OfflineIndicator />);
      const listener = (NetInfo.addEventListener as jest.Mock).mock.calls[0][0];
      act(() => { listener({ isConnected: false, isInternetReachable: false }); });
      await waitFor(() => expect(screen.getByText('Offline - Changes Saved Locally')).toBeTruthy());
      act(() => { listener({ isConnected: true, isInternetReachable: true }); });
      await waitFor(() => expect(screen.getByText('3 Pending Changes')).toBeTruthy());
    });

    test('should detach network updates on unmount', () => {
      const detach = jest.fn();
      (NetInfo.addEventListener as jest.Mock).mockReturnValue(detach);
      const { unmount } = renderWithNavigation(<OfflineIndicator />);
      unmount();
      expect(detach).toHaveBeenCalledTimes(1);
    });

    test('unknown connectivity is displayed as unknown, without a sync action', async () => {
      networkState({ isConnected: null, isInternetReachable: null });
      const screen = renderWithNavigation(<OfflineIndicator />);
      await waitFor(() => expect(screen.getByText('Checking connection')).toBeTruthy());
      expect(screen.queryByText('Sync Now')).toBeNull();
      expect(screen.queryByText('Offline - Changes Saved Locally')).toBeNull();
    });

    test('loads initial sync state when the real subscription has not emitted', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockReturnValue(jest.fn());
      const screen = renderWithNavigation(<OfflineIndicator />);
      await waitFor(() => expect(screen.getByText('3 Pending Changes')).toBeTruthy());
    });

    test('initial state read failure is unavailable rather than all synced', async () => {
      (offlineSyncService.subscribe as jest.Mock).mockReturnValue(jest.fn());
      (offlineSyncService.getSyncState as jest.Mock).mockRejectedValue(new Error('controlled read failure'));
      const screen = renderWithNavigation(<OfflineIndicator />);
      await waitFor(() => expect(screen.getByText('Sync status unavailable')).toBeTruthy());
      expect(screen.queryByText('All Synced')).toBeNull();
    });

    test('a stale initial network fetch cannot overwrite a newer event', async () => {
      let resolve!: (value: { isConnected: boolean; isInternetReachable: boolean }) => void;
      const pending = new Promise(done => { resolve = done; });
      (NetInfo.fetch as jest.Mock).mockReturnValue(pending);
      const screen = renderWithNavigation(<OfflineIndicator />);
      await act(async () => { resolve({ isConnected: false, isInternetReachable: false }); });
      expect(screen.getByText('3 Pending Changes')).toBeTruthy();
      expect(screen.queryByText('Offline - Changes Saved Locally')).toBeNull();
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
