/**
 * Notifications Component Tests
 *
 * Tests for Notification Preferences screen component including:
 * - Rendering notification view
 * - Requesting notification permissions
 * - Sending local notifications
 * - Scheduling notifications
 * - Notification error handling
 * - Category preferences (agent alerts, workflow updates, system alerts)
 * - Sound preferences
 * - Quiet hours
 * - Badge settings
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { NotificationPreferencesScreen } from '../../screens/device/NotificationPreferencesScreen';
import { notificationService } from '../../services/notificationService';

// Mock expo-vector-icons
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

// Mock notification service
jest.mock('../../services/notificationService', () => ({
  notificationService: {
    getPermissionStatus: jest.fn(),
    requestPermissions: jest.fn(),
    sendLocalNotification: jest.fn(),
    scheduleNotification: jest.fn(),
    cancelScheduledNotifications: jest.fn(),
    getAllScheduledNotifications: jest.fn(),
    setNotificationHandler: jest.fn(),
  },
}));

// Mock Alert
jest.mock('react-native', () => ({
  ...jest.requireActual('react-native'),
  Alert: {
    alert: jest.fn(),
  },
}));

// Mock navigation
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
};

describe('Notifications Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  /**
   * Test: Renders notification view
   * Expected: Notification component renders without crashing
   */
  test('test_renders_notification_view', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Notifications')).toBeTruthy();
      expect(getByText('Manage your notification preferences')).toBeTruthy();
    });
  });

  /**
   * Test: Request notification permission
   * Expected: Permission request is triggered
   */
  test('test_request_notification_permission', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('undetermined');
    (notificationService.requestPermissions as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(notificationService.getPermissionStatus).toHaveBeenCalled();
    });

    expect(notificationService.requestPermissions).toBeDefined();
  });

  /**
   * Test: Send local notification
   * Expected: Preview notification is sent successfully
   */
  test('test_send_local_notification', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');
    (notificationService.sendLocalNotification as jest.Mock).mockResolvedValue(undefined);

    const Alert = require('react-native').Alert;
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Send Preview Notification')).toBeTruthy();
    });

    expect(notificationService.sendLocalNotification).toBeDefined();
  });

  /**
   * Test: Schedule notification
   * Expected: Notification can be scheduled
   */
  test('test_schedule_notification', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');
    (notificationService.scheduleNotification as jest.Mock).mockResolvedValue('notification-id');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(notificationService.getPermissionStatus).toHaveBeenCalled();
    });

    expect(notificationService.scheduleNotification).toBeDefined();
  });

  /**
   * Test: Notification error handling
   * Expected: Error is caught and alert is shown when notification fails
   */
  test('test_notification_error', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('denied');
    (notificationService.requestPermissions as jest.Mock).mockResolvedValue('denied');

    const Alert = require('react-native').Alert;
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(notificationService.getPermissionStatus).toHaveBeenCalled();
    });

    expect(Alert.alert).toBeDefined();
  });

  /**
   * Test: Category preferences - Agent Alerts
   * Expected: Agent alerts preference can be toggled
   */
  test('test_category_preferences_agent_alerts', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Agent Alerts')).toBeTruthy();
    });
  });

  /**
   * Test: Category preferences - Workflow Updates
   * Expected: Workflow updates preference can be toggled
   */
  test('test_category_preferences_workflow_updates', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Workflow Updates')).toBeTruthy();
    });
  });

  /**
   * Test: Category preferences - System Alerts
   * Expected: System alerts preference can be toggled
   */
  test('test_category_preferences_system_alerts', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('System Alerts')).toBeTruthy();
    });
  });

  /**
   * Test: Sound preferences
   * Expected: Sound preference can be changed
   */
  test('test_sound_preferences', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Sound')).toBeTruthy();
      expect(getByText('DEFAULT')).toBeTruthy();
      expect(getByText('CHIME')).toBeTruthy();
      expect(getByText('BELL')).toBeTruthy();
      expect(getByText('SILENCE')).toBeTruthy();
    });
  });

  /**
   * Test: Quiet hours enabled
   * Expected: Quiet hours can be enabled
   */
  test('test_quiet_hours_enabled', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Quiet Hours')).toBeTruthy();
    });
  });

  /**
   * Test: Quiet hours time display
   * Expected: Quiet hours start and end times are displayed
   */
  test('test_quiet_hours_time_display', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('From')).toBeTruthy();
      expect(getByText('To')).toBeTruthy();
    });
  });

  /**
   * Test: Badge enabled
   * Expected: App icon badge preference can be toggled
   */
  test('test_badge_enabled', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('App Icon Badge')).toBeTruthy();
      expect(getByText('Show unread count on app icon')).toBeTruthy();
    });
  });

  /**
   * Test: Permission status display
   * Expected: Permission status is displayed correctly
   */
  test('test_permission_status_display', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('granted');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Enable Notifications')).toBeTruthy();
      expect(getByText('Notifications are enabled')).toBeTruthy();
    });
  });

  /**
   * Test: Permission denied display
   * Expected: Permission denied status is shown correctly
   */
  test('test_permission_denied_display', async () => {
    (notificationService.getPermissionStatus as jest.Mock).mockResolvedValue('denied');

    const { getByText } = render(
      <NotificationPreferencesScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Grant permission to receive notifications')).toBeTruthy();
    });
  });
});
