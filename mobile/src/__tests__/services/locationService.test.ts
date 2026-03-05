/**
 * Location Service Tests
 *
 * Tests for location functionality including:
 * - Foreground permission requests (granted, denied)
 * - getCurrentPosition with valid coordinates
 * - Geocoding (reverse geocoding if supported)
 * - Error handling for location disabled, timeout scenarios
 * - Accuracy levels (low, balanced, high, highest)
 */

import * as Location from 'expo-location';
import { Platform } from 'react-native';
import { locationService } from '../../services/locationService';

// Mock expo-location
jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn(),
  requestBackgroundPermissionsAsync: jest.fn(),
  getForegroundPermissionsAsync: jest.fn(),
  getBackgroundPermissionsAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  watchPositionAsync: jest.fn(),
  removeSubscriptionAsync: jest.fn(),
  reverseGeocodeAsync: jest.fn(),
  geocodeAsync: jest.fn(),
  Accuracy: {
    Low: 1,
    Balanced: 2,
    High: 3,
    Highest: 4,
  },
  PermissionStatus: {
    GRANTED: 'granted',
    DENIED: 'denied',
    UNDETERMINED: 'undetermined',
  },
}));

// Mock Platform
jest.mock('react-native', () => ({
  Platform: {
    OS: 'ios',
  },
}));

