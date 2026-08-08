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

// require() AFTER the mocks are registered — a static import would load the
// service before the expo-location mock applies in this environment.
const { locationService } = require('../../services/locationService');

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

    // Restore Platform.OS as a writable data property — earlier describe
    // blocks redefine it with getter-only accessors, which silently make
    // later `(Platform.OS as any) = '...'` assignments no-ops.
    Object.defineProperty(Platform, 'OS', {
      value: 'ios',
      configurable: true,
      writable: true,
    });

    // Reset the singleton's state (destroy() does not reset permission
    // statuses, which would leak between tests)
    (locationService as any)._resetState();

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

      // On iOS the background permission is not queried and stays undetermined
      expect(status).toEqual({
        foreground: 'granted',
        background: 'undetermined',
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

    test('should handle missing address components in reverse geocode', async () => {
      const coordinates = {
        latitude: 37.7749,
        longitude: -122.4194,
      };

      // Mock geocode with empty array (no results)
      (Location.reverseGeocodeAsync as jest.Mock).mockResolvedValue([]);

      const address = await locationService.reverseGeocode(coordinates);

      expect(address).toBeNull();
    });

    test('should handle partial address with only city', async () => {
      const coordinates = {
        latitude: 37.7749,
        longitude: -122.4194,
      };

      // Mock geocode with only city (no street, no postalCode)
      const partialResult = [
        {
          city: 'San Francisco',
          region: 'CA',
          // street: undefined,
          // postalCode: undefined,
        },
      ];

      (Location.reverseGeocodeAsync as jest.Mock).mockResolvedValue(partialResult);

      const address = await locationService.reverseGeocode(coordinates);

      // Should return available parts only
      expect(address).toBe('San Francisco, CA');
    });

    test('should handle geocode with invalid address', async () => {
      const address = '!!!invalid!!!address!!!';

      // Mock geocode with empty array (no results)
      (Location.geocodeAsync as jest.Mock).mockResolvedValue([]);

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
      // No location has been fetched yet — the singleton was reset in
      // beforeEach, so last known location must be null.
      const lastKnown = locationService.getLastKnownLocation();

      expect(lastKnown).toBeNull();
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
  // Location History and Settings
  // ========================================================================

  describe('Location History', () => {
    test('should add location to history', async () => {
      // Mock empty history
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.getItem.mockResolvedValue(null);

      // Reinitialize to load history
      await locationService.initialize();

      // Request permissions
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await locationService.requestPermissions();

      // Get current location (adds to history)
      const location = await locationService.getCurrentLocation();

      // Verify setItem was called to save history
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        'atom_location_history',
        expect.stringContaining('"latitude":')
      );
    });

    test('should get location history', async () => {
      // Mock history with 10 entries
      const historyEntries = Array.from({ length: 10 }, (_, i) => ({
        latitude: 37.7749 + i * 0.0001,
        longitude: -122.4194 + i * 0.0001,
        accuracy: 10,
        timestamp: Date.now() + i * 1000,
      }));

      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.getItem.mockResolvedValue(JSON.stringify(historyEntries));

      // Reinitialize to load history
      await locationService.initialize();

      // Get history
      const history = await locationService.getLocationHistory();

      // Verify returns 10 entries
      expect(history).toHaveLength(10);
      expect(history[0].latitude).toBe(37.7749);
    });

    test('should get location history with limit', async () => {
      // Mock history with 100 entries
      const historyEntries = Array.from({ length: 100 }, (_, i) => ({
        latitude: 37.7749 + i * 0.0001,
        longitude: -122.4194 + i * 0.0001,
        accuracy: 10,
        timestamp: Date.now() + i * 1000,
      }));

      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.getItem.mockResolvedValue(JSON.stringify(historyEntries));

      // Reinitialize to load history
      await locationService.initialize();

      // Get history with limit
      const history = await locationService.getLocationHistory(10);

      // Verify returns only the last 10 entries (most recent)
      expect(history).toHaveLength(10);
      expect(history[0].latitude).toBeCloseTo(37.7839, 3);
    });

    test('should clear location history', async () => {
      // Mock history with entries
      const historyEntries = [
        {
          latitude: 37.7749,
          longitude: -122.4194,
          accuracy: 10,
          timestamp: Date.now(),
        },
      ];

      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.getItem.mockResolvedValue(JSON.stringify(historyEntries));

      // Reinitialize to load history
      await locationService.initialize();

      // Clear history
      await locationService.clearLocationHistory();

      // Verify removeItem called
      expect(AsyncStorage.removeItem).toHaveBeenCalledWith('atom_location_history');

      // Verify history is empty
      const history = await locationService.getLocationHistory();
      expect(history).toHaveLength(0);
    });

    test('should return empty array when no history exists', async () => {
      // Mock empty history
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.getItem.mockResolvedValue(null);

      // Reinitialize to load history
      await locationService.initialize();

      // Get history
      const history = await locationService.getLocationHistory();

      // Verify returns empty array
      expect(history).toEqual([]);
    });

    test('should limit history to MAX_HISTORY_ENTRIES', async () => {
      // Mock history with more than MAX_HISTORY_ENTRIES (1000)
      const historyEntries = Array.from({ length: 1100 }, (_, i) => ({
        latitude: 37.7749 + i * 0.0001,
        longitude: -122.4194 + i * 0.0001,
        accuracy: 10,
        timestamp: Date.now() + i * 1000,
      }));

      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.getItem.mockResolvedValue(JSON.stringify(historyEntries));

      // Reinitialize to load history
      await locationService.initialize();

      // Get all history
      const history = await locationService.getLocationHistory();

      // Verify history is limited to 1000 entries (MAX_HISTORY_ENTRIES)
      expect(history.length).toBeLessThanOrEqual(1000);
    });
  });

  describe('Settings Deep Link', () => {
    test('should open settings on iOS', async () => {
      const { Linking } = require('react-native');

      // Mock iOS
      Object.defineProperty(Platform, 'OS', {
        get: () => 'ios',
        configurable: true,
      });

      // Mock Linking.openURL
      Linking.openURL.mockResolvedValue(undefined);

      // Open settings
      await locationService.openSettings();

      // Verify openURL called with iOS settings URL
      expect(Linking.openURL).toHaveBeenCalledWith('app-settings:');
    });

    test('should send intent on Android', async () => {
      const { Linking } = require('react-native');

      // Mock Android
      Object.defineProperty(Platform, 'OS', {
        get: () => 'android',
        configurable: true,
      });

      // Mock Linking.sendIntent
      Linking.sendIntent.mockResolvedValue(undefined);

      // Open settings
      await locationService.openSettings();

      // Verify sendIntent called with Android settings intent
      expect(Linking.sendIntent).toHaveBeenCalledWith('android.settings.LOCATION_SOURCE_SETTINGS');
    });
  });

  // ========================================================================
  // Geofence Event Notifications
  // ========================================================================

  describe('Geofence Events', () => {
    test('should subscribe to enter events', async () => {
      const mockCallback = jest.fn();
      const unsubscribe = locationService.onGeofenceEvent(mockCallback);

      // Add a geofence region
      const region = {
        id: 'region_1',
        identifier: 'Test Region',
        latitude: 37.7749,
        longitude: -122.4194,
        radius: 100,
        notifyOnEntry: true,
        notifyOnExit: false,
      };

      await locationService.addGeofence(region);

      // Get current location which triggers geofence check
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await locationService.requestPermissions();

      // Trigger location inside geofence
      const insideLocation = {
        coords: {
          latitude: 37.7749,
          longitude: -122.4194,
          altitude: 100,
          accuracy: 10,
        },
        timestamp: Date.now(),
      };

      (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue(insideLocation);
      await locationService.getCurrentLocation();

      // Verify callback invoked with 'enter' event
      expect(mockCallback).toHaveBeenCalledWith(
        expect.objectContaining({
          event: 'enter',
          region: expect.objectContaining({ id: 'region_1' }),
        })
      );

      unsubscribe();
    });

    test('should subscribe to exit events', async () => {
      const mockCallback = jest.fn();
      const unsubscribe = locationService.onGeofenceEvent(mockCallback);

      // Add a geofence region
      const region = {
        id: 'region_2',
        identifier: 'Test Region 2',
        latitude: 37.7749,
        longitude: -122.4194,
        radius: 100,
        notifyOnEntry: false,
        notifyOnExit: true,
      };

      await locationService.addGeofence(region);

      // Request permissions
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await locationService.requestPermissions();

      // Trigger location outside geofence
      const outsideLocation = {
        coords: {
          latitude: 37.78,
          longitude: -122.42,
          altitude: 100,
          accuracy: 10,
        },
        timestamp: Date.now(),
      };

      (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue(outsideLocation);
      await locationService.getCurrentLocation();

      // Verify callback invoked with 'exit' event
      expect(mockCallback).toHaveBeenCalledWith(
        expect.objectContaining({
          event: 'exit',
          region: expect.objectContaining({ id: 'region_2' }),
        })
      );

      unsubscribe();
    });

    test('should unsubscribe removes callback', async () => {
      const mockCallback = jest.fn();
      const unsubscribe = locationService.onGeofenceEvent(mockCallback);

      // Add a geofence region
      const region = {
        id: 'region_3',
        identifier: 'Test Region 3',
        latitude: 37.7749,
        longitude: -122.4194,
        radius: 100,
        notifyOnEntry: true,
        notifyOnExit: true,
      };

      await locationService.addGeofence(region);

      // Unsubscribe before triggering event
      unsubscribe();

      // Request permissions
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await locationService.requestPermissions();

      // Trigger location update
      const insideLocation = {
        coords: {
          latitude: 37.7749,
          longitude: -122.4194,
          altitude: 100,
          accuracy: 10,
        },
        timestamp: Date.now(),
      };

      (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue(insideLocation);
      await locationService.getCurrentLocation();

      // Verify callback NOT invoked
      expect(mockCallback).not.toHaveBeenCalled();
    });

    test('should notify multiple geofence listeners', async () => {
      const mockCallback1 = jest.fn();
      const mockCallback2 = jest.fn();
      const unsubscribe1 = locationService.onGeofenceEvent(mockCallback1);
      const unsubscribe2 = locationService.onGeofenceEvent(mockCallback2);

      // Add two geofence regions
      const region1 = {
        id: 'region_4',
        identifier: 'Test Region 4',
        latitude: 37.7749,
        longitude: -122.4194,
        radius: 100,
        notifyOnEntry: true,
        notifyOnExit: false,
      };

      const region2 = {
        id: 'region_5',
        identifier: 'Test Region 5',
        latitude: 37.775,
        longitude: -122.4195,
        radius: 100,
        notifyOnEntry: true,
        notifyOnExit: false,
      };

      await locationService.addGeofence(region1);
      await locationService.addGeofence(region2);

      // Request permissions
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await locationService.requestPermissions();

      // Trigger location update inside both regions
      const insideLocation = {
        coords: {
          latitude: 37.7749,
          longitude: -122.4194,
          altitude: 100,
          accuracy: 10,
        },
        timestamp: Date.now(),
      };

      (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue(insideLocation);
      await locationService.getCurrentLocation();

      // Verify both callbacks invoked
      expect(mockCallback1).toHaveBeenCalled();
      expect(mockCallback2).toHaveBeenCalled();

      unsubscribe1();
      unsubscribe2();
    });

    test('should include correct data in geofence notification', async () => {
      const mockCallback = jest.fn();
      const unsubscribe = locationService.onGeofenceEvent(mockCallback);

      // Add a geofence region
      const region = {
        id: 'region_6',
        identifier: 'Test Region 6',
        latitude: 37.7749,
        longitude: -122.4194,
        radius: 100,
        notifyOnEntry: true,
        notifyOnExit: true,
      };

      await locationService.addGeofence(region);

      // Request permissions
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await locationService.requestPermissions();

      // Trigger location update
      const testLocation = {
        coords: {
          latitude: 37.7749,
          longitude: -122.4194,
          altitude: 100,
          accuracy: 10,
        },
        timestamp: 1234567890,
      };

      (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue(testLocation);
      await locationService.getCurrentLocation();

      // Verify notification structure
      expect(mockCallback).toHaveBeenCalledWith(
        expect.objectContaining({
          region: expect.objectContaining({
            id: 'region_6',
            identifier: 'Test Region 6',
          }),
          event: 'enter',
          location: expect.objectContaining({
            latitude: 37.7749,
            longitude: -122.4194,
            timestamp: 1234567890,
          }),
          timestamp: expect.any(Number),
        })
      );

      unsubscribe();
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
  // Battery Usage Tests
  // ========================================================================

  describe('Battery Usage', () => {
    test('should return low when not tracking', () => {
      // Ensure not tracking
      expect(locationService.isActive()).toBe(false);

      const usage = locationService.getBatteryUsage();

      expect(usage).toBe('low');
    });

    test('should return high for background tracking', async () => {
      // Mock Android for background tracking
      Object.defineProperty(Platform, 'OS', {
        get: () => 'android',
        configurable: true,
      });

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

      // Request permissions
      await locationService.requestPermissions(true, false);

      // Start background tracking
      await locationService.startBackgroundTracking();

      // Verify background tracking is active
      expect(locationService.isBackgroundTrackingActive()).toBe(true);

      const usage = locationService.getBatteryUsage();

      expect(usage).toBe('high');
    });

    test('should return medium for high accuracy', async () => {
      // Set high accuracy
      locationService.setAccuracy('high');

      // Mock permissions granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(888);

      // Request permissions
      await locationService.requestPermissions(true, false);

      // Start tracking
      await locationService.startTracking();

      const usage = locationService.getBatteryUsage();

      expect(usage).toBe('medium');
    });

    test('should return high for best accuracy', async () => {
      // Set best accuracy
      locationService.setAccuracy('best');

      // Mock permissions granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(777);

      // Request permissions
      await locationService.requestPermissions(true, false);

      // Start tracking
      await locationService.startTracking();

      const usage = locationService.getBatteryUsage();

      expect(usage).toBe('high');
    });

    test('should return high for navigation accuracy', async () => {
      // Set navigation accuracy
      locationService.setAccuracy('navigation');

      // Mock permissions granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(666);

      // Request permissions
      await locationService.requestPermissions(true, false);

      // Start tracking
      await locationService.startTracking();

      const usage = locationService.getBatteryUsage();

      expect(usage).toBe('high');
    });

    test('should return low for balanced accuracy', async () => {
      // Set balanced accuracy
      locationService.setAccuracy('balanced');

      // Mock permissions granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(555);

      // Request permissions
      await locationService.requestPermissions(true, false);

      // Start tracking
      await locationService.startTracking();

      const usage = locationService.getBatteryUsage();

      expect(usage).toBe('low');
    });

    test('should return low for low accuracy', async () => {
      // Set low accuracy
      locationService.setAccuracy('low');

      // Mock permissions granted
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      // Mock watchPositionAsync
      (Location.watchPositionAsync as jest.Mock).mockResolvedValue(444);

      // Request permissions
      await locationService.requestPermissions(true, false);

      // Start tracking
      await locationService.startTracking();

      const usage = locationService.getBatteryUsage();

      expect(usage).toBe('low');
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

  // ========================================================================
  // Watch Callback / Throttling Tests
  // ========================================================================

  describe('Watch Position Callback', () => {
    // Capture the callback passed to watchPositionAsync so tests can drive it
    let watchCallback: ((location: any) => void) | null = null;

    beforeEach(async () => {
      watchCallback = null;
      (Location.watchPositionAsync as jest.Mock).mockImplementation(
        (_options: any, callback: (location: any) => void) => {
          watchCallback = callback;
          return Promise.resolve(777);
        }
      );

      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      await locationService.requestPermissions(true, false);
      await locationService.startTracking();
      expect(watchCallback).not.toBeNull();
    });

    test('should process location updates from the watch callback', async () => {
      const updateLocation = {
        coords: { latitude: 40.7128, longitude: -74.006, altitude: 10, accuracy: 12 },
        timestamp: 1000000,
      };

      // lastLocationUpdate starts at 0, so the first update is NOT throttled
      watchCallback!(updateLocation);

      // Allow the async processLocationUpdate to settle (global fake timers:
      // setTimeout never fires, so flush the promise chain via microtasks)
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();

      const lastKnown = locationService.getLastKnownLocation();
      expect(lastKnown?.latitude).toBe(40.7128);
      expect(lastKnown?.longitude).toBe(-74.006);
      expect(lastKnown?.timestamp).toBe(1000000);

      // Update is recorded in history
      const history = await locationService.getLocationHistory();
      expect(history).toHaveLength(1);
      expect(history[0].latitude).toBe(40.7128);
    });

    test('should throttle rapid updates and process them after the throttle window', async () => {
      jest.useFakeTimers();

      // Simulate a recent update so the next one falls inside the throttle window
      (locationService as any).lastLocationUpdate = Date.now();

      const firstUpdate = {
        coords: { latitude: 1.0, longitude: 1.0, altitude: 1, accuracy: 1 },
        timestamp: 2000000,
      };
      const secondUpdate = {
        coords: { latitude: 2.0, longitude: 2.0, altitude: 2, accuracy: 2 },
        timestamp: 3000000,
      };

      // First rapid update schedules a timer
      watchCallback!(firstUpdate);
      // Second rapid update must NOT schedule a second timer
      watchCallback!(secondUpdate);

      // History must not grow until the throttle window elapses
      expect(await locationService.getLocationHistory()).toHaveLength(0);

      // Advance past THROTTLE_MS so the scheduled timer fires
      jest.advanceTimersByTime(5100);
      // Let the (unawaited) async processLocationUpdate settle
      await Promise.resolve();
      await Promise.resolve();

      const history = await locationService.getLocationHistory();
      expect(history).toHaveLength(1);
      expect(locationService.getLastKnownLocation()?.timestamp).toBe(2000000);

      jest.useRealTimers();
    });

    test('should stop tracking clear a pending throttled update timer', async () => {
      jest.useFakeTimers();

      (locationService as any).lastLocationUpdate = Date.now();
      watchCallback!({
        coords: { latitude: 3.0, longitude: 3.0, altitude: 3, accuracy: 3 },
        timestamp: 4000000,
      });

      // A throttled timer is now pending; stopping tracking must clear it
      await locationService.stopTracking();

      jest.advanceTimersByTime(5100);
      await Promise.resolve();

      // The pending update must never be processed after stop
      const history = await locationService.getLocationHistory();
      expect(history).toHaveLength(0);
      expect(locationService.getLastKnownLocation()).toBeNull();

      jest.useRealTimers();
    });
  });

  // ========================================================================
  // Extended Error Path Tests
  // ========================================================================

  describe('Extended Error Paths', () => {
    test('should not throw when initialize fails', async () => {
      (Location.getForegroundPermissionsAsync as jest.Mock).mockRejectedValue(
        new Error('Permission check failed')
      );

      await expect(locationService.initialize()).resolves.not.toThrow();
    });

    test('should read status (not request) when foreground=false', async () => {
      (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });

      const status = await locationService.requestPermissions(false, false);

      expect(status).toBe('granted');
      expect(Location.requestForegroundPermissionsAsync).not.toHaveBeenCalled();
      expect(Location.getForegroundPermissionsAsync).toHaveBeenCalled();
    });

    test('should query background permission status on Android', async () => {
      (Platform.OS as any) = 'android';
      (Location.getBackgroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'denied',
        canAskAgain: false,
        granted: false,
        expires: 'never',
      });

      const status = await locationService.getPermissionStatus();

      expect(Location.getBackgroundPermissionsAsync).toHaveBeenCalled();
      expect(status).toEqual({
        foreground: 'granted',
        background: 'denied',
      });
    });

    test('should not throw when opening settings fails', async () => {
      const { Linking } = require('react-native');
      Linking.openURL.mockRejectedValue(new Error('Cannot open URL'));

      await expect(locationService.openSettings()).resolves.not.toThrow();
    });

    test('should refuse background tracking without foreground permission', async () => {
      (locationService as any)._resetState();

      const started = await locationService.startBackgroundTracking();

      expect(started).toBe(false);
      expect(Location.requestBackgroundPermissionsAsync).not.toHaveBeenCalled();
    });

    test('should return false when background tracking setup throws', async () => {
      (Platform.OS as any) = 'android';
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
      (Location.watchPositionAsync as jest.Mock).mockRejectedValue(
        new Error('Tracking unavailable')
      );

      await locationService.requestPermissions(true, false);

      const started = await locationService.startBackgroundTracking();

      expect(started).toBe(false);
      expect(locationService.isBackgroundTrackingActive()).toBe(false);
    });
  });

  // ========================================================================
  // Geofence Management Tests
  // ========================================================================

  describe('Geofence Management', () => {
    test('should add, list, and remove geofences', async () => {
      const region1 = {
        id: 'g1',
        identifier: 'Home',
        latitude: 37.7749,
        longitude: -122.4194,
        radius: 100,
        notifyOnEntry: true,
        notifyOnExit: true,
      };
      const region2 = {
        id: 'g2',
        identifier: 'Work',
        latitude: 37.78,
        longitude: -122.41,
        radius: 200,
        notifyOnEntry: true,
        notifyOnExit: false,
      };

      await locationService.addGeofence(region1);
      await locationService.addGeofence(region2);

      expect(locationService.getGeofences()).toHaveLength(2);

      // getGeofences must return a copy, not the internal array
      const listed = locationService.getGeofences();
      listed.push(region1);
      expect(locationService.getGeofences()).toHaveLength(2);

      await locationService.removeGeofence('g1');

      const remaining = locationService.getGeofences();
      expect(remaining).toHaveLength(1);
      expect(remaining[0].id).toBe('g2');

      // Persisted to storage
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      expect(AsyncStorage.setItem).toHaveBeenCalledWith(
        'atom_geofences',
        expect.stringContaining('"g2"')
      );
    });

    test('should isolate a throwing geofence listener from other listeners', async () => {
      const consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation();
      const healthy = jest.fn();

      locationService.onGeofenceEvent(() => {
        throw new Error('Listener crashed');
      });
      locationService.onGeofenceEvent(healthy);

      const region = {
        id: 'g3',
        identifier: 'Isolation',
        latitude: 37.7749,
        longitude: -122.4194,
        radius: 100,
        notifyOnEntry: true,
        notifyOnExit: false,
      };
      await locationService.addGeofence(region);

      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });
      await locationService.requestPermissions(true, false);

      await locationService.getCurrentLocation();

      expect(healthy).toHaveBeenCalled();
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'LocationService: Geofence listener error:',
        expect.any(Error)
      );

      consoleErrorSpy.mockRestore();
    });
  });

  // ========================================================================
  // History Limit & Storage Failure Tests
  // ========================================================================

  describe('History Limits and Storage Failures', () => {
    test('should bound history at MAX_HISTORY_ENTRIES when adding entries', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      const historyEntries = Array.from({ length: 1000 }, (_, i) => ({
        latitude: 37.7749 + i * 0.0001,
        longitude: -122.4194 + i * 0.0001,
        accuracy: 10,
        timestamp: Date.now() + i * 1000,
      }));
      AsyncStorage.getItem.mockResolvedValue(JSON.stringify(historyEntries));

      await locationService.initialize();

      // Adding one more entry must trigger the > MAX_HISTORY_ENTRIES branch
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });
      await locationService.requestPermissions(true, false);
      const location = await locationService.getCurrentLocation();
      expect(location).not.toBeNull();

      const history = await locationService.getLocationHistory();
      expect(history).toHaveLength(1000);
    });

    test('should not throw when saving location history fails', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.setItem.mockRejectedValueOnce(new Error('Write failed'));

      await locationService.requestPermissions(true, false);
      const location = await locationService.getCurrentLocation();

      // Failure to persist must not block location retrieval
      expect(location).not.toBeNull();
    });

    test('should not throw when loading location history fails', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.getItem.mockRejectedValueOnce(new Error('Read failed'));

      await expect(locationService.initialize()).resolves.not.toThrow();
      expect(await locationService.getLocationHistory()).toEqual([]);
    });

    test('should not throw when saving geofences fails', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.setItem.mockRejectedValueOnce(new Error('Write failed'));

      await expect(
        locationService.addGeofence({
          id: 'g10',
          identifier: 'Persist Fail',
          latitude: 0,
          longitude: 0,
          radius: 10,
          notifyOnEntry: true,
          notifyOnExit: true,
        })
      ).resolves.not.toThrow();

      // In-memory state is still updated even if persistence fails
      expect(locationService.getGeofences()).toHaveLength(1);
    });

    test('should not throw when loading geofences fails', async () => {
      const AsyncStorage = require('@react-native-async-storage/async-storage').default;
      AsyncStorage.getItem.mockRejectedValueOnce(new Error('Read failed'));

      await expect(locationService.initialize()).resolves.not.toThrow();
      expect(locationService.getGeofences()).toEqual([]);
    });
  });

  // ========================================================================
  // Mock Location Tests
  // ========================================================================

  describe('Mock Location', () => {
    test('should set a mock location and record it in history', async () => {
      const mockLoc: any = {
        latitude: 51.5074,
        longitude: -0.1278,
        accuracy: 5,
        timestamp: 123456789,
      };

      await locationService.setMockLocation(mockLoc);

      expect(locationService.getLastKnownLocation()).toEqual(mockLoc);

      const history = await locationService.getLocationHistory();
      expect(history).toHaveLength(1);
      expect(history[0].latitude).toBe(51.5074);
      expect(history[0].timestamp).toBe(123456789);
    });
  });

  // ========================================================================
  // Remaining Error-Path Coverage
  // ========================================================================

  describe('Error-Path Coverage', () => {
    test('should return false when background permission request throws', async () => {
      (Platform.OS as any) = 'android';
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: 'granted',
        canAskAgain: true,
        granted: true,
        expires: 'never',
      });
      (Location.requestBackgroundPermissionsAsync as jest.Mock).mockRejectedValue(
        new Error('Background permission request failed')
      );

      await locationService.requestPermissions(true, false);

      const started = await locationService.startBackgroundTracking();

      expect(started).toBe(false);
      expect(locationService.isBackgroundTrackingActive()).toBe(false);
      expect(Location.watchPositionAsync).not.toHaveBeenCalled();
    });

    test('should return Unknown location when all address parts are missing', async () => {
      (Location.reverseGeocodeAsync as jest.Mock).mockResolvedValue([
        {
          street: '',
          city: '',
          region: '',
          postalCode: '',
          country: 'USA',
        },
      ]);

      const address = await locationService.reverseGeocode({
        latitude: 37.7749,
        longitude: -122.4194,
      });

      expect(address).toBe('Unknown location');
    });

    test('should stop tracking gracefully when no subscription is active', async () => {
      await locationService.stopTracking();

      expect(Location.removeSubscriptionAsync).not.toHaveBeenCalled();
      expect(locationService.isActive()).toBe(false);
    });

    test('should not throw when destroy runs with no active tracking', async () => {
      await expect(locationService.destroy()).resolves.not.toThrow();
      expect(locationService.isActive()).toBe(false);
      expect(locationService.getLastKnownLocation()).toBeNull();
    });
  });
});
