/**
 * Device Mock Factories
 *
 * Helper functions for creating realistic mock objects for device features.
 * Reduces boilerplate in service tests and ensures consistent mock data.
 *
 * @module deviceMocks
 *
 * @example
 * import { createMockCameraRef, createMockLocation } from './deviceMocks';
 *
 * const cameraRef = createMockCameraRef({ shouldSucceed: true });
 * const location = createMockLocation({ latitude: 37.7749, longitude: -122.4194 });
 */

// ============================================================================
// TypeScript Interfaces for Mock Options
// ============================================================================

/**
 * Options for creating mock camera ref
 */
export interface MockCameraRefOptions {
  /** Whether takePictureAsync should succeed (default: true) */
  shouldSucceed?: boolean;
  /** Mock photo URI (default: 'file:///mock/photo.jpg') */
  mockUri?: string;
  /** Mock photo width (default: 1920) */
  mockWidth?: number;
  /** Mock photo height (default: 1080) */
  mockHeight?: number;
}

/**
 * Options for creating mock location
 */
export interface MockLocationOptions {
  /** Latitude coordinate (required) */
  latitude?: number;
  /** Longitude coordinate (required) */
  longitude?: number;
  /** Altitude in meters (default: 100) */
  altitude?: number;
  /** Accuracy in meters (default: 10) */
  accuracy?: number;
  /** Heading in degrees (default: 0) */
  heading?: number;
  /** Speed in meters/second (default: 0) */
  speed?: number;
  /** Timestamp (default: Date.now()) */
  timestamp?: number;
}

/**
 * Options for creating mock geofence
 */
export interface MockGeofenceOptions {
  /** Unique geofence identifier (auto-generated if not provided) */
  id?: string;
  /** Human-readable identifier */
  identifier?: string;
  /** Latitude coordinate */
  latitude?: number;
  /** Longitude coordinate */
  longitude?: number;
  /** Radius in meters (default: 100) */
  radius?: number;
  /** Notify on entry (default: true) */
  notifyOnEntry?: boolean;
  /** Notify on exit (default: false) */
  notifyOnExit?: boolean;
}

/**
 * Options for creating mock notification
 */
export interface MockNotificationOptions {
  /** Notification title */
  title?: string;
  /** Notification body text */
  body?: string;
  /** Custom data payload */
  data?: Record<string, unknown>;
  /** Play sound (default: true) */
  sound?: boolean | string;
  /** Badge count */
  badge?: number;
  /** Notification priority */
  priority?: number;
}

/**
 * Options for creating mock push token
 */
export interface MockPushTokenOptions {
  /** Push token string (default: 'ExponentPushToken[xxx]') */
  token?: string;
  /** Platform type (default: 'ios') */
  platform?: 'ios' | 'android';
  /** User ID */
  userId?: string;
  /** Device ID */
  deviceId?: string;
  /** Registration timestamp (default: new Date()) */
  registeredAt?: Date;
}

/**
 * Options for creating mock sync result
 */
export interface MockSyncResultOptions {
  /** Whether sync succeeded */
  success?: boolean;
  /** Number of items synced */
  itemsSynced?: number;
  /** Number of items failed */
  itemsFailed?: number;
  /** Sync duration in milliseconds */
  duration?: number;
  /** Error message if failed */
  error?: string;
  /** Sync timestamp */
  timestamp?: Date;
}

// ============================================================================
// Camera Mock Factories
// ============================================================================

/**
 * Create mock CameraView ref for testing camera operations
 *
 * @param options - Configuration options for the mock
 * @returns Mock ref object with current property
 *
 * @example
 * const cameraRef = createMockCameraRef({ shouldSucceed: true });
 * await cameraRef.current.takePictureAsync();
 * expect(cameraRef.current.takePictureAsync).toHaveBeenCalled();
 */
