/**
 * LocationScreen Component Tests
 *
 * Tests for location display, tracking toggle, accuracy selection,
 * permission status rendering, settings deep link, and history clearing.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react-native';
import { LocationScreen } from '../../../screens/device/LocationScreen';

jest.mock('@expo/vector-icons', () => ({
  Ionicons: 'Ionicons',
}));

const mockLocation = {
  latitude: 37.7749,
  longitude: -122.4194,
  accuracy: 10,
  timestamp: Date.now(),
};

// Mock locationService
jest.mock('../../../services/locationService', () => ({
  locationService: {
    getPermissionStatus: jest.fn(),
    getCurrentLocation: jest.fn(),
    isActive: jest.fn(),
    isBackgroundTrackingActive: jest.fn(),
    startTracking: jest.fn(),
    stopTracking: jest.fn(),
    openSettings: jest.fn(),
    clearLocationHistory: jest.fn(),
    getBatteryUsage: jest.fn(),
    setAccuracy: jest.fn(),
  },
}));

const { locationService } = require('../../../services/locationService');

const Alert = require('react-native/Libraries/Alert/Alert').alert;

function mockPermissionsGranted() {
  locationService.getPermissionStatus.mockResolvedValue({
    foreground: 'granted',
    background: 'granted',
  });
}

describe('LocationScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPermissionsGranted();
    locationService.getCurrentLocation.mockResolvedValue(mockLocation);
    locationService.isActive.mockReturnValue(false);
    locationService.isBackgroundTrackingActive.mockReturnValue(false);
    locationService.startTracking.mockResolvedValue(true);
    locationService.stopTracking.mockResolvedValue(undefined);
    locationService.getBatteryUsage.mockReturnValue('low');
  });

  describe('Initialization', () => {
    it('loads current location when permission granted', async () => {
      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(locationService.getPermissionStatus).toHaveBeenCalled();
        expect(locationService.getCurrentLocation).toHaveBeenCalled();
        expect(getByText('Latitude: 37.774900')).toBeTruthy();
        expect(getByText('Longitude: -122.419400')).toBeTruthy();
        expect(getByText('Accuracy: ±10 meters')).toBeTruthy();
      });
    });

    it('shows "No location data" when permission denied', async () => {
      locationService.getPermissionStatus.mockResolvedValue({
        foreground: 'denied',
        background: 'denied',
      });

      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('No location data')).toBeTruthy();
        expect(locationService.getCurrentLocation).not.toHaveBeenCalled();
      });
    });

    it('shows denied permission badges', async () => {
      locationService.getPermissionStatus.mockResolvedValue({
        foreground: 'denied',
        background: 'undetermined',
      });

      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('denied')).toBeTruthy();
        expect(getByText('undetermined')).toBeTruthy();
      });
    });
  });

  describe('Get Current Location', () => {
    it('updates location when button pressed', async () => {
      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Latitude: 37.774900')).toBeTruthy();
      });

      locationService.getCurrentLocation.mockResolvedValue({
        ...mockLocation,
        latitude: 40.7128,
        longitude: -74.006,
        accuracy: 25,
      });

      fireEvent.press(getByText('Get Current Location'));

      await waitFor(() => {
        expect(getByText('Latitude: 40.712800')).toBeTruthy();
        expect(getByText('Accuracy: ±25 meters')).toBeTruthy();
      });
    });

    it('shows error alert when location fetch fails', async () => {
      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Get Current Location')).toBeTruthy();
      });

      locationService.getCurrentLocation.mockRejectedValue(
        new Error('Location services disabled')
      );

      fireEvent.press(getByText('Get Current Location'));

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Location services disabled');
      });
    });
  });

  describe('Tracking', () => {
    it('turns tracking on and off', async () => {
      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('OFF')).toBeTruthy();
      });

      fireEvent.press(getByText('OFF'));

      await waitFor(() => {
        expect(locationService.startTracking).toHaveBeenCalled();
        expect(getByText('ON')).toBeTruthy();
      });

      fireEvent.press(getByText('ON'));

      await waitFor(() => {
        expect(locationService.stopTracking).toHaveBeenCalled();
        expect(getByText('OFF')).toBeTruthy();
      });
    });

    it('shows error alert when startTracking fails', async () => {
      locationService.startTracking.mockResolvedValue(false);

      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('OFF')).toBeTruthy();
      });

      fireEvent.press(getByText('OFF'));

      await waitFor(() => {
        expect(Alert).toHaveBeenCalledWith('Error', 'Failed to start location tracking');
        expect(getByText('OFF')).toBeTruthy();
      });
    });

    it('restores tracking state from service on init', async () => {
      locationService.isActive.mockReturnValue(true);
      locationService.isBackgroundTrackingActive.mockReturnValue(true);

      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('ON')).toBeTruthy();
      });
    });

    it('shows battery usage from service', async () => {
      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Battery Usage: LOW')).toBeTruthy();
      });
    });
  });

  describe('Accuracy', () => {
    it('selects accuracy level and updates the service', async () => {
      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('HIGH')).toBeTruthy();
      });

      fireEvent.press(getByText('BALANCED'));

      expect(locationService.setAccuracy).toHaveBeenCalledWith('balanced');
    });
  });

  describe('Settings and History', () => {
    it('opens settings when button pressed', async () => {
      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Open Settings')).toBeTruthy();
      });

      fireEvent.press(getByText('Open Settings'));

      expect(locationService.openSettings).toHaveBeenCalled();
    });

    it('clears location history after confirmation', async () => {
      render(<LocationScreen navigation={{}} />);

      await waitFor(() => {
        expect(getByText('Clear Location History')).toBeTruthy();
      });

      fireEvent.press(getByText('Clear Location History'));

      expect(Alert).toHaveBeenCalledWith(
        'Clear History',
        'Are you sure you want to clear location history?',
        expect.any(Array)
      );

      const buttons = Alert.mock.calls[Alert.mock.calls.length - 1][2];
      const clearButton = buttons.find((b: any) => b.text === 'Clear');
      clearButton.onPress();

      await waitFor(() => {
        expect(locationService.clearLocationHistory).toHaveBeenCalled();
        expect(Alert).toHaveBeenCalledWith('Success', 'Location history cleared');
      });
    });
  });
});

function getByText(text: string | RegExp) {
  return screen.getByText(text);
}