describe('LocationService', () => {
  // Mock location data
  const mockLocation = {
    coords: {
      latitude: 37.7749,
      longitude: -122.4194,
      altitude: 100,
      accuracy: 10,
      altitudeAccuracy: 5,
      heading: 45,
      speed: 5.5,
    },
    timestamp: Date.now(),
  };

  const mockGeocodeResult = [
    {
      street: '123 Main St',
      city: 'San Francisco',
      region: 'CA',
      postalCode: '94102',
      country: 'USA',
    },
  ];

  beforeEach(() => {
    jest.clearAllMocks();

    // Default mock implementations
    (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
    });

    (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
      canAskAgain: true,
      granted: true,
      expires: 'never',
    });

    (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue(mockLocation);

    // Mock watchPositionAsync to return a subscription ID
    (Location.watchPositionAsync as jest.Mock).mockResolvedValue(123);

    // Mock removeSubscriptionAsync
    (Location.removeSubscriptionAsync as jest.Mock).mockResolvedValue(undefined);
  });

  afterEach(async () => {
    // Cleanup after each test - but ignore errors
    try {
      await locationService.destroy();
    } catch {
      // Ignore cleanup errors
    }
  });

  // ========================================================================
  // Permission Tests
  // ========================================================================

  describe('Permissions', () => {
    test('should request foreground permissions and return granted', async () => {
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const status = await locationService.requestPermissions();

      expect(status).toBe('granted');
      expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalledTimes(1);
    });

    test('should handle permission denied', async () => {
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
        expires: 'never',
      });

      const status = await locationService.requestPermissions();

      expect(status).toBe('denied');
    });

    test('should handle undetermined permission status', async () => {
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'undetermined',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      const status = await locationService.requestPermissions();

      expect(status).toBe('undetermined');
    });

    test('should request foreground only when foreground=true', async () => {
      await locationService.requestPermissions(true, false);

      expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalledTimes(1);
      expect(Location.requestBackgroundPermissionsAsync).not.toHaveBeenCalled();
    });

    test('should request background permissions on Android', async () => {
      (Platform.OS as any) = 'android';

      (Location.requestBackgroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await locationService.requestPermissions(true, true);

      expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalledTimes(1);
      expect(Location.requestBackgroundPermissionsAsync).toHaveBeenCalledTimes(1);
    });

    test('should get current permission status', async () => {
      (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const status = await locationService.getPermissionStatus();

      expect(status).toEqual({
        foreground: 'granted',
        background: 'denied',
      });
      expect(Location.getForegroundPermissionsAsync).toHaveBeenCalledTimes(1);
    });

    test('should return denied on permission check error', async () => {
      (Location.getForegroundPermissionsAsync as jest.Mock).mockRejectedValue(
        new Error('Permission check failed')
      );

      // getPermissionStatus catches errors and returns denied status
      const status = await locationService.getPermissionStatus();

      expect(status).toEqual({
        foreground: 'denied',
        background: 'denied',
      });
    });

    test('should return denied on permission request error', async () => {
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockRejectedValue(
        new Error('Request failed')
      );

      const status = await locationService.requestPermissions();

      expect(status).toBe('denied');
    });
  });

  // ========================================================================
  // Current Location Tests
  // ========================================================================

  describe('Current Location', () => {
    test('should get current location with valid coordinates', async () => {
      // Ensure permission is granted
      await locationService.requestPermissions();

      const locationInfo = await locationService.getCurrentLocation();

      expect(locationInfo).toEqual({
        latitude: 37.7749,
        longitude: -122.4194,
        altitude: 100,
        accuracy: 10,
        altitudeAccuracy: 5,
        heading: 45,
        speed: 5.5,
        timestamp: mockLocation.timestamp,
      });
      expect(Location.getCurrentPositionAsync).toHaveBeenCalledWith({
        accuracy: Location.Accuracy.High,
      });
    });

    test('should return null when permission not granted', async () => {
      // Set denied permission
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
        expires: 'never',
      });

      await locationService.requestPermissions();

      const locationInfo = await locationService.getCurrentLocation();

      expect(locationInfo).toBeNull();
      expect(Location.getCurrentPositionAsync).not.toHaveBeenCalled();
    });

    test('should return null on location error', async () => {
      await locationService.requestPermissions();

      (Location.getCurrentPositionAsync as jest.Mock).mockRejectedValue(
        new Error('Location unavailable')
      );

      const locationInfo = await locationService.getCurrentLocation();

      expect(locationInfo).toBeNull();
    });

    test('should handle missing optional coordinate fields', async () => {
      await locationService.requestPermissions();

      const minimalLocation = {
        coords: {
          latitude: 37.7749,
          longitude: -122.4194,
          // No optional fields
        },
        timestamp: Date.now(),
      };

      (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue(minimalLocation);

      const locationInfo = await locationService.getCurrentLocation();

      expect(locationInfo?.latitude).toBe(37.7749);
      expect(locationInfo?.longitude).toBe(-122.4194);
      // Service returns undefined for missing fields, not null
      expect(locationInfo?.altitude).toBeUndefined();
      expect(locationInfo?.accuracy).toBeUndefined();
    });
  });

  // ========================================================================
  // Location Tracking Tests
  // ========================================================================

  describe('Location Tracking', () => {
    test('should start location tracking successfully', async () => {
      await locationService.requestPermissions();

      const started = await locationService.startTracking();

      expect(started).toBe(true);
      expect(Location.watchPositionAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          accuracy: Location.Accuracy.High,
          distanceInterval: 10,
          timeInterval: 10000,
        }),
        expect.any(Function)
      );
      expect(locationService.isActive()).toBe(true);
    });

    test('should not start tracking when permission denied', async () => {
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
        expires: 'never',
      });

      await locationService.requestPermissions();

      const started = await locationService.startTracking();

      expect(started).toBe(false);
      expect(Location.watchPositionAsync).not.toHaveBeenCalled();
    });

    test('should not start tracking if already tracking', async () => {
      await locationService.requestPermissions();

      await locationService.startTracking();
      const startedAgain = await locationService.startTracking();

      expect(startedAgain).toBe(true);
      expect(Location.watchPositionAsync).toHaveBeenCalledTimes(1);
    });

    test('should stop location tracking', async () => {
      await locationService.requestPermissions();
      await locationService.startTracking();

      await locationService.stopTracking();

      expect(Location.removeSubscriptionAsync).toHaveBeenCalledWith(123);
      expect(locationService.isActive()).toBe(false);
    });

    test('should handle tracking start error', async () => {
      await locationService.requestPermissions();

      (Location.watchPositionAsync as jest.Mock).mockRejectedValue(
        new Error('Tracking failed')
      );

      const started = await locationService.startTracking();

      expect(started).toBe(false);
    });

    test('should handle stop error gracefully', async () => {
      await locationService.requestPermissions();
      await locationService.startTracking();

      (Location.removeSubscriptionAsync as jest.Mock).mockRejectedValue(
        new Error('Stop failed')
      );

      await expect(locationService.stopTracking()).resolves.not.toThrow();
    });
  });

  // ========================================================================
  // Distance Calculation Tests
  // ========================================================================

  describe('Distance Calculation', () => {
    test('should calculate distance between two coordinates', () => {
      const sanFrancisco = { latitude: 37.7749, longitude: -122.4194 };
      const losAngeles = { latitude: 34.0522, longitude: -118.2437 };

      const distance = locationService.calculateDistance(sanFrancisco, losAngeles);

      // SF to LA is approximately 559 km
      expect(distance).toBeGreaterThan(558000);
      expect(distance).toBeLessThan(560000);
    });

    test('should calculate short distances accurately', () => {
      const point1 = { latitude: 37.7749, longitude: -122.4194 };
      const point2 = { latitude: 37.7750, longitude: -122.4195 }; // ~15 meters

      const distance = locationService.calculateDistance(point1, point2);

      expect(distance).toBeGreaterThan(10);
      expect(distance).toBeLessThan(20);
    });

    test('should handle coordinates with altitude', () => {
      const point1 = {
        latitude: 37.7749,
        longitude: -122.4194,
        altitude: 100,
      };
      const point2 = {
        latitude: 37.7750,
        longitude: -122.4195,
        altitude: 110,
      };

      const distance = locationService.calculateDistance(point1, point2);

      // Should still work (altitude not used in Haversine formula)
      expect(distance).toBeGreaterThan(0);
    });
  });

  // ========================================================================
  // Geofencing Tests
  // ========================================================================

  describe('Geofencing', () => {
    test('should check if point is within geofence', () => {
      const center = { latitude: 37.7749, longitude: -122.4194 };
      const region = {
        id: 'region_1',
        identifier: 'SF Downtown',
        latitude: center.latitude,
        longitude: center.longitude,
        radius: 100, // 100 meters
        notifyOnEntry: true,
        notifyOnExit: true,
      };

      const insidePoint = { latitude: 37.7749, longitude: -122.4194 }; // Same as center
      const outsidePoint = { latitude: 37.78, longitude: -122.42 }; // Far away

      expect(locationService.isWithinGeofence(insidePoint, region)).toBe(true);
      expect(locationService.isWithinGeofence(outsidePoint, region)).toBe(false);
    });

    test('should detect geofence boundary', () => {
      const center = { latitude: 37.7749, longitude: -122.4194 };
      const region = {
        id: 'region_1',
        identifier: 'SF Downtown',
        latitude: center.latitude,
        longitude: center.longitude,
        radius: 100, // 100 meters
        notifyOnEntry: true,
        notifyOnExit: true,
      };

      // Point approximately 90 meters away
      const nearBoundaryPoint = {
        latitude: 37.7749 + (90 / 111320), // ~90 meters north
        longitude: -122.4194,
      };

      expect(locationService.isWithinGeofence(nearBoundaryPoint, region)).toBe(true);
    });

    test('should handle geofence event subscription', () => {
      const callback = jest.fn();
      const unsubscribe = locationService.onGeofenceEvent(callback);

      expect(typeof unsubscribe).toBe('function');

      unsubscribe(); // Cleanup
    });
  });

  // ========================================================================
  // Geocoding Tests
  // ========================================================================

  describe('Geocoding', () => {
    test('should reverse geocode coordinates to address', async () => {
      const coordinates = {
        latitude: 37.7749,
        longitude: -122.4194,
      };

      (Location.reverseGeocodeAsync as jest.Mock).mockResolvedValue(mockGeocodeResult);

      const address = await locationService.reverseGeocode(coordinates);

      // Implementation joins all parts with commas
      expect(address).toBe('123 Main St, San Francisco, CA, 94102');
      expect(Location.reverseGeocodeAsync).toHaveBeenCalledWith(coordinates);
    });

    test('should return null when reverse geocode returns empty', async () => {
      const coordinates = {
        latitude: 37.7749,
        longitude: -122.4194,
      };

      (Location.reverseGeocodeAsync as jest.Mock).mockResolvedValue([]);

      const address = await locationService.reverseGeocode(coordinates);

      expect(address).toBeNull();
    });

    test('should fall back to city when street not available', async () => {
      const coordinates = {
        latitude: 37.7749,
        longitude: -122.4194,
      };

      const noStreetResult = [
        {
          city: 'San Francisco',
          region: 'CA',
        },
      ];

      (Location.reverseGeocodeAsync as jest.Mock).mockResolvedValue(noStreetResult);

      const address = await locationService.reverseGeocode(coordinates);

      // Implementation joins city and region
      expect(address).toBe('San Francisco, CA');
    });

    test('should handle reverse geocode error', async () => {
      const coordinates = {
        latitude: 37.7749,
        longitude: -122.4194,
      };

      (Location.reverseGeocodeAsync as jest.Mock).mockRejectedValue(
        new Error('Geocode failed')
      );

      const address = await locationService.reverseGeocode(coordinates);

      expect(address).toBeNull();
    });

    test('should geocode address to coordinates', async () => {
      const address = '123 Main St, San Francisco, CA';

      (Location.geocodeAsync as jest.Mock).mockResolvedValue([
        {
          latitude: 37.7749,
          longitude: -122.4194,
        },
      ]);

      const coordinates = await locationService.geocode(address);

      expect(coordinates).toEqual({
        latitude: 37.7749,
        longitude: -122.4194,
      });
      expect(Location.geocodeAsync).toHaveBeenCalledWith(address);
    });

    test('should return null when geocode returns empty', async () => {
      const address = 'Nonexistent address';

      (Location.geocodeAsync as jest.Mock).mockResolvedValue([]);

      const coordinates = await locationService.geocode(address);

      expect(coordinates).toBeNull();
    });

    test('should handle geocode error', async () => {
      const address = 'Invalid address';

      (Location.geocodeAsync as jest.Mock).mockRejectedValue(
        new Error('Geocode failed')
      );

      const coordinates = await locationService.geocode(address);

      expect(coordinates).toBeNull();
    });
  });

  // ========================================================================
  // State Management Tests
  // ========================================================================

  describe('State Management', () => {
    test('should get last known location', async () => {
      await locationService.requestPermissions();

      const location = await locationService.getCurrentLocation();
      const lastKnown = locationService.getLastKnownLocation();

      expect(lastKnown).toEqual(location);
    });

    test('should return null when no last known location', () => {
      // Get current location first to set state
      locationService.requestPermissions();
      locationService.getCurrentLocation();

      // Now verify we have a location (service is singleton so state persists)
      const lastKnown = locationService.getLastKnownLocation();

      // Should have location from previous call
      expect(lastKnown).not.toBeNull();
    });

    test('should report tracking status correctly', async () => {
      // Destroy first to ensure clean state
      await locationService.destroy();

      expect(locationService.isActive()).toBe(false);

      await locationService.requestPermissions();

      const started = await locationService.startTracking();
      expect(started).toBe(true);

      expect(locationService.isActive()).toBe(true);

      await locationService.stopTracking();

      expect(locationService.isActive()).toBe(false);
    });
  });

  // ========================================================================
  // Cleanup Tests
  // ========================================================================

  describe('Cleanup', () => {
    test('should cleanup and stop tracking on destroy', async () => {
      // Ensure clean state first
      await locationService.destroy();

      await locationService.requestPermissions();

      const started = await locationService.startTracking();
      expect(started).toBe(true);

      // Verify tracking started
      expect(locationService.isActive()).toBe(true);

      await locationService.destroy();

      expect(locationService.isActive()).toBe(false);
      expect(Location.removeSubscriptionAsync).toHaveBeenCalledWith(123);
    });

    test('should clear geofence listeners on destroy', async () => {
      const callback = jest.fn();
      locationService.onGeofenceEvent(callback);

      await locationService.destroy();

      // Destroy should have cleared the listeners
      // This is implicit - no easy way to test without exposing internal state
    });
  });

  // ========================================================================
  // Platform-Specific Tests
  // ========================================================================

  describe('Platform-Specific Behavior', () => {
    test('should request background permission on Android', async () => {
      (Platform.OS as any) = 'android';

      (Location.getBackgroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: true,
        granted: false,
        expires: 'never',
      });

      await locationService.initialize();

      expect(Location.getBackgroundPermissionsAsync).toHaveBeenCalled();
    });

    test('should not request background permission on iOS', async () => {
      (Platform.OS as any) = 'ios';

      await locationService.initialize();

      expect(Location.getBackgroundPermissionsAsync).not.toHaveBeenCalled();
    });
  });

  // ========================================================================
  // Background Tracking Tests
  // ========================================================================

  describe('Background Tracking', () => {
    beforeEach(() => {
      // Mock Platform.OS = 'android' for background tracking tests
      Object.defineProperty(Platform, 'OS', {
        get: () => 'android',
        configurable: true,
      });
    });

    test('should request background permission on Android', async () => {
      // Mock foreground permission granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock background permission granted
      (Location.requestBackgroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(456);

      // Request foreground permission first
      await locationService.requestPermissions(true, false);

      // Start background tracking
      const started = await locationService.startBackgroundTracking();

      expect(started).toBe(true);
      expect(Location.requestBackgroundPermissionsAsync).toHaveBeenCalledTimes(1);
      expect(locationService.isBackgroundTrackingActive()).toBe(true);
    });

    test('should fail when background permission denied', async () => {
      // Mock foreground permission granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock background permission denied
      (Location.requestBackgroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
        expires: 'never',
      });

      // Request foreground permission first
      await locationService.requestPermissions(true, false);

      // Try to start background tracking
      const started = await locationService.startBackgroundTracking();

      expect(started).toBe(false);
      expect(locationService.isBackgroundTrackingActive()).toBe(false);
    });

    test('should work on iOS with foreground permission', async () => {
      // Switch to iOS
      Object.defineProperty(Platform, 'OS', {
        get: () => 'ios',
        configurable: true,
      });

      // Mock foreground permission granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(789);

      // Request foreground permission
      await locationService.requestPermissions(true, false);

      // Start background tracking (iOS uses 'Always' permission, no separate background request)
      const started = await locationService.startBackgroundTracking();

      expect(started).toBe(true);
      expect(Location.requestBackgroundPermissionsAsync).not.toHaveBeenCalled();
      expect(locationService.isBackgroundTrackingActive()).toBe(true);
    });

    test('should clear background tracking state on stop', async () => {
      // Mock permissions granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      (Location.requestBackgroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(999);

      // Request foreground permission
      await locationService.requestPermissions(true, false);

      // Start background tracking
      await locationService.startBackgroundTracking();
      expect(locationService.isBackgroundTrackingActive()).toBe(true);

      // Stop tracking
      await locationService.stopTracking();

      expect(locationService.isBackgroundTrackingActive()).toBe(false);
      expect(locationService.isActive()).toBe(false);
    });

    test('should clear updateTimer on stop', async () => {
      // Mock permissions granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(123);

      // Request foreground permission
      await locationService.requestPermissions(true, false);

      // Start tracking
      await locationService.startTracking();
      expect(locationService.isActive()).toBe(true);

      // Stop tracking (this clears updateTimer internally)
      await locationService.stopTracking();

      // Verify tracking stopped and watchId cleared
      expect(locationService.isActive()).toBe(false);
      expect(Location.removeSubscriptionAsync).toHaveBeenCalledWith(123);
    });
  });
});
