/**
 * Location Service
 *
 * Manages GPS location tracking and geofencing for mobile devices.
 *
 * Features:
 * - Current location retrieval
 * - Background location tracking
 * - Geofencing (enter/exit regions)
 * - Permission handling
 * - Distance calculations
 *
 * Uses expo-location for cross-platform location support.
 */

import * as Location from 'expo-location';
import { Platform } from 'react-native';

// Types
export type LocationPermissionStatus = 'undetermined' | 'granted' | 'denied';

export interface Coordinates {
  latitude: number;
  longitude: number;
  altitude?: number | null;
  accuracy?: number | null;
  altitudeAccuracy?: number | null;
  heading?: number | null;
  speed?: number | null;
}

export interface LocationInfo extends Coordinates {
  timestamp: number;
}

export interface GeofenceRegion {
  id: string;
  identifier: string;
  latitude: number;
  longitude: number;
  radius: number; // in meters
  notifyOnEntry: boolean;
  notifyOnExit: boolean;
}

export type GeofenceEvent = 'enter' | 'exit';

export interface GeofenceNotification {
  region: GeofenceRegion;
  event: GeofenceEvent;
  location: LocationInfo;
}

// Configuration
const LOCATION_ACCURACY = Location.Accuracy.High;
const DISTANCE_UPDATE_FILTER = 10; // meters
const UPDATE_INTERVAL = 10000; // 10 seconds

/**
 * Location Service
 */
class LocationService {
  private permissionStatus: LocationPermissionStatus = 'undetermined';
  private currentLocation: LocationInfo | null = null;
  private isTracking: boolean = false;
  private watchId: number | null = null;
  private geofenceListeners: Set<(notification: GeofenceNotification) => void> = new Set();

  /**
   * Initialize the location service
   */
  async initialize(): Promise<void> {
    try {
      // Check foreground permissions
      const { status: foregroundStatus } = await Location.getForegroundPermissionsAsync();
      this.permissionStatus = foregroundStatus === 'granted' ? 'granted' : foregroundStatus;

      if (Platform.OS === 'android') {
        // Check background permissions on Android
        const { status: backgroundStatus } = await Location.getBackgroundPermissionsAsync();
        if (backgroundStatus !== 'granted') {
          console.log('LocationService: Background permission not granted');
        }
      }

      console.log('LocationService: Initialized, permission:', this.permissionStatus);
    } catch (error) {
      console.error('LocationService: Failed to initialize:', error);
    }
  }

  /**
   * Request location permissions
   */
  async requestPermissions(foreground: boolean = true, background: boolean = false): Promise<LocationPermissionStatus> {
    try {
      let status: Location.PermissionStatus;

      // Request foreground permission
      if (foreground) {
        const { status: fgStatus } = await Location.requestForegroundPermissionsAsync();
        status = fgStatus;
        this.permissionStatus = fgStatus === 'granted' ? 'granted' : fgStatus;
      } else {
        const { status: fgStatus } = await Location.getForegroundPermissionsAsync();
        status = fgStatus;
      }

      // Request background permission (Android only)
      if (background && Platform.OS === 'android' && status === Location.PermissionStatus.GRANTED) {
        const { status: bgStatus } = await Location.requestBackgroundPermissionsAsync();
        console.log('LocationService: Background permission:', bgStatus);
      }

      console.log('LocationService: Permission requested, status:', this.permissionStatus);
      return this.permissionStatus;
    } catch (error) {
      console.error('LocationService: Failed to request permissions:', error);
      return 'denied';
    }
  }

  /**
   * Get current permission status
   */
  async getPermissionStatus(): Promise<LocationPermissionStatus> {
    const { status } = await Location.getForegroundPermissionsAsync();
    this.permissionStatus = status === 'granted' ? 'granted' : status;
    return this.permissionStatus;
  }

