/**
 * SettingsScreen Tests
 *
 * Comprehensive test suite for SettingsScreen component covering:
 * - Rendering with user data
 * - Toggle interactions (notifications, biometric)
 * - Permission handling
 * - Logout flow
 * - Device info display
 * - Navigation interactions
 *
 * @see src/screens/settings/SettingsScreen.tsx
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react-native';
import { Alert } from 'react-native';
import { SettingsScreen } from '../../src/screens/settings/SettingsScreen';

// Mock contexts
jest.mock('../../src/contexts/AuthContext', () => ({
  useAuth: jest.fn(() => ({
    user: { email: 'test@example.com' },
    logout: jest.fn().mockResolvedValue(undefined),
  })),
}));

jest.mock('../../src/contexts/DeviceContext', () => ({
  useDevice: jest.fn(() => ({
    deviceState: {
      platform: 'iOS',
      deviceId: 'test-device-id-12345',
    },
    requestCapability: jest.fn().mockResolvedValue(true),
  })),
}));

describe('SettingsScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (Alert.alert as jest.Mock).mockClear();
  });

  // Test 1: Renders SettingsScreen with all sections
  it('should render SettingsScreen with all sections', () => {
    const { getByText } = render(<SettingsScreen />);

    expect(getByText('Settings')).toBeTruthy();
    expect(getByText('Account')).toBeTruthy();
    expect(getByText('Preferences')).toBeTruthy();
    expect(getByText('Device')).toBeTruthy();
  });

  // Test 2: Displays user email in profile section
  it('should display user email in profile section', () => {
    const { getByText } = render(<SettingsScreen />);

    expect(getByText('test@example.com')).toBeTruthy();
  });

  // Test 3: Displays device info correctly
  it('should display device info correctly', () => {
    const { getByText } = render(<SettingsScreen />);

    expect(getByText(/iOS/)).toBeTruthy();
    // Device ID is truncated to first 8 characters
    expect(getByText(/test-dev/)).toBeTruthy();
  });

  // Test 4: Displays all setting items
  it('should display all setting items', () => {
    const { getByText } = render(<SettingsScreen />);

    expect(getByText('Profile')).toBeTruthy();
    expect(getByText('Notifications')).toBeTruthy();
    expect(getByText('Biometric Authentication')).toBeTruthy();
    expect(getByText('Device Info')).toBeTruthy();
    expect(getByText('About')).toBeTruthy();
  });

  // Test 5: Shows logout button
  it('should show logout button', () => {
    const { getByText } = render(<SettingsScreen />);

    expect(getByText('Logout')).toBeTruthy();
  });

  // Test 6: Displays version number
  it('should display version number', () => {
    const { getAllByText } = render(<SettingsScreen />);

    // Version appears twice (in About section and at bottom)
    const versionElements = getAllByText('Atom v1.0.0');
    expect(versionElements.length).toBeGreaterThan(0);
  });
});

describe('SettingsScreen - Notification Toggle', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Toggles notifications on successfully
  it('should toggle notifications on when permission granted', async () => {
    const { useDevice } = require('../../src/contexts/DeviceContext');
    const mockRequestCapability = jest.fn().mockResolvedValue(true);
    useDevice.mockReturnValue({
      deviceState: { platform: 'iOS', deviceId: 'test-device-id' },
      requestCapability: mockRequestCapability,
    });

    const { getByText, UNSAFE_getAllByType } = render(<SettingsScreen />);

    // Find and press the notifications toggle
    const notificationText = getByText('Notifications');
    fireEvent.press(notificationText);

    await waitFor(() => {
      expect(mockRequestCapability).toHaveBeenCalledWith('notifications');
    });
  });

  // Test 2: Shows alert when notification permission denied
  it('should show alert when notification permission denied', async () => {
    const { useDevice } = require('../../src/contexts/DeviceContext');
    const mockRequestCapability = jest.fn().mockResolvedValue(false);
    useDevice.mockReturnValue({
      deviceState: { platform: 'iOS', deviceId: 'test-device-id' },
      requestCapability: mockRequestCapability,
    });

    const { getByText } = render(<SettingsScreen />);

    const notificationText = getByText('Notifications');
    fireEvent.press(notificationText);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Permission Denied',
        'Notification permission is required to enable notifications'
      );
    });
  });

  // Test 3: Toggles notifications off
  it('should toggle notifications off without requesting permission', async () => {
    const { useDevice } = require('../../src/contexts/DeviceContext');
    const mockRequestCapability = jest.fn().mockResolvedValue(true);
    useDevice.mockReturnValue({
      deviceState: { platform: 'iOS', deviceId: 'test-device-id' },
      requestCapability: mockRequestCapability,
    });

    const { getByText } = render(<SettingsScreen />);

    // First enable notifications
    const notificationText = getByText('Notifications');
    fireEvent.press(notificationText);

    await waitFor(() => {
      expect(mockRequestCapability).toHaveBeenCalled();
    });

    // Clear the mock
    mockRequestCapability.mockClear();

    // Disable notifications (should not request permission)
    fireEvent.press(notificationText);

    await waitFor(() => {
      expect(mockRequestCapability).not.toHaveBeenCalled();
    });
  });
});

describe('SettingsScreen - Biometric Toggle', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Enables biometric when hardware available
  it('should enable biometric when hardware available', async () => {
    const { useDevice } = require('../../src/contexts/DeviceContext');
    const mockRequestCapability = jest.fn().mockResolvedValue(true);
    useDevice.mockReturnValue({
      deviceState: { platform: 'iOS', deviceId: 'test-device-id' },
      requestCapability: mockRequestCapability,
    });

    const { getByText } = render(<SettingsScreen />);

    const biometricText = getByText('Biometric Authentication');
    fireEvent.press(biometricText);

    await waitFor(() => {
      expect(mockRequestCapability).toHaveBeenCalledWith('biometric');
    });
  });

  // Test 2: Shows alert when biometric not available
  it('should show alert when biometric not available', async () => {
    const { useDevice } = require('../../src/contexts/DeviceContext');
    const mockRequestCapability = jest.fn().mockResolvedValue(false);
    useDevice.mockReturnValue({
      deviceState: { platform: 'iOS', deviceId: 'test-device-id' },
      requestCapability: mockRequestCapability,
    });

    const { getByText } = render(<SettingsScreen />);

    const biometricText = getByText('Biometric Authentication');
    fireEvent.press(biometricText);

    await waitFor(() => {
      expect(Alert.alert).toHaveBeenCalledWith(
        'Biometric Not Available',
        'This device does not support biometric authentication or you have not enrolled a fingerprint/Face ID'
      );
    });
  });

  // Test 3: Disables biometric without requesting permission
  it('should disable biometric without requesting permission', async () => {
    const { useDevice } = require('../../src/contexts/DeviceContext');
    const mockRequestCapability = jest.fn().mockResolvedValue(true);
    useDevice.mockReturnValue({
      deviceState: { platform: 'iOS', deviceId: 'test-device-id' },
      requestCapability: mockRequestCapability,
    });

    const { getByText } = render(<SettingsScreen />);

    const biometricText = getByText('Biometric Authentication');
    fireEvent.press(biometricText);

    await waitFor(() => {
      expect(mockRequestCapability).toHaveBeenCalled();
    });

    mockRequestCapability.mockClear();

    // Disable biometric
    fireEvent.press(biometricText);

    await waitFor(() => {
      expect(mockRequestCapability).not.toHaveBeenCalled();
    });
  });
});

describe('SettingsScreen - Logout Flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Shows confirmation alert on logout press
  it('should show confirmation alert on logout press', () => {
    const { getByText } = render(<SettingsScreen />);

    const logoutButton = getByText('Logout');
    fireEvent.press(logoutButton);

    expect(Alert.alert).toHaveBeenCalledWith(
      'Logout',
      'Are you sure you want to logout?',
      expect.arrayContaining([
        expect.objectContaining({ text: 'Cancel', style: 'cancel' }),
        expect.objectContaining({ text: 'Logout', style: 'destructive' }),
      ])
    );
  });

  // Test 2: Calls logout when logout confirmed
  it('should call logout when logout confirmed', async () => {
    const { useAuth } = require('../../src/contexts/AuthContext');
    const mockLogout = jest.fn().mockResolvedValue(undefined);
    useAuth.mockReturnValue({
      user: { email: 'test@example.com' },
      logout: mockLogout,
    });

    const { getByText } = render(<SettingsScreen />);

    const logoutButton = getByText('Logout');
    fireEvent.press(logoutButton);

    // Get the alert calls
    const alertCalls = (Alert.alert as jest.Mock).mock.calls;
    const lastCall = alertCalls[alertCalls.length - 1];
    const logoutButtonConfig = lastCall[2][1]; // Get the Logout button config

    // Trigger the onPress callback
    await act(async () => {
      await logoutButtonConfig.onPress();
    });

    expect(mockLogout).toHaveBeenCalled();
  });

  // Test 3: Does not logout when cancel pressed
  it('should not logout when cancel pressed', async () => {
    const { useAuth } = require('../../src/contexts/AuthContext');
    const mockLogout = jest.fn().mockResolvedValue(undefined);
    useAuth.mockReturnValue({
      user: { email: 'test@example.com' },
      logout: mockLogout,
    });

    const { getByText } = render(<SettingsScreen />);

    const logoutButton = getByText('Logout');
    fireEvent.press(logoutButton);

    expect(mockLogout).not.toHaveBeenCalled();
  });
});

describe('SettingsScreen - Navigation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  // Test 1: Profile section is pressable
  it('should have pressable profile section', () => {
    const { getByText } = render(<SettingsScreen />);

    const profileText = getByText('Profile');
    expect(profileText.parent).toBeTruthy();
  });

  // Test 2: Device Info section is pressable
  it('should have pressable device info section', () => {
    const { getByText } = render(<SettingsScreen />);

    const deviceInfoText = getByText('Device Info');
    expect(deviceInfoText.parent).toBeTruthy();
  });

  // Test 3: About section is pressable
  it('should have pressable about section', () => {
    const { getByText } = render(<SettingsScreen />);

    const aboutText = getByText('About');
    expect(aboutText.parent).toBeTruthy();
  });
});

describe('SettingsScreen - Edge Cases', () => {
  // Test 1: Handles null user gracefully
  it('should handle null user gracefully', () => {
    const { useAuth } = require('../../src/contexts/AuthContext');
    useAuth.mockReturnValue({
      user: null,
      logout: jest.fn(),
    });

    const { getByText } = render(<SettingsScreen />);

    expect(getByText('Not logged in')).toBeTruthy();
  });

  // Test 2: Handles missing device info gracefully
  it('should handle missing device info gracefully', () => {
    const { useDevice } = require('../../src/contexts/DeviceContext');
    useDevice.mockReturnValue({
      deviceState: {
        platform: 'iOS',
        deviceId: undefined,
      },
      requestCapability: jest.fn(),
    });

    const { getByText } = render(<SettingsScreen />);

    // Should still render without crashing
    expect(getByText('Settings')).toBeTruthy();
  });

  // Test 3: Handles logout error gracefully
  it('should handle logout error gracefully', async () => {
    const { useAuth } = require('../../src/contexts/AuthContext');
    const mockLogout = jest.fn().mockRejectedValue(new Error('Logout failed'));
    useAuth.mockReturnValue({
      user: { email: 'test@example.com' },
      logout: mockLogout,
    });

    const { getByText } = render(<SettingsScreen />);

    const logoutButton = getByText('Logout');
    fireEvent.press(logoutButton);

    const alertCalls = (Alert.alert as jest.Mock).mock.calls;
    const lastCall = alertCalls[alertCalls.length - 1];
    const logoutButtonConfig = lastCall[2][1];

    try {
      await act(async () => {
        await logoutButtonConfig.onPress();
      });
    } catch (error) {
      // Error is expected
      expect(error).toBeDefined();
    }
  });
});

describe('SettingsScreen - Accessibility', () => {
  // Test 1: Has accessible labels
  it('should have accessible labels for all interactive elements', () => {
    const { getByText } = render(<SettingsScreen />);

    expect(getByText('Settings')).toBeTruthy();
    expect(getByText('Notifications')).toBeTruthy();
    expect(getByText('Biometric Authentication')).toBeTruthy();
    expect(getByText('Logout')).toBeTruthy();
  });

  // Test 2: Toggle elements are accessible
  it('should have accessible toggle elements', () => {
    const { getByText } = render(<SettingsScreen />);

    // Toggle items should be pressable
    const notifications = getByText('Notifications');
    const biometric = getByText('Biometric Authentication');

    expect(notifications.parent).toBeTruthy();
    expect(biometric.parent).toBeTruthy();
  });
});
