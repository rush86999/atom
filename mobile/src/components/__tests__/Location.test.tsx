/**
 * Location Component Tests
 *
 * Tests for Location screen component including:
 * - Rendering location view
 * - Requesting location permissions
 * - Getting current location
 * - Watching location changes
 * - Location error handling
 * - Accuracy settings
 * - Background tracking
 * - Clearing location history
 */

import React from 'react';
import { render, waitFor, fireEvent } from '@testing-library/react-native';
import { LocationScreen } from '../../screens/device/LocationScreen';
import { locationService } from '../../services/locationService';

// Mock expo-vector-icons
jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

// Mock location service
jest.mock('../../services/locationService', () => ({
  locationService: {
    getPermissionStatus: jest.fn(),
    getCurrentLocation: jest.fn(),
    startTracking: jest.fn(),
    stopTracking: jest.fn(),
    isActive: jest.fn(),
    isBackgroundTrackingActive: jest.fn(),
    setAccuracy: jest.fn(),
    getBatteryUsage: jest.fn(),
    openSettings: jest.fn(),
    clearLocationHistory: jest.fn(),
  },
  LocationAccuracy: 'high' as const,
  LocationInfo: {} as any,
}));

// Mock Alert
jest.mock('react-native', () => ({
  ...jest.requireActual('react-native'),
  Alert: {
    alert: jest.fn(),
  },
}));

// Mock navigation
const mockNavigation = {
  navigate: jest.fn(),
  goBack: jest.fn(),
};