export const createMockCameraRef = (options: MockCameraRefOptions = {}) => {
  const {
    shouldSucceed = true,
    mockUri = 'file:///mock/photo.jpg',
    mockWidth = 1920,
    mockHeight = 1080,
  } = options;

  return {
    current: {
      takePictureAsync: jest.fn().mockResolvedValue(
        shouldSucceed
          ? { uri: mockUri, width: mockWidth, height: mockHeight }
          : null
      ),
      recordAsync: jest.fn().mockResolvedValue({
        uri: 'file:///mock/video.mp4',
      }),
      stopRecording: jest.fn().mockResolvedValue(undefined),
    },
  };
};

// ============================================================================
// Location Mock Factories
// ============================================================================

/**
 * Create mock GPS coordinates for location testing
 *
 * @param options - Location configuration options
 * @returns LocationInfo object with coordinate properties
 *
 * @example
 * const location = createMockLocation({
 *   latitude: 37.7749,
 *   longitude: -122.4194,
 *   accuracy: 5
 * });
 * expect(location.coords.latitude).toBe(37.7749);
 */
export const createMockLocation = (options: MockLocationOptions = {}) => {
  const {
    latitude = 37.7749,
    longitude = -122.4194,
    altitude = 100,
    accuracy = 10,
    heading = 0,
    speed = 0,
    timestamp = Date.now(),
  } = options;

  return {
    coords: {
      latitude,
      longitude,
      altitude,
      accuracy,
      heading,
      speed,
    },
    timestamp,
  };
};

/**
 * Create mock geofence region for testing location-based triggers
 *
 * @param options - Geofence configuration options
 * @returns GeofenceRegion object with all properties
 *
 * @example
 * const geofence = createMockGeofence({
 *   identifier: 'office',
 *   latitude: 37.7749,
 *   longitude: -122.4194,
 *   radius: 200
 * });
 * expect(geofence.identifier).toBe('office');
 */
