/**
 * Notification Service
 *
 * Manages push notifications for mobile devices using:
 * - FCM (Firebase Cloud Messaging) for Android
 * - APNs (Apple Push Notification Service) for iOS
 *
 * Features:
 * - Push token registration
 * - Notification permission handling
 * - Local notification scheduling
 * - In-app notification handling
 * - Badge count management
 */

import { Notifications, Notification } from 'expo-notifications';
import { Platform } from 'react-native';
import * as Device from 'expo-device';
import Constants from 'expo-constants';

// Types
export type NotificationPermissionStatus = 'undetermined' | 'granted' | 'denied';

export interface PushToken {
  token: string;
  platform: 'ios' | 'android';
  userId?: string;
  deviceId?: string;
  registeredAt: Date;
}

export interface LocalNotification {
  title: string;
  body: string;
  data?: any;
  sound?: boolean | string;
  badge?: number;
  channelId?: string; // Android only
}

export interface NotificationPayload {
  title: string;
  body: string;
  data?: any;
  sound?: string;
  badge?: number;
  priority?: 'high' | 'normal' | 'low';
  ttl?: number; // Time to live in seconds
}

// Configuration
const ANDROID_CHANNEL_ID = 'atom-notifications';
const ANDROID_CHANNEL_NAME = 'Atom Notifications';
const ANDROID_CHANNEL_DESCRIPTION = 'Notifications from Atom AI Automation Platform';

/**
 * Notification Service
 */
class NotificationService {
  private pushToken: PushToken | null = null;
  private permissionStatus: NotificationPermissionStatus = 'undetermined';
  private notificationListeners: Set<(notification: Notification) => void> = new Set();
  private responseListeners: Set<(response: any) => void> = new Set();

  /**
   * Reset service state (for testing)
   */
  _resetState(): void {
    this.pushToken = null;
    this.permissionStatus = 'undetermined';
    this.notificationListeners.clear();
    this.responseListeners.clear();
  }

  /**
   * Initialize the notification service
   */
  async initialize(): Promise<void> {
    try {
      // Configure notification channels for Android
      if (Platform.OS === 'android') {
        await this.configureAndroidChannel();
      }

      // Set notification handler
      this.setNotificationHandler();

      // Check initial permission status
      const settings = await Notifications.getPermissionsAsync();
      this.permissionStatus = settings.granted ? 'granted' : settings.ios?.status || 'denied';

      // Add notification received listener
      Notifications.addNotificationReceivedListener((notification) => {
        console.log('Notification received:', notification);
        this.notifyListeners(notification);
      });

      // Add notification response listener
      Notifications.addNotificationResponseReceivedListener((response) => {
        console.log('Notification response:', response);
        this.notifyResponseListeners(response);
      });

      // Register for push notifications
      await this.registerForPushNotifications();

      console.log('NotificationService: Initialized');
    } catch (error) {
      console.error('NotificationService: Failed to initialize:', error);
    }
  }

  /**
   * Request notification permissions
   */
  async requestPermissions(): Promise<NotificationPermissionStatus> {
    try {
      if (!Device.isDevice) {
        console.warn('NotificationService: Push notifications only work on physical devices');
        this.permissionStatus = 'denied';
        return 'denied';
      }

      const settings = await Notifications.requestPermissionsAsync({
        ios: {
          allowAlert: true,
          allowBadge: true,
          allowSound: true,
        },
        android: {},
      });

      this.permissionStatus = settings.granted ? 'granted' : settings.ios?.status || 'denied';

      if (this.permissionStatus === 'granted') {
        // Register for push notifications after permission granted
        await this.registerForPushNotifications();
      }

      console.log('NotificationService: Permission status:', this.permissionStatus);
      return this.permissionStatus;
    } catch (error) {
      console.error('NotificationService: Failed to request permissions:', error);
      this.permissionStatus = 'denied';
      return 'denied';
    }
  }

  /**
   * Check current permission status
   */
  async getPermissionStatus(): Promise<NotificationPermissionStatus> {
    try {
      const settings = await Notifications.getPermissionsAsync();
      this.permissionStatus = settings.granted ? 'granted' : settings.ios?.status || 'denied';
      return this.permissionStatus;
    } catch (error) {
      console.error('NotificationService: Failed to get permission status:', error);
      this.permissionStatus = 'denied';
      return this.permissionStatus;
    }
  }

  /**
   * Register for push notifications (FCM/APNs)
   */
  async registerForPushNotifications(userId?: string, deviceId?: string): Promise<PushToken | null> {
    try {
      if (!Device.isDevice) {
        console.warn('NotificationService: Push notifications only work on physical devices');
        return null;
      }

      // Check if we already have a token
      if (this.pushToken) {
        console.log('NotificationService: Push token already registered');
        return this.pushToken;
      }

      // Check permissions first
      const settings = await Notifications.getPermissionsAsync();
      if (!settings.granted) {
        console.warn('NotificationService: Notification permissions not granted');
        return null;
      }

      // Get push token
      const { data: tokenData } = await Notifications.getExpoPushTokenAsync({
        projectId: Constants.expoConfig?.extra?.eas?.projectId,
      });

      const token: PushToken = {
        token: tokenData,
        platform: Platform.OS as 'ios' | 'android',
        userId,
        deviceId,
        registeredAt: new Date(),
      };

      this.pushToken = token;

      // Send token to backend for registration
      if (userId && deviceId) {
        await this.registerTokenWithBackend(token);
      }

      console.log('NotificationService: Push token registered', token.platform);
      return token;
    } catch (error: any) {
      console.error('NotificationService: Failed to register for push notifications:', error);
      if (error?.code === 'E_NOTIFICATIONS_TOKEN_NOT_REGISTERED') {
        console.warn('NotificationService: Must request permissions first');
      }
      return null;
    }
  }

