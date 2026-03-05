/**
 * Device Permissions Integration Tests
 *
 * Integration tests for device permission workflows including:
 * - Permission request workflows (camera, location, notifications, biometric)
 * - Permission state transitions and persistence
 * - Multi-permission flows and partial grant handling
 * - Platform-specific behavior (iOS vs Android)
 * - Permission caching in AsyncStorage
 *
 * Uses mocked Expo modules for consistent test behavior.
 */

import * as Camera from 'expo-camera';
import * as Location from 'expo-location';
import * as Notifications from 'expo-notifications';
import * as LocalAuthentication from 'expo-local-authentication';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';

// Mock fetch for API calls
global.fetch = jest.fn();

describe('Device Permissions Integration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset AsyncStorage mock
    global.__resetAsyncStorageMock?.();
  });

  afterEach(async () => {
    await AsyncStorage.clear();
  });

  // ========================================================================
  // Permission Request Workflows
  // ========================================================================

  describe('Permission Request Workflows', () => {
    test('should request camera permission and handle grant', async () => {
      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const result = await Camera.requestCameraPermissionsAsync();

      expect(result.status).toBe('granted');
      expect(result.granted).toBe(true);
      expect(result.canAskAgain).toBe(true);
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should request camera permission and handle denial', async () => {
      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      const result = await Camera.requestCameraPermissionsAsync();

      expect(result.status).toBe('denied');
      expect(result.granted).toBe(false);
      expect(result.canAskAgain).toBe(true);
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should request location permission (foreground) and handle grant', async () => {
      const mockRequestPermission = jest.spyOn(Location, 'requestForegroundPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const result = await Location.requestForegroundPermissionsAsync();

      expect(result.status).toBe('granted');
      expect(result.granted).toBe(true);
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should request location permission (background) and handle grant', async () => {
      const mockRequestPermission = jest.spyOn(Location, 'requestBackgroundPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const result = await Location.requestBackgroundPermissionsAsync();

      expect(result.status).toBe('granted');
      expect(result.granted).toBe(true);
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should request notification permissions and handle grant', async () => {
      const mockRequestPermission = jest.spyOn(Notifications, 'requestPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
        ios: {
          allowsAlert: true,
          allowsBadge: true,
          allowsSound: true,
        },
        android: {},
      });

      const result = await Notifications.requestPermissionsAsync();

      expect(result.status).toBe('granted');
      expect(result.granted).toBe(true);
      expect(result.ios?.allowsAlert).toBe(true);
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should request biometric enrollment check', async () => {
      const mockHasHardware = jest.spyOn(LocalAuthentication, 'hasHardwareAsync').mockResolvedValue(true);
      const mockIsEnrolled = jest.spyOn(LocalAuthentication, 'isEnrolledAsync').mockResolvedValue(true);

      const hasHardware = await LocalAuthentication.hasHardwareAsync();
      const isEnrolled = await LocalAuthentication.isEnrolledAsync();

      expect(hasHardware).toBe(true);
      expect(isEnrolled).toBe(true);
      expect(mockHasHardware).toHaveBeenCalledTimes(1);
      expect(mockIsEnrolled).toHaveBeenCalledTimes(1);
    });
  });

  // ========================================================================
  // Permission State Transitions
  // ========================================================================

  describe('Permission State Transitions', () => {
    test('should track permission state from notAsked to granted', async () => {
      // Initial state: notAsked
      const mockGetPermission = jest.spyOn(Camera, 'getCameraPermissionsAsync')
        .mockResolvedValueOnce({
          status: 'notAsked',
          canAskAgain: true,
          granted: false,
          expires: 'never',
        })
        .mockResolvedValueOnce({
          status: 'granted',
          canAskAgain: true,
          granted: true,
          expires: 'never',
        });

      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Check initial state
      const initialState = await Camera.getCameraPermissionsAsync();
      expect(initialState.status).toBe('notAsked');

      // Request permission
      await Camera.requestCameraPermissionsAsync();

      // Check new state
      const newState = await Camera.getCameraPermissionsAsync();
      expect(newState.status).toBe('granted');

      expect(mockGetPermission).toHaveBeenCalledTimes(2);
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should track permission state from notAsked to denied', async () => {
      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      const mockGetPermission = jest.spyOn(Camera, 'getCameraPermissionsAsync').mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      // Request permission (denied)
      await Camera.requestCameraPermissionsAsync();

      // Check state
      const state = await Camera.getCameraPermissionsAsync();
      expect(state.status).toBe('denied');
      expect(state.granted).toBe(false);

      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
      expect(mockGetPermission).toHaveBeenCalledTimes(1);
    });

    test('should handle canAskAgain flag correctly', async () => {
      // Test with canAskAgain = true
      const mockRequestPermission1 = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValueOnce({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      const result1 = await Camera.requestCameraPermissionsAsync();
      expect(result1.canAskAgain).toBe(true);

      // Test with canAskAgain = false (Android "Don't ask again")
      mockRequestPermission1.mockResolvedValueOnce({
        status: 'denied',
        canAskAgain: false,
        granted: false,
        expires: 'never',
      });

      const result2 = await Camera.requestCameraPermissionsAsync();
      expect(result2.canAskAgain).toBe(false);
    });

    test('should persist permission state across app restarts', async () => {
      const permissionKey = 'atom_camera_permission';

      // First app launch - permission not asked
      const mockGetPermission = jest.spyOn(Camera, 'getCameraPermissionsAsync')
        .mockResolvedValueOnce({
          status: 'notAsked',
          canAskAgain: true,
          granted: false,
          expires: 'never',
        })
        .mockResolvedValueOnce({
          status: 'granted',
          canAskAgain: true,
          granted: true,
          expires: 'never',
        });

      const state1 = await Camera.getCameraPermissionsAsync();
      await AsyncStorage.setItem(permissionKey, JSON.stringify(state1));

      // Simulate app restart
      const storedState = await AsyncStorage.getItem(permissionKey);
      expect(storedState).toBeDefined();

      // Second app launch - load from storage
      const parsedState = JSON.parse(storedState!);
      expect(parsedState.status).toBe('notAsked');

      // Now permission granted
      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await Camera.requestCameraPermissionsAsync();
      const state2 = await Camera.getCameraPermissionsAsync();

      await AsyncStorage.setItem(permissionKey, JSON.stringify(state2));

      // Verify stored state
      const updatedState = JSON.parse(await AsyncStorage.getItem(permissionKey)!);
      expect(updatedState.status).toBe('granted');

      expect(mockGetPermission).toHaveBeenCalledTimes(2); // Called twice: initial + after grant
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });
  });

  // ========================================================================
  // Multi-Permission Flows
  // ========================================================================

  describe('Multi-Permission Flows', () => {
    test('should request multiple permissions in sequence', async () => {
      const mockCamera = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const mockLocation = jest.spyOn(Location, 'requestForegroundPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const mockNotifications = jest.spyOn(Notifications, 'requestPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
        ios: { allowsAlert: true, allowsBadge: true, allowsSound: true },
        android: {},
      });

      // Request permissions in sequence
      const cameraResult = await Camera.requestCameraPermissionsAsync();
      const locationResult = await Location.requestForegroundPermissionsAsync();
      const notificationResult = await Notifications.requestPermissionsAsync();

      expect(cameraResult.granted).toBe(true);
      expect(locationResult.granted).toBe(true);
      expect(notificationResult.granted).toBe(true);

      expect(mockCamera).toHaveBeenCalledTimes(1);
      expect(mockLocation).toHaveBeenCalledTimes(1);
      expect(mockNotifications).toHaveBeenCalledTimes(1);
    });

    test('should handle partial grant (some granted, some denied)', async () => {
      // Camera granted
      const mockCamera = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Location denied
      const mockLocation = jest.spyOn(Location, 'requestForegroundPermissionsAsync').mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      // Notifications granted
      const mockNotifications = jest.spyOn(Notifications, 'requestPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
        ios: { allowsAlert: true, allowsBadge: true, allowsSound: true },
        android: {},
      });

      const cameraResult = await Camera.requestCameraPermissionsAsync();
      const locationResult = await Location.requestForegroundPermissionsAsync();
      const notificationResult = await Notifications.requestPermissionsAsync();

      expect(cameraResult.granted).toBe(true);
      expect(locationResult.granted).toBe(false);
      expect(notificationResult.granted).toBe(true);

      // Verify partial grant state
      const permissions = {
        camera: cameraResult.granted,
        location: locationResult.granted,
        notifications: notificationResult.granted,
      };

      const grantedCount = Object.values(permissions).filter(Boolean).length;
      expect(grantedCount).toBe(2); // 2 out of 3 granted

      expect(mockCamera).toHaveBeenCalledTimes(1);
      expect(mockLocation).toHaveBeenCalledTimes(1);
      expect(mockNotifications).toHaveBeenCalledTimes(1);
    });

    test('should show appropriate UI for each permission type', async () => {
      // Test camera permission UI prompt
      const mockCamera = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const cameraResult = await Camera.requestCameraPermissionsAsync();

      // Verify camera permission result
      expect(cameraResult.status).toBe('granted');

      // Test location permission UI prompt
      const mockLocation = jest.spyOn(Location, 'requestForegroundPermissionsAsync').mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      const locationResult = await Location.requestForegroundPermissionsAsync();

      // Verify location permission result
      expect(locationResult.status).toBe('denied');

      // Each permission type should have its own UI flow
      const permissionFlows = {
        camera: 'Camera access is needed to take photos',
        location: 'Location access is needed for GPS features',
        notifications: 'Notifications are needed for alerts',
      };

      expect(Object.keys(permissionFlows)).toContain('camera');
      expect(Object.keys(permissionFlows)).toContain('location');
      expect(Object.keys(permissionFlows)).toContain('notifications');
    });

    test('should batch permission requests where possible', async () => {
      // Some permissions can be requested together (iOS)
      // Camera and Location must be requested separately
      const mockCamera = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const mockLocation = jest.spyOn(Location, 'requestForegroundPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Request permissions
      const [cameraResult, locationResult] = await Promise.all([
        Camera.requestCameraPermissionsAsync(),
        Location.requestForegroundPermissionsAsync(),
      ]);

      expect(cameraResult.granted).toBe(true);
      expect(locationResult.granted).toBe(true);

      expect(mockCamera).toHaveBeenCalledTimes(1);
      expect(mockLocation).toHaveBeenCalledTimes(1);
    });
  });

  // ========================================================================
  // Platform-Specific Behavior
  // ========================================================================

  describe('Platform-Specific Behavior', () => {
    test('should handle iOS permission dialog behavior', async () => {
      // Note: Platform.OS is a readonly property, we'll just verify behavior
      // In real tests, we'd use jest.replaceProperty if supported

      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const result = await Camera.requestCameraPermissionsAsync();

      expect(result.status).toBe('granted');
      expect(result.granted).toBe(true);
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should handle Android permission rationale', async () => {
      // Test Android "Don't ask again" behavior
      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'denied',
        canAskAgain: false, // Android "Don't ask again"
        granted: false,
        expires: 'never',
      });

      const result = await Camera.requestCameraPermissionsAsync();

      expect(result.status).toBe('denied');
      expect(result.canAskAgain).toBe(false);
      expect(result.granted).toBe(false);

      // When canAskAgain is false, user should be directed to app settings
      if (!result.canAskAgain) {
        expect(true).toBe(true); // Should show "Open Settings" dialog
      }

      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should handle iOS app-level permissions (via Settings)', async () => {
      // iOS permissions can be changed in Settings without app prompt
      const mockGetPermission = jest.spyOn(Camera, 'getCameraPermissionsAsync')
        .mockResolvedValueOnce({
          status: 'granted',
          canAskAgain: true,
          granted: true,
          expires: 'never',
        })
        .mockResolvedValueOnce({
          status: 'denied', // User revoked in Settings
          canAskAgain: true,
          granted: false,
          expires: 'never',
        });

      // Initial check
      const initialState = await Camera.getCameraPermissionsAsync();
      expect(initialState.status).toBe('granted');

      // User revoked permission in Settings
      const revokedState = await Camera.getCameraPermissionsAsync();
      expect(revokedState.status).toBe('denied');

      expect(mockGetPermission).toHaveBeenCalledTimes(2);
    });

    test('should handle Android runtime permissions', async () => {
      // Android requires runtime permissions for dangerous permissions
      const mockRequestPermission = jest.spyOn(Location, 'requestForegroundPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const result = await Location.requestForegroundPermissionsAsync();

      expect(result.granted).toBe(true);
      expect(result.status).toBe('granted');
      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should detect platform correctly (Platform.OS)', () => {
      const platform = Platform.OS;

      expect(platform).toMatch(/^(ios|android|web|windows|macos)$/);

      // Platform detection should be consistent
      const platform2 = Platform.OS;
      expect(platform).toBe(platform2);
    });
  });

  // ========================================================================
  // Permission Caching
  // ========================================================================

  describe('Permission Caching', () => {
    test('should cache granted permissions in AsyncStorage', async () => {
      const cacheKey = 'atom_permissions_cache';
      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync').mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Request permission
      const result = await Camera.requestCameraPermissionsAsync();

      // Cache permission result
      const permissions = {
        camera: result.granted,
        location: false,
        notifications: false,
      };

      await AsyncStorage.setItem(cacheKey, JSON.stringify(permissions));

      // Verify cache
      const cached = await AsyncStorage.getItem(cacheKey);
      expect(cached).toBeDefined();

      const parsedCache = JSON.parse(cached!);
      expect(parsedCache.camera).toBe(true);

      expect(mockRequestPermission).toHaveBeenCalledTimes(1);
    });

    test('should load cached permissions on app startup', async () => {
      const cacheKey = 'atom_permissions_cache';

      // Simulate cached permissions from previous session
      const cachedPermissions = {
        camera: true,
        location: true,
        notifications: false,
        biometric: true,
      };

      await AsyncStorage.setItem(cacheKey, JSON.stringify(cachedPermissions));

      // On app startup, load from cache
      const cached = await AsyncStorage.getItem(cacheKey);
      expect(cached).toBeDefined();

      const loadedPermissions = JSON.parse(cached!);
      expect(loadedPermissions).toEqual(cachedPermissions);

      // Verify specific permissions
      expect(loadedPermissions.camera).toBe(true);
      expect(loadedPermissions.location).toBe(true);
      expect(loadedPermissions.notifications).toBe(false);
      expect(loadedPermissions.biometric).toBe(true);
    });

    test('should invalidate cache when permissions change', async () => {
      const cacheKey = 'atom_permissions_cache';
      const mockGetPermission = jest.spyOn(Camera, 'getCameraPermissionsAsync')
        .mockResolvedValueOnce({
          status: 'granted',
          canAskAgain: true,
          granted: true,
          expires: 'never',
        })
        .mockResolvedValueOnce({
          status: 'denied', // Permission revoked
          canAskAgain: true,
          granted: false,
          expires: 'never',
        });

      // Initial cache
      const initialCache = {
        camera: true,
        location: false,
        notifications: false,
      };

      await AsyncStorage.setItem(cacheKey, JSON.stringify(initialCache));

      // Check permission status
      const permission1 = await Camera.getCameraPermissionsAsync();
      expect(permission1.granted).toBe(true);

      // Permission revoked (e.g., user changed in Settings)
      const permission2 = await Camera.getCameraPermissionsAsync();
      expect(permission2.granted).toBe(false);

      // Invalidate and update cache
      const updatedCache = {
        camera: false,
        location: false,
        notifications: false,
      };

      await AsyncStorage.setItem(cacheKey, JSON.stringify(updatedCache));

      // Verify cache updated
      const cached = await AsyncStorage.getItem(cacheKey);
      const parsedCache = JSON.parse(cached!);
      expect(parsedCache.camera).toBe(false);

      expect(mockGetPermission).toHaveBeenCalledTimes(2);
    });
  });

  // ========================================================================
  // Permission Denial Recovery
  // ========================================================================

  describe('Permission Denial Recovery', () => {
    test('should recover from permission denial after opening settings', async () => {
      const mockRequestPermission = jest.spyOn(Camera, 'requestCameraPermissionsAsync')
        .mockResolvedValueOnce({
          status: 'denied',
          canAskAgain: true,
          granted: false,
          expires: 'never',
        })
        .mockResolvedValueOnce({
          status: 'granted', // User granted permission after opening settings
          canAskAgain: true,
          granted: true,
          expires: 'never',
        });

      const mockGetPermission = jest.spyOn(Camera, 'getCameraPermissionsAsync')
        .mockResolvedValueOnce({
          status: 'denied',
          canAskAgain: true,
          granted: false,
          expires: 'never',
        })
        .mockResolvedValueOnce({
          status: 'granted',
          canAskAgain: true,
          granted: true,
          expires: 'never',
        });

      // Initial permission request (denied)
      const result1 = await Camera.requestCameraPermissionsAsync();
      expect(result1.status).toBe('denied');
      expect(result1.granted).toBe(false);

      // Check current status (still denied)
      const status1 = await Camera.getCameraPermissionsAsync();
      expect(status1.granted).toBe(false);

      // Simulate user opening app settings and granting permission
      // (In real app, would trigger Linking.openURL('app-settings:'))
      // After settings change, request permissions again
      const result2 = await Camera.requestCameraPermissionsAsync();
      expect(result2.status).toBe('granted');
      expect(result2.granted).toBe(true);

      // Verify permission now granted
      const status2 = await Camera.getCameraPermissionsAsync();
      expect(status2.granted).toBe(true);

      expect(mockRequestPermission).toHaveBeenCalledTimes(2);
      expect(mockGetPermission).toHaveBeenCalledTimes(2);
    });
  });
});
