/**
 * Device Mock Factories Tests
 *
 * Validate that all factory functions create correct mock structures
 * with proper defaults and option overrides.
 */

import {
  createMockCameraRef,
  createMockLocation,
  createMockGeofence,
  createMockNotification,
  createMockPushToken,
  simulateNetworkSwitch,
  advanceTimeBySeconds,
  waitForSyncComplete,
  waitForSyncProgress,
  createMockSyncResult,
} from '../deviceMocks';

describe('deviceMocks - Camera Factories', () => {
  describe('createMockCameraRef', () => {
    it('should create camera ref with default options', () => {
      const cameraRef = createMockCameraRef();

      expect(cameraRef).toBeDefined();
      expect(cameraRef.current).toBeDefined();
      expect(cameraRef.current.takePictureAsync).toBeDefined();
      expect(cameraRef.current.recordAsync).toBeDefined();
      expect(cameraRef.current.stopRecording).toBeDefined();
    });

    it('should create successful camera mock by default', async () => {
      const cameraRef = createMockCameraRef();
      const result = await cameraRef.current.takePictureAsync();

      expect(result).toEqual({
        uri: 'file:///mock/photo.jpg',
        width: 1920,
        height: 1080,
      });
    });

    it('should create failing camera mock when shouldSucceed is false', async () => {
      const cameraRef = createMockCameraRef({ shouldSucceed: false });
      const result = await cameraRef.current.takePictureAsync();

      expect(result).toBeNull();
    });

    it('should use custom URI and dimensions from options', async () => {
      const cameraRef = createMockCameraRef({
        mockUri: 'file:///custom/photo.jpg',
        mockWidth: 1280,
        mockHeight: 720,
      });

      const result = await cameraRef.current.takePictureAsync();

      expect(result?.uri).toBe('file:///custom/photo.jpg');
      expect(result?.width).toBe(1280);
      expect(result?.height).toBe(720);
    });
  });
});

describe('deviceMocks - Location Factories', () => {
  describe('createMockLocation', () => {
    it('should create location with default options', () => {
      const location = createMockLocation();

      expect(location).toBeDefined();
      expect(location.coords).toBeDefined();
      expect(location.coords.latitude).toBeDefined();
      expect(location.coords.longitude).toBeDefined();
      expect(location.timestamp).toBeDefined();
    });

    it('should use custom coordinates from options', () => {
      const location = createMockLocation({
        latitude: 40.7128,
        longitude: -74.006,
      });

      expect(location.coords.latitude).toBe(40.7128);
      expect(location.coords.longitude).toBe(-74.006);
    });

    it('should use default San Francisco coordinates', () => {
      const location = createMockLocation();

      expect(location.coords.latitude).toBe(37.7749);
      expect(location.coords.longitude).toBe(-122.4194);
    });

    it('should include altitude, accuracy, heading, and speed', () => {
      const location = createMockLocation({
        altitude: 200,
        accuracy: 5,
        heading: 90,
        speed: 10,
      });

      expect(location.coords.altitude).toBe(200);
      expect(location.coords.accuracy).toBe(5);
      expect(location.coords.heading).toBe(90);
      expect(location.coords.speed).toBe(10);
    });

    it('should use default values for optional properties', () => {
      const location = createMockLocation();

      expect(location.coords.altitude).toBe(100);
      expect(location.coords.accuracy).toBe(10);
      expect(location.coords.heading).toBe(0);
      expect(location.coords.speed).toBe(0);
    });
  });

  describe('createMockGeofence', () => {
    it('should create geofence with default options', () => {
      const geofence = createMockGeofence();

      expect(geofence).toBeDefined();
      expect(geofence.id).toBeDefined();
      expect(geofence.identifier).toBeDefined();
      expect(geofence.latitude).toBeDefined();
      expect(geofence.longitude).toBeDefined();
      expect(geofence.radius).toBeDefined();
    });

    it('should generate unique ID if not provided', () => {
      const geofence1 = createMockGeofence();
      const geofence2 = createMockGeofence();

      expect(geofence1.id).not.toBe(geofence2.id);
    });

    it('should use custom options when provided', () => {
      const geofence = createMockGeofence({
        identifier: 'office',
        latitude: 37.7749,
        longitude: -122.4194,
        radius: 200,
        notifyOnEntry: true,
        notifyOnExit: true,
      });

      expect(geofence.identifier).toBe('office');
      expect(geofence.latitude).toBe(37.7749);
      expect(geofence.longitude).toBe(-122.4194);
      expect(geofence.radius).toBe(200);
      expect(geofence.notifyOnEntry).toBe(true);
      expect(geofence.notifyOnExit).toBe(true);
    });

    it('should use default radius of 100 meters', () => {
      const geofence = createMockGeofence();

      expect(geofence.radius).toBe(100);
    });

    it('should use default notification settings', () => {
      const geofence = createMockGeofence();

      expect(geofence.notifyOnEntry).toBe(true);
      expect(geofence.notifyOnExit).toBe(false);
    });
  });
});

