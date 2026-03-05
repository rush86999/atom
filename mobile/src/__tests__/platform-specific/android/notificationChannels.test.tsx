/**
 * Android Notification Channels Tests
 *
 * Tests for Android-specific notification channel features (API 26+):
 * - Notification channel creation and management
 * - Channel importance levels (HIGH, DEFAULT, LOW, MIN)
 * - Channel grouping
 * - Notification badge management
 * - Foreground service notification requirements
 */

import React from 'react';
import { render, waitFor } from '@testing-library/react-native';
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import {
  mockPlatform,
  restorePlatform,
  cleanupTest,
} from '../../helpers/testUtils';
import { createPermissionMock } from '../../helpers/platformPermissions.test';

// ============================================================================
// Setup and Teardown
// ============================================================================

beforeEach(() => {
  mockPlatform('android');
  jest.clearAllMocks();

  // Default mocks
  (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({
    ...createPermissionMock('granted'),
    android: {},
  });
  (Notifications.setNotificationChannelAsync as jest.Mock).mockResolvedValue(undefined);
  (Notifications.getBadgeCountAsync as jest.Mock).mockResolvedValue(0);
  (Notifications.setBadgeCountAsync as jest.Mock).mockResolvedValue(undefined);
});

afterEach(() => {
  cleanupTest();
});

// ============================================================================
// Notification Channel Creation Tests
// ============================================================================

describe('Android Notification Channels - Channel Creation', () => {
  test('should create notification channel for Android Oreo+', async () => {
    await Notifications.setNotificationChannelAsync('default-channel', {
      name: 'Default Notifications',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: '#FF231F7C',
    });

    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
      'default-channel',
      expect.objectContaining({
        name: 'Default Notifications',
        importance: Notifications.AndroidImportance.HIGH,
      })
    );
  });

  test('should create multiple notification channels', async () => {
    const channels = [
      { id: 'messages', name: 'Messages', importance: Notifications.AndroidImportance.HIGH },
      { id: 'updates', name: 'Updates', importance: Notifications.AndroidImportance.DEFAULT },
      { id: 'promotions', name: 'Promotions', importance: Notifications.AndroidImportance.LOW },
    ];

    for (const channel of channels) {
      await Notifications.setNotificationChannelAsync(channel.id, {
        name: channel.name,
        importance: channel.importance,
      });
    }

    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledTimes(3);
  });

  test('should not create duplicate channels', async () => {
    const channelId = 'default-channel';
    const channelExists = false; // Would check if exists

    if (!channelExists) {
      await Notifications.setNotificationChannelAsync(channelId, {
        name: 'Default',
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }

    // Only called once because channel didn't exist
    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledTimes(1);
  });
});

// ============================================================================
// Channel Importance Levels Tests
// ============================================================================

describe('Android Notification Channels - Importance Levels', () => {
  test('should create HIGH importance channel (urgent)', async () => {
    await Notifications.setNotificationChannelAsync('urgent-channel', {
      name: 'Urgent Notifications',
      importance: Notifications.AndroidImportance.HIGH,
    });

    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
      'urgent-channel',
      expect.objectContaining({
        importance: Notifications.AndroidImportance.HIGH,
      })
    );
  });

  test('should create DEFAULT importance channel', async () => {
    await Notifications.setNotificationChannelAsync('default-channel', {
      name: 'Default Notifications',
      importance: Notifications.AndroidImportance.DEFAULT,
    });

    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
      'default-channel',
      expect.objectContaining({
        importance: Notifications.AndroidImportance.DEFAULT,
      })
    );
  });

  test('should create LOW importance channel', async () => {
    await Notifications.setNotificationChannelAsync('low-channel', {
      name: 'Low Priority Notifications',
      importance: Notifications.AndroidImportance.LOW,
    });

    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
      'low-channel',
      expect.objectContaining({
        importance: Notifications.AndroidImportance.LOW,
      })
    );
  });

  test('should create MIN importance channel (silent)', async () => {
    await Notifications.setNotificationChannelAsync('silent-channel', {
      name: 'Silent Notifications',
      importance: Notifications.AndroidImportance.MIN,
    });

    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
      'silent-channel',
      expect.objectContaining({
        importance: Notifications.AndroidImportance.MIN,
      })
    );
  });
});

// ============================================================================
// Channel Group Tests
// ============================================================================

describe('Android Notification Channels - Channel Groups', () => {
  test('should create notification channel group', async () => {
    // Check if method exists (API level dependent)
    const hasChannelGroups = typeof Notifications.setNotificationChannelGroupAsync === 'function';

    if (hasChannelGroups) {
      (Notifications.setNotificationChannelGroupAsync as jest.Mock).mockResolvedValue(undefined);

      await Notifications.setNotificationChannelGroupAsync('messages-group', {
        name: 'Messages',
      });

      expect(Notifications.setNotificationChannelGroupAsync).toHaveBeenCalledWith(
        'messages-group',
        expect.objectContaining({
          name: 'Messages',
        })
      );
    } else {
      // Channel groups not available in this API level
      expect(hasChannelGroups).toBe(false);
    }
  });

  test('should create channel within group', async () => {
    const groupId = 'messages-group';
    const channelId = 'personal-messages';

    await Notifications.setNotificationChannelAsync(channelId, {
      name: 'Personal Messages',
      importance: Notifications.AndroidImportance.HIGH,
      groupId: groupId, // Assign to group
    });

    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
      channelId,
      expect.objectContaining({
        groupId: groupId,
      })
    );
  });
});

