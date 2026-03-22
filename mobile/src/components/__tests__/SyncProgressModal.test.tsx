/**
 * SyncProgressModal Component Tests
 *
 * Comprehensive test suite for SyncProgressModal component covering:
 * - Modal visibility
 * - Progress display
 * - Sync status messages
 * - Cancel sync
 * - Error display
 * - Success state
 * - Retry failed sync
 * - Animated progress bar
 * - Item-by-item progress
 * - Close on complete
 *
 * Coverage Target: 80%+
 */

import React from 'react';
import { render, fireEvent, waitFor } from '@testing-library/react-native';
import { ThemeProvider } from 'react-native-paper';
import { SyncProgressModal } from '../offline/SyncProgressModal';

// Mock dependencies
jest.mock('react-native/Libraries/Animated/Animated', () => {
  const ActualAnimated = jest.requireActual('react-native/Libraries/Animated/Animated');
  return {
    ...ActualAnimated,
    timing: jest.fn((value, config) => ({
      start: (callback?: any) => callback?.({ finished: true }),
    })),
  };
});

describe('SyncProgressModal Component', () => {
  const mockOnCancel = jest.fn();
  const mockOnRetry = jest.fn();

  const defaultProps = {
    visible: true,
    progress: 50,
    status: 'syncing',
    current: 1,
    total: 10,
    currentItem: 'agents',
    onCancel: mockOnCancel,
    onRetry: mockOnRetry,
  };

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
    test('should render modal when visible', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} />
      );

      expect(getByTestId('sync-modal')).toBeTruthy();
    });

    test('should not render modal when not visible', () => {
      const { queryByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} visible={false} />
      );

      expect(queryByTestId('sync-modal')).toBeNull();
    });

    test('should show progress bar', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} />
      );

      expect(getByTestId('progress-bar')).toBeTruthy();
    });

    test('should show progress percentage', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} />
      );

      expect(getByText('50%')).toBeTruthy();
    });

    test('should show current and total items', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} />
      );

      expect(getByText('1 of 10')).toBeTruthy();
    });

    test('should show current item being synced', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} />
      );

      expect(getByText('Syncing agents...')).toBeTruthy();
    });
  });

  describe('Progress Display', () => {
    test('should update progress percentage', () => {
      const { getByText, rerender } = renderWithTheme(
        <SyncProgressModal {...defaultProps} progress={25} />
      );

      expect(getByText('25%')).toBeTruthy();

      rerender(
        <ThemeProvider theme={{ colors: { primary: '#2196F3' } }}>
          <SyncProgressModal {...defaultProps} progress={75} />
        </ThemeProvider>
      );

      expect(getByText('75%')).toBeTruthy();
    });

    test('should update progress bar width', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} progress={50} />
      );

      const progressBar = getByTestId('progress-bar-fill');
      expect(progressBar.props.style.width).toBe('50%');
    });

    test('should show correct current/total count', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} current={5} total={10} />
      );

      expect(getByText('5 of 10')).toBeTruthy();
    });

    test('should handle zero progress', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} progress={0} />
      );

      expect(getByText('0%')).toBeTruthy();
    });

    test('should handle 100% progress', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} progress={100} />
      );

      expect(getByText('100%')).toBeTruthy();
    });
  });

  describe('Sync Status', () => {
    test('should show syncing status', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="syncing" />
      );

      expect(getByText('Syncing agents...')).toBeTruthy();
    });

    test('should show preparing status', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="preparing" />
      );

      expect(getByText('Preparing sync...')).toBeTruthy();
    });

    test('should show completing status', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="completing" />
      );

      expect(getByText('Completing sync...')).toBeTruthy();
    });

    test('should show success status', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="success" />
      );

      expect(getByText('Sync complete!')).toBeTruthy();
    });

    test('should show error status', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="error" />
      );

      expect(getByText('Sync failed')).toBeTruthy();
    });
  });

  describe('Cancel Sync', () => {
    test('should show cancel button when syncing', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="syncing" />
      );

      expect(getByText('Cancel')).toBeTruthy();
    });

    test('should not show cancel button when complete', () => {
      const { queryByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="success" />
      );

      expect(queryByText('Cancel')).toBeNull();
    });

    test('should not show cancel button when error', () => {
      const { queryByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="error" />
      );

      expect(queryByText('Cancel')).toBeNull();
    });

    test('should call onCancel when cancel is pressed', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="syncing" />
      );

      const cancelButton = getByText('Cancel');
      fireEvent.press(cancelButton);

      expect(mockOnCancel).toHaveBeenCalled();
    });

    test('should show confirmation dialog before cancel', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="syncing" />
      );

      const cancelButton = getByText('Cancel');
      fireEvent.press(cancelButton);

      expect(getByText('Cancel sync?')).toBeTruthy();
      expect(getByText('Any unsynced changes will be lost.')),toBeTruthy();
    });

    test('should not cancel if confirmation is cancelled', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="syncing" />
      );

      const cancelButton = getByText('Cancel');
      fireEvent.press(cancelButton);

      const dontCancelButton = getByText("Don't cancel");
      fireEvent.press(dontCancelButton);

      expect(mockOnCancel).not.toHaveBeenCalled();
    });
  });

  describe('Error State', () => {
    test('should show error message when error occurs', () => {
      const errorMessage = 'Network connection lost';

      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="error"
          error={errorMessage}
        />
      );

      expect(getByText(errorMessage)).toBeTruthy();
    });

    test('should show retry button when error', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="error" />
      );

      expect(getByText('Retry')).toBeTruthy();
    });

    test('should call onRetry when retry is pressed', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="error" />
      );

      const retryButton = getByText('Retry');
      fireEvent.press(retryButton);

      expect(mockOnRetry).toHaveBeenCalled();
    });

    test('should show error icon when error', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="error" />
      );

      expect(getByTestId('error-icon')).toBeTruthy();
    });
  });

  describe('Success State', () => {
    test('should show success message when complete', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="success" />
      );

      expect(getByText('Sync complete!')).toBeTruthy();
    });

    test('should show success icon when complete', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="success" />
      );

      expect(getByTestId('success-icon')).toBeTruthy();
    });

    test('should show close button when complete', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="success" />
      );

      expect(getByText('Close')).toBeTruthy();
    });

    test('should auto-close after delay when complete', async () => {
      jest.useFakeTimers();

      const mockOnClose = jest.fn();

      renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="success"
          autoClose={true}
          autoCloseDelay={2000}
          onClose={mockOnClose}
        />
      );

      act(() => {
        jest.advanceTimersByTime(2000);
      });

      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });

      jest.useRealTimers();
    });

    test('should not auto-close when autoClose is false', async () => {
      jest.useFakeTimers();

      const mockOnClose = jest.fn();

      renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="success"
          autoClose={false}
          onClose={mockOnClose}
        />
      );

      act(() => {
        jest.advanceTimersByTime(5000);
      });

      expect(mockOnClose).not.toHaveBeenCalled();

      jest.useRealTimers();
    });
  });

  describe('Item-by-Item Progress', () => {
    test('should show list of items being synced', () => {
      const items = [
        { id: '1', name: 'Agent 1', status: 'synced' },
        { id: '2', name: 'Agent 2', status: 'syncing' },
        { id: '3', name: 'Agent 3', status: 'pending' },
      ];

      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          items={items}
        />
      );

      expect(getByText('Agent 1')).toBeTruthy();
      expect(getByText('Agent 2')).toBeTruthy();
      expect(getByText('Agent 3')).toBeTruthy();
    });

    test('should show checkmark for synced items', () => {
      const items = [
        { id: '1', name: 'Agent 1', status: 'synced' },
      ];

      const { getByTestId } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          items={items}
        />
      );

      expect(getByTestId('check-icon-1')).toBeTruthy();
    });

    test('should show spinner for syncing item', () => {
      const items = [
        { id: '1', name: 'Agent 1', status: 'syncing' },
      ];

      const { getByTestId } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          items={items}
        />
      );

      expect(getByTestId('spinner-icon-1')).toBeTruthy();
    });

    test('should show error for failed items', () => {
      const items = [
        { id: '1', name: 'Agent 1', status: 'error', error: 'Failed to sync' },
      ];

      const { getByText, getByTestId } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          items={items}
        />
      );

      expect(getByText('Failed to sync')).toBeTruthy();
      expect(getByTestId('error-icon-1')).toBeTruthy();
    });
  });

  describe('Animation', () => {
    test('should animate progress bar', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} progress={50} />
      );

      const progressBar = getByTestId('progress-bar-fill');
      expect(progressBar.props.animated).toBe(true);
    });

    test('should animate success icon', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="success" />
      );

      const successIcon = getByTestId('success-icon');
      expect(successIcon.props.animated).toBe(true);
    });

    test('should animate error icon', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="error" />
      );

      const errorIcon = getByTestId('error-icon');
      expect(errorIcon.props.animated).toBe(true);
    });
  });

  describe('Close on Complete', () => {
    test('should call onClose when close button is pressed', () => {
      const mockOnClose = jest.fn();

      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="success"
          onClose={mockOnClose}
        />
      );

      const closeButton = getByText('Close');
      fireEvent.press(closeButton);

      expect(mockOnClose).toHaveBeenCalled();
    });

    test('should close modal when backdrop is pressed', () => {
      const mockOnClose = jest.fn();

      const { getByTestId } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="success"
          onClose={mockOnClose}
        />
      );

      const backdrop = getByTestId('modal-backdrop');
      fireEvent.press(backdrop);

      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe('Sync Statistics', () => {
    test('should show sync statistics when complete', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="success"
          stats={{
            synced: 10,
            failed: 2,
            skipped: 1,
          }}
        />
      );

      expect(getByText('10 synced')).toBeTruthy();
      expect(getByText('2 failed')).toBeTruthy();
      expect(getByText('1 skipped')).toBeTruthy();
    });

    test('should show time elapsed', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="success"
          timeElapsed="2:34"
        />
      );

      expect(getByText('2:34')).toBeTruthy();
    });

    test('should show sync speed', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="syncing"
          syncSpeed="5 items/sec"
        />
      );

      expect(getByText('5 items/sec')).toBeTruthy();
    });
  });

  describe('Edge Cases', () => {
    test('should handle zero total items', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          total={0}
        />
      );

      expect(getByText('0 of 0')).toBeTruthy();
    });

    test('should handle very large progress', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          progress={150}
        />
      );

      expect(getByText('100%')).toBeTruthy();
    });

    test('should handle negative progress', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          progress={-10}
        />
      );

      expect(getByText('0%')).toBeTruthy();
    });

    test('should handle empty items list', () => {
      const { queryByTestId } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          items={[]}
        />
      );

      expect(queryByTestId('items-list')).toBeNull();
    });

    test('should handle missing error message', () => {
      const { queryByText } = renderWithTheme(
        <SyncProgressModal
          {...defaultProps}
          status="error"
          error={undefined}
        />
      );

      expect(queryByText(/Error/)).toBeTruthy();
    });
  });

  describe('Accessibility', () => {
    test('should have accessibility label for modal', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} />
      );

      const modal = getByTestId('sync-modal');
      expect(modal.props.accessibilityLabel).toBe('Sync progress modal');
    });

    test('should have accessibility label for progress bar', () => {
      const { getByTestId } = renderWithTheme(
        <SyncProgressModal {...defaultProps} progress={50} />
      );

      const progressBar = getByTestId('progress-bar');
      expect(progressBar.props.accessibilityValue).toEqual({ text: '50' });
    });

    test('should announce status changes', () => {
      const { getByText } = renderWithTheme(
        <SyncProgressModal {...defaultProps} status="syncing" />
      );

      const status = getByText('Syncing agents...');
      expect(status.props.accessibilityLiveRegion).toBe('assertive');
    });
  });
});
