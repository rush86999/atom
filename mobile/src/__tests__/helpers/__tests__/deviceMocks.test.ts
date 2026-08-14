/**
 * Device Mock Factories Tests
 *
 * Validate that all factory functions create correct mock structures
 * with proper defaults and option overrides.
 */

import {
  createMockCameraRef,
  createMockBarcodeResult,
  createMockPhoto,
  createMockDocumentCorners,
  createMockLocation,
  createMockGeofence,
  createMockGeofenceNotification,
  createMockLocationHistoryEntry,
  createMockLocationHistory,
  createMockGeocodeResult,
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
    beforeEach(() => {
      // The unique-identifier test awaits a real setImmediate
      jest.useRealTimers();
    });

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
      const listenerInvoked = jest.fn();
      const NetInfo = {
        addEventListener: jest.fn().mockImplementation((callback) => {
          capturedCallback = callback;
          return jest.fn();
        }),
      };

      // Register a listener the way a service (e.g. offlineSyncService) does,
      // then let the helper drive it
      NetInfo.addEventListener((state: any) => listenerInvoked(state));

      simulateNetworkSwitch(NetInfo, true);

      expect(capturedCallback).not.toBeNull();
      expect(listenerInvoked).toHaveBeenCalledWith(
        expect.objectContaining({ isConnected: true })
      );
    });

    it('should trigger NetInfo callback with disconnected state', () => {
      let capturedCallback: ((state: any) => void) | null = null;
      const listenerInvoked = jest.fn();
      const NetInfo = {
        addEventListener: jest.fn().mockImplementation((callback) => {
          capturedCallback = callback;
          return jest.fn();
        }),
      };

      NetInfo.addEventListener((state: any) => listenerInvoked(state));

      simulateNetworkSwitch(NetInfo, false);

      expect(capturedCallback).not.toBeNull();
      expect(listenerInvoked).toHaveBeenCalledWith(
        expect.objectContaining({ isConnected: false })
      );
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
  beforeEach(() => {
    // waitForSyncComplete/waitForSyncProgress poll with setImmediate and
    // Date.now() — fake timers would never let them resolve or time out.
    jest.useRealTimers();
  });

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

  // ========================================================================
  // Wave 118 additions: barcode / photo / corners / geofence / history
  // ========================================================================

  describe('createMockBarcodeResult', () => {
    it('should create a QR barcode with corner points by default', () => {
      const result = createMockBarcodeResult();
      expect(result.barcodes).toHaveLength(1);
      expect(result.barcodes[0].type).toBe('qr');
      expect(result.barcodes[0].rawValue).toBe('https://example.com');
      expect(result.barcodes[0].cornerPoints).toHaveLength(4);
    });

    it('should honor custom type/data and drop corner points when requested', () => {
      const result = createMockBarcodeResult({
        type: 'ean13',
        data: '5901234123457',
        withCorners: false,
      });
      expect(result.barcodes[0].type).toBe('ean13');
      expect(result.barcodes[0].rawValue).toBe('5901234123457');
      expect(result.barcodes[0].cornerPoints).toHaveLength(2);
    });
  });

  describe('createMockPhoto', () => {
    it('should create a photo with default dimensions', () => {
      const photo = createMockPhoto();
      expect(photo.type).toBe('photo');
      expect(photo.width).toBe(1920);
      expect(photo.height).toBe(1080);
      expect(photo.size).toBe(1024000);
      expect(photo.uri).toMatch(/^file:\/\/\/mock\/photo-/);
    });

    it('should honor custom options including exif', () => {
      const exif = { Make: 'Apple' };
      const photo = createMockPhoto({
        uri: 'file:///custom.jpg',
        width: 3840,
        height: 2160,
        size: 5000,
        exif,
      });
      expect(photo.uri).toBe('file:///custom.jpg');
      expect(photo.width).toBe(3840);
      expect(photo.height).toBe(2160);
      expect(photo.size).toBe(5000);
      expect(photo.exif).toBe(exif);
    });
  });

  describe('createMockDocumentCorners', () => {
    it('should create four corner points', () => {
      const corners = createMockDocumentCorners();
      expect(corners.topLeft).toEqual({ x: 10, y: 10 });
      expect(corners.topRight).toEqual({ x: 90, y: 10 });
      expect(corners.bottomRight).toEqual({ x: 90, y: 90 });
      expect(corners.bottomLeft).toEqual({ x: 10, y: 90 });
    });
  });

  describe('createMockGeofenceNotification', () => {
    it('should use defaults when no args given', () => {
      const notification = createMockGeofenceNotification();
      expect(notification.event).toBe('enter');
      expect(notification.region.id).toBeTruthy();
      expect(notification.location.coords.latitude).toBe(37.7749);
      expect(typeof notification.timestamp).toBe('number');
    });

    it('should honor custom region, event, and location', () => {
      const region = { id: 'home', radius: 50 };
      const location = { latitude: 1, longitude: 2 };
      const notification = createMockGeofenceNotification(region, 'exit', location);
      expect(notification.event).toBe('exit');
      expect(notification.region).toBe(region);
      expect(notification.location).toBe(location);
    });
  });

  describe('createMockLocationHistoryEntry', () => {
    it('should create an entry with defaults', () => {
      const entry = createMockLocationHistoryEntry();
      expect(entry.latitude).toBe(37.7749);
      expect(entry.longitude).toBe(-122.4194);
      expect(entry.accuracy).toBe(10);
      expect(typeof entry.timestamp).toBe('number');
    });

    it('should honor overrides', () => {
      const entry = createMockLocationHistoryEntry({ latitude: 1, longitude: 2, accuracy: 5, timestamp: 123 });
      expect(entry).toEqual({ latitude: 1, longitude: 2, accuracy: 5, timestamp: 123 });
    });
  });

  describe('createMockLocationHistory', () => {
    it('should generate the requested count with default spacing', () => {
      const history = createMockLocationHistory(5);
      expect(history).toHaveLength(5);
      expect(history[0].latitude).toBe(37.7749);
      expect(history[4].latitude).toBeCloseTo(37.7753, 4);
      expect(history[1].timestamp - history[0].timestamp).toBe(1000);
    });

    it('should use the default count and custom options', () => {
      const history = createMockLocationHistory(undefined as any, { latitude: 10, accuracy: 3 });
      expect(history).toHaveLength(10);
      expect(history[0].latitude).toBe(10);
      expect(history[0].accuracy).toBe(3);
    });
  });

  describe('createMockGeocodeResult', () => {
    it('should return a single default geocode result', () => {
      const [result] = createMockGeocodeResult();
      expect(result.street).toBe('123 Main St');
      expect(result.city).toBe('San Francisco');
      expect(result.region).toBe('CA');
      expect(result.postalCode).toBe('94102');
      expect(result.country).toBe('USA');
    });

    it('should honor overrides', () => {
      const [result] = createMockGeocodeResult({
        street: '1 Apple Way',
        city: 'Cupertino',
        region: 'CA',
        postalCode: '95014',
        country: 'US',
      });
      expect(result.street).toBe('1 Apple Way');
      expect(result.city).toBe('Cupertino');
      expect(result.country).toBe('US');
    });
  });
});