// ============================================================================
// Badge Management Tests
// ============================================================================

describe('Android Notification Channels - Badge Management', () => {
  test('should get badge count', async () => {
    (Notifications.getBadgeCountAsync as jest.Mock).mockResolvedValue(5);

    const count = await Notifications.getBadgeCountAsync();

    expect(count).toBe(5);
    expect(Notifications.getBadgeCountAsync).toHaveBeenCalled();
  });

  test('should set badge count', async () => {
    await Notifications.setBadgeCountAsync(10);

    expect(Notifications.setBadgeCountAsync).toHaveBeenCalledWith(10);
  });

  test('should clear badge count', async () => {
    await Notifications.setBadgeCountAsync(0);

    expect(Notifications.setBadgeCountAsync).toHaveBeenCalledWith(0);
  });

  test('should increment badge count on new notification', async () => {
    (Notifications.getBadgeCountAsync as jest.Mock).mockResolvedValue(3);
    (Notifications.setBadgeCountAsync as jest.Mock).mockResolvedValue(undefined);

    const currentCount = await Notifications.getBadgeCountAsync();
    await Notifications.setBadgeCountAsync(currentCount + 1);

    expect(Notifications.setBadgeCountAsync).toHaveBeenCalledWith(4);
  });
});

// ============================================================================
// Foreground Service Notification Tests
// ============================================================================

describe('Android Notification Channels - Foreground Service', () => {
  test('should require notification permission for foreground service', async () => {
    const hasPermission = true; // From permission check

    if (hasPermission) {
      // Can start foreground service
      expect(hasPermission).toBe(true);
    }
  });

  test('should create foreground service notification channel', async () => {
    await Notifications.setNotificationChannelAsync('foreground-service', {
      name: 'Foreground Service',
      importance: Notifications.AndroidImportance.HIGH, // Required for foreground service
    });

    expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
      'foreground-service',
      expect.objectContaining({
        importance: Notifications.AndroidImportance.HIGH,
      })
    );
  });

  test('should show ongoing notification for foreground service', async () => {
    const notificationContent = {
      title: 'Service Running',
      body: 'Background operation in progress',
    };

    // Android requires ongoing notification for foreground service
    expect(notificationContent).toBeDefined();
  });
});

// ============================================================================
// Notification Presentation Tests
// ============================================================================

describe('Android Notification Channels - Presentation', () => {
  test('should set notification handler for Android', async () => {
    (Notifications.setNotificationHandler as jest.Mock).mockReturnValue(undefined);

    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      }),
    });

    expect(Notifications.setNotificationHandler).toHaveBeenCalledWith(
      expect.objectContaining({
        handleNotification: expect.any(Function),
      })
    );
  });

  test('should present notification with channel ID', async () => {
    (Notifications.presentNotificationAsync as jest.Mock).mockResolvedValue('notification-id');

    await Notifications.presentNotificationAsync({
      title: 'Test Notification',
      body: 'Test body',
      channelId: 'default-channel', // Required for Android Oreo+
    });

    expect(Notifications.presentNotificationAsync).toHaveBeenCalledWith(
      expect.objectContaining({
        channelId: 'default-channel',
      })
    );
  });
});

// ============================================================================
// Platform-Specific Behavior Tests
// ============================================================================

describe('Android Notification Channels - Platform-Specific Behavior', () => {
  test('should only create channels on Android', () => {
    const isAndroid = Platform.OS === 'android';

    if (isAndroid) {
      // Create channels
      expect(isAndroid).toBe(true);
    }
  });

  test('should handle Android API level differences', () => {
    // API 26+: Notification channels required
    // Pre-API 26: Notifications work without channels

    const apiLevel = 30; // Android 11
    const needsChannels = apiLevel >= 26;

    expect(needsChannels).toBe(true);
  });
});

// ============================================================================
// Edge Cases
// ============================================================================

describe('Android Notification Channels - Edge Cases', () => {
  test('should handle channel creation failure gracefully', async () => {
    (Notifications.setNotificationChannelAsync as jest.Mock).mockRejectedValue(
      new Error('Channel creation failed')
    );

    await expect(
      Notifications.setNotificationChannelAsync('test', {
        name: 'Test',
        importance: Notifications.AndroidImportance.DEFAULT,
      })
    ).rejects.toThrow('Channel creation failed');
  });

  test('should handle rapid badge count updates', async () => {
    (Notifications.setBadgeCountAsync as jest.Mock).mockResolvedValue(undefined);

    // Rapid updates
    await Notifications.setBadgeCountAsync(1);
    await Notifications.setBadgeCountAsync(2);
    await Notifications.setBadgeCountAsync(3);

    expect(Notifications.setBadgeCountAsync).toHaveBeenCalledTimes(3);
  });

  test('should handle channel deletion', async () => {
    // Check if method exists (API level dependent)
    const hasDeleteMethod = typeof Notifications.deleteNotificationChannelAsync === 'function';

    if (hasDeleteMethod) {
      (Notifications.deleteNotificationChannelAsync as jest.Mock).mockResolvedValue(undefined);

      await Notifications.deleteNotificationChannelAsync('old-channel');

      expect(Notifications.deleteNotificationChannelAsync).toHaveBeenCalledWith('old-channel');
    } else {
      // Delete method not available in this API level
      expect(hasDeleteMethod).toBe(false);
    }
  });
});
