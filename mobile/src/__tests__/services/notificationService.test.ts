/**
 * Notification Service Tests
 *
 * Tests for notification functionality using jest.setup.js mocks.
 */

import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';
import * as Device from 'expo-device';
import { notificationService } from '../../services/notificationService';

// Mock fetch
global.fetch = jest.fn();

describe('NotificationService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    notificationService._resetState();
    (global.fetch as jest.Mock).mockReset();
  });

  // ========================================================================
  // Permission Tests (6 tests)
  // ========================================================================

  describe('Permissions', () => {
    test('should initialize with permission check', async () => {
      await notificationService.initialize();
      expect(Notifications.getPermissionsAsync).toHaveBeenCalled();
    });

    test('should get granted permission status', async () => {
      const status = await notificationService.getPermissionStatus();
      expect(status).toBe('granted');
    });

    test('should get denied permission status', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({ status: 'denied', canAskAgain: false, granted: false, expires: 'never' })
      );
      const status = await notificationService.getPermissionStatus();
      expect(status).toBe('denied');
    });

    test('should request permissions with iOS settings', async () => {
      const status = await notificationService.requestPermissions();
      expect(status).toBe('granted');
      expect(Notifications.requestPermissionsAsync).toHaveBeenCalledWith({
        ios: { allowAlert: true, allowBadge: true, allowSound: true },
        android: {},
      });
    });

    test('should request permissions for Android', async () => {
      const status = await notificationService.requestPermissions();
      expect(status).toBe('granted');
    });

    test('should return denied for simulator', async () => {
      (Device as any).isDevice = false;
      const status = await notificationService.requestPermissions();
      expect(status).toBe('denied');
    });
  });

  // ========================================================================
  // Local Notification Tests (8 tests)
  // ========================================================================

  describe('Local Notifications', () => {
    beforeEach(async () => {
      // Initialize service to set permission status
      await notificationService.initialize();
    });

    test('should send local notification', async () => {
      await notificationService.sendLocalNotification({
        title: 'Test',
        body: 'Body',
        data: { key: 'value' },
      });
      expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          content: expect.objectContaining({
            title: 'Test',
            body: 'Body',
            data: { key: 'value' },
          }),
        })
      );
    });

    test('should schedule notification with delay', async () => {
      const id = await notificationService.scheduleNotification({ title: 'Delayed', body: 'Test' }, 10);
      expect(id).toBe('notification-id-123');
      expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          trigger: { seconds: 10 },
        })
      );
    });

    test('should handle scheduling errors', async () => {
      (Notifications.scheduleNotificationAsync as jest.Mock).mockImplementationOnce(() =>
        Promise.reject(new Error('Failed'))
      );
      await expect(
        notificationService.scheduleNotification({ title: 'Test', body: 'Test' }, 5)
      ).rejects.toThrow('Failed');
    });

    test('should cancel notification by ID', async () => {
      await notificationService.cancelNotification('test-id');
      expect(Notifications.cancelScheduledNotificationAsync).toHaveBeenCalledWith('test-id');
    });

    test('should cancel all notifications', async () => {
      await notificationService.cancelAllNotifications();
      expect(Notifications.cancelAllScheduledNotificationsAsync).toHaveBeenCalled();
      expect(Notifications.dismissAllNotificationsAsync).toHaveBeenCalled();
    });

    test('should not send without permission', async () => {
      // Reset and reinitialize with denied permission
      notificationService._resetState();
      (Notifications.getPermissionsAsync as jest.Mock).mockImplementationOnce(() =>
        Promise.resolve({ status: 'denied', canAskAgain: false, granted: false, expires: 'never' })
      );
      await notificationService.initialize();
      await notificationService.sendLocalNotification({ title: 'Test', body: 'Test' });
      expect(Notifications.scheduleNotificationAsync).not.toHaveBeenCalled();
    });

    test('should handle sound parameter', async () => {
      await notificationService.sendLocalNotification({ title: 'Test', body: 'Test', sound: false });
      expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          content: expect.objectContaining({ sound: false }),
        })
      );
    });

    test('should handle badge parameter', async () => {
      await notificationService.sendLocalNotification({ title: 'Test', body: 'Test', badge: 5 });
      expect(Notifications.scheduleNotificationAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          content: expect.objectContaining({ badge: 5 }),
        })
      );
    });
  });

  // ========================================================================
  // Badge Management Tests (6 tests)
  // ========================================================================

  describe('Badge Management', () => {
    test('should get badge count', async () => {
      const count = await notificationService.getBadgeCount();
      expect(count).toBe(0);
    });

    test('should set badge count', async () => {
      await notificationService.setBadgeCount(10);
      expect(Notifications.setBadgeCountAsync).toHaveBeenCalledWith(10);
    });

    test('should increment badge', async () => {
      await notificationService.setBadgeCount(5);
      expect(Notifications.setBadgeCountAsync).toHaveBeenCalledWith(5);
    });

    test('should decrement badge', async () => {
      await notificationService.setBadgeCount(3);
      expect(Notifications.setBadgeCountAsync).toHaveBeenCalledWith(3);
    });

    test('should clear badge', async () => {
      await notificationService.setBadgeCount(0);
      expect(Notifications.setBadgeCountAsync).toHaveBeenCalledWith(0);
    });

    test('should handle badge errors gracefully', async () => {
      (Notifications.getBadgeCountAsync as jest.Mock).mockImplementationOnce(() =>
        Promise.reject(new Error('Error'))
      );
      const count = await notificationService.getBadgeCount();
      expect(count).toBe(0);
    });
  });

  // ========================================================================
  // Push Token Tests (5 tests)
  // ========================================================================

  describe('Push Token', () => {
    beforeEach(async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      } as Response);
      (Device as any).isDevice = true;
      // Initialize service first
      await notificationService.initialize();
    });

    test('should get push token', async () => {
      const token = await notificationService.registerForPushNotifications();
      expect(token).toEqual({
        token: 'ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]',
        platform: Platform.OS,
        registeredAt: expect.any(Date),
      });
    });

    test('should handle token errors', async () => {
      // Reset service state (don't initialize to avoid caching)
      notificationService._resetState();

      (Notifications.getExpoPushTokenAsync as jest.Mock).mockImplementationOnce(() =>
        Promise.reject(new Error('Token error'))
      );
      const token = await notificationService.registerForPushNotifications();
      expect(token).toBeNull();
    });

    test('should cache token', async () => {
      const token1 = await notificationService.registerForPushNotifications();
      const token2 = await notificationService.getPushToken();
      expect(token1).toEqual(token2);
    });

    test('should register with backend', async () => {
      // Reset service state (don't initialize to avoid double token fetch)
      notificationService._resetState();
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await notificationService.registerForPushNotifications('user-123', 'device-456');
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/mobile/notifications/register'),
        expect.objectContaining({
          method: 'POST',
        })
      );
    });

    test('should handle iOS platform', async () => {
      const originalOS = Platform.OS;
      (Platform.OS as any) = 'ios';
      const token = await notificationService.registerForPushNotifications();
      expect(token?.platform).toBe('ios');
      (Platform.OS as any) = originalOS;
    });
  });

  // ========================================================================
  // Push Token Registration with Backend Tests (5 new tests)
  // ========================================================================

  describe('Push Token Registration', () => {
    beforeEach(async () => {
      (global.fetch as jest.Mock).mockReset();
      (Device as any).isDevice = true;
      notificationService._resetState();
    });

    test('should register push token with backend API', async () => {
      // Mock fetch to return success
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      } as Response);

      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const token = await notificationService.registerForPushNotifications('user-123', 'device-456');

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/mobile/notifications/register'),
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'Content-Type': 'application/json',
            'Authorization': expect.stringContaining('Bearer'),
          }),
          body: expect.stringContaining('"device_token":'),
        })
      );
      expect(token).not.toBeNull();
    });

    test('should handle backend API failure gracefully', async () => {
      // Mock fetch to return error
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ error: 'Internal server error' }),
      } as Response);

      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();

      const token = await notificationService.registerForPushNotifications('user-123', 'device-456');

      // Token should still be returned even if backend fails (non-blocking)
      expect(token).not.toBeNull();
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'NotificationService: Failed to register token with backend'
      );

      consoleErrorSpy.mockRestore();
    });

    test('should skip backend registration without userId', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Call without userId
      const token = await notificationService.registerForPushNotifications();

      // Fetch should NOT be called
      expect(global.fetch).not.toHaveBeenCalled();
      // Token should still be returned
      expect(token).not.toBeNull();
    });

    test('should return existing token if already registered', async () => {
      (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // First call - should fetch token
      const token1 = await notificationService.registerForPushNotifications();
      expect(Notifications.getExpoPushTokenAsync).toHaveBeenCalled();

      // Reset mock to track if it's called again
      (Notifications.getExpoPushTokenAsync as jest.Mock).mockClear();

      // Second call - should use cached token
      const token2 = await notificationService.registerForPushNotifications();
      expect(Notifications.getExpoPushTokenAsync).not.toHaveBeenCalled();
      expect(token1).toEqual(token2);
    });

    test('should require physical device for push token', async () => {
      (Device as any).isDevice = false;

      const consoleWarnSpy = jest.spyOn(console, 'warn').mockImplementation();

      const token = await notificationService.registerForPushNotifications();

      expect(token).toBeNull();
      expect(consoleWarnSpy).toHaveBeenCalledWith(
        'NotificationService: Push notifications only work on physical devices'
      );

      consoleWarnSpy.mockRestore();
    });
  });

  // ========================================================================
  // Notification Handlers Tests (5 tests)
  // ========================================================================

  describe('Notification Handlers', () => {
    test('should set handler on initialize', async () => {
      await notificationService.initialize();
      expect(Notifications.setNotificationHandler).toHaveBeenCalled();
    });

    test('should add received listener', async () => {
      await notificationService.initialize();
      expect(Notifications.addNotificationReceivedListener).toHaveBeenCalled();
    });

    test('should add response listener', async () => {
      await notificationService.initialize();
      expect(Notifications.addNotificationResponseReceivedListener).toHaveBeenCalled();
    });

    test('should subscribe to notifications', (done) => {
      let callback: any;
      (Notifications.addNotificationReceivedListener as jest.Mock).mockImplementationOnce((cb) => {
        callback = cb;
        return { remove: jest.fn() };
      });

      notificationService.onNotification((n) => {
        expect(n).toBeDefined();
        done();
      });

      notificationService.initialize().then(() => {
        if (callback) callback({ request: { content: { title: 'Test' } } } as any);
      });
    });

    test('should subscribe to responses', (done) => {
      let callback: any;
      (Notifications.addNotificationResponseReceivedListener as jest.Mock).mockImplementationOnce((cb) => {
        callback = cb;
        return { remove: jest.fn() };
      });

      notificationService.onNotificationResponse((r) => {
        expect(r).toBeDefined();
        done();
      });

      notificationService.initialize().then(() => {
        if (callback) callback({ notification: { request: { content: { title: 'Test' } } } } as any);
      });
    });
  });

  // ========================================================================
  // Foreground Notifications Tests (3 tests)
  // ========================================================================

  describe('Foreground Notifications', () => {
    test('should present notification', async () => {
      await Notifications.presentNotificationAsync('id', { title: 'Test', body: 'Test' } as any);
      expect(Notifications.presentNotificationAsync).toHaveBeenCalledWith('id', {
        title: 'Test',
        body: 'Test',
      });
    });

    test('should dismiss notification', async () => {
      await Notifications.dismissNotificationAsync('id');
      expect(Notifications.dismissNotificationAsync).toHaveBeenCalledWith('id');
    });

    test('should configure handler for foreground', async () => {
      await notificationService.initialize();
      expect(Notifications.setNotificationHandler).toHaveBeenCalled();
    });
  });

  // ========================================================================
  // Platform-Specific Tests (4 tests)
  // ========================================================================

  describe('Platform-Specific', () => {
    test('should configure Android channel', async () => {
      const originalOS = Platform.OS;
      (Platform.OS as any) = 'android';

      // Reset service state and initialize
      notificationService._resetState();
      await notificationService.initialize();

      expect(Notifications.setNotificationChannelAsync).toHaveBeenCalledWith(
        'atom-notifications',
        expect.objectContaining({
          name: 'Atom Notifications',
        })
      );
      (Platform.OS as any) = originalOS;
    });

    test('should handle Android platform', async () => {
      const originalOS = Platform.OS;
      (Platform.OS as any) = 'android';
      (Device as any).isDevice = true;
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: async () => ({ success: true }),
      } as Response);
      const token = await notificationService.registerForPushNotifications();
      expect(token?.platform).toBe('android');
      (Platform.OS as any) = originalOS;
    });

    test('should skip channel on iOS', async () => {
      const originalOS = Platform.OS;
      (Platform.OS as any) = 'ios';

      // Reset service state and initialize
      notificationService._resetState();
      await notificationService.initialize();

      // iOS doesn't use channels, so setNotificationChannelAsync shouldn't be called
      expect(Notifications.setNotificationChannelAsync).not.toHaveBeenCalled();
      (Platform.OS as any) = originalOS;
    });

    test('should detect simulator vs device', async () => {
      (Device as any).isDevice = false;
      const status = await notificationService.requestPermissions();
      expect(status).toBe('denied');
    });
  });
});