export const createMockGeofence = (options: MockGeofenceOptions = {}) => {
  const {
    id = `geofence-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    identifier = 'test-geofence',
    latitude = 37.7749,
    longitude = -122.4194,
    radius = 100,
    notifyOnEntry = true,
    notifyOnExit = false,
  } = options;

  return {
    id,
    identifier,
    latitude,
    longitude,
    radius,
    notifyOnEntry,
    notifyOnExit,
  };
};

// ============================================================================
// Notification Mock Factories
// ============================================================================

/**
 * Create mock notification payload for testing notification display
 *
 * @param options - Notification configuration options
 * @returns LocalNotification object
 *
 * @example
 * const notification = createMockNotification({
 *   title: 'Test Notification',
 *   body: 'Test body',
 *   data: { userId: '123' }
 * });
 * expect(notification.title).toBe('Test Notification');
 */
export const createMockNotification = (options: MockNotificationOptions = {}) => {
  const {
    title = 'Test Notification',
    body = 'Test notification body',
    data = {},
    sound = true,
    badge = 1,
    priority = 5,
  } = options;

  return {
    title,
    body,
    data,
    sound,
    badge,
    priority,
    identifier: `notification-${Date.now()}`,
    timestamp: Date.now(),
  };
};

/**
 * Create mock Expo push token for testing push notification registration
 *
 * @param options - Push token configuration options
 * @returns PushToken object
 *
 * @example
 * const pushToken = createMockPushToken({
 *   token: 'ExponentPushToken[abc123]',
 *   platform: 'ios',
 *   userId: 'user-123'
 * });
 * expect(pushToken.type).toBe('ios');
 */
export const createMockPushToken = (options: MockPushTokenOptions = {}) => {
  const {
    token = 'ExponentPushToken[xxx]',
    platform = 'ios',
    userId = 'test-user',
    deviceId = 'test-device',
    registeredAt = new Date(),
  } = options;

  return {
    type: platform,
    data: token,
    userId,
    deviceId,
    registeredAt,
  };
};

// ============================================================================
// Network Mock Factories
// ============================================================================

/**
 * Simulate network state change for offline sync testing
 *
 * Triggers NetInfo.addEventListener callback with new network state
 *
 * @param NetInfo - NetInfo mock module
 * @param isConnected - Whether device is connected (default: true)
 *
 * @example
 * const NetInfo = require('@react-native-community/netinfo');
 * simulateNetworkSwitch(NetInfo, true);
 * // NetInfo change handlers will be triggered
 */
export const simulateNetworkSwitch = (NetInfo: any, isConnected: boolean) => {
  const addEventListenerMock = NetInfo.addEventListener;
  const callback = addEventListenerMock.mock.calls[0]?.[0];

  if (callback) {
    callback({
      isConnected,
      isInternetReachable: isConnected,
      type: isConnected ? 'wifi' : 'none',
      details: isConnected
        ? { isConnectionExpensive: false, connectionType: 'wifi' }
        : undefined,
    });
  }
};

// ============================================================================
// Timer Helper Utilities
// ============================================================================

/**
 * Wrapper for advanceTimersByTime with human-readable seconds
 * More readable than advanceTimersByTime(300000) for 5 minutes
 *
 * @param seconds - Seconds to advance timers
 *
 * @example
 * jest.useFakeTimers();
 * advanceTimeBySeconds(30); // Advance 30 seconds
 * jest.runAllTimers();
 */
export const advanceTimeBySeconds = (seconds: number): void => {
  jest.advanceTimersByTime(seconds * 1000);
};

// ============================================================================
// Sync Helper Utilities
// ============================================================================

/**
 * Wait for offline sync to complete
 * Polls syncState.syncInProgress until false or timeout
 *
 * @param service - Offline sync service instance
 * @param timeout - Timeout in milliseconds (default: 10000)
 * @returns Promise that resolves when sync completes
 * @throws Error if timeout exceeded
 *
 * @example
 * await waitForSyncComplete(offlineSyncService, 5000);
 * expect(service.getSyncState().syncInProgress).toBe(false);
 */
export const waitForSyncComplete = async (
  service: any,
  timeout = 10000
): Promise<void> => {
  const startTime = Date.now();

  while (true) {
    const state = await service.getSyncState();
    if (!state.syncInProgress) {
      break;
    }

    if (Date.now() - startTime > timeout) {
      throw new Error(`Sync did not complete within ${timeout}ms`);
    }

    // Wait a bit before polling again
    await new Promise(resolve => setImmediate(resolve));
  }
};

// ============================================================================
// Additional Sync Utilities (extending testUtils.ts)
// ============================================================================

/**
 * Wait for specific sync progress milestone
 *
 * @param progress - Current progress value (0-100)
 * @param targetProgress - Target progress to wait for
 * @param timeout - Timeout in milliseconds (default: 5000)
 * @returns Promise that resolves when target progress reached
 *
 * @example
 * await waitForSyncProgress(0, 50); // Wait for 50% progress
 */
export const waitForSyncProgress = async (
  progress: number,
  targetProgress: number,
  timeout = 5000
): Promise<void> => {
  const startTime = Date.now();

  while (progress < targetProgress) {
    if (Date.now() - startTime > timeout) {
      throw new Error(
        `Sync progress did not reach ${targetProgress}% within ${timeout}ms`
      );
    }
    await new Promise(resolve => setImmediate(resolve));
  }
};

/**
 * Create mock SyncResult object for testing sync operations
 *
 * @param options - Sync result configuration options
 * @returns SyncResult object
 *
 * @example
 * const syncResult = createMockSyncResult({
 *   success: true,
 *   itemsSynced: 10,
 *   itemsFailed: 0
 * });
 */
export const createMockSyncResult = (options: MockSyncResultOptions = {}) => {
  const {
    success = true,
    itemsSynced = 0,
    itemsFailed = 0,
    duration = 0,
    error = '',
    timestamp = new Date(),
  } = options;

  return {
    success,
    itemsSynced,
    itemsFailed,
    duration,
    error,
    timestamp,
  };
};

// ============================================================================
// Export All
// ============================================================================

export default {
  // Camera mocks
  createMockCameraRef,

  // Location mocks
  createMockLocation,
  createMockGeofence,

  // Notification mocks
  createMockNotification,
  createMockPushToken,

  // Network mocks
  simulateNetworkSwitch,

  // Timer utilities
  advanceTimeBySeconds,

  // Sync utilities
  waitForSyncComplete,
  waitForSyncProgress,
  createMockSyncResult,
};