  /**
   * Get current location
   */
  async getCurrentLocation(): Promise<LocationInfo | null> {
    try {
      if (this.permissionStatus !== 'granted') {
        console.warn('LocationService: Location permission not granted');
        return null;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: LOCATION_ACCURACY,
      });

      const locationInfo: LocationInfo = {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        altitude: location.coords.altitude,
        accuracy: location.coords.accuracy,
        altitudeAccuracy: location.coords.altitudeAccuracy,
        heading: location.coords.heading,
        speed: location.coords.speed,
        timestamp: location.timestamp,
      };

      this.currentLocation = locationInfo;
      console.log('LocationService: Current location retrieved', locationInfo);
      return locationInfo;
    } catch (error) {
      console.error('LocationService: Failed to get current location:', error);
      return null;
    }
  }

  /**
   * Start location tracking (background)
   */
  async startTracking(): Promise<boolean> {
    try {
      if (this.permissionStatus !== 'granted') {
        console.warn('LocationService: Location permission not granted');
        return false;
      }

      if (this.isTracking) {
        console.log('LocationService: Already tracking');
        return true;
      }

      // Request background permissions on Android
      if (Platform.OS === 'android') {
        const { status: bgStatus } = await Location.requestBackgroundPermissionsAsync();
        if (bgStatus !== Location.PermissionStatus.GRANTED) {
          console.warn('LocationService: Background permission not granted');
          // Continue with foreground tracking
        }
      }

      this.watchId = await Location.watchPositionAsync(
        {
          accuracy: LOCATION_ACCURACY,
          distanceInterval: DISTANCE_UPDATE_FILTER,
          timeInterval: UPDATE_INTERVAL,
        },
        (location) => {
          const locationInfo: LocationInfo = {
            latitude: location.coords.latitude,
            longitude: location.coords.longitude,
            altitude: location.coords.altitude,
            accuracy: location.coords.accuracy,
            altitudeAccuracy: location.coords.altitudeAccuracy,
            heading: location.coords.heading,
            speed: location.coords.speed,
            timestamp: location.timestamp,
          };

          this.currentLocation = locationInfo;
          console.log('LocationService: Location updated', locationInfo);
        }
      );

      this.isTracking = true;
      console.log('LocationService: Started tracking');
      return true;
    } catch (error) {
      console.error('LocationService: Failed to start tracking:', error);
      return false;
    }
  }

  /**
   * Stop location tracking
   */
  async stopTracking(): Promise<void> {
    try {
      if (this.watchId !== null) {
        await Location.removeSubscriptionAsync(this.watchId);
        this.watchId = null;
      }

      this.isTracking = false;
      console.log('LocationService: Stopped tracking');
    } catch (error) {
      console.error('LocationService: Failed to stop tracking:', error);
    }
  }

  /**
   * Calculate distance between two coordinates
   */
  calculateDistance(from: Coordinates, to: Coordinates): number {
    const R = 6371e3; // Earth's radius in meters
    const φ1 = (from.latitude * Math.PI) / 180;
    const φ2 = (to.latitude * Math.PI) / 180;
    const Δφ = ((to.latitude - from.latitude) * Math.PI) / 180;
    const Δλ = ((to.longitude - from.longitude) * Math.PI) / 180;

    const a = Math.sin(Δφ / 2) * Math.sin(Δφ / 2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ / 2) * Math.sin(Δλ / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));

    return R * c; // Distance in meters
  }

  /**
   * Check if point is within geofence region
   */
  isWithinGeofence(point: Coordinates, region: GeofenceRegion): boolean {
    const distance = this.calculateDistance(point, region);
    return distance <= region.radius;
  }

  /**
   * Subscribe to geofence events
   */
  onGeofenceEvent(callback: (notification: GeofenceNotification) => void): () => void {
    this.geofenceListeners.add(callback);
    return () => {
      this.geofenceListeners.delete(callback);
    };
  }

  /**
   * Get last known location
   */
  getLastKnownLocation(): LocationInfo | null {
    return this.currentLocation;
  }

  /**
   * Check if currently tracking
   */
  isActive(): boolean {
    return this.isTracking;
  }

  /**
   * Reverse geocode (address from coordinates)
   */
  async reverseGeocode(location: Coordinates): Promise<string | null> {
    try {
      const geocode = await Location.reverseGeocodeAsync(location);
      if (geocode && geocode.length > 0) {
        return geocode[0].street || geocode[0].city || geocode[0].region || 'Unknown';
      }
      return null;
    } catch (error) {
      console.error('LocationService: Reverse geocode failed:', error);
      return null;
    }
  }

  /**
   * Geocode (coordinates from address)
   */
  async geocode(address: string): Promise<Coordinates | null> {
    try {
      const geocode = await Location.geocodeAsync(address);
      if (geocode && geocode.length > 0) {
        return {
          latitude: geocode[0].latitude,
          longitude: geocode[0].longitude,
        };
      }
      return null;
    } catch (error) {
      console.error('LocationService: Geocode failed:', error);
      return null;
    }
  }

  /**
   * Cleanup
   */
  async destroy(): Promise<void> {
    await this.stopTracking();
    this.geofenceListeners.clear();
  }
}

// Export singleton instance
export const locationService = new LocationService();

export default locationService;
