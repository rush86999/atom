/**
 * Location Service
 *
 * Manages GPS location tracking and geofencing for mobile devices.
 *
 * Features:
 * - Current location retrieval
 * - Foreground/background location tracking
 * - Geofencing (enter/exit regions)
 * - Permission handling
 * - Distance calculations (Haversine)
 * - Location history storage
 * - Battery optimization awareness
 * - Mock location for testing
 * - Location updates throttling
 * - Settings deep link
 *
 * Uses expo-location for cross-platform location support.
 */

import * as Location from 'expo-location';
import { Platform, Linking } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Types
export type LocationPermissionStatus = 'undetermined' | 'granted' | 'denied';

export type LocationAccuracy = 'low' | 'balanced' | 'high' | 'best' | 'navigation';

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
  timestamp: number;
}

export interface LocationHistoryEntry {
  latitude: number;
  longitude: number;
  accuracy: number;
  timestamp: number;
}

// Configuration
const DEFAULT_ACCURACY = Location.Accuracy.High;
const DISTANCE_UPDATE_FILTER = 10; // meters
const UPDATE_INTERVAL = 10000; // 10 seconds
const MAX_HISTORY_ENTRIES = 1000;
const HISTORY_STORAGE_KEY = 'atom_location_history';
const GEOFENCES_STORAGE_KEY = 'atom_geofences';
const THROTTLE_MS = 5000; // 5 seconds

// Accuracy mapping
const ACCURACY_MAP: Record<LocationAccuracy, Location.LocationAccuracy> = {
  low: Location.Accuracy.Low,
  balanced: Location.Accuracy.Balanced,
  high: Location.Accuracy.High,
  best: Location.Accuracy.BestForNavigation,
  navigation: Location.Accuracy.BestForNavigation,
};

/**
 * Location Service
 */
class LocationService {
  private permissionStatus: LocationPermissionStatus = 'undetermined';
  private backgroundPermissionStatus: LocationPermissionStatus = 'undetermined';
  private currentLocation: LocationInfo | null = null;
  private isTracking: boolean = false;
  private isBackgroundTracking: boolean = false;
  private watchId: Location.LocationSubscription | null = null;
  private staleWatches = new Set<Location.LocationSubscription>();
  private trackingGeneration: number = 0;
  private activeTrackingGeneration: number | null = null;
  private pendingStart: {
    generation: number;
    completion: Promise<boolean>;
  } | null = null;
  private currentAccuracy: LocationAccuracy = 'high';
  private locationHistory: LocationHistoryEntry[] = [];
  private geofences: GeofenceRegion[] = [];
  private geofenceListeners: Set<(notification: GeofenceNotification) => void> = new Set();
  private lastLocationUpdate: number = 0;
  private updateTimer: NodeJS.Timeout | null = null;

