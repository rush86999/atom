/**
 * NotificationPreferencesScreen Component Tests
 *
 * Tests for permission handling, category toggles, sound selection,
 * quiet hours, badge toggle, and preview notifications.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { NotificationPreferencesScreen } from '../../../screens/device/NotificationPreferencesScreen';

jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

// Mock notificationService
jest.mock('../../../services/notificationService', () => ({
  notificationService: {
    getPermissionStatus: jest.fn(),
    requestPermissions: jest.fn(),
    sendLocalNotification: jest.fn(),
  },
}));

const { notificationService } = require('../../../services/notificationService');

const Alert = require('react-native/Libraries/Alert/Alert').alert;

function mockPermission(status: 'granted' | 'denied' | 'undetermined') {
  notificationService.getPermissionStatus.mockResolvedValue(status);
}

describe('NotificationPreferencesScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPermission('granted');
    notificationService.sendLocalNotification.mockResolvedValue(undefined);
  });

  describe('Permission Status', () => {
    it('shows enabled text when permission granted', async () => {
      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Notifications are enabled')).toBeTruthy();
      });
    });

    it('shows grant hint when permission denied', async () => {
      mockPermission('denied');

      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Grant permission to receive notifications')).toBeTruthy();
      });
    });

    it('requests permission when enable switch is toggled', async () => {
      mockPermission('denied');
      notificationService.requestPermissions.mockResolvedValue('granted');

      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Grant permission to receive notifications')).toBeTruthy();
      });

      const switches = getSwitches();
      fireEvent(switches[0], 'valueChange', true);

      await waitFor(() => {
        expect(notificationService.requestPermissions).toHaveBeenCalled();
        expect(getByText('Notifications are enabled')).toBeTruthy();
      });
    });

    it('shows permission denied alert when request is denied', async () => {
      mockPermission('denied');
      notificationService.requestPermissions.mockResolvedValue('denied');

      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Grant permission to receive notifications')).toBeTruthy();
      });

      const switches = getSwitches();
      fireEvent(switches[0], 'valueChange', true);

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith(
          'Permission Denied',
          expect.stringContaining('enable them in your device settings'),
          expect.any(Array)
        );
      });
    });

    it('shows error alert when permission check throws', async () => {
      mockPermission('denied');
      notificationService.requestPermissions.mockRejectedValue(
        new Error('Notification module unavailable')
      );

      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Grant permission to receive notifications')).toBeTruthy();
      });

      const switches = getSwitches();
      fireEvent(switches[0], 'valueChange', true);

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Notification module unavailable');
      });
    });
  });

  describe('Category Toggles', () => {
    it('disables category switches when permission not granted', async () => {
      mockPermission('denied');

      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Agent Alerts')).toBeTruthy();
      });

      const switches = getSwitches();
      // switches[1..3] are categories, [5] is badge — all disabled
      expect(switches[1].props.disabled).toBe(true);
      expect(switches[2].props.disabled).toBe(true);
      expect(switches[3].props.disabled).toBe(true);
      expect(switches[5].props.disabled).toBe(true);
    });

    it('toggles category preferences when permission granted', async () => {
      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Agent Alerts')).toBeTruthy();
      });

      const switches = getSwitches();
      expect(switches[1].props.value).toBe(true);

      fireEvent(switches[1], 'valueChange', false);

      await waitFor(() => {
        expect(getSwitches()[1].props.value).toBe(false);
      });
    });
  });

  describe('Sound Selection', () => {
    it('selects a sound and highlights it', async () => {
      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('CHIME')).toBeTruthy();
      });

      const { TouchableOpacity, StyleSheet } = require('react-native');
      const isHighlighted = (label: string) => {
        const text = screen.getByText(label);
        let node = text.parent;
        while (node) {
          if (node.type === TouchableOpacity) {
            return (
              StyleSheet.flatten(node.props.style)?.backgroundColor ===
              '#f0f8ff'
            );
          }
          node = node.parent;
        }
        return false;
      };

      // Default selection is 'default' — its row is highlighted
      expect(isHighlighted('DEFAULT')).toBe(true);

      fireEvent.press(getByText('CHIME'));

      await waitFor(() => {
        // Active radio option moves to the CHIME row
        expect(isHighlighted('CHIME')).toBe(true);
        expect(isHighlighted('DEFAULT')).toBe(false);
      });
    });

    it('shows all sound options', async () => {
      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('DEFAULT')).toBeTruthy();
        expect(getByText('CHIME')).toBeTruthy();
        expect(getByText('BELL')).toBeTruthy();
        expect(getByText('SILENCE')).toBeTruthy();
      });
    });
  });

  describe('Quiet Hours', () => {
    it('shows time rows only when quiet hours enabled', async () => {
      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Quiet Hours')).toBeTruthy();
      });

      expect(queryByText('22:00')).toBeNull();

      const switches = getSwitches();
      fireEvent(switches[4], 'valueChange', true);

      await waitFor(() => {
        expect(getByText('22:00')).toBeTruthy();
        expect(getByText('08:00')).toBeTruthy();
      });
    });
  });

  describe('Preview Notification', () => {
    it('sends a preview notification with correct payload', async () => {
      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Send Preview Notification')).toBeTruthy();
      });

      fireEvent.press(getByText('Send Preview Notification'));

      await waitFor(() => {
        expect(notificationService.sendLocalNotification).toHaveBeenCalledWith({
          title: 'Atom Notification',
          body: 'This is a preview notification from Atom',
          sound: true,
          badge: 1,
        });
        expect(Alert).toHaveBeenCalledWith('Success', 'Preview notification sent');
      });
    });

    it('shows error alert when preview send fails', async () => {
      notificationService.sendLocalNotification.mockRejectedValue(
        new Error('Send failed')
      );

      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Send Preview Notification')).toBeTruthy();
      });

      fireEvent.press(getByText('Send Preview Notification'));

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Send failed');
      });
    });

    it('disables preview button when permission not granted', async () => {
      mockPermission('denied');

      render(<NotificationPreferencesScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Send Preview Notification')).toBeTruthy();
      });

      fireEvent.press(getByText('Send Preview Notification'));

      expect(notificationService.sendLocalNotification).not.toHaveBeenCalled();
    });
  });
});

function getByText(text: string | RegExp) {
  return screen.getByText(text);
}

function queryByText(text: string | RegExp) {
  return screen.queryByText(text);
}

function getSwitches() {
  const { Switch } = require('react-native');
  return screen.UNSAFE_getAllByType(Switch);
}
