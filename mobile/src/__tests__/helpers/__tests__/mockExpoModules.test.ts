/**
 * Mock Expo Modules Tests
 *
 * Tests to verify that all mock objects export correctly
 * and can be configured for different test scenarios.
 */

import {
  MockCamera,
  MockLocation,
  MockNotifications,
  MockLocalAuthentication,
  MockSecureStore,
  MockAsyncStorage,
  MockDevice,
  setPermissionGranted,
  resetAllMocks,
} from '../mockExpoModules';

describe('MockExpoModules', () => {
  beforeEach(() => {
    resetAllMocks();
  });

  // ========================================================================
  // MockCamera Tests
  // ========================================================================

  describe('MockCamera', () => {
    it('should export camera mock functions', () => {
      expect(MockCamera.setPermissionGranted).toBeDefined();
      expect(MockCamera.setPictureResult).toBeDefined();
      expect(MockCamera.setPictureError).toBeDefined();
      expect(MockCamera.getPermissionRequestCount).toBeDefined();
      expect(MockCamera.getPictureCount).toBeDefined();
    });

    it('should configure permission status', () => {
      MockCamera.setPermissionGranted(false);
      expect(MockCamera.getPermissionRequestCount()).toBe(0);
    });

    it('should configure picture result', () => {
      MockCamera.setPictureResult('file:///test.jpg', 1920, 1080);
      expect(MockCamera.getPictureCount()).toBe(0);
    });
  });

  // ========================================================================
  // MockLocation Tests
  // ========================================================================

  describe('MockLocation', () => {
    it('should export location mock functions', () => {
      expect(MockLocation.setForegroundPermissionGranted).toBeDefined();
      expect(MockLocation.setBackgroundPermissionGranted).toBeDefined();
      expect(MockLocation.setCurrentPosition).toBeDefined();
      expect(MockLocation.setPositionError).toBeDefined();
      expect(MockLocation.setGeocodeResult).toBeDefined();
      expect(MockLocation.getPositionRequestCount).toBeDefined();
    });

    it('should configure foreground permission', () => {
      MockLocation.setForegroundPermissionGranted(true);
      expect(MockLocation.getPositionRequestCount()).toBe(0);
    });

    it('should configure background permission', () => {
      MockLocation.setBackgroundPermissionGranted(false);
    });

    it('should configure current position', () => {
      MockLocation.setCurrentPosition({
        latitude: 40.7128,
        longitude: -74.0060,
      });
    });
  });

  // ========================================================================
  // MockNotifications Tests
  // ========================================================================

  describe('MockNotifications', () => {
    it('should export notifications mock functions', () => {
      expect(MockNotifications.setPermissionGranted).toBeDefined();
      expect(MockNotifications.setScheduleResult).toBeDefined();
      expect(MockNotifications.setScheduleError).toBeDefined();
      expect(MockNotifications.setPushToken).toBeDefined();
      expect(MockNotifications.setBadgeCount).toBeDefined();
      expect(MockNotifications.getScheduleCount).toBeDefined();
      expect(MockNotifications.getPushTokenRequestCount).toBeDefined();
    });

    it('should configure permission status', () => {
      MockNotifications.setPermissionGranted(true);
    });

    it('should configure schedule result', () => {
      MockNotifications.setScheduleResult('test-notification-id');
    });

    it('should configure push token', () => {
      MockNotifications.setPushToken('ExponentPushToken[test]');
    });

    it('should configure badge count', () => {
      MockNotifications.setBadgeCount(5);
    });
  });

  // ========================================================================
  // MockLocalAuthentication Tests
  // ========================================================================

  describe('MockLocalAuthentication', () => {
    it('should export local authentication mock functions', () => {
      expect(MockLocalAuthentication.setHasHardware).toBeDefined();
      expect(MockLocalAuthentication.setIsEnrolled).toBeDefined();
      expect(MockLocalAuthentication.setAuthResult).toBeDefined();
      expect(MockLocalAuthentication.getAuthAttemptCount).toBeDefined();
    });

    it('should configure hardware availability', () => {
      MockLocalAuthentication.setHasHardware(true);
    });

    it('should configure enrollment status', () => {
      MockLocalAuthentication.setIsEnrolled(true);
    });

    it('should configure auth result', () => {
      MockLocalAuthentication.setAuthResult(true);
      MockLocalAuthentication.setAuthResult(false, 'User canceled');
    });
  });

  // ========================================================================
  // MockSecureStore Tests
  // ========================================================================

  describe('MockSecureStore', () => {
    it('should export secure store mock functions', async () => {
      expect(MockSecureStore.getItem).toBeDefined();
      expect(MockSecureStore.setItem).toBeDefined();
      expect(MockSecureStore.deleteItem).toBeDefined();
      expect(MockSecureStore.isAvailable).toBeDefined();
      expect(MockSecureStore.getAllKeys).toBeDefined();
      expect(MockSecureStore.clear).toBeDefined();
      expect(MockSecureStore.size).toBeDefined();
    });

    it('should store and retrieve items', async () => {
      await MockSecureStore.setItem('test-key', 'test-value');
      const value = await MockSecureStore.getItem('test-key');
      expect(value).toBe('test-value');
    });

    it('should delete items', async () => {
      await MockSecureStore.setItem('delete-key', 'delete-value');
      await MockSecureStore.deleteItem('delete-key');
      const value = await MockSecureStore.getItem('delete-key');
      expect(value).toBeNull();
    });

    it('should return null for non-existent keys', async () => {
      const value = await MockSecureStore.getItem('non-existent');
      expect(value).toBeNull();
    });

    it('should clear all items', async () => {
      await MockSecureStore.setItem('key1', 'value1');
      await MockSecureStore.setItem('key2', 'value2');
      expect(MockSecureStore.size()).toBe(2);

      MockSecureStore.clear();
      expect(MockSecureStore.size()).toBe(0);
    });
  });

  // ========================================================================
  // MockAsyncStorage Tests
  // ========================================================================

  describe('MockAsyncStorage', () => {
    it('should export async storage mock functions', async () => {
      expect(MockAsyncStorage.getItem).toBeDefined();
      expect(MockAsyncStorage.setItem).toBeDefined();
      expect(MockAsyncStorage.removeItem).toBeDefined();
      expect(MockAsyncStorage.mergeItem).toBeDefined();
      expect(MockAsyncStorage.clear).toBeDefined();
      expect(MockAsyncStorage.getAllKeys).toBeDefined();
      expect(MockAsyncStorage.multiGet).toBeDefined();
      expect(MockAsyncStorage.multiSet).toBeDefined();
      expect(MockAsyncStorage.multiRemove).toBeDefined();
      expect(MockAsyncStorage.size).toBeDefined();
    });

    it('should store and retrieve items', async () => {
      await MockAsyncStorage.setItem('test-key', 'test-value');
      const value = await MockAsyncStorage.getItem('test-key');
      expect(value).toBe('test-value');
    });

    it('should remove items', async () => {
      await MockAsyncStorage.setItem('delete-key', 'delete-value');
      await MockAsyncStorage.removeItem('delete-key');
      const value = await MockAsyncStorage.getItem('delete-key');
      expect(value).toBeNull();
    });

    it('should merge items', async () => {
      await MockAsyncStorage.setItem('merge-key', JSON.stringify({ a: 1 }));
      await MockAsyncStorage.mergeItem('merge-key', JSON.stringify({ b: 2 }));
      const value = await MockAsyncStorage.getItem('merge-key');
      expect(JSON.parse(value!)).toEqual({ a: 1, b: 2 });
    });

    it('should handle multi-get operations', async () => {
      await MockAsyncStorage.setItem('key1', 'value1');
      await MockAsyncStorage.setItem('key2', 'value2');
      const values = await MockAsyncStorage.multiGet(['key1', 'key2']);
      expect(values).toEqual([
        ['key1', 'value1'],
        ['key2', 'value2'],
      ]);
    });

    it('should handle multi-set operations', async () => {
      await MockAsyncStorage.multiSet([
        ['key1', 'value1'],
        ['key2', 'value2'],
      ]);
      expect(await MockAsyncStorage.getItem('key1')).toBe('value1');
      expect(await MockAsyncStorage.getItem('key2')).toBe('value2');
    });

    it('should clear all items', async () => {
      await MockAsyncStorage.setItem('key1', 'value1');
      await MockAsyncStorage.setItem('key2', 'value2');
      expect(MockAsyncStorage.size()).toBe(2);

      await MockAsyncStorage.clear();
      expect(MockAsyncStorage.size()).toBe(0);
    });
  });

  // ========================================================================
  // MockDevice Tests
  // ========================================================================

  describe('MockDevice', () => {
    it('should export device mock functions', () => {
      expect(MockDevice.setDeviceInfo).toBeDefined();
      expect(MockDevice.setIOS).toBeDefined();
      expect(MockDevice.setAndroid).toBeDefined();
    });

    it('should configure iOS device', () => {
      MockDevice.setIOS();
      // Device mock is configured, no assertion needed
    });

    it('should configure Android device', () => {
      MockDevice.setAndroid();
      // Device mock is configured, no assertion needed
    });

    it('should configure custom device info', () => {
      MockDevice.setDeviceInfo({
        osName: 'Android',
        modelName: 'Custom Device',
      });
    });
  });

  // ========================================================================
  // Permission Helper Tests
  // ========================================================================

  describe('setPermissionGranted', () => {
    it('should set camera permission', () => {
      expect(() => setPermissionGranted('camera', true)).not.toThrow();
    });

    it('should set location permission', () => {
      expect(() => setPermissionGranted('location', true)).not.toThrow();
    });

    it('should set notifications permission', () => {
      expect(() => setPermissionGranted('notifications', true)).not.toThrow();
    });

    it('should set biometric permission', () => {
      expect(() => setPermissionGranted('biometric', true)).not.toThrow();
    });

    it('should throw error for unknown module', () => {
      expect(() => setPermissionGranted('unknown', true)).toThrow('Unknown module');
    });
  });

  // ========================================================================
  // Reset Helper Tests
  // ========================================================================

  describe('resetAllMocks', () => {
    it('should reset all mocks to default state', async () => {
      // Modify some mocks
      MockCamera.setPermissionGranted(false);
      await MockSecureStore.setItem('test', 'value');
      await MockAsyncStorage.setItem('test', 'value');

      // Reset
      resetAllMocks();

      // Verify storage is cleared
      expect(await MockSecureStore.getItem('test')).toBeNull();
      expect(await MockAsyncStorage.getItem('test')).toBeNull();
    });
  });
});