  /**
   * Register push token with backend
   */
  private async registerTokenWithBackend(token: PushToken): Promise<void> {
    try {
      // Use Constants.expoConfig pattern for Jest compatibility (avoids expo/virtual/env babel transform)
      const API_BASE_URL = Constants.expoConfig?.extra?.apiUrl || 'http://localhost:8000';
      const authToken = await this.getAuthToken();

      const response = await fetch(`${API_BASE_URL}/api/mobile/notifications/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          device_token: token.token,
          platform: token.platform,
          notification_enabled: true,
        }),
      });

      if (response.ok) {
        console.log('NotificationService: Token registered with backend');
      } else {
        console.error('NotificationService: Failed to register token with backend');
      }
    } catch (error) {
      console.error('NotificationService: Error registering token with backend:', error);
    }
  }

  /**
   * Send local notification
   */
  async sendLocalNotification(notification: LocalNotification): Promise<void> {
    try {
      if (this.permissionStatus !== 'granted') {
        console.warn('NotificationService: Permission not granted');
        return;
      }

      await Notifications.scheduleNotificationAsync({
        content: {
          title: notification.title,
          body: notification.body,
          data: notification.data,
          sound: notification.sound ?? true,
          badge: notification.badge,
        },
        trigger: null, // Show immediately
        identifier: Date.now().toString(),
      });

      console.log('NotificationService: Local notification sent');
    } catch (error) {
      console.error('NotificationService: Failed to send local notification:', error);
    }
  }

  /**
   * Schedule notification for later
   */
  async scheduleNotification(
    notification: LocalNotification,
    triggerSeconds: number
  ): Promise<string> {
    try {
      if (this.permissionStatus !== 'granted') {
        throw new Error('Permission not granted');
      }

      const identifier = await Notifications.scheduleNotificationAsync({
        content: {
          title: notification.title,
          body: notification.body,
          data: notification.data,
          sound: notification.sound ?? true,
          badge: notification.badge,
        },
        trigger: {
          seconds: triggerSeconds,
        },
        identifier: Date.now().toString(),
      });

      console.log(`NotificationService: Notification scheduled for ${triggerSeconds}s from now`);
      return identifier;
    } catch (error) {
      console.error('NotificationService: Failed to schedule notification:', error);
      throw error;
    }
  }

  /**
   * Cancel scheduled notification
   */
  async cancelNotification(identifier: string): Promise<void> {
    try {
      await Notifications.cancelScheduledNotificationAsync(identifier);
      console.log('NotificationService: Notification cancelled');
    } catch (error) {
      console.error('NotificationService: Failed to cancel notification:', error);
    }
  }

  /**
   * Cancel all notifications
   */
  async cancelAllNotifications(): Promise<void> {
    try {
      await Notifications.cancelAllScheduledNotificationsAsync();
      await Notifications.dismissAllNotificationsAsync();
      console.log('NotificationService: All notifications cancelled');
    } catch (error) {
      console.error('NotificationService: Failed to cancel all notifications:', error);
    }
  }

  /**
   * Set badge count
   */
  async setBadgeCount(count: number): Promise<void> {
    try {
      await Notifications.setBadgeCountAsync(count);
      console.log('NotificationService: Badge count set to', count);
    } catch (error) {
      console.error('NotificationService: Failed to set badge count:', error);
    }
  }

  /**
   * Get badge count
   */
  async getBadgeCount(): Promise<number> {
    try {
      return await Notifications.getBadgeCountAsync();
    } catch (error) {
      console.error('NotificationService: Failed to get badge count:', error);
      return 0;
    }
  }

  /**
   * Subscribe to notification events
   */
  onNotification(callback: (notification: Notification) => void): () => void {
    this.notificationListeners.add(callback);
    return () => {
      this.notificationListeners.delete(callback);
    };
  }

  /**
   * Subscribe to notification response events
   */
  onNotificationResponse(callback: (response: any) => void): () => void {
    this.responseListeners.add(callback);
    return () => {
      this.responseListeners.delete(callback);
    };
  }

  // Private helper methods

  private async configureAndroidChannel(): Promise<void> {
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync(ANDROID_CHANNEL_ID, {
        name: ANDROID_CHANNEL_NAME,
        importance: Notifications.AndroidImportance.HIGH,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#FF231F7C',
      });
    }
  }

  private setNotificationHandler(): void {
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowAlert: true,
        shouldPlaySound: true,
        shouldSetBadge: true,
      }),
    });
  }

  private async getAuthToken(): Promise<string | null> {
    try {
      // Import storage service
      const storageService = (await import('./storageService')).storageService;
      return await storageService.getStringAsync('auth_token' as any);
    } catch (error) {
      console.error('NotificationService: Failed to get auth token:', error);
      return null;
    }
  }

  private notifyListeners(notification: Notification): void {
    this.notificationListeners.forEach((callback) => {
      try {
        callback(notification);
      } catch (error) {
        console.error('NotificationService: Listener error:', error);
      }
    });
  }

  private notifyResponseListeners(response: any): void {
    this.responseListeners.forEach((callback) => {
      try {
        callback(response);
      } catch (error) {
        console.error('NotificationService: Response listener error:', error);
      }
    });
  }

  /**
   * Get current push token
   */
  getPushToken(): PushToken | null {
    return this.pushToken;
  }
}

// Export singleton instance
export const notificationService = new NotificationService();

export default notificationService;