  /**
   * Initialize the location service
   */
  async initialize(): Promise<void> {
    try {
      // Check foreground permissions
      const { status: foregroundStatus } = await Location.getForegroundPermissionsAsync();
      this.permissionStatus = foregroundStatus === 'granted' ? 'granted' : foregroundStatus;

      // Check background permissions on Android
      if (Platform.OS === 'android') {
        const { status: backgroundStatus } = await Location.getBackgroundPermissionsAsync();
        this.backgroundPermissionStatus = backgroundStatus === 'granted' ? 'granted' : backgroundStatus;
      }

      // Load saved geofences
      await this.loadGeofences();

      // Load location history
      await this.loadLocationHistory();

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
        this.permissionStatus = fgStatus === 'granted' ? 'granted' : fgStatus;
      }

      // Request background permission (Android only)
      if (background && Platform.OS === 'android' && status === Location.PermissionStatus.GRANTED) {
        const { status: bgStatus } = await Location.requestBackgroundPermissionsAsync();
        this.backgroundPermissionStatus = bgStatus === 'granted' ? 'granted' : bgStatus;
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
  async getPermissionStatus(): Promise<{
    foreground: LocationPermissionStatus;
    background: LocationPermissionStatus;
  }> {
    try {
      const { status: fgStatus } = await Location.getForegroundPermissionsAsync();
      this.permissionStatus = fgStatus === 'granted' ? 'granted' : fgStatus;

      if (Platform.OS === 'android') {
        const { status: bgStatus } = await Location.getBackgroundPermissionsAsync();
        this.backgroundPermissionStatus = bgStatus === 'granted' ? 'granted' : bgStatus;
      }

      return {
        foreground: this.permissionStatus,
        background: this.backgroundPermissionStatus,
      };
    } catch (error) {
      console.error('LocationService: Failed to get permission status:', error);
      return {
        foreground: 'denied',
        background: 'denied',
      };
    }
  }

  /**
   * Open location settings
   */
  async openSettings(): Promise<void> {
    try {
      if (Platform.OS === 'ios') {
        await Linking.openURL('app-settings:');
      } else {
        await Linking.sendIntent('android.settings.LOCATION_SOURCE_SETTINGS');
      }
    } catch (error) {
      console.error('LocationService: Failed to open settings:', error);
    }
  }

  /**
   * Set location accuracy
   */
  setAccuracy(accuracy: LocationAccuracy): void {
    this.currentAccuracy = accuracy;
    console.log('LocationService: Accuracy set to', accuracy);
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
        accuracy: ACCURACY_MAP[this.currentAccuracy],
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
      await this.addToHistory(locationInfo);
      await this.checkGeofences(locationInfo);

      console.log('LocationService: Current location retrieved', locationInfo);
      return locationInfo;
    } catch (error) {
      console.error('LocationService: Failed to get current location:', error);
      return null;
    }
  }

  /**
   * Start location tracking (foreground)
   */
  async startTracking(): Promise<boolean> {
    const result = await this.beginTracking();
    return result.success;
  }

  private async beginTracking(): Promise<{ success: boolean; generation: number }> {
    if (this.permissionStatus !== 'granted') {
      console.warn('LocationService: Location permission not granted');
      return { success: false, generation: this.trackingGeneration };
    }

    // A cancelled watch that could not be removed is not a successful start.
    // Keep its handle available to stopTracking rather than opening another one.
    if (this.staleWatches.size > 0) {
      return { success: false, generation: this.trackingGeneration };
    }

    if (this.isTracking) {
      console.log('LocationService: Already tracking');
      return {
        success: true,
        generation: this.activeTrackingGeneration ?? this.trackingGeneration,
      };
    }

    if (this.pendingStart !== null) {
      const pending = this.pendingStart;
      const success = await pending.completion;
      if (success && this.trackingGeneration !== pending.generation) {
        return { success: false, generation: pending.generation };
      }
      return { success, generation: pending.generation };
    }

    const generation = ++this.trackingGeneration;
    let watch: Promise<Location.LocationSubscription>;

    try {
      watch = Promise.resolve(
        Location.watchPositionAsync(
          {
            accuracy: ACCURACY_MAP[this.currentAccuracy],
            distanceInterval: DISTANCE_UPDATE_FILTER,
            timeInterval: UPDATE_INTERVAL,
          },
          (location) => {
            this.handleLocationUpdate(location, generation);
          }
        )
      );
    } catch (error) {
      console.error('LocationService: Failed to start tracking:', error);
      return { success: false, generation };
    }

    const completion = watch.then(
      (subscription) => {
        if (
          this.pendingStart !== null &&
          this.pendingStart.generation === generation
        ) {
          this.pendingStart = null;
        }

        if (this.trackingGeneration !== generation) {
          try {
            subscription.remove();
          } catch (error) {
            this.staleWatches.add(subscription);
            this.isTracking = true;
            console.error(
              'LocationService: Failed to remove stale tracking subscription:',
              error
            );
          }
          return false;
        }

        this.watchId = subscription;
        this.activeTrackingGeneration = generation;
        this.isTracking = true;
        console.log('LocationService: Started tracking');
        return true;
      },
      (error) => {
        if (
          this.pendingStart !== null &&
          this.pendingStart.generation === generation
        ) {
          this.pendingStart = null;
        }
        console.error('LocationService: Failed to start tracking:', error);
        return false;
      }
    );

    this.pendingStart = { generation, completion };

    const success = await completion;
    if (success && this.trackingGeneration !== generation) {
      return { success: false, generation };
    }

    return { success, generation };
  }

  /**
   * Start background location tracking
   */
  async startBackgroundTracking(): Promise<boolean> {
    const intentGeneration = this.trackingGeneration;
    try {
      if (this.permissionStatus !== 'granted') {
        console.warn('LocationService: Location permission not granted');
        return false;
      }

      // Request background permission on Android
      if (Platform.OS === 'android') {
        const { status: bgStatus } = await Location.requestBackgroundPermissionsAsync();
        if (bgStatus !== Location.PermissionStatus.GRANTED) {
          console.warn('LocationService: Background permission not granted');
          return false;
        }
        this.backgroundPermissionStatus = 'granted';
      }

      // Permission may settle after an explicit stop or a different start.
      // Its grant does not authorize resurrecting the cancelled intent.
      if (this.trackingGeneration !== intentGeneration) {
        return false;
      }

      // Start foreground tracking (background is automatic on iOS with Always permission)
      const attempt = await this.beginTracking();
      if (
        attempt.success &&
        this.isTracking &&
        this.activeTrackingGeneration === attempt.generation
      ) {
        this.isBackgroundTracking = true;
        console.log('LocationService: Started background tracking');
        return true;
      }

      return false;
    } catch (error) {
      console.error('LocationService: Failed to start background tracking:', error);
      return false;
    }
  }

  /**
   * Stop location tracking
   */
  async stopTracking(): Promise<void> {
    // These handles belong to invalidated starts. Removing them must never
    // overwrite the active handle owned by a newer generation.
    for (const subscription of this.staleWatches) {
      try {
        subscription.remove();
        this.staleWatches.delete(subscription);
      } catch (error) {
        this.isTracking = true;
        console.error('LocationService: Failed to remove cancelled watch:', error);
        return;
      }
    }
    if (this.watchId !== null) {
      try {
        this.watchId.remove();
        this.watchId = null;
      } catch (error) {
        // The subscription may still be live if remove() throws. Preserve the
        // handle and tracking flags so callers see the truthful active state
        // and a later stop can retry.
        console.error('LocationService: Failed to stop tracking:', error);
        return;
      }
    }

    // Invalidate any in-flight start and its callbacks. A late subscription
    // will remove itself instead of becoming the active watch.
    this.trackingGeneration += 1;
    this.pendingStart = null;
    this.activeTrackingGeneration = null;

    if (this.updateTimer) {
      clearTimeout(this.updateTimer);
      this.updateTimer = null;
    }

    this.isTracking = false;
    this.isBackgroundTracking = false;
    console.log('LocationService: Stopped tracking');
  }

  /**
   * Handle location update with throttling
   */
  private handleLocationUpdate(
    location: Location.LocationObject,
    generation: number = this.trackingGeneration
  ): void {
    if (this.trackingGeneration !== generation) {
      return;
    }

    const now = Date.now();
    const timeSinceLastUpdate = now - this.lastLocationUpdate;

    // Throttle updates
    if (timeSinceLastUpdate < THROTTLE_MS) {
      // Schedule update if not already scheduled
      if (!this.updateTimer) {
        this.updateTimer = setTimeout(() => {
          if (this.trackingGeneration !== generation) {
            return;
          }
          this.updateTimer = null;
          this.processLocationUpdate(location, generation);
        }, THROTTLE_MS - timeSinceLastUpdate);
      }
      return;
    }

    this.processLocationUpdate(location, generation);
  }

  /**
   * Process location update
   */
  private async processLocationUpdate(
    location: Location.LocationObject,
    generation: number = this.trackingGeneration
  ): Promise<void> {
    if (this.trackingGeneration !== generation) {
      return;
    }

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

    if (this.trackingGeneration !== generation) {
      return;
    }

    this.currentLocation = locationInfo;
    this.lastLocationUpdate = Date.now();

    if (this.trackingGeneration !== generation) {
      return;
    }
    await this.addToHistory(locationInfo);

    if (this.trackingGeneration !== generation) {
      return;
    }
    await this.checkGeofences(locationInfo);

    console.log('LocationService: Location updated', locationInfo);
  }

  /**
   * Calculate distance between two coordinates (Haversine formula)
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
    const distance = this.calculateDistance(point, {
      latitude: region.latitude,
      longitude: region.longitude,
    });
    return distance <= region.radius;
  }

  /**
   * Add geofence region
   */
  async addGeofence(region: GeofenceRegion): Promise<void> {
    this.geofences.push(region);
    await this.saveGeofences();
    console.log('LocationService: Geofence added', region.identifier);
  }

  /**
   * Remove geofence region
   */
  async removeGeofence(regionId: string): Promise<void> {
    this.geofences = this.geofences.filter((g) => g.id !== regionId);
    await this.saveGeofences();
    console.log('LocationService: Geofence removed', regionId);
  }

  /**
   * Get all geofences
   */
  getGeofences(): GeofenceRegion[] {
    return [...this.geofences];
  }

  /**
   * Check geofences for current location
   */
  private async checkGeofences(location: LocationInfo): Promise<void> {
    for (const geofence of this.geofences) {
      const isWithin = this.isWithinGeofence(location, geofence);

      // Notify on entry
      if (isWithin && geofence.notifyOnEntry) {
        this.notifyGeofenceListeners({
          region: geofence,
          event: 'enter',
          location,
          timestamp: Date.now(),
        });
      }

      // Notify on exit (if was previously within)
      if (!isWithin && geofence.notifyOnExit) {
        this.notifyGeofenceListeners({
          region: geofence,
          event: 'exit',
          location,
          timestamp: Date.now(),
        });
      }
    }
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
   * Notify geofence event listeners
   */
  private notifyGeofenceListeners(notification: GeofenceNotification): void {
    this.geofenceListeners.forEach((callback) => {
      try {
        callback(notification);
      } catch (error) {
        console.error('LocationService: Geofence listener error:', error);
      }
    });
  }

  /**
   * Add location to history
   */
  private async addToHistory(location: LocationInfo): Promise<void> {
    const entry: LocationHistoryEntry = {
      latitude: location.latitude,
      longitude: location.longitude,
      accuracy: location.accuracy || 0,
      timestamp: location.timestamp,
    };

    this.locationHistory.push(entry);

    // Limit history size
    if (this.locationHistory.length > MAX_HISTORY_ENTRIES) {
      this.locationHistory = this.locationHistory.slice(-MAX_HISTORY_ENTRIES);
    }

    // Save to storage (debounced)
    await this.saveLocationHistory();
  }

  /**
   * Get location history
   */
  async getLocationHistory(limit?: number): Promise<LocationHistoryEntry[]> {
    if (limit) {
      return this.locationHistory.slice(-limit);
    }
    return [...this.locationHistory];
  }

  /**
   * Clear location history
   */
  async clearLocationHistory(): Promise<void> {
    this.locationHistory = [];
    await AsyncStorage.removeItem(HISTORY_STORAGE_KEY);
    console.log('LocationService: Location history cleared');
  }

  /**
   * Save location history to storage
   */
  private async saveLocationHistory(): Promise<void> {
    try {
      await AsyncStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(this.locationHistory));
    } catch (error) {
      console.error('LocationService: Failed to save location history:', error);
    }
  }

  /**
   * Load location history from storage
   */
  private async loadLocationHistory(): Promise<void> {
    try {
      const data = await AsyncStorage.getItem(HISTORY_STORAGE_KEY);
      if (data) {
        this.locationHistory = JSON.parse(data);
        // Bound the in-memory history the same way addToHistory does
        if (this.locationHistory.length > MAX_HISTORY_ENTRIES) {
          this.locationHistory = this.locationHistory.slice(-MAX_HISTORY_ENTRIES);
        }
        console.log('LocationService: Location history loaded', this.locationHistory.length, 'entries');
      }
    } catch (error) {
      console.error('LocationService: Failed to load location history:', error);
    }
  }

  /**
   * Save geofences to storage
   */
  private async saveGeofences(): Promise<void> {
    try {
      await AsyncStorage.setItem(GEOFENCES_STORAGE_KEY, JSON.stringify(this.geofences));
    } catch (error) {
      console.error('LocationService: Failed to save geofences:', error);
    }
  }

  /**
   * Load geofences from storage
   */
  private async loadGeofences(): Promise<void> {
    try {
      const data = await AsyncStorage.getItem(GEOFENCES_STORAGE_KEY);
      if (data) {
        this.geofences = JSON.parse(data);
        console.log('LocationService: Geofences loaded', this.geofences.length, 'regions');
      }
    } catch (error) {
      console.error('LocationService: Failed to load geofences:', error);
    }
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
   * Check if background tracking is active
   */
  isBackgroundTrackingActive(): boolean {
    return this.isBackgroundTracking;
  }

  /**
   * Reverse geocode (address from coordinates)
   */
  async reverseGeocode(location: Coordinates): Promise<string | null> {
    try {
      const geocode = await Location.reverseGeocodeAsync(location);
      if (geocode && geocode.length > 0) {
        const parts = [
          geocode[0].street,
          geocode[0].city,
          geocode[0].region,
          geocode[0].postalCode,
        ].filter(Boolean);
        return parts.join(', ') || 'Unknown location';
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
   * Set mock location for testing
   */
  async setMockLocation(location: LocationInfo): Promise<void> {
    if (__DEV__) {
      this.currentLocation = location;
      await this.addToHistory(location);
      await this.checkGeofences(location);
      console.log('LocationService: Mock location set', location);
    }
  }

  /**
   * Get battery usage indicator
   */
  getBatteryUsage(): 'low' | 'medium' | 'high' {
    if (!this.isTracking) {
      return 'low';
    }

    if (this.isBackgroundTracking) {
      return 'high';
    }

    if (this.currentAccuracy === 'best' || this.currentAccuracy === 'navigation') {
      return 'high';
    }

    if (this.currentAccuracy === 'high') {
      return 'medium';
    }

    return 'low';
  }

  /**
   * Cleanup
   */
  async destroy(): Promise<void> {
    await this.stopTracking();
    this.geofenceListeners.clear();
    this.locationHistory = [];
    this.geofences = [];
  }

  /**
   * Reset service state (for testing)
   */
  _resetState(): void {
    this.permissionStatus = 'undetermined';
    this.backgroundPermissionStatus = 'undetermined';
    this.currentLocation = null;
    this.isTracking = false;
    this.isBackgroundTracking = false;
    this.watchId = null;
    this.staleWatches.clear();
    this.trackingGeneration += 1;
    this.activeTrackingGeneration = null;
    this.pendingStart = null;
    this.currentAccuracy = 'high';
    this.locationHistory = [];
    this.geofences = [];
    this.geofenceListeners.clear();
    this.lastLocationUpdate = 0;
    this.updateTimer = null;
  }
}

// Export singleton instance
export const locationService = new LocationService();

export default locationService;