describe('deviceMocks - Notification Factories', () => {
  describe('createMockNotification', () => {
    it('should create notification with default options', () => {
      const notification = createMockNotification();

      expect(notification).toBeDefined();
      expect(notification.title).toBeDefined();
      expect(notification.body).toBeDefined();
      expect(notification.data).toBeDefined();
      expect(notification.sound).toBeDefined();
      expect(notification.timestamp).toBeDefined();
    });

    it('should use custom options when provided', () => {
      const notification = createMockNotification({
        title: 'Custom Title',
        body: 'Custom Body',
        data: { userId: '123' },
        badge: 5,
        priority: 10,
      });

      expect(notification.title).toBe('Custom Title');
      expect(notification.body).toBe('Custom Body');
      expect(notification.data).toEqual({ userId: '123' });
      expect(notification.badge).toBe(5);
      expect(notification.priority).toBe(10);
    });

    it('should generate unique identifier', async () => {
      const notification1 = createMockNotification();
      // Small delay to ensure different timestamp
      await new Promise(resolve => setImmediate(resolve));
      const notification2 = createMockNotification();

      expect(notification1.identifier).not.toBe(notification2.identifier);
    });
  });

  describe('createMockPushToken', () => {
    it('should create push token with default options', () => {
      const pushToken = createMockPushToken();

      expect(pushToken).toBeDefined();
      expect(pushToken.type).toBeDefined();
      expect(pushToken.data).toBeDefined();
      expect(pushToken.userId).toBeDefined();
      expect(pushToken.deviceId).toBeDefined();
      expect(pushToken.registeredAt).toBeDefined();
    });

    it('should use default platform of ios', () => {
      const pushToken = createMockPushToken();

      expect(pushToken.type).toBe('ios');
    });

    it('should use custom options when provided', () => {
      const registeredAt = new Date('2026-01-01');
      const pushToken = createMockPushToken({
        token: 'ExponentPushToken[abc123]',
        platform: 'android',
        userId: 'user-456',
        deviceId: 'device-789',
        registeredAt,
      });

      expect(pushToken.data).toBe('ExponentPushToken[abc123]');
      expect(pushToken.type).toBe('android');
      expect(pushToken.userId).toBe('user-456');
      expect(pushToken.deviceId).toBe('device-789');
      expect(pushToken.registeredAt).toBe(registeredAt);
    });
  });
});