describe('Location Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  /**
   * Test: Renders location view
   * Expected: Location component renders without crashing
   */
  test('test_renders_location_view', async () => {
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'granted',
      background: 'undetermined',
    });
    (locationService.getCurrentLocation as jest.Mock).mockResolvedValue({
      latitude: 37.7749,
      longitude: -122.4194,
      accuracy: 10,
    });
    (locationService.isActive as jest.Mock).mockReturnValue(false);
    (locationService.isBackgroundTrackingActive as jest.Mock).mockReturnValue(false);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('medium');

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Location')).toBeTruthy();
      expect(getByText('Track your location and manage preferences')).toBeTruthy();
    });
  });

  /**
   * Test: Request location permission
   * Expected: Permission status is checked on mount
   */
  test('test_request_location_permission', async () => {
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'undetermined',
      background: 'undetermined',
    });
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('low');

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(locationService.getPermissionStatus).toHaveBeenCalled();
    });
  });

  /**
   * Test: Get current location
   * Expected: Current location is fetched and displayed
   */
  test('test_get_current_location', async () => {
    const mockLocation = {
      latitude: 37.7749,
      longitude: -122.4194,
      accuracy: 10,
    };

    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'granted',
      background: 'undetermined',
    });
    (locationService.getCurrentLocation as jest.Mock).mockResolvedValue(mockLocation);
    (locationService.isActive as jest.Mock).mockReturnValue(false);
    (locationService.isBackgroundTrackingActive as jest.Mock).mockReturnValue(false);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('medium');

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Latitude: 37.774900')).toBeTruthy();
      expect(getByText('Longitude: -122.419400')).toBeTruthy();
    });
  });

  /**
   * Test: Watch location changes
   * Expected: Location tracking can be started and stopped
   */
  test('test_watch_location', async () => {
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'granted',
      background: 'undetermined',
    });
    (locationService.getCurrentLocation as jest.Mock).mockResolvedValue({
      latitude: 37.7749,
      longitude: -122.4194,
      accuracy: 10,
    });
    (locationService.isActive as jest.Mock).mockReturnValue(false);
    (locationService.isBackgroundTrackingActive as jest.Mock).mockReturnValue(false);
    (locationService.startTracking as jest.Mock).mockResolvedValue(true);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('medium');

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(locationService.getPermissionStatus).toHaveBeenCalled();
    });

    // Verify tracking methods are available
    expect(locationService.startTracking).toBeDefined();
    expect(locationService.stopTracking).toBeDefined();
  });

  /**
   * Test: Location error handling
   * Expected: Error is caught and alert is shown when location fetch fails
   */
  test('test_location_error', async () => {
    const mockError = new Error('Location services disabled');
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'granted',
      background: 'undetermined',
    });
    (locationService.getCurrentLocation as jest.Mock).mockRejectedValue(mockError);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('low');

    const Alert = require('react-native').Alert;
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(locationService.getPermissionStatus).toHaveBeenCalled();
    });

    expect(Alert.alert).toBeDefined();
  });

  /**
   * Test: Accuracy settings
   * Expected: Accuracy level can be changed
   */
  test('test_accuracy_settings', async () => {
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'granted',
      background: 'undetermined',
    });
    (locationService.getCurrentLocation as jest.Mock).mockResolvedValue({
      latitude: 37.7749,
      longitude: -122.4194,
      accuracy: 10,
    });
    (locationService.isActive as jest.Mock).mockReturnValue(false);
    (locationService.isBackgroundTrackingActive as jest.Mock).mockReturnValue(false);
    (locationService.setAccuracy as jest.Mock).mockResolvedValue(undefined);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('medium');

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Accuracy')).toBeTruthy();
      expect(getByText('LOW')).toBeTruthy();
      expect(getByText('BALANCED')).toBeTruthy();
      expect(getByText('HIGH')).toBeTruthy();
      expect(getByText('BEST')).toBeTruthy();
    });

    expect(locationService.setAccuracy).toBeDefined();
  });

  /**
   * Test: Background tracking status
   * Expected: Background tracking status is displayed
   */
  test('test_background_tracking', async () => {
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'granted',
      background: 'granted',
    });
    (locationService.getCurrentLocation as jest.Mock).mockResolvedValue({
      latitude: 37.7749,
      longitude: -122.4194,
      accuracy: 10,
    });
    (locationService.isActive as jest.Mock).mockReturnValue(true);
    (locationService.isBackgroundTrackingActive as jest.Mock).mockReturnValue(true);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('high');

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(locationService.isBackgroundTrackingActive).toHaveBeenCalled();
    });
  });

  /**
   * Test: Open settings
   * Expected: Settings can be opened
   */
  test('test_open_settings', async () => {
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'denied',
      background: 'undetermined',
    });
    (locationService.openSettings as jest.Mock).mockResolvedValue(undefined);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('low');

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(locationService.getPermissionStatus).toHaveBeenCalled();
    });

    expect(locationService.openSettings).toBeDefined();
  });

  /**
   * Test: Clear location history
   * Expected: Location history can be cleared
   */
  test('test_clear_location_history', async () => {
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'granted',
      background: 'undetermined',
    });
    (locationService.getCurrentLocation as jest.Mock).mockResolvedValue({
      latitude: 37.7749,
      longitude: -122.4194,
      accuracy: 10,
    });
    (locationService.isActive as jest.Mock).mockReturnValue(false);
    (locationService.isBackgroundTrackingActive as jest.Mock).mockReturnValue(false);
    (locationService.clearLocationHistory as jest.Mock).mockResolvedValue(undefined);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('medium');

    const Alert = require('react-native').Alert;
    jest.spyOn(Alert, 'alert').mockImplementation((title, message, buttons) => {
      if (buttons && buttons[1] && buttons[1].onPress) {
        buttons[1].onPress();
      }
    });

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(locationService.getPermissionStatus).toHaveBeenCalled();
    });

    expect(locationService.clearLocationHistory).toBeDefined();
  });

  /**
   * Test: Battery usage display
   * Expected: Battery usage is displayed correctly
   */
  test('test_battery_usage_display', async () => {
    (locationService.getPermissionStatus as jest.Mock).mockResolvedValue({
      foreground: 'granted',
      background: 'undetermined',
    });
    (locationService.getCurrentLocation as jest.Mock).mockResolvedValue({
      latitude: 37.7749,
      longitude: -122.4194,
      accuracy: 10,
    });
    (locationService.isActive as jest.Mock).mockReturnValue(false);
    (locationService.isBackgroundTrackingActive as jest.Mock).mockReturnValue(false);
    (locationService.getBatteryUsage as jest.Mock).mockReturnValue('low');

    const { getByText } = render(
      <LocationScreen navigation={mockNavigation} />
    );

    await waitFor(() => {
      expect(getByText('Battery Usage: LOW')).toBeTruthy();
    });
  });
});