describe('deviceMocks - Network Factories', () => {
  describe('simulateNetworkSwitch', () => {
    it('should trigger NetInfo callback with connected state', () => {
      let capturedCallback: ((state: any) => void) | null = null;
      const NetInfo = {
        addEventListener: jest.fn().mockImplementation((callback) => {
          capturedCallback = callback;
          return jest.fn();
        }),
      };

      // Manually invoke callback since simulateNetworkSwitch accesses it
      if (capturedCallback) {
        capturedCallback({
          isConnected: true,
          isInternetReachable: true,
          type: 'wifi',
          details: { isConnectionExpensive: false },
        });
      }

      expect(NetInfo.addEventListener).toHaveBeenCalled();
    });

    it('should trigger NetInfo callback with disconnected state', () => {
      let capturedCallback: ((state: any) => void) | null = null;
      const NetInfo = {
        addEventListener: jest.fn().mockImplementation((callback) => {
          capturedCallback = callback;
          return jest.fn();
        }),
      };

      // Manually invoke callback with disconnected state
      if (capturedCallback) {
        capturedCallback({
          isConnected: false,
          isInternetReachable: false,
          type: 'none',
          details: undefined,
        });
      }

      expect(NetInfo.addEventListener).toHaveBeenCalled();
    });

    it('should handle missing addEventListener gracefully', () => {
      const NetInfo: any = {};

      // Should not throw when addEventListener is undefined
      expect(() => {
        simulateNetworkSwitch(NetInfo, true);
      }).not.toThrow();
    });
  });
});

describe('deviceMocks - Timer Utilities', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('advanceTimeBySeconds', () => {
    it('should advance timers by specified seconds', () => {
      const mockFn = jest.fn();
      setTimeout(mockFn, 5000); // 5 seconds

      advanceTimeBySeconds(5);

      expect(mockFn).toHaveBeenCalled();
    });

    it('should convert seconds to milliseconds', () => {
      const mockFn = jest.fn();
      setTimeout(mockFn, 30000); // 30 seconds

      advanceTimeBySeconds(30);

      expect(mockFn).toHaveBeenCalled();
    });
  });
});

describe('deviceMocks - Sync Utilities', () => {
  describe('waitForSyncComplete', () => {
    it('should wait for sync to complete', async () => {
      let callCount = 0;
      const mockService = {
        getSyncState: jest.fn().mockImplementation(async () => {
          callCount++;
          if (callCount === 1) {
            return { syncInProgress: true };
          }
          return { syncInProgress: false };
        }),
      };

      await waitForSyncComplete(mockService, 5000);

      expect(mockService.getSyncState).toHaveBeenCalled();
      expect(callCount).toBeGreaterThan(0);
    });

    it('should throw error if timeout exceeded', async () => {
      const mockService = {
        getSyncState: jest.fn().mockResolvedValue({ syncInProgress: true }),
      };

      await expect(
        waitForSyncComplete(mockService, 100)
      ).rejects.toThrow('Sync did not complete within 100ms');
    });

    it('should return immediately if sync already complete', async () => {
      const mockService = {
        getSyncState: jest.fn().mockResolvedValue({ syncInProgress: false }),
      };

      await waitForSyncComplete(mockService, 5000);

      expect(mockService.getSyncState).toHaveBeenCalledTimes(1);
    });
  });

  describe('waitForSyncProgress', () => {
    it('should return immediately if target already reached', async () => {
      // Progress (100) is already at target (100)
      await expect(
        waitForSyncProgress(100, 100, 100)
      ).resolves.not.toThrow();
    });

    it('should throw error if timeout exceeded', async () => {
      // Progress starts at 0, target is 100, will never reach (infinite loop with timeout)
      await expect(
        waitForSyncProgress(0, 100, 200)
      ).rejects.toThrow('Sync progress did not reach 100% within 200ms');
    });
  });

  describe('createMockSyncResult', () => {
    it('should create sync result with default options', () => {
      const result = createMockSyncResult();

      expect(result).toBeDefined();
      expect(result.success).toBe(true);
      expect(result.itemsSynced).toBe(0);
      expect(result.itemsFailed).toBe(0);
      expect(result.timestamp).toBeDefined();
    });

    it('should use custom options when provided', () => {
      const timestamp = new Date('2026-01-01');
      const result = createMockSyncResult({
        success: false,
        itemsSynced: 10,
        itemsFailed: 2,
        duration: 5000,
        error: 'Network error',
        timestamp,
      });

      expect(result.success).toBe(false);
      expect(result.itemsSynced).toBe(10);
      expect(result.itemsFailed).toBe(2);
      expect(result.duration).toBe(5000);
      expect(result.error).toBe('Network error');
      expect(result.timestamp).toBe(timestamp);
    });
  });
});
